import io
import json
import os
import time
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
from PIL import Image

from service import comfy, engine_options, live
from tests.service.test_v4 import V4Base, wait
from tests.service.test_integration import all_done


def jpeg(color, size):
    buf = io.BytesIO()
    Image.new('RGB', size, color).save(buf, format='JPEG', quality=95)
    return buf.getvalue()


def canvas(groups=True, run_order=('detail', 'structure'), mode='detailed', cards=(0,)):
    src = Image.new('RGB', (512, 512), (90, 90, 90))
    return live.LiveCanvas('j1', 'i001', 'm1', 0, 1, (512, 512), 2.0, (512, 512), {'structure': '19', 'detail': '15'}, mode,
                           list(cards), source=src, run_order=list(run_order), groups=groups)


def init(c, node, pass_no, steps=4):
    c.on_frame({'kind': 'init', 'image': False, 'source': 'taesd', 'node': node, 'pass': pass_no, 'step': -1, 'steps': steps,
                'rect_latent': [0, 0, 128, 128], 'canvas_latent': [128, 128]})


def group(c, step, index, n, wins, card=0, phase='cfg', node='15', steps=4):
    c.on_frame({'kind': 'group', 'state': 'start', 'node': node, 'step': step, 'steps': steps, 'index': index, 'n': n,
                'total': n * 2, 'windows_latent': wins, 'rect_latent': wins[0], 'canvas_latent': [128, 128], 'card': card,
                'phase': phase, 'source': 'taesd'})


def win(c, step, rect, color, steps=4, node='15'):
    c.on_frame({'kind': 'win', 'image': True, 'source': 'taesd', 'node': node, 'step': step, 'steps': steps,
                'rect_latent': rect, 'canvas_latent': [128, 128], 'card': 0}, jpeg(color, (rect[2] * 8, rect[3] * 8)))


