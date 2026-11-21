"""phase_run.ComfyEngine's on_started hook (L3r): a sampler that follows the newest worker samples a restarted worker from
its first second, its start-up included. The worker is a stub: a real child process in a real Windows Job (a Python that
holds memory and sleeps), with a ComfyUI client stand-in that answers only after a while, as a loading worker does. No
ComfyUI, no port, no GPU. Windows only (the Job and the counters are Windows')."""
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest import mock

HOLD = 'import time; b = bytearray(64 << 20); time.sleep(60)'


class SlowClient:
    """service.comfy.ComfyClient as a worker that is still loading: system_stats fails until `ready_after` s have passed."""
    ready_after = 1.5

    def __init__(self, port):
        self.port, self.t0 = port, time.monotonic()

    def system_stats(self):
        if time.monotonic() - self.t0 < self.ready_after:
            raise ConnectionRefusedError('loading')
        return {'system': {}}


@unittest.skipUnless(sys.platform == 'win32', 'Windows Jobs')
class OnStarted(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)     # a killed child's log may close late
        self.d = Path(self._t.name)
        from tools.proof import harness
        self.patches = [
            mock.patch.object(harness, 'worker_yaml', lambda cfg, proof_dir: ''),
            mock.patch.object(harness, 'worker_command', lambda cfg, wd, port, yaml, proof_dir: ([sys.executable, '-c', HOLD],
                                                                                                 {})),
            mock.patch('service.comfy.ComfyClient', SlowClient),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self._t.cleanup()

    def engine(self, run_dir, hook):
        from tools.proof import phase_run
        return phase_run.ComfyEngine(types.SimpleNamespace(), self.d, run_dir, 'GPU-stub', 1, 8.0, ready_timeout_s=30,
                                     on_started=hook)

    def test_the_hook_runs_before_the_worker_answers_and_the_sampler_follows_the_restart(self):
        from tools.proof import sampler
        cur, started = {}, []

        def hook(e):
            cur['e'] = e
            started.append((e.proc.pid, time.time()))
        s = sampler.Sampler(self.d / 'samples.jsonl', 0.2, jobs=lambda: {'worker': cur['e'].proc.job} if cur.get('e') else {},
                            pids=lambda: ({'worker': cur['e'].proc.pid} if cur.get('e') else {}), gpu=False, mem=False)
        s.start()
        try:
            first = self.engine(self.d / 'w0', hook)                 # part A's worker
            self.assertIsNotNone(first.ready_at)
            self.assertLess(first.started_at, first.ready_at - 1.0)
            first.stop()
            second = self.engine(self.d / 'w1', hook)                # part B's fresh worker (the restart)
            time.sleep(0.5)
            second.stop()
        finally:
            s.stop()
        self.assertEqual([p for p, _ in started], [first.proc.pid, second.proc.pid])
        rows = sampler.read_samples(self.d / 'samples.jsonl')
        for e in (first, second):
            seen = [r for r in rows if str(e.proc.pid) in (r.get('procs') or {})]
            self.assertTrue(seen, e.proc.pid)
            before_ready = [r for r in seen if r['t'] < e.ready_at]
            self.assertGreaterEqual(len(before_ready), 3, (e.proc.pid, len(seen)))   # sampled while it was starting
            self.assertLess(min(r['t'] for r in seen) - e.started_at, 1.0)           # from its first second
            commits = [r['jobs']['worker']['commit'] for r in before_ready if (r.get('jobs') or {}).get('worker')]
            self.assertTrue(commits and max(commits) > 0)

    def test_a_failing_hook_never_stops_the_worker(self):
        def bad(e):
            raise RuntimeError('the sampler is not there')
        e = self.engine(self.d / 'w', bad)
        try:
            self.assertIn('the sampler is not there', e.hook_error)
            self.assertIsNotNone(e.ready_at)
        finally:
            e.stop()

    def test_without_a_hook_the_engine_is_as_before(self):
        e = self.engine(self.d / 'w', None)
        try:
            self.assertIsNone(e.hook_error)
            self.assertIsNotNone(e.ready_at)
        finally:
            rec = e.stop()
        self.assertTrue(rec.get('all_owned_processes_terminated'), rec)


if __name__ == '__main__':
    unittest.main()
