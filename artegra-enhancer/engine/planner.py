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


def plan(width, height, factor, render_cap=RENDER_CAP_MP, output_cap=STAGE_OUTPUT_CAP_MP):
    w0, h0 = int(width), int(height)
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
        chosen, too_wide = None, False
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
                chosen = Stage(i, float(f), float(s), cur, (pw, ph), (rw, rh), (ow, oh), round(rmp, 1), round(stage_minutes(rmp), 1))
                break
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
    peak = round(max(30 + 0.15 * s.render_mp + 0.43 * (s.output_size[0] * s.output_size[1] / 1e6) for s in stages), 1)
    return Plan(True, factor, (w0, h0), cur, stages, minutes, peak)
