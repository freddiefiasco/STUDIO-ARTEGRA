import json
import subprocess
import sys
import time
import types
import unittest
from pathlib import Path

from PIL import Image

from engine import controls, graph_v5t, planner
from service import runner, settings as settings_mod
from tests.service.helpers import REPO, gradient, rmtree, tmpdir
from tests.service.test_integration import Base, all_done
from tests.service.test_v4 import V4Base, wait

STACK = {'noise_prefetch': True, 'pag_fuse': True, 'batch_windows': 2, 'fp16_acc_scoped': True}
V3_COMMIT = '8b227d5'


class Log:
    def __init__(self):
        self.rows = []

    def log(self, level, event, msg=None, **kw):
        self.rows.append((level, event, msg, kw))

    def info(self, event, msg=None, **kw):
        self.log('info', event, msg, **kw)

    def warn(self, event, msg=None, **kw):
        self.log('warn', event, msg, **kw)

    def error(self, event, msg=None, **kw):
        self.log('error', event, msg, **kw)


def v3_settings_module():
    src = subprocess.run(['git', '-C', str(REPO), 'show', f'{V3_COMMIT}:service/settings.py'], capture_output=True, check=True).stdout
    mod = types.ModuleType('settings_v3')
    mod.__file__ = f'{V3_COMMIT}:service/settings.py'
    exec(compile(src.decode('utf8'), mod.__file__, 'exec'), mod.__dict__)
    return mod


class SettingsRoundTrip(unittest.TestCase):

    def setUp(self):
        self.d = tmpdir('cu-port-set-')
        self.path = self.d / 'settings.json'
        self.out = self.d / 'out'
        self.out.mkdir()

    def tearDown(self):
        rmtree(self.d)

    def make(self, proven=False):
        s = settings_mod.Settings(self.path, self.out, Log(), total_ram_gb=64.0)
        s.gpus_fn = lambda: [0, 1]
        s.split_default_fn = lambda: proven
        return s

    def test_defaults(self):
        s = self.make()
        g = s.get()
        self.assertEqual((g['match_earlier'], g['split'], g['split_chosen']), (False, False, False))
        self.assertEqual(self.make(proven=True).get()['split'], True)
        self.assertNotIn('speed', g)

    @unittest.skip('standalone: reads the internal repository history, which the public repository does not carry')
    def test_round_trip_and_old_version_read(self):
        s = self.make()
        s.update({'match_earlier': True, 'split': False, 'output_dir': str(self.out)}, [0, 1])
        g = s.get()
        self.assertEqual((g['match_earlier'], g['split'], g['split_chosen']), (True, False, True))
        on_disk = json.loads(self.path.read_text(encoding='utf8'))
        self.assertEqual(sorted(on_disk), ['gpus', 'idle_minutes', 'output_dir', 'ram_cap_gb'])
        extra = json.loads((self.d / 'settings-extra.json').read_text(encoding='utf8'))
        self.assertEqual((extra['match_earlier'], extra['split']), (True, False))

        again = self.make()
        self.assertEqual((again.get()['match_earlier'], again.get()['split'], again.get()['split_chosen']), (True, False, True))
        self.assertIsNone(again.load_problem)

        v3 = v3_settings_module()
        old = v3.Settings(self.path, self.out, Log(), total_ram_gb=64.0)
        self.assertIsNone(old.load_problem)
        self.assertEqual(old.get()['output_dir'], str(self.out))
        self.assertNotIn('match_earlier', old.get())

        old.gpus_fn = lambda: [0, 1]
        old.update({'idle_minutes': 7}, [0, 1])
        back = self.make()
        self.assertEqual((back.get()['idle_minutes'], back.get()['match_earlier'], back.get()['split']), (7, True, False))
        self.assertIsNone(back.load_problem)

    def test_split_default_choice_and_back(self):
        s = self.make(proven=True)
        self.assertEqual((s.get()['split'], s.get()['split_chosen']), (True, False))
        s.update({'split': False}, [0, 1])
        self.assertEqual((s.get()['split'], s.get()['split_chosen']), (False, True))
        self.assertEqual(json.loads((self.d / 'settings-extra.json').read_text(encoding='utf8'))['split'], False)
        s.update({'split': 'default'}, [0, 1])
        self.assertEqual((s.get()['split'], s.get()['split_chosen']), (True, False))
        self.assertIsNone(json.loads((self.d / 'settings-extra.json').read_text(encoding='utf8'))['split'])

        early = self.make(proven=False)
        early.update({'split': True}, [0, 1])
        self.assertEqual((early.get()['split'], early.get()['split_chosen']), (True, True))

    def test_bad_values_are_refused_in_plain_words(self):
        s = self.make()
        for patch, text in (({'match_earlier': 'yes'}, 'match_earlier must be true or false.'),
                            ({'match_earlier': 1}, 'match_earlier must be true or false.'),
                            ({'split': 'on'}, 'split must be true, false or "default".'),
                            ({'split': None}, 'split must be true, false or "default".'),
                            ({'speed': {'pag_fuse': True}}, 'These settings cannot be changed here: speed')):
            with self.assertRaises(settings_mod.SettingsError) as cm:
                s.update(patch, [0, 1])
            self.assertEqual(str(cm.exception), text)
        self.assertEqual(s.get()['match_earlier'], False)

    def test_a_10_nov_file_and_a_later_versions_key_are_kept_and_ignored(self):
        (self.d / 'settings-extra.json').write_text(json.dumps({'detailed_preview': False, 'notify': True, 'hold_sleep': True,
                                                                'speed': {'pag_fuse': True}, 'from_v5': [1, 2]}), encoding='utf8')
        s = self.make()
        self.assertIsNone(s.load_problem)
        self.assertEqual((s.get()['detailed_preview'], s.get()['match_earlier']), (False, False))
        self.assertNotIn('speed', s.get())
        s.update({'match_earlier': True}, [0, 1])
        extra = json.loads((self.d / 'settings-extra.json').read_text(encoding='utf8'))
        self.assertEqual((extra['speed'], extra['from_v5'], extra['match_earlier']), ({'pag_fuse': True}, [1, 2], True))


def spot_inputs(graph):
    spot = next(v for v in graph.values() if v['class_type'] == 'ClaudeSpotTiles')
    return {k: v for k, v in spot['inputs'].items() if not isinstance(v, list)}


