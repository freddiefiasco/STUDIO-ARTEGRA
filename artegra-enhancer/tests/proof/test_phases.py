"""tools/proof/phases.py: each role's compared form, and the phase counter locating a difference at its first phase."""
import tempfile
import unittest
from pathlib import Path

import numpy as np

from engine import planes
from tools.proof import phases

T = planes.U8_TO_F32


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.n = 0

    def tearDown(self):
        self._tmp.cleanup()

    def plane(self, arr, form=None):
        self.n += 1
        p = planes.from_array(self.dir / f'p{self.n}.plane', arr)
        e = {'kind': 'plane', 'path': str(p.path)}
        if form:
            e['form'] = form
        return e


class Forms(Base):
    def test_u8_table_equal_when_classic_floats_are_the_table_values(self):
        rng = np.random.default_rng(0)
        u = rng.integers(0, 256, (37, 21, 3)).astype(np.uint8)
        r = phases.compare_entries(self.plane(T[u]), self.plane(u), 'u8_table')
        self.assertEqual(r['count'], 0)
        f = T[u].copy()
        f[3, 4, 1] = np.nextafter(f[3, 4, 1], np.float32(2))     # one ulp off the table
        r = phases.compare_entries(self.plane(f), self.plane(u), 'u8_table')
        self.assertEqual(r['count'], 1)
        self.assertEqual(r['first_row'], 3)

    def test_q8_truncates_like_the_finish(self):
        x = np.array([[[0.0, 0.5, 1.0], [0.99999, 0.0039, 0.004]]], np.float32)
        want = np.clip(255. * x, 0, 255).astype(np.uint8)
        self.assertEqual(phases.compare_entries(self.plane(x), self.plane(want), 'q8')['count'], 0)
        rounded = np.clip(np.round(255. * x), 0, 255).astype(np.uint8)
        self.assertGreater(phases.compare_entries(self.plane(x), self.plane(rounded), 'q8')['count'], 0)

    def test_edges_three_channel_float_against_one_channel_u8(self):
        e = np.zeros((16, 16), bool)
        e[5, :] = True
        classic = e[..., None].repeat(3, -1).astype(np.float32)
        bes = (e * 255).astype(np.uint8)[..., None]
        self.assertEqual(phases.compare_entries(self.plane(classic), self.plane(bes), 'edges')['count'], 0)
        bes2 = bes.copy()
        bes2[9, 2, 0] = 255
        self.assertEqual(phases.compare_entries(self.plane(classic), self.plane(bes2), 'edges')['count'], 1)
        bad = classic.copy()
        bad[0, 0, 1] = 1.0                                       # channels disagree: a form error, counted
        self.assertEqual(phases.compare_entries(self.plane(bad), self.plane(bes), 'edges')['count'], 1)

    def test_bitwise_counts_signed_zero_and_shape_mismatch(self):
        a = np.zeros((4, 4, 1), np.float32)
        b = a.copy()
        b[1, 1, 0] = -0.0
        self.assertEqual(phases.compare_entries(self.plane(a), self.plane(b), 'bitwise')['count'], 1)
        r = phases.compare_entries(self.plane(a), self.plane(np.zeros((4, 5, 1), np.float32)), 'bitwise')
        self.assertEqual(r['status'], 'shape')
        self.assertGreater(r['count'], 0)

    def test_stage_output_crops_the_padded_classic(self):
        rng = np.random.default_rng(2)
        toe = T[rng.integers(0, 256, (40, 30, 3)).astype(np.uint8)]
        stage = np.clip(255. * toe, 0, 255).astype(np.uint8)[:37, :26]
        self.assertEqual(phases.compare_entries(self.plane(toe), self.plane(stage), 'save8_crop')['count'], 0)
        stage[36, 25, 2] ^= 1
        self.assertEqual(phases.compare_entries(self.plane(toe), self.plane(stage), 'save8_crop')['count'], 1)

    def test_band_reading_matches_whole(self):
        rng = np.random.default_rng(3)
        a = rng.random((1100, 7, 3)).astype(np.float32)
        b = a.copy()
        b[0, 0, 0] += 1
        b[1099, 6, 2] += 1
        r = phases.compare_entries(self.plane(a), self.plane(b), 'bitwise', band_rows=64)
        self.assertEqual((r['count'], r['first_row'], r['elements']), (2, 0, a.size))


