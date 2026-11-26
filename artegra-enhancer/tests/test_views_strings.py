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
  engine shows them in its log, and the person sees the runner's plain sentence), and the banded finish's reasons.

At the build wave 2 merge, the places the other wave-2 packages added strings to (their adds), each by its own rule:
- service/workers.py's Large-image lines of the engine start (log only);
- the start-up probe engine/bxf/selfprobe.py: its error output and the reasons it raises;
- the banded finish's exact-selection reason (engine/bxf/selection.py).

Build wave 3 (S5): the reasons service/banded_runner.checkpoint_problem returns (its _WHY table and its literal returns) are
the <why> of the checkpoint line the person sees, so they are read from the source and listed under that line, both ways.

At the build wave 3 merge: service/bxf_probe.py (new; the start-up probe's service side) is scanned whole, as the other
SOURCES are, and the planner's refusals are checked in their wave-3 words (each names the engine and the size).

At the build wave 4 merge (no docs package in wave 4: the merge role lists each package's adds.strings): the
engine's stop after a Large-image image and its kept engine (service/banded_runner.py, scanned whole) and the
protected-area preview's refusal while the processor check runs (service/bxf_probe.py, scanned whole); the
scan finds both."""
import ast
import re
from pathlib import Path

from host import installation
from service import media

ROOT = Path(__file__).resolve().parents[1]
STRINGS = ROOT / 'docs' / 'STRINGS.md'
SOURCES = ('service/banded_runner.py', 'engine/banded_plan.py', 'service/build_channel.py', 'service/plane_io.py',
           'service/card_factor.py', 'service/bxf_probe.py')
RUNNER_PHRASES = ('Large-image', 'developer setting', 'graphics memory with the', 'smaller image', 'per window',
                  'graphics card measurement', 'timed before its first image', 'its speed before', 'system memory (RAM)')
# (5.0.1's own runner lines that name the graphics card, such as 'This image is still releasing its graphics card', are not
# 5.0.2 strings and stay out of this section)
LARGE_ONLY = ('service/media.py', 'service/plane_views.py')                 # their lines that name the Large-image engine
NODE_SOURCES = ('node_pack/claude_banded/__init__.py', 'node_pack/claude_banded/canny_plane.py',
                'node_pack/claude_banded/cn_plane.py',
                'node_pack/claude_banded/noise_banded.py', 'node_pack/claude_banded/vae_planes.py',
                'node_pack/claude_banded/sam_plane.py', 'node_pack/claude_banded/spot_banded.py',
                'node_pack/claude_banded/bxf/__init__.py')
FINISH_REASONS = (('node_pack/claude_banded/bxf/__init__.py', 'banded finish'), ('engine/bxf/g1.py', 'G1 table'))
WORKER_PHRASES = ('Large-image engine parts',)           # service/workers.py: the engine start's Large-image lines (log)
PROBE_SOURCE = 'engine/bxf/selfprobe.py'                 # the start-up probe's error output and the reasons it raises
FINISH_RAISED = (('engine/bxf/selection.py', 'exact selection cannot'),)     # a reason the banded finish gives
CHECKPOINT_SOURCE = 'service/banded_runner.py'           # checkpoint_problem's reasons, the <why> of CHECKPOINT_LINE
CHECKPOINT_LINE = ('The saved first part of pass <> of <> could not be used (<>), so the pass is made again from its '
                   'start.')
REASON_NOTE = ' — a reason of the line above'
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


def checkpoint_reasons():
    """Every reason text service/banded_runner.checkpoint_problem can return, read from the source (no import): the values of
    its _WHY table and the str literals and f-strings it returns (CHECKPOINT_MISSING, a name, and _WHY[key] are not
    literals, so the 'missing' sentinel is never taken). The service puts each into checkpoint_refused_text, the image's
    line; most start lower-case, so the copy-like rule alone would check none of them (S5)."""
    tree = ast.parse((ROOT / CHECKPOINT_SOURCE).read_text(encoding='utf-8'))
    out = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == '_WHY' for t in node.targets):
            out += [(v.lineno, v.col_offset, _lit(v)) for v in node.value.values]
        if isinstance(node, ast.FunctionDef) and node.name == 'checkpoint_problem':
            out += [(n.lineno, n.col_offset, _lit(n.value)) for n in ast.walk(node)
                    if isinstance(n, ast.Return) and n.value is not None and _lit(n.value) is not None]
    return [m for _, _, m in sorted(out)]


def listed_reasons(line):
    """The entries listed right under `line` (normalised) in docs/STRINGS.md that carry REASON_NOTE, in order."""
    lines = [x for x in STRINGS.read_text(encoding='utf-8').splitlines() if x.startswith('- ')]
    heads = [i for i, x in enumerate(lines) if norm(x[2:].split(' — ')[0].strip()) == line]
    assert len(heads) == 1, line
    out = []
    for x in lines[heads[0] + 1:]:
        if not x.endswith(REASON_NOTE):
            break
        out.append(norm(x[2:-len(REASON_NOTE)].strip()))
    return out


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
    found += [s for s in literals('service/workers.py') if copy_like(s) and any(p in s for p in WORKER_PHRASES)]
    found += [s for s in literals(PROBE_SOURCE) if s.startswith('selfprobe:')] + raised(PROBE_SOURCE)
    for path, phrase in FINISH_RAISED:
        found += [m for m in raised(path) if phrase in m]
    found += checkpoint_reasons()
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
    parts.append(''.join(literals('service/workers.py')))
    for path in (PROBE_SOURCE,) + tuple(p for p, _ in FINISH_RAISED):
        parts.append('\n'.join(literals(path)))
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
                 'May run slowly: this image needs about <> GB of graphics memory with the Classic engine; <> <> GB. The '
                 'part that does not fit may use shared memory. The image can then take longer than the time shown. A '
                 'pass that takes far longer than expected is stopped.',                         # small cards
                 ' The Classic engine accepts a smaller image, up to a result of about <> × <> px, but it may run '
                 "slowly: it does not fit the card's graphics memory.",      # small cards: a Large-image refusal
                 '<>: <> s per window',
                 'The viewer copy of a Large-image result could not be made: <>',                          # media.py (V3)
                 'The engine on <> lacks Large-image engine parts; it runs Classic engine images only',     # wave 2: workers
                 'the self-probe ran out of time after <> s (limit <> s)',                                  # the probe
                 'selfprobe: --width must be a positive number of pixels',
                 'CUFinishBanded: finish_tier must be one of <> (got <>)',                                  # the finish node
                 "numpy <> has no <>: exact selection cannot use numpy's own arithmetic",
                 'the tile ControlNet hint has no canvas plane beside it (canvas.plane in the stage plane folder), so its '
                 'memory format cannot be read',                                                          # cn_plane
                 'The Large-image engine on <> could not be stopped after its image, so no other image or '
                 'preview runs in it until it has been closed.',               # wave 4: the kept engine
                 "The protected-area preview cannot run while the app measures this computer's processor "
                 'for the Large-image engine. Try again in about <> minutes.'):   # wave 4: the preview's refusal
        assert want in found, want


def test_the_checkpoint_reasons_are_listed_under_their_line_both_ways():
    """S5: each reason checkpoint_problem returns is listed under the checkpoint line, and every reason listed there is one
    it returns. The scan is not vacuous: it finds the seven _WHY reasons and the five checks of the record, the input and
    each saved part."""
    from service import banded_runner
    reasons = checkpoint_reasons()
    assert len(reasons) == len(set(reasons)) >= 12, reasons             # 7 in _WHY and 5 returned (at the base)
    assert set(norm(v) for v in banded_runner._WHY.values()) <= set(reasons)
    assert norm(banded_runner.CHECKPOINT_MISSING) not in reasons                   # the sentinel is never shown
    for want in ('its record is damaged', 'its input does not match', 'its <> part is missing or damaged'):
        assert want in reasons, want
    assert norm(banded_runner.checkpoint_refused_text(0, 3, '{why}')) == CHECKPOINT_LINE.replace('<>', '1', 1) \
        .replace('<>', '3', 1)
    assert sorted(listed_reasons(CHECKPOINT_LINE)) == sorted(reasons)


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
    for s in ('The Large-image engine cannot make <> \u00d7 <> px on this computer: it needs a computer with at least 48 GB '
              'of memory.',
              'Bolt is not available for the Large-image engine in this version. Choose Redux to make <> \u00d7 <> px.',
              'The Large-image engine cannot make <> \u00d7 <> px: the image is too small for it.',
              "<>\u00d7 would make <> \u00d7 <> px, over the Large-image engine's <> px limit for the longest side.",
              "The Large-image engine cannot make <> \u00d7 <> px on this computer: this computer's processor has not been "
              'measured for the Large-image engine yet, so it can finish a pass of up to <> MP here, and this image needs <> '
              '<> MP pass.'):
        assert s in entries or any(s in e for e in entries), s


def test_the_section_follows_the_copy_rules():
    text = STRINGS.read_text(encoding='utf-8')
    section = text[text.index('## Engines (5.0.2)'):]
    assert 'every pixel' not in section.lower()
    assert not re.search(r'(?i)\bidentical\b', section)