class PortBase(V4Base):
    def sent(self, jid, iid, k=0, worker='gpu0'):
        p = self.d / 'state' / 'workers' / worker / 'fake-prompts' / f'cu_{jid}_{iid}_s{k}.json'
        return json.loads(p.read_text(encoding='utf8'))

    def health(self):
        code, h, _ = self.svc.get('/health')
        self.assertEqual(code, 200, h)
        return h

    def side(self, item):
        return json.loads(Path(item['sidecar']).read_text(encoding='utf8'))

    def started_lines(self, jid=None):
        out = {}
        for ln in self.svc.log_lines():
            if ln.get('event') == 'item_started' and (jid is None or ln.get('job') == jid):
                out.setdefault(ln['item'], ln['msg'])
        return out


class MatchEarlier(PortBase):
    def test_setting_health_and_plan(self):


        self.svc = self.service(env={'CU_FAST': '0'})
        code, s, _ = self.svc.get('/api/settings')


        self.assertEqual((s['match_earlier'], s['split'], s['split_chosen']), (False, True, False))
        h = self.health()
        self.assertTrue(h['features']['match_earlier'])
        self.assertFalse(h['features']['fast'])
        sp = h['engine']['speed']
        self.assertEqual((sp['speed_stack'], sp['match_earlier'], sp['eta_factor'], sp['pag_fuse'], sp['batch_windows'],
                          sp['fp16_acc_scoped'], sp['noise_prefetch'], sp['window_split']),
                         (True, False, 0.7, True, 2, True, True, False))
        self.assertEqual(sp['factors'], {'standard': 0.7, 'match_earlier': 0.947, 'fast': None, 'faster': None})
        code, p, _ = self.svc.post('/api/plan', {'width': 2048, 'height': 2048, 'scale': 2})
        self.assertEqual(code, 200, p)
        m = planner.plan(2048, 2048, 2).minutes
        self.assertEqual(p['minutes'], m)

        self.assertEqual(p['finish'], {'match_earlier': False, 'standard': {'minutes': round(m * 0.7, 1), 'factor': 0.7},
                                       'fast': None, 'fast_refusal': {'reason': 'pending_proof', 'message': 'Bolt is not available. Choose Redux.'},
                                       'single': {'standard': {'minutes': round(m * 0.7, 1), 'factor': 0.7, 'cards': 1},
                                                  'fast': None}})
        self.assertEqual(p['text']['eta'], f'about {m * 0.7:.0f} min')
        mid = self.inputs(1)[0]
        code, inp, _ = self.svc.get('/api/inputs')
        sc = inp['items'][0]['scales']
        self.assertEqual(sc['2']['finish']['standard'], {'minutes': round(sc['2']['minutes'] * 0.7, 1), 'factor': 0.7})
        self.assertEqual(sc['4']['finish']['standard']['factor'], 0.7)
        self.assertIsNone(sc['2']['finish']['fast'])

        code, s, _ = self.svc.post('/api/settings', {'match_earlier': True})
        self.assertEqual((code, s['match_earlier']), (200, True))
        code, e, _ = self.svc.post('/api/settings', {'match_earlier': 'on'})
        self.assertEqual((code, e['error']['message'] if 'error' in e else e.get('message')), (400, 'match_earlier must be true or false.'))
        sp = self.health()['engine']['speed']
        self.assertEqual((sp['speed_stack'], sp['match_earlier'], sp['eta_factor'], sp['pag_fuse'], sp['batch_windows'],
                          sp['fp16_acc_scoped'], sp['noise_prefetch']), (False, True, 0.947, False, 1, False, True))
        code, p, _ = self.svc.post('/api/plan', {'width': 2048, 'height': 2048, 'scale': 2, 'mode': 'standard'})
        self.assertEqual(p['finish'], {'match_earlier': True, 'standard': {'minutes': round(m * 0.947, 1), 'factor': 0.947},
                                       'fast': None, 'fast_refusal': {'reason': 'pending_proof', 'message': 'Bolt is not available. Choose Redux.'},
                                       'single': {'standard': {'minutes': round(m * 0.947, 1), 'factor': 0.947, 'cards': 1},
                                                  'fast': None}})
        code, inp, _ = self.svc.get('/api/inputs')
        self.assertEqual(inp['items'][0]['scales']['2']['finish']['standard']['factor'], 0.947)
        self.assertEqual(self.svc.shutdown(), 0)
        svc2 = self.service()
        self.assertTrue(svc2.get('/api/settings')[1]['match_earlier'])
        self.assertEqual(svc2.shutdown(), 0)
        self.assertTrue(mid)

    def test_applied_per_image_at_dispatch_and_recorded(self):
        self.svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '3'})
        mids = self.inputs(2)
        job = self.job(self.svc, mids, {'scale': 2})
        jid = job['id']

        waiting = {'mode': 'standard', 'match_earlier': False, 'speed_stack': True, 'frozen': False, 'split': False, 'factor': 0.7,
                   'faster': False, 'cards': []}
        for it in job['items']:
            self.assertEqual({k: v for k, v in it['run'].items() if k != 'minutes'}, waiting)
            self.assertEqual(it['run']['minutes'], round(it['plan']['minutes'] * 0.7, 1))
            self.assertEqual(it['effective']['mode'], 'standard')
        self.assertEqual(job['effective']['mode'], 'standard')
        wait(lambda: self.item(jid, 'i001')['state'] == 'running')
        self.assertEqual(self.item(jid, 'i001')['run'], dict(waiting, frozen=True, cards=[0],
                                                             minutes=round(job['items'][0]['plan']['minutes'] * 0.7, 1)))

        self.assertEqual(self.svc.post('/api/settings', {'match_earlier': True})[0], 200)
        r1, r2 = self.item(jid, 'i001')['run'], self.item(jid, 'i002')['run']
        self.assertEqual((r1['match_earlier'], r1['speed_stack'], r1['frozen'], r1['factor']), (False, True, True, 0.7))
        self.assertEqual((r2['match_earlier'], r2['speed_stack'], r2['frozen'], r2['factor']), (True, False, False, 0.947))
        self.assertEqual(r2['minutes'], round(job['items'][1]['plan']['minutes'] * 0.947, 1))
        wait(lambda: self.item(jid, 'i002')['state'] == 'running', timeout=60)

        self.assertEqual(self.svc.post('/api/settings', {'match_earlier': False})[0], 200)
        r2 = self.item(jid, 'i002')['run']
        self.assertEqual((r2['match_earlier'], r2['speed_stack'], r2['frozen'], r2['factor']), (True, False, True, 0.947))
        j = self.svc.wait_job(jid, all_done, timeout=120)
        self.assertEqual([x['state'] for x in j['items']], ['done', 'done'])

        g1, g2 = self.sent(jid, 'i001'), self.sent(jid, 'i002')
        self.assertEqual({k: v for k, v in spot_inputs(g1).items() if k in STACK or k == 'live_preview'},
                         dict(STACK, live_preview='detailed'))
        s2 = spot_inputs(g2)
        self.assertEqual({k: s2.get(k) for k in ('noise_prefetch', 'live_preview', 'pag_fuse', 'batch_windows', 'fp16_acc_scoped')},
                         {'noise_prefetch': True, 'live_preview': 'detailed', 'pag_fuse': None, 'batch_windows': None,
                          'fp16_acc_scoped': None})
        st = j['items'][1]['plan']['stages'][0]
        pre = f'cu_{jid}_i002_s0'
        want, _ = graph_v5t.build_product(pre + '.png', *st['padded_size'], controls.stage_params(controls.resolve({'scale': 2})[0], 0),
                                          pre, f=runner._frac(st['factor']), s=runner._frac(st['supersample']), speed_stack=False,
                                          live_preview='detailed')
        self.assertEqual(g2, json.loads(json.dumps(want)))

        s1, s2 = self.side(j['items'][0]), self.side(j['items'][1])
        self.assertEqual((s1['run']['match_earlier'], s1['run']['speed_stack'], s1['run']['frozen'], s1['run']['factor'],
                          s1['run']['cards'], s1['engine']['speed_stack']), (False, True, True, 0.7, [0], True))
        self.assertEqual((s2['run']['match_earlier'], s2['run']['speed_stack'], s2['run']['frozen'], s2['run']['factor'],
                          s2['engine']['speed_stack']), (True, False, True, 0.947, False))
        self.assertEqual(s1['engine']['spot_options'], dict(STACK, live_preview='detailed'))
        self.assertEqual(s2['engine']['spot_options'], {'noise_prefetch': True, 'live_preview': 'detailed'})
        self.assertEqual((s1['effective']['mode'], s1['engine']['graph'], s1['engine']['fast']),
                         ('standard', 'engine/graph_v5t.py', None))
        self.assertEqual(s1['timings']['stages'][0]['spot_options'], s1['engine']['spot_options'])

        lines = self.started_lines()
        self.assertEqual(lines['i001'], 'Started pic0.png (1 pass)')
        self.assertEqual(lines['i002'], 'Started pic1.png (1 pass), matching earlier results')

        self.assertEqual(self.item(jid, 'i002')['run']['match_earlier'], True)
        self.assertEqual(self.svc.shutdown(), 0)

    def test_an_image_that_goes_on_from_finished_passes_keeps_its_numbers(self):
        self.svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '3'})
        mids = self.inputs(1)
        jid = self.job(self.svc, mids, {'scale': 4})['id']
        wait(lambda: (lambda x: x['state'] == 'running' and x['stage_index'] == 1)(self.item(jid, 'i001')), timeout=60)
        first = self.sent(jid, 'i001', 0)
        self.assertEqual(self.svc.post(f'/api/cancel?image={mids[0]}')[0], 200)
        it = wait(lambda: (lambda x: x if x['state'] == 'stopped' else None)(self.item(jid, 'i001')))
        self.assertEqual((it['run']['frozen'], it['run']['match_earlier']), (True, False))
        self.assertEqual(self.svc.post('/api/settings', {'match_earlier': True})[0], 200)
        code, j, _ = self.svc.post(f'/api/jobs/{jid}/items/i001/requeue', {})
        self.assertEqual(code, 200, j)
        it = next(x for x in j['items'] if x['id'] == 'i001')
        self.assertEqual((it['state'], it['stage_index']), ('queued', 1))
        self.assertEqual((it['run']['frozen'], it['run']['match_earlier'], it['run']['speed_stack']), (True, False, True))

        mid2 = self.inputs(2)[1]
        jid2 = self.job(self.svc, [mid2], {'scale': 2})['id']
        self.assertEqual(self.item(jid2, 'i001')['run']['match_earlier'], True)
        self.svc.wait_job(jid, all_done, timeout=120)
        self.svc.wait_job(jid2, all_done, timeout=120)
        second = self.sent(jid, 'i001', 1)
        self.assertEqual(spot_inputs(first).get('pag_fuse'), True)
        self.assertEqual({k: v for k, v in spot_inputs(second).items() if k in STACK}, STACK)
        self.assertIsNone(spot_inputs(self.sent(jid2, 'i001')).get('pag_fuse'))
        side = self.side(self.item(jid, 'i001'))
        self.assertEqual((side['run']['match_earlier'], side['engine']['speed_stack']), (False, True))
        starts = [ln['msg'] for ln in self.svc.log_lines() if ln.get('event') == 'item_started' and ln.get('job') == jid]
        self.assertEqual(starts, ['Started pic0.png (2 passes)', 'Started pic0.png (2 passes, from pass 2)'])
        self.assertEqual(self.started_lines(jid2)['i001'], 'Started pic1.png (1 pass), matching earlier results')

        mid3 = self.inputs(3)[2]
        jid3 = self.job(self.svc, [mid3], {'scale': 2})['id']
        self.svc.post('/api/settings', {'match_earlier': False})
        self.assertEqual(self.item(jid3, 'i001')['run']['match_earlier'] in (True, False), True)
        self.svc.wait_job(jid3, all_done, timeout=120)
        self.assertEqual(self.svc.shutdown(), 0)

    def test_waiting_eta_uses_each_images_factor(self):
        self.svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '4'})
        mids = self.inputs(2)
        self.svc.post('/api/settings', {'match_earlier': True})
        job = self.job(self.svc, mids, {'scale': 2})

        total = sum(it['plan']['minutes'] for it in job['items']) * 60
        self.assertAlmostEqual(job['summary']['eta_s'], total * 0.947, delta=2)
        self.svc.post('/api/settings', {'match_earlier': False})
        code, j, _ = self.svc.get(f'/api/jobs/{job["id"]}')
        waiting = [it for it in j['items'] if it['state'] == 'queued']
        self.assertTrue(all(it['run']['factor'] == 0.7 for it in waiting))
        self.svc.post(f'/api/jobs/{job["id"]}/cancel')
        self.assertEqual(self.svc.shutdown(), 0)


