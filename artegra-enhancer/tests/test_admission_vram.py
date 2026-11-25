"""Small-card admission (engine design ENGINE-DESIGN.md 8.1 and 8.3; B14): the classic graphics-memory pre-check against
ENGINE-FACTS 2.3's measured terms, plain refusals on cards of 24 GiB or less with the largest size the card can make, none on
a 32 GB card (which behaves exactly as 5.0.1), and the Large-image engine's VRAM classes. In-process (Runner with
SimpleNamespace stubs; no service process). Sizes only."""
import unittest
from types import SimpleNamespace
from unittest import mock

from engine import banded_plan, controls, planner, vram_model
from service import card_factor, memory_policy
from service.runner import BANDED_8GB, BANDED_SMALL_CARD, Runner

G = vram_model.G
CARDS = {8: 7.99, 10: 10.0, 11: 11.0, 12: 11.99, 16: 15.99, 20: 19.99, 24: 23.99, 32: 31.84, 48: 47.99}


def card(gb, index=0, name=None):
    return {'index': index, 'uuid': f'GPU-{gb}-{index}', 'name': name or f'NVIDIA Test {gb} GB', 'mem_total_gb': CARDS[gb],
            'mem_free_gb': CARDS[gb] - 1.0}


def runner(cards, profile='auto', cap=59.0):
    r = object.__new__(Runner)
    r.settings = SimpleNamespace(get=lambda: {'gpus': [c['index'] for c in cards], 'memory_profile': profile,
                                              'ram_cap_gb': cap})
    r.gpu_list = lambda max_age=None: ([dict(c) for c in cards], None)
    r.card_factors = card_factor.CardFactors(None)
    r.log = mock.Mock()
    return r


def stage(I_mp, R_mp, index=0, f=2.0, s=1.0):
    side = lambda mp: (int(round((mp * 1e6) ** 0.5)), int(round((mp * 1e6) ** 0.5)))
    return {'index': index, 'factor': f, 'supersample': s, 'input_size': side(I_mp), 'padded_size': side(I_mp),
            'render_size': side(R_mp), 'output_size': side(R_mp), 'render_mp': R_mp, 'minutes': 10.0}


def plan_of(*stages, engine='classic', size=(4000, 4000), factor=2):
    d = {'ok': True, 'factor': factor, 'input_size': list(size), 'output_size': [size[0] * factor, size[1] * factor],
         'stages': list(stages), 'minutes': 10.0, 'peak_ram_gb': 30.0}
    if engine == 'banded':
        d.update(engine='banded', banded=banded_plan.constants())
    return d


class TheClassicModelAgainstTheMeasurements(unittest.TestCase):
    """ENGINE-FACTS 2.3 and S0b: the model is an upper bound of what was measured on a warm RTX 5090 (reference profile)."""

    def test_the_sam_moment(self):
        for I, measured_peak in ((30.6, 23.9), (32.8, 25.7)):          # P0 peak (worker share), stock SAM
            m = vram_model.classic_moments(stage(I, 4 * I), 'reference', protect=True, lean=False)
            self.assertGreaterEqual(m['sam'], measured_peak)
            self.assertGreaterEqual(m['sam'] - vram_model.RESIDENT_GB['reference']['sam'], 10.1)   # +10.0-10.1 GiB measured
        s0b = 13.823 + 0.3695 * 66.25                                     # S0b's demand at the 66.25 MP pass-3 input
        self.assertGreaterEqual(vram_model.classic_moments(stage(66.25, 66.25), 'reference', lean=False)['sam'], s0b)
        self.assertAlmostEqual(vram_model.SAM_STOCK_BPI + vram_model.SAM_KEPT_BPI, 411.0)

    def test_the_lean_node_above_the_ceiling(self):
        s_lo, s_hi = stage(32.9, 131.6), stage(33.1, 132.4)          # either side of the 33 MP ceiling
        lo = vram_model.classic_moments(s_lo, 'reference')
        hi = vram_model.classic_moments(s_hi, 'reference')
        self.assertAlmostEqual(lo['sam'], 13.823 + 411 * G * vram_model._mp(s_lo['padded_size']), places=9)
        self.assertAlmostEqual(hi['sam'], 13.823 + 13 * G * vram_model._mp(s_hi['padded_size']), places=9)
        self.assertNotIn('sam', vram_model.classic_moments(stage(32.9, 131.6), 'reference', protect=False))

    def test_the_blur_and_the_samplers(self):
        m = vram_model.classic_moments(stage(30.6, 490.0), 'reference')
        self.assertAlmostEqual(m['blur'] - vram_model.RESIDENT_GB['reference']['blur'], 16.4, delta=0.05)  # 36 B/Rpx at 490 MP
        for R, measured in ((122.5, 14.4), (157.0, 17.3)):               # P3 plateau 14.4-17.3 GiB at R 122-157 MP
            self.assertGreaterEqual(vram_model.classic_moments(stage(R / 4, R), 'reference')['samplers'], measured)

    def test_the_x4_model(self):
        st = stage(30.0, 120.0)
        m = vram_model.classic_moments(st, 'balanced', protect=False)
        self.assertAlmostEqual(m['x4'], vram_model.RESIDENT_GB['balanced']['x4'] + 12 * G * vram_model._mp(st['padded_size'])
                               + vram_model.DAT_TILE_GB)
        self.assertAlmostEqual(vram_model.DAT_TILE_GB, 4.5, places=3)

    def test_nominal_classes(self):
        for total, n in ((7.99, 8), (11.99, 12), (15.99, 16), (23.99, 24), (31.84, 32), (10.0, 10), (11.0, 11), (47.99, 48)):
            self.assertEqual(vram_model.nominal_gb(total), n)
        self.assertIsNone(vram_model.nominal_gb(None))
        self.assertIsNone(vram_model.nominal_gb(0))
        self.assertTrue(vram_model.checked(23.99))
        self.assertFalse(vram_model.checked(31.84))
        self.assertFalse(vram_model.checked(None))


