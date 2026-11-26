"""The finish tier of a Large-image plan (engine/banded_plan.py; build wave 2, contracts finish_tier and finish_inputs).

banded_plan.BXF_AVAILABLE (default False: fail closed) chooses the plan constant 'finish_tier': 'bxf' (the banded exact
finish, counted by its band terms) or 'tier3' (5.0.1's whole v4_finish and shadow toe on the planes, what the shipped worker
runs wherever its G1 table does not apply). A 'tier3' plan counts the registered upper bound of the whole finish in its finish
phase, and is refused in plain words that name the size above FINISH_WHOLE_MAX_MP (read from the banded node pack) or over the
cap. The band budget and the process count are plan constants from the machine class of the cap. Sizes only."""
import ast
import json
import unittest
from pathlib import Path
from unittest import mock

from engine import banded_plan as B
from engine import planner

ROOT = Path(__file__).resolve().parents[1]
PROVEN = {k: 10_000.0 for k in B.BANDED_PROVEN_MP}
CAPS = {'pc64': 59.0, 'ws128': 122.2, 'pc48': 45.2}
MEASURED = json.loads((ROOT / 'tests' / 'fixtures' / 'plan2_tier3_measurements.json').read_text(encoding='utf8'))


def bxf(on=True):
    return mock.patch.object(B, 'BXF_AVAILABLE', on)


def proven():
    return mock.patch.dict(B.BANDED_PROVEN_MP, PROVEN)


def raw_stages(w, h, factor):
    cur, out = (w, h), []
    for i, f in enumerate(planner.STAGE_FACTORS[factor]):
        st = B.stage_choice(cur, f, i)
        out.append(st)
        cur = st['output_size']
    return out


def mp(size):
    return size[0] * size[1] / 1e6


def pack_finish_limit():
    """FINISH_WHOLE_MAX_MP as node_pack/claude_banded/__init__.py assigns it (read, never imported or edited here)."""
    src = (ROOT / 'node_pack' / 'claude_banded' / '__init__.py').read_text(encoding='utf8')
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and any(getattr(t, 'id', None) == 'FINISH_WHOLE_MAX_MP' for t in node.targets):
            return float(ast.literal_eval(node.value))
    raise AssertionError('FINISH_WHOLE_MAX_MP is not assigned in the banded pack')


class TheTierIsAPlanConstant(unittest.TestCase):
    def test_fail_closed_by_default(self):
        self.assertIs(B.BXF_AVAILABLE, False)
        self.assertEqual(B.finish_tier(), 'tier3')
        with bxf():
            self.assertEqual(B.finish_tier(), 'bxf')
        self.assertEqual(B.finish_tier(), 'tier3')
        # nothing is admitted above the release sizes the proof passed (tests/test_release_proven_sizes.py)
        self.assertEqual(B.BANDED_PROVEN_MP, {'ws128': 10240 * 12800 / 1e6, 'pc64': 13056 * 16320 / 1e6,
                                              'pc48': 11200 * 14000 / 1e6})

    def test_the_plan_carries_the_tier_it_counted(self):
        with proven():
            for on, want in ((False, 'tier3'), (True, 'bxf')):
                with bxf(on):
                    p = B.plan_banded(2800, 3500, 4, 122.2)           # last pass 156.8 MP: under 300 MP
                self.assertTrue(p.ok, p.reason)
                self.assertEqual(p.banded['finish_tier'], want)
                self.assertEqual({s.finish_tier for s in p.stages}, {want})
                d = p.to_dict()
                self.assertEqual(json.loads(json.dumps(d)), d)
                self.assertEqual(d['banded']['finish_tier'], want)
                self.assertEqual({s['finish_tier'] for s in d['stages']}, {want})

    def test_bxf_only_when_bxf_available(self):
        with proven():
            for w, h, f, cap in ((2800, 3500, 4, 122.2), (3500, 2188, 4, 122.2)):
                with bxf(False):
                    p = B.plan_banded(w, h, f, cap)
                if p.ok:
                    self.assertEqual(p.banded['finish_tier'], 'tier3')
            c = planner.plan(2048, 2048, 2, ram_cap_gb=59.0)
            self.assertEqual(B.plan_forced(c, 59.0).banded['finish_tier'], 'tier3')
            with bxf():
                self.assertEqual(B.plan_forced(c, 59.0).banded['finish_tier'], 'bxf')

    def test_the_limit_is_the_packs_own(self):
        self.assertEqual(B.FINISH_WHOLE_MAX_MP, pack_finish_limit())
        self.assertEqual(B.FINISH_WHOLE_MAX_MP, 300.0)
        src = (ROOT / 'engine' / 'banded_plan.py').read_text(encoding='utf8')
        self.assertNotIn('FINISH_WHOLE_MAX_MP = 300', src)                  # read from the pack, not copied


