"""Fake comfy implementation."""


import io
import json
import os
import re
import struct
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

if __name__ == '__main__':                       
    _args = sys.argv[1:]
    for _i, _a in enumerate(_args):
        if _a == '--path' and _i + 1 < len(_args):
            sys.path.insert(0, _args[_i + 1])
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  
from PIL import Image, ImageDraw  

from service.wsclient import FrameParser, OP_BIN, OP_CLOSE, OP_PING, OP_PONG, OP_TEXT, accept_key, encode_frame  
from engine import run_order  

Image.MAX_IMAGE_PIXELS = 300_000_000
TINT = np.array([255, 150, 60], np.float32)
TINT_AMOUNT = 0.18
CRASH_EXIT_CODE = 70
LIVE_EVENT = 0x4C495645
LIVE_GRID = 3
LIVE_GROUP = 2                   


NODE_SPECS = {
    'CheckpointLoaderSimple': (('ckpt_name',), ('MODEL', 'CLIP', 'VAE')),
    'PerturbedAttentionGuidance': (('model', 'scale'), ('MODEL',)),
    'CLIPTextEncode': (('clip', 'text'), ('CONDITIONING',)),
    'LoadImage': (('image',), ('IMAGE', 'MASK')),
    'UpscaleModelLoader': (('model_name',), ('UPSCALE_MODEL',)),
    'ImageUpscaleWithModel': (('upscale_model', 'image'), ('IMAGE',)),
    'ClaudeUpscaleModelTiled': (('upscale_model', 'image', 'tile', 'margin', 'blend'), ('IMAGE',)),
    'ImageScale': (('image', 'upscale_method', 'width', 'height', 'crop'), ('IMAGE',)),
    'ControlNetLoader': (('control_net_name',), ('CONTROL_NET',)),
    'ImageBlur': (('image', 'blur_radius', 'sigma'), ('IMAGE',)),
    'ClaudeCannyTiled': (('image', 'low_threshold', 'high_threshold'), ('IMAGE',)),
    'ControlNetApplyAdvanced': (('positive', 'negative', 'control_net', 'image', 'strength', 'start_percent', 'end_percent'),
                                ('CONDITIONING', 'CONDITIONING')),
    'ClaudeSpotTiles': (('model', 'tile_px', 'seed'), ('MODEL',)),
    'MultiGPU_WorkUnits': (('model', 'max_gpus'), ('MODEL',)),
    
    'LoraLoaderModelOnly': (('model', 'lora_name', 'strength_model'), ('MODEL',)),
    'VAEEncodeTiled': (('pixels', 'vae', 'tile_size', 'overlap'), ('LATENT',)),
    'KSampler': (('model', 'positive', 'negative', 'latent_image', 'seed', 'steps', 'cfg', 'sampler_name', 'scheduler',
                  'denoise'), ('LATENT',)),
    'VAEDecodeTiled': (('samples', 'vae', 'tile_size', 'overlap'), ('IMAGE',)),
    'SAM3_Detect': (('model', 'image', 'conditioning', 'threshold'), ('MASK', 'BBOX', 'IMAGE')),
    'ClaudeMaskUnion': ((), ('MASK',)),
    'ClaudeProtectGate': (('protect', 'dilate', 'feather'), ('MASK',)),
    'ClaudeV4Finish': (('creative', 'structure', 'init', 'pre', 'smooth_lo', 'smooth_hi', 'protect_dilate', 'protect_feather',
                        'islands', 'chroma_clamp'), ('IMAGE',)),
    'ClaudeShadowToe': (('image', 'amount', 'scale'), ('IMAGE',)),
    'MaskToImage': (('mask',), ('IMAGE',)),
    'SaveImage': (('images', 'filename_prefix'), ()),
}


NODE_OPTIONAL = {
    'ClaudeSpotTiles': ('clamp_blend', 'window_split', 'balance', 'weights', 'batch_windows', 'pag_fuse', 'cn_reuse',
                        'noise_prefetch', 'fp16_acc_scoped', 'live_preview', 'seam_overlap', 'seam_dual', 'pag_end', 'cfg_end'),
    'ClaudeV4Finish': ('protect', 'quantize_8bit', 'keep_blacks', 'clamp', 'lf', 'glow', 'fin_b0_hi', 'release',
                       'island_after_lf'),
    'ClaudeCannyTiled': ('tile',),
    'ClaudeProtectGate': ('release',),
    'ClaudeMaskUnion': tuple(f'mask_{i}' for i in range(1, 9)),
}
MAX_RESOLUTION = 16384           
STAGE_RE = re.compile(r'_s(\d+)$')
UUID_RE = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
FAULT_KINDS = ('fail', 'stall', 'crash', 'oom', 'reject', 'nofile', 'badsize', 'missingnode', 'nows', 'nostart', 'oldpack')
NOSTART_EXIT_CODE = 3
_fired_memory = set()


