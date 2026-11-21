"""The Large-image engine's planner (engine/banded_plan.py; engine design sections 2.1, 2.8, 3.1, 6): which plans it takes,
its registered memory model (gate G9: the design's sizing, design-2-evidence/plan_final2.py, reproduced to 0.1 GiB), the
worker-restart split of the finish (L3r), and the refusals. Sizes only.

Build wave 2: these are the banded exact finish's figures, so this module sets banded_plan.BXF_AVAILABLE = True for its own
tests (contract finish_tier: the shipped default, False, makes every plan count 5.0.1's whole finish, tests/
test_plan2_finish_tier.py). G9 reproduces the design's model as registered (stage_peaks with terms=False); the wave-2 terms
on top of it are tests/test_plan2_model_terms.py's, with the figures they give pinned in tests/fixtures/plan2_sizing.json."""
import json
import unittest
from unittest import mock

from engine import banded_plan as B
from engine import planner

PROVEN = {k: 10_000.0 for k in B.BANDED_PROVEN_MP}
CAPS = {'pc64': 59.0, 'ws128': 122.2, 'pc48': 45.2}
_BXF = mock.patch.object(B, 'BXF_AVAILABLE', True)


def setUpModule():
    _BXF.start()


def tearDownModule():
    _BXF.stop()

# plan_final2-output.txt, "Revised: L1 + L2 + L3r, 4 B/Rpx, Brownian cache uncapped (until G7 passes)":
# (w, h, factor, machine): (expected GiB, its phase, upper GiB, its phase, VRAM GiB, split per stage, ships on the upper bound)
SIZING = {
    (3500, 2188, 4, 'pc64'): (36.8, 'finish', 41.2, 'finish', 16.0, '--', True),
    (3500, 2188, 4, 'pc48'): (35.4, 'finish', 39.8, 'finish', 16.0, '--', True),
    (3500, 2188, 6, 'pc64'): (41.6, 'finish', 51.6, 'finish', 16.9, '---', True),
    (3500, 2188, 6, 'ws128'): (37.1, 'sampling', 43.5, 'P0', 16.9, 'sss', True),
    (3500, 2188, 6, 'pc48'): (37.1, 'sampling', 43.5, 'P0', 16.9, '--s', False),
    (3500, 2188, 8, 'pc64'): (42.5, 'sampling', 51.8, 'decode', 17.3, '--s', True),
    (3500, 2188, 8, 'ws128'): (42.5, 'sampling', 51.8, 'decode', 17.3, 'sss', True),
    (3500, 2188, 8, 'pc48'): (42.5, 'sampling', 51.8, 'decode', 17.3, '--s', False),
    (2800, 3500, 4, 'pc64'): (37.7, 'finish', 43.4, 'finish', 16.1, '--', True),
    (2800, 3500, 4, 'ws128'): (34.0, 'sampling', 37.5, 'decode', 16.1, 'ss', True),
    (2800, 3500, 4, 'pc48'): (36.3, 'finish', 42.0, 'finish', 16.1, '--', True),
    (2800, 3500, 6, 'pc64'): (39.0, 'sampling', 46.2, 'P0', 17.3, '--s', True),
    (2800, 3500, 6, 'ws128'): (39.0, 'sampling', 46.2, 'P0', 17.3, 'sss', True),
    (2800, 3500, 8, 'pc64'): (46.1, 'sampling', 56.7, 'decode', 17.8, '--s', False),
    (2800, 3500, 8, 'ws128'): (46.1, 'sampling', 59.9, 'finish', 17.8, 'sss', True),
    (4000, 2500, 8, 'pc64'): (46.4, 'sampling', 58.0, 'decode', 17.9, '--s', False),
    (4000, 2500, 8, 'ws128'): (46.4, 'sampling', 60.7, 'finish', 17.9, 'sss', True),
    (4000, 4000, 8, 'ws128'): (56.2, 'sampling', 83.8, 'finish', 19.3, 'sss', True),
    (4000, 4000, 8, 'pc64'): (56.2, 'sampling', 80.0, 'finish', 19.3, '--s', False),
    (5333, 3333, 6, 'ws128'): (46.4, 'sampling', 62.1, 'finish', 18.8, 'sss', True),
}


def raw_stages(w, h, factor):
    cur, out = (w, h), []
    for i, f in enumerate(planner.STAGE_FACTORS[factor]):
        st = B.stage_choice(cur, f, i)
        out.append(st)
        cur = st['output_size']
    return out


