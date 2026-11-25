"""The phase-diff harness (engine design sections 7.1-7.2): both executors' graphs for the same stage (f, s), built by the
build's own builders, the dump spec that names every intermediate, the stage inputs, the worker command, and the prompt
runner. Developer only.

- Classic: engine/graph_v5t.build_product, with the identity record's own naming (input `cu_j_i_s<k>.png`, prefix
  `cu_j_i_s<k>`, controls.stage_params(default preset, k)), so its graph is byte for byte the one the identity record
  hashed (tests/fixtures/g0_identity_5_0_1.json) wherever the record has the stage. The harness never edits a graph: the
  instrumentation (tools/proof/comfy_nodes/cu_proof) dumps intermediates from inside the worker, so no node is added and
  ComfyUI runs the nodes in their own order (an added output node would change it: ComfyUI picks output nodes first).
- Large-image engine (BES): engine/graph_banded.build_product with the constants of engine/banded_plan.plan_forced (the
  classic plan's own stages through the Large-image executor; developer builds only).
- The worker: the product's ComfyUI command and model-paths file (service/workers.py), plus exactly one custom-nodes entry
  (this folder's comfy_nodes, holding cu_proof) and two whitelisted packs (claude_banded, cu_proof).

The reference pairs (7.1) are PAIRS; the internal case table that names the images and machines is not in this repository."""
import copy
import hashlib
import json
import time
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

import numpy as np

from engine import banded_plan, controls, graph_banded, graph_v5t, planner


@dataclass(frozen=True)
class Stage:
    """One stage: its input size (w, h, before padding), factor f, supersample s and index in its plan."""
    w: int
    h: int
    f: Fraction
    s: Fraction
    index: int

    def __post_init__(self):
        object.__setattr__(self, 'f', Fraction(self.f).limit_denominator(8))
        object.__setattr__(self, 's', Fraction(self.s).limit_denominator(8))

    @property
    def k(self):
        return self.f * self.s

    @property
    def padded(self):
        unit = planner._pad_unit(self.f, self.s)
        return planner._pad_to(self.w, unit), planner._pad_to(self.h, unit)

    @property
    def output(self):
        return int(self.w * self.f), int(self.h * self.f)


# Design 7.1: the exactness pairs, by k = f x s (the 64 GB pairs), and the workstation's two reference plans.
PAIRS = {
    'k4': (Stage(3500, 2188, 2, 2, 0),),                                   # 2x of 3500 x 2188 at s 2
    'k3': (Stage(2800, 3500, 2, Fraction(3, 2), 0),),                      # 2x of 2800 x 3500 at s 1.5
    'k2': (Stage(2560, 3200, 2, 1, 1),),                                   # forced f 2, s 1 on 2560 x 3200
    'k1.5': (Stage(3000, 2000, Fraction(3, 2), 1, 2),),                    # forced f 1.5, s 1 on 3000 x 2000
    'chain4x': (Stage(1280, 1600, 2, 2, 0), Stage(2560, 3200, 2, 2, 1)),   # 4x of 1280 x 1600, k 4 then 4
    'W1': (Stage(3500, 2188, 2, 2, 0), Stage(7000, 4376, 2, 1, 1)),        # 4x of 3500 x 2188, [s2, s1]
    'W2': (Stage(1280, 1600, 2, 2, 0), Stage(2560, 3200, 2, 2, 1), Stage(5120, 6400, 2, 1, 2)),   # 8x of 1280 x 1600
}
# 7.1's table writes the chain as "[s2, s1]" beside "k 4, then 4"; 5.0.1's planner makes 4x of 1280 x 1600 [s2, s2] at the
# 64 GB and 128 GB caps (k 4 then 4), so the chain is that plan; k 2 at 2560 x 3200 is the separate forced pair 'k2'.
# W1 and W2 are the plans 5.0.1's planner (plan_501) makes at the workstation's cap: 4x of 3500 x 2188 is [s2, s1] and 8x of
# 1280 x 1600 [s2, s2, s1] (the only three-pass classic reference, 131 MP); both are above a 64 GB PC's cap, so they run on
# the 128 GB class only, where the forced plan splits every stage's finish (L3r). The tools follow the planner, not the
# design tables (tests/proof/test_identity_checks.py checks both plans against plan_501).

