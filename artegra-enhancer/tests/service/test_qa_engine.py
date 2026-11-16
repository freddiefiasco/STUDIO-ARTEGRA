import json
import os
import secrets
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from engine import controls, graph_v5t, planner
from service import comfy, config, fake_comfy, lifecycle, live, notify, workers
from service.errors import ApiError
from service.logs import Logger
from service.media import MediaLibrary
from service.runner import Runner, stage_left_s, too_large
from service.settings import Settings
from service.store import JobStore
from tests.service.helpers import REPO, gradient, rmtree, tmpdir

FAST = {'CU_FAKE_GPUS': '1', 'CU_NOTIFY_DRYRUN': '1', 'CU_FAKE_STAGE_SECONDS': '0.4'}


def wait(pred, timeout=30.0, what='condition', interval=0.02):
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        v = pred()
        if v:
            return v
        time.sleep(interval)
    raise AssertionError(f'timed out waiting for {what}')


class InProc:

    def __init__(self, root, watch=None):
        self.root = Path(root)
        self.state, self.out = self.root / 'state', self.root / 'out'
        self.state.mkdir(parents=True, exist_ok=True)
        self.out.mkdir(exist_ok=True)
        self.watch = watch
        self.build()

    def build(self):
        cfg = config.load(self.state, fake_engine=True)
        cfg.two_card_proof = False
        config.ensure_state_dirs(cfg)
        self.cfg = cfg
        self.log = Logger(cfg.logs_dir, cfg.jobs_dir, echo=False)
        self.settings = Settings(self.state / 'settings.json', self.out, self.log)
        self.store = JobStore(cfg.jobs_dir, self.log)
        self.store.load_all()
        self.media = MediaLibrary(cfg.media_dir, self.log)
        self.runner = Runner(cfg, self.settings, self.store, self.media, self.log)
        self.lifecycle = lifecycle.Lifecycle(self.runner, self.log, watch=self.watch, exit_when_closed=False, poll_s=0.2)
        self.runner.lifecycle = self.lifecycle
        self.runner.recover()
        self.runner.port = 0
        self.runner.start()
        return self

    def stop(self):
        self.lifecycle.stop()
        self.runner.shutdown(timeout=20)
        if self.runner._health_thread is not None:
            self.runner._health_thread.join(20)

    def restart(self):
        self.stop()
        return self.build()

    def inputs(self, n=1, size=(96, 72), start=0):
        d = self.root / 'in'
        d.mkdir(exist_ok=True)
        paths = []
        for i in range(start, start + n):
            p = d / f'pic{i}.png'
            Image.fromarray(gradient(size[0], size[1], i)).save(p)
            paths.append(str(p))
        items, rejected = self.media.add_paths(paths)
        assert not rejected, rejected
        return [it['id'] for it in items]

    def job(self, mids, settings=None):
        job, _ = self.runner.create_job({'client_request_id': secrets.token_hex(16), 'media_ids': mids,
                                         'settings': settings or {}})
        return job['id']

    def item(self, jid, iid='i001'):
        return self.store.get(jid)['items'][int(iid[1:]) - 1]

    def raw(self, jid, iid='i001'):
        return self.store.item(jid, iid)

    def work(self, jid, iid='i001'):
        return self.cfg.work_dir / jid / iid

    def events(self, name=None):
        out = []
        for p in sorted(self.cfg.logs_dir.glob('app-*.jsonl')):
            for ln in p.read_text(encoding='utf8').splitlines():
                try:
                    r = json.loads(ln)
                except ValueError:
                    continue
                if name is None or r.get('event') == name:
                    out.append(r)
        return out

    def renders(self, gpu=0):
        p = self.cfg.workers_dir / f'gpu{gpu}' / 'fake-renders.jsonl'
        return [json.loads(x) for x in p.read_text(encoding='utf8').splitlines() if x.strip()] if p.exists() else []

    def prompts(self):
        out = {}
        for d in self.cfg.workers_dir.glob('gpu*/fake-prompts'):
            for p in d.glob('*.json'):
                out[p.stem] = json.loads(p.read_text(encoding='utf8'))
        return out


class Base(unittest.TestCase):
    env = FAST

    def setUp(self):
        self.d = tmpdir('cu-qa-engine-')
        self._env = mock.patch.dict(os.environ, self.env)
        self._env.start()
        self.svcs = []

    def tearDown(self):
        for s in self.svcs:
            try:
                s.stop()
            except Exception as e:
                print(f'\n(stop after the test: {type(e).__name__}: {e})')
        self._env.stop()
        rmtree(self.d)

    def svc(self, **kw):
        s = InProc(self.d / f's{len(self.svcs)}', **kw)
        self.svcs.append(s)
        return s


