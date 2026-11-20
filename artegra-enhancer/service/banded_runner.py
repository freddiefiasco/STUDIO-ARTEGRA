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
    """One Large-image stage (Runner._run_stage's banded branch). r: the Runner."""
    from service.runner import ItemFailure, MultiCardWorker, now_iso
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
    shutil.rmtree(plane_dir, ignore_errors=True)
    plane_dir.mkdir(parents=True, exist_ok=True)
    in_plane = planes.Plane.create(plane_dir / 'input.plane', (ph, pw, 3), 'u8', producer='service pad', run_id=f'{jid}/{iid}/s{k}')
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
    pk = controls.stage_params(params, k)
    run = it.get('run') or r._run_would(None, it, r._item_mode(job, it))
    live_mode = engine_options.live_mode(r.detailed_info()['on'])
    stack = bool(run.get('speed_stack', True))
    prefix = f'cu_{jid}_{iid}_s{k}'
    parts = ['A', 'B'] if st.get('split_finish') else [None]
    t0 = time.monotonic()
    pid = None
    for part in parts:
        run_id = str(uuid.uuid4())
        graph, info = graph_banded.build_product(
            str(in_plane.path), pw, ph, pk, prefix, plane_dir.as_posix(), run_id, f=f, s=s, constants=consts,
            speed_stack=stack, live_preview=live_mode,
            faster=bool(run.get('faster')) and stack and k in engine_options.faster_stages(plan),
            creative_first=engine_options.creative_first_on(shared=isinstance(w, MultiCardWorker)), part=part,
            output_size=(ow, oh))
        if part != 'B':
            graph, info = memory_policy.apply_graph(graph, info, w.memory_profile)
            if isinstance(w, MultiCardWorker):
                graph = graph_banded.add_multigpu(graph, len(w.gpus), balance='static')
        expected = (int(round(pw * f)), int(round(ph * f)))
        if tuple(info['output']) != expected or tuple(info['render']) != (rw, rh):
            raise ItemFailure('This image was stopped because of an internal size mismatch. Details are in the log.',
                              event='graph_size_mismatch', data={'info': str(info), 'stage': st})
        atomic_write_json(work / f'stage{k}{part or ""}.graph.json', graph)
        if part == 'B':
            restart_worker(r, w, ctx, k, n)
        _mark_started(r, it, jid, iid, k, n, st, w, info, graph, work, part, pk, pw, ph)
        hist, pid = _run_prompt(r, w, ctx, graph, run_id, k, n, plan, st, prefix, None)
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


def restart_worker(r, w, ctx, k, n):
    """L3r: the finish of this stage runs in a fresh worker of the same build and flags (engine design section 2.8): stop the
    idle worker through its own stop path and wait for its process to end, then start it again."""
    from service.runner import EngineNotReady, ItemFailure
    from service.workers import WorkerError
    r.log.info('banded_split_restart', f'Pass {k + 1} of {n}: the finish runs in a fresh engine process',
               job=ctx.jid, item=ctx.iid, stage=k)
    try:
        w.stop('banded split finish')
    except Exception as e:      # the stop path reports its own problems; a worker that will not stop fails the stage
        raise ItemFailure('The engine could not be restarted for the last step of this pass.', event='banded_restart_failed',
                          data={'error': str(e)}, kill_worker=True)
    try:
        w.ensure_started(r._gpu_lookup() if r.mode == 'comfy' else None, abort=lambda: ctx.shutdown or not r.accepting)
    except WorkerError as e:
        raise EngineNotReady(str(e), ref=(e.detail or {}).get('log_ref') if isinstance(e.detail, dict) else None)


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


def _run_prompt(r, w, ctx, graph, run_id, k, n, plan, st, prefix, input_name):
    from service.comfy import ComfyUnavailable, ProgressTracker, PromptRejected, rejection_text
    from service.runner import ItemFailure
    pid = run_id
    tracker = ProgressTracker(graph, pid)

    def on_msg(obj, tracker=tracker):
        if obj.get('type') == 'claude.live':
            tracker.touch()
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
