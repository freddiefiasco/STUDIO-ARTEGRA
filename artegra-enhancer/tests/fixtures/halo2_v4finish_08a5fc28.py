"""V4finish implementation."""


import math
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from scipy.ndimage import (gaussian_filter, uniform_filter, binary_dilation, zoom, maximum_filter, minimum_filter, label,
                           find_objects, labeled_comprehension, binary_opening, binary_erosion)
try:  # development dumps (devdump.py); this file is also loaded on its own by CPU replays, without the package
    from . import devdump as _dd
except ImportError:
    _dd = None


def _dumping():
    return _dd is not None and _dd.enabled()


def _dump(name, a, rounding='round', channels=3):
    """Development only: save a copy of a finish step's result (devdump.save); a no-op unless CU_DEV_DUMP_DIR is set."""
    if _dumping():
        _dd.save(name, a, rounding=rounding, channels=channels)


def _gauss1d(sigma, order=0, device='cpu'):
    r = max(1, int(math.ceil(3.5 * sigma)))
    x = torch.arange(-r, r + 1, dtype=torch.float32, device=device)
    g = torch.exp(-x * x / (2 * sigma * sigma)); g = g / g.sum()
    if order == 1:
        g = -x / (sigma * sigma) * g
    return g


def _sep(img, kx, ky):
    """img [N,1,H,W]; separable correlation with reflect padding."""
    px, py = kx.numel() // 2, ky.numel() // 2
    img = F.pad(img, (px, px, 0, 0), mode='reflect')
    img = F.conv2d(img, kx.view(1, 1, 1, -1))
    img = F.pad(img, (0, 0, py, py), mode='reflect')
    return F.conv2d(img, ky.view(1, 1, -1, 1))


def _blur(img, sigma):
    if sigma <= 0:
        return img
    if sigma > 8:  
        f = int(sigma // 4)
        h, w = img.shape[-2:]
        s = F.avg_pool2d(img, f, ceil_mode=True)
        s = _blur(s, sigma / f)
        return F.interpolate(s, size=(h, w), mode='bicubic', align_corners=False)
    g = _gauss1d(sigma, device=img.device)
    return _sep(img, g, g)


def _quantile(t, q):
    flat = t.flatten()
    if flat.numel() > 4_000_000:
        flat = flat[:: flat.numel() // 4_000_000 + 1]
    return torch.quantile(flat.float(), q)


def luminance(rgb):
    """rgb [H,W,3] in 0..1 -> [1,1,H,W]"""
    return (0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2])[None, None]


def creativity_map(rgb, lo=0.25, hi=1.0, gs=1.5, rs=6.0, p_lo=0.25, p_hi=0.85, coh_k=0.6, feather=12.0, abs_hi=0.0):
    """rgb [H,W,3] 0..1 (PRE). Returns [H,W] in [lo,hi].
    t = energy_n * (1 - coh_k * coherence): flats -> lo; parallel structure (hair, grain, edges) partial; incoherent texture -> hi.
    abs_hi > 0 floors the upper normalisation energy, so a mostly flat frame (interiors) does not stretch mild texture to full creativity."""
    L = luminance(rgb.float())
    g, dg = _gauss1d(gs, device=L.device), _gauss1d(gs, 1, device=L.device)
    gx, gy = _sep(L, dg, g), _sep(L, g, dg)
    jxx, jyy, jxy = _blur(gx * gx, rs), _blur(gy * gy, rs), _blur(gx * gy, rs)
    tr = jxx + jyy; det = jxx * jyy - jxy * jxy
    disc = torch.sqrt(torch.clamp(tr * tr / 4 - det, min=0))
    l1, l2 = tr / 2 + disc, torch.clamp(tr / 2 - disc, min=0)
    energy = torch.sqrt(l1 + l2)
    a, b = _quantile(energy, p_lo), _quantile(energy, p_hi)
    if abs_hi:
        b = torch.clamp(b, min=abs_hi)
    en = torch.clamp((energy - a) / torch.clamp(b - a, min=1e-9), 0, 1)
    coh = ((l1 - l2) / (l1 + l2 + 1e-12)) ** 2
    t = _blur(en * (1 - coh_k * coh), feather)
    t = torch.clamp(t / torch.clamp(_quantile(t, 0.99), min=0.75 if abs_hi else 1e-6), 0, 1)  
    return (lo + (hi - lo) * t)[0, 0]


def lowfreq_transfer(image, reference, sigma=24.0, strength=1.0, limit=None, robust=0.0):
    """image [B,H,W,C] (generated, output size); reference [B,h,w,C] (source, any size). Returns [B,H,W,C]."""
    x = image.permute(0, 3, 1, 2).float()
    r = reference.permute(0, 3, 1, 2).float().to(x.device)
    if r.shape[-2:] != x.shape[-2:]:
        r = F.interpolate(r, size=x.shape[-2:], mode='bicubic', align_corners=False, antialias=False)
    B, C, H, W = x.shape
    lp = lambda t: _blur(t.reshape(B * C, 1, H, W), sigma).reshape(B, C, H, W)
    if robust:  
        d = r - x
        dm = _blur(d.abs().mean(1, keepdim=True), 4.0)
        wgt = torch.exp(-(dm / robust) ** 2)
        num = _blur((wgt * d).reshape(B * C, 1, H, W), sigma).reshape(B, C, H, W)
        den = _blur(wgt.expand(B, C, H, W).reshape(B * C, 1, H, W), sigma).reshape(B, C, H, W)
        c = num / torch.clamp(den, min=1e-3)
    else:
        c = lp(r) - lp(x)
    if limit:  
        mag = torch.sqrt((c * c).mean(1, keepdim=True))
        c = c * torch.clamp((limit[1] - mag) / max(limit[1] - limit[0], 1e-6), 0, 1)
    out = x + strength * c
    return torch.clamp(out, 0, 1).permute(0, 2, 3, 1).to(image.dtype)


R = (1, 3, 8, 24, 64)                                       
SIG = [float(np.sqrt(r * (r + 1))) for r in R]              
DEF = dict(dead=1, r0=1.5, r1=1.0, r2=1.0, r3=1.05, r4=1.05, g0=(0.85, 1.7), g12=(0.70, 1.10), g34=(0.9, 1.15), beta=3.0,
           tau0=10.0, kappa=0.12, iters=4)                  
DEAD = [(1.40, 2.10), (0.92, 1.05), (0.92, 1.08), (1.00, 1.12), (1.00, 1.12)]  


def g(x, s, mode='constant'):
    """Gaussian blur; for s > 8 through a grid pooled by f = int(s / 4) and zoomed back.
    mode: scipy zoom's mode. 'constant' is 5.0.1's (zoom's default): where a side is an exact multiple of f, float rounding
    can put the last row's (column's) sample past the last pooled cell, and 'constant' reads 0 there (fin_core's bright
    last row on 1536- and 3072-row frames). 'nearest' (the v6 finish) reads the last cell; every other pixel is the same."""
    if s <= 8:
        return gaussian_filter(x, s)
    f = int(s // 4); h, w = x.shape
    H, W = -(-h // f) * f, -(-w // f) * f
    xp = np.pad(x, ((0, H - h), (0, W - w)), mode='edge').reshape(H // f, f, W // f, f).mean((1, 3))
    y = gaussian_filter(xp, s / f)
    return zoom(y, (H / y.shape[0], W / y.shape[1]), order=1, mode=mode)[:h, :w].astype(np.float32)


def tbb(x, r):
    for _ in range(3):
        x = uniform_filter(x, size=2 * r + 1, mode='reflect')
    return x


def luma(a):
    return 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]


def stack(L):
    bl = [L] + [tbb(L, r) for r in R]
    return [bl[i] - bl[i + 1] for i in range(5)], bl[-1]


def locE(b, s, mode='constant'):
    return np.sqrt(np.maximum(g(b * b, 2 * s, mode), 0)) + 1e-5


def edge_zone(Yq, pct=98.5, dil=2):
    gy, gx = np.gradient(tbb(Yq, 1)); gm = np.sqrt(gx * gx + gy * gy)
    e = gm >= np.percentile(gm, pct)
    return e, binary_dilation(e, iterations=dil)


def fin_core(D, Q, p=None):
    """p['zoom']: g()'s zoom mode ('constant' 5.0.1; 'nearest' the v6 finish, no bright or dark last row)."""
    p = {**DEF, **(p or {})}
    zm = p.get('zoom', 'constant')
    Y, Yq = luma(D), luma(Q)
    BQ, _ = stack(Yq); _, zone = edge_zone(Yq)
    DEADL = DEAD
    EQ = [locE(BQ[k], SIG[k], zm) for k in range(5)]; del BQ
    tx = np.sqrt(EQ[1] ** 2 + EQ[2] ** 2)
    TEX = np.clip((tx - np.percentile(tx, 35)) / (np.percentile(tx, 75) - np.percentile(tx, 35) + 1e-6), 0, 1).astype(np.float32)
    clamps = [p['g0'], p['g12'], p['g12'], p['g34'], p['g34']]
    zone0 = binary_dilation(zone, iterations=int(p['edge0'][1])) if 'edge0' in p else None  
    Ycur = Y
    for _ in range(int(p['iters'])):
        BD, resD = stack(Ycur); acc = resD
        for k in range(5):
            ratio = EQ[k] / locE(BD[k], SIG[k], zm)
            lo, hi = tuple(p['b0']) if (k == 0 and 'b0' in p) else DEADL[k]
            if k == 0 and 'b0_flat' in p:
                lo = p['b0_flat'][0] + TEX * (lo - p['b0_flat'][0]); hi = p['b0_flat'][1] + TEX * (hi - p['b0_flat'][1])
            gain = np.where(ratio * hi < 1, ratio * hi, np.where(ratio * lo > 1, ratio * lo, 1.0))
            gain = g(np.clip(gain, *clamps[k]).astype(np.float32), p['beta'] * SIG[k], zm)
            if k in (1, 2):
                gain = np.where(zone, np.minimum(gain, 1.0), gain)
            if k == 0 and zone0 is not None:
                gain = np.where(zone0, np.minimum(gain, float(p['edge0'][0])), gain)
            acc = acc + BD[k] * gain
        Ycur = acc.astype(np.float32); del BD
    BD, resD = stack(Ycur)
    b0 = p['tau0'] * np.tanh(BD[0] / p['tau0'])
    if p['kappa']:
        pol = np.sign(gaussian_filter(BD[0] ** 3, 8.0))
        b0 = b0 * (1 + p['kappa'] * pol * np.sign(b0))
    Y2 = resD + b0 + BD[1] + BD[2] + BD[3] + BD[4]
    Y2 = np.where(Y2 > 0.95, 0.95 + 0.05 * np.tanh((Y2 - 0.95) / 0.05), Y2)
    return Y.astype(np.float32), Yq.astype(np.float32), Y2.astype(np.float32), zone


def smooth01(u):
    u = np.clip(u, 0, 1); return u * u * (3 - 2 * u)


def fin_post(D, Y, Yq, Y2, zone, antiring=None, keep_blacks=0.0, chroma='add', knee=(0.45, 0.75), ar_mode='plain', Q=None, src=(2.0, 1.0, 1.15)):
    """V4finish implementation."""


    Y2 = Y2.copy()
    if antiring:
        r, tol = int(antiring[0]), float(antiring[1])
        az = binary_dilation(zone, iterations=r + 2)
        w = gaussian_filter(az.astype(np.float32), 1.5)
        lo, hi = minimum_filter(Yq, 2 * r + 1) - tol, maximum_filter(Yq, 2 * r + 1) + tol
        if ar_mode == 'upper':  
            lo = np.full_like(lo, -1.0)
        Y2 = Y2 + w * (np.clip(Y2, lo, hi) - Y2)
    if keep_blacks:
        wd = np.clip((0.22 - Y) / 0.17, 0, 1)
        Y2 = Y2 - float(keep_blacks) * wd * np.maximum(Y2 - Y, 0)
    dY = (Y2 - Y)[..., None]
    add = D + dY
    if chroma == 'add':
        out = add
    else:
        gn = np.clip(Y2 / np.maximum(Y, 1e-4), 0.5, 2.0)[..., None]
        a = np.clip((Y - 0.004) / 0.012, 0, 1)[..., None]
        mul = a * D * gn + (1 - a) * add
        if chroma == 'mul':
            out = mul
        elif chroma == 'hyb':
            wk = smooth01((Y - knee[0]) / (knee[1] - knee[0]))[..., None]
            out = (1 - wk) * mul + wk * add
        elif chroma == 'signed':
            out = np.where(dY < 0, mul, add)
        elif chroma in ('srcmix', 'srcwarm'):  
            sg, m0, m1 = src
            Cd = D - Y[..., None]; Cq = Q - Yq[..., None]
            bc = np.stack([gaussian_filter(Cd[..., c], sg) for c in range(3)], -1); bq = np.stack([gaussian_filter(Cq[..., c], sg) for c in range(3)], -1)
            rc = np.sqrt((bc ** 2).sum(-1)) / np.maximum(gaussian_filter(Y, sg), 0.04)
            rq = np.sqrt((bq ** 2).sum(-1)) / np.maximum(gaussian_filter(Yq, sg), 0.04)
            wk = smooth01((rc / np.maximum(rq, 1e-4) - m0) / (m1 - m0))
            if chroma == 'srcwarm':  
                wk = wk * warm_gate(D)
            out = (1 - wk[..., None]) * mul + wk[..., None] * add
        elif chroma == 'mulsafe':
            m = D * gn
            over = np.maximum(m.max(-1, keepdims=True) - 1.0, 0)  
            
            mx = np.maximum(D.max(-1, keepdims=True), 1e-4)
            gcap = np.minimum(gn, 1.0 / mx)
            m2 = D * gcap
            lost = Y2[..., None] - luma(m2)[..., None]
            m2 = m2 + np.where(over > 0, np.maximum(lost, 0), 0)
            out = a * m2 + (1 - a) * add
        else:
            raise ValueError(chroma)
    return np.clip(out, 0, 1).astype(np.float32)


def hsv(a):
    mx, mn = a.max(-1), a.min(-1); c = mx - mn
    s = c / np.maximum(mx, 1e-6)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    h = np.zeros_like(mx)
    m = c > 1e-6
    rr = m & (mx == r); gg = m & (mx == g) & ~rr; bb = m & ~rr & ~gg
    h[rr] = (60 * ((g - b)[rr] / c[rr])) % 360
    h[gg] = 60 * ((b - r)[gg] / c[gg]) + 120
    h[bb] = 60 * ((r - g)[bb] / c[bb]) + 240
    return h, s, mx


def warm_gate(a, lo=40.0, hi=55.0, red_lo=330.0, red_hi=345.0):
    """1 for warm hues (reds/oranges/yellow-browns, hue <= lo or >= red_hi), fading to 0 by hi / red_lo; 0 for greens/blues."""
    h, s_, v = hsv(a)
    g = np.clip((hi - h) / (hi - lo), 0, 1)
    g = np.maximum(g, np.clip((h - red_lo) / (red_hi - red_lo), 0, 1))
    return (g * np.clip(s_ / 0.08, 0, 1)).astype(np.float32)  


_M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]], np.float32)  
_Mi = np.linalg.inv(_M).astype(np.float32)                                                                  
_WP = np.array([0.95047, 1.0, 1.08883], np.float32)                                                         


