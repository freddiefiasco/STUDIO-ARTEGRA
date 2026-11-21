"""Gate G0d after the worker whitelist (BUILD-WAVE-2 package integ, item 1): with claude_banded whitelisted, ComfyUI imports the
whole Large-image pack (its __init__.py, so every node module, the banded exact finish and dev_vram) beside the classic pack.
Here both packs are loaded the way ComfyUI's custom-node loader loads them (nodes.load_custom_node: each folder's __init__.py,
registered in sys.modules under the folder's path name before it runs, the folders in os.listdir order, so claude_banded
first), on the worker's own libraries. Loading the Large-image pack changes no global state (torch's thread counts, default
dtype, grad and inference modes, matmul, cuDNN and attention flags, numpy's error and print settings, Pillow's
MAX_IMAGE_PIXELS, ComfyUI's MAX_RESOLUTION, sys.path, the recursion limit), whichever pack loads first, and imports no module
outside its own names; the classic nodes give the same bytes before and after (ClaudeCannyTiled on a CPU canvas, v4_finish
with 5.0.1's options). CU_DEV_VRAM_CAP_GB is unset, as in every release worker.
Skipped where torch, kornia or scipy is missing (run on Python 3.11 / torch 2.9.1 CPU, and with the runtime interpreter)."""
import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
HAVE = all(importlib.util.find_spec(m) is not None for m in ('torch', 'kornia', 'scipy', 'PIL'))


def comfy_name(folder):
    """The sys.modules name ComfyUI gives a custom-node folder (nodes.load_custom_node: its path, '.' read as '_x_')."""
    return str(folder).replace('.', '_x_')


def load_custom_node(folder):
    spec = importlib.util.spec_from_file_location(comfy_name(folder), Path(folder) / '__init__.py')
    mod = importlib.util.module_from_spec(spec)
    sys.modules[comfy_name(folder)] = mod
    spec.loader.exec_module(mod)
    return mod


def drop(folder):
    name = comfy_name(folder)
    for m in [m for m in sys.modules if m == name or m.startswith(name + '.')]:
        del sys.modules[m]


@unittest.skipUnless(HAVE, 'needs torch, kornia, scipy and Pillow (the worker libraries)')
class TheWhitelistedPackChangesNoGlobalState(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.worker import test_gpu_nodes_guards as G
        cls.G = G
        cls.banded = ROOT / 'node_pack' / 'claude_banded'
        cls.classic = ROOT / 'node_pack' / 'claude_creative'
        cls.order = [n for n in os.listdir(ROOT / 'node_pack') if n in ('claude_banded', 'claude_creative')]
        import torch  # noqa: F401  (loaded before any pack, as in a worker; never unloaded by a test)
        import kornia  # noqa: F401
        import scipy.ndimage  # noqa: F401

    def setUp(self):
        self.nodes = types.ModuleType('nodes')
        self.nodes.MAX_RESOLUTION = 16384
        self.env = mock.patch.dict(os.environ, {}, clear=False)
        self.env.start()
        os.environ.pop('CU_DEV_VRAM_CAP_GB', None)
        self.had_nodes = sys.modules.get('nodes')
        sys.modules['nodes'] = self.nodes

    def tearDown(self):
        drop(self.banded)
        drop(self.classic)
        if self.had_nodes is None:
            sys.modules.pop('nodes', None)
        else:
            sys.modules['nodes'] = self.had_nodes
        self.env.stop()

    def state(self):
        return self.G.torch_state(), self.G.other_state(self.nodes)

    def load_banded_checked(self):
        before, mods = self.state(), set(sys.modules)
        pack = load_custom_node(self.banded)
        self.assertEqual(self.state(), before)
        name = comfy_name(self.banded)
        self.assertEqual({m for m in set(sys.modules) - mods if not (m == name or m.startswith(name + '.'))
                          and not m.startswith('cu_banded_engine')}, set())
        self.assertEqual(sorted(pack.NODE_CLASS_MAPPINGS), sorted(__import__('engine.graph_banded', fromlist=['x']).NODE_SPECS))
        self.assertIsNone(pack.dev_vram.CAPS)
        return pack

    def test_comfyui_loads_the_banded_pack_first(self):
        self.assertEqual(self.order, ['claude_banded', 'claude_creative'])

    def test_banded_first_then_classic_as_comfyui_does(self):
        self.load_banded_checked()
        classic = load_custom_node(self.classic)
        self.assertIn('ClaudeV4Finish', classic.NODE_CLASS_MAPPINGS)

    def test_banded_after_the_classic_pack(self):
        load_custom_node(self.classic)
        self.load_banded_checked()

    def test_the_classic_nodes_give_the_same_bytes(self):
        canny0, fin0 = self.G.classic_canny_bytes(), self.G.classic_finish_bytes()
        load_custom_node(self.classic)
        self.load_banded_checked()
        self.assertEqual(self.G.classic_canny_bytes(), canny0)
        self.assertEqual(self.G.classic_finish_bytes(), fin0)


if __name__ == '__main__':
    unittest.main()
