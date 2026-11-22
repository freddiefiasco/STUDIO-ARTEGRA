"""5.0.2 build wave 3, the service package's fixes after its check (eng:wp-3-service-check S1 to S5).

- S1: a processor check that fails (out of time, over its cap, an error, or a table that does not apply here) never runs
  again at that band budget this session, whatever widths later images need: one check, and the images run at tier 3.
- S2: at every start, after the restart recovery, queued Large-image images are planned again for the table that applies
  now (a plan stored under a table that is gone runs at tier 3, not fails), in either order of the read and the recovery;
  a failed read is tried once more before a plan that counted the table is failed.
- S3: while the check runs, every queued image (Classic ones and those queued during it too) says why it waits,
  with the check's remaining upper bound, written only when it changes.
- S4: the processor-check sentence, and the check, only for a refusal the check can lift (the planner's or the
  memory cap's, on a card in use that takes a Large-image result of that size).
- S5: while the engine runtime's environment is still being read (a first start), a plan 5.0.1 makes never waits, a plan
  the table can change waits a bounded time below the app's own limit, nothing waits under Runner._lock, the scheduler and
  admission never wait for the read, and plan cards never wait.

In this process with the stub probe of tests/test_service3_probe.py. Sizes and synthetic tables only."""
import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from engine import banded_plan, planner
from service import api, banded_runner, bxf_probe
from service.errors import ApiError
from service.runner import ItemFailure
import tests.test_integ_large_image_job as J
import tests.test_service3_g1u as G
import tests.test_service3_probe as P


def starts(svc):
    return [e for e in svc.events() if e['event'] == 'bxf_probe_start']


class StubRunner(G.ServiceBase):
    """The in-process service with the stub probe: tests/test_service3_probe.TheRunnerRunsIt's set-up and helpers, without
    its tests (a subclass would run them again)."""

    def setUp(self):
        super().setUp()
        self.env = G.unmatched_env()
        self.stub = P.StubProbe(self.td, self.env)
        p = mock.patch.dict(os.environ, self.stub.vars)
        p.start()
        self.addCleanup(p.stop)

    queued = P.TheRunnerRunsIt.queued
    join_probe = P.TheRunnerRunsIt.join_probe


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


class AFailedCheckRunsOnce(StubRunner):
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


