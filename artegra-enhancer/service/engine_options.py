"""Engine options implementation."""


import math
import os
from pathlib import Path

from engine import fast_recipe, graph_v5t
from service.gpu_policy import MIN_SPLIT_FREE_VRAM_GB   

DETAILED_DECODER = 'taesdxl_decoder.safetensors'


DETAILED_OVER_BUDGET = False


SPLIT_PROVEN = True


SPLIT_EARLIER_PROVEN = True


SPLIT_SAMPLING_FACTOR = 1.55
SPLIT_SAMPLING_FACTOR_EARLIER = 1.37


LIVE_REGIONS_PROVEN = True


LIVE_REGION_MAX_SIDE = 8192
LIVE_DEFAULT_MAX_SIDE = 2048      


CREATIVE_FIRST_PROVEN = True
OUTLINE_GROUPS_PROVEN = True


V5_SPLIT_PROVEN = False


FAST_PROVEN = True
FAST_SPLIT_PROVEN = False
FASTER_PROVEN = False
FASTER_SPLIT_PROVEN = False


FASTER_FACTOR = 0.87
FASTER_STAGES = (0,)
FASTER_SUPERSAMPLES = (2.0,)
ETA_STACK = 0.70                  
ETA_EARLIER = 0.947               


ETA_STACK_SAMPLING = round(632.9 / 1269.4, 3)       
ETA_EARLIER_SAMPLING = round(939.6 / 1269.4, 3)     


def decoder_path(vae_approx_dir):
    return Path(vae_approx_dir) / DETAILED_DECODER


def detailed_state(setting_on, decoder_ok):
    """{'available', 'on', 'reason'} for /api/live and /health (contract section 2)."""
    if not decoder_ok:
        return {'available': False, 'on': False, 'reason': 'decoder_missing'}
    if DETAILED_OVER_BUDGET:
        return {'available': True, 'on': False, 'reason': 'over_budget'}
    if not setting_on:
        return {'available': True, 'on': False, 'reason': 'turned_off'}
    return {'available': True, 'on': True, 'reason': None}


def live_mode(detailed_on):
    """The ClaudeSpotTiles live_preview of a product stage. CU_LIVE_PREVIEW=off (proof runs only: tools/e2e_real.py's
    reference render with no live feed at all, the yardstick of the feed's cost, P7) gives 'off'; the product never sets it."""
    if os.environ.get('CU_LIVE_PREVIEW', '').strip().lower() == 'off':
        return 'off'
    return 'detailed' if detailed_on else 'rough'


def _switch(env_name, constant):
    env = os.environ.get(env_name, '').strip()
    if env in ('0', '1'):
        return env == '1'
    return bool(constant)


def live_regions_on():
    """preview design: workers are started to send full-size detailed tiles, and /api/live offers 1:1 regions of the live picture."""
    return _switch('CU_LIVE_REGIONS', LIVE_REGIONS_PROVEN)


def v5_split_on():
    """The v5 live switches also reach an image shared by several cards (V5_SPLIT_PROVEN, CU_V5_SPLIT)."""
    return _switch('CU_V5_SPLIT', V5_SPLIT_PROVEN)


def creative_first_on(shared=False):
    """v5: a new stage samples the detail (creative) pass first (CREATIVE_FIRST_PROVEN, CU_CREATIVE_FIRST). shared: the stage
    runs on several cards (a MultiCardWorker), which also needs V5_SPLIT_PROVEN (CU_V5_SPLIT)."""
    return _switch('CU_CREATIVE_FIRST', CREATIVE_FIRST_PROVEN) and (not shared or v5_split_on())


def outline_groups_on(shared=False):
    """v5: engines are started to send one outline frame per window group (OUTLINE_GROUPS_PROVEN, CU_OUTLINE_GROUPS); read
    when an engine starts (the node pack reads CLAUDE_LIVE_GROUPS when ClaudeSpotTiles runs). shared: an engine on several
    cards, which also needs V5_SPLIT_PROVEN (CU_V5_SPLIT)."""
    return _switch('CU_OUTLINE_GROUPS', OUTLINE_GROUPS_PROVEN) and (not shared or v5_split_on())


def fast_proven():
    """Fast mode may be offered (FAST_PROVEN, CU_FAST)."""
    return _switch('CU_FAST', FAST_PROVEN)


