"""The service with the Large-image engine on the fake engine (engine design sections 2.10, 3, 3.1; gate G8): sizes and
synthetic images only.

- A release build admits Large-image plans only up to its release sizes (engine/banded_plan.BANDED_PROVEN_MP; before the
  5.0.2 release step they were 0, so it planned exactly as 5.0.1); above them the answer is 5.0.1's own refusal. It refuses
  the developer force switch at submit, in plain words.
- A developer build (the test launcher's CU_TEST_DEV_CHANNEL) runs images 5.0.1 refuses through the Large-image engine:
  28,000 and 32,000 px outputs, three passes, the split finish in a fresh engine process (L3r), stage planes instead of
  stage PNGs, every writer (PNG 8/16, TIFF 16, JPEG; RGBA), the plan card and sidecar naming the engine, and the viewer's
  region and proxy routes cut from the result plane.
- The force switch runs a plan the Classic engine accepts through the Large-image engine with the classic plan's own stages."""
import io
import json
import time
import unittest

import numpy as np
from PIL import Image

from service import images
from tests.service.helpers import gradient, read_png16, read_tiff16, split_strip_height
from tests.service.test_integration import Base, DONE, all_done, rid

Image.MAX_IMAGE_PIXELS = None
DEV = {'CU_TEST_DEV_CHANNEL': json.dumps({'ws128': 2000.0, 'pc64': 2000.0, 'pc48': 2000.0})}


def strip_input(d, name, w, h, alpha=False, seed=1):
    d.mkdir(parents=True, exist_ok=True)
    a = gradient(w, h, seed)
    if alpha:
        al = np.tile(np.linspace(0, 255, w).astype(np.uint8), (h, 1))
        Image.fromarray(np.dstack([a, al])).save(d / name)
    else:
        Image.fromarray(a).save(d / name)
    return d / name


class ReleaseBuild(Base):
    def test_501s_refusal_and_no_force_switch(self):
        svc = self.service()
        mid = self.add(svc, [strip_input(self.d / 'in', 'wide.png', 4000, 1000)])['items'][0]['id']
        code, res, _ = svc.post('/api/plan', {'width': 4000, 'height': 1000, 'scale': 8})
        self.assertEqual(code, 200, res)
        self.assertFalse(res['ok'])                                 # 256 MP: over every class's release size
        self.assertIn('The largest supported output is about 150 MP', res['reason'])     # 5.0.1's own refusal
        self.assertNotIn('engine', res)
        job = self.job(svc, [mid], {'scale': 8}, expect=400)
        self.assertEqual(job['error']['code'], 'plan_refused')
        job = self.job(svc, [mid], {'scale': 2}, expect=400, dev_force_engine='banded')
        self.assertEqual(job['error']['code'], 'dev_setting')
        self.assertEqual(job['error']['message'], 'This developer setting is not available in this build.')
        self.assertTrue(any(e.get('event') == 'dev_setting_refused' for e in svc.log_lines()))


