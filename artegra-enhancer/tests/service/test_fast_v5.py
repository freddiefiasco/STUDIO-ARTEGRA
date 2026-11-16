import hashlib
import json
import os
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from engine import controls, fast_recipe, graph_v5t, planner
from service import engine_options, runner
from service.errors import ApiError
from tests.service.helpers import tmpdir, rmtree
from tests.service.test_integration import all_done
from tests.service.test_port import Log, PortBase, spot_inputs
from tests.service.test_v4 import wait

RID = 'H8-e8-s25-c5-p3-k+so16+stk'

LOOK = 'Bolt offers Light and Default only. Choose Redux for Strong, Heavy, Extreme or Custom.'
SCALE = 'Bolt upscales 2× only. Choose Redux for 4× and above.'
CHECKING = 'Bolt is not ready yet: its files are still being checked. Try again in a moment.'


OFFERED = {'available': True, 'reason': None, 'message': None, 'recipe': RID, 'version': '1', 'factor': 0.37,
           'factors': {'first_stage': 0.37}, 'split': True, 'looks': ['Light', 'Default'], 'max_factor': 2}
OFFERED_ONE_CARD = dict(OFFERED, split=False)
PENDING = {'available': False, 'reason': 'pending_proof', 'message': 'Bolt is not in this version.', 'recipe': RID,
           'version': '1', 'factor': None, 'factors': None, 'split': False, 'looks': ['Light', 'Default'], 'max_factor': 2}
NO_OVERRIDES = dict({k: '' for k in ('CU_FAST', 'CU_FAST_SPLIT', 'CU_FASTER', 'CU_FASTER_SPLIT', 'CU_FAST_TEST')},
                    CU_FAKE_GPU_NAME='NVIDIA GeForce RTX 5090')


def err(e):
    return e.get('error', e)


class FastBase(PortBase):
    def start(self, **env):
        self.svc = self.service(env=dict(NO_OVERRIDES, **dict({'CU_FAKE_STAGE_SECONDS': '1'}, **env)))
        return self.svc

    def stage_graph(self, job, iid, fast=False, k=0, faster=False, creative_first=True):
        it = next(x for x in job['items'] if x['id'] == iid)
        st = it['plan']['stages'][k]
        pre = f'cu_{job["id"]}_{iid}_s{k}'
        params = controls.stage_params(controls.resolve(it.get('settings') or job['settings'])[0], k)
        kw = dict(f=runner._frac(st['factor']), s=runner._frac(st['supersample']))
        if fast:
            g, _ = fast_recipe.build(pre + '.png', *st['padded_size'], params, pre, live_preview='detailed', **kw)
        else:
            g, _ = graph_v5t.build_product(pre + '.png', *st['padded_size'], params, pre, speed_stack=True,
                                           live_preview='detailed', creative_first=creative_first, faster=faster, **kw)
        return json.loads(json.dumps(g))


class AsBuilt(FastBase):
    def test_the_build_offers_fast_since_its_new_proof(self):

        self.assertEqual((engine_options.FAST_PROVEN, engine_options.FASTER_PROVEN), (True, False))


        self.assertEqual((engine_options.FAST_SPLIT_PROVEN, engine_options.FASTER_SPLIT_PROVEN,
                          engine_options.V5_SPLIT_PROVEN), (True, False, False))
        self.start()
        h = self.health()
        self.assertEqual(h['engine']['fast'], OFFERED_ONE_CARD)
        self.assertEqual((h['features']['fast'], h['features']['faster']), (True, False))
        self.assertEqual(h['engine']['faster']['reason'], 'pending_proof')
        code, p, _ = self.svc.post('/api/plan', {'width': 1024, 'height': 768, 'scale': 2})
        self.assertEqual((p['finish']['fast']['factor'], p['finish']['fast_refusal']), (0.37, None))
        self.assertEqual(self.svc.shutdown(), 0)

    def test_fast_and_faster_are_installed_but_not_offered(self):

        self.start(CU_FAST='0')
        h = self.health()
        self.assertEqual(h['engine']['fast'], PENDING)
        self.assertEqual((h['features']['fast'], h['features']['faster']), (False, False))
        self.assertEqual(h['engine']['faster'], {'available': False, 'on': False, 'factor': 0.87, 'split': False,
                                                 'reason': 'pending_proof',
                                                 'message': 'Speed up upscaling is not in this version.'})
        sp = h['engine']['speed']
        self.assertEqual((sp['faster_available'], sp['faster'], sp['factors']['fast'], sp['factors']['faster']),
                         (False, False, None, None))
        code, s, _ = self.svc.get('/api/settings')
        self.assertNotIn('faster', s)
        code, e, _ = self.svc.post('/api/settings', {'faster': True})
        self.assertEqual((code, err(e)['code'], err(e)['message']),
                         (400, 'bad_settings', 'These settings cannot be changed here: faster'))
        code, e, _ = self.svc.post('/api/settings', {'mode': 'fast'})
        self.assertEqual((code, err(e)['code']), (400, 'bad_settings'))
        mids = self.inputs(1)
        code, e, _ = self.svc.post('/api/jobs', {'client_request_id': '2' * 32, 'media_ids': mids, 'settings': {'mode': 'fast'}})
        self.assertEqual((code, err(e)['code'], err(e)['message']),
                         (400, 'fast_unavailable', 'Bolt is not available. Choose Redux.'))
        self.assertEqual(err(e)['data'], {'reason': 'pending_proof'})
        code, p, _ = self.svc.post('/api/plan', {'width': 1024, 'height': 768, 'scale': 2})
        self.assertEqual(p['finish'], {'match_earlier': False, 'standard': p['finish']['standard'], 'fast': None,
                                       'fast_refusal': {'reason': 'pending_proof',
                                                        'message': 'Bolt is not available. Choose Redux.'},
                                       'single': {'standard': dict(p['finish']['standard'], cards=1), 'fast': None}})
        self.assertEqual(self.svc.shutdown(), 0)

    def test_a_stored_faster_choice_does_nothing_while_not_offered(self):
        (self.d / 'state').mkdir(parents=True, exist_ok=True)
        (self.d / 'state' / 'settings-extra.json').write_text(json.dumps({'faster': True}), encoding='utf8')
        self.start()
        code, s, _ = self.svc.get('/api/settings')
        self.assertNotIn('faster', s)
        self.assertEqual(self.health()['engine']['faster']['on'], False)
        code, s, _ = self.svc.post('/api/settings', {'match_earlier': True})
        self.assertEqual((code, s.get('match_earlier')), (200, True))
        self.assertEqual(self.svc.post('/api/settings', {'match_earlier': False})[0], 200)
        mids = self.inputs(1)
        j = self.svc.wait_job(self.job(self.svc, mids, {'scale': 2})['id'], all_done, timeout=120)
        self.assertEqual(j['items'][0]['run']['faster'], False)
        self.assertNotIn('cfg_end', spot_inputs(self.sent(j['id'], 'i001')))
        self.assertEqual(self.svc.shutdown(), 0)


