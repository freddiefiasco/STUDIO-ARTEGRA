"""The whole Large-image job through the real service on the fake engine (BUILD-WAVE-2 package integ, item 2's real-service
twin of tests/test_integ_large_image_job.py). A developer build (the launcher's CU_TEST_DEV_CHANNEL) runs plans 5.0.1 refuses:
- 8x of 4000 x 160 on the workstation class: 32,000 x 1,280 px, three passes, each split into prompt A and a finish in a
  fresh engine (the merged planner's model splits every stage of this size on the workstation under either finish tier;
  4000 x 64 kept its first passes whole there once the wave-2 model terms were merged: tests/test_wave2_merge.py); every class of the merged graph_banded.NODE_SPECS in the prompts the engine accepted (every protect category on, so
  the release terms and their unions are there); the viewer's lossless region, proxy and sized copy from the result plane; the
  engine's start logs no missing Large-image part (the worker whitelist loads claude_banded);
- 8x of 3500 x 64 with transparency on a 64 GB PC's class (memory cap 59.0 GiB): 28,000 x 512 px, one prompt per pass, through
  every writer (PNG 8 and 16, TIFF 16, JPEG);
- the engine dying in the finish prompt of pass 2: the restarted service goes on from that pass's saved first part;
- the developer force switch on a plan the Classic engine accepts.
Written and not run by its package (the builder rule: no package starts a service on the workstation); the merge role runs it
first (adds merge_runs_first). Sizes and synthetic pictures only."""
import io
import json
import unittest

import numpy as np
from PIL import Image

from engine import graph_banded
from tests.service.helpers import gradient, read_png16, read_tiff16, split_strip_height
from tests.service.test_integration import Base, all_done

Image.MAX_IMAGE_PIXELS = None
DEV = {'CU_TEST_DEV_CHANNEL': json.dumps({'ws128': 2000.0, 'pc64': 2000.0, 'pc48': 2000.0})}
EVERY_CATEGORY = {'protect': ['people', 'furniture', 'vehicles', 'windows', 'architecture']}


def strip_input(d, name, w, h, alpha=False, seed=1):
    d.mkdir(parents=True, exist_ok=True)
    a = gradient(w, h, seed)
    if alpha:
        al = np.tile(np.linspace(0, 255, w).astype(np.uint8), (h, 1))
        Image.fromarray(np.dstack([a, al])).save(d / name)
    else:
        Image.fromarray(a).save(d / name)
    return d / name


class IntegBase(Base):
    env = DEV

    def run_one(self, svc, path, settings, timeout=300, **extra):
        mid = self.add(svc, [path])['items'][0]['id']
        job = self.job(svc, [mid], settings, **extra)
        self.assertEqual(job['items'][0]['plan'].get('engine'), 'banded', job['items'][0]['plan'])
        job = svc.wait_job(job['id'], all_done, timeout=timeout)
        it = job['items'][0]
        self.assertEqual(it['state'], 'done', it)
        return job, it

    def prompt_classes(self):
        out = set()
        for p in sorted((self.d / 'state' / 'workers').rglob('fake-prompts/*.json')):
            out |= {n['class_type'] for n in json.loads(p.read_text(encoding='utf8')).values()}
        return out


class Every32000PxPass(IntegBase):
    def test_every_pass_every_node_and_the_viewer(self):
        # 5.0.2 wave 3 (contracts.split_premise): the smallest strip height whose 8x plan splits every pass here, from the
        # planner at run time as the service runs it (a developer build's sizes, no probe table), so a refit of the
        # memory model moves the height, not the premise; the premise is asserted on the plan the job made
        H = split_strip_height()
        self.assertIsNotNone(H, 'no listed strip height splits every pass of 8x of 4000 x H on this computer')
        svc = self.service()
        job, it = self.run_one(svc, strip_input(self.d / 'in', 'wide.png', 4000, H), dict(EVERY_CATEGORY, scale=8))
        plan = it['plan']
        self.assertEqual(plan['output_size'], [32000, 8 * H])
        self.assertEqual(len(plan['stages']), 3)
        self.assertTrue(all(s['split_finish'] for s in plan['stages']))
        with Image.open(it['output']) as im:
            self.assertEqual((im.size, im.mode), ((32000, 8 * H), 'RGB'))
            out = np.asarray(im)
        renders = [r for r in svc.renders() if r['status'] == 'success']
        parts = [(r['prefix'].rsplit('_', 2)[-2:] if r['prefix'].endswith('_a') else [r['prefix'][-2:], 'b'])
                 for r in renders]
        self.assertEqual(parts, [['s0', 'a'], ['s0', 'b'], ['s1', 'a'], ['s1', 'b'], ['s2', 'a'], ['s2', 'b']])
        events = [e.get('event') for e in svc.log_lines()]
        self.assertEqual(events.count('banded_split_restart'), 3)
        self.assertNotIn('worker_banded_missing', events)
        self.assertNotIn('worker_banded_inputs', events)
        self.assertNotIn('worker_banded_unchecked', events)
        cls = self.prompt_classes()
        self.assertTrue(set(graph_banded.NODE_SPECS) <= cls, sorted(set(graph_banded.NODE_SPECS) - cls))
        q = f'kind=result&job={job["id"]}&item={it["id"]}'
        rh = min(8 * H, 4096)
        code, png, hdr = svc.get(f'/api/media/{it["media_id"]}/region?x=28000&y=0&w=4000&h={rh}&{q}', raw=True)
        self.assertEqual(code, 200, png[:300])
        with Image.open(io.BytesIO(png)) as im:
            np.testing.assert_array_equal(np.asarray(im), out[:rh, 28000:32000])
        self.assertEqual(hdr.get('X-Image-Size'), f'32000,{8 * H}')
        code, jpg, _ = svc.get(f'/api/media/{it["media_id"]}/proxy?{q}', raw=True)
        self.assertEqual(code, 200)
        code, jpg, hdr = svc.get(f'/api/media/{it["media_id"]}/proxy?w=2000&h=100&{q}', raw=True)
        self.assertEqual(code, 200, jpg[:300])
        self.assertEqual(hdr.get('X-Image-Size'), f'32000,{8 * H}')


