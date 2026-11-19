"""Util implementation."""


import datetime
import hashlib
import json
import os
import secrets
import time
from fractions import Fraction
from pathlib import Path


def now_iso():
    """Local time with offset, millisecond precision (log and record timestamps)."""
    return datetime.datetime.now().astimezone().isoformat(timespec='milliseconds')


def new_id(prefix='', hex_chars=12):
    return prefix + secrets.token_hex(hex_chars // 2)


def to_jsonable(obj):
    """Recursively convert values the engine produces (tuples, Fractions, numpy scalars, Paths) into plain JSON types."""
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, Fraction):
        return int(obj) if obj.denominator == 1 else float(obj)
    if isinstance(obj, Path):
        return str(obj)
    if hasattr(obj, 'item') and callable(obj.item) and type(obj).__module__ == 'numpy':
        return obj.item()
    return obj


def same_record(a, b):
    """a == b as JSON would store them (tuples and lists alike). Settings and plans are compared with what a job record read
    back after a restart holds (lists), so a fresh tuple must not count as a change (12 Nov, QA CONTRACT-2)."""
    return to_jsonable(a) == to_jsonable(b)


PLAN_GRAPH_KEYS = ('factor', 'input_size', 'output_size')
STAGE_GRAPH_KEYS = ('factor', 'supersample', 'input_size', 'padded_size', 'render_size', 'output_size')
BANDED_PIXEL_KEYS = ('bes', 'finish', 'canvas', 'recipe', 'halo_fix', 'mode', 'window', 'dat', 'vae', 'canny', 'encode_state',
                     'brownian_cache', 'cmap', 'hint_store')


def _plan_graph(plan):
    p = to_jsonable(plan.to_dict() if hasattr(plan, 'to_dict') else plan)
    if not isinstance(p, dict):
        return p
    # 5.0.2: the engine and the Large-image engine's pixel constants make the pixels too; a stored 5.0.1 plan has neither
    # and reads as classic, so it still matches the classic plan made now
    banded = p.get('banded')
    return {'plan': [p.get(k) for k in PLAN_GRAPH_KEYS],
            'stages': [[s.get(k) for k in STAGE_GRAPH_KEYS] if isinstance(s, dict) else s for s in p.get('stages') or []],
            'engine': p.get('engine', 'classic'),
            'banded': None if not isinstance(banded, dict) else {k: banded.get(k) for k in BANDED_PIXEL_KEYS}}


def same_plan(a, b):
    """True when two plans make the same graphs, so the same pixels: the same factor and sizes, and per stage the same
    factor, supersample and sizes. The memory estimate, the minutes and ram_limited are left out, so a plan an earlier
    version stored (5.0.0-beta.1 had no ram_limited and another estimate) still matches the plan made now, and its
    finished passes are kept."""
    return _plan_graph(a) == _plan_graph(b)


def canonical_json(obj):
    """Stable bytes for hashing (sorted keys, no whitespace)."""
    return json.dumps(to_jsonable(obj), sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf8')


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path, bufsize=8 << 20):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            b = f.read(bufsize)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def replace_with_retry(src, dst, retries=40):
    """os.replace, retried while another process (antivirus, indexer, a reader) briefly holds the destination open."""
    for i in range(retries):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if i == retries - 1:
                raise
            time.sleep(min(0.025 * (i + 1), 0.25))


def fsync_file(path):
    """Flush a file that was written by someone else (e.g. Pillow) to disk before it is renamed into place."""
    fd = os.open(str(path), os.O_RDWR | getattr(os, 'O_BINARY', 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_write_bytes(path, data):
    path = Path(path)
    tmp = path.with_name(f'{path.name}.{os.getpid()}.{secrets.token_hex(3)}.tmp')
    try:
        with open(tmp, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        replace_with_retry(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def atomic_write_json(path, obj):
    atomic_write_bytes(path, json.dumps(to_jsonable(obj), indent=1, ensure_ascii=False).encode('utf8'))


def read_json(path):
    with open(path, 'r', encoding='utf8') as f:
        return json.load(f)


def link_or_copy(src, dst):
    """Hard link when source and destination share a volume (instant, no extra space), else copy."""
    import shutil
    src, dst = Path(src), Path(dst)
    try:
        os.link(src, dst)
        return 'link'
    except OSError:
        shutil.copyfile(src, dst)
        return 'copy'
