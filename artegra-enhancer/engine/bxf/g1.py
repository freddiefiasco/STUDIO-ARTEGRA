"""The G1 classification table of the banded exact finish (engine design 2.4): an op runs banded only where gate G1 measured 0
differing values for it, on the same libraries and CPU class; every other op runs as the classic call, whole, on mapped planes.

The table (engine/bxf/g1_table.py, written by tools/gate_g1.py) records the environment it was measured in. It applies only
where the running environment is the same: torch, numpy and scipy versions, the CPU capability torch and numpy dispatch on,
and the processor. Anywhere else, and for any op the table does not name, the verdict is 'whole' (gate G1u, which probes the
person's own CPU at first use, is a later build item)."""

ENV_KEYS = ('torch', 'numpy', 'scipy', 'cpu_capability', 'numpy_simd', 'processor')


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
        if not self.applies:
            return 'whole'
        v = self.data.get('ops', {}).get(op)
        return v.get('verdict', 'whole') if v else 'whole'

    def banded(self, *ops):
        return all(self.verdict(op) == 'banded' for op in ops)

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
    """A table that bands everything: tests and gates only (G1 itself, and G2's banded-path check against the classic)."""
    applies = True
    mismatch = []

    def verdict(self, op):
        return 'banded'

    def banded(self, *ops):
        return True

    def why_not(self):
        return None


class AllWhole(AllBanded):
    applies = False

    def verdict(self, op):
        return 'whole'

    def banded(self, *ops):
        return False
