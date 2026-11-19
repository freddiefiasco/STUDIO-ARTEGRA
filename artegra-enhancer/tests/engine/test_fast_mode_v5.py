import ast
import importlib
import json
import os
import re
import sys
import unittest
from fractions import Fraction
from pathlib import Path
from unittest import mock

from engine import controls, fast_recipe, graph_v5t, planner, run_order, schedule
from service import comfy, engine_options

REPO = Path(__file__).resolve().parents[2]
R3 = Path(os.environ.get('CU_FAST_R3_DIR') or Path(__file__).resolve().parent / 'no-research-notes')
INSTALLED = fast_recipe.RECIPE
RID = 'H8-e8-s25-c5-p3-k+so16+stk'

R3_TIMES = {'S4': ((2048, 2048), 474.1), 'S1': ((3500, 2188), 805.9), 'S2': ((3840, 2400), 996.9), 'S3': ((3000, 2000), 644.4)}


def canonical(graph):
    return json.dumps(graph, sort_keys=True, separators=(',', ':')).encode('utf8')


def exact(v):
    fr = Fraction(v).limit_denominator(8)
    return int(fr) if fr.denominator == 1 else fr


def standard_graphs(module=graph_v5t):
    out = []
    for req, (w, h) in (({}, (1024, 768)), ({'preset': 'Strong', 'scale': 4}, (960, 1280)),
                        ({'custom': True, 'creativity': 70, 'resemblance': 40, 'restoration': 20, 'scale': 6,
                          'protect': ['people', 'architecture'], 'seed': '7'}, (1000, 504)),
                        ({'preset': 'Light'}, (768, 768))):
        params, eff = controls.resolve(req)
        for st in planner.plan(w, h, eff['scale']).stages:
            for stack in (True, False):
                g, info = module.build_product('in.png', *st.padded_size, controls.stage_params(params, st.index), f'p{st.index}',
                                               f=exact(st.factor), s=exact(st.supersample), speed_stack=stack,
                                               live_preview='detailed')
                out.append(canonical(g))
    return out


def stand_in(log=None):
    def build(input_name, w, h, params, prefix, f, s, live_preview):
        params['steps'] = 8
        params['cfg'] = 1.5
        params['prompt'] = 'fast'
        g, info = graph_v5t.build_product(input_name, w, h, params, prefix, f=f, s=s, speed_stack=True, live_preview=live_preview)
        for n in g.values():
            if n['class_type'] == 'KSampler':
                n['inputs']['sampler_name'] = 'lcm'
        info['spot_options']['batch_windows'] = 4
        if log is not None:
            log.append(prefix)
        return g, info
    return {'name': 'unit-fast', 'version': '3', 'proof': 'unit test', 'eta_factor': 0.25, 'models': {'loras': ['x.safetensors']},
            'looks': ('Light', 'Default'), 'max_factor': 2, 'speed_stack': True, 'split_ok': False, 'build': build}


def fast_and_standard(look='Default', size=(1024, 768), live='detailed', seed=None):
    req = {'preset': look} if seed is None else {'preset': look, 'seed': str(seed)}
    params, _ = controls.resolve(req)
    pk = controls.stage_params(params, 0)
    std, sinfo = graph_v5t.build_product('in.png', *size, pk, 'p', speed_stack=True, live_preview=live)
    fast, finfo = fast_recipe.build('in.png', *size, pk, 'p', live_preview=live)
    return std, sinfo, fast, finfo


class Restore(unittest.TestCase):
    def tearDown(self):
        fast_recipe.RECIPE = INSTALLED


