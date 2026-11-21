"""Card-factor deadlines (engine design ENGINE-DESIGN.md 8.1 and 8.3; B14): no smaller card is killed by a deadline built for
an RTX 5090, and a 5090 keeps 5.0.1's deadlines to the second. In-process only (Runner with SimpleNamespace stubs; no
service process, no port). Sizes only."""
import json
import threading
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import mock

from engine import controls, planner, vram_model
from service import card_factor, engine_options, memory_policy
from service import runner as runner_mod
from service.comfy import ProgressTracker
from service.runner import ItemFailure, Runner

FIX = Path(__file__).parent / 'fixtures'
SIZES = [(w, h) for w in (512, 777, 1280, 1600, 2188, 2800, 3500, 4096, 6000) for h in (512, 1600, 2188, 2800, 3500)]
CAPS = (None, 45.2, 59.0, 61.2, 100.0, 122.2)
CARD32 = {'index': 0, 'uuid': 'GPU-5090', 'name': 'NVIDIA GeForce RTX 5090', 'mem_total_gb': 31.84, 'mem_free_gb': 30.0}
CARD24 = {'index': 0, 'uuid': 'GPU-4090', 'name': 'NVIDIA GeForce RTX 4090', 'mem_total_gb': 23.99, 'mem_free_gb': 22.0}
CARD12 = {'index': 0, 'uuid': 'GPU-4070', 'name': 'NVIDIA GeForce RTX 4070', 'mem_total_gb': 11.99, 'mem_free_gb': 11.0}


def grid_stages():
    for w, h in SIZES:
        for f in controls.SCALES:
            for cap in CAPS:
                p = planner.plan(w, h, f, ram_cap_gb=cap)
                if p.ok:
                    for s in p.to_dict()['stages']:
                        yield s


def stub_runner(cards, state_dir=None, override=None):
    r = object.__new__(Runner)
    r.deadline_override = override
    r.stall_s = 600.0
    r.mode = 'fake'
    r.log = mock.Mock()
    r.card_factors = card_factor.CardFactors(Path(state_dir) / 'card_factors.json' if state_dir else None)
    r.gpu_list = lambda max_age=None: ([dict(c) for c in cards], None)
    return r


class Helper(unittest.TestCase):
    def test_at_cf_1_every_g0a_stage_keeps_501s_deadline_to_the_bit(self):
        n = 0
        for st in grid_stages():
            n += 1
            old = None or (3 * st['minutes'] + 10) * 60            # 5.0.1's line, runner.py _run_stage
            self.assertEqual(card_factor.deadline_s(st['minutes'], 1.0, None), old)
            self.assertEqual(card_factor.deadline_s(st['minutes'], 0.4, None), old)   # never below 1.0
            self.assertEqual(card_factor.deadline_s(st['minutes'], 1.0, 77.0), 77.0)  # the override wins, as in 5.0.1
        self.assertGreater(n, 400)

    def test_the_factor_scales_the_minutes_term_only(self):
        self.assertEqual(card_factor.deadline_s(38.6, 3.0), (3 * 38.6 * 3.0 + 10) * 60)
        self.assertGreater(card_factor.deadline_s(38.6, 3.0), card_factor.deadline_s(38.6, 1.0) * 2.5)

    def test_stall(self):
        self.assertEqual(card_factor.stall_s(600.0, 1.0), 600.0)
        self.assertEqual(card_factor.stall_s(600.0, 0.5), 600.0)
        self.assertEqual(card_factor.stall_s(600.0, 2.5), 1500.0)


