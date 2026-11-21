"""The replacement CUFinishBanded (node_pack/claude_banded/bxf): exactly the inputs and outputs of
engine/graph_banded.NODE_SPECS['CUFinishBanded'] and NODE_OPTIONAL and of the base build's class (pinned in
tests/fixtures/finish_banded_5_0_2_base.txt; tier 3 is its run body), plus exactly the three optional inputs of build wave 2's
contract finish_inputs, appended in its order (band_gb, processes, finish_tier) with its defaults and value sets; importing it
adds no module and changes no global state (G0d); the fallback ladder's choice within the tier the plan counted (pure; the
exact selection's numpy helpers checked before any plane is written, bxf-chk-6); the variant, budget and process count only
from their registered sets, anything else refused in plain words. numpy only (the finish itself is tested on the worker's
libraries in tests/worker/test_bxf_finish.py)."""
import ast
import hashlib
import importlib
import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path

import numpy as np

from engine import graph_banded

ROOT = Path(__file__).resolve().parents[1]
NAME = 'claude_banded_for_bxf_tests'


def load_pack():
    """The banded pack registered under a test name (a subpackage's relative import needs its parent in sys.modules, as
    ComfyUI's own loader provides)."""
    if NAME in sys.modules:
        return sys.modules[NAME]
    spec = importlib.util.spec_from_file_location(NAME, ROOT / 'node_pack' / 'claude_banded' / '__init__.py',
                                                  submodule_search_locations=[str(ROOT / 'node_pack' / 'claude_banded')])
    mod = importlib.util.module_from_spec(spec)
    sys.modules[NAME] = mod
    spec.loader.exec_module(mod)
    return mod


def bxf_node():
    pack = load_pack()
    return pack, importlib.import_module(NAME + '.bxf')


# The base build's CUFinishBanded (tier 3 only), verbatim from node_pack/claude_banded/__init__.py at 85c69ef2, the 5.0.2
# development base before the banded finish. Since the merge of build wave 1 the pack registers the bxf class under the same
# name, so "today's node" can no longer be the reference: the tests compare the new class with this pinned copy.
BASE_COMMIT = '85c69ef2'
BASE_FILE = ROOT / 'tests' / 'fixtures' / 'finish_banded_5_0_2_base.txt'
BASE_SHA256 = '940cbd3bc7c1d5e97c02d7f0411755833afcf29426d85789039812961d183e08'
# contracts.finish_inputs (BUILD-WAVE-2.json): the three optional inputs wave 2 appends, in this order, with these defaults
ADDITIONS = ('band_gb', 'processes', 'finish_tier')
ADDITION_DEFAULTS = (2.0, 1, 'ladder')


def base_class(pack):
    """The pinned base CUFinishBanded, defined in a copy of `pack`'s namespace (so its helpers are that pack's)."""
    ns = dict(vars(pack))
    exec(compile(BASE_FILE.read_text(encoding='utf8'), str(BASE_FILE), 'exec'), ns)
    return ns['CUFinishBanded']


def _method(cls_node, name):
    return next(n for n in cls_node.body if isinstance(n, ast.FunctionDef) and n.name == name)


def _body(fn):
    """A function's statements without its docstring, each as ast.dump."""
    body = fn.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        body = body[1:]
    return [ast.dump(s) for s in body]