class Q1StopIntoSave(Base):
    def test_a_stop_the_moment_the_card_is_released_is_refused_and_the_image_is_saved(self):
        s = self.svc()
        gap, go = threading.Event(), threading.Event()
        orig = Runner._take_test_crash

        def hold(runner, kind):
            if kind == 'finish' and not gap.is_set():
                gap.set()
                go.wait(10)
            return orig(runner, kind)

        with mock.patch.object(Runner, '_take_test_crash', hold):
            jid = s.job(s.inputs(1))
            wait(gap.is_set, 30, 'the save to begin')
            self.assertEqual(s.item(jid)['state'], 'running')
            self.assertTrue(s.runner.ctx[(jid, 'i001')].worker_released)
            with self.assertRaises(ApiError) as cm:
                s.runner.stop_item(jid, 'i001')
            self.assertEqual((cm.exception.status, cm.exception.code, cm.exception.message),
                             (409, 'not_stoppable', 'This image is being saved and cannot be stopped now.'))
            go.set()
            it = wait(lambda: (lambda x: x if x['state'] == 'done' else None)(s.item(jid)), 30, 'done')
        self.assertTrue(Path(it['output']).is_file())
        self.assertFalse(s.events('item_state_failed'))
        self.assertEqual(s.store.get(jid)['state'], 'done')

    def test_a_cancel_while_saving_still_cancels(self):
        s = self.svc()
        gap, go = threading.Event(), threading.Event()
        orig = Runner._take_test_crash

        def hold(runner, kind):
            if kind == 'finish' and not gap.is_set():
                gap.set()
                go.wait(10)
            return orig(runner, kind)

        with mock.patch.object(Runner, '_take_test_crash', hold):
            jid = s.job(s.inputs(1))
            wait(gap.is_set, 30, 'the save to begin')
            s.runner.cancel_item(jid, 'i001')
            go.set()
            wait(lambda: s.item(jid)['state'] == 'cancelled', 30, 'cancelled')
        self.assertFalse(s.work(jid).exists())

    def test_record_never_leaves_an_image_active_with_no_thread(self):
        s = self.svc()
        jid = s.job(s.inputs(1))
        wait(lambda: s.item(jid)['state'] == 'done', 30, 'done')
        jid2 = s.job(s.inputs(1, start=1))
        with s.runner._lock:
            for st in ('preparing', 'running', 'finishing'):
                s.store.update_item(jid2, 'i001', state=st)
            rec = s.runner._record(jid2, 'i001', state='stopped', message='Stopped')
        self.assertEqual(rec['state'], 'failed')
        self.assertTrue(rec['message'].startswith('Something went wrong while this image was stopping. Queue it again.'))
        self.assertTrue(s.events('item_state_failed'))


class Q2JsonRoundTrip(Base):
    env = dict(FAST, CU_FAKE_STAGE_SECONDS='1.5')

    def test_effective_and_plan_equal_their_json_copies(self):
        _, eff = controls.resolve({'scale': 4})
        self.assertEqual(json.loads(json.dumps(eff)), eff)
        d = planner.plan(96, 64, 4).to_dict()
        self.assertEqual(json.loads(json.dumps(d)), d)
        self.assertEqual(controls.resolve({})[0]['toe'], (0.40, 0.06))

    def stopped_after_pass_1(self, s):
        jid = s.job(s.inputs(1), {'scale': 4})
        wait(lambda: (lambda x: x['state'] == 'running' and x['stage_index'] == 1)(s.item(jid)), 60, 'pass 2 to start')
        s.runner.stop_item(jid, 'i001')
        wait(lambda: s.item(jid)['state'] == 'stopped', 30, 'stopped')
        self.assertTrue((s.work(jid) / 'stage0.png').is_file())
        return jid

    def test_queue_again_after_a_restart_keeps_the_finished_passes(self):
        s = self.svc()
        jid = self.stopped_after_pass_1(s)
        s.restart()
        it = s.item(jid)
        self.assertEqual((it['state'], it['stage_index'], it['settings_changed']), ('stopped', 1, False))
        s.runner.requeue_item(jid, 'i001', front=True)
        it = s.item(jid)
        self.assertEqual(it['stage_index'], 1)
        self.assertTrue((s.work(jid) / 'stage0.png').is_file())
        text = [e['msg'] for e in s.events('item_requeued_by_user')]
        self.assertEqual(text, ['Queued pic0.png again'])
        wait(lambda: s.item(jid)['state'] == 'done', 60, 'done')
        self.assertEqual([r['stage'] for r in s.renders() if r['status'] == 'success'], [0, 1])

    def test_the_same_settings_after_a_restart_change_nothing(self):
        s = self.svc()
        jid = self.stopped_after_pass_1(s)
        s.restart()
        res = s.runner.set_item_settings([{'job_id': jid, 'item_id': 'i001'}], {'scale': 4})
        self.assertEqual(len(res['applied']), 1)
        it = s.item(jid)
        self.assertEqual((it['stage_index'], it['settings_changed']), (1, False))
        self.assertTrue((s.work(jid) / 'stage0.png').is_file())


