"""Q4, Q5 and Q11 of engine design section 5, for the sizes with no classic reference (6x, 8x, 32,000 px), each bounded by the
classic's own three-pass chain W2c (8x of 1280 x 1600) as registered. numpy, by row bands.

Q4  colour or tone drift: CIEDE2000 between 64 px block means of pass 2 and the same blocks of pass 3 (area-downscaled: the
    block mean in linear light over the 64 r px block, r = pass-3 size / pass-2 size), Lab of each block mean. Bound: the
    W2c chain's p50 and p99, computed by q4_bound() as soon as W2c ends; pass: the BES's p50 and p99 within the classic's
    + 25 %.
Q5  invented content at pass 3: DoG band energy (sigma 0.8 and 2.4 px, L*) of pass 3 against pass 2 Lanczos-scaled to
    pass 3's size, per 32 px block, in the blocks where pass 2 is smooth (the block's L* std below its p20). The statistic is
    the excess energy E3 - E2 (L*^2); calibration is the W2c chain's p99.9 of it (floored at CALIB_FLOOR); blocks above 2 x the
    calibration are listed with their boxes for the judges, and each registered crop (signage and text, people and faces,
    glazing reflections, foliage against sky, water, plaster and sky at window corners) is reported.
Q11 halos at geometry edges: the BES's p95 rim and glow (the halo metric's rim_max and glow_abs) against W2c's at the same
    pass count; pass: within W2c's + its noise (|W2c seed A - W2c seed B|). Reported for bxf-1, required for bxf-1h."""
import math

import numpy as np

from tools.proof import colour
from tools.proof.phases import _Arr

Q4_BLOCK = 64
Q4_MARGIN = 0.25
Q5_BLOCK = 32
Q5_SIGMAS = (0.8, 2.4)
Q5_SMOOTH_PCT = 20
Q5_FLAG_X = 2.0
CALIB_FLOOR = 0.01
CROP_CLASSES = ('signage_text', 'people_faces', 'glazing_reflections', 'foliage_sky', 'water', 'plaster_sky_window_corners')


def _entry(x):
    return x if isinstance(x, dict) else {'kind': 'array', 'array': x}


def _ratio(A3, A2):
    rh, rw = A3.shape[0] / A2.shape[0], A3.shape[1] / A2.shape[1]
    if abs(rh - rw) > 1e-9:
        raise ValueError(f'pass 3 is not a uniform scale of pass 2 ({rw} x {rh})')
    return rh


def block_de(pass3, pass2, block=Q4_BLOCK, band_blocks=8):
    """{'p50', 'p99', 'mean', 'n_blocks', 'ratio'}: CIEDE2000 of 64 px block means (pass 2) against pass 3's blocks."""
    A3, A2 = _Arr(_entry(pass3)), _Arr(_entry(pass2))
    r = _ratio(A3, A2)
    b3 = block * r
    if abs(b3 - round(b3)) > 1e-9:
        raise ValueError(f'a {block} px block is {b3} px of pass 3: not whole')
    b3 = int(round(b3))
    nby, nbx = A2.shape[0] // block, A2.shape[1] // block
    des = []
    for by0 in range(0, nby, band_blocks):
        by1 = min(nby, by0 + band_blocks)
        m2 = colour.block_mean(colour.linear_from_rgb(A2.rows(by0 * block, by1 * block)), block)[:, :nbx]
        m3 = colour.block_mean(colour.linear_from_rgb(A3.rows(by0 * b3, by1 * b3)), b3)[:, :nbx]
        des.append(colour.ciede2000(colour.lab_from_linear(m3.astype(np.float32)),
                                    colour.lab_from_linear(m2.astype(np.float32))).ravel())
    d = np.concatenate(des) if des else np.zeros(0)
    return {'p50': float(np.percentile(d, 50)), 'p99': float(np.percentile(d, 99)), 'mean': float(d.mean()),
            'n_blocks': int(d.size), 'ratio': r}


def q4_bound(w2c_pass3, w2c_pass2):
    """The registered bound from the classic chain W2c: its pass-3 against pass-2 statistics."""
    return block_de(w2c_pass3, w2c_pass2)


def q4(bes_pass3, bes_pass2, bound, margin=Q4_MARGIN):
    s = block_de(bes_pass3, bes_pass2)
    lim50, lim99 = bound['p50'] * (1 + margin), bound['p99'] * (1 + margin)
    return {'bes': s, 'bound': bound, 'limit_p50': lim50, 'limit_p99': lim99,
            'pass': bool(s['p50'] <= lim50 and s['p99'] <= lim99)}


