"""Shared stand-ins of the gpu-nodes worker tests (no tests here). ComfyUI's own code is read from CU_COMFY_SOURCE (the runtime's
ComfyUI folder), each file first checked against runtime/source-manifest.json (tests/worker/test_sam_lean.shipped_source), and
compiled function by function: comfy/utils.py (tiled_scale, common_upscale, lanczos), comfy/sd.py (the VAE's tiled encode and
decode), nodes.py (VAEEncodeTiled, VAEDecodeTiled, ImageScale, ControlNetApplyAdvanced), comfy/controlnet.py (set_cond_hint,
get_control and what they call), comfy_extras/nodes_post_processing.py (gaussian_kernel and ImageBlur's Blur.execute, as
comfy_extras.nodes_post_processing; 5.0.2 wave 2, for the tile hint's memory format). Only the parts that need a card or the full runtime are stand-ins: model_management (no
card; records the loads), the progress bar, the networks."""
import contextlib
import itertools
import logging
import math
import types

from tests.worker.test_sam_lean import COMFY, HAVE_TORCH, extract, shipped_source

VAE_METHODS = ['VAE.encode_tiled', 'VAE.encode_tiled_', 'VAE.decode_tiled', 'VAE.decode_tiled_', 'VAE.vae_encode_crop_pixels',
               'VAE._tile_bounded_shape', 'VAE.spacial_compression_encode', 'VAE.spacial_compression_decode',
               'VAE.temporal_compression_decode', 'VAE.throw_exception_if_invalid', 'VAE.vae_output_dtype']


