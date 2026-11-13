"""Workers implementation."""


import os
import shutil
import socket
import sys
import threading
import time
import uuid
from pathlib import Path

from engine import controls, fast_recipe, graph_v5t
from service import engine_options, mask_graph
from service.comfy import ComfyClient, ComfyError, WsListener
from service.settings import env_float
from service.util import now_iso
from service.windows_job import ProcessContainmentError, WindowsJobProcess, run_contained

COMFY_FLAGS = ['--disable-auto-launch', '--offline', '--preview-method', 'none', '--reserve-vram', '0.8',
               '--disable-dynamic-vram', '--disable-fast-disk', '--disable-async-offload', '--disable-pinned-memory',
               '--disable-cuda-malloc', '--disable-api-nodes', '--disable-manager-ui']
SECRET_ENV = {'HF_TOKEN', 'HUGGING_FACE_HUB_TOKEN', 'HF_TOKEN_PATH', 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY'}


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


def required_inputs(multi=False):
    """{class: sorted input names}: every value input the product graphs give a node of this app's own pack (Claude*), with
    the stack on and off, both live modes, every protect category (and, `multi`, the inputs of one image on two cards), plus
    the mask preview. ComfyUI drops an input its node does not declare without a word (execution.py get_input_data), so an
    older pack would run every image without the v4 options while the sidecar says it had them (12 Nov, QA ENGINE-5:
    tools/sync_node_pack.py installs the 9ea176c pack, whose ClaudeSpotTiles has none of them)."""
    p, _ = controls.resolve({'protect': ['architecture']})          
    graphs = [graph_v5t.build_gate_preview('x.png', ['wall'], ['tree'], p['protect'], 'x')]
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


def undeclared_inputs(object_info, multi=False):
    """{class: [input names the product graphs send that the engine's /object_info does not declare]} (empty = all there)."""
    missing = {}
    for cls, names in required_inputs(multi).items():
        spec = (object_info.get(cls) or {}).get('input') or {}
        declared = set(spec.get('required') or {}) | set(spec.get('optional') or {})
        gone = [k for k in names if k not in declared]
        if gone:
            missing[cls] = gone
    return missing


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


def query_gpus(log, scratch_dir):
    """[{index, uuid, name, mem_free_gb, mem_total_gb}] from nvidia-smi, run inside its own Job."""
    exe = shutil.which('nvidia-smi')
    if not exe:
        raise WorkerError('The graphics card driver tools were not found, so the graphics cards cannot be used. Reinstall the '
                          'NVIDIA graphics driver.', detail='nvidia-smi not on PATH')
    Path(scratch_dir).mkdir(parents=True, exist_ok=True)
    code, text = run_contained([os.path.abspath(exe), '--query-gpu=index,uuid,name,memory.free,memory.total',
                                '--format=csv,noheader,nounits'], timeout=20,
                               log_path=Path(scratch_dir) / f'nvidia-smi-{threading.get_ident()}.txt')
    if code != 0:
        raise WorkerError('The graphics cards could not be read. Restart the computer, or reinstall the NVIDIA graphics driver '
                          'if this keeps happening.', detail={'exit_code': code, 'output': text[-1000:]})
    return parse_nvidia_smi(text, log)


def parse_nvidia_smi(text, log=None):
    """Rows of `index, uuid, name, memory.free MiB, memory.total MiB` -> dicts; unreadable lines are logged and skipped."""
    gpus = []
    for line in text.strip().splitlines():
        parts = [x.strip() for x in line.split(',')]
        if len(parts) < 5 or not parts[0].isdigit():
            continue
        try:
            gpus.append({'index': int(parts[0]), 'uuid': parts[1], 'name': parts[2],
                         'mem_free_gb': round(float(parts[3]) / 1024, 2), 'mem_total_gb': round(float(parts[4]) / 1024, 2)})
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


def comfy_command(cfg, worker_dir, port, yaml_path):
    """The exact ComfyUI command line of SERVICE-SPEC 'Process model' (shared runtime python, read only)."""
    w = Path(worker_dir)
    return [str(cfg.runtime_python), '-I', '-S', '-B', '-u', str(Path(__file__).with_name('comfy_main.py')),
            str(Path(cfg.comfy_main).parent), str(cfg.site_packages),
            '--listen', '127.0.0.1', '--port', str(port), *COMFY_FLAGS,
            '--base-directory', str(w), '--input-directory', str(w / 'input'), '--output-directory', str(w / 'output'),
            '--temp-directory', str(w / 'temp'), '--user-directory', str(w / 'user'),
            '--models-directory', str(cfg.models_dir), '--extra-model-paths-config', str(yaml_path),
            '--disable-all-custom-nodes', '--whitelist-custom-nodes', 'claude_creative']


class Worker:
    shares_images = False              

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
                'problem': self.problem, 'mode': self.mode, 'memory_cap_gb': self.memory_cap_info()}

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
            if self.state == 'ready' and self.alive():
                return
            if self.state == 'ready':
                self.log.warn('worker_lost', 'The engine had stopped; starting it again', data={'gpu': self.gpu,
                                                                                                 'exit_code': self.exit_code()})
                self._teardown('lost')
            self._start(gpu_lookup, abort)

    def _start(self, gpu_lookup, abort=None):
        self._abort.clear()
        self.state, self.problem, self.problem_ref, self.preflight_failed = 'starting', None, None, False
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
            env.update(CUDA_VISIBLE_DEVICES=gpu['uuid'], CUDA_DEVICE_ORDER='PCI_BUS_ID')
            yaml = self.dir / 'extra_model_paths.yaml'
            yaml.write_text(extra_model_paths_yaml(self.cfg), encoding='utf8')
            args = comfy_command(self.cfg, self.dir, port, yaml)
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
            raise WorkerError('The engine is missing parts it needs. Reinstall Creative Upscaler.',
                              detail={'missing_node_classes': missing})
        undeclared = undeclared_inputs(info, multi=hasattr(self, 'gpus'))
        if undeclared:     
            raise WorkerError('The engine is missing parts it needs. Reinstall Creative Upscaler.',
                              detail={'undeclared_inputs': undeclared,
                                      'repair': 'the node pack is older than this app (it does not take every input the '
                                                'graphs send); redeploy the app with its own node_pack (install/deploy.py)'})

    
    def stop(self, reason, kill=False):
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
            self.proc = None
        self.client = None
        self.port = None
        self.client_id = uuid.uuid4().hex
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
    """A worker that owns several graphics cards (service/gpu_policy 'split'; ported from the WS lane prototype
    ws/service/workers_mgpu.py). CUDA_VISIBLE_DEVICES = the UUIDs of its cards, comma separated, the first is cuda:0 of the
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
        yaml = self.dir / 'extra_model_paths.yaml'
        yaml.write_text(extra_model_paths_yaml(self.cfg), encoding='utf8')
        args = comfy_command(self.cfg, self.dir, port, yaml)
        assert '--disable-pinned-memory' in args
        self.proc = WindowsJobProcess(args, cwd=str(self.dir), env=env, log_path=log, memory_limit_bytes=int(ram * (1 << 30)),
                                      parent_job=self.shared_job)
        self.port = port
        self.client = ComfyClient(port)
        self.log.info('worker_process', f'Engine process {self.proc.pid} started for {self.name} (memory cap {ram:g} GB)',
                      data={'gpus': list(self.gpus), 'pid': self.proc.pid, 'port': port, 'log': str(log),
                            'receipt': self.proc.receipt()})
