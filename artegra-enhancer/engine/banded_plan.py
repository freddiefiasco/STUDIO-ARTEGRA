"""The Large-image engine's planner (5.0.2; engine design ENGINE-DESIGN.md sections 2.1, 2.8, 3.1, 6).

The Large-image engine (the Banded Exact Stage engine, BES) takes ONLY plans that 5.0.1's planner refuses on this computer:
engine/planner.py's plan() calls plan_501 first and comes here only when 5.0.1 refuses the image or its estimate is over the
memory cap. Every plan 5.0.1 accepts, lightened for memory or not, stays on the classic engine (section 3.1; `UNLIGHTEN` is
off). The plan is the same stage maths on every computer (STAGE_FACTORS, the padding units, the render multiple of 8; each
stage takes the full supersample: the largest of 2, 1.5 and 1 whose render is at most 150 MP, else 1). Only the executor
differs.

Admission is on the registered upper bound (section 6.1, the sizing of design-2-evidence/plan_final2.py): 1.05 x the upper
peak must be at most the cap less 1 GiB. A row that fits only the expected model waits for the measured refit (`MEASURED_FIT`,
section 6.3). Nothing is admitted above `BANDED_PROVEN_MP` for the machine class: those figures are the largest outputs the
registered GPU proof passed, and they stay 0 (nothing admitted) until the proof sets them. A developer build may set them
for its own runs (service/build_channel.py).

No plan constant is chosen from free VRAM. Band heights and process counts adapt at run time only within the registered sets
(engine/bands.py).

Build wave 2 (5.0.2):
- THE FINISH TIER. The shipped worker's CUFinishBanded runs the banded exact finish (BXF, tier 0) only where its G1 table
  covers the pass, else tier 3: 5.0.1's whole v4_finish and shadow toe on the planes, up to the pack's FINISH_WHOLE_MAX_MP and
  refused above. A plan therefore counts the tier it will run, as the plan constant 'finish_tier' chosen by BXF_AVAILABLE
  (False until wave 3's start-up probe sets it per machine: fail closed). A 'tier3' plan's finish phase is the registered
  upper bound of the whole finish; above FINISH_WHOLE_MAX_MP, or over the cap, it is refused in plain words that name the size.
  The BXF band budget and process count are the plan constants 'bxf_band_gb' and 'bxf_processes' of the cap's machine class.
  None of the three is a pixel constant (NON_PIXEL_CONSTANTS).
- BANDED BOLT (B16): 2x only, at supersample 2, render <= 150 MP, with the LoRA's weight backup counted; the plan carries the
  installed Fast recipe's name and version as 'recipe'. BOLT_BANDED stays False until R1b and C4 pass.
- THE MODEL'S MISSING TERMS (stage_peaks and banded_minutes, `terms`): lf.dm's whole run on narrow stages, the RGBA viewer
  copies in the service term, CUCannyPlane's private row-band working set; the spot fork's host crop uploads, the lean SAM's
  float32 view per term and the plane band I/O in the minutes. Upper bounds until R2 fits them; with terms=False the model is
  the design's registered one (gate G9).
- No admitted plan is more than TALL_MAX times taller than wide (Pillow 12.3.0, the runtime's, runs its vertical pass first
  past that; engine/lanczos_bands.py does not).

Build wave 3 (5.0.2):
- THE START-UP PROBE, THE PLANNER'S HALF (G1u; contracts.g1u). The service assigns BXF_TABLE (what engine/bxf/g1.load()
  returns for the ENGINE's environment) and BXF_TABLE_SOURCE ('committed', 'local' or 'committed+local'); the planner never
  does. A set BXF_TABLE always decides the finish tier: 'bxf' when it applies, 'tier3' when it does not. Only while it is None
  does BXF_AVAILABLE count (the tests' and the proof harness's override: today's banded-finish figures, no table term); with
  neither, 'tier3' (fail closed). Each plan reads the two once (table_state), so a plan never mixes two tables. A 'bxf' stage
  planned with a table counts at least the finish's own commit bound, engine/bxf/memory.finish_commit_gb(..., table=), in its
  finish phase, never less than wave 2's terms, and records it ('bxf_finish_gb') with the passes, whole-plane ops and output
  that the table runs whole ('bxf_whole_passes', memory.whole_passes_for; the service checks the finish record against it).
  Both are None for a tier-3 stage (the service reads None as absent) and [] / None under the override. The plan constant
  'bxf_table' names the table counted (BXF_TABLE_SOURCE, 'override', or None for tier 3); it changes no pixel
  (NON_PIXEL_CONSTANTS). probe_widths() names the finish-plane widths the probe must measure for an image. A tier-3 plan above
  FINISH_WHOLE_MAX_MP is refused in words that say this computer's processor has not been measured for the engine yet. This
  module imports no torch (tests/test_plan3_g1u.py checks it in a subprocess)."""
import ast as _ast
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from engine import planner as _P
from engine.bxf import memory as _M

BES_VERSION = 'bes-1'
BANDED_MAX_SIDE = 32000                 # Gigapixel's own export limit; the longest side of a Large-image output
ONE_WINDOW_PX = 1024                    # ClaudeSpotTiles' window: a render no larger than one window takes spot.py's one-window path

# Machine classes, from the memory cap (settings.default_ram_cap_gb: 59.0 on 64 GB, 122.2 on 128 GB, 45.2 on 48 GB).
# finish band budget (GiB), finish processes; 32 GB PCs and smaller are not served (Max: "Not yet: 32 GB PCs").
MACHINE_CLASSES = {
    'ws128': {'min_cap': 100.0, 'band_gb': 6.0, 'processes': 4, 'label': '128 GB', 'ram_gb': 128},
    'pc64': {'min_cap': 52.0, 'band_gb': 3.0, 'processes': 2, 'label': '64 GB', 'ram_gb': 64},
    'pc48': {'min_cap': 40.0, 'band_gb': 2.0, 'processes': 1, 'label': '48 GB', 'ram_gb': 48},
}
# The largest output (MP) the registered GPU proof passed per machine class. 0 = nothing proven: the engine admits nothing.
BANDED_PROVEN_MP = {'ws128': 0.0, 'pc64': 0.0, 'pc48': 0.0}

# Switches that would move a plan the Classic engine can run onto the Large-image engine (section 3.1): all off in 5.0.2.
UNLIGHTEN = False                       # plans 5.0.1 lightens for memory
MAX_SAID_BES_TAKES_CAPPED = False       # plans a 5.0.1.x SAM cap refuses
OFFER_AFTER_OOM = False                 # "try again with the Large-image engine" after an out-of-memory failure
BOLT_BANDED = False                     # banded Bolt (B16) is built but not proven: it flips only after R1b and C4 in Prove

# Halo variant constants (section 2.11). bxf-1 is 5.0.1's finish (it keeps 5.0.1's edge halos); bxf-1h exists only after
# the halo branch's fix reads "STATUS: DEV-PROVEN" and is ported (eng:halo-port).
FINISH_VARIANTS = ('bxf-1',)
DEFAULT_FINISH = 'bxf-1'
CANVAS = 'lanczos-1'
RECIPE = 'r501'
HALO_FIX = None

MARGIN = 1.05                           # admission: 1.05 x the upper bound
CAP_SPARE_GB = 1.0                      # and 1 GiB to spare (section 6.3)
MEASURED_FIT = None                     # the refit of R2-R4 (section 6.3), when registered: {'x0', 'xr', 'v_bpr', ...}

