"""E6: connected components on planes (engine design 2.4).

The classic labels a whole boolean image with scipy.ndimage.label (int32 labels), counts with np.bincount(lab_.ravel()), boxes
with find_objects, tests each component on its box, and marks kept components with `out[lab_ == i] = True` (one full-image
pass per component). Here: the same whole `label` call writing into a mapped int32 plane, counts summed over row bands
(int64), the same find_objects boxes (one whole call on the mapped labels), the classic's own per-component test on the same
windows of mapped planes, and a keep table applied as keep[lab_] (the same set of pixels, without the per-component passes).
Label numbering is the classic's (the same call), and it is never used for anything but identity."""
import numpy as np



ROWS = 2304


def label_into(mask, out):
    """scipy.ndimage.label(mask) with its labels written into `out` (int32, the mask's shape). Returns the count."""
    from scipy.ndimage import label
    if out.dtype != np.int32 or out.shape != mask.shape:
        raise ValueError('label_into: out must be int32 of the mask shape')
    n = label(np.asarray(mask), output=out)
    if isinstance(out, np.memmap):
        out.flush()
    return int(n)


def bincount_bands(lab, n, rows=ROWS):
    """np.bincount(lab.ravel(), minlength=n + 1) summed over row bands; int64 counters."""
    total = np.zeros(int(n) + 1, np.int64)
    H = int(lab.shape[0])
    for y0 in range(0, H, rows):
        c = np.bincount(np.asarray(lab[y0:y0 + rows]).ravel(), minlength=int(n) + 1)
        if c.dtype != np.int64:
            c = c.astype(np.int64)
        total += c[:int(n) + 1]
        if c.size > n + 1:
            raise ValueError('a label above the count')
    return total


def find_objects(lab, n):
    from scipy.ndimage import find_objects as _fo
    return _fo(np.asarray(lab), max_label=int(n))


def apply_table(table, lab, out, rows=ROWS):
    """out = table[lab] by row bands (table: a 1-D array indexed by label; out: a mapped or private array of lab's shape)."""
    H = int(lab.shape[0])
    for y0 in range(0, H, rows):
        out[y0:y0 + rows] = table[np.asarray(lab[y0:y0 + rows])]
    if isinstance(out, np.memmap):
        out.flush()
    return out


def window_values(values, lab, sl, i):
    """values[lab == i] restricted to the component's box (the same values in the same row-major order as the classic's
    full-image boolean selection, since every selected pixel lies in the box)."""
    v = np.asarray(values[sl])
    m = np.asarray(lab[sl]) == i
    return v[m]


def component_values_chunks(values, lab, sl, i, rows=ROWS):
    """chunks() of values[lab == i] over the component's box in row bands (for exact streamed statistics of a large one)."""
    ys, xs = sl

    def it():
        for y0 in range(ys.start, ys.stop, rows):
            y1 = min(ys.stop, y0 + rows)
            v = np.asarray(values[y0:y1, xs])
            m = np.asarray(lab[y0:y1, xs]) == i
            yield np.ascontiguousarray(v[m], dtype=np.float32)
    return it


def component_median(values, lab, sl, i, direct_max=1 << 25):
    """np.median(values[lab == i]) of one component: numpy's own call on the gathered values when the box is small enough,
    else the exact streamed median (select.median), which equals it."""
    from . import selection as select
    ys, xs = sl
    if (ys.stop - ys.start) * (xs.stop - xs.start) <= direct_max:
        return np.median(window_values(values, lab, sl, i))
    return select.median(component_values_chunks(values, lab, sl, i))


def component_percentile(values, lab, sl, i, q, direct_max=1 << 25):
    """np.percentile(values[lab == i], q) of one component, as component_median."""
    from . import selection as select
    ys, xs = sl
    if (ys.stop - ys.start) * (xs.stop - xs.start) <= direct_max:
        return np.percentile(window_values(values, lab, sl, i), q)
    return select.percentiles(component_values_chunks(values, lab, sl, i), [q])[0]


def masked_median(values, mask_plane, rows=ROWS, direct_max=1 << 25):
    """np.median(values[mask]) over whole planes: the direct call when the plane is small enough, else exact streamed."""
    from . import selection as select
    H, W = mask_plane.shape[:2]
    if H * W <= direct_max:
        return np.median(np.asarray(values)[np.asarray(mask_plane)])

    def it():
        for y0 in range(0, H, rows):
            v = np.asarray(values[y0:y0 + rows])
            m = np.asarray(mask_plane[y0:y0 + rows])
            yield np.ascontiguousarray(v[m], dtype=np.float32)
    return select.median(it)


def any_true(mask_plane, rows=ROWS):
    H = int(mask_plane.shape[0])
    return any(bool(np.asarray(mask_plane[y0:y0 + rows]).any()) for y0 in range(0, H, rows))
