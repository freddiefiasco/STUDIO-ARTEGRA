"""Gate G7's tool (tools/gate_g7.py) and the Brownian-cache cap (node_pack/claude_banded/noise_banded.py), on the CPU with
ComfyUI's own BrownianTreeNoiseSampler (compiled from the shipped file) and torchsde 0.2.6:
- the quick run gives PASS: every draw with the cache at 8 (plain, and under the classic prefetch) equals the stock draw at 45;
- the tool reports FAIL when a variant's draws differ (a perturbed stand-in), so a PASS means something;
- the cap is set before the first draw (a tree already queried is refused), cache 45 installs nothing, a cap that cannot
  be installed (another noise patch active) stops the run, uninstall puts the stock class back, the torchsde version is checked.
The full gate (3 latent sizes up to a 50 MP render, 3 seeds, 3 schedules) is run as `python -B tools/gate_g7.py --comfy ...`;
its verdict is recorded in the package's dev runs. Skipped where torch, torchsde or CU_COMFY_SOURCE is missing."""
import importlib.util
import sys
import types
import unittest
from unittest import mock

from tests.worker.test_sam_lean import COMFY

HAVE = all(importlib.util.find_spec(m) is not None for m in ('torch', 'torchsde'))


@unittest.skipUnless(HAVE and COMFY, 'needs torch, torchsde and CU_COMFY_SOURCE (the runtime ComfyUI folder)')
class GateG7(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch
        from tools import gate_g7
        cls.torch, cls.g7 = torch, gate_g7
        cls.ks = gate_g7.sampling_module(COMFY)
        cls.nb = gate_g7.banded_noise_module()

    def test_quick_run_passes(self):
        v = self.g7.run(COMFY, self.g7.QUICK_SIZES[:2], self.g7.QUICK_SEEDS, log=lambda *a: None)
        self.assertEqual(v['verdict'], 'PASS')
        self.assertTrue(v['identical'])
        self.assertEqual(len(v['cases']), 2 * 3 * 2)
        for row in v['cases']:
            self.assertEqual([row[k] for k in self.g7.VARIANTS], [0, 0, 0], row)
            self.assertGreaterEqual(row['draws'], 29)
        self.assertEqual(v['cache_compared'], [45, 8])

    def test_a_difference_is_a_failure(self):
        real = self.nb.make_class

        def perturbed(base, n):
            cls = real(base, n)

            class Off(cls):
                def __call__(self, s, sn):
                    return super().__call__(s, sn) * 1.0000001
            return Off
        with mock.patch.object(self.nb, 'make_class', perturbed):
            v = self.g7.run(COMFY, self.g7.QUICK_SIZES[:1], self.g7.QUICK_SEEDS[:1], denoise=(1.0,), log=lambda *a: None)
        self.assertEqual(v['verdict'], 'FAIL')
        self.assertGreater(v['cases'][0]['capped8'], 0)

    def test_the_cap_comes_before_the_first_draw(self):
        torch = self.torch
        x = torch.zeros(1, 4, 16, 16)
        ns = self.nb.make_class(self.ks.BrownianTreeNoiseSampler, 8)(x, torch.tensor(0.03), torch.tensor(14.6), seed=5, cpu=True)
        iv = ns.tree.trees[0]._interval
        self.assertEqual(iv._cache_size, 8)
        self.assertEqual(iv._increment_and_space_time_levy_area_cache._max_size, 8)
        stock = self.ks.BrownianTreeNoiseSampler(x, torch.tensor(0.03), torch.tensor(14.6), seed=5, cpu=True)
        self.assertEqual(stock.tree.trees[0]._interval._cache_size, 45)
        stock(torch.tensor(14.6), torch.tensor(9.0))
        with self.assertRaises(RuntimeError):
            self.nb.cap_tree(stock.tree.trees[0], 8)

    def test_install_and_uninstall(self):
        torch = self.torch
        ks = self.ks
        stock = ks.BrownianTreeNoiseSampler
        pkg, sub = types.ModuleType('comfy'), types.ModuleType('comfy.k_diffusion')
        pkg.__path__, sub.__path__ = [], []
        pkg.k_diffusion, sub.sampling = sub, ks
        classic = self.g7.classic_pack_stand_in()
        mods = {'comfy': pkg, 'comfy.k_diffusion': sub, 'comfy.k_diffusion.sampling': ks, classic.__name__: classic}
        sig = self.g7.schedule(ks, 30, 1.0, *self.g7.sdxl_sigma_range())
        with mock.patch.dict(sys.modules, mods):
            with self.assertRaises(ValueError):
                self.nb.install(sig, 45)
            for prefetch in (False, True):
                h = self.nb.install(sig, 8, prefetch=prefetch)
                self.assertIsNot(ks.BrownianTreeNoiseSampler, stock)
                self.assertEqual(ks.BrownianTreeNoiseSampler._claude_brownian_cache if not prefetch else 8, 8)
                with self.assertRaises(RuntimeError):                             # a patch is already active: no silent
                    self.nb.install(sig, 8)                                       # uncapped run
                st = h.uninstall()
                self.assertIs(ks.BrownianTreeNoiseSampler, stock)
                self.assertEqual(st['brownian_cache'], 8)
            import torchsde
            with mock.patch.object(torchsde, '__version__', '0.2.7'):
                with self.assertRaises(RuntimeError):
                    self.nb.install(sig, 8)
            self.assertIs(ks.BrownianTreeNoiseSampler, stock)


class TheRuntimeVerdict(unittest.TestCase):
    """The verdict recorded from the worker runtime (tests/fixtures/plan2_g7_runtime.json, build wave 2) is the tool's full
    gate: every latent size, schedule and seed of tools/gate_g7.py, every variant, in the tool's order. Needs no torch."""

    def test_it_is_the_full_gate(self):
        import itertools
        import json
        from pathlib import Path
        from tools import gate_g7
        v = json.loads((Path(__file__).resolve().parents[1] / 'fixtures' / 'plan2_g7_runtime.json').read_text(encoding='utf8'))
        want = [(list(size), d, seed) for size, d, seed in itertools.product(gate_g7.SIZES, gate_g7.DENOISE, gate_g7.SEEDS)]
        self.assertEqual([(c['latent'], c['denoise'], c['seed']) for c in v['cases']], want)
        self.assertEqual(v['steps'], gate_g7.STEPS)
        self.assertEqual(v['cache_compared'], [45, gate_g7.CAP])
        for c in v['cases']:
            self.assertEqual(set(gate_g7.VARIANTS) - set(c), set())
        self.assertFalse(v['quick'])
        self.assertTrue(v['torch'].startswith('2.14.1'))


if __name__ == '__main__':
    unittest.main()
