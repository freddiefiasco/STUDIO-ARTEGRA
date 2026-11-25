"""5.0.2 build wave 4, service package, check W4S-C1: when the stop after a Large-image image fails, the engine is never used
again and nothing starts beside it.

The stop after a Large-image image (banded_runner.release_engine) can fail two ways: (a) it raises before the engine is
touched (the lock-timeout fallback's proc.close), so the engine stays 'ready'; (b) it raises in the teardown (proc.close,
ws.stop or the fake's stop), so the engine stays 'stopping'. Either way the worker still holds the process, which may be alive
with that image's Large-image memory. The rule: a marked, live engine is never claimable. Its record says stopped False with
a failure sentence (never RELEASE_TEXT), it keeps its mark, stopped_after_large stays unset, and it is kept out of use
(workers.Worker.hold_kept: state 'failed' with the start back-off). Its next start closes it first and refuses while it
cannot (Worker._close_marked). The fallback guard (BUILD-WAVE-4 service scope) restarts an engine that still carries a
mark before an image's first prompt (banded_runner.restart_previous, through restart_worker, why 'previous_job'), and stops
it before a protected-area preview; when the stop fails again the image fails plainly and the preview is refused.

In this process on the fake engine, with the recording client of tests/test_service4_engine_release.py. Each test checks the
invariant there (no prompt goes to an engine process that was sent another image's Large-image prompt) and, at every start
of a fake engine, that no other fake engine of that card is still alive. Sizes and synthetic pictures only."""
import os
import time
import unittest
from types import SimpleNamespace
from unittest import mock

from service import banded_runner, engine_options, gpu_policy, memory_policy, workers
from service.errors import ApiError
from service.runner import Runner
import tests.test_integ_large_image_job as J
import tests.test_service4_engine_release as E

KEPT = banded_runner.RELEASE_KEPT_TEXT
RUN_S = 120              # each run_all here takes seconds; a broken rule that keeps an image waiting ends at this bound


class Fault:
    """The stop of an engine fails while `on`: way 'a' raises at the entry of Worker._stop_locked (the engine is left as it
    was, 'ready'; every stop path and the close in ensure_started go through it), way 'b' raises in Worker._teardown (the
    engine is left 'stopping')."""

    def __init__(self, way):
        self.way, self.on, self.raised = way, False, 0
        real = {'a': workers.Worker._stop_locked, 'b': workers.Worker._teardown}[way]
        fault = self

        def failing(w, *args, **kw):
            if fault.on:
                fault.raised += 1
                raise OSError('the Job could not be closed (test)')
            return real(w, *args, **kw)
        self.patch = mock.patch.object(workers.Worker, '_stop_locked' if way == 'a' else '_teardown', failing)


class Base(E.Base):
    def setUp(self):
        super().setUp()
        p = mock.patch.dict(os.environ, {'CU_START_BACKOFF_SECONDS': '0'})    # the kept engine is tried again at once
        p.start()
        self.addCleanup(p.stop)
        self.beside = []                     # (card, the fake engines of that card still alive) at each start
        real_start = J.InProcessFake.start
        beside = self.beside

        def start(fake):
            alive = [f for f in J.InProcessFake.registry.values() if f.alive and f.gpu == fake.gpu]
            if alive:
                beside.append((fake.gpu, len(alive)))
            return real_start(fake)
        p2 = mock.patch.object(J.InProcessFake, 'start', start)
        p2.start()
        self.engine.append(p2)

    def fault(self, way):
        f = Fault(way)
        f.patch.start()
        self.addCleanup(f.patch.stop)
        return f

    def fail_at_release(self, f):
        """The fault goes on when the stop after the Large-image image begins (the image's own passes stop as usual)."""
        real = banded_runner.release_engine

        def release(r, w, ctx, why='large_image_ended', **kw):
            if why == 'large_image_ended':
                f.on = True
            return real(r, w, ctx, why=why, **kw)
        p = mock.patch.object(banded_runner, 'release_engine', release)
        p.start()
        self.addCleanup(p.stop)

    def kept_after_large(self, svc, f, w=None):
        """A Large-image image whose engine stop fails: the image is done, the engine is kept with its mark."""
        w = w or svc.worker
        _, big = self.large(svc)
        key = self.key(big)
        self.fail_at_release(f)
        self.assertEqual(svc.run_all(RUN_S), [])
        self.assertTrue(f.on)
        self.done(svc, big['id'])
        rel = [e for e in self.released(svc) if e['job'] == key[0]]
        self.assertEqual(len(rel), 1)
        self.assertIs(rel[0]['data']['stopped'], False)
        self.assertEqual(rel[0]['level'], 'error')
        self.assertEqual(rel[0]['msg'], KEPT.format(where=w.where()))
        self.assertNotEqual(rel[0]['msg'], banded_runner.RELEASE_TEXT.format(where=w.where()))
        self.assertEqual(rel[0]['data']['commit_check'], 'unmeasured')
        self.assertEqual(w.banded_sent, key)                     # the mark is kept
        self.assertEqual(w.banded_kept, KEPT.format(where=w.where()))
        self.assertFalse(w.stopped_after_large)
        self.assertEqual(w.state, 'failed')
        self.assertEqual(w.problem, KEPT.format(where=w.where()))
        self.assertTrue(w.alive())                               # the fake engine was never stopped
        return key, w.fake

    def check_kept(self, svc, old, starts, w=None):
        w = w or svc.worker
        self.assertIs(w.fake, old)
        self.assertTrue(old.alive)
        self.assertEqual(w.starts, starts)
        self.assertEqual(self.beside, [])
        self.assertEqual(E.violations(), [])


