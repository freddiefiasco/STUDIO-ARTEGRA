"""The banded exact finish (BXF), variant bxf-1: the bytes of 5.0.1's ClaudeV4Finish + ClaudeShadowToe + SaveImage
(node_pack/claude_creative/v4finish.py v4_finish, __init__.py ClaudeV4Finish / shadow_toe_u8) computed over planes (engine
design ENGINE-DESIGN.md section 2.5).

Every step is 5.0.1's own call, in 5.0.1's order, on the same values and dtypes; only where the data lives changes:
  - local steps (E1) run the classic expression on full-width row bands plus their reach in real rows (bands of a registered
    height), where gate G1 measured every op in them band-invariant on this environment; otherwise whole on mapped planes (T7);
  - tbb's uniform filters run as whole lines (E2: column strips, then row bands);
  - percentiles and medians are exact streamed selections with numpy's own interpolation (E5);
  - components are labelled whole into mapped int32 planes, counted by bands, tested by the classic's own per-component code on
    the same windows, and applied as keep tables (E6);
  - pooled grids sit on 288-aligned bands (E3); zooms, resizes and the /4 distance transform are whole calls on small inputs
    writing mapped outputs (E4);
  - agree5's chroma clamp is the classic call on exactly the classic's 1024-row strips with 64 rows of overlap (E7);
  - the creativity map is the classic call, whole, at the stage input size (E8, lever L1's whole form);
  - torch's transcendental steps (pow in lf_mul, exp) and channel means run whole on tensors with the classic's own shapes and
    strides (E9), unless G1 measured them band-invariant.
The small "invented" islands revert to init exactly as 5.0.1 does; nothing else is added.

Private memory: the band budget (a registered value, default 2 GiB), the float32 PRE at I, the whole-call creativity map at I,
and the counted whole-call transients (torch's conv and pow outputs when they run whole; agree5's classic strips, whose size
depends on the width only). Scratch planes live in the work folder (file-backed). The process count is accepted from the
registered set (pixel-neutral); in this build every pass runs in the worker process.

This module is imported only when the finish runs (never at node-pack import: G0d)."""
import numpy as np

EW = ('np.hypot', 'ufunc exp f32', 'ufunc exp toe f32', 'ufunc tanh f32', 'ufunc arctan2 f32', 'ufunc arctan2 chanview f32',
      'ufunc cos sin f32', 'ufunc cbrt f32', 'ufunc power 2.4 f32', 'ufunc power 1/2.4 f32', 'ufunc power 3 f32',
      'ufunc square sqrt f32', 'ufunc sign f32', 'ufunc remainder degrees f32', 'arith f32', 'reduce channels f32',
      'matmul 3x3 f32', 'v4.luma', 'v4.rgb2lab', 'v4.lab2rgb', 'v4.hsv', 'v4.warm_gate', 'v4.smooth01', 'v4.to_u8')
VARIANTS = ('bxf-1',)


def GS(s):
    return f'gaussian_filter s={float(s)!r}'


def r_gauss(s):
    return int(4.0 * float(s) + 0.5)


class Unsupported(Exception):
    """The BXF does not make this option set (the node falls back to the whole oracle, tier 3)."""


class ByRow:
    """The rows of a (C, H, W) plane, seen by the band executor as an (H, W, C)-shaped object (axis 1 is the row axis)."""

    row_axis = 1

    def __init__(self, a):
        self.a = a
        self.shape = (a.shape[1], a.shape[2], a.shape[0])
        self.ndim = 3

    def __getitem__(self, s):
        return self.a[:, s]

    def __setitem__(self, s, v):
        self.a[:, s] = v

    def __array__(self, dtype=None, copy=None):
        return np.asarray(self.a) if dtype is None else np.asarray(self.a, dtype)