def image_scales(pl):
    p, _ = controls.resolve({})
    out = []
    for st in pl.stages:
        f = 2 if st.factor == 2 else planner.Fraction(3, 2)
        s = {2.0: 2, 1.5: planner.Fraction(3, 2), 1.0: 1}[st.supersample]
        g, _ = graph_v5t.build('x.png', st.padded_size[0], st.padded_size[1], p, 'x', f=f, s=s)
        out += [(n['inputs']['width'], n['inputs']['height']) for n in g.values() if n['class_type'] == 'ImageScale']
    return out


class Q3WideImages(unittest.TestCase):
    def test_every_accepted_plan_stays_under_comfyuis_max(self):
        n = 0
        for factor in (2, 4, 6, 8):
            for long in range(1000, 9001, 500):
                for ar in (1.0, 1.78, 1.85, 2.0, 2.4, 4.0):
                    for w, h in ((long, max(64, int(long / ar))), (max(64, int(long / ar)), long)):
                        pl = planner.plan(w, h, factor)
                        if pl.ok:
                            n += 1
                            self.assertLessEqual(max(max(x) for x in image_scales(pl)), planner.MAX_SIDE, (w, h, factor))
        self.assertGreater(n, 300)

    def test_wide_images_take_a_lower_supersample_or_are_refused_in_plain_words(self):
        pl = planner.plan(2750, 1375, 4)
        self.assertTrue(pl.ok)
        self.assertEqual([(s.supersample, s.render_size) for s in pl.stages], [(2.0, (11000, 5504)), (1.0, (11000, 5504))])
        self.assertEqual(planner.plan(5500, 2750, 2).stages[0].supersample, 1.0)
        pl = planner.plan(3000, 1000, 6)
        self.assertFalse(pl.ok)
        self.assertEqual(pl.reason, '6× would make 18,000 × 6,000 px, over the 16,384 px limit for the longest side.')
        self.assertEqual(pl.suggestions, ['Choose 4× for this image', 'Or use a smaller source image'])
        self.assertEqual(planner.plan(3840, 2160, 4).to_dict(), json.loads(json.dumps(planner.plan(3840, 2160, 4).to_dict())))

    def test_the_fake_engine_refuses_as_comfyui_does_and_the_runner_says_so(self):
        d = tmpdir('cu-q3-')
        try:
            (d / 'input').mkdir()
            Image.new('RGB', (64, 64)).save(d / 'input' / 'x.png')
            g = {'1': {'class_type': 'LoadImage', 'inputs': {'image': 'x.png'}},
                 '2': {'class_type': 'ImageScale', 'inputs': {'image': ['1', 0], 'upscale_method': 'area', 'width': 16512,
                                                              'height': 64, 'crop': 'disabled'}},
                 '3': {'class_type': 'SaveImage', 'inputs': {'images': ['2', 0], 'filename_prefix': 'x'}}}
            with self.assertRaises(fake_comfy.GraphInvalid) as cm:
                fake_comfy.validate(g, d / 'input')
            err = cm.exception.node_errors['2']['errors'][0]
            self.assertEqual((err['type'], err['message'], err['details']),
                             ('value_bigger_than_max', 'Value 16512 bigger than max of 16384', 'width'))
            self.assertTrue(too_large({'node_errors': cm.exception.node_errors}))
            self.assertFalse(too_large({'node_errors': {'5': {'errors': [{'type': 'required_input_missing'}]}}}))
        finally:
            rmtree(d)


class Q4StopAndClose(Base):
    env = dict(FAST, CU_FAKE_FAULT='stall@s0', CU_FAKE_STAGE_SECONDS='2')

    def test_a_pass_that_ignores_the_interrupt_holds_the_engine_about_5_s_not_20(self):
        s = self.svc()
        jid = s.job(s.inputs(1))
        wait(lambda: s.item(jid)['state'] == 'running', 30, 'running')
        wait(lambda: s.events('prompt_queued'), 30, 'the pass to be sent')
        time.sleep(0.5)
        t0 = time.monotonic()
        s.lifecycle.close_request('stop')
        s.runner.shutdown(timeout=30)
        took = time.monotonic() - t0
        self.svcs.remove(s)
        self.assertLess(took, 12.0)
        timeout = s.events('interrupt_timeout')
        self.assertEqual([e['msg'] for e in timeout], ['The pass did not stop within 5 s; stopping the engine'])
        self.assertEqual(s.raw(jid)['state'], 'interrupted')
        stops = [e for e in s.events('worker_stopped') if 'did not stop after shutdown' in e['msg']]
        self.assertEqual(len(stops), 1)
        print(f'\n[Q-4] "Stop and close" in a stalled node: the engine was stopped {took:.1f} s after the close')