class Recipe(Restore):
    def test_r_own_is_installed_with_the_slots_keys(self):
        r = fast_recipe.recipe()
        self.assertIs(r, INSTALLED)
        self.assertEqual((r['name'], r['version'], r['eta_factor'], r['eta_factors']), (RID, '1', 0.37, {'first_stage': 0.37}))
        self.assertEqual(r['lora'], {'file': 'Hyper-SDXL-8steps-CFG-lora.safetensors', 'bytes': 787359648, 'strength': 0.25,
                                     'sha256': '55b51334c85061afff5eff7c550b61963c8b8607a5868bbe4f26db49374719b1',
                                     'source': 'ByteDance/Hyper-SD revision bc08d970a87c74c71209491d64e3525845698863'})
        self.assertEqual(r['models'], {'loras': ['Hyper-SDXL-8steps-CFG-lora.safetensors']})
        self.assertEqual((r['steps'], r['cfg'], r['pag'], r['seam_overlap'], tuple(r['looks']), r['max_factor']),
                         (8, 5.0, 3.0, 16, ('Light', 'Default'), 2))
        self.assertEqual((r['speed_stack'], r['split_ok']), (True, False))
        self.assertEqual(fast_recipe.LOOK_NAMES, tuple(controls.PRESET_ORDER))
        self.assertEqual(fast_recipe.FACTORS, tuple(controls.SCALES))
        self.assertFalse(hasattr(fast_recipe, 'NOT_INSTALLED'))
        d = fast_recipe.describe()
        self.assertEqual((d['installed'], d['recipe'], d['factor'], d['factors'], d['looks'], d['max_factor'], d['split']),
                         (True, RID, 0.37, {'first_stage': 0.37}, ['Light', 'Default'], 2, False))

    def test_the_code_is_fastmode_r3_section_7s(self):
        report = R3 / 'FASTMODE-R3.md'
        if not report.is_file():
            self.skipTest('the Fast research notes are not part of this repository (set CU_FAST_R3_DIR)')
        text = report.read_text(encoding='utf8')
        block = re.search(r'```python\n(# engine/fast_recipe\.py, in the version that installs it.*?)```', text, re.S).group(1)
        theirs = ast.parse(block)
        ours = ast.parse((REPO / 'engine' / 'fast_recipe.py').read_text(encoding='utf8'))

        def defs(tree):
            out = {}
            for node in tree.body:
                if isinstance(node, ast.FunctionDef):
                    out[node.name] = ast.dump(node, include_attributes=False)
                elif isinstance(node, ast.Assign):
                    out[','.join(ast.dump(t) for t in node.targets)] = ast.dump(node.value, include_attributes=False)
                elif isinstance(node, ast.ImportFrom):
                    out['import ' + node.module] = sorted(a.name for a in node.names)
            return out
        t, o = defs(theirs), defs(ours)
        self.assertEqual(len(t), 7)
        self.assertIn('_build', t)
        for k, v in t.items():
            self.assertIn(k, o, k)
            self.assertEqual(o[k], v, k)

    def test_offered_since_its_new_proof_and_the_override(self):


        self.assertTrue(engine_options.FAST_PROVEN)
        self.assertTrue(engine_options.FAST_SPLIT_PROVEN)
        offered = {'available': True, 'reason': None, 'message': None, 'recipe': RID, 'version': '1', 'factor': 0.37,
                   'factors': {'first_stage': 0.37}, 'split': True, 'looks': ['Light', 'Default'], 'max_factor': 2}
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop('CU_FAST', None)
            os.environ.pop('CU_FAST_SPLIT', None)
            self.assertEqual(engine_options.fast_info(), offered)
            with mock.patch.dict(os.environ, {'CU_FAST_SPLIT': '0'}):
                self.assertEqual(engine_options.fast_info(), dict(offered, split=False))
            self.assertEqual(engine_options.speed_info()['factors']['fast'], 0.37)
            with mock.patch.dict(os.environ, {'CU_FAST': '1'}):
                self.assertEqual(engine_options.fast_info(), offered)
                self.assertEqual(engine_options.fast_info(files_ok=False)['reason'], 'files_missing')
                self.assertEqual(engine_options.fast_info(files_ok=False)['message'],
                                 'Bolt cannot be used: a file it needs cannot be read.')

                self.assertEqual({k: v for k, v in engine_options.fast_info(files_ok=None).items()
                                  if k in ('available', 'reason', 'message', 'factor')},
                                 {'available': False, 'reason': 'checking', 'message': 'Checking the files Bolt needs.',
                                  'factor': None})
                self.assertEqual(engine_options.speed_info()['factors']['fast'], 0.37)
            with mock.patch.dict(os.environ, {'CU_FAST': '0'}):
                self.assertEqual(engine_options.fast_info(), {
                    'available': False, 'reason': 'pending_proof', 'message': 'Bolt is not in this version.',
                    'recipe': RID, 'version': '1', 'factor': None, 'factors': None, 'split': False,
                    'looks': ['Light', 'Default'], 'max_factor': 2})
                self.assertIsNone(engine_options.speed_info()['factors']['fast'])
                self.assertIsNone(engine_options.finish_info(20.0, fast_available=False)['fast'])
                self.assertEqual(engine_options.fast_info(proven=None)['reason'], 'pending_proof')
                self.assertTrue(engine_options.fast_info(proven=True)['available'])

    def test_sidecar_fields(self):
        _, _, _, info = fast_and_standard('Light')
        self.assertEqual(info['fast'], {
            'recipe': RID, 'version': '1',
            'lora': {'file': 'Hyper-SDXL-8steps-CFG-lora.safetensors', 'bytes': 787359648,
                     'sha256': '55b51334c85061afff5eff7c550b61963c8b8607a5868bbe4f26db49374719b1', 'strength': 0.25},
            'steps': 8, 'cfg': 5.0, 'pag': 3.0, 'seam_overlap': 16,
            'schedule': "pick A's own: KSampler, 8 executed steps of int(8 / denoise)",
            'ends': {'detail': 0.9677, 'structure': 0.9787}})
        self.assertEqual(info['spot_options']['seam_overlap'], 16)
        json.dumps(info['fast'])


