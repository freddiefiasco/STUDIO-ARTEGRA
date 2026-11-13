"""Api implementation."""


import hmac
import json
import re
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from engine import controls, planner
from service import VERSION, engine_options
from service.errors import ApiError
from service.logs import new_ref
from service.settings import SettingsError
from service.store import JOB_ID_RE, NotFound

MAX_BODY = 1 << 20
ITEM_ID_RE = re.compile(r'^i\d{3,4}$')
USER_EVENTS = frozenset({
    'job_created', 'job_state', 'item_dispatched', 'item_started', 'stage_start', 'stage_done', 'item_finishing', 'item_done',
    'item_state', 'item_cancelled', 'cancel_requested', 'item_interrupted', 'item_requeued', 'item_waiting',
    'item_recovered_done', 'item_held_memory', 'worker_starting', 'worker_ready', 'worker_stopped', 'worker_reset',
    'inputs_added', 'input_rejected', 'input_already_added', 'settings_changed', 'http_error', 'output_write_waiting',
    'sidecar_pending', 'sidecar_written', 'engine_retry', 'recovery_done', 'service_ready', 'service_stopping',
    'item_stopped', 'stop_requested', 'item_requeued_by_user', 'item_settings_changed', 'notify_sent', 'sleep_held',
    'sleep_released', 'split_skipped'})
LEVEL_OUT = {'warn': 'warning'}
LEVEL_IN = {'warning': 'warn'}


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False
    request_queue_size = 64

    def server_bind(self):
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):   
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def make_handler(app):
    class Handler(_Handler):
        pass
    Handler.app = app
    return Handler