class EachWay:
    """Both ways the stop can fail, the next image and a preview while it still fails, then after it works again."""
    way = None

    def test_never_used_and_nothing_beside_it_while_the_stop_fails(self):
        f = self.fault(self.way)
        svc = self.service()
        key, old = self.kept_after_large(svc, f)
        starts = svc.worker.starts
        m1, c1 = self.classic(svc)                       # the next image: the fallback's restart fails, so it fails plainly
        self.assertEqual(svc.run_all(RUN_S), [])
        it = svc.item(c1['id'])
        self.assertEqual(it['state'], 'failed')
        n = len(it['plan']['stages'])
        self.assertEqual(it['message'], banded_runner.RESTART_BEFORE_FAILED.format(k=1, n=n))
        self.assertFalse([r for r in E.Recorder.log if r['owner'] == self.key(c1)])     # it sent nothing
        self.check_kept(svc, old, starts)
        with self.assertRaises(ApiError) as cm:          # a preview is refused in plain words
            svc.runner.mask_preview(m1, protect=['people'])
        self.assertEqual((cm.exception.status, cm.exception.code), (503, 'engine_not_ready'))
        self.assertEqual(cm.exception.message, KEPT.format(where=svc.worker.where()))
        self.assertFalse([r for r in E.Recorder.log if r['owner'] and r['owner'][0] == 'preview'])
        self.check_kept(svc, old, starts)
        # the scheduler's own resets of a failed engine (nothing waiting, or Retry) do not make it usable
        svc.runner._reset_worker(svc.worker, 'nothing is waiting for it')
        self.assertEqual(svc.worker.state, 'stopped')
        _, c2 = self.classic(svc, 'b.png', 300, 200, seed=3)
        self.assertEqual(svc.run_all(RUN_S), [])
        self.assertEqual(svc.item(c2['id'])['state'], 'failed')
        self.check_kept(svc, old, starts)
        self.assertGreater(f.raised, 0)
        f.on = False                                     # the stop works again: the next image starts in a fresh engine
        calls = []
        real = svc.runner._active_update

        def update(jid, iid, **fields):
            if fields.get('message') == 'Starting the engine':
                calls.append((jid, dict(fields)))
            return real(jid, iid, **fields)
        svc.runner._active_update = update
        _, c3 = self.classic(svc, 'c.png', 256, 192, seed=4)
        self.assertEqual(svc.run_all(RUN_S), [])
        it = self.done(svc, c3['id'])
        self.assert_fresh(self.key(c3))
        self.assertFalse(old.alive)
        self.assertIsNone(svc.worker.banded_sent)
        self.assertIsNone(svc.worker.banded_kept)
        self.assertEqual(svc.worker.starts, starts + 1)
        self.assertEqual(self.beside, [])
        self.assertEqual(E.violations(), [])
        prev = [e for e in self.released(svc) if e['data'].get('why') == 'previous_job' and e['job'] == c3['id']]
        self.assertEqual(len(prev), 1)
        self.assertIs(prev[0]['data']['stopped'], True)
        self.assertEqual(prev[0]['data']['previous'], list(key))
        self.assertTrue(set(E.CONTRACT) <= set(prev[0]['data']), prev[0]['data'])
        rb = it['timings'].get('restart_before') or {}
        self.assertEqual((rb.get('why'), rb.get('index')), ('previous_job', 0))
        minutes = sum(s['minutes'] for s in it['plan']['stages'])        # the start it says counts the engine start
        self.assertEqual([fl for j, fl in calls if j == c3['id']],
                         [{'message': 'Starting the engine',
                           'eta_s': engine_options.start_eta_s(minutes, float(it['run']['factor']))}])

    def test_a_preview_after_the_stop_works_again(self):
        f = self.fault(self.way)
        svc = self.service()
        m1 = svc.add(J.strip_input(self.td / 'in', 'p.png', 320, 240, seed=5))
        key, old = self.kept_after_large(svc, f)
        f.on = False
        self.assertFalse(svc.runner.mask_preview(m1, protect=['people'])['cached'])
        self.assert_fresh(next(r['owner'] for r in E.Recorder.log if r['owner'] and r['owner'][0] == 'preview'))
        self.assertFalse(old.alive)
        self.assertEqual(self.beside, [])
        self.assertEqual(E.violations(), [])
        prev = [e for e in self.released(svc) if e['data'].get('why') == 'previous_job']
        self.assertEqual([(e['data']['stopped'], e['data']['previous']) for e in prev], [(True, list(key))])

    def test_the_next_large_image_image_records_the_restart_on_its_first_prompt(self):
        f = self.fault(self.way)
        svc = self.service()
        key, old = self.kept_after_large(svc, f)
        f.on = False
        _, big = self.large(svc, 'next.png', seed=6)
        self.assertEqual(svc.run_all(RUN_S), [])
        it = self.done(svc, big['id'])
        self.assert_fresh(self.key(big))
        self.assertEqual(E.violations(), [])
        first = next(x for x in it['timings']['stages'] if x.get('index') == 0)
        self.assertEqual((first.get('restart_before') or {}).get('why'), 'previous_job')


