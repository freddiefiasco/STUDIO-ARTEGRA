"""5.0.2 build wave 3, the service package's fixes after its check (eng:wp-3-service-check S1 to S5).

- S1: a processor check that fails (out of time, over its cap, an error, or a table that does not apply here) never runs
  again at that band budget this session, whatever widths later images need: one check, and the images run at tier 3.

In this process with the stub probe of tests/test_service3_probe.py. Sizes and synthetic tables only."""
import json
import os
import unittest
from unittest import mock

from engine import banded_plan
from service import bxf_probe
from service.errors import ApiError
import tests.test_integ_large_image_job as J
import tests.test_service3_probe as P


def starts(svc):
    return [e for e in svc.events() if e['event'] == 'bxf_probe_start']


class TheFailedRecord(P.ProbeBase):
    def test_a_failure_holds_its_band_budget_for_the_session(self):
        self.stub.mode('exit2')
        g, _ = self.g1u()
        rec = g.run_probe([16000], 6.0, cap_gib=4.0)
        self.assertEqual(rec['exit'], 2)
        self.assertEqual(g.failed[6.0]['reason'], bxf_probe.PROBE_OUT_OF_TIME)
        self.assertEqual(g.failed[6.0]['widths'], [16000])
        for widths in ([16000], [32000], [8000, 16000, 32000], [7000]):
            self.assertFalse(g.probe_needed(widths, 6.0), widths)     # other widths at that budget: no second check
        self.assertTrue(g.probe_needed([16000], 3.0))                    # another band budget is another check
        g.request([7000, 14000], 6.0)
        self.assertIsNone(g.pending_request())

    def test_every_failure_path_records_it_the_same_way(self):
        g, _ = self.g1u()
        g.not_applied([6000, 12000], 6.0, {'exit': 0})
        self.assertEqual(g.failed[6.0]['reason'], bxf_probe.PROBE_NOT_APPLIED)
        self.assertFalse(g.probe_needed([8000, 16000, 32000], 6.0))
        g.mark_failed([8000], 3.0, bxf_probe.PROBE_FAILED)
        self.assertFalse(g.probe_needed([16000], 3.0))
        g.mark_failed([16000], 3.0, bxf_probe.PROBE_NO_MEMORY)             # a second record keeps the first reason
        self.assertEqual(g.failed[3.0], {'reason': bxf_probe.PROBE_FAILED, 'widths': [8000, 16000]})


class AFailedCheckRunsOnce(P.TheRunnerRunsIt):
    """Two queued Large-image images of different finish widths (8x of 4000 x 64 and of 3000 x 64) and a check that fails:
    exactly one check starts, and both images run at tier 3 (the check's reproduction)."""

    def ticks(self, svc, n=4):
        for _ in range(n):
            svc.runner._dispatch()
            self.join_probe(svc)

    def two_images(self, svc):
        j1 = self.queued(svc, w=4000, h=64)
        j2 = self.queued(svc, w=3000, h=64)
        w1 = svc.runner._probe_widths_of(svc.store.get(j1), svc.item(j1))
        w2 = svc.runner._probe_widths_of(svc.store.get(j2), svc.item(j2))
        self.assertTrue(set(w1) - set(w2) and set(w2) - set(w1), (w1, w2))   # the premise: each needs widths the other does not
        return j1, j2

    def both_run_at_tier_3(self, svc, jids):
        self.assertEqual(svc.run_all(), [])
        for jid in jids:
            self.assertEqual(self.done(svc, jid)['plan']['banded']['finish_tier'], 'tier3')

    def test_out_of_time_over_its_cap_and_a_table_that_does_not_apply(self):
        for i, mode in enumerate(('exit2', 'exit3', 'not_applied')):
            with self.subTest(mode=mode):
                if mode == 'not_applied':
                    self.stub.mode('write')
                    os.environ['CU_STUB_PROBE_ENV'] = json.dumps(dict(self.env, torch='0.0.0+another'))
                else:
                    self.stub.mode(mode)
                svc = self.service(f'state-{i}', env=self.env, probe=self.stub.command)
                jids = self.two_images(svc)
                self.ticks(svc)
                self.assertEqual(len(starts(svc)), 1, [e.get('data', {}).get('widths') for e in starts(svc)])
                self.both_run_at_tier_3(svc, jids)
                self.assertEqual(len(starts(svc)), 1)
                self.assertEqual([e['event'] for e in svc.events()].count('bxf_probe_failed'), 1)

    def test_a_check_that_raises(self):
        svc = self.service(env=self.env, probe=self.stub.command)
        jids = self.two_images(svc)
        with mock.patch.object(svc.runner.g1u, 'run_probe', side_effect=RuntimeError('a stand-in error')) as run:
            self.ticks(svc)
            self.both_run_at_tier_3(svc, jids)
        self.assertEqual(run.call_count, 1)
        self.assertIn('bxf_probe_error', [e['event'] for e in svc.events()])

    def test_a_later_image_of_other_widths_runs_without_a_check(self):
        self.stub.mode('exit2')
        svc = self.service(env=self.env, probe=self.stub.command)
        j1 = self.queued(svc, w=4000, h=64)
        self.ticks(svc, 2)
        self.both_run_at_tier_3(svc, [j1])
        j2 = self.queued(svc, w=2500, h=64)                           # 20,000 px: Large-image, widths no check measured
        self.assertTrue(banded_plan.is_banded(svc.item(j2)['plan']))
        self.ticks(svc, 3)
        self.both_run_at_tier_3(svc, [j2])
        self.assertEqual(len(starts(svc)), 1)

    def test_after_a_failure_a_refusal_asks_for_no_check(self):
        self.stub.mode('exit2')
        svc = self.service(env=self.env, probe=self.stub.command)
        j1 = self.queued(svc)
        self.ticks(svc, 2)
        self.both_run_at_tier_3(svc, [j1])
        mid = svc.add(J.strip_input(self.td / 'in', 'big.png', 3500, 2188))
        with mock.patch.object(banded_plan, 'probe_widths', create=True, side_effect=lambda *a, **k: [7000, 14000, 28000]):
            with self.assertRaises(ApiError) as e:
                svc.job([mid], {'scale': 8})
        self.assertNotIn('processor', str(e.exception))
        self.assertIsNone(svc.runner.g1u.pending_request())
        self.ticks(svc, 2)
        self.assertEqual(len(starts(svc)), 1)


if __name__ == '__main__':
    unittest.main()
