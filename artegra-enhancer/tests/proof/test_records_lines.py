"""The wsum mark needs one line per banded sampling call (KS1 and KS2 of every banded stage, counted from the graphs that
ran), and the L3r split marks are checked per stage against that stage's registered bound (D10). Strings and graphs made
here; no log file is committed."""
import json
import unittest

from tools.proof import harness, records, registration

ONE = '[claude_banded] wsum_min=0.25 evals=30 windows=48\n'


def item(*stages):
    return {'timings': {'stages': list(stages)}}


def part_b(index, a=50.1, b=50.1, last=31.0, fall=30.2, **kw):
    return dict({'index': index, 'part': 'B', 'job_peak_commit_a_end_gb': a, 'job_peak_commit_b_start_gb': b,
                 'stopped_worker_last_commit_gb': last, 'commit_fall_gb': fall}, **kw)


class WsumLines(unittest.TestCase):
    def test_one_line_where_two_samplers_ran_fails(self):
        r = records.wsum_mark(ONE, expect_lines=True, expect_min=2)
        self.assertFalse(r['pass'])
        self.assertEqual(r['expected'], 2)
        self.assertIn('1 of 2', r['reason'])
        r = records.wsum_mark(ONE * 2, expect_lines=True, expect_min=2)
        self.assertTrue(r['pass'], r)

    def test_the_old_call_is_unchanged(self):
        self.assertTrue(records.wsum_mark(ONE)['pass'])
        self.assertTrue(records.wsum_mark('', expect_lines=False)['pass'])

    def test_expected_lines_are_counted_from_the_graphs(self):
        st = harness.PAIRS['k4'][0]
        plan = harness.forced_plan([st], 59.0)
        g, _ = harness.bes_graph(st, plan, 'w/p', 'w/p/input.plane', 'r')
        self.assertEqual(records.expected_wsum_lines([g]), 2)              # KS1 and KS2 on the banded spot model
        c, _ = harness.classic_graph(st)
        self.assertEqual(records.expected_wsum_lines([c]), 0)              # the classic spot node prints no wsum line
        w = harness.PAIRS['W1'][0]
        wp = harness.forced_plan(harness.PAIRS['W1'], 122.2)
        a, _ = harness.bes_graph(w, wp, 'w/p', 'w/p/input.plane', 'r', part='A')
        b, _ = harness.bes_graph(w, wp, 'w/p', 'w/p/input.plane', 'r', part='B')
        self.assertEqual(records.expected_wsum_lines([a, b]), 2)          # part A samples, part B finishes only
        self.assertEqual(records.expected_wsum_lines([g, a, b]), 4)

    def test_a_sampler_behind_the_two_card_node_still_counts(self):
        from engine import graph_banded
        st = harness.PAIRS['k4'][0]
        plan = harness.forced_plan([st], 59.0)
        g, _ = harness.bes_graph(st, plan, 'w/p', 'w/p/input.plane', 'r')
        self.assertEqual(records.expected_wsum_lines([graph_banded.add_multigpu(g, 2)]), 2)


class L3rPerStage(unittest.TestCase):
    def marks(self):
        st = harness.PAIRS['W1']
        plan = harness.forced_plan(st, 122.2)
        return registration.plan_marks(plan, 122.2)

    def test_each_split_stage_against_its_own_bound(self):
        m = self.marks()
        bounds = {s['index']: s['peak_upper_gb'] for s in m['stages']}
        it = item({'index': 0, 'part': 'A'}, part_b(0, a=bounds[0] - 1, b=bounds[0] - 1),
                  {'index': 1, 'part': 'A'}, part_b(1, a=bounds[1] - 2, b=bounds[1] - 2))
        r = records.l3r_stage_check(records.l3r_from_item(it), m)
        self.assertTrue(r['pass'], r)
        self.assertEqual(r['expected_stages'], [0, 1])
        self.assertEqual([x['bound_gb'] for x in r['records']], [bounds[0], bounds[1]])

    def test_a_missing_or_unmeasured_split_fails(self):
        m = self.marks()
        r = records.l3r_stage_check(records.l3r_from_item(item(part_b(0, a=10, b=10))), m)
        self.assertFalse(r['pass'])
        self.assertEqual(r['missing_stages'], [1])
        r = records.l3r_stage_check(records.l3r_from_item(item(part_b(0, a=10, b=10), part_b(1, fall=None))), m)
        self.assertFalse(r['pass'])
        self.assertIn('a field is missing', r['records'][1]['fails'])

    def test_a_record_for_a_stage_the_plan_does_not_split_fails(self):
        plan = harness.forced_plan(harness.PAIRS['k4'], 59.0)
        m = registration.plan_marks(plan, 59.0)
        self.assertFalse(any(s['split_finish'] for s in m['stages']))
        self.assertTrue(records.l3r_stage_check([], m)['pass'])
        r = records.l3r_stage_check(records.l3r_from_item(item(part_b(0, a=1, b=1))), m)
        self.assertFalse(r['pass'])
        self.assertEqual(r['unexpected_stages'], [0])

    def test_the_item_and_the_log_are_both_read(self):
        m = self.marks()
        b0, b1 = part_b(0, a=10, b=10), part_b(1, a=11, b=11)
        log = '\n'.join(json.dumps({'event': 'banded_split_commit', 'stage': s['index'], 'job': 'j', 'item': 'i001',
                                    'data': {k: s[k] for k in records.L3R_FIELDS}}) for s in (b0, b1))
        r = records.l3r_marks(item(b0, b1), log, m)
        self.assertTrue(r['pass'], r)
        self.assertEqual(r['source'], 'item.timings')
        self.assertTrue(r['log_agrees'])
        r = records.l3r_marks(None, log, m)
        self.assertTrue(r['pass'], r)
        self.assertEqual(r['source'], 'service log')
        r = records.l3r_marks(item(b0, part_b(1, a=12, b=12)), log, m)
        self.assertFalse(r['log_agrees'])


if __name__ == '__main__':
    unittest.main()
