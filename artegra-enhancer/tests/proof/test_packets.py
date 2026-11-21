"""tools/proof/packets.py: the registration record of every kind of proof-matrix row is stable (built twice, the same
sha256), a mark moved after sealing is detected, a workstation row that would not end before its window closes is refused,
and contracts the build does not have yet (banded Bolt, the finish inputs, the finish tier) are recorded, never assumed.
Sizes only; no image, no worker. Rows here are generic sizes, not the internal matrix."""
import copy
import inspect
import unittest
from pathlib import Path
from unittest import mock

from engine import banded_plan, graph_banded, planner
from tools.proof import harness, packets, registration

ROOT = Path(__file__).resolve().parents[2]
BUILD = {'git_head': 'deadbeef', 'channel': 'dev', 'tree': {'sha256': 'a' * 64, 'files': 1},
         'proof_tools': {'sha256': 'b' * 64, 'files': 1}}


def records():
    """One record per row kind, built from the build's own planner."""
    cl = packets.classic_plan(3500, 2188, 2, 59.0)                             # a classic 2x (R0-like, C1-like)
    bes = packets.forced(cl, 59.0)                                             # its forced Large-image plan
    ws = packets.classic_plan(3500, 2188, 4, 122.2)                           # the workstation's classic 4x
    wsb = packets.forced(ws, 122.2)                                            # split at every stage
    out = {
        'phase': packets.row_record('P-pair', 'phase', BUILD, {
            'classic': packets.plan_record(cl, 59.0, 'classic'), 'bes': packets.plan_record(bes, 59.0, 'bes')}),
        'service': packets.row_record('S-case', 'service', BUILD, {
            'classic_a': packets.plan_record(cl, 59.0, 'classic'), 'bes_a': packets.plan_record(bes, 59.0, 'bes'),
            'classic_b': packets.plan_record(cl, 59.0, 'classic', seed=20261120)}),
        'ws': packets.row_record('W-pair', 'phase', BUILD, {'bes': packets.plan_record(wsb, 122.2, 'bes')},
                                 window=packets.window_check(1_000_000.0, 200.0, 1_000_000.0 + 12 * 3600)),
        'cpu_finish': packets.row_record('F-rerun', 'cpu_finish', BUILD, {
            'rerun': packets.finish_rerun_record(3.0, 2, 'the stage\'s own output')}),
        'r7': packets.row_record('R-probe', 'r7', BUILD, {'probe': packets.r7_record()}),
        'frozen': packets.row_record('Z-frozen', 'frozen', BUILD, {'tools': {'driver.py': 'c' * 64}}),
    }
    return out


class Stable(unittest.TestCase):
    def test_every_kind_is_built_the_same_twice(self):
        a, b = records(), records()
        for k in a:
            da = registration.seal(packets.row_document(a[k], 'r1'), registered_at='2026-11-21T00:00:00+00:00')
            db = registration.seal(packets.row_document(b[k], 'r1'), registered_at='2026-11-21T00:00:00+00:00')
            self.assertEqual(da['sha256'], db['sha256'], k)
            self.assertEqual(registration.verify(da), [], k)

    def test_a_moved_mark_is_detected_for_every_kind(self):
        for k, rec in records().items():
            doc = registration.seal(packets.row_document(rec, 'r1'))
            moved = copy.deepcopy(doc)
            m = moved['marks'][-1]
            m['value'] = {'moved': True, 'was': m['value']}
            self.assertEqual(registration.verify(moved), [f"moved: {m['name']}", 'the document does not match its sealed '
                                                                                  'sha256'], k)
            self.assertEqual(registration.moved_marks(doc, registration.seal(_unsealed(moved))), [m['name']], k)

    def test_the_record_holds_what_the_rows_register(self):
        r = records()
        bes = r['service']['runs']['bes_a']
        self.assertEqual(set(bes['variant_constants']) >= set(packets.VARIANT_KEYS), True)
        self.assertEqual(bes['variant_constants']['finish'], banded_plan.DEFAULT_FINISH)
        self.assertEqual(len(bes['graph_sha256_per_pass']), 1)
        st = bes['stages'][0]
        for k in ('peak_expected_gb', 'peak_upper_gb', 'worker_peak_upper_gb', 'time_band_min', 'deadline_s'):
            self.assertIn(k, st)
        cl = r['service']['runs']['classic_a']
        self.assertEqual(cl['variant_constants']['engine'], 'classic')
        self.assertIn('peak_model_gb', cl['stages'][0])
        self.assertNotEqual(cl['graph_sha256_per_pass'], r['service']['runs']['classic_b']['graph_sha256_per_pass'])
        self.assertEqual(cl['graph_sha256_per_pass'][0],
                         harness.graph_sha(harness.classic_graph(harness.PAIRS['k4'][0])[0]))
        ws = r['ws']['runs']['bes']
        self.assertEqual([sorted(p) for p in ws['graph_sha256_per_pass']], [['A', 'B'], ['A', 'B']])
        self.assertTrue(all('parts' in s for s in ws['stages']))
        self.assertTrue(r['ws']['buildable'])

    def test_finish_tier_is_recorded_as_the_build_has_it(self):
        bes = records()['service']['runs']['bes_a']['variant_constants']
        self.assertEqual(bes['finish_tier_in_build'], 'finish_tier' in banded_plan.constants())
        self.assertEqual(bes['finish_tier'], banded_plan.constants().get('finish_tier'))


