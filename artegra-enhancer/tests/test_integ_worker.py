"""5.0.2: every worker loads the Large-image node pack beside the classic one (BUILD-WAVE-2 package integ, item 1; contract
worker_banded). Sizes and stubs only: no engine is started and no port is bound.

- comfy_command whitelists claude_creative and claude_banded, and nothing else of 5.0.1's command line changes; the proof
  harness then adds only its own instrumentation pack.
- The classic start check stays classic-only: a worker whose Large-image pack failed to load (ComfyUI logs the failed import and
  goes on) still starts, records the missing classes in banded_missing and says so in its log.
- banded_missing: None while unknown, [] when every Large-image class is there, else the sorted missing classes.
- required_inputs(banded=True) covers every input the Large-image graphs give the Large-image pack's nodes (both live modes,
  one and two cards, both parts of the split finish); a pack that does not declare one is reported in the log, never fatal.
- dev_vram: a developer build's engine caps the card when it sees CU_DEV_VRAM_CAP_GB, a release build's ignores it; the
  worker's environment passes the variable through unchanged (no new worker variable)."""
import importlib.util
import logging
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from engine import graph_banded, graph_v5t
from service import fake_comfy, memory_policy, workers

ROOT = Path(__file__).resolve().parents[1]
CLASSIC_501_TAIL = ['--disable-all-custom-nodes', '--whitelist-custom-nodes', 'claude_creative']


def cfg(d):
    d = Path(d)
    return SimpleNamespace(runtime_python=d / 'py' / 'python.exe', comfy_main=d / 'ComfyUI' / 'main.py',
                           site_packages=d / 'site', models_dir=d / 'models', claude_models_dir=d / 'cm',
                           node_pack_dir=d / 'app' / 'node_pack' / 'claude_creative', vae_approx_dir=d / 'va' / 'v',
                           workers_dir=d / 'workers')


def fake_info(drop=(), drop_inputs=None):
    """The fake engine's /object_info (every classic and Large-image class), less `drop` classes and `drop_inputs`."""
    fc = object.__new__(fake_comfy.FakeComfy)
    fc.faults = []
    info = fake_comfy.FakeComfy.object_info(fc)
    for c in drop:
        info.pop(c, None)
    for c, names in (drop_inputs or {}).items():
        for part in ('required', 'optional'):
            for k in names:
                info[c]['input'][part].pop(k, None)
    return info


class Log:
    def __init__(self):
        self.lines = []

    def _add(self, level):
        def f(event, msg='', *a, **k):
            self.lines.append((level, event, msg, k.get('data')))
            return 'ref'
        return f

    def __getattr__(self, name):
        if name in ('info', 'warn', 'error', 'debug'):
            return self._add(name)
        if name == 'exception':
            return lambda event, msg, e, **k: self.lines.append(('exception', event, msg, k.get('data'))) or 'ref'
        raise AttributeError(name)

    def events(self, level=None):
        return [e for lv, e, _, _ in self.lines if level is None or lv == level]


def worker(d, multi=False, log=None):
    c = cfg(d)
    settings = SimpleNamespace(get=lambda: {'ram_cap_gb': 59.0})
    if multi:
        return workers.MultiCardWorker((0, 1), c, settings, log or Log(), 'fake')
    return workers.Worker(0, c, settings, log or Log(), 'fake')


