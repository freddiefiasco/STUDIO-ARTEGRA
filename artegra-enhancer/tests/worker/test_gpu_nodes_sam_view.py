"""gpu-nodes check G3 (BUILD-WAVE-2 package integ, item 4): CUSam3DetectLean writes the float32 view of its input plane ONCE per
stage and every SAM term of the prompt reuses it, pixel-neutral. The node of this tree runs several terms of one prompt on one
input plane, each into its own plane folder as graph_banded names them (protect0, protect1, release0); the base node (the
wave-1 sam_plane.py of the base commit 8b626fee, pinned verbatim below by sha256 and checked against git where the history
exists) runs each term on its own, writing and removing its own view. Every term's mask is the base node's to the bit (0
differing values), for float32, bfloat16 and float16 and odd and even sizes, with the SAM 3.1 stand-in of
tests/worker/test_sam_lean.py. The view is written once per prompt, beside the input plane (input.view32.plane), complete; a
new prompt (another run_id), another input or a view left half written by a stopped engine is written again, never reused.
Skipped where torch or CU_COMFY_SOURCE is missing:
    CU_COMFY_SOURCE=<ComfyUI folder> python -B -m unittest tests.worker.test_gpu_nodes_sam_view   (from the artegra-enhancer folder)."""
import hashlib
import importlib.util
import subprocess
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

BASE_COMMIT = '8b626fee5006ea1f10a90b7a67bc29f49ab56e45'
BASE_SHA256 = '6db02114aba7af789b8ade6f7c0a17880bbd674a6a3aa082973f91bccb4be99e'
BASE_SAM_PLANE = r'''"""CUSam3DetectLean: eng:sam-501's lean SAM on planes (engine design section 2.2 row 2, section 2.6; B3).

The classic lean node, ClaudeSAM3DetectLean (node_pack/claude_creative/sam_lean.py), gives SAM3_Detect's own masks while
upsampling only the kept masks: the stock common_upscale of the input to 1008 x 1008, the detector with orig_size=None, the
same sigmoid, threshold and top-1 per prompt, the kept boxes scaled by [W, H, W, H] in the model dtype, only the kept mask
upsampled by the same F.interpolate, the stock _refine_mask, the union. This node runs that class itself, read-only, as the
loaded classic pack holds it (the pack's _classic_pack lookup; the classic file is never copied or edited). What differs is
the image it is given: the classic passes LoadImage's float32 [1, H, W, 3] of the padded stage input; this node passes the
same values from the u8 input plane through the T2 table (engine/planes.U8_TO_F32, LoadImage's own float32(k) / 255), written
once to a float32 plane in the node's plane folder and handed over as a tensor on its memory map (file-backed pages,
BHWC-contiguous as LoadImage's tensor is). The mask is written float32 H x W x 1 at the input size, at
<plane_dir>/mask.plane, which CUMaskUnionPlane and CUPlaneCheckpoint read. The float32 view plane is removed afterwards."""
import os

from . import _engine, PlaneRef, NotBuilt, _out, _progress, _RUN, _DIR, _classic_pack

VIEW_BAND = 1152          # rows per band when the float32 view is written (a memory bound only)


def lean_class():
    """The classic pack's ClaudeSAM3DetectLean, as ComfyUI loaded it."""
    cls = _classic_pack().NODE_CLASS_MAPPINGS.get('ClaudeSAM3DetectLean')
    if cls is None:
        raise NotBuilt('the classic node pack in this engine has no lean SAM node (ClaudeSAM3DetectLean)')
    return cls


def float_view(pre, path, run_id, band=VIEW_BAND):
    """The input plane's float32 values (T2 for u8), RGB, as a plane (LoadImage's values, without decoding an image)."""
    import numpy as np
    planes = _engine('planes')
    H, W, C = pre.shape
    if C < 3:
        raise ValueError('CUSam3DetectLean needs an RGB input plane')
    out = planes.Plane.create(path, (H, W, 3), 'f32', producer='CUSam3DetectLean view', run_id=run_id)
    for y in range(0, H, band):
        rows = pre.read_rows(y, min(H, y + band))[..., :3]
        out.write_rows(y, planes.U8_TO_F32[rows] if rows.dtype == np.uint8 else rows.astype(np.float32))
    return out


class CUSam3DetectLean:
    """The classic lean SAM on the input plane (module docstring): mask f32 [I] x 1 out."""
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"model": ("MODEL",), "image": ("PLANE",), "conditioning": ("CONDITIONING",),
                             "threshold": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01}),
                             "refine_iterations": ("INT", {"default": 2, "min": 0, "max": 5}), **_DIR, **_RUN}}
    RETURN_TYPES = ("PLANE",)
    FUNCTION = "run"
    CATEGORY = "claude_banded"

    def run(self, model, image, conditioning, threshold, refine_iterations, plane_dir, run_id):
        import gc
        import torch
        if not plane_dir:
            raise ValueError('CUSam3DetectLean needs its plane folder')
        planes = _engine('planes')
        lean = lean_class()
        pre = image.plane()
        H, W = pre.shape[:2]
        view_plane = float_view(pre, _out(plane_dir, 'view32'), run_id)
        try:
            view = torch.from_numpy(view_plane.map('r+'))[None]
            masks = lean().run(model, view, conditioning, threshold, refine_iterations, False)[0]
            del view
            if tuple(masks.shape) != (1, H, W):
                raise AssertionError(f'the lean SAM node gave masks of {tuple(masks.shape)}, expected (1, {H}, {W})')
            m = masks[0].detach().cpu().float()
            del masks
            out = planes.Plane.create(_out(plane_dir, 'mask'), (H, W, 1), 'f32', producer='CUSam3DetectLean', run_id=run_id)
            for y in range(0, H, VIEW_BAND):
                out.write_rows(y, m[y:y + VIEW_BAND].numpy())
            del m
            out.finish()
        finally:
            gc.collect()
            try:
                os.unlink(view_plane.path)
            except OSError:
                pass
        return (PlaneRef(out.path, run_id),)
'''


