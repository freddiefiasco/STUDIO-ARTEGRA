"""5.0.2's fix of the SAM slowdown and the time model found in 5.0.1 (Max, 20 Nov 2026: "Fold into 5.0.2").

1. SAM fits the card. 5.0.1's SAM3_Detect upsamples all 200 query masks to the full pass input on the card (about 0.37 GiB per
   input MP), so a protect-on pass with a large input spills into shared GPU memory (a 66 MP pass input spilled 9.3 GiB on a
   32 GB card). A stage whose padded input is above planner.SAM_STOCK_MAX_MP takes ClaudeSAM3DetectLean instead: the same
   node inputs and the same node ids, the detector's masks kept at its own resolution and only the kept mask upsampled. Its
   masks are 5.0.1's (tests/worker/test_sam_lean.py runs it against ComfyUI's own SAM3_Detect code). Every other stage keeps
   5.0.1's graph byte for byte.
2. Honest times. 5.0.1's stage minutes (5.5 + 0.27 x render MP) had no input or output term: a 6x protect-on job planned
   80.5 min (Standard) and took 114.6. 5.0.2's minutes are the smallest upper envelope of the measured stage times
   (tests/fixtures/stage_times_5_0_1.json), never below 5.0.1's for any stage. Times only: no graph changes with them.

Sizes only; no image is read."""
import importlib.util
import json
import unittest
from pathlib import Path
from unittest import mock

from engine import controls, graph_v5t, planner
from service import engine_options, mask_graph, workers

ROOT = Path(__file__).resolve().parents[1]
FIX = Path(__file__).parent / 'fixtures'
TIMES = json.loads((FIX / 'stage_times_5_0_1.json').read_text(encoding='utf8'))
_SPEC = importlib.util.spec_from_file_location('p501_sam_times', FIX / 'planner_5_0_1.py')
P501 = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(P501)
LEAN = 'ClaudeSAM3DetectLean'
SIZES = [(w, h) for w in (512, 777, 1000, 1280, 1520, 1600, 2048, 2188, 2350, 2800, 3000, 3500, 3840, 4096, 5000, 6000)
         for h in (512, 777, 1080, 1600, 1762, 2188, 2400, 2800, 3500, 4000)]
CAPS = (None, 45.2, 59.0, 122.2)


def mp(s):
    return s[0] * s[1] / 1e6


def without_minutes(d):
    d = dict(d, stages=[{k: v for k, v in s.items() if k != 'minutes'} for s in d['stages']])
    d.pop('minutes', None)
    return d


class TheSamCeiling(unittest.TestCase):
    def test_the_ceiling_is_a_planner_constant_with_its_registered_source(self):
        self.assertEqual(planner.SAM_STOCK_MAX_MP, 18.0)
        src = planner.SAM_STOCK_MAX_SOURCE
        for part in ('9e0e33826f354851aa42e2132ca359cd', '21.0', 'floor(0.9', 'eng:prove'):
            self.assertIn(part, src)

    def test_lean_only_above_the_ceiling(self):
        self.assertFalse(planner.sam_lean(4242, 4243))          # 17.999 MP
        self.assertFalse(planner.sam_lean(4500, 4000))          # 18.000 MP exactly: not above
        self.assertTrue(planner.sam_lean(4243, 4243))           # 18.003 MP
        self.assertTrue(planner.sam_lean(9408, 7056))           # S0b's pass-3 input, 66.4 MP


def stage_graph(pw, ph, f=2, s=1, protect=None, **kw):
    p, _ = controls.resolve({} if protect is None else {'protect': protect})
    return graph_v5t.build_product('x.png', pw, ph, p, 'x', f=f, s=s, **kw)[0]


def classes(g):
    return sorted(n['class_type'] for n in g.values())


