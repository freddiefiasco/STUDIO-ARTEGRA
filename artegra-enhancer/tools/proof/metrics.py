"""M1-M6 of the blind comparison (engine design 7.4) per case, their noise floors and the metric half of the pass rule. numpy.

Each output of a case (classic seed A, BES seed A, classic seed B) is measured once into a bundle: the halo metric on the
region grid (tools/proof/halo_grid; M1, M2, M3 and M6's segment terms), the seam detector at both executors' plan positions
(tools/proof/seams; M4), and the fidelity maps here (M5, M6's low-frequency term). Then compare_case() gives, for every metric
and statistic, the classic A and BES A values, the floor and whether the BES is worse beyond it.

| # | Metric (key)                                              | statistics (paired over the same segments)     | worse  |
| M1 | rim lift/drop each side, rim widths, glow, rim_max        | p50, p95, p99; and the union worst 25 (listed) | larger |
| M2 | rise (10-90 distance); slope (normalised peak slope)      | rise p50, p90; slope p50, p10 (the worst tenth) | wider rise, lower slope |
| M3 | DoG detail energy per textured 256 px tile, BES / classic | p10, p50 of the tile ratio                      | lower  |
| M4 | seams: max z, count of z > 4 (both executors' positions)  | max_z, count                                    | higher |
| M5 | CIEDE2000, source vs output area-averaged, blur 1 and 4   | p50, p95                                        | larger |
| M6 | low-frequency |dL*| (same pair), |edge displacement|;      | p50, p95; contrast kept p50, p5 (the worst     | larger; less contrast kept |
|    | contrast kept per segment                                 | twentieth)                                      |        |

Floor per metric and case: the larger of |m(classic A) - m(classic B)| and the halo tools' own sampling floor for that
statistic (their noise_floor.json; SAMPLING_FLOOR_KEYS). For M3 the classic's own ratio is classic B / classic A against 1.
Lost measurements: per M1, M2 and M6 key, one more row ('unmeasured') counts the paired segments each output cannot measure
(a value that is not finite: a softer edge whose 10-90 rise never completes); the BES is worse when it cannot measure more
of them than classic A by more than max(|count(classic B) - count(classic A)|, the count's sampling floor). The halo tools
give no floor for a count, so that floor is 0 unless the sampling floors name one (UNMEASURED_FLOOR_KEY). Without this row
a candidate that loses edges would be compared only where all three measure, and could read 'not worse'.
Pass (metrics): no row worse than classic A by more than its floor. Byte-identical classic A and BES A read 0 everywhere and are
recorded "identical (sha256)"."""
import hashlib

import numpy as np

from tools.proof import colour
from tools.proof.phases import _Arr

PAIRED = (
    ('M1', 'rim_lift_bright', ('p50', 'p95', 'p99'), 'higher'), ('M1', 'rim_drop_bright', ('p50', 'p95', 'p99'), 'higher'),
    ('M1', 'rim_lift_dark', ('p50', 'p95', 'p99'), 'higher'), ('M1', 'rim_drop_dark', ('p50', 'p95', 'p99'), 'higher'),
    ('M1', 'rimw_lift_bright', ('p50', 'p95', 'p99'), 'higher'), ('M1', 'rimw_drop_bright', ('p50', 'p95', 'p99'), 'higher'),
    ('M1', 'rimw_lift_dark', ('p50', 'p95', 'p99'), 'higher'), ('M1', 'rimw_drop_dark', ('p50', 'p95', 'p99'), 'higher'),
    ('M1', 'glow_abs', ('p50', 'p95', 'p99'), 'higher'), ('M1', 'rim_max', ('p50', 'p95', 'p99'), 'higher'),
    ('M2', 'rise', ('p50', 'p90'), 'higher'), ('M2', 'slope', ('p50', 'p10'), 'lower'),
    ('M6', 'disp_abs', ('p50', 'p95'), 'higher'), ('M6', 'contrast_kept', ('p50', 'p5'), 'lower'),
)
SAMPLING_FLOOR_KEYS = {'rim': 'rim_p90_delta', 'glow': 'glow_p90_delta', ('rise', 'p50'): 'rise_median_delta',
                       ('slope', 'p50'): 'slope_median_delta', ('M3', 'p10'): 'hf_tile_p10', ('M3', 'p50'): 'hf_global_ratio',
                       ('M5', 'p50'): 'de00_mean_delta', ('M5', 'p95'): 'de00_p95_delta'}
