"""CUControlNetApplyPlane and PlaneHint: the classic ControlNetApplyAdvanced with the hint left in a plane (engine design
section 2.2 row 6; T3, T12).

The node runs ComfyUI's own ControlNetApplyAdvanced.apply_controlnet, unchanged, so set_cond_hint, the chain of previous
ControlNets and the conditioning copies are the stock code's. The only difference is the hint: where the classic hands
set_cond_hint `image.movedim(-1, 1)` (the whole canvas hint as a tensor), this node hands it a PlaneHint, a handle on the
hint plane. ClaudeSpotTilesBanded reads each window's crop from the plane (PlaneHint.bind, then `[..., y0:y1, x0:x1]`), in the
classic's dtype and memory format:
- a 3-channel hint (the tile ControlNet's blurred canvas, float32) reaches the ControlNet as an NHWC block viewed NCHW,
  channels-last, which is the layout the classic's crop has (ImageBlur's output is BHWC, ControlNetApplyAdvanced moves it to
  BCHW, common_upscale keeps the channels-last layout);
- the 1-channel edge plane (CUCannyPlane, 0/1) is expanded to 3 channels as ClaudeCannyTiled's output is: float32 0/1,
  repeated to [1, 3, h, w] NCHW-contiguous, which is the layout the classic's edge crop has (ClaudeCannyTiled repeats its
  [B, 1, H, W] edges to 3 channels and moves them to BHWC; ControlNetApplyAdvanced moves them back, contiguous);
- the cast is `.to(device, dtype)` with the ControlNet's run-time dtype (spot.py:702-704), read by the caller, never assumed.

A PlaneHint is not a tensor. Any tensor use raises TypeError, so comfy/controlnet.py:270-281 (get_control re-deriving a
whole-canvas hint from cond_hint_original when no window crop is set) can never run on it. A canvas within one window is
refused here, because the classic takes exactly that whole-canvas path for it (spot.py:1054)."""
from . import _engine, PlaneRef, NotBuilt, _out, _progress, _RUN, _DIR, _classic_pack

WINDOW_PX = 1024           # the plan's window (ClaudeSpotTiles tile_px); a canvas within one window takes the whole-hint path
_SAME_SIZE_IDENTITY = ('nearest-exact', 'nearest')   # common_upscale at the same size with these is the identity


class PlaneHint:
    """A ControlNet hint held in a plane (path and shape), set as `cond_hint_original`. Any tensor use raises (T12)."""
    __slots__ = ('path', 'run_id', 'height', 'width', 'channels', 'plane_dtype')

    def __init__(self, path, run_id, shape, plane_dtype):
        h, w, c = (int(v) for v in shape)
        if c not in (1, 3):
            raise ValueError(f'a ControlNet hint plane has 1 or 3 channels (got {c})')
        if plane_dtype not in ('u8', 'f32'):
            raise ValueError(f'a ControlNet hint plane is u8 or f32 (got {plane_dtype})')
        object.__setattr__(self, 'path', str(path))
        object.__setattr__(self, 'run_id', str(run_id))
        object.__setattr__(self, 'height', h)
        object.__setattr__(self, 'width', w)
        object.__setattr__(self, 'channels', c)
        object.__setattr__(self, 'plane_dtype', plane_dtype)

    @classmethod
    def from_ref(cls, ref):
        if not isinstance(ref, PlaneRef):
            raise TypeError('the hint must be a plane (PLANE) from the Large-image engine')
        return cls(ref.path, ref.run_id, ref.shape, ref.dtype)

    def one_window(self, window_px=None):
        w = WINDOW_PX if window_px is None else window_px
        return self.height <= w and self.width <= w

    def check(self, width, height, cn):
        """Refuse what the classic would resample: the classic's common_upscale to the canvas size (spot.py:701) is the
        identity only at the same size with a nearest method, and its preprocess_image (spot.py:702) must be the identity."""
        if (self.width, self.height) != (int(width), int(height)):
            raise ValueError(f'the hint plane is {self.width} x {self.height} px, the canvas {int(width)} x {int(height)}: '
                             'the Large-image engine never resamples a hint')
        if getattr(cn, 'upscale_algorithm', None) not in _SAME_SIZE_IDENTITY:
            raise ValueError(f'ControlNet hint resampling {getattr(cn, "upscale_algorithm", None)!r} is not supported by the '
                             'Large-image engine')
        probe = object()
        if cn.preprocess_image(probe) is not probe:
            raise ValueError('ControlNets that preprocess their hint are not supported by the Large-image engine')

    def bind(self, device, dtype):
        """The window reader for one card and the ControlNet's run-time dtype."""
        return BoundHint(self, device, dtype)

    # --- not a tensor -------------------------------------------------------------------------------------------------
    def _refuse(self, what):
        raise TypeError(f'a ControlNet hint plane is not a tensor: {what} is not allowed (PlaneHint)')

    def __getattr__(self, name):
        if name.startswith('__') and name.endswith('__'):
            raise AttributeError(name)            # Python's own protocol probes (copy, pickle) see a plain object
        self._refuse(name)

    def __setattr__(self, name, value):
        self._refuse(f'setting {name}')

    @classmethod
    def __torch_function__(cls, func, types, args=(), kwargs=None):
        raise TypeError(f'a ControlNet hint plane is not a tensor: {getattr(func, "__name__", func)} is not allowed (PlaneHint)')

    def __array__(self, *a, **k):
        self._refuse('__array__')

    def __getitem__(self, key):
        self._refuse('indexing')

    def __setitem__(self, key, value):
        self._refuse('indexing')

    def __len__(self):
        self._refuse('len')

    def __iter__(self):
        self._refuse('iteration')

    def __float__(self):
        self._refuse('float')

    def __int__(self):
        self._refuse('int')

    def __index__(self):
        self._refuse('index')

    def __bool__(self):
        return True

    def __copy__(self):                 # immutable: a copied ControlNet shares its hint handle, as copy_to shares a tensor
        return self

    def __deepcopy__(self, memo):
        return self

    def __reduce__(self):
        return (PlaneHint, (self.path, self.run_id, (self.height, self.width, self.channels), self.plane_dtype))

    def _arith(self, *a):
        self._refuse('arithmetic')
    __add__ = __radd__ = __sub__ = __rsub__ = __mul__ = __rmul__ = __truediv__ = __rtruediv__ = _arith
    __matmul__ = __rmatmul__ = __neg__ = __pow__ = __lt__ = __le__ = __gt__ = __ge__ = _arith

    def __repr__(self):
        return f'PlaneHint({self.width}x{self.height}x{self.channels} {self.plane_dtype})'


