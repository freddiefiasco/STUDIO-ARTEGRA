"""The live preview of a Large-image stage (engine design ENGINE-DESIGN.md 2.10, D8): a proxy of the stage input of at most
2048 px made in bands from the input plane by the T1 Lanczos downscale (the bytes of Pillow's whole-image resize), never a
whole-image copy; no full-size live picture, so live frames stay within service/live.py's FULL_BUDGET_MB; the proxy is
counted in the service term; the progress tracker weighs the new node classes. In-process, sizes and synthetic pixels."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np
from PIL import Image

from engine import banded_plan, graph_banded, lanczos_bands, planes
from service import banded_runner, comfy, live
from service.runner import SILENT_NODES, Runner


class Recording(planes.Plane):
    """A plane that records the largest block any read hands back."""
    largest = 0

    def read_rows(self, y0, y1, out=None):
        a = super().read_rows(y0, y1, out)
        Recording.largest = max(Recording.largest, a.nbytes)
        return a


def input_plane(td, iw, ih, pw, ph, seed=3):
    rng = np.random.default_rng(seed)
    a = rng.integers(0, 256, (ph, pw, 3), dtype=np.uint8)
    p = planes.from_array(Path(td) / 'input.plane', a)
    rec = Recording(p.path, p.header, False)
    return rec, a[:ih, :iw]


class TheProxy(unittest.TestCase):
    def test_it_is_the_whole_image_lanczos_of_the_unpadded_input(self):
        for (iw, ih, pw, ph) in ((5000, 3000, 5008, 3008), (2900, 4100, 2912, 4104), (1800, 1200, 1800, 1200),
                                 (2048, 1000, 2048, 1000), (3000, 2048, 3000, 2048)):
            with tempfile.TemporaryDirectory() as td:
                src, arr = input_plane(td, iw, ih, pw, ph)
                got = banded_runner.live_proxy(src, (iw, ih), td)
                W2, H2 = lanczos_bands.proxy_size(iw, ih, 2048)
                self.assertEqual(got.shape, (H2, W2, 3))
                self.assertLessEqual(max(W2, H2), 2048)
                whole = np.asarray(Image.fromarray(np.ascontiguousarray(arr)).resize((W2, H2), Image.LANCZOS))
                np.testing.assert_array_equal(got, whole)                     # 0 differing values
                np.testing.assert_array_equal(got, lanczos_bands.resize_array(np.ascontiguousarray(arr), (W2, H2)))
                self.assertEqual(sorted(p.name for p in Path(td).iterdir()), ['input.plane'])   # its pass plane is gone

    def test_it_never_reads_the_whole_image(self):
        with tempfile.TemporaryDirectory() as td:
            Recording.largest = 0
            src, _ = input_plane(td, 6000, 4000, 6000, 4000)
            banded_runner.live_proxy(src, (6000, 4000), td)
            self.assertLessEqual(Recording.largest, lanczos_bands.ROW_BAND * 6000 * 3)
            self.assertLess(Recording.largest, 6000 * 4000 * 3 / 3)

    def test_its_memory_is_inside_the_service_term(self):
        self.assertLess(2048 * 2048 * 3 * 2, 30e6)                 # the proxy and the canvas's start picture: under 30 MB
        self.assertGreaterEqual(banded_plan.SERVICE_GB - 1.0, banded_runner.FINISH_ROWS_GB - 1e-9)
        self.assertAlmostEqual(banded_plan.SERVICE_GB, 1.2)


class TheCanvas(unittest.TestCase):
    def runner(self):
        r = object.__new__(Runner)
        r.live = live.LiveBoard(log=None)
        r.log = mock.Mock()
        return r

    def test_a_large_image_stage_keeps_no_full_size_picture(self):
        r = self.runner()
        ctx = SimpleNamespace(jid='j1', iid='i001', worker=SimpleNamespace(gpu=0, gpus=(0,), live_max_side=8192,
                                                                         live_groups=False))
        st = {'output_size': [32000, 20000], 'padded_size': [16000, 10000], 'input_size': [16000, 10000],
              'render_size': [32000, 20000], 'supersample': 1.0}
        it = {'media_id': 'm1', 'plan': {'output_size': [32000, 20000]}, 'alpha': False}
        proxy = Image.new('RGB', lanczos_bands.proxy_size(16000, 10000, 2048), (10, 20, 30))
        with mock.patch.object(live, 'FULL_BUDGET_MB', live.FULL_BUDGET_MB):
            c = r._live_begin(ctx, it, 2, 3, st, {'samplers': {'detail': '5', 'structure': '9'}},
                              {'live_preview': 'detailed'}, None, source=proxy, full=False)
        self.assertIsNotNone(c)
        self.assertIsNone(c.full)
        self.assertEqual(c.full_bytes, 0)
        self.assertLessEqual(max(c.size), live.MAX_SIDE)
        self.assertLessEqual(max(c.start_img.size), 2048)

    def test_the_stage_hands_the_proxy_to_the_canvas(self):
        with tempfile.TemporaryDirectory() as td:
            src, arr = input_plane(td, 3000, 2000, 3008, 2000)
            r = SimpleNamespace(_live_begin=mock.Mock(return_value='canvas'), log=mock.Mock())
            st = {'input_size': [3000, 2000]}
            out = banded_runner.live_begin(r, SimpleNamespace(jid='j', iid='i'), {}, 0, 1, st,
                                           {'spot_options': {'live_preview': 'rough'}}, src, td)
            self.assertEqual(out, 'canvas')
            kw = r._live_begin.call_args.kwargs
            self.assertFalse(kw['full'])
            self.assertEqual(kw['source'].size, lanczos_bands.proxy_size(3000, 2000, 2048))
            self.assertIsNone(r._live_begin.call_args.args[7])                 # no whole-image array
            self.assertIsNone(banded_runner.live_begin(r, SimpleNamespace(jid='j', iid='i'), {}, 0, 1, st,
                                                       {'spot_options': {}}, src, td))


class TheTracker(unittest.TestCase):
    def test_every_large_image_class_has_a_rate_and_its_twins_weight(self):
        twins = {'CUFinishBanded': 'ClaudeV4Finish', 'CUDecodePlane': 'VAEDecodeTiled', 'CUEncodePlane': 'VAEEncodeTiled',
                 'CUSam3DetectLean': 'SAM3_Detect', 'CUCannyPlane': 'ClaudeCannyTiled'}
        for cls, twin in twins.items():
            self.assertEqual(comfy.NODE_WEIGHTS[cls], comfy.NODE_WEIGHTS[twin], cls)
        silent = set(graph_banded.NODE_SPECS) - {'CUControlNetApplyPlane', 'ClaudeSpotTilesBanded'}
        self.assertEqual(silent - set(SILENT_NODES), set())
        g = {'1': {'class_type': 'CUFinishBanded', 'inputs': {}}, '2': {'class_type': 'KSampler', 'inputs': {}}}
        t = comfy.ProgressTracker(g, 'p')
        self.assertAlmostEqual(t.total, 8.0 + 40.0)


if __name__ == '__main__':
    unittest.main()