class TheCommandLine(unittest.TestCase):
    def test_both_packs_are_whitelisted_and_nothing_else_changes(self):
        with tempfile.TemporaryDirectory() as d:
            c = cfg(d)
            cmd = workers.comfy_command(c, Path(d) / 'w', 18999, Path(d) / 'w' / 'x.yaml')
            i = cmd.index('--whitelist-custom-nodes')
            self.assertEqual(cmd[i + 1:], ['claude_creative', 'claude_banded'])
            self.assertEqual(cmd[i - 1], '--disable-all-custom-nodes')
            # 5.0.1's command is this one less the one added last token (its tail was CLASSIC_501_TAIL)
            self.assertEqual(cmd[-1], 'claude_banded')
            self.assertEqual(cmd.count('claude_banded'), 1)
            self.assertEqual(cmd[:-1][-len(CLASSIC_501_TAIL):], CLASSIC_501_TAIL)
            self.assertEqual(workers.NODE_PACKS, ('claude_creative', 'claude_banded'))
            for profile in memory_policy.PROFILES.values():
                p = workers.comfy_command(c, Path(d) / 'w', 18999, Path(d) / 'w' / 'x.yaml', profile)
                self.assertEqual(p[p.index('--whitelist-custom-nodes') + 1:], ['claude_creative', 'claude_banded'])

    def test_the_packs_folder_holds_both_packs(self):
        """The model-paths file names node_pack as the custom-nodes folder; both whitelisted names are folders in it."""
        with tempfile.TemporaryDirectory() as d:
            c = cfg(d)
            yaml = workers.extra_model_paths_yaml(c)
            self.assertIn(f'custom_nodes: {Path(c.node_pack_dir).parent.name}', yaml)
        for name in workers.NODE_PACKS:
            self.assertTrue((ROOT / 'node_pack' / name / '__init__.py').is_file(), name)

    def test_the_proof_harness_adds_only_its_instrumentation(self):
        from tools.proof import harness
        with tempfile.TemporaryDirectory() as d:
            c = cfg(d)
            prod = workers.comfy_command(c, Path(d) / 'w', 18999, Path(d) / 'w' / 'x.yaml')
            mine, extra = harness.worker_command(c, Path(d) / 'w', 18999, Path(d) / 'w' / 'x.yaml', Path(d) / 'p')
            self.assertEqual(extra['whitelist_added'], ['cu_proof'])
            self.assertEqual([a for a in mine if a != 'cu_proof'], prod)


