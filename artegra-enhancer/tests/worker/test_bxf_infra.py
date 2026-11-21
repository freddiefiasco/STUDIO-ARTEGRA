"""The banded exact finish's band machinery against the classic calls (engine design 2.4), on the worker's libraries: E2
(uniform_filter on strips and bands, and v4finish.tbb), E3 (the pooled grids of v4finish.g at the 288 alignment), E4 (zoom into a
mapped output), E6 (label into a mapped plane, streamed bincount, keep tables against v4finish._components, per-component
medians), the E1 band executor, and the process pool at 2 and 4 processes against one. The engine is loaded as the worker
loads it (cu_banded_engine, by path); the classic v4finish.py is loaded by path, read only. Skipped where scipy or torch is
not installed:  python -B -m unittest tests.worker.test_bxf_infra   (from the artegra-enhancer folder). Synthetic only."""
import importlib
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

HAVE = all(importlib.util.find_spec(m) is not None for m in ('torch', 'scipy'))
ROOT = Path(__file__).resolve().parents[2]


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
    global _V4
    if _V4 is None:
        spec = importlib.util.spec_from_file_location('cu_test_classic_v4finish',
                                                      ROOT / 'node_pack' / 'claude_creative' / 'v4finish.py')
        _V4 = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_V4)
    return _V4


