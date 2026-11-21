"""5.0.2 (build wave 2, service package, item 5: A9 and contract finish_inputs): a split stage's sub-stage checkpoint is
matched on what makes its pixels only.

- A9: turning Detailed preview on or off between the interruption and the resume keeps a valid checkpoint (the live
  preview's own input is left out of prompt A's graph match); a real change (the seed, a slider, a pixel constant) still
  voids it.
- finish_inputs: the plan's non-pixel constants bxf_band_gb and bxf_processes, and finish_tier (the checkpoint is made
  before the finish), are left out of the match, and so is the machine class, which follows the memory cap. A cap change
  or the banded finish becoming available (wave 3's BXF_AVAILABLE) keeps a valid checkpoint, and a checkpoint written
  before these constants existed is still valid. A finished stage records the tier it was made with.
- The split itself (check S2): a re-plan at another cap can drop a stage's split_finish while the pixels stay the same, and a
  valid checkpoint is then still used (prompt B only), never deleted.

In process, with the split-stage fixture of tests/test_admission_split.py (banded_runner.run_stage, a stub runner and
engine, the fake engine's plane writer). Sizes and synthetic pixels only."""
import copy
import json
import tempfile
import unittest
from unittest import mock

from engine import banded_plan, graph_banded, planes
from service import banded_runner
from service.util import same_plan
from tests.test_admission_split import Fixture, split_plan
from service.runner import ItemFailure

NEW_CONSTANTS = {'bxf_band_gb': 3.0, 'bxf_processes': 2, 'finish_tier': 'tier3'}


def with_constants(**kw):
    p = split_plan()
    p['banded'] = dict(p['banded'], **kw)
    return p


class Base(unittest.TestCase):
    def crashed_in_b(self, td, detailed=False, **kw):
        fx = Fixture(td, **kw)
        fx.r.detailed_info = lambda: {'on': detailed}
        fx.engine.fail_part = 'B'
        with self.assertRaises(ItemFailure):
            fx.run(0)
        self.assertEqual(fx.engine.parts, ['A', 'B'])
        self.assertTrue((fx.plane_dir() / banded_runner.CHECKPOINT_FILE).is_file())
        fx.engine.parts.clear()
        fx.engine.state, fx.engine.client.prompts_sent = 'ready', 0
        return fx

    def resumed(self, fx):
        fx.run(0)
        self.assertEqual(fx.engine.parts, ['B'])
        self.assertEqual([c for c in fx.r.log.warn.call_args_list if c.args[0] == 'banded_checkpoint_refused'], [])

    def voided(self, fx, why):
        fx.run(0)
        self.assertEqual(fx.engine.parts, ['A', 'B'])
        warn = [c.args[1] for c in fx.r.log.warn.call_args_list if c.args[0] == 'banded_checkpoint_refused']
        self.assertEqual(len(warn), 1)
        self.assertIn(why, warn[0])


class TheDetailedPreview(Base):
    def test_turning_detailed_preview_on_keeps_a_valid_checkpoint(self):
        with tempfile.TemporaryDirectory() as td:
            fx = self.crashed_in_b(td, detailed=False)
            fx.r.detailed_info = lambda: {'on': True}
            self.resumed(fx)

    def test_turning_it_off_keeps_it_too(self):
        with tempfile.TemporaryDirectory() as td:
            fx = self.crashed_in_b(td, detailed=True)
            fx.r.detailed_info = lambda: {'on': False}
            self.resumed(fx)

    def test_a_real_change_still_voids_it(self):
        with tempfile.TemporaryDirectory() as td:
            fx = self.crashed_in_b(td)
            fx.r.detailed_info = lambda: {'on': True}
            fx.settings = {'custom': True, 'creativity': 0.7}
            fx.item['settings'] = fx.settings
            self.voided(fx, 'other settings')

    def test_only_the_preview_input_of_the_spot_node_is_left_out(self):
        g = {'1': {'class_type': graph_banded.SPOT_CLASS, 'inputs': {'live_preview': 'rough', 'seed': 1, 'run_id': 'a'}},
             '2': {'class_type': 'CUPlaneInput', 'inputs': {'plane': 'x', 'run_id': 'b'}}}
        same = {'1': {'class_type': graph_banded.SPOT_CLASS, 'inputs': {'seed': 1, 'run_id': 'c'}},
                '2': {'class_type': 'CUPlaneInput', 'inputs': {'plane': 'x', 'run_id': 'd'}}}
        self.assertEqual(banded_runner.graph_sha(g), banded_runner.graph_sha(same))
        other = json.loads(json.dumps(g))
        other['1']['inputs']['seed'] = 2
        self.assertNotEqual(banded_runner.graph_sha(g), banded_runner.graph_sha(other))
        elsewhere = json.loads(json.dumps(g))
        elsewhere['2']['inputs']['live_preview'] = 'rough'            # the same name on another class still counts
        self.assertNotEqual(banded_runner.graph_sha(g), banded_runner.graph_sha(elsewhere))


