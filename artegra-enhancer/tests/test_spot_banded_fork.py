"""The spot fork's guards (engine design section 3: G0e, G0f). Sizes only; no torch.

G0e: node_pack/claude_banded/spot_banded.py is node_pack/claude_creative/spot.py plus the registered hunks: their unified diff
equals tests/fixtures/spot_banded_5_0_2.diff, so an edit to either file fails here until both (and the fixture) are updated.
The registered hunks change only how a ControlNet hint reaches a window, and add the coverage mark, the static split, the
Brownian cache input and the lazy torch import; nothing else of the classic sampler loop differs.
G0f: a Balanced Large-image graph has batch_windows 1 in every spot node; a two-card graph has window_split, the static
balance and one MultiGPU_WorkUnits per spot node, whose output every sampler takes; the fork declares every input those set;
classic graphs are untouched by either (G0b keeps their hashes)."""
import difflib
import re
import unittest

from engine import controls, graph_banded, graph_v5t
from service import memory_policy
from tests import test_gpu_nodes_helpers as H

FIX = H.ROOT / 'tests' / 'fixtures' / 'spot_banded_5_0_2.diff'
SPOT = H.ROOT / 'node_pack' / 'claude_creative' / 'spot.py'
FORK = H.ROOT / 'node_pack' / 'claude_banded' / 'spot_banded.py'


def text(p):
    return p.read_text(encoding='utf8').replace('\r\n', '\n')


def fork_diff():
    return ''.join(difflib.unified_diff(text(SPOT).splitlines(True), text(FORK).splitlines(True),
                                        'node_pack/claude_creative/spot.py', 'node_pack/claude_banded/spot_banded.py', n=2))


class G0eTheForkIsSpotPlusTheRegisteredHunks(unittest.TestCase):
    def test_the_diff_equals_the_registered_patch(self):
        self.assertEqual(fork_diff(), text(FIX))

    def test_the_registered_patch_is_what_it_says(self):
        d = text(FIX)
        removed = [l[1:] for l in d.splitlines() if l.startswith('-') and not l.startswith('---')]
        added = [l[1:] for l in d.splitlines() if l.startswith('+') and not l.startswith('+++')]
        # what leaves the classic code: its docstring and torch import, its class name and category, the classic module
        # lookups, the whole-canvas hint (common_upscale + preprocess + .to) and the whole-hint copy per card
        self.assertEqual(sorted(x.strip() for x in removed if x.strip()), sorted([
            '"""Spot implementation."""', 'import torch', 'class ClaudeSpotTiles:', 'CATEGORY = "claude_creative"',
            'def blend(x_in, windows, outputs, wys=None, wxs=None, to_main=None):',
            '"cfg_end": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01})}}',
            'seam_overlap=0, seam_dual=0, pag_end=1.0, cfg_end=1.0):',
            "st = {'stash': None, 'mid_ok': {}, 'balance': None, 'logged': set(), 'sig': None, 'grids': [], 'skip': None, 'lsig': None}",
            'from . import live as _live', 'from .spot_timing import make_timer',
            'h = comfy.utils.common_upscale(cn.cond_hint_original, W * cr, H * cr, cn.upscale_algorithm, "center")',
            'h = cn.preprocess_image(h)', 'cache[key] = (cn, h.to(device=ref.device, dtype=dtype), cr)',
            'cache[key] = (cn, to_device(hint, device))', 'if noise_prefetch and sig is not None:',
            'from . import noise as _noise', 'to_main=lambda v: v if on_device(v, main) else to_device(v, main))']))
        joined = '\n'.join(added)
        for must in ("h.bind(ref.device, dtype)", "hint.rebind(device)", "coverage(wsum, len(windows))", "cover(wsum, nwin)",
                     "cover(wsum, len(wins))", "coverage=cover", "[claude_banded] wsum_min=%r evals=%d windows=%d",
                     "_nb.install(sig, BC, prefetch=noise_prefetch)", "balance != 'static'", '"brownian_cache": ("INT"',
                     'class ClaudeSpotTilesBanded:', 'CATEGORY = "claude_banded"', 'torch = _Torch()',
                     'the canvas fits one window'):
            self.assertIn(must, joined)
        # the ControlNet's run-time dtype is read by the classic's own line, unchanged (spot.py:703; T12)
        line = 'dtype = cn.manual_cast_dtype if cn.manual_cast_dtype is not None else cn.control_model.dtype'
        self.assertIn(line, text(SPOT))
        self.assertIn(line, text(FORK))
        self.assertNotIn(line, joined)

    def test_the_fork_keeps_the_classic_window_and_blend_code(self):
        spot, fork = text(SPOT), text(FORK)
        for fn in ('_spot_weights', '_spot_starts', 'spot_offsets', '_offsets', 'window_list', '_seam_starts', '_seam_weights',
                   '_tent_weights', 'seam_grid', 'weight_sum', 'static_split', 'run_split', 'patched_call', 'pag_info',
                   'make_fused_attn', 'fp16_accumulation'):
            m = re.search(rf'^def {fn}\(.*?(?=^\S)', spot, re.S | re.M)
            self.assertIsNotNone(m, fn)
            self.assertIn(m.group(0), fork, fn)

    def test_the_fixture_names_both_files(self):
        d = text(FIX)
        self.assertTrue(d.startswith('--- node_pack/claude_creative/spot.py\n+++ node_pack/claude_banded/spot_banded.py\n'))


