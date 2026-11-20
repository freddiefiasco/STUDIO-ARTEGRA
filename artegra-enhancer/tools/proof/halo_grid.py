"""The region-grid wrapper of the halo tools' halo_metric.measure (engine design 2.11, 7.4, 9.2: every proof output is measured
with the halo metric; above 150 MP on a registered grid of regions read by memory map, never a whole decode).

The halo tools are read by path (CU_HALO_TOOLS or an explicit folder), never copied: load() records their VERSION and the
sha256 of halo_metric.py (and of their noise_floor.json). They need numpy, scipy, opencv, Pillow and scikit-image (their own
interpreter); this module adds nothing to those.

measure():
- up to GRID_ABOVE_MP output megapixels, with the output as an array: halo_metric.measure on the whole pair (region 0);
- above that, or for a plane: a grid of source-aligned regions (cores of `core_src` source px, each read with `margin_src`
  source px of real context on every side, clipped at the image), the output region read from the plane's memory map at
  exactly f x the source box. Each region is measured on its own; a segment is kept by the region whose core holds its
  centre, and its centre is moved to the whole output's coordinates. Edge detection depends on the source alone, so two
  outputs of one source measured on the same grid have the same segments, and pair by (region, segment).
- the detail tiles (256 output px) are kept where they lie wholly inside a region's core, keyed by their global origin.
Fidelity (M5, M6) is computed by tools/proof/metrics on the source grid, the same way in both modes."""
import hashlib
import importlib.util
import json
import math
import os
import sys
from pathlib import Path

import numpy as np

GRID_ABOVE_MP = 150.0
MARGIN_SRC = 96
TILE = 256
_MOD = 'cu_halo_metric'


