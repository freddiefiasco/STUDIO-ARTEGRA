"""App implementation."""
import argparse
import json
import os
import signal
import sys
import threading
import time
import urllib.request
from pathlib import Path

from service import API_CONTRACT, SERVICE, VERSION, config, engine_options
from service.api import Server, make_handler
from service.lifecycle import HostWatch, Lifecycle
from service.logs import Logger
from service.media import MediaLibrary
from service.runner import Runner
from service.settings import Settings, SettingsError
from service.store import JobStore
from service.util import atomic_write_json, now_iso, read_json

PORT_RANGE = range(18950, 18970)
DEFAULT_STATE = str(Path(os.environ.get('LOCALAPPDATA') or Path.home() / '.local' / 'share') / 'ArtegraEnhancer' / 'state')


def read_token(path):
    token = Path(path).read_text(encoding='utf8').strip()
    if len(token) < 32 or len(token) > 512 or not all(c.isascii() and (c.isalnum() or c in '-_') for c in token):
        raise config.ConfigError('The session token must contain 32-512 letters, digits, hyphens or underscores.')
    return token


class InstanceLock:
    """Exclusive lock on byte 0 of state/service.lock, held for the life of the process (released by the OS on exit)."""

    def __init__(self, path):
        self.path = Path(path)
        self.f = None

    def acquire(self):
        self.f = open(self.path, 'a+b')
        try:
            if os.name == 'nt':
                import msvcrt
                self.f.seek(0)
                msvcrt.locking(self.f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            self.f.close()
            self.f = None
            return False

    def release(self):
        if self.f is None:
            return
        try:
            if os.name == 'nt':
                import msvcrt
                self.f.seek(0)
                msvcrt.locking(self.f.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            self.f.close()
            self.f = None


def probe_health(port, token, timeout=2.0):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        request = urllib.request.Request(f'http://127.0.0.1:{port}/health', headers={'Authorization': 'Bearer ' + token})
        with opener.open(request, timeout=timeout) as r:
            data = json.loads(r.read())
        return data if data.get('service') == SERVICE else None
    except (OSError, ValueError):
        return None


def report_running(state_dir):
    
    print(json.dumps({'error': 'This state folder is already in use by another session.'}), flush=True)
    return 2


def bind(preferred, handler):
    if preferred not in PORT_RANGE:
        raise ValueError('The service port must be between 18950 and 18969.')
    tried = []
    for port in [preferred] + [p for p in PORT_RANGE if p != preferred]:
        try:
            return Server(('127.0.0.1', port), handler), tried
        except OSError as e:
            tried.append((port, str(e)))
    raise OSError('No free port in 18950-18969: ' + '; '.join(f'{p}: {e}' for p, e in tried[-3:]))


class App:
    def __init__(self, args):
        self.args = args
        self.token = read_token(args.token_file)
        self.state = Path(args.state).resolve()
        self._stopped = threading.Event()
        self._stopping = threading.Lock()
        self.server = None
        self.lifecycle = None
        self._serving = False

    def run(self):
        self.state.mkdir(parents=True, exist_ok=True)
        self.lock = InstanceLock(self.state / 'service.lock')
        if not self.lock.acquire():
            return report_running(self.state)
        try:
            return self._run()
        finally:
            if hasattr(self, 'runner') and not self._stopped.is_set():
                self.stop()
            self.lock.release()

    def _run(self):
        cfg = config.load(self.state, fake_engine=self.args.fake_engine, config_file=self.args.config)
        cfg.two_card_proof = False
        config.ensure_state_dirs(cfg)
        self.cfg = cfg
        self.log = Logger(cfg.logs_dir, cfg.jobs_dir)
        
        self.log.info('service_starting', f'The engine is starting (version {VERSION})', data={
            'pid': os.getpid(), 'python': sys.version, 'executable': sys.executable, 'config': cfg.describe(),
            'fake_engine': cfg.fake_engine, 'argv': sys.argv})
        self.settings = Settings(self.state / 'settings.json', cfg.default_output_dir, self.log)
        self.store = JobStore(cfg.jobs_dir, self.log)
        self.store.load_all()
        self.media = MediaLibrary(cfg.media_dir, self.log)
        self.runner = Runner(cfg, self.settings, self.store, self.media, self.log)
        watch = HostWatch(self.log, self.args.host_pid)
        self.lifecycle = Lifecycle(self.runner, self.log, watch=watch, on_exit=self.stop,
                                   exit_when_closed=True)
        self.runner.lifecycle = self.lifecycle
        self.runner.recover()
        self.server, tried = bind(self.args.port, make_handler(self))
        port = self.server.server_address[1]
        self.runner.port = port
        if tried:
            self.log.info('port_fallback', f'Port {self.args.port} was busy; using {port}', data={'tried': tried})
        info = {'port': port, 'pid': os.getpid(), 'version': VERSION, 'contract': API_CONTRACT, 'started': now_iso(),
                'fake_engine': cfg.fake_engine}
        atomic_write_json(self.state / 'service.json', info)
        self.runner.start()
        self.lifecycle.start()
        self._install_signals()
        print(json.dumps(info), flush=True)
        self.log.info('service_ready', 'Creative Upscaler is ready', data=dict(info, url=f'http://127.0.0.1:{port}'))
        try:
            self._serving = True
            self.server.serve_forever(poll_interval=0.25)
        except KeyboardInterrupt:
            self.log.info('service_interrupt', 'Ctrl+C received')
            self.stop()
        self._stopped.wait(60.0)
        return 0

    def _install_signals(self):
        def handler(signum, frame):
            self.log.info('service_signal', f'Signal {signum} received; stopping')
            threading.Thread(target=self.stop, name='signal-stop', daemon=False).start()
        for name in ('SIGBREAK', 'SIGTERM'):
            sig = getattr(signal, name, None)
            if sig is not None:
                signal.signal(sig, handler)

    def close_requested(self, choice):
        """POST /api/lifecycle/close: the person's answer to the tab's close prompt. The reply is sent before a 'stop' is
        carried out (the route then runs stop() on its own thread)."""
        return self.lifecycle.close_request(choice)

    def stop(self):
        """Idempotent shutdown; safe from any thread except the one running serve_forever."""
        if not self._stopping.acquire(blocking=False):
            return
        try:
            if self.lifecycle is not None:
                self.lifecycle.closing = True       
                self.lifecycle.stop()
            self.log.info('service_stopping', 'Creative Upscaler is closing')
            self.runner.shutdown()
            if self.server is not None:
                if self._serving:
                    self.server.shutdown()
                self.server.server_close()
            p = self.state / 'service.json'
            try:
                if p.exists() and read_json(p).get('pid') == os.getpid():
                    p.unlink()
            except (OSError, ValueError) as e:
                self.log.warn('service_json_cleanup', f'service.json could not be removed: {e}')
            self.log.info('service_stopped', 'Service stopped; all engine processes closed')
        finally:
            self._stopped.set()


def main(argv=None):
    ap = argparse.ArgumentParser(prog='service.app', description='Creative Upscaler backend service')
    ap.add_argument('--state', default=DEFAULT_STATE, help='state folder (jobs, media, work, workers, logs)')
    ap.add_argument('--port', type=int, default=18950, help='preferred port (else next free in 18950-18969)')
    ap.add_argument('--fake-engine', action='store_true', help='use the fake ComfyUI (tests, UI work without a GPU)')
    ap.add_argument('--config', default=None, help='JSON file with path overrides (default: <state>/config.json if present)')
    ap.add_argument('--host-pid', type=int, required=True, help='owning host process; engine stops when it exits')
    ap.add_argument('--token-file', required=True, help='private file containing the per-run authentication token')
    args = ap.parse_args(argv)
    if args.port not in PORT_RANGE:
        ap.error('--port must be 18950-18969')
    if args.host_pid <= 0 or args.host_pid == os.getpid():
        ap.error('--host-pid must identify the separate owning host')
    try:
        return App(args).run()
    except (config.ConfigError, SettingsError, OSError, ValueError) as e:
        print(json.dumps({'error': str(e)}), flush=True)
        sys.stderr.write(f'Creative Upscaler service could not start: {e}\n')
        return 2


if __name__ == '__main__':
    sys.exit(main())
