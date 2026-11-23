"""5.0.2 build wave 4, service package item 1 (admission safety): no image and no protected-area preview starts in an engine
that was sent another image's Large-image prompts.

A Large-image stage's nodes keep memory in their engine after they return (CUFinishBanded up to 6.29 GiB at tier 3 to 73 MP,
the plane nodes about 1.84 GiB), which no plan of another image counts. So an engine that was SENT a Large-image prompt (the
mark is set on send, so a failed, stopped or cancelled prompt counts) runs no prompt of another image, and no protected-area
preview, until it has been stopped and started again. The service stops every engine a Large-image image sent a prompt to
when that image's thread ends, whatever the outcome, before the engine is released: on the success path before
Runner._run_item releases it (the result is saved after that), and in Runner._run_item_safe's finally otherwise. The stop is
logged as event 'banded_engine_released' with its commit fields (BUILD-WAVE-4 contracts.restart_record). The image's own
passes keep contracts.restart unchanged (tests/test_service3_restart.py and tests/test_integ_large_image_job.py).

In this process on the fake engine (tests/test_integ_large_image_job.py's harness), with a client that records every prompt
each engine process is sent. The invariant every test checks: no prompt goes to an engine process that was sent a
Large-image prompt of another image (or of a preview). The identity of a session that sends no Large-image prompt is
checked against tests/fixtures/service4_identity.json, recorded at the base of this package (ecaa61ad) with
CU_SERVICE4_RECORD=1: the same prompts (sha256 of each graph with the job, media and folder names normalised) in the same
order on each card, and the same engine starts and stops. Sizes and synthetic pictures only."""
import hashlib
import json
import os
import re
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from engine import graph_banded
from service import banded_runner, gpu_policy, workers
from service.comfy import PromptRejected
from service.runner import Runner
import tests.test_integ_large_image_job as J
import tests.test_service3_g1u as G

FIXTURE = Path(__file__).resolve().parent / 'fixtures' / 'service4_identity.json'
RECORD = os.environ.get('CU_SERVICE4_RECORD') == '1'
BANDED = frozenset(graph_banded.NODE_SPECS)
OWNER = re.compile(r'cu_(j[0-9a-f]{12})_(i\d+)_s(\d+)')
RELEASED = 'banded_engine_released'
CONTRACT = ('gpus', 'job', 'item', 'why', 'commit_before_gb', 'commit_after_gb', 'commit_fall_gb')


def owner_of(graph):
    """(job, item) of an image's prompt, ('preview', prefix) of a protected-area preview's, from its filename prefix."""
    for node in graph.values():
        v = (node.get('inputs') or {}).get('filename_prefix')
        if isinstance(v, str):
            m = OWNER.search(v)
            if m:
                return (m.group(1), m.group(2))
            if v.startswith('cu_mask_'):
                return ('preview', v)
    return None


class Recorder(J.InProcessClient):
    """The in-process client (one per engine process: the worker makes a new client at every start) that records each prompt
    it is sent, before the engine takes it: the engine, what that engine process was sent before, its owner and whether it
    is a Large-image prompt. hook(graph, owner, banded), when set, runs at that moment (a stop, a cancel, a refusal)."""
    log = []
    hook = None
    gens = {}

    def __init__(self, port):
        super().__init__(port)
        gpu = self.fake.gpu
        Recorder.gens[gpu] = Recorder.gens.get(gpu, 0) + 1
        self.engine = (gpu, Recorder.gens[gpu])
        self.seen = []

    def prompt(self, graph, client_id, prompt_id=None):
        owner = owner_of(graph)
        banded = any(n.get('class_type') in BANDED for n in graph.values())
        Recorder.log.append({'engine': self.engine, 'before': list(self.seen), 'owner': owner, 'banded': banded,
                             'graph': json.loads(json.dumps(graph))})
        self.seen.append((owner, banded))
        if Recorder.hook is not None:
            Recorder.hook(graph, owner, banded)
        return super().prompt(graph, client_id, prompt_id)

    def delete_queued(self, prompt_ids, timeout=None):
        """The runner's interrupt of a stopped, cancelled or interrupted pass (the in-process prompt has already run)."""


