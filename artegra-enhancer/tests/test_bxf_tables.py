"""The G1 tables, one per environment (engine/bxf/g1_table.py TABLES; engine/bxf/g1.py load): a table applies only where the
running environment equals the one it records on every key (ENV_KEYS), anywhere else everything reads whole (fail closed); the
one-table form (TABLE only) is still read; a local table (selfprobe.py's, by path or by the worker's environment variable)
applies alone where no committed table matches and vetoes the ops it measured differing where one does. numpy only."""
import importlib
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
ENV = {'torch': 't', 'numpy': 'n', 'scipy': 's', 'cpu_capability': 'c', 'numpy_simd': ['X'], 'processor': 'p'}
OP = 'gaussian_filter s=2.0'


def engine(name):
    pkg = 'cu_banded_engine'
    if pkg not in sys.modules:
        spec = importlib.util.spec_from_file_location(pkg, ROOT / 'engine' / '__init__.py',
                                                      submodule_search_locations=[str(ROOT / 'engine')])
        mod = importlib.util.module_from_spec(spec)
        sys.modules[pkg] = mod
        spec.loader.exec_module(mod)
    return importlib.import_module(f'{pkg}.{name}')


def banded(w_max=32000, frontier=((128, 10),)):
    fr = {str(h): [list(p) for p in frontier] for h in (288, 576, 1152, 2304)}
    return {'verdict': 'banded', 'domain': {'key': 'height', 'w_max': {k: w_max for k in fr}, 'frontier': fr}}


def table(env, ops):
    return {'gate': 'G1', 'environment': dict(env), 'ops': ops}


GEOM = (6914, 7001, 288, 8)


class TheCommittedTables(unittest.TestCase):
    def test_every_environment_once_and_the_first_is_table(self):
        g1, g1t = engine('bxf.g1'), engine('bxf.g1_table')
        self.assertIs(g1t.TABLE, g1t.TABLES[0])
        envs = [tuple(json.dumps(t['environment'].get(k), sort_keys=True) for k in g1.ENV_KEYS) for t in g1t.TABLES]
        self.assertEqual(len(envs), len(set(envs)))
        for t in g1t.TABLES:
            self.assertEqual(sorted(t['environment']), sorted(g1.ENV_KEYS))
            self.assertEqual(t['band_heights'], [288, 576, 1152, 2304])
            self.assertNotIn('node', t)
            self.assertNotIn('machine', t)
        fx = json.loads((ROOT / 'tests' / 'fixtures' / 'bxf_g1_tables.json').read_text(encoding='utf8'))
        self.assertEqual(fx, g1t.TABLES)

    def test_the_workstation_torch_2_9_1_table_is_kept(self):
        g1t = engine('bxf.g1_table')
        self.assertEqual(g1t.TABLES[0]['environment']['torch'], '2.9.1+cpu')
        self.assertEqual(g1t.TABLES[0]['environment']['numpy'], '2.2.6')


RUNTIME = {'torch': '2.14.1+cu132', 'numpy': '2.5.4', 'scipy': '1.18.1'}     # the worker runtime's pins (contracts.runtime_copy)


