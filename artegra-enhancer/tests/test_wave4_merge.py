"""5.0.2 build wave 4: what the merge of the service and proof packages relies on, checked in process (sizes only).

- contracts.restart, both halves: the proof harness starts each Large-image pass in the engine process the proof's one rule
  gives (tools/proof/registration.worker_layout: a new worker before a pass whose plan sets fresh_worker once the current one
  has run a prompt, and before a split stage's part B), and the service, with wave 4's stop at the image's end merged, sends
  each pass's prompts to exactly those engine processes (the recording client of tests/test_service4_engine_release.py),
  with the split finish on the workstation class and without it on a 64 GB PC's class.
- contracts.restart_record, as built (the names the merge reconciles): the service logs its stop after a Large-image image,
  and the fallback restart before the next image's first prompt, as event 'banded_engine_released' (why 'large_image_ended'
  or 'previous_job'); the fallback's 'restart_before' (why 'previous_job') is on the first prompt's stage entry of a
  Large-image image, and at item level (timings['restart_before'], with the pass 'index') for a Classic image, because the
  registered G0c hunk of Runner._run_stage writes a Classic stage's entry. The proof's split-memory reader
  (tools/proof/records.l3r_from_item, l3r_from_log and l3r_marks) reads the same records with and without them: it never
  takes a wave-4 record for a split record.
- contracts.keep_planes, as the proof's service driver reads it (the merge's one product fix, service/runner.py
  Runner._keep_before_done): when a developer build's Large-image image reads done, every pass's stage file is already in
  kept/ and in the 'kept' list of the timings the done write carries. Before it, the stage files moved to kept/ only in the
  work folder's cleanup after the done write, and the real-service KeepPlanes test (tests/service/test_service3_service.py)
  read kept/ in that moment once in the merge's full suite."""
import json
import unittest

from unittest import mock

from service import banded_runner, build_channel
from tools.proof import records, registration
import tests.test_integ_large_image_job as J
import tests.test_service3_g1u as G
import tests.test_service3_keep_planes as K
import tests.test_service4_engine_release as E
import tests.test_service4_stop_fails as S

WAVE4_EVENT = banded_runner.RELEASED_EVENT


def segments(stages):
    """The (stage, part) segments of a Large-image plan in the order the service sends their prompts."""
    return [[int(s['index']), p] for s in stages for p in (('A', 'B') if s.get('split_finish') else (None,))]


def engine_layout(owner, stages):
    """The segments each engine process ran, in order, from the prompts the recording client saw for this image."""
    sent = [r['engine'] for r in E.Recorder.log if r['owner'] == owner and r['banded']]
    segs = segments(stages)
    assert len(sent) == len(segs), (len(sent), segs)
    out, last = [], None
    for eng, seg in zip(sent, segs):
        if eng != last:
            out.append([])
            last = eng
        out[-1].append(seg)
    return out


def without_wave4(item):
    """The item as the proof reader would see it without wave 4's records (restart_before with why 'previous_job')."""
    it = json.loads(json.dumps(item))
    t = it.get('timings') or {}
    if (t.get('restart_before') or {}).get('why') == 'previous_job':
        t.pop('restart_before')
    for e in t.get('stages') or []:
        if (e.get('restart_before') or {}).get('why') == 'previous_job':
            e.pop('restart_before')
    return it


def log_text(svc, drop_wave4=False):
    return '\n'.join(json.dumps(e) for e in svc.events() if not (drop_wave4 and e.get('event') == WAVE4_EVENT))


def plan_marks(plan):
    """The plan's stages as the proof's marks carry them (a generous bound: only which records are read is compared)."""
    return {'stages': [{'index': s['index'], 'split_finish': bool(s.get('split_finish')), 'peak_upper_gb': 1e6}
                       for s in plan['stages']]}


class Reads:
    def check_reader(self, svc, item, plan):
        self.assertEqual(records.l3r_from_item(item), records.l3r_from_item(without_wave4(item)))
        self.assertEqual(records.l3r_from_log(log_text(svc)), records.l3r_from_log(log_text(svc, True)))
        got = records.l3r_marks(item, log_text(svc), plan_marks(plan))
        base = records.l3r_marks(without_wave4(item), log_text(svc, True), plan_marks(plan))
        self.assertEqual({k: got[k] for k in ('pass', 'expected_stages', 'missing_stages', 'unexpected_stages',
                                               'duplicate_stages', 'log_agrees', 'source')},
                         {k: base[k] for k in ('pass', 'expected_stages', 'missing_stages', 'unexpected_stages',
                                               'duplicate_stages', 'log_agrees', 'source')})
        self.assertEqual(len(records.l3r_from_item(item)), sum(1 for s in plan['stages'] if s.get('split_finish')))


class TheRestartContractBothHalves(Reads, E.Base):
    def run_one(self, svc, w, h, settings):
        mid = svc.add(J.strip_input(self.td / 'in', 'wide.png', w, h))
        job = svc.job([mid], settings)
        plan = job['items'][0]['plan']
        self.assertEqual(plan.get('engine'), 'banded', plan)
        self.assertEqual(svc.run_all(), [])
        it = self.done(svc, job['id'])
        return self.key(job), it, plan

    def test_split_passes_on_the_workstation_class(self):
        svc = self.service(ram_gb=J.RAM_WS)
        H = self.split_height(svc)
        owner, it, plan = self.run_one(svc, J.SPLIT_WIDTH, H, dict(J.PROTECT_ALL, scale=J.SPLIT_FACTOR))
        self.assertTrue(all(s['split_finish'] for s in plan['stages']))               # the premise
        self.assertEqual([bool(s.get('fresh_worker')) for s in plan['stages']], [False, True, True])
        layout = registration.worker_layout(plan['stages'])
        self.assertEqual(layout, [[[0, 'A']], [[0, 'B']], [[1, 'A']], [[1, 'B']], [[2, 'A']], [[2, 'B']]])
        self.assertEqual(engine_layout(owner, plan['stages']), layout)
        rel = [e for e in self.released(svc) if e['job'] == owner[0]]
        self.assertEqual([e['data']['why'] for e in rel], ['large_image_ended'])
        self.check_reader(svc, it, plan)

    def test_one_prompt_passes_on_a_64_gb_pc(self):
        svc = self.service()                                     # E.Base: a 64 GB PC's class
        owner, it, plan = self.run_one(svc, 3500, 64, {'scale': 8})
        self.assertFalse(any(s['split_finish'] for s in plan['stages']))              # the premise
        layout = registration.worker_layout(plan['stages'])
        self.assertEqual(layout, [[[0, None]], [[1, None]], [[2, None]]])
        self.assertEqual(engine_layout(owner, plan['stages']), layout)
        self.check_reader(svc, it, plan)


