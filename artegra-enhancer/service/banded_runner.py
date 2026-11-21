"""The service side of a Large-image stage and result (engine design sections 2.3, 2.8, 2.10). service/runner.py calls
run_stage() for a stage whose plan says engine 'banded' (one early line in Runner._run_stage) and encode_publish() /
views_from_work() for its result; a classic plan never reaches this module.

A stage:
1. streams the reflect pad of its input into the stage-input plane (stage 0 reads the user's input, at most 80 MP, as 5.0.1
   does; later stages read the previous stage's plane by bands, never whole);
2. builds the Large-image graph (engine/graph_banded.py) with the classic's own options and the memory profile, and the
   static window split on two cards;
3. runs it as one prompt, or, with the split finish (L3r, a plan constant), as prompt A, then stops the worker, starts a
   fresh one of the same build and runs prompt B (the finish, no model loader);
4. validates the output plane's header, size and hash without decoding it, and renames it stage{k}.u8.
The result file is written from the last plane by the streamed writers (service/plane_io.py); the viewer keeps the plane."""
import json
import os
import shutil
import time
import uuid
from fractions import Fraction
from pathlib import Path

import numpy as np

from engine import controls, graph_banded, planes
from engine.lanczos_bands import resize as lanczos_resize
from service import engine_options, images, memory_policy, plane_io

PAD_BAND = 1152
GIB = float(1 << 30)
FINISH_ROWS_GB = 0.2            # a Large-image result's alpha and writer row buffers (part of the 1.2 GiB service term, 6.1)
CLASSIC_FINISH_BPO = 13.0       # a classic result's service memory while it is written (ENGINE-FACTS 2.5: 12-13 B per output px)


def finishing_gb(plan, fmt):
    """The service memory (GiB) of an image writing its result (admission, ENGINE-DESIGN 2.10): a Large-image result's row
    buffers plus, for JPEG, the whole-image encode's transient (plane_io.jpeg_transient_bytes); a classic result's 13 B per
    output pixel."""
    W, H = (int(v) for v in plan.get('output_size') or (0, 0))
    if plan.get('engine') == 'banded':
        return FINISH_ROWS_GB + (plane_io.jpeg_transient_bytes(W, H) / GIB if fmt == 'jpeg' else 0.0)
    return CLASSIC_FINISH_BPO * W * H / GIB


def stage_plane_name(k):
    return f'stage{k}.u8'


def stage_source(work, k):
    """The file a stage reads: input.png for the first, else the previous stage's plane."""
    return work / ('input.png' if k == 0 else stage_plane_name(k - 1))


def _reflect_index(i, n):
    """numpy 'reflect' padding's source index for position i of a padded axis whose image has n samples."""
    if i < n:
        return i
    return 2 * (n - 1) - i


def pad_plane(src, dst, size, band=PAD_BAND):
    """Write the reflect pad of `src` (H x W x 3: a plane or an array) to size=(pw, ph) into plane `dst`, by row bands:
    the same bytes as service.images.pad_reflect on the whole array (numpy 'reflect', the edge sample not repeated)."""
    h, w = src.shape[:2]
    pw, ph = int(size[0]), int(size[1])
    if pw < w or ph < h or pw - w >= w or ph - h >= h:
        raise ValueError(f'cannot reflect-pad {w}x{h} to {pw}x{ph}')
    cols = np.array([_reflect_index(x, w) for x in range(pw)])
    read = src.read_rows if hasattr(src, 'read_rows') else (lambda a, b: src[a:b])
    for y0 in range(0, ph, band):
        y1 = min(ph, y0 + band)
        rows = [_reflect_index(y, h) for y in range(y0, y1)]
        lo, hi = min(rows), max(rows) + 1
        block = read(lo, hi)
        dst.write_rows(y0, block[np.array(rows) - lo][:, cols])
    return dst


def _frac(v):
    return Fraction(v).limit_denominator(8)