class FastOffered(FastBase):
    def test_health_plans_and_refusals(self):
        self.start(CU_FAST='1')
        h = self.health()
        self.assertEqual(h['engine']['fast'], OFFERED_ONE_CARD)
        self.assertTrue(h['features']['fast'])
        self.assertEqual(h['engine']['speed']['factors']['fast'], 0.37)
        m2, m4 = planner.plan(2048, 2048, 2).minutes, planner.plan(2048, 2048, 4).minutes
        code, p, _ = self.svc.post('/api/plan', {'width': 2048, 'height': 2048, 'scale': 2, 'mode': 'fast'})
        self.assertEqual((code, p['finish']['fast']), (200, {'minutes': round(m2 * 0.37, 1), 'factor': 0.37}))
        code, p, _ = self.svc.post('/api/plan', {'width': 2048, 'height': 2048, 'scale': 4})
        self.assertEqual((code, p['finish']['fast']), (200, None))
        self.assertEqual(p['finish']['standard'], {'minutes': round(m4 * 0.7, 1), 'factor': 0.7})
        code, e, _ = self.svc.post('/api/plan', {'width': 2048, 'height': 2048, 'scale': 4, 'mode': 'fast'})
        self.assertEqual((code, err(e)['code'], err(e)['message']), (400, 'fast_unavailable', SCALE))
        mids = self.inputs(2)
        code, inp, _ = self.svc.get('/api/inputs')
        sc = next(x for x in inp['items'] if x['id'] == mids[0])['scales']
        self.assertIsNotNone(sc['2']['finish']['fast'])
        self.assertIsNone(sc['4']['finish']['fast'])
        for i, (settings, msg) in enumerate(((dict(preset='Strong'), LOOK), (dict(preset='Extreme'), LOOK),
                                             (dict(preset='Default', custom=True, creativity=70), LOOK),
                                             (dict(scale=4), SCALE), (dict(scale=8, preset='Heavy'), SCALE))):
            code, e, _ = self.svc.post('/api/jobs', {'client_request_id': f'{i + 3:032x}', 'media_ids': mids,
                                                     'settings': dict(settings, mode='fast')})
            self.assertEqual((code, err(e)['code'], err(e)['message']), (400, 'fast_unavailable', msg), settings)
            self.assertEqual(err(e)['data']['reason'], 'look' if msg == LOOK else 'scale')

        job = self.job(self.svc, mids, {'scale': 2, 'preset': 'Strong'})
        jid = job['id']
        code, res, _ = self.svc.post('/api/items/settings', {'items': [{'job_id': jid, 'item_id': 'i002'}],
                                                              'settings': {'scale': 2, 'preset': 'Strong', 'mode': 'fast'}})
        self.assertEqual([(r['item_id'], r['code'], r['reason']) for r in res['refused']], [('i002', 'fast_unavailable', LOOK)])
        code, res, _ = self.svc.post('/api/items/settings', {'items': [{'job_id': jid, 'item_id': 'i002'}],
                                                              'settings': {'scale': 2, 'preset': 'Light', 'mode': 'fast'}})
        self.assertEqual([a['item_id'] for a in res['applied']], ['i002'], res)
        j = self.svc.wait_job(jid, all_done, timeout=120)
        self.assertEqual([x['state'] for x in j['items']], ['done', 'done'])
        self.assertEqual((j['items'][1]['run']['mode'], j['items'][1]['run']['factor']), ('fast', 0.37))
        self.assertTrue(Path(j['items'][1]['output']).name.endswith('_cu2x_bolt.png'))
        self.assertEqual(self.svc.shutdown(), 0)

    def test_a_fast_image_beside_a_standard_one(self):
        self.start(CU_FAST='1')
        mids = self.inputs(2)
        job = self.job(self.svc, mids, {'scale': 2})
        jid = job['id']
        code, res, _ = self.svc.post('/api/items/settings', {'items': [{'job_id': jid, 'item_id': 'i002'}],
                                                              'settings': {'scale': 2, 'mode': 'fast'}})
        self.assertEqual([a['item_id'] for a in res['applied']], ['i002'], res)
        j = self.svc.wait_job(jid, all_done, timeout=120)
        self.assertEqual([x['state'] for x in j['items']], ['done', 'done'], json.dumps(j)[:1500])

        self.assertEqual(self.sent(jid, 'i002'), self.stage_graph(j, 'i002', fast=True))
        self.assertEqual(self.sent(jid, 'i001'), self.stage_graph(j, 'i001'))
        fast = self.sent(jid, 'i002')
        self.assertEqual(spot_inputs(fast)['seam_overlap'], 16)
        self.assertEqual({v['inputs']['steps'] for v in fast.values() if v['class_type'] == 'KSampler'}, {8})
        self.assertEqual([v['inputs']['lora_name'] for v in fast.values() if v['class_type'] == 'LoraLoaderModelOnly'],
                         ['Hyper-SDXL-8steps-CFG-lora.safetensors'])
        self.assertNotIn('seam_overlap', spot_inputs(self.sent(jid, 'i001')))

        std, fst = j['items']
        self.assertEqual((Path(std['output']).name, Path(fst['output']).name), ('pic0_cu2x.png', 'pic1_cu2x_bolt.png'))
        self.assertEqual(Path(fst['sidecar']).name, 'pic1_cu2x_bolt.json')

        self.assertEqual((fst['run']['mode'], fst['run']['factor'], fst['run']['faster'], fst['run']['split']),
                         ('fast', 0.37, False, False))
        side = self.side(fst)
        self.assertEqual((side['engine']['graph'], side['effective']['mode'], side['run']['mode']),
                         ('engine/fast_recipe.py', 'fast', 'fast'))
        self.assertEqual(side['engine']['fast'], {
            'recipe': RID, 'version': '1',
            'lora': {'file': 'Hyper-SDXL-8steps-CFG-lora.safetensors', 'bytes': 787359648,
                     'sha256': '55b51334c85061afff5eff7c550b61963c8b8607a5868bbe4f26db49374719b1', 'strength': 0.25},
            'steps': 8, 'cfg': 5.0, 'pag': 3.0, 'seam_overlap': 16,
            'schedule': "pick A's own: KSampler, 8 executed steps of int(8 / denoise)",
            'ends': {'detail': 0.7936, 'structure': 0.9737}})
        self.assertEqual(side['output']['name'], 'pic1_cu2x_bolt.png')
        self.assertIsNone(self.side(std)['engine']['fast'])
        self.assertEqual(side['timings']['stages'][0]['run_order'], ['structure', 'detail'])
        self.assertEqual(self.side(std)['timings']['stages'][0]['run_order'],
                         ['detail', 'structure'] if engine_options.creative_first_on() else ['structure', 'detail'])
        lines = self.started_lines(jid)
        self.assertEqual((lines['i001'], lines['i002']), ('Started pic0.png (1 pass)', 'Started pic1.png (1 pass), Bolt'))

        again = self.job(self.svc, [mids[1]], {'scale': 2, 'mode': 'standard'})
        draft = self.job(self.svc, [mids[1]], {'scale': 2, 'mode': 'fast'})
        a = self.svc.wait_job(again['id'], all_done, timeout=120)
        d = self.svc.wait_job(draft['id'], all_done, timeout=120)
        self.assertEqual(Path(a['items'][0]['output']).name, 'pic1_cu2x.png')
        self.assertEqual(Path(d['items'][0]['output']).name, 'pic1_cu2x_bolt_2.png')
        self.assertTrue(Path(fst['output']).is_file())
        self.assertEqual(self.svc.shutdown(), 0)


