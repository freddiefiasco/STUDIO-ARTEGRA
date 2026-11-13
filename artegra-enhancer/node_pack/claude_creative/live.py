"""Live implementation."""


import io
import json
import os
import queue
import struct
import threading
import time

import torch

LIVE_EVENT = 0x4C495645  
_Q = queue.Queue(maxsize=512)
_THREAD = None
_LOCK = threading.Lock()
_FILES = {}
_TAESD = {}
_TAESD_FAILED = {}
TAESD_NAS = r'\\Artegranas\studio artegra\Resources\AI\ComfyUI-Dual5090\models\vae_approx\taesdxl_decoder.safetensors'  


def _file_env():
    return os.environ.get('CLAUDE_LIVE_FILE', '').strip() in ('1', 'true', 'yes')


def _every():
    try:
        return max(1, int(os.environ.get('CLAUDE_LIVE_EVERY', '2')))
    except ValueError:
        return 2


def _groups_env():
    """CLAUDE_LIVE_GROUPS=1: the outline is one 'group' frame per model call (module docstring)."""
    return os.environ.get('CLAUDE_LIVE_GROUPS', '').strip() in ('1', 'true', 'yes')


def mode_from(node_value):
    """The emitter mode for the node's live_preview value, or None (off)."""
    v = (node_value or 'auto').strip().lower()
    if v == 'auto':
        v = os.environ.get('CLAUDE_LIVE_PREVIEW', '').strip().lower()
        if v in ('', '0', 'off', 'none'):
            return None
        if v in ('1', 'file', 'ws', 'both'):        
            return {'file': v in ('1', 'file', 'both'), 'ws': v in ('ws', 'both'), 'source': os.environ.get('CLAUDE_LIVE_SOURCE', 'l2r'),
                    'every': 1}
    if v == 'off':
        return None
    if v == 'rough':
        return {'file': _file_env(), 'ws': True, 'source': 'l2r', 'every': 1}
    if v == 'detailed':
        return {'file': _file_env(), 'ws': True, 'source': 'taesd', 'every': _every()}
    if v == 'on':
        return {'file': True, 'ws': True, 'source': os.environ.get('CLAUDE_LIVE_SOURCE', 'l2r'), 'every': 1}
    if v == 'on_taesd':
        return {'file': True, 'ws': True, 'source': 'taesd', 'every': 1}
    raise ValueError(f'ClaudeSpotTiles live_preview must be auto, off, rough, detailed, on or on_taesd (got {node_value!r})')


def _context():
    try:
        from comfy_execution.utils import get_executing_context
        c = get_executing_context()
        if c is not None:
            return c.prompt_id, c.node_id
    except Exception:
        pass
    try:
        from server import PromptServer
        s = PromptServer.instance
        return getattr(s, 'last_prompt_id', None), getattr(s, 'last_node_id', None)
    except Exception:
        return None, None


def _client():
    try:
        from server import PromptServer
        return PromptServer.instance.client_id
    except Exception:
        return None


def _out_dir():
    d = os.environ.get('CLAUDE_LIVE_DIR')
    if not d:
        import folder_paths
        d = os.path.join(folder_paths.get_output_directory(), 'claude_live')
    return d


def _find_taesd():
    """vae_approx/taesdxl_decoder* when the worker's model paths list it (the product's extra_model_paths points vae_approx at
    the NAS folder), else the copy already on the NAS (read in place, never copied)."""
    p = os.environ.get('CLAUDE_LIVE_TAESD', '')
    if p:
        return p
    try:
        import folder_paths
        for fn in folder_paths.get_filename_list('vae_approx'):
            if fn.startswith('taesdxl_decoder'):
                return folder_paths.get_full_path('vae_approx', fn)
    except Exception:
        pass
    return TAESD_NAS