def run_stage(r, w, ctx, job, params, k, n, it):
    """One Large-image stage (Runner._run_stage's banded branch). r: the Runner.

    5.0.2 (ENGINE-DESIGN 2.10): a split stage whose prompt-A planes are on disk, complete and valid for this build
    (checkpoint.json: the same constants, sizes, graph and hashes) resumes with prompt B only; a checkpoint this build cannot
    reproduce is refused in plain words and the pass is made again from its input. The live preview starts from a proxy of
    the stage input of at most 2048 px made in bands from the input plane (never a whole-image copy)."""
    from service.runner import ItemFailure, MultiCardWorker
    from service.util import atomic_write_json
    jid, iid = ctx.jid, ctx.iid
    plan = it['plan']
    st = plan['stages'][k]
    consts = plan.get('banded') or {}
    pack = getattr(r, 'banded_pack', None) or {}
    if not pack.get('ok'):
        raise ItemFailure('The Large-image engine is not installed correctly, so this image was not upscaled. Choose Repair '
                          'installation in Settings.', event='banded_pack_invalid', data={'details': pack.get('details')},
                          keep_work=True)
    f, s = _frac(st['factor']), _frac(st['supersample'])
    work = r.cfg.work_dir / jid / iid
    ow, oh = st['output_size']
    rw, rh = st['render_size']
    pw, ph = st['padded_size']
    I, R, O = pw * ph, rw * rh, ow * oh
    r._stage_disk_check(jid, iid, work, planes.disk_need(I, R, O))
    src = stage_source(work, k)
    if not src.is_file():
        raise ItemFailure('The work files for this image are missing. Add the image again and start a new upscale.',
                          event='work_missing', data={'missing': str(src)})
    plane_dir = work / 'planes' / f's{k}'
    in_path = plane_dir / 'input.plane'
    pk = controls.stage_params(params, k)
    run = it.get('run') or r._run_would(None, it, r._item_mode(job, it))
    live_mode = engine_options.live_mode(r.detailed_info()['on'])
    stack = bool(run.get('speed_stack', True))
    prefix = f'cu_{jid}_{iid}_s{k}'
    split = bool(st.get('split_finish'))
    parts = ['A', 'B'] if split else [None]
    shared = isinstance(w, MultiCardWorker)

    def build(part, run_id):
        try:
            graph, info = graph_banded.build_product(
                str(in_path), pw, ph, pk, prefix, plane_dir.as_posix(), run_id, f=f, s=s, constants=consts,
                speed_stack=stack, live_preview=live_mode,
                faster=bool(run.get('faster')) and stack and k in engine_options.faster_stages(plan),
                creative_first=engine_options.creative_first_on(shared=shared), part=part, output_size=(ow, oh))
        except ValueError as e:
            raise ItemFailure(UNBUILDABLE, event='banded_plan_unbuildable', data={'error': str(e), 'constants': consts},
                              keep_work=True)
        if part != 'B':
            graph, info = memory_policy.apply_graph(graph, info, w.memory_profile)
            if shared:
                graph = graph_banded.add_multigpu(graph, len(w.gpus), balance='static')
        expected = (int(round(pw * f)), int(round(ph * f)))
        if tuple(info['output']) != expected or tuple(info['render']) != (rw, rh):
            raise ItemFailure('This image was stopped because of an internal size mismatch. Details are in the log.',
                              event='graph_size_mismatch', data={'info': str(info), 'stage': st})
        return graph, info

    start, info_a, want = 0, None, None
    if split:
        graph_a, info_a = build('A', '')
        want = checkpoint_expect(k, consts, st, graph_a, pack)
        why = checkpoint_problem(plane_dir, want)
        if why is None:
            start = 1
            r.log.info('banded_checkpoint_resume', f'Pass {k + 1} of {n} goes on from its saved first part',
                       job=jid, item=iid, stage=k, data={'plane_dir': str(plane_dir)})
        elif why != CHECKPOINT_MISSING:
            text = checkpoint_refused_text(k, n, why)
            r.log.warn('banded_checkpoint_refused', text, job=jid, item=iid, stage=k, data={'reason': why})
            r.store.update_item(jid, iid, message=text, event='banded_checkpoint_refused', msg=text, data={'reason': why})
    if start == 0:
        shutil.rmtree(plane_dir, ignore_errors=True)
        plane_dir.mkdir(parents=True, exist_ok=True)
        _make_input_plane(src, in_path, st, k, jid, iid)
    in_plane = planes.Plane.open(in_path)
    t0 = time.monotonic()
    pid, canvas, split_rec = None, None, {}
    for i, part in enumerate(parts):
        if i < start:
            continue
        run_id = str(uuid.uuid4())
        graph, info = build(part, run_id)
        atomic_write_json(work / f'stage{k}{part or ""}.graph.json', graph)
        if canvas is None:
            canvas = live_begin(r, ctx, it, k, n, st, info_a if part == 'B' else info, in_plane, plane_dir)
        if part == 'B':
            split_rec = ({'commit_check': 'not restarted'} if start == 1 and worker_is_fresh(w)
                         else restart_worker(r, w, ctx, k, n))
        _mark_started(r, it, jid, iid, k, n, st, w, info, graph, work, part, pk, pw, ph)
        on_queued = (lambda: record_split(r, ctx, k, n, w, split_rec)) if part == 'B' else None
        hist, pid = _run_prompt(r, w, ctx, graph, run_id, k, n, plan, st, prefix, None, canvas=canvas, on_queued=on_queued)
        if part == 'A':
            write_checkpoint(plane_dir, want, in_plane)
    out_path = plane_dir / 'output.plane'
    try:
        out = planes.validate(out_path, shape=(oh, ow, 3), dtype='u8')
    except planes.PlaneError as e:
        raise ItemFailure(f'The engine result for pass {k + 1} of {n} is missing or has the wrong size, so this image was '
                          'stopped.', event='stage_output_plane', data={'error': str(e)})
    final = work / stage_plane_name(k)
    os.replace(out.path, final)
    shutil.rmtree(plane_dir, ignore_errors=True)
    _stage_done(r, ctx, jid, iid, k, n, st, t0, pid)


