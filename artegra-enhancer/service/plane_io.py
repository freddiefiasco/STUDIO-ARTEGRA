"""Result files and views of a Large-image result, streamed from its plane (engine design sections 2.9, 2.10).

The service never decodes a Large-image result whole: the stage output is a raw uint8 plane (engine/planes.py), and
- PNG 8-bit and 16-bit are written by rows (RGB or RGBA; filter Up; zlib at the given level);
- TIFF 16-bit is written by strips, as BigTIFF when its data could pass 4 GiB of offsets (32,000 x 32,000 x 6 B = 6.1 GB);
- JPEG is encoded by Pillow from a read-only map of the plane (a 4 B/px transient that admission counts; 65,500 px per side);
- the viewer gets a Lanczos proxy of at most 4096 px made in bands (the same bytes as Pillow's whole-image resize) and lossless
  regions cut from the plane (at most 4096 x 4096 px).
The alpha plane, when the input has transparency, is a uint8 H x W x 1 plane at the output size."""
import io
import os
import struct
import zlib

import numpy as np

from engine import lanczos_bands
from engine.planes import Plane

PNG_ROWS = 128
TIFF_STRIP_BYTES = 1 << 20
BIGTIFF_ABOVE = (1 << 32) - (64 << 20)       # classic TIFF offsets are 32-bit: switch to BigTIFF well before 4 GiB
VIEW_MAX_SIDE = 4096
JPEG_MAX_SIDE = 65500


def _chunk(tag, data):
    return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data) & 0xFFFFFFFF)


def _rows(plane, alpha, y0, y1, bits):
    rows = plane.read_rows(y0, y1)
    if alpha is not None:
        rows = np.concatenate([rows, alpha.read_rows(y0, y1)], axis=2)
    if bits == 16:
        return rows.astype(np.uint16) * np.uint16(257)
    return rows