class LiveEmitter:
    def __init__(self, mode):
        self.mode = dict(mode)
        self.max_side = int(os.environ.get('CLAUDE_LIVE_MAX_SIDE', '2048'))
        self.quality = int(os.environ.get('CLAUDE_LIVE_QUALITY', '80'))
        self.prompt = self.node = None
        self.client = None
        self.pass_no = 0
        self.sig = []
        self.seq = 0
        self.lock = threading.Lock()
        self.stats = self._new_stats()
        self.factors = {}          
        self.taesd_path = _find_taesd() if self.mode['source'] == 'taesd' else None
        self.source = self.mode['source']   
        self.groups = _groups_env()         
        _start()

    @staticmethod
    def _new_stats():
        return {'frames': 0, 'dropped': 0, 'main_s': 0.0, 'per_card': {}, 'decoded': 0, 'skipped': 0, 'starts': 0}

    
    def begin_pass(self, guider, latent_image, sigmas):
        t0 = time.perf_counter()
        pid, nid = _context()
        with self.lock:
            if pid != self.prompt:
                self.prompt, self.pass_no = pid, 0
            self.pass_no += 1
            self.node = nid
            self.sig = [float(s) for s in sigmas.detach().flatten().cpu()] if sigmas is not None else []
            self.stats = self._new_stats()
            self.source = self.mode['source']
            if self.source == 'taesd' and _TAESD_FAILED.get(self.taesd_path):
                self.source = 'l2r'            
        self.client = _client()
        try:
            lf = guider.model_patcher.model.latent_format
            if self.source == 'taesd':
                H, W = latent_image.shape[-2:]
                self._put_meta({'kind': 'init', 'source': 'taesd', 'image': False, 'step': -1, 'card': 0,
                                'rect_latent': [0, 0, int(W), int(H)], 'canvas_latent': [int(W), int(H)]})
            else:
                z = lf.process_in(latent_image.to(torch.float32))  
                self._put('init', z[:1], 0, 0, z.shape[-2], z.shape[-1], z.shape[-2], z.shape[-1], -1, lf, card=0)
        except Exception as e:  
            self._put_meta({'kind': 'error', 'where': 'begin_pass', 'error': repr(e)[:300]})
        with self.lock:
            self.stats['main_s'] += time.perf_counter() - t0

    def _step_of(self, sigma):
        return min(range(len(self.sig)), key=lambda i: abs(self.sig[i] - sigma)) if self.sig else -1

    def _decode_step(self, step):
        """detailed: decode on every n-th step counted back from the last step (so the final estimate is always decoded)."""
        n = self.mode.get('every', 1)
        if n <= 1 or step < 0:
            return True
        last = max(len(self.sig) - 2, 0)        
        return (last - step) % n == 0

    def _factors(self, lf, device):
        key = str(device)
        with self.lock:
            f = self.factors.get(key)
        if f is None:
            fac = torch.tensor(lf.latent_rgb_factors, dtype=torch.float32, device=device).transpose(0, 1).contiguous()
            b = getattr(lf, 'latent_rgb_factors_bias', None)
            f = (fac, None if b is None else torch.tensor(b, dtype=torch.float32, device=device))
            with self.lock:
                self.factors[key] = f
        return f

    def window_start(self, y0, xx0, h, w, H, W, sigma, card=0, phase='cfg'):
        """A window's model call begins (no tensors touched): the live outline."""
        t0 = time.perf_counter()
        try:
            self._put_meta({'kind': 'start', 'step': self._step_of(sigma), 'steps': max(len(self.sig) - 1, 0),
                            'rect_latent': [int(xx0), int(y0), int(w), int(h)], 'canvas_latent': [int(W), int(H)],
                            'card': int(card), 'phase': phase, 'source': self.source})
            with self.lock:
                self.stats['starts'] += 1
        except Exception as e:
            self._put_meta({'kind': 'error', 'where': 'window_start', 'error': repr(e)[:300], 'card': card})
        with self.lock:
            self.stats['main_s'] += time.perf_counter() - t0

    def outline(self, index, n, unit, H, W, sigma, card=0, phase='cfg', total=None):
        """A window group's model call begins: unit = [(iy, ix, y0, x0, h1, w1)] (latent px), the index-th of n groups of this
        evaluation (total windows). CLAUDE_LIVE_GROUPS=1: one 'group' frame; otherwise window_start for each window, as v4."""
        if not self.groups:
            for (_, _, y0, x0, h1, w1) in unit:
                self.window_start(y0, x0, h1, w1, H, W, sigma, card=card, phase=phase)
            return
        t0 = time.perf_counter()
        try:
            wins = [[int(x0), int(y0), int(w1), int(h1)] for (_, _, y0, x0, h1, w1) in unit]
            gx0, gy0 = min(r[0] for r in wins), min(r[1] for r in wins)
            gx1, gy1 = max(r[0] + r[2] for r in wins), max(r[1] + r[3] for r in wins)
            self._put_meta({'kind': 'group', 'state': 'start', 'step': self._step_of(sigma), 'steps': max(len(self.sig) - 1, 0),
                            'index': int(index), 'n': int(n), 'total': int(total) if total is not None else None,
                            'windows_latent': wins, 'rect_latent': [gx0, gy0, gx1 - gx0, gy1 - gy0],
                            'canvas_latent': [int(W), int(H)], 'card': int(card), 'phase': phase, 'source': self.source})
            with self.lock:
                self.stats['groups'] = self.stats.get('groups', 0) + 1
        except Exception as e:
            self._put_meta({'kind': 'error', 'where': 'outline', 'error': repr(e)[:300], 'card': card})
        with self.lock:
            self.stats['main_s'] += time.perf_counter() - t0

    def window(self, lf, x0, y0, xx0, h, w, H, W, sigma, card=0):
        """x0: (1, C, h, w) denoised estimate of the positive cond for the window at latent (y0, xx0), evaluated on `card`.
        lf: the model's latent format (or an object with .latent_format)."""
        t0 = time.perf_counter()
        try:
            if lf is not None and not hasattr(lf, 'latent_rgb_factors') and hasattr(lf, 'latent_format'):
                lf = lf.latent_format
            step = self._step_of(sigma)
            if self.source == 'taesd' and not self._decode_step(step):
                if not self.groups:          
                    self._put_meta({'kind': 'win', 'image': False, 'step': step, 'steps': max(len(self.sig) - 1, 0),
                                    'rect_latent': [int(xx0), int(y0), int(w), int(h)], 'canvas_latent': [int(W), int(H)],
                                    'card': int(card), 'source': 'taesd'})
                with self.lock:
                    self.stats['skipped'] += 1
                    pc = self.stats['per_card']
                    pc[str(card)] = pc.get(str(card), 0) + 1
            else:
                self._put('win', x0[:1], y0, xx0, h, w, H, W, step, lf, card=card)
        except Exception as e:
            self._put_meta({'kind': 'error', 'where': 'window', 'error': repr(e)[:300], 'card': card})
        with self.lock:
            self.stats['main_s'] += time.perf_counter() - t0

    def end_pass(self):
        with self.lock:
            st = dict(self.stats, per_card=dict(self.stats['per_card']))
            self.factors = {}
        self._put_meta({'kind': 'pass_end', 'stats': st})

    def _put(self, kind, z, y0, xx0, h, w, H, W, step, lf, card=0):
        taesd = self.source == 'taesd' and kind == 'win'
        if taesd:
            payload = z.detach().clone()  
        else:
            fac, bias = self._factors(lf, z.device)
            rgb = torch.nn.functional.linear(z[0].movedim(0, -1).to(fac.dtype), fac, bias=bias)
            payload = ((rgb + 1.0) / 2.0).clamp(0, 1).mul(255).to(torch.uint8)  
        ev = None
        if payload.is_cuda:
            ev = torch.cuda.Event()
            ev.record(torch.cuda.current_stream(payload.device))
        with self.lock:
            self.seq += 1
            seq = self.seq
        meta = {'kind': kind, 'seq': seq, 'prompt_id': self.prompt, 'node': self.node, 'pass': self.pass_no,
                'step': step, 'steps': max(len(self.sig) - 1, 0), 'rect_latent': [int(xx0), int(y0), int(w), int(h)],
                'canvas_latent': [int(W), int(H)], 'source': 'taesd' if taesd else 'l2r', 'card': int(card),
                'device': str(z.device), 't': time.time(), 'image': True}
        if self.mode['source'] == 'taesd' and not taesd:
            meta['fallback'] = 'taesd_unavailable'
        try:
            _Q.put_nowait((self, payload, ev, meta))
            with self.lock:
                self.stats['frames'] += 1
                if kind == 'win':
                    pc = self.stats['per_card']
                    pc[str(card)] = pc.get(str(card), 0) + 1
                    if taesd:
                        self.stats['decoded'] += 1
        except queue.Full:
            with self.lock:
                self.stats['dropped'] += 1

    def _put_meta(self, meta):
        with self.lock:
            self.seq += 1
            seq = self.seq
        meta = dict(meta, seq=seq, prompt_id=self.prompt, node=self.node, **{'pass': self.pass_no}, t=time.time())
        try:
            _Q.put_nowait((self, None, None, meta))
        except queue.Full:
            with self.lock:
                self.stats['dropped'] += 1


