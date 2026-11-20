"""5.0.2: the viewer of a Large-image result (engine design section 2.10, B13; gate G8), on a media library built in a temp
folder and the real API handlers with stubs (the pattern of tests/test_memory_api.py): no service process, sizes and
synthetic images only.

- The sized copy (GET /api/media/<id>/proxy?w=&h=) is made once per result and size by the streamed T1 Lanczos downscale,
  kept on disk under the result's folder, holds the bytes of Pillow's whole-image resize(size, LANCZOS) at 0 differing
  values, is dropped with the result's views, and never needs a whole decode.
- A result with transparency gets RGBA PNG proxies, as the Classic engine's results do; they hold Pillow's RGBA resize
  (premultiplied, once around both passes) at 0 differing values.
- Regions are lossless plane crops at 28,000 and 32,000 px, at most 4096 x 4096 px.
- DecodedCache never decodes a Large-image result whole, and the API never rebuilds its views from the saved file.
- A Classic result keeps 5.0.1's viewer files and routes."""
import io
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import mock

import numpy as np
from PIL import Image

from engine import lanczos_bands, planes
from service import images, plane_io, plane_views
from service.api import _Handler
from service.errors import ApiError
from service.media import VIEW_FILES, VIEW_FILES_ALPHA, MediaLibrary

Image.MAX_IMAGE_PIXELS = None
JID, IID, MID = 'j0123456789ab', 'i001', 'm0123456789ab'


