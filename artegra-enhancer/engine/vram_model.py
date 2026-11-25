"""Graphics-memory model of a stage, and the graphics-card classes (Artegra Enhancer 5.0.2; engine design ENGINE-DESIGN.md
sections 6.4, 8.1 and 8.3; build item B14). Sizes only: nothing here changes a plan, a graph or a pixel.

The CLASSIC pre-check (8.3). 5.0.1 starts every plan it accepts and lets the stock SAM step (400 B per input pixel), the
whole-canvas ImageBlur (36 B per render pixel) or the full-canvas ControlNet hints fail or spill into shared GPU memory hours
in. classic_vram_gb(stage, profile) is the largest of the stage's graphics-memory moments:
- the SAM moment: the resident set at that moment + 400 B/Ipx (all 200 query masks upsampled to the pass input, stock
  SAM3_Detect) + 11 B/Ipx per kept object (the refine; max_detections 1, one SAM node at a time), or 13 B/Ipx where the lean
  SAM node runs (an input above planner.SAM_STOCK_MAX_MP, or on a checked card one whose stock moment does not fit it);
- the x4 model: the whole `pre` on the card (12 B/Ipx) + one DAT tile (ComfyUI's own reservation for the tile);
- the blur: the whole canvas, input + reflect pad + output (36 B/Rpx);
- the samplers: the resident share + the full-canvas hints (6 B/Rpx per ControlNet, two at the structure pass) + the latent
  state (4 B/Rpx) + one window batch.
The service (service/runner.py) compares it with the card's total less the desktop share and 1 GiB, for cards of 24 GiB or
less only. A card over 24 GiB is never checked: it behaves as 5.0.1.

Small cards (the product owner, 26 Nov 2026: "it needs to facilitate more and more nvidia cards, not less"). 5.0.1 refuses no plan for
graphics memory: a step that does not fit the card spills into shared memory. So on a checked card:
- the SAM step follows the card (card_sam_lean): a pass whose stock SAM moment is over the card's usable memory takes the
  lean SAM node, whatever its size (above planner.SAM_STOCK_MAX_MP every card takes it, as before);
- a plan that still does not fit is admitted, as 5.0.1 admits it, with a note that it may use shared memory and take longer
  than the time shown.
Nothing here refuses a Classic plan. A card over 24 GiB, or one whose memory is not known, keeps planner.sam_lean exactly.

The LARGE-IMAGE class admission (8.1): the latent state at most a quarter of the card (render limits of 537, 805, 1,074 and
1,611 MP on 8, 12, 16 and 24 GB cards), banded_vram_gb at 4 B/Rpx, cards under 8 GB refused, and the 8 GB class refused for
Large-image plans until the 8 GB emulation (R5) passes. A card takes the limit of the largest class at or below its memory
among those R5 is registered to emulate and the RTX 5090's (banded_class_gb): 10 and 11 GB cards are in the 8 GB class.

Measured figures carry their source; the Balanced profile's resident shares are PROVISIONAL until R5 measures them
(ENGINE-DESIGN.md 8.1: "Balanced's resident share from R5")."""
GIB = float(1 << 30)
G = 1e6 / GIB                       # GiB per (byte per pixel x MP)

# --- the classic model -------------------------------------------------------------------------------------------------
SAM_STOCK_BPI = 400.0               # all 200 query masks upsampled to the pass input (fp16), ENGINE-FACTS 2.3
SAM_KEPT_BPI = 11.0                 # the refine of one kept object, ENGINE-FACTS 2.3
SAM_KEPT_OBJECTS = 1                # max_detections 1; one SAM node runs at a time
SAM_LEAN_BPI = 13.0                 # the lean node: only the kept mask at the pass input (eng:sam-501)
PRE_BPI = 12.0                      # the whole `pre` (float32 RGB) on the card for the x4 model
DAT_TILE_GB = (512 * 512 * 3) * 4 * 4 * 384.0 / GIB      # ClaudeUpscaleModelTiled's own reservation for one 512 px tile
BLUR_BPR = 36.0                     # ImageBlur: input 12 + reflect-padded 12 + conv output 12
HINT_BPR = 6.0                      # one ControlNet's full-canvas hint (fp16 RGB) on the card
HINTS_AT_KS2 = 2                    # the structure pass runs with the tile and line ControlNets
LATENT_BPR = 4.0                    # the sampler state on the card (ENGINE-DESIGN 6.1, D5)
WINDOW_GB = 0.75                    # one 1024 px window of a batch: the reference P3 plateau above the fit (17.3 at R 157 MP)