UNBUILDABLE = ("This image's Large-image plan was made by another version of the app, and this version cannot make it. "
               'Queue the image again.')
COMMIT_SPARE_GB = 1.0            # what the stopped engine may leave in the Job and still pass (ENGINE-DESIGN 2.8, L3r step 3)
COMMIT_EPS_GB = 0.05             # the check waits for the stopped engine's whole commit to leave the Job, within this
COMMIT_SETTLE_S = 60.0           # the longest it waits: Windows takes a process's commit back a little after it exits
COMMIT_POLL_S = 0.05
L3R_EXTRA = ('job_commit_before_gb', 'job_commit_after_gb', 'other_engines_commit_before_gb',
             'other_engines_commit_after_gb', 'commit_check', 'commit_wait_s')


class JobCounters:
    """The commit counters of the split finish (L3r, ENGINE-DESIGN 2.8), read from the Windows Jobs themselves (current
    commit, never a historical peak; service/windows_job.py):
    - job_commit_gb(): the committed memory of the shared Job of all engines now (every engine process and every child of
      one, and commit Windows has not yet taken back from a process that exited); None when there is no shared Job (the fake
      engine in this process, or not Windows) or it cannot be read;
    - process_gb(w): one engine's committed memory now: its own Job's (its process and every child of it), else its
      process's private bytes; None for an engine with no process (stopped, or the fake engine in this process);
    - others_gb(w): the sum over the other live engines;
    - job_peak_gb(w): the Job's PeakJobMemoryUsed (the shared Job when there is one, else the engine's own).
    Tests pass their own Job objects (shared_job, proc)."""

    def __init__(self, r):
        self.r = r

    def _real(self):
        return getattr(self.r, 'mode', 'fake') != 'fake'

    def engines(self):
        return list(getattr(self.r, 'workers', {}).values()) + list(getattr(self.r, 'multi', {}).values())

    def process_gb(self, w):
        proc = getattr(w, 'proc', None)
        if proc is None or not self._real():
            return None
        try:
            b = proc.commit_bytes()
        except Exception:          # the engine's own Job cannot be read: its process's private bytes
            b = None
        return b / GIB if b is not None else memory_policy.process_private_gb(proc.pid)

    def others_gb(self, w):
        return sum(v for v in (self.process_gb(x) for x in self.engines() if x is not w) if v is not None)

    def job_commit_gb(self):
        job = getattr(self.r, 'shared_job', None)
        if job is None or not self._real():
            return None
        try:
            b = job.commit_bytes()
        except Exception:          # unreadable: the check is recorded as unmeasured, never passed
            return None
        return None if b is None else b / GIB

    def job_peak_gb(self, w):
        job = getattr(self.r, 'shared_job', None)
        try:
            if job is not None:
                lim = job.limits()
            else:
                proc = getattr(w, 'proc', None)
                lim = proc.limits() if proc is not None else None
        except Exception:          # a counter that cannot be read is recorded as unknown, never a failure
            return None
        v = (lim or {}).get('peak_job_memory_used')
        return None if v is None else round(v / GIB, 3)


def _gb(v):
    return None if v is None else round(float(v), 3)