class Every28000PxPassAndWriter(IntegBase):
    def test_every_writer_on_an_rgba_input_on_a_64_gb_pc(self):
        svc = self.service(settings={'ram_cap_gb': 59.0})
        src = strip_input(self.d / 'in', 'alpha.png', 3500, 64, alpha=True)
        W, H = 28000, 512
        want_a = np.asarray(Image.open(src).getchannel('A').resize((W, H), Image.LANCZOS))
        for fmt in ('png8', 'png16', 'tiff16', 'jpeg'):
            with self.subTest(fmt=fmt):
                job, it = self.run_one(svc, src, {'scale': 8, 'output_format': fmt})
                self.assertEqual(it['plan']['banded']['machine_class'], 'pc64')
                self.assertFalse(any(s['split_finish'] for s in it['plan']['stages']))
                if fmt == 'png8':
                    with Image.open(it['output']) as im:
                        self.assertEqual((im.size, im.mode), ((W, H), 'RGBA'))
                        np.testing.assert_array_equal(np.asarray(im)[..., 3], want_a)
                elif fmt == 'png16':
                    arr, depth, _ = read_png16(it['output'])
                    self.assertEqual((arr.shape, depth), ((H, W, 4), 16))
                elif fmt == 'tiff16':
                    self.assertEqual(read_tiff16(it['output'])[0].shape[:2], (H, W))
                else:
                    with Image.open(it['output']) as im:
                        self.assertEqual((im.size, im.mode), ((W, H), 'RGB'))


class ResumeAfterTheEngineDied(IntegBase):
    def test_the_finish_prompt_of_pass_2(self):
        env = {'CU_FAKE_STAGE_SECONDS': '0.2', 'CU_FAKE_FAULT': 'crash@1'}         # prompt B of pass 2 crashes
        H = split_strip_height()
        self.assertIsNotNone(H)
        svc = self.service(env=env)
        mid = self.add(svc, [strip_input(self.d / 'in', 'wide.png', 4000, H)])['items'][0]['id']
        job = self.job(svc, [mid], {'scale': 8})
        self.assertTrue(all(s['split_finish'] for s in job['items'][0]['plan']['stages']))      # the premise
        self.assertEqual(svc.proc.wait(240), 70)
        svc.out.close()
        svc2 = self.service(env=env)
        j2 = svc2.wait_job(job['id'], all_done, timeout=300)
        self.assertEqual(j2['items'][0]['state'], 'done', j2)
        with Image.open(j2['items'][0]['output']) as im:
            self.assertEqual(im.size, (32000, 8 * H))
        self.assertEqual(len([r for r in svc2.renders() if r['prefix'].endswith('_s1_a')]), 1)
        self.assertIn('banded_checkpoint_resume', [e.get('event') for e in svc2.log_lines()])


class TheForceSwitch(IntegBase):
    def test_a_classic_plan_through_the_large_image_engine(self):
        svc = self.service()
        job, it = self.run_one(svc, strip_input(self.d / 'in', 'small.png', 640, 480), {'scale': 2},
                               dev_force_engine='banded')
        self.assertTrue(it['plan']['banded']['forced'])
        with Image.open(it['output']) as im:
            self.assertEqual(im.size, (1280, 960))


if __name__ == '__main__':
    unittest.main()