class BoundHint:
    """Window crops of a hint plane for one card: `bound[..., y0:y1, x0:x1]` is that crop as the classic's sliced hint holds
    it, [1, 3, y1 - y0, x1 - x0] in the classic's memory format, on `device` in `dtype`. Nothing else is allowed."""

    def __init__(self, hint, device, dtype):
        self.hint, self.device, self.dtype = hint, device, dtype
        self._map = None

    def rebind(self, device):
        """The same hint for another card (host-side crops per card; no whole-hint copy)."""
        return BoundHint(self.hint, device, self.dtype)

    def _plane(self):
        if self._map is None:
            self._map = _engine('planes').Plane.open(self.hint.path).map('r')
        return self._map

    def crop_array(self, y0, y1, x0, x1):
        """The crop as stored, H x W x C, copied out of the map (file-backed; no whole-plane read)."""
        import numpy as np
        h = self.hint
        if not (0 <= y0 < y1 <= h.height and 0 <= x0 < x1 <= h.width):
            raise ValueError(f'hint window {y0}:{y1}, {x0}:{x1} outside a {h.width} x {h.height} plane')
        return np.array(self._plane()[y0:y1, x0:x1])

    def __getitem__(self, key):
        if not (isinstance(key, tuple) and len(key) == 3 and key[0] is Ellipsis and all(
                isinstance(s, slice) and s.step is None and s.start is not None and s.stop is not None for s in key[1:])):
            raise TypeError('a hint plane is read only as hint[..., y0:y1, x0:x1] (PlaneHint)')
        return window_tensor(self.crop_array(key[1].start, key[1].stop, key[2].start, key[2].stop), self.hint.plane_dtype,
                             self.device, self.dtype)

    def __getattr__(self, name):
        if name.startswith('__') and name.endswith('__'):
            raise AttributeError(name)
        raise TypeError(f'a ControlNet hint plane is not a tensor: {name} is not allowed (PlaneHint)')


def window_tensor(arr, plane_dtype, device, dtype):
    """One window crop (H x W x C as stored) as the classic's crop: 3 channels float32 channels-last (u8 through the T2 table),
    or the 1-channel edges as ClaudeCannyTiled's float32 0/1 repeated to 3 channels NCHW; then `.to(device, dtype)`."""
    import numpy as np
    import torch
    if arr.shape[-1] == 3:
        a = _engine('planes').U8_TO_F32[arr] if plane_dtype == 'u8' else np.ascontiguousarray(arr, dtype=np.float32)
        t = torch.from_numpy(np.ascontiguousarray(a))[None].movedim(-1, 1)
    else:
        e = np.ascontiguousarray(arr[..., 0]).astype(np.float32)
        t = torch.from_numpy(e)[None, None].repeat(1, 3, 1, 1)
    return t.to(device=device, dtype=dtype)


class _HintImage:
    """What the stock apply_controlnet does with its `image`: `image.movedim(-1, 1)`, which here gives the PlaneHint."""

    def __init__(self, hint):
        self._hint = hint

    def movedim(self, source, destination):
        if (source, destination) != (-1, 1):
            raise TypeError('a ControlNet hint plane is not a tensor (PlaneHint)')
        return self._hint


def _stock_apply():
    import nodes
    return nodes.ControlNetApplyAdvanced


class CUControlNetApplyPlane:
    """ControlNetApplyAdvanced with the hint in a plane: the stock apply_controlnet and set_cond_hint, with a PlaneHint as
    cond_hint_original (T12). Canvases within one window are refused."""
    @classmethod
    def INPUT_TYPES(cls):
        f = lambda d, hi, st: ("FLOAT", {"default": d, "min": 0.0, "max": hi, "step": st})
        return {"required": {"positive": ("CONDITIONING",), "negative": ("CONDITIONING",), "control_net": ("CONTROL_NET",),
                             "hint": ("PLANE",), "strength": f(1.0, 10.0, 0.01), "start_percent": f(0.0, 1.0, 0.001),
                             "end_percent": f(1.0, 1.0, 0.001), "vae": ("VAE",)}}
    RETURN_TYPES = ("CONDITIONING", "CONDITIONING")
    RETURN_NAMES = ("positive", "negative")
    FUNCTION = "run"
    CATEGORY = "claude_banded"

    def run(self, positive, negative, control_net, hint, strength, start_percent, end_percent, vae):
        ph = PlaneHint.from_ref(hint)
        if ph.one_window():
            raise ValueError(f'the canvas ({ph.width} x {ph.height} px) fits one {WINDOW_PX} px window; the Large-image engine '
                             'does not run such canvases (the Classic engine does)')
        return _stock_apply()().apply_controlnet(positive, negative, control_net, _HintImage(ph), strength, start_percent,
                                                  end_percent, vae=vae)
