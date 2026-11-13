"""  init   implementation."""


import json
import math
import torch
from .imageops import creativity_map, lowfreq_transfer, detail_energy_cap, fin1


def _tiles(length, tile, overlap):
    if length <= tile:
        return [(0, length)]
    step = tile - overlap
    n = math.ceil((length - tile) / step) + 1
    span = length - tile
    starts = [round(i * span / (n - 1)) for i in range(n)]
    return [(s, s + tile) for s in starts]


def _ramp(idx, tiles, device):
    s, e = tiles[idx]
    m = torch.ones(e - s, device=device)
    if idx > 0:
        ov = tiles[idx - 1][1] - s
        if ov > 0:
            m[:ov] *= (torch.arange(ov, device=device) + 1) / (ov + 1)
    if idx < len(tiles) - 1:
        ov = e - tiles[idx + 1][0]
        if ov > 0:
            m[-ov:] *= torch.flip((torch.arange(ov, device=device) + 1) / (ov + 1), [0])
    return m


class ClaudeRegionCaptions:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "clip": ("CLIP",),
            "grid_json": ("STRING", {"multiline": True, "default": '{"cols":1,"rows":1,"captions":[["a photograph"]]}'}),
            "prefix": ("STRING", {"multiline": True, "default": ""}),
            "suffix": ("STRING", {"multiline": True, "default": ""}),
        }}
    RETURN_TYPES = ("CLAUDE_REGION_CONDS",)
    FUNCTION = "encode"
    CATEGORY = "claude_creative"

    def encode(self, clip, grid_json, prefix, suffix):
        g = json.loads(grid_json)
        cache, rows = {}, []
        for r in g["captions"]:
            row = []
            for text in r:
                full = " ".join(x for x in (prefix.strip(), text.strip(), suffix.strip()) if x)
                if full not in cache:
                    tokens = clip.tokenize(full)
                    cache[full] = clip.encode_from_tokens_scheduled(tokens)[0][0]
                row.append(cache[full])
            rows.append(row)
        return ({"cols": int(g["cols"]), "rows": int(g["rows"]), "conds": rows, "unique": len(cache)},)


class ClaudeRegionalTileModel:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "model": ("MODEL",),
            "region_conds": ("CLAUDE_REGION_CONDS",),
            "tile": ("INT", {"default": 128, "min": 32, "max": 1024, "step": 2}),
            "overlap": ("INT", {"default": 32, "min": 0, "max": 512, "step": 2}),
        }}
    RETURN_TYPES = ("MODEL",)
    FUNCTION = "patch"
    CATEGORY = "claude_creative"

    def patch(self, model, region_conds, tile, overlap):
        model = model.clone()
        cols, rows, conds = region_conds["cols"], region_conds["rows"], region_conds["conds"]

        def wrapper(apply_model, args):
            x, t, c = args["input"], args["timestep"], args["c"]
            H, W = x.shape[-2], x.shape[-1]
            ht, wt = _tiles(H, tile, overlap), _tiles(W, tile, overlap)
            out = torch.zeros_like(x); wsum = torch.zeros_like(x)
            base = c.get("c_crossattn")
            for hi, (h0, h1) in enumerate(ht):
                for wi, (w0, w1) in enumerate(wt):
                    ct = c.copy()
                    if base is not None:
                        r = min(rows - 1, int((h0 + h1) / 2 / H * rows)); q = min(cols - 1, int((w0 + w1) / 2 / W * cols))
                        e = conds[r][q].to(device=base.device, dtype=base.dtype)
                        ct["c_crossattn"] = e.expand(base.shape[0], -1, -1) if e.shape[0] == 1 else e
                    if ct.get("c_concat") is not None:
                        ct["c_concat"] = ct["c_concat"][..., h0:h1, w0:w1]
                    y = apply_model(x[..., h0:h1, w0:w1], t, **ct)
                    m = _ramp(hi, ht, x.device).view(-1, 1) * _ramp(wi, wt, x.device).view(1, -1)
                    m = m.view(*([1] * (x.ndim - 2)), h1 - h0, w1 - w0).to(x.dtype)
                    out[..., h0:h1, w0:w1] += y * m; wsum[..., h0:h1, w0:w1] += m
            return out / wsum.clamp_min(1e-6)

        model.set_model_unet_function_wrapper(wrapper)
        orig = model.model.memory_required

        def mem(input_shape, cond_shapes={}):
            s = list(input_shape); s[-2] = min(s[-2], tile); s[-1] = min(s[-1], tile)
            return orig(s, cond_shapes)
        model.model.memory_required = mem
        return (model,)