def rgb2lab(a):
    c = np.where(a <= 0.04045, a / 12.92, ((np.clip(a, 0, 1) + 0.055) / 1.055) ** 2.4)
    xyz = c @ _M.T / _WP
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1).astype(np.float32)


def lab2rgb(l):
    fy = (l[..., 0] + 16) / 116; fx = fy + l[..., 1] / 500; fz = fy - l[..., 2] / 200
    f = np.stack([fx, fy, fz], -1)
    xyz = np.where(f > 0.206893, f ** 3, (f - 16 / 116) / 7.787) * _WP
    c = xyz @ _Mi.T
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, 12.92 * c, 1.055 * np.power(c, 1 / 2.4) - 0.055).astype(np.float32)


def band_energy(L, lo, hi, win):
    b = gaussian_filter(L, lo) - gaussian_filter(L, hi)
    return np.sqrt(gaussian_filter(b * b, win))


def _components(mask, keep_fn):
    from scipy.ndimage import find_objects
    lab_, n = label(mask)
    out = np.zeros(mask.shape, bool)
    if not n:
        return out
    sizes = np.bincount(lab_.ravel()); sl = find_objects(lab_)
    for i in range(1, n + 1):
        if sl[i - 1] is not None and keep_fn(i, lab_, sl[i - 1], sizes[i]):
            out[lab_ == i] = True
    return out


def hardware_islands(mixlf, Q, k=2.2, floor=0.02, src_smooth=0.03, min_px=30, max_px=15000, ring=24, ring_smooth=0.85, grow=4, feather=2.5, cmap=None, rel_t=0.08, edge_t=None, edge_de=35.0, e01_t=0.0065):
    """New mid-scale structure (1-6 px band energy > k x source + floor) where the source surface is smooth: invented badges,
    emblems, indicator lights, zips on plain surfaces. Render-dependent; returns a [0,1] revert-to-init weight."""
    Er, Es = band_energy(luma(mixlf), 1.0, 6.0, 4.0), band_energy(luma(Q), 1.0, 6.0, 4.0)
    Ys = gaussian_filter(luma(Q), 8.0)
    rel = gaussian_filter(Es, 16.0) / (Ys + 0.05)  
    Lq_ = luma(Q); E01 = np.sqrt(gaussian_filter((Lq_ - gaussian_filter(Lq_, 0.8)) ** 2, 4.0))
    
    ns = (Er > k * Es + floor) & (gaussian_filter(Es, 8.0) < src_smooth) & (rel < rel_t) & (gaussian_filter(E01, 6.0) < e01_t)
    if cmap is not None:
        ns &= cmap < 0.3  
    H, W = ns.shape

    def keep(i, lab_, s, size):
        if not (min_px <= size <= max_px):
            return False
        ys, xs = s
        y0, y1 = max(0, ys.start - ring - 2), min(H, ys.stop + ring + 2); x0, x1 = max(0, xs.start - ring - 2), min(W, xs.stop + ring + 2)
        blob = lab_[y0:y1, x0:x1] == i
        rr = binary_dilation(blob, iterations=ring) & ~binary_dilation(blob, iterations=3)
        
        return rr.sum() > 30 and float((~nsd[y0:y1, x0:x1][rr]).mean()) >= ring_smooth
    nsd = binary_dilation(ns, iterations=2)
    
    lq = rgb2lab(gaussian_filter(Q, (1, 1, 0)))
    crng = np.maximum(*[maximum_filter(lq[..., ch], 11) - minimum_filter(lq[..., ch], 11) for ch in (1, 2)])
    gy, gx = np.gradient(gaussian_filter(luma(Q), 1.0)); gm = np.hypot(gx, gy)
    strong = binary_dilation((crng >= edge_de) | ((gm >= edge_t) if edge_t is not None else False), iterations=6)
    keep0 = keep
    keep = lambda i, lab_, s_, size: keep0(i, lab_, s_, size) and not strong[s_][lab_[s_] == i].any()
    m = _components(nsd, keep)
    w = binary_dilation(m, iterations=grow).astype(np.float32)
    return np.clip(gaussian_filter(w, feather) * 1.5, 0, 1)


