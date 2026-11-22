"""tools/proof/writers.py (W8's row: PNG8, PNG16, TIFF16 and JPEG from a result's own planes, and one RGBA input through the
writers): each format of service/plane_io, on a small synthetic result plane with and without an alpha plane, written,
read back by its header and hashed. Synthetic arrays made here only; no service, no GPU."""
import tempfile
import unittest
from pathlib import Path

import numpy as np

from engine import planes
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
            self.assertEqual(rec['files']['png16']['info']['bits'], 16)

    def test_an_rgba_result_keeps_its_alpha_except_in_jpeg(self):
        with tempfile.TemporaryDirectory() as d:
            plane, alpha = make(d, alpha=True)
            rec = writers.write_all(plane, alpha, Path(d) / 'out', writers.FORMATS)
            self.assertTrue(rec['pass'], rec)
            self.assertEqual({k: v['header']['bands'] for k, v in rec['files'].items()},
                             {'png8': 4, 'png16': 4, 'tiff16': 4, 'jpeg': 3})
            self.assertIn('dropped', rec['files']['jpeg']['info']['alpha'])
            self.assertEqual(rec['files']['png8']['info']['alpha'], 'kept')

    def test_a_wrong_header_or_a_failing_writer_fails(self):
        self.assertEqual(writers.check('png16', {'size': [10, 10], 'bands': 3}, writers.expected('png16', (10, 10, 3), False)),
                         [])
        self.assertTrue(writers.check('png16', {'size': [10, 9], 'bands': 4}, writers.expected('png16', (10, 10, 3), False)))
        with tempfile.TemporaryDirectory() as d:
            plane, _ = make(d)
            rec = writers.write_all(plane, None, Path(d) / 'out', ['png16', 'webp'])
            self.assertFalse(rec['pass'])
            self.assertIn('webp', rec['errors'])


if __name__ == '__main__':
    unittest.main()
