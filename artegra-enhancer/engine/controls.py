"""Controls implementation."""


import re

CONTRACT = 'creative-upscaler-controls-v2'
PRESET_ORDER = ['Light', 'Default', 'Strong', 'Heavy', 'Extreme']
PRESETS = {  
    'Light':   (10, 80, 15),
    'Default': (50, 60, 35),
    'Strong':  (60, 56, 45),
    'Heavy':   (68, 53, 55),
    'Extreme': (77, 48, 65),
}
PRESET_TEXT = {
    'Light': 'Adds fine detail; planting keeps its species.',
    'Default': 'New detail; shapes and layout stay as they are.',
    'Strong': 'Crisper materials; planting may be redrawn.',
    'Heavy': 'More new detail; planting is often redrawn.',
    'Extreme': 'Most new detail; check planting and fine shapes.',
}
GENERIC = ('A professional high-resolution photograph. True-to-life materials, crisp sharp micro-detail, rich contrast, bright specular '
           'highlights, deep shadows, natural light, deep focus.')
NEGATIVE = ('cgi, 3d render, cartoon, illustration, painting, smooth plastic, waxy, blurry, soft focus, bokeh, flat lighting, low contrast, '
            'washed out, hazy, muddy, oversaturated, text, watermark, logo, badge, emblem, lettering, zipper, buckle')
DEFAULT_SEED = 20261102


PROTECT_CATEGORIES = {
    'people':       {'label': 'People', 'hint': 'Faces and bodies keep their features.', 'terms': ['person'], 'default': True},
    'furniture':    {'label': 'Furniture and objects', 'hint': 'Sofas, beds, chairs, benches and tables keep their shape.',
                     'terms': ['sofa', 'bed', 'chair', 'bench', 'table'], 'default': True},
    'vehicles':     {'label': 'Vehicles', 'hint': 'Cars keep their bodywork and badges.', 'terms': ['car'], 'default': True},
    'windows':      {'label': 'Windows and glass', 'hint': 'Glazing and reflections stay clean.', 'terms': ['window'], 'default': True},
    'architecture': {'label': 'Architecture', 'hint': 'Walls, roofs, floors, doors and stairs keep their geometry and materials. '
                     'People and planting are still enhanced unless People is ticked.',
                     'terms': ['building', 'wall', 'roof', 'facade', 'door', 'floor', 'ceiling', 'stairs', 'column'], 'default': False},
}
PROTECT_ORDER = ['people', 'furniture', 'vehicles', 'windows', 'architecture']
QUICK_PROTECT = {  
    'architecture_only_people_vegetation': {
        'label': 'Protect architecture and only enhance people and vegetation',
        'categories': ['furniture', 'vehicles', 'windows', 'architecture']},
}
PROTECT_SAM = {'threshold': 0.6, 'refine_iterations': 2, 'dilate': 12, 'feather': 4.0}


RELEASE_VEGETATION = ['tree', 'plant', 'bush', 'flower']
SCALES = [2, 4, 6, 8]
OUTPUT_FORMATS = {'png8': 'PNG 8-bit', 'png16': 'PNG 16-bit', 'tiff16': 'TIFF 16-bit', 'jpeg': 'JPEG (quality 95)'}


MODES = ['standard', 'fast']
MODE_LABELS = {'standard': 'Standard', 'fast': 'Fast'}
MODE_TEXT = {'standard': '', 'fast': 'Quicker, with a slightly different look. Use Standard for finals.'}


class ControlError(ValueError):
    pass


def _num(req, key, default):
    v = req.get(key, default)
    if isinstance(v, bool):
        raise ControlError(f'{key} must be a number from 0 to 100')
    try:
        v = float(v)
    except (TypeError, ValueError):
        raise ControlError(f'{key} must be a number from 0 to 100')
    if not 0 <= v <= 100:
        raise ControlError(f'{key} must be between 0 and 100 (got {v:g})')
    return v


def parse_seed(seed):
    if seed is None or seed == '':
        return DEFAULT_SEED
    if isinstance(seed, bool):
        raise ControlError('Seed must be a whole number')
    if isinstance(seed, int):
        v = seed
    elif isinstance(seed, str) and re.fullmatch(r'[0-9]{1,19}', seed.strip()):
        v = int(seed.strip())
    else:
        raise ControlError('Seed must be a whole number of up to 19 digits')
    if not 0 <= v <= 2 ** 63 - 1:
        raise ControlError('Seed must be between 0 and 9223372036854775807')
    return v


