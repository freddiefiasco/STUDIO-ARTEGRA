"""The processor check's two open findings that close before BANDED_PROVEN_MP is set above 0 (eng:check CHK-4: W4S-C2 and
W4S-C4; BUILD-WAVE-4-MERGE.md section 8 items 3 and 4).

- W4S-C2: the processor-check sentence judges the would-be banded-finish plan with the image's own controls, not with the
  heavier case it counts without them (every protected area on), at both places a refusal can carry it: a job's submit
  and new settings for a queued image (Runner.set_item_settings, through _plan_for). With protected areas off, a computer
  whose physical memory holds the plan's planes without the SAM masks but not with every area's masks gets the sentence;
  the same image with every protected area on does not. Each test here goes red when Runner._probe_plan_fits is given
  None for the image's controls, or when a call site leaves them out.
- W4S-C4: G1u.refresh takes the local table's identity before and after its load and loads again when they differ, so the
  identity it records is the one of the table it loaded, never of a file rewritten in between; the coverage the probe reads
  (local_coverage) comes from that loaded table's own data, keyed on that identity, never from a fresh stat of the file; a
  file that never reads the same around a load is not counted (fail closed).

In this process: G1u with the tests' stand-in environment, and the in-process service on the fake engine with the stub
probe (tests/test_service4_probe_fixes.py). Sizes and synthetic tables only."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from engine import banded_plan, controls
from engine.bxf import g1
from service import banded_runner, bxf_probe
from service.errors import ApiError
from service.runner import Runner
import tests.test_integ_large_image_job as J
import tests.test_service3_g1u as G
import tests.test_service4_probe_fixes as F

SENTENCE = 'The app measures this computer\'s processor'
OFF = {'protect': []}                     # the image's own controls: protected areas off
ALL = {'protect': list(controls.PROTECT_ORDER)}   # every protected area: what _probe_plan_fits counts without controls


# --- W4S-C2 ----------------------------------------------------------------------------------------------------------------
class TheImagesOwnControls(F.ProbeRunner):
    """8x of 3500 x 2188, refused by the planner here (tier 3 without a table), whose would-be banded-finish plan the check
    could lift; probe_widths names its stages (as tests/test_service4_probe_fixes.py S4TheWouldBePlan)."""
    WIDTHS = F.S4TheWouldBePlan.WIDTHS

    def setUp(self):
        super().setUp()
        self.svc = self.service(env=self.env, probe=self.stub.command)
        self.mid = self.svc.add(J.strip_input(self.td / 'in', 'big.png', 3500, 2188))
        self.cap = float(self.svc.settings.get()['ram_cap_gb'])
        p = mock.patch.object(banded_plan, 'probe_widths', create=True, side_effect=lambda *a, **k: list(self.WIDTHS))
        p.start()
        self.addCleanup(p.stop)

    def would_be(self):
        p = banded_plan.plan_banded(3500, 2188, 8, self.cap, mode='standard',
                                    _state=('bxf', banded_plan.PROBE_TABLE, 'probe'))
        self.assertTrue(p.ok, p.reason)
        return p

    def hold_planes_without_the_masks(self):
        """A computer whose physical memory holds the would-be plan beside its planes without the SAM masks (protected
        areas off), but not with every protected area's masks."""
        p = self.would_be()
        on, _ = controls.resolve(dict(ALL))
        off, _ = controls.resolve(dict(OFF))
        self.assertGreater(banded_runner.sam_planes(on), 0)
        self.assertEqual(banded_runner.sam_planes(off), 0)
        lone_on = banded_runner.lone_need_gb(p.peak_ram_gb, banded_runner.plan_planes_gb(p, banded_runner.sam_planes(on)))
        lone_off = banded_runner.lone_need_gb(p.peak_ram_gb, banded_runner.plan_planes_gb(p, 0))
        self.assertGreater(lone_on, lone_off + 0.2)
        total = (lone_on + lone_off) / 2.0 + banded_runner.PHYS_IDLE_GB
        self.svc.runner.fake_memory = {'total_phys_gb': total, 'avail_phys_gb': total}
        self.assertIsNotNone(self.svc.runner._physical_refusal(p, on))      # every protected area: refused
        self.assertIsNone(self.svc.runner._physical_refusal(p, off))        # the image's own controls admit it
        return on, off

    def submit(self, settings):
        with self.assertRaises(ApiError) as e:
            self.svc.job([self.mid], dict(settings, scale=8))
        return str(e.exception)

    def test_probe_plan_fits_reads_the_images_controls(self):
        on, off = self.hold_planes_without_the_masks()
        rec = self.svc.runner.media.get(self.mid)
        self.assertTrue(self.svc.runner._probe_plan_fits(rec, 8, self.cap, 'standard', off))
        self.assertFalse(self.svc.runner._probe_plan_fits(rec, 8, self.cap, 'standard', on))
        self.assertFalse(self.svc.runner._probe_plan_fits(rec, 8, self.cap, 'standard', None))   # None: the default

    def test_at_submit_physical_memory(self):
        self.hold_planes_without_the_masks()
        self.assertIn(SENTENCE, self.submit(OFF))                 # protected areas off: the check can lift it
        self.assertEqual(self.svc.runner.g1u.pending_request(), (self.WIDTHS, 6.0))
        self.svc.runner.g1u.requested.clear()
        self.assertNotIn('processor', self.submit(ALL))           # every protected area on: no sentence
        self.assertIsNone(self.svc.runner.g1u.pending_request())

    def test_at_new_settings_physical_memory(self):
        """Runner.set_item_settings (POST /api/items/settings) plans through _plan_for, the second place a refusal carries
        the sentence."""
        job = self.svc.job([self.mid], {'scale': 2})               # queued: 5.0.1 runs 2x
        jid, iid = job['id'], job['items'][0]['id']
        self.assertEqual(self.svc.item(jid)['state'], 'queued')
        self.hold_planes_without_the_masks()
        out = self.svc.runner.set_item_settings([{'job_id': jid, 'item_id': iid}], dict(OFF, scale=8))
        self.assertEqual(len(out['refused']), 1, out)
        self.assertIn(SENTENCE, out['refused'][0]['reason'])
        self.svc.runner.g1u.requested.clear()
        out = self.svc.runner.set_item_settings([{'job_id': jid, 'item_id': iid}], dict(ALL, scale=8))
        self.assertEqual(len(out['refused']), 1, out)
        self.assertNotIn('processor', out['refused'][0]['reason'])

    def test_at_submit_graphics_memory(self):
        """A card whose graphics memory holds the would-be plan without SAM and not with it (stand-in refusal keyed on
        the protected areas it is asked about)."""
        real = Runner._vram_refusal

        def vram(runner, plan, protect=True, cards=None, mode=None):
            if banded_plan.is_banded(plan) and protect:
                return 'This image needs more graphics memory with its protected areas (test).'
            return real(runner, plan, protect=protect, cards=cards, mode=mode)
        with mock.patch.object(Runner, '_vram_refusal', vram):
            self.assertIn(SENTENCE, self.submit(OFF))
            self.svc.runner.g1u.requested.clear()
            self.assertNotIn('processor', self.submit(ALL))


