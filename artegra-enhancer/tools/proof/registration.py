"""Registration of a proof run's marks (engine design 9.2): every mark is written, with its sha256, before its result exists,
and a mark moved after registration is detected. Standard library and the build's planner only.

A registration is a JSON document {'id', 'registered_at', 'build', 'marks': [{'name', 'value', 'rule'}], 'marks_sha256':
{name: sha256 of the mark}, 'sha256': the sha256 of everything else}. The file is written once (never overwritten: a re-run is
a new registration under a new id); its own sha256 is what the run record and the progress notes quote.

Marks the proof registers (9.2), each built here from the build itself:
- build: the git head and a content hash of the shipped trees and of tools/proof;
- plan: the plan dict's sha256 (Plan.to_dict(), with the variant constants finish, canvas, recipe and halo_fix), and per
  stage the predicted peaks (expected and upper, from the built planner: banded_plan.banded_peak_gb once it exists, else
  banded_plan.stage_peaks; the source is recorded), the VRAM bound (banded_vram_gb), the shared-memory bound, the time band
  and the deadline (the card_factor contract: (3 x minutes x cf + 10) x 60 s, cf = max(1, card factor));
  the peaks are the service Job's (they include banded_plan.SERVICE_GB); beside them, the bound of a Job that holds the
  worker alone (worker_peak_upper_gb = peak_upper_gb - SERVICE_GB), and for a split stage each prompt's (parts A and B,
  from the planner's phase bounds); memory_check applies R1's memory mark (MEMORY_RULE) to a run's workers;
- the workers of a Large-image run (build wave 4): worker_layout gives the (stage, part) segments each worker runs, by the
  service's rule (a fresh worker before a stage whose plan sets fresh_worker when the current one has run a prompt, and
  before a split stage's part B); plan_marks registers each worker's bound over its own segments (a fresh worker carries no
  previous finish's retention), and memory_check fails a run whose workers ran other segments;
- graph_sha256 per pass (tools/proof/harness.graph_sha, the identity record's hashing);
- pixels: the expectation and its reference;
- for the blind comparison: the whole case table, seeds, metrics, floors rule and pass rule (tools/proof/metrics)."""
import datetime
import hashlib
import json
import subprocess
from pathlib import Path

from engine import banded_plan

SHIPPED = ('engine', 'node_pack', 'service', 'host', 'ui', 'runtime', 'cu_service.py', 'support_bundle.py')
PROOF = ('tools/proof',)
SKIP_PARTS = ('__pycache__', '.local', '.pytest_cache')
SHARED_BOUND_GB = 0.5          # 9.2 R1: shared GPU memory <= 0.5 GiB per process
TIME_BAND = 0.30               # 9.2 R2: time within +-30 % of the planned minutes (registered per row)


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf8')


