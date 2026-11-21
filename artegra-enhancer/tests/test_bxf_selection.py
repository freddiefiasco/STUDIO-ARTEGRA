"""E5 of the banded exact finish: exact streamed order statistics and numpy's own percentile / median arithmetic
(engine/bxf/selection.py), against np.percentile and np.median on 1e5-1e7 values at every interpolation edge case: ties,
duplicates, extremes, tiny counts, negative values and signed zeros, every quantile the finish uses, and any chunking. The
engine is loaded as the worker loads it (cu_banded_engine, by path). numpy only; synthetic values only."""
import importlib
import importlib.util
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FINISH_QS = (98.5, 35, 75, 90, 99.9, 50, 0, 100)


def engine(name):
    """engine/<name> under the worker's private package name, as node_pack/claude_banded._engine() loads it."""
    pkg = 'cu_banded_engine'
    if pkg not in sys.modules:
        spec = importlib.util.spec_from_file_location(pkg, ROOT / 'engine' / '__init__.py',
                                                      submodule_search_locations=[str(ROOT / 'engine')])
        mod = importlib.util.module_from_spec(spec)
        sys.modules[pkg] = mod
        spec.loader.exec_module(mod)
    return importlib.import_module(f'{pkg}.{name}')


def chunker(a, size):
    def it():
        for i in range(0, a.size, size):
            yield a[i:i + size]
    return it


def same(test, want, got, msg=''):
    test.assertIs(type(got), type(want), msg)
    w, g = np.asarray(want), np.asarray(got)
    test.assertEqual(w.dtype, g.dtype, msg)
    test.assertEqual(w.tobytes(), g.tobytes(), f'{msg}: want {want!r} got {got!r}')


class Keys(unittest.TestCase):
    def test_keys_are_monotonic_and_invert(self):
        S = engine('bxf.selection')
        v = np.array([-np.inf, -3.5, -1e-38, -1e-45, -0.0, 0.0, 1e-45, 1e-38, 0.5, 1.0, 3e38, np.inf], np.float32)
        k = S.keys(v)
        self.assertEqual(k.dtype, np.uint32)
        self.assertTrue(np.all(np.diff(k.astype(np.int64)) > 0))
        for x, kk in zip(v, k):
            self.assertEqual(S.unkey(kk).tobytes(), np.float32(x).tobytes())

    def test_only_float32(self):
        S = engine('bxf.selection')
        with self.assertRaises(TypeError):
            S.keys(np.zeros(3, np.float64))


class Percentiles(unittest.TestCase):
    def check(self, a, qs=FINISH_QS, chunks=(1000, 7777, None)):
        S = engine('bxf.selection')
        for size in chunks:
            ch = chunker(a, size or a.size)
            got = S.percentiles(ch, qs)
            for q, g in zip(qs, got):
                same(self, np.percentile(a, q), g, f'n={a.size} q={q} chunk={size}')

    def test_large_counts(self):
        rng = np.random.default_rng(1)
        for n in (100_000, 1_000_000, 10_000_000):
            a = rng.random(n, dtype=np.float32) * np.float32(0.3)
            self.check(a, chunks=(65536, None) if n > 1e6 else (1000, 7777, None))

    def test_ties_duplicates_and_extremes(self):
        rng = np.random.default_rng(2)
        cases = [np.zeros(100_000, np.float32), np.full(100_001, 0.25, np.float32),
                 rng.integers(0, 5, 100_000).astype(np.float32) / 4,          # five distinct values, heavy ties
                 np.repeat(np.float32([0.1, 0.9]), 50_000),                  # two values
                 np.concatenate([np.zeros(99_000, np.float32), rng.random(1000, dtype=np.float32)]),
                 (rng.standard_normal(200_000) * 3).astype(np.float32),     # negative values
                 np.float32([3.0]), np.float32([1.0, 2.0]), np.float32([5.0, -1.0, 2.0])]
        for a in cases:
            self.check(a, qs=FINISH_QS + (12.5, 33.3, 66.7, 1, 99))

    def test_random_quantiles_and_counts(self):
        rng = np.random.default_rng(3)
        for _ in range(40):
            n = int(rng.integers(1, 300_000))
            a = (rng.random(n, dtype=np.float32) ** 3).astype(np.float32)
            self.check(a, qs=tuple(float(q) for q in rng.random(4) * 100), chunks=(int(rng.integers(1, 50_000)),))

    def test_counts_and_ranks_past_2_31_are_exact(self):
        """bxf-chk-5: the name says what it checks. 129 chunks of 2**24 values (2,164,260,864 > 2**31): the count and ranks
        on both sides of 2**31 come out exact (int32 counters would wrap). The values are -1 below rank 2**31 and +1 from it,
        so a wrapped counter would put the 2**31 boundary in the wrong place."""
        S = engine('bxf.selection')
        lo, hi = np.full(1 << 24, -1.0, np.float32), np.full(1 << 24, 1.0, np.float32)
        k = (1 << 31) // (1 << 24)                         # 128 chunks of -1, then one of +1

        def it():
            for i in range(129):
                yield lo if i < k else hi
        n_want = 129 << 24
        ranks = [0, (1 << 31) - 1, 1 << 31, (1 << 31) + 5, n_want - 1]
        out, n, nans = S.order_statistics(it, ranks)
        self.assertEqual(n, n_want)
        self.assertGreater(n, 2 ** 31)
        self.assertEqual(nans, 0)
        self.assertEqual([float(out[r]) for r in ranks], [-1.0, -1.0, 1.0, 1.0, 1.0])
        self.assertIsInstance(out[1 << 31], np.float32)

    def test_nan_reads_as_numpys_nan(self):
        S = engine('bxf.selection')
        a = np.float32([1.0, np.nan, 2.0, 3.0])
        self.assertTrue(np.isnan(np.percentile(a, 50)))
        self.assertTrue(np.isnan(S.percentiles(chunker(a, 2), [50])[0]))


class Medians(unittest.TestCase):
    def test_against_np_median(self):
        S = engine('bxf.selection')
        rng = np.random.default_rng(4)
        for n in (1, 2, 3, 4, 5, 100_000, 100_001, 1_000_000):
            a = rng.random(n, dtype=np.float32)
            for size in (999, None):
                same(self, np.median(a), S.median(chunker(a, size or a.size)), f'n={n}')
        a = rng.integers(0, 3, 100_000).astype(np.float32)
        same(self, np.median(a), S.median(chunker(a, 4096)))

    def test_masked_band_chunks(self):
        S = engine('bxf.selection')
        rng = np.random.default_rng(5)
        img = rng.random((900, 333), dtype=np.float32)
        mask = img > 0.7
        want = np.median(img[mask])
        got = S.median(S.band_chunks(img, 288, mask=lambda y0, y1: mask[y0:y1]))
        same(self, want, got)
        same(self, np.percentile(img, 98.5), S.percentiles(S.band_chunks(img, 576), [98.5])[0])


class StridedSample(unittest.TestCase):
    def test_the_same_flat_indices(self):
        S = engine('bxf.selection')
        a = np.arange(4_500_009, dtype=np.float32).reshape(1500003, 3)
        got = S.strided_sample(a)
        step = a.size // 4_000_000 + 1
        np.testing.assert_array_equal(got, a.reshape(-1)[::step])
        small = np.arange(100, dtype=np.float32).reshape(10, 10)
        np.testing.assert_array_equal(S.strided_sample(small), small.reshape(-1))


if __name__ == '__main__':
    unittest.main()
