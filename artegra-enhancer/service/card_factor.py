"""Per-card time factors, so that no smaller card is killed by a deadline built for an RTX 5090 (Artegra Enhancer 5.0.2;
engine design ENGINE-DESIGN.md sections 8.1 and 8.3; build item B14).

card_factor(card) = the card's measured seconds per 1024 x 1024 sampler window over the RTX 5090's, never below 1.0:
- a card of more than 24 GiB (the 32 GB RTX 5090, and larger cards) has factor 1.0 BY RULE, and nothing about its engine
  changes, so it keeps 5.0.1's deadlines to the second and behaves exactly as 5.0.1;
- a card of 24 GiB or less is measured: its engine is started with spot's own timing record on (CLAUDE_SPOT_TIMING; the
  record is written after each sampling pass, which changes no pixel), the service reads the record of every finished
  prompt (main sampler calls, the first step of each pass left out), and keeps the card's seconds per window, per card, in
  <state>/card_factors.json; the factor is that time over REF_S_PER_WINDOW;
- a card never measured before is timed once at engine start, before its first image's prompt (the measurement prompt at
  the end of this module; build wave 2, A4), so its first image already runs at its own factor;
- before a card's first measurement, and when that measurement fails: the class table (engine/vram_model.CARD_CLASSES, by
  name: the larger of the SM-count and memory-bandwidth ratios to the 5090), times 2 for safety; a card not in the table
  takes the slowest listed card of its memory class, times 2.

Applied to every prompt (classic and Large-image): deadline = deadline_override or (3 x minutes x cf + 10) x 60 s; the
stall limit and the time shown are cf times the planner's. The stored plan's minutes never change.

REF_S_PER_WINDOW: the MEDIAN per-window time of 339 sampling passes of the product stack (batch 2, PAG fused, noise
prefetch, fp16 accumulation) on one RTX 5090 in the 2026 proof runs' spot timing records (per pass, the median of the main
calls' seconds per window, step 0 left out; passes 0.091-0.178 s, quartiles 0.098 and 0.154 s). The median, so that a card
as fast as a typical 5090 pass reads 1.0 and the time said on a measured card is not overstated; the deadline keeps its own
margin (3 x the minutes + 10 min)."""
import json
import statistics
import threading
from pathlib import Path

from engine import vram_model

REF_S_PER_WINDOW = 0.147
CLASS_SAFETY = 2.0
TIMING_ENV = 'CLAUDE_SPOT_TIMING'
TIMING_DIR = 'claude_timing'
EWMA_ALPHA = 0.5                    # as spot.record_speed
MAX_FACTOR = 50.0                   # a measurement above this is a broken record, not a card


def deadline_s(minutes, cf=1.0, override=None):
    """Seconds a prompt may take: the override when set (CU_DEADLINE_SECONDS), else (3 x minutes x cf + 10) x 60 with cf
    never below 1.0. At cf 1.0 this is 5.0.1's `(3 * st['minutes'] + 10) * 60` to the bit (x 1.0 is exact)."""
    if override:
        return override
    return (3 * minutes * max(1.0, float(cf)) + 10) * 60


def stall_s(limit_s, cf=1.0):
    """A stall limit for this card: cf times the planner's (never shorter)."""
    cf = max(1.0, float(cf))
    return limit_s if cf == 1.0 else limit_s * cf


def reference_card(card):
    """True for a card that keeps factor 1.0 by rule: more than 24 GiB, or its memory unknown (as 5.0.1)."""
    total = (card or {}).get('mem_total_gb')
    n = vram_model.nominal_gb(total)
    return n is None or n > vram_model.CHECKED_UP_TO_GB


def measures(card):
    """True when this card's engine should write spot's timing record (a card of 24 GiB or less)."""
    return not reference_card(card)


def class_factor(card):
    """The factor of a card before its first measurement: the class table's ratio x CLASS_SAFETY (at least 1.0)."""
    if reference_card(card):
        return 1.0
    row = vram_model.card_class(card.get('name'), card.get('mem_total_gb'))
    ratio = vram_model.class_speed_ratio(row) if row is not None else vram_model.slowest_of_class(card.get('mem_total_gb'))
    return max(1.0, round(ratio * CLASS_SAFETY, 3))


def card_key(card):
    """The key a card's measurement is kept under: its UUID, else its name and memory."""
    card = card or {}
    if card.get('uuid'):
        return str(card['uuid'])
    return f"{card.get('name')}|{vram_model.nominal_gb(card.get('mem_total_gb'))}"


