"""Gpu policy implementation."""


from dataclasses import dataclass, field


SPLIT_SAVING_S_PER_MP = 3.4
SWITCH_COST_S = 68.0


MIN_SPLIT_FREE_VRAM_GB = 19.0


SPLIT_EFFICIENCY = 0.90          
SAMPLING_SHARE = 0.75            


class PolicyError(ValueError):
    pass


def split_eligible(cards, min_free_gb=MIN_SPLIT_FREE_VRAM_GB):
    """cards: [{index, name, mem_free_gb, mem_total_gb}] -> indices that may join a one-image split (enough free VRAM)."""
    return [c['index'] for c in cards if (c.get('mem_free_gb') or 0) >= min_free_gb]


def card_weights(cards, measured=None):
    """Relative speed per card for the static window split, main card first. measured: {card name: seconds per window}."""
    measured = measured or {}
    out = []
    for c in cards:
        s = measured.get(c['name'])
        out.append(1.0 / s if s else float(c.get('sm_count') or 1))
    top = max(out)
    return [round(v / top, 4) for v in out]


def balance_mode(cards):
    """'queue' for identical cards (same name and memory), else 'static'."""
    return 'queue' if len({(c['name'], c.get('mem_total_gb')) for c in cards}) == 1 else 'static'


def split_speedup(n_cards, sampling_share=SAMPLING_SHARE, efficiency=SPLIT_EFFICIENCY):
    """Expected wall-time ratio one card / n cards for one stage (Amdahl: only sampling is split)."""
    if n_cards <= 1:
        return 1.0
    eff = 1 + (n_cards - 1) * efficiency
    return 1.0 / ((1 - sampling_share) + sampling_share / eff)


def split_saving_s(render_mp, n_cards):
    """Seconds one image of `render_mp` render megapixels saves on n cards against one warm card: W2's two-card measurement
    (SPLIT_SAVING_S_PER_MP), scaled for more cards by the Amdahl estimate above."""
    if n_cards <= 1 or not render_mp:
        return 0.0
    scale = (1 - 1 / split_speedup(n_cards)) / (1 - 1 / split_speedup(2))
    return float(render_mp) * SPLIT_SAVING_S_PER_MP * scale


@dataclass
class Topology:
    mode: str                     
    workers: list                 
    reason: str = ''
    saving_s: float = 0.0
    caps_gb: dict = field(default_factory=dict)
    under_floor: list = field(default_factory=list)   


def worker_caps(workers, ram_cap_gb):
    if len(workers) <= 1:
        return {w: float(ram_cap_gb) for w in workers}
    each = round(float(ram_cap_gb) / len(workers), 1)
    return {w: each for w in workers}


def plan_topology(cards, enabled, queued, running, current, split_enabled=True, ram_cap_gb=110.0, waiting_mp=0.0,
                  min_free_gb=None, warm=None):
    """The worker topology for the next dispatch.

    cards       nvidia-smi rows [{index, name, mem_free_gb, mem_total_gb}] (free VRAM as seen with no worker of ours on them)
    enabled     the card numbers in use (settings gpus)
    queued      images waiting          running   images rendering now        current   the topology in use, or None
    waiting_mp  the render megapixels of the next waiting image (its plan's stages), for the switch test (split_saving_s).
                Until 12 Nov it was waiting_minutes, the planner's minutes, which hold 5.5 min a stage before any pixel.
    warm        the card groups that have a loaded engine now, e.g. [(0,), (1,)] or [(0, 1)] (the runner knows); None = not
                known, and the topology in use counts as loaded. A switch costs a model reload only when a loaded engine has
                to be stopped for it: with nothing loaded, or the shared engine itself loaded, sharing costs nothing extra.
    A running image is never moved; a topology change happens only between images."""
    lanes = Topology('lanes', [(g,) for g in enabled], 'one image per card')
    lanes.caps_gb = worker_caps(lanes.workers, ram_cap_gb)
    if len(enabled) < 2 or not split_enabled:
        lanes.reason = 'one card' if len(enabled) < 2 else 'split turned off'
        return lanes
    if running > 0 and current is not None:
        current.reason = 'images are rendering; topology changes only between images'
        current.under_floor = []          
        return current
    if queued >= len(enabled) or queued == 0:
        lanes.reason = 'enough images for every card' if queued else 'nothing waiting'
        if current is not None:
            current.under_floor = []
        return lanes if current is None or queued else current
    by_index = {c['index']: c for c in cards}
    floor = MIN_SPLIT_FREE_VRAM_GB if min_free_gb is None else float(min_free_gb)
    elig = [g for g in enabled if g in split_eligible([by_index[g]] if g in by_index else [], floor)]
    if len(elig) < 2:
        lanes.reason = 'not enough free graphics memory on a second card'
        lanes.under_floor = [(g, round(float(by_index[g].get('mem_free_gb') or 0.0), 1)) for g in enabled
                             if g in by_index and g not in elig]
        return lanes
    if queued < len(elig):
        
        n = len(elig) // queued
        groups = [tuple(elig[i * n:(i + 1) * n]) for i in range(queued)]
        groups[-1] = groups[-1] + tuple(elig[queued * n:])
        sp = Topology('split', groups, f'{queued} image(s) for {len(elig)} cards')
        sp.saving_s = split_saving_s(waiting_mp, len(groups[0]))
        if warm is None:
            switching = current is not None and current.workers != sp.workers
        else:
            new = {tuple(g) for g in sp.workers}
            used = {c for g in new for c in g}
            switching = any(tuple(g) not in new and used & set(g) for g in warm)
        if switching and sp.saving_s <= SWITCH_COST_S:
            keep = current if current is not None else lanes
            keep.reason = f'split would save {sp.saving_s:.0f} s, less than the {SWITCH_COST_S:.0f} s switch'
            return keep
        sp.caps_gb = worker_caps(sp.workers, ram_cap_gb)
        return sp
    return lanes
