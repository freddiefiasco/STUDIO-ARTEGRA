"""Banded Bolt (B16; engine design 9.1 B16, 3.1, 7.4 C4; build wave 2, contract bolt). graph_banded.bolt_patch is a copy of
engine/fast_recipe._build's patch values (the LoRA on the checkpoint's model with the recipe's strength, PAG's model from it,
seam_overlap 16, both samplers at 8 steps and CFG 5.0, the ControlNet end percents by schedule.end_mid for 8 steps), checked
against fast_recipe's own source, so a recipe change fails here. A Bolt plan is 2x only, at supersample 2, render <= 150 MP,
with the LoRA backup counted at its measured upper value, and carries the installed recipe's name and version as its 'recipe'
constant. BOLT_BANDED stays False (it flips only after R1b and C4); engine_options.fast_plan_refusal admits a banded Bolt plan
only when it is True, or for a forced plan in a developer build. Sizes only."""
import ast
import hashlib
import inspect
import unittest
from fractions import Fraction
from unittest import mock

from engine import banded_plan as B
from engine import controls, fast_recipe, graph_banded, graph_v5t, planner, schedule
from service import build_channel, engine_options

PROVEN = {k: 10_000.0 for k in B.BANDED_PROVEN_MP}

# sha256 of ast.dump(fast_recipe._build) and of the recipe's constant assignments as this copy was made from them. A change
# to the recipe's patch makes these differ: then graph_banded.BOLT / bolt_patch must be re-copied and this pin renewed.
BUILD_AST_SHA256 = 'c88494d35a796b08e4bee1344424cd5f2c72052ab2853030b8712beeb08ac115'
CONSTANTS_AST_SHA256 = 'af1766b879761ac2716872ffc10cc9535dabff9a5055cf66ed25f0e6469fbc44'


def by_class(g, cls):
    return [n['inputs'] for n in g.values() if n['class_type'] == cls]


def values(inputs):
    return {k: v for k, v in inputs.items() if not (isinstance(v, list) and len(v) == 2 and isinstance(v[0], str))}


def recipe_source():
    return ast.parse(inspect.getsource(fast_recipe))


def build_ast_sha():
    fn = next(n for n in recipe_source().body if isinstance(n, ast.FunctionDef) and n.name == '_build')
    return hashlib.sha256(ast.dump(fn, include_attributes=False).encode('utf8')).hexdigest()


def constants_ast_sha():
    keep = []
    for n in recipe_source().body:
        if isinstance(n, ast.Assign):
            names = {getattr(t, 'id', None) for t in n.targets} | {getattr(e, 'id', None) for t in n.targets
                                                                  for e in getattr(t, 'elts', [])}
            if names & {'LORA', 'STEPS', 'CFG', 'SEAM_OVERLAP', 'MAX_FACTOR', 'SUPERSAMPLES'}:
                keep.append(ast.dump(n, include_attributes=False))
    return hashlib.sha256('\n'.join(keep).encode('utf8')).hexdigest()


def bolt_consts(machine='pc64'):
    c = B.constants('bolt')
    c.update(machine_class=machine)
    return c