# The memory cap of each machine class as the service sets it by default (settings.default_ram_cap_gb: RAM less
# max(2.5 GiB, 4 %), from the RAM Windows reports): a 64 GB PC 59.0, the 128 GB workstation 122.2, a 48 GB PC 45.2. A
# packet takes its cap from the class of the machine it runs on (and R6's 48 GB rows from pc48 on a 64 GB node).
MACHINE_CLASS_CAPS = {'pc64': 59.0, 'ws128': 122.2, 'pc48': 45.2}
PAIR_CLASS = {'k4': 'pc64', 'k3': 'pc64', 'k2': 'pc64', 'k1.5': 'pc64', 'chain4x': 'pc64', 'W1': 'ws128', 'W2': 'ws128'}


def cap_of(machine_class):
    """The default memory cap of a machine class (MACHINE_CLASS_CAPS); an unknown class is refused."""
    if machine_class not in MACHINE_CLASS_CAPS:
        raise ValueError(f'unknown machine class {machine_class!r} (one of {sorted(MACHINE_CLASS_CAPS)})')
    return MACHINE_CLASS_CAPS[machine_class]


def pair_cap(name, machine_class=None):
    """The cap a pair runs at: its own class's (PAIR_CLASS), or the class asked for."""
    return cap_of(machine_class or PAIR_CLASS[name])
OPTION_SETS = {
    'base': {},
    'live_detailed': {'live_preview': 'detailed'},
    'stack_off': {'speed_stack': False},
    'faster': {'faster': True},
    'bolt': {'bolt': True},          # Bolt (the run mode 'fast'): the classic through engine/fast_recipe, 2x at s 2 only
}
CN_CALLS = 64          # ControlNet calls recorded per sampler and ControlNet (each call is at least one window)
CN_FULL_CALLS = 4      # of those, the first calls whose values are kept (the rest by sha256)


def _sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf8')).hexdigest()


def graph_sha(graph):
    """The identity record's graph hash (tests/fixtures/g0_identity.py _sha)."""
    return _sha(graph)


def fixture_key(st):
    pw, ph = st.padded
    return f'{pw}x{ph}/f{float(st.f):g}/s{float(st.s):g}/k{st.index}'


def stage_params(st, base=None):
    p = base if base is not None else controls.resolve({})[0]
    return controls.stage_params(p, st.index)


def names(st):
    prefix = f'cu_j_i_s{st.index}'
    return prefix + '.png', prefix


def classic_graph(st, options='base', base_params=None):
    """The Classic engine's stage graph (graph_v5t.build_product) with the identity record's naming."""
    o = OPTION_SETS[options]
    name, prefix = names(st)
    pw, ph = st.padded
    if o.get('bolt'):
        from engine import fast_recipe
        return fast_recipe.build(name, pw, ph, stage_params(st, base_params), prefix, f=st.f, s=st.s,
                                 live_preview=o.get('live_preview'))
    return graph_v5t.build_product(name, pw, ph, stage_params(st, base_params), prefix, f=st.f, s=st.s,
                                   speed_stack=o.get('speed_stack', True), live_preview=o.get('live_preview'),
                                   faster=o.get('faster', False))


def forced_mode_supported():
    """True when this build's banded_plan.plan_forced takes the run mode (contracts.bolt: banded Bolt, B16)."""
    import inspect
    return 'mode' in inspect.signature(banded_plan.plan_forced).parameters


def classic_plan_of(stages):
    """The classic Plan made of `stages` as engine/planner makes a plan (each stage's render from its padded input, its
    output the unpadded input times f, 5.0.1's minutes and peak model): the plan the classic side of a pair runs."""
    out = []
    for st in stages:
        pw, ph = st.padded
        rw, rh, _, _ = graph_v5t.stage_sizes(pw, ph, st.f, st.s)
        rmp = rw * rh / 1e6
        out.append(planner.Stage(st.index, float(st.f), float(st.s), (st.w, st.h), (pw, ph), (rw, rh), st.output,
                                 round(rmp, 1), round(planner.stage_minutes(rmp), 1)))
    fac = 1
    for st in stages:
        fac *= st.f
    fac = int(fac) if fac.denominator == 1 else float(fac)
    return planner.Plan(True, fac, (stages[0].w, stages[0].h), out[-1].output_size, out,
                        round(sum(s.minutes for s in out), 1), round(max(planner.stage_peak(s) for s in out), 1))