class GraphInvalid(Exception):
    def __init__(self, message, node_errors=None):
        super().__init__(message)
        self.node_errors = node_errors or {}


def _is_link(v):
    return isinstance(v, list) and len(v) == 2 and isinstance(v[0], str) and isinstance(v[1], int)


def validate(graph, input_dir):
    """Structural validation + size propagation. Returns (topological order, {node: size or None}, save node ids)."""
    if not isinstance(graph, dict) or not graph:
        raise GraphInvalid('The prompt must be a non-empty object of nodes')
    errors = {}

    def bad(nid, msg):
        errors.setdefault(nid, {'errors': [], 'class_type': graph.get(nid, {}).get('class_type')})['errors'].append(
            {'type': 'invalid', 'message': msg, 'details': ''})

    for nid, node in graph.items():
        if not isinstance(node, dict) or 'class_type' not in node or not isinstance(node.get('inputs'), dict):
            bad(nid, 'node must have class_type and inputs')
            continue
        spec = NODE_SPECS.get(node['class_type'])
        if spec is None:
            bad(nid, f"unknown node class {node['class_type']}")
            continue
        for req in spec[0]:
            if req not in node['inputs']:
                bad(nid, f'required input missing: {req}')
        for k, v in node['inputs'].items():
            if _is_link(v):
                src = graph.get(v[0])
                if src is None:
                    bad(nid, f'input {k} links to missing node {v[0]}')
                elif src.get('class_type') in NODE_SPECS and not 0 <= v[1] < len(NODE_SPECS[src['class_type']][1]):
                    bad(nid, f'input {k} uses output {v[1]} of {src["class_type"]}, which has '
                             f'{len(NODE_SPECS[src["class_type"]][1])}')
    if errors:
        raise GraphInvalid('Prompt outputs failed validation', errors)
    saves = [nid for nid, n in graph.items() if n['class_type'] == 'SaveImage']
    if not saves:
        raise GraphInvalid('Prompt has no outputs')
    order, state = [], {}

    def visit(nid, depth=0):
        if state.get(nid) == 2:
            return
        if state.get(nid) == 1:
            raise GraphInvalid(f'cycle through node {nid}')
        state[nid] = 1
        for v in graph[nid]['inputs'].values():
            if _is_link(v):
                visit(v[0], depth + 1)
        state[nid] = 2
        order.append(nid)

    for nid in sorted(graph, key=lambda x: int(x) if x.isdigit() else x):
        visit(nid)
    sizes = {}
    for nid in order:
        n = graph[nid]
        sizes[nid] = _size(graph, nid, n['class_type'], n['inputs'], sizes, input_dir)
    return order, sizes, saves


def _src(sizes, v):
    return sizes.get(v[0]) if _is_link(v) else None


