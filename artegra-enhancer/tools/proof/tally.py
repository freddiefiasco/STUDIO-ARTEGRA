"""The blind verdict files and BLIND-TALLY.json (engine design 7.4), with their validators. Standard library only.

A judge's verdict file (written first, blind; its sha256 recorded before any named material is opened):
  {"format": "cu-blind-verdicts-1", "judge": "guardian" | "technical_qa", "written_at": ISO time,
   "pairs_manifest_sha256": the PAIRS.json the judge was given,
   "verdicts": {"<case>/<crop>": {"halos": "X" | "same" | "Y", "micro_detail": ..., "edge_sharpness": ..., "fidelity": ...,
                                  "colour_tone": ...,
                                  "artefacts": [{"in": "X" | "Y", "kind": one of ARTEFACTS, "x": px, "y": px, "note": text}]}}}
  Every pair of the manifest has a verdict with every criterion.

BLIND-TALLY.json (the proof check fills it after opening the key, which it may only do once both verdict files exist):
  {"format": "cu-blind-tally-1", "key_sha256", "manifest_sha256", "opened_key_at",
   "verdict_files": {judge: {"sha256", "written_at"}}, "criteria": CRITERIA, "rule": RULE,
   "cases": {case: {"pairs", "controls", "by_criterion": {criterion: {judge: {"bes_better", "same", "classic_better"}}},
                    "verdict": {judge: {"result": "same_or_better" | "worse", "worse_on": [criteria]}},
                    "artefacts": [{"pair", "judge", "engine", "kind", "x", "y", "note"}],
                    "controls_called_different": [{"pair", "judge", "criteria"}]}},
   "result": {"all_cases_same_or_better": bool, "worse_cases": [case]}}
RULE (registered with the case table; the proof may register a stricter one, never a looser one without saying so): for each
case, judge and criterion, the Large-image engine is the same or better when no non-control pair of the case is judged
classic-better on that criterion; the blind controls (byte-identical pairs) are tallied apart and show the floor of judging."""
import datetime

CRITERIA = ('halos', 'micro_detail', 'edge_sharpness', 'fidelity', 'colour_tone')
CALLS = ('X', 'same', 'Y')
ARTEFACTS = ('seam', 'banding', 'ringing', 'rim', 'glow_band', 'softening', 'invented_content', 'other')
JUDGES = ('guardian', 'technical_qa')
VERDICT_FORMAT, TALLY_FORMAT = 'cu-blind-verdicts-1', 'cu-blind-tally-1'
RULE = ('per case, judge and criterion: same_or_better when no non-control pair of the case is judged classic-better on that '
        'criterion; byte-identical pairs are blind controls, tallied apart')


def _time(s):
    t = datetime.datetime.fromisoformat(str(s))
    if t.tzinfo is None:
        raise ValueError('a time must carry its zone')
    return t


def validate_verdicts(doc, manifest_rows, crop=512):
    """Problems with one judge's verdict file against the pairs manifest (empty when valid)."""
    err = []
    if doc.get('format') != VERDICT_FORMAT:
        err.append('format is not cu-blind-verdicts-1')
    if doc.get('judge') not in JUDGES:
        err.append(f"judge must be one of {JUDGES}")
    try:
        _time(doc.get('written_at'))
    except (TypeError, ValueError):
        err.append('written_at must be an ISO time with its zone')
    v = doc.get('verdicts')
    if not isinstance(v, dict):
        return err + ['verdicts must be an object']
    pairs = {r['pair']: r for r in manifest_rows}
    for p in sorted(set(pairs) - set(v)):
        err.append(f'{p}: no verdict')
    for p in sorted(set(v) - set(pairs)):
        err.append(f'{p}: not a pair of the manifest')
    for p, e in v.items():
        if not isinstance(e, dict):
            err.append(f'{p}: a verdict must be an object')
            continue
        for c in CRITERIA:
            if e.get(c) not in CALLS:
                err.append(f'{p}: {c} must be X, same or Y')
        for k in set(e) - set(CRITERIA) - {'artefacts', 'note'}:
            err.append(f'{p}: unknown field {k}')
        for a in e.get('artefacts') or []:
            size = crop if (pairs.get(p) or {}).get('kind') != 'proxy' else 4096
            if a.get('in') not in ('X', 'Y') or a.get('kind') not in ARTEFACTS:
                err.append(f'{p}: an artefact needs in X or Y and a kind of {ARTEFACTS}')
            if not all(isinstance(a.get(q), int) and 0 <= a[q] < size for q in ('x', 'y')):
                err.append(f'{p}: an artefact needs whole x and y inside the crop')
    return err