class FastTwoCards(FastBase):
    def run_one(self, **env):
        self.svc = self.service(env=dict(NO_OVERRIDES, CU_FAKE_STAGE_SECONDS='1', CU_FAKE_GPUS='2', **env),
                                settings={}, state='state-' + '-'.join(sorted(env)).lower())
        mids = self.inputs(1)
        job = self.job(self.svc, mids, {'scale': 2, 'mode': 'fast'})
        j = self.svc.wait_job(job['id'], all_done, timeout=120)
        self.assertEqual(j['items'][0]['state'], 'done', json.dumps(j)[:1500])
        return j['items'][0]

    def test_one_card_until_its_two_card_proof(self):


        it = self.run_one(CU_FAST='1', CU_FAST_SPLIT='0')
        self.assertEqual((it['run']['split'], it['run']['cards'], it['run']['factor']), (False, [0], 0.37))
        self.assertEqual(self.health()['engine']['fast'], OFFERED_ONE_CARD)
        self.assertEqual(self.svc.shutdown(), 0)

    def test_the_build_shares_one_fast_image(self):
        it = self.run_one(CU_FAST='1')
        self.assertEqual((it['run']['split'], it['run']['cards'], it['run']['factor']), (True, [0, 1], 0.308))
        self.assertEqual(self.svc.shutdown(), 0)

    def test_the_multi_card_worker_carries_fast_once_proven(self):

        it = self.run_one(CU_FAST='1', CU_FAST_SPLIT='1')
        self.assertEqual((it['run']['split'], it['run']['cards'], it['run']['factor']), (True, [0, 1], 0.308))
        side = self.side(it)
        self.assertEqual(side['engine']['spot_options'].get('window_split'), True)
        self.assertEqual(side['engine']['spot_options'].get('seam_overlap'), 16)
        self.assertEqual(side['timings']['stages'][0]['run_order'], ['structure', 'detail'])
        self.assertEqual(self.svc.shutdown(), 0)


