"""The Large-image writers on a finished result's own planes (engine design 9.2 W8: PNG8, PNG16, TIFF16 and JPEG at size,
and one RGBA input through the writers). The service writes a job's output in the one format the job asks for; this runs
the build's other writers (service/plane_io.encode, as service/banded_runner calls it) on the same result plane and alpha
plane, so each format is proven at size without another diffusion run. Each file is read back by its header only (never
decoded whole): its size, its band count and its bits per sample, read from the file itself (a PNG's IHDR, a TIFF's
BitsPerSample, a JPEG's frame precision), never from the writer's own report. Needs numpy and Pillow (the worker runtime).

    python -B -m tools.proof.writers --plane <result.plane> [--alpha <alpha.plane>] --out <dir> --formats png16,tiff16,jpeg

Prints {"files": {fmt: {"path", "bytes", "seconds", "sha256", "info", "header"}}, "errors": {fmt: text}}."""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

FORMATS = ('png8', 'png16', 'tiff16', 'jpeg')
EXT = {'png8': '.png', 'png16': '.png', 'tiff16': '.tif', 'jpeg': '.jpg'}
BITS = {'png8': 8, 'png16': 16, 'tiff16': 16, 'jpeg': 8}


def sha256_file(path, chunk=64 << 20):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(chunk), b''):
            h.update(b)
    return h.hexdigest()


PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'


def file_bits(path, im):
    """The bits per sample the written file declares, read from the file: a PNG's IHDR bit depth (byte 24; Pillow's mode
    reads 'RGB' or 'RGBA' at 8 and at 16 bits), a TIFF's BitsPerSample (tag 258, every sample alike) and a JPEG's frame
    precision. None when it cannot be read, or when a TIFF's samples differ."""
    if im.format == 'PNG':
        with open(path, 'rb') as f:
            b = f.read(26)
        return b[24] if len(b) == 26 and b[:8] == PNG_SIGNATURE and b[12:16] == b'IHDR' else None
    if im.format == 'TIFF':
        bits = set(im.tag_v2.get(258) or ())
        return bits.pop() if len(bits) == 1 else None
    if im.format == 'JPEG':
        return getattr(im, 'bits', None)
    return None


def header(path):
    """The written file's size, mode, band count and bits per sample from its header (Pillow opens lazily: no pixel is
    decoded)."""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None                     # a 1 GP output is the point; only the header is read
    with Image.open(path) as im:
        return {'size': list(im.size), 'mode': im.mode, 'bands': len(im.getbands()), 'format': im.format,
                'bits': file_bits(path, im)}


def expected(fmt, shape, alpha):
    """What the header must say: the plane's size, 4 bands with alpha (JPEG drops it, with 3), else 3."""
    h, w = int(shape[0]), int(shape[1])
    bands = 4 if (alpha and fmt != 'jpeg') else 3
    return {'size': [w, h], 'bands': bands, 'bits': BITS[fmt]}


def check(fmt, hdr, want):
    """The reasons a written file does not match (size, bands, bits per sample), or []. A header whose bits could not be
    read fails."""
    out = []
    if hdr.get('size') != want['size']:
        out.append(f"size {hdr.get('size')}, not {want['size']}")
    if hdr.get('bands') != want['bands']:
        out.append(f"{hdr.get('bands')} bands, not {want['bands']}")
    if hdr.get('bits') != want['bits']:
        out.append(f"{hdr.get('bits')} bits per sample in the file, not {want['bits']}")
    return out


def write_all(plane_path, alpha_path, out_dir, formats=FORMATS[1:], stem='result'):
    """Each format through service/plane_io.encode from the result plane (and alpha plane), into out_dir."""
    from engine import planes
    from service import images, plane_io
    plane = planes.validate(plane_path, dtype='u8')
    alpha = planes.validate(alpha_path) if alpha_path else None
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rec = {'plane': str(plane_path), 'alpha': str(alpha_path) if alpha_path else None, 'shape': list(plane.shape),
           'files': {}, 'errors': {}}
    for fmt in formats:
        if fmt not in FORMATS:
            rec['errors'][fmt] = f'unknown format {fmt}'
            continue
        path = out_dir / f'{stem}-{fmt}{EXT[fmt]}'
        t0 = time.time()
        try:
            info = plane_io.encode(path, plane, fmt, alpha=alpha, icc=images.srgb_icc_bytes())
            secs = round(time.time() - t0, 1)
            hdr = header(path)
            want = expected(fmt, plane.shape, alpha is not None)
            rec['files'][fmt] = {'path': str(path), 'bytes': path.stat().st_size, 'seconds': secs,
                                 'sha256': sha256_file(path), 'info': info, 'header': hdr, 'expected': want,
                                 'problems': check(fmt, hdr, want)}
        except Exception as e:  # noqa: BLE001 - a writer that fails is a result
            rec['errors'][fmt] = f'{type(e).__name__}: {e}'
    rec['pass'] = bool(rec['files']) and not rec['errors'] and not any(v['problems'] for v in rec['files'].values())
    return rec


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--plane', required=True)
    ap.add_argument('--alpha')
    ap.add_argument('--out', required=True)
    ap.add_argument('--formats', default='png16,tiff16,jpeg')
    a = ap.parse_args(argv)
    rec = write_all(a.plane, a.alpha, a.out, [f for f in a.formats.split(',') if f])
    print(json.dumps(rec, default=str))
    return 0 if rec['pass'] else 1


if __name__ == '__main__':
    sys.exit(main())
