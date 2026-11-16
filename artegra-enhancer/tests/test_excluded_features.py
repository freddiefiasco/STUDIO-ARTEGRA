"""Features that are not part of this product stay out: no file name or content carries them, and the window loads
only the enhancement tab. Their names are not kept in the repository: the maintainer's untracked
.local/private-terms.txt lists them with the private terms (see tools/public_scan.py). Without that file, as in CI,
the two word checks are skipped and the check of what the window loads still runs."""
import subprocess
from pathlib import Path

import pytest

from tools import public_scan

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = public_scan.load_private_terms()
needs_terms = pytest.mark.skipif(not EXCLUDED, reason="no .local/private-terms.txt: the listed words are checked where it is present")


def tracked_files():
    try:
        out = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT, stderr=subprocess.DEVNULL)
        names = [n.decode("utf-8") for n in out.split(b"\0") if n]
        if names:
            return [ROOT / n for n in names]
    except (OSError, subprocess.CalledProcessError):
        pass
    skip = {".git", ".venv", "__pycache__", ".local", "build", "dist"}
    return [p for p in ROOT.rglob("*") if p.is_file() and not skip.intersection(p.relative_to(ROOT).parts)]


@needs_terms
def test_no_file_name_or_content_names_an_excluded_feature():
    found = []
    for path in tracked_files():
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT).as_posix()
        issues = public_scan.check_blob(rel, path.read_bytes())
        if any(word.lower() in rel.lower() for word in EXCLUDED) or any("excluded identifier" in issue for issue in issues):
            found.append(rel)
    assert found == []


@needs_terms
def test_the_public_content_scan_refuses_them_too():
    for word in EXCLUDED:
        assert word in public_scan.FORBIDDEN
        assert public_scan.check_blob("x.qml", ("import " + word.capitalize() + "View").encode())


def test_the_window_loads_only_the_enhancement_tab():
    main = (ROOT / "ui" / "qml" / "Main.qml").read_text(encoding="utf-8")
    assert "CreativeUpscalerView {" in main and "Loader" not in main
    view = (ROOT / "ui" / "qml" / "CreativeUpscalerView.qml").read_text(encoding="utf-8")
    assert view.count("Loader {") == 1 and "creative/CreativeUpscalerTab.qml" in view
    qml = sorted(p.relative_to(ROOT / "ui" / "qml").as_posix() for p in (ROOT / "ui" / "qml").glob("*.qml"))
    assert qml == ["CreativeUpscalerView.qml", "Main.qml", "SetupView.qml"]