def forced_plan(stages, cap, mode=None):
    """banded_plan.plan_forced of the classic plan made of `stages` (each stage's render from its padded input, its output the
    unpadded input times f, as engine/planner makes them). mode: the service's run mode ('standard' Redux, 'fast' Bolt),
    passed only when given; a build without banded Bolt (contracts.bolt) refuses a mode other than Redux in plain words."""
    classic = classic_plan_of(stages)
    fac = classic.factor
    if mode is None:
        return banded_plan.plan_forced(classic, cap)
    if not forced_mode_supported():
        if mode in ('standard', 'redux'):
            return banded_plan.plan_forced(classic, cap)
        return planner.Plan(False, fac, classic.input_size, classic.output_size, reason='banded Bolt is not built in this '
                            'build (plan_forced takes no run mode: contracts.bolt, B16)', engine='banded')
    return banded_plan.plan_forced(classic, cap, mode=mode)


def bes_parts(plan_stage):
    """The prompts one Large-image stage runs as (service/banded_runner.run_stage): ('A', 'B') when the plan splits its
    finish into a fresh worker (L3r, the stage's split_finish), else (None,)."""
    return ('A', 'B') if getattr(plan_stage, 'split_finish', False) else (None,)


def bes_graph(st, plan, plane_dir, input_plane, run_id, options='base', base_params=None, part=None):
    """The Large-image stage graph (graph_banded.build_product) with the forced plan's constants, writing the stage output
    at the stage's cropped size. part: None (one prompt), or 'A' / 'B' of a split stage (bes_parts), as the service builds
    them: A ends in CUPlaneCheckpoint, B is CUPlaneInput of A's planes and the finish, with no model loader."""
    o = OPTION_SETS[options]
    _, prefix = names(st)
    pw, ph = st.padded
    return graph_banded.build_product(input_plane, pw, ph, stage_params(st, base_params), prefix, plane_dir, run_id, f=st.f,
                                      s=st.s, constants=plan.banded, speed_stack=o.get('speed_stack', True),
                                      live_preview=o.get('live_preview'), faster=o.get('faster', False), part=part,
                                      output_size=st.output)


def prompt_graph(graph, spec):
    """The graph to submit: the built graph itself (a copy), never edited. Raises if the spec names a node it does not have."""
    missing = set(spec.get('roles', {})) - set(graph)
    if missing:
        raise ValueError(f'the dump spec names nodes the graph does not have: {sorted(missing)}')
    return copy.deepcopy(graph)


# --- the dump spec -----------------------------------------------------------------------------------------------------

CLASS_PHASE = {
    'SAM3_Detect': 'sam', 'ClaudeSAM3DetectLean': 'sam', 'CUSam3DetectLean': 'sam', 'ClaudeMaskUnion': 'sam',
    'CUMaskUnionPlane': 'sam', 'ClaudeUpscaleModelTiled': 'x4', 'ImageUpscaleWithModel': 'x4', 'CUUpscaleCanvas': 'x4',
    'ImageBlur': 'hints', 'CUBlurPlane': 'hints', 'ClaudeCannyTiled': 'hints', 'CUCannyPlane': 'hints',
    'ControlNetApplyAdvanced': 'hints', 'CUControlNetApplyPlane': 'hints', 'VAEEncodeTiled': 'vae_samplers',
    'CUEncodePlane': 'vae_samplers', 'KSampler': 'vae_samplers', 'VAEDecodeTiled': 'decodes', 'CUDecodePlane': 'decodes',
    'ClaudeV4Finish': 'finish', 'ClaudeShadowToe': 'finish', 'SaveImage': 'finish', 'CUFinishBanded': 'finish',
    'CUPlaneCheckpoint': 'finish', 'CUPlaneInput': 'load', 'LoadImage': 'load',
}


def twin_nodes(graph, a, b):
    """True when nodes a and b have the same class and the same inputs: ComfyUI's cache keys a node by its class and inputs,
    so it runs one of the two and serves the other's output from its cache (the other never executes)."""
    na, nb = graph[str(a)], graph[str(b)]
    return na['class_type'] == nb['class_type'] and na['inputs'] == nb['inputs']


def _src(graph, ref):
    if not (isinstance(ref, list) and len(ref) == 2):
        raise ValueError(f'not a node reference: {ref!r}')
    return str(ref[0]), int(ref[1])


