"""Live implementation."""


import io
import statistics
import threading
import time

import numpy as np
from PIL import Image

MAX_SIDE = 2048
THUMB_SIDE = 256
ENCODE_EVERY_S = 0.25
THUMB_EVERY_S = 1.0
KEEP_FROZEN = 16
JPEG_Q = 85
PASSES_PER_STAGE = 2
EARLY_MIX = True              
MIX_FULL_AT = 0.5             
MIX_POWER = 2                 
FULL_MIN_GAIN = 1.25          
FULL_BAND = 512               
FULL_BUDGET_MB = 1280         
FROZEN_FULL_KEEP = 1          
FROZEN_FULL_IDLE_S = 600.0    
REGION_MAX_SIDE = 4096        
REGION_JPEG_Q = 92            
GONE_KEEP_S = 5.0             


def mix_weight(step, steps):
    """How much of a detailed tile's estimate is shown at 0-based sampler step `step` of `steps` (the rest is the stage's own
    picture): 0..1, rising as the square of the pass progress and 1.0 from the midpoint on. 1.0 when the step is unknown."""
    if not EARLY_MIX or steps is None or step is None or steps <= 0 or step < 0:
        return 1.0
    p = min(1.0, (step + 1) / float(steps))
    if p >= MIX_FULL_AT:
        return 1.0
    return (p / MIX_FULL_AT) ** MIX_POWER


def fit(w, h, side):
    k = min(1.0, side / float(max(w, h)))
    return max(1, int(round(w * k))), max(1, int(round(h * k)))


def _median(xs):
    return round(statistics.median(xs), 3) if xs else None


def _ceil(v):
    """Smallest whole number not below v (v >= 0)."""
    n = int(v)
    return n if n == v else n + 1


class FullPicture:
    """preview design: one image's live composite at full size (module docstring). `size` is its own size in pixels, `frame` the
    image's final result size; `scale` = its pixels per result pixel (1.0 on the last stage when the tiles reach that far,
    0.5 on the first stage of a 4x image). The pixels are a numpy array, 3 bytes each, made when the first pass starts."""

    def __init__(self, size, frame):
        self.w, self.h = int(size[0]), int(size[1])
        self.frame = (int(frame[0]), int(frame[1]))
        self.scale = self.w / float(self.frame[0])
        self.nbytes = self.w * self.h * 3
        self.a = None
        self.lock = threading.Lock()
        self.pastes = 0
        self.reads = 0

    def lay(self, src):
        """Start from `src` (the stage's own picture, PIL RGB at its own size): resampled to this size from its own pixels,
        FULL_BAND rows at a time. Pillow reads the rows next to a band from the whole picture, so the bands leave no seam."""
        a = self.a
        if a is None:
            a = np.empty((self.h, self.w, 3), np.uint8)
        sw, sh = src.size
        for y0 in range(0, self.h, FULL_BAND):
            y1 = min(self.h, y0 + FULL_BAND)
            band = src.resize((self.w, y1 - y0), Image.BICUBIC, box=(0, y0 * sh / float(self.h), sw, y1 * sh / float(self.h)))
            with self.lock:
                a[y0:y1] = np.asarray(band)
        with self.lock:
            self.a = a

    def under(self, src, box):
        """The part of the stage's own picture under `box` (x0, y0, x1, y1 in this picture's pixels, inside it), at the
        box's size: the pixels `lay` put there."""
        x0, y0, x1, y1 = box
        sw, sh = src.size
        return src.resize((x1 - x0, y1 - y0), Image.BICUBIC, box=(x0 * sw / float(self.w), y0 * sh / float(self.h),
                                                                  x1 * sw / float(self.w), y1 * sh / float(self.h)))

    def paste(self, piece, x0, y0):
        """`piece` (PIL RGB, already inside the picture) at (x0, y0)."""
        with self.lock:
            if self.a is None:
                return
            self.a[y0:y0 + piece.height, x0:x0 + piece.width] = np.asarray(piece)
            self.pastes += 1

    def region(self, x, y, w, h):
        """(jpeg, (x, y, w, h)) for the asked rectangle of the result (result pixels), cut to the image: this picture's own
        pixels under it, so the JPEG is `scale` times the rectangle's size (the same size at scale 1.0). None before the
        first pass has started. ValueError when the rectangle is too large or outside the image."""
        if w <= 0 or h <= 0 or w > REGION_MAX_SIDE or h > REGION_MAX_SIDE:
            raise ValueError(f'Region width and height must be 1 to {REGION_MAX_SIDE} px')
        fw, fh = self.frame
        x0, y0 = max(0, int(x)), max(0, int(y))
        x1, y1 = min(fw, int(x) + int(w)), min(fh, int(y) + int(h))
        if x1 <= x0 or y1 <= y0:
            raise ValueError('The region is outside the image')
        kx, ky = self.w / float(fw), self.h / float(fh)
        cx0, cy0 = int(x0 * kx), int(y0 * ky)
        cx1, cy1 = min(self.w, max(cx0 + 1, _ceil(x1 * kx))), min(self.h, max(cy0 + 1, _ceil(y1 * ky)))
        with self.lock:
            if self.a is None:
                return None
            part = self.a[cy0:cy1, cx0:cx1].copy()
            self.reads += 1
        img = Image.fromarray(part)
        size = (max(1, int(round((x1 - x0) * kx))), max(1, int(round((y1 - y0) * ky))))
        box = (x0 * kx - cx0, y0 * ky - cy0, min(float(img.width), x1 * kx - cx0), min(float(img.height), y1 * ky - cy0))
        if size != img.size or box != (0, 0, img.width, img.height):
            img = img.resize(size, Image.BILINEAR, box=box)       
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=REGION_JPEG_Q, subsampling=0)
        return buf.getvalue(), (x0, y0, x1 - x0, y1 - y0)


