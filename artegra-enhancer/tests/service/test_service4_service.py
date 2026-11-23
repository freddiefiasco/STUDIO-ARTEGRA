"""5.0.2 build wave 4, service package item 1, through a real developer-build service on the fake engine: the engine a
Large-image image used is stopped when that image ends (event 'banded_engine_released', contracts.restart_record), so the
next image and a protected-area preview start a fresh engine; a session that sends no Large-image prompt makes no extra
engine stop or start. With the fake engine in its own process (CU_FAKE_PROCESS, a real shared Windows Job), the stop's
commit record is measured. Sizes and synthetic pictures only.

WRITTEN, NOT RUN in the service package's worktree (it starts a service on the test ports 18950-18969, which v6's suite
binds on the same machine); the merge role runs it first (adds.merge_runs_first)."""
import sys
import unittest

from service import banded_runner
from tests.service.test_banded_service import DEV, strip_input
from tests.service.test_integration import Base, all_done

RELEASED = 'banded_engine_released'


class AfterALargeImageImage(Base):
    env = DEV

    def run_one(self, svc, path, scale):
        mid = self.add(svc, [path])['items'][0]['id']
        job = self.job(svc, [mid], {'scale': scale})
        job = svc.wait_job(job['id'], all_done, timeout=240)
        self.assertEqual(job['items'][0]['state'], 'done', job['items'][0])
        return mid, job

    def events(self, svc, *names):
        return [e for e in svc.log_lines() if e.get('event') in names]

    def test_the_next_image_and_a_preview_start_a_fresh_engine(self):
        svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '0.2'})
        _, big = self.run_one(svc, strip_input(self.d / 'in', 'wide.png', 3500, 64), 8)
        self.assertEqual(big['items'][0]['plan'].get('engine'), 'banded')
        rel = self.events(svc, RELEASED)
        self.assertEqual(len(rel), 1)
        self.assertEqual((rel[0]['data']['why'], rel[0]['data']['gpus'], rel[0]['data']['job']),
                         ('large_image_ended', [0], big['id']))
        for key in ('commit_before_gb', 'commit_after_gb', 'commit_fall_gb', 'commit_check'):
            self.assertIn(key, rel[0]['data'])
        stops = [e for e in self.events(svc, 'worker_stopped') if e['data'].get('reason') == banded_runner.RELEASE_REASON]
        self.assertEqual(len(stops), 1)
        small_mid, small = self.run_one(svc, strip_input(self.d / 'in', 'small.png', 640, 480), 2)
        self.assertNotEqual(small['items'][0]['plan'].get('engine'), 'banded')
        lines = [(e.get('event'), e.get('item'), e.get('job')) for e in svc.log_lines()
                 if e.get('event') in (RELEASED, 'worker_starting', 'prompt_queued', 'stage_start')]
        i_rel = next(i for i, x in enumerate(lines) if x[0] == RELEASED)
        i_first = next(i for i, x in enumerate(lines) if x[2] == small['id'] and x[0] in ('prompt_queued', 'stage_start'))
        self.assertIn('worker_starting', [x[0] for x in lines[i_rel:i_first]])      # a fresh engine for the next image
        # a second Large-image image, then a protected-area preview: a fresh engine for the preview
        self.run_one(svc, strip_input(self.d / 'in', 'wide2.png', 3500, 64, seed=2), 8)
        n_start = len(self.events(svc, 'worker_starting'))
        code, m, _ = svc.post('/api/mask-preview', {'media_id': small_mid, 'protect': ['people']})
        self.assertEqual(code, 200, m)
        self.assertEqual(len(self.events(svc, 'worker_starting')), n_start + 1)
        self.assertEqual(len(self.events(svc, RELEASED)), 2)

    @unittest.skipUnless(sys.platform == 'win32', 'the commit record needs a real Windows Job')
    def test_the_stop_is_measured_in_the_shared_job(self):
        svc = self.service(env={'CU_FAKE_PROCESS': '1', 'CU_FAKE_STAGE_SECONDS': '0.2', 'CU_FAKE_HOLD_MB': '512'})
        self.run_one(svc, strip_input(self.d / 'in', 'wide.png', 3500, 64), 8)
        rel = self.events(svc, RELEASED)
        self.assertEqual(len(rel), 1)
        d = rel[0]['data']
        self.assertEqual(d['commit_check'], 'passed', d)
        self.assertGreaterEqual(d['stopped_worker_last_commit_gb'], 0.5, d)          # the fake engine's 512 MiB
        self.assertGreaterEqual(d['commit_fall_gb'], d['stopped_worker_last_commit_gb'] - banded_runner.COMMIT_EPS_GB, d)
        self.assertLess(d['commit_after_gb'], d['commit_before_gb'] - 0.45, d)


class AClassicOnlySession(Base):
    env = DEV

    def test_no_extra_engine_stop_or_start(self):
        svc = self.service(env={'CU_FAKE_STAGE_SECONDS': '0.2'})
        mids = []
        for name, seed in (('a.png', 1), ('b.png', 2)):
            mid = self.add(svc, [strip_input(self.d / 'in', name, 640, 480, seed=seed)])['items'][0]['id']
            mids.append(mid)
            job = svc.wait_job(self.job(svc, [mid], {'scale': 2})['id'], all_done, timeout=120)
            self.assertEqual(job['items'][0]['state'], 'done', job['items'][0])
            if seed == 1:
                code, m, _ = svc.post('/api/mask-preview', {'media_id': mid, 'protect': ['people']})
                self.assertEqual(code, 200, m)
        events = [e.get('event') for e in svc.log_lines()]
        self.assertEqual(events.count('worker_starting'), 1)
        self.assertEqual(events.count('worker_stopped'), 0)
        self.assertNotIn(RELEASED, events)


if __name__ == '__main__':
    unittest.main()
