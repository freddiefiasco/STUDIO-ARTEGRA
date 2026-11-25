"""Halo Reduction (beta)'s clamp (node_pack/claude_banded/bxf/dehalo.py, in its row bands) read by the halo tools' metric
(halo_metric.py, through tools/proof/halo_grid.load) on synthetic cards: a 2x and a 4x output whose edges carry rims (a
sharpened bicubic with grain, the shape of a rendered halo). With the clamp the rims read lower (rim_max p90 and p50) on the
same edges, and a clean output (no rim) keeps its reading. Acutance is round 2's robust A2 (acut2.py of the round-2 tools,
CU_HALO2_TOOLS; round 1's mean 10-90 rise reads the removed overshoot itself as a softer edge, HALO-FIX.md D3): the 30-70 %
rise's median is unchanged (rule 2's A1 floor, 0.003 px) at 2x and 4x and the 10-90 % rise's at 2x (A3, 0.010 px); at 4x
the 10-90 % median on this card grows by about 0.05 px, over A3's floor, which is round 2's own sub-floor-tail finding at 4x
(HALO-FIX.md D-K) on a harsher stand-in, so here it is pinned below 0.10 px, not passed. This is the measure round 2 used, on
synthetic edges only (the real-render evidence and its limits are HALO-FIX.md's); the pixels themselves are round 2's:
tests/worker/test_halo_reduction.py. Needs the halo tools' own interpreter (numpy, scipy, opencv, Pillow, scikit-image);
skipped unless CU_HALO_TOOLS names round 1's tools folder (and the A2 test unless CU_HALO2_TOOLS names round 2's):
    CU_HALO_TOOLS=<folder> CU_HALO2_TOOLS=<folder> python -B -m unittest tests.proof.test_halo_reduction_metric"""
import importlib.util
import math
import os
import unittest
from pathlib import Path

import numpy as np

HALO = os.environ.get('CU_HALO_TOOLS')
HALO2 = os.environ.get('CU_HALO2_TOOLS')
HAVE = bool(HALO) and all(importlib.util.find_spec(m) is not None for m in ('scipy', 'cv2', 'skimage'))
ROOT = Path(__file__).resolve().parents[2]
SRC = 192