class FastFiles(unittest.TestCase):

    def setUp(self):
        self.d = tmpdir('cu-fastfiles-')
        self.saved = fast_recipe.RECIPE
        body = b'not a real lora' * 1000
        self.lora = {'file': 'tiny.safetensors', 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest(), 'strength': 0.25}
        self.body = body
        fast_recipe.RECIPE = dict(self.saved, lora=self.lora, models={'loras': ['tiny.safetensors']})
        self.r = runner.Runner.__new__(runner.Runner)
        self.r.mode, self.r._fast_files_ok, self.r._fast_hashes, self.r._fast_test = 'comfy', None, {}, False
        self.r.log = Log()
        self.r.cfg = mock.Mock(models_dir=self.d / 'models', claude_models_dir=self.d / 'claude')

    def tearDown(self):
        fast_recipe.RECIPE = self.saved
        rmtree(self.d)

    def put(self, base, body):
        p = self.d / base / 'loras' / 'tiny.safetensors'
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body)
        return p

    def test_name_size_and_hash_of_the_file_the_engine_would_find(self):
        with mock.patch.dict(os.environ, {'CU_FAST': '1'}):
            self.assertFalse(self.r._fast_files_check())
            self.assertEqual(self.r.log.rows[-1][3]['data']['missing'], ['loras/tiny.safetensors'])
            self.put('claude', self.body[:-1])
            self.assertFalse(self.r._fast_files_check())
            p = self.put('claude', self.body[:-1] + b'X')
            self.assertFalse(self.r._fast_files_check())
            p.write_bytes(self.body)
            os.utime(p, ns=(p.stat().st_atime_ns, p.stat().st_mtime_ns + 10 ** 9))
            with mock.patch.object(runner, 'sha256_file', wraps=runner.sha256_file) as sh:
                self.assertTrue(self.r._fast_files_check())
                self.r._fast_files_ok = True
                self.assertTrue(self.r._fast_files_check())
                self.assertEqual(sh.call_count, 1)
            self.put('models', self.body[:-1] + b'Y')
            self.r._fast_files_ok = True
            self.assertFalse(self.r._fast_files_check())
            self.r._fast_files_ok = False
            self.assertEqual(self.r.fast_info()['reason'], 'files_missing')
            with self.assertRaises(ApiError) as cm:
                self.r._check_mode({'mode': 'fast', 'scale': 2, 'preset': 'Default'})
            self.assertEqual((cm.exception.code, cm.exception.message, cm.exception.data),
                             ('fast_unavailable', 'Bolt cannot be used: a file it needs cannot be read. Choose Redux.',
                              {'reason': 'files_missing'}))
        with mock.patch.dict(os.environ, {'CU_FAST': '0'}):
            self.assertTrue(self.r._fast_files_check())


    def test_not_offered_before_the_first_check(self):
        import threading
        import time
        self.r._snap_ready = threading.Event()
        fast = {'mode': 'fast', 'scale': 2, 'preset': 'Default'}
        with mock.patch.dict(os.environ, {'CU_FAST': '1'}), mock.patch.object(runner, 'FAST_CHECK_WAIT_S', 0.2):
            f = self.r.fast_info()
            self.assertEqual((f['available'], f['reason'], f['message'], f['factor']),
                             (False, 'checking', 'Checking the files Bolt needs.', None))
            t0 = time.monotonic()
            with self.assertRaises(ApiError) as cm:
                self.r._check_mode(fast)
            self.assertGreaterEqual(time.monotonic() - t0, 0.15)
            self.assertEqual((cm.exception.code, cm.exception.message, cm.exception.data),
                             ('fast_unavailable', CHECKING, {'reason': 'checking'}))
            t0 = time.monotonic()
            self.r._check_mode({'mode': 'standard', 'scale': 4, 'preset': 'Heavy'})
            self.assertLess(time.monotonic() - t0, 0.1)

            def probe(ok):
                time.sleep(0.05)
                self.r._fast_files_ok = ok
                self.r._snap_ready.set()
            with mock.patch.object(runner, 'FAST_CHECK_WAIT_S', 5.0):
                th = threading.Thread(target=probe, args=(True,))
                th.start()
                self.r._check_mode(fast)
                th.join()
                self.assertTrue(self.r.fast_info()['available'])
                self.r._fast_files_ok, self.r._snap_ready = None, threading.Event()
                th = threading.Thread(target=probe, args=(False,))
                th.start()
                with self.assertRaises(ApiError) as cm:
                    self.r._check_mode(fast)
                th.join()
                self.assertEqual(cm.exception.data, {'reason': 'files_missing'})
        self.r._fast_files_ok = None
        with mock.patch.dict(os.environ, {'CU_FAST': '0'}):
            self.assertEqual(self.r.fast_info()['reason'], 'pending_proof')
        self.r.mode = 'fake'
        with mock.patch.dict(os.environ, {'CU_FAST': '1'}):
            self.assertTrue(self.r.fast_info()['available'])

    def test_a_fast_image_about_to_start_has_the_files_read_first(self):
        calls = []

        def refresh(ok):
            def go():
                calls.append(ok)
                self.r._fast_files_ok = ok
            return go
        with mock.patch.dict(os.environ, {'CU_FAST': '1'}):
            self.r._refresh_health = refresh(True)
            self.assertTrue(self.r._fast_info_to_start()['available'])
            self.assertEqual(calls, [True])
            self.assertTrue(self.r._fast_info_to_start()['available'])
            self.assertEqual(calls, [True])
            self.r._fast_files_ok, self.r._refresh_health = None, refresh(False)
            self.assertEqual(self.r._fast_info_to_start()['reason'], 'files_missing')
            self.assertEqual(calls, [True, False])
            self.r._fast_files_ok = None
            self.r._refresh_health = lambda: calls.append('no answer')
            self.assertEqual(self.r._fast_info_to_start()['reason'], 'checking')
        with mock.patch.dict(os.environ, {'CU_FAST': '0'}):
            self.assertEqual(self.r._fast_info_to_start()['reason'], 'pending_proof')
        self.assertEqual(calls, [True, False, 'no answer'])

    def test_a_start_never_meets_checking(self):
        import inspect
        self.assertEqual(inspect.getsource(runner.Runner._refresh_health).count(
            'self._fast_files_ok = self._fast_files_check()'), 1)
        run = inspect.getsource(runner.Runner._run_item)
        self.assertIn("run.get('mode') == 'fast' and not self._fast_info_to_start()['available']", run)
        self.assertLess(run.index('self._fast_info_to_start()'), run.index('self._run_stage('))
        self.r._refresh_health = lambda: setattr(self.r, '_fast_files_ok', self.r._fast_files_check())
        with mock.patch.dict(os.environ, {'CU_FAST': '1'}):
            for state, body in (('missing', None), ('wrong hash', self.body[:-1] + b'X'), ('right', self.body)):
                if body is not None:
                    p = self.put('claude', body)
                    os.utime(p, ns=(p.stat().st_atime_ns, p.stat().st_mtime_ns + 10 ** 9 * len(state)))
                self.r._fast_files_ok = None
                f = self.r._fast_info_to_start()
                self.assertEqual((f['available'], f['reason']), (True, None) if state == 'right' else
                                 (False, 'files_missing'), state)


