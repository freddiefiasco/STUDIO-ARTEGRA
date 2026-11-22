"""One reference pair of design 7.1 run end to end: both executors on fresh workers of one developer build on the same card,
every intermediate dumped, the derived protect gate, the oracle finish on the BES's decoded planes, the phase diff, the thread
rule, the wsum mark and each run's Job peak commit. Generic: the machine, card, build and inputs are the caller's.

    run_pair(name, stages, cap, source_u8, work, launcher, app, python=...) -> report (JSON-able)

launcher(executor, run_dir) starts a fresh worker and returns an engine object with:
    client      (prompt(graph, client_id, prompt_id=...), history(prompt_id)): service/comfy.ComfyClient on the worker
    input_dir   the worker's ComfyUI input folder (the classic's LoadImage reads the stage input there)
    dump_root   the worker's CU_PROOF_DIR
    log_text()  the worker's stdout and stderr so far (the wsum lines)
    job_peak()  the worker Job's PeakJobMemoryUsed in bytes (or None)
    stop()      stops the worker and waits for its processes to end; may return a record with
                'all_owned_processes_terminated' (a worker still alive after its stop fails a split stage's part B)
comfy_launcher() makes one for a real ComfyUI worker (the product's command plus the proof packs; tools/proof/harness.py).
The oracle finish and the derived gate run in a fresh process of `python` (the worker runtime's interpreter: torch, scipy).

A Large-image stage whose forced plan splits its finish (L3r, the stage's split_finish: every stage at the workstation's cap)
runs as the service runs it: prompt A (ending in CUPlaneCheckpoint) on the current worker, then that worker is stopped and a
fresh one is launched (run dir <work>/bes/restart<n>) for prompt B (CUPlaneInput of A's planes and the finish), and the fresh
worker carries on into the next stage. The report lists every worker with the (stage, part) segments it ran and its own Job
peak (runs[executor]['workers']); the commit-fall mark of the split stays with the service's own record (records.l3r_*),
since each harness worker has a Job of its own.

Modes of the finish phase (design 7.2, 7.3; finish_rule):
  until_bxf  the finish phase compares the classic's stage output with the oracle finish run whole on the BES's decoded planes
             (the GPU phases are proven before the banded finish exists), at 0 differing values; the BES's own stage output
             is compared with the classic's and, by the tier rule, with the oracle (reported, not judged).
  bxf        every phase before the finish at 0 differing values; the finish phase's candidate is the BES's own stage
             output, judged by the tier rule against the oracle finish on the BES planes (tier 0, or tier 1 with the
             registered floor F), at both executors' boundary rows and columns of the stage (seams.positions).
In both modes the tier's reference is the oracle's output, never the BES's own."""
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import numpy as np

from tools.proof import classic, harness, harness_io, phases, records, registration, seams, tiers


def _run(cmd, cwd, timeout_s):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout_s)
    if p.returncode != 0:
        raise RuntimeError(f'{cmd[3:5]} failed: {p.stderr[-2000:]}')
    return json.loads(p.stdout.strip().splitlines()[-1])


def cpu_gate(python, app, union, release, dilate, feather, out, timeout_s=3600):
    cmd = [python, '-B', '-m', 'tools.proof.classic', 'gate', '--app', str(app), '--union', str(union), '--dilate',
           str(int(dilate)), '--feather', str(float(feather)), '--out', str(out)]
    if release:
        cmd += ['--release', str(release)]
    return _run(cmd, app, timeout_s)


def cpu_oracle(python, app, job_path, out, timeout_s=4 * 3600):
    return _run([python, '-B', '-m', 'tools.proof.classic', 'finish', '--job', str(job_path), '--out', str(out)], app,
                timeout_s)


def stage_output_u8(entry):
    """A run's stage output (a report row's stage_output_entry) as u8 at the stage's cropped size: the next input of a chain."""
    return _stage_output_u8(entry, None, entry['size'])


def _stage_output_u8(entry, form, size):
    """The stage output as u8 at the stage's cropped size (classic: the toe's float dump as SaveImage writes it)."""
    from engine import planes
    p = planes.validate(entry['path'])
    a = p.read_rows(0, p.shape[0])
    if a.dtype != np.uint8:
        a = np.clip(255. * a.astype(np.float32), 0, 255).astype(np.uint8)
    return np.ascontiguousarray(a[:size[1], :size[0], :3])


MODES = ('until_bxf', 'bxf')
BEFORE_FINISH_RULE = '0 differing values in every phase before the finish against the classic 5.0.1 on the same card'


def boundary_lines(plan_stage):
    """Both executors' band, strip and tile rows and columns of ONE stage, in that stage's output px (seams.positions of the
    stage alone: given a chain, positions() scales every stage to the last one's output). Returns (rows, cols)."""
    pos = seams.positions([plan_stage], ('classic', 'bes'))
    return (sorted({int(v) for vs in pos['rows'].values() for v in vs}),
            sorted({int(v) for vs in pos['cols'].values() for v in vs}))


