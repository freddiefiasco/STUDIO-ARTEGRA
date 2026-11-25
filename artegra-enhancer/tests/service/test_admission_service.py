"""Admission, deadlines and the Large-image stage flow through a real service on the fake engine (engine design
ENGINE-DESIGN.md 2.8, 2.10, 8.1, 8.3; gates G8 and B14): graphics-memory refusals with their reasons on 8, 12, 16 and 24 GB
cards and none on 32 GB; the Large-image VRAM classes; the card factor from the class table and then from spot's timing
record; the split finish's restart path and its record; resume from the sub-stage checkpoint of each pass and the refusal
of a damaged one, at 32,000 px. Sizes and synthetic images only.

WRITTEN, NOT RUN in the admission package's worktree (it starts services on the test ports; the merge role runs it first).
Until the merge role regenerates node_pack/MANIFEST-banded.json (claude_banded gains dev_vram.py), the banded pack does not
verify in a package worktree and the Large-image tests here fail at the pack check by design."""
import json
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from service import banded_runner, card_factor, runner as runner_mod
from engine import vram_model
from tests.service.helpers import gradient, split_strip_height
from tests.service.test_banded_service import DEV, strip_input
from tests.service.test_integration import Base, all_done

Image.MAX_IMAGE_PIXELS = None


def square(d, name, side, seed=4):
    d.mkdir(parents=True, exist_ok=True)
    Image.fromarray(gradient(side, side, seed)).save(d / name)
    return d / name


class ClassicRefusals(Base):
    """5.0.1 refuses no plan for graphics memory, and neither does 5.0.2's Classic engine (26 Nov 2026): on an 8 GB card the
    protect-on 2x of 4000 x 4000 takes the lean SAM step and runs (WRITTEN, NOT RUN by the small-card fix: it starts a
    service)."""

    def test_an_8_gb_card_runs_what_5_0_1_runs(self):
        svc = self.service(env={'CU_FAKE_GPU_MEM_GB': '7.99', 'CU_FAKE_STAGE_SECONDS': '0.2'})
        code, res, _ = svc.post('/api/plan', {'width': 4000, 'height': 4000, 'scale': 2})
        self.assertEqual(code, 200, res)
        self.assertTrue(res['ok'], res)
        self.assertNotIn('vram_refused', res)
        mid = self.add(svc, [square(self.d / 'in', 'big.png', 4000)])['items'][0]['id']
        for settings in ({'scale': 2}, {'scale': 2, 'protect': []}):
            job = self.job(svc, [mid], settings)
            job = svc.wait_job(job['id'], all_done, timeout=120)
            self.assertEqual(job['items'][0]['state'], 'done', (settings, job))

    def test_larger_small_cards_and_a_32_gb_card_accept_it(self):
        for gb in ('11.99', '15.99', '23.99', '31.84'):
            svc = self.service(env={'CU_FAKE_GPU_MEM_GB': gb}, state=f'state-{gb}')
            code, res, _ = svc.post('/api/plan', {'width': 4000, 'height': 4000, 'scale': 2})
            self.assertEqual(code, 200, res)
            self.assertTrue(res['ok'], (gb, res))
            self.assertNotIn('vram_refused', res)
            svc.shutdown()


class LargeImageClasses(Base):
    env = DEV

    def test_the_classes_refuse_in_plain_words(self):
        svc = self.service(env={'CU_FAKE_GPU_MEM_GB': '7.99'})
        code, res, _ = svc.post('/api/plan', {'width': 4000, 'height': 64, 'scale': 8})
        self.assertFalse(res['ok'])
        size = runner_mod.LARGE_NEEDED.format(a='A', w=32000, h=512)          # A10: the refusal names the size
        self.assertEqual(res['reason'], f'{runner_mod.BANDED_8GB} {size}')
        svc.shutdown()
        for gb in ('10.0', '11.0'):                                      # the 8 GB class until the 8 GB emulation passes
            svc = self.service(env={'CU_FAKE_GPU_MEM_GB': gb}, state=f'state-{gb}')
            code, res, _ = svc.post('/api/plan', {'width': 4000, 'height': 64, 'scale': 8})
            self.assertFalse(res['ok'], res)
            self.assertEqual(res['reason'], f'{runner_mod.BANDED_UNPROVEN.format(gb=int(float(gb)))} {size}')
            svc.shutdown()
        # 1,024 MP is over the 300 MP whole finish: the card's render limit shows only where the banded finish is counted
        svc = self.service(env={'CU_FAKE_GPU_MEM_GB': '11.99', 'CU_TEST_BXF_AVAILABLE': '1'}, state='state-12')
        code, res, _ = svc.post('/api/plan', {'width': 4000, 'height': 4000, 'scale': 8})     # 32,000 x 32,000: 1,024 MP
        self.assertFalse(res['ok'], res)
        self.assertTrue(res['reason'].startswith('A 12 GB graphics card can render up to 805 MP with the Large-image '
                                                 'engine; a 32,000 × 32,000 px result needs '), res['reason'])
        code, res, _ = svc.post('/api/plan', {'width': 4000, 'height': 64, 'scale': 8})      # 32,000 x 512 fits
        self.assertTrue(res['ok'], res)


