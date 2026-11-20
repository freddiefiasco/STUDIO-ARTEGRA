"""tools/proof/pairs.py: the X/Y order follows the hash rule, the crops are chosen as registered, nothing in the judges'
material names an engine, identical pairs are kept as controls, and the sealed key round-trips. Synthetic images."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from engine import planes
from tools.proof import colour, pairs


def outputs(seed=0, W=1600, H=1200, f=2):
    rng = np.random.default_rng(seed)
    src = np.clip(colour.gaussian(rng.standard_normal((H // f, W // f)), 2.0) * 25 + 128, 0, 255).astype(np.uint8)
    src[: H // f // 2, :] = 200                           # a flat sky band (the top half)
    src = src[..., None].repeat(3, -1)
    a = src.repeat(f, 0).repeat(f, 1)
    b = a.copy()
    b[400:420, 300:320] ^= 7                                # the BES differs in one place
    return src, a, b


class Order(unittest.TestCase):
    def test_parity_of_the_first_byte(self):
        for case, crop in (('C1', 'edge01'), ('C1', 'edge02'), ('C3b', 'flat'), ('W1', 'proxy')):
            b0 = hashlib.sha256(f'{case}/{crop}'.encode('utf8')).digest()[0]
            o = pairs.order(case, crop)
            self.assertEqual(o['X'], 'classic' if b0 % 2 == 0 else 'bes')
            self.assertEqual({o['X'], o['Y']}, {'classic', 'bes'})

    def test_both_orders_occur(self):
        xs = {pairs.order('C1', f'edge{i:02d}')['X'] for i in range(1, 9)}
        self.assertEqual(xs, {'classic', 'bes'})


class Crops(unittest.TestCase):
    def test_the_registered_crop_set(self):
        src, a, b = outputs()
        H, W = a.shape[:2]
        worst_a = [{'x': 150 + 250 * i, 'y': 600, 'halo_index': 5.0 - i} for i in range(6)]
        worst_b = [{'x': 1400, 'y': 100 + 200 * i, 'halo_index': 4.5 - i} for i in range(6)]
        pos = {'rows': {'vae': [256, 512, 768, 1024], 'bxf_band': [288, 576, 864, 1152]}, 'cols': {'dat': [800]}}
        crops = pairs.select_crops(worst_a, worst_b, pos, src, 2)
        kinds = [c['kind'] for c in crops]
        self.assertEqual(kinds.count('edge'), 8)
        self.assertEqual(kinds.count('boundary'), 4)
        self.assertEqual((kinds.count('flat'), kinds.count('textured'), kinds.count('proxy')), (1, 1, 1))
        for c in crops:
            if c['kind'] != 'proxy':
                x0, y0, x1, y1 = c['box']
                self.assertEqual((x1 - x0, y1 - y0), (512, 512))
                self.assertTrue(0 <= x0 and 0 <= y0 and x1 <= W and y1 <= H)
        first = crops[0]                                       # the worst segment of the union: worst_a's first
        self.assertEqual(first['id'], 'edge01')
        self.assertTrue(first['box'][0] <= 150 < first['box'][2] and first['box'][1] <= 600 < first['box'][3])
        self.assertEqual(crops[1]['center'], [1400, 100])       # then worst_b's first (halo index 4.5)
        flat = [c for c in crops if c['kind'] == 'flat'][0]
        self.assertLessEqual(flat['box'][3], H // 2)          # in the flat band
        tex = [c for c in crops if c['kind'] == 'textured'][0]
        self.assertGreaterEqual(tex['center'][1], H // 2)     # centred in the textured half
        ids = [c['id'] for c in crops]
        self.assertEqual(len(ids), len(set(ids)))

    def test_near_duplicate_segments_give_one_crop(self):
        src, a, b = outputs()
        worst = [{'x': 300 + 40 * i, 'y': 410, 'halo_index': 5.0 - i} for i in range(6)]
        edges = [c for c in pairs.select_crops(worst, [], {'rows': {}, 'cols': {}}, src, 2) if c['kind'] == 'edge']
        self.assertEqual([c['center'][0] for c in edges], [300, 460])     # centres at least 128 px apart


class Making(unittest.TestCase):
    def test_pairs_key_and_leaks(self):
        src, a, b = outputs()
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            pdir, sealed = d / 'pairs', d / 'sealed'
            crops = [{'id': 'edge01', 'kind': 'edge', 'box': [200, 300, 712, 812]},
                     {'id': 'flat', 'kind': 'flat', 'box': [1000, 0, 1512, 512]},
                     {'id': 'proxy', 'kind': 'proxy', 'box': None}]
            man, key = pairs.make_pairs('C1', a, b, src, 2, crops, pdir)
            msha = pairs.write_manifest(pdir, man)
            text = (pdir / 'PAIRS.json').read_text(encoding='utf8').lower()
            for word in ('classic', 'bes', 'banded', 'identical', 'large-image'):
                self.assertNotIn(word, text)
            for row in man:
                files = sorted(p.name for p in (pdir / row['pair']).iterdir())
                self.assertEqual(files, ['X.png', 'Y.png', 'source.png'])
                for name in ('X.png', 'Y.png'):
                    with Image.open(pdir / row['pair'] / name) as im:
                        self.assertEqual({k for k in im.info if k not in ('dpi',)}, set())
                        self.assertEqual(im.mode, 'RGB')
            by = {k['pair']: k for k in key}
            self.assertFalse(by['C1/edge01']['identical'])
            self.assertTrue(by['C1/flat']['identical'])            # unchanged area: a blind control
            with Image.open(pdir / 'C1' / 'edge01' / 'X.png') as im:
                x = np.asarray(im)
            want = (a if by['C1/edge01']['X'] == 'classic' else b)[300:812, 200:712]
            self.assertTrue(np.array_equal(x, want))
            with Image.open(pdir / 'C1' / 'proxy' / 'X.png') as im:
                self.assertEqual(max(im.size), 1600 if max(a.shape[:2]) <= 2048 else 2048)
            with Image.open(pdir / 'C1' / 'edge01' / 'source.png') as im:
                self.assertEqual(im.size, (256, 256))
            with self.assertRaises(ValueError):
                pairs.write_key(pdir / 'KEY.json', key, pdir, msha)
            ksha = pairs.write_key(sealed / 'KEY.json', key, pdir, msha)
            with self.assertRaises(FileExistsError):
                pairs.write_key(sealed / 'KEY.json', key, pdir, msha)
            back = pairs.read_key(sealed / 'KEY.json', ksha)
            self.assertEqual(back['pairs'], {k['pair']: {kk: v for kk, v in k.items() if kk != 'pair'} for k in key})
            self.assertEqual(back['manifest_sha256'], msha)
            (sealed / 'KEY.json').write_text(json.dumps(dict(back, pairs={})), encoding='utf8')
            with self.assertRaises(ValueError):
                pairs.read_key(sealed / 'KEY.json', ksha)

    def test_proxy_of_a_plane_equals_the_array_proxy(self):
        rng = np.random.default_rng(1)
        a = rng.integers(0, 256, (3000, 2200, 3)).astype(np.uint8)
        with tempfile.TemporaryDirectory() as d:
            p = planes.from_array(Path(d) / 'o.plane', a)
            x = pairs.proxy({'kind': 'plane', 'path': str(p.path)})
            del p
        y = pairs.proxy(a)
        self.assertEqual(max(x.shape[:2]), 2048)
        self.assertTrue(np.array_equal(x, y))


if __name__ == '__main__':
    unittest.main()
