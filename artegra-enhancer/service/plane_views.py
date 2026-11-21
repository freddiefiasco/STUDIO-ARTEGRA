"""Viewer copies of a Large-image result, made from its plane (engine design section 2.10, B13; gate G8).

A Large-image result is kept as its raw uint8 plane (result.plane, and alpha.plane when the input has transparency) in the
result's viewer folder, so nothing here decodes a whole result:
- the proxy and thumb: proxy.jpg and thumb.jpg for an opaque result; proxy.png and thumb.png (RGBA) for one with
  transparency, as the Classic engine's results with transparency have them (service/images.py write_previews_rgba);
- sized copies (GET /api/media/<id>/proxy?w=&h=, the picture at the size the viewer draws it): made once per result and
  size by the streamed T1 Lanczos downscale, kept on disk in the result folder's sized/ folder (at most PER_ITEM sizes; the
  least recently used goes first), and dropped with the folder, when a new result replaces the item's, or by drop();
- regions stay plane_io.region_png: lossless crops of at most 4096 x 4096 px.

Exactness. Every copy holds the bytes of Pillow's own whole-image Image.resize(size, LANCZOS) of the same picture. Pillow
resizes an RGBA picture premultiplied: it converts to RGBa once, runs both passes, and converts back once. Banding
lanczos_bands.resize over four channels would convert around each pass instead (2,715 of 600,000 values differed on a
synthetic card), so an RGBA copy is resampled here in mode RGBa, by row bands and column strips (the T1 order), and
converted back once at the end. Pillow also chooses its pass order (vertical_first): both orders are kept here.

The Classic engine's copies are unchanged (service/images.py): its proxy.png is made with reducing_gap 2.0 and its sized
copies with reducing_gap 3.0, both from the decoded picture; these use the exact Lanczos from the plane, which looks the same
zoomed out. The sized copy is encoded as the Classic engine's is: JPEG quality 95 with 4:4:4 chroma, or an RGBA PNG."""
import io
import os
import secrets
import shutil
import threading
from pathlib import Path

import numpy as np

from engine import bands as _bands
from engine import lanczos_bands, planes
from service import images
from service.util import replace_with_retry

RESULT_PLANE = 'result.plane'
ALPHA_PLANE = 'alpha.plane'
PLANE_FILES = (RESULT_PLANE, 'proxy.jpg', 'thumb.jpg')
PLANE_FILES_ALPHA = (RESULT_PLANE, ALPHA_PLANE, 'proxy.png', 'thumb.png')
SIZED_DIR = 'sized'
PER_ITEM = 6
COPY_VERSION = 'v1'                 # part of every cached copy's name: a change of method makes every copy again


class WholeDecodeRefused(ValueError):
    """A whole decode of a Large-image result was asked for; its viewer uses the plane's proxy and region routes."""


def is_plane_result(folder):
    return (Path(folder) / RESULT_PLANE).is_file()


def open_planes(folder):
    """(result plane, alpha plane or None) of a Large-image result's viewer folder. PlaneError when it has none."""
    folder = Path(folder)
    p = planes.Plane.open(folder / RESULT_PLANE)
    a = planes.Plane.open(folder / ALPHA_PLANE) if (folder / ALPHA_PLANE).is_file() else None
    if a is not None and a.shape != p.shape[:2] + (1,):
        raise planes.PlaneError(f'{ALPHA_PLANE} is {a.shape}, the result {p.shape}')
    return p, a


def views_ready(folder):
    """True when a Large-image result's viewer folder holds its plane and the proxy and thumb for its kind."""
    folder = Path(folder)
    if not is_plane_result(folder):
        return False
    names = PLANE_FILES_ALPHA if (folder / ALPHA_PLANE).is_file() else PLANE_FILES
    return all((folder / n).is_file() for n in names)


# --- the exact resample -------------------------------------------------------------------------------------------------

def _tmp_plane(folder, shape):
    Path(folder).mkdir(parents=True, exist_ok=True)
    return planes.Plane.create(Path(folder) / f'.lanczos-{secrets.token_hex(6)}.tmp.plane', shape, 'u8', producer='viewer')


def _unlink(path):
    try:
        os.unlink(path)
    except OSError:
        pass


def _image(arr, mode):
    from PIL import Image
    a = np.ascontiguousarray(arr)
    return Image.frombuffer(mode, (a.shape[1], a.shape[0]), a, 'raw', mode, 0, 1)


