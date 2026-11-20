"""The region-grid wrapper of the halo tools' metric and M1-M6 on synthetic test cards built here: a clean step reads near 0,
a Lanczos step rings, a low-frequency-transfer step glows, a blurred step loses acutance; whole and grid measurements agree;
the comparison flags the haloed output and passes an identical one. The halo tools are read by path and need their own
interpreter (numpy, scipy, opencv, Pillow, scikit-image); skipped unless CU_HALO_TOOLS names their folder:
    CU_HALO_TOOLS=<halo tools folder> python -B -m unittest tests.proof.test_halo_grid     (from the artegra-enhancer folder)"""
import importlib.util
import math
import os
import tempfile
import unittest
from pathlib import Path

import numpy as np

HALO = os.environ.get('CU_HALO_TOOLS')
HAVE = bool(HALO) and all(importlib.util.find_spec(m) is not None for m in ('scipy', 'cv2', 'skimage'))
F = 2
SRC = 192


def _f_inv(t):
    d = 6.0 / 29.0
    return np.where(t > d, t ** 3, 3 * d * d * (t - 4.0 / 29.0))


def _srgb(lin):
    lin = np.clip(lin, 0, 1)
    return np.where(lin <= 0.0031308, 12.92 * lin, 1.055 * lin ** (1 / 2.4) - 0.055)


def render(f, shift=0.0, angle=30.0, ss=4, L_dark=35.0, L_bright=80.0):
    """A straight step through the card's centre at `angle`, rendered at f x the source size with ss x ss box
    anti-aliasing in linear light; neutral grey, sRGB float. shift moves the edge along its normal (source px)."""
    n = SRC * f
    a = math.radians(angle)
    nx, ny = math.cos(a), math.sin(a)
    sub = (np.arange(ss) + 0.5) / ss
    xs = (np.arange(n)[:, None] + sub[None, :]).ravel() / f
    X, Y = np.meshgrid(xs, xs)
    d = (X - SRC / 2 - 0.3) * nx + (Y - SRC / 2) * ny - shift
    L = np.where(d >= 0, L_bright, L_dark)
    Ylin = _f_inv((L + 16.0) / 116.0).reshape(n, ss, n, ss).mean((1, 3))
    g = _srgb(Ylin).astype(np.float32)
    return np.repeat(g[..., None], 3, -1)


def area(img, f):
    from tools.proof import colour
    lin = colour.linear_from_rgb(img)
    return _srgb(colour.block_mean(lin, f)).astype(np.float32)


def u8(x):
    return np.clip(np.round(np.asarray(x) * 255), 0, 255).astype(np.uint8)


