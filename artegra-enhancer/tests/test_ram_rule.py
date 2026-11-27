"""Max's rule for 5.0.2 (27 Nov 2026): "a machine that has more ram than one tested should always be able to output at or
higher than the maximum output size of a tested machine with lower ram."

In the planner: a machine class's Large-image limit is the largest proven figure of that class and of every class with less
memory (banded_plan.class_limit_mp), and a plan may use the constants of a class with less memory whose own proof reached
the size (banded_plan.plan_classes). Checked here on OUTCOMES, not only the table: over the admission sweep's sizes, every
scale and a ladder of memory caps (every PC class the sweep has, more besides, and the caps either side of each class
boundary), with the processor table held fixed (none, each committed node table, the probe's best case), an image the
planner and the service's memory check admit at a smaller cap is admitted at every larger one. The card, Bolt and the
physical-memory checks are swept through Runner.create_job outside the suite (sweep_admission.py, ship-A). Sizes only."""
import unittest
from unittest import mock

from engine import banded_plan as B
from engine import planner
from engine.bxf import g1, g1_table
from service.media import ram_refusal
from service.settings import default_ram_cap_gb

# the admission sweep's sizes (research/v5-engine-20261119/lead-smallcard/sweep/sweep_admission.py full_sizes)
LISTED = [(800, 600), (1280, 1600), (1600, 1200), (1920, 1080), (2048, 2048), (2560, 1440), (2800, 3500), (3000, 2000),
          (3500, 2188), (3840, 2160), (4000, 3000), (5000, 3333), (6000, 4000), (8000, 5000)]
CAL_W = (512, 777, 1000, 1280, 1520, 1600, 2048, 2188, 2350, 2800, 3000, 3500, 3840, 4096, 5000, 6000)
CAL_H = (512, 777, 1080, 1600, 1762, 2188, 2400, 2800, 3500, 4000)
SIZES = LISTED + [(w, h) for w in CAL_W for h in CAL_H if (w, h) not in LISTED]
FACTORS = (2, 4, 6, 8)
# Windows' reported GiB of the sweep's PC classes (16, 32, 48, 64, 128 GB) and of 96 and 256 GB PCs, as caps
# (settings.default_ram_cap_gb), and the caps either side of each machine-class boundary (40, 52 and 100)
CAPS = sorted({default_ram_cap_gb(t) for t in (15.7, 31.7, 47.7, 61.5, 95.6, 127.3, 255.3)} |
              {39.9, 40.0, 51.9, 52.0, 99.9, 100.0})
ROWS = {      # (input width, height, factor) of every Large-image row that passed, by the class it ran in (PROOF.md)
    'pc64': [(3500, 2188, 4), (2800, 3500, 4), (2976, 1860, 6), (2304, 1440, 8), (1632, 2040, 8), (1824, 1824, 8)],
    'pc48': [(3500, 2188, 4), (2800, 3500, 4)],
    'ws128': [(3500, 2188, 4), (1280, 1600, 8)],
}
CLASS_CAP = {'pc48': 45.2, 'pc64': 59.0, 'ws128': 122.2}
TABLES = ('none', 'ws', 'node', 'probe')


def held_table(which):
    if which == 'none':
        return None
    if which == 'probe':
        return B.PROBE_TABLE
    t = g1_table.TABLES[{'ws': 1, 'node': 2}[which]]
    return g1.Table(t, env=dict(t['environment']))


class Held:
    """The processor table held fixed for every cap (as one computer with more or less memory would have it)."""

    def __init__(self, which):
        t = held_table(which)
        self.patches = [mock.patch.object(B, 'BXF_TABLE', t),
                        mock.patch.object(B, 'BXF_TABLE_SOURCE', None if t is None else 'committed'),
                        mock.patch.object(B, 'BXF_AVAILABLE', False)]

    def __enter__(self):
        for p in self.patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in reversed(self.patches):
            p.stop()


def admitted(w, h, f, cap):
    p = planner.plan(w, h, f, ram_cap_gb=cap)
    return p, bool(p.ok and ram_refusal(p, cap) is None)