def restart_worker(r, w, ctx, k, n, counters=None, settle_s=None):
    """L3r: the finish of this stage runs in a fresh worker of the same build and flags (engine design section 2.8): stop the
    idle worker through its own stop path and wait for its processes to end, check in the shared Job that the stopped
    engine's memory left it (else the stage fails plainly), then start it again.

    The check: commit_fall_gb = (the shared Job's commit before the stop - after it) - (the other engines' commit before -
    after), so another card's engine growing or shrinking meanwhile neither fails nor passes it; it passes when the fall is
    at least the stopped engine's last commit (its own Job: its process and every child) less COMMIT_SPARE_GB. Windows takes
    a process's commit back a little after the process has exited, so the Job is read again until the whole commit has
    left it or COMMIT_SETTLE_S has passed (the wait ends early when the app stops). With no shared Job to read (the fake
    engine in this process, not Windows, or a counter that cannot be read), or a wait cut short by the app stopping before
    the memory came back, the check is recorded as unmeasured: commit_fall_gb None, never a fall from zeros.

    Returns the split's record (contract l3r_record): job_peak_commit_a_end_gb (the Job's PeakJobMemoryUsed read after
    prompt A, before the stop), stopped_worker_last_commit_gb and commit_fall_gb, and (L3R_EXTRA) job_commit_before_gb,
    job_commit_after_gb, other_engines_commit_before_gb, other_engines_commit_after_gb, commit_check ('passed',
    'failed' or 'unmeasured') and commit_wait_s (how long the Job was read after the stop)."""
    from service.runner import EngineNotReady, ItemFailure
    from service.workers import WorkerError
    c = counters or JobCounters(r)
    settle = COMMIT_SETTLE_S if settle_s is None else float(settle_s)
    r.log.info('banded_split_restart', f'Pass {k + 1} of {n}: the finish runs in a fresh engine process',
               job=ctx.jid, item=ctx.iid, stage=k)
    peak_a = c.job_peak_gb(w)
    last = c.process_gb(w)
    job_before = c.job_commit_gb()
    others_before = c.others_gb(w)
    try:
        cleanup = w.stop('banded split finish')
    except Exception as e:      # the stop path reports its own problems; a worker that will not stop fails the stage
        raise ItemFailure('The engine could not be restarted for the last step of this pass.', event='banded_restart_failed',
                          data={'error': str(e)}, kill_worker=True, keep_work=True)
    if isinstance(cleanup, dict) and cleanup.get('all_owned_processes_terminated') is False:
        raise ItemFailure('The engine could not be restarted for the last step of this pass.', event='banded_restart_failed',
                          data={'cleanup': cleanup}, kill_worker=True, keep_work=True)
    rec = {'job_peak_commit_a_end_gb': peak_a, 'stopped_worker_last_commit_gb': _gb(last), 'commit_fall_gb': None,
           'job_commit_before_gb': _gb(job_before), 'job_commit_after_gb': None,
           'other_engines_commit_before_gb': _gb(others_before), 'other_engines_commit_after_gb': None,
           'commit_check': 'unmeasured', 'commit_wait_s': None}
    if job_before is not None and last is not None:
        t0 = time.monotonic()
        end, cut = t0 + settle, False
        while True:
            job_after, others_after = c.job_commit_gb(), c.others_gb(w)
            if job_after is None:
                break
            fall = (job_before - job_after) - (others_before - others_after)
            if fall >= last - COMMIT_EPS_GB or time.monotonic() >= end:
                break
            if getattr(ctx, 'shutdown', False) or not getattr(r, 'accepting', True):
                cut = True             # the app is stopping: the wait ends here, as the engine start below does
                break
            time.sleep(COMMIT_POLL_S)
        rec['commit_wait_s'] = round(time.monotonic() - t0, 2)
        if job_after is not None:
            rec.update(job_commit_after_gb=_gb(job_after), other_engines_commit_after_gb=_gb(others_after))
            if fall >= last - COMMIT_SPARE_GB:
                rec.update(commit_fall_gb=_gb(fall), commit_check='passed')
            elif not cut:
                rec.update(commit_fall_gb=_gb(fall), commit_check='failed')
            # cut short before the memory came back: unmeasured (the wait did not run its course), never failed
    if rec['commit_check'] == 'failed':
        raise ItemFailure(f'The engine did not give its memory back when it was restarted for the last step of pass {k + 1} '
                          f'of {n}, so this image was stopped.', event='banded_restart_memory', data=rec,
                          kill_worker=True, keep_work=True)
    if rec['commit_check'] == 'unmeasured':
        say = r.log.warn if getattr(r, 'mode', 'fake') == 'comfy' else r.log.info
        say('banded_split_commit_unmeasured', f'Pass {k + 1} of {n}: the memory the engine gave back could not be measured',
            job=ctx.jid, item=ctx.iid, stage=k, data=rec)
    try:
        w.ensure_started(r._gpu_lookup() if r.mode == 'comfy' else None, abort=lambda: ctx.shutdown or not r.accepting)
    except WorkerError as e:
        raise EngineNotReady(str(e), ref=(e.detail or {}).get('log_ref') if isinstance(e.detail, dict) else None)
    return rec


def worker_is_fresh(w):
    """True for an engine that is ready and has run no prompt since it started (a resumed prompt B needs no restart)."""
    try:
        return w.state == 'ready' and w.alive() and getattr(w.client, 'prompts_sent', 1) == 0
    except Exception:
        return False


def record_split(r, ctx, k, n, w, rec, counters=None):
    """Just after prompt B is queued: the Job's PeakJobMemoryUsed, and the split's record in the item's timings (part B's
    stage entry) and the log (event banded_split_commit), with the fields proof-tools reads (contract l3r_record) and the
    check's own readings (L3R_EXTRA). A field that was not measured is None, which proof-tools' mark reads as a failure."""
    c = counters or JobCounters(r)
    fields = {'job_peak_commit_a_end_gb': rec.get('job_peak_commit_a_end_gb'),
              'job_peak_commit_b_start_gb': c.job_peak_gb(w),
              'stopped_worker_last_commit_gb': rec.get('stopped_worker_last_commit_gb'),
              'commit_fall_gb': rec.get('commit_fall_gb')}
    fields.update({key: rec.get(key) for key in L3R_EXTRA})
    try:
        it = r.store.item(ctx.jid, ctx.iid)
        timings = dict(it['timings'])
        timings['stages'] = [dict(x, **fields) if (x.get('index') == k and x.get('part') == 'B') else x
                             for x in timings.get('stages', [])]
        r.store.update_item(ctx.jid, ctx.iid, timings=timings)
    except Exception as e:         # the record is for the proof; it never stops the image
        r.log.warn('banded_split_record_failed', f'The split record could not be stored: {e}', job=ctx.jid, item=ctx.iid)
    r.log.info('banded_split_commit', f'Pass {k + 1} of {n}: memory across the split finish', job=ctx.jid, item=ctx.iid,
               stage=k, data=fields)
    return fields


