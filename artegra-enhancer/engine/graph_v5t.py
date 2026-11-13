"""Graph v5t implementation."""


from engine.schedule import end_mid

MODELS = {
    'ckpt': 'juggernautXL_ragnarok.safetensors',
    'upscaler': '4xRealWebPhoto_v4_dat2.safetensors',
    'cn_tile': 'TTPLANET_Controlnet_Tile_realistic_v2_fp16.safetensors',
    'cn_line': 'mistoLine_fp16.safetensors',
    'sam': 'sam3.1_multiplex_fp16.safetensors',
}
DAT_TILES = {'tile': 512, 'margin': 64, 'blend': 16}
V4F = {'smooth_lo': 0.2, 'smooth_hi': 0.5, 'protect_dilate': 12, 'protect_feather': 4.0, 'islands': True, 'chroma_clamp': True,
       'quantize_8bit': True, 'keep_blacks': 'render', 'lf': 'hybmin', 'clamp': 'agree5', 'glow': 'skygaps'}
VAE_TILE = {'tile_size': 1024, 'overlap': 64, 'temporal_size': 64, 'temporal_overlap': 8}

SPOT_OPTIONS = {'window_split': bool, 'balance': str, 'weights': str, 'batch_windows': int, 'pag_fuse': bool, 'cn_reuse': bool,
                'noise_prefetch': bool, 'fp16_acc_scoped': bool, 'live_preview': str, 'cfg_end': float, 'pag_end': float}
LIVE_MODES = ('auto', 'off', 'rough', 'detailed', 'on', 'on_taesd')


SPEED_STACK_ON = {'noise_prefetch': True, 'pag_fuse': True, 'batch_windows': 2, 'fp16_acc_scoped': True}
SPEED_STACK_OFF = {'noise_prefetch': True}
PRODUCT_LIVE_MODES = ('rough', 'detailed')
PROOF_LIVE_MODES = ('off',)         


FASTER_ON = {'cfg_end': 0.7, 'pag_end': 0.6}


def check_spot_options(opts):
    """Validated copy of engine options for ClaudeSpotTiles ({} for None); raises ValueError on an unknown name or a bad value."""
    out = {}
    for k, v in (opts or {}).items():
        if k not in SPOT_OPTIONS:
            raise ValueError(f'unknown ClaudeSpotTiles option {k!r}')
        t = SPOT_OPTIONS[k]
        bad = ((t is bool and not isinstance(v, bool)) or (t is int and (isinstance(v, bool) or not isinstance(v, int)))
               or (t is str and not isinstance(v, str)) or (t is float and (isinstance(v, bool) or not isinstance(v, float))))
        if bad:
            raise ValueError(f'ClaudeSpotTiles option {k} must be {t.__name__} (got {v!r})')
        if k in ('cfg_end', 'pag_end') and not 0.0 <= v <= 1.0:
            raise ValueError(f'{k} must be between 0 and 1 (got {v!r})')
        if k == 'live_preview' and v not in LIVE_MODES:
            raise ValueError(f'live_preview must be one of {LIVE_MODES} (got {v!r})')
        if k == 'batch_windows' and not 1 <= v <= 16:
            raise ValueError(f'batch_windows must be 1 to 16 (got {v})')
        if k == 'balance' and v not in ('auto', 'queue', 'static'):
            raise ValueError(f'balance must be auto, queue or static (got {v!r})')
        out[k] = v
    return out


class G:
    def __init__(self):
        self.nodes = {}
        self._once = {}

    def once(self, cls, **inputs):
        """Loader nodes are shared by every stage of one graph (a second CheckpointLoaderSimple would load a second copy)."""
        key = (cls, tuple(sorted(inputs.items())))
        if key not in self._once:
            self._once[key] = self.add(cls, **inputs)
        return self._once[key]

    def add(self, cls, **inputs):
        nid = str(len(self.nodes) + 1)
        self.nodes[nid] = {'class_type': cls, 'inputs': {k: (v.ref(0) if isinstance(v, _Node) else v) for k, v in inputs.items()}}
        return _Node(nid)


class _Node:
    def __init__(self, nid):
        self.id = nid

    def ref(self, i):
        return [self.id, i]

    def out(self, i):
        return _Out(self.id, i)


class _Out(_Node):
    def __init__(self, nid, i):
        super().__init__(nid); self.i = i

    def ref(self, _):
        return [self.id, self.i]