class Q5StopWhileTheEngineStarts(Base):
    env = dict(FAST, CU_FAKE_START_SECONDS='4')

    def preparing(self, s):
        jid = s.job(s.inputs(1))
        wait(lambda: (lambda x: x['state'] == 'preparing' and x['message'] == 'Starting the engine')(s.item(jid)), 30,
             'the engine start')
        return jid

    def test_queue_again_and_new_settings_at_once_after_a_stop(self):
        s = self.svc()
        jid = self.preparing(s)
        s.runner.stop_item(jid, 'i001')
        self.assertEqual(s.item(jid)['state'], 'stopped')
        self.assertIn((jid, 'i001'), s.runner.ctx)
        res = s.runner.set_item_settings([{'job_id': jid, 'item_id': 'i001'}], {'preset': 'Strong'})
        self.assertEqual(res['refused'], [])
        s.runner.requeue_item(jid, 'i001', front=True)
        self.assertEqual(s.item(jid)['state'], 'queued')
        it = wait(lambda: (lambda x: x if x['state'] == 'done' else None)(s.item(jid)), 60, 'done')
        self.assertEqual(it['effective']['preset'], 'Strong')
        states = [h['state'] for h in s.raw(jid)['history']]
        self.assertEqual(states[states.index('stopped'):], ['stopped', 'queued', 'preparing', 'running', 'finishing', 'done'])
        self.assertTrue(s.events('item_end_superseded'))
        self.assertEqual(len(s.events('worker_ready')), 1)

    def test_queue_again_at_once_after_a_cancel(self):
        s = self.svc()
        jid = self.preparing(s)
        s.runner.cancel_item(jid, 'i001')
        self.assertEqual(s.item(jid)['state'], 'cancelled')
        s.runner.requeue_item(jid, 'i001', front=True)
        wait(lambda: s.item(jid)['state'] == 'done', 60, 'done')
        self.assertTrue(Path(s.item(jid)['output']).is_file())


class Q6SettingsUndo(Base):
    env = dict(FAST, CU_FAKE_STAGE_SECONDS='1.5')

    def test_changing_the_settings_back_resumes_from_the_finished_passes(self):
        s = self.svc()
        jid = s.job(s.inputs(1), {'scale': 4})
        wait(lambda: (lambda x: x['state'] == 'running' and x['stage_index'] == 1)(s.item(jid)), 60, 'pass 2 to start')
        s.runner.stop_item(jid, 'i001')
        wait(lambda: s.item(jid)['state'] == 'stopped' and (jid, 'i001') not in s.runner.ctx, 30, 'stopped')
        ref = [{'job_id': jid, 'item_id': 'i001'}]
        self.assertEqual(s.runner.set_item_settings(ref, {'scale': 4, 'preset': 'Strong'})['refused'], [])
        it = s.item(jid)
        self.assertEqual((it['stage_index'], it['settings_changed']), (0, True))
        self.assertFalse((s.work(jid) / 'stage0.png').exists())
        self.assertTrue((s.work(jid) / 'kept' / 'stage0.png').is_file())
        self.assertNotIn('kept_passes', it)
        s.runner.set_item_settings(ref, {'scale': 4})
        it = s.item(jid)
        self.assertEqual((it['stage_index'], it['settings_changed']), (1, False))
        self.assertTrue((s.work(jid) / 'stage0.png').is_file())
        self.assertFalse((s.work(jid) / 'kept').exists())
        s.runner.requeue_item(jid, 'i001', front=True)
        self.assertEqual(s.item(jid)['stage_index'], 1)
        wait(lambda: s.item(jid)['state'] == 'done', 60, 'done')
        self.assertEqual([r['stage'] for r in s.renders() if r['status'] == 'success'], [0, 1])

    def test_queued_with_other_settings_the_kept_passes_go(self):
        s = self.svc()
        jid = s.job(s.inputs(1), {'scale': 4})
        wait(lambda: (lambda x: x['state'] == 'running' and x['stage_index'] == 1)(s.item(jid)), 60, 'pass 2 to start')
        s.runner.stop_item(jid, 'i001')
        wait(lambda: s.item(jid)['state'] == 'stopped' and (jid, 'i001') not in s.runner.ctx, 30, 'stopped')
        s.runner.set_item_settings([{'job_id': jid, 'item_id': 'i001'}], {'scale': 4, 'preset': 'Light'})
        s.runner.requeue_item(jid, 'i001', front=True)
        self.assertEqual(s.item(jid)['stage_index'], 0)
        self.assertFalse((s.work(jid) / 'kept').exists())
        wait(lambda: s.item(jid)['state'] == 'done', 60, 'done')