class TheRuntimeTables(unittest.TestCase):
    """The tables G1 wrote on the worker runtime (this workstation, and each render node by G1r): their domains come from
    their own records (every banded op's frontier from 128 px, at every registered height, measured at the registered
    targets' own stage shapes too), and the reader covers the production passes on the targets' stages there."""

    def runtime_tables(self):
        g1t = engine('bxf.g1_table')
        return [t for t in g1t.TABLES if all(t['environment'].get(k) == v for k, v in RUNTIME.items())]

    def test_the_workstation_runtime_table_exists_and_measured_the_targets(self):
        from tools import gate_g1 as G1
        ts = self.runtime_tables()
        self.assertGreaterEqual(len(ts), 1)
        for t in ts:
            self.assertEqual([tuple(p) for p in t['target_planes']], list(G1.TARGET_PLANES))
            self.assertEqual(t['band_heights'], [288, 576, 1152, 2304])
            self.assertEqual(t['environment']['cpu_capability'], 'AVX512')

    def test_domains_come_from_their_own_records(self):
        g1 = engine('bxf.g1')
        for t in self.runtime_tables():
            banded = {k: v for k, v in t['ops'].items() if v['verdict'] == 'banded'}
            self.assertGreater(len(banded), 100)
            for name, op in t['ops'].items():
                if op['verdict'] != 'banded':
                    self.assertNotIn('domain', op, name)
                    continue
                self.assertEqual((op['core_differing_max'], op['errors'], op['monotone']), (0, 0, True), name)
                d = op['domain']
                keys = ['288', '576', '1152', '2304'] if d['key'] == 'height' else ['any']
                self.assertEqual(sorted(d['frontier']), sorted(keys), name)
                self.assertGreaterEqual(min(p[0] for k in keys for p in d['frontier'][k]), 128, name)
                if op['cls'] != 'pool':
                    self.assertGreater(op.get('target_tested', 0), 0, name)
            geom = g1.Geometry(4376, 7000, 288, 8)                      # the 4x 3500 x 2188 plan's first stage
            tab = g1.Table(t, t['environment'])
            for name in ('gaussian_filter s=2.0', 'v4.fin_post srcwarm', 'v4.luma', 'torch exact ops'):
                if t['ops'][name]['verdict'] == 'banded':
                    self.assertTrue(tab.banded(name, geom=geom), name)

    def test_the_routed_pool_covers_every_targets_plane(self):
        """fin-chk-2: Runner.pooled's lookup (the routed probe, a whole-plane geometry) is True at every registered target's
        finish plane, at 2 and 4 processes, on every runtime table: the 128 GB class's 6x and 8x stages (21,000-32,000 px)
        run their routed passes in the pool."""
        from tools import gate_g1 as G1
        g1 = engine('bxf.g1')
        routed = ('pool gaussian_filter s=4.242640687119286 n={n}', 'pool gradient_mag n={n}')
        for t in self.runtime_tables():
            tab = g1.Table(t, t['environment'])
            for W, H in G1.TARGET_PLANES:
                for n in (2, 4):
                    for name in routed:
                        self.assertTrue(tab.banded(name.format(n=n), geom=g1.Geometry(H, W)),
                                        (t['environment']['processor'][:12], name.format(n=n), W, H))

    def test_no_machine_fact_but_the_processor(self):
        for t in engine('bxf.g1_table').TABLES:
            self.assertEqual(sorted(t['environment']), sorted(engine('bxf.g1').ENV_KEYS))
            text = json.dumps(t).lower()
            for word in ('hostname', 'node', 'artegra', 'machine'):
                self.assertNotIn(word, text)


class TheRenderNodeTables(unittest.TestCase):
    """G1r (build wave 2): each render node class's own table on the worker runtime beside the workstation's, told apart by
    the processor string alone; two computers of one environment are committed as their merge (registered rule: banded only
    where both measured it banded, the domain covered only where both cover), never as one replacing the other."""

    def runtime_tables(self):
        return TheRuntimeTables.runtime_tables(self)

    def test_a_runtime_table_per_processor(self):
        ts = self.runtime_tables()
        procs = [t['environment']['processor'] for t in ts]
        self.assertGreaterEqual(len(set(procs)), 2)                  # this workstation and the render node class
        self.assertEqual(len(procs), len(set(procs)))

    def test_a_merged_table_holds_only_what_both_measured(self):
        merged = [t for t in self.runtime_tables() if 'merge' in t]
        for t in merged:
            self.assertEqual(t['merge']['tables'], 2)
            for name, op in t['ops'].items():
                both = op['merged_verdicts'] == ['banded', 'banded']
                if op['verdict'] == 'banded':
                    self.assertTrue(both, name)
                    self.assertIn('domain', op, name)
                else:
                    self.assertNotIn('domain', op, name)

    def test_the_render_node_class_reads_its_own_table(self):
        g1 = engine('bxf.g1')
        ts = self.runtime_tables()
        for t in ts:
            got = g1.load(env=dict(t['environment']), local='')
            self.assertTrue(got.applies)
            self.assertEqual(got.data['environment']['processor'], t['environment']['processor'])


