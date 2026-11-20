"""The developer-only graphics-memory cap of the small-card emulation R5 (node_pack/claude_banded/dev_vram.py; engine design
8.1, gate G0g): applied only by a developer build that sees CU_DEV_VRAM_CAP_GB, ignored (and logged) by a release build, and
importing it changes no global state (G0d). Before the merge role adds its import to the pack, the module is reached as
load_banded_pack() then importlib.import_module (BUILD-WAVE-1 contract node_registration). No torch is needed: a stub
stands in for torch.cuda."""
import importlib
import logging
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from tests.test_banded_guards import ROOT, load_banded_pack


def dev_vram():
    pack = load_banded_pack()
    sys.modules[pack.__name__] = pack           # the package a submodule import needs (as ComfyUI registers the pack)
    sys.modules.pop(pack.__name__ + '.dev_vram', None)
    return importlib.import_module(pack.__name__ + '.dev_vram')


class StubCuda:
    def __init__(self, totals_gb):
        self.totals = totals_gb
        self.set = []

    def is_available(self):
        return bool(self.totals)

    def device_count(self):
        return len(self.totals)

    def get_device_properties(self, i):
        return SimpleNamespace(total_memory=int(self.totals[i] * (1 << 30)))

    def set_per_process_memory_fraction(self, frac, i):
        self.set.append((i, frac))


class DevVram(unittest.TestCase):
    def setUp(self):
        self.m = dev_vram()
        self.log = logging.getLogger('test_dev_vram')

    def test_the_source_tree_is_a_release_build(self):
        self.assertEqual(self.m.build_channel(), 'release')
        self.assertEqual(self.m.CHANNEL_FILE, ROOT / 'service' / 'build_channel.py')
        self.assertIsNone(self.m.CAPS)

    def test_a_release_build_ignores_it_and_says_so(self):
        torch = SimpleNamespace(cuda=StubCuda([32.0]))
        with self.assertLogs('test_dev_vram', 'WARNING') as logs:
            self.assertIsNone(self.m.apply({'CU_DEV_VRAM_CAP_GB': '12'}, 'release', torch, self.log))
        self.assertEqual(torch.cuda.set, [])
        self.assertIn('release build', logs.output[0])

    def test_a_developer_build_caps_every_card(self):
        torch = SimpleNamespace(cuda=StubCuda([32.0, 32.0]))
        out = self.m.apply({'CU_DEV_VRAM_CAP_GB': '12'}, 'dev', torch, self.log)
        self.assertEqual([d['device'] for d in out], [0, 1])
        self.assertEqual(torch.cuda.set, [(0, 12 / 32.0), (1, 12 / 32.0)])
        torch = SimpleNamespace(cuda=StubCuda([8.0]))
        self.m.apply({'CU_DEV_VRAM_CAP_GB': '24'}, 'dev', torch, self.log)
        self.assertEqual(torch.cuda.set, [(0, 1.0)])                   # never above the card

    def test_nothing_without_the_variable_or_with_a_bad_value(self):
        torch = SimpleNamespace(cuda=StubCuda([32.0]))
        self.assertIsNone(self.m.apply({}, 'dev', torch, self.log))
        with self.assertLogs('test_dev_vram', 'WARNING'):
            self.assertIsNone(self.m.apply({'CU_DEV_VRAM_CAP_GB': 'twelve'}, 'dev', torch, self.log))
        with self.assertLogs('test_dev_vram', 'WARNING'):
            self.assertIsNone(self.m.apply({'CU_DEV_VRAM_CAP_GB': '12'}, 'dev', SimpleNamespace(cuda=StubCuda([])), self.log))
        self.assertEqual(torch.cuda.set, [])

    def test_the_channel_is_read_from_a_developer_tree(self):
        from tools import make_dev_build
        with tempfile.TemporaryDirectory() as td:
            dest = make_dev_build.make(Path(td) / 'dev')
            self.assertEqual(self.m.build_channel(dest / 'service' / 'build_channel.py'), 'dev')
            self.assertEqual(self.m.build_channel(Path(td) / 'missing.py'), 'release')

    def test_g0d_importing_it_changes_no_global_state(self):
        from PIL import Image
        mods = set(sys.modules)
        state = (Image.MAX_IMAGE_PIXELS, np.get_printoptions(), sys.getrecursionlimit(), list(sys.path))
        dev_vram()
        self.assertEqual((Image.MAX_IMAGE_PIXELS, np.get_printoptions(), sys.getrecursionlimit(), list(sys.path)), state)
        self.assertEqual({m for m in set(sys.modules) - mods if not m.startswith('claude_banded_for_tests')}, set())
        self.assertNotIn('torch', set(sys.modules) - mods)


if __name__ == '__main__':
    unittest.main()