# Resident shares (GiB) by memory profile: at the SAM moment, at the x4 model and blur, and at the samplers.
#   reference: S0b's SAM-step intercept (13.823 GiB, a warm worker with the SDXL set loaded) and the classic sampler fit
#              (13.5 GiB; engine/banded_plan.V0); the x4 model and the blur run with the same set resident.
#   balanced (--lowvram, every card of 24 GiB or less under Auto): the weights stream; what stays is the CUDA context and
#              the model of the moment. PROVISIONAL until R5 measures it: the SAM set loaded completely (SAM3.1 990 MB + its
#              CLIP 675 MB, ENGINE-FACTS 2.3) + a 0.5 GiB context; 2.0 GiB at the samplers.
RESIDENT_GB = {
    'reference': {'sam': 13.823, 'x4': 13.823, 'blur': 13.823, 'samplers': 13.5},
    'balanced': {'sam': 0.5 + 1665e6 / GIB, 'x4': 0.5 + 43e6 / GIB, 'blur': 0.5, 'samplers': 2.0},
}
BALANCED_MEASURED = False           # R5 replaces the balanced shares with measured ones

CHECKED_UP_TO_GB = 24.0             # the pre-check applies to cards of 24 GiB or less (Max: "Safer 8-24 GB")
DESKTOP_SHARE_GB = 1.5              # other processes on the card (RAM-MEASURE.md: 1.2, 2.2 and 3.4 GiB on the test machines;
                                    # the desktop of a one-card PC); PROVISIONAL until R5 records small-card desktops
SPARE_GB = 1.0                      # and 1 GiB to spare (8.1, 8.3)

# --- the Large-image class admission -----------------------------------------------------------------------------------
LATENT_SHARE = 0.25                 # the latent state at most a quarter of the card (8.1)
BANDED_MIN_CARD_GB = 8              # cards under 8 GB are refused
EIGHT_GB_PROVEN = False             # R5's 8 GB emulation has not passed: the 8 GB class is refused for Large-image plans
# The card classes R5 is registered to emulate (8.1: 8 GB, admitted only once its emulation passes, 12, 16 and 24 GB), plus
# the RTX 5090's own 32 GB. R5 has not run yet. A card is in the largest class at or below its memory and takes that class's
# render limit, so no card is admitted beyond a class R5 or the 5090 is to prove: a 10 or 11 GB card is in the 8 GB class
# (refused until EIGHT_GB_PROVEN, then 537 MP).
BANDED_CLASSES_GB = (8, 12, 16, 24, 32)
BANDED_RESIDENT_GB = {'reference': {'sam': 15.4, 'samplers': 15.5},          # engine/banded_plan SAM_VRAM0, VS0
                      'balanced': {'sam': 0.5 + 1665e6 / GIB, 'samplers': 2.0}}  # PROVISIONAL, as above
BANDED_SAM_BPI = 13.0

NOMINAL_GB = (2, 3, 4, 6, 8, 10, 11, 12, 16, 20, 24, 32, 48, 80, 96, 141)

