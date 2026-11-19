"""The Large-image stage graph (engine/graph_banded.py) keeps every classic input value of the same stage (engine design
section 2.2): models, DAT tiles, the canvas and hint sizes, Canny, ControlNet strengths and end percents, the samplers, the
ClaudeSpotTiles options, the VAE tiling, SAM settings, V4F, fin_b0_hi and the toe. The memory profiles and the two-card split
reach the fork (T11, G0f). Sizes only."""
import unittest

from engine import controls, graph_banded, graph_v5t, planner
from service import memory_policy


def by_class(g, cls):
    return [n['inputs'] for n in g.values() if n['class_type'] == cls]


def values(inputs):
    return {k: v for k, v in inputs.items() if not (isinstance(v, list) and len(v) == 2 and isinstance(v[0], str))}


STAGES = [(1752, 1096, 2, 2, 0), (7000, 4376, 2, 1, 1), (1000, 504, 1.5, 2, 2), (2000, 2000, 2, 1.5, 0)]


class SameValuesAsTheClassicStage(unittest.TestCase):
    def pair(self, w, h, f, s, k, protect=None, **kw):
        req = {} if protect is None else {'protect': protect}
        p = controls.stage_params(controls.resolve(req)[0], k)
        from fractions import Fraction
        fr, sr = Fraction(f).limit_denominator(8), Fraction(s).limit_denominator(8)
        c, ci = graph_v5t.build_product('x.png', w, h, p, 'cu_j_i_s0', f=fr, s=sr, **kw)
        b, bi = graph_banded.build_product('work/in.plane', w, h, p, 'cu_j_i_s0', 'work/planes/s0', 'run1', f=fr, s=sr, **kw)
        return c, ci, b, bi

    def test_every_value(self):
        for (w, h, f, s, k) in STAGES:
            for protect in (None, [], list(controls.PROTECT_ORDER)):
                for kw in ({}, {'live_preview': 'detailed'}, {'speed_stack': False}, {'faster': True},
                           {'creative_first': True}):
                    c, ci, b, bi = self.pair(w, h, f, s, k, protect, **kw)
                    key = (w, h, f, s, k, protect, kw)
                    for cls in ('CheckpointLoaderSimple', 'PerturbedAttentionGuidance', 'CLIPTextEncode', 'UpscaleModelLoader',
                                'ControlNetLoader', 'KSampler'):
                        self.assertEqual([values(x) for x in by_class(c, cls)], [values(x) for x in by_class(b, cls)],
                                         (key, cls))
                    self.assertEqual([values(x) for x in by_class(c, 'ControlNetApplyAdvanced')],
                                     [values(x) for x in by_class(b, 'CUControlNetApplyPlane')], key)
                    spot_c = values(by_class(c, 'ClaudeSpotTiles')[0])
                    self.assertEqual(spot_c, values(by_class(b, 'ClaudeSpotTilesBanded')[0]), key)
                    dat = values(by_class(c, 'ClaudeUpscaleModelTiled')[0])
                    cv = by_class(b, 'CUUpscaleCanvas')[0]
                    self.assertEqual({x: cv[x] for x in dat}, dat, key)
                    rw, rh = ci['render']
                    self.assertEqual((cv['render_width'], cv['render_height']), (rw, rh))
                    self.assertEqual((cv['init_width'], cv['init_height']), ci['output'])
                    blur = values(by_class(c, 'ImageBlur')[0])
                    self.assertEqual({x: by_class(b, 'CUBlurPlane')[0][x] for x in blur}, blur, key)
                    canny = values(by_class(c, 'ClaudeCannyTiled')[0])
                    self.assertEqual({x: by_class(b, 'CUCannyPlane')[0][x] for x in canny}, canny, key)
                    for enc in by_class(c, 'VAEEncodeTiled'):
                        e = by_class(b, 'CUEncodePlane')[0]
                        self.assertEqual((enc['tile_size'], enc['overlap']), (e['tile_size'], e['overlap']))
                    for dec in by_class(b, 'CUDecodePlane'):
                        self.assertEqual((dec['tile_size'], dec['overlap']), (1024, 64))
                        self.assertEqual((dec['width'], dec['height']), ci['output'])
                    fin_c = values(by_class(c, 'ClaudeV4Finish')[0])
                    fin_b = values(by_class(b, 'CUFinishBanded')[0])
                    self.assertEqual({x: fin_b.get(x) for x in fin_c}, fin_c, key)
                    toe = values(by_class(c, 'ClaudeShadowToe')[0])
                    self.assertEqual((fin_b['toe_amount'], fin_b['toe_scale']), (toe['amount'], toe['scale']), key)
                    self.assertEqual([values(x) for x in by_class(c, 'SAM3_Detect')],
                                     [{x: v for x, v in values(y).items() if x not in ('plane_dir', 'run_id')}
                                      | {'individual_masks': False} for y in by_class(b, 'CUSam3DetectLean')], key)
                    self.assertIsNotNone(bi['samplers'])
                    self.assertEqual(bi['run_order'], ci['run_order'])
                    self.assertEqual(bi['render'], ci['render'])

    def test_no_whole_image_node_is_left(self):
        _, _, b, _ = self.pair(1752, 1096, 2, 2, 0, list(controls.PROTECT_ORDER))
        left = {n['class_type'] for n in b.values()} & {'LoadImage', 'ImageScale', 'ImageBlur', 'ClaudeCannyTiled', 'VAEEncodeTiled',
                                                         'VAEDecodeTiled', 'SAM3_Detect', 'ClaudeMaskUnion', 'ClaudeV4Finish',
                                                         'ClaudeShadowToe', 'SaveImage', 'ClaudeSpotTiles',
                                                         'ClaudeUpscaleModelTiled', 'ControlNetApplyAdvanced'}
        self.assertEqual(left, set())
        for n in b.values():
            if n['class_type'] in graph_banded.NODE_SPECS:
                req, _ = graph_banded.NODE_SPECS[n['class_type']]
                self.assertEqual([r for r in req if r not in n['inputs']], [], n['class_type'])
                opt = graph_banded.NODE_OPTIONAL.get(n['class_type'], ())
                extra = set(n['inputs']) - set(req) - set(opt)
                self.assertEqual(extra, set(), n['class_type'])

    def test_every_node_has_the_run_id_and_planes_stay_in_the_stage_folder(self):
        _, _, b, bi = self.pair(1752, 1096, 2, 2, 0, list(controls.PROTECT_ORDER))
        for n in b.values():
            if 'run_id' in graph_banded.NODE_SPECS.get(n['class_type'], ((), ()))[0]:
                self.assertEqual(n['inputs']['run_id'], 'run1')
            if 'plane_dir' in n['inputs']:
                self.assertTrue(n['inputs']['plane_dir'].startswith('work/planes/s0'))
        self.assertEqual(sorted(bi['planes']), sorted(['canvas', 'init', 'hint', 'edges', 'creative', 'structure', 'output']))

    def test_the_split_finish_is_two_prompts(self):
        p = controls.resolve({'protect': list(controls.PROTECT_ORDER)})[0]
        a, ai = graph_banded.build_stage('in.plane', 1752, 1096, p, 'pre', 'pl', 'r', part='A')
        b, bi = graph_banded.build_stage('in.plane', 1752, 1096, p, 'pre', 'pl', 'r', part='B')
        self.assertEqual([n['class_type'] for n in a.values()].count('CUPlaneCheckpoint'), 1)
        self.assertNotIn('CUFinishBanded', {n['class_type'] for n in a.values()})
        cls_b = {n['class_type'] for n in b.values()}
        self.assertEqual(cls_b, {'CUPlaneInput', 'CUFinishBanded'})     # no model loader in prompt B
        ck = next(n for n in a.values() if n['class_type'] == 'CUPlaneCheckpoint')['inputs']
        self.assertEqual(sorted(k for k in ck if k in graph_banded.CHECKPOINT_ROLES),
                         ['creative', 'init', 'protect', 'release', 'structure'])

    def test_variants_this_build_cannot_make_are_refused(self):
        p = controls.resolve({})[0]
        with self.assertRaises(ValueError):
            graph_banded.build_stage('in.plane', 1752, 1096, p, 'x', 'pl', 'r', constants={'finish': 'bxf-1h'})
        with self.assertRaises(ValueError):
            graph_banded.build_stage('in.plane', 1752, 1096, p, 'x', 'pl', 'r', constants={'canvas': 'other'})

    def test_32000_px_stage(self):
        p = controls.stage_params(controls.resolve({})[0], 2)
        g, info = graph_banded.build_stage('in.plane', 16000, 10000, p, 'x', 'pl', 'r', f=2, s=1, output_size=(32000, 20000))
        self.assertEqual(info['output'], (32000, 20000))
        fin = by_class(g, 'CUFinishBanded')[0]
        self.assertEqual((fin['output_width'], fin['output_height']), (32000, 20000))


