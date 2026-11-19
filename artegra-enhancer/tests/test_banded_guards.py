"""Guards around the Large-image engine (engine design section 3): the developer-only force switch and build channel (G0g),
the registered hunk of Runner._run_stage, the second node pack and its manifest (D9), its declared node classes against the
graph builder, import side effects (G0d), the streamed reflect pad, and plan matching for resumes. Sizes and synthetic
arrays only."""
import difflib
import importlib.util
import inspect
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from engine import banded_plan, graph_banded, planes, planner
from service import banded_runner, build_channel, config, images
from service.util import same_plan

ROOT = Path(__file__).resolve().parents[1]
FIX = Path(__file__).parent / 'fixtures'


def load_banded_pack():
    spec = importlib.util.spec_from_file_location('claude_banded_for_tests', ROOT / 'node_pack' / 'claude_banded' / '__init__.py',
                                                  submodule_search_locations=[str(ROOT / 'node_pack' / 'claude_banded')])
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class G0gTheForceSwitchIsDeveloperOnly(unittest.TestCase):
    def test_the_source_tree_is_the_release_channel(self):
        self.assertEqual(build_channel.CHANNEL, 'release')
        self.assertIsNone(build_channel.DEV_PROVEN_MP)
        self.assertFalse(build_channel.is_dev())
        self.assertFalse(build_channel.apply_dev_proven())

    def test_the_release_build_refuses_a_developer_tree(self):
        from tools import build_release
        build_release.check_release_channel(ROOT)
        from tools import make_dev_build
        with tempfile.TemporaryDirectory() as td:
            dest = make_dev_build.make(Path(td) / 'dev', proven={'ws128': 640.0})
            text = (dest / 'service' / 'build_channel.py').read_text(encoding='utf8')
            self.assertIn("CHANNEL = 'dev'", text)
            self.assertIn("'ws128': 640.0", text)
            with self.assertRaises(RuntimeError):
                build_release.check_release_channel(dest)

    def test_the_default_configuration_never_sets_it(self):
        from service import settings
        self.assertNotIn('dev_force_engine', json.dumps(settings.Settings.__init__.__defaults__ or ()))
        for p in (ROOT / 'service').glob('*.py'):
            if p.name in ('runner.py', 'build_channel.py'):
                continue
            self.assertNotIn('dev_force_engine', p.read_text(encoding='utf8'), p.name)

    def test_developer_sizes_apply_only_in_a_developer_build(self):
        before = dict(banded_plan.BANDED_PROVEN_MP)
        with mock.patch.object(build_channel, 'DEV_PROVEN_MP', {'ws128': 640.0}):
            self.assertFalse(build_channel.apply_dev_proven())               # release channel: ignored
            self.assertEqual(banded_plan.BANDED_PROVEN_MP, before)
            with mock.patch.object(build_channel, 'CHANNEL', 'dev'), mock.patch.dict(banded_plan.BANDED_PROVEN_MP, {}):
                self.assertTrue(build_channel.apply_dev_proven())
                self.assertEqual(banded_plan.BANDED_PROVEN_MP['ws128'], 640.0)
        self.assertEqual(banded_plan.BANDED_PROVEN_MP, before)


class TheRegisteredHunkOfRunStage(unittest.TestCase):
    def test_run_stage_differs_from_501_only_by_the_registered_patch(self):
        from service.runner import Runner
        old = (FIX / 'run_stage_5_0_1.txt').read_text(encoding='utf8')
        new = inspect.getsource(Runner._run_stage).replace('\r\n', '\n')
        diff = ''.join(difflib.unified_diff(old.splitlines(True), new.splitlines(True), 'run_stage_5_0_1', 'run_stage_5_0_2', n=1))
        self.assertEqual(diff, (FIX / 'run_stage_5_0_2.diff').read_text(encoding='utf8'))

    def test_the_fixture_is_501s_run_stage(self):
        text = (FIX / 'run_stage_5_0_1.txt').read_text(encoding='utf8')
        self.assertTrue(text.startswith('    def _run_stage(self, w, ctx, job, params, k, n):\n'))
        self.assertIn("graph_v5t.build_product(name, pw, ph, pk, prefix, f=f, s=s,", text)
        self.assertNotIn('banded', text)


