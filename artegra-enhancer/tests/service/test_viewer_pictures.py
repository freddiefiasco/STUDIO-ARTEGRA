import io
import os
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image

from service import engine_options, images, live, workers
from tests.service.helpers import rmtree, tmpdir
from tests.service.test_integration import all_done
from tests.service.test_v4 import V4Base, wait

GREY = (128, 127, 125)


def smooth(w, h, seed=0):
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    r = 127 + 100 * np.sin(x / (23.0 + seed)) * np.cos(y / 31.0)
    g = 127 + 100 * np.sin((x + y) / 41.0)
    b = 255 * x / max(1, w - 1) * 0.5 + 255 * y / max(1, h - 1) * 0.5
    return np.clip(np.stack([r, g, b], -1), 0, 255).astype(np.uint8)


def png(size, color):
    buf = io.BytesIO()
    Image.new('RGB', size, color).save(buf, 'PNG')
    return buf.getvalue()


def png_of(img):
    buf = io.BytesIO()
    img.save(buf, 'PNG')
    return buf.getvalue()


def pixels(data):
    return np.asarray(Image.open(io.BytesIO(data)).convert('RGB')).astype(np.float64)


class SizedSize(unittest.TestCase):
    def test_exact_when_the_picture_is_large_enough(self):
        self.assertEqual(images.sized_size(4000, 3000, 800, 600), (800, 600))
        self.assertEqual(images.sized_size(4000, 3000, 4000, 3000), (4000, 3000))
        self.assertEqual(images.sized_size(4000, 3000, 1, 1), (1, 1))
        self.assertEqual(images.sized_size(7680, 4800, 1242, 776), (1242, 776))

    def test_never_larger_than_the_picture(self):
        self.assertEqual(images.sized_size(4000, 3000, 8000, 6000), (4000, 3000))
        self.assertEqual(images.sized_size(96, 72, 672, 420), (96, 60))
        self.assertEqual(images.sized_size(4000, 3000, 5000, 100), (4000, 80))
        for iw, ih, w, h in ((101, 67, 8192, 8192), (64, 8000, 8192, 1), (3840, 2400, 3841, 2400), (1, 1, 5, 9)):
            sw, sh = images.sized_size(iw, ih, w, h)
            self.assertTrue(1 <= sw <= min(iw, w) and 1 <= sh <= min(ih, h), (iw, ih, w, h, sw, sh))


class SizedCopy(unittest.TestCase):
    def test_an_opaque_picture_is_a_sharp_jpeg_of_exactly_the_size_asked(self):
        src = Image.fromarray(smooth(1600, 1200))
        data, ctype, size = images.sized_copy(src, 400, 300)
        self.assertEqual((ctype, size), ('image/jpeg', (400, 300)))
        got = Image.open(io.BytesIO(data))
        self.assertEqual((got.format, got.size, got.mode), ('JPEG', (400, 300), 'RGB'))

        self.assertEqual({tuple(layer[1:3]) for layer in got.layer}, {(1, 1)})
        ideal = np.asarray(src.resize((400, 300), Image.LANCZOS)).astype(np.float64)
        self.assertLess(np.abs(pixels(data) - ideal).mean(), 1.0)
        self.assertEqual(src.size, (1600, 1200))

    def test_it_is_sharper_than_the_2048_px_copy_drawn_smaller(self):
        rng = np.random.default_rng(3)
        fine = np.repeat(np.repeat(rng.integers(0, 2, (300, 480), dtype=np.uint8) * 255, 16, 0), 16, 1)
        src = Image.fromarray(np.stack([fine] * 3, -1))
        ideal = np.asarray(src.resize((1242, 776), Image.LANCZOS)).astype(np.float64)
        proxy = src.copy()
        proxy.thumbnail((2048, 2048), Image.LANCZOS)
        twice = proxy.resize((2484, 1552), Image.BILINEAR).resize((1242, 776), Image.BILINEAR)
        data, _, size = images.sized_copy(src, 1242, 776)
        self.assertEqual(size, (1242, 776))
        ours, old = np.abs(pixels(data) - ideal).mean(), np.abs(np.asarray(twice).astype(np.float64) - ideal).mean()
        self.assertLess(ours, 2.5)
        self.assertGreater(old, 3 * ours)

    def test_transparency_is_kept_and_does_not_bleed(self):
        a = np.zeros((600, 800, 4), np.uint8)
        a[:, :400] = (100, 100, 100, 255)
        a[:, 400:] = (255, 0, 255, 0)
        data, ctype, size = images.sized_copy(Image.fromarray(a, 'RGBA'), 200, 150)
        self.assertEqual((ctype, size), ('image/png', (200, 150)))
        got = np.asarray(Image.open(io.BytesIO(data)))
        self.assertEqual(got.shape, (150, 200, 4))
        solid = got[got[..., 3] > 200]
        self.assertTrue((np.abs(solid[:, :3].astype(int) - 100) <= 2).all())
        self.assertEqual((got[75, 10, 3], got[75, 190, 3]), (255, 0))

    def test_a_larger_ask_is_the_picture_itself(self):
        src = Image.fromarray(smooth(96, 72))
        data, ctype, size = images.sized_copy(src, 960, 720)
        self.assertEqual((ctype, size, Image.open(io.BytesIO(data)).size), ('image/jpeg', (96, 72), (96, 72)))


