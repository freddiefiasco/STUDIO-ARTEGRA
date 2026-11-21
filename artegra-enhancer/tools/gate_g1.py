"""Gate G1: the op-classification probe of the banded exact finish (engine design ENGINE-DESIGN.md section 2.4, build item B1).

For every op of the product's V4F finish path and the creativity map, G1 compares the way the banded exact finish (BXF) calls
it with the classic call, bit for bit:
  - local ops (E1, numpy / scipy / torch): the classic call on the whole private array, against the SAME call made by the BXF's
    own band executor (engine/bxf/local.run_bands) on full-width bands of memory-mapped planes plus the op's reach in real rows,
    so the band slices carry the BXF's own alignment, strides and dtypes;
  - E2 (uniform_filter), E3 (pooled grids), E4 (whole calls with output= a mapped plane), E5 (exact streamed selection and
    numpy's own interpolation), E6 (label into a mapped plane, streamed bincount, keep tables) through the BXF's own modules;
  - pool ops at the registered process counts 2 and 4 against one process (the routed passes' own ops and params included).
Shapes: exactly the registered band heights {288, 576, 1152, 2304}, each as 2 h + r rows with r in {1, 7, h // 2 + 3} (the last
band is the remainder; 1 and 7 are the stress cases), at each probe's production widths up to 32,000 px (its production class)
and at NARROW_WIDTHS: from 128 px (the narrowest finish stage plan_banded can produce, a 64 px source at 2x) to 5,600 px, with
the same remainders, so the smallest band (1 row + reach) is measured at every width (bxf-chk-1); and, for every probe but the
pool, the registered targets' own finish planes (TARGET_PLANES: each plane's width with its own last band, H mod h, at every
height; production class, bxf-chk-4). A shape whose estimated memory is over --cap-gib is run as h + r rows (one join) or
skipped, and recorded. --shard i/n splits the probes across processes (merge their records before the summary).

Libraries pick kernels by size (torch's conv2d takes oneDNN only above 20,480 input elements), so a verdict holds only on the
band geometry measured. An op is 'banded' only if every production-class shape gave 0 differing values, at all four heights,
with no error, and no failing shape (of either class) is at least as large in width and in smallest band as a clean shape at the
same height; its domain is the frontier of its clean shapes (engine/bxf/g1.py covers a pass only inside it), so no measured
failure lies inside the domain. Anything else is 'whole' (the BXF runs the classic call whole on mapped planes, T7). The table
records the environment (torch, numpy, scipy, the CPU capability, numpy's SIMD features and the processor); the BXF applies
it only in the same environment (engine/bxf/g1.py).

--sweep runs every probe but the pool at shapes off this grid (SWEEP_*: widths, heights and remainders G1 does not use);
--sweep-check then reads them against the table: wherever the reader says banded, the shape must have given 0 differing values.

Run (Python with torch, numpy and scipy; it lowers its own priority; it never sets a thread count):
    python -B tools/gate_g1.py --out <folder> [--write] [--only <substring>] [--widths 7001,14000] [--quick]
    python -B tools/gate_g1.py --out <folder> --sweep          then  --sweep-check  (after the table is written)
Results stream to <folder>/g1-results.jsonl (a rerun resumes); --write upserts the table into engine/bxf/g1_table.py (TABLES: one
table per environment; the table of the same environment is replaced, the others kept) and tests/fixtures/bxf_g1_tables.json.
Sizes and synthetic images only."""
import argparse
import ast
import ctypes
import gc
import importlib
import importlib.util
import json
import math
import os
import shutil
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
HEIGHTS = (288, 576, 1152, 2304)
WIDTHS_ALL = (5600, 7000, 7001, 11200, 14000, 16800, 21000, 22400, 28000, 32000)
WIDTHS_CORE = (7001, 14000, 21000, 32000)
WIDTHS_COMPOSITE = (5600, 7001, 14000, 32000)
NARROW_WIDTHS = (128, 131, 197, 293, 437, 653, 977, 1459, 2183, 3271, 4903, 5600)
SWEEP_WIDTHS = (150, 400, 777, 1336, 1340, 2600, 6200)
SWEEP_HEIGHTS = (288, 576)
SWEEP_REMS = (1, 2, 5, 18, 19, 40)
# The registered targets (handover section 2 and the proof matrix: 4x, 6x and 8x of 3500 x 2188 and 2800 x 3500, and the
# 32,000 px outputs of 4000 x 2500 and 4000 x 4000 at 8x) and the finish planes (W, H) of their Large-image stages, from
# engine/banded_plan.stage_choice and engine/graph_banded.stage_sizes (tests/test_bxf_gates.py recomputes them). G1 runs every
# probe but the pool at each plane's own width with its own last band at every registered height (bxf-chk-4): 2 h + (H mod h)
# rows, so the smallest band is the target's own.
TARGET_SOURCES = ((3500, 2188, 4), (2800, 3500, 4), (3500, 2188, 6), (2800, 3500, 6), (3500, 2188, 8), (2800, 3500, 8),
                  (4000, 2500, 8), (4000, 4000, 8))
TARGET_PLANES = ((5600, 7008), (7000, 4376), (8000, 5008), (8000, 8000), (11200, 14000), (14000, 8752), (16000, 10000),
                 (16000, 16000), (16800, 21000), (21000, 13128), (22400, 28000), (28000, 17504), (32000, 20000),
                 (32000, 32000))


