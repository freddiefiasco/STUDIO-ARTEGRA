"""Graph option validation and multi-GPU graph transformation tests."""
import unittest

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
        # a 1.5x stage adds an ImageScale before the samplers: the ids move, the names follow
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
        self.assertEqual(g[sid]['inputs'].get('window_split'), None)      # the input graph is not changed
        with self.assertRaises(ValueError):
            graph_v5t.add_multigpu(g, 0)

