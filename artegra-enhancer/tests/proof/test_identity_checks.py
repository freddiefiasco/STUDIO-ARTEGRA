"""Checks that cannot pass by construction (D9) and the workstation pairs (W1, W2) with the cap of each machine class.

- FINISH_KEYS (the oracle finish's values) equals ClaudeV4Finish's non-image inputs as the classic pack declares them, read
  from node_pack/claude_creative/__init__.py by its syntax tree (no torch), and a pack with one more input is caught.
- Every pair stage's classic graph equals the graph the identity record's own builder (tests/fixtures/g0_identity.py
  product_graphs) makes for that stage, and, where the 5.0.1 record has the stage, 5.0.1's hash (the lean SAM read back as
  SAM3_Detect, the registered exception for inputs above SAM_STOCK_MAX_MP).
- harness.PAIRS holds W1 (4x of 3500 x 2188) and W2 (8x of 1280 x 1600) exactly as 5.0.1's planner makes them at the
  workstation's cap, and each pair's cap follows its machine class (pc64 59.0, ws128 122.2, pc48 45.2)."""
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from engine import banded_plan, planner
from tools.proof import classic, harness

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / 'tests' / 'fixtures'
RECORD = json.loads((FIX / 'g0_identity_5_0_1.json').read_text(encoding='utf8'))


