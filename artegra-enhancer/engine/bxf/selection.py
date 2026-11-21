"""E5: exact streamed order statistics over planes, and numpy's own percentile / median arithmetic on them (engine design 2.4).

np.percentile(a, q) on float32 data (numpy 2, method 'linear') is: q / float32(100) in float32, numpy's virtual index
n * q + (1 + q * (1 - 1 - 1)) - 1 in float32 (n a weak Python int), floor and the next index, gamma = the fraction, and
_lerp(previous, next, gamma) in float32; the result is an np.float32 scalar. np.median(a) is np.mean of the one or two middle
order statistics, also np.float32. This module finds those order statistics without holding the data: a histogram of the
high 16 bits of each value's monotonic float32 key, then a histogram of the low 16 bits inside the bin that holds each rank (two
streamed passes, int64 counters, exact for any count), and then calls numpy's OWN index, gamma and lerp helpers (or np.mean)
on them, so the operand types and the arithmetic are numpy's. A numpy without those helpers raises Unavailable, never an
imitation; the finish node asks unavailable() before it writes any plane (bxf-chk-6), so its ladder takes the whole tier
where the plan counted it, or refuses in plain words."""
import numpy as np

HI_BINS = 1 << 16


class Unavailable(RuntimeError):
    """This numpy lacks a helper the exact selection calls (its own index, gamma or lerp)."""


def unavailable():
    """None when this numpy has every helper the exact selection calls, else the plain reason."""
    try:
        _fb()
    except (Unavailable, ImportError) as e:
        return str(e) or 'numpy has no exact-selection helpers'
    return None


def _fb():
    try:
        import numpy.lib._function_base_impl as fb
    except ImportError:                                  # numpy 1.x layout
        import numpy.lib.function_base as fb
    for name in ('_QuantileMethods', '_get_indexes', '_get_gamma', '_lerp'):
        if not hasattr(fb, name):
            raise Unavailable(f'numpy {np.__version__} has no {name}: exact selection cannot use numpy\'s own arithmetic')
    return fb


def keys(values):
    """Monotonic uint32 keys of float32 values (-0.0 sorts just below +0.0; NaN above +inf)."""
    v = np.ascontiguousarray(values)
    if v.dtype != np.float32:
        raise TypeError(f'exact selection reads float32 values (got {v.dtype})')
    u = v.reshape(-1).view(np.uint32)
    return np.where(u >> np.uint32(31), ~u, u | np.uint32(0x80000000))


def unkey(k):
    k = int(k) & 0xffffffff
    u = (k & 0x7fffffff) if k & 0x80000000 else (~k & 0xffffffff)
    return np.array([u], np.uint32).view(np.float32)[0]


def order_statistics(chunks, ranks):
    """chunks(): a new iterator of float32 arrays (the selected values, any shape), called twice. ranks: 0-based ranks.
    Returns ({rank: np.float32}, n, nan_count). Counters are int64."""
    hist = np.zeros(HI_BINS, np.int64)
    n = 0
    nans = 0
    for v in chunks():
        k = keys(v)
        if k.size:
            c = np.bincount((k >> np.uint32(16)).astype(np.intp), minlength=HI_BINS)
            assert c.dtype == np.int64
            hist += c
            nans += int(np.count_nonzero(np.isnan(np.asarray(v, np.float32))))
        n += int(k.size)
    ranks = sorted(set(int(r) for r in ranks))
    if not ranks:
        return {}, n, nans
    if ranks[0] < 0 or ranks[-1] >= n:
        raise ValueError(f'rank outside 0..{n - 1}')
    cum = np.cumsum(hist)
    assert cum.dtype == np.int64
    need = {}
    for r in ranks:
        hb = int(np.searchsorted(cum, np.int64(r), side='right'))
        base = int(cum[hb - 1]) if hb else 0
        need.setdefault(hb, []).append((r, r - base))
    lows = {hb: np.zeros(HI_BINS, np.int64) for hb in need}
    for v in chunks():
        k = keys(v)
        if not k.size:
            continue
        hi = k >> np.uint32(16)
        for hb, h in lows.items():
            sel = k[hi == np.uint32(hb)]
            if sel.size:
                h += np.bincount((sel & np.uint32(0xffff)).astype(np.intp), minlength=HI_BINS)
    out = {}
    for hb, lst in need.items():
        c = np.cumsum(lows[hb])
        for r, rr in lst:
            lb = int(np.searchsorted(c, np.int64(rr), side='right'))
            out[r] = unkey((hb << 16) | lb)
    return out, n, nans