class ClaudeCreativityMap:
    @classmethod
    def INPUT_TYPES(cls):
        f = lambda d, lo=0.0, hi=1.0, st=0.01: ("FLOAT", {"default": d, "min": lo, "max": hi, "step": st})
        return {"required": {"image": ("IMAGE",), "lo": f(0.25), "hi": f(1.0), "coherence_k": f(0.6),
                             "gradient_sigma": f(1.5, 0.5, 8.0), "tensor_sigma": f(6.0, 1.0, 32.0, 0.5),
                             "feather": f(12.0, 0.0, 64.0, 0.5), "p_lo": f(0.25), "p_hi": f(0.85)},
                "optional": {"abs_hi": f(0.0, 0.0, 0.2, 0.001), "contrast_lo": f(0.0), "contrast_hi": f(1.0)}}
    RETURN_TYPES = ("MASK",)
    FUNCTION = "run"
    CATEGORY = "claude_creative"

    def run(self, image, lo, hi, coherence_k, gradient_sigma, tensor_sigma, feather, p_lo, p_hi, abs_hi=0.0, contrast_lo=0.0, contrast_hi=1.0):
        dev = image.device if image.is_cuda else (torch.device("cuda") if torch.cuda.is_available() else image.device)
        m = creativity_map(image[0].to(dev), lo=lo, hi=hi, gs=gradient_sigma, rs=tensor_sigma, p_lo=p_lo, p_hi=p_hi,
                           coh_k=coherence_k, feather=feather, abs_hi=abs_hi)
        if contrast_lo > 0.0 or contrast_hi < 1.0:  
            s = torch.clamp((m - contrast_lo) / max(contrast_hi - contrast_lo, 1e-3), 0, 1); m = s * s * (3 - 2 * s)
        return (m[None].cpu(),)


class ClaudeLowFreqTransfer:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"image": ("IMAGE",), "reference": ("IMAGE",),
                             "sigma": ("FLOAT", {"default": 24.0, "min": 1.0, "max": 256.0, "step": 0.5}),
                             "strength": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01})},
                "optional": {"robust": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.005})}}
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "run"
    CATEGORY = "claude_creative"

    def run(self, image, reference, sigma, strength, robust=0.0):
        if strength <= 0:
            return (image,)
        dev = torch.device("cuda") if torch.cuda.is_available() else image.device
        return (lowfreq_transfer(image.to(dev), reference.to(dev), sigma=sigma, strength=strength, robust=robust).cpu(),)


class ClaudeDetailEnergyCap:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"image": ("IMAGE",), "reference": ("IMAGE",),
                             "cap": ("FLOAT", {"default": 1.10, "min": 0.8, "max": 2.0, "step": 0.01}),
                             "min_scale": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01})}}
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "run"
    CATEGORY = "claude_creative"

    def run(self, image, reference, cap, min_scale):
        dev = torch.device("cuda") if torch.cuda.is_available() else image.device
        return (detail_energy_cap(image.to(dev), reference.to(dev), cap=cap, smin=min_scale).cpu(),)


class ClaudeFin1:
    """FIN-1 finish: per-band luma energy matched to ClearVision's measured range x the source's local band energy (dead-band),
    no 1-8 px gain on strong edges (removes halos/rings), finest-band polarity shaping, soft highlight shoulder.
    reference = the source upscaled to output size with Lanczos (or the PRE; it is resized bicubic)."""
    @classmethod
    def INPUT_TYPES(cls):
        f = lambda d, lo, hi, st=0.01: ("FLOAT", {"default": d, "min": lo, "max": hi, "step": st})
        return {"required": {"image": ("IMAGE",), "reference": ("IMAGE",), "kappa": f(0.12, 0.0, 0.5),
                             "iters": ("INT", {"default": 4, "min": 1, "max": 8}), "b0_lo": f(1.40, 0.8, 3.0), "b0_hi": f(2.10, 1.0, 3.5)},
                "optional": {"antiring_radius": ("INT", {"default": 0, "min": 0, "max": 8}), "antiring_tol": f(0.04, 0.0, 0.2),
                             "keep_blacks": f(0.0, 0.0, 1.0), "chroma": (["add", "mul"], {"default": "add"}),
                             "b0_flat_lo": f(0.0, 0.0, 3.0), "b0_flat_hi": f(0.0, 0.0, 3.5)}}
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "run"
    CATEGORY = "claude_creative"

    def run(self, image, reference, kappa, iters, b0_lo, b0_hi, antiring_radius=0, antiring_tol=0.04, keep_blacks=0.0, chroma="add",
            b0_flat_lo=0.0, b0_flat_hi=0.0):
        dev = torch.device("cuda") if torch.cuda.is_available() else image.device
        return (fin1(image.to(dev), reference.to(dev), kappa=kappa, iters=iters, b0=(b0_lo, b0_hi),
                     antiring=(antiring_radius, antiring_tol) if antiring_radius else None, keep_blacks=keep_blacks, chroma=chroma,
                     b0_flat=(b0_flat_lo, b0_flat_hi) if b0_flat_hi > 0 else None).cpu(),)


def _usdu():
    import nodes
    return nodes.NODE_CLASS_MAPPINGS["UltimateSDUpscaleNoUpscale"]


class ClaudeUSDUTileSeed:
    """UltimateSDUpscaleNoUpscale with a distinct deterministic seed per sampled tile (seed + 1000003 * k, k = sampling order).
    USDU samples every tile with the same seed, so initial and SDE noise repeat at the tile stride (FR1 S1 high-pass
    autocorrelation 0.030 at exactly 1024 px against ~0.001 at neighbouring shifts). Inputs are the wrapped node's."""
    @classmethod
    def INPUT_TYPES(cls):
        return _usdu().INPUT_TYPES()
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "upscale"
    CATEGORY = "claude_creative"

    def upscale(self, **kw):
        node = _usdu()
        g = node.upscale.__globals__["StableDiffusionProcessing"].__init__.__globals__  
        orig, k = g["sample"], [0]

        def sample(model, seed, *a, **kwa):
            s = (seed + 1000003 * k[0]) % 0xffffffffffffffff
            k[0] += 1
            return orig(model, s, *a, **kwa)
        g["sample"] = sample
        try:
            return node().upscale(**kw)
        finally:
            g["sample"] = orig