class CardFactorTimes(Base):
    def run_one(self, svc, path, scale=2):
        mid = self.add(svc, [path])['items'][0]['id']
        job = svc.wait_job(self.job(svc, [mid], {'scale': scale})['id'], all_done, timeout=120)
        self.assertEqual(job['items'][0]['state'], 'done', job)
        return job

    def started(self, svc):
        return [e for e in svc.log_lines() if e.get('event') == 'item_started']

    def test_a_12_gb_card_is_measured_at_engine_start_and_its_first_image_runs_at_its_factor(self):
        # 5.0.2 build wave 2 (A4): the card is timed once, right after its engine starts and before the first image's own
        # prompt, so the first image already runs (and has its time said) at the measured factor, not the class table's
        per = card_factor.REF_S_PER_WINDOW * 3
        svc = self.service(env={'CU_FAKE_GPU_MEM_GB': '11.99', 'CU_FAKE_WINDOW_S': repr(per), 'CU_FAKE_STAGE_SECONDS': '0.2'})
        src = strip_input(self.d / 'in', 'a.png', 640, 480)
        job = self.run_one(svc, src)
        cls = card_factor.class_factor({'name': 'Test graphics card 1', 'mem_total_gb': 11.99})
        self.assertNotAlmostEqual(cls, 3.0, places=1)
        events = [e.get('event') for e in svc.log_lines()]
        self.assertEqual(events.count('card_timing_start'), 1)
        self.assertLess(events.index('card_timing_start'), events.index('item_started'))
        self.assertAlmostEqual(self.started(svc)[0]['data']['card_factor'], 3.0, places=2)
        run = job['items'][0]['run']
        self.assertAlmostEqual(run['card_factor'], 3.0, places=2)
        self.assertAlmostEqual(run['factor'], round(0.70 * 3.0, 3), places=2)
        rec = json.loads((self.d / 'state' / 'card_factors.json').read_text(encoding='utf8'))
        self.assertAlmostEqual(rec['cards']['FAKE-0']['s_per_window'], per, places=4)
        job = self.run_one(svc, strip_input(self.d / 'in', 'b.png', 640, 480, seed=2))
        self.assertEqual([e.get('event') for e in svc.log_lines()].count('card_timing_start'), 1)   # measured once
        self.assertAlmostEqual(self.started(svc)[-1]['data']['card_factor'], 3.0, places=2)
        prompts = sorted((self.d / 'state' / 'workers').rglob('fake-prompts/*.json'))
        cal = [p for p in prompts if any(n.get('class_type') == 'SaveImage' and
                                         str(n['inputs'].get('filename_prefix', '')).startswith(card_factor.CAL_PREFIX)
                                         for n in json.loads(p.read_text(encoding='utf8')).values())]
        self.assertEqual(len(cal), 1)                                     # one measurement prompt, a classic graph

    def test_a_32_gb_card_is_1_and_measures_nothing(self):
        svc = self.service(env={'CU_FAKE_WINDOW_S': '0.5', 'CU_FAKE_STAGE_SECONDS': '0.2'})
        job = self.run_one(svc, strip_input(self.d / 'in', 'a.png', 640, 480))
        self.assertNotIn('card_timing_start', [e.get('event') for e in svc.log_lines()])     # no measurement prompt
        self.assertNotIn('card_factor', self.started(svc)[0]['data'])
        self.assertNotIn('card_factor', job['items'][0]['run'])
        self.assertFalse((self.d / 'state' / 'card_factors.json').exists())