class T3Changes(Restore):
    def changes(self, std, fast):
        added = {k: v for k, v in fast.items() if k not in std}
        changed = {}
        for k, v in std.items():
            self.assertIn(k, fast)
            self.assertEqual(fast[k]['class_type'], v['class_type'], k)
            diff = {i: (v['inputs'].get(i), fast[k]['inputs'].get(i)) for i in set(v['inputs']) | set(fast[k]['inputs'])
                    if v['inputs'].get(i, '<absent>') != fast[k]['inputs'].get(i, '<absent>')}
            if diff:
                changed[k] = diff
        return added, changed

    def test_the_five_changes_and_nothing_else(self):
        for look in ('Light', 'Default'):
            for size in ((1024, 768), (768, 768), (2048, 2048)):
                for live in ('detailed', 'rough'):
                    std, sinfo, fast, finfo = fast_and_standard(look, size, live)
                    added, changed = self.changes(std, fast)
                    self.assertEqual(len(added), 1, (look, size))
                    (lid, lora), = added.items()
                    ck = next(k for k, n in std.items() if n['class_type'] == 'CheckpointLoaderSimple'
                              and n['inputs']['ckpt_name'] == graph_v5t.MODELS['ckpt'])
                    self.assertEqual(lora, {'class_type': 'LoraLoaderModelOnly', 'inputs': {
                        'model': [ck, 0], 'lora_name': 'Hyper-SDXL-8steps-CFG-lora.safetensors', 'strength_model': 0.25}})
                    pag = next(k for k, n in std.items() if n['class_type'] == 'PerturbedAttentionGuidance')
                    spot = next(k for k, n in std.items() if n['class_type'] == 'ClaudeSpotTiles')
                    det, struct = sinfo['samplers']['detail'], sinfo['samplers']['structure']
                    c1, c3 = std[det]['inputs']['positive'][0], std[struct]['inputs']['positive'][0]
                    c2 = std[c3]['inputs']['positive'][0]
                    params, _ = controls.resolve({'preset': look})
                    e1 = schedule.end_mid('karras', 8, params['denoise'], params['tile_frac'])
                    e3 = schedule.end_mid('karras', 8, params['structure'], params['s_line_frac'])
                    want = {pag: {'model': (std[pag]['inputs']['model'], [lid, 0])},
                            spot: {'seam_overlap': (None, 16)},
                            det: {'steps': (30, 8), 'cfg': (6.0, 5.0)}, struct: {'steps': (30, 8), 'cfg': (6.0, 5.0)},
                            c1: {'end_percent': (std[c1]['inputs']['end_percent'], e1)},
                            c3: {'end_percent': (std[c3]['inputs']['end_percent'], e3)}}
                    self.assertEqual(changed, want, (look, size, live))
                    self.assertNotIn(c2, changed)
                    self.assertEqual(std[c2]['inputs']['end_percent'], 1.0)
                    classes = {n['class_type'] for n in fast.values()}
                    self.assertFalse(classes & {'SamplerCustom', 'KSamplerSelect', 'KarrasScheduler'})
                    for n in fast.values():
                        for name in ('clip', 'vae'):
                            if name in n['inputs'] and n['class_type'] not in ('SAM3_Detect',):
                                src = n['inputs'][name][0]
                                self.assertEqual(fast[src]['class_type'], 'CheckpointLoaderSimple')
                    self.assertEqual(finfo['fast_ends'], {'detail': e1, 'structure': e3})
                    self.assertEqual(finfo['samplers'], sinfo['samplers'])

    def test_equals_round_3s_rendered_graphs_node_for_node(self):
        spec_p = R3 / 'specs' / 'r3a.json'
        if not spec_p.is_file():
            self.skipTest('the Fast research notes are not part of this repository (set CU_FAST_R3_DIR)')
        spec = json.loads(spec_p.read_text(encoding='utf8'))
        import hashlib
        n = 0
        for p in spec['prompts']:
            e = spec['experiment']['prompts'][p['name']]
            if e['recipe_id'] != RID or e['factor'] != 2:
                continue
            raw = (R3 / 'wf' / 'r3a' / f'{p["name"]}.json').read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), e['graph_sha256'], p['name'])
            ref = json.loads(raw)
            fin = next(v for v in ref.values() if v['class_type'] == 'ClaudeV4Finish')
            init = ref[fin['inputs']['init'][0]]
            self.assertEqual((init['class_type'], init['inputs']['upscale_method']), ('ImageScale', 'lanczos'))
            w, h = init['inputs']['width'] // 2, init['inputs']['height'] // 2
            params, _ = controls.resolve({'preset': e['look'], 'seed': str(e['seed'])})
            g, _ = fast_recipe.build('in.png', w, h, controls.stage_params(params, 0), 'p', live_preview='detailed')

            def norm(graph):
                c = json.loads(json.dumps(graph))
                for v in c.values():
                    if v['class_type'] == 'LoadImage':
                        v['inputs']['image'] = '<in>'
                    if v['class_type'] == 'SaveImage':
                        v['inputs']['filename_prefix'] = '<out>'
                    if v['class_type'] == 'ClaudeSpotTiles':
                        v['inputs']['live_preview'] = '<feed>'
                return c
            self.assertEqual(norm(g), norm(ref), p['name'])
            self.assertEqual(ref[next(k for k, v in ref.items() if v['class_type'] == 'ClaudeSpotTiles')]['inputs']['live_preview'],
                             'on')
            n += 1
        self.assertEqual(n, 10)


