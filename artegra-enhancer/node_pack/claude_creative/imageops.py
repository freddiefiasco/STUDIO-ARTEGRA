"""Imageops implementation."""


import math
import torch
import torch.nn.functional as F


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


def detail_energy_cap(image, reference, cap=1.10, smin=0.5, bands=((1.5, 4.0), (4.0, 12.0))):
    """Attenuate generated mid-band luminance detail where its local energy exceeds cap x the source's (never amplifies).
    image [B,H,W,C] output size; reference [B,h,w,C] source. Luminance-only delta added to all channels."""
    x = image.permute(0, 3, 1, 2).float()
    r = reference.permute(0, 3, 1, 2).float().to(x.device)
    if r.shape[-2:] != x.shape[-2:]:
        r = F.interpolate(r, size=x.shape[-2:], mode='bicubic', align_corners=False)
    lum = lambda t: (0.2126 * t[:, 0:1] + 0.7152 * t[:, 1:2] + 0.0722 * t[:, 2:3])
    Lg, Lr = lum(x), lum(r)
    delta = torch.zeros_like(Lg)
    for lo, hi in bands:
        bg = _blur(Lg, lo) - _blur(Lg, hi)
        br = _blur(Lr, lo) - _blur(Lr, hi)
        eg = torch.sqrt(_blur(bg * bg, 3 * hi)) + 1e-5
        er = torch.sqrt(_blur(br * br, 3 * hi)) + 1e-5
        delta += (torch.clamp(cap * er / eg, smin, 1.0) - 1.0) * bg
    return torch.clamp(x + delta, 0, 1).permute(0, 2, 3, 1).to(image.dtype)


FIN1_R = (1, 3, 8, 24, 64)
FIN1_SIG = [math.sqrt(r * (r + 1)) for r in FIN1_R]
FIN1_DEAD = [(1.40, 2.10), (0.92, 1.05), (0.92, 1.08), (1.00, 1.12), (1.00, 1.12)]
FIN1_CLAMP = [(0.85, 1.7), (0.70, 1.10), (0.70, 1.10), (0.9, 1.15), (0.9, 1.15)]


def _sympad(x, r, dim):
    n = x.shape[dim]
    lo = x.narrow(dim, 0, min(r, n)).flip(dim); hi = x.narrow(dim, n - min(r, n), min(r, n)).flip(dim)
    return torch.cat([lo, x, hi], dim)


def _box(x, r, dim):
    """scipy uniform_filter(size=2r+1, mode='reflect') along dim, via float64 cumulative sums (exact, O(N))."""
    p = _sympad(x, r, dim).double()
    c = torch.cumsum(p, dim)
    c = torch.cat([torch.zeros_like(c.narrow(dim, 0, 1)), c], dim)
    n = x.shape[dim]
    return ((c.narrow(dim, 2 * r + 1, n) - c.narrow(dim, 0, n)) / (2 * r + 1)).to(x.dtype)


def _tbb(x, r):
    for _ in range(3):
        x = _box(_box(x, r, -1), r, -2)
    return x


def _stack(L):
    bl = [L] + [_tbb(L, r) for r in FIN1_R]
    return [bl[i] - bl[i + 1] for i in range(5)], bl[-1]


def _dilate_cross(m, it):
    for _ in range(it):
        p = F.pad(m.float(), (1, 1, 1, 1))
        m = (p[..., 1:-1, 1:-1] + p[..., :-2, 1:-1] + p[..., 2:, 1:-1] + p[..., 1:-1, :-2] + p[..., 1:-1, 2:]) > 0
    return m