def sha(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


def file_sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def tree_sha256(root, parts=SHIPPED):
    """A content hash of files under root/<part> (relative path and sha256 of each, sorted; caches skipped)."""
    root = Path(root)
    rows = []
    for part in parts:
        p = root / part
        files = [p] if p.is_file() else sorted(x for x in p.rglob('*') if x.is_file()) if p.is_dir() else []
        for f in files:
            rel = f.relative_to(root).as_posix()
            if any(s in rel.split('/') for s in SKIP_PARTS) or f.suffix == '.pyc':
                continue
            rows.append([rel, file_sha(f)])
    return {'sha256': sha(rows), 'files': len(rows)}


def git_head(root):
    try:
        return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def build_record(root):
    """The build a run uses: its git head (None for an exported tree), its channel, the shipped trees' and the proof tools'
    content hashes."""
    root = Path(root)
    text = (root / 'service' / 'build_channel.py').read_text(encoding='utf8') if (root / 'service' / 'build_channel.py').is_file() else ''
    channel = 'dev' if "CHANNEL = 'dev'" in text else 'release' if "CHANNEL = 'release'" in text else None
    return {'git_head': git_head(root), 'channel': channel, 'tree': tree_sha256(root, SHIPPED),
            'proof_tools': tree_sha256(root, PROOF)}


def stage_peaks(st, mclass, split):
    """(expected GiB, upper GiB, binding phase, source) from the built planner."""
    f = getattr(banded_plan, 'banded_peak_gb', None)
    note = ''
    if f is not None:
        try:
            r = f(st, mclass, split)
            if isinstance(r, dict) and 'expected' in r and 'upper' in r:
                return float(r['expected']), float(r['upper']), r.get('phase'), 'banded_plan.banded_peak_gb'
            note = f' (banded_peak_gb returned {type(r).__name__} without expected and upper)'
        except TypeError as e:
            note = f' (banded_peak_gb(stage, machine class, split) failed: {e})'
    pk = banded_plan.stage_peaks(st, mclass, split)
    return float(pk['exp'][0]), float(pk['up'][0]), pk['up'][1], 'banded_plan.stage_peaks' + note


PART_PHASES = {'A': ('P0', 'sampling', 'decode'), 'B': ('finish',)}   # the prompts of a split stage (L3r)
WORKER_BOUND_RULE = ("the peak upper bounds are of the service's Job (banded_plan.stage_peaks: the worker's phases plus "
                     "banded_plan.SERVICE_GB for the service process). A Job that holds a ComfyUI worker alone, as the "
                     "phase-diff harness's does, is bounded by worker_peak_upper_gb = peak_upper_gb - service_gb; a split "
                     "stage's two prompts run on two workers, each bounded by its part's worker_peak_upper_gb.")


def part_peaks(st, mclass):
    """The upper service-Job peaks of the two prompts of a split stage (its finish in a fresh worker): part A (P0, sampling
    and the decodes, on the worker that loaded the models) and part B (the finish, on the fresh worker), from the built
    planner's phase bounds. Returns ({part: {'phases', 'peak_upper_gb', 'binding_phase'}}, source)."""
    def complete(ph):
        return isinstance(ph, dict) and all(p in ph for ps in PART_PHASES.values() for p in ps)
    phases, source = None, None
    f = getattr(banded_plan, 'banded_peak_gb', None)
    if f is not None:
        try:
            r = f(st, mclass, True)
            if isinstance(r, dict) and complete(r.get('phases')):
                phases, source = r['phases'], 'banded_plan.banded_peak_gb phases'
        except TypeError:
            pass
    if phases is None:
        pk = banded_plan.stage_peaks(st, mclass, True)
        phases, source = pk.get('phases_up'), 'banded_plan.stage_peaks phases_up'
        if not complete(phases):
            up, ph = pk['up']
            return ({k: {'phases': list(v), 'peak_upper_gb': float(up), 'binding_phase': ph} for k, v in PART_PHASES.items()},
                    'banded_plan.stage_peaks up (no phase bounds: the stage upper for both parts)')
    out = {}
    for part, ps in PART_PHASES.items():
        ph = max(ps, key=lambda p: phases[p])
        out[part] = {'phases': list(ps), 'peak_upper_gb': float(phases[ph]), 'binding_phase': ph}
    return out, source


def plan_marks(plan, cap, card_factor=1.0, shared_bound_gb=SHARED_BOUND_GB, time_band=TIME_BAND):
    """The plan's registered marks: the plan dict's sha256 and variant constants, and per stage the peaks, bounds, time band
    and deadline. plan: a Large-image Plan (banded_plan.plan_banded or plan_forced) or a classic one (no peaks then).
    peak_upper_gb is the service Job's bound; worker_peak_upper_gb (and each part's, for a split stage) is the bound of a Job
    that holds the worker alone (WORKER_BOUND_RULE)."""
    d = plan.to_dict()
    cf = max(1.0, float(card_factor))
    c = plan.banded or {}
    mclass = c.get('machine_class') or banded_plan.machine_class(cap)
    svc = float(banded_plan.SERVICE_GB)
    stages = []
    for st in plan.stages:
        row = {'index': st.index, 'factor': st.factor, 'supersample': st.supersample, 'render_size': list(st.render_size),
               'output_size': list(st.output_size), 'minutes': st.minutes,
               'time_band_min': [round(st.minutes * (1 - time_band), 1), round(st.minutes * (1 + time_band), 1)],
               'deadline_s': round((3 * st.minutes * cf + 10) * 60)}
        if plan.engine == 'banded':
            split = bool(getattr(st, 'split_finish', False))
            exp, up, phase, source = stage_peaks(st, mclass, split)
            row.update(split_finish=split, peak_expected_gb=round(exp, 2), peak_upper_gb=round(up, 2), binding_phase=phase,
                       peak_source=source, vram_bound_gb=round(banded_plan.banded_vram_gb(st), 2),
                       shared_bound_gb=float(shared_bound_gb), worker_peak_upper_gb=round(up - svc, 2),
                       fresh_worker=bool(getattr(st, 'fresh_worker', False)))
            if split:
                parts, psource = part_peaks(st, mclass)
                row['parts'] = {k: dict(v, peak_upper_gb=round(v['peak_upper_gb'], 2),
                                        worker_peak_upper_gb=round(v['peak_upper_gb'] - svc, 2)) for k, v in parts.items()}
                row['parts_source'] = psource
        stages.append(row)
    out = {'engine': plan.engine, 'plan_dict_sha256': sha(d), 'constants': {k: c.get(k) for k in ('finish', 'canvas',
                                                                                                   'recipe', 'halo_fix')},
           'machine_class': mclass, 'cap_gb': float(cap), 'card_factor': cf, 'admit_gb': plan.peak_ram_gb, 'stages': stages}
    if plan.engine == 'banded':
        out.update(service_gb=svc, worker_bound_rule=WORKER_BOUND_RULE)
        out['workers'] = worker_bounds(out)
        out['worker_layout_rule'] = WORKER_LAYOUT_RULE
    return out


# --- build wave 4: the workers of a Large-image run (contracts.restart) ---------------------------------------------------
WORKER_LAYOUT_RULE = ("the workers of a Large-image run, as the service starts them (service/banded_runner.run_stage, "
                      "contracts.restart) and the proof harness follows (tools/proof/phase_run): the run's first worker; "
                      "before a stage whose plan sets fresh_worker, a fresh worker when the current one has run a prompt "
                      "(none when it is fresh); before a split stage's part B, a fresh worker. A split stage with the flag "
                      "restarts before A and before B. Each worker is bounded by the largest worker_peak_upper_gb of its own "
                      "segments; a fresh worker carries no previous finish's retention (the stage's own bound counts none)")


def _stage_flags(st):
    get = (lambda k, d=None: st.get(k, d)) if isinstance(st, dict) else (lambda k, d=None: getattr(st, k, d))
    return int(get('index')), bool(get('split_finish', False)), bool(get('fresh_worker', False))


def fresh_before(stage, segments_run):
    """True when a stage (a plan stage or a plan_marks row) starts in a fresh worker although the current worker exists:
    the plan sets fresh_worker and the current worker has run a prompt (segments_run: the segments it ran)."""
    return _stage_flags(stage)[2] and bool(segments_run)


def worker_layout(stages):
    """The (stage, part) segments each worker of a Large-image run runs (WORKER_LAYOUT_RULE), in order: a list per worker of
    [stage index, part] (part None for an unsplit stage, 'A' or 'B' for a split one). stages: plan stages or plan_marks rows,
    with index, split_finish and fresh_worker (absent is False)."""
    workers = [[]]
    for st in stages:
        index, split, _ = _stage_flags(st)
        if fresh_before(st, workers[-1]):
            workers.append([])
        for part in (('A', 'B') if split else (None,)):
            if part == 'B':
                workers.append([])
            workers[-1].append([index, part])
    return workers


def worker_bounds(marks):
    """Per worker of the layout (worker_layout of the marks' stages): its segments and its worker-only bound, the largest
    worker_peak_upper_gb of its own segments (segment_bound_gb); None where a segment has no bound."""
    out = []
    for n, segs in enumerate(worker_layout(marks['stages'])):
        bounds = [segment_bound_gb(marks, s, p) for s, p in segs]
        out.append({'n': n, 'segments': segs,
                    'worker_peak_upper_gb': None if any(b is None for b in bounds) else max(bounds)})
    return out


def _segments(segs):
    return [[int(s), None if p is None else str(p)] for s, p in (segs or [])]


def segment_bound_gb(marks, stage_index, part):
    """The worker-only bound of one (stage, part) segment: the part's for a split stage, the stage's for an unsplit one;
    None for a segment the plan does not make (a split stage run as one prompt, or a part of an unsplit stage)."""
    row = next((s for s in marks['stages'] if s['index'] == stage_index), None)
    if row is None or 'worker_peak_upper_gb' not in row:
        return None
    if bool(row.get('split_finish')) != (part is not None):
        return None
    if part is None:
        return row['worker_peak_upper_gb']
    return ((row.get('parts') or {}).get(part) or {}).get('worker_peak_upper_gb')


MEMORY_RULE = ("each Large-image (BES) harness worker's Job peak commit (PeakJobMemoryUsed of the worker's own Job: the "
               "ComfyUI worker process alone, no service process; it includes the cu_proof instrumentation's host buffers, "
               "recorded beside it and never subtracted) <= the largest worker_peak_upper_gb among the (stage, part) segments "
               "that worker ran; a peak that was not measured fails; the classic workers' peaks are recorded, not bounded")


def layout_check(marks, workers):
    """The run's workers against the registered layout (marks['workers'], else worker_layout of its stages): each worker
    ran exactly its segments, in order. A run that did not restart where its plan asks (it ran a fresh stage on the worker
    of the previous one) is not the product's run, whatever its peaks; one that stopped early ran fewer segments."""
    want = [_segments(w['segments']) for w in marks.get('workers') or []] if marks.get('workers') is not None else \
        worker_layout(marks.get('stages') or [])
    ran = [_segments(w.get('segments')) for w in workers or []]
    out = {'rule': WORKER_LAYOUT_RULE, 'registered': want, 'ran': ran, 'pass': ran == want}
    if ran != want:
        out['why'] = (f'the run\'s workers ran {ran}, the plan\'s layout is {want}' if ran else
                      'no worker of the run is recorded')
    return out


def memory_check(marks, workers):
    """R1's memory mark over the Large-image run's workers (phase_run's runs['bes']['workers']): per worker, its measured Job
    peak against the largest worker-only bound of the segments it ran (MEMORY_RULE), and the workers' segments against the
    plan's layout (layout_check; build wave 4)."""
    rows, ok = [], bool(workers)
    for w in workers:
        bounds = [segment_bound_gb(marks, s, p) for s, p in w.get('segments') or []]
        bound = None if (not bounds or any(b is None for b in bounds)) else max(bounds)
        peak_b = w.get('job_peak_bytes')
        peak = None if peak_b is None else peak_b / 2 ** 30
        fails = []
        if peak is None:
            fails.append('the Job peak was not measured')
        if bound is None:
            fails.append('no registered bound for a segment this worker ran')
        if peak is not None and bound is not None and peak > bound:
            fails.append('peak over the bound')
        ok = ok and not fails
        rows.append({'worker': w.get('n'), 'segments': w.get('segments'), 'job_peak_commit_gb': None if peak is None else
                     round(peak, 3), 'bound_gb': bound, 'instrument_host_gb_max': w.get('instrument_host_gb_max'),
                     'instrument_commit_delta_gb_max': w.get('instrument_commit_delta_gb_max'), 'fails': fails,
                     'pass': not fails})
    layout = layout_check(marks, workers)
    return {'rule': MEMORY_RULE, 'pass': bool(ok and layout['pass']), 'workers': rows, 'layout': layout}


def mark(name, value, rule):
    return {'name': str(name), 'value': value, 'rule': str(rule)}


def registration(reg_id, build, marks, extra=None):
    names = [m['name'] for m in marks]
    if len(set(names)) != len(names):
        raise ValueError(f'mark names must be unique: {names}')
    return {'id': str(reg_id), 'build': build, 'marks': list(marks), **(extra or {})}


def _body(doc):
    return {k: v for k, v in doc.items() if k not in ('sha256', 'marks_sha256')}


def seal(doc, registered_at=None):
    """The document with registered_at, each mark's sha256 and the document's sha256."""
    d = dict(doc)
    d['registered_at'] = registered_at or d.get('registered_at') or \
        datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
    d['marks_sha256'] = {m['name']: sha(m) for m in d['marks']}
    d['sha256'] = sha(_body(d))
    return d


def write_registration(path, doc, registered_at=None):
    """Seal and write once. Refuses an existing file (FileExistsError). Returns the sha256 of the file written."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(seal(doc, registered_at), indent=1, sort_keys=True, ensure_ascii=False).encode('utf8')
    with open(p, 'xb') as f:
        f.write(data)
    return hashlib.sha256(data).hexdigest()


def verify(doc_or_path):
    """Problems with a sealed registration (empty when every mark and the document still match their sealed hashes)."""
    d = json.loads(Path(doc_or_path).read_text(encoding='utf8')) if not isinstance(doc_or_path, dict) else doc_or_path
    out = []
    sealed = d.get('marks_sha256') or {}
    names = [m['name'] for m in d.get('marks', [])]
    for m in d.get('marks', []):
        if sealed.get(m['name']) != sha(m):
            out.append(f"moved: {m['name']}")
    for n in set(sealed) - set(names):
        out.append(f'removed: {n}')
    if d.get('sha256') != sha(_body(d)):
        out.append('the document does not match its sealed sha256')
    return out


def moved_marks(registered, current):
    """Names of the registered marks whose sealed hash differs in `current` (or that `current` lacks)."""
    a, b = registered.get('marks_sha256') or {}, current.get('marks_sha256') or {}
    return sorted(n for n in a if b.get(n) != a[n])


def registered_before(doc, result_time):
    """True when the registration's time is strictly before a result's ISO time (both timezone-aware)."""
    t0 = datetime.datetime.fromisoformat(doc['registered_at'])
    t1 = datetime.datetime.fromisoformat(result_time)
    return t0 < t1