class BXF:
    def __init__(self, V, toe, E, work, band_gb=2.0, processes=1, table=None, progress=None, keep=False):
        bands = E('bands')
        self.keep = keep                                  # gates only: keep every scratch plane for a phase diff
        self.V, self.toe, self.E = V, toe, E
        self.band_gb = bands.check_band_budget(band_gb)
        self.processes = bands.check_process_count(int(processes))
        self.table = table if table is not None else E('bxf.g1').load()
        self.ws = E('bxf.work').Workspace(work)
        self.log = []
        self.stats = {}                                  # branch counts (pixel-neutral; gates read them)
        self.run = E('bxf.local').Runner(self.table, self.band_gb, log=self.log)
        self.T = E('planes').U8_TO_F32
        self.progress = progress or (lambda name: None)
        self.sel, self.comp, self.pool_, self.uni = E('bxf.selection'), E('bxf.components'), E('bxf.pooling'), E('bxf.uniform')

    # --- helpers ---------------------------------------------------------------------------------------------------------
    def new(self, name, shape, dtype=np.float32):
        return self.ws.new(name, shape, dtype)

    def free(self, *names):
        if not self.keep:
            self.ws.free(*[n for n in names if n in self.ws])

    def local(self, name, fn, inputs, outs, reach, ops=(), bpp=64.0):
        """outs: [(name, shape, dtype)]; a (3, H, W) shape is a CHW plane (its rows are axis 1). Returns the mapped output(s)."""
        arrays = [self.new(n, s, d) for (n, s, d) in outs]
        views = [ByRow(a) if (a.ndim == 3 and a.shape[0] == 3 and a.shape[2] != 3) else a for a in arrays]
        self.run(name, fn, inputs, views, reach, tuple(ops) + EW, bpp)
        self.progress(name)
        return arrays if len(arrays) > 1 else arrays[0]

    def h(self):
        """The band height for whole-line and pooled passes (pixel-neutral)."""
        return 2304 if self.band_gb >= 6.0 else 1152

    def tbb(self, x, r, name):
        out = self.new(name, x.shape)
        if self.table.banded(f'E2 tbb r={r}'):
            tmp = self.new(name + '.tmp', x.shape)
            self.uni.tbb_planes(x, r, out, tmp)
            self.free(name + '.tmp')
        else:
            out[...] = self.V.tbb(np.asarray(x), r)
        self.log.append((name, 'E2', r))
        return out

    def g(self, x, s, name):
        """v4finish.g(x, s): gaussian_filter (s <= 8, banded as E1) or the pooled path (E3 + E4)."""
        from scipy.ndimage import gaussian_filter
        if s <= 8:
            return self.local(name, lambda a: gaussian_filter(a, s), [x], [(name, x.shape, np.float32)], r_gauss(s), [GS(s)], 16)
        if self.table.banded(f'E3 g s={s!r}'):
            z = self.pool_.g_pooled(x, s, self.ws, name, 2304 if self.band_gb >= 6.0 else 576)
            self.log.append((name, 'E3', s))
            return z
        out = self.new(name, x.shape)
        out[...] = self.V.g(np.asarray(x), s)
        self.log.append((name, 'E3 whole', s))
        return out

    def percentiles(self, x, qs):
        if all(self.table.banded(f'E5 percentile q={q}') for q in qs):
            return self.sel.percentiles(self.sel.band_chunks(x, 2304), list(qs))
        a = np.asarray(x)
        return [np.percentile(a, q) for q in qs]

    def masked_median(self, values, mask):
        if self.table.banded('E5 median'):
            return self.comp.masked_median(values, mask)
        return np.median(np.asarray(values)[np.asarray(mask)])

    def component_median(self, values, lab, sl, i):
        if self.table.banded('E5 median'):
            return self.comp.component_median(values, lab, sl, i)
        return np.median(np.asarray(values)[np.asarray(lab) == i])

    def label(self, mask, name):
        """(labels plane, count) of scipy.ndimage.label(mask): into a mapped int32 plane (E6) or the classic call."""
        from scipy.ndimage import label
        out = self.new(name, mask.shape, np.int32)
        if self.table.banded('E6 label out=mapped'):
            n = self.comp.label_into(mask, out)
        else:
            lab, n = label(np.asarray(mask))
            out[...] = lab
            del lab
        return out, int(n)

    def bincount(self, lab, n):
        if self.table.banded('E6 bincount bands'):
            return self.comp.bincount_bands(lab, n)
        return np.bincount(np.asarray(lab).ravel())

    def table_apply(self, table, lab, name, dtype=bool):
        out = self.new(name, lab.shape, dtype)
        self.comp.apply_table(table, lab, out)
        return out

    def any(self, mask):
        return self.comp.any_true(mask)

    def tensor(self, a):
        import torch
        return torch.from_numpy(np.asarray(a))

    def ups(self, src, size, mode, name, channels):
        """F.interpolate(src, size, mode, align_corners=False) into a mapped (channels, H, W) plane (E4)."""
        import torch
        import torch.nn.functional as F
        if src.shape[0] * src.shape[1] != channels:
            raise ValueError('ups: channels must be the input N x C')
        out = self.new(name, (channels,) + tuple(size))
        t = self.tensor(out).view(src.shape[0], src.shape[1], *size)
        probe = 'E4 upsample_bilinear2d out=mapped' if mode == 'bilinear' else 'E4 upsample_bicubic2d out=mapped'
        if self.table.banded(probe):
            fn = torch._C._nn.upsample_bilinear2d if mode == 'bilinear' else torch._C._nn.upsample_bicubic2d
            fn(src, tuple(size), False, None, None, out=t)
        else:
            kw = {'antialias': False} if mode == 'bicubic' else {}
            t.copy_(F.interpolate(src, size=tuple(size), mode=mode, align_corners=False, **kw))
        out.flush()
        return out

    def blur_big(self, t, sigma, name):
        """v4finish._blur(t, sigma) for sigma > 8 on a [N, 1, H, W] (mapped) tensor: avg_pool2d whole on the mapped input (its
        output is small), the classic _blur on the pooled grid, the bicubic resize into a mapped (N, H, W) plane."""
        import torch.nn.functional as F
        f = int(sigma // 4)
        hh, ww = t.shape[-2:]
        s = F.avg_pool2d(t, f, ceil_mode=True)
        s = self.V._blur(s, sigma / f)
        return self.ups(s, (hh, ww), 'bicubic', name, t.shape[0])

    def blur_big_from_pooled(self, s, sigma, size, name):
        return self.ups(self.V._blur(s, sigma / int(sigma // 4)), size, 'bicubic', name, s.shape[0])

    def whole_torch(self, name, fn, out_shape):
        """An E9 step run whole (the classic tensor shapes and strides; its output a private transient copied into a mapped
        plane of out_shape, numpy layout)."""
        out = self.new(name, out_shape)
        r = fn()
        out[...] = r
        del r
        out.flush()
        self.log.append((name, 'E9 whole', None))
        return out

    # --- the finish ------------------------------------------------------------------------------------------------------
    def finish(self, S8, B8, I8, P8, protect, release, smooth=(0.3, 0.6), protect_dilate=12, protect_feather=4.0,
               islands=True, chroma_clamp=True, keep_blacks='pre_narrow', clamp='lead', lf='hyb', glow=None, fin_b0_hi=None,
               island_after_lf=False):
        """v4_finish on planes. S8, B8, I8: u8 (H, W, 3) (creative, structure, init); P8: u8 (h, w, 3) (pre); protect,
        release: float32 (h, w) or None. Returns the float32 (H, W, 3) result plane (v4_finish's return value)."""
        import torch
        from scipy.ndimage import (gaussian_filter, binary_dilation, binary_erosion, binary_opening, maximum_filter,
                                   minimum_filter, distance_transform_edt, zoom)
        V, T = self.V, self.T
        if (keep_blacks not in ('pre_narrow', 'render') or clamp not in ('lead', 'mm', 'agree5') or lf not in ('hyb', 'hybmin')
                or glow not in (None, 'none', 'skygaps')):
            raise ValueError('v4_finish: keep_blacks must be pre_narrow|render, clamp lead|mm|agree5, lf hyb|hybmin, glow None|skygaps')
        H, W = S8.shape[:2]
        if B8.shape != S8.shape or (islands and I8.shape != S8.shape):
            raise ValueError('v4_finish: structure and init must match creative')
        h, w = P8.shape[:2]
        C3 = (H, W, 3)
        # PRE as float32 (the classic's _f32(pre)), private at I
        P_ = np.ascontiguousarray(T[np.asarray(P8)[..., :3]])
        pre_t = torch.from_numpy(P_)

        # creativity map at I (E8, whole: the classic call), smoothstep, bilinear to (H, W) into a mapped plane (E4)
        m_i = V.creativity_map(pre_t, lo=0.0, hi=1.0, coh_k=0.85, p_lo=0.25, p_hi=0.85, feather=12.0, abs_hi=0.035)
        ss = (smooth[0], smooth[1])
        u = torch.clamp((m_i - ss[0]) / (ss[1] - ss[0]), 0, 1)
        m_i = u * u * (3 - 2 * u)
        del u
        MAP = self.ups(m_i[None, None], (H, W), 'bilinear', 'map', 1)[0]
        del m_i
        self.progress('creativity map')
        if protect is not None:
            pm = np.asarray(protect, dtype=np.float32)
            if pm.shape != P_.shape[:2]:
                raise ValueError(f'v4_finish: protect {pm.shape} must be at PRE resolution {P_.shape[:2]}')
            uu = pm > 0.5
            if protect_dilate > 0:
                uu = binary_dilation(uu, iterations=int(protect_dilate))
            p = gaussian_filter(uu.astype(np.float32), protect_feather)
            del uu
            if release is not None:
                r = np.asarray(release, dtype=np.float32)
                if r.shape != p.shape:
                    raise ValueError(f'protect_gate: release {r.shape} must match protect {p.shape}')
                p = p * (1 - gaussian_filter((r > 0.5).astype(np.float32), V.RELEASE_FEATHER))
            GATE = self.ups(torch.from_numpy(p)[None, None], (H, W), 'bilinear', 'gate', 1)[0]
            del p
            MM = self.local('mm', lambda m, g: m * (1 - g.clip(0, 1)), [MAP, GATE], [('mm', (H, W), np.float32)], 0)
            self.free('gate', 'map')
        else:
            MM = MAP
        # ref: bicubic PRE at (H, W) (E4), CHW as the classic's tensor; its HWC view is the classic's numpy `ref`
        REF = self.ups(pre_t.permute(2, 0, 1)[None], (H, W), 'bicubic', 'ref', 3)
        # Q: Pillow's Lanczos of the 8-bit PRE (T1: engine/lanczos_bands.py), kept as u8 (Q = T[Q8])
        lz = self.E('lanczos_bands')
        Q8 = self.new('q8', C3, np.uint8)
        P8c = np.ascontiguousarray(np.clip(np.round(P_ * 255), 0, 255).astype(np.uint8))
        tmp = self.new('q8.h', (h, W, 3), np.uint8) if (W != w and H != h) else None
        lz.resize(lz.ArrayRows(P8c), lz.ArrayRows(Q8), lz.ArrayRows(tmp) if tmp is not None else None)
        del P8c
        self.free('q8.h')
        self.progress('Q')
        LQ = self.local('lq', lambda q: V.luma(T[q]), [Q8], [('lq', (H, W), np.float32)], 0)
        # G['edge_p985'] and edge_zone(Yq): the same gradient magnitude of tbb(luma(Q), 1) (one plane, two readers)
        TB1 = self.tbb(LQ, 1, 'blq1')
        GMZ = self.local('gmz', lambda t: (lambda gy, gx: np.sqrt(gx * gx + gy * gy))(*np.gradient(t)), [TB1],
                         [('gmz', (H, W), np.float32)], 1, ['np.gradient'])
        p985 = self.percentiles(GMZ, [98.5])[0]
        Gd = {'edge_p985': float(p985)}
        ZONE = self.local('zone', lambda gm: binary_dilation(gm >= p985, iterations=2), [GMZ], [('zone', (H, W), bool)], 2,
                          ['binary_dilation it=2'])
        self.free('gmz')
        # mix
        MIX = self.local('mix', lambda m, s8, b8: (m[..., None] * T[s8] + (1 - m[..., None]) * T[b8]).astype(np.float32),
                         [MM, S8, B8], [('mix', C3, np.float32)], 0)
        Wisl = None
        if islands:
            MIXLF = self.lf_add_plain(MIX, REF, 'mixlf')
            Wisl = self.islands(MIXLF, Q8, LQ, MM, Gd, ZONE)
            self.free('mixlf')
            if not island_after_lf:
                MIX2 = self.local('mix2', lambda wi, i8, x: (wi[..., None] * T[i8] + (1 - wi[..., None]) * x).astype(np.float32),
                                  [Wisl, I8, MIX], [('mix2', C3, np.float32)], 0)
                self.free('mix')
                MIX = MIX2
        # the hybrid robust low-frequency transfer (torch; E9 steps whole)
        X = self.lf_hybrid(MIX, REF, lf)
        self.free('mix', 'mix2', 'ref')
        if islands and island_after_lf:
            X2 = self.local('x2', lambda wi, i8, x: (wi[..., None] * T[i8] + (1 - wi[..., None]) * x).astype(np.float32),
                            [Wisl, I8, X], [('x2', C3, np.float32)], 0)
            self.free('x')
            X = X2
        self.free('wisl')
        self.progress('lf')
        # FIN-1.2 core
        finp = V.FINP if fin_b0_hi is None else {**V.FINP, 'b0': (V.FINP['b0'][0], float(fin_b0_hi))}
        Y, Y2 = self.fin_core(X, LQ, ZONE, finp)
        # post: antiring agree2, keep_blacks, srcwarm
        out = self.post(X, Y, LQ, Y2, ZONE, Q8, kb_pre='narrow' if keep_blacks == 'pre_narrow' else False)
        self.free('fy', 'fy2', 'zone')
        do_glow = glow == 'skygaps'
        if chroma_clamp and clamp == 'agree5':
            PC = self.local('pc', V.to_u8, [out], [('pc', C3, np.uint8)], 0)
            self.free('post')
            RES = self.new('res', C3, np.float32)
            step, ov = 1024, 64
            for y0 in range(0, H, step):                        # E7: exactly the classic's strips
                a, b = max(0, y0 - ov), min(H, y0 + step + ov)
                r = V.clamp_r2(T[np.asarray(PC[a:b])], T[np.asarray(Q8[a:b])], mode='agree5')
                RES[y0:min(H, y0 + step)] = r[y0 - a:y0 - a + min(step, H - y0)]
                del r
            RES.flush()
            self.free('pc')
            self.progress('clamp agree5')
            if do_glow:
                RES = self.csc_sky(RES, Q8, LQ, 'res')
            return RES
        if chroma_clamp:
            if clamp == 'lead':
                out = self.local('clamped', lambda o, q: V.chroma_hc2(o, T[q], warm=V.WARM), [out, Q8], [('clamped', C3, np.float32)],
                                 8, ['v4.chroma_hc2 warm', GS(2.0), GS(1.0)], 260)
            else:
                out = self.local('clamped', lambda o, q: V.chroma_mm(T[V.to_u8(o)], T[q]), [out, Q8], [('clamped', C3, np.float32)],
                                 40, ['v4.chroma_mm', 'v4.agreement', GS(2.0), GS(1.0)], 340)
            self.free('post')
        if do_glow:
            O8 = self.local('o8', V.to_u8, [out], [('o8', C3, np.uint8)], 0)
            out = self.csc_sky(O8, Q8, LQ, 'post' if 'post' in self.ws else 'clamped', from_u8=True)
        return out

    # --- the steps ---------------------------------------------------------------------------------------------------------
    def lf_add_plain(self, MIX, REF, name):
        """lf_add(mix, ref, 0.0) = lowfreq_transfer(sigma 32, strength 1, robust 0): lp(r) - lp(x) by pooled blurs."""
        H, W = MIX.shape[:2]
        XC = self.new(name + '.xc', (3, H, W))
        for y0 in range(0, H, 2304):                             # x.reshape(3, 1, H, W): the classic's contiguous copy
            XC[:, y0:y0 + 2304] = np.moveaxis(np.asarray(MIX[y0:y0 + 2304]), -1, 0)
        LPX = self.blur_big(self.tensor(XC).view(3, 1, H, W), 32.0, name + '.lpx')
        self.free(name + '.xc')
        LPR = self.blur_big(self.tensor(REF).view(3, 1, H, W), 32.0, name + '.lpr')

        def fn(mix, lpr, lpx):
            x = self.tensor(mix).permute(2, 0, 1)[None]
            c = self.tensor(lpr)[None] - self.tensor(lpx)[None]
            out = x + 1.0 * c
            return self.torch_clamp01(out).permute(0, 2, 3, 1)[0].numpy()
        out = self.local(name, fn, [MIX, ByRow(LPR), ByRow(LPX)], [(name, MIX.shape, np.float32)], 0, ['torch exact ops'], 48)
        self.free(name + '.lpx', name + '.lpr')
        return out

    @staticmethod
    def torch_clamp01(t):
        import torch
        return torch.clamp(t, 0, 1)

    def weight(self, MIX, REF, robust):
        """wgt = exp(-(_blur(|r - x|.mean(1), 4) / robust) ** 2) of lowfreq_transfer / lf_mul (the same expression in both), and
        d = r - x (CHW)."""
        import torch
        H, W = MIX.shape[:2]
        V = self.V

        def dfn(mix, r):
            return (self.tensor(r)[None] - self.tensor(mix).permute(2, 0, 1)[None])[0].numpy()
        Dp = self.local('lf.d', dfn, [MIX, ByRow(REF)], [('lf.d', (3, H, W), np.float32)], 0, ['torch exact ops'], 48)
        if self.table.banded('torch mean(1) of |r - x|'):
            A1 = self.local('lf.a1', lambda d: self.tensor(d)[None].abs().mean(1, keepdim=True)[0, 0].numpy(), [ByRow(Dp)],
                            [('lf.a1', (H, W), np.float32)], 0, ['torch mean(1) of |r - x|'], 32)
        else:
            A1 = self.whole_torch('lf.a1', lambda: self.tensor(Dp)[None].abs().mean(1, keepdim=True)[0, 0], (H, W))
        if self.table.banded('torch _blur s=4.0 (_sep conv)'):
            DM = self.local('lf.dm', lambda a: V._blur(self.tensor(np.ascontiguousarray(a))[None, None], 4.0)[0, 0].numpy(), [A1],
                            [('lf.dm', (H, W), np.float32)], 14, ['torch _blur s=4.0 (_sep conv)'], 40)
        else:
            DM = self.whole_torch('lf.dm', lambda: V._blur(self.tensor(A1)[None, None], 4.0)[0, 0], (H, W))
        self.free('lf.a1')
        if self.table.banded('torch exp f32'):
            WG = self.local('lf.w', lambda dm: torch.exp(-(self.tensor(np.ascontiguousarray(dm))[None, None] / robust) ** 2)[0, 0]
                            .numpy(), [DM], [('lf.w', (H, W), np.float32)], 0, ['torch exp f32'], 24)
        else:
            WG = self.whole_torch('lf.w', lambda: torch.exp(-(self.tensor(DM)[None, None] / robust) ** 2)[0, 0], (H, W))
        self.free('lf.dm')
        return Dp, WG

    def lf_hybrid(self, MIX, REF, lf):
        """lf_hyb / lf_hyb_min(mix, ref, 0.06): lf_add (robust) and lf_mul, then the classic blend, banded."""
        import torch
        import torch.nn.functional as F
        V, T = self.V, self.T
        H, W = MIX.shape[:2]
        robust = 0.06
        Dp, WG = self.weight(MIX, REF, robust)
        wt = self.tensor(WG).view(1, 1, H, W)
        # den = _blur(wgt expanded to 3 channels, 32): pooling is per element, so the pooled wgt expanded is the same grid
        s1 = F.avg_pool2d(wt, 8, ceil_mode=True)
        DEN = self.blur_big_from_pooled(s1.expand(3, 1, *s1.shape[-2:]).contiguous(), 32.0, (H, W), 'lf.den')
        del s1
        # lf_add robust: num = _blur((wgt * d).reshape(3, 1, H, W), 32)
        WD = self.local('lf.wd', lambda wg, d: (self.tensor(np.ascontiguousarray(wg))[None, None] * self.tensor(d)[None])[0].numpy(),
                        [WG, ByRow(Dp)], [('lf.wd', (3, H, W), np.float32)], 0, ['torch exact ops'], 40)
        WDp = self.ws.get('lf.wd')
        NUM = self.blur_big(self.tensor(WDp).view(3, 1, H, W), 32.0, 'lf.num')
        self.free('lf.wd', 'lf.d')

        def addfn(mix, num, den):
            x = self.tensor(mix).permute(2, 0, 1)[None]
            c = self.tensor(num)[None] / torch.clamp(self.tensor(den)[None], min=1e-3)
            return self.torch_clamp01(x + 1.0 * c).permute(0, 2, 3, 1)[0].numpy()
        ADD = self.local('lf.add', addfn, [MIX, ByRow(NUM), ByRow(DEN)], [('lf.add', MIX.shape, np.float32)], 0, ['torch exact ops'], 48)
        self.free('lf.num')
        # lf_mul: lin(x), lin(r) (pow 2.4: E9 whole on the classic strides), the gain, the inverse (pow 1/2.4: E9 whole)
        PX = self.local('lf.px', lambda mix: ((self.tensor(mix).permute(2, 0, 1)[None].clamp(0, 1) + 0.055) / 1.055)
                        .permute(0, 2, 3, 1)[0].numpy(), [MIX], [('lf.px', MIX.shape, np.float32)], 0, ['torch exact ops'], 36)
        if self.table.banded('torch pow 2.4 channels-last'):
            POWX = self.local('lf.powx', lambda p: (self.tensor(p).permute(2, 0, 1)[None] ** 2.4).permute(0, 2, 3, 1)[0].numpy(),
                              [PX], [('lf.powx', MIX.shape, np.float32)], 0, ['torch pow 2.4 channels-last'], 36)
        else:
            POWX = self.whole_torch('lf.powx', lambda: (self.tensor(PX).permute(2, 0, 1)[None] ** 2.4).permute(0, 2, 3, 1)[0],
                                    MIX.shape)
        self.free('lf.px')
        XL = self.local('lf.xl', lambda mix, pw: torch.where(self.tensor(mix).permute(2, 0, 1)[None] <= 0.04045,
                                                              self.tensor(mix).permute(2, 0, 1)[None] / 12.92,
                                                              self.tensor(pw).permute(2, 0, 1)[None]).permute(0, 2, 3, 1)[0].numpy(),
                        [MIX, POWX], [('lf.xl', MIX.shape, np.float32)], 0, ['torch exact ops'], 40)
        self.free('lf.powx')
        PR = self.local('lf.pr', lambda r: ((self.tensor(r)[None].clamp(0, 1) + 0.055) / 1.055)[0].numpy(), [ByRow(REF)],
                        [('lf.pr', (3, H, W), np.float32)], 0, ['torch exact ops'], 36)
        PRp = self.ws.get('lf.pr')
        POWR = self.whole_torch('lf.powr', lambda: self.tensor(PRp)[None] ** 2.4, (1, 3, H, W))
        self.free('lf.pr')
        RL = self.local('lf.rl', lambda r, pw: torch.where(self.tensor(r)[None] <= 0.04045, self.tensor(r)[None] / 12.92,
                                                            self.tensor(pw)[None])[0].numpy(),
                        [ByRow(REF), ByRow(POWR[0])], [('lf.rl', (3, H, W), np.float32)], 0, ['torch exact ops'], 40)
        self.free('lf.powr')
        RLp = self.ws.get('lf.rl')
        WRL = self.local('lf.wrl', lambda wg, rl: (self.tensor(np.ascontiguousarray(wg))[None, None] * self.tensor(rl)[None])[0]
                         .numpy(), [WG, ByRow(RLp)], [('lf.wrl', (3, H, W), np.float32)], 0, ['torch exact ops'], 40)
        BRL = self.blur_big(self.tensor(self.ws.get('lf.wrl')).view(3, 1, H, W), 32.0, 'lf.brl')
        self.free('lf.wrl', 'lf.rl')
        XLp = self.ws.get('lf.xl')
        WXL = self.local('lf.wxl', lambda wg, xl: (self.tensor(np.ascontiguousarray(wg))[None, None]
                                                   * self.tensor(xl).permute(2, 0, 1)[None])[0].numpy(),
                         [WG, XLp], [('lf.wxl', (3, H, W), np.float32)], 0, ['torch exact ops'], 40)
        BXL = self.blur_big(self.tensor(self.ws.get('lf.wxl')).view(3, 1, H, W), 32.0, 'lf.bxl')
        self.free('lf.wxl', 'lf.w')

        def gainfn(brl, bxl, den, xl):
            dc = torch.clamp(self.tensor(den)[None], min=1e-3)
            gain = ((self.tensor(brl)[None] / dc + 2e-3) / (self.tensor(bxl)[None] / dc + 2e-3)).clamp(0.5, 2.0)
            ol = (self.tensor(xl).permute(2, 0, 1)[None] * gain).clamp(0, 1)
            return ol.permute(0, 2, 3, 1)[0].numpy()
        OL = self.local('lf.ol', gainfn, [ByRow(BRL), ByRow(BXL), ByRow(DEN), XLp], [('lf.ol', MIX.shape, np.float32)], 0,
                        ['torch exact ops'], 60)
        self.free('lf.brl', 'lf.bxl', 'lf.den', 'lf.xl')
        if self.table.banded('torch pow 1/2.4 channels-last'):
            POWO = self.local('lf.powo', lambda o: (self.tensor(o).permute(2, 0, 1)[None] ** (1 / 2.4)).permute(0, 2, 3, 1)[0].numpy(),
                              [OL], [('lf.powo', MIX.shape, np.float32)], 0, ['torch pow 1/2.4 channels-last'], 36)
        else:
            POWO = self.whole_torch('lf.powo', lambda: (self.tensor(OL).permute(2, 0, 1)[None] ** (1 / 2.4)).permute(0, 2, 3, 1)[0],
                                    MIX.shape)

        def mulfn(ol, pw):
            o = self.tensor(ol).permute(2, 0, 1)[None]
            r = torch.where(o <= 0.0031308, 12.92 * o, 1.055 * self.tensor(pw).permute(2, 0, 1)[None] - 0.055)
            return r[0].permute(1, 2, 0).numpy().astype(np.float32)
        MUL = self.local('lf.mul', mulfn, [OL, POWO], [('lf.mul', MIX.shape, np.float32)], 0, ['torch exact ops'], 40)
        self.free('lf.ol', 'lf.powo')
        V_ = V
        if lf == 'hyb':
            def blend(a, m, mix):
                ww = np.clip((0.30 - V_.luma(mix)) / (0.30 - 0.10), 0, 1)[..., None]
                return (ww * m + (1 - ww) * a).astype(np.float32)
        else:
            def blend(a, m, mix):
                ca, cm = a.max(-1) - a.min(-1), m.max(-1) - m.min(-1)
                sel = (1 / (1 + np.exp(-(ca - cm) / 0.01)))[..., None]
                dark = sel * m + (1 - sel) * a
                ww = np.clip((0.30 - V_.luma(mix)) / (0.30 - 0.10), 0, 1)[..., None]
                return (ww * dark + (1 - ww) * a).astype(np.float32)
        X = self.local('x', blend, [ADD, MUL, MIX], [('x', MIX.shape, np.float32)], 0, (), 80)
        self.free('lf.add', 'lf.mul')
        return X

    def islands(self, MIXLF, Q8, LQ, MM, Gd, ZONE):
        """w = max(colour_filter(hardware_islands(mixlf, Q, cmap=mm, edge_t), mixlf, Q), litter_islands(Q, mm, G))."""
        from scipy.ndimage import gaussian_filter, binary_dilation, maximum_filter, minimum_filter
        V, T = self.V, self.T
        H, W = LQ.shape
        S2 = (H, W)
        edge_t = Gd['edge_p985']
        # hardware_islands (k 2.2, floor .02, src_smooth .03, min_px 30, max_px 15000, ring 24, ring_smooth .85, grow 4,
        # feather 2.5, rel_t .08, edge_de 35, e01_t .0065)
        ER = self.local('hw.er', lambda x: V.band_energy(V.luma(x), 1.0, 6.0, 4.0), [MIXLF], [('hw.er', S2, np.float32)], 40,
                        ['v4.band_energy (1,6,4)'], 40)
        ES = self.local('hw.es', lambda lq: V.band_energy(lq, 1.0, 6.0, 4.0), [LQ], [('hw.es', S2, np.float32)], 40,
                        ['v4.band_energy (1,6,4)'], 32)
        REL = self.local('hw.rel', lambda es, lq: gaussian_filter(es, 16.0) / (gaussian_filter(lq, 8.0) + 0.05), [ES, LQ],
                         [('hw.rel', S2, np.float32)], 64, [GS(16.0), GS(8.0)], 24)
        E01 = self.local('hw.e01', lambda lq: np.sqrt(gaussian_filter((lq - gaussian_filter(lq, 0.8)) ** 2, 4.0)), [LQ],
                         [('hw.e01', S2, np.float32)], 19, [GS(0.8), GS(4.0)], 24)

        def nsfn(er, es, rel, e01, mm):
            ns = (er > 2.2 * es + 0.02) & (gaussian_filter(es, 8.0) < 0.03) & (rel < 0.08) & (gaussian_filter(e01, 6.0) < 0.0065)
            ns &= mm < 0.3
            return binary_dilation(ns, iterations=2)
        NSD = self.local('hw.nsd', nsfn, [ER, ES, REL, E01, MM], [('hw.nsd', S2, bool)], 34,
                         [GS(8.0), GS(6.0), 'binary_dilation it=2'], 32)
        self.free('hw.er', 'hw.rel', 'hw.e01')
        LQLAB = self.local('lqlab', lambda q: V.rgb2lab(gaussian_filter(T[q], (1, 1, 0))), [Q8], [('lqlab', S2 + (3,), np.float32)], 4,
                           ['gaussian_filter hwc (1,1,0)'], 80)
        GMQ = self.local('gmq', lambda lq: (lambda gy, gx: np.hypot(gx, gy))(*np.gradient(gaussian_filter(lq, 1.0))), [LQ],
                         [('gmq', S2, np.float32)], 5, [GS(1.0), 'np.gradient'], 24)

        def strongfn(lab3, gm):
            crng = np.maximum(*[maximum_filter(lab3[..., ch], 11) - minimum_filter(lab3[..., ch], 11) for ch in (1, 2)])
            return binary_dilation((crng >= 35.0) | ((gm >= edge_t) if edge_t is not None else False), iterations=6)
        STRONG = self.local('hw.strong', strongfn, [LQLAB, GMQ], [('hw.strong', S2, bool)], 11,
                            ['maximum_filter chanview 11', 'binary_dilation it=6'], 24)
        LAB1, n1 = self.label(NSD, 'hw.lab')
        keep1 = np.zeros(n1 + 1, bool)
        if n1:
            sizes = self.bincount(LAB1, n1)
            sl = self.comp.find_objects(LAB1, n1)
            ring, min_px, max_px, ring_smooth = 24, 30, 15000, 0.85
            for i in range(1, n1 + 1):
                s = sl[i - 1]
                if s is None or not (min_px <= sizes[i] <= max_px):
                    continue
                ys, xs = s
                y0, y1 = max(0, ys.start - ring - 2), min(H, ys.stop + ring + 2)
                x0, x1 = max(0, xs.start - ring - 2), min(W, xs.stop + ring + 2)
                blob = np.asarray(LAB1[y0:y1, x0:x1]) == i
                rr = binary_dilation(blob, iterations=ring) & ~binary_dilation(blob, iterations=3)
                if not (rr.sum() > 30 and float((~np.asarray(NSD[y0:y1, x0:x1])[rr]).mean()) >= ring_smooth):
                    continue
                if np.asarray(STRONG[s])[np.asarray(LAB1[s]) == i].any():
                    continue
                keep1[i] = True
        self.stats.update(hw_components=n1, hw_kept=int(keep1.sum()))
        self.free('hw.strong', 'hw.nsd')
        WHW = self.local('hw.w', lambda lab: np.clip(gaussian_filter(binary_dilation(keep1[lab], iterations=4).astype(np.float32),
                                                                     2.5) * 1.5, 0, 1),
                         [LAB1], [('hw.w', S2, np.float32)], 14, ['binary_dilation it=4', GS(2.5)], 24)
        self.free('hw.lab')
        self.progress('hardware islands')
        # colour_filter(whw, mixlf, Q, dab_p90 10)
        SUP = self.local('cf.sup', lambda ww: ww > 0.02, [WHW], [('cf.sup', S2, bool)], 0)
        LAB2, n2 = self.label(SUP, 'cf.lab')
        self.free('cf.sup')
        if n2:
            DAB = self.local('cf.dab', lambda x, lqlab: np.sqrt(((V.rgb2lab(gaussian_filter(x, (1, 1, 0)))[..., 1:] - lqlab[..., 1:]) ** 2)
                                                                .sum(-1)),
                             [MIXLF, LQLAB], [('cf.dab', S2, np.float32)], 4, ['gaussian_filter hwc (1,1,0)'], 80)
            CORE = self.local('cf.core', lambda ww, lab: np.where(ww > 0.5, lab, 0), [WHW, LAB2], [('cf.core', S2, np.int32)], 0)
            sl2 = self.comp.find_objects(LAB2, n2)
            temp = np.empty(n2, float)
            temp[:] = 0.0
            for i in range(1, n2 + 1):
                s = sl2[i - 1]
                if s is None:
                    continue
                v = self.comp.window_values(DAB, CORE, s, i)
                if v.size:
                    temp[i - 1] = np.percentile(v, 90)
            keep2 = np.zeros(n2 + 1, bool)
            keep2[1:] = temp >= 10.0
            self.stats.update(cf_components=n2, cf_kept=int(keep2.sum()))
            WHW2 = self.local('cf.w', lambda ww, lab: (ww * keep2[lab]).astype(np.float32), [WHW, LAB2], [('cf.w', S2, np.float32)], 0)
            self.free('cf.dab', 'cf.core', 'hw.w')
        else:
            WHW2 = WHW
        self.free('cf.lab')
        self.progress('colour filter')
        # litter_islands(Q, mm, G) (tex_t .035, ring 30, ring_mat .35, grow 6, feather 2.5, dab_min 8)

        def seedfn(q, es):
            a = gaussian_filter(T[q], (1, 1, 0))
            mx, mn = a.max(-1), a.min(-1)
            d = mx - mn
            sat = d / np.maximum(mx, 1e-4)
            r, g, b = a[..., 0], a[..., 1], a[..., 2]
            hue = np.where(mx == r, (60 * (g - b) / np.maximum(d, 1e-6)) % 360,
                           np.where(mx == g, 60 * (b - r) / np.maximum(d, 1e-6) + 120, 60 * (r - g) / np.maximum(d, 1e-6) + 240))
            dry = (hue >= 10) & (hue <= 55) & (sat >= 0.12) & (sat <= 0.6)
            return binary_dilation((es > 0.035) & dry, iterations=3)
        SEED = self.local('lt.seed', seedfn, [Q8, ES], [('lt.seed', S2, bool)], 7, ['gaussian_filter hwc (1,1,0)', 'binary_dilation it=3'], 80)
        self.free('hw.es')
        M = self.material_mask(Q8, LQ, MM, Gd)
        LAB4, n4 = self.label(SEED, 'lt.lab')
        self.free('lt.seed')
        keep4 = np.zeros(n4 + 1, bool)
        if n4:
            sizes = self.bincount(LAB4, n4)
            sl4 = self.comp.find_objects(LAB4, n4)
            ring = 30
            for i in range(1, n4 + 1):
                s = sl4[i - 1]
                if s is None:
                    continue
                ys, xs = s
                y0, y1 = max(0, ys.start - ring - 2), min(H, ys.stop + ring + 2)
                x0, x1 = max(0, xs.start - ring - 2), min(W, xs.stop + ring + 2)
                blob = np.asarray(LAB4[y0:y1, x0:x1]) == i
                rr = binary_dilation(blob, iterations=ring) & ~blob
                if not (sizes[i] >= 40 and rr.sum() > 30 and float((np.asarray(M[y0:y1, x0:x1])[rr] > 0.5).mean()) >= 0.35):
                    continue
                ab = np.asarray(LQLAB[y0:y1, x0:x1, 1:])
                if float(np.linalg.norm(ab[blob].mean(0) - ab[rr].mean(0))) >= 8.0:
                    keep4[i] = True
        self.stats.update(litter_components=n4, litter_kept=int(keep4.sum()))
        self.free('lt.m', 'lqlab')
        WLT = self.local('lt.w', lambda lab: np.clip(gaussian_filter(binary_dilation(keep4[lab], iterations=6).astype(np.float32),
                                                                     2.5) * 1.5, 0, 1),
                         [LAB4], [('lt.w', S2, np.float32)], 16, ['binary_dilation it=6', GS(2.5)], 24)
        self.free('lt.lab')
        WI = self.local('wisl', lambda a, b: np.maximum(a, b), [WHW2, WLT], [('wisl', S2, np.float32)], 0)
        self.free('cf.w', 'hw.w', 'lt.w')
        self.progress('litter islands')
        return WI

    def material_mask(self, Q8, LQ, MM, Gd):
        """material_mask(Q, cmap, G)[0]: structure tensor, edges, the product mask, opening(40), components whose median
        coherence is > .88 removed, dilation(40) and the sigma-3 blur."""
        from scipy.ndimage import gaussian_filter, binary_dilation, binary_opening
        V, T = self.V, self.T
        H, W = LQ.shape
        S2 = (H, W)

        def structfn(lq):
            gy, gx = np.gradient(gaussian_filter(lq, 1.0))
            jxx, jyy, jxy = gaussian_filter(gx * gx, 6.0), gaussian_filter(gy * gy, 6.0), gaussian_filter(gx * gy, 6.0)
            tr = jxx + jyy
            disc = np.sqrt(np.maximum((jxx - jyy) ** 2 / 4 + jxy ** 2, 0))
            l1, l2 = tr / 2 + disc, np.maximum(tr / 2 - disc, 0)
            coh = ((l1 - l2) / (l1 + l2 + 1e-12)) ** 2
            return coh, np.sqrt(l1 + l2)
        COH, EST = self.local('mt.st', structfn, [LQ], [('mt.coh', S2, np.float32), ('mt.e', S2, np.float32)], 29,
                              [GS(1.0), GS(6.0), 'np.gradient'], 60)
        edge = Gd['edge_p985']

        def mfn(coh, e, cm, q, gm, lq):
            a = T[q]
            mx, mn = a.max(-1), a.min(-1)
            sat = (mx - mn) / np.maximum(mx, 1e-4)
            edges = binary_dilation(gm >= edge, iterations=4)
            m = np.clip((coh - 0.35) / 0.25, 0, 1) * np.clip((0.045 - e) / 0.02, 0, 1) * np.clip((0.3 - cm) / 0.2, 0, 1) \
                * np.clip((0.28 - sat) / 0.1, 0, 1)
            m = m * (~edges)
            return m * np.clip((0.88 - lq) / 0.1, 0, 1)
        MR = self.local('mt.m', mfn, [COH, EST, MM, Q8, self.ws.get('gmq'), LQ], [('mt.m', S2, np.float32)], 4,
                        ['binary_dilation it=4'], 60)
        self.free('mt.e', 'gmq')
        BIG = self.local('mt.big', lambda m: binary_opening(m > 0.5, iterations=40), [MR], [('mt.big', S2, bool)], 80,
                         ['binary_opening it=40'], 8)
        LAB3, n3 = self.label(BIG, 'mt.lab')
        drop = np.zeros(n3 + 1, bool)
        if n3:
            sl3 = self.comp.find_objects(LAB3, n3)
            for i in range(1, n3 + 1):
                if sl3[i - 1] is not None and self.component_median(COH, LAB3, sl3[i - 1], i) > 0.88:
                    drop[i] = True
        self.stats.update(material_components=n3, material_dropped=int(drop.sum()))
        self.free('mt.coh')
        M = self.local('lt.m', lambda m, big, lab: gaussian_filter((m * binary_dilation(big & ~drop[lab], iterations=40))
                                                                   .astype(np.float32), 3.0),
                       [MR, BIG, LAB3], [('lt.m', S2, np.float32)], 52, ['binary_dilation it=40', GS(3.0)], 24)
        self.free('mt.m', 'mt.big', 'mt.lab')
        return M

    def fin_core(self, X, LQ, ZONE, p):
        """fin_core(X, Q, finp) -> (Y, Y2) planes (Yq is LQ, zone is ZONE)."""
        from scipy.ndimage import gaussian_filter
        V = self.V
        p = {**V.DEF, **(p or {})}
        H, W = LQ.shape
        S2 = (H, W)
        R, SIG = V.R, V.SIG
        Y = self.local('fy', V.luma, [X], [('fy', S2, np.float32)], 0)
        # BQ = stack(Yq): bl = [Yq] + tbb(Yq, r)
        blq = [LQ, self.ws.get('blq1')] + [self.tbb(LQ, r, f'blq{r}') for r in R[1:]]

        def loce(a, b, k, name):
            s = SIG[k]
            if 2 * s <= 8:
                return self.local(name, lambda u, v: np.sqrt(np.maximum(gaussian_filter((u - v) * (u - v), 2 * s), 0)) + 1e-5,
                                  [a, b], [(name, S2, np.float32)], r_gauss(2 * s), [GS(2 * s)], 24)
            sq = self.local(name + '.sq', lambda u, v: (u - v) * (u - v), [a, b], [(name + '.sq', S2, np.float32)], 0)
            z = self.g(sq, 2 * s, name + '.z')
            out = self.local(name, lambda zz: np.sqrt(np.maximum(zz, 0)) + 1e-5, [z], [(name, S2, np.float32)], 0)
            self.free(name + '.sq', name + '.z')
            return out
        EQ = [loce(blq[k], blq[k + 1], k, f'eq{k}') for k in range(5)]
        for r in R[1:]:
            self.free(f'blq{r}')
        self.free('blq1')
        TX = self.local('tx', lambda e1, e2: np.sqrt(e1 ** 2 + e2 ** 2), [EQ[1], EQ[2]], [('tx', S2, np.float32)], 0)
        p35, p75 = self.percentiles(TX, [35, 75])
        den = p75 - p35 + 1e-6
        TEX = self.local('tex', lambda tx: np.clip((tx - p35) / den, 0, 1).astype(np.float32), [TX], [('tex', S2, np.float32)], 0)
        self.free('tx')
        clamps = [p['g0'], p['g12'], p['g12'], p['g34'], p['g34']]
        DEADL = V.DEAD
        ycur = Y
        for it in range(int(p['iters'])):
            bl = [ycur] + [self.tbb(ycur, r, f'bl{it}.{r}') for r in R]
            acc = bl[5]
            for k in range(5):
                LD = loce(bl[k], bl[k + 1], k, f'ld{it}.{k}')
                lo, hi = tuple(p['b0']) if (k == 0 and 'b0' in p) else DEADL[k]
                flat = (k == 0 and 'b0_flat' in p)
                ck = clamps[k]

                def gainfn(eq, ld, tex, lo=lo, hi=hi, flat=flat, ck=ck):
                    ratio = eq / ld
                    lo_, hi_ = lo, hi
                    if flat:
                        lo_ = p['b0_flat'][0] + tex * (lo - p['b0_flat'][0])
                        hi_ = p['b0_flat'][1] + tex * (hi - p['b0_flat'][1])
                    gain = np.where(ratio * hi_ < 1, ratio * hi_, np.where(ratio * lo_ > 1, ratio * lo_, 1.0))
                    return np.clip(gain, *ck).astype(np.float32)
                GC = self.local(f'gc{it}.{k}', gainfn, [EQ[k], LD, TEX], [(f'gc{it}.{k}', S2, np.float32)], 0)
                self.free(f'ld{it}.{k}')
                GG = self.g(GC, p['beta'] * SIG[k], f'gg{it}.{k}')
                self.free(f'gc{it}.{k}')
                zk = k in (1, 2)

                def accfn(acc_, a, b, gg, zone, zk=zk):
                    gain = np.where(zone, np.minimum(gg, 1.0), gg) if zk else gg
                    return acc_ + (a - b) * gain
                newacc = self.local(f'acc{it}.{k}', accfn, [acc, bl[k], bl[k + 1], GG, ZONE], [(f'acc{it}.{k}', S2, np.float32)], 0)
                self.free(f'gg{it}.{k}')
                if k:
                    self.free(f'acc{it}.{k - 1}')
                acc = newacc
            for r in R:
                self.free(f'bl{it}.{r}')
            if it:
                self.free(f'ycur{it - 1}')
            ycur = self.local(f'ycur{it}', lambda a: a.astype(np.float32), [acc], [(f'ycur{it}', S2, np.float32)], 0)
            self.free(f'acc{it}.4')
        self.free('tex', *[f'eq{k}' for k in range(5)])
        bl = [ycur] + [self.tbb(ycur, r, f'blf.{r}') for r in R]
        tau0, kappa = p['tau0'], p['kappa']

        def y2fn(b0_, b1, b2, b3, b4, b5):
            BD = [b0_ - b1, b1 - b2, b2 - b3, b3 - b4, b4 - b5]
            resD = b5
            b0 = tau0 * np.tanh(BD[0] / tau0)
            if kappa:
                pol = np.sign(gaussian_filter(BD[0] ** 3, 8.0))
                b0 = b0 * (1 + kappa * pol * np.sign(b0))
            Y2 = resD + b0 + BD[1] + BD[2] + BD[3] + BD[4]
            Y2 = np.where(Y2 > 0.95, 0.95 + 0.05 * np.tanh((Y2 - 0.95) / 0.05), Y2)
            return Y2.astype(np.float32)
        Y2 = self.local('fy2', y2fn, bl, [('fy2', S2, np.float32)], 32, [GS(8.0)], 48)
        for r in R:
            self.free(f'blf.{r}')
        self.free(f'ycur{int(p["iters"]) - 1}')
        self.progress('fin core')
        return Y, Y2

    def post(self, X, Y, LQ, Y2, ZONE, Q8, kb_pre):
        """post(X, Y, Yq, Y2, zone, Q, ar 'agree2', kb .75, kb_pre, chroma 'srcwarm', ar_min 80)."""
        from scipy.ndimage import gaussian_filter, binary_dilation, maximum_filter, minimum_filter
        V, T = self.V, self.T
        H, W = LQ.shape
        S2 = (H, W)
        r, tol = 3, 0.04

        def disfn(y2, yq):
            ys_, qs_ = gaussian_filter(y2, 1.5), gaussian_filter(yq, 1.5)
            cr = y2 > 0.5 * (maximum_filter(ys_, 15) + minimum_filter(ys_, 15))
            cq = yq > 0.5 * (maximum_filter(qs_, 15) + minimum_filter(qs_, 15))
            return cr != cq
        DIS = self.local('po.dis', disfn, [Y2, LQ], [('po.dis', S2, bool)], 13, [GS(1.5), 'maximum_filter 15', 'minimum_filter 15'], 40)
        LAB5, n5 = self.label(DIS, 'po.lab')
        self.free('po.dis')
        big = self.bincount(LAB5, n5) >= 80
        big[0] = False
        self.stats.update(agree2_components=n5, agree2_big=int(big.sum()))

        def y2post(y2, yq, y, zone, lab):
            az = binary_dilation(zone, iterations=r + 2)
            w = gaussian_filter(az.astype(np.float32), 1.5)
            lo, hi = minimum_filter(yq, 2 * r + 1) - tol, maximum_filter(yq, 2 * r + 1) + tol
            dis = big[lab]
            w = w * gaussian_filter((~dis).astype(np.float32), 1.0)
            y2 = y2 + w * (np.clip(y2, lo, hi) - y2)
            wd = np.clip((0.22 - y) / 0.17, 0, 1)
            if kb_pre == 'narrow':
                wd = wd * np.maximum(np.clip((0.22 - gaussian_filter(yq, 2.0)) / 0.17, 0, 1), np.clip((y - 0.06) / 0.04, 0, 1))
            elif kb_pre:
                wd = wd * np.clip((0.22 - gaussian_filter(yq, 2.0)) / 0.17, 0, 1)
            return y2 - 0.75 * wd * np.maximum(y2 - y, 0)
        Y2b = self.local('po.y2', y2post, [Y2, LQ, Y, ZONE, LAB5], [('po.y2', S2, np.float32)], 11,
                         ['binary_dilation it=5', GS(1.5), GS(1.0), GS(2.0), 'maximum_filter 7', 'minimum_filter 7'], 48)
        self.free('po.lab')
        OUT = self.local('post', lambda x, y, yq, y2, q: V.fin_post(x, y, yq, y2, None, antiring=None, keep_blacks=0.0,
                                                                    chroma='srcwarm', Q=T[q], src=(2.0, 0.9, 1.05)),
                         [X, Y, LQ, Y2b, Q8], [('post', X.shape, np.float32)], 8, ['v4.fin_post srcwarm', GS(2.0)], 260)
        self.free('po.y2', 'x', 'x2')
        self.progress('post')
        return OUT

    def csc_sky(self, O, Q8, LQ, src_name, from_u8=False):
        """csc_sky(O, Q, size 31, sig 12, tol .03, dil 4, mode 'gaps', rim 5)[0]."""
        from scipy.ndimage import gaussian_filter, binary_dilation, binary_erosion, maximum_filter, minimum_filter
        from scipy.ndimage import distance_transform_edt, zoom
        V, T = self.V, self.T
        H, W = LQ.shape
        S2 = (H, W)
        # sky_mask(Q)
        CAND = self.local('sk.cand', lambda lq, q: (lq > 0.55) & (np.sqrt(gaussian_filter((lq - gaussian_filter(lq, 1.0)) ** 2 + (
            gaussian_filter(lq, 1.0) - gaussian_filter(lq, 4.0)) ** 2, 3.0)) < 0.012) & ((T[q][..., 2] - T[q][..., 0]) > -0.01),
            [LQ, Q8], [('sk.cand', S2, bool)], 28, [GS(1.0), GS(4.0), GS(3.0)], 40)
        LAB6, n6 = self.label(CAND, 'sk.lab')
        sky_any = False
        if n6:
            BR = self.local('sk.br', lambda q: T[q][..., 2] - T[q][..., 0], [Q8], [('sk.br', S2, np.float32)], 0)
            top = np.unique(np.asarray(LAB6[:8, :]))
            top = top[top > 0]
            sizes = self.bincount(LAB6, n6)
            keep6 = np.zeros(n6 + 1, bool)
            if top.size:
                sl6 = self.comp.find_objects(LAB6, int(top.max()))
                for k in top:
                    if sizes[k] >= 2000 and float(self.component_median(BR, LAB6, sl6[k - 1], k)) >= 0.012:
                        keep6[k] = True
            SKY0 = self.table_apply(keep6, LAB6, 'sk.sky0')
            self.stats.update(sky_candidates=n6, sky_top=int(top.size), sky_kept=int(keep6.sum()))
            if self.any(SKY0):
                s_level = float(self.masked_median(LQ, SKY0))
                GAPS = self.local('sk.gaps', lambda c, sk, lq, br: c & ~sk & (lq > s_level - 0.10) & (br > 0.005),
                                  [CAND, SKY0, LQ, BR], [('sk.gaps', S2, bool)], 0)
                LAB7, n7 = self.label(GAPS, 'sk.lab2')
                self.free('sk.gaps')
                sz2 = self.bincount(LAB7, n7)
                okg = (sz2 >= 40) & (sz2 <= 200000)
                okg[0] = False
                self.stats.update(sky_gap_components=n7, sky_gaps_kept=int(okg.sum()))
                SKY1 = self.local('sk.sky1', lambda sk, lab2: sk | okg[lab2], [SKY0, LAB7], [('sk.sky1', S2, bool)], 0)
                self.free('sk.lab2', 'sk.sky0')
            else:
                SKY1 = SKY0
            self.free('sk.br')
            SKYM = self.local('sk.m', lambda sk: np.clip(gaussian_filter(binary_erosion(sk, iterations=2).astype(np.float32), 1.5)
                                                         * 1.3, 0, 1),
                              [SKY1], [('sk.m', S2, np.float32)], 8, ['binary_erosion it=2', GS(1.5)], 24)
            self.free('sk.sky1', 'sk.sky0')
            sky_any = True
        self.free('sk.lab', 'sk.cand')
        # sky_gaps(Q, sky)
        gate_s = None
        if sky_any:
            S0 = self.local('sg.s0', lambda m: m > 0.5, [SKYM], [('sg.s0', S2, bool)], 0)
            if self.any(S0):
                lvl = float(self.masked_median(LQ, S0))
                C2 = self.local('sg.cand', lambda lq, q: (gaussian_filter(lq, 1.0) > lvl - 0.12) & (T[q][..., 2] - T[q][..., 0] >= 0.0),
                                [LQ, Q8], [('sg.cand', S2, bool)], 4, [GS(1.0)], 24)
                f = 4
                d = distance_transform_edt(~np.asarray(S0)[::f, ::f]) * f
                fac = (H / d.shape[0], W / d.shape[1])
                NZ = self.new('sg.near', self.pool_.zoom_shape(d.shape, fac), np.float64)
                if self.table.banded('E4 zoom order=0 f64 out=mapped'):
                    zoom(d, fac, output=NZ, order=0)
                else:
                    NZ[...] = zoom(d, fac, order=0)
                del d
                NZv = NZ[:H, :W]
                gate_s = self.local('sg.gate', lambda c, nz: np.clip(gaussian_filter(binary_dilation(c & (nz <= 512), iterations=3)
                                                                                     .astype(np.float32), 1.0) * 1.3, 0, 1),
                                    [C2, NZv], [('sg.gate', S2, np.float32)], 7, ['binary_dilation it=3', GS(1.0)], 24)
                del NZv
                self.stats.update(gate_s_nonzero=True)
                self.free('sg.near', 'sg.cand')
            self.free('sg.s0')
        self.free('sk.m')
        if gate_s is None:
            gate_s = self.new('sg.gate', S2, np.float32)

        def cscfn(o, yq, gs):
            O_ = T[o] if from_u8 else o
            Y = V.luma(O_)
            qs = gaussian_filter(yq, 1.5)
            qmx, qmn = maximum_filter(qs, 31), minimum_filter(qs, 31)
            qb = (qs > qmx - 0.2 * (qmx - qmn)).astype(np.float32)
            ref = gaussian_filter(yq * qb, 12.0) / np.maximum(gaussian_filter(qb, 12.0), 1e-3)
            ys = gaussian_filter(Y, 1.5)
            ymx, ymn = maximum_filter(ys, 31), minimum_filter(ys, 31)
            rb = np.clip((Y - 0.5 * (ymx + ymn)) / np.maximum(0.1 * (ymx - ymn), 1e-3), 0, 1)
            gate = np.clip(((qmx - qmn) - 0.2) / 0.1, 0, 1) * gs
            darkc = Y < 0.5 * (ymx + ymn)
            gate = gate * np.clip(gaussian_filter(binary_dilation(darkc, iterations=5).astype(np.float32), 1.0) * 1.3, 0, 1)
            Y2 = Y - gate * rb * np.maximum(Y - (ref + 0.03), 0)
            out = np.clip(O_ * (Y2 / np.maximum(Y, 1e-4))[..., None], 0, 1)
            return out.astype(np.float32)
        OUT = self.local('glow', cscfn, [O, LQ, gate_s], [('glow', (H, W, 3), np.float32)], 72,
                         [GS(1.5), GS(12.0), GS(1.0), 'maximum_filter 31', 'minimum_filter 31', 'binary_dilation it=5'], 120)
        self.free('sg.gate', src_name, 'o8')
        self.progress('glow')
        return OUT

    # --- toe and the stage output plane (B11) ------------------------------------------------------------------------------
    def write_output(self, out, toe_amount, toe_scale, out_plane):
        """to_u8, shadow_toe_u8 and the crop, by row bands, into the stage output plane (u8 [O_stage] x 3)."""
        oh, ow = out_plane.shape[:2]
        V, toe = self.V, self.toe
        if self.table.banded('v4.to_u8', 'shadow_toe_u8'):
            for y0 in range(0, oh, 1152):
                y1 = min(oh, y0 + 1152)
                u8 = toe(V.to_u8(np.asarray(out[y0:y1])), float(toe_amount), float(toe_scale))
                out_plane.write_rows(y0, np.ascontiguousarray(u8[:, :ow]))
        else:
            u8 = toe(V.to_u8(np.asarray(out)), float(toe_amount), float(toe_scale))
            u8 = np.ascontiguousarray(u8[:oh, :ow])
            for y0 in range(0, oh, 1152):
                out_plane.write_rows(y0, u8[y0:y0 + 1152])
        return out_plane

    def close(self):
        self.ws.close()