class InTheMiddleOfTheImage(Base):
    def test_its_own_restart_and_the_kill_fail(self):
        """The Large-image image's own restart between its passes (contracts.restart) cannot stop the engine, and the kill
        its failure asks for fails too: the image fails plainly (never left active with no thread), the engine is kept,
        and the next image never runs in it nor beside it."""
        f = self.fault('b')
        svc = self.service()
        _, big = self.large(svc)
        f.on = True
        self.assertEqual(svc.run_all(RUN_S), [])                      # no item thread ended without its record
        it = svc.item(big['id'])
        self.assertEqual(it['state'], 'failed')
        self.assertTrue(it['message'].startswith('The Large-image engine could not be restarted'), it['message'])
        rel = [e for e in self.released(svc) if e['job'] == big['id']]
        self.assertEqual([(e['data']['stopped'], e['msg']) for e in rel], [(False, KEPT.format(where='GPU 1'))])
        old, starts = svc.worker.fake, svc.worker.starts
        _, c1 = self.classic(svc)
        self.assertEqual(svc.run_all(RUN_S), [])
        self.assertEqual(svc.item(c1['id'])['state'], 'failed')
        self.check_kept(svc, old, starts)
        f.on = False
        _, c2 = self.classic(svc, 'b.png', 300, 200, seed=3)
        self.assertEqual(svc.run_all(RUN_S), [])
        self.done(svc, c2['id'])
        self.assert_fresh(self.key(c2))
        self.assertFalse(old.alive)
        self.assertEqual(E.violations(), [])
        self.assertEqual(self.beside, [])


class WayA(EachWay, Base):
    """(a) the stop raises before the engine is touched: the engine stays 'ready' and alive."""
    way = 'a'


class WayB(EachWay, Base):
    """(b) the stop raises in the teardown: the engine stays 'stopping' and alive."""
    way = 'b'


class ASharedImage(Base):
    ram_gb = J.RAM_WS

    def test_a_kept_shared_engine_keeps_every_card(self):
        """A shared Large-image image whose one engine (MultiCardWorker, both cards) cannot be stopped: a preview finds no
        card to use and is refused plainly (no lane engine starts on its cards beside it), and the next shared image fails
        plainly until the stop works; then it starts in a fresh shared engine."""
        f = self.fault('b')
        svc = E.TwoCards(self.td / 'state', self.ram_gb, split=True)
        _, big = self.large(svc)
        self.fail_at_release(f)
        self.assertEqual(svc.run_all(RUN_S), [])
        self.done(svc, big['id'])
        mw = svc.runner.multi.get((0, 1))
        self.assertIsNotNone(mw)
        self.assertIsNotNone(mw.banded_kept)
        old = mw.fake
        self.assertTrue(old.alive)
        m1 = svc.add(J.strip_input(self.td / 'in', 'p.png', 320, 240, seed=5))
        with self.assertRaises(ApiError) as cm:
            svc.runner.mask_preview(m1, protect=['people'])
        self.assertEqual((cm.exception.status, cm.exception.code), (503, 'engine_not_ready'))
        self.assertIs(svc.runner.multi.get((0, 1)), mw)          # never popped: its handle is kept
        self.assertFalse(svc.worker.alive() or svc.worker1.alive())
        _, c1 = self.classic(svc)
        self.assertEqual(svc.run_all(RUN_S), [])
        self.assertEqual(svc.item(c1['id'])['state'], 'failed')
        self.assertTrue(old.alive)
        self.assertEqual(self.beside, [])
        self.assertEqual(E.violations(), [])
        f.on = False
        _, c2 = self.classic(svc, 'b.png', 300, 200, seed=3)
        self.assertEqual(svc.run_all(RUN_S), [])
        self.done(svc, c2['id'])
        self.assert_fresh(self.key(c2))
        self.assertFalse(old.alive)
        self.assertEqual(self.beside, [])
        self.assertEqual(E.violations(), [])

    def test_a_kept_shared_engine_waits_out_its_back_off(self):
        """While a kept shared engine's back-off runs, the scheduler neither stops it again nor starts anything on its
        cards, whether the next image would be shared, run on one card in lanes, or the split is off."""
        f = self.fault('a')
        with mock.patch.dict(os.environ, {'CU_START_BACKOFF_SECONDS': '600'}):
            svc = E.TwoCards(self.td / 'state', self.ram_gb, split=True)
            _, big = self.large(svc)
            self.fail_at_release(f)
            self.assertEqual(svc.run_all(RUN_S), [])
        self.done(svc, big['id'])
        mw = svc.runner.multi.get((0, 1))
        self.assertIsNotNone(mw.banded_kept)
        self.assertGreater(mw.next_start_after - time.monotonic(), 60)
        old, raised = mw.fake, f.raised
        _, c1 = self.classic(svc)
        for mode, topo in (('1', gpu_policy.Topology('split', [(0, 1)])), ('1', gpu_policy.Topology('lanes', [(0,), (1,)])),
                           ('0', None)):
            with mock.patch.dict(os.environ, {'CU_SPLIT_TEST': mode}), \
                    mock.patch.object(gpu_policy, 'plan_topology', lambda *a, topo=topo, **k: topo):
                svc.runner._dispatch()
            self.assertEqual(svc.runner.threads, {}, mode)
            self.assertEqual(f.raised, raised, mode)                 # not stopped again meanwhile
        self.assertEqual(svc.item(c1['id'])['state'], 'queued')
        self.assertTrue(old.alive)
        self.assertFalse(svc.worker.alive() or svc.worker1.alive())
        self.assertEqual(self.beside, [])
        svc.runner.cancel_item(*self.key(c1))