class Stock:
    """The stock functions and the stand-in modules, built once per test class."""

    def __init__(self):
        import numpy as np
        import torch
        from PIL import Image
        cpu = torch.device('cpu')
        self.torch = torch

        class ProgressBar:
            def __init__(self, total, node_id=None):
                self.total, self.current = total, 0

            def update(self, n):
                self.current += n

            def update_absolute(self, v, total=None, preview=None):
                self.current = v

        mm = types.ModuleType('comfy.model_management')
        mm.calls = []
        mm.current_loaded_models = []
        mm.get_torch_device = lambda: cpu
        mm.intermediate_device = lambda: cpu
        mm.intermediate_dtype = lambda: torch.float32
        mm.load_models_gpu = lambda models, memory_required=0, force_patch_weights=False, minimum_memory_required=None, \
            force_full_load=False: mm.calls.append(('load_models_gpu', tuple(models), memory_required, force_full_load))
        mm.load_model_gpu = lambda model: mm.calls.append(('load_model_gpu', model))
        mm.free_memory = lambda *a, **k: mm.calls.append(('free_memory', a, k))
        mm.cuda_device_context = lambda device: contextlib.nullcontext()
        mm.soft_empty_cache = lambda force=False: None
        mm.processing_interrupted = lambda: False

        class InterruptProcessingException(Exception):
            pass
        mm.InterruptProcessingException = InterruptProcessingException

        class LoadedModel:
            def __init__(self, model):
                self.model = model

            def __eq__(self, other):
                return self.model is other.model

            def model_load(self, lowvram_model_memory=0, force_patch_weights=False):
                mm.calls.append(('model_load', self.model, lowvram_model_memory))

            def model_unload(self, memory_to_free=None, unpatch_weights=True):
                mm.calls.append(('model_unload', self.model, memory_to_free))
                return True
        mm.LoadedModel = LoadedModel
        self.mm = mm

        cu = types.ModuleType('comfy.utils')
        ug = {'torch': torch, 'itertools': itertools, 'math': math, 'np': np, 'Image': Image}
        fns = extract(shipped_source('comfy/utils.py'), 'comfy/utils.py',
                      ['common_upscale', 'lanczos', 'bislerp', 'get_tiled_scale_steps', 'tiled_scale_multidim', 'tiled_scale'], ug)
        ug['tiled_scale_multidim'] = torch.inference_mode()(fns['tiled_scale_multidim'])      # its decorator, as shipped
        for k, v in fns.items():
            setattr(cu, k, ug[k] if k == 'tiled_scale_multidim' else v)
        cu.ProgressBar = ProgressBar
        self.cu = cu
        comfy = types.ModuleType('comfy')
        comfy.__path__ = []
        comfy.utils, comfy.model_management = cu, mm
        self.comfy = comfy

        sg = {'torch': torch, 'comfy': comfy, 'model_management': mm, 'logging': logging, 'math': math, 'ProgressBar': ProgressBar}
        self.vae_fns = {k.split('.')[1]: v for k, v in extract(shipped_source('comfy/sd.py'), 'comfy/sd.py', VAE_METHODS, sg).items()}
        ng = {'torch': torch, 'comfy': comfy}
        self.node_fns = extract(shipped_source('nodes.py'), 'nodes.py',
                                ['VAEEncodeTiled.encode', 'VAEDecodeTiled.decode', 'ImageScale.upscale',
                                 'ControlNetApplyAdvanced.apply_controlnet'], ng)
        nodes = types.ModuleType('nodes')
        nodes.MAX_RESOLUTION = 16384
        nodes.ControlNetApplyAdvanced = type('ControlNetApplyAdvanced', (),
                                             {'apply_controlnet': self.node_fns['ControlNetApplyAdvanced.apply_controlnet']})
        nodes.ImageScale = type('ImageScale', (), {'upscale': self.node_fns['ImageScale.upscale']})
        self.nodes = nodes

        # comfy_extras/nodes_post_processing.py: gaussian_kernel and the ImageBlur node's execute, compiled as shipped; its
        # io.NodeOutput is a stand-in holding the result in .args, as comfy_api's does
        import torch.nn.functional as F

        class NodeOutput:
            def __init__(self, *args, **kw):
                self.args = args
        io_ = types.SimpleNamespace(NodeOutput=NodeOutput)
        pg = {'torch': torch, 'F': F, 'comfy': comfy, 'io': io_}
        pp_src = shipped_source('comfy_extras/nodes_post_processing.py')
        pfn = extract(pp_src, 'comfy_extras/nodes_post_processing.py', ['gaussian_kernel', 'Blur.execute'], pg)
        pg['gaussian_kernel'] = pfn['gaussian_kernel']
        pp = types.ModuleType('comfy_extras.nodes_post_processing')
        pp.gaussian_kernel = pfn['gaussian_kernel']
        pp.Blur = type('Blur', (), {'execute': classmethod(pfn['Blur.execute'])})
        extras = types.ModuleType('comfy_extras')
        extras.__path__ = []
        extras.nodes_post_processing = pp
        self.extras, self.post_processing = extras, pp

    def modules(self):
        """The stand-in modules, for mock.patch.dict(sys.modules, ...)."""
        return {'comfy': self.comfy, 'comfy.utils': self.cu, 'comfy.model_management': self.mm, 'nodes': self.nodes,
                'comfy_extras': self.extras, 'comfy_extras.nodes_post_processing': self.post_processing}

    def controlnet(self):
        """comfy/controlnet.py's ControlBase and ControlNet (set_cond_hint, copy, get_control, control_merge, ...) and
        broadcast_image_to, compiled from the shipped file (its `from __future__ import annotations` kept); the model patcher
        is a stand-in (no weights move on the CPU)."""
        import __future__
        import ast as _ast
        import copy as _copy
        import enum
        import typing
        torch = self.torch
        mp = types.ModuleType('comfy.model_patcher')
        mp.CoreModelPatcher = mp.ModelPatcher = lambda model, load_device=None, offload_device=None, fast_disk=False: \
            types.SimpleNamespace(model=model, load_device=load_device, fast_disk=fast_disk)
        mb = types.ModuleType('comfy.model_base')
        mb.convert_tensor = lambda extra, dtype, device: extra.to(device=device, dtype=dtype)
        self.mm.unet_offload_device = lambda: torch.device('cpu')
        self.mm.cast_to_device = lambda t, device, dtype, copy=False: t.to(device=device, dtype=dtype)
        self.mm.loaded_models = lambda only_currently_used=False: []
        self.comfy.model_patcher, self.comfy.model_base = mp, mb
        src = shipped_source('comfy/controlnet.py')
        tree = _ast.parse(src)
        keep = {'broadcast_image_to', 'StrengthType', 'ControlIsolation', 'ControlBase', 'ControlNet'}
        body = [n for n in tree.body if isinstance(n, (_ast.ClassDef, _ast.FunctionDef)) and n.name in keep]
        g = {'torch': torch, 'comfy': self.comfy, 'Enum': enum.Enum, 'math': math, 'logging': logging, 'copy': _copy,
             'Union': typing.Union, '__name__': 'comfy.controlnet'}
        exec(compile(_ast.Module(body=body, type_ignores=[]), 'comfy/controlnet.py', 'exec',
                     flags=__future__.annotations.compiler_flag, dont_inherit=True), g)
        return types.SimpleNamespace(**{k: g[k] for k in keep})

    def vae(self, model, dtype, memory_scale=1):
        """An SDXL-like VAE (comfy/sd.py VAE's attributes for AutoencoderKL) whose tiled methods are sd.py's own."""
        torch = self.torch
        cls = type('StockVAE', (), dict(self.vae_fns))
        v = cls()
        cpu = torch.device('cpu')
        v.first_stage_model = model.to(dtype)
        v.process_input = lambda image: image * 2.0 - 1.0
        v.process_output = lambda image: image.add_(1.0).div_(2.0).clamp_(0.0, 1.0)
        v.vae_dtype, v.device, v.output_device = dtype, cpu, cpu
        v.downscale_ratio = v.upscale_ratio = 8
        v.latent_channels, v.output_channels, v.latent_dim = 4, 3, 2
        v.crop_input, v.pad_channel_value, v.handles_tiling, v.extra_1d_channel = True, None, False, None
        v.disable_offload, v.format_encoded, v.not_video = False, None, True
        v.patcher = types.SimpleNamespace(name='vae-patcher')
        size = 2 if dtype in (torch.float16, torch.bfloat16) else 4
        v.memory_used_encode = lambda shape, dt: (1767 * shape[2] * shape[3]) * size * memory_scale
        v.memory_used_decode = lambda shape, dt: (2178 * shape[2] * shape[3] * 64) * size * memory_scale
        return v


