"""The registration record of one row of the proof matrix (engine design 9.2, 7.4), whatever the row's kind: what a packet
builder registers before the row's queue call, from the build itself. Standard library, the build's planner and the graph
builders; no image is read and nothing runs.

Every record holds (contracts.finish_inputs, finish_tier and bolt of the wave-2 plan are read where the build has them):
- build: the git head and the content hashes of the shipped trees and of tools/proof (registration.build_record);
- per run of the row: its plan dict's sha256, the variant constants (finish, canvas, recipe, halo_fix, finish_tier; a
  constant this build's planner does not make is recorded as None, and finish_tier's presence as such), the graph sha256
  per pass (the classic with the identity record's naming; the Large-image graph per prompt with template plane folders
  and run id, PLANE_TEMPLATE and RUN_TEMPLATE, which the run record's own paths replace before it is compared), the
  predicted peaks from the built banded_plan (expected and upper per stage; the classic's from 5.0.1's peak model), the
  time band and the deadline (the card_factor contract);
- for a workstation row: the window's close, the registered end and whether the row ends before the close
  (window_check). A row that does not end before the close is refused here, never queued.
A plan the built planner refuses is recorded as refused with its reason (refused_runs): a packet is never forced by
patching a constant.

row_marks() turns a record into registration marks (one per item, so a moved item is named by registration.verify), and
row_document() into the registration document that registration.write_registration seals and writes once."""
import inspect

from engine import banded_plan, planner
from tools.proof import harness, registration

VARIANT_KEYS = ('finish', 'canvas', 'recipe', 'halo_fix', 'finish_tier')
PLANE_TEMPLATE = '<planes>/s{index}'
RUN_TEMPLATE = '<run>-s{index}{part}'
KINDS = ('phase', 'service', 'cpu_finish', 'r7', 'frozen')
WINDOW_MARGIN_MIN = 30.0         # a workstation row is queued only if its registered end is this long before the close
OVERHEAD_MIN = 15.0              # service start, model loads, the close and the copies, per row
R7_SIZES_GIB = (2, 8, 16)
R7_DISK_GB = 130.0               # under this much free on the work drive, the 1 GP Large-image rows are refused there


def stage_of(plan_stage):
    """The harness Stage of a planner stage (its unpadded input, f, s and index)."""
    return harness.Stage(int(plan_stage.input_size[0]), int(plan_stage.input_size[1]), plan_stage.factor,
                         plan_stage.supersample, int(plan_stage.index))


def variant_constants(plan):
    """The variant constants of a plan: a Large-image plan's from its constants (None where this build's planner makes none),
    a classic plan's as 'classic' (5.0.1's graph builders and finish)."""
    c = plan.banded or {}
    if plan.engine != 'banded':
        return {'engine': 'classic', **{k: None for k in VARIANT_KEYS}, 'finish_tier_in_build': None}
    return {'engine': 'banded', **{k: c.get(k) for k in VARIANT_KEYS}, 'finish_tier_in_build': 'finish_tier' in c,
            'mode': c.get('mode'), 'machine_class': c.get('machine_class'), 'forced': c.get('forced')}


def classic_graph_shas(plan, options='base', seed=None):
    """[sha256 per pass] of a classic plan's stage graphs, with the identity record's naming (harness.classic_graph)."""
    from tools.proof import phase_run
    bp = phase_run.base_params(seed) if seed is not None else None
    return [harness.graph_sha(harness.classic_graph(stage_of(s), options, bp)[0]) for s in plan.stages]


def bes_graph_shas(plan, options='base', seed=None):
    """[{part: sha256}] per pass of a Large-image plan: each prompt's graph (parts A and B of a split stage, else None) with
    template plane folders and run ids (PLANE_TEMPLATE, RUN_TEMPLATE)."""
    from tools.proof import phase_run
    bp = phase_run.base_params(seed) if seed is not None else None
    out = []
    for s in plan.stages:
        st = stage_of(s)
        pd = PLANE_TEMPLATE.format(index=st.index)
        row = {}
        for part in harness.bes_parts(s):
            g, _ = harness.bes_graph(st, plan, pd, f'{pd}/input.plane', RUN_TEMPLATE.format(index=st.index, part=part or ''),
                                     options, bp, part=part)
            row[str(part)] = harness.graph_sha(g)
        out.append(row)
    return out