def _start():
    global _THREAD
    with _LOCK:
        if _THREAD is None or not _THREAD.is_alive():
            _THREAD = threading.Thread(target=_run, name='claude-live-preview', daemon=True)
            _THREAD.start()


def _taesd(path, device):
    key = (path, str(device))
    if key not in _TAESD:
        from comfy.taesd.taesd import TAESD
        t = TAESD(None, path, latent_channels=4).to(device=device, dtype=torch.float16 if device.type == 'cuda' else torch.float32).eval()
        _TAESD[key] = t
    return _TAESD[key]


def drain(timeout=10.0):
    """Wait until the background thread has handled every queued frame (tests)."""
    t = time.time() + timeout
    while time.time() < t:
        if _Q.unfinished_tasks == 0:
            return True
        time.sleep(0.02)
    return False


def _send(em, meta, jpg=b''):
    if not em.mode.get('ws'):
        return
    try:
        from server import PromptServer
        js = json.dumps(meta).encode('utf8')
        PromptServer.instance.send_sync(LIVE_EVENT, struct.pack('>I', len(js)) + js + jpg, getattr(em, 'client', None))
    except Exception as e:
        meta['ws_error'] = repr(e)[:200]


SKIP = object()          
GIVEN_BACK = [0]        


def _interrupts():
    """ComfyUI's interrupt flag: (processing_interrupted, interrupt_current_processing, InterruptProcessingException), each
    None when this process has no ComfyUI or the function is missing."""
    try:
        import comfy.model_management as mm
    except Exception:
        return None, None, None
    return (getattr(mm, 'processing_interrupted', None), getattr(mm, 'interrupt_current_processing', None),
            getattr(mm, 'InterruptProcessingException', None))