def tile_noise_mask(image_mask, blur, region, tile_size):
    """USDU tile mask (canvas-size 'L' image, tile rectangle white) -> latent noise mask for one crop: Gaussian blur (Pillow
    radius = sigma, as USDU's paste mask), crop to the processed region, resize to the processing size; shape (1, 1, H, W)."""
    from PIL import ImageFilter, Image
    import numpy as np
    m = image_mask.convert('L')
    if blur > 0:
        m = m.filter(ImageFilter.GaussianBlur(blur))
    m = m.crop(tuple(region))
    if m.size != tuple(tile_size):
        m = m.resize(tuple(tile_size), Image.BILINEAR)
    return torch.from_numpy(np.asarray(m, dtype=np.float32) / 255.0)[None, None]


class ClaudeUSDUFixedContext(ClaudeUSDUTileSeed):
    """ClaudeUSDUTileSeed with A1111-style fixed context. The ComfyUI USDU port denoises each whole crop (tile + padding) freely
    and pastes only the tile back through the blurred mask, so at every tile boundary two independent renders of the same
    pixels cross-fade (S1 v3g: 1-3 px energy on the y=1024 tile line 0.42x the far zone, ClearVision 0.88x; the round-4
    translucent ghost leaves sit on that line). Here each tile latent carries a noise mask (the tile mask blurred by
    context_blur, -1 = mask_blur), so the padding is held to the current canvas while the tile is denoised, as A1111's
    inpaint-only-masked tiles were. Per-tile seeds as ClaudeUSDUTileSeed; batch_size must be 1."""
    @classmethod
    def INPUT_TYPES(cls):
        t = {k: dict(v) for k, v in _usdu().INPUT_TYPES().items()}
        t.setdefault("optional", {})["context_blur"] = ("INT", {"default": -1, "min": -1, "max": 256, "step": 1})
        return t

    def upscale(self, context_blur=-1, **kw):
        if kw.get("batch_size", 1) != 1:
            raise ValueError("ClaudeUSDUFixedContext needs batch_size 1")
        node = _usdu()
        g = node.upscale.__globals__["StableDiffusionProcessing"].__init__.__globals__  
        orig = {n: g[n] for n in ("sample", "crop_cond", "process_images")}
        st = {"k": 0, "p": None, "region": None, "tile": None}

        def process_images(p):
            st["p"], st["region"] = p, None
            return orig["process_images"](p)

        def crop_cond(cond, region, init_size, canvas_size, tile_size, *a, **k2):
            st["region"], st["tile"] = region, tile_size
            return orig["crop_cond"](cond, region, init_size, canvas_size, tile_size, *a, **k2)

        def sample(model, seed, *a, **kwa):
            s = (seed + 1000003 * st["k"]) % 0xffffffffffffffff
            st["k"] += 1
            p, reg = st["p"], st["region"]
            if p is None or not isinstance(reg, tuple):
                raise RuntimeError("ClaudeUSDUFixedContext: tile region not captured")
            a = list(a)  
            a[6] = dict(a[6], noise_mask=tile_noise_mask(p.image_mask, p.mask_blur if context_blur < 0 else context_blur, reg, st["tile"]))
            return orig["sample"](model, s, *a, **kwa)
        g.update(sample=sample, crop_cond=crop_cond, process_images=process_images)
        try:
            return node().upscale(**kw)
        finally:
            g.update(orig)