class TheCopyIsFastRecipesOwn(unittest.TestCase):
    def test_the_values(self):
        b = graph_banded.BOLT
        self.assertEqual(b['lora'], fast_recipe.LORA['file'])
        self.assertEqual(b['strength'], fast_recipe.LORA['strength'])
        self.assertEqual((b['steps'], b['cfg'], b['seam_overlap']), (fast_recipe.STEPS, fast_recipe.CFG, fast_recipe.SEAM_OVERLAP))
        self.assertEqual((b['steps'], b['cfg'], b['seam_overlap']), (8, 5.0, 16))
        self.assertEqual(b['scheduler'], 'karras')
        self.assertEqual(b['max_factor'], fast_recipe.MAX_FACTOR)
        self.assertEqual(tuple(b['supersamples']), tuple(float(x) for x in fast_recipe.SUPERSAMPLES))
        r = fast_recipe.recipe()
        self.assertEqual((b['recipe'], b['version']), (r['name'], r['version']))
        self.assertEqual(graph_banded.BOLT_RECIPE, f"{r['name']}@{r['version']}")

    def test_the_source_it_was_copied_from(self):
        self.assertEqual(build_ast_sha(), BUILD_AST_SHA256, 'fast_recipe._build changed: re-copy graph_banded.bolt_patch')
        self.assertEqual(constants_ast_sha(), CONSTANTS_AST_SHA256, "fast_recipe's constants changed: re-copy graph_banded.BOLT")

    def test_the_banded_bolt_stage_has_the_classic_bolt_stages_values(self):
        """fast_recipe.build (the classic Bolt graph) against graph_banded.build_product with Bolt's constants, for 2x stages at
        supersample 2: every value of the classes the patch touches, and the ends it places."""
        for (w, h) in ((1752, 1096), (2048, 1536), (1000, 504)):
            for protect in (None, [], list(controls.PROTECT_ORDER)):
                for live in (None, 'rough', 'detailed'):
                    req = {} if protect is None else {'protect': protect}
                    p = controls.stage_params(controls.resolve(req)[0], 0)
                    c, ci = fast_recipe.build('x.png', w, h, p, 'cu_j_i_s0', f=2, s=2, live_preview=live)
                    b, bi = graph_banded.build_product('work/in.plane', w, h, p, 'cu_j_i_s0', 'work/planes/s0', 'run1', f=2,
                                                       s=2, constants=bolt_consts(), live_preview=live,
                                                       creative_first=True, speed_stack=False, faster=True)
                    key = (w, h, protect, live)
                    for cls in ('LoraLoaderModelOnly', 'PerturbedAttentionGuidance', 'KSampler', 'CheckpointLoaderSimple'):
                        self.assertEqual([values(x) for x in by_class(c, cls)], [values(x) for x in by_class(b, cls)], (key, cls))
                    self.assertEqual([values(x) for x in by_class(c, 'ControlNetApplyAdvanced')],
                                     [values(x) for x in by_class(b, 'CUControlNetApplyPlane')], key)
                    fork = values(by_class(b, 'ClaudeSpotTilesBanded')[0])
                    self.assertEqual(fork.pop('brownian_cache', 45), bolt_consts()['brownian_cache'], key)   # the plan's cap
                    self.assertEqual(values(by_class(c, 'ClaudeSpotTiles')[0]), fork, key)
                    self.assertEqual(bi['fast_ends'], ci['fast_ends'], key)
                    self.assertEqual(bi['spot_options'], ci['spot_options'], key)
                    self.assertEqual(bi['run_order'], ci['run_order'], key)
                    self.assertEqual(bi['fast'], ci['fast'], key)
                    lora = next(k for k, n in b.items() if n['class_type'] == 'LoraLoaderModelOnly')
                    ck = next(k for k, n in b.items() if n['class_type'] == 'CheckpointLoaderSimple'
                              and n['inputs']['ckpt_name'] == graph_v5t.MODELS['ckpt'])
                    pag = by_class(b, 'PerturbedAttentionGuidance')[0]
                    self.assertEqual(b[lora]['inputs']['model'], [ck, 0])
                    self.assertEqual(pag['model'], [lora, 0])

    def test_the_ends_are_end_mid_for_eight_steps(self):
        p = controls.stage_params(controls.resolve({})[0], 0)
        b, bi = graph_banded.build_product('in.plane', 1752, 1096, p, 'x', 'pl', 'r', constants=bolt_consts())
        self.assertEqual(bi['fast_ends'], {'detail': schedule.end_mid('karras', 8, p['denoise'], p['tile_frac']),
                                           'structure': schedule.end_mid('karras', 8, p['structure'], p['s_line_frac'])})
        for ks in by_class(b, 'KSampler'):
            self.assertEqual((ks['steps'], ks['cfg']), (8, 5.0))

    def test_a_split_bolt_stage_patches_part_a_only(self):
        p = controls.stage_params(controls.resolve({'protect': list(controls.PROTECT_ORDER)})[0], 0)
        a, _ = graph_banded.build_product('in.plane', 1752, 1096, p, 'x', 'pl', 'r', constants=bolt_consts(), part='A')
        bb, _ = graph_banded.build_product('in.plane', 1752, 1096, p, 'x', 'pl', 'r', constants=bolt_consts(), part='B')
        self.assertEqual(len(by_class(a, 'LoraLoaderModelOnly')), 1)
        self.assertEqual({n['class_type'] for n in bb.values()}, {'CUPlaneInput', 'CUFinishBanded'})

    def test_the_redux_graph_is_untouched(self):
        p = controls.stage_params(controls.resolve({})[0], 0)
        base, _ = graph_banded.build_product('in.plane', 1752, 1096, p, 'x', 'pl', 'r')
        red, _ = graph_banded.build_product('in.plane', 1752, 1096, p, 'x', 'pl', 'r',
                                            constants=dict(B.constants('redux'), brownian_cache=45))   # the base's own cache
        self.assertEqual(base, red)
        self.assertEqual(by_class(base, 'LoraLoaderModelOnly'), [])
        capped, _ = graph_banded.build_product('in.plane', 1752, 1096, p, 'x', 'pl', 'r', constants=B.constants('redux'))
        self.assertEqual(by_class(capped, 'LoraLoaderModelOnly'), [])
        self.assertEqual([values(x) for x in by_class(capped, 'KSampler')], [values(x) for x in by_class(base, 'KSampler')])