def finish_rule(mode, row, oracle_out, bes_own, floor_F):
    """(rule record, pass) of the finish phase (design 7.2, 7.3), by mode:
    until_bxf  the oracle finish on the BES's decoded planes against the classic's stage output, 0 differing values (the same
               classic code on planes the earlier phases proved equal); the BES's own output and its tier are reported only;
    bxf        the BES's own stage output at tier 0, or tier 1 against the registered floor F, against the oracle finish on
               the BES planes; without a floor only tier 0 passes; without an oracle run, 0 differing values against the
               classic's stage output. A BES run that wrote no stage output fails either way."""
    fin = next(p for p in row['phase_diff']['phases'] if p['phase'] == 'finish')
    rule = {'mode': mode, 'before_finish': BEFORE_FINISH_RULE}
    if bes_own is None:
        return dict(rule, finish='the BES wrote no stage output: fails'), False
    if mode == 'until_bxf':
        if oracle_out is None:
            return dict(rule, finish='no oracle run: the BES stage output against the classic stage output, 0 differing '
                                     'values'), fin['differing'] == 0
        return dict(rule, finish='the oracle finish on the BES planes against the classic stage output, 0 differing values; '
                                 'the BES stage output against the oracle reported (bes_finish_tier), not judged'), \
            fin['differing'] == 0
    if oracle_out is None:
        return dict(rule, finish='no oracle run: the BES stage output against the classic stage output, 0 differing '
                                 'values'), fin['differing'] == 0
    t = row['bes_finish_tier']
    if floor_F is None:
        return dict(rule, finish='the BES stage output against the oracle finish on the BES planes: tier 0 (no floor F is '
                                 'registered, so tier 1 cannot pass)', F=None), bool(t['pass'])
    return dict(rule, finish=f'the BES stage output against the oracle finish on the BES planes: tier 0, or tier 1 with the '
                             f'registered floor F = {int(floor_F)} (7.3)', F=int(floor_F)), bool(t['pass'])


PRIVATE_KEYS = ('graph', 'graphs', 'spec', 'roles')


def _public_stage(s):
    out = {k: v for k, v in s.items() if k not in PRIVATE_KEYS}
    if 'parts' in out:
        out['parts'] = [{k: v for k, v in p.items() if k not in PRIVATE_KEYS} for p in out['parts']]
    return out


def _start_worker(workers, launcher, ex, rd):
    """A fresh worker for this executor's run: the first in <run dir>, each restart in <run dir>/restart<n>."""
    n = len(workers)
    run_dir = rd if n == 0 else rd / f'restart{n}'
    workers.append({'n': n, 'run_dir': str(run_dir), 'segments': [], 'engine': launcher(ex, run_dir)})
    return workers[-1]['engine']


def _stop_worker(w):
    """Read the worker's log and Job peak, then stop it (once). Records them on w; returns the stop record or None."""
    e = w.pop('engine', None)
    if e is None:
        return w.get('stop')
    try:
        w['log'] = e.log_text() or ''
    except Exception as err:  # noqa: BLE001 - a log that cannot be read is recorded, the run goes on
        w['log'], w['log_error'] = '', str(err)
    try:
        peak = e.job_peak()
    except Exception:  # noqa: BLE001
        peak = None
    w['job_peak_bytes'] = peak
    w['job_peak_commit_gb'] = None if peak is None else round(peak / 2 ** 30, 2)
    res = e.stop()
    w['stop'] = res if isinstance(res, dict) else None
    return w['stop']


def _stopped_cleanly(rec):
    """False only when the stop record says a process of the worker is still alive (a fake engine gives no record)."""
    return not (isinstance(rec, dict) and rec.get('all_owned_processes_terminated') is False)


def new_prompt_id():
    """A prompt id the runtime ComfyUI takes: a fresh UUID in canonical lowercase hyphenated form (its /prompt refuses
    any other client id with 400 invalid_prompt_id: comfy_execution/jobs.validate_job_id; integ-dev-2). The service sends
    the same (service/runner: str(uuid.uuid4()))."""
    return str(uuid.uuid4())


def _run_part(ex, name, st, plan, part, eng, worker, pd, plane, options, timeout_s, base_params=None):
    # Two ids: run_id, readable, names the BES's planes and is the graph's run id (packets.RUN_TEMPLATE stands for it in
    # the registered graph hashes); prompt_id is ComfyUI's (a canonical UUID), and the instrumentation's dump folder
    # <CU_PROOF_DIR>/<prompt id>/ (its spec, events and dumps) is keyed by it.
    run_id = f'{name}-{ex}-s{st.index}{part or ""}-{uuid.uuid4().hex[:8]}'
    prompt_id = new_prompt_id()
    if ex == 'classic':
        graph, info = harness.classic_graph(st, options, base_params)
    else:
        graph, info = harness.bes_graph(st, plan, pd.as_posix(), Path(plane).as_posix(), run_id, options, base_params,
                                        part=part)
    spec = harness.dump_spec(graph, info, ex, st)
    harness_io.write_spec(eng.dump_root, prompt_id, spec)
    t0 = time.time()
    p = {'part': part, 'prompt_id': prompt_id, 'run_id': run_id, 'graph_sha256': harness.graph_sha(graph),
         'worker': worker['n']}
    try:
        hist = harness.run_prompt(eng.client, harness.prompt_graph(graph, spec), prompt_id, timeout_s=timeout_s)
        p['status'] = (hist.get('status') or {}).get('status_str')
    except harness.RunFailed as e:
        p.update(status='failed', error=str(e))
    except Exception as e:  # noqa: BLE001 - a prompt the engine refused (PromptRejected) or could not take is a result
        p.update(status='failed', error=f'{type(e).__name__}: {e}' + (f' {e.detail}' if getattr(e, 'detail', None) else ''))
    p['seconds'] = round(time.time() - t0, 1)
    man = harness_io.collect(Path(eng.dump_root) / prompt_id, spec)
    p.update(missing=harness_io.check_complete(man, spec), errors=man['errors'], env=man['env'][:1],
             phase_seconds=man['phase_seconds'], timeline=man['timeline'], spec=spec, graph=graph, roles=man['roles'],
             instrument=man.get('instrument'))
    worker['segments'].append([st.index, part])
    worker.setdefault('instrument', []).append(man.get('instrument') or {})
    return p


