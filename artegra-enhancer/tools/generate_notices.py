"""Generate bundled-package notices from the installed locked environment."""
from importlib import metadata
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ("PySide6", "PySide6_Essentials", "PySide6_Addons", "shiboken6", "numpy", "Pillow", "pyinstaller")


def main():
    sections = ["THIRD-PARTY NOTICES\n\nGenerated from the locked build environment.\n"
                "Qt/PySide is used under the LGPL option; replaceable dynamic libraries are retained.\n"
                "Qt source and build instructions: https://code.qt.io/cgit/\n"
                "Source for the exact PySide version: https://code.qt.io/cgit/pyside/pyside-setup.git/\n"
                "The runtime engine is installed separately and keeps its source and licences.\n"
                "Model weights are not bundled; see MODEL-LICENSES.md.\n"]
    for name in PACKAGES:
        dist = metadata.distribution(name)
        sections.append(f"\n{'=' * 72}\n{name} {dist.version}\nLicence: {dist.metadata.get('License-Expression') or dist.metadata.get('License', 'See text below')}\n")
        found = 0
        for relative in dist.files or []:
            text = str(relative).lower()
            if any(token in text for token in ("license", "copying", "notice")) and relative.suffix.lower() in ("", ".txt", ".md", ".rst"):
                path = dist.locate_file(relative)
                if path.is_file():
                    sections.append(f"\n--- {relative.name} ---\n" + path.read_text(encoding="utf-8", errors="replace"))
                    found += 1
        if not found:
            raise RuntimeError(f"No licence text found for {name}")
    for folder in (ROOT / "licenses", ROOT / "ui/qml/creative/fonts", ROOT / "runtime/licenses"):
        for path in sorted(folder.rglob("*")):
            if path.is_file() and (folder.name != "fonts" or path.suffix == ".txt"):
                sections.append(f"\n{'=' * 72}\n{path.relative_to(ROOT).as_posix()}\n"
                                + path.read_text(encoding="utf-8", errors="replace"))
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if python_license.exists():
        sections.append("\nPython\n" + python_license.read_text(encoding="utf-8"))
    else:
        raise RuntimeError("Python licence missing from the build environment")
    (ROOT / "THIRD-PARTY-NOTICES.txt").write_text("\n".join(sections), encoding="utf-8")


if __name__ == "__main__":
    main()
