import io
import json
import time
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from tests.service.helpers import gradient
from tests.service.test_integration import Base, all_done


def wait(pred, timeout=30.0, interval=0.05):
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        v = pred()
        if v:
            return v
        time.sleep(interval)
    raise AssertionError('timed out')


class V4Base(Base):
    def inputs(self, n=2, size=(96, 72), alpha=False):
        d = self.d / 'in'
        d.mkdir(parents=True, exist_ok=True)
        paths = []
        for i in range(n):
            a = gradient(size[0], size[1], i)
            if alpha:
                a = np.dstack([a, np.tile(np.linspace(0, 255, size[0]).astype(np.uint8), (size[1], 1))])
            p = d / f'pic{i}.png'
            Image.fromarray(a).save(p)
            paths.append(p)
        return [it['id'] for it in self.add(self.svc, paths)['items']]

    def live(self):
        code, res, _ = self.svc.get('/api/live')
        self.assertEqual(code, 200, res)
        return res

    def item(self, jid, iid):
        code, job, _ = self.svc.get(f'/api/jobs/{jid}')
        return next(x for x in job['items'] if x['id'] == iid)


class LivePreview(V4Base):
    def test_detailed_frames_reach_the_api(self):
        self.svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '3'})
        mids = self.inputs(1)
        job = self.job(self.svc, mids, {'scale': 2})
        jid = job['id']
        snap = wait(lambda: next((x for x in self.live()['items'] if x['job_id'] == jid and x['state'] == 'sampling'
                                  and x['rects'] and x['canvas_url']), None))
        self.assertEqual(snap['preview'], 'detailed')
        self.assertEqual(snap['card'], 0)
        self.assertEqual(snap['passes'], 2)
        self.assertIn(snap['pass'], ('structure', 'detail'))
        self.assertEqual(snap['frame'], job['items'][0]['plan']['output_size'])
        r = snap['rects'][0]
        self.assertTrue(0 <= r['x'] < 1 and 0 <= r['y'] < 1 and 0 < r['w'] <= 1 and 0 < r['h'] <= 1, r)
        self.assertEqual(r['card'], 0)
        code, jpg, hdr = self.svc.get(snap['canvas_url'], raw=True)
        self.assertEqual(code, 200)
        self.assertEqual(hdr.get('Content-Type'), 'image/jpeg')
        self.assertEqual(hdr.get('Cache-Control'), 'no-store')
        im = Image.open(io.BytesIO(jpg))
        self.assertEqual(list(im.size), snap['canvas_size'])
        ow, oh = snap['frame']
        self.assertAlmostEqual(im.size[0] / im.size[1], ow / oh, places=1)
        code, th, _ = self.svc.get(snap['thumb_url'], raw=True)
        self.assertEqual(code, 200)
        self.assertLessEqual(max(Image.open(io.BytesIO(th)).size), 256)
        code, one, _ = self.svc.get(f'/api/jobs/{jid}/items/i001/live')
        self.assertEqual(code, 200)
        self.assertEqual(one['item_id'], 'i001')

        later = wait(lambda: next((x for x in self.live()['items'] if x['job_id'] == jid and x['step'] >= 3), None))
        self.assertEqual(later['steps'], 5)
        self.assertIsNotNone(later['timing']['tile_s'])
        self.assertIsNotNone(later['timing']['last_tile_age_s'])
        self.assertEqual(self.live()['detailed'], {'available': True, 'on': True, 'reason': None})
        j = self.svc.wait_job(jid, all_done, timeout=60)
        self.assertEqual(j['items'][0]['state'], 'done')
        self.assertFalse([x for x in self.live()['items'] if x['job_id'] == jid])


        code, last, hdr = self.svc.get(f'/api/jobs/{jid}/items/i001/live.jpg?seq=1', raw=True)
        self.assertEqual((code, hdr.get('Content-Type')), (200, 'image/jpeg'))
        code, _, _ = self.svc.get(f'/api/jobs/{jid}/items/i001/live-thumb.jpg?seq=1', raw=True)
        self.assertEqual(code, 200)
        code, err = wait(lambda: (lambda r: (r[0], json.loads(r[1])) if r[0] == 404 else None)(
            self.svc.get(f'/api/jobs/{jid}/items/i001/live.jpg', raw=True)), timeout=15)
        self.assertEqual((code, err['error']['code']), (404, 'no_live'))
        side = json.loads(Path(j['items'][0]['sidecar']).read_text(encoding='utf8'))

        self.assertEqual(side['engine']['spot_options'], {'noise_prefetch': True, 'pag_fuse': True, 'batch_windows': 2,
                                                          'fp16_acc_scoped': True, 'live_preview': 'detailed'})
        self.assertEqual(self.svc.shutdown(), 0)

    def test_rough_when_settings_turn_detailed_off(self):
        self.svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '2'})
        code, s, _ = self.svc.post('/api/settings', {'detailed_preview': False})
        self.assertEqual((code, s['detailed_preview']), (200, False))
        mids = self.inputs(1)
        jid = self.job(self.svc, mids, {'scale': 2})['id']
        snap = wait(lambda: next((x for x in self.live()['items'] if x['job_id'] == jid and x['canvas_url']), None))
        self.assertEqual(snap['preview'], 'rough')
        self.assertEqual(self.live()['detailed'], {'available': True, 'on': False, 'reason': 'turned_off'})
        sent = json.loads(next((self.d / 'state/workers/gpu0/fake-prompts').glob(f'cu_{jid}_i001_s0.json')).read_text())
        spot = next(v for v in sent.values() if v['class_type'] == 'ClaudeSpotTiles')
        self.assertEqual(spot['inputs']['live_preview'], 'rough')
        self.svc.wait_job(jid, all_done, timeout=60)
        self.assertEqual(self.svc.shutdown(), 0)