class TheNodeInterface(unittest.TestCase):
    def test_inputs_and_outputs_are_the_frozen_spec_and_the_base_builds(self):
        """The base class's inputs, unchanged, plus exactly the contract's three optional inputs appended in its order. The
        graph's NODE_OPTIONAL is the plan package's: before the wave-2 merge it lacks the three (that side's spec test is red
        by design), after it it lists them; either way the node declares no other input."""
        pack, bxf = bxf_node()
        cls, base = bxf.CUFinishBanded, base_class(pack)
        self.assertIs(pack.NODE_CLASS_MAPPINGS['CUFinishBanded'], cls)          # the merge registered the ladder
        self.assertIsNot(base, cls)
        req, outs = graph_banded.NODE_SPECS['CUFinishBanded']
        it, it0 = cls.INPUT_TYPES(), base.INPUT_TYPES()
        self.assertEqual(sorted(it['required']), sorted(req))
        self.assertEqual(it['required'], it0['required'])
        self.assertEqual(list(it['optional']), list(it0['optional']) + list(ADDITIONS))
        for k, v in it0['optional'].items():
            self.assertEqual(it['optional'][k], v, k)
        graph_opt = tuple(graph_banded.NODE_OPTIONAL['CUFinishBanded'])
        base_opt = tuple(it0['optional'])
        self.assertIn(graph_opt, (base_opt, base_opt + ADDITIONS))
        self.assertEqual(sorted(it['optional']), sorted(set(graph_opt) | set(ADDITIONS)))
        self.assertEqual(bxf.NEW_INPUTS, ADDITIONS)
        self.assertEqual(tuple(cls.RETURN_TYPES), tuple(outs))
        opt = it['optional']
        self.assertEqual(opt['band_gb'], ('FLOAT', {'default': 2.0, 'min': 2.0, 'max': 6.0, 'step': 1.0}))
        self.assertEqual(opt['processes'], ('INT', {'default': 1, 'min': 1, 'max': 4}))
        self.assertEqual(opt['finish_tier'], (['ladder', 'bxf', 'tier3'], {'default': 'ladder'}))
        bands = pack._engine('bands')
        self.assertEqual((opt['band_gb'][1]['min'], opt['band_gb'][1]['max']), (min(bands.BAND_BUDGETS_GB), max(bands.BAND_BUDGETS_GB)))
        self.assertEqual((opt['processes'][1]['min'], opt['processes'][1]['max']), (min(bands.PROCESS_COUNTS), max(bands.PROCESS_COUNTS)))
        for k in ('RETURN_TYPES', 'FUNCTION', 'OUTPUT_NODE', 'CATEGORY'):
            self.assertEqual(getattr(cls, k), getattr(base, k), k)
        self.assertEqual(bxf.VARIANTS, graph_banded.FINISH_VARIANTS)

    def test_tier_3_is_the_base_builds_run_body_and_run_keeps_its_two_checks(self):
        """_tier3's statements equal the base run()'s minus its variant and smoothing checks, which the new run() makes
        before it chooses a tier; _tier3 takes the base run()'s arguments in the same order, and run() those plus exactly the
        contract's three, appended, with the contract's defaults."""
        base = ast.parse(BASE_FILE.read_text(encoding='utf8')).body[0]
        new = next(n for n in ast.parse((ROOT / 'node_pack' / 'claude_banded' / 'bxf' / '__init__.py').read_text(encoding='utf8')).body
                   if isinstance(n, ast.ClassDef) and n.name == 'CUFinishBanded')
        run0, run1, tier3 = _method(base, 'run'), _method(new, 'run'), _method(new, '_tier3')
        checks = [s for s in run0.body if isinstance(s, ast.If) and isinstance(s.body[0], ast.Raise)
                  and {n.id for n in ast.walk(s.test) if isinstance(n, ast.Name)} & {'finish', 'smooth_hi'}]
        self.assertEqual(len(checks), 2)
        want = [ast.dump(s) for s in run0.body if s not in checks]
        self.assertEqual(_body(tier3), want)
        self.assertEqual([a.arg for a in tier3.args.args], [a.arg for a in run0.args.args])
        self.assertEqual([a.arg for a in run1.args.args], [a.arg for a in run0.args.args] + list(ADDITIONS))
        self.assertEqual([ast.dump(d) for d in run1.args.defaults],
                         [ast.dump(d) for d in run0.args.defaults] + [ast.dump(ast.Constant(v)) for v in ADDITION_DEFAULTS])
        new_checks = [ast.unparse(s.test) for s in run1.body if isinstance(s, ast.If) and isinstance(s.body[0], ast.Raise)]
        self.assertEqual(new_checks, ['finish not in VARIANTS', 'smooth_hi <= smooth_lo'])

    def test_the_pinned_base_is_the_base_commits_class(self):
        self.assertEqual(hashlib.sha256(BASE_FILE.read_bytes()).hexdigest(), BASE_SHA256)
        try:
            src = subprocess.run(['git', 'show', f'{BASE_COMMIT}:artegra-enhancer/node_pack/claude_banded/__init__.py'],
                                 cwd=ROOT, capture_output=True, check=True, timeout=60).stdout.decode('utf8')
        except (OSError, subprocess.SubprocessError):
            self.skipTest('standalone: the base commit is in the internal repository history only')
        a, b = src.index('class CUFinishBanded:'), src.index('def _not_built(')
        self.assertEqual(src[a:b].rstrip('\n') + '\n', BASE_FILE.read_text(encoding='utf8'))

    def test_g0d_importing_it_adds_no_module_and_changes_no_global_state(self):
        from PIL import Image
        for k in [k for k in sys.modules if k.startswith(NAME)]:
            del sys.modules[k]
        mods = set(sys.modules)
        state = (Image.MAX_IMAGE_PIXELS, np.get_printoptions(), sys.getrecursionlimit(), list(sys.path))
        bxf_node()
        self.assertEqual((Image.MAX_IMAGE_PIXELS, np.get_printoptions(), sys.getrecursionlimit(), list(sys.path)), state)
        new = {m for m in set(sys.modules) - mods if not m.startswith(NAME)}
        self.assertEqual(new - {'cu_banded_engine'}, set())
        self.assertNotIn(NAME + '.bxf.finish', sys.modules)
        for heavy in ('torch', 'scipy'):
            if heavy not in mods:
                self.assertNotIn(heavy, sys.modules)


