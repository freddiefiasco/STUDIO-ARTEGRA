"""Gate G0d for the gpu-nodes modules on the worker's own libraries: importing canny_plane, vae_planes, spot_banded,
noise_banded, cn_plane and sam_plane (a fresh copy of the pack each time), and running the fork's node, changes no global
state: torch's thread counts, default dtype, grad mode, matmul and cuDNN flags, the attention settings, numpy's error and print
settings, Pillow's MAX_IMAGE_PIXELS and ComfyUI's MAX_RESOLUTION. And the classic nodes give the same bytes before and after:
ClaudeCannyTiled (kornia) on a CPU canvas, and ClaudeV4Finish's v4_finish with 5.0.1's options on synthetic passes.
Skipped where torch is missing (kornia/scipy for the classic-bytes part)."""
import importlib
import importlib.util
import sys
import types
import unittest
from unittest import mock

import numpy as np

from tests import test_gpu_nodes_helpers as H

HAVE_TORCH = importlib.util.find_spec('torch') is not None
HAVE_CLASSIC = HAVE_TORCH and all(importlib.util.find_spec(m) is not None for m in ('kornia', 'scipy', 'PIL'))
MODULES = ('canny_plane', 'vae_planes', 'spot_banded', 'noise_banded', 'cn_plane', 'sam_plane')


def torch_state():
    import torch
    m = torch.backends.cuda.matmul
    sdp = None
    try:
        from torch.backends import cuda as bc
        sdp = (bc.flash_sdp_enabled(), bc.cudnn_sdp_enabled(), bc.mem_efficient_sdp_enabled(), bc.math_sdp_enabled(),
               tuple(int(x) for x in torch._C._get_sdp_priority_order()))
    except Exception:
        pass
    return {'threads': torch.get_num_threads(), 'interop': torch.get_num_interop_threads(),
            'dtype': str(torch.get_default_dtype()), 'grad': torch.is_grad_enabled(),
            'inference': torch.is_inference_mode_enabled(), 'deterministic': torch.are_deterministic_algorithms_enabled(),
            'f32_matmul': torch.get_float32_matmul_precision(), 'tf32': m.allow_tf32,
            'fp16_red': m.allow_fp16_reduced_precision_reduction, 'bf16_red': m.allow_bf16_reduced_precision_reduction,
            'fp16_acc': getattr(m, 'allow_fp16_accumulation', None), 'cudnn': (torch.backends.cudnn.enabled,
                                                                              torch.backends.cudnn.benchmark,
                                                                              torch.backends.cudnn.deterministic,
                                                                              torch.backends.cudnn.allow_tf32),
            'mkldnn': torch.backends.mkldnn.enabled, 'sdp': sdp}


def other_state(nodes):
    from PIL import Image
    return (Image.MAX_IMAGE_PIXELS, nodes.MAX_RESOLUTION, np.geterr(), np.get_printoptions(), list(sys.path),
            sys.getrecursionlimit())


def fresh_pack(n):
    name = f'claude_banded_g0d_worker_{n}'
    spec = importlib.util.spec_from_file_location(name, H.PACK_DIR / '__init__.py', submodule_search_locations=[str(H.PACK_DIR)])
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return name


@unittest.skipUnless(HAVE_TORCH, 'torch is not installed here (run on the worker runtime)')
class G0dOnTheWorkerLibraries(unittest.TestCase):
    def test_importing_each_module_changes_no_global_state(self):
        import torch  # noqa: F401  (loaded first, as in a worker)
        nodes = types.ModuleType('nodes')
        nodes.MAX_RESOLUTION = 16384
        with mock.patch.dict(sys.modules, {'nodes': nodes}):
            for i, m in enumerate(MODULES):
                name = fresh_pack(i)
                before = (torch_state(), other_state(nodes))
                mods = set(sys.modules)
                importlib.import_module(f'{name}.{m}')
                self.assertEqual((torch_state(), other_state(nodes)), before, m)
                self.assertEqual({x for x in set(sys.modules) - mods if not x.startswith(name)}, set(), m)
                for x in [x for x in sys.modules if x.startswith(name)]:
                    del sys.modules[x]

    def test_the_fork_node_changes_no_global_state(self):
        fork = H.module('spot_banded')
        classic = H.fake_classic_pack('cu_fake_classic_for_g0d')
        pe = types.ModuleType('comfy.patcher_extension')
        pe.WrappersMP = types.SimpleNamespace(CALC_COND_BATCH='a', PREPARE_SAMPLING='b', OUTER_SAMPLE='c')
        comfy = types.ModuleType('comfy')
        comfy.__path__ = []
        cu = types.ModuleType('comfy.utils')
        comfy.patcher_extension, comfy.utils = pe, cu

        class M:
            def clone(self):
                return self

            def add_wrapper_with_key(self, *a):
                pass
        nodes = types.ModuleType('nodes')
        nodes.MAX_RESOLUTION = 16384
        mods = {'comfy': comfy, 'comfy.patcher_extension': pe, 'comfy.utils': cu, 'cu_fake_classic_for_g0d': classic,
                'nodes': nodes}
        with mock.patch.dict(sys.modules, mods):
            before = (torch_state(), other_state(nodes))
            fork.ClaudeSpotTilesBanded().apply(M(), 1024, 1, clamp_blend=True, noise_prefetch=True, fp16_acc_scoped=True,
                                               batch_windows=2, brownian_cache=8)
            self.assertEqual((torch_state(), other_state(nodes)), before)


def classic_canny_bytes():
    import torch
    from tests.worker.test_gpu_nodes_canny import canvas, classic_canny_run
    from engine import planes
    img = torch.from_numpy(planes.U8_TO_F32[canvas(300, 520, 7)])[None]
    return classic_canny_run()(None, img, 0.2, 0.45, 256, device=torch.device('cpu'))[0].numpy().tobytes()


def classic_finish_bytes():
    spec = importlib.util.spec_from_file_location('cu_v4finish_g0d', H.ROOT / 'node_pack' / 'claude_creative' / 'v4finish.py')
    v4 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v4)
    rng = np.random.default_rng(3)
    h, w = 192, 256
    pre = rng.random((h // 2, w // 2, 3)).astype(np.float32)
    base = np.repeat(np.repeat(pre, 2, 0), 2, 1)
    cr = np.clip(base + rng.normal(0, 0.05, base.shape), 0, 1).astype(np.float32)
    st = np.clip(base + rng.normal(0, 0.02, base.shape), 0, 1).astype(np.float32)
    a = [v4.quantize_8bit(x) for x in (cr, st, base, pre)]
    o = v4.v4_finish(*a, None, smooth=(0.2, 0.5), keep_blacks='render', lf='hybmin', clamp='agree5', glow='skygaps',
                     island_after_lf=True)
    return v4.to_u8(o).tobytes()


@unittest.skipUnless(HAVE_CLASSIC, 'needs torch, kornia, scipy and Pillow (run on the worker runtime)')
class G0dTheClassicNodesGiveTheSameBytes(unittest.TestCase):
    def test_before_and_after_importing_the_modules(self):
        canny0, fin0 = classic_canny_bytes(), classic_finish_bytes()
        name = fresh_pack('bytes')
        for m in MODULES:
            importlib.import_module(f'{name}.{m}')
        self.assertEqual(classic_canny_bytes(), canny0)
        self.assertEqual(classic_finish_bytes(), fin0)
        for x in [x for x in sys.modules if x.startswith(name)]:
            del sys.modules[x]


if __name__ == '__main__':
    unittest.main()