def _merge_parts(row, parts):
    """One stage row from its prompts: the single prompt's fields, or, for a split stage, both parts' roles, timelines and
    errors together, the env of part A (each part's env is checked by the thread rule), the finish graph of part B."""
    if len(parts) == 1 and parts[0]['part'] is None:
        p = parts[0]
        row.update({k: v for k, v in p.items() if k not in ('part', 'worker')}, graphs=[p['graph']])
        row['parts'] = [{k: v for k, v in p.items() if k in ('part', 'prompt_id', 'run_id', 'graph_sha256', 'worker',
                                                             'status')}]
        return row
    roles, missing, errors, timeline, phase_s = {}, [], [], [], {}
    for p in parts:
        for role, e in p['roles'].items():
            if role in roles:
                errors.append({'where': 'merge', 'message': f"{role} came from parts {roles[role].get('part')} and {p['part']}"})
            roles[role] = dict(e, part=p['part'])
        missing += [m for m in p['missing'] if m not in missing]
        errors += p['errors']
        timeline += p['timeline']
        for ph, s in p['phase_seconds'].items():
            phase_s[ph] = round(phase_s.get(ph, 0.0) + s, 3)
    failed = next((p for p in parts if p['status'] != 'success'), None)
    want = ('A', 'B')
    if [p['part'] for p in parts] != list(want) and failed is None:
        failed = {'status': 'failed', 'error': f"parts {[p['part'] for p in parts]} ran, not {list(want)}"}
    row.update(prompt_id={p['part']: p['prompt_id'] for p in parts},
               graph_sha256={p['part']: p['graph_sha256'] for p in parts},
               status='success' if failed is None else 'failed', seconds=round(sum(p['seconds'] for p in parts), 1),
               missing=missing, errors=errors, env=parts[0]['env'], phase_seconds=phase_s, timeline=timeline,
               roles=roles, graph=next((p['graph'] for p in reversed(parts) if p.get('graph')), None),
               graphs=[p['graph'] for p in parts if p.get('graph')], spec=parts[0]['spec'], parts=parts)
    if failed is not None:
        row['error'] = failed.get('error') or f"part {failed.get('part')} did not finish"
    return row


def thread_diffs(c, b):
    """Design 7.1's thread rule for one stage: the classic run's thread record against every BES prompt's (both parts of a
    split stage: the fresh worker of part B must run at the same thread count too)."""
    out = harness_io.same_threads(c['env'], b['env'])
    for p in (b.get('parts') or [])[1:]:
        out += [f"part {p['part']}: {d}" for d in harness_io.same_threads(c['env'], p.get('env'))]
    return out


