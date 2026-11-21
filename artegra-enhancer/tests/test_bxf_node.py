"""The replacement CUFinishBanded (node_pack/claude_banded/bxf): exactly the inputs and outputs of
engine/graph_banded.NODE_SPECS['CUFinishBanded'] and NODE_OPTIONAL (frozen in wave 1) and of the base build's class (pinned in
tests/fixtures/finish_banded_5_0_2_base.txt; tier 3 is its run body); importing it adds no
module and changes no global state (G0d); the fallback ladder's choice (pure); the variant, budget and process count only from
their registered sets. numpy only (the finish itself is tested on the worker's libraries in tests/worker/test_bxf_finish.py)."""
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
        pack, bxf = bxf_node()
        cls, base = bxf.CUFinishBanded, base_class(pack)
        self.assertIs(pack.NODE_CLASS_MAPPINGS['CUFinishBanded'], cls)          # the merge registered the ladder
        self.assertIsNot(base, cls)
        req, outs = graph_banded.NODE_SPECS['CUFinishBanded']
        it = cls.INPUT_TYPES()
        self.assertEqual(sorted(it['required']), sorted(req))
        self.assertEqual(sorted(it['optional']), sorted(graph_banded.NODE_OPTIONAL['CUFinishBanded']))
        self.assertEqual(tuple(cls.RETURN_TYPES), tuple(outs))
        self.assertEqual(it, base.INPUT_TYPES())
        for k in ('RETURN_TYPES', 'FUNCTION', 'OUTPUT_NODE', 'CATEGORY'):
            self.assertEqual(getattr(cls, k), getattr(base, k), k)
        self.assertEqual(bxf.VARIANTS, graph_banded.FINISH_VARIANTS)

    def test_tier_3_is_the_base_builds_run_body_and_run_keeps_its_two_checks(self):
        """_tier3's statements equal the base run()'s minus its variant and smoothing checks, which the new run() makes
        before it chooses a tier; the arguments are the same, in the same order."""
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
        self.assertEqual([a.arg for a in run1.args.args], [a.arg for a in run0.args.args])
        self.assertEqual([ast.dump(d) for d in run1.args.defaults], [ast.dump(d) for d in run0.args.defaults])
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