def img(h, w, seed=0):
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    a = 0.5 + 0.3 * np.sin(x / 37.0) * np.cos(y / 23.0) + (((x // 41 + y // 29) % 2) * 0.2) + rng.random((h, w)) * 0.1
    return (np.clip(a * 255, 0, 255).astype(np.uint8).astype(np.float32) / 255).astype(np.float32)


_N = [0]


def mapped(td, name, a):
    """A memory-mapped copy of `a` (each file new: Windows cannot resize a file that is still mapped)."""
    _N[0] += 1
    m = np.memmap(Path(td) / f'{name}-{_N[0]}.raw', dtype=a.dtype, mode='w+', shape=a.shape)
    m[...] = a
    m.flush()
    return m


def bits(a, b):
    a, b = np.asarray(a), np.asarray(b)
    assert a.shape == b.shape and a.dtype == b.dtype, (a.shape, b.shape, a.dtype, b.dtype)
    if a.dtype.kind == 'f':
        return int(np.count_nonzero(a.view(f'u{a.itemsize}') != b.view(f'u{b.itemsize}')))
    return int(np.count_nonzero(a != b))


SHAPES = ((577, 333), (1159, 129), (2311, 70), (300, 1001))


@unittest.skipUnless(HAVE, 'torch and scipy are not installed here (run on the worker runtime)')
class E2UniformFilter(unittest.TestCase):
    def test_strips_and_bands_equal_scipy_at_float32_and_float64(self):
        from scipy.ndimage import uniform_filter
        U, b = engine('bxf.uniform'), engine('bands')
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            for (H, W) in SHAPES:
                for dt in (np.float32, np.float64):
                    x = img(H, W, H).astype(dt)
                    mx = mapped(td, f'x{H}{dt.__name__}', x)
                    for n in (3, 7, 17, 49, 129):
                        want = uniform_filter(x, n, mode='reflect')
                        for rows in b.BAND_HEIGHTS:
                            dst = np.zeros_like(want)
                            U.uniform_filter_planes(mx, dst, n, np.zeros_like(want), rows=rows, strip=97)
                            self.assertEqual(bits(want, dst), 0, (H, W, dt, n, rows))

    def test_tbb_planes_equal_v4finish_tbb_in_place(self):
        U = engine('bxf.uniform')
        V = v4()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            for (H, W) in SHAPES[:2]:
                x = img(H, W, 7)
                for r in V.R:
                    out = mapped(td, f'o{r}', np.zeros_like(x))
                    U.tbb_planes(mapped(td, 'x', x) if r == 1 else mapped(td, f'x{r}', x), r, out, mapped(td, f't{r}', np.zeros_like(x)))
                    self.assertEqual(bits(V.tbb(x, r), out), 0, (H, W, r))


@unittest.skipUnless(HAVE, 'torch and scipy are not installed here (run on the worker runtime)')
class E3PooledGrids(unittest.TestCase):
    def test_pool_mean_and_g_at_the_288_alignment(self):
        P, Wk = engine('bxf.pooling'), engine('bxf.work')
        V = v4()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            for (H, W) in ((577, 333), (1153, 211), (2305, 61)):
                x = img(H, W, 3) - np.float32(0.4)
                for f in (2, 3, 4, 6, 8, 12, 18, 32, 48):
                    Hp, Wp = -(-H // f) * f, -(-W // f) * f
                    want = np.pad(x, ((0, Hp - H), (0, Wp - W)), mode='edge').reshape(Hp // f, f, Wp // f, f).mean((1, 3))
                    for rows in (288, 576, 1152, 2304):
                        grid = np.zeros_like(want)
                        P.pool_mean_bands(mapped(td, 'x', x), f, grid, rows)
                        self.assertEqual(bits(want, grid), 0, (H, W, f, rows))
                for s in sorted(set([2 * s for s in V.SIG if 2 * s > 8] + [3 * s for s in V.SIG if 3 * s > 8])):
                    ws = Wk.Workspace(Path(td) / 'ws')
                    got = P.g_pooled(mapped(td, 'gx', x), s, ws, 'z', 576)
                    self.assertEqual(bits(V.g(x, s), np.asarray(got).astype(np.float32)), 0, (H, W, s))
                    del got
                    ws.close()

    def test_a_factor_off_the_alignment_is_refused(self):
        P = engine('bxf.pooling')
        with self.assertRaises(AssertionError):
            P.pool_mean_bands(np.zeros((600, 10), np.float32), 5, np.zeros((120, 2), np.float32), 288)


@unittest.skipUnless(HAVE, 'torch and scipy are not installed here (run on the worker runtime)')
class E6Components(unittest.TestCase):
    def test_label_bincount_boxes_and_keep_tables(self):
        from scipy.ndimage import label, binary_dilation
        C = engine('bxf.components')
        V = v4()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            for (H, W) in SHAPES:
                x = img(H, W, 11)
                mask = (x > 0.62) & (np.roll(x, 3, 1) < 0.75)
                want, n = label(mask)
                lab = mapped(td, 'lab', np.zeros(mask.shape, np.int32))
                self.assertEqual(C.label_into(mapped(td, 'm', mask), lab), n)
                self.assertEqual(bits(want, lab), 0)
                for rows in (288, 2304):
                    counts = C.bincount_bands(lab, n, rows=rows)
                    self.assertEqual(counts.dtype, np.int64)
                    np.testing.assert_array_equal(counts, np.bincount(want.ravel()))

                def keep(i, lab_, s, size):     # a classic-style test reading the box
                    if not (5 <= size <= 5000):
                        return False
                    blob = lab_[s] == i
                    rr = binary_dilation(blob, iterations=2) & ~blob
                    return rr.sum() > 3 and float(x[s][blob].mean()) > 0.66
                ref = V._components(mask, keep)
                sizes, sl = C.bincount_bands(lab, n), C.find_objects(lab, n)
                table = np.zeros(n + 1, bool)
                for i in range(1, n + 1):
                    if sl[i - 1] is not None and keep(i, lab, sl[i - 1], sizes[i]):
                        table[i] = True
                out = np.zeros(mask.shape, bool)
                C.apply_table(table, lab, out, rows=288)
                self.assertEqual(bits(ref, out), 0, (H, W))
                for i in range(1, min(n, 40) + 1):
                    w = np.median(x[want == i])
                    self.assertEqual(np.asarray(C.component_median(x, lab, sl[i - 1], i)).tobytes(), np.asarray(w).tobytes())
                    self.assertEqual(np.asarray(C.component_median(x, lab, sl[i - 1], i, direct_max=0)).tobytes(),
                                     np.asarray(w).tobytes())
                    p = np.percentile(x[want == i], 90)
                    self.assertEqual(np.asarray(C.component_percentile(x, lab, sl[i - 1], i, 90, direct_max=0)).tobytes(),
                                     np.asarray(p).tobytes())
                sm = np.median(x[mask])
                self.assertEqual(np.asarray(C.masked_median(x, mask, rows=288, direct_max=0)).tobytes(), np.asarray(sm).tobytes())


@unittest.skipUnless(HAVE, 'torch and scipy are not installed here (run on the worker runtime)')
class E1BandExecutor(unittest.TestCase):
    def test_banded_equals_whole_for_classic_calls(self):
        from scipy.ndimage import gaussian_filter, maximum_filter, binary_dilation
        L = engine('bxf.local')
        V = v4()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            for (H, W) in SHAPES:
                x = img(H, W, 5)
                rgb = np.stack([x, np.roll(x, 5, 1), np.roll(x, 9, 0)], -1)
                mx, mrgb = mapped(td, 'x', x), mapped(td, 'rgb', rgb)
                cases = [(lambda a: gaussian_filter(a, 6.0), [x], [mx], 24),
                         (lambda a: maximum_filter(a, 15), [x], [mx], 7),
                         (lambda a: binary_dilation(a > 0.6, iterations=5), [x], [mx], 5),
                         (lambda a: V.band_energy(V.luma(a), 1.0, 6.0, 4.0), [rgb], [mrgb], 40),
                         (lambda a, b: V.chroma_mm(a, np.roll(b, 2, 1)), [rgb, rgb], [mrgb, mrgb], 40)]
                for fn, whole_in, band_in, reach in cases:
                    want = fn(*whole_in)
                    for h in (288, 576):
                        got = np.empty_like(want)
                        L.run_bands(fn, band_in, [got], h, reach)
                        self.assertEqual(bits(want, got), 0, (H, W, h, reach))

    def test_a_result_with_the_wrong_rows_is_refused(self):
        L = engine('bxf.local')
        with self.assertRaises(ValueError):
            L.run_bands(lambda a: a[1:], [np.zeros((600, 4), np.float32)], [np.zeros((600, 4), np.float32)], 288, 2)


@unittest.skipUnless(HAVE, 'torch and scipy are not installed here (run on the worker runtime)')
class ThePool(unittest.TestCase):
    def test_two_and_four_processes_equal_one(self):
        Pl = engine('bxf.pool')
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            x = img(1500, 517, 9)
            mx = mapped(td, 'x', x)
            mm = mapped(td, 'm', x > 0.6)
            for op, params, src, reach in (('gaussian_filter', {'sigma': 4.0}, mx, 16), ('maximum_filter', {'size': 15}, mx, 7),
                                           ('binary_dilation', {'iterations': 5}, mm, 5), ('gradient_mag', {}, mx, 1)):
                ref = None
                for n in (1, 2, 4):
                    out = mapped(td, f'o{n}', np.zeros(src.shape, src.dtype if op == 'binary_dilation' else np.float32))
                    with Pl.BandPool(n) as p:
                        self.assertEqual(len(p.children), 0 if n == 1 else n)
                        p.map_rows(op, params, [src], [out], 288, reach)
                    got = np.array(out)
                    if ref is None:
                        ref = got
                    self.assertEqual(bits(ref, got), 0, (op, n))
            s = mapped(td, 's', np.zeros_like(x))
            with Pl.BandPool(2) as p:
                p.map_cols('uniform_filter1d', {'size': 17, 'axis': 0, 'dtype': '<f4'}, [mx], [s], strip=100)
            from scipy.ndimage import uniform_filter1d
            self.assertEqual(bits(uniform_filter1d(x, 17, axis=0), s), 0)

    def test_unregistered_counts_and_ops_are_refused(self):
        Pl = engine('bxf.pool')
        with self.assertRaises(AssertionError):
            Pl.BandPool(3)
        with Pl.BandPool(1) as p, self.assertRaises(KeyError):
            p.map_rows('torch_conv', {}, [], [np.zeros((10, 10), np.float32)], 288)

    def test_a_child_imports_no_torch_and_sets_no_threads(self):
        src = (ROOT / 'engine' / 'bxf' / '_child.py').read_text(encoding='utf8') + \
            (ROOT / 'engine' / 'bxf' / 'ops.py').read_text(encoding='utf8')
        self.assertNotIn('import torch', src)
        for v in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'set_num_threads'):
            self.assertNotIn(v, src)


if __name__ == '__main__':
    unittest.main()