def fin1(image, reference, kappa=0.12, iters=4, b0=(1.40, 2.10), antiring=None, keep_blacks=0.0, chroma='add', b0_flat=None):
    """Imageops implementation."""


    x = image.permute(0, 3, 1, 2).float()
    q = reference.permute(0, 3, 1, 2).float().to(x.device)
    if q.shape[-2:] != x.shape[-2:]:
        q = torch.clamp(F.interpolate(q, size=x.shape[-2:], mode='bicubic', align_corners=False, antialias=True), 0, 1)
    lum = lambda t: (0.2126 * t[:, 0:1] + 0.7152 * t[:, 1:2] + 0.0722 * t[:, 2:3])
    Y, Yq = lum(x), lum(q)
    loc = lambda b, s: torch.sqrt(torch.clamp(_blur(b * b, 2 * s), min=0)) + 1e-5
    BQ, _ = _stack(Yq)
    EQ = [loc(BQ[k], FIN1_SIG[k]) for k in range(5)]; del BQ
    if b0_flat:  
        tx = torch.sqrt(EQ[1] ** 2 + EQ[2] ** 2)
        a35, a75 = _quantile(tx, 0.35), _quantile(tx, 0.75)
        TEX = torch.clamp((tx - a35) / (a75 - a35 + 1e-6), 0, 1)
    s1 = _tbb(Yq, 1); gy = torch.zeros_like(s1); gx = torch.zeros_like(s1)
    gy[..., 1:-1, :] = (s1[..., 2:, :] - s1[..., :-2, :]) / 2; gx[..., :, 1:-1] = (s1[..., :, 2:] - s1[..., :, :-2]) / 2
    gy[..., 0, :] = s1[..., 1, :] - s1[..., 0, :]; gy[..., -1, :] = s1[..., -1, :] - s1[..., -2, :]
    gx[..., :, 0] = s1[..., :, 1] - s1[..., :, 0]; gx[..., :, -1] = s1[..., :, -1] - s1[..., :, -2]
    gm = torch.sqrt(gx * gx + gy * gy)
    zone = _dilate_cross(gm >= _quantile(gm, 0.985), 2); del s1, gx, gy, gm
    dead = [tuple(b0)] + FIN1_DEAD[1:]
    Yc = Y
    for _ in range(int(iters)):
        BD, acc = _stack(Yc)
        for k in range(5):
            ratio = EQ[k] / loc(BD[k], FIN1_SIG[k])
            lo, hi = dead[k]
            if k == 0 and b0_flat:
                lo = b0_flat[0] + TEX * (lo - b0_flat[0]); hi = b0_flat[1] + TEX * (hi - b0_flat[1])
            gain = torch.where(ratio * hi < 1, ratio * hi, torch.where(ratio * lo > 1, ratio * lo, torch.ones_like(ratio)))
            gain = _blur(torch.clamp(gain, *FIN1_CLAMP[k]), 3.0 * FIN1_SIG[k])
            if k in (1, 2):
                gain = torch.where(zone, torch.clamp(gain, max=1.0), gain)
            acc = acc + BD[k] * gain
        Yc = acc; del BD
    BD, res = _stack(Yc)
    b = 10.0 * torch.tanh(BD[0] / 10.0)
    if kappa:
        b = b * (1 + kappa * torch.sign(_blur(BD[0] ** 3, 8.0)) * torch.sign(b))
    Y2 = res + b + BD[1] + BD[2] + BD[3] + BD[4]
    Y2 = torch.where(Y2 > 0.95, 0.95 + 0.05 * torch.tanh((Y2 - 0.95) / 0.05), Y2)
    if antiring:
        r, tol = int(antiring[0]), float(antiring[1])
        az = _dilate_cross(zone, r + 2)
        w = _blur(az.float(), 1.5)
        lo = -F.max_pool2d(-Yq, 2 * r + 1, stride=1, padding=r) - tol
        hi = F.max_pool2d(Yq, 2 * r + 1, stride=1, padding=r) + tol
        Y2 = Y2 + w * (torch.minimum(torch.maximum(Y2, lo), hi) - Y2)
    if keep_blacks:
        wd = torch.clamp((0.22 - Y) / 0.17, 0, 1)
        Y2 = Y2 - keep_blacks * wd * torch.clamp(Y2 - Y, min=0)
    if chroma == 'mul':
        gn = torch.clamp(Y2 / torch.clamp(Y, min=1e-4), 0.5, 2.0)
        a = torch.clamp((Y - 0.004) / 0.012, 0, 1)
        out = a * x * gn + (1 - a) * (x + (Y2 - Y))
    else:
        out = x + (Y2 - Y)
    return torch.clamp(out, 0, 1).permute(0, 2, 3, 1).to(image.dtype)