class TheBackOff(Base):
    def test_a_kept_engine_waits_out_its_back_off(self):
        """While a kept engine's back-off runs, the scheduler neither stops it again nor gives it an image."""
        f = self.fault('a')
        svc = self.service()
        with mock.patch.dict(os.environ, {'CU_START_BACKOFF_SECONDS': '600'}):
            svc.worker.backoff_s = 600.0
            key, old = self.kept_after_large(svc, f)
        self.assertGreater(svc.worker.next_start_after - time.monotonic(), 60)
        raised = f.raised
        _, c1 = self.classic(svc)
        for _ in range(3):
            svc.runner._dispatch()
        self.assertEqual(svc.runner.threads, {})
        self.assertEqual(svc.item(c1['id'])['state'], 'queued')
        self.assertEqual(f.raised, raised)                     # not stopped again meanwhile
        self.assertTrue(old.alive)
        self.assertEqual(svc.runner._kept_waiting([svc.worker]), True)
        svc.runner.cancel_item(*self.key(c1))


# --- the worker's own rule (workers.Worker), the record (banded_runner.release_engine) and admission ----------------------
class TheWorkersRule(Base):
    def worker(self):
        svc = self.service()
        svc.worker.ensure_started()
        return svc, svc.worker

    def test_a_marked_engine_is_closed_before_it_is_used(self):
        """ensure_started never hands back an engine process that was sent a Large-image prompt: it is closed and a fresh
        one is started (no caller does so mid-image)."""
        svc, w = self.worker()
        old = w.fake
        w.banded_sent = ('j1', 'i001')
        w.ensure_started()
        self.assertFalse(old.alive)
        self.assertIsNot(w.fake, old)
        self.assertIsNone(w.banded_sent)
        self.assertEqual(w.starts, 2)
        self.assertEqual(self.beside, [])

    def test_a_kept_engine_that_cannot_be_closed_is_never_started_beside(self):
        f = self.fault('b')
        svc, w = self.worker()
        old = w.fake
        w.banded_sent = ('j1', 'i001')
        f.on = True
        with self.assertRaises(workers.WorkerError) as cm:
            w.ensure_started()
        self.assertEqual(str(cm.exception), KEPT.format(where=w.where()))
        self.assertIs(w.fake, old)
        self.assertTrue(old.alive)
        self.assertEqual((w.state, w.starts, w.banded_sent), ('failed', 1, ('j1', 'i001')))
        self.assertEqual(w.banded_kept, KEPT.format(where=w.where()))
        f.on = False
        w.ensure_started()
        self.assertFalse(old.alive)
        self.assertEqual((w.state, w.starts, w.banded_sent, w.banded_kept), ('ready', 2, None, None))
        self.assertEqual(self.beside, [])

    def test_a_marked_engine_whose_stop_raises_is_kept(self):
        f = self.fault('a')
        svc, w = self.worker()
        w.banded_sent = ('j1', 'i001')
        f.on = True
        with self.assertRaises(OSError):
            w.stop('test')
        self.assertEqual((w.state, w.banded_kept), ('failed', KEPT.format(where=w.where())))
        self.assertGreater(w.next_start_after, 0.0)

    def test_an_unmarked_engine_whose_stop_raises_is_as_in_5_0_1(self):
        f = self.fault('a')
        svc, w = self.worker()
        f.on = True
        with self.assertRaises(OSError):
            w.stop('test')
        self.assertEqual((w.state, w.banded_kept, w.next_start_after), ('ready', None, 0.0))


# --- eng:check CHK-3 (W4S-F1): the real Job close that raises, on a fake kernel32 -------------------------------------------
JOB = 0x5A5A                 # the fake Job handle