def litter_islands(Q, cmap, G, tex_t=0.035, ring=30, ring_mat=0.35, grow=6, feather=2.5, dab_min=8.0):
    """Dry litter on a flat material surface, from the SOURCE only (can live in the PRE map node): textured, tan/brown
    (hue 10-55 deg, sat .12-.6) blobs whose surroundings are timber-like material (material_mask). Returns [0,1] weight."""
    Es = band_energy(luma(Q), 1.0, 6.0, 4.0)
    a = gaussian_filter(Q, (1, 1, 0)); mx, mn = a.max(-1), a.min(-1); d = mx - mn; sat = d / np.maximum(mx, 1e-4)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    hue = np.where(mx == r, (60 * (g - b) / np.maximum(d, 1e-6)) % 360, np.where(mx == g, 60 * (b - r) / np.maximum(d, 1e-6) + 120, 60 * (r - g) / np.maximum(d, 1e-6) + 240))
    dry = (hue >= 10) & (hue <= 55) & (sat >= 0.12) & (sat <= 0.6)
    seed = binary_dilation((Es > tex_t) & dry, iterations=3)
    M, _, _, _ = material_mask(Q, cmap, G)
    H, W = seed.shape
    lq = rgb2lab(a)

    def keep(i, lab_, s, size):
        ys, xs = s
        y0, y1 = max(0, ys.start - ring - 2), min(H, ys.stop + ring + 2); x0, x1 = max(0, xs.start - ring - 2), min(W, xs.stop + ring + 2)
        blob = lab_[y0:y1, x0:x1] == i
        rr = binary_dilation(blob, iterations=ring) & ~blob
        if not (size >= 40 and rr.sum() > 30 and float((M[y0:y1, x0:x1][rr] > 0.5).mean()) >= ring_mat):
            return False
        
        ab = lq[y0:y1, x0:x1, 1:]
        return float(np.linalg.norm(ab[blob].mean(0) - ab[rr].mean(0))) >= dab_min
    m = _components(seed, keep)
    w = binary_dilation(m, iterations=grow).astype(np.float32)
    return np.clip(gaussian_filter(w, feather) * 1.5, 0, 1)


def structure(Lq, gs=1.0, rs=6.0):
    gy, gx = np.gradient(gaussian_filter(Lq, gs))
    jxx, jyy, jxy = gaussian_filter(gx * gx, rs), gaussian_filter(gy * gy, rs), gaussian_filter(gx * gy, rs)
    tr = jxx + jyy; disc = np.sqrt(np.maximum((jxx - jyy) ** 2 / 4 + jxy ** 2, 0))
    l1, l2 = tr / 2 + disc, np.maximum(tr / 2 - disc, 0)
    theta = 0.5 * np.arctan2(2 * jxy, jxx - jyy)  
    coh = ((l1 - l2) / (l1 + l2 + 1e-12)) ** 2
    return theta, coh, np.sqrt(l1 + l2)


def material_mask(Q, cmap, G):
    Lq = luma(Q)
    th, coh, E = structure(Lq)
    
    a = Q; mx, mn = a.max(-1), a.min(-1); sat = (mx - mn) / np.maximum(mx, 1e-4)
    gy, gx = np.gradient(gaussian_filter(Lq, 1.0)); gm = np.hypot(gx, gy)
    edges = binary_dilation(gm >= G['edge_p985'], iterations=4)
    m = np.clip((coh - 0.35) / 0.25, 0, 1) * np.clip((0.045 - E) / 0.02, 0, 1) * np.clip((0.3 - cmap) / 0.2, 0, 1) * np.clip((0.28 - sat) / 0.1, 0, 1)
    m = m * (~edges)
    from scipy.ndimage import binary_opening
    m = m * np.clip((0.88 - Lq) / 0.1, 0, 1)  
    big = binary_opening(m > 0.5, iterations=40)  
    
    
    lab_, n = label(big)
    for i in range(1, n + 1):
        r_ = lab_ == i
        if np.median(coh[r_]) > 0.88:
            big[r_] = False
    m = m * binary_dilation(big, iterations=40)
    return gaussian_filter(m.astype(np.float32), 3.0), th, coh, E


def lf_mul(mix, ref, robust=0.06, sigma=32.0):
    """Robust low-frequency transfer as a per-channel GAIN in linear light (illuminant-like): the same correction field as
    lowfreq_transfer(robust) but multiplicative, so a dark object on a tinted surface is not given the surface's absolute tint."""
    x = torch.from_numpy(mix).permute(2, 0, 1)[None]; r = torch.from_numpy(ref).permute(2, 0, 1)[None]
    lin = lambda t: torch.where(t <= 0.04045, t / 12.92, ((t.clamp(0, 1) + 0.055) / 1.055) ** 2.4)
    xl, rl = lin(x), lin(r)
    B, C, H, W = x.shape
    bl = lambda t: _blur(t.reshape(-1, 1, H, W), sigma).reshape(t.shape)
    d = r - x
    wgt = torch.exp(-(_blur(d.abs().mean(1, keepdim=True), 4.0) / robust) ** 2) if robust else torch.ones_like(x[:, :1])
    den = bl(wgt.expand(B, C, H, W).contiguous()).clamp(min=1e-3)
    gain = ((bl(wgt * rl) / den + 2e-3) / (bl(wgt * xl) / den + 2e-3)).clamp(0.5, 2.0)
    ol = (xl * gain).clamp(0, 1)
    o = torch.where(ol <= 0.0031308, 12.92 * ol, 1.055 * ol ** (1 / 2.4) - 0.055)
    return o[0].permute(1, 2, 0).numpy().astype(np.float32)


def chroma_hc2(O, Q, hue_deg=10.0, rlo=0.9, rhi=1.18, rpad=2.5, neutral=5.0, s=2.0, warm=None):
    """fixes.chroma_hc plus an optional warm-hue tightening: warm=(h0, h1, rhi_w, s_w, rlo_w) -> on chromatic source pixels whose Lab hue
    lies in [h0, h1] deg the chroma ceiling is rhi_w x source (+pad) with statistics at sigma s_w (strand scale) and floor rlo_w."""
    def clamp(O, Q, rlo, rhi, s):
        lo_, lq = rgb2lab(O), rgb2lab(Q)
        ob = gaussian_filter(lo_[..., 1:], (s, s, 0)); sb = gaussian_filter(lq[..., 1:], (s, s, 0))
        cs = np.sqrt((sb ** 2).sum(-1)); co = np.sqrt((ob ** 2).sum(-1))
        hs, ho = np.arctan2(sb[..., 1], sb[..., 0]), np.arctan2(ob[..., 1], ob[..., 0])
        dh = (ho - hs + np.pi) % (2 * np.pi) - np.pi
        h2 = hs + np.clip(dh, -np.radians(hue_deg), np.radians(hue_deg))
        r2 = np.clip(co, np.maximum(rlo * cs - rpad, 0), rhi * cs + rpad)
        t_chrom = np.stack([r2 * np.cos(h2), r2 * np.sin(h2)], -1)
        d = ob - sb; mag = np.sqrt((d ** 2).sum(-1, keepdims=True)) + 1e-6
        t_neut = sb + d * (neutral * np.tanh(mag / neutral) / mag)
        wch = np.clip((cs - 4.0) / 4.0, 0, 1)[..., None]
        target = wch * t_chrom + (1 - wch) * t_neut
        out = lo_.copy(); out[..., 1:] = lo_[..., 1:] + (target - ob)
        return out, np.degrees(hs) % 360, cs
    out, hdeg, cs = clamp(O, Q, rlo, rhi, s)
    if warm:
        h0, h1, rhi_w, s_w, rlo_w = warm
        out_w, _, _ = clamp(O, Q, rlo_w, rhi_w, s_w)
        ww = (np.clip((hdeg - h0) / 8, 0, 1) * np.clip((h1 - hdeg) / 8, 0, 1) * np.clip((cs - 6) / 4, 0, 1))[..., None]
        out = ww * out_w + (1 - ww) * out
    rgb = lab2rgb(out); Y, Y2 = luma(O), luma(rgb)
    return np.clip(rgb * (Y / np.maximum(Y2, 1e-4))[..., None], 0, 1).astype(np.float32)


FINP = {'kappa': 0.12, 'b0': (1.6, 2.4), 'b0_flat': (0.9, 1.25)}  
WARM = (15, 110, 1.00, 1.0, 0.9)  


def v3g_map(pre_t, H, W, ss=(0.3, 0.6)):
    m = creativity_map(pre_t, lo=0.0, hi=1.0, coh_k=0.85, p_lo=0.25, p_hi=0.85, feather=12.0, abs_hi=0.035)
    u = torch.clamp((m - ss[0]) / (ss[1] - ss[0]), 0, 1); m = u * u * (3 - 2 * u)
    return torch.nn.functional.interpolate(m[None, None], size=(H, W), mode='bilinear', align_corners=False)[0, 0].numpy()


