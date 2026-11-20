"""Gate G2 (and G2r): the banded exact finish against 5.0.1's classic finish, end to end (engine design 2.5, 7.3).

The oracle is 5.0.1's own chain, as the classic graph runs it: ClaudeV4Finish.run (the 8-bit inputs as float32, quantize_8bit,
v4finish.v4_finish, to_u8 / 255), ClaudeShadowToe.run (round to 8 bits, shadow_toe_u8, / 255) and SaveImage
(np.clip(255 * x, 0, 255).astype(uint8)), then the stage crop. The BXF is node_pack/claude_banded/bxf/finish.py, loaded through
the banded node pack as the worker loads it (the engine by path as cu_banded_engine), on planes in a work folder.

Procedural scenes exercise every branch: open sky connected to the top border with canopy gaps (sky_mask, sky_gaps, the glow),
hard-edged geometry, flat walls with invented badges in the creative pass (hardware islands and the colour filter), a timber
floor with tan litter (material_mask, litter islands), deep shadows (keep_blacks, the toe), protect and release masks (the
gate), and the option switches: clamp agree5 / lead / mm, lf hybmin / hyb, keep_blacks render / pre_narrow, glow skygaps / none,
islands on / off, island_after_lf on / off, chroma_clamp off.

Pass (tier 0): 0 differing values in the stage output. Otherwise the case is reported with its differing count, the 8-connected
groups and the largest |difference| (section 7.3's tier-1 facts), and --trace gives the first pass whose plane differs from the
classic's own intermediate. G2r (--fresh): the same case finished in a fresh process and in this long-running one; 0 differing.

    python -B tools/gate_g2.py --out <folder> [--mp 16] [--cases v4f,lead,...] [--table g1|all] [--trace] [--fresh]
Sizes and synthetic images only; below-normal priority; no thread count set."""
import argparse
import ast
import ctypes
import gc
import importlib
import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
U8 = np.arange(256, dtype=np.float32) / 255.0
V4F = dict(smooth=(0.2, 0.5), keep_blacks='render', lf='hybmin', clamp='agree5', glow='skygaps', islands=True,
           chroma_clamp=True, island_after_lf=True, fin_b0_hi=6.0)
CASES = {
    'v4f': dict(V4F),
    'v4f-protect': dict(V4F, protect=True),
    'v4f-protect-release': dict(V4F, protect=True, release=True),
    'lead': dict(V4F, clamp='lead'),
    'mm': dict(V4F, clamp='mm'),
    'hyb': dict(V4F, lf='hyb'),
    'pre_narrow': dict(V4F, keep_blacks='pre_narrow'),
    'no-glow': dict(V4F, glow=None),
    'no-islands': dict(V4F, islands=False),
    'islands-before-lf': dict(V4F, island_after_lf=False),
    'no-clamp-glow': dict(V4F, chroma_clamp=False),
    'lead-no-glow': dict(V4F, clamp='lead', glow=None),
    'b0-default': dict(V4F, fin_b0_hi=None),
}
TOE = (0.40, 0.06)


def load_pack():
    """The banded node pack, registered under a private name (relative imports need the parent in sys.modules)."""
    name = 'claude_banded_for_g2'
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, ROOT / 'node_pack' / 'claude_banded' / '__init__.py',
                                                  submodule_search_locations=[str(ROOT / 'node_pack' / 'claude_banded')])
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def bxf_module():
    pack = load_pack()
    return importlib.import_module(pack.__name__ + '.bxf.finish'), pack._engine


_V4 = None


def v4():
    global _V4
    if _V4 is None:
        spec = importlib.util.spec_from_file_location('cu_g2_classic_v4finish', ROOT / 'node_pack' / 'claude_creative' / 'v4finish.py')
        _V4 = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_V4)
    return _V4


def classic_function(name):
    src = (ROOT / 'node_pack' / 'claude_creative' / '__init__.py').read_text(encoding='utf8')
    fn = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == name)
    g = {'np': np, '__name__': 'cu_g2_classic_init'}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), 'claude_creative/__init__.py', 'exec'), g)
    return g[name]


