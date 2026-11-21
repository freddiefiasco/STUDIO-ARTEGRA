"""The Large-image engine's nodes (Artegra Enhancer 5.0.2; engine design ENGINE-DESIGN.md section 2.2).

A second package beside claude_creative, with its own manifest (node_pack/MANIFEST-banded.json): the classic pack and its
manifest stay byte-identical, so a classic result's recorded tree hash is 5.0.1's. These nodes reuse classic functions by
importing them from claude_creative (read, never patched) and share the app's plane store and band arithmetic
(engine/planes.py, engine/bands.py, engine/dat_bands.py, engine/lanczos_bands.py), loaded by path under a private package name
so nothing global changes (no Pillow guard, numpy allocator, torch flag, thread count or MAX_RESOLUTION; gate G0d).

Pixels live in planes on the work disk. Every node takes `run_id` (the prompt's id), so ComfyUI's cache never reuses a plane
handle across prompts. A plane handle used as a tensor raises (PlaneHint, T12).

BUILD STATE (5.0.2 development branch, after build wave 1): every declared node is built. Here: CUPlaneInput, CUUpscaleCanvas
(banded x4 and banded Lanczos), CUBlurPlane, CUMaskUnionPlane and CUPlaneCheckpoint. In their own modules, imported at the end of
this file after the helpers they take from it: CUCannyPlane (canny_plane.py), CUEncodePlane and CUDecodePlane (vae_planes.py),
ClaudeSpotTilesBanded (spot_banded.py, the registered fork of the classic spot.py, gate G0e; its Brownian cache cap is
noise_banded.py), CUControlNetApplyPlane with PlaneHint (cn_plane.py), CUSam3DetectLean (sam_plane.py) and CUFinishBanded
(bxf/: the fallback ladder, tier 0 the banded exact finish where this environment's G1 table applies, else tier 3, 5.0.1's own
v4_finish and shadow toe run whole on the planes up to FINISH_WHOLE_MAX_MP, refused above). dev_vram.py is the developer-only
graphics-memory cap of the small-card emulation R5 (a release build ignores it). None of these nodes has run on a GPU yet, and no
Large-image plan is admitted: engine/banded_plan.BANDED_PROVEN_MP is 0 until the GPU proof sets it."""
import importlib
import importlib.util
import os
import sys
from pathlib import Path

_ENGINE_DIR = Path(__file__).resolve().parents[2] / 'engine'
_PKG = 'cu_banded_engine'
FINISH_WHOLE_MAX_MP = 300.0          # tier 3 (whole oracle finish) runs only where 5.0.1's finish fits; larger is refused


def _engine(name):
    """engine/<name>.py of this app, under the private package name cu_banded_engine (no sys.path change)."""
    if _PKG not in sys.modules:
        spec = importlib.util.spec_from_file_location(_PKG, _ENGINE_DIR / '__init__.py',
                                                      submodule_search_locations=[str(_ENGINE_DIR)])
        mod = importlib.util.module_from_spec(spec)
        sys.modules[_PKG] = mod
        spec.loader.exec_module(mod)
    return importlib.import_module(f'{_PKG}.{name}')


class NotBuilt(RuntimeError):
    pass


def _classic_pack():
    """The classic node pack as ComfyUI loaded it (its module name is ComfyUI's choice), found by its own node classes."""
    for mod in list(sys.modules.values()):
        m = getattr(mod, 'NODE_CLASS_MAPPINGS', None)
        if isinstance(m, dict) and 'ClaudeV4Finish' in m and 'ClaudeShadowToe' in m and hasattr(mod, 'shadow_toe_u8'):
            return mod
    raise NotBuilt('the classic node pack (claude_creative) is not loaded in this engine')


class PlaneRef:
    """A plane handle passed between nodes: its path and shape. It is not a tensor; any tensor use raises (T12)."""

    def __init__(self, path, run_id):
        self.path = str(path)
        self.run_id = str(run_id)
        p = _engine('planes').Plane.open(self.path)
        self.shape = p.shape
        self.dtype = p.header['dtype']

    def plane(self, writable=False):
        return _engine('planes').Plane.open(self.path, writable=writable)

    def __getattr__(self, name):
        if name in ('to', 'cpu', 'cuda', 'numpy', 'float', 'movedim', 'permute', 'shape_hw', 'dim', 'size', 'device', 'dtype_t'):
            raise TypeError(f'a plane ({os.path.basename(self.path)}) is not a tensor: {name} is not allowed (PlaneHint)')
        raise AttributeError(name)