# The registered memory model (section 6.1), GiB, sizes in MP. G = GiB per (byte per pixel x MP).
G = 1e6 / 2 ** 30
V0, V_R = 13.5, 2.7 * G                 # VRAM charged as commit at the samplers (classic fit)
VS0, VS_BPR = 15.5, 4.0                 # BES sampler state on the card: 15.5 + 4 B/Rpx (D5)
SAM_VRAM0, SAM_BPI = 15.4, 13.0         # resident set + SAM + one kept mask at I
X0, XR_EXP, XR_UP, XRES = 10.0, 0.010, 0.035, 3.3
DAT_BAND_ROWS = 2048 + 512              # big rows of one DAT tile-row band plus the next band's overlap
DAT_BPX = 16                            # acc 12 + wsum 4 per big px of the live band (L2), plus 0.3 GiB of chunk buffers
SAMPLE_BPR, PREFETCH_BPR = 1.0, 0.5     # CPU latents; one prefetched draw
BROWN_UNCAPPED_BPR, BROWN_CAPPED_BPR = 11.25, 2.0
# G7 (tools/gate_g7.py) on the worker runtime (torch 2.14.1, torchsde 0.2.6), every draw of every variant bit-identical with
# the cache at 8 against torchsde's 45, on 3 latents (1, 6 and 50 MP renders) and 3 seeds each, at KSampler's karras
# schedules of 30 executed steps for SDXL's sigma range: (a) plan2-g7-runtime (wave 2): denoise 1.0, 0.68 and 0.48, 27 of 27
# cases (tests/fixtures/plan2_g7_runtime.json), none of which a Redux Look runs; (b) plan3-g7-redux-looks (wave 3,
# plan-chk-6): every Look's own creative denoise of stages 0-2 and its structure denoise (Light to Extreme, 0.423-0.6448;
# 20 values in 13 distinct schedules), 117 of 117 cases (tests/fixtures/plan3_g7_redux_looks.json). So Redux plans set
# brownian_cache 8 (graph_banded passes it to the fork's brownian_cache input). A Custom recipe's denoise outside those
# schedules was not compared. Only the expected figure falls; the upper X was measured with the full cache in it.
BROWNIAN_CAPPED = True
# Bolt samples 8 executed steps of int(8 / denoise) (fast_recipe), at its Looks' denoise (Light 0.436 / 0.51, Default
# 0.58 / 0.55, detail / structure). G7 on those schedules (dev run plan2-g7-bolt-schedules, wave 3, the worker runtime:
# 36 of 36 cases, every draw of every variant bit-identical with the cache at 8; tests/fixtures/plan3_g7_bolt.json)
# passed, so a Bolt plan caps the cache at 8 too.
BOLT_BROWNIAN_CAPPED = True


def brownian_capped(mode='redux'):
    """True when a plan of this run mode caps the Brownian cache at 8 (its plan constant brownian_cache)."""
    return bool(BROWNIAN_CAPPED and (run_mode(mode) == 'redux' or BOLT_BROWNIAN_CAPPED))
# CUDecodePlane: 3776 rows x 24 B per render column + 0.5 GiB (90,624 B per column), kept above the measured 72,000 B per
# render column + 0.1 GiB (torch 2.9.1 CPU, gpu-nodes) with a 1.26 margin; R2 measures the runtime's allocator.
DEC_ROWS, DEC_BPX = 1088 + 576 + 2112, 24
LABEL_BPO, PRE_F32_BPI, POOL_PROC_GB = 4, 12, 0.4
FIN_RES_EXP_BPO, FIN_RES_UP_BPO = 8, 20
CTX_GB = 0.5                            # CUDA context of the fresh finish worker (L3r)
SERVICE_GB = 1.2                        # service Job above the workers' (1.0 measured, + alpha rows and the live proxy)

# Time (one RTX 5090), seconds per MP; the plane-I/O budget until R2 fits it; a split stage's worker restart and reload.
T_P0_I, T_SAMPLE_R, T_DECODE_R, T_FINISH_O = 20.5, 9.3, 1.04, 6.5
IO_BUDGET = 1.10
SPLIT_MINUTES = 5.0

# Disk: the stage folder at its largest moment, the finish, in bytes per padded-input (I), render (R) and output (O) pixel
# (wave 3; the node pack's plane list, design 2.3). I: the stage-input plane u8 3, the previous stage's file u8 3, big8 (the
# x4 model's output, 4 x each side, kept to the end of the stage) u8 48, the lean SAM's float32 view 12 (held for the stage)
# and up to SAM_PLANES_MAX (26) SAM mask and union planes f32 4 each, 104: 170. R: the canvas f32
# 12 (u8 3 below k = 4), the hint f32 12 and the edges u8 1: 25. O: init, creative, structure and the output u8 3 each, and
# the BXF's scratch planes, 118 B per output px (bxf-g2-1: 7.907 GiB at 73.1 MP and 1.978 GiB at 18.3 MP, 116.1-116.2 B/O;
# recorded as "108 B/O" by reading GiB as GB, which the finish package found in wave 3; its own wave-3 measurement of the
# scratch folder may raise this further through adds.bound_raises): 130.
# Every earlier moment holds less: CUUpscaleCanvas's temporaries come before any R plane but the canvas and before every O plane,
# and CUCannyPlane's three (6 B per R px) before every O plane but init, while the finish holds 108 B per O px and R is at
# most about 4 O. engine/planes.live_bytes is the same formula (tests/test_plan3_refit.py); disk_need adds 10 % on top.
DISK_I, DISK_R, DISK_O = 170, 25, 130
DISK_WAVE2 = (24, 22, 84)               # wave 2's coefficients (C's figure plus 24 B/O of scratch, design 2.3): terms='wave2'


def _pack_finish_whole_max_mp():
    """FINISH_WHOLE_MAX_MP as node_pack/claude_banded/__init__.py assigns it (read here, never imported or edited): the
    largest finish the pack's tier 3 runs. 0.0 when it cannot be read, so no tier-3 plan is admitted (fail closed)."""
    try:
        src = (Path(__file__).resolve().parents[1] / 'node_pack' / 'claude_banded' / '__init__.py').read_text(encoding='utf8')
        for node in _ast.parse(src).body:
            if isinstance(node, _ast.Assign) and any(getattr(t, 'id', None) == 'FINISH_WHOLE_MAX_MP' for t in node.targets):
                return float(_ast.literal_eval(node.value))
    except (OSError, SyntaxError, ValueError, TypeError):
        pass
    return 0.0


