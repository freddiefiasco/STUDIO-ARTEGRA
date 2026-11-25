"""Halo Reduction (beta): a per-job option of the Large-image finish, OFF by default (HANDOVER-ENGINE-CORE.md 13a; Max, 22 Nov
2026: a toggle "Halo Reduction (beta)" that the user turns on and off; "Keep it off"). It is halo round 2's 'edge3f' clamp
(branch halo2/fix 08a5fc28, node_pack/claude_creative/v4finish.py there; v6/engine/HALO-FIX.md section 3.2), ported here
function for function and run on the LAST pass's finish only, in full-width row bands, each read with the clamp's declared
reach (edge_profile_clamp3_reach: 174 rows at f 2, 334 at f 4) of real rows above and below. Every step is local or on
_gpool's grid anchored to the whole image, with float64 sample coordinates, so a band gives the whole call's values on its
rows (HALO-FIX.md section 3.5). It never runs in the classic 1024-row strips.

What it is, plainly (HALO-FIX.md's first line reads NOT FIXED): the halo at edges of geometry is reduced, not removed. At 4x
a thin dark line that 5.0.1 draws too dark can turn two-tone (D-A), a restored dark rim beside a white strip can stay grey
(D-D), and a share of edges on 4x test cards is softer, far below the floors (D-K). It is ported as round 2 left it, behind
the option; the fixes are v6's engine lane's.

The port's differences from 08a5fc28's functions (tests/worker/test_halo_reduction.py checks every result against that
file's own whole-image calls):
- the development dump in _final_clamp3 is dropped (it wrote nothing unless a developer variable was set);
- _clamp_geometry also returns e_rows (which rows hold an edge of geometry), so the band driver can take the whole call's
  two global decisions in _final_clamp3 (no edge of geometry anywhere: the finish's own output; nothing changed anywhere: no
  chroma pass) over every band's own rows;
- the band drivers at the end (clamp_luma_bands, source_planes, final_clamp_bands) and _bilinear_rows_part, which reads only
  the source rows a band's bilinear uses (the same float64 products as _bilinear_rows on the whole source).

Pure numpy and scipy. Imported only when a finish runs with the option on (never at node-pack import: G0d)."""
import math

import numpy as np
from scipy.ndimage import gaussian_filter, binary_dilation, maximum_filter, minimum_filter, label

PORTED_FROM = 'halo2/fix 08a5fc28 node_pack/claude_creative/v4finish.py'
MODE = 'edge3f'                     # the one mode the option runs (HALO-FIX.md section 8 step 2)


def luma(a):
    """v4finish.luma (5.0.1's, unchanged)."""
    return 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]


# --- ported from halo2/fix 08a5fc28 v4finish.py (its lines 501-659 and 810-1026) ------------------------------------------
DEHALO = dict(c_edge=0.10, coh_min=0.5, len_min=12.0, pad=1, tol=0.006, kstd=1.0, line_d=0.03)


def _orient(Yref, sd, si):
    """Dominant gradient direction (radians; x = columns, y = rows) and coherence of the structure tensor of Yref."""
    gx = gaussian_filter(Yref, sd, order=(0, 1))
    gy = gaussian_filter(Yref, sd, order=(1, 0))
    jxx, jyy, jxy = gaussian_filter(gx * gx, si), gaussian_filter(gy * gy, si), gaussian_filter(gx * gy, si)
    theta = 0.5 * np.arctan2(2 * jxy, jxx - jyy)
    disc = np.sqrt(((jxx - jyy) * 0.5) ** 2 + jxy * jxy)
    coh = (2 * disc / (jxx + jyy + 1e-12)) ** 2
    return theta.astype(np.float32), coh.astype(np.float32), gx, gy


LINE_BINS, LINE_HALF = 90, 0.35


def _line_weights(th, sig, half=LINE_HALF):
    """Integer offsets (dy, dx) and weights of a tangent mean at gradient direction th: every pixel of the window whose
    distance from the tangent line is under `half` px, weighted by a triangle in that distance and a Gaussian (sigma sig)
    along the line, as an edge-spread profile is binned by exact distance."""
    K = max(1, int(math.ceil(2.5 * sig)))
    oy, ox = np.mgrid[-K:K + 1, -K:K + 1].astype(np.float32)
    dn = oy * math.sin(th) + ox * math.cos(th)            # across the edge (normal (y, x) = (sin, cos))
    dt = oy * math.cos(th) - ox * math.sin(th)            # along the edge
    wgt = np.exp(-dt * dt / (2 * sig * sig)) * np.clip(1 - np.abs(dn) / half, 0, 1)
    sel = wgt > 1e-3
    wv = (wgt[sel] / wgt[sel].sum()).astype(np.float32)
    return oy[sel].astype(np.int64), ox[sel].astype(np.int64), wv