def lf_add(mix, ref, robust):
    return lowfreq_transfer(torch.from_numpy(mix)[None], torch.from_numpy(ref)[None], sigma=32.0, strength=1.0, robust=robust)[0].numpy()


def lf_hyb(mix, ref, robust=0.06, y0=0.10, y1=0.30):
    """Lead: robust LF as a gain in linear light only in dark pixels (where the additive offset paints a tint onto crushed darks:
    S2 navy leaves), additive elsewhere (the additive form keeps v3g's saturation on mid-tones: S2/S4 saturation, S3 hair)."""
    a = lf_add(mix, ref, robust); m = lf_mul(mix, ref, robust)
    w = np.clip((y1 - luma(mix)) / (y1 - y0), 0, 1)[..., None]
    return (w * m + (1 - w) * a).astype(np.float32)


def colour_filter(w, mixlf, Q, dab_p90=10.0):
    """Lead: keep a hardware island only if it is a COLOUR novelty (p90 of Lab chroma distance render vs PRE, sigma 1, >= dab_p90):
    a red/silver badge on a green fender, rust flecks on grey concrete, an orange glow in a white downlight. Same-hue enrichment
    of soft source detail (hair tips over a wall, sheer-curtain texture) is not reverted."""
    from scipy.ndimage import labeled_comprehension
    sup = w > 0.02
    lab_, n = label(sup)
    if n == 0:
        return w
    a = rgb2lab(gaussian_filter(mixlf, (1, 1, 0)))[..., 1:]; b = rgb2lab(gaussian_filter(Q, (1, 1, 0)))[..., 1:]
    dab = np.sqrt(((a - b) ** 2).sum(-1)); del a, b
    core = np.where(w > 0.5, lab_, 0)
    idx = np.arange(1, n + 1)
    p90 = labeled_comprehension(dab, core, idx, lambda v: np.percentile(v, 90) if v.size else 0.0, float, 0.0)
    keep = np.zeros(n + 1, bool); keep[1:] = p90 >= dab_p90
    return (w * keep[lab_]).astype(np.float32)


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


def edge_profile_clamp_bands(Y2, Yref, f, band, halo, p=None, Yenv=None, smooth='pooled'):
    """edge_profile_clamp over full-width bands of `band` rows, each read with `halo` rows of real image above and below
    (cut at the image's edges); returns the joined core rows. With smooth='pooled' and halo >= edge_profile_clamp_reach(f)
    it equals the whole call, value for value (tests/engine/test_halo2_fix.py)."""
    Y2 = np.asarray(Y2, np.float32)
    Yref = np.asarray(Yref, np.float32)
    H = Y2.shape[0]
    out = np.empty_like(Y2)
    for y0 in range(0, H, int(band)):
        y1 = min(H, y0 + int(band))
        a, b = max(0, y0 - int(halo)), min(H, y1 + int(halo))
        r = edge_profile_clamp(Y2[a:b], Yref[a:b], f, p, None if Yenv is None else np.asarray(Yenv, np.float32)[a:b],
                               smooth=smooth, oy=a, H_full=H)
        out[y0:y1] = r[y0 - a:y1 - a]
    return out


def edge_profile_clamp(Y2, Yref, f, p=None, Yenv=None, smooth='g', oy=0, H_full=None):
    """The halo fix (v6, 20 Nov 2026): an overshoot at an edge of geometry is removed; the edge, its ramp and the texture
    beside it are kept.

    Y2: the finish's luma [H, W]; Yref: a NON-RINGING reference of the source at the same size (bilinear: every weight >= 0,
    so it never overshoots); f: output px per reference-content px (2 for a 2x pass; 4 for the second pass of 4x when the
    reference is the original input).
    - Where: within r + 1 px of edges of geometry (geometry_edges: strong, coherent, long), r = max(3, 1.5 f).
    - The envelope: the reference averaged along the edge tangent (_line_mean, sigma 2f px), its min / max within r px,
      shifted by the local tone offset of output against reference (measured away from the edges), widened by tol plus
      kstd x the standard error of a tangent mean of the local texture (measured away from the edges).
    - What is removed: a pixel's excess beyond the envelope, in the proportion that the excess is shared along the edge
      (the excess of the tangent mean of the output over the tangent mean of the pixels' excess): a rim, the same along the
      edge, goes whole; texture, whose mean along the edge stays inside the envelope, is left as rendered. The ramp lies
      inside the envelope and is never touched.
    - A valley (ridge) of the reference along the normal, a thin dark (light) line, keeps its drop (lift).
    Yenv (optional): a second non-ringing reference at the same size that gives the envelope, the tone offset and the
    thin-line test, while Yref still gives where the edges of geometry are and their direction (a later pass: the edges
    of the original, the envelope of the previous pass's own output).
    Returns float32 luma of the same shape; with no edge of geometry it is Y2 itself, bit for bit.
    smooth: 'g' (round 1: the tone offset and texture level through g()) | 'pooled' (round 2: through _gpool, whose grid is
    anchored to the whole image, so the clamp is exact in bands: edge_profile_clamp_bands). oy, H_full: with 'pooled', the
    first row of Y2 in the whole image and the whole image's rows (a band); every other step is local."""
    if smooth not in ('g', 'pooled'):
        raise ValueError(f"edge_profile_clamp: smooth must be 'g' or 'pooled' (got {smooth!r})")
    if smooth == 'g':
        blur = lambda x_, s_: g(x_, s_, 'nearest')
    else:
        blur = lambda x_, s_: _gpool(x_, s_, oy, H_full)
    p = {**DEHALO, **(p or {})}
    Y2 = np.asarray(Y2, np.float32)
    Yref = np.asarray(Yref, np.float32)
    Yenv = Yref if Yenv is None else np.asarray(Yenv, np.float32)
    f = float(max(f, 1.0))
    r = max(3, int(round(1.5 * f)))
    sig_t, off_sigma = 2.0 * f, 12.0 * f
    K = max(1, int(math.ceil(2.5 * sig_t)))
    theta, coh, gx, gy = _orient(Yref, max(1.0, 0.5 * f), max(2.0, f))
    e = geometry_edges(Yref, gx, gy, coh, f, p['c_edge'], p['coh_min'], p['len_min'] * f, coord64=smooth == 'pooled')
    del gx, gy, coh
    if not e.any():
        return Y2
    w = np.clip(gaussian_filter(binary_dilation(e, iterations=r + int(p['pad'])).astype(np.float32), 1.0) * 1.5, 0, 1)
    del e
    act = w > 0.01
    near = binary_dilation(act, iterations=K)                 # pixels the tangent means at active pixels read
    ys, xs = np.nonzero(binary_dilation(near, iterations=r))
    R = Yenv.copy()                                           # the reference averaged along the edge tangent
    R[ys, xs] = _line_mean(Yenv, ys, xs, theta[ys, xs], sig_t)
    del ys, xs
    lo, hi = minimum_filter(R, 2 * r + 1), maximum_filter(R, 2 * r + 1)
    # tone offset and texture level of the output against the reference, away from the edges (normalised convolution)
    far = (~binary_dilation(act, iterations=r + 2)).astype(np.float32)
    den = blur(far, off_sigma)
    off = np.where(den > 0.05, blur((Y2 - Yenv) * far, off_sigma) / np.maximum(den, 1e-6), 0.0).astype(np.float32)
    hp = Y2 - gaussian_filter(Y2, f)
    tex = np.sqrt(np.maximum(np.where(den > 0.05, blur(hp * hp * far, off_sigma) / np.maximum(den, 1e-6),
                                      blur(hp * hp, off_sigma)), 0)).astype(np.float32)
    del hp, far, den
    tol = (p['tol'] + p['kstd'] * tex / math.sqrt(_line_neff(sig_t))).astype(np.float32)
    del tex
    lo_, hi_ = lo + off - tol, hi + off + tol
    del lo, hi, off, tol
    ex = np.where(near, Y2 - np.clip(Y2, lo_, hi_), 0).astype(np.float32)   # each pixel's own excess (signed)
    ya, xa = np.nonzero(act)
    tha = theta[ya, xa]
    del theta
    P = _line_mean(Y2, ya, xa, tha, sig_t)
    Mp = _line_mean(np.maximum(ex, 0), ya, xa, tha, sig_t)
    Mm = _line_mean(np.minimum(ex, 0), ya, xa, tha, sig_t)
    E = P - np.clip(P, lo_[ya, xa], hi_[ya, xa])              # the excess of the mean profile
    cp = np.clip(np.maximum(E, 0) / np.maximum(Mp, 1e-6), 0, 1)
    cm = np.clip(np.minimum(E, 0) / np.minimum(Mm, -1e-6), 0, 1)
    exa = ex[ya, xa]
    del ex, lo_, hi_, P, Mp, Mm, E
    from scipy.ndimage import map_coordinates
    sx, cy = np.sin(tha).astype(np.float32), np.cos(tha).astype(np.float32)
    ct = np.float64 if smooth == 'pooled' else np.float32
    yaf, xaf = ya.astype(ct), xa.astype(ct)
    Rm = map_coordinates(R, [yaf - r * sx, xaf - r * cy], order=1, mode='nearest', prefilter=False)   # normal (y, x) = (sin, cos)
    Rp = map_coordinates(R, [yaf + r * sx, xaf + r * cy], order=1, mode='nearest', prefilter=False)
    Rc = R[ya, xa]
    ld = float(p['line_d'])
    keep_lift = np.clip(1 - (Rc - np.maximum(Rm, Rp)) / ld, 0, 1)      # 0 on a light line of the reference
    keep_drop = np.clip(1 - (np.minimum(Rm, Rp) - Rc) / ld, 0, 1)      # 0 on a dark line of the reference
    wa = w[ya, xa]
    out = Y2.copy()
    out[ya, xa] = Y2[ya, xa] - wa * (keep_lift * cp * np.maximum(exa, 0) + keep_drop * cm * np.minimum(exa, 0))
    return out