def stage_sizes(w, h, f, s):
    rw, rh = w * f * s, h * f * s
    ow, oh = w * f, h * f
    for v, name in ((rw, 'render width'), (rh, 'render height')):
        if abs(v - round(v)) > 1e-9 or round(v) % 8:
            raise ValueError(f'{name} {v} must be a whole multiple of 8 (pad the stage input first)')
    for v, name in ((ow, 'output width'), (oh, 'output height')):
        if abs(v - round(v)) > 1e-9:
            raise ValueError(f'{name} {v} must be whole')
    return int(round(rw)), int(round(rh)), int(round(ow)), int(round(oh))


def build(input_name, w, h, params, prefix, f=2, s=2, v5t_finish=True, spot_options=None, creative_first=False):
    """One stage from an image in ComfyUI's input folder. params: engine.controls.resolve(...)[0] (or stage_params).
    v5t_finish=False gives the v5s finish (identity tests). spot_options: engine options for ClaudeSpotTiles (module docstring).
    creative_first: the detail (creative) pass is sampled first (module docstring, "Run order"). Returns (graph, info)."""
    if not isinstance(creative_first, bool):
        raise ValueError(f'creative_first must be true or false (got {creative_first!r})')
    g = G()
    _, info = _stage(g, input_name, w, h, params, prefix, f, s, v5t_finish, check_spot_options(spot_options), creative_first)
    return g.nodes, info


def product_options(speed_stack=True, live_preview=None, faster=False):
    """ClaudeSpotTiles inputs of a product stage. speed_stack on (the default): the trials' stack. Off: the noise prefetch
    only (the 9ea176c numbers; "Match earlier results"). live_preview: 'detailed', 'rough' or None (no preview input); 'off'
    only for the proof runs' no-feed reference (PROOF_LIVE_MODES). faster: FASTER_ON as well (only with the stack)."""
    if not isinstance(speed_stack, bool):
        raise ValueError(f'speed_stack must be true or false (got {speed_stack!r})')
    if not isinstance(faster, bool):
        raise ValueError(f'faster must be true or false (got {faster!r})')
    if faster and not speed_stack:
        raise ValueError('faster needs the speed stack ("Match earlier results" is off)')
    opts = dict(SPEED_STACK_ON if speed_stack else SPEED_STACK_OFF)
    if live_preview is not None:
        if live_preview not in PRODUCT_LIVE_MODES + PROOF_LIVE_MODES:
            raise ValueError(f'live_preview must be one of {PRODUCT_LIVE_MODES + PROOF_LIVE_MODES} or None (got {live_preview!r})')
        opts['live_preview'] = live_preview
    if faster:
        opts.update(FASTER_ON)
    return opts


def build_product(input_name, w, h, params, prefix, f=2, s=2, speed_stack=True, live_preview=None, creative_first=False,
                  faster=False):
    """The stage graph the product runs (service/runner.py calls exactly this for a Standard image): `build` with
    product_options(speed_stack, live_preview, faster) and the run order (creative_first, module docstring). Returns (graph,
    info); info['spot_options'] lists the engine options set, info['run_order'] the passes in the order ComfyUI runs them,
    info['faster'] the Faster inputs set (None without)."""
    opts = product_options(speed_stack, live_preview, faster)
    graph, info = build(input_name, w, h, params, prefix, f=f, s=s, spot_options=opts, creative_first=creative_first)
    return graph, dict(info, spot_options=opts, speed_stack=bool(speed_stack), faster=dict(FASTER_ON) if faster else None)


def build_chain(input_name, stages, v5t_finish=True, spot_options=None):
    """Several stages in ONE graph (farm validation only; the product runs one prompt per stage so it can pad, crop, resume
    and report progress between stages). stages: [(w, h, f, s, params, prefix)], each stage's (w, h) = the previous output."""
    g = G()
    src, infos = input_name, []
    opts = check_spot_options(spot_options)
    for (w, h, f, s, params, prefix) in stages:
        src, info = _stage(g, src, w, h, params, prefix, f, s, v5t_finish, opts)
        infos.append(info)
    return g.nodes, infos


def add_multigpu(graph, gpus, balance='auto', weights=''):
    """Graph v5t implementation."""


    if isinstance(gpus, bool) or not isinstance(gpus, int) or gpus < 1:
        raise ValueError(f'gpus must be a whole number >= 1 (got {gpus!r})')
    g = {k: {'class_type': v['class_type'], 'inputs': dict(v['inputs'])} for k, v in graph.items()}
    if gpus == 1:
        return g
    spots = [k for k, v in g.items() if v['class_type'] == 'ClaudeSpotTiles']
    if not spots:
        raise ValueError('graph has no ClaudeSpotTiles node')
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