def pack_input_types():
    import importlib.util
    import types

    class Stub(types.ModuleType):
        def __getattr__(self, name):
            if name.startswith('__'):
                raise AttributeError(name)
            m = Stub(f'{self.__name__}.{name}')
            setattr(self, name, m)
            return m

        def __call__(self, *a, **k):
            return Stub('call')

    with mock.patch.dict(sys.modules):
        for n in ('torch', 'torch.nn', 'torch.nn.functional', 'comfy', 'comfy.utils', 'comfy.model_management', 'nodes',
                  'folder_paths', 'kornia'):
            sys.modules[n] = Stub(n)
        p = REPO / 'node_pack' / 'claude_creative' / '__init__.py'
        spec = importlib.util.spec_from_file_location('cu_qa_pack', p, submodule_search_locations=[str(p.parent)])
        m = importlib.util.module_from_spec(spec)
        sys.modules['cu_qa_pack'] = m
        spec.loader.exec_module(m)
        out = {}
        wanted = set(workers.required_inputs(True)) | set(fake_comfy.NODE_OPTIONAL)
        for name in sorted(wanted):
            t = m.NODE_CLASS_MAPPINGS[name].INPUT_TYPES()
            out[name] = set(t.get('required') or {}) | set(t.get('optional') or {})
        return out


class Q7NodePackInputs(unittest.TestCase):
    def test_the_repo_pack_and_the_fake_engine_declare_every_input_the_graphs_send(self):
        pack = pack_input_types()
        for multi in (False, True):
            for cls, names in workers.required_inputs(multi).items():
                self.assertLessEqual(set(names), pack[cls], cls)
        fake = fake_comfy.FakeComfy(tmpdir('cu-q7-'), faults='')
        info = fake.object_info()
        self.assertEqual(workers.undeclared_inputs(info, multi=True), {})
        for cls in fake_comfy.NODE_OPTIONAL:
            spec = info[cls]['input']
            self.assertEqual(set(spec['required']) | set(spec['optional']), pack[cls], cls)
        rmtree(fake.root)

    def test_an_older_pack_is_refused_before_any_image_runs(self):
        root = tmpdir('cu-q7-')
        fake = fake_comfy.FakeComfy(root, faults='oldpack', fault_dir=str(root / 'faults'))
        info = fake.object_info()
        rmtree(root)
        missing = workers.undeclared_inputs(info)

        self.assertEqual(missing, {'ClaudeSpotTiles': ['batch_windows', 'cfg_end', 'fp16_acc_scoped', 'live_preview',
                                                       'noise_prefetch', 'pag_end', 'pag_fuse', 'seam_overlap']})
        w = workers.Worker.__new__(workers.Worker)
        w.client = mock.Mock(object_info=lambda: info)
        with self.assertRaises(workers.WorkerError) as cm:
            w._check_nodes()
        self.assertEqual(str(cm.exception), 'The engine is missing parts it needs. Reinstall Creative Upscaler.')
        self.assertEqual(cm.exception.detail['undeclared_inputs'], missing)

    def test_the_repair_the_log_names_is_no_longer_the_old_pack(self):
        d = tmpdir('cu-q7-')
        try:
            res = config.verify_node_pack(d / 'missing')
            text = ' '.join(res['details'])
            self.assertNotIn('; run tools/sync_node_pack.py', text)
            self.assertIn('install/deploy.py', text)
            self.assertIn('do not run tools/sync_node_pack.py', text)
        finally:
            rmtree(d)


class Q9OneName(unittest.TestCase):
    def test_gpu_names(self):
        self.assertEqual(workers.gpu_names([0]), 'GPU 1')
        self.assertEqual(workers.gpu_names([0, 1]), 'GPU 1 and GPU 2')
        self.assertEqual(workers.gpu_names([0, 1, 2]), 'GPU 1, GPU 2 and GPU 3')
        with self.assertRaises(KeyError) as cm:
            workers.cuda_visible_devices([0, 1], {0: {'uuid': 'a'}})
        self.assertEqual(cm.exception.args[0], 'GPU 2 was not found.')

    def test_no_engine_log_line_names_another_product_or_graphics_card_n(self):
        import re
        from tools.public_scan import load_private_terms  # the maintainer's local list; empty without it
        for name in ('lifecycle.py', 'runner.py', 'workers.py', 'app.py'):
            src = (REPO / 'service' / name).read_text(encoding='utf8')
            for m in re.finditer(r"self\.log\.\w+\('[a-z_]+',\s*f?'([^']*)'", src):
                for term in load_private_terms():
                    self.assertNotIn(term.lower(), m.group(1).lower(), (name, m.group(1)))
                self.assertIsNone(re.search(r'graphics cards? \{', m.group(1)), (name, m.group(1)))