class TheFinishConstants(Base):
    def test_band_budget_processes_and_tier_are_ignored_and_a_cap_change_keeps_it(self):
        with tempfile.TemporaryDirectory() as td:
            fx = self.crashed_in_b(td, plan=with_constants(**NEW_CONSTANTS, machine_class='pc64'))
            rec = json.loads((fx.plane_dir() / banded_runner.CHECKPOINT_FILE).read_text(encoding='utf8'))
            for k in ('bxf_band_gb', 'bxf_processes', 'finish_tier', 'machine_class'):
                self.assertNotIn(k, rec['constants'])
            fx.item['plan'] = fx.plan = with_constants(bxf_band_gb=6.0, bxf_processes=4, finish_tier='bxf',
                                                       machine_class='ws128')
            self.resumed(fx)

    def test_the_banded_finish_becoming_available_keeps_it(self):
        with tempfile.TemporaryDirectory() as td:
            fx = self.crashed_in_b(td, plan=with_constants(finish_tier='tier3'))
            fx.item['plan'] = fx.plan = with_constants(finish_tier='bxf')
            self.resumed(fx)

    def test_a_checkpoint_written_before_the_constants_existed_is_still_valid(self):
        with tempfile.TemporaryDirectory() as td:
            fx = self.crashed_in_b(td)                                  # the wave-1 plan: no such constants
            fx.item['plan'] = fx.plan = with_constants(**NEW_CONSTANTS)
            self.resumed(fx)
        with tempfile.TemporaryDirectory() as td:
            fx = self.crashed_in_b(td, plan=with_constants(**NEW_CONSTANTS))
            path = fx.plane_dir() / banded_runner.CHECKPOINT_FILE
            rec = json.loads(path.read_text(encoding='utf8'))
            rec['constants'].update(NEW_CONSTANTS)                      # a record that carries them is matched without them
            path.write_text(json.dumps(rec), encoding='utf8')
            self.resumed(fx)

    def test_a_pixel_constant_still_voids_it(self):
        with tempfile.TemporaryDirectory() as td:
            fx = self.crashed_in_b(td, plan=with_constants(**NEW_CONSTANTS))
            fx.item['plan'] = fx.plan = with_constants(**NEW_CONSTANTS, cmap='whole')
            self.voided(fx, 'other Large-image engine settings')

    def test_the_finished_stage_records_its_tier(self):
        with tempfile.TemporaryDirectory() as td:
            fx = self.crashed_in_b(td, plan=with_constants(finish_tier='tier3'))
            fx.run(0)
            parts = {x.get('part'): x for x in fx.item['timings']['stages'] if x.get('index') == 0}
            self.assertEqual(parts['B']['finish_tier'], 'tier3')
            self.assertEqual(banded_runner.finish_tiers(fx.item['timings']['stages']), [{'index': 0, 'finish_tier': 'tier3'}])

    def test_a_plan_without_the_constant_records_todays_ladder(self):
        self.assertEqual(banded_runner.finish_tier_of({'banded': {}}), 'ladder')
        self.assertEqual(banded_runner.finish_tier_of({'banded': {'finish_tier': 'bxf'}}), 'bxf')
        self.assertEqual(banded_runner.finish_tiers([{'index': 0, 'part': 'A'}, {'index': 0, 'part': 'B',
                                                                                 'finish_tier': 'ladder'}]),
                         [{'index': 0, 'finish_tier': 'ladder'}])


