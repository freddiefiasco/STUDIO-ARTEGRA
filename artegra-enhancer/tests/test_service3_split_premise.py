"""5.0.2 build wave 3 (BUILD-WAVE-3 contracts.split_premise): the split tests (tests/test_integ_large_image_job.py and the
real-service tests/service/test_integ_large_image.py, test_admission_service.py SplitRestartAndResume and
test_banded_service.py's 32,000 px case) choose their strip height from the planner at run time
(tests/service/helpers.split_strip_height), with the premise asserted on the plan the job made, so a refit of the memory
model (the plan package) moves the height and does not turn them red. Sizes only."""
import unittest
from unittest import mock

from engine import banded_plan, planner
from tests.service import helpers

WS_CAP = 122.2           # settings.default_ram_cap_gb on a 128 GB computer


class TheHeightFollowsThePlanner(unittest.TestCase):
    def splits(self, h, cap=WS_CAP):
        with mock.patch.dict(banded_plan.BANDED_PROVEN_MP, helpers.DEV_PROVEN), \
                mock.patch.object(banded_plan, 'BXF_AVAILABLE', False):
            p = planner.plan(helpers.SPLIT_WIDTH, h, helpers.SPLIT_FACTOR, ram_cap_gb=cap)
        return p.ok and p.engine == 'banded' and all(s.split_finish for s in p.stages)

    def test_the_smallest_listed_height_that_splits_every_pass(self):
        h = helpers.split_strip_height(WS_CAP)
        self.assertIsNotNone(h)
        self.assertTrue(self.splits(h))
        for lower in [x for x in helpers.SPLIT_HEIGHTS if x < h]:
            self.assertFalse(self.splits(lower), lower)

    def test_a_refit_moves_the_height(self):
        """A model in which only a finish of at least 1,024 rows binds: every pass of 8x splits from 512 px up."""
        def split_needed(st, mclass, cap, *a, **k):
            get = (lambda k: st[k]) if isinstance(st, dict) else (lambda k: getattr(st, k))
            return get('output_size')[1] >= 1024
        with mock.patch.object(banded_plan, 'split_needed', split_needed):
            self.assertEqual(helpers.split_strip_height(WS_CAP), 512)
        with mock.patch.object(banded_plan, 'split_needed', lambda *a, **k: False):
            self.assertIsNone(helpers.split_strip_height(WS_CAP))           # the tests then say so, never a silent pass

    def test_the_service_planner_is_used_not_this_processs_patches(self):
        with mock.patch.object(banded_plan, 'BXF_AVAILABLE', True), \
                mock.patch.dict(banded_plan.BANDED_PROVEN_MP, {'ws128': 0.0, 'pc64': 0.0, 'pc48': 0.0}):
            self.assertEqual(helpers.split_strip_height(WS_CAP), helpers.split_strip_height(WS_CAP, bxf_available=False))
            self.assertIsNone(helpers.split_strip_height(WS_CAP, service=False))     # nothing proven in this process
        self.assertEqual(banded_plan.BXF_AVAILABLE, False)


if __name__ == '__main__':
    unittest.main()
