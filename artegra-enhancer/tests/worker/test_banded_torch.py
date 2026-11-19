"""Exactness of the Large-image engine's banded steps against the classic node code itself, on the worker's own libraries
(torch, scipy). Skipped where torch is not installed (the app's test environment); run on the worker runtime or any Python
with torch and numpy:  python -B -m unittest tests.worker.test_banded_torch   (from the artegra-enhancer folder).

- the banded x4 accumulator (engine/dat_bands.py) against margin_tiled_upscale, read from node_pack/claude_creative/__init__.py
  without importing the node pack (it needs ComfyUI): 0 differing float32 values;
- the x4 output's 8-bit conversion against the classic's (torch.clamp, then comfy.utils.lanczos's np.clip(255. * x)).
CPU only; synthetic images."""
import ast
import importlib.util
import unittest
from pathlib import Path

import numpy as np

HAVE_TORCH = importlib.util.find_spec('torch') is not None
ROOT = Path(__file__).resolve().parents[2]


def classic_function(name):
    """A top-level function of the classic node pack, compiled on its own (with torch in its globals)."""
    import torch
    src = (ROOT / 'node_pack' / 'claude_creative' / '__init__.py').read_text(encoding='utf8')
    tree = ast.parse(src)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    g = {'torch': torch, 'math': __import__('math')}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), 'claude_creative/__init__.py', 'exec'), g)
    return g[name]


def synth(h, w, seed):
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:h, 0:w]
    a = np.stack([(x * 7 + y * 3) % 256, np.where(((x // 31) + (y // 17)) % 2 == 0, 210, 25),
                  rng.integers(0, 256, (h, w))], -1).astype(np.uint8)
    return a


@unittest.skipUnless(HAVE_TORCH, 'torch is not installed here (run on the worker runtime)')
class BandedDatAgainstTheClassicFunction(unittest.TestCase):
    def test_zero_differing_values(self):
        import sys
        sys.path.insert(0, str(ROOT))
        import torch
        from engine import dat_bands
        mtu = classic_function('margin_tiled_upscale')

        def model_t(a):              # a stand-in x4 model: nearest x4, a nonlinear tone and a channel mix (CPU, float32)
            u = a.repeat_interleave(4, -2).repeat_interleave(4, -1)
            return (u.clamp(0, 1) ** 1.3) * 0.97 + 0.02 * u.mean(1, keepdim=True)

        def model_np(crop):          # the same model on an H x W x C uint8 crop, as the BES node calls it
            t = torch.from_numpy(crop.astype(np.float32) / np.float32(255.0)).permute(2, 0, 1)[None]
            return model_t(t)[0].permute(1, 2, 0).numpy()

        for H, W in ((300, 700), (1100, 530), (513, 1500), (480, 480)):
            img = synth(H, W, H + W)
            x = torch.from_numpy(img.astype(np.float32) / np.float32(255.0)).permute(2, 0, 1)[None]
            want = mtu(x, model_t, 4, 512, 64, 16)[0].permute(1, 2, 0).numpy()
            got = np.zeros_like(want)

            def sink(y0, rows):
                got[y0:y0 + rows.shape[0]] = rows
            dat_bands.margin_tiled_banded(lambda y0, y1, x0, x1: img[y0:y1, x0:x1], img.shape, model_np, 4, sink)
            self.assertEqual(int((got.view(np.uint32) != want.view(np.uint32)).sum()), 0, (H, W))

    def test_the_8_bit_conversion(self):
        import sys
        sys.path.insert(0, str(ROOT))
        import torch
        from engine import dat_bands
        v = torch.linspace(-0.2, 1.2, 1_000_003, dtype=torch.float32).reshape(1, -1, 1)
        want = np.clip(255. * torch.clamp(v, min=0, max=1.0).numpy(), 0, 255).astype(np.uint8)
        got = dat_bands.to_canvas_u8(v.numpy())
        self.assertEqual(int((got != want).sum()), 0)


if __name__ == '__main__':
    unittest.main()