class FasterOffered(FastBase):
    def test_the_setting_and_its_exclusion(self):
        self.start(CU_FASTER='1')
        code, s, _ = self.svc.get('/api/settings')
        self.assertIs(s['faster'], False)
        h = self.health()
        self.assertEqual(h['engine']['faster'], {'available': True, 'on': False, 'factor': 0.87, 'split': False, 'reason': None,
                                                 'message': None})
        self.assertEqual((h['features']['faster'], h['engine']['speed']['faster_available']), (True, True))
        code, s, _ = self.svc.post('/api/settings', {'faster': True})
        self.assertEqual((code, s['faster']), (200, True))
        self.assertEqual(self.health()['engine']['faster']['on'], True)
        code, e, _ = self.svc.post('/api/settings', {'match_earlier': True})
        self.assertEqual((code, err(e)['code'], err(e)['message']),
                         (409, 'faster_with_match', 'Match earlier results cannot be on while Speed up upscaling is on.'))
        code, e, _ = self.svc.post('/api/settings', {'faster': 'yes'})
        self.assertEqual((code, err(e)['code'], err(e)['message']), (400, 'bad_settings', 'faster must be true or false.'))
        self.assertEqual(self.svc.post('/api/settings', {'faster': False, 'match_earlier': True})[0], 200)
        code, e, _ = self.svc.post('/api/settings', {'faster': True})
        self.assertEqual((code, err(e)['code'], err(e)['message']),
                         (409, 'faster_with_match', 'Speed up upscaling cannot be on while Match earlier results is on.'))
        code, p, _ = self.svc.post('/api/plan', {'width': 2048, 'height': 2048, 'scale': 2})
        self.assertIsNone(p['finish']['faster'])
        self.assertEqual(self.svc.post('/api/settings', {'match_earlier': False})[0], 200)
        m2, p4 = planner.plan(2048, 2048, 2).minutes, planner.plan(2048, 2048, 4)
        code, p, _ = self.svc.post('/api/plan', {'width': 2048, 'height': 2048, 'scale': 2})
        self.assertEqual(p['finish']['faster'], {'minutes': round(m2 * 0.609, 1), 'factor': 0.609, 'stages': [0]})
        code, p, _ = self.svc.post('/api/plan', {'width': 2048, 'height': 2048, 'scale': 4})
        f4 = engine_options.faster_factor(p4)
        self.assertEqual(p['finish']['faster'], {'minutes': round(p4.minutes * f4, 1), 'factor': f4, 'stages': [0]})
        self.assertLess(0.609, f4)
        self.assertLess(f4, 0.70)
        self.assertEqual(self.svc.shutdown(), 0)

    def test_faster_images_and_what_they_say(self):
        self.start(CU_FASTER='1', CU_FAST='1')
        self.assertEqual(self.svc.post('/api/settings', {'faster': True})[0], 200)
        mids = self.inputs(3)
        job = self.job(self.svc, mids[:2], {'scale': 2})
        job4 = self.job(self.svc, [mids[2]], {'scale': 4})
        jid, j4 = job['id'], job4['id']
        code, res, _ = self.svc.post('/api/items/settings', {'items': [{'job_id': jid, 'item_id': 'i002'}],
                                                              'settings': {'scale': 2, 'mode': 'fast'}})
        self.assertEqual([a['item_id'] for a in res['applied']], ['i002'], res)
        j = self.svc.wait_job(jid, all_done, timeout=120)
        k = self.svc.wait_job(j4, all_done, timeout=180)
        std, fst = j['items']
        self.assertEqual(self.sent(jid, 'i001'), self.stage_graph(j, 'i001', faster=True))
        self.assertEqual((spot_inputs(self.sent(jid, 'i001'))['cfg_end'], spot_inputs(self.sent(jid, 'i001'))['pag_end']),
                         (0.7, 0.6))
        self.assertEqual(self.sent(jid, 'i002'), self.stage_graph(j, 'i002', fast=True))
        self.assertNotIn('cfg_end', spot_inputs(self.sent(jid, 'i002')))
        self.assertEqual((std['run']['faster'], std['run']['factor'], std['run']['stage_factors']), (True, 0.609, [0.609]))
        self.assertEqual((fst['run']['faster'], fst['run']['factor']), (False, 0.37))
        self.assertEqual(self.side(std)['engine']['faster'], {'cfg_end': 0.7, 'pag_end': 0.6, 'stages': [0]})
        self.assertIsNone(self.side(fst)['engine']['faster'])
        self.assertEqual(self.started_lines(jid)['i001'], 'Started pic0.png (1 pass), sped up')
        self.assertEqual(Path(std['output']).name, 'pic0_cu2x.png')

        it4 = k['items'][0]
        self.assertEqual(self.sent(j4, 'i001', k=0), self.stage_graph(k, 'i001', faster=True, k=0))
        self.assertEqual(self.sent(j4, 'i001', k=1), self.stage_graph(k, 'i001', faster=False, k=1))
        self.assertNotIn('cfg_end', spot_inputs(self.sent(j4, 'i001', k=1)))
        self.assertEqual(it4['run']['stage_factors'], [0.609, 0.7])
        self.assertEqual(it4['run']['factor'], engine_options.faster_factor(it4['plan']))
        self.assertEqual(self.side(it4)['engine']['faster']['stages'], [0])
        self.assertEqual(self.svc.shutdown(), 0)

    def test_a_shared_image_runs_as_standard_until_its_two_card_proof(self):
        for env, faster in (({}, False), ({'CU_FASTER_SPLIT': '1'}, True)):
            with self.subTest(env=env):
                self.svc = self.service(env=dict(NO_OVERRIDES, CU_FAKE_STAGE_SECONDS='1', CU_FAKE_GPUS='2', CU_FASTER='1', **env),
                                        settings={}, state='state-sh' + str(int(faster)))
                self.assertEqual(self.svc.post('/api/settings', {'faster': True})[0], 200)
                mids = self.inputs(1)
                job = self.job(self.svc, mids, {'scale': 2})
                j = self.svc.wait_job(job['id'], all_done, timeout=120)
                it = j['items'][0]
                self.assertEqual((it['run']['split'], it['run']['faster']), (True, faster), json.dumps(it['run']))
                side = self.side(it)
                self.assertEqual('cfg_end' in side['engine']['spot_options'], faster)
                if not faster:
                    self.assertEqual(it['run']['factor'], engine_options.eta_factor(cards=2))
                    self.assertTrue(any(ln.get('event') == 'faster_not_shared' for ln in self.svc.log_lines()))
                self.assertEqual(self.svc.shutdown(), 0)


