"""CUEncodePlane and CUDecodePlane: VAEEncodeTiled and VAEDecodeTiled (with the classic's ImageScale area and the finish's
8-bit step) on planes (engine design section 2.2 rows 8 and 10; B6; T2, T13).

CUEncodePlane (row 8). The classic VAEEncodeTiled (nodes.py) calls VAE.encode_tiled, which runs VAE.encode_tiled_
(comfy/sd.py:1210-1221): three tilings of the canvas, (tile, tile), (2 tile, tile / 2) and (tile / 2, 2 tile), summed in
that order (sd.py:1217-1220) and divided by 3, each by comfy.utils.tiled_scale. This node runs the same lines with ComfyUI's
own tiled_scale, unchanged; only the samples it is given differ: a handle on the canvas plane (PlaneSamples) whose windows
(`[b:b + 1]`, `narrow`) are read from the plane when the tile function asks for them. A window reaches the VAE as the
classic's does: float32 through the T2 table (engine/planes.U8_TO_F32, the classic's own float32(k) / 255) or the float32
plane at k = 4, NCHW-contiguous (the classic's canvas IMAGE is a BHWC view of NCHW memory, so its encode tiles are NCHW),
then process_input, the VAE dtype and the device, by the stock encode function. The latent is float32, whole, on the VAE's
output device (the CPU), as the classic's is. The encode state (T13, a plan constant) sets how the VAE is loaded first:
- 'resident': ComfyUI's load with a one-tile memory estimate (the largest tile of the three tilings); nothing is evicted
  when the VAE fits beside SDXL and the ControlNets;
- 'partial': the VAE in the state the classic leaves it in (its whole-canvas estimate makes ComfyUI load it with a 0.1-byte
  weight budget on NVIDIA, "loaded partially; 0.00 MB usable"), reached without evicting SDXL or the ControlNets;
- 'classic': the classic's own call, the whole-canvas estimate and its eviction.
Which state gives latents bit-equal to the classic's is a GPU question (R1); every state runs the same arithmetic.

CUDecodePlane (row 10). The classic VAEDecodeTiled calls VAE.decode_tiled_ (sd.py:1178-1190): three tilings of the latent,
((A + B) + C) / 3 with A = (tile / 2, 2 tile), B = (2 tile, tile / 2), C = (tile, tile) (sd.py:1185-1189), then
process_output; then ImageScale area to the stage output, then the finish's 8-bit step (q8, v4finish.quantize_8bit, applied
first by ClaudeV4Finish). This node runs each tiling as tiled_scale_multidim does (the same tile positions, the same feather
masks, contributions added to each pixel in the same tile order, then divided by the summed mask), but in rolling row
buffers: output rows are combined, scaled and stored as soon as no later tile of any tiling touches them. The three tilings
are decoded tile row by tile row, interleaved; every tile's input and every per-pixel sum is the classic's. The buffers are
allocated once and reused (_Tiling, decode_rows): the three tilings' accumulators and mask sums, (3.5 tile_size + 3 (p - 1))
render rows x 16 B, plus one chunk of at most EMIT_ROWS rows x 12 B, per render column (about 60 kB at tile 1024). Area runs on
bands aligned to the supersample (render rows a multiple of p and output rows of q for s = p / q), which gives every output
pixel the classic's own window. The stored bytes are q8's: np.clip(255 x, 0, 255).astype(uint8) of the classic's float, so the
finish reading them through the T2 table sees exactly what q8 gives it (G4). Written u8 [O] x 3 at <plane_dir>/<role>.plane."""
from . import _engine, PlaneRef, NotBuilt, _out, _progress, _RUN, _DIR, _classic_pack

ENCODE_STATES = ('resident', 'partial', 'classic')
PARTIAL_BUDGET = 0.1        # model_management.load_models_gpu's lowvram budget when the estimate exceeds the card (NVIDIA)


def _comfy():
    import comfy.model_management as mm
    import comfy.utils as cu
    return mm, cu


def check_vae(vae):
    """The VAEs this engine reproduces: an image VAE with 2-D latents and whole-number scale ratios that tiles through
    comfy.utils.tiled_scale (SDXL's). Anything else is refused in plain words."""
    vae.throw_exception_if_invalid()
    ok = (getattr(vae, 'latent_dim', None) == 2 and not getattr(vae, 'handles_tiling', False)
          and getattr(vae, 'extra_1d_channel', None) is None
          and isinstance(vae.downscale_ratio, int) and isinstance(vae.upscale_ratio, int)
          and not isinstance(vae.downscale_ratio, bool) and vae.downscale_ratio == vae.upscale_ratio)
    if not ok:
        raise ValueError('this VAE is not supported by the Large-image engine (it needs an image VAE such as SDXL\'s)')
    return vae.downscale_ratio


