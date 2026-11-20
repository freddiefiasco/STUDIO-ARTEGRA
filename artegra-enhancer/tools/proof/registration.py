"""Registration of a proof run's marks (engine design 9.2): every mark is written, with its sha256, before its result exists,
and a mark moved after registration is detected. Standard library and the build's planner only.

A registration is a JSON document {'id', 'registered_at', 'build', 'marks': [{'name', 'value', 'rule'}], 'marks_sha256':
{name: sha256 of the mark}, 'sha256': the sha256 of everything else}. The file is written once (never overwritten: a re-run is
a new registration under a new id); its own sha256 is what the run record and the progress notes quote.

Marks the proof registers (9.2), each built here from the build itself:
- build: the git head and a content hash of the shipped trees and of tools/proof;
- plan: the plan dict's sha256 (Plan.to_dict(), with the variant constants finish, canvas, recipe and halo_fix), and per
  stage the predicted peaks (expected and upper, from the built planner: banded_plan.banded_peak_gb once it exists, else
  banded_plan.stage_peaks; the source is recorded), the VRAM bound (banded_vram_gb), the shared-memory bound, the time band
  and the deadline (the card_factor contract: (3 x minutes x cf + 10) x 60 s, cf = max(1, card factor));
- graph_sha256 per pass (tools/proof/harness.graph_sha, the identity record's hashing);
- pixels: the expectation and its reference;
- for the blind comparison: the whole case table, seeds, metrics, floors rule and pass rule (tools/proof/metrics)."""
import datetime
import hashlib
import json
import subprocess
from pathlib import Path

from engine import banded_plan

SHIPPED = ('engine', 'node_pack', 'service', 'host', 'ui', 'runtime', 'cu_service.py', 'support_bundle.py')
PROOF = ('tools/proof',)
SKIP_PARTS = ('__pycache__', '.local', '.pytest_cache')
SHARED_BOUND_GB = 0.5          # 9.2 R1: shared GPU memory <= 0.5 GiB per process
TIME_BAND = 0.30               # 9.2 R2: time within +-30 % of the planned minutes (registered per row)


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf8')


