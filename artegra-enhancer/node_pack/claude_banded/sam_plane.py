"""CUSam3DetectLean: eng:sam-501's lean SAM on planes (engine design section 2.2 row 2, section 2.6; B3).

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