UNMEASURED_FLOOR_KEY = 'unmeasured_segments'   # a count's sampling floor, when supplied (the halo tools give none: 0)
FID_SIGMAS = (1.0, 4.0)
TILE_FULL = 0.25 * 256 * 256


def _pct(v, p):
    v = v[np.isfinite(v)]
    return float(np.percentile(v, float(p[1:]))) if v.size else None


def _seg_values(A, key):
    if key == 'disp_abs':
        return np.abs(A['disp'])
    if key == 'glow_abs':
        return A['glow_abs']
    return A[key]


def fidelity(source, output, sigmas=FID_SIGMAS, band_blocks=64):
    """M5 and M6's low-frequency term: the output area-averaged to the source grid in linear light (by row bands), both
    Gaussian-blurred by sigma source px in linear light, then CIEDE2000 and |dL*| per source pixel (strided as the halo tools
    do above 2 MP). {'sigma_<s>': {'de_p50', 'de_p95', 'de_mean', 'dl_p50', 'dl_p95'}}."""
    src = np.asarray(source)[..., :3]
    O = _Arr(output if isinstance(output, dict) else {'kind': 'array', 'array': output})
    h, w = src.shape[:2]
    f = O.shape[0] / h
    if abs(f - round(f)) > 1e-9 or abs(O.shape[1] / w - f) > 1e-9:
        raise ValueError('the output is not a whole multiple of the source')
    f = int(round(f))
    lo = np.zeros((h, w, 3), np.float32)
    for by in range(0, h, band_blocks):
        by1 = min(h, by + band_blocks)
        lo[by:by1] = colour.block_mean(colour.linear_from_rgb(O.rows(by * f, by1 * f)), f)
    ls = colour.linear_from_rgb(src)
    out = {}
    for sg in sigmas:
        a = np.stack([colour.gaussian(ls[..., c], sg) for c in range(3)], -1)
        b = np.stack([colour.gaussian(lo[..., c], sg) for c in range(3)], -1)
        st = max(1, int(round(sg / 2))) if h * w > 2_000_000 else 1
        la, lb = colour.lab_from_linear(a[::st, ::st]), colour.lab_from_linear(b[::st, ::st])
        de = colour.ciede2000(la, lb)
        dl = np.abs(lb[..., 0].astype(np.float64) - la[..., 0])
        out[f'sigma_{sg:g}'] = {'de_p50': float(np.percentile(de, 50)), 'de_p95': float(np.percentile(de, 95)),
                                'de_mean': float(de.mean()), 'dl_p50': float(np.percentile(dl, 50)),
                                'dl_p95': float(np.percentile(dl, 95))}
    return out


def output_sha256(output):
    O = _Arr(output if isinstance(output, dict) else {'kind': 'array', 'array': output})
    h = hashlib.sha256()
    for y in range(0, O.shape[0], 1024):
        h.update(np.ascontiguousarray(O.rows(y, min(O.shape[0], y + 1024))).tobytes())
    return h.hexdigest()


def bundle(hm, source, output, seam_positions, P=None, grid_above_mp=None):
    """Every measurement of one output: the halo metric (region grid above 150 MP), M4 at the given positions, M5/M6."""
    from tools.proof import halo_grid, seams
    kw = {} if grid_above_mp is None else {'grid_above_mp': grid_above_mp}
    rep, arrays, tiles = halo_grid.measure(hm, source, output, P, **kw)
    return {'report': rep, 'arrays': arrays, 'tiles': tiles,
            'seams': seams.detect(output, seam_positions.get('rows'), seam_positions.get('cols')),
            'fidelity': fidelity(source, output), 'sha256': output_sha256(output)}