def _premultiplied(rgb, a):
    """Pillow's own RGBA -> RGBa conversion of a block of rows or columns (per pixel, so any block gives the same values)."""
    return np.asarray(_image(np.concatenate([rgb, a], axis=2), 'RGBA').convert('RGBa'))


class _Premultiplied:
    """A result plane and its alpha plane read as RGBa (premultiplied) rows and column strips."""

    def __init__(self, plane, alpha):
        self.plane, self.alpha = plane, alpha
        self.shape = plane.shape[:2] + (4,)

    def read_rows(self, y0, y1):
        return _premultiplied(self.plane.read_rows(y0, y1), self.alpha.read_rows(y0, y1))

    def read_cols(self, x0, x1):
        return _premultiplied(self.plane.read_cols(x0, x1), self.alpha.read_cols(x0, x1))


def vertical_first(w, h, w2, h2):
    """Pillow's pass order. PIL/Image.py (12.3.0) Image.resize runs the vertical pass first, then the horizontal one, when
    the picture is more than 100 times taller than it is wide and its height shrinks; otherwise libImaging/Resample.c runs
    the horizontal pass first (engine/lanczos_bands.py's order). A Large-image result (over 150 MP, sides of at most
    32,000 px) is never that tall; a tall strip is, and the copies of it must still hold Pillow's values."""
    return h > w * 100 and h2 < h


def _resample(src, size, mode, tmp_dir):
    """Lanczos-resample `src` (read_rows / read_cols; H x W x C uint8, mode 'RGB' or 'RGBa') to size (W2, H2) by row bands
    and column strips, in Pillow's own pass order, through the same 8-bit intermediate: Pillow's whole-image values."""
    from PIL import Image
    H, W, C = src.shape
    W2, H2 = int(size[0]), int(size[1])
    need_h, need_v = W2 != W, H2 != H
    if vertical_first(W, H, W2, H2):
        mid = np.zeros((H2, W, C), np.uint8)              # H2 x W: small, as W is under H / 100
        for s in _bands.strips(W, lanczos_bands.COL_STRIP):
            mid[:, s.start:s.stop] = np.asarray(_image(src.read_cols(s.start, s.stop), mode).resize((s.rows, H2),
                                                                                                    Image.LANCZOS))
        if not need_h:
            return mid
        out = np.zeros((H2, W2, C), np.uint8)
        for b in _bands.bands(H2, lanczos_bands.ROW_BAND):
            out[b.start:b.stop] = np.asarray(_image(mid[b.start:b.stop], mode).resize((W2, b.rows), Image.LANCZOS))
        return out
    if mode == 'RGB':
        dst = lanczos_bands.ArrayRows(np.zeros((H2, W2, C), np.uint8))
        tmp = _tmp_plane(tmp_dir, (H, W2, C)) if (need_h and need_v) else None
        try:
            lanczos_bands.resize(src, dst, tmp)
        finally:
            if tmp is not None:
                _unlink(tmp.path)
        return dst.a
    out = np.zeros((H2, W2, C), np.uint8)
    tmp = _tmp_plane(tmp_dir, (H, W2, C)) if (need_h and need_v) else None
    try:
        if need_h:
            for b in _bands.bands(H, lanczos_bands.ROW_BAND):
                rows = np.asarray(_image(src.read_rows(b.start, b.stop), mode).resize((W2, b.rows), Image.LANCZOS))
                if tmp is not None:
                    tmp.write_rows(b.start, rows)
                else:
                    out[b.start:b.stop] = rows
        if need_v:
            col_src = tmp if tmp is not None else src
            for s in _bands.strips(W2, lanczos_bands.COL_STRIP):
                out[:, s.start:s.stop] = np.asarray(_image(col_src.read_cols(s.start, s.stop), mode).resize(
                    (s.rows, H2), Image.LANCZOS))
    finally:
        if tmp is not None:
            _unlink(tmp.path)
    return out