def fast_split_on():
    """A Fast image may be shared by several cards (FAST_SPLIT_PROVEN, CU_FAST_SPLIT; or the recipe's own split_ok)."""
    return _switch('CU_FAST_SPLIT', FAST_SPLIT_PROVEN) or bool(fast_recipe.describe()['split'])


def faster_proven():
    """"Speed up upscaling" (Faster) may be offered (FASTER_PROVEN, CU_FASTER)."""
    return _switch('CU_FASTER', FASTER_PROVEN)


def faster_split_on():
    """An image shared by several cards may run Faster (FASTER_SPLIT_PROVEN, CU_FASTER_SPLIT)."""
    return _switch('CU_FASTER_SPLIT', FASTER_SPLIT_PROVEN)


def live_switches():
    """The v5 live-preview switches as this process has them (/health.engine.live, /health.features): an image on one card,
    and an image shared by several cards (`_shared`)."""
    return {'creative_first': creative_first_on(), 'outline_groups': outline_groups_on(),
            'creative_first_shared': creative_first_on(shared=True), 'outline_groups_shared': outline_groups_on(shared=True)}


def live_tile_scale(max_side, render_size, supersample):
    """The worker's detailed tiles in pixels per pixel of the stage's output, for an emitter started with `max_side`
    (node_pack/claude_creative/live.py scales a tile by min(1, max_side / the render canvas's long side); the render canvas
    is `supersample` times the output). None when the tiles are at the emitter's default size (nothing to keep)."""
    if not max_side or int(max_side) <= LIVE_DEFAULT_MAX_SIDE:
        return None
    return min(1.0, int(max_side) / float(max(render_size))) * float(supersample)


def spot_options(detailed_on, speed_stack=True):
    """ClaudeSpotTiles inputs for one Standard stage of the product graph (= graph_v5t.product_options)."""
    return graph_v5t.product_options(bool(speed_stack), live_mode(detailed_on))


def eta_factor(speed_stack=True, cards=1, mode='standard'):
    """What the planner's minutes are multiplied by for one image: Standard with or without the stack, or Fast (None when no
    recipe is installed); `cards` > 1 = one image shared by that many cards: only the sampling share shrinks, by the
    two-card factor the workstation measured (no credit for Fast, whose recipe has no sampling share here)."""
    if mode == 'fast':
        d = fast_recipe.describe()
        if not d['installed']:
            return None
        base, sampling = float(d['factor']), None
    else:
        base, sampling = (ETA_STACK, ETA_STACK_SAMPLING) if speed_stack else (ETA_EARLIER, ETA_EARLIER_SAMPLING)
    two = SPLIT_SAMPLING_FACTOR if speed_stack else SPLIT_SAMPLING_FACTOR_EARLIER
    if cards > 1 and two and sampling is not None:
        gain = 1.0 + (float(two) - 1.0) * (cards - 1)       
        base = base - sampling * (1.0 - 1.0 / gain)
    return round(base, 3)


def _stage_field(st, key, default=None):
    return st.get(key, default) if isinstance(st, dict) else getattr(st, key, default)


def _plan_stages(plan):
    """The stages of a plan (a planner.Plan or its dict), or None."""
    if plan is None:
        return None
    stages = plan.get('stages') if isinstance(plan, dict) else getattr(plan, 'stages', None)
    return list(stages) if stages else None


def plan_render_mp(plan):
    """The render megapixels of a plan's stages together (the split policy's switch test; runner._dispatch_split)."""
    return sum(float(_stage_field(st, 'render_mp', 0) or 0) for st in _plan_stages(plan) or [])


def _stage_minutes(plan):
    """The planner's minutes of each stage of a plan (a planner.Plan or its dict), or None."""
    stages = _plan_stages(plan)
    if not stages:
        return None
    out = [float(_stage_field(st, 'minutes', 0) or 0) for st in stages]
    return out if sum(out) > 0 else None


def faster_stages(plan):
    """The stages of a plan that run Faster: those FASTER_STAGES names (the first, always a 2x stage; preview design) that run at a
    supersample Faster was rendered and timed at (FASTER_SUPERSAMPLES: 2; FC2). A plan whose first stage runs at
    supersample 1.5 or 1 (a 2x stage above about 9.4 MP) runs no stage Faster. Without the plan's stages: FASTER_STAGES (a
    caller that has not said which image; the plan of a 2x at supersample 2)."""
    stages = _plan_stages(plan)
    if stages is None:
        return list(FASTER_STAGES)
    return [k for k in FASTER_STAGES if k < len(stages)
            and float(_stage_field(stages[k], 'supersample', 0) or 0) in FASTER_SUPERSAMPLES]


