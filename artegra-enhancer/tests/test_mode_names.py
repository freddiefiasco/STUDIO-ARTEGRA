"""Redux and Bolt in every sentence a person reads; the ids stay "standard" and "fast"; old wording is still parsed."""
import ast
import re
from pathlib import Path

import pytest

from engine import controls
from service import naming, runner

ROOT = Path(__file__).resolve().parents[1]
WORDS = re.compile(r"\b(Standard|Fast)\b")
# Parsers that must read the alpha's stored sentences as well as the Beta's (plan-check D1), and the publisher's model name.
ALLOWED = {
    ("ui/qml/creative/CreativeUpscalerTab.qml", r"/\s*Choose (?:Standard|Redux)\.\s*$/"),
    ("ui/qml/creative/CreativeUpscalerTab.qml", "/^(Fast mode is not available|Fast mode cannot be used|This image is too large for Fast mode|Bolt is not available|Bolt cannot be used|This image is too large for Bolt)/"),
    ("ui/qml/creative/CuActivityLog.qml", r"/^Started (.+) \(\d+ pass(?:es)?\), (Fast mode|Bolt|matching earlier results|sped up)$/"),
    ("ui/qml/creative/CuActivityLog.qml", '"Fast mode"'),
}


def js_literals(text):
    """(kind, literal) for every string, template and regex literal outside comments."""
    out, i, n = [], 0, len(text)
    prev, word = "", ""
    while i < n:
        c = text[i]
        if c in "\"'`":
            j = i + 1
            while j < n and text[j] != c:
                j += 2 if text[j] == "\\" else 1
            out.append(("string", text[i:j + 1]))
            i, prev, word = j + 1, "r", ""
            continue
        if text.startswith("//", i):
            i = text.find("\n", i) if text.find("\n", i) >= 0 else n
            continue
        if text.startswith("/*", i):
            i = text.find("*/", i + 2) + 2 if text.find("*/", i + 2) >= 0 else n
            continue
        if c == "/" and (prev == "" or prev in "(,=:[!&|?{};+-*%<>~^" or (prev == "w" and word in ("return", "typeof", "case"))):
            j, cls = i + 1, False
            while j < n and text[j] != "\n" and (cls or text[j] != "/"):
                if text[j] == "\\":
                    j += 1
                elif text[j] == "[":
                    cls = True
                elif text[j] == "]":
                    cls = False
                j += 1
            if j < n and text[j] == "/":
                j += 1
                while j < n and text[j].isalpha():
                    j += 1
                out.append(("regex", text[i:j]))
                i, prev, word = j, "r", ""
                continue
        if c.isalnum() or c in "_$":
            j = i
            while j < n and (text[j].isalnum() or text[j] in "_$"):
                j += 1
            word, prev, i = text[i:j], "w", j
            continue
        if not c.isspace():
            prev, word = c, ""
        i += 1
    return out


def py_literals(text):
    """String constants a person can read: every str constant and f-string part except docstrings."""
    tree = ast.parse(text)
    docs = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(body, list) and body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            docs.add(id(body[0].value))
    return [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs]


