"""The branch labels of the tier-3 wide-stage measurements (5.0.2 wave 3, F3C-2): tests/fixtures/bxf_finish_memory.json says,
for each tier-3 row at a 32,000 px wide stage, which BRANCHES of tools/gate_g2.py its scene does not exercise
(branches_not_exercised). The classic tier-3 child records no branch counters, so the label comes from the BXF's counters on
the same scene (the BXF is exact against the classic finish: gate G2): tools/gate_g2.scene_branches cuts the measured scene
(its pre size and its seed) to its left two base tiles, which hold the same rows and features. This checks that the cut is
the measured scene's own left part and that every label equals the counters. Sizes and synthetic images only. Skipped where
torch or scipy is not installed:  python -B -m unittest tests.worker.test_bxf_tier3_scenes  (artegra-enhancer folder)."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

HAVE = all(importlib.util.find_spec(m) is not None for m in ('torch', 'scipy'))
ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / 'tests' / 'fixtures' / 'bxf_finish_memory.json'


def gate_g2():
    spec = importlib.util.spec_from_file_location('cu_test_tier3_scenes_gate_g2', ROOT / 'tools' / 'gate_g2.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def wide_rows():
    data = json.loads(FIXTURE.read_text(encoding='utf8'))
    return [m for m in data['measurements'] if m['tier'] == 'tier3' and m['output_size'][0] >= 32000]


@unittest.skipUnless(HAVE, 'torch and scipy are needed')
class TheWideTier3Labels(unittest.TestCase):
    def test_the_cut_is_the_measured_scenes_left_part(self):
        """Every array of the cut (pre, creative, structure, init, protect, release) equals the left part of the scene the
        measurement made at its own width (16,000 pre px), at every wide row's height."""
        G2 = gate_g2()
        rows = wide_rows()
        self.assertTrue(rows)
        for m in rows:
            w, h = m['input_size']
            whole = G2.scene(h, w, 2, seed=h * 31 + w)
            cut = G2.scene(h, 2 * G2.BASE[1], 2, seed=h * 31 + w)
            for k, (a, b) in enumerate(zip(whole, cut)):
                self.assertEqual(a.shape[0], b.shape[0], (m['source'], k))
                self.assertTrue(np.array_equal(a[:, :b.shape[1]], b), (m['source'], G2.SCENE_KEYS[k]))
            del whole, cut

    def test_each_wide_rows_label_is_its_scenes_branches(self):
        """The fixture's branches_not_exercised is exactly the BRANCHES the BXF's counters leave at 0 (or absent) on the cut,
        with the option case the measurement ran (v4f-protect-release): [] at 1,200 and 2,400 rows, the floor, litter and
        sky-gap branches at 600 rows, and the badges' too at 320 rows."""
        G2 = gate_g2()
        rows = wide_rows()
        self.assertTrue(any(m['branches_not_exercised'] for m in rows))
        self.assertTrue(any(not m['branches_not_exercised'] for m in rows))
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            for i, m in enumerate(rows):
                w, h = m['input_size']
                br, gone = G2.scene_branches(h, w, Path(td) / str(i))
                self.assertEqual(gone, sorted(k for k in G2.BRANCHES if not br.get(k, 0)), m['source'])
                self.assertEqual(gone, m['branches_not_exercised'], (m['source'], br))


if __name__ == '__main__':
    unittest.main()