def faster_stage_factors(plan, base):
    """Per stage, the finish-time factor of an image that runs Faster: the stack's factor `base` x FASTER_FACTOR on the stages
    Faster runs on (faster_stages), `base` on the rest. None without the plan's stages."""
    mins = _stage_minutes(plan)
    if mins is None:
        return None
    on = faster_stages(plan)
    return [round(base * (FASTER_FACTOR if k in on else 1.0), 4) for k in range(len(mins))]


def faster_factor(plan, base=ETA_STACK):
    """One image's factor with Faster on: the stage factors weighted by the planner's minutes of each stage. 0.609 for a 2x
    image on one card; 0.654 for S4 at 4x; `base` itself for a plan none of whose stages runs Faster (faster_stages).
    Without the plan's stages: the first stage alone (a 2x at supersample 2)."""
    mins = _stage_minutes(plan)
    sf = faster_stage_factors(plan, base)
    if mins is None or sf is None:
        return round(base * FASTER_FACTOR, 3)
    return round(sum(m * f for m, f in zip(mins, sf)) / sum(mins), 3)


def split_allowed(mode='standard', match_earlier=False, earlier_proven=None):
    """Whether an image that runs like this may be shared by several cards at all: the proof flags here and the Fast
    recipe's own. Settings, the number of cards and their free memory are the policy's business (service/gpu_policy.py).
    earlier_proven: None = SPLIT_EARLIER_PROVEN; the runner passes True only in a two-card proof run (service/app.py
    --two-card-proof), the run that decides that constant. A Fast image needs FAST_SPLIT_PROVEN (or its recipe's split_ok)."""
    if mode == 'fast':
        return fast_split_on()
    earlier = SPLIT_EARLIER_PROVEN if earlier_proven is None else bool(earlier_proven)
    return bool(earlier or not match_earlier)


def run_info(mode='standard', match_earlier=False, frozen=False, split=False, cards=1, faster=False, plan=None):
    """The `run` object of an item (contract part 2, section 1; fast-contract section 5), without `minutes`. faster: the
    image runs (or, waiting, would run) with "Speed up upscaling": Standard with the stack only, never on a shared image
    unless FASTER_SPLIT_PROVEN, and only when a stage of its plan runs Faster (faster_stages: none for an image whose 2x
    stage runs at supersample 1.5 or 1; FC2); its factor follows the plan's stages (faster_factor), and `stage_factors`
    gives the factor of each stage for the finish time while it runs. split / cards: the cards the image runs on (frozen) or
    would run on if it started now (waiting; the runner asks the split policy, FC3)."""
    if mode == 'fast':
        stack = bool(fast_recipe.describe()['speed_stack'])
        match_earlier = False
    else:
        stack = not match_earlier
    faster = bool(faster) and mode != 'fast' and stack and not match_earlier
    if faster and split and not faster_split_on():
        faster = False
    if faster and plan is not None and not faster_stages(plan):
        faster = False
    out = {'mode': mode, 'match_earlier': bool(match_earlier), 'speed_stack': stack, 'frozen': bool(frozen),
           'split': bool(split), 'factor': eta_factor(stack, cards if split else 1, mode), 'faster': faster}
    if faster:
        base = out['factor']
        out['factor'] = faster_factor(plan, base)
        sf = faster_stage_factors(plan, base)
        if sf is not None:
            out['stage_factors'] = sf
    return out


def speed_info(match_earlier=False, split_on=False, fast_available=None, faster=None):
    """/health engine.speed (the 10 Nov fields, and the port's). fast_available: Fast can be chosen now (None: installed and
    FAST_PROVEN; the runner passes its own answer, which also knows the files). faster: /health engine.faster (None: not
    offered)."""
    opts = graph_v5t.product_options(not match_earlier)
    if fast_available is None:
        fast_available = fast_recipe.installed() and fast_proven()
    faster = faster or {}
    return {'noise_prefetch': bool(opts.get('noise_prefetch')), 'pag_fuse': bool(opts.get('pag_fuse')),
            'batch_windows': int(opts.get('batch_windows') or 1), 'fp16_acc_scoped': bool(opts.get('fp16_acc_scoped')),
            'window_split': bool(split_on), 'eta_factor': eta_factor(not match_earlier),
            'speed_stack': not match_earlier, 'match_earlier': bool(match_earlier),
            'faster_available': bool(faster.get('available')), 'faster': bool(faster.get('on')),
            'factors': {'standard': ETA_STACK, 'match_earlier': ETA_EARLIER,
                        'fast': eta_factor(mode='fast') if fast_available else None,
                        'faster': FASTER_FACTOR if faster.get('available') else None}}


