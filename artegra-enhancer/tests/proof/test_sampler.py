"""tools/proof/sampler.py on this Windows machine (no service, no GPU job): the per-process and system probes, a Job's peak
commit, the 2 s sampler thread and the per-phase summary. The GPU counters are read when Windows has them."""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from tools.proof import sampler

WIN = sys.platform == 'win32'


@unittest.skipUnless(WIN, 'Windows counters')
class Probes(unittest.TestCase):
    def test_this_process(self):
        m = sampler.proc_mem(os.getpid())
        self.assertGreater(m['private'], 1 << 20)
        self.assertGreater(m['ws'], 1 << 20)
        io = sampler.io_counters(os.getpid())
        self.assertGreaterEqual(io['read_bytes'], 0)
        self.assertGreaterEqual(io['write_bytes'], 0)

    def test_system(self):
        p = sampler.perf()
        self.assertGreater(p['commit_total'], 0)
        self.assertGreaterEqual(p['cache'], 0)
        pf = sampler.pagefiles()
        self.assertIsInstance(pf, list)
        mc = sampler.MemoryCounters()
        time.sleep(0.2)
        r = mc.read()
        self.assertIn('pages_input_per_s', r)
        self.assertIn('cache_bytes', r)
        mc.close()

    def test_gpu_counters_when_present(self):
        try:
            g = sampler.GpuCounters()
        except OSError as e:
            self.skipTest(f'no GPU memory counters here: {e}')
        r = g.read()
        self.assertIn('proc', r)
        self.assertIn('adapter', r)
        g.close()

    def test_job_peak_commit_of_a_child(self):
        from service import windows_job
        with tempfile.TemporaryDirectory() as d:
            code = 'import time; b = bytearray(160 * 1024 * 1024); time.sleep(1.0)'
            proc = windows_job.WindowsJobProcess([sys.executable, '-B', '-c', code], cwd=d, env=dict(os.environ),
                                                 log_path=Path(d) / 'child.txt')
            try:
                seen = sampler.job_pids(proc.job)
                cur, peak = sampler.job_memory(proc.job)
                proc.wait(30)
                cur2, peak2 = sampler.job_memory(proc.job)
                self.assertGreaterEqual(peak2, 150 * (1 << 20))
                self.assertEqual(peak2, proc.limits()['peak_job_memory_used'])
                self.assertIn(proc.pid, seen)
            finally:
                proc.close()


@unittest.skipUnless(WIN, 'Windows counters')
class SamplerThread(unittest.TestCase):
    def test_writes_samples_of_the_named_processes(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'samples.jsonl'
            s = sampler.Sampler(out, interval_s=0.1, pids=lambda: {'self': os.getpid()}, gpu=False)
            s.start()
            time.sleep(0.7)
            s.stop()
            lines = [json.loads(x) for x in out.read_text(encoding='utf8').splitlines()]
            self.assertGreaterEqual(len(lines), 3)
            self.assertIn(str(os.getpid()), lines[-1]['procs'])
            self.assertEqual(lines[-1]['procs'][str(os.getpid())]['role'], 'self')
            self.assertIn('commit_total', lines[-1]['perf'])


class Summary(unittest.TestCase):
    def test_peaks_overall_and_per_phase(self):
        samples = [
            {'t': 10.0, 'jobs': {'service': {'commit': 5 << 30}}, 'procs': {'1': {'private': 4 << 30, 'ws': 3 << 30}},
             'gpu': {'proc': {'1': [10 << 30, 0]}}},
            {'t': 12.0, 'jobs': {'service': {'commit': 9 << 30}}, 'procs': {'1': {'private': 8 << 30, 'ws': 6 << 30}},
             'gpu': {'proc': {'1': [20 << 30, 1 << 29]}}},
            {'t': 14.0, 'jobs': {'service': {'commit': 7 << 30}}, 'procs': {'1': {'private': 6 << 30, 'ws': 5 << 30}},
             'gpu': {'proc': {'1': [12 << 30, 0]}}},
        ]
        timeline = [{'phase': 'x4', 't0': 9.0, 't1': 11.0}, {'phase': 'vae_samplers', 't0': 11.0, 't1': 15.0}]
        s = sampler.summarize(samples, timeline)
        self.assertEqual(s['peak']['job_commit_gb']['service'], 9.0)
        self.assertEqual(s['peak']['gpu_dedicated_gb'], 20.0)
        self.assertEqual(s['peak']['gpu_shared_gb'], 0.5)
        self.assertEqual(s['per_phase']['x4']['job_commit_gb']['service'], 5.0)
        self.assertEqual(s['per_phase']['vae_samplers']['job_commit_gb']['service'], 9.0)
        self.assertEqual(s['per_phase']['vae_samplers']['seconds'], 4.0)
        self.assertEqual(s['samples'], 3)


if __name__ == '__main__':
    unittest.main()