class ClaudeUSDUSharedNoise(ClaudeUSDUTileSeed):
    """ClaudeUSDUTileSeed with canvas-shared noise (v5, 4 Nov 2026). Every tile takes its initial latent noise and its SDE
    per-step noise (the BrownianTreeNoiseSampler that dpmpp_*_sde builds per call) as crops of ONE canvas-wide field, indexed by
    the tile's absolute latent position: the initial field is randn from `seed`; each step's field is randn from a seed drawn
    from (`seed`, the step's order of first request), cached per (sigma, sigma_next), and every tile runs the same schedule.
    Overlapping tiles therefore see the same noise over the same init pixels, so the USDU paste cross-fades two renders of the
    same texture instead of two independent ones (raw passes: finest-band RMS dips to .61-.68 on tile lines, ~.707 for equal
    averaging of uncorrelated textures; Codex measured 30-69% less overlap disagreement with shared tile noise). Unit-variance
    i.i.d. increments are the same distribution the Brownian tree gives for one fixed schedule. batch_size must be 1."""

    def upscale(self, **kw):
        if kw.get("batch_size", 1) != 1:
            raise ValueError("ClaudeUSDUSharedNoise needs batch_size 1")
        import comfy.sample
        import comfy.k_diffusion.sampling as ks
        node = _usdu()
        g = node.upscale.__globals__["StableDiffusionProcessing"].__init__.__globals__  
        orig = {n: g[n] for n in ("sample", "crop_cond")}
        o_prep, o_bt = comfy.sample.prepare_noise, ks.BrownianTreeNoiseSampler
        img = kw["upscaled_image"]
        H, W, seed = -(-img.shape[1] // 8) + 8, -(-img.shape[2] // 8) + 8, int(kw["seed"])  
        st = {"region": None, "init": None, "steps": {}, "k": 0}

        def field(c, s):
            return torch.randn((1, c, H, W), generator=torch.Generator().manual_seed(s % 0x7fffffffffffffff), dtype=torch.float32)

        def crop(f, shape):
            x0, y0 = st["region"][0] // 8, st["region"][1] // 8
            h, w = shape[-2], shape[-1]
            if y0 + h > f.shape[-2] or x0 + w > f.shape[-1]:
                raise RuntimeError(f"ClaudeUSDUSharedNoise: tile {st['region']} {tuple(shape)} outside canvas field {tuple(f.shape)}")
            return f[:, :, y0:y0 + h, x0:x0 + w]

        def crop_cond(cond, region, *a, **k2):
            st["region"] = tuple(region)
            return orig["crop_cond"](cond, region, *a, **k2)

        def prepare_noise(latent_image, s, noise_inds=None):
            if st["region"] is None or getattr(latent_image, "is_nested", False) or latent_image.shape[0] != 1:
                raise RuntimeError("ClaudeUSDUSharedNoise: tile region not captured or batch != 1")
            if st["init"] is None or st["init"].shape[1] != latent_image.shape[1]:
                st["init"] = field(latent_image.shape[1], seed)
            return crop(st["init"], latent_image.shape).to(dtype=latent_image.dtype)

        class CanvasNoise:
            def __init__(self, x, sigma_min, sigma_max, seed=None, cpu=True, **k2):
                self.shape, self.device, self.dtype = x.shape, x.device, x.dtype

            def __call__(self, sigma, sigma_next):
                key = (round(float(sigma), 6), round(float(sigma_next), 6), self.shape[1])
                if key not in st["steps"]:
                    st["steps"][key] = field(self.shape[1], seed * 1000003 + 7919 * (len(st["steps"]) + 1))
                return crop(st["steps"][key], self.shape).to(self.device, self.dtype)

        def sample(model, s, *a, **kwa):
            st["k"] += 1
            return orig["sample"](model, s, *a, **kwa)
        g.update(sample=sample, crop_cond=crop_cond)
        comfy.sample.prepare_noise, ks.BrownianTreeNoiseSampler = prepare_noise, CanvasNoise
        try:
            return node().upscale(**kw)
        finally:
            g.update(orig)
            comfy.sample.prepare_noise, ks.BrownianTreeNoiseSampler = o_prep, o_bt


from .spot import _spot_weights, _spot_starts, ClaudeSpotTiles  


class ClaudeCannyTiled:
    """ComfyUI's Canny node (kornia.filters.canny: grey, Gaussian 5x5 sigma 1, Sobel, 8-direction NMS, low/high thresholds,
    8-connected hysteresis) in bounded memory (v5, 5 Nov 2026). SS9b: stock Canny on the 147 MP 4x S2 init needs ~15 GB of VRAM
    (8-channel NMS and hysteresis maps at full size) next to SDXL + two ControlNets, and stopped the RN2 job (GPU free < 256 MB);
    on WS it overflowed into shared memory. Here everything up to the thresholds runs per tile on the GPU with an 8 px margin
    (blur 2 + Sobel 1 + NMS 1 = 4 px reach; true image borders keep kornia's own padding), by calling kornia's canny with
    hysteresis off; hysteresis is done exactly on the CPU as its fixed point: keep every 8-connected component of the low mask
    that contains a high pixel (kornia's loop promotes weak pixels with a strong 8-neighbour until nothing changes). Output as the
    stock node: 0/1 edges, 3 channels, intermediate device/dtype."""
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"image": ("IMAGE",), "low_threshold": ("FLOAT", {"default": 0.4, "min": 0.01, "max": 0.99, "step": 0.01}),
                             "high_threshold": ("FLOAT", {"default": 0.8, "min": 0.01, "max": 0.99, "step": 0.01}),
                             "tile": ("INT", {"default": 2048, "min": 256, "max": 16384, "step": 64})}}
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "run"
    CATEGORY = "claude_creative"

    def run(self, image, low_threshold, high_threshold, tile=2048, device=None):
        import numpy as np
        from kornia.filters import canny
        from scipy.ndimage import label
        if device is None:
            import comfy.model_management as mm
            device, odev, odt = mm.get_torch_device(), mm.intermediate_device(), mm.intermediate_dtype()
        else:
            odev, odt = torch.device('cpu'), torch.float32
        B, H, W = image.shape[:3]
        M, outs = 8, []
        for b in range(B):
            low = np.zeros((H, W), bool); high = np.zeros((H, W), bool)
            for y0 in range(0, H, tile):
                for x0 in range(0, W, tile):
                    y1, x1 = min(H, y0 + tile), min(W, x0 + tile)
                    ya, xa, yb, xb = max(0, y0 - M), max(0, x0 - M), min(H, y1 + M), min(W, x1 + M)
                    t = image[b:b + 1, ya:yb, xa:xb, :3].to(device=device, dtype=torch.float32).movedim(-1, 1)
                    e = canny(t, low_threshold, high_threshold, hysteresis=False)[1][0, 0, y0 - ya:y1 - ya, x0 - xa:x1 - xa]
                    low[y0:y1, x0:x1] = (e > 0).cpu().numpy(); high[y0:y1, x0:x1] = (e == 1).cpu().numpy()
                    del t, e
            lab, n = label(low, structure=np.ones((3, 3), bool))
            keep = np.zeros(n + 1, bool); keep[np.unique(lab[high])] = True; keep[0] = False
            outs.append(torch.from_numpy(keep[lab]))
            del lab, low, high
        out = torch.stack(outs)[:, None].to(dtype=torch.float32)
        return (out.to(device=odev, dtype=odt).repeat(1, 3, 1, 1).movedim(1, -1),)


