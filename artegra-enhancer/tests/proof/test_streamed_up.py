"""Q5's pass-2 upscale made by the streamed path (D10): pass 2 Lanczos-scaled into a plane by row bands and column strips
(engine/lanczos_bands.resize between planes), never a whole array at pass-3 size, equal byte for byte to the whole upscale on
a small case; and the module list of tools/proof names only modules that exist. Synthetic arrays only."""
import ast
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from engine import planes
from tools.proof import qmetrics
from tools.proof.phases import _Arr

ROOT = Path(__file__).resolve().parents[2]


def pass2(w=150, h=96, seed=3):
    rng = np.random.default_rng(seed)
    a = rng.integers(0, 256, (h, w, 3)).astype(np.uint8)
    a[20:40, 30:90] = (250, 240, 230)
    return a


class StreamedUp(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.d = Path(self._t.name)

    def tearDown(self):
        self._t.cleanup()

    def test_the_plane_equals_the_whole_upscale(self):
        p2 = pass2(150, 330)
        size = (450, 990)                                                # x3, as 8x pass 3 against pass 2's 2x+2x
        whole = np.asarray(Image.fromarray(p2).resize(size, Image.LANCZOS))
        e = qmetrics.lanczos_up_plane(p2, size, self.d / 'up.plane', row_band=288, col_strip=48)   # 2 and 4 row bands
        self.assertEqual(e['kind'], 'plane')
        A = _Arr(e)
        self.assertEqual(A.shape, (990, 450, 3))
        got = A.rows(0, 990)
        self.assertTrue(np.array_equal(got, whole))
        self.assertTrue(np.array_equal(got, qmetrics.lanczos_up(p2, size)))
        self.assertIsNotNone(planes.validate(e['path']).header.get('sha256'))

    def test_a_plane_source_is_read_by_bands(self):
        p2 = pass2(97, 301, seed=5)
        src = planes.from_array(self.d / 'p2.plane', p2)
        e = qmetrics.lanczos_up_plane({'kind': 'plane', 'path': str(src.path)}, (194, 602), self.d / 'up.plane',
                                      row_band=288)
        whole = np.asarray(Image.fromarray(p2).resize((194, 602), Image.LANCZOS))
        self.assertTrue(np.array_equal(_Arr(e).rows(0, 602), whole))
        self.assertFalse(list(self.d.glob('*.hpass.plane')))             # the horizontal pass's plane is removed

    def test_q5_reads_the_streamed_plane_as_it_reads_an_array(self):
        p2 = pass2(128, 96, seed=7)
        p3 = np.asarray(Image.fromarray(p2).resize((256, 192), Image.LANCZOS))
        e = qmetrics.lanczos_up_plane(p2, (256, 192), self.d / 'up.plane')
        _, _, a = qmetrics.q5_stats(p3, qmetrics.lanczos_up(p2, (256, 192)))
        _, _, b = qmetrics.q5_stats(p3, e)
        self.assertEqual(a, b)

    def test_an_existing_target_is_refused(self):
        p2 = pass2(40, 30)
        qmetrics.lanczos_up_plane(p2, (80, 60), self.d / 'up.plane')
        with self.assertRaises(FileExistsError):
            qmetrics.lanczos_up_plane(p2, (80, 60), self.d / 'up.plane')


class ModuleList(unittest.TestCase):
    def test_the_package_docstring_names_exactly_the_modules_that_exist(self):
        pkg = ROOT / 'tools' / 'proof'
        doc = ast.get_docstring(ast.parse((pkg / '__init__.py').read_text(encoding='utf8')))
        named = [line[2:].split(':', 1)[0].strip() for line in doc.splitlines() if line.startswith('- ')]
        self.assertEqual(len(named), len(set(named)))
        named = set(named)
        have = {p.stem for p in pkg.glob('*.py') if p.stem != '__init__'} | {'comfy_nodes/cu_proof'}
        self.assertEqual(named, have)


if __name__ == '__main__':
    unittest.main()