def synth(h, w, c=3, seed=0):
    """A synthetic card: hard geometric edges, a gradient and fine noise (no real image)."""
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:h, 0:w]
    a = np.zeros((h, w, c), np.uint8)
    a[..., 0] = ((x * 255) // max(1, w - 1)).astype(np.uint8)
    a[..., min(1, c - 1)] ^= np.where(((x // 37) + (y // 23)) % 2 == 0, 200, 30).astype(np.uint8)
    a[..., c - 1] = np.where((x - w // 3) ** 2 + (y - h // 2) ** 2 < (min(h, w) // 3) ** 2, 240, a[..., c - 1])
    a ^= rng.integers(0, 16, size=a.shape, dtype=np.uint8)
    return a


def soft_alpha(h, w, seed=0):
    """An alpha with fully clear and fully opaque blocks, the edge values 1 and 254, and soft ramps between."""
    rng = np.random.default_rng(seed + 7)
    y, x = np.mgrid[0:h, 0:w]
    a = ((x * 255) // max(1, w - 1)).astype(np.uint8)
    a = np.where(((x // 41) + (y // 19)) % 3 == 0, 0, a)
    a = np.where(((x // 53) + (y // 29)) % 5 == 1, 255, a)
    a = np.where((x + y) % 97 == 0, 1, a)
    a = np.where((x * 3 + y) % 89 == 0, 254, a)
    a ^= (rng.integers(0, 2, size=a.shape, dtype=np.uint8) * (a > 4) * (a < 250)).astype(np.uint8)
    return a[..., None].astype(np.uint8)


def whole_rgba(rgb, a, size):
    """Pillow's own whole-image RGBA resize: the oracle of every RGBA copy."""
    im = Image.frombuffer('RGBA', (rgb.shape[1], rgb.shape[0]), np.ascontiguousarray(np.concatenate([rgb, a], 2)),
                          'raw', 'RGBA', 0, 1)
    return np.asarray(im.resize(size, Image.LANCZOS))


def whole_rgb(rgb, size):
    return np.asarray(Image.fromarray(rgb).resize(size, Image.LANCZOS))


def jpeg_bytes(arr):
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, 'JPEG', quality=images.SIZED_JPEG_QUALITY, subsampling=0)
    return buf.getvalue()


def decoded(data):
    with Image.open(io.BytesIO(data)) as im:
        im.load()
        return np.asarray(im), im.mode


class Log:
    def __getattr__(self, name):
        return lambda *a, **k: None


class Media(unittest.TestCase):
    def setUp(self):
        self._td = TemporaryDirectory()
        self.dir = Path(self._td.name)
        self.media = MediaLibrary(self.dir / 'media', Log())
        self.media.records[MID] = {'id': MID, 'name': 'card.png', 'alpha': False}
        self.plan = {'engine': 'banded', 'output_size': [0, 0], 'stages': [{}]}

    def tearDown(self):
        self._td.cleanup()

    def result(self, w, h, alpha=False, seed=0, jid=JID, iid=IID):
        """A finished Large-image result: its stage plane in a work folder, then the viewer copy the runner makes."""
        rgb = synth(h, w, seed=seed)
        work = self.dir / 'work' / jid / iid
        work.mkdir(parents=True, exist_ok=True)
        plane = planes.from_array(work / f'stage-{seed}.u8', rgb)
        a = soft_alpha(h, w, seed) if alpha else None
        ap = planes.from_array(work / f'alpha-{seed}.plane', a) if alpha else None
        self.media.write_result_views_plane(jid, iid, plane, ap)
        self.plan['output_size'] = [w, h]
        return rgb, a

    def handler(self, plan=None, ensure=None):
        sent = []
        item = {'media_id': MID, 'state': 'done', 'plan': plan or self.plan}
        store = SimpleNamespace(item=lambda j, i: dict(item), latest_result=lambda mid: (JID, IID))
        runner = SimpleNamespace(ensure_result_views=ensure or mock.Mock(side_effect=AssertionError('no rebuild')),
                                 cfg=SimpleNamespace(work_dir=self.dir / 'work'), media=self.media, log=Log())
        h = object.__new__(_Handler)
        h.app = SimpleNamespace(media=self.media, store=store, runner=runner, log=Log())
        h._send = lambda status, body, ctype='application/json', extra=None: sent.append((status, body, ctype, extra or {}))
        return h, sent

    def ask(self, route, **q):
        h, sent = self.handler()
        q = {k: str(v) for k, v in q.items()}
        q.update(kind='result', job=JID, item=IID)
        getattr(h, route)(q, MID)
        self.assertEqual(len(sent), 1)
        return sent[0]

    def rdir(self):
        return self.media.result_dir(JID, IID)


class SizedCopy(Media):
    def test_made_once_per_size_and_equal_to_the_whole_image_lanczos(self):
        for (w, h), ask in (((28000, 120), (2000, 10)), ((32000, 96), (4000, 12)), ((300, 28000), (8, 800))):
            with self.subTest(size=(w, h)):
                rgb, _ = self.result(w, h, seed=w % 97)
                made = self.media.sized_planes.made
                served = images.sized_size(w, h, *ask)
                want = whole_rgb(rgb, served)
                np.testing.assert_array_equal(plane_views.pixels(planes.Plane.open(self.rdir() / 'result.plane'), None,
                                                                 served, self.dir), want)
                status, body, ctype, extra = self.ask('r_proxy', w=ask[0], h=ask[1])
                self.assertEqual((status, ctype), (200, 'image/jpeg'))
                self.assertEqual(body, jpeg_bytes(want))                       # 0 differing values, encoded as 5.0.1 does
                self.assertEqual(extra['X-Sized'], f'{served[0]},{served[1]}')
                self.assertEqual(extra['X-Image-Size'], f'{w},{h}')
                self.assertEqual(self.media.sized_planes.made, made + 1)
                with mock.patch.object(lanczos_bands, 'resize', side_effect=AssertionError('resampled again')):
                    again = self.ask('r_proxy', w=ask[0], h=ask[1])
                self.assertEqual(again[1], body)
                self.assertEqual(self.media.sized_planes.made, made + 1)       # the copy on disk, not a new resample
                kept = list((self.rdir() / plane_views.SIZED_DIR).glob(f'{served[0]}x{served[1]}-*.jpg'))
                self.assertEqual(len(kept), 1)
                self.assertEqual(kept[0].read_bytes(), body)

    def test_never_a_whole_decode_and_never_the_whole_plane_in_memory(self):
        w, h = 5000, 2 * lanczos_bands.ROW_BAND + 200          # more than two row bands, so a band is never the whole plane
        rgb, _ = self.result(w, h, seed=4)
        src = str(self.rdir() / 'result.plane')
        real_rows, real_cols, reads = planes.Plane.read_rows, planes.Plane.read_cols, []

        def rows(p, y0, y1, out=None):
            if str(p.path) == src:
                reads.append(('rows', (y1 - y0) * p.row_bytes))
            return real_rows(p, y0, y1, out)

        def cols(p, x0, x1):
            if str(p.path) == src:
                reads.append(('cols', (x1 - x0) * p.shape[0] * p.shape[2]))
            return real_cols(p, x0, x1)
        with mock.patch.object(planes.Plane, 'read_rows', rows), mock.patch.object(planes.Plane, 'read_cols', cols), \
                mock.patch.object(images.DecodedCache, 'get', side_effect=AssertionError('whole decode')), \
                mock.patch.object(Image, 'open', side_effect=AssertionError('whole decode')):
            status, body, _, _ = self.ask('r_proxy', w=1000, h=200)
        self.assertEqual(status, 200)
        self.assertTrue(reads)
        self.assertLessEqual(max(n for _, n in reads), lanczos_bands.ROW_BAND * w * 3)
        self.assertLess(max(n for _, n in reads), w * h * 3)
        served = images.sized_size(w, h, 1000, 200)
        self.assertEqual(body, jpeg_bytes(whole_rgb(rgb, served)))

    def test_sizes_are_bounded_per_result_and_dropped_with_its_views(self):
        self.result(4000, 64, seed=2)
        asks = [(100 + 10 * k, 2) for k in range(plane_views.PER_ITEM + 2)]
        for ask in asks:
            self.ask('r_proxy', w=ask[0], h=ask[1])
        kept = sorted(p.name for p in (self.rdir() / plane_views.SIZED_DIR).glob('*.jpg'))
        self.assertEqual(len(kept), plane_views.PER_ITEM)
        self.assertFalse(any(n.startswith(f'{asks[0][0]}x') for n in kept))  # the least recently used went first
        self.assertTrue(self.media.drop_sized_copies(JID, IID))
        self.assertFalse((self.rdir() / plane_views.SIZED_DIR).exists())
        self.assertTrue(self.media.result_views_ready(JID, IID))              # the plane and proxies stay for the viewer
        made = self.media.sized_planes.made
        self.ask('r_proxy', w=500, h=8)
        self.assertEqual(self.media.sized_planes.made, made + 1)

    def test_a_new_result_for_the_item_drops_the_old_copies(self):
        self.result(4000, 64, seed=2)
        first = self.ask('r_proxy', w=1000, h=16)[1]
        rgb, _ = self.result(4000, 64, seed=3)
        second = self.ask('r_proxy', w=1000, h=16)[1]
        self.assertNotEqual(first, second)
        self.assertEqual(second, jpeg_bytes(whole_rgb(rgb, (1000, 16))))
        self.assertEqual(len(list((self.rdir() / plane_views.SIZED_DIR).glob('*.jpg'))), 1)

    def test_two_layers_asking_at_once_make_one_copy(self):
        self.result(6000, 200, seed=5)
        barrier, out = threading.Barrier(4), []

        def one():
            barrier.wait()
            out.append(self.ask('r_proxy', w=1500, h=50)[1])
        threads = [threading.Thread(target=one) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(60)
        self.assertEqual(len(out), 4)
        self.assertEqual(len(set(out)), 1)
        self.assertEqual(self.media.sized_planes.made, 1)
        self.assertEqual(list(self.rdir().glob('*.tmp*')) + list((self.rdir() / plane_views.SIZED_DIR).glob('*.tmp*')), [])

    def test_bad_sizes_are_refused(self):
        self.result(4000, 64)
        for bad in ((0, 10), (10, images.SIZED_MAX_SIDE + 1)):
            h, _ = self.handler()
            with self.assertRaises(ApiError) as e:
                h.r_proxy({'w': str(bad[0]), 'h': str(bad[1]), 'kind': 'result', 'job': JID, 'item': IID}, MID)
            self.assertEqual(e.exception.status, 400)


class RgbaProxies(Media):
    def test_proxies_are_rgba_pngs_equal_to_pillows_rgba_resize(self):
        for w, h in ((28000, 64), (64, 32000), (5000, 3000)):
            with self.subTest(size=(w, h)):
                rgb, a = self.result(w, h, alpha=True, seed=h % 13)
                d = self.rdir()
                self.assertTrue((d / 'proxy.png').is_file() and (d / 'thumb.png').is_file())
                self.assertFalse((d / 'proxy.jpg').exists() or (d / 'thumb.jpg').exists())
                psize = images.preview_size(w, h, images.PROXY_SIDE)
                want = whole_rgba(rgb, a, psize)
                got, mode = decoded((d / 'proxy.png').read_bytes())
                self.assertEqual(mode, 'RGBA')
                np.testing.assert_array_equal(got, want)
                tsize = images.preview_size(w, h, images.THUMB_SIDE)
                pim = Image.frombuffer('RGBA', psize, np.ascontiguousarray(want), 'raw', 'RGBA', 0, 1)
                twant = np.asarray(pim.resize(tsize, Image.LANCZOS, reducing_gap=2.0))   # the classic's own thumb step
                np.testing.assert_array_equal(decoded((d / 'thumb.png').read_bytes())[0], twant)
                self.assertEqual(MediaLibrary.display_file(d, 'proxy'), (d / 'proxy.png', 'image/png'))
                self.assertTrue(self.media.result_views_ready(JID, IID))

    def test_the_pure_rgba_resize_at_every_pass_combination(self):
        a = synth(700, 900, seed=9)
        al = soft_alpha(700, 900, seed=9)
        for size in ((300, 200), (900, 250), (250, 700), (900, 700), (1, 1)):
            with self.subTest(size=size):
                p = planes.from_array(self.dir / f'c{size}.plane', a)
                ap = planes.from_array(self.dir / f'a{size}.plane', al)
                want = whole_rgba(a, al, size)
                np.testing.assert_array_equal(plane_views.pixels(p, ap, size, self.dir), want)

    def test_pillows_own_pass_order_is_kept(self):
        # Pillow 12.3's Image.resize runs the vertical pass first for a picture over 100 times taller than wide
        # (PIL/Image.py); every copy keeps Pillow's values on both sides of that line.
        for w, h, size in ((64, 6400, (4, 400)), (64, 6480, (4, 405)), (64, 8000, (4, 500)), (200, 32000, (13, 2048)),
                           (64, 8000, (64, 500)), (300, 28000, (300, 28000))):
            with self.subTest(size=(w, h), to=size):
                a, al = synth(h, w, seed=w), soft_alpha(h, w, seed=w)
                p = planes.from_array(self.dir / f'p{w}x{h}.plane', a)
                ap = planes.from_array(self.dir / f'a{w}x{h}.plane', al)
                np.testing.assert_array_equal(plane_views.pixels(p, None, size, self.dir), whole_rgb(a, size))
                np.testing.assert_array_equal(plane_views.pixels(p, ap, size, self.dir), whole_rgba(a, al, size))
        self.assertTrue(plane_views.vertical_first(64, 6480, 4, 405))
        self.assertFalse(plane_views.vertical_first(64, 6400, 4, 400))
        self.assertFalse(plane_views.vertical_first(64, 8000, 4, 8000))

    def test_sized_copies_with_alpha_are_rgba_pngs(self):
        rgb, a = self.result(28000, 96, alpha=True, seed=3)
        status, body, ctype, extra = self.ask('r_proxy', w=2800, h=10)
        self.assertEqual((status, ctype), (200, 'image/png'))
        got, mode = decoded(body)
        self.assertEqual(mode, 'RGBA')
        np.testing.assert_array_equal(got, whole_rgba(rgb, a, (2800, 10)))

    def test_opaque_proxies_are_unchanged(self):
        rgb, _ = self.result(28000, 300, seed=1)
        d = self.rdir()
        self.assertEqual(sorted(p.name for p in d.iterdir() if p.is_file()), ['proxy.jpg', 'result.plane', 'thumb.jpg'])
        px = whole_rgb(rgb, images.preview_size(28000, 300, images.PROXY_SIDE))
        np.testing.assert_array_equal(px, plane_io.proxy(planes.Plane.open(d / 'result.plane'), self.dir,
                                                        images.PROXY_SIDE))
        buf = io.BytesIO()
        Image.fromarray(px).save(buf, 'JPEG', quality=90)
        self.assertEqual((d / 'proxy.jpg').read_bytes(), buf.getvalue())


class Regions(Media):
    def test_regions_are_plane_crops_at_28000_and_32000_px(self):
        for w, h, alpha in ((28000, 200, False), (32000, 160, False), (32000, 96, True), (120, 28000, True)):
            with self.subTest(size=(w, h), alpha=alpha):
                rgb, a = self.result(w, h, alpha=alpha, seed=w % 11)
                full = np.concatenate([rgb, a], 2) if alpha else rgb
                x, y = max(0, w - 1000), max(0, h - 4096)
                with mock.patch.object(images.DecodedCache, 'get', side_effect=AssertionError('whole decode')):
                    status, body, ctype, extra = self.ask('r_region', x=x, y=y, w=4096, h=4096)
                self.assertEqual((status, ctype), (200, 'image/png'))
                got, mode = decoded(body)
                self.assertEqual(mode, 'RGBA' if alpha else 'RGB')
                np.testing.assert_array_equal(got, full[y:y + 4096, x:x + 4096])
                self.assertEqual(extra['X-Region'], f'{x},{y},{min(4096, w - x)},{min(4096, h - y)}')
                self.assertEqual(extra['X-Image-Size'], f'{w},{h}')

    def test_regions_stay_at_most_4096_px(self):
        self.result(32000, 64)
        for w, h in ((4097, 10), (10, 4097), (0, 10)):
            hd, _ = self.handler()
            with self.assertRaises(ApiError) as e:
                hd.r_region({'x': '0', 'y': '0', 'w': str(w), 'h': str(h), 'kind': 'result', 'job': JID, 'item': IID}, MID)
            self.assertEqual((e.exception.status, e.exception.code), (400, 'bad_region'))


class NoWholeDecode(Media):
    def test_decoded_cache_refuses_a_large_image_result(self):
        self.result(3000, 2000, seed=6)
        d = self.rdir()
        Image.fromarray(synth(2000, 3000)).save(d / 'view.jpg', 'JPEG', quality=95)      # a stray full-size view
        self.assertIsInstance(self.media.decoded, plane_views.GuardedDecodedCache)
        self.assertIs(self.media.sized.decoded, self.media.decoded)
        with self.assertRaises(plane_views.WholeDecodeRefused):
            self.media.decoded.get(d / 'view.jpg')
        self.assertEqual(self.media.decoded.decodes, 0)

    def test_decoded_cache_decodes_a_classic_result_as_before(self):
        rgb = synth(300, 400, seed=2)
        self.media.write_result_views(JID, IID, rgb, None)
        p = self.rdir() / 'view.jpg'
        got = self.media.decoded.get(p)
        ref = images.DecodedCache(size=2).get(p)
        np.testing.assert_array_equal(np.asarray(got), np.asarray(ref))
        self.assertEqual(self.media.decoded.decodes, 1)

    def test_the_api_never_rebuilds_a_large_image_result_from_its_saved_file(self):
        self.media.records[MID]['alpha'] = False
        ensure = mock.Mock(side_effect=AssertionError('would decode the saved file whole'))
        h, sent = self.handler(plan={'engine': 'banded', 'output_size': [4000, 64], 'stages': [{}]}, ensure=ensure)
        with self.assertRaises(ApiError) as e:                  # nothing in the result folder, no work folder: say so
            h.r_proxy({'kind': 'result', 'job': JID, 'item': IID}, MID)
        self.assertEqual((e.exception.status, e.exception.code), (404, 'result_preview_missing'))
        ensure.assert_not_called()

    def test_missing_proxies_are_made_again_from_the_result_plane(self):
        rgb, a = self.result(5000, 80, alpha=True, seed=8)
        for name in ('proxy.png', 'thumb.png'):
            (self.rdir() / name).unlink()
        self.assertFalse(self.media.result_views_ready(JID, IID))
        status, body, ctype, _ = self.ask('r_proxy')
        self.assertEqual((status, ctype), (200, 'image/png'))
        np.testing.assert_array_equal(decoded(body)[0], whole_rgba(rgb, a, images.preview_size(5000, 80, images.PROXY_SIDE)))

    def test_a_large_image_stage_plane_still_in_the_work_folder_makes_the_views(self):
        rgb = synth(64, 4000, seed=12)
        work = self.dir / 'work' / JID / IID
        work.mkdir(parents=True)
        planes.from_array(work / 'stage0.u8', rgb)
        h, sent = self.handler(plan={'engine': 'banded', 'output_size': [4000, 64], 'stages': [{}]})
        h.r_proxy({'kind': 'result', 'job': JID, 'item': IID}, MID)
        self.assertEqual(sent[0][:1], (200,))
        self.assertTrue(self.media.result_views_ready(JID, IID))


class ClassicResults(Media):
    def test_classic_viewer_files_and_routes_are_5_0_1s(self):
        rgb = synth(300, 400, seed=3)
        self.media.write_result_views(JID, IID, rgb, None)
        self.assertEqual(sorted(p.name for p in self.rdir().iterdir()), sorted(VIEW_FILES))
        ensure = mock.Mock(return_value=True)
        h, sent = self.handler(plan={'output_size': [400, 300], 'stages': [{}]}, ensure=ensure)
        h.r_proxy({'w': '200', 'h': '150', 'kind': 'result', 'job': JID, 'item': IID}, MID)
        ensure.assert_called_once_with(JID, IID)
        img = images.DecodedCache().get(self.rdir() / 'view.jpg')
        self.assertEqual(sent[0][1], images.sized_copy(img, 200, 150)[0])
        self.assertEqual(self.media.sized_planes.made, 0)

    def test_classic_results_with_alpha_keep_their_files(self):
        rgb, a = synth(300, 400, seed=4), soft_alpha(300, 400)[..., 0]
        self.media.write_result_views(JID, IID, rgb, a)
        self.assertEqual(sorted(p.name for p in self.rdir().iterdir()), sorted(VIEW_FILES_ALPHA))
        self.assertTrue(self.media.result_views_ready(JID, IID))
        self.assertEqual(MediaLibrary.result_plane(self.rdir()), (None, None))


if __name__ == '__main__':
    unittest.main()
