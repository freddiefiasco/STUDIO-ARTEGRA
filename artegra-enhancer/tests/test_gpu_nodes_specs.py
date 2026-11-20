"""The six GPU plane nodes of the Large-image engine (gpu-nodes, wave 1) against the graph builder's contract, and gate G0d for
their modules. Sizes only; runs without torch (every module imports torch and numpy only inside its functions).

- Each node's INPUT_TYPES (required and optional) and RETURN_TYPES equal engine/graph_banded.NODE_SPECS / NODE_OPTIONAL, and
  every graph the builder makes passes only declared inputs with values inside the declared ranges and choices.
- G0d: importing each module (a fresh copy of the pack each time) adds no module outside the pack's private names, and changes
  no global state: Pillow's MAX_IMAGE_PIXELS, ComfyUI's MAX_RESOLUTION, numpy's print options, sys.path, the recursion limit
  (torch flags and thread counts: tests/worker/test_gpu_nodes_guards.py)."""
import importlib
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from engine import controls, graph_banded
from tests import test_gpu_nodes_helpers as H

NEW_MODULES = ('canny_plane', 'vae_planes', 'spot_banded', 'noise_banded', 'cn_plane', 'sam_plane')


class EachNodeMatchesTheGraphBuilder(unittest.TestCase):
    def test_inputs_and_outputs(self):
        for name in H.MODULES:
            cls = H.node_class(name)
            req, outs = graph_banded.NODE_SPECS[name]
            it = cls.INPUT_TYPES()
            self.assertEqual(sorted(it['required']), sorted(req), name)
            self.assertEqual(sorted(it.get('optional', {})), sorted(graph_banded.NODE_OPTIONAL.get(name, ())), name)
            self.assertEqual(tuple(cls.RETURN_TYPES), tuple(outs), name)
            self.assertTrue(callable(getattr(cls, cls.FUNCTION)), name)
            self.assertEqual(cls.CATEGORY, 'claude_banded', name)
            self.assertFalse(getattr(cls, 'NOT_BUILT', False), name)

    def test_the_planes_nodes_take_the_run_id_and_their_folder(self):
        for name in ('CUCannyPlane', 'CUDecodePlane', 'CUSam3DetectLean'):
            it = H.node_class(name).INPUT_TYPES()['required']
            self.assertEqual(it['run_id'][0], 'STRING', name)
            self.assertEqual(it['plane_dir'][0], 'STRING', name)

    def test_every_graph_value_is_accepted(self):
        """Every value the builder passes to one of these nodes is inside the node's declared range or choices (ComfyUI
        validates them before it runs anything)."""
        p0 = controls.resolve({'protect': list(controls.PROTECT_ORDER)})[0]
        seen = set()
        for (w, h, f, s, k) in ((1752, 1096, 2, 2, 0), (7000, 4376, 2, 1, 1), (16000, 10000, 2, 1, 2)):
            p = controls.stage_params(p0, k)
            for kw in ({}, {'live_preview': 'detailed'}, {'speed_stack': False}, {'faster': True}):
                for consts in ({}, {'brownian_cache': 8}, {'encode_state': 'partial'}, {'encode_state': 'classic'}):
                    g, _ = graph_banded.build_product('in.plane', w, h, p, 'x', 'pl', 'r', f=f, s=s, constants=consts, **kw)
                    for node in g.values():
                        name = node['class_type']
                        if name not in H.MODULES:
                            continue
                        seen.add(name)
                        it = H.node_class(name).INPUT_TYPES()
                        decl = {**it['required'], **it.get('optional', {})}
                        for key, val in node['inputs'].items():
                            self.assertIn(key, decl, (name, key))
                            if isinstance(val, list):
                                continue                       # a link
                            spec = decl[key]
                            if isinstance(spec[0], list):
                                self.assertIn(val, spec[0], (name, key))
                            elif len(spec) > 1 and isinstance(spec[1], dict):
                                lo, hi = spec[1].get('min'), spec[1].get('max')
                                if lo is not None:
                                    self.assertGreaterEqual(val, lo, (name, key))
                                if hi is not None:
                                    self.assertLessEqual(val, hi, (name, key))
        self.assertEqual(seen, set(H.MODULES))


class G0dImportingTheModulesChangesNothing(unittest.TestCase):
    def fresh(self, n):
        name = f'claude_banded_g0d_{n}'
        spec = importlib.util.spec_from_file_location(name, H.PACK_DIR / '__init__.py',
                                                      submodule_search_locations=[str(H.PACK_DIR)])
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        return name

    def test_no_global_state_and_no_new_module(self):
        from PIL import Image
        nodes = types.ModuleType('nodes')
        nodes.MAX_RESOLUTION = 16384
        with mock.patch.dict(sys.modules, {'nodes': nodes}):
            for i, m in enumerate(NEW_MODULES):
                name = self.fresh(i)
                mods = set(sys.modules)
                state = (Image.MAX_IMAGE_PIXELS, nodes.MAX_RESOLUTION, np.get_printoptions(), list(sys.path),
                         sys.getrecursionlimit(), sys.getswitchinterval())
                importlib.import_module(f'{name}.{m}')
                self.assertEqual((Image.MAX_IMAGE_PIXELS, nodes.MAX_RESOLUTION, np.get_printoptions(), list(sys.path),
                                  sys.getrecursionlimit(), sys.getswitchinterval()), state, m)
                new = {x for x in set(sys.modules) - mods if not x.startswith(name)}
                self.assertEqual(new, set(), m)
                for x in [x for x in sys.modules if x.startswith(name)]:
                    del sys.modules[x]


if __name__ == '__main__':
    unittest.main()
