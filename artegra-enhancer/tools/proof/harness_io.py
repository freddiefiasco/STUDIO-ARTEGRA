"""The harness's side of the instrumentation's files (tools/proof/comfy_nodes/cu_proof): a prompt's dump folder read back
into the entries the phase counter compares, its node timeline, thread record and errors. Standard library only.

<CU_PROOF_DIR>/<prompt id>/
  spec.json      written by the harness before the prompt (tools/proof/harness.dump_spec)
  events.jsonl   written by the instrumentation: env, node (start, end), dump (role -> plane), cn (call records), error
  dumps/*.plane  the dumped intermediates; cn/*.bin the ControlNet values kept"""
import json
from pathlib import Path


def write_spec(dump_root, prompt_id, spec):
    d = Path(dump_root) / str(prompt_id)
    d.mkdir(parents=True, exist_ok=True)
    (d / 'spec.json').write_text(json.dumps(spec, sort_keys=True, indent=1), encoding='utf8')
    return d


def events(dump_dir):
    p = Path(dump_dir) / 'events.jsonl'
    if not p.is_file():
        return []
    out = []
    for line in p.read_text(encoding='utf8').splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def collect(dump_dir, spec=None):
    """{'roles': {role: entry}, 'timeline': [node events], 'env': [env records], 'errors': [...], 'phase_seconds': {...}}.
    A role dumped twice (a node run twice in one prompt) is an error. The spec's contract files (the BES's stage output
    plane) are added as plane entries when they exist."""
    dump_dir = Path(dump_dir)
    if spec is None and (dump_dir / 'spec.json').is_file():
        spec = json.loads((dump_dir / 'spec.json').read_text(encoding='utf8'))
    roles, timeline, env, errors, cn = {}, [], [], [], {}
    for ev in events(dump_dir):
        t = ev.get('type')
        if t == 'dump':
            if ev['role'] in roles:
                errors.append({'where': 'collect', 'message': f"{ev['role']} was dumped twice"})
            roles[ev['role']] = {k: ev[k] for k in ('kind', 'path', 'form', 'node', 'class', 'output', 'sha256',
                                                    'tensor_shape', 'torch_dtype') if k in ev}
        elif t == 'cn':
            cn.setdefault(ev['role'], []).append({k: ev[k] for k in ('call', 'keys', 'sha256', 'dtypes', 'shapes', 'files')})
        elif t == 'node':
            timeline.append(ev)
        elif t == 'env':
            env.append(ev)
        elif t == 'error':
            errors.append(ev)
    for role, calls in cn.items():
        calls.sort(key=lambda c: c['call'])
        if [c['call'] for c in calls] != list(range(len(calls))):
            errors.append({'where': 'collect', 'message': f'{role}: calls are not 0..n-1'})
        roles[role] = {'kind': 'cn', 'form': 'cn', 'calls': calls}
    for role, f in ((spec or {}).get('files') or {}).items():
        if Path(f['path']).is_file():
            roles[role] = {'kind': 'plane', 'path': str(f['path']), 'form': f.get('form')}
    phase_s = {}
    for ev in timeline:
        ph = ev.get('phase') or 'other'
        phase_s[ph] = round(phase_s.get(ph, 0.0) + float(ev['t1']) - float(ev['t0']), 3)
    return {'roles': roles, 'timeline': timeline, 'env': env, 'errors': errors, 'phase_seconds': phase_s}


def expected_roles(spec):
    """Every role the spec names (dumped node outputs, contract files and the ControlNet records of each sampler)."""
    r = {role for v in spec.get('roles', {}).values() for _, role, _ in v} | set(spec.get('files') or {})
    return r


def check_complete(manifest, spec):
    """The roles the spec names that the run did not produce (a ControlNet role counts once any instance was recorded)."""
    have = set(manifest['roles'])
    missing = sorted(r for r in expected_roles(spec) if r not in have)
    for s in sorted(set((spec.get('cn') or {}).get('nodes', {}).values())):
        if not any(r.startswith(f'cn/{s}/') for r in have):
            missing.append(f'cn/{s}/*')
    return missing


def same_threads(env_a, env_b):
    """Design 7.1's rule for every pair: torch.get_num_threads() and the OMP/MKL environment are equal in both runs. Returns
    the list of differences (empty when equal); a run without a record is a difference."""
    if not env_a or not env_b:
        return ['a run has no thread record']
    a, b = env_a[0], env_b[0]
    out = []
    for k in ('torch_threads', 'interop_threads', 'omp_mkl'):
        if a.get(k) != b.get(k):
            out.append(f'{k}: {a.get(k)!r} != {b.get(k)!r}')
    return out
