import http.client
import json
import os
import secrets
import socket
import subprocess
import sys
import time
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from engine import controls, graph_v5t
from service import images, runner
from service.media import LIGHTER_FOR_MEMORY
from tests.service.helpers import REPO, ServiceProcess, gradient, read_tiff16, rmtree, tmpdir

DONE = ('done', 'failed', 'cancelled')


def rid():
    return secrets.token_hex(16)


def make_inputs(d):
    d.mkdir(parents=True, exist_ok=True)
    ex = Image.Exif()
    ex[0x0112] = 6
    ex[271] = 'IntegrationCam'
    Image.fromarray(gradient(96, 80, 1)).save(d / 'a.jpg', 'JPEG', quality=95, exif=ex.tobytes())
    alpha = np.tile(np.linspace(0, 255, 101).astype(np.uint8), (67, 1))
    Image.fromarray(np.dstack([gradient(101, 67, 2), alpha])).save(d / 'b.png')
    images.write_tiff16(d / 'c.tif', gradient(120, 90, 3).astype(np.uint16) * 257)
    return [d / 'a.jpg', d / 'b.png', d / 'c.tif']


def all_done(job):
    return job['state'] in DONE and all(it['state'] in DONE for it in job['items'])


class Base(unittest.TestCase):
    env = {}

    def setUp(self):
        self.d = tmpdir('cu-int-')
        self.out = self.d / 'out'
        self.svcs = []

    def tearDown(self):
        for s in self.svcs:
            s.kill()
        rmtree(self.d)

    def service(self, env=None, state='state', **kw):
        kw.setdefault('output_dir', self.out)


        pin = {} if 'gpus' in (kw.get('settings') or {}) else {'CU_FAKE_GPUS': '1'}
        s = ServiceProcess(self.d / state, env={**pin, **self.env, **(env or {})}, **kw)
        self.svcs.append(s)
        return s.start()

    def add(self, svc, paths):
        code, res, _ = svc.post('/api/inputs', {'paths': [str(p) for p in paths]})
        self.assertEqual(code, 200, res)
        return res

    def job(self, svc, mids, settings=None, expect=201, request_id=None, **extra):
        body = dict({'client_request_id': request_id or rid(), 'media_ids': mids, 'settings': settings or {}}, **extra)
        code, job, _ = svc.post('/api/jobs', body)
        self.assertEqual(code, expect, job)
        return job


class Batches(Base):
    def test_batch_of_three_at_2x_and_4x(self):
        svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '0.3'})
        res = self.add(svc, make_inputs(self.d / 'in'))
        self.assertEqual(res['rejected'], [])
        items = res['items']
        self.assertEqual([(i['width'], i['height'], i['alpha']) for i in items],
                         [(80, 96, False), (101, 67, True), (120, 90, False)])
        self.assertEqual(items[2]['bit_depth'], 16)
        self.assertTrue(items[0]['scales']['2']['ok'])
        mids = [i['id'] for i in items]
        j2 = self.job(svc, mids, {'preset': 'Default', 'scale': 2})
        self.assertEqual([it['state'] for it in j2['items']], ['queued'] * 3)
        j4 = self.job(svc, mids, {'preset': 'Strong', 'scale': 4, 'output_format': 'tiff16', 'seed': '42'})
        first = svc.wait_job(j2['id'], lambda j: j['items'][0]['state'] == 'done', timeout=90)['items'][0]
        self.assertTrue(first['result_ready'])
        code, _, _ = svc.get(first['result_proxy_url'], raw=True)
        self.assertEqual(code, 200)
        j2 = svc.wait_job(j2['id'], all_done, timeout=90)
        j4 = svc.wait_job(j4['id'], all_done, timeout=120)
        self.assertEqual([it['state'] for it in j2['items'] + j4['items']], ['done'] * 6, json.dumps(j2)[:2000])
        self.assertEqual((j2['state'], j4['state']), ('done', 'done'))
        self.assertEqual(j2['summary']['progress'], 1.0)

        for it, (w, h) in zip(j2['items'], [(80, 96), (101, 67), (120, 90)]):
            out = Path(it['output'])
            self.assertEqual(out.parent, self.out)
            self.assertEqual(out.name, Path(it['name']).stem + '_cu2x.png')
            with Image.open(out) as im:
                self.assertEqual(im.size, (2 * w, 2 * h))
                self.assertEqual(im.mode, 'RGBA' if it['alpha'] else 'RGB')
                self.assertEqual(im.info.get('icc_profile'), images.srgb_icc_bytes())
            side = json.loads(Path(it['sidecar']).read_text(encoding='utf8'))
            self.assertEqual(side['output']['sha256'], images_sha(out))
            self.assertEqual(side['input_sha256'], it['sha256'])
            self.assertEqual((side['job'], side['item'], side['seed']), (j2['id'], it['id'], '20261102'))
            self.assertEqual(side['effective']['preset'], 'Default')
            self.assertEqual(len(side['node_pack']['sha256']), 64)
            self.assertEqual(len(side['plan']['stages']), 1)
        with Image.open(j2['items'][0]['output']) as im:
            self.assertEqual(im.getexif().get(271), 'IntegrationCam')
            self.assertNotIn(0x0112, im.getexif())
        with Image.open(j2['items'][1]['output']) as im:
            a = np.asarray(im)[..., 3]
            self.assertLess(a[:, :10].mean(), 30)
            self.assertGreater(a[:, -10:].mean(), 225)

        for it, (w, h) in zip(j4['items'], [(80, 96), (101, 67), (120, 90)]):
            arr, tags = read_tiff16(it['output'])
            self.assertEqual(arr.shape[:2], (4 * h, 4 * w))
            self.assertEqual(arr.shape[2], 4 if it['alpha'] else 3)
            self.assertTrue(np.all(arr % 257 == 0))
            side = json.loads(Path(it['sidecar']).read_text(encoding='utf8'))
            self.assertEqual(side['stage_seeds'], ['42', '43'])
            self.assertEqual(side['output']['bytes'], Path(it['output']).stat().st_size)
            self.assertEqual(len(it['timings']['stages']), 2)
            self.assertEqual((it['stage'], it['stages'], it['stages_done'], it['stage_index']), (1, 2, 2, 2))
            self.assertEqual((it['thumb_url'], it['proxy_url']), (f'/api/media/{it["media_id"]}/thumb',
                                                                  f'/api/media/{it["media_id"]}/proxy'))
        renders = svc.renders()
        self.assertEqual(sorted(r['stage'] for r in renders if r['status'] == 'success'), [0] * 6 + [1] * 3)

        self.assertFalse(any((self.d / 'state' / 'work').iterdir()))
        self.assertEqual(list((self.d / 'state' / 'workers' / 'gpu0' / 'input').iterdir()), [])

        mid = mids[1]
        code, data, hdr = svc.get(f'/api/media/{mid}/proxy?kind=result', raw=True)
        self.assertEqual((code, hdr['Content-Type']), (200, 'image/png'))
        code, data, hdr = svc.get(f'/api/media/{mid}/region?x=10&y=10&w=64&h=32&kind=result', raw=True)
        self.assertEqual(code, 200)
        self.assertEqual(hdr['X-Image-Size'], '404,268')
        code, data, hdr = svc.get(f'/api/media/{mid}/region?x=0&y=0&w=20&h=20&kind=source', raw=True)
        self.assertEqual((code, hdr['X-Region']), (200, '0,0,20,20'))
        code, data, _ = svc.get(f'/api/media/{mid}/thumb', raw=True)
        self.assertEqual(code, 200)
        urls = j2['items'][1]['result_urls']
        code, data, hdr = svc.get(urls['region'] + '&x=0&y=0&w=8&h=8', raw=True)
        self.assertEqual((code, hdr['X-Image-Size']), (200, '202,134'))
        code, data, hdr = svc.get(urls['proxy'], raw=True)
        self.assertEqual(code, 200)

        j2b = self.job(svc, [mids[0]], {'scale': 2})
        j2b = svc.wait_job(j2b['id'], all_done, timeout=60)
        self.assertEqual(Path(j2b['items'][0]['output']).name, 'a_cu2x_2.png')

        code, logs, _ = svc.get(f'/api/logs?job={j4["id"]}&limit=500')
        events = [l['event'] for l in logs['lines']]
        for ev in ('job_created', 'item_dispatched', 'stage_start', 'stage_done', 'item_done'):
            self.assertIn(ev, events)
        self.assertNotIn('prompt_queued', events)
        msgs = [l['msg'] for l in logs['lines']]
        self.assertIn('Started 3 images', msgs)
        self.assertIn('Pass 2 of 2 started', msgs)
        self.assertTrue(any(m.startswith('GPU 1 started ') for m in msgs), msgs)
        code, logs, _ = svc.get(f'/api/logs?job={j4["id"]}&limit=500&all=1')
        self.assertIn('prompt_queued', [l['event'] for l in logs['lines']])
        code, h, _ = svc.get('/health')
        self.assertEqual(h['engine']['workers'][0]['state'], 'idle')
        self.assertTrue(h['checked_at'])
        code, res, _ = svc.post('/api/open', {'path': j2['items'][0]['output']})
        self.assertEqual((code, res['how'], res['dryrun']), (200, 'select', True))
        code, res, _ = svc.post('/api/open', {'path': str(self.out)})
        self.assertEqual((code, res['how']), (200, 'folder'))
        code, res, _ = svc.post('/api/open', {'path': str(self.d / 'in' / 'a.jpg')})
        self.assertEqual(code, 403)
        self.assertIn('log_ref', res['error'])
        self.assertEqual(svc.shutdown(), 0)


