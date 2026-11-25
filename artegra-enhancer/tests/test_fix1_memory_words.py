"""The Large-image memory refusal states the comparison admission makes (eng:check CHK-1, WP4P-C5).

Admission refuses when 1.05 x the upper bound (unrounded, `admit`) is over the cap less CAP_SPARE_GB. Until CHK-1 the words
rounded admit and compared it with the cap, so an image refused at the boundary read as if it fitted ('needs about 58 GB ...
more than the 59 GB it may use'). The sentence now states admit rounded up and the cap less CAP_SPARE_GB rounded down
(banded_plan.memory_figures), in plan_banded and in plan_forced's developer sentence: on every machine class, an image whose
admit lies just under the cap, and one just above it, reads a need greater than the limit, and the limit is the cap less
CAP_SPARE_GB. Planned with each class's committed node table (tests/test_plan3_sizing.py), BANDED_PROVEN_MP lifted, as the
service plans on that node. Sizes and GiB only."""
import math
import re
import unittest
from unittest import mock

from engine import banded_plan as B
from engine import planner
from tests.test_plan3_sizing import node_table

PROVEN = {k: 10_000.0 for k in B.BANDED_PROVEN_MP}
CAPS = {'pc64': 59.0, 'ws128': 122.2, 'pc48': 45.2}
# 4x sizes per class: one whose admit lies in (cap - 1, cap] (the check's reproductions), one just above the cap
BOUNDARY = {'pc64': ((4684, 2927), (4740, 2962)), 'ws128': ((4300, 2687), (4328, 2704)),
            'pc48': ((3788, 2367), (4028, 2517))}
MEM = re.compile(r'needs about (\d+) GB of memory with the Large-image engine to make [\d,]+ × [\d,]+ px, more than the '
                 r'(\d+) GB it may use on this computer\.$')


class OnTheNode:
    """BANDED_PROVEN_MP lifted and the class's committed table set, as tests/test_plan2_model_terms.check_rows plans."""

    def __init__(self, mc):
        if mc is None:              # the fail-closed default: no table applies, tier 3
            self.patches = [mock.patch.dict(B.BANDED_PROVEN_MP, PROVEN), mock.patch.object(B, 'BXF_TABLE', None),
                            mock.patch.object(B, 'BXF_TABLE_SOURCE', None), mock.patch.object(B, 'BXF_AVAILABLE', False)]
            return
        self.patches = [mock.patch.dict(B.BANDED_PROVEN_MP, PROVEN), mock.patch.object(B, 'BXF_TABLE', node_table(mc)),
                        mock.patch.object(B, 'BXF_TABLE_SOURCE', 'committed')]

    def __enter__(self):
        for p in self.patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in reversed(self.patches):
            p.stop()


def raw_stages(w, h, factor):
    cur, out = (w, h), []
    for i, f in enumerate(planner.STAGE_FACTORS[factor]):
        st = B.stage_choice(cur, f, i)
        out.append(st)
        cur = st['output_size']
    return out


def admit_of(raw, cap):
    """The figure admission compares with cap - CAP_SPARE_GB (plan_banded's and plan_forced's `admit`), planned now."""
    tier, table, _ = B.table_state()
    _, uppers = B._banded_stages(raw, B.machine_class(cap), cap, tier, 0.0, table, 'redux')
    return B.MARGIN * max(uppers)


def figures(case, reason):
    m = MEM.search(reason or '')
    case.assertIsNotNone(m, reason)
    return int(m.group(1)), int(m.group(2))


