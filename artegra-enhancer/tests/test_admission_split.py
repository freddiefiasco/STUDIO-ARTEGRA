"""The split finish of a Large-image stage (lever L3r, engine design ENGINE-DESIGN.md 2.8) and its sub-stage checkpoint (2.10):
the commit-fall check after the old engine has exited, read in the shared Windows Job itself and corrected for the other
engines' own change, PeakJobMemoryUsed read around the split and recorded (contract l3r_record), and a split stage resuming
with prompt B only from a complete, valid checkpoint while a damaged one, or one this build cannot reproduce, is refused in
plain words. In-process: banded_runner and its real JobCounters with stub Job objects (and, on Windows, real Jobs holding a
real process tree), a stub runner and engine; the engine's planes are written by the fake engine's own plane writer
(service/fake_comfy.py). Sizes and synthetic pixels only."""
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np

from engine import banded_plan, controls, graph_banded, planes, planner
from service import banded_runner, fake_comfy, memory_policy
from service.runner import ItemFailure, Runner

GIB = float(1 << 30)
CONTRACT = ('job_peak_commit_a_end_gb', 'job_peak_commit_b_start_gb', 'stopped_worker_last_commit_gb', 'commit_fall_gb')


class Job:
    """A stub of the shared Job (service/windows_job.SharedJob). Its commit now is what its engines' processes hold (`held`,
    GiB by engine) plus `stray`: commit no live engine holds (an orphan child, or commit Windows has not taken back yet).
    stray_reads: the stray commit leaves after that many more reads (None: never). Its peak grows by 1 GiB at every read."""

    def __init__(self, peak=40.0):
        self.held, self.stray, self.stray_reads = {}, 0.0, None
        self.peak, self.reads, self.fail = peak, 0, False

    def commit_bytes(self):
        if self.fail:
            raise OSError('the Job cannot be read (test)')
        self.reads += 1
        if self.stray_reads is not None:
            if self.stray_reads <= 0:
                self.stray = 0.0
            else:
                self.stray_reads -= 1
        return int(round((sum(self.held.values()) + self.stray) * GIB))

    def limits(self):
        self.peak += 1.0
        return {'peak_job_memory_used': int(self.peak * GIB)}


class Proc:
    """A stub engine process in its own Job (service/windows_job.WindowsJobProcess): its commit is what `job` says it holds."""

    def __init__(self, job, name, pid):
        self.job, self.name, self.pid = job, name, pid

    def commit_bytes(self):
        return int(round(self.job.held.get(self.name, 0.0) * GIB))


class Engine:
    """A stub engine in the stub Job: queues prompts (a stub _wait_prompt writes the output node's planes as the fake engine
    does), and stops as workers.Worker does (its process ends and it forgets it: proc None). leave: what its commit does when
    it stops: 'freed' (it leaves the Job), 'orphan' (an orphan child keeps it in the Job), ('lag', n) (Windows takes it back
    after n more reads of the Job) or ('leak', GiB) (that much stays). on_stop(): what happens elsewhere meanwhile."""

    def __init__(self, job, name='engine', commit_gb=20.0, leave='freed'):
        self.client = SimpleNamespace(prompts_sent=0)
        self.client.prompt = self._prompt
        self.client_id = 'c'
        self.ws = None
        self.gpu = 0
        self.state = 'ready'
        self.memory_profile = memory_policy.PROFILES['reference']
        self.parts, self.stops, self.starts = [], 0, 0
        self.job, self.name, self.commit_gb, self.leave = job, name, commit_gb, leave
        self.on_stop = None
        self.job.held[name] = commit_gb
        self.proc = Proc(job, name, 100)
        self.fail_part = False                 # the part ('A', 'B' or None) whose prompt fails once

    def _prompt(self, graph, client_id, prompt_id=None):
        self.client.prompts_sent += 1
        part = 'B' if any(n['class_type'] == 'CUFinishBanded' for n in graph.values()) and \
            not any(n['class_type'] == 'KSampler' for n in graph.values()) else \
            ('A' if any(n['class_type'] == 'CUPlaneCheckpoint' for n in graph.values()) else None)
        self.parts.append(part)
        return prompt_id

    def alive(self):
        return self.state == 'ready'

    def stop(self, reason):
        self.stops += 1
        self.state = 'stopped'
        if self.on_stop is not None:
            self.on_stop()
        held = self.job.held.pop(self.name, 0.0)
        if self.leave == 'orphan':
            self.job.stray += held
        elif isinstance(self.leave, tuple) and self.leave[0] == 'lag':
            self.job.stray, self.job.stray_reads = self.job.stray + held, int(self.leave[1])
        elif isinstance(self.leave, tuple) and self.leave[0] == 'leak':
            self.job.stray += float(self.leave[1])
        self.proc = None
        return {'all_owned_processes_terminated': True}

    def ensure_started(self, lookup=None, abort=None):
        self.starts += 1
        self.state = 'ready'
        self.job.held[self.name] = self.commit_gb
        self.proc = Proc(self.job, self.name, 101)
        self.client.prompts_sent = 0


