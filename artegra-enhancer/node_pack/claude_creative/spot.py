"""Spot implementation."""


import contextlib
import logging
import os
import threading
import time

import torch

SPOT_LISTENERS = []          
_EVAL_COUNTER = [0]
_SPEED = {}                  
_SPEED_LOCK = threading.Lock()
PAG_KEY = ("middle", 0)
_MG_KEYS = ('multigpu_clones', 'multigpu_thread_pool')


def sdp_state():
    """torch's process-wide attention settings: the four scaled-dot-product enable flags and the kernel priority order
    (backend numbers). None when this torch cannot report them."""
    try:
        from torch.backends import cuda as bc
        return (bool(bc.flash_sdp_enabled()), bool(bc.cudnn_sdp_enabled()), bool(bc.mem_efficient_sdp_enabled()),
                bool(bc.math_sdp_enabled()), tuple(int(x) for x in torch._C._get_sdp_priority_order()))
    except Exception:
        return None


def sdp_restore(before):
    """Spot implementation."""


    if before is None:
        return False
    now = sdp_state()
    if now is None or now == before:
        return False
    from torch.backends import cuda as bc
    bc.enable_flash_sdp(before[0])
    bc.enable_cudnn_sdp(before[1])
    bc.enable_mem_efficient_sdp(before[2])
    bc.enable_math_sdp(before[3])
    torch._C._set_sdp_priority_order(list(before[4]))
    logging.info('ClaudeSpotTiles: attention settings put back after the sampling run (found %s, wrote %s)', now, before)
    return sdp_state() == before


def to_device(t, device):
    """Copy a tensor to another card (exact). Module-level so the CPU tests can stand in for CUDA devices."""
    return t.to(device)


def on_device(t, device):
    return t.device == device


def set_device(device):
    """torch.cuda.set_device for a CUDA device (called at the start of every worker thread's loop); no-op otherwise."""
    if getattr(device, 'type', None) == 'cuda':
        torch.cuda.set_device(device)


def _strip(model_options):
    return {k: v for k, v in model_options.items() if k not in _MG_KEYS}


def _spot_weights(starts, t, n):
    """Per-window blend weights along one axis (clamp_blend, Creative Upscaler app 5 Nov 2026). Where two windows overlap (only the
    clamped edge windows do), the earlier one ramps down and the later one ramps up linearly across the overlap, so the weights
    sum to 1 and change smoothly. Plain averaging (the original behaviour) switches from 1/2 to 1 at the clamped window's edge,
    which sits at the same canvas position on every step (latent t and n - t) and printed a seam there (APPV2 S4a seat, output
    x 1024 of a 3072 px canvas)."""
    w = min(t, n)
    out = []
    for i, a in enumerate(starts):
        v = torch.ones(w)
        if i > 0:
            ov = starts[i - 1] + w - a
            if ov > 0:
                v[:ov] = (torch.arange(ov, dtype=torch.float32) + 0.5) / ov
        if i < len(starts) - 1:
            ov = a + w - starts[i + 1]
            if ov > 0:
                v[w - ov:] = torch.minimum(v[w - ov:], (ov - 0.5 - torch.arange(ov, dtype=torch.float32)) / ov)
        out.append(v)
    return out


def _spot_starts(n, t, d):
    """Window starts covering [0, n) with windows of t latent px on a grid shifted by -d; edge windows clamp inside the canvas."""
    if n <= t:
        return [0]
    out, s = [], -d
    while s < n:
        c = min(max(s, 0), n - t)
        if not out or out[-1] != c:
            out.append(c)
        s += t
    return out


def spot_offsets(seed, timestep, T):
    """The grid shift of one evaluation (unchanged from 9ea176c): a CPU generator seeded from (seed, sigma)."""
    return _offsets(seed, float(timestep.flatten()[0]), T)


def _offsets(seed, sigma, T):
    g = torch.Generator().manual_seed((int(seed) * 1000003 + int(round(sigma * 1e4))) % 0x7fffffffffffffff)
    dy, dx = (int(v) for v in torch.randint(0, T, (2,), generator=g))
    return dy, dx


def window_list(H, W, T, dy, dx):
    """(ys, xs, windows) with windows in the 9ea176c evaluation order: row-major, (iy, ix, y0, x0, h1, w1)."""
    ys, xs = _spot_starts(H, T, dy), _spot_starts(W, T, dx)
    h1, w1 = min(T, H), min(T, W)
    return ys, xs, [(iy, ix, y0, x0, h1, w1) for iy, y0 in enumerate(ys) for ix, x0 in enumerate(xs)]


def _seam_starts(n, t, d, ov):
    """Window starts covering [0, n) with windows of t latent px on a grid of stride t - ov shifted by -d (0 <= d < t - ov).
    Edge windows clamp inside the canvas, so every pair of neighbours overlaps by at least ov. With ov 0 this is _spot_starts."""
    if n <= t:
        return [0]
    stride = t - ov
    out, s = [], -d
    while True:
        c = min(max(s, 0), n - t)
        if not out or out[-1] != c:
            out.append(c)
        if s + t >= n:       
            break
        s += stride
    return out


def _seam_weights(starts, t, n):
    """_spot_weights (a linear ramp across every overlap of neighbours), then normalised along the axis: the weights sum to 1
    at every latent pixel also where three windows meet (a clamped edge window, its neighbour and the one after)."""
    raw = _spot_weights(starts, t, n)
    w = min(t, n)
    tot = torch.zeros(n)
    for a, v in zip(starts, raw):
        tot[a:a + w] += v
    return [v / tot[a:a + w] for a, v in zip(starts, raw)]


