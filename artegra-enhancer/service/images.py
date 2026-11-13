"""Images implementation."""


import io
import math
import os
import secrets
import struct
import threading
import time
import zlib
from collections import OrderedDict
from pathlib import Path

import numpy as np
from PIL import Image, ImageCms, ImageOps, UnidentifiedImageError

from engine import planner
from service.util import fsync_file, replace_with_retry


Image.MAX_IMAGE_PIXELS = 300_000_000

SUPPORTED_FORMATS = {'PNG': 'PNG', 'JPEG': 'JPEG', 'MPO': 'JPEG', 'TIFF': 'TIFF', 'WEBP': 'WebP', 'BMP': 'BMP', 'DIB': 'BMP'}
INPUT_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.jpe', '.jfif', '.tif', '.tiff', '.webp', '.bmp', '.dib'}
OUTPUT_EXT = {'png8': '.png', 'png16': '.png', 'tiff16': '.tif', 'jpeg': '.jpg'}
THUMB_SIDE, PROXY_SIDE = 320, 2048
MATTE = (38, 38, 38)            
PREVIEW_PNG_LEVEL = 6           
VIEW_ALPHA_PNG_LEVEL = 1        
EXIF_IFD0_KEEP = {270, 271, 272, 306, 315, 33432, 0x8769, 0x8825}   # description, make, model, date, artist, copyright, Exif, GPS
EXIF_SUB_DROP = {0x927C, 0xA002, 0xA003, 0xA005}                   
ORIENTATION = 0x0112


class InputRejected(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


class OutputError(Exception):
    pass


class SidecarPending(Exception):
    """The output file is published, but its sidecar could not be written yet (the folder became unreachable). The caller
    retries `write_sidecar(output, data)` only; the output must never be encoded or published again."""

    def __init__(self, output, data, cause):
        super().__init__(f'{output}: sidecar not written ({cause})')
        self.output, self.data, self.cause = Path(output), data, cause


_srgb_lock = threading.Lock()
_srgb = {}


def srgb_profile():
    with _srgb_lock:
        if 'p' not in _srgb:
            _srgb['p'] = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB'))
            
            
            b = bytearray(_srgb['p'].tobytes())
            b[24:36] = struct.pack('>6H', 2026, 11, 5, 0, 0, 0)
            _srgb['b'] = bytes(b)
        return _srgb['p']


def srgb_icc_bytes():
    srgb_profile()
    return _srgb['b']


def _png_bit_depth(path):
    try:
        with open(path, 'rb') as f:
            head = f.read(26)
    except OSError:
        return None
    if head[:8] == b'\x89PNG\r\n\x1a\n' and head[12:16] == b'IHDR':
        return head[24]
    return None


def _bit_depth(im, path):
    if im.format == 'PNG':
        return _png_bit_depth(path) or 8
    if im.format == 'TIFF':
        bps = getattr(im, 'tag_v2', {}).get(258)
        if isinstance(bps, (tuple, list)) and bps:
            return int(max(bps))
        if isinstance(bps, int):
            return bps
    if im.mode.startswith('I;16'):
        return 16
    return 8


def _to_8bit_single(im, bit_depth):
    """16-bit / 32-bit integer or float single-channel modes -> 8-bit 'L' (PIL's own convert clips instead of scaling)."""
    a = np.asarray(im)
    if im.mode == 'F':
        a = a.astype(np.float64)
        scale = 255.0 if np.nanmax(a) <= 1.0 else 1.0
        a = np.nan_to_num(a * scale)
    else:
        a = a.astype(np.float64)
        if bit_depth >= 16 or a.max() > 255:
            a = a / 257.0
    return Image.fromarray(np.clip(np.round(a), 0, 255).astype(np.uint8), 'L')


def filtered_exif_bytes(exif):
    """Source EXIF for the output: descriptive IFD0 tags + Exif and GPS sub-IFDs, without orientation (already applied), pixel
    size and maker notes (their offsets break when re-written). Returns bytes ('Exif\\0\\0' + TIFF) or None."""
    if exif is None or len(exif) == 0:
        return None
    out = Image.Exif()
    for tag in EXIF_IFD0_KEEP:
        if tag not in exif:
            continue
        if tag in (0x8769, 0x8825):
            sub = {k: v for k, v in dict(exif.get_ifd(tag)).items() if k not in EXIF_SUB_DROP}
            if sub:
                out[tag] = sub
        else:
            out[tag] = exif[tag]
    if len(out) == 0:
        return None
    return out.tobytes()


def normalise(path, out_dir, max_mp=planner.MAX_INPUT_MP, min_side=planner.MIN_SIDE):
    """Read one input image, refuse it with a plain reason, or write the engine-ready files into out_dir.
    Returns a record (width, height after orientation, format, mode, bit_depth, alpha, icc, exif, notes)."""
    path = Path(path)
    notes = []
    try:
        im = Image.open(path)
    except FileNotFoundError:
        raise InputRejected('The file was not found.')
    except PermissionError:
        raise InputRejected('The file could not be opened (access was denied).')
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError):
        raise InputRejected('Not an image file.')
    with im:
        fmt = SUPPORTED_FORMATS.get(im.format)
        if fmt is None:
            raise InputRejected(f'{im.format or "This"} files are not supported. Use PNG, JPEG, TIFF, WebP or BMP.')
        frames = getattr(im, 'n_frames', 1)
        if im.format == 'MPO':
            if frames > 1:
                notes.append('This camera file holds several pictures; the first one is used.')
        elif frames > 1:
            raise InputRejected('Animated or multi-page images are not supported. Save a single image and add that.')
        w0, h0 = im.size
        if w0 * h0 > max_mp * 1e6:
            raise InputRejected(f'This image is very large ({w0 * h0 / 1e6:.0f} MP). Images up to {max_mp:.0f} MP are supported.')
        if min(w0, h0) < min_side:
            raise InputRejected(f'Too small ({w0} × {h0} px); the shorter side needs at least {min_side} px.')
        bit_depth = _bit_depth(im, path)
        try:
            exif = im.getexif()
        except (OSError, ValueError, SyntaxError, struct.error, TypeError):
            exif = None
            notes.append('The camera details in this file are damaged, so they were not copied to the result.')
        orientation = exif.get(ORIENTATION) if exif is not None else None
        icc = im.info.get('icc_profile')
        try:
            im.load()
        except (OSError, ValueError, SyntaxError, EOFError, struct.error, zlib.error):
            raise InputRejected('The image data is damaged or incomplete.')
        try:
            im2 = ImageOps.exif_transpose(im)
        except (OSError, ValueError, SyntaxError, struct.error, TypeError):
            im2 = im.copy()
            notes.append('Which way is up could not be read from this file, so the image is used as stored.')
        mode_in = im.mode
    if orientation not in (None, 1):
        notes.append('Turned upright, as the camera recorded it.')

    base, alpha = _split_colour_alpha(im2, bit_depth)
    if bit_depth > 8:
        notes.append(f'This is a {bit_depth}-bit image. Upscaling works in 8-bit, so very fine tonal steps are reduced; 16-bit '
                     'output files keep the 8-bit result.')
    rgb, icc_state = _to_srgb(base, icc, notes)
    if alpha is not None and alpha.getextrema() == (255, 255):
        alpha = None
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    save_png_atomic(rgb, out_dir / 'source.png', compress_level=1)
    if alpha is not None:
        save_png_atomic(alpha, out_dir / 'alpha.png', compress_level=1)
    exif_b = None
    if exif is not None:
        try:
            exif_b = filtered_exif_bytes(exif)
        except (OSError, ValueError, TypeError, struct.error, KeyError) as e:
            notes.append('The camera details could not be copied to the result.')
            exif_b = None
    if exif_b:
        with open(out_dir / 'exif.bin', 'wb') as f:
            f.write(exif_b)
    write_preview(rgb, alpha, out_dir / 'thumb.jpg', THUMB_SIDE, 85)
    write_preview(rgb, alpha, out_dir / 'proxy.jpg', PROXY_SIDE, 90)
    if alpha is not None:
        rgba = rgb.copy()
        rgba.putalpha(alpha)              
        write_previews_rgba(rgba, out_dir / 'proxy.png', out_dir / 'thumb.png')
    return {'width': rgb.width, 'height': rgb.height, 'format': fmt, 'mode': mode_in, 'bit_depth': bit_depth,
            'alpha': alpha is not None, 'icc': icc_state, 'exif': bool(exif_b), 'orientation': orientation or 1, 'notes': notes}


