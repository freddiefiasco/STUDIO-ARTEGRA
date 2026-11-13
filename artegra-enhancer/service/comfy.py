"""Comfy implementation."""


import json
import struct
import threading
import time
import urllib.error
import urllib.request

from service.wsclient import WebSocket, WebSocketError

NODE_WEIGHTS = {'KSampler': 40.0, 'ClaudeV4Finish': 8.0, 'VAEDecodeTiled': 3.0, 'VAEEncodeTiled': 2.0,
                'ImageUpscaleWithModel': 3.0, 'SAM3_Detect': 1.0, 'ClaudeCannyTiled': 0.5}
DEFAULT_WEIGHT = 0.2
LIVE_EVENT = 0x4C495645          


def parse_live(msg):
    """A LIVE binary message -> {'type': 'claude.live', 'data': meta, 'jpeg': bytes}, or None for any other binary message.
    Raises ValueError for a LIVE message that cannot be read."""
    if not isinstance(msg, (bytes, bytearray)) or len(msg) < 8 or struct.unpack('>I', msg[:4])[0] != LIVE_EVENT:
        return None
    n = struct.unpack('>I', msg[4:8])[0]
    if n > len(msg) - 8:
        raise ValueError(f'live frame header says {n} bytes of metadata, {len(msg) - 8} present')
    meta = json.loads(bytes(msg[8:8 + n]).decode('utf8'))
    if not isinstance(meta, dict):
        raise ValueError('live frame metadata is not an object')
    return {'type': 'claude.live', 'data': meta, 'jpeg': bytes(msg[8 + n:])}


class ComfyError(Exception):
    """The engine could not be reached or answered with an error. `detail` is for the log, str(self) is plain."""

    def __init__(self, message, detail=None, status=None):
        super().__init__(message)
        self.detail = detail
        self.status = status


class ComfyUnavailable(ComfyError):
    pass


class PromptRejected(ComfyError):
    pass


class ComfyClient:
    def __init__(self, port, host='127.0.0.1'):
        self.base = f'http://{host}:{port}'
        
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def _call(self, path, data=None, timeout=30.0):
        raw = None if data is None else json.dumps(data).encode('utf8')
        req = urllib.request.Request(self.base + path, data=raw, headers={'Content-Type': 'application/json'},
                                     method='GET' if data is None else 'POST')
        try:
            with self._opener.open(req, timeout=timeout) as r:
                body = r.read()
        except urllib.error.HTTPError as e:
            body = e.read()
            try:
                payload = json.loads(body) if body.strip() else {}
            except ValueError:
                payload = {'raw': body[:2000].decode('utf8', 'replace')}
            raise ComfyError(f'The engine answered {e.code} for {path}', detail=payload, status=e.code)
        except (urllib.error.URLError, OSError) as e:
            raise ComfyUnavailable('The engine is not reachable', detail=f'{path}: {e}')
        if not body.strip():
            return {}
        try:
            return json.loads(body)
        except ValueError:
            raise ComfyError('The engine sent an unreadable answer', detail=body[:2000].decode('utf8', 'replace'))

    def system_stats(self, timeout=5.0):
        return self._call('/system_stats', timeout=timeout)

    def object_info(self, timeout=180.0):
        return self._call('/object_info', timeout=timeout)

    def prompt(self, graph, client_id, timeout=60.0, prompt_id=None):
        body = {'prompt': graph, 'client_id': client_id}
        if prompt_id is not None:
            body['prompt_id'] = prompt_id
        try:
            res = self._call('/prompt', body, timeout=timeout)
        except ComfyError as e:
            if e.status == 400:
                raise PromptRejected('The engine refused the job', detail=e.detail, status=400)
            raise
        if not res.get('prompt_id'):
            raise ComfyError('The engine did not accept the job', detail=res)
        if res.get('node_errors'):
            raise PromptRejected('The engine refused the job', detail=res)
        return res['prompt_id']

    def history(self, prompt_id, timeout=30.0):
        res = self._call(f'/history/{prompt_id}', timeout=timeout)
        return res.get(prompt_id)

    def queue(self, timeout=10.0):
        return self._call('/queue', timeout=timeout)

    def interrupt(self, timeout=10.0):
        return self._call('/interrupt', {}, timeout=timeout)

    def delete_queued(self, prompt_ids, timeout=10.0):
        return self._call('/queue', {'delete': list(prompt_ids)}, timeout=timeout)