def without_split(plan):
    """The same plan with no stage split: what a re-plan at another memory cap can give (banded_plan.split_needed)."""
    p = copy.deepcopy(plan)
    for st in p['stages']:
        st['split_finish'] = False
    return p


class TheSplitFollowingTheCap(Base):
    """The split finish (L3r) is a stage field that follows the memory cap and the finish tier (banded_plan.split_needed).
    A re-plan when the image is queued again or given new settings (Runner.requeue_item, set_item_settings) can drop it while
    service.util.same_plan still holds, so a stopped image keeps its work folder. A valid checkpoint is used whatever the
    plan now says about the split: prompt B in a fresh engine (L3r is pixel-neutral, G2r), within the plan's bound (a split
    stage's peaks are at most the unsplit one's). An invalid one is refused as before and the stage runs as planned."""

    def test_the_cap_moves_the_split_while_the_plan_keeps_its_pixels(self):
        proven = {'ws128': 1e9, 'pc64': 1e9, 'pc48': 1e9}
        made = {}
        with mock.patch.object(banded_plan, 'BXF_AVAILABLE', True, create=True):
            for c10 in range(520, 640, 5):                       # caps of a 64 GB PC (machine class pc64)
                p = banded_plan.plan_banded(3500, 2188, 6, c10 / 10, proven=proven)
                if p.ok:
                    made[c10 / 10] = p.to_dict()
        pairs = [(a, b) for a in made for b in made if a < b and same_plan(made[a], made[b])
                 and [s['split_finish'] for s in made[a]['stages']] != [s['split_finish'] for s in made[b]['stages']]]
        self.assertTrue(pairs, '6x of 3500 x 2188: no two caps with the same pixels and another split')

    def test_a_re_plan_that_drops_the_split_resumes_with_prompt_b_only(self):
        with tempfile.TemporaryDirectory() as td:
            fx = self.crashed_in_b(td)
            new = without_split(fx.plan)
            self.assertTrue(same_plan(fx.plan, new))
            fx.item['plan'] = fx.plan = new
            self.resumed(fx)
            ow, oh = new['stages'][0]['output_size']
            planes.validate(fx.work / 'stage0.u8', shape=(oh, ow, 3), dtype='u8')
            b = [x for x in fx.item['timings']['stages'] if x.get('index') == 0 and x.get('part') == 'B']
            self.assertTrue(b and b[-1]['split_finish'])                 # the record says what ran: the finish split
            self.assertFalse(fx.plan['stages'][0]['split_finish'])      # the stored plan is not changed
            resume = [c for c in fx.r.log.info.call_args_list if c.args[0] == 'banded_checkpoint_resume']
            self.assertEqual(len(resume), 1)
            self.assertIs(resume[0].kwargs['data']['plan_split_finish'], False)

    def test_the_planners_own_re_plan_at_a_lower_cap_resumes_with_prompt_b_only(self):
        """The same with real plans: the fixture's image split at the workstation's cap and not at a 64 GB PC's."""
        from engine import planner
        classic = planner.plan(1100, 900, 2, ram_cap_gb=59.0)
        high = banded_plan.plan_forced(classic, 122.2).to_dict()
        low = banded_plan.plan_forced(classic, 59.0).to_dict()
        self.assertEqual(([s['split_finish'] for s in high['stages']], [s['split_finish'] for s in low['stages']]),
                         ([True], [False]))
        self.assertTrue(same_plan(high, low))
        with tempfile.TemporaryDirectory() as td:
            fx = self.crashed_in_b(td, plan=high)
            fx.item['plan'] = fx.plan = low
            self.resumed(fx)

    def test_a_warm_engine_is_restarted_before_that_prompt_b(self):
        with tempfile.TemporaryDirectory() as td:
            fx = self.crashed_in_b(td)
            fx.item['plan'] = fx.plan = without_split(fx.plan)
            fx.engine.client.prompts_sent = 3                           # the engine has run other prompts since
            stops = fx.engine.stops
            self.resumed(fx)
            self.assertEqual(fx.engine.stops, stops + 1)

    def test_a_real_change_with_the_split_dropped_still_voids_it_and_runs_as_planned(self):
        with tempfile.TemporaryDirectory() as td:
            fx = self.crashed_in_b(td)
            fx.item['plan'] = fx.plan = without_split(fx.plan)
            fx.settings = {'custom': True, 'creativity': 0.7}
            fx.item['settings'] = fx.settings
            fx.run(0)
            self.assertEqual(fx.engine.parts, [None])                    # one prompt, as the plan now says
            warn = [c.args[1] for c in fx.r.log.warn.call_args_list if c.args[0] == 'banded_checkpoint_refused']
            self.assertEqual(len(warn), 1)
            self.assertIn('other settings', warn[0])
            self.assertFalse(fx.plane_dir().exists())

    def test_a_stage_that_is_not_split_and_has_no_checkpoint_builds_one_prompt_only(self):
        with tempfile.TemporaryDirectory() as td:
            fx = Fixture(td, plan=without_split(split_plan()))
            fx.plane_dir().mkdir(parents=True)                           # a folder left by a stopped one-prompt stage
            (fx.plane_dir() / 'input.plane').write_bytes(b'partial')
            built = []
            real = graph_banded.build_product
            with mock.patch.object(graph_banded, 'build_product',
                                   side_effect=lambda *a, **kw: built.append(kw.get('part')) or real(*a, **kw)):
                fx.run(0)
            self.assertEqual(built, [None])                               # no prompt-A graph is made to look for one
            self.assertEqual(fx.engine.parts, [None])
            self.assertEqual([c for c in fx.r.log.warn.call_args_list if c.args[0] == 'banded_checkpoint_refused'], [])


