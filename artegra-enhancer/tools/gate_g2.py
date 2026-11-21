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

Pass (tier 0): 0 differing values in the stage output and, for the phase case of the run (--phase: by default its first case),
0 differing bit patterns in every float, bool and 8-bit scratch plane against the classic's own intermediate, with every
expected plane present (phase_compare; the 8-bit rounding can absorb a float difference, bxf-chk-1). Otherwise the case is
reported with its differing count, the 8-connected groups and the largest |difference| (section 7.3's tier-1 facts), and
--trace gives the planes that differ. G2r (--fresh): the same case finished in a fresh process and in this long-running one;
0 differing. A narrow, tall --pre (for example 300x3457: a 600 x 6,914 stage, a 2-row last band at every registered height)
stacks a base scene of its own width.

    python -B tools/gate_g2.py --out <folder> [--mp 16] [--pre WxH] [--cases v4f,lead,...] [--table g1|all] [--phase first|all|<case>]
                               [--trace] [--fresh] [--measure] [--no-branch-rule]
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

BASE = (503, 571)          # the pre size whose scene exercises every branch (sky connected to the top border in the top row)
BRANCHES = ('hw_kept', 'cf_kept', 'material_components', 'material_dropped', 'litter_kept', 'agree2_big', 'sky_kept',
            'sky_gaps_kept', 'gate_s_nonzero')


def scene(h, w, f=2, seed=0):
    """(pre u8 [h, w, 3], creative, structure, init u8 [f h, f w, 3], protect, release float32 [h, w]). Larger than BASE, the
    base scene is tiled (its features keep their pixel scale, so every branch fires at any size)."""
    if h <= BASE[0] and w <= BASE[1]:
        return scene_base(h, w, f, seed)
    bw = min(w, BASE[1])                            # a narrow, tall scene stacks a base scene of its own width (bxf-chk-1)
    b = scene_base(BASE[0], bw, f, seed)
    ny, nx = -(-h // BASE[0]), -(-w // bw)
    out = []
    for i, a in enumerate(b):
        k = 1 if i in (0, 4, 5) else f
        reps = (ny, nx) + ((1,) if a.ndim == 3 else ())
        t = np.ascontiguousarray(np.tile(a, reps)[:k * h, :k * w])
        if i < 4 and nx > 1:                        # a dark 3-px column (pre) every half tile keeps each tile's sky and gap
            for x0 in range(BASE[1] // 2, w, BASE[1] // 2):   # regions their own components (the gap test caps a gap at 200,000 px)
                t[:, k * x0:k * (x0 + 3)] = 20
        out.append(t)
    return tuple(out)


def scene_base(h, w, f=2, seed=0):
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
        bw, bh = int(rng.integers(15, max(16, w // 5))), int(rng.integers(15, h // 6))   # (the floor: scenes under 80 px wide)
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
        r = int(rng.integers(7, 11)) if i % 3 else int(rng.integers(3, 6))      # red badges large enough to pass the colour
        col = (0.85, 0.08, 0.08) if i % 3 else (0.9, 0.9, 0.95)                # filter, small near-neutral ones rejected
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
              height=None, after_pass=None):
    F, E = bxf_module()
    V = v4()
    toe = classic_function('shadow_toe_u8')
    g1 = E('bxf.g1')
    if not isinstance(table, str):
        tab = table                                     # tests: a table object (for example the committed table, bound)
    elif table not in ('g1', 'all', 'whole'):           # a table file (G1r: the table G1 just wrote on this node)
        data = json.loads(Path(table).read_text(encoding='utf8'))
        tab = g1.Table(data)                            # applies only where its environment is this process's
    else:
        tab = g1.load() if table == 'g1' else g1.AllBanded() if table == 'all' else g1.AllWhole()
    planes = E('planes')
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    maps = {}
    for name, arr in (('creative', creative), ('structure', structure), ('init', init), ('pre', pre)):
        p = planes.from_array(work / f'{name}.plane', arr)
        maps[name] = p.map('r')
    b = F.BXF(V, toe, E, work / 'bxf', band_gb=band_gb, processes=1, table=tab, keep=keep, band_height=height)
    b.after_pass = after_pass
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


def run_case(name, opts, h, w, work, table, band_gb, trace=False, height=None, phase=False, branch_rule=None):
    """One case. phase: keep every scratch plane and compare each with the classic's own intermediate (the float-plane
    rule: the case passes only if every compared plane is 0 and every expected plane exists). branch_rule: require every
    branch counter > 0 (default: for the case 'v4f')."""
    pre, cr, st, it, pm, rm = scene(h, w, 2, seed=h * 31 + w)
    size = (2 * w - 3, 2 * h - 5)                # a cropped stage output, as the service crops the padded stage
    t0 = time.time()
    want = classic_chain(pre, cr, st, it, pm, rm, opts, size)
    tc = time.time() - t0
    gc.collect()
    keep = bool(trace or phase)
    got, info, b = bxf_chain(pre, cr, st, it, pm, rm, opts, size, Path(work) / name, table, band_gb, keep=keep, height=height)
    rec = {'case': name, 'pre': [w, h], 'output': list(size), 'mp': round(size[0] * size[1] / 1e6, 2), 'classic_secs': round(tc, 1),
           'bxf': info, **compare(want, got)}
    rec['tier0'] = rec['differing_values'] == 0
    if (name == 'v4f') if branch_rule is None else branch_rule:
        br = info.get('branches', {})
        rec['branches_ok'] = all(bool(br.get(k)) for k in BRANCHES)
        rec['tier0'] = rec['tier0'] and rec['branches_ok']
    try:
        if phase or (trace and not rec['tier0']):
            del want, got
            gc.collect()
            t1 = time.time()
            rec['phase'] = phase_compare(b, pre, cr, st, it, pm, rm, opts)
            rec['phase']['secs'] = round(time.time() - t1, 1)
            if phase:
                rec['phase_ok'] = rec['phase']['ok']
                rec['tier0'] = rec['tier0'] and rec['phase_ok']
    finally:
        if b is not None:
            b.close()
    return rec


PHASE_REQUIRED = ('lf.dm', 'lf.w', 'lf.den', 'lf.add', 'lf.mul', 'x', 'fy', 'fy2', 'zone', 'post')


def phase_compare(b, pre, cr, st, it, pm, rm, opts):
    """Every kept scratch plane of a BXF run (BXF(keep=True)) against the classic's own intermediate, bit for bit: the classic
    v4_finish run step by step (its own calls, in its order, on the same 8-bit inputs). Returns {'planes': {name: differing
    bit patterns | 'missing' | a shape or dtype mismatch}, 'ok': every compared plane 0 and every expected plane present}.
    The planes of the low-frequency transfer (whose banded torch conv is the bxf-chk-1 case), the FIN core and post are
    always expected (PHASE_REQUIRED); the others as the options make them."""
    import torch
    from PIL import Image
    V = v4()
    T = U8
    out = {}

    def chk(name, want, alt=None):
        nm = name if name in b.ws else alt if (alt is not None and alt in b.ws) else None
        if nm is None:
            out[name] = 'missing'
            return
        g = np.asarray(b.ws.get(nm))
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
        out[name] = int(np.count_nonzero(g.view(u) != want.view(u))) if u else int(np.count_nonzero(g != want))

    S, B, I, P_ = [V._f32(V.quantize_8bit(T[a][..., :3]), k) for a, k in ((cr, 'creative'), (st, 'structure'), (it, 'init'),
                                                                          (pre, 'pre'))]
    H, W = S.shape[:2]
    pre_t = torch.from_numpy(P_)
    m = V.v3g_map(pre_t, H, W, (opts['smooth'][0], opts['smooth'][1]))
    chk('map', m[None])
    if opts.get('protect'):
        m = m * (1 - V.protect_gate(np.asarray(pm, np.float32), H, W, 12, 4.0,
                                    release=rm if opts.get('release') else None))
        chk('mm', m)
    reft = torch.nn.functional.interpolate(pre_t.permute(2, 0, 1)[None], size=(H, W), mode='bicubic', align_corners=False,
                                           antialias=False)[0]
    chk('ref', reft.numpy())
    ref = reft.permute(1, 2, 0).numpy()
    Q8 = np.asarray(Image.fromarray(np.clip(np.round(P_ * 255), 0, 255).astype(np.uint8)).resize((W, H), Image.LANCZOS))
    chk('q8', Q8)
    Q = np.asarray(Q8, dtype=np.float32) / 255
    del Q8
    chk('lq', V.luma(Q))
    gy, gx = np.gradient(V.tbb(V.luma(Q), 1))
    G = {'edge_p985': float(np.percentile(np.sqrt(gx * gx + gy * gy), 98.5))}
    del gx, gy
    mm = m.copy()
    mix = (mm[..., None] * S + (1 - mm[..., None]) * B).astype(np.float32)
    chk('mix', mix)
    del S, B
    w = None
    if opts['islands']:
        mixlf = V.lf_add(mix, ref, 0.0)
        chk('mixlf', mixlf)
        whw = V.hardware_islands(mixlf, Q, cmap=mm, edge_t=G['edge_p985'])
        chk('hw.w', whw)
        whw = V.colour_filter(whw, mixlf, Q)
        chk('cf.w', whw, alt='hw.w')                     # no colour-filter components: the BXF keeps the hardware plane
        chk('lt.m', V.material_mask(Q, mm, G)[0])
        w = np.maximum(whw, V.litter_islands(Q, mm, G))
        chk('wisl', w)
        del mixlf, whw
        if not opts['island_after_lf']:
            mix = (w[..., None] * I + (1 - w[..., None]) * mix).astype(np.float32)
            chk('mix2', mix)
    # the robust low-frequency transfer's own steps (lowfreq_transfer / lf_mul): d, its blurred channel mean, the weight, den
    x_t = torch.from_numpy(mix).permute(2, 0, 1)[None]
    r_t = torch.from_numpy(ref).permute(2, 0, 1)[None]
    dm = V._blur((r_t - x_t).abs().mean(1, keepdim=True), 4.0)
    chk('lf.dm', dm[0, 0].numpy())
    wgt = torch.exp(-(dm / 0.06) ** 2)
    chk('lf.w', wgt[0, 0].numpy())
    chk('lf.den', V._blur(wgt.expand(1, 3, H, W).reshape(3, 1, H, W), 32.0).reshape(1, 3, H, W)[0].numpy())
    del x_t, r_t, dm, wgt
    chk('lf.add', V.lf_add(mix, ref, 0.06))
    chk('lf.mul', V.lf_mul(mix, ref, 0.06))
    X = V.lf_hyb(mix, ref, 0.06) if opts['lf'] == 'hyb' else V.lf_hyb_min(mix, ref, 0.06)
    chk('x', X)
    del mix, ref
    if opts['islands'] and opts['island_after_lf']:
        X = (w[..., None] * I + (1 - w[..., None]) * X).astype(np.float32)
        chk('x2', X)
    del I, w
    finp = V.FINP if opts['fin_b0_hi'] is None else {**V.FINP, 'b0': (V.FINP['b0'][0], float(opts['fin_b0_hi']))}
    Y, Yq, Y2, zone = V.fin_core(X, Q, finp)
    chk('fy', Y)
    chk('fy2', Y2)
    chk('zone', zone)
    o = V.post(X, Y, Yq, Y2, zone, Q, ar='agree2', kb_pre='narrow' if opts['keep_blacks'] == 'pre_narrow' else False,
               chroma='srcwarm', ar_min=80)
    chk('post', o)
    del X, Y, Yq, Y2, zone
    glow = opts.get('glow') == 'skygaps'

    def sky_planes():
        sky = V.sky_mask(Q)
        if 'sk.m' in b.ws:
            chk('sk.m', sky)
        else:                                            # no sky candidate: the classic mask must be empty
            out['sk.m'] = int(np.count_nonzero(sky))
        chk('sg.gate', V.sky_gaps(Q, sky))
    if opts['chroma_clamp'] and opts['clamp'] == 'agree5':
        chk('pc', V.to_u8(o))
        res = np.empty((H, W, 3), np.float32)
        O = V.to_u8(o).astype(np.float32) / 255
        for y0 in range(0, H, 1024):
            a_, b_ = max(0, y0 - 64), min(H, y0 + 1024 + 64)
            r_ = V.clamp_r2(O[a_:b_], Q[a_:b_], mode='agree5')
            res[y0:min(H, y0 + 1024)] = r_[y0 - a_:y0 - a_ + min(1024, H - y0)]
        chk('res', res)
        del O
        if glow:
            sky_planes()
            chk('glow', V.csc_sky(res, Q, tol=0.03, dil=4, mode='gaps', rim=5)[0])
    else:
        if opts['chroma_clamp']:
            o = V.chroma_hc2(o, Q, warm=V.WARM) if opts['clamp'] == 'lead' else V.chroma_mm(V.to_u8(o).astype(np.float32) / 255, Q)
            chk('clamped', o)
        if glow:
            o8 = V.to_u8(o)
            chk('o8', o8)
            sky_planes()
            chk('glow', V.csc_sky(o8.astype(np.float32) / 255, Q, tol=0.03, dil=4, mode='gaps', rim=5)[0])
    bad = {k: v for k, v in out.items() if v != 0}
    return {'planes': out, 'compared': len(out), 'nonzero': bad,
            'ok': not bad and all(isinstance(out.get(k), int) for k in PHASE_REQUIRED)}


def self_cmd(*args):
    """This script in a fresh process of the same interpreter with this process's import path: the worker runtime runs
    python -I -S -B with its site-packages put on sys.path by a launcher, which a plain child would not see."""
    boot = ('import sys, runpy; sys.path[:0] = %r; sys.argv = %r; runpy.run_path(sys.argv[0], run_name="__main__")'
            % ([p for p in sys.path if p], [str(Path(__file__).resolve())] + [str(a) for a in args]))
    return [sys.executable, '-I', '-S', '-B', '-c', boot]


def head():
    """The commit of the code under test: git, or the COMMIT file of a frozen archive (a snapshot or a farm packet)."""
    r = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=str(ROOT), capture_output=True, text=True)
    if r.returncode == 0 and r.stdout.strip():
        return r.stdout.strip()
    f = ROOT / 'COMMIT'
    return f.read_text(encoding='utf8').strip() if f.exists() else ''


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
    ap.add_argument('--table', default='g1', help="g1 (the committed tables), all, whole, or a table JSON file")
    ap.add_argument('--band-gb', type=float, default=2.0)
    ap.add_argument('--height', type=int, default=0, help='a registered band height for every banded pass (0: the budget picks)')
    ap.add_argument('--trace', action='store_true')
    ap.add_argument('--fresh', action='store_true', help='G2r: also finish the first case in a fresh process and compare')
    ap.add_argument('--child', default='')
    ap.add_argument('--pre', default='', help='pre size WxH (overrides --mp)')
    ap.add_argument('--what', default='bxf', choices=('bxf', 'classic'))
    ap.add_argument('--measure', action='store_true', help='peak memory of each finish alone, each in a fresh process')
    ap.add_argument('--phase', default='first', help="the case whose float planes are compared with the classic's "
                                                       "intermediates (the registered rule: 'first', the run's first case; "
                                                       "'all'; a case name; 'none' only for debugging)")
    ap.add_argument('--work', default='', help='the folder for planes, scenes and fresh outputs (default: --out; a local disk '
                                               'when --out is on a network share)')
    ap.add_argument('--no-branch-rule', action='store_true', help="do not require every branch counter > 0 for 'v4f' (a scene "
                                                                  'too narrow to hold every branch)')
    a = ap.parse_args(argv)
    pri = below_normal()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    work = Path(a.work) if a.work else out
    work.mkdir(parents=True, exist_ok=True)
    side = int(round((a.mp * 1e6) ** 0.5 / 2))
    h, w = side - side % 4 + 3, side + side // 7          # odd, non-square pre sizes
    if a.pre:                                            # an explicit pre size W x H (a wide, short production-width scene)
        w, h = (int(v) for v in a.pre.lower().split('x'))
    if a.child:                                          # a fresh process: one finish (G2r, and the memory measurement)
        opts = CASES[a.child]
        sc = work / 'scene'                                  # written by the parent: the child only maps it (no generation peak)
        pre, cr, st, it, pm, rm = (np.load(sc / f'{k}.npy', mmap_mode='r') for k in SCENE_KEYS)
        size = (2 * w - 3, 2 * h - 5)
        base = peak_memory()
        t0 = time.time()
        if a.what == 'classic':
            got, info = classic_chain(pre, cr, st, it, pm, rm, opts, size), {}
        else:
            samples = []

            def after(name, samples=samples):
                pk = peak_memory().get('peak_commit_gib', 0)
                if not samples or pk > samples[-1][1] + 0.05:
                    samples.append((name, pk))
            got, info, _ = bxf_chain(pre, cr, st, it, pm, rm, opts, size, work / ('fresh-' + a.child), a.table, a.band_gb,
                                     height=a.height or None, after_pass=after)
            info['peak_rises'] = samples
        rec = {'what': a.what, 'case': a.child, 'mp': round(size[0] * size[1] / 1e6, 2), 'secs': round(time.time() - t0, 1),
               'inputs_only': base, **peak_memory(), **({'workspace_peak_gb': info.get('workspace_peak_gb'),
                                                          'peak_rises': info.get('peak_rises')} if info else {})}
        np.save(work / f'fresh-{a.what}-{a.child}.npy', got)
        (out / f'fresh-{a.what}-{a.child}.json').write_text(json.dumps(rec) + '\n', encoding='utf8')
        return
    log = out / 'g2-results.jsonl'
    recs = []
    names = [c for c in a.cases.split(',') if c]
    phased = set(names[:1]) if a.phase == 'first' else set(names) if a.phase == 'all' else set() if a.phase == 'none' \
        else {a.phase}
    if not phased <= set(names):
        raise SystemExit(f'--phase {a.phase}: not a case of this run')
    for name in names:
        rec = run_case(name, CASES[name], h, w, work / 'work', a.table, a.band_gb, a.trace, a.height or None, phase=name in phased,
                       branch_rule=False if a.no_branch_rule else None)
        rec['height'] = a.height or None
        rec['table'] = a.table
        rec['head'] = head()
        rec['below_normal_priority'] = pri
        rec['band_gb'] = a.band_gb
        recs.append(rec)
        with open(log, 'a', encoding='utf8') as f:
            f.write(json.dumps(rec) + '\n')
        print(json.dumps({k: rec[k] for k in ('case', 'mp', 'differing_values', 'tier0')} | {'secs': rec['bxf']['secs'],
                         'branches_ok': rec.get('branches_ok'), 'phase_ok': rec.get('phase_ok'),
                         'phase_nonzero': rec.get('phase', {}).get('nonzero'),
                         'whole_passes': len(rec['bxf'].get('whole_passes', []))}), flush=True)
    if a.fresh or a.measure:
        save_scene(work / 'scene', scene(h, w, 2, seed=h * 31 + w))
    if a.fresh:
        name = [c for c in a.cases.split(',') if c][0]
        pre, cr, st, it, pm, rm = scene(h, w, 2, seed=h * 31 + w)
        size = (2 * w - 3, 2 * h - 5)
        # this process has run every case above (long-running); the child is fresh
        got, info, _ = bxf_chain(pre, cr, st, it, pm, rm, CASES[name], size, work / 'work' / ('long-' + name), a.table, a.band_gb,
                                 height=a.height or None)
        subprocess.run(self_cmd('--out', out, '--mp', a.mp, '--table', a.table, '--band-gb', a.band_gb, '--height', a.height,
                                '--pre', a.pre, '--work', work, '--child', name, '--what', 'bxf'), check=True)
        fresh = np.load(work / f'fresh-bxf-{name}.npy')
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
            subprocess.run(self_cmd('--out', out, '--mp', a.mp, '--table', a.table, '--band-gb', a.band_gb, '--height', a.height,
                                    '--pre', a.pre, '--work', work, '--child', name, '--what', what), check=True)
            m[what] = json.loads((out / f'fresh-{what}-{name}.json').read_text(encoding='utf8'))
        a_ = np.load(work / f'fresh-classic-{name}.npy')
        b_ = np.load(work / f'fresh-bxf-{name}.npy')
        r = {'case': name, 'measure': m, 'differing_values': int(np.count_nonzero(a_ != b_))}
        with open(log, 'a', encoding='utf8') as f:
            f.write(json.dumps(r) + '\n')
        print(json.dumps(r), flush=True)
    return recs


if __name__ == '__main__':
    main()