class TheRestartRecordAsBuilt(Reads, S.Base):
    """The fallback's records (a stop after a Large-image image that failed, then works): the next Classic image carries
    restart_before at item level, the next Large-image image on its first prompt's stage entry; both why 'previous_job'."""

    def test_a_classic_image_after_a_kept_engine(self):
        f = self.fault('a')
        svc = self.service()
        key, old = self.kept_after_large(svc, f)
        f.on = False
        _, c = self.classic(svc, 'c.png', 256, 192, seed=4)
        self.assertEqual(svc.run_all(S.RUN_S), [])
        it = self.done(svc, c['id'])
        rb = it['timings'].get('restart_before') or {}
        self.assertEqual((rb.get('why'), rb.get('index')), ('previous_job', 0))
        self.assertFalse(any('restart_before' in (e or {}) for e in it['timings'].get('stages') or []))
        ev = [e for e in self.released(svc) if e['data'].get('why') == 'previous_job']
        self.assertEqual([(e['job'], e['data']['stopped']) for e in ev], [(c['id'], True)])
        self.check_reader(svc, it, {'stages': []})

    def test_a_large_image_image_after_a_kept_engine(self):
        f = self.fault('a')
        svc = self.service()
        key, old = self.kept_after_large(svc, f)
        f.on = False
        _, big = self.large(svc, 'next.png', seed=6)
        self.assertEqual(svc.run_all(S.RUN_S), [])
        it = self.done(svc, big['id'])
        first = next(x for x in it['timings']['stages'] if x.get('index') == 0)
        self.assertEqual((first.get('restart_before') or {}).get('why'), 'previous_job')
        self.assertNotIn('restart_before', it['timings'])
        self.check_reader(svc, it, big['items'][0]['plan'])


class TheKeptRecordIsCompleteWhenTheImageReadsDone(G.GlobalsRestored, J.Base):
    ram_gb = J.RAM_WS

    def setUp(self):
        super().setUp()
        p = mock.patch.object(build_channel, 'CHANNEL', 'dev')
        p.start()
        self.addCleanup(p.stop)

    def run_kept(self, keep_planes=True, w=4000, h=None, scale=8):
        svc = self.service()
        if h is None:
            h = J.split_strip_height(float(svc.settings.get()['ram_cap_gb']), service=False)
            self.assertIsNotNone(h)
        mid = svc.add(J.strip_input(self.td / 'in', f'img{w}x{h}.png', w, h))
        extra = {'dev_keep_planes': True} if keep_planes else {}
        job, _ = svc.runner.create_job(K.body(svc, mid, {'scale': scale}, **extra))
        work = svc.cfg.work_dir / job['id'] / 'i001'
        seen, real = [], svc.store.update_item

        def update(jid, iid, **kw):              # what a reader sees at the done write
            if kw.get('state') == 'done' and jid == job['id']:
                kept = work / 'kept'
                seen.append({'kept_dir': sorted(p.name for p in kept.iterdir()) if kept.is_dir() else None,
                             'work_stage_files': sorted(p.name for p in work.glob('stage*.u8')),
                             'timings_kept': sorted((kw.get('timings') or {}).get('kept') or [])})
            return real(jid, iid, **kw)
        svc.store.update_item = update
        self.assertEqual(svc.run_all(), [])
        it = self.done(svc, job['id'])
        self.assertEqual(len(seen), 1)
        return svc, job, it, work, seen[0]

    def test_every_stage_file_is_kept_and_recorded_at_the_done_write(self):
        svc, job, it, work, at_done = self.run_kept()
        kept = work / 'kept'
        names = ['s0', 's1', 's2', 'stage0.u8', 'stage1.u8', 'stage2.u8']
        self.assertEqual(at_done['kept_dir'], names)
        self.assertEqual(at_done['work_stage_files'], [])
        self.assertTrue({str(kept / f'stage{k}.u8') for k in range(3)} <= set(at_done['timings_kept']))
        # after the cleanup, as before: kept/ alone stays, and the item's record lists everything in it once
        self.assertEqual(sorted(p.name for p in work.iterdir()), ['kept'])
        self.assertEqual(sorted(p.name for p in kept.iterdir()), names)
        self.assertEqual(sorted(it['timings']['kept']), sorted(str(kept / n) for n in names))

    def test_a_job_without_the_setting_keeps_nothing_and_cleans_up_after_done(self):
        svc, job, it, work, at_done = self.run_kept(keep_planes=False)
        self.assertIsNone(at_done['kept_dir'])
        self.assertEqual(len(at_done['work_stage_files']), 3)    # as in 5.0.2 before the merge: removed after the done write
        self.assertNotIn('kept', it['timings'])
        self.assertFalse(work.exists())


if __name__ == '__main__':
    unittest.main()