def wait_prompt(engine):
    def wait(w, ctx, graph, pid, k, n, plan, deadline, prefix, input_name, st, tracker):
        part = engine.parts[-1]
        if engine.fail_part is not False and engine.fail_part == part:
            engine.fail_part = False
            raise ItemFailure('The engine closed unexpectedly (test).', event='worker_crashed', kill_worker=True)
        fc = object.__new__(fake_comfy.FakeComfy)
        fc._last_saved = {}
        outs = {}
        for nid, nd in graph.items():
            if nd['class_type'] in graph_banded.OUTPUT_CLASSES:
                outs[nid] = fake_comfy.FakeComfy._save_planes(fc, graph, nid)
        return {'status': {'completed': True, 'status_str': 'success'}, 'outputs': outs}
    return wait


class Store:
    def __init__(self, item):
        self.it = item
        self.updates = []

    def item(self, jid, iid):
        return self.it

    def update_item(self, jid, iid, **kw):
        self.updates.append(kw)
        for key in ('timings', 'message'):
            if key in kw:
                self.it[key] = kw[key]
        return self.it

    def set_job_fields(self, jid, **kw):
        pass


def split_plan(w=1100, h=900, f=2):
    p = banded_plan.plan_forced(planner.plan(w, h, f, ram_cap_gb=59.0), 59.0).to_dict()
    for st in p['stages']:
        st['split_finish'] = True
    return p


class Fixture:
    """A split stage through banded_runner.run_stage with the real JobCounters reading a stub shared Job (the runner's mode
    is 'fake-process': engines with processes in a real Job, as the fake engine's own process mode has)."""

    def __init__(self, td, plan=None, settings=None, run=None):
        self.td = Path(td)
        self.plan = plan or split_plan()
        self.settings = settings if settings is not None else {}
        self.job = Job()
        self.engine = Engine(self.job)
        work = self.td / 'work' / 'j1' / 'i001'
        work.mkdir(parents=True)
        iw, ih = self.plan['input_size']
        rng = np.random.default_rng(7)
        from PIL import Image
        Image.fromarray(rng.integers(0, 256, (ih, iw, 3), dtype=np.uint8), 'RGB').save(work / 'input.png')
        self.work = work
        self.item = {'id': 'i001', 'name': 'x', 'plan': self.plan, 'timings': {'stages': []}, 'run': run, 'media_id': 'm1',
                     'settings': self.settings}
        self.store = Store(self.item)
        r = object.__new__(Runner)
        r.cfg = SimpleNamespace(work_dir=self.td / 'work')
        r.banded_pack = {'ok': True, 'tree_sha256': 'pack-sha'}
        r.store = self.store
        r.log = mock.Mock()
        r.mode = 'fake-process'
        r.shared_job = self.job
        r.workers = {0: self.engine}
        r.multi = {}
        r.accepting = True
        r.deadline_override = None
        r._stage_disk_check = lambda *a: None
        r._run_would = lambda job, it, mode: {'speed_stack': True, 'faster': False}
        r.detailed_info = lambda: {'on': False}
        r._live_begin = mock.Mock(return_value=None)
        r._wait_prompt = wait_prompt(self.engine)
        r._gpu_lookup = lambda: {}
        self.r = r
        self.ctx = SimpleNamespace(jid='j1', iid='i001', shutdown=False, speed=None, pace=None, factor=1.0,
                                   stage_factors=None, card_factor=1.0, prompt_id=None)

    def run(self, k=0, params=None):
        params = params or controls.resolve(self.settings)[0]
        n = len(self.plan['stages'])
        return banded_runner.run_stage(self.r, self.engine, self.ctx, {'settings': self.settings}, params, k, n, self.item)

    def plane_dir(self, k=0):
        return self.work / 'planes' / f's{k}'