def images_sha(p):
    from service.util import sha256_file
    return sha256_file(p)


class Transparency(Base):

    def get_image(self, svc, url):
        import io
        code, data, hdr = svc.get(url, raw=True)
        self.assertEqual(code, 200, (url, data[:300]))
        with Image.open(io.BytesIO(data)) as im:
            im.load()
            return hdr['Content-Type'], im.format, im.copy()

    def assert_band(self, im, band_rows, opaque_from, what):
        a = np.asarray(im.getchannel('A'))
        self.assertEqual(a[:band_rows].max(), 0, what)
        self.assertEqual(a[opaque_from:].min(), 255, what)

    def test_alpha_is_served_and_old_records_still_work(self):
        svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '0.2'})
        inp = self.d / 'in'
        inp.mkdir(parents=True)
        rgb = gradient(960, 600, 6)
        alpha = np.full((600, 960), 255, np.uint8)
        alpha[:60] = 0
        Image.fromarray(np.dstack([rgb, alpha])).save(inp / 'band_alpha.png')
        Image.fromarray(gradient(640, 480, 7)).save(inp / 'opaque.jpg', 'JPEG', quality=92)
        res = self.add(svc, [inp / 'band_alpha.png', inp / 'opaque.jpg'])
        band, opaque = res['items']
        self.assertEqual((band['alpha'], opaque['alpha']), (True, False))
        mb, mo = band['id'], opaque['id']
        for kind, size in (('thumb', (320, 200)), ('proxy', (960, 600))):
            ctype, fmt, im = self.get_image(svc, band[f'{kind}_url'])
            self.assertEqual((ctype, fmt, im.mode, im.size), ('image/png', 'PNG', 'RGBA', size), kind)
            self.assert_band(im, size[1] // 10 - 5, size[1] // 10 + 6, kind)
            ctype, fmt, im = self.get_image(svc, opaque[f'{kind}_url'])
            self.assertEqual((ctype, fmt, im.mode), ('image/jpeg', 'JPEG', 'RGB'), kind)
        ctype, _, im = self.get_image(svc, f'/api/media/{mb}/region?kind=source&x=100&y=0&w=200&h=150')
        self.assertEqual((ctype, im.mode, im.size), ('image/png', 'RGBA', (200, 150)))
        self.assert_band(im, 60, 60, 'source region')
        self.assertTrue(np.array_equal(np.asarray(im)[..., :3], rgb[:150, 100:300]))
        ctype, _, im = self.get_image(svc, f'/api/media/{mo}/region?kind=source&x=0&y=0&w=64&h=64')
        self.assertEqual((ctype, im.mode), ('image/png', 'RGB'))

        code, m, _ = svc.post('/api/mask-preview', {'media_id': mb, 'protect': []})
        self.assertEqual(code, 200, m)
        code, _, hdr = svc.get(m['mask_url'], raw=True)
        self.assertEqual((code, hdr['Content-Type']), (200, 'image/png'))

        (inp / 'band_alpha_copy.png').write_bytes((inp / 'band_alpha.png').read_bytes())
        dup = self.add(svc, [inp / 'band_alpha_copy.png'])['items'][0]
        self.assertTrue(dup['duplicate'])
        self.assertEqual(self.get_image(svc, dup['proxy_url'])[0], 'image/png')

        job = svc.wait_job(self.job(svc, [mb, mo], {'scale': 4})['id'], all_done, timeout=120)
        self.assertEqual([it['state'] for it in job['items']], ['done', 'done'], json.dumps(job)[:2000])
        it_b, it_o = job['items']
        rdir = self.d / 'state' / 'media' / 'results' / f'{job["id"]}_{it_b["id"]}'
        self.assertEqual(sorted(p.name for p in rdir.iterdir()), ['proxy.png', 'thumb.png', 'view-alpha.png', 'view.jpg'])
        odir = self.d / 'state' / 'media' / 'results' / f'{job["id"]}_{it_o["id"]}'
        self.assertEqual(sorted(p.name for p in odir.iterdir()), ['proxy.jpg', 'thumb.jpg', 'view.jpg'])
        for kind, size in (('thumb', (320, 200)), ('proxy', (2048, 1280))):
            ctype, fmt, im = self.get_image(svc, it_b['result_urls'][kind])
            self.assertEqual((ctype, im.mode, im.size), ('image/png', 'RGBA', size), kind)
            self.assert_band(im, size[1] // 10 - 5, size[1] // 10 + 6, 'result ' + kind)
            ctype, fmt, im = self.get_image(svc, it_o['result_urls'][kind])
            self.assertEqual((ctype, im.mode), ('image/jpeg', 'RGB'), kind)
        ctype, _, im = self.get_image(svc, it_b['result_urls']['region'] + '&x=500&y=0&w=300&h=400')
        self.assertEqual((ctype, im.mode, im.size), ('image/png', 'RGBA', (300, 400)))
        self.assert_band(im, 230, 250, 'result region')
        ctype, _, im = self.get_image(svc, it_o['result_urls']['region'] + '&x=0&y=0&w=64&h=64')
        self.assertEqual((ctype, im.mode), ('image/png', 'RGB'))

        with Image.open(it_b['output']) as out:
            self.assertEqual((out.mode, out.size), ('RGBA', (3840, 2400)))
        side = json.loads(Path(it_b['sidecar']).read_text(encoding='utf8'))
        self.assertEqual(side['output']['sha256'], images_sha(it_b['output']))


        for n in ('thumb.png', 'proxy.png'):
            (self.d / 'state' / 'media' / mb / n).unlink()
        for n in ('proxy.png', 'thumb.png', 'view-alpha.png'):
            (rdir / n).unlink()
        flat = Image.new('RGB', (3840, 2400), (38, 38, 38))
        flat.save(rdir / 'view.jpg', 'JPEG', quality=95)
        flat.resize((2048, 1280)).save(rdir / 'proxy.jpg', 'JPEG', quality=90)
        flat.resize((320, 200)).save(rdir / 'thumb.jpg', 'JPEG', quality=85)
        for url in (band['thumb_url'], band['proxy_url'], it_b['result_urls']['thumb'], it_b['result_urls']['proxy']):
            ctype, fmt, im = self.get_image(svc, url)
            self.assertEqual((ctype, fmt, im.mode), ('image/jpeg', 'JPEG', 'RGB'), url)
        ctype, _, im = self.get_image(svc, it_b['result_urls']['region'] + '&x=0&y=0&w=64&h=64')
        self.assertEqual((ctype, im.mode), ('image/png', 'RGB'))
        ctype, _, im = self.get_image(svc, f'/api/media/{mb}/region?kind=source&x=0&y=0&w=64&h=100')
        self.assertEqual(im.mode, 'RGBA')
        self.assertEqual(svc.shutdown(), 0)


class TwoGpus(Base):
    def test_two_gpus_run_two_items_in_parallel(self):
        svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '2.5'}, settings={'gpus': [0, 1]})
        mids = [i['id'] for i in self.add(svc, make_inputs(self.d / 'in'))['items']]
        jid = self.job(svc, mids, {'scale': 2})['id']
        svc.wait_job(jid, lambda j: [it['state'] for it in j['items'][:2]] == ['running', 'running'], timeout=30)
        j = svc.wait_job(jid, all_done, timeout=60)
        self.assertEqual([it['state'] for it in j['items']], ['done'] * 3)
        gpus = [l['data']['gpu'] for l in svc.log_lines() if l['event'] == 'item_dispatched']
        self.assertEqual(sorted(gpus[:2]), [0, 1])
        code, h, _ = svc.get('/health')
        self.assertEqual([w['gpu'] for w in h['engine']['workers']], [0, 1])
        self.assertEqual(svc.shutdown(), 0)