def violations():
    """The prompts sent to an engine process that had been sent a Large-image prompt of another image (or preview)."""
    return [(r['owner'], r['engine'], sorted({o for o, b in r['before'] if b and o != r['owner']}, key=str))
            for r in Recorder.log if any(b and o != r['owner'] for o, b in r['before'])]


def first_prompt(owner):
    return next(r for r in Recorder.log if r['owner'] == owner)


class TwoCards(J.InProcessService):
    """The in-process service with two test cards in lanes (split off), or one image shared by both (split forced)."""

    def __init__(self, state, ram_gb, split=False):
        super().__init__(state, ram_gb)
        self.split = split
        self.runner.fake_gpus = 2
        self.worker1 = workers.Worker(1, self.cfg, self.settings, self.log, 'fake')
        self.runner.workers = {0: self.worker, 1: self.worker1}

    def run_all(self, timeout=600):
        with mock.patch.dict(os.environ, {'CU_SPLIT_TEST': '1' if self.split else '0'}):
            if not self.split:
                return super().run_all(timeout)
            with mock.patch.object(gpu_policy, 'plan_topology', lambda *a, **k: gpu_policy.Topology('split', [(0, 1)])):
                return super().run_all(timeout)


class Base(G.GlobalsRestored, J.Base):
    ram_gb = J.RAM_PC

    def setUp(self):
        super().setUp()
        Recorder.log, Recorder.hook, Recorder.gens = [], None, {}
        p = mock.patch.object(workers, 'ComfyClient', Recorder)
        p.start()
        self.engine.append(p)              # stopped first in J.Base.tearDown

    def tearDown(self):
        Recorder.hook = None
        super().tearDown()

    def classic(self, svc, name='small.png', w=320, h=240, seed=1):
        mid = svc.add(J.strip_input(self.td / 'in', name, w, h, seed=seed))
        job = svc.job([mid], {'scale': 2})
        self.assertNotEqual(job['items'][0]['plan'].get('engine'), 'banded')
        return mid, job

    def large(self, svc, name='wide.png', w=3500, h=64, seed=2):
        """8x of 3500 x 64 on a 64 GB PC's class: three one-prompt Large-image passes."""
        mid = svc.add(J.strip_input(self.td / 'in', name, w, h, seed=seed))
        job = svc.job([mid], {'scale': 8})
        self.assertEqual(job['items'][0]['plan'].get('engine'), 'banded')
        return mid, job

    def key(self, job):
        return (job['id'], job['items'][0]['id'])

    def released(self, svc):
        return [e for e in svc.events() if e['event'] == RELEASED]

    def assert_fresh(self, owner):
        """The owner's first prompt went to an engine process that had been sent no prompt."""
        rec = first_prompt(owner)
        self.assertEqual(rec['before'], [], (owner, rec['engine'], rec['before']))


# --- (i) identity: a session that sends no Large-image prompt ------------------------------------------------------------
def canon_sha(graph, names, roots):
    s = json.dumps(graph, sort_keys=True)
    for root in roots:
        s = s.replace(root, '<root>')
    for k, v in names.items():
        s = s.replace(k, v)
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def session_record(svc, td, jobs, media):
    """The session's prompts on each card in order (normalised graph hashes, with the card's engine process number) and
    each engine's starts and stops (event, reason), from the log."""
    names = {j: f'<job{n}>' for n, j in enumerate(jobs, 1)}
    names.update({m: f'<media{n}>' for n, m in enumerate(media, 1)})
    roots = [json.dumps(str(td))[1:-1], str(td).replace('\\', '/'), str(td)]
    prompts = {}
    for r in Recorder.log:
        prompts.setdefault(str(r['engine'][0]), []).append([r['engine'][1], canon_sha(r['graph'], names, roots)])
    life = {}
    for e in svc.events():
        if e['event'] in ('worker_starting', 'worker_stopped'):
            d = e.get('data') or {}
            gpus = ','.join(str(g) for g in (d.get('gpus') or [d.get('gpu')]))
            life.setdefault(gpus, []).append([e['event'], d.get('reason')])
    return {'prompts': prompts, 'engines': life}


