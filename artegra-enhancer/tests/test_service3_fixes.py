"""5.0.2 build wave 3, the service package's fixes after its check (eng:wp-3-service-check S1 to S5).

- S1: a processor check that fails (out of time, over its cap, an error, or a table that does not apply here) never runs
  again at that band budget this session, whatever widths later images need: one check, and the images run at tier 3.
- S5: while the engine runtime's environment is still being read (a first start), a plan 5.0.1 makes never waits, a plan
  the table can change waits a bounded time below the app's own limit, nothing waits under Runner._lock, the scheduler and
  admission never wait for the read, and plan cards never wait.

In this process with the stub probe of tests/test_service3_probe.py. Sizes and synthetic tables only."""
import json
import os
import threading
import time
import unittest
from types import SimpleNamespace
from unittest import mock

from engine import banded_plan, planner
from service import api, bxf_probe
from service.errors import ApiError
import tests.test_integ_large_image_job as J
import tests.test_service3_g1u as G
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


class SlowRead:
    """An environment read that blocks until the test releases it (a first start's cold read of the runtime)."""

    def __init__(self, env):
        self.env, self.go = env, threading.Event()

    def __call__(self):
        self.go.wait(60)
        return dict(self.env)


def in_thread(fn, *a, **k):
    out, done = {}, threading.Event()

    def body():
        try:
            out['value'] = fn(*a, **k)
        except BaseException as e:        # the test reads it
            out['error'] = e
        finally:
            done.set()
    threading.Thread(target=body, daemon=True).start()
    return out, done


class TheReadIsPending(G.ServiceBase):
    def setUp(self):
        super().setUp()
        self.read = SlowRead(G.committed_env(1))

    def tearDown(self):
        self.read.go.set()                 # the read ends (and assigns the planner's table) while the test's patches hold
        for t in threading.enumerate():
            if t.name == 'bxf-g1u':
                t.join(30)
        super().tearDown()

    def pending(self, state='state'):
        bxf_probe.TEST_ENVIRONMENT = self.read
        svc = J.InProcessService(self.td / state, self.ram_gb)
        self.assertFalse(svc.runner.g1u.ready.is_set())
        return svc

    def land(self, svc):
        self.read.go.set()
        self.assertTrue(svc.runner.g1u.ready.wait(30))

    def tier_soon(self, svc, jid, tier):
        end = time.monotonic() + 30
        while svc.item(jid)['plan']['banded']['finish_tier'] != tier and time.monotonic() < end:
            time.sleep(0.05)
        return svc.item(jid)['plan']['banded']['finish_tier']

    def test_a_classic_submit_returns_at_once_with_501s_plan(self):
        svc = self.pending()
        mid = svc.add(J.strip_input(self.td / 'in', 'small.png', 640, 480))
        t0 = time.monotonic()
        job = svc.job([mid], {'scale': 2})
        self.assertLess(time.monotonic() - t0, 5.0)
        self.assertFalse(svc.runner.g1u.ready.is_set())                    # it did not wait for the read
        cap = float(svc.settings.get()['ram_cap_gb'])
        self.assertEqual(job['items'][0]['plan'], planner.with_times(planner.plan_501(640, 480, 2, ram_cap_gb=cap)).to_dict())

    def test_plan_cards_and_a_classic_plan_route_do_not_wait(self):
        svc = self.pending()
        t0 = time.monotonic()
        svc.add(J.strip_input(self.td / 'in', 'wide.png', 4000, 64))        # its plan cards are made now
        self.assertEqual(svc.runner._media_ram_cap(), svc.settings.get()['ram_cap_gb'])
        self.assertEqual(self.route_plan(svc, 640, 480, 2)['status'], 200)
        self.assertLess(time.monotonic() - t0, 5.0)
        with mock.patch('service.runner.PLAN_TABLE_WAIT_S', 0.5):
            t0 = time.monotonic()
            self.assertEqual(self.route_plan(svc, 4000, 64, 8)['status'], 200)
            self.assertGreaterEqual(time.monotonic() - t0, 0.4)            # a Large-image size waits (bounded)

    def route_plan(self, svc, w, h, scale):
        h_ = object.__new__(api._Handler)
        h_.app = SimpleNamespace(runner=svc.runner, media=svc.media, store=svc.store, log=svc.log, settings=svc.settings)
        got = {}
        h_._body = lambda: {'width': w, 'height': h, 'scale': scale}
        h_._json = lambda status, body: got.update(status=status, body=body)
        api._Handler.r_plan(h_, {})
        return got

    def test_a_large_image_submit_waits_a_bounded_time_and_is_planned_again_when_the_table_lands(self):
        svc = self.pending()
        mid = svc.add(J.strip_input(self.td / 'in', 'wide.png', 4000, 64))
        with mock.patch('service.runner.SUBMIT_TABLE_WAIT_S', 0.5):
            t0 = time.monotonic()
            job = svc.job([mid], {'scale': 8})
            self.assertGreaterEqual(time.monotonic() - t0, 0.4)
        self.assertEqual(job['items'][0]['plan']['banded']['finish_tier'], 'tier3')   # made before the table landed
        self.land(svc)
        self.assertEqual(self.tier_soon(svc, job['id'], 'bxf'), 'bxf')
        self.assertIn('item_replanned', [e['event'] for e in svc.events()])

    def test_the_scheduler_and_admission_never_wait_for_the_read(self):
        svc = self.pending()
        _, done = in_thread(svc.runner._dispatch)
        self.assertTrue(done.wait(5))                                      # nothing queued: it asks for no check
        mid = svc.add(J.strip_input(self.td / 'in', 'small.png', 640, 480))
        jid = svc.job([mid], {'scale': 2})['id']
        _, done = in_thread(svc.runner._dispatch)
        self.assertTrue(done.wait(5))                                      # a Classic image is admitted and starts
        self.assertFalse(svc.runner.g1u.ready.is_set())
        self.assertEqual(svc.run_all(), [])
        self.done(svc, jid)

    def large_queued(self, svc):
        mid = svc.add(J.strip_input(self.td / 'in', 'wide.png', 4000, 64))
        with mock.patch('service.runner.SUBMIT_TABLE_WAIT_S', 0.1):
            return svc.job([mid], {'scale': 8})['id']

    def assert_waits_outside_the_lock(self, svc, fn, *a):
        with mock.patch('service.runner.CHANGE_TABLE_WAIT_S', 3.0):
            out, done = in_thread(fn, *a)
            time.sleep(0.5)                                                # it is waiting for the table now
            self.assertFalse(done.is_set())
            got = svc.runner._lock.acquire(timeout=1.0)
            if got:
                svc.runner._lock.release()
            self.assertTrue(got, 'the wait for the table held Runner._lock')
            self.assertTrue(done.wait(10))
        self.assertNotIn('error', out, out.get('error'))
        return out['value']

    def test_a_settings_change_waits_outside_the_runner_lock(self):
        svc = self.pending()
        jid = self.large_queued(svc)
        out = self.assert_waits_outside_the_lock(svc, svc.runner.set_item_settings, [{'job_id': jid, 'item_id': 'i001'}],
                                                 {'scale': 8})
        self.assertEqual(out['refused'], [], out)

    def test_a_requeue_waits_outside_the_runner_lock(self):
        svc = self.pending()
        jid = self.large_queued(svc)
        svc.store.update_item(jid, 'i001', state='failed', if_state={'queued'})
        self.assert_waits_outside_the_lock(svc, svc.runner.requeue_item, jid, 'i001')
        self.assertEqual(svc.item(jid)['state'], 'queued')


if __name__ == '__main__':
    unittest.main()