class Tier3IsCounted(unittest.TestCase):
    def test_the_whole_finish_bound_covers_every_measurement_cited(self):
        for m in MEASURED['measurements']:
            got = B.tier3_finish_gb(mp(m['finish_size']), mp(m['pre']))
            self.assertGreaterEqual(got, m['peak_commit_gib'], m)
            self.assertLess(got, 1.25 * m['peak_commit_gib'] + 1.0, m)          # an upper bound, not an arbitrary one

    def test_the_finish_phase_takes_the_larger_of_5_0_1s_model_and_the_whole_finish(self):
        for w, h, f, mc in ((2800, 3500, 4, 'ws128'), (3500, 2188, 4, 'ws128'), (3500, 2188, 2, 'pc64'), (1280, 1600, 4, 'pc64')):
            for st in raw_stages(w, h, f):
                for split in (False, True):
                    up = B.stage_peaks(st, mc, split, tier='tier3')['phases_up']['finish']
                    I, R, O = mp(st['padded_size']), mp(st['render_size']), mp(st['output_size'])
                    fin_mp = mp((int(st['padded_size'][0] * st['factor']), int(st['padded_size'][1] * st['factor'])))
                    svc = B.service_gb(st)
                    self.assertGreaterEqual(up + 1e-9, planner.stage_peak_gb(R, O, I) - B.SERVICE_GB + svc)
                    x_up = B.X0 + B.XR_UP * R + B.XRES
                    v_fin = B.CTX_GB if split else max(B.V0 + B.V_R * R, B.VS0 + B.VS_BPR * B.G * R)
                    self.assertGreaterEqual(up + 1e-9, v_fin + x_up + B.tier3_finish_gb(fin_mp, I) + svc)
                    bxf_up = B.stage_peaks(st, mc, split, tier='bxf')['phases_up']['finish']
                    self.assertGreater(up, bxf_up, (w, h, f, mc, st['index'], split))

    def test_a_stage_reads_its_own_tier(self):
        with proven(), bxf(False):
            p = B.plan_banded(2800, 3500, 4, 122.2)
        for s in p.stages:
            with bxf(True):                                     # the module default changed since: the stage keeps its own
                self.assertEqual(round(B.stage_peaks(s, 'ws128', s.split_finish)['up'][0], 1), s.peak_upper_gb)

    def test_above_300_mp_is_refused_naming_the_size(self):
        with proven(), bxf(False):
            for w, h, f, cap in ((3500, 2188, 8, 122.2), (2800, 3500, 6, 122.2), (4000, 4000, 8, 122.2), (3500, 2188, 8, 59.0)):
                p = B.plan_banded(w, h, f, cap)
                self.assertFalse(p.ok, (w, h, f))
                self.assertIn(f'{w * f:,} × {h * f:,} px', p.reason)
                self.assertIn('300 MP', p.reason)
                self.assertNotIn('not yet been measured', p.reason)
        with proven(), bxf(True):
            self.assertTrue(B.plan_banded(3500, 2188, 8, 122.2).ok)

    def test_over_the_cap_is_refused_naming_the_size(self):
        with proven(), bxf(False):
            p = B.plan_banded(3500, 2188, 4, 59.0)              # the 122.5 MP whole finish does not fit a 64 GB PC
            self.assertFalse(p.ok)
            self.assertIn('14,000 × 8,752 px', p.reason)
            self.assertIn('GB of memory', p.reason)
            p = B.plan_banded(3500, 2188, 6, 122.2)             # 275.7 MP: under 300 MP, over the workstation's cap
            self.assertFalse(p.ok)
            self.assertIn('21,000 × 13,128 px', p.reason)
            self.assertIn('GB of memory', p.reason)
        with proven(), bxf(True):
            self.assertTrue(B.plan_banded(3500, 2188, 4, 59.0).ok)

    def test_the_refusals_come_after_the_proof_limit(self):
        """Over every class's proven size (8x of 3500 x 2188, 490 MP) the answer stays 'not yet been measured', as at the base."""
        for on in (False, True):
            with bxf(on):
                p = B.plan_banded(3500, 2188, 8, 59.0)
            self.assertFalse(p.ok)
            self.assertIn('not yet been measured', p.reason)

    def test_forced_plans_of_the_comparison_still_fit_under_tier3(self):
        """The 1:1 comparison's forced plans (design 7.4) are classic plans 5.0.1 accepts; tier 3 runs the same whole finish."""
        with bxf(False):
            for w, h, f, cap in ((3500, 2188, 2, 59.0), (2800, 3500, 2, 59.0), (1280, 1600, 4, 59.0), (3500, 2188, 4, 122.2)):
                c = planner.plan(w, h, f, ram_cap_gb=cap)
                self.assertEqual(c.engine, 'classic')
                p = B.plan_forced(c, cap)
                self.assertTrue(p.ok, (w, h, f, cap, p.reason))
                self.assertEqual(p.banded['finish_tier'], 'tier3')
                for a, s in zip(c.stages, p.stages):
                    self.assertGreaterEqual(s.peak_upper_gb + 0.05, round(planner.stage_peak(a), 1))