class Identity(Base):
    """(i) Classic images one after another in one engine, a protected-area preview between them, and two cards: the same
    prompts in the same order as the base, and no extra engine stop or start; no 'banded_engine_released'."""

    def check(self, name, rec):
        if RECORD:
            data = json.loads(FIXTURE.read_text(encoding='utf8')) if FIXTURE.is_file() else {}
            data[name] = rec
            FIXTURE.write_text(json.dumps(data, indent=1, sort_keys=True) + '\n', encoding='utf8')
            return
        want = json.loads(FIXTURE.read_text(encoding='utf8'))[name]
        self.assertEqual(rec, want)

    def test_classic_images_one_after_another_in_one_engine(self):
        svc = self.service()
        m1, j1 = self.classic(svc, 'a.png', seed=1)
        self.assertEqual(svc.run_all(), [])
        m2, j2 = self.classic(svc, 'b.png', 300, 200, seed=3)
        self.assertEqual(svc.run_all(), [])
        self.done(svc, j1['id']), self.done(svc, j2['id'])
        self.assertEqual(self.released(svc), [])
        self.assertEqual(violations(), [])
        self.assertEqual(svc.worker.starts, 1)
        self.check('one_card', session_record(svc, self.td, [j1['id'], j2['id']], [m1, m2]))

    def test_a_preview_between_classic_images(self):
        svc = self.service()
        m1, j1 = self.classic(svc, 'a.png', seed=1)
        self.assertEqual(svc.run_all(), [])
        self.assertFalse(svc.runner.mask_preview(m1, protect=['people'])['cached'])
        m2, j2 = self.classic(svc, 'b.png', 300, 200, seed=3)
        self.assertEqual(svc.run_all(), [])
        self.done(svc, j2['id'])
        self.assertEqual(self.released(svc), [])
        self.assertEqual(svc.worker.starts, 1)
        self.check('preview_between', session_record(svc, self.td, [j1['id'], j2['id']], [m1, m2]))

    def test_two_cards(self):
        svc = TwoCards(self.td / 'state', self.ram_gb)
        m1 = svc.add(J.strip_input(self.td / 'in', 'a.png', 320, 240, seed=1))
        m2 = svc.add(J.strip_input(self.td / 'in', 'b.png', 300, 200, seed=3))
        j1 = svc.job([m1, m2], {'scale': 2})                # one image on each card
        self.assertEqual(svc.run_all(), [])
        self.assertFalse(svc.runner.mask_preview(m2, protect=['people'])['cached'])
        m3, j2 = self.classic(svc, 'c.png', 256, 192, seed=4)
        self.assertEqual(svc.run_all(), [])
        self.assertEqual([it['state'] for it in svc.store.get(j1['id'])['items']], ['done', 'done'])
        self.done(svc, j2['id'])
        self.assertEqual(sorted(r['engine'][0] for r in Recorder.log if r['owner'] and r['owner'][0] == j1['id']), [0, 1])
        self.assertEqual(self.released(svc), [])
        self.check('two_cards', session_record(svc, self.td, [j1['id'], j2['id']], [m1, m2, m3]))


