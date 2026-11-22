"""File-backed image planes of the Large-image engine (engine design section 2.3). Pure numpy; no torch.

A plane is one file: an 8-byte magic, an 8-byte little-endian header length, a JSON header (shape [H, W, C], dtype, producer,
run_id, the sha256 of its inputs, and once finished the sha256 of its data), padded so the data starts at DATA_OFFSET (a page
boundary, for memory maps), then the raw little-endian array, row-major H x W x C.

Access is by full-width row bands (buffered reads and writes into the caller's private buffers), full-height column strips,
lossless regions, or a memory map opened read-only or read-write (never copy-on-write) where a library call needs a whole
array. Mapped pages are file-backed, so on Windows they are not charged to a Job's commit limit (gate G6 measures this).

The engine's worker loads this file by path (node_pack/claude_banded), so the service and the engine share one definition."""
import hashlib
import json
import os
import struct
from pathlib import Path

import numpy as np

MAGIC = b'CUPLANE1'
DATA_OFFSET = 65536
DTYPES = {'u8': np.dtype('<u1'), 'u16': np.dtype('<u2'), 'f16': np.dtype('<f2'), 'f32': np.dtype('<f4'), 'i32': np.dtype('<i4')}
_NAMES = {v: k for k, v in DTYPES.items()}
U8_TO_F32 = np.arange(256, dtype=np.float32) / 255.0     # the classic's CPU conversion (np.float32 array / 255.0), as a table


class PlaneError(Exception):
    pass


def _dtype_name(dtype):
    """A plane dtype name ('u8', 'u16', 'f16', 'f32', 'i32'; these names win over numpy's, where 'u8' is uint64) from a name or
    a numpy dtype."""
    if isinstance(dtype, str) and dtype in DTYPES:
        return dtype
    d = np.dtype(dtype).newbyteorder('<') if np.dtype(dtype).byteorder not in ('<', '|') else np.dtype(dtype)
    if d not in _NAMES:
        raise PlaneError(f'unsupported plane dtype {dtype}')
    return _NAMES[d]


class Plane:
    """A plane on disk. Create with Plane.create, open with Plane.open."""

    def __init__(self, path, header, writable):
        self.path = Path(path)
        self.header = header
        self.writable = writable
        self.shape = tuple(int(v) for v in header['shape'])
        self.dtype = DTYPES[header['dtype']]
        self.row_bytes = self.shape[1] * self.shape[2] * self.dtype.itemsize
        self.nbytes = self.shape[0] * self.row_bytes

    # --- create / open ---------------------------------------------------------------------------------------------------
    @classmethod
    def create(cls, path, shape, dtype='u8', producer='', run_id='', inputs=None):
        if len(shape) == 2:
            shape = (shape[0], shape[1], 1)
        h, w, c = (int(v) for v in shape)
        if h <= 0 or w <= 0 or c <= 0:
            raise PlaneError(f'bad plane shape {shape}')
        header = {'shape': [h, w, c], 'dtype': _dtype_name(dtype), 'producer': str(producer), 'run_id': str(run_id),
                  'inputs': dict(inputs or {}), 'sha256': None, 'complete': False}
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        p = cls(path, header, True)
        with open(path, 'wb') as f:
            f.write(p._header_bytes())
            f.truncate(DATA_OFFSET + p.nbytes)           # sparse where the file system allows; written by bands
        return p

    @classmethod
    def open(cls, path, writable=False):
        path = Path(path)
        try:
            with open(path, 'rb') as f:
                head = f.read(16)
                if len(head) != 16 or head[:8] != MAGIC:
                    raise PlaneError(f'{path.name} is not a plane')
                n = struct.unpack('<Q', head[8:])[0]
                if not 0 < n <= DATA_OFFSET - 16:
                    raise PlaneError(f'{path.name} has a bad plane header')
                header = json.loads(f.read(n).decode('utf8'))
        except (OSError, ValueError) as e:
            raise PlaneError(f'{path.name} could not be read as a plane ({e})') from e
        p = cls(path, header, writable)
        size = path.stat().st_size
        if size != DATA_OFFSET + p.nbytes:
            raise PlaneError(f'{path.name} is {size} bytes, not the {DATA_OFFSET + p.nbytes} its header says')
        return p

    def _header_bytes(self):
        body = json.dumps(self.header, sort_keys=True, separators=(',', ':')).encode('utf8')
        if len(body) > DATA_OFFSET - 16:
            raise PlaneError('plane header too long')
        return (MAGIC + struct.pack('<Q', len(body)) + body).ljust(DATA_OFFSET, b'\x00')

    def _rewrite_header(self):
        with open(self.path, 'r+b') as f:
            f.write(self._header_bytes())

    # --- rows ------------------------------------------------------------------------------------------------------------
    def _check_rows(self, y0, y1):
        if not 0 <= y0 <= y1 <= self.shape[0]:
            raise PlaneError(f'rows {y0}:{y1} outside a plane of {self.shape[0]} rows')

    def read_rows(self, y0, y1, out=None):
        """Rows y0:y1 as an (y1 - y0, W, C) array (into `out` when given)."""
        self._check_rows(y0, y1)
        arr = out if out is not None else np.empty((y1 - y0,) + self.shape[1:], self.dtype)
        if arr.shape != (y1 - y0,) + self.shape[1:] or arr.dtype != self.dtype or not arr.flags.c_contiguous:
            raise PlaneError('read_rows: out has the wrong shape, type or layout')
        with open(self.path, 'rb', buffering=0) as f:
            f.seek(DATA_OFFSET + y0 * self.row_bytes)
            view = memoryview(arr.reshape(-1).view(np.uint8))
            got = 0
            while got < len(view):
                n = f.readinto(view[got:])
                if not n:
                    raise PlaneError(f'{self.path.name} ended early')
                got += n
        return arr

    def write_rows(self, y0, rows):
        if not self.writable:
            raise PlaneError(f'{self.path.name} is open read-only')
        rows = np.ascontiguousarray(rows, dtype=self.dtype)
        if rows.ndim == 2 and self.shape[2] == 1:
            rows = rows[..., None]
        if rows.shape[1:] != self.shape[1:]:
            raise PlaneError(f'write_rows: rows of {rows.shape[1:]} into a plane of {self.shape[1:]}')
        self._check_rows(y0, y0 + rows.shape[0])
        with open(self.path, 'r+b', buffering=0) as f:
            f.seek(DATA_OFFSET + y0 * self.row_bytes)
            f.write(rows.reshape(-1).view(np.uint8).data)

    def read_region(self, x0, y0, x1, y1):
        """A lossless crop [y0:y1, x0:x1] (row by row; never the whole plane)."""
        if not (0 <= x0 < x1 <= self.shape[1] and 0 <= y0 < y1 <= self.shape[0]):
            raise PlaneError('region outside the plane')
        out = np.empty((y1 - y0, x1 - x0, self.shape[2]), self.dtype)
        px = self.shape[2] * self.dtype.itemsize
        with open(self.path, 'rb') as f:
            for i, y in enumerate(range(y0, y1)):
                f.seek(DATA_OFFSET + y * self.row_bytes + x0 * px)
                out[i] = np.frombuffer(f.read((x1 - x0) * px), self.dtype).reshape(x1 - x0, self.shape[2])
        return out

    def read_cols(self, x0, x1):
        """A full-height column strip [:, x0:x1] (through a read-only map, copied into the caller's buffer)."""
        m = self.map('r')
        try:
            return np.array(m[:, x0:x1])
        finally:
            del m

    def map(self, mode='r'):
        """A numpy memmap of the data: 'r' (read-only) or 'r+' (read-write). Never copy-on-write."""
        if mode not in ('r', 'r+'):
            raise PlaneError("planes map 'r' or 'r+' only (never copy-on-write)")
        if mode == 'r+' and not self.writable:
            raise PlaneError(f'{self.path.name} is open read-only')
        return np.memmap(self.path, dtype=self.dtype, mode=mode, offset=DATA_OFFSET, shape=self.shape)

    # --- integrity -------------------------------------------------------------------------------------------------------
    def data_sha256(self, chunk=64 << 20):
        h = hashlib.sha256()
        with open(self.path, 'rb') as f:
            f.seek(DATA_OFFSET)
            left = self.nbytes
            while left:
                b = f.read(min(chunk, left))
                if not b:
                    raise PlaneError(f'{self.path.name} ended early')
                h.update(b)
                left -= len(b)
        return h.hexdigest()

    def finish(self):
        """Mark the plane complete with the sha256 of its data (the producer's last step)."""
        if not self.writable:
            raise PlaneError(f'{self.path.name} is open read-only')
        with open(self.path, 'r+b') as f:
            f.flush()
            os.fsync(f.fileno())
        self.header['sha256'] = self.data_sha256()
        self.header['complete'] = True
        self._rewrite_header()
        return self.header['sha256']