# --- encode -------------------------------------------------------------------------------------------------------------

class PlaneSamples:
    """The canvas plane as comfy.utils.tiled_scale sees `pixel_samples` ([1, 3, H, W]): `shape`, `[0:1]` and
    `narrow(dim, start, length)` give windows without reading; read() gives a window's pixels as the classic's tile has them
    (float32, NCHW-contiguous; u8 through the T2 table)."""

    def __init__(self, plane, y0=0, y1=None, x0=0, x1=None):
        self.plane = plane
        H, W = plane.shape[:2]
        self.y0, self.y1 = y0, H if y1 is None else y1
        self.x0, self.x1 = x0, W if x1 is None else x1
        self.reads = 0

    @property
    def shape(self):
        return (1, 3, self.y1 - self.y0, self.x1 - self.x0)

    def __getitem__(self, key):
        if key != slice(0, 1, None):
            raise TypeError('a canvas plane holds one image')
        return self

    def narrow(self, dim, start, length):
        if dim == 2:
            return PlaneSamples(self.plane, self.y0 + start, self.y0 + start + length, self.x0, self.x1)
        if dim == 3:
            return PlaneSamples(self.plane, self.y0, self.y1, self.x0 + start, self.x0 + start + length)
        raise TypeError(f'a canvas plane window narrows rows (2) or columns (3), not {dim}')

    def read(self):
        import numpy as np
        import torch
        crop = self.plane.read_region(self.x0, self.y0, self.x1, self.y1)[..., :3]
        a = _engine('planes').U8_TO_F32[crop] if crop.dtype == np.uint8 else crop.astype(np.float32, copy=False)
        return torch.from_numpy(np.ascontiguousarray(a)).permute(2, 0, 1).contiguous()[None]


def load_for_encode(vae, pixel_shape, tilings, state):
    """Load the VAE for the encode in the plan's encode state (module docstring)."""
    mm, _ = _comfy()
    if state == 'classic':
        memory_used = vae.memory_used_encode(pixel_shape, vae.vae_dtype)      # sd.py:1487, the whole canvas
        mm.load_models_gpu([vae.patcher], memory_required=memory_used, force_full_load=vae.disable_offload)
    elif state == 'resident':
        _, _, H, W = pixel_shape
        memory_used = max(vae.memory_used_encode((1, 3, min(H, ty), min(W, tx)), vae.vae_dtype) for (tx, ty) in tilings)
        mm.load_models_gpu([vae.patcher], memory_required=memory_used, force_full_load=vae.disable_offload)
    elif state == 'partial':
        load_partial(mm, vae.patcher)
    else:
        raise ValueError(f'encode_state must be one of {ENCODE_STATES} (got {state!r})')


def load_partial(mm, patcher):
    """The classic encode's VAE state without its eviction. The classic's whole-canvas estimate makes load_models_gpu free
    every model and then load the VAE with lowvram_model_memory 0 -> 0.1 (comfy/model_management.py:1020-1034;
    MIN_WEIGHT_MEMORY_RATIO is 0 on NVIDIA). Here only the VAE itself is unloaded, then loaded with that same budget, and
    registered as load_models_gpu registers it; free_memory is never called."""
    loaded = mm.LoadedModel(patcher)
    cur = mm.current_loaded_models
    if loaded in cur:
        cur.pop(cur.index(loaded)).model_unload()
    loaded.model_load(PARTIAL_BUDGET)
    cur.insert(0, loaded)


