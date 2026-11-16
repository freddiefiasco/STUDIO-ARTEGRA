import os
import unittest
from unittest import mock

from engine import controls, graph_v5t, planner
from service import engine_options


def build(opts=None, w=1024, h=768, scale=2, k=0, req=None):
    params, _ = controls.resolve(req or {})
    pl = planner.plan(w, h, scale)
    st = pl.stages[k]
    pw, ph = st.padded_size
    return graph_v5t.build('x.png', pw, ph, controls.stage_params(params, k), 'p', f=st.factor, s=st.supersample,
                           spot_options=opts)


def spot_id(g):
    ids = [k for k, v in g.items() if v['class_type'] == 'ClaudeSpotTiles']
    assert len(ids) == 1
    return ids[0]


class SpotOptions(unittest.TestCase):
    def test_absent_or_empty_is_the_reference_graph(self):
        ref, _ = build()
        for opts in (None, {}):
            g, _ = build(opts)
            self.assertEqual(g, ref)

    def test_only_clauded_spot_tiles_changes(self):
        ref, _ = build()
        for opts in ({'noise_prefetch': True}, {'noise_prefetch': True, 'live_preview': 'detailed'},
                     {'live_preview': 'rough'}, {'pag_fuse': True, 'batch_windows': 2, 'fp16_acc_scoped': True}):
            g, _ = build(opts)
            sid = spot_id(g)
            self.assertEqual({k: v for k, v in g.items() if k != sid}, {k: v for k, v in ref.items() if k != sid})
            self.assertEqual(g[sid]['inputs'], dict(ref[sid]['inputs'], **opts))

    def test_bad_options_refused(self):
        for opts in ({'nope': True}, {'noise_prefetch': 1}, {'live_preview': 'sometimes'}, {'batch_windows': 0},
                     {'batch_windows': True}, {'balance': 'x'}):
            with self.assertRaises(ValueError, msg=opts):
                build(opts)

    def test_samplers_named(self):
        g, info = build()
        self.assertEqual(set(info['samplers']), {'structure', 'detail'})
        s, d = g[info['samplers']['structure']], g[info['samplers']['detail']]
        self.assertEqual((s['class_type'], d['class_type']), ('KSampler', 'KSampler'))
        params, _ = controls.resolve({})
        self.assertEqual(s['inputs']['denoise'], controls.stage_params(params, 0)['structure'])
        self.assertEqual(d['inputs']['denoise'], controls.stage_params(params, 0)['denoise'])

        g2, info2 = build(w=1000, h=504, scale=6, k=2)
        self.assertEqual(g2[info2['samplers']['structure']]['inputs']['denoise'],
                         controls.stage_params(controls.resolve({'scale': 6})[0], 2)['structure'])

    def test_chain_takes_options_for_every_stage(self):
        params, _ = controls.resolve({'scale': 4})
        pl = planner.plan(768, 768, 4)
        stages = [(s.padded_size[0], s.padded_size[1], s.factor, s.supersample, controls.stage_params(params, s.index), f'p{s.index}')
                  for s in pl.stages]
        g, infos = graph_v5t.build_chain('x.png', stages, spot_options={'noise_prefetch': True})
        spots = [v for v in g.values() if v['class_type'] == 'ClaudeSpotTiles']
        self.assertEqual(len(spots), 2)
        self.assertTrue(all(v['inputs']['noise_prefetch'] is True for v in spots))


class MultiGpu(unittest.TestCase):
    def test_one_card_is_unchanged(self):
        g, _ = build()
        self.assertEqual(graph_v5t.add_multigpu(g, 1), g)

    def test_two_cards_insert_work_units(self):
        g, info = build()
        sid = spot_id(g)
        m = graph_v5t.add_multigpu(g, 2)
        mg = [k for k, v in m.items() if v['class_type'] == 'MultiGPU_WorkUnits']
        self.assertEqual(len(mg), 1)
        self.assertEqual(m[mg[0]]['inputs'], {'model': [sid, 0], 'max_gpus': 2})
        self.assertEqual(m[sid]['inputs']['window_split'], True)
        for name in ('structure', 'detail'):
            self.assertEqual(m[info['samplers'][name]]['inputs']['model'], [mg[0], 0])
        self.assertFalse([k for k, v in m.items() if k != mg[0] and v['inputs'].get('model') == [sid, 0]])
        self.assertEqual(g[sid]['inputs'].get('window_split'), None)
        with self.assertRaises(ValueError):
            graph_v5t.add_multigpu(g, 0)


