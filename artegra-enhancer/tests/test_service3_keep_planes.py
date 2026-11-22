"""5.0.2 build wave 3, the developer keep-planes setting (BUILD-WAVE-3 contracts.keep_planes): a job body field
dev_keep_planes: true, accepted only by a developer build (a release build refuses it at submit in plain words, as G0g);
each Large-image stage's plane folder moves to <work>/<job>/<item>/kept/s<k>/ and its stage file to kept/stage<k>.u8, the
kept paths are recorded in the item's timings and the log, the disk check counts them, and kept/ stays until the item is
cleared (the done item, a resume and the housekeeping sweep keep it). Classic jobs ignore it.

In this process on the fake engine (tests/test_integ_large_image_job.py's harness). Sizes and synthetic pictures only."""
import unittest
import uuid
from unittest import mock

from engine import planes
from service import banded_runner, build_channel
from service.errors import ApiError
import tests.test_integ_large_image_job as J
from tests.service.helpers import split_strip_height
import tests.test_service3_g1u as G


def body(svc, mid, settings, **extra):
    return dict({'client_request_id': uuid.uuid4().hex, 'media_ids': [mid], 'settings': settings,
                 'output_dir': str(svc.cfg.default_output_dir)}, **extra)


class TheSwitch(G.GlobalsRestored, J.Base):
    ram_gb = J.RAM_WS

    def test_a_release_build_refuses_it_at_submit(self):
        svc = self.service()
        mid = svc.add(J.strip_input(self.td / 'in', 'wide.png', 4000, 64))
        with mock.patch.object(build_channel, 'CHANNEL', 'release'):
            with self.assertRaises(ApiError) as e:
                svc.runner.create_job(body(svc, mid, {'scale': 8}, dev_keep_planes=True))
        self.assertEqual((e.exception.status, e.exception.code), (400, 'dev_setting'))
        self.assertEqual(str(e.exception), build_channel.DEV_SETTING_REFUSED)
        self.assertEqual(list(svc.store.job_ids()), [])
        self.assertIn('dev_setting_refused', [x['event'] for x in svc.events()])

    def test_only_true_or_false(self):
        svc = self.service()
        mid = svc.add(J.strip_input(self.td / 'in', 'wide.png', 4000, 64))
        with mock.patch.object(build_channel, 'CHANNEL', 'dev'):
            with self.assertRaises(ApiError) as e:
                svc.runner.create_job(body(svc, mid, {'scale': 8}, dev_keep_planes='yes'))
        self.assertEqual(e.exception.status, 400)

    def test_the_default_configuration_never_sets_it(self):
        from service import settings
        import json
        self.assertNotIn('dev_keep_planes', json.dumps(settings.Settings.__init__.__defaults__ or ()))
        for p in (J.ROOT / 'service').glob('*.py'):
            if p.name in ('runner.py', 'build_channel.py', 'banded_runner.py'):
                continue
            self.assertNotIn('dev_keep_planes', p.read_text(encoding='utf8'), p.name)