def base_module(pack):
    """The base node as a module of the loaded pack (its relative imports bound to that pack's helpers)."""
    src = BASE_SAM_PLANE.encode('ascii')
    if hashlib.sha256(src).hexdigest() != BASE_SHA256:
        raise AssertionError("the pinned base sam_plane.py is not the base commit's")
    name = pack.__name__ + '.sam_plane_base'
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = pack.__name__
    sys.modules[name] = mod
    exec(compile(src, 'sam_plane.py@8b626fee', 'exec'), mod.__dict__)
    return mod


@unittest.skipUnless(HAVE_TORCH and COMFY, 'needs torch and CU_COMFY_SOURCE (the runtime ComfyUI folder)')
class OneViewPerStage(unittest.TestCase):
    Fixtures = _sam_fixtures.LeanSamAgainstComfyUIsSam3Detect      # its stand-ins (a class attribute: not collected again)

    @classmethod
    def setUpClass(cls):
        import torch
        cls.torch = torch
        cls.Fixtures.setUpClass()
        cls.fx = cls.Fixtures('test_no_kept_object')
        cls.sp = H.module('sam_plane')
        cls.pack = H.load_pack()
        cls.base = base_module(cls.pack)
        cls.classic = H.fake_classic_pack('cu_fake_classic_for_sam_view',
                                          mappings={'ClaudeSAM3DetectLean': cls.Fixtures.lean_mod.ClaudeSAM3DetectLean})

    @classmethod
    def tearDownClass(cls):
        sys.modules.pop(cls.pack.__name__ + '.sam_plane_base', None)

    def u8_image(self, h, w, seed):
        f = self.fx.image(h, w, seed)[0].numpy()
        return np.clip(np.round(f * 255), 0, 255).astype(np.uint8)

    def modules(self):
        return mock.patch.dict(sys.modules, dict(self.Fixtures.modules, cu_fake_classic_for_sam_view=self.classic))

    def terms(self, dtype, seed):
        return [(self.fx.model(dtype, seed=seed), self.fx.cond(seed), 2, 'protect0'),
                (self.fx.model(dtype, seed=seed + 1, hot=6), self.fx.cond(seed + 1, multi=(1, 3)), 2, 'protect1'),
                (self.fx.model(dtype, seed=seed + 2), self.fx.cond(seed + 2), 0, 'release0')]

    def mask(self, ref, shape):
        return planes.validate(ref.path, shape=shape + (1,), dtype='f32').read_rows(0, shape[0])[..., 0]

    def test_every_term_is_the_base_nodes_mask_and_the_view_is_written_once(self):
        torch = self.torch
        n = 0
        for dtype in (torch.float32, torch.bfloat16, torch.float16):
            for (h, w), seed in (((101, 333), 0), ((256, 128), 1)):
                u8 = self.u8_image(h, w, seed)
                with tempfile.TemporaryDirectory() as td, self.modules():
                    d = Path(td)
                    base_in = planes.from_array(d / 'base' / 'input.plane', u8)
                    stage_in = planes.from_array(d / 'stage' / 'input.plane', u8)
                    calls = []
                    real = self.sp.float_view

                    def counted(*a, **k):
                        calls.append(a[1])
                        return real(*a, **k)
                    for model, cond, it, role in self.terms(dtype, seed):
                        want = self.base.CUSam3DetectLean().run(model, self.pack.PlaneRef(base_in.path, 'r1'), cond, 0.6, it,
                                                                str(d / 'base' / role), 'r1')[0]
                        with mock.patch.object(self.sp, 'float_view', counted):
                            got = self.sp.CUSam3DetectLean().run(model, self.pack.PlaneRef(stage_in.path, 'r1'), cond, 0.6,
                                                                 it, str(d / 'stage' / role), 'r1')[0]
                        a, b = self.mask(want, (h, w)), self.mask(got, (h, w))
                        self.assertEqual(int((a.view(np.uint32) != b.view(np.uint32)).sum()), 0, (dtype, h, w, role))
                        self.assertEqual(sorted(x.name for x in (d / 'stage' / role).iterdir()), ['mask.plane'])
                        n += 1
                    self.assertEqual([Path(c).name for c in calls], ['input.view32.plane'])          # once per prompt
                    v = planes.validate(d / 'stage' / 'input.view32.plane', shape=(h, w, 3), dtype='f32')
                    self.assertEqual(v.header['run_id'], 'r1')
                    np.testing.assert_array_equal(v.read_rows(0, h), planes.U8_TO_F32[u8])
                    self.assertFalse((d / 'base' / 'input.view32.plane').exists())                 # the base removes its own
        self.assertEqual(n, 18)

    def test_a_new_prompt_another_input_or_a_half_written_view_is_written_again(self):
        torch = self.torch
        model, cond = self.fx.model(torch.float32, seed=7), self.fx.cond(7)
        u8 = self.u8_image(120, 90, 7)
        with tempfile.TemporaryDirectory() as td, self.modules():
            d = Path(td)
            stage_in = planes.from_array(d / 'input.plane', u8)
            want = self.base.CUSam3DetectLean().run(model, self.pack.PlaneRef(stage_in.path, 'r0'), cond, 0.6, 2,
                                                    str(d / 'b0'), 'r0')[0]
            want = self.mask(want, (120, 90))
            calls = []
            real = self.sp.float_view

            def counted(*a, **k):
                calls.append(a[2])
                return real(*a, **k)

            def run(run_id, role, ref_path=None):
                with mock.patch.object(self.sp, 'float_view', counted):
                    got = self.sp.CUSam3DetectLean().run(model, self.pack.PlaneRef(ref_path or stage_in.path, run_id), cond,
                                                         0.6, 2, str(d / role), run_id)[0]
                m = self.mask(got, (120, 90))
                self.assertEqual(int((m.view(np.uint32) != want.view(np.uint32)).sum()), 0, role)
            run('r1', 't0')
            run('r1', 't1')
            run('r2', 't2')                                          # another prompt: its own view
            self.assertEqual(calls, ['r1', 'r2'])
            view = d / 'input.view32.plane'
            p = planes.Plane.open(view)
            p.header['complete'] = False                             # as a stopped engine leaves it
            with open(view, 'r+b') as f:
                f.write(p._header_bytes())
            run('r2', 't3')
            self.assertEqual(calls, ['r1', 'r2', 'r2'])
            other = planes.from_array(d / 'other' / 'input.plane', u8)
            run('r2', 't4', ref_path=other.path)                      # another folder's input: its own view
            self.assertEqual(calls, ['r1', 'r2', 'r2', 'r2'])
            self.assertTrue((d / 'other' / 'input.view32.plane').is_file())
            q = planes.Plane.open(view)                               # the same name over another input's values
            q.header['producer'] = 'CUSam3DetectLean view of ' + '0' * 64
            with open(view, 'r+b') as f:
                f.write(q._header_bytes())
            run('r2', 't5')
            self.assertEqual(calls, ['r1', 'r2', 'r2', 'r2', 'r2'])

    def test_the_pinned_base_is_the_base_commits_file(self):
        root = H.ROOT.parent
        try:
            got = subprocess.run(['git', 'show', f'{BASE_COMMIT}:artegra-enhancer/node_pack/claude_banded/sam_plane.py'],
                                 cwd=root, capture_output=True, timeout=60)
        except (OSError, subprocess.TimeoutExpired):
            self.skipTest('no git here')
        if got.returncode != 0:
            self.skipTest('the base commit is not in this checkout')
        self.assertEqual(hashlib.sha256(got.stdout.replace(b'\r\n', b'\n')).hexdigest(), BASE_SHA256)


if __name__ == '__main__':
    unittest.main()