def tier_soon(svc, jid, tier, timeout=30.0):
    """The image's finish tier once it is `tier` (the re-plan runs on the G1u thread), or as it is at the timeout."""
    end = time.monotonic() + timeout
    while svc.item(jid)['plan']['banded']['finish_tier'] != tier and time.monotonic() < end:
        time.sleep(0.05)
    return svc.item(jid)['plan']['banded']['finish_tier']


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
        return tier_soon(svc, jid, tier)

    def waits(self, svc):
        """A spy on the one wait for the table (G1u.wait_ready)."""
        p = mock.patch.object(svc.runner.g1u, 'wait_ready', wraps=svc.runner.g1u.wait_ready)
        spy = p.start()
        self.addCleanup(p.stop)
        return spy

    def test_a_classic_submit_returns_at_once_with_501s_plan(self):
        svc = self.pending()
        mid = svc.add(J.strip_input(self.td / 'in', 'small.png', 640, 480))
        spy = self.waits(svc)
        job = svc.job([mid], {'scale': 2})
        spy.assert_not_called()                                            # it did not wait for the read
        self.assertFalse(svc.runner.g1u.ready.is_set())
        cap = float(svc.settings.get()['ram_cap_gb'])
        self.assertEqual(job['items'][0]['plan'], planner.with_times(planner.plan_501(640, 480, 2, ram_cap_gb=cap)).to_dict())

    def test_plan_cards_and_a_classic_plan_route_do_not_wait(self):
        svc = self.pending()
        spy = self.waits(svc)
        svc.add(J.strip_input(self.td / 'in', 'wide.png', 4000, 64))        # its plan cards are made now
        self.assertEqual(svc.runner._media_ram_cap(), svc.settings.get()['ram_cap_gb'])
        self.assertEqual(self.route_plan(svc, 640, 480, 2)['status'], 200)
        spy.assert_not_called()
        with mock.patch('service.runner.PLAN_TABLE_WAIT_S', 0.5):
            t0 = time.monotonic()
            self.assertEqual(self.route_plan(svc, 4000, 64, 8)['status'], 200)
            self.assertGreaterEqual(time.monotonic() - t0, 0.4)            # a Large-image size waits (bounded)
        spy.assert_called_once_with(0.5)

    def big_refused(self, svc):
        mid = svc.add(J.strip_input(self.td / 'in', 'big.png', 3500, 2188))
        with mock.patch('service.runner.SUBMIT_TABLE_WAIT_S', 0.1), \
                mock.patch.object(banded_plan, 'probe_widths', create=True, side_effect=lambda *a, **k: [7000, 14000, 28000]):
            with self.assertRaises(ApiError) as e:
                svc.job([mid], {'scale': 8})
        return str(e.exception)

    def test_a_refusal_before_the_table_lands_says_the_engine_is_still_reading(self):
        """8x of 3500 x 2188 is refused at tier 3 before the table lands (the bounded wait ran out): the refusal says the
        engine is still reading its runtime, and asks for no check."""
        svc = self.pending()
        text = self.big_refused(svc)
        self.assertIn(bxf_probe.READING_REFUSED.format(m=bxf_probe.reading_minutes()).strip(), text)
        self.assertNotIn('measures this computer', text)
        self.assertEqual(svc.runner.g1u.requested, {})

    def test_no_reading_sentence_where_the_table_cannot_help(self):
        """A release build (no Large-image size admitted: no wait either) and a card the Large-image engine refuses: 5.0.1's
        refusal only."""
        for case in ('release', 'card'):
            with self.subTest(case=case):
                p = (mock.patch.dict(banded_plan.BANDED_PROVEN_MP, {'ws128': 0.0, 'pc64': 0.0, 'pc48': 0.0}) if case == 'release'
                     else mock.patch.dict(os.environ, {'CU_FAKE_GPU_MEM_GB': '7.99'}))
                with p:
                    svc = self.pending(f'state-{case}')
                    spy = self.waits(svc)
                    text = self.big_refused(svc)
                self.assertNotIn('runtime', text)
                self.assertNotIn('processor', text)
                if case == 'release':
                    spy.assert_not_called()

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
        svc = self.pending()                                               # the read never ends until the test ends
        _, done = in_thread(svc.runner._dispatch)
        self.assertTrue(done.wait(20))                                     # nothing queued: it asks for no check
        mid = svc.add(J.strip_input(self.td / 'in', 'small.png', 640, 480))
        jid = svc.job([mid], {'scale': 2})['id']
        _, done = in_thread(svc.runner._dispatch)
        self.assertTrue(done.wait(20))                                     # a Classic image is admitted and starts
        self.assertFalse(svc.runner.g1u.ready.is_set())
        self.assertEqual(svc.run_all(), [])
        self.done(svc, jid)

    def large_queued(self, svc):
        mid = svc.add(J.strip_input(self.td / 'in', 'wide.png', 4000, 64))
        with mock.patch('service.runner.SUBMIT_TABLE_WAIT_S', 0.1):
            return svc.job([mid], {'scale': 8})['id']

    def assert_waits_outside_the_lock(self, svc, fn, *a):
        spy = self.waits(svc)
        with mock.patch('service.runner.CHANGE_TABLE_WAIT_S', 3.0):
            out, done = in_thread(fn, *a)
            end = time.monotonic() + 20
            while not spy.called and time.monotonic() < end:              # it is waiting for the table now
                time.sleep(0.02)
            self.assertTrue(spy.called)
            self.assertFalse(done.is_set())
            got = svc.runner._lock.acquire(timeout=1.0)
            if got:
                svc.runner._lock.release()
            self.assertTrue(got, 'the wait for the table held Runner._lock')
            self.assertTrue(done.wait(30))
        spy.assert_called_once_with(3.0)                                   # bounded by CHANGE_TABLE_WAIT_S (3 s here)
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