class T4Looks(unittest.TestCase):
    def test_end_percents_and_active_steps(self):
        want = {'Light': ((0.9677, 4), (0.9787, 5)), 'Default': ((0.7936, 3), (0.9737, 5))}
        for look, ((e1, a1), (e3, a3)) in want.items():
            _, _, _, info = fast_and_standard(look)
            self.assertEqual(info['fast_ends'], {'detail': e1, 'structure': e3}, look)
            params, _ = controls.resolve({'preset': look})
            for d, frac, end, active in ((params['denoise'], params['tile_frac'], e1, a1),
                                         (params['structure'], params['s_line_frac'], e3, a3)):
                ev = schedule.run('karras', 8, d)
                self.assertEqual(len(ev), 8)
                self.assertEqual(sum(1 for s in ev if s > schedule.p2s(end)), active, (look, d))

        for look, (s1, s3) in {'Light': (0.7462, 1.2741), 'Default': (2.0392, 1.5892)}.items():
            params, _ = controls.resolve({'preset': look})
            self.assertAlmostEqual(float(schedule.run('karras', 8, params['denoise'])[0]), s1, places=4)
            self.assertAlmostEqual(float(schedule.run('karras', 8, params['structure'])[0]), s3, places=4)


class T5Gating(Restore):
    def info(self, **kw):
        with mock.patch.dict(os.environ, {'CU_FAST': '1'}):
            return engine_options.fast_info(**kw)

    def test_look_and_scale_refusals(self):
        on = self.info()
        for req in ({'preset': 'Light'}, {'preset': 'Default'}, {'preset': 'Default', 'protect': ['people']},
                    {'preset': 'Light', 'seed': '7', 'prompt': 'stone'},
                    {'preset': 'Default', 'custom': True, 'creativity': 50, 'resemblance': 60, 'restoration': 35}):
            _, eff = controls.resolve(dict(req, mode='fast'))
            self.assertIsNone(engine_options.fast_refusal(eff, on), req)

        look = 'Bolt offers Light and Default only. Choose Redux for Strong, Heavy, Extreme or Custom.'
        scale = 'Bolt upscales 2\u00d7 only. Choose Redux for 4\u00d7 and above.'
        for req, want in (({'preset': 'Strong'}, ('look', look)), ({'preset': 'Heavy'}, ('look', look)),
                          ({'preset': 'Extreme'}, ('look', look)),
                          ({'preset': 'Default', 'custom': True, 'creativity': 70}, ('look', look)),
                          ({'scale': 4}, ('scale', scale)), ({'scale': 8, 'preset': 'Light'}, ('scale', scale)),
                          ({'scale': 6, 'preset': 'Heavy'}, ('scale', scale))):
            _, eff = controls.resolve(dict(req, mode='fast'))
            self.assertEqual(engine_options.fast_refusal(eff, on), want, req)
        _, std = controls.resolve({'preset': 'Extreme', 'scale': 8})
        self.assertIsNone(engine_options.fast_refusal(std, on))
        self.assertIsNone(engine_options.fast_refusal({'mode': 'fast', 'scale': 2}, on))

    def test_availability_refusals(self):
        _, eff = controls.resolve({'mode': 'fast'})


        with mock.patch.dict(os.environ, {'CU_FAST': '0'}):
            self.assertEqual(engine_options.fast_refusal(eff, engine_options.fast_info()),
                             ('pending_proof', 'Bolt is not available. Choose Redux.'))
        os.environ.pop('CU_FAST', None)
        self.assertIsNone(engine_options.fast_refusal(eff, engine_options.fast_info()))
        self.assertIsNone(engine_options.fast_refusal(eff, self.info()))
        self.assertEqual(engine_options.fast_refusal(eff, self.info(files_ok=None)),
                         ('checking', 'Bolt is not ready yet: its files are still being checked. Try again in a moment.'))
        self.assertEqual(engine_options.fast_refusal(eff, self.info(files_ok=False)),
                         ('files_missing', 'Bolt cannot be used: a file it needs cannot be read. Choose Redux.'))
        fast_recipe.RECIPE = None
        self.assertEqual(engine_options.fast_refusal(eff, self.info()), ('no_recipe', 'Bolt is not available. Choose Redux.'))
        self.assertEqual(engine_options.FAST_REFUSAL, 'Bolt is not available. Choose Redux.')

    def test_plans_fast_cannot_make_have_no_fast_time(self):
        for scale in (2, 4, 6, 8):
            p = planner.plan(2048, 2048, scale)
            f = engine_options.finish_info(p.minutes, fast_available=True, plan=p)
            if scale == 2:
                self.assertEqual(f['fast'], {'minutes': round(p.minutes * 0.37, 1), 'factor': 0.37})
            else:
                self.assertIsNone(f['fast'], scale)
            self.assertIsNone(engine_options.finish_info(p.minutes, fast_available=False, plan=p)['fast'])
            self.assertIsNone(engine_options.finish_info(p.minutes, fast_available=True, plan=p.to_dict() | {'factor': 4})['fast']) \
                if scale == 2 else None


