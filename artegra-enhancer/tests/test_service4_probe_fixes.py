"""5.0.2 build wave 4, service package items 2-4: the start-up probe's open findings S6, S7 and S4
(roles/eng-wp-3-service-check.json; BUILD-WAVE-3-MERGE.md section 8 items 3-5). The probe path runs only where no committed
table applies and only for sizes up to BANDED_PROVEN_MP, which is 0 in a release build, so no Prove row reaches it; these
close before BANDED_PROVEN_MP is set.

- S6: G1u.refresh compares against the last load it made (the local table's path, size, mtime_ns and sha256 at that load),
  never against a fresh stat of the file now, so a local table rewritten at the same path (a second check) is a change:
  on_change runs and queued, unstarted Large-image images are planned again.
- S7: a protected-area preview never runs beside the processor check: the check does not start while a preview runs, and a
  preview asked for while the check runs is refused in plain words with the check's remaining upper bound. The check's
  --cap-gib stays sized with nothing beside it.
- S4 (narrowed): the processor-check sentence, and the request for the check, come only when the would-be banded-finish plan
  (banded_plan.plan_banded with the probe's best-case table) exists and passes Runner._vram_refusal and _physical_refusal.

In this process: G1u with the tests' stand-in environment, the in-process service on the fake engine and the stub probe of
tests/test_service3_probe.py. Sizes and synthetic tables only."""
import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from engine import banded_plan, controls
from engine.bxf import g1
from service import bxf_probe
from service.errors import ApiError
from service.runner import Runner
from service.util import same_plan
import tests.test_integ_large_image_job as J
import tests.test_service3_g1u as G
import tests.test_service3_probe as P


# --- S6 ------------------------------------------------------------------------------------------------------------------
class S6TheTableRewrittenInPlace(G.GlobalsRestored):
    def g1u(self, td, env):
        bxf_probe.TEST_ENVIRONMENT = env
        g = bxf_probe.G1u(SimpleNamespace(state_dir=Path(td), fake_engine=True), G.Log(), fake=True)
        g.start(background=False)
        return g

    def test_a_table_rewritten_at_the_same_path_is_a_change(self):
        with tempfile.TemporaryDirectory() as td:
            env = G.unmatched_env()
            path = G.write_local(td, G.local_table(env, widths=(16000,)))
            g = self.g1u(td, env)
            calls = []
            g.on_change = calls.append
            self.assertEqual(g.source, 'local')
            self.assertFalse(g.refresh(reason='probe'))                       # the same file: no change
            self.assertEqual(G.write_local(td, G.local_table(env, widths=(16000, 32000))), path)   # a second check
            self.assertTrue(g.refresh(reason='probe'))
            self.assertEqual(calls, ['probe'])
            self.assertFalse(g.refresh(reason='probe'))                       # compared with the load it made
            self.assertEqual(calls, ['probe'])
            self.assertEqual(g.loaded[0], str(path))

    def test_the_same_size_and_time_with_other_bytes_is_a_change(self):
        """The sha256 of the load decides where the size and mtime_ns cannot (a rewrite within the clock's tick)."""
        with tempfile.TemporaryDirectory() as td:
            env = G.unmatched_env()
            data = G.local_table(env, widths=(16000,))
            path = G.write_local(td, data)
            st = path.stat()
            g = self.g1u(td, env)
            text = path.read_text(encoding='utf8')
            other = text.replace('"gate": "G1u"', '"gate": "G1U"')
            self.assertNotEqual(other, text)
            self.assertEqual(len(other), len(text))
            path.write_text(other, encoding='utf8')
            os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))
            self.assertEqual((path.stat().st_size, path.stat().st_mtime_ns), (st.st_size, st.st_mtime_ns))
            self.assertTrue(g.refresh(reason='probe'))

    def test_a_removed_table_is_a_change(self):
        with tempfile.TemporaryDirectory() as td:
            env = G.unmatched_env()
            path = G.write_local(td, G.local_table(env, widths=(16000,)))
            g = self.g1u(td, env)
            path.unlink()
            self.assertTrue(g.refresh(reason='change'))
            self.assertIsNone(g.source)
            self.assertIsNone(g.loaded)


