"""The Large-image engine's stage graph (engine design section 2.2). graph_v5t.py is not edited; this builder makes the same
stage with the Large-image nodes (node_pack/claude_banded) in place of the whole-image ones, and keeps every classic input
value: the models, DAT_TILES, VAE_TILE, V4F, the protect settings, fin_b0_hi, the toe, the ControlNet strengths and end
percents, the run order and the ClaudeSpotTiles options (tests/test_graph_banded.py checks each against graph_v5t's graph for
the same stage).

Pixels live in planes on the work disk (engine/planes.py), named by role inside the stage's plane folder; every node takes
`run_id` (the prompt's own id) so ComfyUI's cache never hands a plane from one prompt to another.

With the finish split (lever L3r, a plan constant), the stage is two prompts:
  part 'A': everything up to the two decoded diffusion passes, `init` and the protect masks, ending in CUPlaneCheckpoint;
  part 'B': CUPlaneInput of those planes and the finish (CUFinishBanded), which has no model loader.
Without the split the stage is one prompt (part None) ending in CUFinishBanded.

Build wave 2 (5.0.2):
- the finish inputs (contract finish_inputs): every Large-image finish node takes 'band_gb', 'processes' and 'finish_tier' from
  the plan constants 'bxf_band_gb', 'bxf_processes' and 'finish_tier'; a graph built without those constants passes none, so it
  is the graph of the base. None of them is a pixel constant;
- banded Bolt (B16; contract bolt): a plan whose constants say mode 'bolt' and carry the installed Fast recipe's constant gets
  bolt_patch, a copy of engine/fast_recipe._build's patch values (BOLT), and the recipe's own stage options (the speed stack,
  no Faster, the structure pass first), as the classic Bolt stage has them. A recipe constant this build does not know is
  refused.

Build wave 3: a plan's capped Brownian cache reaches the fork only on schedules gate G7 compared (G7_SCHEDULES)."""
from engine import bands, graph_v5t
from engine.graph_v5t import DAT_TILES, MODELS, V4F, VAE_TILE, G, check_spot_options, stage_sizes
from engine.schedule import end_mid

SPOT_CLASS = 'ClaudeSpotTilesBanded'
OUTPUT_CLASSES = ('CUFinishBanded', 'CUPlaneCheckpoint')
CANNY = {'low_threshold': 0.2, 'high_threshold': 0.45, 'tile': 2048}
FINISH_VARIANTS = ('bxf-1',)
PLANE_MAX_SIDE = 65536

# The Large-image node classes: required inputs, outputs (the node pack declares exactly these; tests check both ways).
NODE_SPECS = {
    'CUPlaneInput': (('plane', 'run_id'), ('PLANE',)),
    'CUUpscaleCanvas': (('upscale_model', 'image', 'render_width', 'render_height', 'init_width', 'init_height', 'tile',
                         'margin', 'blend', 'canvas', 'plane_dir', 'run_id'), ('PLANE', 'PLANE')),
    'CUBlurPlane': (('canvas', 'blur_radius', 'sigma', 'plane_dir', 'run_id'), ('PLANE',)),
    'CUCannyPlane': (('canvas', 'low_threshold', 'high_threshold', 'tile', 'plane_dir', 'run_id'), ('PLANE',)),
    'CUControlNetApplyPlane': (('positive', 'negative', 'control_net', 'hint', 'strength', 'start_percent', 'end_percent',
                                'vae'), ('CONDITIONING', 'CONDITIONING')),
    'ClaudeSpotTilesBanded': (('model', 'tile_px', 'seed'), ('MODEL',)),
    'CUEncodePlane': (('canvas', 'vae', 'tile_size', 'overlap', 'encode_state'), ('LATENT',)),
    'CUDecodePlane': (('samples', 'vae', 'tile_size', 'overlap', 'width', 'height', 'role', 'plane_dir', 'run_id'), ('PLANE',)),
    'CUSam3DetectLean': (('model', 'image', 'conditioning', 'threshold', 'refine_iterations', 'plane_dir', 'run_id'),
                         ('PLANE',)),
    'CUMaskUnionPlane': (('plane_dir', 'run_id'), ('PLANE',)),
    'CUPlaneCheckpoint': (('filename_prefix', 'plane_dir', 'run_id'), ()),
    'CUFinishBanded': (('creative', 'structure', 'init', 'pre', 'smooth_lo', 'smooth_hi', 'protect_dilate',
                        'protect_feather', 'islands', 'chroma_clamp', 'finish', 'toe_amount', 'toe_scale', 'output_width',
                        'output_height', 'output_plane', 'filename_prefix', 'run_id'), ()),
}
NODE_OPTIONAL = {
    'ClaudeSpotTilesBanded': ('clamp_blend', 'window_split', 'balance', 'weights', 'batch_windows', 'pag_fuse', 'cn_reuse',
                              'noise_prefetch', 'fp16_acc_scoped', 'live_preview', 'seam_overlap', 'seam_dual', 'pag_end',
                              'cfg_end', 'brownian_cache'),
    'CUMaskUnionPlane': tuple(f'mask_{i}' for i in range(1, 9)),
    'CUPlaneCheckpoint': ('creative', 'structure', 'init', 'protect', 'release'),
    'CUFinishBanded': ('protect', 'release', 'quantize_8bit', 'keep_blacks', 'clamp', 'lf', 'glow', 'fin_b0_hi',
                       'island_after_lf', 'band_gb', 'processes', 'finish_tier'),
}
CHECKPOINT_ROLES = ('creative', 'structure', 'init', 'protect', 'release')

