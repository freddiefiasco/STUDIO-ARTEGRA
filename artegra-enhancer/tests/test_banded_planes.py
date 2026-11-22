"""The Large-image engine's planes, band and seam arithmetic, banded Lanczos (T1, gate G3 on Pillow), and the streamed result
writers and viewer routes at 28,000 px and up to 32,000 px (gate G8, sizes and synthetic images only)."""
import os
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

import numpy as np
from PIL import Image

from engine import bands, lanczos_bands, planes
from service import images, plane_io

Image.MAX_IMAGE_PIXELS = None
RNG = np.random.default_rng(20261119)


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


class Tmp(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.dir = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()


class PlaneStore(Tmp):
    def test_rows_regions_cols_and_maps_round_trip(self):
        a = synth(700, 513)
        p = planes.from_array(self.dir / 'a.plane', a, producer='test', run_id='r1')
        q = planes.validate(self.dir / 'a.plane', shape=(700, 513, 3), dtype='u8')
        self.assertEqual(q.header['producer'], 'test')
        np.testing.assert_array_equal(q.read_rows(0, 700), a)
        np.testing.assert_array_equal(q.read_rows(123, 456), a[123:456])
        np.testing.assert_array_equal(q.read_region(10, 20, 300, 400), a[20:400, 10:300])
        np.testing.assert_array_equal(q.read_cols(500, 513), a[:, 500:513])
        m = q.map('r')
        np.testing.assert_array_equal(np.asarray(m), a)
        del m
        self.assertEqual(p.header['sha256'], q.data_sha256())

    def test_never_copy_on_write_and_read_only_stays_read_only(self):
        p = planes.from_array(self.dir / 'a.plane', synth(64, 64))
        q = planes.Plane.open(p.path)
        with self.assertRaises(planes.PlaneError):
            q.map('c')
        with self.assertRaises(planes.PlaneError):
            q.map('r+')
        with self.assertRaises(planes.PlaneError):
            q.write_rows(0, np.zeros((1, 64, 3), np.uint8))

    def test_validation_catches_incomplete_wrong_and_changed_planes(self):
        p = planes.Plane.create(self.dir / 'b.plane', (10, 10, 3))
        with self.assertRaises(planes.PlaneError):
            planes.validate(p.path)                                  # not finished
        p.write_rows(0, np.ones((10, 10, 3), np.uint8))
        p.finish()
        planes.validate(p.path, shape=(10, 10))
        with self.assertRaises(planes.PlaneError):
            planes.validate(p.path, shape=(10, 11))
        with self.assertRaises(planes.PlaneError):
            planes.validate(p.path, dtype='f32')
        with open(p.path, 'r+b') as f:
            f.seek(planes.DATA_OFFSET + 5)
            f.write(b'\x07')
        with self.assertRaises(planes.PlaneError):
            planes.validate(p.path)                                  # changed after it was finished
        with open(self.dir / 'junk.plane', 'wb') as f:
            f.write(b'not a plane')
        with self.assertRaises(planes.PlaneError):
            planes.Plane.open(self.dir / 'junk.plane')

    def test_the_uint8_table_is_the_classics_cpu_conversion(self):
        k = np.arange(256, dtype=np.uint8)
        np.testing.assert_array_equal(planes.U8_TO_F32[k], k.astype(np.float32) / 255.0)
        self.assertEqual(planes.U8_TO_F32.dtype, np.float32)

    def test_32000_px_wide_plane_by_bands_without_a_whole_copy(self):
        h, w = 96, 32000
        p = planes.Plane.create(self.dir / 'w.plane', (h, w, 3))
        for b in bands.bands(h, 288):
            p.write_rows(b.start, synth(b.rows, w, seed=b.index))
        p.finish()
        q = planes.validate(p.path, shape=(h, w, 3))
        np.testing.assert_array_equal(q.read_rows(0, h), synth(h, w, seed=0))

    def test_disk_need(self):
        I, R, O = 30.6e6, 122.5e6, 122.5e6
        # section 2.3 said about 14 GB at 4x of 3500 x 2188 (24 I + 22 R + 84 O); wave 3 counts the stage folder at the finish,
        # with big8, the SAM view and masks and the BXF's scratch folder as measured (170 I + 25 R + 310 O, O the finish
        # plane's pixels; tests/test_plan3_refit.py, the wave-3 merge's bound raise in tests/test_wave3_merge.py)
        self.assertAlmostEqual(planes.live_bytes(I, R, O) / 1e9, 46.2, delta=0.2)
        self.assertGreater(planes.disk_need(I, R, O), planes.live_bytes(I, R, O))


class BandArithmetic(unittest.TestCase):
    def test_only_registered_heights_and_counts(self):
        for h in bands.BAND_HEIGHTS:
            self.assertEqual(h % bands.ALIGN, 0)
        for bad in (1, 7, 100, 287, 289, 1000, 4608):
            with self.assertRaises(AssertionError):
                bands.bands(10_000, bad)
        for bad in (0, 3, 5, 8):
            with self.assertRaises(AssertionError):
                bands.check_process_count(bad)
        self.assertEqual([bands.shrink_processes(n) for n in (4, 2, 1)], [2, 1, 1])

    def test_bands_tile_the_plane_with_real_halo_rows(self):
        for total in (1, 287, 288, 289, 5000, 17504, 28000, 32000):
            for h in bands.BAND_HEIGHTS:
                for halo in (0, 8, 80):
                    bs = bands.bands(total, h, halo)
                    self.assertTrue(bands.covers(bs, total), (total, h, halo))
                    for b in bs:
                        self.assertEqual(b.start % h, 0)
                        self.assertEqual(b.read_start, max(0, b.start - halo))
                        self.assertEqual(b.read_stop, min(total, b.stop + halo))
                    self.assertEqual(bands.join_rows(bs), [b.start for b in bs[1:]])

    def test_band_height_from_the_budget_stays_registered(self):
        self.assertEqual(bands.band_height_for(32000, 12, 6 << 30, halo=80), 2304)
        self.assertEqual(bands.band_height_for(32000, 12, 1 << 20), 288)
        self.assertIn(bands.band_height_for(28000, 24, 300 << 20, halo=64), bands.BAND_HEIGHTS)

    def test_dat_tiles_match_the_classic_loop(self):
        """The tile grid of margin_tiled_upscale (node_pack/claude_creative/__init__.py), restated: starts, cores, crops."""
        tile, margin, blend = 512, 64, 16
        core, step = tile - 2 * margin, tile - 2 * margin - blend
        for n in (100, 512, 513, 1000, 2188, 3500, 7000, 8000):
            if n <= tile:
                self.assertEqual(bands.dat_starts(n), [0])
                continue
            s = sorted(set(max(0, min(n - core, v)) for v in list(range(0, n - core, step)) + [n - core]))
            self.assertEqual(bands.dat_starts(n), s)
            st = bands.dat_starts(n)
            covered = set()
            for v in st:
                covered.update(range(v, v + core))
            self.assertEqual(covered, set(range(n)))

    def test_dat_rows_flush_in_order_and_hold_a_bounded_band(self):
        for H, W in ((2188, 3500), (8752, 14000), (64, 4000), (4000, 64), (17504, 28000)):
            rows = bands.dat_tile_rows(H, W)
            fin = bands.dat_final_rows(rows, H)
            self.assertEqual(fin[0][0], 0)
            self.assertEqual(fin[-1][1], H * 4)
            for (a, b), (c, d) in zip(fin, fin[1:]):
                self.assertEqual(b, c)
            for r in rows:
                self.assertEqual([t.y for t in r], [r[0].y] * len(r))
            # the memory model's 2560 big rows (2048 + 512) bound the live band of every image
            self.assertLessEqual(bands.dat_live_rows(rows), 2560, (H, W))


def accumulate_whole(img, fn, scale, tile=512, margin=64, blend=16):
    """margin_tiled_upscale's accumulation, restated with numpy float32 (one image)."""
    H, W, C = img.shape
    acc = np.zeros((H * scale, W * scale, C), np.float32)
    wsum = np.zeros((H * scale, W * scale, 1), np.float32)
    for row in bands.dat_tile_rows(H, W, tile, margin, blend):
        for t in row:
            o = fn(img[t.iy0:t.iy1, t.ix0:t.ix1])
            o = o[(t.cy0 - t.iy0) * scale:(t.cy1 - t.iy0) * scale, (t.cx0 - t.ix0) * scale:(t.cx1 - t.ix0) * scale]
            w = (_ramp(t.cy1 - t.cy0, t.lo_y, t.hi_y, blend).repeat(scale)[:, None]
                 * _ramp(t.cx1 - t.cx0, t.lo_x, t.hi_x, blend).repeat(scale)[None, :])[..., None]
            acc[t.cy0 * scale:t.cy1 * scale, t.cx0 * scale:t.cx1 * scale] += o * w
            wsum[t.cy0 * scale:t.cy1 * scale, t.cx0 * scale:t.cx1 * scale] += w
    return acc / wsum


def _ramp(n, lo, hi, blend):
    w = np.ones(n, np.float32)
    r = np.arange(1, blend + 1, dtype=np.float32) / np.float32(blend + 1)
    if not lo:
        w[:blend] = r
    if not hi:
        w[-blend:] = np.minimum(w[-blend:], r[::-1])
    return w


class BandedDatAccumulator(unittest.TestCase):
    """The banded x4 accumulator (L2: acc and wsum per live tile-row band, flushed in row chunks) gives the whole
    accumulator's values exactly: the same products are added in the same order to every pixel."""

    def test_banded_equals_whole(self):
        from engine import dat_bands
        fn = lambda a: (np.repeat(np.repeat(a.astype(np.float32) / 255.0, 4, 0), 4, 1) ** 1.3 * np.float32(0.97)
                        + np.float32(0.01)).astype(np.float32)
        for H, W in ((300, 700), (1100, 530), (513, 1500)):
            img = synth(H, W, seed=H)
            whole = accumulate_whole(img, fn, 4)
            got = np.zeros_like(whole)

            def sink(y0, rows):
                got[y0:y0 + rows.shape[0]] = rows
            dat_bands.margin_tiled_banded(lambda y0, y1, x0, x1: img[y0:y1, x0:x1], (H, W, 3), fn, 4, sink)
            np.testing.assert_array_equal(got, whole)


class BandedLanczos(Tmp):
    """T1 / G3: the banded two-pass Lanczos equals Pillow's whole call, for every production ratio and the viewer proxy."""

    def test_production_pairs(self):
        cases = [((520, 344), (390, 258)),           # k = 3: x4 output to a 3x render (4/3 down)
                 ((800, 600), (400, 300)),           # k = 2 (s 1 of f 2 from x4)
                 ((800, 600), (300, 225)),           # k = 1.5 (8/3 down)
                 ((1000, 504), (750, 378)),          # padded non-dyadic
                 ((160, 2400), (120, 1800)),         # tall and narrow
                 ((640, 480), (640, 300)),           # vertical only
                 ((640, 480), (500, 480)),           # horizontal only
                 ((300, 200), (300, 200))]           # no change
        for (w, h), (w2, h2) in cases:
            for c in (3, 1):
                a = synth(h, w, c, seed=w + c)
                whole = np.asarray(Image.fromarray(a if c == 3 else a[..., 0]).resize((w2, h2), Image.LANCZOS))
                got = lanczos_bands.resize_array(a if c == 3 else a[..., 0], (w2, h2), row_band=288, col_strip=97)
                np.testing.assert_array_equal(got, whole, err_msg=str(((w, h), (w2, h2), c)))

    def test_on_planes_at_28000_and_32000_px(self):
        for w, h, w2, h2 in ((28000, 120, 21000, 90), (32000, 64, 4096, 8), (1200, 32000, 900, 24000)):
            a = synth(h, w, seed=w)
            src = planes.from_array(self.dir / f's{w}.plane', a)
            dst = planes.Plane.create(self.dir / f'd{w}.plane', (h2, w2, 3))
            tmp = planes.Plane.create(self.dir / f't{w}.plane', (h, w2, 3))
            lanczos_bands.resize(src, dst, tmp, row_band=1152, col_strip=4096)
            whole = np.asarray(Image.fromarray(a).resize((w2, h2), Image.LANCZOS))
            np.testing.assert_array_equal(dst.read_rows(0, h2), whole, err_msg=str((w, h)))


class ResultFiles(Tmp):
    """G8: every writer at 28,000 and 32,000 px from a plane, RGB and RGBA, decoded back to the same pixels."""

    def plane(self, h, w, name='r'):
        return planes.from_array(self.dir / f'{name}.plane', synth(h, w, seed=w))

    def alpha(self, h, w):
        a = np.zeros((h, w, 1), np.uint8)
        a[:, : w // 2] = 255
        a[:, w // 2: w // 2 + 100, 0] = np.arange(100, dtype=np.uint8)[None, :] * 2
        return planes.from_array(self.dir / 'alpha.plane', a)

    def test_png8_and_png16_rgb_and_rgba(self):
        for w in (28000, 32000):
            h = 40
            p, al = self.plane(h, w, f'p{w}'), self.alpha(h, w)
            ref = p.read_rows(0, h)
            for bits in (8, 16):
                for alpha in (None, al):
                    out = self.dir / f'o{w}-{bits}-{alpha is not None}.png'
                    plane_io.write_png(out, p, bits=bits, alpha=alpha, level=1, icc=images.srgb_icc_bytes())
                    with Image.open(out) as im:
                        self.assertEqual(im.size, (w, h))
                        arr = np.asarray(im)
                    if bits == 8:
                        np.testing.assert_array_equal(arr[..., :3], ref)
                        if alpha is not None:
                            np.testing.assert_array_equal(arr[..., 3], al.read_rows(0, h)[..., 0])
                    else:
                        raw = _png16_pixels(out)
                        np.testing.assert_array_equal(raw[..., :3], ref.astype(np.uint16) * 257)
                        if alpha is not None:
                            np.testing.assert_array_equal(raw[..., 3], al.read_rows(0, h)[..., 0].astype(np.uint16) * 257)

    def test_png16_is_the_classic_writers_bytes(self):
        """The 16-bit PNG streamed from a plane has exactly the bytes the classic writer makes from the same pixels."""
        a = synth(300, 1000)
        p = planes.from_array(self.dir / 'c.plane', a)
        icc = images.srgb_icc_bytes()
        plane_io.write_png(self.dir / 'new.png', p, bits=16, level=6, icc=icc)
        images.write_png16(self.dir / 'old.png', a, icc=icc)
        self.assertEqual((self.dir / 'new.png').read_bytes(), (self.dir / 'old.png').read_bytes())

    def test_tiff16_classic_and_bigtiff(self):
        for w, big in ((28000, False), (32000, True)):
            h = 24
            p = self.plane(h, w, f't{w}')
            al = self.alpha(h, w)
            out = self.dir / f'o{w}.tif'
            kind = plane_io.write_tiff16(out, p, alpha=al, icc=images.srgb_icc_bytes(), big=big)
            self.assertEqual(kind, 'bigtiff' if big else 'tiff')
            with open(out, 'rb') as f:
                self.assertEqual(f.read(4), b'II+\x00' if big else b'II*\x00')
            with Image.open(out) as im:
                self.assertEqual(im.size, (w, h))
                im.load()
                got = np.asarray(im)
            # Pillow reads 16-bit RGBA TIFF as 8-bit RGBA; the 16-bit values are x257 of the plane, so >> 8 is the plane
            np.testing.assert_array_equal(got[..., :3], p.read_rows(0, h))
            np.testing.assert_array_equal(got[..., 3], al.read_rows(0, h)[..., 0])

    def test_bigtiff_is_chosen_past_4_gib_of_data(self):
        self.assertGreater(32000 * 32000 * 3 * 2, plane_io.BIGTIFF_ABOVE)
        self.assertLess(14000 * 8752 * 3 * 2, plane_io.BIGTIFF_ABOVE)

    def test_jpeg(self):
        p = self.plane(64, 28000, 'j')
        out = self.dir / 'o.jpg'
        plane_io.write_jpeg(out, p)
        with Image.open(out) as im:
            self.assertEqual(im.size, (28000, 64))
            diff = np.abs(np.asarray(im).astype(int) - p.read_rows(0, 64).astype(int))
        self.assertLess(diff.mean(), 6)
        self.assertEqual(plane_io.jpeg_transient_bytes(32000, 32000), 4 * 32000 * 32000)

    def test_encode_reports_the_writer(self):
        p = self.plane(16, 512, 'e')
        for fmt in ('png8', 'png16', 'tiff16', 'jpeg'):
            info = plane_io.encode(self.dir / f'e.{fmt}', p, fmt, alpha=self.alpha(16, 512), icc=images.srgb_icc_bytes())
            self.assertEqual(info['writer'], 'streamed')
            self.assertEqual(info['alpha'], 'dropped (JPEG has no transparency)' if fmt == 'jpeg' else 'kept')


class Viewer(Tmp):
    def test_proxy_is_pillows_whole_lanczos(self):
        for (w, h) in ((28000, 300), (32000, 200), (500, 32000)):
            a = synth(h, w, seed=h)
            p = planes.from_array(self.dir / f'v{w}.plane', a)
            got = plane_io.proxy(p, self.dir)
            size = lanczos_bands.proxy_size(w, h, 4096)
            self.assertEqual(size, images.preview_size(w, h, 4096))
            whole = np.asarray(Image.fromarray(a).resize(size, Image.LANCZOS))
            np.testing.assert_array_equal(got, whole)
            self.assertLessEqual(max(got.shape[:2]), 4096)

    def test_regions_are_lossless_crops(self):
        a = synth(1000, 32000, seed=3)
        p = planes.from_array(self.dir / 'r.plane', a)
        arr, box = plane_io.region(p, 31000, 900, 4096, 4096)
        self.assertEqual(box, (31000, 900, 1000, 100))
        np.testing.assert_array_equal(arr, a[900:1000, 31000:32000])
        png, box = plane_io.region_png(p, 100, 100, 300, 200)
        from io import BytesIO
        with Image.open(BytesIO(png)) as im:
            np.testing.assert_array_equal(np.asarray(im), a[100:300, 100:400])
        for bad in ((0, 0, 0, 10), (0, 0, 4097, 10), (40000, 0, 10, 10)):
            with self.assertRaises(ValueError):
                plane_io.region(p, *bad)


def _png16_pixels(path):
    """Decode a 16-bit RGB/RGBA PNG with filter Up (our writers' only filter) to H x W x C uint16 (Pillow reads RGB16 as 8-bit)."""
    data = Path(path).read_bytes()
    pos, idat, w = 8, b'', 0
    while pos < len(data):
        n = struct.unpack('>I', data[pos:pos + 4])[0]
        tag = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + n]
        if tag == b'IHDR':
            w, h, bits, ctype = struct.unpack('>IIBB', body[:10])
            c = 3 if ctype == 2 else 4
        elif tag == b'IDAT':
            idat += body
        pos += 12 + n
    raw = np.frombuffer(zlib.decompress(idat), np.uint8).reshape(h, 1 + w * c * 2)
    assert (raw[:, 0] == 2).all()
    rows = np.cumsum(raw[:, 1:].astype(np.uint64), axis=0).astype(np.uint8)
    return rows.view('>u2').reshape(h, w, c).astype(np.uint16)


if __name__ == '__main__':
    unittest.main()