class TheRecipeConstant(unittest.TestCase):
    def test_accepted_exactly(self):
        p = controls.resolve({})[0]
        graph_banded.build_stage('in.plane', 1752, 1096, p, 'x', 'pl', 'r', constants={'recipe': 'r501'})
        graph_banded.build_stage('in.plane', 1752, 1096, p, 'x', 'pl', 'r', constants=bolt_consts())
        for bad in ({'recipe': 'r502'}, {'recipe': graph_banded.BOLT_RECIPE},                    # Bolt's recipe on Redux
                    {'mode': 'bolt', 'recipe': 'r501'}, {'mode': 'bolt', 'recipe': 'H8-other@2'}, {'mode': 'turbo'}):
            with self.assertRaises(ValueError, msg=bad):
                graph_banded.build_stage('in.plane', 1752, 1096, p, 'x', 'pl', 'r', constants=bad)

    def test_the_plan_takes_the_installed_recipe(self):
        c = B.constants('fast')
        self.assertEqual((c['mode'], c['recipe']), ('bolt', graph_banded.BOLT_RECIPE))
        self.assertEqual(B.constants('standard'), B.constants('redux'))
        self.assertEqual(B.constants('redux')['recipe'], 'r501')
        with self.assertRaises(ValueError):
            B.constants('turbo')
        with mock.patch.object(fast_recipe, 'RECIPE', dict(fast_recipe.RECIPE, version='2')):
            self.assertNotEqual(B.constants('bolt')['recipe'], graph_banded.BOLT_RECIPE)
            p = controls.resolve({})[0]
            with self.assertRaises(ValueError):                     # a recipe this build's copy does not know is refused
                graph_banded.build_stage('in.plane', 1752, 1096, p, 'x', 'pl', 'r', constants=B.constants('bolt'))


