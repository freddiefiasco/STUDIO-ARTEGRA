"""The blind comparison's case runner, generic part (engine design 7.4): the case table's shape, each run's job body for the
service API, the run record, and the held-equal check that voids a pair. Standard library only. The internal case table (the
inputs, nodes and cards) and the farm driver that submits these bodies are not in this repository.

Engines: the Classic engine of the 5.0.2 build through the release path (a job with no developer field), and the Large-image
engine on the classic plan's own stages and constants through the developer-only force switch of a developer build
(`dev_force_engine: 'banded'`, service/build_channel.py; a release build refuses it at submit).
Runs per case: classic seed A, BES seed A, classic seed B (the noise floor); a run may be taken from an earlier registered run
(the case table's `reuse`, for example R0's classic seed-A outputs).
Held equal in each pair (a run whose record differs is void): input, seed (between classic A and BES A), every setting (the
default preset, protect default), the build, torch.get_num_threads() and the OMP/MKL environment, the card and the node."""
RUNS = ('classic_a', 'bes_a', 'classic_b')
MODES = {'redux': 'standard', 'bolt': 'fast'}
HELD_EQUAL = ('input_sha256', 'settings', 'build', 'threads', 'card', 'node')


def validate_case_table(table):
    """Problems with a case table {'seeds': {'A', 'B'}, 'cases': [{'id', 'mode', 'factor', 'supersamples', 'input', 'node',
    'card', 'runs', 'reuse'?}]} (empty when valid)."""
    err = []
    seeds = table.get('seeds') or {}
    if not all(isinstance(seeds.get(k), int) and not isinstance(seeds.get(k), bool) for k in ('A', 'B')):
        err.append('seeds A and B must be whole numbers')
    elif seeds['A'] == seeds['B']:
        err.append('seeds A and B must differ')
    ids = [c.get('id') for c in table.get('cases') or []]
    if len(set(ids)) != len(ids) or not ids:
        err.append('case ids must be unique and present')
    for c in table.get('cases') or []:
        cid = c.get('id')
        if c.get('mode') not in MODES:
            err.append(f'{cid}: mode must be redux or bolt')
        if c.get('factor') not in (2, 4):
            err.append(f'{cid}: the comparison runs 2x and 4x only')
        if c.get('mode') == 'bolt' and (c.get('factor') != 2 or list(c.get('supersamples') or []) != [2]):
            err.append(f'{cid}: Bolt runs 2x at s 2 only')
        if not isinstance(c.get('supersamples'), list) or not c['supersamples']:
            err.append(f'{cid}: supersamples per stage are required')
        for k in ('input', 'node', 'card'):
            if c.get(k) in (None, ''):
                err.append(f'{cid}: {k} is required')
        runs, reuse = list(c.get('runs') or []), dict(c.get('reuse') or {})
        if any(r not in RUNS for r in runs + list(reuse)):
            err.append(f'{cid}: runs are {RUNS}')
        if sorted(set(runs) | set(reuse)) != sorted(RUNS) or set(runs) & set(reuse):
            err.append(f'{cid}: every run is made or reused, once')
    return err


def seed_of(run, seeds):
    return seeds['B'] if run == 'classic_b' else seeds['A']


def job_body(case, run, media_id, seeds, request_id, output_format='png8'):
    """The service API body of one run (POST /api/jobs): the default preset and protect default, the case's scale and mode,
    the run's seed; the BES side adds only the developer force switch."""
    if run not in RUNS:
        raise ValueError(f'run must be one of {RUNS}')
    body = {'client_request_id': str(request_id), 'media_ids': [media_id],
            'settings': {'scale': int(case['factor']), 'seed': seed_of(run, seeds), 'mode': MODES[case['mode']],
                         'output_format': output_format}}
    if run == 'bes_a':
        body['dev_force_engine'] = 'banded'
    return body


def run_record(case_id, run, job, item, build, env, card, node, output_sha256=None):
    """The record a pair is checked with: what was held equal, from the job, its item, the build and the worker's thread
    record (tools/proof/comfy_nodes/cu_proof env, or the service's)."""
    settings = {k: v for k, v in (job.get('settings') or {}).items() if k != 'seed'}
    return {'case': case_id, 'run': run, 'seed': (job.get('settings') or {}).get('seed'), 'input_sha256': item.get('sha256'),
            'settings': settings, 'effective': {k: v for k, v in (job.get('effective') or {}).items() if k != 'seed'},
            'forced': job.get('dev_force_engine'), 'build': build,
            'threads': {'torch_threads': (env or {}).get('torch_threads'), 'omp_mkl': (env or {}).get('omp_mkl')},
            'card': card, 'node': node, 'plan': item.get('plan'), 'output_sha256': output_sha256}


def held_equal(a, b, same_seed=True, keys=HELD_EQUAL):
    """Differences that void the pair (empty when everything held equal)."""
    out = [k for k in keys if a.get(k) != b.get(k)]
    if a.get('effective') != b.get('effective'):
        out.append('effective')
    if same_seed and a.get('seed') != b.get('seed'):
        out.append('seed')
    return out


def check_case(records):
    """{run: record} of one case -> {'void': bool, 'classic_vs_bes': [...], 'classic_a_vs_b': [...], 'plan': ...}. The BES
    side must have run the classic plan's own stages (plan_forced): equal stage factors, supersamples and sizes."""
    a, x, b = records.get('classic_a'), records.get('bes_a'), records.get('classic_b')
    if not (a and x and b):
        return {'void': True, 'reason': 'a run is missing'}
    d1, d2 = held_equal(a, x), held_equal(a, b, same_seed=False)
    if a.get('seed') == b.get('seed'):
        d2.append('seed B equals seed A')
    st = lambda r: [(s['factor'], s['supersample'], list(s['render_size']), list(s['output_size']))
                    for s in (r.get('plan') or {}).get('stages', [])]
    plan_ok = bool(st(a)) and st(a) == st(x) and (x.get('plan') or {}).get('engine') == 'banded' and x.get('forced') == 'banded'
    return {'void': bool(d1 or d2 or not plan_ok), 'classic_vs_bes': d1, 'classic_a_vs_b': d2, 'plan_forced_ok': plan_ok}