class TheLimits(unittest.TestCase):
    def test_a_class_takes_at_least_every_smaller_class_s_proven_figure(self):
        for hi, mh in B.MACHINE_CLASSES.items():
            for lo, ml in B.MACHINE_CLASSES.items():
                if ml['ram_gb'] < mh['ram_gb']:
                    self.assertGreaterEqual(B.class_limit_mp(hi), B.BANDED_PROVEN_MP[lo], (hi, lo))
            self.assertGreaterEqual(B.class_limit_mp(hi), B.BANDED_PROVEN_MP[hi], hi)

    def test_the_release_limits(self):
        self.assertEqual(B.class_limit_mp('pc48'), 11200 * 14000 / 1e6)          # R6, its own
        self.assertEqual(B.class_limit_mp('pc64'), 13056 * 16320 / 1e6)          # R4a-s, its own
        self.assertEqual(B.class_limit_mp('ws128'), 13056 * 16320 / 1e6)         # R4a-s, the 64 GB PC's: above W2b-1's 131
        self.assertEqual(B.class_limit_mp(None), 0.0)

    def test_the_classes_a_plan_may_use(self):
        self.assertEqual(B.plan_classes('ws128', 122.5), ['ws128'])               # within its own proof: as before
        self.assertEqual(B.plan_classes('ws128', 156.8), ['pc64', 'pc48'])       # above W2b-1: the smaller PCs' proofs
        self.assertEqual(B.plan_classes('ws128', 213.0), ['pc64'])
        self.assertEqual(B.plan_classes('ws128', 213.1), [])
        self.assertEqual(B.plan_classes('pc64', 150.0), ['pc64'])
        self.assertEqual(B.plan_classes('pc48', 100.0), ['pc48'])
        self.assertEqual(B.plan_classes('pc48', 157.0), [])

    def test_a_developer_build_s_own_figures_follow_the_rule(self):
        proven = {'ws128': 640.0, 'pc64': 700.0, 'pc48': 100.0}
        self.assertEqual(B.class_limit_mp('ws128', proven), 700.0)
        self.assertEqual(B.class_limit_mp('pc48', proven), 100.0)
        with mock.patch.dict(B.BANDED_PROVEN_MP, proven):
            self.assertEqual(B.class_limit_mp('ws128'), 700.0)


class EverySmallerClassRowIsAdmittedAbove(unittest.TestCase):
    def test_each_passed_row_is_admitted_in_every_class_with_more_memory(self):
        for which in ('ws', 'node'):
            with Held(which):
                for lo, rows in ROWS.items():
                    for hi, mh in B.MACHINE_CLASSES.items():
                        if mh['ram_gb'] < B.MACHINE_CLASSES[lo]['ram_gb']:
                            continue
                        for w, h, f in rows:
                            p, ok = admitted(w, h, f, CLASS_CAP[hi])
                            self.assertTrue(ok, (which, lo, hi, w, h, f, p.reason or p.peak_ram_gb))

    def test_the_workstation_makes_the_64_gb_pc_s_4x_of_2800_x_3500(self):
        """Refused at 6e670e07 (131 MP was the workstation's limit); a 64 GB PC makes it (R2b)."""
        with Held('ws'):
            p, ok = admitted(2800, 3500, 4, 122.2)
            self.assertTrue(ok, p.reason)
            self.assertEqual(p.engine, 'banded')
            self.assertEqual(p.output_size, (11200, 14000))
            self.assertEqual(p.banded['machine_class'], 'pc64')                 # the constants R2b ran with
            self.assertEqual((p.banded['bxf_band_gb'], p.banded['bxf_processes']), (3.0, 2))

    def test_the_workstation_keeps_its_own_constants_where_its_proof_reached(self):
        with Held('ws'):
            p = B.plan_banded(4096, 512, 8, 122.2)                            # 134 MP? no: 32768 px wide, refused
            q = B.plan_banded(2048, 1000, 8, 122.2)                           # 16,384 x 8,000 px, 131.07 MP
            self.assertFalse(p.ok)
            self.assertTrue(q.ok, q.reason)
            self.assertEqual(q.banded['machine_class'], 'ws128')

    def test_above_every_proof_is_still_refused(self):
        with Held('ws'):
            p = B.plan_banded(1633, 2040, 8, 122.2)
            self.assertFalse(p.ok)
            self.assertIn('has not yet been measured', p.reason)


class MoreMemoryNeverRefusesWhatLessAdmits(unittest.TestCase):
    """The outcome sweep: for every size, scale and held table, admitted at a cap implies admitted at every larger cap."""

    def test_admission_is_monotone_in_memory(self):
        inversions, admitted_large = [], 0
        for which in TABLES:
            with Held(which):
                for w, h in SIZES:
                    for f in FACTORS:
                        seen = None
                        for cap in CAPS:
                            p, ok = admitted(w, h, f, cap)
                            admitted_large += ok and p.engine == 'banded'
                            if seen is not None and not ok:
                                inversions.append((which, w, h, f, seen, cap, p.reason or p.peak_ram_gb))
                            if ok and seen is None:
                                seen = cap
        self.assertEqual(inversions, [], inversions[:8])
        self.assertGreater(admitted_large, 0)                  # the sweep reaches the Large-image engine


if __name__ == '__main__':
    unittest.main()