def build_mask_preview(input_name, groups, protect, prefix):
    """SAM 3.1 protect masks for the UI preview and for term checks. groups: [(save_suffix, [terms])]; each group is saved as a
    white-on-black PNG (protected = white) named <prefix>_<suffix>. Raw union before the finish's dilate/feather."""
    g = G()
    pre = g.add('LoadImage', image=input_name)
    sam = g.once('CheckpointLoaderSimple', ckpt_name=MODELS['sam'])
    det = {}
    for suffix, terms in groups:
        masks = []
        for t in terms:
            if t not in det:
                cond = g.add('CLIPTextEncode', clip=sam.out(1), text=t)
                det[t] = g.add('SAM3_Detect', model=sam.out(0), image=pre, conditioning=cond, threshold=protect['threshold'],
                               refine_iterations=protect['refine_iterations'], individual_masks=False)
            masks.append(det[t])
        while len(masks) > 1:
            masks = [g.add('ClaudeMaskUnion', **{f'mask_{i + 1}': mk for i, mk in enumerate(masks[j:j + 8])})
                     for j in range(0, len(masks), 8)]
        img = g.add('MaskToImage', mask=masks[0])
        g.add('SaveImage', images=img, filename_prefix=f'{prefix}_{suffix}')
    return g.nodes


def sam_union(g, image, terms, sam_settings):
    """One CLIPTextEncode + SAM3_Detect per term on `image` (shared SAM 3.1 loader), unions of up to 8 (ClaudeMaskUnion)."""
    sam = g.once('CheckpointLoaderSimple', ckpt_name=MODELS['sam'])
    masks = []
    for t in terms:
        cond = g.add('CLIPTextEncode', clip=sam.out(1), text=t)
        masks.append(g.add('SAM3_Detect', model=sam.out(0), image=image, conditioning=cond, threshold=sam_settings['threshold'],
                           refine_iterations=sam_settings['refine_iterations'], individual_masks=False))
    while len(masks) > 1:  
        masks = [g.add('ClaudeMaskUnion', **{f'mask_{i + 1}': mk for i, mk in enumerate(masks[j:j + 8])})
                 for j in range(0, len(masks), 8)]
    return masks[0]


def build_gate_preview(input_name, protect_terms, release_terms, sam_settings, prefix):
    """The exact protect gate the finish applies (ClaudeProtectGate: union, dilate, feather, release carve-out) at the input's
    resolution, saved white = protected. For the UI preview and the GPU checks."""
    g = G()
    pre = g.add('LoadImage', image=input_name)
    gate_in = {'protect': sam_union(g, pre, protect_terms, sam_settings), 'dilate': sam_settings['dilate'],
               'feather': sam_settings['feather']}
    if release_terms:
        gate_in['release'] = sam_union(g, pre, release_terms, sam_settings)
    gate = g.add('ClaudeProtectGate', **gate_in)
    g.add('SaveImage', images=g.add('MaskToImage', mask=gate), filename_prefix=prefix)
    return g.nodes


