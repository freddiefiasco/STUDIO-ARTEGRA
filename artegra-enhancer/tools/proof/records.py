"""Marks read from a run's own records (engine design 9.2; wave contracts wsum and l3r_record). Standard library only.

wsum (contract wsum): ClaudeSpotTilesBanded raises if wsum.min() <= 0 at any evaluation, and prints one line per sampling
call to the worker's stdout: "[claude_banded] wsum_min=<repr float> evals=<n> windows=<m>". The mark is wsum > 0: every such
line parses and its minimum is > 0, and a run whose graph has the banded spot node has at least one line.

L3r split (contract l3r_record): for a split stage the service records in the item's timings stage entry (part B)
job_peak_commit_a_end_gb, job_peak_commit_b_start_gb, stopped_worker_last_commit_gb and commit_fall_gb, and logs the event
banded_split_commit with the same fields. The marks (9.2 R3, 2.8): across each split, the Job's peak commit (just before prompt
A ends and just after prompt B starts) is at most the stage's registered bound, and the stopped worker's commit is returned
(the commit fall is at least the stopped worker's last commit, less a registered tolerance)."""
import json
import math
import re

WSUM_PREFIX = '[claude_banded] wsum_min='
WSUM_RE = re.compile(r'^\[claude_banded\] wsum_min=(\S+) evals=(\d+) windows=(\d+)\s*$')
L3R_FIELDS = ('job_peak_commit_a_end_gb', 'job_peak_commit_b_start_gb', 'stopped_worker_last_commit_gb', 'commit_fall_gb')


def wsum_mark(text, expect_lines=True):
    """{'pass', 'lines', 'min', 'evals', 'windows', 'bad', 'reason'} from worker-log text."""
    lines, bad, mins, evals, windows = 0, [], [], 0, 0
    for raw in str(text).splitlines():
        line = raw.strip()
        if not line.startswith(WSUM_PREFIX):
            continue
        m = WSUM_RE.match(line)
        if not m:
            bad.append(line[:200])
            continue
        try:
            v = float(m.group(1))
        except ValueError:
            bad.append(line[:200])
            continue
        lines += 1
        evals += int(m.group(2))
        windows = max(windows, int(m.group(3)))
        mins.append(v)
        if not (math.isfinite(v) and v > 0):
            bad.append(line[:200])
    out = {'lines': lines, 'min': min(mins) if mins else None, 'evals': evals, 'windows': windows, 'bad': bad}
    if bad:
        return dict(out, **{'pass': False, 'reason': 'a wsum line is not > 0 or does not parse'})
    if expect_lines and not lines:
        return dict(out, **{'pass': False, 'reason': 'no wsum line although a banded spot node ran'})
    return dict(out, **{'pass': True, 'reason': ''})


def l3r_from_item(item):
    """The split records of one item (its timings' stage entries that carry the l3r fields)."""
    out = []
    for e in ((item or {}).get('timings') or {}).get('stages') or []:
        if any(k in e for k in L3R_FIELDS):
            out.append(dict({k: e.get(k) for k in L3R_FIELDS}, stage=e.get('stage', e.get('index')), part=e.get('part'),
                            source='item.timings'))
    return out


def l3r_from_log(text):
    """The banded_split_commit events of a service log (JSON lines; other lines ignored)."""
    out = []
    for line in str(text).splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict) and rec.get('event') == 'banded_split_commit':
            d = rec.get('data') or {}
            out.append(dict({k: d.get(k) for k in L3R_FIELDS}, stage=rec.get('stage'), job=rec.get('job'),
                            item=rec.get('item'), ts=rec.get('ts'), source='service log'))
    return out


def l3r_check(recs, bound_gb, returned_tolerance_gb=1.0, expect=None):
    """The split marks per record. expect: the number of split stages the plan has (a missing record fails)."""
    rows, ok = [], True
    for r in recs:
        fails = []
        vals = [r.get(k) for k in L3R_FIELDS]
        if any(v is None for v in vals):
            fails.append('a field is missing')
        else:
            a, b, last, fall = (float(v) for v in vals)
            if max(a, b) > float(bound_gb):
                fails.append('peak over the bound')
            if fall < last - float(returned_tolerance_gb):
                fails.append('stopped worker commit not returned')
        ok = ok and not fails
        rows.append(dict(r, fails=fails, bound_gb=float(bound_gb)))
    if expect is not None and len(recs) != int(expect):
        ok = False
    return {'pass': bool(ok and (recs or expect == 0)), 'records': rows, 'expected': expect, 'found': len(recs)}