class _Handler(BaseHTTPRequestHandler):
    app = None
    protocol_version = 'HTTP/1.1'
    server_version = 'CreativeUpscaler/' + VERSION

    def log_message(self, fmt, *args):
        if args and isinstance(args[0], str) and args[0].split(' ')[0] in ('GET', 'POST', 'DELETE', 'PUT', 'PATCH', 'HEAD',
                                                                           'OPTIONS'):
            return   
        self.app.log.debug('http', fmt % args)

    
    def _send(self, status, body, ctype='application/json; charset=utf-8', extra=None):
        self.send_response(status)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store' if ctype.startswith('application/json') else 'private, max-age=60')
        if self.close_connection:
            self.send_header('Connection', 'close')
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def send_error(self, code, message=None, explain=None):
        """http.server's own errors (malformed request line, header too long, unsupported method): JSON with a log_ref
        instead of an HTML page, and the connection is closed (its remaining bytes cannot be trusted)."""
        self.close_connection = True
        ref = new_ref()
        try:
            self.app.log.log('warn' if code < 500 else 'error', 'http_error', 'The request could not be read.', ref=ref,
                             data={'status': code, 'reason': message, 'explain': explain,
                                   'requestline': str(getattr(self, 'requestline', '')).split('?')[0][:200]})
        except Exception as e:   
            import sys
            sys.stderr.write(f'http_error log failed: {e}\n')
        body = json.dumps({'error': {'code': f'http_{code}', 'message': 'The request could not be read.',
                                     'log_ref': ref}}).encode('utf8')
        try:
            self.send_response(code, message)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Connection', 'close')
            self.end_headers()
            if getattr(self, 'command', None) != 'HEAD' and code >= 200 and code not in (204, 304):
                self.wfile.write(body)
        except OSError as e:
            self.app.log.debug('http_client_gone', f'Client disconnected during an error answer: {e}')

    def _json(self, status, obj):
        from service.util import to_jsonable
        self._send(status, json.dumps(to_jsonable(obj), ensure_ascii=False).encode('utf8'))

    def _error(self, status, code, message, data=None, exc=None, ref=None):
        ref = ref or new_ref()
        log = self.app.log
        fields = {'status': status, 'code': code, 'method': self.command, 'path': self.path.split('?')[0], 'data': data}
        if exc is not None and status >= 500:
            log.exception('http_error', message, exc, ref=ref, data=fields)
        else:
            log.log('error' if status >= 500 else 'warn', 'http_error', message, ref=ref, data=fields)
        err = {'code': code, 'message': message, 'log_ref': ref}
        if data:
            err['data'] = data
        self._json(status, {'error': err})

    def _read_body(self):
        """Read the whole declared body before routing (keep-alive safety, see the module docstring)."""
        self._raw = b''
        n = self.headers.get('Content-Length')
        if self.headers.get('Transfer-Encoding'):
            self.close_connection = True
            raise ApiError(411, 'length_required', 'Send the request with a Content-Length.')
        if n is None:
            return
        try:
            n = int(n)
            if n < 0:
                raise ValueError(n)
        except ValueError:
            self.close_connection = True
            raise ApiError(400, 'bad_request', 'Content-Length is not a number.')
        if n > MAX_BODY:
            self.close_connection = True
            raise ApiError(413, 'too_large', 'The request is too large.')
        self._raw = self.rfile.read(n) if n else b''
        if len(self._raw) != n:
            self.close_connection = True
            raise ApiError(400, 'bad_request', 'The request body was cut short.')

    def _body(self):
        raw = getattr(self, '_raw', b'')
        if not raw.strip():
            return {}
        try:
            return json.loads(raw.decode('utf8'))
        except (UnicodeDecodeError, ValueError):
            raise ApiError(400, 'bad_json', 'The request body must be JSON.')

    def _guard(self):
        expected = getattr(self.app, 'token', '')
        auth = self.headers.get('Authorization', '')
        supplied = auth[7:] if auth.startswith('Bearer ') else ''
        path = urlsplit(self.path).path
        image_route = bool(re.fullmatch(r'/api/media/[^/]+/(?:thumb|proxy|region|mask/[^/]+)', path)
                           or re.fullmatch(r'/api/jobs/[^/]+/items/[^/]+/(?:live|live-thumb|live-region|live-pass)\.jpg', path))
        if not supplied and self.command in ('GET', 'HEAD') and image_route:
            supplied = parse_qs(urlsplit(self.path).query).get('token', [''])[0]
        if not expected or not hmac.compare_digest(supplied.encode('utf8'), expected.encode('utf8')):
            raise ApiError(401, 'unauthorized', 'This request does not belong to the current app session.')
        host = (self.headers.get('Host') or '').split(':')[0].strip('[]').lower()
        if host not in ('127.0.0.1', 'localhost', ''):
            raise ApiError(403, 'forbidden_host', 'Requests must be addressed to 127.0.0.1.')
        origin = self.headers.get('Origin')
        if origin is not None and not re.fullmatch(r'http://(127\.0\.0\.1|localhost)(:\d+)?', origin):
            raise ApiError(403, 'forbidden_origin', 'Web pages cannot use this service.')
        site = self.headers.get('Sec-Fetch-Site')
        if site is not None and site not in ('same-origin', 'none'):
            raise ApiError(403, 'forbidden_origin', 'Web pages cannot use this service.')

    def _dispatch(self, method):
        url = urlsplit(self.path)
        path = url.path.rstrip('/') or '/'
        query = {k: v[-1] for k, v in parse_qs(url.query).items()}
        try:
            self._guard()
            self._read_body()
            for m, rx, fn in ROUTES:
                if m != method:
                    continue
                mt = rx.fullmatch(path)
                if mt:
                    return fn(self, query, *mt.groups())
            if any(rx.fullmatch(path) for _, rx, _ in ROUTES):
                raise ApiError(405, 'method_not_allowed', f'{method} is not supported here.')
            raise ApiError(404, 'not_found', 'Unknown address.')
        except ApiError as e:
            self.close_connection = True
            self._error(e.status, e.code, e.message, e.data, ref=e.ref)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError) as e:
            self.app.log.debug('http_client_gone', f'Client disconnected: {e}')
        except Exception as e:   
            self._error(500, 'internal_error', 'Something went wrong in the service. Details are in the log.', exc=e)

    def do_GET(self):
        self._dispatch('GET')

    def do_POST(self):
        self._dispatch('POST')

    def do_DELETE(self):
        self._dispatch('DELETE')

    def do_PUT(self):
        self._dispatch('PUT')

    def do_PATCH(self):
        self._dispatch('PATCH')

    def do_HEAD(self):
        self._dispatch('HEAD')

    def do_OPTIONS(self):
        self._dispatch('OPTIONS')

    
    def r_health(self, q):
        self._json(200, self.app.runner.health())

    def r_controls(self, q):
        self._json(200, controls.describe())

    def _settings_out(self, s, writable=None, problem=None):
        if writable is None:
            writable, problem = self.app.runner.output_dir_status()
        out = dict(s, available_gpus=self.app.runner.gpu_list()[0], output_dir_writable=writable,
                   output_dir_problem=problem)
        if not self.app.runner.faster_info()['available']:     
            out.pop('faster', None)
        return out

    def r_settings_get(self, q):
        self._json(200, self._settings_out(self.app.settings.get()))

    def r_settings_post(self, q):
        body = self._body()
        runner = self.app.runner
        if isinstance(body, dict) and 'gpus' in body:
            gpus, problem = runner.gpu_list()
            if problem:
                raise ApiError(503, 'gpus_unavailable', problem)
            if not gpus and runner.gpu_probe_pending():   
                runner.invalidate_problems()
                raise ApiError(503, 'gpus_unavailable', 'The graphics cards are still being checked. Try again in a moment.')
        if isinstance(body, dict) and 'faster' in body and not runner.faster_info()['available']:
            raise ApiError(400, 'bad_settings', 'These settings cannot be changed here: faster')   
        if isinstance(body, dict) and runner.faster_info()['available'] and isinstance(body.get('faster', False), bool) \
                and isinstance(body.get('match_earlier', False), bool):
            clash = engine_options.faster_conflict(self.app.settings.get(), body)
            if clash:
                raise ApiError(409, 'faster_with_match', clash)
        try:
            s = self.app.settings.update(body, runner.available_gpus())
        except SettingsError as e:
            raise ApiError(400, 'bad_settings', str(e))
        runner.invalidate_problems()
        runner.wake()
        if 'output_dir' in body:          
            self._json(200, self._settings_out(s, True, None))
        else:
            self._json(200, self._settings_out(s))

    def r_plan(self, q):
        b = self._body()
        if not isinstance(b, dict):
            raise ApiError(400, 'bad_request', 'Send {width, height, scale}.')
        w, h, scale = b.get('width'), b.get('height'), b.get('scale', 2)
        for v, name in ((w, 'width'), (h, 'height')):
            if isinstance(v, bool) or not isinstance(v, int) or not 1 <= v <= 1_000_000:
                raise ApiError(400, 'bad_request', f'{name} must be a whole number of pixels.')
        if isinstance(scale, bool) or scale not in controls.SCALES:
            raise ApiError(400, 'bad_request', 'scale must be 2, 4, 6 or 8.')
        unknown = set(b) - {'width', 'height', 'scale', 'output_format', 'alpha', 'media_id', 'mode'}
        if unknown:
            raise ApiError(400, 'bad_request', 'Unsupported fields: ' + ', '.join(sorted(unknown)))
        mode = b.get('mode', 'standard')
        if mode not in controls.MODES:
            raise ApiError(400, 'bad_settings', 'Choose a mode: Standard or Fast.')
        
        self.app.runner._check_mode({'mode': mode, 'scale': scale})
        plan = planner.plan(w, h, scale)
        self.app.runner._check_mode({'mode': mode, 'scale': scale}, plan)
        out = self.app.runner.plan_check(plan)
        alpha = b.get('alpha')
        if b.get('media_id') is not None:
            alpha = bool(self._media(b['media_id']).get('alpha'))
        if alpha is not None or 'output_format' in b:
            fmt = b.get('output_format', 'png8')
            if fmt not in controls.OUTPUT_FORMATS:
                raise ApiError(400, 'bad_request', 'output_format must be png8, png16, tiff16 or jpeg.')
            if not alpha:
                out.update(transparency='none', transparency_reason=None)
            elif fmt == 'jpeg':
                out.update(transparency='not_kept', transparency_reason='jpeg')
            else:
                out.update(transparency='kept', transparency_reason=None)
        self._json(200, out)

    def r_inputs_get(self, q):
        self._json(200, {'items': self.app.media.list()})

    def r_inputs_post(self, q):
        b = self._body()
        if not isinstance(b, dict) or 'paths' not in b:
            raise ApiError(400, 'bad_request', 'Send {paths: [...]} with full file or folder paths.')
        t0 = time.monotonic()
        try:
            items, rejected = self.app.media.add_paths(b['paths'])
        except ValueError as e:
            raise ApiError(400, 'bad_request', str(e))
        n, r = len(items), len(rejected)
        self.app.log.info('inputs_added', f'{n} image{"s" if n != 1 else ""} added' + (f', {r} refused' if r else ''),
                          data={'added': [i['id'] for i in items], 'rejected': rejected,
                                'seconds': round(time.monotonic() - t0, 1)})
        self._json(200, {'items': items, 'rejected': rejected})

    def r_inputs_delete(self, q, mid):
        try:
            self.app.media.delete(mid)
        except KeyError:
            raise ApiError(404, 'unknown_image', 'This image is not in the list.')
        except OSError as e:
            raise ApiError(500, 'delete_failed', f'The image files could not be removed ({e.strerror or e}).')
        self._json(200, {'deleted': mid})

    def _media(self, mid):
        try:
            return self.app.media.get(mid)
        except KeyError:
            raise ApiError(404, 'unknown_image', 'This image is not in the list.')

    def _result_dir(self, mid, q):
        """Folder of the viewer copies of a result; rebuilt on demand when they are missing (e.g. a result completed at a
        restart). 404 result_preview_missing when they cannot be made."""
        jid, iid = q.get('job'), q.get('item')
        store = self.app.store
        if jid or iid:
            if not (jid and iid and JOB_ID_RE.match(jid) and ITEM_ID_RE.match(iid)):
                raise ApiError(400, 'bad_request', 'Give both job and item.')
            try:
                it = store.item(jid, iid)
            except NotFound:
                raise ApiError(404, 'not_found', 'Unknown job or item.')
            if it['media_id'] != mid or it['state'] != 'done':
                raise ApiError(404, 'no_result', 'This image has no finished result in that job.')
        else:
            best = store.latest_result(mid)
            if best is None:
                raise ApiError(404, 'no_result', 'This image has no finished result yet.')
            jid, iid = best
        if not self.app.runner.ensure_result_views(jid, iid):
            raise ApiError(404, 'result_preview_missing', 'The preview of this result is not available. Open the result '
                                                          'file instead.')
        return self.app.media.result_dir(jid, iid)

    def _file(self, path, ctype):
        p = Path(path)
        if not p.is_file():
            raise ApiError(404, 'not_found', 'The preview file is missing.')
        self._send(200, p.read_bytes(), ctype)

    def _display(self, q, mid, kind):
        """thumb or proxy: the RGBA PNG when the image (or its result) has one, else the JPEG (L23)."""
        self._media(mid)
        folder = self._result_dir(mid, q) if q.get('kind') == 'result' else self.app.media.dir / mid
        self._file(*self.app.media.display_file(folder, kind))

    def r_thumb(self, q, mid):
        self._display(q, mid, 'thumb')

    def r_proxy(self, q, mid):
        if 'w' in q or 'h' in q:
            return self._sized(q, mid)
        self._display(q, mid, 'proxy')

    def _sized(self, q, mid):
        """proxy?w=&h= (v4, preview design): the display copy at the drawn size, resampled from the picture's own full-size pixels
        (the source, or with kind=result the result's view copy); never larger than the picture. JPEG, or RGBA PNG for a
        picture with transparency. X-Sized says the size served, X-Image-Size the picture's own."""
        from service import images
        self._media(mid)
        try:
            w, h = int(q['w']), int(q['h'])
        except (KeyError, ValueError):
            raise ApiError(400, 'bad_request', 'Give w and h as whole numbers of pixels.')
        if not (1 <= w <= images.SIZED_MAX_SIDE and 1 <= h <= images.SIZED_MAX_SIDE):
            raise ApiError(400, 'bad_request', f'w and h must be 1 to {images.SIZED_MAX_SIDE} px.')
        if q.get('kind') == 'result':
            path, alpha_path = self.app.media.result_layer(self._result_dir(mid, q))
        else:
            path, alpha_path = self.app.media.source_layer(mid)
        if not path.is_file():
            raise ApiError(404, 'not_found', 'The image file is missing.')
        data, ctype, size, own = self.app.media.sized.get(path, alpha_path, w, h)
        self._send(200, data, ctype, extra={'X-Sized': f'{size[0]},{size[1]}', 'X-Image-Size': f'{own[0]},{own[1]}'})

    def r_region(self, q, mid):
        from service import images
        self._media(mid)
        try:
            x, y, w, h = (int(q[k]) for k in ('x', 'y', 'w', 'h'))
        except (KeyError, ValueError):
            raise ApiError(400, 'bad_request', 'Give x, y, w and h as whole numbers of pixels.')
        kind = q.get('kind', 'source')
        if kind == 'source':
            path, alpha_path = self.app.media.source_layer(mid)
        elif kind == 'result':
            path, alpha_path = self.app.media.result_layer(self._result_dir(mid, q))
        else:
            raise ApiError(400, 'bad_request', 'kind must be source or result.')
        if not path.is_file():
            raise ApiError(404, 'not_found', 'The image file is missing.')
        img = self.app.media.decoded.get(path, alpha_path)      
        try:
            data, box = images.region_png(img, x, y, w, h)
        except ValueError as e:
            raise ApiError(400, 'bad_region', str(e))
        self._send(200, data, 'image/png', extra={'X-Region': ','.join(map(str, box)),
                                                  'X-Image-Size': f'{img.width},{img.height}'})

    def r_mask_get(self, q, mid, key):
        self._media(mid)
        try:
            p = self.app.media.mask_file(mid, key)
        except KeyError:
            raise ApiError(404, 'not_found', 'Unknown mask.')
        self._file(p, 'image/png')

    def r_mask_preview(self, q):
        b = self._body()
        if not isinstance(b, dict) or not isinstance(b.get('media_id'), str):
            raise ApiError(400, 'bad_request', 'Send {media_id, protect, quick_protect}.')
        unknown = set(b) - {'media_id', 'protect', 'quick_protect'}
        if unknown:
            raise ApiError(400, 'bad_request', 'Unsupported fields: ' + ', '.join(sorted(unknown)))
        self._json(200, self.app.runner.mask_preview(b['media_id'], b.get('protect'), b.get('quick_protect')))

    def r_jobs_post(self, q):
        job, created = self.app.runner.create_job(self._body())
        self._json(201 if created else 200, job)

    def r_jobs_get(self, q):
        try:
            limit = max(1, min(int(q.get('limit', 50)), 200))
        except ValueError:
            raise ApiError(400, 'bad_request', 'limit must be a number.')
        self._json(200, {'jobs': self.app.store.list(limit=limit)})

    def _job(self, jid):
        if not JOB_ID_RE.match(jid):
            raise ApiError(404, 'not_found', 'Unknown job.')
        try:
            return self.app.store.get(jid)
        except NotFound:
            raise ApiError(404, 'not_found', 'Unknown job.')

    def r_job_get(self, q, jid):
        self._json(200, self._job(jid))

    def r_job_cancel(self, q, jid):
        self._job(jid)
        self.app.runner.cancel_job(jid)
        self._json(200, self.app.store.get(jid))

    def r_item_cancel(self, q, jid, iid):
        self._job(jid)
        try:
            self.app.runner.cancel_item(jid, iid)
        except NotFound:
            raise ApiError(404, 'not_found', 'Unknown image in this job.')
        self._json(200, self.app.store.get(jid))

    
    def r_live(self, q):
        self._json(200, self.app.runner.live_summary())

    def _live_of(self, jid, iid, recent=False):
        """The image's live canvas (or frozen last frame). recent: also the last frame of an image whose live picture was
        dropped in the last few seconds (live.jpg and live-thumb.jpg only: a picture the tab asked for as the image ended)."""
        self._job(jid)
        board = self.app.runner.live
        c = board.get(jid, iid) or (board.recent(jid, iid) if recent else None)
        if c is None:
            raise ApiError(404, 'no_live', 'This image has no live preview.')
        return c

    def r_item_live(self, q, jid, iid):
        self._live_of(jid, iid)
        for it in self.app.runner.live_summary()['items']:
            if it['job_id'] == jid and it['item_id'] == iid:
                return self._json(200, it)
        raise ApiError(404, 'no_live', 'This image has no live preview.')

    def _live_jpeg(self, data, extra=None):
        if not data:
            raise ApiError(404, 'no_live', 'This image has no live picture yet.')
        self.send_response(200)
        self.send_header('Content-Type', 'image/jpeg')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        if self.close_connection:
            self.send_header('Connection', 'close')
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(data)

    def r_item_live_jpg(self, q, jid, iid):
        self._live_jpeg(self._live_of(jid, iid, recent=True).jpeg())

    def r_item_live_thumb(self, q, jid, iid):
        self._live_jpeg(self._live_of(jid, iid, recent=True).thumb())

    def r_item_live_pass(self, q, jid, iid):
        """Api implementation."""

        c = self._live_of(jid, iid, recent=True)
        data = c.earlier_jpeg() if hasattr(c, 'earlier_jpeg') else None
        if not data:
            data = self.app.runner.live.recent_earlier(jid, iid)
        if not data:
            raise ApiError(404, 'no_earlier_pass', 'This image has no finished pass to show yet.')
        self._live_jpeg(data)

    def r_item_live_region(self, q, jid, iid):
        """preview design: a rectangle of the live picture from the composite's own full-size pixels (service/live.py)."""
        c = self._live_of(jid, iid)
        try:
            x, y, w, h = (int(q[k]) for k in ('x', 'y', 'w', 'h'))
        except (KeyError, ValueError):
            raise ApiError(400, 'bad_request', 'Give x, y, w and h as whole numbers of pixels.')
        try:
            got = c.region(x, y, w, h)
        except ValueError as e:
            raise ApiError(400, 'bad_region', str(e))
        if got is None:
            raise ApiError(404, 'no_live_region', 'This image has no full-size live picture.')
        data, box, scale, seq = got
        self._live_jpeg(data, extra={'X-Region': ','.join(map(str, box)), 'X-Region-Scale': f'{scale:.4f}',
                                     'X-Live-Seq': str(seq)})

    def r_cancel_image(self, q):
        mid, jid, iid = q.get('image'), q.get('job'), q.get('item')
        if not mid and not (jid and iid):
            raise ApiError(400, 'bad_request', 'Give the image: /api/cancel?image=<image id>.')
        if jid is not None and not JOB_ID_RE.match(jid) or iid is not None and not ITEM_ID_RE.match(iid):
            raise ApiError(404, 'not_found', 'Unknown job or item.')
        try:
            jid, iid = self.app.runner.stop_image(mid, jid, iid)
        except NotFound:
            raise ApiError(404, 'not_found', 'Unknown image in this job.')
        self._stopped_reply(jid, iid)

    def _stopped_reply(self, jid, iid):
        job = self.app.store.get(jid)
        it = next(x for x in job['items'] if x['id'] == iid)
        self._json(200, {'stopped': {'job_id': jid, 'item_id': iid, 'media_id': it['media_id'], 'state': it['state'],
                                     'at': it.get('at')}, 'job': job})

    def r_item_stop(self, q, jid, iid):
        self._job(jid)
        try:
            self.app.runner.stop_item(jid, iid)
        except NotFound:
            raise ApiError(404, 'not_found', 'Unknown image in this job.')
        self._stopped_reply(jid, iid)

    def r_item_requeue(self, q, jid, iid):
        self._job(jid)
        b = self._body()
        if not isinstance(b, dict) or set(b) - {'settings', 'front', 'as_before'}:
            raise ApiError(400, 'bad_request', 'Send {settings?, front?, as_before?}.')
        front, as_before = b.get('front', True), b.get('as_before', False)
        if not isinstance(front, bool) or not isinstance(as_before, bool):
            raise ApiError(400, 'bad_request', 'front and as_before must be true or false.')
        if as_before and b.get('settings') is not None:
            raise ApiError(400, 'bad_request', 'Send either settings or as_before.')
        try:
            job = self.app.runner.requeue_item(jid, iid, b.get('settings'), front, as_before)
        except NotFound:
            raise ApiError(404, 'not_found', 'Unknown image in this job.')
        self._json(200, job)

    def r_items_settings(self, q):
        b = self._body()
        if not isinstance(b, dict) or set(b) - {'items', 'settings'} or 'items' not in b or 'settings' not in b:
            raise ApiError(400, 'bad_request', 'Send {items: [{job_id, item_id}, ...], settings: {...}}.')
        self._json(200, self.app.runner.set_item_settings(b['items'], b['settings']))

    def r_open(self, q):
        b = self._body()
        self._json(200, self.app.runner.open_path(b.get('path') if isinstance(b, dict) else None))

    def r_logs(self, q):
        jid = q.get('job')
        if jid is not None:
            self._job(jid)
        try:
            limit = int(q.get('limit', 200))
        except ValueError:
            raise ApiError(400, 'bad_request', 'limit must be a number.')
        level = q.get('level', 'info')
        level = LEVEL_IN.get(level, level)
        if level not in ('debug', 'info', 'warn', 'error'):
            raise ApiError(400, 'bad_request', 'level must be debug, info, warning or error.')
        everything = q.get('all') in ('1', 'true', 'yes')
        pred = None if everything else (lambda r: r.get('event') in USER_EVENTS or r.get('level') == 'error')
        lines = self.app.log.recent(job=jid, limit=limit, min_level=level, pred=pred)
        out = [{'ts': r.get('ts'), 'level': LEVEL_OUT.get(r.get('level'), r.get('level')), 'event': r.get('event'),
                'msg': r.get('msg'), 'job': r.get('job'), 'item': r.get('item'), 'stage': r.get('stage'),
                'log_ref': r.get('log_ref') or (r.get('data') or {}).get('log_ref')}
               for r in lines]
        self._json(200, {'lines': out})

    def r_engine_retry(self, q):
        self._json(200, self.app.runner.retry_engine())

    def r_shutdown(self, q):
        self.app.log.info('shutdown_requested', 'Shutdown requested over HTTP')
        self._json(200, {'stopping': True})
        threading.Thread(target=self.app.stop, name='shutdown', daemon=False).start()

    def r_lifecycle_close(self, q):
        b = self._body()
        if not isinstance(b, dict) or b.get('choice') not in ('stop', 'finish') or set(b) - {'choice'}:
            raise ApiError(400, 'bad_request', 'Send {"choice": "stop"} or {"choice": "finish"}.')
        reply = self.app.close_requested(b['choice'])
        self._json(200, reply)
        if b['choice'] == 'stop':
            threading.Thread(target=self.app.stop, name='stop-and-close', daemon=False).start()