# The finish node's inputs from the plan constants (contract finish_inputs): (plan constant, node input), in node order.
FINISH_INPUTS = (('bxf_band_gb', 'band_gb'), ('bxf_processes', 'processes'), ('finish_tier', 'finish_tier'))
FINISH_TIERS = ('bxf', 'tier3')         # what a plan asks the node for ('ladder', the node's default, is never a plan's)

# Banded Bolt (B16): a COPY of engine/fast_recipe._build's patch values (tests/test_plan2_bolt.py checks it against that
# file's source, so a recipe change fails there). BOLT_RECIPE is the plan constant 'recipe' of a Bolt plan.
BOLT = {'recipe': 'H8-e8-s25-c5-p3-k+so16+stk', 'version': '1', 'lora': 'Hyper-SDXL-8steps-CFG-lora.safetensors',
        'strength': 0.25, 'steps': 8, 'cfg': 5.0, 'seam_overlap': 16, 'scheduler': 'karras', 'max_factor': 2,
        'supersamples': (2.0,)}
BOLT_RECIPE = f"{BOLT['recipe']}@{BOLT['version']}"
RECIPES = {'redux': 'r501', 'bolt': BOLT_RECIPE}

# Build wave 3: the schedules gate G7 compared with the Brownian cache at 8 (tools/gate_g7.py on the worker runtime; the
# verdicts are tests/fixtures/plan2_g7_runtime.json, plan3_g7_redux_looks.json and plan3_g7_bolt.json), by executed steps:
# KSampler's karras schedule is fixed by n = int(steps / denoise) (steps itself at denoise 1.0). A stage passes a plan's
# capped brownian_cache to the fork only when both its samplers' schedules are among them (every Look's, Redux and Bolt); a
# schedule G7 did not compare (a Custom recipe's) keeps torchsde's own 45. Only the expected memory figure counts the cap.
G7_SCHEDULES = {30: frozenset({30, 44, 46, 48, 49, 50, 51, 52, 53, 54, 55, 58, 62, 68, 69, 70}), 8: frozenset({13, 14, 15, 18})}


def g7_schedule(steps, denoise):
    """The karras schedule's n of a sampler of `steps` executed steps at `denoise` (KSampler.set_steps; gate_g7.schedule)."""
    return int(steps) if denoise is None or float(denoise) > 0.9999 else int(int(steps) / float(denoise))


def brownian_cache_for(constants, params, mode='redux'):
    """The brownian_cache a stage's fork takes: the plan constant where G7 compared both samplers' schedules, else 45."""
    cap = int((constants or {}).get('brownian_cache', 45))
    if cap == 45:
        return 45
    steps = BOLT['steps'] if mode == 'bolt' else int(params['steps'])
    seen = G7_SCHEDULES.get(int(steps), frozenset())
    return cap if all(g7_schedule(steps, params[k]) in seen for k in ('denoise', 'structure')) else 45


def plane_path(plane_dir, role):
    return f'{plane_dir}/{role}.plane'


