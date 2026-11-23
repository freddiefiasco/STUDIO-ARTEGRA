"""tools/proof/records.py: the wsum mark from worker-log text (contract wsum) and the L3r split record (contract l3r_record).
Log samples are strings made here; no log file is committed."""
import json
import unittest

from tools.proof import records

LOG = """got prompt
Requested to load SDXL
[claude_banded] wsum_min=0.25 evals=30 windows=48
 10%|#         | 3/30
[claude_banded] wsum_min=1.0 evals=30 windows=48
Prompt executed in 812.33 seconds
"""


class Wsum(unittest.TestCase):
    def test_positive_lines_pass(self):
        r = records.wsum_mark(LOG)
        self.assertTrue(r['pass'])
        self.assertEqual((r['lines'], r['min'], r['evals'], r['windows']), (2, 0.25, 60, 48))

    def test_zero_negative_nan_and_garbled_fail(self):
        for bad in ('[claude_banded] wsum_min=0.0 evals=3 windows=4', '[claude_banded] wsum_min=-1e-07 evals=3 windows=4',
                    '[claude_banded] wsum_min=nan evals=3 windows=4', '[claude_banded] wsum_min= evals=3'):
            r = records.wsum_mark(LOG + bad + '\n')
            self.assertFalse(r['pass'], bad)
            self.assertTrue(r['bad'], bad)

    def test_a_banded_spot_run_without_any_line_fails(self):
        r = records.wsum_mark('got prompt\nPrompt executed in 1 s\n', expect_lines=True)
        self.assertFalse(r['pass'])
        self.assertEqual(r['reason'], 'no wsum line although a banded spot node ran')
        self.assertTrue(records.wsum_mark('got prompt\n', expect_lines=False)['pass'])

    def test_float_repr_forms(self):
        r = records.wsum_mark('[claude_banded] wsum_min=3.0517578125e-05 evals=1 windows=1\n')
        self.assertTrue(r['pass'])
        self.assertAlmostEqual(r['min'], 3.0517578125e-05)


ITEM = {'timings': {'stages': [
    {'stage': 0, 'part': None, 'seconds': 100},
    {'stage': 1, 'part': 'A', 'seconds': 400},
    {'stage': 1, 'part': 'B', 'seconds': 300, 'job_peak_commit_a_end_gb': 50.1, 'job_peak_commit_b_start_gb': 50.1,
     'stopped_worker_last_commit_gb': 31.0, 'commit_fall_gb': 30.2},
]}}


class L3r(unittest.TestCase):
    def test_from_the_item_timings(self):
        rs = records.l3r_from_item(ITEM)
        self.assertEqual(len(rs), 1)
        self.assertEqual(rs[0]['stage'], 1)
        self.assertEqual(rs[0]['source'], 'item.timings')

    def test_from_the_service_log_event(self):
        lines = [json.dumps({'ts': '2026-11-22T01:00:00.000+11:00', 'level': 'info', 'event': 'banded_split_commit',
                             'job': 'j1', 'item': 'i001', 'stage': 2, 'msg': 'x',
                             'data': {'job_peak_commit_a_end_gb': 40.0, 'job_peak_commit_b_start_gb': 41.0,
                                      'stopped_worker_last_commit_gb': 20.0, 'commit_fall_gb': 19.5}}),
                 json.dumps({'event': 'other', 'data': {}}), 'not json']
        rs = records.l3r_from_log('\n'.join(lines))
        self.assertEqual(len(rs), 1)
        self.assertEqual((rs[0]['stage'], rs[0]['job_peak_commit_b_start_gb']), (2, 41.0))

    def test_the_split_marks(self):
        r = records.l3r_check(records.l3r_from_item(ITEM), bound_gb=51.6, returned_tolerance_gb=1.0)
        self.assertTrue(r['pass'], r)
        r = records.l3r_check(records.l3r_from_item(ITEM), bound_gb=50.0, returned_tolerance_gb=1.0)
        self.assertFalse(r['pass'])
        self.assertIn('peak over the bound', r['records'][0]['fails'])
        r = records.l3r_check(records.l3r_from_item(ITEM), bound_gb=51.6, returned_tolerance_gb=0.5)
        self.assertIn('stopped worker commit not returned', r['records'][0]['fails'])
        self.assertFalse(records.l3r_check([], bound_gb=51.6, expect=1)['pass'])
        broken = {'timings': {'stages': [dict(ITEM['timings']['stages'][2], commit_fall_gb=None)]}}
        self.assertFalse(records.l3r_check(records.l3r_from_item(broken), bound_gb=60)['pass'])