# --- W4S-C4 ----------------------------------------------------------------------------------------------------------------
class TheLoadedTable(G.GlobalsRestored):
    def g1u(self, td, env):
        bxf_probe.TEST_ENVIRONMENT = env
        g = bxf_probe.G1u(SimpleNamespace(state_dir=Path(td), fake_engine=True), G.Log(), fake=True)
        g.start(background=False)
        return g

    @staticmethod
    def banded_op():
        return sorted(op for op, v in g1.committed_tables()[-1]['ops'].items() if v.get('verdict') == 'banded')[0]

    def rewriting(self, g, path, data, times=1):
        """g.load reads the file, then (the first `times` loads) the file is rewritten with `data` before refresh's second
        read: a second processor check landing in between."""
        real = g.load
        calls = []

        def load(env, local=None):
            out = real(env) if local is None else real(env, local)
            calls.append(out[1])
            if len(calls) <= times:
                path.write_text(json.dumps(dict(data, note=f'rewrite {len(calls)}')), encoding='utf8')
            return out
        g.load = load
        return calls

    def test_a_rewrite_between_the_two_reads(self):
        with tempfile.TemporaryDirectory() as td:
            env = G.unmatched_env()
            op = self.banded_op()
            path = G.write_local(td, G.local_table(env, widths=(16000,)))
            g = self.g1u(td, env)
            self.assertEqual(banded_plan.BXF_TABLE.verdict(op), 'banded')
            later = G.local_table(env, widths=(16000, 32000), whole=(op,))    # the second check classes op whole
            calls = self.rewriting(g, path, later)
            self.assertTrue(g.refresh(reason='probe'))
            self.assertEqual(len(calls), 2)                                    # loaded again after the rewrite
            self.assertEqual(banded_plan.BXF_TABLE.verdict(op), 'whole')       # the table counted is the rewritten one
            self.assertEqual(g.loaded, bxf_probe.file_identity(str(path)))     # and its identity is that table's
            self.assertEqual(g.local_coverage()[0], {8192, 16000, 32000})
            self.assertFalse(g.refresh(reason='probe'))                        # nothing changed since that load

    def test_coverage_after_a_same_size_rewrite(self):
        """A second check rewrites the table at the same size and time with other widths: after the refresh that loads
        it, the coverage the probe reads is the new table's (never a cached reading keyed on the size and time)."""
        with tempfile.TemporaryDirectory() as td:
            env = G.unmatched_env()
            path = G.write_local(td, G.local_table(env, widths=(16000,)))
            st = path.stat()
            g = self.g1u(td, env)
            self.assertEqual(g.local_coverage()[0], {8192, 16000})
            self.assertFalse(g.probe_needed([16000], 6.0))
            text = path.read_text(encoding='utf8')
            other = text.replace('16000', '32000')
            self.assertEqual(len(other), len(text))
            path.write_text(other, encoding='utf8')
            os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))
            self.assertEqual((path.stat().st_size, path.stat().st_mtime_ns), (st.st_size, st.st_mtime_ns))
            self.assertTrue(g.refresh(reason='probe'))
            self.assertEqual(g.local_coverage()[0], {8192, 32000})
            self.assertFalse(g.probe_needed([32000], 6.0))
            self.assertTrue(g.probe_needed([16000], 6.0))

    def test_the_coverage_is_the_loaded_tables_until_the_next_load(self):
        """A rewrite the planner has not loaded yet changes nothing the probe reads: the coverage stays the one of the table
        the planner counts, and follows the file at the refresh that loads it."""
        with tempfile.TemporaryDirectory() as td:
            env = G.unmatched_env()
            path = G.write_local(td, G.local_table(env, widths=(16000,)))
            g = self.g1u(td, env)
            self.assertEqual(g.local_coverage()[0], {8192, 16000})
            G.write_local(td, G.local_table(env, widths=(16000, 32000)))
            self.assertEqual(g.local_coverage()[0], {8192, 16000})            # not loaded yet
            self.assertTrue(g.refresh(reason='probe'))
            self.assertEqual(g.local_coverage()[0], {8192, 16000, 32000})
            path.unlink()
            self.assertTrue(g.refresh(reason='change'))
            self.assertEqual(g.local_coverage(), (set(), set()))

    def test_a_table_that_never_reads_the_same_is_not_counted(self):
        with tempfile.TemporaryDirectory() as td:
            env = G.unmatched_env()
            path = G.write_local(td, G.local_table(env, widths=(16000,)))
            g = self.g1u(td, env)
            log = g.log
            calls = self.rewriting(g, path, G.local_table(env, widths=(16000, 32000)), times=99)
            self.assertTrue(g.refresh(reason='probe'))
            self.assertEqual(len(calls), bxf_probe.LOAD_TRIES)
            self.assertIsNone(g.source)                                       # fail closed: the whole finish
            self.assertIsNone(banded_plan.BXF_TABLE)
            self.assertEqual(g.local_coverage(), (set(), set()))
            self.assertIn('bxf_table_unstable', log.events('warn'))
            self.assertEqual(g.loaded, (str(path), None, None, None))
            calls.clear()
            del g.load                                                        # the file settles
            self.assertTrue(g.refresh(reason='probe'))
            self.assertEqual(g.source, 'local')
            self.assertEqual(g.local_coverage()[0], {8192, 16000, 32000})


if __name__ == '__main__':
    unittest.main()
