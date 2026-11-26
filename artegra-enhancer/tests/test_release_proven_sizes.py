"""The Large-image engine's release sizes (engine/banded_plan.BANDED_PROVEN_MP; engine design section 0.3: "BANDED_PROVEN_MP per
machine class is the largest output that passed").

Until the release step the figures were 0 in every class, so a release build admitted no Large-image plan and every Large-image
row of the GPU proof ran in the developer channel. The release figures are the exact output size of the largest Large-image
row that ran in that machine class, on a plan of that class, and passed its registered job marks:

- pc64 (a 64 GB PC, cap 59.0): 13,056 x 16,320 px, an 8x row (R4a-s). Its 4x rows (R2a, R2b) and its 6x and 8x rows (R3a-s,
  R4b-s, R8-s, R8-w) also passed.
- pc48 (cap 45.2): 11,200 x 14,000 px, a 4x row (R6). The class is reached only as a lowered cap on a PC that Setup accepts
  (64 GB; installation.FLOOR_48_ON is off), which is what R6 ran.
- ws128 (cap 122.2): 10,240 x 12,800 px, an 8x row (W2b-1). No workstation row ran a larger Large-image plan.

Here: the figures, each row's own size planned on the Large-image engine at its class's cap with the class's committed node
table (as the service plans on that node), the next size up refused as not yet measured, and the release channel. Every plan
5.0.1 makes stays 5.0.1's (tests/test_engine_identity.py). Sizes only; no image is read."""
import unittest
from unittest import mock

from engine import banded_plan as B
from engine import planner
from service import build_channel
from tests.test_plan3_sizing import node_table

CAPS = {'pc64': 59.0, 'ws128': 122.2, 'pc48': 45.2}
FIGURES = {'pc64': 13056 * 16320 / 1e6, 'pc48': 11200 * 14000 / 1e6, 'ws128': 10240 * 12800 / 1e6}
# (input width, height, factor) of every Large-image row that passed, by the class it ran in
ROWS = {
    'pc64': [(3500, 2188, 4), (2800, 3500, 4), (2976, 1860, 6), (2304, 1440, 8), (1632, 2040, 8), (1824, 1824, 8)],
    'pc48': [(3500, 2188, 4), (2800, 3500, 4)],
    'ws128': [(3500, 2188, 4), (1280, 1600, 8)],
}
# the largest row of each class, one pixel wider: its output is over the figure
ABOVE = {'pc64': (1633, 2040, 8), 'pc48': (2801, 3500, 4), 'ws128': (1281, 1600, 8)}


class OnTheNode:
    """The class's committed table set, as the service sets it on that node; the shipped BANDED_PROVEN_MP untouched."""

    def __init__(self, mc):
        self.patches = [mock.patch.object(B, 'BXF_TABLE', node_table(mc)),
                        mock.patch.object(B, 'BXF_TABLE_SOURCE', 'committed')]

    def __enter__(self):
        for p in self.patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in reversed(self.patches):
            p.stop()


def out_mp(w, h, f):
    return w * f * h * f / 1e6


class TheReleaseFigures(unittest.TestCase):
    def test_each_class_is_its_largest_passed_output(self):
        self.assertEqual(set(B.BANDED_PROVEN_MP), set(FIGURES))
        for mc, mp in FIGURES.items():
            self.assertEqual(B.BANDED_PROVEN_MP[mc], mp, mc)
            self.assertEqual(max(out_mp(*r) for r in ROWS[mc]), mp, mc)

    def test_the_source_names_the_rows(self):
        for row in ('R4a-s', 'R6', 'W2b-1', '86eb9a49', '1f23f727', '962b87d9'):
            self.assertIn(row, B.BANDED_PROVEN_SOURCE)

    def test_a_release_build_takes_the_figures_as_they_are(self):
        self.assertEqual(build_channel.CHANNEL, 'release')
        before = dict(B.BANDED_PROVEN_MP)
        self.assertFalse(build_channel.apply_dev_proven())
        self.assertEqual(B.BANDED_PROVEN_MP, before)


class EveryPassedRowPlansOnItsClass(unittest.TestCase):
    def test_the_rows_plan_on_the_large_image_engine(self):
        for mc, rows in ROWS.items():
            cap = CAPS[mc]
            with OnTheNode(mc):
                for w, h, f in rows:
                    p = B.plan_banded(w, h, f, cap)
                    self.assertTrue(p.ok, (mc, w, h, f, p.reason))
                    self.assertEqual(p.output_size, (w * f, h * f))
                    self.assertEqual(p.banded['machine_class'], mc)

    def test_the_router_gives_them_to_the_large_image_engine_where_501_refuses(self):
        for mc, rows in ROWS.items():
            cap = CAPS[mc]
            with OnTheNode(mc):
                for w, h, f in rows:
                    old = planner.plan_501(w, h, f, ram_cap_gb=cap)
                    new = planner.plan(w, h, f, ram_cap_gb=cap)
                    if old.ok and old.peak_ram_gb <= cap:
                        self.assertEqual(new.engine, 'classic', (mc, w, h, f))      # 5.0.1 makes it: it stays 5.0.1's
                    else:
                        self.assertEqual(new.engine, 'banded', (mc, w, h, f))

    def test_on_a_64_gb_pc_the_4x_6x_and_8x_rows_are_large_image(self):
        with OnTheNode('pc64'):
            for w, h, f in ROWS['pc64']:
                self.assertEqual(planner.plan(w, h, f, ram_cap_gb=59.0).engine, 'banded', (w, h, f))

    def test_the_next_size_up_is_not_yet_measured(self):
        for mc, (w, h, f) in ABOVE.items():
            self.assertGreater(out_mp(w, h, f), FIGURES[mc])
            with OnTheNode(mc):
                p = B.plan_banded(w, h, f, CAPS[mc])
                self.assertFalse(p.ok, (mc, w, h, f))
                self.assertIn('has not yet been measured', p.reason)

    def test_without_a_table_nothing_large_image_starts_before_the_processor_check(self):
        """Fail closed: with no table for this processor (tier 3), the largest rows are refused until the check has run."""
        with mock.patch.object(B, 'BXF_TABLE', None), mock.patch.object(B, 'BXF_TABLE_SOURCE', None), \
                mock.patch.object(B, 'BXF_AVAILABLE', False):
            for w, h, f in ((2800, 3500, 4), (1632, 2040, 8), (1824, 1824, 8)):
                self.assertFalse(B.plan_banded(w, h, f, 59.0).ok, (w, h, f))


if __name__ == '__main__':
    unittest.main()
