"""5.0.2 (build wave 2, service package, item 5: A4 and A6; ENGINE-DESIGN 8.1 and 8.3).

- A4: a new card of 24 GiB or less is timed at engine start, before its first image's prompt, by its own small prompt (a
  synthetic picture through the product's sampler stack; no classic graph changes), so its first image already runs and
  has its time said at its own factor, not at the class table x 2. A 32 GB card sends no such prompt and keeps cf 1.0 and
  5.0.1's deadlines to the second for every stage of the G0a grid. A failed measurement never fails the image.
- A6: the protected-area preview's 600 s limit follows the card factor (5.0.1's 600 s exactly on a card over 24 GiB).

In process: a Runner made without its start-up and stub engines (the pattern of tests/test_memory_api.py and
tests/test_admission_card_factor.py). Sizes and a synthetic picture only."""
import importlib.util
import json
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import mock

from engine import controls, graph_banded
from service import card_factor, fake_comfy, memory_policy
from service.comfy import ComfyError
from service.runner import Cancelled, ItemFailure, Runner

FIX = Path(__file__).parent / 'fixtures'
CARD32 = {'index': 0, 'uuid': 'GPU-5090', 'name': 'NVIDIA GeForce RTX 5090', 'mem_total_gb': 31.84, 'mem_free_gb': 30.0}
CARD24 = {'index': 0, 'uuid': 'GPU-4090', 'name': 'NVIDIA GeForce RTX 4090', 'mem_total_gb': 23.99, 'mem_free_gb': 22.0}
CARD12 = {'index': 0, 'uuid': 'GPU-4070', 'name': 'NVIDIA GeForce RTX 4070', 'mem_total_gb': 11.99, 'mem_free_gb': 11.0}


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Engine:
    """A stub engine on one card. Its prompt writes the timing record spot writes under CLAUDE_SPOT_TIMING, at
    `per_window` seconds per window (or none); its history says the prompt finished."""

    def __init__(self, root, card, per_window=0.6, fail=None):
        self.gpu = card['index']
        self.input_dir, self.output_dir = Path(root) / 'input', Path(root) / 'output'
        self.input_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.client_id = 'c'
        self.prompts = []
        self.per_window, self.fail = per_window, fail
        self.memory_profile = memory_policy.choose_profile(card['mem_total_gb'], 'auto')
        self.state, self.starts = 'ready', 0
        self.client = SimpleNamespace(prompt=self._prompt, history=self._history, interrupt=mock.Mock(),
                                      delete_queued=mock.Mock())

    def alive(self):
        return self.state == 'ready'

    def ensure_started(self, lookup=None, abort=None):
        self.starts += 1
        self.state = 'ready'

    def _prompt(self, graph, client_id, prompt_id=None):
        if self.fail == 'reject':
            raise ComfyError('refused (test)')
        fake_comfy.validate(graph, self.input_dir)                # the graph is one the engine accepts
        self.prompts.append(graph)
        if self.fail == 'crash':
            self.state = 'stopped'
        if self.per_window is not None:
            spot = next(k for k, v in graph.items() if v['class_type'] == 'ClaudeSpotTiles')
            calls, t = [], 0.0
            for step in range(card_factor.CAL_STEPS):
                d = 4 * self.per_window * (3.0 if step == 0 else 1.0)
                calls.append(['main', step, 4, round(t, 5), round(t + d, 5)])
                t += d
            d = self.output_dir / card_factor.TIMING_DIR
            d.mkdir(exist_ok=True)
            (d / f'merged-sp0-b2_{prompt_id}_pass1_node{spot}.json').write_text(json.dumps({'calls': calls}), 'utf8')
        return prompt_id

    def _history(self, pid, timeout=10.0):
        if self.fail == 'hang':
            return None
        return {'status': {'completed': True, 'status_str': 'success'}}