def finish_info(minutes, match_earlier=False, fast_available=False, plan=None, faster_available=False, fast_reason=None,
                cards=None):
    """`finish` of a plan object: the finish time per mode with Settings as they are (contract part 2, section 1;
    fast-contract section 4).

    The top-level pairs are one card's (each image of a batch that runs one image per card, and every image on a one-card
    machine): `standard`; `fast` only for a plan Fast can make (fast_plan_refusal), with `fast_refusal` {reason, message}
    saying why when it is null (the sentence the service answers 400 fast_unavailable with); `faster` (its pair gains
    `stages`, the stages that run Faster: [0], or [] for a plan whose 2x stage runs at supersample 1.5 or 1, FC2) only while
    Faster is offered, and null while "Match earlier results" is on.

    `single` (13 Nov 2026, FAST PORT FIX, FC3): the same three for ONE image of this plan started now on its own, on the cards
    the split policy would give it (`cards`: {'standard': n, 'fast': n}, from the runner; 1 each when not given). Each pair
    there carries `cards`. On the two-card workstation a single Standard image is shared (0.523 of the planner's minutes), a
    single Fast image runs on one card (0.37: about 1.4x Standard's speed there, not 1.9x; BRIEF-v5 15), and a single Faster
    image that would be shared runs as Standard, shared, until FASTER_SPLIT_PROVEN (its pair is Standard's, stages [])."""
    def pair(factor, **extra):
        return None if factor is None else dict({'minutes': round(float(minutes) * factor, 1), 'factor': factor}, **extra)
    cards = cards or {}
    n_std, n_fast = max(1, int(cards.get('standard') or 1)), max(1, int(cards.get('fast') or 1))
    stack = not match_earlier
    refusal = fast_plan_refusal(plan) if fast_available else (fast_reason or 'no_recipe')
    fast = fast1 = None
    if refusal is None:
        fast = pair(eta_factor(mode='fast'))
        fast1 = pair(eta_factor(mode='fast', cards=n_fast), cards=n_fast)
    out = {'match_earlier': bool(match_earlier), 'standard': pair(eta_factor(stack)), 'fast': fast,
           'fast_refusal': None if refusal is None else {'reason': refusal,
                                                         'message': FAST_REFUSALS.get(refusal, FAST_REFUSAL)}}
    single = {'standard': pair(eta_factor(stack, n_std), cards=n_std), 'fast': fast1}
    if faster_available:
        on = faster_stages(plan)
        out['faster'] = None if match_earlier else pair(faster_factor(plan), stages=on)
        if match_earlier:
            single['faster'] = None
        elif n_std > 1 and not faster_split_on():
            single['faster'] = dict(single['standard'], stages=[])         
        else:
            base = eta_factor(True, n_std)
            single['faster'] = pair(faster_factor(plan, base), cards=n_std, stages=on)
    out['single'] = single
    return out


def fast_plan_refusal(plan):
    """Why Fast cannot make this plan, as fast_refusal's `data.reason`, or None when it can: 'no_recipe'; 'scale' (its
    output factor is above the recipe's max_factor: a second stage); 'size' (a stage would run at a supersample the
    recipe's proof did not render, fast_recipe.SUPERSAMPLES: a 2x image above about 9.4 MP, which the planner renders at
    supersample 1.5 or 1; FC1). None without a plan (the caller has not said which) and for a plan the planner refused (its
    own reason stands)."""
    d = fast_recipe.describe()
    if not d['installed']:
        return 'no_recipe'
    if plan is None:
        return None
    factor = plan.get('factor') if isinstance(plan, dict) else getattr(plan, 'factor', None)
    if d['max_factor'] is not None and (factor is None or float(factor) > float(d['max_factor'])):
        return 'scale'
    ok = plan.get('ok', True) if isinstance(plan, dict) else getattr(plan, 'ok', True)
    allowed = {float(x) for x in d['supersamples']}
    if ok and any(float(_stage_field(st, 'supersample', 0) or 0) not in allowed for st in _plan_stages(plan) or []):
        return 'size'
    return None


