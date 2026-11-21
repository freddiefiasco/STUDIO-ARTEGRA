"""Marks read from a run's own records (engine design 9.2; wave contracts wsum and l3r_record). Standard library only.

wsum (contract wsum): ClaudeSpotTilesBanded raises if wsum.min() <= 0 at any evaluation, and prints one line per sampling
call to the worker's stdout: "[claude_banded] wsum_min=<repr float> evals=<n> windows=<m>". The mark is wsum > 0: every such
line parses and its minimum is > 0, and a run has one line per banded sampling call it made: expected_wsum_lines counts the
KSampler nodes whose model is the banded spot node (KS1 and KS2 of every banded stage, two per stage), from the graphs that
ran.

L3r split (contract l3r_record): for a split stage the service records in the item's timings stage entry (part B)
job_peak_commit_a_end_gb, job_peak_commit_b_start_gb, stopped_worker_last_commit_gb and commit_fall_gb, and logs the event
banded_split_commit with the same fields. The marks (9.2 R3, 2.8): across each split, the Job's peak commit (just before prompt
A ends and just after prompt B starts) is at most the stage's registered bound, and the stopped worker's commit is returned
(the commit fall is at least the stopped worker's last commit, less a registered tolerance). l3r_stage_check holds each
split stage's record to that stage's own registered bound (the plan marks' peak_upper_gb, the service Job's bound) and
wants exactly one record per split stage; l3r_marks reads the item's timings and the service log and checks they agree."""
import json
import math
import re

WSUM_PREFIX = '[claude_banded] wsum_min='
WSUM_RE = re.compile(r'^\[claude_banded\] wsum_min=(\S+) evals=(\d+) windows=(\d+)\s*$')
L3R_FIELDS = ('job_peak_commit_a_end_gb', 'job_peak_commit_b_start_gb', 'stopped_worker_last_commit_gb', 'commit_fall_gb')


SPOT_BANDED = 'ClaudeSpotTilesBanded'
PASS_THROUGH = ('MultiGPU_WorkUnits',)          # a model node that hands the spot model on unchanged (two cards)


def expected_wsum_lines(graphs):
    """The wsum lines the given prompts' graphs make: one per KSampler whose model is the banded spot node (directly or
    through a pass-through model node). A Large-image stage samples twice (KS1, KS2); part B of a split stage not at all."""
    n = 0
    for g in graphs or []:
        for v in g.values():
            if v.get('class_type') != 'KSampler':
                continue
            ref = (v.get('inputs') or {}).get('model')
            seen = 0
            while isinstance(ref, list) and len(ref) == 2 and seen < 8:
                node = g.get(str(ref[0])) or {}
                if node.get('class_type') == SPOT_BANDED:
                    n += 1
                    break
                if node.get('class_type') not in PASS_THROUGH:
                    break
                ref, seen = (node.get('inputs') or {}).get('model'), seen + 1
    return n


def wsum_mark(text, expect_lines=True, expect_min=None):
    """{'pass', 'lines', 'min', 'evals', 'windows', 'bad', 'reason', 'expected'} from worker-log text. expect_min: the
    lines the run must have (expected_wsum_lines of its graphs); without it, at least one when expect_lines."""
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
    out = {'lines': lines, 'min': min(mins) if mins else None, 'evals': evals, 'windows': windows, 'bad': bad,
           'expected': None if expect_min is None else int(expect_min)}
    if bad:
        return dict(out, **{'pass': False, 'reason': 'a wsum line is not > 0 or does not parse'})
    if expect_lines and not lines:
        return dict(out, **{'pass': False, 'reason': 'no wsum line although a banded spot node ran'})
    if expect_lines and expect_min is not None and lines < int(expect_min):
        return dict(out, **{'pass': False, 'reason': f'one wsum line per banded sampler: {lines} of {int(expect_min)}'})
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


def l3r_stage_check(recs, plan_marks, returned_tolerance_gb=1.0):
    """The split marks per stage: each record held to its own stage's registered bound (plan_marks' peak_upper_gb, the
    service Job's), exactly one record per split stage, and none for a stage the plan does not split. {'pass', 'records',
    'expected_stages', 'missing_stages', 'unexpected_stages', 'duplicate_stages'}."""
    stages = {int(s['index']): s for s in (plan_marks or {}).get('stages') or []}
    split = sorted(i for i, s in stages.items() if s.get('split_finish'))
    rows, ok, seen, unexpected, dup = [], True, [], [], []
    for r in recs:
        k = r.get('stage')
        k = int(k) if k is not None else None
        st = stages.get(k)
        if st is None or not st.get('split_finish'):
            unexpected.append(k)
            rows.append(dict(r, fails=['no split stage of the plan has this index'], bound_gb=None))
            ok = False
            continue
        if k in seen:
            dup.append(k)
            ok = False
        seen.append(k)
        one = l3r_check([r], st['peak_upper_gb'], returned_tolerance_gb)
        rows.append(one['records'][0])
        ok = ok and one['pass']
    missing = [k for k in split if k not in seen]
    return {'pass': bool(ok and not missing), 'records': rows, 'expected_stages': split, 'missing_stages': missing,
            'unexpected_stages': unexpected, 'duplicate_stages': dup}


def l3r_marks(item, log_text, plan_marks, returned_tolerance_gb=1.0):
    """The split marks of one service run: the item's timings (the record), cross-checked with the service log's
    banded_split_commit events (the same fields, written together; a disagreement fails). Without an item, the log."""
    from_item, from_log = l3r_from_item(item) if item else [], l3r_from_log(log_text) if log_text else []
    recs, source = (from_item, 'item.timings') if (item and (from_item or not from_log)) else (from_log, 'service log')
    out = dict(l3r_stage_check(recs, plan_marks, returned_tolerance_gb), source=source, log_agrees=None)
    if item and log_text:
        key = lambda r: (r.get('stage'), tuple(r.get(k) for k in L3R_FIELDS))
        out['log_agrees'] = sorted(map(key, from_item), key=str) == sorted(map(key, from_log), key=str)
        out['pass'] = bool(out['pass'] and out['log_agrees'])
    return out