def _common(*arrs):
    keys = [{(int(r), int(s)): i for i, (r, s) in enumerate(zip(A['region'], A['seg'])) if A['status'][i] == 0}
            for A in arrs]
    both = sorted(set.intersection(*(set(k) for k in keys)))
    return [np.array([k[x] for x in both], int) for k in keys]


def _floor(key, stat, metric, sampling):
    s = sampling or {}
    if stat == 'unmeasured':
        return float(s.get(UNMEASURED_FLOOR_KEY, 0.0))
    if metric == 'M1':
        name = SAMPLING_FLOOR_KEYS['glow' if key.startswith('glow') else 'rim'] if not key.startswith('rimw') else None
    elif metric in ('M3', 'M5'):
        name = SAMPLING_FLOOR_KEYS.get((metric, stat))
    else:
        name = SAMPLING_FLOOR_KEYS.get((key, stat))
    return float(s.get(name, 0.0)) if name else 0.0


def _row(metric, key, stat, worse, base, cand, base_b, sampling):
    row = {'metric': metric, 'key': key, 'stat': stat, 'worse_if': worse, 'classic_a': base, 'bes_a': cand,
           'classic_b': base_b}
    if base is None or cand is None or base_b is None:
        return dict(row, floor=None, worse_by=None, worse=True, reason='missing value')
    fl = max(abs(base - base_b), _floor(key, stat, metric, sampling))
    by = (cand - base) if worse == 'higher' else (base - cand)
    return dict(row, floor=fl, worse_by=by, worse=bool(by > fl + 1e-12))


def _tile_ratios(t_num, t_den):
    out = {}
    for xy, d in t_den.items():
        n = t_num.get(xy)
        if n is None or min(n['count'], d['count']) < TILE_FULL:
            continue
        for k, v in d.items():
            if k.startswith('tile_out_band_') and v > 0:
                out.setdefault(k, []).append(n[k] / v)
    return {k: np.array(v) for k, v in out.items()}


MEASURED_ALIKE = ('mode', 'grid', 'n_regions', 'edge_set_hash')


def comparable(*bundles):
    """Problems that make bundles incomparable (empty when they are alike): each must carry the halo metric's measurement
    record (mode, grid, n_regions, edge_set_hash of halo_grid.measure), and the three must have been measured in the same
    mode on the same grid with the same edge set. Segments pair by (region, segment), and those indices name the same source
    segments only then (D5)."""
    out = []
    names = ('classic A', 'BES A', 'classic B')
    reps = [(b.get('report') or {}) for b in bundles]
    for n, r in zip(names, reps):
        missing = [k for k in MEASURED_ALIKE if k not in r]
        if missing:
            out.append(f'{n}: no measurement record ({", ".join(missing)} missing)')
    if out:
        return out
    for k in MEASURED_ALIKE:
        vals = [r.get(k) for r in reps]
        if any(v != vals[0] for v in vals[1:]):
            out.append(f'{k} differs: ' + ', '.join(f'{n} {v!r}' for n, v in zip(names, vals)))
    return out