def _out(plane_dir, role):
    d = Path(plane_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d / f'{role}.plane'


def _progress(total):
    try:
        import comfy.utils
        return comfy.utils.ProgressBar(total)
    except Exception:          # outside ComfyUI (tests)
        class _P:
            def update(self, n):
                pass
        return _P()


_RUN = {"run_id": ("STRING", {"default": ""})}
_DIR = {"plane_dir": ("STRING", {"default": ""})}


class CUPlaneInput:
    """A plane on the work disk (the service's padded stage input, or a checkpointed plane of prompt A), validated."""
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"plane": ("STRING", {"default": ""}), **_RUN}}
    RETURN_TYPES = ("PLANE",)
    FUNCTION = "run"
    CATEGORY = "claude_banded"

    def run(self, plane, run_id):
        _engine('planes').validate(plane, check_sha=True)
        return (PlaneRef(plane, run_id),)


class CUUpscaleCanvas:
    """ClaudeUpscaleModelTiled + ImageScale lanczos (canvas and init) on planes: the classic margin tiling in tile-row bands
    (engine/dat_bands.py, the same sums in the same order), then Pillow's two Lanczos passes on row bands and column strips
    (engine/lanczos_bands.py). At k = 4 the canvas is the x4 output itself, kept float32 as the classic keeps it."""
    @classmethod
    def INPUT_TYPES(cls):
        i = lambda d: ("INT", {"default": d, "min": 1, "max": 65536})
        return {"required": {"upscale_model": ("UPSCALE_MODEL",), "image": ("PLANE",), "render_width": i(1024),
                             "render_height": i(1024), "init_width": i(1024), "init_height": i(1024),
                             "tile": ("INT", {"default": 512, "min": 256, "max": 4096, "step": 32}),
                             "margin": ("INT", {"default": 64, "min": 0, "max": 256}),
                             "blend": ("INT", {"default": 16, "min": 1, "max": 256}),
                             "canvas": (["lanczos-1"], {"default": "lanczos-1"}), **_DIR, **_RUN}}
    RETURN_TYPES = ("PLANE", "PLANE")
    FUNCTION = "run"
    CATEGORY = "claude_banded"

    def run(self, upscale_model, image, render_width, render_height, init_width, init_height, tile, margin, blend, canvas,
            plane_dir, run_id):
        import numpy as np
        import torch
        import comfy.model_management as mm
        planes, dat, lz = _engine('planes'), _engine('dat_bands'), _engine('lanczos_bands')
        src = image.plane()
        H, W, C = src.shape
        scale = int(round(upscale_model.scale))
        if scale != 4:
            raise ValueError('the Large-image engine expects the x4 model')
        device = upscale_model.patcher.load_device
        mem = (tile * tile * 3) * 4 * max(upscale_model.scale, 1.0) * 384.0
        mm.load_models_gpu([upscale_model.patcher], memory_required=mem, force_full_load=True)
        table = planes.U8_TO_F32

        def read(y0, y1, x0, x1):
            return src.read_region(x0, y0, x1, y1)

        def fn(crop):
            t = torch.from_numpy(table[crop]).unsqueeze(0).movedim(-1, -3).to(device)
            with torch.no_grad():
                o = upscale_model(t.float()).float().cpu()
            return o[0].movedim(0, -1).numpy()
        k4 = (render_width, render_height) == (W * scale, H * scale)
        big8 = planes.Plane.create(_out(plane_dir, 'big8'), (H * scale, W * scale, 3), 'u8', producer='CUUpscaleCanvas', run_id=run_id)
        canvas_plane = (planes.Plane.create(_out(plane_dir, 'canvas'), (H * scale, W * scale, 3), 'f32', producer='CUUpscaleCanvas',
                                            run_id=run_id) if k4 else None)
        pbar = _progress(len(_engine('bands').dat_tile_rows(H, W, tile, margin, blend)))

        def sink(y0, rows):
            r = np.clip(rows, np.float32(0.0), np.float32(1.0))
            if canvas_plane is not None:
                canvas_plane.write_rows(y0, r)
            big8.write_rows(y0, dat.to_canvas_u8(r))
            pbar.update(0)
        dat.margin_tiled_banded(read, (H, W, C), fn, scale, sink, tile, margin, blend)
        big8.finish()
        if canvas_plane is None:
            canvas_plane = planes.Plane.create(_out(plane_dir, 'canvas'), (render_height, render_width, 3), 'u8',
                                               producer='CUUpscaleCanvas', run_id=run_id)
            tmp = planes.Plane.create(_out(plane_dir, 'canvas-h'), (H * scale, render_width, 3), 'u8', run_id=run_id)
            lz.resize(big8, canvas_plane, tmp)
            os.unlink(tmp.path)
        canvas_plane.finish()
        init = planes.Plane.create(_out(plane_dir, 'init'), (init_height, init_width, 3), 'u8', producer='CUUpscaleCanvas',
                                   run_id=run_id)
        tmp = planes.Plane.create(_out(plane_dir, 'init-h'), (H * scale, init_width, 3), 'u8', run_id=run_id)
        lz.resize(big8, init, tmp)
        os.unlink(tmp.path)
        init.finish()
        return (PlaneRef(canvas_plane.path, run_id), PlaneRef(init.path, run_id))