class S6QueuedImagesArePlannedAgain(G.ServiceBase):
    def test_a_second_check_rewriting_the_table_replans_the_queued_image(self):
        env = G.unmatched_env()
        banded_ops = sorted(op for op, v in g1.committed_tables()[-1]['ops'].items() if v.get('verdict') == 'banded')
        svc = self.service(env=env)
        mid = svc.add(J.strip_input(self.td / 'in', 'wide.png', 4000, 64))
        widths = None
        for whole in ((), banded_ops):                         # the first check, then a second one at the same path
            if widths is None:
                job = svc.job([mid], {'scale': 8})
                jid = job['id']
                widths = sorted({banded_plan.finish_size(s)[0] for s in job['items'][0]['plan']['stages']})
            G.write_local(svc.state, G.local_table(env, widths=widths, band_gb=(6.0,), whole=whole))
            before = svc.item(jid)['plan']
            self.assertTrue(svc.runner.g1u.refresh(reason='probe'))
            after = svc.item(jid)['plan']
            self.assertTrue(same_plan(before, after))
            self.assertNotEqual(before, after)                                # planned again with the rewritten table
        self.assertEqual(svc.item(jid)['state'], 'queued')
        self.assertEqual([e['data']['reason'] for e in svc.events() if e['event'] == 'item_replanned'], ['probe', 'probe'])


# --- S7 ------------------------------------------------------------------------------------------------------------------
class ProbeRunner(G.ServiceBase):
    """The in-process service with the stub probe (tests/test_service3_probe.py's TheRunnerRunsIt set-up, not its tests)."""

    def setUp(self):
        super().setUp()
        self.env = G.unmatched_env()
        self.stub = P.StubProbe(self.td, self.env)
        p = mock.patch.dict(os.environ, self.stub.vars)
        p.start()
        self.addCleanup(p.stop)

    def join_probe(self, svc):
        t = svc.runner._probe_thread
        if t is not None:
            t.join(60)
        self.assertIsNone(svc.runner._probe_thread)


class S7ThePreviewAndTheCheck(ProbeRunner):
    def test_a_preview_asked_for_while_the_check_runs_is_refused_in_plain_words(self):
        svc = self.service(env=self.env, probe=self.stub.command)
        mid = svc.add(J.strip_input(self.td / 'in', 'small.png', 320, 240))
        self.stub.mode('sleep')
        with mock.patch.object(bxf_probe, 'probe_seconds', return_value=600.0):
            svc.runner.g1u.request([16000], 6.0)
            svc.runner._dispatch()                                               # nothing queued or running: it starts
            self.assertIsNotNone(svc.runner._probe_thread)
            try:
                with self.assertRaises(ApiError) as e:
                    svc.runner.mask_preview(mid, protect=['people'])
                self.assertEqual((e.exception.status, e.exception.code), (503, 'processor_check'))
                self.assertEqual(str(e.exception), bxf_probe.say(bxf_probe.PREVIEW_DURING_CHECK, svc.runner._probe_minutes_left()))
                self.assertIn('11 minutes', str(e.exception))                    # 600 s and the kill grace, rounded up
                self.assertEqual(svc.worker.starts, 0)                           # no engine was started for it
                self.assertEqual(svc.runner._mask_inflight, {})
            finally:
                svc.runner.g1u.stop()
                self.join_probe(svc)
        svc.runner.g1u._stop.clear()
        self.assertFalse(svc.runner.mask_preview(mid, protect=['people'])['cached'])     # and after it, the preview runs

    def test_the_check_does_not_start_while_a_preview_runs(self):
        svc = self.service(env=self.env, probe=self.stub.command)
        svc.runner.g1u.request([16000], 6.0)
        key = ('m000000000000', 'k')
        svc.runner._mask_inflight[key] = threading.Event()
        svc.runner._dispatch()
        self.assertIsNone(svc.runner._probe_thread)
        del svc.runner._mask_inflight[key]
        svc.runner._dispatch()
        self.assertIsNotNone(svc.runner._probe_thread)
        self.join_probe(svc)

    def test_the_cap_is_sized_with_nothing_beside_it(self):
        svc = self.service(env=self.env, probe=self.stub.command)
        cap = float(svc.settings.get()['ram_cap_gb'])
        self.assertEqual(svc.runner._probe_cap_gib(), round(max(1.0, cap - bxf_probe.PROBE_SPARE_GB), 1))