# --- the finish tier (build wave 2; contracts finish_tier and finish_inputs) -----------------------------------------------
BXF_AVAILABLE = False                   # the tests' override: 'bxf' with today's figures, counted only while BXF_TABLE is None
BXF_TABLE = None                        # the engine's G1 table (g1.load() for the engine's environment): the service assigns it
BXF_TABLE_SOURCE = None                 # ... and where it came from: one of TABLE_SOURCES (the service assigns it)
TABLE_SOURCES = ('committed', 'local', 'committed+local')
FINISH_TIERS = ('bxf', 'tier3')
FINISH_CONSTANTS = ('bxf_band_gb', 'bxf_processes', 'finish_tier')
# plan constants that change no pixel (resume matching ignores them; finish_inputs): the finish's three and the table counted
NON_PIXEL_CONSTANTS = FINISH_CONSTANTS + ('bxf_table',)
FINISH_WHOLE_MAX_MP = _pack_finish_whole_max_mp()
# Tier 3's own commit, GiB: T3_BASE_GB + T3_BPO bytes per finish pixel (the stage's padded output: the planes tier 3 reads
# whole, as float32, with v4_finish's own arrays) + T3_BPI bytes per input pixel (pre as float32, quantized). The smallest
# round upper bound, with about 10 % to spare, of the whole finish's peak commit measured alone in a fresh process (the
# classic chain of tools/gate_g2.py --measure: 9.48 GiB at 18.3 MP, 19.29 GiB at 38.4 MP of a 32,000 px wide stage, 33.75 GiB
# at 73.2 MP; tests/fixtures/plan2_tier3_measurements.json). The finish phase never takes less than 5.0.1's own measured
# peak model for the stage's sizes either (planner.stage_peak_gb: the envelope of the classic stages that run this finish).
T3_BASE_GB, T3_BPO, T3_BPI = 1.0, 560, 24

# --- banded Bolt (B16; contract bolt) ----------------------------------------------------------------------------------------
MODES = {'redux': 'redux', 'standard': 'redux', 'bolt': 'bolt', 'fast': 'bolt'}   # the service's run modes and the plan's
# Bolt's LoRA weight backup above Redux, at its measured upper value (ENGINE-FACTS 2.6: +5.1 GiB at a 122.5 MP render and
# +7.2 GiB at 156.8 MP; Bolt renders at most 150 MP), in every phase of the worker that loaded it (not in a split stage's
# fresh finish worker).
LORA_GB = 7.2

# --- the memory model's missing terms (merge report item 13) --------------------------------------------------------------
LFDM_BPO = 12                           # lf.dm run whole: 12 B per finish pixel (float32 RGB)
# ... on a stage narrower than this: twice the width below which the worker runtime's tables (engine/bxf/g1_table.py
# TABLES[1], the workstation's class, and TABLES[2], the render nodes') run lf.dm's conv whole at some band geometry: 1,459 px
# (tests/test_plan3_refit.py sweeps lf.dm's own lookups through both tables). Wave 2 had 8,192 from torch 2.9.1's frontier.
LFDM_NARROW_PX = 2918
LFDM_NARROW_WAVE2 = 8192                # wave 2's (terms='wave2')
CANNY_BPC_U8 = 72_000                   # CUCannyPlane's private set per render column: the 2,064-row tile-row block, the two
CANNY_BPC_F32 = 92_000                  # bool rows, the hysteresis band temporaries, the crop (u8 canvas; f32 at k = 4)
CANNY_BPR = 0.5                         # ... and its keep table (measured +1.85-1.95 GiB at 32,000 px, u8, CPU device)
VIEW_COPY_BPC = 21_000                  # one RGBA viewer copy per output column (views-docs V2: 620 MiB at 32,000 px)
VIEW_COPIES = 3                         # SizedPlaneCopies' two at once, and the finish's proxies (write_proxies)

# --- the time model's missing terms (upper bounds until R2 fits them) ----------------------------------------------------
STEPS = 30                              # each sampler's executed steps (controls)
CROP_OVERLAP, CROP_EVALS = 1.5, 2       # window overlap; ControlNet evaluations per step (CFG's group and PAG's)
CROP_BPR = (12 + 12 + 17) * CROP_OVERLAP * CROP_EVALS * STEPS   # B per render px: KS1's hint crops, KS2's hint and edges
HOST_CROP_GBPS = 2.0                    # crop copy, conversion and upload, GB/s
# The most SAM terms a stage runs (graph_banded._sam: one CUSam3DetectLean per term) and the float32 view written and read per
# term (G3). Wave 2 counted 9 (5 protect categories + 4 release terms); a category holds several terms, so with every
# protected area on a stage runs 17 protect terms and 4 release terms (engine/controls.py; tests/test_plan3_refit.py): 21.
SAM_TERMS_MAX, SAM_VIEW_BPI = 21, 24
SAM_TERMS_WAVE2 = 9
# ... and the most mask planes it writes: a mask per term and a union per 8 masks, level by level
# (service/banded_runner.sam_planes over every protected-area choice): 26, f32 4 B per input px each.
SAM_PLANES_MAX = 26
PLANE_IO_PASSES, PLANE_IO_GBPS = 3, 0.5  # every live plane written once and read twice, at a slow work drive's rate

TALL_MAX = 100                          # Pillow 12.3.0 resizes vertically first past 100:1; the banded Lanczos does not

# --- the refit to upper bounds of what is measured (build wave 3; contracts.conservative_bounds and contracts.restart) ------
# stage_peaks(..., terms=True) counts these on top of wave 2's model; terms='wave2' gives wave 2's figures exactly.
PHASES = ('P0', 'sampling', 'decode', 'finish')
# The retained commit each distinct Large-image node leaves in its engine after it returns, with the allocator's defaults
# (eng:wp-2-integ allocator_retention 'alloc-retention', the worker runtime, CPU device; tests/fixtures/plan3_measurements.json:
# CUCannyPlane 1.534, CUEncodePlane 0.205, CUUpscaleCanvas 0.04, CUSam3DetectLean 0.023, CUBlurPlane 0.004, the rest 0.0),
# rounded up: 1.84 GiB (integ's 1.8), by the phase each node runs in. Phase-aware: in an engine that has not run the node
# before, its retention counts from its own phase on (the P0 nodes' order inside P0 is not fixed, so each counts in all of
# P0); in an engine that ran a whole stage before (warm_engine), every node's counts from P0.
ALLOC_NODE_GB = {'CUUpscaleCanvas': ('P0', 0.04), 'CUBlurPlane': ('P0', 0.01), 'CUCannyPlane': ('P0', 1.54),
                 'CUSam3DetectLean': ('P0', 0.03), 'CUEncodePlane': ('sampling', 0.21), 'CUDecodePlane': ('decode', 0.01)}
# ... and CUCannyPlane's CPU-device figures on top, until Prove measures the GPU worker (contracts.conservative_bounds): the
# 0.779 GiB that survives purge delay 0 and gc (cause not identified) and a repeat call's peak above a single call's (0.311 to
# 0.742 GiB), in every phase after Canny. The 0.78 GiB is also inside Canny's 1.54 above: counted twice on purpose (v6 lane).
CANNY_KEPT_GB, CANNY_REPEAT_GB = 0.78, 0.75
# What the previous stage's CUFinishBanded leaves in the engine the next stage starts in (eng:wp-2-integ-fix alloc-finish: two
# calls in one fresh process, the defaults, the worker runtime), by the finish plane's MP up to which it was measured: tier 3
# 0.342 / 2.377 / 6.290 GiB at 18.27 / 36.55 / 73.12 MP (it rises faster than the size, so no rate is carried past 73.12 MP);
# tier 0 0.44 / 0.65 / 0.47 GiB, counted as 0.65 up to 73.12 MP where that finish ran whole only what the measured ones did
# (FINISH_RETAIN_T0_WHOLE: the committed runtime table's lf.pow passes at those widths). Anywhere else it is unmeasured, and
# the next stage starts in a fresh engine instead (its 'fresh_worker'; the service restarts the engine before the stage,
# contracts.restart, and the plan counts SPLIT_MINUTES for it), as it does where counting the retention would bind admission.
# Never neither (MIMALLOC_PURGE_DELAY is ruled out for 5.0.2: contracts.mimalloc).
FINISH_RETAIN_T3 = ((18.27, 0.35), (36.55, 2.38), (73.12, 6.29))
FINISH_RETAIN_T0 = ((73.12, 0.65),)
FINISH_RETAIN_T0_WHOLE = ('lf.powo', 'lf.powr', 'lf.powx')
# Banded Bolt's minutes (B16): its samplers run 8 executed steps (graph_banded.BOLT, fast_recipe.STEPS), the rest of the stage
# at the measured rates; never fewer than the classic Bolt stage's (planner.stage_minutes_502 x the Fast recipe's factor).
BOLT_STEPS = 8
BOLT_ETA_FACTOR = 0.37                  # fast_recipe.RECIPE['eta_factor'] of graph_banded.BOLT_RECIPE (tests check both)