class ModeWithoutARecipe(PortBase):
    def test_fast_is_refused_in_plain_words(self):

        self.svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '2', 'CU_FAST': '0'})
        h = self.health()


        self.assertEqual(h['engine']['fast'], {'available': False, 'reason': 'pending_proof',
                                               'message': 'Bolt is not in this version.',
                                               'recipe': 'H8-e8-s25-c5-p3-k+so16+stk', 'version': '1', 'factor': None,
                                               'factors': None, 'split': False, 'looks': ['Light', 'Default'], 'max_factor': 2})
        self.assertFalse(h['features']['fast'])
        code, c, _ = self.svc.get('/api/controls')
        self.assertEqual([m['key'] for m in c['modes']], ['standard', 'fast'])
        self.assertEqual(c['modes'][1]['text'], 'Quicker, with a slightly different look. Use Redux for finals.')
        mids = self.inputs(2)
        code, e, _ = self.svc.post('/api/jobs', {'client_request_id': '0' * 32, 'media_ids': mids, 'settings': {'mode': 'fast'}})
        self.assertEqual(code, 400, e)
        err = e.get('error', e)
        self.assertEqual((err['code'], err['message']), ('fast_unavailable', 'Bolt is not available. Choose Redux.'))
        code, e, _ = self.svc.post('/api/jobs', {'client_request_id': '1' * 32, 'media_ids': mids, 'settings': {'mode': 'turbo'}})
        self.assertEqual((code, e.get('error', e)['code'], e.get('error', e)['message']),
                         (400, 'bad_settings', 'Choose a mode: Redux or Bolt.'))
        code, e, _ = self.svc.post('/api/plan', {'width': 1024, 'height': 768, 'scale': 2, 'mode': 'fast'})
        self.assertEqual((code, e.get('error', e)['code']), (400, 'fast_unavailable'))
        code, e, _ = self.svc.post('/api/plan', {'width': 1024, 'height': 768, 'scale': 2, 'mode': 'quick'})
        self.assertEqual((code, e.get('error', e)['code']), (400, 'bad_settings'))

        job = self.job(self.svc, mids, {'scale': 2, 'mode': 'standard'})
        jid = job['id']
        code, res, _ = self.svc.post('/api/items/settings', {'items': [{'job_id': jid, 'item_id': 'i002'}],
                                                              'settings': {'scale': 2, 'mode': 'fast'}})
        self.assertEqual(code, 200, res)
        self.assertEqual(res['applied'], [])
        self.assertEqual([(r['item_id'], r['code'], r['reason']) for r in res['refused']],
                         [('i002', 'fast_unavailable', 'Bolt is not available. Choose Redux.')])
        wait(lambda: self.item(jid, 'i001')['state'] == 'running')
        self.assertEqual(self.svc.post(f'/api/cancel?image={mids[0]}')[0], 200)
        wait(lambda: self.item(jid, 'i001')['state'] == 'stopped')
        code, e, _ = self.svc.post(f'/api/jobs/{jid}/items/i001/requeue', {'settings': {'scale': 2, 'mode': 'fast'}})
        self.assertEqual((code, e.get('error', e)['code']), (400, 'fast_unavailable'))
        j = self.svc.wait_job(jid, lambda x: x['items'][1]['state'] == 'done', timeout=60)
        self.assertEqual(j['items'][1]['effective']['mode'], 'standard')
        self.assertEqual(self.side(j['items'][1])['effective']['mode'], 'standard')
        self.assertEqual(self.svc.shutdown(), 0)


