"""docs/STRINGS.md lists every user-facing string of the Large-image engine (B15): the ones already in the base
(service/banded_runner.py, the runner's developer-build lines, service/build_channel.py, engine/banded_plan.py's refusals,
service/plane_io.py) and the ones the engine naming adds (service/media.py, host/installation.py, the QML). Both ways: every
string in those places is listed, and every listed string is in the code. Placeholders (<N>, {k}) compare as one."""
import ast
import re
from pathlib import Path

from host import installation
from service import media

ROOT = Path(__file__).resolve().parents[1]
STRINGS = ROOT / 'docs' / 'STRINGS.md'
SOURCES = ('service/banded_runner.py', 'engine/banded_plan.py', 'service/build_channel.py', 'service/plane_io.py')
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
    return ' ' in s and (s[:1].isupper() or s.startswith('<>')) and s not in NOT_COPY


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
    found += [s for s in literals('service/runner.py') if copy_like(s) and ('Large-image' in s or 'developer setting' in s)]
    found += [norm(getattr(media, k)) for k in ('ENGINE_CLASSIC', 'ENGINE_LARGE', 'ENGINE_LARGE_FORCED', 'ENGINE_HALO_NOTE',
                                                'DISK_NEED', 'MEMORY_CLASS')]
    found.append(norm(installation.MEMORY_48))
    return found


def haystack():
    """Every literal of the places above (and the QML), joined in source order within a file: a listed string may be
    built from several literals (a message with an optional part)."""
    parts = []
    for path in SOURCES + ('service/runner.py', 'service/media.py', 'host/installation.py'):
        parts.append(''.join(literals(path)))
    for p in sorted((ROOT / 'ui' / 'qml').rglob('*.qml')) + sorted((ROOT / 'ui' / 'qml').rglob('*.js')):
        from tests.test_mode_names import js_literals
        parts.append(''.join(norm(lit[1:-1]) for kind, lit in js_literals(p.read_text(encoding='utf-8')) if kind == 'string'))
    return '\n'.join(parts)


def test_every_large_image_string_in_the_code_is_listed():
    entries = listed()
    missing = [s for s in source_strings() if not any(s in e for e in entries)]
    assert missing == []


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
