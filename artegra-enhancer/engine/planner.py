"""Planner implementation."""


from dataclasses import dataclass, field, asdict
from fractions import Fraction
import math

STAGE_FACTORS = {2: [2], 4: [2, 2], 6: [2, 2, Fraction(3, 2)], 8: [2, 2, 2]}
SUPERSAMPLES = [2, Fraction(3, 2), 1]
RENDER_CAP_MP = 150.0
STAGE_OUTPUT_CAP_MP = 150.0
MIN_SIDE = 64
MAX_INPUT_MP = 80.0


MAX_SIDE = 16384


# Peak memory of one stage, in GiB of committed memory, from the stage's render, output and input megapixels. The
# constants are the smallest upper envelope of the peaks measured on RTX 5090 PCs (19 Nov 2026: Redux and Bolt, 2x to
# 8x, renders of 67 to 157 MP, outputs up to 131 MP, inputs up to 32.8 MP; Bolt peaks 5-7 GiB above Redux at the same
# size, so the envelope follows Bolt), times PEAK_MARGIN. The peaks are those of a Windows Job around the service and
# the engine together, about 1 GiB above what the app's Job limit counts (the engine's processes only). It is an
# upper bound for those runs: one card, the original memory settings. Until 5.0.1 the model was 30 + 0.15 x render
# MP + 0.43 x output MP, 15-35 % above the measured peaks, which refused images a 64 GB PC renders.
PEAK_BASE_GB = 22.69
PEAK_PER_RENDER_MP = 0.1463
PEAK_PER_OUTPUT_MP = 0.2687
PEAK_PER_INPUT_MP = 0.3078
PEAK_MARGIN = 1.03


def stage_peak_gb(render_mp, output_mp, input_mp):
    """Upper bound of one stage's peak committed memory in GiB."""
    return PEAK_MARGIN * (PEAK_BASE_GB + PEAK_PER_RENDER_MP * float(render_mp) + PEAK_PER_OUTPUT_MP * float(output_mp)
                          + PEAK_PER_INPUT_MP * float(input_mp))


def stage_peak(stage):
    """stage_peak_gb of a Stage: its rounded render MP (as stored), its output and its padded input."""
    return stage_peak_gb(stage.render_mp, stage.output_size[0] * stage.output_size[1] / 1e6,
                         stage.padded_size[0] * stage.padded_size[1] / 1e6)


@dataclass
class Stage:
    index: int
    factor: float
    supersample: float
    input_size: tuple          
    padded_size: tuple         
    render_size: tuple
    output_size: tuple         
    render_mp: float
    minutes: float


@dataclass
class Plan:
    ok: bool
    factor: int
    input_size: tuple
    output_size: tuple
    stages: list = field(default_factory=list)
    minutes: float = 0.0
    peak_ram_gb: float = 0.0
    reason: str = ''
    suggestions: list = field(default_factory=list)
    ram_limited: bool = False      # a stage uses a lighter supersample than the full one so the image fits the memory cap
    engine: str = 'classic'        # 5.0.2: 'classic' (5.0.1's engine) or 'banded' (the Large-image engine); not stored when classic
    banded: dict = None            # 5.0.2: the Large-image engine's plan constants (engine/banded_plan.py); not stored when None

    def to_dict(self):
        """JSON shapes (sizes as lists, not tuples): the dict is stored on job records and compared with the copy read back
        after a restart (12 Nov, QA CONTRACT-2: a tuple never equals the list it is read back as). A classic plan's dict is
        5.0.1's, key for key: `engine` and `banded` are left out when they are 'classic' and None."""
        d = _lists(asdict(self))
        d['stages'] = [_lists(asdict(s)) for s in self.stages]
        if d.get('engine') == 'classic':
            d.pop('engine')
        if d.get('banded') is None:
            d.pop('banded', None)
        return d


def _lists(d):
    return {k: (list(v) if isinstance(v, tuple) else v) for k, v in d.items()}


def _pad_unit(f, s):
    """Smallest m such that m*f*s and m*f are whole and m*f*s is a multiple of 8."""
    fs = Fraction(f) * Fraction(s)
    m = 1
    while not ((m * fs).denominator == 1 and (m * fs).numerator % 8 == 0 and (m * Fraction(f)).denominator == 1):
        m += 1
    return m


def _pad_to(v, unit):
    return int(math.ceil(v / unit) * unit)


def stage_minutes(render_mp):
    return 5.5 + 0.27 * render_mp