def tiny_autoencoder(seed):
    """A small deterministic encoder (x8 down, 4 channels) and decoder (x8 up, 3 channels) whose outputs depend on every
    input value and on the tile layout's arithmetic, and that records what each call receives."""
    import torch
    import torch.nn.functional as F

    class TinyAE(torch.nn.Module):
        def __init__(self):
            super().__init__()
            g = torch.Generator().manual_seed(seed)
            self.e1 = torch.nn.Conv2d(3, 8, 3, padding=1)
            self.e2 = torch.nn.Conv2d(8, 8, 4, stride=4)
            self.e3 = torch.nn.Conv2d(8, 4, 2, stride=2)
            self.d1 = torch.nn.Conv2d(4, 8, 3, padding=1)
            self.d2 = torch.nn.Conv2d(8, 3, 3, padding=1)
            with torch.no_grad():
                for p in self.parameters():
                    p.copy_(torch.randn(p.shape, generator=g) * 0.3)
            self.seen = []

        def _see(self, kind, x):
            st = x.stride()
            self.seen.append((kind, tuple(x.shape), str(x.dtype), str(x.device), x.is_contiguous(),
                              x.is_contiguous(memory_format=torch.channels_last), tuple(sorted(range(4), key=lambda d: -st[d]))))

        def encode(self, x):
            self._see('encode', x)
            return self.e3(F.silu(self.e2(F.silu(self.e1(x)))))

        def decode(self, z):
            self._see('decode', z)
            u = F.interpolate(z, scale_factor=8, mode='nearest')
            return torch.tanh(self.d2(F.silu(self.d1(u)))) * 1.15
    return TinyAE()