def _weak_q_numpy(fb):
    """numpy >= 2.4 (the worker runtime's 2.5.4) divides a Python q by 100 in float64 and passes gamma as a Python float
    ('weak_q'); numpy 2.0-2.3 divides by the data's own float type. Both are followed exactly, by the installed numpy's
    own code path."""
    import inspect
    return 'weak_q' in inspect.signature(fb._quantile).parameters


def percentile_plan(n, q, dtype=np.float32):
    """numpy's own virtual index, neighbour ranks and gamma for np.percentile(a, q) of n values of `dtype` (linear method),
    following the installed numpy's np.percentile -> _quantile path step by step."""
    fb = _fb()
    dt = np.dtype(dtype)
    if _weak_q_numpy(fb):
        weak_q = type(q) in (int, float)
        qa = np.true_divide(q, 100, out=...)
    else:
        weak_q = False
        qa = np.asanyarray(np.true_divide(q, dt.type(100) if dt.kind == 'f' else 100))
    if not (0 <= float(qa) <= 1):
        raise ValueError('Percentiles must be in the range [0, 100]')
    props = fb._QuantileMethods['linear']
    vi = np.asanyarray(props['get_virtual_index'](n, qa))
    if np.issubdtype(vi.dtype, np.integer):
        r = int(vi)
        return ('take', r if r >= 0 else n + r, None, None)
    prev, nxt = fb._get_indexes(np.empty(0, dt), vi, n)
    gamma = fb._get_gamma(vi, prev, props)
    gamma = float(gamma) if weak_q else gamma.reshape(vi.shape)
    p, x = int(prev), int(nxt)
    return ('lerp', p if p >= 0 else n + p, x if x >= 0 else n + x, gamma)


def percentiles(chunks, qs, dtype=np.float32, n=None):
    """[np.percentile(a, q) for q in qs] where a is the concatenation of chunks() (float32), as np.float32 scalars."""
    fb = _fb()
    dt = np.dtype(dtype)
    if n is None:
        n = sum(int(np.asarray(v).size) for v in chunks())
    if n == 0:
        raise ValueError('percentile of no values')
    plans = [percentile_plan(n, q, dt) for q in qs]
    ranks = [p[1] for p in plans] + [p[2] for p in plans if p[0] == 'lerp']
    vals, n2, nans = order_statistics(chunks, ranks)
    if n2 != n:
        raise ValueError(f'the chunks held {n2} values, not {n}')
    out = []
    for kind, a, b, gamma in plans:
        if nans:
            out.append(dt.type(np.nan))
        elif kind == 'take':
            out.append(dt.type(vals[a]))
        else:
            out.append(fb._lerp(dt.type(vals[a]), dt.type(vals[b]), gamma))
    return out


def median(chunks, dtype=np.float32, n=None):
    """np.median(a) of the concatenation of chunks() (float32), as numpy computes it: np.mean of the middle order statistic(s)."""
    dt = np.dtype(dtype)
    if n is None:
        n = sum(int(np.asarray(v).size) for v in chunks())
    if n == 0:
        raise ValueError('median of no values')
    ranks = [n // 2 - 1, n // 2] if n % 2 == 0 else [(n - 1) // 2]
    vals, n2, nans = order_statistics(chunks, ranks)
    if n2 != n:
        raise ValueError(f'the chunks held {n2} values, not {n}')
    if nans:
        return dt.type(np.nan)
    return np.mean(np.array([vals[r] for r in ranks], dt), axis=0)


def band_chunks(arr, height=2304, mask=None, transform=None):
    """chunks() over a (mapped) array by full-width row bands: the values (optionally transform(rows)) where mask(rows,
    y0, y1) holds, in row-major order."""
    H = int(arr.shape[0])

    def it():
        for y0 in range(0, H, height):
            y1 = min(H, y0 + height)
            rows = np.asarray(arr[y0:y1])
            if transform is not None:
                rows = transform(rows)
            if mask is not None:
                rows = rows[mask(y0, y1)]
            yield np.ascontiguousarray(rows, dtype=np.float32).reshape(-1)
    return it


def strided_sample(arr, limit=4_000_000):
    """The classic _quantile's sample of a (mapped) array: flat[:: numel // limit + 1] when numel > limit, else all values; the
    same global flat indices (int64) as the classic's flatten-then-slice."""
    flat = np.asarray(arr).reshape(-1)
    n = int(flat.size)
    if n > limit:
        step = n // limit + 1
        return np.array(flat[::step])
    return np.array(flat)