def plan_501(width, height, factor, render_cap=RENDER_CAP_MP, output_cap=STAGE_OUTPUT_CAP_MP, ram_cap_gb=None):
    """The stages for `factor`. With ram_cap_gb (the memory cap in GiB), each stage takes the fullest supersample whose
    peak fits the cap (2, then 1.5, then 1) before the image is refused; `ram_limited` then says a stage was lightened for
    memory. When no supersample fits, the stage keeps its lightest one and peak_ram_gb is above the cap, so the caller's
    memory refusal names the least memory the image needs. Without ram_cap_gb the plan is the one every earlier version
    made."""
    w0, h0 = int(width), int(height)
    cap = None if ram_cap_gb is None else float(ram_cap_gb)
    ram_limited = False
    if factor not in STAGE_FACTORS:
        return Plan(False, factor, (w0, h0), (0, 0), reason='Choose an upscale of 2×, 4×, 6× or 8×.')
    out = (w0 * factor, h0 * factor)
    if min(w0, h0) < MIN_SIDE:
        return Plan(False, factor, (w0, h0), out, reason=f'This image is too small ({w0:,} × {h0:,} px). The shortest side must be at least {MIN_SIDE} px.')
    if w0 * h0 / 1e6 > MAX_INPUT_MP:
        return Plan(False, factor, (w0, h0), out, reason=f'This image is very large ({w0 * h0 / 1e6:.0f} MP). Images up to {MAX_INPUT_MP:.0f} MP are supported.')
    stages, cur = [], (w0, h0)
    for i, f in enumerate(STAGE_FACTORS[factor]):
        f = Fraction(f)
        chosen, too_wide, fitting = None, False, []
        for s in SUPERSAMPLES:
            unit = _pad_unit(f, s)
            pw, ph = _pad_to(cur[0], unit), _pad_to(cur[1], unit)
            rw, rh = int(pw * f * s), int(ph * f * s)
            ow, oh = int(cur[0] * f), int(cur[1] * f)
            rmp, omp = rw * rh / 1e6, ow * oh / 1e6
            
            
            sides = [int(pw * f), int(ph * f)] + ([] if f * s == 4 else [rw, rh])
            if max(sides) > MAX_SIDE:
                too_wide = True
                continue
            if rmp <= render_cap and omp <= output_cap:
                fitting.append(Stage(i, float(f), float(s), cur, (pw, ph), (rw, rh), (ow, oh), round(rmp, 1),
                                     round(stage_minutes(rmp), 1)))
                # the figure peak_ram_gb is made of (the stage's rounded render MP), rounded as it is, so a stage chosen
                # here never fails the caller's memory check, and one that passes it is never lightened
                if cap is None or round(stage_peak(fitting[-1]), 1) <= cap:
                    chosen = fitting[-1]
                    break
        if chosen is None and fitting:
            chosen = fitting[-1]                 # nothing fits the memory cap: the lightest, so the refusal says the least
        elif chosen is not None and fitting and chosen is not fitting[0]:
            ram_limited = True
        if chosen is None:
            ow, oh = int(cur[0] * f), int(cur[1] * f)
            fits = lambda g: w0 * h0 * g * g / 1e6 <= output_cap and max(w0, h0) * g <= MAX_SIDE
            sug = [f'{g}×' for g in sorted(STAGE_FACTORS) if g < factor and fits(g)]
            if too_wide and out[0] * out[1] / 1e6 <= output_cap:
                
                reason = f'{factor}× would make {out[0]:,} × {out[1]:,} px, over the {MAX_SIDE:,} px limit for the longest side.'
            else:
                reason = (f'{factor}× would make a {out[0]:,} × {out[1]:,} px image ({out[0] * out[1] / 1e6:.0f} MP). '
                          f'The largest supported output is about {output_cap:.0f} MP.')
            return Plan(False, factor, (w0, h0), out, stages, reason=reason,
                        suggestions=([f'Choose {sug[-1]} for this image'] if sug else []) + ['Or use a smaller source image'])
        stages.append(chosen)
        cur = chosen.output_size
    minutes = round(sum(s.minutes for s in stages), 1)
    peak = round(max(stage_peak(s) for s in stages), 1)
    return Plan(True, factor, (w0, h0), cur, stages, minutes, peak, ram_limited=ram_limited)


# 5.0.2 (Max, 20 Nov 2026: "Fold into 5.0.2"): SAM fits the card. 5.0.1's SAM3_Detect upsamples all 200 query masks to the
# whole pass input on the card (about 0.37 GiB per input MP), so a protect-on pass with a large input spills into shared GPU
# memory. A stage whose padded input is above SAM_STOCK_MAX_MP (MP) takes the lean SAM node instead (engine/graph_v5t.py,
# node_pack/claude_creative/sam_lean.py): the same masks, with only the kept mask upsampled. Every other stage keeps
# SAM3_Detect. The figure is S0b's registered one, conservatively, until eng:prove measures the ceiling.
SAM_STOCK_MAX_MP = 18.0
SAM_STOCK_MAX_SOURCE = (
    "S0b (5.0.1 on an RTX 5090 32 GB, run 9e0e33826f354851aa42e2132ca359cd, 19 Nov 2026): SAM-step demand 13.823 + "
    "0.3695 GiB per padded input MP; a 66.4 MP pass-3 input spilled 9.3 GiB into shared GPU memory, a 16.6 MP one did not. "
    "Registered ceiling 21.0 MP (a lower bound) and registered cap floor(0.9 x 21.0) = 18 MP, used here as it is; the "
    "adapter-counter bound (an upper bound) was 44.3 MP. eng:prove's registered check at a 36-39 MP protect-on pass input "
    "sets the measured figure.")