class ModeWithTheStandIn(PortBase):

    def run_batch(self, fast_env, fast_item):
        self.svc = self.service(env=dict({'CU_FAKE_STAGE_SECONDS': '1.5'}, **fast_env), state='state-' + ('f' if fast_env else 's'))
        self.state = self.d / ('state-' + ('f' if fast_env else 's'))
        mids = self.inputs(3)
        job = self.job(self.svc, mids, {'scale': 2})
        jid = job['id']
        if fast_item:
            code, res, _ = self.svc.post('/api/items/settings', {'items': [{'job_id': jid, 'item_id': fast_item}],
                                                                  'settings': {'scale': 2, 'mode': 'fast'}})
            self.assertEqual(code, 200, res)
            self.assertEqual([a['item_id'] for a in res['applied']], [fast_item], res)
            self.assertEqual(res['applied'][0]['effective']['mode'], 'fast')
        j = self.svc.wait_job(jid, all_done, timeout=120)
        self.assertEqual([x['state'] for x in j['items']], ['done'] * 3, json.dumps(j)[:2000])
        graphs = {}
        for iid in ('i001', 'i002', 'i003'):
            text = (self.state / 'workers' / 'gpu0' / 'fake-prompts' / f'cu_{jid}_{iid}_s0.json').read_text(encoding='utf8')
            graphs[iid] = text.replace(jid, 'JOB')
        return j, graphs

    def test_fast_is_one_images_choice_and_standard_is_byte_identical(self):
        plain_job, plain = self.run_batch({}, None)
        self.assertEqual(self.svc.shutdown(), 0)
        job, mixed = self.run_batch({'CU_FAST_TEST': '1'}, 'i002')
        h = self.health()

        self.assertEqual(h['engine']['fast'], {'available': True, 'reason': None, 'message': None, 'recipe': 'test-fast',
                                               'version': '0', 'factor': 0.3, 'factors': {'first_stage': 0.3}, 'split': False,
                                               'looks': ['Light', 'Default'], 'max_factor': 2})
        self.assertTrue(h['features']['fast'])
        self.assertEqual(h['engine']['speed']['factors']['fast'], 0.3)

        self.assertEqual(mixed['i001'], plain['i001'])
        self.assertEqual(mixed['i003'], plain['i003'])
        self.assertNotEqual(mixed['i002'], plain['i002'])
        fast_graph, std_graph = json.loads(mixed['i002']), json.loads(plain['i002'])
        self.assertEqual({v['inputs']['steps'] for v in fast_graph.values() if v['class_type'] == 'KSampler'}, {8})
        self.assertEqual({v['inputs']['steps'] for v in std_graph.values() if v['class_type'] == 'KSampler'}, {30})

        st = job['items'][0]['plan']['stages'][0]
        pre = 'cu_JOB_i001_s0'
        want, _ = graph_v5t.build_product(pre + '.png', *st['padded_size'], controls.stage_params(controls.resolve({'scale': 2})[0], 0),
                                          pre, f=runner._frac(st['factor']), s=runner._frac(st['supersample']), speed_stack=True,
                                          live_preview='detailed')
        self.assertEqual(json.loads(mixed['i001']), json.loads(json.dumps(want)))

        modes = [(x['effective']['mode'], x['run']['mode'], x['run']['factor'], x['run']['match_earlier']) for x in job['items']]
        self.assertEqual(modes, [('standard', 'standard', 0.7, False), ('fast', 'fast', 0.3, False),
                                 ('standard', 'standard', 0.7, False)])
        self.assertEqual(job['effective']['mode'], 'standard')
        sf, ss = self.side(job['items'][1]), self.side(job['items'][0])
        self.assertEqual((sf['effective']['mode'], sf['run']['mode'], sf['engine']['graph'], sf['engine']['fast']),
                         ('fast', 'fast', 'engine/fast_recipe.py', {'recipe': 'test-fast', 'version': '0'}))
        self.assertEqual((ss['effective']['mode'], ss['run']['mode'], ss['engine']['graph'], ss['engine']['fast']),
                         ('standard', 'standard', 'engine/graph_v5t.py', None))
        lines = self.started_lines()
        self.assertEqual(lines['i002'], 'Started pic1.png (1 pass), Bolt')
        self.assertEqual(lines['i001'], 'Started pic0.png (1 pass)')

        code, p, _ = self.svc.post('/api/plan', {'width': 2048, 'height': 2048, 'scale': 2, 'mode': 'fast'})
        m = planner.plan(2048, 2048, 2).minutes
        self.assertEqual(p['finish'], {'match_earlier': False, 'standard': {'minutes': round(m * 0.7, 1), 'factor': 0.7},
                                       'fast': {'minutes': round(m * 0.3, 1), 'factor': 0.3}, 'fast_refusal': None,
                                       'single': {'standard': {'minutes': round(m * 0.7, 1), 'factor': 0.7, 'cards': 1},
                                                  'fast': {'minutes': round(m * 0.3, 1), 'factor': 0.3, 'cards': 1}}})
        self.assertEqual(self.svc.shutdown(), 0)

    def test_fast_job_stop_and_queue_again_in_standard(self):
        self.svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '3', 'CU_FAST_TEST': '1'})
        mids = self.inputs(1)
        self.svc.post('/api/settings', {'match_earlier': True})
        job = self.job(self.svc, mids, {'scale': 2, 'mode': 'fast'})
        jid = job['id']
        self.assertEqual((job['effective']['mode'], job['items'][0]['run']['mode'], job['items'][0]['run']['match_earlier'],
                          job['items'][0]['run']['factor']), ('fast', 'fast', False, 0.3))
        self.assertEqual(job['items'][0]['run']['minutes'], round(job['items'][0]['plan']['minutes'] * 0.3, 1))
        wait(lambda: self.item(jid, 'i001')['state'] == 'running')
        self.assertEqual(self.svc.post(f'/api/cancel?image={mids[0]}')[0], 200)
        it = wait(lambda: (lambda x: x if x['state'] == 'stopped' else None)(self.item(jid, 'i001')))
        self.assertEqual((it['ran_with']['mode'], it['settings_changed']), ('fast', False))
        code, res, _ = self.svc.post('/api/items/settings', {'items': [{'job_id': jid, 'item_id': 'i001'}],
                                                              'settings': {'scale': 2, 'mode': 'standard'}})
        self.assertEqual(code, 200, res)
        it = self.item(jid, 'i001')
        self.assertEqual((it['effective']['mode'], it['settings_changed']), ('standard', True))
        code, j, _ = self.svc.post(f'/api/jobs/{jid}/items/i001/requeue', {})
        self.assertEqual(code, 200, j)
        j = self.svc.wait_job(jid, all_done, timeout=60)
        side = self.side(j['items'][0])
        self.assertEqual((side['effective']['mode'], side['run']['mode'], side['run']['match_earlier'], side['engine']['fast']),
                         ('standard', 'standard', True, None))
        self.assertEqual({v['inputs']['steps'] for v in self.sent(jid, 'i001').values() if v['class_type'] == 'KSampler'}, {30})
        self.assertIsNone(spot_inputs(self.sent(jid, 'i001')).get('pag_fuse'))
        self.assertEqual(self.svc.shutdown(), 0)


