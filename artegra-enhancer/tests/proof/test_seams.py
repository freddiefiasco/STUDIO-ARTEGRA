"""tools/proof/seams.py: M4 flags an injected band step and a gradient seam, and not a clean plane; positions from the plan."""
import tempfile
import unittest
from pathlib import Path

import numpy as np

from engine import planes
from tools.proof import colour, harness, seams


def texture(h, w, seed=0, sigma=2.0, amp=18.0, base=120.0):
    rng = np.random.default_rng(seed)
    t = colour.gaussian(rng.standard_normal((h, w)), sigma)
    t = t / t.std() * amp + base
    return np.clip(t, 0, 255).astype(np.uint8)[..., None].repeat(3, -1)


class Detector(unittest.TestCase):
    def test_clean_plane_is_not_flagged(self):
        img = texture(600, 400)
        r = seams.detect(img, rows={'band': [100, 200, 288, 300, 576]}, cols={'strip': [128, 256]})
        self.assertEqual(r['count_z_gt_4'], 0, r['flags'])
        self.assertLess(r['max_z'], 4.0)

    def test_injected_band_step_is_flagged_at_its_row(self):
        img = texture(600, 400).astype(np.int16)
        img[288:] += 3                                   # a 3-level brightness step at a band boundary
        img = np.clip(img, 0, 255).astype(np.uint8)
        r = seams.detect(img, rows={'band': [100, 200, 288, 400]})
        self.assertEqual([f['pos'] for f in r['flags']], [288])
        self.assertGreater(r['flags'][0]['z_step'], 4.0)

    def test_gradient_seam_without_a_mean_step_is_flagged(self):
        a = texture(600, 400, seed=1)
        b = texture(600, 400, seed=2)
        img = np.concatenate([a[:300], b[300:]])        # texture changes at row 300: |grad| spike, mean unchanged
        r = seams.detect(img, rows={'band': [150, 300, 450]})
        self.assertEqual([f['pos'] for f in r['flags']], [300])
        self.assertGreater(r['flags'][0]['z_grad'], 4.0)

    def test_columns_and_planes_read_by_bands(self):
        img = texture(600, 500).astype(np.int16)
        img[:, 256:] += 6
        img = np.clip(img, 0, 255).astype(np.uint8)
        with tempfile.TemporaryDirectory() as d:
            p = planes.from_array(Path(d) / 'o.plane', img)
            r = seams.detect({'kind': 'plane', 'path': str(p.path)}, cols={'strip': [128, 256, 384]}, band_rows=64)
            whole = seams.detect(img, cols={'strip': [128, 256, 384]})
        self.assertEqual([f['pos'] for f in r['flags']], [256])
        self.assertAlmostEqual(r['max_z'], whole['max_z'], places=6)


class Positions(unittest.TestCase):
    def test_positions_of_a_two_stage_plan_in_final_px(self):
        plan = harness.forced_plan(harness.PAIRS['chain4x'], 59.0)
        pos = seams.positions(plan.stages)
        W, H = plan.stages[-1].output_size
        for axis, lim in (('rows', H), ('cols', W)):
            for kind, vals in pos[axis].items():
                self.assertEqual(vals, sorted(set(vals)), kind)
                self.assertTrue(all(0 < v < lim for v in vals), kind)
        self.assertIn(288, pos['rows']['bxf_band'])
        self.assertIn(1024, pos['rows']['clamp_strip'])
        # stage 1 (1280 x 1600 at f 2) has DAT tile rows at input rows; scaled by 2 (stage) then 2 (the next stage)
        dat = harness.PAIRS['chain4x'][0]
        rows1 = seams._stage_positions({'factor': 2.0, 'supersample': 2.0, 'padded_size': dat.padded,
                                        'render_size': (dat.padded[0] * 4, dat.padded[1] * 4),
                                        'output_size': dat.output}, 'classic')['rows']['dat']
        self.assertTrue({int(round(v * 2)) for v in rows1} <= set(pos['rows']['dat']))

    def test_classic_only_has_no_bes_kinds(self):
        plan = harness.forced_plan(harness.PAIRS['k4'], 59.0)
        pos = seams.positions(plan.stages, executors=('classic',))
        self.assertNotIn('bxf_band', pos['rows'])
        self.assertIn('vae', pos['rows'])

    def test_tiled_scale_spans_cover_the_axis(self):
        for n in (50, 128, 129, 437, 1094):
            sp = seams.tiled_scale_spans(n, 128, 8)
            self.assertEqual(sp[0][0], 0)
            self.assertEqual(max(b for _, b in sp), n)


if __name__ == '__main__':
    unittest.main()