def alloc_gb(phase, warm=False):
    """The engine's retained commit counted in `phase` of a stage (GiB): the distinct nodes' (ALLOC_NODE_GB, phase-aware;
    from P0 in a warm engine) and CUCannyPlane's CPU-device figures from P0 on (CANNY_KEPT_GB, CANNY_REPEAT_GB)."""
    i = PHASES.index(phase)
    nodes = sum(gb for ph, gb in ALLOC_NODE_GB.values() if warm or PHASES.index(ph) <= i)
    return nodes + CANNY_KEPT_GB + CANNY_REPEAT_GB


def finish_retention_gb(st):
    """What a finished stage's CUFinishBanded leaves in its engine (GiB), or None where that is not measured
    (FINISH_RETAIN_T3, FINISH_RETAIN_T0). st: the previous stage (a stage dict or BandedStage, with its finish_tier and
    bxf_whole_passes)."""
    get = _getter(st)
    mp = _mp(finish_size(st))
    if (get('finish_tier') or 'tier3') == 'tier3':
        table = FINISH_RETAIN_T3
    else:
        if not set(get('bxf_whole_passes') or ()) <= set(FINISH_RETAIN_T0_WHOLE):
            return None                 # a mostly whole banded finish: not measured
        table = FINISH_RETAIN_T0
    for up_to, gb in table:
        if mp <= up_to:
            return gb
    return None


@dataclass
class BandedStage(_P.Stage):
    """A stage of a Large-image plan: the classic Stage fields (same meaning) plus its memory and split constants, the finish
    tier and the LoRA backup its bound was counted with (so stage_peaks of the stage alone gives its own figures)."""
    split_finish: bool = False
    peak_expected_gb: float = 0.0
    peak_upper_gb: float = 0.0
    binding_phase: str = ''
    vram_gb: float = 0.0
    disk_gb: float = 0.0
    finish_tier: str = ''
    lora_gb: float = 0.0
    bxf_whole_passes: list = None       # G1u: what the table runs whole (memory.whole_passes_for); [] under the override
    bxf_finish_gb: float = None         # G1u: the finish's own commit bound counted (memory.finish_commit_gb with the table)
    mode: str = 'redux'                 # the plan's run mode ('redux' or 'bolt'): Bolt's minutes are its own (banded_minutes)
    fresh_worker: bool = False          # the stage starts in a fresh engine (contracts.restart; the service restarts it)
    carry_gb: float = 0.0               # the previous stage's finish retention counted in this stage's engine (GiB)
    warm_engine: bool = False           # the stage's engine ran a whole stage before (every node's retention from P0)


def machine_class(cap):
    """The machine class of a memory cap, or None (no cap, or too small for the Large-image engine)."""
    if cap is None:
        return None
    for name, mc in MACHINE_CLASSES.items():
        if float(cap) >= mc['min_cap']:
            return name
    return None


def table_state():
    """(tier, table, source) for a plan made now, read once (contracts.g1u): a set BXF_TABLE decides ('bxf' with that table
    and BXF_TABLE_SOURCE when it applies, else 'tier3'); only while it is None does BXF_AVAILABLE count ('bxf', no table,
    'override'); with neither, ('tier3', None, None)."""
    table, source = BXF_TABLE, BXF_TABLE_SOURCE
    if table is not None:
        return ('bxf', table, source) if getattr(table, 'applies', False) is True else ('tier3', None, None)
    if BXF_AVAILABLE:
        return ('bxf', None, 'override')
    return ('tier3', None, None)


def finish_tier():
    """The finish tier a plan made now counts and asks the node for (table_state): 'bxf' or 'tier3'."""
    return table_state()[0]


def finish_bound(st, mclass, table):
    """(bxf_whole_passes, bxf_finish_gb) of a 'bxf' stage planned with `table` (G1u): what the table runs whole on the stage's
    finish plane (memory.whole_passes_for) and the finish's own commit bound (memory.finish_commit_gb), at the machine class's
    band budget and process count, from the padded input, with the stage output's rows."""
    get = _getter(st)
    mc = MACHINE_CLASSES[mclass]
    fs, rows = finish_size(st), int(get('output_size')[1])
    whole = _M.whole_passes_for(table, fs, mc['band_gb'], output_rows=rows)
    gb = _M.finish_commit_gb(fs, tuple(get('padded_size')), mc['band_gb'], mc['processes'], 'bxf', table=table,
                             output_rows=rows)
    return list(whole), float(gb)


def finish_constants(mclass, tier=None):
    """The plan constants 'bxf_band_gb', 'bxf_processes' (the machine class's registered values) and 'finish_tier'."""
    tier = tier or finish_tier()
    if tier not in FINISH_TIERS:
        raise ValueError(f'unknown finish tier {tier!r}')
    mc = MACHINE_CLASSES[mclass]
    return {'bxf_band_gb': float(mc['band_gb']), 'bxf_processes': int(mc['processes']), 'finish_tier': tier}


def run_mode(mode):
    """'redux' or 'bolt' for the service's run modes ('standard', 'fast') and the plan's own; ValueError otherwise."""
    try:
        return MODES[mode]
    except (KeyError, TypeError):
        raise ValueError(f'unknown run mode {mode!r}') from None


def bolt_recipe():
    """The installed Fast recipe's plan constant, 'name@version' (engine/fast_recipe.py), or None when the Large-image engine
    cannot make it: none is installed, it does not check, or it is not graph_banded.BOLT_RECIPE, the one recipe
    graph_banded.bolt_patch copies (contract bolt; the wave-2 merge's finding: a plan made with another recipe, such as the
    fake engine's CU_FAST_TEST stand-in, was admitted and then refused at the stage for the wrong reason). A Bolt plan is
    then refused in plain words before the start (BOLT_UNAVAILABLE)."""
    from engine import fast_recipe, graph_banded
    try:
        r = fast_recipe.recipe()
    except ValueError:
        return None
    if r is None:
        return None
    name = f"{r['name']}@{r['version']}"
    return name if name == graph_banded.BOLT_RECIPE else None


def _mp(size):
    return size[0] * size[1] / 1e6


def _getter(st):
    return (lambda k, d=None: st.get(k, d)) if isinstance(st, dict) else (lambda k, d=None: getattr(st, k, d))