class TheStartReplan(G.ServiceBase):
    """S2: at every start, once the restart's images are queued again, the queued Large-image images are planned again for
    the table that applies now, whether or not it differs from the empty state before it. The check's reproduction: two
    images planned 'bxf' under a committed table (one of them running when the app stopped), then a start on a runtime no
    committed table matches; both orders of the read and the recovery."""

    def earlier_session(self, state):
        svc = self.service(state, env=G.committed_env(1))
        jids = []
        for name, w in (('wide.png', 4000), ('wide2.png', 3000)):
            mid = svc.add(J.strip_input(self.td / 'in', name, w, 64))
            jids.append(svc.job([mid], {'scale': 8})['id'])
        for jid in jids:
            self.assertEqual(svc.item(jid)['plan']['banded']['finish_tier'], 'bxf')
        svc.store.update_item(jids[1], 'i001', state='preparing', if_state={'queued'})   # the app stopped as it started
        svc.store.update_item(jids[1], 'i001', state='running', if_state={'preparing'})
        return jids

    def runs_at_tier_3(self, svc, jids):
        for jid in jids:
            self.assertEqual(svc.item(jid)['state'], 'queued')
            self.assertEqual(tier_soon(svc, jid, 'tier3'), 'tier3')
        self.assertEqual(svc.run_all(), [])
        for jid in jids:
            self.done(svc, jid)
        ev = [e['event'] for e in svc.events()]
        self.assertNotIn('bxf_table_gone', ev)
        self.assertGreaterEqual(ev.count('item_replanned'), 2)

    def test_the_read_lands_before_the_recovery(self):
        jids = self.earlier_session('state-a')
        real = bxf_probe.G1u.start
        with mock.patch.object(bxf_probe.G1u, 'start', lambda g, background=True: real(g, background=False)):
            svc = self.service('state-a', env=G.unmatched_env())
        self.runs_at_tier_3(svc, jids)

    def test_the_recovery_comes_before_the_read(self):
        jids = self.earlier_session('state-b')
        env = G.unmatched_env()

        def slow():
            time.sleep(0.5)
            return dict(env)
        svc = self.service('state-b', env=slow)
        self.runs_at_tier_3(svc, jids)

    def test_a_failing_re_plan_never_stops_the_start(self):
        """recover() runs the start re-plan when the table was already assigned; an error in it is logged, and the service
        starts with its images recovered (as on the G1u thread)."""
        jids = self.earlier_session('state-d')
        real = bxf_probe.G1u.start
        with mock.patch.object(bxf_probe.G1u, 'start', lambda g, background=True: real(g, background=False)), \
                mock.patch('service.runner.Runner._bxf_table_changed', side_effect=RuntimeError('a stand-in error')):
            svc = self.service('state-d', env=G.unmatched_env())
        self.assertEqual(svc.item(jids[1])['state'], 'queued')               # the recovery itself was done
        self.assertEqual([e['event'] for e in svc.events()].count('bxf_replan_failed'), 2)   # the G1u call and recover()'s

    def test_a_start_with_the_same_table_changes_nothing(self):
        jids = self.earlier_session('state-c')
        svc = self.service('state-c', env=G.committed_env(1))
        time.sleep(0.3)
        for jid in jids:
            self.assertEqual(svc.item(jid)['plan']['banded']['finish_tier'], 'bxf')
        self.assertNotIn('item_replanned', [e['event'] for e in svc.events()])