def compare_case(classic_a, bes_a, classic_b, sampling_floors=None):
    """Every metric row of one case, and the metric pass (no row worse beyond its floor). Bundles that were not measured
    alike (comparable) are refused: no row is compared and the case does not pass ('not comparable')."""
    rows = []
    identical = classic_a.get('sha256') is not None and classic_a.get('sha256') == bes_a.get('sha256')
    problems = comparable(classic_a, bes_a, classic_b)
    if problems:
        return {'rows': [], 'pass_metrics': False, 'comparable': False, 'not_comparable': problems,
                'identical': identical, 'identical_sha256': None, 'paired_segments': 0, 'worst_union_25': [],
                'worse_rows': [], 'reason': 'not comparable: the three outputs were not measured alike'}
    A, Bc, Bb = classic_a['arrays'], bes_a['arrays'], classic_b['arrays']
    ia, ic, ib = _common(A, Bc, Bb)
    for metric, key, stats, worse in PAIRED:
        va, vc, vb = (np.asarray(_seg_values(X, key)[i], np.float64) for X, i in ((A, ia), (Bc, ic), (Bb, ib)))
        # paired per key: a segment whose value one output cannot measure (rise, slope and contrast kept are two-sided
        # only) is left out of all three, so no output is measured on a kinder subset; each output's count is reported
        fin = np.isfinite(va) & np.isfinite(vc) & np.isfinite(vb)
        unmeasured = {k: int((~np.isfinite(v)).sum()) for k, v in (('classic_a', va), ('bes_a', vc), ('classic_b', vb))}
        for st in stats:
            r = _row(metric, key, st, worse, _pct(va[fin], st), _pct(vc[fin], st), _pct(vb[fin], st), sampling_floors)
            r.update(n=int(fin.sum()), unmeasured=unmeasured)
            rows.append(r)
        # lost measurements: more segments the BES cannot measure than classic A, beyond classic B's spread (and a
        # supplied count floor), is worse even where the paired statistics above agree
        r = _row(metric, key, 'unmeasured', 'higher', unmeasured['classic_a'], unmeasured['bes_a'],
                 unmeasured['classic_b'], sampling_floors)
        r.update(n=int(va.size), unmeasured=unmeasured)
        rows.append(r)
    rc, rb = _tile_ratios(bes_a['tiles'], classic_a['tiles']), _tile_ratios(classic_b['tiles'], classic_a['tiles'])
    for band in sorted(set(rc) | set(rb)):
        for st in ('p10', 'p50'):
            c, b = _pct(rc.get(band, np.zeros(0)), st), _pct(rb.get(band, np.zeros(0)), st)
            r = _row('M3', band.replace('tile_out_', ''), st, 'lower', 1.0, c, b, sampling_floors)
            rows.append(r)
    for st in ('max_z', 'count_z_gt_4'):
        g = lambda x: (x['seams'].get(st) if x['seams'].get(st) is not None else 0.0)
        rows.append(_row('M4', 'seams', st, 'higher', float(g(classic_a)), float(g(bes_a)), float(g(classic_b)),
                         sampling_floors))
    for sg in classic_a['fidelity']:
        for key, mid in (('de', 'M5'), ('dl', 'M6')):
            for st in ('p50', 'p95'):
                k = f'{key}_{st}'
                rows.append(_row(mid, f'{key}_{sg}', st, 'higher', classic_a['fidelity'][sg][k], bes_a['fidelity'][sg][k],
                                 classic_b['fidelity'][sg][k], sampling_floors))
    if identical:
        for r in rows:
            r.update(worse=False, worse_by=0.0)
    worst = sorted({(w['x'], w['y']): w for w in classic_a['report'].get('worst', []) + bes_a['report'].get('worst', [])}
                   .values(), key=lambda w: -(w.get('halo_index') or 0))[:25]
    return {'rows': rows, 'pass_metrics': not any(r['worse'] for r in rows), 'comparable': True, 'not_comparable': [],
            'identical': identical,
            'identical_sha256': classic_a.get('sha256') if identical else None, 'paired_segments': int(ia.size),
            'worst_union_25': worst, 'worse_rows': [r for r in rows if r['worse']]}