def _detail_sigma_schedule(n, amount, start, end, bias, exponent):
    """Per executed step k = 0..n-1: 0 outside [start, end] (fractions of the run), a cosine ramp up to `amount` at
    start + bias (end - start) and back down to 0 at end, each ramp raised to `exponent`."""
    import numpy as np
    m = np.zeros(n, dtype=np.float64)
    if n < 2 or amount == 0:
        return m
    s, e = sorted((float(start), float(end)))
    mid = s + float(bias) * (e - s)
    si, mi, ei = (int(round(v * (n - 1))) for v in (s, mid, e))
    m[si:mi + 1] = (0.5 * (1 - np.cos(np.linspace(0, 1, mi - si + 1) * np.pi))) ** exponent * amount
    m[mi:ei + 1] = (0.5 * (1 - np.cos(np.linspace(1, 0, ei - mi + 1) * np.pi))) ** exponent * amount
    return m


class ClaudeDetailSigma:
    """Under-reported sigma during the middle of the run (v5, 5 Nov 2026; own implementation of the idea of Detail Daemon by
    muerrilla, as ported to ComfyUI by Jonseed, MIT): the sampler keeps its true sigma schedule, but the model is told a slightly LOWER noise level, so it removes
    less of what it reads as noise and leaves finer texture. A PREDICT_NOISE wrapper (so CFG, PAG, ControlNets and
    ClaudeSpotTiles all see the same sigma): sigma_model = sigma x (1 - 0.1 x w(sigma) x cfg), w the _detail_sigma_schedule of
    the executed steps (transformer_options sample_sigmas; denoise < 1 runs schedule over the executed part only), interpolated
    between steps; cfg = cfg_scale, or the guider's cfg when 0 (Detail Daemon's scaling: amount .1 at CFG 6 = sigma x .94 at the
    peak). Outside the run's sigma range, or amount 0, the model is called unchanged."""
    @classmethod
    def INPUT_TYPES(cls):
        f = lambda d, lo, hi: ("FLOAT", {"default": d, "min": lo, "max": hi, "step": 0.01})
        return {"required": {"model": ("MODEL",), "amount": f(0.1, -1.0, 1.0), "start": f(0.2, 0.0, 1.0), "end": f(0.8, 0.0, 1.0),
                             "bias": f(0.5, 0.0, 1.0), "exponent": f(1.0, 0.0, 10.0), "cfg_scale": f(0.0, 0.0, 30.0)}}
    RETURN_TYPES = ("MODEL",)
    FUNCTION = "apply"
    CATEGORY = "claude_creative"

    def apply(self, model, amount, start, end, bias, exponent, cfg_scale):
        import comfy.patcher_extension as pe
        memo = {}

        def weight(sig, s):
            key = (tuple(round(float(v), 6) for v in sig.tolist()))
            if key not in memo:
                memo.clear(); memo[key] = _detail_sigma_schedule(len(sig) - 1, amount, start, end, bias, exponent)
            m = memo[key]; n = len(m)
            for i in range(n):
                hi, lo = float(sig[i]), float(sig[i + 1])
                if lo <= s <= hi:
                    t = 0.0 if hi == lo else (hi - s) / (hi - lo)
                    return float(m[i] * (1 - t) + m[min(i + 1, n - 1)] * t)
            return 0.0

        def wrap(executor, x, timestep, model_options={}, seed=None):
            sig = (model_options.get('transformer_options') or {}).get('sample_sigmas')
            if amount == 0 or sig is None or len(sig) < 3:
                return executor(x, timestep, model_options, seed)
            sig = sig.detach().float().cpu()
            s = float(timestep.max())
            if not (float(sig[-1]) <= s <= float(sig[0])):
                return executor(x, timestep, model_options, seed)
            cfg = float(cfg_scale) if cfg_scale > 0 else float(getattr(getattr(executor, 'class_obj', None), 'cfg', 1.0) or 1.0)
            adj = max(1e-6, 1.0 - 0.1 * weight(sig, s) * cfg)
            return executor(x, timestep * adj, model_options, seed)

        m = model.clone()
        m.add_wrapper_with_key(pe.WrappersMP.PREDICT_NOISE, "claude_detail_sigma", wrap)
        return (m,)


