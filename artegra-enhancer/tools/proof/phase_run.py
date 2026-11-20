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

from tools.proof import classic, harness, harness_io, phases, records, seams, tiers


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


def _run_part(ex, name, st, plan, part, eng, worker, pd, plane, options, timeout_s):
    run_id = f'{name}-{ex}-s{st.index}{part or ""}-{uuid.uuid4().hex[:8]}'
    if ex == 'classic':
        graph, info = harness.classic_graph(st, options)
    else:
        graph, info = harness.bes_graph(st, plan, pd.as_posix(), Path(plane).as_posix(), run_id, options, part=part)
    spec = harness.dump_spec(graph, info, ex, st)
    harness_io.write_spec(eng.dump_root, run_id, spec)
    t0 = time.time()
    p = {'part': part, 'prompt_id': run_id, 'graph_sha256': harness.graph_sha(graph), 'worker': worker['n']}
    try:
        hist = harness.run_prompt(eng.client, harness.prompt_graph(graph, spec), run_id, timeout_s=timeout_s)
        p['status'] = (hist.get('status') or {}).get('status_str')
    except harness.RunFailed as e:
        p.update(status='failed', error=str(e))
    p['seconds'] = round(time.time() - t0, 1)
    man = harness_io.collect(Path(eng.dump_root) / run_id, spec)
    p.update(missing=harness_io.check_complete(man, spec), errors=man['errors'], env=man['env'][:1],
             phase_seconds=man['phase_seconds'], timeline=man['timeline'], spec=spec, graph=graph, roles=man['roles'])
    worker['segments'].append([st.index, part])
    return p


def _merge_parts(row, parts):
    """One stage row from its prompts: the single prompt's fields, or, for a split stage, both parts' roles, timelines and
    errors together, the env of part A (each part's env is checked by the thread rule), the finish graph of part B."""
    if len(parts) == 1 and parts[0]['part'] is None:
        p = parts[0]
        row.update({k: v for k, v in p.items() if k not in ('part', 'worker')}, graphs=[p['graph']])
        row['parts'] = [{k: v for k, v in p.items() if k in ('part', 'prompt_id', 'graph_sha256', 'worker', 'status')}]
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


def _run_executor(ex, name, stages, plan, rd, launcher, source_u8, options, timeout_s):
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
                              timeout_s)
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
    peaks = [w.get('job_peak_bytes') for w in workers]
    spot = any(v['class_type'] == 'ClaudeSpotTilesBanded' for r in out_stage for g in r.get('graphs', []) for v in g.values())
    return {'stages': out_stage,
            'workers': [{k: v for k, v in w.items() if k not in ('log', 'engine')} for w in workers],
            'job_peak_commit_gb': None if (not peaks or any(p is None for p in peaks)) else round(max(peaks) / 2 ** 30, 2),
            'log_tail': text[-4000:], 'wsum': records.wsum_mark(text, expect_lines=(ex == 'bes' and spot))}


def run_pair(name, stages, cap, source_u8, work, launcher, app, python=None, mode='until_bxf', floor_F=None,
             options='base', gate=True, oracle=True, gate_fn=None, oracle_fn=None, prompt_timeout_s=6 * 3600):
    """Run one pair (one stage, or a chain whose stages run on one worker per executor, each executor feeding its own next
    stage). Returns the report; nothing is retried, and a failure is reported as one. Each compared stage row says which
    finish rule ran (finish_rule)."""
    if mode not in MODES:
        raise ValueError(f'mode must be one of {MODES} (got {mode!r})')
    work = Path(work)
    python = python or sys.executable
    gate_fn = gate_fn or (lambda *a: cpu_gate(python, app, *a))
    oracle_fn = oracle_fn or (lambda job, out: cpu_oracle(python, app, job, out))
    plan = harness.forced_plan(stages, cap)
    rep = {'pair': name, 'cap_gb': float(cap), 'mode': mode, 'plan_forced': plan.to_dict(), 'runs': {}, 'stages': [],
           'started': time.time()}
    if not plan.ok:
        rep['error'] = f'plan_forced refused: {plan.reason}'
        return rep
    runs = {}
    for ex in ('classic', 'bes'):
        runs[ex] = _run_executor(ex, name, stages, plan, work / ex, launcher, source_u8, options, prompt_timeout_s)
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
            for side, roles, sd in (('classic', croles, work / 'classic'), ('bes', broles, work / 'bes')):
                u = roles.get('union/protect')
                if u:
                    out = sd / f's{st.index}' / 'derived_gate.plane'
                    rel = roles.get('union/release')
                    g = c['spec']['gate']
                    gate_fn(u['path'], rel['path'] if rel else None, g['dilate'], g['feather'], out)
                    roles['gate'] = {'kind': 'plane', 'path': str(out), 'form': 'bitwise', 'derived': True}
        bes_own = broles.pop('stage_output', None)
        oracle_out = None
        if oracle:
            job = {'app': str(app), 'inputs': classic.finish_inputs(b['graph']),
                   'planes': {'creative': broles['raw8']['path'], 'structure': broles['rawlo8']['path'],
                              'init': broles['init']['path'], 'pre': b['input_plane'],
                              'protect': (broles.get('union/protect') or {}).get('path'),
                              'release': (broles.get('union/release') or {}).get('path')}}
            jp = work / 'bes' / f's{st.index}' / 'oracle_job.json'
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
    rep['ended'] = time.time()
    return rep


class ComfyEngine:
    """A real ComfyUI worker of a developer build for one executor run (fresh, so nothing is cached between runs)."""

    def __init__(self, cfg, app, run_dir, card_uuid, port, memory_cap_gb, ready_timeout_s=600):
        from service import comfy, windows_job, workers
        self.dir = Path(run_dir) / 'worker'
        for d in ('input', 'output', 'temp', 'user', 'proof'):
            (self.dir / d).mkdir(parents=True, exist_ok=True)
        self.input_dir, self.dump_root = self.dir / 'input', self.dir / 'proof'
        proof_dir = Path(app) / 'tools' / 'proof'
        yaml = self.dir / 'extra_model_paths.yaml'
        yaml.write_text(harness.worker_yaml(cfg, proof_dir), encoding='utf8')
        cmd, self.differs = harness.worker_command(cfg, self.dir, port, yaml, proof_dir)
        env = {k: v for k, v in os.environ.items() if k.upper() not in workers.SECRET_ENV}
        tmp = str(self.dir / 'temp')
        env.update(TEMP=tmp, TMP=tmp, HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', PYTHONDONTWRITEBYTECODE='1',
                   PYTHONNOUSERSITE='1', PYTHONUNBUFFERED='1', PYTHONIOENCODING='utf-8', CUDA_VISIBLE_DEVICES=card_uuid,
                   CUDA_DEVICE_ORDER='PCI_BUS_ID', CU_PROOF_DIR=str(self.dump_root))
        self.log = self.dir / 'worker-log.txt'
        self.proc = windows_job.WindowsJobProcess(cmd, cwd=str(self.dir), env=env, log_path=self.log,
                                                  memory_limit_bytes=int(float(memory_cap_gb) * (1 << 30)))
        self.client = comfy.ComfyClient(port)
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


def comfy_launcher(cfg, app, card_uuid, port, memory_cap_gb):
    """launcher(executor, run_dir) for run_pair: a fresh ComfyEngine per executor run on the given card and port."""
    return lambda executor, run_dir: ComfyEngine(cfg, app, run_dir, card_uuid, port, memory_cap_gb)


def strip_for_json(rep):
    return json.loads(json.dumps(rep, default=str))