class TooLarge(FastBase):
    SIZE = 'Bolt works on images up to about 9 MP. Choose Redux for larger images.'

    def big_input(self, name='big.png', size=(3072, 3072)):
        d = self.d / 'big'
        d.mkdir(parents=True, exist_ok=True)
        p = d / name
        Image.new('RGB', size, (120, 110, 100)).save(p)
        self.assertEqual(planner.plan(*size, 2).stages[0].supersample, 1.5)
        return self.add(self.svc, [p])['items'][0]['id']

    def prompt(self, jid, iid='i001', timeout=60):
        f = self.d / 'state' / 'workers' / 'gpu0' / 'fake-prompts' / f'cu_{jid}_{iid}_s0.json'
        wait(lambda: f.is_file() or None, timeout=timeout)
        return json.loads(f.read_text(encoding='utf8'))

    def test_an_image_too_large_for_fast_is_refused_in_plain_words(self):
        self.start(CU_FAST='1', CU_FAKE_STAGE_SECONDS='60')
        self.assertEqual(engine_options.FAST_REFUSALS['size'], self.SIZE)
        code, e, _ = self.svc.post('/api/plan', {'width': 4032, 'height': 3024, 'scale': 2, 'mode': 'fast'})
        self.assertEqual((code, err(e)['code'], err(e)['message'], err(e)['data']),
                         (400, 'fast_unavailable', self.SIZE, {'reason': 'size'}))
        code, p, _ = self.svc.post('/api/plan', {'width': 4032, 'height': 3024, 'scale': 2})
        self.assertEqual((code, p['finish']['fast'], p['finish']['fast_refusal'], p['finish']['single']['fast']),
                         (200, None, {'reason': 'size', 'message': self.SIZE}, None))
        code, p, _ = self.svc.post('/api/plan', {'width': 3840, 'height': 2400, 'scale': 2, 'mode': 'fast'})
        self.assertEqual((code, p['finish']['fast']['factor'], p['finish']['fast_refusal']), (200, 0.37, None))
        small = self.inputs(1)
        big = self.big_input()
        code, inp, _ = self.svc.get('/api/inputs')
        sc = next(x for x in inp['items'] if x['id'] == big)['scales']
        self.assertEqual((sc['2']['finish']['fast'], sc['2']['finish']['fast_refusal']['reason']), (None, 'size'))
        code, e, _ = self.svc.post('/api/jobs', {'client_request_id': 'b' * 32, 'media_ids': small + [big],
                                                 'settings': {'mode': 'fast', 'scale': 2}})
        self.assertEqual((code, err(e)['code'], err(e)['message'], err(e)['data']),
                         (400, 'fast_unavailable', self.SIZE, {'reason': 'size', 'refused': ['big.png']}))

        jid = self.job(self.svc, small + [big], {'scale': 2})['id']
        code, res, _ = self.svc.post('/api/items/settings', {'items': [{'job_id': jid, 'item_id': 'i002'}],
                                                              'settings': {'scale': 2, 'mode': 'fast'}})
        self.assertEqual([(r['item_id'], r['code'], r['reason']) for r in res['refused']],
                         [('i002', 'fast_unavailable', self.SIZE)])
        self.assertEqual(self.svc.post(f'/api/jobs/{jid}/cancel')[0], 200)
        self.svc.wait_job(jid, lambda j: all(x['state'] == 'cancelled' for x in j['items']), timeout=60)

        code, e, _ = self.svc.post(f'/api/jobs/{jid}/items/i002/requeue', {'settings': {'scale': 2, 'mode': 'fast'}})
        self.assertEqual((code, err(e)['code'], err(e)['data']), (400, 'fast_unavailable', {'reason': 'size'}))
        self.assertEqual(self.svc.shutdown(), 0)

    def test_faster_runs_the_stack_on_a_stage_below_supersample_2(self):
        self.start(CU_FASTER='1', CU_FAKE_STAGE_SECONDS='60')
        self.assertEqual(self.svc.post('/api/settings', {'faster': True})[0], 200)
        m = planner.plan(3072, 3072, 2).minutes
        code, p, _ = self.svc.post('/api/plan', {'width': 3072, 'height': 3072, 'scale': 2})
        self.assertEqual(p['finish']['faster'], {'minutes': round(m * 0.7, 1), 'factor': 0.7, 'stages': []})
        big = self.big_input()
        job = self.job(self.svc, [big], {'scale': 2})
        jid = job['id']
        self.assertEqual((job['items'][0]['run']['faster'], job['items'][0]['run']['factor']), (False, 0.7))
        g = self.prompt(jid)
        j = self.svc.get(f'/api/jobs/{jid}')[1]
        self.assertNotIn('cfg_end', spot_inputs(g))
        self.assertNotIn('pag_end', spot_inputs(g))
        self.assertEqual(g, self.stage_graph(j, 'i001'))
        run = j['items'][0]['run']
        self.assertEqual((run['frozen'], run['faster'], run['factor']), (True, False, 0.7))
        self.assertNotIn('stage_factors', run)
        self.assertEqual(self.started_lines(jid)['i001'], 'Started big.png (1 pass)')
        self.assertEqual(self.svc.post(f'/api/jobs/{jid}/cancel')[0], 200)
        self.svc.wait_job(jid, lambda x: x['items'][0]['state'] == 'cancelled', timeout=60)
        self.assertEqual(self.svc.shutdown(), 0)


