"""Banded Bolt, the planner's gaps (engine/banded_plan.py, service/engine_options.py; build wave 3, contract bolt):
- bolt_recipe() is None unless the installed Fast recipe is graph_banded.BOLT_RECIPE, the one the Large-image graph makes, so
  a Large-image Bolt plan made with any other recipe (the fake engine's CU_FAST_TEST stand-in) is refused in plain words
  before the start (the wave-2 merge's finding);
- engine_options.finish_info gives a forced banded Bolt plan its fast figures in a developer build, where fast_plan_refusal
  admits it;
- a Bolt stage's minutes are at Bolt's own rates (its 8 steps), never fewer than the classic Bolt stage's, and fewer than
  the same stage's at Redux's sampling rates;
- G7 passed on Bolt's own schedules, so a Bolt plan caps the Brownian cache at 8 (tests/test_plan3_g7.py).
Sizes only."""
import unittest
from unittest import mock

from engine import banded_plan as B
from engine import fast_recipe, graph_banded, planner
from service import build_channel, engine_options

PROVEN = {k: 10_000.0 for k in B.BANDED_PROVEN_MP}


def stand_in():
    """The fake engine's CU_FAST_TEST recipe, as service/runner.py installs it (tests only)."""
    from service.runner import _test_fast_recipe
    return _test_fast_recipe()


class TheRecipeMustBeTheOneTheGraphMakes(unittest.TestCase):
    def test_the_shipped_recipe(self):
        self.assertEqual(B.bolt_recipe(), graph_banded.BOLT_RECIPE)
        self.assertEqual(B.constants('bolt')['recipe'], graph_banded.BOLT_RECIPE)

    def test_another_recipe_is_none_and_refused_before_the_start(self):
        with mock.patch.object(fast_recipe, 'RECIPE', stand_in()):
            self.assertTrue(fast_recipe.installed())
            self.assertEqual(fast_recipe.describe()['recipe'], 'test-fast')
            self.assertIsNone(B.bolt_recipe())
            with self.assertRaises(ValueError):
                B.constants('bolt')
            with mock.patch.dict(B.BANDED_PROVEN_MP, PROVEN), mock.patch.object(B, 'BOLT_BANDED', True), \
                    mock.patch.object(B, 'BXF_AVAILABLE', True):
                p = B.plan_banded(3500, 2188, 2, 45.2, mode='fast')
                self.assertFalse(p.ok)
                self.assertTrue(p.reason.startswith(B.BOLT_UNAVAILABLE), p.reason)
                c = planner.plan(2048, 2048, 2, ram_cap_gb=59.0)
                f = B.plan_forced(c, 59.0, mode='fast')
                self.assertFalse(f.ok)
                self.assertTrue(f.reason.startswith(B.BOLT_UNAVAILABLE), f.reason)
        self.assertIn('Large-image engine', B.BOLT_UNAVAILABLE)

    def test_none_without_a_recipe(self):
        with mock.patch.object(fast_recipe, 'RECIPE', None):
            self.assertIsNone(B.bolt_recipe())

    def test_a_stored_bolt_plan_with_another_recipe_is_refused_by_fast(self):
        c = planner.plan(2048, 2048, 2, ram_cap_gb=59.0)
        with mock.patch.object(B, 'BXF_AVAILABLE', True):
            f = B.plan_forced(c, 59.0, mode='fast')
        self.assertTrue(f.ok, f.reason)
        d = f.to_dict()
        with mock.patch.object(build_channel, 'CHANNEL', 'dev'):
            self.assertIsNone(engine_options.fast_plan_refusal(d))
            d['banded']['recipe'] = 'test-fast@0'
            self.assertEqual(engine_options.fast_plan_refusal(d), 'no_recipe')
            d['banded']['recipe'] = graph_banded.BOLT_RECIPE
            with mock.patch.object(fast_recipe, 'RECIPE', stand_in()):
                self.assertEqual(engine_options.fast_plan_refusal(d), 'no_recipe')