class StopAndQueueAgain(V4Base):
    def test_stop_this_image_the_queue_goes_on_then_queue_again_with_new_settings(self):
        self.svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '3'})
        mids = self.inputs(3)
        job = self.job(self.svc, mids, {'scale': 2})
        jid = job['id']
        self.assertEqual([it['queue_rank'] for it in job['items']], [1, 2, 3])
        wait(lambda: next((x for x in self.live()['items'] if x['item_id'] == 'i001' and x['step'] >= 2), None))
        code, res, _ = self.svc.post(f'/api/cancel?image={mids[0]}')
        self.assertEqual(code, 200, res)
        self.assertEqual(res['stopped']['item_id'], 'i001')
        it = wait(lambda: (lambda x: x if x['state'] == 'stopped' else None)(self.item(jid, 'i001')))
        self.assertEqual(it['ran_with']['scale'], 2)
        self.assertIn(it['at']['pass'], ('structure', 'detail'))
        self.assertGreaterEqual(it['at']['step'], 2)
        self.assertEqual(it['gpu'], None)

        wait(lambda: self.item(jid, 'i002')['state'] in ('preparing', 'running', 'finishing', 'done'), timeout=10)
        frozen = next(x for x in self.live()['items'] if x['item_id'] == 'i001')
        self.assertEqual((frozen['state'], frozen['rects']), ('stopped', []))
        self.assertEqual(self.svc.get(frozen['canvas_url'], raw=True)[0], 200)

        code, res, _ = self.svc.post('/api/items/settings', {'items': [{'job_id': jid, 'item_id': 'i001'},
                                                                        {'job_id': jid, 'item_id': 'i002'},
                                                                        {'job_id': jid, 'item_id': 'i003'}],
                                                              'settings': {'scale': 4, 'preset': 'Strong'}})
        self.assertEqual(code, 200, res)
        self.assertEqual(sorted(a['item_id'] for a in res['applied']), ['i001', 'i003'])
        self.assertEqual([(r['item_id'], r['code']) for r in res['refused']], [('i002', 'started')])
        it1 = self.item(jid, 'i001')
        self.assertTrue(it1['settings_changed'])
        self.assertEqual((it1['effective']['scale'], it1['effective']['preset']), (4, 'Strong'))

        code, j, _ = self.svc.post(f'/api/jobs/{jid}/items/i001/requeue', {})
        self.assertEqual(code, 200, j)
        it1 = next(x for x in j['items'] if x['id'] == 'i001')
        self.assertEqual((it1['state'], it1['queue_rank'], it1['effective']['scale'], len(it1['plan']['stages'])),
                         ('queued', 1, 4, 2))
        self.assertEqual(next(x for x in j['items'] if x['id'] == 'i003')['queue_rank'], 2)
        self.assertFalse([x for x in self.live()['items'] if x['item_id'] == 'i001'])
        j = self.svc.wait_job(jid, all_done, timeout=120)
        self.assertEqual([x['state'] for x in j['items']], ['done'] * 3)
        names = [x['output'].replace('\\', '/').rsplit('/', 1)[-1] for x in j['items']]
        self.assertTrue(names[0].startswith('pic0_cu4x'), names)
        self.assertTrue(names[1].startswith('pic1_cu2x'), names)
        self.assertTrue(names[2].startswith('pic2_cu4x'), names)
        side = json.loads(Path(j['items'][0]['sidecar']).read_text(encoding='utf8'))
        self.assertEqual((side['effective']['scale'], side['effective']['preset']), (4, 'Strong'))

        starts = [ln for ln in self.svc.log_lines() if ln.get('event') == 'item_dispatched']
        self.assertEqual([ln['item'] for ln in starts], ['i001', 'i002', 'i001', 'i003'])
        events = {ln['event'] for ln in self.svc.log_lines()}
        self.assertTrue({'stop_requested', 'item_stopped', 'item_settings_changed', 'item_requeued_by_user'} <= events)
        self.assertEqual(self.svc.shutdown(), 0)

    def test_queue_again_as_before_keeps_finished_passes(self):
        self.svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '2'})
        mids = self.inputs(1)
        jid = self.job(self.svc, mids, {'scale': 4})['id']
        wait(lambda: next((x for x in self.live()['items'] if x['item_id'] == 'i001' and x['stage'] == 1 and x['step'] >= 1),
                          None), timeout=40)
        code, res, _ = self.svc.post(f'/api/jobs/{jid}/items/i001/stop')
        self.assertEqual(code, 200, res)
        it = wait(lambda: (lambda x: x if x['state'] == 'stopped' else None)(self.item(jid, 'i001')))
        self.assertEqual(it['at']['stage'], 1)
        self.assertFalse(it['settings_changed'])
        code, j, _ = self.svc.post(f'/api/jobs/{jid}/items/i001/requeue', {})
        self.assertEqual(code, 200, j)
        self.assertEqual(j['items'][0]['stage_index'], 1)
        j = self.svc.wait_job(jid, all_done, timeout=60)
        self.assertEqual(j['items'][0]['state'], 'done')
        stage0 = [r for r in self.svc.renders() if r['prefix'].endswith('_s0') and r['status'] == 'success']
        self.assertEqual(len(stage0), 1)
        self.assertEqual(self.svc.shutdown(), 0)

    def test_stop_refusals_and_waiting_images(self):
        self.svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '3'})
        mids = self.inputs(2)
        jid = self.job(self.svc, mids, {'scale': 2})['id']
        code, res, _ = self.svc.post(f'/api/cancel?image={mids[1]}')
        self.assertEqual(code, 200, res)
        self.assertEqual(self.item(jid, 'i002')['state'], 'stopped')
        code, res, _ = self.svc.post(f'/api/cancel?image={mids[1]}')
        self.assertEqual((code, res['error']['code']), (404, 'unknown_image'))
        code, res, _ = self.svc.post('/api/cancel')
        self.assertEqual(code, 400)
        code, res, _ = self.svc.post(f'/api/jobs/{jid}/items/i002/requeue', {'settings': {'scale': 8, 'creativity': 'x'}})
        self.assertEqual((code, res['error']['code']), (400, 'bad_settings'))
        code, res, _ = self.svc.post(f'/api/jobs/{jid}/items/i001/requeue', {})
        self.assertEqual((code, res['error']['code']), (409, 'not_requeueable'))
        j = self.svc.wait_job(jid, lambda j: j['items'][0]['state'] == 'done', timeout=60)
        self.assertEqual(j['state'], 'stopped')
        self.assertEqual(j['summary']['counts'], {'done': 1, 'stopped': 1})
        code, j, _ = self.svc.post(f'/api/jobs/{jid}/cancel')
        self.assertEqual(next(x for x in j['items'] if x['id'] == 'i002')['state'], 'cancelled')
        self.assertEqual(self.svc.shutdown(), 0)

    def test_queue_again_as_before_after_the_settings_changed(self):
        self.svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '4'})
        mids = self.inputs(2)
        jid = self.job(self.svc, mids, {'scale': 2, 'preset': 'Default'})['id']
        self.assertEqual(self.svc.post(f'/api/cancel?image={mids[1]}')[0], 200)
        it = self.item(jid, 'i002')
        self.assertEqual((it['ran_with']['preset'], it['ran_with_request']), ('Default', {'scale': 2, 'preset': 'Default'}))
        code, res, _ = self.svc.post('/api/items/settings', {'items': [{'job_id': jid, 'item_id': 'i002'}],
                                                              'settings': {'scale': 4, 'preset': 'Strong'}})
        self.assertEqual([a['item_id'] for a in res['applied']], ['i002'])
        self.assertTrue(self.item(jid, 'i002')['settings_changed'])
        code, res, _ = self.svc.post(f'/api/jobs/{jid}/items/i002/requeue', {'as_before': True, 'settings': {'scale': 2}})
        self.assertEqual(code, 400)
        code, j, _ = self.svc.post(f'/api/jobs/{jid}/items/i002/requeue', {'as_before': True})
        self.assertEqual(code, 200, j)
        it = next(x for x in j['items'] if x['id'] == 'i002')
        self.assertEqual((it['state'], it['effective']['scale'], it['effective']['preset'], len(it['plan']['stages'])),
                         ('queued', 2, 'Default', 1))
        self.svc.post(f'/api/jobs/{jid}/cancel')
        self.assertEqual(self.svc.shutdown(), 0)

    def test_plan_refused_for_one_waiting_image(self):
        self.svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '5'})
        big = self.d / 'in' / 'big.png'
        big.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(gradient(2000, 1500, 4)).save(big)
        small = self.inputs(2)
        mid_big = self.add(self.svc, [big])['items'][0]['id']
        jid = self.job(self.svc, small + [mid_big], {'scale': 2})['id']
        code, res, _ = self.svc.post('/api/items/settings', {'items': [{'job_id': jid, 'item_id': 'i002'},
                                                                        {'job_id': jid, 'item_id': 'i003'}],
                                                              'settings': {'scale': 8}})
        self.assertEqual(code, 200, res)
        self.assertEqual([a['item_id'] for a in res['applied']], ['i002'])
        self.assertEqual([(r['item_id'], r['code']) for r in res['refused']], [('i003', 'plan_refused')])
        self.assertIn('8×', res['refused'][0]['reason'])
        self.svc.post(f'/api/jobs/{jid}/cancel')
        self.assertEqual(self.svc.shutdown(), 0)