# The class table for a card's time factor before its first measurement (service/card_factor.py): SM count and memory
# bandwidth (GB/s) per card name. ESTIMATES: the makers' published figures as recalled for this build, not re-measured
# (laptop parts vary with their power limit); the factor taken from them is doubled for safety, and a card's own measured
# window time replaces it after its first image. tests/fixtures/card_classes_5_0_2.json registers this table.
CARD_CLASSES = {
    'reference': {'name': 'RTX 5090', 'sm': 170, 'bandwidth_gbs': 1792, 'memory_gb': 32},
    'source': 'published specifications (estimates, not measured in this build); laptop figures vary with the power limit',
    'cards': [
        {'name': 'RTX 5090', 'sm': 170, 'bandwidth_gbs': 1792, 'memory_gb': 32},
        {'name': 'RTX 5080', 'sm': 84, 'bandwidth_gbs': 960, 'memory_gb': 16},
        {'name': 'RTX 5070 Ti', 'sm': 70, 'bandwidth_gbs': 896, 'memory_gb': 16},
        {'name': 'RTX 5070', 'sm': 48, 'bandwidth_gbs': 672, 'memory_gb': 12},
        {'name': 'RTX 5060 Ti', 'sm': 36, 'bandwidth_gbs': 448, 'memory_gb': 16},
        {'name': 'RTX 5060 Ti', 'sm': 36, 'bandwidth_gbs': 448, 'memory_gb': 8},
        {'name': 'RTX 5060', 'sm': 30, 'bandwidth_gbs': 448, 'memory_gb': 8},
        {'name': 'RTX 4090', 'sm': 128, 'bandwidth_gbs': 1008, 'memory_gb': 24},
        {'name': 'RTX 4080 SUPER', 'sm': 80, 'bandwidth_gbs': 736, 'memory_gb': 16},
        {'name': 'RTX 4080', 'sm': 76, 'bandwidth_gbs': 717, 'memory_gb': 16},
        {'name': 'RTX 4070 Ti SUPER', 'sm': 66, 'bandwidth_gbs': 672, 'memory_gb': 16},
        {'name': 'RTX 4070 Ti', 'sm': 60, 'bandwidth_gbs': 504, 'memory_gb': 12},
        {'name': 'RTX 4070 SUPER', 'sm': 56, 'bandwidth_gbs': 504, 'memory_gb': 12},
        {'name': 'RTX 4070', 'sm': 46, 'bandwidth_gbs': 504, 'memory_gb': 12},
        {'name': 'RTX 4060 Ti', 'sm': 34, 'bandwidth_gbs': 288, 'memory_gb': 16},
        {'name': 'RTX 4060 Ti', 'sm': 34, 'bandwidth_gbs': 288, 'memory_gb': 8},
        {'name': 'RTX 4060', 'sm': 24, 'bandwidth_gbs': 272, 'memory_gb': 8},
        {'name': 'RTX 3090 Ti', 'sm': 84, 'bandwidth_gbs': 1008, 'memory_gb': 24},
        {'name': 'RTX 3090', 'sm': 82, 'bandwidth_gbs': 936, 'memory_gb': 24},
        {'name': 'RTX 3080 Ti', 'sm': 80, 'bandwidth_gbs': 912, 'memory_gb': 12},
        {'name': 'RTX 3080', 'sm': 70, 'bandwidth_gbs': 912, 'memory_gb': 12},
        {'name': 'RTX 3080', 'sm': 68, 'bandwidth_gbs': 760, 'memory_gb': 10},
        {'name': 'RTX 3070 Ti', 'sm': 48, 'bandwidth_gbs': 608, 'memory_gb': 8},
        {'name': 'RTX 3070', 'sm': 46, 'bandwidth_gbs': 448, 'memory_gb': 8},
        {'name': 'RTX 3060 Ti', 'sm': 38, 'bandwidth_gbs': 448, 'memory_gb': 8},
        {'name': 'RTX 3060', 'sm': 28, 'bandwidth_gbs': 360, 'memory_gb': 12},
        {'name': 'RTX 2080 Ti', 'sm': 68, 'bandwidth_gbs': 616, 'memory_gb': 11},
        {'name': 'RTX 2080 SUPER', 'sm': 48, 'bandwidth_gbs': 496, 'memory_gb': 8},
        {'name': 'RTX 2080', 'sm': 46, 'bandwidth_gbs': 448, 'memory_gb': 8},
        {'name': 'RTX 2070 SUPER', 'sm': 40, 'bandwidth_gbs': 448, 'memory_gb': 8},
        {'name': 'RTX 2070', 'sm': 36, 'bandwidth_gbs': 448, 'memory_gb': 8},
        {'name': 'RTX 2060 SUPER', 'sm': 34, 'bandwidth_gbs': 448, 'memory_gb': 8},
        {'name': 'RTX 5090 Laptop GPU', 'sm': 82, 'bandwidth_gbs': 896, 'memory_gb': 24},
        {'name': 'RTX 4090 Laptop GPU', 'sm': 76, 'bandwidth_gbs': 576, 'memory_gb': 16},
        {'name': 'RTX 4080 Laptop GPU', 'sm': 58, 'bandwidth_gbs': 432, 'memory_gb': 12},
        {'name': 'RTX 4070 Laptop GPU', 'sm': 36, 'bandwidth_gbs': 256, 'memory_gb': 8},
        {'name': 'RTX 3080 Ti Laptop GPU', 'sm': 58, 'bandwidth_gbs': 512, 'memory_gb': 16},
        {'name': 'RTX PRO 6000 Blackwell Workstation Edition', 'sm': 188, 'bandwidth_gbs': 1792, 'memory_gb': 96},
        {'name': 'RTX 6000 Ada Generation', 'sm': 142, 'bandwidth_gbs': 960, 'memory_gb': 48},
        {'name': 'RTX A6000', 'sm': 84, 'bandwidth_gbs': 768, 'memory_gb': 48},
        {'name': 'RTX A5000', 'sm': 64, 'bandwidth_gbs': 768, 'memory_gb': 24},
        {'name': 'RTX A4000', 'sm': 48, 'bandwidth_gbs': 448, 'memory_gb': 16},
    ],
}


