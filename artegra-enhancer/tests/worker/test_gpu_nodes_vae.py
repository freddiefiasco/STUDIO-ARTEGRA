"""CUEncodePlane and CUDecodePlane (node_pack/claude_banded/vae_planes.py) against ComfyUI's own VAEEncodeTiled /
VAEDecodeTiled -> VAE.encode_tiled / decode_tiled -> encode_tiled_ / decode_tiled_ -> comfy.utils.tiled_scale, ImageScale
area and the finish's q8 (v4finish.quantize_8bit), all compiled from the shipped files (tests/worker/test_gpu_nodes_stock.py),
with a tiny CPU autoencoder in float32 and bfloat16, on synthetic canvases and latents:
- the latents are the stock's to the bit, for u8 canvas planes (T2) and float32 ones (k = 4), several tile sizes, odd tile
  counts and canvases where one tiling is a single tile; every tile reaches the encoder as the stock's tile does (shape,
  dtype, memory format, in the same order); the three encode states load the VAE as specified and give the same latent;
- the decoded rows (rolling buffers) are the stock decode's float output to the bit; area on aligned bands equals the whole
  F.interpolate area to the bit, at s = 1, 1.5 and 2; the stored u8 is q8's value of the stock float (0 differing values),
  and reading it through the T2 table gives exactly what q8 gives the finish (G4).
Skipped where torch or CU_COMFY_SOURCE is missing:
    CU_COMFY_SOURCE=<ComfyUI folder> python -B -m unittest tests.worker.test_gpu_nodes_vae   (from the artegra-enhancer folder)."""
import ast
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from engine import planes
from tests import test_gpu_nodes_helpers as H
from tests.worker.test_gpu_nodes_stock import COMFY, HAVE_TORCH, Stock, tiny_autoencoder


def quantize_8bit():
    src = (H.ROOT / 'node_pack' / 'claude_creative' / 'v4finish.py').read_text(encoding='utf8')
    fn = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == 'quantize_8bit')
    g = {'np': np}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), 'v4finish.py', 'exec'), g)
    return g['quantize_8bit']


