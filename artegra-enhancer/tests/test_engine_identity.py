"""5.0.2's identity rule (engine design, section 3): every plan 5.0.1 makes keeps its plan, its graphs byte for byte and so its
pixels. The Large-image engine takes only plans 5.0.1 refuses.

- G0a: planner.plan's dict equals the published planner's (tests/fixtures/planner_5_0_1.py, engine/planner.py of 5.0.1
  verbatim) on a grid of sizes x factors x caps wherever 5.0.1 accepts, and wherever it refuses while the Large-image engine
  is unproven; plan_501's source is 5.0.1's plan() text; the 5.0.0-beta.1 plans the Beta ran still plan the same stages.
- G0b: the sha256 of every pass graph of those plans, across the product's option sets, equals the record made from the 5.0.1
  tree (tests/fixtures/g0_identity_5_0_1.json, written by tests/fixtures/g0_identity.py from the 5.0.1 tree, read-only).
- G0c: the classic engine's files (graph builders, Bolt recipe, node pack and its manifest) are byte-identical to 5.0.1's.

Sizes only; no image is read."""
import importlib.util
import inspect
import json
import unittest
from pathlib import Path
from unittest import mock

from engine import banded_plan, controls, planner
from service import settings

ROOT = Path(__file__).resolve().parents[1]
FIX = Path(__file__).parent / 'fixtures'


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


P501 = _load('planner_5_0_1_fixture', FIX / 'planner_5_0_1.py')
BETA = _load('beta_planner_for_identity', FIX / 'beta_planner_5_0_0b1.py')
G0 = _load('g0_identity_for_tests', FIX / 'g0_identity.py')
RECORD = json.loads((FIX / 'g0_identity_5_0_1.json').read_text(encoding='utf8'))

SIZES = [(w, h) for w in (64, 512, 777, 1000, 1280, 1600, 2048, 2188, 2800, 3000, 3500, 3840, 4096, 5000, 6000, 8000)
         for h in (64, 512, 777, 1600, 2188, 2400, 2800, 3500, 4000, 5000)]
CAPS = (None, 45.2, 59.0, 61.2, 100.0, 122.2)