class ClaudeV4Finish:
    """V4 finish in one node (CPU numpy; v4finish.py, a bit-exact port of the offline lead v4stack variant v4n, and with `protect`
    of v4build variant v4b): creativity map from PRE (smoothstep smooth_lo..smooth_hi) x (1 - protect gate) -> composite of the
    creative / structure passes -> colour-novel hardware + litter islands revert to init -> hybrid robust LF (bicubic PRE) ->
    FIN-1.2 (Lanczos PRE) -> antiring agree2 / keep_blacks narrow / srcwarm -> warm-tight hue/chroma clamp.
    creative, structure, init: output size (2x); pre: the source (1x). protect: object union at PRE resolution (ClaudeMaskUnion of
    SAM3_Detect masks; batch = union), binarised at .5, dilated protect_dilate px and feathered (sigma protect_feather) here.
    quantize_8bit: inputs take the SaveImage -> PNG -> LoadImage 8-bit round trip (a no-op on loaded images) and the output is
    rounded to 8 bits as the offline stack writes it, so SaveImage of this output == the offline v4b / v4n PNG from the same passes.
    Optional stage switches (defaults = v4b): keep_blacks pre_narrow | render; lf hyb | hybmin (min-chroma hybrid LF); clamp lead |
    mm (mismatch-aware) | agree5 (structure-agreement gated, run on the 8-bit pre-clamp image in 1024-row strips); glow none |
    skygaps (bright rims in PRE sky gaps capped at PRE's local level; no-op without open sky). Candidate v4f = smooth .2-.5,
    keep_blacks render, lf hybmin, clamp agree5, glow skygaps (offline v4build v4f_nohc + v4final.py; v4finish.V4F)."""
    @classmethod
    def INPUT_TYPES(cls):
        f = lambda d, lo, hi, st=0.01: ("FLOAT", {"default": d, "min": lo, "max": hi, "step": st})
        return {"required": {"creative": ("IMAGE",), "structure": ("IMAGE",), "init": ("IMAGE",), "pre": ("IMAGE",),
                             "smooth_lo": f(0.3, 0.0, 1.0), "smooth_hi": f(0.6, 0.0, 1.0),
                             "protect_dilate": ("INT", {"default": 12, "min": 0, "max": 256}),
                             "protect_feather": f(4.0, 0.0, 64.0, 0.5),
                             "islands": ("BOOLEAN", {"default": True}), "chroma_clamp": ("BOOLEAN", {"default": True})},
                "optional": {"protect": ("MASK",), "quantize_8bit": ("BOOLEAN", {"default": True}),
                             "keep_blacks": (["pre_narrow", "render"], {"default": "pre_narrow"}),
                             "clamp": (["lead", "mm", "agree5"], {"default": "lead"}),
                             "lf": (["hyb", "hybmin"], {"default": "hyb"}),
                             "glow": (["none", "skygaps"], {"default": "none"}),
                             "fin_b0_hi": ("FLOAT", {"default": 2.4, "min": 1.6, "max": 1000.0, "step": 0.1}),
                             "release": ("MASK",), "island_after_lf": ("BOOLEAN", {"default": False})}}
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "run"
    CATEGORY = "claude_creative"

    def run(self, creative, structure, init, pre, smooth_lo, smooth_hi, protect_dilate, protect_feather, islands, chroma_clamp,
            protect=None, quantize_8bit=True, keep_blacks='pre_narrow', clamp='lead', lf='hyb', glow='none', fin_b0_hi=2.4,
            release=None, island_after_lf=False):
        import numpy as np
        from .v4finish import v4_finish, to_u8, quantize_8bit as q8
        if smooth_hi <= smooth_lo:
            raise ValueError("ClaudeV4Finish: smooth_hi must be > smooth_lo")
        glow = None if glow in (None, 'none') else glow
        pm, per_image = None, False
        if protect is not None:
            pm = protect.detach().cpu().float()
            pm = pm.reshape(-1, *pm.shape[-2:])
            per_image = pm.shape[0] == creative.shape[0] and pm.shape[0] > 1  
            pm = pm.numpy() if per_image else (pm.amax(0) if pm.shape[0] else pm.new_zeros(pm.shape[-2:])).numpy()
        rm = _mask_union_np(release) if (release is not None and pm is not None) else None  
        outs = []
        for i in range(creative.shape[0]):
            a = [t[min(i, t.shape[0] - 1)].detach().cpu().float().numpy()[..., :3] for t in (creative, structure, init, pre)]
            if quantize_8bit:
                a = [q8(x) for x in a]
            o = v4_finish(*a, pm[i] if per_image else pm, smooth=(smooth_lo, smooth_hi), protect_dilate=protect_dilate, protect_feather=protect_feather,
                          islands=islands, chroma_clamp=chroma_clamp, keep_blacks=keep_blacks, clamp=clamp, lf=lf, glow=glow,
                          fin_b0_hi=None if float(fin_b0_hi) == 2.4 else float(fin_b0_hi), release=rm,
                          island_after_lf=bool(island_after_lf))
            o = to_u8(o).astype(np.float32) / 255.0 if quantize_8bit else np.clip(o, 0, 1).astype(np.float32)
            outs.append(torch.from_numpy(np.ascontiguousarray(o)))
        return (torch.stack(outs, 0),)


def shadow_toe_u8(rgb_u8, a=0.40, s=0.06):
    """  init   implementation."""


    import numpy as np
    if a == 0:
        return rgb_u8
    x = rgb_u8.astype(np.float32) / 255
    L = 0.2126 * x[..., 0] + 0.7152 * x[..., 1] + 0.0722 * x[..., 2]
    L2 = L * (1 - a * np.exp(-L / s))
    r = np.where(L > 1e-4, L2 / np.maximum(L, 1e-4), 1.0)[..., None]
    return np.clip(np.round(x * r * 255), 0, 255).astype(np.uint8)