def plan_record(plan, cap, executor=None, options='base', seed=None, card_factor=1.0, time_band=registration.TIME_BAND):
    """One run's plan record: the plan dict's sha256, the variant constants, the graph sha256 per pass, and per stage the
    peaks, time band and deadline. A refused plan gives {'refused': reason} with its sha256 only."""
    d = plan.to_dict()
    rec = {'engine': plan.engine, 'executor': executor or ('bes' if plan.engine == 'banded' else 'classic'),
           'plan_dict_sha256': registration.sha(d), 'variant_constants': variant_constants(plan), 'options': options,
           'seed': seed, 'cap_gb': float(cap)}
    if not plan.ok:
        return dict(rec, refused=plan.reason or 'refused')
    marks = registration.plan_marks(plan, cap, card_factor=card_factor, time_band=time_band)
    if plan.engine == 'banded':
        rec['graph_sha256_per_pass'] = bes_graph_shas(plan, options, seed)
    else:
        rec['graph_sha256_per_pass'] = classic_graph_shas(plan, options, seed)
        for row, st in zip(marks['stages'], plan.stages):
            row['peak_model_gb'] = round(planner.stage_peak(st), 1)          # 5.0.1's peak model (the classic's bound)
    rec.update(machine_class=marks['machine_class'], admit_gb=marks['admit_gb'], card_factor=marks['card_factor'],
               stages=marks['stages'], minutes=plan.minutes,
               minutes_upper=round(sum(s['time_band_min'][1] for s in marks['stages']), 1),
               deadline_s=sum(s['deadline_s'] for s in marks['stages']))
    if plan.engine == 'banded':
        rec.update(service_gb=marks['service_gb'], worker_bound_rule=marks['worker_bound_rule'])
    return rec


def classic_plan(width, height, factor, cap):
    """5.0.1's plan (plan_501) at the cap, with 5.0.2's honest minutes: the classic engine's plan as the 5.0.2 build makes
    it for an image 5.0.1 accepts."""
    return planner.with_times(planner.plan_501(width, height, factor, ram_cap_gb=cap))


def forced(classic, cap, mode=None):
    """plan_forced of a classic plan (the developer force switch), with the run mode only where the build takes one
    (contracts.bolt); a Bolt mode in a build without banded Bolt is refused in plain words."""
    if mode is None or mode in ('standard', 'redux'):
        if mode is not None and 'mode' in inspect.signature(banded_plan.plan_forced).parameters:
            return banded_plan.plan_forced(classic, cap, mode=mode)
        return banded_plan.plan_forced(classic, cap)
    if 'mode' not in inspect.signature(banded_plan.plan_forced).parameters:
        return planner.Plan(False, classic.factor, classic.input_size, classic.output_size, engine='banded',
                            reason='banded Bolt is not built in this build (plan_forced takes no run mode: contracts.bolt)')
    return banded_plan.plan_forced(classic, cap, mode=mode)


def production(width, height, factor, cap, mode='redux', proven=None):
    """The Large-image engine's own plan (plan_banded) for an image 5.0.1 refuses at the cap; proven: the developer build's
    BANDED_PROVEN_MP (the packet's dev build sets it; a release build admits nothing)."""
    classic = planner.plan_501(width, height, factor, ram_cap_gb=cap)
    kw = {'mode': mode} if mode != 'redux' else {}
    return banded_plan.plan_banded(width, height, factor, cap, classic=classic, proven=proven, **kw)


def finish_inputs_supported():
    """The finish node inputs of contracts.finish_inputs (band_gb, processes, finish_tier) where this build has them."""
    from engine import graph_banded
    opt = graph_banded.NODE_OPTIONAL.get('CUFinishBanded', ())
    return {k: k in opt for k in ('band_gb', 'processes', 'finish_tier')}


