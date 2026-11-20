"""CUCannyPlane: ClaudeCannyTiled on the canvas plane (engine design section 2.2 row 5; B5).

The classic node (node_pack/claude_creative/__init__.py, ClaudeCannyTiled) runs kornia's canny with hysteresis off on
2048 px tiles of the canvas with an 8 px margin, keeps each tile's core, and then runs hysteresis on the CPU as one
scipy.ndimage.label of the whole low mask (8-connected), keeping every component that holds a strong pixel. This node does
the same, on planes:
- the same tiles on the same global grid (y outer, x inner; margin 8 clipped at the true border), each crop read from the
  canvas plane (u8 through the T2 table, or float32 at k = 4, where the canvas is the x4 output itself), moved to the card as
  float32 and viewed channels-first exactly as the classic's crop is (`.to(device, float32).movedim(-1, 1)`), and the same
  kornia call with the same thresholds;
- the low and strong masks of a tile row are written to two 1-byte planes;
- hysteresis is the same label call (structure ones(3, 3)) over the whole low plane, its output an int32 mapped plane
  (`output=`; the pages are file-backed), and the kept set is the classic's `np.unique(lab[high])`, collected band by band;
- the edges are written u8, one channel, 0 or 1, at <plane_dir>/edges.plane (ClaudeCannyTiled's 0/1 float edges; the spot
  fork expands them to 3 channels per window as the classic's output is, cn_plane.window_tensor).
Progress is reported per tile row. The temporary planes are removed."""
import os

from . import _engine, PlaneRef, NotBuilt, _out, _progress, _RUN, _DIR, _classic_pack

MARGIN = 8              # ClaudeCannyTiled's M: blur 2 + Sobel 1 + NMS 1 = 4 px reach, doubled
HYSTERESIS_BAND = 2304  # rows per band of the kept-set and write passes (a memory bound only; the result does not depend on it)


def tile_grid(H, W, tile, margin=MARGIN):
    """ClaudeCannyTiled's tiles in its order, grouped by tile row: (y0, y1, x0, x1, ya, xa, yb, xb) with the core
    [y0:y1, x0:x1] and the crop read [ya:yb, xa:xb]."""
    rows = []
    for y0 in range(0, H, tile):
        row = []
        for x0 in range(0, W, tile):
            y1, x1 = min(H, y0 + tile), min(W, x0 + tile)
            ya, xa, yb, xb = max(0, y0 - margin), max(0, x0 - margin), min(H, y1 + margin), min(W, x1 + margin)
            row.append((y0, y1, x0, x1, ya, xa, yb, xb))
        rows.append(row)
    return rows


def _mask(plane, mode='r'):
    """A 1-channel plane's map as an H x W array (a view of the memory map)."""
    return plane.map(mode)[..., 0]


def hysteresis(low_plane, high_plane, lab_plane, out_plane, band=HYSTERESIS_BAND):
    """ClaudeCannyTiled's hysteresis on planes. low/high: u8 0/1 planes (H x W x 1); lab_plane: an int32 plane of the same
    shape (the label output, mapped); out_plane: the u8 edges plane, written keep[lab] by bands. Returns the component count."""
    import numpy as np
    from scipy.ndimage import label
    low = _mask(low_plane).view(np.bool_)
    lab = _mask(lab_plane, 'r+')
    n = label(low, structure=np.ones((3, 3), bool), output=lab)
    H = low.shape[0]
    keep = np.zeros(n + 1, bool)
    high_map = _mask(high_plane).view(np.bool_)
    for y in range(0, H, band):
        keep[np.unique(lab[y:y + band][high_map[y:y + band]])] = True
    keep[0] = False
    for y in range(0, H, band):
        out_plane.write_rows(y, keep[lab[y:y + band]].view(np.uint8))
    del low, lab, high_map
    return int(n)


class CUCannyPlane:
    """ClaudeCannyTiled on planes (module docstring): canvas plane in, edges u8 [R] x 1 (0/1) out."""
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"canvas": ("PLANE",),
                             "low_threshold": ("FLOAT", {"default": 0.4, "min": 0.01, "max": 0.99, "step": 0.01}),
                             "high_threshold": ("FLOAT", {"default": 0.8, "min": 0.01, "max": 0.99, "step": 0.01}),
                             "tile": ("INT", {"default": 2048, "min": 256, "max": 16384, "step": 64}), **_DIR, **_RUN}}
    RETURN_TYPES = ("PLANE",)
    FUNCTION = "run"
    CATEGORY = "claude_banded"

    def run(self, canvas, low_threshold, high_threshold, tile, plane_dir, run_id, device=None):
        import numpy as np
        import torch
        from kornia.filters import canny
        if not plane_dir:
            raise ValueError('CUCannyPlane needs the stage plane folder')
        if device is None:
            import comfy.model_management as mm
            device = mm.get_torch_device()
        planes = _engine('planes')
        src = canvas.plane()
        H, W, C = src.shape
        if C < 3:
            raise ValueError('CUCannyPlane needs an RGB canvas plane')
        table = planes.U8_TO_F32
        made = []

        def plane(role, dtype):
            p = planes.Plane.create(_out(plane_dir, role), (H, W, 1), dtype, producer='CUCannyPlane', run_id=run_id)
            made.append(p)
            return p
        low_p, high_p = plane('edges-low', 'u8'), plane('edges-high', 'u8')
        grid = tile_grid(H, W, int(tile))
        pbar = _progress(len(grid))
        try:
            for row in grid:
                ry0, ry1, rya, ryb = row[0][0], row[0][1], row[0][4], row[0][6]
                block = src.read_rows(rya, ryb)
                low = np.zeros((ry1 - ry0, W), bool)
                high = np.zeros((ry1 - ry0, W), bool)
                for (y0, y1, x0, x1, ya, xa, yb, xb) in row:
                    crop = block[:, xa:xb, :3]
                    crop = table[crop] if crop.dtype == np.uint8 else np.ascontiguousarray(crop, dtype=np.float32)
                    t = torch.from_numpy(np.ascontiguousarray(crop))[None].to(device=device, dtype=torch.float32).movedim(-1, 1)
                    e = canny(t, low_threshold, high_threshold, hysteresis=False)[1][0, 0, y0 - ya:y1 - ya, x0 - xa:x1 - xa]
                    low[:, x0:x1] = (e > 0).cpu().numpy()
                    high[:, x0:x1] = (e == 1).cpu().numpy()
                    del t, e
                low_p.write_rows(ry0, low.view(np.uint8))
                high_p.write_rows(ry0, high.view(np.uint8))
                del block, low, high
                pbar.update(1)
            lab_p = plane('edges-label', 'i32')
            edges = planes.Plane.create(_out(plane_dir, 'edges'), (H, W, 1), 'u8', producer='CUCannyPlane', run_id=run_id)
            hysteresis(low_p, high_p, lab_p, edges)
            edges.finish()
        finally:
            _remove(made)
        return (PlaneRef(edges.path, run_id),)


def _remove(made):
    """Delete temporary planes (after their maps are released; Windows refuses to delete a mapped file)."""
    import gc
    gc.collect()
    for p in made:
        try:
            os.unlink(p.path)
        except OSError:
            pass
