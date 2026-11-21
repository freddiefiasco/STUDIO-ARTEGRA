"""CUControlNetApplyPlane and the window crops of PlaneHint (node_pack/claude_banded/cn_plane.py; T3, T12), with ComfyUI's own
ControlNetApplyAdvanced.apply_controlnet (nodes.py) and ControlNet code (comfy/controlnet.py), compiled from the shipped files:
- the node gives the stock node's conditioning (the same chain of ControlNet copies, strengths, ranges, previous ControlNets,
  control_apply_to_uncond), with the PlaneHint where the stock has its tensor; strength 0 returns the inputs as the stock does;
- ComfyUI's get_control cannot make a whole-canvas hint from a PlaneHint: with no window crop set it raises TypeError;
- a window crop has the classic crop's values, dtype and memory format: the 3-channel hint (f32, or u8 through T2) in the
  classic's tile hint format, which cn_plane.classic_tile_format reads from ComfyUI's own ImageBlur, ImageScale and
  common_upscale (5.0.2 wave 2: the first GPU runs found it NCHW-contiguous where the wave-1 node gave channels-last), here
  checked against that stock chain run on full-size canvases of both kinds (the classic canvas at k = 4, and ImageScale
  lanczos's otherwise); a 3-channel hint with no canvas plane beside it is refused; the 1-channel edges are ClaudeCannyTiled's
  0/1 repeated to 3 channels NCHW-contiguous; a rebound hint reads the same crop for another device.
Skipped where torch or CU_COMFY_SOURCE is missing."""
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from engine import planes
from tests import test_gpu_nodes_helpers as H
from tests.worker.test_gpu_nodes_stock import COMFY, HAVE_TORCH, Stock