class G0aThePlannerIs501(unittest.TestCase):
    def test_every_plan_501_accepts_is_501s_dict(self):
        n = 0
        for w, h in SIZES:
            for f in controls.SCALES:
                for cap in CAPS:
                    old = P501.plan(w, h, f, ram_cap_gb=cap)
                    if not (old.ok and (cap is None or old.peak_ram_gb <= cap)):
                        continue
                    n += 1
                    new = planner.plan(w, h, f, ram_cap_gb=cap)
                    self.assertEqual(new.to_dict(), old.to_dict(), (w, h, f, cap))
                    self.assertEqual(new.engine, 'classic', (w, h, f, cap))
                    self.assertNotIn('engine', new.to_dict())
                    self.assertNotIn('banded', new.to_dict())
        self.assertGreater(n, 800)

    def test_every_plan_501_refuses_is_501s_refusal_while_the_new_engine_is_unproven(self):
        self.assertEqual(set(banded_plan.BANDED_PROVEN_MP.values()), {0.0})      # the shipped default: nothing proven
        n = 0
        for w, h in SIZES:
            for f in controls.SCALES:
                for cap in CAPS:
                    old = P501.plan(w, h, f, ram_cap_gb=cap)
                    if old.ok and (cap is None or old.peak_ram_gb <= cap):
                        continue
                    n += 1
                    self.assertEqual(planner.plan(w, h, f, ram_cap_gb=cap).to_dict(), old.to_dict(), (w, h, f, cap))
        self.assertGreater(n, 100)

    def test_plan_501_is_the_published_plan_text(self):
        new = inspect.getsource(planner.plan_501).replace('def plan_501(', 'def plan(', 1)
        self.assertEqual(new, inspect.getsource(P501.plan))
        for name in ('stage_peak_gb', 'stage_peak', '_pad_unit', '_pad_to', 'stage_minutes', '_lists'):
            self.assertEqual(inspect.getsource(getattr(planner, name)), inspect.getsource(getattr(P501, name)), name)
        for name in ('STAGE_FACTORS', 'SUPERSAMPLES', 'RENDER_CAP_MP', 'STAGE_OUTPUT_CAP_MP', 'MIN_SIDE', 'MAX_INPUT_MP',
                     'MAX_SIDE', 'PEAK_BASE_GB', 'PEAK_PER_RENDER_MP', 'PEAK_PER_OUTPUT_MP', 'PEAK_PER_INPUT_MP', 'PEAK_MARGIN'):
            self.assertEqual(getattr(planner, name), getattr(P501, name), name)

    def test_the_fixture_is_501s_planner(self):
        self.assertEqual(G0._file_sha(FIX / 'planner_5_0_1.py'), RECORD['planner_sha256'])

    def test_a_classic_record_reads_back_as_classic(self):
        d = planner.plan(2048, 2048, 2, ram_cap_gb=59.0).to_dict()
        self.assertFalse(banded_plan.is_banded(d))
        self.assertFalse(banded_plan.is_banded(json.loads(json.dumps(d))))

    def test_the_betas_plans_keep_their_stages(self):
        for total in (47.7, 61.56, 127.37):
            cap = settings.default_ram_cap_gb(total)
            for w, h in SIZES:
                for f in controls.SCALES:
                    old = BETA.plan(w, h, f)
                    if not old.ok or old.peak_ram_gb > settings.beta_default_ram_cap_gb(total):
                        continue
                    new = planner.plan(w, h, f, ram_cap_gb=cap)
                    self.assertEqual([(s.factor, s.supersample, s.padded_size, s.render_size, s.output_size) for s in new.stages],
                                     [(s.factor, s.supersample, s.padded_size, s.render_size, s.output_size) for s in old.stages])
                    self.assertEqual(new.engine, 'classic')

    def test_with_the_new_engine_proven_501s_plans_are_still_501s(self):
        """Even with the Large-image engine admitted at every size, no plan 5.0.1 accepts moves to it (section 3.1)."""
        big = {k: 10_000.0 for k in banded_plan.BANDED_PROVEN_MP}
        with mock.patch.dict(banded_plan.BANDED_PROVEN_MP, big):
            for w, h in SIZES:
                for f in controls.SCALES:
                    for cap in CAPS:
                        old = P501.plan(w, h, f, ram_cap_gb=cap)
                        if old.ok and (cap is None or old.peak_ram_gb <= cap):
                            self.assertEqual(planner.plan(w, h, f, ram_cap_gb=cap).to_dict(), old.to_dict(), (w, h, f, cap))


class G0bGraphsAre501s(unittest.TestCase):
    """The graphs of the 5.0.1 tree's plans, recomputed with this tree's builders, equal the 5.0.1 record byte for byte."""

    @classmethod
    def setUpClass(cls):
        cls.now = G0.compute(ROOT)

    def test_counts(self):
        self.assertEqual(self.now['counts'], RECORD['counts'])
        self.assertGreater(RECORD['counts']['graphs'], 1500)

    def test_every_pass_graph(self):
        for name, rec in RECORD['graphs'].items():
            got = self.now['graphs'][name]
            diff = sorted(k for k in rec if got.get(k) != rec[k])
            self.assertEqual(diff, [], name)
            self.assertEqual(sorted(got), sorted(rec), name)

    def test_chains_and_previews(self):
        self.assertEqual(self.now['other_graphs'], RECORD['other_graphs'])

    def test_the_plans_of_the_record(self):
        self.assertEqual(self.now['plans'], RECORD['plans'])


class G0cClassicFilesAreFrozen(unittest.TestCase):
    def test_frozen_files(self):
        for rel, sha in RECORD['frozen'].items():
            self.assertEqual(G0._file_sha(ROOT / rel), sha, rel)

    def test_the_classic_node_pack_is_its_manifest(self):
        from service import config
        res = config.verify_node_pack(ROOT / 'node_pack' / 'claude_creative')
        self.assertTrue(res['ok'], res)
        self.assertEqual(res['tree_sha256'], json.loads((ROOT / 'node_pack' / 'MANIFEST.json').read_text())['tree_sha256'])


if __name__ == '__main__':
    unittest.main()