# --- procedural scenes -----------------------------------------------------------------------------------------------------

def scene(h, w, f=2, seed=0):
    """(pre u8 [h, w, 3], creative, structure, init u8 [f h, f w, 3], protect, release float32 [h, w])."""
    from PIL import Image
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    img = np.zeros((h, w, 3), np.float32)
    img[...] = (0.55, 0.52, 0.50)
    sky = y < 0.26 * h
    img[sky] = np.stack([0.64 + 0.1 * (y[sky] / h), 0.74 + 0.08 * (y[sky] / h), 0.92 + 0.0 * y[sky]], -1)
    # canopy: dark green foliage hanging into the sky, with holes (sky gaps)
    edge = (np.sin(x / 23.0) * 0.5 + 0.5) * 0.10 * h + 0.16 * h
    canopy = (y > edge) & (y < 0.30 * h) & (np.sin(x / 5.0) * np.cos(y / 4.0) > -0.30) & (x > 0.5 * w)
    img[canopy] = (0.10, 0.22, 0.08)
    # buildings: hard-edged blocks of different tones (right half, middle band)
    for i in range(10):
        x0, y0 = int(rng.integers(int(0.5 * w), w - 30)), int(rng.integers(int(0.32 * h), int(0.62 * h)))
        bw, bh = int(rng.integers(15, w // 5)), int(rng.integers(15, h // 6))
        img[y0:y0 + bh, x0:x0 + bw] = rng.uniform(0.15, 0.85, 3) * np.array([1.0, 0.95, 0.9])
    # a flat plain wall (left, middle band), where the passes invent badges
    wall = (x > 0.04 * w) & (x < 0.46 * w) & (y > 0.31 * h) & (y < 0.62 * h)
    img[wall] = (0.56, 0.55, 0.53)
    # timber floor, low saturation: left curved grain (coherence about .7: a material, kept), right straight stripes
    # (coherence about .97: dropped by the median-coherence test)
    fl = y > 0.66 * h
    left = x < 0.5 * w
    g = np.where(left, 0.04 * np.sin(x / 2.0 + 1.2 * np.sin(y / 13.0)), 0.06 * np.sin(x / 2.0))
    img[fl] = np.stack([0.50 + g[fl], 0.47 + g[fl], 0.44 + g[fl]], -1)
    for i in range(70):                                    # tan litter on the kept half
        cy, cxx = int(rng.integers(int(0.70 * h), h - 6)), int(rng.integers(6, int(0.45 * w)))
        rr = int(rng.integers(2, 4))
        img[cy - rr:cy + rr, cxx - rr:cxx + rr] = (0.66, 0.50, 0.30) + rng.normal(0, 0.05, 3)
    # deep shadows
    img[(x > 0.62 * w) & (x < 0.72 * w) & (y > 0.45 * h)] *= 0.12
    other = ~(wall | sky | fl)
    img[other] += rng.normal(0, 0.006, img[other].shape).astype(np.float32)
    img[fl & left] += rng.normal(0, 0.010, img[fl & left].shape).astype(np.float32)
    img[fl & ~left] += rng.normal(0, 0.004, img[fl & ~left].shape).astype(np.float32)
    pre = np.clip(img * 255 + 0.5, 0, 255).astype(np.uint8)
    H, W = f * h, f * w
    up = np.asarray(Image.fromarray(pre).resize((W, H), Image.LANCZOS)).astype(np.float32) / 255
    Y_, X_ = np.mgrid[0:H, 0:W].astype(np.float32)
    tex = rng.normal(0, 0.035, (H, W, 1)).astype(np.float32) * (1 - np.clip(np.abs(up.mean(-1, keepdims=True) - 0.5) * 2, 0, 1))
    creative = up + tex + 0.01 * np.sin(X_ / 3.0)[..., None]
    structure = up + 0.4 * tex
    # invented badges on the plain wall, in both passes (hardware islands; red ones pass the colour filter)
    for i in range(36):
        cy, cxx = int(rng.integers(int(0.34 * H), int(0.59 * H))), int(rng.integers(int(0.07 * W), int(0.43 * W)))
        r = int(rng.integers(3, 6))
        col = (0.85, 0.08, 0.08) if i % 3 else (0.9, 0.9, 0.95)
        creative[cy - r:cy + r, cxx - r:cxx + r] = col
        structure[cy - r:cy + r, cxx - r:cxx + r] = col
    init = np.asarray(Image.fromarray(pre).resize((W, H), Image.BICUBIC)).astype(np.float32) / 255
    q = lambda a: np.clip(a * 255 + 0.5, 0, 255).astype(np.uint8)
    protect = ((x > 0.5 * w) & (x < 0.8 * w) & (y > 0.35 * h) & (y < 0.75 * h)).astype(np.float32)
    release = ((x > 0.6 * w) & (x < 0.68 * w) & (y > 0.45 * h) & (y < 0.65 * h)).astype(np.float32)
    return pre, q(creative), q(structure), q(init), protect, release


# --- the two finishes -------------------------------------------------------------------------------------------------------

def classic_chain(pre, creative, structure, init, protect, release, opts, out_size):
    """5.0.1's ClaudeV4Finish -> ClaudeShadowToe -> SaveImage on the same 8-bit inputs, then the stage crop."""
    V = v4()
    toe = classic_function('shadow_toe_u8')
    a = [U8[t][..., :3] for t in (creative, structure, init, pre)]
    a = [V.quantize_8bit(t) for t in a]
    g = None if opts.get('glow') in (None, 'none') else opts['glow']
    o = V.v4_finish(*a, protect if opts.get('protect') else None, smooth=opts['smooth'], protect_dilate=12, protect_feather=4.0,
                    islands=opts['islands'], chroma_clamp=opts['chroma_clamp'], keep_blacks=opts['keep_blacks'],
                    clamp=opts['clamp'], lf=opts['lf'], glow=g, fin_b0_hi=opts['fin_b0_hi'],
                    release=release if (opts.get('release') and opts.get('protect')) else None,
                    island_after_lf=bool(opts['island_after_lf']))
    o = V.to_u8(o).astype(np.float32) / 255.0
    u8 = np.clip(np.round(o * 255), 0, 255).astype(np.uint8)
    o2 = toe(u8, *TOE).astype(np.float32) / 255.0
    saved = np.clip(255. * o2, 0, 255).astype(np.uint8)
    ow, oh = out_size
    return np.ascontiguousarray(saved[:oh, :ow])


def bxf_chain(pre, creative, structure, init, protect, release, opts, out_size, work, table='g1', band_gb=2.0, keep=False,
              height=None):
    F, E = bxf_module()
    V = v4()
    toe = classic_function('shadow_toe_u8')
    g1 = E('bxf.g1')
    tab = g1.load() if table == 'g1' else g1.AllBanded() if table == 'all' else g1.AllWhole()
    planes = E('planes')
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    maps = {}
    for name, arr in (('creative', creative), ('structure', structure), ('init', init), ('pre', pre)):
        p = planes.from_array(work / f'{name}.plane', arr)
        maps[name] = p.map('r')
    b = F.BXF(V, toe, E, work / 'bxf', band_gb=band_gb, processes=1, table=tab, keep=keep, band_height=height)
    t0 = time.time()
    g = None if opts.get('glow') in (None, 'none') else opts['glow']
    res = b.finish(maps['creative'], maps['structure'], maps['init'], maps['pre'], protect if opts.get('protect') else None,
                   release if (opts.get('release') and opts.get('protect')) else None, smooth=opts['smooth'], protect_dilate=12,
                   protect_feather=4.0, islands=opts['islands'], chroma_clamp=opts['chroma_clamp'],
                   keep_blacks=opts['keep_blacks'], clamp=opts['clamp'], lf=opts['lf'], glow=g, fin_b0_hi=opts['fin_b0_hi'],
                   island_after_lf=bool(opts['island_after_lf']))
    ow, oh = out_size
    outp = planes.Plane.create(work / 'output.plane', (oh, ow, 3), 'u8', producer='gate G2')
    b.write_output(res, TOE[0], TOE[1], outp)
    outp.finish()
    secs = time.time() - t0
    got = outp.read_rows(0, oh)
    info = {'secs': round(secs, 1), 'workspace_peak_gb': round(b.ws.peak_bytes / 2 ** 30, 3),
            'passes': len(b.log), 'band_heights': sorted(set(x[2] for x in b.log if x[1] == 'banded')), 'whole_passes': sorted(set(n for n, mode, *_ in b.log if 'whole' in str(mode))),
            'table_applies': bool(getattr(tab, 'applies', False)), 'table_why_not': tab.why_not(), 'branches': dict(b.stats)}
    if keep:
        return got, info, b
    del res, maps
    b.close()
    return got, info, None


SCENE_KEYS = ('pre', 'creative', 'structure', 'init', 'protect', 'release')


def save_scene(folder, arrays):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for k, v in zip(SCENE_KEYS, arrays):
        np.save(folder / f'{k}.npy', v)


def peak_memory():
    """This process's peak commit (pagefile-backed private bytes) and peak working set, in GiB (Windows)."""
    class PMC(ctypes.Structure):
        _fields_ = [('cb', ctypes.c_ulong), ('PageFaultCount', ctypes.c_ulong), ('PeakWorkingSetSize', ctypes.c_size_t),
                    ('WorkingSetSize', ctypes.c_size_t), ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaPagedPoolUsage', ctypes.c_size_t), ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaNonPagedPoolUsage', ctypes.c_size_t), ('PagefileUsage', ctypes.c_size_t),
                    ('PeakPagefileUsage', ctypes.c_size_t), ('PrivateUsage', ctypes.c_size_t)]
    try:
        c = PMC()
        c.cb = ctypes.sizeof(PMC)
        k, ps = ctypes.windll.kernel32, ctypes.windll.psapi
        k.GetCurrentProcess.restype = ctypes.c_void_p
        ps.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(PMC), ctypes.c_ulong]
        if not ps.GetProcessMemoryInfo(k.GetCurrentProcess(), ctypes.byref(c), c.cb):
            return {'error': 'GetProcessMemoryInfo failed'}
        return {'peak_commit_gib': round(c.PeakPagefileUsage / 2 ** 30, 3), 'peak_working_set_gib': round(c.PeakWorkingSetSize / 2 ** 30, 3)}
    except Exception as e:
        return {'error': str(e)}