class Cancel(Base):
    def test_cancel_queued_and_running(self):
        svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '6'})
        mids = [i['id'] for i in self.add(svc, make_inputs(self.d / 'in'))['items']]
        job = self.job(svc, mids, {'scale': 2})
        jid = job['id']
        svc.wait_job(jid, lambda j: j['items'][0]['state'] == 'running' and j['items'][0]['stage_progress'] > 0, timeout=30)
        code, j, _ = svc.post(f'/api/jobs/{jid}/items/i003/cancel')
        self.assertEqual((code, j['items'][2]['state']), (200, 'cancelled'))
        code, j, _ = svc.post(f'/api/jobs/{jid}/items/i001/cancel')
        self.assertEqual(code, 200)
        self.assertTrue(j['items'][0]['cancel_requested'])
        j = svc.wait_job(jid, lambda j: j['items'][0]['state'] == 'cancelled', timeout=30)
        j = svc.wait_job(jid, lambda j: j['items'][1]['state'] == 'running', timeout=30)
        code, j, _ = svc.post(f'/api/jobs/{jid}/cancel')
        j = svc.wait_job(jid, all_done, timeout=30)
        self.assertEqual([it['state'] for it in j['items']], ['cancelled'] * 3)
        self.assertEqual(j['state'], 'cancelled')
        self.assertFalse(self.out.exists() and any(self.out.iterdir()))
        self.assertFalse((self.d / 'state' / 'work' / jid).exists())
        time.sleep(0.5)
        w = self.d / 'state' / 'workers' / 'gpu0'
        self.assertEqual(list((w / 'input').iterdir()), [])
        self.assertEqual(list((w / 'output').iterdir()), [])
        renders = svc.renders()
        self.assertEqual([r['status'] for r in renders], ['interrupted', 'interrupted'])
        code, j2, _ = svc.post(f'/api/jobs/{jid}/cancel')
        self.assertEqual((code, j2['state']), (200, 'cancelled'))
        self.assertEqual(svc.shutdown(), 0)


class CrashRecovery(Base):
    def test_crash_mid_stage_then_restart_resumes_without_rerendering(self):
        env = {'CU_FAKE_STAGE_SECONDS': '0.4', 'CU_FAKE_FAULT': 'crash@1'}
        svc = self.service(env=env)
        mid = self.add(svc, [make_inputs(self.d / 'in')[1]])['items'][0]['id']
        job = self.job(svc, [mid], {'scale': 4})
        code = svc.proc.wait(60)
        self.assertEqual(code, 70)
        svc.out.close()
        rec = json.loads((self.d / 'state' / 'jobs' / f'{job["id"]}.json').read_text(encoding='utf8'))
        self.assertEqual((rec['items'][0]['state'], rec['items'][0]['stage_index']), ('running', 1))
        self.assertTrue((self.d / 'state' / 'work' / job['id'] / 'i001' / 'stage0.png').is_file())
        svc2 = self.service(env=env)
        j = svc2.wait_job(job['id'], all_done, timeout=60)
        it = j['items'][0]
        self.assertEqual(it['state'], 'done', json.dumps(it)[:1500])
        with Image.open(it['output']) as im:
            self.assertEqual(im.size, (404, 268))
        renders = svc2.renders()
        self.assertEqual([(r['stage'], r['status']) for r in renders], [(0, 'success'), (1, 'success')])
        lines = svc2.log_lines()
        req = [l for l in lines if l['event'] == 'item_requeued']
        self.assertEqual(req[0]['data']['stage_index'], 1)
        self.assertEqual(req[0]['msg'], 'Resuming at pass 2 of 2 after a restart')
        self.assertTrue(any(l['event'] == 'item_interrupted' for l in lines))
        self.assertEqual(svc2.shutdown(), 0)


