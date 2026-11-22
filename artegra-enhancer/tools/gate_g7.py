"""Gate G7 (engine design section 2.7 and B1; CPU, sizes and seeds only): are the sampler's Brownian noise draws bit-identical
with torchsde's increment cache at 45 (its default, what every classic and Large-image plan has today) and at 8?

dpmpp_2m_sde draws its noise from ComfyUI's BrownianTreeNoiseSampler (comfy/k_diffusion/sampling.py), one torchsde 0.2.6
BrownianTree per seed, whose BrownianInterval keeps an LRU cache of 45 latent-size increments on the CPU (11.25 B per render
pixel; 10.7 GiB at 1 GP). The Large-image engine can cap it through node_pack/claude_banded/noise_banded.py (the fork's
`brownian_cache` input); the plan constant may become 8 only if this gate passes (engine/banded_plan.BROWNIAN_CAPPED is
flipped by a later item, with the memory model re-checked).

What is compared, for each latent size, seed and schedule (KSampler's karras schedule of 30 steps for SDXL's sigma range at
denoise 1.0 and at the product's 0.68 and 0.48; dpmpp_2m_sde's query pattern: (sigma_i, sigma_i+1) for every step that does
not end at 0):
- 'stock45': ComfyUI's own BrownianTreeNoiseSampler, compiled from the shipped file;
- 'capped8': noise_banded.make_class(stock, 8), the class the fork installs;
- 'prefetch45': the classic noise prefetch (node_pack/claude_creative/noise.py, as the classic graph runs it);
- 'prefetch_capped8': noise_banded.install(..., 8, prefetch=True), the fork's path with noise_prefetch on.
Every draw of every variant must equal stock45's to the bit. The shipped ComfyUI files are checked against
runtime/source-manifest.json first.

Usage (the worker runtime's Python, or any Python with torch and torchsde 0.2.6; from the artegra-enhancer folder):
    python -B tools/gate_g7.py --comfy <ComfyUI folder> [--out verdict.json] [--quick] [--threads N] [--schedules S]
--threads sets this process's torch CPU threads (default 8, to share the machine); every variant runs in the same process at
the same count, so the comparison does not depend on it. --schedules (build wave 3) chooses what is compared: 'gate' (the
registered gate: 30 steps at denoise 1.0, 0.68 and 0.48; the default), 'bolt' (Bolt's 8 executed steps at its Looks' denoise:
dev run plan2-g7-bolt-schedules) or 'redux-looks' (30 steps at every Look's own creative denoise of stages 0-2 and its
structure denoise, from engine/controls.py: dev run plan3-g7-redux-looks; values whose schedules are equal tensors run once,
by the group's smallest value, and the verdict lists the groups). Exit code 0 when every draw is identical, 1 otherwise."""
import argparse
import ast
import contextlib
import hashlib
import importlib
import importlib.util
import json
import math
import platform
import sys
import time
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIZES = ((1, 4, 128, 128), (1, 4, 251, 377), (1, 4, 1024, 768))      # latents of 1 MP, 6 MP and 50 MP renders
QUICK_SIZES = ((1, 4, 32, 32), (1, 4, 61, 47), (1, 4, 96, 128))
STEPS = 30
DENOISE = (1.0, 0.68, 0.48)
SEEDS = (0, 869316851, 2 ** 63 - 25)
QUICK_SEEDS = (0, 869316851)
VARIANTS = ('capped8', 'prefetch45', 'prefetch_capped8')
CAP = 8
BOLT_STEPS = 8                          # fast_recipe.STEPS: Bolt's samplers' executed steps
BOLT_DENOISE = (0.436, 0.51, 0.58, 0.55)   # Bolt's Looks at stage 0: Light 0.436 / 0.51, Default 0.58 / 0.55 (detail / structure)
SCHEDULES = ('gate', 'bolt', 'redux-looks')
LOOK_STAGES = 3                         # stages 0-2: an 8x plan's three passes


def blob_sha1(data):
    return hashlib.sha1(b'blob %d\0' % len(data) + data).hexdigest()


def shipped(comfy, rel):
    """A ComfyUI file's text, after checking it is the runtime's own (git blob hash in runtime/source-manifest.json)."""
    files = json.loads((ROOT / 'runtime' / 'source-manifest.json').read_text(encoding='utf8'))['files']
    data = (Path(comfy) / rel).read_bytes()
    if files[rel]['blob'] not in (blob_sha1(data), blob_sha1(data.replace(b'\r\n', b'\n'))):
        raise SystemExit(f'{rel} in {comfy} is not the runtime\'s file')
    return data.decode('utf8')


