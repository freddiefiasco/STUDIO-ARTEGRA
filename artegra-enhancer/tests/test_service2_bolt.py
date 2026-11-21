"""5.0.2 (build wave 2, service package, item 4; contract bolt): for a forced developer run, Runner._planned passes the job's
run mode to banded_plan.plan_forced(plan, ram_cap, mode=mode) (the real function gains `mode` in the plan package; here it
is a stub that takes it). A Large-image Bolt result's sidecar carries the Fast recipe's sidecar keys, as the classic Bolt
sidecar does. BOLT_BANDED stays False: nothing here admits a banded Bolt plan outside a developer build.

In process: a Runner made without its start-up, stub plans and the stand-in Fast recipe of the fake engine. Sizes only."""
import threading
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest import mock

from engine import banded_plan, fast_recipe, planner
from service import banded_runner, build_channel, runner as runner_mod
from service.runner import Runner

REC = {'width': 2048, 'height': 2048, 'name': 'card.png', 'alpha': False}


class Forced:
    """A stand-in for banded_plan.plan_forced with the contract's signature: plan_forced(classic, cap, mode='redux')."""

    def __init__(self):
        self.calls = []

    def __call__(self, classic, cap, mode='redux'):
        self.calls.append((classic.output_size, cap, mode))
        return planner.Plan(True, classic.factor, tuple(classic.input_size), tuple(classic.output_size), list(classic.stages),
                            classic.minutes, classic.peak_ram_gb, engine='banded',
                            banded={'mode': 'bolt' if mode == 'fast' else 'redux', 'forced': True})


def bare():
    r = object.__new__(Runner)
    r.settings = SimpleNamespace(get=lambda: {'ram_cap_gb': 59.0, 'gpus': [0]})
    r.log = mock.Mock()
    return r


class ThePlannedMode(unittest.TestCase):
    def test_a_forced_run_passes_the_jobs_run_mode(self):
        r = bare()
        stub = Forced()
        with mock.patch.object(banded_plan, 'plan_forced', stub), mock.patch.object(build_channel, 'is_dev', return_value=True):
            for mode in ('standard', 'fast'):
                p = r._planned(REC, 2, 59.0, force='banded', mode=mode)
                self.assertEqual(p.engine, 'banded')
        self.assertEqual([c[2] for c in stub.calls], ['standard', 'fast'])
        self.assertEqual({c[1] for c in stub.calls}, {59.0})

    def test_the_mode_defaults_to_redux_and_a_release_build_never_forces(self):
        r = bare()
        stub = Forced()
        with mock.patch.object(banded_plan, 'plan_forced', stub), mock.patch.object(build_channel, 'is_dev', return_value=True):
            r._planned(REC, 2, 59.0, force='banded')
        self.assertEqual(stub.calls[0][2], 'standard')
        with mock.patch.object(banded_plan, 'plan_forced', stub), mock.patch.object(build_channel, 'is_dev', return_value=False):
            p = r._planned(REC, 2, 59.0, force='banded', mode='fast')
        self.assertEqual(p.engine, 'classic')
        self.assertEqual(len(stub.calls), 1)

    def test_an_unforced_plan_is_5_0_1s(self):
        r = bare()
        with mock.patch.object(banded_plan, 'plan_forced', side_effect=AssertionError('forced')):
            p = r._planned(REC, 2, 59.0, mode='fast')
        self.assertEqual(p.to_dict(), planner.plan(2048, 2048, 2, ram_cap_gb=59.0).to_dict())

    def test_the_queue_and_requeue_paths_pass_the_effective_mode(self):
        r = bare()
        r._check_mode = lambda eff, plan=None: None
        r._vram_refusal = lambda plan, protect=True, cards=None: None
        r._physical_refusal = lambda plan, params: None
        stub = Forced()
        with mock.patch.object(banded_plan, 'plan_forced', stub), mock.patch.object(build_channel, 'is_dev', return_value=True):
            eff, plan, _ = r._plan_for(REC, {'mode': 'fast', 'scale': 2}, force='banded')
            r._plan_for(REC, {'scale': 2}, force='banded')
        self.assertEqual(eff['mode'], 'fast')
        self.assertEqual(plan['banded']['mode'], 'bolt')
        self.assertEqual([c[2] for c in stub.calls], ['fast', 'standard'])