def _split_colour_alpha(im, bit_depth):
    mode = im.mode
    if mode == 'P':
        im = im.convert('RGBA' if 'transparency' in im.info else 'RGB')
    elif mode == 'PA':
        im = im.convert('RGBA')
    elif mode in ('RGBa', 'La'):
        im = im.convert('RGBA' if mode == 'RGBa' else 'LA')
    elif mode == '1':
        im = im.convert('L')
    mode = im.mode
    alpha = None
    if mode == 'RGBA':
        alpha = im.getchannel('A')
        im = im.convert('RGB')
    elif mode == 'LA':
        alpha = im.getchannel('A')
        im = im.getchannel('L')
    elif mode.startswith('I') or mode == 'F':
        im = _to_8bit_single(im, bit_depth)
    return im, alpha


def _to_srgb(base, icc, notes):
    if icc:
        try:
            src = ImageCms.ImageCmsProfile(io.BytesIO(icc))
            out = ImageCms.profileToProfile(base, src, srgb_profile(), renderingIntent=ImageCms.Intent.PERCEPTUAL,
                                            outputMode='RGB')
            if out is None:
                raise ValueError('no image returned')
            return out, 'converted'
        except (ImageCms.PyCMSError, OSError, ValueError, TypeError) as e:
            notes.append('The colour profile in this file could not be used, so colours in the result may differ slightly.')
            return _naive_rgb(base), 'failed'
    return _naive_rgb(base), 'none'


def _naive_rgb(im):
    if im.mode == 'RGB':
        return im
    if im.mode == 'LAB':
        lab = ImageCms.createProfile('LAB')
        return ImageCms.profileToProfile(im, lab, srgb_profile(), outputMode='RGB')
    return im.convert('RGB')


def write_preview(rgb, alpha, path, long_side, quality):
    im = rgb
    if alpha is not None:
        bg = Image.new('RGB', rgb.size, MATTE)
        bg.paste(rgb, (0, 0), alpha)
        im = bg
    else:
        im = rgb.copy()
    im.thumbnail((long_side, long_side), Image.LANCZOS)
    save_atomic(im, path, 'JPEG', quality=quality)