class FakeJobApi:
    """The kernel32 calls service/windows_job.WindowsJobProcess.close makes, on a fake Job: the Job queries raise
    `query_raises` (an error that is not ProcessContainmentError, so the close raises it) or report no process left;
    CloseHandle(job) succeeds, fails (returns 0) or raises."""

    def __init__(self, query_raises=None, close='ok'):
        self.query_raises, self.close = query_raises, close
        self.closed, self.terminated = [], 0

    def QueryInformationJobObject(self, job, cls, info, size, ret):
        if self.query_raises is not None:
            raise self.query_raises
        return 1                      # the structure stays zero: no process active, no peak

    def TerminateJobObject(self, job, code):
        self.terminated += 1
        return 1

    def CloseHandle(self, handle):
        self.closed.append(handle)
        if handle == JOB and self.close == 'raises':
            raise OSError('CloseHandle (test)')
        return 0 if handle == JOB and self.close == 'fails' else 1


def job_process(api):
    """A WindowsJobProcess holding the fake Job (no process is started; the root's handle is not held)."""
    import threading
    from service import windows_job
    p = object.__new__(windows_job.WindowsJobProcess)
    p._lock, p.api, p.job, p.process, p.pid, p.cleanup = threading.RLock(), api, JOB, None, 4242, None
    p.command, p.memory_limit_bytes, p.parent_job = ['engine.exe'], None, None
    return p


ON_WINDOWS = unittest.skipUnless(os.name == 'nt', 'the failed CloseHandle reads the Windows error text')


class TheJobCloseRecordsItsCleanup(unittest.TestCase):
    """windows_job.WindowsJobProcess.close writes its cleanup record before it raises again, so a second close returns what
    the first did (until eng:check CHK-3 it returned a record that knew nothing: processes not ended, no error, the handle
    'closed' whatever CloseHandle said)."""

    def test_a_close_that_raises_with_the_handle_closed(self):
        api = FakeJobApi(query_raises=OSError('the Job query failed (test)'))
        p = job_process(api)
        with self.assertRaises(OSError):
            p.close()
        rec = p.cleanup
        self.assertIsNotNone(rec)                                  # recorded before the error went on
        self.assertEqual((rec['job_handle'], rec['job_handle_closed']), ('closed', True))
        self.assertEqual(rec['raised'], 'OSError: the Job query failed (test)')
        self.assertIn(rec['raised'], rec['errors'])
        self.assertIs(rec['all_owned_processes_terminated'], False)
        self.assertIsNone(rec['active_processes_before_final_close'])       # never counted
        self.assertEqual(api.closed, [JOB])
        self.assertIsNone(p.job)
        self.assertIs(p.close(), rec)                               # the second close returns that record, never raises
        self.assertEqual(api.closed, [JOB])                         # and closes nothing twice

    @ON_WINDOWS
    def test_a_close_that_raises_and_whose_handle_did_not_close(self):
        api = FakeJobApi(query_raises=OSError('the Job query failed (test)'), close='fails')
        p = job_process(api)
        with self.assertRaises(OSError):
            p.close()
        rec = p.close()
        self.assertEqual((rec['job_handle'], rec['job_handle_closed']), ('close_failed', False))
        self.assertEqual(rec['raised'], 'OSError: the Job query failed (test)')
        self.assertTrue(any(e.startswith('CloseHandle(job) failed') for e in rec['errors']), rec['errors'])
        self.assertIs(rec['all_owned_processes_terminated'], False)

    def test_a_close_handle_that_raises_reads_as_not_closed(self):
        api = FakeJobApi(query_raises=OSError('the Job query failed (test)'), close='raises')
        p = job_process(api)
        with self.assertRaises(OSError) as cm:
            p.close()
        self.assertEqual(str(cm.exception), 'the Job query failed (test)')    # the close's own error, not CloseHandle's
        rec = p.close()
        self.assertEqual((rec['job_handle'], rec['job_handle_closed']), ('close_failed', False))
        self.assertIn('CloseHandle(job): OSError: CloseHandle (test)', rec['errors'])

    @ON_WINDOWS
    def test_a_close_that_returns_says_whether_the_handle_closed(self):
        p = job_process(FakeJobApi(close='fails'))
        rec = p.close()
        self.assertEqual((rec['job_handle'], rec['job_handle_closed'], rec['raised']), ('close_failed', False, None))
        self.assertIs(rec['all_owned_processes_terminated'], False)
        p = job_process(FakeJobApi())
        rec = p.close()
        self.assertEqual((rec['job_handle'], rec['job_handle_closed'], rec['raised']), ('closed', True, None))
        self.assertIs(rec['all_owned_processes_terminated'], True)
        self.assertEqual(rec['active_processes_before_final_close'], 0)

    def test_no_job_handle_held(self):
        p = job_process(FakeJobApi())
        p.job = None
        rec = p.close()
        self.assertEqual((rec['job_handle'], rec['job_handle_closed']), ('none', True))


