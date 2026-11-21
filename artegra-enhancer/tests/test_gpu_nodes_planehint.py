"""PlaneHint (node_pack/claude_banded/cn_plane.py; engine design T12): a ControlNet hint held in a plane is never a tensor.
Every tensor use raises, so ComfyUI's get_control (comfy/controlnet.py:270-281) cannot re-derive a whole-canvas hint from it;
the hint is refused where the classic would resample it; a canvas within one window is refused. Sizes and synthetic arrays
only; no torch (the window crops themselves: tests/worker/test_gpu_nodes_cn.py)."""
import copy
import pickle
import tempfile
import types
import unittest
from pathlib import Path

import numpy as np

from engine import planes
from tests import test_gpu_nodes_helpers as H

TENSOR_NAMES = ('to', 'cpu', 'cuda', 'numpy', 'float', 'half', 'movedim', 'permute', 'shape', 'dtype', 'device', 'ndim', 'size',
                'dim', 'contiguous', 'clone', 'detach', 'unsqueeze', 'squeeze', 'repeat', 'expand', 'narrow', 'view',
                'reshape', 'is_contiguous', 'stride', 'element_size', 'numel', 'new_zeros', 'chunk', 'mul', 'add', 'data')


class PlaneHintIsNotATensor(unittest.TestCase):
    def setUp(self):
        self.cn = H.module('cn_plane')
        pack = H.load_pack()
        self.td = tempfile.TemporaryDirectory()
        p = planes.from_array(Path(self.td.name) / 'hint.plane', np.zeros((1200, 1500, 3), np.float32))
        self.hint = self.cn.PlaneHint.from_ref(pack.PlaneRef(p.path, 'run1'))

    def tearDown(self):
        self.td.cleanup()

    def test_every_tensor_attribute_raises(self):
        for name in TENSOR_NAMES:
            with self.assertRaises(TypeError, msg=name):
                getattr(self.hint, name)

    def test_every_tensor_operation_raises(self):
        h = self.hint
        ops = [lambda: h[..., 0:8, 0:8], lambda: h[0], lambda: len(h), lambda: list(h), lambda: float(h), lambda: int(h),
               lambda: h + 1, lambda: 1 + h, lambda: h * 2.0, lambda: 2.0 * h, lambda: h - h, lambda: h / 3, lambda: -h,
               lambda: h @ h, lambda: h ** 2, lambda: h < 1, lambda: np.asarray(h, dtype=np.float32),
               lambda: setattr(h, 'path', 'x'), lambda: h.__setitem__(0, 1)]
        for i, op in enumerate(ops):
            with self.assertRaises(TypeError, msg=i):
                op()

    def test_torch_functions_refuse_it(self):
        with self.assertRaises(TypeError):
            self.cn.PlaneHint.__torch_function__(lambda: None, (), (self.hint,))

    def test_it_can_be_shared_like_a_hint_reference(self):
        h = self.hint
        self.assertIs(copy.copy(h), h)
        self.assertIs(copy.deepcopy({'k': [h]})['k'][0], h)
        p = pickle.loads(pickle.dumps(h))
        self.assertEqual((p.path, p.run_id, p.height, p.width, p.channels, p.plane_dtype),
                         (h.path, h.run_id, h.height, h.width, h.channels, h.plane_dtype))
        self.assertTrue(bool(h))
        self.assertIsNot(h, None)
        self.assertIn('1500x1200x3', repr(h))

    def test_only_a_plane_handle_becomes_a_hint(self):
        with self.assertRaises(TypeError):
            self.cn.PlaneHint.from_ref(np.zeros((8, 8, 3)))
        with self.assertRaises(ValueError):
            self.cn.PlaneHint('x', 'r', (8, 8, 2), 'f32')
        with self.assertRaises(ValueError):
            self.cn.PlaneHint('x', 'r', (8, 8, 3), 'f16')


class RefusedWhereTheClassicWouldResample(unittest.TestCase):
    def test_check(self):
        cn = H.module('cn_plane')
        h = cn.PlaneHint('x', 'r', (1200, 1600, 3), 'f32')
        ok = types.SimpleNamespace(upscale_algorithm='nearest-exact', preprocess_image=lambda a: a)
        h.check(1600, 1200, ok)
        with self.assertRaises(ValueError):
            h.check(1608, 1200, ok)
        with self.assertRaises(ValueError):
            h.check(1600, 1200, types.SimpleNamespace(upscale_algorithm='bilinear', preprocess_image=lambda a: a))
        with self.assertRaises(ValueError):
            h.check(1600, 1200, types.SimpleNamespace(upscale_algorithm='nearest-exact', preprocess_image=lambda a: [a]))

    def test_one_window_canvases(self):
        cn = H.module('cn_plane')
        self.assertTrue(cn.PlaneHint('x', 'r', (1024, 1024, 3), 'f32').one_window())
        self.assertTrue(cn.PlaneHint('x', 'r', (640, 1024, 1), 'u8').one_window())
        self.assertFalse(cn.PlaneHint('x', 'r', (1024, 1032, 3), 'f32').one_window())
        self.assertFalse(cn.PlaneHint('x', 'r', (1032, 64, 3), 'f32').one_window())

    def test_the_node_refuses_a_one_window_canvas_before_anything_else(self):
        cn = H.module('cn_plane')
        pack = H.load_pack()
        with tempfile.TemporaryDirectory() as td:
            p = planes.from_array(Path(td) / 'h.plane', np.zeros((1024, 1000, 3), np.float32))
            with self.assertRaises(ValueError) as e:
                cn.CUControlNetApplyPlane().run([], [], None, pack.PlaneRef(p.path, 'r'), 0.7, 0.0, 1.0, None)
            self.assertIn('one 1024 px window', str(e.exception))

    def test_the_window_reader_takes_only_window_slices(self):
        cn = H.module('cn_plane')
        b = cn.PlaneHint('x', 'r', (1200, 1600, 3), 'f32').bind('cpu', 'float16')
        for key in ((slice(0, 8), slice(0, 8)), (Ellipsis, slice(0, 8)), (Ellipsis, slice(0, 8, 2), slice(0, 8)),
                    (Ellipsis, slice(None, 8), slice(0, 8)), 3):
            with self.assertRaises(TypeError, msg=key):
                b[key]
        for name in ('shape', 'to', 'dtype_t', 'numpy'):
            with self.assertRaises(TypeError):
                getattr(b, name)
        self.assertEqual(b.rebind('cuda:1').device, 'cuda:1')
        self.assertEqual(b.rebind('cuda:1').dtype, 'float16')


if __name__ == '__main__':
    unittest.main()
