"""docs/STRINGS.md lists every user-facing string of the Large-image engine (B15): the ones already in the base
(service/banded_runner.py, the runner's developer-build lines, service/build_channel.py, engine/banded_plan.py's refusals,
service/plane_io.py) and the ones the engine naming adds (service/media.py, host/installation.py, the QML). Both ways: every
string in those places is listed, and every listed string is in the code. Placeholders (<N>, {k}) compare as one.

5.0.2 build wave 2 (strings reconciliation, merge report item 9; views-docs V3) scans more places, each by its own rule:
- the runner's graphics-memory admission (Classic and Large-image), its card timing and physical-memory lines (RUNNER_PHRASES);
- service/media.py's and service/plane_views.py's Large-image lines (V3: no 5.0.1 string of those files is pulled in);
- service/card_factor.py, whole;
- the Large-image engine's own nodes (node_pack/claude_banded's plane modules and the banded finish) and the finish's G1
  table: every message they raise (most start lower-case, so the copy-like rule alone would check nothing there; the
  engine shows them in its log, and the person sees the runner's plain sentence), and the banded finish's reasons."""
import ast
import re
from pathlib import Path

from host import installation
from service import media

ROOT = Path(__file__).resolve().parents[1]
STRINGS = ROOT / 'docs' / 'STRINGS.md'
SOURCES = ('service/banded_runner.py', 'engine/banded_plan.py', 'service/build_channel.py', 'service/plane_io.py',
           'service/card_factor.py')
RUNNER_PHRASES = ('Large-image', 'developer setting', 'graphics memory with the', 'smaller image', 'per window',
                  'graphics card measurement', 'timed before its first image', 'its speed before', 'system memory (RAM)')
# (5.0.1's own runner lines that name the graphics card, such as 'This image is still releasing its graphics card', are not
# 5.0.2 strings and stay out of this section)
LARGE_ONLY = ('service/media.py', 'service/plane_views.py')                 # their lines that name the Large-image engine
NODE_SOURCES = ('node_pack/claude_banded/canny_plane.py', 'node_pack/claude_banded/cn_plane.py',
                'node_pack/claude_banded/noise_banded.py', 'node_pack/claude_banded/vae_planes.py',
                'node_pack/claude_banded/sam_plane.py', 'node_pack/claude_banded/spot_banded.py',
                'node_pack/claude_banded/bxf/__init__.py')
FINISH_REASONS = (('node_pack/claude_banded/bxf/__init__.py', 'banded finish'), ('engine/bxf/g1.py', 'G1 table'))
NOT_COPY = {'Artegra Enhancer', 'Creative Upscaler <>'}           # the TIFF software tag
PLACEHOLDER = re.compile(r'<[^<>]*>|\{[^{}]*\}')


def norm(s):
    return PLACEHOLDER.sub('<>', s)


def literals(path, keep=lambda s: True):
    """Every str constant and f-string of a module except docstrings, normalised, in source order."""
    tree = ast.parse((ROOT / path).read_text(encoding='utf-8'))
    docs, inner = set(), set()
    for node in ast.walk(tree):
        body = getattr(node, 'body', None)
        if isinstance(body, list) and body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            docs.add(id(body[0].value))
        if isinstance(node, ast.JoinedStr):
            inner.update(id(v) for v in node.values)
    out = []
    for n in ast.walk(tree):
        if id(n) in docs or id(n) in inner:
            continue
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            s = norm(n.value)
        elif isinstance(n, ast.JoinedStr):
            s = ''.join(norm(v.value) if isinstance(v, ast.Constant) else '<>' for v in n.values)
        else:
            continue
        out.append((n.lineno, n.col_offset, s))
    return [s for _, _, s in sorted(out) if keep(s)]


def copy_like(s):
    s = s.strip()
    return ' ' in s and (s[:1].isupper() or s.startswith('<>')) and s not in NOT_COPY


def _lit(n):
    """A message expression as one normalised string: a str constant, an f-string, or literals joined by +; else None."""
    if isinstance(n, ast.Constant) and isinstance(n.value, str):
        return norm(n.value)
    if isinstance(n, ast.JoinedStr):
        return ''.join(norm(v.value) if isinstance(v, ast.Constant) else '<>' for v in n.values)
    if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Add):
        a, b = _lit(n.left), _lit(n.right)
        return None if a is None and b is None else (a or '<>') + (b or '<>')
    if isinstance(n, ast.Call):            # ', '.join(...) and the like inside a message
        return '<>'
    return None


def raised(path):
    """Every literal message a module raises (the first argument of the exception it raises), in source order."""
    tree = ast.parse((ROOT / path).read_text(encoding='utf-8'))
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call) and node.exc.args:
            m = _lit(node.exc.args[0])
            if m is not None and m.strip('<> '):
                out.append((node.lineno, m))
    return [m for _, m in sorted(out)]