def registered_rules():
    """The text the proof registers with the case table before the first comparison run."""
    return {'metrics': [{'metric': m, 'key': k, 'stats': list(s), 'worse_if': w} for m, k, s, w in PAIRED]
            + [{'metric': 'M3', 'key': 'band_<s1>_<s2>', 'stats': ['p10', 'p50'], 'worse_if': 'lower'},
               {'metric': 'M4', 'key': 'seams', 'stats': ['max_z', 'count_z_gt_4'], 'worse_if': 'higher'},
               {'metric': 'M5', 'key': 'de_sigma_1, de_sigma_4', 'stats': ['p50', 'p95'], 'worse_if': 'higher'},
               {'metric': 'M6', 'key': 'dl_sigma_1, dl_sigma_4', 'stats': ['p50', 'p95'], 'worse_if': 'higher'}],
            'floors_rule': 'per metric and case: max(|m(classic A) - m(classic B)|, the halo tools\' sampling floor for the '
                           'statistic (SAMPLING_FLOOR_KEYS of tools/proof/metrics.py))',
            'pass_rule': 'per case: no metric worse than classic A by more than its floor, and both judges\' blind verdicts '
                         'the same or better on every criterion (tools/proof/tally.py)',
            'paired_over': 'the segments measured ok in classic A, BES A and classic B, by (region, segment); per key, '
                           'those whose value is finite in all three (a value one output cannot measure leaves that '
                           'segment out of all three, and is judged by the lost-measurements rule; no segment left reads '
                           'as a missing value, which is worse)',
            'lost_measurements': {
                'metrics': [{'metric': m, 'key': k, 'stat': 'unmeasured', 'worse_if': 'higher'} for m, k, _, _ in PAIRED],
                'rule': 'per M1, M2 and M6 key, over the segments measured ok in all three outputs: worse when '
                        'unmeasured(BES A) - unmeasured(classic A) > max(|unmeasured(classic B) - unmeasured(classic A)|, '
                        'the count\'s sampling floor); unmeasured = the segments whose value for that key is not finite',
                'sampling_floor_key': UNMEASURED_FLOOR_KEY,
                'sampling_floor_rule': 'the halo tools\' noise_floor.json gives no floor for a segment count, so it is 0 '
                                       'unless the sampling floors passed to compare_case name one under this key'},
            'comparable': 'the three outputs measured alike (the same halo metric mode, grid, region count and edge set); '
                          'otherwise the case is not comparable and does not pass'}


def measure_case(tools_dir, source, outputs, seam_positions):
    """One case measured whole in this process (the halo tools' interpreter): {'result': compare_case's report, 'worst':
    {run: the bundle's worst list}, 'halo': the tools' record}. outputs: {'classic_a', 'bes_a', 'classic_b'} u8 arrays."""
    from tools.proof import halo_grid
    hm, info = halo_grid.load(tools_dir)
    b = {k: bundle(hm, source, v, seam_positions) for k, v in outputs.items()}
    r = compare_case(b['classic_a'], b['bes_a'], b['classic_b'], (info.get('noise_floor') or {}).get('floors'))
    return {'result': {k: v for k, v in r.items() if k != 'rows'}, 'rows': r.get('rows'),
            'worst': {k: v['report'].get('worst') for k, v in b.items()},
            'halo': {k: info.get(k) for k in ('path', 'version', 'sha256', 'noise_floor_sha256')}}


def main(argv=None):
    """python -B -m tools.proof.metrics measure --halo <tools> --source <.npy> --classic-a <.npy> --bes-a <.npy>
    --classic-b <.npy> --seams <positions.json>: measure_case in the halo tools' interpreter (a caller in another one, the
    service tests', runs this as a subprocess); prints its JSON."""
    import argparse
    import json
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['measure'])
    for k in ('--halo', '--source', '--classic-a', '--bes-a', '--classic-b', '--seams'):
        ap.add_argument(k, required=True)
    a = ap.parse_args(argv)
    outs = {'classic_a': np.load(a.classic_a), 'bes_a': np.load(a.bes_a), 'classic_b': np.load(a.classic_b)}
    with open(a.seams, encoding='utf8') as f:
        pos = json.load(f)
    print(json.dumps(measure_case(a.halo, np.load(a.source), outs, pos), default=str))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
