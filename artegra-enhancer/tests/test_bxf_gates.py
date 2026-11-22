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


class ThePoolShapes(unittest.TestCase):
    """fin-chk-2: the pool's probes reach the widest registered target (32,000 px), and the routed ones run at every target's
    own plane, so the pool covers the 128 GB class's 6x and 8x stages (Runner.pooled's lookup)."""

    class P:
        def __init__(self, name, cls, widths, targets=None, only_rem=7):
            G1 = gate_g1()
            self.name, self.cls, self.widths, self.only_rem = name, cls, widths, only_rem
            self.targets = G1.Probe(name, cls, 'custom', targets=targets).targets

    def test_the_pool_widths_reach_every_target(self):
        G1 = gate_g1()
        self.assertEqual(max(G1.POOL_WIDTHS), max(W for W, _ in G1.TARGET_PLANES))
        self.assertEqual(max(G1.POOL_WIDTHS), 32000)
        self.assertEqual(G1.ROUTED_POOL_OPS, ('gradient_mag',))

    def test_routed_pool_probes_run_at_the_targets_planes(self):
        G1 = gate_g1()
        routed = self.P('pool gaussian_filter s=4.242640687119286 n=2', 'pool', G1.POOL_WIDTHS, targets=True)
        unrouted = self.P('pool maximum_filter n=2', 'pool', G1.POOL_WIDTHS)
        local = self.P('gaussian_filter s=2.0', 'E1', G1.WIDTHS_CORE, only_rem=None)
        shapes = G1.plan_shapes(sorted(set(G1.POOL_WIDTHS) | set(G1.NARROW_WIDTHS)))
        tagged = [s for s in shapes if len(s) > 4]
        self.assertEqual(sorted(s[:3] for s in tagged), G1.target_shapes())
        self.assertTrue(all(s[3](routed) and s[3](local) and not s[3](unrouted) for s in tagged))
        at = {s[0] for s in shapes if len(s) == 4 and s[3](routed)}
        self.assertTrue({21000, 32000} <= at)
        self.assertEqual(G1.plan_shapes([61, 64], quick=True, targets=False)[0][3](unrouted), True)
        self.assertFalse(any(len(s) > 4 for s in G1.plan_shapes([7001], targets=False)))


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


class TheMerge(unittest.TestCase):
    """Two machines whose environment keys are equal give one table: banded only where both are, domain the intersection."""

    def test_banded_where_both_are_and_covered_where_both_cover(self):
        G1 = gate_g1()
        import importlib
        g1 = importlib.import_module(G1.engine('bxf.g1').__name__)

        def op(fr, wmax=32000, verdict='banded'):
            d = {'verdict': verdict, 'cls': 'E8', 'core_differing_max': 0, 'errors': 0, 'monotone': True}
            if verdict == 'banded':
                d['domain'] = {'key': 'height', 'w_max': {'288': wmax}, 'frontier': {'288': fr}}
            return d
        a = {'environment': dict(ENV), 'gate': 'G1', 'ops': {'c': op([[977, 21], [1459, 15]]), 'w': op([[128, 1]]),
                                                             'same': op([[128, 5]])}}
        b = {'environment': dict(ENV), 'gate': 'G1', 'ops': {'c': op([[1459, 21], [2183, 13]], 21000), 'w': op(None, verdict='whole'),
                                                             'same': op([[128, 5]])}}
        m = G1.merge_tables(a, b, [{'torch_threads': 12}, {'torch_threads': 16}])
        self.assertEqual(m['ops']['w']['verdict'], 'whole')
        self.assertNotIn('domain', m['ops']['w'])
        self.assertEqual(m['ops']['c']['domain']['w_max'], {'288': 21000})
        self.assertEqual(m['ops']['c']['domain']['frontier']['288'], [[1459, 21], [2183, 15]])
        self.assertEqual(m['ops']['same'], dict(a['ops']['same'], merged_verdicts=['banded', 'banded']))
        self.assertEqual(sorted(x['op'] for x in m['merge']['disagreements']), ['c', 'w'])
        self.assertNotIn('torch_threads', json.dumps(m))                 # no machine fact but the processor string
        t = g1.Table(m, ENV)
        for W, rows, want in ((1459, 21, True), (1458, 21, False), (2183, 15, True), (1600, 16, False), (1600, 21, True), (21001, 99, False)):
            self.assertEqual(t.covers('c', g1.Geometry(2 * 288 + rows - 14, W, 288, 14)), want, (W, rows))
        with self.assertRaises(ValueError):
            G1.merge_tables(a, dict(b, environment=dict(ENV, torch='x')))


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