class SizedCache(unittest.TestCase):
    def setUp(self):
        self.d = tmpdir('cu-sized-')
        self.p = self.d / 'source.png'
        Image.fromarray(smooth(800, 600)).save(self.p)
        self.decoded = images.DecodedCache(size=2)

    def tearDown(self):
        rmtree(self.d)

    def test_made_once_and_kept(self):
        c = images.SizedCopies(self.decoded)
        a = c.get(self.p, None, 400, 300)
        b = c.get(self.p, None, 400, 300)
        self.assertIs(a, b)
        self.assertEqual((c.made, self.decoded.decodes), (1, 1))
        self.assertEqual((a[1], a[2], a[3]), ('image/jpeg', (400, 300), (800, 600)))
        c.get(self.p, None, 1600, 1200)
        c.get(self.p, None, 2400, 1800)
        self.assertEqual(c.made, 2)
        self.assertEqual(self.decoded.decodes, 1)

    def test_a_changed_file_is_made_again(self):
        c = images.SizedCopies(self.decoded)
        first = c.get(self.p, None, 400, 300)[0]
        time.sleep(0.05)
        Image.fromarray(smooth(800, 600, seed=9)).save(self.p)
        os.utime(self.p, ns=(time.time_ns(), time.time_ns() + 5_000_000_000))
        second = c.get(self.p, None, 400, 300)[0]
        self.assertEqual(c.made, 2)
        self.assertNotEqual(first, second)

    def test_bounded_per_picture_and_in_all(self):
        c = images.SizedCopies(self.decoded, per_picture=3)
        for w in (100, 120, 140, 160, 180):
            c.get(self.p, None, w, w * 3 // 4)
        self.assertEqual(len(c._d), 3)
        self.assertEqual([k[1] for k in c._d], [140, 160, 180])
        c.get(self.p, None, 140, 105)
        c.get(self.p, None, 200, 150)
        self.assertEqual([k[1] for k in c._d], [180, 140, 200])
        one = len(c.get(self.p, None, 400, 300)[0])
        small = images.SizedCopies(self.decoded, max_bytes=int(one * 2.5), per_picture=50)
        for w in (400, 404, 408, 412, 416):
            small.get(self.p, None, w, w * 3 // 4)
        self.assertLessEqual(small.bytes_held(), int(one * 2.5))
        self.assertLess(len(small._d), 5)
        tiny = images.SizedCopies(self.decoded, max_bytes=one)
        tiny.get(self.p, None, 400, 300)
        self.assertEqual((len(tiny._d), tiny.made), (0, 1))

    def test_sizes_outside_the_range_are_refused(self):
        c = images.SizedCopies(self.decoded)
        for w, h in ((0, 10), (10, 0), (-5, 5), (images.SIZED_MAX_SIDE + 1, 10)):
            with self.assertRaises(ValueError):
                c.get(self.p, None, w, h)
        self.assertEqual(c.made, 0)

    def test_many_asks_for_one_copy_resample_once(self):
        c = images.SizedCopies(self.decoded)
        got, errors = [], []

        def ask():
            try:
                got.append(c.get(self.p, None, 640, 480))
            except Exception as e:
                errors.append(e)
        ts = [threading.Thread(target=ask) for _ in range(8)]
        for t in ts:
            t.start()
        for t in ts:
            t.join(30)
        self.assertEqual((errors, len(got), c.made), ([], 8, 1))
        self.assertTrue(all(g[0] == got[0][0] for g in got))


class SizedRoute(V4Base):

    def test_source_result_alpha_and_refusals(self):
        self.svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '0.3'})
        d = self.d / 'in'
        d.mkdir(parents=True, exist_ok=True)
        Image.fromarray(smooth(800, 600)).save(d / 'opaque.png')
        rgba = np.dstack([smooth(400, 300, 4), np.tile(np.linspace(0, 255, 400).astype(np.uint8), (300, 1))])
        Image.fromarray(rgba, 'RGBA').save(d / 'cutout.png')
        opaque, cutout = (it['id'] for it in self.add(self.svc, [d / 'opaque.png', d / 'cutout.png'])['items'])
        code, health, _ = self.svc.get('/health')
        self.assertIs(health['features']['sized_proxy'], True)


        code, data, hdr = self.svc.get(f'/api/media/{opaque}/proxy?w=400&h=300', raw=True)
        self.assertEqual((code, hdr['Content-Type']), (200, 'image/jpeg'))
        self.assertEqual((hdr['X-Sized'], hdr['X-Image-Size']), ('400,300', '800,600'))
        self.assertEqual(Image.open(io.BytesIO(data)).size, (400, 300))
        ideal = np.asarray(Image.fromarray(smooth(800, 600)).resize((400, 300), Image.LANCZOS)).astype(np.float64)
        self.assertLess(np.abs(pixels(data) - ideal).mean(), 1.0)
        again = self.svc.get(f'/api/media/{opaque}/proxy?w=400&h=300', raw=True)[1]
        self.assertEqual(again, data)

        code, big, hdr = self.svc.get(f'/api/media/{opaque}/proxy?w=1600&h=1200', raw=True)
        self.assertEqual((code, hdr['X-Sized'], Image.open(io.BytesIO(big)).size), (200, '800,600', (800, 600)))

        code, cut, hdr = self.svc.get(f'/api/media/{cutout}/proxy?w=200&h=150', raw=True)
        self.assertEqual((code, hdr['Content-Type'], hdr['X-Sized']), (200, 'image/png', '200,150'))
        im = Image.open(io.BytesIO(cut))
        self.assertEqual((im.mode, im.size), ('RGBA', (200, 150)))
        alpha = np.asarray(im)[..., 3]
        self.assertLess(alpha[:, 2].mean(), 10)
        self.assertGreater(alpha[:, -3].mean(), 245)

        code, plain, hdr = self.svc.get(f'/api/media/{opaque}/proxy', raw=True)
        self.assertEqual((code, hdr['Content-Type'], Image.open(io.BytesIO(plain)).size), (200, 'image/jpeg', (800, 600)))
        self.assertIsNone(hdr.get('X-Sized'))
        self.assertEqual(plain, (self.d / 'state/media' / opaque / 'proxy.jpg').read_bytes())

        for query in ('w=400', 'h=300', 'w=abc&h=300', 'w=0&h=300', 'w=400&h=-1', f'w={images.SIZED_MAX_SIDE + 1}&h=300'):
            code, err, _ = self.svc.get(f'/api/media/{opaque}/proxy?{query}')
            self.assertEqual((code, err['error']['code']), (400, 'bad_request'), query)
        code, err, _ = self.svc.get('/api/media/m000000000000/proxy?w=10&h=10')
        self.assertEqual((code, err['error']['code']), (404, 'unknown_image'))
        code, err, _ = self.svc.get(f'/api/media/{opaque}/proxy?kind=result&w=10&h=10')
        self.assertEqual((code, err['error']['code']), (404, 'no_result'))


        job = self.job(self.svc, [opaque, cutout], {'scale': 2})
        job = self.svc.wait_job(job['id'], all_done, timeout=90)
        self.assertEqual([it['state'] for it in job['items']], ['done', 'done'])
        it = job['items'][0]
        url = it['result_proxy_url']
        self.assertIn('kind=result', url)
        code, res, hdr = self.svc.get(url + '&w=640&h=480', raw=True)
        self.assertEqual((code, hdr['Content-Type'], hdr['X-Sized'], hdr['X-Image-Size']),
                         (200, 'image/jpeg', '640,480', '1600,1200'))
        view = Image.open(self.d / 'state/media/results' / f'{job["id"]}_{it["id"]}' / 'view.jpg').convert('RGB')
        ideal = np.asarray(view.resize((640, 480), Image.LANCZOS)).astype(np.float64)
        self.assertLess(np.abs(pixels(res) - ideal).mean(), 1.0)
        code, res2, hdr = self.svc.get(f'/api/media/{opaque}/proxy?kind=result&w=640&h=480', raw=True)
        self.assertEqual((code, res2), (200, res))
        code, cres, hdr = self.svc.get(job['items'][1]['result_proxy_url'] + '&w=400&h=300', raw=True)
        self.assertEqual((code, hdr['Content-Type']), (200, 'image/png'))
        self.assertEqual(Image.open(io.BytesIO(cres)).mode, 'RGBA')

        names = {p.name for p in (self.d / 'state/media' / opaque).iterdir()}
        self.assertEqual(names, {'media.json', 'source.png', 'thumb.jpg', 'proxy.jpg'})
        self.assertEqual(self.svc.shutdown(), 0)