def _sam(g, pre, terms, sam_settings, plane_dir, run_id, role):
    sam = g.once('CheckpointLoaderSimple', ckpt_name=MODELS['sam'])
    masks = []
    for i, t in enumerate(terms):
        cond = g.add('CLIPTextEncode', clip=sam.out(1), text=t)
        masks.append(g.add('CUSam3DetectLean', model=sam.out(0), image=pre, conditioning=cond,
                           threshold=sam_settings['threshold'], refine_iterations=sam_settings['refine_iterations'],
                           plane_dir=f'{plane_dir}/{role}{i}', run_id=run_id))
    level = 0
    while len(masks) > 1:
        masks = [g.add('CUMaskUnionPlane', plane_dir=f'{plane_dir}/{role}u{level}_{j}', run_id=run_id,
                       **{f'mask_{i + 1}': mk for i, mk in enumerate(masks[j:j + 8])}) for j in range(0, len(masks), 8)]
        level += 1
    return masks[0]


def finish_inputs(constants):
    """The finish node's 'band_gb', 'processes' and 'finish_tier' from the plan constants (contract finish_inputs): all three,
    or {} for a plan that has none of them (the base's graph). An incomplete set or a value outside the registered sets
    (engine/bands.py BAND_BUDGETS_GB and PROCESS_COUNTS; the tiers 'bxf' and 'tier3') is refused."""
    c = constants or {}
    present = [k for k, _ in FINISH_INPUTS if k in c]
    if not present:
        return {}
    if len(present) != len(FINISH_INPUTS):
        raise ValueError('the plan constants name only ' + ', '.join(present) + ' of ' + ', '.join(k for k, _ in FINISH_INPUTS))
    band, procs, tier = (c[k] for k, _ in FINISH_INPUTS)
    if isinstance(band, bool) or not isinstance(band, (int, float)) or float(band) not in bands.BAND_BUDGETS_GB:
        raise ValueError(f'band budget {band!r} GiB is not a registered budget {bands.BAND_BUDGETS_GB}')
    if isinstance(procs, bool) or not isinstance(procs, int) or procs not in bands.PROCESS_COUNTS:
        raise ValueError(f'process count {procs!r} is not a registered count {bands.PROCESS_COUNTS}')
    if tier not in FINISH_TIERS:
        raise ValueError(f'finish tier {tier!r} is not one a plan asks for {FINISH_TIERS}')
    return {'band_gb': float(band), 'processes': int(procs), 'finish_tier': tier}


def stage_mode(constants):
    """'redux' or 'bolt' from the plan constants, after checking their recipe is the one this build makes for that mode
    ('r501' for Redux, BOLT_RECIPE for Bolt); ValueError otherwise."""
    c = constants or {}
    mode = c.get('mode', 'redux')
    if mode not in RECIPES:
        raise ValueError(f'this build makes the modes redux and bolt only (got {mode!r})')
    recipe = c.get('recipe', 'r501' if mode == 'redux' else None)
    if recipe != RECIPES[mode]:
        raise ValueError(f'this build makes the {mode} recipe {RECIPES[mode]} only (got {recipe!r})')
    return mode


def bolt_patch(g, info, params):
    """engine/fast_recipe._build's patch, a copy of its values (BOLT), on a Large-image stage graph, in place: the LoRA
    (LoraLoaderModelOnly) on the checkpoint's model with the recipe's file and strength, PAG's model from it, the spot fork's
    seam_overlap, both samplers at the recipe's steps and CFG, and the end percent of the ControlNet each sampler's positive
    comes from, by schedule.end_mid for the recipe's steps. info: the stage's info (its 'samplers'). Returns the ends placed,
    by role (fast_recipe's 'fast_ends')."""
    nid = lambda: str(max(int(k) for k in g) + 1)
    ck = next(k for k, n in g.items() if n['class_type'] == 'CheckpointLoaderSimple'
              and n['inputs']['ckpt_name'] == MODELS['ckpt'])
    pag = next(k for k, n in g.items() if n['class_type'] == 'PerturbedAttentionGuidance')
    spot = next(k for k, n in g.items() if n['class_type'] == SPOT_CLASS)
    lora = nid()
    g[lora] = {'class_type': 'LoraLoaderModelOnly', 'inputs': {'model': [ck, 0], 'lora_name': BOLT['lora'],
                                                                'strength_model': BOLT['strength']}}
    g[pag]['inputs']['model'] = [lora, 0]
    g[spot]['inputs']['seam_overlap'] = BOLT['seam_overlap']
    ends = {}
    for role, d, frac in (('detail', params['denoise'], params['tile_frac']),
                          ('structure', params['structure'], params['s_line_frac'])):
        kid = info['samplers'][role]
        k = g[kid]['inputs']
        if g[kid]['class_type'] != 'KSampler' or k['scheduler'] != BOLT['scheduler'] or k['steps'] != params['steps']:
            raise ValueError('the Bolt patch needs the karras KSampler stage this build makes')
        k['steps'], k['cfg'] = BOLT['steps'], BOLT['cfg']
        cn = k['positive'][0]
        g[cn]['inputs']['end_percent'] = ends[role] = end_mid(BOLT['scheduler'], BOLT['steps'], d, frac)
    return ends