class BoltPlans(unittest.TestCase):
    def test_bolt_stays_off_until_r1b_and_c4(self):
        self.assertIs(B.BOLT_BANDED, False)
        with mock.patch.dict(B.BANDED_PROVEN_MP, PROVEN):
            for mode in ('fast', 'bolt'):
                p = B.plan_banded(3000, 3000, 2, 59.0, mode=mode)
                self.assertFalse(p.ok)
                self.assertIn('Bolt is not available', p.reason)

    def test_two_x_at_supersample_two_only(self):
        with mock.patch.dict(B.BANDED_PROVEN_MP, PROVEN), mock.patch.object(B, 'BOLT_BANDED', True), \
                mock.patch.object(B, 'BXF_AVAILABLE', True):
            ok = B.plan_banded(3000, 3000, 2, 59.0, mode='fast')
            self.assertTrue(ok.ok, ok.reason)
            self.assertEqual([(s.factor, s.supersample) for s in ok.stages], [(2.0, 2.0)])
            self.assertLessEqual(ok.stages[0].render_mp, 150.0)
            self.assertEqual((ok.banded['mode'], ok.banded['recipe']), ('bolt', graph_banded.BOLT_RECIPE))
            for f in (4, 6, 8):
                p = B.plan_banded(3000, 3000, f, 122.2, mode='fast')
                self.assertFalse(p.ok)
                self.assertIn('2×', p.reason)
            p = B.plan_banded(3500, 2800, 2, 122.2, mode='fast')        # 9.8 MP: its 2x renders at supersample 1.5
            self.assertFalse(p.ok)
            self.assertIn('Bolt', p.reason)
            self.assertIn('9 MP', p.reason)

    def test_the_lora_backup_is_counted_at_its_upper_value(self):
        self.assertGreaterEqual(B.LORA_GB, 7.2)                     # ENGINE-FACTS 2.6: +5.1 and +7.2 GiB measured above Redux
        st = B.stage_choice((3000, 3000), 2, 0)
        for tier in ('bxf', 'tier3'):
            red = B.stage_peaks(st, 'pc64', False, tier=tier)['phases_up']
            bolt = B.stage_peaks(st, 'pc64', False, tier=tier, lora_gb=B.LORA_GB)['phases_up']
            for ph in ('P0', 'sampling', 'decode'):
                self.assertAlmostEqual(bolt[ph] - red[ph], B.LORA_GB, msg=(tier, ph))
            self.assertGreaterEqual(bolt['finish'] - red['finish'], 0.0)
            if tier == 'bxf':
                self.assertAlmostEqual(bolt['finish'] - red['finish'], B.LORA_GB)
            split = B.stage_peaks(st, 'pc64', True, tier=tier, lora_gb=B.LORA_GB)['phases_up']
            self.assertAlmostEqual(split['finish'], B.stage_peaks(st, 'pc64', True, tier=tier)['phases_up']['finish'])
        with mock.patch.dict(B.BANDED_PROVEN_MP, PROVEN), mock.patch.object(B, 'BOLT_BANDED', True), \
                mock.patch.object(B, 'BXF_AVAILABLE', True):
            bolt, red = B.plan_banded(3000, 3000, 2, 59.0, mode='fast'), B.plan_banded(3000, 3000, 2, 59.0)
        self.assertEqual(bolt.stages[0].lora_gb, B.LORA_GB)
        self.assertEqual(red.stages[0].lora_gb, 0.0)
        self.assertGreater(bolt.peak_ram_gb, red.peak_ram_gb + 7.0)
        self.assertEqual(round(B.stage_peaks(bolt.stages[0], 'pc64', bolt.stages[0].split_finish)['up'][0], 1),
                         bolt.stages[0].peak_upper_gb)

    def test_the_brownian_cap_waits_for_bolts_own_schedules(self):
        """G7 compared Redux's 30-step schedules; a Bolt plan caps the cache only once Bolt's 8-step ones passed too."""
        c = planner.plan(2048, 2048, 2, ram_cap_gb=59.0)
        st = B.stage_choice((2048, 2048), 2, 0)
        for redux_cap, bolt_cap in ((True, False), (True, True), (False, True), (False, False)):
            with mock.patch.object(B, 'BROWNIAN_CAPPED', redux_cap), mock.patch.object(B, 'BOLT_BROWNIAN_CAPPED', bolt_cap):
                want = 8 if (redux_cap and bolt_cap) else 45
                self.assertEqual(B.constants('bolt')['brownian_cache'], want)
                self.assertEqual(B.plan_forced(c, 59.0, mode='fast').banded['brownian_cache'], want)
                self.assertEqual(B.constants('redux')['brownian_cache'], 8 if redux_cap else 45)
                bolt = B.stage_peaks(st, 'pc64', False, tier='bxf', lora_gb=B.LORA_GB)
                same = B.stage_peaks(st, 'pc64', False, tier='bxf', lora_gb=B.LORA_GB, brownian_capped=want == 8)
                self.assertEqual(bolt, same)
                p = controls.stage_params(controls.resolve({})[0], 0)
                g, _ = graph_banded.build_product('in.plane', 2048, 2048, p, 'x', 'pl', 'r', constants=B.constants('bolt'))
                spot = by_class(g, 'ClaudeSpotTilesBanded')[0]
                self.assertEqual(spot.get('brownian_cache', 45), want)

    def test_forced_bolt(self):
        c = planner.plan(2048, 2048, 2, ram_cap_gb=59.0)
        for mode in ('fast', 'bolt'):
            p = B.plan_forced(c, 59.0, mode=mode)
            self.assertTrue(p.ok, p.reason)
            self.assertEqual((p.banded['mode'], p.banded['recipe'], p.banded['forced']), ('bolt', graph_banded.BOLT_RECIPE, True))
            self.assertEqual(p.stages[0].lora_gb, B.LORA_GB)
        self.assertEqual(B.plan_forced(c, 59.0, mode='standard').to_dict(), B.plan_forced(c, 59.0).to_dict())
        self.assertEqual(B.plan_forced(c, 59.0, mode='redux').banded['mode'], 'redux')
        four = planner.plan(1280, 1600, 4, ram_cap_gb=59.0)
        self.assertFalse(B.plan_forced(four, 59.0, mode='fast').ok)
        self.assertIn('2×', B.plan_forced(four, 59.0, mode='fast').reason)
        s15 = planner.plan(2800, 3500, 2, ram_cap_gb=59.0)                   # 5.0.1 renders it at supersample 1.5
        self.assertEqual(s15.stages[0].supersample, 1.5)
        self.assertFalse(B.plan_forced(s15, 59.0, mode='fast').ok)
        with self.assertRaises(ValueError):
            B.plan_forced(c, 59.0, mode='turbo')