class SingleImage(FastBase):

    def test_plans_and_waiting_images_on_two_cards(self):
        self.svc = self.service(env=dict(NO_OVERRIDES, CU_FAKE_STAGE_SECONDS='3', CU_FAKE_GPUS='2', CU_FAST='1',
                                         CU_FASTER='1'), settings={}, state='state-single')
        self.assertEqual(self.svc.post('/api/settings', {'faster': True})[0], 200)
        m = planner.plan(2048, 2048, 2).minutes
        code, p, _ = self.svc.post('/api/plan', {'width': 2048, 'height': 2048, 'scale': 2})
        f = p['finish']

        self.assertEqual((f['standard'], f['fast'], f['faster']),
                         ({'minutes': round(m * 0.7, 1), 'factor': 0.7}, {'minutes': round(m * 0.37, 1), 'factor': 0.37},
                          {'minutes': round(m * 0.609, 1), 'factor': 0.609, 'stages': [0]}))


        self.assertEqual(f['single'], {'standard': {'minutes': round(m * 0.523, 1), 'factor': 0.523, 'cards': 2},
                                       'fast': {'minutes': round(m * 0.308, 1), 'factor': 0.308, 'cards': 2},
                                       'faster': {'minutes': round(m * 0.523, 1), 'factor': 0.523, 'cards': 2, 'stages': []}})
        mids = self.inputs(3)

        a = self.job(self.svc, [mids[0]], {'scale': 2})['id']
        wait(lambda: (lambda it: it['state'] in ('preparing', 'running') and it['run'].get('frozen') or None)(
            self.svc.get(f'/api/jobs/{a}')[1]['items'][0]), timeout=60)
        b = self.job(self.svc, [mids[1]], {'scale': 2})
        rb = b['items'][0]['run']
        self.assertEqual((b['items'][0]['state'], rb['frozen'], rb['split'], rb['factor'], rb['faster'], rb['cards']),
                         ('queued', False, True, 0.523, False, []), json.dumps(rb))
        self.assertEqual(rb['minutes'], round(b['items'][0]['plan']['minutes'] * 0.523, 1))
        jb = self.svc.wait_job(b['id'], all_done, timeout=120)
        fb = jb['items'][0]['run']
        self.assertEqual((fb['frozen'], fb['split'], fb['factor'], fb['faster'], fb['cards']),
                         (True, True, 0.523, False, [0, 1]))
        self.svc.wait_job(a, all_done, timeout=60)

        c = self.job(self.svc, mids, {'scale': 2})['id']
        third = wait(lambda: (lambda j: j['items'][2] if sum(x['state'] in ('preparing', 'running') for x in j['items']) == 2
                              and j['items'][2]['state'] == 'queued' else None)(self.svc.get(f'/api/jobs/{c}')[1]),
                     timeout=60)
        r3 = third['run']
        self.assertEqual((r3['frozen'], r3['split'], r3['factor'], r3['faster']), (False, False, 0.609, True), json.dumps(r3))
        jc = self.svc.wait_job(c, all_done, timeout=120)
        f3 = jc['items'][2]['run']
        self.assertEqual((f3['split'], f3['factor'], f3['faster'], len(f3['cards'])), (False, 0.609, True, 1))
        self.assertEqual(self.svc.shutdown(), 0)


