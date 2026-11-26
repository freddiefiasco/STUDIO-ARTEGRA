"""5.0.2 build wave 3, the start-up probe run by the service (G1u; BUILD-WAVE-3 contracts.g1u; service/bxf_probe.py): its
command line, the table written atomically (a partial table is never read), exit 2 and 3 leaving tier 3 with a plain reason,
the kill at the service's deadline, never beside a running image, its commit counted in admission, the waiting image's
message with its upper bound, the re-plan once the table lands, and a refused image asking for the probe.

In this process with a stub probe: a small script standing in for engine/bxf/selfprobe.py by its command line (it writes a
table, exits 2 or 3, writes a partial table, or sleeps past its deadline). Sizes and synthetic tables only."""
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from engine import banded_plan
from engine.bxf import g1
from service import bxf_probe
from service.errors import ApiError
import tests.test_integ_large_image_job as J
import tests.test_service3_g1u as G

STUB = r'''
import json, os, sys, time
a = sys.argv[1:]
def opt(name):
    return [a[i + 1] for i, v in enumerate(a) if v == name and i + 1 < len(a)]
if os.environ.get('CU_STUB_PROBE_ARGS'):
    with open(os.environ['CU_STUB_PROBE_ARGS'], 'w') as f:
        json.dump(a, f)
mode = os.environ.get('CU_STUB_PROBE_MODE', 'write')
out = opt('--out')[0]
if mode == 'write':
    data = json.load(open(os.environ['CU_STUB_PROBE_BASE']))
    data.update(environment=json.loads(os.environ['CU_STUB_PROBE_ENV']), gate='G1u',
                widths=sorted({8192} | {int(w) for w in opt('--width')}), band_gb=[float(b) for b in opt('--band-gb')])
    with open(out + '.tmp', 'w') as f:
        json.dump(data, f)
    os.replace(out + '.tmp', out)
    sys.exit(0)
if mode == 'exit2':
    print('selfprobe: the self-probe ran out of time after 5 s (limit 5 s); no table was written', file=sys.stderr)
    sys.exit(2)
if mode == 'exit3':
    print('selfprobe: the probe needs about 9.0 GiB at 32000 px (1153 rows), over the cap of 1 GiB; no table was written',
          file=sys.stderr)
    sys.exit(3)
if mode == 'fail':
    print('selfprobe: the probe failed (RuntimeError: boom); no table was written', file=sys.stderr)
    sys.exit(3)
if mode in ('partial', 'partial0'):
    with open(out, 'w') as f:
        f.write('{"ops": {')
    sys.exit(0 if mode == 'partial0' else 3)
if mode == 'sleep':
    time.sleep(120)
sys.exit(0)
'''


class StubProbe:
    """The stub's files and environment (the stub reads CU_STUB_PROBE_*: inherited through bxf_probe.child_env)."""

    def __init__(self, td, env, mode='write'):
        self.dir = Path(td) / 'stub'
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / 'selfprobe_stub.py').write_text(STUB, encoding='utf8')
        (self.dir / 'base.json').write_text(json.dumps(g1.committed_tables()[-1]), encoding='utf8')
        self.args_file = self.dir / 'args.json'
        self.vars = {'CU_STUB_PROBE_MODE': mode, 'CU_STUB_PROBE_BASE': str(self.dir / 'base.json'),
                     'CU_STUB_PROBE_ENV': json.dumps(env), 'CU_STUB_PROBE_ARGS': str(self.args_file)}
        self.command = [sys.executable, '-I', '-B', str(self.dir / 'selfprobe_stub.py')]

    def mode(self, m):
        os.environ['CU_STUB_PROBE_MODE'] = m

    def args(self):
        return json.loads(self.args_file.read_text(encoding='utf8'))


