"""Fast recipe implementation."""


from engine import graph_v5t, schedule


LORA = {'file': 'Hyper-SDXL-8steps-CFG-lora.safetensors', 'bytes': 787359648, 'strength': 0.25,
        'sha256': '55b51334c85061afff5eff7c550b61963c8b8607a5868bbe4f26db49374719b1',
        'source': 'ByteDance/Hyper-SD revision bc08d970a87c74c71209491d64e3525845698863'}
STEPS, CFG, SEAM_OVERLAP = 8, 5.0, 16
LOOKS = ('Light', 'Default')     
MAX_FACTOR = 2                   


def _build(input_name, w, h, params, prefix, f, s, live_preview):
    g, info = graph_v5t.build_product(input_name, w, h, params, prefix, f=f, s=s, speed_stack=True,
                                      live_preview=live_preview)
    nid = lambda: str(max(int(k) for k in g) + 1)
    ck = next(k for k, n in g.items() if n['class_type'] == 'CheckpointLoaderSimple'
              and n['inputs']['ckpt_name'] == graph_v5t.MODELS['ckpt'])
    pag = next(k for k, n in g.items() if n['class_type'] == 'PerturbedAttentionGuidance')
    spot = next(k for k, n in g.items() if n['class_type'] == 'ClaudeSpotTiles')
    lora = nid()
    g[lora] = {'class_type': 'LoraLoaderModelOnly', 'inputs': {'model': [ck, 0], 'lora_name': LORA['file'],
                                                                'strength_model': LORA['strength']}}
    g[pag]['inputs']['model'] = [lora, 0]                       
    g[spot]['inputs']['seam_overlap'] = SEAM_OVERLAP
    ends = {}
    for role, d, frac in (('detail', params['denoise'], params['tile_frac']),        
                          ('structure', params['structure'], params['s_line_frac'])):  
        kid = info['samplers'][role]
        k = g[kid]['inputs']
        assert g[kid]['class_type'] == 'KSampler' and k['scheduler'] == 'karras' and k['steps'] == params['steps']
        k['steps'], k['cfg'] = STEPS, CFG                       
        cn = k['positive'][0]                                   
        g[cn]['inputs']['end_percent'] = ends[role] = schedule.end_mid('karras', STEPS, d, frac)
    return g, dict(info, fast_ends=ends, spot_options=dict(info['spot_options'], seam_overlap=SEAM_OVERLAP))


RECIPE = {
    'name': 'H8-e8-s25-c5-p3-k+so16+stk',
    'version': '1',
    'proof': 'Validated v5 preview Fast recipe (R-own)',
    'eta_factor': 0.37,                                          
    'eta_factors': {'first_stage': 0.37},                        
    'models': {'loras': [LORA['file']]},
    'lora': LORA, 'steps': STEPS, 'cfg': CFG, 'pag': 3.0, 'seam_overlap': SEAM_OVERLAP,
    'schedule': "pick A's own: KSampler, 8 executed steps of int(8 / denoise)",
    'looks': LOOKS, 'max_factor': MAX_FACTOR,
    'speed_stack': True,
    'split_ok': False,                                           
    'build': _build,
}


INSTALLED = {'version': '5', 'recipe': 'R-own', 'offered': 'Only after the release proof gate and model checks pass.'}


SUPERSAMPLES = (2,)
REQUIRED_KEYS = ('name', 'version', 'proof', 'eta_factor', 'models', 'looks', 'max_factor', 'speed_stack', 'split_ok', 'build')
INFO_KEYS = ('render', 'output', 'factor', 'supersample', 'samplers', 'spot_options', 'speed_stack')

SIDECAR_KEYS = ('lora', 'steps', 'cfg', 'pag', 'seam_overlap', 'schedule')
LOOK_NAMES = ('Light', 'Default', 'Strong', 'Heavy', 'Extreme')     
FACTORS = (2, 4, 6, 8)                                               


class FastUnavailable(Exception):
    """Fast was asked for and no proven recipe is installed."""


class FastTooLarge(FastUnavailable):
    """Fast was asked for a stage at a supersample its recipe's proof did not render (an image too large for Fast; FC1)."""


def supersamples(recipe):
    """The supersamples a recipe's stage may run at: its own `supersamples`, else SUPERSAMPLES (as floats)."""
    return tuple(float(x) for x in recipe.get('supersamples', SUPERSAMPLES))


def _number(v, lo, hi):
    return not isinstance(v, bool) and isinstance(v, (int, float)) and lo < v <= hi


