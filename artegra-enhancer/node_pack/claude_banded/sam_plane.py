"""CUSam3DetectLean: eng:sam-501's lean SAM on planes (engine design section 2.2 row 2, section 2.6; B3).

The classic lean node, ClaudeSAM3DetectLean (node_pack/claude_creative/sam_lean.py), gives SAM3_Detect's own masks while
upsampling only the kept masks: the stock common_upscale of the input to 1008 x 1008, the detector with orig_size=None, the
same sigmoid, threshold and top-1 per prompt, the kept boxes scaled by [W, H, W, H] in the model dtype, only the kept mask
upsampled by the same F.interpolate, the stock _refine_mask, the union. This node runs that class itself, read-only, as the
loaded classic pack holds it (the pack's _classic_pack lookup; the classic file is never copied or edited). What differs is
the image it is given: the classic passes LoadImage's float32 [1, H, W, 3] of the padded stage input; this node passes the
same values from the u8 input plane through the T2 table (engine/planes.U8_TO_F32, LoadImage's own float32(k) / 255), written
to a float32 plane and handed over as a tensor on its memory map (file-backed pages, BHWC-contiguous as LoadImage's tensor
is). The mask is written float32 H x W x 1 at the input size, at <plane_dir>/mask.plane, which CUMaskUnionPlane and
CUPlaneCheckpoint read.

5.0.2 wave 2 (gpu-nodes check G3): the float32 view is written ONCE per stage, beside the input plane (input.plane ->
input.view32.plane), and every SAM term of the same prompt (the protect and release terms all read the one input plane)
reuses it: a view is reused only when it is complete and records this prompt's run_id and the input plane's own sha256, else
it is written again. The view is the same values whichever term writes it, and the classic lean node only reads its image
(common_upscale and the refinement crops), so the masks are the base node's to the bit. The view stays until the stage's
plane folder is removed after the stage (service/banded_runner.run_stage), 12 B per input pixel on the work disk for the
rest of the stage, where the base node held it for each term only: plane I/O per stage falls from (3 + 12) B x I per term
to that once."""
from pathlib import Path

from . import _engine, PlaneRef, NotBuilt, _out, _progress, _RUN, _DIR, _classic_pack

VIEW_BAND = 1152          # rows per band when the float32 view is written (a memory bound only)


def lean_class():
    """The classic pack's ClaudeSAM3DetectLean, as ComfyUI loaded it."""
    cls = _classic_pack().NODE_CLASS_MAPPINGS.get('ClaudeSAM3DetectLean')
    if cls is None:
        raise NotBuilt('the classic node pack in this engine has no lean SAM node (ClaudeSAM3DetectLean)')
    return cls


def float_view(pre, path, run_id, band=VIEW_BAND, producer='CUSam3DetectLean view'):
    """The input plane's float32 values (T2 for u8), RGB, as a plane (LoadImage's values, without decoding an image)."""
    import numpy as np
    planes = _engine('planes')
    H, W, C = pre.shape
    if C < 3:
        raise ValueError('CUSam3DetectLean needs an RGB input plane')
    out = planes.Plane.create(path, (H, W, 3), 'f32', producer=producer, run_id=run_id)
    for y in range(0, H, band):
        rows = pre.read_rows(y, min(H, y + band))[..., :3]
        out.write_rows(y, planes.U8_TO_F32[rows] if rows.dtype == np.uint8 else rows.astype(np.float32))
    return out


def view_path(pre_path):
    """The stage's one float32 view, beside its input plane: input.plane -> input.view32.plane."""
    p = Path(pre_path)
    return p.with_name(p.stem + '.view32.plane')


def view_producer(pre):
    """The producer a view records: the input plane's own sha256 (None for a plane not finished: never reused)."""
    return f'CUSam3DetectLean view of {pre.header.get("sha256")}'


def stage_view(pre, run_id, band=VIEW_BAND):
    """(view plane, written): the input plane's float32 view for this prompt, written once and reused by every SAM term of the
    prompt. An existing view is reused only when it is complete, records this run_id and this input's sha256, and has the
    input's size; anything else (another prompt's, another input's, or one a stopped engine left half written) is written
    again."""
    planes = _engine('planes')
    path = view_path(pre.path)
    want = view_producer(pre)
    if pre.header.get('sha256'):
        try:
            v = planes.Plane.open(path, writable=True)        # mapped 'r+' as the written view is (never written)
            if (v.header.get('complete') and v.header.get('run_id') == str(run_id) and v.header.get('producer') == want
                    and v.shape == (pre.shape[0], pre.shape[1], 3) and v.header.get('dtype') == 'f32'):
                return v, False
        except planes.PlaneError:
            pass
    v = float_view(pre, path, run_id, band, producer=want)
    v.finish()
    return v, True


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
        view_plane, _ = stage_view(pre, run_id)
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
            gc.collect()             # the view's map is released before the next term opens it (the file stays)
        return (PlaneRef(out.path, run_id),)
