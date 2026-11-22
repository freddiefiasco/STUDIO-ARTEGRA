"""tools/proof/node_table.py (build wave 3, contracts.g1u): a proof row's plans are made with its machine's committed G1 table
set on the planner as the service sets it, so the registered upper bound equals what the service plans on that machine.

The base planner of this branch ignores BXF_TABLE (the plan package adds the precedence in wave 3), so the tests that need
the merged behaviour patch banded_plan.finish_tier with contracts.g1u's precedence: a set BXF_TABLE decides ('bxf' when it
applies, else 'tier3'); BXF_AVAILABLE counts only while BXF_TABLE is None. Sizes only; nothing runs."""
import unittest
from unittest import mock

from engine import banded_plan
from engine.bxf import g1
from tools.proof import harness, node_table, packets, registration


class Stub:
    """A table with g1's interface; applies or not."""

    def __init__(self, applies):
        self.applies, self.mismatch = bool(applies), [] if applies else ['processor']
        self.data = {'environment': {'torch': 'stub', 'processor': 'stub'}, 'ops': {}}
        self.env = dict(self.data['environment'])

    def verdict(self, op):
        return 'banded' if self.applies else 'whole'

    def covers(self, op, geom=None):
        return self.applies

    def banded(self, *ops, geom=None):
        return self.applies and bool(ops)

    def why_not(self):
        return None if self.applies else 'the G1 table was measured on another environment (processor)'


def merged_tier():
    """contracts.g1u's precedence (the plan package's half, merged after this wave)."""
    t = getattr(banded_plan, 'BXF_TABLE', None)
    if t is not None:
        return 'bxf' if t.applies else 'tier3'
    return 'bxf' if banded_plan.BXF_AVAILABLE else 'tier3'


class Isolated(unittest.TestCase):
    def setUp(self):
        for name, value in (('BXF_TABLE', None), ('BXF_TABLE_SOURCE', None), ('BXF_AVAILABLE', False)):
            p = mock.patch.object(banded_plan, name, value, create=True)
            p.start()
            self.addCleanup(p.stop)


class Committed(Isolated):
    def test_each_committed_table_applies_under_its_own_environment(self):
        tabs = node_table.tables()
        self.assertGreaterEqual(len(tabs), 3)
        for i in range(len(tabs)):
            t = node_table.committed(i)
            self.assertTrue(t.applies, i)
            rec = node_table.record(i)
            self.assertEqual(rec['environment'], tabs[i]['environment'])
            self.assertEqual(rec['environment_sha256'], node_table.environment_sha256(tabs[i]['environment']))
            self.assertEqual(rec['source'], 'committed')
            self.assertGreater(rec['ops_banded'], 0)
            self.assertIsNone(node_table.check_registered(rec))
        with self.assertRaises(IndexError):
            node_table.committed(len(tabs))

    def test_the_worker_runtime_tables_carry_the_runtimes_libraries(self):
        # TABLES[1] (this workstation class) and TABLES[2] (the render node class) are the worker runtime's: the same
        # torch, numpy and scipy, another processor (BUILD-WAVE-3 verified.committed_tables_checked)
        a, b = (node_table.tables()[i]['environment'] for i in (1, 2))
        for k in ('torch', 'numpy', 'scipy', 'cpu_capability'):
            self.assertEqual(a[k], b[k], k)
        self.assertNotEqual(a['processor'], b['processor'])
        self.assertTrue(a['torch'].startswith('2.14.1'), a['torch'])

    def test_use_sets_the_planner_as_the_service_does(self):
        rec = node_table.use(2)
        self.assertIsInstance(banded_plan.BXF_TABLE, g1.Table)
        self.assertTrue(banded_plan.BXF_TABLE.applies)
        self.assertEqual(banded_plan.BXF_TABLE_SOURCE, 'committed')
        self.assertTrue(banded_plan.BXF_AVAILABLE)                # this branch alone still counts the banded finish
        self.assertEqual(rec['index'], 2)
        self.assertEqual(node_table.in_force(), {'table_set': True, 'source': 'committed', 'bxf_available': True,
                                                 'environment_sha256': rec['environment_sha256']})

    def test_a_registered_table_that_moved_is_refused(self):
        rec = dict(node_table.record(1), environment_sha256='0' * 64)
        self.assertIn('differs', node_table.check_registered(rec))
        self.assertIn('not in this build', node_table.check_registered({'index': 99}))

    def test_the_machines_environment_against_the_table(self):
        rec = node_table.record(2)
        self.assertEqual(node_table.check_environment(rec, rec['environment'])['equal'], True)
        other = dict(rec['environment'], processor='another')
        got = node_table.check_environment(rec, other)
        self.assertEqual((got['equal'], got['differs']), (False, ['processor']))