def finish_rerun_record(band_gb, processes, reference, tier=None):
    """A BXF re-run's registered settings (R1f, R3f, W11a, W11b; D7): a second band height and process count from the
    registered sets (engine/bands BAND_BUDGETS_GB, PROCESS_COUNTS), against the stage's own output at 0 differing values.
    Refused in plain words when a value is outside the sets or this build's finish node takes no such input."""
    from engine import bands
    budgets, counts = tuple(getattr(bands, 'BAND_BUDGETS_GB', ())), tuple(getattr(bands, 'PROCESS_COUNTS', ()))
    rec = {'band_gb': float(band_gb), 'processes': int(processes), 'finish_tier': tier, 'reference': reference,
           'registered_sets': {'band_gb': list(budgets), 'processes': list(counts)}, 'inputs_in_build': finish_inputs_supported(),
           'expect': '0 differing values against the reference output'}
    probs = []
    if float(band_gb) not in budgets:
        probs.append(f'band_gb {band_gb} is not in the registered set {list(budgets)}')
    if int(processes) not in counts:
        probs.append(f'processes {processes} is not in the registered set {list(counts)}')
    missing = [k for k, v in rec['inputs_in_build'].items() if not v and (k != 'finish_tier' or tier is not None)]
    if missing:
        probs.append('this build\'s CUFinishBanded takes no ' + ', '.join(missing) + ' (contracts.finish_inputs)')
    if probs:
        rec['refused'] = '; '.join(probs)
    return rec


def r7_record(sizes_gib=R7_SIZES_GIB, disk_gb=R7_DISK_GB):
    return {'sizes_gib': [int(x) for x in sizes_gib], 'disk_threshold_gb': float(disk_gb),
            'rule': 'recorded, no pass or fail: per allocation, the rise of PrivateUsage and of the Job commit against the '
                    f'bytes allocated on the card (the commit-VRAM ratio, sets V); under {disk_gb:g} GB free on the work '
                    'drive, the 1 GP Large-image rows are refused on that node'}


def window_check(queue_epoch, minutes_upper, close_epoch, overhead_min=OVERHEAD_MIN, margin_min=WINDOW_MARGIN_MIN):
    """{'registered_end', 'close', 'ends_before_close', ...}: the row's registered end (queue time + its upper minutes + the
    overhead) must be at least margin_min before the window's close."""
    end = float(queue_epoch) + 60.0 * (float(minutes_upper) + float(overhead_min))
    ok = end <= float(close_epoch) - 60.0 * float(margin_min)
    return {'queue_epoch': float(queue_epoch), 'minutes_upper': float(minutes_upper), 'overhead_min': float(overhead_min),
            'registered_end_epoch': round(end, 1), 'close_epoch': float(close_epoch), 'margin_min': float(margin_min),
            'ends_before_close': bool(ok)}


def row_record(row_id, kind, build, runs, window=None, extra=None):
    """The registration record of one matrix row. runs: {run name: plan_record(...) | finish_rerun_record(...) | r7_record()
    | a frozen packet's tool hashes}. window: window_check(...) for a workstation row (None elsewhere)."""
    if kind not in KINDS:
        raise ValueError(f'kind must be one of {KINDS}')
    rec = {'row': str(row_id), 'kind': kind, 'build': build, 'runs': runs, 'window': window, **(extra or {})}
    rec['refused_runs'] = {k: v['refused'] for k, v in runs.items() if isinstance(v, dict) and v.get('refused')}
    if window is not None and not window.get('ends_before_close'):
        rec['refused_runs']['window'] = 'the row does not end before the window closes'
    rec['buildable'] = not rec['refused_runs']
    return rec


def row_marks(record):
    """Registration marks of a row record: the build, each run's whole record, the window; one mark each."""
    marks = [registration.mark('build', record['build'], 'the run record\'s build equals it (git head, the shipped trees\' '
                                                         'and tools/proof content hashes)')]
    for name, r in sorted(record['runs'].items()):
        marks.append(registration.mark(f'{record["row"]}/{name}', r, 'the run record equals it: plan dict sha256 and '
                                       'variant constants, each pass graph sha256 (template names replaced by the run\'s '
                                       'own), peaks within the upper bound, minutes within the time band, no prompt '
                                       'past its deadline'))
    if record.get('window') is not None:
        marks.append(registration.mark(f'{record["row"]}/window', record['window'], 'queued only when it ends at least '
                                       'margin_min before the window\'s close; the driver stops whatever runs at the '
                                       'close'))
    return marks


def row_document(record, reg_id, extra=None):
    """The registration document of a row (registration.registration over row_marks); seal and write it with
    registration.write_registration, once."""
    return registration.registration(reg_id, record['build'], row_marks(record),
                                     extra=dict({'row': record['row'], 'kind': record['kind'],
                                                 'buildable': record['buildable'], 'refused_runs': record['refused_runs']},
                                                **(extra or {})))