class SplitReadiness(Base):

    def inputs(self, svc, n, start=0):
        d = self.d / 'in'
        d.mkdir(parents=True, exist_ok=True)
        paths = []
        for i in range(start, start + n):
            p = d / f'q{i}.png'
            Image.fromarray(gradient(80, 64, i)).save(p)
            paths.append(p)
        return [it['id'] for it in self.add(svc, paths)['items']][-n:]

    def health(self, svc):
        code, h, _ = svc.get('/health')
        self.assertEqual(code, 200, h)
        return h

    def test_not_proven_nothing_is_shared_and_health_says_so(self):


        svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '0.5', 'CU_FAKE_GPUS': '2', 'CU_SPLIT_TEST': '0'}, settings={})
        s = svc.get('/api/settings')[1]
        self.assertEqual((s['split'], s['split_chosen']), (False, False))
        h = self.health(svc)
        self.assertFalse(h['features']['split'])
        self.assertEqual(h['engine']['split'], {
            'available': False, 'on': False, 'reason': 'pending_ws_proof', 'topology': None, 'proven': False, 'setting': False,
            'floor_gb': 19.0, 'message': 'Each image runs on one GPU in this version.',
            'cards': [{'gpu': 0, 'vram_free_gb': 32.0, 'above_floor': True}, {'gpu': 1, 'vram_free_gb': 32.0, 'above_floor': True}]})
        self.assertFalse(h['engine']['speed']['window_split'])

        code, s, _ = svc.post('/api/settings', {'split': True})
        self.assertEqual((code, s['split'], s['split_chosen']), (200, True, True))
        sp = self.health(svc)['engine']['split']
        self.assertEqual((sp['setting'], sp['on'], sp['available'], sp['reason']), (True, False, False, 'pending_ws_proof'))
        mids = self.inputs(svc, 1)
        j = svc.wait_job(self.job(svc, mids, {'scale': 2})['id'], all_done, timeout=30)
        self.assertEqual((j['items'][0]['run']['split'], j['items'][0]['run']['cards']), (False, [0]))
        self.assertFalse((self.d / 'state' / 'workers' / 'gpu0+1').exists())
        code, e, _ = svc.post('/api/settings', {'split': 'yes'})
        self.assertEqual((code, e.get('error', e)['message']), (400, 'split must be true, false or "default".'))
        self.assertEqual(svc.shutdown(), 0)

    def test_proven_one_image_on_both_cards_what_the_item_and_live_say(self):
        svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '3', 'CU_FAKE_GPUS': '2', 'CU_SPLIT_TEST': '1'}, settings={})
        s = svc.get('/api/settings')[1]
        self.assertEqual((s['split'], s['split_chosen']), (True, False))
        sp = self.health(svc)['engine']['split']
        self.assertEqual((sp['proven'], sp['available'], sp['setting'], sp['on'], sp['reason'], sp['message']),
                         (True, True, True, True, None, None))
        self.assertTrue(self.health(svc)['features']['split'])
        self.assertTrue(self.health(svc)['engine']['speed']['window_split'])
        mids = self.inputs(svc, 1)
        jid = self.job(svc, mids, {'scale': 2})['id']
        live = None
        t0 = time.monotonic()
        while time.monotonic() - t0 < 40:
            code, lv, _ = svc.get('/api/live')
            live = next((x for x in lv['items'] if x['job_id'] == jid and x['state'] == 'sampling'), None)
            if live is not None:
                break
            time.sleep(0.1)
        self.assertIsNotNone(live, 'the shared image never reached sampling')
        self.assertEqual((live['split'], live['cards'], live['card']), (True, [0, 1], 0))
        code, job, _ = svc.get(f'/api/jobs/{jid}')
        it = job['items'][0]
        self.assertEqual((it['gpu'], it['cards'], it['run']['split'], it['run']['cards'], it['run']['frozen']),
                         (0, [0, 1], True, [0, 1], True))
        h = self.health(svc)
        self.assertEqual([(w['item_id'], w['cards'], w['state']) for w in h['engine']['workers']],
                         [('i001', [0, 1], 'working'), ('i001', [0, 1], 'working')])
        self.assertEqual(h['engine']['split']['topology'], {'mode': 'split', 'workers': [[0, 1]]})
        j = svc.wait_job(jid, all_done, timeout=60)
        it = j['items'][0]
        self.assertEqual((it['state'], it['cards'], it['run']['split'], it['run']['cards']), ('done', [], True, [0, 1]))
        side = json.loads(Path(it['sidecar']).read_text(encoding='utf8'))
        self.assertEqual((side['run']['split'], side['run']['cards'], side['engine']['spot_options'].get('window_split')),
                         (True, [0, 1], True))

        code, s, _ = svc.post('/api/settings', {'split': False})
        self.assertEqual((s['split'], s['split_chosen']), (False, True))
        sp = self.health(svc)['engine']['split']
        self.assertEqual((sp['available'], sp['on'], sp['reason'], sp['message']), (True, False, 'turned_off', None))
        mids2 = self.inputs(svc, 1, start=1)
        j2 = svc.wait_job(self.job(svc, mids2, {'scale': 2})['id'], all_done, timeout=60)
        self.assertEqual((j2['items'][0]['run']['split'], len(j2['items'][0]['run']['cards'])), (False, 1))

        seq = [(ln['event'], (ln.get('data') or {}).get('gpus'), ln.get('item')) for ln in svc.log_lines()
               if ln.get('event') in ('worker_stopped', 'item_dispatched')]
        stop = seq.index(('worker_stopped', [0, 1], None))
        self.assertEqual([e for e, _, _ in seq[stop + 1:]].count('item_dispatched'), 1)
        self.assertEqual([e for e, _, _ in seq[:stop]].count('item_dispatched'), 1)
        self.assertIn('each image runs on one card again', next(
            ln['msg'] for ln in svc.log_lines() if ln.get('event') == 'worker_stopped' and ln['data'].get('gpus') == [0, 1]))

        code, s, _ = svc.post('/api/settings', {'split': 'default'})
        self.assertEqual((s['split'], s['split_chosen']), (True, False))
        code, s, _ = svc.post('/api/settings', {'gpus': [0]})
        self.assertEqual(code, 200, s)
        sp = self.health(svc)['engine']['split']
        self.assertEqual((sp['available'], sp['on'], sp['reason'], sp['message'], [c['gpu'] for c in sp['cards']]),
                         (False, False, 'one_card', 'One GPU is in use, so each image runs on it.', [0]))
        self.assertEqual(svc.shutdown(), 0)

    def test_a_card_under_the_floor_is_said_in_plain_words(self):
        svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '0.5', 'CU_FAKE_GPUS': '2', 'CU_SPLIT_TEST': '1',
                                'CU_FAKE_VRAM_FREE': '32,14'}, settings={})
        sp = self.health(svc)['engine']['split']
        self.assertEqual((sp['on'], sp['reason']), (True, 'card_under_floor'))
        self.assertEqual(sp['message'], 'GPU 2 has 14 GB free; sharing an image needs 19 GB.')
        self.assertEqual(sp['cards'], [{'gpu': 0, 'vram_free_gb': 32.0, 'above_floor': True},
                                       {'gpu': 1, 'vram_free_gb': 14.0, 'above_floor': False}])
        mids = self.inputs(svc, 1)
        j = svc.wait_job(self.job(svc, mids, {'scale': 2})['id'], all_done, timeout=30)
        it = j['items'][0]
        self.assertEqual((it['state'], it['run']['split'], it['run']['cards']), ('done', False, [0]))
        said = [ln for ln in svc.log_lines() if ln.get('event') == 'split_skipped']
        self.assertEqual(len(said), 1, said)
        self.assertEqual(said[0]['msg'], 'GPU 2 has 14 GB free; sharing an image needs 19 GB, so q0.png runs on one GPU.')
        self.assertEqual(said[0]['data']['under_floor'], [{'gpu': 1, 'vram_free_gb': 14.0}])
        code, logs, _ = svc.get('/api/logs')
        self.assertTrue(any(r.get('event') == 'split_skipped' for r in logs.get('items', logs.get('lines', []))), str(logs)[:400])
        order = [ln['event'] for ln in svc.log_lines() if ln.get('event') in ('split_skipped', 'item_dispatched')]
        self.assertEqual(order, ['split_skipped', 'item_dispatched'])
        self.assertFalse((self.d / 'state' / 'workers' / 'gpu0+1').exists())

        mids2 = self.inputs(svc, 2, start=1)
        j2 = svc.wait_job(self.job(svc, mids2, {'scale': 2})['id'], all_done, timeout=60)
        self.assertEqual([x['state'] for x in j2['items']], ['done', 'done'])
        self.assertEqual(len([ln for ln in svc.log_lines() if ln.get('event') == 'split_skipped']), 1)
        self.assertEqual(svc.shutdown(), 0)

    def test_a_shared_engine_names_both_cards_and_keeps_its_name_when_warm(self):
        svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '0.5', 'CU_FAKE_GPUS': '2', 'CU_SPLIT_TEST': '1'}, settings={})
        for i in range(2):
            mids = self.inputs(svc, 1, start=i)
            j = svc.wait_job(self.job(svc, mids, {'scale': 2})['id'], all_done, timeout=60)
            it = j['items'][0]
            self.assertEqual((it['state'], it['run']['split'], it['run']['cards']), ('done', True, [0, 1]))

            self.assertEqual(it['run']['factor'], 0.523)
        lines = svc.log_lines()
        self.assertEqual([ln['msg'] for ln in lines if ln.get('event') == 'item_dispatched'],
                         ['GPU 1 + GPU 2 started q0.png', 'GPU 1 + GPU 2 started q1.png'])
        starts = [ln for ln in lines if ln.get('event') == 'worker_starting']
        self.assertEqual([(ln['msg'], ln['data']['gpus']) for ln in starts],
                         [('Starting the engine on GPU 1 and GPU 2', [0, 1])])


        ready = [ln for ln in lines if ln.get('event') == 'worker_ready']
        self.assertEqual(len(ready), 1)
        self.assertRegex(ready[0]['msg'], r'^The engine is ready on GPU 1 and GPU 2 \(\d+ s\)$')
        self.assertEqual(ready[0]['data']['gpus'], [0, 1])


        rows = self.health(svc)['engine']['workers']
        self.assertEqual([(w['gpu'], w['state'], w['cards'], w['job_id']) for w in rows],
                         [(0, 'idle', [0, 1], None), (1, 'idle', [0, 1], None)])
        self.assertEqual(rows[0]['pid'], rows[1]['pid'])
        self.assertNotIn('gpus', rows[0])
        self.assertEqual(svc.shutdown(), 0)
        stopped = [ln for ln in svc.log_lines() if ln.get('event') == 'worker_stopped' and ln['data'].get('gpus') == [0, 1]]
        self.assertEqual(len(stopped), 1)
        self.assertTrue(stopped[0]['msg'].startswith('The engine on GPU 1 and GPU 2 stopped ('), stopped[0]['msg'])

    def test_one_card_lines_are_unchanged(self):


        svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '0.3', 'CU_FAKE_GPUS': '1'}, settings={})
        mids = self.inputs(svc, 1)
        svc.wait_job(self.job(svc, mids, {'scale': 2})['id'], all_done, timeout=30)
        lines = svc.log_lines()
        start = next(ln for ln in lines if ln.get('event') == 'worker_starting')
        self.assertEqual((start['msg'], start['data']['gpus']), ('Starting the engine on GPU 1', [0]))
        ready = next(ln for ln in lines if ln.get('event') == 'worker_ready')
        self.assertRegex(ready['msg'], r'^The engine is ready on GPU 1 \(\d+ s\)$')
        self.assertEqual(svc.shutdown(), 0)

    def test_an_image_that_matches_earlier_results_is_shared_too(self):
        svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '0.5', 'CU_FAKE_GPUS': '2'}, settings={})
        code, s, _ = svc.post('/api/settings', {'match_earlier': True})
        self.assertEqual((code, s['match_earlier'], s['split']), (200, True, True))
        h = self.health(svc)
        sp = h['engine']['split']
        self.assertEqual((sp['proven'], sp['available'], sp['setting'], sp['on'], sp['reason'], sp['message']),
                         (True, True, True, True, None, None))
        self.assertTrue(h['engine']['speed']['window_split'])
        mids = self.inputs(svc, 1)
        j = svc.wait_job(self.job(svc, mids, {'scale': 2})['id'], all_done, timeout=60)
        r = j['items'][0]['run']
        self.assertEqual((r['split'], r['cards'], r['match_earlier'], r['speed_stack'], r['factor']),
                         (True, [0, 1], True, False, 0.747))
        side = json.loads(Path(j['items'][0]['sidecar']).read_text(encoding='utf8'))
        self.assertEqual(side['engine']['spot_options'], {'noise_prefetch': True, 'live_preview': 'detailed', 'window_split': True})
        init = next(ln for ln in svc.log_lines() if ln.get('event') == 'runner_init')
        self.assertEqual((init['data']['two_card_proof'], init['data']['split_proven'], init['data']['split_earlier_proven']),
                         (False, True, True))
        self.assertEqual(svc.shutdown(), 0)

    def test_without_its_proof_an_image_that_matches_earlier_results_is_never_shared(self):
        svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '0.5', 'CU_FAKE_GPUS': '2', 'CU_SPLIT_TEST': '1',
                                'CU_SPLIT_EARLIER_TEST': '0'}, settings={})
        code, s, _ = svc.post('/api/settings', {'match_earlier': True})
        self.assertEqual((code, s['match_earlier'], s['split']), (200, True, True))
        h = self.health(svc)
        sp = h['engine']['split']
        self.assertEqual((sp['proven'], sp['available'], sp['setting'], sp['on'], sp['reason'], sp['message']),
                         (True, True, True, False, 'match_earlier', '"Match earlier results" is on, so each image runs on one GPU.'))
        self.assertFalse(h['engine']['speed']['window_split'])
        mids = self.inputs(svc, 1)
        j = svc.wait_job(self.job(svc, mids, {'scale': 2})['id'], all_done, timeout=30)
        r = j['items'][0]['run']
        self.assertEqual((r['split'], r['cards'], r['match_earlier'], r['speed_stack'], r['factor']), (False, [0], True, False, 0.947))
        self.assertFalse((self.d / 'state' / 'workers' / 'gpu0+1').exists())
        self.assertEqual([ln for ln in svc.log_lines() if ln.get('event') == 'split_skipped'], [])
        code, s, _ = svc.post('/api/settings', {'match_earlier': False})
        sp = self.health(svc)['engine']['split']
        self.assertEqual((sp['on'], sp['reason'], sp['message']), (True, None, None))
        self.assertEqual(svc.shutdown(), 0)


        svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '0.5', 'CU_FAKE_GPUS': '2', 'CU_SPLIT_TEST': '1',
                                'CU_SPLIT_EARLIER_TEST': '0'}, settings={}, state='state2')
        mids = self.inputs(svc, 1, start=1)
        j = svc.wait_job(self.job(svc, mids, {'scale': 2})['id'], all_done, timeout=60)
        r = j['items'][0]['run']
        self.assertEqual((r['split'], r['cards'], r['match_earlier'], r['speed_stack']), (True, [0, 1], False, True))
        svc.post('/api/settings', {'match_earlier': True})
        mids = self.inputs(svc, 1, start=2)
        j = svc.wait_job(self.job(svc, mids, {'scale': 2})['id'], all_done, timeout=60)
        r = j['items'][0]['run']
        self.assertEqual((r['split'], len(r['cards']), r['match_earlier']), (False, 1, True))
        seq = [(ln['event'], (ln.get('data') or {}).get('gpus')) for ln in svc.log_lines()
               if ln.get('event') in ('worker_stopped', 'item_dispatched')]
        stop = seq.index(('worker_stopped', [0, 1]))
        self.assertEqual(([e for e, _ in seq[:stop]].count('item_dispatched'),
                          [e for e, _ in seq[stop + 1:]].count('item_dispatched')), (1, 1))
        topo = [ln['msg'] for ln in svc.log_lines() if ln.get('event') == 'topology']
        self.assertEqual(topo[-1], 'Graphics cards: lanes (the next image runs on one card: it matches earlier results)')
        self.assertEqual(svc.shutdown(), 0)


