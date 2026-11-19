"""Banded Lanczos resampling that gives the bytes of Pillow's whole-image call (engine design T1).

Pillow resamples an 8-bit image in two passes, horizontal then vertical, through an 8-bit intermediate, and each pass's
coefficients depend only on the sizes along its own axis. So the whole call equals:
  1. the horizontal pass on full-width row bands (each band's rows are exactly the whole pass's rows), into an 8-bit plane;
  2. the vertical pass on full-height column strips of that plane (each column is processed whole).
A pass whose size does not change is skipped, as Pillow skips it. Used for the render canvas, `init`, the finish's Q, the
alpha plane (mode L) and the viewer's proxy; the gate G3 compares it with the whole call at every production pair.

Sources and targets are objects with read_rows(y0, y1) / read_cols(x0, x1) and write_rows(y0, rows) / map('r+') (engine.planes
Plane), or plain arrays through ArrayRows."""
import numpy as np

from engine import bands as _bands

ROW_BAND = 1152
COL_STRIP = 256


class ArrayRows:
    """An in-memory array with the plane access methods (tests, small images)."""

    def __init__(self, arr):
        self.a = arr if arr.ndim == 3 else arr[..., None]
        self.shape = self.a.shape
        self.dtype = self.a.dtype

    def read_rows(self, y0, y1):
        return np.array(self.a[y0:y1])

    def read_cols(self, x0, x1):
        return np.array(self.a[:, x0:x1])

    def write_rows(self, y0, rows):
        r = rows if rows.ndim == 3 else rows[..., None]
        self.a[y0:y0 + r.shape[0]] = r

    def map(self, mode='r'):
        return self.a


def _img(arr):
    from PIL import Image
    a = arr[..., 0] if arr.shape[2] == 1 else arr
    return Image.fromarray(np.ascontiguousarray(a), 'L' if arr.shape[2] == 1 else ('RGB' if arr.shape[2] == 3 else 'RGBA'))


def _arr(im, c):
    a = np.asarray(im)
    return a[..., None] if c == 1 else a


def resize(src, dst, tmp=None, row_band=ROW_BAND, col_strip=COL_STRIP):
    """Lanczos-resize plane `src` (H x W x C, uint8; C 1 or 3) into plane `dst` (H2 x W2 x C). `tmp` (H x W2 x C, uint8) holds
    the horizontal pass when both passes are needed."""
    from PIL import Image
    H, W, C = src.shape
    H2, W2, C2 = dst.shape
    if C != C2 or C not in (1, 3, 4) or np.dtype(src.dtype) != np.uint8:
        raise ValueError('resize: uint8 planes with the same 1, 3 or 4 channels')
    _bands.check_band_height(row_band)
    need_h, need_v = W2 != W, H2 != H
    if not need_h and not need_v:
        for b in _bands.bands(H, row_band):
            dst.write_rows(b.start, src.read_rows(b.start, b.stop))
        return dst
    mid = src
    if need_h:
        mid = dst if not need_v else tmp
        if mid is None:
            raise ValueError('resize: both passes need a tmp plane of H x W2')
        if mid.shape != (H, W2, C):
            raise ValueError(f'resize: the horizontal pass needs a plane of {(H, W2, C)}, got {mid.shape}')
        for b in _bands.bands(H, row_band):
            rows = src.read_rows(b.start, b.stop)
            mid.write_rows(b.start, _arr(_img(rows).resize((W2, b.rows), Image.LANCZOS), C))
    if need_v:
        out = dst.map('r+')
        try:
            for s in _bands.strips(W2, col_strip):
                col = mid.read_cols(s.start, s.stop)
                out[:, s.start:s.stop] = _arr(_img(col).resize((s.rows, H2), Image.LANCZOS), C)
            if hasattr(out, 'flush'):
                out.flush()
        finally:
            del out
    return dst


def resize_array(arr, size, row_band=ROW_BAND, col_strip=COL_STRIP):
    """resize() on arrays (H x W x C uint8) to size (W2, H2): the banded path, for tests and small images."""
    a = arr if arr.ndim == 3 else arr[..., None]
    H, W, C = a.shape
    W2, H2 = size
    dst = ArrayRows(np.zeros((H2, W2, C), np.uint8))
    tmp = ArrayRows(np.zeros((H, W2, C), np.uint8)) if (W2 != W and H2 != H) else None
    resize(ArrayRows(np.ascontiguousarray(a)), dst, tmp, row_band, col_strip)
    return dst.a if arr.ndim == 3 else dst.a[..., 0]


def proxy_size(w, h, long_side):
    """The fit size of a w x h image within long_side (Pillow thumbnail's rounding, as service.images.preview_size)."""
    import math
    if w <= long_side and h <= long_side:
        return w, h
    aspect = w / h

    def closest(number, key):
        return max(min(math.floor(number), math.ceil(number), key=key), 1)
    x = y = long_side
    if x / y >= aspect:
        x = closest(y * aspect, key=lambda n: abs(aspect - n / y))
    else:
        y = closest(x / aspect, key=lambda n: 0 if n == 0 else abs(aspect - x / n))
    return x, y