def offenders():
    found = []
    for path in sorted(list((ROOT / "ui").rglob("*.qml")) + list((ROOT / "ui").rglob("*.js"))):
        rel = path.relative_to(ROOT).as_posix()
        for kind, lit in js_literals(path.read_text(encoding="utf-8")):
            if WORDS.search(lit) and (rel, lit) not in ALLOWED:
                found.append((rel, lit))
    for folder in ("service", "host"):
        for path in sorted((ROOT / folder).rglob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            for lit in py_literals(path.read_text(encoding="utf-8")):
                if WORDS.search(lit):
                    found.append((rel, lit))
    iss = (ROOT / "installer" / "ArtegraEnhancer.iss").read_text(encoding="utf-8")
    for line in iss.splitlines():
        if WORDS.search(line):
            found.append(("installer/ArtegraEnhancer.iss", line))
    summary = (ROOT / "installer" / "TERMS.txt").read_text(encoding="utf-8-sig").split("STUDIO ARTEGRA SOFTWARE TERMS")[0]
    if WORDS.search(summary):
        found.append(("installer/TERMS.txt", "summary"))
    return found


def test_no_sentence_a_person_reads_says_standard_or_fast():
    assert offenders() == []


def test_the_scanner_finds_the_words_it_looks_for():
    assert js_literals('x = "Use Standard for finals." // Fast\n') == [("string", '"Use Standard for finals."')]
    assert js_literals("var r = /Choose Standard/.test(s)") == [("regex", "/Choose Standard/")]
    assert py_literals('"""Fast doc."""\nx = "Fast mode"\n') == ["Fast mode"]


def test_the_controls_answer_names_redux_and_bolt_and_keeps_the_ids():
    doc = naming.controls_doc(controls.describe())
    assert [(m["key"], m["label"]) for m in doc["modes"]] == [("standard", "Redux"), ("fast", "Bolt")]
    assert doc["modes"][1]["text"] == "Quicker, with a slightly different look. Use Redux for finals."
    assert controls.MODE_LABELS == {"standard": "Standard", "fast": "Fast"}       # engine/ is unchanged


def test_the_engines_mode_error_reaches_people_in_the_new_words():
    with pytest.raises(controls.ControlError) as caught:
        controls.resolve({"mode": "turbo"})
    assert runner.plain_control_error(caught.value) == "Choose a mode: Redux or Bolt."


def js_engine():
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtQml import QJSEngine
    app = QCoreApplication.instance() or QCoreApplication([])
    return app, QJSEngine()


def regex_from(rel, needle):
    text = (ROOT / rel).read_text(encoding="utf-8")
    hits = [lit for kind, lit in js_literals(text) if kind == "regex" and needle in lit]
    assert len(hits) == 1, (rel, needle, hits)
    return hits[0]


def test_the_try_again_in_redux_tile_reads_alpha_and_beta_failures():
    app, engine = js_engine()
    pattern = regex_from("ui/qml/creative/CreativeUpscalerTab.qml", "This image is too large for")
    for text, want in (("Fast mode is not available, so this image was not upscaled. Queue it again in Standard.", True),
                       ("This image is too large for Fast mode, so it was not upscaled. Queue it again in Standard.", True),
                       ("Bolt is not available, so this image was not upscaled. Queue it again in Redux.", True),
                       ("This image is too large for Bolt, so it was not upscaled. Queue it again in Redux.", True),
                       ("Bolt cannot be used: a file it needs cannot be read. Choose Redux.", True),
                       ("GPU 1 ran out of memory.", False)):
        assert engine.evaluate(f"{pattern}.test({text!r})").toBool() is want, text


def test_the_activity_line_for_a_bolt_start_reads_both_wordings():
    app, engine = js_engine()
    pattern = regex_from("ui/qml/creative/CuActivityLog.qml", "matching earlier results")
    for line in ("Started a.png (1 pass), Fast mode", "Started a.png (1 pass), Bolt"):
        assert engine.evaluate(f"{pattern}.exec({line!r})[2]").toString() in ("Fast mode", "Bolt")
    source = (ROOT / "ui/qml/creative/CuActivityLog.qml").read_text(encoding="utf-8")
    assert '(m[2] === "Fast mode" || m[2] === "Bolt" ? " runs in Bolt"' in source


def test_the_choose_redux_tail_is_stripped_for_both_wordings():
    app, engine = js_engine()
    pattern = regex_from("ui/qml/creative/CreativeUpscalerTab.qml", "Choose (?:Standard|Redux)")
    for text in ("Fast mode is not available. Choose Standard.", "Bolt is not available. Choose Redux."):
        assert engine.evaluate(f"{text!r}.replace({pattern}, '')").toString() in ("Fast mode is not available.", "Bolt is not available.")


def test_bolt_results_are_named_bolt_and_old_fast_results_are_still_recognised():
    source = (ROOT / "service" / "runner.py").read_text(encoding="utf-8")
    assert "suffix = '_bolt' if" in source
    app, engine = js_engine()
    for rel in ("ui/qml/creative/CuQueueRow.qml", "ui/qml/creative/CuViewer.qml", "ui/qml/creative/CuResultsSheet.qml"):
        pattern = regex_from(rel, "(?:fast|bolt)")
        for name in ("/out/a_cu2x_fast.png", "/out/a_cu2x_bolt.png", "/out/a_cu2x_bolt_2.tif"):
            assert engine.evaluate(f"{pattern}.test({name!r})").toBool(), (rel, name)
        assert not engine.evaluate(f"{pattern}.test('/out/fast_cu2x.png')").toBool()
    tokens = regex_from("ui/qml/creative/Tokens.qml", "_cu\\d+x(?:_fast|_bolt)")
    assert engine.evaluate(f"{tokens}.exec('photo_cu2x_bolt_2').index").toInt() == 5