class TwoCardProofSwitch(Base):
    inputs = SplitReadiness.inputs
    health = SplitReadiness.health

    def test_a_stored_split_true_is_ignored_while_not_proven(self):

        (self.d / 'state').mkdir(parents=True, exist_ok=True)
        (self.d / 'state' / 'settings-extra.json').write_text(json.dumps({'split': True, 'match_earlier': False}),
                                                               encoding='utf8')
        svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '0.5', 'CU_FAKE_GPUS': '2', 'CU_SPLIT_TEST': '0',
                                'CU_SPLIT_EARLIER_TEST': '0'}, settings={})
        s = svc.get('/api/settings')[1]
        self.assertEqual((s['split'], s['split_chosen']), (True, True))
        h = self.health(svc)
        sp = h['engine']['split']
        self.assertEqual((sp['proven'], sp['available'], sp['setting'], sp['on'], sp['reason']),
                         (False, False, True, False, 'pending_ws_proof'))
        self.assertFalse(h['features']['split'])
        mids = self.inputs(svc, 1)
        j = svc.wait_job(self.job(svc, mids, {'scale': 2})['id'], all_done, timeout=30)
        self.assertEqual((j['items'][0]['state'], j['items'][0]['run']['split'], j['items'][0]['run']['cards']),
                         ('done', False, [0]))
        self.assertFalse((self.d / 'state' / 'workers' / 'gpu0+1').exists())
        init = next(ln for ln in svc.log_lines() if ln.get('event') == 'runner_init')
        self.assertEqual((init['data']['two_card_proof'], init['data']['split_proven'], init['data']['split_earlier_proven']),
                         (False, False, False))
        self.assertEqual([ln for ln in svc.log_lines() if ln.get('event') == 'two_card_proof_run'], [])
        self.assertEqual(svc.shutdown(), 0)

    @unittest.skip('standalone: the internal two-card proof switch is not part of the Beta (Codex removed it)')
    def test_the_proof_switch_shares_images_in_its_own_process_only(self):
        svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '0.5', 'CU_FAKE_GPUS': '2'}, settings={}, args=['--two-card-proof'])
        lines = svc.log_lines()
        said = [ln for ln in lines if ln.get('event') == 'two_card_proof_run']
        self.assertEqual(len(said), 1)
        self.assertTrue(said[0]['msg'].startswith('Two-card proof run: '), said[0]['msg'])
        init = next(ln for ln in lines if ln.get('event') == 'runner_init')
        self.assertEqual((init['data']['two_card_proof'], init['data']['split_proven'], init['data']['split_earlier_proven']),
                         (True, True, True))
        s = svc.get('/api/settings')[1]
        self.assertEqual((s['split'], s['split_chosen']), (True, False))
        h = self.health(svc)
        sp = h['engine']['split']
        self.assertEqual((sp['proven'], sp['available'], sp['on'], sp['reason']), (True, True, True, None))
        self.assertTrue(h['features']['split'])
        mids = self.inputs(svc, 1)
        j = svc.wait_job(self.job(svc, mids, {'scale': 2})['id'], all_done, timeout=60)
        r = j['items'][0]['run']
        self.assertEqual((j['items'][0]['state'], r['split'], r['cards'], r['speed_stack']), ('done', True, [0, 1], True))

        code, s, _ = svc.post('/api/settings', {'match_earlier': True})
        self.assertEqual(code, 200, s)
        sp = self.health(svc)['engine']['split']
        self.assertEqual((sp['on'], sp['reason'], sp['message']), (True, None, None))
        mids = self.inputs(svc, 1, start=1)
        j = svc.wait_job(self.job(svc, mids, {'scale': 2})['id'], all_done, timeout=60)
        r = j['items'][0]['run']
        self.assertEqual((j['items'][0]['state'], r['split'], r['cards'], r['match_earlier'], r['speed_stack']),
                         ('done', True, [0, 1], True, False))
        side = json.loads(Path(j['items'][0]['sidecar']).read_text(encoding='utf8'))
        self.assertEqual(side['engine']['spot_options'], {'noise_prefetch': True, 'live_preview': 'detailed', 'window_split': True})
        self.assertEqual(svc.shutdown(), 0)


        svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '0.5', 'CU_FAKE_GPUS': '2', 'CU_SPLIT_TEST': '0'}, settings={})
        sp = self.health(svc)['engine']['split']
        self.assertEqual((sp['proven'], sp['on'], sp['reason']), (False, False, 'pending_ws_proof'))
        code, s, _ = svc.post('/api/settings', {'match_earlier': False})
        mids = self.inputs(svc, 1, start=2)
        j = svc.wait_job(self.job(svc, mids, {'scale': 2})['id'], all_done, timeout=30)
        self.assertEqual((j['items'][0]['run']['split'], j['items'][0]['run']['cards']), (False, [0]))
        self.assertEqual(svc.shutdown(), 0)

    @unittest.skip('standalone: the internal two-card proof switch is not part of the Beta (Codex removed it)')
    def test_the_installed_products_folders_refuse_it_and_no_file_turns_it_on(self):
        pass