def _get(st, k):
    return st[k] if isinstance(st, dict) else getattr(st, k)


def _mp(size):
    return size[0] * size[1] / 1e6


def nominal_gb(total_gb):
    """The card's nominal memory (8, 12, 16, 24, 32 GB ...) from the total nvidia-smi reports in GiB (a 24 GB card reports
    about 23.99, an RTX 5090 about 31.84). None when the total is unknown."""
    try:
        t = float(total_gb)
    except (TypeError, ValueError):
        return None
    if not t > 0:
        return None
    for n in NOMINAL_GB:
        if n >= t - 0.5:
            return n
    return int(round(t))


def checked(total_gb):
    """True when the classic pre-check applies to a card of this total (24 GiB or less, total known)."""
    n = nominal_gb(total_gb)
    return n is not None and n <= CHECKED_UP_TO_GB


def usable_gb(total_gb):
    """The card's total less the desktop share and 1 GiB."""
    return float(total_gb) - DESKTOP_SHARE_GB - SPARE_GB


def _profile(profile):
    name = getattr(profile, 'name', profile) or 'reference'
    if name not in RESIDENT_GB:
        raise ValueError(f'unknown memory profile {name!r}')
    return name


def _batch(profile):
    b = getattr(profile, 'batch_windows', None)
    if b is None:
        b = 1 if _profile(profile) == 'balanced' else 2
    return int(b)


def stock_sam_gb(width, height, profile='reference'):
    """The stock SAM3_Detect moment (GiB) of a SAM input of width x height px: the resident set + 411 B/Ipx."""
    return (RESIDENT_GB[_profile(profile)]['sam']
            + (SAM_STOCK_BPI + SAM_KEPT_BPI * SAM_KEPT_OBJECTS) * G * _mp((int(width), int(height))))


def card_sam_lean(width, height, total_gb=None, profile='reference'):
    """True when the lean SAM node runs for a SAM input of width x height px (a stage's padded input, or a protected-area
    preview's source) on a card of `total_gb` (nvidia-smi GiB) under `profile`: above planner.SAM_STOCK_MAX_MP on every card
    (planner.sam_lean), and on a checked card (24 GiB or less) also wherever the stock SAM moment is over the card's usable
    memory. The lean node gives SAM3_Detect's own masks (node_pack/claude_creative/sam_lean.py). A card over 24 GiB, or one
    whose memory is unknown (None), keeps planner.sam_lean exactly."""
    from engine import planner
    if planner.sam_lean(width, height):
        return True
    if not checked(total_gb):
        return False
    return stock_sam_gb(width, height, profile) > usable_gb(total_gb)


def classic_moments(stage, profile='reference', protect=True, lean=None, total_gb=None):
    """{moment: GiB} of one classic stage (see the module docstring). stage: a planner Stage or its dict. protect: the
    stage runs the SAM step (protected areas on). lean: the lean SAM node runs (None: card_sam_lean of the padded input on
    a card of `total_gb`; with total_gb None, planner.sam_lean)."""
    name = _profile(profile)
    res = RESIDENT_GB[name]
    pw, ph = _get(stage, 'padded_size')
    I, R = _mp((pw, ph)), _mp(_get(stage, 'render_size'))
    if lean is None:
        lean = card_sam_lean(pw, ph, total_gb, profile)
    out = {'x4': res['x4'] + PRE_BPI * G * I + DAT_TILE_GB,
           'blur': res['blur'] + BLUR_BPR * G * R,
           'samplers': (res['samplers'] + (HINT_BPR * HINTS_AT_KS2 + LATENT_BPR) * G * R
                        + WINDOW_GB * _batch(profile))}
    if protect:
        per = SAM_LEAN_BPI if lean else SAM_STOCK_BPI + SAM_KEPT_BPI * SAM_KEPT_OBJECTS
        out['sam'] = res['sam'] + per * G * I
    return out