class Compositor(unittest.TestCase):
    def test_group_frames_give_every_window_of_the_group_and_the_evaluation(self):
        c = canvas()
        init(c, '15', 1)
        group(c, 0, 0, 3, [[96, 0, 32, 32], [0, 32, 32, 32]])
        s = c.snapshot('/api/jobs/j1/items/i001')
        self.assertEqual(s['pass'], 'detail')
        self.assertEqual(s['pass_index'], 1)
        self.assertEqual(s['pass_order'], ['detail', 'structure'])
        self.assertEqual(s['rects'], [{'x': 0.75, 'y': 0.0, 'w': 0.25, 'h': 0.25, 'card': 0},
                                      {'x': 0.0, 'y': 0.25, 'w': 0.25, 'h': 0.25, 'card': 0}])
        self.assertEqual(s['evaluation'], [{'card': 0, 'group': 0, 'groups': 3, 'windows': 2, 'phase': 'cfg'}])
        self.assertEqual(s['step'], 1)
        self.assertAlmostEqual(s['step_progress'], 1 / 3, places=3)
        group(c, 0, 2, 3, [[64, 64, 32, 32]])
        self.assertEqual(c.snapshot('/x')['step_progress'], 1.0)
        group(c, 1, 0, 2, [[0, 0, 32, 32], [32, 0, 32, 32]])
        s = c.snapshot('/x')
        self.assertEqual((s['step'], s['evaluation'][0]['groups'], s['step_progress']), (2, 2, 0.5))

    def test_a_pag_evaluation_makes_each_evaluation_half_a_step(self):
        c = canvas()
        init(c, '15', 1)
        group(c, 0, 1, 2, [[0, 0, 32, 32]], phase='cfg')
        self.assertEqual(c.snapshot('/x')['step_progress'], 1.0)
        group(c, 0, 0, 2, [[0, 0, 32, 32]], phase='pag')
        self.assertEqual(c.snapshot('/x')['step_progress'], 0.75)
        group(c, 1, 0, 2, [[0, 0, 32, 32]], phase='cfg')
        self.assertEqual(c.snapshot('/x')['step_progress'], 0.25)

    def test_two_cards(self):
        c = canvas(cards=(0, 1))
        init(c, '15', 1)
        group(c, 0, 0, 4, [[0, 0, 32, 32], [32, 0, 32, 32]], card=0)
        group(c, 0, 1, 4, [[64, 0, 32, 32], [96, 0, 32, 32]], card=1)
        s = c.snapshot('/x')
        self.assertEqual([r['card'] for r in s['rects']], [0, 0, 1, 1])
        self.assertEqual([e['card'] for e in s['evaluation']], [0, 1])
        self.assertEqual(s['step_progress'], 0.5)

    def test_v4_start_frames_one_window_a_card_and_no_evaluation(self):
        c = canvas(groups=False, run_order=('structure', 'detail'))
        init(c, '19', 1)
        c.on_frame({'kind': 'start', 'node': '19', 'step': 0, 'steps': 4, 'rect_latent': [0, 0, 32, 32],
                    'canvas_latent': [128, 128], 'card': 0, 'phase': 'cfg'})
        s = c.snapshot('/x')
        self.assertEqual(s['pass'], 'structure')
        self.assertEqual(s['rects'], [{'x': 0.0, 'y': 0.0, 'w': 0.25, 'h': 0.25, 'card': 0}])
        self.assertEqual((s['evaluation'], s['step_progress']), (None, None))
        self.assertEqual(s['pass_order'], ['structure', 'detail'])

    def test_the_earlier_pass_keeps_its_last_picture(self):
        c = canvas()
        init(c, '15', 1)
        self.assertIsNone(c.snapshot('/b')['earlier_pass'])
        self.assertIsNone(c.snapshot('/b')['timing']['first_tile_s'])
        group(c, 3, 0, 1, [[0, 0, 128, 128]])
        win(c, 3, [0, 0, 128, 128], (200, 40, 40))
        self.assertIsNotNone(c.snapshot('/b')['timing']['first_tile_s'])
        c.on_frame({'kind': 'pass_end', 'node': '15', 'stats': {}})
        self.assertEqual(c.snapshot('/b')['state'], 'between')
        self.assertIsNone(c.earlier_jpeg())
        init(c, '19', 2)
        s = c.snapshot('/b')
        self.assertEqual(s['pass'], 'structure')
        e = s['earlier_pass']
        self.assertEqual((e['pass'], e['size'], e['preview']), ('detail', [512, 512], 'detailed'))
        self.assertEqual(e['url'], f'/b/live-pass.jpg?seq={e["seq"]}')
        held = np.asarray(Image.open(io.BytesIO(c.earlier_jpeg())).convert('RGB'), dtype=np.int16)
        self.assertLess(np.abs(held - np.array([200, 40, 40])).max(), 12)
        now = np.asarray(Image.open(io.BytesIO(c.jpeg(force=True))).convert('RGB'), dtype=np.int16)
        self.assertLess(np.abs(now - 90).max(), 12)

        board = live.LiveBoard()
        board._live[('j1', 'i001')] = c
        board.freeze('j1', 'i001', 'stopped')
        f = board.get('j1', 'i001')
        self.assertEqual(f.earlier_jpeg(), c.earlier_jpeg())
        snap = f.snapshot('/b')
        self.assertEqual(snap['earlier_pass']['pass'], 'detail')
        self.assertEqual((snap['rects'], snap['evaluation'], snap['step_progress']), ([], [], None))

    def test_no_earlier_pass_for_the_first_pass_or_a_new_stage(self):
        c = canvas()
        init(c, '15', 1)
        init(c, '15', 1)
        e = c.snapshot('/b')['earlier_pass']
        self.assertTrue(e is None or e['pass'] == 'detail')
        self.assertIsNone(canvas().snapshot('/b')['earlier_pass'])