def remainders(h):
    return (1, 7, h // 2 + 3)


def target_shapes(heights=HEIGHTS):
    """(W, h, rem) of every registered target's finish plane at every registered band height (H mod h is its last band)."""
    return sorted({(W, h, H % h) for W, H in TARGET_PLANES for h in heights})


def runs_at(p, W):
    """A probe runs at its own production widths and at every narrow width (the process pool too, since 5.0.2's second
    build wave routes it into the passes)."""
    return W in p.widths or W in NARROW_WIDTHS


def shard_of(P, shard):
    """The probes of shard 'i/n' (every n-th probe from the i-th; '' = all): shards run in separate processes and their
    records are merged before the summary (pixel-neutral; the records are the same)."""
    if not shard:
        return P
    i, n = (int(v) for v in shard.split('/'))
    if not 0 <= i < n:
        raise SystemExit(f'--shard {shard}: want i/n with 0 <= i < n')
    return [p for k, p in enumerate(P) if k % n == i]


# --- code under test, loaded as the worker loads it ------------------------------------------------------------------------

def engine(name):
    pkg = 'cu_banded_engine'
    if pkg not in sys.modules:
        spec = importlib.util.spec_from_file_location(pkg, ROOT / 'engine' / '__init__.py',
                                                      submodule_search_locations=[str(ROOT / 'engine')])
        mod = importlib.util.module_from_spec(spec)
        sys.modules[pkg] = mod
        spec.loader.exec_module(mod)
    return importlib.import_module(f'{pkg}.{name}')


_V4 = None


def v4():
    """The classic node_pack/claude_creative/v4finish.py, loaded by path (read, never patched)."""
    global _V4
    if _V4 is None:
        spec = importlib.util.spec_from_file_location('cu_g1_classic_v4finish',
                                                      ROOT / 'node_pack' / 'claude_creative' / 'v4finish.py')
        _V4 = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_V4)
    return _V4


def classic_function(name):
    """A top-level function of node_pack/claude_creative/__init__.py, compiled on its own."""
    src = (ROOT / 'node_pack' / 'claude_creative' / '__init__.py').read_text(encoding='utf8')
    fn = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == name)
    g = {'np': np, '__name__': 'cu_g1_classic_init'}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), 'claude_creative/__init__.py', 'exec'), g)
    return g[name]


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


# --- synthetic planes --------------------------------------------------------------------------------------------------------

U8 = np.arange(256, dtype=np.float32) / 255.0