class Watchdogs(Base):
    def test_stall_and_engine_error_fail_plainly_then_next_image_runs(self):
        svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '0.3', 'CU_FAKE_FAULT': 'stall@0,fail@0',
                                'CU_STALL_SECONDS': '1.5'})
        mids = [i['id'] for i in self.add(svc, make_inputs(self.d / 'in'))['items']]
        j = svc.wait_job(self.job(svc, mids, {'scale': 2})['id'], all_done, timeout=60)
        a, b, c = j['items']
        self.assertEqual((a['state'], b['state'], c['state']), ('failed', 'failed', 'done'))
        self.assertIn('stopped making progress', a['error']['text'])
        self.assertIn('stopped with an error', b['error']['text'])
        for it in (a, b):
            self.assertRegex(it['error']['log_ref'], r'^[0-9a-f]{8}$')
        code, logs, _ = svc.get(f'/api/logs?job={j["id"]}&level=warning')
        refs = {l['log_ref'] for l in logs['lines']}
        self.assertIn(a['error']['log_ref'], refs)
        self.assertTrue({l['level'] for l in logs['lines']} <= {'warning', 'error'}, logs['lines'])
        self.assertIn('warning', {l['level'] for l in logs['lines']})
        self.assertNotIn('KSampler', b['error']['text'])
        self.assertEqual(j['state'], 'failed')
        code, h, _ = svc.get('/health')
        self.assertEqual(h['engine']['workers'][0]['starts'], 2)
        self.assertEqual(svc.shutdown(), 0)


@unittest.skipUnless(os.name == 'nt', 'Windows Job containment')
class ContainedWorkers(Base):
    env = {'CU_FAKE_PROCESS': '1'}

    def worker_pids(self, svc):
        return [l['data']['pid'] for l in svc.log_lines() if l['event'] == 'worker_process']

    def test_worker_crash_restarts_and_shutdown_leaves_no_child_processes(self):
        from service.windows_job import process_alive
        svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '0.3', 'CU_FAKE_FAULT': 'crash@0'})
        mids = [i['id'] for i in self.add(svc, make_inputs(self.d / 'in'))['items']]
        j = svc.wait_job(self.job(svc, mids[:2], {'scale': 2})['id'], all_done, timeout=90)
        a, b = j['items']
        self.assertEqual((a['state'], b['state']), ('failed', 'done'))
        self.assertIn('closed unexpectedly', a['error']['text'])
        self.assertIn('(exit code 70)', a['error']['text'])
        pids = self.worker_pids(svc)
        self.assertEqual(len(pids), 2)
        self.assertFalse(process_alive(pids[0]))
        self.assertTrue(process_alive(pids[1]))

        svc.post('/api/settings', {'idle_minutes': 10})
        slow = self.job(svc, [mids[2]], {'scale': 4})
        svc.wait_job(slow['id'], lambda x: x['items'][0]['state'] == 'running', timeout=30)
        self.assertEqual(svc.shutdown(), 0)
        time.sleep(0.3)
        for pid in self.worker_pids(svc):
            self.assertFalse(process_alive(pid), f'worker process {pid} survived shutdown')
        rec = json.loads((self.d / 'state' / 'jobs' / f'{slow["id"]}.json').read_text(encoding='utf8'))
        self.assertEqual(rec['items'][0]['state'], 'interrupted')
        self.assertFalse((self.d / 'state' / 'service.json').exists())
        svc2 = self.service(env={'CU_FAKE_STAGE_SECONDS': '0.3'})
        j = svc2.wait_job(slow['id'], all_done, timeout=90)
        self.assertEqual(j['items'][0]['state'], 'done')
        self.assertEqual(svc2.shutdown(), 0)
        for pid in self.worker_pids(svc2):
            self.assertFalse(process_alive(pid))


@unittest.skipUnless(os.name == 'nt', 'Windows Job containment')
class HungEngine(Base):
    env = {'CU_FAKE_PROCESS': '1'}

    def worker_pids(self, svc):
        return [l['data']['pid'] for l in svc.log_lines() if l['event'] == 'worker_process']

    def test_cancel_kills_a_hung_engine_after_the_grace_time(self):
        from service.windows_job import process_alive
        svc = self.service(env={'CU_FAKE_FAULT': 'stall@0', 'CU_CANCEL_GRACE_SECONDS': '1', 'CU_STALL_SECONDS': '120',
                                'CU_FAKE_STAGE_SECONDS': '0.3'})
        mids = [i['id'] for i in self.add(svc, make_inputs(self.d / 'in'))['items']]
        jid = self.job(svc, mids[:2], {'scale': 2})['id']
        svc.wait_job(jid, lambda j: j['items'][0]['state'] == 'running', timeout=30)
        time.sleep(0.5)
        t0 = time.monotonic()
        svc.post(f'/api/jobs/{jid}/items/i001/cancel')
        j = svc.wait_job(jid, all_done, timeout=60)
        self.assertLess(time.monotonic() - t0, 30)
        self.assertEqual([i['state'] for i in j['items']], ['cancelled', 'done'])
        self.assertIn('interrupt_timeout', [l['event'] for l in svc.log_lines()])
        pids = self.worker_pids(svc)
        self.assertEqual(len(pids), 2)
        self.assertFalse(process_alive(pids[0]))
        self.assertEqual(svc.shutdown(), 0)

    def test_deadline_stops_a_pass_that_never_ends(self):
        svc = self.service(env={'CU_FAKE_FAULT': 'stall@0', 'CU_STALL_SECONDS': '600', 'CU_DEADLINE_SECONDS': '2',
                                'CU_FAKE_STAGE_SECONDS': '0.3'})
        mids = [i['id'] for i in self.add(svc, make_inputs(self.d / 'in'))['items']]
        j = svc.wait_job(self.job(svc, mids[:2], {'scale': 2})['id'], all_done, timeout=60)
        a, b = j['items']
        self.assertEqual((a['state'], b['state']), ('failed', 'done'))
        self.assertIn('took far longer than expected', a['error']['text'])
        self.assertRegex(a['error']['log_ref'], r'^[0-9a-f]{8}$')
        self.assertIn('deadline', [l['event'] for l in svc.log_lines()])
        code, h, _ = svc.get('/health')
        self.assertEqual(h['engine']['workers'][0]['starts'], 2)
        self.assertEqual(svc.shutdown(), 0)