class T7Weights(Restore):
    def test_the_sampling_passes_weigh_as_in_standard(self):
        std, sinfo, fast, finfo = fast_and_standard()
        ts, tf = comfy.ProgressTracker(std, 'a'), comfy.ProgressTracker(fast, 'b')
        for t, info in ((ts, sinfo), (tf, finfo)):
            ks = [info['samplers']['structure'], info['samplers']['detail']]
            self.assertEqual([t.weights[k] for k in ks], [40.0, 40.0])
        lora = next(k for k, v in fast.items() if v['class_type'] == 'LoraLoaderModelOnly')
        self.assertEqual(tf.weights[lora], comfy.DEFAULT_WEIGHT)
        self.assertAlmostEqual(tf.total - ts.total, comfy.DEFAULT_WEIGHT)
        self.assertLess(abs(80.0 / tf.total - 80.0 / ts.total), 0.002)


class T8FinishTime(Restore):
    def test_0_37_of_the_planners_minutes_covers_round_3(self):
        # 5.0.2: the planner's minutes are an upper bound of the 19 Nov stage times (tests/test_sam_lean_and_times.py),
        # whose Bolt runs took longer than round 3 (917.5 s against 805.9 s at 3500 x 2188); so the said time is at least
        # round 3's and within 20 % of it (5.0.2 says 10-19 % above round 3, 5.0.1 said 1-11 % above it).
        for scene, ((w, h), secs) in R3_TIMES.items():
            p = planner.plan(w, h, 2)
            shown = p.minutes * 60 * engine_options.eta_factor(mode='fast')
            self.assertGreaterEqual(shown, secs, (scene, shown, secs))
            self.assertLess(shown / secs, 1.20, (scene, shown, secs))
        self.assertEqual(engine_options.eta_factor(mode='fast'), 0.37)


        os.environ.pop('CU_FAST_SPLIT', None)
        self.assertEqual(engine_options.eta_factor(mode='fast', cards=2), 0.308)
        with mock.patch.dict(os.environ, {'CU_FAST_SPLIT': '0'}):
            self.assertEqual(engine_options.eta_factor(mode='fast', cards=2), 0.37)
        r = engine_options.run_info('fast', match_earlier=True, frozen=True, split=False)
        self.assertEqual((r['mode'], r['match_earlier'], r['speed_stack'], r['factor'], r['faster']),
                         ('fast', False, True, 0.37, False))
        r = engine_options.run_info('fast', faster=True, plan=planner.plan(2048, 2048, 2).to_dict())
        self.assertEqual((r['factor'], r['faster']), (0.37, False))


class RunOrder(Restore):
    def test_fast_samples_the_structure_pass_first(self):
        for look in ('Light', 'Default'):
            _, _, fast, info = fast_and_standard(look)
            self.assertEqual(info['run_order'], ['structure', 'detail'])
            self.assertEqual(run_order.pass_order(fast, info['samplers']), ['structure', 'detail'])

        with mock.patch.dict(os.environ, {'CU_CREATIVE_FIRST': '1'}):
            _, _, fast2, info2 = fast_and_standard()
        self.assertEqual(run_order.pass_order(fast2, info2['samplers']), ['structure', 'detail'])


