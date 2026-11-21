"""E2: scipy's uniform_filter on planes (engine design 2.4). scipy runs uniform_filter as uniform_filter1d along axis 0 into the
output (cast to the output dtype), then along axis 1 on that output; each 1-D pass keeps a running sum along every line, so a
line must be processed WHOLE. Here: axis 0 on full-height column strips (every column whole) into a scratch plane of the
output dtype, then axis 1 on full-width row bands (every row whole). Each line sees exactly the classic's values, so the bytes
are the classic's by construction (G1 checks it at the registered shapes).

tbb(x, r) of the finish is three such filters of size 2r + 1, mode 'reflect'."""
import numpy as np

from .. import bands as _bands

STRIP = 1024          # columns per strip (any split is exact: each column is whole)
ROWS = 2304           # rows per band of the axis-1 pass (any split is exact: each row is whole)


def uniform_filter_planes(src, dst, size, tmp, mode='reflect', strip=STRIP, rows=ROWS):
    """dst = scipy.ndimage.uniform_filter(src, size, mode=mode) for a 2-D float plane. tmp: a scratch plane of dst's shape and
    dtype, distinct from src and dst; dst may be src (the axis-0 pass reads src whole before dst is written). Returns dst."""
    from scipy.ndimage import uniform_filter1d
    H, W = src.shape
    if dst.shape != (H, W) or tmp.shape != (H, W) or tmp.dtype != dst.dtype:
        raise ValueError('uniform_filter_planes: tmp and dst must have the source shape and the output dtype')
    if int(size) <= 1:
        dst[...] = src
        return dst
    _bands.check_band_height(rows)
    for x0 in range(0, W, strip):
        x1 = min(W, x0 + strip)
        out = np.empty((H, x1 - x0), dst.dtype)
        uniform_filter1d(np.asarray(src[:, x0:x1]), int(size), axis=0, output=out, mode=mode)
        tmp[:, x0:x1] = out
    for b in _bands.bands(H, rows):
        band = np.array(tmp[b.start:b.stop])
        uniform_filter1d(band, int(size), axis=1, output=band, mode=mode)
        dst[b.start:b.stop] = band
    for a in (tmp, dst):
        if isinstance(a, np.memmap):
            a.flush()
    return dst


def tbb_planes(x, r, out, tmp):
    """out = tbb(x, r) of v4finish: three uniform filters of size 2r + 1 (reflect), each into the output dtype. tmp: a scratch
    plane of out's shape and dtype, distinct from x and out (the axis-0 pass writes only tmp, so out may be filtered in
    place)."""
    if tmp is x or tmp is out:
        raise ValueError('tbb_planes: tmp must be its own plane')
    uniform_filter_planes(x, out, 2 * r + 1, tmp)
    uniform_filter_planes(out, out, 2 * r + 1, tmp)
    uniform_filter_planes(out, out, 2 * r + 1, tmp)
    return out