class TheLastGuard(G.GlobalsRestored):
    """S2: a plan that counted the table, on a start whose read failed: the runtime is read once more on the image's own
    thread before the image is failed, once a session."""
    PLAN = {'engine': 'banded', 'banded': {'finish_tier': 'bxf', 'bxf_table': 'committed'}}

    def g1u(self, td, env_fn):
        bxf_probe.TEST_ENVIRONMENT = env_fn
        g = bxf_probe.G1u(SimpleNamespace(state_dir=Path(td), fake_engine=True), G.Log(), fake=True)
        g.start(background=False)
        self.assertIsNone(g.env)
        return g

    def test_read_again_before_the_image_fails(self):
        calls = []

        def env():
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError('the read timed out')
            return G.committed_env(1)
        with tempfile.TemporaryDirectory() as td:
            g = self.g1u(td, env)
            banded_runner.check_table(SimpleNamespace(g1u=g), self.PLAN)      # the table applies now: the pass goes on
            self.assertEqual(len(calls), 2)
            self.assertEqual(g.source, 'committed')
            self.assertIs(banded_plan.BXF_TABLE, g.table)

    def test_once_a_session(self):
        calls = []

        def env():
            calls.append(1)
            raise RuntimeError('the read failed')
        with tempfile.TemporaryDirectory() as td:
            g = self.g1u(td, env)
            for _ in range(2):
                with self.assertRaises(ItemFailure) as e:
                    banded_runner.check_table(SimpleNamespace(g1u=g), self.PLAN)
                self.assertEqual(e.exception.text, banded_runner.TABLE_GONE)
            self.assertEqual(len(calls), 2)                                   # the start's read and one more


class TheCheckSentence(StubRunner):
    """S4: the sentence about the processor check, and the check itself, come only with a refusal the check can lift: the
    planner's or the memory cap's, on a card in use that takes a Large-image result of that size."""

    def refused(self, svc, w, h, widths, scale=8):
        mid = svc.add(J.strip_input(self.td / 'in', f'img{w}x{h}.png', w, h))
        with mock.patch.object(banded_plan, 'probe_widths', create=True, side_effect=lambda *a, **k: list(widths)):
            with self.assertRaises(ApiError) as e:
                svc.job([mid], {'scale': scale})
        return str(e.exception)

    def on_card(self, gb, state):
        p = mock.patch.dict(os.environ, {'CU_FAKE_GPU_MEM_GB': gb})
        p.start()
        self.addCleanup(p.stop)
        return self.service(state, env=self.env, probe=self.stub.command)

    def test_a_card_refusal_gains_no_sentence_and_asks_for_no_check(self):
        """The check's reproduction: an 8 GB class card, no committed table, 8x of 4000 x 64 (the plan fits memory; the
        card refuses it)."""
        svc = self.on_card('7.99', 'state-8')
        text = self.refused(svc, 4000, 64, [8000, 16000, 32000])
        self.assertIn('graphics card', text)
        self.assertNotIn('processor', text)
        self.assertIsNone(svc.runner.g1u.pending_request())

    def test_a_planner_refusal_on_a_card_the_engine_refuses_by_its_class(self):
        for gb in ('5.99', '7.99', '10.99'):                       # under 8 GB, and the 8 GB class (10 and 11 GB cards too)
            with self.subTest(card=gb):
                svc = self.on_card(gb, f'state-{gb}')
                text = self.refused(svc, 3500, 2188, [7000, 14000, 28000])
                self.assertNotIn('processor', text)
                self.assertIsNone(svc.runner.g1u.pending_request())

    def test_a_result_over_every_cards_render_limit(self):
        """8x of 4000 x 3200 is 819 MP: over a 12 GB card's render limit (805 MP), under a 16 GB card's (1,074 MP)."""
        from engine import vram_model
        self.assertLess(vram_model.render_limit_mp(12), 32000 * 25600 / 1e6)
        self.assertGreater(vram_model.render_limit_mp(16), 32000 * 25600 / 1e6)
        svc = self.on_card('11.99', 'state-12')
        text = self.refused(svc, 4000, 3200, [8000, 16000, 32000])
        self.assertNotIn('processor', text)
        self.assertIsNone(svc.runner.g1u.pending_request())
        svc = self.on_card('15.99', 'state-16')
        text = self.refused(svc, 4000, 3200, [8000, 16000, 32000])
        self.assertIn('The app measures this computer\'s processor', text)    # a card that takes it: the check helps
        self.assertEqual(svc.runner.g1u.pending_request(), ([8000, 16000, 32000], 6.0))