class Load(unittest.TestCase):
    def patched(self, tables):
        g1t = engine('bxf.g1_table')
        return mock.patch.multiple(g1t, TABLES=tables, TABLE=tables[0] if tables else None)

    def test_the_exact_environment_only(self):
        g1 = engine('bxf.g1')
        a, b = table(ENV, {OP: banded()}), table(dict(ENV, torch='u'), {})
        with self.patched([b, a]):
            t = g1.load(env=dict(ENV), local='')
            self.assertTrue(t.applies)
            self.assertIs(t.data, a)
            self.assertTrue(t.banded(OP, geom=g1.Geometry(*GEOM)))
            for k in g1.ENV_KEYS:
                other = dict(ENV, **{k: 'different' if k != 'numpy_simd' else ['X', 'Y']})
                t2 = g1.load(env=other, local='')
                self.assertFalse(t2.applies, k)
                self.assertFalse(t2.banded(OP, geom=g1.Geometry(*GEOM)), k)
                self.assertEqual(t2.verdict(OP), 'whole', k)
                self.assertIn(k, t2.why_not(), k)

    def test_no_table_reads_whole(self):
        g1 = engine('bxf.g1')
        with self.patched([]):
            t = g1.load(env=dict(ENV), local='')
            self.assertFalse(t.applies)
            self.assertEqual(t.why_not(), 'no G1 table')

    def test_the_one_table_form_is_still_read(self):
        g1, g1t = engine('bxf.g1'), engine('bxf.g1_table')
        a = table(ENV, {OP: banded()})
        with mock.patch.multiple(g1t, TABLE=a, TABLES=None):
            t = g1.load(env=dict(ENV), local='')
            self.assertTrue(t.applies)
            self.assertTrue(t.banded(OP, geom=g1.Geometry(*GEOM)))
            self.assertFalse(g1.load(env=dict(ENV, scipy='z'), local='').applies)

    def test_two_tables_of_one_environment_are_read_together(self):
        g1 = engine('bxf.g1')
        a = table(ENV, {OP: banded(frontier=((128, 10),)), 'b': banded()})
        b = table(ENV, {OP: banded(frontier=((1459, 10),)), 'b': {'verdict': 'whole'}})
        with self.patched([a, b]):
            t = g1.load(env=dict(ENV), local='')
            self.assertTrue(t.applies)
            self.assertFalse(t.banded(OP, geom=g1.Geometry(6914, 600, 288, 8)))     # only one table covers 600 px
            self.assertTrue(t.banded(OP, geom=g1.Geometry(6914, 1500, 288, 8)))
            self.assertEqual(t.verdict('b'), 'whole')
            self.assertFalse(t.banded('b', geom=g1.Geometry(*GEOM)))


class TheLocalTable(unittest.TestCase):
    def write(self, td, data):
        p = Path(td) / 'local.json'
        p.write_text(json.dumps(data), encoding='utf8')
        return str(p)

    def test_alone_where_no_committed_table_matches(self):
        g1, g1t = engine('bxf.g1'), engine('bxf.g1_table')
        here = dict(ENV, processor='this computer')
        with tempfile.TemporaryDirectory() as td, mock.patch.multiple(g1t, TABLES=[table(ENV, {OP: banded()})],
                                                                      TABLE=table(ENV, {OP: banded()})):
            path = self.write(td, table(here, {OP: banded()}))
            self.assertFalse(g1.load(env=here, local='').applies)
            t = g1.load(env=here, local=path)
            self.assertTrue(t.applies)
            self.assertTrue(t.banded(OP, geom=g1.Geometry(*GEOM)))
            self.assertFalse(g1.load(env=dict(here, torch='x'), local=path).applies)    # its environment must match too
            with mock.patch.dict(os.environ, {g1.LOCAL_TABLE_ENV: path}):
                self.assertTrue(g1.load(env=here).applies)                              # the worker's variable
            bad = Path(td) / 'bad.json'
            bad.write_text('{not json', encoding='utf8')
            self.assertFalse(g1.load(env=here, local=str(bad)).applies)                 # unreadable: adds nothing
            self.assertFalse(g1.load(env=here, local=str(Path(td) / 'missing.json')).applies)

    def test_on_a_committed_table_its_differing_ops_read_whole(self):
        g1, g1t = engine('bxf.g1'), engine('bxf.g1_table')
        committed = table(ENV, {OP: banded(), 'other': banded()})
        with tempfile.TemporaryDirectory() as td, mock.patch.multiple(g1t, TABLES=[committed], TABLE=committed):
            path = self.write(td, table(ENV, {OP: {'verdict': 'whole'}, 'other': banded(frontier=((9000, 10),))}))
            t = g1.load(env=dict(ENV), local=path)
            geom = g1.Geometry(*GEOM)
            self.assertTrue(t.applies)
            self.assertFalse(t.banded(OP, geom=geom))
            self.assertEqual(t.verdict(OP), 'whole')
            self.assertTrue(t.banded('other', geom=geom))           # the committed domain stands for an op the probe passed
            self.assertIsNone(t.why_not())


if __name__ == '__main__':
    unittest.main()