def pixels(plane, alpha, size, tmp_dir):
    """The picture of a uint8 plane (with its H x W x 1 alpha plane, when given) at `size` (W2, H2): the values of Pillow's
    whole-image Image.resize(size, LANCZOS), RGB or RGBA, made by row bands and column strips (an RGBA one premultiplied
    once, as Pillow does). A temporary plane of H x W2 goes in tmp_dir while both passes run, under a name of its own (two
    copies can be made at once)."""
    H, W, _ = plane.shape
    size = (int(size[0]), int(size[1]))
    if alpha is None:
        return _resample(plane, size, 'RGB', tmp_dir)
    if size == (W, H):                        # Pillow returns an untouched copy when the size does not change
        out = np.empty((H, W, 4), np.uint8)
        for b in _bands.bands(H, lanczos_bands.ROW_BAND):
            out[b.start:b.stop, :, :3] = plane.read_rows(b.start, b.stop)
            out[b.start:b.stop, :, 3:] = alpha.read_rows(b.start, b.stop)
        return out
    return np.asarray(_image(_resample(_Premultiplied(plane, alpha), size, 'RGBa', tmp_dir), 'RGBa').convert('RGBA'))


def encode(arr):
    """(bytes, content type) of a sized copy, as service/images.sized_copy encodes the Classic engine's."""
    from PIL import Image
    buf = io.BytesIO()
    if arr.shape[2] == 4:
        _image(arr, 'RGBA').save(buf, 'PNG', compress_level=images.SIZED_PNG_LEVEL)
        return buf.getvalue(), 'image/png'
    Image.fromarray(np.ascontiguousarray(arr)).save(buf, 'JPEG', quality=images.SIZED_JPEG_QUALITY, subsampling=0)
    return buf.getvalue(), 'image/jpeg'


# --- the result's viewer folder -----------------------------------------------------------------------------------------

def place(src, dst):
    """Hard-link (or copy) `src` to `dst`, replacing a file already there without writing into it (an old result plane can
    be a hard link of a stage plane in the work folder)."""
    from service.util import link_or_copy
    dst = Path(dst)
    tmp = dst.with_name(f'.{dst.name}.{secrets.token_hex(4)}.tmp')
    try:
        link_or_copy(src, tmp)
        os.replace(tmp, dst)
    finally:
        _unlink(tmp)


def write_proxies(folder, plane, alpha=None):
    """proxy and thumb of a Large-image result from its planes. Opaque: proxy.jpg (quality 90) and thumb.jpg (quality 85, from
    the proxy), as 5.0.2's first build made them. With alpha: proxy.png and thumb.png, RGBA, at the sizes and in the way the
    Classic engine's are made (the thumb from the proxy, with its reducing_gap 2.0), so they look alike."""
    from PIL import Image
    folder = Path(folder)
    h, w, _ = plane.shape
    size = images.preview_size(w, h, images.PROXY_SIDE)
    tsize = images.preview_size(w, h, images.THUMB_SIDE)
    if alpha is None:
        px = Image.fromarray(pixels(plane, None, size, folder))
        images.save_atomic(px, folder / 'proxy.jpg', 'JPEG', quality=90)
        images.save_atomic(px.resize(tsize, Image.LANCZOS), folder / 'thumb.jpg', 'JPEG', quality=85)
        for stale in ('proxy.png', 'thumb.png'):
            _unlink(folder / stale)
        return
    px = _image(pixels(plane, alpha, size, folder), 'RGBA')
    images.save_atomic(px, folder / 'proxy.png', 'PNG', compress_level=images.PREVIEW_PNG_LEVEL)
    thumb = px if tsize == px.size else px.resize(tsize, Image.LANCZOS, reducing_gap=2.0)
    images.save_atomic(thumb, folder / 'thumb.png', 'PNG', compress_level=images.PREVIEW_PNG_LEVEL)
    for stale in ('proxy.jpg', 'thumb.jpg'):
        _unlink(folder / stale)


def identity(plane, alpha):
    """A short name for the pictures in these planes: the data hashes their producers recorded (engine/planes.py finish),
    else their sizes and modification times."""
    import hashlib

    def one(p):
        sha = p.header.get('sha256') if p.header.get('complete') else None
        if sha:
            return sha
        st = p.path.stat()
        return f'{st.st_size:x}.{st.st_mtime_ns:x}'
    text = COPY_VERSION + ':' + one(plane) + (':' + one(alpha) if alpha is not None else '')
    return hashlib.sha256(text.encode('ascii')).hexdigest()[:12]