class Counter(Base):
    def run_pair(self, change):
        rng = np.random.default_rng(4)
        mask = (rng.random((24, 24, 1)) > 0.5).astype(np.float32)
        canvas = rng.integers(0, 256, (48, 48, 3)).astype(np.uint8)
        hint = rng.random((48, 48, 3)).astype(np.float32)
        lat = rng.random((4 * 6, 6, 1)).astype(np.float32)
        raw = T[rng.integers(0, 256, (48, 48, 3)).astype(np.uint8)]
        classic = {'sam/protect/0': self.plane(mask), 'union/protect': self.plane(mask),
                   'canvas': self.plane(T[canvas], 'u8_table'), 'hint': self.plane(hint), 'latent/ks1': self.plane(lat),
                   'raw8': self.plane(raw)}
        bes = {'sam/protect/0': self.plane(mask), 'union/protect': self.plane(mask), 'canvas': self.plane(canvas, 'u8_table'),
               'hint': self.plane(hint), 'latent/ks1': self.plane(lat),
               'raw8': self.plane(np.clip(255. * raw, 0, 255).astype(np.uint8))}
        for role, arr in change.items():
            bes[role] = self.plane(arr, bes[role].get('form'))
        return phases.count(classic, bes)

    def test_identical_runs_read_zero_everywhere(self):
        rep = self.run_pair({})
        self.assertTrue(rep['zero'])
        self.assertIsNone(rep['first_differing_phase'])
        self.assertEqual([p['phase'] for p in rep['phases']], list(phases.PHASES))

    def test_first_differing_phase_is_the_earliest_in_the_table(self):
        rng = np.random.default_rng(9)
        hint2 = rng.random((48, 48, 3)).astype(np.float32)
        lat2 = rng.random((24, 6, 1)).astype(np.float32)
        rep = self.run_pair({'latent/ks1': lat2, 'hint': hint2})
        self.assertFalse(rep['zero'])
        self.assertEqual(rep['first_differing_phase'], 'hints')
        by = {p['phase']: p for p in rep['phases']}
        self.assertEqual(by['x4']['differing'], 0)
        self.assertGreater(by['vae_samplers']['differing'], 0)

    def test_a_missing_role_is_a_difference_not_a_pass(self):
        rng = np.random.default_rng(5)
        c = {'canvas': self.plane(T[rng.integers(0, 256, (8, 8, 3)).astype(np.uint8)], 'u8_table')}
        rep = phases.count(c, {})
        self.assertFalse(rep['zero'])
        self.assertEqual(rep['first_differing_phase'], 'x4')
        self.assertIn('canvas', rep['missing'])

    def test_optional_finish_role_is_not_compared_when_one_side_lacks_it(self):
        rng = np.random.default_rng(6)
        c = {'finish': self.plane(rng.random((4, 4, 3)).astype(np.float32))}
        rep = phases.count(c, {})
        self.assertTrue(rep['zero'])
        self.assertEqual(rep['not_compared'], ['finish'])

    def test_controlnet_records_compare_by_hash_and_by_values(self):
        a = {'kind': 'cn', 'calls': [{'sha256': ['aa', 'bb']}, {'sha256': ['cc']}]}
        b = {'kind': 'cn', 'calls': [{'sha256': ['aa', 'bb']}, {'sha256': ['cd']}]}
        r = phases.compare_entries(a, b, 'cn')
        self.assertEqual((r['count'], r['exact'], r['first_call']), (1, False, 1))
        self.assertEqual(phases.compare_entries(a, dict(a), 'cn')['count'], 0)

    def test_controlnet_values_kept_give_an_exact_count(self):
        x = np.arange(12, dtype=np.float16)
        y = x.copy()
        y[[2, 7]] += 1
        fx, fy = self.dir / 'x.bin', self.dir / 'y.bin'
        x.tofile(fx)
        y.tofile(fy)
        a = {'kind': 'cn', 'calls': [{'sha256': ['x'], 'files': [str(fx)], 'dtypes': ['torch.float16']}]}
        b = {'kind': 'cn', 'calls': [{'sha256': ['y'], 'files': [str(fy)], 'dtypes': ['torch.float16']}]}
        r = phases.compare_entries(a, b, 'cn')
        self.assertEqual((r['count'], r['exact']), (2, True))

    def test_every_role_maps_to_a_phase(self):
        for role in ('sam/protect/3', 'union/release', 'gate', 'canvas', 'init', 'hint', 'edges', 'cn/12/0', 'latent/encode',
                     'latent/ks2', 'raw8', 'rawlo8', 'finish', 'stage_output'):
            self.assertIn(phases.phase_of(role), phases.PHASES, role)
        with self.assertRaises(KeyError):
            phases.phase_of('something_else')


if __name__ == '__main__':
    unittest.main()