class TheCommitFallCheck(unittest.TestCase):
    """restart_worker with the real JobCounters: only the Job objects are stubs. The stopped engine holds 20 GiB, another
    card's engine 10 GiB."""

    def setup(self, last=20.0, other=10.0, leave='freed', mode='comfy'):
        job = Job()
        e = Engine(job, 'engine', last, leave)
        job.held['other'] = other
        o = SimpleNamespace(proc=Proc(job, 'other', 200))
        r = SimpleNamespace(log=mock.Mock(), mode=mode, accepting=True, _gpu_lookup=lambda: {}, shared_job=job,
                            workers={0: e, 1: o}, multi={})
        return r, e, job

    def restart(self, r, e, settle_s=0.0):
        ctx = SimpleNamespace(jid='j', iid='i', shutdown=False)
        return banded_runner.restart_worker(r, e, ctx, 2, 3, settle_s=settle_s)

    def failure(self, r, e, settle_s=0.0):
        with self.assertRaises(ItemFailure) as ex:
            self.restart(r, e, settle_s)
        f = ex.exception
        self.assertEqual(f.event, 'banded_restart_memory')
        self.assertTrue(f.keep_work)
        self.assertTrue(f.kill_worker)
        self.assertEqual(str(f), 'The Large-image engine did not give its memory back when it was restarted for the last step '
                                 'of pass 3 of 3, so this image was stopped.')
        self.assertEqual(f.data['commit_check'], 'failed')
        self.assertEqual(e.starts, 0)                                     # never started again on memory still held
        return f.data

    def test_it_passes_and_records_when_the_memory_left_the_job(self):
        r, e, job = self.setup()
        rec = self.restart(r, e)
        self.assertEqual((e.stops, e.starts), (1, 1))
        self.assertLess(rec.pop('commit_wait_s'), 1.0)                    # the memory was back at the first read
        self.assertEqual(rec, {'job_peak_commit_a_end_gb': 41.0,           # read before the stop
                               'stopped_worker_last_commit_gb': 20.0, 'commit_fall_gb': 20.0,
                               'job_commit_before_gb': 30.0, 'job_commit_after_gb': 10.0,
                               'other_engines_commit_before_gb': 10.0, 'other_engines_commit_after_gb': 10.0,
                               'commit_check': 'passed'})

    def test_memory_an_orphan_child_keeps_in_the_job_fails_the_stage(self):
        # the defect: the stopped engine forgets its process (proc None), so its own counter reads nothing after the stop,
        # while its 20 GiB stays in the shared Job; the Job's own counter sees that nothing left
        r, e, job = self.setup(leave='orphan')
        d = self.failure(r, e)
        self.assertEqual((d['job_commit_before_gb'], d['job_commit_after_gb']), (30.0, 30.0))
        self.assertEqual(d['commit_fall_gb'], 0.0)
        self.assertEqual(d['stopped_worker_last_commit_gb'], 20.0)

    def test_another_engine_growing_by_2_gib_during_the_stop_does_not_fail_it(self):
        r, e, job = self.setup()
        e.on_stop = lambda: job.held.update(other=12.0)                   # two images on the workstation
        rec = self.restart(r, e)
        self.assertEqual(rec['commit_check'], 'passed')
        self.assertEqual(rec['commit_fall_gb'], 20.0)                     # only the stopped engine's release is tested
        self.assertEqual((rec['job_commit_before_gb'], rec['job_commit_after_gb']), (30.0, 12.0))
        self.assertEqual((rec['other_engines_commit_before_gb'], rec['other_engines_commit_after_gb']), (10.0, 12.0))

    def test_another_engine_shrinking_during_the_stop_does_not_pass_a_leak(self):
        r, e, job = self.setup(other=30.0, leave='orphan')
        e.on_stop = lambda: job.held.update(other=10.0)                   # the other card's image released 20 GiB
        d = self.failure(r, e)
        self.assertEqual((d['job_commit_before_gb'], d['job_commit_after_gb']), (50.0, 30.0))
        self.assertEqual(d['commit_fall_gb'], 0.0)

    def test_commit_windows_takes_back_after_the_exit_is_waited_for(self):
        r, e, job = self.setup(leave=('lag', 3))
        rec = self.restart(r, e, settle_s=10.0)
        self.assertEqual((rec['commit_check'], rec['commit_fall_gb']), ('passed', 20.0))
        r, e, job = self.setup(leave=('lag', 3))
        self.failure(r, e, settle_s=0.0)                                  # read only once, the commit was still there

    def test_the_wait_ends_when_the_app_stops_and_is_then_unmeasured_never_failed(self):
        r, e, job = self.setup(leave='orphan')
        e.on_stop = lambda: setattr(r, 'accepting', False)                # the app is shutting down meanwhile
        t0 = time.monotonic()
        rec = self.restart(r, e, settle_s=30.0)
        self.assertLess(time.monotonic() - t0, 5.0)                       # not the 30 s wait
        self.assertEqual(rec['commit_check'], 'unmeasured')
        self.assertIsNone(rec['commit_fall_gb'])
        self.assertEqual(rec['job_commit_after_gb'], 30.0)                # what was read is kept
        self.assertLess(rec['commit_wait_s'], 5.0)
        r, e, job = self.setup(leave=('lag', 3))
        rec = self.restart(r, e, settle_s=10.0)
        self.assertGreater(rec['commit_wait_s'], 0.0)                     # the wait for a lagged release is recorded

    def test_the_wait_is_for_the_whole_commit_not_for_the_spare(self):
        r, e, job = self.setup(last=0.5, leave=('lag', 2))                # 0.5 GiB would pass the 1 GiB rule at once
        rec = self.restart(r, e, settle_s=10.0)
        self.assertEqual((rec['commit_check'], rec['commit_fall_gb']), ('passed', 0.5))

    def test_a_leak_within_the_spare_passes_and_one_over_it_fails(self):
        r, e, job = self.setup(leave=('leak', 0.5))
        rec = self.restart(r, e, settle_s=0.2)
        self.assertEqual((rec['commit_check'], rec['commit_fall_gb']), ('passed', 19.5))
        r, e, job = self.setup(leave=('leak', 1.5))
        self.assertEqual(self.failure(r, e, settle_s=0.2)['commit_fall_gb'], 18.5)

    def test_without_a_shared_job_it_is_unmeasured_never_a_fall_from_zeros(self):
        r, e, job = self.setup(mode='fake')                               # the fake engine in this process
        r.shared_job = None
        rec = self.restart(r, e)
        self.assertEqual(rec['commit_check'], 'unmeasured')
        for key in ('commit_fall_gb', 'stopped_worker_last_commit_gb', 'job_commit_before_gb', 'job_commit_after_gb'):
            self.assertIsNone(rec[key], key)
        self.assertEqual(e.starts, 1)
        self.assertTrue(any(c.args[0] == 'banded_split_commit_unmeasured' for c in r.log.info.call_args_list))

    def test_a_job_that_cannot_be_read_on_a_real_engine_is_unmeasured_and_warned(self):
        for when in ('before', 'after'):
            with self.subTest(when=when):
                r, e, job = self.setup()
                if when == 'before':
                    job.fail = True
                else:
                    e.on_stop = lambda job=job: setattr(job, 'fail', True)
                rec = self.restart(r, e)
                self.assertEqual(rec['commit_check'], 'unmeasured')
                self.assertIsNone(rec['commit_fall_gb'])
                self.assertEqual(e.starts, 1)
                self.assertTrue(any(c.args[0] == 'banded_split_commit_unmeasured' for c in r.log.warn.call_args_list))

    def test_an_engine_whose_processes_did_not_all_end_fails(self):
        r, e, job = self.setup()
        e.stop = lambda reason: {'all_owned_processes_terminated': False}
        with self.assertRaises(ItemFailure) as ex:
            self.restart(r, e)
        self.assertEqual(ex.exception.event, 'banded_restart_failed')

    def test_the_counters_read_the_jobs_and_nothing_from_a_fake_engine(self):
        r = SimpleNamespace(mode='fake', workers={0: SimpleNamespace(proc=None)}, multi={}, shared_job=None)
        c = banded_runner.JobCounters(r)
        self.assertIsNone(c.job_commit_gb())
        self.assertIsNone(c.process_gb(r.workers[0]))
        self.assertEqual(c.others_gb(None), 0.0)
        self.assertIsNone(c.job_peak_gb(SimpleNamespace(proc=None)))
        job = Job()
        job.held.update(a=3.0, b=4.0)
        a, b = SimpleNamespace(proc=Proc(job, 'a', 1)), SimpleNamespace(proc=Proc(job, 'b', 2))
        c = banded_runner.JobCounters(SimpleNamespace(mode='comfy', shared_job=job, workers={0: a}, multi={'01': b}))
        self.assertEqual((c.job_commit_gb(), c.process_gb(a), c.others_gb(a)), (7.0, 3.0, 4.0))
        broken = SimpleNamespace(proc=SimpleNamespace(pid=9, commit_bytes=mock.Mock(side_effect=OSError('closed'))))
        with mock.patch.object(memory_policy, 'process_private_gb', lambda pid: 2.5 if pid == 9 else 0.0):
            self.assertEqual(c.process_gb(broken), 2.5)                   # its own Job unreadable: its private bytes
        job = SimpleNamespace(limits=lambda: {'peak_job_memory_used': 40 * (1 << 30)})
        self.assertEqual(banded_runner.JobCounters(SimpleNamespace(shared_job=job)).job_peak_gb(None), 40.0)
        bad = SimpleNamespace(limits=mock.Mock(side_effect=OSError('closed')))
        self.assertIsNone(banded_runner.JobCounters(SimpleNamespace(shared_job=bad)).job_peak_gb(None))