class TheJobCloseThatRaises(unittest.TestCase):
    """The stop after a Large-image image when the real Job close raises (eng:check CHK-3, W4S-F1; until then this class
    pinned a trace in which the record could not tell the two outcomes apart and the next start always went ahead). The
    first stop raises in proc.close, which records its cleanup; the kill's teardown gets that record and drops the handle.
    - The Job handle closed: the kill-on-close Job ended the tree, so the record says ended_by_job_close and the engine is
      released as before (stopped False, RELEASE_UNCONFIRMED, the next start goes ahead).
    - The Job handle did not close: never a silent release. The record says kept_until_restart with RELEASE_KEPT_TEXT, and
      no engine starts on that card again in this service, whichever worker asks for it, until the app restarts."""

    def setUp(self):
        import tempfile
        from pathlib import Path
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.cfg = SimpleNamespace(workers_dir=Path(td.name), state_dir=Path(td.name))
        self.settings = SimpleNamespace(get=lambda: {'ram_cap_gb': 59.0, 'memory_profile': 'auto'})
        self.addCleanup(lambda: [workers.LOST_CARDS.pop(k) for k in list(workers.LOST_CARDS)
                                 if k[0] == str(self.cfg.workers_dir)])

    def release(self, close):
        api = FakeJobApi(query_raises=OSError('TerminateJobObject failed (test)'), close=close)
        w = workers.Worker(0, self.cfg, self.settings, mock.Mock(), 'comfy')
        w.proc, w.state, w.banded_sent = job_process(api), 'ready', ('j1', 'i001')
        r = SimpleNamespace(mode='comfy', shared_job=None, workers={0: w}, multi={}, accepting=True, log=mock.Mock())
        rec = banded_runner.release_engine(r, w, SimpleNamespace(jid='j1', iid='i001', shutdown=False), settle_s=0.1)
        self.assertEqual(api.closed, [JOB])                    # the first close closed the handle once; the second closed nothing
        self.assertIs(rec['stopped'], False)                   # the pinned contract field: no process was counted ended
        self.assertIs(rec['cleanup']['all_owned_processes_terminated'], False)
        self.assertEqual(rec['cleanup']['raised'], 'OSError: TerminateJobObject failed (test)')
        self.assertIsNone(w.proc)
        ev = [c for c in r.log.error.call_args_list if c.args and c.args[0] == E.RELEASED]
        return w, rec, [c.args[1] for c in ev]

    def test_the_job_handle_closed(self):
        w, rec, said = self.release('ok')
        self.assertEqual((rec['job_handle'], rec['ended_by_job_close'], rec['kept_until_restart']), ('closed', True, False))
        self.assertEqual((w.banded_sent, w.banded_kept, w.state, w.stopped_after_large), (None, None, 'stopped', True))
        self.assertEqual(said, [banded_runner.RELEASE_FAILED_TEXT.format(where='GPU 1',
                                                                         error=banded_runner.RELEASE_UNCONFIRMED)])
        self.assertIsNone(w.lost_text())
        with mock.patch.object(workers.Worker, '_start') as start:
            w.ensure_started()
        start.assert_called_once()                             # the tree ended with the handle: the next start goes ahead

    @ON_WINDOWS
    def test_the_job_handle_did_not_close(self):
        w, rec, said = self.release('fails')
        kept = KEPT.format(where='GPU 1')
        self.assertEqual((rec['job_handle'], rec['ended_by_job_close'], rec['kept_until_restart']),
                         ('close_failed', False, True))
        self.assertEqual(said, [kept])                         # never RELEASE_UNCONFIRMED's silent release
        self.assertEqual((w.banded_sent, w.stopped_after_large), (None, False))
        self.assertEqual(w.lost_text(), kept)
        with mock.patch.object(workers.Worker, '_start') as start:
            for _ in range(2):
                with self.assertRaises(workers.WorkerError) as cm:
                    w.ensure_started()
                self.assertEqual(str(cm.exception), kept)
                self.assertEqual((w.state, w.problem), ('failed', kept))
                self.assertGreater(w.next_start_after, 0.0)
            # another worker for the same card (after Settings dropped and re-added it), or a shared engine over it
            again = workers.Worker(0, self.cfg, self.settings, mock.Mock(), 'comfy')
            shared = workers.MultiCardWorker([0, 1], self.cfg, self.settings, mock.Mock(), 'comfy')
            for x in (again, shared):
                with self.assertRaises(workers.WorkerError) as cm:
                    x.ensure_started()
                self.assertEqual(str(cm.exception), kept)
            start.assert_not_called()
            workers.Worker(1, self.cfg, self.settings, mock.Mock(), 'comfy').ensure_started()      # the other card
            other_service = SimpleNamespace(workers_dir=self.cfg.workers_dir / 'other', state_dir=self.cfg.state_dir)
            workers.Worker(0, other_service, self.settings, mock.Mock(), 'comfy').ensure_started()
        self.assertEqual(start.call_count, 2)

    @ON_WINDOWS
    def test_the_close_at_the_next_start_whose_handle_did_not_close(self):
        """ensure_started closes a marked engine first (Worker._close_marked); when that close's Job handle does not
        close, the card is marked there, and this same start is refused: never a new engine beside it."""
        w = workers.Worker(0, self.cfg, self.settings, mock.Mock(), 'comfy')
        w.proc, w.state, w.banded_sent = job_process(FakeJobApi(close='fails')), 'ready', ('j1', 'i001')
        with mock.patch.object(workers.Worker, '_start') as start:
            with self.assertRaises(workers.WorkerError) as cm:
                w.ensure_started()
        start.assert_not_called()
        self.assertEqual(str(cm.exception), KEPT.format(where='GPU 1'))
        self.assertIsNone(w.proc)
        self.assertEqual((w.state, w.lost_text()), ('failed', KEPT.format(where='GPU 1')))

    @ON_WINDOWS
    def test_any_stop_of_a_marked_engine_whose_handle_did_not_close(self):
        """Not only the stop after the image: a restart's stop (restart_worker) or an idle stop of an engine that was sent a
        Large-image prompt marks its cards too, in Worker._teardown. An unmarked engine's stop is 5.0.1's."""
        for marked in (True, False):
            w = workers.Worker(0 if marked else 1, self.cfg, self.settings, mock.Mock(), 'comfy')
            w.proc, w.state = job_process(FakeJobApi(close='fails')), 'ready'
            if marked:
                w.banded_sent = ('j1', 'i001')
            cleanup = w.stop('a fresh engine for this pass')
            self.assertEqual(cleanup['job_handle'], 'close_failed')
            self.assertEqual(w.lost_text(), KEPT.format(where='GPU 1') if marked else None)