def finish_size(st):
    """The finish's planes of a stage (its padded output, graph_v5t.stage_sizes' output): (width, height)."""
    get = _getter(st)
    pw, ph = get('padded_size')
    f = Fraction(get('factor')).limit_denominator(8)
    return int(pw * f), int(ph * f)


def tier3_finish_gb(finish_mp, input_mp):
    """Tier 3's own commit (GiB) for a finish of `finish_mp` (the padded output) and a padded input of `input_mp` MP."""
    return T3_BASE_GB + (T3_BPO * float(finish_mp) + T3_BPI * float(input_mp)) * G


def lfdm_gb(st, terms=True):
    """lf.dm's whole run on a narrow stage (the BXF's conv falls outside its clean band geometry there), GiB; else 0. terms:
    True for LFDM_NARROW_PX, 'wave2' for wave 2's width."""
    fw, fh = finish_size(st)
    narrow = LFDM_NARROW_PX if terms is True else LFDM_NARROW_WAVE2
    return LFDM_BPO * G * fw * fh / 1e6 if fw < narrow else 0.0


def canny_gb(st):
    """CUCannyPlane's private row-band working set (GiB): per render column, and its keep table per render pixel."""
    get = _getter(st)
    rw, rh = get('render_size')
    k = float(get('factor')) * float(get('supersample'))
    bpc = CANNY_BPC_F32 if abs(k - 4.0) < 1e-9 else CANNY_BPC_U8
    return (bpc * rw + CANNY_BPR * rw * rh) / 2 ** 30


def service_gb(st):
    """The service Job's term of a stage: SERVICE_GB and its result's RGBA viewer copies at the stage's output width."""
    return SERVICE_GB + VIEW_COPIES * VIEW_COPY_BPC * _getter(st)('output_size')[0] / 2 ** 30


def too_tall(st):
    """True when any of a stage's sizes is more than TALL_MAX times taller than wide."""
    get = _getter(st)
    sizes = [get(k) for k in ('input_size', 'padded_size', 'render_size', 'output_size') if get(k) is not None]
    return any(h > TALL_MAX * w for w, h in sizes + [finish_size(st)])


def stage_choice(cur, f, index):
    """The full-supersample stage for input `cur` and stage factor f: the largest of 2, 1.5 and 1 whose render is at most
    150 MP (planner.RENDER_CAP_MP), else 1. No 16,384 px side limit (the Large-image graph has no ImageScale)."""
    f = Fraction(f)
    for s in _P.SUPERSAMPLES:
        unit = _P._pad_unit(f, s)
        pw, ph = _P._pad_to(cur[0], unit), _P._pad_to(cur[1], unit)
        rw, rh = int(pw * f * s), int(ph * f * s)
        if rw * rh / 1e6 <= _P.RENDER_CAP_MP or s == 1:
            ow, oh = int(cur[0] * f), int(cur[1] * f)
            return dict(index=index, factor=float(f), supersample=float(s), input_size=tuple(cur), padded_size=(pw, ph),
                        render_size=(rw, rh), output_size=(ow, oh))
    raise AssertionError('supersample 1 always fits')


def stage_peaks(st, mclass, split, brownian_capped=None, tier=None, lora_gb=None, terms=True):
    """Peak service-Job commit of one Large-image stage, GiB: {'exp': (gib, phase), 'up': (gib, phase), 'phases_up': {...}}.
    st: a stage dict or Stage (padded_size, render_size, output_size). split: the finish runs in a fresh worker (L3r).
    tier: 'bxf' or 'tier3' (None: the stage's own finish_tier, else finish_tier()); lora_gb: Bolt's LoRA backup (None: the
    stage's own, else 0); terms: True (wave 3: wave 2's terms and the refit's), 'wave2' (wave 2's: lf.dm, Canny, the viewer
    copies) or False (the design's model, G9).
    Wave 3 (terms True; every input is the stage's own, so a stored stage gives its own figures whatever the module holds
    now): a 'bxf' stage's upper finish phase takes the larger of wave 2's finish terms and the finish bound it was planned
    with ('bxf_finish_gb', G1u; none under the override); tier 3's whole finish is the largest of T3, the finish package's
    bound (memory.finish_commit_gb tier 3) and 5.0.1's model; and every phase that runs in the stage's first engine counts the
    retained commit of its nodes (alloc_gb, phase-aware; from P0 when 'warm_engine') and what the previous stage's finish left
    there ('carry_gb'). A split stage's finish runs in a fresh engine, which holds neither."""
    get = _getter(st)
    tier = tier or get('finish_tier') or finish_tier()
    if tier not in FINISH_TIERS:
        raise ValueError(f'unknown finish tier {tier!r}')
    lora = float(get('lora_gb') or 0.0) if lora_gb is None else float(lora_gb)
    if brownian_capped is None:                  # a Bolt stage (its LoRA counted) caps only once Bolt's schedules passed G7
        brownian_capped = BROWNIAN_CAPPED and (lora == 0.0 or BOLT_BROWNIAN_CAPPED)
    capped = brownian_capped
    mc = MACHINE_CLASSES[mclass]
    I, R, O = _mp(get('padded_size')), _mp(get('render_size')), _mp(get('output_size'))
    big_w = 4 * get('padded_size')[0]
    fit = MEASURED_FIT or {}
    v_s = max(V0 + V_R * R, VS0 + fit.get('v_bpr', VS_BPR) * G * R)
    v_p0 = max(v_s, SAM_VRAM0 + SAM_BPI * G * I)
    p0 = DAT_BPX * DAT_BAND_ROWS * big_w / 2 ** 30 + 0.3 + (canny_gb(st) if terms else 0.0)
    brown = (BROWN_CAPPED_BPR if capped else BROWN_UNCAPPED_BPR) + PREFETCH_BPR
    dec = DEC_ROWS * get('render_size')[0] * DEC_BPX / 2 ** 30 + 0.5
    fin_common = (mc['band_gb'] + POOL_PROC_GB * (mc['processes'] - 1) + (LABEL_BPO * O + PRE_F32_BPI * I) * G
                  + (lfdm_gb(st, terms) if terms else 0.0))
    svc = service_gb(st) if terms else SERVICE_GB
    v_fin = CTX_GB if split else v_s
    fin_lora = 0.0 if split else lora            # a split stage's finish runs in a fresh worker, which loads no LoRA
    wave3 = terms is True
    if tier == 'tier3':
        t3 = tier3_finish_gb(_mp(finish_size(st)), I)
        if wave3:                                # (a) the finish package's tier-3 bound, which covers the runtime's 2.10 GiB
            t3 = max(t3, _M.finish_commit_gb(finish_size(st), tuple(get('padded_size')), mc['band_gb'], mc['processes'],
                                             'tier3'))
        classic = _P.stage_peak_gb(R, O, I) - SERVICE_GB     # 5.0.1's model holds its own service share
    carry = float(get('carry_gb') or 0.0) if wave3 else 0.0
    warm = bool(get('warm_engine')) if wave3 else False
    out = {}
    for case, xr in (('exp', XR_EXP), ('up', fit.get('xr', XR_UP))):
        X = fit.get('x0', X0) + xr * R + XRES
        smp = (SAMPLE_BPR + (brown if case == 'exp' else PREFETCH_BPR)) * G * R
        if tier == 'bxf':
            own = fin_common + (FIN_RES_EXP_BPO if case == 'exp' else FIN_RES_UP_BPO) * G * O
            if wave3 and case == 'up' and get('bxf_finish_gb') is not None:
                own = max(own, float(get('bxf_finish_gb')))     # G1u: the finish's own bound with the planned table
            fin = v_fin + X + own + fin_lora
        else:
            fin = v_fin + X + t3 + fin_lora
            if case == 'up':
                fin = max(fin, classic)
        phases = {'P0': v_p0 + X + p0 + lora, 'sampling': v_s + X + smp + lora, 'decode': v_s + X + dec + lora,
                  'finish': fin}
        if wave3:                                # (b), (c): what the stage's first engine holds besides its live sets
            for p in PHASES:
                if not (p == 'finish' and split):
                    phases[p] += carry + alloc_gb(p, warm)
        ph = max(phases, key=phases.get)
        out[case] = (phases[ph] + svc, ph)
        if case == 'up':
            out['phases_up'] = {k: v + svc for k, v in phases.items()}
    return out


