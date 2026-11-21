"""The band executor's own record (engine/bxf/local.Runner, node_pack/claude_banded/bxf/finish.BXF.record): a pass whose
estimated band is over the band budget even at the smallest registered height is recorded as an overrun with its numbers
(bxf-chk-2; the height stays a registered one); a pass that names a pool op runs in the pool only with 2 or 4 processes, where
the table covers that op's pool probe at the plane's size, and on whole file-backed planes; the finish's record carries the
tier, budget, processes, whole and pooled passes and the overruns; pool probe names are G1's own. numpy only."""
import importlib
import importlib.util
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


def finish_module():
    name = 'cu_test_record_bxf_finish'
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, ROOT / 'node_pack' / 'claude_banded' / 'bxf' / 'finish.py')
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    return sys.modules[name]


class Overruns(unittest.TestCase):
    def test_a_band_over_the_budget_is_recorded_with_its_numbers(self):
        g1, loc = engine('bxf.g1'), engine('bxf.local')
        r = loc.Runner(g1.AllBanded(), 2.0)
        a = np.ones((3, 30000), np.float32)
        out = np.empty_like(a)
        r('post', lambda x: x + np.float32(1), [a], [out], 8, (), 260)
        self.assertEqual(r.log[-1][:3], ('post', 'banded', 288))
        self.assertEqual(r.overruns, [{'pass': 'post', 'height': 288, 'estimated_bytes': (288 + 16) * 30000 * 260,
                                       'budget_bytes': 2 * 2 ** 30}])
        np.testing.assert_array_equal(out, a + 1)
        r('small', lambda x: x, [a[:, :1000]], [out[:, :1000]], 8, (), 260)
        self.assertEqual(len(r.overruns), 1)                       # it fits: nothing recorded
        r6 = loc.Runner(g1.AllBanded(), 6.0)
        r6('post', lambda x: x, [a], [out], 8, (), 260)
        self.assertEqual(r6.overruns, [])                          # (2304 + 16) x 30000 x 260 B is over 6 GiB, but 288 fits
        self.assertEqual(r6.log[-1][2], 576)

    def test_a_whole_pass_records_no_band_overrun(self):
        g1, loc = engine('bxf.g1'), engine('bxf.local')
        r = loc.Runner(g1.AllWhole(), 2.0)
        a = np.ones((3, 30000), np.float32)
        out = np.empty_like(a)
        r('post', lambda x: x, [a], [out], 8, (), 260)
        self.assertEqual((r.log[-1][1], r.overruns), ('whole', []))


class PoolRouting(unittest.TestCase):
    def test_the_pool_runs_only_where_it_is_proven_and_on_file_backed_planes(self):
        g1, loc = engine('bxf.g1'), engine('bxf.local')
        F = finish_module()
        probe = F.pool_probe('gaussian_filter', {'sigma': 4.242640687119286}, 2)
        self.assertEqual(probe, 'pool gaussian_filter s=4.242640687119286 n=2')
        self.assertEqual(F.pool_probe('gradient_mag', {}, 4), 'pool gradient_mag n=4')
        op = ('gaussian_filter', {'sigma': 4.242640687119286}, probe)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            m = np.memmap(Path(td) / 'a.raw', np.float32, 'w+', shape=(600, 40))
            o = np.memmap(Path(td) / 'o.raw', np.float32, 'w+', shape=(600, 40))
            self.assertTrue(loc.Runner(g1.AllBanded(), 2.0, processes=2).pooled(op, 600, 40, [m], [o]))
            self.assertFalse(loc.Runner(g1.AllBanded(), 2.0, processes=1).pooled(op, 600, 40, [m], [o]))
            self.assertFalse(loc.Runner(g1.AllBanded(), 2.0, processes=2).pooled(None, 600, 40, [m], [o]))
            self.assertFalse(loc.Runner(g1.AllBanded(), 2.0, processes=2).pooled(op, 600, 40, [np.zeros((600, 40), np.float32)], [o]))
            self.assertFalse(loc.Runner(g1.AllBanded(), 2.0, processes=2).pooled(op, 600, 40, [m[:300]], [o]))
            ENV = {'torch': 't', 'numpy': 'n', 'scipy': 's', 'cpu_capability': 'c', 'numpy_simd': [], 'processor': 'p'}
            without = g1.Table({'environment': ENV, 'ops': {}}, ENV)
            self.assertFalse(loc.Runner(without, 2.0, processes=2).pooled(op, 600, 40, [m], [o]))
            dom = {'verdict': 'banded', 'domain': {'key': 'any', 'w_max': {'any': 32000}, 'frontier': {'any': [[128, 583]]}}}
            t = g1.Table({'environment': ENV, 'ops': {probe: dom}}, ENV)
            self.assertTrue(loc.Runner(t, 2.0, processes=2).pooled(op, 600, 128, [m], [o]))
            self.assertFalse(loc.Runner(t, 2.0, processes=2).pooled(op, 600, 127, [m], [o]))     # narrower than G1 measured
            op4 = op[:2] + (F.pool_probe(op[0], op[1], 4),)
            self.assertFalse(loc.Runner(t, 2.0, processes=4).pooled(op4, 600, 128, [m], [o]))    # its n=4 probe is absent
            del m, o

    def test_every_routed_probe_is_a_g1_probe(self):
        """The finish's pool probe names are exactly the names tools/gate_g1.py measures (one source of truth)."""
        src = (ROOT / 'tools' / 'gate_g1.py').read_text(encoding='utf8')
        F = finish_module()
        self.assertIn("f'pool gaussian_filter s={s0!r} n={n}'", src)
        self.assertIn("f'pool {op} n={n}'", src)
        self.assertIn("('gradient_mag', {}, 1)", src)
        self.assertEqual(set(v[0] for v in F.POOL_ROUTES.values()), {'gaussian_filter', 'gradient_mag'})


class TheRecord(unittest.TestCase):
    def test_the_finish_record(self):
        g1 = engine('bxf.g1')
        F = finish_module()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            b = F.BXF(None, None, engine, Path(td) / 'w', band_gb=3.0, processes=2, table=g1.AllBanded())
            b.log.extend([('gmz', 'banded', 576, 1, 'pool', 2), ('lf.dm', 'whole', None, 14), ('lf.powx', 'E9 whole out=mapped', None),
                          ('mix', 'banded', 576, 0)])
            b.run.overruns.append({'pass': 'post', 'height': 288, 'estimated_bytes': 5, 'budget_bytes': 3})
            rec = b.record(0)
            self.assertEqual(rec, {'tier': 0, 'band_gb': 3.0, 'processes': 2, 'whole_passes': ['lf.dm', 'lf.powx'],
                                   'pool_passes': ['gmz'], 'band_overruns': 1,
                                   'overruns': [{'pass': 'post', 'height': 288, 'estimated_bytes': 5, 'budget_bytes': 3}]})
            b.close()
            self.assertFalse((Path(td) / 'w').exists())


if __name__ == '__main__':
    unittest.main()