class Q9Lines(Base):
    def test_lifecycle_and_start_lines(self):
        s = self.svc()
        s.lifecycle.close_request('finish')
        s.lifecycle.close_request('stop')
        msgs = [e['msg'] for e in s.events() if e.get('event') in ('app_close_finish', 'app_close_stop')]
        self.assertTrue(all(m.startswith('Artegra Enhancer is closing: ') for m in msgs) and len(msgs) == 2, msgs)
        jid = s.job(s.inputs(1))
        wait(lambda: s.item(jid)['state'] == 'done', 30, 'done')
        self.assertEqual([e['msg'] for e in s.events('worker_starting')], ['Starting the engine on GPU 1'])


class Q11OutputInfo(Base):
    def test_a_finished_image_says_its_bytes_and_size(self):
        s = self.svc()
        jid = s.job(s.inputs(1))
        it = wait(lambda: (lambda x: x if x['state'] == 'done' else None)(s.item(jid)), 30, 'done')
        info = it['output_info']
        self.assertEqual(info['bytes'], os.path.getsize(it['output']))
        self.assertEqual(info['size'], it['plan']['output_size'])
        self.assertEqual(info['sha256'], json.loads(Path(it['sidecar']).read_text(encoding='utf8'))['output']['sha256'])


class Q12LastFrame(unittest.TestCase):
    def test_a_dropped_image_keeps_its_last_frame_for_a_few_seconds_only(self):
        import io
        board = live.LiveBoard()
        c = board.begin('j1', 'i001', media_id='m1', stage=0, stages=1, out_size=(400, 300), supersample=2.0,
                        frame=(400, 300), samplers={'structure': '19', 'detail': '15'}, mode='rough', cards=[0])
        buf = io.BytesIO()
        Image.new('RGB', (50, 37), (200, 10, 10)).save(buf, 'JPEG')
        c.on_frame({'kind': 'init', 'pass': 1, 'node': '19', 'steps': 30, 'canvas_latent': [50, 37], 'image': True},
                   buf.getvalue())
        self.assertIsNone(board.recent('j1', 'i001'))
        board.drop('j1', 'i001')
        self.assertIsNone(board.get('j1', 'i001'))
        self.assertEqual(board.summary()['items'], [])
        got = board.recent('j1', 'i001')
        self.assertTrue(got.jpeg()[:2] == b'\xff\xd8' and got.thumb()[:2] == b'\xff\xd8')
        with mock.patch.object(live, 'GONE_KEEP_S', 0.0):
            time.sleep(0.1)
            self.assertIsNone(board.recent('j1', 'i001'))


class Q13ToastLaunch(unittest.TestCase):
    def test_clickable_only_while_the_launcher_script_is_there(self):
        d = tmpdir('cu-q13-')
        try:
            vbs = d / 'Start Artegra Enhancer.vbs'
            cmd = f'"{Path(os.environ.get('SystemRoot') or Path.home()) / 'System32' / 'wscript.exe'}" "{vbs}" /open:creative-upscaler'
            with mock.patch.object(notify, '_protocol_command', lambda: cmd):
                self.assertEqual(notify.launch_uri(), '')
                vbs.write_text("' launcher", encoding='utf8')
                self.assertEqual(notify.launch_uri(), notify.LAUNCH)
            with mock.patch.object(notify, '_protocol_command', lambda: None):
                self.assertEqual(notify.launch_uri(), '')
            self.assertFalse(notify.launch_target_ok(f'"{Path.home() / 'x' / 'app.exe'}" /open'))
        finally:
            rmtree(d)


class Q14Background(unittest.TestCase):
    class Runner:
        def __init__(self, busy=True):
            self.busy = busy

        def work_summary(self):
            return {'images_running': 1 if self.busy else 0, 'images_saving': 0, 'images_waiting': 0}

        def wake(self):
            pass

    class Watch:
        def __init__(self, pids):
            self.pids, self.names = set(pids), ['Artegra Enhancer.exe']

        def gone(self):
            return not self.pids

        def info(self):
            return {}

    def make(self, pids):
        from tests.service.test_v4_units import Log
        return lifecycle.Lifecycle(self.Runner(), Log(), watch=self.Watch(pids), exit_when_closed=False, poll_s=1)

    @unittest.skip('standalone: closing stops the engine; finishing in the background is not part of the Beta')
    def test_not_in_the_background_while_another_window_is_open(self):
        lc = self.make([101, 202])
        lc.close_request('finish')
        self.assertFalse(lc.in_background())

    @unittest.skip('standalone: closing stops the engine; finishing in the background is not part of the Beta')
    def test_the_flag_clears_when_the_batch_ends(self):
        lc = self.make([101])
        lc.close_request('finish')
        self.assertTrue(lc.in_background())
        lc.batch_ended()
        self.assertFalse(lc.in_background())


