"""Schedule implementation."""


import math
import numpy as np

T = 1000
_b = np.linspace(0.00085 ** .5, 0.012 ** .5, T, dtype=np.float64) ** 2
_ac = np.cumprod(1 - _b)
_sig = ((1 - _ac) / _ac) ** .5
_ls = np.log(_sig)
SMIN, SMAX = _sig[0], _sig[-1]


def sigma_t(t):
    t = min(max(t, 0), T - 1)
    lo, hi = int(math.floor(t)), int(math.ceil(t))
    w = t - lo
    return math.exp((1 - w) * _ls[lo] + w * _ls[hi])


def p2s(p):
    if p <= 0:
        return 1e9
    if p >= 1:
        return 0.0
    return sigma_t((1 - p) * 999)


def karras(n, rho=7.):
    r = np.linspace(0, 1, n)
    a, c = SMAX ** (1 / rho), SMIN ** (1 / rho)
    return list((a + r * (c - a)) ** rho) + [0.]


SCHED = {'karras': karras}


def run(sched, steps, d):
    tot = int(steps / d)
    s = SCHED[sched](tot)[-(steps + 1):]
    return s[:-1]


def end_mid(sched, steps, d, frac):
    ev = run(sched, steps, d)
    k = max(1, round(frac * len(ev)))
    if k >= len(ev):
        return 1.0
    target = math.sqrt(ev[k - 1] * ev[k])
    lo, hi = 0.0, 1.0
    for _ in range(60):
        m = (lo + hi) / 2
        if p2s(m) > target:
            lo = m
        else:
            hi = m
    return round(hi, 4)