def split_needed(st, mclass, cap, tier=None, lora_gb=None, terms=True):
    """L3r per stage (section 2.8): on the 128 GB workstation, every stage whose upper bound the finish phase binds (so a
    second image fits beside it); on a 64 GB or 48 GB PC, a stage whose 1.05 x upper bound without the split is over the cap
    less 1 GiB."""
    up = stage_peaks(st, mclass, False, tier=tier, lora_gb=lora_gb, terms=terms)['up']
    if mclass == 'ws128':
        return up[1] == 'finish'
    return MARGIN * up[0] > float(cap) - CAP_SPARE_GB


def banded_vram_gb(st):
    get = (lambda k: st[k]) if isinstance(st, dict) else (lambda k: getattr(st, k))
    I, R = _mp(get('padded_size')), _mp(get('render_size'))
    return max(VS0 + VS_BPR * G * R, SAM_VRAM0 + SAM_BPI * G * I)


def classic_bolt_minutes(st):
    """The classic Bolt stage's minutes for a stage's sizes, as the service says them: 5.0.2's classic stage minutes
    (planner.stage_minutes_502) x the Fast recipe's factor (BOLT_ETA_FACTOR)."""
    get = _getter(st)
    I, R, O = _mp(get('padded_size')), _mp(get('render_size')), _mp(get('output_size'))
    return _P.stage_minutes_502(R, I, O) * BOLT_ETA_FACTOR


def banded_minutes(st, split, terms=True):
    """One stage on one RTX 5090, minutes: the measured rates of the classic phases, plus the plane-I/O budget, plus a worker
    restart and model load when the finish is split. With terms (wave 2), upper-bound terms until R2 fits them: the spot fork's
    per-window host crop uploads, the lean SAM's float32 view written and read per term, and the plane band I/O. With terms
    True (wave 3): the plane I/O of the refit's disk figure, a restart and model load before a stage that starts in a fresh
    engine ('fresh_worker'), and a Bolt stage ('mode' 'bolt') at Bolt's own rates (its samplers' 8 steps, the crops of 8
    steps), never fewer than the classic Bolt stage's minutes. terms 'wave2' gives wave 2's figure."""
    get = _getter(st)
    I, R, O = _mp(get('padded_size')), _mp(get('render_size')), _mp(get('output_size'))
    wave3 = terms is True
    steps = BOLT_STEPS if wave3 and get('mode') == 'bolt' else STEPS
    secs = T_P0_I * I + (T_SAMPLE_R * steps / STEPS + T_DECODE_R) * R + T_FINISH_O * O
    minutes = secs / 60.0 * IO_BUDGET + (SPLIT_MINUTES if split else 0.0)
    if terms:
        crop = CROP_BPR * steps / STEPS * R * 1e6 / (HOST_CROP_GBPS * 1e9)
        sam = (SAM_TERMS_MAX if wave3 else SAM_TERMS_WAVE2) * SAM_VIEW_BPI * I * 1e6 / (PLANE_IO_GBPS * 1e9)
        io = PLANE_IO_PASSES * banded_disk_gb(st, terms) / PLANE_IO_GBPS
        minutes += (crop + sam + io) / 60.0
    if wave3:
        if get('fresh_worker'):
            minutes += SPLIT_MINUTES
        if get('mode') == 'bolt':
            minutes = max(minutes, classic_bolt_minutes(st))
    return minutes


def banded_disk_gb(st, terms=True):
    """The stage folder's largest size (GB, 1e9 B): DISK_I, DISK_R and DISK_O (wave 3; engine/planes.live_bytes), or wave 2's
    coefficients (terms 'wave2' or False)."""
    get = _getter(st)
    I, R, O = _mp(get('padded_size')), _mp(get('render_size')), _mp(get('output_size'))
    di, dr, do = (DISK_I, DISK_R, DISK_O) if terms is True else DISK_WAVE2
    return (di * I + dr * R + do * O) / 1e3


def constants(mode='redux', finish=None):
    """The plan's pixel-relevant constants, stored on the plan for resumes (section 2.1). mode: a run mode (run_mode); a Bolt
    plan's 'recipe' is the installed Fast recipe's name and version (bolt_recipe)."""
    finish = finish or DEFAULT_FINISH
    if finish not in FINISH_VARIANTS:
        raise ValueError(f'unknown finish variant {finish!r}')
    mode = run_mode(mode)
    recipe = RECIPE
    if mode == 'bolt':
        recipe = bolt_recipe()
        if recipe is None:
            raise ValueError('no Fast recipe this build makes for the Large-image engine is installed')
    return {'bes': BES_VERSION, 'hint_store': 'host', 'finish': finish, 'canvas': CANVAS, 'recipe': recipe,
            'halo_fix': HALO_FIX, 'mode': mode, 'window': 1024, 'dat': [512, 64, 16], 'vae': [1024, 64], 'canny': [2048, 8],
            'encode_state': 'resident', 'brownian_cache': 8 if brownian_capped(mode) else 45, 'cmap': 'mapped',
            'machine_class': None, 'forced': False}


def stage_starts(prev):
    """The ways a stage after `prev` (the previous stage, with its split_finish; None for the first) may start, in the
    order the planner tries them (contracts.restart): in the engine the previous stage's finish ran in, counting what that
    finish left there (finish_retention_gb) when it is measured, and in a fresh engine. Each is the stage's
    {'fresh_worker', 'carry_gb', 'warm_engine'}: an engine that ran the previous stage whole (not split) ran every node of a
    stage before. The first stage has the one way (see the module notes on a job's first stage)."""
    if prev is None:
        return [{'fresh_worker': False, 'carry_gb': 0.0, 'warm_engine': False}]
    out = []
    ret = finish_retention_gb(prev)
    if ret is not None:
        out.append({'fresh_worker': False, 'carry_gb': float(ret), 'warm_engine': not bool(_getter(prev)('split_finish'))})
    out.append({'fresh_worker': True, 'carry_gb': 0.0, 'warm_engine': False})
    return out


