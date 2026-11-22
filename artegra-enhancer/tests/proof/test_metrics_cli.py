"""tools/proof/metrics.py's measure command (python -m tools.proof.metrics measure): one case measured in the halo tools'
interpreter from .npy files, as tests/service/test_proof_rehearsal.py runs it from the service suite's interpreter. On the
synthetic step cards of test_halo_grid: three identical outputs are comparable and read not worse; a Lanczos-ringed BES
output reads worse. Skipped unless CU_HALO_TOOLS names the halo tools and this interpreter has their packages:
    CU_HALO_TOOLS=<halo tools folder> py -3.12 -B -m unittest tests.proof.test_metrics_cli"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

from tests.proof.test_halo_grid import HAVE, HALO, F, area, render, u8

APP = Path(__file__).resolve().parents[2]


def run(d, src, outs, pos):
    np.save(Path(d) / 'source.npy', src)
    args = []
    for k, v in outs.items():
        np.save(Path(d) / f'{k}.npy', v)
        args += [f"--{k.replace('_', '-')}", str(Path(d) / f'{k}.npy')]
    (Path(d) / 'seams.json').write_text(json.dumps(pos), encoding='utf8')
    r = subprocess.run([sys.executable, '-B', '-m', 'tools.proof.metrics', 'measure', '--halo', HALO, '--source',
                        str(Path(d) / 'source.npy'), '--seams', str(Path(d) / 'seams.json')] + args, cwd=str(APP),
                       capture_output=True, text=True, timeout=900, env=dict(os.environ, PYTHONIOENCODING='utf-8'))
    if r.returncode != 0:
        raise AssertionError(r.stderr[-2000:])
    return json.loads(r.stdout.strip().splitlines()[-1])


@unittest.skipUnless(HAVE, 'needs CU_HALO_TOOLS (the halo tools folder) and their interpreter (scipy, opencv, scikit-image)')
class MeasureCommand(unittest.TestCase):
    def test_identical_outputs_are_comparable_and_not_worse(self):
        clean = render(F)
        src, out = u8(area(clean, F)), u8(clean)
        with tempfile.TemporaryDirectory() as d:
            m = run(d, src, {'classic_a': out, 'bes_a': out, 'classic_b': out}, {'rows': [], 'cols': []})
        self.assertTrue(m['result']['comparable'], m['result'])
        self.assertTrue(m['result']['pass_metrics'], [r for r in m['rows'] if r.get('worse')][:3])
        self.assertTrue(m['halo']['sha256'])
        self.assertEqual(sorted(m['worst']), ['bes_a', 'classic_a', 'classic_b'])


if __name__ == '__main__':
    unittest.main()