def gate_g2():
    spec = importlib.util.spec_from_file_location('cu_test_gates_gate_g2', ROOT / 'tools' / 'gate_g2.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TheCommitRecord(unittest.TestCase):
    """G2's record names the code under test on a computer without git (a render node runs the gate from a frozen farm packet;
    21 Nov 2026 the first node G2 stopped at start because git was not on the PATH): the packet's COMMIT file is read."""

    def test_without_git_the_commit_file_is_read(self):
        from unittest import mock
        G2 = gate_g2()
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / 'COMMIT').write_text('abcd1234\n', encoding='utf8')
            no_git = FileNotFoundError(2, 'git')
            with mock.patch.object(G2, 'ROOT', Path(td)), mock.patch.object(G2.subprocess, 'run', side_effect=no_git):
                self.assertEqual(G2.head(), 'abcd1234')
            with mock.patch.object(G2, 'ROOT', Path(td) / 'none'), mock.patch.object(G2.subprocess, 'run', side_effect=no_git):
                self.assertEqual(G2.head(), '')                                   # no git and no COMMIT file: unnamed

    def test_a_git_that_fails_falls_back_too(self):
        from unittest import mock
        G2 = gate_g2()
        failed = mock.Mock(returncode=128, stdout='')
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / 'COMMIT').write_text('feed0001\n', encoding='utf8')
            with mock.patch.object(G2, 'ROOT', Path(td)), mock.patch.object(G2.subprocess, 'run', return_value=failed):
                self.assertEqual(G2.head(), 'feed0001')


class TheMeasurementTools(unittest.TestCase):
    """Wave 3: --measure's fresh children run at the run's process count (before, they ran one process whatever --processes
    said), and the lean child's disk sampler counts the scratch folder's real bytes, the volume's free space and its floor."""

    def test_the_measure_child_carries_the_process_count_and_budget(self):
        import argparse
        G2 = gate_g2()
        a = argparse.Namespace(mp=16.0, table='g1', band_gb=6.0, height=0, processes=4, pre='5600x7000')
        cmd = G2.measure_cmd(a, Path('o'), Path('w'), 'v4f', 'bxf', ['--factor', 2.0])
        boot = cmd[-1]
        for flag, value in (('--processes', '4'), ('--band-gb', '6.0'), ('--child', 'v4f'), ('--what', 'bxf'),
                            ('--pre', '5600x7000'), ('--factor', '2.0')):
            self.assertIn(f"'{flag}', '{value}'", boot)
        self.assertEqual(cmd[1:4], ['-I', '-S', '-B'])

    def test_the_disk_sampler_counts_real_bytes_and_its_floor(self):
        G2 = gate_g2()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'bxf'
            self.assertEqual(G2.folder_bytes(root), 0)                          # not made yet
            (root / 'sub').mkdir(parents=True)
            (root / 'a.raw').write_bytes(b'x' * 1000)
            (root / 'sub' / 'b.raw').write_bytes(b'y' * 24)
            self.assertEqual(G2.folder_bytes(root), 1024)
            s = G2.DiskSampler(root, every=60)
            s.sample()
            (root / 'a.raw').unlink()
            s.sample()
            r = s.record()
            self.assertEqual(r['scratch_max_bytes'], 1024)
            self.assertEqual(r['samples'], 2)
            self.assertGreater(r['volume_min_free_bytes'], 0)
            self.assertGreaterEqual(r['volume_start_free_bytes'], 0)
            hit = []
            f = G2.DiskSampler(Path(td) / 'missing' / 'bxf', every=60, floor_bytes=2 ** 62, on_floor=hit.append)
            f.sample()                                                            # the first existing folder's volume
            self.assertEqual(len(hit), 1)
            self.assertEqual(hit[0]['floor_bytes'], 2 ** 62)
            with G2.DiskSampler(root, every=0.05) as t:
                pass
            self.assertGreaterEqual(t.record()['samples'], 2)


if __name__ == '__main__':
    unittest.main()