def runner(card, td):
    r = object.__new__(Runner)
    r.mode = 'fake'
    r.accepting = True
    r.deadline_override = None
    r.stall_s = 600.0
    r.settings = SimpleNamespace(get=lambda: {'gpus': [card['index']], 'memory_profile': 'auto', 'ram_cap_gb': 59.0})
    r.gpu_list = lambda max_age=None: ([dict(card)], None)
    r.card_factors = card_factor.CardFactors(Path(td) / 'card_factors.json')
    r.log = mock.Mock()
    r.store = SimpleNamespace(update_item=mock.Mock())
    r._active_update = mock.Mock()
    r._gpu_lookup = lambda: {}
    r._lock = threading.RLock()
    return r


def ctx_for(w, cf=1.0):
    return SimpleNamespace(jid='j1', iid='i001', worker=w, cancel=threading.Event(), shutdown=False, card_factor=cf,
                           factor=1.0, stage_factors=None)


class TheMeasurementPrompt(unittest.TestCase):
    def test_it_is_a_classic_sampler_stack_on_a_synthetic_canvas_of_several_windows(self):
        params = controls.stage_params(controls.resolve({'protect': []})[0], 0)
        for card in (CARD24, CARD12):
            profile = memory_policy.choose_profile(card['mem_total_gb'], 'auto')
            graph, info = card_factor.calibration_graph('cu_cardtime_x.png', 'cu_cardtime_x', params, profile)
            classes = {nd['class_type'] for nd in graph.values()}
            self.assertFalse(classes & set(graph_banded.NODE_SPECS))           # no Large-image class
            self.assertLessEqual(classes, set(fake_comfy.NODE_SPECS))           # classes the engine knows
            spot = next(nd for nd in graph.values() if nd['class_type'] == 'ClaudeSpotTiles')
            from engine import graph_v5t
            want = dict({'clamp_blend': True}, **graph_v5t.product_options(speed_stack=True))
            want = memory_policy.apply_graph({'1': {'class_type': 'ClaudeSpotTiles', 'inputs': dict(want)}},
                                             {'spot_options': want}, profile)[1]['spot_options']
            self.assertEqual({k: spot['inputs'][k] for k in want}, want)        # the product's stack at this card's profile
            ks = next(nd for nd in graph.values() if nd['class_type'] == 'KSampler')
            self.assertGreaterEqual(ks['inputs']['steps'], 3)                   # step 0 is left out of the timing
        w, h = card_factor.CAL_SIZE
        self.assertTrue(w > params['tile_px'] and h > params['tile_px'])        # never spot's one-window path
        a = card_factor.calibration_picture()
        self.assertEqual(a.size, card_factor.CAL_SIZE)
        self.assertEqual(a.tobytes(), card_factor.calibration_picture().tobytes())   # the same picture every time

    def test_only_a_new_single_card_of_24_gib_or_less_needs_measuring(self):
        with TemporaryDirectory() as td:
            store = card_factor.CardFactors(Path(td) / 'cf.json')
            self.assertFalse(card_factor.needs_measuring(store, [CARD32]))
            self.assertTrue(card_factor.needs_measuring(store, [CARD24]))
            self.assertFalse(card_factor.needs_measuring(store, [CARD24, dict(CARD24, index=1, uuid='GPU-2')]))
            self.assertFalse(card_factor.needs_measuring(None, [CARD24]))
            store.record(CARD24, 0.3)
            self.assertFalse(card_factor.needs_measuring(store, [CARD24]))


