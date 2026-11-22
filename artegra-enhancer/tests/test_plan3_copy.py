"""The Large-image planner's refusal words (engine/banded_plan.py; build wave 3, A10, plan-chk-2 and the recorded copy
findings): every refusal names the Large-image engine and the size, a computer's memory class says GB, and an article before
a number follows how the number is spoken. Sizes only."""
import itertools
import re
import unittest
from unittest import mock

from engine import banded_plan as B
from engine import planner

PROVEN = {k: 10_000.0 for k in B.BANDED_PROVEN_MP}
SIDES = (64, 200, 600, 1280, 2188, 3500, 4000, 5333, 9000)


def refusals():
    out = []
    for w, h, f in itertools.product(SIDES, SIDES, (2, 3, 4, 6, 8)):
        for cap in (30.0, 45.2, 59.0, 122.2):
            for mode in ('redux', 'fast'):
                for proven in (None, PROVEN):
                    for bolt in (False, True):
                        with mock.patch.object(B, 'BOLT_BANDED', bolt):
                            p = B.plan_banded(w, h, f, cap, mode=mode, proven=proven)
                        if not p.ok:
                            out.append(((w, h, f, cap, mode), p))
    for w, h, f in ((2048, 2048, 2), (3500, 2188, 4), (3500, 2188, 2), (64, 3000, 2), (3000, 64, 2), (4000, 4000, 2)):
        c = planner.plan(w, h, f, ram_cap_gb=122.2)
        for cap in (30.0, 45.2, 59.0):
            for mode in ('redux', 'fast'):
                p = B.plan_forced(c, cap, mode=mode)
                if not p.ok:
                    out.append(((w, h, f, cap, mode, 'forced'), p))
    return out


class EveryRefusalNamesTheEngineAndTheSize(unittest.TestCase):
    def test_over_a_grid(self):
        seen = set()
        for key, p in refusals():
            r = p.reason
            seen.add(re.sub(r'[\d,.]+', '<>', r))
            self.assertIn('Large-image engine', r, key)
            sizes = [f'{W:,} × {H:,} px' for W, H in (p.output_size, p.input_size) if (W, H) != (0, 0)]
            self.assertTrue(any(x in r for x in sizes), (key, r))          # the result's size, or the image's own
            self.assertNotIn('proven', r, key)
            self.assertNotIn('over the cap', r, key)
            for m in re.finditer(r'\bon an? (\S+) computer', r):
                self.assertTrue(m.group(1).endswith('GB') or m.group(0) == 'on this computer', (key, r))
            self.assertIsNone(re.search(r'\ba 8|\ba 11\b|\ba 18\b|\ba 80|\ba 11,|\ba 18,', r), (key, r))
        self.assertGreater(len(seen), 10)

    def test_the_articles(self):
        for n, want in ((8, 'an'), (11, 'an'), (18, 'an'), (80, 'an'), (88, 'an'), (800, 'an'), (8000, 'an'),
                        (11000, 'an'), (18000, 'an'), (110, 'a'), (118, 'a'), (1100, 'a'), (490, 'a'), (64, 'a'),
                        (1, 'a'), (275.7, 'a'), (7.9, 'an')):
            self.assertEqual(B._a(n), want, n)

    def test_the_forced_over_cap_refusal_names_the_size(self):
        """plan-chk-2: the developer comparison run's memory refusal says what it would make and in GB."""
        c = planner.plan(3500, 2188, 4, ram_cap_gb=122.2)
        p = B.plan_forced(c, 59.0)                         # tier 3 (no table): the whole finish of its 122.5 MP pass
        self.assertFalse(p.ok)
        self.assertIn('developer comparison run', p.reason)
        self.assertRegex(p.reason, r'needs about \d+ GB of memory with the Large-image engine to make 14,000 × 8,752 px, '
                                   r'more than the 59 GB it may use on this computer\.')

    def test_bolt_refusals_point_to_redux_for_the_size(self):
        with mock.patch.dict(B.BANDED_PROVEN_MP, PROVEN):
            p = B.plan_banded(3500, 2188, 2, 59.0, mode='fast')
        self.assertEqual(p.reason, f'{B.BOLT_UNAVAILABLE} Choose Redux to make 7,000 × 4,376 px.')
        with mock.patch.dict(B.BANDED_PROVEN_MP, PROVEN), mock.patch.object(B, 'BOLT_BANDED', True):
            p = B.plan_banded(3500, 2188, 4, 59.0, mode='fast')
            self.assertEqual(p.reason, 'Bolt upscales 2× only. Choose Redux to make 14,000 × 8,752 px with the Large-image '
                                       'engine.')
            p = B.plan_banded(4000, 4000, 2, 59.0, mode='fast')
            self.assertEqual(p.reason, 'Bolt works on images up to about 9 MP. Choose Redux to make 8,000 × 8,000 px with '
                                       'the Large-image engine.')


if __name__ == '__main__':
    unittest.main()