class BandBudgetAndProcesses(unittest.TestCase):
    def test_by_machine_class_of_the_cap(self):
        want = {'ws128': (6.0, 4), 'pc64': (3.0, 2), 'pc48': (2.0, 1)}
        for mc, cap in CAPS.items():
            self.assertEqual((B.MACHINE_CLASSES[mc]['band_gb'], B.MACHINE_CLASSES[mc]['processes']), want[mc])
            c = planner.plan(2048, 2048, 2, ram_cap_gb=cap)
            for on in (False, True):
                with bxf(on):
                    p = B.plan_forced(c, cap)
                self.assertTrue(p.ok, (mc, p.reason))
                self.assertEqual(p.banded['machine_class'], mc)
                self.assertEqual((p.banded['bxf_band_gb'], p.banded['bxf_processes']), want[mc])
                self.assertEqual(p.banded['finish_tier'], 'bxf' if on else 'tier3')
        self.assertEqual(B.machine_class(45.2), 'pc48')         # a 64 GB node run at the 45.2 cap takes pc48's values
        self.assertEqual(B.finish_constants('pc48')['bxf_band_gb'], 2.0)

    def test_the_registered_sets(self):
        from engine import bands
        for mc in B.MACHINE_CLASSES.values():
            self.assertIn(mc['band_gb'], bands.BAND_BUDGETS_GB)
            self.assertIn(mc['processes'], bands.PROCESS_COUNTS)

    def test_constants_alone_carry_none_of_them(self):
        c = B.constants()
        for k in B.FINISH_CONSTANTS:
            self.assertNotIn(k, c)
        self.assertEqual(B.FINISH_CONSTANTS, ('bxf_band_gb', 'bxf_processes', 'finish_tier'))

    def test_none_of_them_is_a_pixel_constant(self):
        for k in B.FINISH_CONSTANTS:
            self.assertIn(k, B.NON_PIXEL_CONSTANTS)
        for k in ('finish', 'canvas', 'recipe', 'halo_fix', 'mode', 'window', 'dat', 'vae', 'canny', 'brownian_cache'):
            self.assertNotIn(k, B.NON_PIXEL_CONSTANTS)


if __name__ == '__main__':
    unittest.main()