HOLD_MB = 256


def contained_tree(job, td, name, hold_mb=HOLD_MB):
    """A real engine-like process tree in its own Windows Job nested in `job`: a root Python that starts a child Python
    holding hold_mb of committed memory (the memory is in the child, not the root). Returns once the child holds it."""
    from service import windows_job
    ready = Path(td) / f'{name}.ready'
    child = (f"import sys, time; b = bytearray({int(hold_mb)} << 20); open(sys.argv[1], 'w').write('ready'); "
             "time.sleep(300)")
    root = f"import subprocess, sys; subprocess.Popen([sys.executable, '-I', '-S', '-B', '-c', {child!r}, sys.argv[1]]).wait()"
    p = windows_job.WindowsJobProcess([os.path.abspath(sys.executable), '-I', '-S', '-B', '-c', root, str(ready)],
                                      cwd=str(td), env=dict(os.environ), log_path=Path(td) / f'{name}.log',
                                      memory_limit_bytes=2 << 30, parent_job=job)
    end = time.monotonic() + 90
    while not ready.is_file():
        if time.monotonic() > end or p.poll_root() is not None:
            p.close()
            raise AssertionError(f'the test process tree did not start: {(Path(td) / f"{name}.log").read_text()!r}')
        time.sleep(0.05)
    return p