class Api(Base):
    def test_requests_settings_inputs_masks_and_guards(self):
        svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '0.3'})
        paths = make_inputs(self.d / 'in')
        (self.d / 'in' / 'notes.txt').write_text('not an image')
        sub = self.d / 'in' / 'sub'
        sub.mkdir()
        Image.fromarray(gradient(70, 70)).save(sub / 'deeper.png')
        res = self.add(svc, [str(self.d / 'in'), str(paths[0]), str(self.d / 'nope.png'), 'relative.png'])
        self.assertEqual(len(res['items']), 3)
        again = self.add(svc, [str(paths[0])])['items'][0]
        self.assertEqual(again['id'], res['items'][0]['id'])
        (self.d / 'copies').mkdir()
        (self.d / 'copies' / 'a_copy.jpg').write_bytes(paths[0].read_bytes())
        (self.d / 'copies' / 'a_copy2.jpg').write_bytes(paths[0].read_bytes())
        copies = self.add(svc, [str(self.d / 'copies')])['items']
        self.assertEqual([c['duplicate'] for c in copies], [True, True])
        self.assertEqual(copies[0]['duplicate_of'], res['items'][0]['id'])
        self.assertIn('identical to another image', ' '.join(copies[0]['notes']))
        self.assertFalse(res['items'][0]['duplicate'])
        res['items'].append(copies[0])
        svc.request('DELETE', f'/api/inputs/{copies[1]["id"]}')
        reasons = {Path(r['path']).name: r['reason'] for r in res['rejected']}
        self.assertIn('not found', reasons['nope.png'])
        self.assertIn('full path', reasons['relative.png'])
        txt = self.add(svc, [str(self.d / 'in' / 'notes.txt')])
        self.assertIn('Not an image file', txt['rejected'][0]['reason'])
        mids = [i['id'] for i in res['items']]
        code, err, _ = svc.post('/api/open', {'path': str(self.out)})
        self.assertEqual(code, 404)
        self.assertIn('has not been created yet', err['error']['message'])
        self.out.mkdir(parents=True, exist_ok=True)
        code, opened, _ = svc.post('/api/open', {'path': str(self.out)})
        self.assertEqual((code, opened['how']), (200, 'folder'))
        code, lst, _ = svc.get('/api/inputs')
        self.assertEqual(len(lst['items']), 4)
        code, _, _ = svc.request('DELETE', f'/api/inputs/{mids[3]}')
        self.assertEqual(code, 200)
        code, err, _ = svc.request('DELETE', f'/api/inputs/{mids[3]}')
        self.assertEqual(code, 404)

        r = rid()
        j1 = self.job(svc, mids[:1], {'scale': 2}, request_id=r)
        j1b = self.job(svc, mids[:1], {'scale': 2}, request_id=r, expect=200)
        self.assertEqual(j1['id'], j1b['id'])
        code, err, _ = svc.post('/api/jobs', {'client_request_id': r, 'media_ids': mids[:1], 'settings': {'scale': 4}})
        self.assertEqual(code, 409)
        self.assertEqual(err['error']['code'], 'request_conflict')
        self.assertRegex(err['error']['log_ref'], r'^[0-9a-f]{8}$')

        for settings, text in (({'creativity': 70}, 'Choose Custom'), ({'scale': 3}, '2×, 4×, 6× or 8×'),
                               ({'colour': 'red'}, 'not recognised'), ({'preset': 'Medium'}, 'Choose a preset')):
            code, err, _ = svc.post('/api/jobs', {'client_request_id': rid(), 'media_ids': mids[:1], 'settings': settings})
            self.assertEqual(code, 400, err)
            self.assertIn(text, err['error']['message'])
        for body, code_ in (({'client_request_id': 'short', 'media_ids': mids[:1]}, 'bad_request'),
                            ({'client_request_id': rid(), 'media_ids': ['m000000000000']}, 'unknown_image'),
                            ({'client_request_id': rid(), 'media_ids': mids[:1], 'output_dir': 'rel'}, 'bad_output_dir')):
            code, err, _ = svc.post('/api/jobs', body)
            self.assertEqual((code, err['error']['code']), (400, code_))
        n_jobs = len(svc.get('/api/jobs')[1]['jobs'])
        self.assertEqual(n_jobs, 1)

        # 8x of 1900 x 1900 is 231 MP: over the Classic engine's 150 MP and over every Large-image limit (213 MP; a 128 GB
        # PC takes the 64 GB PC's by Max's rule, so 8x of 1600 x 1600, 164 MP, is no longer refused here)
        Image.fromarray(gradient(1900, 1900)).save(self.d / 'big.png')
        big = self.add(svc, [self.d / 'big.png'])['items'][0]
        self.assertFalse(big['scales']['8']['ok'])
        code, err, _ = svc.post('/api/jobs', {'client_request_id': rid(), 'media_ids': [big['id']], 'settings': {'scale': 8}})
        self.assertEqual((code, err['error']['code']), (400, 'plan_refused'))
        self.assertIn('largest supported output', err['error']['message'])
        code, plan, _ = svc.post('/api/plan', {'width': 3840, 'height': 2400, 'scale': 2})
        self.assertTrue(plan['ok'])
        self.assertIn('7,680 \u00d7 4,800', plan['text']['summary'])
        self.assertNotIn('padded', ' '.join(plan['text']['notes']))
        code, err, _ = svc.post('/api/plan', {'width': 'x', 'height': 2, 'scale': 2})
        self.assertEqual(code, 400)

        code, s, _ = svc.get('/api/settings')
        self.assertEqual((code, s['gpus'], s['output_dir']), (200, [0], str(self.out)))
        self.assertEqual((s['output_dir_writable'], s['output_dir_problem']), (True, None))
        code, err, _ = svc.post('/api/settings', {'gpus': [5]})
        self.assertEqual(code, 400)
        code, err, _ = svc.post('/api/settings', {'ram_cap_gb': 20})
        self.assertEqual(code, 400)
        code, s, _ = svc.post('/api/settings', {'output_dir': str(self.d / 'out2'), 'idle_minutes': 3})
        self.assertEqual((code, s['idle_minutes'], s['output_dir_writable']), (200, 3, True))
        code, err, _ = svc.post('/api/settings', {'output_dir': str(self.d / 'no' / 'such' / 'out')})
        self.assertEqual(code, 400)
        self.assertFalse((self.d / 'no').exists())

        code, c, _ = svc.get('/api/controls')
        self.assertEqual([p['name'] for p in c['presets']], ['Light', 'Default', 'Strong', 'Heavy', 'Extreme'])

        svc.wait_job(j1['id'], all_done, timeout=60)
        code, m, _ = svc.post('/api/mask-preview', {'media_id': mids[0], 'protect': ['people', 'architecture']})
        self.assertEqual(code, 200, m)
        self.assertEqual((m['cached'], m['categories']), (False, ['people', 'architecture']))
        code, png, hdr = svc.get(m['mask_url'], raw=True)
        self.assertEqual((code, hdr['Content-Type']), (200, 'image/png'))
        code, m2, _ = svc.post('/api/mask-preview', {'media_id': mids[0], 'protect': ['architecture', 'people']})
        self.assertTrue(m2['cached'])
        code, m3, _ = svc.post('/api/mask-preview', {'media_id': mids[0], 'quick_protect': 'architecture_only_people_vegetation'})
        self.assertNotIn('person', m3['terms'])
        code, m4, _ = svc.post('/api/mask-preview', {'media_id': mids[0], 'protect': []})
        self.assertEqual((code, m4['terms']), (200, []))
        code, err, _ = svc.post('/api/mask-preview', {'media_id': mids[0], 'protect': ['trees']})
        self.assertEqual(code, 400)

        code, err, _ = svc.request('GET', '/api/nothing')
        self.assertEqual(code, 404)
        code, err, _ = svc.request('DELETE', '/api/jobs')
        self.assertEqual(code, 405)
        code, err, hdr = svc.request('PUT', '/api/settings', {'gpus': [0]})
        self.assertEqual((code, err['error']['code']), (405, 'method_not_allowed'))
        self.assertRegex(err['error']['log_ref'], r'^[0-9a-f]{8}$')
        import urllib.request
        req = urllib.request.Request(f'http://127.0.0.1:{svc.port}/api/shutdown', data=b'{}', method='POST',
                                     headers={'Origin': 'http://evil.example', 'Content-Type': 'text/plain',
                                              'Authorization': 'Bearer ' + svc.token})
        code = None
        try:
            svc.opener.open(req, timeout=10)
        except urllib.error.HTTPError as e:
            code = e.code
        self.assertEqual(code, 403)
        req = urllib.request.Request(f'http://127.0.0.1:{svc.port}/health', headers={'Host': 'evil.example',
                                                                                     'Authorization': 'Bearer ' + svc.token})
        try:
            svc.opener.open(req, timeout=10)
            code = 200
        except urllib.error.HTTPError as e:
            code = e.code
        self.assertEqual(code, 403)

        self.assertEqual(svc.shutdown(), 0)

    def test_health_reports_missing_paths(self):
        svc = self.service(config={'node_pack_dir': str(self.d / 'missing' / 'claude_creative')},
                           output_dir=self.d / 'unplugged' / 'drive' / 'out')
        code, h, _ = svc.get('/health')
        self.assertEqual(code, 200)
        self.assertFalse(h['ok'])
        self.assertFalse(h['engine']['ready'])
        text = ' '.join(h['problems'])
        self.assertIn('engine files are missing or changed', text)
        self.assertIn('not reachable', text)
        for jargon in ('node pack', 'manifest', 'tools/'):
            self.assertNotIn(jargon, text)
        code, st, _ = svc.get('/api/settings')
        self.assertFalse(st['output_dir_writable'])
        self.assertIn('not reachable', st['output_dir_problem'])
        self.assertEqual((h['service'], h['contract']), ('creative-upscaler', 'creative-upscaler-service-v1'))
        self.assertEqual(svc.shutdown(), 0)
        ok = self.service(state='state2')
        code, h, _ = ok.get('/health')
        self.assertTrue(h['ok'], h['problems'])
        self.assertTrue(h['engine']['ready'])
        self.assertEqual(h['engine']['workers'][0]['state'], 'stopped')
        self.assertEqual(ok.shutdown(), 0)