class G0fProfilesAndCardsReachTheFork(unittest.TestCase):
    def graphs(self):
        p0 = controls.resolve({'protect': list(controls.PROTECT_ORDER)})[0]
        for (w, h, f, s, k) in ((1752, 1096, 2, 2, 0), (7000, 4376, 2, 1, 1), (16000, 10000, 2, 1, 2)):
            p = controls.stage_params(p0, k)
            for kw in ({}, {'live_preview': 'rough'}, {'speed_stack': False}, {'faster': True}, {'creative_first': True}):
                for part in (None, 'A'):
                    for consts in ({}, {'brownian_cache': 8}):
                        yield graph_banded.build_product('in.plane', w, h, p, 'x', 'pl', 'r', f=f, s=s, part=part,
                                                         constants=consts, **kw)

    def test_balanced_sets_batch_windows_1_in_every_spot_node(self):
        n = 0
        for g, info in self.graphs():
            g2, info2 = memory_policy.apply_graph(g, info, memory_policy.PROFILES['balanced'])
            spots = [v for v in g2.values() if v['class_type'] == graph_banded.SPOT_CLASS]
            self.assertTrue(spots)
            self.assertTrue(all(v['inputs']['batch_windows'] == 1 for v in spots))
            self.assertEqual(info2['spot_options']['batch_windows'], 1)
            self.assertFalse(any(v['class_type'] == 'ClaudeSpotTiles' for v in g2.values()))
            n += 1
        self.assertEqual(n, 3 * 5 * 2 * 2)
        self.assertIn(graph_banded.SPOT_CLASS, memory_policy.SPOT_CLASSES)

    def test_two_cards_split_the_windows_statically(self):
        for g, _ in self.graphs():
            g2 = graph_banded.add_multigpu(g, 2)
            spots = {k for k, v in g2.items() if v['class_type'] == graph_banded.SPOT_CLASS}
            mgs = {k: v for k, v in g2.items() if v['class_type'] == 'MultiGPU_WorkUnits'}
            self.assertEqual(len(mgs), len(spots))
            self.assertEqual({v['inputs']['model'][0] for v in mgs.values()}, spots)
            for k in spots:
                self.assertEqual((g2[k]['inputs']['window_split'], g2[k]['inputs']['balance']), (True, 'static'))
            for v in g2.values():
                if v['class_type'] == 'KSampler':
                    self.assertIn(v['inputs']['model'][0], mgs)
            self.assertEqual(graph_banded.add_multigpu(g, 1), g)

    def test_the_fork_declares_what_they_set(self):
        fork = H.node_class('ClaudeSpotTilesBanded').INPUT_TYPES()
        opt = fork['optional']
        for k in ('batch_windows', 'window_split', 'balance', 'weights', 'brownian_cache'):
            self.assertIn(k, opt)
        self.assertIn('static', opt['balance'][0])
        self.assertEqual(opt['brownian_cache'][1]['default'], 45)
        # the fork takes every option the classic node takes, with the classic's defaults
        import ast
        tree = ast.parse(text(SPOT))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'ClaudeSpotTiles')
        it = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'INPUT_TYPES')
        classic = eval(compile(ast.Expression(it.body[0].value), 'spot.py', 'eval'))
        self.assertEqual({k: v for k, v in opt.items() if k != 'brownian_cache'}, classic['optional'])
        self.assertEqual(fork['required'], classic['required'])

    def test_classic_graphs_are_untouched(self):
        p = controls.resolve({})[0]
        g, info = graph_v5t.build_product('x.png', 1752, 1096, p, 'x')
        self.assertEqual(graph_v5t.add_multigpu(g, 1), g)
        with self.assertRaises(ValueError):
            graph_banded.add_multigpu(g, 2)                 # the fork's builder never takes a classic graph
        g2, _ = memory_policy.apply_graph(g, info, memory_policy.PROFILES['balanced'])
        self.assertFalse(any(v['class_type'] == graph_banded.SPOT_CLASS for v in g2.values()))


if __name__ == '__main__':
    unittest.main()