class RealEngine:
    """An engine whose stop does what workers.Worker._teardown does: it closes its own Job (every process of it ends) and
    forgets the process (proc None). orphan: it forgets the process but leaves its tree running in the shared Job."""

    def __init__(self, proc, orphan=False):
        self.proc, self.orphan, self.left, self.starts = proc, orphan, None, 0

    def stop(self, reason):
        proc, self.proc = self.proc, None
        if self.orphan:
            self.left = proc
            return {'all_owned_processes_terminated': True}
        return proc.close(timeout=15)

    def ensure_started(self, lookup=None, abort=None):
        self.starts += 1


@unittest.skipUnless(os.name == 'nt', 'Windows Jobs')
class TheRealWindowsJobs(unittest.TestCase):
    """The counters on real Windows Jobs: a shared Job holding a real process tree whose memory is in a child process."""

    def setUp(self):
        from service import windows_job
        self.td = tempfile.mkdtemp(prefix='cu-l3r-')
        self.addCleanup(shutil.rmtree, self.td, True)
        self.job = windows_job.SharedJob(memory_limit_bytes=4 << 30)
        self.addCleanup(self.job.close)

    def tree(self, name):
        p = contained_tree(self.job, self.td, name)
        self.addCleanup(p.close)
        return p

    def runner(self, *engines):
        return SimpleNamespace(log=mock.Mock(), mode='comfy', accepting=True, _gpu_lookup=lambda: {},
                               shared_job=self.job, workers=dict(enumerate(engines)), multi={})

    def test_the_counters_read_an_engine_with_its_children_and_the_shared_job(self):
        p = self.tree('engine')
        hold = HOLD_MB / 1024.0
        job_gb, own_gb = self.job.commit_bytes() / GIB, p.commit_bytes() / GIB
        listed = sum(memory_policy.process_private_gb(pid) for pid in self.job.process_ids())
        self.assertGreaterEqual(own_gb, hold)
        self.assertLess(memory_policy.process_private_gb(p.pid), hold / 2)   # the root's own bytes miss the child's memory
        self.assertAlmostEqual(job_gb, own_gb, delta=0.02)                  # one engine: the shared Job holds its Job
        self.assertAlmostEqual(job_gb, listed, delta=0.05)                  # the Job's counter agrees with its process list
        w = SimpleNamespace(proc=p)
        c = banded_runner.JobCounters(self.runner(w))
        self.assertAlmostEqual(c.process_gb(w), own_gb, delta=0.02)
        self.assertAlmostEqual(c.job_commit_gb(), job_gb, delta=0.02)

    def test_a_real_stop_gives_the_memory_back_and_passes(self):
        e = RealEngine(self.tree('engine'))
        rec = banded_runner.restart_worker(self.runner(e), e, SimpleNamespace(jid='j', iid='i', shutdown=False), 0, 1,
                                           settle_s=30.0)
        self.assertEqual(rec['commit_check'], 'passed', rec)
        self.assertGreaterEqual(rec['stopped_worker_last_commit_gb'], HOLD_MB / 1024.0)
        self.assertGreaterEqual(rec['commit_fall_gb'], rec['stopped_worker_last_commit_gb'] - banded_runner.COMMIT_EPS_GB)
        self.assertLessEqual(rec['job_commit_after_gb'], banded_runner.COMMIT_EPS_GB)
        self.assertEqual(e.starts, 1)

    def test_a_tree_left_running_in_the_shared_job_fails(self):
        e = RealEngine(self.tree('engine'), orphan=True)
        self.addCleanup(lambda: e.left is not None and e.left.close())
        with mock.patch.object(banded_runner, 'COMMIT_SPARE_GB', 0.1):    # the test tree holds 256 MiB, not gigabytes
            with self.assertRaises(ItemFailure) as ex:
                banded_runner.restart_worker(self.runner(e), e, SimpleNamespace(jid='j', iid='i', shutdown=False), 0, 1,
                                             settle_s=1.0)
        self.assertEqual(ex.exception.event, 'banded_restart_memory')
        self.assertLess(ex.exception.data['commit_fall_gb'], 0.1)
        self.assertEqual(e.starts, 0)


