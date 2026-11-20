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


def compare_case(classic_a, bes_a, classic_b, sampling_floors=None):
    """Every metric row of one case, and the metric pass (no row worse beyond its floor)."""
    rows = []
    identical = classic_a.get('sha256') is not None and classic_a.get('sha256') == bes_a.get('sha256')
    A, Bc, Bb = classic_a['arrays'], bes_a['arrays'], classic_b['arrays']
    ia, ic, ib = _common(A, Bc, Bb)
    for metric, key, stats, worse in PAIRED:
        va, vc, vb = (_seg_values(X, key)[i] for X, i in ((A, ia), (Bc, ic), (Bb, ib)))
        for st in stats:
            rows.append(_row(metric, key, st, worse, _pct(va, st), _pct(vc, st), _pct(vb, st), sampling_floors))
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
    return {'rows': rows, 'pass_metrics': not any(r['worse'] for r in rows), 'identical': identical,
            'identical_sha256': classic_a.get('sha256') if identical else None, 'paired_segments': int(ia.size),
            'worst_union_25': worst, 'worse_rows': [r for r in rows if r['worse']]}


def registered_rules():
    """The text eng:prove registers with the case table before the first comparison run."""
    return {'metrics': [{'metric': m, 'key': k, 'stats': list(s), 'worse_if': w} for m, k, s, w in PAIRED]
            + [{'metric': 'M3', 'key': 'band_<s1>_<s2>', 'stats': ['p10', 'p50'], 'worse_if': 'lower'},
               {'metric': 'M4', 'key': 'seams', 'stats': ['max_z', 'count_z_gt_4'], 'worse_if': 'higher'},
               {'metric': 'M5', 'key': 'de_sigma_1, de_sigma_4', 'stats': ['p50', 'p95'], 'worse_if': 'higher'},
               {'metric': 'M6', 'key': 'dl_sigma_1, dl_sigma_4', 'stats': ['p50', 'p95'], 'worse_if': 'higher'}],
            'floors_rule': 'per metric and case: max(|m(classic A) - m(classic B)|, the halo tools\' sampling floor for the '
                           'statistic (SAMPLING_FLOOR_KEYS of tools/proof/metrics.py))',
            'pass_rule': 'per case: no metric worse than classic A by more than its floor, and both judges\' blind verdicts '
                         'the same or better on every criterion (tools/proof/tally.py)',
            'paired_over': 'the segments measured ok in classic A, BES A and classic B, by (region, segment)'}