def post(D, Y, Yq, Y2, zone, Q, ar='plain', kb=0.75, kb_pre=False, chroma='mul', ar_min=200, dehalo=None, dehalo_smooth='g',
         dctx=None):
    """dehalo: None (5.0.1) or (Yref, f): edge_profile_clamp after keep_blacks (so the darks it restores are held too).
    dehalo_smooth: the clamp's smooth fields ('g' round 1, 'pooled' round 2), or 'r3' (round 2 revision: edge_profile_clamp3
    with dehalo = (Yref, f, source luma, source RGB, guard); its luma change is left in dctx['dY'] for the final clamp)."""
    Y2 = Y2.copy()
    if ar:
        r, tol = 3, 0.04
        az = binary_dilation(zone, iterations=r + 2); w = gaussian_filter(az.astype(np.float32), 1.5)
        lo, hi = minimum_filter(Yq, 2 * r + 1) - tol, maximum_filter(Yq, 2 * r + 1) + tol
        if ar in ('agree', 'agree2'):  
            ys_, qs_ = gaussian_filter(Y2, 1.5), gaussian_filter(Yq, 1.5)
            cr = Y2 > 0.5 * (maximum_filter(ys_, 15) + minimum_filter(ys_, 15))
            cq = Yq > 0.5 * (maximum_filter(qs_, 15) + minimum_filter(qs_, 15))
            dis = cr != cq
            if ar == 'agree2':  
                lab_, n = label(dis)  
                big = np.bincount(lab_.ravel()) >= ar_min; big[0] = False
                dis = big[lab_]; del lab_
            w = w * gaussian_filter((~dis).astype(np.float32), 1.0)
        Y2 = Y2 + w * (np.clip(Y2, lo, hi) - Y2)
    if kb:
        wd = np.clip((0.22 - Y) / 0.17, 0, 1)
        if kb_pre == 'narrow':  
            wd = wd * np.maximum(np.clip((0.22 - gaussian_filter(Yq, 2.0)) / 0.17, 0, 1), np.clip((Y - 0.06) / 0.04, 0, 1))
        elif kb_pre:
            wd = wd * np.clip((0.22 - gaussian_filter(Yq, 2.0)) / 0.17, 0, 1)
        Y2 = Y2 - kb * wd * np.maximum(Y2 - Y, 0)
    if dehalo is not None:
        if dehalo_smooth == 'r3':
            Y2b = Y2
            Y2 = edge_profile_clamp3(Y2, dehalo[0], dehalo[1], Ysrc=dehalo[2], guard=dehalo[4])
            if dctx is not None:
                dctx['dY'] = (Y2 - Y2b).astype(np.float32)
            del Y2b
        else:
            Y2 = edge_profile_clamp(Y2, dehalo[0], dehalo[1], Yenv=dehalo[2] if len(dehalo) > 2 else None, smooth=dehalo_smooth)
        if _dumping():
            _dump('f08a-dehalo', np.clip(D + (Y2 - Y)[..., None], 0, 1))
    return fin_post(D, Y, Yq, Y2, zone, antiring=None, keep_blacks=0.0, chroma=chroma, Q=Q, src=(2.0, 0.9, 1.05))


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
    w = np.clip(gaussian_filter(binary_dilation(e, iterations=r + int(p['pad'])).astype(np.float32), 1.0) * 1.5, 0, 1)
    del e
    act = w > 0.01
    near = binary_dilation(act, iterations=K)
    return dict(f=f, r=r, sig_t=sig_t, off_sigma=12.0 * f, theta=theta, w=w, act=act, near=near)


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
    _dump('f11-dehalo-final', res)
    return res


def final_clamp3_bands(out, ref, band, halo, dYp=None):
    """_final_clamp3 over full-width bands (ref[0] and dYp sliced, the source arrays whole); with halo >=
    edge_profile_clamp3_reach(f) it equals the whole call, value for value."""
    out = np.asarray(out, np.float32)
    H = out.shape[0]
    res = np.empty_like(out)
    for y0 in range(0, H, int(band)):
        y1 = min(H, y0 + int(band))
        a, b = max(0, y0 - int(halo)), min(H, y1 + int(halo))
        r = (np.asarray(ref[0])[a:b],) + tuple(ref[1:])
        res[y0:y1] = _final_clamp3(out[a:b], r, None if dYp is None else dYp[a:b], oy=a, H_full=H)[y0 - a:y1 - a]
    return res


RELEASE_FEATHER = 1.5


def protect_gate(protect, H, W, dil=12, feather=4.0, release=None):
    """protect: [h, w] object union at PRE resolution, binarised at .5 -> dilated dil px, Gaussian sigma feather, bilinear to
    (H, W), clipped to [0, 1]. v4build: union of the MK2 term masks (PNG > 127) -> the same three steps.
    release (Creative Upscaler app, 5 Nov): optional [h, w] mask at PRE resolution of areas that stay creative even where a protect
    term covers them (people and planting inside an architecture mask). Binarised at .5, not dilated, Gaussian sigma
    RELEASE_FEATHER; the gate becomes P * (1 - R) after the protect feather, so the protect dilation never grows back into them.
    release=None leaves the v4b gate bit for bit."""
    u = np.asarray(protect, dtype=np.float32) > 0.5
    if dil > 0:
        u = binary_dilation(u, iterations=int(dil))
    p = gaussian_filter(u.astype(np.float32), feather)
    if release is not None:
        r = np.asarray(release, dtype=np.float32)
        if r.shape != p.shape:
            raise ValueError(f'protect_gate: release {r.shape} must match protect {p.shape}')
        p = p * (1 - gaussian_filter((r > 0.5).astype(np.float32), RELEASE_FEATHER))
    return torch.nn.functional.interpolate(torch.from_numpy(p)[None, None], size=(H, W), mode='bilinear', align_corners=False)[0, 0].numpy().clip(0, 1)


def to_u8(out):
    """The offline stack's 8-bit write (reports/v4-analysis/lead/v4stack.py::main)."""
    return (np.clip(out, 0, 1) * 255 + .5).astype(np.uint8)


def quantize_8bit(a):
    """ComfyUI SaveImage -> PNG -> LoadImage round trip (floor of 255 x, clipped; /255 in float32). Exact no-op on 8-bit-derived
    images (255 * float32(k / 255) == k for every k), so it only matters for unsaved float renders."""
    return np.clip(255. * np.asarray(a, dtype=np.float32), 0, 255).astype(np.uint8).astype(np.float32) / 255.0


def _f32(a, name):
    a = np.asarray(a, dtype=np.float32)
    if a.ndim != 3 or a.shape[-1] < 3:
        raise ValueError(f'v4_finish: {name} must be HxWx3, got {a.shape}')
    if a.shape[-1] > 3:
        a = a[..., :3]
    return np.ascontiguousarray(a)


def agreement(O, Q, s=4.0):
    a = luma(O); b = luma(Q)
    ha = gaussian_filter(a, 1.0) - gaussian_filter(a, 6.0); hb = gaussian_filter(b, 1.0) - gaussian_filter(b, 6.0)
    num = gaussian_filter(ha * hb, s)
    den = np.sqrt(gaussian_filter(ha * ha, s) * gaussian_filter(hb * hb, s)) + 1e-8
    return num / den