class ASplitStage(unittest.TestCase):
    def test_prompt_a_then_a_fresh_engine_then_prompt_b_and_the_record(self):
        with tempfile.TemporaryDirectory() as td:
            fx = Fixture(td)
            fx.run(0)
            self.assertEqual(fx.engine.parts, ['A', 'B'])
            self.assertEqual((fx.engine.stops, fx.engine.starts), (1, 1))
            ow, oh = fx.plan['stages'][0]['output_size']
            planes.validate(fx.work / 'stage0.u8', shape=(oh, ow, 3), dtype='u8')
            self.assertFalse(fx.plane_dir().exists())                    # removed after the stage output was validated
            b = [x for x in fx.item['timings']['stages'] if x.get('part') == 'B'][0]
            self.assertEqual(b['job_peak_commit_a_end_gb'], 41.0)        # PeakJobMemoryUsed just before prompt A ended
            self.assertEqual(b['job_peak_commit_b_start_gb'], 42.0)      # and just after prompt B started
            self.assertEqual(b['stopped_worker_last_commit_gb'], 20.0)
            self.assertEqual(b['commit_fall_gb'], 20.0)
            self.assertEqual((b['job_commit_before_gb'], b['job_commit_after_gb']), (20.0, 0.0))   # the shared Job's own
            self.assertEqual(b['commit_check'], 'passed')
            logged = [c for c in fx.r.log.info.call_args_list if c.args[0] == 'banded_split_commit']
            self.assertEqual(len(logged), 1)
            self.assertEqual(set(logged[0].kwargs['data']), set(CONTRACT) | set(banded_runner.L3R_EXTRA))
            self.assertEqual({k: logged[0].kwargs['data'][k] for k in CONTRACT}, {k: b[k] for k in CONTRACT})

    def test_the_stopped_engines_memory_kept_in_the_job_stops_the_stage(self):
        with tempfile.TemporaryDirectory() as td:
            fx = Fixture(td)
            fx.engine.leave = 'orphan'
            with mock.patch.object(banded_runner, 'COMMIT_SETTLE_S', 0.0):
                with self.assertRaises(ItemFailure) as ex:
                    fx.run(0)
            self.assertEqual(ex.exception.event, 'banded_restart_memory')
            self.assertEqual(fx.engine.parts, ['A'])                     # prompt B never ran on the memory still held
            self.assertTrue((fx.plane_dir() / banded_runner.CHECKPOINT_FILE).is_file())   # prompt A's work is kept

    def test_a_resumed_prompt_b_in_a_fresh_engine_records_no_restart(self):
        with tempfile.TemporaryDirectory() as td:
            fx = Fixture(td)
            fx.engine.fail_part = 'B'
            with self.assertRaises(ItemFailure):
                fx.run(0)
            fx.engine.parts.clear()
            fx.engine.state, fx.engine.client.prompts_sent = 'ready', 0
            fx.run(0)
            self.assertEqual(fx.engine.parts, ['B'])
            b = [x for x in fx.item['timings']['stages'] if x.get('part') == 'B'][-1]
            self.assertEqual(b['commit_check'], 'not restarted')
            self.assertIsNone(b['commit_fall_gb'])

    def test_a_stage_without_the_split_is_one_prompt_with_no_checkpoint(self):
        with tempfile.TemporaryDirectory() as td:
            p = split_plan()
            p['stages'][0]['split_finish'] = False
            fx = Fixture(td, plan=p)
            fx.run(0)
            self.assertEqual(fx.engine.parts, [None])
            self.assertEqual(fx.engine.stops, 0)