class RegisteredEqualsPlanned(Isolated):
    """The registered upper bound equals plan_banded's (and plan_forced's) under the same table, with the merged
    precedence: a table that applies counts the banded finish, one that does not counts tier 3, whatever BXF_AVAILABLE."""

    def setUp(self):
        super().setUp()
        p = mock.patch.object(banded_plan, 'finish_tier', merged_tier)
        p.start()
        self.addCleanup(p.stop)

    @staticmethod
    def uppers(rec):
        return [s['peak_upper_gb'] for s in rec['stages']]

    def forced_record(self, w, h, f, cap):
        return packets.plan_record(packets.forced(packets.classic_plan(w, h, f, cap), cap), cap, 'bes')

    def direct_forced(self, w, h, f, cap):
        plan = banded_plan.plan_forced(packets.classic_plan(w, h, f, cap), cap)
        return registration.plan_marks(plan, cap), plan

    def test_forced_plans_follow_the_table(self):
        for applies, tier in ((True, 'bxf'), (False, 'tier3')):
            node_table.use(table=Stub(applies))
            self.assertTrue(banded_plan.BXF_AVAILABLE)
            rec = self.forced_record(1280, 1600, 2, 59.0)
            marks, plan = self.direct_forced(1280, 1600, 2, 59.0)
            self.assertEqual(self.uppers(rec), [s['peak_upper_gb'] for s in marks['stages']], tier)
            self.assertEqual(rec['plan_dict_sha256'], registration.sha(plan.to_dict()))
            self.assertEqual(rec['variant_constants']['finish_tier'], tier)
        node_table.use(table=Stub(True))
        bxf = self.uppers(self.forced_record(1280, 1600, 2, 59.0))
        node_table.use(table=Stub(False))
        t3 = self.uppers(self.forced_record(1280, 1600, 2, 59.0))
        self.assertTrue(all(a <= b for a, b in zip(bxf, t3)), (bxf, t3))

    def test_production_plans_follow_the_table(self):
        proven = {'ws128': 2000.0, 'pc64': 2000.0, 'pc48': 2000.0}
        for applies in (True, False):
            node_table.use(table=Stub(applies))
            for w, h, f, cap in ((3500, 2188, 6, 122.2), (2800, 3500, 4, 59.0)):
                plan = packets.production(w, h, f, cap, proven=proven)
                rec = packets.plan_record(plan, cap, 'bes')
                direct = banded_plan.plan_banded(w, h, f, cap, classic=packets.planner.plan_501(w, h, f, ram_cap_gb=cap),
                                                 proven=proven)
                self.assertEqual(rec['plan_dict_sha256'], registration.sha(direct.to_dict()), (w, h, f, applies))
                if direct.ok:
                    self.assertEqual(self.uppers(rec), [s['peak_upper_gb'] for s in
                                                        registration.plan_marks(direct, cap)['stages']])

    def test_the_harness_forced_plan_is_the_registered_one(self):
        node_table.use(2)
        stages = (harness.Stage(1280, 1600, 2, 2, 0),)
        plan = harness.forced_plan(stages, 59.0)
        rec = packets.plan_record(plan, 59.0, 'bes')
        self.assertEqual(rec['variant_constants']['finish_tier'], 'bxf')
        self.assertEqual(rec['plan_dict_sha256'], registration.sha(harness.forced_plan(stages, 59.0).to_dict()))


if __name__ == '__main__':
    unittest.main()
