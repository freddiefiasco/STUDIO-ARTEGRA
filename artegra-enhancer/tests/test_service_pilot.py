"""CPU-only boundary checks. No service, helper process or model is started."""
import json
import os
import tempfile
import threading
import unittest
from email.message import Message
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from engine import fast_recipe, graph_v5t, controls
from service import config, engine_options, notify
from service.api import _Handler, ROUTES
from service.app import App, PORT_RANGE, bind, read_token
from service.errors import ApiError
from service.lifecycle import HostWatch, Lifecycle


class SessionTests(unittest.TestCase):
    def handler(self, path='/health', method='GET', token=None):
        h = object.__new__(_Handler)
        h.app = SimpleNamespace(token='s' * 64)
        h.path, h.command = path, method
        h.headers = Message()
        h.headers['Host'] = '127.0.0.1:18950'
        if token is not None:
            h.headers['Authorization'] = 'Bearer ' + token
        return h

    def test_all_registered_routes_require_token(self):
        for method, route, _ in ROUTES:
            h = self.handler(route.pattern, method)
            with self.subTest(method=method, route=route.pattern):
                with self.assertRaises(ApiError) as caught:
                    h._guard()
                self.assertEqual(caught.exception.status, 401)

    def test_tokens_are_per_session(self):
        self.handler(token='s' * 64)._guard()
        for token in ('previous-session', '\u00e9' * 64):
            with self.assertRaises(ApiError):
                self.handler(token=token)._guard()

    def test_image_query_token_is_narrow(self):
        for path in ('/api/media/m123/proxy', '/api/media/m123/mask/gate',
                     '/api/jobs/j123/items/i001/live.jpg', '/api/jobs/j123/items/i001/live-pass.jpg'):
            self.handler(path + '?token=' + 's' * 64)._guard()
        for path, method in (('/health', 'GET'), ('/api/settings', 'POST'),
                             ('/api/media/m123/proxy', 'DELETE')):
            with self.assertRaises(ApiError):
                self.handler(path + '?token=' + 's' * 64, method)._guard()

    def test_foreign_origin_and_host_remain_blocked(self):
        for key, value in [('Host', 'example.com'), ('Origin', 'https://example.com'),
                           ('Sec-Fetch-Site', 'cross-site')]:
            h = self.handler(token='s' * 64)
            h.headers.replace_header(key, value) if key in h.headers else h.headers.__setitem__(key, value)
            with self.assertRaises(ApiError) as caught:
                h._guard()
            self.assertEqual(caught.exception.status, 403)

    def test_invalid_auth_is_rejected_before_reading_body(self):
        h = self.handler()
        h._read_body, h._error = Mock(), Mock()
        h._dispatch('GET')
        h._read_body.assert_not_called()
        self.assertEqual(h._error.call_args.args[:2], (401, 'unauthorized'))
        self.assertTrue(h.close_connection)

    def test_binding_never_leaves_pilot_port_range(self):
        with patch('service.app.Server', side_effect=OSError('busy')) as server:
            with self.assertRaises(OSError):
                bind(18951, object)
        self.assertEqual({call.args[0] for call in server.call_args_list},
                         {('127.0.0.1', port) for port in PORT_RANGE})
        with patch('service.app.Server') as server:
            with self.assertRaises(ValueError):
                bind(80, object)
            server.assert_not_called()

    def test_token_file_validation(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'session.token'
            p.write_text('a' * 64, encoding='utf8')
            self.assertEqual(read_token(p), 'a' * 64)
            for value in ('short', 'a' * 31, 'a' * 32 + '\nsecret'):
                p.write_text(value, encoding='utf8')
                with self.assertRaises(config.ConfigError):
                    read_token(p)


class LifecycleTests(unittest.TestCase):
    def test_shutdown_closes_only_owned_resources_once(self):
        with tempfile.TemporaryDirectory() as td:
            token = Path(td) / 'token'
            token.write_text('s' * 64, encoding='utf8')
            app = App(SimpleNamespace(state=td, token_file=token))
            app.log, app.runner, app.lifecycle, app.server = Mock(), Mock(), Mock(), Mock()
            app._serving = True
            (Path(td) / 'service.json').write_text(json.dumps({'pid': os.getpid()}), encoding='utf8')
            app.stop()
            app.stop()
            app.runner.shutdown.assert_called_once()
            app.lifecycle.stop.assert_called_once()
            app.server.shutdown.assert_called_once()
            app.server.server_close.assert_called_once()
            self.assertFalse((Path(td) / 'service.json').exists())

    def test_notifications_cannot_reuse_existing_product_identity(self):
        self.assertEqual(notify.APP_ID, 'StudioArtegra.ArtegraEnhancerPilot')
        self.assertEqual(notify.PROTOCOL, 'artegra-enhancer-pilot')

    @unittest.skipUnless(os.name == 'nt', 'Windows process handle')
    def test_host_handle_is_retained_and_closed_without_touching_process(self):
        watch = HostWatch(Mock(), os.getpid())
        self.assertIsNotNone(watch._handle)
        watch.poll()
        self.assertFalse(watch.gone())
        watch.close()
        self.assertIsNone(watch._handle)
        watch.close()

    def test_exact_host_death_stops_even_with_work_waiting(self):
        alive = {42: True}
        log = Mock()
        watch = HostWatch(log, 42, probe=lambda pid: alive.get(pid, False))
        stopped = threading.Event()
        runner = Mock()
        runner.quiet.return_value = False
        lifecycle = Lifecycle(runner, log, watch=watch, on_exit=stopped.set)
        watch.poll()
        self.assertFalse(watch.gone())
        alive[42] = False
        watch.poll()
        lifecycle.tick()
        self.assertTrue(stopped.wait(1))
        self.assertTrue(lifecycle.closing)
        # A reused PID cannot resurrect a terminated host session.
        alive[42] = True
        watch.poll()
        self.assertTrue(watch.gone())
        lifecycle.stop()

    def test_missing_host_is_rejected(self):
        with self.assertRaises(OSError):
            HostWatch(Mock(), 42, probe=lambda _: False)


class PortableConfigTests(unittest.TestCase):
    def test_relative_paths_resolve_at_config_not_working_directory(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = root / 'config.json'
            p.write_text(json.dumps({'models_dir': 'models'}), encoding='utf8')
            cfg = config.load(root / 'state', config_file=p)
            self.assertEqual(cfg.models_dir, root / 'models')
            self.assertEqual(set(config.DEFAULTS), set(config.PATH_KEYS))

    def test_unknown_key_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'config.json'
            p.write_text('{"host_pid": 12}', encoding='utf8')
            with self.assertRaises(config.ConfigError):
                config.load(td)

    def test_pack_hashes_and_tamper_detection(self):
        import shutil
        result = config.verify_node_pack(config.DEFAULTS['node_pack_dir'])
        self.assertTrue(result['ok'], result['details'])
        with tempfile.TemporaryDirectory() as td:
            pack = Path(td) / 'claude_creative'
            shutil.copytree(config.DEFAULTS['node_pack_dir'], pack, ignore=shutil.ignore_patterns('__pycache__'))
            shutil.copyfile(config.DEFAULTS['node_pack_dir'].parent / 'MANIFEST.json', Path(td) / 'MANIFEST.json')
            (pack / 'noise.py').write_text('# modified\n', encoding='utf8')
            self.assertFalse(config.verify_node_pack(pack)['ok'])

    def test_preview_fast_recipe_and_standard_is_stable(self):
        self.assertTrue(fast_recipe.installed())
        self.assertTrue(engine_options.FAST_PROVEN)
        self.assertFalse(engine_options.FAST_SPLIT_PROVEN)
        params, _ = controls.resolve({})
        first = graph_v5t.build_product('input.png', 1024, 1024, params, 'output')
        fast, info = fast_recipe.build('input.png', 1024, 1024, params, 'output')
        lora = next(n for n in fast.values() if n['class_type'] == 'LoraLoaderModelOnly')
        self.assertEqual(lora['inputs']['lora_name'], 'Hyper-SDXL-8steps-CFG-lora.safetensors')
        self.assertEqual(lora['inputs']['strength_model'], 0.25)
        for node in fast.values():
            if node['class_type'] == 'KSampler':
                self.assertEqual(node['inputs']['steps'], 8)
                self.assertEqual(node['inputs']['cfg'], 5.0)
        self.assertEqual(info['spot_options']['seam_overlap'], 16)
        self.assertEqual(first, graph_v5t.build_product('input.png', 1024, 1024, params, 'output'))

    def test_fast_files_scale_and_look_gates(self):
        self.assertFalse(engine_options.fast_info(files_ok=False)['available'])
        available = engine_options.fast_info(files_ok=True)
        self.assertTrue(available['available'])
        self.assertEqual(engine_options.fast_refusal({'mode': 'fast', 'scale': 4, 'preset': 'Default'}, available)[0], 'scale')
        self.assertEqual(engine_options.fast_refusal({'mode': 'fast', 'scale': 2, 'preset': 'Strong'}, available)[0], 'look')
        self.assertIsNone(engine_options.fast_refusal({'mode': 'fast', 'scale': 2, 'preset': 'Default'}, available))


if __name__ == '__main__':
    unittest.main()
