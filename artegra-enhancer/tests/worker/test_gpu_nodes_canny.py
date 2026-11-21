"""CUCannyPlane (node_pack/claude_banded/canny_plane.py) against ClaudeCannyTiled.run itself (compiled from
node_pack/claude_creative/__init__.py without importing the classic pack), with the real kornia and scipy, on synthetic
canvases: u8 canvas planes (the classic's canvas is the Lanczos output, float32(k)/255) and float32 canvas planes (k = 4,
where the classic's canvas is the x4 output, a BHWC view of NCHW memory), odd sizes, components across tile borders, the
production 2048 px tile and small tiles that put many borders in a small image: 0 differing edge values.
CPU only. Skipped where torch, kornia or scipy is missing:
    python -B -m unittest tests.worker.test_gpu_nodes_canny   (from the artegra-enhancer folder)."""
import ast
import importlib.util
import tempfile
import unittest
from pathlib import Path

import numpy as np

from engine import planes
from tests import test_gpu_nodes_helpers as H

HAVE = all(importlib.util.find_spec(m) is not None for m in ('torch', 'kornia', 'scipy'))


def classic_canny_run():
    import torch
    src = (H.ROOT / 'node_pack' / 'claude_creative' / '__init__.py').read_text(encoding='utf8')
    tree = ast.parse(src)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'ClaudeCannyTiled')
    fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'run')
    g = {'torch': torch}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), 'claude_creative/__init__.py', 'exec'), g)
    return g['run']


def canvas(h, w, seed):
    """A synthetic render: hard-edged blocks and thin lines (geometry), a soft gradient, texture noise, as u8."""
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    img = 0.25 + 0.3 * (x / w) + 0.1 * np.sin(y / 23.0)
    for _ in range(40):
        y0, x0 = rng.integers(0, h), rng.integers(0, w)
        hh, ww = rng.integers(4, max(5, h // 3)), rng.integers(4, max(5, w // 3))
        img[y0:y0 + hh, x0:x0 + ww] += rng.uniform(-0.35, 0.35)
    img += 0.25 * (((x + 2 * y) % 257) < 2)
    rgb = np.stack([img, img * 0.9 + 0.05, img[::-1] * 0.8], -1) + rng.normal(0, 0.02, (h, w, 3))
    return np.clip(np.round(rgb * 255), 0, 255).astype(np.uint8)


@unittest.skipUnless(HAVE, 'needs torch, kornia and scipy (run on the worker runtime)')
class CannyPlaneAgainstClaudeCannyTiled(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch
        cls.torch = torch
        cls.run_classic = staticmethod(classic_canny_run())
        cls.cp = H.module('canny_plane')
        cls.pack = H.load_pack()

    def both(self, plane_arr, img_classic, tile):
        """plane_arr: the canvas plane's data (u8, or float32 at k = 4); img_classic: the classic node's IMAGE."""
        torch = self.torch
        hw = plane_arr.shape[:2]
        want = self.run_classic(None, img_classic, 0.2, 0.45, tile, device=torch.device('cpu'))[0]
        self.assertEqual(tuple(want.shape), (1,) + hw + (3,))
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            cv = planes.from_array(d / 'canvas.plane', plane_arr)
            ref = self.cp.CUCannyPlane().run(self.pack.PlaneRef(cv.path, 'r1'), 0.2, 0.45, tile, str(d / 's0'), 'r1',
                                             device=torch.device('cpu'))[0]
            self.assertEqual(Path(ref.path), d / 's0' / 'edges.plane')
            self.assertEqual(sorted(p.name for p in (d / 's0').iterdir()), ['edges.plane'])     # temporaries removed
            e = planes.validate(ref.path, shape=hw + (1,), dtype='u8')
            got = e.read_rows(0, hw[0])[..., 0]
        w = want[0, ..., 0].numpy()
        self.assertTrue(np.array_equal(want[0, ..., 1].numpy(), w) and np.array_equal(want[0, ..., 2].numpy(), w))
        return got, w

    def test_u8_canvases(self):
        torch = self.torch
        for (h, w, tile) in ((300, 520, 256), (517, 777, 256), (2100, 2300, 2048), (1024, 1032, 2048)):
            u8 = canvas(h, w, h + w)
            img = torch.from_numpy(planes.U8_TO_F32[u8])[None]    # the classic's canvas: Lanczos output float32(k) / 255
            got, want = self.both(u8, img, tile)
            self.assertEqual(int((got != want.astype(np.uint8)).sum()), 0, (h, w, tile))
            self.assertGreater(int(got.sum()), 100, (h, w))

    def test_float_canvases_at_k4(self):
        torch = self.torch
        for (h, w, tile) in ((333, 611, 256), (2052, 2049, 2048)):
            u8 = canvas(h, w, 3 * h + w)
            f = np.clip(planes.U8_TO_F32[u8] * np.float32(1.07) - np.float32(0.031), 0, 1).astype(np.float32)
            nchw = torch.from_numpy(f).permute(2, 0, 1).contiguous()[None]
            img = torch.clamp(nchw.movedim(-3, -1), min=0, max=1.0)  # ClaudeUpscaleModelTiled's output layout
            self.assertFalse(img.is_contiguous())
            got, want = self.both(f, img, tile)
            self.assertEqual(int((got != want.astype(np.uint8)).sum()), 0, (h, w, tile))

    def test_the_node_refuses_without_its_folder(self):
        with tempfile.TemporaryDirectory() as td:
            cv = planes.from_array(Path(td) / 'c.plane', canvas(40, 40, 1))
            with self.assertRaises(ValueError):
                self.cp.CUCannyPlane().run(self.pack.PlaneRef(cv.path, 'r'), 0.2, 0.45, 256, '', 'r')


if __name__ == '__main__':
    unittest.main()