# --- the sub-stage checkpoint (ENGINE-DESIGN 2.10) --------------------------------------------------------------------
CHECKPOINT_FILE = 'checkpoint.json'
CHECKPOINT_VERSION = 1
CHECKPOINT_MISSING = 'missing'


def graph_sha(graph):
    """sha256 of a stage graph with its run ids blanked (each prompt has its own; everything else is the plan's)."""
    from service.util import canonical_json, sha256_bytes
    g = {nid: {'class_type': nd['class_type'], 'inputs': {k: ('' if k == 'run_id' else v) for k, v in nd['inputs'].items()}}
         for nid, nd in graph.items()}
    return sha256_bytes(canonical_json(g))


def checkpoint_roles(graph_a):
    """The roles prompt A's CUPlaneCheckpoint saves (creative, structure, init, and protect / release when present)."""
    node = next((nd for nd in graph_a.values() if nd['class_type'] == 'CUPlaneCheckpoint'), None)
    if node is None:
        return []
    return [role for role in graph_banded.CHECKPOINT_ROLES if role in node['inputs']]


def checkpoint_expect(k, consts, st, graph_a, pack):
    """What a checkpoint of this stage must say to be used by this build."""
    return {'version': CHECKPOINT_VERSION, 'stage': int(k), 'constants': dict(consts),
            'sizes': {key: list(st[key]) for key in ('input_size', 'padded_size', 'render_size', 'output_size')},
            'graph_a_sha': graph_sha(graph_a), 'banded_pack': (pack or {}).get('tree_sha256'),
            'roles': checkpoint_roles(graph_a)}


def write_checkpoint(plane_dir, want, in_plane):
    """After prompt A: the record that says its planes are complete (with their hashes) and what made them."""
    from service.util import atomic_write_json, now_iso
    rec = dict(want, written=now_iso(), input={'file': in_plane.path.name, 'sha256': in_plane.header.get('sha256')},
               planes=[])
    for role in want['roles']:
        p = planes.validate(Path(plane_dir) / f'{role}.plane', check_sha=False)
        rec['planes'].append({'role': role, 'file': p.path.name, 'shape': list(p.shape), 'dtype': p.header['dtype'],
                              'sha256': p.header.get('sha256')})
    atomic_write_json(Path(plane_dir) / CHECKPOINT_FILE, rec)
    return rec


_WHY = {'constants': 'it was made with other Large-image engine settings', 'sizes': 'its sizes are not this pass\'s',
        'graph_a_sha': 'it was made with other settings, another card setup or another build',
        'banded_pack': 'it was made by another build of the Large-image engine', 'roles': 'it does not hold every part needed',
        'stage': 'it belongs to another pass', 'version': 'it was written by another version of the app'}


def checkpoint_problem(plane_dir, want):
    """None when the stage's prompt-A checkpoint can be used by this build: its record matches `want` (constants, sizes,
    graph, build, roles) and the input plane and every saved plane is complete, of its recorded shape and type, and of its
    recorded hash. CHECKPOINT_MISSING when there is none; else the plain reason it cannot be used."""
    path = Path(plane_dir) / CHECKPOINT_FILE
    if not path.is_file():
        return CHECKPOINT_MISSING
    try:
        rec = json.loads(path.read_text(encoding='utf8'))
        if not isinstance(rec, dict):
            raise ValueError('not an object')
    except (OSError, ValueError):
        return 'its record is damaged'
    for key in ('version', 'stage', 'constants', 'sizes', 'banded_pack', 'graph_a_sha', 'roles'):
        if rec.get(key) != want.get(key):
            return _WHY[key]
    ph, pw = want['sizes']['padded_size'][1], want['sizes']['padded_size'][0]
    try:
        p = planes.validate(Path(plane_dir) / 'input.plane', shape=(ph, pw, 3), dtype='u8', check_sha=True)
        if p.header.get('sha256') != (rec.get('input') or {}).get('sha256'):
            return 'its input does not match'
    except planes.PlaneError:
        return 'its input is missing or damaged'
    got = {x.get('role'): x for x in rec.get('planes') or [] if isinstance(x, dict)}
    if sorted(got) != sorted(want['roles']):
        return _WHY['roles']
    for role in want['roles']:
        x = got[role]
        try:
            p = planes.validate(Path(plane_dir) / f'{role}.plane', shape=tuple(x.get('shape') or ()), dtype=x.get('dtype'),
                                check_sha=True)
        except (planes.PlaneError, TypeError, ValueError):
            return f'its {role} part is missing or damaged'
        if p.header.get('sha256') != x.get('sha256'):
            return f'its {role} part does not match'
    return None


def checkpoint_refused_text(k, n, why):
    return f'The saved first part of pass {k + 1} of {n} could not be used ({why}), so the pass is made again from its start.'


