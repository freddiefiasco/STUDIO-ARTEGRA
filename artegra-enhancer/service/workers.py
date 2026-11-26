"""Workers implementation."""


import os
import shutil
import socket
import sys
import threading
import time
import uuid
from pathlib import Path

from engine import controls, fast_recipe, graph_banded, graph_v5t
from service import bxf_probe, card_factor, engine_options, mask_graph, memory_policy
from service.comfy import ComfyClient, ComfyError, WsListener
from service.settings import env_float
from service.util import now_iso
from service.windows_job import ProcessContainmentError, WindowsJobProcess, run_contained

COMFY_FLAGS = ['--disable-auto-launch', '--offline', '--preview-method', 'none', '--reserve-vram', '0.8',
               '--disable-dynamic-vram', '--disable-fast-disk', '--disable-async-offload', '--disable-pinned-memory',
               '--disable-cuda-malloc', '--disable-api-nodes', '--disable-manager-ui']
SECRET_ENV = {'HF_TOKEN', 'HUGGING_FACE_HUB_TOKEN', 'HF_TOKEN_PATH', 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY'}
# 5.0.2: every worker loads both of the app's node packs, the classic pack and the Large-image engine's (node_pack/claude_banded).
# The classic start check (required_classes, undeclared_inputs) stays classic-only, so a Large-image pack that fails to load never
# stops a classic worker: ComfyUI logs the failed import and goes on, and the worker records what is missing (banded_missing).
NODE_PACKS = ('claude_creative', 'claude_banded')


FEED_WAIT_S = 5.0

# 5.0.2 (eng:check CHK-3, W4S-F1): the cards of an engine that was sent a Large-image prompt and whose Windows Job handle
# could not be closed when it was stopped (WindowsJobProcess.close: job_handle 'close_failed'). Its processes may still run
# with that image's memory, which no admission counts, and nothing in the app holds a handle that could end them; so no
# engine starts on those cards again until the app restarts (Worker.ensure_started refuses with the plain sentence,
# banded_runner.RELEASE_KEPT_TEXT). {(the service's workers folder, card index): that sentence}: per service, so each test
# service keeps its own; nothing clears it while the service runs (an app restart closes the shared Job, which ends them).
LOST_CARDS = {}


def _fast_graphs(p):
    """The installed Fast recipe's stage graphs for these params (FAST PORT, 12 Nov 2026: its LoraLoaderModelOnly and its
    ClaudeSpotTiles inputs, seam_overlap among them), both live modes, or [] when no recipe can be built."""
    try:
        r = fast_recipe.recipe()
    except ValueError:
        return []
    if r is None:
        return []
    out = []
    for live in graph_v5t.PRODUCT_LIVE_MODES:
        g, _ = fast_recipe.build('x.png', 1024, 1024, p, 'x', live_preview=live)
        out.append(g)
    return out


def required_classes():
    """Every node class the production graphs can use (all protect categories on) plus the mask-preview graph, and the Fast
    recipe's graph when one is installed (LoraLoaderModelOnly)."""
    p, _ = controls.resolve({'protect': list(controls.PROTECT_ORDER)})
    g, _ = graph_v5t.build('x.png', 1024, 1024, p, 'x')
    g2, _ = graph_v5t.build('x.png', 1000, 504, p, 'x', f=1.5, s=2)
    fast = {n['class_type'] for fg in _fast_graphs(controls.stage_params(p, 0)) for n in fg.values()}
    return sorted({n['class_type'] for n in g.values()} | {n['class_type'] for n in g2.values()} | set(mask_graph.SAM_CLASSES)
                  | fast)


def banded_graphs(multi=False):
    """The Large-image engine's stage graphs (engine/graph_banded.build_product) over what can change a node's inputs: one
    prompt and both parts of the split finish, the speed stack on and off, both live modes, the sped-up options, every protect
    category (so the release terms and their unions are there), the capped Brownian cache constant, the banded finish's
    plan constants (contract finish_inputs: band_gb, processes and finish_tier reach CUFinishBanded when the plan carries
    them), and (`multi`) the static window split of one image on two cards. Sizes only; no plane is read."""
    p, _ = controls.resolve({'protect': list(controls.PROTECT_ORDER)})
    pk = controls.stage_params(p, 0)
    graphs = []
    for consts in ({}, {'brownian_cache': 8}, {'bxf_band_gb': 3.0, 'bxf_processes': 2, 'finish_tier': 'bxf'}):
        for part in (None, 'A', 'B'):
            for stack, faster in ((True, False), (False, False), (True, True)):
                for live in graph_v5t.PRODUCT_LIVE_MODES:
                    g, _ = graph_banded.build_product('w/input.plane', 2048, 2048, pk, 'x', 'w', 'r', constants=consts,
                                                      speed_stack=stack, live_preview=live, faster=faster, part=part)
                    graphs.append(graph_banded.add_multigpu(g, 2) if multi and part != 'B' else g)
    return graphs + banded_bolt_graphs(multi)


def banded_bolt_graphs(multi=False):
    """The Large-image Bolt stage graphs (contract bolt; R1b and C4): graph_banded.build_product with Bolt's constants and the
    shipped Fast recipe (graph_banded.BOLT_RECIPE), one prompt and both parts of the split finish, both live modes, every
    protect category, with and without the finish's plan constants, and (`multi`) on two cards. Bolt patches the spot fork's
    seam_overlap. [] when the installed Fast recipe is not the one this build makes (none installed, or a stand-in): no
    Large-image Bolt plan can then be made (banded_plan.bolt_recipe), so there is nothing to check."""
    p, _ = controls.resolve({'protect': list(controls.PROTECT_ORDER)})
    pk = controls.stage_params(p, 0)
    graphs = []
    base = {'mode': 'bolt', 'recipe': graph_banded.BOLT_RECIPE}
    try:
        for consts in (base, dict(base, bxf_band_gb=3.0, bxf_processes=2, finish_tier='bxf')):
            for part in (None, 'A', 'B'):
                for live in graph_v5t.PRODUCT_LIVE_MODES:
                    g, _ = graph_banded.build_product('w/input.plane', 2048, 2048, pk, 'x', 'w', 'r', f=2, s=2,
                                                      constants=consts, live_preview=live, part=part)
                    graphs.append(graph_banded.add_multigpu(g, 2) if multi and part != 'B' else g)
    except ValueError:              # the installed Fast recipe is not graph_banded.BOLT_RECIPE (or none is installed)
        return []
    return graphs


def required_inputs(multi=False, banded=False):
    """{class: sorted input names}: every value input the product graphs give a node of this app's own pack (Claude*), with
    the stack on and off, both live modes, every protect category (and, `multi`, the inputs of one image on two cards), plus
    the mask preview. ComfyUI drops an input its node does not declare without a word (execution.py get_input_data), so an
    older pack would run every image without the v4 options while the sidecar says it had them (12 Nov, QA ENGINE-5:
    tools/sync_node_pack.py installs the 9ea176c pack, whose ClaudeSpotTiles has none of them).

    5.0.2, banded=True: instead, every input the Large-image graphs (banded_graphs) give the Large-image pack's own nodes
    (graph_banded.NODE_SPECS: ClaudeSpotTilesBanded and the CU* nodes). The worker checks those apart, in its log only, so the
    classic start check is unchanged."""
    if banded:
        out = {}
        for g in banded_graphs(multi):
            for n in g.values():
                if n['class_type'] in graph_banded.NODE_SPECS:
                    out.setdefault(n['class_type'], set()).update(n['inputs'])
        return {k: sorted(v) for k, v in sorted(out.items())}
    p, _ = controls.resolve({'protect': ['architecture']})
    graphs = [graph_v5t.build_gate_preview('x.png', ['wall'], ['tree'], p['protect'], 'x'),
              graph_v5t.build_gate_preview('x.png', ['wall'], ['tree'], p['protect'], 'x', lean=True)]   # 5.0.2: lean SAM
    for stack in (True, False):
        for live in graph_v5t.PRODUCT_LIVE_MODES:
            g, _ = graph_v5t.build_product('x.png', 1024, 1024, p, 'x', speed_stack=stack, live_preview=live)
            graphs.append(graph_v5t.add_multigpu(g, 2) if multi else g)


    graphs += [graph_v5t.add_multigpu(g, 2) if multi else g for g in _fast_graphs(controls.stage_params(p, 0))]
    for live in graph_v5t.PRODUCT_LIVE_MODES:
        g, _ = graph_v5t.build_product('x.png', 1024, 1024, p, 'x', speed_stack=True, live_preview=live, faster=True)
        graphs.append(graph_v5t.add_multigpu(g, 2) if multi else g)
    out = {}
    for g in graphs:
        for n in g.values():
            if n['class_type'].startswith('Claude'):
                out.setdefault(n['class_type'], set()).update(n['inputs'])
    return {k: sorted(v) for k, v in sorted(out.items())}


def undeclared_inputs(object_info, multi=False, banded=False):
    """{class: [input names the product graphs send that the engine's /object_info does not declare]} (empty = all there).
    banded=True: the Large-image graphs' inputs of the Large-image pack's nodes (required_inputs(banded=True)); a class the
    engine does not have at all is banded_missing's to name, not listed here."""
    missing = {}
    for cls, names in required_inputs(multi, banded=banded).items():
        if banded and cls not in object_info:
            continue
        spec = (object_info.get(cls) or {}).get('input') or {}
        declared = set(spec.get('required') or {}) | set(spec.get('optional') or {})
        gone = [k for k in names if k not in declared]
        if gone:
            missing[cls] = gone
    return missing


def missing_banded(object_info):
    """The Large-image node classes (graph_banded.NODE_SPECS) the engine's /object_info does not have, sorted ([] = all
    loaded), or None when there is no /object_info to read (contract worker_banded)."""
    if not isinstance(object_info, dict) or not object_info:
        return None
    return sorted(c for c in graph_banded.NODE_SPECS if c not in object_info)


def gpu_names(cards):
    """'GPU 1', 'GPU 1 and GPU 2' (0-based card numbers in; the one name every line uses for a card, preview design)."""
    names = [f'GPU {g + 1}' for g in cards]
    return names[0] if len(names) == 1 else ', '.join(names[:-1]) + ' and ' + names[-1]


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


class WorkerError(Exception):
    """Plain message for the user; `detail` for the log."""

    def __init__(self, message, detail=None):
        super().__init__(message)
        self.detail = detail


def find_nvidia_smi():
    """Official driver install locations also work when an app has a restricted PATH."""
    found = shutil.which('nvidia-smi')
    if found:
        return found
    candidates = []
    if os.environ.get('SystemRoot'):
        candidates.append(Path(os.environ['SystemRoot']) / 'System32' / 'nvidia-smi.exe')
    for key in ('ProgramW6432', 'ProgramFiles'):
        if os.environ.get(key):
            candidates.append(Path(os.environ[key]) / 'NVIDIA Corporation' / 'NVSMI' / 'nvidia-smi.exe')
    return next((str(path) for path in candidates if path.is_file()), None)


def query_gpus(log, scratch_dir):
    """[{index, uuid, name, mem_free_gb, mem_total_gb}] from nvidia-smi, run inside its own Job."""
    exe = find_nvidia_smi()
    if not exe:
        raise WorkerError('The graphics card driver tools were not found, so the graphics cards cannot be used. Reinstall the '
                          'NVIDIA graphics driver.', detail='nvidia-smi not on PATH')
    Path(scratch_dir).mkdir(parents=True, exist_ok=True)
    code, text = run_contained([os.path.abspath(exe), '--query-gpu=index,uuid,name,memory.free,memory.total,driver_version',
                                '--format=csv,noheader,nounits'], timeout=20,
                               log_path=Path(scratch_dir) / f'nvidia-smi-{threading.get_ident()}.txt')
    if code != 0:
        raise WorkerError('The graphics cards could not be read. Restart the computer, or reinstall the NVIDIA graphics driver '
                          'if this keeps happening.', detail={'exit_code': code, 'output': text[-1000:]})
    gpus = parse_nvidia_smi(text, log)
    from runtime.compatibility import evaluate_nvidia_driver
    for gpu in gpus:
        check = evaluate_nvidia_driver(gpu.get('driver_version', ''))
        if check['errors']:
            raise WorkerError(' '.join(check['errors']))
        gpu['compatibility_warnings'] = check['warnings']
    return gpus


def parse_nvidia_smi(text, log=None):
    """Rows of `index, uuid, name, memory.free MiB, memory.total MiB` -> dicts; unreadable lines are logged and skipped."""
    gpus = []
    for line in text.strip().splitlines():
        parts = [x.strip() for x in line.split(',')]
        if len(parts) < 5 or not parts[0].isdigit():
            continue
        try:
            gpus.append({'index': int(parts[0]), 'uuid': parts[1], 'name': parts[2],
                         'mem_free_gb': round(float(parts[3]) / 1024, 2), 'mem_total_gb': round(float(parts[4]) / 1024, 2),
                         **({'driver_version': parts[5]} if len(parts) > 5 else {})})
        except ValueError:
            if log is not None:
                log.warn('nvidia_smi_parse', f'Unreadable nvidia-smi line: {line[:200]}')
    return gpus


def extra_model_paths_yaml(cfg):
    """extra_model_paths.yaml for a worker: the claude models (controlnet; and loras, FAST PORT 12 Nov 2026: Fast mode's
    Hyper-SD LoRA, read in place on the NAS, never copied), the vendored node pack as a custom_nodes folder (base = the app
    root, i.e. node_pack's parent; custom_nodes = node_pack) and, v4 preview design, the folder of the detailed live preview's TAESD XL
    decoder as vae_approx (read in place on the NAS, never copied)."""
    models = Path(cfg.claude_models_dir).as_posix()
    app_root = Path(cfg.node_pack_dir).parent.parent.as_posix()
    va = Path(cfg.vae_approx_dir)
    return (f'claude_models:\n  base_path: "{models}"\n  controlnet: controlnet\n  loras: loras\n'
            f'claude_custom_nodes:\n  base_path: "{app_root}"\n  custom_nodes: {Path(cfg.node_pack_dir).parent.name}\n'
            f'claude_preview:\n  base_path: "{va.parent.as_posix()}"\n  vae_approx: {va.name}\n')


def comfy_command(cfg, worker_dir, port, yaml_path, memory_profile=None):
    """The exact ComfyUI command line of SERVICE-SPEC 'Process model' (shared runtime python, read only)."""
    w = Path(worker_dir)
    # -I ignores PYTHONIOENCODING/PYTHONUTF8. Select UTF-8 explicitly so engine
    # logging cannot crash when a Windows account or data folder contains Unicode.
    return [str(cfg.runtime_python), '-I', '-X', 'utf8', '-S', '-B', '-u', str(Path(__file__).with_name('comfy_main.py')),
            str(Path(cfg.comfy_main).parent), str(cfg.site_packages),
            '--listen', '127.0.0.1', '--port', str(port),
            *memory_policy.launch_flags(COMFY_FLAGS, memory_profile or memory_policy.PROFILES['reference']),
            '--base-directory', str(w), '--input-directory', str(w / 'input'), '--output-directory', str(w / 'output'),
            '--temp-directory', str(w / 'temp'), '--user-directory', str(w / 'user'),
            '--models-directory', str(cfg.models_dir), '--extra-model-paths-config', str(yaml_path),
            '--disable-all-custom-nodes', '--whitelist-custom-nodes', *NODE_PACKS]


class Worker:
    shares_images = False
    # 5.0.2 (contract worker_banded): the Large-image classes this engine lacks, read from /object_info after each start;
    # None while unknown (before a start, after a stop, or with no /object_info to read), [] when every one is loaded.
    banded_missing = None
    # 5.0.2 wave 3 (contracts.g1u): the CU_BXF_LOCAL_TABLE this engine was started with (None: not started yet)
    bxf_local_table = None
    # 5.0.2 wave 4 (service item 1, admission safety): (job, item) of the image whose Large-image prompt this engine process
    # was last sent, set just before the prompt goes out (service/banded_runner.mark_sent), None for a process that was sent
    # none; cleared when the process goes (_teardown) and at every start. Such an engine runs no prompt of another image and
    # no protected-area preview: it is stopped when that image's thread ends (Runner._release_large_engines).
    banded_sent = None
    # True from that stop until the engine starts again: the next image's time left counts the engine start
    # (engine_options.start_eta_s); a Classic-only session never sets it
    stopped_after_large = False
    # 5.0.2 wave 4 (check W4S-C1): the plain sentence of a marked engine whose stop failed, so that its process may still
    # be alive with the Large-image image's memory (banded_runner.release_engine, or a stop here that raised), else None.
    # Such an engine keeps its mark and is kept out of use (hold_kept: state 'failed' with the start back-off and the
    # sentence as its problem), and ensure_started closes a marked engine before anything is started or run in it, and
    # refuses while it cannot (_close_marked): never another image's prompt in it, never a new process beside it. Cleared
    # when the process goes (_teardown) and at every start; a Classic-only session never sets it.
    banded_kept = None

    def __init__(self, gpu, cfg, settings, log, mode, shared_job=None):
        self.gpu = gpu
        self.shared_job = shared_job
        self.cfg = cfg
        self.settings = settings
        self.log = log
        self.mode = mode
        self.dir = cfg.workers_dir / f'gpu{gpu}'
        self.state = 'stopped'
        self.problem = None
        self.port = None
        self.client = None
        self.proc = None
        self.fake = None
        self.ws = None
        self.client_id = uuid.uuid4().hex
        self.busy = False
        self.last_used = time.monotonic()
        self.starts = 0
        self.name = f'Test graphics card {gpu + 1}' if mode != 'comfy' else f'Graphics card {gpu + 1}'
        self.uuid = None
        self.memory_profile = memory_policy.PROFILES['reference']
        self.vram_free_gb = None
        self.live_max_side = engine_options.LIVE_DEFAULT_MAX_SIDE
        self.live_groups = False
        self.vram_free_by_card = {}
        self.lock = threading.RLock()
        self.next_start_after = 0.0
        self.start_failures = 0
        self.problem_ref = None
        self.preflight_failed = False
        self.backoff_s = env_float('CU_START_BACKOFF_SECONDS', 15.0)
        self._abort = threading.Event()
        self.mem_cap_gb = None
        self._cap_problem = None


    def set_memory_cap(self, gb, total_gb=None):
        """Record this worker's share and apply it to its running Job at once (contained modes). Never raises: a share that
        cannot be applied is logged once and the shared parent Job's cap still bounds every worker together."""
        gb = round(float(gb), 2)
        changed = gb != self.mem_cap_gb
        self.mem_cap_gb = gb
        proc = self.proc
        if proc is None or not changed:
            return
        want = int(gb * (1 << 30))
        try:

            from service import windows_job
            with proc._lock:
                if not proc.job:
                    return
                windows_job._set_limits(proc.api, proc.job, want)
                proc.memory_limit_bytes = want
            self._cap_problem = None
            self.log.debug('worker_memory_cap', f'GPU {self.gpu + 1}: memory cap {gb:g} GB',
                           data={'gpu': self.gpu, 'cap_gb': gb, 'total_gb': total_gb, 'pid': proc.pid})
        except (ProcessContainmentError, OSError) as e:
            if self._cap_problem != str(e):
                self._cap_problem = str(e)
                self.log.warn('worker_memory_cap_failed', f'The memory cap of GPU {self.gpu + 1} could not be '
                              f'changed to {gb:g} GB; the shared cap still holds', data={'gpu': self.gpu, 'error': str(e)})

    def memory_cap_info(self):
        """The cap in force on the worker's own Job (read back from Windows for contained workers), in GB."""
        proc = self.proc
        if proc is not None:
            try:
                lim = proc.limits().get('job_memory_limit')
                return None if lim is None else round(lim / (1 << 30), 2)
            except (ProcessContainmentError, OSError):
                return self.mem_cap_gb
        return self.mem_cap_gb


    def info(self):
        return {'gpu': self.gpu, 'name': self.name, 'state': self.state, 'vram_free_gb': self.vram_free_gb,
                'busy': self.busy, 'port': self.port, 'pid': self.proc.pid if self.proc else None, 'starts': self.starts,
                'problem': self.problem, 'mode': self.mode, 'memory_cap_gb': self.memory_cap_info(),
                'memory_profile': self.memory_profile.to_dict()}

    def where(self):
        """'GPU 1', or 'GPU 1 and GPU 2' for an engine that holds several (it is named under each card). Until 12 Nov 'graphics
        card 1' / 'graphics cards 1 and 2', beside 'GPU 1 + GPU 2 started ...' on the same Activity plate (QA ID1, preview design: one
        name per thing)."""
        return gpu_names(list(getattr(self, 'gpus', (self.gpu,))))

    def alive(self):
        if self.mode == 'fake':
            return self.fake is not None and self.fake.alive
        if self.proc is None:
            return False
        try:
            return self.proc.poll_root() is None
        except ProcessContainmentError as e:
            self.log.error('worker_poll_failed', f'Worker state could not be read: {e}', data={'gpu': self.gpu})
            return False

    def exit_code(self):
        if self.proc is None:
            return None
        try:
            return self.proc.poll_root()
        except ProcessContainmentError:
            return None

    def log_file(self):
        return self.dir / f'comfy-{time.strftime("%Y%m%d")}.log'

    @property
    def input_dir(self):
        return self.dir / 'input'

    @property
    def output_dir(self):
        return self.dir / 'output'


    def ensure_started(self, gpu_lookup=None, abort=None):
        """Start the engine unless it is ready. `abort()` (optional) is polled while waiting for readiness; when it returns
        True the start is stopped (WorkerError 'The engine start was stopped.')."""
        with self.lock:
            lost = self.lost_text()
            if lost is not None:               # eng:check CHK-3: never a new engine beside processes no handle can end
                self.hold_lost(lost)
                raise WorkerError(lost, detail={'kept': True, 'until_restart': True})
            if self.banded_sent is not None or self.banded_kept is not None:
                self._close_marked()           # 5.0.2 wave 4 (check W4S-C1): a marked engine is closed first, never reused
                lost = self.lost_text()        # eng:check CHK-3: that close's Job handle did not close (_teardown)
                if lost is not None:
                    self.hold_lost(lost)
                    raise WorkerError(lost, detail={'kept': True, 'until_restart': True})
            if self.state == 'ready' and self.alive():
                return
            if self.state == 'ready':
                self.log.warn('worker_lost', 'The engine had stopped; starting it again', data={'gpu': self.gpu,
                                                                                                 'exit_code': self.exit_code()})
                self._teardown('lost')
            self._start(gpu_lookup, abort)

    def hold_kept(self, text):
        """5.0.2 wave 4 (check W4S-C1): a stop of this marked engine failed, so its process may still be alive and hold the
        Large-image image's memory: keep it out of use. It keeps its mark; its state is 'failed' with `text` as its problem
        and the start back-off, which the claim sites wait out (Runner._dispatch, _dispatch_split, _claim_worker), and the
        next ensure_started closes it before anything starts here (_close_marked)."""
        self.banded_kept = text
        self.state, self.problem = 'failed', text
        self.start_failures += 1
        self.next_start_after = time.monotonic() + min(300.0, self.backoff_s * 2 ** (self.start_failures - 1))

    def _lost_keys(self):
        return [(str(self.cfg.workers_dir), int(g)) for g in getattr(self, 'gpus', (self.gpu,))]

    def lost_text(self):
        """eng:check CHK-3: the plain sentence when one of this engine's cards is in LOST_CARDS (a Large-image engine there
        was stopped but its Job handle could not be closed), else None."""
        return next((LOST_CARDS[k] for k in self._lost_keys() if k in LOST_CARDS), None)

    def mark_lost(self, text):
        """eng:check CHK-3: this engine's cards take no new engine until the app restarts (LOST_CARDS), whichever worker
        (one card's or a shared one) asks for them; the first sentence is kept. Logged once per card."""
        new = [k for k in self._lost_keys() if k not in LOST_CARDS]
        for k in new:
            LOST_CARDS[k] = text
        if new:
            self.log.error('worker_kept_until_restart', text, data={'gpu': self.gpu, 'gpus': [k[1] for k in new]})

    def hold_lost(self, text):
        """eng:check CHK-3: a card in LOST_CARDS keeps its engine 'failed' with `text` as its problem and the start
        back-off (as hold_kept, without a process to keep), so the claim sites wait it out between refusals."""
        self.state, self.problem = 'failed', text
        self.start_failures += 1
        self.next_start_after = time.monotonic() + min(300.0, self.backoff_s * 2 ** (self.start_failures - 1))

    def _close_marked(self):
        """5.0.2 wave 4 (check W4S-C1), the root rule: an engine process that was sent a Large-image prompt runs nothing
        more, and nothing is started beside it. Called with the lock held when ensure_started finds the mark (or a kept
        engine); no caller does so in the middle of an image, whose own restarts stop the engine first, which clears the mark.
        The process is killed and torn down. While this worker still holds it (a stop that raised: its process may be
        alive), the engine stays kept (hold_kept) and the start is refused (WorkerError) with the plain sentence."""
        from service import banded_runner
        text = self.banded_kept or banded_runner.RELEASE_KEPT_TEXT.format(where=self.where())
        try:
            self._stop_locked(banded_runner.RELEASE_REASON, kill=True)
        except Exception as e:          # the stop path reports its own problems; the engine stays kept
            self.log.error('worker_kept_close_failed', text, data={'gpu': self.gpu, 'gpus': list(getattr(self, 'gpus',
                                                                                                         (self.gpu,))),
                                                                   'error': str(e)})
        if self.proc is not None or self.fake is not None:
            self.hold_kept(text)
            raise WorkerError(text, detail={'kept': True})

    def _start(self, gpu_lookup, abort=None):
        self._abort.clear()
        self.state, self.problem, self.problem_ref, self.preflight_failed = 'starting', None, None, False
        self.banded_missing = None
        self.banded_sent, self.stopped_after_large = None, False       # 5.0.2 wave 4: a new process has run no prompt
        self.banded_kept = None
        t0 = time.monotonic()


        for d in ('input', 'output', 'temp', 'user', 'cache', 'custom_nodes'):
            (self.dir / d).mkdir(parents=True, exist_ok=True)
        cards = list(getattr(self, 'gpus', (self.gpu,)))
        self.log.info('worker_starting', f'Starting the engine on {self.where()}',
                      data={'gpu': self.gpu, 'gpus': cards, 'mode': self.mode})
        try:
            if self.mode == 'fake':
                from service.fake_comfy import FakeComfy
                self._env()
                self.fake = FakeComfy(self.dir, gpu=self.gpu, fault_dir=str(self.cfg.workers_dir / 'fake-faults'),
                                      live_max_side=self.live_max_side, live_groups=self.live_groups)
                self.port = self.fake.start()
                self.client = ComfyClient(self.port)
            else:
                self._start_process(gpu_lookup)
            self._wait_ready(t0, abort)
            self._check_nodes()
            self.ws = WsListener(self.port, self.client_id, self.log, self.gpu)
            self.ws.start()
            self._wait_feed(abort)
        except Exception as e:
            aborted = self._abort.is_set() or (abort is not None and abort())
            plain = str(e) if isinstance(e, WorkerError) else 'The engine could not start.'
            if aborted:

                self.log.info('worker_start_stopped', 'The engine start was stopped', data={'gpu': self.gpu})
                self._teardown('start stopped')
                self.state = 'stopped'
                raise WorkerError('The engine start was stopped.', detail={'aborted': True})
            self.start_failures += 1
            self.next_start_after = time.monotonic() + min(300.0, self.backoff_s * 2 ** (self.start_failures - 1))
            ref = self.log.exception('worker_start_failed', plain, e, data={
                'gpu': self.gpu, 'mode': self.mode, 'log': str(self.log_file()),
                'detail': getattr(e, 'detail', None), 'retry_in_s': round(self.next_start_after - time.monotonic())})
            self.problem, self.problem_ref = plain, ref
            self._teardown('start failed')
            self.state = 'failed'
            raise WorkerError(plain, detail={'log_ref': ref, 'detail': getattr(e, 'detail', None)})
        self.starts += 1
        self.start_failures = 0
        self.state = 'ready'
        self.last_used = time.monotonic()
        self.log.info('worker_ready', f'The engine is ready on {self.where()} ({time.monotonic() - t0:.0f} s)',
                      data={'gpu': self.gpu, 'gpus': cards, 'port': self.port,
                            'pid': self.proc.pid if self.proc else os.getpid(), 'mode': self.mode, 'starts': self.starts,
                            'seconds': round(time.monotonic() - t0, 1),
                            'live_max_side': self.live_max_side,
                            'live_groups': self.live_groups,
                            'containment': self.proc.receipt() if self.proc else None})

    def _env(self):
        env = {k: v for k, v in os.environ.items() if k.upper() not in SECRET_ENV}
        tmp = str(self.dir / 'temp')
        env.update(TEMP=tmp, TMP=tmp, HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', PYTHONDONTWRITEBYTECODE='1',
                   PYTHONNOUSERSITE='1', PYTHONUNBUFFERED='1', PYTHONIOENCODING='utf-8')


        if engine_options.live_regions_on():
            env['CLAUDE_LIVE_MAX_SIDE'] = str(engine_options.LIVE_REGION_MAX_SIDE)


        if engine_options.outline_groups_on(shared=self.shares_images):
            env['CLAUDE_LIVE_GROUPS'] = '1'
        else:
            env.pop('CLAUDE_LIVE_GROUPS', None)
        # 5.0.2 wave 3 (contracts.g1u): the local G1u table the planner's table used, else '', so the Large-image finish
        # node loads the planner's table (the classic pack never reads it); a Large-image stage restarts an engine started
        # with another value (service/banded_runner.py)
        env[bxf_probe.LOCAL_TABLE_ENV] = self.bxf_local_table = bxf_probe.local_table_env()
        self.live_max_side = self._live_max_side(env)
        self.live_groups = env.get('CLAUDE_LIVE_GROUPS') == '1'
        return env

    @staticmethod
    def _live_max_side(env):
        """The long side this engine's live tiles are scaled to fit (the emitter's own reading of CLAUDE_LIVE_MAX_SIDE)."""
        try:
            return int(env.get('CLAUDE_LIVE_MAX_SIDE', '') or engine_options.LIVE_DEFAULT_MAX_SIDE)
        except ValueError:
            return engine_options.LIVE_DEFAULT_MAX_SIDE

    def _start_process(self, gpu_lookup):
        port = free_port()
        log = self.log_file()
        with open(log, 'a', encoding='utf8') as f:
            f.write(f'\n===== {now_iso()} worker start (gpu {self.gpu}, port {port}, mode {self.mode}) =====\n')
        env = self._env()
        total = float(self.settings.get()['ram_cap_gb'])
        ram = min(total, float(self.mem_cap_gb)) if self.mem_cap_gb else total
        if self.mode == 'comfy':
            gpu = (gpu_lookup or {}).get(self.gpu)
            if gpu is None:
                raise WorkerError(f'GPU {self.gpu + 1} was not found.')
            self.uuid, self.name = gpu['uuid'], gpu['name']
            self.memory_profile = memory_policy.choose_profile(gpu.get('mem_total_gb'),
                                                               self.settings.get().get('memory_profile', 'auto'))
            env.update(CUDA_VISIBLE_DEVICES=gpu['uuid'], CUDA_DEVICE_ORDER='PCI_BUS_ID')
            card_factor.worker_env(env, gpu)     # 5.0.2: spot's timing record on a card of 24 GiB or less (no pixel change)
            yaml = self.dir / 'extra_model_paths.yaml'
            yaml.write_text(extra_model_paths_yaml(self.cfg), encoding='utf8')
            args = comfy_command(self.cfg, self.dir, port, yaml, self.memory_profile)
        else:
            import numpy
            import PIL
            paths = sorted({str(Path(numpy.__file__).resolve().parents[1]), str(Path(PIL.__file__).resolve().parents[1])})
            args = [os.path.abspath(sys.executable), '-I', '-S', '-B', '-u', str(Path(__file__).with_name('fake_comfy.py')),
                    '--port', str(port), '--root', str(self.dir), '--gpu', str(self.gpu)]
            for p in paths:
                args += ['--path', p]
            env['CU_FAKE_FAULT_DIR'] = str(self.cfg.workers_dir / 'fake-faults')
        self.proc = WindowsJobProcess(args, cwd=str(self.dir), env=env, log_path=log, memory_limit_bytes=int(ram * (1 << 30)),
                                      parent_job=self.shared_job)
        self.port = port
        self.client = ComfyClient(port)
        self.log.info('worker_process', f'Engine process {self.proc.pid} started in a Windows Job (memory cap {ram:g} GB'
                      + (f', {total:g} GB shared by all graphics cards)' if self.shared_job is not None else ')'),
                      data={'gpu': self.gpu, 'pid': self.proc.pid, 'port': port, 'log': str(log),
                            'receipt': self.proc.receipt()})

    def _wait_feed(self, abort=None):
        ws = self.ws
        end = time.monotonic() + FEED_WAIT_S
        while ws.last_message is None and not ws.disconnects:
            if self._abort.is_set() or (abort is not None and abort()):
                raise WorkerError('The engine start was stopped.')
            if time.monotonic() >= end:
                self.log.warn('worker_feed_late', f'The progress feed of the engine on {self.where()} did not answer within '
                              f'{FEED_WAIT_S:g} s; progress is read by polling until it does',
                              data={'gpu': self.gpu, 'port': self.port, 'connected': ws.connected})
                return
            time.sleep(0.02)

    def _wait_ready(self, t0, abort=None):
        timeout = 30.0 if self.mode != 'comfy' else 900.0
        while True:
            if self._abort.is_set() or (abort is not None and abort()):
                raise WorkerError('The engine start was stopped.')
            if self.mode != 'fake':
                code = self.exit_code()
                if code is not None:
                    raise WorkerError(f'The engine closed while starting (exit code {code}). Details are in the log.',
                                      detail={'exit_code': code, 'log': str(self.log_file())})
            try:
                stats = self.client.system_stats(timeout=5.0)
                dev = (stats.get('devices') or [{}])[0]
                if dev.get('vram_free') is not None:
                    self.vram_free_gb = round(dev['vram_free'] / (1 << 30), 2)
                if self.mode == 'fake' and not hasattr(self, 'gpus'):


                    self.name = dev.get('name') or self.name
                break
            except ComfyError as e:
                if time.monotonic() - t0 > timeout:
                    raise WorkerError(f'The engine did not start within {timeout / 60:.0f} minutes. Details are in the log.',
                                      detail={'error': str(e.detail), 'log': str(self.log_file())})
                time.sleep(0.5 if self.mode != 'comfy' else 2.0)
        if self.proc is not None and not self.proc.assert_listener_owned(self.port, root_only=False):
            raise WorkerError('The engine started but could not be reached safely, so it was stopped. Try again.',
                              detail={'port': self.port, 'reason': 'listener not owned by the engine Job'})

    def _check_nodes(self):
        info = self.client.object_info()
        missing = [c for c in required_classes() if c not in info]
        if missing:
            raise WorkerError('The engine is missing parts it needs. Choose Repair installation in Settings.',
                              detail={'missing_node_classes': missing})
        undeclared = undeclared_inputs(info, multi=hasattr(self, 'gpus'))
        if undeclared:
            raise WorkerError('The engine is missing parts it needs. Choose Repair installation in Settings.',
                              detail={'undeclared_inputs': undeclared,
                                      'repair': 'the node pack is older than this app (it does not take every input the '
                                                'graphs send); redeploy the app with its own node_pack (install/deploy.py)'})
        self._check_banded(info)

    def _check_banded(self, info):
        """5.0.2: record which Large-image classes this engine lacks (banded_missing) and log, never raise: a classic worker
        starts whatever the Large-image pack's state; service/banded_runner refuses a Large-image prompt on a worker whose
        banded_missing is a non-empty list."""
        multi = hasattr(self, 'gpus')
        try:
            missing = missing_banded(info)
        except Exception as e:          # the check is for the Large-image engine only; it never stops a classic worker
            missing = None
            self.log.warn('worker_banded_unchecked', f'The Large-image engine parts on {self.where()} could not be checked: {e}',
                          data={'gpu': self.gpu, 'error': str(e)})
        self.banded_missing = missing   # 5.0.2 wave 3 (integ's finding): read from /object_info before the input check
        if missing:
            self.log.warn('worker_banded_missing', f'The engine on {self.where()} lacks Large-image engine parts; it runs '
                          'Classic engine images only', data={'gpu': self.gpu, 'banded_missing': missing})
        if missing is None:
            return
        try:
            undeclared = undeclared_inputs(info, multi=multi, banded=True)
        except Exception as e:          # only the input check is guarded: the classes it read stay recorded
            self.log.warn('worker_banded_unchecked', f'The inputs of the Large-image engine parts on {self.where()} could not '
                          f'be checked: {e}', data={'gpu': self.gpu, 'error': str(e), 'banded_missing': missing})
            return
        if undeclared:
            self.log.warn('worker_banded_inputs', f'The Large-image engine parts on {self.where()} do not take every input '
                          'its graphs send', data={'gpu': self.gpu, 'undeclared_inputs': undeclared})


    def stop(self, reason, kill=False):
        try:
            return self._stop(reason, kill)
        except Exception:
            # 5.0.2 wave 4 (check W4S-C1): a marked engine whose stop raised while this worker still holds its process may
            # still be alive with a Large-image image's memory: it is kept out of use until a stop works (an unmarked
            # engine's stop raises exactly as in 5.0.1)
            if (self.banded_sent is not None or self.banded_kept is not None) and (self.proc is not None
                                                                                  or self.fake is not None):
                from service import banded_runner
                self.hold_kept(self.banded_kept or banded_runner.RELEASE_KEPT_TEXT.format(where=self.where()))
            raise

    def _stop(self, reason, kill):
        self._abort.set()
        if not self.lock.acquire(timeout=3.0):

            proc, fake = self.proc, self.fake
            if proc is not None:
                proc.close(timeout=10)
            if fake is not None:
                fake.stop()
            self.lock.acquire()
        try:
            return self._stop_locked(reason, kill)
        finally:
            self.lock.release()

    def _stop_locked(self, reason, kill):
        if self.state == 'stopped' and self.proc is None and self.fake is None:
            return None
        self.state = 'stopping'
        if not kill and self.alive() and self.client is not None:
            try:
                self.client.interrupt(timeout=5.0)
            except ComfyError as e:
                self.log.warn('worker_interrupt_failed', f'Interrupt before stop failed: {e}', data={'gpu': self.gpu})
        cleanup = self._teardown(reason)
        self.state = 'stopped'
        cards = list(getattr(self, 'gpus', (self.gpu,)))
        self.log.info('worker_stopped', f'The engine on {self.where()} stopped ({reason})',
                      data={'gpu': self.gpu, 'gpus': cards, 'reason': reason, 'kill': kill, 'cleanup': cleanup})
        return cleanup

    def _teardown(self, reason):
        cleanup = None
        if self.ws is not None:
            self.ws.stop()
            self.ws = None
        if self.fake is not None:
            self.fake.stop()
            self.fake = None
        if self.proc is not None:
            cleanup = self.proc.close(timeout=15)
            if not cleanup.get('all_owned_processes_terminated'):
                self.log.error('worker_cleanup_incomplete', 'The engine processes may not all have stopped',
                               data={'gpu': self.gpu, 'cleanup': cleanup})
            if cleanup.get('job_handle') == 'close_failed' and (self.banded_sent is not None
                                                               or self.banded_kept is not None):
                from service import banded_runner        # eng:check CHK-3: its processes may live on with no handle
                self.mark_lost(banded_runner.RELEASE_LOST_TEXT.format(where=self.where()))
            self.proc = None
        self.client = None
        self.port = None
        self.client_id = uuid.uuid4().hex
        self.banded_missing = None
        self.banded_sent = None              # 5.0.2 wave 4: the process that was sent the Large-image prompt is gone
        self.banded_kept = None
        return cleanup


def cuda_visible_devices(gpus, lookup):
    """'uuidA,uuidB' for the card numbers `gpus` (0-based, nvidia-smi index order) from {index: {'uuid', 'name'}}."""
    missing = [g for g in gpus if g not in lookup]
    if missing:
        raise KeyError(gpu_names(missing) + (' was' if len(missing) == 1 else ' were') + ' not found.')
    if len(set(gpus)) != len(gpus):
        raise ValueError('a card can belong to one worker only')
    return ','.join(lookup[g]['uuid'] for g in gpus)


def worker_dir_name(gpus):
    return 'gpu' + '+'.join(str(g) for g in gpus)


class MultiCardWorker(Worker):
    """A worker that owns several graphics cards (service/gpu_policy 'split'; ported from the <workstation> lane prototype
    <project folder>/service/workers_mgpu.py). CUDA_VISIBLE_DEVICES = the UUIDs of its cards, comma separated, the first is cuda:0 of the
    ComfyUI process (CLIP, VAE, DAT2, SAM, the finish and the blend run there); the flags stay COMFY_FLAGS, including
    --disable-pinned-memory (the Windows dual-GPU pinned-memory fault). Its own folder workers/gpu<a>+<b>, the name
    'GPU 1 + GPU 2'. Stopping it (idle, settings, app close, watchdog) closes its Windows Job, which ends the one process that
    holds the SDXL and ControlNet replicas and the window threads on every card, so every card's memory is released together."""
    shares_images = True

    def __init__(self, gpus, cfg, settings, log, mode, shared_job=None):
        super().__init__(gpus[0], cfg, settings, log, mode, shared_job=shared_job)
        self.gpus = tuple(gpus)
        self.dir = cfg.workers_dir / worker_dir_name(self.gpus)
        self.name = ' + '.join(f'GPU {g + 1}' for g in self.gpus)

    def info(self):
        return dict(super().info(), gpus=list(self.gpus))

    def _start_process(self, gpu_lookup):
        if self.mode != 'comfy':
            return super()._start_process(gpu_lookup)
        port = free_port()
        log = self.log_file()
        with open(log, 'a', encoding='utf8') as f:
            f.write(f'\n===== {now_iso()} worker start (gpus {list(self.gpus)}, port {port}, mode {self.mode}) =====\n')
        env = self._env()
        total = float(self.settings.get()['ram_cap_gb'])
        ram = min(total, float(self.mem_cap_gb)) if self.mem_cap_gb else total
        try:
            env.update(CUDA_VISIBLE_DEVICES=cuda_visible_devices(self.gpus, gpu_lookup or {}), CUDA_DEVICE_ORDER='PCI_BUS_ID')
        except KeyError as e:
            raise WorkerError(str(e.args[0]))
        self.uuid = env['CUDA_VISIBLE_DEVICES']
        smallest = min((gpu_lookup[g].get('mem_total_gb') or 0 for g in self.gpus), default=0)
        self.memory_profile = memory_policy.choose_profile(smallest, self.settings.get().get('memory_profile', 'auto'))
        yaml = self.dir / 'extra_model_paths.yaml'
        yaml.write_text(extra_model_paths_yaml(self.cfg), encoding='utf8')
        args = comfy_command(self.cfg, self.dir, port, yaml, self.memory_profile)
        assert '--disable-pinned-memory' in args
        self.proc = WindowsJobProcess(args, cwd=str(self.dir), env=env, log_path=log, memory_limit_bytes=int(ram * (1 << 30)),
                                      parent_job=self.shared_job)
        self.port = port
        self.client = ComfyClient(port)
        self.log.info('worker_process', f'Engine process {self.proc.pid} started for {self.name} (memory cap {ram:g} GB)',
                      data={'gpus': list(self.gpus), 'pid': self.proc.pid, 'port': port, 'log': str(log),
                            'receipt': self.proc.receipt()})