def window_seconds(record):
    """Seconds per window of one spot timing record (a sampling pass on one card), or None: the median over its main
    calls of (end - start) / windows, the first step left out. Records of a pass shared by several cards are not used."""
    if not isinstance(record, dict) or record.get('window_split'):
        return None
    per = []
    for c in record.get('calls') or []:
        try:
            kind, step, n, t0, t1 = c[0], int(c[1]), int(c[2]), float(c[3]), float(c[4])
        except (TypeError, ValueError, IndexError):
            continue
        if kind == 'main' and step >= 1 and n > 0 and t1 > t0:
            per.append((t1 - t0) / n)
    return statistics.median(per) if per else None


def read_records(output_dir, prompt_id, remove=True):
    """The seconds per window of every spot timing record this prompt left in the engine's output folder (the files are
    removed). Never raises."""
    d = Path(output_dir) / TIMING_DIR
    out = []
    try:
        files = sorted(d.glob(f'*_{prompt_id}_pass*_node*.json')) if d.is_dir() else []
    except OSError:
        return out
    for p in files:
        try:
            s = window_seconds(json.loads(p.read_text(encoding='utf8')))
            if s is not None:
                out.append(s)
        except (OSError, ValueError):
            pass
        if remove:
            try:
                p.unlink()
            except OSError:
                pass
    return out


class CardFactors:
    """The measured window time of each card, persisted in a small JSON file (state folder)."""

    def __init__(self, path, log=None):
        self.path = Path(path) if path is not None else None
        self.log = log
        self._lock = threading.Lock()
        self._data = {}
        if self.path is not None:
            try:
                d = json.loads(self.path.read_text(encoding='utf8'))
                if isinstance(d, dict) and isinstance(d.get('cards'), dict):
                    self._data = {k: v for k, v in d['cards'].items() if isinstance(v, dict)}
            except (OSError, ValueError):
                self._data = {}

    def measured(self, card):
        with self._lock:
            rec = self._data.get(card_key(card))
        s = (rec or {}).get('s_per_window')
        return float(s) if isinstance(s, (int, float)) and s > 0 else None

    def factor(self, card):
        """cf of one card (a gpu_list row: name, uuid, mem_total_gb): 1.0 for a card over 24 GiB or of unknown memory;
        else its measured window time over the 5090's, or the class table x 2 before its first measurement."""
        if reference_card(card):
            return 1.0
        s = self.measured(card)
        if s is None:
            return class_factor(card)
        return max(1.0, min(MAX_FACTOR, round(s / REF_S_PER_WINDOW, 3)))

    def source(self, card):
        if reference_card(card):
            return 'reference'
        return 'measured' if self.measured(card) is not None else 'class'

    def record(self, card, seconds_per_window):
        """Fold one measurement into the card's kept time (as spot.record_speed: half the old, half the new) and save."""
        if reference_card(card) or not seconds_per_window or seconds_per_window <= 0:
            return None
        s = float(seconds_per_window)
        if s / REF_S_PER_WINDOW > MAX_FACTOR:
            return None
        from service.util import now_iso
        key = card_key(card)
        with self._lock:
            old = (self._data.get(key) or {}).get('s_per_window')
            new = s if not old else (1 - EWMA_ALPHA) * float(old) + EWMA_ALPHA * s
            self._data[key] = {'s_per_window': round(new, 5), 'name': (card or {}).get('name'),
                               'memory_gb': vram_model.nominal_gb((card or {}).get('mem_total_gb')),
                               'samples': int((self._data.get(key) or {}).get('samples', 0)) + 1, 'updated': now_iso()}
            data = {'version': 1, 'ref_s_per_window': REF_S_PER_WINDOW, 'cards': dict(self._data)}
        self._save(data)
        return new

    def _save(self, data):
        if self.path is None:
            return
        try:
            from service.util import atomic_write_json
            atomic_write_json(self.path, data)
        except OSError as e:
            if self.log is not None:
                self.log.warn('card_factor_save_failed', f'The graphics card timing could not be saved: {e}')

    def info(self, cards):
        """[{gpu, name, factor, source}] for the cards given (gpu_list rows)."""
        return [{'gpu': c.get('index'), 'name': c.get('name'), 'factor': self.factor(c), 'source': self.source(c)}
                for c in cards or []]


def worker_env(env, card):
    """The engine's environment for this card: spot's timing record on for a measured card, as the user's otherwise."""
    if card is not None and measures(card):
        env[TIMING_ENV] = '1'
    return env


def cards_factor(store, cards):
    """The factor of several cards working on one image (the slowest), 1.0 without cards."""
    if store is None:
        return 1.0
    return max([store.factor(c) for c in cards or []] or [1.0])