class EarlierAfterItGoes(unittest.TestCase):

    KW = dict(media_id='m1', stages=2, supersample=2.0, samplers={'structure': '19', 'detail': '15'}, mode='detailed',
              cards=[0], run_order=['detail', 'structure'], groups=True)

    def two_passes(self, c, color):
        init(c, '15', 1)
        group(c, 3, 0, 1, [[0, 0, 128, 128]])
        win(c, 3, [0, 0, 128, 128], color)
        c.on_frame({'kind': 'pass_end', 'node': '15', 'stats': {}})
        init(c, '19', 2)
        self.assertTrue(c.earlier_jpeg())
        return c.earlier_jpeg()

    def test_the_stage_befores_earlier_pass_and_an_ended_images(self):
        board = live.LiveBoard()
        c = board.begin('j1', 'i001', stage=0, out_size=(512, 512), frame=(512, 512),
                        source=Image.new('RGB', (512, 512), (90, 90, 90)), **self.KW)
        held = self.two_passes(c, (200, 40, 40))
        self.assertIsNone(board.recent_earlier('j1', 'i001'))
        c2 = board.begin('j1', 'i001', stage=1, out_size=(1024, 1024), frame=(1024, 1024),
                         source=Image.new('RGB', (1024, 1024), (90, 90, 90)), **self.KW)
        self.assertIsNone(c2.earlier_jpeg())
        self.assertIsNone(c2.snapshot('/b')['earlier_pass'])
        self.assertEqual(board.recent_earlier('j1', 'i001'), held)
        self.assertIsNone(board.recent_earlier('j1', 'i002'))
        with mock.patch.object(live, 'GONE_KEEP_S', 0.0):
            time.sleep(0.1)
            self.assertIsNone(board.recent_earlier('j1', 'i001'))

        held2 = self.two_passes(c2, (40, 200, 40))
        board.drop('j1', 'i001')
        self.assertIsNone(board.get('j1', 'i001'))
        self.assertEqual(board.recent('j1', 'i001').earlier_jpeg(), held2)
        with mock.patch.object(live, 'GONE_KEEP_S', 0.0):
            time.sleep(0.1)
            self.assertIsNone(board.recent('j1', 'i001'))


class Tracker(unittest.TestCase):
    def tracker(self):
        g = {'15': {'class_type': 'KSampler', 'inputs': {}}, '19': {'class_type': 'KSampler', 'inputs': {}}}
        t = comfy.ProgressTracker(g, 'p1')
        t.on_message({'type': 'executing', 'data': {'prompt_id': 'p1', 'node': '15'}})
        return t

    def meta(self, step, index, n, phase='cfg', node='15', steps=4, pid='p1'):
        return {'kind': 'group', 'prompt_id': pid, 'node': node, 'step': step, 'steps': steps, 'index': index, 'n': n,
                'phase': phase}

    def test_the_fraction_moves_within_a_step(self):
        t = self.tracker()
        self.assertIsNone(t.node_progress(['15', '19']))
        t.on_group(self.meta(0, 0, 4))
        self.assertAlmostEqual(t.current_frac, 0.25 / 4)
        self.assertIsNotNone(t.node_progress(['15', '19']))
        t.on_group(self.meta(0, 3, 4))
        self.assertAlmostEqual(t.current_frac, 1 / 4)
        t.on_message({'type': 'progress', 'data': {'prompt_id': 'p1', 'node': '15', 'value': 1, 'max': 4}})
        self.assertAlmostEqual(t.current_frac, 1 / 4)
        t.on_group(self.meta(0, 1, 4))
        self.assertAlmostEqual(t.current_frac, 1 / 4)
        t.on_group(self.meta(1, 1, 4))
        self.assertAlmostEqual(t.current_frac, 1.5 / 4)

    def test_pag_halves_and_what_is_ignored(self):
        t = self.tracker()
        t.on_group(self.meta(0, 1, 2, phase='pag'))
        self.assertAlmostEqual(t.current_frac, 1 / 4)
        t.on_group(self.meta(1, 1, 2, phase='cfg'))
        self.assertAlmostEqual(t.current_frac, 1.5 / 4)
        before = t.current_frac
        for bad in (self.meta(3, 0, 2, pid='other'), self.meta(3, 0, 2, node='19'), dict(self.meta(3, 0, 2), n=0),
                    dict(self.meta(3, 0, 2), index=5), dict(self.meta(3, 0, 2), step='x')):
            t.on_group(bad)
        self.assertEqual(t.current_frac, before)


OFF4 = {'creative_first': False, 'outline_groups': False, 'creative_first_shared': False, 'outline_groups_shared': False}
ON1 = {'creative_first': True, 'outline_groups': True, 'creative_first_shared': False, 'outline_groups_shared': False}
ON4 = {'creative_first': True, 'outline_groups': True, 'creative_first_shared': True, 'outline_groups_shared': True}
V5_ENV = ('CU_CREATIVE_FIRST', 'CU_OUTLINE_GROUPS', 'CU_V5_SPLIT', 'CU_LIVE_PREVIEW')


