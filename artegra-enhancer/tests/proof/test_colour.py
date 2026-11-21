"""tools/proof/colour.py: CIEDE2000 on published reference pairs, L* of known greys, the Gaussian against a direct sum."""
import unittest

import numpy as np

from tools.proof import colour

# CIEDE2000 reference pairs (Sharma, Wu and Dalal 2005, Table 1): L1, a1, b1, L2, a2, b2, dE00
SHARMA = [
    (50.0, 2.6772, -79.7751, 50.0, 0.0, -82.7485, 2.0425),
    (50.0, 3.1571, -77.2803, 50.0, 0.0, -82.7485, 2.8615),
    (50.0, 2.8361, -74.0200, 50.0, 0.0, -82.7485, 3.4412),
    (50.0, 0.0, 0.0, 50.0, -1.0, 2.0, 2.3669),
    (50.0, 2.5, 0.0, 73.0, 25.0, -18.0, 27.1492),
    (50.0, 2.5, 0.0, 61.0, -5.0, 29.0, 22.8977),
    (50.0, 2.5, 0.0, 56.0, -27.0, -3.0, 31.9030),
    (50.0, 2.5, 0.0, 58.0, 24.0, 15.0, 19.4535),
    (50.0, 2.5, 0.0, 50.0, 3.1736, 0.5854, 1.0000),
]


class Ciede2000(unittest.TestCase):
    def test_reference_pairs(self):
        t = np.array(SHARMA)
        de = colour.ciede2000(t[:, 0:3], t[:, 3:6])
        np.testing.assert_allclose(de, t[:, 6], atol=1e-4)

    def test_symmetric_and_zero(self):
        t = np.array(SHARMA)
        np.testing.assert_allclose(colour.ciede2000(t[:, 3:6], t[:, 0:3]), t[:, 6], atol=1e-4)
        self.assertEqual(float(np.abs(colour.ciede2000(t[:, 0:3], t[:, 0:3])).max()), 0.0)


class Lightness(unittest.TestCase):
    def test_black_white_and_mid_grey(self):
        img = np.array([[[0, 0, 0], [255, 255, 255], [119, 119, 119]]], np.uint8)
        L = colour.lstar(img)
        self.assertAlmostEqual(float(L[0, 0]), 0.0, places=4)
        self.assertAlmostEqual(float(L[0, 1]), 100.0, places=3)
        self.assertAlmostEqual(float(L[0, 2]), 50.0, delta=0.3)   # sRGB 119 is about L* 50

    def test_float_and_u8_agree(self):
        u = np.arange(256, dtype=np.uint8).reshape(16, 16, 1).repeat(3, -1)
        np.testing.assert_allclose(colour.lstar(u), colour.lstar(u.astype(np.float32) / 255), atol=1e-4)

    def test_lab_of_neutral_has_no_chroma(self):
        lab = colour.lab_from_linear(colour.linear_from_rgb(np.full((2, 2, 3), 180, np.uint8)))
        self.assertLess(float(np.abs(lab[..., 1:]).max()), 1e-3)


class Gaussian(unittest.TestCase):
    def test_against_direct_sum_with_symmetric_border(self):
        rng = np.random.default_rng(1)
        a = rng.random((40, 33)).astype(np.float32)
        s = 1.7
        got = colour.gaussian(a, s)
        r = int(4.0 * s + 0.5)
        x = np.arange(-r, r + 1)
        k = np.exp(-0.5 * (x / s) ** 2)
        k /= k.sum()
        p = np.pad(a.astype(np.float64), r, mode='symmetric')
        want = np.zeros_like(a, np.float64)
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                want += k[dy + r] * k[dx + r] * p[r + dy:r + dy + a.shape[0], r + dx:r + dx + a.shape[1]]
        np.testing.assert_allclose(got, want, atol=1e-5)

    def test_constant_stays_constant(self):
        a = np.full((20, 20), 0.25, np.float32)
        np.testing.assert_allclose(colour.gaussian(a, 3.0), a, atol=1e-6)


class BlockMeans(unittest.TestCase):
    def test_block_mean_and_partial_edge(self):
        a = np.arange(5 * 6, dtype=np.float64).reshape(5, 6, 1)
        m = colour.block_mean(a, 2)
        self.assertEqual(m.shape, (2, 3, 1))           # only whole blocks
        self.assertAlmostEqual(float(m[0, 0, 0]), (0 + 1 + 6 + 7) / 4)


if __name__ == '__main__':
    unittest.main()
