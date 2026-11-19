"""Gate G6 (engine design section 2.3) as a regression test: planes mapped, written and read through the Large-image engine's
paths add no commit, so a process inside a Windows Job capped well below the planes' size neither hits the cap nor grows its
private memory. tools/gate_g6.py runs the registered size (a 4 GiB Job, 16 GiB of planes); this test runs a smaller one."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == 'nt', 'Windows Job containment')
class PlanesAddNoCommit(unittest.TestCase):
    def test_planes_larger_than_the_job_limit(self):
        with tempfile.TemporaryDirectory(prefix='cu-g6-') as td:
            r = subprocess.run([sys.executable, '-B', str(ROOT / 'tools' / 'gate_g6.py'), '--dir', td, '--job-mib', '1024',
                                '--planes-gib', '2.5', '--private-max-mib', '512'], capture_output=True, text=True,
                               timeout=900, cwd=str(ROOT))
            res = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertTrue(res['pass'], res)
        self.assertGreater(res['child']['plane_bytes'], 2 * (1024 << 20))
        self.assertLess(res['job']['peak_job_memory_used'], 512 << 20)


if __name__ == '__main__':
    unittest.main()
