import json
import unittest
from pathlib import Path

from engine import graph_v5t, planner
from service import engine_options
from tests.service.test_fast_v5 import FastBase, NO_OVERRIDES
from tests.service.test_integration import all_done
from tests.service.test_port import spot_inputs


class TwoCardBase(FastBase):
    def two_cards(self, **env):
        self.svc = self.service(env=dict(NO_OVERRIDES, CU_FAKE_STAGE_SECONDS='1', CU_FAKE_GPUS='2', **env), settings={})
        return self.svc

    def sent_any(self, jid, iid):
        hits = sorted((self.d / 'state' / 'workers').glob(f'*/fake-prompts/cu_{jid}_{iid}_s0.json'))
        self.assertEqual(len(hits), 1, [str(h) for h in hits])
        return hits[0].parents[1].name, json.loads(hits[0].read_text(encoding='utf8'))

    def plan_single(self, w=1024, h=768):
        code, p, _ = self.svc.post('/api/plan', {'width': w, 'height': h, 'scale': 2})
        self.assertEqual(code, 200, p)
        return planner.plan(w, h, 2).minutes, p['finish']

    def events(self, name):
        return [ln for ln in self.svc.log_lines() if ln.get('event') == name]

    def lanes(self, mids):
        j = self.svc.wait_job(self.job(self.svc, mids, {'scale': 2, 'mode': 'fast'})['id'], all_done, timeout=120)
        self.assertEqual([x['state'] for x in j['items']], ['done', 'done'], json.dumps(j)[:1500])
        cards = []
        for it in j['items']:
            run = it['run']
            self.assertEqual((run['mode'], run['split'], run['factor'], len(run['cards'])), ('fast', False, 0.37, 1))
            cards += run['cards']
            folder, g = self.sent_any(j['id'], it['id'])
            self.assertEqual(folder, f'gpu{run["cards"][0]}')
            self.assertEqual(g, self.stage_graph(j, it['id'], fast=True))
            self.assertNotIn('window_split', spot_inputs(g))
            self.assertTrue(Path(it['output']).name.endswith('_cu2x_bolt.png'))
        self.assertEqual(sorted(cards), [0, 1])
        return j


class AsBuilt(TwoCardBase):
    def test_one_card_each_and_no_two_card_speed_shown(self):


        self.assertTrue(engine_options.FAST_SPLIT_PROVEN)
        self.two_cards(CU_FAST='1', CU_FAST_SPLIT='0')
        h = self.health()
        self.assertEqual((h['engine']['fast']['available'], h['engine']['fast']['split']), (True, False))
        self.assertTrue(h['engine']['split']['on'])
        m, f = self.plan_single()
        self.assertEqual(f['single']['fast'], {'minutes': round(m * 0.37, 1), 'factor': 0.37, 'cards': 1})
        self.assertEqual(f['single']['standard'], {'minutes': round(m * 0.523, 1), 'factor': 0.523, 'cards': 2})
        self.lanes(self.inputs(2))
        self.assertEqual(self.svc.shutdown(), 0)


class Shared(TwoCardBase):
    def test_one_fast_image_on_both_cards_then_standard_then_lanes(self):


        self.two_cards(CU_FAST='1')
        h = self.health()
        self.assertEqual((h['engine']['fast']['available'], h['engine']['fast']['split']), (True, True))
        m, f = self.plan_single()

        self.assertEqual(engine_options.FAST_SPLIT_SAMPLING_FACTOR, 1.59)
        self.assertEqual(f['single']['fast'], {'minutes': round(m * 0.308, 1), 'factor': 0.308, 'cards': 2})
        self.assertEqual(f['fast'], {'minutes': round(m * 0.37, 1), 'factor': 0.37})
        mids = self.inputs(4)

        ja = self.svc.wait_job(self.job(self.svc, [mids[0]], {'scale': 2, 'mode': 'fast'})['id'], all_done, timeout=120)
        ia = ja['items'][0]
        self.assertEqual(ia['state'], 'done', json.dumps(ja)[:1500])
        self.assertEqual((ia['run']['mode'], ia['run']['split'], ia['run']['cards'], ia['run']['factor']),
                         ('fast', True, [0, 1], 0.308))
        self.assertEqual(ia['run']['factor'], f['single']['fast']['factor'])
        folder, g = self.sent_any(ja['id'], 'i001')
        self.assertEqual(folder, 'gpu0+1')
        bal = spot_inputs(g)['balance']
        self.assertEqual(g, json.loads(json.dumps(graph_v5t.add_multigpu(self.stage_graph(ja, 'i001', fast=True), 2,
                                                                         balance=bal))))
        self.assertEqual((spot_inputs(g)['window_split'], spot_inputs(g)['seam_overlap']), (True, 16))
        side = self.side(ia)
        self.assertEqual((side['engine']['graph'], side['engine']['spot_options']['window_split'],
                          side['timings']['stages'][0]['run_order']), ('engine/fast_recipe.py', True, ['structure', 'detail']))
        self.assertTrue(Path(ia['output']).name.endswith('_cu2x_bolt.png'))
        self.assertEqual(self.started_lines(ja['id'])['i001'][-len(', Bolt'):], ', Bolt')
        self.assertTrue(any(ln['msg'].startswith('GPU 1 + GPU 2 started ') for ln in self.events('item_dispatched')
                            if ln.get('job') == ja['id']))
        starts = len(self.events('worker_starting'))

        jb = self.svc.wait_job(self.job(self.svc, [mids[1]], {'scale': 2})['id'], all_done, timeout=120)
        ib = jb['items'][0]
        self.assertEqual((ib['state'], ib['run']['mode'], ib['run']['split'], ib['run']['cards'], ib['run']['factor']),
                         ('done', 'standard', True, [0, 1], 0.523))
        folder, gb = self.sent_any(jb['id'], 'i001')
        self.assertEqual(folder, 'gpu0+1')
        want = self.stage_graph(jb, 'i001', creative_first=engine_options.creative_first_on(shared=True))
        self.assertEqual(gb, json.loads(json.dumps(graph_v5t.add_multigpu(want, 2, balance=spot_inputs(gb)['balance']))))
        self.assertNotIn('seam_overlap', spot_inputs(gb))
        self.assertEqual(len(self.events('worker_starting')), starts)

        self.lanes(mids[2:])
        self.assertTrue(any('one image per card again' in (ln.get('msg') or '') for ln in self.events('worker_stopped')))
        self.assertEqual(self.svc.shutdown(), 0)


if __name__ == '__main__':
    unittest.main()