def _run_executor(ex, name, stages, plan, rd, launcher, source_u8, options, timeout_s, base_params=None):
    """One executor's run of the pair's stages, in order, each stage feeding the next. A BES stage whose plan splits its
    finish (L3r) runs as the service runs it (service/banded_runner.run_stage): prompt A on the current worker; that worker
    is stopped (its log and Job peak read first); a fresh worker of the same build runs prompt B and carries on into the
    next stage. Each worker's Job peak is its own: workers lists the (stage, part) segments each one ran."""
    workers, out_stage = [], []
    _start_worker(workers, launcher, ex, rd)
    try:
        cur = np.ascontiguousarray(np.asarray(source_u8, np.uint8)[..., :3])
        for st, bst in zip(stages, plan.stages):
            parts_ = harness.bes_parts(bst) if ex == 'bes' else (None,)
            sd = rd / f's{st.index}'
            pd = sd / 'planes'
            _, plane = harness.prepare_inputs(cur, st, workers[-1]['engine'].input_dir, pd)
            row = {'stage': st.index, 'input_plane': plane, 'split_finish': parts_ != (None,)}
            parts = []
            for part in parts_:
                if part == 'B':
                    rec = _stop_worker(workers[-1])
                    if not _stopped_cleanly(rec):
                        parts.append({'part': 'B', 'status': 'failed', 'worker': workers[-1]['n'], 'seconds': 0.0,
                                      'error': 'the worker of part A did not stop, so part B was not run', 'roles': {},
                                      'missing': [], 'errors': [], 'env': [], 'phase_seconds': {}, 'timeline': [],
                                      'graph': None, 'graph_sha256': None, 'prompt_id': None, 'spec': None})
                        break
                    _start_worker(workers, launcher, ex, rd)
                p = _run_part(ex, name, st, plan, part, workers[-1]['engine'], workers[-1], pd, plane, options,
                              timeout_s, base_params)
                parts.append(p)
                if p['status'] != 'success':
                    break
            _merge_parts(row, parts)
            man_roles = row['roles']
            if row['status'] == 'success' and 'stage_output' in man_roles:
                cur = _stage_output_u8(man_roles['stage_output'], None, st.output)
                row['stage_output_sha256'] = hashlib.sha256(cur.tobytes()).hexdigest()
                row['stage_output_entry'] = dict(man_roles['stage_output'], size=list(st.output))
            out_stage.append(row)
            if row['status'] != 'success':
                break
    finally:
        _stop_worker(workers[-1])
    text = '\n'.join(w.get('log', '') for w in workers)
    for w in workers:
        ins = w.pop('instrument', [])
        host = [i.get('host_bytes_max') or 0 for i in ins]
        delta = [i['commit_delta_max_bytes'] for i in ins if i.get('commit_delta_max_bytes') is not None]
        w['instrument_host_gb_max'] = round(max(host) / 2 ** 30, 3) if host else 0.0
        w['instrument_commit_delta_gb_max'] = round(max(delta) / 2 ** 30, 3) if delta else None
    peaks = [w.get('job_peak_bytes') for w in workers]
    graphs = [g for r in out_stage for g in r.get('graphs', []) if g]
    want = records.expected_wsum_lines(graphs) if ex == 'bes' else 0
    return {'stages': out_stage,
            'workers': [{k: v for k, v in w.items() if k not in ('log', 'engine')} for w in workers],
            'job_peak_commit_gb': None if (not peaks or any(p is None for p in peaks)) else round(max(peaks) / 2 ** 30, 2),
            'log_tail': text[-4000:], 'wsum': records.wsum_mark(text, expect_lines=bool(want), expect_min=want or None)}


SEEDS_NOTE = 'seed None: the default preset seed (controls.DEFAULT_SEED, the case table seed A); else the run is made with it'


def run_mode(options):
    """The service's run mode of a harness option set, for the forced plan: 'fast' (Bolt) for an option set that runs the
    classic through engine/fast_recipe ('bolt'), else None (Redux: plan_forced's default). The Large-image graph takes its
    mode from the plan's constants (graph_banded.stage_mode), so a Bolt pair's forced plan must be made in mode 'fast', as
    the packet builder registers it; a Redux plan there would build the Redux banded stage beside the classic Bolt stage."""
    return 'fast' if harness.OPTION_SETS.get(options, {}).get('bolt') else None


IDENTITY_RULE = ("design 7.1 and 7.4: the two sides of a compared pair hold the seed, the build (the shipped tree's content "
                 "hash and channel), the node and the card equal (the card only unless the pair is registered cross-card); "
                 "a pair whose records differ, or record one of these on one side only, is void (refused, pass False)")


def _identity(sd, key):
    if key == 'build':
        b = sd.get('build')
        return None if not b else (b.get('tree'), b.get('channel'))
    return sd.get(key)


def void_reason(a, b, cross_card=False):
    """None when two stored sides may be compared (IDENTITY_RULE), else the plain reason. a, b: side records (run_side's,
    with the driver's build, node and card_uuid where it adds them)."""
    out = []
    if a.get('seed') != b.get('seed'):
        out.append(f"seed ({a.get('seed')!r} and {b.get('seed')!r})")
    if a.get('options', 'base') != b.get('options', 'base'):
        out.append(f"options ({a.get('options')!r} and {b.get('options')!r})")
    for key, label in (('build', 'build'), ('node', 'node'), ('card_uuid', 'card')):
        if key == 'card_uuid' and cross_card:
            continue
        va, vb = _identity(a, key), _identity(b, key)
        if va is None and vb is None:
            continue
        if va is None or vb is None:
            out.append(f'{label} (recorded on one side only)')
        elif va != vb:
            out.append(label)
    return ('the two sides differ in ' + ', '.join(out)) if out else None


def base_params(seed=None):
    """The default preset's parameters (controls.resolve), with the run's seed when one is given (classic seed B)."""
    from engine import controls
    return controls.resolve({} if seed is None else {'seed': int(seed)})[0]


def run_side(name, stages, cap, source_u8, work, launcher, executor, options='base', seed=None,
             prompt_timeout_s=6 * 3600, store=True):
    """One executor's run of a pair, kept for a later comparison (compare_runs): for the workstation's rows, where the
    classic reference (W1c, W2c) and the Large-image run (W1b, W2b) run hours apart, and for a classic seed-B run (W1s,
    W2s). Each stage's every intermediate is dumped as in run_pair. Returns the side record (JSON-able); with store, also
    written to <work>/<executor>/side.json. Nothing is retried; a failure is a result."""
    if executor not in ('classic', 'bes'):
        raise ValueError('executor must be classic or bes')
    work = Path(work)
    plan = harness.forced_plan(stages, cap, run_mode(options))
    rec = {'pair': name, 'executor': executor, 'cap_gb': float(cap), 'plan_forced': plan.to_dict(), 'options': options,
           'mode': run_mode(options), 'seed': seed, 'seed_rule': SEEDS_NOTE, 'started': time.time(),
           'stages': [{'w': s.w, 'h': s.h, 'f': str(s.f), 's': str(s.s), 'index': s.index} for s in stages]}
    if not plan.ok:
        rec['error'] = f'plan_forced refused: {plan.reason}'
        return rec
    rec['run'] = _run_executor(executor, name, stages, plan, work / executor, launcher, source_u8, options,
                               prompt_timeout_s, base_params(seed) if seed is not None else None)
    rec['ended'] = time.time()
    rec = strip_for_json(rec)
    if store:
        (work / executor).mkdir(parents=True, exist_ok=True)
        (work / executor / 'side.json').write_text(json.dumps(rec), encoding='utf8')
    return rec