def design(st, mc, split, capped=False):
    """The design's registered model (plan_final2.py): the banded exact finish, without the wave-2 terms."""
    return B.stage_peaks(st, mc, split, brownian_capped=capped, tier='bxf', terms=False)


class G9TheRegisteredMemoryModel(unittest.TestCase):
    def test_the_design_sizing_to_a_tenth(self):
        for (w, h, f, mc), (exp, eph, up, uph, vram, split, ships) in SIZING.items():
            cap = CAPS[mc]
            st = raw_stages(w, h, f)
            splits = [B.split_needed(s, mc, cap, tier='bxf', terms=False) for s in st]
            pk = [design(s, mc, sp) for s, sp in zip(st, splits)]
            e = max(pk, key=lambda d: d['exp'][0])
            u = max(pk, key=lambda d: d['up'][0])
            key = (w, h, f, mc)
            self.assertEqual(''.join('s' if x else '-' for x in splits), split, key)
            self.assertEqual((round(e['exp'][0], 1), e['exp'][1]), (exp, eph), key)
            self.assertEqual((round(u['up'][0], 1), u['up'][1]), (up, uph), key)
            self.assertAlmostEqual(max(B.banded_vram_gb(s) for s in st), vram, delta=0.051, msg=key)
            self.assertEqual(B.MARGIN * up <= cap - B.CAP_SPARE_GB, ships, key)       # the design's verdict on its own model
            with mock.patch.dict(B.BANDED_PROVEN_MP, PROVEN):
                p = B.plan_banded(w, h, f, cap)
            self.assertEqual(p.ok, ships, (key, p.reason))      # with the wave-2 terms every row keeps the design's verdict
            if p.ok:            # admission now counts the wave-2 terms too: never less than the design with the same splits
                # (a stage the terms push over the cap takes the registered L3r split, which the design's row may not have had)
                same = max(design(s, mc, ps.split_finish)['up'][0] for s, ps in zip(st, p.stages))
                self.assertGreaterEqual(p.peak_ram_gb, round(B.MARGIN * same, 1), key)
                if [ps.split_finish for ps in p.stages] == splits:
                    self.assertGreaterEqual(p.peak_ram_gb, round(B.MARGIN * up, 1), key)
                    self.assertTrue(ships, key)
            else:
                self.assertIn('memory', p.reason)

    def test_the_split_has_no_weight_copy_moment(self):
        """L3r (a fresh worker) removes V from the finish; the in-process /free of the first design would have put the 8x
        row of 3500 x 2188 over the 64 GB cap (D4). With the split, its finish is no longer what binds."""
        st = raw_stages(3500, 2188, 8)[-1]
        for terms in (False, True):
            no_split = B.stage_peaks(st, 'pc64', False, tier='bxf', terms=terms)
            split = B.stage_peaks(st, 'pc64', True, tier='bxf', terms=terms)
            self.assertGreater(no_split['phases_up']['finish'], split['phases_up']['finish'] + 15)
            self.assertLessEqual(B.MARGIN * split['up'][0], 59.0 - 1.0)
            self.assertGreater(B.MARGIN * no_split['up'][0], 59.0 - 1.0)

    def test_the_brownian_cap_after_g7(self):
        """G7 passed on the worker runtime (tests/test_plan2_g7.py): the cache is capped at 8, and only the expected figure
        falls (the upper model's X was measured with the full cache in it)."""
        self.assertTrue(B.BROWNIAN_CAPPED)
        st = raw_stages(3500, 2188, 8)[-1]
        capped, full = B.stage_peaks(st, 'ws128', True, True), B.stage_peaks(st, 'ws128', True, False)
        self.assertGreater(full['exp'][0], capped['exp'][0])
        self.assertEqual(full['up'], capped['up'])          # the upper model's X was measured with the cache in it
        self.assertEqual(B.constants()['brownian_cache'], 8)
        self.assertEqual(B.stage_peaks(st, 'ws128', True), capped)

    def test_sampler_state_is_four_bytes_per_render_pixel(self):
        """One figure for the on-card sampler state everywhere (D5): VRAM 15.5 + 4 B/Rpx."""
        for R_mp, want in ((122.5, 16.0), (490.1, 17.3), (640.0, 17.9), (1024.0, 19.3)):
            self.assertAlmostEqual(B.VS0 + B.VS_BPR * B.G * R_mp, want, delta=0.06)