def protect_terms(categories):
    terms = []
    for cat in PROTECT_ORDER:
        if cat in categories:
            terms += PROTECT_CATEGORIES[cat]['terms']
    return terms


def creativity_denoise(c):
    """Creativity 0-100 -> creative-pass denoise, mapping v2 (6 Nov 2026). Batch v5 / v7 blind judging: perceived change saturates
    above .58 (v5t), and only a creative pass well below it keeps plant species (Light .436: 0 species changes from three judges,
    the only step they would ship for named planting). So the lower half spans .40-.58 and the upper half .58-.70."""
    return round(0.58 + (c - 50) * (0.0036 if c < 50 else 0.0024), 4)


def release_terms(categories):
    if 'architecture' not in categories:
        return []
    return RELEASE_VEGETATION + ([] if 'people' in categories else PROTECT_CATEGORIES['people']['terms'])


def resolve(req):
    """req: dict from the UI. Returns (params, effective). params feed engine.graph_v5t.build (per stage, via planner)."""
    allowed = {'preset', 'custom', 'creativity', 'resemblance', 'restoration', 'protect', 'quick_protect', 'scale', 'seed',
               'prompt', 'output_format', 'mode'}
    unknown = set(req) - allowed
    if unknown:
        raise ControlError('These settings are not recognised: ' + ', '.join(sorted(unknown)) + '.')
    preset = req.get('preset', 'Default')
    if preset not in PRESETS:
        raise ControlError('Choose a preset: ' + ', '.join(PRESET_ORDER) + '.')
    c, r, rs = PRESETS[preset]
    custom = bool(req.get('custom', False))
    if custom:
        c, r, rs = _num(req, 'creativity', c), _num(req, 'resemblance', r), _num(req, 'restoration', rs)
    elif any(k in req for k in ('creativity', 'resemblance', 'restoration')):
        vals = (_num(req, 'creativity', c), _num(req, 'resemblance', r), _num(req, 'restoration', rs))
        if vals != (c, r, rs):
            raise ControlError("These slider values are not the preset's values. Choose Custom to use your own.")
    scale = req.get('scale', 2)
    
    
    if isinstance(scale, float) and scale.is_integer():
        scale = int(scale)
    if isinstance(scale, bool) or not isinstance(scale, int) or scale not in SCALES:
        raise ControlError('Choose an upscale of 2×, 4×, 6× or 8×.')
    quick = req.get('quick_protect')
    if quick is not None and quick not in QUICK_PROTECT:
        raise ControlError('That protect option is not available. Choose one from the list.')
    if quick:
        cats = list(QUICK_PROTECT[quick]['categories'])
    else:
        cats = req.get('protect')
        if cats is None:
            cats = [k for k in PROTECT_ORDER if PROTECT_CATEGORIES[k]['default']]
        if not isinstance(cats, list) or any(k not in PROTECT_CATEGORIES for k in cats):
            raise ControlError('Choose protected areas from: ' + ', '.join(PROTECT_CATEGORIES[k]['label'] for k in PROTECT_ORDER) + '.')
        cats = [k for k in PROTECT_ORDER if k in cats]
    fmt = req.get('output_format', 'png8')
    if fmt not in OUTPUT_FORMATS:
        raise ControlError('Choose an output format: ' + ', '.join(OUTPUT_FORMATS.values()) + '.')
    mode = req.get('mode', 'standard')
    if mode not in MODES:
        raise ControlError('Choose a mode: Standard or Fast.')
    seed = parse_seed(req.get('seed'))
    user = (req.get('prompt') or '').strip()
    if len(user) > 400:
        raise ControlError('Extra description is limited to 400 characters')
    params = {
        'denoise': creativity_denoise(c),
        'tile': 0.70, 'tile_frac': round(0.25 + 0.25 * r / 100.0, 4),
        'structure': round(0.48 + 0.20 * rs / 100.0, 4),
        's_tile': round(0.60 + 0.25 * r / 100.0, 4),
        's_line': round(0.50 + 1.0 / 3.0 * r / 100.0, 4), 's_line_frac': 0.6,
        'pag': 3.0, 'cfg': 6.0, 'steps': 30, 'sampler': 'dpmpp_2m_sde', 'scheduler': 'karras', 'tile_px': 1024,
        'protect_terms': protect_terms(cats), 'release_terms': release_terms(cats), 'protect': dict(PROTECT_SAM),
        'fin_b0_hi': 6.0, 'toe': (0.40, 0.06), 'dat_tiling': 'margin', 'spot_clamp_blend': True, 'island_after_lf': True,
        'seed': seed, 'prompt': GENERIC + (' ' + user if user else ''), 'negative': NEGATIVE,
    }
    effective = {'contract': CONTRACT, 'preset': 'Custom' if custom and (c, r, rs) != PRESETS[preset] else preset,
                 'base_preset': preset, 'creativity': c, 'resemblance': r, 'restoration': rs, 'scale': scale,
                 'protect': cats, 'quick_protect': quick, 'seed': str(seed), 'prompt_extra': user, 'output_format': fmt,
                 'mode': mode,
                 
                 
                 'engine': {k: (list(v) if isinstance(v, tuple) else v) for k, v in params.items()
                            if k not in ('prompt', 'negative')}}
    return params, effective