# --- the start-up measurement (A4; ENGINE-DESIGN 8.1: "measured at engine start with spot's record_speed") -------------
# A card of 24 GiB or less that has never been measured is timed once, right after its engine starts and before its first
# image's prompt, so its first image already runs (and has its time said) at its own factor, not at the class table x 2.
# The measurement is its own small prompt: a synthetic picture (never a person's image) sampled by the product's own
# ClaudeSpotTiles stack (graph_v5t.product_options with the speed stack, the card's memory profile applied, one tile
# ControlNet as in the detail pass), on a canvas of several 1024 px windows so spot's windowed path and its timing record
# run. No classic graph is changed: the image's own prompts are built exactly as before, after it. A card over 24 GiB is
# never measured (factor 1.0 by rule), so nothing about a 32 GB card's engine or prompts changes.
CAL_SIZE = (2048, 1536)                 # 2 x 2 windows of 1024 px and their shifts: never spot's one-window path
CAL_STEPS = 6                           # window_seconds leaves step 0 out: 5 timed steps
CAL_PREFIX = 'cu_cardtime'
CAL_LIMIT_S = 600.0                     # x the card's class factor: the longest the measurement may take
CAL_MESSAGE = "Measuring this graphics card's speed before its first image"


def needs_measuring(store, cards):
    """True when one card of 24 GiB or less runs the engine and has no measurement yet (a shared engine is not measured:
    each card is timed on its own)."""
    return store is not None and len(cards or []) == 1 and measures(cards[0]) and store.measured(cards[0]) is None


def calibration_limit_s(card):
    return CAL_LIMIT_S * class_factor(card)


def calibration_picture(size=CAL_SIZE):
    """A synthetic picture (gradients, hard edges and fine texture) for the measurement; the same every time."""
    import numpy as np
    from PIL import Image
    w, h = size
    y, x = np.mgrid[0:h, 0:w]
    a = np.zeros((h, w, 3), np.uint8)
    a[..., 0] = (x * 255 // max(1, w - 1)).astype(np.uint8)
    a[..., 1] = np.where(((x // 64) + (y // 48)) % 2 == 0, 190, 40).astype(np.uint8)
    a[..., 2] = ((x * 7 + y * 13) % 256).astype(np.uint8)
    return Image.fromarray(a, 'RGB')


def calibration_graph(input_name, prefix, params, profile):
    """(graph, info) of the measurement prompt: the product's sampler stack on the synthetic picture in ComfyUI's input
    folder. params: a stage's parameters (engine/controls.stage_params). profile: the engine's memory profile."""
    from engine import graph_v5t
    from service import memory_policy
    g = graph_v5t.G()
    ck = g.once('CheckpointLoaderSimple', ckpt_name=graph_v5t.MODELS['ckpt'])
    m, clip, vae = ck.out(0), ck.out(1), ck.out(2)
    pag = g.add('PerturbedAttentionGuidance', model=m, scale=params['pag'])
    pos = g.add('CLIPTextEncode', clip=clip, text=params['prompt'])
    neg = g.add('CLIPTextEncode', clip=clip, text=params['negative'])
    canvas = g.add('LoadImage', image=input_name)
    cn_t = g.once('ControlNetLoader', control_net_name=graph_v5t.MODELS['cn_tile'])
    hint = g.add('ImageBlur', image=canvas, blur_radius=2, sigma=1.0)
    c1 = g.add('ControlNetApplyAdvanced', positive=pos, negative=neg, control_net=cn_t, image=hint, strength=params['tile'],
               start_percent=0.0, end_percent=1.0, vae=vae)
    spot = {'clamp_blend': True}
    spot.update(graph_v5t.product_options(speed_stack=True))
    model = g.add('ClaudeSpotTiles', model=pag, tile_px=params['tile_px'], seed=params['seed'], **spot)
    lat = g.add('VAEEncodeTiled', pixels=canvas, vae=vae, **graph_v5t.VAE_TILE)
    ks = g.add('KSampler', model=model, positive=c1.out(0), negative=c1.out(1), latent_image=lat, seed=params['seed'],
               steps=CAL_STEPS, cfg=params['cfg'], sampler_name=params['sampler'], scheduler=params['scheduler'], denoise=1.0)
    out = g.add('VAEDecodeTiled', samples=ks, vae=vae, **graph_v5t.VAE_TILE)
    g.add('SaveImage', images=out, filename_prefix=prefix)
    return memory_policy.apply_graph(g.nodes, {'spot_options': spot, 'sampler': ks.id}, profile)


def rescale_run(run, old_cf, new_cf):
    """A frozen `run` record moved from one card factor to another (its finish-time factor and per-stage factors)."""
    if not isinstance(run, dict) or run.get('factor') is None or old_cf == new_cf:
        return run
    old_cf, new_cf = max(1.0, float(old_cf)), max(1.0, float(new_cf))
    out = dict(run, factor=round(float(run['factor']) / old_cf * new_cf, 3))
    if new_cf == 1.0:
        out.pop('card_factor', None)
    else:
        out['card_factor'] = new_cf
    if isinstance(run.get('stage_factors'), list):
        out['stage_factors'] = [round(float(x) / old_cf * new_cf, 4) for x in run['stage_factors']]
    return out
