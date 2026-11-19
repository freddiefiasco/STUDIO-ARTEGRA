"""The Large-image engine's planner (5.0.2; engine design ENGINE-DESIGN.md sections 2.1, 2.8, 3.1, 6).

The Large-image engine (the Banded Exact Stage engine, BES) takes ONLY plans that 5.0.1's planner refuses on this computer:
engine/planner.py's plan() calls plan_501 first and comes here only when 5.0.1 refuses the image or its estimate is over the
memory cap. Every plan 5.0.1 accepts, lightened for memory or not, stays on the classic engine (section 3.1; `UNLIGHTEN` is
off). The plan is the same stage maths on every computer (STAGE_FACTORS, the padding units, the render multiple of 8; each
stage takes the full supersample: the largest of 2, 1.5 and 1 whose render is at most 150 MP, else 1). Only the executor
differs.

Admission is on the registered upper bound (section 6.1, the sizing of design-2-evidence/plan_final2.py): 1.05 x the upper
peak must be at most the cap less 1 GiB. A row that fits only the expected model waits for the measured refit (`MEASURED_FIT`,
section 6.3). Nothing is admitted above `BANDED_PROVEN_MP` for the machine class: those figures are the largest outputs the
registered GPU proof passed, and they stay 0 (nothing admitted) until the proof sets them. A developer build may set them
for its own runs (service/build_channel.py).

No plan constant is chosen from free VRAM. Band heights and process counts adapt at run time only within the registered sets
(engine/bands.py)."""
from dataclasses import dataclass
from fractions import Fraction

from engine import planner as _P

BES_VERSION = 'bes-1'
BANDED_MAX_SIDE = 32000                 # Gigapixel's own export limit; the longest side of a Large-image output
ONE_WINDOW_PX = 1024                    # ClaudeSpotTiles' window: a render no larger than one window takes spot.py's one-window path

# Machine classes, from the memory cap (settings.default_ram_cap_gb: 59.0 on 64 GB, 122.2 on 128 GB, 45.2 on 48 GB).
# finish band budget (GiB), finish processes; 32 GB PCs and smaller are not served (Max: "Not yet: 32 GB PCs").
MACHINE_CLASSES = {
    'ws128': {'min_cap': 100.0, 'band_gb': 6.0, 'processes': 4, 'label': '128 GB'},
    'pc64': {'min_cap': 52.0, 'band_gb': 3.0, 'processes': 2, 'label': '64 GB'},
    'pc48': {'min_cap': 40.0, 'band_gb': 2.0, 'processes': 1, 'label': '48 GB'},
}
# The largest output (MP) the registered GPU proof passed per machine class. 0 = nothing proven: the engine admits nothing.
BANDED_PROVEN_MP = {'ws128': 0.0, 'pc64': 0.0, 'pc48': 0.0}

# Switches that would move a plan the Classic engine can run onto the Large-image engine (section 3.1): all off in 5.0.2.
UNLIGHTEN = False                       # plans 5.0.1 lightens for memory
MAX_SAID_BES_TAKES_CAPPED = False       # plans a 5.0.1.x SAM cap refuses
OFFER_AFTER_OOM = False                 # "try again with the Large-image engine" after an out-of-memory failure
BOLT_BANDED = False                     # banded Bolt (B16) is not built or proven: Bolt stays classic-only

# Halo variant constants (section 2.11). bxf-1 is 5.0.1's finish (it keeps 5.0.1's edge halos); bxf-1h exists only after
# the halo branch's fix reads "STATUS: DEV-PROVEN" and is ported (eng:halo-port).
FINISH_VARIANTS = ('bxf-1',)
DEFAULT_FINISH = 'bxf-1'
CANVAS = 'lanczos-1'
RECIPE = 'r501'
HALO_FIX = None

MARGIN = 1.05                           # admission: 1.05 x the upper bound
CAP_SPARE_GB = 1.0                      # and 1 GiB to spare (section 6.3)
MEASURED_FIT = None                     # the refit of R2-R4 (section 6.3), when registered: {'x0', 'xr', 'v_bpr', ...}

