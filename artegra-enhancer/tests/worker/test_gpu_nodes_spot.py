"""ClaudeSpotTilesBanded (node_pack/claude_banded/spot_banded.py) against the frozen ClaudeSpotTiles (node_pack/claude_creative/
spot.py), on a CPU canvas, with a stub UNet and stub ControlNet networks inside ComfyUI's own ControlNet code (comfy/controlnet.py:
set_cond_hint, copy, get_control, broadcast_image_to, control_merge, compiled from the shipped file) and the stock
ControlNetApplyAdvanced.apply_controlnet (nodes.py):
- the classic run gets the whole-canvas hints as the classic graph makes them (the tile hint: ImageBlur's BHWC output moved
  to BCHW; the line hint: ClaudeCannyTiled's 0/1 edges repeated to 3 channels and moved, as its source does); the fork gets
  the same hints as planes (f32 [R] x 3; u8 0/1 [R] x 1) through CUControlNetApplyPlane / PlaneHint;
- over a short sampling run (dpmpp-like updates), every evaluation's output and the final latent are the classic's to the
  bit, and every call of the stub ControlNet network receives a hint with the classic's shape, dtype, memory format and
  values, in the same order: for the single, grouped (batch_windows 2), clamped-blend and seam-overlap paths, with the
  ControlNet's run-time dtype from manual_cast_dtype or from the model, cond and uncond batched together (the broadcast
  path) or apart (the crop view path);
- the coverage mark: one "[claude_banded] wsum_min=... evals=... windows=..." line per sampling run with wsum_min > 0, and
  a wsum of 0 raises; a canvas within one window is refused; balance other than static is refused with window_split;
- the Brownian cache input: 45 installs nothing; 8 installs the capped sampler for the run and puts the stock one back.
Skipped where torch or CU_COMFY_SOURCE is missing:
    CU_COMFY_SOURCE=<ComfyUI folder> python -B -m unittest tests.worker.test_gpu_nodes_spot   (from the artegra-enhancer folder)."""
import contextlib
import importlib
import io
import re
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

CLASSIC_NAME = 'cu_fake_classic_for_spot'


class _Executor:
    """What ComfyUI's wrapper executor is to a wrapper: callable with the wrapped call's arguments."""

    def __init__(self, fn, class_obj=None):
        self.fn, self.class_obj = fn, class_obj

    def __call__(self, *a, **k):
        return self.fn(*a, **k)


class StubModel:
    """A ModelPatcher stand-in: clone() and add_wrapper_with_key, the wrappers kept by type."""

    def __init__(self):
        self.wrappers = {}

    def clone(self):
        m = StubModel()
        m.wrappers = dict(self.wrappers)
        return m

    def add_wrapper_with_key(self, kind, key, fn):
        self.wrappers[kind] = fn