class ProbeBase(G.GlobalsRestored):
    def setUp(self):
        super().setUp()
        self.td = tempfile.mkdtemp(prefix='cu-probe-')
        self.addCleanup(lambda: __import__('shutil').rmtree(self.td, ignore_errors=True))
        self.env = G.unmatched_env()
        self.stub = StubProbe(self.td, self.env)
        p = mock.patch.dict(os.environ, self.stub.vars)
        p.start()
        self.addCleanup(p.stop)
        bxf_probe.TEST_ENVIRONMENT = self.env
        bxf_probe.TEST_PROBE = self.stub.command

    def g1u(self):
        cfg = SimpleNamespace(state_dir=Path(self.td) / 'state', fake_engine=True, site_packages=Path(self.td) / 'site',
                              runtime_python=Path(sys.executable))
        log = G.Log()
        g = bxf_probe.G1u(cfg, log, fake=True)
        g.start(background=False)
        return g, log


class TheProbeRun(ProbeBase):
    def test_exit_0_writes_the_table_atomically_and_it_applies(self):
        g, log = self.g1u()
        self.assertTrue(g.probe_needed([16000, 32000], 6.0))
        rec = g.run_probe([32000, 16000], 6.0, cap_gib=40.0)
        self.assertEqual(rec['exit'], 0, rec)
        args = self.stub.args()
        self.assertEqual([args[i + 1] for i, v in enumerate(args) if v == '--width'], ['16000', '32000'])
        self.assertEqual(args[args.index('--band-gb') + 1], '6')
        self.assertEqual(args[args.index('--cap-gib') + 1], '40.0')
        self.assertEqual(args[args.index('--site') + 1], str(Path(self.td) / 'site'))
        self.assertEqual(int(args[args.index('--seconds') + 1]),
                         int(__import__('math').ceil(bxf_probe.probe_seconds([16000, 32000], [6.0]))))
        self.assertTrue(args[args.index('--out') + 1].endswith(bxf_probe.PROBE_PART))   # renamed only on exit 0
        state = Path(self.td) / 'state' / 'bxf'
        self.assertFalse((state / bxf_probe.PROBE_PART).exists())
        self.assertTrue((state / bxf_probe.LOCAL_TABLE).is_file())
        self.assertTrue(g.refresh(reason='probe'))
        self.assertEqual(g.source, 'local')
        self.assertTrue(banded_plan.BXF_TABLE.applies)
        self.assertFalse(g.probe_needed([16000, 32000], 6.0))
        self.assertIn('bxf_probe_done', log.events('info'))

    def test_the_real_command_runs_selfprobe_by_path_with_the_runtime(self):
        g, _ = self.g1u()
        g.fake = False
        args = g.probe_command([16000], 3.0, 20.0, 600, Path(self.td) / 'out.json')
        self.assertEqual(args[:5], [sys.executable, '-I', '-B', '-S', str(bxf_probe.selfprobe_path())])
        self.assertTrue(bxf_probe.selfprobe_path().is_file())

    def test_exit_2_and_3_leave_tier_3_with_a_plain_reason(self):
        for mode, reason in (('exit2', bxf_probe.PROBE_OUT_OF_TIME), ('exit3', bxf_probe.PROBE_NO_MEMORY),
                             ('fail', bxf_probe.PROBE_FAILED), ('partial', bxf_probe.PROBE_FAILED),
                             ('partial0', bxf_probe.PROBE_FAILED)):
            with self.subTest(mode=mode):
                self.stub.mode(mode)
                g, log = self.g1u()
                rec = g.run_probe([16000], 6.0, cap_gib=1.0)
                self.assertIn(rec['exit'], (2, 3), rec)
                self.assertEqual(rec['reason'], reason)
                state = Path(self.td) / 'state' / 'bxf'
                self.assertFalse((state / bxf_probe.LOCAL_TABLE).exists())      # a partial table is never read
                self.assertFalse((state / bxf_probe.PROBE_PART).exists())
                g.refresh(reason='probe')
                self.assertIsNone(banded_plan.BXF_TABLE)
                self.assertFalse(g.probe_needed([16000], 6.0))                  # not again this session
                warn = [x for x in log.lines if x[1] == 'bxf_probe_failed']
                self.assertEqual(len(warn), 1)
                self.assertIn(reason, warn[0][2])
                self.assertNotIn('selfprobe', warn[0][2])                        # the plain sentence, not the probe's own

    def test_killed_at_the_deadline(self):
        self.stub.mode('sleep')
        g, log = self.g1u()
        t0 = time.monotonic()
        with mock.patch.object(bxf_probe, 'probe_seconds', return_value=1.0), \
                mock.patch.object(bxf_probe, 'PROBE_KILL_GRACE_S', 0.5):
            rec = g.run_probe([16000], 6.0, cap_gib=4.0)
        self.assertLess(time.monotonic() - t0, 30.0)
        self.assertEqual(rec['exit'], 2)
        self.assertEqual(rec['reason'], bxf_probe.PROBE_OUT_OF_TIME)
        self.assertIn('deadline', rec['detail'])
        self.assertIsNone(g.proc)
        self.assertEqual(g.probe_commit_gb(), 0.0)

    def test_stopped_when_the_app_closes(self):
        self.stub.mode('sleep')
        g, log = self.g1u()
        out = {}
        t = threading.Thread(target=lambda: out.update(g.run_probe([16000], 6.0, cap_gib=4.0)))
        t.start()
        end = time.monotonic() + 20
        while g.proc is None and time.monotonic() < end:
            time.sleep(0.05)
        self.assertEqual(g.probe_commit_gb(), 4.0)                              # counted while it runs
        if os.name == 'nt':                                                       # below normal priority (0x4000)
            import ctypes
            k32 = ctypes.windll.kernel32
            k32.GetPriorityClass.argtypes = [ctypes.c_void_p]
            with g.proc._lock:
                self.assertEqual(k32.GetPriorityClass(ctypes.c_void_p(g.proc.process)),
                                 bxf_probe.BELOW_NORMAL_PRIORITY_CLASS)
        g.stop()
        t.join(30)
        self.assertFalse(t.is_alive())
        self.assertIsNone(out['exit'])
        self.assertIn('bxf_probe_stopped', log.events('info'))

    def test_the_waiting_message_states_an_upper_bound(self):
        for widths, bands in (([16000], [6.0]), ([16000, 32000], [3.0]), ([8192], [2.0])):
            m = bxf_probe.probe_minutes(widths, bands)
            self.assertGreaterEqual(m * 60, bxf_probe.probe_seconds(widths, bands) + bxf_probe.PROBE_KILL_GRACE_S)
        # at least the measured 20 min of fin-g1u-rt for its widths on this workstation's CPU
        self.assertGreaterEqual(bxf_probe.probe_seconds([14000], [6.0]), 1209)