def compare(want, got):
    from scipy.ndimage import label
    d = want.astype(np.int16) - got.astype(np.int16)
    diff = np.any(d != 0, -1)
    n = int(np.count_nonzero(d))
    out = {'differing_values': n, 'total_values': int(want.size), 'max_abs': int(np.abs(d).max()) if n else 0}
    if n:
        lab, k = label(diff, structure=np.ones((3, 3), bool))
        sizes = np.bincount(lab.ravel())[1:]
        out.update(groups=int(k), largest_group_px=int(sizes.max()), first=[int(v) for v in np.argwhere(diff)[0]])
    return out


def run_case(name, opts, h, w, work, table, band_gb, trace=False, height=None):
    pre, cr, st, it, pm, rm = scene(h, w, 2, seed=h * 31 + w)
    size = (2 * w - 3, 2 * h - 5)                # a cropped stage output, as the service crops the padded stage
    t0 = time.time()
    want = classic_chain(pre, cr, st, it, pm, rm, opts, size)
    tc = time.time() - t0
    gc.collect()
    got, info, b = bxf_chain(pre, cr, st, it, pm, rm, opts, size, Path(work) / name, table, band_gb, keep=trace, height=height)
    rec = {'case': name, 'pre': [w, h], 'output': list(size), 'mp': round(size[0] * size[1] / 1e6, 2), 'classic_secs': round(tc, 1),
           'bxf': info, **compare(want, got)}
    rec['tier0'] = rec['differing_values'] == 0
    if trace and not rec['tier0']:
        rec['trace'] = phase_diff(b, pre, cr, st, it, pm, rm, opts)
    if b is not None:
        b.close()
    return rec