def sha(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


def file_sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def tree_sha256(root, parts=SHIPPED):
    """A content hash of files under root/<part> (relative path and sha256 of each, sorted; caches skipped)."""
    root = Path(root)
    rows = []
    for part in parts:
        p = root / part
        files = [p] if p.is_file() else sorted(x for x in p.rglob('*') if x.is_file()) if p.is_dir() else []
        for f in files:
            rel = f.relative_to(root).as_posix()
            if any(s in rel.split('/') for s in SKIP_PARTS) or f.suffix == '.pyc':
                continue
            rows.append([rel, file_sha(f)])
    return {'sha256': sha(rows), 'files': len(rows)}


def git_head(root):
    try:
        return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def build_record(root):
    """The build a run uses: its git head (None for an exported tree), its channel, the shipped trees' and the proof tools'
    content hashes."""
    root = Path(root)
    text = (root / 'service' / 'build_channel.py').read_text(encoding='utf8') if (root / 'service' / 'build_channel.py').is_file() else ''
    channel = 'dev' if "CHANNEL = 'dev'" in text else 'release' if "CHANNEL = 'release'" in text else None
    return {'git_head': git_head(root), 'channel': channel, 'tree': tree_sha256(root, SHIPPED),
            'proof_tools': tree_sha256(root, PROOF)}


def stage_peaks(st, mclass, split):
    """(expected GiB, upper GiB, binding phase, source) from the built planner."""
    f = getattr(banded_plan, 'banded_peak_gb', None)
    if f is not None:
        r = f(st, mclass, split)
        return float(r['expected']), float(r['upper']), r.get('phase'), 'banded_plan.banded_peak_gb'
    pk = banded_plan.stage_peaks(st, mclass, split)
    return float(pk['exp'][0]), float(pk['up'][0]), pk['up'][1], 'banded_plan.stage_peaks'


def plan_marks(plan, cap, card_factor=1.0, shared_bound_gb=SHARED_BOUND_GB, time_band=TIME_BAND):
    """The plan's registered marks: the plan dict's sha256 and variant constants, and per stage the peaks, bounds, time band
    and deadline. plan: a Large-image Plan (banded_plan.plan_banded or plan_forced) or a classic one (no peaks then)."""
    d = plan.to_dict()
    cf = max(1.0, float(card_factor))
    c = plan.banded or {}
    mclass = c.get('machine_class') or banded_plan.machine_class(cap)
    stages = []
    for st in plan.stages:
        row = {'index': st.index, 'factor': st.factor, 'supersample': st.supersample, 'render_size': list(st.render_size),
               'output_size': list(st.output_size), 'minutes': st.minutes,
               'time_band_min': [round(st.minutes * (1 - time_band), 1), round(st.minutes * (1 + time_band), 1)],
               'deadline_s': round((3 * st.minutes * cf + 10) * 60)}
        if plan.engine == 'banded':
            split = bool(getattr(st, 'split_finish', False))
            exp, up, phase, source = stage_peaks(st, mclass, split)
            row.update(split_finish=split, peak_expected_gb=round(exp, 2), peak_upper_gb=round(up, 2), binding_phase=phase,
                       peak_source=source, vram_bound_gb=round(banded_plan.banded_vram_gb(st), 2),
                       shared_bound_gb=float(shared_bound_gb))
        stages.append(row)
    return {'engine': plan.engine, 'plan_dict_sha256': sha(d), 'constants': {k: c.get(k) for k in ('finish', 'canvas',
                                                                                                    'recipe', 'halo_fix')},
            'machine_class': mclass, 'cap_gb': float(cap), 'card_factor': cf, 'admit_gb': plan.peak_ram_gb,
            'stages': stages}


def mark(name, value, rule):
    return {'name': str(name), 'value': value, 'rule': str(rule)}


def registration(reg_id, build, marks, extra=None):
    names = [m['name'] for m in marks]
    if len(set(names)) != len(names):
        raise ValueError(f'mark names must be unique: {names}')
    return {'id': str(reg_id), 'build': build, 'marks': list(marks), **(extra or {})}


def _body(doc):
    return {k: v for k, v in doc.items() if k not in ('sha256', 'marks_sha256')}


def seal(doc, registered_at=None):
    """The document with registered_at, each mark's sha256 and the document's sha256."""
    d = dict(doc)
    d['registered_at'] = registered_at or d.get('registered_at') or \
        datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
    d['marks_sha256'] = {m['name']: sha(m) for m in d['marks']}
    d['sha256'] = sha(_body(d))
    return d


def write_registration(path, doc, registered_at=None):
    """Seal and write once. Refuses an existing file (FileExistsError). Returns the sha256 of the file written."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(seal(doc, registered_at), indent=1, sort_keys=True, ensure_ascii=False).encode('utf8')
    with open(p, 'xb') as f:
        f.write(data)
    return hashlib.sha256(data).hexdigest()


def verify(doc_or_path):
    """Problems with a sealed registration (empty when every mark and the document still match their sealed hashes)."""
    d = json.loads(Path(doc_or_path).read_text(encoding='utf8')) if not isinstance(doc_or_path, dict) else doc_or_path
    out = []
    sealed = d.get('marks_sha256') or {}
    names = [m['name'] for m in d.get('marks', [])]
    for m in d.get('marks', []):
        if sealed.get(m['name']) != sha(m):
            out.append(f"moved: {m['name']}")
    for n in set(sealed) - set(names):
        out.append(f'removed: {n}')
    if d.get('sha256') != sha(_body(d)):
        out.append('the document does not match its sealed sha256')
    return out


def moved_marks(registered, current):
    """Names of the registered marks whose sealed hash differs in `current` (or that `current` lacks)."""
    a, b = registered.get('marks_sha256') or {}, current.get('marks_sha256') or {}
    return sorted(n for n in a if b.get(n) != a[n])


def registered_before(doc, result_time):
    """True when the registration's time is strictly before a result's ISO time (both timezone-aware)."""
    t0 = datetime.datetime.fromisoformat(doc['registered_at'])
    t1 = datetime.datetime.fromisoformat(result_time)
    return t0 < t1