class ResumeFromTheCheckpoint(unittest.TestCase):
    def crashed_in_b(self, td, **kw):
        fx = Fixture(td, **kw)
        fx.engine.fail_part = 'B'
        with self.assertRaises(ItemFailure):
            fx.run(0)
        self.assertEqual(fx.engine.parts, ['A', 'B'])
        self.assertTrue((fx.plane_dir() / banded_runner.CHECKPOINT_FILE).is_file())
        fx.engine.parts.clear()
        return fx

    def test_a_complete_valid_checkpoint_runs_prompt_b_only(self):
        with tempfile.TemporaryDirectory() as td:
            fx = self.crashed_in_b(td)
            rec = json.loads((fx.plane_dir() / banded_runner.CHECKPOINT_FILE).read_text(encoding='utf8'))
            self.assertEqual(sorted(x['role'] for x in rec['planes']), sorted(rec['roles']))
            self.assertIn('protect', rec['roles'])                       # the default settings protect
            with mock.patch.object(banded_runner, '_make_input_plane', side_effect=AssertionError('no new pad')):
                fx.engine.state, fx.engine.client.prompts_sent = 'ready', 0   # the engine just started: fresh
                stops = fx.engine.stops
                fx.run(0)
            self.assertEqual(fx.engine.parts, ['B'])
            self.assertEqual(fx.engine.stops, stops)                      # a fresh engine is not restarted again
            ow, oh = fx.plan['stages'][0]['output_size']
            planes.validate(fx.work / 'stage0.u8', shape=(oh, ow, 3), dtype='u8')
            self.assertTrue(any(c.args[0] == 'banded_checkpoint_resume' for c in fx.r.log.info.call_args_list))

    def test_a_warm_engine_is_restarted_before_a_resumed_prompt_b(self):
        with tempfile.TemporaryDirectory() as td:
            fx = self.crashed_in_b(td)
            fx.engine.state, fx.engine.client.prompts_sent = 'ready', 3
            stops = fx.engine.stops
            fx.run(0)
            self.assertEqual(fx.engine.parts, ['B'])
            self.assertEqual(fx.engine.stops, stops + 1)

    def refused(self, fx, reason_part):
        fx.engine.state, fx.engine.client.prompts_sent = 'ready', 0
        fx.run(0)
        self.assertEqual(fx.engine.parts, ['A', 'B'])                     # made again from its start
        warn = [c for c in fx.r.log.warn.call_args_list if c.args[0] == 'banded_checkpoint_refused']
        self.assertEqual(len(warn), 1)
        text = warn[0].args[1]
        self.assertTrue(text.startswith('The saved first part of pass 1 of 1 could not be used ('), text)
        self.assertTrue(text.endswith('), so the pass is made again from its start.'), text)
        self.assertIn(reason_part, text)
        self.assertIn(text, [u.get('message') for u in fx.store.updates])   # the image's own line says it too
        # logged once: the warning above is the log line, so the item update that carries the text logs no event of its own
        self.assertEqual([u for u in fx.store.updates if u.get('event') == 'banded_checkpoint_refused'], [])

    def test_a_damaged_plane_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            fx = self.crashed_in_b(td)
            p = fx.plane_dir() / 'creative.plane'
            with open(p, 'r+b') as f:
                f.seek(planes.DATA_OFFSET + 10)
                b = f.read(1)
                f.seek(planes.DATA_OFFSET + 10)
                f.write(bytes([b[0] ^ 0xFF]))
            self.refused(fx, 'its creative part')

    def test_a_missing_plane_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            fx = self.crashed_in_b(td)
            (fx.plane_dir() / 'protect.plane').unlink()
            self.refused(fx, 'its protect part is missing or damaged')

    def test_other_settings_are_refused(self):
        with tempfile.TemporaryDirectory() as td:
            fx = self.crashed_in_b(td)
            fx.settings = {'seed': '12345'}
            fx.item['settings'] = fx.settings
            self.refused(fx, 'other settings')

    def test_another_build_or_other_constants_are_refused(self):
        with tempfile.TemporaryDirectory() as td:
            fx = self.crashed_in_b(td)
            fx.r.banded_pack = {'ok': True, 'tree_sha256': 'another-build'}
            self.refused(fx, 'another build of the Large-image engine')
        with tempfile.TemporaryDirectory() as td:
            fx = self.crashed_in_b(td)
            path = fx.plane_dir() / banded_runner.CHECKPOINT_FILE
            rec = json.loads(path.read_text(encoding='utf8'))
            rec['constants']['window'] = 2048
            path.write_text(json.dumps(rec), encoding='utf8')
            self.refused(fx, 'other Large-image engine settings')

    def test_a_damaged_record_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            fx = self.crashed_in_b(td)
            (fx.plane_dir() / banded_runner.CHECKPOINT_FILE).write_text('{half', encoding='utf8')
            self.refused(fx, 'its record is damaged')

    def test_a_plan_this_build_cannot_make_fails_plainly(self):
        with tempfile.TemporaryDirectory() as td:
            p = split_plan()
            p['banded'] = dict(p['banded'], finish='bxf-1h')
            fx = Fixture(td, plan=p)
            with self.assertRaises(ItemFailure) as ex:
                fx.run(0)
            self.assertEqual(ex.exception.event, 'banded_plan_unbuildable')
            self.assertEqual(str(ex.exception), banded_runner.UNBUILDABLE)
            self.assertEqual(fx.engine.parts, [])


