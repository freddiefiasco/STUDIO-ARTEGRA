"""The noise-floor runner of design 7.3, measured from the oracle's own runs only, on the machine where the pair ran: 5.0.1's
classic finish (tools/proof/classic.py) on the pair's own decoded planes at three thread counts (the default, 7 and 13) plus one
classic variant with torch pow evaluated in 333-row chunks (the E9 chunk boundaries a band would move). F is the largest
differing count across those classic-against-classic comparisons (every pair of the four runs), per output size class.

Each run is a fresh process (the thread count is set before any work), with the interpreter given (the worker runtime's):
    python -B -m tools.proof.noise_floor --job <job.json> --out <dir> [--python <interpreter>] [--floors <floors.json>]
job.json as tools/proof/classic.py's. The record and (with --floors) the floor of its size class are written."""
import argparse
import itertools
import json
import subprocess
import sys
from pathlib import Path

from tools.proof import phases

VARIANTS = (('default', None, None), ('threads7', 7, None), ('threads13', 13, None), ('pow333', None, 333))
SIZE_CLASSES = ((8.0, 'le8'), (32.0, 'le32'), (64.0, 'le64'), (150.0, 'le150'), (300.0, 'le300'), (700.0, 'le700'),
                (float('inf'), 'gt700'))


def size_class(output_mp):
    for top, name in SIZE_CLASSES:
        if output_mp <= top:
            return name
    raise AssertionError


def run(job_path, out_dir, python=None, app=None, variants=VARIANTS, timeout_s=4 * 3600):
    """Run every variant and compare every pair. Returns the record (variants, pairs, F, size class)."""
    job = json.loads(Path(job_path).read_text(encoding='utf8'))
    app = Path(app or job['app'])
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    runs = []
    for name, threads, chunk in variants:
        out = out_dir / f'{name}.plane'
        cmd = [python or sys.executable, '-B', '-m', 'tools.proof.classic', 'finish', '--job', str(job_path), '--out', str(out)]
        if threads:
            cmd += ['--threads', str(threads)]
        if chunk:
            cmd += ['--pow-chunk', str(chunk)]
        p = subprocess.run(cmd, cwd=app, capture_output=True, text=True, timeout=timeout_s)
        if p.returncode != 0:
            raise RuntimeError(f'noise-floor variant {name} failed: {p.stderr[-2000:]}')
        rec = json.loads(p.stdout.strip().splitlines()[-1])
        runs.append(dict(rec, variant=name, plane=str(out)))
    pairs = []
    for a, b in itertools.combinations(runs, 2):
        r = phases.compare_entries({'kind': 'plane', 'path': a['plane']}, {'kind': 'plane', 'path': b['plane']}, 'bitwise')
        pairs.append({'a': a['variant'], 'b': b['variant'], 'count': r['count'], 'max_abs': r['max_abs']})
    ow, oh = int(job['inputs']['output_width']), int(job['inputs']['output_height'])
    mp = ow * oh / 1e6
    return {'variants': runs, 'pairs': pairs, 'F': max(p['count'] for p in pairs), 'output_mp': round(mp, 2),
            'size_class': size_class(mp), 'rule': 'F = the largest differing count across every pair of the four classic runs'}


def update_floors(path, record, label):
    """Keep the largest F per size class across the runs recorded in floors.json (with each run's label)."""
    p = Path(path)
    d = json.loads(p.read_text(encoding='utf8')) if p.is_file() else {'classes': {}}
    c = d['classes'].setdefault(record['size_class'], {'F': 0, 'runs': []})
    c['runs'].append({'label': label, 'F': record['F'], 'output_mp': record['output_mp']})
    c['F'] = max(r['F'] for r in c['runs'])
    p.write_text(json.dumps(d, indent=1, sort_keys=True), encoding='utf8')
    return d


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--job', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--python')
    ap.add_argument('--floors')
    ap.add_argument('--label', default='')
    a = ap.parse_args(argv)
    rec = run(a.job, a.out, python=a.python)
    Path(a.out, 'noise_floor.json').write_text(json.dumps(rec, indent=1), encoding='utf8')
    if a.floors:
        update_floors(a.floors, rec, a.label)
    print(json.dumps({'F': rec['F'], 'size_class': rec['size_class']}))


if __name__ == '__main__':
    main()
