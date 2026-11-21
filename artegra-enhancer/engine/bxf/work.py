"""Scratch planes of the banded exact finish: raw little-endian arrays in memory-mapped files (mode w+, never copy-on-write)
under one work folder. Mapped pages are file-backed, so a whole-image intermediate costs disk and file cache, not commit
(gate G6). Pure numpy."""
import gc
import os
import shutil
from pathlib import Path

import numpy as np


class Workspace:
    """Named scratch arrays of the finish. new() makes a zero-filled mapped array; free() drops one (its file is removed once
    nothing maps it); close() removes the folder."""

    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._arrays = {}
        self._dead = []
        self.peak_bytes = 0
        self.live_bytes = 0

    def new(self, name, shape, dtype=np.float32):
        if name in self._arrays:
            raise KeyError(f'scratch plane {name} exists')
        shape = tuple(int(v) for v in shape)
        nbytes = int(np.prod(shape, dtype=np.int64)) * np.dtype(dtype).itemsize
        if nbytes == 0:
            arr, path = np.zeros(shape, dtype), None
        else:
            path = self.root / f'{name}.raw'
            arr = np.memmap(path, dtype=dtype, mode='w+', shape=shape)
        self._arrays[name] = (arr, path, nbytes)
        self.live_bytes += nbytes
        self.peak_bytes = max(self.peak_bytes, self.live_bytes)
        return arr

    def __contains__(self, name):
        return name in self._arrays

    def get(self, name):
        return self._arrays[name][0]

    def names(self):
        return list(self._arrays)

    def free(self, *names):
        for name in names:
            arr, path, nbytes = self._arrays.pop(name, (None, None, 0))
            if arr is None:
                continue
            self.live_bytes -= nbytes
            if isinstance(arr, np.memmap):
                try:
                    arr.flush()
                except Exception:
                    pass
            del arr
            if path is not None:
                self._dead.append(path)
        self._sweep()

    def _sweep(self):
        gc.collect()
        left = []
        for p in self._dead:
            try:
                os.unlink(p)
            except FileNotFoundError:
                pass
            except OSError:
                left.append(p)              # still mapped by a view somewhere: removed at close()
        self._dead = left

    def close(self):
        self.free(*list(self._arrays))
        self._sweep()
        shutil.rmtree(self.root, ignore_errors=True)