class KeepAlive(Base):
    def test_refused_requests_never_desync_the_connection(self):
        svc = self.service()
        c = http.client.HTTPConnection('127.0.0.1', svc.port, timeout=10)
        try:
            for method, path, body in (('POST', '/api/jobs/j000000000000/cancel', b'{"note": "x"}'),
                                       ('POST', '/api/jobs/j000000000000/items/i001/cancel', b'{}'),
                                       ('POST', '/api/nothing', b'{"x": 1}'),
                                       ('PUT', '/api/settings', b'{"gpus": [0]}'),
                                       ('DELETE', '/api/jobs', b'{}'),
                                       ('POST', '/api/shutdown', b'{}')):
                if path == '/api/shutdown':
                    c.request(method, path, body=body, headers={'Content-Type': 'application/json',
                                                                'Origin': 'http://evil.example', **svc.auth()})
                else:
                    c.request(method, path, body=body, headers={'Content-Type': 'application/json', **svc.auth()})
                r = c.getresponse()
                data = json.loads(r.read())
                self.assertIn(r.status, (403, 404, 405), (method, path, r.status))
                self.assertIn('log_ref', data['error'])
                c.request('GET', '/health', headers=svc.auth())
                r = c.getresponse()
                self.assertEqual((r.status, r.getheader('Content-Type')), (200, 'application/json; charset=utf-8'),
                                 (method, path))
                self.assertEqual(json.loads(r.read())['service'], 'creative-upscaler')

            c.request('POST', '/api/plan', body=b'{}', headers={'Content-Length': str(2 << 20), **svc.auth()})
            r = c.getresponse()
            self.assertEqual((r.status, r.getheader('Connection')), (413, 'close'))
            self.assertEqual(json.loads(r.read())['error']['code'], 'too_large')
        finally:
            c.close()

        with socket.create_connection(('127.0.0.1', svc.port), timeout=10) as sock:
            sock.sendall(b'{}GET /health HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n')
            raw = b''
            while True:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                raw += chunk
        head, _, body = raw.partition(b'\r\n\r\n')
        self.assertIn(b'application/json', head)
        self.assertIn(b'Connection: close', head)
        err = json.loads(body)['error']
        self.assertRegex(err['code'], r'^http_[45]\d\d$')
        self.assertRegex(err['log_ref'], r'^[0-9a-f]{8}$')
        self.assertEqual(svc.shutdown(), 0)


class GraphIdentity(Base):
    def test_service_sends_exact_engine_graph(self):
        svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '0.2'})
        img = self.d / 'g.png'
        Image.fromarray(gradient(72, 65)).save(img)
        mid = self.add(svc, [img])['items'][0]['id']
        for req in ({}, {'custom': True, 'creativity': 70, 'resemblance': 40, 'restoration': 20,
                         'protect': ['people', 'architecture'], 'scale': 4, 'seed': '7'}):
            j = svc.wait_job(self.job(svc, [mid], req)['id'], all_done, timeout=60)
            self.assertEqual(j['items'][0]['state'], 'done', json.dumps(j)[:1500])
            params, eff = controls.resolve(req)
            self.assertEqual({k: j['effective'][k] for k in eff}, json.loads(json.dumps(eff)))
            stages = j['items'][0]['plan']['stages']
            self.assertEqual(len(stages), 1 if not req else 2)
            for k, st in enumerate(stages):
                pre = f"cu_{j['id']}_i001_s{k}"
                sent = json.loads((self.d / 'state/workers/gpu0/fake-prompts' / f'{pre}.json').read_text(encoding='utf8'))


                opts = {'noise_prefetch': True, 'pag_fuse': True, 'batch_windows': 2, 'fp16_acc_scoped': True,
                        'live_preview': 'detailed'}
                want, _ = graph_v5t.build_product(pre + '.png', *st['padded_size'], controls.stage_params(params, k), pre,
                                                  f=runner._frac(st['factor']), s=runner._frac(st['supersample']),
                                                  speed_stack=True, live_preview='detailed')
                self.assertEqual(sent, json.loads(json.dumps(want)), f'stage {k} of {req}')
                plain, _ = graph_v5t.build(pre + '.png', *st['padded_size'], controls.stage_params(params, k), pre,
                                           f=runner._frac(st['factor']), s=runner._frac(st['supersample']))
                spot = next(n for n, v in sent.items() if v['class_type'] == 'ClaudeSpotTiles')
                for n, v in sent.items():
                    if n != spot:
                        self.assertEqual(v, json.loads(json.dumps(plain[n])), (k, n))
                self.assertEqual({a: b for a, b in sent[spot]['inputs'].items() if a not in opts},
                                 json.loads(json.dumps(plain[spot]['inputs'])))
            if not req:
                p0, _ = controls.resolve({})
                self.assertEqual(controls.stage_params(params, 0), controls.stage_params(p0, 0))
            else:
                s1 = controls.stage_params(params, 1)
                self.assertEqual(s1['seed'], 8)
                self.assertIn('building', s1['protect_terms'])
        self.assertEqual(svc.shutdown(), 0)


