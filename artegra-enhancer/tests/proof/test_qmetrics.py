"""tools/proof/qmetrics.py on synthetic passes: Q4 reads 0 on a faithful pass 3 and the drift of a tinted one; Q5 flags
invented texture in a smooth region and not a clean Lanczos pass; Q11's rule."""
import unittest

import numpy as np

from tools.proof import colour, qmetrics


def pass2(h=256, w=320, seed=0):
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    img = np.stack([0.4 + 0.3 * y / h, 0.5 + 0.2 * x / w, 0.6 - 0.2 * y / h], -1)
    tex = colour.gaussian(rng.standard_normal((h, w)), 1.5)[..., None] * 0.04
    img[:, w // 2:] += tex[:, w // 2:]                     # left half smooth, right half textured
    return np.clip(np.round(img * 255), 0, 255).astype(np.uint8)


class Q4(unittest.TestCase):
    def test_faithful_pass_3_reads_zero(self):
        p2 = pass2()
        p3 = p2.repeat(2, 0).repeat(2, 1)                  # every pass-2 pixel as a 2 x 2 block: same block means
        s = qmetrics.block_de(p3, p2)
        self.assertLess(s['p99'], 1e-3)
        self.assertEqual(s['n_blocks'], (256 // 64) * (320 // 64))

    def test_a_tint_is_measured_and_judged_against_the_bound(self):
        p2 = pass2()
        p3 = np.clip(p2.repeat(2, 0).repeat(2, 1).astype(np.int16) + np.array([6, 0, -6]), 0, 255).astype(np.uint8)
        s = qmetrics.block_de(p3, p2)
        self.assertGreater(s['p50'], 1.0)
        self.assertFalse(qmetrics.q4(p3, p2, {'p50': 0.5, 'p99': 1.0})['pass'])
        self.assertTrue(qmetrics.q4(p3, p2, {'p50': s['p50'], 'p99': s['p99']})['pass'])

    def test_non_whole_block_is_refused(self):
        with self.assertRaises(ValueError):
            qmetrics.block_de(np.zeros((100, 100, 3), np.uint8), np.zeros((70, 70, 3), np.uint8))


class Q5(unittest.TestCase):
    def setUp(self):
        self.p2 = pass2()
        self.up = qmetrics.lanczos_up(self.p2, (640, 512))

    def test_clean_lanczos_pass_flags_nothing(self):
        r = qmetrics.q5(self.up, self.up, calib=0.05)
        self.assertEqual(r['n_flagged'], 0)
        self.assertGreater(r['stats']['n_smooth'], 0)

    def test_invented_texture_in_a_smooth_region_is_flagged_with_its_box(self):
        rng = np.random.default_rng(5)
        p3 = self.up.astype(np.float32)
        p3[96:192, 64:192] += rng.normal(0, 10, (96, 128, 1))   # fine new texture inside the smooth left half
        p3 = np.clip(np.round(p3), 0, 255).astype(np.uint8)
        calib = qmetrics.q5_calibrate(self.up, self.up)
        r = qmetrics.q5(p3, self.up, calib, crops=[{'class': 'plaster_sky_window_corners', 'box': [64, 96, 192, 192]},
                                                   {'class': 'water', 'box': [400, 300, 600, 480]}])
        self.assertGreater(r['n_flagged'], 0)
        for b in r['flagged']:
            x0, y0, x1, y1 = b['box']
            self.assertTrue(64 <= x0 and x1 <= 192 + 32 and 96 - 32 <= y0 and y1 <= 192 + 32, b)
        self.assertGreater(r['crops'][0]['flagged_blocks'], 0)
        self.assertEqual(r['crops'][1]['flagged_blocks'], 0)
        with self.assertRaises(ValueError):
            qmetrics.q5(p3, self.up, calib, crops=[{'class': 'cats', 'box': [0, 0, 32, 32]}])

    def test_banded_blocks_equal_whole(self):
        E1, S1 = qmetrics.dog_blocks(self.up, band_rows=64)
        E2, S2 = qmetrics.dog_blocks(self.up, band_rows=512)
        np.testing.assert_allclose(E1, E2, rtol=1e-6, atol=1e-9)
        np.testing.assert_allclose(S1, S2, rtol=1e-6, atol=1e-9)


class Q11(unittest.TestCase):
    def rep(self, rim, glow):
        return {'summary': {'rim_max': {'p95': rim}, 'glow_abs': {'p95': glow}}}

    def test_within_the_chain_plus_its_noise(self):
        r = qmetrics.q11(self.rep(5.2, 2.0), self.rep(5.0, 2.1), self.rep(4.7, 2.0))
        self.assertTrue(r['pass'], r)
        r = qmetrics.q11(self.rep(5.4, 2.0), self.rep(5.0, 2.1), self.rep(4.7, 2.0))
        self.assertFalse(r['pass'])
        r = qmetrics.q11({'summary': {}}, self.rep(5.0, 2.1), self.rep(4.7, 2.0))
        self.assertFalse(r['pass'])


if __name__ == '__main__':
    unittest.main()