def phase_diff(b, pre, cr, st, it, pm, rm, opts):
    """The first scratch planes of the BXF that differ from the classic's own intermediates (a debugging aid)."""
    V = v4()
    T = U8
    S, B, I, P = (T[a].astype(np.float32) for a in (cr, st, it, pre))
    H, W = S.shape[:2]
    out = {}

    def chk(name, want):
        if name not in b.ws:
            out[name] = 'missing'
            return
        g = np.asarray(b.ws.get(name))
        want = np.asarray(want)
        if g.shape != want.shape:
            try:
                g = g.reshape(want.shape)
            except ValueError:
                out[name] = f'shape {g.shape} vs {want.shape}'
                return
        if g.dtype != want.dtype:
            out[name] = f'dtype {g.dtype} vs {want.dtype}'
            return
        u = f'u{want.itemsize}' if want.dtype.kind == 'f' else None
        n = int(np.count_nonzero(g.view(u) != want.view(u))) if u else int(np.count_nonzero(g != want))
        out[name] = n
    import torch
    pre_t = torch.from_numpy(P)
    m = V.v3g_map(pre_t, H, W, opts['smooth'])
    chk('map', m[None])
    if opts.get('protect'):
        m = m * (1 - V.protect_gate(pm, H, W, 12, 4.0, release=rm if opts.get('release') else None))
        chk('mm', m)
    ref = torch.nn.functional.interpolate(pre_t.permute(2, 0, 1)[None], size=(H, W), mode='bicubic', align_corners=False,
                                          antialias=False)[0].numpy()
    chk('ref', ref)
    from PIL import Image
    Q = np.asarray(Image.fromarray(pre).resize((W, H), Image.LANCZOS), dtype=np.float32) / 255
    chk('q8', np.asarray(Image.fromarray(pre).resize((W, H), Image.LANCZOS)))
    Yq = V.luma(Q)
    chk('lq', Yq)
    mix = (m[..., None] * S + (1 - m[..., None]) * B).astype(np.float32)
    chk('mix', mix)
    if opts['islands']:
        mixlf = V.lf_add(mix, ref.transpose(1, 2, 0), 0.0)
        chk('mixlf', mixlf)
    X = V.lf_hyb_min(mix, ref.transpose(1, 2, 0), 0.06) if opts['lf'] == 'hybmin' else V.lf_hyb(mix, ref.transpose(1, 2, 0), 0.06)
    chk('x', X)
    return out


