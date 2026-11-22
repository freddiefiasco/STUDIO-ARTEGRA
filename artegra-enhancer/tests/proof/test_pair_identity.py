"""Two proof-tool fixes on the stand-in engine of test_phase_run (no ComfyUI, no GPU; build wave 3, package proof):
- a Bolt pair's forced plan is made in the run mode 'fast' (phase_run.run_mode), as the packet builder registers it: the
  Large-image graph takes its mode from the plan's constants, so a Redux plan there built the Redux banded stage beside
  the classic Bolt stage (found while freezing the second GPU development run);
- PC10 of the wave-2 check: a compared pair whose two sides differ in seed, options, build, node or card (the card only
  unless the pair is cross-card) is void: refused with its reason and pass False (design 7.1, 7.4)."""
import json
import tempfile
import unittest
from pathlib import Path

from engine import graph_banded
from tests.proof.test_phase_run import SMALL, FakeEngine, fake_gate, fake_oracle_for, u8
from tools.proof import harness, packets, phase_run, registration

BUILD = {'git_head': None, 'channel': 'dev', 'tree': 'a' * 64, 'proof_tools': 'b' * 64}


def side(d, name, executor, options='base', seed=None, **extra):
    engines = []

    def launcher(ex, rd):
        engines.append(FakeEngine(ex, rd))
        return engines[-1]
    src = u8('source', (SMALL[0].h, SMALL[0].w, 3))
    rec = phase_run.run_side('t', SMALL, 59.0, src, Path(d) / name, launcher, executor, options, seed=seed)
    rec.update(extra)
    return rec, engines


class BoltMode(unittest.TestCase):
    def test_the_option_sets_run_mode(self):
        self.assertEqual(phase_run.run_mode('bolt'), 'fast')
        for o in ('base', 'live_detailed', 'stack_off', 'faster'):
            self.assertIsNone(phase_run.run_mode(o))

    def test_a_bolt_side_runs_the_bolt_banded_stage_of_the_registered_plan(self):
        with tempfile.TemporaryDirectory() as d:
            rec, engines = side(d, 'b', 'bes', 'bolt')
        self.assertNotIn('error', rec)
        want = harness.forced_plan(SMALL, 59.0, 'fast')
        self.assertEqual(rec['plan_forced'], phase_run.strip_for_json(want.to_dict()))
        self.assertEqual(rec['plan_forced']['banded']['mode'], 'bolt')
        self.assertEqual(rec['mode'], 'fast')
        self.assertEqual(graph_banded.stage_mode(want.banded), 'bolt')
        # the graph the worker got is the one packets registers for a Bolt BES run
        reg = packets.plan_record(want, 59.0, 'bes', 'bolt')
        self.assertEqual(reg['variant_constants']['mode'], 'bolt')
        self.assertEqual(rec['run']['stages'][0]['graph_sha256'], harness.graph_sha(engines[0].prompts[0]))
        redux = harness.forced_plan(SMALL, 59.0)
        self.assertNotEqual(registration.sha(redux.to_dict()), registration.sha(want.to_dict()))

    def test_a_bolt_pair_compares_bolt_with_bolt(self):
        with tempfile.TemporaryDirectory() as d:
            launched = []

            def launcher(ex, rd):
                launched.append(FakeEngine(ex, rd))
                return launched[-1]
            src = u8('source', (SMALL[0].h, SMALL[0].w, 3))
            rep = phase_run.run_pair('t', SMALL, 59.0, src, d, launcher, Path('.'), options='bolt', gate_fn=fake_gate,
                                     oracle_fn=fake_oracle_for([0]))
        self.assertEqual(rep['plan_forced']['banded']['mode'], 'bolt')
        bes = next(e for e in launched if e.ex == 'bes')
        self.assertIn('LoraLoaderModelOnly', {v['class_type'] for v in bes.prompts[0].values()})
        self.assertTrue(rep['pass'], json.dumps(rep.get('stages'), indent=1)[:2000])


class Void(unittest.TestCase):
    """PC10: compare_runs and compare_sides void a pair whose records differ (IDENTITY_RULE)."""

    @classmethod
    def setUpClass(cls):
        cls._d = tempfile.TemporaryDirectory()
        d = cls._d.name
        cls.c, _ = side(d, 'c', 'classic', build=BUILD, node='N1', card=0, card_uuid='GPU-a')
        cls.b, _ = side(d, 'b', 'bes', build=BUILD, node='N1', card=0, card_uuid='GPU-a')
        cls.b2, _ = side(d, 'b2', 'bes', build=BUILD, node='N1', card=1, card_uuid='GPU-b')
        cls.cs, _ = side(d, 'cs', 'classic', seed=20261120, build=BUILD, node='N1', card=0, card_uuid='GPU-a')

    @classmethod
    def tearDownClass(cls):
        cls._d.cleanup()

    def compare(self, c, b, **kw):
        with tempfile.TemporaryDirectory() as w:
            return phase_run.compare_runs('t', SMALL, 59.0, c, b, w, Path('.'), gate_fn=fake_gate,
                                          oracle_fn=fake_oracle_for([0]), **kw)

    def test_equal_records_compare(self):
        rep = self.compare(self.c, self.b)
        self.assertTrue(rep['pass'], rep.get('error'))
        self.assertNotIn('void', rep)

    def test_a_different_seed_build_node_or_card_is_void(self):
        cases = [(self.cs, self.b, 'seed'),
                 (dict(self.c, build=dict(BUILD, tree='c' * 64)), self.b, 'build'),
                 (dict(self.c, node='N2'), self.b, 'node'),
                 (self.c, self.b2, 'card'),
                 ({k: v for k, v in self.c.items() if k != 'build'}, self.b, 'build (recorded on one side only)'),
                 (dict(self.c, options='bolt'), self.b, 'options')]
        for c, b, what in cases:
            rep = self.compare(c, b)
            self.assertFalse(rep['pass'], what)
            self.assertTrue(rep.get('void'), what)
            self.assertIn(what, rep['error'])
            self.assertEqual(rep['stages'], [], what)                  # nothing compared

    def test_a_cross_card_pair_may_differ_in_card_only(self):
        rep = self.compare(self.c, self.b2, cross_card=True)
        self.assertTrue(rep['pass'], rep.get('error'))
        rep = self.compare(dict(self.c, node='N2'), self.b2, cross_card=True)
        self.assertTrue(rep.get('void'))

    def test_the_build_channel_counts_and_the_git_head_does_not(self):
        rep = self.compare(dict(self.c, build=dict(BUILD, git_head='abc')), self.b)
        self.assertTrue(rep['pass'], rep.get('error'))
        rep = self.compare(dict(self.c, build=dict(BUILD, channel='release')), self.b)
        self.assertTrue(rep.get('void'))

    def test_same_executor_identity_crosses_cards_but_not_builds_or_nodes(self):
        self.assertTrue(phase_run.compare_sides('t', SMALL, 59.0, self.b, self.b2)['pass'])
        rep = phase_run.compare_sides('t', SMALL, 59.0, self.b, dict(self.b2, build=dict(BUILD, tree='d' * 64)))
        self.assertFalse(rep['pass'])
        self.assertIn('build', rep['error'])
        rep = phase_run.compare_sides('t', SMALL, 59.0, self.b, dict(self.b2, node='N2'))
        self.assertIn('node', rep['error'])

    def test_void_reason_directly(self):
        self.assertIsNone(phase_run.void_reason({'seed': None}, {'seed': None}))
        self.assertIn('seed', phase_run.void_reason({'seed': 1}, {'seed': 2}))


if __name__ == '__main__':
    unittest.main()