class WhichPlansItTakes(unittest.TestCase):
    def test_nothing_is_admitted_until_the_proof_sets_the_sizes(self):
        self.assertEqual(set(B.BANDED_PROVEN_MP.values()), {0.0})
        p = B.plan_banded(3500, 2188, 8, 59.0)
        self.assertFalse(p.ok)
        self.assertIn('not yet proven', p.reason)
        # the router then gives 5.0.1's own refusal
        self.assertEqual(planner.plan(3500, 2188, 8, ram_cap_gb=59.0).to_dict(),
                         planner.plan_501(3500, 2188, 8, ram_cap_gb=59.0).to_dict())

    def test_the_router_takes_only_what_501_refuses(self):
        with mock.patch.dict(B.BANDED_PROVEN_MP, PROVEN):
            p = planner.plan(3500, 2188, 4, ram_cap_gb=59.0)          # 5.0.1 refuses for memory on 64 GB
            self.assertEqual(p.engine, 'banded')
            self.assertEqual([(s.factor, s.supersample) for s in p.stages], [(2.0, 2.0), (2.0, 1.0)])
            self.assertEqual(planner.plan(3500, 2188, 4, ram_cap_gb=122.2).engine, 'classic')   # the workstation runs it
            self.assertEqual(planner.plan(2048, 2048, 2, ram_cap_gb=59.0).engine, 'classic')
            self.assertEqual(planner.plan(3500, 2188, 8, ram_cap_gb=59.0).engine, 'banded')   # 28,000 px, over 16,384
            self.assertEqual(planner.plan(3500, 2188, 8, ram_cap_gb=None).engine, 'classic')  # no cap, no machine class

    def test_the_same_stages_on_every_computer(self):
        """A new plan's stages do not depend on the machine (only admission and the split do)."""
        with mock.patch.dict(B.BANDED_PROVEN_MP, PROVEN):
            a = B.plan_banded(3500, 2188, 8, 59.0)
            b = B.plan_banded(3500, 2188, 8, 122.2)
        sig = lambda p: [(s.factor, s.supersample, s.padded_size, s.render_size, s.output_size) for s in p.stages]
        self.assertEqual(sig(a), sig(b))
        self.assertEqual([s.supersample for s in a.stages], [2.0, 1.0, 1.0])

    def test_up_to_32000_px_and_not_beyond(self):
        with mock.patch.dict(B.BANDED_PROVEN_MP, PROVEN):
            p = B.plan_banded(4000, 2500, 8, 122.2)
            self.assertTrue(p.ok, p.reason)
            self.assertEqual(p.output_size, (32000, 20000))
            p = B.plan_banded(4000, 4000, 8, 122.2)
            self.assertTrue(p.ok, p.reason)
            self.assertEqual(p.output_size, (32000, 32000))
            p = B.plan_banded(4001, 2500, 8, 122.2)
            self.assertFalse(p.ok)
            self.assertIn('32,000', p.reason)
            p = B.plan_banded(3500, 64, 8, 122.2)
            self.assertTrue(p.ok, p.reason)
            self.assertEqual(p.output_size, (28000, 512))

    def test_refusals(self):
        with mock.patch.dict(B.BANDED_PROVEN_MP, PROVEN):
            self.assertIn('48 GB', B.plan_banded(3500, 2188, 4, 28.0).reason)          # 32 GB PCs: not yet
            self.assertIn('Bolt', B.plan_banded(3500, 2188, 4, 59.0, mode='bolt').reason)
            self.assertIn('memory', B.plan_banded(4000, 4000, 8, 59.0).reason)
            self.assertFalse(B.plan_banded(3500, 2188, 3, 59.0).ok)
        with mock.patch.dict(B.BANDED_PROVEN_MP, {'ws128': 200.0, 'pc64': 0.0, 'pc48': 0.0}):
            self.assertTrue(B.plan_banded(2800, 3500, 4, 122.2).ok)                    # 156.8 MP
            self.assertIn('not yet proven', B.plan_banded(3500, 2188, 6, 122.2).reason)  # 275.7 MP

    def test_the_switches_that_would_move_classic_plans_are_off(self):
        self.assertFalse(B.UNLIGHTEN)
        self.assertFalse(B.MAX_SAID_BES_TAKES_CAPPED)
        self.assertFalse(B.OFFER_AFTER_OOM)
        self.assertFalse(B.BOLT_BANDED)

    def test_the_plan_dict_carries_its_constants_and_reads_back(self):
        with mock.patch.dict(B.BANDED_PROVEN_MP, PROVEN):
            p = B.plan_banded(3500, 2188, 8, 59.0)
        d = p.to_dict()
        self.assertEqual(d['engine'], 'banded')
        self.assertEqual(json.loads(json.dumps(d)), d)
        c = d['banded']
        for k in ('bes', 'finish', 'canvas', 'recipe', 'halo_fix', 'mode', 'window', 'dat', 'vae', 'canny', 'encode_state',
                  'brownian_cache', 'cmap', 'machine_class', 'forced', 'hint_store'):
            self.assertIn(k, c)
        self.assertEqual((c['finish'], c['canvas'], c['recipe'], c['halo_fix']), ('bxf-1', 'lanczos-1', 'r501', None))
        self.assertEqual((c['bxf_band_gb'], c['bxf_processes'], c['finish_tier']), (3.0, 2, 'bxf'))
        self.assertTrue(B.is_banded(d))
        for s in d['stages']:
            for k in ('split_finish', 'peak_expected_gb', 'peak_upper_gb', 'binding_phase', 'vram_gb', 'disk_gb', 'minutes',
                      'finish_tier', 'lora_gb'):
                self.assertIn(k, s)

    def test_minutes_and_disk(self):
        with mock.patch.dict(B.BANDED_PROVEN_MP, PROVEN):
            p = B.plan_banded(3500, 2188, 4, 59.0)
        # the design's 72 min on one RTX 5090 (0.3), plus the plane-I/O budget until R2 measures it; and the wave-2 upper-
        # bound terms on top (the fork's host crops, the lean SAM's views, the plane band I/O: tests/test_plan2_model_terms)
        base = sum(B.banded_minutes(s, s.split_finish, terms=False) for s in p.stages)
        self.assertAlmostEqual(base, 72 * B.IO_BUDGET, delta=1.5)
        self.assertAlmostEqual(p.minutes, round(sum(round(B.banded_minutes(s, s.split_finish), 1) for s in p.stages), 1))
        self.assertGreater(p.minutes, base)
        self.assertAlmostEqual(max(s.disk_gb for s in p.stages), 14.0, delta=1.0)
        with mock.patch.dict(B.BANDED_PROVEN_MP, PROVEN):
            p = B.plan_banded(3500, 2188, 8, 59.0)
        self.assertEqual([s.split_finish for s in p.stages], [False, False, True])
        self.assertAlmostEqual(p.stages[-1].minutes - B.banded_minutes(p.stages[-1], False), B.SPLIT_MINUTES, delta=0.11)


