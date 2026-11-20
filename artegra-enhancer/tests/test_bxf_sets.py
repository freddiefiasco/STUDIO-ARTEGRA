"""The banded exact finish's registered sets and its G1 table reader (engine design 2.4, D7): band heights, process counts and
band budgets come only from their registered sets (anything else is asserted, never adapted); the table applies only in the
environment G1 measured, and an op it does not name, or any op elsewhere, reads 'whole'; the scratch workspace. numpy only."""
import importlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def engine(name):
    pkg = 'cu_banded_engine'
    if pkg not in sys.modules:
        spec = importlib.util.spec_from_file_location(pkg, ROOT / 'engine' / '__init__.py',
                                                      submodule_search_locations=[str(ROOT / 'engine')])
        mod = importlib.util.module_from_spec(spec)
        sys.modules[pkg] = mod
        spec.loader.exec_module(mod)
    return importlib.import_module(f'{pkg}.{name}')


class RegisteredSets(unittest.TestCase):
    def test_the_sets(self):
        b = engine('bands')
        self.assertEqual(b.BAND_HEIGHTS, (288, 576, 1152, 2304))
        self.assertEqual(sorted(b.PROCESS_COUNTS), [1, 2, 4])
        self.assertEqual(b.BAND_BUDGETS_GB, (2.0, 3.0, 6.0))
        self.assertEqual((b.BXF_DEFAULT_BUDGET_GB, b.BXF_DEFAULT_PROCESSES), (2.0, 1))
        for gb in (2, 3, 6, 2.0):
            self.assertEqual(b.check_band_budget(gb), float(gb))
        for gb in (1, 2.5, 4, 8, 64):
            with self.assertRaises(AssertionError):
                b.check_band_budget(gb)
        for n in (0, 3, 8):
            with self.assertRaises(AssertionError):
                b.check_process_count(n)
        for h in (1, 7, 289, 1024):
            with self.assertRaises(AssertionError):
                b.bands(1000, h)

    def test_band_heights_from_any_budget_and_width_stay_registered(self):
        loc, b = engine('bxf.local'), engine('bands')
        for gb in b.BAND_BUDGETS_GB:
            for w in (61, 5600, 14000, 32000):
                for bpp in (8, 64, 340):
                    for reach in (0, 40, 80):
                        self.assertIn(loc.band_height(w, bpp, gb, reach), b.BAND_HEIGHTS)

    def test_the_runner_refuses_an_unregistered_budget(self):
        loc, g1 = engine('bxf.local'), engine('bxf.g1')
        with self.assertRaises(AssertionError):
            loc.Runner(g1.AllBanded(), 4.0)
        loc.Runner(g1.AllBanded(), 2.0)

    def test_bands_tile_with_registered_alignment(self):
        b = engine('bands')
        for h in b.BAND_HEIGHTS:
            for T in (1, 7, h, 2 * h + 1, 2 * h + 7, 5 * h + h // 2 + 3):
                parts = b.bands(T, h, halo=80)
                self.assertTrue(b.covers(parts, T))
                for p in parts:
                    self.assertEqual(p.start % b.ALIGN, 0)


class G1Table(unittest.TestCase):
    def test_unknown_ops_and_other_environments_read_whole(self):
        g1 = engine('bxf.g1')
        env = {'torch': 't', 'numpy': 'n', 'scipy': 's', 'cpu_capability': 'c', 'numpy_simd': ['X'], 'processor': 'p'}
        data = {'environment': env, 'ops': {'a': {'verdict': 'banded'}, 'b': {'verdict': 'whole'}}}
        t = g1.Table(data, env)
        self.assertTrue(t.applies)
        self.assertEqual((t.verdict('a'), t.verdict('b'), t.verdict('c')), ('banded', 'whole', 'whole'))
        self.assertTrue(t.banded('a'))
        self.assertFalse(t.banded('a', 'b'))
        self.assertFalse(t.banded('a', 'zzz'))
        for k in g1.ENV_KEYS:
            other = dict(env, **{k: 'different'})
            t2 = g1.Table(data, other)
            self.assertFalse(t2.applies)
            self.assertEqual(t2.verdict('a'), 'whole')
            self.assertIn(k, t2.why_not())
        self.assertEqual(g1.Table(None, env).verdict('a'), 'whole')

    def test_the_table_module_and_its_fixture_agree(self):
        g1t = engine('bxf.g1_table')
        fx = ROOT / 'tests' / 'fixtures' / 'bxf_g1_table.json'
        if g1t.TABLE is None:
            self.assertFalse(fx.exists())
            return
        self.assertEqual(json.loads(fx.read_text(encoding='utf8')), g1t.TABLE)
        self.assertEqual(g1t.TABLE['band_heights'], [288, 576, 1152, 2304])
        for name, op in g1t.TABLE['ops'].items():
            self.assertIn(op['verdict'], ('banded', 'whole'), name)
            if op['verdict'] == 'banded':
                self.assertEqual(op['differing_max'], 0, name)
                self.assertEqual(op['heights'], [288, 576, 1152, 2304], name)
                self.assertEqual(op['errors'], 0, name)


class Workspace(unittest.TestCase):
    def test_new_free_close(self):
        W = engine('bxf.work')
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            ws = W.Workspace(Path(td) / 'w')
            a = ws.new('a', (300, 41, 3), np.float32)
            self.assertIsInstance(a, np.memmap)
            a[...] = 1.5
            b = ws.new('b', (300, 41), np.int32)
            self.assertEqual(ws.live_bytes, 300 * 41 * 16)
            with self.assertRaises(KeyError):
                ws.new('a', (1, 1))
            del a
            ws.free('a')
            self.assertFalse((Path(td) / 'w' / 'a.raw').exists())
            self.assertEqual(ws.peak_bytes, 300 * 41 * 16)
            del b
            ws.close()
            self.assertFalse((Path(td) / 'w').exists())


if __name__ == '__main__':
    unittest.main()