class TheBoltSidecar(unittest.TestCase):
    def plan(self, mode):
        return {'engine': 'banded', 'output_size': [4096, 4096], 'stages': [],
                'banded': {'bes': 'bes-1', 'mode': mode, 'finish': 'bxf-1', 'recipe': 'r501'}}

    def test_a_bolt_stage_records_the_recipes_sidecar_keys(self):
        recipe = runner_mod._test_fast_recipe()
        with mock.patch.object(fast_recipe, 'RECIPE', recipe):
            want = fast_recipe.sidecar_fields(recipe, {})
            self.assertEqual(banded_runner.bolt_sidecar(self.plan('bolt'), {}), want)
        self.assertEqual(want['recipe'], recipe['name'])
        self.assertEqual(want['version'], recipe['version'])

    def test_the_builds_own_fast_record_wins(self):
        info = {'fast': {'recipe': 'x', 'version': '2', 'ends': {'k': 1}}}
        self.assertEqual(banded_runner.bolt_sidecar(self.plan('bolt'), info), info['fast'])

    def test_a_redux_stage_records_none(self):
        self.assertIsNone(banded_runner.bolt_sidecar(self.plan('redux'), {'fast': {'recipe': 'x'}}))
        self.assertIsNone(banded_runner.bolt_sidecar({'engine': 'banded', 'banded': {}}, {}))

    def test_the_stage_entry_and_the_sidecar_carry_it_as_the_classic_bolt_sidecar_does(self):
        recipe = runner_mod._test_fast_recipe()
        updates = []
        it = {'id': 'i001', 'name': 'card.png', 'timings': {'stages': []}, 'plan': self.plan('bolt')}
        store = SimpleNamespace(item=lambda j, i: it, update_item=lambda j, i, **kw: updates.append(kw) or
                                it.update(timings=kw.get('timings', it['timings'])))
        r = SimpleNamespace(store=store)
        w = SimpleNamespace(memory_profile=SimpleNamespace(to_dict=lambda: {'name': 'reference'}))
        st = {'factor': 2.0, 'supersample': 2.0, 'input_size': [2048, 2048], 'render_size': [8192, 8192],
              'output_size': [4096, 4096], 'minutes': 3.0}
        with mock.patch.object(fast_recipe, 'RECIPE', recipe):
            banded_runner._mark_started(r, it, 'j1', 'i001', 0, 1, st, w, {'spot_options': {}, 'finish': 'bxf-1'}, {},
                                        Path("w"), None, {'denoise': 0.3, 'structure': 0.2,
                                                                                           'seed': 1}, 2048, 2048)
        entry = it['timings']['stages'][0]
        self.assertEqual(entry['fast'], fast_recipe.sidecar_fields(recipe, {}))
        # Runner._sidecar takes `fast` from the last stage that has it, for the classic and the Large-image sidecar alike
        stages = it['timings']['stages']
        fast = next((x.get('fast') for x in reversed(stages) if x.get('fast')), None)
        self.assertEqual(fast['recipe'], recipe['name'])

    def test_a_redux_stage_entry_has_no_fast_record(self):
        it = {'id': 'i001', 'name': 'card.png', 'timings': {'stages': []}, 'plan': self.plan('redux')}
        store = SimpleNamespace(item=lambda j, i: it, update_item=lambda j, i, **kw: it.update(timings=kw['timings']))
        w = SimpleNamespace(memory_profile=SimpleNamespace(to_dict=lambda: {'name': 'reference'}))
        st = {'factor': 2.0, 'supersample': 2.0, 'input_size': [2048, 2048], 'render_size': [8192, 8192],
              'output_size': [4096, 4096], 'minutes': 3.0}
        banded_runner._mark_started(SimpleNamespace(store=store), it, 'j1', 'i001', 0, 1, st, w, {'spot_options': {}}, {},
                                    Path("w"), None,
                                    {'denoise': 0.3, 'structure': 0.2, 'seed': 1}, 2048, 2048)
        self.assertNotIn('fast', it['timings']['stages'][0])


if __name__ == '__main__':
    unittest.main()