def _give_back(meta):
    """Live implementation."""


    _, rearm, _ = _interrupts()
    if rearm is not None:
        rearm(True)
    GIVEN_BACK[0] += 1
    meta['interrupt_given_back'] = rearm is not None
    if GIVEN_BACK[0] == 1 or rearm is None:
        import logging
        logging.info('ClaudeSpotTiles live preview: an interrupt reached the preview thread; %s',
                     'given back to the sampler' if rearm is not None else 'it could not be given back (no ComfyUI here)')


def _is_interrupt(e):
    exc = _interrupts()[2]
    return exc is not None and isinstance(e, exc)


def _decode_taesd(em, payload, dev, meta):
    """TAESD XL decode of one x0 window -> uint8 (h*8, w*8, 3); None when the decoder cannot be loaded (logged once per path);
    SKIP when an interrupt is waiting for the sampler (nothing decoded) or reached the decoder (given back, _give_back)."""
    pending = _interrupts()[0]
    if pending is not None and pending():
        meta['interrupt_pending'] = True
        return SKIP
    try:
        t0 = time.perf_counter()
        with torch.inference_mode():
            dec = _taesd(em.taesd_path, dev)
            x = dec.decode(payload.to(next(dec.parameters()).dtype))[0, :3].movedim(0, 2)
            arr = ((x.float() + 1.0) / 2.0).clamp(0, 1).mul(255).to(torch.uint8).cpu().numpy()
        meta['taesd_ms'] = round((time.perf_counter() - t0) * 1000, 2)
        return arr
    except Exception as e:
        if not _TAESD_FAILED.get(em.taesd_path):
            _TAESD_FAILED[em.taesd_path] = repr(e)[:300]
        meta['taesd_error'] = repr(e)[:300]
        return None
    except BaseException as e:      
        if not _is_interrupt(e):
            raise
        _give_back(meta)
        return SKIP


