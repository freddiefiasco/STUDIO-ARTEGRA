"""The replacement CUFinishBanded (node_pack/claude_banded/bxf): exactly the inputs and outputs of
engine/graph_banded.NODE_SPECS['CUFinishBanded'] and NODE_OPTIONAL (frozen in wave 1) and of today's class; importing it adds no
module and changes no global state (G0d); the fallback ladder's choice (pure); the variant, budget and process count only from
their registered sets. numpy only (the finish itself is tested on the worker's libraries in tests/worker/test_bxf_finish.py)."""
import importlib
import importlib.util
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


class TheNodeInterface(unittest.TestCase):
    def test_inputs_and_outputs_are_the_frozen_spec_and_todays(self):
        pack, bxf = bxf_node()
        cls, today = bxf.CUFinishBanded, pack.NODE_CLASS_MAPPINGS['CUFinishBanded']
        req, outs = graph_banded.NODE_SPECS['CUFinishBanded']
        it = cls.INPUT_TYPES()
        self.assertEqual(sorted(it['required']), sorted(req))
        self.assertEqual(sorted(it['optional']), sorted(graph_banded.NODE_OPTIONAL['CUFinishBanded']))
        self.assertEqual(tuple(cls.RETURN_TYPES), tuple(outs))
        self.assertEqual(it, today.INPUT_TYPES())
        for k in ('RETURN_TYPES', 'FUNCTION', 'OUTPUT_NODE', 'CATEGORY'):
            self.assertEqual(getattr(cls, k), getattr(today, k), k)
        self.assertEqual(bxf.VARIANTS, graph_banded.FINISH_VARIANTS)

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