class TwoCards(Restore):
    def test_the_multi_card_transform_carries_the_fast_graph(self):
        _, _, fast, info = fast_and_standard()
        g = graph_v5t.add_multigpu(fast, 2)
        spot = next(k for k, v in g.items() if v['class_type'] == 'ClaudeSpotTiles')
        mg = next(k for k, v in g.items() if v['class_type'] == 'MultiGPU_WorkUnits')
        lora = next(k for k, v in g.items() if v['class_type'] == 'LoraLoaderModelOnly')
        pag = next(k for k, v in g.items() if v['class_type'] == 'PerturbedAttentionGuidance')
        self.assertEqual(g[mg]['inputs'], {'model': [spot, 0], 'max_gpus': 2})
        self.assertEqual((g[spot]['inputs']['model'], g[pag]['inputs']['model']), ([pag, 0], [lora, 0]))
        self.assertEqual((g[spot]['inputs']['window_split'], g[spot]['inputs']['seam_overlap']), (True, 16))
        for role in ('structure', 'detail'):
            self.assertEqual(g[info['samplers'][role]]['inputs']['model'], [mg, 0])
        self.assertEqual(fast, fast_and_standard()[2])

    def test_fast_shares_an_image_only_once_proven(self):


        os.environ.pop('CU_FAST_SPLIT', None)
        self.assertTrue(engine_options.split_allowed('fast'))
        with mock.patch.dict(os.environ, {'CU_FAST_SPLIT': '0'}):
            self.assertFalse(engine_options.split_allowed('fast'))
            with mock.patch.dict(os.environ, {'CU_FAST': '1'}):
                self.assertFalse(engine_options.fast_info()['split'])
        with mock.patch.dict(os.environ, {'CU_FAST_SPLIT': '1'}):
            self.assertTrue(engine_options.split_allowed('fast'))
            with mock.patch.dict(os.environ, {'CU_FAST': '1'}):
                self.assertTrue(engine_options.fast_info()['split'])
        with mock.patch.dict(os.environ, {'CU_FAST': '1'}):
            self.assertTrue(engine_options.fast_info()['split'])


class ModeControl(unittest.TestCase):
    def test_mode_resolves_like_the_look(self):
        p0, e0 = controls.resolve({})
        self.assertEqual(e0['mode'], 'standard')
        p1, e1 = controls.resolve({'mode': 'fast'})
        self.assertEqual(e1['mode'], 'fast')
        self.assertEqual(p0, p1)
        self.assertEqual(e0['engine'], e1['engine'])
        self.assertEqual({k: v for k, v in e1.items() if k != 'mode'}, {k: v for k, v in e0.items() if k != 'mode'})
        for bad in ('Fast', 'turbo', 1, None, True):
            with self.assertRaises(controls.ControlError) as cm:
                controls.resolve({'mode': bad})
            self.assertEqual(str(cm.exception), 'Choose a mode: Standard or Fast.')
        d = controls.describe()
        self.assertEqual(d['modes'], [{'key': 'standard', 'label': 'Standard', 'text': ''},
                                      {'key': 'fast', 'label': 'Fast',
                                       'text': 'Quicker, with a slightly different look. Use Standard for finals.'}])
        self.assertEqual(d['contract'], 'creative-upscaler-controls-v2')

    def test_stage_params_do_not_know_the_mode(self):
        p, _ = controls.resolve({'mode': 'fast', 'scale': 4})
        q, _ = controls.resolve({'scale': 4})
        self.assertEqual([controls.stage_params(p, k) for k in range(2)], [controls.stage_params(q, k) for k in range(2)])