def check(recipe):
    """A recipe dict that can be used, or ValueError saying what is wrong with it (a half-installed recipe must not run)."""
    if not isinstance(recipe, dict):
        raise ValueError('the Fast recipe must be a dict')
    missing = [k for k in REQUIRED_KEYS if k not in recipe]
    if missing:
        raise ValueError('the Fast recipe lacks ' + ', '.join(missing))
    if not isinstance(recipe['name'], str) or not recipe['name'] or not isinstance(recipe['version'], str):
        raise ValueError('the Fast recipe needs a name and a version (strings)')
    if not _number(recipe['eta_factor'], 0, 2):
        raise ValueError('the Fast recipe needs a measured eta_factor (0 to 2)')
    ef = recipe.get('eta_factors')
    if ef is not None and (not isinstance(ef, dict) or not ef or not all(isinstance(k, str) and _number(v, 0, 2)
                                                                         for k, v in ef.items())):
        raise ValueError("the Fast recipe's eta_factors must be {stage kind: factor (0 to 2)}")
    if not isinstance(recipe['models'], dict) or not all(isinstance(v, (list, tuple)) for v in recipe['models'].values()):
        raise ValueError("the Fast recipe's models must be {folder: [file names]}")
    lora = recipe.get('lora')
    if lora is not None:
        if (not isinstance(lora, dict) or not isinstance(lora.get('file'), str) or not lora['file']
                or isinstance(lora.get('bytes'), bool) or not isinstance(lora.get('bytes'), int) or lora['bytes'] <= 0
                or not isinstance(lora.get('sha256'), str) or len(lora['sha256']) != 64
                or not _number(lora.get('strength'), 0, 4)):
            raise ValueError("the Fast recipe's lora must name its file, bytes, sha256 and strength")
        if not any(lora['file'] in v for v in recipe['models'].values()):
            raise ValueError("the Fast recipe's lora must be one of its models")
    looks = recipe['looks']
    if (not isinstance(looks, (list, tuple)) or not looks or len(set(looks)) != len(looks)
            or any(x not in LOOK_NAMES for x in looks)):
        raise ValueError("the Fast recipe's looks must name Looks from " + ', '.join(LOOK_NAMES))
    if recipe['max_factor'] not in FACTORS or isinstance(recipe['max_factor'], bool):
        raise ValueError("the Fast recipe's max_factor must be one of " + ', '.join(str(x) for x in FACTORS))
    if not isinstance(recipe['speed_stack'], bool) or not isinstance(recipe['split_ok'], bool):
        raise ValueError("the Fast recipe's speed_stack and split_ok must be true or false")
    ss = recipe.get('supersamples', SUPERSAMPLES)
    if (not isinstance(ss, (list, tuple)) or not ss or any(isinstance(x, bool) or x not in (2, 1.5, 1) for x in ss)):
        raise ValueError("the Fast recipe's supersamples must name supersamples from 2, 1.5 and 1")
    if not callable(recipe['build']):
        raise ValueError("the Fast recipe's build must be a function")
    return recipe


def recipe():
    """The installed recipe (checked), or None."""
    return None if RECIPE is None else check(RECIPE)


def installed():
    return RECIPE is not None


def describe():
    """What the service says about Fast before the model files are checked: {'installed', 'recipe', 'version', 'factor',
    'factors', 'split', 'speed_stack', 'models', 'lora', 'looks', 'max_factor', 'supersamples'}."""
    empty = {'installed': False, 'recipe': None, 'version': None, 'factor': None, 'factors': None, 'split': False,
             'speed_stack': None, 'models': {}, 'lora': None, 'looks': [], 'max_factor': None, 'supersamples': []}
    try:
        r = recipe()
    except ValueError as e:     
        return dict(empty, problem=str(e))
    if r is None:
        return empty
    factor = round(float(r['eta_factor']), 3)
    factors = {k: round(float(v), 3) for k, v in (r.get('eta_factors') or {'first_stage': factor}).items()}
    lora = r.get('lora')
    return {'installed': True, 'recipe': r['name'], 'version': r['version'], 'factor': factor, 'factors': factors,
            'split': bool(r['split_ok']), 'speed_stack': bool(r['speed_stack']),
            'models': {k: list(v) for k, v in r['models'].items()},
            'lora': None if lora is None else {k: lora[k] for k in ('file', 'bytes', 'sha256', 'strength')},
            'looks': list(r['looks']), 'max_factor': int(r['max_factor']), 'supersamples': list(supersamples(r))}


def sidecar_fields(r, info):
    """engine.fast of a Fast stage: the recipe's name and version, what it changes (SIDECAR_KEYS it names) and the ends its
    build placed (info['fast_ends'])."""
    out = {'recipe': r['name'], 'version': r['version']}
    for k in SIDECAR_KEYS:
        if k in r:
            v = r[k]
            out[k] = {x: v[x] for x in ('file', 'bytes', 'sha256', 'strength')} if k == 'lora' else v
    if info.get('fast_ends'):
        out['ends'] = dict(info['fast_ends'])
    return out


def build(input_name, w, h, params, prefix, f=2, s=2, live_preview=None):
    """The Fast stage graph for one stage: (graph, info). FastUnavailable when no recipe is installed; FastTooLarge for a
    stage at a supersample the recipe's proof did not render (SUPERSAMPLES; FC1)."""
    r = recipe()
    if r is None:
        raise FastUnavailable('no Fast recipe is installed')
    if float(s) not in supersamples(r):
        raise FastTooLarge(f'the Fast recipe was proven at supersample {", ".join(f"{x:g}" for x in supersamples(r))} '
                           f'only, not {float(s):g}')
    graph, info = r['build'](input_name, w, h, dict(params), prefix, f, s, live_preview)
    missing = [k for k in INFO_KEYS if k not in info]
    if missing:
        raise ValueError("the Fast recipe's build returned no " + ', '.join(missing))
    return graph, dict(info, fast=sidecar_fields(r, info))