def denoise_creativity(d):
    """Inverse of creativity_denoise (mapping v2): the creativity that gives creative-pass denoise d."""
    return 50.0 + (d - 0.58) / (0.0036 if d < 0.58 else 0.0024)


LATER_STAGE_POLICIES = {
    
    'decay08': (0.8, 1.0),
    'decay06': (0.6, 0.8),
}


def stage_params(params, k, policy='decay08', refine=None):
    """Parameters for stage k (0-based) of a multi-stage plan (DESIGN §6). Stage 0 is the user's recipe unchanged. Later stages:
    creativity (and restoration) shrink by the policy factors per stage, or `refine` = (creativity, resemblance, restoration)
    replaces the recipe for every later stage; seed + k. APPV1: 'decay08' over-invented on a 1008 px source at 6x."""
    if k == 0:
        return dict(params)
    p = dict(params)
    if refine is not None:
        c, r, rs = refine
        p['denoise'] = round(0.48 + 0.20 * c / 100.0, 4)
        p['tile_frac'] = round(0.25 + 0.25 * r / 100.0, 4)
        p['s_tile'] = round(0.60 + 0.25 * r / 100.0, 4)
        p['s_line'] = round(0.50 + 1.0 / 3.0 * r / 100.0, 4)
        p['structure'] = round(0.48 + 0.20 * rs / 100.0, 4)
    else:
        cf, rf = LATER_STAGE_POLICIES[policy]
        if p['denoise'] >= 0.48:
            
            
            c = (p['denoise'] - 0.48) / 0.20 * 100.0 * (cf ** k)
            p['denoise'] = round(0.48 + 0.20 * c / 100.0, 4)
        else:


            p['denoise'] = creativity_denoise(denoise_creativity(p['denoise']) * (cf ** k))
        rs = (p['structure'] - 0.48) / 0.20 * 100.0 * (rf ** k)
        p['structure'] = round(0.48 + 0.20 * rs / 100.0, 4)
    p['seed'] = (params['seed'] + k) % (2 ** 63)
    return p


def describe():
    """Everything the UI needs to draw the controls (labels, ranges, presets, protect options)."""
    return {
        'contract': CONTRACT,
        'presets': [{'name': n, 'values': dict(zip(('creativity', 'resemblance', 'restoration'), PRESETS[n])),
                     'text': PRESET_TEXT[n]} for n in PRESET_ORDER],
        'sliders': [
            {'key': 'creativity', 'label': 'Creativity', 'low': 'Faithful', 'high': 'Inventive',
             'text': 'How much new detail is invented.'},
            {'key': 'resemblance', 'label': 'Resemblance', 'low': 'Loose', 'high': 'Exact',
             'text': 'How closely shapes, edges and layout follow your original.'},
            {'key': 'restoration', 'label': 'Restoration', 'low': 'Keep', 'high': 'Renew',
             'text': 'How much fresh detail plain surfaces and protected areas get. High values can add artefacts.'},
        ],
        'protect': [{'key': k, **{x: PROTECT_CATEGORIES[k][x] for x in ('label', 'hint', 'default')}} for k in PROTECT_ORDER],
        'quick_protect': [{'key': k, 'label': v['label'], 'categories': v['categories']} for k, v in QUICK_PROTECT.items()],
        'scales': SCALES, 'output_formats': [{'key': k, 'label': v} for k, v in OUTPUT_FORMATS.items()],
        'modes': [{'key': k, 'label': MODE_LABELS[k], 'text': MODE_TEXT[k]} for k in MODES],
        'default_seed': str(DEFAULT_SEED),
    }