class Factors(unittest.TestCase):
    def test_a_card_over_24_gib_is_1_by_rule_and_never_measured(self):
        cf = card_factor.CardFactors(None)
        self.assertEqual(cf.factor(CARD32), 1.0)
        self.assertIsNone(cf.record(CARD32, 0.9))          # a slow reading changes nothing on a 5090
        self.assertEqual(cf.factor(CARD32), 1.0)
        self.assertFalse(card_factor.measures(CARD32))
        self.assertEqual(cf.factor({'name': 'x', 'mem_total_gb': None}), 1.0)   # unknown memory: as 5.0.1
        self.assertEqual(cf.factor({}), 1.0)

    def test_before_the_first_measurement_the_class_table_x2(self):
        cf = card_factor.CardFactors(None)
        ratio = max(170 / 46, 1792 / 504)                   # RTX 4070 against the RTX 5090
        self.assertAlmostEqual(cf.factor(CARD12), round(ratio * 2, 3), places=3)
        self.assertEqual(cf.source(CARD12), 'class')
        unknown = {'name': 'NVIDIA Some Future Card', 'mem_total_gb': 11.99}
        slowest12 = max(vram_model.class_speed_ratio(r) for r in vram_model.CARD_CLASSES['cards'] if r['memory_gb'] == 12)
        self.assertAlmostEqual(cf.factor(unknown), round(slowest12 * 2, 3), places=3)
        self.assertGreaterEqual(cf.factor(CARD24), 1.0)

    def test_measured_over_the_5090_and_never_below_1(self):
        with TemporaryDirectory() as td:
            cf = card_factor.CardFactors(Path(td) / 'card_factors.json')
            cf.record(CARD12, card_factor.REF_S_PER_WINDOW * 3)
            self.assertAlmostEqual(cf.factor(CARD12), 3.0, places=3)
            self.assertEqual(cf.source(CARD12), 'measured')
            cf.record(CARD12, card_factor.REF_S_PER_WINDOW * 5)       # half the old, half the new (spot.record_speed)
            self.assertAlmostEqual(cf.factor(CARD12), 4.0, places=3)
            again = card_factor.CardFactors(Path(td) / 'card_factors.json')   # persisted per card
            self.assertAlmostEqual(again.factor(CARD12), 4.0, places=3)
            self.assertEqual(again.factor(dict(CARD12, uuid='GPU-other')), card_factor.class_factor(CARD12))
            fast = dict(CARD24, uuid='GPU-fast')
            again.record(fast, card_factor.REF_S_PER_WINDOW / 2)
            self.assertEqual(again.factor(fast), 1.0)
            self.assertIsNone(again.record(CARD12, card_factor.REF_S_PER_WINDOW * 500))   # a broken record is ignored

    def test_a_damaged_store_reads_as_empty(self):
        with TemporaryDirectory() as td:
            p = Path(td) / 'card_factors.json'
            p.write_text('{not json', encoding='utf8')
            self.assertEqual(card_factor.CardFactors(p).factor(CARD12), card_factor.class_factor(CARD12))

    def test_the_class_table_is_registered(self):
        reg = json.loads((FIX / 'card_classes_5_0_2.json').read_text(encoding='utf8'))
        self.assertEqual(reg, vram_model.CARD_CLASSES)
        ref = vram_model.CARD_CLASSES['reference']
        self.assertEqual(vram_model.class_speed_ratio(ref), 1.0)
        for r in vram_model.CARD_CLASSES['cards']:
            self.assertGreaterEqual(vram_model.class_speed_ratio(r), 1.0, r['name'])

    def test_names_and_variants(self):
        self.assertEqual(vram_model.card_class('NVIDIA GeForce RTX 4060 Ti', 7.99)['memory_gb'], 8)
        self.assertEqual(vram_model.card_class('NVIDIA GeForce RTX 4060 Ti', 15.99)['memory_gb'], 16)
        self.assertEqual(vram_model.card_class('NVIDIA GeForce RTX 3080', 9.99)['sm'], 68)
        self.assertIsNone(vram_model.card_class('NVIDIA GeForce GTX 1080', 8.0))


