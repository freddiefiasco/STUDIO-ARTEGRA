"""5.0.2 (build wave 2, service package, item 1; merge report item 15): after a restart, the viewer copies of a finished
Large-image result are made again from its planes only, never from a whole decode of the saved file (up to 1 GP, over
Pillow's guard). A Classic result keeps 5.0.1's path: the last stage file, else the saved file.

In process, with a Runner made without its start-up and a real media library in a temp folder (the pattern of
tests/test_memory_api.py and tests/test_views_planes.py). Sizes and synthetic pictures only."""
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import mock

import numpy as np
from PIL import Image

from engine import planes
from service import banded_runner, images, plane_views
from service.media import VIEW_FILES, MediaLibrary
from service.runner import LARGE_VIEWS_GONE, Runner

JID, IID, MID = 'j0123456789ab', 'i001', 'm0123456789ab'


def synth(h, w, seed=0):
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:h, 0:w]
    a = np.zeros((h, w, 3), np.uint8)
    a[..., 0] = ((x * 255) // max(1, w - 1)).astype(np.uint8)
    a[..., 1] = np.where(((x // 37) + (y // 23)) % 2 == 0, 200, 30).astype(np.uint8)
    a[..., 2] = rng.integers(0, 255, size=(h, w), dtype=np.uint8)
    return a


class Log:
    def __init__(self):
        self.lines = []

    def __getattr__(self, level):
        def say(event, msg='', *a, **kw):
            self.lines.append((level, event, msg))
        return say


class Store:
    def __init__(self, it):
        self.it = it
        self.updates = []

    def item(self, jid, iid):
        return self.it

    def update_item(self, jid, iid, **kw):
        self.updates.append(kw)
        self.it.update({k: v for k, v in kw.items() if k not in ('if_state', 'event', 'msg')})
        return self.it


class Recovery(unittest.TestCase):
    W, H = 640, 400

    def setUp(self):
        self.td = TemporaryDirectory()
        root = Path(self.td.name)
        self.log = Log()
        self.media = MediaLibrary(root / 'media', self.log)
        self.work_dir = root / 'work'
        self.work = self.work_dir / JID / IID
        self.work.mkdir(parents=True)
        self.out = root / 'out' / 'result.png'
        self.out.parent.mkdir()

    def tearDown(self):
        self.td.cleanup()

    def runner(self, it):
        r = object.__new__(Runner)
        r.cfg = SimpleNamespace(work_dir=self.work_dir)
        r.media, r.log, r.store = self.media, self.log, Store(it)
        r._lock = threading.RLock()
        r._views_inflight = {}
        return r

    def item(self, banded, n=2):
        stages = [{'index': k, 'output_size': [self.W, self.H]} for k in range(n)]
        plan = {'ok': True, 'output_size': [self.W, self.H], 'stages': stages}
        if banded:
            plan.update(engine='banded', banded={'bes': 'bes-1'})
        return {'id': IID, 'media_id': MID, 'state': 'done', 'plan': plan, 'output': str(self.out)}

    def save_output(self, arr):
        Image.fromarray(arr).save(self.out)

    def guarded_open(self, opened):
        """Image.open that refuses the saved result and every stage file (a whole decode), and records what it opens."""
        real = Image.open

        def guarded(fp, *a, **kw):
            name = Path(fp).name if isinstance(fp, (str, Path)) else ''
            opened.append(name)
            if Path(fp) == self.out or name.startswith('stage'):
                raise Image.DecompressionBombError('a whole decode of a Large-image result')
            return real(fp, *a, **kw)
        return guarded

    def test_a_large_image_result_is_remade_from_its_last_stage_plane_without_a_whole_decode(self):
        arr = synth(self.H, self.W)
        planes.from_array(self.work / banded_runner.stage_plane_name(1), arr)
        self.save_output(arr)
        it = self.item(banded=True)
        r = self.runner(it)
        opened = []
        with mock.patch.object(Image, 'open', self.guarded_open(opened)), \
                mock.patch.object(images, 'load_rgb', side_effect=AssertionError('a whole decode')):
            self.assertTrue(r.ensure_result_views(JID, IID))
        d = self.media.result_dir(JID, IID)
        self.assertTrue(plane_views.views_ready(d))
        self.assertTrue(plane_views.is_plane_result(d))
        self.assertFalse(any((d / n).is_file() for n in ('view.jpg',)))        # never a classic view of it
        self.assertNotIn(self.out.name, opened)
        np.testing.assert_array_equal(planes.Plane.open(d / plane_views.RESULT_PLANE).read_rows(0, self.H), arr)
        self.assertTrue(it['result_ready'])
        self.assertFalse(self.work.exists())                                   # the work folder goes, the views stay
        self.assertTrue((d / plane_views.RESULT_PLANE).is_file())

    def test_a_large_image_result_whose_proxies_failed_is_remade_from_the_viewer_folder(self):
        arr = synth(self.H, self.W, seed=3)
        d = self.media.result_dir(JID, IID)
        d.mkdir(parents=True)
        planes.from_array(d / plane_views.RESULT_PLANE, arr)                   # the plane is there, its proxies are not
        self.save_output(arr)
        it = self.item(banded=True)
        r = self.runner(it)
        opened = []
        with mock.patch.object(Image, 'open', self.guarded_open(opened)):
            self.assertTrue(r.ensure_result_views(JID, IID))
        self.assertTrue(plane_views.views_ready(d))
        self.assertNotIn(self.out.name, opened)

    def test_without_its_planes_a_large_image_result_is_never_decoded_whole(self):
        self.save_output(synth(self.H, self.W))
        it = self.item(banded=True)
        r = self.runner(it)
        opened = []
        with mock.patch.object(Image, 'open', self.guarded_open(opened)):
            self.assertFalse(r.ensure_result_views(JID, IID))
        self.assertEqual(opened, [])
        self.assertIn(('warn', 'result_view_failed', LARGE_VIEWS_GONE), self.log.lines)
        self.assertNotIn('result_ready', it)
        self.assertFalse((self.media.result_dir(JID, IID) / 'view.jpg').exists())

    def test_the_recovered_views_thread_takes_the_plane_path(self):
        arr = synth(self.H, self.W, seed=5)
        planes.from_array(self.work / banded_runner.stage_plane_name(0), arr)
        it = self.item(banded=True, n=1)
        r = self.runner(it)
        with mock.patch.object(images, 'load_rgb', side_effect=AssertionError('a whole decode')):
            r._views_safe(JID, IID)
        self.assertTrue(plane_views.views_ready(self.media.result_dir(JID, IID)))

    def test_a_classic_result_keeps_5_0_1s_path_from_the_last_stage_file(self):
        arr = synth(self.H, self.W, seed=1)
        Image.fromarray(synth(self.H // 2, self.W // 2)).save(self.work / 'stage0.png')
        Image.fromarray(arr).save(self.work / 'stage1.png')
        it = self.item(banded=False)
        r = self.runner(it)
        with mock.patch.object(images, 'load_rgb', wraps=images.load_rgb) as load:
            self.assertTrue(r.ensure_result_views(JID, IID))
        load.assert_called_once_with(self.work / 'stage1.png')
        d = self.media.result_dir(JID, IID)
        self.assertTrue(all((d / n).is_file() for n in VIEW_FILES))
        self.assertFalse(plane_views.is_plane_result(d))

    def test_a_classic_result_without_work_files_is_decoded_from_its_saved_file_as_before(self):
        arr = synth(self.H, self.W, seed=2)
        self.save_output(arr)
        it = self.item(banded=False)
        r = self.runner(it)
        real, opened = Image.open, []

        def spy(fp, *a, **kw):
            opened.append(Path(fp))
            return real(fp, *a, **kw)
        with mock.patch.object(Image, 'open', spy):
            self.assertTrue(r.ensure_result_views(JID, IID))
        self.assertIn(self.out, opened)
        d = self.media.result_dir(JID, IID)
        self.assertTrue(all((d / n).is_file() for n in VIEW_FILES))
        with Image.open(d / 'view.jpg') as im:
            self.assertEqual(im.size, (self.W, self.H))


if __name__ == '__main__':
    unittest.main()