def build_stage(input_plane, w, h, params, prefix, plane_dir, run_id, f=2, s=2, constants=None, spot_options=None,
                creative_first=False, part=None, output_size=None):
    """One Large-image stage. input_plane: the service's padded stage-input plane (w x h). part: None (one prompt), 'A' or
    'B' (the split finish). output_size: the stage's cropped output (ow, oh); the finish writes exactly that. Returns (graph,
    info) with info as graph_v5t's plus 'planes' (role -> path) and 'part'. With Bolt's constants the stage is patched as the
    classic Bolt stage (bolt_patch; info 'fast_ends'); with the finish constants the finish node takes them (finish_inputs)."""
    if part not in (None, 'A', 'B'):
        raise ValueError(f'part must be None, A or B (got {part!r})')
    c = dict(constants or {})
    finish = c.get('finish', 'bxf-1')
    if finish not in FINISH_VARIANTS:
        raise ValueError(f'this build cannot make the finish variant {finish!r}')
    if c.get('canvas', 'lanczos-1') != 'lanczos-1':
        raise ValueError('this build makes the canvas lanczos-1 only')
    mode = stage_mode(c)
    fin_opt = finish_inputs(c)
    if mode == 'bolt' and (float(f) != 2.0 or float(s) not in BOLT['supersamples']):
        raise ValueError(f'Bolt makes 2x stages at supersample 2 only (got {float(f):g}x at {float(s):g})')
    rw, rh, pow_, poh = stage_sizes(w, h, f, s)
    ow, oh = output_size or (pow_, poh)
    for v in (rw, rh, pow_, poh):
        if v > PLANE_MAX_SIDE:
            raise ValueError(f'a plane side of {v} px is over {PLANE_MAX_SIDE}')
    k = f * s
    opts = check_spot_options(spot_options)
    g = G()
    planes = {r: plane_path(plane_dir, r) for r in ('canvas', 'init', 'hint', 'edges', 'creative', 'structure', 'output')}
    fin_extra = {}
    if part == 'B':
        pre = g.add('CUPlaneInput', plane=input_plane, run_id=run_id)
        creative = g.add('CUPlaneInput', plane=planes['creative'], run_id=run_id)
        structure = g.add('CUPlaneInput', plane=planes['structure'], run_id=run_id)
        init = g.add('CUPlaneInput', plane=planes['init'], run_id=run_id)
        if params['protect_terms']:
            fin_extra['protect'] = g.add('CUPlaneInput', plane=plane_path(plane_dir, 'protect'), run_id=run_id)
            if params.get('release_terms'):
                fin_extra['release'] = g.add('CUPlaneInput', plane=plane_path(plane_dir, 'release'), run_id=run_id)
        info_samplers = None
    else:
        ck = g.once('CheckpointLoaderSimple', ckpt_name=MODELS['ckpt'])
        m, clip, vae = ck.out(0), ck.out(1), ck.out(2)
        pag = g.add('PerturbedAttentionGuidance', model=m, scale=params['pag'])
        pos = g.add('CLIPTextEncode', clip=clip, text=params['prompt'])
        neg = g.add('CLIPTextEncode', clip=clip, text=params['negative'])
        pre = g.add('CUPlaneInput', plane=input_plane, run_id=run_id)
        up = g.once('UpscaleModelLoader', model_name=MODELS['upscaler'])
        if params.get('dat_tiling', 'margin') != 'margin':
            raise ValueError('the Large-image engine makes the margin-tiled x4 canvas only')
        cv = g.add('CUUpscaleCanvas', upscale_model=up, image=pre, render_width=rw, render_height=rh, init_width=pow_,
                   init_height=poh, canvas='lanczos-1', plane_dir=plane_dir, run_id=run_id, **DAT_TILES)
        canvas, init = cv.out(0), cv.out(1)
        cn_t = g.once('ControlNetLoader', control_net_name=MODELS['cn_tile'])
        cn_l = g.once('ControlNetLoader', control_net_name=MODELS['cn_line'])
        hint = g.add('CUBlurPlane', canvas=canvas, blur_radius=int(round(k)), sigma=k / 2.0, plane_dir=plane_dir, run_id=run_id)
        edges = g.add('CUCannyPlane', canvas=canvas, plane_dir=plane_dir, run_id=run_id, **CANNY)
        sched, steps = params['scheduler'], params['steps']
        c1 = g.add('CUControlNetApplyPlane', positive=pos, negative=neg, control_net=cn_t, hint=hint, strength=params['tile'],
                   start_percent=0.0, end_percent=end_mid(sched, steps, params['denoise'], params['tile_frac']), vae=vae)
        spot = {'clamp_blend': True} if params.get('spot_clamp_blend', True) else {}
        spot.update(opts)
        cache = brownian_cache_for(c, params, mode)
        if cache != 45:
            spot['brownian_cache'] = cache
        model = g.add(SPOT_CLASS, model=pag, tile_px=params['tile_px'], seed=params['seed'], **spot)
        lat = g.add('CUEncodePlane', canvas=canvas, vae=vae, tile_size=VAE_TILE['tile_size'], overlap=VAE_TILE['overlap'],
                    encode_state=c.get('encode_state', 'resident'))
        ks1 = g.add('KSampler', model=model, positive=c1.out(0), negative=c1.out(1), latent_image=lat, seed=params['seed'],
                    steps=steps, cfg=params['cfg'], sampler_name=params['sampler'], scheduler=sched, denoise=params['denoise'])
        creative = g.add('CUDecodePlane', samples=ks1, vae=vae, tile_size=VAE_TILE['tile_size'], overlap=VAE_TILE['overlap'],
                         width=pow_, height=poh, role='creative', plane_dir=plane_dir, run_id=run_id)
        c2 = g.add('CUControlNetApplyPlane', positive=pos, negative=neg, control_net=cn_t, hint=hint,
                   strength=params['s_tile'], start_percent=0.0, end_percent=1.0, vae=vae)
        c3 = g.add('CUControlNetApplyPlane', positive=c2.out(0), negative=c2.out(1), control_net=cn_l, hint=edges,
                   strength=params['s_line'], start_percent=0.0,
                   end_percent=end_mid(sched, steps, params['structure'], params['s_line_frac']), vae=vae)
        ks2 = g.add('KSampler', model=model, positive=c3.out(0), negative=c3.out(1), latent_image=lat, seed=params['seed'],
                    steps=steps, cfg=params['cfg'], sampler_name=params['sampler'], scheduler=sched,
                    denoise=params['structure'])
        structure = g.add('CUDecodePlane', samples=ks2, vae=vae, tile_size=VAE_TILE['tile_size'],
                          overlap=VAE_TILE['overlap'], width=pow_, height=poh, role='structure', plane_dir=plane_dir,
                          run_id=run_id)
        terms = list(params['protect_terms'])
        if terms:
            fin_extra['protect'] = _sam(g, pre, terms, params['protect'], plane_dir, run_id, 'protect')
            release = list(params.get('release_terms') or [])
            if release:
                fin_extra['release'] = _sam(g, pre, release, params['protect'], plane_dir, run_id, 'release')
        info_samplers = {'structure': ks2.id, 'detail': ks1.id}
    if part == 'A':
        g.add('CUPlaneCheckpoint', filename_prefix=prefix + '_a', plane_dir=plane_dir, run_id=run_id, creative=creative,
              structure=structure, init=init, **fin_extra)
    else:
        fin_inputs = (dict(structure=structure, creative=creative) if creative_first else dict(creative=creative,
                                                                                            structure=structure))
        fin_inputs.update(init=init, pre=pre, **V4F)
        fin_inputs.update(fin_extra)
        if fin_extra.get('protect') is not None:
            fin_inputs['protect_dilate'] = params['protect']['dilate']
            fin_inputs['protect_feather'] = params['protect']['feather']
        fin_inputs['fin_b0_hi'] = params['fin_b0_hi']
        if params.get('island_after_lf', True):
            fin_inputs['island_after_lf'] = True
        fin_inputs.update(fin_opt)                  # band_gb, processes, finish_tier: appended, only with the plan's constants
        g.add('CUFinishBanded', finish=finish, toe_amount=params['toe'][0], toe_scale=params['toe'][1], output_width=ow,
              output_height=oh, output_plane=planes['output'], filename_prefix=prefix, run_id=run_id, **fin_inputs)
    info = {'render': (rw, rh), 'output': (pow_, poh), 'stage_output': (ow, oh), 'factor': f, 'supersample': s,
            'samplers': info_samplers, 'run_order': ['detail', 'structure'] if creative_first else ['structure', 'detail'],
            'planes': planes, 'part': part, 'engine': 'banded', 'finish': finish}
    if mode == 'bolt':
        info['mode'] = 'bolt'
        if info_samplers is not None:               # prompt B of a split stage has no sampler to patch
            info['fast_ends'] = bolt_patch(g.nodes, info, params)
    return g.nodes, info


