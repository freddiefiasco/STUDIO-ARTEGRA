"""M4, the seam detector (engine design 7.4 M4, 5 Q3b): row- and column-mean |grad L*| and mean L* steps, z against the +-16
neighbouring rows (columns), at every band, strip and tile row and column of both executors, the positions taken from the
plan. numpy, by row bands (a plane is never read whole).

For each boundary position p of an output (in output px):
  grad z:  g[p] = mean over the row of |L*[p] - L*[p - 1]|, against g at p - 16 .. p + 16 without p;
  step z:  s[p] = |mean L*[p] - mean L*[p - 1]|, against s at the same neighbours;
  z = (value - mean(neighbours)) / max(std(neighbours), STD_FLOOR). Flagged: z > 4.
Columns the same along x. Reported: the max z and the count of z > 4 per kind, and every flag with its position.

Positions (positions()): for every stage of the plan, in that stage's output px, then scaled to the final output (a seam made
at an earlier pass is carried, magnified, by the later passes):
  dat          the x4 model's tile-row and tile-column cross-fades (engine/bands.dat_tile_rows; the BES's DAT bands are these)
  vae          the VAE's three tilings (1024 px tiles, 64 px overlap; ComfyUI tiled_scale's starts and ends), encode and decode
  window       the clamped edge windows of the sampler (1024 px windows; the window grid moves every step, the clamps do not)
  clamp_strip  the finish's agree5 clamp, run in 1024-row strips
  bxf_band     (BES) every multiple of 288 rows: every registered band height's starts (engine/bands.ALIGN)
  lanczos      (BES) the Lanczos passes' row bands and column strips (engine/lanczos_bands ROW_BAND, COL_STRIP) in the canvas
  pad_band     (BES) the stage-input pad's row bands (service/banded_runner.PAD_BAND), in input px"""
import numpy as np

from engine import bands as _bands
from tools.proof import colour
from tools.proof.phases import _Arr

NEIGHBOURS = 16
Z_FLAG = 4.0
STD_FLOOR = 1e-3
VAE_TILE_PX, VAE_OVERLAP_PX, VAE_COMPRESSION = 1024, 64, 8
WINDOW_PX = 1024
CLAMP_STRIP = 1024
LANCZOS_ROW_BAND, LANCZOS_COL_STRIP = 1152, 256
PAD_BAND = 1152


def _entry(x):
    return x if isinstance(x, dict) else {'kind': 'array', 'array': x}


def profiles(img, band_rows=512):
    """Row and column profiles of L*: row_grad[y] = mean |L[y] - L[y-1]| (NaN at 0), row_mean[y], col_grad[x], col_mean[x]."""
    A = _Arr(_entry(img))
    H, W = A.shape[0], A.shape[1]
    row_grad = np.full(H, np.nan)
    row_mean = np.zeros(H)
    col_grad_sum = np.zeros(W)
    col_sum = np.zeros(W)
    prev = None
    for y0 in range(0, H, band_rows):
        y1 = min(H, y0 + band_rows)
        L = colour.lstar(A.rows(y0, y1)).astype(np.float64)
        row_mean[y0:y1] = L.mean(1)
        full = L if prev is None else np.concatenate([prev, L])
        d = np.abs(np.diff(full, axis=0)).mean(1)
        row_grad[y0 + (0 if prev is not None else 1):y1] = d
        col_grad_sum[1:] += np.abs(np.diff(L, axis=1)).sum(0)
        col_sum += L.sum(0)
        prev = L[-1:]
    col_grad = np.full(W, np.nan)
    col_grad[1:] = col_grad_sum[1:] / H
    return {'row_grad': row_grad, 'row_mean': row_mean, 'col_grad': col_grad, 'col_mean': col_sum / H}


def _z(v, p, k=NEIGHBOURS):
    n = v.shape[0]
    if not 1 <= p < n:
        return None
    idx = [i for i in range(p - k, p + k + 1) if i != p and 1 <= i < n]
    nb = v[idx]
    nb = nb[np.isfinite(nb)]
    if nb.size < 4 or not np.isfinite(v[p]):
        return None
    return float((v[p] - nb.mean()) / max(nb.std(), STD_FLOOR))


def _steps(mean):
    s = np.full(mean.shape[0], np.nan)
    s[1:] = np.abs(np.diff(mean))
    return s