class SplitRestartAndResume(Base):
    env = DEV

    def setUp(self):
        super().setUp()
        # 5.0.2 wave 3 (contracts.split_premise): the smallest strip height whose 8x plan splits every pass here, from the
        # planner at run time as the service runs it (a developer build's sizes, no probe table), so a refit of the
        # memory model moves the height, not the premise; the premise is asserted on the plan the job made
        self.H = split_strip_height()
        self.assertIsNotNone(self.H, 'no listed strip height splits every pass of 8x of 4000 x H on this computer')

    def strip(self, d):
        return strip_input(d, 'wide.png', 4000, self.H)

    def split_job(self, svc, mid):
        job = self.job(svc, [mid], {'scale': 8})
        self.assertTrue(all(s['split_finish'] for s in job['items'][0]['plan']['stages']))      # the premise
        return job

    def plane_dir(self, job, k):
        return self.d / 'state' / 'work' / job['id'] / 'i001' / 'planes' / f's{k}'

    L3R = ('job_peak_commit_a_end_gb', 'job_peak_commit_b_start_gb', 'stopped_worker_last_commit_gb', 'commit_fall_gb')

    def test_the_restart_path_records_each_split(self):
        # the fake engine in its own process: its engines run in a real shared Windows Job, which the check reads; each
        # engine holds 512 MiB, so the record shows that commit leaving the Job at every restart
        svc = self.service(env={'CU_FAKE_PROCESS': '1', 'CU_FAKE_STAGE_SECONDS': '0.2', 'CU_FAKE_HOLD_MB': '512'})
        mid = self.add(svc, [self.strip(self.d / 'in')])['items'][0]['id']
        job = svc.wait_job(self.split_job(svc, mid)['id'], all_done, timeout=300)
        it = job['items'][0]
        self.assertEqual(it['state'], 'done', it)
        parts_b = [x for x in it['timings']['stages'] if x.get('part') == 'B']
        self.assertEqual(len(parts_b), 3)
        for x in parts_b:
            for key in self.L3R + banded_runner.L3R_EXTRA:
                self.assertIn(key, x)
            self.assertEqual(x['commit_check'], 'passed', x)
            last = x['stopped_worker_last_commit_gb']
            self.assertGreaterEqual(last, 0.5, x)                         # the engine's 512 MiB, read in its own Job
            self.assertGreaterEqual(x['job_commit_before_gb'], last - 0.01, x)
            self.assertGreaterEqual(x['commit_fall_gb'], last - banded_runner.COMMIT_EPS_GB, x)   # all of it came back
            self.assertLess(x['job_commit_after_gb'], x['job_commit_before_gb'] - 0.45, x)
            self.assertLess(x['commit_wait_s'], banded_runner.COMMIT_SETTLE_S, x)
        events = [e for e in svc.log_lines() if e.get('event') == 'banded_split_commit']
        self.assertEqual(len(events), 3)
        for e in events:
            self.assertEqual(e['data']['commit_check'], 'passed', e)

    def test_the_in_process_fake_engine_records_the_check_as_unmeasured(self):
        svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '0.2'})              # no process, no Job: nothing to read
        mid = self.add(svc, [self.strip(self.d / 'in')])['items'][0]['id']
        job = svc.wait_job(self.split_job(svc, mid)['id'], all_done, timeout=300)
        it = job['items'][0]
        self.assertEqual(it['state'], 'done', it)
        parts_b = [x for x in it['timings']['stages'] if x.get('part') == 'B']
        self.assertEqual(len(parts_b), 3)
        for x in parts_b:
            self.assertEqual(x['commit_check'], 'unmeasured', x)
            self.assertIsNone(x['commit_wait_s'])
            self.assertIsNone(x['commit_fall_gb'])                            # never a fall computed from zeros
            self.assertIsNone(x['stopped_worker_last_commit_gb'])

    def test_resume_from_the_checkpoint_of_each_pass(self):
        for k in (0, 1, 2):
            with self.subTest(stage=k):
                state = f'state-{k}'
                env = {'CU_FAKE_STAGE_SECONDS': '0.2', 'CU_FAKE_FAULT': f'crash@{k}'}     # prompt B of pass k crashes
                svc = self.service(env=env, state=state)
                mid = self.add(svc, [self.strip(self.d / f'in{k}')])['items'][0]['id']
                job = self.split_job(svc, mid)
                self.assertEqual(svc.proc.wait(240), 70)
                svc.out.close()
                ck = self.d / state / 'work' / job['id'] / 'i001' / 'planes' / f's{k}' / 'checkpoint.json'
                self.assertTrue(ck.is_file())
                svc2 = self.service(env=env, state=state)
                j2 = svc2.wait_job(job['id'], all_done, timeout=300)
                self.assertEqual(j2['items'][0]['state'], 'done', j2)
                with Image.open(j2['items'][0]['output']) as im:
                    self.assertEqual(im.size, (32000, 8 * self.H))
                a_runs = [r for r in svc2.renders() if r['prefix'].endswith(f'_s{k}_a')]
                self.assertEqual(len(a_runs), 1)                                   # prompt A of pass k ran once in all
                self.assertTrue(any(e.get('event') == 'banded_checkpoint_resume' for e in svc2.log_lines()))
                svc2.shutdown()

    def test_a_damaged_checkpoint_is_refused_and_the_pass_made_again(self):
        env = {'CU_FAKE_STAGE_SECONDS': '0.2', 'CU_FAKE_FAULT': 'crash@1'}
        svc = self.service(env=env)
        mid = self.add(svc, [self.strip(self.d / 'in')])['items'][0]['id']
        job = self.split_job(svc, mid)
        self.assertEqual(svc.proc.wait(240), 70)
        svc.out.close()
        from engine import planes
        p = self.plane_dir(job, 1) / 'creative.plane'
        with open(p, 'r+b') as f:
            f.seek(planes.DATA_OFFSET + 99)
            b = f.read(1)
            f.seek(planes.DATA_OFFSET + 99)
            f.write(bytes([b[0] ^ 0xFF]))
        svc2 = self.service(env=env)
        j2 = svc2.wait_job(job['id'], all_done, timeout=300)
        self.assertEqual(j2['items'][0]['state'], 'done', j2)
        refused = [e for e in svc2.log_lines() if e.get('event') == 'banded_checkpoint_refused']
        self.assertEqual(len(refused), 1)
        self.assertIn('could not be used (its creative part is missing or damaged)', refused[0]['msg'])
        self.assertEqual(len([r for r in svc2.renders() if r['prefix'].endswith('_s1_a')]), 2)


if __name__ == '__main__':
    unittest.main()