def preview_size(w, h, long_side):
    """The size Image.thumbnail((long_side, long_side)) gives a w x h image (Pillow's own rounding, which keeps the aspect
    closest), so a PNG preview made from the proxy has exactly the size of the .jpg made from the full image."""
    if w <= long_side and h <= long_side:
        return w, h
    aspect = w / h

    def closest(number, key):
        return max(min(math.floor(number), math.ceil(number), key=key), 1)
    x = y = long_side
    if x / y >= aspect:
        x = closest(y * aspect, key=lambda n: abs(aspect - n / y))
    else:
        y = closest(x / aspect, key=lambda n: 0 if n == 0 else abs(aspect - x / n))
    return x, y


def write_previews_rgba(rgba, proxy_path, thumb_path):
    """RGBA display copies that keep transparency (L23): proxy.png (long side PROXY_SIDE) from the full image and thumb.png
    (THUMB_SIDE) from the proxy, at the sizes of the matching .jpg copies. Pillow resizes RGBA premultiplied, so the colour
    under fully transparent pixels never bleeds into the edges. `rgba` may be a read-only view of a buffer: it is not changed."""
    w, h = rgba.size
    size = preview_size(w, h, PROXY_SIDE)
    proxy = rgba if size == (w, h) else rgba.resize(size, Image.LANCZOS, reducing_gap=2.0)
    save_atomic(proxy, proxy_path, 'PNG', compress_level=PREVIEW_PNG_LEVEL)
    size = preview_size(w, h, THUMB_SIDE)
    thumb = proxy if size == proxy.size else proxy.resize(size, Image.LANCZOS, reducing_gap=2.0)
    save_atomic(thumb, thumb_path, 'PNG', compress_level=PREVIEW_PNG_LEVEL)


def write_result_views_rgba(d, rgb, alpha):
    """Viewer copies of a result with transparency (L23), into folder `d`: view-alpha.png (the full-size alpha), view.jpg (the
    colour as rendered, q95 4:4:4, not flattened), proxy.png and thumb.png (RGBA). rgb: uint8 HxWx3, alpha: uint8 HxW; neither
    is changed. The alpha is written first, so an unflattened view.jpg is never on disk without it.

    Why not one full-size RGBA PNG: on a 150 MP result it took 4.4-6.7 s at level 1 (11 s at level 6) and 280-480 MB on disk
    (178-320 MB at level 6), against 0.7 s and 48-65 MB for this pair, and decoding it for the 100% view took 2-3 s against
    0.6-0.8 s. Viewer copies are never pruned, so the size counts per result.
    Memory: one RGBA buffer (4 bytes per pixel, the size of one Pillow RGB image) shared by the JPEG (as RGBX) and the
    previews; the premultiplied resize adds one transient copy. Less than the flattened v2 path, which held three."""
    h, w = alpha.shape
    if rgb.shape[:2] != (h, w):
        raise ValueError(f'alpha {w}x{h} does not match the colour {rgb.shape[1]}x{rgb.shape[0]}')
    save_png_atomic(Image.fromarray(np.ascontiguousarray(alpha)), Path(d) / 'view-alpha.png',
                    compress_level=VIEW_ALPHA_PNG_LEVEL)
    buf = np.empty((h, w, 4), np.uint8)
    buf[..., :3] = rgb
    buf[..., 3] = alpha
    save_atomic(Image.frombuffer('RGBX', (w, h), buf, 'raw', 'RGBX', 0, 1), Path(d) / 'view.jpg', 'JPEG', quality=95,
                subsampling=0)
    write_previews_rgba(Image.frombuffer('RGBA', (w, h), buf, 'raw', 'RGBA', 0, 1), Path(d) / 'proxy.png',
                        Path(d) / 'thumb.png')


def save_atomic(im, path, fmt, **kw):
    """Encode to a temp file beside `path`, fsync it, then replace `path` (a crash leaves the old file or the new one, never a
    renamed file with missing data)."""
    path = Path(path)
    tmp = path.with_name(f'{path.name}.{secrets.token_hex(3)}.tmp')
    try:
        with open(tmp, 'wb') as f:
            im.save(f, fmt, **kw)
            f.flush()
            os.fsync(f.fileno())
        replace_with_retry(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def save_png_atomic(im_or_arr, path, compress_level=1):
    im = Image.fromarray(im_or_arr) if isinstance(im_or_arr, np.ndarray) else im_or_arr
    save_atomic(im, path, 'PNG', compress_level=compress_level)


def load_rgb(path):
    with Image.open(path) as im:
        if im.mode != 'RGB':
            im = im.convert('RGB')
        return np.asarray(im, dtype=np.uint8).copy()


def load_alpha(path):
    with Image.open(path) as im:
        return im.convert('L').copy()


def pad_reflect(arr, size):
    """Pad an HxWxC array on the right and bottom to size=(w, h) by reflection (numpy 'reflect': the edge pixel is not
    repeated). The planner pads by less than one pad unit and inputs are at least 64 px, so reflection always fits."""
    pw, ph = int(size[0]), int(size[1])
    h, w = arr.shape[:2]
    if pw < w or ph < h:
        raise ValueError(f'padded size {pw}x{ph} is smaller than the image {w}x{h}')
    if (pw, ph) == (w, h):
        return arr
    if pw - w >= w or ph - h >= h:
        raise ValueError(f'padding {pw - w}x{ph - h} px is too large to reflect a {w}x{h} image')
    pad = ((0, ph - h), (0, pw - w)) + ((0, 0),) * (arr.ndim - 2)
    return np.pad(arr, pad, mode='reflect')


def crop(arr, size):
    ow, oh = int(size[0]), int(size[1])
    if arr.shape[1] < ow or arr.shape[0] < oh:
        raise ValueError(f'cannot crop {arr.shape[1]}x{arr.shape[0]} to {ow}x{oh}')
    return np.ascontiguousarray(arr[:oh, :ow])


def _png_chunk(tag, data):
    return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data) & 0xFFFFFFFF)


