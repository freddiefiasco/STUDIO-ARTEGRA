"""tools/proof/tiers.py: design 7.3's tier 0 and tier 1 rules on synthetic 8-bit outputs."""
import unittest

import numpy as np

from tools.proof import tiers


def base():
    return np.random.default_rng(0).integers(10, 240, (96, 80, 3)).astype(np.uint8)


class Tiers(unittest.TestCase):
    def test_identical_is_tier_0(self):
        a = base()
        r = tiers.tier(a, a.copy(), F=0)
        self.assertEqual((r['tier'], r['pass']), (0, True))

    def test_few_scattered_one_level_values_within_F_are_tier_1(self):
        a = base()
        b = a.copy()
        for y, x in ((5, 5), (40, 60), (70, 11)):
            b[y, x, 1] += 1
        r = tiers.tier(a, b, F=3, rows=[32, 64], cols=[40])
        self.assertEqual((r['tier'], r['pass']), (1, True), r)

    def test_each_tier_1_rule_fails_on_its_own(self):
        a = base()
        over_f = a.copy()
        over_f[5, 5, 0] += 1
        over_f[50, 50, 0] += 1
        self.assertEqual(tiers.tier(a, over_f, F=1)['fails'], ['count'])
        two = a.copy()
        two[5, 5, 0] += 2
        self.assertEqual(tiers.tier(a, two, F=10)['fails'], ['max_abs'])
        blob = a.copy()
        for y, x in ((20, 20), (20, 21), (21, 21), (22, 22), (23, 23)):     # 8-connected, 5 px
            blob[y, x, 2] += 1
        r = tiers.tier(a, blob, F=10)
        self.assertEqual(r['fails'], ['groups'])
        self.assertEqual(r['checks']['largest_group_px'], 5)
        row = a.copy()
        row[64, 3, 0] += 1
        self.assertEqual(tiers.tier(a, row, F=10, rows=[64])['fails'], ['structure'])
        one = a.copy()
        one[10, 10, 0] += 1
        r = tiers.tier(a, one, F=10, flips=[{'kind': 'island', 'box': [1, 2, 3, 4]}])
        self.assertEqual(r['fails'], ['flips'])

    def test_four_pixel_group_is_allowed(self):
        a = base()
        b = a.copy()
        for y, x in ((20, 20), (20, 21), (21, 21), (22, 22)):
            b[y, x, 2] += 1
        self.assertTrue(tiers.tier(a, b, F=10)['pass'])

    def test_shape_mismatch_fails(self):
        a = base()
        self.assertFalse(tiers.tier(a, a[:-1], F=0)['pass'])

    def test_groups_over(self):
        largest, big, boxes = tiers.groups_over([(0, 0), (1, 1), (5, 5), (5, 6), (6, 6), (7, 7), (8, 8)], limit=4)
        self.assertEqual((largest, big, boxes), (5, 1, [[5, 5, 9, 9]]))


if __name__ == '__main__':
    unittest.main()