# The registered memory model (section 6.1), GiB, sizes in MP. G = GiB per (byte per pixel x MP).
G = 1e6 / 2 ** 30
V0, V_R = 13.5, 2.7 * G                 # VRAM charged as commit at the samplers (classic fit)
VS0, VS_BPR = 15.5, 4.0                 # BES sampler state on the card: 15.5 + 4 B/Rpx (D5)
SAM_VRAM0, SAM_BPI = 15.4, 13.0         # resident set + SAM + one kept mask at I
X0, XR_EXP, XR_UP, XRES = 10.0, 0.010, 0.035, 3.3
DAT_BAND_ROWS = 2048 + 512              # big rows of one DAT tile-row band plus the next band's overlap
DAT_BPX = 16                            # acc 12 + wsum 4 per big px of the live band (L2), plus 0.3 GiB of chunk buffers
SAMPLE_BPR, PREFETCH_BPR = 1.0, 0.5     # CPU latents; one prefetched draw
BROWN_UNCAPPED_BPR, BROWN_CAPPED_BPR = 11.25, 2.0
BROWNIAN_CAPPED = False                 # G7 (draws bit-identical with the cache at 8) has not passed: the full cache is counted
DEC_ROWS, DEC_BPX = 1088 + 576 + 2112, 24
LABEL_BPO, PRE_F32_BPI, POOL_PROC_GB = 4, 12, 0.4
FIN_RES_EXP_BPO, FIN_RES_UP_BPO = 8, 20
CTX_GB = 0.5                            # CUDA context of the fresh finish worker (L3r)
SERVICE_GB = 1.2                        # service Job above the workers' (1.0 measured, + alpha rows and the live proxy)

# Time (one RTX 5090), seconds per MP; the plane-I/O budget until R2 fits it; a split stage's worker restart and reload.
T_P0_I, T_SAMPLE_R, T_DECODE_R, T_FINISH_O = 20.5, 9.3, 1.04, 6.5
IO_BUDGET = 1.10
SPLIT_MINUTES = 5.0

# Disk: live planes per stage (bytes per I, R and O pixel; section 2.3)
DISK_I, DISK_R, DISK_O = 24, 22, 84


@dataclass
class BandedStage(_P.Stage):
    """A stage of a Large-image plan: the classic Stage fields (same meaning) plus its memory and split constants."""
    split_finish: bool = False
    peak_expected_gb: float = 0.0
    peak_upper_gb: float = 0.0
    binding_phase: str = ''
    vram_gb: float = 0.0
    disk_gb: float = 0.0


def machine_class(cap):
    """The machine class of a memory cap, or None (no cap, or too small for the Large-image engine)."""
    if cap is None:
        return None
    for name, mc in MACHINE_CLASSES.items():
        if float(cap) >= mc['min_cap']:
            return name
    return None


def _mp(size):
    return size[0] * size[1] / 1e6


def stage_choice(cur, f, index):
    """The full-supersample stage for input `cur` and stage factor f: the largest of 2, 1.5 and 1 whose render is at most
    150 MP (planner.RENDER_CAP_MP), else 1. No 16,384 px side limit (the Large-image graph has no ImageScale)."""
    f = Fraction(f)
    for s in _P.SUPERSAMPLES:
        unit = _P._pad_unit(f, s)
        pw, ph = _P._pad_to(cur[0], unit), _P._pad_to(cur[1], unit)
        rw, rh = int(pw * f * s), int(ph * f * s)
        if rw * rh / 1e6 <= _P.RENDER_CAP_MP or s == 1:
            ow, oh = int(cur[0] * f), int(cur[1] * f)
            return dict(index=index, factor=float(f), supersample=float(s), input_size=tuple(cur), padded_size=(pw, ph),
                        render_size=(rw, rh), output_size=(ow, oh))
    raise AssertionError('supersample 1 always fits')


def stage_peaks(st, mclass, split, brownian_capped=None):
    """Peak service-Job commit of one Large-image stage, GiB: {'exp': (gib, phase), 'up': (gib, phase), 'phases_up': {...}}.
    st: a stage dict or Stage (padded_size, render_size, output_size). split: the finish runs in a fresh worker (L3r)."""
    get = (lambda k: st[k]) if isinstance(st, dict) else (lambda k: getattr(st, k))
    capped = BROWNIAN_CAPPED if brownian_capped is None else brownian_capped
    mc = MACHINE_CLASSES[mclass]
    I, R, O = _mp(get('padded_size')), _mp(get('render_size')), _mp(get('output_size'))
    big_w = 4 * get('padded_size')[0]
    fit = MEASURED_FIT or {}
    v_s = max(V0 + V_R * R, VS0 + fit.get('v_bpr', VS_BPR) * G * R)
    v_p0 = max(v_s, SAM_VRAM0 + SAM_BPI * G * I)
    p0 = DAT_BPX * DAT_BAND_ROWS * big_w / 2 ** 30 + 0.3
    brown = (BROWN_CAPPED_BPR if capped else BROWN_UNCAPPED_BPR) + PREFETCH_BPR
    dec = DEC_ROWS * get('render_size')[0] * DEC_BPX / 2 ** 30 + 0.5
    fin_common = mc['band_gb'] + POOL_PROC_GB * (mc['processes'] - 1) + (LABEL_BPO * O + PRE_F32_BPI * I) * G
    v_fin = CTX_GB if split else v_s
    out = {}
    for case, xr in (('exp', XR_EXP), ('up', fit.get('xr', XR_UP))):
        X = fit.get('x0', X0) + xr * R + XRES
        smp = (SAMPLE_BPR + (brown if case == 'exp' else PREFETCH_BPR)) * G * R
        fin = fin_common + (FIN_RES_EXP_BPO if case == 'exp' else FIN_RES_UP_BPO) * G * O
        phases = {'P0': v_p0 + X + p0, 'sampling': v_s + X + smp, 'decode': v_s + X + dec, 'finish': v_fin + X + fin}
        ph = max(phases, key=phases.get)
        out[case] = (phases[ph] + SERVICE_GB, ph)
        if case == 'up':
            out['phases_up'] = {k: v + SERVICE_GB for k, v in phases.items()}
    return out