def rejection_text(detail):
    """Short plain summary of a /prompt 400 (node_errors) for the log and the user."""
    if not isinstance(detail, dict):
        return str(detail)[:300]
    parts = []
    err = detail.get('error')
    if isinstance(err, dict) and err.get('message'):
        parts.append(str(err['message']))
    for nid, ne in (detail.get('node_errors') or {}).items():
        for e in (ne.get('errors') or [])[:2]:
            parts.append(f"{ne.get('class_type', '?')}: {e.get('message', '')} {e.get('details', '')}".strip())
    return '; '.join(parts)[:600] or 'no details'


class ProgressTracker:
    def __init__(self, graph, prompt_id):
        self.prompt_id = prompt_id
        self.weights = {nid: NODE_WEIGHTS.get(n['class_type'], DEFAULT_WEIGHT) for nid, n in graph.items()}
        self.total = sum(self.weights.values()) or 1.0
        self.done = set()
        self.current = None
        self.current_frac = 0.0
        self.started = False
        self.finished = False
        self.success = False
        self.error = None
        self.interrupted = False
        self.last_activity = time.monotonic()
        self.messages = 0
        self._pag_nodes = set()            
        self.groups_seen = 0
        self._lock = threading.Lock()
        self.changed = threading.Event()

    def on_message(self, msg):
        t, data = msg.get('type'), msg.get('data') or {}
        if data.get('prompt_id') not in (None, self.prompt_id):
            return
        with self._lock:
            self.last_activity = time.monotonic()
            self.messages += 1
            if t == 'execution_start':
                self.started = True
            elif t == 'execution_cached':
                self.done.update(str(n) for n in data.get('nodes') or [])
            elif t == 'executing':
                node = data.get('node')
                if self.current is not None:
                    self.done.add(self.current)
                if node is None:
                    if data.get('prompt_id') == self.prompt_id:
                        self.finished = True
                    self.current = None
                else:
                    self.started = True
                    self.current, self.current_frac = str(node), 0.0
            elif t == 'progress':
                mx = data.get('max') or 0
                if mx:
                    node = data.get('node')
                    if node is not None and str(node) != self.current:
                        if self.current is not None:
                            self.done.add(self.current)
                        self.current = str(node)
                    self.current_frac = min(1.0, max(0.0, float(data.get('value', 0)) / float(mx)))
            elif t == 'executed':
                if data.get('node') is not None:
                    self.done.add(str(data['node']))
            elif t == 'execution_success':
                self.finished, self.success = True, True
            elif t == 'execution_error':
                self.finished, self.error = True, data
            elif t == 'execution_interrupted':
                self.finished, self.interrupted = True, True
        self.changed.set()

    def on_group(self, meta):
        """Comfy implementation."""


        if meta.get('prompt_id') not in (None, self.prompt_id):
            return
        try:
            node, step, steps = str(meta.get('node')), int(meta.get('step')), int(meta.get('steps'))
            index, n = int(meta.get('index')), int(meta.get('n'))
        except (TypeError, ValueError):
            return
        if steps <= 0 or n <= 0 or step < 0 or not 0 <= index < n:
            return
        with self._lock:
            if node != self.current or node in self.done:
                return
            sub = (index + 1) / float(n)
            if meta.get('phase') == 'pag':
                self._pag_nodes.add(node)
                sub = 0.5 + sub / 2.0
            elif node in self._pag_nodes:
                sub = sub / 2.0
            self.current_frac = max(self.current_frac, min(1.0, (step + sub) / float(steps)))
            self.groups_seen += 1

    def fraction(self):
        with self._lock:
            if self.success:
                return 1.0
            w = sum(self.weights.get(n, DEFAULT_WEIGHT) for n in self.done)
            if self.current is not None and self.current not in self.done:
                w += self.weights.get(self.current, DEFAULT_WEIGHT) * self.current_frac
            return min(0.99, w / self.total)

    def node_progress(self, nodes):
        """How far these nodes (a stage's KSamplers) have run, 0-1 over all of them, or None before any of them has reported
        a step (the finish-time estimate waits for it: runner.stage_left_s)."""
        nodes = [str(n) for n in nodes or ()]
        if not nodes:
            return None
        with self._lock:
            done = sum(1 for n in nodes if n in self.done)
            cur = self.current_frac if self.current in nodes and self.current not in self.done else 0.0
            if done == 0 and cur <= 0.0:
                return None
            return (done + cur) / len(nodes)

    def idle_seconds(self):
        with self._lock:
            return time.monotonic() - self.last_activity

    def touch(self):
        """Count as activity now (the progress feed came back, or the engine answered while the feed was down)."""
        with self._lock:
            self.last_activity = time.monotonic()