def _stage(g, source, w, h, params, prefix, f, s, v5t_finish, spot_options=None, creative_first=False):
    """source: an input file name (LoadImage) or the IMAGE output node of a previous stage. creative_first: the finish's
    inputs keyed structure before creative, so ComfyUI samples the detail (creative) pass first (module docstring)."""
    rw, rh, ow, oh = stage_sizes(w, h, f, s)
    k = f * s
    ck = g.once('CheckpointLoaderSimple', ckpt_name=MODELS['ckpt'])
    m, clip, vae = ck.out(0), ck.out(1), ck.out(2)
    pag = g.add('PerturbedAttentionGuidance', model=m, scale=params['pag'])
    pos = g.add('CLIPTextEncode', clip=clip, text=params['prompt'])
    neg = g.add('CLIPTextEncode', clip=clip, text=params['negative'])
    pre = g.add('LoadImage', image=source) if isinstance(source, str) else source
    up = g.once('UpscaleModelLoader', model_name=MODELS['upscaler'])
    if params.get('dat_tiling', 'margin') == 'margin':  
        big = g.add('ClaudeUpscaleModelTiled', upscale_model=up, image=pre, **DAT_TILES)
    else:                                                
        big = g.add('ImageUpscaleWithModel', upscale_model=up, image=pre)            
    canvas = big if k == 4 else g.add('ImageScale', image=big, upscale_method='lanczos', width=rw, height=rh, crop='disabled')
    cn_t = g.once('ControlNetLoader', control_net_name=MODELS['cn_tile'])
    cn_l = g.once('ControlNetLoader', control_net_name=MODELS['cn_line'])
    hint = g.add('ImageBlur', image=canvas, blur_radius=int(round(k)), sigma=k / 2.0)   
    edges = g.add('ClaudeCannyTiled', image=canvas, low_threshold=0.2, high_threshold=0.45, tile=2048)
    sched, steps = params['scheduler'], params['steps']
    c1 = g.add('ControlNetApplyAdvanced', positive=pos, negative=neg, control_net=cn_t, image=hint, strength=params['tile'],
               start_percent=0.0, end_percent=end_mid(sched, steps, params['denoise'], params['tile_frac']), vae=vae)
    spot = {'clamp_blend': True} if params.get('spot_clamp_blend', True) else {}   
    spot.update(spot_options or {})                                                 
    model = g.add('ClaudeSpotTiles', model=pag, tile_px=params['tile_px'], seed=params['seed'], **spot)
    lat = g.add('VAEEncodeTiled', pixels=canvas, vae=vae, **VAE_TILE)
    ks1 = g.add('KSampler', model=model, positive=c1.out(0), negative=c1.out(1), latent_image=lat, seed=params['seed'],
                steps=steps, cfg=params['cfg'], sampler_name=params['sampler'], scheduler=sched, denoise=params['denoise'])
    raw = g.add('VAEDecodeTiled', samples=ks1, vae=vae, **VAE_TILE)
    c2 = g.add('ControlNetApplyAdvanced', positive=pos, negative=neg, control_net=cn_t, image=hint, strength=params['s_tile'],
               start_percent=0.0, end_percent=1.0, vae=vae)
    c3 = g.add('ControlNetApplyAdvanced', positive=c2.out(0), negative=c2.out(1), control_net=cn_l, image=edges,
               strength=params['s_line'], start_percent=0.0,
               end_percent=end_mid(sched, steps, params['structure'], params['s_line_frac']), vae=vae)
    ks2 = g.add('KSampler', model=model, positive=c3.out(0), negative=c3.out(1), latent_image=lat, seed=params['seed'],
                steps=steps, cfg=params['cfg'], sampler_name=params['sampler'], scheduler=sched, denoise=params['structure'])
    rawlo = g.add('VAEDecodeTiled', samples=ks2, vae=vae, **VAE_TILE)
    creative = g.add('ImageScale', image=raw, upscale_method='area', width=ow, height=oh, crop='disabled')
    structure = g.add('ImageScale', image=rawlo, upscale_method='area', width=ow, height=oh, crop='disabled')
    init = g.add('ImageScale', image=big, upscale_method='lanczos', width=ow, height=oh, crop='disabled')
    if creative_first:   
        fin_inputs = dict(structure=structure, creative=creative, init=init, pre=pre, **V4F)
    else:
        fin_inputs = dict(creative=creative, structure=structure, init=init, pre=pre, **V4F)
    terms = list(params['protect_terms'])
    if terms:
        fin_inputs['protect'] = sam_union(g, pre, terms, params['protect'])
        fin_inputs['protect_dilate'] = params['protect']['dilate']
        fin_inputs['protect_feather'] = params['protect']['feather']
        release = list(params.get('release_terms') or [])
        if release:
            fin_inputs['release'] = sam_union(g, pre, release, params['protect'])
    if v5t_finish:
        fin_inputs['fin_b0_hi'] = params['fin_b0_hi']
    if params.get('island_after_lf', True):   
        fin_inputs['island_after_lf'] = True
    fin = g.add('ClaudeV4Finish', **fin_inputs)
    out = g.add('ClaudeShadowToe', image=fin, amount=params['toe'][0], scale=params['toe'][1]) if v5t_finish else fin
    g.add('SaveImage', images=out, filename_prefix=prefix)
    return out, {'render': (rw, rh), 'output': (ow, oh), 'factor': f, 'supersample': s,
                 'samplers': {'structure': ks2.id, 'detail': ks1.id},
                 'run_order': ['detail', 'structure'] if creative_first else ['structure', 'detail']}
