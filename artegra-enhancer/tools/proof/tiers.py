"""Design 7.3's pass rule for the finish phase: tier 0 (0 differing values) or tier 1 against the measured floor F. numpy.

Tier 1 passes only if all of these hold (each is reported):
  count       differing values <= F
  max_abs     every |delta| <= 1/255 (one level)
  groups      no 8-connected group of differing pixels larger than 4 px
  structure   no structure along band, strip or tile rows: the mean |delta| on each boundary row (and column) is at most
              2 x the median row's (column's) mean |delta|
  flips       no flipped component (every island, material, agree2 or sky component decided differently, with its box; any
              flip fails tier 1). The finish's component records are passed in; without them the groups rule still catches
              a flip, which is never smaller than a component.
Otherwise the result is a failure of the exactness claim (section 2.5's tier 2 or 3 applies)."""
from collections import deque

import numpy as np

from tools.proof.phases import _Arr

MAX_GROUP_PX = 4
MAX_COORDS = 5_000_000


def _entry(x):
    return x if isinstance(x, dict) else {'kind': 'array', 'array': x}


def groups_over(coords, limit=MAX_GROUP_PX):
    """8-connected groups of a set of (y, x): (largest size, number of groups larger than limit, their boxes (first 20))."""
    left = set(coords)
    largest, big, boxes = 0, 0, []
    while left:
        start = left.pop()
        q = deque([start])
        n, y0, x0, y1, x1 = 0, start[0], start[1], start[0], start[1]
        while q:
            y, x = q.popleft()
            n += 1
            y0, x0, y1, x1 = min(y0, y), min(x0, x), max(y1, y), max(x1, x)
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    p = (y + dy, x + dx)
                    if p in left:
                        left.remove(p)
                        q.append(p)
        largest = max(largest, n)
        if n > limit:
            big += 1
            if len(boxes) < 20:
                boxes.append([x0, y0, x1 + 1, y1 + 1])
    return largest, big, boxes


def tier(ref, cand, F, rows=(), cols=(), flips=None, band_rows=1024):
    """Tier of a candidate stage output (u8, H x W x 3) against its reference. ref, cand: arrays or plane entries.
    rows, cols: the boundary rows and columns of both executors (tools/proof/seams.positions). F: the floor (7.3)."""
    A, B = _Arr(_entry(ref)), _Arr(_entry(cand))
    if A.shape != B.shape:
        return {'tier': None, 'pass': False, 'reason': f'shapes differ: {A.shape} against {B.shape}'}
    H, W = A.shape[0], A.shape[1]
    row_mean = np.zeros(H, np.float64)
    col_sum = np.zeros(W, np.float64)
    count, max_abs, coords, too_many = 0, 0, [], False
    for y0 in range(0, H, band_rows):
        y1 = min(H, y0 + band_rows)
        d = np.abs(A.rows(y0, y1).astype(np.int16) - B.rows(y0, y1).astype(np.int16))
        px = d.max(-1)
        row_mean[y0:y1] = d.mean((1, 2))
        col_sum += d.mean(2).sum(0)
        n = int((d != 0).sum())
        if n:
            count += n
            max_abs = max(max_abs, int(d.max()))
            ys, xs = np.nonzero(px)
            if len(coords) + ys.size > MAX_COORDS:
                too_many = True
            elif not too_many:
                coords.extend(zip((ys + y0).tolist(), xs.tolist()))
    col_mean = col_sum / H
    checks = {'count': count, 'F': int(F), 'max_abs_levels': max_abs}
    if count == 0:
        return {'tier': 0, 'pass': True, 'checks': checks}
    fails = []
    if count > F:
        fails.append('count')
    if max_abs > 1:
        fails.append('max_abs')
    if too_many:
        fails.append('groups')
        checks['groups'] = 'too many differing pixels to group'
    else:
        largest, big, boxes = groups_over(coords)
        checks.update(largest_group_px=largest, groups_over_4=big, group_boxes=boxes)
        if big:
            fails.append('groups')
    med_r, med_c = float(np.median(row_mean)), float(np.median(col_mean))
    bad_rows = [int(r) for r in rows if 0 <= r < H and row_mean[r] > 2 * med_r]
    bad_cols = [int(c) for c in cols if 0 <= c < W and col_mean[c] > 2 * med_c]
    checks.update(median_row_mean=med_r, median_col_mean=med_c, boundary_rows_over=bad_rows[:50],
                  boundary_cols_over=bad_cols[:50])
    if bad_rows or bad_cols:
        fails.append('structure')
    flips = list(flips or [])
    checks['flips'] = flips[:50]
    if flips:
        fails.append('flips')
    return {'tier': None if fails else 1, 'pass': not fails, 'fails': fails, 'checks': checks}
