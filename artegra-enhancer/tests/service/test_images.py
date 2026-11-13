"""Synthetic image IO, transparency, metadata, output integrity and no-overwrite tests."""
import io
import json
import struct
import unittest
import zlib
from pathlib import Path

import numpy as np
from PIL import Image, ImageCms
from PIL.JpegImagePlugin import get_sampling

from service import images
from tests.service.helpers import gradient, read_png16, read_tiff16, rmtree, tmpdir


class Inputs(unittest.TestCase):
    def setUp(self):
        self.d = tmpdir()

    def tearDown(self):
        rmtree(self.d)

    def norm(self, src, name='out'):
        return images.normalise(src, self.d / name)

    def test_formats_accepted(self):
        a = gradient(96, 80)
        for fmt, ext, kw in (('PNG', 'png', {}), ('JPEG', 'jpg', {'quality': 95}), ('TIFF', 'tif', {}),
                             ('WEBP', 'webp', {'quality': 90}), ('BMP', 'bmp', {})):
            p = self.d / f'in.{ext}'
            Image.fromarray(a).save(p, fmt, **kw)
            rec = self.norm(p, f'o_{ext}')
            self.assertEqual((rec['width'], rec['height']), (96, 80), fmt)
            self.assertFalse(rec['alpha'], fmt)
            for f in ('source.png', 'thumb.jpg', 'proxy.jpg'):
                self.assertTrue((self.d / f'o_{ext}' / f).is_file(), (fmt, f))
            with Image.open(self.d / f'o_{ext}' / 'source.png') as im:
                self.assertEqual((im.mode, im.size), ('RGB', (96, 80)))

    def test_unsupported_unreadable_animated_refused(self):
        p = self.d / 'a.gif'
        Image.fromarray(gradient(80, 80)).save(p, 'GIF')
        with self.assertRaises(images.InputRejected) as cm:
            self.norm(p)
        self.assertIn('not supported', cm.exception.reason)
        t = self.d / 'notes.png'
        t.write_text('hello', encoding='utf8')
        with self.assertRaises(images.InputRejected) as cm:
            self.norm(t)
        self.assertIn('Not an image file', cm.exception.reason)
        frames = [Image.fromarray(gradient(80, 80, seed=i)) for i in range(3)]
        w = self.d / 'anim.webp'
        frames[0].save(w, 'WEBP', save_all=True, append_images=frames[1:], duration=100)
        with self.assertRaises(images.InputRejected) as cm:
            self.norm(w)
        self.assertIn('Animated', cm.exception.reason)
        mt = self.d / 'pages.tif'
        frames[0].save(mt, 'TIFF', save_all=True, append_images=frames[1:])
        with self.assertRaises(images.InputRejected):
            self.norm(mt)
        with self.assertRaises(images.InputRejected) as cm:
            self.norm(self.d / 'missing.png')
        self.assertIn('not found', cm.exception.reason)

    def test_damaged_file_refused(self):
        p = self.d / 'cut.png'
        Image.fromarray(gradient(200, 200)).save(p, 'PNG')
        data = p.read_bytes()
        p.write_bytes(data[:len(data) // 2])
        with self.assertRaises(images.InputRejected) as cm:
            self.norm(p)
        self.assertIn('damaged', cm.exception.reason)

    def test_size_limits(self):
        small = self.d / 'small.png'
        Image.fromarray(gradient(63, 200)).save(small)
        with self.assertRaises(images.InputRejected) as cm:
            self.norm(small)
        self.assertIn('Too small', cm.exception.reason)
        # A PNG header that claims 9000 x 9000 (81 MP): refused from the header, nothing is decoded.
        chunk = lambda t, d: struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xFFFFFFFF)
        big = self.d / 'big.png'
        big.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 9000, 9000, 8, 2, 0, 0, 0))
                        + chunk(b'IDAT', zlib.compress(b'\x00' * 10)) + chunk(b'IEND', b''))
        with self.assertRaises(images.InputRejected) as cm:
            self.norm(big)
        self.assertIn('very large', cm.exception.reason)

    def test_exif_orientation_applied_and_removed(self):
        a = gradient(120, 80)
        ex = Image.Exif()
        ex[0x0112] = 6
        ex[271] = 'TestMake'
        ex[272] = 'TestModel'
        ex[0x8769] = {0x9003: '2026:11:05 10:00:00', 0xA002: 120, 0xA003: 80}
        p = self.d / 'rot.jpg'
        Image.fromarray(a).save(p, 'JPEG', quality=95, exif=ex.tobytes())
        rec = self.norm(p)
        self.assertEqual((rec['width'], rec['height']), (80, 120))   # rotated upright
        self.assertEqual(rec['orientation'], 6)
        self.assertTrue(rec['exif'])
        e2 = Image.Exif()
        e2.load((self.d / 'out' / 'exif.bin').read_bytes())
        self.assertNotIn(0x0112, e2)
        self.assertEqual(e2[271], 'TestMake')
        sub = e2.get_ifd(0x8769)
        self.assertEqual(sub[0x9003], '2026:11:05 10:00:00')
        self.assertNotIn(0xA002, sub)                                  # stale pixel size dropped

    def test_icc_converted_and_bad_icc_reported(self):
        a = gradient(90, 70)
        srgb = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
        p = self.d / 'icc.png'
        Image.fromarray(a).save(p, icc_profile=srgb)
        rec = self.norm(p, 'icc')
        self.assertEqual(rec['icc'], 'converted')
        with Image.open(self.d / 'icc' / 'source.png') as im:
            got = np.asarray(im, np.int32)
        self.assertLessEqual(np.abs(got - a).max(), 2)                 # sRGB -> sRGB is (near) identity
        q = self.d / 'bad.png'
        Image.fromarray(a).save(q, icc_profile=b'not a profile at all' * 10)
        rec = self.norm(q, 'bad')
        self.assertEqual(rec['icc'], 'failed')
        self.assertTrue(any('colour profile' in n for n in rec['notes']))
        with Image.open(self.d / 'bad' / 'source.png') as im:
            self.assertTrue(np.array_equal(np.asarray(im), a))

    def test_cmyk_grey_palette_converted(self):
        a = gradient(80, 80)
        Image.fromarray(a).convert('CMYK').save(self.d / 'c.jpg', 'JPEG', quality=95)
        Image.fromarray(a).convert('L').save(self.d / 'g.png')
        Image.fromarray(a).convert('P', palette=Image.ADAPTIVE).save(self.d / 'p.png')
        for n in ('c.jpg', 'g.png', 'p.png'):
            rec = self.norm(self.d / n, n + '_o')
            with Image.open(self.d / (n + '_o') / 'source.png') as im:
                self.assertEqual(im.mode, 'RGB', n)
            self.assertFalse(rec['alpha'])

    def test_alpha_kept_and_opaque_alpha_dropped(self):
        a = gradient(101, 67)
        alpha = np.tile(np.linspace(0, 255, 101).astype(np.uint8), (67, 1))
        Image.fromarray(np.dstack([a, alpha])).save(self.d / 'rgba.png')
        rec = self.norm(self.d / 'rgba.png', 'rgba')
        self.assertTrue(rec['alpha'])
        with Image.open(self.d / 'rgba' / 'alpha.png') as am, Image.open(self.d / 'rgba' / 'source.png') as sm:
            self.assertTrue(np.array_equal(np.asarray(am), alpha))
            self.assertTrue(np.array_equal(np.asarray(sm), a))
        Image.fromarray(np.dstack([a, np.full((67, 101), 255, np.uint8)])).save(self.d / 'opaque.png')
        rec = self.norm(self.d / 'opaque.png', 'opaque')
        self.assertFalse(rec['alpha'])
        self.assertFalse((self.d / 'opaque' / 'alpha.png').exists())
        la = np.dstack([a[..., 0], alpha])
        Image.fromarray(la, 'LA').save(self.d / 'la.png')
        self.assertTrue(self.norm(self.d / 'la.png', 'la')['alpha'])

    def test_16bit_grey_and_rgb(self):
        g = (np.linspace(0, 65535, 100 * 80).reshape(80, 100)).astype(np.uint16)
        Image.fromarray(g).save(self.d / 'g16.png')
        rec = self.norm(self.d / 'g16.png', 'g16')
        self.assertEqual(rec['bit_depth'], 16)
        with Image.open(self.d / 'g16' / 'source.png') as im:
            got = np.asarray(im)[..., 0].astype(np.int32)
        self.assertLessEqual(np.abs(got - np.round(g / 257.0)).max(), 1)   # scaled, not clipped
        rgb16 = (gradient(90, 70).astype(np.uint16) * 257)
        images.write_tiff16(self.d / 'rgb16.tif', rgb16)
        rec = self.norm(self.d / 'rgb16.tif', 'rgb16')
        self.assertEqual(rec['bit_depth'], 16)
        with Image.open(self.d / 'rgb16' / 'source.png') as im:
            got = np.asarray(im, np.int32)
        self.assertLessEqual(np.abs(got - gradient(90, 70)).max(), 1)

    def test_thumb_and_proxy_sizes(self):
        Image.fromarray(gradient(3000, 1000)).save(self.d / 'wide.png')
        self.norm(self.d / 'wide.png', 'wide')
        with Image.open(self.d / 'wide' / 'thumb.jpg') as t, Image.open(self.d / 'wide' / 'proxy.jpg') as p:
            self.assertEqual((t.size, p.size), ((320, 107), (2048, 683)))