def _banded_stages(raw, mclass, cap, tier=None, lora_gb=0.0, table=None, mode='redux'):
    """The Large-image stages of `raw` with their bounds, and each stage's unrounded upper bound (admission compares those:
    plan-chk-1). tier and table: one plan's table_state (a 'bxf' stage planned with a table records and counts the table's
    finish bound, finish_bound; without one, the override's figures). Each stage after the first counts the previous finish's
    retention where it is measured and fits, else starts in a fresh engine (stage_starts): never neither."""
    tier = tier or finish_tier()
    out, uppers, prev = [], [], None
    for st in raw:
        whole, fin_gb = None, None
        if tier == 'bxf':
            whole, fin_gb = finish_bound(st, mclass, table) if table is not None else ([], None)
        base = dict(st, finish_tier=tier, lora_gb=float(lora_gb), bxf_whole_passes=whole, bxf_finish_gb=fin_gb, mode=mode)
        ways = stage_starts(prev)
        for i, way in enumerate(ways):
            st = dict(base, **way)
            split = split_needed(st, mclass, cap, tier=tier, lora_gb=lora_gb)
            pk = stage_peaks(st, mclass, split, tier=tier, lora_gb=lora_gb)
            if MARGIN * pk['up'][0] <= float(cap) - CAP_SPARE_GB or i == len(ways) - 1:
                break
        st['split_finish'] = split
        prev = st
        uppers.append(pk['up'][0])
        out.append(BandedStage(st['index'], st['factor'], st['supersample'], st['input_size'], st['padded_size'],
                               st['render_size'], st['output_size'], round(_mp(st['render_size']), 1),
                               round(banded_minutes(st, split), 1), split_finish=split,
                               peak_expected_gb=round(pk['exp'][0], 1), peak_upper_gb=round(pk['up'][0], 1),
                               binding_phase=pk['up'][1], vram_gb=round(banded_vram_gb(st), 1),
                               disk_gb=round(banded_disk_gb(st), 1), finish_tier=tier, lora_gb=float(lora_gb),
                               bxf_whole_passes=whole, bxf_finish_gb=fin_gb, mode=mode,
                               fresh_worker=bool(st['fresh_worker']), carry_gb=float(st['carry_gb']),
                               warm_engine=bool(st['warm_engine'])))
    return out, uppers


def _table_constant(tier, source):
    """The plan constant 'bxf_table' (non-pixel): the table counted ('committed', 'local', 'committed+local' or
    'override'), None for tier 3."""
    return source if tier == 'bxf' else None


def _refuse(w0, h0, factor, out, reason):
    return _P.Plan(False, factor, (w0, h0), out, reason=reason, engine='banded')


BOLT_UNAVAILABLE = 'Bolt is not available for the Large-image engine in this version.'   # _bolt_reason's first sentence


# Build wave 3 (A10, plan-chk-2, the recorded copy findings): every refusal of this planner names the Large-image engine and
# the size, a computer's memory class says GB, and an article before a number follows how the number is spoken.
def _a(n):
    """'an' before a number spoken with a vowel sound (8, 11, 18, 80-89, 8,000, 11,000, 18,000, ...), else 'a'."""
    d = str(int(round(float(n))))
    return 'an' if d.startswith('8') or (d[:2] in ('11', '18') and len(d) in (2, 5, 8)) else 'a'


def _bolt_reason(which, out):
    """A Bolt refusal of this planner, then Redux for this size: 'unavailable' (BOLT_UNAVAILABLE), 'scale' (2x only) or 'size'
    (a 2x stage above supersample 2's 150 MP render); the first sentences are engine_options' own Bolt refusals."""
    w, h = out
    if which == 'unavailable':
        return f'Bolt is not available for the Large-image engine in this version. Choose Redux to make {w:,} × {h:,} px.'
    if which == 'scale':
        return f'Bolt upscales 2× only. Choose Redux to make {w:,} × {h:,} px with the Large-image engine.'
    return f'Bolt works on images up to about 9 MP. Choose Redux to make {w:,} × {h:,} px with the Large-image engine.'


def _class_reason(out):
    return (f'The Large-image engine cannot make {out[0]:,} × {out[1]:,} px on this computer: it needs a computer with at '
            'least 48 GB of memory.')


def _small_reason(out):
    return f'The Large-image engine cannot make {out[0]:,} × {out[1]:,} px: the image is too small for it.'


def _tall_reason(out):
    return (f'This image is too tall and narrow for the Large-image engine: {out[0]:,} × {out[1]:,} px is more than '
            f'{TALL_MAX} times taller than wide.')


def _tier3_reason(raw, out):
    """The plain refusal of a tier-3 plan whose largest finish is above FINISH_WHOLE_MAX_MP, or None. A plan is tier 3
    because no G1 table applies to this computer's processor (table_state), so the words say so."""
    big = max(_mp(finish_size(st)) for st in raw)
    if big <= FINISH_WHOLE_MAX_MP:
        return None
    return (f'The Large-image engine cannot make {out[0]:,} × {out[1]:,} px on this computer: this computer\'s processor '
            f'has not been measured for the Large-image engine yet, so it can finish a pass of up to '
            f'{FINISH_WHOLE_MAX_MP:.0f} MP here, and this image needs {_a(big)} {big:.0f} MP pass.')


def _memory_reason(admit, cap, out):
    return (f'This image needs about {admit:.0f} GB of memory with the Large-image engine to make {out[0]:,} × {out[1]:,} px, '
            f'more than the {float(cap):.0f} GB it may use on this computer.')


def plan_banded(width, height, factor, cap, classic=None, mode='redux', proven=None, _state=None):
    """The Large-image plan for an image 5.0.1 refuses on this computer, or a refusal (ok False) with the reason. The
    caller (planner.plan) gives 5.0.1's own answer when this refuses. proven: BANDED_PROVEN_MP (tests and developer builds
    pass their own). mode: 'redux' / 'standard' or 'bolt' / 'fast' (Bolt only while BOLT_BANDED). _state: a table_state()
    to plan with (probe_widths' 'bxf'); default: table_state() now, read once."""
    tier, table, source = _state or table_state()
    w0, h0 = int(width), int(height)
    proven = BANDED_PROVEN_MP if proven is None else proven
    mode = run_mode(mode)
    if factor not in _P.STAGE_FACTORS:
        return _refuse(w0, h0, factor, (0, 0), f'The Large-image engine upscales by 2×, 4×, 6× or 8× only, so it cannot '
                                               f'upscale this {w0:,} × {h0:,} px image by {factor}×.')
    out = (w0 * factor, h0 * factor)
    if classic is not None and classic.ok and classic.ram_limited and not UNLIGHTEN:
        pass                    # a lightened plan that fits is classic; one that does not fit is still 5.0.1's to refuse
    if mode == 'bolt' and (not BOLT_BANDED or bolt_recipe() is None):
        return _refuse(w0, h0, factor, out, _bolt_reason('unavailable', out))
    if min(w0, h0) < _P.MIN_SIDE or w0 * h0 / 1e6 > _P.MAX_INPUT_MP:
        return _refuse(w0, h0, factor, out, classic.reason if classic is not None else
                       f'This {w0:,} × {h0:,} px image is outside the sizes the Large-image engine supports.')
    if max(out) > BANDED_MAX_SIDE:
        return _refuse(w0, h0, factor, out, f"{factor}× would make {out[0]:,} × {out[1]:,} px, over the Large-image engine's "
                                            f'{BANDED_MAX_SIDE:,} px limit for the longest side.')
    mclass = machine_class(cap)
    if mclass is None:
        return _refuse(w0, h0, factor, out, _class_reason(out))
    if mode == 'bolt' and factor != 2:
        return _refuse(w0, h0, factor, out, _bolt_reason('scale', out))
    if out[0] * out[1] / 1e6 > float(proven.get(mclass, 0.0)):
        mp = out[0] * out[1] / 1e6
        return _refuse(w0, h0, factor, out, f'The Large-image engine has not yet been measured for {_a(mp)} {mp:.0f} MP '
                                            f'result on a {MACHINE_CLASSES[mclass]["ram_gb"]} GB computer, so it cannot '
                                            f'make {out[0]:,} × {out[1]:,} px here.')
    raw, cur = [], (w0, h0)
    for i, f in enumerate(_P.STAGE_FACTORS[factor]):
        st = stage_choice(cur, f, i)
        if st['render_size'][0] <= ONE_WINDOW_PX and st['render_size'][1] <= ONE_WINDOW_PX:
            return _refuse(w0, h0, factor, out, _small_reason(out))
        raw.append(st)
        cur = st['output_size']
    if any(too_tall(st) for st in raw):
        return _refuse(w0, h0, factor, out, _tall_reason(out))
    if mode == 'bolt' and (raw[0]['supersample'] != 2.0 or _mp(raw[0]['render_size']) > _P.RENDER_CAP_MP):
        return _refuse(w0, h0, factor, out, _bolt_reason('size', out))
    if tier == 'tier3':
        why = _tier3_reason(raw, out)
        if why:
            return _refuse(w0, h0, factor, out, why)
    lora = LORA_GB if mode == 'bolt' else 0.0
    stages, uppers = _banded_stages(raw, mclass, cap, tier, lora, table, mode)
    admit = MARGIN * max(uppers)                # the unrounded upper bound (plan-chk-1); peak_ram_gb shows it rounded
    if admit > float(cap) - CAP_SPARE_GB:
        return _refuse(w0, h0, factor, out, _memory_reason(admit, cap, out))
    c = constants(mode)
    c['machine_class'] = mclass
    c.update(finish_constants(mclass, tier))
    c['bxf_table'] = _table_constant(tier, source)
    return _P.Plan(True, factor, (w0, h0), cur, stages, round(sum(s.minutes for s in stages), 1), round(admit, 1),
                   engine='banded', banded=c)