class LiveCanvas:
    def __init__(self, jid, iid, media_id, stage, stages, out_size, supersample, frame, samplers, mode, cards, alpha=False,
                 source=None, full_scale=None, log=None, clock=time.monotonic, wall=time.time, run_order=None, groups=False):
        self.jid, self.iid, self.media_id = jid, iid, media_id
        self.stage, self.stages = int(stage), int(stages)
        self.ow, self.oh = int(out_size[0]), int(out_size[1])            
        self.s = float(supersample)
        self.frame = [int(frame[0]), int(frame[1])]                       
        self.samplers = {str(v): k for k, v in (samplers or {}).items()}  
        self.mode = mode                                                  
        self.cards = [int(c) for c in (cards or [])]                     
        self.alpha = bool(alpha)
        self.log = log
        self.clock, self.wall = clock, wall
        self.size = fit(self.ow, self.oh, MAX_SIDE)
        self.k = self.size[0] / float(self.ow)                            
        self.lock = threading.Lock()
        self.state = 'preparing'
        self.preview = None
        self.fallback = False
        self.pass_name = None
        self.pass_index = 0
        self.step = 0
        self.steps = 0
        self.rects = {}                                                   
        self.img = None
        self.start_img = None
        self.paint_seq = 0
        self._enc = (None, -1, 0.0)                                       
        self._thumb = (None, -1, 0.0)
        self._thumb_report = (0, -1.0)                                    
        self.created = clock()
        self.first_frame_s = None
        self.pass_started = None
        self.step_starts = {}                                             
        self.tile_gaps = []
        self.last_tile = None
        self.frames = 0
        self.dropped_unreadable = 0
        
        self.pass_order = [str(p) for p in (run_order or [])]
        self.groups = bool(groups)
        self.evals = {}                                                   
        self.pag_seen = False
        self.earlier = None                                               
        self.first_tile_s = None
        self.pass_tiles_s = {}                                            
        self.pass_counts = {}                                             
        
        
        self.full = None
        self.large_tiles = bool(full_scale)                   
        self.full_note = 'off' if not full_scale else None    
        self.src_img = None                                   
        size = self._full_size(full_scale)
        if size is not None:
            self.full = FullPicture(size, self.frame)
        if source is not None:
            self.set_source(source)

    
    def _full_size(self, full_scale):
        """The size of this stage's full-size picture, or None when none is kept (and `full_note` says why)."""
        if not full_scale:
            return None
        if self.mode != 'detailed':
            self.full_note = 'rough'
            return None
        if self.alpha:
            self.full_note = 'transparency'
            return None
        k = min(1.0, float(full_scale))
        fw, fh = max(1, int(round(self.ow * k))), max(1, int(round(self.oh * k)))
        if fw < self.size[0] * FULL_MIN_GAIN:
            self.full_note = 'small'
            return None
        return fw, fh

    @property
    def full_bytes(self):
        """What this image's full-size picture holds or will hold, with the stage's input picture kept for it."""
        full, src = self.full, self.src_img
        return (full.nbytes if full is not None else 0) + (src.width * src.height * 4 if src is not None else 0)

    def drop_full(self, note=None):
        """Give the full-size picture up (no memory for it, a rough or fallback frame, a later stage took over)."""
        with self.lock:
            self._drop_full_locked(note)

    def _drop_full_locked(self, note=None):
        if self.full is not None and note:
            self.full_note = note
        self.full = None
        self.src_img = None

    def release_full(self):
        """Hand the full-size picture over (to the frozen last frame); the stage's input picture goes."""
        with self.lock:
            full = self.full if self._full_ready_locked() else None
            self.full = None
            self.src_img = None
            return full

    def _full_ready_locked(self):
        return (self.full is not None and self.full.a is not None and self.img is not None and self.preview == 'detailed'
                and not self.fallback)

    def set_source(self, img):
        """The stage's input picture (PIL), the start picture of a detailed pass (and of a later stage while it prepares)."""
        im = img.convert('RGB') if img.mode != 'RGB' else img
        if self.full is not None:
            self.src_img = im
        if im.size != (self.ow, self.oh) and im.size != self.size:
            
            im = im.resize(self.size, Image.BOX if im.width > self.size[0] * 2 else Image.BILINEAR)
        elif im.size != self.size:
            im = im.resize(self.size, Image.BILINEAR)
        with self.lock:
            self.start_img = im

    
    def _canvas_px(self, v):
        return v * 8.0 / self.s * self.k

    def _frac(self, rect):
        x, y, w, h = rect
        ox, oy, ow, oh = (v * 8.0 / self.s for v in (x, y, w, h))
        x0, y0 = max(0.0, ox / self.ow), max(0.0, oy / self.oh)
        x1, y1 = min(1.0, (ox + ow) / self.ow), min(1.0, (oy + oh) / self.oh)
        return {'x': round(x0, 5), 'y': round(y0, 5), 'w': round(max(0.0, x1 - x0), 5), 'h': round(max(0.0, y1 - y0), 5)}

    def on_frame(self, meta, jpeg=b''):
        kind = meta.get('kind')
        now = self.clock()
        try:
            tile = None
            if kind in ('init', 'win') and meta.get('image', True) and jpeg:
                tile = Image.open(io.BytesIO(jpeg))
                tile.load()
                tile = tile.convert('RGB')
        except (OSError, ValueError) as e:
            self.dropped_unreadable += 1
            if self.log is not None and self.dropped_unreadable <= 3:
                self.log.warn('live_frame_unreadable', f'A live preview frame could not be read: {e}', job=self.jid, item=self.iid)
            return
        full, src = self.full, self.src_img
        if kind == 'init' and tile is None and meta.get('source') == 'taesd' and full is not None and src is not None:
            full.lay(src)          
        if kind == 'init':
            self._keep_earlier()   
        with self.lock:
            self.frames += 1
            if kind == 'init':
                self.pass_counts = {}
            ck = kind + ('_tile' if tile is not None else '')
            self.pass_counts[ck] = self.pass_counts.get(ck, 0) + 1
            if self.first_frame_s is None:
                self.first_frame_s = round(now - self.created, 2)
            if meta.get('fallback'):
                self.fallback = True
                self._drop_full_locked('rough')     
            card = int(meta.get('card') or 0)
            if kind == 'init':
                self.pass_index = int(meta.get('pass') or (self.pass_index + 1))
                self.pass_name = self.samplers.get(str(meta.get('node'))) or ('structure', 'detail')[(self.pass_index - 1) % 2]
                self.step, self.steps = 0, int(meta.get('steps') or self.steps or 0)
                self.rects = {}
                self.evals, self.pag_seen = {}, False
                self.state = 'sampling'
                self.pass_started = (now, self.wall())
                self.step_starts, self.tile_gaps, self.last_tile = {}, [], None
                if tile is not None:            
                    W, H = meta['canvas_latent']
                    sx, sy = tile.width / float(W), tile.height / float(H)
                    box = (0, 0, max(1, round(self.ow * self.s / 8.0 * sx)), max(1, round(self.oh * self.s / 8.0 * sy)))
                    self.img = tile.crop(box).resize(self.size, Image.BILINEAR)
                    self.preview = 'rough'
                    self._drop_full_locked('rough')
                else:                           
                    self.img = self.start_img.copy() if self.start_img is not None else Image.new('RGB', self.size, (46, 46, 46))
                    self.preview = 'detailed' if meta.get('source') == 'taesd' else (self.preview or self.mode)
                self.paint_seq += 1
                return
            if kind == 'start':
                step = int(meta.get('step', -1))
                if step >= 0:
                    self.step = step + 1
                    self.steps = int(meta.get('steps') or self.steps)
                    self.step_starts.setdefault(step, now)
                if self.last_tile is not None:
                    self.tile_gaps.append(now - self.last_tile)
                    del self.tile_gaps[:-200]
                self.last_tile = now
                self.rects[card] = [self._frac(meta['rect_latent'])]
                if self.state != 'sampling':
                    self.state = 'sampling'
                return
            if kind == 'group':            
                step = int(meta.get('step', -1))
                if step >= 0:
                    self.step = max(self.step, step + 1)
                    self.steps = int(meta.get('steps') or self.steps)
                    self.step_starts.setdefault(step, now)
                if self.last_tile is not None:
                    self.tile_gaps.append(now - self.last_tile)
                    del self.tile_gaps[:-200]
                self.last_tile = now
                wins = meta.get('windows_latent') or [meta['rect_latent']]
                self.rects[card] = [self._frac(r) for r in wins]
                phase = meta.get('phase') or 'cfg'
                self.pag_seen = self.pag_seen or phase == 'pag'
                self.evals[card] = {'group': int(meta.get('index') or 0), 'groups': int(meta.get('n') or 0),
                                    'windows': len(wins), 'phase': phase, 'step': step}
                if self.state != 'sampling':
                    self.state = 'sampling'
                return
            if kind == 'win':
                step = int(meta.get('step', -1))
                if step >= 0:
                    self.step = max(self.step, step + 1)
                self.last_tile = now
                if tile is not None and self.first_tile_s is None:
                    self.first_tile_s = round(now - self.created, 2)
                if tile is not None and self.pass_name is not None and self.pass_name not in self.pass_tiles_s:
                    self.pass_tiles_s[self.pass_name] = round(now - self.created, 2)
                if tile is not None and self.img is not None:
                    x, y, w, h = meta['rect_latent']
                    x0, y0 = int(round(self._canvas_px(x))), int(round(self._canvas_px(y)))
                    x1, y1 = int(round(self._canvas_px(x + w))), int(round(self._canvas_px(y + h)))
                    if x1 > x0 and y1 > y0:
                        
                        
                        big = self.large_tiles and tile.width >= 2 * (x1 - x0) and tile.height >= 2 * (y1 - y0)
                        piece = tile.resize((x1 - x0, y1 - y0), Image.BOX if big else Image.BILINEAR)
                        wgt = 1.0
                        if meta.get('source') == 'l2r' and self.preview == 'detailed':
                            self.preview = 'rough'      
                            self._drop_full_locked('rough')
                        elif meta.get('source') == 'taesd' and self.start_img is not None:
                            
                            wgt = mix_weight(step, int(meta.get('steps') or self.steps or 0))
                            if wgt < 1.0:
                                piece = Image.blend(self.start_img.crop((x0, y0, x1, y1)), piece, wgt)
                        self.img.paste(piece, (x0, y0))
                        if self.full is not None and meta.get('source') == 'taesd':
                            self._full_paste(tile, (x, y, w, h), wgt)
                        self.paint_seq += 1
                return
            if kind == 'pass_end':
                self.rects = {}
                self.evals = {}
                self.state = 'finishing' if self.pass_index >= PASSES_PER_STAGE else 'between'
                ended = {'pass': self.pass_name, 'pass_index': self.pass_index, 'node': meta.get('node'),
                         'received': dict(self.pass_counts), 'sent': meta.get('stats'), 'groups': self.groups,
                         'first_tile_s': self.pass_tiles_s.get(self.pass_name), 'seconds': None if self.pass_started is None
                         else round(now - self.pass_started[0], 2)}
            else:
                return
        
        
        if self.log is not None:
            self.log.info('live_pass_end', f'Live preview: {ended["pass"]} pass ended', job=self.jid, item=self.iid,
                          stage=self.stage, data=ended)

    def _keep_earlier(self):
        """v5: a new pass is starting on a canvas that already holds a pass: keep that pass's last composite as the earlier
        pass's picture (JPEG, encoded once, outside the lock)."""
        with self.lock:
            if self.img is None or self.pass_index < 1:
                return
            img, name, seq, size, preview = self.img.copy(), self.pass_name, self.paint_seq, list(self.size), self.preview
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=JPEG_Q)
        with self.lock:
            self.earlier = (buf.getvalue(), name, seq, size, preview)

    def earlier_jpeg(self):
        """The earlier pass's last composite as JPEG, or None (GET .../live-pass.jpg)."""
        with self.lock:
            return self.earlier[0] if self.earlier is not None else None

    def _earlier_snap(self, base_url):
        e = self.earlier
        if e is None:
            return None
        return {'pass': e[1], 'url': f'{base_url}/live-pass.jpg?seq={e[2]}', 'seq': e[2], 'size': e[3], 'preview': e[4]}

    def _step_progress(self):
        """v5: 0-1 within the current step from the newest group of each card (a PAG evaluation, once seen, is the second
        half of a step); None when the engine sends no group frames or nothing is being evaluated."""
        if not self.groups or self.state != 'sampling' or not self.evals:
            return None
        best = 0.0
        for e in self.evals.values():
            if e['groups'] <= 0 or e['step'] is None or e['step'] + 1 != self.step:
                continue
            sub = (e['group'] + 1) / float(e['groups'])
            if self.pag_seen:
                sub = 0.5 + sub / 2.0 if e['phase'] == 'pag' else sub / 2.0
            best = max(best, sub)
        return round(min(1.0, best), 3)

    def _full_paste(self, tile, rect, wgt):
        """preview design: the same tile into the full-size picture, at that picture's own scale, with the same preview design weight against
        the stage's own picture at full size. Called under the lock; a tile is at most one window, so this is a few ms."""
        full = self.full
        if full.a is None:
            return
        x, y, w, h = rect
        kx, ky = full.w / float(self.ow) * 8.0 / self.s, full.h / float(self.oh) * 8.0 / self.s     
        x0, y0 = int(round(x * kx)), int(round(y * ky))
        x1, y1 = int(round((x + w) * kx)), int(round((y + h) * ky))
        if x1 <= x0 or y1 <= y0 or x0 >= full.w or y0 >= full.h:
            return
        size = (x1 - x0, y1 - y0)
        piece = tile
        if tile.size != size:
            piece = tile.resize(size, Image.BOX if tile.width >= 2 * size[0] and tile.height >= 2 * size[1] else Image.BICUBIC)
        cx1, cy1 = min(x1, full.w), min(y1, full.h)          
        if (cx1, cy1) != (x1, y1):
            piece = piece.crop((0, 0, cx1 - x0, cy1 - y0))
        if wgt < 1.0 and self.src_img is not None:
            piece = Image.blend(full.under(self.src_img, (x0, y0, cx1, cy1)), piece, wgt)
        full.paste(piece, x0, y0)

    def region(self, x, y, w, h):
        """(jpeg, (x, y, w, h), scale, image_seq) of the full-size picture under a rectangle of the result, or None when
        there is no full-size picture (module docstring). ValueError for a rectangle that cannot be served."""
        with self.lock:
            full = self.full if self._full_ready_locked() else None
            seq = self.paint_seq
        if full is None:
            return None
        got = full.region(x, y, w, h)
        return None if got is None else got + (full.scale, seq)

    
    def set_state(self, state):
        with self.lock:
            self.state = state
            if state not in ('sampling',):
                self.rects = {}
                self.evals = {}

    
    def _step_s(self):
        st = sorted(self.step_starts.items())
        gaps = [b[1] - a[1] for a, b in zip(st, st[1:])]
        return _median(gaps[-10:])

    def at(self):
        with self.lock:
            return {'stage': self.stage, 'stages': self.stages, 'pass': self.pass_name, 'step': self.step, 'steps': self.steps}

    def snapshot(self, base_url):
        now = self.clock()
        with self.lock:
            seq = self.paint_seq
            ts, tt = self._thumb_report
            if seq != ts and now - tt >= THUMB_EVERY_S:
                self._thumb_report = (seq, now)
                ts = seq
            has = self.img is not None
            full = self.full if self._full_ready_locked() else None
            timing = {'step_s': self._step_s(), 'tile_s': _median(self.tile_gaps[-50:]),
                      'steps_done': max(0, self.step - 1) if self.state == 'sampling' else self.step,
                      'pass_started': None if self.pass_started is None else
                      time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(self.pass_started[1])) + _tz(),
                      'last_tile_age_s': None if self.last_tile is None else round(now - self.last_tile, 2),
                      'first_frame_s': self.first_frame_s, 'first_tile_s': self.first_tile_s,
                      'pass_tiles_s': dict(self.pass_tiles_s)}
            sampling = self.state == 'sampling'

            def gpu(c):
                return self.cards[c] if c < len(self.cards) else c
            return {'job_id': self.jid, 'item_id': self.iid, 'media_id': self.media_id, 'state': self.state,
                    'preview': self.preview if has else None, 'card': self.cards[0] if self.cards else None,
                    'cards': list(self.cards), 'split': len(self.cards) > 1,      
                    'stage': self.stage, 'stages': self.stages, 'pass': self.pass_name, 'pass_index': self.pass_index,
                    'passes': PASSES_PER_STAGE, 'step': self.step, 'steps': self.steps,
                    
                    'pass_order': list(self.pass_order),
                    'rects': [dict(r, card=gpu(c)) for c, rs in sorted(self.rects.items()) for r in rs] if sampling else [],
                    'evaluation': ([{'card': gpu(c), 'group': e['group'], 'groups': e['groups'], 'windows': e['windows'],
                                     'phase': e['phase']} for c, e in sorted(self.evals.items())] if sampling else [])
                    if self.groups else None,
                    'step_progress': self._step_progress(),
                    'earlier_pass': self._earlier_snap(base_url),
                    'image_seq': seq if has else None,
                    'canvas_url': f'{base_url}/live.jpg?seq={seq}' if has else None,
                    'canvas_size': list(self.size) if has else None,
                    'thumb_url': f'{base_url}/live-thumb.jpg?seq={ts}' if has else None,
                    
                    'region_url': f'{base_url}/live-region.jpg?seq={seq}' if full is not None else None,
                    'region_scale': round(full.scale, 4) if full is not None else None,
                    'frame': list(self.frame), 'alpha': self.alpha, 'fallback': self.fallback, 'timing': timing}

    def jpeg(self, force=False):
        """The canvas as JPEG (encoded at most every ENCODE_EVERY_S unless force); None when there is no picture yet."""
        now = self.clock()
        with self.lock:
            data, seq, t = self._enc
            if self.img is None:
                return data
            if data is not None and (seq == self.paint_seq or (not force and now - t < ENCODE_EVERY_S)):
                return data
            img, seq = self.img.copy(), self.paint_seq
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=JPEG_Q)
        data = buf.getvalue()
        with self.lock:
            self._enc = (data, seq, now)
        return data

    def thumb(self):
        now = self.clock()
        with self.lock:
            data, seq, t = self._thumb
            if self.img is None:
                return data
            if data is not None and (seq == self.paint_seq or now - t < THUMB_EVERY_S):
                return data
            img, seq = self.img.copy(), self.paint_seq
        img.thumbnail((THUMB_SIDE, THUMB_SIDE), Image.BILINEAR)
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=JPEG_Q)
        data = buf.getvalue()
        with self.lock:
            self._thumb = (data, seq, now)
        return data


