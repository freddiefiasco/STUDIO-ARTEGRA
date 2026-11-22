"""Gate G1u, the start-up self-probe of the banded exact finish on the person's own CPU (engine design 2.4, build item B18).

    python -I -B <engine>/bxf/selfprobe.py --out <file> --width <px> [--width <px>]... [--band-gb <GiB>]...
                                           [--seconds <limit>] [--site <dir>]... [--cap-gib <GiB>]

G1 classes each op of the finish on the CPU classes it ran on (engine/bxf/g1_table.py). On any other computer, or when the
libraries or the CPU capability change, the BXF cannot assume an op is band-invariant: this probe runs every op G1 classes
(every probe of tools/gate_g1.py but the process pool, under the same names; tests/worker/test_bxf_selfprobe.py checks the two
definitions give the same values) band against whole, bit for bit, through the BXF's own band executor on memory-mapped planes,
at exactly the shapes the finish will look up (plan(); fin-chk-1):
  - at 8,192 px and at every --width given: each finish stage's width of the plan (a stage of another width reads whole);
  - for each band budget given (--band-gb, the plan's; default every registered budget), at the band height the executor
    picks for each call of each pass at that width (engine/bxf/memory.lookups: its bytes per pixel and reach), with a plane of
    h + r rows, r in (1, 7): one join and a small last band of r rows plus the op's reach (the smallest band the executor hands
    an op, where libraries switch kernels by size); the stage output's ops at its 1,152-row bands; each whole-plane op (and
    each op the finish does not look up) at the smallest registered height.
No shape the executor will use is skipped, so whatever the table leaves whole is what the probe measured differing, or a width
or budget it was not asked about; engine/bxf/memory.whole_passes_for(table, ...) names it for the planner either way.
It writes a table in the g1_table format for this computer's environment (engine/bxf/g1.environment) to --out: an op that
differed at any shape, or failed, is classed 'whole' (whole-mapped, T7); an op clean at every shape it ran is 'banded' on the
domain of the shapes it ran (the reader covers a pass only inside it). g1.load(local=<file>) applies it: alone where no
committed table matches this environment, or on top of the one that does, where its 'whole' ops veto.

Bounded: each shape's memory follows the band height the executor itself picks at that budget (the table records the largest
shape's estimate, largest_shape_gib); with --cap-gib the probe refuses to start when that estimate and the probe process's own
commit (PROCESS_GIB; together cap_estimate_gib, also in the table) are over the cap (exit 3, no
table). The whole probe stops at --seconds: it then exits 2 and writes no table. Any other failure exits 3. Both print a plain
reason on stderr. On success it exits 0. --site adds package folders (the worker's site-packages) to the path, as the worker's
own launcher does; the probe sets no thread count and makes no CUDA call.

It runs by path: the block at the bottom loads this engine package by path as cu_banded_engine (as the node pack and the pool
child do) and calls main() of that package's copy of this module, whose own imports are relative. Synthetic images only."""
import json
import os
import sys
import time

WIDTHS = (8192,)
RESTS = (1, 7)
DEFAULT_SECONDS = 1800
DEFAULT_CAP_GIB = None                   # no cap: each shape is sized by the executor's own band height (see plan())
# one shape's synthetic planes (Data: u8, rgb, rgb2, L, L2, Y2, masks, lab, energy, f64) and their generator's temporaries,
# bytes per pixel (an estimate)
DATA_BPP = 96
PLAN_ROWS = 10 ** 6                      # a plane height for the lookups (the heights the executor picks do not depend on it)
# The probe process's own commit beside its shapes (the interpreter, torch, numpy, scipy and the classic finish module), which
# the shapes' estimate leaves out; the --cap-gib check counts it, so that a refusal is honest at any width. Wave 3 measured
# the probe's Job peak 2.23 and 0.69 GiB above its largest shape's estimate at the smallest shapes (fin3-g1u-base: 2.495 GiB
# against 0.27, 2.948 against 2.26; tests/fixtures/bxf_g1u_measured.json), and 2.6-4.2 GiB below it at 28,000 and 32,000 px
# (fin3-g1u). Raised from those figures, never lowered.
PROCESS_GIB = 2.5


# --- the classic code the probe calls (read by path, never patched) -----------------------------------------------------------

def classic(classic_dir):
    """(v4finish module, shadow_toe_u8) from node_pack/claude_creative, loaded by path."""
    import ast
    import importlib.util
    import numpy as np
    from pathlib import Path
    d = Path(classic_dir)
    spec = importlib.util.spec_from_file_location('cu_g1u_classic_v4finish', d / 'v4finish.py')
    V = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(V)
    src = (d / '__init__.py').read_text(encoding='utf8')
    fn = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == 'shadow_toe_u8')
    g = {'np': np, '__name__': 'cu_g1u_classic_init'}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), 'claude_creative/__init__.py', 'exec'), g)
    return V, g['shadow_toe_u8']


# --- synthetic planes (the same generator as tools/gate_g1.py Data) -----------------------------------------------------------