def encode_plane(vae, canvas_plane, tile_x, tile_y, overlap, state):
    """VAEEncodeTiled -> VAE.encode_tiled -> VAE.encode_tiled_ on a canvas plane; returns the latent tensor."""
    mm, cu = _comfy()
    ratio = check_vae(vae)
    H, W, C = canvas_plane.shape
    if C < 3:
        raise ValueError('CUEncodePlane needs an RGB canvas plane')
    if H % ratio or W % ratio:
        raise ValueError(f'the canvas ({W} x {H} px) must be a whole multiple of {ratio} px')     # vae_encode_crop_pixels
    pixel_samples = PlaneSamples(canvas_plane)
    tilings = ((tile_x, tile_y), (tile_x * 2, tile_y // 2), (tile_x // 2, tile_y * 2))
    load_for_encode(vae, pixel_samples.shape, tilings, state)
    with mm.cuda_device_context(vae.device):
        # VAE.encode_tiled_ (sd.py:1211-1221), with the window read where the stock function receives its tensor
        steps = pixel_samples.shape[0] * cu.get_tiled_scale_steps(pixel_samples.shape[3], pixel_samples.shape[2], tile_x, tile_y, overlap)
        steps += pixel_samples.shape[0] * cu.get_tiled_scale_steps(pixel_samples.shape[3], pixel_samples.shape[2], tile_x // 2, tile_y * 2, overlap)
        steps += pixel_samples.shape[0] * cu.get_tiled_scale_steps(pixel_samples.shape[3], pixel_samples.shape[2], tile_x * 2, tile_y // 2, overlap)
        pbar = cu.ProgressBar(steps)

        encode_fn = lambda a: vae.first_stage_model.encode((vae.process_input(a.read())).to(vae.vae_dtype).to(vae.device)).to(dtype=vae.vae_output_dtype())
        samples = cu.tiled_scale(pixel_samples, encode_fn, tile_x, tile_y, overlap, upscale_amount = (1/vae.downscale_ratio), out_channels=vae.latent_channels, output_device=vae.output_device, pbar=pbar)
        samples += cu.tiled_scale(pixel_samples, encode_fn, tile_x * 2, tile_y // 2, overlap, upscale_amount = (1/vae.downscale_ratio), out_channels=vae.latent_channels, output_device=vae.output_device, pbar=pbar)
        samples += cu.tiled_scale(pixel_samples, encode_fn, tile_x // 2, tile_y * 2, overlap, upscale_amount = (1/vae.downscale_ratio), out_channels=vae.latent_channels, output_device=vae.output_device, pbar=pbar)
        samples /= 3.0
    if vae.format_encoded is not None:
        samples = vae.format_encoded(samples)
    return samples


class CUEncodePlane:
    """VAEEncodeTiled from the canvas plane (module docstring); the latent whole on the CPU."""
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"canvas": ("PLANE",), "vae": ("VAE",),
                             "tile_size": ("INT", {"default": 512, "min": 64, "max": 4096, "step": 64}),
                             "overlap": ("INT", {"default": 64, "min": 0, "max": 4096, "step": 32}),
                             "encode_state": (list(ENCODE_STATES), {"default": "resident"})}}
    RETURN_TYPES = ("LATENT",)
    FUNCTION = "run"
    CATEGORY = "claude_banded"

    def run(self, canvas, vae, tile_size, overlap, encode_state='resident'):
        if encode_state not in ENCODE_STATES:
            raise ValueError(f'encode_state must be one of {ENCODE_STATES} (got {encode_state!r})')
        # VAEEncodeTiled.encode: vae.encode_tiled(pixels, tile_x=tile_size, tile_y=tile_size, overlap=overlap, ...)
        return ({"samples": encode_plane(vae, canvas.plane(), tile_size, tile_size, overlap, encode_state)},)


# --- decode -------------------------------------------------------------------------------------------------------------

def positions(n, tile, overlap):
    """tiled_scale_multidim's tile starts and lengths along one axis of n latent px: [(pos, l)]."""
    its = range(0, n - overlap, tile - overlap) if n > tile else [0]
    out = []
    for it in its:
        pos = max(0, min(n - overlap, it))
        out.append((pos, min(tile, n - pos)))
    return out


def feather_mask(torch, shape, feather, device):
    """tiled_scale_multidim's blend mask for one tile output of `shape` [1, C, h, w] (comfy/utils.py:1231-1240)."""
    mask = torch.ones([1, 1] + list(shape[2:]), device=device)
    for d in range(2, 4):
        if feather >= mask.shape[d]:
            continue
        for t in range(feather):
            a = (t + 1) / feather
            mask.narrow(d, t, 1).mul_(a)
            mask.narrow(d, mask.shape[d] - 1 - t, 1).mul_(a)
    return mask


EMIT_ROWS = 256        # render rows per decoded chunk at most (rounded up to a multiple of the supersample period)


def _buffer(torch, shape, device):
    """An uninitialised buffer of the default dtype (that of tiled_scale_multidim's output) on `device`. On the CPU it is
    numpy memory, from the C runtime heap, which returns a large block's commit to the system as soon as it is freed;
    torch's CPU allocator can keep freed blocks committed after the node returns. Values are unaffected: torch computes on
    the memory in place."""
    if torch.device(device).type == 'cpu' and torch.get_default_dtype() == torch.float32:
        import numpy as np
        return torch.from_numpy(np.empty(shape, np.float32))
    return torch.empty(shape, device=device)


class _Tiling:
    """One tiling of tiled_scale_multidim (2-D, tile = (tile_y, tile_x) latent px), run tile row by tile row into one rolling
    accumulator. Contributions reach each output pixel in the classic's tile order; rows are released (divided by the summed
    mask, in place) once no later tile row touches them, and handed out as views until they are taken.

    Memory: the accumulator (C channels) and the mask sum (1 channel) are allocated once, at the tallest tile row plus
    period - 1 rows, full render width, and reused: nothing is concatenated or cloned per step (a CPU allocator keeps the
    commit of freed blocks of changing sizes, which made the peak about three times the live rows). Buffer row 0 holds
    output row `org`; rows [base, top) are in use: [base, released) released and not yet taken, [released, top) still
    accumulating. A step first moves [base, top) to buffer row 0; decode_rows takes rows in step with the slowest tiling, so
    that move is at most the overlap plus period - 1 rows, and the tile row then fits (asserted)."""

    def __init__(self, torch, samples, fn, tile_x, tile_y, overlap, scale, channels, device, pbar, period=1):
        self.torch, self.samples, self.fn, self.device, self.pbar = torch, samples, fn, device, pbar
        self.scale, self.channels = scale, channels
        h, w = samples.shape[2], samples.shape[3]
        self.H, self.W = h * scale, w * scale
        self.single = h <= tile_y and w <= tile_x
        self.rows = positions(h, tile_y, overlap)
        self.cols = positions(w, tile_x, overlap)
        self.feather = round(scale * overlap)
        self.next_row = 0
        self.org = self.base = self.top = 0
        self.released = 0                   # output rows [0, released) are released
        if self.single:                     # tiled_scale_multidim's output tensor, the whole (one-tile) image
            self.acc, self.div = torch.empty((1, channels, self.H, self.W), device=device), None
        else:
            cap = min(self.H, max(l for _, l in self.rows) * scale + period - 1)
            self.acc = _buffer(torch, (1, channels, cap, self.W), device)
            self.div = _buffer(torch, (1, 1, cap, self.W), device)

    @property
    def done(self):
        return self.released >= self.H

    def _compact(self):
        """Move the rows in use [base, top) to buffer row 0, front to back in blocks no longer than the move (never an
        overlapping copy)."""
        d, k = self.base - self.org, self.top - self.base
        if d == 0:
            return
        i = 0
        while i < k:
            c = min(d, k - i)
            self.acc[:, :, i:i + c].copy_(self.acc[:, :, d + i:d + i + c])
            self.div[:, :, i:i + c].copy_(self.div[:, :, d + i:d + i + c])
            i += c
        self.org = self.base

    def step(self):
        """Decode the next tile row and release the rows that are final."""
        torch = self.torch
        if self.single:                                      # the whole latent fits one tile: the output is the tile itself
            self.acc[0:1] = self.fn(self.samples).to(self.device)
            self.pbar.update(1)
            self.top = self.released = self.H
            return
        j = self.next_row
        pos_y, l_y = self.rows[j]
        bot = (pos_y + l_y) * self.scale
        self._compact()
        if bot - self.org > self.acc.shape[2]:
            raise AssertionError(f'decode tile row {j} needs rows {self.org}-{bot}, over the {self.acc.shape[2]}-row buffer')
        if bot > self.top:                                   # rows first touched by this tile row start at zero
            self.acc[:, :, self.top - self.org:bot - self.org].zero_()
            self.div[:, :, self.top - self.org:bot - self.org].zero_()
            self.top = bot
        for (pos_x, l_x) in self.cols:
            s_in = self.samples.narrow(2, pos_y, l_y).narrow(3, pos_x, l_x)
            ps = self.fn(s_in).to(self.device)
            if ps.shape[2] != l_y * self.scale or ps.shape[3] != l_x * self.scale:
                raise AssertionError(f'a decoded tile of {tuple(ps.shape[2:])} px for a latent tile of {(l_y, l_x)}')
            mask = feather_mask(torch, ps.shape, self.feather, self.device)
            up_y, up_x = round(pos_y * self.scale), round(pos_x * self.scale)
            o = self.acc[:, :, up_y - self.org:bot - self.org, :]
            o_d = self.div[:, :, up_y - self.org:bot - self.org, :]
            ps_view, mask_view = ps, mask
            for d, up in ((0, 0), (1, up_x)):
                full = (o.shape[2] if d == 0 else self.W - up)
                ln = min(ps_view.shape[d + 2], full)
                o = o.narrow(d + 2, up, ln)
                o_d = o_d.narrow(d + 2, up, ln)
                if ln < ps_view.shape[d + 2]:
                    ps_view = ps_view.narrow(d + 2, 0, ln)
                    mask_view = mask_view.narrow(d + 2, 0, ln)
            o.add_(ps_view * mask_view)
            o_d.add_(mask_view)
            self.pbar.update(1)
        self.next_row += 1
        final = self.rows[self.next_row][0] * self.scale if self.next_row < len(self.rows) else self.H
        if final > self.released:
            a, b = self.released - self.org, final - self.org
            self.acc[:, :, a:b].div_(self.div[:, :, a:b])
            self.released = final

    def take(self, r0, r1):
        """Released rows [r0, r1) (normalized) as a view of the buffer, valid until this tiling's next step; the rows
        before r1 are no longer kept."""
        if r0 != self.base or r1 > self.released:
            raise AssertionError(f'decode rows {r0}-{r1} taken out of order (next {self.base}, released {self.released})')
        self.base = r1
        return self.acc[:, :, r0 - self.org:r1 - self.org]


def decode_rows(vae, samples, tile_x, tile_y, overlap, sink, period=1):
    """VAE.decode_tiled_ (sd.py:1178-1190) by output rows: sink(r0, rows) receives process_output(((A + B) + C) / 3.0) for
    render rows [r0, r0 + n), [1, C, n, W] on the VAE's output device, in order, each chunk's start and length (except the
    last) a multiple of `period`, n at most EMIT_ROWS rounded up to the period. `rows` is a view of one buffer that the next
    chunk overwrites: the sink uses or copies it before it returns. The sum is formed in that buffer as copy A, add B, add C,
    divide by 3.0 (the same float operations, in the same order, as the stock expression)."""
    import torch
    _, cu = _comfy()
    steps = samples.shape[0] * cu.get_tiled_scale_steps(samples.shape[3], samples.shape[2], tile_x, tile_y, overlap)
    steps += samples.shape[0] * cu.get_tiled_scale_steps(samples.shape[3], samples.shape[2], tile_x // 2, tile_y * 2, overlap)
    steps += samples.shape[0] * cu.get_tiled_scale_steps(samples.shape[3], samples.shape[2], tile_x * 2, tile_y // 2, overlap)
    pbar = cu.ProgressBar(steps)
    decode_fn = lambda a: vae.first_stage_model.decode(a.to(vae.vae_dtype).to(vae.device)).to(dtype=vae.vae_output_dtype())
    with torch.inference_mode():
        mk = lambda tx, ty: _Tiling(torch, samples, decode_fn, tx, ty, overlap, vae.upscale_ratio, vae.output_channels,
                                    vae.output_device, pbar, period)
        A, B, C = mk(tile_x // 2, tile_y * 2), mk(tile_x * 2, tile_y // 2), mk(tile_x, tile_y)
        H, W, ch = A.H, A.W, A.channels
        E = period * -(-EMIT_ROWS // period)
        emit = _buffer(torch, (ch * min(E, H) * W,), vae.output_device)     # flat: every chunk view is contiguous
        done = 0
        while done < H:
            t = min((x for x in (A, B, C) if not x.done), key=lambda x: x.released, default=None)
            if t is not None:
                t.step()
            upto = min(A.released, B.released, C.released)
            if upto < H:
                upto -= upto % period
            for r0 in range(done, upto, E):
                r1 = min(upto, r0 + E)
                out = emit[:ch * (r1 - r0) * W].view(1, ch, r1 - r0, W)
                out.copy_(A.take(r0, r1))
                out.add_(B.take(r0, r1))
                out.add_(C.take(r0, r1))
                out.div_(3.0)
                sink(r0, vae.process_output(out))
            done = max(done, upto)


def q8_u8(x):
    """The 8-bit value the finish's q8 gives a float (v4finish.quantize_8bit before its / 255): exact to store as u8."""
    import numpy as np
    return np.clip(255. * np.asarray(x, dtype=np.float32), 0, 255).astype(np.uint8)


def supersample(R_w, R_h, O_w, O_h):
    """s = render / output as a fraction p / q, the same on both axes (ImageScale area's ratio), or a refusal."""
    from fractions import Fraction
    sx, sy = Fraction(R_w, O_w), Fraction(R_h, O_h)
    if sx != sy or sx < 1:
        raise ValueError(f'the decoded render ({R_w} x {R_h}) is not the output ({O_w} x {O_h}) times one supersample >= 1')
    return sx


class CUDecodePlane:
    """VAEDecodeTiled + ImageScale area + the finish's 8-bit step, into a u8 plane (module docstring)."""
    @classmethod
    def INPUT_TYPES(cls):
        i = lambda d: ("INT", {"default": d, "min": 1, "max": 65536})
        return {"required": {"samples": ("LATENT",), "vae": ("VAE",),
                             "tile_size": ("INT", {"default": 512, "min": 64, "max": 4096, "step": 32}),
                             "overlap": ("INT", {"default": 64, "min": 0, "max": 4096, "step": 32}),
                             "width": i(1024), "height": i(1024), "role": (["creative", "structure"], {"default": "creative"}),
                             **_DIR, **_RUN}}
    RETURN_TYPES = ("PLANE",)
    FUNCTION = "run"
    CATEGORY = "claude_banded"

    def run(self, samples, vae, tile_size, overlap, width, height, role, plane_dir, run_id):
        if not plane_dir:
            raise ValueError('CUDecodePlane needs the stage plane folder')
        if role not in ('creative', 'structure'):
            raise ValueError(f'CUDecodePlane role must be creative or structure (got {role!r})')
        mm, cu = _comfy()
        planes = _engine('planes')
        ratio = check_vae(vae)
        # VAEDecodeTiled.decode (nodes.py)
        if tile_size < overlap * 4:
            overlap = tile_size // 4
        if vae.temporal_compression_decode() is not None:
            raise ValueError('a video VAE is not supported by the Large-image engine')
        latent = samples["samples"]
        if latent.is_nested:
            latent = latent.unbind()[0]
        if latent.ndim != 4 or latent.shape[0] != 1:
            raise ValueError('CUDecodePlane decodes one image latent')
        compression = vae.spacial_compression_decode()
        tile_x = tile_y = tile_size // compression
        ov = overlap // compression
        R_h, R_w = latent.shape[2] * ratio, latent.shape[3] * ratio
        s = supersample(R_w, R_h, width, height)
        p, q = s.numerator, s.denominator
        out = planes.Plane.create(_out(plane_dir, role), (height, width, 3), 'u8', producer=f'CUDecodePlane {role}',
                                  run_id=run_id)
        state = {'rows': 0}

        def sink(r0, rows):
            if s != 1:
                o0, n = r0 * q // p, rows.shape[2] * q // p
                rows = cu.common_upscale(rows, width, n, 'area', 'disabled')     # ImageScale area, on an aligned band
            else:
                o0 = r0
            u8 = q8_u8(rows.movedim(1, -1)[0].detach().cpu().float().numpy())
            if o0 != state['rows']:
                raise AssertionError('decode rows out of order')
            out.write_rows(o0, u8)
            state['rows'] = o0 + u8.shape[0]

        # VAE.decode_tiled (sd.py:1386-1406): the one-tile memory estimate, then decode_tiled_
        vae.throw_exception_if_invalid()
        memory_used = vae.memory_used_decode(vae._tile_bounded_shape(latent.shape, tile_x, tile_y, None), vae.vae_dtype)
        mm.load_models_gpu([vae.patcher], memory_required=memory_used, force_full_load=vae.disable_offload)
        with mm.cuda_device_context(vae.device):
            decode_rows(vae, latent, tile_x, tile_y, ov, sink, period=p)
        if state['rows'] != height:
            raise AssertionError(f'CUDecodePlane wrote {state["rows"]} of {height} rows')
        out.finish()
        return (PlaneRef(out.path, run_id),)
