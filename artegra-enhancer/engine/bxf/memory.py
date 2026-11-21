"""The finish's own commit, as an upper bound (engine design 2.5 and 6.1; contracts.g1u of build wave 2).

finish_commit_gb(output_size, input_size, band_gb, processes, tier, whole_ops) bounds the private commit the finish itself
adds to its worker process (and its pool processes) above the worker's own baseline, in GiB:

  tier 3 (5.0.1's v4_finish run whole on the planes): TIER3_GB + TIER3_BPO x O + TIER3_BPI x I, fitted as an upper envelope of
         fresh-process measurements of the whole finish;
  tier 0 (the banded exact finish, BXF): the band budget; the fixed parts (the float32 PRE and the whole creativity map at I,
         the classic agree5 strips, the component tables: BXF_GB + BXF_BPO x O + BXF_BPI x I, fitted the same way); the pool
         processes (each its interpreter and at most half a band budget of band arrays); and the largest transient of a pass
         that runs whole on mapped planes (T7): a pass runs whole when any op it calls is in whole_ops (the ops this computer's
         table classes whole, or does not cover at this geometry), and its transient is its own bytes per pixel (PASSES, the
         band executor's estimate) over the whole plane. On a narrow stage (output width below NARROW_W, where G1's domain
         for the s = 4 torch conv excludes the small last band) lf.dm runs whole whatever whole_ops says.

O and I are the finish's output and input (PRE) pixels. Sizes only; the fit's measurements are registered in the finish
package's development runs (wave 2) and checked by tests/test_bxf_memory.py. Pure Python."""

GIB = 2 ** 30

# tier 3: the whole finish (fresh-process peaks less the process's inputs-only baseline). Refit on the worker runtime (torch
# 2.14.1, 22 Nov 2026): its small-size intercept is higher (2.10 GiB at a 1.2 MP stage against 1.47 on torch 2.9.1), so
# TIER3_GB rose from 1.5; its per-pixel terms already bound 7.7-73 MP there (0.37-0.39 GiB per output MP measured).
TIER3_GB, TIER3_BPO, TIER3_BPI = 1.8, 480.0, 72.0
# tier 0: the BXF's fixed parts beside the band budget (same method)
BXF_GB, BXF_BPO, BXF_BPI = 0.75, 64.0, 72.0
POOL_PROC_GB = 0.4                      # one pool process: its interpreter, numpy and scipy (engine/banded_plan.POOL_PROC_GB)
NARROW_W = 5600                         # below this output width lf.dm (the s = 4 torch conv) may run whole on a small band

# The ops every local pass also names (node_pack/claude_banded/bxf/finish.py EW; tests check the two agree)
EW = ('np.hypot', 'ufunc exp f32', 'ufunc exp toe f32', 'ufunc tanh f32', 'ufunc arctan2 f32', 'ufunc arctan2 chanview f32',
      'ufunc cos sin f32', 'ufunc cbrt f32', 'ufunc power 2.4 f32', 'ufunc power 1/2.4 f32', 'ufunc power 3 f32',
      'ufunc square sqrt f32', 'ufunc sign f32', 'ufunc remainder degrees f32', 'arith f32', 'reduce channels f32',
      'matmul 3x3 f32', 'v4.luma', 'v4.rgb2lab', 'v4.lab2rgb', 'v4.hsv', 'v4.warm_gate', 'v4.smooth01', 'v4.to_u8')