def below_normal():
    """Lower this process to below-normal priority (Windows); True only when the call took effect."""
    try:
        k = ctypes.windll.kernel32
        k.GetCurrentProcess.restype = ctypes.c_void_p
        k.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        k.GetPriorityClass.argtypes = [ctypes.c_void_p]
        h = k.GetCurrentProcess()
        return bool(k.SetPriorityClass(h, 0x4000)) and k.GetPriorityClass(h) == 0x4000   # BELOW_NORMAL_PRIORITY_CLASS
    except Exception:
        return False


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--mp', type=float, default=16.0, help='stage output megapixels (pre is a quarter)')
    ap.add_argument('--cases', default=','.join(CASES))
    ap.add_argument('--table', default='g1', choices=('g1', 'all', 'whole'))
    ap.add_argument('--band-gb', type=float, default=2.0)
    ap.add_argument('--height', type=int, default=0, help='a registered band height for every banded pass (0: the budget picks)')
    ap.add_argument('--trace', action='store_true')
    ap.add_argument('--fresh', action='store_true', help='G2r: also finish the first case in a fresh process and compare')
    ap.add_argument('--child', default='')
    ap.add_argument('--what', default='bxf', choices=('bxf', 'classic'))
    ap.add_argument('--measure', action='store_true', help='peak memory of each finish alone, each in a fresh process')
    a = ap.parse_args(argv)
    pri = below_normal()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    side = int(round((a.mp * 1e6) ** 0.5 / 2))
    h, w = side - side % 4 + 3, side + side // 7          # odd, non-square pre sizes
    if a.child:                                          # a fresh process: one finish (G2r, and the memory measurement)
        opts = CASES[a.child]
        sc = out / 'scene'                                  # written by the parent: the child only maps it (no generation peak)
        pre, cr, st, it, pm, rm = (np.load(sc / f'{k}.npy', mmap_mode='r') for k in SCENE_KEYS)
        size = (2 * w - 3, 2 * h - 5)
        base = peak_memory()
        t0 = time.time()
        if a.what == 'classic':
            got, info = classic_chain(pre, cr, st, it, pm, rm, opts, size), {}
        else:
            got, info, _ = bxf_chain(pre, cr, st, it, pm, rm, opts, size, out / ('fresh-' + a.child), a.table, a.band_gb,
                                     height=a.height or None)
        rec = {'what': a.what, 'case': a.child, 'mp': round(size[0] * size[1] / 1e6, 2), 'secs': round(time.time() - t0, 1),
               'inputs_only': base, **peak_memory(), **({'workspace_peak_gb': info.get('workspace_peak_gb')} if info else {})}
        np.save(out / f'fresh-{a.what}-{a.child}.npy', got)
        (out / f'fresh-{a.what}-{a.child}.json').write_text(json.dumps(rec) + '\n', encoding='utf8')
        return
    log = out / 'g2-results.jsonl'
    recs = []
    for name in [c for c in a.cases.split(',') if c]:
        rec = run_case(name, CASES[name], h, w, out / 'work', a.table, a.band_gb, a.trace, a.height or None)
        rec['height'] = a.height or None
        rec['table'] = a.table
        rec['below_normal_priority'] = pri
        rec['band_gb'] = a.band_gb
        recs.append(rec)
        with open(log, 'a', encoding='utf8') as f:
            f.write(json.dumps(rec) + '\n')
        print(json.dumps({k: rec[k] for k in ('case', 'mp', 'differing_values', 'tier0')} | {'secs': rec['bxf']['secs']}), flush=True)
    if a.fresh or a.measure:
        save_scene(out / 'scene', scene(h, w, 2, seed=h * 31 + w))
    if a.fresh:
        name = [c for c in a.cases.split(',') if c][0]
        pre, cr, st, it, pm, rm = scene(h, w, 2, seed=h * 31 + w)
        size = (2 * w - 3, 2 * h - 5)
        # this process has run every case above (long-running); the child is fresh
        got, info, _ = bxf_chain(pre, cr, st, it, pm, rm, CASES[name], size, out / 'work' / ('long-' + name), a.table, a.band_gb,
                                 height=a.height or None)
        subprocess.run([sys.executable, '-B', str(Path(__file__).resolve()), '--out', str(out), '--mp', str(a.mp), '--table', a.table,
                        '--band-gb', str(a.band_gb), '--height', str(a.height), '--child', name, '--what', 'bxf'], check=True)
        fresh = np.load(out / f'fresh-bxf-{name}.npy')
        r = {'case': name, 'g2r': True, 'differing_values': int(np.count_nonzero(fresh != got)), 'mp': round(size[0] * size[1] / 1e6, 2),
             'fresh': json.loads((out / f'fresh-bxf-{name}.json').read_text(encoding='utf8'))}
        r['pass'] = r['differing_values'] == 0
        with open(log, 'a', encoding='utf8') as f:
            f.write(json.dumps(r) + '\n')
        print(json.dumps(r), flush=True)
    if a.measure:
        name = [c for c in a.cases.split(',') if c][0]
        m = {}
        for what in ('classic', 'bxf'):
            subprocess.run([sys.executable, '-B', str(Path(__file__).resolve()), '--out', str(out), '--mp', str(a.mp), '--table',
                            a.table, '--band-gb', str(a.band_gb), '--height', str(a.height), '--child', name, '--what', what], check=True)
            m[what] = json.loads((out / f'fresh-{what}-{name}.json').read_text(encoding='utf8'))
        a_ = np.load(out / f'fresh-classic-{name}.npy')
        b_ = np.load(out / f'fresh-bxf-{name}.npy')
        r = {'case': name, 'measure': m, 'differing_values': int(np.count_nonzero(a_ != b_))}
        with open(log, 'a', encoding='utf8') as f:
            f.write(json.dumps(r) + '\n')
        print(json.dumps(r), flush=True)
    return recs


if __name__ == '__main__':
    main()