class RestartRecovery(unittest.TestCase):
    def test_a_finished_large_image_pass_is_found_after_a_restart(self):
        with tempfile.TemporaryDirectory() as td:
            fx = Fixture(td)
            fx.run(0)
            r = fx.r
            self.assertTrue(Runner._stage_file_ok(r, 'j1', 'i001', 0))
            p = fx.work / 'stage0.u8'
            with open(p, 'r+b') as f:
                f.seek(planes.DATA_OFFSET)
                b = f.read(1)
                f.seek(planes.DATA_OFFSET)
                f.write(bytes([b[0] ^ 1]))
            self.assertFalse(Runner._stage_file_ok(r, 'j1', 'i001', 0))
            self.assertTrue(any(c.args[0] == 'stage_file_damaged' for c in r.log.warn.call_args_list))

    def test_a_reset_removes_the_planes(self):
        with tempfile.TemporaryDirectory() as td:
            fx = Fixture(td)
            fx.engine.fail_part = 'B'
            with self.assertRaises(ItemFailure):
                fx.run(0)
            self.assertTrue(fx.plane_dir().is_dir())
            Runner._reset_stage_files(fx.r, 'j1', 'i001', 1, keep=False)
            self.assertFalse((fx.work / 'planes').exists())


if __name__ == '__main__':
    unittest.main()