_ID = r'([A-Za-z0-9]+)'
ROUTES = [
    ('GET', re.compile(r'/health'), _Handler.r_health),
    ('GET', re.compile(r'/api/controls'), _Handler.r_controls),
    ('GET', re.compile(r'/api/settings'), _Handler.r_settings_get),
    ('POST', re.compile(r'/api/settings'), _Handler.r_settings_post),
    ('POST', re.compile(r'/api/plan'), _Handler.r_plan),
    ('GET', re.compile(r'/api/inputs'), _Handler.r_inputs_get),
    ('POST', re.compile(r'/api/inputs'), _Handler.r_inputs_post),
    ('DELETE', re.compile(r'/api/inputs/(m[0-9a-f]{12})'), _Handler.r_inputs_delete),
    ('GET', re.compile(r'/api/media/(m[0-9a-f]{12})/thumb'), _Handler.r_thumb),
    ('GET', re.compile(r'/api/media/(m[0-9a-f]{12})/proxy'), _Handler.r_proxy),
    ('GET', re.compile(r'/api/media/(m[0-9a-f]{12})/region'), _Handler.r_region),
    ('GET', re.compile(r'/api/media/(m[0-9a-f]{12})/mask/([0-9a-f]{12})'), _Handler.r_mask_get),
    ('POST', re.compile(r'/api/mask-preview'), _Handler.r_mask_preview),
    ('POST', re.compile(r'/api/jobs'), _Handler.r_jobs_post),
    ('GET', re.compile(r'/api/jobs'), _Handler.r_jobs_get),
    ('GET', re.compile(r'/api/jobs/' + _ID), _Handler.r_job_get),
    ('POST', re.compile(r'/api/jobs/' + _ID + r'/cancel'), _Handler.r_job_cancel),
    ('POST', re.compile(r'/api/jobs/' + _ID + r'/items/' + _ID + r'/cancel'), _Handler.r_item_cancel),
    ('POST', re.compile(r'/api/engine/retry'), _Handler.r_engine_retry),
    ('POST', re.compile(r'/api/open'), _Handler.r_open),
    ('GET', re.compile(r'/api/logs'), _Handler.r_logs),
    ('POST', re.compile(r'/api/shutdown'), _Handler.r_shutdown),
    ('POST', re.compile(r'/api/lifecycle/close'), _Handler.r_lifecycle_close),
    ('GET', re.compile(r'/api/live'), _Handler.r_live),
    ('GET', re.compile(r'/api/jobs/' + _ID + r'/items/' + _ID + r'/live'), _Handler.r_item_live),
    ('GET', re.compile(r'/api/jobs/' + _ID + r'/items/' + _ID + r'/live\.jpg'), _Handler.r_item_live_jpg),
    ('GET', re.compile(r'/api/jobs/' + _ID + r'/items/' + _ID + r'/live-thumb\.jpg'), _Handler.r_item_live_thumb),
    ('GET', re.compile(r'/api/jobs/' + _ID + r'/items/' + _ID + r'/live-region\.jpg'), _Handler.r_item_live_region),
    ('GET', re.compile(r'/api/jobs/' + _ID + r'/items/' + _ID + r'/live-pass\.jpg'), _Handler.r_item_live_pass),
    ('POST', re.compile(r'/api/cancel'), _Handler.r_cancel_image),
    ('POST', re.compile(r'/api/jobs/' + _ID + r'/items/' + _ID + r'/stop'), _Handler.r_item_stop),
    ('POST', re.compile(r'/api/jobs/' + _ID + r'/items/' + _ID + r'/requeue'), _Handler.r_item_requeue),
    ('POST', re.compile(r'/api/items/settings'), _Handler.r_items_settings),
]