class CUBlurPlane:
    """ComfyUI's ImageBlur on a plane, by bands on the card: the stock reflect pad and depthwise conv2d per band with
    blur_radius real rows above and below; reflection only at the true image border. Output float32, as the classic's."""
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"canvas": ("PLANE",), "blur_radius": ("INT", {"default": 1, "min": 1, "max": 31}),
                             "sigma": ("FLOAT", {"default": 1.0, "min": 0.1, "max": 10.0, "step": 0.1}), **_DIR, **_RUN}}
    RETURN_TYPES = ("PLANE",)
    FUNCTION = "run"
    CATEGORY = "claude_banded"

    def run(self, canvas, blur_radius, sigma, plane_dir, run_id):
        import numpy as np
        import torch
        import torch.nn.functional as F
        import comfy.model_management as mm
        from comfy_extras.nodes_post_processing import gaussian_kernel
        planes, bands = _engine('planes'), _engine('bands')
        src = canvas.plane()
        H, W, C = src.shape
        out = planes.Plane.create(_out(plane_dir, 'hint'), (H, W, C), 'f32', producer='CUBlurPlane', run_id=run_id)
        r = int(blur_radius)
        dev = mm.get_torch_device()
        ks = r * 2 + 1
        kernel = gaussian_kernel(ks, sigma, device=dev).repeat(C, 1, 1).unsqueeze(1)
        for b in bands.bands(H, 288, halo=r):
            rows = src.read_rows(b.read_start, b.read_stop)
            x = torch.from_numpy(planes.U8_TO_F32[rows] if rows.dtype == np.uint8 else rows).unsqueeze(0).to(dev)
            x = x.permute(0, 3, 1, 2)
            top = r if b.read_start == 0 else 0
            bot = r if b.read_stop == H else 0
            x = F.pad(x, (r, r, 0, 0), 'reflect')
            if top or bot:
                x = F.pad(x, (0, 0, top, bot), 'reflect')
            y = F.conv2d(x, kernel, padding=ks // 2, groups=C)[:, :, r:-r, r:-r]
            lo = b.core_offset + top - r
            y = y[:, :, lo:lo + b.rows].permute(0, 2, 3, 1)
            out.write_rows(b.start, y[0].cpu().numpy())
        out.finish()
        return (PlaneRef(out.path, run_id),)


class CUMaskUnionPlane:
    """ClaudeMaskUnion on mask planes (float32 H x W x 1): the element-wise maximum, by bands."""
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {**_DIR, **_RUN}, "optional": {f"mask_{i}": ("PLANE",) for i in range(1, 9)}}
    RETURN_TYPES = ("PLANE",)
    FUNCTION = "run"
    CATEGORY = "claude_banded"

    def run(self, plane_dir, run_id, **masks):
        import numpy as np
        planes, bands = _engine('planes'), _engine('bands')
        ms = [masks[f'mask_{i}'].plane() for i in range(1, 9) if masks.get(f'mask_{i}') is not None]
        if not ms:
            raise ValueError('CUMaskUnionPlane: connect at least one mask')
        shape = ms[0].shape
        if any(m.shape != shape for m in ms):
            raise ValueError('CUMaskUnionPlane: masks of different sizes')
        out = planes.Plane.create(_out(plane_dir, 'union'), shape, 'f32', producer='CUMaskUnionPlane', run_id=run_id)
        for b in bands.bands(shape[0], 2304):
            u = None
            for m in ms:
                a = m.read_rows(b.start, b.stop).astype(np.float32)
                u = a if u is None else np.maximum(u, a)
            out.write_rows(b.start, u)
        out.finish()
        return (PlaneRef(out.path, run_id),)