# --- (ii) after a Large-image image ends each way ------------------------------------------------------------------------
class AfterEachEnding(Base):
    """(ii) After a Large-image image ends (done, failed inside the finish, stopped, cancelled, interrupted), the next
    Classic image, the next Large-image image and a protected-area preview each start in an engine that has been sent no
    prompt, and the stop is logged with its commit fields."""

    def ending(self, how):
        svc = self.service(f'state-{how}')
        _, big = self.large(svc)
        key = self.key(big)
        fired = []

        def hook(graph, owner, banded):
            if how not in ('stopped', 'cancelled', 'interrupted') or owner != key or fired or '_s1' not in json.dumps(graph):
                return
            fired.append(how)
            ctx = svc.runner.ctx[key]
            if how == 'stopped':
                svc.runner.stop_item(*key)
            elif how == 'cancelled':
                svc.runner.cancel_item(*key)
            elif how == 'interrupted':
                ctx.shutdown = True
        Recorder.hook = hook
        real_save = J.InProcessFake._save_planes

        def save(fake, graph, nid, wider=0):
            if (how == 'failed' and graph[nid]['class_type'] == 'CUFinishBanded'
                    and str(graph[nid]['inputs']['filename_prefix']).endswith('_s1') and not fired):
                fired.append(how)
                raise RuntimeError('the finish failed (test)')
            return real_save(fake, graph, nid, wider)
        with mock.patch.object(J.InProcessFake, '_save_planes', save):
            self.assertEqual(svc.run_all(), [])
        Recorder.hook = None
        self.assertEqual(fired, [] if how == 'done' else [how])
        state = svc.item(big['id'])['state']
        want = {'done': 'done', 'failed': 'failed', 'stopped': 'stopped', 'cancelled': 'cancelled',
                'interrupted': 'interrupted'}[how]              # an interrupted image goes on when the app starts again
        self.assertEqual(state, want, svc.item(big['id']).get('message'))
        rel = [e for e in self.released(svc) if e['job'] == key[0]]
        self.assertGreaterEqual(len(rel), 1)
        for e in rel:
            self.assertTrue(set(CONTRACT) <= set(e['data']), e['data'])
            self.assertEqual((e['data']['why'], e['data']['job'], e['data']['item'], e['data']['gpus']),
                             ('large_image_ended', key[0], key[1], [0]))
            self.assertEqual(e['data']['commit_check'], 'unmeasured')        # no shared Job in this process
        # the next Classic image, a protected-area preview and the next Large-image image
        m1, c1 = self.classic(svc)
        self.assertEqual(svc.run_all(), [])
        self.done(svc, c1['id'])
        self.assert_fresh(self.key(c1))
        _, big2 = self.large(svc, 'wide2.png', seed=5)
        self.assertEqual(svc.run_all(), [])
        self.done(svc, big2['id'])
        self.assert_fresh(self.key(big2))
        self.assertFalse(svc.runner.mask_preview(m1, protect=['people'])['cached'])
        self.assert_fresh(next(r['owner'] for r in Recorder.log if r['owner'] and r['owner'][0] == 'preview'))
        self.assertEqual(violations(), [])
        return svc

    def test_done(self):
        svc = self.ending('done')
        # the stop comes after the image's last pass and before its result is saved; one per Large-image image
        ev = [e['event'] for e in svc.events() if e['event'] in ('stage_done', RELEASED, 'item_finishing')]
        self.assertEqual(ev.count(RELEASED), 2)
        i = ev.index(RELEASED)
        self.assertEqual(ev[i - 1], 'stage_done')
        self.assertEqual(ev[i + 1], 'item_finishing')

    def test_failed_inside_the_finish(self):
        self.ending('failed')

    def test_stopped(self):
        self.ending('stopped')

    def test_cancelled(self):
        self.ending('cancelled')

    def test_interrupted(self):
        self.ending('interrupted')