def write_png(path, plane, bits=8, alpha=None, level=6, icc=None, exif=None):
    """A PNG (8 or 16 bits per sample, RGB or RGBA) streamed from a uint8 plane by PNG_ROWS rows; 16-bit widens x257 as the
    classic writer does (service/images.py write_png16)."""
    h, w, c = plane.shape
    if c != 3 or (alpha is not None and alpha.shape != (h, w, 1)):
        raise ValueError('write_png: an RGB plane and an optional H x W x 1 alpha plane')
    ch = 4 if alpha is not None else 3
    with open(path, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n')
        f.write(_chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, bits, 2 if ch == 3 else 6, 0, 0, 0)))
        if icc:
            f.write(_chunk(b'iCCP', b'sRGB\x00\x00' + zlib.compress(icc)))
        if exif:
            f.write(_chunk(b'eXIf', exif[6:] if exif.startswith(b'Exif\x00\x00') else exif))
        comp = zlib.compressobj(level)
        row_bytes = w * ch * (bits // 8)
        prev = np.zeros(row_bytes, np.uint8)
        pending, size = [], 0
        for y0 in range(0, h, PNG_ROWS):
            r = _rows(plane, alpha, y0, min(h, y0 + PNG_ROWS), bits)
            rows = np.ascontiguousarray(r.astype('>u2') if bits == 16 else r).view(np.uint8).reshape(-1, row_bytes)
            up = np.vstack([prev[None], rows[:-1]])
            filt = (rows - up).astype(np.uint8)
            prev = rows[-1].copy()
            out = comp.compress(np.hstack([np.full((rows.shape[0], 1), 2, np.uint8), filt]).tobytes())
            if out:
                pending.append(out)
                size += len(out)
            if size > (4 << 20):
                f.write(_chunk(b'IDAT', b''.join(pending)))
                pending, size = [], 0
        pending.append(comp.flush())
        f.write(_chunk(b'IDAT', b''.join(pending)))
        f.write(_chunk(b'IEND', b''))
        f.flush()
        os.fsync(f.fileno())


def write_tiff16(path, plane, alpha=None, icc=None, software='Artegra Enhancer', big=None):
    """A 16-bit RGB or RGBA TIFF (Adobe Deflate strips, horizontal predictor, unassociated alpha, ICC), streamed strip by
    strip to disk; BigTIFF when `big`, or (big None) when the uncompressed data could pass BIGTIFF_ABOVE. Returns 'bigtiff' or
    'tiff'."""
    h, w, _ = plane.shape
    c = 4 if alpha is not None else 3
    if big is None:
        big = h * w * c * 2 > BIGTIFF_ABOVE
    rows_per_strip = max(1, min(h, TIFF_STRIP_BYTES // (w * c * 2)))
    offsets, counts = [], []
    with open(path, 'wb') as f:
        f.write(b'II+\x00' + struct.pack('<HHQ', 8, 0, 0) if big else b'II*\x00' + struct.pack('<I', 0))
        for y0 in range(0, h, rows_per_strip):
            a = _rows(plane, alpha, y0, min(h, y0 + rows_per_strip), 16).astype(np.int32)
            d = a.copy()
            d[:, 1:, :] = a[:, 1:, :] - a[:, :-1, :]
            s = zlib.compress((d & 0xFFFF).astype('<u2').tobytes(), 6)
            offsets.append(f.tell())
            counts.append(len(s))
            f.write(s)
            if f.tell() % 2:
                f.write(b'\x00')
        if not big and f.tell() >= (1 << 32):
            raise OSError('TIFF data passed 4 GiB; write it as BigTIFF')
        sw = lambda *v: struct.pack(f'<{len(v)}H', *v)
        if big:
            off_t, cnt_t, packo = 16, 16, (lambda *v: struct.pack(f'<{len(v)}Q', *v))
        else:
            off_t, cnt_t, packo = 4, 4, (lambda *v: struct.pack(f'<{len(v)}I', *v))
        lo = lambda *v: struct.pack(f'<{len(v)}I', *v)
        asc = (software.encode('ascii', 'replace') + b'\x00')
        e = [(256, 4, 1, lo(w)), (257, 4, 1, lo(h)), (258, 3, c, sw(*([16] * c))), (259, 3, 1, sw(8)), (262, 3, 1, sw(2)),
             (273, off_t, len(offsets), packo(*offsets)), (277, 3, 1, sw(c)), (278, 4, 1, lo(rows_per_strip)),
             (279, cnt_t, len(counts), packo(*counts)), (284, 3, 1, sw(1)), (305, 2, len(asc), asc), (317, 3, 1, sw(2)),
             (339, 3, c, sw(*([1] * c)))]
        if c == 4:
            e.append((338, 3, 1, sw(2)))
        if icc:
            e.append((34675, 7, len(icc), icc))
        e.sort(key=lambda x: x[0])
        if f.tell() % 8:
            f.write(b'\x00' * (8 - f.tell() % 8))
        ifd_pos = f.tell()
        inline = 8 if big else 4
        entry = 20 if big else 12
        extra_pos = ifd_pos + (8 if big else 2) + entry * len(e) + (8 if big else 4)
        head, extra = [struct.pack('<Q', len(e)) if big else struct.pack('<H', len(e))], []
        for tag, typ, count, val in e:
            if len(val) <= inline:
                head.append(struct.pack('<HHQ' if big else '<HHI', tag, typ, count) + val.ljust(inline, b'\x00'))
            else:
                off = extra_pos + sum(len(x) for x in extra)
                head.append(struct.pack('<HHQQ' if big else '<HHII', tag, typ, count, off))
                extra.append(val + (b'\x00' if len(val) % 2 else b''))
        head.append(struct.pack('<Q', 0) if big else struct.pack('<I', 0))
        f.write(b''.join(head) + b''.join(extra))
        f.seek(8 if big else 4)
        f.write(struct.pack('<Q', ifd_pos) if big else struct.pack('<I', ifd_pos))
        f.flush()
        os.fsync(f.fileno())
    return 'bigtiff' if big else 'tiff'


def write_jpeg(path, plane, quality=95, icc=None, exif=None):
    """JPEG through Pillow from a read-only map of the plane (the whole-image encode is the counted 4 B/px transient)."""
    from PIL import Image
    h, w, _ = plane.shape
    if max(h, w) > JPEG_MAX_SIDE:
        raise ValueError(f'JPEG allows at most {JPEG_MAX_SIDE:,} px per side')
    m = plane.map('r')
    try:
        Image.fromarray(np.asarray(m), 'RGB').save(path, 'JPEG', quality=quality, subsampling=0, icc_profile=icc,
                                                   exif=exif or b'')
    finally:
        del m
    with open(path, 'rb+') as f:
        os.fsync(f.fileno())


def jpeg_transient_bytes(w, h):
    return 4 * int(w) * int(h)


def encode(path, plane, fmt, alpha=None, icc=None, exif=None, software='Artegra Enhancer'):
    """The final file of a Large-image result, by format (as service.images.encode for a classic result). Returns facts for
    the sidecar."""
    info = {'format': fmt, 'icc': 'sRGB' if icc else 'none', 'alpha': 'none', 'exif': 'none',
            'bits': 16 if fmt in ('png16', 'tiff16') else 8, 'writer': 'streamed'}
    keep = alpha is not None and fmt != 'jpeg'
    if alpha is not None:
        info['alpha'] = 'kept' if keep else 'dropped (JPEG has no transparency)'
    if fmt == 'png8':
        write_png(path, plane, 8, alpha if keep else None, 6, icc, exif)
        info['exif'] = 'copied' if exif else 'none'
    elif fmt == 'png16':
        write_png(path, plane, 16, alpha if keep else None, 6, icc, exif)
        info['exif'] = 'copied' if exif else 'none'
    elif fmt == 'tiff16':
        info['container'] = write_tiff16(path, plane, alpha if keep else None, icc, software)
    elif fmt == 'jpeg':
        write_jpeg(path, plane, 95, icc, exif)
        info['exif'] = 'copied' if exif else 'none'
    else:
        raise ValueError(f'Unknown output format {fmt}')
    return info


# --- the viewer --------------------------------------------------------------------------------------------------------------

def proxy(plane, tmp_dir, long_side=VIEW_MAX_SIDE):
    """A fit proxy (at most long_side px) of a uint8 plane, by banded Lanczos: the bytes of Pillow's whole-image
    resize(size, LANCZOS). Returns an H2 x W2 x C array (small)."""
    h, w, c = plane.shape
    W2, H2 = lanczos_bands.proxy_size(w, h, long_side)
    dst = lanczos_bands.ArrayRows(np.zeros((H2, W2, c), np.uint8))
    tmp = None
    if W2 != w and H2 != h:
        tmp = Plane.create(os.path.join(tmp_dir, 'proxy-h.plane'), (h, W2, c), 'u8', producer='viewer proxy')
    try:
        lanczos_bands.resize(plane, dst, tmp)
    finally:
        if tmp is not None:
            try:
                os.unlink(tmp.path)
            except OSError:
                pass
    return dst.a


def region(plane, x, y, w, h, max_side=VIEW_MAX_SIDE):
    """A lossless 1:1 region (the requested rectangle intersected with the image) as an array, and the part returned."""
    if w <= 0 or h <= 0 or w > max_side or h > max_side:
        raise ValueError(f'Region width and height must be 1 to {max_side} px')
    H, W, _ = plane.shape
    x0, y0 = max(0, int(x)), max(0, int(y))
    x1, y1 = min(W, int(x) + int(w)), min(H, int(y) + int(h))
    if x1 <= x0 or y1 <= y0:
        raise ValueError('The region is outside the image')
    return plane.read_region(x0, y0, x1, y1), (x0, y0, x1 - x0, y1 - y0)


def region_png(plane, x, y, w, h, alpha=None, max_side=VIEW_MAX_SIDE):
    """region() as PNG bytes (RGBA when an alpha plane is given), as service.images.region_png returns for a classic result."""
    from PIL import Image
    arr, box = region(plane, x, y, w, h, max_side)
    if alpha is not None:
        a, _ = region(alpha, x, y, w, h, max_side)
        arr = np.concatenate([arr, a], axis=2)
    buf = io.BytesIO()
    Image.fromarray(arr if arr.shape[2] != 1 else arr[..., 0]).save(buf, 'PNG', compress_level=1)
    return buf.getvalue(), box
