"""5.0.2 (build wave 2, service package, item 5: A9 and contract finish_inputs): a split stage's sub-stage checkpoint is
matched on what makes its pixels only.

- A9: turning Detailed preview on or off between the interruption and the resume keeps a valid checkpoint (the live
  preview's own input is left out of prompt A's graph match); a real change (the seed, a slider, a pixel constant) still
  voids it.
- finish_inputs: the plan's non-pixel constants bxf_band_gb and bxf_processes, and finish_tier (the checkpoint is made
  before the finish), are left out of the match, and so is the machine class, which follows the memory cap. A cap change
  or the banded finish becoming available (wave 3's BXF_AVAILABLE) keeps a valid checkpoint, and a checkpoint written
  before these constants existed is still valid. A finished stage records the tier it was made with.

In process, with the split-stage fixture of tests/test_admission_split.py (banded_runner.run_stage, a stub runner and
engine, the fake engine's plane writer). Sizes and synthetic pixels only."""
import json
import tempfile
import unittest

from engine import graph_banded
from service import banded_runner
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


if __name__ == '__main__':
    unittest.main()