def fast_plan_ok(plan):
    """A plan Fast can make (fast_plan_refusal is None): one stage (the recipe's max_factor) at a supersample its proof
    rendered. True without a plan (the caller has not said which)."""
    return fast_plan_refusal(plan) is None


SPLIT_MESSAGES = {'pending_ws_proof': 'Each image runs on one GPU in this version.',
                  'one_card': 'One GPU is in use, so each image runs on it.',
                  'match_earlier': '"Match earlier results" is on, so each image runs on one GPU.'}


def gb_text(v):
    return f'{float(v):.0f} GB'


def free_text(v, floor_gb):
    """A card's free memory in the under-the-floor sentence: whole GB, or one decimal rounded down (and below the floor)
    where whole GB would read as the floor or more ("has 19 GB ... needs 19 GB" for 18.7 free; 12 Nov)."""
    v, floor = float(v), float(floor_gb)
    if round(v) < floor:
        return gb_text(v)
    return f'{min(math.floor(v * 10 + 1e-6) / 10, floor - 0.1):.1f} GB'


def under_floor_text(short, floor_gb, tail=None):
    """Engine options implementation."""


    names = ' and '.join(f'GPU {g + 1}' for g, _ in short)
    frees = ' and '.join(free_text(v, floor_gb) for _, v in short)
    verb = 'has' if len(short) == 1 else 'have'
    text = f'{names} {verb} {frees} free; sharing an image needs {gb_text(floor_gb)}'
    return f'{text}, so {tail}.' if tail else f'{text}.'


def split_info(setting, enabled, cards, topology=None, proven=None, floor_gb=None, match_earlier=False, earlier_proven=None):
    """/health engine.split. setting: Settings `split` as it reads; enabled: the GPU numbers in use; cards: [{index,
    mem_free_gb}] with the free memory a shared image would find (the runner adds what its own idle engines give back);
    match_earlier: Settings "Match earlier results" as it reads (a new image would run with the earlier numbers).
    proven / earlier_proven: None = SPLIT_PROVEN / SPLIT_EARLIER_PROVEN (the runner passes what its process may do).
    `reason` 'pending_ws_proof' is the contract's word for "not proven": a build whose SPLIT_PROVEN is False (none since 12
    Nov; the tests hold that state with the fake engine's CU_SPLIT_TEST=0)."""
    proven = SPLIT_PROVEN if proven is None else bool(proven)
    floor = MIN_SPLIT_FREE_VRAM_GB if floor_gb is None else float(floor_gb)
    by = {c['index']: c for c in cards}
    rows = []
    for g in enabled:
        free = by.get(g, {}).get('mem_free_gb')
        rows.append({'gpu': g, 'vram_free_gb': None if free is None else round(float(free), 1),
                     'above_floor': free is None or float(free) >= floor})
    available = proven and len(enabled) > 1
    earlier = bool(match_earlier) and not split_allowed(match_earlier=True, earlier_proven=earlier_proven)
    on = available and bool(setting) and not earlier
    reason = message = None
    if not proven:
        reason = 'pending_ws_proof'
    elif len(enabled) < 2:
        reason = 'one_card'
    elif not setting:
        reason = 'turned_off'
    elif earlier:
        reason = 'match_earlier'
    else:
        short = [(r['gpu'], r['vram_free_gb']) for r in rows if not r['above_floor']]
        if short:
            reason, message = 'card_under_floor', under_floor_text(short, floor)
    if reason in SPLIT_MESSAGES:
        message = SPLIT_MESSAGES[reason]
    return {'available': available, 'on': on, 'reason': reason, 'topology': topology, 'proven': proven,
            'setting': bool(setting), 'floor_gb': floor, 'message': message, 'cards': rows}


FAST_MESSAGES = {'no_recipe': 'Fast mode is not in this version.',
                 'pending_proof': 'Fast mode is not in this version.',
                 'files_missing': 'Fast mode cannot be used: a file it needs cannot be read.',
                 'checking': 'Checking the files Fast mode needs.'}
FAST_REFUSAL = 'Fast mode is not available. Choose Standard.'


