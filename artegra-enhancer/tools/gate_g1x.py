"""Gate G1x: the banded exact finish's global statistics past 2^31 elements (engine design 2.4; CPU, sizes only).

On memory-mapped synthetic planes of 185 x 2^24 = 3,103,784,960 float32 values (about 12.4 GB; 94,720 x 32,768) in the work
folder, with a deterministic pattern whose order statistics are known in closed form:
    value(i) = ((i * A) mod 2^24) * 2^-24 for flat index i (A odd), so every k * 2^-24, k < 2^24, occurs exactly 185 times and
    the sorted array is s[R] = floor(R / 185) * 2^-24;
it checks, through the engine as the worker loads it (cu_banded_engine, by path):
  - exact streamed selection (engine/bxf/selection.py): order statistics at ranks below and above 2^31 (up to n - 1, about 3.1e9)
    equal the closed form; every counter and rank is int64; the percentiles the finish takes (98.5, 35, 75, 90, 99.9, 50, 0, 100) and the median
    equal numpy's own np.percentile / np.median on the whole mapped array (bits and type: numpy computes its own index, gamma
    and interpolation, independently of the code under test; bxf-chk-5), and numpy's virtual index equals the closed form of
    its linear method, q / 100 x (n - 1);
  - the float32-bit-pattern histograms sum to the count (int64);
  - the strided 4 M sample (the classic _quantile's flat[:: n // 4M + 1]) gathers the same global flat indices (int64);
  - label tables: label into a mapped int32 plane of the same size (32 x 32 blocks; closed-form count and sizes), bincount over
    bands (int64; total = the element count), a keep table applied by bands (closed-form count).
Run (Python with numpy and scipy; below-normal priority; no thread count set):
    python -B tools/gate_g1x.py --work <folder>      # writes <folder>/g1x.json; removes its planes at the end"""
import argparse
import ctypes
import importlib
import importlib.util
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
M = 1 << 24
Q = 185
H, W = 94720, 32768                     # H * W = Q * M = 3,103,784,960
A = 2654435761 % M | 1
BAND = 2304


def engine(name):
    pkg = 'cu_banded_engine'
    if pkg not in sys.modules:
        spec = importlib.util.spec_from_file_location(pkg, ROOT / 'engine' / '__init__.py',
                                                      submodule_search_locations=[str(ROOT / 'engine')])
        mod = importlib.util.module_from_spec(spec)
        sys.modules[pkg] = mod
        spec.loader.exec_module(mod)
    return importlib.import_module(f'{pkg}.{name}')


def value_of(i):
    i = np.asarray(i, np.int64)
    return (((i * np.int64(A)) % np.int64(M)).astype(np.float64) / M).astype(np.float32)