class WhatTheTabsQueueAgainUses(unittest.TestCase):

    def setUp(self):
        from tests.service.test_qa_engine import FAST, InProc
        self.d = tmpdir('cu-tab-requeue-')
        self._env = mock.patch.dict(os.environ, dict(FAST, CU_FAST_TEST='1', CU_FAKE_STAGE_SECONDS='1.5'))
        self._env.start()


        self._recipe = fast_recipe.RECIPE
        self.s = InProc(self.d)

    def tearDown(self):
        try:
            self.s.stop()
        finally:
            fast_recipe.RECIPE = self._recipe
            self._env.stop()
            rmtree(self.d)

    def test_the_recipe_put_back_is_the_shipped_one(self):
        self.assertEqual(fast_recipe.RECIPE['name'], 'test-fast')
        self.assertIsNot(self._recipe, fast_recipe.RECIPE)
        self.assertNotEqual(self._recipe['name'], 'test-fast', 'the recipe saved before this class is the shipped one')

    def test_queue_again_and_new_settings_as_the_tab_sends_them(self):
        s, r = self.s, self.s.runner
        jid = s.job(s.inputs(2), {'scale': 2})
        wait(lambda: s.item(jid, 'i001')['state'] == 'running' or None, timeout=60)
        r.stop_item(jid, 'i002')
        self.assertEqual(s.item(jid, 'i002')['state'], 'stopped')
        ref = [{'job_id': jid, 'item_id': 'i002'}]
        res = r.set_item_settings(ref, {'scale': 2, 'mode': 'fast'})
        self.assertEqual((len(res['applied']), res['refused']), (1, []), res)
        wait(lambda: s.item(jid, 'i001')['state'] == 'done' or None, timeout=60)
        self.assertEqual(s.store.get(jid)['state'], 'stopped')
        res = r.set_item_settings(ref, {'scale': 2, 'mode': 'fast', 'preset': 'Light'})
        self.assertEqual((len(res['applied']), res['refused']), (1, []), res)
        self.assertEqual(s.raw(jid, 'i002')['settings'], {'scale': 2, 'mode': 'fast', 'preset': 'Light'})

        r.requeue_item(jid, 'i002', front=True)
        wait(lambda: s.item(jid, 'i002')['state'] == 'running' or None, timeout=60)
        r.stop_item(jid, 'i002')
        wait(lambda: s.item(jid, 'i002')['state'] == 'stopped' or None, timeout=60)
        wait(lambda: (jid, 'i002') not in r.ctx or None, timeout=60)
        self.assertEqual(s.raw(jid, 'i002')['ran_with_request'], {'scale': 2, 'mode': 'fast', 'preset': 'Light'})

        gone = dict(r.fast_info(), available=False, reason='files_missing',
                    message=engine_options.FAST_MESSAGES['files_missing'])
        with mock.patch.object(r, 'fast_info', return_value=gone):
            for kw in ({}, {'as_before': True}):
                with self.assertRaises(ApiError) as cm:
                    r.requeue_item(jid, 'i002', front=True, **kw)
                self.assertEqual((cm.exception.status, cm.exception.code, cm.exception.message, cm.exception.data),
                                 (400, 'fast_unavailable', 'Bolt cannot be used: a file it needs cannot be read. '
                                  'Choose Redux.', {'reason': 'files_missing'}), kw)
                self.assertEqual(s.item(jid, 'i002')['state'], 'stopped', kw)

            want = {'scale': 2, 'mode': 'standard', 'preset': 'Light'}
            r.requeue_item(jid, 'i002', settings=want, front=True)
        raw = s.raw(jid, 'i002')
        self.assertEqual((raw['state'], raw['settings'], raw['effective']['mode'], raw['effective']['preset']),
                         ('queued', want, 'standard', 'Light'))
        self.assertIsNotNone(raw['queue_front'])
        _, eff = controls.resolve(want)
        self.assertEqual(json.loads(json.dumps(raw['effective'])), json.loads(json.dumps(eff)))
        self.assertEqual(len(raw['plan']['stages']), 1)
        wait(lambda: s.item(jid, 'i002')['state'] == 'done' or None, timeout=60)
        done = s.item(jid, 'i002')
        self.assertEqual((done['run']['mode'], done['effective']['mode']), ('standard', 'standard'))


class WhatTheHeldRequestUses(unittest.TestCase):

    def setUp(self):
        from tests.service.test_qa_engine import FAST, InProc
        self.d = tmpdir('cu-tab-held-')

        self._env = mock.patch.dict(os.environ, dict(FAST, CU_FAST_TEST='1', CU_FAKE_STAGE_SECONDS='30'))
        self._env.start()
        self._recipe = fast_recipe.RECIPE
        self.s = InProc(self.d)

    def tearDown(self):
        try:
            self.s.stop()
        finally:
            fast_recipe.RECIPE = self._recipe
            self._env.stop()
            rmtree(self.d)

    def test_while_checking_standard_goes_at_once_and_fast_once_the_files_are_read(self):
        import threading
        import time
        s, r = self.s, self.s.runner
        jid = s.job(s.inputs(3), {'scale': 2})
        wait(lambda: s.item(jid, 'i001')['state'] == 'running' or None, timeout=60)
        waiting = [{'job_id': jid, 'item_id': i} for i in ('i002', 'i003')]
        res = r.set_item_settings(waiting, {'scale': 2, 'mode': 'fast', 'preset': 'Light'})
        self.assertEqual((len(res['applied']), res['refused']), (2, []), res)
        held_back = threading.Event()
        with mock.patch.object(r, '_fast_check_due', return_value=True), \
                mock.patch.object(r, '_refresh_health', return_value=None), \
                mock.patch.object(r, '_snap_ready', held_back), \
                mock.patch.object(r, '_fast_files_ok', None), \
                mock.patch.object(runner, 'FAST_CHECK_WAIT_S', 6.0):
            self.assertEqual(r.fast_info()['reason'], 'checking')

            t0 = time.monotonic()
            res = r.set_item_settings(waiting[:1], {'scale': 2, 'mode': 'standard', 'preset': 'Light'})
            self.assertLess(time.monotonic() - t0, 3.0)
            self.assertEqual((len(res['applied']), res['refused']), (1, []), res)
            self.assertEqual(s.raw(jid, 'i002')['effective']['mode'], 'standard')

            t0 = time.monotonic()
            res = r.set_item_settings([{'job_id': jid, 'item_id': 'i001'}], {'scale': 2, 'mode': 'fast', 'preset': 'Default'})
            self.assertLess(time.monotonic() - t0, 3.0)
            self.assertEqual(res, {'applied': [], 'refused': [{'job_id': jid, 'item_id': 'i001', 'code': 'started',
                                                               'reason': 'This image has started.'}]})
            self.assertEqual([s.item(jid, i)['state'] for i in ('i002', 'i003')], ['queued', 'queued'])

            r._fast_files_ok = True
            held_back.set()
            self.assertTrue(r.fast_info()['available'])
            t0 = time.monotonic()
            res = r.set_item_settings(waiting[1:], {'scale': 2, 'mode': 'fast', 'preset': 'Default'})
            self.assertLess(time.monotonic() - t0, 3.0)
            self.assertEqual((len(res['applied']), res['refused']), (1, []), res)
            raw = s.raw(jid, 'i003')
            self.assertEqual((raw['state'], raw['effective']['mode'], raw['effective']['preset']), ('queued', 'fast', 'Default'))
        r.cancel_job(jid)


if __name__ == '__main__':
    unittest.main()