def _tz():
    off = -time.altzone if time.localtime().tm_isdst > 0 else -time.timezone
    sign = '+' if off >= 0 else '-'
    off = abs(off)
    return f'{sign}{off // 3600:02d}:{off % 3600 // 60:02d}'


class Frozen:
    """The last frame of a stopped or failed image: its JPEGs and its last snapshot. No canvas picture is kept; the
    full-size picture (preview design) is taken over when the image had one, so "Last frame" at 100 % stays as sharp as the live
    picture was, until LiveBoard needs the memory or nobody has read a region of it for a while (`drop_full`)."""

    def __init__(self, canvas, state):
        canvas.set_state(state)
        self.jpg = canvas.jpeg(force=True)
        self.thumb_jpg = canvas.thumb()
        self.state = state
        self.snap = canvas.snapshot(f'/api/jobs/{canvas.jid}/items/{canvas.iid}')
        self.snap.update(state=state, rects=[])
        self.snap['timing'] = dict(self.snap['timing'], last_tile_age_s=None)
        self.at = canvas.at()
        self.clock = canvas.clock
        self.full = canvas.release_full()
        self.full_used = self.clock()
        self.earlier_jpg = canvas.earlier_jpeg()      

    def earlier_jpeg(self):
        return self.earlier_jpg

    @property
    def full_bytes(self):
        full = self.full
        return full.nbytes if full is not None else 0

    def drop_full(self):
        self.full = None

    def snapshot(self, base_url):
        full = self.full
        return dict(self.snap, region_url=f'{base_url}/live-region.jpg?seq={self.snap.get("image_seq")}' if full is not None
                    else None, region_scale=round(full.scale, 4) if full is not None else None)

    def region(self, x, y, w, h):
        full = self.full
        if full is None:
            return None
        got = full.region(x, y, w, h)
        self.full_used = self.clock()
        return None if got is None else got + (full.scale, self.snap.get('image_seq'))

    def jpeg(self, force=False):
        return self.jpg

    def thumb(self):
        return self.thumb_jpg