class KeptInADeveloperBuild(G.GlobalsRestored, J.Base):
    ram_gb = J.RAM_WS

    def setUp(self):
        super().setUp()
        p = mock.patch.object(build_channel, 'CHANNEL', 'dev')
        p.start()
        self.addCleanup(p.stop)

    def keep_job(self, svc, w=4000, h=None, scale=8):
        if h is None:                         # a strip whose every pass is split here (contracts.split_premise)
            h = split_strip_height(float(svc.settings.get()['ram_cap_gb']), service=False)
            self.assertIsNotNone(h)
        mid = svc.add(J.strip_input(self.td / 'in', f'img{w}x{h}.png', w, h))
        job, _ = svc.runner.create_job(body(svc, mid, {'scale': scale}, dev_keep_planes=True))
        return job

    def test_every_stage_planes_and_stage_file_stay_after_done(self):
        svc = self.service()
        job = self.keep_job(svc)
        self.assertTrue(svc.store.get(job['id'])['dev_keep_planes'])
        plan = job['items'][0]['plan']
        self.assertTrue(all(s['split_finish'] for s in plan['stages']))
        self.assertEqual(svc.run_all(), [])
        it = self.done(svc, job['id'])
        work = svc.cfg.work_dir / job['id'] / 'i001'
        kept = work / 'kept'
        self.assertEqual(sorted(p.name for p in work.iterdir()), ['kept'])            # everything else is gone
        names = sorted(p.name for p in kept.iterdir())
        self.assertEqual(names, ['s0', 's1', 's2', 'stage0.u8', 'stage1.u8', 'stage2.u8'])
        for k, st in enumerate(plan['stages']):
            self.assertTrue((kept / f's{k}' / 'input.plane').is_file())
            self.assertTrue((kept / f's{k}' / 'checkpoint.json').is_file())             # a split stage's checkpoint
            ow, oh = st['output_size']
            planes.validate(kept / f'stage{k}.u8', shape=(oh, ow, 3), dtype='u8', check_sha=True)
        rec = set(it['timings']['kept'])
        self.assertEqual(rec, {str(kept / n) for n in names})
        self.assertIn('dev_planes_kept', [e['event'] for e in svc.events()])
        removed = svc.runner.sweep()                                                    # the sweep keeps it
        self.assertEqual(removed['work'], 0)
        self.assertTrue(kept.is_dir())

    def test_a_resume_keeps_the_earlier_passes(self):
        svc = self.service('state-r')
        job = self.keep_job(svc)
        J.InProcessFake.die_at = (1, 'B')
        self.assertEqual(len(svc.run_all()), 1)
        kept = svc.cfg.work_dir / job['id'] / 'i001' / 'kept'
        self.assertTrue((kept / 's0').is_dir())
        svc2 = self.service('state-r')
        with mock.patch.object(build_channel, 'CHANNEL', 'dev'):
            self.assertEqual(svc2.run_all(), [])
        self.done(svc2, job['id'])
        self.assertEqual(sorted(p.name for p in kept.iterdir()),
                         ['s0', 's1', 's2', 'stage0.u8', 'stage1.u8', 'stage2.u8'])

    def test_the_disk_check_counts_them(self):
        svc = self.service()
        job = self.keep_job(svc)
        plan = job['items'][0]['plan']
        seen = []
        real = svc.runner._stage_disk_check

        def spy(jid, iid, work, need):
            seen.append(need)
            return real(jid, iid, work, need)
        with mock.patch.object(svc.runner, '_stage_disk_check', spy):
            self.assertEqual(svc.run_all(), [])
        want = []
        for k, st in enumerate(plan['stages']):
            (pw, ph), (rw, rh), (ow, oh) = st['padded_size'], st['render_size'], st['output_size']
            want.append(planes.disk_need(pw * ph, rw * rh, ow * oh) + banded_runner.kept_need(plan, k))
        self.assertEqual(seen, want)
        self.assertGreater(seen[0], planes.disk_need(*(a * b for a, b in (plan['stages'][0]['padded_size'],
                                                                          plan['stages'][0]['render_size'],
                                                                          plan['stages'][0]['output_size']))))

    def test_a_job_without_it_keeps_nothing(self):
        svc = self.service()
        mid = svc.add(J.strip_input(self.td / 'in', 'wide.png', 4000,
                                    split_strip_height(float(svc.settings.get()['ram_cap_gb']), service=False)))
        job = svc.job([mid], {'scale': 8})
        self.assertEqual(svc.run_all(), [])
        self.done(svc, job['id'])
        self.assertFalse((svc.cfg.work_dir / job['id']).exists())

    def test_a_classic_job_ignores_it(self):
        svc = self.service()
        job = self.keep_job(svc, 640, 480, 2)
        self.assertNotEqual(job['items'][0]['plan'].get('engine'), 'banded')
        self.assertEqual(svc.run_all(), [])
        self.done(svc, job['id'])
        self.assertFalse((svc.cfg.work_dir / job['id']).exists())


if __name__ == '__main__':
    unittest.main()