def validate(path, shape=None, dtype=None, check_sha=True):
    """Open a finished plane and check it, without decoding an image: its header says complete, its shape and dtype are
    the expected ones, its size matches and (check_sha) its data hash equals the header's. Returns the Plane."""
    p = Plane.open(path)
    if not p.header.get('complete'):
        raise PlaneError(f'{Path(path).name} is not complete')
    if shape is not None:
        want = tuple(shape) if len(shape) == 3 else (shape[0], shape[1], p.shape[2])
        if p.shape != want:
            raise PlaneError(f'{Path(path).name} is {p.shape}, expected {want}')
    if dtype is not None and p.header['dtype'] != dtype:
        raise PlaneError(f'{Path(path).name} is {p.header["dtype"]}, expected {dtype}')
    if check_sha and p.data_sha256() != p.header.get('sha256'):
        raise PlaneError(f'{Path(path).name} does not match its hash')
    return p


def from_array(path, arr, producer='', run_id='', band_rows=1024):
    """A finished plane holding `arr` (H x W x C or H x W), written in bands."""
    a = np.asarray(arr)
    if a.ndim == 2:
        a = a[..., None]
    p = Plane.create(path, a.shape, _dtype_name(a.dtype), producer=producer, run_id=run_id)
    for y in range(0, a.shape[0], band_rows):
        p.write_rows(y, a[y:y + band_rows])
    p.finish()
    return p


def live_bytes(I_px, R_px, O_px):
    """Bytes of the live planes of one stage at its largest moment, the finish (build wave 3; engine/banded_plan.py DISK_I,
    DISK_R and DISK_O give the plane list): 110 I (the input plane, the previous stage's file, big8, the lean SAM's float32
    view and up to 11 mask planes) + 25 R (the canvas, the hint and the edges) + 130 O (init, creative, structure, the output
    and the BXF's scratch planes, 118 B per output px: measured 116.2). Wave 2 counted 24 I + 22 R + 84 O."""
    return 110 * I_px + 25 * R_px + 130 * O_px


def disk_need(I_px, R_px, O_px, outputs_bytes=0):
    """What the disk check needs free before an image starts: the live planes x 1.1 plus the output files."""
    return int(1.1 * live_bytes(I_px, R_px, O_px)) + int(outputs_bytes)