def load_side(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def _gate_roles(croles, broles, c, st, work, gate_fn):
    """The SAM phase's 'gate' role (D7). The classic's gate is derived from its dumped unions by the classic's own
    ClaudeProtectGate. The Large-image side is compared through its finish's own gate plane where its finish exposes one (a
    'gate' role it dumped or wrote, not derived here); the base CUFinishBanded exposes none, so its gate is derived the same
    way from its own unions, and the role then adds nothing beyond the unions: the row says so ('union-derived')."""
    own = broles.get('gate') if not (broles.get('gate') or {}).get('derived') else None
    for side, roles, sd in (('classic', croles, work / 'classic'), ('bes', broles, work / 'bes')):
        if side == 'bes' and own is not None:
            continue
        u = roles.get('union/protect')
        if u:
            out = sd / f's{st.index}' / 'derived_gate.plane'
            rel = roles.get('union/release')
            g = c['spec']['gate']
            gate_fn(u['path'], rel['path'] if rel else None, g['dilate'], g['feather'], out)
            roles['gate'] = {'kind': 'plane', 'path': str(out), 'form': 'bitwise', 'derived': True}
    if not croles.get('union/protect'):
        return {'source': None, 'note': 'no protect union in this stage: no gate'}
    if own is not None:
        return {'source': 'the finish gate plane', 'note': "the Large-image finish's own gate plane against the classic's "
                                                          'gate derived from its unions'}
    return {'source': 'union-derived', 'note': 'both gates derived from the dumped unions by the classic ClaudeProtectGate: '
                                               'the Large-image finish exposes no gate plane, so this role adds nothing '
                                               'beyond the union roles'}


def compare_runs(name, stages, cap, classic_side, bes_side, work, app, python=None, mode='until_bxf', floor_F=None,
                 gate=True, oracle=True, gate_fn=None, oracle_fn=None, cross_card=False):
    """The comparison of two stored sides (run_side, or run_pair's own runs): the derived gate, the oracle finish on the
    BES's decoded planes, the phase diff, the finish rule, the thread rule, wsum, and the memory mark. Returns run_pair's
    report. The two sides must be of this pair, cap and plan (made in the sides' run mode), else the report is refused;
    sides that differ in seed, options, build, node or card (the card only without cross_card) are void (IDENTITY_RULE)."""
    if mode not in MODES:
        raise ValueError(f'mode must be one of {MODES} (got {mode!r})')
    work = Path(work)
    python = python or sys.executable
    gate_fn = gate_fn or (lambda *a: cpu_gate(python, app, *a))
    oracle_fn = oracle_fn or (lambda job, out: cpu_oracle(python, app, job, out))
    options = classic_side.get('options', 'base')
    plan = harness.forced_plan(stages, cap, run_mode(options))
    rep = {'pair': name, 'cap_gb': float(cap), 'mode': mode, 'plan_forced': plan.to_dict(), 'runs': {}, 'stages': [],
           'started': time.time(), 'identity_rule': IDENTITY_RULE, 'cross_card': bool(cross_card)}
    if not plan.ok:
        rep['error'] = f'plan_forced refused: {plan.reason}'
        return rep
    why = void_reason(classic_side, bes_side, cross_card)
    if why:
        rep.update({'error': f'void: {why}', 'void': True, 'pass': False})
        return rep
    sides = {'classic': classic_side, 'bes': bes_side}
    for ex, sd in sides.items():
        if sd.get('executor', ex) != ex or sd.get('pair', name) != name or float(sd.get('cap_gb', cap)) != float(cap) \
                or (sd.get('plan_forced') is not None and sd['plan_forced'] != strip_for_json(plan.to_dict())):
            rep['error'] = f'the stored {ex} side is not of this pair, cap and plan'
            return rep
        if 'run' not in sd:
            rep['error'] = f"the {ex} side did not run: {sd.get('error')}"
            return rep
    runs = {ex: sides[ex]['run'] for ex in sides}
    rep['seeds'] = {ex: sides[ex].get('seed') for ex in sides}
    for ex, r in runs.items():
        rep['runs'][ex] = {k: v for k, v in r.items() if k != 'stages'}
        rep['runs'][ex]['stages'] = [_public_stage(s) for s in r['stages']]
    for i, (st, bst) in enumerate(zip(stages, plan.stages)):
        c = runs['classic']['stages'][i] if i < len(runs['classic']['stages']) else None
        b = runs['bes']['stages'][i] if i < len(runs['bes']['stages']) else None
        row = {'stage': st.index, 'k': str(st.k)}
        if not c or not b or c['status'] != 'success' or b['status'] != 'success':
            row['error'] = 'a run of this stage did not finish'
            rep['stages'].append(row)
            continue
        croles, broles = dict(c['roles']), dict(b['roles'])
        for r in (croles, broles):
            r.pop('input', None)
        if gate:
            row['gate'] = _gate_roles(croles, broles, c, st, work, gate_fn)
        bes_own = broles.pop('stage_output', None)
        oracle_out = None
        if oracle:
            job = {'app': str(app), 'inputs': classic.finish_inputs(b['graph']),
                   'planes': {'creative': broles['raw8']['path'], 'structure': broles['rawlo8']['path'],
                              'init': broles['init']['path'], 'pre': b['input_plane'],
                              'protect': (broles.get('union/protect') or {}).get('path'),
                              'release': (broles.get('union/release') or {}).get('path')}}
            jp = work / 'bes' / f's{st.index}' / 'oracle_job.json'
            jp.parent.mkdir(parents=True, exist_ok=True)
            jp.write_text(json.dumps(job), encoding='utf8')
            out = work / 'bes' / f's{st.index}' / 'oracle_output.plane'
            oracle_fn(jp, out)
            oracle_out = {'kind': 'plane', 'path': str(out), 'form': 'save8_crop', 'oracle': True}
        # The finish phase's candidate: the oracle finish on the BES planes until the BXF exists, else the BES's own output.
        cand = oracle_out if (mode == 'until_bxf' and oracle_out is not None) else bes_own
        if cand is not None:
            broles['stage_output'] = cand
        row['phase_diff'] = phases.count(croles, broles)
        c_out = croles.get('stage_output')
        if bes_own is not None and c_out is not None:
            row['bes_stage_output_vs_classic'] = phases.compare_entries(c_out, bes_own, 'save8_crop')
        if oracle_out is not None and c_out is not None and mode == 'bxf':
            row['oracle_vs_classic'] = phases.compare_entries(c_out, oracle_out, 'save8_crop')
        lines = boundary_lines(bst)
        row['boundaries'] = {'rows': len(lines[0]), 'cols': len(lines[1])}
        if oracle_out is not None and bes_own is not None:
            # 7.3: the BES's own stage output against the oracle (never against itself), at both executors' boundary rows
            # and columns of this stage; without a registered floor F only tier 0 can pass.
            row['bes_finish_tier'] = dict(tiers.tier(oracle_out, bes_own, 0 if floor_F is None else floor_F, *lines),
                                          F_registered=floor_F is not None)
        rule, finish_ok = finish_rule(mode, row, oracle_out, bes_own, floor_F)
        row['rule'] = rule
        row['finish_pass'] = finish_ok
        row['before_finish_zero'] = all(p['differing'] == 0 for p in row['phase_diff']['phases'] if p['phase'] != 'finish')
        row['threads'] = thread_diffs(c, b)
        row['missing'] = {'classic': c['missing'], 'bes': b['missing']}
        row['errors'] = {'classic': c['errors'], 'bes': b['errors']}
        row['pass'] = bool(row['before_finish_zero'] and finish_ok and not row['threads'] and not c['missing']
                           and not b['missing'] and not c['errors'] and not b['errors'] and runs['bes']['wsum']['pass'])
        rep['stages'].append(row)
    rep['pass'] = bool(rep['stages']) and all(s.get('pass') for s in rep['stages'])
    # 9.2 R1's memory mark, on the harness's own Jobs: each BES worker against the worker-only bound of what it ran
    rep['memory'] = registration.memory_check(registration.plan_marks(plan, cap), runs['bes']['workers'])
    rep['ended'] = time.time()
    return rep


SAME_RULE = ("two kept sides of one executor (a cross-card identity, W5a; an emulated small card against the uncapped run, "
             "R5): every dumped role of every stage, the stage output included, compared bitwise (ControlNet calls by "
             "their recorded hashes) at 0 differing values, no role on one side only, the same thread counts, no missing "
             "intermediate and no error; the two sides must be of this pair, cap, plan, options and seed, and for the "
             "Large-image executor both wsum marks pass")


def _bitwise(roles):
    """The roles of one side with every compared form bitwise (a same-executor identity is exact), the ControlNet calls
    by their recorded hashes."""
    return {k: (v if str(k).split('/')[0] in ('cn', 'cn_hint') else dict(v, form='bitwise')) for k, v in roles.items()}


def compare_sides(name, stages, cap, side_a, side_b, executor='bes', band_rows=1024):
    """The identity of two stored sides of ONE executor (run_side): W5a's BES on card 1 against W1b's BES on card 0, R5's
    BES on an emulated card against the uncapped BES. Unlike compare_runs (classic against BES: derived gates, the oracle
    finish, the finish rule), every role is compared as it was dumped, bitwise (SAME_RULE). Returns a report with pass;
    sides that are not of this pair, cap, plan, executor, options and seed are refused with an error and pass False."""
    plan = harness.forced_plan(stages, cap, run_mode(side_a.get('options', 'base')))
    rep = {'pair': name, 'cap_gb': float(cap), 'mode': f'same:{executor}', 'rule': SAME_RULE, 'plan_forced': plan.to_dict(),
           'runs': {}, 'stages': [], 'started': time.time(), 'pass': False}
    if not plan.ok:
        rep['error'] = f'plan_forced refused: {plan.reason}'
        return rep
    sides = {'a': side_a, 'b': side_b}
    want = strip_for_json(plan.to_dict())
    for k, sd in sides.items():
        if sd.get('executor') != executor:
            rep['error'] = f"side {k} is a {sd.get('executor')!r} side, not {executor!r}"
            return rep
        if sd.get('pair', name) != name or float(sd.get('cap_gb', cap)) != float(cap) \
                or (sd.get('plan_forced') is not None and sd['plan_forced'] != want):
            rep['error'] = f'the stored side {k} is not of this pair, cap and plan'
            return rep
        if 'run' not in sd:
            rep['error'] = f"side {k} did not run: {sd.get('error')}"
            return rep
    for key in ('options', 'seed'):
        if side_a.get(key) != side_b.get(key):
            rep['error'] = f'the two sides differ in {key}: {side_a.get(key)!r} and {side_b.get(key)!r}'
            return rep
    why = void_reason(side_a, side_b, cross_card=True)       # a same-executor identity may cross cards (W5a)
    if why:
        rep.update(error=f'void: {why}', void=True)
        return rep
    rep['seeds'] = {k: sd.get('seed') for k, sd in sides.items()}
    rep['cards'] = {k: {'card': sd.get('card'), 'card_uuid': sd.get('card_uuid'), 'node': sd.get('node')}
                    for k, sd in sides.items()}
    runs = {k: sides[k]['run'] for k in sides}
    for k, r in runs.items():
        rep['runs'][k] = {x: v for x, v in r.items() if x != 'stages'}
        rep['runs'][k]['stages'] = [_public_stage(s) for s in r['stages']]
    for i, st in enumerate(stages):
        a = runs['a']['stages'][i] if i < len(runs['a']['stages']) else None
        b = runs['b']['stages'][i] if i < len(runs['b']['stages']) else None
        row = {'stage': st.index, 'k': str(st.k)}
        if not a or not b or a['status'] != 'success' or b['status'] != 'success':
            row.update({'error': 'a run of this stage did not finish', 'pass': False})
            rep['stages'].append(row)
            continue
        ra, rb = dict(a['roles']), dict(b['roles'])
        for r in (ra, rb):
            r.pop('input', None)
        row['phase_diff'] = phases.count(_bitwise(ra), _bitwise(rb), optional=frozenset(), band_rows=band_rows)
        row['stage_output_sha256'] = {'a': a.get('stage_output_sha256'), 'b': b.get('stage_output_sha256')}
        row['threads'] = thread_diffs(a, b)
        row['missing'] = {'a': a['missing'], 'b': b['missing']}
        row['errors'] = {'a': a['errors'], 'b': b['errors']}
        row['pass'] = bool(row['phase_diff']['zero'] and not row['threads'] and not a['missing'] and not b['missing']
                           and not a['errors'] and not b['errors'])
        rep['stages'].append(row)
    rep['wsum'] = {k: runs[k].get('wsum') for k in runs}
    wsum_ok = executor != 'bes' or all((runs[k].get('wsum') or {}).get('pass') for k in runs)
    rep['pass'] = bool(len(rep['stages']) == len(stages) and all(s.get('pass') for s in rep['stages']) and wsum_ok)
    if executor == 'bes':
        marks = registration.plan_marks(plan, cap)
        rep['memory'] = {k: registration.memory_check(marks, runs[k]['workers']) for k in runs}
    rep['ended'] = time.time()
    return rep


def run_pair(name, stages, cap, source_u8, work, launcher, app, python=None, mode='until_bxf', floor_F=None,
             options='base', gate=True, oracle=True, gate_fn=None, oracle_fn=None, prompt_timeout_s=6 * 3600, seeds=None):
    """Run one pair (one stage, or a chain whose stages run on one worker per executor, each executor feeding its own next
    stage), then compare (compare_runs). Returns the report; nothing is retried, and a failure is reported as one. Each
    compared stage row says which finish rule ran (finish_rule) and where its gate came from (row['gate']). seeds:
    {'classic': s, 'bes': s} (default: the preset's seed on both)."""
    if mode not in MODES:
        raise ValueError(f'mode must be one of {MODES} (got {mode!r})')
    work = Path(work)
    plan = harness.forced_plan(stages, cap, run_mode(options))
    if not plan.ok:
        return {'pair': name, 'cap_gb': float(cap), 'mode': mode, 'plan_forced': plan.to_dict(), 'runs': {}, 'stages': [],
                'started': time.time(), 'error': f'plan_forced refused: {plan.reason}'}
    seeds = seeds or {}
    sides = {ex: run_side(name, stages, cap, source_u8, work, launcher, ex, options, seeds.get(ex), prompt_timeout_s,
                          store=False) for ex in ('classic', 'bes')}
    return compare_runs(name, stages, cap, sides['classic'], sides['bes'], work, app, python, mode, floor_F, gate, oracle,
                        gate_fn, oracle_fn)


# The worker's base folders: the product's (service/workers.Worker._start makes input, output, temp, user, cache and
# custom_nodes: ComfyUI's prestartup lists <base>/custom_nodes, and a worker without it exits at once, integ-dev-1) and the
# instrumentation's dump root.
WORKER_DIRS = ('input', 'output', 'temp', 'user', 'cache', 'custom_nodes', 'proof')


class ComfyEngine:
    """A real ComfyUI worker of a developer build for one executor run (fresh, so nothing is cached between runs)."""

    def __init__(self, cfg, app, run_dir, card_uuid, port, memory_cap_gb, ready_timeout_s=600, on_started=None,
                 memory_profile=None, reserve_vram_gb=None, extra_env=None):
        """on_started(engine), when given, is called as soon as the worker's process and Job exist and before the worker
        answers (self.proc and self.client are set): a sampler that follows the newest worker then samples a restarted
        worker from its first second, its start-up included (L3r: part B's fresh worker). A failing hook never stops the
        worker; its error is kept in self.hook_error.
        memory_profile: a service/memory_policy profile for the product's command (Balanced for R5); reserve_vram_gb: the
        value of the command's --reserve-vram (R5's small-card emulation: the card's total less the emulated size);
        extra_env: added to the worker's environment (R5: CU_DEV_VRAM_CAP_GB, which only a developer build honours).
        Each is recorded in self.differs."""
        from service import comfy, windows_job, workers
        self.dir = Path(run_dir) / 'worker'
        for d in WORKER_DIRS:
            (self.dir / d).mkdir(parents=True, exist_ok=True)
        self.input_dir, self.dump_root, self.output_dir = self.dir / 'input', self.dir / 'proof', self.dir / 'output'
        proof_dir = Path(app) / 'tools' / 'proof'
        yaml = self.dir / 'extra_model_paths.yaml'
        yaml.write_text(harness.worker_yaml(cfg, proof_dir), encoding='utf8')
        cmd, self.differs = harness.worker_command(cfg, self.dir, port, yaml, proof_dir, memory_profile=memory_profile)
        if reserve_vram_gb is not None:
            i = cmd.index('--reserve-vram')
            cmd = cmd[:i + 1] + [f'{float(reserve_vram_gb):g}'] + cmd[i + 2:]
            self.differs['reserve_vram_gb'] = float(reserve_vram_gb)
        if memory_profile is not None:
            self.differs['memory_profile'] = getattr(memory_profile, 'name', None) or str(memory_profile)
        env = {k: v for k, v in os.environ.items() if k.upper() not in workers.SECRET_ENV}
        tmp = str(self.dir / 'temp')
        env.update(TEMP=tmp, TMP=tmp, HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', PYTHONDONTWRITEBYTECODE='1',
                   PYTHONNOUSERSITE='1', PYTHONUNBUFFERED='1', PYTHONIOENCODING='utf-8', CUDA_VISIBLE_DEVICES=card_uuid,
                   CUDA_DEVICE_ORDER='PCI_BUS_ID', CU_PROOF_DIR=str(self.dump_root))
        if extra_env:
            env.update({str(k): str(v) for k, v in extra_env.items()})
            self.differs['extra_env'] = sorted(extra_env)
        self.log = self.dir / 'worker-log.txt'
        self.proc = windows_job.WindowsJobProcess(cmd, cwd=str(self.dir), env=env, log_path=self.log,
                                                  memory_limit_bytes=int(float(memory_cap_gb) * (1 << 30)))
        self.client = comfy.ComfyClient(port)
        self.started_at, self.ready_at, self.hook_error = time.time(), None, None
        if on_started is not None:
            try:
                on_started(self)
            except Exception as e:  # noqa: BLE001 - the hook observes; it never stops the worker
                self.hook_error = f'{type(e).__name__}: {e}'
        t0 = time.monotonic()
        while True:
            try:
                self.client.system_stats()
                break
            except Exception:
                if time.monotonic() - t0 > ready_timeout_s or self.proc.poll_root() is not None:
                    self.stop()
                    raise RuntimeError('the proof worker did not start')
                time.sleep(2)
        self.ready_at = time.time()

    def log_text(self):
        try:
            return self.log.read_text(encoding='utf8', errors='replace')
        except OSError:
            return ''

    def job_peak(self):
        try:
            return self.proc.limits().get('peak_job_memory_used')
        except Exception:
            return None

    def stop(self):
        """Kill the worker's Job and wait for its processes to end (WindowsJobProcess.close). Returns its cleanup record
        ({'all_owned_processes_terminated', 'peak_job_memory_used', ...}); a failure to stop is a record, not an exception."""
        try:
            return self.proc.close()
        except Exception as e:  # noqa: BLE001
            return {'all_owned_processes_terminated': False, 'errors': [f'{type(e).__name__}: {e}']}


def comfy_launcher(cfg, app, card_uuid, port, memory_cap_gb, on_started=None):
    """launcher(executor, run_dir) for run_pair: a fresh ComfyEngine per executor run on the given card and port.
    on_started(engine): called as each worker's process starts, before it is ready (ComfyEngine)."""
    return lambda executor, run_dir: ComfyEngine(cfg, app, run_dir, card_uuid, port, memory_cap_gb, on_started=on_started)


def strip_for_json(rep):
    return json.loads(json.dumps(rep, default=str))