def detect(img, rows=None, cols=None, k=NEIGHBOURS, z_flag=Z_FLAG, band_rows=512, prof=None):
    """rows, cols: {kind: [positions]} (positions() gives both executors'). Returns {'max_z', 'count_z_gt_4', 'by_kind',
    'flags'} with flags [{'axis', 'kind', 'pos', 'z_grad', 'z_step'}] for z > z_flag."""
    P = prof or profiles(img, band_rows)
    series = {'row': (P['row_grad'], _steps(P['row_mean'])), 'col': (P['col_grad'], _steps(P['col_mean']))}
    flags, by_kind, max_z, count = [], {}, None, 0
    for axis, groups in (('row', rows or {}), ('col', cols or {})):
        g, s = series[axis]
        for kind, ps in groups.items():
            bk = by_kind.setdefault(f'{axis}/{kind}', {'positions': 0, 'max_z': None, 'count_z_gt_4': 0})
            for p in sorted(set(int(x) for x in ps)):
                zg, zs = _z(g, p, k), _z(s, p, k)
                zs_ = [z for z in (zg, zs) if z is not None]
                if not zs_:
                    continue
                bk['positions'] += 1
                z = max(zs_)
                bk['max_z'] = z if bk['max_z'] is None else max(bk['max_z'], z)
                max_z = z if max_z is None else max(max_z, z)
                if z > z_flag:
                    count += 1
                    bk['count_z_gt_4'] += 1
                    flags.append({'axis': axis, 'kind': kind, 'pos': p, 'z_grad': zg, 'z_step': zs})
    return {'max_z': max_z, 'count_z_gt_4': count, 'by_kind': by_kind, 'flags': flags, 'neighbours': k, 'z_flag': z_flag}


# --- positions from the plan ---------------------------------------------------------------------------------------------

def tiled_scale_spans(n, tile, overlap):
    """ComfyUI tiled_scale's tiles along one axis of n samples: [(start, end)]."""
    if n <= tile:
        return [(0, n)]
    out = []
    for p in range(0, n - overlap, tile - overlap):
        pos = max(0, min(n - overlap, p))
        out.append((pos, pos + min(tile, n - pos)))
    return out


def _vae_bounds(n_px):
    """Start and end rows (px) of the three tilings' tiles along an axis of n_px pixels (latent = px / 8)."""
    t, ov = VAE_TILE_PX // VAE_COMPRESSION, VAE_OVERLAP_PX // VAE_COMPRESSION
    n = n_px // VAE_COMPRESSION
    out = set()
    for tile in (t, t // 2, t * 2):
        for a, b in tiled_scale_spans(n, tile, ov):
            out.update((a * VAE_COMPRESSION, b * VAE_COMPRESSION))
    return out


def _stage_positions(st, executor):
    """{'rows': {kind: set}, 'cols': {kind: set}} of one stage, in its output px (render px / s, input px * f)."""
    f, s = float(st['factor']), float(st['supersample'])
    pw, ph = st['padded_size']
    rw, rh = st['render_size']
    rows, cols = {}, {}
    dat = _bands.dat_tile_rows(ph, pw)
    ry = set()
    for i in range(1, len(dat)):
        ry.update((dat[i][0].cy0, dat[i - 1][0].cy1))
    cx = set()
    for i in range(1, len(dat[0])):
        cx.update((dat[0][i].cx0, dat[0][i - 1].cx1))
    rows['dat'] = {v * f for v in ry}
    cols['dat'] = {v * f for v in cx}
    rows['vae'] = {v / s for v in _vae_bounds(rh)}
    cols['vae'] = {v / s for v in _vae_bounds(rw)}
    rows['window'] = {v / s for v in (WINDOW_PX, rh - WINDOW_PX) if 0 < v < rh}
    cols['window'] = {v / s for v in (WINDOW_PX, rw - WINDOW_PX) if 0 < v < rw}
    oh = st['output_size'][1]
    rows['clamp_strip'] = set(range(CLAMP_STRIP, oh, CLAMP_STRIP))
    if executor == 'bes':
        rows['bxf_band'] = set(range(_bands.ALIGN, oh, _bands.ALIGN))
        rows['lanczos'] = {v / s for v in range(LANCZOS_ROW_BAND, rh, LANCZOS_ROW_BAND)}
        cols['lanczos'] = {v / s for v in range(LANCZOS_COL_STRIP, rw, LANCZOS_COL_STRIP)}
        rows['pad_band'] = {v * f for v in range(PAD_BAND, ph, PAD_BAND)}
    return {'rows': rows, 'cols': cols}


def positions(stages, executors=('classic', 'bes')):
    """Seam positions of a plan's stages (dicts or Stage objects with factor, supersample, padded_size, render_size,
    output_size), in the final output's px, for the given executors: {'rows': {kind: [y]}, 'cols': {kind: [x]}}."""
    rows_st = [s if isinstance(s, dict) else {k: getattr(s, k) for k in ('factor', 'supersample', 'padded_size',
                                                                           'render_size', 'output_size')} for s in stages]
    fw, fh = rows_st[-1]['output_size']
    out = {'rows': {}, 'cols': {}}
    for st in rows_st:
        sx, sy = fw / st['output_size'][0], fh / st['output_size'][1]
        for ex in executors:
            p = _stage_positions(st, ex)
            for axis, scale, limit in (('rows', sy, fh), ('cols', sx, fw)):
                for kind, vals in p[axis].items():
                    tgt = out[axis].setdefault(kind, set())
                    tgt.update(int(round(v * scale)) for v in vals if 0 < v * scale < limit)
    return {axis: {k: sorted(v) for k, v in d.items()} for axis, d in out.items()}