def _tent_weights(starts, t, n, r=None):
    """Per-window weight along one axis for a blend of two shifted grids: 0 at the window's own edge, rising linearly over r
    latent px (default half a window) to 1; no ramp at a canvas border. Not normalised: the blend divides by the weight sum."""
    w = min(t, n)
    r = float(r if r else max(w // 2, 1))
    k = torch.arange(w, dtype=torch.float32)
    up = torch.clamp((k + 0.5) / r, max=1.0)
    down = torch.clamp((w - 0.5 - k) / r, max=1.0)
    out = []
    for a in starts:
        v = torch.ones(w)
        if a > 0:
            v = torch.minimum(v, up)
        if a + w < n:
            v = torch.minimum(v, down)
        out.append(v)
    return out


def seam_grid(H, W, T, seed, sigma, ov=0, dual=False):
    """(ys, xs, windows, wys, wxs, info) of one evaluation with the seam fix: stride T - ov, shift in [0, stride) from the
    (seed, sigma) generator; dual adds a second grid shifted by half the stride on both axes. Windows are
    (iy, ix, y0, x0, h1, w1) with iy / ix indexing ys / xs (and wys / wxs), row-major per grid, grid 1 first."""
    stride = T - ov
    dy, dx = _offsets(seed, sigma, stride)
    h1, w1 = min(T, H), min(T, W)
    ys, xs = _seam_starts(H, T, dy, ov), _seam_starts(W, T, dx, ov)
    info = {'dy': dy, 'dx': dx, 'ny': len(ys), 'nx': len(xs), 'stride': stride, 'dual': bool(dual)}
    if not dual:
        wins = [(iy, ix, y0, x0, h1, w1) for iy, y0 in enumerate(ys) for ix, x0 in enumerate(xs)]
        return ys, xs, wins, _seam_weights(ys, T, H), _seam_weights(xs, T, W), info
    dy2, dx2 = (dy + stride // 2) % stride, (dx + stride // 2) % stride
    ys2, xs2 = _seam_starts(H, T, dy2, ov), _seam_starts(W, T, dx2, ov)
    wins = [(iy, ix, y0, x0, h1, w1) for iy, y0 in enumerate(ys) for ix, x0 in enumerate(xs)]
    wins += [(len(ys) + iy, len(xs) + ix, y0, x0, h1, w1) for iy, y0 in enumerate(ys2) for ix, x0 in enumerate(xs2)]
    info.update(dy2=dy2, dx2=dx2, ny2=len(ys2), nx2=len(xs2))
    return (ys + ys2, xs + xs2, wins, _tent_weights(ys, T, H) + _tent_weights(ys2, T, H),
            _tent_weights(xs, T, W) + _tent_weights(xs2, T, W), info)


def weight_sum(H, W, wins, wys, wxs):
    """The blend's weight sum per latent pixel for a window list (tests and reports)."""
    tot = torch.zeros(H, W)
    for (iy, ix, y0, x0, h1, w1) in wins:
        tot[y0:y0 + h1, x0:x0 + w1] += wys[iy][:, None] * wxs[ix][None, :]
    return tot


def steps_on(frac, n):
    """Spot implementation."""

    if frac >= 1.0 or n <= 0:
        return n
    return max(1, int(round(frac * n)))


def static_split(n, weights):
    """Unit indices per device: contiguous row-major blocks with sizes proportional to `weights`, rounded so they sum to n
    (largest remainders first, ties to the earlier device). Deterministic for a given (n, weights)."""
    k = len(weights)
    if k == 0:
        raise ValueError('static_split needs at least one device')
    if any((not isinstance(w, (int, float))) or w < 0 for w in weights) or sum(weights) <= 0:
        raise ValueError(f'device weights must be non-negative numbers with a positive sum (got {weights})')
    total = float(sum(weights))
    raw = [n * w / total for w in weights]
    counts = [int(r) for r in raw]
    order = sorted(range(k), key=lambda i: (-(raw[i] - counts[i]), i))
    for i in order[:n - sum(counts)]:
        counts[i] += 1
    out, s = [], 0
    for c in counts:
        out.append(list(range(s, s + c)))
        s += c
    return out


def parse_weights(text, k):
    if text is None or not str(text).strip():
        return None
    try:
        vals = [float(v) for v in str(text).replace(';', ',').split(',') if v.strip()]
    except ValueError:
        raise ValueError(f'ClaudeSpotTiles weights must be numbers separated by commas (got {text!r})')
    if len(vals) != k:
        raise ValueError(f'ClaudeSpotTiles weights list {len(vals)} values for {k} graphics cards')
    return vals


def device_identity(device):
    """(name, SM count, capability, memory) of a CUDA device; None for CPU / test keys."""
    try:
        if getattr(device, 'type', None) == 'cuda':
            p = torch.cuda.get_device_properties(device)
            return (p.name, int(p.multi_processor_count), (int(p.major), int(p.minor)), int(p.total_memory))
    except Exception:
        return None
    return None


def measured_weights(devices, identities=None):
    """Relative speed per device (1 / measured seconds per window) when every device has a measurement, else None."""
    ids = identities if identities is not None else [device_identity(d) for d in devices]
    with _SPEED_LOCK:
        secs = [_SPEED.get(i) if i is not None else None for i in ids]
    if any(s is None or s <= 0 for s in secs):
        return None
    return [1.0 / s for s in secs]


def record_speed(identity, seconds_per_window, alpha=0.5):
    if identity is None or not seconds_per_window or seconds_per_window <= 0:
        return
    with _SPEED_LOCK:
        old = _SPEED.get(identity)
        _SPEED[identity] = seconds_per_window if old is None else (1 - alpha) * old + alpha * seconds_per_window


def choose_balance(devices, balance, weights_text, identities=None, measured=None):
    """('queue', None) or ('static', weights) for the devices (first = main card)."""
    weights = parse_weights(weights_text, len(devices))
    if balance == 'queue':
        return 'queue', None
    ids = identities if identities is not None else [device_identity(d) for d in devices]
    if measured is None:
        measured = measured_weights(devices, ids)
    if balance == 'static':
        return 'static', weights or measured or [1.0] * len(devices)
    if weights is None and all(i is not None for i in ids) and len({i[:3] for i in ids}) == 1:
        return 'queue', None
    if weights is None:
        weights = measured or [float(i[1]) if i is not None else 1.0 for i in ids]
    return 'static', weights


def grad_context(inference, grad):
    """The sampler thread's autograd mode for a worker thread (grad and inference modes are thread-local; ComfyUI runs nodes
    under torch.inference_mode(), execution.py, and MultiGPUThreadPool threads start in the default mode)."""
    if inference:
        return torch.inference_mode(True)
    if not grad:
        return torch.no_grad()
    return contextlib.nullcontext()


def events_wanted():
    return bool(SPOT_LISTENERS) or os.environ.get('CU_SPOT_EVENTS') == '1'


def _emit(event):
    for fn in list(SPOT_LISTENERS):
        try:
            fn(event)
        except Exception:
            pass
    if os.environ.get('CU_SPOT_EVENTS') == '1':
        try:
            import server  
            inst = getattr(server.PromptServer, 'instance', None)
            if inst is not None:
                inst.send_sync('claude.spot', event)
        except Exception:
            pass


def run_split(units, devices, eval_unit, mode='queue', weights=None, submit=None, collect=None, interrupted=None,
              interrupt_exc=None, on_event=None, sync=None, eval_id=None, canvas=None, unit_size=None):
    """Evaluate every unit on one of `devices` and return (outputs in unit order, units per device, seconds per device).

    eval_unit(device, index, unit) -> anything. submit(device, fn) / collect(device) -> (result, error) is the
    MultiGPUThreadPool interface (one thread per device); without it one thread per device is started here. Every thread
    calls set_device(device) first. interrupted() -> bool is polled between units (ComfyUI's processing_interrupted; read-only,
    it does not clear the flag); interrupt_exc is the exception class raised then. sync(device) is called after a device's
    last unit (CUDA: synchronize, so the main thread reads finished results and the device's seconds are real). Errors: the
    first interrupt (else the first error) is re-raised after every device has stopped; the shared abort event stops the
    other devices after their current unit."""
    n = len(units)
    results = [None] * n
    abort = threading.Event()
    lock = threading.Lock()
    nxt = [0]
    if mode == 'static':
        plan = static_split(n, weights or [1.0] * len(devices))
    elif mode == 'queue':
        plan = None
    else:
        raise ValueError(f'unknown balance mode {mode!r}')
    counts, secs, wins = {}, {}, {}

    def take(pos):
        if plan is not None:
            for i in plan[pos]:
                yield i
            return
        while True:
            with lock:
                i = nxt[0]
                nxt[0] += 1
            if i >= n:
                return
            yield i

    def loop(pos, dev):
        done, nw = 0, 0
        set_device(dev)
        t0 = time.perf_counter()
        try:
            for i in take(pos):
                if abort.is_set():
                    break
                if interrupted is not None and interrupted():
                    abort.set()
                    raise (interrupt_exc or KeyboardInterrupt)()
                u = units[i]
                if on_event is not None:
                    on_event(dict(device=pos, state='start', index=i, unit=u, eval=eval_id, canvas=canvas))
                results[i] = eval_unit(dev, i, u)
                done += 1
                nw += unit_size(u) if unit_size is not None else 1
                if on_event is not None:
                    on_event(dict(device=pos, state='done', index=i, unit=u, eval=eval_id, canvas=canvas))
            if sync is not None:
                sync(dev)
        except BaseException:
            abort.set()
            raise
        finally:
            counts[pos] = done
            wins[pos] = nw
            secs[pos] = time.perf_counter() - t0
        return done

    errors = []
    if submit is not None:
        for pos, dev in enumerate(devices):
            submit(dev, loop, pos, dev)
        for dev in devices:
            _, err = collect(dev)
            if err is not None:
                errors.append(err)
    else:
        box = {}

        def run(pos, dev):
            try:
                loop(pos, dev)
            except BaseException as e:   
                box[pos] = e
        threads = [threading.Thread(target=run, args=(pos, dev), daemon=True, name=f'claude-spot-card{pos}')
                   for pos, dev in enumerate(devices)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        errors = [box[k] for k in sorted(box)]
    if errors:
        first = next((e for e in errors if interrupt_exc is not None and isinstance(e, interrupt_exc)), errors[0])
        raise first
    missing = [i for i, r in enumerate(results) if r is None]
    if missing:
        raise RuntimeError(f'ClaudeSpotTiles: {len(missing)} window group(s) were not evaluated')
    return results, counts, {'seconds': secs, 'windows': wins}


def blend(x_in, windows, outputs, wys=None, wxs=None, to_main=None):
    """The 9ea176c accumulation, in window order: acc[..win] += v * wt, wsum[..win] += wt, return acc / wsum. `outputs[i]` is
    the list returned for window i; to_main(v) moves a tensor to x_in's device (identity for main-card results)."""
    H, W = x_in.shape[-2:]
    out, wsum = None, torch.zeros((1, 1, H, W), device=x_in.device, dtype=x_in.dtype)
    clamp = wys is not None
    for (iy, ix, y0, x0, h1, w1), o in zip(windows, outputs):
        if to_main is not None:
            o = [to_main(v) for v in o]
        if out is None:
            out = [torch.zeros_like(x_in) for _ in o]
        wt = (wys[iy][:, None] * wxs[ix][None, :]) if clamp else 1
        for acc, v in zip(out, o):
            acc[..., y0:y0 + h1, x0:x0 + w1] += v * wt
        wsum[..., y0:y0 + h1, x0:x0 + w1] += wt
    return [acc / wsum for acc in out]


class _Fp16:
    lock = threading.Lock()
    depth = 0
    saved = None
    warned = False


def fp16_available():
    try:
        return hasattr(torch.backends.cuda.matmul, 'allow_fp16_accumulation')
    except Exception:
        return False


@contextlib.contextmanager
def fp16_accumulation():
    """allow_fp16_accumulation on for the duration (process-wide torch flag, reference-counted so concurrent card threads
    never switch it off under each other); restored to the value it had before the outermost entry."""
    m = torch.backends.cuda.matmul
    with _Fp16.lock:
        if _Fp16.depth == 0:
            _Fp16.saved = bool(m.allow_fp16_accumulation)
            m.allow_fp16_accumulation = True
        _Fp16.depth += 1
    try:
        yield
    finally:
        with _Fp16.lock:
            _Fp16.depth -= 1
            if _Fp16.depth == 0:
                m.allow_fp16_accumulation = _Fp16.saved
                _Fp16.saved = None


def pag_info(model_options):
    """({'perturbed': fn, 'scale': s}, None) when the stock PerturbedAttentionGuidance post-CFG function is present exactly once
    with scale > 0 and block ('middle', 0); else (None, reason)."""
    fns = model_options.get('sampler_post_cfg_function') or []
    pags = [f for f in fns if str(getattr(f, '__module__', '')).endswith('nodes_pag')
            and str(getattr(f, '__qualname__', '')).startswith('PerturbedAttentionGuidance.')
            and str(getattr(f, '__qualname__', '')).endswith('post_cfg_function')]
    if not pags:
        return None, 'no PerturbedAttentionGuidance post-CFG function'
    if len(pags) > 1:
        return None, 'more than one PerturbedAttentionGuidance'
    f = pags[0]
    try:
        cells = dict(zip(f.__code__.co_freevars, (c.cell_contents for c in (f.__closure__ or ()))))
    except ValueError:
        return None, 'PAG closure unreadable'
    scale, block, bid, pert = cells.get('scale'), cells.get('unet_block'), cells.get('unet_block_id'), cells.get('perturbed_attention')
    if not isinstance(scale, (int, float)) or not scale > 0:
        return None, f'PAG scale {scale!r} (not > 0)'
    if (block, bid) != PAG_KEY:
        return None, f'PAG block {(block, bid)!r} (expected {PAG_KEY})'
    if not callable(pert):
        return None, 'PAG perturbation function missing'
    return {'perturbed': pert, 'scale': float(scale)}, None


def default_middle_attention(bm, cache):
    """True unless a middle-block attention module carries its own attention function (ComfyAttention config): the fused
    patch calls ComfyUI's dispatcher without the module's preferred_attention, which is only the same call when it is unset."""
    dm = getattr(bm, 'diffusion_model', None)
    mid = getattr(dm, 'middle_block', None) if dm is not None else None
    if mid is None:
        return True
    key = id(dm)
    if key not in cache:
        ok = True
        for mod in mid.modules():
            ca = getattr(mod, 'comfy_attention', None)
            if ca is not None and getattr(ca, 'function', None) is not None:
                ok = False
                break
        cache[key] = ok
    return cache[key]


def make_fused_attn(pert):
    """attn1 replace patch for the batch-3 call: ComfyUI's normal attention for every row (as CrossAttention calls it, tensors
    in AttentionTensorContainers), and PAG's own perturbation function on the rows whose cond index is 2 (cond')."""
    def fused_attn(q, k, v, extra_options, mask=None):
        from comfy.ldm.modules import attention as A
        cu = list(extra_options.get('cond_or_uncond', []))
        n = len(cu)
        b = q.shape[0] // n if n else 0
        pag_rows = {}
        for j, ci in enumerate(cu):
            if ci == 2:
                sl = slice(j * b, (j + 1) * b)
                pag_rows[j] = pert(q[sl], k[sl], v[sl], extra_options).clone()   
        TC = getattr(A, 'AttentionTensorContainer', None)
        args = (TC(q), TC(k), TC(v)) if TC is not None else (q, k, v)
        out = A.optimized_attention(*args, extra_options['n_heads'], attn_precision=extra_options.get('attn_precision'),
                                    transformer_options=extra_options)
        for j, r in pag_rows.items():
            out[j * b:(j + 1) * b] = r
        return out
    return fused_attn


def _rows(t, keep, n):
    b = t.shape[0] // n
    return torch.cat([t[j * b:(j + 1) * b] for j in keep], dim=0)


def patched_call(call, conds_, xb, tb, mo, hds, mode, box):
    """One model call with the ControlNet chain head(s) wrapped: mode None | 'capture' (keep the positive chunk) | 'replay'
    (return the captured residuals) | 'dedupe' (batch-3 fused call: compute on the 2 distinct chunks). `call(conds, x, t, mo)`."""
    for hd in hds:
        orig = hd.get_control
        if mode == 'capture':
            def f(x_noisy, t, cond, batched_number, transformer_options, _o=orig, _h=hd):
                r = _o(x_noisy, t, cond, batched_number, transformer_options)
                cu = list(transformer_options.get('cond_or_uncond', []))
                if 0 in cu:
                    j = cu.index(0)
                    nch = len(cu)
                    box[id(_h)] = None if r is None else {kk: [None if vv is None else vv.chunk(nch)[j] for vv in lst]
                                                          for kk, lst in r.items()}
                return r
        elif mode == 'replay':
            def f(x_noisy, t, cond, batched_number, transformer_options, _o=orig, _h=hd):
                if id(_h) not in box:
                    return _o(x_noisy, t, cond, batched_number, transformer_options)
                r = box.pop(id(_h))
                return None if r is None else {kk: list(lst) for kk, lst in r.items()}
        elif mode == 'dedupe':
            def f(x_noisy, t, cond, batched_number, transformer_options, _o=orig, _h=hd):
                cu = list(transformer_options.get('cond_or_uncond', []))
                if not (2 in cu and 0 in cu):
                    return _o(x_noisy, t, cond, batched_number, transformer_options)
                nch = len(cu)
                keep = [j for j, ci in enumerate(cu) if ci != 2]
                c2 = {kk: (_rows(vv, keep, nch) if torch.is_tensor(vv) and vv.ndim > 0 and vv.shape[0] == x_noisy.shape[0] else vv)
                      for kk, vv in cond.items()}
                r = _o(_rows(x_noisy, keep, nch), _rows(t, keep, nch), c2, len(keep), transformer_options)
                if r is None:
                    return None
                pos = keep.index(cu.index(0))
                full = {}
                for kk, lst in r.items():
                    nl = []
                    for vv in lst:
                        if vv is None:
                            nl.append(None)
                            continue
                        b = vv.shape[0] // len(keep)
                        parts, it = [], 0
                        for ci in cu:
                            if ci == 2:
                                parts.append(vv[pos * b:(pos + 1) * b])
                            else:
                                parts.append(vv[it * b:(it + 1) * b])
                                it += 1
                        nl.append(torch.cat(parts, dim=0))
                    full[kk] = nl
                return full
        else:
            continue
        hd.get_control = f
    try:
        return call(conds_, xb, tb, mo)
    finally:
        for hd in hds:
            if 'get_control' in hd.__dict__:
                del hd.get_control  


def _controls(conds):
    seen, out = set(), []
    for group in conds:
        for c in group or []:
            cn = c.get('control') if isinstance(c, dict) else None
            while cn is not None and id(cn) not in seen:
                seen.add(id(cn)); out.append(cn); cn = cn.previous_controlnet
    return out


def _heads(conds):
    seen, out = set(), []
    for group in conds:
        for c in group or []:
            cn = c.get('control') if isinstance(c, dict) else None
            if cn is not None and id(cn) not in seen:
                seen.add(id(cn)); out.append(cn)
    return out


class ClaudeSpotTiles:
    """Per-step shifted tiling of ONE canvas latent (v5, 4 Nov 2026; own implementation of the SpotDiffusion idea, Frolov et al.
    2024). See the 9ea176c docstring for the single-GPU design (CALC_COND_BATCH wrapper, per-window ControlNet hint crops,
    PREPARE_SAMPLING one-window memory estimate, OUTER_SAMPLE hint release) and this module's docstring for the speed options,
    all off by default (off == 9ea176c bit for bit)."""
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"model": ("MODEL",), "tile_px": ("INT", {"default": 1024, "min": 256, "max": 4096, "step": 64}),
                             "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff})},
                "optional": {"clamp_blend": ("BOOLEAN", {"default": False}),
                             "window_split": ("BOOLEAN", {"default": False}),
                             "balance": (["auto", "queue", "static"], {"default": "auto"}),
                             "weights": ("STRING", {"default": ""}),
                             "batch_windows": ("INT", {"default": 1, "min": 1, "max": 16}),
                             "pag_fuse": ("BOOLEAN", {"default": False}),
                             "cn_reuse": ("BOOLEAN", {"default": False}),
                             "noise_prefetch": ("BOOLEAN", {"default": False}),
                             "fp16_acc_scoped": ("BOOLEAN", {"default": False}),
                             "live_preview": (["auto", "off", "rough", "detailed", "on", "on_taesd"], {"default": "auto"}),
                             "seam_overlap": ("INT", {"default": 0, "min": 0, "max": 64}),
                             "seam_dual": ("INT", {"default": 0, "min": 0, "max": 16}),
                             "pag_end": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01}),
                             "cfg_end": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01})}}
    RETURN_TYPES = ("MODEL",)
    FUNCTION = "apply"
    CATEGORY = "claude_creative"

    def apply(self, model, tile_px, seed, clamp_blend=False, window_split=False, balance='auto', weights='', batch_windows=1,
              pag_fuse=False, cn_reuse=False, noise_prefetch=False, fp16_acc_scoped=False, live_preview='auto',
              seam_overlap=0, seam_dual=0, pag_end=1.0, cfg_end=1.0):
        import comfy.utils
        import comfy.patcher_extension as pe
        T = tile_px // 8
        NB = int(batch_windows)
        if NB < 1:
            raise ValueError(f'ClaudeSpotTiles batch_windows must be >= 1 (got {batch_windows!r})')
        if balance not in ('auto', 'queue', 'static'):
            raise ValueError(f'ClaudeSpotTiles balance must be auto, queue or static (got {balance!r})')
        window_split, pag_fuse, cn_reuse = bool(window_split), bool(pag_fuse), bool(cn_reuse)
        noise_prefetch, fp16_acc_scoped = bool(noise_prefetch), bool(fp16_acc_scoped)
        pag_here = pag_fuse or cn_reuse
        SOV, SDUAL = int(seam_overlap), int(seam_dual)
        if SOV < 0 or SOV > T // 4:
            raise ValueError(f'ClaudeSpotTiles seam_overlap must be between 0 and a quarter of the window, {T // 4} latent px '
                             f'(got {seam_overlap!r})')
        if SDUAL < 0:
            raise ValueError(f'ClaudeSpotTiles seam_dual must be >= 0 (got {seam_dual!r})')
        seam_on = SOV > 0 or SDUAL > 0
        pag_end, cfg_end = float(pag_end), float(cfg_end)
        for nm, v in (('pag_end', pag_end), ('cfg_end', cfg_end)):
            if not 0.0 <= v <= 1.0:
                raise ValueError(f'ClaudeSpotTiles {nm} must be between 0 and 1 (got {v!r})')
        levers_on = pag_end < 1.0 or cfg_end < 1.0
        cache = {}
        st = {'stash': None, 'mid_ok': {}, 'balance': None, 'logged': set(), 'sig': None, 'grids': [], 'skip': None, 'lsig': None}
        from . import live as _live
        lmode = _live.mode_from(live_preview)
        em = _live.LiveEmitter(lmode) if lmode else None
        from .spot_timing import make_timer
        timer = make_timer('merged-sp%d-b%d-pf%d-cn%d-np%d-fp%d' % (int(window_split), NB, int(pag_fuse), int(cn_reuse),
                                                                   int(noise_prefetch), int(fp16_acc_scoped))
                           + ('-so%d-sd%d' % (SOV, SDUAL) if seam_on else '')
                           + ('-pe%03d-ce%03d' % (int(round(pag_end * 100)), int(round(cfg_end * 100))) if levers_on else ''))
        if fp16_acc_scoped and not fp16_available():
            logging.warning('ClaudeSpotTiles fp16_acc_scoped: this torch has no allow_fp16_accumulation; option ignored')
            fp16_acc_scoped = False
        scope = fp16_accumulation if fp16_acc_scoped else contextlib.nullcontext

        def note(msg):
            if msg not in st['logged']:
                st['logged'].add(msg)
                logging.info('ClaudeSpotTiles: %s', msg)

        def full_hint(cn, H, W, ref):
            key = (id(cn), H, W)
            if key not in cache or cache[key][0] is not cn:  
                if getattr(cn, 'vae', None) is not None or getattr(cn, 'latent_format', None) is not None or len(getattr(cn, 'extra_concat_orig', [])) > 0:
                    raise ValueError("ClaudeSpotTiles: ControlNets with VAE-encoded hints or extra concat are not supported")
                cr = cn.compression_ratio
                h = comfy.utils.common_upscale(cn.cond_hint_original, W * cr, H * cr, cn.upscale_algorithm, "center")
                h = cn.preprocess_image(h)
                dtype = cn.manual_cast_dtype if cn.manual_cast_dtype is not None else cn.control_model.dtype
                cache[key] = (cn, h.to(device=ref.device, dtype=dtype), cr)
            return cache[key][1:]

        def device_hint(cn, H, W, hint, device):
            """The main card's canvas hint copied once per sampling run to `device` (an exact copy)."""
            key = (id(cn), H, W, str(device))
            if key not in cache or cache[key][0] is not cn:
                cache[key] = (cn, to_device(hint, device))
            return cache[key][1]

        def prep(executor, model_p, noise_shape, *a, **k):
            ns = list(noise_shape)
            if len(ns) >= 4:
                ns[-2], ns[-1] = min(ns[-2], T), min(ns[-1], T)
                ns[0] = ns[0] * NB * (2 if pag_fuse else 1)  
            return executor(model_p, ns, *a, **k)

        def outer(executor, *a, **k):
            sig = a[3] if len(a) > 3 else k.get('sigmas')
            if timer is not None:
                timer.begin(sig)
            if em is not None:
                em.begin_pass(executor.class_obj, a[1] if len(a) > 1 else k.get('latent_image'), sig)
            st['stash'] = None
            st['balance'] = None
            if seam_on:
                st['sig'] = [float(v) for v in sig.detach().flatten().cpu()] if sig is not None else None
                st['grids'] = []
            if levers_on:
                st['skip'] = None
                st['lsig'] = [float(v) for v in sig.detach().flatten().cpu()] if sig is not None else None
            pf = None
            if noise_prefetch and sig is not None:
                from . import noise as _noise
                pf = _noise.install(sig)
            pf_stats = None
            sdp = sdp_state()                 
            try:
                return executor(*a, **k)
            finally:
                sdp_restore(sdp)              
                if pf is not None:
                    pf_stats = pf.uninstall()
                    logging.info('ClaudeSpotTiles noise_prefetch: %s', pf_stats)
                cache.clear()
                st['stash'] = None
                st['balance'] = None
                st['mid_ok'].clear()
                if em is not None:
                    em.end_pass()
                if timer is not None:
                    extra = {'window_split': window_split, 'batch_windows': NB, 'pag_fuse': pag_fuse, 'cn_reuse': cn_reuse,
                             'noise_prefetch': noise_prefetch, 'fp16_acc_scoped': fp16_acc_scoped,
                             'prefetch_stats': pf_stats, 'live_stats': dict(em.stats) if em is not None else None}
                    if seam_on:
                        extra.update(seam_overlap=SOV, seam_dual=SDUAL, seam_grids=list(st['grids']))
                    if levers_on:
                        extra.update(pag_end=pag_end, cfg_end=cfg_end)
                    timer.end(extra)
                if seam_on:
                    st['sig'] = None
                    st['grids'] = []
                if levers_on:
                    st['skip'] = None
                    st['lsig'] = None

        def pag_mode(bm, conds, model_options, main_call):
            """'fuse' / 'reuse' / None for this evaluation, and the PAG info."""
            if not (pag_here and main_call):
                return None, None
            info, why = pag_info(model_options)
            if info is None:
                note('pag_fuse/cn_reuse not used: ' + why)
                return None, None
            if len(conds) != 2 or conds[0] is None or conds[1] is None:
                note('pag_fuse/cn_reuse not used: cond or uncond missing (cfg 1)')
                return None, None
            rp = model_options.get('transformer_options', {}).get('patches_replace', {}).get('attn1', {})
            if PAG_KEY in rp:
                note('pag_fuse/cn_reuse not used: another attn1 replace patch at %r' % (PAG_KEY,))
                return None, None
            if 'model_function_wrapper' in model_options:
                note('pag_fuse/cn_reuse not used: a model_function_wrapper is set')
                return None, None
            if not default_middle_attention(bm, st['mid_ok']):
                note('pag_fuse/cn_reuse not used: the middle block has its own attention function')
                return None, None
            return ('fuse' if pag_fuse else 'reuse'), info

        def pag_options(mo, info):
            import comfy.model_patcher as mp
            
            
            mo_pag = mp.set_model_options_patch_replace(mo.copy(), info['perturbed'], "attn1", PAG_KEY[0], PAG_KEY[1])
            mo_fused = mp.set_model_options_patch_replace(mo.copy(), make_fused_attn(info['perturbed']), "attn1", PAG_KEY[0], PAG_KEY[1])
            return mo_pag, mo_fused

        def eval_group(executor, bm_d, conds, x_in, timestep, mo, mo_pag, mo_fused, grp, cns_d, hints_d, heads_d, mode, dev=None,
                       cfg1=False):
            """Evaluate the windows of `grp` [(iy, ix, y0, x0, h1, w1)] in one model call (mode None), one fused batch-3 call
            ('fuse') or a CFG call + PAG call ('reuse'). Returns one output list per window (on the evaluating device).
            cfg1 (cfg_end): the negative cond is not evaluated (None in its slot, so its output stays ComfyUI's zeros; the
            wrapper puts the positive prediction there); fused calls are then [cond, cond'] (cond_or_uncond [2, 0])."""
            if cfg1:
                conds = [conds[0], None] + list(conds[2:])
            n = len(grp)
            B = x_in.shape[0]
            crops = [x_in[..., y0:y0 + h1, x0:x0 + w1] for (_, _, y0, x0, h1, w1) in grp]
            xb = torch.cat(crops, dim=0) if n > 1 else crops[0]
            if dev is not None:
                xb = to_device(xb, dev)
            tb = timestep.repeat(n) if n > 1 else timestep

            def set_hints():
                for cn, (hint, cr) in zip(cns_d, hints_d):
                    cs = [hint[..., y0 * cr:(y0 + h1) * cr, x0 * cr:(x0 + w1) * cr] for (_, _, y0, x0, h1, w1) in grp]
                    cn.cond_hint = torch.cat(cs, dim=0) if n > 1 else cs[0]

            def call(c, xx, tt, mm_):
                with scope():
                    return executor(bm_d, c, xx, tt, mm_)
            set_hints()
            if mode == 'fuse':
                o = patched_call(call, [conds[0], conds[1], conds[0]], xb, tb, mo_fused, heads_d, 'dedupe', {})
            elif mode == 'reuse':
                box = {}
                o = patched_call(call, conds, xb, tb, mo, heads_d, 'capture', box)
                set_hints()  
                p = patched_call(call, [conds[0]], xb, tb, mo_pag, heads_d, 'replay', box)
                o = list(o) + list(p)
            else:
                o = call(conds, xb, tb, mo)
            if n == 1:
                return [o]
            return [[v[i * B:(i + 1) * B] for v in o] for i in range(n)]

        def window_event(device, state, index, unit, eid, H, W, n):
            ys0 = [w[2] for w in unit]; xs0 = [w[3] for w in unit]
            y0, x0 = min(ys0), min(xs0)
            y1 = max(w[2] + w[4] for w in unit); x1 = max(w[3] + w[5] for w in unit)
            ev = dict(device=device, state=state, index=index, eval=eid, n=n, y=y0 * 8, x=x0 * 8, h=(y1 - y0) * 8,
                      w=(x1 - x0) * 8, H=H * 8, W=W * 8, t=time.time())
            if len(unit) > 1:
                ev['windows'] = [[w[2] * 8, w[3] * 8, w[4] * 8, w[5] * 8] for w in unit]
            _emit(ev)

        def single(executor, bm, conds, x_in, timestep, model_options, cns, hints, ys, xs, wys, wxs, main_call, sigma, cfg1=False):
            """The 9ea176c loop, unchanged (plus the off-by-default emitter, fp16 scope and window events)."""
            H, W = x_in.shape[-2:]
            if cfg1:
                conds = [conds[0], None]
            lf = getattr(bm, 'latent_format', None)
            evs = events_wanted()
            eid = None
            if evs:
                _EVAL_COUNTER[0] += 1
                eid = _EVAL_COUNTER[0]
            nwin = len(ys) * len(xs)
            out, wsum = None, torch.zeros((1, 1, H, W), device=x_in.device, dtype=x_in.dtype)
            try:
                for iy, y0 in enumerate(ys):
                    for ix, x0 in enumerate(xs):
                        h1, w1 = min(T, H), min(T, W)
                        for cn, (hint, cr) in zip(cns, hints):
                            cn.cond_hint = hint[..., y0 * cr:(y0 + h1) * cr, x0 * cr:(x0 + w1) * cr]
                        if evs:
                            window_event(0, 'start', iy * len(xs) + ix, [(iy, ix, y0, x0, h1, w1)], eid, H, W, nwin)
                        if em is not None:
                            em.outline(iy * len(xs) + ix, nwin, [(iy, ix, y0, x0, h1, w1)], H, W, sigma, card=0,
                                       phase='cfg' if main_call else 'pag', total=nwin)
                        with scope():
                            o = executor(bm, conds, x_in[..., y0:y0 + h1, x0:x0 + w1], timestep, model_options)
                        if evs:
                            window_event(0, 'done', iy * len(xs) + ix, [(iy, ix, y0, x0, h1, w1)], eid, H, W, nwin)
                        if em is not None and main_call:
                            em.window(lf, o[0], y0, x0, h1, w1, H, W, sigma, card=0)  
                        if out is None:
                            out = [torch.zeros_like(x_in) for _ in o]
                        wt = (wys[iy][:, None] * wxs[ix][None, :]) if wys is not None else 1
                        for acc, v in zip(out, o):
                            acc[..., y0:y0 + h1, x0:x0 + w1] += v * wt
                        wsum[..., y0:y0 + h1, x0:x0 + w1] += wt
            finally:
                for cn in cns:
                    cn.cond_hint = None
            return [acc / wsum for acc in out]

        def grouped(executor, bm, conds, x_in, timestep, model_options, cns, hints, wins, wys, wxs, main_call, sigma, mode, info,
                    cfg1=False):
            """One card, batch groups and/or PAG fusion: groups of NB windows in row-major order, accumulated window by window."""
            H, W = x_in.shape[-2:]
            lf = getattr(bm, 'latent_format', None)
            mo_pag = mo_fused = None
            if mode is not None:
                mo_pag, mo_fused = pag_options(model_options, info)
            hds = _heads(conds) if (mode is not None and cns) else []
            groups = [wins[i:i + NB] for i in range(0, len(wins), NB)]
            evs = events_wanted()
            eid = None
            if evs:
                _EVAL_COUNTER[0] += 1
                eid = _EVAL_COUNTER[0]
            out, wsum = None, torch.zeros((1, 1, H, W), device=x_in.device, dtype=x_in.dtype)
            try:
                for gi, grp in enumerate(groups):
                    if evs:
                        window_event(0, 'start', gi, grp, eid, H, W, len(groups))
                    if em is not None:
                        em.outline(gi, len(groups), grp, H, W, sigma, card=0, phase='cfg' if main_call else 'pag',
                                   total=len(wins))
                    res = eval_group(executor, bm, conds, x_in, timestep, model_options, mo_pag, mo_fused, grp, cns, hints, hds, mode,
                                     cfg1=cfg1)
                    if evs:
                        window_event(0, 'done', gi, grp, eid, H, W, len(groups))
                    for (iy, ix, y0, x0, h1, w1), o in zip(grp, res):  
                        if em is not None and main_call:
                            em.window(lf, o[0], y0, x0, h1, w1, H, W, sigma, card=0)
                        if out is None:
                            out = [torch.zeros_like(x_in) for _ in o]
                        wt = (wys[iy][:, None] * wxs[ix][None, :]) if wys is not None else 1
                        for acc, v in zip(out, o):
                            acc[..., y0:y0 + h1, x0:x0 + w1] += v * wt
                        wsum[..., y0:y0 + h1, x0:x0 + w1] += wt
            finally:
                for cn in cns:
                    cn.cond_hint = None
            return [acc / wsum for acc in out]

        def split(executor, bm, conds, x_in, timestep, model_options, clones, cns, hints, wins, wys, wxs, H, W, main_call, sigma,
                  mode, info, cfg1=False):
            import comfy.model_management as mm
            main = x_in.device
            devices = [main] + [d for d in clones if d != main]
            mo_main = _strip(model_options)
            inst = {d: [cn.get_instance_for_device(d) for cn in cns] for d in devices}
            for d in devices[1:]:
                for i, cn in enumerate(cns):
                    if inst[d][i] is cn:
                        raise RuntimeError(f'ClaudeSpotTiles: the ControlNet has no clone on {d}; put MultiGPU_WorkUnits after '
                                           'ClaudeSpotTiles so ComfyUI prepares one per card')
            hds = _heads(conds) if (mode is not None and cns) else []
            hinst = {d: [h.get_instance_for_device(d) for h in hds] for d in devices}
            dev_hints = {main: hints}
            for d in devices[1:]:
                dev_hints[d] = [(device_hint(cn, H, W, h, d), cr) for cn, (h, cr) in zip(cns, hints)]
            mo_pag_main = mo_fused_main = None
            if mode is not None:
                mo_pag_main, mo_fused_main = pag_options(mo_main, info)

            def per_dev(mo, d):
                return mo if (mo is None or d == main) else dict(mo, multigpu_clones={d: clones[d]})
            mo_d = {d: per_dev(mo_main, d) for d in devices}
            mo_pag_d = {d: per_dev(mo_pag_main, d) for d in devices}
            mo_fused_d = {d: per_dev(mo_fused_main, d) for d in devices}
            bms = {d: (bm if d == main else clones[d].model) for d in devices}
            groups = [wins[i:i + NB] for i in range(0, len(wins), NB)]
            ids = [device_identity(d) for d in devices]
            if st['balance'] is None:      
                st['balance'] = choose_balance(devices, balance, weights, identities=ids)
                note('window_split over %d cards, balance %s %s' % (len(devices), st['balance'][0], st['balance'][1] or ''))
            bal, wts = st['balance']
            _EVAL_COUNTER[0] += 1
            eid = _EVAL_COUNTER[0]
            inference, grad = torch.is_inference_mode_enabled(), torch.is_grad_enabled()
            lf = getattr(bm, 'latent_format', None)
            evs = events_wanted()

            def eval_unit(d, gi, grp):
                if em is not None:
                    em.outline(gi, len(groups), grp, H, W, sigma, card=devices.index(d), phase='cfg' if main_call else 'pag',
                               total=len(wins))
                with grad_context(inference, grad):
                    res = eval_group(executor, bms[d], conds, x_in, timestep, mo_d[d], mo_pag_d[d], mo_fused_d[d], grp, inst[d],
                                     dev_hints[d], hinst[d], mode, dev=None if d == main else d, cfg1=cfg1)
                    if em is not None and main_call:
                        card = devices.index(d)
                        for (iy, ix, y0, x0, h1, w1), o in zip(grp, res):
                            em.window(lf, o[0], y0, x0, h1, w1, H, W, sigma, card=card)
                return res

            def on_event(ev):
                window_event(ev['device'], ev['state'], ev['index'], ev['unit'], ev['eval'], H, W, len(groups))

            pool = model_options.get('multigpu_thread_pool')
            pool_ok = pool is not None and all(d in pool.devices for d in devices)

            def sync(d):
                if getattr(d, 'type', None) == 'cuda':
                    torch.cuda.synchronize(d)
            try:
                outs, counts, tm = run_split(groups, devices, eval_unit, mode=bal, weights=wts,
                                             submit=pool.submit if pool_ok else None, collect=pool.get_result if pool_ok else None,
                                             interrupted=mm.processing_interrupted, interrupt_exc=mm.InterruptProcessingException,
                                             on_event=on_event if evs else None, sync=sync, eval_id=eid, unit_size=len)
            finally:
                for d in devices:
                    for cn in inst[d]:
                        cn.cond_hint = None
            for pos, ident in enumerate(ids):
                nw = tm['windows'].get(pos, 0)
                if nw:
                    record_speed(ident, tm['seconds'][pos] / nw)
            flat = [o for res in outs for o in res]
            return blend(x_in, wins, flat, wys, wxs,
                         to_main=lambda v: v if on_device(v, main) else to_device(v, main))

        def lever_state(sigma):
            """The levers for the step whose sigma this is: (pag_on, cfg_full). Both True (and no lookup) when the levers are
            off; the step is the sigma's index in this run's executed sigmas (OUTER_SAMPLE)."""
            if not levers_on:
                return True, True
            sg = st['lsig']
            if not sg:
                return True, True
            n = len(sg) - 1
            i = min(range(len(sg)), key=lambda j: abs(sg[j] - sigma))
            return i < steps_on(pag_end, n), i < steps_on(cfg_end, n)

        def remember_skip(conds, x_in, sigma, model_options, res0):
            """pag_end: keep this step's positive prediction for PAG's perturbed call (answered from it: PAG term exactly 0)."""
            info, why = pag_info(model_options)
            if info is None:
                st['skip'] = None
                return
            st['skip'] = {'sigma': sigma, 'x': x_in, 'cond': conds[0], 'perturbed': info['perturbed'], 'res0': res0}

        def wrapper(executor, bm, conds, x_in, timestep, model_options):
            H, W = x_in.shape[-2:]
            clones = model_options.get('multigpu_clones') if window_split else None
            multi = clones is not None and len(clones) > 1
            if 'multigpu_clones' in model_options and not multi:
                
                model_options = _strip(model_options)
            pag_on = cfg_full = True
            if levers_on:      
                t_lev = time.perf_counter()
                lsigma = float(timestep.flatten()[0])
                pag_on, cfg_full = lever_state(lsigma)
                if len(conds) < 2 and not pag_on and st['skip'] is not None:
                    s = st['skip']
                    rp = model_options.get('transformer_options', {}).get('patches_replace', {}).get('attn1', {})
                    if (s['sigma'] == lsigma and s['x'] is x_in and len(conds) == 1 and s['cond'] is conds[0]
                            and rp.get(PAG_KEY) is s['perturbed']):
                        st['skip'] = None
                        if timer is not None:
                            timer.call('pag', timer.step_of(lsigma), 0, t_lev, time.perf_counter(), 'skipped')
                        return [s['res0']]
                    if s['sigma'] != lsigma:
                        st['skip'] = None
            cfg1 = levers_on and len(conds) >= 2 and not cfg_full
            if H <= T and W <= T:
                mo = _strip(model_options) if multi else model_options   
                if em is not None:
                    em.outline(0, 1, [(0, 0, 0, 0, H, W)], H, W, float(timestep.flatten()[0]), card=0,
                               phase='cfg' if len(conds) >= 2 else 'pag', total=1)
                with scope():
                    o = executor(bm, [conds[0], None] if cfg1 else conds, x_in, timestep, mo)
                if cfg1:
                    o = [o[0], o[0]] + list(o[2:])
                if em is not None and len(conds) >= 2:
                    em.window(getattr(bm, 'latent_format', None), o[0], 0, 0, H, W, H, W, float(timestep.flatten()[0]), card=0)
                if levers_on and len(conds) >= 2 and not pag_on:
                    remember_skip(conds, x_in, float(timestep.flatten()[0]), model_options, o[0])
                return o
            t_call = time.perf_counter()
            sigma = float(timestep.flatten()[0])
            main_call = len(conds) >= 2  
            if pag_here and not main_call and st['stash'] is not None:
                s = st['stash']
                rp = model_options.get('transformer_options', {}).get('patches_replace', {}).get('attn1', {})
                if (s['sigma'] == sigma and s['x'] is x_in and len(conds) == 1 and s['cond'] is conds[0]
                        and rp.get(PAG_KEY) is s['perturbed']):
                    st['stash'] = None
                    if timer is not None:
                        timer.call('pag', timer.step_of(sigma), 0, t_call, time.perf_counter(), 'precomputed')
                    return [s['res']]
                if s['sigma'] != sigma:
                    st['stash'] = None
            cns = _controls(conds)
            hints = [full_hint(cn, H, W, x_in) for cn in cns]
            dual = False
            if seam_on:
                
                if SDUAL:
                    sg = st['sig']
                    if sg is None or len(sg) < 2:
                        note('seam_dual not used: the sampling run gave no sigma list')
                    else:
                        nev = len(sg) - 1
                        stp = min(range(nev), key=lambda i: abs(sg[i] - sigma))
                        dual = stp >= nev - SDUAL
                ys, xs, wins, wys, wxs, ginfo = seam_grid(H, W, T, seed, sigma, SOV, dual)
                wys = [v.to(device=x_in.device, dtype=x_in.dtype) for v in wys]
                wxs = [v.to(device=x_in.device, dtype=x_in.dtype) for v in wxs]
                if timer is not None and main_call:
                    st['grids'].append(dict(ginfo, sigma=round(sigma, 5), windows=len(wins)))
            else:
                dy, dx = _offsets(seed, sigma, T)
                ys, xs, wins = window_list(H, W, T, dy, dx)
                wys = wxs = None
                if clamp_blend:
                    wys = [v.to(device=x_in.device, dtype=x_in.dtype) for v in _spot_weights(ys, T, H)]
                    wxs = [v.to(device=x_in.device, dtype=x_in.dtype) for v in _spot_weights(xs, T, W)]
            mode, info = pag_mode(bm, conds, model_options, main_call) if pag_on else (None, None)
            if multi:
                res = split(executor, bm, conds, x_in, timestep, model_options, clones, cns, hints, wins, wys, wxs, H, W, main_call,
                            sigma, mode, info, cfg1=cfg1)
            elif NB == 1 and mode is None and not dual:
                res = single(executor, bm, conds, x_in, timestep, model_options, cns, hints, ys, xs, wys, wxs, main_call, sigma,
                             cfg1=cfg1)
            else:
                res = grouped(executor, bm, conds, x_in, timestep, model_options, cns, hints, wins, wys, wxs, main_call, sigma,
                              mode, info, cfg1=cfg1)
            if cfg1:
                res = [res[0], res[0]] + list(res[2:])   
            if timer is not None:
                label = mode
                if cfg1 or (main_call and not pag_on):
                    label = '%s%s%s' % (mode, '+cfg1' if cfg1 else '', '+pagoff' if (main_call and not pag_on) else '')
                timer.call('main' if main_call else 'pag', timer.step_of(sigma), len(wins), t_call, time.perf_counter(), label)
            if levers_on and main_call and not pag_on:
                remember_skip(conds, x_in, sigma, model_options, res[0])
            if mode is not None:
                st['stash'] = {'sigma': sigma, 'x': x_in, 'cond': conds[0], 'perturbed': info['perturbed'], 'res': res[2]}
                return res[:2]
            return res

        m = model.clone()
        m.add_wrapper_with_key(pe.WrappersMP.CALC_COND_BATCH, "claude_spot_tiles", wrapper)
        m.add_wrapper_with_key(pe.WrappersMP.PREPARE_SAMPLING, "claude_spot_tiles", prep)
        m.add_wrapper_with_key(pe.WrappersMP.OUTER_SAMPLE, "claude_spot_tiles", outer)
        return (m,)