def _strip16(arr, alpha, y0, y1):
    """Rows y0:y1 as uint16 HxWxC: colour (uint8 is widened exactly, x257) plus the alpha channel when given. Only this strip
    is converted, so a 268 MP output never needs a full-frame 16-bit copy."""
    rows = arr[y0:y1]
    if alpha is not None:
        rows = np.dstack([rows, alpha[y0:y1]])
    if rows.dtype == np.uint8:
        return rows.astype(np.uint16) * np.uint16(257)
    return rows


def _shape16(arr, alpha, who):
    if arr.ndim != 3 or arr.dtype not in (np.uint8, np.uint16):
        raise ValueError(f'{who} needs uint8 or uint16 HxWx3 or HxWx4')
    h, w, c = arr.shape
    if alpha is not None:
        if alpha.shape != (h, w) or alpha.dtype != arr.dtype:
            raise ValueError(f'{who}: alpha must be HxW of the same type as the colour')
        c += 1
    if c not in (3, 4):
        raise ValueError(f'{who} needs uint8 or uint16 HxWx3 or HxWx4')
    return h, w, c


def write_png16(path, arr16, icc=None, exif=None, level=6, alpha=None):
    """16-bit RGB / RGBA PNG, 'Up' row filter, streamed zlib; iCCP and eXIf chunks when given. `arr16` is uint16 HxWx3|4, or
    the uint8 result (widened x257 per 128-row strip); `alpha` (HxW, same type) is interleaved per strip."""
    h, w, c = _shape16(arr16, alpha, 'write_png16')
    with open(path, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n')
        f.write(_png_chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 16, 2 if c == 3 else 6, 0, 0, 0)))
        if icc:
            f.write(_png_chunk(b'iCCP', b'sRGB\x00\x00' + zlib.compress(icc)))
        if exif:
            f.write(_png_chunk(b'eXIf', exif[6:] if exif.startswith(b'Exif\x00\x00') else exif))
        comp = zlib.compressobj(level)
        row_bytes = w * c * 2
        prev = np.zeros(row_bytes, np.uint8)
        pending = []
        for y0 in range(0, h, 128):
            rows = np.ascontiguousarray(_strip16(arr16, alpha, y0, y0 + 128).astype('>u2')).view(np.uint8).reshape(-1, row_bytes)
            up = np.vstack([prev[None], rows[:-1]])
            filt = (rows - up).astype(np.uint8)          
            prev = rows[-1].copy()
            data = np.hstack([np.full((rows.shape[0], 1), 2, np.uint8), filt]).tobytes()
            out = comp.compress(data)
            if out:
                pending.append(out)
            if sum(map(len, pending)) > (4 << 20):
                f.write(_png_chunk(b'IDAT', b''.join(pending)))
                pending = []
        pending.append(comp.flush())
        f.write(_png_chunk(b'IDAT', b''.join(pending)))
        f.write(_png_chunk(b'IEND', b''))
        f.flush()
        os.fsync(f.fileno())


def _tiff_exif_ifd(exif_bytes, offset):
    """Exif sub-IFD (relocated to `offset`) from 'Exif\\0\\0'+TIFF bytes, plus IFD0 text tags. Returns (ifd_bytes, ifd0_tags)."""
    from PIL import TiffImagePlugin
    ex = Image.Exif()
    ex.load(exif_bytes)
    ifd0 = {t: ex[t] for t in (270, 271, 272, 306, 315, 33432) if t in ex and isinstance(ex[t], str)}
    sub = {k: v for k, v in dict(ex.get_ifd(0x8769)).items() if k not in EXIF_SUB_DROP} if 0x8769 in ex else {}
    if not sub:
        return None, ifd0
    d = TiffImagePlugin.ImageFileDirectory_v2(prefix=b'II')
    for k, v in sub.items():
        d[k] = v
    return d.tobytes(offset), ifd0