def canvas(full_scale=2.0, out=(4096, 4096), frame=None, src=None, mode='detailed', alpha=False, s=2.0):
    src = src if src is not None else Image.new('RGB', (out[0] // 2, out[1] // 2), GREY)
    return live.LiveCanvas('j1', 'i001', 'm1', 0, 1, out, s, frame or out, {'structure': '19', 'detail': '15'}, mode, [0],
                           alpha=alpha, source=src, full_scale=full_scale)


def init(c, pass_no=1, latent=(1024, 1024), source='taesd', image=False, data=b''):
    c.on_frame({'kind': 'init', 'pass': pass_no, 'node': '19' if pass_no == 1 else '15', 'steps': 30,
                'canvas_latent': list(latent), 'image': image, 'source': source}, data)


def tile(c, rect, color, step=29, px=(1024, 1024), latent=(1024, 1024), source='taesd', **more):
    c.on_frame(dict({'kind': 'win', 'step': step, 'steps': 30, 'rect_latent': list(rect), 'canvas_latent': list(latent),
                     'image': True, 'source': source}, **more), color if isinstance(color, bytes) else png(px, color))


def region(c, x, y, w, h):
    got = c.region(x, y, w, h)
    return None if got is None else (np.asarray(Image.open(io.BytesIO(got[0])).convert('RGB')).astype(np.float64),) + got[1:]


class Switch(unittest.TestCase):
    def setUp(self):
        self.saved = os.environ.pop('CU_LIVE_REGIONS', None)
        self.d = tmpdir('cu-lr-')

    def tearDown(self):
        os.environ.pop('CU_LIVE_REGIONS', None)
        if self.saved is not None:
            os.environ['CU_LIVE_REGIONS'] = self.saved
        rmtree(self.d)

    def test_on_in_the_product_since_its_cost_was_measured(self):
        self.assertIs(engine_options.LIVE_REGIONS_PROVEN, True)
        self.assertIs(engine_options.live_regions_on(), True)
        os.environ['CU_LIVE_REGIONS'] = '0'
        self.assertIs(engine_options.live_regions_on(), False)
        os.environ['CU_LIVE_REGIONS'] = '1'
        self.assertIs(engine_options.live_regions_on(), True)
        os.environ['CU_LIVE_REGIONS'] = 'yes'
        self.assertIs(engine_options.live_regions_on(), True)

    def test_the_tiles_scale_follows_the_emitter(self):
        f = engine_options.live_tile_scale
        self.assertIsNone(f(2048, (8192, 8192), 2))
        self.assertIsNone(f(None, (8192, 8192), 2))
        self.assertEqual(f(8192, (8192, 8192), 2), 2.0)
        self.assertAlmostEqual(f(8192, (15360, 9600), 2), 1.0667, places=4)
        self.assertAlmostEqual(f(8192, (15360, 9600), 1), 0.5333, places=4)
        self.assertEqual(engine_options.LIVE_REGION_MAX_SIDE, 8192)

    def test_only_the_worker_environment_changes_and_only_when_on(self):
        saved = os.environ.pop('CLAUDE_LIVE_MAX_SIDE', None)
        try:
            w = workers.Worker(0, SimpleNamespace(workers_dir=Path(self.d)), None, None, 'fake')
            os.environ['CU_LIVE_REGIONS'] = '0'
            env = w._env()
            self.assertNotIn('CLAUDE_LIVE_MAX_SIDE', env)
            self.assertEqual(w.live_max_side, 2048)
            os.environ['CU_LIVE_REGIONS'] = '1'
            env2 = w._env()
            self.assertEqual(env2['CLAUDE_LIVE_MAX_SIDE'], '8192')
            self.assertEqual(w.live_max_side, 8192)
            same = {k: v for k, v in env2.items() if k not in ('CLAUDE_LIVE_MAX_SIDE', 'CU_LIVE_REGIONS')}
            self.assertEqual(same, {k: v for k, v in env.items() if k != 'CU_LIVE_REGIONS'})
            os.environ.pop('CU_LIVE_REGIONS')
            self.assertEqual(w._env()['CLAUDE_LIVE_MAX_SIDE'], '8192')
            self.assertEqual(w.live_max_side, 8192)


            real = workers.Worker(0, SimpleNamespace(workers_dir=Path(self.d)), None, None, 'comfy')
            os.environ['CU_LIVE_REGIONS'] = '0'
            self.assertNotIn('CLAUDE_LIVE_MAX_SIDE', real._env())
            os.environ['CU_LIVE_REGIONS'] = '1'
            self.assertEqual(real._env()['CLAUDE_LIVE_MAX_SIDE'], '8192')
            os.environ.pop('CU_LIVE_REGIONS')
        finally:
            if saved is not None:
                os.environ['CLAUDE_LIVE_MAX_SIDE'] = saved

    def test_the_node_pack_and_the_graph_are_not_touched_by_it(self):
        repo = Path(__file__).resolve().parents[2]
        text = (repo / 'node_pack/claude_creative/live.py').read_text(encoding='utf8')
        self.assertIn("os.environ.get('CLAUDE_LIVE_MAX_SIDE', '2048')", text)
        for name in ('engine/graph_v5t.py', 'engine/controls.py', 'engine/fast_recipe.py'):
            body = (repo / name).read_text(encoding='utf8')
            self.assertNotIn('LIVE_MAX_SIDE', body, name)
            self.assertNotIn('live_regions', body, name)


class OffIsAsBefore(unittest.TestCase):

    def run_frames(self, c):
        init(c)
        tile(c, (0, 0, 128, 128), (10, 200, 30), step=3, px=(256, 256))
        tile(c, (128, 256, 128, 128), (250, 10, 10), step=29, px=(256, 256))
        tile(c, (960, 960, 128, 128), (5, 5, 250), step=29, px=(256, 256))

    def test_no_full_size_picture_and_the_same_canvas(self):
        off = canvas(full_scale=None)
        self.assertIsNone(off.full)
        self.assertEqual((off.full_note, off.large_tiles, off.full_bytes), ('off', False, 0))
        self.run_frames(off)
        snap = off.snapshot('/api/jobs/j1/items/i001')
        self.assertIsNone(snap['region_url'])
        self.assertIsNone(snap['region_scale'])
        self.assertIsNone(off.region(0, 0, 64, 64))
        self.assertIsNone(off.src_img)

        on = canvas(full_scale=2.0)
        self.run_frames(on)
        self.assertTrue((np.asarray(off.img) == np.asarray(on.img)).all())
        self.assertEqual(off.paint_seq, on.paint_seq)

    def test_every_field_the_canvas_had_is_still_there(self):
        c = canvas(full_scale=None)
        self.run_frames(c)
        snap = c.snapshot('/api/jobs/j1/items/i001')
        for key in ('job_id', 'item_id', 'media_id', 'state', 'preview', 'card', 'cards', 'split', 'stage', 'stages', 'pass',
                    'pass_index', 'passes', 'step', 'steps', 'rects', 'image_seq', 'canvas_url', 'canvas_size', 'thumb_url',
                    'frame', 'alpha', 'fallback', 'timing'):
            self.assertIn(key, snap)


        self.assertEqual(len(snap), 30)
        self.assertEqual((snap['pass_order'], snap['evaluation'], snap['step_progress'], snap['earlier_pass']),
                         ([], None, None, None))


class FullSizePicture(unittest.TestCase):
    def test_a_tile_lands_at_full_size_where_the_canvas_has_it_small(self):
        src = Image.fromarray(smooth(2048, 2048))
        c = canvas(src=src)
        self.assertEqual((c.full.w, c.full.h, c.full.scale), (4096, 4096, 1.0))
        self.assertEqual(c.full_bytes, 4096 * 4096 * 3 + 2048 * 2048 * 4)
        self.assertIsNone(c.snapshot('/x')['region_url'])
        self.assertIsNone(c.region(0, 0, 64, 64))
        init(c)
        snap = c.snapshot('/api/jobs/j1/items/i001')
        self.assertEqual(snap['region_url'], f'/api/jobs/j1/items/i001/live-region.jpg?seq={snap["image_seq"]}')
        self.assertEqual(snap['region_scale'], 1.0)

        a, box, scale, seq = region(c, 1000, 1000, 512, 512)
        want = np.asarray(src.resize((4096, 4096), Image.BICUBIC)).astype(np.float64)[1000:1512, 1000:1512]
        self.assertEqual((a.shape, box, scale), ((512, 512, 3), (1000, 1000, 512, 512), 1.0))
        self.assertLess(np.abs(a - want).mean(), 1.5)

        yy, xx = np.mgrid[0:1024, 0:1024]
        fine = (((xx // 2 + yy // 2) % 2) * 255).astype(np.uint8)
        t = Image.fromarray(np.stack([fine] * 3, -1))
        tile(c, (128, 256, 128, 128), png_of(t))
        a, box, scale, seq2 = region(c, 512, 1024, 512, 512)
        self.assertGreater(seq2, seq)
        expected = (((np.mgrid[0:512, 0:512][1] + np.mgrid[0:512, 0:512][0]) % 2) * 255).astype(np.float64)
        self.assertLess(np.abs(a[..., 0] - expected).mean(), 12.0)

        small = np.asarray(c.img)[512:768, 256:512, 0].astype(np.float64)
        self.assertLess(small.std(), 5.0)
        self.assertGreater(a[..., 0].std(), 100.0)

        b, *_ = region(c, 1100, 0, 256, 256)
        self.assertLess(np.abs(b - want_part(src, 1100, 0, 256, 256)).mean(), 1.5)

    def test_early_tiles_take_the_same_weight_as_on_the_canvas(self):
        c = canvas(src=Image.new('RGB', (2048, 2048), (100, 100, 100)))
        init(c)
        for step in (1, 3, 7, 11, 13, 14, 29):
            tile(c, (0, 0, 128, 128), (255, 255, 255), step=step)
            w = live.mix_weight(step, 30)
            a, *_ = region(c, 0, 0, 256, 256)
            self.assertAlmostEqual(a.mean(), 100 + 155 * w, delta=1.5, msg=str(step))
            self.assertAlmostEqual(float(np.asarray(c.img)[64, 64, 0]), 100 + 155 * w, delta=1.5)
        self.assertEqual(live.mix_weight(14, 30), 1.0)

    def test_a_window_that_reaches_into_the_padding(self):

        src = Image.new('RGB', (1500, 900), GREY)
        c = live.LiveCanvas('j1', 'i001', 'm1', 0, 1, (3000, 1800), 2.0, (3000, 1800), {'structure': '19', 'detail': '15'},
                            'detailed', [0], source=src, full_scale=2.0)
        init(c, latent=(752, 452))
        tile(c, (624, 324, 128, 128), (255, 255, 255), latent=(752, 452))
        a, box, *_ = region(c, 2900, 1700, 200, 200)
        self.assertEqual(box, (2900, 1700, 100, 100))
        self.assertGreater(a.mean(), 250)
        a, *_ = region(c, 2300, 1100, 100, 100)
        self.assertLess(np.abs(a - np.array(GREY)).mean(), 1.5)

    def test_a_pass_starts_again_from_the_stage_picture(self):
        c = canvas()
        init(c)
        tile(c, (0, 0, 128, 128), (255, 0, 0))
        self.assertGreater(region(c, 0, 0, 128, 128)[0][..., 0].mean(), 250)
        init(c, pass_no=2)
        a, *_ = region(c, 0, 0, 128, 128)
        self.assertLess(np.abs(a - np.array(GREY)).mean(), 1.5)
        self.assertEqual(c.pass_name, 'detail')

    def test_regions_of_an_earlier_stage_are_its_own_pixels_at_half_size(self):
        src = Image.fromarray(smooth(1024, 1024))
        c = live.LiveCanvas('j1', 'i001', 'm1', 0, 2, (2048, 2048), 2.0, (4096, 4096), {'structure': '19', 'detail': '15'},
                            'detailed', [0], source=src, full_scale=2.0)
        self.assertIsNone(c.full)
        self.assertEqual(c.full_note, 'small')
        big = Image.fromarray(smooth(2048, 2048))
        c = live.LiveCanvas('j1', 'i001', 'm1', 0, 2, (4096, 4096), 2.0, (8192, 8192), {'structure': '19', 'detail': '15'},
                            'detailed', [0], source=big, full_scale=2.0)
        self.assertEqual((c.full.w, c.full.scale), (4096, 0.5))
        init(c)
        self.assertEqual(c.snapshot('/x')['region_scale'], 0.5)
        a, box, scale, _ = region(c, 2000, 2000, 1024, 512)
        self.assertEqual((a.shape, box, scale), ((256, 512, 3), (2000, 2000, 1024, 512), 0.5))
        want = np.asarray(big.resize((4096, 4096), Image.BICUBIC)).astype(np.float64)[1000:1256, 1000:1512]
        self.assertLess(np.abs(a - want).mean(), 1.5)
        a, box, *_ = region(c, 2001, 2001, 301, 301)
        self.assertEqual((box, a.shape[:2]), ((2001, 2001, 301, 301), (150, 150)))

    def test_tiles_smaller_than_the_output_give_a_smaller_picture(self):
        c = live.LiveCanvas('j1', 'i001', 'm1', 1, 2, (6000, 4000), 1.0, (6000, 4000), {'structure': '19', 'detail': '15'},
                            'detailed', [0], source=Image.new('RGB', (3000, 2000), GREY), full_scale=0.5333)
        self.assertEqual((c.full.w, c.full.h), (3200, 2133))
        self.assertAlmostEqual(c.full.scale, 0.5333, places=4)
        init(c, latent=(750, 500))
        tile(c, (0, 0, 128, 128), (255, 255, 255), px=(546, 546), latent=(750, 500))
        a, box, scale, _ = region(c, 0, 0, 1024, 1024)
        self.assertEqual(a.shape[:2], (546, 546))
        self.assertGreater(a[8:-8, 8:-8].mean(), 250)

    def test_refused_rectangles(self):
        c = canvas()
        init(c)
        for x, y, w, h in ((0, 0, 0, 10), (0, 0, 10, -1), (0, 0, live.REGION_MAX_SIDE + 1, 10), (5000, 0, 10, 10),
                           (-50, -50, 40, 40)):
            with self.assertRaises(ValueError):
                c.region(x, y, w, h)
        a, box, *_ = region(c, -10, 4000, 200, 200)
        self.assertEqual(box, (0, 4000, 190, 96))


def want_part(src, x, y, w, h, size=(4096, 4096)):
    return np.asarray(src.resize(size, Image.BICUBIC)).astype(np.float64)[y:y + h, x:x + w]


class WhenThereIsNone(unittest.TestCase):
    def test_rough_has_no_full_size_pixels(self):
        c = canvas(mode='rough')
        self.assertIsNone(c.full)
        self.assertEqual(c.full_note, 'rough')
        init(c, source='l2r', image=True, data=png((512, 512), (10, 20, 30)))
        self.assertEqual(c.preview, 'rough')
        self.assertIsNone(c.snapshot('/x')['region_url'])
        self.assertTrue(c.large_tiles)

    def test_fallback_frames_end_it(self):
        c = canvas()
        init(c)
        tile(c, (0, 0, 128, 128), (255, 0, 0))
        self.assertIsNotNone(c.snapshot('/x')['region_url'])
        tile(c, (128, 0, 128, 128), (200, 40, 220), px=(128, 128), source='l2r', fallback='taesd_unavailable')
        self.assertEqual((c.preview, c.fallback), ('rough', True))
        self.assertIsNone(c.full)
        self.assertIsNone(c.src_img)
        self.assertEqual(c.full_bytes, 0)
        self.assertIsNone(c.snapshot('/x')['region_url'])
        self.assertIsNone(c.region(0, 0, 64, 64))
        self.assertEqual(c.full_note, 'rough')

    def test_a_decoder_that_failed_before_the_pass(self):
        c = canvas()
        init(c, source='l2r', image=True, data=png((1024, 1024), (10, 20, 30)))
        self.assertIsNone(c.full)
        self.assertEqual(c.preview, 'rough')

    def test_transparency_and_small_pictures(self):
        c = canvas(alpha=True)
        self.assertEqual((c.full, c.full_note), (None, 'transparency'))
        c = canvas(out=(2400, 1600), src=Image.new('RGB', (1200, 800), GREY))
        self.assertEqual((c.full, c.full_note), (None, 'small'))
        c = canvas(out=(2600, 1600), src=Image.new('RGB', (1300, 800), GREY))
        self.assertEqual((c.full.w, c.full.h), (2600, 1600))


class Budget(unittest.TestCase):
    KW = dict(media_id='m1', stage=0, stages=1, out_size=(4096, 4096), supersample=2.0, frame=(4096, 4096),
              samplers={'structure': '19', 'detail': '15'}, mode='detailed', cards=[0])
    ONE = 4096 * 4096 * 3 + 2048 * 2048 * 4

    def begin(self, board, iid, **kw):
        c = board.begin('j1', iid, source=Image.new('RGB', (2048, 2048), GREY), full_scale=2.0, **dict(self.KW, **kw))
        return c

    def run_one(self, c):
        init(c)
        tile(c, (0, 0, 128, 128), (255, 0, 0))

    def test_what_is_counted(self):
        board = live.LiveBoard()
        self.assertEqual(board.full_budget, 1280 << 20)
        self.assertEqual(live.FULL_BUDGET_MB, 1280)

        largest = 15360 * 9600 * 3 + 7680 * 4800 * 4
        self.assertLessEqual(2 * largest, board.full_budget)
        self.assertEqual(round(largest / 2 ** 20), 562)
        self.assertEqual(round((7680 * 4800 * 3 + 3840 * 2400 * 4) / 2 ** 20), 141)
        a = self.begin(board, 'i001')
        self.assertEqual((a.full_bytes, board.full_bytes()), (self.ONE, self.ONE))
        board.drop('j1', 'i001')
        self.assertEqual(board.full_bytes(), 0)

    def test_an_image_that_does_not_fit_runs_without_one(self):
        board = live.LiveBoard(full_budget_mb=self.ONE * 2.5 / 2 ** 20)
        a, b = self.begin(board, 'i001'), self.begin(board, 'i002')
        c = self.begin(board, 'i003')
        self.assertIsNotNone(a.full)
        self.assertIsNotNone(b.full)
        self.assertEqual((c.full, c.src_img, c.full_note), (None, None, 'memory'))
        self.assertEqual(board.full_bytes(), 2 * self.ONE)
        self.run_one(c)
        self.assertIsNone(c.snapshot('/x')['region_url'])
        self.assertIsNotNone(c.snapshot('/x')['canvas_url'])
        board.drop('j1', 'i001')
        d = self.begin(board, 'i004')
        self.assertIsNotNone(d.full)

    def test_stopped_images_give_theirs_up_first(self):
        board = live.LiveBoard(full_budget_mb=self.ONE * 2.5 / 2 ** 20)
        a = self.begin(board, 'i001')
        self.run_one(a)
        board.freeze('j1', 'i001', 'stopped')
        f = board.get('j1', 'i001')
        self.assertIsInstance(f, live.Frozen)
        self.assertEqual(f.full_bytes, 4096 * 4096 * 3)
        snap = f.snapshot('/api/jobs/j1/items/i001')
        self.assertIsNotNone(snap['region_url'])
        self.assertEqual(snap['state'], 'stopped')
        got = f.region(0, 0, 256, 256)
        self.assertGreater(pixels(got[0])[..., 0].mean(), 250)
        b = self.begin(board, 'i002')
        self.assertIsNotNone(f.full)
        c = self.begin(board, 'i003')
        self.assertIsNone(f.full)
        self.assertIsNotNone(c.full)
        self.assertIsNotNone(b.full)
        self.assertIsNone(f.snapshot('/x')['region_url'])
        self.assertIsNone(board.region('j1', 'i001', 0, 0, 64, 64))
        self.assertIsNotNone(f.jpeg())

    def test_only_the_newest_stopped_image_keeps_one(self):
        board = live.LiveBoard()
        for iid in ('i001', 'i002', 'i003'):
            c = self.begin(board, iid)
            self.run_one(c)
            board.freeze('j1', iid, 'failed' if iid == 'i002' else 'stopped')
        self.assertEqual([board.get('j1', i).full is not None for i in ('i001', 'i002', 'i003')], [False, False, True])
        self.assertEqual(board.full_bytes(), 4096 * 4096 * 3)
        items = {it['item_id']: it for it in board.summary()['items']}
        self.assertEqual([items[i]['region_url'] is not None for i in ('i001', 'i002', 'i003')], [False, False, True])
        again = self.begin(board, 'i003')
        self.assertEqual(board.full_bytes(), again.full_bytes)

    def test_a_stopped_image_gives_it_up_when_nobody_looks(self):
        board = live.LiveBoard()
        board.frozen_full_idle_s = 0.4
        c = self.begin(board, 'i001')
        self.run_one(c)
        board.freeze('j1', 'i001', 'stopped')
        f = board.get('j1', 'i001')
        seq = board.summary()['seq']
        time.sleep(0.25)
        self.assertIsNotNone(board.region('j1', 'i001', 0, 0, 64, 64))
        time.sleep(0.25)
        self.assertIsNotNone(f.full)
        deadline = time.monotonic() + 5
        while f.full is not None and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertIsNone(f.full)
        self.assertGreater(board.summary()['seq'], seq)
        self.assertIsNone(board.summary()['items'][0]['region_url'])

    def test_an_image_stopped_before_its_first_frame_keeps_nothing(self):
        board = live.LiveBoard()
        self.begin(board, 'i001')
        board.freeze('j1', 'i001', 'stopped')
        self.assertEqual(board.full_bytes(), 0)

    def test_a_later_stage_takes_over(self):
        board = live.LiveBoard()
        first = self.begin(board, 'i001', stages=2, frame=(8192, 8192))
        self.run_one(first)
        self.assertEqual(first.snapshot('/x')['region_scale'], 0.5)
        second = board.begin('j1', 'i001', source=Image.new('RGB', (4096, 4096), (9, 99, 199)), full_scale=2.0,
                             **dict(self.KW, stage=1, stages=2, out_size=(8192, 8192), frame=(8192, 8192)))
        self.assertIsNone(first.full)
        self.assertEqual(board.full_bytes(), second.full_bytes)
        snap = second.snapshot('/x')
        self.assertEqual(snap['region_scale'], 1.0)
        a, *_ = region(second, 4000, 4000, 256, 256)
        self.assertLess(np.abs(a - np.array((9, 99, 199))).mean(), 1.5)


class RegionsThroughTheService(V4Base):

    def big_input(self):
        d = self.d / 'in'
        d.mkdir(parents=True, exist_ok=True)
        self.src = smooth(1400, 900)
        yy, xx = np.mgrid[0:200, 0:200]
        self.src[300:500, 600:800] = (((xx + yy) % 2) * 255).astype(np.uint8)[..., None]
        Image.fromarray(self.src).save(d / 'room.png')
        return [it['id'] for it in self.add(self.svc, [d / 'room.png'])['items']]

    def sampling(self, jid, extra=lambda x: True):
        return wait(lambda: next((x for x in self.live()['items'] if x['job_id'] == jid and x['state'] == 'sampling'
                                  and x['canvas_url'] and extra(x)), None), timeout=60)

    def test_on_a_region_is_served_from_full_size_pixels_and_a_stopped_image_keeps_it(self):

        self.svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '6'})
        code, health, _ = self.svc.get('/health')
        self.assertIs(health['features']['live_regions'], True)
        mids = self.big_input()
        job = self.job(self.svc, mids, {'scale': 2})
        jid = job['id']
        snap = self.sampling(jid, lambda x: x['region_url'] and x['step'] >= 2)
        self.assertEqual(snap['preview'], 'detailed')
        ready = next(ln for ln in self.svc.log_lines() if ln.get('event') == 'worker_ready')
        self.assertEqual(ready['data']['live_max_side'], 8192)
        self.assertEqual((snap['frame'], snap['canvas_size'], snap['region_scale']), ([2800, 1800], [2048, 1317], 1.0))
        self.assertEqual(snap['region_url'], f'/api/jobs/{jid}/items/i001/live-region.jpg?seq={snap["image_seq"]}')

        code, jpg, hdr = self.svc.get(snap['region_url'] + '&x=1000&y=600&w=800&h=600', raw=True)
        self.assertEqual((code, hdr['Content-Type'], hdr['Cache-Control']), (200, 'image/jpeg', 'no-store'))
        self.assertEqual((hdr['X-Region'], hdr['X-Region-Scale']), ('1000,600,800,600', '1.0000'))
        im = Image.open(io.BytesIO(jpg))
        self.assertEqual(im.size, (800, 600))

        want = np.asarray(Image.fromarray(self.src).resize((2800, 1800), Image.BICUBIC)).astype(np.float64)[600:1200, 1000:1800]
        got = pixels(jpg)
        self.assertLess(np.abs(got - want)[:, 620:].mean(), 4.0)

        code, cv, _ = self.svc.get(snap['canvas_url'], raw=True)
        k = 2048 / 2800.0
        enlarged = Image.open(io.BytesIO(cv)).convert('RGB').crop((int(1220 * k), int(620 * k), int(1580 * k), int(980 * k)))
        enlarged = np.asarray(enlarged.resize((360, 360), Image.BILINEAR)).astype(np.float64)
        weave, soft = got[20:380, 220:580, 0].std(), enlarged[..., 0].std()
        self.assertGreater(weave, 40.0)
        self.assertGreater(weave, 2 * soft)
        code, edge, hdr = self.svc.get(snap['region_url'] + '&x=2700&y=1700&w=400&h=400', raw=True)
        self.assertEqual((code, hdr['X-Region'], Image.open(io.BytesIO(edge)).size), (200, '2700,1700,100,100', (100, 100)))
        for query, want_code in (('x=0&y=0&w=10', 'bad_request'), ('x=0&y=0&w=5000&h=10', 'bad_region'),
                                 ('x=9000&y=0&w=10&h=10', 'bad_region')):
            code, err, _ = self.svc.get(snap['region_url'] + '&' + query)
            self.assertEqual((code, err['error']['code']), (400, want_code), query)

        code, res, _ = self.svc.post(f'/api/cancel?image={mids[0]}')
        self.assertEqual(code, 200, res)
        wait(lambda: self.item(jid, 'i001')['state'] == 'stopped')
        frozen = wait(lambda: next((x for x in self.live()['items'] if x['job_id'] == jid and x['state'] == 'stopped'), None))
        self.assertIsNotNone(frozen['region_url'])
        code, last, hdr = self.svc.get(frozen['region_url'] + '&x=1000&y=600&w=800&h=600', raw=True)
        self.assertEqual((code, Image.open(io.BytesIO(last)).size), (200, (800, 600)))
        last_px = pixels(last)
        self.assertLess(np.abs(last_px - want)[:, 620:].mean(), 4.0)


        code, cv_last, _ = self.svc.get(frozen['canvas_url'], raw=True)
        self.assertEqual(code, 200)
        soft_last = Image.open(io.BytesIO(cv_last)).convert('RGB').crop((int(1220 * k), int(620 * k), int(1580 * k),
                                                                        int(980 * k)))
        soft_last = np.asarray(soft_last.resize((360, 360), Image.BILINEAR)).astype(np.float64)[..., 0].std()
        weave_last = last_px[20:380, 220:580, 0].std()
        self.assertGreater(weave_last, 2 * soft_last, (weave_last, soft_last))

        code, j, _ = self.svc.post(f'/api/jobs/{jid}/items/i001/requeue', {})
        self.assertEqual(code, 200, j)
        self.svc.post('/api/settings', {})
        j = self.svc.wait_job(jid, all_done, timeout=120)
        self.assertEqual(j['items'][0]['state'], 'done')
        code, err, _ = self.svc.get(f'/api/jobs/{jid}/items/i001/live-region.jpg?x=0&y=0&w=10&h=10')
        self.assertEqual((code, err['error']['code']), (404, 'no_live'))
        self.assertEqual(self.svc.shutdown(), 0)

    def test_off_nothing_is_offered_and_the_tiles_are_canvas_size(self):

        self.svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '3', 'CU_LIVE_REGIONS': '0'})
        code, health, _ = self.svc.get('/health')
        self.assertIs(health['features']['live_regions'], False)
        mids = self.big_input()
        jid = self.job(self.svc, mids, {'scale': 2})['id']
        snap = self.sampling(jid, lambda x: x['step'] >= 2)
        self.assertEqual(snap['preview'], 'detailed')
        ready = next(ln for ln in self.svc.log_lines() if ln.get('event') == 'worker_ready')
        self.assertEqual(ready['data']['live_max_side'], 2048)
        self.assertIsNone(snap['region_url'])
        self.assertIsNone(snap['region_scale'])
        code, err, _ = self.svc.get(f'/api/jobs/{jid}/items/i001/live-region.jpg?x=0&y=0&w=10&h=10')
        self.assertEqual((code, err['error']['code']), (404, 'no_live_region'))
        code, jpg, _ = self.svc.get(snap['canvas_url'], raw=True)
        self.assertEqual(Image.open(io.BytesIO(jpg)).size, (2048, 1317))
        self.svc.wait_job(jid, all_done, timeout=120)
        self.assertEqual(self.svc.shutdown(), 0)

    def test_rough_preview_offers_none_even_when_on(self):
        self.svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '3', 'CU_LIVE_REGIONS': '1'})
        code, s, _ = self.svc.post('/api/settings', {'detailed_preview': False})
        self.assertEqual(code, 200)
        mids = self.big_input()
        jid = self.job(self.svc, mids, {'scale': 2})['id']
        snap = self.sampling(jid)
        self.assertEqual(snap['preview'], 'rough')
        self.assertIsNone(snap['region_url'])
        self.svc.wait_job(jid, all_done, timeout=120)
        self.assertEqual(self.svc.shutdown(), 0)


if __name__ == '__main__':
    unittest.main()