def jpeg_bytes(im, **kw):
    buf = io.BytesIO()
    im.save(buf, 'JPEG', **kw)
    return buf.getvalue()


def v2_preview(rgb_im, alpha_im, side, quality):
    """The display JPEG as v2 made it (flattened onto the matte when there is alpha), written independently of write_preview."""
    im = rgb_im.copy()
    if alpha_im is not None:
        im = Image.new('RGB', rgb_im.size, (38, 38, 38))
        im.paste(rgb_im, (0, 0), alpha_im)
    im.thumbnail((side, side), Image.LANCZOS)
    return jpeg_bytes(im, quality=quality)


def band_rgba(w, h, band, fade=24, seed=4):
    """A test picture whose top `band` rows are fully transparent, fading in over `fade` rows (like the harness fixture)."""
    a = np.full((h, w), 255, np.uint8)
    a[:band] = 0
    a[band:band + fade] = np.linspace(0, 255, fade).astype(np.uint8)[:, None]
    return gradient(w, h, seed), a


class _Log:
    def __getattr__(self, name):
        return lambda *a, **kw: None


class DisplayCopies(unittest.TestCase):
    """L23: images and results with alpha get display copies that keep it; everything else is byte-for-byte as in v2."""

    def setUp(self):
        self.d = tmpdir()

    def tearDown(self):
        rmtree(self.d)

    def test_preview_size_is_pillows_thumbnail_size(self):
        for w, h in ((3000, 1000), (101, 67), (2049, 2047), (5000, 3333), (1999, 4001), (4096, 2731), (321, 320), (640, 960),
                     (2048, 2048), (2048, 64), (64, 2049), (15000, 10000), (7, 4999)):
            for side in (images.THUMB_SIDE, images.PROXY_SIDE):
                im = Image.new('L', (w, h))
                im.thumbnail((side, side), Image.LANCZOS)
                self.assertEqual(images.preview_size(w, h, side), im.size, (w, h, side))

    def test_opaque_input_writes_exactly_the_v2_files_and_bytes(self):
        a = gradient(2300, 1400, 1)
        Image.fromarray(a).save(self.d / 'opaque.png')
        images.normalise(self.d / 'opaque.png', self.d / 'o')
        self.assertEqual(sorted(p.name for p in (self.d / 'o').iterdir()), ['proxy.jpg', 'source.png', 'thumb.jpg'])
        src = Image.fromarray(a)
        self.assertEqual((self.d / 'o' / 'thumb.jpg').read_bytes(), v2_preview(src, None, 320, 85))
        self.assertEqual((self.d / 'o' / 'proxy.jpg').read_bytes(), v2_preview(src, None, 2048, 90))

    def test_alpha_input_keeps_the_v2_jpegs_and_adds_rgba_pngs(self):
        rgb, a = band_rgba(2600, 1500, 300)
        Image.fromarray(np.dstack([rgb, a])).save(self.d / 'band.png')
        rec = images.normalise(self.d / 'band.png', self.d / 'b')
        self.assertTrue(rec['alpha'])
        self.assertEqual(sorted(p.name for p in (self.d / 'b').iterdir()),
                         ['alpha.png', 'proxy.jpg', 'proxy.png', 'source.png', 'thumb.jpg', 'thumb.png'])
        src, am = Image.fromarray(rgb), Image.fromarray(a)
        # the flattened JPEGs are exactly v2's (the runner still reads proxy.jpg; records made before v3 have only these)
        self.assertEqual((self.d / 'b' / 'thumb.jpg').read_bytes(), v2_preview(src, am, 320, 85))
        self.assertEqual((self.d / 'b' / 'proxy.jpg').read_bytes(), v2_preview(src, am, 2048, 90))
        for name, side in (('thumb', 320), ('proxy', 2048)):
            with Image.open(self.d / 'b' / f'{name}.png') as p, Image.open(self.d / 'b' / f'{name}.jpg') as j:
                self.assertEqual((p.format, p.mode), ('PNG', 'RGBA'), name)
                self.assertEqual(p.size, j.size, name)                                # the same size as the .jpg copy
                arr = np.asarray(p)
            k = p.size[1] / 1500                                                        # preview rows per source row
            self.assertEqual(arr[:int(300 * k) - 4, :, 3].max(), 0, name)               # the band is fully transparent
            self.assertEqual(arr[int(330 * k) + 4:, :, 3].min(), 255, name)             # below the fade it is opaque
            ref = np.asarray(src.resize(p.size, Image.LANCZOS), np.int32)
            body = slice(int(330 * k) + 6, None)
            self.assertLess(np.abs(arr[body, :, :3].astype(np.int32) - ref[body]).mean(), 2.0, name)   # true colour, no matte

    def test_premultiplied_resize_never_shows_the_hidden_colour_at_the_edge(self):
        rgb = np.zeros((400, 600, 3), np.uint8)
        rgb[:200] = (255, 0, 255)                                                       # hidden colour under alpha 0
        rgb[200:] = (40, 120, 200)
        a = np.zeros((400, 600), np.uint8)
        a[200:] = 255
        Image.fromarray(np.dstack([rgb, a])).save(self.d / 'edge.png')
        images.normalise(self.d / 'edge.png', self.d / 'e')
        with Image.open(self.d / 'e' / 'thumb.png') as t:
            arr = np.asarray(t).astype(np.int32)
        # Edge pixels (alpha 8 or more; below that 8-bit un-premultiplying rounds coarsely, unseen at that opacity) keep the
        # visible colour. A straight (not premultiplied) resize would pull them up to 211 levels towards the hidden magenta.
        edge = arr[(arr[..., 3] >= 8) & (arr[..., 3] < 255)]
        self.assertGreater(len(edge), 0)
        self.assertLessEqual(np.abs(edge[:, :3] - [40, 120, 200]).max(), 2)            # no magenta fringe

    def test_result_views_opaque_are_exactly_v2(self):
        from service.media import MediaLibrary, VIEW_FILES
        lib = MediaLibrary(self.d / 'media', _Log())
        rgb = gradient(2600, 1500, 2)
        before = rgb.copy()
        d = lib.write_result_views('j000000000001', 'i001', rgb, None)
        self.assertEqual(sorted(p.name for p in d.iterdir()), sorted(VIEW_FILES))
        im = Image.fromarray(rgb)
        self.assertEqual((d / 'view.jpg').read_bytes(), jpeg_bytes(im, quality=95, subsampling=0))
        self.assertEqual((d / 'proxy.jpg').read_bytes(), v2_preview(im, None, 2048, 90))
        self.assertEqual((d / 'thumb.jpg').read_bytes(), v2_preview(im, None, 320, 85))
        self.assertTrue(np.array_equal(rgb, before))
        self.assertTrue(lib.result_views_ready('j000000000001', 'i001'))
        self.assertEqual(lib.display_file(d, 'proxy'), (d / 'proxy.jpg', 'image/jpeg'))
        self.assertEqual(lib.result_layer(d), (d / 'view.jpg', None))

    def test_result_views_with_alpha_keep_it(self):
        from service.media import MediaLibrary, VIEW_FILES_ALPHA
        lib = MediaLibrary(self.d / 'media', _Log())
        rgb, a = band_rgba(2600, 1500, 300, fade=40)
        rgb_before, a_before = rgb.copy(), a.copy()
        d = lib.write_result_views('j000000000002', 'i001', rgb, a)
        self.assertEqual(sorted(p.name for p in d.iterdir()), sorted(VIEW_FILES_ALPHA))
        self.assertTrue(np.array_equal(rgb, rgb_before) and np.array_equal(a, a_before))   # shared buffer: inputs untouched
        with Image.open(d / 'view-alpha.png') as am:
            self.assertEqual(am.mode, 'L')
            self.assertTrue(np.array_equal(np.asarray(am), a))                              # the exact alpha, full size
        # view.jpg is the colour as rendered (not flattened onto the matte), and the RGBX encode equals an RGB encode
        self.assertEqual((d / 'view.jpg').read_bytes(), jpeg_bytes(Image.fromarray(rgb), quality=95, subsampling=0))
        for name, side in (('proxy', 2048), ('thumb', 320)):
            with Image.open(d / f'{name}.png') as p:
                self.assertEqual((p.mode, p.size), ('RGBA', images.preview_size(2600, 1500, side)), name)
                arr = np.asarray(p)
            k = p.size[1] / 1500
            self.assertEqual(arr[:int(300 * k) - 4, :, 3].max(), 0, name)
            self.assertEqual(arr[int(340 * k) + 4:, :, 3].min(), 255, name)
        self.assertTrue(lib.result_views_ready('j000000000002', 'i001'))
        self.assertEqual(lib.display_file(d, 'thumb'), (d / 'thumb.png', 'image/png'))
        self.assertEqual(lib.result_layer(d), (d / 'view.jpg', d / 'view-alpha.png'))
        (d / 'proxy.png').unlink()                                                          # incomplete: rebuilt on demand
        self.assertFalse(lib.result_views_ready('j000000000002', 'i001'))

    def test_records_made_before_v3_are_served_as_they_are(self):
        from service.media import MediaLibrary
        lib = MediaLibrary(self.d / 'media', _Log())
        old = lib.result_dir('j000000000003', 'i001')
        old.mkdir(parents=True)
        for n in ('view.jpg', 'proxy.jpg', 'thumb.jpg'):                                    # v2 layout, flattened JPEGs
            Image.new('RGB', (64, 64), (38, 38, 38)).save(old / n)
        self.assertTrue(lib.result_views_ready('j000000000003', 'i001'))
        self.assertEqual(lib.display_file(old, 'proxy'), (old / 'proxy.jpg', 'image/jpeg'))
        self.assertEqual(lib.display_file(old, 'thumb'), (old / 'thumb.jpg', 'image/jpeg'))
        self.assertEqual(lib.result_layer(old), (old / 'view.jpg', None))
        with self.assertRaises(ValueError):
            lib.display_file(old, 'view')

    def test_region_of_a_picture_with_alpha_is_rgba(self):
        rgb, a = band_rgba(300, 200, 40, fade=10)
        Image.fromarray(rgb).save(self.d / 'c.png')
        Image.fromarray(a).save(self.d / 'a.png')
        cache = images.DecodedCache(size=2)
        img = cache.get(self.d / 'c.png', self.d / 'a.png')
        self.assertEqual((img.mode, img.size), ('RGBA', (300, 200)))
        self.assertIs(cache.get(self.d / 'c.png', self.d / 'a.png'), img)
        plain = cache.get(self.d / 'c.png')                                              # without alpha: its own entry
        self.assertEqual((plain.mode, cache.decodes), ('RGB', 2))
        data, box = images.region_png(img, 0, 0, 50, 60)
        with Image.open(io.BytesIO(data)) as r:
            self.assertEqual((r.mode, r.size, box), ('RGBA', (50, 60), (0, 0, 50, 60)))
            arr = np.asarray(r)
        self.assertTrue(np.array_equal(arr[..., 3], a[:60, :50]))
        self.assertTrue(np.array_equal(arr[..., :3], rgb[:60, :50]))
        Image.fromarray(a[:100]).save(self.d / 'short.png')
        with self.assertRaises(ValueError):                                              # a mismatch is an error, never silent
            cache.get(self.d / 'c.png', self.d / 'short.png')


