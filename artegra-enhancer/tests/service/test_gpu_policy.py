import hashlib
import json
import time
import unittest

import numpy as np
from PIL import Image

from service import engine_options, gpu_policy as gp, workers as wk
from tests.service.helpers import REPO, gradient
from tests.service.test_integration import Base, all_done

WS_CARDS = [{'index': 0, 'name': 'NVIDIA GeForce RTX 5090', 'mem_free_gb': 31.0, 'mem_total_gb': 31.84, 'sm_count': 170},
            {'index': 1, 'name': 'NVIDIA GeForce RTX 5090', 'mem_free_gb': 31.4, 'mem_total_gb': 31.84, 'sm_count': 170}]
LAPTOP = [{'index': 0, 'name': 'NVIDIA GeForce RTX 4080 Laptop GPU', 'mem_free_gb': 11.0, 'mem_total_gb': 12.0, 'sm_count': 58}]


class Policy(unittest.TestCase):
    def test_one_image_uses_both_cards(self):
        t = gp.plan_topology(WS_CARDS, [0, 1], queued=1, running=0, current=None, waiting_mp=67.1)
        self.assertEqual((t.mode, t.workers), ('split', [(0, 1)]))
        self.assertEqual(t.caps_gb, {(0, 1): 110.0})

        self.assertAlmostEqual(t.saving_s, 913.3 - 684.7, delta=2)

    def test_batch_uses_one_card_each(self):
        t = gp.plan_topology(WS_CARDS, [0, 1], queued=5, running=0, current=None, waiting_mp=67.1)
        self.assertEqual((t.mode, t.workers), ('lanes', [(0,), (1,)]))
        self.assertEqual(t.caps_gb, {(0,): 55.0, (1,): 55.0})

    def test_running_image_is_never_moved(self):
        cur = gp.Topology('lanes', [(0,), (1,)])
        self.assertIs(gp.plan_topology(WS_CARDS, [0, 1], queued=1, running=1, current=cur), cur)

    def test_short_image_does_not_pay_the_switch(self):
        cur = gp.Topology('lanes', [(0,), (1,)])
        t = gp.plan_topology(WS_CARDS, [0, 1], queued=1, running=0, current=cur, waiting_mp=9.4)
        self.assertEqual(t.mode, 'lanes')
        self.assertIn('switch', t.reason)
        self.assertEqual(gp.plan_topology(WS_CARDS, [0, 1], queued=1, running=0, current=None, waiting_mp=9.4).mode,
                         'split')

    def test_card_without_memory_stays_out(self):
        cards = [dict(WS_CARDS[0]), dict(WS_CARDS[1], mem_free_gb=6.0)]
        self.assertEqual(gp.plan_topology(cards, [0, 1], queued=1, running=0, current=None, waiting_mp=54).mode, 'lanes')

    def test_the_plan_names_the_cards_under_the_floor(self):
        cards = [dict(WS_CARDS[0]), dict(WS_CARDS[1], mem_free_gb=14.04)]
        t = gp.plan_topology(cards, [0, 1], queued=1, running=0, current=None, waiting_mp=54)
        self.assertEqual((t.mode, t.under_floor), ('lanes', [(1, 14.0)]))
        both = [dict(WS_CARDS[0], mem_free_gb=12.0), dict(WS_CARDS[1], mem_free_gb=6.0)]
        self.assertEqual(gp.plan_topology(both, [0, 1], queued=1, running=0, current=None, waiting_mp=54).under_floor,
                         [(0, 12.0), (1, 6.0)])

        self.assertEqual(gp.plan_topology(cards, [0, 1], queued=2, running=0, current=None, waiting_mp=54).under_floor, [])
        self.assertEqual(gp.plan_topology(WS_CARDS, [0, 1], queued=1, running=0, current=None, waiting_mp=54).under_floor, [])

        short = gp.plan_topology(cards, [0, 1], queued=1, running=0, current=None, waiting_mp=54)
        self.assertEqual(short.under_floor, [(1, 14.0)])
        kept = gp.plan_topology(cards, [0, 1], queued=1, running=1, current=short, waiting_mp=54)
        self.assertIs(kept, short)
        self.assertEqual(kept.under_floor, [])

        self.assertEqual(gp.plan_topology(cards, [0, 1], queued=1, running=0, current=None, waiting_mp=54,
                                          min_free_gb=12.0).mode, 'split')
        self.assertEqual(gp.MIN_SPLIT_FREE_VRAM_GB, engine_options.MIN_SPLIT_FREE_VRAM_GB)

    def test_the_floor_is_the_measured_one(self):
        self.assertEqual(gp.MIN_SPLIT_FREE_VRAM_GB, 19.0)
        self.assertAlmostEqual(gp.MIN_SPLIT_FREE_VRAM_GB - (17005 - 476) / 1024.0, 2.86, places=2)
        at = [dict(WS_CARDS[0]), dict(WS_CARDS[1], mem_free_gb=19.0)]
        self.assertEqual(gp.plan_topology(at, [0, 1], queued=1, running=0, current=None, waiting_mp=54).mode, 'split')
        under = [dict(WS_CARDS[0]), dict(WS_CARDS[1], mem_free_gb=18.9)]
        t = gp.plan_topology(under, [0, 1], queued=1, running=0, current=None, waiting_mp=54)
        self.assertEqual((t.mode, t.under_floor), ('lanes', [(1, 18.9)]))
        old = [dict(WS_CARDS[0]), dict(WS_CARDS[1], mem_free_gb=18.0)]
        self.assertEqual(gp.plan_topology(old, [0, 1], queued=1, running=0, current=None, waiting_mp=54).mode, 'lanes')


        ws = [dict(WS_CARDS[0], mem_free_gb=26.6), dict(WS_CARDS[1], mem_free_gb=30.3)]
        self.assertEqual(gp.plan_topology(ws, [0, 1], queued=1, running=0, current=None, waiting_mp=54).mode, 'split')

    def test_the_switch_costs_only_when_a_loaded_engine_must_stop(self):
        lanes = gp.Topology('lanes', [(0,), (1,)])
        kw = dict(queued=1, running=0, current=lanes, waiting_mp=9.4)
        self.assertEqual(gp.plan_topology(WS_CARDS, [0, 1], **kw).mode, 'lanes')
        self.assertEqual(gp.plan_topology(WS_CARDS, [0, 1], warm=[], **kw).mode, 'split')
        self.assertEqual(gp.plan_topology(WS_CARDS, [0, 1], warm=[(0, 1)], **kw).mode, 'split')
        t = gp.plan_topology(WS_CARDS, [0, 1], warm=[(0,)], **kw)
        self.assertEqual(t.mode, 'lanes')
        self.assertIn('switch', t.reason)
        long = dict(kw, waiting_mp=67.1)
        self.assertEqual(gp.plan_topology(WS_CARDS, [0, 1], warm=[(0,), (1,)], **long).mode, 'split')

    def test_the_switch_test_is_w2s_measurement(self):
        both_warm = dict(queued=1, running=0, current=gp.Topology('lanes', [(0,), (1,)]), warm=[(0,), (1,)])
        crop = gp.plan_topology(WS_CARDS, [0, 1], waiting_mp=9.4, **both_warm)
        self.assertEqual(crop.mode, 'lanes')
        self.assertIn('less than the 68 s switch', crop.reason)
        full = gp.plan_topology(WS_CARDS, [0, 1], waiting_mp=67.1, **both_warm)
        self.assertEqual(full.mode, 'split')

        self.assertAlmostEqual(gp.SPLIT_SAVING_S_PER_MP, (913.3 - 684.7) / 67.1, places=1)
        self.assertLess(gp.SPLIT_SAVING_S_PER_MP, (173.7 - 127.3) / 9.4)
        self.assertAlmostEqual(gp.SWITCH_COST_S, max(184.9 - 127.3 + 9.5, 743.9 - 684.7 + 8.9), delta=0.5)

        self.assertLess(173.7 - 127.3, gp.SWITCH_COST_S)
        self.assertLess(240.7 - 190.7, gp.SWITCH_COST_S)

        self.assertEqual(gp.plan_topology(WS_CARDS, [0, 1], waiting_mp=19.0, **both_warm).mode, 'lanes')
        self.assertEqual(gp.plan_topology(WS_CARDS, [0, 1], waiting_mp=21.0, **both_warm).mode, 'split')

        self.assertEqual(gp.plan_topology(WS_CARDS, [0, 1], waiting_mp=9.4, **dict(both_warm, warm=[])).mode, 'split')
        self.assertEqual(gp.plan_topology(WS_CARDS, [0, 1], waiting_mp=9.4, **dict(both_warm, warm=[(0, 1)])).mode, 'split')

        self.assertEqual(gp.split_saving_s(67.1, 1), 0.0)
        self.assertGreater(gp.split_saving_s(67.1, 4), gp.split_saving_s(67.1, 2))
        self.assertAlmostEqual(gp.split_saving_s(67.1, 2), 67.1 * gp.SPLIT_SAVING_S_PER_MP)

    def test_single_card_machine(self):
        t = gp.plan_topology(LAPTOP, [0], queued=3, running=0, current=None)
        self.assertEqual((t.mode, t.workers), ('lanes', [(0,)]))

    def test_four_cards_two_images(self):
        cards = [dict(WS_CARDS[0], index=i) for i in range(4)]
        t = gp.plan_topology(cards, [0, 1, 2, 3], queued=2, running=0, current=None, waiting_mp=54)
        self.assertEqual((t.mode, t.workers), ('split', [(0, 1), (2, 3)]))
        t3 = gp.plan_topology(cards[:3], [0, 1, 2], queued=2, running=0, current=None, waiting_mp=54)
        self.assertEqual(t3.workers, [(0,), (1, 2)])

    def test_weights_and_balance(self):
        self.assertEqual(gp.balance_mode(WS_CARDS), 'queue')
        mixed = [WS_CARDS[0], {'index': 1, 'name': 'NVIDIA GeForce RTX 4080', 'mem_free_gb': 15, 'mem_total_gb': 16, 'sm_count': 76}]
        self.assertEqual(gp.balance_mode(mixed), 'static')
        self.assertEqual(gp.card_weights(mixed), [1.0, round(76 / 170, 4)])
        self.assertEqual(gp.card_weights(mixed, {'NVIDIA GeForce RTX 5090': 0.30, 'NVIDIA GeForce RTX 4080': 0.60}), [1.0, 0.5])

    def test_amdahl(self):
        self.assertAlmostEqual(gp.split_speedup(1), 1.0)
        self.assertTrue(1.5 < gp.split_speedup(2) < 1.6)
        self.assertTrue(2.1 < gp.split_speedup(4) < 2.3)