@unittest.skipUnless(HAVE_TORCH and COMFY, 'needs torch and CU_COMFY_SOURCE (the runtime ComfyUI folder)')
class ControlNetApplyPlane(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch
        cls.torch = torch
        cls.S = Stock()
        cls.CN = cls.S.controlnet()
        cls.cnp = H.module('cn_plane')
        cls.pack = H.load_pack()

    def cn(self):
        torch = self.torch
        c = self.CN.ControlNet(types.SimpleNamespace(dtype=torch.float16), load_device=torch.device('cpu'))
        c.model_sampling_current = types.SimpleNamespace(timestep=lambda t: t, calculate_input=lambda t, x: x)
        return c

    def test_the_stock_conditioning_with_a_plane_hint(self):
        torch = self.torch
        rng = np.random.default_rng(1)
        hint = rng.random((1200, 1600, 3)).astype(np.float32)
        ctx = torch.zeros(1, 2, 4)
        apply = self.S.nodes.ControlNetApplyAdvanced().apply_controlnet
        with tempfile.TemporaryDirectory() as td, mock.patch.dict(sys.modules, self.S.modules()):
            ref = self.pack.PlaneRef(planes.from_array(Path(td) / 'h.plane', hint).path, 'r')
            for prev in (None, 'chain'):
                cn_a, cn_b = self.cn(), self.cn()
                pos = [[ctx, {'x': 1}], [ctx * 2, {}]]
                neg = [[ctx * 3, {}]]
                if prev:
                    pos, neg = apply(pos, neg, cn_a, torch.from_numpy(hint)[None], 0.3, 0.0, 1.0)
                    pos2, neg2 = self.cnp.CUControlNetApplyPlane().run(pos, neg, cn_b, ref, 0.7, 0.1, 0.6, 'vae')
                    want = apply(pos, neg, cn_b, torch.from_numpy(hint)[None], 0.7, 0.1, 0.6, vae='vae')
                else:
                    pos2, neg2 = self.cnp.CUControlNetApplyPlane().run(pos, neg, cn_b, ref, 0.7, 0.1, 0.6, 'vae')
                    want = apply(pos, neg, cn_b, torch.from_numpy(hint)[None], 0.7, 0.1, 0.6, vae='vae')
                for got_g, want_g in zip((pos2, neg2), want):
                    self.assertEqual(len(got_g), len(want_g))
                    for g, w in zip(got_g, want_g):
                        self.assertIs(g[0], w[0])
                        self.assertEqual(sorted(g[1]), sorted(w[1]))
                        gc, wc = g[1]['control'], w[1]['control']
                        self.assertIsInstance(gc.cond_hint_original, self.cnp.PlaneHint)
                        self.assertTrue(torch.is_tensor(wc.cond_hint_original))
                        for k in ('strength', 'timestep_percent_range', 'compression_ratio', 'upscale_algorithm'):
                            self.assertEqual(getattr(gc, k), getattr(wc, k), k)
                        self.assertIs(gc.previous_controlnet, wc.previous_controlnet)
                        self.assertEqual(g[1]['control_apply_to_uncond'], False)
                # cond and uncond share one ControlNet copy per previous ControlNet, as the stock's do
                self.assertIs(pos2[0][1]['control'], neg2[0][1]['control'])
            same = self.cnp.CUControlNetApplyPlane().run(pos, neg, cn_b, ref, 0.0, 0.0, 1.0, 'vae')
            self.assertIs(same[0], pos)
            self.assertIs(same[1], neg)

    def test_get_control_cannot_rederive_a_whole_canvas_hint(self):
        torch = self.torch
        with tempfile.TemporaryDirectory() as td, mock.patch.dict(sys.modules, self.S.modules()):
            ref = self.pack.PlaneRef(planes.from_array(Path(td) / 'h.plane', np.zeros((1200, 1600, 3), np.float32)).path, 'r')
            pos, neg = self.cnp.CUControlNetApplyPlane().run([[torch.zeros(1, 2, 4), {}]], [[torch.zeros(1, 2, 4), {}]],
                                                             self.cn(), ref, 0.7, 0.0, 1.0, None)
            c = pos[0][1]['control']
            with self.assertRaises(TypeError):
                c.get_control(torch.zeros(1, 4, 150, 200), torch.tensor([1.0]), {'c_crossattn': torch.zeros(1, 2, 4)}, 1, {})

    def stock_tile_format(self, canvas, h, w):
        """The memory format the classic's tile hint has at the ControlNet, from the stock chain on a canvas of h x w: the
        classic canvas (k = 4: ClaudeUpscaleModelTiled's IMAGE; else ImageScale lanczos), ImageBlur, ControlNetApplyAdvanced's
        movedim, the classic spot's same-size common_upscale and its cast."""
        torch = self.torch
        with mock.patch.dict(sys.modules, self.S.modules()):
            if canvas == 'f32':
                c = torch.clamp(torch.rand(1, 3, h, w).movedim(-3, -1), min=0, max=1.0)
            else:
                c = self.S.nodes.ImageScale().upscale(torch.rand(1, h // 4, w // 4, 3), 'lanczos', w, h, 'disabled')[0]
            img = self.S.post_processing.Blur.execute(c, 4, 2.0).args[0]
            hint = self.S.cu.common_upscale(img.movedim(-1, 1), w, h, 'nearest-exact', 'center').to(dtype=torch.float16)
        if hint.is_contiguous():
            return torch.contiguous_format
        self.assertTrue(hint.is_contiguous(memory_format=torch.channels_last))
        return torch.channels_last

    def test_the_classic_canvas_steps_are_the_classics(self):
        """classic_tile_format's k = 4 canvas is ClaudeUpscaleModelTiled's own last step (the classic pack's source)."""
        src = (H.ROOT / 'node_pack' / 'claude_creative' / '__init__.py').read_text(encoding='utf8')
        self.assertIn('s = torch.clamp(s.movedim(-3, -1), min=0, max=1.0).to(device=mm.intermediate_device(), '
                      'dtype=mm.intermediate_dtype())', src)
        import inspect
        fmt_src = inspect.getsource(self.cnp.classic_tile_format)
        self.assertIn("torch.clamp(torch.rand(1, 3, h, w, generator=g).movedim(-3, -1), min=0, max=1.0)", fmt_src)
        self.assertIn("nodes.ImageScale().upscale(", fmt_src)
        self.assertIn("Blur.execute(canvas, 1, 1.0)", fmt_src)

    def test_window_crops(self):
        torch = self.torch
        rng = np.random.default_rng(2)
        f = rng.random((300, 400, 3)).astype(np.float32)
        u = rng.integers(0, 256, (300, 400, 3), dtype=np.uint8)
        e = (rng.random((300, 400)) < 0.1).astype(np.uint8)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td, \
                mock.patch.dict(sys.modules, self.S.modules()):      # a bound hint keeps its plane mapped
            def mk(name, a, canvas):
                d = Path(td) / name
                d.mkdir()
                if canvas is not None:
                    planes.from_array(d / 'canvas.plane', np.zeros((300, 400, 3), {'f32': np.float32, 'u8': np.uint8}[canvas]))
                return self.cnp.PlaneHint.from_ref(self.pack.PlaneRef(planes.from_array(d / 'hint.plane', a).path, 'r'))
            he = mk('e', e[..., None], None)
            for canvas in ('f32', 'u8'):
                hf, hu = mk(f'f-{canvas}', f, canvas), mk(f'u-{canvas}', u, canvas)
                self.assertEqual((hf.canvas_dtype, hu.canvas_dtype), (canvas, canvas))
                fmt = self.stock_tile_format(canvas, 300, 400)
                self.assertEqual(self.cnp.classic_tile_format(canvas), fmt)
                for h, want_full in ((hf, torch.from_numpy(f)[None].movedim(-1, 1)),
                                     (hu, torch.from_numpy(planes.U8_TO_F32[u])[None].movedim(-1, 1))):
                    for dtype in (torch.float16, torch.bfloat16, torch.float32):
                        b = h.bind(torch.device('cpu'), dtype)
                        crop = b[..., 40:296, 8:264]
                        want = want_full.to(dtype=dtype)[..., 40:296, 8:264]
                        self.assertTrue(torch.equal(crop, want))
                        self.assertEqual(crop.dtype, dtype)
                        self.assertTrue(crop.is_contiguous(memory_format=fmt))
                        self.assertTrue(torch.equal(b.rebind(torch.device('cpu'))[..., 40:296, 8:264], crop))
            no_canvas = mk('f-none', f, None)
            self.assertIsNone(no_canvas.canvas_dtype)
            with self.assertRaises(ValueError):
                no_canvas.bind(torch.device('cpu'), torch.float16)[..., 0:64, 0:64]
            classic = torch.stack([torch.from_numpy(e.astype(bool))])[:, None].to(dtype=torch.float32)
            classic = classic.repeat(1, 3, 1, 1).movedim(1, -1).movedim(-1, 1)        # ClaudeCannyTiled -> ControlNetApply
            self.assertTrue(classic.is_contiguous())
            crop = he.bind(torch.device('cpu'), torch.float16)[..., 0:256, 100:356]
            self.assertTrue(torch.equal(crop, classic.to(torch.float16)[..., 0:256, 100:356]))
            self.assertTrue(crop.is_contiguous())
            self.assertEqual(tuple(crop.shape), (1, 3, 256, 256))
            with self.assertRaises(ValueError):
                he.bind(torch.device('cpu'), torch.float16)[..., 0:301, 0:8]


if __name__ == '__main__':
    unittest.main()