def chroma_mm(O, Q, hue_deg=10.0, rlo=0.9, rhi=1.18, rpad=2.5, neutral=4.0, s=2.0, warm=(15, 110, 1.00, 1.0, 0.9),
              c_lo=0.2, c_hi=0.5, q_lo=0.35, q_hi=0.6, h_lo=30.0, h_hi=60.0, cyan=(165.0, 270.0, 30.0, 0.0), neut=(8.0, 14.0),
              hsim=(3.0, 6.0)):
    
    
    """V4finish implementation."""


    lo_, lq = rgb2lab(O), rgb2lab(Q)
    wa = np.clip((agreement(O, Q) - c_lo) / (c_hi - c_lo), 0, 1)

    def target(rlo, rhi, s):
        ob = gaussian_filter(lo_[..., 1:], (s, s, 0)); sb = gaussian_filter(lq[..., 1:], (s, s, 0))
        cs = np.sqrt((sb ** 2).sum(-1)); co = np.sqrt((ob ** 2).sum(-1))
        hs, ho = np.arctan2(sb[..., 1], sb[..., 0]), np.arctan2(ob[..., 1], ob[..., 0])
        dh = (ho - hs + np.pi) % (2 * np.pi) - np.pi
        wf = np.maximum(wa, np.clip((co / np.maximum(cs, 1e-3) - q_lo) / (q_hi - q_lo), 0, 1))
        if hsim:  
            wf = np.maximum(wf, np.clip((np.radians(h_hi) - np.abs(dh)) / np.radians(h_hi - h_lo), 0, 1) * np.clip((co - hsim[0]) / (hsim[1] - hsim[0]), 0, 1))
        wh = np.maximum(wa, np.clip((np.radians(h_hi) - np.abs(dh)) / np.radians(h_hi - h_lo), 0, 1))
        h2 = ho + wh * (np.clip(dh, -np.radians(hue_deg), np.radians(hue_deg)) - dh)
        floor = wf * np.maximum(rlo * cs - rpad, 0)
        r2 = np.clip(co, floor, rhi * cs + rpad)
        if cyan:
            hod = np.degrees(ho) % 360; c0, c1, dmax, kc = cyan
            wc = np.clip((hod - c0) / 10, 0, 1) * np.clip((c1 - hod) / 10, 0, 1) * np.clip((np.degrees(np.abs(dh)) - dmax) / 15, 0, 1) * (1 - wa)
            r2 = r2 + wc * (np.minimum(r2, neutral + kc * cs) - r2)
        t_chrom = np.stack([r2 * np.cos(h2), r2 * np.sin(h2)], -1)
        d = ob - sb; mag = np.sqrt((d ** 2).sum(-1, keepdims=True)) + 1e-6
        t_neut = sb + d * (neutral * np.tanh(mag / neutral) / mag)
        wch = np.clip((cs - neut[0]) / (neut[1] - neut[0]), 0, 1)[..., None]
        return wch * t_chrom + (1 - wch) * t_neut, ob, np.degrees(hs) % 360, cs
    t, ob, hdeg, cs = target(rlo, rhi, s)
    out = lo_.copy(); out[..., 1:] = lo_[..., 1:] + (t - ob)
    if warm:
        h0, h1, rhi_w, s_w, rlo_w = warm
        tw, obw, _, _ = target(rlo_w, rhi_w, s_w)
        ww = (np.clip((hdeg - h0) / 8, 0, 1) * np.clip((h1 - hdeg) / 8, 0, 1) * np.clip((cs - 6) / 4, 0, 1))[..., None]
        outw = lo_.copy(); outw[..., 1:] = lo_[..., 1:] + (tw - obw)
        out = ww * outw + (1 - ww) * out
    rgb = lab2rgb(out); Y, Y2 = luma(O), luma(rgb)
    return np.clip(rgb * (Y / np.maximum(Y2, 1e-4))[..., None], 0, 1).astype(np.float32)


def lf_hyb_min(mix, ref, robust=0.06, y0=0.10, y1=0.30):
    """Copied from reports/v4-analysis/lead/r2/r2build.py lf_hyb_min (lead plan revision 2; not imported because importing r2build
    re-points v4stack.OUT). On dark pixels take whichever of the additive and the gain LF result has lower chroma: the gain fixes the
    additive navy tint on crushed leaves (S2), the additive form avoids the gain's saturation lift on dark warm wood (S4 chair leg)."""
    a = lf_add(mix, ref, robust); m = lf_mul(mix, ref, robust)
    ca, cm = a.max(-1) - a.min(-1), m.max(-1) - m.min(-1)
    sel = (1 / (1 + np.exp(-(ca - cm) / 0.01)))[..., None]          
    dark = sel * m + (1 - sel) * a
    w = np.clip((y1 - luma(mix)) / (y1 - y0), 0, 1)[..., None]
    return (w * dark + (1 - w) * a).astype(np.float32)


def G(x, s):
    return gaussian_filter(x, (s, s, 0)) if x.ndim == 3 else gaussian_filter(x, s)


def agreement_r2(O, Q, s1=1.0, s2=4.0, sw=3.0, t0=0.2, t1=0.6, e_flat=0.004):
    Yo, Yq = luma(O), luma(Q)
    bo = gaussian_filter(Yo, s1) - gaussian_filter(Yo, s2); bq = gaussian_filter(Yq, s1) - gaussian_filter(Yq, s2)
    num = gaussian_filter(bo * bq, sw); eo = gaussian_filter(bo * bo, sw); eq = gaussian_filter(bq * bq, sw)
    ncc = num / np.sqrt(eo * eq + 1e-12)
    w = np.clip((ncc - t0) / (t1 - t0), 0, 1)
    w = np.where(np.sqrt(np.maximum(eo, eq)) < e_flat, 1.0, w)
    return gaussian_filter(w.astype(np.float32), 1.0)


def clamp_r2(O, Q, mode='agree', hue_deg=10.0, rlo=0.9, rhi=1.18, rpad=2.5, neutral=5.0, s=2.0, warm=(15, 110, 1.00, 1.0, 0.9),
             h0=25.0, h1=60.0, keep=0.3, neutral_mis=8.0):
    lo_, lq = rgb2lab(O), rgb2lab(Q)
    m4 = mode in ('agree4', 'agree5')
    m5 = mode == 'agree5'
    if m4:
        mode = 'agree3'
    wa = agreement_r2(O, Q)[..., None] if mode in ('agree', 'agree2', 'agree3') else None

    def target(s_, rlo_, rhi_):
        ob = G(lo_[..., 1:], s_); sb = G(lq[..., 1:], s_)
        cs = np.sqrt((sb ** 2).sum(-1)); co = np.sqrt((ob ** 2).sum(-1))
        hs, ho = np.arctan2(sb[..., 1], sb[..., 0]), np.arctan2(ob[..., 1], ob[..., 0])
        dh = (ho - hs + np.pi) % (2 * np.pi) - np.pi
        d = ob - sb; mag = np.sqrt((d ** 2).sum(-1, keepdims=True)) + 1e-6
        wch = np.clip((cs - 4.0) / 4.0, 0, 1)[..., None]
        ceil = rhi_ * cs + rpad
        if mode == 'ceil':
            r2 = np.minimum(co, ceil); t_ch = np.stack([r2 * np.cos(ho), r2 * np.sin(ho)], -1)
            t_ne = sb + d * (neutral * np.tanh(mag / neutral) / mag)
            return wch * t_ch + (1 - wch) * t_ne, ob, hs, cs
        h2 = hs + np.clip(dh, -np.radians(hue_deg), np.radians(hue_deg))
        r2 = np.clip(co, np.maximum(rlo_ * cs - rpad, 0), ceil)
        t_ag = wch * np.stack([r2 * np.cos(h2), r2 * np.sin(h2)], -1) + (1 - wch) * (sb + d * (neutral * np.tanh(mag / neutral) / mag))
        if wa is None:
            return t_ag, ob, hs, cs
        if mode in ('agree2', 'agree3'):  
            f = np.clip((np.degrees(np.abs(dh)) - 60.0) / 60.0, 0, 1)        
            fl = np.where(co >= 4.0, np.minimum(np.maximum(rlo_ * cs - rpad, 0), 1.6 * co), co)
            rm = np.minimum(np.maximum(co, fl), ceil * (1 - 0.6 * f))
            if mode == 'agree3':  
                wfam = np.clip((45.0 - np.degrees(np.abs(dh))) / 15.0, 0, 1)[..., None]
                t_mis = wch * np.stack([rm * np.cos(ho), rm * np.sin(ho)], -1) + (1 - wch) * (sb + d * (neutral_mis * np.tanh(mag / neutral_mis) / mag))
                t_mis = wfam * t_ag + (1 - wfam) * t_mis
                return wa * t_ag + (1 - wa) * t_mis, ob, hs, cs
        else:
            f = np.clip((np.degrees(np.abs(dh)) - h0) / (h1 - h0), 0, 1)
            rm = np.minimum(co, ceil * (1 - (1 - keep) * f))
        t_mis = wch * np.stack([rm * np.cos(ho), rm * np.sin(ho)], -1) + (1 - wch) * (sb + d * (neutral_mis * np.tanh(mag / neutral_mis) / mag))
        return wa * t_ag + (1 - wa) * t_mis, ob, hs, cs

    t, ob, hs, cs = target(s, rlo, rhi)
    out = lo_.copy(); out[..., 1:] = lo_[..., 1:] + (t - ob)
    if warm:
        h0w, h1w, rhiw, sw, rlow = warm
        tw, obw, _, _ = target(sw, rlow, rhiw)
        hdeg = np.degrees(hs) % 360
        ww = (np.clip((hdeg - h0w) / 8, 0, 1) * np.clip((h1w - hdeg) / 8, 0, 1) * np.clip((cs - 6) / 4, 0, 1))[..., None]
        outw = lo_.copy(); outw[..., 1:] = lo_[..., 1:] + (tw - obw)
        out = ww * outw + (1 - ww) * out
    if m5:  
        co = np.sqrt((out[..., 1:] ** 2).sum(-1)); hh = np.degrees(np.arctan2(out[..., 2], out[..., 1])) % 360
        hq = np.degrees(hs) % 360; dq = np.abs(hh - hq); dq = np.minimum(dq, 360 - dq)
        hw = np.clip((hh - 165) / 10, 0, 1) * np.clip((270 - hh) / 10, 0, 1) * np.clip((dq - 30) / 15, 0, 1)
        bw = (1 - wa[..., 0]) * hw
        fac = np.where(co > 3, 3 / np.maximum(co, 1e-6), 1.0)
        out[..., 1:] = out[..., 1:] * (1 - bw * (1 - fac))[..., None]
    elif m4:  
        co = np.sqrt((out[..., 1:] ** 2).sum(-1)); hh = np.degrees(np.arctan2(out[..., 2], out[..., 1])) % 360
        hw = np.clip((hh - 160) / 15, 0, 1) * np.clip((290 - hh) / 15, 0, 1)
        bw = (1 - wa[..., 0]) * np.clip((out[..., 0] - 60) / 10, 0, 1) * hw
        fac = np.where(co > 6, np.maximum(6 / np.maximum(co, 1e-6), 0.4), 1.0)
        out[..., 1:] = out[..., 1:] * (1 - bw * (1 - fac))[..., None]
    rgb = lab2rgb(out); Y, Y2 = luma(O), luma(rgb)
    return np.clip(rgb * (Y / np.maximum(Y2, 1e-4))[..., None], 0, 1).astype(np.float32)