FAST_REFUSALS = {'no_recipe': FAST_REFUSAL, 'pending_proof': FAST_REFUSAL,
                 'files_missing': 'Fast mode cannot be used: a file it needs cannot be read. Choose Standard.',
                 'checking': 'Fast mode is not ready yet: its files are still being checked. Try again in a moment.',
                 'scale': 'Fast mode upscales 2× only. Choose Standard for 4× and above.',
                 'look': 'Fast mode offers Light and Default only. Choose Standard for Strong, Heavy, Extreme or Custom.',
                 
                 'size': 'Fast mode works on images up to about 9 MP. Choose Standard for larger images.'}

FAST_SIZE_FAILURE = 'This image is too large for Fast mode, so it was not upscaled. Queue it again in Standard.'


def fast_info(files_ok=True, proven=None):
    """/health engine.fast. files_ok: the recipe's model files can be read with the right size and sha256 (the health probe
    checks them): True, False, or None = not checked yet since the service started (`checking`: not offered; FCK3, 13 Nov
    2026). proven: None = fast_proven() (FAST_PROVEN, CU_FAST); the runner passes True for the fake engine's stand-in
    recipe (CU_FAST_TEST=1, tests only)."""
    d = fast_recipe.describe()
    if not d['installed']:
        reason = 'no_recipe'
    elif not (fast_proven() if proven is None else bool(proven)):
        reason = 'pending_proof'
    elif files_ok is None:
        reason = 'checking'
    elif not files_ok:
        reason = 'files_missing'
    else:
        reason = None
    on = reason is None
    return {'available': on, 'reason': reason, 'message': FAST_MESSAGES.get(reason),
            'recipe': d['recipe'], 'version': d['version'], 'factor': d['factor'] if on else None,
            'factors': d['factors'] if on else None, 'split': fast_split_on() if on else False,
            'looks': list(d['looks']), 'max_factor': d['max_factor']}


def fast_refusal(effective, info, plan=None):
    """(reason, message) when a request whose effective settings are `effective` asks for Fast and Fast cannot make it, else
    None. info: fast_info() as the service has it now; plan: the image's plan at this scale, once it is known (the size
    check, FC1). The order of the checks: availability, then the scale, then the Look, then the image's size, so one
    sentence is returned."""
    if (effective or {}).get('mode') != 'fast':
        return None
    if not info.get('available'):
        reason = info.get('reason') or 'no_recipe'
        return reason, FAST_REFUSALS.get(reason, FAST_REFUSAL)
    mf = info.get('max_factor')
    if mf is not None and int(effective.get('scale') or 0) > int(mf):
        return 'scale', FAST_REFUSALS['scale']
    looks = info.get('looks') or []
    if looks and 'preset' in effective and effective.get('preset') not in looks:     
        return 'look', FAST_REFUSALS['look']
    if plan is not None:
        reason = fast_plan_refusal(plan)
        if reason is not None:
            return reason, FAST_REFUSALS.get(reason, FAST_REFUSAL)
    return None


FASTER_MESSAGES = {'pending_proof': 'Speed up upscaling is not in this version.'}
FASTER_WITH_MATCH = 'Speed up upscaling cannot be on while Match earlier results is on.'
MATCH_WITH_FASTER = 'Match earlier results cannot be on while Speed up upscaling is on.'


def faster_info(setting_on=False, match_earlier=False):
    """/health engine.faster. setting_on: Settings `faster`; match_earlier: Settings "Match earlier results" (the two cannot
    both be on; a stored pair from an older file counts as off)."""
    available = faster_proven()
    reason = None if available else 'pending_proof'
    return {'available': available, 'on': bool(available and setting_on and not match_earlier),
            'factor': FASTER_FACTOR, 'split': faster_split_on() if available else False,
            'reason': reason, 'message': FASTER_MESSAGES.get(reason)}


def faster_conflict(current, patch):
    """The 409 faster_with_match sentence for a settings patch that would leave Faster and "Match earlier results" both on,
    else None. current: the settings as they are ({'faster', 'match_earlier'})."""
    faster = patch.get('faster', bool(current.get('faster')))
    match = patch.get('match_earlier', bool(current.get('match_earlier')))
    if not (faster is True and match is True):
        return None
    if patch.get('faster') is True:
        return FASTER_WITH_MATCH
    if patch.get('match_earlier') is True:
        return MATCH_WITH_FASTER
    return None