if __name__ == '__main__':
    unittest.main()


class TheRunnersResumeMatch(unittest.TestCase):
    """The runner's own resume match (finished passes kept across a restart or a re-queue: Runner._kept_matches and
    service.util.same_plan, whose pixel keys are util.BANDED_PIXEL_KEYS) follows contracts.finish_inputs too: the finish's
    band budget, process count and tier, and the machine class, are not pixel keys; every pixel constant still is."""

    def test_kept_passes_survive_the_non_pixel_constants_and_not_a_pixel_one(self):
        from engine import controls
        from service.runner import Runner
        from service.util import same_plan
        eff = controls.resolve({})[1]
        made = with_constants(**NEW_CONSTANTS, machine_class='pc64')
        kept = {'effective': eff, 'plan': made}
        for change in ({'bxf_band_gb': 6.0}, {'bxf_processes': 4}, {'finish_tier': 'bxf'}, {'machine_class': 'ws128'},
                       {'bxf_band_gb': 2.0, 'bxf_processes': 1, 'finish_tier': 'ladder', 'machine_class': 'pc48'}):
            now = with_constants(**{**NEW_CONSTANTS, 'machine_class': 'pc64', **change})
            self.assertTrue(Runner._kept_matches(kept, eff, now), change)
            self.assertTrue(same_plan(made, now), change)
        without = split_plan()                                         # a plan made before the constants existed
        self.assertTrue(Runner._kept_matches({'effective': eff, 'plan': without}, eff, made))
        for pixel in ({'finish': 'bxf-1h'}, {'brownian_cache': 8}, {'cmap': 'whole'}, {'window': 2048}):
            now = with_constants(**NEW_CONSTANTS, **pixel)
            self.assertFalse(Runner._kept_matches(kept, eff, now), pixel)