@unittest.skipUnless(HAVE, 'needs CU_HALO_TOOLS (the halo tools folder) and their interpreter (scipy, opencv, scikit-image)')
class Cards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PIL import Image
        from scipy import ndimage as ndi
        from tools.proof import halo_grid
        cls.hm, cls.info = halo_grid.load(HALO)
        cls.halo_grid = halo_grid
        truth = render(F)
        cls.src = u8(area(truth, F))
        cls.clean = u8(truth)
        sf = cls.src.astype(np.float32) / 255
        cls.lanczos = u8(np.stack([np.asarray(Image.fromarray(sf[..., c], 'F').resize((SRC * F, SRC * F), Image.LANCZOS))
                                   for c in range(3)], -1))
        mis = render(F, shift=6.0 / F)
        g = lambda x: np.stack([ndi.gaussian_filter(x[..., c], 32.0, mode='reflect') for c in range(3)], -1)
        cls.glow = u8(np.clip(truth + g(mis) - g(truth), 0, 1))
        cls.blur = u8(np.stack([ndi.gaussian_filter(truth[..., c], 2.0) for c in range(3)], -1))
        cls.m = {k: cls.halo_grid.measure(cls.hm, cls.src, getattr(cls, k), want_detail=False)
                 for k in ('clean', 'lanczos', 'glow', 'blur')}

    def s(self, name, key, stat='p50'):
        return self.m[name][0]['summary'][key].get(stat)

    def test_version_and_sha_are_recorded(self):
        self.assertTrue(self.info['version'].startswith('halo-metric'))
        self.assertEqual(len(self.info['sha256']), 64)
        self.assertEqual(self.m['clean'][0]['version'], self.info['version'])
        self.assertEqual(self.m['clean'][0]['mode'], 'whole')

    def test_clean_step_reads_near_zero(self):
        self.assertGreaterEqual(self.m['clean'][0]['summary']['status']['ok'], 4)
        self.assertLess(self.s('clean', 'rim_max', 'p90'), 0.5)
        self.assertLess(self.s('clean', 'glow_abs', 'p90'), 0.3)

    def test_lanczos_step_rings(self):
        self.assertGreater(self.s('lanczos', 'rim_max'), self.s('clean', 'rim_max') + 1.0)

    def test_lf_transfer_step_glows(self):
        self.assertGreater(self.s('glow', 'glow_abs'), self.s('clean', 'glow_abs') + 0.5)

    def test_blurred_step_loses_acutance(self):
        self.assertGreater(self.s('blur', 'rise'), self.s('clean', 'rise') + 1.0)
        self.assertLess(self.s('blur', 'slope'), self.s('clean', 'slope'))
        self.assertLess(self.s('blur', 'rim_max', 'p90'), 1.0)

    def test_grid_agrees_with_whole_and_pairs_by_region_and_segment(self):
        rep_w, A_w, _ = self.m['lanczos']
        rep_g, A_g, _ = self.halo_grid.measure(self.hm, self.src, self.lanczos, grid_above_mp=0.0, core_src=64,
                                               want_detail=False)
        self.assertEqual(rep_g['mode'], 'grid')
        self.assertGreater(rep_g['n_regions'], 4)
        ok_w, ok_g = rep_w['summary']['status']['ok'], rep_g['summary']['status']['ok']
        self.assertGreater(ok_g, 0.6 * ok_w)
        self.assertAlmostEqual(rep_g['summary']['rim_max']['p50'], rep_w['summary']['rim_max']['p50'], delta=0.6)
        rep_c, A_c, _ = self.halo_grid.measure(self.hm, self.src, self.clean, grid_above_mp=0.0, core_src=64,
                                               want_detail=False)
        ia, ib = self.halo_grid.pair_index(A_g, A_c)
        self.assertGreater(ia.size, 4)
        np.testing.assert_allclose(A_g['cx'][ia], A_c['cx'][ib], atol=1e-3)
        self.assertEqual(rep_g['edge_set_hash'], rep_c['edge_set_hash'])

    def test_plane_output_is_read_by_regions(self):
        from engine import planes
        with tempfile.TemporaryDirectory() as d:
            p = planes.from_array(Path(d) / 'out.plane', self.lanczos)
            rep, A, _ = self.halo_grid.measure(self.hm, self.src, {'kind': 'plane', 'path': str(p.path)}, core_src=64,
                                               want_detail=False)
            rep_a, A_a, _ = self.halo_grid.measure(self.hm, self.src, self.lanczos, grid_above_mp=0.0, core_src=64,
                                                   want_detail=False)
            del p
        self.assertEqual(rep['mode'], 'grid')
        self.assertEqual(rep['summary']['rim_max'], rep_a['summary']['rim_max'])

    def test_comparison_flags_the_haloed_output_and_passes_an_identical_one(self):
        from tools.proof import metrics, seams
        pos = {'rows': {'band': [100, 200]}, 'cols': {'strip': [128]}}
        rng = np.random.default_rng(3)
        clean_b = np.clip(self.clean.astype(np.int16) + rng.integers(-1, 2, self.clean.shape), 0, 255).astype(np.uint8)
        b = {k: metrics.bundle(self.hm, self.src, v, pos) for k, v in (('a', self.clean), ('b', clean_b),
                                                                     ('l', self.lanczos))}
        r = metrics.compare_case(b['a'], b['l'], b['b'], self.info.get('noise_floor', {}).get('floors'))
        self.assertFalse(r['pass_metrics'])
        self.assertTrue(any(x['metric'] == 'M1' and x['key'] == 'rim_max' for x in r['worse_rows']), r['worse_rows'])
        same = metrics.compare_case(b['a'], dict(b['a']), b['b'])
        self.assertTrue(same['identical'])
        self.assertTrue(same['pass_metrics'])


if __name__ == '__main__':
    unittest.main()