class Switches(unittest.TestCase):
    def test_on_from_run_a2_on_one_card_and_the_overrides(self):
        self.assertTrue(engine_options.CREATIVE_FIRST_PROVEN)
        self.assertTrue(engine_options.OUTLINE_GROUPS_PROVEN)
        with mock.patch.dict(os.environ, {}, clear=False):
            for k in V5_ENV:
                os.environ.pop(k, None)
            self.assertEqual(engine_options.live_switches(), ON1)
            self.assertEqual(engine_options.live_mode(True), 'detailed')
            os.environ.update(CU_CREATIVE_FIRST='1', CU_OUTLINE_GROUPS='1', CU_LIVE_PREVIEW='off')
            self.assertEqual(engine_options.live_switches(), ON1)
            self.assertEqual((engine_options.live_mode(True), engine_options.live_mode(False)), ('off', 'off'))
            self.assertEqual(engine_options.spot_options(True)['live_preview'], 'off')
            with mock.patch.object(engine_options, 'CREATIVE_FIRST_PROVEN', True), \
                    mock.patch.object(engine_options, 'OUTLINE_GROUPS_PROVEN', True):
                os.environ.update(CU_CREATIVE_FIRST='0', CU_OUTLINE_GROUPS='0')
                self.assertEqual(engine_options.live_switches(), OFF4)
                os.environ.pop('CU_CREATIVE_FIRST'); os.environ.pop('CU_OUTLINE_GROUPS')
                self.assertEqual(engine_options.live_switches(), ON1)

    def test_a_shared_image_needs_its_own_two_card_run(self):
        self.assertFalse(engine_options.V5_SPLIT_PROVEN)
        with mock.patch.dict(os.environ, {}, clear=False):
            for k in V5_ENV:
                os.environ.pop(k, None)
            with mock.patch.object(engine_options, 'CREATIVE_FIRST_PROVEN', True), \
                    mock.patch.object(engine_options, 'OUTLINE_GROUPS_PROVEN', True):
                self.assertEqual(engine_options.live_switches(), ON1)
                self.assertEqual((engine_options.creative_first_on(), engine_options.creative_first_on(shared=True)),
                                 (True, False))
                self.assertEqual((engine_options.outline_groups_on(), engine_options.outline_groups_on(shared=True)),
                                 (True, False))
                os.environ['CU_V5_SPLIT'] = '1'
                self.assertEqual(engine_options.live_switches(), ON4)
                with mock.patch.object(engine_options, 'V5_SPLIT_PROVEN', True):
                    os.environ['CU_V5_SPLIT'] = '0'
                    self.assertEqual(engine_options.live_switches(), ON1)
                    os.environ.pop('CU_V5_SPLIT')
                    self.assertEqual(engine_options.live_switches(), ON4)
            os.environ.update(CU_V5_SPLIT='1', CU_CREATIVE_FIRST='0', CU_OUTLINE_GROUPS='0')
            self.assertEqual(engine_options.live_switches(), OFF4)
            with mock.patch.object(engine_options, 'V5_SPLIT_PROVEN', True):
                os.environ.pop('CU_V5_SPLIT')
                self.assertEqual(engine_options.live_switches(), OFF4)

    def test_the_workers_and_the_runner_ask_for_their_kind_of_engine(self):
        from service import workers
        self.assertIs(workers.Worker.shares_images, False)
        self.assertIs(workers.MultiCardWorker.shares_images, True)
        src = Path(workers.__file__).read_text(encoding='utf8')
        self.assertIn('engine_options.outline_groups_on(shared=self.shares_images)', src)
        self.assertEqual(src.count('outline_groups_on('), 1)
        run = Path(workers.__file__).with_name('runner.py').read_text(encoding='utf8')
        self.assertIn('shared=isinstance(w, MultiCardWorker)))', run)
        self.assertEqual(run.count('creative_first_on('), 1)