def load(tools_dir=None):
    """(halo_metric module, {'path', 'version', 'sha256', 'noise_floor_sha256', 'noise_floor'})."""
    d = Path(tools_dir or os.environ.get('CU_HALO_TOOLS') or '')
    path = d / 'halo_metric.py'
    if not path.is_file():
        raise FileNotFoundError('the halo tools folder (CU_HALO_TOOLS) has no halo_metric.py')
    data = path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    mod = sys.modules.get(_MOD)
    if mod is None or getattr(mod, '_cu_sha256', None) != sha:
        spec = importlib.util.spec_from_file_location(_MOD, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[_MOD] = mod
        spec.loader.exec_module(mod)
        mod._cu_sha256 = sha
    info = {'path': str(path), 'version': mod.VERSION, 'sha256': sha}
    nf = d / 'noise_floor.json'
    if nf.is_file():
        b = nf.read_bytes()
        info['noise_floor_sha256'] = hashlib.sha256(b).hexdigest()
        info['noise_floor'] = json.loads(b.decode('utf8'))
    return mod, info


def _scale(src_shape, out_shape):
    fy, fx = out_shape[0] / src_shape[0], out_shape[1] / src_shape[1]
    if abs(fx - fy) > 1e-9 or abs(fx - round(fx)) > 1e-9:
        raise ValueError(f'the output is not a whole multiple of the source ({fx} x {fy})')
    return int(round(fx))


def grid(src_w, src_h, f, core_src=None, margin_src=MARGIN_SRC):
    """Regions in source px: [{'id', 'core': [x0, y0, x1, y1], 'read': [x0, y0, x1, y1]}]."""
    core = int(core_src or max(128, 2048 // f))
    out = []
    for y0 in range(0, src_h, core):
        for x0 in range(0, src_w, core):
            c = [x0, y0, min(src_w, x0 + core), min(src_h, y0 + core)]
            r = [max(0, c[0] - margin_src), max(0, c[1] - margin_src), min(src_w, c[2] + margin_src),
                 min(src_h, c[3] + margin_src)]
            out.append({'id': len(out), 'core': c, 'read': r})
    return out


class _Out:
    """The output as an array or a plane: shape and a region reader (memory map for a plane)."""

    def __init__(self, output):
        if isinstance(output, dict):
            from engine import planes
            self.plane = planes.Plane.open(output['path'])
            self.shape = self.plane.shape
            self.region = self._plane_region
        else:
            self.a = np.asarray(output)
            self.shape = self.a.shape
            self.region = lambda x0, y0, x1, y1: self.a[y0:y1, x0:x1]

    def _plane_region(self, x0, y0, x1, y1):
        m = self.plane.map('r')
        try:
            return np.array(m[y0:y1, x0:x1, :3])
        finally:
            del m


def _tiles(arrays, ox, oy, core_out):
    """{(x0, y0): {'count', name: energy}} of the detail tiles wholly inside the core (global origins)."""
    out = {}
    if 'tile_count' not in arrays:
        return out
    cnt = arrays['tile_count']
    names = [k for k in arrays if k.startswith('tile_out_band_')]
    cx0, cy0, cx1, cy1 = core_out
    for ty in range(cnt.shape[0]):
        for tx in range(cnt.shape[1]):
            x0, y0 = ox + tx * TILE, oy + ty * TILE
            if x0 >= cx0 and y0 >= cy0 and x0 + TILE <= cx1 and y0 + TILE <= cy1:
                out[(x0, y0)] = dict({'count': float(cnt[ty, tx])}, **{n: float(arrays[n][ty, tx]) for n in names})
    return out


def _seg_keys(arrays, n):
    return [k for k, v in arrays.items() if isinstance(v, np.ndarray) and v.ndim >= 1 and v.shape[0] == n
            and not k.startswith('tile_') and k not in ('prof_tc', 'prof_tcf')]


def measure(hm, source, output, P=None, grid_above_mp=GRID_ABOVE_MP, core_src=None, margin_src=MARGIN_SRC,
            want_detail=True, log=None):
    """(report, arrays, tiles) for one output against its source. arrays: halo_metric's per-segment arrays (with 'region';
    'cx', 'cy' in the whole output's px); tiles: {(x0, y0): {...}}; report: version, mode, summary, worst 25, counts."""
    src = np.asarray(source)
    O = _Out(output)
    f = _scale(src.shape, O.shape)
    H, W = O.shape[0], O.shape[1]
    whole = (not isinstance(output, dict)) and H * W / 1e6 <= grid_above_mp
    regions = ([{'id': 0, 'core': [0, 0, src.shape[1], src.shape[0]], 'read': [0, 0, src.shape[1], src.shape[0]]}] if whole
               else grid(src.shape[1], src.shape[0], f, core_src, margin_src))
    parts, tiles, hashes, n_found = [], {}, [], 0
    tc = tcf = None
    for reg in regions:
        rx0, ry0, rx1, ry1 = reg['read']
        out = O.region(rx0 * f, ry0 * f, rx1 * f, ry1 * f)
        rep, A = hm.measure(src[ry0:ry1, rx0:rx1], out, P, want_detail=want_detail, want_fidelity=False, log=log)
        hashes.append(rep['edges']['edge_set_hash'])
        n_found += rep['edges']['n_segments_found']
        tc, tcf = A['prof_tc'], A['prof_tcf']
        ox, oy = rx0 * f, ry0 * f
        c = [v * f for v in reg['core']]
        n = A['status'].shape[0]
        gx, gy = A['cx'] + ox, A['cy'] + oy
        keep = (gx >= c[0]) & (gx < c[2]) & (gy >= c[1]) & (gy < c[3])
        part = {k: A[k][keep] for k in _seg_keys(A, n)}
        part['cx'], part['cy'] = gx[keep].astype(np.float32), gy[keep].astype(np.float32)
        part['region'] = np.full(int(keep.sum()), reg['id'], np.int32)
        parts.append(part)
        tiles.update(_tiles(A, ox, oy, c))
    keys = parts[0].keys()
    arrays = {k: np.concatenate([p[k] for p in parts]) for k in keys}
    arrays['prof_tc'], arrays['prof_tcf'] = tc, tcf
    P2 = {**hm.DEFAULTS, **(P or {})}
    report = {'version': hm.VERSION, 'mode': 'whole' if whole else 'grid', 'scale': f, 'out_size': [W, H],
              'src_size': [int(src.shape[1]), int(src.shape[0])], 'n_regions': len(regions),
              'grid': None if whole else {'core_src': regions[0]['core'][2] - regions[0]['core'][0] if regions else None,
                                          'margin_src': margin_src},
              'edge_set_hash': hashlib.sha256('/'.join(hashes).encode()).hexdigest()[:16],
              'n_segments_found': n_found, 'n_segments_kept': int(arrays['status'].shape[0]),
              'summary': hm.summarize(arrays, P2), 'worst': hm.worst_list(arrays, 25)}
    return report, arrays, tiles


def pair_index(a, b):
    """Index arrays (ia, ib) pairing two measurements of one source on one grid by (region, segment), both status ok."""
    ka = {(int(r), int(s)): i for i, (r, s) in enumerate(zip(a['region'], a['seg']))}
    ia, ib = [], []
    for j, (r, s) in enumerate(zip(b['region'], b['seg'])):
        i = ka.get((int(r), int(s)))
        if i is not None and a['status'][i] == 0 and b['status'][j] == 0:
            ia.append(i)
            ib.append(j)
    return np.array(ia, int), np.array(ib, int)


def finite(x):
    return x is not None and isinstance(x, (int, float)) and math.isfinite(x)