# Every local pass of the BXF: (bytes per output pixel of its band call, the ops it names besides EW). Iteration-numbered
# passes are written with <it>. Recorded from the finish itself (tests/worker/test_bxf_memory.py checks this table).
_D = 64.0
PASSES = {
    'acc<it>.0': (_D, ()), 'acc<it>.1': (_D, ()), 'acc<it>.2': (_D, ()), 'acc<it>.3': (_D, ()), 'acc<it>.4': (_D, ()),
    'cf.core': (_D, ()), 'cf.dab': (80, ('gaussian_filter hwc (1,1,0)',)), 'cf.sup': (_D, ()), 'cf.w': (_D, ()),
    'clamped': (340, ('gaussian_filter s=1.0', 'gaussian_filter s=2.0', 'v4.agreement', 'v4.chroma_hc2 warm', 'v4.chroma_mm')),
    'eq0': (24, ('gaussian_filter s=2.8284271247461903',)), 'eq1': (24, ('gaussian_filter s=6.928203230275509',)),
    'eq2': (_D, ()), 'eq2.sq': (_D, ()), 'eq3': (_D, ()), 'eq3.sq': (_D, ()), 'eq4': (_D, ()), 'eq4.sq': (_D, ()),
    'fy': (_D, ()), 'fy2': (48, ('gaussian_filter s=8.0',)),
    'gc<it>.0': (_D, ()), 'gc<it>.1': (_D, ()), 'gc<it>.2': (_D, ()), 'gc<it>.3': (_D, ()), 'gc<it>.4': (_D, ()),
    'gg<it>.0': (16, ('gaussian_filter s=4.242640687119286',)),
    'glow': (120, ('binary_dilation it=5', 'gaussian_filter s=1.0', 'gaussian_filter s=1.5', 'gaussian_filter s=12.0',
                   'maximum_filter 31', 'minimum_filter 31')),
    'gmq': (24, ('gaussian_filter s=1.0', 'np.gradient')), 'gmz': (_D, ('np.gradient',)),
    'hw.e01': (24, ('gaussian_filter s=0.8', 'gaussian_filter s=4.0')), 'hw.er': (40, ('v4.band_energy (1,6,4)',)),
    'hw.es': (32, ('v4.band_energy (1,6,4)',)), 'hw.nsd': (32, ('binary_dilation it=2', 'gaussian_filter s=6.0',
                                                                'gaussian_filter s=8.0')),
    'hw.rel': (24, ('gaussian_filter s=16.0', 'gaussian_filter s=8.0')),
    'hw.strong': (24, ('binary_dilation it=6', 'maximum_filter chanview 11')),
    'hw.w': (24, ('binary_dilation it=4', 'gaussian_filter s=2.5')),
    'ld<it>.0': (24, ('gaussian_filter s=2.8284271247461903',)), 'ld<it>.1': (24, ('gaussian_filter s=6.928203230275509',)),
    'ld<it>.2': (_D, ()), 'ld<it>.2.sq': (_D, ()), 'ld<it>.3': (_D, ()), 'ld<it>.3.sq': (_D, ()), 'ld<it>.4': (_D, ()),
    'ld<it>.4.sq': (_D, ()),
    'lf.a1': (32, ('torch mean(1) of |r - x|',)), 'lf.add': (48, ('torch exact ops',)), 'lf.d': (48, ('torch exact ops',)),
    'lf.dm': (40, ('torch _blur s=4.0 (_sep conv)',)), 'lf.mul': (40, ('torch exact ops',)), 'lf.ol': (60, ('torch exact ops',)),
    'lf.powo': (36, ('torch pow 1/2.4 channels-last',)), 'lf.powx': (36, ('torch pow 2.4 channels-last',)),
    'lf.pr': (36, ('torch exact ops',)), 'lf.px': (36, ('torch exact ops',)), 'lf.rl': (40, ('torch exact ops',)),
    'lf.w': (24, ('torch exp f32',)), 'lf.wd': (40, ('torch exact ops',)), 'lf.wrl': (40, ('torch exact ops',)),
    'lf.wxl': (40, ('torch exact ops',)), 'lf.xl': (40, ('torch exact ops',)), 'lq': (_D, ()),
    'lqlab': (80, ('gaussian_filter hwc (1,1,0)',)), 'lt.m': (24, ('binary_dilation it=40', 'gaussian_filter s=3.0')),
    'lt.seed': (80, ('binary_dilation it=3', 'gaussian_filter hwc (1,1,0)')),
    'lt.w': (24, ('binary_dilation it=6', 'gaussian_filter s=2.5')), 'mix': (_D, ()), 'mix2': (_D, ()),
    'mixlf': (48, ('torch exact ops',)), 'mm': (_D, ()), 'mt.big': (8, ('binary_opening it=40',)),
    'mt.m': (60, ('binary_dilation it=4',)), 'mt.st': (60, ('gaussian_filter s=1.0', 'gaussian_filter s=6.0', 'np.gradient')),
    'o8': (_D, ()), 'pc': (_D, ()),
    'po.dis': (40, ('gaussian_filter s=1.5', 'maximum_filter 15', 'minimum_filter 15')),
    'po.y2': (48, ('binary_dilation it=5', 'gaussian_filter s=1.0', 'gaussian_filter s=1.5', 'gaussian_filter s=2.0',
                   'maximum_filter 7', 'minimum_filter 7')),
    'post': (260, ('gaussian_filter s=2.0', 'v4.fin_post srcwarm')), 'sg.cand': (24, ('gaussian_filter s=1.0',)),
    'sg.gate': (24, ('binary_dilation it=3', 'gaussian_filter s=1.0')), 'sg.s0': (_D, ()), 'sk.br': (_D, ()),
    'sk.cand': (40, ('gaussian_filter s=1.0', 'gaussian_filter s=3.0', 'gaussian_filter s=4.0')), 'sk.gaps': (_D, ()),
    'sk.m': (24, ('binary_erosion it=2', 'gaussian_filter s=1.5')), 'sk.sky1': (_D, ()), 'tex': (_D, ()), 'tx': (_D, ()),
    'wisl': (_D, ()), 'x': (80, ()), 'x2': (_D, ()), 'ycur<it>': (_D, ()), 'zone': (_D, ('binary_dilation it=2',)),
}
NARROW_WHOLE = ('lf.dm',)


