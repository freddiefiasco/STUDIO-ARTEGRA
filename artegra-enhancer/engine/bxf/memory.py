"""The finish's own commit, as an upper bound (engine design 2.5 and 6.1; contracts.g1u of build wave 2).

finish_commit_gb(output_size, input_size, band_gb, processes, tier, whole_ops, table=...) bounds the private commit the finish
itself adds to its worker process (and its pool processes) above the worker's own baseline, in GiB:

  tier 3 (5.0.1's v4_finish run whole on the planes): TIER3_GB + TIER3_BPO x O + TIER3_BPI x I, fitted as an upper envelope of
         fresh-process measurements of the whole finish;
  tier 0 (the banded exact finish, BXF): the band term (the budget, or a band over it: band_peak_gb); the fixed parts (the
         float32 PRE and the whole creativity map at I, the classic agree5 strips, the component tables: BXF_GB + BXF_BPO x O
         + BXF_BPI x I, fitted the same way); the pool processes (each its interpreter and at most half a band budget of band
         arrays); and the largest transient of whatever runs whole on mapped planes (T7): every pass, whole-plane op and the
         stage output that the worker's G1 table does not cover at this geometry (whole_passes_for: the band executor's and
         BXF.on's own lookups, from CALLS, WHOLE_CALLS and OUTPUT_OPS), each at its own bytes per pixel over the whole plane.

whole_passes_for(table, output_size, band_gb) names what runs whole; lookups() lists every lookup, so that the start-up
self-probe (engine/bxf/selfprobe.py, G1u) measures exactly the shapes the executor will ask about. O and I are the finish's
output and input (PRE) pixels. Sizes only; the fit's measurements are registered in the finish package's development runs
(wave 2) and checked by tests/test_bxf_memory.py. Pure Python."""

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