def _mask_tree(graph, ref, group, roles):
    """Walk a protect or release union down to its SAM term nodes: 'union/<group>' for the root, 'sam/<group>/<i>' for each
    term in the builder's order."""
    nid, out = _src(graph, ref)
    roles.setdefault(nid, []).append([out, f'union/{group}', 'bitwise'])
    leaves = []

    def walk(n):
        node = graph[n]
        if node['class_type'] in ('ClaudeMaskUnion', 'CUMaskUnionPlane'):
            for i in range(1, 9):
                r = node['inputs'].get(f'mask_{i}')
                if r is not None:
                    walk(_src(graph, r)[0])
        else:
            leaves.append(n)
    walk(nid)
    for i, n in enumerate(leaves):
        roles.setdefault(n, []).append([0, f'sam/{group}/{i}', 'bitwise'])


def dump_spec(graph, info, executor, st, cn_calls=CN_CALLS, cn_full_calls=CN_FULL_CALLS):
    """{node id: [[output index, role, form]]} of every intermediate of design 7.2 in this stage graph, the files the BES
    writes by contract (engine/graph_banded plane_path), the samplers whose ControlNet calls are recorded, and every node's
    phase (for the time per phase). The graph is read, never changed.

    A split BES stage (info['part'] 'A' or 'B') is two prompts, and each part's spec names what that prompt makes: part A
    every intermediate up to the decodes and the masks (its CUPlaneCheckpoint takes them), part B only the stage output
    (its inputs are part A's checkpointed planes, already dumped)."""
    if executor not in ('classic', 'bes'):
        raise ValueError('executor must be classic or bes')
    part = info.get('part') if executor == 'bes' else None
    if part not in (None, 'A', 'B'):
        raise ValueError(f'unknown part {part!r}')
    k = st.k
    roles, files = {}, {}

    def add(nid, out, role, form):
        roles.setdefault(str(nid), []).append([int(out), role, form])
    by_class = {}
    for nid, v in graph.items():
        by_class.setdefault(v['class_type'], []).append(nid)
    samplers = info.get('samplers')
    ks1, ks2 = (None, None) if part == 'B' else (str(samplers['detail']), str(samplers['structure']))
    if part == 'B':
        if samplers is not None or any(c in by_class for c in ('KSampler', 'CheckpointLoaderSimple', 'CUUpscaleCanvas')):
            raise ValueError('part B of a split stage must have no sampler, model loader or canvas node')
        if len(by_class.get('CUFinishBanded', [])) != 1:
            raise ValueError('part B of a split stage must end in one CUFinishBanded')
        fin_id = by_class['CUFinishBanded'][0]
        fin = graph[fin_id]['inputs']
        files['stage_output'] = {'path': info['planes']['output'], 'form': 'save8_crop'}
    elif executor == 'classic':
        fin_id = by_class['ClaudeV4Finish'][0]
        fin = graph[fin_id]['inputs']
        cre, _ = _src(graph, fin['creative'])
        stru, _ = _src(graph, fin['structure'])
        ini, _ = _src(graph, fin['init'])
        for nid, want, role in ((cre, ks1, 'raw8'), (stru, ks2, 'rawlo8')):
            dec = _src(graph, graph[nid]['inputs']['image'])[0]
            if _src(graph, graph[dec]['inputs']['samples'])[0] != want:
                raise ValueError(f'{role}: the area scale does not decode the expected sampler')
            add(nid, 0, role, 'q8')
        add(ini, 0, 'init', 'u8_table')
        blur = by_class['ImageBlur'][0]
        canvas = _src(graph, graph[blur]['inputs']['image'])[0]
        add(canvas, 0, 'canvas', 'bitwise' if k == 4 else 'u8_table')
        if canvas != ini and twin_nodes(graph, canvas, ini):
            # At k 2 and 1.5 the canvas and the init are two ImageScale nodes with the same class and inputs. ComfyUI runs
            # one of them and serves the other from its cache (W1c, 26 Nov 2026: 'missing canvas' at stage 1), so the node
            # that runs carries both roles; cu_proof dumps each role once per prompt.
            add(ini, 0, 'canvas', 'bitwise' if k == 4 else 'u8_table')
            add(canvas, 0, 'init', 'u8_table')
        add(blur, 0, 'hint', 'bitwise')
        add(by_class['ClaudeCannyTiled'][0], 0, 'edges', 'edges')
        add(by_class['VAEEncodeTiled'][0], 0, 'latent/encode', 'bitwise')
        add(fin_id, 0, 'finish', 'round8')
        toe = [n for n in by_class.get('ClaudeShadowToe', []) if _src(graph, graph[n]['inputs']['image'])[0] == fin_id]
        if len(toe) != 1:
            raise ValueError('the classic stage has no shadow toe after its finish')
        add(toe[0], 0, 'stage_output', 'save8_crop')
    else:
        # one prompt ends in the finish; part A of a split stage ends in the checkpoint, which takes the same planes
        end = 'CUFinishBanded' if part is None else 'CUPlaneCheckpoint'
        if len(by_class.get(end, [])) != 1 or (part == 'A' and 'CUFinishBanded' in by_class):
            raise ValueError(f'the BES stage graph (part {part}) must end in one {end}')
        fin_id = by_class[end][0]
        fin = graph[fin_id]['inputs']
        cv = by_class['CUUpscaleCanvas'][0]
        add(cv, 0, 'canvas', 'bitwise' if k == 4 else 'u8_table')
        if _src(graph, fin['init']) != (cv, 1):
            raise ValueError(f'the BES {end} does not take init from the canvas node')
        add(cv, 1, 'init', 'u8_table')
        add(by_class['CUBlurPlane'][0], 0, 'hint', 'bitwise')
        add(by_class['CUCannyPlane'][0], 0, 'edges', 'edges')
        add(by_class['CUEncodePlane'][0], 0, 'latent/encode', 'bitwise')
        for nid in by_class['CUDecodePlane']:
            role = {'creative': 'raw8', 'structure': 'rawlo8'}[graph[nid]['inputs']['role']]
            add(nid, 0, role, 'q8')
        if part is None:
            files['stage_output'] = {'path': info['planes']['output'], 'form': 'save8_crop'}
    if executor == 'bes' and part != 'A' and (info.get('planes') or {}).get('gate'):
        # the finish's own protect gate plane, where a build's finish exposes one: the SAM phase's 'gate' role is then the
        # Large-image engine's own, compared with the classic's derived gate (D7); the base finish exposes none
        files['gate'] = {'path': info['planes']['gate'], 'form': 'bitwise'}
    if part != 'B':
        add(ks1, 0, 'latent/ks1', 'bitwise')
        add(ks2, 0, 'latent/ks2', 'bitwise')
        for group in ('protect', 'release'):
            if fin.get(group) is not None:
                _mask_tree(graph, fin[group], group, roles)
    phase_of_node = {}
    for nid, v in graph.items():
        c = v['class_type']
        if c == 'ImageScale':
            phase_of_node[nid] = 'decodes' if v['inputs'].get('upscale_method') == 'area' else 'x4'
        else:
            phase_of_node[nid] = CLASS_PHASE.get(c, 'other')
    return {'executor': executor, 'part': part,
            'stage': {'w': st.w, 'h': st.h, 'f': str(st.f), 's': str(st.s), 'index': st.index, 'padded': list(st.padded),
                      'output': list(st.output)},
            'graph_sha256': graph_sha(graph), 'roles': roles, 'files': files,
            'gate': {'dilate': fin.get('protect_dilate'), 'feather': fin.get('protect_feather')},
            'cn': {'nodes': {} if ks1 is None else {ks1: 'ks1', ks2: 'ks2'}, 'calls': int(cn_calls),
                   'full_calls': int(cn_full_calls), 'hints': True},
            'phase_of_node': phase_of_node}