def sam_lean(width, height):
    """True when a SAM input of width x height px (a stage's padded input, or a protected-area preview's source) is above
    SAM_STOCK_MAX_MP, so the lean SAM node runs in place of SAM3_Detect."""
    return int(width) * int(height) / 1e6 > SAM_STOCK_MAX_MP


# 5.0.2: honest times. 5.0.1's stage minutes (stage_minutes: 5.5 + 0.27 x render MP) had no input or output term, and a
# 6x protect-on image said 80.5 min (Standard: the minutes x engine_options.ETA_STACK, 0.70) and took 114.6: the x4 model
# and the hints cost about 20 s per input MP, the finish and the save about 6 s per output MP. 5.0.2's stage minutes are
# 5.5 + TIME_PER_RENDER_MP x render MP + TIME_PER_INPUT_MP x padded input MP + TIME_PER_OUTPUT_MP x output MP, and never
# below 5.0.1's. The three figures are the smallest upper envelope (an LP, rounded up) of the stage times measured on the
# 5.0.1 engine on 19 Nov 2026 (tests/fixtures/stage_times_5_0_1.json: 19 stages of 11 jobs, Standard and Bolt, 64 GB PCs
# and the 128 GB workstation): every one took at most the time said, for its mode's factor, and so did every job's
# stages together. Times only: no stage, size or graph depends on them.
TIME_BASE_MINUTES = 5.5
TIME_PER_RENDER_MP = 0.238
TIME_PER_INPUT_MP = 0.423
TIME_PER_OUTPUT_MP = 0.128


def stage_minutes_502(render_mp, input_mp, output_mp):
    """Planner minutes of one stage (5.0.2): an upper bound of the measured stage times, never below 5.0.1's."""
    return max(stage_minutes(render_mp), TIME_BASE_MINUTES + TIME_PER_RENDER_MP * float(render_mp)
               + TIME_PER_INPUT_MP * float(input_mp) + TIME_PER_OUTPUT_MP * float(output_mp))


def stage_io_minutes(render_mp, input_mp, output_mp):
    """The part of stage_minutes_502 that is input and output work beyond a full-supersample 2x stage of the same render
    (whose input is a 16th and whose output a quarter of its render): the x4 model and hints on a larger input, the finish
    and save on a larger output. Two cards sharing one image share none of it (service/engine_options.plan_io_share); 0 for a
    full-supersample 2x stage."""
    r = float(render_mp)
    return max(0.0, TIME_PER_INPUT_MP * (float(input_mp) - r / 16) + TIME_PER_OUTPUT_MP * (float(output_mp) - r / 4))


def with_times(p):
    """A classic plan with 5.0.2's minutes (stage_minutes_502 per stage, rounded as 5.0.1 rounds; the plan's the sum). Only
    the minutes change, and only for a plan 5.0.1 made (ok); a refusal is returned as it is."""
    if not p.ok:
        return p
    for s in p.stages:
        s.minutes = round(stage_minutes_502(s.render_size[0] * s.render_size[1] / 1e6,
                                            s.padded_size[0] * s.padded_size[1] / 1e6,
                                            s.output_size[0] * s.output_size[1] / 1e6), 1)
    p.minutes = round(sum(s.minutes for s in p.stages), 1)
    return p


def plan(width, height, factor, render_cap=RENDER_CAP_MP, output_cap=STAGE_OUTPUT_CAP_MP, ram_cap_gb=None):
    """5.0.2's planner (engine design, section 2.1): 5.0.1's plan (plan_501, verbatim) for every image 5.0.1 accepts on this
    computer, lightened for memory or not; otherwise the Large-image engine's plan when that engine is proven for the size on
    this machine class (engine/banded_plan.py); otherwise 5.0.1's own answer, its refusal. With non-default render or output
    caps, or without a memory cap (no machine class), only 5.0.1's plan is made. A classic plan carries 5.0.2's minutes
    (with_times); every other value of it is plan_501's."""
    p = with_times(plan_501(width, height, factor, render_cap, output_cap, ram_cap_gb))
    if ram_cap_gb is None or render_cap != RENDER_CAP_MP or output_cap != STAGE_OUTPUT_CAP_MP:
        return p
    if p.ok and p.peak_ram_gb <= float(ram_cap_gb):
        return p
    from engine import banded_plan
    q = banded_plan.plan_banded(width, height, factor, float(ram_cap_gb), classic=p)
    return q if q.ok else p