def _unsealed(doc):
    return {k: v for k, v in doc.items() if k not in ('sha256', 'marks_sha256', 'registered_at')}


class Refusals(unittest.TestCase):
    def test_a_workstation_row_that_would_end_after_the_close_is_refused(self):
        w = packets.window_check(0.0, 600.0, 10 * 3600)            # 10 h upper + 15 min in a 10 h window
        self.assertFalse(w['ends_before_close'])
        rec = packets.row_record('W', 'phase', BUILD, {}, window=w)
        self.assertFalse(rec['buildable'])
        self.assertIn('window', rec['refused_runs'])
        self.assertTrue(packets.window_check(0.0, 500.0, 10 * 3600)['ends_before_close'])

    def test_a_plan_the_planner_refuses_is_recorded_with_its_reason(self):
        cl = packets.classic_plan(3500, 2188, 8, 59.0)              # 5.0.1 refuses 8x of 3500 x 2188 (784 MP)
        self.assertFalse(cl.ok)
        bes = packets.forced(cl, 59.0)                              # so there is no classic plan to force
        rec = packets.plan_record(bes, 59.0)
        self.assertEqual(rec['refused'], cl.reason)
        row = packets.row_record('X', 'service', BUILD, {'bes_a': rec})
        self.assertFalse(row['buildable'])
        self.assertEqual(row['refused_runs'], {'bes_a': cl.reason})
        big = packets.production(4000, 4000, 8, 59.0, proven={'pc64': 2000.0})   # 1,024 MP on a 64 GB PC
        self.assertFalse(big.ok)
        self.assertTrue(packets.plan_record(big, 59.0)['refused'])

    def test_bolt_follows_the_build(self):
        cl = packets.classic_plan(3500, 2188, 2, 59.0)
        p = packets.forced(cl, 59.0, mode='fast')
        if 'mode' in inspect.signature(banded_plan.plan_forced).parameters:
            self.assertTrue(p.ok, p.reason)
        else:
            self.assertFalse(p.ok)
            self.assertIn('contracts.bolt', p.reason)
        self.assertEqual(harness.forced_plan(harness.PAIRS['k4'], 59.0, mode='fast').ok, p.ok)

    def test_a_build_with_banded_bolt_passes_the_mode(self):
        seen = {}

        def plan_forced(classic, cap, mode='redux'):
            seen['mode'] = mode
            return planner.Plan(True, classic.factor, classic.input_size, classic.output_size, engine='banded',
                                banded={'mode': 'bolt'})
        with mock.patch.object(banded_plan, 'plan_forced', plan_forced):
            p = packets.forced(packets.classic_plan(3500, 2188, 2, 59.0), 59.0, mode='fast')
        self.assertTrue(p.ok)
        self.assertEqual(seen['mode'], 'fast')

    def test_the_finish_inputs_follow_the_build(self):
        have = packets.finish_inputs_supported()
        rec = packets.finish_rerun_record(3.0, 2, 'ref')
        if all(have[k] for k in ('band_gb', 'processes')):
            self.assertNotIn('refused', rec)
        else:
            self.assertIn('contracts.finish_inputs', rec['refused'])
        with mock.patch.dict(graph_banded.NODE_OPTIONAL, {'CUFinishBanded': graph_banded.NODE_OPTIONAL['CUFinishBanded']
                                                          + ('band_gb', 'processes', 'finish_tier')}):
            self.assertNotIn('refused', packets.finish_rerun_record(3.0, 2, 'ref'))
            self.assertIn('not in the registered set', packets.finish_rerun_record(4.0, 2, 'ref')['refused'])
            self.assertIn('not in the registered set', packets.finish_rerun_record(3.0, 3, 'ref')['refused'])

    def test_over_300_mp_a_bxf_build_counts_the_banded_finish(self):
        # contracts.finish_tier: above FINISH_WHOLE_MAX_MP (300 MP) a 'tier3' plan is refused; a build whose BXF is
        # available plans it. Only the Large-image engine's own plans pass 300 MP (a classic stage is at most 150 MP, so no
        # forced plan does): 8x of 2800 x 3500 is 627 MP. Proof's registration sets BXF_AVAILABLE test-locally.
        with mock.patch.object(banded_plan, 'BXF_AVAILABLE', True, create=True):
            p = packets.production(2800, 3500, 8, 122.2, proven={'ws128': 2000.0})
            self.assertTrue(p.ok, p.reason)
            rec = packets.plan_record(p, 122.2)
        self.assertGreater(p.output_size[0] * p.output_size[1] / 1e6, 300)
        self.assertNotIn('refused', rec)
        self.assertEqual(len(rec['graph_sha256_per_pass']), 3)
        self.assertEqual(rec['variant_constants']['finish_tier'], (p.banded or {}).get('finish_tier'))
        self.assertFalse(packets.classic_plan(2800, 3500, 8, 122.2).ok)                    # 5.0.1 refuses it


if __name__ == '__main__':
    unittest.main()
