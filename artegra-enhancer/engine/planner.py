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


# Peak memory of one stage, in GiB of committed memory (the figure the Windows Job limit counts, for the engine and the
# service together), from the stage's render, output and input megapixels. The constants are the smallest upper envelope
# of the peaks measured on RTX 5090 PCs (19 Nov 2026: Redux and Bolt, 2x to 8x, renders of 67 to 157 MP, outputs up to
# 131 MP, inputs up to 32.8 MP; Bolt peaks 5-7 GiB above Redux at the same size, so the envelope follows Bolt), times
# PEAK_MARGIN. It is an upper bound for those runs: one card, the original memory settings. Until 5.0.1 the model was
# 30 + 0.15 x render MP + 0.43 x output MP, 17-34 % above the measured peaks, which refused images a 64 GB PC renders.
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

    def to_dict(self):
        """JSON shapes (sizes as lists, not tuples): the dict is stored on job records and compared with the copy read back
        after a restart (12 Nov, QA CONTRACT-2: a tuple never equals the list it is read back as)."""
        d = _lists(asdict(self))
        d['stages'] = [_lists(asdict(s)) for s in self.stages]
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


def plan(width, height, factor, render_cap=RENDER_CAP_MP, output_cap=STAGE_OUTPUT_CAP_MP, ram_cap_gb=None):
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