class MultiCardWorkerHelpers(unittest.TestCase):
    def test_visible_devices_and_names(self):
        lookup = {0: {'uuid': 'GPU-83704b2a'}, 1: {'uuid': 'GPU-66595cfc'}}
        self.assertEqual(wk.cuda_visible_devices((0, 1), lookup), 'GPU-83704b2a,GPU-66595cfc')
        self.assertEqual(wk.worker_dir_name((0, 1)), 'gpu0+1')
        with self.assertRaises(KeyError):
            wk.cuda_visible_devices((0, 2), lookup)
        with self.assertRaises(ValueError):
            wk.cuda_visible_devices((1, 1), lookup)
        self.assertIn('--disable-pinned-memory', wk.COMFY_FLAGS)

        self.assertNotIn('--fast', wk.COMFY_FLAGS)
        self.assertFalse([f for f in wk.COMFY_FLAGS if 'fp16' in f], wk.COMFY_FLAGS)

    def test_on_in_the_product_with_its_proof_named(self):
        self.assertTrue(engine_options.SPLIT_PROVEN)
        self.assertTrue(engine_options.SPLIT_EARLIER_PROVEN)

    def test_the_split_cannot_turn_on_before_the_node_puts_the_attention_settings_back(self):
        pack = REPO / 'node_pack' / 'claude_creative'
        spot = (pack / 'spot.py').read_text(encoding='utf8')
        has_restore = 'def sdp_restore(' in spot and 'sdp_restore(sdp)' in spot
        self.assertTrue(has_restore or not engine_options.SPLIT_PROVEN,
                        'SPLIT_PROVEN is True, but spot.py does not put the attention settings back after a sampling run')
        self.assertTrue(engine_options.SPLIT_PROVEN or not engine_options.SPLIT_EARLIER_PROVEN,
                        'sharing with the earlier numbers cannot be proven before sharing itself')

        self.assertTrue(has_restore, 'spot.py has lost the attention restore (the two-card cure, LC35)')
        lines = [ln.split('#')[0].strip() for ln in spot.splitlines()]
        i_read = lines.index('sdp = sdp_state()')
        self.assertEqual(lines[i_read + 1:i_read + 5], ['try:', 'return executor(*a, **k)', 'finally:', 'sdp_restore(sdp)'])
        man = json.loads((pack.parent / 'MANIFEST.json').read_text(encoding='utf8'))
        self.assertEqual(man['files']['spot.py']['sha256'], hashlib.sha256((pack / 'spot.py').read_bytes()).hexdigest())