# --- inputs ------------------------------------------------------------------------------------------------------------

def prepare_inputs(src_u8, st, input_dir, plane_dir):
    """The stage's padded input, as the service makes it: the classic's PNG (service/images.pad_reflect, save_png_atomic)
    named as the identity record names it, and the BES's input plane (service/banded_runner.pad_plane). Returns (png, plane)."""
    from engine import planes
    from service import banded_runner, images
    src = np.ascontiguousarray(np.asarray(src_u8, np.uint8)[..., :3])
    if src.shape[:2] != (st.h, st.w):
        raise ValueError(f'the stage input is {src.shape[1]}x{src.shape[0]}, not {st.w}x{st.h}')
    pw, ph = st.padded
    Path(input_dir).mkdir(parents=True, exist_ok=True)
    png = Path(input_dir) / names(st)[0]
    images.save_png_atomic(images.pad_reflect(src, (pw, ph)), png)
    plane = planes.Plane.create(Path(plane_dir) / 'input.plane', (ph, pw, 3), 'u8', producer='proof harness input',
                                run_id='input')
    banded_runner.pad_plane(src, plane, (pw, ph))
    plane.finish()
    return str(png), str(plane.path)


# --- the worker --------------------------------------------------------------------------------------------------------

PROOF_PACKS = ('claude_banded', 'cu_proof')


