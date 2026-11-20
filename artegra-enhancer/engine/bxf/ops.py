"""The band ops a BXF pool child may run: numpy and scipy only (never torch; E8, E9 and every torch op stay in the worker
process). Each op is f(inputs, params) -> outputs for one block of rows (or columns, for column ops) and is the very call the
in-process path makes, so a pool of any registered size gives the same bytes as one process (G1 checks {1, 2, 4})."""
import numpy as np


def _gaussian(inputs, p):
    from scipy.ndimage import gaussian_filter
    return (gaussian_filter(inputs[0], p['sigma']),)


def _maximum(inputs, p):
    from scipy.ndimage import maximum_filter
    return (maximum_filter(inputs[0], p['size']),)


def _minimum(inputs, p):
    from scipy.ndimage import minimum_filter
    return (minimum_filter(inputs[0], p['size']),)


def _dilate(inputs, p):
    from scipy.ndimage import binary_dilation
    return (binary_dilation(inputs[0], iterations=int(p['iterations'])),)


def _uniform1d(inputs, p):
    from scipy.ndimage import uniform_filter1d
    x = inputs[0]
    out = np.empty(x.shape, np.dtype(p.get('dtype', x.dtype.str)))
    uniform_filter1d(x, int(p['size']), axis=int(p['axis']), output=out, mode=p.get('mode', 'reflect'))
    return (out,)


def _gradient_mag(inputs, p):
    gy, gx = np.gradient(inputs[0])
    return (np.sqrt(gx * gx + gy * gy),)


OPS = {'gaussian_filter': _gaussian, 'maximum_filter': _maximum, 'minimum_filter': _minimum, 'binary_dilation': _dilate,
       'uniform_filter1d': _uniform1d, 'gradient_mag': _gradient_mag}

# column ops read full-height column strips (every column whole); the rest read row bands with a halo
COLUMN_OPS = {'uniform_filter1d_axis0'}


def run(op, inputs, params):
    return OPS[op](inputs, params)