class ClaudeShadowToe:
    """v5t shadow toe (v5, 5 Nov 2026): deepens shadows towards ClearVision's black point without touching mid-tones, highlights
    or hue (blind judging marked v5s down for punch; ClearVision deepens p5 luma by 5-22% vs the source in every scene, v5s keeps
    the source blacks). Default a .40, s .06 (L .025 -> .019, .10 -> .093, .30 -> .2995). Input is treated as 8-bit (it follows
    ClaudeV4Finish with quantize_8bit); output is 8-bit quantised float."""
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"image": ("IMAGE",), "amount": ("FLOAT", {"default": 0.40, "min": 0.0, "max": 0.9, "step": 0.01}),
                             "scale": ("FLOAT", {"default": 0.06, "min": 0.005, "max": 0.5, "step": 0.005})}}
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "run"
    CATEGORY = "claude_creative"

    def run(self, image, amount, scale):
        import numpy as np
        outs = []
        for i in range(image.shape[0]):
            u8 = np.clip(np.round(image[i].detach().cpu().float().numpy()[..., :3] * 255), 0, 255).astype(np.uint8)
            o = shadow_toe_u8(u8, float(amount), float(scale)).astype(np.float32) / 255.0
            outs.append(torch.from_numpy(np.ascontiguousarray(o)))
        return (torch.stack(outs, 0),)


def margin_tiled_upscale(img, fn, scale, tile=512, margin=64, blend=16):
    """Seam-free tiled upscaling (Creative Upscaler app, 5 Nov 2026). img: [B, C, H, W] float; fn: [1, C, h, w] -> [1, C, h*scale,
    w*scale]. Each tile is evaluated with `margin` input px of real context on every side that has image beyond it; the margin's
    output is discarded and neighbouring tiles cross-fade over `blend` input px inside the kept cores, so no tile border (where a
    model sees padding instead of image) ever reaches the result. ComfyUI's ImageUpscaleWithModel uses tile 512 / overlap 32 with
    the cross-fade ending exactly where the next tile's border effects begin; on the APPV2 S4a crop that left a texture seam at
    output x 1024 (blind judges, 5 Nov). Images that fit in one tile are evaluated whole. Output on the input's device/dtype."""
    B, C, H, W = img.shape
    if H <= tile and W <= tile:
        return torch.cat([fn(img[b:b + 1]) for b in range(B)], 0)
    if tile <= 2 * margin + blend:
        raise ValueError('margin_tiled_upscale: tile must exceed 2 * margin + blend')
    core = tile - 2 * margin
    step = core - blend

    def starts(n):
        if n <= tile:
            return [0]
        s = list(range(0, n - core, step)) + [n - core]   
        return sorted(set(max(0, min(n - core, v)) for v in s))

    def ramp(n_core, at_lo, at_hi):
        w = torch.ones(n_core)
        r = torch.arange(1, blend + 1, dtype=torch.float32) / (blend + 1)
        if not at_lo:
            w[:blend] = r
        if not at_hi:
            w[-blend:] = torch.minimum(w[-blend:], r.flip(0))
        return w

    out = None
    wsum = torch.zeros((1, 1, H * scale, W * scale))
    ys, xs = starts(H), starts(W)
    for b in range(B):
        acc = None
        wsum.zero_()
        for y in ys:
            for x in xs:
                cy0, cy1 = (0, H) if H <= tile else (y, y + core)
                cx0, cx1 = (0, W) if W <= tile else (x, x + core)
                iy0, iy1, ix0, ix1 = max(0, cy0 - margin), min(H, cy1 + margin), max(0, cx0 - margin), min(W, cx1 + margin)
                o = fn(img[b:b + 1, :, iy0:iy1, ix0:ix1]).float().cpu()
                o = o[..., (cy0 - iy0) * scale:(cy1 - iy0) * scale, (cx0 - ix0) * scale:(cx1 - ix0) * scale]
                wy = ramp(cy1 - cy0, cy0 == 0 or H <= tile, cy1 == H or H <= tile).repeat_interleave(scale)
                wx = ramp(cx1 - cx0, cx0 == 0 or W <= tile, cx1 == W or W <= tile).repeat_interleave(scale)
                w = (wy[:, None] * wx[None, :])[None, None]
                if acc is None:
                    acc = torch.zeros((1, o.shape[1], H * scale, W * scale))
                acc[..., cy0 * scale:cy1 * scale, cx0 * scale:cx1 * scale] += o * w
                wsum[..., cy0 * scale:cy1 * scale, cx0 * scale:cx1 * scale] += w
        r = acc / wsum
        out = r if out is None else torch.cat([out, r], 0)
    return out.to(dtype=img.dtype)  


class ClaudeUpscaleModelTiled:
    """ImageUpscaleWithModel with seam-free margin tiling (margin_tiled_upscale): same model call as ComfyUI's node (model on the
    torch device, input moved channels-first, float, output clamped to [0, 1]); on out-of-memory the tile is halved (down to
    256) as the stock node does."""
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"upscale_model": ("UPSCALE_MODEL",), "image": ("IMAGE",),
                             "tile": ("INT", {"default": 512, "min": 256, "max": 4096, "step": 32}),
                             "margin": ("INT", {"default": 64, "min": 0, "max": 256}),
                             "blend": ("INT", {"default": 16, "min": 1, "max": 256})}}
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "run"
    CATEGORY = "claude_creative"

    def run(self, upscale_model, image, tile=512, margin=64, blend=16):
        import comfy.model_management as mm
        import comfy.utils
        
        device = upscale_model.patcher.load_device
        alpha = None
        if image.shape[-1] == 4:
            alpha, image = image[..., 3:4], image[..., :3]
        mem = (512 * 512 * 3) * image.element_size() * max(upscale_model.scale, 1.0) * 384.0 + image.nelement() * image.element_size()
        mm.load_models_gpu([upscale_model.patcher], memory_required=mem, force_full_load=True)
        x = image.movedim(-1, -3).to(device)
        scale = int(round(upscale_model.scale))
        while True:
            try:
                with torch.no_grad():
                    s = margin_tiled_upscale(x, lambda a: upscale_model(a.float()), scale, tile, margin, blend)
                break
            except Exception as e:
                mm.raise_non_oom(e)
                mm.soft_empty_cache()
                tile //= 2
                if tile < 256 or tile <= 2 * margin + blend:
                    raise e
        s = torch.clamp(s.movedim(-3, -1), min=0, max=1.0).to(device=mm.intermediate_device(), dtype=mm.intermediate_dtype())
        if alpha is not None:
            alpha = comfy.utils.common_upscale(alpha.movedim(-1, -3).to(s), s.shape[2], s.shape[1], "bilinear", "disabled")
            s = torch.cat((s, alpha.movedim(-3, -1)), dim=-1)
        return (s,)


