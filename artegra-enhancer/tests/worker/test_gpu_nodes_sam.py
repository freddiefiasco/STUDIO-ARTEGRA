"""CUSam3DetectLean (node_pack/claude_banded/sam_plane.py) against ComfyUI's own SAM3_Detect (its execute, _refine_mask and
_extract_text_prompts as shipped; the detector's forward as shipped; common_upscale as shipped), with the deterministic SAM 3.1
stand-in of tests/worker/test_sam_lean.py, on u8 input planes of synthetic images: the mask plane is the stock node's mask to
the bit (0 differing values) for float32, bfloat16 and float16, odd and even sizes, one and several prompts, no kept object
and refinement off; the plane is float32 H x W x 1 at <plane_dir>/mask.plane, the float32 view is removed, the lean node is the
classic pack's own class, and CUMaskUnionPlane over two term masks is the stock union.
Skipped where torch or CU_COMFY_SOURCE is missing:
    CU_COMFY_SOURCE=<ComfyUI folder> python -B -m unittest tests.worker.test_gpu_nodes_sam   (from the artegra-enhancer folder)."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from engine import planes
from tests import test_gpu_nodes_helpers as H
from tests.worker import test_sam_lean as _sam_fixtures
from tests.worker.test_sam_lean import COMFY, HAVE_TORCH


@unittest.skipUnless(HAVE_TORCH and COMFY, 'needs torch and CU_COMFY_SOURCE (the runtime ComfyUI folder)')
class SamPlaneAgainstSam3Detect(unittest.TestCase):
    Fixtures = _sam_fixtures.LeanSamAgainstComfyUIsSam3Detect      # its stand-ins (a class attribute: not collected again)

    @classmethod
    def setUpClass(cls):
        import torch
        cls.torch = torch
        cls.Fixtures.setUpClass()
        cls.fx = cls.Fixtures('test_no_kept_object')
        cls.sp = H.module('sam_plane')
        cls.pack = H.load_pack()
        cls.classic = H.fake_classic_pack('cu_fake_classic_for_sam',
                                          mappings={'ClaudeSAM3DetectLean': cls.Fixtures.lean_mod.ClaudeSAM3DetectLean})

    def u8_image(self, h, w, seed):
        f = self.fx.image(h, w, seed)[0].numpy()
        return np.clip(np.round(f * 255), 0, 255).astype(np.uint8)

    def both(self, model, u8, cond, iterations=2):
        torch = self.torch
        img = torch.from_numpy(planes.U8_TO_F32[u8])[None]                # LoadImage's tensor of the stage input
        stock = self.Fixtures.stock_execute(model, img, conditioning=cond, threshold=0.6, refine_iterations=iterations,
                                       individual_masks=False)
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            p = planes.from_array(d / 'input.plane', u8)
            mods = dict(self.Fixtures.modules, cu_fake_classic_for_sam=self.classic)
            with mock.patch.dict(sys.modules, mods):
                ref = self.sp.CUSam3DetectLean().run(model, self.pack.PlaneRef(p.path, 'r1'), cond, 0.6, iterations,
                                                     str(d / 'protect0'), 'r1')[0]
            self.assertEqual(Path(ref.path), d / 'protect0' / 'mask.plane')
            self.assertEqual(sorted(x.name for x in (d / 'protect0').iterdir()), ['mask.plane'])
            m = planes.validate(ref.path, shape=u8.shape[:2] + (1,), dtype='f32').read_rows(0, u8.shape[0])[..., 0]
        return stock[0][0].numpy(), m, ref

    def test_the_mask_is_the_stock_nodes(self):
        torch = self.torch
        n = 0
        for dtype in (torch.float32, torch.bfloat16, torch.float16):
            for (h, w) in ((64, 64), (101, 333), (777, 1001)):
                for seed in (0, 1):
                    want, got, _ = self.both(self.fx.model(dtype, seed=seed), self.u8_image(h, w, seed), self.fx.cond(seed))
                    self.assertEqual(int((want.view(np.uint32) != got.view(np.uint32)).sum()), 0, (dtype, h, w, seed))
                    self.assertGreater(float(got.sum()), 0.0)
                    n += 1
        self.assertEqual(n, 18)

    def test_several_prompts_none_kept_and_no_refinement(self):
        torch = self.torch
        cases = [(self.fx.model(torch.float32, seed=3, hot=6), self.u8_image(300, 520, 3), self.fx.cond(3, multi=(1, 3, 5)), 2),
                 (self.fx.model(torch.float32, seed=4, hot=0), self.u8_image(200, 120, 4), self.fx.cond(4), 2),
                 (self.fx.model(torch.float16, seed=5), self.u8_image(257, 129, 5), self.fx.cond(5), 0)]
        for i, (model, u8, cond, it) in enumerate(cases):
            want, got, _ = self.both(model, u8, cond, it)
            self.assertEqual(int((want.view(np.uint32) != got.view(np.uint32)).sum()), 0, i)
        self.assertEqual(float(self.both(*cases[1][:3])[1].sum()), 0.0)

    def test_the_union_of_term_masks_is_the_stock_union(self):
        torch = self.torch
        u8 = self.u8_image(301, 517, 9)
        wants = [self.both(self.fx.model(torch.float32, seed=seed), u8, self.fx.cond(seed))[0] for seed in (0, 1)]
        with tempfile.TemporaryDirectory() as td:
            rs = [self.pack.PlaneRef(planes.from_array(Path(td) / f'm{i}.plane', w[..., None].astype(np.float32)).path, 'r')
                  for i, w in enumerate(wants)]
            u = self.pack.CUMaskUnionPlane().run(str(Path(td) / 'u'), 'r', mask_1=rs[0], mask_2=rs[1])[0]
            got = u.plane().read_rows(0, 301)[..., 0]
        stock = torch.maximum(torch.from_numpy(wants[0]), torch.from_numpy(wants[1])).numpy()   # ClaudeMaskUnion
        self.assertEqual(int((got != stock).sum()), 0)

    def test_no_classic_lean_node_is_a_plain_error(self):
        empty = H.fake_classic_pack('cu_fake_classic_without_lean')
        with mock.patch.dict(sys.modules, {'cu_fake_classic_without_lean': empty}):
            with self.assertRaises(self.pack.NotBuilt):
                self.sp.lean_class()


if __name__ == '__main__':
    unittest.main()