def _line_neff(sig):
    """The smallest effective number of pixels in a tangent mean over all orientations."""
    return min(float(1.0 / (w * w).sum()) for w in
               (_line_weights(-np.pi / 2 + (b + 0.5) * np.pi / LINE_BINS, sig)[2] for b in range(LINE_BINS)))


def _line_mean(A, ys, xs, theta, sig):
    """Mean of A along the edge tangent through each pixel (ys, xs) from whole pixels only (_line_weights), so a 1-2 px rim
    keeps its height (an interpolated sample would average it with the ramp). theta: the gradient direction per pixel
    (radians), binned into LINE_BINS orientations."""
    H, W = A.shape
    bins = (((theta + np.pi / 2) / np.pi) * LINE_BINS).astype(np.int64) % LINE_BINS
    out = np.empty(ys.shape, np.float32)
    order = np.argsort(bins, kind='stable')
    starts = np.searchsorted(bins[order], np.arange(LINE_BINS + 1))
    for bi in range(LINE_BINS):
        idx = order[starts[bi]:starts[bi + 1]]
        if idx.size == 0:
            continue
        dys, dxs, wv = _line_weights(-np.pi / 2 + (bi + 0.5) * np.pi / LINE_BINS, sig)
        y0, x0 = ys[idx].astype(np.int64), xs[idx].astype(np.int64)
        acc = np.zeros(idx.size, np.float32)
        for w_, dy, dx in zip(wv, dys, dxs):
            acc += w_ * A[np.clip(y0 + dy, 0, H - 1), np.clip(x0 + dx, 0, W - 1)]
        out[idx] = acc
    return out


def geometry_edges(Yref, gx, gy, coh, f, c_edge, coh_min, len_min, coord64=False):
    """Edges of geometry in the reference: non-maximum-suppressed gradient pixels with a step of >= c_edge (luma) across
    +-1.5 f px, locally coherent (>= coh_min), in 8-connected runs of >= len_min px. Bool map at output size."""
    from scipy.ndimage import map_coordinates
    mag = np.hypot(gx, gy)
    ys, xs = np.nonzero(mag >= 0.25 * c_edge / max(1.0, f))
    m = mag[ys, xs]
    nx_, ny_ = gx[ys, xs] / np.maximum(m, 1e-9), gy[ys, xs] / np.maximum(m, 1e-9)
    ct = np.float64 if coord64 else np.float32     # float64: a sample's weights do not depend on where the array starts
    yf, xf = ys.astype(ct), xs.astype(ct)
    mp = map_coordinates(mag, [yf + ny_, xf + nx_], order=1, mode='nearest', prefilter=False)
    mm = map_coordinates(mag, [yf - ny_, xf - nx_], order=1, mode='nearest', prefilter=False)
    keep = (m >= mp) & (m > mm)
    ys, xs, nx_, ny_, yf, xf = ys[keep], xs[keep], nx_[keep], ny_[keep], yf[keep], xf[keep]
    d = 1.5 * f
    con = (map_coordinates(Yref, [yf + d * ny_, xf + d * nx_], order=1, mode='nearest', prefilter=False)
           - map_coordinates(Yref, [yf - d * ny_, xf - d * nx_], order=1, mode='nearest', prefilter=False))
    sel = (con >= c_edge) & (coh[ys, xs] >= coh_min)
    e = np.zeros(Yref.shape, bool)
    e[ys[sel], xs[sel]] = True
    lab_, n = label(e, structure=np.ones((3, 3), bool))
    if n:
        ok = np.bincount(lab_.ravel()) >= len_min
        ok[0] = False
        e = ok[lab_]
    return e