def dehalo():
    spec = importlib.util.spec_from_file_location('cu_test_metric_dehalo', ROOT / 'node_pack' / 'claude_banded' / 'bxf' / 'dehalo.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def card(seed=2):
    """A source of SRC x SRC px (u8): straight steps at several angles between flat tones, and a thin dark line."""
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:SRC, 0:SRC].astype(np.float32)
    img = np.full((SRC, SRC), 0.30, np.float32)
    for ang, off, tone in ((12.0, 40.0, 0.78), (-25.0, 110.0, 0.55), (70.0, 150.0, 0.18)):
        a = math.radians(ang)
        img = np.where(x * math.cos(a) + y * math.sin(a) > off + 0.3, tone, img)
    img[:, SRC // 2:SRC // 2 + 1] = 0.05
    rgb = np.repeat(img[..., None], 3, -1) * np.array([1.0, 0.97, 0.92], np.float32)
    rgb += rng.normal(0, 0.003, rgb.shape).astype(np.float32)
    return np.clip(rgb * 255 + 0.5, 0, 255).astype(np.uint8)


def rendered(src, f, rims=True, seed=3):
    """The source's bicubic at f x, sharpened (an overshoot at every edge) with grain; rims False: the bilinear alone."""
    from PIL import Image
    from scipy.ndimage import gaussian_filter
    n = SRC * f
    a = np.asarray(Image.fromarray(src).resize((n, n), Image.BICUBIC if rims else Image.BILINEAR)).astype(np.float32) / 255
    if not rims:
        return a
    rng = np.random.default_rng(seed)
    out = a + 1.0 * (a - gaussian_filter(a, (0.6 * f, 0.6 * f, 0))) + rng.normal(0, 0.004, a.shape).astype(np.float32)
    return np.clip(out, 0, 1).astype(np.float32)


def clamp(src, out, f):
    """The option on this output: post's clamp on its luma (its change carried, as the finish carries it), then the final
    clamp, both in 288-row bands with the clamp's reach; the reference is the bilinear of the source's luma."""
    D = dehalo()
    S = src.astype(np.float32) / 255
    H, W = out.shape[:2]
    Ys, D0, D2 = (np.zeros(S.shape[:2], np.float32) for _ in range(3))
    D.source_planes(lambda a, b: S[a:b], Ys, D0, D2)
    Yref = D._bilinear_rows(Ys, H, W)
    Y2 = D.luma(out).astype(np.float32)
    Y2c = D.clamp_luma_bands(Y2, Yref, float(f), Ys, np.zeros_like(Y2), 288)
    dY = (Y2c - Y2).astype(np.float32)
    mid = np.clip(out + dY[..., None], 0, 1).astype(np.float32)
    r0, rf = np.zeros_like(out), np.zeros_like(out)
    which, st = D.final_clamp_bands(mid, Yref, float(f), Ys, D0, D2, dY, r0, rf, 288)
    return {'out': mid, 'res0': r0, 'resf': rf}[which], st


def u8(a):
    return np.clip(np.round(np.asarray(a) * 255), 0, 255).astype(np.uint8)


@unittest.skipUnless(HAVE, 'the halo tools are not available here (set CU_HALO_TOOLS; scipy, cv2, skimage)')
class TheMetricReadsTheClamp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.proof import halo_grid
        cls.halo_grid = halo_grid
        cls.hm, cls.info = halo_grid.load(HALO)
        cls.src = card()

    def summary(self, out):
        rep, _, _ = self.halo_grid.measure(self.hm, self.src.astype(np.float32) / 255, u8(out).astype(np.float32) / 255,
                                           want_detail=False)
        return rep['summary']

    def test_the_rims_read_lower(self):
        for f in (2, 4):
            with self.subTest(f=f):
                off = rendered(self.src, f)
                on, st = clamp(self.src, off, f)
                self.assertTrue(st['edges_of_geometry'])
                self.assertGreater(st['pixels_changed'], 0)
                a, b = self.summary(off), self.summary(on)
                self.assertGreater(a['rim_max']['n'], 5)
                self.assertEqual(a['rim_max']['n'], b['rim_max']['n'])              # the same edges, read on both
                self.assertGreater(a['rim_max']['p90'], 2.0)                        # the card's rims are visible
                self.assertLess(b['rim_max']['p90'], a['rim_max']['p90'] - 1.0)
                self.assertLess(b['rim_max']['p50'], a['rim_max']['p50'])

    @unittest.skipUnless(HALO2, 'the round-2 tools (acut2.py) are not named (CU_HALO2_TOOLS)')
    def test_a2_the_edges_ramps(self):
        spec = importlib.util.spec_from_file_location('cu_test_acut2', Path(HALO2) / 'acut2.py')
        A2 = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(A2)
        for f, r1090_max in ((2, 0.010), (4, 0.10)):
            with self.subTest(f=f):
                off = rendered(self.src, f)
                on, _ = clamp(self.src, off, f)
                r = A2.run(self.src, {'base': u8(off), 'cand': u8(on)}, base='base', lines=False, detail=False)
                pc = r['paired']['cand']
                self.assertGreater(pc['r3070']['n'], 20)
                self.assertLessEqual(pc['r3070']['median'], 0.003, pc['r3070'])
                self.assertLessEqual(pc['r1090']['median'], r1090_max, pc['r1090'])
                self.assertLess(r['per_image']['cand']['env_p90'], r['per_image']['base']['env_p90'] - 3.0)

    def test_a_clean_output_keeps_its_reading(self):
        clean = rendered(self.src, 2, rims=False)
        on, st = clamp(self.src, clean, 2)
        a, b = self.summary(clean), self.summary(on)
        self.assertLess(abs(b['rim_max']['p90'] - a['rim_max']['p90']), 0.3)
        self.assertLess(int(np.count_nonzero(u8(on) != u8(clean))), clean.size // 100)


if __name__ == '__main__':
    unittest.main()