class BandedMissing(unittest.TestCase):
    def test_none_before_any_start_and_for_no_object_info(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(worker(d).banded_missing)
            self.assertIsNone(worker(d, multi=True).banded_missing)
            self.assertIsNone(object.__new__(workers.Worker).banded_missing)     # stubs made without __init__ too
        for info in (None, {}, [], 'text'):
            self.assertIsNone(workers.missing_banded(info))

    def test_an_empty_list_when_every_large_image_class_is_there(self):
        self.assertEqual(workers.missing_banded(fake_info()), [])

    def test_the_sorted_missing_classes(self):
        gone = ('CUSam3DetectLean', 'ClaudeSpotTilesBanded', 'CUCannyPlane')
        self.assertEqual(workers.missing_banded(fake_info(drop=gone)), sorted(gone))
        only_classic = fake_info(drop=graph_banded.NODE_SPECS)
        self.assertEqual(workers.missing_banded(only_classic), sorted(graph_banded.NODE_SPECS))

    def test_after_a_start_and_reset_by_a_stop(self):
        with tempfile.TemporaryDirectory() as d:
            w = worker(d)
            w.client = SimpleNamespace(object_info=lambda: fake_info(drop=('CUDecodePlane',)))
            w._check_nodes()
            self.assertEqual(w.banded_missing, ['CUDecodePlane'])
            w._teardown('test')
            self.assertIsNone(w.banded_missing)


class TheClassicStartCheckStaysClassic(unittest.TestCase):
    def test_required_classes_and_inputs_are_classic_only(self):
        classic = set(workers.required_classes())
        self.assertFalse(classic & set(graph_banded.NODE_SPECS))
        self.assertFalse(set(workers.required_inputs()) & set(graph_banded.NODE_SPECS))
        self.assertFalse(set(workers.required_inputs(multi=True)) & set(graph_banded.NODE_SPECS))

    def test_a_worker_whose_large_image_pack_failed_to_load_still_starts(self):
        """The real start path (_start: the engine answers, the classic check, the progress feed), on an engine whose
        /object_info has no Large-image class, as after ComfyUI logged the pack's failed import."""
        with tempfile.TemporaryDirectory() as d:
            log = Log()
            w = worker(d, log=log)
            info = fake_info(drop=graph_banded.NODE_SPECS)

            class Fake:
                def __init__(self, *a, **k):
                    self.alive = True

                def start(self):
                    return 1

                def stop(self):
                    self.alive = False

            class Client:
                def __init__(self, port):
                    pass

                def system_stats(self, timeout=None):
                    return {'devices': [{'name': 'Test graphics card 1', 'vram_free': 30 << 30}]}

                def object_info(self):
                    return info

            class Ws:
                def __init__(self, *a):
                    self.last_message, self.disconnects, self.connected = {'type': 'status'}, 0, True

                def start(self):
                    pass

                def stop(self):
                    pass
            with mock.patch.object(fake_comfy, 'FakeComfy', Fake), mock.patch.object(workers, 'ComfyClient', Client), \
                    mock.patch.object(workers, 'WsListener', Ws):
                w.ensure_started()
            self.assertEqual(w.state, 'ready')
            self.assertEqual(w.banded_missing, sorted(graph_banded.NODE_SPECS))
            self.assertIn('worker_banded_missing', log.events('warn'))
            self.assertIn('worker_ready', log.events('info'))
            self.assertNotIn('worker_start_failed', log.events())

    def test_a_missing_classic_class_still_stops_the_start(self):
        with tempfile.TemporaryDirectory() as d:
            w = worker(d)
            w.client = SimpleNamespace(object_info=lambda: fake_info(drop=('ClaudeV4Finish',)))
            with self.assertRaises(workers.WorkerError):
                w._check_nodes()

    def test_a_banded_check_that_breaks_is_logged_and_never_stops_the_start(self):
        with tempfile.TemporaryDirectory() as d:
            log = Log()
            w = worker(d, log=log)
            w.client = SimpleNamespace(object_info=lambda: fake_info())
            with mock.patch.object(workers, 'banded_graphs', side_effect=RuntimeError('broken')):
                w._check_nodes()
            # 5.0.2 wave 3 (integ's finding): the classes read from /object_info stay recorded; only the input check broke
            self.assertEqual(w.banded_missing, [])
            self.assertIn('worker_banded_unchecked', log.events('warn'))

    def test_a_class_check_that_breaks_leaves_it_unknown(self):
        with tempfile.TemporaryDirectory() as d:
            log = Log()
            w = worker(d, log=log)
            w.client = SimpleNamespace(object_info=lambda: fake_info())
            with mock.patch.object(workers, 'missing_banded', side_effect=RuntimeError('broken')):
                w._check_nodes()
            self.assertIsNone(w.banded_missing)
            self.assertIn('worker_banded_unchecked', log.events('warn'))

    def test_a_missing_class_is_recorded_even_when_the_input_check_breaks(self):
        with tempfile.TemporaryDirectory() as d:
            log = Log()
            w = worker(d, log=log)
            w.client = SimpleNamespace(object_info=lambda: fake_info(drop=('CUFinishBanded',)))
            def broken(info, multi=False, banded=False):
                if banded:
                    raise RuntimeError('broken')
                return {}
            with mock.patch.object(workers, 'undeclared_inputs', broken):
                w._check_nodes()
            self.assertEqual(w.banded_missing, ['CUFinishBanded'])
            self.assertIn('worker_banded_missing', log.events('warn'))
            self.assertIn('worker_banded_unchecked', log.events('warn'))


class LargeImageInputs(unittest.TestCase):
    def test_every_large_image_class_and_its_inputs(self):
        req = workers.required_inputs(banded=True)
        self.assertEqual(set(req), set(graph_banded.NODE_SPECS))           # every node of the merged NODE_SPECS is used
        for cls, names in req.items():
            declared = set(graph_banded.NODE_SPECS[cls][0]) | set(graph_banded.NODE_OPTIONAL.get(cls, ()))
            self.assertLessEqual(set(names), declared, cls)
            self.assertLessEqual(set(graph_banded.NODE_SPECS[cls][0]), set(names), cls)
        self.assertIn('brownian_cache', req['ClaudeSpotTilesBanded'])        # the capped-cache constant's input
        self.assertTrue({'protect', 'release'} <= set(req['CUFinishBanded']))
        self.assertTrue({'protect', 'release'} <= set(req['CUPlaneCheckpoint']))

    def test_both_live_modes_and_two_cards(self):
        one, two = workers.required_inputs(banded=True), workers.required_inputs(multi=True, banded=True)
        self.assertIn('live_preview', one['ClaudeSpotTilesBanded'])
        self.assertFalse({'window_split', 'balance', 'weights'} & set(one['ClaudeSpotTilesBanded']))
        self.assertTrue({'window_split', 'balance', 'weights'} <= set(two['ClaudeSpotTilesBanded']))
        lives = {g[n]['inputs'].get('live_preview') for g in workers.banded_graphs() for n in g
                 if g[n]['class_type'] == 'ClaudeSpotTilesBanded'}
        self.assertTrue(set(graph_v5t.PRODUCT_LIVE_MODES) <= lives)
        multi = [g for g in workers.banded_graphs(multi=True)
                 if any(v['class_type'] == 'MultiGPU_WorkUnits' for v in g.values())]
        self.assertTrue(multi)

    def test_the_engine_declares_them_or_the_log_says_so(self):
        info = fake_info()
        self.assertEqual(workers.undeclared_inputs(info, banded=True), {})
        self.assertEqual(workers.undeclared_inputs(info, multi=True, banded=True), {})
        old = fake_info(drop_inputs={'ClaudeSpotTilesBanded': ('brownian_cache',)})
        self.assertEqual(workers.undeclared_inputs(old, banded=True), {'ClaudeSpotTilesBanded': ['brownian_cache']})
        self.assertEqual(workers.undeclared_inputs(old), {})                          # the classic check does not see it
        with tempfile.TemporaryDirectory() as d:
            for multi in (False, True):
                log = Log()
                w = worker(d, multi=multi, log=log)
                w.client = SimpleNamespace(object_info=lambda: old)
                w._check_nodes()                                                       # never fatal for a classic worker
                self.assertEqual(w.banded_missing, [])
                warn = [x for x in log.lines if x[1] == 'worker_banded_inputs']
                self.assertEqual(len(warn), 1)
                self.assertEqual(warn[0][3]['undeclared_inputs'], {'ClaudeSpotTilesBanded': ['brownian_cache']})

    def test_the_finish_plan_constants_are_among_the_graphs(self):
        """contract finish_inputs: graph_banded passes band_gb, processes and finish_tier to CUFinishBanded when the plan
        carries bxf_band_gb, bxf_processes and finish_tier, so the check builds graphs with them too (at the base the builder
        ignores them; after the merge the inputs they give are checked)."""
        seen = []
        real = graph_banded.build_product

        def spy(*a, **k):
            seen.append(dict(k.get('constants') or {}))
            return real(*a, **k)
        with mock.patch.object(graph_banded, 'build_product', spy):
            workers.required_inputs(banded=True)
        self.assertIn({'bxf_band_gb': 3.0, 'bxf_processes': 2, 'finish_tier': 'bxf'}, seen)
        self.assertIn({}, seen)
        self.assertIn({'brownian_cache': 8}, seen)

    def test_a_missing_class_is_not_also_an_undeclared_input(self):
        info = fake_info(drop=('CUFinishBanded',))
        self.assertNotIn('CUFinishBanded', workers.undeclared_inputs(info, banded=True))


def pack_tree(td, channel):
    """node_pack/claude_banded and service/build_channel.py of a build of this tree in `channel` ('dev' is what
    tools/make_dev_build.py writes)."""
    from tools import make_dev_build
    app = Path(td) / f'app-{channel}'
    shutil.copytree(ROOT / 'node_pack' / 'claude_banded', app / 'node_pack' / 'claude_banded',
                    ignore=shutil.ignore_patterns('__pycache__'))
    text = (ROOT / 'service' / 'build_channel.py').read_text(encoding='utf8')
    if channel == 'dev':
        text = text.replace(make_dev_build.RELEASE_LINES, make_dev_build.channel_source())
    (app / 'service').mkdir(parents=True)
    (app / 'service' / 'build_channel.py').write_text(text, encoding='utf8')
    return app / 'node_pack' / 'claude_banded'


def load_as_comfyui(pack_dir, name):
    """The pack's __init__.py executed as ComfyUI's custom-node loader does (nodes.load_custom_node: the module registered in
    sys.modules under its name before it runs)."""
    spec = importlib.util.spec_from_file_location(name, Path(pack_dir) / '__init__.py',
                                                  submodule_search_locations=[str(pack_dir)])
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        for m in [m for m in sys.modules if m == name or m.startswith(name + '.')]:
            del sys.modules[m]
    return mod


class StubCuda:
    def __init__(self, totals_gb):
        self.totals, self.set = totals_gb, []

    def is_available(self):
        return bool(self.totals)

    def device_count(self):
        return len(self.totals)

    def get_device_properties(self, i):
        return SimpleNamespace(total_memory=int(self.totals[i] * (1 << 30)))

    def set_per_process_memory_fraction(self, frac, i):
        self.set.append((i, frac))


class TheDeveloperVramHook(unittest.TestCase):
    """With the pack whitelisted, the engine imports dev_vram (the pack's __init__ does), so the R5 cap acts in a developer
    build's worker and a release build's ignores it. A stub stands in for torch.cuda (no card here)."""

    def run_pack(self, channel, env):
        torch = SimpleNamespace(cuda=StubCuda([32.0]))
        with tempfile.TemporaryDirectory() as td:
            pack = pack_tree(td, channel)
            with mock.patch.dict(sys.modules, {'torch': torch}), mock.patch.dict('os.environ', env, clear=False), \
                    self.assertLogs('claude_banded', 'WARNING') as logs:
                if 'CU_DEV_VRAM_CAP_GB' not in env:
                    logging.getLogger('claude_banded').warning('marker')
                mod = load_as_comfyui(pack, f'cu_integ_pack_{channel}')
        return mod, torch, logs.output

    def test_a_developer_build_caps_the_card(self):
        mod, torch, logs = self.run_pack('dev', {'CU_DEV_VRAM_CAP_GB': '12'})
        self.assertEqual(torch.cuda.set, [(0, 12 / 32.0)])
        self.assertEqual(mod.dev_vram.CAPS, [{'device': 0, 'total_gb': 32.0, 'fraction': 0.375}])
        self.assertTrue(any('DEVELOPER BUILD' in x for x in logs))

    def test_a_release_build_ignores_it_and_says_so(self):
        mod, torch, logs = self.run_pack('release', {'CU_DEV_VRAM_CAP_GB': '12'})
        self.assertEqual(torch.cuda.set, [])
        self.assertIsNone(mod.dev_vram.CAPS)
        self.assertTrue(any('release build' in x for x in logs))

    def test_without_the_variable_nothing_happens_in_either_build(self):
        with mock.patch.dict('os.environ', {}, clear=False):
            import os
            os.environ.pop('CU_DEV_VRAM_CAP_GB', None)
            for channel in ('dev', 'release'):
                mod, torch, logs = self.run_pack(channel, {})
                self.assertEqual(torch.cuda.set, [])
                self.assertIsNone(mod.dev_vram.CAPS)
                self.assertEqual(logs, ['WARNING:claude_banded:marker'])

    def test_the_worker_environment_passes_the_variable_through(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict('os.environ', {'CU_DEV_VRAM_CAP_GB': '12'}):
            env = worker(d)._env()
            self.assertEqual(env['CU_DEV_VRAM_CAP_GB'], '12')
        with tempfile.TemporaryDirectory() as d, mock.patch.dict('os.environ', {}, clear=False):
            import os
            os.environ.pop('CU_DEV_VRAM_CAP_GB', None)
            self.assertNotIn('CU_DEV_VRAM_CAP_GB', worker(d)._env())


if __name__ == '__main__':
    unittest.main()
