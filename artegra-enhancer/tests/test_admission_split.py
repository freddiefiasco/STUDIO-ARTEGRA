"""The split finish of a Large-image stage (lever L3r, engine design ENGINE-DESIGN.md 2.8) and its sub-stage checkpoint (2.10):
the commit-fall check after the old engine has exited, PeakJobMemoryUsed read around the split and recorded (contract
l3r_record), and a split stage resuming with prompt B only from a complete, valid checkpoint while a damaged one, or one this
build cannot reproduce, is refused in plain words. In-process: banded_runner with a stub runner and engine; the engine's
planes are written by the fake engine's own plane writer (service/fake_comfy.py). Sizes and synthetic pixels only."""
import json
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np

from engine import banded_plan, controls, graph_banded, planes, planner
from service import banded_runner, fake_comfy, memory_policy
from service.runner import ItemFailure, Runner


class Counters:
    """Stub commit counters: `seq` of (workers commit before, after) per restart, the stopped engine's commit, and a Job
    peak that grows by 1 GiB at every read."""

    def __init__(self, last=20.0, before=30.0, after=10.0):
        self.last, self.before, self.after = last, before, after
        self.peak, self.reads, self.stopped = 40.0, 0, False

    def __call__(self, r):
        return self

    def process_gb(self, w):
        return self.last

    def workers_commit_gb(self):
        return self.after if self.stopped else self.before

    def job_peak_gb(self, w):
        self.reads += 1
        self.peak += 1.0
        return self.peak


class Engine:
    """A stub engine: queues prompts, and a stub _wait_prompt that writes the output node's planes as the fake engine does."""

    def __init__(self, counters):
        self.client = SimpleNamespace(prompts_sent=0)
        self.client.prompt = self._prompt
        self.client_id = 'c'
        self.ws = None
        self.gpu = 0
        self.state = 'ready'
        self.memory_profile = memory_policy.PROFILES['reference']
        self.parts, self.stops, self.starts = [], 0, 0
        self.counters = counters
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
        self.counters.stopped = True
        return {'all_owned_processes_terminated': True}

    def ensure_started(self, lookup=None, abort=None):
        self.starts += 1
        self.state = 'ready'
        self.counters.stopped = False
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
    def __init__(self, td, plan=None, settings=None, counters=None):
        self.td = Path(td)
        self.plan = plan or split_plan()
        self.settings = settings if settings is not None else {}
        self.counters = counters or Counters()
        self.engine = Engine(self.counters)
        work = self.td / 'work' / 'j1' / 'i001'
        work.mkdir(parents=True)
        iw, ih = self.plan['input_size']
        rng = np.random.default_rng(7)
        from PIL import Image
        Image.fromarray(rng.integers(0, 256, (ih, iw, 3), dtype=np.uint8), 'RGB').save(work / 'input.png')
        self.work = work
        self.item = {'id': 'i001', 'name': 'x', 'plan': self.plan, 'timings': {'stages': []}, 'run': None, 'media_id': 'm1',
                     'settings': self.settings}
        self.store = Store(self.item)
        r = object.__new__(Runner)
        r.cfg = SimpleNamespace(work_dir=self.td / 'work')
        r.banded_pack = {'ok': True, 'tree_sha256': 'pack-sha'}
        r.store = self.store
        r.log = mock.Mock()
        r.mode = 'fake'
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
        with mock.patch.object(banded_runner, 'JobCounters', self.counters):
            return banded_runner.run_stage(self.r, self.engine, self.ctx, {'settings': self.settings}, params, k, n, self.item)

    def plane_dir(self, k=0):
        return self.work / 'planes' / f's{k}'


class TheCommitFallCheck(unittest.TestCase):
    def call(self, last, before, after):
        c = Counters(last, before, after)
        e = Engine(c)
        r = SimpleNamespace(log=mock.Mock(), mode='fake', accepting=True, _gpu_lookup=lambda: {})
        ctx = SimpleNamespace(jid='j', iid='i', shutdown=False)
        return banded_runner.restart_worker(r, e, ctx, 2, 3, counters=c), e, c

    def test_it_passes_when_the_commit_fell_by_the_stopped_engines_less_1_gib(self):
        rec, e, c = self.call(last=20.0, before=30.0, after=10.0)
        self.assertEqual((e.stops, e.starts), (1, 1))
        self.assertEqual(rec['stopped_worker_last_commit_gb'], 20.0)
        self.assertEqual(rec['commit_fall_gb'], 20.0)
        self.assertEqual(rec['job_peak_commit_a_end_gb'], 41.0)          # read before the stop
        rec, _, _ = self.call(last=20.0, before=30.0, after=11.0)         # 19 GiB fell: within the 1 GiB spare
        self.assertEqual(rec['commit_fall_gb'], 19.0)

    def test_it_fails_the_stage_plainly_when_the_memory_stayed(self):
        with self.assertRaises(ItemFailure) as ex:
            self.call(last=20.0, before=30.0, after=12.0)                 # another engine cannot explain 2 GiB
        f = ex.exception
        self.assertEqual(f.event, 'banded_restart_memory')
        self.assertTrue(f.keep_work)
        self.assertTrue(f.kill_worker)
        self.assertEqual(str(f), 'The engine did not give its memory back when it was restarted for the last step of pass 3 '
                                 'of 3, so this image was stopped.')
        self.assertEqual(f.data['commit_fall_gb'], 18.0)

    def test_an_engine_whose_processes_did_not_all_end_fails(self):
        c = Counters()
        e = Engine(c)
        e.stop = lambda reason: {'all_owned_processes_terminated': False}
        r = SimpleNamespace(log=mock.Mock(), mode='fake', accepting=True, _gpu_lookup=lambda: {})
        with self.assertRaises(ItemFailure) as ex:
            banded_runner.restart_worker(r, e, SimpleNamespace(jid='j', iid='i', shutdown=False), 0, 1, counters=c)
        self.assertEqual(ex.exception.event, 'banded_restart_failed')

    def test_the_real_counters_read_nothing_from_a_fake_engine(self):
        r = SimpleNamespace(mode='fake', workers={0: SimpleNamespace(proc=None)}, multi={}, shared_job=None)
        c = banded_runner.JobCounters(r)
        self.assertEqual(c.workers_commit_gb(), 0.0)
        self.assertIsNone(c.job_peak_gb(SimpleNamespace(proc=None)))
        job = SimpleNamespace(limits=lambda: {'peak_job_memory_used': 40 * (1 << 30)})
        self.assertEqual(banded_runner.JobCounters(SimpleNamespace(shared_job=job)).job_peak_gb(None), 40.0)
        bad = SimpleNamespace(limits=mock.Mock(side_effect=OSError('closed')))
        self.assertIsNone(banded_runner.JobCounters(SimpleNamespace(shared_job=bad)).job_peak_gb(None))


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
            logged = [c for c in fx.r.log.info.call_args_list if c.args[0] == 'banded_split_commit']
            self.assertEqual(len(logged), 1)
            self.assertEqual(set(logged[0].kwargs['data']), {'job_peak_commit_a_end_gb', 'job_peak_commit_b_start_gb',
                                                            'stopped_worker_last_commit_gb', 'commit_fall_gb'})

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
