"""The G1 table's measured domain (bxf-chk-1): a 'banded' verdict holds only on the band geometry G1 measured. The reader
(engine/bxf/g1.py) answers 'banded' for a pass only when the pass's width is within the widths G1 measured clean at that band
height and the smallest band the executor would hand the op is at least as large (rows read, at a width at least as large)
as a band G1 measured clean; otherwise the pass runs whole on mapped planes (T7). A table without the domain fields, a
lookup without a geometry and an op G1 does not name read 'whole' (fail closed). numpy only."""
import importlib
import importlib.util
import json
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ENV = {'torch': 't', 'numpy': 'n', 'scipy': 's', 'cpu_capability': 'c', 'numpy_simd': ['X'], 'processor': 'p'}
CONV = 'torch _blur s=4.0 (_sep conv)'


def engine(name):
    pkg = 'cu_banded_engine'
    if pkg not in sys.modules:
        spec = importlib.util.spec_from_file_location(pkg, ROOT / 'engine' / '__init__.py',
                                                      submodule_search_locations=[str(ROOT / 'engine')])
        mod = importlib.util.module_from_spec(spec)
        sys.modules[pkg] = mod
        spec.loader.exec_module(mod)
    return importlib.import_module(f'{pkg}.{name}')


def gate_g1():
    spec = importlib.util.spec_from_file_location('cu_test_domain_gate_g1', ROOT / 'tools' / 'gate_g1.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def synthetic(ops):
    return {'environment': ENV, 'ops': ops}


def conv_like():
    """A local op measured clean on full bands at every width and on small last bands only from 1,459 px (the shape of the
    torch conv's oneDNN / native switch on this workstation)."""
    fr = {str(h): [[1459, 15], [977, 21], [128, h // 2 + 3 + 14]] for h in (288, 576, 1152, 2304)}
    return {'verdict': 'banded', 'domain': {'key': 'height', 'w_max': {k: 32000 for k in fr}, 'frontier': fr}}


class TheReaderChecksTheShape(unittest.TestCase):
    def test_small_last_bands_at_narrow_widths_are_not_covered(self):
        g1 = engine('bxf.g1')
        t = g1.Table(synthetic({CONV: conv_like()}), ENV)
        G = g1.Geometry
        # a narrow stage with a 2-row last band (6,914 = 24 x 288 + 2): 16 rows read (2 + reach 14)
        self.assertFalse(t.banded(CONV, geom=G(6914, 600, 288, 14)))
        self.assertFalse(t.banded(CONV, geom=G(6914, 1200, 288, 14)))
        self.assertTrue(t.banded(CONV, geom=G(6914, 1459, 288, 14)))
        self.assertTrue(t.banded(CONV, geom=G(6914, 7001, 288, 14)))
        # 21 rows read (a 7-row last band) is covered from 977 px; a 147-row last band from 128 px
        self.assertTrue(t.banded(CONV, geom=G(2 * 288 + 7, 977, 288, 14)))
        self.assertFalse(t.banded(CONV, geom=G(2 * 288 + 7, 976, 288, 14)))
        self.assertTrue(t.banded(CONV, geom=G(2 * 288 + 147, 128, 288, 14)))
        self.assertFalse(t.banded(CONV, geom=G(2 * 288 + 147, 127, 288, 14)))
        # wider than G1 measured, at that height: not covered
        self.assertFalse(t.banded(CONV, geom=G(6914, 32001, 288, 14)))

    def test_one_band_is_the_whole_call(self):
        g1 = engine('bxf.g1')
        t = g1.Table(synthetic({CONV: conv_like()}), ENV)
        self.assertTrue(t.banded(CONV, geom=g1.Geometry(200, 600, 288, 14)))
        self.assertTrue(t.banded(CONV, geom=g1.Geometry(288, 64, 288, 14)))
        self.assertEqual(g1.band_rows(289, 288, 14), [288 + 1, 1 + 14])

    def test_fail_closed(self):
        g1 = engine('bxf.g1')
        legacy = {'verdict': 'banded', 'differing_max': 0}                    # a table written before the domain fields
        t = g1.Table(synthetic({CONV: conv_like(), 'old': legacy, 'w': {'verdict': 'whole'}}), ENV)
        geom = g1.Geometry(6914, 7001, 288, 14)
        self.assertTrue(t.banded(CONV, geom=geom))
        self.assertFalse(t.banded(CONV))                                       # no geometry
        self.assertFalse(t.banded('old', geom=geom))
        self.assertFalse(t.banded('w', geom=geom))
        self.assertFalse(t.banded('not a probe', geom=geom))
        self.assertFalse(t.banded(CONV, 'old', geom=geom))
        self.assertFalse(t.banded(CONV, geom=g1.Geometry(6914, 7001)))         # a local op asked without its band height
        other = g1.Table(synthetic({CONV: conv_like()}), dict(ENV, torch='other'))
        self.assertFalse(other.banded(CONV, geom=geom))

    def test_whole_plane_ops_are_keyed_on_width_and_plane_rows(self):
        g1 = engine('bxf.g1')
        op = {'verdict': 'banded', 'domain': {'key': 'any', 'w_max': {'any': 32000}, 'frontier': {'any': [[128, 577]]}}}
        t = g1.Table(synthetic({'E6 label out=mapped': op}), ENV)
        self.assertTrue(t.banded('E6 label out=mapped', geom=g1.Geometry(577, 128)))
        self.assertTrue(t.banded('E6 label out=mapped', geom=g1.Geometry(32000, 32000)))
        self.assertFalse(t.banded('E6 label out=mapped', geom=g1.Geometry(576, 5000)))
        self.assertFalse(t.banded('E6 label out=mapped', geom=g1.Geometry(5000, 127)))

    def test_the_test_tables_ignore_the_geometry(self):
        g1 = engine('bxf.g1')
        self.assertTrue(g1.AllBanded().banded(CONV, geom=g1.Geometry(6914, 600, 288, 14)))
        self.assertTrue(g1.AllBanded().banded(CONV))
        self.assertFalse(g1.AllWhole().banded(CONV, geom=g1.Geometry(6914, 7001, 288, 14)))


class TheRunnerRoutesByShape(unittest.TestCase):
    def test_a_small_last_band_at_a_narrow_width_runs_whole(self):
        g1, loc = engine('bxf.g1'), engine('bxf.local')
        t = g1.Table(synthetic({CONV: conv_like()}), ENV)
        for H, W, want in ((6914, 600, 'whole'), (2 * 288 + 147, 600, 'banded'), (2 * 288 + 2, 1500, 'banded'), (200, 600, 'banded')):
            a = np.arange(H * W, dtype=np.float32).reshape(H, W)
            out = np.empty_like(a)
            r = loc.Runner(t, 2.0, height=288)
            r('lf.dm', lambda x: x * np.float32(2), [a], [out], 14, (CONV,), 40)
            self.assertEqual(r.log[-1][:2], ('lf.dm', want), (H, W))
            np.testing.assert_array_equal(out, a * np.float32(2))
            self.assertEqual(r.would_band((CONV,), H, W, 14, 40)[0] == 'banded', want == 'banded')


class TheGateRule(unittest.TestCase):
    """tools/gate_g1.summarise: banded only if every production-class shape is 0, at every height, with no error, and no
    failing shape at least as large (width and band rows) as a clean one; the domain is the clean points' frontier."""

    def rec(self, op, T, W, h, rem, d, reach=14):
        return {'op': op, 'cls': 'E8', 'T': T, 'W': W, 'h': h, 'rem': rem, 'reach': reach, 'differing': [d], 'value_differing': [d]}

    def write(self, tmp, recs):
        p = Path(tmp) / 'g1-results.jsonl'
        p.write_text(''.join(json.dumps(r) + '\n' for r in recs), encoding='utf8')
        return p

    def table(self, recs, core=(7001,)):
        import tempfile
        G1 = gate_g1()
        with tempfile.TemporaryDirectory() as td:
            return G1.summarise(self.write(td, recs), ENV, info={'c': ('local', tuple(core))})

    def shapes(self, W, fail=lambda W, rem: False):
        out = []
        for h in (288, 576, 1152, 2304):
            for rem in (1, 7, h // 2 + 3):
                out.append(self.rec('c', 2 * h + rem, W, h, rem, 5 if fail(W, rem) else 0))
        return out

    def test_a_narrow_small_band_failure_carves_the_domain(self):
        recs = self.shapes(7001) + self.shapes(600, lambda W, rem: rem == 1) + self.shapes(1459)
        t = self.table(recs)
        op = t['ops']['c']
        self.assertEqual(op['verdict'], 'banded')
        self.assertEqual(op['core_differing_max'], 0)
        self.assertGreater(op['differing_max'], 0)
        self.assertEqual(op['domain']['frontier']['288'], [[600, 21], [1459, 15]])
        g1 = engine('bxf.g1')
        T = g1.Table(t, ENV)
        self.assertFalse(T.banded('c', geom=g1.Geometry(577, 600, 288, 14)))      # the failing shape itself
        self.assertFalse(T.banded('c', geom=g1.Geometry(578, 1000, 288, 14)))
        self.assertTrue(T.banded('c', geom=g1.Geometry(578, 1459, 288, 14)))
        self.assertTrue(T.banded('c', geom=g1.Geometry(583, 600, 288, 14)))
        self.assertEqual((op['band_rows_min'], op['band_numel_min']), (15, 600 * 21))

    def test_a_production_failure_or_an_interleaved_failure_makes_it_whole(self):
        self.assertEqual(self.table(self.shapes(7001, lambda W, rem: rem == 7))['ops']['c']['verdict'], 'whole')
        # a failure at a larger width and band than a clean shape: the size generalisation is contradicted
        recs = self.shapes(7001) + self.shapes(977) + self.shapes(1459, lambda W, rem: rem == 1)
        op = self.table(recs)['ops']['c']
        self.assertEqual(op['verdict'], 'whole')
        self.assertFalse(op['monotone'])
        self.assertNotIn('domain', op)

    def test_errors_and_missing_heights_make_it_whole(self):
        recs = self.shapes(7001)
        recs[3] = {'op': 'c', 'cls': 'E8', 'T': recs[3]['T'], 'W': 7001, 'h': 576, 'rem': 1, 'error': 'MemoryError'}
        self.assertEqual(self.table(recs)['ops']['c']['verdict'], 'whole')
        recs = [r for r in self.shapes(7001) if r['h'] != 2304]
        self.assertEqual(self.table(recs)['ops']['c']['verdict'], 'whole')


class TheCommittedTable(unittest.TestCase):
    """The committed table read as if this were its own environment: the reader never covers a shape G1 measured differing,
    covers every production-class shape G1 measured clean, and names the conv's small narrow bands whole."""

    def table(self):
        g1, g1t = engine('bxf.g1'), engine('bxf.g1_table')
        return g1, g1t.TABLE, g1.Table(g1t.TABLE, g1t.TABLE['environment'])

    def test_fields(self):
        g1, data, t = self.table()
        self.assertTrue(t.applies)
        for name, op in data['ops'].items():
            self.assertIn(op['verdict'], ('banded', 'whole'), name)
            if op['verdict'] == 'banded':
                self.assertEqual((op['core_differing_max'], op['errors'], op['monotone']), (0, 0, True), name)
                self.assertEqual(op['heights'], [288, 576, 1152, 2304], name)
                d = op['domain']
                self.assertIn(d['key'], ('height', 'any'), name)
                keys = ['288', '576', '1152', '2304'] if d['key'] == 'height' else ['any']
                self.assertEqual(sorted(d['frontier']), sorted(keys), name)
                self.assertGreaterEqual(min(p[0] for k in keys for p in d['frontier'][k]), 128, name)
            else:
                self.assertNotIn('domain', op, name)

    def test_the_conv_is_whole_on_a_narrow_stage_with_a_small_last_band(self):
        g1, data, t = self.table()
        self.assertEqual(data['ops'][CONV]['verdict'], 'banded')
        self.assertFalse(t.banded(CONV, geom=g1.Geometry(6914, 600, 288, 14)))
        self.assertFalse(t.banded(CONV, geom=g1.Geometry(578, 600, 288, 14)))
        self.assertTrue(t.banded(CONV, geom=g1.Geometry(2 * 288 + 1, 7001, 288, 14)))
        self.assertTrue(t.banded(CONV, geom=g1.Geometry(6914, 32000, 288, 14)))


if __name__ == '__main__':
    unittest.main()