class Transparency(V4Base):
    def test_said_before_the_run_and_kept(self):
        self.svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '0.3'})
        mid = self.inputs(1, alpha=True)[0]
        code, p, _ = self.svc.post('/api/plan', {'width': 96, 'height': 72, 'scale': 2, 'media_id': mid})
        self.assertEqual((code, p['transparency']), (200, 'kept'))
        code, p, _ = self.svc.post('/api/plan', {'width': 96, 'height': 72, 'scale': 2, 'alpha': True, 'output_format': 'jpeg'})
        self.assertEqual((p['transparency'], p['transparency_reason']), ('not_kept', 'jpeg'))
        code, p, _ = self.svc.post('/api/plan', {'width': 96, 'height': 72, 'scale': 2, 'alpha': False})
        self.assertEqual(p['transparency'], 'none')
        j = self.job(self.svc, [mid], {'scale': 2})
        self.assertEqual(j['items'][0]['transparency'], 'kept')
        j = self.svc.wait_job(j['id'], all_done, timeout=30)
        with Image.open(j['items'][0]['output']) as im:
            self.assertEqual(im.mode, 'RGBA')
            a = np.asarray(im.getchannel('A'))
        want = np.asarray(Image.fromarray(np.tile(np.linspace(0, 255, 96).astype(np.uint8), (72, 1))).resize((192, 144),
                                                                                                            Image.LANCZOS))
        self.assertLessEqual(int(np.abs(a.astype(int) - want.astype(int)).max()), 1)
        jj = self.job(self.svc, [mid], {'scale': 2, 'output_format': 'jpeg'})
        self.assertEqual(jj['items'][0]['transparency'], 'not_kept')
        self.svc.wait_job(jj['id'], all_done, timeout=30)
        self.assertEqual(self.svc.shutdown(), 0)


