"""E3 and E4 of the banded exact finish (engine design 2.4).

E3, aligned pooling: v4finish.g(x, s) for s > 8 pools the edge-padded image into f x f cells (f = int(s // 4), 2..48) by
reshape(H // f, f, W // f, f).mean((1, 3)). Bands start on multiples of 288 rows (bands.ALIGN, the LCM of every f), so each band
holds whole cells and each cell sums the same elements in the same order as the whole call. The pooled grid is a mapped plane;
its blur and the zoom back to (H, W) are the classic calls, whole, with output= a mapped plane (E4).

E4, small in, whole out: the same call on its small input, writing into a mapped output."""
import numpy as np

from .. import bands as _bands


def pool_mean_bands(x, f, grid, height=2304):
    """grid[...] = np.pad(x, ((0, H - h), (0, W - w)), mode='edge').reshape(H // f, f, W // f, f).mean((1, 3)) by row bands of
    `height` (a registered height; a multiple of f)."""
    h, w = x.shape
    H, W = -(-h // f) * f, -(-w // f) * f
    if grid.shape != (H // f, W // f):
        raise ValueError(f'pool_mean_bands: the grid must be {(H // f, W // f)}')
    _bands.check_band_height(height)
    if height % f or _bands.ALIGN % f:
        raise AssertionError(f'pool factor {f} does not divide the band alignment')
    for b in _bands.bands(h, height):
        rows = np.asarray(x[b.start:b.stop])
        padb = (H - h) if b.stop == h else 0
        xb = np.pad(rows, ((0, padb), (0, W - w)), mode='edge')
        grid[b.start // f:(b.stop + padb) // f] = xb.reshape(xb.shape[0] // f, f, W // f, f).mean((1, 3))
    if isinstance(grid, np.memmap):
        grid.flush()
    return grid


def zoom_shape(shape, factors):
    """scipy.ndimage.zoom's output shape for these factors (its own rounding)."""
    return tuple(int(round(ii * jj)) for ii, jj in zip(shape, factors))


def g_pooled(x, s, ws, name, height=2304):
    """v4finish.g(x, s) for s > 8 with mapped intermediates: returns the [:h, :w] view of a mapped float32 plane holding
    zoom(gaussian_filter(pooled, s / f), (H / gh, W / gw), order=1). `ws`: a work.Workspace; scratch names start with `name`."""
    from scipy.ndimage import gaussian_filter, zoom
    if not s > 8:
        raise ValueError('g_pooled is the s > 8 branch of g()')
    f = int(s // 4)
    h, w = x.shape
    H, W = -(-h // f) * f, -(-w // f) * f
    grid = ws.new(name + '.grid', (H // f, W // f), np.float32)
    pool_mean_bands(x, f, grid, height)
    y = ws.new(name + '.blur', grid.shape, np.float32)
    gaussian_filter(np.asarray(grid), s / f, output=y)
    ws.free(name + '.grid')
    factors = (H / y.shape[0], W / y.shape[1])
    z = ws.new(name, zoom_shape(y.shape, factors), np.float32)
    zoom(np.asarray(y), factors, output=z, order=1)
    ws.free(name + '.blur')
    z.flush()
    return z[:h, :w]