class RecoveryEdges(Base):
    def test_crash_after_publishing_completes_without_a_second_copy(self):
        svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '0.2'})
        mid = self.add(svc, [make_inputs(self.d / 'in')[0]])['items'][0]['id']
        j = svc.wait_job(self.job(svc, [mid], {'scale': 2})['id'], all_done, timeout=60)
        out = j['items'][0]['output']
        self.assertEqual(svc.shutdown(), 0)
        rec_path = self.d / 'state' / 'jobs' / f'{j["id"]}.json'
        rec = json.loads(rec_path.read_text(encoding='utf8'))
        rec['items'][0]['state'] = 'finishing'
        rec['items'][0]['history'].append({'ts': 'x', 'state': 'finishing'})
        rec['state'] = 'running'
        rec_path.write_text(json.dumps(rec), encoding='utf8')
        renders = len(svc.renders())
        svc2 = self.service(env={'CU_FAKE_STAGE_SECONDS': '0.2'})
        j2 = svc2.wait_job(j['id'], all_done, timeout=30)
        self.assertEqual((j2['items'][0]['state'], j2['items'][0]['output']), ('done', out))
        self.assertEqual(sorted(p.name for p in self.out.iterdir()), ['a_cu2x.json', 'a_cu2x.png'])
        self.assertEqual(len(svc2.renders()), renders)
        self.assertIn('item_recovered_done', [l['event'] for l in svc2.log_lines()])
        self.assertEqual(svc2.shutdown(), 0)

    def test_crash_while_finishing_publishes_without_rendering_again(self):
        env = {'CU_FAKE_STAGE_SECONDS': '0.2', 'CU_TEST_CRASH': 'finish'}
        svc = self.service(env=env)
        mid = self.add(svc, [make_inputs(self.d / 'in')[1]])['items'][0]['id']
        job = self.job(svc, [mid], {'scale': 4})
        self.assertEqual(svc.proc.wait(60), 70)
        svc.out.close()
        svc2 = self.service(env=env)
        j = svc2.wait_job(job['id'], all_done, timeout=60)
        self.assertEqual(j['items'][0]['state'], 'done', json.dumps(j)[:1500])
        self.assertEqual([(r['stage'], r['status']) for r in svc2.renders()], [(0, 'success'), (1, 'success')])
        with Image.open(j['items'][0]['output']) as im:
            self.assertEqual(im.size, (404, 268))
        self.assertTrue(j['items'][0]['result_ready'])
        self.assertEqual(svc2.shutdown(), 0)

    def test_several_jobs_across_a_crash_keep_order_and_finished_work(self):
        env = {'CU_FAKE_STAGE_SECONDS': '0.2', 'CU_FAKE_FAULT': 'crash@i001_s1'}
        svc = self.service(env=env)
        a, b, c = (i['id'] for i in self.add(svc, make_inputs(self.d / 'in'))['items'])
        j1 = svc.wait_job(self.job(svc, [a], {'scale': 2})['id'], all_done, timeout=60)
        side = Path(j1['items'][0]['sidecar'])
        before = (images_sha(j1['items'][0]['output']), side.stat().st_mtime_ns)
        j2 = self.job(svc, [b, c], {'scale': 4})
        self.assertEqual(svc.proc.wait(60), 70)
        svc.out.close()
        svc2 = self.service(env=env)
        j2 = svc2.wait_job(j2['id'], all_done, timeout=90)
        self.assertEqual([it['state'] for it in j2['items']], ['done', 'done'])
        self.assertEqual((images_sha(j1['items'][0]['output']), side.stat().st_mtime_ns), before)
        ok = [r['prefix'] for r in svc2.renders() if r['status'] == 'success']
        self.assertEqual([p.split('_', 2)[2] for p in ok], ['i001_s0', 'i001_s0', 'i001_s1', 'i002_s0', 'i002_s1'])
        self.assertEqual(svc2.shutdown(), 0)


class CancelWhileStarting(Base):
    def test_cancel_during_engine_start_is_immediate_and_final(self):
        svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '0.2', 'CU_FAKE_START_SECONDS': '3'})
        mids = [i['id'] for i in self.add(svc, make_inputs(self.d / 'in'))['items']]
        jid = self.job(svc, mids[:2], {'scale': 2})['id']
        svc.wait_job(jid, lambda j: j['items'][0]['state'] == 'preparing', timeout=20)
        t0 = time.monotonic()
        code, j, _ = svc.post(f'/api/jobs/{jid}/items/i001/cancel')
        self.assertLess(time.monotonic() - t0, 2.0)
        self.assertEqual((code, j['items'][0]['state']), (200, 'cancelled'))
        j = svc.wait_job(jid, all_done, timeout=60)
        self.assertEqual([it['state'] for it in j['items']], ['cancelled', 'done'])
        self.assertEqual([r['prefix'].split('_', 2)[2] for r in svc.renders()], ['i002_s0'])
        code, h, _ = svc.get('/health')
        self.assertEqual(h['engine']['workers'][0]['starts'], 1)
        self.assertEqual(svc.shutdown(), 0)