class TheFastFiguresOfAForcedBoltPlan(unittest.TestCase):
    def forced(self):
        c = planner.plan(2048, 2048, 2, ram_cap_gb=59.0)
        with mock.patch.object(B, 'BXF_AVAILABLE', True):
            f = B.plan_forced(c, 59.0, mode='fast')
        self.assertTrue(f.ok, f.reason)
        return f

    def test_a_developer_build_gives_them(self):
        f = self.forced()
        with mock.patch.object(build_channel, 'CHANNEL', 'dev'):
            self.assertIsNone(engine_options.fast_plan_refusal(f))
            info = engine_options.finish_info(f.minutes, fast_available=True, plan=f)
        self.assertEqual(info['fast'], {'minutes': round(f.minutes * engine_options.BANDED_FACTOR, 1),
                                        'factor': engine_options.BANDED_FACTOR})
        self.assertIsNone(info['fast_refusal'])
        self.assertEqual(info['single']['fast'], dict(info['fast'], cards=1))

    def test_a_release_build_or_a_redux_plan_does_not(self):
        f = self.forced()
        info = engine_options.finish_info(f.minutes, fast_available=True, plan=f)       # the source tree is a release build
        self.assertIsNone(info['fast'])
        self.assertEqual(engine_options.fast_plan_refusal(f), 'size')
        self.assertIn(info['fast_refusal']['reason'], ('size', 'memory', 'memory_all'))   # fast_plan_reason's words
        with mock.patch.object(B, 'BXF_AVAILABLE', True), mock.patch.dict(B.BANDED_PROVEN_MP, PROVEN):
            r = B.plan_forced(planner.plan(2048, 2048, 2, ram_cap_gb=59.0), 59.0)
        with mock.patch.object(build_channel, 'CHANNEL', 'dev'):
            info = engine_options.finish_info(r.minutes, fast_available=True, plan=r)
        self.assertIsNone(info['fast'])                                  # a Redux plan: fast_plan_reason's own words
        self.assertIn(info['fast_refusal']['reason'], ('size', 'memory', 'memory_all'))
        with mock.patch.object(build_channel, 'CHANNEL', 'dev'):
            info = engine_options.finish_info(f.minutes, fast_available=False, fast_reason='files_missing', plan=f)
        self.assertIsNone(info['fast'])
        self.assertEqual(info['fast_refusal']['reason'], 'files_missing')


class BoltsOwnMinutes(unittest.TestCase):
    def test_the_constants_are_the_recipes(self):
        self.assertEqual(B.BOLT_STEPS, graph_banded.BOLT['steps'])
        self.assertEqual(B.BOLT_STEPS, fast_recipe.STEPS)
        self.assertEqual(B.BOLT_ETA_FACTOR, fast_recipe.RECIPE['eta_factor'])
        self.assertEqual(f"{fast_recipe.RECIPE['name']}@{fast_recipe.RECIPE['version']}", graph_banded.BOLT_RECIPE)

    def test_at_least_the_classic_bolt_stage_and_below_redux(self):
        n = 0
        for w, h in ((2048, 2048), (3500, 2188), (2800, 3500), (1280, 1600), (3000, 3000), (1024, 4000)):
            c = planner.plan(w, h, 2, ram_cap_gb=122.2)
            with mock.patch.object(B, 'BXF_AVAILABLE', True):
                f = B.plan_forced(c, 122.2, mode='fast')
                r = B.plan_forced(c, 122.2)
            if not f.ok:
                continue
            n += 1
            for sf, sr, sc in zip(f.stages, r.stages, c.stages):
                self.assertEqual(sf.mode, 'bolt')
                self.assertEqual(sr.mode, 'redux')
                classic_bolt = sc.minutes * fast_recipe.RECIPE['eta_factor']
                self.assertGreaterEqual(B.banded_minutes(sf, sf.split_finish) + 0.05, classic_bolt)
                self.assertGreaterEqual(B.banded_minutes(sf, sf.split_finish) + 1e-9, B.classic_bolt_minutes(sf))
                self.assertLess(B.banded_minutes(sf, sf.split_finish), B.banded_minutes(dict(sf.__dict__, mode='redux'),
                                                                                     sf.split_finish))
                self.assertAlmostEqual(sf.minutes, round(B.banded_minutes(sf, sf.split_finish), 1))
        self.assertGreater(n, 2)


if __name__ == '__main__':
    unittest.main()