class AtEngineStart(unittest.TestCase):
    def test_a_new_small_card_is_measured_before_its_first_image_and_runs_at_its_factor(self):
        with TemporaryDirectory() as td:
            r = runner(CARD12, td)
            w = Engine(td, CARD12, per_window=0.6)
            before = r.card_factor_of(w)
            self.assertEqual(before, card_factor.class_factor(CARD12))          # the class table x 2 until measured
            ctx = ctx_for(w, cf=before)
            run = r._with_card_factor({'factor': 1.0, 'stage_factors': [1.0, 0.8]}, before)
            ctx.factor, ctx.stage_factors = run['factor'], list(run['stage_factors'])
            self.assertTrue(r._measure_card(w, ctx))
            self.assertEqual(len(w.prompts), 1)
            measured = r.card_factors.factor(CARD12)
            self.assertAlmostEqual(measured, round(0.6 / card_factor.REF_S_PER_WINDOW, 3))
            self.assertNotEqual(measured, before)
            new = r._run_at_card_factor('j1', 'i001', run, ctx)
            self.assertEqual(ctx.card_factor, measured)
            self.assertAlmostEqual(new['factor'], round(1.0 * measured, 3))
            self.assertEqual(new['card_factor'], measured)
            self.assertEqual(ctx.stage_factors, new['stage_factors'])
            r.store.update_item.assert_called_with('j1', 'i001', run=new)
            st = {'minutes': 20.0}
            self.assertEqual(r._deadline_s(ctx, st), (3 * 20.0 * measured + 10) * 60)   # its own deadline from the start
            self.assertEqual(sorted(p.name for p in w.input_dir.iterdir()), [])          # the synthetic picture is gone
            self.assertFalse(any((w.output_dir / card_factor.TIMING_DIR).iterdir()))     # and the record was read
            self.assertTrue(json.loads((Path(td) / 'card_factors.json').read_text('utf8'))['cards'])   # kept per card

    def test_a_measured_card_is_not_measured_again(self):
        with TemporaryDirectory() as td:
            r = runner(CARD12, td)
            r.card_factors.record(CARD12, 0.4)
            w = Engine(td, CARD12)
            self.assertFalse(r._measure_card(w, ctx_for(w)))
            self.assertEqual(w.prompts, [])

    def test_a_32_gb_card_sends_no_extra_prompt_and_keeps_501s_deadlines_on_the_whole_g0a_grid(self):
        g0 = load('g0_identity_for_a4', FIX / 'g0_identity.py')
        p501 = load('planner_501_for_a4', FIX / 'planner_5_0_1.py')
        with TemporaryDirectory() as td:
            r = runner(CARD32, td)
            w = Engine(td, CARD32)
            ctx = ctx_for(w, cf=r.card_factor_of(w))
            self.assertFalse(r._measure_card(w, ctx))
            self.assertEqual(w.prompts, [])
            r._active_update.assert_not_called()
            run = {'factor': 0.523, 'stage_factors': [0.5, 0.6]}
            self.assertIs(r._run_at_card_factor('j1', 'i001', run, ctx), run)
            self.assertEqual(ctx.card_factor, 1.0)
            n = 0
            for (w0, h0, f, cap), _ in g0.accepted_plans(p501):
                for st in p501.plan(w0, h0, f, ram_cap_gb=cap).to_dict()['stages']:
                    self.assertEqual(r._deadline_s(ctx, st), (3 * st['minutes'] + 10) * 60)   # 5.0.1's, to the second
                    n += 1
            self.assertGreater(n, 300)

    def test_a_failed_measurement_never_fails_the_image(self):
        for fail in ('reject', 'crash', None):
            with TemporaryDirectory() as td:
                r = runner(CARD12, td)
                w = Engine(td, CARD12, per_window=None if fail is None else 0.6, fail=fail)
                self.assertFalse(r._measure_card(w, ctx_for(w)), fail)
                self.assertEqual(r.card_factors.factor(CARD12), card_factor.class_factor(CARD12))
                self.assertTrue(w.alive(), fail)                           # an engine that closed is started again
                if fail is not None:
                    self.assertTrue(any(c.args[0] == 'card_timing_failed' for c in r.log.warn.call_args_list), fail)

    def test_a_measurement_that_takes_too_long_is_stopped_and_the_image_goes_on(self):
        with TemporaryDirectory() as td:
            r = runner(CARD12, td)
            w = Engine(td, CARD12, fail='hang')
            with mock.patch.object(card_factor, 'calibration_limit_s', return_value=0.3):
                self.assertFalse(r._measure_card(w, ctx_for(w)))
            w.client.interrupt.assert_called()

    def test_cancelling_the_image_during_the_measurement_cancels_it(self):
        with TemporaryDirectory() as td:
            r = runner(CARD12, td)
            w = Engine(td, CARD12, fail='hang')
            ctx = ctx_for(w)
            ctx.cancel.set()
            with self.assertRaises(Cancelled):
                r._measure_card(w, ctx)
            w.client.interrupt.assert_called()

    def test_the_image_thread_measures_after_the_engine_started_and_before_its_first_prompt(self):
        with TemporaryDirectory() as td:
            r = runner(CARD12, td)
            w = Engine(td, CARD12, per_window=0.6)
            w.busy = True
            work = Path(td) / 'work' / 'j1' / 'i001'
            work.mkdir(parents=True)
            (work / 'input.png').write_bytes(b'')
            plan = {'stages': [{'index': 0, 'minutes': 10.0}], 'minutes': 10.0}
            it = {'id': 'i001', 'name': 'x', 'plan': plan, 'stage_index': 0, 'settings': {}, 'timings': {},
                  'run': r._with_card_factor({'factor': 1.0, 'frozen': True, 'mode': 'standard'},
                                             card_factor.class_factor(CARD12))}       # as it was frozen at dispatch
            job = {'id': 'j1', 'settings': {}, 'items': [it]}
            r.cfg = SimpleNamespace(work_dir=Path(td) / 'work')
            r.store = SimpleNamespace(get=lambda jid: job, item=lambda j, i: it, update_item=mock.Mock())
            r._vram_refusal = lambda *a, **k: None
            r._drop_kept = lambda *a: None
            seen = []

            class Stop(Exception):
                pass

            def first_stage(w_, ctx, job_, params, k, n):
                seen.append((len(w.prompts), ctx.card_factor, ctx.factor))
                raise Stop()
            r._run_stage = first_stage
            ctx = ctx_for(w)
            with self.assertRaises(Stop):
                r._run_item(w, ctx)
            measured = r.card_factors.factor(CARD12)
            self.assertEqual(seen, [(1, measured, round(measured, 3))])        # timed, then the image at its factor