class ClassicRefusals(unittest.TestCase):
    def test_none_on_a_32_gb_card_for_any_plan_5_0_1_makes(self):
        r = runner([card(32)])
        for w, h in ((512, 512), (3500, 2188), (2800, 3500), (6000, 3500), (8000, 5000)):
            for f in controls.SCALES:
                p = planner.plan(w, h, f, ram_cap_gb=122.2)
                self.assertIsNone(r._vram_refusal(p, protect=True), (w, h, f))
                self.assertIsNone(r._vram_refusal(p.to_dict(), protect=True), (w, h, f))
        huge = plan_of(stage(66.0, 600.0))                                # beyond any classic plan: still not checked
        self.assertIsNone(r._vram_refusal(huge))

    def test_an_8_gb_card_refuses_a_stock_sam_stage_in_plain_words(self):
        p = planner.plan(4000, 4000, 2, ram_cap_gb=59.0)                  # one stage, padded input 16 MP: stock SAM
        self.assertFalse(planner.sam_lean(*p.stages[0].padded_size))
        r = runner([card(8)])
        text = r._vram_refusal(p, protect=True)
        self.assertRegex(text, r'^This image needs about \d+ GB of graphics memory with the Classic engine; this card has '
                               r'8 GB\. A smaller image fits this card at 2×: up to a result of about [\d,]+ × '
                               r'[\d,]+ px\.$')
        need = vram_model.classic_plan_vram_gb(p, memory_policy.PROFILES['balanced'], True)[0]
        self.assertIn(f'about {max(int(-(-(need + 2.5) // 1)), 9)} GB', text)
        self.assertIsNone(r._vram_refusal(p, protect=False))              # without the SAM step it fits
        for gb in (12, 16, 24):
            self.assertIsNone(runner([card(gb)])._vram_refusal(p, protect=True), gb)

    def test_the_size_said_fits_and_a_little_more_does_not(self):
        p = planner.plan(4000, 4000, 2, ram_cap_gb=59.0)
        r = runner([card(8)])
        W, H = r._largest_classic(p, card(8), True)
        q = planner.plan(W // 2, H // 2, 2, ram_cap_gb=59.0)
        self.assertIsNone(r._card_vram_problem(q, card(8), True))
        bigger = planner.plan(int(W // 2 * 1.05), int(H // 2 * 1.05), 2, ram_cap_gb=59.0)
        self.assertIsNotNone(r._card_vram_problem(bigger, card(8), True))

    def test_need_is_not_monotone_so_the_words_never_say_largest(self):
        """Above the SAM ceiling the lean node runs, so on an 8 GB card a larger image can fit where a smaller one with the
        stock SAM step does not (the stock-SAM band; an open issue for small cards). The refusal says "a smaller image
        fits up to", which stays true."""
        r = runner([card(8)])
        refused = planner.plan(5700, 5700, 2, ram_cap_gb=122.2)       # 32.5 MP: the stock SAM step
        larger = planner.plan(5800, 5800, 2, ram_cap_gb=122.2)        # 33.6 MP: the lean node
        self.assertTrue(planner.sam_lean(*larger.stages[0].padded_size))
        self.assertIsNotNone(r._card_vram_problem(refused, card(8), True))
        self.assertIsNone(r._card_vram_problem(larger, card(8), True))
        self.assertNotIn('largest', r._vram_refusal(refused, protect=True))

    def test_refusals_at_8_12_16_and_24_gb_and_none_at_32(self):
        """A synthetic stage just over each class's usable memory is refused in plain words; just under, it is not."""
        bal = memory_policy.PROFILES['balanced']
        for gb in (8, 12, 16, 24):
            usable = vram_model.usable_gb(CARDS[gb])
            res = vram_model.RESIDENT_GB['balanced']['blur']
            R_over = (usable - res + 0.2) / (36 * G)
            R_under = (usable - res - 0.2) / (36 * G)
            over, under = plan_of(stage(1.0, R_over)), plan_of(stage(1.0, R_under))
            self.assertGreater(vram_model.classic_vram_gb(over['stages'][0], bal, protect=False), usable)
            r = runner([card(gb)])
            text = r._vram_refusal(over, protect=False)
            self.assertIsNotNone(text, gb)
            self.assertIn(f'this card has {gb} GB', text)
            self.assertIn('with the Classic engine', text)
            self.assertIsNone(r._vram_refusal(under, protect=False), gb)
            self.assertIsNone(runner([card(32)])._vram_refusal(over, protect=False))

    def test_a_card_that_reads_its_memory_late_is_not_checked(self):
        r = runner([])
        self.assertIsNone(r._vram_refusal(planner.plan(4000, 4000, 2, ram_cap_gb=59.0)))
        r = runner([{'index': 0, 'name': 'x', 'mem_total_gb': None}])
        self.assertIsNone(r._vram_refusal(planner.plan(4000, 4000, 2, ram_cap_gb=59.0)))

    def test_two_cards_one_that_fits(self):
        p = planner.plan(4000, 4000, 2, ram_cap_gb=59.0)
        r = runner([card(8, 0), card(16, 1)])
        self.assertIsNone(r._vram_refusal(p, protect=True))               # the 16 GB card can make it
        r2 = runner([card(8, 0), card(8, 1)])
        self.assertIn('the largest graphics card in use has 8 GB', r2._vram_refusal(p, protect=True))

    def test_a_refusal_reaches_plan_check(self):
        p = planner.plan(4000, 4000, 2, ram_cap_gb=59.0)
        r = runner([card(8)])
        r.finish_info = lambda minutes, plan=None: None
        r.memory_info = lambda: {'profiles': []}
        res = r.plan_check(p)
        self.assertFalse(res['ok'])
        self.assertTrue(res['vram_refused'])
        self.assertIn('graphics memory', res['reason'])
        self.assertEqual(res['text']['summary'], res['reason'])
        self.assertTrue(r.plan_check(p, protect=False)['ok'])
        r32 = runner([card(32)])
        r32.finish_info, r32.memory_info = r.finish_info, r.memory_info
        from service.media import plan_dict
        want = dict(plan_dict(p, 59.0, r.finish_info), memory={'profiles': []})
        self.assertEqual(r32.plan_check(p), want)                         # 5.0.1's answer, key for key


class TheScheduler(unittest.TestCase):
    def test_an_image_waits_for_the_card_it_fits(self):
        p = planner.plan(4000, 4000, 2, ram_cap_gb=59.0).to_dict()
        r = runner([card(8, 0), card(16, 1)])
        it = {'plan': p, 'settings': {}}
        r.store = SimpleNamespace(item=lambda j, i: it, get=lambda j: {'settings': {}})
        w8, w16 = SimpleNamespace(gpu=0), SimpleNamespace(gpu=1)
        self.assertFalse(r._fits_worker('j', 'i', w8))
        self.assertTrue(r._fits_worker('j', 'i', w16))
        both = SimpleNamespace(gpu=0, gpus=(0, 1))                         # one image shared by both: every card must fit
        self.assertFalse(r._fits_worker('j', 'i', both))
        it['settings'] = {'protect': []}
        self.assertTrue(r._fits_worker('j', 'i', w8))
        r1 = runner([card(8, 0)])                                          # it fits no card: given to the engine, which says so
        it['settings'] = {}
        r1.store = r.store
        self.assertTrue(r1._fits_worker('j', 'i', w8))
        r32 = runner([card(32, 0)])
        r32.store = r.store
        self.assertTrue(r32._fits_worker('j', 'i', SimpleNamespace(gpu=0)))
        r32._item_protect = mock.Mock(side_effect=AssertionError('a classic plan on a 32 GB card is not checked'))
        self.assertTrue(r32._fits_worker('j', 'i', SimpleNamespace(gpu=0)))


class LargeImageClasses(unittest.TestCase):
    def test_the_render_limits(self):
        self.assertEqual([vram_model.render_limit_mp(gb) for gb in (8, 12, 16, 24)], [537, 805, 1074, 1611])   # the design's
        self.assertEqual(vram_model.render_limit_mp(32), 2147)

    def banded(self, R):
        return plan_of(stage(R / 16, R), engine='banded')

    def test_refusals_by_class_in_plain_words(self):
        size = 'An 8,000 × 8,000 px result needs the Large-image engine on this computer.'      # A10: the size refused
        self.assertEqual(runner([card(8)])._vram_refusal(self.banded(100.0)), f'{BANDED_8GB} {size}')
        small = {'index': 0, 'name': 'x', 'mem_total_gb': 5.99}
        self.assertEqual(runner([small])._vram_refusal(self.banded(100.0)), f'{BANDED_SMALL_CARD.format(gb=12)} {size}')
        for gb, limit in ((12, 805), (16, 1074), (24, 1611)):
            r = runner([card(gb)])
            text = r._vram_refusal(self.banded(limit + 5.0))
            self.assertTrue(text.startswith(f'A {gb} GB graphics card can render up to {limit:,} MP with the Large-image '
                                            f'engine; an 8,000 × 8,000 px result needs {limit + 5:,.0f} MP. '), text)
            self.assertRegex(text, r' (A smaller image fits this card at 2× with the (?:Classic|Large-image) engine: up to a '
                                   r'result of about [\d,]+ × [\d,]+ px'
                                   r'|No smaller image of this shape fits this card at 2× with either engine)\.$')
            self.assertIsNone(r._vram_refusal(self.banded(limit - 5.0)), gb)
        self.assertIsNone(runner([card(32)])._vram_refusal(self.banded(1024.0)))        # 32,000 x 32,000 at s = 1

    def test_the_classes_a_proof_covers(self):
        self.assertEqual(vram_model.BANDED_CLASSES_GB[0], vram_model.BANDED_MIN_CARD_GB)
        got = {n: vram_model.banded_class_gb(n) for n in (None, 4, 6, 8, 10, 11, 12, 16, 20, 24, 32, 48, 96)}
        self.assertEqual(got, {None: None, 4: None, 6: None, 8: 8, 10: 8, 11: 8, 12: 12, 16: 16, 20: 16, 24: 24, 32: 32,
                               48: 32, 96: 32})
        self.assertEqual({gb: vram_model.banded_class_gb(vram_model.nominal_gb(CARDS[gb])) for gb in (10, 11, 12)},
                         {10: 8, 11: 8, 12: 12})                         # an 11.99 GiB card stays a 12 GB card

    def test_10_and_11_gb_cards_are_the_8_gb_class(self):
        self.assertFalse(vram_model.EIGHT_GB_PROVEN)
        for gb in (8, 10, 11):
            with self.subTest(gb=gb):
                text = runner([card(gb)])._vram_refusal(self.banded(100.0))
                self.assertEqual(text, f'The Large-image engine has not yet been measured on {gb} GB graphics cards. An 8,000 × '
                                       '8,000 px result needs the Large-image engine on this computer.')
        self.assertEqual(BANDED_8GB, 'The Large-image engine has not yet been measured on 8 GB graphics cards.')   # 5.0.2's words
        with mock.patch.object(vram_model, 'EIGHT_GB_PROVEN', True):     # once R5's 8 GB emulation passes
            for gb in (8, 10, 11):
                with self.subTest(gb=gb, proven=True):
                    r = runner([card(gb)])
                    self.assertIsNone(r._vram_refusal(self.banded(530.0)))
                    a = 'An' if gb in (8, 11) else 'A'
                    self.assertTrue(r._vram_refusal(self.banded(545.0)).startswith(
                        f'{a} {gb} GB graphics card can render up to 537 MP with the Large-image engine; an 8,000 × 8,000 '
                        'px result needs 545 MP.'))                       # the 8 GB class's limit, not 671 or 738 MP

    def test_cards_between_and_above_the_classes_take_the_class_below(self):
        r20 = runner([card(20)])
        self.assertIsNone(r20._vram_refusal(self.banded(1070.0)))
        self.assertTrue(r20._vram_refusal(self.banded(1080.0)).startswith(
            'A 20 GB graphics card can render up to 1,074 MP with the Large-image engine; an 8,000 × 8,000 px result needs '
            '1,080 MP.'))
        r48 = runner([card(48)])
        self.assertIsNone(r48._vram_refusal(self.banded(2140.0)))
        self.assertTrue(r48._vram_refusal(self.banded(2155.0)).startswith('A 48 GB graphics card can render up to 2,147 MP'))

    def test_the_banded_vram_model(self):
        st = stage(256.0, 1024.0)
        self.assertAlmostEqual(vram_model.banded_vram_gb(st, 'reference'), banded_plan.banded_vram_gb(st))
        self.assertAlmostEqual(vram_model.banded_vram_gb(st, 'reference'), 15.5 + 4 * G * 1024.0)
        self.assertLess(vram_model.banded_vram_gb(st, 'balanced'), vram_model.usable_gb(CARDS[16]))

    def test_the_offer_after_an_out_of_memory_error_stays_off(self):
        self.assertFalse(banded_plan.OFFER_AFTER_OOM)


if __name__ == '__main__':
    unittest.main()