# Every local call of the BXF, by pass: ((bytes per output pixel of its band call, its reach in rows, the ops it names besides
# EW), ...); a pass with two calls (clamped: the lead and the mm clamp) lists both. Iteration-numbered passes are written with
# <it>. Recorded from the finish itself in every option case (tests/worker/test_bxf_memory.py checks this table against the
# calls the finish makes). The band executor's decision for a call needs all three: its height comes from its bytes per pixel
# and reach (engine/bxf/local.Runner.would_band), and G1's domain is keyed on that height and the smallest band it reads.
_D = 64.0
CALLS = {
    'acc<it>.0': ((_D, 0, ()),), 'acc<it>.1': ((_D, 0, ()),), 'acc<it>.2': ((_D, 0, ()),), 'acc<it>.3': ((_D, 0, ()),),
    'acc<it>.4': ((_D, 0, ()),), 'cf.core': ((_D, 0, ()),), 'cf.dab': ((80, 4, ('gaussian_filter hwc (1,1,0)',)),),
    'cf.sup': ((_D, 0, ()),), 'cf.w': ((_D, 0, ()),),
    'clamped': ((260, 8, ('gaussian_filter s=1.0', 'gaussian_filter s=2.0', 'v4.chroma_hc2 warm')),          # lead
                (340, 40, ('gaussian_filter s=1.0', 'gaussian_filter s=2.0', 'v4.agreement', 'v4.chroma_mm'))),  # mm
    'eq0': ((24, 11, ('gaussian_filter s=2.8284271247461903',)),),
    'eq1': ((24, 28, ('gaussian_filter s=6.928203230275509',)),), 'eq2': ((_D, 0, ()),), 'eq2.sq': ((_D, 0, ()),),
    'eq3': ((_D, 0, ()),), 'eq3.sq': ((_D, 0, ()),), 'eq4': ((_D, 0, ()),), 'eq4.sq': ((_D, 0, ()),), 'fy': ((_D, 0, ()),),
    'fy2': ((48, 32, ('gaussian_filter s=8.0',)),), 'gc<it>.0': ((_D, 0, ()),), 'gc<it>.1': ((_D, 0, ()),),
    'gc<it>.2': ((_D, 0, ()),), 'gc<it>.3': ((_D, 0, ()),), 'gc<it>.4': ((_D, 0, ()),),
    'gg<it>.0': ((16, 17, ('gaussian_filter s=4.242640687119286',)),),
    'glow': ((120, 72, ('binary_dilation it=5', 'gaussian_filter s=1.0', 'gaussian_filter s=1.5', 'gaussian_filter s=12.0',
                        'maximum_filter 31', 'minimum_filter 31')),),
    'gmq': ((24, 5, ('gaussian_filter s=1.0', 'np.gradient')),), 'gmz': ((_D, 1, ('np.gradient',)),),
    'hw.e01': ((24, 19, ('gaussian_filter s=0.8', 'gaussian_filter s=4.0')),),
    'hw.er': ((40, 40, ('v4.band_energy (1,6,4)',)),), 'hw.es': ((32, 40, ('v4.band_energy (1,6,4)',)),),
    'hw.nsd': ((32, 34, ('binary_dilation it=2', 'gaussian_filter s=6.0', 'gaussian_filter s=8.0')),),
    'hw.rel': ((24, 64, ('gaussian_filter s=16.0', 'gaussian_filter s=8.0')),),
    'hw.strong': ((24, 11, ('binary_dilation it=6', 'maximum_filter chanview 11')),),
    'hw.w': ((24, 14, ('binary_dilation it=4', 'gaussian_filter s=2.5')),),
    'ld<it>.0': ((24, 11, ('gaussian_filter s=2.8284271247461903',)),),
    'ld<it>.1': ((24, 28, ('gaussian_filter s=6.928203230275509',)),), 'ld<it>.2': ((_D, 0, ()),),
    'ld<it>.2.sq': ((_D, 0, ()),), 'ld<it>.3': ((_D, 0, ()),), 'ld<it>.3.sq': ((_D, 0, ()),), 'ld<it>.4': ((_D, 0, ()),),
    'ld<it>.4.sq': ((_D, 0, ()),), 'lf.a1': ((32, 0, ('torch mean(1) of |r - x|',)),),
    'lf.add': ((48, 0, ('torch exact ops',)),), 'lf.d': ((48, 0, ('torch exact ops',)),),
    'lf.dm': ((40, 14, ('torch _blur s=4.0 (_sep conv)',)),), 'lf.mul': ((40, 0, ('torch exact ops',)),),
    'lf.ol': ((60, 0, ('torch exact ops',)),), 'lf.powo': ((36, 0, ('torch pow 1/2.4 channels-last',)),),
    'lf.powx': ((36, 0, ('torch pow 2.4 channels-last',)),), 'lf.pr': ((36, 0, ('torch exact ops',)),),
    'lf.px': ((36, 0, ('torch exact ops',)),), 'lf.rl': ((40, 0, ('torch exact ops',)),),
    'lf.w': ((24, 0, ('torch exp f32',)),), 'lf.wd': ((40, 0, ('torch exact ops',)),),
    'lf.wrl': ((40, 0, ('torch exact ops',)),), 'lf.wxl': ((40, 0, ('torch exact ops',)),),
    'lf.xl': ((40, 0, ('torch exact ops',)),), 'lq': ((_D, 0, ()),), 'lqlab': ((80, 4, ('gaussian_filter hwc (1,1,0)',)),),
    'lt.m': ((24, 52, ('binary_dilation it=40', 'gaussian_filter s=3.0')),),
    'lt.seed': ((80, 7, ('binary_dilation it=3', 'gaussian_filter hwc (1,1,0)')),),
    'lt.w': ((24, 16, ('binary_dilation it=6', 'gaussian_filter s=2.5')),), 'mix': ((_D, 0, ()),), 'mix2': ((_D, 0, ()),),
    'mixlf': ((48, 0, ('torch exact ops',)),), 'mm': ((_D, 0, ()),), 'mt.big': ((8, 80, ('binary_opening it=40',)),),
    'mt.m': ((60, 4, ('binary_dilation it=4',)),),
    'mt.st': ((60, 29, ('gaussian_filter s=1.0', 'gaussian_filter s=6.0', 'np.gradient')),), 'o8': ((_D, 0, ()),),
    'pc': ((_D, 0, ()),), 'po.dis': ((40, 13, ('gaussian_filter s=1.5', 'maximum_filter 15', 'minimum_filter 15')),),
    'po.y2': ((48, 11, ('binary_dilation it=5', 'gaussian_filter s=1.0', 'gaussian_filter s=1.5', 'gaussian_filter s=2.0',
                        'maximum_filter 7', 'minimum_filter 7')),),
    'post': ((260, 8, ('gaussian_filter s=2.0', 'v4.fin_post srcwarm')),), 'sg.cand': ((24, 4, ('gaussian_filter s=1.0',)),),
    'sg.gate': ((24, 7, ('binary_dilation it=3', 'gaussian_filter s=1.0')),), 'sg.s0': ((_D, 0, ()),),
    'sk.br': ((_D, 0, ()),),
    'sk.cand': ((40, 28, ('gaussian_filter s=1.0', 'gaussian_filter s=3.0', 'gaussian_filter s=4.0')),),
    'sk.gaps': ((_D, 0, ()),), 'sk.m': ((24, 8, ('binary_erosion it=2', 'gaussian_filter s=1.5')),),
    'sk.sky1': ((_D, 0, ()),), 'tex': ((_D, 0, ()),), 'tx': ((_D, 0, ()),), 'wisl': ((_D, 0, ()),), 'x': ((80, 0, ()),),
    'x2': ((_D, 0, ()),), 'ycur<it>': ((_D, 0, ()),), 'zone': ((_D, 2, ('binary_dilation it=2',)),),
}
# Every local pass: (its largest band call's bytes per pixel, every op it names besides EW): the one-table form
PASSES = {k: (max(c[0] for c in v), tuple(sorted({o for c in v for o in c[2]}))) for k, v in CALLS.items()}
NARROW_WHOLE = ('lf.dm',)