# --- (iii) the mark is set on send; an image that starts while the result is saved --------------------------------------
class TheMarkAndTheSave(Base):
    def test_a_prompt_the_engine_refuses_still_leads_to_the_stop(self):
        """The engine refuses the first Large-image prompt (it was sent: the mark is set before the prompt goes out)."""
        svc = self.service()
        _, big = self.large(svc)
        key = self.key(big)

        def hook(graph, owner, banded):
            if owner == key:
                Recorder.hook = None
                raise PromptRejected('rejected (test)', detail={'error': 'test', 'node_errors': {}})
        Recorder.hook = hook
        self.assertEqual(svc.run_all(), [])
        self.assertEqual(svc.item(big['id'])['state'], 'failed')
        self.assertEqual(len([e for e in self.released(svc) if e['job'] == key[0]]), 1)
        _, c1 = self.classic(svc)
        self.assertEqual(svc.run_all(), [])
        self.assert_fresh(self.key(c1))
        self.assertEqual(violations(), [])

    def test_an_image_that_starts_while_the_result_is_saved(self):
        """The success path releases the engine before the result is saved: the next image may start meanwhile, and it
        starts in a fresh engine."""
        svc = self.service()
        _, big = self.large(svc)
        key = self.key(big)
        entered, gate = threading.Event(), threading.Event()
        real = Runner._finish

        def finish(runner, ctx, job):
            if (ctx.jid, ctx.iid) == key:
                entered.set()
                gate.wait(60)
            return real(runner, ctx, job)
        with mock.patch.object(Runner, '_finish', finish):
            svc.runner._dispatch()
            self.assertTrue(entered.wait(60))
            self.assertTrue(svc.runner.ctx[key].worker_released)
            _, c1 = self.classic(svc)
            svc.runner._dispatch()
            t = svc.runner.threads.get(self.key(c1))
            self.assertIsNotNone(t, 'the Classic image did not start while the Large-image result was being saved')
            t.join(60)
            self.assertEqual(svc.item(c1['id'])['state'], 'done')
            gate.set()
            svc.runner.threads[key].join(60)
        self.done(svc, big['id'])
        self.assert_fresh(self.key(c1))
        self.assertEqual(violations(), [])
        self.assertEqual(len(self.released(svc)), 1)                     # the finally does not stop it a second time


# --- (iv) a shared Large-image image -------------------------------------------------------------------------------------
class ASharedImage(Base):
    ram_gb = J.RAM_WS

    def test_every_card_of_a_shared_image_is_stopped(self):
        svc = TwoCards(self.td / 'state', self.ram_gb, split=True)
        _, big = self.large(svc)
        self.assertEqual(svc.run_all(), [])
        it = self.done(svc, big['id'])
        self.assertEqual((it.get('run') or {}).get('cards'), [0, 1])
        rel = self.released(svc)
        self.assertEqual([e['data']['gpus'] for e in rel], [[0, 1]])
        mw = svc.runner.multi.get((0, 1))
        self.assertIsNotNone(mw)
        self.assertFalse(mw.alive())
        self.assertFalse(svc.worker.alive() or svc.worker1.alive())
        _, c1 = self.classic(svc)                            # shared too (the split is forced): a fresh shared engine
        self.assertEqual(svc.run_all(), [])
        self.done(svc, c1['id'])
        self.assert_fresh(self.key(c1))
        self.assertEqual(violations(), [])


# --- (v) the image's own passes ------------------------------------------------------------------------------------------
class TheImagesOwnPasses(Base):
    def test_no_stop_between_its_passes_and_one_at_its_end(self):
        """contracts.restart is unchanged: with the plan's fresh_worker flags cleared, the image's three passes run in one
        engine (no restart between them), and the engine is stopped once, after the last pass."""
        import tests.test_service3_restart as R
        svc = self.service()
        _, big = self.large(svc)
        R.flag(svc, big['id'], ())
        self.assertEqual(svc.run_all(), [])
        self.done(svc, big['id'])
        self.assertEqual(R.restarts(svc), [])
        self.assertEqual(svc.worker.starts, 1)
        self.assertEqual(len(self.released(svc)), 1)
        self.assertEqual([len(r['before']) for r in Recorder.log], [0, 1, 2])   # one engine process for the three passes
        self.assertFalse(svc.worker.alive())