class DeveloperBuild(Base):
    env = DEV

    def run_one(self, svc, path, scale, fmt='png8', **extra):
        mid = self.add(svc, [path])['items'][0]['id']
        job = self.job(svc, [mid], {'scale': scale, 'output_format': fmt}, **extra)
        self.assertEqual(job['items'][0]['plan'].get('engine'), 'banded', job['items'][0]['plan'])
        job = svc.wait_job(job['id'], all_done, timeout=240)
        it = job['items'][0]
        self.assertEqual(it['state'], 'done', it)
        return job, it

    def test_32000_px_three_passes_with_the_split_finish(self):
        # 5.0.2 wave 3 (contracts.split_premise): the smallest strip height whose 8x plan splits every pass here, from the
        # planner at run time as the service runs it (a developer build's sizes, no probe table), so a refit of the
        # memory model moves the height, not the premise; the premise is asserted on the plan the job made
        H = split_strip_height()
        self.assertIsNotNone(H, 'no listed strip height splits every pass of 8x of 4000 x H on this computer')
        svc = self.service()
        code, res, _ = svc.post('/api/plan', {'width': 4000, 'height': H, 'scale': 8})
        self.assertEqual(code, 200, res)
        self.assertTrue(res['ok'], res)
        self.assertEqual(res['output_size'], [32000, 8 * H])
        self.assertEqual(res['engine'], 'banded')
        self.assertIn('Large-image', res['text']['engine'])
        job, it = self.run_one(svc, strip_input(self.d / 'in', 'wide.png', 4000, H), 8)
        plan = it['plan']
        self.assertEqual(len(plan['stages']), 3)
        self.assertTrue(all(s['split_finish'] for s in plan['stages']))         # the premise, on the plan the job made
        with Image.open(it['output']) as im:
            self.assertEqual(im.size, (32000, 8 * H))
            out = np.asarray(im.convert('RGB'))
        side = json.loads(open(it['sidecar'], encoding='utf8').read())
        self.assertEqual(side['engine']['executor'], 'large-image')
        self.assertEqual(side['engine']['finish'], 'bxf-1')
        self.assertIsNone(side['engine']['halo_fix'])
        self.assertEqual(side['output']['writer'], 'streamed')
        events = [e.get('event') for e in svc.log_lines()]
        self.assertEqual(events.count('banded_split_restart'), 3)
        # the viewer: a lossless region of the kept result plane equals the saved file's pixels
        q = f'kind=result&job={job["id"]}&item={it["id"]}'
        code, png, hdr = svc.get(f'/api/media/{it["media_id"]}/region?x=31000&y=100&w=1000&h=300&{q}', raw=True)
        self.assertEqual(code, 200, png[:300])
        with Image.open(io.BytesIO(png)) as im:
            np.testing.assert_array_equal(np.asarray(im), out[100:400, 31000:32000])
        self.assertEqual(hdr.get('X-Image-Size'), f'32000,{8 * H}')
        code, jpg, hdr = svc.get(f'/api/media/{it["media_id"]}/proxy?{q}', raw=True)
        self.assertEqual(code, 200)
        with Image.open(io.BytesIO(jpg)) as im:
            self.assertLessEqual(max(im.size), images.PROXY_SIDE)
        code, jpg, hdr = svc.get(f'/api/media/{it["media_id"]}/proxy?w=2000&h=100&{q}', raw=True)
        self.assertEqual(code, 200, jpg[:300])
        # every pass ran as Large-image graphs: no whole-image node, the finish in its own prompt
        prompts = sorted((self.d / 'state' / 'workers').rglob('fake-prompts/*.json'))
        classes = set()
        for p in prompts:
            classes |= {n['class_type'] for n in json.loads(p.read_text(encoding='utf8')).values()}
        self.assertIn('CUFinishBanded', classes)
        self.assertIn('CUPlaneCheckpoint', classes)
        self.assertFalse(classes & {'LoadImage', 'ImageScale', 'SaveImage', 'ClaudeV4Finish', 'VAEDecodeTiled'})

    def test_28000_px_rgba_through_every_writer(self):
        svc = self.service()
        src = strip_input(self.d / 'in', 'alpha.png', 3500, 64, alpha=True)
        for fmt in ('png8', 'png16', 'tiff16', 'jpeg'):
            job, it = self.run_one(svc, src, 8, fmt)
            W, H = 28000, 512
            if fmt == 'png8':
                with Image.open(it['output']) as im:
                    self.assertEqual((im.size, im.mode), ((W, H), 'RGBA'))
                    a = np.asarray(im)[..., 3]
                want = np.asarray(Image.open(src).getchannel('A').resize((W, H), Image.LANCZOS))
                np.testing.assert_array_equal(a, want)                    # the banded alpha is Pillow's whole LANCZOS
            elif fmt == 'png16':
                arr, depth, _ = read_png16(it['output'])
                self.assertEqual((arr.shape, depth), ((H, W, 4), 16))
            elif fmt == 'tiff16':
                arr = read_tiff16(it["output"])[0]
                self.assertEqual(arr.shape[:2], (H, W))
            else:
                with Image.open(it['output']) as im:
                    self.assertEqual((im.size, im.mode), ((W, H), 'RGB'))

    def test_force_switch_runs_the_classic_plan_through_the_new_path(self):
        svc = self.service()
        src = strip_input(self.d / 'in', 'small.png', 640, 480)
        code, classic, _ = svc.post('/api/plan', {'width': 640, 'height': 480, 'scale': 2})
        self.assertEqual(code, 200)
        self.assertNotIn('engine', classic)                         # the default stays classic in a developer build too
        job, it = self.run_one(svc, src, 2, dev_force_engine='banded')
        plan = it['plan']
        self.assertTrue(plan['banded']['forced'])
        self.assertEqual([[s[k] for k in ('factor', 'supersample', 'padded_size', 'render_size', 'output_size')]
                          for s in plan['stages']],
                         [[s[k] for k in ('factor', 'supersample', 'padded_size', 'render_size', 'output_size')]
                          for s in classic['stages']])
        with Image.open(it['output']) as im:
            self.assertEqual(im.size, (1280, 960))
        code, jobs, _ = svc.get(f'/api/jobs/{job["id"]}')
        self.assertEqual(jobs.get('dev_force_engine', 'banded'), 'banded')

    def test_a_classic_image_in_a_developer_build_is_classic(self):
        svc = self.service()
        mid = self.add(svc, [strip_input(self.d / 'in', 'small.png', 640, 480)])['items'][0]['id']
        job = self.job(svc, [mid], {'scale': 2})
        self.assertNotIn('engine', job['items'][0]['plan'])
        job = svc.wait_job(job['id'], all_done, timeout=120)
        self.assertEqual(job['items'][0]['state'], 'done')
        side = json.loads(open(job['items'][0]['sidecar'], encoding='utf8').read())
        self.assertNotIn('executor', side['engine'])
        self.assertEqual(side['engine']['graph'], 'engine/graph_v5t.py')


if __name__ == '__main__':
    unittest.main()
