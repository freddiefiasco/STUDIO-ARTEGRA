"""Halo Reduction (beta) through the service with the fake engine (the in-process service of tests/test_integ_large_image_job.py):
a job that sets halo_reduction runs it on the Large-image engine's last pass only. A 4x job (a developer build's force
switch: the Classic plan's two passes through the Large-image engine, every Large-image plan counting the banded finish)
with the setting on and its planes kept: the plan carries halo_fix 'edge3f' and its last pass dehalo_f 4.0; the last pass's
finish prompt has dehalo, the anchor plane and anchor_factor 4.0, the first pass's has none; the kept anchor plane holds the
bytes of round 2's anchor (the original resampled to that pass's input with Pillow's bilinear, reflect-padded); the sidecar
names the halo constant. A Classic engine job with the setting on keeps its Classic plan and graph and says in its notes and
sidecar that its finish is 5.0.1's. Sizes and synthetic images only."""
import json
import unittest
import uuid
from pathlib import Path
from unittest import mock

import numpy as np
from PIL import Image

from engine import banded_plan, planes
from service import build_channel, images
from service import runner as R
from tests.test_integ_large_image_job import Base, strip_input


def finishes(svc):
    """[(prefix, finish inputs)] of every CUFinishBanded the engine was given."""
    out = []
    for g in svc.prompts():
        for n in g.values():
            if n['class_type'] == 'CUFinishBanded':
                out.append((n['inputs']['filename_prefix'], n['inputs'], g))
    return out


class TheOptionThroughTheService(Base):
    def test_a_4x_job_runs_it_on_its_last_pass_with_the_anchor(self):
        svc = self.service()
        src = self.td / 'in'
        mid = svc.add(strip_input(src, 'card.png', 640, 480))
        body = {'client_request_id': uuid.uuid4().hex, 'media_ids': [mid], 'settings': {'scale': 4, 'halo_reduction': True},
                'output_dir': str(svc.cfg.default_output_dir), 'dev_force_engine': 'banded', 'dev_keep_planes': True}
        with mock.patch.object(banded_plan, 'BXF_AVAILABLE', True), mock.patch.object(build_channel, 'CHANNEL', 'dev'):
            job, _ = svc.runner.create_job(body)
            plan = job['items'][0]['plan']
            self.assertEqual(plan['engine'], 'banded')
            self.assertEqual(plan['banded']['halo_fix'], 'edge3f')
            self.assertEqual([s.get('dehalo_f') for s in plan['stages']], [None, 4.0])
            self.assertNotIn('dehalo_f', plan['stages'][0])
            self.assertEqual(job['items'][0]['notes'], [])
            self.assertEqual(svc.run_all(), [])
        it = self.done(svc, job['id'])
        fins = finishes(svc)
        by_stage = {p.rsplit('_s', 1)[1]: inp for p, inp, _ in fins}
        self.assertEqual(sorted(by_stage), ['0', '1'])
        self.assertFalse({'dehalo', 'anchor', 'anchor_factor'} & set(by_stage['0']))
        last = by_stage['1']
        self.assertEqual((last['dehalo'], last['anchor_factor']), ('edge3f', 4.0))
        g = next(g for p, inp, g in fins if p.endswith('_s1'))
        anchor_node = g[last['anchor'][0]]
        self.assertEqual(anchor_node['class_type'], 'CUPlaneInput')
        self.assertTrue(anchor_node['inputs']['plane'].endswith('planes/s1/anchor.plane'), anchor_node['inputs']['plane'])
        # the kept anchor plane: round 2's anchor bytes
        st = plan['stages'][1]
        kept = sorted((svc.cfg.work_dir / job['id'] / it['id']).rglob('anchor.plane'))
        self.assertEqual(len(kept), 1, kept)
        with Image.open(src / 'card.png') as im:
            orig = np.asarray(im.convert('RGB'))
        iw, ih = st['input_size']
        want = images.pad_reflect(np.asarray(Image.fromarray(orig).resize((iw, ih), Image.BILINEAR)), tuple(st['padded_size']))
        got = planes.validate(kept[0]).read_rows(0, st['padded_size'][1])
        self.assertEqual(got.shape, want.shape)
        self.assertEqual(int(np.count_nonzero(got != want)), 0)
        side = json.loads(Path(it['sidecar']).read_text(encoding='utf8'))
        self.assertEqual(side['engine']['halo_fix'], 'edge3f')
        self.assertIs(side['effective']['halo_reduction'], True)

    def test_a_classic_job_keeps_its_classic_plan_and_says_so(self):
        svc = self.service()
        mid = svc.add(strip_input(self.td / 'in', 'small.png', 640, 480))
        on = svc.job([mid], {'scale': 2, 'halo_reduction': True})
        off = svc.job([mid], {'scale': 2})
        a, b = on['items'][0], off['items'][0]
        self.assertEqual(a['plan'], b['plan'])
        self.assertNotIn('engine', a['plan'])
        self.assertEqual(a['notes'], [R.HALO_CLASSIC_NOTE])
        self.assertEqual(b['notes'], [])
        self.assertEqual(svc.run_all(), [])
        ga = [g for g in svc.prompts()]
        self.assertFalse(any('dehalo' in n['inputs'] for g in ga for n in g.values()))
        side = json.loads(Path(self.done(svc, on['id'])['sidecar']).read_text(encoding='utf8'))
        self.assertIn(R.HALO_CLASSIC_NOTE, side['notes'])
        self.assertNotIn('halo_fix', json.dumps(side['engine']))

    def test_a_setting_that_is_not_true_or_false_is_refused_at_submit(self):
        svc = self.service()
        mid = svc.add(strip_input(self.td / 'in', 'small.png', 640, 480))
        with self.assertRaises(R.ApiError) as cm:
            svc.job([mid], {'scale': 2, 'halo_reduction': 'yes'})
        self.assertEqual(cm.exception.code, 'bad_settings')
        self.assertIn('Halo Reduction (beta)', cm.exception.message)


if __name__ == '__main__':
    unittest.main()