def tally(verdicts, key, manifest_rows, verdict_sha256, key_sha256, opened_key_at, manifest_sha256=None):
    """BLIND-TALLY.json from both judges' verdicts and the opened key. Raises if a judge is missing, a verdict file is
    invalid, or the key was opened before both verdict files were written."""
    missing = [j for j in JUDGES if j not in verdicts]
    if missing:
        raise ValueError(f'the key is opened only after both verdict files exist (missing {missing})')
    opened = _time(opened_key_at)
    for j, doc in verdicts.items():
        e = validate_verdicts(doc, manifest_rows)
        if e:
            raise ValueError(f'{j}: ' + '; '.join(e[:5]))
        if _time(doc['written_at']) >= opened:
            raise ValueError(f'{j}: the verdicts were written after the key was opened')
    kp = key['pairs']
    cases = {}
    for r in manifest_rows:
        pid, case = r['pair'], r['case']
        k = kp[pid]
        c = cases.setdefault(case, {'pairs': 0, 'controls': 0, 'by_criterion': {cr: {j: {'bes_better': 0, 'same': 0,
                                                                                        'classic_better': 0}
                                                                                    for j in JUDGES} for cr in CRITERIA},
                                    'artefacts': [], 'controls_called_different': []})
        if k['identical']:
            c['controls'] += 1
        else:
            c['pairs'] += 1
        for j in JUDGES:
            e = verdicts[j]['verdicts'][pid]
            if k['identical']:
                diff = [cr for cr in CRITERIA if e[cr] != 'same']
                if diff:
                    c['controls_called_different'].append({'pair': pid, 'judge': j, 'criteria': diff})
            else:
                for cr in CRITERIA:
                    call = e[cr]
                    eng = 'same' if call == 'same' else k[call]
                    c['by_criterion'][cr][j][{'same': 'same', 'bes': 'bes_better', 'classic': 'classic_better'}[eng]] += 1
            for a in e.get('artefacts') or []:
                c['artefacts'].append({'pair': pid, 'judge': j, 'engine': k[a['in']], 'kind': a['kind'], 'x': a['x'],
                                       'y': a['y'], 'note': a.get('note', '')})
    worse_cases = []
    for case, c in cases.items():
        c['verdict'] = {}
        for j in JUDGES:
            worse_on = [cr for cr in CRITERIA if c['by_criterion'][cr][j]['classic_better'] > 0]
            c['verdict'][j] = {'result': 'worse' if worse_on else 'same_or_better', 'worse_on': worse_on}
        if any(v['result'] == 'worse' for v in c['verdict'].values()):
            worse_cases.append(case)
    return {'format': TALLY_FORMAT, 'key_sha256': key_sha256, 'manifest_sha256': manifest_sha256 or key.get('manifest_sha256'),
            'opened_key_at': opened.isoformat(), 'criteria': list(CRITERIA), 'rule': RULE,
            'verdict_files': {j: {'sha256': verdict_sha256[j], 'written_at': verdicts[j]['written_at']} for j in JUDGES},
            'cases': cases, 'result': {'all_cases_same_or_better': not worse_cases, 'worse_cases': sorted(worse_cases)}}


def validate_tally(doc):
    """Problems with a BLIND-TALLY.json (empty when valid)."""
    err = []
    if doc.get('format') != TALLY_FORMAT:
        err.append('format is not cu-blind-tally-1')
    for k in ('key_sha256', 'opened_key_at', 'verdict_files', 'cases', 'result', 'criteria', 'rule'):
        if k not in doc:
            err.append(f'missing {k}')
    if err:
        return err
    if list(doc['criteria']) != list(CRITERIA):
        err.append('criteria differ from the registered ones')
    if sorted(doc['verdict_files']) != sorted(JUDGES):
        err.append('both judges\' verdict files are required')
    try:
        opened = _time(doc['opened_key_at'])
        for j, v in doc['verdict_files'].items():
            if len(str(v.get('sha256', ''))) != 64:
                err.append(f'{j}: verdict sha256 missing')
            if _time(v['written_at']) >= opened:
                err.append(f'{j}: verdicts written after the key was opened')
    except (TypeError, ValueError, KeyError):
        err.append('times must be ISO with their zone')
    worse = []
    for case, c in doc['cases'].items():
        for cr in CRITERIA:
            for j in JUDGES:
                n = (c.get('by_criterion', {}).get(cr, {}).get(j) or {})
                if sorted(n) != ['bes_better', 'classic_better', 'same'] or any(not isinstance(v, int) or v < 0
                                                                                  for v in n.values()):
                    err.append(f'{case}: {cr}/{j} counts are incomplete')
                elif sum(n.values()) != c.get('pairs'):
                    err.append(f'{case}: {cr}/{j} counts do not add up to the pairs')
        for j in JUDGES:
            v = (c.get('verdict') or {}).get(j) or {}
            want = 'worse' if any(c['by_criterion'][cr][j].get('classic_better', 0) for cr in CRITERIA
                                  if isinstance(c.get('by_criterion', {}).get(cr, {}).get(j), dict)) else 'same_or_better'
            if v.get('result') != want:
                err.append(f'{case}: {j} verdict does not follow the rule')
            if v.get('result') == 'worse':
                worse.append(case)
    if doc['result'].get('all_cases_same_or_better') != (not worse):
        err.append('result does not follow the cases')
    return err