def build_product(input_plane, w, h, params, prefix, plane_dir, run_id, f=2, s=2, constants=None, speed_stack=True,
                  live_preview=None, creative_first=False, faster=False, part=None, output_size=None):
    """build_stage with graph_v5t.product_options (the classic's own ClaudeSpotTiles options for these settings). A Bolt
    plan's stage takes the recipe's own options whatever the caller asks, as fast_recipe._build's stage does (the speed stack,
    no Faster, the structure pass first), and its info carries fast_recipe's 'fast' sidecar fields."""
    bolt = stage_mode(constants) == 'bolt'
    if bolt:
        speed_stack, faster, creative_first = True, False, False
    opts = graph_v5t.product_options(speed_stack, live_preview, faster)
    graph, info = build_stage(input_plane, w, h, params, prefix, plane_dir, run_id, f=f, s=s, constants=constants,
                              spot_options=opts, creative_first=creative_first, part=part, output_size=output_size)
    info = dict(info, spot_options=opts, speed_stack=bool(speed_stack), faster=dict(graph_v5t.FASTER_ON) if faster else None)
    if bolt:
        from engine import fast_recipe
        r = fast_recipe.recipe()
        if r is None or f"{r['name']}@{r['version']}" != BOLT_RECIPE:
            raise ValueError(f'the installed Fast recipe is not {BOLT_RECIPE}, the one this build makes')
        info['spot_options'] = dict(opts, seam_overlap=BOLT['seam_overlap'])
        info['fast'] = fast_recipe.sidecar_fields(r, info)
    return graph, info