class StandardIsUntouched(Restore):
    def test_standard_modules_never_import_the_recipe(self):
        for name in ('graph_v5t.py', 'controls.py', 'planner.py', 'schedule.py'):
            tree = ast.parse((REPO / 'engine' / name).read_text(encoding='utf8'))
            names = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names |= {a.name for a in node.names}
                elif isinstance(node, ast.ImportFrom):
                    names |= {node.module or ''} | {a.name for a in node.names}
            self.assertFalse([n for n in names if 'fast' in n.lower()], name)

    def test_byte_identical_with_and_without_a_recipe(self):
        fast_recipe.RECIPE = None
        before = standard_graphs()
        for recipe in (INSTALLED, stand_in([])):
            fast_recipe.RECIPE = recipe
            self.assertEqual(standard_graphs(), before)

            params, _ = controls.resolve({'mode': 'fast'})
            mine = dict(params)
            g, info = fast_recipe.build('other.png', 1024, 768, mine, 'fastp', live_preview='detailed')
            self.assertEqual(mine, params)
            self.assertEqual(standard_graphs(), before)
        self.assertEqual(graph_v5t.SPEED_STACK_ON, {'noise_prefetch': True, 'pag_fuse': True, 'batch_windows': 2,
                                                    'fp16_acc_scoped': True})
        self.assertEqual(controls.resolve({})[0]['steps'], 30)
        for b in before:
            self.assertNotIn(b'seam_overlap', b)
            self.assertNotIn(b'LoraLoaderModelOnly', b)
            self.assertNotIn(b'cfg_end', b)

    def test_byte_identical_when_the_fast_module_does_not_exist(self):
        before = standard_graphs()

        class NoFast:
            @staticmethod
            def find_spec(name, path=None, target=None):
                if name == 'engine.fast_recipe':
                    raise ImportError('engine.fast_recipe does not exist in this build')
                return None
        saved = {k: sys.modules.pop(k) for k in list(sys.modules) if k in ('engine.fast_recipe', 'engine.graph_v5t')}
        sys.meta_path.insert(0, NoFast)
        try:
            with self.assertRaises(ImportError):
                importlib.import_module('engine.fast_recipe')
            fresh = importlib.import_module('engine.graph_v5t')
            self.assertIsNot(fresh, graph_v5t)
            self.assertNotIn('engine.fast_recipe', sys.modules)
            self.assertEqual(standard_graphs(fresh), before)
        finally:
            sys.meta_path.remove(NoFast)
            for k in ('engine.fast_recipe', 'engine.graph_v5t'):
                sys.modules.pop(k, None)
            sys.modules.update(saved)
            import engine
            engine.graph_v5t, engine.fast_recipe = saved['engine.graph_v5t'], saved['engine.fast_recipe']

    def test_a_stand_in_recipes_factor_and_health(self):
        fast_recipe.RECIPE = stand_in()
        self.assertEqual(engine_options.eta_factor(mode='fast'), 0.25)
        self.assertEqual(engine_options.finish_info(20.0, fast_available=True)['fast'], {'minutes': 5.0, 'factor': 0.25})
        self.assertIsNone(engine_options.finish_info(20.0, fast_available=False)['fast'])
        info = engine_options.fast_info(proven=True)
        self.assertEqual((info['available'], info['recipe'], info['factor'], info['looks'], info['max_factor']),
                         (True, 'unit-fast', 0.25, ['Light', 'Default'], 2))
        self.assertEqual(engine_options.fast_info(files_ok=False, proven=True)['reason'], 'files_missing')
        self.assertEqual(engine_options.eta_factor(), 0.70)

    def test_a_half_installed_recipe_cannot_run(self):
        good = stand_in()
        for broken in ({'name': 'x'}, dict(good, eta_factor=None), dict(good, build='not a function'),
                       dict(good, models=['x']), dict(good, split_ok='yes'), 'recipe',
                       {k: v for k, v in good.items() if k != 'looks'}, {k: v for k, v in good.items() if k != 'max_factor'},
                       dict(good, looks=()), dict(good, looks=('Light', 'Medium')), dict(good, looks=('Light', 'Light')),
                       dict(good, max_factor=3), dict(good, max_factor=True), dict(good, eta_factors={'first_stage': 0}),
                       dict(good, lora={'file': 'x.safetensors'}),
                       dict(good, lora={'file': 'y.safetensors', 'bytes': 1, 'sha256': '0' * 64, 'strength': 0.25})):
            fast_recipe.RECIPE = broken
            with self.assertRaises(ValueError):
                fast_recipe.recipe()
            with self.assertRaises(ValueError):
                fast_recipe.build('in.png', 1024, 768, controls.resolve({})[0], 'p')
            d = fast_recipe.describe()
            self.assertEqual((d['installed'], bool(d['problem'])), (False, True))
            info = engine_options.fast_info(proven=True)
            self.assertEqual((info['available'], info['reason']), (False, 'no_recipe'))
            self.assertIsNone(engine_options.eta_factor(mode='fast'))
        fast_recipe.RECIPE = dict(good, build=lambda *a: ({}, {'render': 1}))
        with self.assertRaises(ValueError):
            fast_recipe.build('in.png', 1024, 768, controls.resolve({})[0], 'p')


