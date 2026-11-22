"""The finish's memory measurement at production values (tools/gate_g2.py, 5.0.2 wave 3): --scene-only writes a scene once and
--child <case> --lean finishes from it alone in a fresh process at the band budget and process count it is given (before
wave 3 the child ran one process whatever --processes said), without reading the output into memory: it records the output's
data sha256 (equal to the classic chain's on the same scene, and the same at 1 and 2 processes), the workspace's own peak
in bytes, the scratch folder's real size on disk, and it stops at a volume floor (exit 4, a disk-floor record). Sizes and
synthetic images only. Skipped where torch or scipy is not installed:
python -B -m unittest tests.worker.test_bxf_measure  (artegra-enhancer folder)."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HAVE = all(importlib.util.find_spec(m) is not None for m in ('torch', 'scipy'))
ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / 'tools' / 'gate_g2.py'
CASE = 'v4f-protect-release'


def run_gate(*args, timeout=600):
    """tools/gate_g2.py in a fresh process of this interpreter with this process's import path (as a driver runs it)."""
    boot = ('import sys, runpy; sys.path[:0] = %r; sys.argv = %r; runpy.run_path(sys.argv[0], run_name="__main__")'
            % ([p for p in sys.path if p], [str(GATE)] + [str(a) for a in args]))
    env = dict(os.environ, CUDA_VISIBLE_DEVICES='')
    return subprocess.run([sys.executable, '-I', '-S', '-B', '-c', boot], capture_output=True, text=True, timeout=timeout,
                          env=env)


@unittest.skipUnless(HAVE, 'torch and scipy are needed')
class TheLeanMeasurement(unittest.TestCase):
    def test_the_child_runs_at_the_process_count_and_budget_given_and_records_its_disk(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            out, work = Path(td) / 'out', Path(td) / 'work'
            size = ['--pre', '160x150', '--crop', '320x300']
            r = run_gate('--out', out, '--work', work, *size, '--scene-only')
            self.assertEqual(r.returncode, 0, r.stderr[-2000:])
            scene = json.loads((out / 'scene.json').read_text(encoding='utf8'))
            self.assertEqual(scene['stage'], [320, 300])
            self.assertTrue((work / 'scene' / 'release.npy').exists())
            recs = {}
            for gb, n in ((3.0, 2), (2.0, 1)):
                o = Path(td) / f'out-{n}'
                r = run_gate('--out', o, '--work', work, *size, '--child', CASE, '--what', 'bxf', '--lean', '--band-gb', gb,
                             '--processes', n)
                self.assertEqual(r.returncode, 0, r.stderr[-2000:])
                rec = json.loads((o / f'fresh-bxf-{CASE}.json').read_text(encoding='utf8'))
                self.assertEqual((rec['processes'], rec['band_gb']), (n, gb))
                self.assertEqual((rec['finish_record']['processes'], rec['finish_record']['band_gb']), (n, gb))
                self.assertTrue(rec['lean'])
                self.assertEqual(rec['output_shape'], [300, 320, 3])
                self.assertGreater(rec['workspace_peak_bytes'], 0)
                self.assertGreater(rec['disk']['scratch_max_bytes'], 0)
                self.assertGreater(rec['disk']['samples'], 0)
                self.assertIsNotNone(rec['disk']['volume_min_free_bytes'])
                self.assertGreater(rec['peak_commit_gib'], rec['inputs_only']['peak_commit_gib'])
                self.assertFalse(list(o.glob('*.npy')) + list(work.glob('fresh-*.npy')))      # a lean child saves no array
                recs[n] = rec
            self.assertEqual(recs[1]['output_sha256'], recs[2]['output_sha256'])         # the pool is pixel-neutral
            o = Path(td) / 'out-classic'
            r = run_gate('--out', o, '--work', work, *size, '--child', CASE, '--what', 'classic', '--lean')
            self.assertEqual(r.returncode, 0, r.stderr[-2000:])
            classic = json.loads((o / f'fresh-classic-{CASE}.json').read_text(encoding='utf8'))
            self.assertEqual(classic['output_sha256'], recs[1]['output_sha256'])           # tier 0: the classic's own bytes

    def test_a_volume_floor_stops_the_finish(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            out, work = Path(td) / 'out', Path(td) / 'work'
            size = ['--pre', '160x150']
            self.assertEqual(run_gate('--out', out, '--work', work, *size, '--scene-only').returncode, 0)
            r = run_gate('--out', out, '--work', work, *size, '--child', CASE, '--what', 'bxf', '--lean', '--min-free-gb', 1e9)
            self.assertEqual(r.returncode, 4, r.stderr[-2000:])
            floor = json.loads((out / f'fresh-bxf-{CASE}.disk-floor.json').read_text(encoding='utf8'))
            self.assertEqual(floor['floor_bytes'], int(1e9 * 2 ** 30))
            self.assertFalse((out / f'fresh-bxf-{CASE}.json').exists())


if __name__ == '__main__':
    unittest.main()