def write_tiff16(path, arr16, icc=None, exif=None, software='Creative Upscaler', alpha=None):
    """16-bit RGB / RGBA baseline TIFF: Adobe Deflate strips with horizontal predictor, ICC tag, unassociated alpha, EXIF
    (Exif sub-IFD + IFD0 text tags). Input as for write_png16 (uint16, or uint8 widened per strip; optional alpha).
    Returns 'copied', 'basic' (IFD0 text only) or 'none' for the EXIF that was written."""
    h, w, c = _shape16(arr16, alpha, 'write_tiff16')
    rows_per_strip = max(1, min(h, (1 << 20) // (w * c * 2)))
    strips = []
    for y0 in range(0, h, rows_per_strip):
        a = _strip16(arr16, alpha, y0, y0 + rows_per_strip).astype(np.int32)
        d = a.copy()
        d[:, 1:, :] = a[:, 1:, :] - a[:, :-1, :]        
        strips.append(zlib.compress((d & 0xFFFF).astype('<u2').tobytes(), 6))
    exif_state = 'none'
    with open(path, 'wb') as f:
        f.write(b'II*\x00' + struct.pack('<I', 0))
        offsets, counts = [], []
        for s in strips:
            offsets.append(f.tell())
            counts.append(len(s))
            f.write(s)
            if f.tell() % 2:
                f.write(b'\x00')
        exif_off, ifd0_text = None, {}
        if exif:
            try:
                pos = f.tell()
                sub_bytes, ifd0_text = _tiff_exif_ifd(exif, pos)
                if sub_bytes:
                    f.write(sub_bytes)
                    exif_off = pos
                    if f.tell() % 2:
                        f.write(b'\x00')
                exif_state = 'copied' if exif_off else ('basic' if ifd0_text else 'none')
            except (ValueError, TypeError, KeyError, struct.error, OSError):
                f.seek(pos)
                f.truncate()
                exif_off, ifd0_text, exif_state = None, {}, 'none'
        
        sh = lambda *v: struct.pack(f'<{len(v)}H', *v)
        lo = lambda *v: struct.pack(f'<{len(v)}I', *v)
        ascii_ = lambda s: s.encode('ascii', 'replace') + b'\x00'
        e = [(256, 4, 1, lo(w)), (257, 4, 1, lo(h)), (258, 3, c, sh(*([16] * c))), (259, 3, 1, sh(8)), (262, 3, 1, sh(2)),
             (273, 4, len(offsets), lo(*offsets)), (277, 3, 1, sh(c)), (278, 4, 1, lo(rows_per_strip)),
             (279, 4, len(counts), lo(*counts)), (284, 3, 1, sh(1)), (305, 2, len(ascii_(software)), ascii_(software)),
             (317, 3, 1, sh(2)), (339, 3, c, sh(*([1] * c)))]
        if c == 4:
            e.append((338, 3, 1, sh(2)))
        for t, s in ifd0_text.items():
            b = ascii_(s)
            e.append((t, 2, len(b), b))
        if exif_off:
            e.append((34665, 4, 1, lo(exif_off)))
        if icc:
            e.append((34675, 7, len(icc), icc))
        e.sort(key=lambda x: x[0])
        ifd_pos = f.tell()
        extra_pos = ifd_pos + 2 + 12 * len(e) + 4
        head, extra = [struct.pack('<H', len(e))], []
        for tag, typ, count, val in e:
            if len(val) <= 4:
                head.append(struct.pack('<HHI', tag, typ, count) + val.ljust(4, b'\x00'))
            else:
                off = extra_pos + sum(len(x) for x in extra)
                head.append(struct.pack('<HHII', tag, typ, count, off))
                extra.append(val + (b'\x00' if len(val) % 2 else b''))
        head.append(struct.pack('<I', 0))
        f.write(b''.join(head) + b''.join(extra))
        f.seek(4)
        f.write(struct.pack('<I', ifd_pos))
        f.flush()
        os.fsync(f.fileno())
    return exif_state


def encode(path, rgb, alpha, fmt, exif=None, software='Creative Upscaler'):
    """Write the final image (fsynced). rgb: uint8 HxWx3; alpha: uint8 HxW or None. Returns facts for the sidecar."""
    if fmt not in OUTPUT_EXT:
        raise OutputError(f'Unknown output format {fmt}')
    icc = srgb_icc_bytes()
    info = {'format': fmt, 'icc': 'sRGB', 'alpha': 'none', 'exif': 'none', 'bits': 16 if fmt in ('png16', 'tiff16') else 8}
    keep_alpha = alpha is not None and fmt != 'jpeg'
    if alpha is not None:
        info['alpha'] = 'kept' if keep_alpha else 'dropped (JPEG has no transparency)'
    if fmt == 'png8':
        arr = np.dstack([rgb, alpha]) if keep_alpha else rgb
        Image.fromarray(arr).save(path, 'PNG', icc_profile=icc, exif=exif or b'', compress_level=6)
        fsync_file(path)
        info['exif'] = 'copied' if exif else 'none'
    elif fmt == 'jpeg':
        Image.fromarray(rgb).save(path, 'JPEG', quality=95, subsampling=0, icc_profile=icc, exif=exif or b'')
        fsync_file(path)
        info['exif'] = 'copied' if exif else 'none'
    elif fmt == 'png16':
        write_png16(path, rgb, icc=icc, exif=exif, alpha=alpha if keep_alpha else None)
        info['exif'] = 'copied' if exif else 'none'
    else:
        info['exif'] = write_tiff16(path, rgb, icc=icc, exif=exif, software=software, alpha=alpha if keep_alpha else None)
    return info


def safe_stem(name, limit=150):
    base = str(name).replace(chr(92), '/').rsplit('/', 1)[-1]   
    stem = (base.rsplit('.', 1)[0] if '.' in base[1:] else base).strip() or 'image'
    stem = ''.join('_' if ch in '<>:"/\\|?*' or ord(ch) < 32 else ch for ch in stem).rstrip('. ')
    return (stem or 'image')[:limit]


def output_candidates(out_dir, stem, factor, ext, limit=10000, suffix=''):
    """(output path, sidecar path) pairs: <stem>_cu<F>x<suffix><ext> + .json, then _2, _3, ... skipping any pair already in
    use. suffix: '_fast' for a Fast result (preview design: a draft and its final sit side by side, and never share a name)."""
    base = f'{stem}_cu{factor}x{suffix}'
    for n in range(1, limit + 1):
        name = base if n == 1 else f'{base}_{n}'
        out, side = Path(out_dir) / (name + ext), Path(out_dir) / (name + '.json')
        if not out.exists() and not side.exists():
            yield out, side
    raise OutputError(f'No free output name for {base} in {out_dir}')


def no_overwrite_rename(src, dst):
    """Rename that refuses to replace an existing file (Windows os.rename semantics; elsewhere a hard link + unlink)."""
    if os.name == 'nt':
        os.rename(src, dst)
    else:
        os.link(src, dst)
        os.unlink(src)


def _write_tmp(path, data):
    with open(path, 'wb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())


def _unlink_quiet(path, log_fn=None):
    """Remove a temp file; a failure (share gone) is reported through log_fn, never raised over the real outcome."""
    try:
        if path is not None and Path(path).exists():
            Path(path).unlink()
    except OSError as e:
        if log_fn is not None:
            log_fn(f'Temporary file {path} could not be removed: {e}')


def sidecar_candidates(output):
    """Where the sidecar of `output` may go: `<name>.json` beside it, else `<name><ext>.json` (only under a race)."""
    out = Path(output)
    return [out.with_suffix('.json'), out.with_name(out.name + '.json')]


def _rename_sidecar(tmp_side, output):
    for side in sidecar_candidates(output):
        try:
            no_overwrite_rename(tmp_side, side)
            return side
        except FileExistsError:
            continue
    raise OutputError(f'No free sidecar name for {Path(output).name}')


def write_sidecar(output, data, log_fn=None):
    """(Re)write the sidecar of an output that is already published; never overwrites an existing file."""
    out = Path(output)
    tmp_side = out.with_name(f'.{out.stem}.json.{secrets.token_hex(3)}.tmp')
    try:
        _write_tmp(tmp_side, data)
        side = _rename_sidecar(tmp_side, out)
        tmp_side = None
        return side
    finally:
        _unlink_quiet(tmp_side, log_fn)


def reserve_and_publish(tmp_output, out_dir, stem, factor, ext, sidecar_bytes_fn, on_reserved=None, log_fn=None, suffix=''):
    """Publish a finished, fsynced temp file under the first free name, with its sidecar; never overwrites anything.
    sidecar_bytes_fn(output_path) -> bytes. on_reserved(output_path, sidecar_bytes) is called just before the output is renamed
    into place (the caller records it, so a crash in between is recognised at the next start). Returns (output, sidecar).
    Raises SidecarPending when the output is in place but the sidecar could not be renamed (retry with write_sidecar)."""
    for out, side in output_candidates(out_dir, stem, factor, ext, suffix=suffix):
        data = sidecar_bytes_fn(out)
        tmp_side = side.with_name(f'.{side.name}.{secrets.token_hex(3)}.tmp')
        try:
            _write_tmp(tmp_side, data)
            if on_reserved is not None:
                on_reserved(out, data)
            try:
                no_overwrite_rename(tmp_output, out)
            except FileExistsError:
                continue
            try:
                side = _rename_sidecar(tmp_side, out)
                tmp_side = None
            except (OSError, OutputError) as e:
                raise SidecarPending(out, data, e)
            return out, side
        finally:
            _unlink_quiet(tmp_side, log_fn)
    raise OutputError('No free output name')


class DecodedCache:
    """Keeps the last few decoded images in memory (keyed by path + mtime) so 1:1 region requests are fast.

    Single flight: concurrent requests for the same file wait for one decode instead of each decoding it (a pan in the viewer
    fires several requests while the first decode of a large result is still running). At most `max_decodes` files are decoded
    at once, and entries unused for `idle_s` seconds are dropped (a full-size result can be ~800 MB decoded).

    With `alpha_path` the entry is the colour file with that alpha put back (RGBA, L23): one entry per picture, the same size as
    the colour alone (Pillow keeps RGB in 4 bytes per pixel, so the alpha fills the spare byte in place)."""

    def __init__(self, size=2, max_decodes=2, idle_s=300.0):
        self.size = size
        self.idle_s = idle_s
        self._d = OrderedDict()          
        self._lock = threading.Lock()
        self._inflight = {}              
        self._decode_slots = threading.BoundedSemaphore(max_decodes)
        self.decodes = 0                 

    def _evict_idle_locked(self, now):
        for k in [k for k, (_, used) in self._d.items() if now - used > self.idle_s]:
            del self._d[k]

    def evict_idle(self):
        with self._lock:
            self._evict_idle_locked(time.monotonic())

    def get(self, path, alpha_path=None):
        path = Path(path)
        key = (str(path), path.stat().st_mtime_ns)
        if alpha_path is not None:
            alpha_path = Path(alpha_path)
            key += (str(alpha_path), alpha_path.stat().st_mtime_ns)
        with self._lock:
            now = time.monotonic()
            self._evict_idle_locked(now)
            if key in self._d:
                img = self._d[key][0]
                self._d[key] = (img, now)
                self._d.move_to_end(key)
                return img
            flight = self._inflight.get(key)
            owner = flight is None
            if owner:
                flight = self._inflight[key] = [threading.Event(), None, None]
        if not owner:
            flight[0].wait()
            if flight[2] is not None:
                raise flight[2]
            return flight[1]
        try:
            with self._decode_slots:
                self.decodes += 1
                with Image.open(path) as im:
                    im.load()
                    img = im.copy()
                if alpha_path is not None:
                    img = with_alpha(img, alpha_path)
            flight[1] = img
            with self._lock:
                self._d[key] = (img, time.monotonic())
                while len(self._d) > self.size:
                    self._d.popitem(last=False)
            return img
        except BaseException as e:
            flight[2] = e
            raise
        finally:
            with self._lock:
                self._inflight.pop(key, None)
            flight[0].set()


def with_alpha(img, alpha_path):
    """The colour image `img` with the alpha file put back as its fourth channel (RGBA). Sizes must match."""
    with Image.open(alpha_path) as am:
        am.load()
        a = am if am.mode == 'L' else am.convert('L')
        if a.size != img.size:
            raise ValueError(f'{Path(alpha_path).name} is {a.size[0]}x{a.size[1]}, the picture {img.size[0]}x{img.size[1]}')
        if img.mode != 'RGB':
            img = img.convert('RGB')
        img.putalpha(a)                   
    return img


def region_png(img, x, y, w, h, max_side=4096):
    """1:1 crop of the requested rectangle intersected with the image, as PNG bytes (8-bit; 16-bit sources are reduced for
    display; an RGBA image gives an RGBA crop). Returns (png, (x, y, w, h) of the part returned); the PNG has exactly that size."""
    if w <= 0 or h <= 0 or w > max_side or h > max_side:
        raise ValueError(f'Region width and height must be 1 to {max_side} px')
    x0, y0 = max(0, int(x)), max(0, int(y))
    x1, y1 = min(img.width, int(x) + int(w)), min(img.height, int(y) + int(h))
    if x1 <= x0 or y1 <= y0:
        raise ValueError('The region is outside the image')
    part = img.crop((x0, y0, x1, y1))
    if part.mode not in ('RGB', 'RGBA', 'L'):
        part = part.convert('RGBA' if 'A' in part.mode else 'RGB')
    buf = io.BytesIO()
    part.save(buf, 'PNG', compress_level=1)
    return buf.getvalue(), (x0, y0, x1 - x0, y1 - y0)


SIZED_MAX_SIDE = 8192           
SIZED_JPEG_QUALITY = 95         
SIZED_PNG_LEVEL = 3             


def sized_size(iw, ih, w, h):
    """The size a `w x h` ask is served at for an `iw x ih` picture: exactly `w x h` when the picture is at least that large,
    else the ask shrunk (keeping its shape) until it fits inside the picture, so a copy is never larger than the picture it
    is made from and an ask of the picture's own shape that is too large is served at the picture's own size."""
    k = min(1.0, iw / float(w), ih / float(h))
    if k >= 1.0:
        return int(w), int(h)
    return max(1, min(int(iw), int(round(w * k)))), max(1, min(int(ih), int(round(h * k))))


def sized_copy(img, w, h):
    """`img` (a decoded picture, RGB or RGBA) resampled from its own pixels to the size `sized_size` gives for `w x h`.
    Returns (bytes, content type, (width, height)): JPEG (quality 95, 4:4:4) for an opaque picture, RGBA PNG for one with
    transparency. Lanczos, after Pillow's whole-number box reduction where the picture is more than three times larger
    (reducing_gap 3: indistinguishable from the one-step filter, and several times quicker on a 150 MP result). Pillow
    resizes RGBA premultiplied, so the colour under fully transparent pixels never bleeds into the edges. `img` is not
    changed."""
    size = sized_size(img.width, img.height, w, h)
    if img.mode not in ('RGB', 'RGBA'):
        img = img.convert('RGBA' if 'A' in img.mode else 'RGB')
    out = img if size == img.size else img.resize(size, Image.LANCZOS, reducing_gap=3.0)
    buf = io.BytesIO()
    if out.mode == 'RGBA':
        out.save(buf, 'PNG', compress_level=SIZED_PNG_LEVEL)
        return buf.getvalue(), 'image/png', size
    out.save(buf, 'JPEG', quality=SIZED_JPEG_QUALITY, subsampling=0)
    return buf.getvalue(), 'image/jpeg', size


class SizedCopies:
    """Display copies at the drawn size, kept in memory (GET /api/media/<id>/proxy?w=&h=; preview design).

    The viewer asks for the picture at exactly the size it draws it at Fit, in device pixels, 150 ms after the window stops
    changing size, so a picture needs one or two sizes in a session and a handful when the window is resized. Bounds: at most
    `per_picture` sizes for one picture (the least recently used goes first) and `max_bytes` for all pictures together
    (again least recently used first); a copy larger than half of `max_bytes` is served and not kept. Nothing is written to
    disk, so there is nothing to clean up, to migrate or to go stale: a copy is keyed by the file it was made from and that
    file's modification time, and a restart makes each one again on demand (about a second for a 37 MP result, most of it the
    decode, which the 1:1 region route then finds already done in `decoded`).
    Single flight: the two layers of the viewer, or a retry, asking for the same copy wait for one resample; at most
    `max_jobs` resamples run at once (the person may be working on this machine)."""

    def __init__(self, decoded, max_bytes=128 << 20, per_picture=6, max_jobs=2):
        self.decoded = decoded
        self.max_bytes = int(max_bytes)
        self.per_picture = int(per_picture)
        self._d = OrderedDict()          
        self._lock = threading.Lock()
        self._inflight = {}              
        self._slots = threading.BoundedSemaphore(max_jobs)
        self.made = 0                    

    def bytes_held(self):
        with self._lock:
            return sum(len(v[0]) for v in self._d.values())

    def _trim_locked(self, picture):
        mine = [k for k in self._d if k[0] == picture]
        for k in mine[:max(0, len(mine) - self.per_picture)]:
            del self._d[k]
        total = sum(len(v[0]) for v in self._d.values())
        while self._d and total > self.max_bytes:
            _, v = self._d.popitem(last=False)
            total -= len(v[0])

    def get(self, path, alpha_path, w, h):
        """(bytes, content type, (served w, h), (picture w, h)) for the picture in `path` (with `alpha_path` put back when
        given) at the size asked. ValueError when w or h is not 1..SIZED_MAX_SIDE."""
        w, h = int(w), int(h)
        if not (1 <= w <= SIZED_MAX_SIDE and 1 <= h <= SIZED_MAX_SIDE):
            raise ValueError(f'w and h must be 1 to {SIZED_MAX_SIDE} px')
        path = Path(path)
        picture = (str(path), path.stat().st_mtime_ns)
        if alpha_path is not None:
            alpha_path = Path(alpha_path)
            picture += (str(alpha_path), alpha_path.stat().st_mtime_ns)
        with Image.open(path) as head:                      
            own = head.size
        size = sized_size(own[0], own[1], w, h)
        key = (picture,) + size
        with self._lock:
            hit = self._d.get(key)
            if hit is not None:
                self._d.move_to_end(key)
                return hit
            flight = self._inflight.get(key)
            owner = flight is None
            if owner:
                flight = self._inflight[key] = [threading.Event(), None, None]
        if not owner:
            flight[0].wait()
            if flight[2] is not None:
                raise flight[2]
            return flight[1]
        try:
            with self._slots:
                img = self.decoded.get(path, alpha_path)
                data, ctype, served = sized_copy(img, size[0], size[1])
                self.made += 1
            value = flight[1] = (data, ctype, served, (img.width, img.height))
            with self._lock:
                if len(data) <= self.max_bytes // 2:
                    self._d[key] = value
                    self._trim_locked(picture)
            return value
        except BaseException as e:
            flight[2] = e
            raise
        finally:
            with self._lock:
                self._inflight.pop(key, None)
            flight[0].set()


def _max_filter_square(a, r):
    """Separable square dilation of a 2-D uint8 array by r px (2r+1 window), numpy shifts (fast for small r)."""
    out = a
    for axis in (0, 1):
        src, acc = out, out.copy()
        n = src.shape[axis]
        for d in range(1, min(r, n - 1) + 1):
            fwd = [slice(None)] * 2
            bwd = [slice(None)] * 2
            fwd[axis], bwd[axis] = slice(d, None), slice(None, n - d)
            np.maximum(acc[tuple(bwd)], src[tuple(fwd)], out=acc[tuple(bwd)])
            np.maximum(acc[tuple(fwd)], src[tuple(bwd)], out=acc[tuple(fwd)])
        out = acc
    return out


def mask_proxy(mask_l, long_side=PROXY_SIDE):
    """The engine's exact protect gate (soft, 0-255) resized to display-proxy resolution; values kept, nothing re-thresholded."""
    scale = min(1.0, long_side / max(mask_l.size))
    if scale < 1.0:
        mask_l = mask_l.resize((max(1, round(mask_l.width * scale)), max(1, round(mask_l.height * scale))), Image.BILINEAR)
    return mask_l.convert('L')


def mask_postprocess(mask_l, dilate=12, feather=4.0, long_side=PROXY_SIDE):
    """Preview of the finish's protect gate at display-proxy resolution: binarise at .5, dilate and feather (both scaled to the
    preview size). A square dilation stands in for the finish's own; it is a preview, the render applies the exact gate."""
    from PIL import ImageFilter
    scale = min(1.0, long_side / max(mask_l.size))
    m = mask_l
    if scale < 1.0:
        m = m.resize((max(1, round(m.width * scale)), max(1, round(m.height * scale))), Image.BILINEAR)
    a = np.where(np.asarray(m, dtype=np.uint8) >= 128, 255, 0).astype(np.uint8)
    r = int(round(dilate * scale))
    if dilate > 0 and r > 0:
        a = _max_filter_square(a, r)
    m = Image.fromarray(a, 'L')
    if feather > 0:
        m = m.filter(ImageFilter.GaussianBlur(float(feather) * scale))
    return m