class ProfilesAndCards(unittest.TestCase):
    def graph(self):
        p = controls.resolve({})[0]
        return graph_banded.build_product('in.plane', 1752, 1096, p, 'x', 'pl', 'r', live_preview='rough')

    def test_balanced_reaches_the_fork(self):
        g, info = self.graph()
        g2, info2 = memory_policy.apply_graph(g, info, memory_policy.PROFILES['balanced'])
        self.assertEqual(by_class(g2, 'ClaudeSpotTilesBanded')[0]['batch_windows'], 1)
        self.assertEqual(info2['spot_options']['batch_windows'], 1)
        g3, _ = memory_policy.apply_graph(g, info, memory_policy.PROFILES['reference'])
        self.assertEqual(g3, g)

    def test_two_cards_static_split(self):
        g, _ = self.graph()
        g2 = graph_banded.add_multigpu(g, 2)
        spot = next(k for k, v in g2.items() if v['class_type'] == 'ClaudeSpotTilesBanded')
        self.assertTrue(g2[spot]['inputs']['window_split'])
        self.assertEqual(g2[spot]['inputs']['balance'], 'static')
        mg = [v for v in g2.values() if v['class_type'] == 'MultiGPU_WorkUnits']
        self.assertEqual(len(mg), 1)
        users = [v for v in g2.values() if v['class_type'] == 'KSampler']
        self.assertTrue(all(u['inputs']['model'][0] != spot for u in users))
        with self.assertRaises(ValueError):
            graph_banded.add_multigpu(g, 2, balance='auto')


if __name__ == '__main__':
    unittest.main()
