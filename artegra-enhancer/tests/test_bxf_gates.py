"""The G1 gate's shape set and table writer (tools/gate_g1.py, 5.0.2 wave 2): the registered targets' own finish planes are
the stages the planner makes for them (bxf-chk-4), each measured at its own last band; shards partition the probes; the summary
counts a target shape as production class; --write upserts one table per environment and keeps the others, and still reads
the one-table form. numpy only (no probe runs here)."""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def gate_g1():
    spec = importlib.util.spec_from_file_location('cu_test_gates_gate_g1', ROOT / 'tools' / 'gate_g1.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ENV = {'torch': 't', 'numpy': 'n', 'scipy': 's', 'cpu_capability': 'c', 'numpy_simd': ['X'], 'processor': 'p'}


class TheTargetShapes(unittest.TestCase):
    def test_the_target_planes_are_the_planners_stages(self):
        from engine import banded_plan, graph_banded, planner
        G1 = gate_g1()
        planes = set()
        for w0, h0, factor in G1.TARGET_SOURCES:
            cur = (w0, h0)
            for i, f in enumerate(planner.STAGE_FACTORS[factor]):
                st = banded_plan.stage_choice(cur, f, i)
                pw, ph = st['padded_size']
                _, _, ow, oh = graph_banded.stage_sizes(pw, ph, st['factor'], st['supersample'])
                planes.add((ow, oh))
                cur = st['output_size']
        self.assertEqual(sorted(planes), sorted(G1.TARGET_PLANES))
        self.assertIn((32000, 32000), planes)
        self.assertIn((21000, 13128), planes)            # the 6x stage at factor 1.5

    def test_each_shape_has_the_planes_own_last_band(self):
        G1 = gate_g1()
        shapes = G1.target_shapes()
        self.assertEqual(len(shapes), len(set(shapes)))
        for W, H in G1.TARGET_PLANES:
            for h in G1.HEIGHTS:
                self.assertIn((W, h, H % h), shapes)
        self.assertTrue(all(W in {p[0] for p in G1.TARGET_PLANES} and h in G1.HEIGHTS for W, h, _ in shapes))


class Shards(unittest.TestCase):
    def test_shards_partition_the_probes(self):
        G1 = gate_g1()
        P = list(range(23))
        parts = [G1.shard_of(P, f'{i}/4') for i in range(4)]
        self.assertEqual(sorted(x for p in parts for x in p), P)
        self.assertEqual(G1.shard_of(P, ''), P)
        with self.assertRaises(SystemExit):
            G1.shard_of(P, '4/4')

    def test_write_refuses_a_shard(self):
        G1 = gate_g1()
        with tempfile.TemporaryDirectory() as td, self.assertRaises(SystemExit):
            G1.main(['--out', td, '--shard', '0/2', '--write', '--summarise-only'])


class TheSummary(unittest.TestCase):
    def recs(self, W=7001, fail_target=False):
        out = []
        for h in (288, 576, 1152, 2304):
            for rem in (1, 7, h // 2 + 3):
                out.append({'op': 'c', 'cls': 'E1', 'T': 2 * h + rem, 'W': W, 'h': h, 'rem': rem, 'reach': 4,
                            'differing': [0], 'value_differing': [0]})
            out.append({'op': 'c', 'cls': 'E1', 'T': 2 * h + 96, 'W': 5600, 'h': h, 'rem': 96, 'reach': 4,
                        'differing': [5 if fail_target else 0], 'value_differing': [5 if fail_target else 0], 'set': 'target'})
        return out

    def table(self, recs):
        G1 = gate_g1()
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'r.jsonl'
            p.write_text(''.join(json.dumps(r) + '\n' for r in recs), encoding='utf8')
            return G1.summarise(p, ENV, True, info={'c': ('local', (7001,))})

    def test_a_target_shape_is_production_class(self):
        t = self.table(self.recs())
        op = t['ops']['c']
        self.assertEqual(op['verdict'], 'banded')
        self.assertEqual((op['target_tested'], op['target_differing']), (4, 0))
        self.assertEqual(op['core_tested'], 16)
        self.assertIn([5600, 96 + 4], op['domain']['frontier']['288'])
        self.assertIn('target_planes', t)
        bad = self.table(self.recs(fail_target=True))['ops']['c']
        self.assertEqual(bad['verdict'], 'whole')        # a differing target shape is a differing production shape


class TheWriter(unittest.TestCase):
    def root(self, td, one_table):
        r = Path(td)
        (r / 'engine' / 'bxf').mkdir(parents=True)
        (r / 'tests' / 'fixtures').mkdir(parents=True)
        (r / 'engine' / 'bxf' / 'g1_table.py').write_text(
            'import json\n\nTABLE = json.loads(r\'\'\'\n' + json.dumps(one_table) + "\n''')\n", encoding='utf8')
        return r

    def load(self, r):
        spec = importlib.util.spec_from_file_location('cu_test_written_g1_table', r / 'engine' / 'bxf' / 'g1_table.py')
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_upsert_by_environment_and_the_one_table_form(self):
        G1 = gate_g1()
        a = {'environment': dict(ENV), 'ops': {'x': {'verdict': 'whole'}}, 'gate': 'G1'}
        with tempfile.TemporaryDirectory() as td:
            r = self.root(td, a)
            self.assertEqual(G1.current_tables(r), [a])                          # the one-table form is read
            b = {'environment': dict(ENV, torch='other'), 'ops': {}, 'gate': 'G1'}
            G1.write_table(b, r)
            m = self.load(r)
            self.assertEqual(m.TABLES, [a, b])
            self.assertEqual(m.TABLE, a)                                          # the first table, for one-table readers
            a2 = dict(a, ops={'x': {'verdict': 'banded'}})
            G1.write_table(a2, r)
            m = self.load(r)
            self.assertEqual(m.TABLES, [a2, b])                                   # the same environment is replaced in place
            fx = json.loads((r / 'tests' / 'fixtures' / 'bxf_g1_tables.json').read_text(encoding='utf8'))
            self.assertEqual(fx, [a2, b])
            self.assertEqual(json.loads((r / 'tests' / 'fixtures' / 'bxf_g1_table.json').read_text(encoding='utf8')), a2)
            self.assertNotIn(b'\r\n', (r / 'engine' / 'bxf' / 'g1_table.py').read_bytes())
            c = {'environment': dict(ENV, numpy_simd=['X', 'Y']), 'ops': {}, 'gate': 'G1'}
            self.assertEqual(len(G1.write_table(c, r)), 3)                       # any one key differing: another table


if __name__ == '__main__':
    unittest.main()