def _make_input_plane(src, in_path, st, k, jid, iid):
    """The stage-input plane: the reflect pad of the stage input, streamed by bands (stage 0 reads the user's input)."""
    from service.runner import ItemFailure
    pw, ph = st['padded_size']
    in_plane = planes.Plane.create(in_path, (ph, pw, 3), 'u8', producer='service pad', run_id=f'{jid}/{iid}/s{k}')
    if k == 0:
        arr = images.load_rgb(src)
        got = [arr.shape[1], arr.shape[0]]
        if got != list(st['input_size']):
            raise ItemFailure('An intermediate result has an unexpected size, so this image was stopped.',
                              event='stage_input_size', data={'expected': st['input_size'], 'got': got})
        pad_plane(arr, in_plane, (pw, ph))
        del arr
    else:
        prev = planes.Plane.open(src)
        if [prev.shape[1], prev.shape[0]] != list(st['input_size']):
            raise ItemFailure('An intermediate result has an unexpected size, so this image was stopped.',
                              event='stage_input_size', data={'expected': st['input_size'], 'got': [prev.shape[1], prev.shape[0]]})
        pad_plane(prev, in_plane, (pw, ph))
    in_plane.finish()
    return in_plane


# --- the live preview (ENGINE-DESIGN 2.10, D8) --------------------------------------------------------------------------
LIVE_PROXY_SIDE = 2048


class _InputCrop:
    """The unpadded stage input inside the padded input plane (its first ih rows and iw columns), with the access the
    banded Lanczos needs: row bands and column strips, never the whole image."""

    def __init__(self, plane, iw, ih):
        self.plane, self.iw, self.ih = plane, int(iw), int(ih)
        self.shape = (self.ih, self.iw, plane.shape[2])
        self.dtype = plane.dtype

    def read_rows(self, y0, y1):
        return np.ascontiguousarray(self.plane.read_rows(y0, y1)[:, :self.iw])

    def read_cols(self, x0, x1):
        m = self.plane.map('r')
        try:
            return np.array(m[:self.ih, x0:x1])
        finally:
            del m


def live_proxy(in_plane, input_size, tmp_dir, long_side=LIVE_PROXY_SIDE):
    """A proxy of the stage input (input_size, inside the padded input plane) of at most long_side px on its long side, by
    the T1 banded Lanczos (engine/lanczos_bands): the bytes of Pillow's whole-image resize(size, LANCZOS). An H2 x W2 x 3
    uint8 array (under 13 MB at 2048 px); the horizontal pass, when both passes run, goes through a plane in tmp_dir."""
    from engine import lanczos_bands
    iw, ih = (int(v) for v in input_size)
    W2, H2 = lanczos_bands.proxy_size(iw, ih, long_side)
    src = _InputCrop(in_plane, iw, ih)
    dst = lanczos_bands.ArrayRows(np.zeros((H2, W2, 3), np.uint8))
    tmp = None
    if W2 != iw and H2 != ih:
        tmp = planes.Plane.create(Path(tmp_dir) / 'live-proxy-h.plane', (ih, W2, 3), 'u8', producer='live proxy')
    try:
        lanczos_resize(src, dst, tmp)
    finally:
        if tmp is not None:
            try:
                os.unlink(tmp.path)
            except OSError:
                pass
    return dst.a


def live_begin(r, ctx, it, k, n, st, info, in_plane, tmp_dir):
    """The item's live canvas for a Large-image stage (None when the graph has no live preview): Runner._live_begin with the
    banded proxy of the stage input as its start picture, and no full-size live picture (whose memory would grow with the
    output; live frames stay within service/live.py's FULL_BUDGET_MB). Never raises."""
    opts = dict((info or {}).get('spot_options') or {})
    if opts.get('live_preview') not in ('rough', 'detailed'):
        return None
    try:
        from PIL import Image
        proxy = Image.fromarray(live_proxy(in_plane, st['input_size'], tmp_dir), 'RGB')
    except Exception as e:      # the preview is a convenience; the stage goes on without it
        r.log.warn('live_proxy_failed', f'The live preview picture could not be made for this pass: {e}', job=ctx.jid,
                   item=ctx.iid, stage=k)
        proxy = None
    return r._live_begin(ctx, it, k, n, st, info, opts, None, source=proxy, full=False)


