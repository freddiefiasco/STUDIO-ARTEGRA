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


if __name__ == '__main__':
    unittest.main()