def sampling_module(comfy):
    """comfy.k_diffusion.sampling's BatchedBrownianTree, BrownianTreeNoiseSampler, get_sigmas_karras and append_zero, compiled
    from the shipped file into a module of that name (nothing else of ComfyUI is imported)."""
    import torch
    import torchsde
    src = shipped(comfy, 'comfy/k_diffusion/sampling.py')
    names = {'BatchedBrownianTree', 'BrownianTreeNoiseSampler', 'get_sigmas_karras', 'append_zero'}
    body = [n for n in ast.parse(src).body if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name in names]
    if {n.name for n in body} != names:
        raise SystemExit('comfy/k_diffusion/sampling.py does not define the Brownian sampler as expected')
    for n in body:
        n.decorator_list = []
    mod = types.ModuleType('comfy.k_diffusion.sampling')
    mod.__dict__.update(torch=torch, torchsde=torchsde, math=math)
    exec(compile(ast.Module(body=body, type_ignores=[]), 'comfy/k_diffusion/sampling.py', 'exec'), mod.__dict__)
    return mod


def sdxl_sigma_range():
    """SDXL's sigma_min and sigma_max (comfy/model_sampling.py ModelSamplingDiscrete: scaled-linear betas 0.00085-0.012 over
    1000 steps, sigmas = sqrt((1 - alphas_cumprod) / alphas_cumprod))."""
    import torch
    betas = torch.linspace(0.00085 ** 0.5, 0.012 ** 0.5, 1000, dtype=torch.float64) ** 2
    ac = torch.cumprod(1.0 - betas, dim=0)
    sig = (((1 - ac) / ac) ** 0.5).float()
    return float(sig[0]), float(sig[-1])


def schedule(ks, steps, denoise, smin, smax):
    """KSampler.set_steps with the karras scheduler: the full schedule, or the last steps + 1 of a longer one."""
    if denoise is None or denoise > 0.9999:
        return ks.get_sigmas_karras(steps, smin, smax)
    return ks.get_sigmas_karras(int(steps / denoise), smin, smax)[-(steps + 1):]


def look_values(stages=LOOK_STAGES):
    """Redux's own denoise values (engine/controls.py): for every Look, the creative denoise of stages 0 to stages - 1
    (controls.stage_params) and the structure denoise, as rows and as the sorted distinct values. Every row must sample as
    G7 models it (STEPS executed steps, karras, dpmpp_2m_sde)."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from engine import controls
    rows = []
    for look in controls.PRESET_ORDER:
        p = controls.resolve({'preset': look})[0]
        for k in range(stages):
            s = controls.stage_params(p, k)
            if (s['steps'], s['scheduler'], s['sampler']) != (STEPS, 'karras', 'dpmpp_2m_sde'):
                raise SystemExit(f'{look} stage {k} does not sample as G7 models it')
            rows.append({'look': look, 'stage': k, 'creative': s['denoise'], 'structure': s['structure']})
    return rows, sorted({r['creative'] for r in rows} | {r['structure'] for r in rows})


def schedule_groups(ks, steps, values, smin, smax):
    """The values grouped by their schedule: each group's members give equal sigma tensors (torch.equal), its key the
    smallest member. [(representative, [members], len(int(steps / representative)) )] in ascending order."""
    import torch
    groups = []
    for d in sorted(values):
        sig = schedule(ks, steps, d, smin, smax)
        for g in groups:
            if torch.equal(g[2], sig):
                g[1].append(d)
                break
        else:
            groups.append((d, [d], sig))
    return [(rep, members, int(steps / rep)) for rep, members, _ in groups]


def plan_schedules(comfy, which):
    """(steps, denoise values to run, record extras) for --schedules `which` (SCHEDULES)."""
    if which == 'gate':
        return STEPS, DENOISE, {}
    if which == 'bolt':
        return BOLT_STEPS, BOLT_DENOISE, {'schedules': "Bolt: KSampler karras, 8 executed steps of int(8 / denoise), the "
                                                       "Looks' denoise"}
    if which != 'redux-looks':
        raise SystemExit(f'--schedules must be one of {SCHEDULES}')
    rows, values = look_values()
    ks = sampling_module(comfy)
    smin, smax = sdxl_sigma_range()
    groups = schedule_groups(ks, STEPS, values, smin, smax)
    return STEPS, tuple(g[0] for g in groups), {
        'schedules': "Redux: KSampler karras, 30 executed steps of int(30 / denoise), every Look's stage 0-2 denoise",
        'looks': rows, 'values': values,
        'schedule_groups': [{'representative': g[0], 'members': g[1], 'karras_n': g[2]} for g in groups]}


def banded_noise_module():
    """node_pack/claude_banded/noise_banded.py, loaded with its package under a private name."""
    name = 'claude_banded_gate_g7'
    if name not in sys.modules:
        d = ROOT / 'node_pack' / 'claude_banded'
        spec = importlib.util.spec_from_file_location(name, d / '__init__.py', submodule_search_locations=[str(d)])
        pkg = importlib.util.module_from_spec(spec)
        sys.modules[name] = pkg
        spec.loader.exec_module(pkg)
    return importlib.import_module(name + '.noise_banded')


def classic_pack_stand_in():
    """A module that the pack's _classic_pack() finds, whose .noise is node_pack/claude_creative/noise.py itself."""
    mod = types.ModuleType('cu_gate_g7_classic')
    mod.__path__ = [str(ROOT / 'node_pack' / 'claude_creative')]
    mod.NODE_CLASS_MAPPINGS = {'ClaudeV4Finish': object, 'ClaudeShadowToe': object}
    mod.shadow_toe_u8 = lambda *a: None
    return mod