@unittest.skipUnless(HAVE_TORCH and COMFY, 'needs torch and CU_COMFY_SOURCE (the runtime ComfyUI folder)')
class ForkAgainstFrozenSpot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch
        cls.torch = torch
        cls.S = Stock()
        cls.CN = cls.S.controlnet()
        pe = types.ModuleType('comfy.patcher_extension')
        pe.WrappersMP = types.SimpleNamespace(CALC_COND_BATCH='calc_cond_batch', PREPARE_SAMPLING='prepare_sampling',
                                              OUTER_SAMPLE='outer_sample')
        cls.pe = pe
        cls.S.comfy.patcher_extension = pe
        cls.classic_pack = H.fake_classic_pack(CLASSIC_NAME)
        cls.mods = dict(cls.S.modules(), **{'comfy.patcher_extension': pe, 'comfy.model_patcher': cls.S.comfy.model_patcher,
                                             'comfy.model_base': cls.S.comfy.model_base, CLASSIC_NAME: cls.classic_pack})
        with mock.patch.dict(sys.modules, cls.mods):
            cls.spot = importlib.import_module(CLASSIC_NAME + '.spot')
        cls.fork = H.module('spot_banded')
        cls.cnp = H.module('cn_plane')
        cls.pack = H.load_pack()

    # ---- stand-ins for the networks ---------------------------------------------------------------------------------
    def stub_cn_net(self, seed, dtype, log):
        torch = self.torch
        import torch.nn.functional as F
        g = torch.Generator().manual_seed(seed)
        w = (torch.randn(4, 3, 8, 8, generator=g) * 0.05).to(dtype)
        wx = torch.randn(4, 4, 1, 1, generator=g).to(dtype) * 0.1

        class Net:
            def __init__(self):
                self.dtype = dtype

            def __call__(self, x, hint, timesteps, context, **extra):
                st = hint.stride()
                log.append((tuple(hint.shape), str(hint.dtype), tuple(sorted(range(4), key=lambda d: -st[d])),
                            hint.float().sum().item(), hint.float().std().item()))
                r = F.conv2d(hint, w.to(hint.dtype), stride=8) + F.conv2d(x, wx.to(x.dtype)) + timesteps.reshape(-1, 1, 1, 1) * 0.001
                return {'input': [r * 0.5], 'middle': [r * 0.25], 'output': [r]}
        return Net()

    def controlnet(self, seed, dtype, manual, log):
        torch = self.torch
        c = self.CN.ControlNet(self.stub_cn_net(seed, dtype, log), load_device=torch.device('cpu'), manual_cast_dtype=manual)
        c.model_sampling_current = types.SimpleNamespace(timestep=lambda t: t * 10.0,
                                                         calculate_input=lambda t, x: x / (t.reshape(-1, 1, 1, 1) ** 2 + 1) ** 0.5)
        return c

    def executor(self, joint):
        """calc_cond_batch's stand-in: the stub UNet with each cond's ControlNet residuals (stock get_control). joint: cond
        and uncond in one batch (ComfyUI batches them when they share their ControlNet), else one call per cond."""
        torch = self.torch

        def unet(x, t, ctrl):
            out = x * 0.93 + torch.sin(x * 3.0) * 0.05 + t.reshape(-1, 1, 1, 1) * 0.01
            if ctrl is not None:
                for k in ('input', 'middle', 'output'):
                    for r in ctrl[k]:
                        out = out + r.float() * 0.02
            return out

        def run(bm, conds, x_in, timestep, model_options):
            live = [(i, c) for i, c in enumerate(conds) if c is not None]
            outs = [torch.zeros_like(x_in) for _ in conds]
            groups = [live] if joint else [[ic] for ic in live]
            for grp in groups:
                n = len(grp)
                x = torch.cat([x_in] * n) if n > 1 else x_in
                t = timestep.repeat(n) if n > 1 else timestep
                c = grp[0][1][0]
                mg = model_options.get('multigpu_clones')      # a second card's call (comfy/samplers.py:519-521)
                dev = next(iter(mg)) if mg and len(mg) == 1 else None
                ctl = c.get('control')
                if ctl is not None and dev is not None:
                    ctl = ctl.get_instance_for_device(dev)
                ctrl = ctl.get_control(x, t, c, n, {}) if ctl is not None else None
                o = unet(x, t, ctrl)
                for j, (i, _) in enumerate(grp):
                    outs[i] = o[j * x_in.shape[0]:(j + 1) * x_in.shape[0]] + 0.003 * i
            return outs
        return run

    # ---- one sampling run of the classic or the fork ---------------------------------------------------------------
    def hints(self, R_h, R_w, seed):
        torch = self.torch
        rng = np.random.default_rng(seed)
        blur = rng.random((R_h, R_w, 3)).astype(np.float32)
        edges = rng.random((R_h, R_w)) < 0.07
        return blur, edges

    def classic_images(self, blur, edges):
        torch = self.torch
        tile_img = torch.from_numpy(blur)[None]                   # ImageBlur's output on the CPU: BHWC, contiguous
        out = torch.stack([torch.from_numpy(edges)])[:, None].to(dtype=torch.float32)
        line_img = out.to(device=torch.device('cpu'), dtype=torch.float32).repeat(1, 3, 1, 1).movedim(1, -1)   # ClaudeCannyTiled
        return tile_img, line_img

    def conds(self, cn_tile, cn_line, tile_img, line_img, fork, td, structure):
        """The graph's ControlNet chain (graph_v5t.py:266-279): c1 = tile on (pos, neg); or c2 = tile, then c3 = line on c2."""
        torch = self.torch
        g = torch.Generator().manual_seed(1)
        ctx = torch.randn(1, 6, 16, generator=g)
        pos, neg = [[ctx, {}]], [[ctx * 0.5, {}]]
        apply = self.S.nodes.ControlNetApplyAdvanced().apply_controlnet
        if fork:
            node = self.cnp.CUControlNetApplyPlane()
            tp = self.pack.PlaneRef(planes.from_array(Path(td) / 'hint.plane', tile_img).path, 'r')
            ep = self.pack.PlaneRef(planes.from_array(Path(td) / 'edges.plane', line_img).path, 'r')
            run = lambda p, n, cn, img, s, e: node.run(p, n, cn, img, s, 0.0, e, None)
            a, b = (tp, ep)
        else:
            run = lambda p, n, cn, img, s, e: apply(p, n, cn, img, s, 0.0, e, vae=None)
            a, b = tile_img, line_img
        with mock.patch.dict(sys.modules, self.mods):
            if not structure:
                p, n = run(pos, neg, cn_tile, a, 0.7, 0.6)
            else:
                p, n = run(pos, neg, cn_tile, a, 0.5, 1.0)
                p, n = run(p, n, cn_line, b, 0.8, 0.4)
        to = lambda grp: [{'c_crossattn': c[0], **c[1]} for c in grp]
        out = [to(p), to(n)]
        for grp in out:                                   # what ControlNet.pre_run gives every copy in the chain
            for c in grp:
                cn = c.get('control')
                while cn is not None:
                    cn.model_sampling_current = cn_tile.model_sampling_current
                    cn.timestep_range = None
                    cn = cn.previous_controlnet
        return out

    def two_cards(self, conds):
        """What MultiGPU_WorkUnits gives a second card (here a second CPU device key): a deep clone of every ControlNet in
        each chain, registered on its original, the clones chained as the originals are; and the model's clones."""
        torch = self.torch
        d2 = torch.device('cpu', 0)
        seen = {}
        for grp in conds:
            for c in grp:
                cn = c.get('control')
                while cn is not None and id(cn) not in seen:
                    seen[id(cn)] = cn
                    cl = cn.deepclone_multigpu(d2, autoregister=True)
                    cl.model_sampling_current, cl.timestep_range = cn.model_sampling_current, None
                    cn = cn.previous_controlnet
        for cn in seen.values():
            if cn.previous_controlnet is not None:
                cn.multigpu_clones[d2].previous_controlnet = cn.previous_controlnet.multigpu_clones[d2]
        return {torch.device('cpu'): types.SimpleNamespace(model=object()), d2: types.SimpleNamespace(model=object())}

    def sample(self, fork, R_h, R_w, opts, dtype=None, manual=None, joint=True, structure=True, steps=4, seed=11, split=False):
        torch = self.torch
        dtype = dtype or torch.bfloat16
        log = []
        blur, edges = self.hints(R_h, R_w, seed)
        cn_tile = self.controlnet(5, dtype, manual, log)
        cn_line = self.controlnet(6, dtype, manual, log)
        node = (self.fork.ClaudeSpotTilesBanded if fork else self.spot.ClaudeSpotTiles)()
        g = torch.Generator().manual_seed(seed)
        x0 = torch.randn(1, 4, R_h // 8, R_w // 8, generator=g)
        sigmas = torch.linspace(4.0, 0.5, steps + 1)
        evals = []
        stdout = io.StringIO()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td, mock.patch.object(self.cnp, 'WINDOW_PX', 255):
            if fork:
                conds = self.conds(cn_tile, cn_line, blur, edges.astype(np.uint8)[..., None], True, td, structure)
            else:
                conds = self.conds(cn_tile, cn_line, *self.classic_images(blur, edges), False, td, structure)
            mo = {'transformer_options': {}}
            if split:
                mo['multigpu_clones'] = self.two_cards(conds)
            with mock.patch.dict(sys.modules, self.mods), contextlib.redirect_stdout(stdout):
                m = node.apply(StubModel(), opts.pop('tile_px', 256), 1234, **opts)[0]
                calc, outer = m.wrappers['calc_cond_batch'], m.wrappers['outer_sample']
                ex = self.executor(joint)

                def inner(noise, latent, sampler, sig, *rest):
                    x = latent.clone()
                    for i in range(len(sig) - 1):
                        out = calc(ex, object(), conds, x, sig[i:i + 1], dict(mo))
                        evals.append([o.clone() for o in out])
                        x = x + (out[0] - out[1]) * 0.1 + out[0] * 0.01
                    return x
                with torch.inference_mode():
                    final = outer(_Executor(inner), torch.zeros_like(x0), x0, None, sigmas)
        return final, evals, log, stdout.getvalue()

    def assert_same(self, a, b, key):
        torch = self.torch
        fa, ea, la, sa = a
        fb, eb, lb, sb = b
        self.assertEqual(len(ea), len(eb), key)
        for i, (x, y) in enumerate(zip(ea, eb)):
            for u, v in zip(x, y):
                self.assertTrue(torch.equal(u, v), (key, 'evaluation', i, int((u != v).sum())))
        self.assertTrue(torch.equal(fa, fb), key)
        self.assertEqual(lb, la, key)                       # every ControlNet call: shape, dtype, layout, values
        self.assertGreater(len(la), 0, key)

    # ---- the checks --------------------------------------------------------------------------------------------------
    def test_identical_outputs_hints_and_layouts(self):
        torch = self.torch
        cases = [
            ('single', 600, 808, {}, dict()),
            ('clamped', 600, 808, {'clamp_blend': True}, dict()),
            ('grouped', 600, 808, {'clamp_blend': True, 'batch_windows': 2}, dict()),
            ('seam', 664, 744, {'clamp_blend': True, 'seam_overlap': 8, 'seam_dual': 2}, dict()),
            ('apart', 600, 808, {'clamp_blend': True}, dict(joint=False)),
            ('manual-cast', 600, 808, {'clamp_blend': True}, dict(dtype=torch.float32, manual=torch.bfloat16)),
            ('float32', 520, 1032, {'clamp_blend': True, 'batch_windows': 3}, dict(dtype=torch.float32)),
            ('tile-only', 600, 808, {'clamp_blend': True}, dict(structure=False)),
            ('product', 1208, 1600, {'clamp_blend': True, 'tile_px': 1024, 'noise_prefetch': False}, dict(steps=2)),
        ]
        for name, R_h, R_w, opts, kw in cases:
            a = self.sample(False, R_h, R_w, dict(opts), **kw)
            b = self.sample(True, R_h, R_w, dict(opts), **kw)
            self.assert_same(a, b, name)
            dt = str(kw.get('manual') or kw.get('dtype') or torch.bfloat16)
            self.assertTrue(all(c[1] == dt for c in b[2]), name)          # the ControlNet's run-time dtype
            orders = {c[2] for c in b[2]}
            self.assertTrue(orders <= {(0, 1, 2, 3), (0, 2, 3, 1), (1, 2, 3, 0), (1, 0, 2, 3)}, (name, orders))
            lines = [l for l in b[3].splitlines() if l.startswith('[claude_banded]')]
            self.assertEqual(len(lines), 1, name)
            m = re.fullmatch(r'\[claude_banded\] wsum_min=(\S+) evals=(\d+) windows=(\d+)', lines[0])
            self.assertIsNotNone(m, lines[0])
            self.assertGreater(float(m.group(1)), 0.0)
            self.assertGreaterEqual(int(m.group(2)), len(b[1]))
            self.assertGreater(int(m.group(3)), int(m.group(2)))
            self.assertNotIn('[claude_banded]', a[3])

    def test_two_cards_split_the_windows_statically(self):
        """The split path (spot.py split(): per-card ControlNet clones, per-card hints, the window units run on two threads,
        blended on the main card): the fork reads each card's crops from the plane (BoundHint.rebind) where the classic copies
        the whole hint; outputs, final latent and the ControlNet calls (as a multiset: the two cards run concurrently) are the
        classic's, and the coverage mark is logged."""
        opts = {'clamp_blend': True, 'window_split': True, 'balance': 'static'}
        for kw in ({}, {'joint': False}, {'structure': False}):
            a = self.sample(False, 600, 808, dict(opts), split=True, **kw)
            b = self.sample(True, 600, 808, dict(opts), split=True, **kw)
            self.assert_same((a[0], a[1], sorted(a[2]), a[3]), (b[0], b[1], sorted(b[2]), b[3]), ('split', kw))
            lines = [l for l in b[3].splitlines() if l.startswith('[claude_banded]')]
            self.assertEqual(len(lines), 1)
            self.assertGreater(float(lines[0].split()[1].split('=')[1]), 0.0)
            self.assertEqual(int(lines[0].split()[2].split('=')[1]), len(b[1]))
        single = self.sample(True, 600, 808, {'clamp_blend': True})
        real, seen = self.cnp.BoundHint.rebind, []

        def rebind(bound, device):
            seen.append((str(bound.device), str(device)))
            return real(bound, device)
        with mock.patch.object(self.cnp.BoundHint, 'rebind', rebind):
            split = self.sample(True, 600, 808, dict(opts), split=True)
        self.assertEqual(sorted(single[2]), sorted(split[2]))
        self.assertTrue(seen and set(seen) == {('cpu', 'cpu:0')}, seen)     # the second card reads its own crops

    def test_the_layouts_are_the_classics(self):
        """The tile hint reaches the ControlNet channels-last, the line hint NCHW, as the classic's crops do (T3)."""
        a = self.sample(False, 600, 808, {'clamp_blend': True}, joint=False)
        b = self.sample(True, 600, 808, {'clamp_blend': True}, joint=False)
        self.assertEqual([c[2] for c in a[2]], [c[2] for c in b[2]])
        self.assertIn((0, 2, 3, 1), {c[2] for c in b[2]})         # channels-last (the tile hint)
        self.assertIn((0, 1, 2, 3), {c[2] for c in b[2]})         # NCHW (the line hint)

    def test_one_window_canvases_and_non_static_splits_are_refused(self):
        torch = self.torch
        with mock.patch.dict(sys.modules, self.mods):
            with self.assertRaises(ValueError):
                self.fork.ClaudeSpotTilesBanded().apply(StubModel(), 256, 1, window_split=True, balance='auto')
            m = self.fork.ClaudeSpotTilesBanded().apply(StubModel(), 1024, 1)[0]
            x = torch.zeros(1, 4, 100, 120)
            with self.assertRaises(ValueError) as e:
                m.wrappers['calc_cond_batch'](lambda *a: None, object(), [[{}], [{}]], x, torch.tensor([1.0]), {})
            self.assertIn('fits one window', str(e.exception))
            with self.assertRaises(ValueError):
                self.fork.ClaudeSpotTilesBanded().apply(StubModel(), 256, 1, brownian_cache=46)

    def test_a_pixel_without_a_window_raises(self):
        torch = self.torch
        x = torch.zeros(1, 1, 4, 6)
        wins = [(0, 0, 0, 0, 4, 3)]                                 # the right half is never covered
        seen = []

        def cover(wsum, n):
            m = float(wsum.min())
            seen.append(m)
            if not m > 0:
                raise RuntimeError('no window')
        with self.assertRaises(RuntimeError):
            self.fork.blend(x, wins, [[torch.ones(1, 1, 4, 3)]], coverage=cover)
        self.assertEqual(seen, [0.0])
        out = self.fork.blend(x, [(0, 0, 0, 0, 4, 6)], [[torch.ones(1, 1, 4, 6)]], coverage=lambda w, n: seen.append(n))
        self.assertEqual(seen[-1], 1)
        self.assertTrue(torch.equal(out[0], self.spot.blend(x, [(0, 0, 0, 0, 4, 6)], [[torch.ones(1, 1, 4, 6)]])[0]))

    def test_the_brownian_cache_input(self):
        torch = self.torch
        from tools import gate_g7
        ks = gate_g7.sampling_module(COMFY)
        stock = ks.BrownianTreeNoiseSampler
        kd = types.ModuleType('comfy.k_diffusion')
        kd.__path__, kd.sampling = [], ks
        self.S.comfy.k_diffusion = kd
        mods = dict(self.mods, **{'comfy.k_diffusion': kd, 'comfy.k_diffusion.sampling': ks})
        seen = []
        x0 = torch.zeros(1, 4, 75, 101)
        for bc, prefetch in ((45, False), (45, True), (8, False), (8, True)):
            with mock.patch.dict(sys.modules, mods):
                m = self.fork.ClaudeSpotTilesBanded().apply(StubModel(), 256, 1, noise_prefetch=prefetch, brownian_cache=bc)[0]

                def inner(*a):
                    cls = ks.BrownianTreeNoiseSampler
                    seen.append((bc, prefetch, cls is stock, getattr(cls, '_claude_brownian_cache', None),
                                 getattr(cls, '_claude_prefetch', False)))
                    return a[1]
                with contextlib.redirect_stdout(io.StringIO()):
                    m.wrappers['outer_sample'](_Executor(inner), x0, x0, None, torch.linspace(4.0, 0.0, 5))
            self.assertIs(ks.BrownianTreeNoiseSampler, stock)
        self.assertEqual(seen, [(45, False, True, None, False), (45, True, False, None, True), (8, False, False, 8, False),
                                (8, True, False, 8, True)])


if __name__ == '__main__':
    unittest.main()
