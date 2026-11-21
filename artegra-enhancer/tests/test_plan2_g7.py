"""Gate G7 on the worker runtime, its verdict, and the memory model re-checked after the flip (engine design 2.7, B1; build
wave 2, the plan package's item 2).

tools/gate_g7.py ran with the worker runtime's interpreter and libraries (torch 2.14.1, torchsde 0.2.6) on a CPU; its verdict
is recorded in tests/fixtures/plan2_g7_runtime.json (sizes, seeds and differing counts only). banded_plan.BROWNIAN_CAPPED
follows it: True (plan constant brownian_cache 8, which graph_banded passes to the fork's existing brownian_cache input) only
when every draw of every variant was identical. The model with the capped cache reproduces the design's capped sizing
(design-2-evidence/plan_final2-output.txt, 'Brownian cache capped at 8') to a tenth, and the upper figures are those of the
uncapped model (the upper X was measured with the cache in it). Sizes only."""
import json
import unittest
from pathlib import Path
from unittest import mock

from engine import banded_plan as B
from engine import controls, graph_banded, planner

ROOT = Path(__file__).resolve().parents[1]
VERDICT = json.loads((ROOT / 'tests' / 'fixtures' / 'plan2_g7_runtime.json').read_text(encoding='utf8'))
CAPS = {'pc64': 59.0, 'ws128': 122.2, 'pc48': 45.2}

# plan_final2-output.txt, "Revised: L1 + L2 + L3r (worker restart), 4 B/Rpx, Brownian cache capped at 8":
# (w, h, factor, machine): (expected GiB, its phase, upper GiB, its phase, split per stage)
SIZING_CAPPED = {
    (3500, 2188, 4, 'pc64'): (36.8, 'finish', 41.2, 'finish', '--'),
    (3500, 2188, 4, 'pc48'): (35.4, 'finish', 39.8, 'finish', '--'),
    (3500, 2188, 6, 'pc64'): (41.6, 'finish', 51.6, 'finish', '---'),
    (3500, 2188, 6, 'ws128'): (36.6, 'P0', 43.5, 'P0', 'sss'),
    (3500, 2188, 6, 'pc48'): (36.6, 'P0', 43.5, 'P0', '--s'),
    (3500, 2188, 8, 'pc64'): (39.6, 'decode', 51.8, 'decode', '--s'),
    (3500, 2188, 8, 'ws128'): (39.6, 'decode', 51.8, 'decode', 'sss'),
    (3500, 2188, 8, 'pc48'): (39.6, 'decode', 51.8, 'decode', '--s'),
    (2800, 3500, 4, 'pc64'): (37.7, 'finish', 43.4, 'finish', '--'),
    (2800, 3500, 4, 'ws128'): (33.6, 'decode', 37.5, 'decode', 'ss'),
    (2800, 3500, 4, 'pc48'): (36.3, 'finish', 42.0, 'finish', '--'),
    (2800, 3500, 6, 'pc64'): (37.7, 'finish', 46.2, 'P0', '--s'),
    (2800, 3500, 6, 'ws128'): (37.3, 'P0', 46.2, 'P0', 'sss'),
    (2800, 3500, 6, 'pc48'): (37.3, 'P0', 46.2, 'P0', '--s'),
    (2800, 3500, 8, 'pc64'): (41.0, 'decode', 56.7, 'decode', '--s'),
    (2800, 3500, 8, 'ws128'): (41.0, 'decode', 59.9, 'finish', 'sss'),
    (2800, 3500, 8, 'pc48'): (41.0, 'decode', 56.7, 'decode', '--s'),
    (4000, 2500, 8, 'pc64'): (42.0, 'decode', 58.0, 'decode', '--s'),
    (4000, 2500, 8, 'ws128'): (42.0, 'decode', 60.7, 'finish', 'sss'),
    (4000, 2500, 8, 'pc48'): (42.0, 'decode', 58.0, 'decode', '-ss'),
    (4000, 4000, 8, 'pc64'): (47.4, 'sampling', 80.0, 'finish', '--s'),
    (4000, 4000, 8, 'ws128'): (47.4, 'sampling', 83.8, 'finish', 'sss'),
    (4000, 4000, 8, 'pc48'): (47.4, 'sampling', 78.6, 'finish', '-ss'),
    (5333, 3333, 6, 'pc64'): (43.3, 'P0', 59.3, 'P0', '--s'),
    (5333, 3333, 6, 'ws128'): (43.3, 'P0', 62.1, 'finish', 'sss'),
    (5333, 3333, 6, 'pc48'): (43.3, 'P0', 59.3, 'P0', '-ss'),
}


def raw_stages(w, h, factor):
    cur, out = (w, h), []
    for i, f in enumerate(planner.STAGE_FACTORS[factor]):
        st = B.stage_choice(cur, f, i)
        out.append(st)
        cur = st['output_size']
    return out