STACK = {'noise_prefetch': True, 'pag_fuse': True, 'batch_windows': 2, 'fp16_acc_scoped': True}


class ProductOptions(unittest.TestCase):
    def test_default_is_the_speed_stack(self):

        self.assertEqual(graph_v5t.SPEED_STACK_ON, STACK)
        self.assertEqual(graph_v5t.SPEED_STACK_OFF, {'noise_prefetch': True})
        self.assertEqual(engine_options.spot_options(True), dict(STACK, live_preview='detailed'))
        self.assertEqual(engine_options.spot_options(False), dict(STACK, live_preview='rough'))
        self.assertNotIn('cn_reuse', engine_options.spot_options(True))
        self.assertNotIn('window_split', engine_options.spot_options(True))

        self.assertTrue(engine_options.SPLIT_PROVEN)

    def test_stack_off_is_the_10_nov_graph_options(self):

        self.assertEqual(engine_options.spot_options(True, speed_stack=False), {'noise_prefetch': True, 'live_preview': 'detailed'})
        self.assertEqual(engine_options.spot_options(False, speed_stack=False), {'noise_prefetch': True, 'live_preview': 'rough'})

    def test_there_is_no_third_combination(self):


        self.assertFalse(hasattr(engine_options, 'check_speed'))
        for bad in (None, 1, 'on'):
            with self.assertRaises(ValueError):
                graph_v5t.product_options(bad)
        with self.assertRaises(ValueError):
            graph_v5t.product_options(True, 'on_taesd')
        self.assertEqual(graph_v5t.product_options(), STACK)
        self.assertEqual(graph_v5t.product_options(False), {'noise_prefetch': True})

    def test_finish_time_factors(self):

        self.assertEqual(engine_options.eta_factor(), 0.70)
        self.assertEqual(engine_options.eta_factor(speed_stack=False), 0.947)

        self.assertEqual(engine_options.eta_factor(mode='fast'), 0.37)

        share = 1009.9 / 1269.4
        self.assertAlmostEqual((1 - share) + share * 0.63, 0.70, delta=0.01)
        self.assertAlmostEqual(engine_options.ETA_STACK_SAMPLING / share, 0.63, places=2)


        self.assertEqual((engine_options.SPLIT_SAMPLING_FACTOR, engine_options.SPLIT_SAMPLING_FACTOR_EARLIER), (1.55, 1.37))
        self.assertEqual(engine_options.eta_factor(cards=2), 0.523)
        self.assertAlmostEqual(engine_options.eta_factor(cards=2), 0.70 - 0.499 * (1 - 1 / 1.55), places=3)
        self.assertEqual(engine_options.eta_factor(False, cards=2), 0.747)
        self.assertAlmostEqual(engine_options.eta_factor(False, cards=2), 0.947 - 0.740 * (1 - 1 / 1.37), places=3)
        self.assertEqual(engine_options.eta_factor(cards=1), 0.70)


        self.assertAlmostEqual(0.70 / engine_options.eta_factor(cards=2), 913.3 / 684.7, delta=0.03)
        self.assertAlmostEqual(0.947 / engine_options.eta_factor(False, cards=2), 240.7 / 190.7, delta=0.03)
        self.assertAlmostEqual(649.968 / 418.562, engine_options.SPLIT_SAMPLING_FACTOR, delta=0.01)
        self.assertAlmostEqual(194.847 / 142.683, engine_options.SPLIT_SAMPLING_FACTOR_EARLIER, delta=0.01)
        old = engine_options.SPLIT_SAMPLING_FACTOR, engine_options.SPLIT_SAMPLING_FACTOR_EARLIER
        engine_options.SPLIT_SAMPLING_FACTOR = engine_options.SPLIT_SAMPLING_FACTOR_EARLIER = None
        try:
            self.assertEqual((engine_options.eta_factor(cards=2), engine_options.eta_factor(False, cards=2)), (0.70, 0.947))
        finally:
            engine_options.SPLIT_SAMPLING_FACTOR, engine_options.SPLIT_SAMPLING_FACTOR_EARLIER = old

        self.assertEqual(engine_options.run_info(split=False, cards=2)['factor'], 0.70)
        self.assertEqual(engine_options.run_info(frozen=True, split=True, cards=2)['factor'], 0.523)
        f = engine_options.finish_info(23.0)


        self.assertEqual(f, {'match_earlier': False, 'standard': {'minutes': 16.1, 'factor': 0.7}, 'fast': None,
                             'fast_refusal': {'reason': 'no_recipe', 'message': 'Bolt is not available. Choose Redux.'},
                             'single': {'standard': {'minutes': 16.1, 'factor': 0.7, 'cards': 1}, 'fast': None}})
        f2 = engine_options.finish_info(23.0, cards={'standard': 2, 'fast': 1})
        self.assertEqual((f2['standard'], f2['single']['standard']),
                         ({'minutes': 16.1, 'factor': 0.7}, {'minutes': 12.0, 'factor': 0.523, 'cards': 2}))
        f = engine_options.finish_info(23.0, match_earlier=True)
        self.assertEqual(f['standard'], {'minutes': 21.8, 'factor': 0.947})


        self.assertEqual(engine_options.speed_info()['factors'], {'standard': 0.7, 'match_earlier': 0.947, 'fast': 0.37,
                                                                  'faster': None})
        with mock.patch.dict(os.environ, {'CU_FAST': '1'}):
            self.assertEqual(engine_options.speed_info()['factors']['fast'], 0.37)
        on, off = engine_options.speed_info(), engine_options.speed_info(match_earlier=True)
        self.assertEqual((on['pag_fuse'], on['batch_windows'], on['fp16_acc_scoped'], on['noise_prefetch'], on['eta_factor'],
                          on['speed_stack'], on['match_earlier']), (True, 2, True, True, 0.7, True, False))
        self.assertEqual((off['pag_fuse'], off['batch_windows'], off['fp16_acc_scoped'], off['noise_prefetch'],
                          off['eta_factor'], off['speed_stack'], off['match_earlier']), (False, 1, False, True, 0.947, False, True))

    def test_run_info(self):
        self.assertEqual(engine_options.run_info(), {'mode': 'standard', 'match_earlier': False, 'speed_stack': True,
                                                     'frozen': False, 'split': False, 'factor': 0.7, 'faster': False})
        r = engine_options.run_info(match_earlier=True, frozen=True)
        self.assertEqual((r['match_earlier'], r['speed_stack'], r['frozen'], r['factor']), (True, False, True, 0.947))

    def test_split_and_fast_health(self):
        cards = [{'index': 0, 'mem_free_gb': 31.2}, {'index': 1, 'mem_free_gb': 14.04}]

        s = engine_options.split_info(False, [0, 1], cards, proven=False)
        self.assertEqual((s['available'], s['proven'], s['on'], s['reason']), (False, False, False, 'pending_ws_proof'))
        self.assertEqual(s['message'], 'Each image runs on one GPU in this version.')
        self.assertEqual(s['cards'], [{'gpu': 0, 'vram_free_gb': 31.2, 'above_floor': True},
                                      {'gpu': 1, 'vram_free_gb': 14.0, 'above_floor': False}])


        self.assertEqual(s['floor_gb'], 19.0)

        s = engine_options.split_info(True, [0, 1], cards)
        self.assertEqual((s['proven'], s['available'], s['on'], s['reason']), (True, True, True, 'card_under_floor'))


        self.assertEqual(s['message'], 'GPU 2 has 14 GB free; sharing an image needs 19 GB.')
        self.assertLessEqual(len(engine_options.under_floor_text([(1, 18.74)], 19.0)), 80)
        both = [{'index': 0, 'mem_free_gb': 14.0}, {'index': 1, 'mem_free_gb': 12.2}]
        self.assertEqual(engine_options.split_info(True, [0, 1], both, proven=True)['message'],
                         'GPU 1 and GPU 2 have 14 GB and 12 GB free; sharing an image needs 19 GB.')
        edge = [{'index': 0, 'mem_free_gb': 28.2}, {'index': 1, 'mem_free_gb': 19.0}]
        self.assertEqual(engine_options.split_info(True, [0, 1], edge, proven=True)['reason'], None)


        for free in (18.9, 18.96, 18.6):
            under = [{'index': 0, 'mem_free_gb': 28.2}, {'index': 1, 'mem_free_gb': free}]
            s = engine_options.split_info(True, [0, 1], under, proven=True)
            self.assertEqual((s['reason'], s['message']), ('card_under_floor', f'GPU 2 has {str(free)[:4]} GB free; '
                             'sharing an image needs 19 GB.'), free)
        self.assertEqual(engine_options.under_floor_text([(1, 18.5)], 19.0), 'GPU 2 has 18 GB free; sharing an '
                         'image needs 19 GB.')
        self.assertEqual(engine_options.under_floor_text([(0, 19.0), (1, 9.6)], 19.0, tail='a.png runs on one GPU'),
                         'GPU 1 and GPU 2 have 18.9 GB and 10 GB free; sharing an image needs 19 GB, so a.png runs '
                         'on one GPU.')
        ok = [{'index': 0, 'mem_free_gb': 31.0}, {'index': 1, 'mem_free_gb': 30.0}]
        s = engine_options.split_info(True, [0, 1], ok, proven=True)
        self.assertEqual((s['on'], s['reason'], s['message']), (True, None, None))
        s = engine_options.split_info(False, [0, 1], ok, proven=True)
        self.assertEqual((s['available'], s['on'], s['reason'], s['message']), (True, False, 'turned_off', None))
        s = engine_options.split_info(True, [0], ok, proven=True)
        self.assertEqual((s['available'], s['on'], s['reason'], s['message']),
                         (False, False, 'one_card', 'One GPU is in use, so each image runs on it.'))


        self.assertTrue(engine_options.SPLIT_EARLIER_PROVEN)


        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop('CU_FAST_SPLIT', None)
            self.assertEqual((engine_options.split_allowed(), engine_options.split_allowed(match_earlier=True),
                              engine_options.split_allowed('fast')), (True, True, True))
            with mock.patch.dict(os.environ, {'CU_FAST_SPLIT': '0'}):
                self.assertFalse(engine_options.split_allowed('fast'))
        s = engine_options.split_info(True, [0, 1], ok, match_earlier=True)
        self.assertEqual((s['available'], s['on'], s['reason'], s['message']), (True, True, None, None))

        self.assertFalse(engine_options.split_allowed(match_earlier=True, earlier_proven=False))
        s = engine_options.split_info(True, [0, 1], ok, proven=True, match_earlier=True, earlier_proven=False)
        self.assertEqual((s['available'], s['on'], s['reason'], s['message']),
                         (True, False, 'match_earlier', '"Match earlier results" is on, so each image runs on one GPU.'))
        self.assertEqual(engine_options.split_info(False, [0, 1], ok, proven=True, match_earlier=True,
                                                   earlier_proven=False)['reason'], 'turned_off')
        self.assertEqual(engine_options.split_info(True, [0, 1], ok, proven=False, match_earlier=True)['reason'],
                         'pending_ws_proof')


        self.assertEqual(engine_options.fast_info(), engine_options.fast_info(proven=True))

        os.environ.pop('CU_FAST_SPLIT', None)
        self.assertEqual(engine_options.fast_info(proven=True), {'available': True, 'reason': None, 'message': None,
                                                      'recipe': 'H8-e8-s25-c5-p3-k+so16+stk', 'version': '1', 'factor': 0.37,
                                                      'factors': {'first_stage': 0.37}, 'split': True,
                                                      'looks': ['Light', 'Default'], 'max_factor': 2})
        with mock.patch.dict(os.environ, {'CU_FAST_SPLIT': '0'}):
            self.assertIs(engine_options.fast_info(proven=True)['split'], False)
        self.assertEqual(engine_options.fast_info(proven=False), {'available': False, 'reason': 'pending_proof',
                                                      'message': 'Bolt is not in this version.',
                                                      'recipe': 'H8-e8-s25-c5-p3-k+so16+stk', 'version': '1', 'factor': None,
                                                      'factors': None, 'split': False, 'looks': ['Light', 'Default'],
                                                      'max_factor': 2})

    def test_detailed_state(self):
        self.assertEqual(engine_options.detailed_state(True, True), {'available': True, 'on': True, 'reason': None})
        self.assertEqual(engine_options.detailed_state(False, True)['reason'], 'turned_off')
        self.assertEqual(engine_options.detailed_state(True, False), {'available': False, 'on': False, 'reason': 'decoder_missing'})


if __name__ == '__main__':
    unittest.main()