# Every whole-plane lookup of the finish (node_pack/claude_banded/bxf/finish.py BXF.on: E2-E6 and the E4/E9 out= calls, each on
# the finish plane's own H x W), with the private bytes per output pixel of the classic fallback it runs when the table does
# not cover it, from that fallback's code: tbb's three uniform_filter outputs (two live) and the copy in; g()'s padded copy,
# the order-1 zoom and its float32 crop; one or three float32 channels of F.interpolate or a clone for avg_pool2d; the order-0
# zoom's float64 plane; numpy's copy for a percentile or a median (and the masked values); label's int32 output; bincount's
# intp cast; and torch's pow result with its copy. Recorded from the finish (tests/worker/test_bxf_memory.py); the channels-last
# pow lookups are made only when lf.powx or lf.powo runs whole.
WHOLE_CALLS = {
    'E2 tbb r=1': 12, 'E2 tbb r=3': 12, 'E2 tbb r=8': 12, 'E2 tbb r=24': 12, 'E2 tbb r=64': 12,
    'E3 g s=10.392304845413264': 12, 'E3 g s=16.97056274847714': 12, 'E3 g s=25.45584412271571': 12,
    'E3 g s=48.98979485566356': 12, 'E3 g s=73.48469228349535': 12, 'E3 g s=128.9961239727768': 12,
    'E3 g s=193.49418595916518': 12,
    'E4 avg_pool2d of a mapped input': 12, 'E4 upsample_bicubic2d out=mapped': 12, 'E4 upsample_bilinear2d out=mapped': 8,
    'E4 zoom order=0 f64 out=mapped': 16,
    'E5 median': 12, 'E5 percentile q=35': 8, 'E5 percentile q=75': 8, 'E5 percentile q=98.5': 8,
    'E6 bincount bands': 12, 'E6 label out=mapped': 12,
    'E9 torch pow 2.4 out=mapped contiguous': 24, 'E9 torch pow 2.4 out=mapped channels-last': 24,
    'E9 torch pow 1/2.4 out=mapped channels-last': 24,
}
# The stage output (BXF.write_output): to_u8 and shadow_toe_u8 by 1,152-row bands at reach 0 on the stage output plane, else
# whole: to_u8's float32 clip, scale and offset of three channels, the toe's float32 copy, luma, gain and products, and the crop
# copy (the name 'write_output' stands for it in whole_passes_for)
OUTPUT_OPS, OUTPUT_HEIGHT, OUTPUT_WHOLE_BPP = ('v4.to_u8', 'shadow_toe_u8'), 1152, 64.0


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
    """The local passes that run whole when the ops in whole_ops are whole (and, on a narrow stage, lf.dm). For a table's own
    decision at a stage, use whole_passes_for."""
    w = set(whole_ops or ())
    ew = bool(w & set(EW))
    out = {p for p, (_, ops) in PASSES.items() if ew or (w & set(ops))}
    if output_width is not None and int(output_width) < NARROW_W:
        out |= set(NARROW_WHOLE)
    return sorted(out)


def band_height(width, bytes_per_px, band_gb, reach, height=None):
    """The band executor's height for one call (engine/bxf/local.Runner.would_band): `height` when it is given (a registered
    value every banded pass uses), else the largest registered height whose rows (core + 2 x reach) fit the budget at
    bytes_per_px, or the smallest when none does (engine/bands.band_height_for)."""
    from .. import bands
    if height is not None:
        return bands.check_band_height(int(height))
    return bands.band_height_for(int(width), float(bytes_per_px), float(band_gb) * GIB, int(reach))