class FastPlanRefusal(unittest.TestCase):
    def forced_bolt(self):
        return B.plan_forced(planner.plan(2048, 2048, 2, ram_cap_gb=59.0), 59.0, mode='fast')

    def test_a_forced_banded_bolt_plan_in_a_developer_build(self):
        p = self.forced_bolt()
        for plan in (p, p.to_dict()):
            with mock.patch.object(build_channel, 'CHANNEL', 'dev'):
                self.assertIsNone(engine_options.fast_plan_refusal(plan))
            with mock.patch.object(build_channel, 'CHANNEL', 'release'):
                self.assertEqual(engine_options.fast_plan_refusal(plan), 'size')
            self.assertEqual(engine_options.fast_plan_refusal(plan), 'size')          # the source tree is a release build

    def test_a_banded_redux_plan_is_never_bolts(self):
        p = B.plan_forced(planner.plan(2048, 2048, 2, ram_cap_gb=59.0), 59.0)
        for channel in ('dev', 'release'):
            with mock.patch.object(build_channel, 'CHANNEL', channel), mock.patch.object(B, 'BOLT_BANDED', True):
                self.assertEqual(engine_options.fast_plan_refusal(p), 'size')

    def test_an_unforced_banded_bolt_plan_waits_for_bolt_banded(self):
        with mock.patch.dict(B.BANDED_PROVEN_MP, PROVEN), mock.patch.object(B, 'BOLT_BANDED', True), \
                mock.patch.object(B, 'BXF_AVAILABLE', True):
            p = B.plan_banded(3000, 3000, 2, 59.0, mode='fast')
        self.assertTrue(p.ok, p.reason)
        for channel in ('dev', 'release'):
            with mock.patch.object(build_channel, 'CHANNEL', channel):
                self.assertEqual(engine_options.fast_plan_refusal(p), 'size')
                with mock.patch.object(B, 'BOLT_BANDED', True):
                    self.assertIsNone(engine_options.fast_plan_refusal(p))

    def test_no_recipe_comes_first(self):
        p = self.forced_bolt()
        with mock.patch.object(fast_recipe, 'RECIPE', None), mock.patch.object(build_channel, 'CHANNEL', 'dev'):
            self.assertEqual(engine_options.fast_plan_refusal(p), 'no_recipe')

    def test_classic_plans_are_unchanged(self):
        for w, h, f in ((2048, 2048, 2), (1280, 1600, 4), (3500, 2188, 2), (2800, 3500, 2)):
            c = planner.plan(w, h, f, ram_cap_gb=59.0)
            for channel in ('dev', 'release'):
                with mock.patch.object(build_channel, 'CHANNEL', channel), mock.patch.object(B, 'BOLT_BANDED', True):
                    got = engine_options.fast_plan_refusal(c)
                self.assertEqual(got, engine_options.fast_plan_refusal(c.to_dict()))
            self.assertEqual(engine_options.fast_plan_refusal(c), ('scale' if f > 2 else
                                                                   'size' if c.stages[0].supersample != 2 else None))


if __name__ == '__main__':
    unittest.main()
