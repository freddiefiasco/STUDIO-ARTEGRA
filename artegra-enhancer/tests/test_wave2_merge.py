"""5.0.2 build wave 2: what the merge of the five packages relies on, checked in process (sizes only).

- The real-service split tests (tests/service/test_banded_service.py, test_admission_service.py and
  test_integ_large_image.py) run 8x of 4000 x 160 on the workstation class and expect every pass split into prompt A and a
  finish in a fresh engine. On the workstation class a stage splits when its finish phase binds its upper bound
  (banded_plan.split_needed). With the plan package's wave-2 model terms merged, 4000 x 64 (the wave-1 size) keeps its
  first passes whole, so the tests moved to a size whose every stage splits under either finish tier.
- The test launcher's CU_TEST_BXF_AVAILABLE (tests/qa/launch_service.py) plans a real-service test as if the banded exact
  finish were available, as the planner's own tests do with banded_plan.BXF_AVAILABLE (contract finish_tier). Only the
  launcher reads it: no product file names it, and the release build copies no test file.
- A forced developer Bolt plan made with the shipped Fast recipe builds its Large-image graph (contract bolt): the plan's
  recipe constant is the one graph_banded.bolt_patch copies."""
import ast
import unittest
from pathlib import Path
from unittest import mock

from engine import banded_plan, controls, fast_recipe, graph_banded, planner

ROOT = Path(__file__).resolve().parents[1]
DEV_SIZES = {'ws128': 2000.0, 'pc64': 2000.0, 'pc48': 2000.0}        # the real-service tests' CU_TEST_DEV_CHANNEL
WS_CAP = 122.2


class TheRealServiceSplitTestsPremise(unittest.TestCase):
    def test_8x_of_4000_x_160_splits_every_pass_on_the_workstation_under_either_tier(self):
        for bxf in (False, True):
            with self.subTest(bxf_available=bxf), mock.patch.object(banded_plan, 'BXF_AVAILABLE', bxf):
                p = banded_plan.plan_banded(4000, 160, 8, WS_CAP, proven=DEV_SIZES)
                self.assertTrue(p.ok, p.reason)
                self.assertEqual(p.output_size, (32000, 1280))
                self.assertEqual(p.banded['machine_class'], 'ws128')
                self.assertEqual(len(p.stages), 3)
                self.assertEqual([s.split_finish for s in p.stages], [True, True, True])
                for s in p.stages:
                    self.assertEqual(banded_plan.stage_peaks(s, 'ws128', False)['up'][1], 'finish')

    def test_the_wave_1_size_no_longer_splits_every_pass(self):
        """Why the tests moved: 8x of 4000 x 64 keeps at least one pass whole on the workstation under either tier."""
        for bxf in (False, True):
            with self.subTest(bxf_available=bxf), mock.patch.object(banded_plan, 'BXF_AVAILABLE', bxf):
                p = banded_plan.plan_banded(4000, 64, 8, WS_CAP, proven=DEV_SIZES)
                self.assertTrue(p.ok, p.reason)
                self.assertFalse(all(s.split_finish for s in p.stages))


class TheTestLaunchersFinishSwitch(unittest.TestCase):
    NAME = 'CU_TEST_BXF_AVAILABLE'

    def test_only_the_test_launcher_reads_it(self):
        launcher = (ROOT / 'tests' / 'qa' / 'launch_service.py').read_text(encoding='utf-8')
        self.assertIn(self.NAME, launcher)
        product = [ROOT / 'cu_service.py', ROOT / 'support_bundle.py']
        for d in ('engine', 'service', 'node_pack', 'host', 'runtime', 'ui'):
            product += [p for p in (ROOT / d).rglob('*') if p.is_file() and p.suffix in ('.py', '.qml', '.js', '.json')]
        for p in product:
            self.assertNotIn(self.NAME, p.read_text(encoding='utf-8', errors='replace'), p.relative_to(ROOT).as_posix())

    def test_the_release_build_copies_no_test_file(self):
        tree = ast.parse((ROOT / 'tools' / 'build_release.py').read_text(encoding='utf-8'))
        data = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == 'DATA_PATHS' for t in n.targets))
        self.assertFalse([p for p in data if p == 'tests' or p.startswith('tests/')], data)

    def test_the_shipped_default_stays_fail_closed(self):
        self.assertIs(banded_plan.BXF_AVAILABLE, False)
        self.assertEqual(banded_plan.finish_tier(), 'tier3')


class TheForcedBoltPlanBuildsWithTheShippedRecipe(unittest.TestCase):
    def test_plan_forced_in_bolt_mode_builds_its_large_image_graph(self):
        self.assertEqual(f"{fast_recipe.RECIPE['name']}@{fast_recipe.RECIPE['version']}", graph_banded.BOLT_RECIPE)
        classic = planner.plan(1280, 960, 2, ram_cap_gb=WS_CAP)
        self.assertTrue(classic.ok)
        self.assertEqual(classic.engine, 'classic')
        p = banded_plan.plan_forced(classic, WS_CAP, mode='fast')
        self.assertTrue(p.ok, p.reason)
        self.assertEqual(p.banded['mode'], 'bolt')
        self.assertEqual(p.banded['recipe'], graph_banded.BOLT_RECIPE)
        st = p.stages[0]
        params = controls.stage_params(controls.resolve({'mode': 'fast'})[0], 0)
        consts = p.to_dict()['banded']                   # what service/banded_runner.run_stage passes (plan['banded'])
        graph, info = graph_banded.build_product('in.plane', st.padded_size[0], st.padded_size[1], params, 'cu_s0',
                                                 'planes/s0', 'run', f=2, s=2, constants=consts)
        self.assertIn(graph_banded.SPOT_CLASS, {n['class_type'] for n in graph.values()})
        self.assertIn('fast', info)
        self.assertEqual((info['fast']['recipe'], info['fast']['version']),
                         (fast_recipe.RECIPE['name'], fast_recipe.RECIPE['version']))


if __name__ == '__main__':
    unittest.main()
