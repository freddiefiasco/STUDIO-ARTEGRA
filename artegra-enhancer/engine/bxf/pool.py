"""A pool of CPU processes for registered numpy/scipy band ops of the banded exact finish (engine design 2.5).

The count is a registered value (bands.PROCESS_COUNTS: 1, 2 or 4) and pixel-neutral: every band is the same call on the same
rows whichever process runs it. Children are plain Python processes of the same interpreter (sys.executable, isolated mode,
no thread-count variable set or changed), started by a small script that loads this engine package BY PATH under the
private name cu_banded_engine (as the node pack does), so nothing in the worker is re-imported or patched (no multiprocessing
spawn, which would re-run the worker's __main__). They share the planes through file-backed memory maps and run only the ops
in ops.OPS. With one process every band runs in the calling process and no child is started."""
import json
import mmap
import subprocess
import sys
from pathlib import Path

import numpy as np

from .. import bands as _bands
from . import ops as _ops

_ENGINE_DIR = Path(__file__).resolve().parents[1]
_CHILD = Path(__file__).resolve().parent / '_child.py'


def spec_of(m):
    """The file spec of a C-contiguous file-backed memmap (its own mapping, not a view)."""
    if not isinstance(m, np.memmap) or not isinstance(m.base, mmap.mmap) or not m.flags.c_contiguous:
        raise ValueError('pool arrays must be whole, C-contiguous file-backed memmaps')
    return {'path': str(m.filename), 'offset': int(m.offset), 'shape': [int(v) for v in m.shape], 'dtype': m.dtype.str}


class BandPool:
    """with BandPool(n) as pool: pool.map_rows(op, params, inputs, outputs, height, reach)."""

    def __init__(self, processes=1):
        self.n = _bands.check_process_count(int(processes))
        self.children = []

    def __enter__(self):
        if self.n > 1:
            for _ in range(self.n):
                p = subprocess.Popen([sys.executable, '-I', '-B', str(_CHILD), str(_ENGINE_DIR)], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, text=True, encoding='utf8', bufsize=1)
                line = p.stdout.readline().strip()
                if line != 'ready':
                    p.kill()
                    raise RuntimeError(f'a finish pool process did not start ({line!r})')
                self.children.append(p)
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        for p in self.children:
            try:
                p.stdin.write(json.dumps({'quit': True}) + '\n')
                p.stdin.flush()
                p.wait(timeout=30)
            except Exception:
                p.kill()
        self.children = []

    def map_rows(self, op, params, inputs, outputs, height, reach=0):
        """For each row band (registered height, `reach` halo rows): outputs[core] = ops.run(op, inputs[read rows], params)."""
        H = int(outputs[0].shape[0])
        parts = [[b.start, b.stop, b.read_start, b.read_stop] for b in _bands.bands(H, height, halo=int(reach))]
        self._run(op, params, inputs, outputs, parts, 'rows')

    def map_cols(self, op, params, inputs, outputs, strip=1024):
        """For each full-height column strip: outputs[:, strip] = ops.run(op, inputs[:, strip], params) (column-whole ops)."""
        W = int(outputs[0].shape[1])
        parts = [[x0, min(W, x0 + strip), x0, min(W, x0 + strip)] for x0 in range(0, W, strip)]
        self._run(op, params, inputs, outputs, parts, 'cols')

    def _run(self, op, params, inputs, outputs, parts, axis):
        if op not in _ops.OPS:
            raise KeyError(f'{op} is not a registered pool op')
        if self.n == 1 or not self.children:
            run_parts(op, params, inputs, outputs, parts, axis)
            for o in outputs:
                if isinstance(o, np.memmap):
                    o.flush()
            return
        for o in outputs:
            o.flush()
        job = {'op': op, 'params': params, 'axis': axis, 'inputs': [spec_of(a) for a in inputs],
               'outputs': [spec_of(a) for a in outputs]}
        for i, p in enumerate(self.children):
            p.stdin.write(json.dumps(dict(job, parts=parts[i::self.n])) + '\n')
            p.stdin.flush()
        errors = []
        for p in self.children:
            r = json.loads(p.stdout.readline())
            if not r.get('ok'):
                errors.append(r.get('error', 'unknown error'))
        if errors:
            raise RuntimeError('a finish pool process failed: ' + '; '.join(errors))


def run_parts(op, params, inputs, outputs, parts, axis):
    """The in-process (and the child's) loop: the same op call on each part."""
    for s, e, rs, re_ in parts:
        if axis == 'rows':
            args = [np.asarray(a[rs:re_]) for a in inputs]
        else:
            args = [np.asarray(a[:, rs:re_]) for a in inputs]
        res = _ops.run(op, args, params)
        for o, r in zip(outputs, res):
            if axis == 'rows':
                o[s:e] = r[s - rs:s - rs + (e - s)]
            else:
                o[:, s:e] = r[:, s - rs:s - rs + (e - s)]
