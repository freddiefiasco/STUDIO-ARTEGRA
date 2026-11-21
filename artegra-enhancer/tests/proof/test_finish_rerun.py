"""tools/proof/finish_rerun.py on a stand-in pack (no torch): the stage's own finish values and planes reach the node, the
re-run writes its own output plane, the asked band budget, process count and tier are passed only when the node declares
them (contracts.finish_inputs), else refused in plain words; and the build's real pack is found where torch is present."""
import importlib.util
import tempfile
import types
import unittest
from pathlib import Path

import numpy as np

from engine import planes
from tools.proof import finish_rerun

ROOT = Path(__file__).resolve().parents[2]
HAVE_TORCH = importlib.util.find_spec('torch') is not None


def stub_pack(optional):
    seen = {}

    class PlaneRef:
        def __init__(self, path, run_id):
            self.path, self.run_id = str(path), run_id

    class CUFinishBanded:
        @classmethod
        def INPUT_TYPES(cls):
            return {'required': {'creative': ('PLANE',)}, 'optional': {k: ('FLOAT',) for k in optional}}

        def run(self, **kw):
            seen.update(kw)
            src = planes.validate(kw['creative'].path)
            planes.from_array(kw['output_plane'], src.read_rows(0, src.shape[0]))
            return {'tier': kw.get('finish_tier', 'ladder')}
    return types.SimpleNamespace(PlaneRef=PlaneRef, CUFinishBanded=CUFinishBanded), seen


class Rerun(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.d = Path(self._t.name)
        a = np.random.default_rng(1).integers(0, 256, (16, 24, 3)).astype(np.uint8)
        for r in ('creative', 'structure', 'init', 'pre'):
            planes.from_array(self.d / f'{r}.plane', a)
        self.job = {'app': str(ROOT), 'planes': {r: str(self.d / f'{r}.plane') for r in ('creative', 'structure', 'init',
                                                                                         'pre')},
                    'inputs': {'smooth_lo': 0.2, 'output_plane': 'the/stage/output.plane', 'output_width': 24,
                               'output_height': 16, 'run_id': 'stage-run', 'finish': 'bxf-1'}}

    def tearDown(self):
        self._t.cleanup()

    def test_the_stage_values_and_planes_reach_the_node_and_the_output_is_its_own(self):
        pack, seen = stub_pack(('band_gb', 'processes', 'finish_tier'))
        out = self.d / 'rerun.plane'
        r = finish_rerun.rerun(ROOT, self.job, out, band_gb=3.0, processes=2, pack=pack)
        self.assertEqual(seen['output_plane'], str(out))                    # never the stage's own output plane
        self.assertEqual((seen['band_gb'], seen['processes']), (3.0, 2))
        self.assertNotIn('finish_tier', seen)
        self.assertEqual(seen['smooth_lo'], 0.2)
        self.assertEqual(seen['creative'].path, self.job['planes']['creative'])
        self.assertNotIn('protect', seen)
        self.assertEqual(r['sha256'], planes.validate(out).header['sha256'])
        self.assertEqual(r['settings'], {'band_gb': 3.0, 'processes': 2, 'finish_tier': None})

    def test_a_setting_the_node_does_not_declare_is_refused(self):
        pack, seen = stub_pack(())
        with self.assertRaises(finish_rerun.FinishInputMissing) as e:
            finish_rerun.rerun(ROOT, self.job, self.d / 'x.plane', band_gb=3.0, processes=2, pack=pack)
        self.assertIn('band_gb, processes', str(e.exception))
        self.assertIn('contracts.finish_inputs', str(e.exception))
        self.assertEqual(seen, {})
        finish_rerun.rerun(ROOT, self.job, self.d / 'y.plane', pack=pack)       # without settings: today's finish

    @unittest.skipUnless(HAVE_TORCH, 'needs torch (the worker interpreter)')
    def test_the_builds_own_pack_has_the_node(self):
        pack = finish_rerun.load_pack(ROOT)
        node = getattr(pack, 'CUFinishBanded', None) or pack.bxf.CUFinishBanded
        self.assertTrue(hasattr(pack, 'PlaneRef'))
        self.assertIsInstance(finish_rerun.node_optional(node), set)


if __name__ == '__main__':
    unittest.main()