class ThroughTheService(V4Base):
    def stage_graph(self, jid):
        return json.loads(next((self.d / 'state/workers/gpu0/fake-prompts').glob(f'cu_{jid}_i001_s0.json')).read_text())

    def passes_run(self, jid):
        rows = [json.loads(x) for x in (self.d / 'state/workers/gpu0/fake-live.jsonl').read_text(encoding='utf8').splitlines()]
        return [(r['node'], r['pass']) for r in rows]

    def test_v5_on_the_detail_pass_first_groups_and_the_earlier_pass(self):
        self.svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '6'})
        code, h, _ = self.svc.get('/health')
        self.assertEqual((h['features']['creative_first'], h['features']['outline_groups']), (True, True))
        self.assertEqual((h['features']['creative_first_shared'], h['features']['outline_groups_shared']), (False, False))
        self.assertEqual({k: h['engine']['live'][k] for k in ('creative_first', 'outline_groups')},
                         {'creative_first': True, 'outline_groups': True})
        mids = self.inputs(1)
        jid = self.job(self.svc, mids, {'scale': 2})['id']
        first = wait(lambda: next((x for x in self.live()['items'] if x['job_id'] == jid and x['state'] == 'sampling'
                                   and x['rects'] and x['evaluation']), None))
        self.assertEqual((first['pass'], first['pass_index'], first['pass_order']), ('detail', 1, ['detail', 'structure']))
        self.assertTrue(all(e['groups'] == 5 and e['windows'] in (1, 2) for e in first['evaluation']), first['evaluation'])
        self.assertLessEqual(len(first['rects']), 2)
        self.assertIsNotNone(first['step_progress'])
        self.assertIsNone(first['earlier_pass'])
        second = wait(lambda: next((x for x in self.live()['items'] if x['job_id'] == jid and x['pass'] == 'structure'
                                    and x['earlier_pass']), None), timeout=60)
        self.assertEqual((second['pass_index'], second['earlier_pass']['pass']), (2, 'detail'))
        code, body, hdr = self.svc.get(second['earlier_pass']['url'], raw=True)
        self.assertEqual((code, hdr.get('Content-Type'), hdr.get('Cache-Control')), (200, 'image/jpeg', 'no-store'))
        self.assertEqual(list(Image.open(io.BytesIO(body)).size), second['earlier_pass']['size'])
        self.assertIsNotNone(second['timing']['first_tile_s'])
        j = self.svc.wait_job(jid, all_done, timeout=90)
        self.assertEqual(j['items'][0]['state'], 'done')
        self.assertEqual(self.passes_run(jid), [('15', 1), ('19', 2)])
        side = json.loads(Path(j['items'][0]['sidecar']).read_text(encoding='utf8'))
        st = side['timings']['stages'][0]
        self.assertEqual((st['run_order'], st['live_groups']), (['detail', 'structure'], True))
        self.assertEqual(self.svc.shutdown(), 0)

    def test_a_late_progress_feed_loses_nothing_of_the_first_pass(self):
        self.svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '6', 'CU_FAKE_WS_DELAY': '1.5'})
        jid = self.job(self.svc, self.inputs(1), {'scale': 2})['id']
        first = wait(lambda: next((x for x in self.live()['items'] if x['job_id'] == jid and x['state'] == 'sampling'
                                   and x['rects'] and x['evaluation']), None))
        self.assertEqual((first['pass'], first['pass_index'], first['pass_order']), ('detail', 1, ['detail', 'structure']))
        j = self.svc.wait_job(jid, all_done, timeout=90)
        self.assertEqual(j['items'][0]['state'], 'done')
        lines = self.svc.log_lines()
        ends = [ln['data'] for ln in lines if ln.get('event') == 'live_pass_end']
        self.assertEqual([(e['pass'], e['pass_index'], e['received'].get('init')) for e in ends],
                         [('detail', 1, 1), ('structure', 2, 1)])
        self.assertNotIn('worker_feed_late', [ln.get('event') for ln in lines])
        self.assertEqual(self.svc.shutdown(), 0)

    def test_v4_with_the_overrides_off_and_the_earlier_pass_is_the_structure_pass(self):

        self.svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '6', 'CU_CREATIVE_FIRST': '0', 'CU_OUTLINE_GROUPS': '0'})
        code, h, _ = self.svc.get('/health')
        self.assertEqual((h['features']['creative_first'], h['features']['outline_groups']), (False, False))
        mids = self.inputs(1)
        jid = self.job(self.svc, mids, {'scale': 2})['id']
        first = wait(lambda: next((x for x in self.live()['items'] if x['job_id'] == jid and x['state'] == 'sampling'
                                   and x['rects']), None))
        self.assertEqual((first['pass'], first['pass_index'], first['pass_order']), ('structure', 1, ['structure', 'detail']))
        self.assertEqual((first['evaluation'], first['step_progress']), (None, None))
        self.assertEqual(len(first['rects']), 1)
        second = wait(lambda: next((x for x in self.live()['items'] if x['job_id'] == jid and x['pass'] == 'detail'
                                    and x['earlier_pass']), None), timeout=60)
        self.assertEqual(second['earlier_pass']['pass'], 'structure')
        j = self.svc.wait_job(jid, all_done, timeout=90)
        self.assertEqual(self.passes_run(jid), [('19', 1), ('15', 2)])
        side = json.loads(Path(j['items'][0]['sidecar']).read_text(encoding='utf8'))
        self.assertEqual(side['timings']['stages'][0]['run_order'], ['structure', 'detail'])


        code, body, hdr = self.svc.get(f'/api/jobs/{jid}/items/i001/live-pass.jpg', raw=True)
        self.assertIn(code, (200, 404))
        if code == 200:
            self.assertEqual((hdr.get('Content-Type'), body[:2]), ('image/jpeg', b'\xff\xd8'))
        self.assertTrue(wait(lambda: self.svc.get(f'/api/jobs/{jid}/items/i001/live-pass.jpg', raw=True)[0] == 404 or None,
                             timeout=20))
        self.assertEqual(self.svc.shutdown(), 0)

    def test_the_proof_runs_reference_has_no_live_feed(self):
        self.svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '1', 'CU_LIVE_PREVIEW': 'off'})
        mids = self.inputs(1)
        jid = self.job(self.svc, mids, {'scale': 2})['id']
        j = self.svc.wait_job(jid, all_done, timeout=60)
        self.assertEqual(j['items'][0]['state'], 'done')
        spot = next(v for v in self.stage_graph(jid).values() if v['class_type'] == 'ClaudeSpotTiles')
        self.assertEqual(spot['inputs']['live_preview'], 'off')
        side = json.loads(Path(j['items'][0]['sidecar']).read_text(encoding='utf8'))
        self.assertEqual(side['engine']['spot_options']['live_preview'], 'off')
        self.assertEqual(self.svc.shutdown(), 0)