# --- the stop and its record (contracts.restart_record), with the real JobCounters on stub Jobs --------------------------
class TheRecord(unittest.TestCase):
    def fixture(self, leave='freed', other_gb=None):
        import tests.test_admission_split as S
        job = S.Job()
        eng = S.Engine(job, commit_gb=12.0, leave=leave)
        eng.banded_sent = ('j1', 'i001')
        others = {}
        if other_gb is not None:
            other = S.Engine(job, name='other', commit_gb=other_gb)
            other.gpu = 1
            others[1] = other
        r = SimpleNamespace(mode='fake-process', shared_job=job, workers={0: eng, **others}, multi={}, accepting=True,
                            log=mock.Mock())
        ctx = SimpleNamespace(jid='j1', iid='i001', shutdown=False)
        return r, eng, ctx, job

    def test_the_commit_fields(self):
        r, eng, ctx, job = self.fixture(other_gb=5.0)
        rec = banded_runner.release_engine(r, eng, ctx, settle_s=1.0)
        self.assertEqual(eng.stops, 1)
        self.assertEqual(eng.starts, 0)                             # stopped, not started again: the next image starts it
        self.assertIsNone(eng.banded_sent)
        self.assertTrue(set(CONTRACT) <= set(rec), rec)
        self.assertEqual((rec['why'], rec['job'], rec['item'], rec['gpus']), ('large_image_ended', 'j1', 'i001', [0]))
        self.assertAlmostEqual(rec['commit_before_gb'], 17.0, places=2)
        self.assertAlmostEqual(rec['commit_after_gb'], 5.0, places=2)
        self.assertAlmostEqual(rec['commit_fall_gb'], 12.0, places=2)
        self.assertAlmostEqual(rec['stopped_worker_last_commit_gb'], 12.0, places=2)
        self.assertEqual(rec['commit_check'], 'passed')
        ev = [c for c in r.log.info.call_args_list if c.args and c.args[0] == RELEASED]
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0].kwargs['data'], rec)
        self.assertEqual((ev[0].kwargs['job'], ev[0].kwargs['item']), ('j1', 'i001'))

    def test_memory_that_stays_is_a_warning_never_a_failure(self):
        r, eng, ctx, job = self.fixture(leave=('leak', 4.0))
        rec = banded_runner.release_engine(r, eng, ctx, settle_s=0.2)
        self.assertEqual(rec['commit_check'], 'failed')
        self.assertAlmostEqual(rec['commit_fall_gb'], 8.0, places=2)
        self.assertTrue(any(c.args and c.args[0] == 'banded_engine_release_memory' for c in r.log.warn.call_args_list))

    def test_a_stop_that_raises_is_logged_and_the_engine_is_killed(self):
        r, eng, ctx, job = self.fixture()
        calls = []

        def stop(reason, kill=False):
            calls.append(kill)
            if not kill:
                raise OSError('the stop failed (test)')
            eng.state, eng.proc = 'stopped', None
        eng.stop = stop
        rec = banded_runner.release_engine(r, eng, ctx, settle_s=0.1)
        self.assertEqual(calls, [False, True])
        self.assertEqual(rec['commit_check'], 'unmeasured')
        self.assertTrue(any(c.args and c.args[0] == 'banded_engine_release_failed' for c in r.log.error.call_args_list))

    def test_the_wait_ends_when_the_app_closes(self):
        r, eng, ctx, job = self.fixture(leave='orphan')
        r.accepting = False
        rec = banded_runner.release_engine(r, eng, ctx, settle_s=30.0)
        self.assertLess(rec['commit_wait_s'], 5.0)
        self.assertEqual(rec['commit_check'], 'unmeasured')


class TheMark(unittest.TestCase):
    def test_the_worker_mark_is_cleared_when_the_process_goes(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            cfg = SimpleNamespace(workers_dir=Path(td), state_dir=Path(td))
            settings = SimpleNamespace(get=lambda: {'ram_cap_gb': 59.0, 'memory_profile': 'auto'})
            for w in (workers.Worker(0, cfg, settings, G.Log(), 'fake'),
                      workers.MultiCardWorker([0, 1], cfg, settings, G.Log(), 'fake')):
                self.assertIsNone(w.banded_sent)
                w.banded_sent = ('j1', 'i001')
                w._teardown('test')
                self.assertIsNone(w.banded_sent)


if __name__ == '__main__':
    unittest.main()