class Notification(V4Base):
    def records(self):
        p = self.d / 'state' / 'notifications.jsonl'
        return [json.loads(x) for x in p.read_text(encoding='utf8').splitlines()] if p.exists() else []

    def test_finish_in_the_background_notifies_the_end_and_a_failure(self):
        self.svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '1.5', 'CU_FAKE_FAULT': 'fail@i002_s0'})
        mids = self.inputs(3)
        jid = self.job(self.svc, mids, {'scale': 2})['id']
        wait(lambda: self.item(jid, 'i001')['state'] == 'running')
        code, res, _ = self.svc.post('/api/lifecycle/close', {'choice': 'finish'})
        self.assertEqual(code, 200, res)
        code, h, _ = self.svc.get('/health')
        self.assertTrue(h['lifecycle']['in_background'])
        self.assertTrue(h['lifecycle']['notify']['available'])
        j = self.svc.wait_job(jid, all_done, timeout=60)
        self.assertEqual([x['state'] for x in j['items']], ['done', 'failed', 'done'])
        recs = wait(lambda: (lambda r: r if len(r) >= 2 else None)(self.records()), timeout=10)
        self.assertEqual([(r['kind'], r['title']) for r in recs], [('image_failed', 'Artegra Enhancer'),
                                                                   ('batch_end', 'Artegra Enhancer')])
        self.assertEqual(recs[0]['body'], '1 image failed. The rest carried on.')
        self.assertTrue(recs[1]['body'].startswith('2 images upscaled in ') and recs[1]['body'].endswith('. 1 failed.'),
                        recs[1]['body'])
        self.assertTrue(all(r['dry_run'] and not r['shown'] for r in recs))
        failed = next(x for x in j['items'] if x['id'] == 'i002')
        self.assertTrue(failed['at'] and failed['ran_with'])
        self.assertEqual(self.svc.shutdown(), 0)

    def test_nothing_while_the_window_is_open_or_when_turned_off(self):
        self.svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '0.3'})
        mids = self.inputs(1)
        self.svc.wait_job(self.job(self.svc, mids, {'scale': 2})['id'], all_done, timeout=30)
        time.sleep(1.0)
        self.assertEqual(self.records(), [])
        code, s, _ = self.svc.post('/api/settings', {'notify': False})
        self.assertEqual(s['notify'], False)
        self.svc.post('/api/lifecycle/close', {'choice': 'finish'})
        self.svc.wait_job(self.job(self.svc, mids, {'scale': 2})['id'], all_done, timeout=30)
        time.sleep(1.0)
        self.assertEqual(self.records(), [])
        self.assertEqual(self.svc.shutdown(), 0)