class SharedImages(V4Base):

    def worker_files(self, folder, jid):
        root = self.d / 'state' / 'workers' / folder
        graph = json.loads(next((root / 'fake-prompts').glob(f'cu_{jid}_*_s0.json')).read_text(encoding='utf8'))
        rows = [json.loads(x) for x in (root / 'fake-live.jsonl').read_text(encoding='utf8').splitlines()]
        return graph, rows

    def spot(self, graph):
        return next(v for v in graph.values() if v['class_type'] == 'ClaudeSpotTiles')['inputs']

    def stage(self, it):
        side = json.loads(Path(it['sidecar']).read_text(encoding='utf8'))
        return side['timings']['stages'][0]

    def ready_groups(self):
        return {tuple(ln['data']['gpus']): ln['data']['live_groups'] for ln in self.svc.log_lines()
                if ln.get('event') == 'worker_ready'}

    def shared_run(self, extra_env):
        self.svc = self.service(env=dict({'CU_FAKE_STAGE_SECONDS': '3', 'CU_FAKE_GPUS': '2', 'CU_CREATIVE_FIRST': '1',
                                          'CU_OUTLINE_GROUPS': '1'}, **extra_env), settings={})
        code, h, _ = self.svc.get('/health')
        mids = self.inputs(1)
        jid = self.job(self.svc, mids, {'scale': 2})['id']
        snaps = []

        def sampling():
            x = next((x for x in self.live()['items'] if x['job_id'] == jid and x['state'] == 'sampling' and x['rects']), None)
            if x is not None:
                snaps.append(x)
            return x
        first = wait(sampling)
        j = self.svc.wait_job(jid, all_done, timeout=90)
        it = j['items'][0]
        self.assertEqual((it['state'], it['run']['split']), ('done', True))
        self.assertIn('GPU 1 + GPU 2 started pic0.png', [ln['msg'] for ln in self.svc.log_lines()
                                                         if ln.get('event') == 'item_dispatched'])
        graph, rows = self.worker_files('gpu0+1', jid)
        return h, first, it, graph, rows

    def test_a_shared_image_keeps_v4s_order_and_outline_and_lanes_get_v5(self):
        h, first, it, graph, rows = self.shared_run({})
        self.assertEqual({k: h['features'][k] for k in engine_options.live_switches()},
                         {'creative_first': True, 'outline_groups': True,
                          'creative_first_shared': False, 'outline_groups_shared': False})
        self.assertEqual({k: h['engine']['live'][k] for k in ('creative_first_shared', 'outline_groups_shared')},
                         {'creative_first_shared': False, 'outline_groups_shared': False})
        self.assertEqual(self.spot(graph)['window_split'], True)
        self.assertEqual([(r['node'], r['pass']) for r in rows], [('19', 1), ('15', 2)])
        self.assertEqual((first['pass'], first['pass_order'], first['evaluation'], first['step_progress']),
                         ('structure', ['structure', 'detail'], None, None))
        st = self.stage(it)
        self.assertEqual((st['run_order'], st['live_groups'], st['spot_options']['window_split']),
                         (['structure', 'detail'], False, True))
        self.assertEqual(self.ready_groups(), {(0, 1): False})

        mids = self.inputs(2)
        j2 = self.svc.wait_job(self.job(self.svc, mids[-2:], {'scale': 2})['id'], all_done, timeout=90)
        self.assertEqual([(x['state'], x['run']['split']) for x in j2['items']], [('done', False), ('done', False)])
        for x in j2['items']:
            st = self.stage(x)
            self.assertEqual((st['run_order'], st['live_groups']), (['detail', 'structure'], True), x['id'])
        self.assertEqual(self.ready_groups(), {(0, 1): False, (0,): True, (1,): True})
        for folder in ('gpu0', 'gpu1'):
            graph, rows = self.worker_files(folder, j2['id'])
            self.assertFalse(self.spot(graph).get('window_split', False))
            self.assertEqual([(r['node'], r['pass']) for r in rows], [('15', 1), ('19', 2)])
        self.assertEqual(self.svc.shutdown(), 0)

    def test_with_its_proof_a_shared_image_gets_both(self):
        h, first, it, graph, rows = self.shared_run({'CU_V5_SPLIT': '1'})
        self.assertEqual({k: h['features'][k] for k in engine_options.live_switches()},
                         {'creative_first': True, 'outline_groups': True,
                          'creative_first_shared': True, 'outline_groups_shared': True})
        self.assertEqual(self.spot(graph)['window_split'], True)
        self.assertEqual([(r['node'], r['pass']) for r in rows], [('15', 1), ('19', 2)])
        self.assertEqual((first['pass'], first['pass_order']), ('detail', ['detail', 'structure']))
        st = self.stage(it)
        self.assertEqual((st['run_order'], st['live_groups']), (['detail', 'structure'], True))
        self.assertEqual(self.ready_groups(), {(0, 1): True})
        self.assertEqual(self.svc.shutdown(), 0)

    def test_a_late_feed_on_two_cards_loses_nothing_of_the_first_pass(self):
        h, first, it, graph, rows = self.shared_run({'CU_V5_SPLIT': '1', 'CU_FAKE_WS_DELAY': '1.5'})
        self.assertEqual((first['pass'], first['pass_index'], first['pass_order']), ('detail', 1, ['detail', 'structure']))
        self.assertEqual(first['cards'], [0, 1])
        self.assertEqual(self.svc.shutdown(), 0)

    def test_the_split_switch_alone_turns_nothing_on(self):
        self.svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '1', 'CU_FAKE_GPUS': '2', 'CU_V5_SPLIT': '1',
                                     'CU_CREATIVE_FIRST': '0', 'CU_OUTLINE_GROUPS': '0'}, settings={})
        j = self.svc.wait_job(self.job(self.svc, self.inputs(1), {'scale': 2})['id'], all_done, timeout=60)
        it = j['items'][0]
        self.assertEqual((it['state'], it['run']['split']), ('done', True))
        st = self.stage(it)
        self.assertEqual((st['run_order'], st['live_groups']), (['structure', 'detail'], False))
        self.assertEqual(self.ready_groups(), {(0, 1): False})
        self.assertEqual(self.svc.shutdown(), 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