def _mark_started(r, it, jid, iid, k, n, st, w, info, graph, work, part, pk, pw, ph):
    from service.runner import now_iso
    it = r.store.item(jid, iid)
    timings = dict(it['timings'])
    timings['stages'] = [x for x in timings.get('stages', []) if not (x.get('index') == k and x.get('part') == part)]
    timings['stages'].append({'index': k, 'part': part, 'started': now_iso(), 'planned_minutes': st['minutes'],
                              'spot_options': info.get('spot_options'), 'memory_profile': w.memory_profile.to_dict(),
                              'engine': 'banded', 'finish': info.get('finish'), 'split_finish': bool(st.get('split_finish')),
                              'run_order': info.get('run_order')})
    r.store.update_item(jid, iid, state='running', stage_index=k, stage=k, stages=n, stages_done=k, stage_progress=0.0,
                        progress_estimated=False, message=f'Pass {k + 1} of {n} · Large-image engine', timings=timings,
                        event='stage_start', msg=f'Pass {k + 1} of {n} started (Large-image engine'
                                                 + (f', part {part}' if part else '') + ')',
                        data={'factor': float(st['factor']), 'supersample': float(st['supersample']),
                              'input': st['input_size'], 'padded': [pw, ph], 'render': st['render_size'],
                              'output': st['output_size'], 'denoise': pk['denoise'], 'structure': pk['structure'],
                              'seed': str(pk['seed']), 'nodes': len(graph), 'engine': 'banded', 'part': part,
                              'graph': str(work / f'stage{k}{part or ""}.graph.json')})


def _run_prompt(r, w, ctx, graph, run_id, k, n, plan, st, prefix, input_name, canvas=None, on_queued=None):
    """Queue one prompt and wait for it (Runner._wait_prompt, with this card's deadline). canvas: the stage's live canvas,
    fed the engine's live frames as the classic stage feeds them. on_queued(): called once the engine has accepted it."""
    from service.comfy import ComfyUnavailable, ProgressTracker, PromptRejected, rejection_text
    from service.runner import ItemFailure
    pid = run_id
    tracker = ProgressTracker(graph, pid)

    def on_msg(obj, tracker=tracker, canvas=canvas):
        if obj.get('type') == 'claude.live':
            tracker.touch()
            data = obj.get('data') or {}
            if data.get('kind') == 'group':
                tracker.on_group(data)
            if canvas is not None:
                canvas.on_frame(data, obj.get('jpeg') or b'')
        else:
            tracker.on_message(obj)
    ws = w.ws
    if ws is not None:
        ws.subscribe(pid, on_msg)
    try:
        try:
            got = w.client.prompt(graph, w.client_id, prompt_id=pid)
        except PromptRejected as e:
            raise ItemFailure(f'The engine could not accept pass {k + 1} of {n}: it is missing a part it needs (the '
                              'Large-image engine). Details are in the log.', event='prompt_rejected',
                              data={'detail': e.detail, 'summary': rejection_text(e.detail)})
        except ComfyUnavailable as e:
            raise ItemFailure(f'The engine stopped answering at the start of pass {k + 1} of {n}.',
                              event='worker_unreachable', data={'detail': e.detail}, kill_worker=True)
        if got != pid:
            if ws is not None:
                ws.unsubscribe(pid)
                ws.subscribe(got, on_msg)
            pid = tracker.prompt_id = got
        ctx.prompt_id = pid
        r.log.info('prompt_queued', f'Pass {k + 1} of {n} sent to the engine (Large-image)', job=ctx.jid, item=ctx.iid,
                   stage=k, data={'prompt_id': pid, 'gpu': w.gpu})
        if on_queued is not None:
            on_queued()
        deadline = r._deadline_s(ctx, st)          # (3 x minutes x card factor + 10) min (service/card_factor.py)
        hist = r._wait_prompt(w, ctx, graph, pid, k, n, plan, deadline, prefix, input_name, st, tracker)
    finally:
        if ws is not None:
            ws.unsubscribe(pid)
    return hist, pid


def _stage_done(r, ctx, jid, iid, k, n, st, t0, pid):
    from service.runner import ACTIVE, now_iso
    secs = time.monotonic() - t0
    ratio = secs / max(1.0, st['minutes'] * 60)
    ctx.speed = ratio if ctx.speed is None else (ctx.speed + ratio) / 2
    sfs = getattr(ctx, 'stage_factors', None)
    pace = ratio / max(0.01, sfs[k] if sfs else getattr(ctx, 'factor', 1.0))
    ctx.pace = pace if ctx.pace is None else (ctx.pace + pace) / 2
    it = r.store.item(jid, iid)
    timings = dict(it['timings'])
    for x in timings['stages']:
        if x['index'] == k:
            x.update(finished=now_iso(), seconds=round(secs, 1))
    r.store.set_job_fields(jid, speed_factor=round(ctx.speed, 4), pace=round(ctx.pace, 4))
    r.store.update_item(jid, iid, stage_index=k + 1, stage=k, stages_done=k + 1, stage_progress=0.0, timings=timings,
                        if_state=ACTIVE, event='stage_done',
                        msg=(f'Pass {k + 1} of {n} finished in {secs:.0f} s' if n > 1 else f'Upscaled {it["name"]} in {secs:.0f} s'),
                        data={'seconds': round(secs, 1), 'planned_minutes': st['minutes'], 'prompt_id': pid,
                              'engine': 'banded'})


# --- the result -----------------------------------------------------------------------------------------------------------