class Data:
    """Deterministic synthetic planes of T x W (lazily made): rgb / rgb2 (8-bit-derived float32, like the decoded passes and
    Q), their luma, masks, a Lab image, a non-negative 'energy' plane and an 8-bit image."""

    def __init__(self, T, W, seed=0):
        self.T, self.W, self.seed = T, W, seed
        self.d = {}

    def _u8(self, k):
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
            v = np.where((x // 61 + y // 43) % 7 == 0, np.float32(0.02), v)        # dark islands
            out[..., c] = np.clip(v * 255.0, 0, 255).astype(np.uint8)
        return out

    def __getitem__(self, key):
        if key in self.d:
            return self.d[key]
        V = v4()
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
    """Memory-mapped copies of a Data's planes (the BXF reads its planes through maps)."""

    def __init__(self, data, folder):
        self.data, self.folder, self.m = data, Path(folder), {}
        self.folder.mkdir(parents=True, exist_ok=True)

    def __getitem__(self, key):
        if key not in self.m:
            a = np.ascontiguousarray(self.data[key])
            mm = np.memmap(self.folder / f'{key}.raw', dtype=a.dtype, mode='w+', shape=a.shape)
            mm[...] = a
            mm.flush()
            self.m[key] = mm
        return self.m[key]

    def close(self):
        self.m.clear()
        gc.collect()
        shutil.rmtree(self.folder, ignore_errors=True)


# --- comparison --------------------------------------------------------------------------------------------------------------

def differing(a, b):
    """(differing bit patterns, differing values) between two arrays (or scalars); -1 for a shape or dtype mismatch."""
    a, b = np.asarray(a), np.asarray(b)
    if a.shape != b.shape or a.dtype != b.dtype:
        return -1, -1
    if a.dtype.kind == 'f':
        u = f'u{a.itemsize}'
        bits = int(np.count_nonzero(a.view(u) != b.view(u)))
        vals = int(np.count_nonzero(~((a == b) | (np.isnan(a) & np.isnan(b)))))
        return bits, vals
    n = int(np.count_nonzero(a != b))
    return n, n


def _outs(r):
    if isinstance(r, (tuple, list)):
        return list(r)
    return [r]


# --- probes --------------------------------------------------------------------------------------------------------------

class Probe:
    def __init__(self, name, cls, kind, fn=None, inputs=None, reach=0, bpp=40, widths=WIDTHS_CORE, run=None, note='',
                 only_rem=None):
        self.name, self.cls, self.kind, self.fn, self.inputs, self.reach = name, cls, kind, fn, inputs, int(reach)
        self.bpp, self.widths, self.run, self.note, self.only_rem = bpp, widths, run, note, only_rem


def r_gauss(s):
    return int(4.0 * float(s) + 0.5)


def probes():
    import torch
    from scipy.ndimage import (gaussian_filter, maximum_filter, minimum_filter, binary_dilation, binary_erosion,
                               binary_opening, uniform_filter, label, zoom)
    V = v4()
    SIG = V.SIG
    toe = classic_function('shadow_toe_u8')
    loc = engine('bxf.local')
    P = []

    def add(*a, **k):
        P.append(Probe(*a, **k))

    # E1: scipy filters at every sigma / size / iteration count the V4F path uses
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
    add('np.hypot', 'E1', 'local', lambda a, b: np.hypot(a, b), lambda d: [d['L'], d['L2']], 0, 16, WIDTHS_ALL)

    # E1: numpy element-wise, contiguous and on channel views, with the classic's scalar kinds
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
        add(name, 'E1', 'local', fn, lambda d, keys=keys: [d[k] for k in keys], 0, 40, WIDTHS_ALL)

    # E1: the classic's own functions, as the BXF calls them on bands
    add('v4.luma', 'E1', 'local', V.luma, lambda d: [d['rgb']], 0, 16, WIDTHS_ALL)
    add('v4.rgb2lab', 'E1', 'local', V.rgb2lab, lambda d: [d['rgb']], 0, 80, WIDTHS_ALL)
    add('v4.lab2rgb', 'E1', 'local', V.lab2rgb, lambda d: [d['lab']], 0, 80, WIDTHS_ALL)
    add('v4.hsv', 'E1', 'local', lambda a: tuple(V.hsv(a)), lambda d: [d['rgb']], 0, 60, WIDTHS_ALL)
    add('v4.warm_gate', 'E1', 'local', V.warm_gate, lambda d: [d['rgb']], 0, 60, WIDTHS_ALL)
    add('v4.smooth01', 'E1', 'local', lambda L: V.smooth01((L - 0.45) / (0.75 - 0.45)), lambda d: [d['L']], 0, 16, WIDTHS_ALL)
    add('v4.to_u8', 'E1', 'local', V.to_u8, lambda d: [d['rgb']], 0, 20, WIDTHS_ALL)
    add('shadow_toe_u8', 'E1', 'local', lambda u: toe(u, 0.40, 0.06), lambda d: [d['u8']], 0, 40, WIDTHS_ALL)
    add('v4.band_energy (1,6,4)', 'E1', 'local', lambda L: V.band_energy(L, 1.0, 6.0, 4.0), lambda d: [d['L']], 40, 24)
    for k in (0, 1):
        s = SIG[k]
        add(f'v4.locE k={k}', 'E1', 'local', lambda b, s=s: V.locE(b - 0.5, s), lambda d: [d['L']], r_gauss(2 * s), 24)
    add('v4.agreement', 'E1', 'local', V.agreement, lambda d: [d['rgb'], d['rgb2']], 40, 80, WIDTHS_COMPOSITE)
    add('v4.fin_post srcwarm', 'E1', 'local',
        lambda D, Y, Yq, Y2, Q: V.fin_post(D, Y, Yq, Y2, None, antiring=None, keep_blacks=0.0, chroma='srcwarm', Q=Q,
                                           src=(2.0, 0.9, 1.05)),
        lambda d: [d['rgb'], d['L'], d['L2'], d['Y2'], d['rgb2']], 8, 260, WIDTHS_COMPOSITE)
    add('v4.chroma_hc2 warm', 'E1', 'local', lambda O, Q: V.chroma_hc2(O, Q, warm=V.WARM), lambda d: [d['rgb'], d['rgb2']], 8,
        260, WIDTHS_COMPOSITE)
    add('v4.chroma_mm', 'E1', 'local', V.chroma_mm, lambda d: [d['rgb'], d['rgb2']], 40, 340, WIDTHS_COMPOSITE)

    # torch on the CPU (E8 / E9): banded against whole; the BXF bands only what reads 0 here
    def t2(L):
        return torch.from_numpy(np.ascontiguousarray(L))[None, None]
    add('torch _blur s=4.0 (_sep conv)', 'E8', 'local', lambda L: V._blur(t2(L), 4.0)[0, 0].numpy(), lambda d: [d['L']], 14, 30)
    add('torch _blur s=6.0 (_sep conv)', 'E8', 'local', lambda L: V._blur(t2(L), 6.0)[0, 0].numpy(), lambda d: [d['L']], 21, 30)
    add('torch _sep s=1.5 gradient', 'E8', 'local',
        lambda L: V._sep(t2(L), V._gauss1d(1.5, 1), V._gauss1d(1.5))[0, 0].numpy(), lambda d: [d['L']], 6, 30)
    add('torch exp f32', 'E9', 'local', lambda L: torch.exp(-(t2(L) / 0.06) ** 2)[0, 0].numpy(), lambda d: [d['L']], 0, 24,
        WIDTHS_ALL)

    def cl(a):
        return torch.from_numpy(a).permute(2, 0, 1)[None]
    add('torch pow 2.4 channels-last', 'E9', 'local',
        lambda a: torch.where(cl(a) <= 0.04045, cl(a) / 12.92, ((cl(a).clamp(0, 1) + 0.055) / 1.055) ** 2.4)[0].permute(1, 2, 0)
        .numpy(), lambda d: [d['rgb']], 0, 48, WIDTHS_ALL)
    add('torch pow 1/2.4 channels-last', 'E9', 'local',
        lambda a: (1.055 * cl(a) ** (1 / 2.4) - 0.055)[0].permute(1, 2, 0).numpy(), lambda d: [d['rgb']], 0, 48, WIDTHS_ALL)
    add('torch mean(1) of |r - x|', 'E9', 'local',
        lambda a, b: (cl(b).contiguous() - cl(a)).abs().mean(1, keepdim=True)[0, 0].numpy(), lambda d: [d['rgb'], d['rgb2']],
        0, 48, WIDTHS_ALL)
    add('torch exact ops', 'E9', 'local',
        lambda a, b: torch.clamp(cl(a) + 1.0 * ((cl(b).contiguous() - cl(a)) / torch.clamp(cl(b).contiguous(), min=1e-3)),
                                 0, 1)[0].permute(1, 2, 0).numpy(), lambda d: [d['rgb'], d['rgb2']], 0, 60, WIDTHS_ALL)

    # E2, E3, E4, E5, E6 and the pool, through the BXF's own modules
    for n in (3, 7, 17, 49, 129):
        for key in ('L', 'f64'):
            add(f'E2 uniform_filter size={n} {"f32" if key == "L" else "f64"}', 'E2', 'custom', run=_e2(n, key), bpp=24)
    for r in V.R:
        add(f'E2 tbb r={r}', 'E2', 'custom', run=_tbb(r), bpp=24)
    for f in (2, 3, 4, 6, 8, 12, 18, 32, 48):
        add(f'E3 pool_mean f={f}', 'E3', 'custom', run=_pool(f), bpp=16)
    gs = sorted(set([2 * s for s in SIG if 2 * s > 8] + [3 * s for s in SIG if 3 * s > 8]))
    for s in gs:
        add(f'E3 g s={s!r}', 'E3', 'custom', run=_g(s), bpp=24)
    add('E4 zoom order=0 f64 out=mapped', 'E4', 'custom', run=_zoom0, bpp=24, only_rem=7)
    add('E4 upsample_bilinear2d out=mapped', 'E4', 'custom', run=_ups('bilinear'), bpp=16, only_rem=7)
    add('E4 upsample_bicubic2d out=mapped', 'E4', 'custom', run=_ups('bicubic'), bpp=40, only_rem=7)
    add('E4 avg_pool2d of a mapped input', 'E4', 'custom', run=_avgpool, bpp=16, only_rem=7)
    add('E4 reflection_pad2d out=mapped', 'E4', 'custom', run=_rpad, bpp=16, only_rem=7)
    for e, lay in ((2.4, 'channels-last'), (2.4, 'contiguous'), (1 / 2.4, 'channels-last')):
        add(f'E9 torch pow {"2.4" if e == 2.4 else "1/2.4"} out=mapped {lay}', 'E9', 'custom', run=_powout(e, lay), bpp=40,
            only_rem=7)
    add('E6 label out=mapped', 'E6', 'custom', run=_label, bpp=16)
    add('E6 bincount bands', 'E6', 'custom', run=_bincount, bpp=16)
    add('E6 keep table', 'E6', 'custom', run=_keep, bpp=24, only_rem=7)
    for q in (98.5, 35, 75, 90, 99.9, 50, 0, 100):
        add(f'E5 percentile q={q}', 'E5', 'custom', run=_pct(q), bpp=12)
    add('E5 median', 'E5', 'custom', run=_med, bpp=12)
    add('E5 strided 4M sample', 'E5', 'custom', run=_strided, bpp=8, only_rem=7)
    for op, params, reach in (('gaussian_filter', {'sigma': 4.0}, 16), ('maximum_filter', {'size': 15}, 7),
                              ('binary_dilation', {'iterations': 5}, 5), ('gradient_mag', {}, 1)):
        for n in (2, 4):
            add(f'pool {op} n={n}', 'pool', 'custom', run=_poolrun(op, params, reach, n), bpp=24, widths=(7001, 14000),
                only_rem=7)
    # the passes the BXF routes into the pool (node_pack/claude_banded/bxf/finish.py POOL_ROUTES): the FIN core's gain blur
    # g(gc, beta * SIG[0]) (a gaussian_filter at s <= 8) and the edge zone's gradient magnitude; probed with their own params
    s0 = float(V.DEF['beta'] * SIG[0])
    for n in (2, 4):
        add(f'pool gaussian_filter s={s0!r} n={n}', 'pool', 'custom', run=_poolrun('gaussian_filter', {'sigma': s0},
                                                                                   r_gauss(s0), n),
            bpp=24, widths=(7001, 14000), only_rem=7)
    return P


def _e2(n, key):
    def run(data, mdata, T, W, h, tmp):
        from scipy.ndimage import uniform_filter
        U = engine('bxf.uniform')
        want = uniform_filter(data[key], n, mode='reflect')
        src = mdata[key]
        dst = np.memmap(tmp / 'e2dst.raw', dtype=want.dtype, mode='w+', shape=want.shape)
        sc = np.memmap(tmp / 'e2tmp.raw', dtype=want.dtype, mode='w+', shape=want.shape)
        U.uniform_filter_planes(src, dst, n, sc, rows=h)
        return [differing(want, np.asarray(dst))]
    return run


def _tbb(r):
    def run(data, mdata, T, W, h, tmp):
        U = engine('bxf.uniform')
        want = v4().tbb(data['L'], r)
        dst = np.memmap(tmp / 'tbbdst.raw', dtype=np.float32, mode='w+', shape=want.shape)
        sc = np.memmap(tmp / 'tbbtmp.raw', dtype=np.float32, mode='w+', shape=want.shape)
        U.tbb_planes(mdata['L'], r, dst, sc)
        return [differing(want, np.asarray(dst))]
    return run


def _pool(f):
    def run(data, mdata, T, W, h, tmp):
        Pm = engine('bxf.pooling')
        x = data['L']
        hh, ww = x.shape
        H, Wp = -(-hh // f) * f, -(-ww // f) * f
        want = np.pad(x, ((0, H - hh), (0, Wp - ww)), mode='edge').reshape(H // f, f, Wp // f, f).mean((1, 3))
        grid = np.memmap(tmp / 'grid.raw', dtype=np.float32, mode='w+', shape=want.shape)
        Pm.pool_mean_bands(mdata['L'], f, grid, h)
        return [differing(want, np.asarray(grid))]
    return run


def _g(s):
    def run(data, mdata, T, W, h, tmp):
        Pm, Wk = engine('bxf.pooling'), engine('bxf.work')
        want = v4().g(data['L'] - np.float32(0.5), s)
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
    from scipy.ndimage import zoom
    Pm = engine('bxf.pooling')
    d = (data['f64'][::4, ::4] * 1000.0)
    fac = (T / d.shape[0], W / d.shape[1])
    want = zoom(d, fac, order=0)
    out = np.memmap(tmp / 'z0.raw', dtype=np.float64, mode='w+', shape=Pm.zoom_shape(d.shape, fac))
    zoom(d, fac, output=out, order=0)
    return [differing(want, np.asarray(out))]


def _ups(mode):
    def run(data, mdata, T, W, h, tmp):
        import torch
        import torch.nn.functional as F
        small = torch.from_numpy(np.ascontiguousarray(data['rgb'][::2, ::2])).permute(2, 0, 1)[None].contiguous()
        if mode == 'bilinear':
            small = small[:, :1]
        want = F.interpolate(small, size=(T, W), mode=mode, align_corners=False, **({'antialias': False} if mode == 'bicubic'
                                                                                    else {}))
        out = np.memmap(tmp / 'ups.raw', dtype=np.float32, mode='w+', shape=tuple(want.shape))
        ot = torch.from_numpy(out)
        fn = torch._C._nn.upsample_bilinear2d if mode == 'bilinear' else torch._C._nn.upsample_bicubic2d
        fn(small, (T, W), False, None, None, out=ot)
        return [differing(want.numpy(), np.asarray(out))]
    return run


def _powout(e, layout):
    """The classic's functional torch pow (whole) against torch.pow(..., out=) into a mapped tensor of the same shape and
    strides (the E9 whole call without a private output)."""
    def run(data, mdata, T, W, h, tmp):
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
        assert [st for st, n in zip(want.stride(), want.shape) if n > 1] == [st for st, n in zip(ot.stride(), ot.shape) if n > 1]
        torch.pow(x, e, out=ot)
        return [differing(want.numpy(), ot.numpy())]
    return run


def _avgpool(data, mdata, T, W, h, tmp):
    import torch
    import torch.nn.functional as F
    a = torch.from_numpy(np.ascontiguousarray(data['L']))[None, None]
    b = torch.from_numpy(np.asarray(mdata['L']))[None, None]
    return [differing(F.avg_pool2d(a, f, ceil_mode=True).numpy(), F.avg_pool2d(b, f, ceil_mode=True).numpy()) for f in (3, 8)]


def _rpad(data, mdata, T, W, h, tmp):
    import torch
    import torch.nn.functional as F
    a = torch.from_numpy(np.ascontiguousarray(data['L']))[None, None]
    want = F.pad(a, (14, 14, 0, 0), mode='reflect')
    out = np.memmap(tmp / 'rpad.raw', dtype=np.float32, mode='w+', shape=tuple(want.shape))
    torch._C._nn.reflection_pad2d(torch.from_numpy(np.asarray(mdata['L']))[None, None], (14, 14, 0, 0), out=torch.from_numpy(out))
    return [differing(want.numpy(), np.asarray(out))]


def _label(data, mdata, T, W, h, tmp):
    from scipy.ndimage import label
    C = engine('bxf.components')
    want, n = label(data['mask'])
    out = np.memmap(tmp / 'lab.raw', dtype=np.int32, mode='w+', shape=want.shape)
    n2 = C.label_into(mdata['mask'], out)
    return [differing(want, np.asarray(out)), (0 if n == n2 else 1, 0 if n == n2 else 1)]


def _bincount(data, mdata, T, W, h, tmp):
    from scipy.ndimage import label
    C = engine('bxf.components')
    lab, n = label(data['mask'])
    want = np.bincount(lab.ravel())
    out = np.memmap(tmp / 'lab.raw', dtype=np.int32, mode='w+', shape=lab.shape)
    out[...] = lab
    got = C.bincount_bands(out, n, rows=h)
    return [differing(want, got), (0 if got.dtype == np.int64 else 1, 0)]


def _keep(data, mdata, T, W, h, tmp):
    C = engine('bxf.components')
    V = v4()
    mask = data['mask2']
    L = data['L']

    def keep(i, lab_, s, size):                    # a classic-style test: size and a ring statistic on the box
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


def _pct(q):
    def run(data, mdata, T, W, h, tmp):
        S = engine('bxf.selection')
        want = np.percentile(data['energy'], q)
        got = S.percentiles(S.band_chunks(mdata['energy'], h), [q])[0]
        return [differing(want, got), (0 if type(want) is type(got) else 1, 0)]
    return run


def _med(data, mdata, T, W, h, tmp):
    S = engine('bxf.selection')
    want = np.median(data['energy'])
    got = S.median(S.band_chunks(mdata['energy'], h))
    m = data['mask']
    want2 = np.median(data['L'][m])
    got2 = S.median(S.band_chunks(mdata['L'], h, mask=lambda y0, y1: np.asarray(mdata['mask'][y0:y1])))
    return [differing(want, got), differing(want2, got2), (0 if type(want) is type(got) else 1, 0)]


def _strided(data, mdata, T, W, h, tmp):
    S = engine('bxf.selection')
    import torch
    t = torch.from_numpy(np.ascontiguousarray(data['L']))[None, None]
    flat = t.flatten()
    if flat.numel() > 4_000_000:
        flat = flat[:: flat.numel() // 4_000_000 + 1]
    got = S.strided_sample(mdata['L'])
    return [differing(flat.numpy(), got)]


def _poolrun(op, params, reach, n):
    def run(data, mdata, T, W, h, tmp):
        Pl = engine('bxf.pool')
        key = 'mask' if op == 'binary_dilation' else 'L'
        src = mdata[key]
        one = np.memmap(tmp / 'p1.raw', dtype=src.dtype if op == 'binary_dilation' else np.float32, mode='w+', shape=src.shape)
        many = np.memmap(tmp / 'pn.raw', dtype=one.dtype, mode='w+', shape=src.shape)
        with Pl.BandPool(1) as p:
            p.map_rows(op, params, [src], [one], h, reach)
        with Pl.BandPool(n) as p:
            p.map_rows(op, params, [src], [many], h, reach)
        return [differing(np.asarray(one), np.asarray(many))]
    return run


# --- the run -------------------------------------------------------------------------------------------------------------

def run_probe(p, data, mdata, T, W, h, tmp):
    if p.kind == 'custom':
        res = p.run(data, mdata, T, W, h, tmp)
        return [r[0] for r in res], [r[1] for r in res]
    loc = engine('bxf.local')
    want = _outs(p.fn(*p.inputs(data)))
    got = [np.empty(np.asarray(w).shape, np.asarray(w).dtype) for w in want]
    loc.run_bands(lambda *a: tuple(_outs(p.fn(*a))), p.inputs(mdata), got, h, p.reach)
    res = [differing(w, g) for w, g in zip(want, got)]
    return [r[0] for r in res], [r[1] for r in res]


def environment():
    return engine('bxf.g1').environment()


def run_shapes(P, shapes, res_path, tmp, cap_gib, seed_offset=0, any_rem=False):
    """Run each probe at each (W, h, rem, filter[, tag]) shape, streaming one record per shape-test to res_path (a rerun
    resumes). any_rem: also run the probes registered for one remainder only (the sweep, and a tagged shape: the registered
    targets' own geometry, recorded with 'set': tag)."""
    done = set()
    if res_path.exists():
        for line in res_path.read_text(encoding='utf8').splitlines():
            r = json.loads(line)
            done.add((r['op'], r['T'], r['W'], r['h']))
    cap = cap_gib * 2 ** 30
    with open(res_path, 'a', encoding='utf8') as log:
        for shape in shapes:
            W, h, rem, keep = shape[:4]
            tag = shape[4] if len(shape) > 4 else None
            todo = [p for p in P if keep(p) and (any_rem or tag or p.only_rem is None or rem == p.only_rem)]
            if not todo:
                continue
            T2 = 2 * h + rem
            cache = {}
            for p in todo:
                T = T2 if p.bpp * T2 * W <= cap else (h + rem if p.bpp * (h + rem) * W <= cap else None)
                if T is None:
                    key = (p.name, -1, W, h)
                    if key not in done:
                        log.write(json.dumps({'op': p.name, 'cls': p.cls, 'T': -1, 'W': W, 'h': h, 'rem': rem,
                                              'skipped': f'over {cap_gib} GiB at {p.bpp} B/px',
                                              **({'set': tag} if tag else {})}) + '\n')
                        log.flush()
                        done.add(key)
                    continue
                if (p.name, T, W, h) in done:
                    continue
                if T not in cache:
                    for k in list(cache):
                        cache[k][1].close()
                    cache.clear()
                    gc.collect()
                    dd = Data(T, W, seed=T * 7 + W + seed_offset)
                    cache[T] = (dd, Mapped(dd, tmp / f'm{T}x{W}'))
                data, mdata = cache[T]
                t0 = time.time()
                try:
                    bits, vals = run_probe(p, data, mdata, T, W, h, tmp)
                    rec = {'op': p.name, 'cls': p.cls, 'T': T, 'W': W, 'h': h, 'rem': rem, 'reach': p.reach,
                           'differing': bits, 'value_differing': vals, 'secs': round(time.time() - t0, 2)}
                except MemoryError as e:
                    rec = {'op': p.name, 'cls': p.cls, 'T': T, 'W': W, 'h': h, 'rem': rem, 'error': f'MemoryError {e}'}
                except Exception as e:
                    rec = {'op': p.name, 'cls': p.cls, 'T': T, 'W': W, 'h': h, 'rem': rem,
                           'error': f'{type(e).__name__}: {e}'}
                if tag:
                    rec['set'] = tag
                log.write(json.dumps(rec) + '\n')
                log.flush()
                done.add((p.name, T, W, h))
                gc.collect()
            for k in list(cache):
                cache[k][1].close()
            cache.clear()
            gc.collect()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--only', default='')
    ap.add_argument('--widths', default='')
    ap.add_argument('--heights', default='')
    ap.add_argument('--cap-gib', type=float, default=8.0)
    ap.add_argument('--quick', action='store_true', help='tiny widths (a self-test of the gate, not a G1 run)')
    ap.add_argument('--summarise-only', action='store_true')
    ap.add_argument('--sweep', action='store_true', help='the off-grid soundness sweep (g1-sweep.jsonl)')
    ap.add_argument('--sweep-check', action='store_true', help='read the sweep against <out>/g1-table.json')
    ap.add_argument('--shard', default='', help="i/n: run every n-th probe from the i-th (merge the shards' g1-results.jsonl "
                                                'before --summarise-only)')
    ap.add_argument('--no-targets', action='store_true', help="skip the registered targets' own stage shapes (bxf-chk-4)")
    a = ap.parse_args(argv)
    if a.write and a.shard:
        raise SystemExit('--write needs every probe: merge the shards and run --summarise-only --write')
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    res_path = out / 'g1-results.jsonl'
    pri = below_normal()
    if a.sweep_check:
        r = sweep_check(json.loads((out / 'g1-table.json').read_text(encoding='utf8')), out / 'g1-sweep.jsonl')
        (out / 'g1-sweep-check.json').write_text(json.dumps(r, indent=1) + '\n', encoding='utf8')
        print(json.dumps({k: r[k] for k in ('tests', 'covered', 'covered_differing', 'whole_differing', 'pass')}))
        return r
    env = environment()
    P = shard_of([p for p in probes() if a.only in p.name], a.shard)
    if a.sweep:
        shapes = [(W, h, rem, lambda p: p.cls != 'pool') for W in SWEEP_WIDTHS for h in SWEEP_HEIGHTS for rem in SWEEP_REMS]
        run_shapes(P, shapes, out / 'g1-sweep.jsonl', out / 'tmp', a.cap_gib, seed_offset=1, any_rem=True)
        print('G1 sweep done:', out / 'g1-sweep.jsonl')
        return None
    if not a.summarise_only:
        widths = [int(v) for v in a.widths.split(',') if v] or sorted(set(w for p in P for w in p.widths) | set(NARROW_WIDTHS))
        heights = [int(v) for v in a.heights.split(',') if v] or list(HEIGHTS)
        if a.quick:
            widths = [61, 64]
        shapes = [(W, h, rem, (lambda p: True) if a.quick else (lambda p, W=W: runs_at(p, W)))
                  for W in widths for h in heights for rem in remainders(h)]
        if not (a.quick or a.no_targets or a.widths):
            shapes += [(W, h, rem, lambda p: p.cls != 'pool', 'target') for W, h, rem in target_shapes(heights)]
        run_shapes(P, shapes, res_path, out / 'tmp', a.cap_gib)
    table = summarise(res_path, env, pri)
    (out / 'g1-table.json').write_text(json.dumps(table, indent=1) + '\n', encoding='utf8')
    if a.write:
        write_table(table)
    n_b = sum(1 for v in table['ops'].values() if v['verdict'] == 'banded')
    print(f"G1: {len(table['ops'])} ops, {n_b} banded, {len(table['ops']) - n_b} whole; table in {out / 'g1-table.json'}")
    return table


def probe_info():
    """{op: (kind, production widths)} of the probes (the summary's classes)."""
    return {p.name: (p.kind, tuple(p.widths)) for p in probes()}


def geometry_of(g1, kind, r):
    """The record's band geometry as the reader keys it: local ops by band height and smallest band, others by plane."""
    if kind == 'local':
        return g1.Geometry(r['T'], r['W'], r['h'], r.get('reach', 0))
    return g1.Geometry(r['T'], r['W'])


def _differing(r):
    d = max((v if v >= 0 else 10 ** 12) for v in r['differing']) if r['differing'] else 0
    vd = max((v if v >= 0 else 10 ** 12) for v in r['value_differing']) if r['value_differing'] else 0
    return d, vd


def pareto(points):
    """The clean points no other clean point is at most as large as, in width and rows (sorted by width)."""
    pts = sorted(set(tuple(p) for p in points))
    return [list(p) for p in pts if not any(q != p and q[0] <= p[0] and q[1] <= p[1] for q in pts)]


def summarise(res_path, env, pri=None, info=None):
    """The table from the raw records. info: {op: (kind, production widths)} (default: the probes')."""
    g1 = engine('bxf.g1')
    info = probe_info() if info is None else info
    ops = {}
    for line in res_path.read_text(encoding='utf8').splitlines():
        r = json.loads(line)
        kind, core_w = info[r['op']][:2]
        o = ops.setdefault(r['op'], {'cls': r.get('cls'), 'kind': kind, 'reach': r.get('reach', 0), 'tested': 0, 'skipped': 0,
                                     'errors': 0, 'differing_max': 0, 'value_differing_max': 0, 'widths': set(),
                                     'heights': set(), 'rows': set(), 'first_difference': None, 'core_tested': 0,
                                     'core_differing_max': 0, 'core_heights': set(), 'narrow_tested': 0, 'narrow_differing': 0,
                                     '_clean': {}, '_failing': {}})
        if 'skipped' in r:
            o['skipped'] += 1
            continue
        if 'error' in r:
            o['errors'] += 1
            o.setdefault('error', r['error'])
            continue
        o['tested'] += 1
        o['widths'].add(r['W'])
        o['heights'].add(r['h'])
        o['rows'].add(r['T'])
        if 'reach' in r:
            o['reach'] = r['reach']
        d, vd = _differing(r)
        if d and o['first_difference'] is None:
            o['first_difference'] = {'T': r['T'], 'W': r['W'], 'h': r['h'], 'differing': r['differing']}
        o['differing_max'] = max(o['differing_max'], d)
        o['value_differing_max'] = max(o['value_differing_max'], vd)
        if r.get('set') == 'target':                    # the registered targets' own stage shapes are production-class
            o['target_tested'] = o.get('target_tested', 0) + 1
            o['target_differing'] = o.get('target_differing', 0) + int(d != 0)
        if r['W'] in core_w or r.get('set') == 'target':
            o['core_tested'] += 1
            o['core_heights'].add(r['h'])
            o['core_differing_max'] = max(o['core_differing_max'], d)
        else:
            o['narrow_tested'] += 1
            o['narrow_differing'] += int(d != 0)
        key, pt = g1.point(geometry_of(g1, kind, r))
        if pt is not None:
            (o['_clean'] if d == 0 else o['_failing']).setdefault(key, []).append(pt)
    for name, o in ops.items():
        clean, failing = o.pop('_clean'), o.pop('_failing')
        o['monotone'] = not any(fw >= cw and fr >= cr for k, fl in failing.items() for fw, fr in fl for cw, cr in clean.get(k, ()))
        ok = (o['core_tested'] > 0 and o['errors'] == 0 and o['core_differing_max'] == 0 and set(HEIGHTS) <= o['core_heights']
              and o['monotone'])
        o['verdict'] = 'banded' if ok else 'whole'
        o['failing_shapes'] = sum(len(v) for v in failing.values())
        allc = [p for v in clean.values() for p in v]
        o['band_rows_min'] = min((p[1] for p in allc), default=None)
        o['band_numel_min'] = min((p[0] * p[1] for p in allc), default=None)
        if ok:
            o['domain'] = {'key': 'height' if o['kind'] == 'local' else 'any',
                           'w_max': {k: max(p[0] for p in v) for k, v in sorted(clean.items())},
                           'frontier': {k: pareto(v) for k, v in sorted(clean.items())}}
        o['widths'] = sorted(o['widths'])
        o['heights'] = sorted(o['heights'])
        o['core_heights'] = sorted(o['core_heights'])
        o['rows'] = sorted(o['rows'])
    return {'gate': 'G1', 'about': 'engine design 2.4 and bxf-chk-1: banded only where every production-class shape gave 0 '
                                   'differing values and no failing shape is at least as large as a clean one; covered only '
                                   'on the measured band geometry (domain)',
            'environment': env, 'below_normal_priority': pri, 'band_heights': list(HEIGHTS), 'narrow_widths': list(NARROW_WIDTHS),
            'process_counts': [1, 2, 4], 'ops': dict(sorted(ops.items())),
            **({'target_planes': [list(t) for t in TARGET_PLANES]} if any(o.get('target_tested') for o in ops.values()) else {})}


def sweep_check(table, sweep_path, info=None):
    """The off-grid sweep against the table: a covered shape (the reader says banded) must have given 0 differing values."""
    g1 = engine('bxf.g1')
    info = probe_info() if info is None else info
    t = g1.Table(table, table['environment'])
    res = {'tests': 0, 'covered': 0, 'covered_differing': 0, 'whole_differing': 0, 'errors': 0, 'violations': [],
           'whole_differing_ops': {}}
    for line in Path(sweep_path).read_text(encoding='utf8').splitlines():
        r = json.loads(line)
        if 'skipped' in r:
            continue
        res['tests'] += 1
        kind = info[r['op']][0]
        cov = t.banded(r['op'], geom=geometry_of(g1, kind, r))
        bad = 'error' in r or _differing(r)[0] != 0
        res['errors'] += int('error' in r)
        if cov:
            res['covered'] += 1
            if bad:
                res['covered_differing'] += 1
                res['violations'].append({k: r.get(k) for k in ('op', 'T', 'W', 'h', 'rem', 'reach', 'differing', 'error')})
        elif bad:
            res['whole_differing'] += 1
            res['whole_differing_ops'][r['op']] = res['whole_differing_ops'].get(r['op'], 0) + 1
    res['pass'] = res['covered_differing'] == 0 and res['errors'] == 0
    return res


TABLE_HEADER = ('"""The G1 classification tables (written by tools/gate_g1.py --write; do not edit by hand): one table per '
                'environment\n(engine/bxf/g1.py ENV_KEYS), sizes and classifications only; the processor string is the only '
                'machine fact a table\ncarries. engine/bxf/g1.py applies a table only in the environment it records. TABLE is '
                'the first table, for\nreaders of the one-table form."""\nimport json\n\nTABLES = json.loads(r\'\'\'\n')


def current_tables(root=ROOT):
    """The committed tables of `root` (engine/bxf/g1_table.py), read from the file: TABLES, or the one-table form's TABLE."""
    path = Path(root) / 'engine' / 'bxf' / 'g1_table.py'
    if not path.exists():
        return []
    spec = importlib.util.spec_from_file_location('cu_g1_written_table', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if getattr(mod, 'TABLES', None) is not None:
        return list(mod.TABLES)
    return [mod.TABLE] if getattr(mod, 'TABLE', None) else []


def same_environment(a, b):
    """True when two tables record the same environment (every ENV_KEYS value equal)."""
    keys = engine('bxf.g1').ENV_KEYS
    ea, eb = a.get('environment', {}), b.get('environment', {})
    return all(ea.get(k) == eb.get(k) for k in keys)


def write_table(table, root=ROOT):
    """Upsert `table` into the committed list: the table of the same environment is replaced in place, every other table is
    kept (engine/bxf/g1_table.py TABLES; tests/fixtures/bxf_g1_tables.json, and bxf_g1_table.json = the first table)."""
    root = Path(root)
    tables = current_tables(root)
    for i, t in enumerate(tables):
        if same_environment(t, table):
            tables[i] = table
            break
    else:
        tables.append(table)
    text = json.dumps(tables, indent=1, sort_keys=True)
    (root / 'engine' / 'bxf' / 'g1_table.py').write_bytes(
        (TABLE_HEADER + text + "\n''')\nTABLE = TABLES[0] if TABLES else None\n").encode('utf8'))
    (root / 'tests' / 'fixtures' / 'bxf_g1_tables.json').write_bytes((text + '\n').encode('utf8'))
    one = root / 'tests' / 'fixtures' / 'bxf_g1_table.json'
    if not (one.exists() and json.loads(one.read_text(encoding='utf8')) == tables[0]):    # unchanged content: left as it is
        one.write_bytes((json.dumps(tables[0], indent=1, sort_keys=True) + '\n').encode('utf8'))
    return tables


if __name__ == '__main__':
    main()