class TheRecord(unittest.TestCase):
    fixture = E.TheRecord.fixture

    def test_neither_stop_works(self):
        r, eng, ctx, job = self.fixture()
        calls = []

        def stop(reason, kill=False):
            calls.append(kill)
            raise OSError('the Job could not be closed (test)')
        eng.stop = stop
        rec = banded_runner.release_engine(r, eng, ctx, settle_s=0.1)
        self.assertEqual(calls, [False, True])
        self.assertIs(rec['stopped'], False)
        self.assertEqual(rec['commit_check'], 'unmeasured')
        self.assertEqual(eng.banded_sent, ('j1', 'i001'))         # the mark stays
        self.assertEqual(eng.banded_kept, KEPT.format(where='GPU 1'))
        self.assertEqual(eng.state, 'failed')
        self.assertFalse(getattr(eng, 'stopped_after_large', False))
        ev = [c for c in r.log.error.call_args_list if c.args and c.args[0] == E.RELEASED]
        self.assertEqual([c.args[1] for c in ev], [KEPT.format(where='GPU 1')])
        self.assertEqual(ev[0].kwargs['data'], rec)
        self.assertFalse([c for c in r.log.info.call_args_list if c.args and c.args[0] == E.RELEASED])

    def test_an_engine_that_cannot_be_polled_is_kept_too(self):
        """Whether it may be alive is read from the handle the worker still holds, not from alive(), which reads False for
        a process it cannot poll."""
        r, eng, ctx, job = self.fixture()

        def stop(reason, kill=False):
            raise OSError('the Job could not be closed (test)')
        eng.stop = stop
        eng.alive = lambda: False
        rec = banded_runner.release_engine(r, eng, ctx, settle_s=0.1)
        self.assertIs(rec['stopped'], False)
        self.assertEqual(eng.banded_sent, ('j1', 'i001'))
        self.assertEqual(eng.banded_kept, KEPT.format(where='GPU 1'))

    def test_a_stop_whose_job_reports_a_process_left(self):
        """The stop returned, but its Job reported a process still running: no handle is left to close, so the record says
        stopped False with the failure sentence, and the commit fall says what came back."""
        r, eng, ctx, job = self.fixture()

        def stop(reason, kill=False):
            eng.state, eng.proc = 'stopped', None
            job.held.pop(eng.name, None)
            return {'all_owned_processes_terminated': False}
        eng.stop = stop
        rec = banded_runner.release_engine(r, eng, ctx, settle_s=0.5)
        self.assertIs(rec['stopped'], False)
        self.assertEqual(rec['cleanup'], {'all_owned_processes_terminated': False})
        self.assertEqual(rec['commit_check'], 'passed')
        self.assertIsNone(eng.banded_sent)
        self.assertTrue(eng.stopped_after_large)
        ev = [c for c in r.log.error.call_args_list if c.args and c.args[0] == E.RELEASED]
        self.assertEqual([c.args[1] for c in ev], [banded_runner.RELEASE_FAILED_TEXT.format(
            where='GPU 1', error=banded_runner.RELEASE_UNCONFIRMED)])