def _mask_union_np(mask):
    """  init   implementation."""
    m = mask.detach().cpu().float()
    m = m.reshape(-1, *m.shape[-2:])
    return (m.amax(0) if m.shape[0] else m.new_zeros(m.shape[-2:])).numpy()


class ClaudeProtectGate:
    """The finish's protect gate at PRE resolution, for previews and checks (Creative Upscaler app, 5 Nov 2026): protect union
    binarised at .5, dilated `dilate` px, Gaussian sigma `feather`, then x (1 - release feathered) when a release mask is given;
    exactly v4finish.protect_gate before its bilinear resize to the output size. Output MASK [1, H, W] in [0, 1]."""
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"protect": ("MASK",), "dilate": ("INT", {"default": 12, "min": 0, "max": 256}),
                             "feather": ("FLOAT", {"default": 4.0, "min": 0.0, "max": 64.0, "step": 0.5})},
                "optional": {"release": ("MASK",)}}
    RETURN_TYPES = ("MASK",)
    FUNCTION = "run"
    CATEGORY = "claude_creative"

    def run(self, protect, dilate, feather, release=None):
        from .v4finish import protect_gate
        pm = _mask_union_np(protect)
        rm = _mask_union_np(release) if release is not None else None
        g = protect_gate(pm, pm.shape[0], pm.shape[1], int(dilate), float(feather), release=rm)
        return (torch.from_numpy(g.astype("float32"))[None],)


class ClaudeMaskUnion:
    """  init   implementation."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {}, "optional": {f"mask_{i}": ("MASK",) for i in range(1, 9)}}
    RETURN_TYPES = ("MASK",)
    FUNCTION = "run"
    CATEGORY = "claude_creative"

    def run(self, **masks):
        u = None
        for i in range(1, 9):
            m = masks.get(f"mask_{i}")
            if m is None:
                continue
            m = m.detach().cpu().float()
            m = m.reshape(-1, *m.shape[-2:])
            m = m.amax(0) if m.shape[0] else m.new_zeros(m.shape[-2:])  
            if u is not None and m.shape != u.shape:
                raise ValueError(f"ClaudeMaskUnion: mask_{i} is {tuple(m.shape)}, earlier masks {tuple(u.shape)}")
            u = m if u is None else torch.maximum(u, m)
        if u is None:
            raise ValueError("ClaudeMaskUnion: connect at least one mask")
        return (u[None],)


NODE_CLASS_MAPPINGS = {"ClaudeDetailEnergyCap": ClaudeDetailEnergyCap, "ClaudeRegionCaptions": ClaudeRegionCaptions, "ClaudeRegionalTileModel": ClaudeRegionalTileModel,
                       "ClaudeCreativityMap": ClaudeCreativityMap, "ClaudeLowFreqTransfer": ClaudeLowFreqTransfer, "ClaudeFin1": ClaudeFin1,
                       "ClaudeSpotTiles": ClaudeSpotTiles, "ClaudeDetailSigma": ClaudeDetailSigma, "ClaudeCannyTiled": ClaudeCannyTiled, "ClaudeShadowToe": ClaudeShadowToe, "ClaudeV4Finish": ClaudeV4Finish, "ClaudeMaskUnion": ClaudeMaskUnion, "ClaudeProtectGate": ClaudeProtectGate, "ClaudeUpscaleModelTiled": ClaudeUpscaleModelTiled}
NODE_DISPLAY_NAME_MAPPINGS = {"ClaudeDetailEnergyCap": "Detail Energy Cap (Claude)", "ClaudeRegionCaptions": "Region Captions (Claude)", "ClaudeRegionalTileModel": "Regional Tile Model (Claude)",
                              "ClaudeCreativityMap": "Creativity Map (Claude)", "ClaudeLowFreqTransfer": "Low-Frequency Transfer (Claude)",
                              "ClaudeFin1": "FIN-1 Finish (Claude)",
                              "ClaudeSpotTiles": "Shifted-Window Canvas Tiling (Claude)", "ClaudeDetailSigma": "Detail Sigma (Claude)", "ClaudeCannyTiled": "Canny, tiled (Claude)", "ClaudeShadowToe": "Shadow Toe (Claude)", "ClaudeV4Finish": "V4 Finish (Claude)",
                              "ClaudeMaskUnion": "Mask Union (Claude)", "ClaudeProtectGate": "Protect Gate (Claude)", "ClaudeUpscaleModelTiled": "Upscale Image (using Model), seam-free tiles (Claude)"}