# --- S4 ------------------------------------------------------------------------------------------------------------------
class S4TheWouldBePlan(ProbeRunner):
    """8x of 3500 x 2188 counts tier 3 without a table here, which refuses its last pass; probe_widths names the stages."""
    WIDTHS = [7000, 14000, 28000]

    def submit(self, svc, mid):
        with mock.patch.object(banded_plan, 'probe_widths', create=True, side_effect=lambda *a, **k: list(self.WIDTHS)):
            with self.assertRaises(ApiError) as e:
                svc.job([mid], {'scale': 8})
        return str(e.exception)

    def setUp(self):
        super().setUp()
        self.svc = self.service(env=self.env, probe=self.stub.command)
        self.mid = self.svc.add(J.strip_input(self.td / 'in', 'big.png', 3500, 2188))

    def test_a_would_be_plan_that_passes_both_checks_gets_the_sentence(self):
        seen = []
        real = Runner._vram_refusal

        def vram(runner, plan, protect=True, cards=None, mode=None):
            seen.append((banded_plan.is_banded(plan), getattr(plan, 'ok', None), protect))
            return real(runner, plan, protect=protect, cards=cards, mode=mode)
        with mock.patch.object(Runner, '_vram_refusal', vram):
            text = self.submit(self.svc, self.mid)
        self.assertIn('The app measures this computer\'s processor', text)
        protect = bool(controls.resolve({'scale': 8})[0]['protect_terms'])        # the image's own controls
        self.assertIn((True, True, protect), seen)                    # the would-be plan was judged
        self.assertEqual(self.svc.runner.g1u.pending_request(), (self.WIDTHS, 6.0))

    def test_a_would_be_plan_the_graphics_cards_refuse_gets_no_sentence(self):
        with mock.patch.object(Runner, '_vram_refusal', lambda *a, **k: 'This image needs more graphics memory (test).'):
            text = self.submit(self.svc, self.mid)
        self.assertNotIn('processor', text)
        self.assertIsNone(self.svc.runner.g1u.pending_request())

    def test_a_would_be_plan_the_physical_memory_refuses_gets_no_sentence(self):
        with mock.patch.object(Runner, '_physical_refusal', lambda *a, **k: 'This computer cannot hold it (test).'):
            text = self.submit(self.svc, self.mid)
        self.assertNotIn('processor', text)
        self.assertIsNone(self.svc.runner.g1u.pending_request())

    def test_the_reading_sentence_follows_the_same_rule(self):
        """While the engine runtime is still being read, the sentence that says so (READING_REFUSED, 'queue it again
        then') also needs a would-be plan that passes both checks."""
        g = self.svc.runner.g1u
        with mock.patch.object(Runner, '_g1u_settle', lambda *a, **k: None):
            g.ready.clear()
            try:
                text = self.submit(self.svc, self.mid)
                self.assertIn('still reading this computer\'s runtime', text)
                with mock.patch.object(Runner, '_vram_refusal', lambda *a, **k: 'This image needs more graphics memory.'):
                    text = self.submit(self.svc, self.mid)
                self.assertNotIn('still reading', text)
                self.assertNotIn('processor', text)
            finally:
                g.ready.set()

    def test_no_would_be_plan_no_sentence(self):
        real = banded_plan.plan_banded
        calls = []

        def plan(*a, **k):
            if k.get('_state') == ('bxf', banded_plan.PROBE_TABLE, 'probe'):
                calls.append(k)
                return SimpleNamespace(ok=False, reason='refused (test)', engine='banded')
            return real(*a, **k)
        with mock.patch.object(banded_plan, 'plan_banded', plan):
            text = self.submit(self.svc, self.mid)
        self.assertTrue(calls)
        self.assertNotIn('processor', text)
        self.assertIsNone(self.svc.runner.g1u.pending_request())


if __name__ == '__main__':
    unittest.main()