class Q14Runner(Base):
    def test_a_later_batch_with_the_window_kept_raises_no_notification(self):
        s = self.svc()
        jid = s.job(s.inputs(1))
        s.lifecycle.close_request('finish')
        wait(lambda: s.item(jid)['state'] == 'done', 30, 'done')
        wait(lambda: not s.lifecycle.in_background(), 10, 'the flag to clear')
        self.assertEqual([r['kind'] for r in s.runner.notifier.sent], ['batch_end'])
        jid2 = s.job(s.inputs(1, start=1))
        wait(lambda: s.item(jid2)['state'] == 'done', 30, 'done')
        time.sleep(1.0)
        self.assertEqual([r['kind'] for r in s.runner.notifier.sent], ['batch_end'])


class Q15MaskAfterShared(Base):
    env = dict(FAST, CU_FAKE_GPUS='2')

    def test_a_mask_preview_never_starts_a_second_engine_on_a_card_the_shared_engine_holds(self):
        s = self.svc()
        mids = s.inputs(1)
        jid = s.job(mids)
        it = wait(lambda: (lambda x: x if x['state'] == 'done' else None)(s.item(jid)), 30, 'the shared image')
        self.assertEqual(it['cards'] or it['run']['cards'], [0, 1])
        self.assertTrue(any(mw.state == 'ready' for mw in s.runner.multi.values()))
        seen = []
        orig = workers.Worker.ensure_started

        def look(w, *a, **k):
            if not isinstance(w, workers.MultiCardWorker):
                seen.append([(key, mw.state, mw.fake is not None) for key, mw in s.runner.multi.items()
                             if w.gpu in key and (mw.fake is not None or mw.state in ('ready', 'starting'))])
            return orig(w, *a, **k)

        with mock.patch.object(workers.Worker, 'ensure_started', look):
            res = s.runner.mask_preview(mids[0], protect=['people'])
        self.assertTrue(res['mask_url'])
        self.assertEqual(seen, [[]])
        lines = [(e['event'], e['msg']) for e in s.events() if e.get('event') in ('worker_stopped', 'worker_starting')]
        stop = lines.index(('worker_stopped', 'The engine on GPU 1 and GPU 2 stopped (the protected-area preview needs GPU 1)'))
        self.assertGreater(lines.index(('worker_starting', 'Starting the engine on GPU 1')), stop)