def classic_vram_gb(stage, profile='reference', protect=True, lean=None, total_gb=None):
    """The graphics memory one classic stage needs, GiB: the largest of its moments (classic_moments)."""
    return max(classic_moments(stage, profile, protect, lean, total_gb).values())


def classic_plan_vram_gb(plan, profile='reference', protect=True, total_gb=None):
    """(GiB, stage index, moment) of the classic plan's largest stage moment. plan: a planner Plan or its dict. total_gb: the
    card it runs on, whose SAM choice each stage takes (card_sam_lean; None: planner.sam_lean)."""
    best = (0.0, None, None)
    for st in _get(plan, 'stages') or []:
        m = classic_moments(st, profile, protect, total_gb=total_gb)
        k = max(m, key=m.get)
        if m[k] > best[0]:
            best = (m[k], _get(st, 'index'), k)
    return best


# --- Large-image ---------------------------------------------------------------------------------------------------------
def banded_class_gb(nominal):
    """The Large-image class (GB) of a card of `nominal` GB (nominal_gb): the largest of BANDED_CLASSES_GB at or below it
    (10 and 11 GB cards are in the 8 GB class, a 20 GB card in the 16 GB class, a 48 GB card in the 32 GB class); None for a
    card under 8 GB or of unknown memory."""
    if nominal is None:
        return None
    got = [c for c in BANDED_CLASSES_GB if c <= float(nominal)]
    return max(got) if got else None


def render_limit_mp(card_gb):
    """The largest render (MP) whose latent state (4 B/Rpx) is at most a quarter of a card of `card_gb` nominal GB."""
    return int(round(card_gb * GIB * LATENT_SHARE / LATENT_BPR / 1e6))


def banded_vram_gb(stage, profile='reference'):
    """The graphics memory one Large-image stage needs, GiB: the larger of the SAM moment (resident + one kept mask at
    13 B/Ipx) and the samplers (resident + 4 B/Rpx + one window batch on small-card profiles)."""
    name = _profile(profile)
    res = BANDED_RESIDENT_GB[name]
    I, R = _mp(_get(stage, 'padded_size')), _mp(_get(stage, 'render_size'))
    batch = WINDOW_GB * _batch(profile) if name != 'reference' else 0.0     # the reference figure carries it (6.4)
    return max(res['sam'] + BANDED_SAM_BPI * G * I, res['samplers'] + LATENT_BPR * G * R + batch)


# --- card classes --------------------------------------------------------------------------------------------------------
def _norm(name):
    n = ' '.join(str(name or '').replace('NVIDIA', ' ').replace('GeForce', ' ').split())
    return n.lower()


def card_class(name, total_gb=None, table=None):
    """The class-table row of a card (by name; between variants of one name, the closest memory), or None."""
    rows = (table or CARD_CLASSES)['cards']
    key = _norm(name)
    hits = [r for r in rows if _norm(r['name']) == key]
    if not hits:
        return None
    if total_gb is None or len(hits) == 1:
        return hits[0]
    n = nominal_gb(total_gb) or 0
    return min(hits, key=lambda r: abs(r['memory_gb'] - n))


def class_speed_ratio(row, table=None):
    """How many times slower than the reference card a class row is, from its SM count and memory bandwidth (the larger
    of the two ratios; at least 1)."""
    ref = (table or CARD_CLASSES)['reference']
    return max(1.0, ref['sm'] / float(row['sm']), ref['bandwidth_gbs'] / float(row['bandwidth_gbs']))


def slowest_of_class(total_gb, table=None):
    """The speed ratio of the slowest listed card of this card's nominal memory (an unknown card), or of the slowest card
    of all when none of that memory is listed."""
    t = table or CARD_CLASSES
    n = nominal_gb(total_gb)
    rows = [r for r in t['cards'] if r['memory_gb'] == n] or t['cards']
    return max(class_speed_ratio(r, t) for r in rows)