class SleepAndSettings(V4Base):
    def test_sleep_held_while_a_batch_runs(self):
        self.svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '2'})
        mids = self.inputs(1)
        jid = self.job(self.svc, mids, {'scale': 2})['id']
        wait(lambda: self.svc.get('/health')[1]['engine']['sleep_held'])
        self.svc.wait_job(jid, all_done, timeout=30)
        wait(lambda: not self.svc.get('/health')[1]['engine']['sleep_held'])
        events = [ln['event'] for ln in self.svc.log_lines() if ln['event'] in ('sleep_held', 'sleep_released')]
        self.assertEqual(events[:2], ['sleep_held', 'sleep_released'])
        self.assertEqual(self.svc.shutdown(), 0)

    def test_settings_extra_and_health(self):
        self.svc = self.service()
        code, s, _ = self.svc.get('/api/settings')


        self.assertEqual((s['detailed_preview'], s['notify'], s['hold_sleep'], s['match_earlier']), (True, True, True, False))
        self.assertNotIn('speed', s)
        code, s, _ = self.svc.post('/api/settings', {'hold_sleep': False})
        self.assertEqual(code, 200, s)
        self.assertEqual(s['hold_sleep'], False)
        code, e, _ = self.svc.post('/api/settings', {'speed': {'pag_fuse': True}})
        self.assertEqual(code, 400)
        code, e, _ = self.svc.post('/api/settings', {'notify': 'yes'})
        self.assertEqual(code, 400)
        on_disk = json.loads((self.d / 'state' / 'settings.json').read_text(encoding='utf8'))
        self.assertNotIn('hold_sleep', on_disk)
        extra = json.loads((self.d / 'state' / 'settings-extra.json').read_text(encoding='utf8'))
        self.assertEqual(extra['hold_sleep'], False)
        code, h, _ = self.svc.get('/health')

        self.assertTrue(h['features']['live'] and h['features']['stop_image'] and h['features']['split'])


        sp = h['engine']['split']
        self.assertEqual({k: sp[k] for k in ('available', 'on', 'reason', 'topology', 'proven', 'message')},
                         {'available': False, 'on': False, 'reason': 'one_card', 'topology': None, 'proven': True,
                          'message': 'One GPU is in use, so each image runs on it.'})
        self.assertEqual(h['engine']['speed']['noise_prefetch'], True)
        self.assertEqual((h['engine']['speed']['pag_fuse'], h['engine']['speed']['batch_windows']), (True, 2))
        w = h['engine']['workers'][0]
        self.assertEqual((w['job_id'], w['item_id'], w['media_id'], w['cards']), (None, None, None, [0]))
        self.assertEqual(self.svc.shutdown(), 0)

        svc2 = self.service()
        self.assertEqual(svc2.get('/api/settings')[1]['hold_sleep'], False)
        self.assertEqual(svc2.shutdown(), 0)


if __name__ == '__main__':
    unittest.main()