class ForcedThroughTheNewPath(unittest.TestCase):
    """plan_forced: the comparison's Large-image side (developer builds only; the build channel is checked by the service)."""

    def test_the_classic_plans_own_stages(self):
        c = planner.plan(3500, 2188, 4, ram_cap_gb=122.2)
        self.assertEqual(c.engine, 'classic')
        f = B.plan_forced(c, 122.2)
        self.assertTrue(f.ok, f.reason)
        self.assertEqual(f.engine, 'banded')
        self.assertTrue(f.banded['forced'])
        for a, b in zip(c.stages, f.stages):
            self.assertEqual((a.factor, a.supersample, a.input_size, a.padded_size, a.render_size, a.output_size),
                             (b.factor, b.supersample, b.input_size, b.padded_size, b.render_size, b.output_size))

    def test_redux_2x_cases_of_the_comparison(self):
        for (w, h) in ((3500, 2188), (2800, 3500)):
            c = planner.plan(w, h, 2, ram_cap_gb=59.0)
            f = B.plan_forced(c, 59.0)
            self.assertTrue(f.ok, (w, h, f.reason))
        c = planner.plan(1280, 1600, 4, ram_cap_gb=59.0)
        self.assertTrue(B.plan_forced(c, 59.0).ok)

    def test_a_refused_classic_plan_is_not_forced(self):
        c = planner.plan(9000, 9000, 8, ram_cap_gb=59.0)
        self.assertFalse(c.ok)
        self.assertIs(B.plan_forced(c, 59.0), c)


if __name__ == '__main__':
    unittest.main()