def _size(graph, nid, cls, inp, sizes, input_dir):
    if cls == 'LoadImage':
        p = Path(input_dir) / str(inp['image'])
        if not p.is_file():
            raise GraphInvalid(f'Invalid image file: {inp["image"]}', {nid: {'class_type': cls, 'errors': [
                {'type': 'custom_validation_failed', 'message': 'Invalid image file', 'details': str(inp['image'])}]}})
        with Image.open(p) as im:
            return im.size
    if cls in ('ImageUpscaleWithModel', 'ClaudeUpscaleModelTiled'):
        s = _src(sizes, inp['image'])
        return (s[0] * 4, s[1] * 4)
    if cls == 'ImageScale':
        w, h = inp['width'], inp['height']
        if not (isinstance(w, int) and isinstance(h, int) and w > 0 and h > 0):
            raise GraphInvalid(f'node {nid}: ImageScale needs positive whole width/height (got {w}, {h})')
        for name, v in (('width', w), ('height', h)):
            if v > MAX_RESOLUTION:      
                raise GraphInvalid('Prompt outputs failed validation', {nid: {'class_type': cls, 'errors': [
                    {'type': 'value_bigger_than_max', 'message': f'Value {v} bigger than max of {MAX_RESOLUTION}',
                     'details': name, 'extra_info': {'input_name': name, 'input_config': ['INT', {'max': MAX_RESOLUTION}],
                                                     'received_value': v}}], 'dependent_outputs': []}})
        return (w, h)
    if cls in ('ImageBlur', 'ClaudeCannyTiled', 'ClaudeShadowToe'):
        return _src(sizes, inp['image'])
    if cls == 'VAEEncodeTiled':
        s = _src(sizes, inp['pixels'])
        if s[0] % 8 or s[1] % 8:
            raise GraphInvalid(f'node {nid}: VAE input {s[0]}x{s[1]} is not a multiple of 8')
        return (s[0] // 8, s[1] // 8)
    if cls == 'KSampler':
        d = inp['denoise']
        if not (isinstance(d, (int, float)) and 0 < d <= 1):
            raise GraphInvalid(f'node {nid}: denoise {d} out of range')
        return _src(sizes, inp['latent_image'])
    if cls == 'VAEDecodeTiled':
        s = _src(sizes, inp['samples'])
        return (s[0] * 8, s[1] * 8)
    if cls == 'SAM3_Detect':
        return _src(sizes, inp['image'])
    if cls == 'ClaudeMaskUnion':
        ms = [_src(sizes, v) for k, v in sorted(inp.items()) if _is_link(v)]
        if not ms:
            raise GraphInvalid(f'node {nid}: ClaudeMaskUnion needs at least one mask')
        if len(set(ms)) != 1:
            raise GraphInvalid(f'node {nid}: masks of different sizes {sorted(set(ms))}')
        return ms[0]
    if cls == 'MaskToImage':
        return _src(sizes, inp['mask'])
    if cls == 'ClaudeProtectGate':
        p = _src(sizes, inp['protect'])
        if 'release' in inp and _src(sizes, inp['release']) != p:
            raise GraphInvalid(f'node {nid}: release mask {_src(sizes, inp["release"])} is not the protect size {p}')
        return p
    if cls == 'ClaudeV4Finish':
        a = {k: _src(sizes, inp[k]) for k in ('creative', 'structure', 'init', 'pre')}
        if not (a['creative'] == a['structure'] == a['init']):
            raise GraphInvalid(f'node {nid}: finish inputs differ in size {a}')
        if 'protect' in inp and _src(sizes, inp['protect']) != a['pre']:
            raise GraphInvalid(f'node {nid}: protect mask {_src(sizes, inp["protect"])} is not the source size {a["pre"]}')
        if 'release' in inp and _src(sizes, inp['release']) != a['pre']:
            raise GraphInvalid(f'node {nid}: release mask {_src(sizes, inp["release"])} is not the source size {a["pre"]}')
        return a['creative']
    if cls == 'SaveImage':
        return _src(sizes, inp['images'])
    return None


class _Live:
    """The live frames of one prompt (see the module docstring)."""

    def __init__(self, fake, graph, sizes, client_id, pid, steps):
        self.fake, self.client_id, self.pid, self.steps = fake, client_id, pid, steps
        spots = [n for n in graph.values() if n['class_type'] == 'ClaudeSpotTiles']
        mode = spots[0]['inputs'].get('live_preview') if spots else None
        self.mode = mode if mode in ('rough', 'detailed') else None
        self.seq = 0
        self.node = None
        self.pass_no = 0
        self.counts = {}
        if not self.mode:
            return
        ks = next(k for k, v in graph.items() if v['class_type'] == 'KSampler')
        self.W, self.H = sizes[ks]                       
        load = _find_load_image(graph, ks)
        with Image.open(fake.root / 'input' / graph[load]['inputs']['image']) as im:
            self.src = im.convert('RGB')
        self.T = max(1, -(-max(self.W, self.H) // LIVE_GRID))
        xs = list(range(0, self.W, self.T))
        ys = list(range(0, self.H, self.T))
        self.windows = [(x, y, min(self.T, self.W - x), min(self.T, self.H - y)) for y in ys for x in xs]

    def _send(self, meta, jpg=b''):
        self.seq += 1
        meta = dict(meta, seq=self.seq, prompt_id=self.pid, node=self.node, steps=self.steps, card=0, t=time.time(),
                    canvas_latent=[self.W, self.H], **{'pass': self.pass_no})
        meta.setdefault('source', 'taesd' if self.mode == 'detailed' else 'l2r')
        js = json.dumps(meta).encode('utf8')
        self.fake._send_bytes(self.client_id, struct.pack('>I', LIVE_EVENT) + struct.pack('>I', len(js)) + js + jpg)
        self.counts[meta['kind']] = self.counts.get(meta['kind'], 0) + 1

    def _tile(self, rect, rough):
        x, y, w, h = rect
        sw, sh = self.src.size
        fx, fy = sw / float(self.W), sh / float(self.H)
        box = (int(x * fx), int(y * fy), max(int(x * fx) + 1, int((x + w) * fx)), max(int(y * fy) + 1, int((y + h) * fy)))
        side = float(self.fake.live_max_side)
        if rough:
            k = min(1.0, side / max(self.W, self.H))
            size = (max(1, round(w * k)), max(1, round(h * k)))
        else:
            k = min(1.0, side / (max(self.W, self.H) * 8))
            size = (max(1, round(w * 8 * k)), max(1, round(h * 8 * k)))
        im = self.src.crop(box).resize(size, Image.BILINEAR)
        if rough:
            a = np.asarray(im, np.float32) * np.array([0.82, 0.92, 0.78], np.float32)
            im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), 'RGB')
        buf = io.BytesIO()
        im.save(buf, format='JPEG', quality=80)
        return buf.getvalue(), list(size)

    def begin(self, node, pass_no):
        self.node, self.pass_no = node, pass_no
        if self.mode == 'rough':
            jpg, px = self._tile((0, 0, self.W, self.H), True)
            self._send({'kind': 'init', 'image': True, 'step': -1, 'rect_latent': [0, 0, self.W, self.H], 'px': px}, jpg)
        else:
            self._send({'kind': 'init', 'image': False, 'step': -1, 'rect_latent': [0, 0, self.W, self.H]})

    def step(self, step, seconds, interrupt):
        decode = self.mode == 'rough' or (self.steps - 1 - step) % 2 == 0
        if self.fake.live_groups:
            return self._group_step(step, seconds, interrupt, decode)
        each = seconds / max(1, len(self.windows))
        for rect in self.windows:
            if interrupt.is_set():
                return
            self._send({'kind': 'start', 'step': step, 'rect_latent': list(rect), 'phase': 'cfg'})
            time.sleep(each)
            if decode:
                jpg, px = self._tile(rect, self.mode == 'rough')
                self._send({'kind': 'win', 'image': True, 'step': step, 'rect_latent': list(rect), 'px': px}, jpg)
            else:
                self._send({'kind': 'win', 'image': False, 'step': step, 'rect_latent': list(rect)})

    def _group_step(self, step, seconds, interrupt, decode):
        """v5: one 'group' frame per LIVE_GROUP windows (node_pack live.py LiveEmitter.outline), tiles on decoded steps only."""
        groups = [self.windows[i:i + LIVE_GROUP] for i in range(0, len(self.windows), LIVE_GROUP)]
        each = seconds / max(1, len(groups))
        for gi, grp in enumerate(groups):
            if interrupt.is_set():
                return
            x0, y0 = min(r[0] for r in grp), min(r[1] for r in grp)
            x1, y1 = max(r[0] + r[2] for r in grp), max(r[1] + r[3] for r in grp)
            self._send({'kind': 'group', 'state': 'start', 'step': step, 'index': gi, 'n': len(groups),
                        'total': len(self.windows), 'windows_latent': [list(r) for r in grp],
                        'rect_latent': [x0, y0, x1 - x0, y1 - y0], 'phase': 'cfg'})
            time.sleep(each)
            if decode:
                for rect in grp:
                    jpg, px = self._tile(rect, self.mode == 'rough')
                    self._send({'kind': 'win', 'image': True, 'step': step, 'rect_latent': list(rect), 'px': px}, jpg)

    def end(self):
        self._send({'kind': 'pass_end', 'stats': dict(self.counts)})
        try:
            with open(self.fake.root / 'fake-live.jsonl', 'a', encoding='utf8') as f:
                f.write(json.dumps({'prompt_id': self.pid, 'node': self.node, 'pass': self.pass_no, 'mode': self.mode,
                                    'counts': dict(self.counts)}) + '\n')
        except OSError:
            pass
        self.counts = {}


def _find_load_image(graph, nid, seen=None):
    """The LoadImage feeding node nid (depth first)."""
    seen = seen or set()
    if nid in seen:
        return None
    seen.add(nid)
    n = graph[nid]
    if n['class_type'] == 'LoadImage':
        return nid
    for v in n['inputs'].values():
        if _is_link(v):
            r = _find_load_image(graph, v[0], seen)
            if r:
                return r
    return None


def parse_faults(spec):
    """'kind[@target],...' -> [(kind, target)]; target is an int stage, a prefix substring, or None (any prompt)."""
    out = []
    for part in (spec or '').split(','):
        part = part.strip()
        if not part:
            continue
        kind, _, target = part.partition('@')
        if kind not in FAULT_KINDS:
            raise ValueError(f'CU_FAKE_FAULT: unknown fault {kind!r} (use one of {", ".join(FAULT_KINDS)})')
        out.append((kind, int(target) if target.isdigit() else (target or None)))
    return out


class Interrupted(Exception):
    pass


class FakeComfy:
    def __init__(self, root, gpu=0, stage_seconds=None, faults=None, fault_dir=None, port=0, live_max_side=None,
                 live_groups=None):
        self.root = Path(root)
        
        self.live_groups = (os.environ.get('CLAUDE_LIVE_GROUPS', '').strip() == '1') if live_groups is None else bool(live_groups)
        
        try:
            self.live_max_side = int(live_max_side or os.environ.get('CLAUDE_LIVE_MAX_SIDE') or 2048)
        except ValueError:
            self.live_max_side = 2048
        for d in ('input', 'output', 'temp', 'user'):
            (self.root / d).mkdir(parents=True, exist_ok=True)
        self.gpu = gpu
        self.stage_seconds = float(os.environ.get('CU_FAKE_STAGE_SECONDS', '0.6') if stage_seconds is None else stage_seconds)
        self.start_seconds = float(os.environ.get('CU_FAKE_START_SECONDS', '0') or 0)
        self.ready_at = 0.0
        self.faults = parse_faults(os.environ.get('CU_FAKE_FAULT', '') if faults is None else faults)
        fd = os.environ.get('CU_FAKE_FAULT_DIR') if fault_dir is None else fault_dir
        self.fault_dir = Path(fd) if fd else None
        self.requested_port = port
        self.alive = False
        self._lock = threading.Lock()
        self._queue = []                 
        self._running = None
        self._number = 0
        self.history = {}
        self._interrupt = threading.Event()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._clients = []               
        self.server = None
        self.renders_log = self.root / 'fake-renders.jsonl'
        self._last_saved = {}
        self.verbose = False             

    
    def start(self):
        if self._take_fault(('nostart',)):
            raise RuntimeError('fake: CU_FAKE_FAULT nostart')
        fake = self

        class Handler(_Handler):
            app = fake
        self.server = _Server(('127.0.0.1', self.requested_port), Handler)
        self.port = self.server.server_address[1]
        self.ready_at = time.monotonic() + self.start_seconds
        self.alive = True
        threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': 0.1}, name=f'fake-http-{self.gpu}',
                         daemon=True).start()
        threading.Thread(target=self._executor, name=f'fake-exec-{self.gpu}', daemon=True).start()
        return self.port

    def stop(self):
        """Shut down like a killed process: stop serving, drop WebSocket clients, abandon the running prompt."""
        if not self.alive:
            return
        self.alive = False
        self._stop.set()
        self._wake.set()
        with self._lock:
            clients, self._clients = self._clients, []
        for _, sock, _ in clients:
            try:
                sock.close()
            except OSError as e:
                sys.stderr.write(f'fake: closing a WebSocket client failed: {e}\n')
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()

    
    def has_fault(self, kind):
        return any(k == kind for k, _ in self.faults)

    def _take_fault(self, kinds, stage=None, prefix=''):
        """The first matching fault of these kinds that has not fired yet (and mark it fired), else None."""
        for kind, at in self.faults:
            if kind not in kinds:
                continue
            if isinstance(at, int) and at != stage:
                continue
            if isinstance(at, str) and at not in (prefix or ''):
                continue
            key = f'{kind}@{"any" if at is None else at}'
            if self.fault_dir is not None:
                self.fault_dir.mkdir(parents=True, exist_ok=True)
                marker = self.fault_dir / f'{key}.fired'
                try:
                    with open(marker, 'x', encoding='utf8') as f:
                        f.write(time.strftime('%Y-%m-%d %H:%M:%S'))
                except FileExistsError:
                    continue
            else:
                if key in _fired_memory:
                    continue
                _fired_memory.add(key)
            return kind
        return None

    
    def submit(self, graph, client_id, prompt_id=None):
        if prompt_id is not None and not (isinstance(prompt_id, str) and UUID_RE.match(prompt_id)):
            raise GraphInvalid('prompt_id must be a valid UUID')
        order, sizes, saves = validate(graph, self.root / 'input')
        prefix = str(graph[saves[0]]['inputs']['filename_prefix'])
        m = STAGE_RE.search(prefix)
        if self._take_fault(('reject',), int(m.group(1)) if m else None, prefix):
            raise GraphInvalid('Prompt outputs failed validation', {saves[0]: {'class_type': 'SaveImage', 'errors': [
                {'type': 'fake_reject', 'message': 'CU_FAKE_FAULT reject', 'details': prefix}]}})
        d = self.root / 'fake-prompts'
        d.mkdir(exist_ok=True)
        (d / f'{prefix}.json').write_text(json.dumps(graph, sort_keys=True), encoding='utf8')
        with self._lock:
            self._number += 1
            pid = prompt_id or str(uuid.uuid4())
            self._queue.append([self._number, pid, graph, client_id, order, sizes, saves])
            n = self._number
        self._wake.set()
        self._broadcast_status()
        return pid, n

    def _executor(self):
        while not self._stop.is_set():
            self._wake.wait(0.2)
            self._wake.clear()
            while not self._stop.is_set():
                with self._lock:
                    if not self._queue:
                        break
                    job = self._queue.pop(0)
                    self._running = job
                    self._interrupt.clear()
                try:
                    self._execute(*job)
                finally:
                    with self._lock:
                        self._running = None
                    self._broadcast_status()

    def _execute(self, number, pid, graph, client_id, order, sizes, saves):
        order = run_order.order(graph)          
        prefix = str(graph[saves[0]]['inputs']['filename_prefix'])
        m = STAGE_RE.search(prefix)
        stage = int(m.group(1)) if m else None
        fault = self._take_fault(('fail', 'stall', 'crash', 'oom', 'nofile', 'badsize'), stage, prefix)
        send = lambda t, d: self._send(client_id, {'type': t, 'data': dict(d, prompt_id=pid)})
        msgs = [['execution_start', {'prompt_id': pid, 'timestamp': int(time.time() * 1000)}]]
        send('execution_start', {'timestamp': int(time.time() * 1000)})
        loaders = [n for n in order if graph[n]['class_type'] in ('CheckpointLoaderSimple', 'UpscaleModelLoader',
                                                                   'ControlNetLoader')]
        send('execution_cached', {'nodes': loaders[:1]})
        heavy = [n for n in order if graph[n]['class_type'] == 'KSampler']
        steps = 5
        per_step = self.stage_seconds / max(1, len(heavy) * steps + 2)
        live = _Live(self, graph, sizes, client_id, pid, steps) if heavy else None
        passes = 0
        try:
            for nid in order:
                if nid in loaders[:1]:
                    continue
                send('executing', {'node': nid, 'display_node': nid})
                if fault == 'stall':
                    while not self._stop.is_set():       
                        time.sleep(0.05)
                    return
                if self._interrupt.is_set():
                    raise Interrupted()
                if graph[nid]['class_type'] == 'KSampler':
                    passes += 1
                    if live is not None and live.mode:
                        live.begin(nid, passes)
                    for v in range(1, steps + 1):
                        if self._stop.is_set():
                            return
                        if self._interrupt.is_set():
                            raise Interrupted()
                        if live is not None and live.mode:
                            live.step(v - 1, per_step, self._interrupt)
                        else:
                            time.sleep(per_step)
                        send('progress', {'value': v, 'max': steps, 'node': nid})
                        if fault == 'crash' and nid == heavy[0] and v == 2:
                            sys.stderr.write(f'fake: CU_FAKE_FAULT crash at stage {stage} (exit {CRASH_EXIT_CODE})\n')
                            sys.stderr.flush()
                            os._exit(CRASH_EXIT_CODE)
                        if fault == 'fail' and nid == heavy[0] and v == 2:
                            raise RuntimeError('Fake engine failure requested by CU_FAKE_FAULT')
                        if fault == 'oom' and nid == heavy[0] and v == 2:
                            raise _FakeOOM('CUDA out of memory. Tried to allocate 2.00 GiB (CU_FAKE_FAULT oom)')
                    if live is not None and live.mode:
                        live.end()
                if graph[nid]['class_type'] == 'SaveImage':
                    out = self._save(graph, nid, sizes, prefix, wider=8 if fault == 'badsize' else 0)
                    if fault == 'nofile':
                        (self.root / 'output' / out['filename']).unlink()
                    send('executed', {'node': nid, 'output': {'images': [out]}})
                if fault == 'fail' and not heavy and graph[nid]['class_type'] == 'SAM3_Detect':
                    raise RuntimeError('Fake engine failure requested by CU_FAKE_FAULT')
            if not heavy:
                time.sleep(min(0.2, self.stage_seconds))
        except Interrupted:
            msgs.append(['execution_interrupted', {'prompt_id': pid, 'node_id': nid, 'node_type': graph[nid]['class_type'],
                                                   'executed': []}])
            send('execution_interrupted', {'node_id': nid, 'node_type': graph[nid]['class_type'], 'executed': []})
            self.history[pid] = {'prompt': [number, pid, graph, {'client_id': client_id}, saves], 'outputs': {},
                                 'status': {'status_str': 'error', 'completed': False, 'messages': msgs}}
            self._log_render(pid, prefix, stage, 'interrupted', None)
            return
        except RuntimeError as e:
            err = {'prompt_id': pid, 'node_id': nid, 'node_type': graph[nid]['class_type'], 'exception_message': str(e),
                   'exception_type': 'torch.OutOfMemoryError' if isinstance(e, _FakeOOM) else 'RuntimeError',
                   'traceback': ['fake traceback'], 'current_inputs': {}, 'current_outputs': {}}
            msgs.append(['execution_error', err])
            send('execution_error', {k: v for k, v in err.items() if k != 'prompt_id'})
            self.history[pid] = {'prompt': [number, pid, graph, {'client_id': client_id}, saves], 'outputs': {},
                                 'status': {'status_str': 'error', 'completed': False, 'messages': msgs}}
            self._log_render(pid, prefix, stage, 'error', None)
            return
        outputs = {nid: {'images': [self._last_saved[nid]]} for nid in saves if nid in self._last_saved}
        msgs.append(['execution_success', {'prompt_id': pid}])
        self.history[pid] = {'prompt': [number, pid, graph, {'client_id': client_id}, saves], 'outputs': outputs,
                             'status': {'status_str': 'success', 'completed': True, 'messages': msgs}}
        send('executing', {'node': None})
        send('execution_success', {})
        self._log_render(pid, prefix, stage, 'success', sizes[saves[0]])

    def _save(self, graph, nid, sizes, prefix, wider=0):
        size = (sizes[nid][0] + wider, sizes[nid][1])
        src_id = graph[nid]['inputs']['images'][0]
        mask_graph = graph[src_id]['class_type'] == 'MaskToImage'
        load = _find_load_image(graph, nid)
        if mask_graph:
            n_terms = sum(1 for n in graph.values() if n['class_type'] == 'SAM3_Detect')
            img = Image.new('L', size, 0)
            d = ImageDraw.Draw(img)
            fx = min(0.45, 0.15 + 0.05 * n_terms)
            w, h = size
            d.ellipse([w * (0.5 - fx), h * (0.5 - fx), w * (0.5 + fx), h * (0.5 + fx)], fill=255)
            img = img.convert('RGB')
        else:
            with Image.open(self.root / 'input' / graph[load]['inputs']['image']) as im:
                src = im.convert('RGB')
            a = np.asarray(src.resize(size, Image.LANCZOS), np.float32)
            a = a * (1 - TINT_AMOUNT) + TINT * TINT_AMOUNT
            img = Image.fromarray(np.clip(np.round(a), 0, 255).astype(np.uint8), 'RGB')
        name = f'{prefix}_00001_.png'
        n = 1
        while (self.root / 'output' / name).exists():
            n += 1
            name = f'{prefix}_{n:05d}_.png'
        img.save(self.root / 'output' / name, compress_level=1)
        rec = {'filename': name, 'subfolder': '', 'type': 'output'}
        self._last_saved = dict(self._last_saved, **{nid: rec})
        return rec

    def _log_render(self, pid, prefix, stage, status, size):
        line = json.dumps({'ts': time.strftime('%Y-%m-%dT%H:%M:%S'), 'gpu': self.gpu, 'prompt_id': pid, 'prefix': prefix,
                           'stage': stage, 'status': status, 'size': size}) + '\n'
        with self._lock:
            with open(self.renders_log, 'a', encoding='utf8') as f:
                f.write(line)

    def interrupt(self):
        self._interrupt.set()

    def queue_state(self):
        with self._lock:
            run = [[self._running[0], self._running[1], {}, {}, []]] if self._running else []
            pend = [[q[0], q[1], {}, {}, []] for q in self._queue]
        return {'queue_running': run, 'queue_pending': pend}

    def delete(self, ids):
        with self._lock:
            self._queue = [q for q in self._queue if q[1] not in set(ids)]

    
    def _send(self, client_id, obj):
        data = encode_frame(OP_TEXT, json.dumps(obj), mask=False)
        with self._lock:
            targets = [c for c in self._clients if client_id is None or c[0] == client_id]
        for cid, sock, lk in targets:
            try:
                with lk:
                    sock.sendall(data)
            except OSError:
                self._drop(sock)

    def _send_bytes(self, client_id, payload):
        data = encode_frame(OP_BIN, payload, mask=False)
        with self._lock:
            targets = [c for c in self._clients if client_id is None or c[0] == client_id]
        for cid, sock, lk in targets:
            try:
                with lk:
                    sock.sendall(data)
            except OSError:
                self._drop(sock)

    def _drop(self, sock):
        with self._lock:
            self._clients = [c for c in self._clients if c[1] is not sock]

    def _broadcast_status(self):
        with self._lock:
            remaining = len(self._queue) + (1 if self._running else 0)
        self._send(None, {'type': 'status', 'data': {'status': {'exec_info': {'queue_remaining': remaining}}}})

    def object_info(self):
        info = {cls: {'input': {'required': {k: ['*'] for k in spec[0]},
                                'optional': {k: ['*'] for k in NODE_OPTIONAL.get(cls, ()) if k not in spec[0]}},
                      'output': list(spec[1]), 'name': cls, 'category': 'fake'} for cls, spec in NODE_SPECS.items()}
        if self._take_fault(('missingnode',)):
            info.pop('ClaudeV4Finish', None)
        if self._take_fault(('oldpack',)):
            
            info['ClaudeSpotTiles']['input']['optional'] = {'clamp_blend': ['*']}
        return info