class TheMaskPreviewLimit(unittest.TestCase):
    def test_600_s_on_a_card_over_24_gib_and_x_cf_on_a_small_one(self):
        with TemporaryDirectory() as td:
            r = runner(CARD32, td)
            self.assertEqual(r._mask_preview_limit_s(Engine(td, CARD32)), 600.0)
            r = runner(CARD12, td)
            w = Engine(td, CARD12)
            self.assertEqual(r._mask_preview_limit_s(w), 600.0 * card_factor.class_factor(CARD12))
            r.card_factors.record(CARD12, 0.735)
            self.assertAlmostEqual(r._mask_preview_limit_s(w), 600.0 * r.card_factors.factor(CARD12))

    def test_the_preview_waits_that_long(self):
        from PIL import Image
        with TemporaryDirectory() as td:
            r = runner(CARD12, td)
            w = Engine(td, CARD12, per_window=None)
            w.busy = True
            src = Path(td) / 'source.png'
            Image.new('RGB', (64, 48)).save(src)
            out = Path(td) / 'mask.png'
            Image.new('L', (64, 48), 128).save(out)
            r._claim_worker_wait = lambda: w
            r._preflight = lambda w_, refresh=True: None
            r.media = SimpleNamespace(path=lambda mid, name: src)
            r._output_file = lambda w_, h: out
            r._cleanup_worker_files = mock.Mock()
            r.wake = mock.Mock()
            got = {}

            def wait(w_, pid, timeout):
                got['timeout'] = timeout
                return {}
            r._wait_simple = wait
            params, _ = controls.resolve({})
            r._mask_preview_run('m1', 'k', params['protect_terms'], params, Path(td) / 'saved.png')
            self.assertEqual(got['timeout'], 600.0 * card_factor.class_factor(CARD12))


if __name__ == '__main__':
    unittest.main()