class TheSecondNodePack(unittest.TestCase):
    def test_both_packs_verify_and_the_classic_tree_hash_is_501s_but_the_sam_exception(self):
        classic = config.verify_node_pack(ROOT / 'node_pack' / 'claude_creative')
        banded = config.verify_banded_pack(ROOT / 'node_pack' / 'claude_creative')
        self.assertTrue(classic['ok'], classic)
        self.assertTrue(banded['ok'], banded)
        # 5.0.1's tree was 3d8e1feb...; 5.0.2's differs by the registered lean-SAM exception alone (test_engine_identity G0c)
        exc = json.loads((FIX / 'sam_lean_5_0_2.json').read_text(encoding='utf8'))
        self.assertEqual(classic['tree_sha256'], exc['classic_tree_sha256'])
        self.assertNotEqual(classic['tree_sha256'], '3d8e1feb3359a0d1020ffd1fe4468005c7bfc784b1f3545996589eb769674935')
        self.assertNotEqual(banded['tree_sha256'], classic['tree_sha256'])

    def test_the_manifest_is_current(self):
        from tools import make_banded_manifest
        self.assertEqual(make_banded_manifest.manifest(),
                         json.loads((ROOT / 'node_pack' / 'MANIFEST-banded.json').read_text(encoding='utf8')))

    def test_a_changed_or_extra_file_fails_verification(self):
        import shutil
        with tempfile.TemporaryDirectory() as td:
            np_dir = Path(td) / 'node_pack'
            shutil.copytree(ROOT / 'node_pack', np_dir, ignore=shutil.ignore_patterns('__pycache__'))
            (np_dir / 'claude_banded' / 'extra.py').write_text('x = 1\n', encoding='utf8')
            self.assertFalse(config.verify_banded_pack(np_dir / 'claude_creative')['ok'])
            (np_dir / 'claude_banded' / 'extra.py').unlink()
            self.assertTrue(config.verify_banded_pack(np_dir / 'claude_creative')['ok'])
            with open(np_dir / 'claude_banded' / '__init__.py', 'a', encoding='utf8') as f:
                f.write('\n')
            self.assertFalse(config.verify_banded_pack(np_dir / 'claude_creative')['ok'])
            self.assertTrue(config.verify_node_pack(np_dir / 'claude_creative')['ok'])   # the classic pack is unaffected

    def test_declared_classes_match_the_graph_builder(self):
        pack = load_banded_pack()
        self.assertEqual(sorted(pack.NODE_CLASS_MAPPINGS), graph_banded.classes())
        for name, cls in pack.NODE_CLASS_MAPPINGS.items():
            req, outs = graph_banded.NODE_SPECS[name]
            it = cls.INPUT_TYPES()
            self.assertEqual(sorted(it['required']), sorted(req), name)
            self.assertEqual(sorted(it.get('optional', {})), sorted(graph_banded.NODE_OPTIONAL.get(name, ())), name)
            self.assertEqual(tuple(cls.RETURN_TYPES), tuple(outs), name)
        self.assertEqual(set(pack.BUILT) | set(pack.NOT_BUILT), set(pack.NODE_CLASS_MAPPINGS))
        self.assertIn('CUFinishBanded', pack.BUILT)

    def test_a_node_not_built_stops_with_a_plain_error(self):
        pack = load_banded_pack()
        for name in pack.NOT_BUILT:
            with self.assertRaises(pack.NotBuilt) as e:
                getattr(pack.NODE_CLASS_MAPPINGS[name](), pack.NODE_CLASS_MAPPINGS[name].FUNCTION)()
            self.assertIn('not built', str(e.exception))

    def test_a_plane_handle_is_not_a_tensor(self):
        pack = load_banded_pack()
        with tempfile.TemporaryDirectory() as td:
            p = planes.from_array(Path(td) / 'h.plane', np.zeros((8, 8, 3), np.uint8))
            ref = pack.PlaneRef(p.path, 'r')
            for name in ('to', 'cpu', 'cuda', 'numpy', 'float', 'movedim', 'permute'):
                with self.assertRaises(TypeError):
                    getattr(ref, name)

    def test_g0d_importing_the_pack_changes_no_global_state(self):
        from PIL import Image
        mods = set(sys.modules)
        state = (Image.MAX_IMAGE_PIXELS, np.get_printoptions(), sys.getrecursionlimit(), list(sys.path))
        load_banded_pack()
        self.assertEqual((Image.MAX_IMAGE_PIXELS, np.get_printoptions(), sys.getrecursionlimit(), list(sys.path)), state)
        self.assertEqual({m for m in set(sys.modules) - mods if not m.startswith('claude_banded_for_tests')}, set())


class StreamedReflectPad(unittest.TestCase):
    def test_equals_the_classic_pad(self):
        rng = np.random.default_rng(5)
        for (h, w, ph, pw) in ((64, 3500, 64, 3500), (100, 333, 104, 336), (1301, 777, 1304, 784), (65, 65, 72, 72)):
            a = rng.integers(0, 256, (h, w, 3), dtype=np.uint8)
            want = images.pad_reflect(a, (pw, ph))
            with tempfile.TemporaryDirectory() as td:
                src = planes.from_array(Path(td) / 's.plane', a)
                dst = planes.Plane.create(Path(td) / 'd.plane', (ph, pw, 3))
                banded_runner.pad_plane(src, dst, (pw, ph), band=288)
                np.testing.assert_array_equal(dst.read_rows(0, ph), want)
                dst2 = planes.Plane.create(Path(td) / 'e.plane', (ph, pw, 3))
                banded_runner.pad_plane(a, dst2, (pw, ph), band=1152)
                np.testing.assert_array_equal(dst2.read_rows(0, ph), want)


class PlanMatching(unittest.TestCase):
    def test_a_501_record_matches_the_classic_plan_and_never_a_banded_one(self):
        old = planner.plan(2048, 2048, 2, ram_cap_gb=59.0).to_dict()
        self.assertTrue(same_plan(old, planner.plan(2048, 2048, 2, ram_cap_gb=59.0)))
        forced = banded_plan.plan_forced(planner.plan(2048, 2048, 2, ram_cap_gb=59.0), 59.0)
        self.assertFalse(same_plan(old, forced))
        self.assertTrue(same_plan(forced.to_dict(), banded_plan.plan_forced(planner.plan(2048, 2048, 2, ram_cap_gb=122.2), 122.2)))
        other = forced.to_dict()
        other['banded'] = dict(other['banded'], finish='bxf-1h')
        self.assertFalse(same_plan(forced.to_dict(), other))


if __name__ == '__main__':
    unittest.main()