class Faults(Base):
    def test_engine_faults_fail_plainly_and_keep_the_worker(self):
        faults = 'nows,reject@i001_s0,nofile@i002_s0,badsize@i003_s0,oom@i004_s0'
        svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '0.2', 'CU_FAKE_FAULT': faults})
        mid = self.add(svc, [make_inputs(self.d / 'in')[0]])['items'][0]['id']
        j = svc.wait_job(self.job(svc, [mid] * 5, {'scale': 2})['id'], all_done, timeout=90)
        texts = [it['error']['text'] if it['error'] else it['state'] for it in j['items']]
        self.assertIn('could not accept pass 1 of 1', texts[0])
        self.assertIn('result file is missing', texts[1])
        self.assertIn('wrong size', texts[2])
        self.assertIn('graphics card ran out of memory', texts[3])
        self.assertNotIn('smaller upscale', texts[3])
        self.assertIn('Close other programs that use it', texts[3])
        self.assertEqual(texts[4], 'done')
        for it in j['items'][:4]:
            self.assertRegex(it['error']['log_ref'], r'^[0-9a-f]{8}$')
        events = [l['event'] for l in svc.log_lines()]
        self.assertIn('ws_down', events)
        code, h, _ = svc.get('/health')
        self.assertEqual(h['engine']['workers'][0]['starts'], 1)
        self.assertEqual(svc.shutdown(), 0)

    def test_engine_start_failures_wait_then_retry(self):
        svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '0.2', 'CU_FAKE_FAULT': 'nostart,missingnode',
                                'CU_START_BACKOFF_SECONDS': '60'})
        mid = self.add(svc, [make_inputs(self.d / 'in')[0]])['items'][0]['id']
        jid = self.job(svc, [mid], {'scale': 2})['id']
        j = svc.wait_job(jid, lambda j: j['items'][0]['message'].startswith('Waiting for the engine'), timeout=30)
        it = j['items'][0]
        self.assertEqual(it['state'], 'queued')
        self.assertRegex(it['message_log_ref'], r'^[0-9a-f]{8}$')
        code, h, _ = svc.get('/health')
        self.assertIn('The engine could not start.', h['problems'])
        self.assertEqual(h['engine']['workers'][0]['state'], 'failed')
        self.assertEqual(h['engine']['workers'][0]['log_ref'], it['message_log_ref'])
        code, h, _ = svc.post('/api/engine/retry')
        self.assertEqual(code, 200)
        j = svc.wait_job(jid, lambda j: 'missing parts' in j['items'][0]['message'], timeout=30)
        code, h, _ = svc.post('/api/engine/retry')
        j = svc.wait_job(jid, all_done, timeout=30)
        self.assertEqual(j['items'][0]['state'], 'done')
        self.assertIsNone(j['items'][0]['message_log_ref'])
        code, h, _ = svc.get('/health')
        self.assertTrue(h['ok'], h['problems'])
        self.assertEqual(svc.shutdown(), 0)


class OutputOutage(Base):
    def test_finishing_waits_for_the_output_folder_and_frees_the_gpu(self):
        drive = self.d / 'drive'
        out = drive / 'out'
        drive.mkdir()
        svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '1.5', 'CU_OUTPUT_WAIT_SECONDS': '1'}, output_dir=out)
        mids = [i['id'] for i in self.add(svc, make_inputs(self.d / 'in'))['items']]
        jid = self.job(svc, mids[:2], {'scale': 2})['id']
        svc.wait_job(jid, lambda j: j['items'][0]['state'] == 'running', timeout=30)
        drive.rename(self.d / 'drive_off')
        j = svc.wait_job(jid, lambda j: j['items'][0]['message'].startswith('Waiting for the output folder'), timeout=30)
        self.assertEqual(j['items'][0]['state'], 'finishing')
        self.assertIn('not reachable', j['items'][0]['message'])
        j = svc.wait_job(jid, lambda j: j['items'][1]['state'] in ('running', 'finishing'), timeout=30)
        self.assertEqual(j['items'][0]['state'], 'finishing')
        (self.d / 'drive_off').rename(drive)
        j = svc.wait_job(jid, all_done, timeout=60)
        self.assertEqual([it['state'] for it in j['items']], ['done', 'done'])
        self.assertEqual(sorted(p.name for p in out.iterdir()), ['a_cu2x.json', 'a_cu2x.png', 'b_cu2x.json', 'b_cu2x.png'])
        self.assertIn('output_write_waiting', [l['event'] for l in svc.log_lines()])
        self.assertEqual(svc.shutdown(), 0)


class MaskPreview(Base):
    def test_a_repeated_preview_waits_for_the_first_and_renders_once(self):
        import threading
        svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '0.2', 'CU_FAKE_START_SECONDS': '2'})
        mid = self.add(svc, [make_inputs(self.d / 'in')[0]])['items'][0]['id']
        res = []

        def ask():
            res.append(svc.post('/api/mask-preview', {'media_id': mid, 'protect': ['people']}, timeout=60))
        ts = [threading.Thread(target=ask) for _ in range(2)]
        for t in ts:
            t.start()
            time.sleep(0.4)
        for t in ts:
            t.join(60)
        self.assertEqual(sorted(r[0] for r in res), [200, 200], res)
        self.assertEqual(sorted(r[1]['cached'] for r in res), [False, True])
        self.assertEqual(len([r for r in svc.renders() if r['prefix'].startswith('cu_mask_')]), 1)
        self.assertEqual(svc.shutdown(), 0)


class Memory(Base):
    def test_second_image_waits_for_memory_and_too_large_plans_are_refused(self):
        svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '1.0'}, settings={'gpus': [0, 1], 'ram_cap_gb': 45})
        items = self.add(svc, make_inputs(self.d / 'in'))['items']
        mids = [i['id'] for i in items]
        j = svc.wait_job(self.job(svc, mids[:2], {'scale': 2})['id'], all_done, timeout=60)
        self.assertEqual([it['state'] for it in j['items']], ['done', 'done'])
        held = [l for l in svc.log_lines() if l['event'] == 'item_held_memory']
        self.assertTrue(held and held[0]['item'] == 'i002', held)
        starts = {l['item']: l['ts'] for l in svc.log_lines() if l['event'] == 'stage_start'}
        dones = {l['item']: l['ts'] for l in svc.log_lines() if l['event'] == 'stage_done'}
        self.assertGreaterEqual(starts['i002'], dones['i001'])
        Image.fromarray(gradient(1600, 1600)).save(self.d / 'big.png')
        big = self.add(svc, [self.d / 'big.png'])['items'][0]
        # 5.0.1: 4x fits the 45 GB cap with its second pass lightened, and says so; 6x needs more than 45 at any setting
        four = big['scales']['4']
        self.assertTrue(four['ok'], four)
        self.assertTrue(four['ram_limited'])
        self.assertEqual(four['text']['notes'], [LIGHTER_FOR_MEMORY])
        job = self.job(svc, [big['id']], {'scale': 4})
        plan = job['items'][0]['plan']
        self.assertEqual(([s['supersample'] for s in plan['stages']], plan['ram_limited']), ([2.0, 1.0], True))
        self.assertLessEqual(plan['peak_ram_gb'], 45)
        self.assertFalse(big['scales']['6']['ok'])
        self.assertIn('GB of memory', big['scales']['6']['reason'])
        code, err, _ = svc.post('/api/jobs', {'client_request_id': rid(), 'media_ids': [big['id']], 'settings': {'scale': 6}})
        self.assertEqual((code, err['error']['code']), (400, 'plan_refused'))
        self.assertIn('GB of memory', err['error']['message'])
        svc.wait_job(job['id'], all_done, timeout=120)
        self.assertEqual(svc.shutdown(), 0)


if __name__ == '__main__':
    unittest.main()
