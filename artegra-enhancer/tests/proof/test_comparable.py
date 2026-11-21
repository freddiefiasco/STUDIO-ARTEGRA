"""metrics.compare_case refuses bundles that were not measured alike (D5): the three outputs of a case must share the halo
metric's mode, region grid and edge set, else their segments are not the same source segments and no row is compared."""
import unittest

from tests.proof.test_metrics import fake
from tools.proof import metrics


def measured(b, mode='whole', grid=None, edges='e0', regions=1):
    b = dict(b)
    b['report'] = dict(b['report'], mode=mode, grid=grid, edge_set_hash=edges, n_regions=regions)
    return b


GRID = {'core_src': 512, 'margin_src': 96}


class Comparable(unittest.TestCase):
    def test_alike_bundles_are_compared(self):
        r = metrics.compare_case(measured(fake()), measured(fake(seed=1)), measured(fake(seed=2)))
        self.assertTrue(r['comparable'])
        self.assertEqual(r['not_comparable'], [])
        self.assertTrue(r['rows'])

    def test_a_different_mode_is_refused(self):
        r = metrics.compare_case(measured(fake()), measured(fake(seed=1), mode='grid', grid=GRID, regions=4),
                                 measured(fake(seed=2)))
        self.assertFalse(r['comparable'])
        self.assertFalse(r['pass_metrics'])
        self.assertEqual(r['rows'], [])
        self.assertTrue(any('mode' in p for p in r['not_comparable']), r['not_comparable'])

    def test_a_different_grid_or_edge_set_is_refused(self):
        a = measured(fake(), mode='grid', grid=GRID, regions=4)
        b = measured(fake(seed=1), mode='grid', grid=dict(GRID, core_src=256), regions=16)
        r = metrics.compare_case(a, b, measured(fake(seed=2), mode='grid', grid=GRID, regions=4))
        self.assertFalse(r['comparable'])
        self.assertTrue(any('grid' in p for p in r['not_comparable']))
        r = metrics.compare_case(measured(fake()), measured(fake(seed=1), edges='e1'), measured(fake(seed=2)))
        self.assertFalse(r['comparable'])
        self.assertTrue(any('edge_set_hash' in p for p in r['not_comparable']))

    def test_identical_outputs_measured_differently_are_still_refused(self):
        a = measured(fake(sha='same'))
        b = measured(dict(fake(sha='same')), edges='other')
        r = metrics.compare_case(a, b, measured(fake(seed=2)))
        self.assertFalse(r['comparable'])
        self.assertFalse(r['pass_metrics'])

    def test_a_bundle_without_a_measurement_record_is_refused(self):
        b = fake(seed=1)
        b['report'] = {'worst': []}
        r = metrics.compare_case(measured(fake()), b, measured(fake(seed=2)))
        self.assertFalse(r['comparable'])


if __name__ == '__main__':
    unittest.main()
