"""The x4 model's margin tiling as a banded accumulator (engine design section 2.2 row 3, lever L2).

margin_tiled_upscale (node_pack/claude_creative/__init__.py) adds each tile's output times its blend weight into a whole-image
accumulator `acc` and the weights into `wsum`, tile rows outer and tiles inner, then divides. Here `acc` and `wsum` live only
for the output rows the current tile row touches; rows that no later tile row reaches are divided and handed to `sink` in row
chunks. Every output value is the same float32 sum of the same products in the same order, so the result is the classic's,
value for value (tests/test_banded_planes.py; on the worker runtime, tests/worker/test_banded_torch.py against the classic
function itself). Memory: 16 B per output pixel of the live band (about 2,560 output rows), not of the whole image."""
import numpy as np

from engine import bands as _bands

FLUSH_ROWS = 512


def ramp(n_core, at_lo, at_hi, blend):
    """margin_tiled_upscale's blend ramp, in float32 (torch.arange(1, blend + 1, float32) / (blend + 1))."""
    w = np.ones(n_core, np.float32)
    r = np.arange(1, blend + 1, dtype=np.float32) / np.float32(blend + 1)
    if not at_lo:
        w[:blend] = r
    if not at_hi:
        w[-blend:] = np.minimum(w[-blend:], r[::-1])
    return w


def margin_tiled_banded(read, shape, fn, scale, sink, tile=512, margin=64, blend=16, flush_rows=FLUSH_ROWS):
    """read(y0, y1, x0, x1) -> the input crop (H x W x C); fn(crop) -> its float32 output (h*scale x w*scale x C);
    sink(y0, rows) receives finished output rows `acc / wsum` (float32), in order, at most flush_rows at a time.
    Images that fit one tile are evaluated whole, as the classic does."""
    H, W, C = shape
    if H <= tile and W <= tile:
        out = np.asarray(fn(read(0, H, 0, W)), np.float32)
        for y in range(0, out.shape[0], flush_rows):
            sink(y, out[y:y + flush_rows])
        return
    rows = _bands.dat_tile_rows(H, W, tile, margin, blend)
    final = _bands.dat_final_rows(rows, H, scale)
    Ws = W * scale
    base = 0                                   # first output row held in acc / wsum
    acc = np.zeros((0, Ws, C), np.float32)
    wsum = np.zeros((0, Ws, 1), np.float32)
    for row, (lo, hi) in zip(rows, final):
        top = row[0].cy1 * scale               # the band must reach this row
        if top - base > acc.shape[0]:
            grow = top - base - acc.shape[0]
            acc = np.concatenate([acc, np.zeros((grow, Ws, C), np.float32)])
            wsum = np.concatenate([wsum, np.zeros((grow, Ws, 1), np.float32)])
        for t in row:
            o = np.asarray(fn(read(t.iy0, t.iy1, t.ix0, t.ix1)), np.float32)
            o = o[(t.cy0 - t.iy0) * scale:(t.cy1 - t.iy0) * scale, (t.cx0 - t.ix0) * scale:(t.cx1 - t.ix0) * scale]
            wy = ramp(t.cy1 - t.cy0, t.lo_y, t.hi_y, blend).repeat(scale)
            wx = ramp(t.cx1 - t.cx0, t.lo_x, t.hi_x, blend).repeat(scale)
            w = (wy[:, None] * wx[None, :])[..., None]
            y0, y1 = t.cy0 * scale - base, t.cy1 * scale - base
            acc[y0:y1, t.cx0 * scale:t.cx1 * scale] += o * w
            wsum[y0:y1, t.cx0 * scale:t.cx1 * scale] += w
        for y in range(lo, hi, flush_rows):
            y2 = min(hi, y + flush_rows)
            sink(y, acc[y - base:y2 - base] / wsum[y - base:y2 - base])
        keep = hi - base
        acc, wsum = acc[keep:].copy(), wsum[keep:].copy()
        base = hi


def to_canvas_u8(rows):
    """The classic's float-to-8-bit conversion of the x4 output (torch.clamp(0, 1), then comfy.utils.lanczos's
    np.clip(255. * x, 0, 255).astype(np.uint8)), per row chunk."""
    r = np.clip(rows, np.float32(0.0), np.float32(1.0))
    return np.clip(np.float32(255.0) * r, 0, 255).astype(np.uint8)
