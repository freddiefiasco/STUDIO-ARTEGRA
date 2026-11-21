"""The band executor of local ops (engine design 2.4, class E1): the SAME call on a full-width band plus `reach` real rows above
and below (clipped at the true image border, where the call's own border rule applies), keeping the core rows. A band is exact
when every op inside the call is band-invariant (gate G1 measured 0 differing values) and `reach` covers the call's whole
chain of neighbourhoods. Where G1 did not prove an op, or did not measure it on this pass's band geometry (its width and the
smallest band it would read), the call runs whole on the mapped planes instead (T7)."""
import numpy as np

from .. import bands as _bands


def _as_tuple(r):
    return r if isinstance(r, tuple) else (r,)


def run_bands(fn, inputs, outputs, height, reach, progress=None):
    """For each band: fn(*[input rows read_start:read_stop]) -> one array or a tuple, one per output; each output takes the
    core rows. Inputs and outputs are arrays (mapped or private) with the same number of rows, or row views of a (C, H, W)
    plane (an object with row_axis = 1, whose band slice and band result are (C, rows, W))."""
    H = int(outputs[0].shape[0])
    for a in list(inputs) + list(outputs):
        if a.shape[0] != H:
            raise ValueError(f'run_bands: an array of {a.shape[0]} rows in a pass of {H} rows')
    for b in _bands.bands(H, height, halo=int(reach)):
        args = [np.asarray(a[b.read_start:b.read_stop]) for a in inputs]
        res = _as_tuple(fn(*args))
        if len(res) != len(outputs):
            raise ValueError('run_bands: the band function returned the wrong number of arrays')
        lo = b.core_offset
        for o, r in zip(outputs, res):
            r = np.asarray(r)
            ax = getattr(o, 'row_axis', 0)
            if r.shape[ax] != b.read_stop - b.read_start:
                raise ValueError('run_bands: a band result must keep the rows it was given')
            o[b.start:b.stop] = r[lo:lo + b.rows] if ax == 0 else r[:, lo:lo + b.rows]
        if progress is not None:
            progress(b)
    for o in outputs:
        if isinstance(o, np.memmap):
            o.flush()


def run_whole(fn, inputs, outputs):
    """The classic call on the whole mapped arrays (T7): its own temporaries are private while it runs."""
    res = _as_tuple(fn(*[np.asarray(a) for a in inputs]))
    for o, r in zip(outputs, res):
        o[...] = r
        if isinstance(o, np.memmap):
            o.flush()


def band_height(width, bytes_per_px, budget_gb, reach):
    """The registered band height whose rows (core + 2 x reach) fit the band budget at `bytes_per_px` private bytes per pixel
    of the band call (an estimate; pixel-neutral: any registered height gives the same bytes)."""
    return _bands.band_height_for(int(width), float(bytes_per_px), float(budget_gb) * 2 ** 30, int(reach))


class Runner:
    """Runs local ops banded where G1 proved every op in them on this pass's band geometry (the width, the band height and
    the smallest band it would read: engine/bxf/g1.py), else whole (T7). budget_gb: the band budget (registered). height: a
    registered band height used for every banded pass instead of the budget's choice (gates and tests; pixel-neutral)."""

    def __init__(self, table, budget_gb, progress=None, log=None, height=None):
        self.table = table
        self.budget_gb = _bands.check_band_budget(budget_gb)
        self.height = None if height is None else _bands.check_band_height(int(height))
        self.progress = progress
        self.log = log if log is not None else []

    def would_band(self, ops, rows, width, reach, bytes_per_px=64.0):
        """('banded', band height) when every op is covered at this pass's geometry, else ('whole', None)."""
        from .g1 import Geometry
        h = self.height or band_height(width, bytes_per_px, self.budget_gb, reach)
        if self.table.banded(*ops, geom=Geometry(rows, width, h, reach)):
            return 'banded', h
        return 'whole', None

    def __call__(self, name, fn, inputs, outputs, reach, ops, bytes_per_px=64.0):
        rows = int(outputs[0].shape[0])
        width = int(outputs[0].shape[1]) if outputs[0].ndim > 1 else 1
        mode, h = self.would_band(ops, rows, width, reach, bytes_per_px)
        if mode == 'banded':
            run_bands(fn, inputs, outputs, h, reach, self.progress)
            self.log.append((name, 'banded', h, int(reach)))
        else:
            run_whole(fn, inputs, outputs)
            self.log.append((name, 'whole', None, int(reach)))