class TheLeanNodeInTheStageGraph(unittest.TestCase):
    def test_above_the_ceiling_only_the_sam_class_changes(self):
        for (pw, ph, f, s) in ((5120, 4000, 2, 1.5), (9408, 7056, 1.5, 1), (7000, 4376, 2, 1), (4248, 4248, 2, 1)):
            for protect in (None, list(controls.PROTECT_ORDER)):
                lean = stage_graph(pw, ph, f, s, protect, live_preview='rough')
                with mock.patch.object(planner, 'SAM_STOCK_MAX_MP', float('inf')):
                    stock = stage_graph(pw, ph, f, s, protect, live_preview='rough')
                self.assertEqual(sorted(lean), sorted(stock))
                n_sam = 0
                for nid, node in stock.items():
                    if node['class_type'] == 'SAM3_Detect':
                        n_sam += 1
                        self.assertEqual(lean[nid], dict(node, class_type=LEAN), (pw, ph, nid))
                    else:
                        self.assertEqual(lean[nid], node, (pw, ph, nid))
                self.assertGreater(n_sam, 0)
                self.assertNotIn('SAM3_Detect', classes(lean))

    def test_at_or_below_the_ceiling_the_graph_is_501s(self):
        for (pw, ph, f, s) in ((4500, 4000, 2, 1), (4240, 4240, 2, 1), (4704, 3528, 2, 1.5), (2350, 1762, 2, 2)):
            g = stage_graph(pw, ph, f, s, list(controls.PROTECT_ORDER))
            self.assertNotIn(LEAN, classes(g))
            self.assertIn('SAM3_Detect', classes(g))

    def test_protect_off_has_no_sam_at_any_size(self):
        g = stage_graph(9408, 7056, 1.5, 1, [])
        self.assertNotIn(LEAN, classes(g))
        self.assertNotIn('SAM3_Detect', classes(g))

    def test_the_chain_builder_follows_the_same_rule(self):
        p, _ = controls.resolve({})
        for (w, h, second) in ((2400, 2000, LEAN), (2350, 1762, 'SAM3_Detect')):      # second input 19.2 MP / 16.6 MP
            g, _ = graph_v5t.build_chain('x.png', [(w, h, 2, 2, p, 'a'), (2 * w, 2 * h, 2, 1, controls.stage_params(p, 1), 'b')])
            loads = {nid for nid, n in g.items() if n['class_type'] == 'LoadImage'}
            sams = [n for n in g.values() if n['class_type'] in ('SAM3_Detect', LEAN)]
            self.assertEqual(len(loads), 1)
            self.assertEqual({n['class_type'] for n in sams if n['inputs']['image'][0] in loads}, {'SAM3_Detect'})
            self.assertEqual({n['class_type'] for n in sams if n['inputs']['image'][0] not in loads}, {second})

    def test_the_protected_area_preview_takes_the_rule_of_its_source(self):
        p, _ = controls.resolve({'protect': ['architecture']})
        stock = mask_graph.build('x.png', p['protect_terms'], p['protect'], 'm', release_terms=['tree'])
        self.assertEqual(stock, graph_v5t.build_gate_preview('x.png', p['protect_terms'], ['tree'], p['protect'], 'm'))
        for size in ((4242, 4243), (4500, 4000), (800, 600)):
            self.assertEqual(mask_graph.build('x.png', p['protect_terms'], p['protect'], 'm', release_terms=['tree'], size=size),
                             stock, size)
        lean = mask_graph.build('x.png', p['protect_terms'], p['protect'], 'm', release_terms=['tree'], size=(4243, 4243))
        self.assertEqual(sorted(stock), sorted(lean))
        for nid, node in stock.items():
            self.assertEqual(lean[nid], dict(node, class_type=LEAN) if node['class_type'] == 'SAM3_Detect' else node)
        self.assertIn(LEAN, mask_graph.SAM_CLASSES)
        self.assertEqual(graph_v5t.build_mask_preview('x.png', [('a', ['wall'])], p['protect'], 'm', lean=True),
                         {k: (dict(v, class_type=LEAN) if v['class_type'] == 'SAM3_Detect' else v)
                          for k, v in graph_v5t.build_mask_preview('x.png', [('a', ['wall'])], p['protect'], 'm').items()})

    def test_the_engine_check_asks_for_the_lean_node_and_its_inputs(self):
        self.assertIn(LEAN, workers.required_classes())
        self.assertEqual(workers.required_inputs()[LEAN],
                         sorted(['model', 'image', 'conditioning', 'threshold', 'refine_iterations', 'individual_masks']))

    def test_the_fake_engine_validates_the_lean_node(self):
        from service import fake_comfy
        import tempfile
        from PIL import Image
        self.assertEqual(fake_comfy.NODE_SPECS[LEAN], fake_comfy.NODE_SPECS['SAM3_Detect'])
        with tempfile.TemporaryDirectory() as td:
            Image.new('RGB', (4248, 4248)).save(Path(td) / 'x.png')
            g = stage_graph(4248, 4248, 2, 1, list(controls.PROTECT_ORDER))
            order, sizes, saves = fake_comfy.validate(g, td)
            lean = [nid for nid, n in g.items() if n['class_type'] == LEAN]
            self.assertTrue(lean)
            for nid in lean:
                self.assertEqual(sizes[nid], (4248, 4248))