class WhileTheCheckRuns(StubRunner):
    """S3: while the processor check runs nothing starts, and every queued image (Classic ones and those queued during it
    too) says so with the check's remaining upper bound, written only when it changes; when it ends they all say Waiting."""

    def test_every_queued_image_says_why_and_for_how_long(self):
        svc = self.service(env=self.env, probe=self.stub.command)
        self.stub.mode('sleep')
        j1 = self.queued(svc)                                             # a Large-image image at tier 3: the check starts
        with mock.patch.object(bxf_probe, 'probe_seconds', return_value=125.0), \
                mock.patch.object(bxf_probe, 'PROBE_KILL_GRACE_S', 0.0):
            svc.runner._dispatch()
            self.assertIsNotNone(svc.runner._probe_thread)
            mid = svc.add(J.strip_input(self.td / 'in', 'small.png', 640, 480))
            j2 = svc.job([mid], {'scale': 2})['id']                       # a Classic image queued during the check
            svc.runner._dispatch()
            self.assertEqual(svc.runner.ctx, {})
            self.assertEqual(svc.item(j1)['message'], bxf_probe.PROBE_WAITING.format(m=3))
            self.assertEqual(svc.item(j2)['message'], bxf_probe.PROBE_HELD.format(m=3))
            with mock.patch.object(svc.store, 'update_item', wraps=svc.store.update_item) as up, \
                    mock.patch.object(svc.store, 'item', wraps=svc.store.item) as read:
                for _ in range(5):
                    svc.runner._dispatch()
            self.assertEqual((up.call_count, read.call_count), (0, 0))   # nothing changed: no store reads or writes
            svc.runner._probe_t0 -= 70.0                                  # 70 s later: 55 s left
            svc.runner._dispatch()
            self.assertEqual(svc.item(j1)['message'], bxf_probe.PROBE_WAITING.format(m=1))
            self.assertEqual(svc.item(j2)['message'], bxf_probe.PROBE_HELD.format(m=1))
            svc.runner.g1u.stop()                                          # the check ends
            self.join_probe(svc)
        for jid in (j1, j2):
            self.assertEqual(svc.item(jid)['message'], 'Waiting')

    def test_an_image_queued_behind_a_check_a_refusal_asked_for(self):
        svc = self.service(env=self.env, probe=self.stub.command)
        self.stub.mode('sleep')
        g = svc.runner.g1u
        g.request([16000], 6.0)
        with mock.patch.object(bxf_probe, 'probe_seconds', return_value=125.0), \
                mock.patch.object(bxf_probe, 'PROBE_KILL_GRACE_S', 0.0):
            svc.runner._dispatch()                                        # nothing queued or running: the check starts
            self.assertIsNotNone(svc.runner._probe_thread)
            mid = svc.add(J.strip_input(self.td / 'in', 'small.png', 640, 480))
            jid = svc.job([mid], {'scale': 2})['id']
            svc.runner._dispatch()
            self.assertEqual(svc.item(jid)['message'], bxf_probe.PROBE_HELD.format(m=3))
            g.stop()
            self.join_probe(svc)
        self.assertEqual(svc.item(jid)['message'], 'Waiting')

    def test_the_figure_before_the_images_ahead_is_the_checks_own(self):
        self.assertIn('The check itself takes up to about {m} minutes', bxf_probe.PROBE_WAITING_OTHERS)


if __name__ == '__main__':
    unittest.main()