class TimingRecords(unittest.TestCase):
    def rec(self, per_window, step0=9.0, split=False):
        calls, t = [], 0.0
        for step in range(6):
            n = 16
            d = (step0 if step == 0 else per_window) * n
            calls.append(['main', step, n, t, t + d, 'fuse'])
            calls.append(['pag', step, 0, t + d, t + d, 'precomputed'])
            t += d
        return {'label': 'merged-sp0-b1-pf1-cn0-np1-fp1', 'steps': 6, 'calls': calls, 'window_split': split}

    def test_the_first_step_is_left_out(self):
        self.assertAlmostEqual(card_factor.window_seconds(self.rec(0.3)), 0.3)
        self.assertIsNone(card_factor.window_seconds(self.rec(0.3, split=True)))
        self.assertIsNone(card_factor.window_seconds({'calls': [['main', 0, 16, 0.0, 1.0]]}))
        self.assertIsNone(card_factor.window_seconds(None))

    def test_records_of_this_prompt_are_read_and_removed(self):
        with TemporaryDirectory() as td:
            d = Path(td) / 'claude_timing'
            d.mkdir()
            (d / 'merged-x_pid1_pass1_node19.json').write_text(json.dumps(self.rec(0.3)), encoding='utf8')
            (d / 'merged-x_pid1_pass2_node19.json').write_text(json.dumps(self.rec(0.5)), encoding='utf8')
            (d / 'merged-x_pid2_pass1_node19.json').write_text(json.dumps(self.rec(0.7)), encoding='utf8')
            (d / 'merged-x_pid1_pass3_node19.json').write_text('{bad', encoding='utf8')
            got = card_factor.read_records(td, 'pid1')
            self.assertEqual(sorted(round(x, 3) for x in got), [0.3, 0.5])
            self.assertEqual(sorted(p.name for p in d.iterdir()), ['merged-x_pid2_pass1_node19.json'])
            self.assertEqual(card_factor.read_records(Path(td) / 'missing', 'pid1'), [])

    def test_the_fake_engine_writes_the_record_spot_writes(self):
        from service import fake_comfy
        with TemporaryDirectory() as td:
            fc = object.__new__(fake_comfy.FakeComfy)
            fc.root = Path(td)
            g = {'3': {'class_type': 'ClaudeSpotTiles', 'inputs': {}}, '9': {'class_type': 'KSampler', 'inputs': {}}}
            with mock.patch.dict('os.environ', {'CU_FAKE_WINDOW_S': '0.25'}):
                fake_comfy.FakeComfy._timing_record(fc, g, 'pidx', 1, 5)
            with mock.patch.dict('os.environ', {'CU_FAKE_WINDOW_S': ''}):
                fake_comfy.FakeComfy._timing_record(fc, g, 'pidy', 1, 5)       # off: nothing written
            got = card_factor.read_records(Path(td) / 'output', 'pidx')
            self.assertEqual([round(x, 6) for x in got], [0.25])
            self.assertEqual(card_factor.read_records(Path(td) / 'output', 'pidy'), [])

    def test_the_worker_env(self):
        self.assertEqual(card_factor.worker_env({'A': '1'}, CARD32), {'A': '1'})
        self.assertEqual(card_factor.worker_env({}, CARD12), {card_factor.TIMING_ENV: '1'})
        self.assertEqual(card_factor.worker_env({}, None), {})


class RunnerUse(unittest.TestCase):
    def worker(self, gpu=0):
        return SimpleNamespace(gpu=gpu, gpus=(gpu,), output_dir=Path('nowhere'))

    def test_the_runner_deadline_at_cf_1_is_501s(self):
        r = stub_runner([CARD32])
        ctx = SimpleNamespace(card_factor=r.card_factor_of(self.worker()))
        self.assertEqual(ctx.card_factor, 1.0)
        for st in grid_stages():
            self.assertEqual(r._deadline_s(ctx, st), (3 * st['minutes'] + 10) * 60)
        self.assertEqual(r._deadline_s(SimpleNamespace(), {'minutes': 2.0}), (3 * 2.0 + 10) * 60)   # no factor yet: 1.0
        r.deadline_override = 120.0
        self.assertEqual(r._deadline_s(ctx, {'minutes': 50.0}), 120.0)

    def test_the_stall_limit_x_cf(self):
        r = stub_runner([CARD12])
        g = {'5': {'class_type': 'ClaudeV4Finish', 'inputs': {}}, '6': {'class_type': 'KSampler', 'inputs': {}}}
        st = {'output_size': [8000, 8000], 'render_size': [8000, 8000], 'padded_size': [4000, 4000]}
        base = Runner.stall_limit(r, g, '5', st)
        self.assertEqual(base, max(600.0, 3.0 * 15.0 * 64.0))
        self.assertEqual(Runner.stall_limit(r, g, '5', st, cf=3.0), base * 3.0)
        self.assertEqual(Runner.stall_limit(r, g, '6', st, cf=1.0), 600.0)
        self.assertEqual(Runner.stall_limit(r, g, '6', st, cf=2.0), 1200.0)

    def test_eta_x_cf_on_a_small_card_only(self):
        plan = planner.plan(3500, 2188, 2).to_dict()
        for cards, cf in (([CARD32], 1.0), ([CARD12], card_factor.class_factor(CARD12))):
            r = stub_runner(cards)
            base = engine_options.run_info('standard', plan=plan)
            run = r._with_card_factor(dict(base), cf)
            if cf == 1.0:
                self.assertEqual(run, base)                      # a 5090's run record is 5.0.1's, key for key
            else:
                self.assertAlmostEqual(run['factor'], round(base['factor'] * cf, 3))
                self.assertEqual(run['card_factor'], cf)

    def test_finish_info_x_cf(self):
        plan = planner.plan(3500, 2188, 4)
        want = engine_options.finish_info(plan.minutes, plan=plan)
        self.assertEqual(Runner._finish_x_cf(want, plan.minutes, 1.0), want)
        got = Runner._finish_x_cf(want, plan.minutes, 2.5)
        self.assertAlmostEqual(got['standard']['factor'], round(want['standard']['factor'] * 2.5, 3))
        self.assertAlmostEqual(got['standard']['minutes'], round(plan.minutes * got['standard']['factor'], 1))
        self.assertAlmostEqual(got['single']['standard']['factor'], round(want['single']['standard']['factor'] * 2.5, 3))