class CUPlaneCheckpoint:
    """The end of prompt A of a split stage (L3r): the decoded passes, init and the masks are on disk and complete."""
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"filename_prefix": ("STRING", {"default": "cu"}), **_DIR, **_RUN},
                "optional": {r: ("PLANE",) for r in ('creative', 'structure', 'init', 'protect', 'release')}}
    RETURN_TYPES = ()
    FUNCTION = "run"
    OUTPUT_NODE = True
    CATEGORY = "claude_banded"

    def run(self, filename_prefix, plane_dir, run_id, **planes_in):
        import shutil
        planes = _engine('planes')
        out = []
        for role, ref in planes_in.items():
            if ref is None:
                continue
            p = planes.validate(ref.path, check_sha=False)
            want = _out(plane_dir, role)               # prompt B reads each role at <plane_dir>/<role>.plane
            if Path(p.path).resolve() != want.resolve():
                try:
                    os.link(p.path, want)
                except OSError:
                    shutil.copyfile(p.path, want)
            out.append({'role': role, 'path': str(want), 'sha256': p.header.get('sha256')})
        return {"ui": {"planes": out}}


def _not_built(name, required, outputs, optional=None):
    """A node that is declared (so graphs validate and the service can name it) but not built in this version."""
    def INPUT_TYPES(cls):
        req = {k: ("*",) for k in required}
        return {"required": req, "optional": {k: ("*",) for k in (optional or ())}}

    def run(self, **kw):
        raise NotBuilt(f'{name} is not built in this version of the Large-image engine')
    return type(name, (), {'INPUT_TYPES': classmethod(INPUT_TYPES), 'RETURN_TYPES': tuple(outputs), 'FUNCTION': 'run',
                           'CATEGORY': 'claude_banded', 'run': run, 'NOT_BUILT': True})


_SPECS = {}          # declared nodes not built yet: none since build wave 1 (each maps to _not_built(name, *spec))

# The nodes built in their own modules (5.0.2 build wave 1). Imported here, after the helpers above, because each module takes
# them from this package ("from . import _engine, PlaneRef, ..."); ComfyUI registers the package in sys.modules before it runs
# this file, so these relative imports resolve.
from .canny_plane import CUCannyPlane  # noqa: E402
from .vae_planes import CUEncodePlane, CUDecodePlane  # noqa: E402
from .spot_banded import ClaudeSpotTilesBanded  # noqa: E402
from .cn_plane import CUControlNetApplyPlane  # noqa: E402
from .sam_plane import CUSam3DetectLean  # noqa: E402
from .bxf import CUFinishBanded  # noqa: E402
from . import dev_vram  # noqa: E402,F401  (developer-only VRAM cap for R5)

NODE_CLASS_MAPPINGS = {
    'CUPlaneInput': CUPlaneInput, 'CUUpscaleCanvas': CUUpscaleCanvas, 'CUBlurPlane': CUBlurPlane,
    'CUMaskUnionPlane': CUMaskUnionPlane, 'CUPlaneCheckpoint': CUPlaneCheckpoint, 'CUFinishBanded': CUFinishBanded,
    'CUCannyPlane': CUCannyPlane, 'CUEncodePlane': CUEncodePlane, 'CUDecodePlane': CUDecodePlane,
    'ClaudeSpotTilesBanded': ClaudeSpotTilesBanded, 'CUControlNetApplyPlane': CUControlNetApplyPlane,
    'CUSam3DetectLean': CUSam3DetectLean,
    **{name: _not_built(name, *spec) for name, spec in _SPECS.items()},
}
NODE_DISPLAY_NAME_MAPPINGS = {k: k for k in NODE_CLASS_MAPPINGS}
BUILT = sorted(k for k, v in NODE_CLASS_MAPPINGS.items() if not getattr(v, 'NOT_BUILT', False))
NOT_BUILT = sorted(k for k, v in NODE_CLASS_MAPPINGS.items() if getattr(v, 'NOT_BUILT', False))