def dog_blocks(img, sigmas=Q5_SIGMAS, block=Q5_BLOCK, band_rows=512):
    """(E, S): per block, the mean squared DoG band of L* and the L* std. Bands carry real halo rows; borders mirror only at
    the true image border."""
    A = _Arr(_entry(img))
    H, W = A.shape[0], A.shape[1]
    if band_rows % block:
        raise ValueError('band_rows must be a multiple of the block')
    halo = int(4 * max(sigmas) + 0.5) + 1
    nby, nbx = H // block, W // block
    E = np.zeros((nby, nbx))
    S = np.zeros((nby, nbx))
    for y0 in range(0, nby * block, band_rows):
        y1 = min(nby * block, y0 + band_rows)
        r0, r1 = max(0, y0 - halo), min(H, y1 + halo)
        L = colour.lstar(A.rows(r0, r1)).astype(np.float64)
        d = colour.gaussian(L, sigmas[0]).astype(np.float64) - colour.gaussian(L, sigmas[1]).astype(np.float64)
        core = slice(y0 - r0, y0 - r0 + (y1 - y0))
        e = d[core, :nbx * block] ** 2
        lc = L[core, :nbx * block]
        k = (y1 - y0) // block
        E[y0 // block:y0 // block + k] = e.reshape(k, block, nbx, block).mean((1, 3))
        S[y0 // block:y0 // block + k] = lc.reshape(k, block, nbx, block).std((1, 3))
    return E, S


def lanczos_up(pass2_u8, size):
    """pass 2 Lanczos-scaled to (W, H) by the engine's banded Pillow-exact Lanczos (engine/lanczos_bands)."""
    from engine import lanczos_bands
    return lanczos_bands.resize_array(np.ascontiguousarray(pass2_u8), size)


def q5_stats(pass3, pass2_up, block=Q5_BLOCK, smooth_pct=Q5_SMOOTH_PCT):
    E3, _ = dog_blocks(pass3, block=block)
    E2, S2 = dog_blocks(pass2_up, block=block)
    smooth = S2 < np.percentile(S2, smooth_pct)
    ex = E3 - E2
    v = ex[smooth]
    st = {'n_smooth': int(v.size)}
    if v.size:
        st.update(p50=float(np.percentile(v, 50)), p99=float(np.percentile(v, 99)), p99_9=float(np.percentile(v, 99.9)))
    return ex, smooth, st


def q5_calibrate(w2c_pass3, w2c_pass2_up):
    _, _, st = q5_stats(w2c_pass3, w2c_pass2_up)
    return max(float(st.get('p99_9', 0.0)), CALIB_FLOOR)


def q5(pass3, pass2_up, calib, crops=(), block=Q5_BLOCK):
    """Blocks of invented content: smooth in pass 2 and with excess energy above Q5_FLAG_X x the calibration. crops:
    [{'class', 'box': [x0, y0, x1, y1]}] in pass-3 px."""
    ex, smooth, st = q5_stats(pass3, pass2_up, block)
    thr = Q5_FLAG_X * max(float(calib), CALIB_FLOOR)
    flag = smooth & (ex > thr)
    ys, xs = np.nonzero(flag)
    boxes = [{'box': [int(x * block), int(y * block), int((x + 1) * block), int((y + 1) * block)], 'excess': float(ex[y, x])}
             for y, x in zip(ys, xs)]
    boxes.sort(key=lambda b: -b['excess'])
    rep = []
    for c in crops or ():
        if c.get('class') not in CROP_CLASSES:
            raise ValueError(f"unregistered crop class {c.get('class')!r}")
        x0, y0, x1, y1 = (int(v) for v in c['box'])
        bx0, by0, bx1, by1 = x0 // block, y0 // block, -(-x1 // block), -(-y1 // block)
        sub, fl = ex[by0:by1, bx0:bx1], flag[by0:by1, bx0:bx1]
        rep.append({'class': c['class'], 'box': [x0, y0, x1, y1], 'mean_excess': float(sub.mean()) if sub.size else None,
                    'max_excess': float(sub.max()) if sub.size else None, 'flagged_blocks': int(fl.sum())})
    return {'stats': st, 'calibration': float(calib), 'threshold': thr, 'flagged': boxes[:200], 'n_flagged': len(boxes),
            'crops': rep}


def q11(bes_report, w2c_a_report, w2c_b_report, keys=('rim_max', 'glow_abs'), stat='p95'):
    """The BES's p95 rim and glow against the classic chain's (W2c seed A) plus its noise (|seed A - seed B|)."""
    rows, ok = [], True
    for k in keys:
        b = (bes_report['summary'].get(k) or {}).get(stat)
        a = (w2c_a_report['summary'].get(k) or {}).get(stat)
        n = (w2c_b_report['summary'].get(k) or {}).get(stat)
        if b is None or a is None or n is None or not all(math.isfinite(x) for x in (b, a, n)):
            rows.append({'key': k, 'pass': False, 'reason': 'missing statistic'})
            ok = False
            continue
        noise = abs(a - n)
        p = b <= a + noise
        ok = ok and p
        rows.append({'key': k, 'stat': stat, 'bes': b, 'w2c': a, 'noise': noise, 'limit': a + noise, 'pass': bool(p)})
    return {'rows': rows, 'pass': bool(ok)}