class TheRunnerRunsIt(G.ServiceBase):
    def setUp(self):
        super().setUp()
        self.env = G.unmatched_env()
        self.stub = StubProbe(self.td, self.env)
        p = mock.patch.dict(os.environ, self.stub.vars)
        p.start()
        self.addCleanup(p.stop)

    def queued(self, svc, w=4000, h=64, scale=8):
        mid = svc.add(J.strip_input(self.td / 'in', f'img{w}x{h}.png', w, h))
        job = svc.job([mid], {'scale': scale})
        return job['id']

    def join_probe(self, svc):
        t = svc.runner._probe_thread
        if t is not None:
            t.join(60)
        self.assertIsNone(svc.runner._probe_thread)

    def test_never_beside_a_running_image_then_the_table_lands(self):
        svc = self.service(env=self.env, probe=self.stub.command)
        jid = self.queued(svc)
        self.assertEqual(svc.item(jid)['plan']['banded']['finish_tier'], 'tier3')
        busy = ('jbusy', 'i001')
        svc.runner.ctx[busy] = SimpleNamespace(worker_released=False, worker=None)
        svc.runner._dispatch()
        self.assertIsNone(svc.runner._probe_thread)                              # an image is running: no probe
        msg = svc.item(jid)['message']
        self.assertTrue(msg.startswith('Waiting for the processor check'), msg)
        self.assertIn('when the images before it are done', msg)
        del svc.runner.ctx[busy]
        with mock.patch.object(bxf_probe.G1u, 'run_probe', wraps=svc.runner.g1u.run_probe) as spy:
            svc.runner._dispatch()
            self.assertIsNotNone(svc.runner._probe_thread)
            self.join_probe(svc)
        self.assertEqual(spy.call_count, 1)
        self.assertEqual(svc.runner.g1u.source, 'local')
        plan = svc.item(jid)['plan']
        self.assertEqual(plan['banded']['finish_tier'], 'bxf')                  # re-planned once the table landed
        self.assertEqual(svc.item(jid)['message'], 'Waiting')
        self.assertEqual(svc.run_all(), [])
        self.done(svc, jid)
        ev = [e['event'] for e in svc.events()]
        self.assertIn('bxf_probe_start', ev)
        self.assertIn('item_replanned', ev)
        self.assertEqual(ev.count('bxf_probe_start'), 1)

    def test_the_waiting_image_shows_its_upper_bound(self):
        svc = self.service(env=self.env, probe=self.stub.command)
        self.stub.mode('sleep')
        jid = self.queued(svc)
        with mock.patch.object(bxf_probe, 'probe_seconds', return_value=1.0), \
                mock.patch.object(bxf_probe, 'PROBE_KILL_GRACE_S', 0.5):
            svc.runner._dispatch()
            msg = svc.item(jid)['message']
            self.assertEqual(msg, bxf_probe.say(bxf_probe.PROBE_WAITING, 1))
            svc.runner._dispatch()                                               # nothing starts beside it
            self.assertEqual(svc.runner.ctx, {})
            self.join_probe(svc)

    def test_exit_2_leaves_tier_3_and_the_image_runs(self):
        svc = self.service(env=self.env, probe=self.stub.command)
        self.stub.mode('exit2')
        jid = self.queued(svc)
        svc.runner._dispatch()
        self.join_probe(svc)
        self.assertEqual(svc.item(jid)['plan']['banded']['finish_tier'], 'tier3')
        self.assertEqual(svc.item(jid)['message'], 'Waiting')
        self.assertEqual(svc.run_all(), [])                                      # no second probe; it runs at tier 3
        it = self.done(svc, jid)
        ev = [e['event'] for e in svc.events()]
        self.assertEqual(ev.count('bxf_probe_start'), 1)
        self.assertIn('bxf_probe_failed', ev)
        side = json.loads(Path(it['sidecar']).read_text(encoding='utf8'))
        self.assertEqual([x['finish_tier'] for x in side['engine']['bxf_stages']], ['tier3'] * 3)

    def test_its_commit_is_counted_in_admission(self):
        svc = self.service(env=self.env, probe=self.stub.command)
        mid = svc.add(J.strip_input(self.td / 'in', 'small.png', 640, 480))
        job = svc.job([mid], {'scale': 2})                                       # a classic image
        cap = float(svc.settings.get()['ram_cap_gb'])
        self.assertTrue(svc.runner._admit(job['id'], 'i001'))
        svc.runner.g1u.probing = {'cap_gib': cap}
        try:
            self.assertFalse(svc.runner._admit(job['id'], 'i001'))
        finally:
            svc.runner.g1u.probing = None

    def test_a_committed_match_never_probes(self):
        svc = self.service(env=G.committed_env(1), probe=self.stub.command)
        jid = self.queued(svc)
        self.assertEqual(svc.item(jid)['plan']['banded']['finish_tier'], 'bxf')
        self.assertEqual(svc.run_all(), [])
        self.done(svc, jid)
        self.assertNotIn('bxf_probe_start', [e['event'] for e in svc.events()])
        self.assertFalse(self.stub.args_file.exists())

    def test_a_refused_image_asks_for_the_probe(self):
        """8x of 3500 x 2188 counts tier 3 without a table here, which refuses its 490 MP last pass; when probe_widths names
        the stages a banded-finish plan would have, the refusal says the check runs when the app is free, and it does."""
        svc = self.service(env=self.env, probe=self.stub.command)
        mid = svc.add(J.strip_input(self.td / 'in', 'big.png', 3500, 2188))
        widths = [7000, 14000, 28000]
        with mock.patch.object(banded_plan, 'probe_widths', create=True, side_effect=lambda *a, **k: list(widths)):
            with self.assertRaises(ApiError) as e:
                svc.job([mid], {'scale': 8})
            self.assertIn('The app measures this computer\'s processor', str(e.exception))
            self.assertEqual(svc.runner.g1u.pending_request(), (widths, 6.0))
            svc.runner._dispatch()                                               # nothing queued or running: it starts
            self.join_probe(svc)
        args = self.stub.args()
        self.assertEqual([int(args[i + 1]) for i, v in enumerate(args) if v == '--width'], widths)
        self.assertEqual(svc.runner.g1u.source, 'local')
        self.assertIsNone(svc.runner.g1u.pending_request())

    def test_a_waiting_queue_is_not_planned_again_at_every_tick(self):
        svc = self.service(env=self.env, probe=self.stub.command)
        for i in range(4):
            self.queued(svc, h=64 + 32 * i)
        svc.runner.ctx[('jbusy', 'i001')] = SimpleNamespace(worker_released=False, worker=None)
        calls = []
        with mock.patch.object(banded_plan, 'probe_widths', create=True,
                               side_effect=lambda *a, **k: calls.append(a) or []):
            svc.runner._dispatch()
        self.assertLessEqual(len(calls), 1)                                       # the first image only, while it waits
        reads = []
        real = g1.read_local
        with mock.patch.object(g1, 'read_local', side_effect=lambda p: reads.append(p) or real(p)):
            for _ in range(5):
                svc.runner.g1u.local_covers([16000], 6.0)
        self.assertLessEqual(len(reads), 1)                                       # read once per file version
        del svc.runner.ctx[('jbusy', 'i001')]

    def test_a_table_that_does_not_apply_is_not_probed_again(self):
        """The probe exits 0 but its table is for another environment (a stale environment reading): the environment is
        read again once, and as it still does not apply, the check is recorded as failed and the image runs at tier 3; no
        second probe."""
        os.environ['CU_STUB_PROBE_ENV'] = json.dumps(dict(self.env, torch='0.0.0+another'))
        svc = self.service(env=self.env, probe=self.stub.command)
        jid = self.queued(svc)
        svc.runner._dispatch()
        self.join_probe(svc)
        self.assertIsNone(svc.runner.g1u.source)
        self.assertEqual(svc.run_all(), [])
        it = self.done(svc, jid)
        self.assertEqual(it['plan']['banded']['finish_tier'], 'tier3')
        ev = [e for e in svc.events()]
        self.assertEqual([e['event'] for e in ev].count('bxf_probe_start'), 1)
        failed = [e for e in ev if e['event'] == 'bxf_probe_failed']
        self.assertEqual(len(failed), 1)
        self.assertIn(bxf_probe.PROBE_NOT_APPLIED, failed[0]['msg'])

    def test_a_release_build_refusal_stays_501s(self):
        """Nothing is admitted to the Large-image engine in a release build (BANDED_PROVEN_MP 0): the refusal gains no
        sentence about the processor check and asks for none, whatever probe_widths says."""
        svc = self.service(env=self.env, probe=self.stub.command)
        mid = svc.add(J.strip_input(self.td / 'in', 'big.png', 3500, 2188))
        with mock.patch.dict(banded_plan.BANDED_PROVEN_MP, {'ws128': 0.0, 'pc64': 0.0, 'pc48': 0.0}), \
                mock.patch.object(banded_plan, 'probe_widths', create=True, side_effect=lambda *a, **k: [7000, 14000]):
            with self.assertRaises(ApiError) as e:
                svc.job([mid], {'scale': 8})
        self.assertNotIn('processor', str(e.exception))
        self.assertIsNone(svc.runner.g1u.pending_request())

    def test_without_probe_widths_a_refusal_is_501s(self):
        svc = self.service(env=self.env, probe=self.stub.command)
        mid = svc.add(J.strip_input(self.td / 'in', 'big.png', 3500, 2188))
        with mock.patch.object(banded_plan, 'probe_widths', create=True, side_effect=lambda *a, **k: []):
            with self.assertRaises(ApiError) as e:
                svc.job([mid], {'scale': 8})
        self.assertNotIn('processor', str(e.exception))
        self.assertIsNone(svc.runner.g1u.pending_request())


if __name__ == '__main__':
    unittest.main()