def lookups(output_size, band_gb, height=None, output_rows=None):
    """Every G1 table lookup the finish makes on a finish plane of output_size (W, H) at this band budget, as (name, kind,
    ops, geometry, bytes per output pixel when it runs whole): kind 'local' (each call of a pass; name its PASSES key; ops its
    own and EW; the geometry the band executor names), 'plane' (each whole-plane op, on the whole H x W) and 'output'
    (write_output's bands on output_rows rows, default H). The geometry is engine/bxf/g1.Geometry. Pure Python."""
    from .g1 import Geometry
    W, H = (int(v) for v in output_size)
    out = []
    for key, calls in CALLS.items():
        for bpp, reach, ops in calls:
            out.append((key, 'local', tuple(ops) + EW, Geometry(H, W, band_height(W, bpp, band_gb, reach, height), reach),
                        float(bpp)))
    for op, bpp in WHOLE_CALLS.items():
        out.append((op, 'plane', (op,), Geometry(H, W), float(bpp)))
    oh = H if output_rows is None else int(output_rows)
    out.append(('write_output', 'output', OUTPUT_OPS, Geometry(oh, W, OUTPUT_HEIGHT, 0), OUTPUT_WHOLE_BPP))
    return out


def whole_passes_for(table, output_size, band_gb, height=None, output_rows=None):
    """The passes (PASSES keys), whole-plane ops (WHOLE_CALLS names) and 'write_output' that run whole on a finish plane of
    output_size (W, H) with this table and band budget: every lookup the table does not cover (lookups(); the band executor's
    and BXF.on's own decisions, fail closed). table: what engine/bxf/g1.load() returns (a committed table, a local G1u table
    alone or as a veto, several read together) or any object with its banded(*ops, geom=) method. A pass with two calls is
    whole when either is."""
    return sorted({name for name, _, ops, geom, _ in lookups(output_size, band_gb, height, output_rows)
                   if not table.banded(*ops, geom=geom)})


def whole_bytes_per_px(name):
    """The private bytes per output pixel while `name` (a whole_passes_for name) runs whole."""
    if name in PASSES:
        return float(PASSES[name][0])
    if name in WHOLE_CALLS:
        return float(WHOLE_CALLS[name])
    if name == 'write_output':
        return OUTPUT_WHOLE_BPP
    raise KeyError(f'not a pass, whole-plane op or the output of the finish: {name!r}')


def band_peak_gb(output_size, band_gb, whole=(), height=None):
    """The band term: the budget, or the largest band a banded call reads when its estimate (rows read, at most core + 2 x
    reach, at its bytes per pixel) is over the budget even at the smallest registered height (engine/bxf/local.Runner.overrun
    records it; the height stays a registered one). Passes in `whole` read no band."""
    W, H = (int(v) for v in output_size)
    peak = float(band_gb) * GIB
    for key, calls in CALLS.items():
        if key in whole:
            continue
        for bpp, reach, _ in calls:
            h = band_height(W, bpp, band_gb, reach, height)
            peak = max(peak, min(H, h + 2 * int(reach)) * W * float(bpp))
    return peak / GIB


def finish_commit_gb(output_size, input_size, band_gb, processes, tier, whole_ops=(), table=None, height=None,
                     output_rows=None):
    """An upper bound (GiB) of the finish's own commit for a finish plane of output_size (W, H) from a PRE of input_size
    (w, h), at the registered band budget and process count, at tier 3 ('tier3' or 3) or tier 0 ('bxf', 0).

    Tier 0 counts as whole every pass, whole-plane op and the output that the G1 table does not cover at this geometry
    (table: what engine/bxf/g1.load() returns for the worker; whole_passes_for) and, in addition, every one named through
    whole_ops (op names run whole: the passes that call them, the whole-plane ops among them, and the output when to_u8 or the
    toe is among them; on a narrow stage lf.dm). Without a table only whole_ops counts; a planner must pass the table, because
    a table's verdicts alone (its classed-whole ops) do not say where its measured domain ends (fin-chk-1). The calls run one
    at a time, so the whole transient is the largest of them, not their sum; a band over the budget counts at its size."""
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
    w = set(whole_ops or ())
    whole = set(whole_passes(w, output_size[0])) | (w & set(WHOLE_CALLS))
    if w & set(OUTPUT_OPS):
        whole.add('write_output')
    if table is not None:
        whole |= set(whole_passes_for(table, output_size, band_gb, height, output_rows))
    transient = max((whole_bytes_per_px(n) for n in whole), default=0.0) * O / GIB
    return band_peak_gb(output_size, band_gb, whole, height) + fixed + pool + transient


def tier3_gb_per_output_mp():
    """Tier 3's bound per output megapixel at a 2x stage (I = O / 4), for the plan's refit."""
    return (TIER3_BPO + TIER3_BPI / 4) * 1e6 / GIB