class TheBoundaryOnEachClass(unittest.TestCase):
    def check(self, mc, size, inside):
        cap = CAPS[mc]
        with OnTheNode(mc):
            self.assertEqual(B.machine_class(cap), mc)
            admit = admit_of(raw_stages(size[0], size[1], 4), cap)
            p = B.plan_banded(size[0], size[1], 4, cap)
        if inside:
            self.assertTrue(cap - 1.0 < admit <= cap, (mc, size, admit))      # the boundary this test is about
        else:
            self.assertTrue(cap < admit < cap + 1.0, (mc, size, admit))       # just above the cap
        self.assertFalse(p.ok, (mc, size))
        need, limit = figures(self, p.reason)
        self.assertGreater(need, limit, p.reason)                            # never reads as if it fits
        self.assertEqual(limit, math.floor(cap - B.CAP_SPARE_GB), p.reason)  # the figure admission compares with
        self.assertEqual(need, math.ceil(admit), p.reason)
        self.assertEqual((need, limit), B.memory_figures(admit, cap))

    def test_pc64(self):
        self.check('pc64', BOUNDARY['pc64'][0], True)
        self.check('pc64', BOUNDARY['pc64'][1], False)

    def test_ws128(self):
        self.check('ws128', BOUNDARY['ws128'][0], True)
        self.check('ws128', BOUNDARY['ws128'][1], False)

    def test_pc48(self):
        self.check('pc48', BOUNDARY['pc48'][0], True)
        self.check('pc48', BOUNDARY['pc48'][1], False)

    def test_the_words_are_the_rule(self):
        """memory_figures over admit values around the limit: refused exactly when need > limit can be read."""
        for cap in (45.2, 59.0, 122.2, 60.0, 100.05):
            lim = cap - B.CAP_SPARE_GB
            for admit in (lim - 0.5, lim - 1e-9, lim + 1e-9, lim + 0.01, lim + 0.49, lim + 0.5, lim + 0.99, cap, cap + 0.3):
                need, limit = B.memory_figures(admit, cap)
                self.assertEqual(limit, math.floor(lim))
                if admit > lim:                       # refused: the words must read as not fitting
                    self.assertGreater(need, limit, (cap, admit))


class EveryMemoryRefusal(unittest.TestCase):
    """Over a grid of sizes near each class's limit, with its node table and with the fail-closed default: every memory
    refusal reads a need greater than its limit, and its limit is the cap less CAP_SPARE_GB rounded down."""

    def test_over_a_grid(self):
        seen = 0
        for mc, cap in CAPS.items():
            (w0, h0), _ = BOUNDARY[mc]
            for node in (True, False):
                with OnTheNode(mc if node else None):
                    for dw in range(-400, 401, 40):
                        w = w0 + dw
                        for h in (round(h0 * w / w0), w):
                            p = B.plan_banded(w, h, 4, cap)
                            if p.ok or not MEM.search(p.reason or ''):
                                continue
                            need, limit = figures(self, p.reason)
                            self.assertGreater(need, limit, (mc, node, w, h, p.reason))
                            self.assertEqual(limit, math.floor(cap - B.CAP_SPARE_GB), (mc, node, w, h))
                            seen += 1
        self.assertGreater(seen, 30)


class TheDeveloperComparisonRun(unittest.TestCase):
    """plan_forced's sentence states the same figures, swept over caps through the boundary: at the last refused cap the
    forced plan's admit lies in (cap - 1, cap]. Plans 5.0.1 runs at 122.2, forced onto the Large-image executor: on pc48
    with its node table; on pc64 and ws128 at the fail-closed default (tier 3, no table), because with their node tables no
    classic plan's forced admit reaches those classes' caps (plan_forced then refuses nothing for memory there)."""

    def test_at_the_boundary_on_each_class(self):
        for mc, (lo, hi), (w, h, f), node in (('pc48', (40.0, 52.0), (2350, 1762, 6), True),
                                              ('pc64', (52.0, 70.0), (2048, 2048, 4), False),
                                              ('ws128', (100.0, 130.0), (2350, 1762, 6), False)):
            c = planner.plan(w, h, f, ram_cap_gb=122.2)
            self.assertTrue(c.ok and c.engine == 'classic')
            raw = [dict(index=s.index, factor=s.factor, supersample=s.supersample, input_size=tuple(s.input_size),
                        padded_size=tuple(s.padded_size), render_size=tuple(s.render_size),
                        output_size=tuple(s.output_size)) for s in c.stages]
            hit = 0
            with OnTheNode(mc if node else None):
                self.assertEqual(B.table_state()[0], 'bxf' if node else 'tier3')
                caps = [round(lo + 0.1 * i, 1) for i in range(int(round((hi - lo) * 10)))]
                for cap in caps:
                    if B.machine_class(cap) != mc:
                        continue
                    p = B.plan_forced(c, cap)
                    if p.ok:
                        continue
                    if 'developer comparison run' not in (p.reason or ''):
                        continue
                    need, limit = figures(self, p.reason)
                    self.assertGreater(need, limit, (mc, cap, p.reason))
                    self.assertEqual(limit, math.floor(cap - B.CAP_SPARE_GB), (mc, cap))
                    admit = admit_of(raw, cap)
                    self.assertEqual(need, math.ceil(admit), (mc, cap))
                    hit += cap - 1.0 < admit <= cap
            self.assertGreater(hit, 0, mc)              # the boundary itself was planned on this class


if __name__ == '__main__':
    unittest.main()