def canvas_u8(h, w, seed):
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:h, 0:w]
    a = np.stack([(x * 7 + y * 3) % 256, np.where(((x // 37) + (y // 23)) % 2 == 0, 200, 40), rng.integers(0, 256, (h, w))], -1)
    return a.astype(np.uint8)


@unittest.skipUnless(HAVE_TORCH and COMFY, 'needs torch and CU_COMFY_SOURCE (the runtime ComfyUI folder)')
class EncodeAgainstVAEEncodeTiled(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch
        cls.torch = torch
        cls.S = Stock()
        cls.vp = H.module('vae_planes')
        cls.pack = H.load_pack()

    def stock_latent(self, vae, image, tile, overlap):
        return self.S.node_fns['VAEEncodeTiled.encode'](None, vae, image, tile, overlap)[0]['samples']

    def run_pair(self, arr, tile, overlap, dtype, state='resident'):
        torch = self.torch
        f = planes.U8_TO_F32[arr] if arr.dtype == np.uint8 else arr
        # the classic canvas IMAGE: a BHWC view of NCHW memory (ImageScale lanczos' stack, or the x4 node's movedim + clamp)
        image = torch.from_numpy(np.ascontiguousarray(f)).permute(2, 0, 1).contiguous()[None].movedim(1, -1)
        m1, m2 = tiny_autoencoder(7), tiny_autoencoder(7)
        v1, v2 = self.S.vae(m1, dtype), self.S.vae(m2, dtype)
        self.S.mm.calls.clear()
        with mock.patch.dict(sys.modules, self.S.modules()), torch.inference_mode():     # ComfyUI runs nodes so
            want = self.stock_latent(v1, image, tile, overlap)
            stock_calls = list(self.S.mm.calls)
            self.S.mm.calls.clear()
            with tempfile.TemporaryDirectory() as td:
                p = planes.from_array(Path(td) / 'canvas.plane', arr)
                got = self.vp.CUEncodePlane().run(self.pack.PlaneRef(p.path, 'r'), v2, tile, overlap, state)[0]['samples']
        return want, got, m1.seen, m2.seen, stock_calls, list(self.S.mm.calls)

    def test_latents_and_tiles_are_the_stocks(self):
        torch = self.torch
        n = 0
        for (h, w, tile, overlap) in ((1232, 2056, 1024, 64), (1600, 504, 1024, 64), (520, 776, 256, 32), (776, 1000, 320, 64)):
            for dtype in (torch.float32, torch.bfloat16):
                for kind in ('u8', 'f32'):
                    arr = canvas_u8(h, w, h + w)
                    if kind == 'f32':
                        arr = np.clip(planes.U8_TO_F32[arr] * np.float32(0.93) + np.float32(0.021), 0, 1).astype(np.float32)
                    want, got, seen1, seen2, _, _ = self.run_pair(arr, tile, overlap, dtype)
                    key = (h, w, tile, overlap, dtype, kind)
                    self.assertEqual(got.dtype, want.dtype, key)
                    self.assertEqual(tuple(got.shape), (1, 4, h // 8, w // 8), key)
                    self.assertTrue(torch.equal(got, want), f'{key}: {int((got != want).sum())} differing latent values')
                    self.assertEqual(seen2, seen1, key)                 # same tiles, same order, same layout and dtype
                    n += 1
        self.assertEqual(n, 16)

    def test_the_encode_states(self):
        torch = self.torch
        arr = canvas_u8(1232, 2056, 5)
        base = None
        for state in ('resident', 'partial', 'classic'):
            want, got, _, _, stock_calls, calls = self.run_pair(arr, 1024, 64, torch.float32, state)
            self.assertTrue(torch.equal(got, want), state)
            base = got if base is None else base
            self.assertTrue(torch.equal(got, base), state)
            vae_loads = [c for c in calls if c[0] == 'load_models_gpu']
            if state == 'classic':                       # the classic's whole-canvas estimate, exactly
                self.assertEqual(calls, stock_calls)
                self.assertEqual(vae_loads[0][2], 1767 * 1232 * 2056 * 4)
            elif state == 'resident':                    # one tile: the largest of 1024 x 1024, 2048 x 512, 512 x 2048
                self.assertEqual(len(vae_loads), 1)
                self.assertEqual(vae_loads[0][2], 1767 * 1024 * 1024 * 4)
                self.assertEqual(vae_loads[0][3], False)
            else:                                        # partial: the VAE alone, budget 0.1, no free_memory, no eviction
                self.assertEqual([c[0] for c in calls], ['model_load'])
                self.assertEqual(calls[0][2], 0.1)
                self.assertFalse(any(c[0] == 'free_memory' for c in calls))
        with self.assertRaises(ValueError):
            self.run_pair(arr, 1024, 64, torch.float32, 'evict')

    def test_partial_unloads_only_the_vae(self):
        mm = self.S.mm
        other, vae_p = object(), object()
        mm.current_loaded_models[:] = [mm.LoadedModel(other), mm.LoadedModel(vae_p)]
        mm.calls.clear()
        self.vp.load_partial(mm, vae_p)
        self.assertEqual([(c[0], c[1]) for c in mm.calls], [('model_unload', vae_p), ('model_load', vae_p)])
        self.assertEqual([m.model for m in mm.current_loaded_models], [vae_p, other])
        mm.current_loaded_models[:] = []

    def test_refusals(self):
        torch = self.torch
        v = self.S.vae(tiny_autoencoder(1), torch.float32)
        with tempfile.TemporaryDirectory() as td:
            p = planes.from_array(Path(td) / 'c.plane', canvas_u8(100, 64, 1))
            with mock.patch.dict(sys.modules, self.S.modules()):
                with self.assertRaises(ValueError):                   # not a multiple of 8
                    self.vp.CUEncodePlane().run(self.pack.PlaneRef(p.path, 'r'), v, 1024, 64, 'resident')
                v.handles_tiling = True
                p2 = planes.from_array(Path(td) / 'd.plane', canvas_u8(96, 64, 1))
                with self.assertRaises(ValueError):                   # a VAE this engine does not reproduce
                    self.vp.CUEncodePlane().run(self.pack.PlaneRef(p2.path, 'r'), v, 1024, 64, 'resident')


@unittest.skipUnless(HAVE_TORCH and COMFY, 'needs torch and CU_COMFY_SOURCE (the runtime ComfyUI folder)')
class DecodeAgainstVAEDecodeTiled(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch
        cls.torch = torch
        cls.S = Stock()
        cls.vp = H.module('vae_planes')
        cls.pack = H.load_pack()
        cls.q8 = staticmethod(quantize_8bit())

    def latent(self, h, w, seed):
        g = self.torch.Generator().manual_seed(seed)
        return self.torch.randn((1, 4, h, w), generator=g) * 0.8

    CASES = ((63, 93, 1.5, 256, 32), (62, 94, 2, 256, 32), (61, 93, 1, 256, 32), (300, 200, 2, 1024, 64),
             (200, 63, 1, 1024, 64), (33, 600, 1.5, 1024, 64))

    def test_rows_area_and_u8_are_the_stocks(self):
        torch = self.torch
        from fractions import Fraction
        for (lh, lw, s, tile, overlap) in self.CASES:
            for dtype in (torch.float32, torch.bfloat16):
                z = self.latent(lh, lw, lh * 31 + lw)
                R_h, R_w = lh * 8, lw * 8
                fs = Fraction(s).limit_denominator(4)
                O_h, O_w = int(R_h / fs), int(R_w / fs)
                key = (lh, lw, s, tile, overlap, dtype)
                m1, m2, m3 = tiny_autoencoder(3), tiny_autoencoder(3), tiny_autoencoder(3)
                with mock.patch.dict(sys.modules, self.S.modules()):
                    raw = self.S.node_fns['VAEDecodeTiled.decode'](None, self.S.vae(m1, dtype), {'samples': z}, tile, overlap)[0]
                    area = self.S.node_fns['ImageScale.upscale'](None, raw, 'area', O_w, O_h, 'disabled')[0]
                    # the decoded rows of the rolling buffers, against the stock float output
                    got_rows = []
                    v2 = self.S.vae(m2, dtype)
                    self.vp.decode_rows(v2, z, tile // 8, tile // 8, overlap // 8, lambda r0, t: got_rows.append((r0, t.clone())),
                                        period=fs.numerator)
                    starts = [r for r, _ in got_rows]
                    self.assertEqual(starts, sorted(starts), key)
                    self.assertTrue(all(r % fs.numerator == 0 for r in starts), key)
                    rows = torch.cat([t for _, t in got_rows], 2)
                    self.assertTrue(torch.equal(rows, raw.movedim(-1, 1)), f'{key}: {int((rows != raw.movedim(-1, 1)).sum())}')
                    self.assertEqual(sorted(x for x in m2.seen), sorted(x for x in m1.seen), key)   # the same tiles
                    # the node: area on aligned bands, then u8
                    with tempfile.TemporaryDirectory() as td:
                        ref = self.vp.CUDecodePlane().run({'samples': z}, self.S.vae(m3, dtype), tile, overlap, O_w, O_h,
                                                          'creative', str(Path(td) / 's0'), 'r1')[0]
                        self.assertEqual(Path(ref.path), Path(td) / 's0' / 'creative.plane')
                        u8 = planes.validate(ref.path, shape=(O_h, O_w, 3), dtype='u8').read_rows(0, O_h)
                a = area[0].numpy()
                want_u8 = np.clip(255. * a, 0, 255).astype(np.uint8)
                self.assertEqual(int((u8 != want_u8).sum()), 0, key)
                q = self.q8(a)
                self.assertEqual(int((planes.U8_TO_F32[u8].view(np.uint32) != q.view(np.uint32)).sum()), 0, key)
                self.assertEqual(int((self.q8(planes.U8_TO_F32[u8]).view(np.uint32) != q.view(np.uint32)).sum()), 0, key)

    def test_area_on_aligned_bands_is_the_whole_area(self):
        torch = self.torch
        cu = self.S.cu
        for (R_h, R_w, num, den) in ((1200, 1536, 2, 1), (1203, 1500, 3, 2), (4800, 96, 2, 1), (96, 4803, 3, 2)):
            x = torch.rand((1, 3, R_h, R_w), generator=torch.Generator().manual_seed(R_h))
            O_h, O_w = R_h * den // num, R_w * den // num
            whole = cu.common_upscale(x, O_w, O_h, 'area', 'disabled')
            for band in (num * 1, num * 7, num * 96, num * 401):
                parts = []
                for r0 in range(0, R_h, band):
                    r1 = min(R_h, r0 + band)
                    n = (r1 - r0) * den // num
                    parts.append(cu.common_upscale(x[:, :, r0:r1].contiguous(), O_w, n, 'area', 'disabled'))
                got = torch.cat(parts, 2)
                self.assertTrue(torch.equal(got, whole), (R_h, R_w, num, den, band))

    def test_the_add_order(self):
        """The rolling sum is ((A + B) + C) / 3 with A = (tile / 2, 2 tile), B = (2 tile, tile / 2): float addition is not
        associative, so a reordered sum differs somewhere on these values."""
        torch = self.torch
        from fractions import Fraction
        z = self.latent(63, 93, 9)
        m = tiny_autoencoder(4)
        with mock.patch.dict(sys.modules, self.S.modules()):
            raw = self.S.node_fns['VAEDecodeTiled.decode'](None, self.S.vae(m, torch.float32), {'samples': z}, 256, 32)[0]
            v = self.S.vae(tiny_autoencoder(4), torch.float32)
            ts = lambda tx, ty: self.S.cu.tiled_scale(z, lambda a: v.first_stage_model.decode(a), tx, ty, 4, upscale_amount=8,
                                                      out_channels=3, output_device='cpu')
            A, B, C = ts(16, 64), ts(64, 16), ts(32, 32)
            right = ((A + B) + C) / 3.0
            wrong = (A + (B + C)) / 3.0
        self.assertTrue(torch.equal(v.process_output(right.clone()), raw.movedim(-1, 1)))
        self.assertFalse(torch.equal(right, wrong))

    # (lh, lw, tile, overlap) in latent px, period, EMIT_ROWS (None: the module's)
    GEOMETRY = ((150, 70, 32, 8, 1, None),          # overlap at the node's clamp (tile / 4)
                (150, 70, 32, 12, 2, None),         # beyond it: tiling B moves 4 latent rows a step and keeps 12
                (121, 157, 32, 4, 3, None),         # short last tile rows and columns, period 3
                (20, 30, 32, 4, 1, None),           # tiling C is a single tile
                (97, 80, 32, 8, 3, 7),              # chunks shorter than one release (9 rows at period 3)
                (64, 64, 16, 4, 5, 2))              # a period longer than EMIT_ROWS

    def test_decode_rows_is_the_stock_decode_on_more_geometry(self):
        """decode_rows against the stock VAE.decode_tiled_ (process_output included) to the bit, where the rolling buffers
        compact in blocks (overlap above the shift), with a single-tile tiling, odd last tiles, periods 1-5 and chunks
        shorter than a release; every chunk starts where the last ended, at a multiple of the period, and is at most
        EMIT_ROWS rounded up to the period."""
        torch = self.torch
        for (lh, lw, tile, ov, period, emit_rows) in self.GEOMETRY:
            for dtype in (torch.float32, torch.bfloat16):
                key = (lh, lw, tile, ov, period, emit_rows, dtype)
                z = self.latent(lh, lw, lh * 7 + lw)
                m1, m2 = tiny_autoencoder(5), tiny_autoencoder(5)
                got = []
                with mock.patch.dict(sys.modules, self.S.modules()), \
                        mock.patch.object(self.vp, 'EMIT_ROWS', emit_rows or self.vp.EMIT_ROWS):
                    want = self.S.vae(m1, dtype).decode_tiled_(z, tile, tile, ov)
                    self.vp.decode_rows(self.S.vae(m2, dtype), z, tile, tile, ov,
                                        lambda r0, t: got.append((r0, t.clone())), period=period)
                    E = period * -(-self.vp.EMIT_ROWS // period)
                rows = torch.cat([t for _, t in got], 2)
                self.assertTrue(torch.equal(rows, want), f'{key}: {int((rows != want).sum())} differing values')
                self.assertEqual(sorted(m2.seen), sorted(m1.seen), key)
                end = 0
                for i, (r0, t) in enumerate(got):
                    n = t.shape[2]
                    self.assertEqual(r0, end, key)
                    self.assertEqual(r0 % period, 0, key)
                    self.assertLessEqual(n, E, key)
                    if i < len(got) - 1:
                        self.assertEqual(n % period, 0, key)
                    end = r0 + n
                self.assertEqual(end, lh * 8, key)

    def test_the_buffers_are_allocated_once(self):
        """No full-width tensor is allocated per step: the count of full-render-width results that are not a view of, or
        in place on, an argument (torch.cat, clone, zeros, a + b, ...) is the same for a latent three times as tall, and
        each tiling keeps one buffer (the same memory) from its first step to its last."""
        torch = self.torch
        from torch.overrides import TorchFunctionMode
        lw = 150
        W = lw * 8

        class FreshFullWidth(TorchFunctionMode):
            def __init__(self):
                super().__init__()
                self.n = 0

            def __torch_function__(self, func, types, args=(), kwargs=None):
                kwargs = kwargs or {}
                out = func(*args, **kwargs)
                if isinstance(out, torch.Tensor) and out.dim() == 4 and out.shape[-1] == W:
                    flat = [b for a in list(args) + list(kwargs.values()) for b in (a if isinstance(a, (list, tuple)) else [a])]
                    ptrs = {b.untyped_storage().data_ptr() for b in flat if isinstance(b, torch.Tensor)}
                    if out.untyped_storage().data_ptr() not in ptrs:
                        self.n += 1
                return out

        tilings, ptrs = [], {}
        orig_init, orig_step = self.vp._Tiling.__init__, self.vp._Tiling.step

        def init(t, *a, **k):
            orig_init(t, *a, **k)
            tilings.append(t)

        def step(t):
            orig_step(t)
            ptrs.setdefault(id(t), set()).add((t.acc.data_ptr(), None if t.div is None else t.div.data_ptr()))

        counts = []
        for lh in (80, 240):
            z = self.latent(lh, lw, lh)
            v = self.S.vae(tiny_autoencoder(2), torch.float32)
            tilings.clear()
            ptrs.clear()
            with mock.patch.dict(sys.modules, self.S.modules()), mock.patch.object(self.vp._Tiling, '__init__', init), \
                    mock.patch.object(self.vp._Tiling, 'step', step), FreshFullWidth() as fresh:
                self.vp.decode_rows(v, z, 32, 32, 4, lambda r0, t: None, period=1)
            counts.append(fresh.n)
            self.assertEqual(len(tilings), 3)
            self.assertTrue(all(not t.single for t in tilings))
            self.assertEqual([len(ptrs[id(t)]) for t in tilings], [1, 1, 1], lh)
        self.assertEqual(counts[0], counts[1], counts)
        self.assertLessEqual(counts[1], 6, counts)

    def test_refusals(self):
        torch = self.torch
        z = self.latent(40, 40, 1)
        with mock.patch.dict(sys.modules, self.S.modules()), tempfile.TemporaryDirectory() as td:
            for (w, h) in ((200, 160), (320, 256), (640, 640)):        # not one supersample >= 1 on both axes
                with self.assertRaises(ValueError):
                    self.vp.CUDecodePlane().run({'samples': z}, self.S.vae(tiny_autoencoder(1), torch.float32), 256, 32,
                                                w, h, 'creative', td, 'r')
            with self.assertRaises(ValueError):
                self.vp.CUDecodePlane().run({'samples': z}, self.S.vae(tiny_autoencoder(1), torch.float32), 256, 32, 320,
                                            320, 'other', td, 'r')


COMMIT_PROBE = r'''
import gc, json, os, sys
from unittest import mock
import psutil, torch
import torch.nn.functional as F
torch.set_num_threads(2)
from tests import test_gpu_nodes_helpers as H
from tests.worker.test_gpu_nodes_stock import Stock
S = Stock()
vp = H.module('vae_planes')
class Dec(torch.nn.Module):
    def decode(self, z):
        return F.interpolate(z[:, :3], scale_factor=8, mode='nearest')
lh, td, widths = int(sys.argv[1]), sys.argv[2], [int(w) for w in sys.argv[3:]]
v = S.vae(Dec(), torch.float32)
zs = [torch.randn((1, 4, lh, lw)) for lw in widths]
proc = psutil.Process()
gc.collect()
before = proc.memory_info().private
out = []
for i, z in enumerate(zs):
    with mock.patch.dict(sys.modules, S.modules()):
        vp.CUDecodePlane().run({'samples': z}, v, 1024, 64, z.shape[3] * 8, lh * 8, 'creative', os.path.join(td, str(i)), 'r')
    gc.collect()
    mi = proc.memory_info()
    out.append((mi.private - before, mi.peak_pagefile - before))
print(json.dumps(out))
'''


def _have_psutil():
    import importlib.util
    return importlib.util.find_spec('psutil') is not None


@unittest.skipUnless(HAVE_TORCH and COMFY and sys.platform == 'win32' and _have_psutil(),
                     'needs torch, CU_COMFY_SOURCE, Windows (peak commit) and psutil')
class DecodeCommit(unittest.TestCase):
    def test_the_peak_commit_follows_the_live_rows(self):
        """CUDecodePlane at the product's tile (1024 px, overlap 64), four calls in one fresh process on renders 4,000,
        8,000, 6,000 and 8,000 px wide (4,000 rows), a trivial x8 decoder (the CPU side is the node's): the peak commit
        growth stays within 1.3 x the widest call's live rows, (3584 x 16 + 256 x 12) B per render column, plus 32 MiB, and
        no more than 96 MiB stays committed after each call returns. At 9fc2aade (per-step concatenations and clones) the
        peak was about 2.7 x the live rows (torch 2.9.1, Windows: the allocator kept the commit of the freed blocks); with
        the fixed buffers in torch's own allocator, about 1.6 x, and 200-400 MiB stayed committed after each call."""
        import json
        import os
        import subprocess
        lh, widths = 500, (500, 1000, 750, 1000)
        live = (3584 * 16 + 256 * 12) * max(widths) * 8
        with tempfile.TemporaryDirectory() as td:
            env = dict(os.environ, PYTHONPATH=os.pathsep.join(p for p in (str(H.ROOT), os.environ.get('PYTHONPATH')) if p))
            r = subprocess.run([sys.executable, '-B', '-c', COMMIT_PROBE, str(lh), td] + [str(w) for w in widths],
                               cwd=str(H.ROOT), env=env, capture_output=True, text=True, timeout=600)
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        calls = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertEqual(len(calls), len(widths))
        MiB = 2 ** 20
        msg = f'{[(round(a / MiB), round(b / MiB)) for a, b in calls]} MiB (kept, peak); live rows {live / MiB:.0f} MiB'
        self.assertLessEqual(max(b for _, b in calls), 1.3 * live + 32 * MiB, msg)
        self.assertLessEqual(max(a for a, _ in calls), 96 * MiB, msg)


if __name__ == '__main__':
    unittest.main()