class Gone:
    """The last canvas and miniature JPEGs of an image whose live picture was just dropped (LiveBoard.drop), and its
    earlier pass's picture when it had one (R-V1)."""

    def __init__(self, jpg, thumb_jpg, t, earlier_jpg=None):
        self.jpg, self.thumb_jpg, self.t, self.earlier_jpg = jpg, thumb_jpg, t, earlier_jpg

    def earlier_jpeg(self):
        return self.earlier_jpg

    def jpeg(self, force=False):
        return self.jpg

    def thumb(self):
        return self.thumb_jpg


class LiveBoard:
    """Every live canvas of this service, by (job, item); the frozen last frames of stopped and failed images."""

    def __init__(self, log=None, full_budget_mb=None):
        self.log = log
        self._lock = threading.Lock()
        self._live = {}
        self._frozen = {}
        self._gone = {}                
        self._earlier_gone = {}        
        self.seq = 0
        
        self.full_budget = int((FULL_BUDGET_MB if full_budget_mb is None else full_budget_mb) * (1 << 20))
        self.frozen_full_idle_s = FROZEN_FULL_IDLE_S

    def full_bytes(self):
        """Bytes held or reserved by full-size live pictures now (diagnostics and tests)."""
        with self._lock:
            return sum(c.full_bytes for c in self._live.values()) + sum(f.full_bytes for f in self._frozen.values())

    def begin(self, jid, iid, **kw):
        c = LiveCanvas(jid, iid, log=self.log, **kw)
        prime = skipped = False
        with self._lock:
            old = self._live.get((jid, iid))
            self._gone.pop((jid, iid), None)
            gone = self._frozen.pop((jid, iid), None)
            if gone is not None:
                gone.drop_full()
            if c.full is not None:
                
                
                need = c.full_bytes
                used = (sum(x.full_bytes for x in self._live.values() if x is not old)
                        + sum(f.full_bytes for f in self._frozen.values()))
                for f in list(self._frozen.values()):
                    if used + need <= self.full_budget:
                        break
                    used -= f.full_bytes
                    f.drop_full()
                if used + need > self.full_budget:
                    c.drop_full('memory')
                    skipped = True
            if old is not None and c.start_img is None and old.img is not None:
                c.start_img = old.img.resize(c.size, Image.BILINEAR)   
            if old is not None and old.img is not None and c.stage > old.stage:
                c.img = old.img.resize(c.size, Image.BILINEAR)         
                c.preview = old.preview
                c.paint_seq = old.paint_seq + 1
                prime = c.full is not None and c.src_img is not None and c.preview == 'detailed'
            if old is not None:
                old.drop_full()                                        
            self._live[(jid, iid)] = c
            self.seq += 1
        earlier = old.earlier_jpeg() if old is not None else None
        if earlier:                     
            with self._lock:
                self._purge_gone_locked()
                self._earlier_gone[(jid, iid)] = (earlier, time.monotonic())
        if skipped and self.log is not None:
            self.log.info('live_full_skipped', 'No memory for a full-size live picture of this image; its live picture '
                          'stays at canvas size', job=jid, item=iid, data={'budget_mb': self.full_budget >> 20})
        if prime:
            c.full.lay(c.src_img)       
        return c

    def get(self, jid, iid):
        with self._lock:
            return self._live.get((jid, iid)) or self._frozen.get((jid, iid))

    def live(self, jid, iid):
        with self._lock:
            return self._live.get((jid, iid))

    def set_state(self, jid, iid, state):
        c = self.live(jid, iid)
        if c is not None:
            c.set_state(state)
            with self._lock:
                self.seq += 1

    def at(self, jid, iid):
        c = self.get(jid, iid)
        return c.at if isinstance(c, Frozen) else (c.at() if c is not None else None)

    def freeze(self, jid, iid, state):
        """Keep the last frame (stopped / failed); returns where it stopped ({stage, stages, pass, step, steps}) or None."""
        with self._lock:
            c = self._live.pop((jid, iid), None)
        if c is None:
            f = self._frozen.get((jid, iid))
            return f.at if f is not None else None
        if c.img is None:
            c.drop_full()
            return c.at()
        f = Frozen(c, state)
        with self._lock:
            self._frozen[(jid, iid)] = f
            while len(self._frozen) > KEEP_FROZEN:
                self._frozen.pop(next(iter(self._frozen))).drop_full()
            holders = [x for x in self._frozen.values() if x.full is not None]
            for x in holders[:max(0, len(holders) - FROZEN_FULL_KEEP)]:
                x.drop_full()                      
            self.seq += 1
        if f.full is not None:
            self._arm(f, self.frozen_full_idle_s)
        return f.at

    def _arm(self, f, seconds):
        t = threading.Timer(max(0.05, seconds), self._expire, args=(f,))
        t.daemon = True
        t.start()

    def _expire(self, f):
        """A stopped or failed image gives its full-size picture up once nobody has read a region of it for a while."""
        if f.full is None:
            return
        left = self.frozen_full_idle_s - (f.clock() - f.full_used)
        if left > 0.05:
            return self._arm(f, left)
        f.drop_full()
        with self._lock:
            self.seq += 1

    def region(self, jid, iid, x, y, w, h):
        """preview design: (jpeg, (x, y, w, h), scale, image_seq) from the image's full-size live picture, or None when it has none."""
        c = self.get(jid, iid)
        return None if c is None else c.region(x, y, w, h)

    def drop(self, jid, iid):
        """The image has no live picture any more (done, cancelled, queued again). Its last canvas and miniature JPEGs stay
        servable for GONE_KEEP_S (recent()), never listed by /api/live: a request the tab sent for the seq it had just read
        would otherwise come back 404 (12 Nov, QA Q-12 / integrator I1: CuMiniature's live-thumb.jpg?seq=38 at the end of
        an image, a Qt warning that failed the real-service run of record)."""
        with self._lock:
            a = self._live.pop((jid, iid), None)
            b = self._frozen.pop((jid, iid), None)
            if a is not None or b is not None:
                self.seq += 1
        if a is not None:
            a.drop_full()
        if b is not None:
            b.drop_full()
        last = b if b is not None else a
        if last is not None:
            try:
                kept = Gone(last.jpeg(force=True), last.thumb(), time.monotonic(),
                            last.earlier_jpeg() if hasattr(last, 'earlier_jpeg') else None)
            except Exception as e:   
                kept = None
                if self.log is not None:
                    self.log.exception('live_gone_failed', 'The last live frame could not be kept', e, job=jid, item=iid)
            with self._lock:
                self._purge_gone_locked()
                if kept is not None and (kept.jpg or kept.thumb_jpg):
                    self._gone[(jid, iid)] = kept

    def _purge_gone_locked(self):
        now = time.monotonic()
        for k in [k for k, g in self._gone.items() if now - g.t > GONE_KEEP_S]:
            del self._gone[k]
        for k in [k for k, (_, t) in self._earlier_gone.items() if now - t > GONE_KEEP_S]:
            del self._earlier_gone[k]

    def recent_earlier(self, jid, iid):
        """R-V1: the earlier pass's picture of the image's stage before, kept for GONE_KEEP_S after the next stage began
        (its `earlier_pass` is null again), else None."""
        with self._lock:
            self._purge_gone_locked()
            e = self._earlier_gone.get((jid, iid))
        return e[0] if e is not None else None

    def recent(self, jid, iid):
        """The last frame of an image dropped within GONE_KEEP_S (jpeg() and thumb() only), else None."""
        with self._lock:
            self._purge_gone_locked()
            return self._gone.get((jid, iid))

    def summary(self, extra=None):
        """GET /api/live: {seq, items: [...]} (extra(jid, iid) -> dict merged into each item, e.g. eta_s and elapsed_s)."""
        with self._lock:
            live = list(self._live.values())
            frozen = list(self._frozen.items())
            seq = self.seq
        items = []
        for c in live:
            snap = c.snapshot(f'/api/jobs/{c.jid}/items/{c.iid}')
            seq += c.paint_seq
            items.append(snap)
        for (jid, iid), f in frozen:
            items.append(f.snapshot(f'/api/jobs/{jid}/items/{iid}'))
        if extra is not None:
            for it in items:
                it.update(extra(it['job_id'], it['item_id']) or {})
        return {'seq': seq, 'items': items}
