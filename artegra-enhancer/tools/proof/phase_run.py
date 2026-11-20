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
    stop()
comfy_launcher() makes one for a real ComfyUI worker (the product's command plus the proof packs; tools/proof/harness.py).
The oracle finish and the derived gate run in a fresh process of `python` (the worker runtime's interpreter: torch, scipy).

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
        rd = work / ex
        eng = launcher(ex, rd)
        out_stage = []
        try:
            cur = np.ascontiguousarray(np.asarray(source_u8, np.uint8)[..., :3])
            for st in stages:
                sd = rd / f's{st.index}'
                pd = sd / 'planes'
                _, plane = harness.prepare_inputs(cur, st, eng.input_dir, pd)
                run_id = f'{name}-{ex}-s{st.index}-{uuid.uuid4().hex[:8]}'
                if ex == 'classic':
                    graph, info = harness.classic_graph(st, options)
                else:
                    graph, info = harness.bes_graph(st, plan, pd.as_posix(), Path(plane).as_posix(), run_id, options)
                spec = harness.dump_spec(graph, info, ex, st)
                harness_io.write_spec(eng.dump_root, run_id, spec)
                t0 = time.time()
                row = {'stage': st.index, 'prompt_id': run_id, 'graph_sha256': harness.graph_sha(graph), 'input_plane': plane}
                try:
                    hist = harness.run_prompt(eng.client, harness.prompt_graph(graph, spec), run_id, timeout_s=prompt_timeout_s)
                    row['status'] = (hist.get('status') or {}).get('status_str')
                except harness.RunFailed as e:
                    row.update(status='failed', error=str(e))
                row['seconds'] = round(time.time() - t0, 1)
                man = harness_io.collect(Path(eng.dump_root) / run_id, spec)
                man['roles'].setdefault('input', {'kind': 'plane', 'path': plane})
                row.update(missing=harness_io.check_complete(man, spec), errors=man['errors'], env=man['env'][:1],
                           phase_seconds=man['phase_seconds'], timeline=man['timeline'], spec=spec, graph=graph,
                           roles=man['roles'])
                if row['status'] == 'success' and 'stage_output' in man['roles']:
                    cur = _stage_output_u8(man['roles']['stage_output'], None, st.output)
                    row['stage_output_sha256'] = hashlib.sha256(cur.tobytes()).hexdigest()
                    row['stage_output_entry'] = dict(man['roles']['stage_output'], size=list(st.output))
                out_stage.append(row)
                if row['status'] != 'success':
                    break
        finally:
            text = eng.log_text()
            peak = eng.job_peak()
            eng.stop()
        runs[ex] = {'stages': out_stage, 'job_peak_commit_gb': None if peak is None else round(peak / 2 ** 30, 2),
                    'log_tail': text[-4000:], 'wsum': records.wsum_mark(text, expect_lines=(ex == 'bes' and any(
                        v['class_type'] == 'ClaudeSpotTilesBanded' for r in out_stage for v in r['graph'].values())))}
    for ex, r in runs.items():
        rep['runs'][ex] = {k: v for k, v in r.items() if k != 'stages'}
        rep['runs'][ex]['stages'] = [{k: v for k, v in s.items() if k not in ('graph', 'spec', 'roles')}
                                     for s in r['stages']]
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
        row['threads'] = harness_io.same_threads(c['env'], b['env'])
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
        try:
            self.proc.close()
        except Exception:
            pass


def comfy_launcher(cfg, app, card_uuid, port, memory_cap_gb):
    """launcher(executor, run_dir) for run_pair: a fresh ComfyEngine per executor run on the given card and port."""
    return lambda executor, run_dir: ComfyEngine(cfg, app, run_dir, card_uuid, port, memory_cap_gb)


def strip_for_json(rep):
    return json.loads(json.dumps(rep, default=str))