def draws(cls, x, sigmas, seed):
    """dpmpp_2m_sde's draws: the sampler made as it makes it, queried at (sigma_i, sigma_i+1) for every step not ending at 0."""
    smin, smax = sigmas[sigmas > 0].min(), sigmas.max()
    ns = cls(x, smin, smax, seed=seed, cpu=True)
    return [ns(sigmas[i], sigmas[i + 1]) for i in range(len(sigmas) - 1) if sigmas[i + 1] != 0]


def run(comfy, sizes=SIZES, seeds=SEEDS, steps=STEPS, denoise=DENOISE, cap=CAP, log=print):
    import torch
    import torchsde
    ks = sampling_module(comfy)
    nb = banded_noise_module()
    classic = classic_pack_stand_in()
    stock = ks.BrownianTreeNoiseSampler
    smin, smax = sdxl_sigma_range()
    cases, ok = [], True
    pkg, sub = types.ModuleType('comfy'), types.ModuleType('comfy.k_diffusion')
    pkg.__path__, sub.__path__ = [], []
    pkg.k_diffusion, sub.sampling = sub, ks
    mods = {'comfy': pkg, 'comfy.k_diffusion': sub, 'comfy.k_diffusion.sampling': ks, classic.__name__: classic}
    t0 = time.time()
    with _patched_modules(mods):
        for size in sizes:
            x = torch.zeros(size, dtype=torch.float32)
            for d in denoise:
                sig = schedule(ks, steps, d, smin, smax)
                for seed in seeds:
                    ref = draws(stock, x, sig, seed)
                    row = {'latent': list(size), 'denoise': d, 'seed': seed, 'draws': len(ref)}
                    for v in VARIANTS:
                        if v == 'capped8':
                            got = draws(nb.make_class(stock, cap), x, sig, seed)
                        else:
                            h = (nb.install(sig, cap, prefetch=True) if v == 'prefetch_capped8'
                                 else importlib.import_module(classic.__name__ + '.noise').install(sig))
                            try:
                                got = draws(ks.BrownianTreeNoiseSampler, x, sig, seed)
                            finally:
                                h.uninstall()
                            if ks.BrownianTreeNoiseSampler is not stock:
                                raise SystemExit('the noise sampler was not put back')
                        diff = sum(int((a != b).sum()) for a, b in zip(ref, got)) + abs(len(ref) - len(got)) * ref[0].numel()
                        row[v] = diff
                        ok = ok and diff == 0
                    cases.append(row)
                    log(json.dumps(row))
    return {'gate': 'G7', 'verdict': 'PASS' if ok else 'FAIL', 'cache_compared': [45, cap],
            'identical': ok, 'steps': steps, 'denoise': list(denoise), 'scheduler': 'karras', 'sampler': 'dpmpp_2m_sde',
            'sigma_range': [smin, smax], 'cases': cases, 'seconds': round(time.time() - t0, 1),
            'torch': torch.__version__, 'torchsde': getattr(torchsde, '__version__', None), 'python': platform.python_version(),
            'cpu': platform.processor() or platform.machine()}


@contextlib.contextmanager
def _patched_modules(mods):
    saved = {k: sys.modules.get(k) for k in mods}
    sys.modules.update(mods)
    try:
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--comfy', required=True, help='the runtime ComfyUI folder (read only)')
    ap.add_argument('--out', help='write the verdict JSON here')
    ap.add_argument('--quick', action='store_true', help='small latents and two seeds (a smoke run, not the gate)')
    ap.add_argument('--threads', type=int, default=8, help="this process's torch CPU threads (default 8)")
    ap.add_argument('--schedules', choices=SCHEDULES, default='gate', help="what is compared (default: the registered gate)")
    a = ap.parse_args(argv)
    import torch
    torch.set_num_threads(a.threads)
    steps, denoise, extra = plan_schedules(a.comfy, a.schedules)
    v = run(a.comfy, QUICK_SIZES if a.quick else SIZES, QUICK_SEEDS if a.quick else SEEDS, steps=steps, denoise=denoise,
            log=lambda line: print(line, flush=True))
    v.update(extra)
    v['quick'], v['threads'], v['schedules_run'] = bool(a.quick), a.threads, a.schedules
    text = json.dumps(v, indent=1)
    if a.out:
        Path(a.out).write_text(text + '\n', encoding='utf8')
    print(json.dumps({k: v[k] for k in ('gate', 'verdict', 'seconds', 'torch', 'torchsde', 'quick')}))
    return 0 if v['identical'] else 1


if __name__ == '__main__':
    sys.exit(main())