class Data:
    def __init__(self, V, T, W, seed=0):
        self.V, self.T, self.W, self.seed, self.d = V, T, W, seed, {}

    def _u8(self, k):
        import numpy as np
        T, W = self.T, self.W
        rng = np.random.default_rng(self.seed * 1000 + k)
        y = np.arange(T, dtype=np.float32)[:, None]
        x = np.arange(W, dtype=np.float32)[None, :]
        out = np.empty((T, W, 3), np.uint8)
        for c in range(3):
            base = 0.45 + 0.3 * np.sin(x / (173.0 + 31 * c + 7 * k) + y / 97.0) * np.cos(y / 251.0 - x / (389.0 + k))
            blocks = (((x // (211 + 13 * c)) + (y // (157 + 5 * k))) % 2).astype(np.float32) * 0.22
            sky = np.where(y < 0.18 * T, np.float32(0.35 + 0.03 * c), np.float32(0.0))
            v = base + blocks + sky + rng.random((T, W), dtype=np.float32) * np.float32(0.10 + 0.03 * k)
            v = np.where((x // 61 + y // 43) % 7 == 0, np.float32(0.02), v)
            out[..., c] = np.clip(v * 255.0, 0, 255).astype(np.uint8)
        return out

    def __getitem__(self, key):
        import numpy as np
        if key in self.d:
            return self.d[key]
        V = self.V
        U8 = np.arange(256, dtype=np.float32) / 255.0
        if key == 'u8':
            a = self._u8(1)
        elif key == 'rgb':
            a = U8[self['u8']]
        elif key == 'rgb2':
            a = U8[self._u8(2)]
        elif key == 'L':
            a = V.luma(self['rgb'])
        elif key == 'L2':
            a = V.luma(self['rgb2'])
        elif key == 'Y2':
            a = (self['L'] * np.float32(0.97) + np.float32(0.02)).astype(np.float32)
        elif key == 'mask':
            a = self['L'] > 0.6
        elif key == 'mask2':
            a = (self['L2'] > 0.72) & (self['L'] < 0.6)
        elif key == 'lab':
            a = V.rgb2lab(self['rgb'])
        elif key == 'energy':
            gy, gx = np.gradient(self['L'])
            a = np.sqrt(gx * gx + gy * gy)
        elif key == 'f64':
            a = self['L'].astype(np.float64)
        else:
            raise KeyError(key)
        self.d[key] = a
        return a


class Mapped:
    def __init__(self, data, folder):
        from pathlib import Path
        self.data, self.folder, self.m = data, Path(folder), {}
        self.folder.mkdir(parents=True, exist_ok=True)

    def __getitem__(self, key):
        import numpy as np
        if key not in self.m:
            a = np.ascontiguousarray(self.data[key])
            mm = np.memmap(self.folder / f'{key}.raw', dtype=a.dtype, mode='w+', shape=a.shape)
            mm[...] = a
            mm.flush()
            self.m[key] = mm
        return self.m[key]

    def close(self):
        import gc
        import shutil
        self.m.clear()
        gc.collect()
        shutil.rmtree(self.folder, ignore_errors=True)


def differing(a, b):
    """(differing bit patterns, differing values); -1 for a shape or dtype mismatch."""
    import numpy as np
    a, b = np.asarray(a), np.asarray(b)
    if a.shape != b.shape or a.dtype != b.dtype:
        return -1, -1
    if a.dtype.kind == 'f':
        u = f'u{a.itemsize}'
        return int(np.count_nonzero(a.view(u) != b.view(u))), int(np.count_nonzero(~((a == b) | (np.isnan(a) & np.isnan(b)))))
    n = int(np.count_nonzero(a != b))
    return n, n


def _outs(r):
    return list(r) if isinstance(r, (tuple, list)) else [r]


class Op:
    """One probe: kind 'local' (fn on band + reach rows against the whole call) or 'custom' (run(data, mdata, T, W, h, tmp)
    returns [(bits, values), ...])."""

    def __init__(self, name, cls, kind, fn=None, inputs=None, reach=0, bpp=40, run=None):
        self.name, self.cls, self.kind, self.fn, self.inputs, self.reach, self.bpp, self.run = name, cls, kind, fn, inputs, \
            int(reach), bpp, run


def r_gauss(s):
    return int(4.0 * float(s) + 0.5)


def ops(V, toe):
    """Every probe of tools/gate_g1.py but the process pool, under the same names, with the same calls."""
    import numpy as np
    import torch
    from scipy.ndimage import (gaussian_filter, maximum_filter, minimum_filter, binary_dilation, binary_erosion,
                               binary_opening)
    SIG = V.SIG
    P = []

    def add(*a, **k):
        P.append(Op(*a, **k))

    sig = sorted(set([0.8, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 6.0, 8.0, 12.0, 16.0] + [2 * s for s in SIG if 2 * s <= 8]
                     + [3 * s for s in SIG if 3 * s <= 8]))
    for s in sig:
        add(f'gaussian_filter s={s!r}', 'E1', 'local', lambda L, s=s: gaussian_filter(L, s), lambda d: [d['L']], r_gauss(s), 16)
    add('gaussian_filter hwc (1,1,0)', 'E1', 'local', lambda a: gaussian_filter(a, (1, 1, 0)), lambda d: [d['rgb']], 4, 30)
    add('gaussian_filter chanview s=2.0', 'E1', 'local', lambda a: gaussian_filter(a[..., 1], 2.0), lambda d: [d['rgb']], 8, 30)
    add('G lab[...,1:] s=2.0', 'E1', 'local', lambda a: V.G(a[..., 1:], 2.0), lambda d: [d['lab']], 8, 40)
    add('G lab[...,1:] s=1.0', 'E1', 'local', lambda a: V.G(a[..., 1:], 1.0), lambda d: [d['lab']], 4, 40)
    for n in (7, 11, 15, 31):
        add(f'maximum_filter {n}', 'E1', 'local', lambda L, n=n: maximum_filter(L, n), lambda d: [d['L']], n // 2, 16)
        add(f'minimum_filter {n}', 'E1', 'local', lambda L, n=n: minimum_filter(L, n), lambda d: [d['L']], n // 2, 16)
    add('maximum_filter chanview 11', 'E1', 'local', lambda a: maximum_filter(a[..., 1], 11) - minimum_filter(a[..., 1], 11),
        lambda d: [d['lab']], 5, 30)
    for k in (2, 3, 4, 5, 6, 12, 40):
        add(f'binary_dilation it={k}', 'E1', 'local', lambda m, k=k: binary_dilation(m, iterations=k), lambda d: [d['mask']], k, 8)
    add('binary_erosion it=2', 'E1', 'local', lambda m: binary_erosion(m, iterations=2), lambda d: [d['mask']], 2, 8)
    add('binary_opening it=40', 'E1', 'local', lambda m: binary_opening(m, iterations=40), lambda d: [d['mask']], 80, 8)
    add('np.gradient', 'E1', 'local', lambda L: tuple(np.gradient(L)), lambda d: [d['L']], 1, 24)
    add('np.hypot', 'E1', 'local', lambda a, b: np.hypot(a, b), lambda d: [d['L'], d['L2']], 0, 16)
    ew = {
        'ufunc exp f32': (lambda L: np.exp(-(L - 0.5) / 0.01), ['L']),
        'ufunc exp toe f32': (lambda L: L * (1 - 0.40 * np.exp(-L / 0.06)), ['L']),
        'ufunc tanh f32': (lambda L: 10.0 * np.tanh((L - 0.5) / 10.0) + 0.05 * np.tanh((L - 0.95) / 0.05), ['L']),
        'ufunc arctan2 f32': (lambda L, M: np.arctan2(L - 0.5, M - 0.5), ['L', 'L2']),
        'ufunc arctan2 chanview f32': (lambda a: np.arctan2(a[..., 2], a[..., 1]), ['lab']),
        'ufunc cos sin f32': (lambda L: (L * np.cos(L * 6.0), L * np.sin(L * 6.0)), ['L']),
        'ufunc cbrt f32': (lambda L: np.cbrt(L - 0.3), ['L']),
        'ufunc power 2.4 f32': (lambda a: ((np.clip(a, 0, 1) + 0.055) / 1.055) ** 2.4, ['rgb']),
        'ufunc power 1/2.4 f32': (lambda a: 1.055 * np.power(a, 1 / 2.4) - 0.055, ['rgb']),
        'ufunc power 3 f32': (lambda L: (L - 0.4) ** 3, ['L']),
        'ufunc square sqrt f32': (lambda L, M: np.sqrt(L * L + (M - 0.5) ** 2), ['L', 'L2']),
        'ufunc sign f32': (lambda L: np.sign(L - 0.5), ['L']),
        'ufunc remainder degrees f32': (lambda L, M: ((60 * (L - M) / np.maximum(L + M, 1e-6)) % 360,
                                                      np.degrees(L - M) % 360), ['L', 'L2']),
        'arith f32': (lambda a, L: ((L[..., None] * a + (1 - L[..., None]) * np.clip(a * 1.1 - 0.05, 0, 1)).astype(np.float32),
                                    np.where(L > 0.95, 0.95 + 0.05 * L, L) / np.maximum(L, 1e-4)), ['rgb', 'L']),
        'reduce channels f32': (lambda a: (a.max(-1) - a.min(-1), (a ** 2).sum(-1), np.sqrt(((a - 0.5) ** 2).sum(-1))), ['rgb']),
        'matmul 3x3 f32': (lambda a: a @ V._M.T / V._WP, ['rgb']),
    }
    for name, (fn, keys) in ew.items():
        add(name, 'E1', 'local', fn, lambda d, keys=keys: [d[k] for k in keys], 0, 40)
    add('v4.luma', 'E1', 'local', V.luma, lambda d: [d['rgb']], 0, 16)
    add('v4.rgb2lab', 'E1', 'local', V.rgb2lab, lambda d: [d['rgb']], 0, 80)
    add('v4.lab2rgb', 'E1', 'local', V.lab2rgb, lambda d: [d['lab']], 0, 80)
    add('v4.hsv', 'E1', 'local', lambda a: tuple(V.hsv(a)), lambda d: [d['rgb']], 0, 60)
    add('v4.warm_gate', 'E1', 'local', V.warm_gate, lambda d: [d['rgb']], 0, 60)
    add('v4.smooth01', 'E1', 'local', lambda L: V.smooth01((L - 0.45) / (0.75 - 0.45)), lambda d: [d['L']], 0, 16)
    add('v4.to_u8', 'E1', 'local', V.to_u8, lambda d: [d['rgb']], 0, 20)
    add('shadow_toe_u8', 'E1', 'local', lambda u: toe(u, 0.40, 0.06), lambda d: [d['u8']], 0, 40)
    add('v4.band_energy (1,6,4)', 'E1', 'local', lambda L: V.band_energy(L, 1.0, 6.0, 4.0), lambda d: [d['L']], 40, 24)
    for k in (0, 1):
        s = SIG[k]
        add(f'v4.locE k={k}', 'E1', 'local', lambda b, s=s: V.locE(b - 0.5, s), lambda d: [d['L']], r_gauss(2 * s), 24)
    add('v4.agreement', 'E1', 'local', V.agreement, lambda d: [d['rgb'], d['rgb2']], 40, 80)
    add('v4.fin_post srcwarm', 'E1', 'local',
        lambda D, Y, Yq, Y2, Q: V.fin_post(D, Y, Yq, Y2, None, antiring=None, keep_blacks=0.0, chroma='srcwarm', Q=Q,
                                           src=(2.0, 0.9, 1.05)),
        lambda d: [d['rgb'], d['L'], d['L2'], d['Y2'], d['rgb2']], 8, 260)
    add('v4.chroma_hc2 warm', 'E1', 'local', lambda O, Q: V.chroma_hc2(O, Q, warm=V.WARM), lambda d: [d['rgb'], d['rgb2']], 8, 260)
    add('v4.chroma_mm', 'E1', 'local', V.chroma_mm, lambda d: [d['rgb'], d['rgb2']], 40, 340)

    def t2(L):
        return torch.from_numpy(np.ascontiguousarray(L))[None, None]
    add('torch _blur s=4.0 (_sep conv)', 'E8', 'local', lambda L: V._blur(t2(L), 4.0)[0, 0].numpy(), lambda d: [d['L']], 14, 30)
    add('torch _blur s=6.0 (_sep conv)', 'E8', 'local', lambda L: V._blur(t2(L), 6.0)[0, 0].numpy(), lambda d: [d['L']], 21, 30)
    add('torch _sep s=1.5 gradient', 'E8', 'local',
        lambda L: V._sep(t2(L), V._gauss1d(1.5, 1), V._gauss1d(1.5))[0, 0].numpy(), lambda d: [d['L']], 6, 30)
    add('torch exp f32', 'E9', 'local', lambda L: torch.exp(-(t2(L) / 0.06) ** 2)[0, 0].numpy(), lambda d: [d['L']], 0, 24)

    def cl(a):
        return torch.from_numpy(a).permute(2, 0, 1)[None]
    add('torch pow 2.4 channels-last', 'E9', 'local',
        lambda a: torch.where(cl(a) <= 0.04045, cl(a) / 12.92, ((cl(a).clamp(0, 1) + 0.055) / 1.055) ** 2.4)[0].permute(1, 2, 0)
        .numpy(), lambda d: [d['rgb']], 0, 48)
    add('torch pow 1/2.4 channels-last', 'E9', 'local',
        lambda a: (1.055 * cl(a) ** (1 / 2.4) - 0.055)[0].permute(1, 2, 0).numpy(), lambda d: [d['rgb']], 0, 48)
    add('torch mean(1) of |r - x|', 'E9', 'local',
        lambda a, b: (cl(b).contiguous() - cl(a)).abs().mean(1, keepdim=True)[0, 0].numpy(), lambda d: [d['rgb'], d['rgb2']], 0, 48)
    add('torch exact ops', 'E9', 'local',
        lambda a, b: torch.clamp(cl(a) + 1.0 * ((cl(b).contiguous() - cl(a)) / torch.clamp(cl(b).contiguous(), min=1e-3)),
                                 0, 1)[0].permute(1, 2, 0).numpy(), lambda d: [d['rgb'], d['rgb2']], 0, 60)

    for n in (3, 7, 17, 49, 129):
        for key in ('L', 'f64'):
            add(f'E2 uniform_filter size={n} {"f32" if key == "L" else "f64"}', 'E2', 'custom', run=_e2(n, key), bpp=24)
    for r in V.R:
        add(f'E2 tbb r={r}', 'E2', 'custom', run=_tbb(V, r), bpp=24)
    for f in (2, 3, 4, 6, 8, 12, 18, 32, 48):
        add(f'E3 pool_mean f={f}', 'E3', 'custom', run=_pool(f), bpp=16)
    for s in sorted(set([2 * s for s in SIG if 2 * s > 8] + [3 * s for s in SIG if 3 * s > 8])):
        add(f'E3 g s={s!r}', 'E3', 'custom', run=_g(V, s), bpp=24)
    add('E4 zoom order=0 f64 out=mapped', 'E4', 'custom', run=_zoom0, bpp=24)
    add('E4 upsample_bilinear2d out=mapped', 'E4', 'custom', run=_ups('bilinear'), bpp=16)
    add('E4 upsample_bicubic2d out=mapped', 'E4', 'custom', run=_ups('bicubic'), bpp=40)
    add('E4 avg_pool2d of a mapped input', 'E4', 'custom', run=_avgpool, bpp=16)
    add('E4 reflection_pad2d out=mapped', 'E4', 'custom', run=_rpad, bpp=16)
    for e, lay in ((2.4, 'channels-last'), (2.4, 'contiguous'), (1 / 2.4, 'channels-last')):
        add(f'E9 torch pow {"2.4" if e == 2.4 else "1/2.4"} out=mapped {lay}', 'E9', 'custom', run=_powout(e, lay), bpp=40)
    add('E6 label out=mapped', 'E6', 'custom', run=_label, bpp=16)
    add('E6 bincount bands', 'E6', 'custom', run=_bincount, bpp=16)
    add('E6 keep table', 'E6', 'custom', run=_keep(V), bpp=24)
    for q in (98.5, 35, 75, 90, 99.9, 50, 0, 100):
        add(f'E5 percentile q={q}', 'E5', 'custom', run=_pct(q), bpp=12)
    add('E5 median', 'E5', 'custom', run=_med, bpp=12)
    add('E5 strided 4M sample', 'E5', 'custom', run=_strided, bpp=8)
    return P


def _e2(n, key):
    def run(data, mdata, T, W, h, tmp):
        import numpy as np
        from scipy.ndimage import uniform_filter
        from . import uniform as U
        want = uniform_filter(data[key], n, mode='reflect')
        dst = np.memmap(tmp / 'e2dst.raw', dtype=want.dtype, mode='w+', shape=want.shape)
        sc = np.memmap(tmp / 'e2tmp.raw', dtype=want.dtype, mode='w+', shape=want.shape)
        U.uniform_filter_planes(mdata[key], dst, n, sc, rows=h)
        return [differing(want, np.asarray(dst))]
    return run


def _tbb(V, r):
    def run(data, mdata, T, W, h, tmp):
        import numpy as np
        from . import uniform as U
        want = V.tbb(data['L'], r)
        dst = np.memmap(tmp / 'tbbdst.raw', dtype=np.float32, mode='w+', shape=want.shape)
        sc = np.memmap(tmp / 'tbbtmp.raw', dtype=np.float32, mode='w+', shape=want.shape)
        U.tbb_planes(mdata['L'], r, dst, sc)
        return [differing(want, np.asarray(dst))]
    return run


def _pool(f):
    def run(data, mdata, T, W, h, tmp):
        import numpy as np
        from . import pooling as Pm
        x = data['L']
        hh, ww = x.shape
        H, Wp = -(-hh // f) * f, -(-ww // f) * f
        want = np.pad(x, ((0, H - hh), (0, Wp - ww)), mode='edge').reshape(H // f, f, Wp // f, f).mean((1, 3))
        grid = np.memmap(tmp / 'grid.raw', dtype=np.float32, mode='w+', shape=want.shape)
        Pm.pool_mean_bands(mdata['L'], f, grid, h)
        return [differing(want, np.asarray(grid))]
    return run


def _g(V, s):
    def run(data, mdata, T, W, h, tmp):
        import numpy as np
        from . import pooling as Pm, work as Wk
        want = V.g(data['L'] - np.float32(0.5), s)
        ws = Wk.Workspace(tmp / 'g')
        x = ws.new('x', data['L'].shape)
        x[...] = data['L'] - np.float32(0.5)
        got = Pm.g_pooled(x, s, ws, 'z', h)
        r = differing(want, np.asarray(got).astype(np.float32))
        del got, x
        ws.close()
        return [r]
    return run


def _zoom0(data, mdata, T, W, h, tmp):
    import numpy as np
    from scipy.ndimage import zoom
    from . import pooling as Pm
    d = (data['f64'][::4, ::4] * 1000.0)
    fac = (T / d.shape[0], W / d.shape[1])
    want = zoom(d, fac, order=0)
    out = np.memmap(tmp / 'z0.raw', dtype=np.float64, mode='w+', shape=Pm.zoom_shape(d.shape, fac))
    zoom(d, fac, output=out, order=0)
    return [differing(want, np.asarray(out))]


def _ups(mode):
    def run(data, mdata, T, W, h, tmp):
        import numpy as np
        import torch
        import torch.nn.functional as F
        small = torch.from_numpy(np.ascontiguousarray(data['rgb'][::2, ::2])).permute(2, 0, 1)[None].contiguous()
        if mode == 'bilinear':
            small = small[:, :1]
        want = F.interpolate(small, size=(T, W), mode=mode, align_corners=False, **({'antialias': False} if mode == 'bicubic'
                                                                                    else {}))
        out = np.memmap(tmp / 'ups.raw', dtype=np.float32, mode='w+', shape=tuple(want.shape))
        fn = torch._C._nn.upsample_bilinear2d if mode == 'bilinear' else torch._C._nn.upsample_bicubic2d
        fn(small, (T, W), False, None, None, out=torch.from_numpy(out))
        return [differing(want.numpy(), np.asarray(out))]
    return run


def _powout(e, layout):
    def run(data, mdata, T, W, h, tmp):
        import numpy as np
        import torch
        a = np.clip(data['rgb'] * np.float32(1.02) - np.float32(0.01), 0, 1)
        if layout == 'channels-last':
            x = torch.from_numpy(a).permute(2, 0, 1)[None]
            out = np.memmap(tmp / 'pow.raw', dtype=np.float32, mode='w+', shape=a.shape)
            ot = torch.from_numpy(out).permute(2, 0, 1)[None]
        else:
            x = torch.from_numpy(np.ascontiguousarray(np.moveaxis(a, -1, 0)))[None]
            out = np.memmap(tmp / 'pow.raw', dtype=np.float32, mode='w+', shape=(3,) + a.shape[:2])
            ot = torch.from_numpy(out)[None]
        want = (x ** e)
        torch.pow(x, e, out=ot)
        return [differing(want.numpy(), ot.numpy())]
    return run


def _avgpool(data, mdata, T, W, h, tmp):
    import numpy as np
    import torch
    import torch.nn.functional as F
    a = torch.from_numpy(np.ascontiguousarray(data['L']))[None, None]
    b = torch.from_numpy(np.asarray(mdata['L']))[None, None]
    return [differing(F.avg_pool2d(a, f, ceil_mode=True).numpy(), F.avg_pool2d(b, f, ceil_mode=True).numpy()) for f in (3, 8)]


def _rpad(data, mdata, T, W, h, tmp):
    import numpy as np
    import torch
    import torch.nn.functional as F
    a = torch.from_numpy(np.ascontiguousarray(data['L']))[None, None]
    want = F.pad(a, (14, 14, 0, 0), mode='reflect')
    out = np.memmap(tmp / 'rpad.raw', dtype=np.float32, mode='w+', shape=tuple(want.shape))
    torch._C._nn.reflection_pad2d(torch.from_numpy(np.asarray(mdata['L']))[None, None], (14, 14, 0, 0), out=torch.from_numpy(out))
    return [differing(want.numpy(), np.asarray(out))]


def _label(data, mdata, T, W, h, tmp):
    import numpy as np
    from scipy.ndimage import label
    from . import components as C
    want, n = label(data['mask'])
    out = np.memmap(tmp / 'lab.raw', dtype=np.int32, mode='w+', shape=want.shape)
    n2 = C.label_into(mdata['mask'], out)
    return [differing(want, np.asarray(out)), (0 if n == n2 else 1, 0 if n == n2 else 1)]


def _bincount(data, mdata, T, W, h, tmp):
    import numpy as np
    from scipy.ndimage import label
    from . import components as C
    lab, n = label(data['mask'])
    want = np.bincount(lab.ravel())
    out = np.memmap(tmp / 'lab.raw', dtype=np.int32, mode='w+', shape=lab.shape)
    out[...] = lab
    got = C.bincount_bands(out, n, rows=h)
    return [differing(want, got), (0 if got.dtype == np.int64 else 1, 0)]


def _keep(V):
    def run(data, mdata, T, W, h, tmp):
        import numpy as np
        from . import components as C
        mask, L = data['mask2'], data['L']

        def keep(i, lab_, s, size):
            if not (20 <= size <= 20000):
                return False
            return float(L[s][lab_[s] == i].mean()) < 0.5
        want = V._components(mask, keep)
        lab = np.memmap(tmp / 'lab.raw', dtype=np.int32, mode='w+', shape=mask.shape)
        n = C.label_into(mdata['mask2'], lab)
        sizes = C.bincount_bands(lab, n, rows=h)
        sl = C.find_objects(lab, n)
        table = np.zeros(n + 1, bool)
        for i in range(1, n + 1):
            if sl[i - 1] is not None and keep(i, lab, sl[i - 1], sizes[i]):
                table[i] = True
        out = np.zeros(mask.shape, bool)
        C.apply_table(table, lab, out, rows=h)
        return [differing(want, out)]
    return run


def _pct(q):
    def run(data, mdata, T, W, h, tmp):
        import numpy as np
        from . import selection as S
        want = np.percentile(data['energy'], q)
        got = S.percentiles(S.band_chunks(mdata['energy'], h), [q])[0]
        return [differing(want, got), (0 if type(want) is type(got) else 1, 0)]
    return run


def _med(data, mdata, T, W, h, tmp):
    import numpy as np
    from . import selection as S
    want = np.median(data['energy'])
    got = S.median(S.band_chunks(mdata['energy'], h))
    want2 = np.median(data['L'][data['mask']])
    got2 = S.median(S.band_chunks(mdata['L'], h, mask=lambda y0, y1: np.asarray(mdata['mask'][y0:y1])))
    return [differing(want, got), differing(want2, got2), (0 if type(want) is type(got) else 1, 0)]


def _strided(data, mdata, T, W, h, tmp):
    import numpy as np
    import torch
    from . import selection as S
    flat = torch.from_numpy(np.ascontiguousarray(data['L']))[None, None].flatten()
    if flat.numel() > 4_000_000:
        flat = flat[:: flat.numel() // 4_000_000 + 1]
    return [differing(flat.numpy(), S.strided_sample(mdata['L']))]


# --- the run ---------------------------------------------------------------------------------------------------------------

class OutOfTime(Exception):
    pass


def run_op(p, data, mdata, T, W, h, tmp):
    """[(bits, values), ...] of one op at one shape (the band executor on mapped planes against the whole call)."""
    import numpy as np
    from . import local
    if p.kind == 'custom':
        return p.run(data, mdata, T, W, h, tmp)
    want = _outs(p.fn(*p.inputs(data)))
    got = [np.empty(np.asarray(w).shape, np.asarray(w).dtype) for w in want]
    local.run_bands(lambda *a: tuple(_outs(p.fn(*a))), p.inputs(mdata), got, h, p.reach)
    return [differing(w, g) for w, g in zip(want, got)]


class TooLarge(Exception):
    pass


def widths_of(widths):
    """The probe's widths: 8,192 px and every width given (an int or an iterable of ints)."""
    ws = [widths] if isinstance(widths, int) else list(widths)
    return sorted(set(WIDTHS) | {int(w) for w in ws})


def budgets_of(band_gb):
    """The band budgets the probe covers: those given (registered values only), or every registered budget."""
    from .. import bands
    if band_gb is None:
        return list(bands.BAND_BUDGETS_GB)
    bs = [band_gb] if isinstance(band_gb, (int, float)) else list(band_gb)
    return sorted({bands.check_band_budget(float(b)) for b in bs})


def plan(names, widths, band_gb=None, heights=None):
    """{(W, h): op names}: the shapes the probe runs (the module docstring). names: the probe's ops. heights: forced band
    heights (tests and gates, like the band executor's own height=): every op at each of them."""
    from .. import bands
    from . import memory
    names = set(names)
    h0 = min(bands.BAND_HEIGHTS)
    out = {}
    for W in widths_of(widths):
        if heights is not None:
            for h in heights:
                out.setdefault((W, bands.check_band_height(int(h))), set()).update(names)
            continue
        seen = set()
        for b in budgets_of(band_gb):
            for _, kind, ops_, geom, _ in memory.lookups((W, PLAN_ROWS), b):
                for op in ops_:
                    if op in names:
                        out.setdefault((W, h0 if kind == 'plane' else geom.h), set()).add(op)
                        seen.add(op)
        if names - seen:
            out.setdefault((W, h0), set()).update(names - seen)
    return out


def shapes(widths, band_gb=None, heights=None, names=()):
    """(W, h, rows, op names) of the probe: plan()'s shapes, each with h + r rows, r in RESTS."""
    return [(W, h, h + r, sorted(ns)) for (W, h), ns in sorted(plan(names, widths, band_gb, heights).items()) for r in RESTS]


def shape_gib(T, W, P):
    """The estimate of one shape's memory: its synthetic planes and, for the largest op, its whole call and the banded copy."""
    return (DATA_BPP + 2 * max((p.bpp for p in P), default=0)) * T * W / 2 ** 30


def largest_shape_gib(todo_shapes):
    """The largest shape's estimate (shape_gib) over (W, h, rows, ops) shapes; 0 for none."""
    return max((shape_gib(T, W, todo) for W, h, T, todo in todo_shapes), default=0.0)


def cap_estimate_gib(largest):
    """What the --cap-gib check compares with the cap: the largest shape's estimate and the probe process's own commit."""
    return PROCESS_GIB + float(largest)


def probe(width, tmp, seconds=DEFAULT_SECONDS, cap_gib=DEFAULT_CAP_GIB, classic_dir=None, extra_ops=(), only='',
          heights=None, band_gb=None):
    """Run the probe; returns the table (a dict in the g1_table format). width: the plan's stage widths (an int or several).
    band_gb: the plan's band budget(s) (default: every registered one). Raises OutOfTime past `seconds`, TooLarge when the
    largest shape's estimate and the process's own commit (cap_estimate_gib) are over cap_gib. extra_ops: more Op objects
    (tests inject a differing op this way)."""
    import gc
    import shutil
    from pathlib import Path
    from . import g1
    t0 = time.time()
    if classic_dir is None:
        classic_dir = Path(__file__).resolve().parents[2] / 'node_pack' / 'claude_creative'
    V, toe = classic(classic_dir)
    P = [p for p in ops(V, toe) if only in p.name] + list(extra_ops)
    by_name = {p.name: p for p in P}
    tmp = Path(tmp)
    todo_shapes = [(W, h, T, [by_name[n] for n in ns]) for W, h, T, ns in shapes(width, band_gb, heights, by_name)]
    largest = largest_shape_gib(todo_shapes)
    need = cap_estimate_gib(largest)
    if cap_gib is not None and need > float(cap_gib):
        W, h, T, _ = max(todo_shapes, key=lambda x: shape_gib(x[2], x[0], x[3]))
        raise TooLarge(f'the probe needs about {need:.1f} GiB at {W} px ({T} rows), over the cap of {float(cap_gib):g} GiB')
    recs = {p.name: {'cls': p.cls, 'kind': p.kind, 'reach': p.reach, 'tested': 0, 'errors': 0, 'differing': 0,
                     'clean': {}, 'first_difference': None} for p in P}
    try:
        for W, h, T, todo in todo_shapes:
            data = Data(V, T, W, seed=T * 7 + W)
            mdata = Mapped(data, tmp / f'm{T}x{W}')
            try:
                for p in todo:
                    if time.time() - t0 > seconds:
                        raise OutOfTime(f'the self-probe ran out of time after {int(time.time() - t0)} s (limit {int(seconds)} s)')
                    o = recs[p.name]
                    try:
                        res = run_op(p, data, mdata, T, W, h, tmp)
                        d = max((b if b >= 0 else 10 ** 12) for b, _ in res) if res else 0
                    except MemoryError:
                        o['errors'] += 1
                        continue
                    except Exception as e:                        # an op that cannot run banded here reads whole
                        o['errors'] += 1
                        o.setdefault('error', f'{type(e).__name__}: {e}'[:200])
                        continue
                    o['tested'] += 1
                    geom = g1.Geometry(T, W, h, p.reach) if p.kind == 'local' else g1.Geometry(T, W)
                    key, pt = g1.point(geom)
                    if d:
                        o['differing'] += 1
                        if o['first_difference'] is None:
                            o['first_difference'] = {'T': T, 'W': W, 'h': h, 'differing': d}
                    elif pt is not None:
                        o['clean'].setdefault(key, []).append(list(pt))
                    gc.collect()
            finally:
                mdata.close()
                del data
                gc.collect()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    out = {}
    for name, o in recs.items():
        clean = o.pop('clean')
        ok = o['tested'] > 0 and o['errors'] == 0 and o['differing'] == 0 and bool(clean)
        o['verdict'] = 'banded' if ok else 'whole'
        if ok:
            o['domain'] = {'key': 'height' if o['kind'] == 'local' else 'any',
                           'w_max': {k: max(p[0] for p in v) for k, v in sorted(clean.items())},
                           'frontier': {k: pareto(v) for k, v in sorted(clean.items())}}
        out[name] = o
    from .. import bands
    return {'gate': 'G1u', 'about': 'engine/bxf/selfprobe.py: every op band against whole at 8,192 px and the plan stage '
                                    'widths, at the band heights the executor picks for it at the given budgets '
                                    '(forced_heights: at those) with a 1- and a 7-row last band; an op that differed is whole',
            'environment': g1.environment(), 'band_heights': list(bands.BAND_HEIGHTS),
            'widths': widths_of(width), 'band_gb': budgets_of(band_gb),
            'forced_heights': None if heights is None else [int(h) for h in heights],
            'shapes': len(todo_shapes), 'largest_shape_gib': round(largest, 2), 'cap_estimate_gib': round(need, 2),
            'seconds': round(time.time() - t0, 1),
            'cap_gib': None if cap_gib is None else float(cap_gib), 'ops': dict(sorted(out.items()))}


def pareto(points):
    pts = sorted(set(tuple(p) for p in points))
    return [list(p) for p in pts if not any(q != p and q[0] <= p[0] and q[1] <= p[1] for q in pts)]


def write(table, path):
    from pathlib import Path
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_bytes((json.dumps(table, indent=1, sort_keys=True) + '\n').encode('utf8'))
    os.replace(tmp, path)


def main(argv=None):
    import argparse
    import tempfile
    from pathlib import Path
    ap = argparse.ArgumentParser(prog='selfprobe.py')
    ap.add_argument('--out', required=True)
    ap.add_argument('--width', action='append', required=True, help='a finish stage width of the plan (repeat, or a, b, ...)')
    ap.add_argument('--band-gb', type=float, action='append', default=None, help='the plan band budget (repeat; default all)')
    ap.add_argument('--seconds', type=float, default=DEFAULT_SECONDS)
    ap.add_argument('--cap-gib', type=float, default=DEFAULT_CAP_GIB)
    ap.add_argument('--site', action='append', default=[])
    ap.add_argument('--classic', default=None)
    ap.add_argument('--only', default='')
    a = ap.parse_args(argv)
    try:
        widths = [int(v) for w in a.width for v in str(w).split(',') if v.strip()]
    except ValueError:
        widths = []
    if not widths or min(widths) < 1:
        print('selfprobe: --width must be a positive number of pixels', file=sys.stderr)
        return 3
    try:
        budgets_of(a.band_gb)
    except (AssertionError, ValueError):
        print('selfprobe: --band-gb must be a registered band budget (2, 3 or 6 GiB)', file=sys.stderr)
        return 3
    try:
        with tempfile.TemporaryDirectory(prefix='cu-g1u-', ignore_cleanup_errors=True) as td:
            table = probe(widths, Path(td) / 'planes', a.seconds, a.cap_gib, a.classic, only=a.only, band_gb=a.band_gb)
        write(table, a.out)
    except OutOfTime as e:
        print(f'selfprobe: {e}; no table was written', file=sys.stderr)
        return 2
    except TooLarge as e:
        print(f'selfprobe: {e}; no table was written', file=sys.stderr)
        return 3
    except Exception as e:                                 # a plain reason, never a traceback for the service to parse
        print(f'selfprobe: the probe failed ({type(e).__name__}: {e}); no table was written', file=sys.stderr)
        return 3
    return 0


if __name__ == '__main__':
    def _bootstrap():
        import importlib
        import importlib.util
        from pathlib import Path
        argv = sys.argv[1:]
        for i, v in enumerate(argv):
            if v == '--site' and i + 1 < len(argv) and argv[i + 1] not in sys.path:
                sys.path.insert(0, argv[i + 1])
        eng = Path(__file__).resolve().parents[1]
        name = 'cu_banded_engine'
        if name not in sys.modules:
            spec = importlib.util.spec_from_file_location(name, eng / '__init__.py', submodule_search_locations=[str(eng)])
            mod = importlib.util.module_from_spec(spec)
            sys.modules[name] = mod
            spec.loader.exec_module(mod)
        return importlib.import_module(name + '.bxf.selfprobe').main(argv)
    sys.exit(_bootstrap())