class Size(Restore):

    SIZES = {(2048, 2048): 2.0, (3500, 2188): 2.0, (3840, 2400): 2.0, (3842, 2440): 2.0, (8192, 1144): 2.0, (4097, 2000): 2.0,
             (3850, 2436): 1.5, (3061, 3062): 1.5, (4032, 3024): 1.5, (4200, 2800): 1.5, (5472, 3648): 1.0, (6000, 4000): 1.0}

    def info(self):
        with mock.patch.dict(os.environ, {'CU_FAST': '1'}):
            return engine_options.fast_info()

    def test_the_gate_is_the_planners_supersample_2(self):
        self.assertEqual(fast_recipe.SUPERSAMPLES, (2,))
        self.assertEqual(fast_recipe.describe()['supersamples'], [2.0])
        for (w, h), s in self.SIZES.items():
            p = planner.plan(w, h, 2)
            self.assertEqual(p.stages[0].supersample, s, (w, h))
            self.assertEqual(engine_options.fast_plan_refusal(p), None if s == 2 else 'size', (w, h))
            self.assertEqual(engine_options.fast_plan_ok(p.to_dict()), s == 2, (w, h))

        for w in range(1000, 8200, 397):
            for h in range(600, 4200, 311):
                p = planner.plan(w, h, 2)
                if p.ok:
                    self.assertEqual(engine_options.fast_plan_refusal(p) is None, p.stages[0].supersample == 2, (w, h))

        for scene, ((w, h), _) in R3_TIMES.items():
            self.assertIsNone(engine_options.fast_plan_refusal(planner.plan(w, h, 2)), scene)

        self.assertEqual(engine_options.fast_plan_refusal(planner.plan(4032, 3024, 4)), 'scale')
        self.assertEqual(engine_options.fast_plan_refusal(planner.plan(512, 512, 4)), 'scale')

    def test_the_refusal_and_its_order(self):
        on = self.info()
        big, small = planner.plan(4032, 3024, 2), planner.plan(2048, 2048, 2)
        size = 'Bolt works on images up to about 9 MP. Choose Redux for larger images.'
        self.assertEqual(engine_options.FAST_REFUSALS['size'], size)
        eff = {'mode': 'fast', 'scale': 2, 'preset': 'Default'}
        self.assertEqual(engine_options.fast_refusal(eff, on, big), ('size', size))
        self.assertIsNone(engine_options.fast_refusal(eff, on, small))
        self.assertIsNone(engine_options.fast_refusal(eff, on))
        self.assertIsNone(engine_options.fast_refusal(dict(eff, mode='standard'), on, big))

        self.assertEqual(engine_options.fast_refusal(dict(eff, preset='Heavy'), on, big)[0], 'look')
        self.assertEqual(engine_options.fast_refusal(dict(eff, scale=4), on, planner.plan(4032, 3024, 4))[0], 'scale')
        with mock.patch.dict(os.environ, {'CU_FAST': '0'}):
            off = engine_options.fast_info()
        self.assertEqual(engine_options.fast_refusal(eff, off, big)[0], 'pending_proof')
        self.assertEqual(engine_options.FAST_SIZE_FAILURE,
                         'This image is too large for Bolt, so it was not upscaled. Queue it again in Redux.')

    def test_no_fast_time_for_an_image_too_large(self):
        big = planner.plan(4032, 3024, 2)
        f = engine_options.finish_info(big.minutes, fast_available=True, plan=big)
        self.assertIsNone(f['fast'])
        self.assertEqual(f['fast_refusal'], {'reason': 'size', 'message': engine_options.FAST_REFUSALS['size']})
        self.assertIsNone(f['single']['fast'])
        ok = planner.plan(3840, 2400, 2)
        f = engine_options.finish_info(ok.minutes, fast_available=True, plan=ok)
        self.assertEqual((f['fast'], f['fast_refusal']), ({'minutes': round(ok.minutes * 0.37, 1), 'factor': 0.37}, None))
        f = engine_options.finish_info(ok.minutes, fast_available=False, plan=ok, fast_reason='files_missing')
        self.assertEqual(f['fast_refusal'], {'reason': 'files_missing',
                                             'message': engine_options.FAST_REFUSALS['files_missing']})

    def test_the_builder_refuses_a_stage_below_supersample_2(self):
        pk = controls.stage_params(controls.resolve({'preset': 'Default'})[0], 0)
        g, info = fast_recipe.build('in.png', 1024, 768, pk, 'p', f=2, s=2, live_preview='detailed')
        self.assertEqual(info['supersample'], 2)
        for s in (Fraction(3, 2), 1):
            with self.assertRaises(fast_recipe.FastTooLarge):
                fast_recipe.build('in.png', 1024, 768, pk, 'p', f=2, s=s, live_preview='detailed')
        self.assertTrue(issubclass(fast_recipe.FastTooLarge, fast_recipe.FastUnavailable))

        fast_recipe.RECIPE = dict(INSTALLED, supersamples=(2, 1.5))
        g, info = fast_recipe.build('in.png', 1024, 768, pk, 'p', f=2, s=Fraction(3, 2), live_preview='detailed')
        self.assertEqual(fast_recipe.describe()['supersamples'], [2.0, 1.5])
        for bad in ((), (3,), (True,), 'x'):
            fast_recipe.RECIPE = dict(INSTALLED, supersamples=bad)
            with self.assertRaises(ValueError):
                fast_recipe.recipe()


if __name__ == '__main__':
    unittest.main()