class TheRuntimeVerdict(unittest.TestCase):
    def test_the_recorded_run(self):
        v = VERDICT
        self.assertEqual(v['gate'], 'G7')
        self.assertTrue(v['torch'].startswith('2.14.1'), v['torch'])          # the worker runtime, not the test env's torch
        self.assertEqual(v['torchsde'], '0.2.6')
        self.assertFalse(v['quick'])
        self.assertEqual(v['cache_compared'], [45, 8])
        self.assertEqual((v['steps'], v['scheduler'], v['sampler']), (30, 'karras', 'dpmpp_2m_sde'))
        self.assertEqual(v['denoise'], [1.0, 0.68, 0.48])
        self.assertEqual(len(v['cases']), 3 * 3 * 3)
        self.assertEqual({tuple(c['latent']) for c in v['cases']}, {(1, 4, 128, 128), (1, 4, 251, 377), (1, 4, 1024, 768)})
        identical = all(c[k] == 0 for c in v['cases'] for k in ('capped8', 'prefetch45', 'prefetch_capped8'))
        self.assertEqual(v['identical'], identical)
        self.assertEqual(v['verdict'], 'PASS' if identical else 'FAIL')
        self.assertTrue(all(c['draws'] >= 29 for c in v['cases']))

    def test_the_cap_follows_the_verdict(self):
        self.assertEqual(B.BROWNIAN_CAPPED, VERDICT['verdict'] == 'PASS')
        self.assertEqual(B.constants()['brownian_cache'], 8 if B.BROWNIAN_CAPPED else 45)

    def test_the_constant_reaches_the_fork(self):
        p = controls.stage_params(controls.resolve({})[0], 0)
        g, _ = graph_banded.build_stage('in.plane', 1752, 1096, p, 'x', 'pl', 'r', constants=B.constants())
        spot = [n['inputs'] for n in g.values() if n['class_type'] == 'ClaudeSpotTilesBanded'][0]
        if B.BROWNIAN_CAPPED:
            self.assertEqual(spot['brownian_cache'], 8)
        else:
            self.assertNotIn('brownian_cache', spot)
        self.assertIn('brownian_cache', graph_banded.NODE_OPTIONAL['ClaudeSpotTilesBanded'])


class G9AfterTheFlip(unittest.TestCase):
    def test_the_design_capped_sizing_to_a_tenth(self):
        for (w, h, f, mc), (exp, eph, up, uph, split) in SIZING_CAPPED.items():
            cap = CAPS[mc]
            st = raw_stages(w, h, f)
            splits = [B.split_needed(s, mc, cap, tier='bxf', terms=False) for s in st]
            pk = [B.stage_peaks(s, mc, sp, brownian_capped=True, tier='bxf', terms=False) for s, sp in zip(st, splits)]
            e = max(pk, key=lambda d: d['exp'][0])
            u = max(pk, key=lambda d: d['up'][0])
            key = (w, h, f, mc)
            self.assertEqual(''.join('s' if x else '-' for x in splits), split, key)
            self.assertEqual((round(e['exp'][0], 1), e['exp'][1]), (exp, eph), key)
            self.assertEqual((round(u['up'][0], 1), u['up'][1]), (up, uph), key)

    def test_the_flip_lowers_only_the_expected_figures(self):
        for (w, h, f, mc) in SIZING_CAPPED:
            for s in raw_stages(w, h, f):
                for tier in ('bxf', 'tier3'):
                    for split in (False, True):
                        a = B.stage_peaks(s, mc, split, brownian_capped=False, tier=tier)
                        b = B.stage_peaks(s, mc, split, brownian_capped=True, tier=tier)
                        self.assertEqual(a['up'], b['up'])
                        self.assertEqual(a['phases_up'], b['phases_up'])
                        self.assertLessEqual(b['exp'][0], a['exp'][0])

    def test_admission_is_unchanged_by_the_flip(self):
        """Admission is on the upper bound, which carries the cache measured: the flip changes no verdict."""
        proven = {k: 10_000.0 for k in B.BANDED_PROVEN_MP}
        with mock.patch.dict(B.BANDED_PROVEN_MP, proven), mock.patch.object(B, 'BXF_AVAILABLE', True):
            for (w, h, f, mc) in SIZING_CAPPED:
                with mock.patch.object(B, 'BROWNIAN_CAPPED', False):
                    a = B.plan_banded(w, h, f, CAPS[mc])
                with mock.patch.object(B, 'BROWNIAN_CAPPED', True):
                    b = B.plan_banded(w, h, f, CAPS[mc])
                self.assertEqual((a.ok, a.peak_ram_gb), (b.ok, b.peak_ram_gb), (w, h, f, mc))
                if a.ok:
                    self.assertEqual((a.banded['brownian_cache'], b.banded['brownian_cache']), (45, 8))


if __name__ == '__main__':
    unittest.main()