def probe_widths(width, height, factor, cap, mode='standard', proven=None):
    """The finish-plane widths (int px, sorted, distinct) the start-up probe must measure for this image (G1u): those of the
    stages its Large-image plan would have under the banded exact finish (planned as the override plans, with no table term:
    a table can only run more whole, never admit more), whatever BXF_TABLE is now; [] where no Large-image plan of that size
    exists (5.0.1 runs it, it is refused before any finish is counted, or it does not fit even so). Routed as planner.plan
    routes, with the service's run modes; proven: as plan_banded's."""
    try:
        mode = run_mode(mode)
    except ValueError:
        return []
    p = _P.with_times(_P.plan_501(width, height, factor, ram_cap_gb=cap)) if cap is not None else None
    if cap is None or (p.ok and p.peak_ram_gb <= float(cap)):
        return []
    q = plan_banded(width, height, factor, float(cap), classic=p, mode=mode, proven=proven, _state=('bxf', None, 'override'))
    return plan_finish_widths(q) if q.ok else []


def plan_finish_widths(plan):
    """The distinct finish-plane widths (int px, sorted) of a Large-image plan (a Plan or its stored dict): every width its
    finish runs at, for the probe and the service's check that a local table covers a plan. [] for a classic plan."""
    if not is_banded(plan):
        return []
    stages = plan.get('stages') if isinstance(plan, dict) else plan.stages
    return sorted({int(finish_size(s)[0]) for s in stages or []})


def plan_forced(classic, cap, mode='redux', _state=None):
    """DEVELOPER BUILDS ONLY (section 3, G0g): the classic plan's own stages (factors, supersamples, sizes) with the
    Large-image executor, for the 1:1 comparison with the Classic engine on the same plan. The caller checks the build
    channel. Refuses (ok False) when the classic plan is not ok or the forced plan would not fit the cap. mode (contract
    bolt): 'redux' / 'standard', or 'bolt' / 'fast' for Bolt's comparison (R1b, C4): one 2x stage at supersample 2. _state:
    as plan_banded's."""
    tier, table, source = _state or table_state()
    mode = run_mode(mode)
    if not classic.ok:
        return classic
    w0, h0 = classic.input_size[0], classic.input_size[1]
    mclass = machine_class(cap)
    if mclass is None:
        return _refuse(w0, h0, classic.factor, classic.output_size, _class_reason(tuple(classic.output_size)))
    if mode == 'bolt' and bolt_recipe() is None:
        return _refuse(w0, h0, classic.factor, classic.output_size,
                       _bolt_reason('unavailable', tuple(classic.output_size)))
    raw = [dict(index=s.index, factor=s.factor, supersample=s.supersample, input_size=tuple(s.input_size),
                padded_size=tuple(s.padded_size), render_size=tuple(s.render_size), output_size=tuple(s.output_size))
           for s in classic.stages]
    for st in raw:
        if st['render_size'][0] <= ONE_WINDOW_PX and st['render_size'][1] <= ONE_WINDOW_PX:
            return _refuse(w0, h0, classic.factor, classic.output_size, _small_reason(tuple(classic.output_size)))
    if any(too_tall(st) for st in raw):
        return _refuse(w0, h0, classic.factor, classic.output_size, _tall_reason(tuple(classic.output_size)))
    if mode == 'bolt':
        if classic.factor != 2 or len(raw) != 1:
            return _refuse(w0, h0, classic.factor, classic.output_size,
                           _bolt_reason('scale', tuple(classic.output_size)))
        if raw[0]['supersample'] != 2.0 or _mp(raw[0]['render_size']) > _P.RENDER_CAP_MP:
            return _refuse(w0, h0, classic.factor, classic.output_size,
                           _bolt_reason('size', tuple(classic.output_size)))
    if tier == 'tier3':
        why = _tier3_reason(raw, tuple(classic.output_size))
        if why:
            return _refuse(w0, h0, classic.factor, classic.output_size, why)
    lora = LORA_GB if mode == 'bolt' else 0.0
    stages, uppers = _banded_stages(raw, mclass, cap, tier, lora, table, mode)
    admit = MARGIN * max(uppers)                # the unrounded upper bound (plan-chk-1)
    if admit > float(cap) - CAP_SPARE_GB:
        return _refuse(w0, h0, classic.factor, classic.output_size,
                       f'This developer comparison run needs about {admit:.0f} GB of memory with the Large-image engine to '
                       f'make {classic.output_size[0]:,} × {classic.output_size[1]:,} px, more than the {float(cap):.0f} GB it may '
                       'use on this computer.')
    c = constants(mode)
    c.update(machine_class=mclass, forced=True, **finish_constants(mclass, tier))
    c['bxf_table'] = _table_constant(tier, source)
    return _P.Plan(True, classic.factor, tuple(classic.input_size), tuple(classic.output_size), stages,
                   round(sum(s.minutes for s in stages), 1), round(admit, 1), engine='banded', banded=c)


def is_banded(plan):
    """True for a Large-image plan (a Plan or its stored dict); a dict without `engine` is classic (5.0.1's records)."""
    eng = plan.get('engine') if isinstance(plan, dict) else getattr(plan, 'engine', 'classic')
    return eng == 'banded'