class HonestTimes(unittest.TestCase):
    def stage_minutes(self, st):
        return round(planner.stage_minutes_502(mp(st['render']), mp(st['padded']), mp(st['output'])), 1)

    def test_every_measured_stage_takes_at_most_the_time_said(self):
        n = 0
        for st in TIMES['stages']:
            said = TIMES['factor'][st['mode']] * 60 * self.stage_minutes(st)
            self.assertGreaterEqual(said, st['seconds'], st)
            n += 1
        self.assertEqual(n, 19)

    def test_every_measured_job_takes_at_most_the_time_said(self):
        jobs = {}
        for st in TIMES['stages']:
            jobs.setdefault(st['job'], []).append(st)
        for k, sts in jobs.items():
            said = TIMES['factor'][sts[0]['mode']] * 60 * round(sum(self.stage_minutes(s) for s in sts), 1)
            self.assertGreaterEqual(said, sum(s['seconds'] for s in sts), k)

    def test_the_6x_job_that_took_114_6_min(self):
        p = planner.plan(2350, 1762, 6, ram_cap_gb=122.2)
        self.assertTrue(p.ok)
        self.assertEqual(round(P501.plan(2350, 1762, 6, ram_cap_gb=122.2).minutes * 0.70, 1), 80.5)   # what 5.0.1 said
        self.assertGreaterEqual(p.minutes * engine_options.ETA_STACK, 114.6)

    def test_never_below_501_and_the_plan_otherwise_501s(self):
        n = 0
        for w, h in SIZES:
            for f in controls.SCALES:
                for cap in CAPS:
                    old = P501.plan(w, h, f, ram_cap_gb=cap)
                    if not old.ok:
                        continue
                    new = planner.plan(w, h, f, ram_cap_gb=cap)
                    if new.engine != 'classic':
                        continue
                    n += 1
                    self.assertEqual(without_minutes(new.to_dict()), without_minutes(old.to_dict()), (w, h, f, cap))
                    for a, b in zip(new.stages, old.stages):
                        want = round(planner.stage_minutes_502(mp(a.render_size), mp(a.padded_size), mp(a.output_size)), 1)
                        self.assertEqual(a.minutes, want)
                        self.assertGreaterEqual(a.minutes, b.minutes, (w, h, f, cap, a.index))
                    self.assertEqual(new.minutes, round(sum(s.minutes for s in new.stages), 1))
                    self.assertGreaterEqual(new.minutes, old.minutes)
        self.assertGreater(n, 500)

    def test_a_full_supersample_2x_stage_keeps_a_slope_of_at_least_501s(self):
        slope = planner.TIME_PER_RENDER_MP + planner.TIME_PER_INPUT_MP / 16 + planner.TIME_PER_OUTPUT_MP / 4
        self.assertGreaterEqual(slope, 0.27)
        self.assertEqual(planner.TIME_BASE_MINUTES, 5.5)

    def test_refusals_are_501s(self):
        for args in ((4000, 3000, 8), (40, 400, 2), (1000, 1000, 3), (9000, 9000, 2)):
            self.assertEqual(planner.plan(*args).to_dict(), P501.plan(*args).to_dict())

    def test_the_minutes_change_no_graph(self):
        from service.util import same_plan
        for w, h, f in ((2350, 1762, 6), (3500, 2188, 4), (2048, 2048, 2)):
            self.assertTrue(same_plan(planner.plan(w, h, f).to_dict(), P501.plan(w, h, f).to_dict()))


class TheTwoCardTimeSplitsOnlyTheSampling(unittest.TestCase):
    """On two cards only the sampling is shared, so the two-card saving applies to 5.0.1's share of the minutes and never to
    5.0.2's input and output terms (the x4 model, the hints, the finish and the save run on one card)."""

    def test_the_io_share(self):
        p = planner.plan(2350, 1762, 6, ram_cap_gb=122.2)
        share = engine_options.plan_io_share(p.to_dict())
        io = sum(planner.stage_io_minutes(s.render_mp, mp(s.padded_size), mp(s.output_size)) for s in p.stages)
        self.assertAlmostEqual(share, io / p.minutes, delta=0.002)
        self.assertGreater(share, 0.2)
        self.assertEqual(engine_options.plan_io_share(None), 0.0)
        self.assertAlmostEqual(engine_options.plan_io_share(planner.plan(2048, 2048, 2).to_dict()), 0.0, places=9)   # 2x, s 2
        stored_501 = P501.plan(2350, 1762, 6, ram_cap_gb=122.2).to_dict()
        self.assertLess(engine_options.plan_io_share(stored_501), 0.005)
        self.assertEqual(planner.stage_io_minutes(122.5, 122.5 / 16, 122.5 / 4), 0.0)

    def test_the_factor(self):
        self.assertEqual(engine_options.eta_factor(True, 2), 0.523)                        # without a plan: 5.0.1's
        self.assertEqual(engine_options.eta_factor(True, 2, io_share=0.0), 0.523)
        f = engine_options.eta_factor(True, 2, io_share=0.4)
        self.assertAlmostEqual(f, round(0.70 - (0.70 - 0.523) * 0.6, 3), delta=0.0015)
        self.assertEqual(engine_options.eta_factor(True, 1, io_share=0.4), 0.70)          # one card: unchanged

    def test_finish_info_uses_the_plan(self):
        p = planner.plan(2350, 1762, 6, ram_cap_gb=122.2)
        fi = engine_options.finish_info(p.minutes, plan=p.to_dict(), cards={'standard': 2})
        share = engine_options.plan_io_share(p.to_dict())
        self.assertEqual(fi['single']['standard']['factor'], engine_options.eta_factor(True, 2, io_share=share))
        self.assertGreater(fi['single']['standard']['factor'], 0.523)
        self.assertEqual(fi['standard']['factor'], 0.7)


if __name__ == '__main__':
    unittest.main()