def sorted_at(r):
    return np.float32((int(r) // Q) / M)


def below_normal():
    """Lower this process to below-normal priority (Windows); True only when the call took effect."""
    try:
        k = ctypes.windll.kernel32
        k.GetCurrentProcess.restype = ctypes.c_void_p
        k.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        k.GetPriorityClass.argtypes = [ctypes.c_void_p]
        h = k.GetCurrentProcess()
        return bool(k.SetPriorityClass(h, 0x4000)) and k.GetPriorityClass(h) == 0x4000   # BELOW_NORMAL_PRIORITY_CLASS
    except Exception:
        return False


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', required=True)
    ap.add_argument('--keep', action='store_true')
    a = ap.parse_args(argv)
    pri = below_normal()
    work = Path(a.work)
    work.mkdir(parents=True, exist_ok=True)
    S, C = engine('bxf.selection'), engine('bxf.components')
    out = {'gate': 'G1x', 'elements': H * W, 'shape': [H, W], 'numpy': np.__version__, 'below_normal_priority': pri,
           'checks': {}}
    assert H * W == Q * M and H * W > 2 ** 31
    t0 = time.time()
    vals = np.memmap(work / 'values.raw', dtype=np.float32, mode='w+', shape=(H, W))
    for y0 in range(0, H, BAND):
        y1 = min(H, y0 + BAND)
        i = np.arange(y0 * W, y1 * W, dtype=np.int64)
        vals[y0:y1] = value_of(i).reshape(y1 - y0, W)
    vals.flush()
    out['write_s'] = round(time.time() - t0, 1)
    n = H * W
    ch = S.band_chunks(vals, BAND)

    # order statistics past 2^31 (n = 3.1e9 < 2^32)
    ranks = [0, 1, Q - 1, Q, 2 ** 31 - 1, 2 ** 31, 2 ** 31 + 1, 3 * 10 ** 9, 3 * 10 ** 9 + 12345, n - Q - 1, n - 2, n - 1]
    t0 = time.time()
    got, cnt, nans = S.order_statistics(ch, ranks)
    out['select_s'] = round(time.time() - t0, 1)
    bad = [r for r in ranks if got[r].tobytes() != sorted_at(r).tobytes()]
    out['checks']['order_statistics'] = {'ranks': ranks, 'count': cnt, 'count_is_n': cnt == n, 'nans': nans, 'wrong': bad,
                                         'pass': cnt == n and not bad and nans == 0}

    # percentiles and the median against numpy itself: np.percentile / np.median of the whole mapped array (each partitions a
    # private copy, about 12.4 GB), so the index, gamma and lerp are numpy's own, not the code under test's (bxf-chk-5)
    pct = {}
    qs = (98.5, 35, 75, 90, 99.9, 50, 0, 100)
    got_p = S.percentiles(ch, qs, n=n)
    t1 = time.time()
    flat = np.asarray(vals).reshape(-1)
    want_p = [np.percentile(flat, q) for q in qs]
    out['numpy_percentile_s'] = round(time.time() - t1, 1)
    for q, g, want in zip(qs, got_p, want_p):
        vi = float(q) / 100.0 * (n - 1)                                  # numpy's linear method, in closed form
        r0 = int(np.floor(vi))
        pct[str(q)] = {'virtual_index': vi, 'ranks': [r0, min(r0 + 1, n - 1)], 'gamma': vi - r0, 'want': float(want),
                       'got': float(g), 'type': type(g).__name__, 'want_type': type(want).__name__,
                       'closed_form_lerp': float(sorted_at(r0) + (sorted_at(min(r0 + 1, n - 1)) - sorted_at(r0)) * (vi - r0)),
                       'pass': np.asarray(want).tobytes() == np.asarray(g).tobytes() and type(g) is type(want)}
    t1 = time.time()
    want_m = np.median(flat)
    out['numpy_median_s'] = round(time.time() - t1, 1)
    del flat
    got_m = S.median(ch, n=n)
    pct['median'] = {'ranks': [n // 2 - 1, n // 2], 'want': float(want_m), 'got': float(got_m), 'type': type(got_m).__name__,
                     'want_type': type(want_m).__name__,
                     'pass': np.asarray(want_m).tobytes() == np.asarray(got_m).tobytes() and type(got_m) is type(want_m)}
    out['checks']['percentiles'] = pct

    # the bit-pattern histogram sums to the count, int64
    hist = np.zeros(S.HI_BINS, np.int64)
    for v in ch():
        c = np.bincount((S.keys(v) >> np.uint32(16)).astype(np.intp), minlength=S.HI_BINS)
        hist += c
    out['checks']['histogram'] = {'dtype': str(hist.dtype), 'sum': int(hist.sum()), 'max_bin': int(hist.max()),
                                  'pass': hist.dtype == np.int64 and int(hist.sum()) == n}

    # the strided 4 M sample: the same global flat indices
    t0 = time.time()
    smp = S.strided_sample(vals)
    step = n // 4_000_000 + 1
    idx = np.arange(0, n, step, dtype=np.int64)
    ok = smp.size == idx.size and smp.tobytes() == value_of(idx).tobytes()
    out['checks']['strided_sample'] = {'step': step, 'count': int(smp.size), 'last_index': int(idx[-1]),
                                       'last_index_over_2_31': int(idx[-1]) > 2 ** 31, 'pass': bool(ok),
                                       'secs': round(time.time() - t0, 1)}
    del smp, idx

    # label tables past 2^31 elements
    t0 = time.time()
    mask = np.memmap(work / 'mask.raw', dtype=bool, mode='w+', shape=(H, W))
    yy = (np.arange(BAND)[:, None] % 64) < 32
    xx = (np.arange(W)[None, :] % 64) < 32
    for y0 in range(0, H, BAND):
        y1 = min(H, y0 + BAND)
        mask[y0:y1] = (((np.arange(y0, y1)[:, None] % 64) < 32) & xx)
    mask.flush()
    lab = np.memmap(work / 'labels.raw', dtype=np.int32, mode='w+', shape=(H, W))
    nl = C.label_into(mask, lab)
    out['label_s'] = round(time.time() - t0, 1)
    want_n = (H // 64) * (W // 64)
    counts = C.bincount_bands(lab, nl, rows=BAND)
    want_bg = n - want_n * 1024
    lab_ok = (nl == want_n and counts.dtype == np.int64 and int(counts.sum()) == n and int(counts[0]) == want_bg
              and bool(np.all(counts[1:] == 1024)))
    table = (np.arange(nl + 1) % 2 == 1)
    table[0] = False
    kept = 0
    for y0 in range(0, H, BAND):
        kept += int(np.count_nonzero(table[np.asarray(lab[y0:y0 + BAND])]))
    want_kept = ((want_n + 1) // 2) * 1024
    out['checks']['labels'] = {'count': nl, 'want_count': want_n, 'counts_dtype': str(counts.dtype),
                               'counts_sum': int(counts.sum()), 'background': int(counts[0]), 'kept_px': kept,
                               'want_kept_px': want_kept, 'pass': bool(lab_ok and kept == want_kept)}
    del yy
    out['pass'] = all(v['pass'] for k, v in out['checks'].items() if k != 'percentiles') and \
        all(v['pass'] for v in out['checks']['percentiles'].values())
    out['secs'] = round(time.time() - t0, 1)
    del vals, mask, lab, ch
    import gc
    gc.collect()
    (work / 'g1x.json').write_text(json.dumps(out, indent=1) + '\n', encoding='utf8')
    if not a.keep:
        for f in ('values.raw', 'mask.raw', 'labels.raw'):
            try:
                (work / f).unlink()
            except OSError:
                pass
    print(json.dumps({'pass': out['pass'], **{k: v.get('pass') if isinstance(v, dict) and 'pass' in v else
                                              {kk: vv['pass'] for kk, vv in v.items()} for k, v in out['checks'].items()}}))
    return out


if __name__ == '__main__':
    main()