class SizedPlaneCopies:
    """Sized copies of Large-image results, made once per result and size and kept on disk beside the result's plane.

    The viewer asks for the picture at exactly the size it draws it at Fit, so a result needs one or two sizes in a session
    and a handful when the window is resized; at most `per_item` are kept per result. Single flight: the two layers of the
    viewer, or a retry, asking for the same copy wait for one resample; at most `max_jobs` resamples run at once."""

    def __init__(self, per_item=PER_ITEM, max_jobs=2):
        self.per_item = int(per_item)
        self._lock = threading.Lock()
        self._inflight = {}
        self._slots = threading.BoundedSemaphore(max_jobs)
        self.made = 0

    @staticmethod
    def folder(result_dir):
        return Path(result_dir) / SIZED_DIR

    def get(self, result_dir, w, h):
        """(bytes, content type, (served w, h), (picture w, h)) of the result in `result_dir` at the size asked
        (images.sized_size: never larger than the picture). ValueError for a size outside 1..SIZED_MAX_SIDE;
        planes.PlaneError when the folder has no readable result plane."""
        w, h = int(w), int(h)
        if not (1 <= w <= images.SIZED_MAX_SIDE and 1 <= h <= images.SIZED_MAX_SIDE):
            raise ValueError(f'w and h must be 1 to {images.SIZED_MAX_SIDE} px')
        plane, alpha = open_planes(result_dir)
        H, W, _ = plane.shape
        served = images.sized_size(W, H, w, h)
        ident = identity(plane, alpha)
        ext = 'png' if alpha is not None else 'jpg'
        path = self.folder(result_dir) / f'{served[0]}x{served[1]}-{ident}.{ext}'
        ctype = 'image/png' if alpha is not None else 'image/jpeg'
        hit = self._read(path)
        if hit is not None:
            return hit, ctype, served, (W, H)
        key = str(path).lower()
        with self._lock:
            flight = self._inflight.get(key)
            owner = flight is None
            if owner:
                flight = self._inflight[key] = [threading.Event(), None, None]
        if not owner:
            flight[0].wait()
            if flight[2] is not None:
                raise flight[2]
            return flight[1], ctype, served, (W, H)
        try:
            hit = self._read(path)              # made while this request waited for the lock
            if hit is None:
                with self._slots:
                    data, _ = encode(pixels(plane, alpha, served, path.parent))
                    self._write(path, data)
                    self.made += 1
                self._trim(path.parent, ident, keep=path.name)
                hit = data
            flight[1] = hit
            return hit, ctype, served, (W, H)
        except BaseException as e:
            flight[2] = e
            raise
        finally:
            with self._lock:
                self._inflight.pop(key, None)
            flight[0].set()

    @staticmethod
    def _read(path):
        try:
            data = path.read_bytes()
        except OSError:
            return None
        try:
            os.utime(path)                      # most recently used
        except OSError:
            pass
        return data

    @staticmethod
    def _write(path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f'.{path.name}.{secrets.token_hex(4)}.tmp')
        try:
            with open(tmp, 'wb') as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            replace_with_retry(tmp, path)
        finally:
            _unlink(tmp)

    def _trim(self, folder, ident, keep):
        """Copies of an earlier result go; then the least recently used beyond per_item."""
        try:
            files = [p for p in Path(folder).iterdir() if p.is_file() and not p.name.startswith('.')]
        except OSError:
            return
        mine = []
        for p in files:
            if not p.stem.endswith('-' + ident):
                _unlink(p)
            else:
                mine.append(p)

        def used(p):
            try:
                return p.stat().st_mtime_ns
            except OSError:
                return 0
        mine.sort(key=lambda p: (p.name == keep, used(p)))
        for p in mine[:max(0, len(mine) - self.per_item)]:
            _unlink(p)

    def drop(self, result_dir):
        """Remove every sized copy of this result. True when there were any."""
        d = self.folder(result_dir)
        if not d.exists():
            return False
        shutil.rmtree(d, ignore_errors=True)
        return not d.exists()


class GuardedDecodedCache(images.DecodedCache):
    """images.DecodedCache that never decodes a Large-image result whole: a picture in a folder that holds a result plane is
    refused (WholeDecodeRefused), and its viewer uses the plane's routes. Every other picture is decoded as before."""

    def get(self, path, alpha_path=None):
        if is_plane_result(Path(path).parent):
            raise WholeDecodeRefused(f'{Path(path).name} belongs to a Large-image result; it is never decoded whole')
        return super().get(path, alpha_path)
