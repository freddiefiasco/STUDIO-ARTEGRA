"""Synthetic image fixtures and independent output decoders for CPU-only tests."""
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zlib
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[2]


def tmpdir(prefix='cu-test-'):
    return Path(tempfile.mkdtemp(prefix=prefix))


def rmtree(p):
    shutil.rmtree(p, ignore_errors=True)


def gradient(w, h, seed=0):
    """Deterministic RGB test picture with structure (gradients + noise)."""
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:h, 0:w]
    a = np.stack([(x * 255 // max(1, w - 1)), (y * 255 // max(1, h - 1)), ((x + y) * 3) % 256], -1).astype(np.int32)
    a = np.clip(a + rng.integers(-12, 12, a.shape), 0, 255).astype(np.uint8)
    return a


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


# ---- independent readers for the service's own 16-bit encoders --------------------------------------------------------
def read_png16(path):
    data = Path(path).read_bytes()
    assert data[:8] == b'\x89PNG\r\n\x1a\n'
    pos, idat, chunks = 8, b'', {}
    while pos < len(data):
        n = struct.unpack('>I', data[pos:pos + 4])[0]
        tag = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + n]
        crc = struct.unpack('>I', data[pos + 8 + n:pos + 12 + n])[0]
        assert zlib.crc32(tag + body) & 0xFFFFFFFF == crc, tag
        if tag == b'IDAT':
            idat += body
        else:
            chunks[tag] = body
        pos += 12 + n
    w, h, depth, ctype = struct.unpack('>IIBB', chunks[b'IHDR'][:10])
    c = {2: 3, 6: 4}[ctype]
    raw = zlib.decompress(idat)
    stride = w * c * 2
    rows = np.frombuffer(raw, np.uint8).reshape(h, stride + 1)
    out = np.zeros((h, stride), np.uint8)
    prev = np.zeros(stride, np.uint8)
    for y in range(h):
        ft, line = rows[y, 0], rows[y, 1:]
        if ft == 0:
            cur = line
        elif ft == 2:
            cur = (line.astype(np.uint16) + prev).astype(np.uint8)
        else:
            raise AssertionError(f'unexpected filter {ft}')
        out[y] = cur
        prev = cur
    arr = out.view('>u2').reshape(h, w, c).astype(np.uint16)
    return arr, depth, chunks


def read_tiff16(path):
    data = Path(path).read_bytes()
    assert data[:4] == b'II*\x00'
    ifd = struct.unpack('<I', data[4:8])[0]
    n = struct.unpack('<H', data[ifd:ifd + 2])[0]
    tags = {}
    sizes = {2: 1, 3: 2, 4: 4, 7: 1}
    for i in range(n):
        tag, typ, cnt, val = struct.unpack('<HHI4s', data[ifd + 2 + 12 * i:ifd + 14 + 12 * i])
        size = sizes[typ] * cnt
        raw = val[:size] if size <= 4 else data[struct.unpack('<I', val)[0]:struct.unpack('<I', val)[0] + size]
        if typ == 3:
            tags[tag] = struct.unpack(f'<{cnt}H', raw)
        elif typ == 4:
            tags[tag] = struct.unpack(f'<{cnt}I', raw)
        else:
            tags[tag] = raw
    w, h, c = tags[256][0], tags[257][0], tags[277][0]
    rps = tags[278][0]
    rows = []
    for off, cnt in zip(tags[273], tags[279]):
        d = np.frombuffer(zlib.decompress(data[off:off + cnt]), '<u2').astype(np.int64)
        d = d.reshape(-1, w, c)
        if tags.get(317, (1,))[0] == 2:
            d = np.cumsum(d, axis=1) & 0xFFFF
        rows.append(d)
    arr = np.concatenate(rows, 0)[:h].astype(np.uint16)
    assert arr.shape[0] == h and rps >= 1
    return arr, tags



def write_image(path, arr, **save):
    Image.fromarray(arr).save(path, **save)
    return Path(path)