def pass_key(name):
    """A pass's PASSES key: the FIN core's iteration number written <it> (acc2.4 -> acc<it>.4, ld0.3.sq -> ld<it>.3.sq,
    ycur1 -> ycur<it>)."""
    import re
    return re.sub(r'^(acc|ld|gc|gg)\d+\.', r'\1<it>.', re.sub(r'^ycur\d+$', 'ycur<it>', name))


def _px(size):
    w, h = (int(v) for v in size)
    if w <= 0 or h <= 0:
        raise ValueError(f'a size must be positive (got {size})')
    return w * h


def whole_passes(whole_ops, output_width=None):
    """The local passes that run whole when the ops in whole_ops are whole (and, on a narrow stage, lf.dm)."""
    w = set(whole_ops or ())
    ew = bool(w & set(EW))
    out = {p for p, (_, ops) in PASSES.items() if ew or (w & set(ops))}
    if output_width is not None and int(output_width) < NARROW_W:
        out |= set(NARROW_WHOLE)
    return sorted(out)


def finish_commit_gb(output_size, input_size, band_gb, processes, tier, whole_ops=()):
    """An upper bound (GiB) of the finish's own commit for a finish plane of output_size (W, H) from a PRE of input_size
    (w, h), at the registered band budget and process count, at tier 3 ('tier3' or 3) or tier 0 ('bxf', 0), with the ops
    in whole_ops run whole (see the module docstring)."""
    from .. import bands
    O, I = _px(output_size), _px(input_size)
    band_gb = bands.check_band_budget(band_gb)
    processes = bands.check_process_count(int(processes))
    if tier in (3, 'tier3'):
        return (TIER3_GB * GIB + TIER3_BPO * O + TIER3_BPI * I) / GIB
    if tier not in (0, 'bxf'):
        raise ValueError(f"tier must be 'bxf' (0) or 'tier3' (3) (got {tier!r})")
    fixed = (BXF_GB * GIB + BXF_BPO * O + BXF_BPI * I) / GIB
    pool = 0.0 if processes == 1 else processes * (POOL_PROC_GB + band_gb / 2)
    passes = whole_passes(whole_ops, output_size[0])
    transient = max((PASSES[p][0] for p in passes), default=0.0) * O / GIB
    return band_gb + fixed + pool + transient


def tier3_gb_per_output_mp():
    """Tier 3's bound per output megapixel at a 2x stage (I = O / 4), for the plan's refit."""
    return (TIER3_BPO + TIER3_BPI / 4) * 1e6 / GIB
