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
Without the split the stage is one prompt (part None) ending in CUFinishBanded."""
from engine import graph_v5t
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
                       'island_after_lf'),
}
CHECKPOINT_ROLES = ('creative', 'structure', 'init', 'protect', 'release')


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


def build_stage(input_plane, w, h, params, prefix, plane_dir, run_id, f=2, s=2, constants=None, spot_options=None,
                creative_first=False, part=None, output_size=None):
    """One Large-image stage. input_plane: the service's padded stage-input plane (w x h). part: None (one prompt), 'A' or
    'B' (the split finish). output_size: the stage's cropped output (ow, oh); the finish writes exactly that. Returns (graph,
    info) with info as graph_v5t's plus 'planes' (role -> path) and 'part'."""
    if part not in (None, 'A', 'B'):
        raise ValueError(f'part must be None, A or B (got {part!r})')
    c = dict(constants or {})
    finish = c.get('finish', 'bxf-1')
    if finish not in FINISH_VARIANTS:
        raise ValueError(f'this build cannot make the finish variant {finish!r}')
    if c.get('canvas', 'lanczos-1') != 'lanczos-1' or c.get('recipe', 'r501') != 'r501':
        raise ValueError('this build makes the canvas lanczos-1 and the recipe r501 only')
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
        if c.get('brownian_cache', 45) != 45:
            spot['brownian_cache'] = int(c['brownian_cache'])
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
        g.add('CUFinishBanded', finish=finish, toe_amount=params['toe'][0], toe_scale=params['toe'][1], output_width=ow,
              output_height=oh, output_plane=planes['output'], filename_prefix=prefix, run_id=run_id, **fin_inputs)
    info = {'render': (rw, rh), 'output': (pow_, poh), 'stage_output': (ow, oh), 'factor': f, 'supersample': s,
            'samplers': info_samplers, 'run_order': ['detail', 'structure'] if creative_first else ['structure', 'detail'],
            'planes': planes, 'part': part, 'engine': 'banded', 'finish': finish}
    return g.nodes, info


def build_product(input_plane, w, h, params, prefix, plane_dir, run_id, f=2, s=2, constants=None, speed_stack=True,
                  live_preview=None, creative_first=False, faster=False, part=None, output_size=None):
    """build_stage with graph_v5t.product_options (the classic's own ClaudeSpotTiles options for these settings)."""
    opts = graph_v5t.product_options(speed_stack, live_preview, faster)
    graph, info = build_stage(input_plane, w, h, params, prefix, plane_dir, run_id, f=f, s=s, constants=constants,
                              spot_options=opts, creative_first=creative_first, part=part, output_size=output_size)
    return graph, dict(info, spot_options=opts, speed_stack=bool(speed_stack),
                       faster=dict(graph_v5t.FASTER_ON) if faster else None)


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