@unittest.skipUnless(os.name == 'nt' and notify.powershell(), 'Windows PowerShell not found')
class Q16ContainedToast(unittest.TestCase):
    def test_the_helper_dies_with_the_service(self):
        from service.windows_job import process_alive
        d = tmpdir('cu-q16-')
        try:
            pidfile = d / 'ps.pid'
            script = '"$PID" | Out-File -Encoding ascii $env:CU_TEST_PIDFILE; Start-Sleep -Seconds 20; "ready"'
            child = ('import sys; sys.path.insert(0, %r); from service import notify; '
                     'print(notify._run("t", "x", check=True, log_dir=%r, script=%r))' % (str(REPO), str(d), script))
            p = subprocess.Popen([sys.executable, '-B', '-c', child], env=dict(os.environ, CU_TEST_PIDFILE=str(pidfile)),
                                 creationflags=0x08000000, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                wait(lambda: pidfile.is_file() and pidfile.read_text(encoding='ascii').strip(), 30, 'PowerShell to start')
                ps = int(pidfile.read_text(encoding='ascii').strip())
                self.assertTrue(process_alive(ps))
            finally:
                p.kill()
                p.wait(10)
            wait(lambda: not process_alive(ps), 10, 'the helper to end with the service')
        finally:
            rmtree(d)

    def test_it_still_builds_a_toast_without_showing_it(self):
        d = tmpdir('cu-q16-')
        try:
            ok, why = notify._run(notify.TITLE, 'check: nothing is shown', check=True, log_dir=d)
            self.assertTrue(ok, why)
            self.assertEqual(list(d.iterdir()), [])
        finally:
            rmtree(d)


class Q17EmptyOwnSettings(Base):
    env = dict(FAST, CU_FAKE_STAGE_SECONDS='2')

    def test_an_images_own_empty_settings_render_as_default(self):
        s = self.svc()
        mids = s.inputs(2)
        jid = s.job(mids, {'preset': 'Strong', 'scale': 2, 'seed': '777'})
        res = s.runner.set_item_settings([{'job_id': jid, 'item_id': 'i002'}], {})
        self.assertEqual(len(res['applied']), 1)
        wait(lambda: s.item(jid, 'i002')['state'] == 'done', 60, 'done')
        g = next(v for k, v in s.prompts().items() if f'{jid}_i002_s0' in k)
        ks = sorted((n['inputs']['denoise'], n['inputs']['seed']) for n in g.values() if n['class_type'] == 'KSampler')
        self.assertEqual(ks, [(0.55, controls.DEFAULT_SEED), (0.58, controls.DEFAULT_SEED)])
        side = json.loads(Path(s.item(jid, 'i002')['sidecar']).read_text(encoding='utf8'))
        self.assertEqual((side['effective']['preset'], side['stage_seeds']), ('Default', [str(controls.DEFAULT_SEED)]))


class Q18OldRecordResume(Base):
    def test_a_record_without_run_resumes_with_the_numbers_it_started_with(self):
        s = self.svc()
        job = {'effective': {'mode': 'standard'}}

        self.assertEqual(s.runner._run_choice(job, {'stage_index': 1}), ('standard', True, False))
        self.assertEqual(s.runner._run_choice(job, {'stage_index': 0}), ('standard', False, False))
        frozen = {'stage_index': 1, 'run': {'frozen': True, 'mode': 'standard', 'match_earlier': False}}
        self.assertEqual(s.runner._run_choice(job, frozen), ('standard', False, False))


class Q19LaterPasses(unittest.TestCase):
    def ladder(self, req):
        p, _ = controls.resolve(dict(req, scale=8))
        return [controls.stage_params(p, k)['denoise'] for k in range(3)]

    def test_later_passes_never_invent_more_and_the_judged_ladder_stays(self):
        self.assertEqual(self.ladder({}), [0.58, 0.56, 0.544])
        self.assertEqual(self.ladder({'preset': 'Strong'}), [0.604, 0.5792, 0.5594])
        self.assertEqual(self.ladder({'preset': 'Light'}), [0.436, 0.4288, 0.423])
        for c in (0, 5, 10, 15, 20, 22, 22.3, 23, 28, 40, 50, 77, 100):
            lad = self.ladder({'preset': 'Default', 'custom': True, 'creativity': c, 'resemblance': 60, 'restoration': 35})
            self.assertTrue(lad[0] >= lad[1] >= lad[2], (c, lad))
        self.assertEqual(self.ladder({'preset': 'Default', 'custom': True, 'creativity': 0, 'resemblance': 60,
                                      'restoration': 35}), [0.4, 0.4, 0.4])


class Q20FloatScale(unittest.TestCase):
    def test_a_whole_float_is_that_factor_and_anything_else_is_refused(self):
        _, eff = controls.resolve({'scale': 2.0})
        self.assertEqual((eff['scale'], type(eff['scale'])), (2, int))
        self.assertEqual(planner.plan(320, 240, eff['scale']).factor, 2)
        for bad in (2.5, True, '2', None, 3):
            with self.assertRaises(controls.ControlError, msg=repr(bad)):
                controls.resolve({'scale': bad})


class Q20Output(Base):
    def test_the_output_is_named_for_the_whole_factor(self):
        s = self.svc()
        jid = s.job(s.inputs(1), {'scale': 2.0})
        it = wait(lambda: (lambda x: x if x['state'] == 'done' else None)(s.item(jid)), 30, 'done')
        self.assertEqual(Path(it['output']).name, 'pic0_cu2x.png')


class NewAFinishTime(unittest.TestCase):
    def test_before_the_sampler_the_planned_time_is_used(self):

        self.assertAlmostEqual(stage_left_s(2.0, 0.10, 740.0), 738.0)
        self.assertAlmostEqual(stage_left_s(118.0, 0.11, 740.0), 622.0)
        self.assertAlmostEqual(stage_left_s(800.0, 0.11, 740.0), 37.0)

    def test_once_the_sampler_runs_its_own_rate_takes_over(self):
        early = stage_left_s(130.0, 0.13, 740.0, sampling_s=10.0, frac_at_sampling=0.12, sampler_done=0.01)
        self.assertAlmostEqual(early, 0.96 * 610.0 + 0.04 * (0.87 * 10.0 / 0.01), places=6)
        late = stage_left_s(400.0, 0.55, 740.0, sampling_s=280.0, frac_at_sampling=0.12, sampler_done=0.6)
        self.assertAlmostEqual(late, 0.45 * 280.0 / 0.43)

    def test_the_tracker_says_when_the_sampler_has_started(self):
        t = comfy.ProgressTracker({'1': {'class_type': 'LoadImage'}, '2': {'class_type': 'KSampler'},
                                   '3': {'class_type': 'KSampler'}}, 'p')
        t.on_message({'type': 'executing', 'data': {'node': '1', 'prompt_id': 'p'}})
        t.on_message({'type': 'executing', 'data': {'node': '2', 'prompt_id': 'p'}})
        self.assertIsNone(t.node_progress(['2', '3']))
        t.on_message({'type': 'progress', 'data': {'node': '2', 'value': 3, 'max': 30, 'prompt_id': 'p'}})
        self.assertAlmostEqual(t.node_progress(['2', '3']), 0.05)
        t.on_message({'type': 'executing', 'data': {'node': '3', 'prompt_id': 'p'}})
        self.assertAlmostEqual(t.node_progress(['2', '3']), 0.5)


if __name__ == '__main__':
    unittest.main()
