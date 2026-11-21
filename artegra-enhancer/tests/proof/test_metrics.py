"""tools/proof/metrics.py without the halo tools: M5/M6 fidelity on synthetic outputs, and compare_case's floors and rule on
hand-made measurement bundles."""
import unittest

import numpy as np

from tools.proof import colour, metrics


def src_img(seed=0):
    rng = np.random.default_rng(seed)
    a = colour.gaussian(rng.standard_normal((48, 64)), 2.0)
    a = (a / a.std() * 20 + 120)
    return np.clip(np.stack([a, a * 0.9 + 10, a * 0.8 + 20], -1), 0, 255).astype(np.uint8)


class Fidelity(unittest.TestCase):
    def test_a_faithful_enlargement_reads_zero_and_a_tint_does_not(self):
        s = src_img()
        out = s.repeat(2, 0).repeat(2, 1)
        f = metrics.fidelity(s, out)
        self.assertEqual(sorted(f), ['sigma_1', 'sigma_4'])
        self.assertLess(f['sigma_1']['de_p95'], 1e-3)
        tint = np.clip(out.astype(np.int16) + np.array([8, 0, -8]), 0, 255).astype(np.uint8)
        g = metrics.fidelity(s, tint)
        self.assertGreater(g['sigma_1']['de_p50'], 1.0)
        dark = np.clip(out.astype(np.int16) - 10, 0, 255).astype(np.uint8)
        self.assertGreater(metrics.fidelity(s, dark)['sigma_4']['dl_p50'], 2.0)


def fake(n=40, rim=1.0, seed=0, sha=None, tiles=1.0, z=1.0, jitter=0.0):
    rng = np.random.default_rng(seed)
    disp = np.random.default_rng(99).normal(0, 0.1, n).astype(np.float32)      # the same edges in every output
    A = {'region': np.zeros(n, np.int32), 'seg': np.arange(n, dtype=np.int32), 'status': np.zeros(n, np.int8),
         'disp': disp, 'glow_abs': np.full(n, 0.2, np.float32),
         'contrast_kept': np.full(n, 0.95, np.float32), 'rise': np.full(n, 1.5, np.float32),
         'slope': np.full(n, 0.8, np.float32)}
    for k in ('rim_lift_bright', 'rim_drop_bright', 'rim_lift_dark', 'rim_drop_dark', 'rimw_lift_bright', 'rimw_drop_bright',
              'rimw_lift_dark', 'rimw_drop_dark', 'rim_max'):
        A[k] = (np.full(n, rim) + rng.normal(0, jitter, n)).astype(np.float32)
    T = {(x * 256, 0): {'count': 65536.0, 'tile_out_band_0.5_1.0': 10.0 * tiles} for x in range(8)}
    fid = {'sigma_1': {'de_p50': 0.5, 'de_p95': 1.0, 'de_mean': 0.6, 'dl_p50': 0.2, 'dl_p95': 0.5},
           'sigma_4': {'de_p50': 0.3, 'de_p95': 0.7, 'de_mean': 0.4, 'dl_p50': 0.1, 'dl_p95': 0.3}}
    return {'arrays': A, 'tiles': T, 'seams': {'max_z': z, 'count_z_gt_4': 0}, 'fidelity': fid, 'sha256': sha,
            'report': {'worst': [{'x': 1, 'y': 2, 'halo_index': rim}], 'mode': 'whole', 'grid': None, 'n_regions': 1,
                       'edge_set_hash': 'e0'}}


class Compare(unittest.TestCase):
    def test_same_quality_passes_within_the_floor(self):
        r = metrics.compare_case(fake(rim=1.0, sha='a', jitter=0.001), fake(rim=1.005, seed=1, sha='b', jitter=0.001),
                                 fake(rim=1.02, seed=2, sha='c', jitter=0.001))
        self.assertTrue(r['pass_metrics'], r['worse_rows'])
        self.assertFalse(r['identical'])
        self.assertEqual(r['paired_segments'], 40)

    def test_a_larger_halo_beyond_its_floor_fails_on_m1(self):
        r = metrics.compare_case(fake(rim=1.0), fake(rim=2.0, seed=1), fake(rim=1.02, seed=2))
        self.assertFalse(r['pass_metrics'])
        self.assertTrue(all(x['metric'] == 'M1' for x in r['worse_rows']))
        self.assertIn('rim_max', {x['key'] for x in r['worse_rows']})

    def test_the_sampling_floor_can_cover_a_small_delta(self):
        r = metrics.compare_case(fake(rim=1.0), fake(rim=1.3, seed=1), fake(rim=1.0, seed=2),
                                 sampling_floors={'rim_p90_delta': 0.387})
        self.assertFalse(any(x['key'] == 'rim_max' for x in r['worse_rows']), r['worse_rows'])

    def test_lost_detail_and_seams_fail_on_m3_and_m4(self):
        r = metrics.compare_case(fake(), fake(seed=1, tiles=0.8, z=9.0), fake(seed=2))
        bad = {x['metric'] for x in r['worse_rows']}
        self.assertEqual(bad, {'M3', 'M4'})

    def test_identical_outputs_read_zero_and_pass(self):
        a = fake(sha='same')
        r = metrics.compare_case(a, dict(a), fake(seed=2))
        self.assertTrue(r['identical'])
        self.assertTrue(r['pass_metrics'])
        self.assertTrue(all(x['worse_by'] == 0.0 for x in r['rows']))

    def test_missing_values_are_worse_not_a_pass(self):
        b = fake(seed=1)
        b['arrays']['status'][:] = 1                          # no segment measured ok
        r = metrics.compare_case(fake(), b, fake(seed=2))
        self.assertFalse(r['pass_metrics'])

    def test_a_key_is_paired_over_the_segments_all_three_measure(self):
        a, b, c = fake(), fake(seed=1), fake(seed=2)
        for X in (a, b, c):
            X['arrays']['rise'][:20], X['arrays']['rise'][20:] = 1.0, 3.0      # 20 sharp edges, 20 soft ones
        b['arrays']['rise'][20:] = np.nan                     # the BES cannot measure its soft edges' rise
        r = metrics.compare_case(a, b, c)
        row = next(x for x in r['rows'] if x['key'] == 'rise' and x['stat'] == 'p50')
        # not the BES's 20 sharp edges against the classic's 40 (which would read the BES sharper): the same 20 in all three
        self.assertEqual((row['n'], row['classic_a'], row['bes_a'], row['classic_b']), (20, 1.0, 1.0, 1.0))
        self.assertEqual(row['unmeasured'], {'classic_a': 0, 'bes_a': 20, 'classic_b': 0})
        slope = next(x for x in r['rows'] if x['key'] == 'slope' and x['stat'] == 'p50')
        self.assertEqual(slope['n'], 40)

    def test_a_key_the_bes_never_measures_is_worse(self):
        b = fake(seed=1)
        b['arrays']['rise'][:] = np.nan
        r = metrics.compare_case(fake(), b, fake(seed=2))
        bad = [x for x in r['worse_rows'] if x['key'] == 'rise']
        self.assertEqual([x['stat'] for x in bad], ['p50', 'p90'])
        self.assertTrue(all(x['reason'] == 'missing value' and x['n'] == 0 for x in bad))

    def test_registered_rules_name_every_metric(self):
        rules = metrics.registered_rules()
        self.assertEqual({m['metric'] for m in rules['metrics']}, {'M1', 'M2', 'M3', 'M4', 'M5', 'M6'})


if __name__ == '__main__':
    unittest.main()