def _gpool(x, s, oy=0, H_full=None):
    """Gaussian blur of sigma s (s > 8) through a pooled grid ANCHORED TO THE WHOLE IMAGE (halo round 2): cells of
    q = int(s // 4) px start at the image's row 0 and column 0, so a full-width band of rows [oy, oy + h) of an image of
    H_full rows gives the whole image's values on its rows wherever the band carries edge_profile_clamp_reach() rows of
    real image above and below. (g() starts its grid at the array's own first row and zooms back to the array's own size,
    so a band of it differs from the whole image everywhere: round 1's D6.)
    Cells past the image's last row or column repeat it (as g()'s 'edge' padding); a band's partial cells at a cut are left
    out. Cell means are summed in a fixed order (rows, then columns, float64), the grid is blurred by gaussian_filter
    (sigma s / q) and read back bilinearly at every pixel centre, clamped to the end cells."""
    x = np.asarray(x, np.float32)
    h, w = x.shape
    oy = int(oy)
    H_full = h + oy if H_full is None else int(H_full)
    if s <= 8:
        return gaussian_filter(x, s)
    q = int(s // 4)
    c0 = -(-oy // q)
    c1 = -(-H_full // q) if oy + h >= H_full else (oy + h) // q
    if c1 - c0 < 2:
        raise ValueError(f'_gpool: a band of {h} rows at row {oy} holds under two cells of {q} rows')
    r0, r1 = c0 * q - oy, c1 * q - oy
    xr = x[r0:min(r1, h)]
    if r1 > h:
        xr = np.concatenate([xr, np.repeat(xr[-1:], r1 - h, 0)], 0)
    Wp = -(-w // q) * q
    if Wp > w:
        xr = np.concatenate([xr, np.repeat(xr[:, -1:], Wp - w, 1)], 1)
    nr, nc = c1 - c0, Wp // q
    a3 = xr.reshape(nr, q, Wp)
    acc = np.zeros((nr, Wp), np.float64)
    for i in range(q):
        acc += a3[:, i, :]
    a4 = acc.reshape(nr, nc, q)
    cells = np.zeros((nr, nc), np.float64)
    for j in range(q):
        cells += a4[:, :, j]
    y = gaussian_filter((cells / (q * q)).astype(np.float32), s / q).astype(np.float64)
    t = np.clip((np.arange(oy, oy + h, dtype=np.float64) + 0.5) / q - 0.5 - c0, 0, nr - 1)
    i0 = np.minimum(np.floor(t).astype(np.int64), nr - 2)
    ft = (t - i0)[:, None]
    rows = y[i0] * (1 - ft) + y[i0 + 1] * ft
    if nc < 2:
        return np.repeat(rows[:, :1], w, 1).astype(np.float32)
    u = np.clip((np.arange(w, dtype=np.float64) + 0.5) / q - 0.5, 0, nc - 1)
    j0 = np.minimum(np.floor(u).astype(np.int64), nc - 2)
    fu = (u - j0)[None, :]
    return (rows[:, j0] * (1 - fu) + rows[:, j0 + 1] * fu).astype(np.float32)


def edge_profile_clamp_reach(f, p=None):
    """Rows of real image a band of edge_profile_clamp(..., smooth='pooled') must carry above and below its own rows for its
    values to equal the whole image's (halo round 2; strip-exact). The sum of every step's reach: the orientation and edge
    test, the component test (a component of >= L px has >= L px within L - 1 px of each of its pixels, so labelling a band
    with that margin decides it exactly), the zone dilations, the tangent means, the envelope's min / max, the pooled tone
    and texture fields (cells of 3f px, blurred over 4 sigma), and a margin of 8 rows."""
    p = {**DEHALO, **(p or {})}
    f = float(max(f, 1.0))
    r = max(3, int(round(1.5 * f)))
    K = max(1, int(math.ceil(2.5 * 2.0 * f)))
    rad = lambda s_: int(4.0 * s_ + 0.5)
    rd, ri = rad(max(1.0, 0.5 * f)), rad(max(2.0, f))
    e_ = max(rd + ri, rd + 2, int(math.ceil(1.5 * f)) + 2) + int(math.ceil(p['len_min'] * f)) - 1
    w_ = e_ + r + int(p['pad']) + rad(1.0)
    near = w_ + K
    Rr = max(near + r, K + rd + ri)
    s_ = 12.0 * f
    q = int(s_ // 4)
    fields = max(w_ + r + 2, rad(f)) + (rad(s_ / q) + 2) * q
    ex = max(near, Rr + r, fields)
    return int(max(ex + K, Rr + r + 2, w_)) + 8



# ---------------------------------------------------------------------------------------------------------------------------
# Halo round 2 revision (halo2:fix-2, 21 Nov 2026; halo2:check D1, D3, D4): the 'edge3' clamp.
# - Grain (D1): round 2 removed a pixel's excess in the share in which it is common along the edge, so a pixel under a
#   strong rim was set to the bound, which is smooth along the edge: its grain was lost and a smooth band appeared. Here the
#   along-edge mean's excess E is removed as an OFFSET (smooth along the edge), and each pixel keeps its own along-edge
#   high-pass h (pixel - tangent mean) up to kh x the local texture level (+ the allowance); only the part of h beyond that
#   (a bead of the halo, as 5.0.1's rims carry) goes, fading in with E.
# - Guard (D4): round 2's guard keeps every lift (drop) on a ridge (valley) of the BILINEAR reference, whose flanks are
#   wider than the line, so an overshoot beside a thin line is kept with it. 'fringe' holds the guard only where the
#   source's own pixel is on the line (nearest sampling of the source at the pixel and at +-r along the normal); 'srcwin'
#   (round 1's r1sw) bounds a guarded pixel at the source's own pixels within the window; 'fringe_srcwin' both. The
#   service's policy is DEHALO3_GUARD (halo2:fix-2's measurement: r1sw costs thin-line contrast).
# - Chroma (D3): the final output's opponent chroma (R' - Y', B' - Y') goes through the same clamp against the source's
#   local chroma envelope, where and in the proportion that the luma halo was removed (post + final), so a restored dark
#   rim takes back its colour instead of turning grey; the luma stays the clamp's.
# Every step is local or on _gpool's grid anchored to the whole image, with float64 sample coordinates: exact in bands with
# edge_profile_clamp3_reach() rows of halo (tests/engine/test_halo2_fix2.py).
DEHALO3 = dict(DEHALO, kh=2.5, rho_l=0.02)
DEHALO3_GUARDS = ('bil', 'fringe', 'srcwin', 'fringe_srcwin')
DEHALO3_GUARD = {'first': 'fringe', 'later': 'fringe'}


def _src_index(n_out, n_src, o0=0, n_full=None):
    """The source index (nearest, no interpolation) of output rows (columns) o0 .. o0 + n_out of n_full output rows."""
    n_full = n_out + o0 if n_full is None else int(n_full)
    t = (np.arange(o0, o0 + n_out, dtype=np.float64) + 0.5) * n_src / n_full
    return np.minimum(t.astype(np.int64), n_src - 1)


def _bilinear_rows(a, H_full, W, oy=0, h=None):
    """torch's bilinear (align_corners=False, no antialias) of a [hs, ws] or [hs, ws, c] array to H_full x W, for output
    rows oy .. oy + h only, computed in float64 from global coordinates (a band gives the whole image's rows)."""
    a = np.asarray(a, np.float32)
    hs, ws = a.shape[:2]
    h = H_full - oy if h is None else int(h)
    sy = np.maximum((np.arange(oy, oy + h, dtype=np.float64) + 0.5) * hs / H_full - 0.5, 0)
    sx = np.maximum((np.arange(W, dtype=np.float64) + 0.5) * ws / W - 0.5, 0)
    y0 = np.minimum(np.floor(sy).astype(np.int64), hs - 1)
    x0 = np.minimum(np.floor(sx).astype(np.int64), ws - 1)
    y1, x1 = np.minimum(y0 + 1, hs - 1), np.minimum(x0 + 1, ws - 1)
    fy, fx = sy - y0, sx - x0
    ex = (slice(None),) + (None,) * (a.ndim - 1)
    fy, fx = fy[ex], fx[(None, slice(None)) + (None,) * (a.ndim - 2)]
    a64 = a.astype(np.float64)
    r0 = a64[y0][:, x0] * (1 - fx) + a64[y0][:, x1] * fx
    r1 = a64[y1][:, x0] * (1 - fx) + a64[y1][:, x1] * fx
    return (r0 * (1 - fy) + r1 * fy).astype(np.float32)


def _clamp_geometry(Yref, f, p):
    """Where the round-2 clamp acts (edges of geometry of Yref and their orientation; as edge_profile_clamp), or None."""
    f = float(max(f, 1.0))
    r = max(3, int(round(1.5 * f)))
    sig_t = 2.0 * f
    K = max(1, int(math.ceil(2.5 * sig_t)))
    theta, coh, gx, gy = _orient(Yref, max(1.0, 0.5 * f), max(2.0, f))
    e = geometry_edges(Yref, gx, gy, coh, f, p['c_edge'], p['coh_min'], p['len_min'] * f, coord64=True)
    del gx, gy, coh
    if not e.any():
        return None
    e_rows = e.any(1)                                         # (the port: the rows that hold an edge of geometry)
    w = np.clip(gaussian_filter(binary_dilation(e, iterations=r + int(p['pad'])).astype(np.float32), 1.0) * 1.5, 0, 1)
    del e
    act = w > 0.01
    near = binary_dilation(act, iterations=K)
    return dict(f=f, r=r, sig_t=sig_t, off_sigma=12.0 * f, theta=theta, w=w, act=act, near=near, e_rows=e_rows)


def _clamp_channel(A2, Aenv, g, p, oy=0, H_full=None, guard='bil', Ysrc=None, sel=None):
    """The edge3 removal on one channel A2 (luma, or one opponent chroma) against the non-ringing reference Aenv of the same
    channel, at the geometry g (_clamp_geometry). sel (optional bool map): compute only at the active pixels inside it
    (every value there is the unrestricted call's: the tone and texture fields still use the whole zone, and the tangent
    means and the envelope are computed over sel's own neighbourhood); elsewhere A2 is returned unchanged. Returns float32."""
    blur = lambda x_, s_: _gpool(x_, s_, oy, H_full)
    H, W = A2.shape
    r, sig_t, theta, w, act, near = g['r'], g['sig_t'], g['theta'], g['w'], g['act'], g['near']
    if sel is not None:
        K = max(1, int(math.ceil(2.5 * sig_t)))
        near = binary_dilation(act & sel, iterations=K)
    ys, xs = np.nonzero(binary_dilation(near, iterations=r))
    R = Aenv.copy()                                           # the reference averaged along the edge tangent
    R[ys, xs] = _line_mean(Aenv, ys, xs, theta[ys, xs], sig_t)
    del ys, xs
    lo, hi = minimum_filter(R, 2 * r + 1), maximum_filter(R, 2 * r + 1)
    far = (~binary_dilation(act, iterations=r + 2)).astype(np.float32)
    den = blur(far, g['off_sigma'])
    off = np.where(den > 0.05, blur((A2 - Aenv) * far, g['off_sigma']) / np.maximum(den, 1e-6), 0.0).astype(np.float32)
    hp = A2 - gaussian_filter(A2, g['f'])
    tex = np.sqrt(np.maximum(np.where(den > 0.05, blur(hp * hp * far, g['off_sigma']) / np.maximum(den, 1e-6),
                                      blur(hp * hp, g['off_sigma'])), 0)).astype(np.float32)
    del hp, far, den
    tol = (p['tol'] + p['kstd'] * tex / math.sqrt(_line_neff(sig_t))).astype(np.float32)
    ya, xa = np.nonzero(act if sel is None else act & sel)
    offa, tola, texa = off[ya, xa], tol[ya, xa], tex[ya, xa]
    loa, hia = lo[ya, xa] + offa - tola, hi[ya, xa] + offa + tola
    del off, tol, tex, lo, hi
    if guard in ('srcwin', 'fringe_srcwin'):
        Sn = np.asarray(Ysrc, np.float32)[_src_index(H, Ysrc.shape[0], oy, H_full)][:, _src_index(W, Ysrc.shape[1])]
        fla = np.minimum(minimum_filter(Sn, 2 * r + 1)[ya, xa] + offa - tola, loa)
        fha = np.maximum(maximum_filter(Sn, 2 * r + 1)[ya, xa] + offa + tola, hia)
        del Sn
    tha = theta[ya, xa]
    a2 = A2[ya, xa]
    P = _line_mean(A2, ya, xa, tha, sig_t)
    E = P - np.clip(P, loa, hia)                              # the excess of the along-edge mean profile
    from scipy.ndimage import map_coordinates
    sx, cy = np.sin(tha).astype(np.float64), np.cos(tha).astype(np.float64)
    yaf, xaf = ya.astype(np.float64), xa.astype(np.float64)
    Rm = map_coordinates(R, [yaf - r * sx, xaf - r * cy], order=1, mode='nearest', prefilter=False)
    Rp = map_coordinates(R, [yaf + r * sx, xaf + r * cy], order=1, mode='nearest', prefilter=False)
    Rc = R[ya, xa]
    ld = float(p['line_d'])
    keep_lift = np.clip(1 - (Rc - np.maximum(Rm, Rp)) / ld, 0, 1)        # 0 on a light line of the reference
    keep_drop = np.clip(1 - (np.minimum(Rm, Rp) - Rc) / ld, 0, 1)        # 0 on a dark line of the reference
    del Rm, Rp, Rc
    if guard in ('fringe', 'fringe_srcwin'):                   # the guard holds only on the source's own line pixels
        Ys_ = np.asarray(Ysrc, np.float32)
        hs, ws = Ys_.shape
        Hf = H + oy if H_full is None else int(H_full)

        def sn(yy, xx):
            iy = np.clip(((oy + yy + 0.5) * hs / Hf).astype(np.int64), 0, hs - 1)
            ix = np.clip(((xx + 0.5) * ws / W).astype(np.int64), 0, ws - 1)
            return Ys_[iy, ix]
        Sc, Sm, Sp = sn(yaf, xaf), sn(yaf - r * sx, xaf - r * cy), sn(yaf + r * sx, xaf + r * cy)
        keep_lift = 1 - (1 - keep_lift) * np.clip((Sc - np.maximum(Sm, Sp)) / ld, 0, 1)
        keep_drop = 1 - (1 - keep_drop) * np.clip((np.minimum(Sm, Sp) - Sc) / ld, 0, 1)
        del Sc, Sm, Sp
    El = P - np.clip(P, fla, fha) if guard in ('srcwin', 'fringe_srcwin') else np.zeros_like(P)
    Ep = keep_lift * np.maximum(E, 0) + (1 - keep_lift) * np.maximum(El, 0)
    Em = keep_drop * np.minimum(E, 0) + (1 - keep_drop) * np.minimum(El, 0)
    h = a2 - P                                                # the pixel's own along-edge high-pass (its grain)
    b = float(p['kh']) * texa + tola                          # the texture level it keeps
    gp = np.clip(Ep / np.maximum(tola, 1e-6), 0, 1)           # a bead's cap fades in with the shared excess
    gm = np.clip(-Em / np.maximum(tola, 1e-6), 0, 1)
    rem = w[ya, xa] * (Ep + gp * np.maximum(h - b, 0) + Em + gm * np.minimum(h + b, 0))
    out = A2.copy()
    out[ya, xa] = a2 - rem
    return out


def edge_profile_clamp3(Y2, Yref, f, p=None, oy=0, H_full=None, Ysrc=None, guard='bil'):
    """The halo fix, round 2 revision: edge_profile_clamp's envelope, tone offset, allowance and zone (pooled fields, the
    original as reference), with the grain kept (an offset smooth along the edge, the pixel's own along-edge high-pass up to
    kh x the texture level) and the thin-line guard `guard` (DEHALO3_GUARDS). Ysrc: the source luma at its OWN resolution
    (the pass input for a first pass, the anchor at its own frame for a later pass), for the guards other than 'bil'.
    oy, H_full: Y2's first row and the whole image's rows (a band). Returns Y2 itself where no edge of geometry exists."""
    if guard not in DEHALO3_GUARDS:
        raise ValueError(f'edge_profile_clamp3: guard must be one of {DEHALO3_GUARDS} (got {guard!r})')
    if guard != 'bil' and Ysrc is None:
        raise ValueError(f'edge_profile_clamp3: guard {guard!r} needs Ysrc, the source at its own resolution')
    p = {**DEHALO3, **(p or {})}
    Y2 = np.asarray(Y2, np.float32)
    g = _clamp_geometry(np.asarray(Yref, np.float32), f, p)
    if g is None:
        return Y2
    return _clamp_channel(Y2, np.asarray(Yref, np.float32), g, p, oy, H_full, guard, Ysrc)


def edge_profile_clamp3_reach(f, p=None):
    """Rows of real image a band of edge_profile_clamp3 / _final_clamp3 must carry above and below its own rows: the round-2
    clamp's reach (edge_profile_clamp_reach). The guards' samples (+-r along the normal, a window of r) and the chroma pass
    read no further than the steps that reach already counts (tests/engine/test_halo2_fix2.Bands)."""
    return edge_profile_clamp_reach(f, p)


def edge_profile_clamp3_bands(Y2, Yref, f, band, halo, p=None, Ysrc=None, guard='bil'):
    """edge_profile_clamp3 over full-width bands of `band` rows, each read with `halo` rows above and below; with
    halo >= edge_profile_clamp3_reach(f) it equals the whole call, value for value."""
    Y2 = np.asarray(Y2, np.float32)
    Yref = np.asarray(Yref, np.float32)
    H = Y2.shape[0]
    out = np.empty_like(Y2)
    for y0 in range(0, H, int(band)):
        y1 = min(H, y0 + int(band))
        a, b = max(0, y0 - int(halo)), min(H, y1 + int(halo))
        out[y0:y1] = edge_profile_clamp3(Y2[a:b], Yref[a:b], f, p, oy=a, H_full=H, Ysrc=Ysrc, guard=guard)[y0 - a:y1 - a]
    return out


def _final_clamp3(out, ref, dYp=None, oy=0, H_full=None):
    """'edge3f': the edge3 clamp once more on the finish's final RGB, the luma change added to every channel; then each
    opponent chroma channel (R' - Y', B' - Y') of every pixel either clamp changed goes through the same clamp against the
    source's chroma (bilinear of the source RGB), in the proportion rho = |luma removed| / rho_l (post's dYp + this one's),
    capped at 1; G' keeps the luma. ref = (Yref at output size, f, source luma at its own size, source RGB at its own size,
    guard). Unchanged pixels are the finish's own, bit for bit; with no edge of geometry `out` itself is returned."""
    if ref is None:
        return out
    p = dict(DEHALO3)
    out = np.asarray(out, np.float32)
    H, W = out.shape[:2]
    Hf = H + oy if H_full is None else int(H_full)
    Yref = np.asarray(ref[0], np.float32)
    g = _clamp_geometry(Yref, ref[1], p)
    if g is None:
        return out
    Y = luma(out).astype(np.float32)
    Y2 = _clamp_channel(Y, Yref, g, p, oy, H_full, ref[4], ref[2])
    res = np.clip(out + (Y2 - Y)[..., None], 0, 1).astype(np.float32)
    dYt = Y2 - Y if dYp is None else (Y2 - Y) + np.asarray(dYp, np.float32)
    rho = np.clip(np.abs(dYt) / float(p['rho_l']), 0, 1).astype(np.float32)
    del dYt
    if rho.any():
        Yr = luma(res).astype(np.float32)
        Sr = np.asarray(ref[3], np.float32)
        Ys = luma(Sr).astype(np.float32)
        for c in (0, 2):
            Cref = _bilinear_rows(Sr[..., c] - Ys, Hf, W, oy, H)
            C0 = res[..., c] - Yr
            Cn = _clamp_channel(C0, Cref, g, p, oy, H_full, 'bil', None, sel=rho > 0)
            res[..., c] = Yr + C0 + rho * (Cn - C0)
            del Cref, C0, Cn
        res[..., 1] = (Yr - 0.2126 * res[..., 0] - 0.0722 * res[..., 2]) / 0.7152
        res = np.clip(res, 0, 1).astype(np.float32)
    return res




# --- the band drivers (the port's own) -------------------------------------------------------------------------------------
def _bands(H, height, halo):
    for y0 in range(0, H, int(height)):
        y1 = min(H, y0 + int(height))
        yield y0, y1, max(0, y0 - int(halo)), min(H, y1 + int(halo))


def _flush(a):
    if hasattr(a, 'flush'):
        a.flush()


def guard_for(anchor):
    """The thin-line guard of a pass: DEHALO3_GUARD['first'] for a pass whose input is the original, 'later' with an anchor."""
    return DEHALO3_GUARD['first' if anchor is None else 'later']


def clamp_luma_bands(Y2, Yref, f, Ysrc, out, height, halo=None, guard='fringe', progress=None):
    """edge_profile_clamp3(Y2, Yref, f, Ysrc=Ysrc, guard=guard) of the whole image (post's clamp, after keep_blacks), by
    full-width row bands of `height` rows, each read with `halo` rows of real image above and below (default: the reach).
    Y2, Yref: H x W float32 (planes or arrays); Ysrc: the source luma at its own size (read where the guard samples it);
    out: an H x W float32 plane or array, written band by band. Returns out."""
    H = int(Y2.shape[0])
    halo = edge_profile_clamp3_reach(f) if halo is None else int(halo)
    for y0, y1, a, b in _bands(H, height, halo):
        r = edge_profile_clamp3(np.array(Y2[a:b], np.float32), np.array(Yref[a:b], np.float32), f, oy=a, H_full=H,
                                Ysrc=Ysrc, guard=guard)
        out[y0:y1] = r[y0 - a:y1 - a]
        del r
        if progress is not None:
            progress('halo reduction')
    _flush(out)
    return out


def _bilinear_rows_part(a, H_full, W, oy, h):
    """_bilinear_rows(a, H_full, W, oy, h) of a 2-D source, reading only the source rows those output rows use."""
    hs, ws = a.shape[:2]
    sy = np.maximum((np.arange(oy, oy + h, dtype=np.float64) + 0.5) * hs / H_full - 0.5, 0)
    sx = np.maximum((np.arange(W, dtype=np.float64) + 0.5) * ws / W - 0.5, 0)
    y0 = np.minimum(np.floor(sy).astype(np.int64), hs - 1)
    x0 = np.minimum(np.floor(sx).astype(np.int64), ws - 1)
    y1, x1 = np.minimum(y0 + 1, hs - 1), np.minimum(x0 + 1, ws - 1)
    fy, fx = sy - y0, sx - x0
    fy, fx = fy[:, None], fx[None, :]
    s0, s1 = int(y0.min()), int(y1.max()) + 1
    a64 = np.asarray(a[s0:s1], np.float32).astype(np.float64)
    y0, y1 = y0 - s0, y1 - s0
    r0 = a64[y0][:, x0] * (1 - fx) + a64[y0][:, x1] * fx
    r1 = a64[y1][:, x0] * (1 - fx) + a64[y1][:, x1] * fx
    return (r0 * (1 - fy) + r1 * fy).astype(np.float32)


def source_planes(src_rows, Ys, D0, D2, rows=1152):
    """The source's luma (luma(S).astype(float32), as v4_finish and _final_clamp3 compute it) and opponent chroma (S[..., 0]
    and S[..., 2] less that luma) at the source's own size, by row chunks (every value is per pixel, so a chunk gives the
    whole array's values). src_rows(y0, y1): float32 RGB rows of the source (the pass input, or the anchor for a later pass)."""
    hs = int(Ys.shape[0])
    for y0 in range(0, hs, int(rows)):
        y1 = min(hs, y0 + int(rows))
        S = np.asarray(src_rows(y0, y1), np.float32)
        y = luma(S).astype(np.float32)
        Ys[y0:y1] = y
        D0[y0:y1] = S[..., 0] - y
        D2[y0:y1] = S[..., 2] - y
        del S, y
    for a in (Ys, D0, D2):
        _flush(a)


def final_clamp_bands(out, Yref, f, Ysrc, D0, D2, dYp, res0, resf, height, halo=None, guard='fringe', progress=None):
    """_final_clamp3(out, (Yref, f, Ysrc, S, guard), dYp) of the whole image by row bands (the clamp on the finish's final
    output: its luma, then the opponent chroma of every pixel either clamp changed). D0, D2: the source's opponent chroma at
    its own size (source_planes). res0, resf: H x W x 3 float32 planes or arrays the bands write, res0 with the luma clamp
    alone and resf with the chroma pass too. The whole call decides twice for the whole image: with no edge of geometry
    anywhere it returns the finish's own output, and when no pixel changed (rho 0 everywhere) it skips the chroma pass. Each
    band makes both results and the two decisions are taken over every band's own rows. Returns (which, stats): which of
    'out', 'res0' or 'resf' holds the whole call's result."""
    p = dict(DEHALO3)
    H, W = int(out.shape[0]), int(out.shape[1])
    halo = edge_profile_clamp3_reach(f) if halo is None else int(halo)
    geom = False
    changed = bare = 0
    for y0, y1, a, b in _bands(H, height, halo):
        o = np.array(out[a:b], np.float32)
        yr = np.array(Yref[a:b], np.float32)
        g = _clamp_geometry(yr, f, p)
        Y = luma(o).astype(np.float32)
        if g is None:
            Y2 = Y
            bare += 1
        else:
            geom = geom or bool(g['e_rows'][y0 - a:y1 - a].any())
            Y2 = _clamp_channel(Y, yr, g, p, a, H, guard, Ysrc)
        res = np.clip(o + (Y2 - Y)[..., None], 0, 1).astype(np.float32)
        dYt = (Y2 - Y) + np.array(dYp[a:b], np.float32)
        rho = np.clip(np.abs(dYt) / float(p['rho_l']), 0, 1).astype(np.float32)
        del dYt, o, Y2, Y
        changed += int(np.count_nonzero(rho[y0 - a:y1 - a]))
        res0[y0:y1] = res[y0 - a:y1 - a]
        rf = res.copy()
        Yr = luma(res).astype(np.float32)
        for c, Dc in ((0, D0), (2, D2)):
            C0 = res[..., c] - Yr
            if g is None:
                Cn = C0
            else:
                Cref = _bilinear_rows_part(Dc, H, W, a, b - a)
                Cn = _clamp_channel(C0, Cref, g, p, a, H, 'bil', None, sel=rho > 0)
                del Cref
            rf[..., c] = Yr + C0 + rho * (Cn - C0)
            del C0, Cn
        rf[..., 1] = (Yr - 0.2126 * rf[..., 0] - 0.0722 * rf[..., 2]) / 0.7152
        rf = np.clip(rf, 0, 1).astype(np.float32)
        resf[y0:y1] = rf[y0 - a:y1 - a]
        del rf, res, rho, Yr, g, yr
        if progress is not None:
            progress('halo reduction')
    _flush(res0)
    _flush(resf)
    which = 'out' if not geom else ('resf' if changed else 'res0')
    return which, {'edges_of_geometry': bool(geom), 'pixels_changed': int(changed), 'bands_without_edges': bare,
                   'result': which}