def add_multigpu(graph, gpus, balance='static', weights=''):
    """graph_v5t.add_multigpu for the fork's class name (two cards share the windows of one image; static split only)."""
    if isinstance(gpus, bool) or not isinstance(gpus, int) or gpus < 1:
        raise ValueError(f'gpus must be a whole number >= 1 (got {gpus!r})')
    if balance != 'static':
        raise ValueError('the Large-image engine splits the windows statically between cards')
    g = {k: {'class_type': v['class_type'], 'inputs': dict(v['inputs'])} for k, v in graph.items()}
    if gpus == 1:
        return g
    spots = [k for k, v in g.items() if v['class_type'] == SPOT_CLASS]
    if not spots:
        raise ValueError(f'graph has no {SPOT_CLASS} node')
    nxt = max(int(k) for k in g) + 1
    for sid in spots:
        g[sid]['inputs'].update(window_split=True, balance=balance, weights=weights)
        mg = str(nxt)
        nxt += 1
        g[mg] = {'class_type': 'MultiGPU_WorkUnits', 'inputs': {'model': [sid, 0], 'max_gpus': int(gpus)}}
        for k, v in g.items():
            if k == mg:
                continue
            for name, val in v['inputs'].items():
                if isinstance(val, list) and len(val) == 2 and val[0] == sid:
                    v['inputs'][name] = [mg, val[1]]
    return g


def classes():
    return sorted(NODE_SPECS)