class _FakeOOM(RuntimeError):
    pass


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False


class _Handler(BaseHTTPRequestHandler):
    app = None
    protocol_version = 'HTTP/1.1'

    def log_message(self, fmt, *args):
        if self.app is not None and self.app.verbose:
            sys.stdout.write('fake-comfy %s - %s\n' % (self.address_string(), fmt % args))

    def _json(self, code, obj):
        body = json.dumps(obj).encode('utf8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get('Content-Length') or 0)
        if not n:
            return {}
        return json.loads(self.rfile.read(n))

    def do_GET(self):
        a = self.app
        path, _, query = self.path.partition('?')
        if path == '/ws':
            return self._websocket(query)
        if path == '/system_stats':
            if time.monotonic() < a.ready_at:
                return self._json(503, {'error': 'starting (CU_FAKE_START_SECONDS)'})
            return self._json(200, {'system': {'os': 'fake', 'comfyui_version': 'fake'}, 'devices': [
                {'name': f'Fake GPU {a.gpu}', 'type': 'cuda', 'index': a.gpu, 'vram_total': 32 << 30,
                 'vram_free': 30 << 30}]})
        if path == '/object_info':
            return self._json(200, a.object_info())
        if path == '/queue':
            return self._json(200, a.queue_state())
        if path == '/history':
            return self._json(200, a.history)
        if path.startswith('/history/'):
            pid = path.split('/', 2)[2]
            return self._json(200, {pid: a.history[pid]} if pid in a.history else {})
        return self._json(404, {'error': 'not found'})

    def do_POST(self):
        a = self.app
        try:
            body = self._body()
        except ValueError:
            return self._json(400, {'error': {'type': 'invalid_json', 'message': 'invalid JSON'}})
        if self.path == '/prompt':
            try:
                pid, n = a.submit(body.get('prompt'), body.get('client_id'), body.get('prompt_id'))
            except GraphInvalid as e:
                return self._json(400, {'error': {'type': 'prompt_outputs_failed_validation', 'message': str(e),
                                                  'details': '', 'extra_info': {}}, 'node_errors': e.node_errors})
            return self._json(200, {'prompt_id': pid, 'number': n, 'node_errors': {}})
        if self.path == '/interrupt':
            a.interrupt()
            return self._json(200, {})
        if self.path == '/queue':
            if body.get('clear'):
                a.delete([q[1] for q in a._queue])
            if body.get('delete'):
                a.delete(body['delete'])
            return self._json(200, {})
        return self._json(404, {'error': 'not found'})

    def _websocket(self, query):
        a = self.app
        key = self.headers.get('Sec-WebSocket-Key')
        if not key or 'websocket' not in (self.headers.get('Upgrade') or '').lower():
            return self._json(400, {'error': 'not a websocket request'})
        if a.has_fault('nows'):
            self.close_connection = True
            return self._json(503, {'error': 'CU_FAKE_FAULT nows: progress feed refused'})
        cid = None
        for part in query.split('&'):
            k, _, v = part.partition('=')
            if k == 'clientId':
                cid = v
        cid = cid or uuid.uuid4().hex
        self.send_response(101, 'Switching Protocols')
        self.send_header('Upgrade', 'websocket')
        self.send_header('Connection', 'Upgrade')
        self.send_header('Sec-WebSocket-Accept', accept_key(key))
        self.end_headers()
        self.wfile.flush()
        sock = self.connection
        lk = threading.Lock()
        with a._lock:
            a._clients.append((cid, sock, lk))
        a._send(cid, {'type': 'status', 'data': {'status': {'exec_info': {'queue_remaining': 0}}, 'sid': cid}})
        parser = FrameParser()
        sock.settimeout(0.5)
        try:
            while a.alive:
                try:
                    chunk = sock.recv(65536)
                except TimeoutError:
                    continue
                if not chunk:
                    break
                parser.feed(chunk)
                while True:
                    fr = parser.pop()
                    if fr is None:
                        break
                    if fr[1] == OP_CLOSE:
                        with lk:
                            sock.sendall(encode_frame(OP_CLOSE, fr[2][:2], mask=False))
                        return
                    if fr[1] == OP_PING:
                        with lk:
                            sock.sendall(encode_frame(OP_PONG, fr[2], mask=False))
        except OSError as e:
            sys.stdout.write(f'fake-comfy websocket {cid} closed: {e}\n')
        finally:
            a._drop(sock)
            self.close_connection = True


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description='Fake ComfyUI (Creative Upscaler tests)')
    ap.add_argument('--port', type=int, required=True)
    ap.add_argument('--root', required=True)
    ap.add_argument('--gpu', type=int, default=0)
    ap.add_argument('--path', action='append', default=[])
    a = ap.parse_args(argv)
    fake = FakeComfy(a.root, gpu=a.gpu, port=a.port)
    fake.verbose = True
    try:
        port = fake.start()
    except RuntimeError as e:          
        sys.stderr.write(f'{e}; exiting with {NOSTART_EXIT_CODE}\n')
        sys.stderr.flush()
        return NOSTART_EXIT_CODE
    sys.stdout.write(f'Fake ComfyUI ready. To see the GUI go to: http://127.0.0.1:{port}\n')
    sys.stdout.flush()
    try:
        while fake.alive:
            time.sleep(0.5)
    except KeyboardInterrupt:
        fake.stop()
    return 0


if __name__ == '__main__':
    sys.exit(main())