class StageHelpers(unittest.TestCase):
    def test_pad_reflect_and_crop_exact(self):
        a = gradient(101, 67)
        p = images.pad_reflect(a, (104, 72))
        self.assertEqual(p.shape, (72, 104, 3))
        self.assertTrue(np.array_equal(p[:67, :101], a))
        self.assertTrue(np.array_equal(p[:67, 101], a[:, 99]))         # reflect: edge pixel not repeated
        self.assertTrue(np.array_equal(images.crop(p, (101, 67)), a))
        self.assertIs(images.pad_reflect(a, (101, 67)), a)
        with self.assertRaises(ValueError):
            images.pad_reflect(a, (100, 67))
        with self.assertRaises(ValueError):
            images.crop(a, (102, 67))


class Outputs(unittest.TestCase):
    def setUp(self):
        self.d = tmpdir()
        self.rgb = gradient(73, 41)
        self.alpha = np.tile(np.linspace(0, 255, 73).astype(np.uint8), (41, 1))
        ex = Image.Exif()
        ex[271] = 'OutMake'
        ex[0x8769] = {0x9003: '2026:01:02 03:04:05'}
        self.exif = ex.tobytes()

    def tearDown(self):
        rmtree(self.d)

    def test_png8_with_alpha_icc_exif(self):
        info = images.encode(self.d / 'o.png', self.rgb, self.alpha, 'png8', self.exif)
        self.assertEqual((info['alpha'], info['exif'], info['icc']), ('kept', 'copied', 'sRGB'))
        with Image.open(self.d / 'o.png') as im:
            self.assertEqual(im.mode, 'RGBA')
            self.assertTrue(np.array_equal(np.asarray(im)[..., :3], self.rgb))
            self.assertTrue(np.array_equal(np.asarray(im)[..., 3], self.alpha))
            self.assertEqual(im.info.get('icc_profile'), images.srgb_icc_bytes())
            self.assertEqual(im.getexif()[271], 'OutMake')

    def test_png16_widened_exactly(self):
        info = images.encode(self.d / 'o16.png', self.rgb, self.alpha, 'png16', self.exif)
        self.assertEqual(info['bits'], 16)
        arr, depth, chunks = read_png16(self.d / 'o16.png')
        self.assertEqual(depth, 16)
        self.assertTrue(np.array_equal(arr[..., :3], self.rgb.astype(np.uint16) * 257))
        self.assertTrue(np.array_equal(arr[..., 3], self.alpha.astype(np.uint16) * 257))
        self.assertIn(b'iCCP', chunks)
        self.assertIn(b'eXIf', chunks)
        with Image.open(self.d / 'o16.png') as im:   # also readable by a standard decoder
            self.assertEqual(im.size, (73, 41))

    def test_tiff16_widened_exactly(self):
        info = images.encode(self.d / 'o.tif', self.rgb, None, 'tiff16', self.exif)
        self.assertEqual(info['exif'], 'copied')
        arr, tags = read_tiff16(self.d / 'o.tif')
        self.assertTrue(np.array_equal(arr, self.rgb.astype(np.uint16) * 257))
        self.assertEqual(tags[258], (16, 16, 16))
        self.assertEqual(tags[34675], images.srgb_icc_bytes())
        self.assertEqual(tags[271], b'OutMake\x00')
        with Image.open(self.d / 'o.tif') as im:
            im.load()
            self.assertEqual(im.size, (73, 41))
            self.assertEqual(im.getexif().get_ifd(0x8769).get(0x9003), '2026:01:02 03:04:05')
        images.encode(self.d / 'oa.tif', self.rgb, self.alpha, 'tiff16')
        arr, tags = read_tiff16(self.d / 'oa.tif')
        self.assertTrue(np.array_equal(arr[..., 3], self.alpha.astype(np.uint16) * 257))
        self.assertEqual(tags[338], (2,))

    def test_jpeg_444_and_alpha_reported(self):
        info = images.encode(self.d / 'o.jpg', self.rgb, self.alpha, 'jpeg', self.exif)
        self.assertTrue(info['alpha'].startswith('dropped'))
        with Image.open(self.d / 'o.jpg') as im:
            self.assertEqual(get_sampling(im), 0)                       # 4:4:4
            self.assertEqual(im.info.get('icc_profile'), images.srgb_icc_bytes())
            self.assertEqual(im.getexif()[271], 'OutMake')

    def test_naming_never_overwrites(self):
        sidecar = lambda p: json.dumps({'output': str(p)}).encode()
        outs = []
        for i in range(3):
            tmp = self.d / f'.t{i}.partial.png'
            tmp.write_bytes(b'x%d' % i)
            outs.append(images.reserve_and_publish(tmp, self.d, 'photo', 2, '.png', sidecar))
        self.assertEqual([o.name for o, _ in outs], ['photo_cu2x.png', 'photo_cu2x_2.png', 'photo_cu2x_3.png'])
        self.assertEqual([s.name for _, s in outs], ['photo_cu2x.json', 'photo_cu2x_2.json', 'photo_cu2x_3.json'])
        self.assertEqual((self.d / 'photo_cu2x.png').read_bytes(), b'x0')
        # a lone sidecar (or output) with the next name also blocks that name
        (self.d / 'photo_cu4x.json').write_text('{}')
        tmp = self.d / '.t.partial.png'
        tmp.write_bytes(b'y')
        o, s = images.reserve_and_publish(tmp, self.d, 'photo', 4, '.png', sidecar)
        self.assertEqual(o.name, 'photo_cu4x_2.png')
        self.assertEqual(json.loads(s.read_text())['output'], str(o))
        self.assertEqual(images.safe_stem('a:b?.png'), 'a_b_')

    def test_region_and_mask_preview(self):
        img = Image.fromarray(self.rgb)
        data, box = images.region_png(img, 70, 40, 10, 10)
        self.assertEqual(box, (70, 40, 3, 1))
        with Image.open(io.BytesIO(data)) as im:
            self.assertEqual(im.size, (3, 1))
        with self.assertRaises(ValueError):
            images.region_png(img, 100, 100, 5, 5)
        m = Image.new('L', (400, 300), 0)
        m.paste(255, (190, 140, 210, 160))
        out = images.mask_postprocess(m, dilate=12, feather=0)
        a = np.asarray(out)
        self.assertEqual(a[150, 200], 255)
        self.assertEqual(a[150, 221], 255)                              # dilated 12 px
        self.assertEqual(a[150, 223], 0)
        big = images.mask_postprocess(Image.new('L', (4096, 1024), 0), 12, 4)
        self.assertEqual(big.size, (2048, 512))                          # preview at proxy resolution

    def test_region_negative_origin_is_the_intersection(self):
        img = Image.fromarray(self.rgb)                                  # 73 x 41
        data, box = images.region_png(img, -10, -5, 20, 10)
        self.assertEqual(box, (0, 0, 10, 5))                             # not shifted to 0..19
        with Image.open(io.BytesIO(data)) as im:
            self.assertEqual(im.size, (10, 5))
            self.assertTrue(np.array_equal(np.asarray(im), self.rgb[:5, :10]))
        with self.assertRaises(ValueError):
            images.region_png(img, -30, 0, 20, 10)                       # entirely left of the image

    def test_decoded_cache_single_flight_and_idle_eviction(self):
        import threading
        p = self.d / 'big.png'
        Image.fromarray(gradient(600, 400)).save(p)
        cache = images.DecodedCache(size=2, idle_s=0.2)
        got, errors = [], []

        def worker():
            try:
                got.append(cache.get(p))
            except Exception as e:
                errors.append(e)
        ts = [threading.Thread(target=worker) for _ in range(6)]
        for t in ts:
            t.start()
        for t in ts:
            t.join(30)
        self.assertEqual(errors, [])
        self.assertEqual(len(got), 6)
        self.assertEqual(cache.decodes, 1)                               # six requests, one decode
        self.assertTrue(all(g is got[0] for g in got))
        import time
        time.sleep(0.3)
        cache.evict_idle()
        cache.get(p)
        self.assertEqual(cache.decodes, 2)                               # dropped after the idle time
        with self.assertRaises(OSError):
            cache.get(self.d / 'missing.png')

    def test_publish_writes_sidecar_first_and_reports_a_pending_sidecar(self):
        seen = []
        sidecar = lambda p: json.dumps({'output': str(p)}).encode()

        def on_reserved(out, data):
            # the sidecar temp file is already on disk and the output is not yet in place
            seen.append((out.exists(), [x.name for x in self.d.iterdir() if x.name.endswith('.tmp')], data))
        tmp = self.d / '.t.partial.png'
        tmp.write_bytes(b'img')
        out, side = images.reserve_and_publish(tmp, self.d, 'p', 2, '.png', sidecar, on_reserved=on_reserved)
        self.assertEqual(seen[0][0], False)
        self.assertEqual(len(seen[0][1]), 1)
        self.assertEqual(json.loads(side.read_text())['output'], str(out))
        self.assertEqual(sorted(x.name for x in self.d.iterdir()), ['p_cu2x.json', 'p_cu2x.png'])
        # the share drops between the output and the sidecar: the output stays, only the sidecar is pending
        orig = images._rename_sidecar
        images._rename_sidecar = lambda tmp_side, output: (_ for _ in ()).throw(OSError('network name gone'))
        try:
            tmp.write_bytes(b'img2')
            with self.assertRaises(images.SidecarPending) as cm:
                images.reserve_and_publish(tmp, self.d, 'p', 2, '.png', sidecar)
        finally:
            images._rename_sidecar = orig
        pending = cm.exception
        self.assertEqual(pending.output.name, 'p_cu2x_2.png')
        self.assertEqual(pending.output.read_bytes(), b'img2')
        self.assertFalse(any(x.name.endswith('.tmp') for x in self.d.iterdir()))   # temp sidecar cleaned up
        side2 = images.write_sidecar(pending.output, pending.data)
        self.assertEqual(side2.name, 'p_cu2x_2.json')
        self.assertEqual(json.loads(side2.read_text())['output'], str(pending.output))

    def test_16bit_encoders_widen_per_strip_from_uint8(self):
        rgb = gradient(300, 270)                                         # more than two 128-row strips
        alpha = np.tile(np.linspace(0, 255, 300).astype(np.uint8), (270, 1))
        images.write_png16(self.d / 's.png', rgb, alpha=alpha)
        arr, depth, _ = read_png16(self.d / 's.png')
        self.assertTrue(np.array_equal(arr, np.dstack([rgb, alpha]).astype(np.uint16) * 257))
        images.write_tiff16(self.d / 's.tif', rgb, alpha=alpha)
        arr, _ = read_tiff16(self.d / 's.tif')
        self.assertTrue(np.array_equal(arr, np.dstack([rgb, alpha]).astype(np.uint16) * 257))
        with self.assertRaises(ValueError):
            images.write_png16(self.d / 'x.png', rgb, alpha=alpha[:5])


if __name__ == '__main__':
    unittest.main()
