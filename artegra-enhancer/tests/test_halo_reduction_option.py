"""Halo Reduction (beta), the per-job option (HANDOVER-ENGINE-CORE.md 13a): a job setting 'halo_reduction' (true / false,
absent = off) carried from the service API to the Large-image finish's node, never a process-wide switch. With the option off
or absent every record, plan, graph and finish is what it was before the option existed; on, a Large-image plan's LAST pass
runs round 2's clamp (node_pack/claude_banded/bxf/dehalo.py; its pixels are tests/worker/test_halo_reduction.py's), its
memory, disk and minutes are counted, and the plan constant halo_fix names it. A Classic engine image keeps 5.0.1's finish in
5.0.2 (the option's port to the Classic engine is v6's) and says so; tier 3 (the whole finish) cannot run the clamp, so a
plan that would need it is refused before it starts. 5.0.2's app shows no new control. Sizes and synthetic images only."""
import ast
import json
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from engine import banded_plan as B
from engine import controls, graph_banded, planner
from engine.bxf import memory as M

ROOT = Path(__file__).resolve().parents[1]
PROVEN = {k: 10_000.0 for k in B.BANDED_PROVEN_MP}
CAPS = {'pc64': 59.0, 'ws128': 122.2, 'pc48': 45.2}


def bxf(on=True):
    return mock.patch.object(B, 'BXF_AVAILABLE', on)


def proven():
    return mock.patch.dict(B.BANDED_PROVEN_MP, PROVEN)


class TheSetting(unittest.TestCase):
    def test_off_or_absent_changes_nothing_on_records(self):
        for req in ({}, {'preset': 'Default', 'scale': 4}, {'protect': ['architecture'], 'scale': 8}):
            base = controls.resolve(dict(req))
            off = controls.resolve(dict(req, halo_reduction=False))
            self.assertEqual(json.dumps(base, sort_keys=True), json.dumps(off, sort_keys=True))
            self.assertNotIn('halo_reduction', json.dumps(base))

    def test_on_is_a_job_setting_in_the_params_and_the_effective_record(self):
        params, eff = controls.resolve({'halo_reduction': True, 'scale': 4})
        self.assertIs(params['halo_reduction'], True)
        self.assertIs(eff['halo_reduction'], True)
        self.assertIs(eff['engine']['halo_reduction'], True)

    def test_a_value_that_is_not_true_or_false_is_refused_in_plain_words(self):
        for v in (1, 0, 'on', 'true', None, [], {}):
            with self.assertRaises(controls.ControlError) as cm:
                controls.resolve({'halo_reduction': v})
            self.assertIn('Halo Reduction', str(cm.exception))

    def test_the_app_shows_no_new_control_and_no_process_wide_switch_is_read(self):
        self.assertNotIn('halo', json.dumps(controls.describe()).lower())
        for top in ('ui', 'engine', 'service', 'node_pack'):
            for p in (ROOT / top).rglob('*'):
                if p.is_file() and p.suffix in ('.py', '.qml', '.js', '.html') and '__pycache__' not in p.parts:
                    text = p.read_text(encoding='utf8', errors='replace')
                    self.assertNotIn('CU_HALO_FIX', text, p)
                    if top == 'ui':
                        self.assertNotIn('Halo Reduction', text, p)


def planned(w, h, f, mclass, halo, tier=True):
    with bxf(tier), proven():
        return planner.plan(w, h, f, ram_cap_gb=CAPS[mclass], **({'halo_reduction': True} if halo else {}))