def _l2r_of(em, payload, dev):
    """latent2rgb of a window kept for TAESD (the decoder failed): the same maths as the rough mode."""
    import comfy.latent_formats as lfm
    lf = lfm.SDXL()
    fac = torch.tensor(lf.latent_rgb_factors, dtype=torch.float32, device=dev).transpose(0, 1)
    b = getattr(lf, 'latent_rgb_factors_bias', None)
    bias = None if b is None else torch.tensor(b, dtype=torch.float32, device=dev)
    rgb = torch.nn.functional.linear(payload[0].movedim(0, -1).float(), fac, bias=bias)
    return ((rgb + 1.0) / 2.0).clamp(0, 1).mul(255).to(torch.uint8).cpu().numpy()


def _run():
    from PIL import Image
    streams = {}
    while True:
        em, payload, ev, meta = _Q.get()
        try:
            d = os.path.join(_out_dir(), str(meta.get('prompt_id') or 'none')) if em.mode.get('file') else None
            if payload is None:
                _send(em, meta)
                if d is not None:
                    _index(d, meta)
                continue
            dev = payload.device
            ctx = torch.cuda.device(dev) if payload.is_cuda else None
            if ctx is not None:
                ctx.__enter__()
            try:
                if payload.is_cuda:
                    st = streams.get(str(dev))
                    if st is None:
                        st = streams[str(dev)] = torch.cuda.Stream(device=dev)
                    sctx = torch.cuda.stream(st)
                    sctx.__enter__()
                    st.wait_event(ev)
                else:
                    sctx = None
                try:
                    if meta['source'] == 'taesd':
                        arr = _decode_taesd(em, payload, dev, meta)
                        if arr is None:      
                            arr = _l2r_of(em, payload, dev)
                            meta['source'], meta['fallback'] = 'l2r', 'taesd_unavailable'
                    else:
                        arr = payload.cpu().numpy()
                finally:
                    if sctx is not None:
                        sctx.__exit__(None, None, None)
            finally:
                if ctx is not None:
                    ctx.__exit__(None, None, None)
            if arr is SKIP:                  
                continue
            img = Image.fromarray(arr)
            cw, ch = meta['canvas_latent']
            if meta['source'] == 'taesd':
                scale = min(1.0, em.max_side / float(max(cw, ch) * 8))
                rw = max(1, round(meta['rect_latent'][2] * 8 * scale)); rh = max(1, round(meta['rect_latent'][3] * 8 * scale))
            else:
                scale = min(1.0, em.max_side / float(max(cw, ch)))  
                rw = max(1, round(meta['rect_latent'][2] * scale)); rh = max(1, round(meta['rect_latent'][3] * scale))
            if (rw, rh) != img.size:
                img = img.resize((rw, rh), Image.BOX)
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=em.quality)
            jpg = buf.getvalue()
            meta['scale'] = scale
            meta['px'] = [rw, rh]
            meta['bytes'] = len(jpg)
            if d is not None:
                os.makedirs(d, exist_ok=True)
                name = 'f%07d.jpg' % meta['seq']
                with open(os.path.join(d, name), 'wb') as f:
                    f.write(jpg)
                meta['file'] = name
            meta['done_t'] = time.time()
            _send(em, meta, jpg)
            if d is not None:
                _index(d, meta)
        except Exception as e:
            try:
                if em.mode.get('file'):
                    _index(os.path.join(_out_dir(), 'errors'), {'kind': 'error', 'where': 'thread', 'error': repr(e)[:300], 'meta': meta})
                _send(em, {'kind': 'error', 'where': 'thread', 'error': repr(e)[:300], 'prompt_id': meta.get('prompt_id'),
                           'seq': meta.get('seq')})
            except Exception:
                pass
        except BaseException as e:          
            if not _is_interrupt(e):
                raise
            _give_back(meta)
        finally:
            _Q.task_done()


def _index(d, meta):
    os.makedirs(d, exist_ok=True)
    f = _FILES.get(d)
    if f is None:
        f = _FILES[d] = open(os.path.join(d, 'index.jsonl'), 'a', encoding='utf8', buffering=1)
    f.write(json.dumps(meta) + '\n')