def g0():
    spec = importlib.util.spec_from_file_location('g0_identity_for_proof_tests', FIX / 'g0_identity.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class FinishKeys(unittest.TestCase):
    def test_finish_keys_are_the_classic_finish_non_image_inputs(self):
        self.assertEqual(set(classic.FINISH_KEYS), set(classic.pack_finish_keys(ROOT)))
        self.assertEqual(len(classic.FINISH_KEYS), len(set(classic.FINISH_KEYS)))
        self.assertEqual(classic.finish_keys_problems(ROOT), [])

    def test_a_pack_with_one_more_finish_input_is_caught(self):
        with tempfile.TemporaryDirectory() as t:
            pack = Path(t) / 'node_pack' / 'claude_creative'
            pack.mkdir(parents=True)
            src = (ROOT / 'node_pack' / 'claude_creative' / '__init__.py').read_text(encoding='utf8')
            marker = '"release": ("MASK",), "island_after_lf"'
            self.assertEqual(src.count(marker), 1)
            (pack / '__init__.py').write_text(src.replace(marker, '"release": ("MASK",), "new_knob": ("FLOAT", {}), '
                                                                  '"island_after_lf"'), encoding='utf8')
            self.assertIn('new_knob', classic.pack_finish_keys(t))
            probs = classic.finish_keys_problems(t)
            self.assertTrue(any('new_knob' in p for p in probs), probs)
            (pack / '__init__.py').write_text(src.replace('"fin_b0_hi": ("FLOAT", {"default": 2.4, "min": 1.6, "max": 1000.0, '
                                                          '"step": 0.1}),', ''), encoding='utf8')
            self.assertTrue(any('fin_b0_hi' in p for p in classic.finish_keys_problems(t)))

    def test_image_and_mask_inputs_are_not_finish_values(self):
        keys = set(classic.pack_finish_keys(ROOT))
        self.assertFalse(keys & {'creative', 'structure', 'init', 'pre', 'protect', 'release'})


class ClassicGraphsAgainstTheRecordsBuilder(unittest.TestCase):
    def test_every_pair_stage_equals_the_identity_builders_graph(self):
        G = g0()
        base = RECORD['graphs']['base']
        found = []
        for name, stages in harness.PAIRS.items():
            for st in stages:
                g, _ = harness.classic_graph(st)
                pw, ph = st.padded
                rec = [x for x in G.product_graphs([(pw, ph, float(st.f), float(st.s), st.index)]) if x[0] == 'base']
                self.assertEqual(len(rec), 1, (name, st))
                self.assertEqual(harness.graph_sha(g), harness.graph_sha(rec[0][2]), f'{name} {harness.fixture_key(st)}')
                key = harness.fixture_key(st)
                if key in base:
                    self.assertEqual(harness.graph_sha(G.stock_view(g)), base[key], f'{name} {key} against 5.0.1')
                    found.append(key)
        self.assertIn('3500x2188/f2/s2/k0', found)

    def test_k1_5_is_checked_against_a_builder_that_is_not_the_harness(self):
        st = harness.PAIRS['k1.5'][0]
        self.assertNotIn(harness.fixture_key(st), RECORD['graphs']['base'])
        G = g0()
        pw, ph = st.padded
        (name, key, rec), = [x for x in G.product_graphs([(pw, ph, 1.5, 1.0, 2)]) if x[0] == 'base']
        self.assertEqual(key, '3008x2000/f1.5/s1/k2')
        g, _ = harness.classic_graph(st)
        self.assertEqual(harness.graph_sha(g), harness.graph_sha(rec))
        # a harness that named the stage differently would differ from the record's builder
        g2, _ = harness.classic_graph(harness.Stage(3000, 2000, '3/2', 1, 1))
        self.assertNotEqual(harness.graph_sha(g2), harness.graph_sha(rec))


class WorkstationPairs(unittest.TestCase):
    def test_w1_and_w2_are_the_plans_5_0_1_makes_at_the_workstation_cap(self):
        for name, (w, h, factor) in (('W1', (3500, 2188, 4)), ('W2', (1280, 1600, 8))):
            p = planner.plan_501(w, h, factor, ram_cap_gb=harness.cap_of('ws128'))
            self.assertTrue(p.ok)
            got = [(float(s.f), float(s.s), (s.w, s.h), s.padded, s.index) for s in harness.PAIRS[name]]
            want = [(s.factor, s.supersample, tuple(s.input_size), tuple(s.padded_size), s.index) for s in p.stages]
            self.assertEqual(got, want, name)
        self.assertEqual([float(s.s) for s in harness.PAIRS['W1']], [2.0, 1.0])
        self.assertEqual([float(s.s) for s in harness.PAIRS['W2']], [2.0, 2.0, 1.0])

    def test_the_workstation_pairs_split_every_stage_at_the_workstation_cap(self):
        for name in ('W1', 'W2'):
            self.assertEqual(harness.PAIR_CLASS[name], 'ws128')
            plan = harness.forced_plan(harness.PAIRS[name], harness.pair_cap(name))
            self.assertTrue(plan.ok, plan.reason)
            self.assertTrue(all(s.split_finish for s in plan.stages), name)
            self.assertEqual([harness.bes_parts(s) for s in plan.stages], [('A', 'B')] * len(plan.stages))

    def test_the_cap_follows_the_machine_class(self):
        self.assertEqual(harness.MACHINE_CLASS_CAPS, {'pc64': 59.0, 'ws128': 122.2, 'pc48': 45.2})
        for mc, cap in harness.MACHINE_CLASS_CAPS.items():
            self.assertEqual(banded_plan.machine_class(cap), mc)
            self.assertEqual(harness.cap_of(mc), cap)
        with self.assertRaises(ValueError):
            harness.cap_of('pc32')
        for name in ('k4', 'k3', 'k2', 'k1.5', 'chain4x'):
            self.assertEqual(harness.pair_cap(name), 59.0)
        self.assertEqual(harness.pair_cap('W1'), 122.2)
        self.assertEqual(harness.pair_cap('k4', 'pc48'), 45.2)          # R6's class, asked for explicitly

    def test_the_classic_plan_of_a_pair_is_the_planners(self):
        for name, (w, h, factor) in (('W1', (3500, 2188, 4)), ('W2', (1280, 1600, 8)), ('chain4x', (1280, 1600, 4))):
            p = planner.plan_501(w, h, factor, ram_cap_gb=122.2)
            c = harness.classic_plan_of(harness.PAIRS[name])
            self.assertEqual(c.to_dict()['stages'], p.to_dict()['stages'], name)
            self.assertEqual((c.factor, c.output_size), (p.factor, tuple(p.output_size)), name)

    def test_every_pair_has_a_class(self):
        self.assertEqual(set(harness.PAIR_CLASS), set(harness.PAIRS))


if __name__ == '__main__':
    unittest.main()