class WholePasses(unittest.TestCase):
    """Build wave 4 (WP3P-1): the finish record's whole passes against the stage's bxf_whole_passes, read through the
    service's own mapping (memory.pass_key, local passes only) and pinned to the service's check."""
    PLANNED = ['acc<it>.4', 'lf.powo', 'lf.powx']

    def rec(self, *names, tier=0):
        return {'tier': tier, 'whole_passes': list(names), 'band_gb': 3.0, 'processes': 2}

    def test_iteration_names_read_as_their_pass_keys(self):
        r = records.whole_pass_check(self.rec('acc2.4', 'lf.powo', 'lf.powx'), self.PLANNED)
        self.assertTrue(r['pass'], r)
        self.assertEqual(r['ran_whole'], self.PLANNED)
        self.assertEqual(r['not_counted'], [])
        fewer = records.whole_pass_check(self.rec('lf.powo'), self.PLANNED)       # ran fewer whole: within the plan
        self.assertTrue(fewer['pass'])

    def test_a_pass_run_whole_that_the_plan_did_not_count_fails_naming_both(self):
        self.check_not_counted()

    def check_not_counted(self):
        r = records.whole_pass_check(self.rec('acc2.4', 'gc1.0', 'lf.powo'), self.PLANNED)
        self.assertFalse(r['pass'])
        self.assertEqual(r['not_counted'], ['gc<it>.0'])
        self.assertIn("the plan counted ['acc<it>.4', 'lf.powo', 'lf.powx']", r['why'])
        self.assertIn("ran ['acc<it>.4', 'gc<it>.0', 'lf.powo'] whole", r['why'])

    def test_a_plane_name_fallback_is_recorded_not_judged(self):
        r = records.whole_pass_check(self.rec('lf.powo', 'creative', 'E5 median'), self.PLANNED)
        self.assertTrue(r['pass'], r)
        self.assertEqual(r['not_judged'], ['E5 median', 'creative'])

    def test_tier_3_is_not_judged_and_a_missing_list_or_record_fails(self):
        self.assertIsNone(records.whole_pass_check(self.rec('x', tier=3), None)['pass'])
        self.assertFalse(records.whole_pass_check(self.rec('lf.powo'), None)['pass'])
        self.assertFalse(records.whole_pass_check(None, self.PLANNED)['pass'])

    def test_it_reads_as_the_service_reads(self):
        from service import banded_runner
        for names in (('acc2.4', 'lf.powo'), ('acc0.1', 'gc3.4', 'ycur2', 'creative', 'lf.dm'), ('E5 median',), ()):
            rec = self.rec(*names)
            keys, other = banded_runner.ran_whole(rec)
            r = records.whole_pass_check(rec, self.PLANNED)
            self.assertEqual((r['ran_whole'], r['not_judged']), (keys, other), names)
            self.assertEqual(r['not_counted'], sorted(set(keys) - set(self.PLANNED)), names)     # check_finish_record's

    def test_a_mutant_without_the_service_mapping_turns_it_red(self):
        from unittest import mock
        from engine.bxf import memory
        with mock.patch.object(memory, 'pass_key', lambda name: name):          # the iteration names read as written
            with self.assertRaises(AssertionError):                            # gc1.0 is lost as "not judged"
                self.check_not_counted()
        self.check_not_counted()
        with mock.patch.object(memory, 'PASSES', dict(memory.PASSES, creative=(12, ()))):  # a plane name read as a pass
            with self.assertRaises(AssertionError):
                self.test_a_plane_name_fallback_is_recorded_not_judged()


if __name__ == '__main__':
    unittest.main()
