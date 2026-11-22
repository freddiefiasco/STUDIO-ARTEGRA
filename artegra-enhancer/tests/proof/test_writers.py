"""tools/proof/writers.py (W8's row: PNG8, PNG16, TIFF16 and JPEG from a result's own planes, and one RGBA input through the
writers): each format of service/plane_io, on a small synthetic result plane with and without an alpha plane, written,
read back by its header (size, bands and the bits per sample the file itself declares) and hashed; a file written at the
wrong bit depth under a 16-bit format fails. Synthetic arrays made here only; no service, no GPU."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from engine import planes
from service import plane_io
from tools.proof import writers


def make(d, w=96, h=64, alpha=False):
    rng = np.random.default_rng(7)
    p = planes.from_array(Path(d) / 'result.plane', rng.integers(0, 256, (h, w, 3)).astype(np.uint8))
    a = None
    if alpha:
        yy, xx = np.mgrid[0:h, 0:w]
        a = planes.from_array(Path(d) / 'alpha.plane', ((xx * 255 // (w - 1)) * (yy > h // 4))[..., None].astype(np.uint8))
    return p.path, (a.path if a is not None else None)


class Writers(unittest.TestCase):
    def test_every_format_from_an_rgb_result(self):
        with tempfile.TemporaryDirectory() as d:
            plane, _ = make(d)
            rec = writers.write_all(plane, None, Path(d) / 'out', writers.FORMATS)
            self.assertTrue(rec['pass'], rec)
            self.assertEqual(sorted(rec['files']), sorted(writers.FORMATS))
            for fmt, f in rec['files'].items():
                self.assertEqual(f['header']['size'], [96, 64], fmt)
                self.assertEqual(f['header']['bands'], 3, fmt)
                self.assertEqual(len(f['sha256']), 64)
                self.assertGreater(f['bytes'], 0)
            self.assertEqual({k: v['header']['bits'] for k, v in rec['files'].items()},
                             {'png8': 8, 'png16': 16, 'tiff16': 16, 'jpeg': 8})
            self.assertEqual(rec['files']['png16']['info']['bits'], 16)

    def test_an_rgba_result_keeps_its_alpha_except_in_jpeg(self):
        with tempfile.TemporaryDirectory() as d:
            plane, alpha = make(d, alpha=True)
            rec = writers.write_all(plane, alpha, Path(d) / 'out', writers.FORMATS)
            self.assertTrue(rec['pass'], rec)
            self.assertEqual({k: v['header']['bands'] for k, v in rec['files'].items()},
                             {'png8': 4, 'png16': 4, 'tiff16': 4, 'jpeg': 3})
            self.assertEqual({k: v['header']['bits'] for k, v in rec['files'].items()},
                             {'png8': 8, 'png16': 16, 'tiff16': 16, 'jpeg': 8})
            self.assertIn('dropped', rec['files']['jpeg']['info']['alpha'])
            self.assertEqual(rec['files']['png8']['info']['alpha'], 'kept')

    def test_a_wrong_header_or_a_failing_writer_fails(self):
        want = writers.expected('png16', (10, 10, 3), False)
        self.assertEqual(writers.check('png16', {'size': [10, 10], 'bands': 3, 'bits': 16}, want), [])
        self.assertTrue(writers.check('png16', {'size': [10, 9], 'bands': 4, 'bits': 16}, want))
        self.assertEqual(writers.check('png16', {'size': [10, 10], 'bands': 3, 'bits': 8}, want),
                         ['8 bits per sample in the file, not 16'])
        self.assertEqual(writers.check('png16', {'size': [10, 10], 'bands': 3}, want),       # unread bits fail
                         ['None bits per sample in the file, not 16'])
        with tempfile.TemporaryDirectory() as d:
            plane, _ = make(d)
            rec = writers.write_all(plane, None, Path(d) / 'out', ['png16', 'webp'])
            self.assertFalse(rec['pass'])
            self.assertIn('webp', rec['errors'])

    def test_an_8_bit_png_written_under_png16_fails(self):
        """The writer reports 16 bits from the format name; the file's own IHDR says 8 and the check reads the file."""
        real = plane_io.write_png

        def eight(path, plane, bits=8, *a, **k):
            return real(path, plane, 8, *a, **k)
        with tempfile.TemporaryDirectory() as d, mock.patch.object(plane_io, 'write_png', eight):
            plane, alpha = make(d, alpha=True)
            rec = writers.write_all(plane, alpha, Path(d) / 'out', ['png16'])
            f = rec['files']['png16']
            self.assertEqual((f['info']['bits'], f['header']['bits'], f['header']['mode']), (16, 8, 'RGBA'))
            self.assertEqual(f['problems'], ['8 bits per sample in the file, not 16'])
            self.assertFalse(rec['pass'])

    def test_an_8_bit_tiff_written_under_tiff16_fails(self):
        from PIL import Image

        def eight(path, plane, alpha=None, icc=None, software='', big=None):
            rgb = np.asarray(plane.map('r'))
            if alpha is not None:
                rgb = np.concatenate([rgb, np.asarray(alpha.map('r'))], axis=2)
            Image.fromarray(np.ascontiguousarray(rgb), 'RGBA' if alpha is not None else 'RGB').save(path, 'TIFF')
            return 'tiff'
        with tempfile.TemporaryDirectory() as d, mock.patch.object(plane_io, 'write_tiff16', eight):
            plane, _ = make(d)
            rec = writers.write_all(plane, None, Path(d) / 'out', ['tiff16'])
            f = rec['files']['tiff16']
            self.assertEqual((f['info']['bits'], f['header']['bits'], f['header']['bands']), (16, 8, 3))
            self.assertEqual(f['problems'], ['8 bits per sample in the file, not 16'])
            self.assertFalse(rec['pass'])

    def test_a_bigtiff_is_read_for_its_bits(self):
        """W8's TIFF16 at 1 GP is a BigTIFF (plane_io.BIGTIFF_ABOVE): its BitsPerSample reads 16 from the file."""
        with tempfile.TemporaryDirectory() as d:
            plane, alpha = make(d, alpha=True)
            for big, container in ((True, 'bigtiff'), (False, 'tiff')):
                path = Path(d) / f'{container}.tif'
                got = plane_io.write_tiff16(path, planes.validate(plane, dtype='u8'), planes.validate(alpha), big=big)
                self.assertEqual(got, container)
                hdr = writers.header(path)
                self.assertEqual((hdr['bits'], hdr['bands'], hdr['size']), (16, 4, [96, 64]), container)
                self.assertEqual(writers.check('tiff16', hdr, writers.expected('tiff16', (64, 96, 3), True)), [])


if __name__ == '__main__':
    unittest.main()
