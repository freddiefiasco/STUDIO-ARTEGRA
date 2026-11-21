"""tools/proof/r7.py on a stub (no card): host memory in place of the card's, so the probe's readings, rises, ratios, the
work drive's space and its record format are checked without a GPU. Inside a real Windows Job (the probe run as a child
of service/windows_job.WindowsJobProcess) the Job commit is read too; outside one it is recorded as unmeasured."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from tools.proof import r7

ROOT = Path(__file__).resolve().parents[2]
MIB = 1 << 20


class Stub(unittest.TestCase):
    def test_rows_rises_and_ratios_on_host_memory(self):
        alloc, free, label = r7.stub_allocator()
        with tempfile.TemporaryDirectory() as d:
            rec = r7.probe([32 * MIB, 96 * MIB], alloc, free, work_dir=d, settle_s=0.05, label=label)
        self.assertEqual(rec['format'], 'cu-r7-1')
        self.assertEqual([r['bytes'] for r in rec['rows']], [32 * MIB, 96 * MIB])
        self.assertIn('context', rec)
        self.assertGreater(rec['work_drive']['free_bytes'], 0)
        if sys.platform == 'win32':
            for r in rec['rows']:
                self.assertGreater(r['private_ratio'], 0.9, r)           # a touched host buffer is all commit
                self.assertLess(r['private_ratio'], 1.2, r)
                self.assertLess(abs(r['private_left_after_free']), 0.5 * r['bytes'], r)
        in_job = r7.own_job_memory()[0] is not None                      # a shell may run the tests inside a Job
        self.assertEqual('job_commit' in rec['unmeasured'], not in_job)

    @unittest.skipUnless(sys.platform == 'win32', 'Windows Jobs')
    def test_inside_a_job_the_job_commit_is_read(self):
        from service import windows_job
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            out = Path(d) / 'r7.json'
            env = dict(os.environ, PYTHONPATH=str(ROOT))
            p = windows_job.WindowsJobProcess([sys.executable, '-B', '-m', 'tools.proof.r7', '--stub', '--sizes-mib', '64',
                                               '--settle', '0.05', '--work', d, '--out', str(out)], cwd=str(ROOT), env=env,
                                              log_path=Path(d) / 'log.txt')
            try:
                self.assertEqual(p.wait(120), 0, (Path(d) / 'log.txt').read_text(encoding='utf8', errors='replace'))
            finally:
                p.close()
            rec = json.loads(out.read_text(encoding='utf8'))
        self.assertTrue(rec['stub'])
        self.assertNotIn('job_commit', rec['unmeasured'])
        row = rec['rows'][0]
        self.assertGreater(row['job_commit_ratio'], 0.9, row)
        self.assertLess(row['job_commit_ratio'], 1.2, row)

    def test_the_registered_record_names_the_sizes_and_the_disk_rule(self):
        from tools.proof import packets
        r = packets.r7_record()
        self.assertEqual(r['sizes_gib'], [2, 8, 16])
        self.assertEqual(r['disk_threshold_gb'], 130.0)
        self.assertIn('no pass or fail', r['rule'])


if __name__ == '__main__':
    unittest.main()