def split_needed(st, mclass, cap):
    """L3r per stage (section 2.8): on the 128 GB workstation, every stage whose upper bound the finish phase binds (so a
    second image fits beside it); on a 64 GB or 48 GB PC, a stage whose 1.05 x upper bound without the split is over the cap
    less 1 GiB."""
    up = stage_peaks(st, mclass, False)['up']
    if mclass == 'ws128':
        return up[1] == 'finish'
    return MARGIN * up[0] > float(cap) - CAP_SPARE_GB


def banded_vram_gb(st):
    get = (lambda k: st[k]) if isinstance(st, dict) else (lambda k: getattr(st, k))
    I, R = _mp(get('padded_size')), _mp(get('render_size'))
    return max(VS0 + VS_BPR * G * R, SAM_VRAM0 + SAM_BPI * G * I)


def banded_minutes(st, split):
    """One stage on one RTX 5090, minutes: the measured rates of the classic phases, plus the plane-I/O budget, plus a worker
    restart and model load when the finish is split. An estimate until R2 fits the plane-I/O term."""
    get = (lambda k: st[k]) if isinstance(st, dict) else (lambda k: getattr(st, k))
    I, R, O = _mp(get('padded_size')), _mp(get('render_size')), _mp(get('output_size'))
    secs = T_P0_I * I + (T_SAMPLE_R + T_DECODE_R) * R + T_FINISH_O * O
    return secs / 60.0 * IO_BUDGET + (SPLIT_MINUTES if split else 0.0)


def banded_disk_gb(st):
    get = (lambda k: st[k]) if isinstance(st, dict) else (lambda k: getattr(st, k))
    I, R, O = _mp(get('padded_size')), _mp(get('render_size')), _mp(get('output_size'))
    return (DISK_I * I + DISK_R * R + DISK_O * O) / 1e3


def constants(mode='redux', finish=None):
    """The plan's pixel-relevant constants, stored on the plan for resumes (section 2.1)."""
    finish = finish or DEFAULT_FINISH
    if finish not in FINISH_VARIANTS:
        raise ValueError(f'unknown finish variant {finish!r}')
    return {'bes': BES_VERSION, 'hint_store': 'host', 'finish': finish, 'canvas': CANVAS, 'recipe': RECIPE,
            'halo_fix': HALO_FIX, 'mode': mode, 'window': 1024, 'dat': [512, 64, 16], 'vae': [1024, 64], 'canny': [2048, 8],
            'encode_state': 'resident', 'brownian_cache': 8 if BROWNIAN_CAPPED else 45, 'cmap': 'mapped',
            'machine_class': None, 'forced': False}


def _banded_stages(raw, mclass, cap):
    out = []
    for st in raw:
        split = split_needed(st, mclass, cap)
        pk = stage_peaks(st, mclass, split)
        out.append(BandedStage(st['index'], st['factor'], st['supersample'], st['input_size'], st['padded_size'],
                               st['render_size'], st['output_size'], round(_mp(st['render_size']), 1),
                               round(banded_minutes(st, split), 1), split_finish=split,
                               peak_expected_gb=round(pk['exp'][0], 1), peak_upper_gb=round(pk['up'][0], 1),
                               binding_phase=pk['up'][1], vram_gb=round(banded_vram_gb(st), 1),
                               disk_gb=round(banded_disk_gb(st), 1)))
    return out


def _refuse(w0, h0, factor, out, reason):
    return _P.Plan(False, factor, (w0, h0), out, reason=reason, engine='banded')