def worker_yaml(cfg, proof_dir):
    """The product's extra_model_paths.yaml, plus one custom-nodes entry: <proof_dir>/comfy_nodes (cu_proof)."""
    from service import workers
    base = Path(proof_dir).as_posix()
    return workers.extra_model_paths_yaml(cfg) + f'cu_proof_nodes:\n  base_path: "{base}"\n  custom_nodes: comfy_nodes\n'


def worker_command(cfg, worker_dir, port, yaml_path, proof_dir, memory_profile=None):
    """The product's ComfyUI command (service/workers.comfy_command) with claude_banded and cu_proof whitelisted too.
    Returns (command, record of what differs from the product's)."""
    from service import workers
    cmd = workers.comfy_command(cfg, worker_dir, port, yaml_path, memory_profile)
    i = cmd.index('--whitelist-custom-nodes')
    j = i + 1
    while j < len(cmd) and not str(cmd[j]).startswith('--'):
        j += 1
    have = cmd[i + 1:j]
    if 'claude_creative' not in have:
        raise ValueError(f'the product whitelist has no claude_creative: {have}')
    add = [p for p in PROOF_PACKS if p not in have]
    return cmd[:j] + add + cmd[j:], {'whitelist_added': add, 'yaml_added': 'cu_proof_nodes',
                                     'product_command_sha256': _sha(cmd)}


class RunFailed(RuntimeError):
    pass


ENTRY_KEYS = ('status', 'outputs', 'prompt', 'meta')


def history_entry(answer, prompt_id):
    """The history entry of one prompt from a client's history() answer, or None while the prompt has none.

    service/comfy.ComfyClient.history (the client every engine object here holds) returns the entry itself: ComfyUI's
    GET /history/<id> answers {<id>: entry} and the client returns answer.get(<id>), so None (or {}) until the prompt is
    done. A client that hands back ComfyUI's raw answer instead ({<id>: entry}) is read too, as a fallback."""
    if not isinstance(answer, dict) or not answer:
        return None
    if any(k in answer for k in ENTRY_KEYS):
        return answer
    e = answer.get(prompt_id)
    return e if isinstance(e, dict) else None


def _failure_text(status):
    out = []
    for m in status.get('messages') or []:
        if not (isinstance(m, (list, tuple)) and m):
            continue
        d = (m[1] if len(m) > 1 else None) or {}
        if m[0] == 'execution_error':
            out.append(f"{d.get('node_type', '?')} (node {d.get('node_id', '?')}): {d.get('exception_type', '')}: "
                       f"{d.get('exception_message', '')}".strip())
        elif m[0] == 'execution_interrupted':
            out.append('interrupted')
    return '; '.join(out) or 'error'


def run_prompt(client, graph, prompt_id, client_id='cu-proof', poll_s=2.0, timeout_s=6 * 3600, on_poll=None):
    """Submit one prompt with our own prompt id (the instrumentation finds its spec by it) and wait for its history entry.
    client: service/comfy.ComfyClient (or any object with its prompt() and history(); history_entry reads either answer
    shape). Returns the entry; raises RunFailed on an error, an interruption or a timeout."""
    client.prompt(graph, client_id, prompt_id=prompt_id)
    t0 = time.monotonic()
    while True:
        e = history_entry(client.history(prompt_id), prompt_id)
        st = (e or {}).get('status') or {}
        if st.get('completed') is not None and st.get('status_str') in ('success', 'error'):
            if st['status_str'] != 'success':
                raise RunFailed(f'prompt {prompt_id} failed: {_failure_text(st)}')
            return e
        if time.monotonic() - t0 > timeout_s:
            raise RunFailed(f'prompt {prompt_id} did not finish within {timeout_s} s')
        if on_poll:
            on_poll()
        time.sleep(poll_s)