class SplitDispatch(Base):
    def inputs(self, svc, n):
        d = self.d / 'in'
        d.mkdir(parents=True, exist_ok=True)
        paths = []
        for i in range(n):
            p = d / f'q{i}.png'
            Image.fromarray(gradient(80, 64, i)).save(p)
            paths.append(p)
        return [it['id'] for it in self.add(svc, paths)['items']]

    def dispatch_lines(self, svc):
        return [ln for ln in svc.log_lines() if ln.get('event') == 'item_dispatched']

    def test_one_image_on_two_cards_by_default(self):
        svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '2', 'CU_FAKE_GPUS': '2'}, settings={})
        mids = self.inputs(svc, 1)
        jid = self.job(svc, mids, {'scale': 2})['id']
        t0 = time.monotonic()
        while time.monotonic() - t0 < 30:
            code, h, _ = svc.get('/health')
            busy = [w for w in h['engine']['workers'] if w['job_id'] == jid]
            if len(busy) == 2:
                break
            time.sleep(0.1)
        self.assertEqual([w['cards'] for w in busy], [[0, 1], [0, 1]])
        self.assertTrue(h['engine']['split']['on'])
        self.assertEqual(h['engine']['split']['topology'], {'mode': 'split', 'workers': [[0, 1]]})
        j = svc.wait_job(jid, all_done, timeout=60)
        self.assertEqual(j['items'][0]['state'], 'done')
        self.assertEqual(self.dispatch_lines(svc)[0]['msg'], 'GPU 1 + GPU 2 started q0.png')
        sent = json.loads(next((self.d / 'state' / 'workers' / 'gpu0+1' / 'fake-prompts').glob('cu_*_s0.json')).read_text())
        mg = [k for k, v in sent.items() if v['class_type'] == 'MultiGPU_WorkUnits']
        spot = next(v for v in sent.values() if v['class_type'] == 'ClaudeSpotTiles')
        self.assertEqual(len(mg), 1)
        self.assertEqual(sent[mg[0]]['inputs']['max_gpus'], 2)
        self.assertEqual(spot['inputs']['window_split'], True)

        mids2 = self.inputs(svc, 2)
        jid2 = self.job(svc, mids2, {'scale': 2})['id']
        j2 = svc.wait_job(jid2, all_done, timeout=60)
        self.assertEqual([x['state'] for x in j2['items']], ['done', 'done'])
        gpus = sorted(ln['data']['gpu'] for ln in self.dispatch_lines(svc)[1:])
        self.assertEqual(gpus, [0, 1])
        self.assertEqual(svc.shutdown(), 0)

    def test_after_a_batch_a_small_image_stays_on_a_warm_card_and_a_large_one_is_shared(self):
        svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '0.5', 'CU_FAKE_GPUS': '2'}, settings={})
        j0 = svc.wait_job(self.job(svc, self.inputs(svc, 2), {'scale': 2})['id'], all_done, timeout=60)
        self.assertEqual([x['state'] for x in j0['items']], ['done', 'done'])
        code, h, _ = svc.get('/health')
        self.assertEqual(sorted((w['gpu'], w['state']) for w in h['engine']['workers']), [(0, 'idle'), (1, 'idle')])
        d = self.d / 'in'
        Image.fromarray(gradient(768, 768, 7)).save(d / 'crop.png')
        Image.fromarray(gradient(2048, 2048, 8)).save(d / 'full.png')
        crop, full = [it['id'] for it in self.add(svc, [d / 'crop.png', d / 'full.png'])['items']]
        j1 = svc.wait_job(self.job(svc, [crop], {'scale': 2})['id'], all_done, timeout=60)
        self.assertEqual((j1['items'][0]['state'], j1['items'][0]['run']['split']), ('done', False))
        self.assertIn(self.dispatch_lines(svc)[-1]['msg'], ('GPU 1 started crop.png', 'GPU 2 started crop.png'))
        self.assertFalse([ln for ln in svc.log_lines() if ln.get('event') == 'worker_stopped'])
        j2 = svc.wait_job(self.job(svc, [full], {'scale': 2})['id'], all_done, timeout=120)
        self.assertEqual((j2['items'][0]['state'], j2['items'][0]['run']['split']), ('done', True))
        self.assertEqual(self.dispatch_lines(svc)[-1]['msg'], 'GPU 1 + GPU 2 started full.png')
        self.assertEqual(sorted(ln['data']['gpu'] for ln in svc.log_lines() if ln.get('event') == 'worker_stopped'), [0, 1])
        topo = [ln for ln in svc.log_lines() if ln.get('event') == 'topology' and ln['data']['mode'] == 'split']
        self.assertEqual([ln['data']['saving_s'] for ln in topo], [228])
        self.assertEqual(svc.shutdown(), 0)

    def test_without_the_proof_one_image_one_card(self):
        svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '0.5', 'CU_FAKE_GPUS': '2', 'CU_SPLIT_TEST': '0'}, settings={})
        mids = self.inputs(svc, 1)
        j = svc.wait_job(self.job(svc, mids, {'scale': 2})['id'], all_done, timeout=30)
        self.assertEqual(j['items'][0]['cards'], [])
        self.assertEqual(self.dispatch_lines(svc)[0]['msg'], 'GPU 1 started q0.png')
        self.assertFalse((self.d / 'state' / 'workers' / 'gpu0+1').exists())
        code, h, _ = svc.get('/health')
        self.assertEqual((h['engine']['split']['on'], h['engine']['split']['reason']), (False, 'pending_ws_proof'))
        self.assertEqual(svc.shutdown(), 0)


if __name__ == '__main__':
    unittest.main()