class TheFallback(unittest.TestCase):
    def test_the_kill_it_asks_for_is_made_and_never_raised_on(self):
        """restart_worker asks its caller to kill an engine it could not stop: restart_previous makes that kill itself,
        guarded, keeps an engine it still holds, and raises the failure again without kill_worker, so the image's failure
        handler never kills it again (a kill that raises there would leave the image active with no thread)."""
        from service.runner import ItemFailure
        r = SimpleNamespace(log=mock.Mock())
        ctx = SimpleNamespace(jid='j2', iid='i001', shutdown=False)
        kills = []

        def stop(reason, kill=False):
            kills.append(kill)
            raise OSError('the Job could not be closed (test)')
        w = SimpleNamespace(gpu=0, proc=object(), fake=None, banded_sent=('j1', 'i001'), banded_kept=None, state='ready',
                            stop=stop)
        failure = ItemFailure(banded_runner.RESTART_BEFORE_FAILED.format(k=1, n=2), event='banded_restart_failed',
                              kill_worker=True, keep_work=True)
        with mock.patch.object(banded_runner, 'restart_worker', mock.Mock(side_effect=failure)):
            with self.assertRaises(ItemFailure) as cm:
                banded_runner.restart_previous(r, w, ctx, 0, 2)
        self.assertEqual(kills, [True])
        self.assertIs(cm.exception.kill_worker, False)
        self.assertEqual((cm.exception.text, cm.exception.keep_work), (failure.text, True))
        self.assertEqual((cm.exception.data['why'], cm.exception.data['previous']), ('previous_job', ['j1', 'i001']))
        self.assertEqual((w.banded_kept, w.state), (KEPT.format(where='GPU 1'), 'failed'))
        ev = [c for c in r.log.error.call_args_list if c.args and c.args[0] == E.RELEASED]
        self.assertEqual([(c.kwargs['data']['stopped'], c.kwargs['data']['why']) for c in ev], [(False, 'previous_job')])


class TheAdmission(unittest.TestCase):
    def runner(self, kept_gb):
        from engine import planner
        c = dict(planner.plan(1280, 960, 2, ram_cap_gb=59.0).to_dict(), peak_ram_gb=30.0)
        r = object.__new__(Runner)
        r.mode = 'comfy'
        r.ctx = {}
        r.store = SimpleNamespace(item=lambda j, i: {'plan': c}, update_item=mock.Mock())
        r.settings = SimpleNamespace(get=lambda: {'ram_cap_gb': 59.0})
        r._held = {}
        r.log = mock.Mock()
        a = SimpleNamespace(gpu=0, proc=None, busy=False, state='ready', banded_kept=None)
        b = SimpleNamespace(gpu=1, proc=SimpleNamespace(pid=7), busy=False, state='failed',
                            banded_kept=KEPT.format(where='GPU 2') if kept_gb else None)
        r.workers, r.multi = {0: a, 1: b}, {}
        return r, a, b

    def admit(self, r, worker, private_gb):
        memory = {'avail_phys_gb': 120.0, 'commit_available_gb': 120.0, 'commit_growth_gb': 0.0}
        with mock.patch.object(memory_policy, 'system_memory', lambda: memory), \
                mock.patch.object(memory_policy, 'process_private_gb', lambda pid: {7: private_gb}.get(pid, 0.0)):
            return r._admit('j1', 'i001', worker)

    def test_a_kept_engine_is_counted_for_another_card(self):
        r, a, b = self.runner(kept_gb=True)
        self.assertFalse(self.admit(r, a, 35.0))            # 30 + 35 > 59: the kept engine still holds its memory
        self.assertIn('Waiting for memory', r._held[('j1', 'i001')])
        r, a, b = self.runner(kept_gb=False)
        self.assertTrue(self.admit(r, a, 35.0))             # a failed engine that is not kept is admitted as before

    def test_the_kept_engines_own_job_is_read(self):
        """Its own Job's commit (its process and every child) when it can be read, as restart_worker reads an engine."""
        r, a, b = self.runner(kept_gb=True)
        b.proc.commit_bytes = lambda: int(40.0 * (1 << 30))
        self.assertFalse(self.admit(r, a, 5.0))             # 30 + 40 > 59, though its root process holds only 5

    def test_its_own_card_closes_it_first(self):
        r, a, b = self.runner(kept_gb=True)
        self.assertTrue(self.admit(r, b, 35.0))             # counted as reusable there: its start closes it first


class TheClaim(unittest.TestCase):
    def test_a_kept_shared_engine_is_never_popped_for_a_preview(self):
        r = object.__new__(Runner)
        import threading
        r._lock = threading.RLock()
        r._sync_workers = lambda: None
        lanes = {g: SimpleNamespace(gpu=g, busy=False, state='stopped', next_start_after=0.0) for g in (0, 1)}
        mw = SimpleNamespace(gpus=(0, 1), busy=False, state='failed', proc=None, fake=object(), next_start_after=0.0,
                             banded_kept=KEPT.format(where='GPU 1 and GPU 2'), stop=mock.Mock())
        r.workers, r.multi = lanes, {(0, 1): mw}
        self.assertIsNone(r._claim_worker())
        self.assertIs(r.multi.get((0, 1)), mw)
        mw.stop.assert_not_called()
        self.assertFalse(any(w.busy for w in lanes.values()))


if __name__ == '__main__':
    unittest.main()