def alpha_plane(work, W, H):
    """The input's alpha resized to the output by banded Lanczos (mode L): the bytes of the classic's whole-image
    Image.resize((W, H), LANCZOS) of alpha.png (at most the input's 80 MP), without a whole output-size copy."""
    if not (work / 'alpha.png').is_file():
        return None
    a = np.asarray(images.load_alpha(work / 'alpha.png'), dtype=np.uint8)
    src = planes.from_array(work / 'alpha-src.plane', a)
    dst = planes.Plane.create(work / 'alpha.plane', (H, W, 1), 'u8', producer='service alpha')
    tmp = None
    if W != a.shape[1] and H != a.shape[0]:
        tmp = planes.Plane.create(work / 'alpha-h.plane', (a.shape[0], W, 1), 'u8', producer='service alpha')
    try:
        lanczos_resize(src, dst, tmp)
    finally:
        for p in (src.path, tmp.path if tmp is not None else None):
            if p is not None:
                try:
                    os.unlink(p)
                except OSError:
                    pass
    dst.finish()
    return dst


def encode_publish(r, ctx, job, it, work, last, out_dir, stem, factor, fmt, ext, W, H):
    """Runner._encode_publish for a Large-image result: the same naming, sidecar and publication, with the file written from
    the plane by the streamed writers and the viewer copies made from the plane."""
    from service.runner import ItemFailure, VERSION
    from service.util import new_id, sha256_file
    import json
    jid, iid = ctx.jid, ctx.iid
    try:
        plane = planes.validate(last, dtype='u8')
    except planes.PlaneError as e:
        raise ItemFailure('The finished image is missing or damaged in the work folder, so it could not be saved.',
                          event='final_missing', data={'error': str(e)}, keep_work=True)
    if (plane.shape[1], plane.shape[0]) != (W, H):
        raise ItemFailure('The finished image has an unexpected size, so it was not saved.', event='final_size',
                          data={'expected': [W, H], 'got': [plane.shape[1], plane.shape[0]]}, keep_work=True)
    alpha = alpha_plane(work, W, H)
    exif = (work / 'exif.bin').read_bytes() if (work / 'exif.bin').is_file() else None
    tmp = out_dir / f'.{stem}_cu{factor}x.{new_id("", 8)}.partial{ext}'
    try:
        info = plane_io.encode(tmp, plane, fmt, alpha=alpha, icc=images.srgb_icc_bytes(), exif=exif,
                               software=f'Creative Upscaler {VERSION}')
        out_sha = sha256_file(tmp)
        nbytes = tmp.stat().st_size
        sidecar = r._sidecar(job, it, info, out_sha, (W, H), nbytes)
        r._check_finish_cancel(ctx)
        result_ready = write_views(r, jid, iid, plane, alpha)

        def on_reserved(path, data):
            r.store.update_item(jid, iid, publishing={'output': str(path), 'bytes': nbytes, 'sha256': out_sha,
                                                      'sidecar_json': data.decode('utf8')}, if_state={'finishing'})
        try:
            out, side = images.reserve_and_publish(
                tmp, out_dir, stem, factor, ext,
                lambda p: json.dumps(dict(sidecar, output=dict(sidecar['output'], path=str(p), name=p.name)),
                                     indent=1, ensure_ascii=False).encode('utf8'),
                on_reserved=on_reserved, log_fn=lambda m: r.log.warn('temp_cleanup_failed', m, job=jid, item=iid))
        except images.SidecarPending as e:
            tmp = None
            e.info, e.out_sha, e.result_ready = info, out_sha, result_ready
            raise
        tmp = None
        return out, side, info, out_sha, result_ready
    finally:
        if tmp is not None:
            try:
                if Path(tmp).exists():
                    Path(tmp).unlink()
            except OSError as e:
                r.log.warn('temp_cleanup_failed', f'Temporary file {tmp} could not be removed: {e}', job=jid, item=iid)


def write_views(r, jid, iid, plane, alpha):
    try:
        r.media.write_result_views_plane(jid, iid, plane, alpha)
        return True
    except (OSError, ValueError, planes.PlaneError) as e:
        r.log.warn('result_view_failed', f'The viewer copy of the result could not be made: {e}', job=jid, item=iid)
        return False


def views_from_work(r, jid, iid, work, W, H, n):
    if r.media.result_views_ready(jid, iid):
        return True
    last = work / stage_plane_name(n - 1)
    if not last.is_file():
        return False
    try:
        plane = planes.validate(last, shape=(H, W, 3), dtype='u8')
    except planes.PlaneError:
        return False
    return write_views(r, jid, iid, plane, alpha_plane(work, W, H))


def sidecar_fields(plan):
    """What a Large-image result's sidecar adds under `engine` (a classic sidecar is 5.0.1's, key for key)."""
    c = plan.get('banded') or {}
    return {'executor': 'large-image', 'engine_version': c.get('bes'), 'finish': c.get('finish'),
            'halo_fix': c.get('halo_fix'), 'canvas': c.get('canvas'), 'recipe': c.get('recipe'),
            'forced_for_comparison': bool(c.get('forced')), 'graph': 'engine/graph_banded.py'}