def sky_mask(Q):
    """PRE-derived open sky (lead): bright, flat at 1-8 px, low saturation or blue hue, connected to the top border.
    Content-adaptive (no scene switch); interiors without sky return an empty mask."""
    Yq = luma(Q)
    e = np.sqrt(gaussian_filter((Yq - gaussian_filter(Yq, 1.0)) ** 2 + (gaussian_filter(Yq, 1.0) - gaussian_filter(Yq, 4.0)) ** 2, 3.0))
    br = Q[..., 2] - Q[..., 0]
    cand = (Yq > 0.55) & (e < 0.012) & (br > -0.01)
    lab_, n = label(cand)
    if n == 0:
        return np.zeros(Yq.shape, np.float32)
    top = np.unique(lab_[:8, :]); top = top[top > 0]
    sizes = np.bincount(lab_.ravel())
    keep = np.zeros(n + 1, bool)
    for k in top:  
        if sizes[k] >= 2000 and float(np.median(br[lab_ == k])) >= 0.012:
            keep[k] = True
    sky = keep[lab_]
    
    if sky.any():
        s_level = float(np.median(Yq[sky]))
        gaps = cand & ~sky & (Yq > s_level - 0.10) & (br > 0.005)
        lab2, n2 = label(gaps); sz2 = np.bincount(lab2.ravel())
        okg = (sz2 >= 40) & (sz2 <= 200000); okg[0] = False
        sky = sky | okg[lab2]
    sky = binary_erosion(sky, iterations=2)
    return np.clip(gaussian_filter(sky.astype(np.float32), 1.5) * 1.3, 0, 1)


def sky_gaps(Q, sky, near_px=512, dil=3, zmode='constant'):
    """'gaps' gate: v4stack.sky_mask only keeps FLAT gaps, so most canopy sky gaps (textured at 1-8 px next to leaves) are missed.
    Here: PRE pixels as bright as the open sky (G1 luma > open-sky median - .12) and not warm (B >= R), within near_px of the open
    sky, dilated dil px so the gate reaches the rims on the sky side of moved leaves. Interiors (no open sky) -> empty."""
    from scipy.ndimage import distance_transform_edt, zoom
    s0 = sky > 0.5
    if not s0.any():
        return np.zeros(sky.shape, np.float32)
    Yq = luma(Q); lvl = float(np.median(Yq[s0]))
    cand = (gaussian_filter(Yq, 1.0) > lvl - 0.12) & (Q[..., 2] - Q[..., 0] >= 0.0)
    f = 4; d = distance_transform_edt(~s0[::f, ::f]) * f
    near = zoom(d, (sky.shape[0] / d.shape[0], sky.shape[1] / d.shape[1]), order=0, mode=zmode)[:sky.shape[0], :sky.shape[1]] <= near_px
    g = binary_dilation(cand & near, iterations=dil)
    return np.clip(gaussian_filter(g.astype(np.float32), 1.0) * 1.3, 0, 1)


def veg_rim(Q, near_px=16, dil=2):
    """'vegrim' gate (generic, not sky-specific): bright PRE background (G1 luma > .5) within near_px of dark PRE foliage
    (luma < .35, hue 50-190 deg, sat >= .15). Covers canopy gaps against sky AND leaves against curtains/walls; empty where the
    source has no vegetation silhouettes."""
    Yq = luma(Q); mx, mn = Q.max(-1), Q.min(-1); s = (mx - mn) / np.maximum(mx, 1e-6)
    r, g, b = Q[..., 0], Q[..., 1], Q[..., 2]; d = np.maximum(mx - mn, 1e-6)
    h = np.where(mx == r, (60 * (g - b) / d) % 360, np.where(mx == g, 60 * (b - r) / d + 120, 60 * (r - g) / d + 240))
    veg = (Yq < 0.35) & (h >= 50) & (h <= 190) & (s >= 0.15)
    near = binary_dilation(veg, iterations=near_px)
    gg = binary_dilation(near & (gaussian_filter(Yq, 1.0) > 0.5) & ~veg, iterations=dil)
    return np.clip(gaussian_filter(gg.astype(np.float32), 1.0) * 1.3, 0, 1)


def csc_sky(O, Q, size=31, sig=12.0, tol=0.02, dil=4, mode='sky', rim=0, zmode='constant'):
    Y, Yq = luma(O), luma(Q)
    sky = sky_mask(Q)
    if mode == 'gaps':
        gate_s = sky_gaps(Q, sky, zmode=zmode)
    elif mode == 'vegrim':
        gate_s = veg_rim(Q)
    else:
        gate_s = np.clip(gaussian_filter(binary_dilation(sky > 0.5, iterations=dil).astype(np.float32), 1.5) * 1.3, 0, 1)
    qs = gaussian_filter(Yq, 1.5); qmx, qmn = maximum_filter(qs, size), minimum_filter(qs, size)
    qb = (qs > qmx - 0.2 * (qmx - qmn)).astype(np.float32)
    ref = gaussian_filter(Yq * qb, sig) / np.maximum(gaussian_filter(qb, sig), 1e-3)
    ys = gaussian_filter(Y, 1.5); ymx, ymn = maximum_filter(ys, size), minimum_filter(ys, size)
    rb = np.clip((Y - 0.5 * (ymx + ymn)) / np.maximum(0.1 * (ymx - ymn), 1e-3), 0, 1)
    gate = np.clip(((qmx - qmn) - 0.2) / 0.1, 0, 1) * gate_s
    if rim:  
        darkc = Y < 0.5 * (ymx + ymn)
        gate = gate * np.clip(gaussian_filter(binary_dilation(darkc, iterations=int(rim)).astype(np.float32), 1.0) * 1.3, 0, 1)
    Y2 = Y - gate * rb * np.maximum(Y - (ref + tol), 0)
    out = np.clip(O * (Y2 / np.maximum(Y, 1e-4))[..., None], 0, 1)
    return out.astype(np.float32), {'sky_cov%': round(100 * float((sky > 0.5).mean()), 2), 'gate_cov%': round(100 * float((gate > 0.5).mean()), 2),
                                    'changed%': round(100 * float((np.abs(Y2 - Y) > 1 / 255).mean()), 3), 'removed_p999_x255': round(255 * float(np.percentile(Y - Y2, 99.9)), 1)}


def finish(O, Q, clamp='agree5', glow=True, zmode='constant'):
    H = O.shape[0]
    res = np.empty_like(O); step, ov = 1024, 64
    for y0 in range(0, H, step):
        a, b = max(0, y0 - ov), min(H, y0 + step + ov)
        r = clamp_r2(O[a:b], Q[a:b], mode=clamp)
        res[y0:min(H, y0 + step)] = r[y0 - a:y0 - a + min(step, H - y0)]
    _dump('f09-clamp', res)
    log = {}
    if glow:
        res, gl = csc_sky(res, Q, tol=0.03, dil=4, mode='gaps', rim=5, zmode=zmode); log.update({'glow_' + k: v for k, v in gl.items()})
        _dump('f10-glow', res)
    return res, log


V4F = dict(smooth=(0.2, 0.5), keep_blacks='render', lf='hybmin', clamp='agree5', glow='skygaps')  