class ThePlan(unittest.TestCase):
    def test_off_is_the_plan_made_before_the_option_and_a_classic_plan_never_changes(self):
        for args in ((3500, 2188, 4, 'pc64'), (2800, 3500, 4, 'ws128'), (1024, 768, 2, 'pc64'), (1024, 768, 4, 'pc64')):
            base = planned(*args, halo=False)
            with bxf(), proven():
                off = planner.plan(*args[:3], ram_cap_gb=CAPS[args[3]], halo_reduction=False)
            self.assertEqual(base.to_dict(), off.to_dict(), args)
            self.assertNotIn('dehalo_f', json.dumps(base.to_dict()))
            if base.engine == 'classic':
                self.assertEqual(planned(*args, halo=True).to_dict(), base.to_dict(), args)

    def test_on_a_large_image_plan_counts_the_clamp_on_its_last_pass_only(self):
        for w, h, f, mc in ((3500, 2188, 4, 'pc64'), (2800, 3500, 4, 'ws128'), (3500, 2188, 8, 'ws128'),
                            (3500, 2188, 6, 'ws128'), (6000, 4000, 2, 'ws128')):
            off, on = planned(w, h, f, mc, False), planned(w, h, f, mc, True)
            if not off.ok or off.engine != 'banded':
                continue
            with self.subTest(size=(w, h, f, mc)):
                self.assertEqual(off.banded['halo_fix'], None)
                self.assertEqual(on.banded['halo_fix'], 'edge3f')
                d_off, d_on = off.to_dict(), on.to_dict()
                for a, b in zip(d_off['stages'][:-1], d_on['stages'][:-1]):
                    self.assertEqual(a, b)                                  # every earlier pass is 5.0.1's (no clamp)
                last = on.stages[-1]
                want_f = float(last.factor) * last.input_size[0] / w
                self.assertEqual(last.dehalo_f, want_f)
                self.assertEqual(d_on['stages'][-1]['dehalo_f'], want_f)
                self.assertGreater(last.minutes, off.stages[-1].minutes)
                self.assertGreaterEqual(last.disk_gb, off.stages[-1].disk_gb)
                self.assertGreaterEqual(last.peak_upper_gb, off.stages[-1].peak_upper_gb)
                self.assertGreaterEqual(on.peak_ram_gb, off.peak_ram_gb)

    def test_the_last_pass_bound_holds_the_clamps_band(self):
        """A stage alone gives its own figures (stage_peaks reads the stored stage): with dehalo_f the finish phase counts
        the clamp's band where it is larger than the band budget."""
        with bxf(), proven():
            p = planner.plan(3500, 2188, 8, ram_cap_gb=CAPS['ws128'], halo_reduction=True)
        self.assertTrue(p.ok, p.reason)
        st = p.to_dict()['stages'][-1]
        mc = B.MACHINE_CLASSES['ws128']
        band = M.dehalo_band_gb(B.finish_size(st), mc['band_gb'], st['dehalo_f'])
        self.assertGreater(band, mc['band_gb'])                              # 28,000 px wide at f 8: over the 6 GiB budget
        a = B.stage_peaks(st, 'ws128', st['split_finish'])['phases_up']['finish']
        b = B.stage_peaks(dict(st, dehalo_f=None), 'ws128', st['split_finish'])['phases_up']['finish']
        self.assertAlmostEqual(a - b, band - mc['band_gb'], places=6)

    def test_tier_3_cannot_run_the_clamp_so_the_plan_is_refused_before_it_starts(self):
        off = planned(3500, 2188, 4, 'ws128', False, tier=False)
        on = planned(3500, 2188, 4, 'ws128', True, tier=False)
        if off.ok and off.engine == 'banded':
            self.assertFalse(on.ok)
            self.assertEqual(on.engine, 'banded')
            self.assertIn('Halo Reduction', on.reason)
            self.assertIn('Turn it off', on.reason)