class TheLadder(unittest.TestCase):
    def test_choose_within_the_tier_the_plan_counted(self):
        """'tier3' runs the whole finish at any size it is asked (the whole finish itself refuses above 300 MP); 'bxf' runs
        tier 0 where the table applies and is refused in plain words where it does not, at any size (never tier 3, which
        that plan did not count); 'ladder' is the ladder."""
        pack, bxf = bxf_node()
        g1 = pack._engine('bxf.g1')
        C = bxf.CUFinishBanded.choose
        other = g1.Table({'environment': {}, 'ops': {}}, {'torch': 'x'})
        self.assertEqual(C(10.0, True, g1.AllBanded(), 'tier3')[0], 'tier3')
        self.assertEqual(C(10.0, True, other, 'tier3')[0], 'tier3')
        self.assertEqual(C(1000.0, True, g1.AllBanded(), 'bxf')[0], 'bxf')
        for mp in (10.0, 300.0, 1000.0):
            with self.assertRaises(pack.NotBuilt) as cm:
                C(mp, True, other, 'bxf')
            self.assertIn('this plan counted only the banded finish', str(cm.exception))
            self.assertIn('another environment', str(cm.exception))
        with self.assertRaises(pack.NotBuilt):
            C(10.0, False, g1.AllBanded(), 'bxf')
        self.assertEqual(C(10.0, True, other, 'ladder'), C(10.0, True, other))

    def test_bxf_chk_6_missing_selection_helpers_are_found_before_any_plane(self):
        """A numpy without the exact selection's helpers: the ladder takes tier 3 up to 300 MP and refuses above, the 'bxf'
        tier refuses, all before the finish starts (selection.unavailable(), not a RuntimeError in the middle of the finish)."""
        from unittest import mock
        pack, bxf = bxf_node()
        g1, sel = pack._engine('bxf.g1'), pack._engine('bxf.selection')
        self.assertIsNone(sel.unavailable())
        self.assertTrue(issubclass(sel.Unavailable, RuntimeError))
        C = bxf.CUFinishBanded.choose
        with mock.patch.object(sel, 'unavailable', lambda: 'numpy 9 has no _lerp: exact selection cannot use numpy\'s own arithmetic'):
            mode, why = C(100.0, True, g1.AllBanded())
            self.assertEqual(mode, 'tier3')
            self.assertIn('_lerp', why)
            with self.assertRaises(pack.NotBuilt):
                C(300.1, True, g1.AllBanded())
            with self.assertRaises(pack.NotBuilt):
                C(10.0, True, g1.AllBanded(), 'bxf')
            self.assertEqual(C(10.0, True, g1.AllBanded(), 'tier3')[0], 'tier3')
        import numpy.lib._function_base_impl as fb
        with mock.patch.dict(fb.__dict__):
            del fb.__dict__['_lerp']
            self.assertIn('_lerp', sel.unavailable())
        self.assertIsNone(sel.unavailable())

    def test_choose(self):
        pack, bxf = bxf_node()
        g1 = pack._engine('bxf.g1')
        C = bxf.CUFinishBanded.choose
        self.assertEqual(C(10.0, True, g1.AllBanded())[0], 'bxf')
        self.assertEqual(C(1000.0, True, g1.AllBanded())[0], 'bxf')
        other = g1.Table({'environment': {}, 'ops': {}}, {'torch': 'x'})
        self.assertEqual(C(300.0, True, other)[0], 'tier3')
        with self.assertRaises(pack.NotBuilt):
            C(300.1, True, other)
        self.assertEqual(C(10.0, False, g1.AllBanded())[0], 'tier3')
        with self.assertRaises(pack.NotBuilt):
            C(500.0, False, g1.AllBanded())
        self.assertEqual(bxf.FORCE, None)

    def test_the_three_inputs_only_from_their_registered_sets(self):
        pack, bxf = bxf_node()
        F = bxf.CUFinishBanded.finish_inputs
        self.assertEqual(F(), (2.0, 1, 'ladder'))
        for gb in (2.0, 3.0, 6.0, 2, 3, 6):
            self.assertEqual(F(gb, 1, 'ladder')[0], float(gb))
        for n in (1, 2, 4):
            self.assertEqual(F(2.0, n, 'bxf')[1], n)
        for t in ('ladder', 'bxf', 'tier3'):
            self.assertEqual(F(2.0, 1, t)[2], t)
        for bad in ((4.0, 1, 'ladder'), (2.5, 1, 'ladder'), ('2', 1, 'ladder'), (True, 1, 'ladder'), (None, 1, 'ladder'),
                    (2.0, 3, 'ladder'), (2.0, 0, 'ladder'), (2.0, 2.0, 'ladder'), (2.0, True, 'ladder'),
                    (2.0, 1, 'tier0'), (2.0, 1, 'Ladder'), (2.0, 1, None)):
            with self.assertRaises(ValueError, msg=bad) as cm:
                F(*bad)
            self.assertTrue(str(cm.exception).startswith('CUFinishBanded: '), str(cm.exception))
        node = bxf.CUFinishBanded()
        with self.assertRaises(ValueError):                  # refused before any plane is read
            node.run(None, None, None, None, 0.2, 0.5, 12, 4.0, True, True, 'bxf-1', 0.4, 0.06, 8, 8, 'x', 'cu', 'r', band_gb=4.0)
        with self.assertRaises(ValueError):
            node.run(None, None, None, None, 0.2, 0.5, 12, 4.0, True, True, 'bxf-1', 0.4, 0.06, 8, 8, 'x', 'cu', 'r', processes=3)
        with self.assertRaises(ValueError):
            node.run(None, None, None, None, 0.2, 0.5, 12, 4.0, True, True, 'bxf-1', 0.4, 0.06, 8, 8, 'x', 'cu', 'r',
                     finish_tier='tier1')

    def test_bxf_chk_6_dead_code_is_gone(self):
        src = (ROOT / 'node_pack' / 'claude_banded' / 'bxf' / 'finish.py').read_text(encoding='utf8')
        tree = ast.parse(src)
        self.assertNotIn('Unsupported', {n.name for n in tree.body if isinstance(n, ast.ClassDef)})
        bxf_cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'BXF')
        self.assertNotIn('h', {n.name for n in bxf_cls.body if isinstance(n, ast.FunctionDef)})

    def test_variant_budget_and_processes_come_from_their_registered_sets(self):
        pack, bxf = bxf_node()
        node = bxf.CUFinishBanded()
        with self.assertRaises(ValueError):
            node.run(None, None, None, None, 0.2, 0.5, 12, 4.0, True, True, 'bxf-1h', 0.4, 0.06, 8, 8, 'x', 'cu', 'r')
        with self.assertRaises(ValueError):
            node.run(None, None, None, None, 0.5, 0.2, 12, 4.0, True, True, 'bxf-1', 0.4, 0.06, 8, 8, 'x', 'cu', 'r')
        bands = pack._engine('bands')
        with self.assertRaises(AssertionError):
            bands.check_band_budget(4.0)
        with self.assertRaises(AssertionError):
            bands.check_process_count(3)


if __name__ == '__main__':
    unittest.main()