def reasons(path, phrase):
    """The reason texts a module builds (assigned or returned) that carry `phrase`."""
    tree = ast.parse((ROOT / path).read_text(encoding='utf-8'))
    out = []
    for node in ast.walk(tree):
        value = node.value if isinstance(node, (ast.Assign, ast.Return)) else None
        m = _lit(value) if value is not None else None
        if m is not None and phrase in m:
            out.append((node.lineno, m))
    return [m for _, m in sorted(out)]


def listed():
    text = STRINGS.read_text(encoding='utf-8')
    section = text[text.index('## Engines (5.0.2)'):]
    out = []
    for line in section.splitlines():
        if line.startswith('- '):
            out.append(norm(line[2:].split(' \u2014 ')[0].strip()))
    return out


def source_strings():
    found = []
    for path in SOURCES:
        found += [s for s in literals(path) if copy_like(s)]
    found += [s for s in literals('service/runner.py') if copy_like(s) and any(p in s for p in RUNNER_PHRASES)]
    for path in LARGE_ONLY:
        found += [s for s in literals(path) if copy_like(s) and 'Large-image' in s]
    for path in NODE_SOURCES:
        found += raised(path)
    for path, phrase in FINISH_REASONS:
        found += reasons(path, phrase)
    found += [norm(getattr(media, k)) for k in ('ENGINE_CLASSIC', 'ENGINE_LARGE', 'ENGINE_LARGE_FORCED', 'ENGINE_HALO_NOTE',
                                                'DISK_NEED', 'MEMORY_CLASS')]
    found.append(norm(installation.MEMORY_48))
    return found


def haystack():
    """Every literal of the places above (and the QML), joined in source order within a file: a listed string may be
    built from several literals (a message with an optional part)."""
    parts = []
    for path in SOURCES + ('service/runner.py', 'service/media.py', 'host/installation.py', 'service/plane_views.py'):
        parts.append(''.join(literals(path)))
    for path in NODE_SOURCES + tuple(p for p, _ in FINISH_REASONS):
        parts.append(''.join(literals(path)))
        parts.append('\n'.join(raised(path)))
    for p in sorted((ROOT / 'ui' / 'qml').rglob('*.qml')) + sorted((ROOT / 'ui' / 'qml').rglob('*.js')):
        from tests.test_mode_names import js_literals
        parts.append(''.join(norm(lit[1:-1]) for kind, lit in js_literals(p.read_text(encoding='utf-8')) if kind == 'string'))
    return '\n'.join(parts)


def test_every_large_image_string_in_the_code_is_listed():
    entries = listed()
    missing = [s for s in source_strings() if not any(s.strip() in e for e in entries)]
    assert missing == []


def test_the_new_places_are_scanned_and_find_what_they_must():
    """The wider scan is not vacuous: each new place yields strings, among them the ones the reconciliation names."""
    found = source_strings()
    for path in NODE_SOURCES:
        assert raised(path), path
    for want in ('the canvas (<> x <> px) fits one <> px window; the Large-image engine does not run such canvases (the '
                 'Classic engine does)',                                            # gpu-nodes' worker strings
                 'the Brownian cache cap could not be installed: another noise sampler patch is active',   # its check G2
                 'the banded finish cannot run here (<>); the whole finish runs only up to <> MP',           # bxf
                 'the G1 table was measured on another environment (<>)',
                 'the banded finish makes the 8-bit product finish only',
                 'This image needs about <> GB of graphics memory with the <> engine; <> <> GB.',            # admission
                 '<>: <> s per window',
                 'The viewer copy of a Large-image result could not be made: <>'):                         # media.py (V3)
        assert want in found, want


def test_every_listed_string_is_in_the_code():
    hay = haystack()
    absent = []
    for e in listed():
        pattern = '.*?'.join(re.escape(chunk) for chunk in e.split('<>'))
        if not re.search(pattern, hay):
            absent.append(e)
    assert absent == []


def test_the_base_refusals_are_all_there():
    """The refusals engine/banded_plan.py returns, one by one (the list the planner's own tests know)."""
    entries = listed()
    for s in ('The Large-image engine needs a computer with at least 48 GB of memory.',
              'Bolt is not available for the Large-image engine in this version.',
              'This image is too small for the Large-image engine.',
              '<>\u00d7 would make <> \u00d7 <> px, over the <> px limit for the longest side.'):
        assert s in entries or any(s in e for e in entries), s


def test_the_section_follows_the_copy_rules():
    text = STRINGS.read_text(encoding='utf-8')
    section = text[text.index('## Engines (5.0.2)'):]
    assert 'every pixel' not in section.lower()
    assert not re.search(r'(?i)\bidentical\b', section)