def plan_banded(width, height, factor, cap, classic=None, mode='redux', proven=None):
    """The Large-image plan for an image 5.0.1 refuses on this computer, or a refusal (ok False) with the reason. The
    caller (planner.plan) gives 5.0.1's own answer when this refuses. proven: BANDED_PROVEN_MP (tests and developer builds
    pass their own)."""
    w0, h0 = int(width), int(height)
    proven = BANDED_PROVEN_MP if proven is None else proven
    if factor not in _P.STAGE_FACTORS:
        return _refuse(w0, h0, factor, (0, 0), 'Choose an upscale of 2×, 4×, 6× or 8×.')
    out = (w0 * factor, h0 * factor)
    if classic is not None and classic.ok and classic.ram_limited and not UNLIGHTEN:
        pass                    # a lightened plan that fits is classic; one that does not fit is still 5.0.1's to refuse
    if mode != 'redux' and not BOLT_BANDED:
        return _refuse(w0, h0, factor, out, 'Bolt is not available for the Large-image engine in this version.')
    if min(w0, h0) < _P.MIN_SIDE or w0 * h0 / 1e6 > _P.MAX_INPUT_MP:
        return _refuse(w0, h0, factor, out, classic.reason if classic is not None else 'This image is outside the supported sizes.')
    if max(out) > BANDED_MAX_SIDE:
        return _refuse(w0, h0, factor, out, f'{factor}× would make {out[0]:,} × {out[1]:,} px, over the {BANDED_MAX_SIDE:,} px '
                                            'limit for the longest side.')
    mclass = machine_class(cap)
    if mclass is None:
        return _refuse(w0, h0, factor, out, 'The Large-image engine needs a computer with at least 48 GB of memory.')
    if out[0] * out[1] / 1e6 > float(proven.get(mclass, 0.0)):
        return _refuse(w0, h0, factor, out, f'The Large-image engine is not yet proven for a {out[0] * out[1] / 1e6:.0f} MP '
                                            f'result on a {MACHINE_CLASSES[mclass]["label"]} computer.')
    raw, cur = [], (w0, h0)
    for i, f in enumerate(_P.STAGE_FACTORS[factor]):
        st = stage_choice(cur, f, i)
        if st['render_size'][0] <= ONE_WINDOW_PX and st['render_size'][1] <= ONE_WINDOW_PX:
            return _refuse(w0, h0, factor, out, 'This image is too small for the Large-image engine.')
        raw.append(st)
        cur = st['output_size']
    stages = _banded_stages(raw, mclass, cap)
    upper = max(s.peak_upper_gb for s in stages)
    admit = MARGIN * upper
    if admit > float(cap) - CAP_SPARE_GB:
        return _refuse(w0, h0, factor, out, f'This image needs about {admit:.0f} GB of memory with the Large-image engine, '
                                            f'more than the {float(cap):.0f} GB it may use on this computer.')
    c = constants(mode)
    c['machine_class'] = mclass
    return _P.Plan(True, factor, (w0, h0), cur, stages, round(sum(s.minutes for s in stages), 1), round(admit, 1),
                   engine='banded', banded=c)


def plan_forced(classic, cap):
    """DEVELOPER BUILDS ONLY (section 3, G0g): the classic plan's own stages (factors, supersamples, sizes) with the
    Large-image executor, for the 1:1 comparison with the Classic engine on the same plan. The caller checks the build
    channel. Refuses (ok False) when the classic plan is not ok or the forced plan would not fit the cap."""
    if not classic.ok:
        return classic
    mclass = machine_class(cap)
    if mclass is None:
        return _refuse(classic.input_size[0], classic.input_size[1], classic.factor, classic.output_size,
                       'The Large-image engine needs a computer with at least 48 GB of memory.')
    raw = [dict(index=s.index, factor=s.factor, supersample=s.supersample, input_size=tuple(s.input_size),
                padded_size=tuple(s.padded_size), render_size=tuple(s.render_size), output_size=tuple(s.output_size))
           for s in classic.stages]
    for st in raw:
        if st['render_size'][0] <= ONE_WINDOW_PX and st['render_size'][1] <= ONE_WINDOW_PX:
            return _refuse(classic.input_size[0], classic.input_size[1], classic.factor, classic.output_size,
                           'This image is too small for the Large-image engine.')
    stages = _banded_stages(raw, mclass, cap)
    admit = MARGIN * max(s.peak_upper_gb for s in stages)
    if admit > float(cap) - CAP_SPARE_GB:
        return _refuse(classic.input_size[0], classic.input_size[1], classic.factor, classic.output_size,
                       f'The forced Large-image plan needs about {admit:.0f} GB, over the cap.')
    c = constants('redux')
    c.update(machine_class=mclass, forced=True)
    return _P.Plan(True, classic.factor, tuple(classic.input_size), tuple(classic.output_size), stages,
                   round(sum(s.minutes for s in stages), 1), round(admit, 1), engine='banded', banded=c)


def is_banded(plan):
    """True for a Large-image plan (a Plan or its stored dict); a dict without `engine` is classic (5.0.1's records)."""
    eng = plan.get('engine') if isinstance(plan, dict) else getattr(plan, 'engine', 'classic')
    return eng == 'banded'
