"""The G1 classification table of the banded exact finish (engine design 2.4): an op runs banded only where gate G1 measured 0
differing values for it, on the same libraries and CPU class, and only on the band geometry G1 measured; every other op, and
every pass outside that geometry, runs as the classic call, whole, on mapped planes (T7).

The table (engine/bxf/g1_table.py, written by tools/gate_g1.py) records the environment it was measured in. It applies only
where the running environment is the same: torch, numpy and scipy versions, the CPU capability torch and numpy dispatch on,
and the processor. Anywhere else, and for any op the table does not name, the verdict is 'whole' (gate G1u, which probes the
person's own CPU at first use, is a later build item).

Band-invariance is never assumed beyond what G1 measured (bxf-chk-1). Libraries choose their kernels by size: torch's conv2d,
for one, takes oneDNN only for an input of more than 20,480 elements and its native loop below, and the two sum differently, so
a banded conv on a small band can differ from the whole call although it is exact on every larger band. Each banded op
therefore carries its measured domain, and a lookup names the pass's geometry (a Geometry):
  - a local op (key 'height': the band executor's calls) is covered at band height h when the pass's width is at most the
    widest width G1 measured clean at h and some clean G1 shape at h had a width no larger than the pass's and a smallest band
    (rows read, reach included) no larger than the smallest band this pass would read; a pass of one band is the whole call
    itself and is always covered;
  - a whole-plane op (key 'any': E2-E6 and the E4/E9 out= calls, which band or chunk internally) is covered when some clean G1
    shape had a width and a plane height no larger than the pass's, and the width is at most the widest measured clean.
G1's own rule (tools/gate_g1.py) makes an op 'banded' only when every production-class shape is clean, at every height, and no
failing shape is at least as large (width and band) as a clean one; its domain's frontier then excludes every failing shape.
A table without the domain fields, a lookup without a geometry, and an op the table does not name read 'whole' (fail closed)."""
from collections import namedtuple

ENV_KEYS = ('torch', 'numpy', 'scipy', 'cpu_capability', 'numpy_simd', 'processor')


class Geometry(namedtuple('Geometry', 'H W h reach')):
    """The shape of one pass: H rows x W columns, band height h (None: a whole-plane op) and the reach in rows."""
    __slots__ = ()

    def __new__(cls, H, W, h=None, reach=0):
        return super().__new__(cls, int(H), int(W), None if h is None else int(h), int(reach))


def band_rows(H, h, reach):
    """The rows the band executor reads for each band of a plane of H rows at band height h with `reach` rows above and
    below (engine/bands.py: cores of h rows, the last the remainder, the reads clipped to the image)."""
    from .. import bands as _bands
    return [b.read_stop - b.read_start for b in _bands.bands(int(H), int(h), halo=int(reach))]


def point(geom):
    """(key, (W, rows)) for a geometry: a local op's smallest band at its height, a whole-plane op's plane height; None for a
    pass of one band (the whole call)."""
    if geom.h is None:
        return 'any', (geom.W, geom.H)
    rows = band_rows(geom.H, geom.h, geom.reach)
    if len(rows) <= 1:
        return str(geom.h), None
    return str(geom.h), (geom.W, min(rows))


def environment():
    """The facts the table is keyed on, for this process."""
    import platform
    import numpy as np
    env = {'numpy': np.__version__, 'processor': platform.processor() or platform.machine()}
    try:
        import scipy
        env['scipy'] = scipy.__version__
    except ImportError:
        env['scipy'] = None
    try:
        import torch
        env['torch'] = torch.__version__
        env['cpu_capability'] = torch.backends.cpu.get_cpu_capability()
    except ImportError:
        env['torch'] = env['cpu_capability'] = None
    try:
        from numpy._core._multiarray_umath import __cpu_features__ as feats
    except ImportError:
        try:
            from numpy.core._multiarray_umath import __cpu_features__ as feats
        except ImportError:
            feats = {}
    env['numpy_simd'] = sorted(k for k, v in feats.items() if v)
    return env


class Table:
    def __init__(self, data, env=None):
        self.data = data or {}
        self.env = env if env is not None else (environment() if data else {})
        rec = self.data.get('environment', {})
        self.mismatch = [k for k in ENV_KEYS if rec.get(k) != self.env.get(k)] if data else list(ENV_KEYS)
        self.applies = bool(data) and not self.mismatch

    def verdict(self, op):
        """The op's classification ('banded' on its measured domain, or 'whole'); covers() says whether a pass is inside it."""
        if not self.applies:
            return 'whole'
        v = self.data.get('ops', {}).get(op)
        return v.get('verdict', 'whole') if v else 'whole'

    def covers(self, op, geom):
        """True only when G1 measured `op` clean on band geometry that covers `geom` (see the module docstring)."""
        if not self.applies or geom is None or self.verdict(op) != 'banded':
            return False
        d = self.data['ops'][op].get('domain')
        if not d or d.get('key') not in ('height', 'any'):
            return False
        if d['key'] == 'height' and geom.h is None:
            return False
        key, pt = point(geom if d['key'] == 'height' else Geometry(geom.H, geom.W))
        if pt is None:
            return True
        w_max = d.get('w_max', {}).get(key)
        if w_max is None or pt[0] > w_max:
            return False
        return any(wp <= pt[0] and rp <= pt[1] for wp, rp in d.get('frontier', {}).get(key, ()))

    def banded(self, *ops, geom=None):
        """True when every op is covered at this geometry (a lookup without a geometry reads False: fail closed)."""
        return bool(ops) and all(self.covers(op, geom) for op in ops)

    def why_not(self):
        if not self.data:
            return 'no G1 table'
        if self.mismatch:
            return 'the G1 table was measured on another environment (' + ', '.join(self.mismatch) + ')'
        return None


def load(env=None):
    from . import g1_table
    return Table(g1_table.TABLE, env)


class AllBanded:
    """A table that bands everything at any geometry: tests and gates only (G1 itself, and G2's banded-path check)."""
    applies = True
    mismatch = []

    def verdict(self, op):
        return 'banded'

    def covers(self, op, geom=None):
        return True

    def banded(self, *ops, geom=None):
        return True

    def why_not(self):
        return None


class AllWhole(AllBanded):
    applies = False

    def verdict(self, op):
        return 'whole'

    def covers(self, op, geom=None):
        return False

    def banded(self, *ops, geom=None):
        return False