def v4_finish(creative, structure, init, pre, protect=None, *, smooth=(0.3, 0.6), protect_dilate=12, protect_feather=4.0,
              islands=True, chroma_clamp=True, keep_blacks='pre_narrow', clamp='lead', lf='hyb', glow=None, fin_b0_hi=None,
              release=None, island_after_lf=False, dehalo=None, anchor=None, anchor_factor=None):
    """Offline v4 finish, bit-exact: v4stack.main(variant v4n) for protect=None, v4build variant v4b with the MK2 term union as
    protect. smooth = map smoothstep (v4c: (0.2, 0.5)); islands / chroma_clamp switch the island revert and the post-FIN clamp
    (v4stack variant options 'islands' / 'hc'). Returns float32 HxWx3 in [0, 1]; to_u8() gives the offline PNG pixels.
    v4e options (defaults keep v4b): keep_blacks 'pre_narrow' (v4n) | 'render' (v3g render-keyed: S1 p1 +.011 -> +.0034 vs CV);
    clamp 'lead' (warm-tight chroma_hc2) | 'mm' (mismatch-aware chroma_mm: no PRE colours painted onto redrawn vegetation).
    v4e = smooth (0.2, 0.5), keep_blacks 'render', clamp 'mm' (offline: v4build v4d_nohc + v4mods.chroma_mm).
    v4f options (defaults keep v4b): lf 'hyb' (lead hybrid LF) | 'hybmin' (min-chroma hybrid LF, lead r2 lf_hyb_min); clamp
    'agree5' (lead r2 clamp_r2 mode agree5); glow None | 'skygaps' (lead r2 csc_sky mode gaps, rim 5, tol .03, dil 4; 'none' = None).
    v4f = V4F = smooth (0.2, 0.5), keep_blacks 'render', lf 'hybmin', clamp 'agree5', glow 'skygaps' (offline: v4build v4f_nohc ->
    8-bit PNG -> v4final.py). Each later stage reads what its offline tool reads: 'mm' and 'agree5' clamp the 8-bit pre-clamp image
    (v4mods / v4final read the saved PNG), 'agree5' in v4final's overlapping strips with the glow on its float output (one process,
    as v4final); after 'lead', 'mm' or no clamp the glow reads that stage's 8-bit result (r2glow.py on the saved PNG).
    v6 halo fix (20 Nov 2026): dehalo None | 'off' (5.0.1, bit for bit) | 'edge' (edge_profile_clamp in post, after keep_blacks).
    With dehalo on, the large-scale blurs (g, sky_gaps) also read their last row and column (zoom mode 'nearest'): no bright
    or dark last row on frames whose side is a multiple of the pool factor (round 2, halo:check D5).
    Its reference is the bilinear of `anchor` (the ORIGINAL job input at this pass's input frame, for a later pass) at output
    size with f = anchor_factor (output px per original px), else the bilinear of pre with f = output / pre. 'edge_preenv'
    (the service's mode for a later pass): with an anchor, the edges come from the anchor and the envelope from pre.
    Halo round 2 (21 Nov 2026; the service gives these to the LAST pass only, every earlier pass runs 5.0.1's finish):
    'edge2' = 'edge' with the clamp's smooth fields on a grid anchored to the whole image (exact in bands) and 5.0.1's zoom
    mode (the border fix is its own change, border/fix); 'edge2f' = 'edge2' and the same clamp once more on the finish's
    final output (after the chroma clamp and the sky-glow cap, before the toe), with the same reference.
    Round 2 revision (halo2:fix-2, 21 Nov 2026; last pass only, as round 2): 'edge3' = 'edge2' with edge_profile_clamp3 (the
    grain kept, the thin-line guard DEHALO3_GUARD: 'first' for a pass whose input is the original, 'later' with an anchor);
    'edge3f' = 'edge3' and _final_clamp3 on the final output (luma, then the chroma of every pixel the clamps changed)."""
    if (keep_blacks not in ('pre_narrow', 'render') or clamp not in ('lead', 'mm', 'agree5') or lf not in ('hyb', 'hybmin')
            or glow not in (None, 'none', 'skygaps')):
        raise ValueError('v4_finish: keep_blacks must be pre_narrow|render, clamp lead|mm|agree5, lf hyb|hybmin, glow None|skygaps')
    if dehalo not in (None, 'off', 'edge', 'edge_preenv', 'edge2', 'edge2f', 'edge3', 'edge3f'):
        raise ValueError(f'v4_finish: dehalo must be off, edge, edge_preenv, edge2, edge2f, edge3 or edge3f (got {dehalo!r})')
    v6 = dehalo in ('edge', 'edge_preenv')
    r2 = dehalo in ('edge2', 'edge2f')
    r3 = dehalo in ('edge3', 'edge3f')
    if anchor is not None and (v6 or r2 or r3) and not (anchor_factor and float(anchor_factor) >= 1.0):
        raise ValueError(f'v4_finish: an anchor needs anchor_factor >= 1 (got {anchor_factor!r})')
    zmode = 'nearest' if v6 else 'constant'
    S = _f32(creative, 'creative'); B = _f32(structure, 'structure'); P_ = _f32(pre, 'pre')
    H, W = S.shape[:2]
    if B.shape != S.shape:
        raise ValueError(f'v4_finish: structure {B.shape} != creative {S.shape}')
    if islands:
        I = _f32(init, 'init')
        if I.shape != S.shape:
            raise ValueError(f'v4_finish: init {I.shape} != creative {S.shape}')
    
    pre_t = torch.from_numpy(P_)
    m = v3g_map(pre_t, H, W, (smooth[0], smooth[1]))
    _dump('f01-map', m, channels=1)
    if protect is not None:
        pm = np.asarray(protect, dtype=np.float32)
        if pm.shape != P_.shape[:2]:
            raise ValueError(f'v4_finish: protect {pm.shape} must be at PRE resolution {P_.shape[:2]}')
        gate_ = protect_gate(pm, H, W, protect_dilate, protect_feather, release=release)
        _dump('f01-gate', gate_, channels=1)
        m = m * (1 - gate_)
        del gate_
        _dump('f01-mapgated', m, channels=1)

    ref = torch.nn.functional.interpolate(pre_t.permute(2, 0, 1)[None], size=(H, W), mode='bicubic', align_corners=False, antialias=False)[0].permute(1, 2, 0).numpy()
    pre_im = Image.fromarray(np.clip(np.round(P_ * 255), 0, 255).astype(np.uint8))
    Q = np.asarray(pre_im.resize((W, H), Image.LANCZOS), dtype=np.float32) / 255
    _dump('f02-ref', ref)
    _dump('f02-Q', Q)
    gy, gx = np.gradient(tbb(luma(Q), 1)); G = {'edge_p985': float(np.percentile(np.sqrt(gx * gx + gy * gy), 98.5))}; del gx, gy

    mm = m.copy()
    mix = (mm[..., None] * S + (1 - mm[..., None]) * B).astype(np.float32)
    _dump('f03-mix', mix)
    if islands:
        mixlf = lf_add(mix, ref, 0.0)
        whw = hardware_islands(mixlf, Q, cmap=mm, edge_t=G['edge_p985'])
        whw = colour_filter(whw, mixlf, Q)
        w = np.maximum(whw, litter_islands(Q, mm, G)); del mixlf, whw
        _dump('f04-islandw', w, channels=1)
        if not island_after_lf:
            mix = (w[..., None] * I + (1 - w[..., None]) * mix).astype(np.float32)
            _dump('f04-mixislands', mix)
    X = (lf_hyb(mix, ref, 0.06) if lf == 'hyb' else lf_hyb_min(mix, ref, 0.06)); del mix
    _dump('f05-lf', X)


    if islands and island_after_lf:
        X = (w[..., None] * I + (1 - w[..., None]) * X).astype(np.float32)
        _dump('f06-islands', X)


    finp = FINP if fin_b0_hi is None else {**FINP, 'b0': (FINP['b0'][0], float(fin_b0_hi))}
    if v6:
        finp = {**finp, 'zoom': zmode}
    Y, Yq, Y2, zone = fin_core(X, Q, finp)
    if _dumping():
        _dump('f07-fincore', np.clip(X + (Y2 - Y)[..., None], 0, 1))
    dh = None
    if v6 or r2 or r3:
        up = lambda a_: torch.nn.functional.interpolate(torch.from_numpy(np.ascontiguousarray(luma(a_)))[None, None],
                                                        size=(H, W), mode='bilinear', align_corners=False,
                                                        antialias=False)[0, 0].numpy().astype(np.float32)
        if anchor is None:
            dh = (up(P_), H / P_.shape[0])
        elif dehalo in ('edge', 'edge2', 'edge2f', 'edge3', 'edge3f'):
            dh = (up(_f32(anchor, 'anchor')), float(anchor_factor))
        else:   # edges of the original, envelope of this pass's own input
            dh = (up(_f32(anchor, 'anchor')), float(anchor_factor), up(P_))
    dctx = None
    if r3:
        src3 = P_ if anchor is None else _f32(anchor, 'anchor')
        dh = (dh[0], dh[1], luma(src3).astype(np.float32), src3, DEHALO3_GUARD['first' if anchor is None else 'later'])
        dctx = {}
        del src3
    out = post(X, Y, Yq, Y2, zone, Q, ar='agree2', kb_pre='narrow' if keep_blacks == 'pre_narrow' else False, chroma='srcwarm', ar_min=80,
               dehalo=dh, dehalo_smooth='r3' if r3 else ('pooled' if r2 else 'g'), dctx=dctx)
    fin_ref = dh if dehalo in ('edge2f', 'edge3f') else None
    fin = ((lambda o_: _final_clamp3(o_, fin_ref, dctx.get('dY'))) if dehalo == 'edge3f'
           else (lambda o_: _final_clamp(o_, fin_ref)))
    del dh
    _dump('f08-post', out)
    glow = glow == 'skygaps'
    if chroma_clamp and clamp == 'agree5':
        out, _ = finish(to_u8(out).astype(np.float32) / 255, Q, 'agree5', glow, zmode)
        return fin(out)
    if chroma_clamp:
        if clamp == 'lead':
            out = chroma_hc2(out, Q, warm=WARM)
        else:
            out = chroma_mm(to_u8(out).astype(np.float32) / 255, Q)
    if glow:
        out, _ = csc_sky(to_u8(out).astype(np.float32) / 255, Q, tol=0.03, dil=4, mode='gaps', rim=5, zmode=zmode)
    return fin(out)


def _final_clamp(out, ref):
    """Halo round 2, 'edge2f': the round-2 clamp once more on the finish's final RGB (after the chroma clamp and the sky-glow
    cap, which can lift an edge's overshoot again), with the reference the post clamp used; the luma change is added to
    every channel. ref None: out unchanged (every other mode)."""
    if ref is None:
        return out
    out = np.asarray(out, np.float32)
    Y = luma(out).astype(np.float32)
    Y2 = edge_profile_clamp(Y, ref[0], ref[1], smooth='pooled')
    if Y2 is Y:                       # no edge of geometry: the finish's own output, bit for bit
        return out
    res = np.clip(out + (Y2 - Y)[..., None], 0, 1).astype(np.float32)
    _dump('f11-dehalo-final', res)
    return res
