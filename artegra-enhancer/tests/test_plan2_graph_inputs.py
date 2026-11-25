"""The finish inputs of a Large-image stage graph (engine/graph_banded.py; build wave 2, contract finish_inputs).

NODE_OPTIONAL['CUFinishBanded'] gains 'band_gb', 'processes' and 'finish_tier', appended in that order. build_stage passes all
three on every Large-image finish node from the plan constants 'bxf_band_gb', 'bxf_processes' and 'finish_tier' (the machine
class's band budget and process count; the 45.2 cap gives the 48 GB class's), and a graph built without those constants passes
none, so every graph built before them is unchanged. None of the three is a pixel constant: every other input value is the
same with or without them. Sizes only."""
import unittest
from unittest import mock

from engine import banded_plan as B
from engine import bands, controls, graph_banded, planner

BASE_OPTIONAL = ('protect', 'release', 'quantize_8bit', 'keep_blacks', 'clamp', 'lf', 'glow', 'fin_b0_hi', 'island_after_lf')
NEW = ('band_gb', 'processes', 'finish_tier')
HALO = ('dehalo', 'anchor', 'anchor_factor')        # Halo Reduction (beta)'s inputs, appended after them (13a)
PROVEN = {k: 10_000.0 for k in B.BANDED_PROVEN_MP}


def finish_nodes(g):
    return [n['inputs'] for n in g.values() if n['class_type'] == 'CUFinishBanded']


def stage_graphs(plan, protect=True):
    """Every prompt of every stage of a plan, as the service builds them (constants = the plan's own)."""
    req = {'protect': list(controls.PROTECT_ORDER)} if protect else {}
    params = controls.resolve(req)[0]
    out = []
    for st in plan.stages:
        pk = controls.stage_params(params, st.index)
        from fractions import Fraction
        f, s = Fraction(st.factor).limit_denominator(8), Fraction(st.supersample).limit_denominator(8)
        for part in (['A', 'B'] if st.split_finish else [None]):
            g, info = graph_banded.build_product('w/in.plane', st.padded_size[0], st.padded_size[1], pk, 'cu_j_i_s%d' % st.index,
                                                 'w/planes/s%d' % st.index, 'run1', f=f, s=s, constants=plan.banded, part=part,
                                                 output_size=tuple(st.output_size), live_preview='rough')
            out.append((st, part, g))
    return out


class TheSpec(unittest.TestCase):
    def test_appended_in_order(self):
        self.assertEqual(graph_banded.NODE_OPTIONAL['CUFinishBanded'], BASE_OPTIONAL + NEW + HALO)
        self.assertEqual(graph_banded.FINISH_INPUTS, (('bxf_band_gb', 'band_gb'), ('bxf_processes', 'processes'),
                                                     ('finish_tier', 'finish_tier')))
        self.assertEqual(tuple(k for k, _ in graph_banded.FINISH_INPUTS), B.FINISH_CONSTANTS)


class EveryFinishNode(unittest.TestCase):
    def test_at_the_machine_class_values(self):
        for cap, mc in ((122.2, 'ws128'), (59.0, 'pc64'), (45.2, 'pc48')):
            for on in (False, True):
                with mock.patch.object(B, 'BXF_AVAILABLE', on):
                    p = B.plan_forced(planner.plan(2048, 2048, 2, ram_cap_gb=cap), cap)
                self.assertTrue(p.ok, (cap, p.reason))
                n = 0
                for st, part, g in stage_graphs(p):
                    for fin in finish_nodes(g):
                        n += 1
                        self.assertEqual((fin['band_gb'], fin['processes'], fin['finish_tier']),
                                         (B.MACHINE_CLASSES[mc]['band_gb'], B.MACHINE_CLASSES[mc]['processes'],
                                          'bxf' if on else 'tier3'), (cap, on, st.index, part))
                        self.assertEqual(list(fin)[-3:], list(NEW))                     # appended after the base inputs
                        self.assertIn(fin['band_gb'], bands.BAND_BUDGETS_GB)
                        self.assertIn(fin['processes'], bands.PROCESS_COUNTS)
                self.assertGreaterEqual(n, 1)

    def test_split_stages_carry_them_in_part_b(self):
        with mock.patch.dict(B.BANDED_PROVEN_MP, PROVEN), mock.patch.object(B, 'BXF_AVAILABLE', True):
            p = B.plan_banded(2800, 3500, 6, 59.0)      # wave 3: 8x of 3500 x 2188 no longer fits a 64 GB PC (the refit)
        self.assertTrue(p.ok, p.reason)
        self.assertEqual([s.split_finish for s in p.stages][-1], True)
        parts = [(st.index, part, len(finish_nodes(g))) for st, part, g in stage_graphs(p)]
        self.assertIn((2, 'A', 0), parts)
        self.assertIn((2, 'B', 1), parts)
        for st, part, g in stage_graphs(p):
            for fin in finish_nodes(g):
                self.assertEqual((fin['band_gb'], fin['processes'], fin['finish_tier']), (3.0, 2, 'bxf'))

    def test_absent_without_the_constants_and_nothing_else_changes(self):
        p = controls.stage_params(controls.resolve({'protect': list(controls.PROTECT_ORDER)})[0], 0)
        none, _ = graph_banded.build_stage('in.plane', 1752, 1096, p, 'x', 'pl', 'r')
        base, _ = graph_banded.build_stage('in.plane', 1752, 1096, p, 'x', 'pl', 'r', constants=B.constants())
        for g in (none, base):
            self.assertEqual(len(finish_nodes(g)), 1)
            for fin in finish_nodes(g):
                self.assertEqual(set(fin) & set(NEW), set())
        consts = dict(B.constants(), machine_class='pc64', **B.finish_constants('pc64', 'bxf'))
        full, _ = graph_banded.build_stage('in.plane', 1752, 1096, p, 'x', 'pl', 'r', constants=consts)
        self.assertEqual(set(full), set(base))
        for k in base:
            a, b = base[k], full[k]
            if b['class_type'] == 'CUFinishBanded':
                b = {'class_type': b['class_type'], 'inputs': {x: v for x, v in b['inputs'].items() if x not in NEW}}
            self.assertEqual(a, b, k)

    def test_incomplete_or_unregistered_values_are_refused(self):
        p = controls.resolve({})[0]
        good = B.finish_constants('pc64', 'bxf')
        bad = [{'finish_tier': 'bxf'}, {'bxf_band_gb': 3.0, 'bxf_processes': 2},
               dict(good, bxf_band_gb=4.0), dict(good, bxf_processes=3), dict(good, finish_tier='ladder'),
               dict(good, finish_tier='tier1'), dict(good, bxf_processes=True), dict(good, bxf_band_gb='3')]
        for c in bad:
            with self.assertRaises(ValueError, msg=c):
                graph_banded.build_stage('in.plane', 1752, 1096, p, 'x', 'pl', 'r', constants=c)
        for c in (good, B.finish_constants('ws128', 'tier3'), B.finish_constants('pc48', 'bxf')):
            graph_banded.build_stage('in.plane', 1752, 1096, p, 'x', 'pl', 'r', constants=c)


if __name__ == '__main__':
    unittest.main()