class WsListener(threading.Thread):
    def __init__(self, port, client_id, log, gpu, host='127.0.0.1'):
        super().__init__(name=f'ws-gpu{gpu}', daemon=True)
        self.port, self.client_id, self.log, self.gpu, self.host = port, client_id, log, gpu, host
        self._stop = threading.Event()
        self._subs = {}
        self._lock = threading.Lock()
        self.connected = False
        self.last_message = None
        self.ws = None
        self.disconnects = 0
        self.generation = 0          
        self.bad_live = 0

    def subscribe(self, prompt_id, callback):
        with self._lock:
            self._subs[prompt_id] = callback

    def unsubscribe(self, prompt_id):
        with self._lock:
            self._subs.pop(prompt_id, None)

    def stop(self):
        self._stop.set()
        ws = self.ws
        if ws is not None:
            try:
                ws.close()
            except OSError as e:
                self.log.debug('ws_close_error', f'Progress feed close: {e}', data={'gpu': self.gpu})

    def run(self):
        backoff = 0.5
        reported = False
        while not self._stop.is_set():
            try:
                self.ws = WebSocket.connect(self.host, self.port, f'/ws?clientId={self.client_id}', timeout=5.0)
                self.generation += 1
                self.connected, backoff = True, 0.5
                if reported:
                    self.log.info('ws_reconnected', 'Progress feed reconnected', data={'gpu': self.gpu})
                reported = False
                while not self._stop.is_set():
                    msg = self.ws.recv(timeout=1.0)
                    if msg is None:
                        continue
                    if isinstance(msg, (bytes, bytearray)):
                        try:
                            live = parse_live(msg)
                        except (ValueError, UnicodeDecodeError) as e:
                            self.bad_live += 1
                            if self.bad_live <= 3:
                                self.log.warn('ws_bad_live', f'Unreadable live preview frame ignored: {e}', data={'gpu': self.gpu})
                            continue
                        if live is not None:
                            self.last_message = time.monotonic()
                            self._dispatch(live)
                        continue
                    try:
                        obj = json.loads(msg)
                    except ValueError:
                        self.log.warn('ws_bad_message', 'Unreadable progress message ignored', data={'gpu': self.gpu,
                                                                                                     'text': msg[:200]})
                        continue
                    self.last_message = time.monotonic()
                    self._dispatch(obj)
            except (OSError, WebSocketError) as e:
                if self._stop.is_set():
                    break
                self.connected = False
                self.disconnects += 1
                if not reported:
                    self.log.warn('ws_down', f'Progress feed unavailable ({e}); falling back to polling every 2 s',
                                  data={'gpu': self.gpu, 'port': self.port})
                    reported = True
                self._stop.wait(backoff)
                backoff = min(5.0, backoff * 2)
            finally:
                self.connected = False
                if self.ws is not None:
                    try:
                        self.ws.close()
                    except OSError as e:
                        self.log.debug('ws_close_error', f'Progress feed close: {e}', data={'gpu': self.gpu})
                    self.ws = None

    def _dispatch(self, obj):
        pid = (obj.get('data') or {}).get('prompt_id')
        with self._lock:
            targets = [self._subs[pid]] if pid in self._subs else ([] if pid else list(self._subs.values()))
        for cb in targets:
            try:
                cb(obj)
            except Exception as e:   
                self.log.exception('ws_dispatch_failed', 'A progress message could not be processed', e,
                                   data={'gpu': self.gpu})
