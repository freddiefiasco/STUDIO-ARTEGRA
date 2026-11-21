"""tools/proof/noise_floor.py: size classes and the floors file (the runner itself is tested in test_classic, with torch)."""
import json
import tempfile
import unittest
from pathlib import Path

from tools.proof import noise_floor


class Floors(unittest.TestCase):
    def test_size_classes(self):
        self.assertEqual(noise_floor.size_class(7.7), 'le8')
        self.assertEqual(noise_floor.size_class(122.5), 'le150')
        self.assertEqual(noise_floor.size_class(490.0), 'le700')
        self.assertEqual(noise_floor.size_class(1024.0), 'gt700')

    def test_floors_keep_the_largest_F_per_class(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'floors.json'
            noise_floor.update_floors(p, {'size_class': 'le150', 'F': 3, 'output_mp': 122.5}, 'a')
            noise_floor.update_floors(p, {'size_class': 'le150', 'F': 1, 'output_mp': 140.0}, 'b')
            noise_floor.update_floors(p, {'size_class': 'le8', 'F': 0, 'output_mp': 2.0}, 'c')
            d = json.loads(p.read_text(encoding='utf8'))
            self.assertEqual(d['classes']['le150']['F'], 3)
            self.assertEqual(len(d['classes']['le150']['runs']), 2)
            self.assertEqual(d['classes']['le8']['F'], 0)

    def test_the_registered_variants(self):
        self.assertEqual(noise_floor.VARIANTS, (('default', None, None), ('threads7', 7, None), ('threads13', 13, None),
                                                ('pow333', None, 333)))


if __name__ == '__main__':
    unittest.main()