class TheRunStageHunkForTheMergeRole(unittest.TestCase):
    """The classic deadline line inside Runner._run_stage is the registered G0c hunk: the merge role replaces it (adds file,
    run_stage_hunk). This builds the replacement in memory, never on disk, and checks the guard's diff would have exactly
    the two registered hunks, and that the new line compiles where it stands."""
    BEFORE = "            deadline = self.deadline_override or (3 * st['minutes'] + 10) * 60\n"
    AFTER = "            deadline = self._deadline_s(ctx, st)\n"

    def test_the_replacement(self):
        import difflib
        import inspect
        import textwrap
        src = inspect.getsource(Runner._run_stage).replace('\r\n', '\n')
        if self.AFTER in src:                       # after the merge: the line is in place and the old one gone
            self.assertNotIn(self.BEFORE, src)
            return
        self.assertEqual(src.count(self.BEFORE), 1)
        new = src.replace(self.BEFORE, self.AFTER)
        compile(textwrap.dedent(new), '_run_stage', 'exec')
        old = (FIX / 'run_stage_5_0_1.txt').read_text(encoding='utf8')
        diff = ''.join(difflib.unified_diff(old.splitlines(True), new.splitlines(True), 'run_stage_5_0_1', 'run_stage_5_0_2',
                                            n=1))
        self.assertEqual(diff.count('@@ -'), 2)
        self.assertIn('-' + self.BEFORE, diff)
        self.assertIn('+' + self.AFTER, diff)
        self.assertTrue(diff.startswith((FIX / 'run_stage_5_0_2.diff').read_text(encoding='utf8')))


class SlowPromptAtCf3(unittest.TestCase):
    """_wait_prompt on a stub engine whose prompt finishes after 15 min (simulated clock): 5.0.1's deadline for a 1-minute
    stage is 13 min, so at cf 1.0 the prompt is stopped; at cf 3 (19 min) it finishes."""

    def run_wait(self, cf):
        r = stub_runner([CARD12])
        r.accepting = True
        r.unreachable_s = 30.0
        r.store = SimpleNamespace(update_item=lambda *a, **k: None)
        r._active_update = lambda *a, **k: None
        clock = [0.0]

        def mono():
            clock[0] += 5.0
            return clock[0]
        done_at = 15 * 60.0
        hist = {'status': {'completed': True, 'status_str': 'success'}, 'outputs': {}}
        client = SimpleNamespace(history=lambda pid, timeout=10.0: hist if clock[0] >= done_at else {})
        w = SimpleNamespace(ws=None, alive=lambda: True, client=client, gpu=0, gpus=(0,), output_dir=Path('nowhere'))
        ctx = SimpleNamespace(jid='j1', iid='i1', cancel=threading.Event(), shutdown=False, speed=None, pace=None, factor=1.0,
                              stage_factors=None, card_factor=cf)
        st = {'minutes': 1.0, 'output_size': [1024, 1024], 'render_size': [2048, 2048], 'padded_size': [512, 512]}
        plan = {'stages': [st], 'factor': 2}
        graph = {'1': {'class_type': 'KSampler', 'inputs': {}}}
        tracker = ProgressTracker(graph, 'pid')
        tracker.changed = SimpleNamespace(wait=lambda t: None, clear=lambda: None, set=lambda: None)
        with mock.patch.object(runner_mod.time, 'monotonic', mono):
            return Runner._wait_prompt(r, w, ctx, graph, 'pid', 0, 1, plan, r._deadline_s(ctx, st), 'cu_x', 'x.png', st,
                                       tracker)

    def test_cf_1_stops_the_slow_prompt_as_501_does(self):
        with self.assertRaises(ItemFailure) as e:
            self.run_wait(1.0)
        self.assertEqual(e.exception.event, 'deadline')
        self.assertEqual(e.exception.data['deadline_s'], (3 * 1.0 + 10) * 60)

    def test_cf_3_lets_it_finish(self):
        self.assertEqual(self.run_wait(3.0)['status']['status_str'], 'success')


if __name__ == '__main__':
    unittest.main()