class TheMemoryModel(unittest.TestCase):
    def test_the_reach_is_the_clamps(self):
        self.assertEqual([M.dehalo_reach(f) for f in (1.5, 2, 4, 6, 8)], [138, 174, 334, 494, 654])
        src = (ROOT / 'node_pack' / 'claude_banded' / 'bxf' / 'dehalo.py').read_text(encoding='utf8')
        self.assertIn('def edge_profile_clamp_reach(f, p=None):', src)

    def test_off_bounds_are_unchanged_and_on_takes_the_larger_band(self):
        for size, band in (((28000, 17504), 6.0), ((11200, 14000), 3.0), ((7000, 4376), 2.0)):
            base = M.finish_commit_gb(size, (size[0] // 2, size[1] // 2), band, 1, 'bxf')
            self.assertEqual(M.finish_commit_gb(size, (size[0] // 2, size[1] // 2), band, 1, 'bxf', dehalo_f=None), base)
            for f in (2.0, 4.0, 8.0):
                on = M.finish_commit_gb(size, (size[0] // 2, size[1] // 2), band, 1, 'bxf', dehalo_f=f)
                self.assertAlmostEqual(on - base, max(0.0, M.dehalo_band_gb(size, band, f) - M.band_peak_gb(size, band)),
                                       places=9)

    def test_the_band_rows_and_reads(self):
        h = M.dehalo_band_height(11200, 3.0, 4.0)
        self.assertEqual(h, 576)                                       # (576 + 2 x 334) x 11,200 x 200 B fits 3 GiB
        self.assertEqual(M.dehalo_band_height(28000, 6.0, 8.0), 288)   # nothing fits: the smallest height
        H, W, R = 14000, 11200, 334
        rows = sum(min(H, y + h + R) - max(0, y - R) for y in range(0, H, h))
        self.assertAlmostEqual(M.dehalo_read_mp((W, H), 3.0, 4.0), rows * W / 1e6)


class TheGraph(unittest.TestCase):
    def build(self, part=None, halo=None, consts=None, k=1):
        params = controls.stage_params(controls.resolve({'scale': 4})[0], k)
        c = B.constants('redux')
        c.update(consts or {})
        kw = {} if halo is None else {'halo': halo}
        return graph_banded.build_stage('w/planes/s1/input.plane', 1400, 880, params, 'cu_j_i_s1', 'w/planes/s1',
                                        'run1', f=2, s=1, constants=c, part=part, **kw)[0]

    def test_off_is_the_graph_made_before_the_option(self):
        for part in (None, 'A', 'B'):
            a = json.dumps(self.build(part), sort_keys=True)
            self.assertEqual(json.dumps(self.build(part, consts={'halo_fix': 'edge3f'}), sort_keys=True), a)  # earlier pass
            self.assertNotIn('dehalo', a)

    def test_the_last_pass_takes_the_option_and_its_anchor(self):
        halo = {'dehalo': 'edge3f', 'anchor': 'w/planes/s1/anchor.plane', 'anchor_factor': 4.0}
        for part in (None, 'B'):
            g = self.build(part, halo=halo, consts={'halo_fix': 'edge3f'})
            fin = next(n for n in g.values() if n['class_type'] == 'CUFinishBanded')['inputs']
            self.assertEqual((fin['dehalo'], fin['anchor_factor']), ('edge3f', 4.0))
            src = g[fin['anchor'][0]]
            self.assertEqual((src['class_type'], src['inputs']['plane']), ('CUPlaneInput', halo['anchor']))
            self.assertEqual(list(fin)[-3:], ['dehalo', 'anchor', 'anchor_factor'])
        first = self.build(None, halo={'dehalo': 'edge3f', 'anchor': None, 'anchor_factor': None},
                           consts={'halo_fix': 'edge3f'}, k=0)
        fin = next(n for n in first.values() if n['class_type'] == 'CUFinishBanded')['inputs']
        self.assertEqual(fin['dehalo'], 'edge3f')
        self.assertNotIn('anchor', fin)
        a = self.build('A', halo=halo, consts={'halo_fix': 'edge3f'})
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(self.build('A'), sort_keys=True))

    def test_a_mismatch_or_another_mode_is_refused(self):
        with self.assertRaises(ValueError):
            self.build(None, halo={'dehalo': 'edge3f', 'anchor': None, 'anchor_factor': None})   # the plan did not count it
        with self.assertRaises(ValueError):
            self.build(None, halo={'dehalo': 'edge2f', 'anchor': None, 'anchor_factor': None}, consts={'halo_fix': 'edge2f'})
        with self.assertRaises(ValueError):
            self.build(None, consts={'halo_fix': 'edge9'})

    def test_the_node_declares_the_options_inputs(self):
        self.assertEqual(graph_banded.NODE_OPTIONAL['CUFinishBanded'][-3:], ('dehalo', 'anchor', 'anchor_factor'))
        src = (ROOT / 'node_pack' / 'claude_banded' / 'bxf' / '__init__.py').read_text(encoding='utf8')
        self.assertIn('"dehalo": (["off", "edge3f"], {"default": "off"})', src)


class TheAnchor(unittest.TestCase):
    def test_the_banded_bilinear_is_pillows_whole_call(self):
        from PIL import Image
        from engine import lanczos_bands as L
        rng = np.random.default_rng(3)
        for (h, w), size in (((301, 263), (526, 602)), ((180, 240), (960, 720)), ((640, 480), (300, 400))):
            a = rng.integers(0, 256, (h, w, 3), dtype=np.uint8)
            want = np.asarray(Image.fromarray(a).resize(size, Image.BILINEAR))
            got = L.resize_array(a, size, row_band=288, col_strip=64, resample=Image.BILINEAR)
            self.assertEqual(int(np.count_nonzero(got != want)), 0, size)
            self.assertEqual(int(np.count_nonzero(L.resize_array(a, size, row_band=288, col_strip=64)
                                                  != np.asarray(Image.fromarray(a).resize(size, Image.LANCZOS)))), 0)

    def test_the_anchor_plane_is_round_2s_anchor(self):
        """service.banded_runner.make_anchor: the original resampled to the pass input (Pillow's bilinear) and reflect-padded
        as the pass input is, in bands: the bytes of round 2's images.halo_anchor (its whole-image calls)."""
        import tempfile
        from PIL import Image
        from engine import planes
        from service import banded_runner, images
        rng = np.random.default_rng(5)
        orig = rng.integers(0, 256, (190, 250, 3), dtype=np.uint8)
        st = {'input_size': [1000, 760], 'padded_size': [1008, 768]}
        want = images.pad_reflect(np.asarray(Image.fromarray(orig).resize((1000, 760), Image.BILINEAR)), (1008, 768))
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            p = banded_runner.make_anchor(orig, st, Path(td) / 'anchor.plane', 'r1')
            got = planes.Plane.open(p).read_rows(0, 768)
            self.assertEqual(got.shape, want.shape)
            self.assertEqual(int(np.count_nonzero(got != want)), 0)
            self.assertFalse([q.name for q in Path(td).iterdir() if q.name != 'anchor.plane'])

    def test_the_stage_gets_the_option_on_its_last_pass_only(self):
        from service import banded_runner
        plan = {'input_size': [3500, 2188], 'banded': {'halo_fix': 'edge3f'},
                'stages': [{'factor': 2.0, 'input_size': [3500, 2188]}, {'factor': 2.0, 'input_size': [7000, 4376]}]}
        self.assertIsNone(banded_runner.halo_of(plan, 0, 2))
        self.assertEqual(banded_runner.halo_of(plan, 1, 2), {'dehalo': 'edge3f', 'anchor_factor': 4.0})
        one = dict(plan, stages=plan['stages'][:1])
        self.assertEqual(banded_runner.halo_of(one, 0, 1), {'dehalo': 'edge3f', 'anchor_factor': None})
        self.assertIsNone(banded_runner.halo_of(dict(plan, banded={'halo_fix': None}), 1, 2))


class ThePhysicalAndDiskTerms(unittest.TestCase):
    def test_the_finish_phase_counts_the_clamps_planes_when_on(self):
        from service import banded_runner as BR
        st = {'padded_size': [7000, 4376], 'render_size': [14000, 8752], 'output_size': [14000, 8752], 'factor': 2.0,
              'binding_phase': 'finish'}
        off = BR.stage_planes_bytes(st, 'finish')
        on = BR.stage_planes_bytes(dict(st, dehalo_f=4.0), 'finish')
        O, I = B.finish_px(st), 7000 * 4376
        self.assertEqual(on - off, M.DEHALO_PLANES_BPO * O + M.DEHALO_PLANES_BPI * I)
        self.assertEqual(BR.stage_planes_bytes(dict(st, dehalo_f=None), 'finish'), off)
        self.assertEqual(BR.stage_planes_bytes(dict(st, dehalo_f=4.0), 'sampling'), BR.stage_planes_bytes(st, 'sampling'))


class TheRunner(unittest.TestCase):
    def test_the_job_settings_reach_the_plan(self):
        src = (ROOT / 'service' / 'runner.py').read_text(encoding='utf8')
        tree = ast.parse(src)
        planned = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == '_planned')
        self.assertIn('halo', [a.arg for a in planned.args.args + planned.args.kwonlyargs])
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, 'attr', None) == '_planned']
        self.assertGreaterEqual(len(calls), 2)
        for c in calls:
            self.assertIn('halo', [k.arg for k in c.keywords], ast.unparse(c))

    def test_a_classic_image_says_its_finish_is_5_0_1s(self):
        from service import runner as R
        classic = planner.plan(1024, 768, 2, ram_cap_gb=59.0)
        self.assertEqual(R.halo_notes(classic, {'halo_reduction': True}), [R.HALO_CLASSIC_NOTE])
        self.assertEqual(R.halo_notes(classic, {}), [])
        self.assertIn('Halo Reduction (beta)', R.HALO_CLASSIC_NOTE)
        self.assertIn('Classic engine', R.HALO_CLASSIC_NOTE)


if __name__ == '__main__':
    unittest.main()
