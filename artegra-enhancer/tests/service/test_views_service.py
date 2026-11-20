"""The viewer and the engine names on a real service with the fake engine, in a developer build (engine design 2.10, B13,
B15; gate G8): sizes and synthetic images only. WRITTEN FOR THE MERGE ROLE: it starts a service process (ports 18950-18969),
so package worktrees do not run it.

- /api/plan says which engine will run a plan; a classic plan keeps 5.0.1's keys.
- A Large-image result's sized copy is made once per size and kept on disk beside its plane; a second ask is the same bytes.
- A Large-image result with transparency has RGBA PNG proxies; its regions are lossless RGBA crops of the plane.
- The item's plan and the sidecar name the engine."""
import io
import json
import unittest

import numpy as np
from PIL import Image

from service import images, plane_views
from tests.service.test_banded_service import DEV, strip_input
from tests.service.test_integration import Base, all_done

Image.MAX_IMAGE_PIXELS = None


class PlanAnswers(Base):
    env = DEV

    def test_the_plan_answer_names_the_engine(self):
        svc = self.service()
        code, classic, _ = svc.post('/api/plan', {'width': 640, 'height': 480, 'scale': 2})
        self.assertEqual(code, 200, classic)
        self.assertEqual(classic['executor'], 'classic')
        self.assertNotIn('engine', classic)
        self.assertEqual(classic['text']['engine'], 'Engine: Classic')
        code, large, _ = svc.post('/api/plan', {'width': 4000, 'height': 64, 'scale': 8})
        self.assertEqual(code, 200, large)
        self.assertEqual((large['executor'], large['engine']), ('large-image', 'banded'))
        self.assertEqual(large['text']['engine'],
                         'Engine: Large-image (this size is beyond the Classic engine on this computer)')
        self.assertIn('disk', large['text'])


class LargeImageViewer(Base):
    env = DEV

    def run_one(self, svc, path, scale, fmt='png8'):
        mid = self.add(svc, [path])['items'][0]['id']
        job = self.job(svc, [mid], {'scale': scale, 'output_format': fmt})
        self.assertEqual(job['items'][0]['plan'].get('engine'), 'banded', job['items'][0]['plan'])
        job = svc.wait_job(job['id'], all_done, timeout=240)
        it = job['items'][0]
        self.assertEqual(it['state'], 'done', it)
        return job, it

    def test_sized_copies_are_made_once_and_kept_beside_the_plane(self):
        svc = self.service()
        job, it = self.run_one(svc, strip_input(self.d / 'in', 'wide.png', 4000, 64), 8)
        q = f'kind=result&job={job["id"]}&item={it["id"]}'
        code, first, hdr = svc.get(f'/api/media/{it["media_id"]}/proxy?w=2000&h=40&{q}', raw=True)
        self.assertEqual(code, 200, first[:300])
        self.assertEqual(hdr.get('X-Sized'), '2000,40')
        self.assertEqual(hdr.get('X-Image-Size'), '32000,512')
        code, again, _ = svc.get(f'/api/media/{it["media_id"]}/proxy?w=2000&h=40&{q}', raw=True)
        self.assertEqual((code, again), (200, first))
        rdir = self.d / 'state' / 'media' / 'results' / f'{job["id"]}_{it["id"]}'
        kept = list((rdir / plane_views.SIZED_DIR).glob('2000x40-*.jpg'))
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].read_bytes(), first)
        with Image.open(it['output']) as im:
            want = np.asarray(im.convert('RGB').resize((2000, 40), Image.LANCZOS))
        buf = io.BytesIO()
        Image.fromarray(want).save(buf, 'JPEG', quality=images.SIZED_JPEG_QUALITY, subsampling=0)
        self.assertEqual(first, buf.getvalue())

    def test_rgba_results_have_rgba_proxies_and_regions(self):
        svc = self.service()
        job, it = self.run_one(svc, strip_input(self.d / 'in', 'alpha.png', 3500, 64, alpha=True), 8)
        q = f'kind=result&job={job["id"]}&item={it["id"]}'
        code, png, hdr = svc.get(f'/api/media/{it["media_id"]}/proxy?{q}', raw=True)
        self.assertEqual(code, 200)
        self.assertEqual(hdr.get('Content-Type'), 'image/png')
        with Image.open(io.BytesIO(png)) as im:
            self.assertEqual(im.mode, 'RGBA')
            self.assertLessEqual(max(im.size), images.PROXY_SIDE)
        with Image.open(it['output']) as im:
            full = np.asarray(im)
        code, png, hdr = svc.get(f'/api/media/{it["media_id"]}/region?x=27000&y=100&w=1000&h=300&{q}', raw=True)
        self.assertEqual(code, 200, png[:300])
        with Image.open(io.BytesIO(png)) as im:
            self.assertEqual(im.mode, 'RGBA')
            np.testing.assert_array_equal(np.asarray(im), full[100:400, 27000:28000])
        code, png, hdr = svc.get(f'/api/media/{it["media_id"]}/proxy?w=1400&h=40&{q}', raw=True)
        self.assertEqual((code, hdr.get('Content-Type')), (200, 'image/png'))

    def test_the_sidecar_and_the_item_name_the_engine(self):
        svc = self.service()
        job, it = self.run_one(svc, strip_input(self.d / 'in', 'wide.png', 4000, 64), 8)
        side = json.loads(open(it['sidecar'], encoding='utf8').read())
        self.assertEqual(side['engine']['executor'], 'large-image')
        self.assertEqual(side['plan']['engine'], 'banded')
        self.assertEqual(side['engine']['finish'], 'bxf-1')


if __name__ == '__main__':
    unittest.main()
