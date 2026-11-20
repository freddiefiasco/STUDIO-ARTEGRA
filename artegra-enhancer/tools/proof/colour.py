"""Colour and filtering for the proof metrics, in numpy alone (the app's test interpreter has numpy and Pillow, no scipy).

The conversions are the halo tools' own (sRGB IEC 61966-2-1, D65, CIE L* and Lab), so a value here and the halo metric's
value for the same pixels agree. CIEDE2000 is Sharma, Wu and Dalal (2005), checked on their published pairs
(tests/proof/test_colour.py). The Gaussian is a separable correlation with a kernel truncated at 4 sigma and the border
mirrored with the edge pixel repeated (scipy.ndimage's 'reflect', numpy's 'symmetric')."""
import numpy as np

WY = (0.2126729, 0.7151522, 0.0721750)
M_XYZ = np.array([[0.4124564, 0.3575761, 0.1804375],
                  [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]], np.float32)
WHITE = np.array([0.95047, 1.0, 1.08883], np.float32)


def srgb_to_linear(c):
    c = np.asarray(c, np.float32)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4).astype(np.float32)


def linear_to_srgb(c):
    c = np.clip(np.asarray(c, np.float32), 0, 1)
    return np.where(c <= 0.0031308, 12.92 * c, 1.055 * c ** (1 / 2.4) - 0.055).astype(np.float32)


LUT_LIN = srgb_to_linear(np.arange(256, dtype=np.float32) / 255.0)


def linear_from_rgb(img):
    """Linear-light RGB (float32) of an sRGB image: uint8 through a table, float in [0, 1] by the formula."""
    a = np.asarray(img)
    if a.ndim == 2:
        a = a[..., None].repeat(3, -1)
    a = a[..., :3]
    if a.dtype == np.uint8:
        return LUT_LIN[a]
    return srgb_to_linear(np.clip(a, 0, 1))


def f_lab(t):
    d = 6.0 / 29.0
    t = np.asarray(t, np.float32)
    return np.where(t > d ** 3, np.cbrt(np.maximum(t, 0)), t / (3 * d * d) + 4.0 / 29.0).astype(np.float32)


def lstar_from_linear(lin):
    Y = lin[..., 0] * WY[0] + lin[..., 1] * WY[1] + lin[..., 2] * WY[2]
    return (116.0 * f_lab(Y) - 16.0).astype(np.float32)


def lstar(img):
    """CIE L* (D65) of an sRGB image (H x W x 3, uint8 or float in [0, 1]) as float32 H x W."""
    return lstar_from_linear(linear_from_rgb(img))


def lab_from_linear(lin):
    xyz = np.asarray(lin, np.float32) @ M_XYZ.T / WHITE
    f = f_lab(xyz)
    return np.stack([116.0 * f[..., 1] - 16.0, 500.0 * (f[..., 0] - f[..., 1]), 200.0 * (f[..., 1] - f[..., 2])],
                    -1).astype(np.float32)


def ciede2000(lab1, lab2):
    """CIEDE2000 (kL = kC = kH = 1) between two Lab arrays (..., 3); float64 internally."""
    L1, a1, b1 = (np.asarray(lab1, np.float64)[..., i] for i in range(3))
    L2, a2, b2 = (np.asarray(lab2, np.float64)[..., i] for i in range(3))
    C1, C2 = np.hypot(a1, b1), np.hypot(a2, b2)
    Cm = (C1 + C2) / 2.0
    G = 0.5 * (1 - np.sqrt(Cm ** 7 / (Cm ** 7 + 25.0 ** 7)))
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = np.hypot(a1p, b1), np.hypot(a2p, b2)
    h1p = np.where((a1p == 0) & (b1 == 0), 0.0, np.degrees(np.arctan2(b1, a1p)) % 360.0)
    h2p = np.where((a2p == 0) & (b2 == 0), 0.0, np.degrees(np.arctan2(b2, a2p)) % 360.0)
    dLp = L2 - L1
    dCp = C2p - C1p
    zero = (C1p * C2p) == 0
    dh = h2p - h1p
    dh = np.where(dh > 180, dh - 360, np.where(dh < -180, dh + 360, dh))
    dh = np.where(zero, 0.0, dh)
    dHp = 2 * np.sqrt(C1p * C2p) * np.sin(np.radians(dh) / 2.0)
    Lpm = (L1 + L2) / 2.0
    Cpm = (C1p + C2p) / 2.0
    hs = h1p + h2p
    hpm = np.where(zero, hs, np.where(np.abs(h1p - h2p) <= 180, hs / 2.0,
                                      np.where(hs < 360, (hs + 360) / 2.0, (hs - 360) / 2.0)))
    T = (1 - 0.17 * np.cos(np.radians(hpm - 30)) + 0.24 * np.cos(np.radians(2 * hpm))
         + 0.32 * np.cos(np.radians(3 * hpm + 6)) - 0.20 * np.cos(np.radians(4 * hpm - 63)))
    dtheta = 30 * np.exp(-(((hpm - 275) / 25.0) ** 2))
    Rc = 2 * np.sqrt(Cpm ** 7 / (Cpm ** 7 + 25.0 ** 7))
    Sl = 1 + 0.015 * (Lpm - 50) ** 2 / np.sqrt(20 + (Lpm - 50) ** 2)
    Sc = 1 + 0.045 * Cpm
    Sh = 1 + 0.015 * Cpm * T
    Rt = -np.sin(np.radians(2 * dtheta)) * Rc
    return np.sqrt((dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2 + Rt * (dCp / Sc) * (dHp / Sh))


def gaussian_kernel(sigma, truncate=4.0):
    r = int(truncate * float(sigma) + 0.5)
    x = np.arange(-r, r + 1, dtype=np.float64)
    k = np.exp(-0.5 * (x / float(sigma)) ** 2)
    return k / k.sum(), r


def _corr1d(a, k, r, axis):
    pad = [(0, 0)] * a.ndim
    pad[axis] = (r, r)
    p = np.pad(a, pad, mode='symmetric')
    out = np.zeros_like(a, np.float64)
    n = a.shape[axis]
    for i, w in enumerate(k):
        sl = [slice(None)] * a.ndim
        sl[axis] = slice(i, i + n)
        out += w * p[tuple(sl)]
    return out


def gaussian(a, sigma, truncate=4.0):
    """Separable Gaussian of a 2-D array (or H x W x C, per channel), mirrored border; float32."""
    a = np.asarray(a, np.float64)
    k, r = gaussian_kernel(sigma, truncate)
    if r == 0:
        return a.astype(np.float32)
    return _corr1d(_corr1d(a, k, r, 0), k, r, 1).astype(np.float32)


def block_mean(a, b):
    """Means of whole b x b blocks of an H x W (x C) array (a trailing partial block is dropped)."""
    a = np.asarray(a, np.float64)
    h, w = a.shape[0] // b, a.shape[1] // b
    a = a[:h * b, :w * b]
    return a.reshape(h, b, w, b, *a.shape[2:]).mean((1, 3))


def area_mean(a, f):
    """Area average by an integer factor f (output -> source grid), whole blocks."""
    return block_mean(a, int(f))
