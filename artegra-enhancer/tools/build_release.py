"""Build the Windows standalone host, optional per-user installer and portable zip."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
NAME = "ArtegraEnhancer"
QT_MODULES = {"QtCore", "QtGui", "QtNetwork", "QtQml", "QtQuick", "QtQuickControls2", "QtWidgets", "QtOpenGL", "QtSvg"}


def run(args, **kwargs):
    env = dict(os.environ)
    windows = Path(os.environ["SystemRoot"])
    # Resolve Windows libraries from Windows, not unrelated apps on the user's PATH.
    # In particular, a foreign ICU DLL is ABI-incompatible with Qt's system ICU.
    env["PATH"] = os.pathsep.join(map(str, (Path(sys.executable).parent, windows / "System32", windows)))
    subprocess.run([str(arg) for arg in args], cwd=ROOT, check=True, env=env, **kwargs)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_zip(folder: Path, output: Path):
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(folder.parent).as_posix())


def build(*, installer=False, smoke=True, allow_missing_docs=False):
    if sys.platform != "win32":
        raise RuntimeError("Build this release on Windows x64.")
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    from PySide6 import __path__ as qt_path
    import PyInstaller
    qt_excludes = sorted(path.stem for path in Path(qt_path[0]).glob("Qt*.pyd") if path.stem not in QT_MODULES)
    build_dir, dist = ROOT / "build" / "release", ROOT / "dist"
    build_dir.mkdir(parents=True, exist_ok=True)
    dist.mkdir(exist_ok=True)
    hooks = build_dir / "hooks"
    hooks.mkdir(exist_ok=True)
    (hooks / "hook-PySide6.QtQml.py").write_text('''from pathlib import Path
from PyInstaller.utils.hooks.qt import add_qt6_dependencies, pyside6_library_info
hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
source = Path(pyside6_library_info.location['QmlImportsPath'])
for module in ('QtCore', 'QtQml', 'QtQuick'):
    for path in (source / module).rglob('*'):
        relative = path.relative_to(source)
        if module == 'QtQuick' and len(relative.parts) > 2 and relative.parts[1] not in {'Controls', 'Dialogs', 'Effects', 'Layouts', 'NativeStyle', 'Shapes', 'Templates', 'VectorImage', 'Window'}:
            continue
        if path.is_file():
            item = (str(path), str(Path(pyside6_library_info.qt_rel_dir) / 'qml' / path.parent.relative_to(source)))
            (binaries if path.suffix.lower() == '.dll' else datas).append(item)
''')
    common = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--noupx", "--distpath", dist, "--workpath", build_dir / "work", "--specpath", build_dir, "--paths", ROOT, "--additional-hooks-dir", hooks]
    for module in qt_excludes:
        common += ["--exclude-module", "PySide6." + module]
    for module in ("tkinter", "matplotlib", "torch", "torchvision", "scipy", "pytest", "IPython"):
        common += ["--exclude-module", module]
    data_paths = ("ui", "service", "engine", "node_pack", "runtime", "cu_service.py", "docs", "licenses", "LICENSE.txt", "README.md", "INSTALL.md", "KNOWN-ISSUES.md", "PRIVACY.md", "PILOT-TERMS.md", "THIRD-PARTY-NOTICES.txt", "models.manifest.json", "MODEL-LICENSES.md", "asset-hashes.json", "tools/verify_models.py")
    required = {"ui", "service", "engine", "node_pack", "runtime", "cu_service.py"}
    if not allow_missing_docs:
        required.update(("docs", "licenses", "LICENSE.txt", "THIRD-PARTY-NOTICES.txt"))
    for name in data_paths:
        path = ROOT / name
        if not path.exists():
            if name in required:
                raise FileNotFoundError(f"Required release material is missing: {name}")
            continue
        common += ["--add-data", f"{path}{os.pathsep}{name if path.is_dir() else Path(name).parent}"]
    for module in ("service.app", "runtime.setup_runtime", "PySide6.QtQuick", "PySide6.QtQuickControls2"):
        common += ["--hidden-import", module]
    run(common + ["--name", NAME, "--windowed", ROOT / "host" / "app.py"])
    # Separate console setup keeps download progress visible and never runs at install/startup.
    setup_entry = build_dir / "setup_entry.py"
    setup_entry.write_text("from runtime.setup_runtime import main\nraise SystemExit(main())\n")
    run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--noupx", "--contents-directory", "setup-internal", "--name", "SetupRuntime", "--distpath", build_dir / "setup-dist", "--workpath", build_dir / "setup-work", "--specpath", build_dir, "--paths", ROOT, "--add-data", f"{ROOT / 'runtime'}{os.pathsep}runtime", setup_entry])
    output = dist / NAME
    setup_output = build_dir / "setup-dist" / "SetupRuntime"
    shutil.copy2(setup_output / "SetupRuntime.exe", output / "SetupRuntime.exe")
    shutil.copytree(setup_output / "setup-internal", output / "setup-internal", dirs_exist_ok=True)
    # Source data must not carry interpreter caches or local build files.
    for cache in list(output.rglob("__pycache__")):
        shutil.rmtree(cache)
    for path in output.rglob("*.pyc"):
        path.unlink()
    sbom = output / "SBOM.cdx.json"
    run([sys.executable, "-m", "cyclonedx_py", "environment", "--output-reproducible", "--short-PURLs", "-o", sbom])
    document = json.loads(sbom.read_text())
    # Local editable project URLs are not portable package provenance.
    for component in document.get("components", []):
        component["externalReferences"] = [reference for reference in component.get("externalReferences", []) if not reference.get("url", "").startswith("file:")]
        component.pop("evidence", None)
    sbom.write_text(json.dumps(document, indent=2) + "\n")
    if smoke:
        result = subprocess.run([str(output / (NAME + ".exe")), "--smoke"], cwd=output, capture_output=True, text=True, timeout=65)
        (build_dir / "smoke-result.json").write_text(json.dumps({"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}, indent=2))
        if result.returncode:
            raise RuntimeError(f"Frozen smoke check failed; see {build_dir / 'smoke-result.json'}")
    artifacts = []
    if installer:
        compiler = shutil.which("ISCC.exe") or next((str(path) for path in (ROOT / '.local' / 'inno' / 'ISCC.exe', Path(os.environ.get("ProgramFiles(x86)", "")) / "Inno Setup 6" / "ISCC.exe",) if path.exists()), None)
        if not compiler:
            raise RuntimeError("Inno Setup 6 compiler is required for --installer; the standalone folder is built.")
        run([compiler, f"/DAppVersion={version}", f"/DSourceDir={output}", f"/DOutputDir={dist}", ROOT / "installer" / "ArtegraEnhancer.iss"])
        artifacts += sorted(dist.glob("ArtegraEnhancer-*-Setup.exe"))
    archive = dist / f"ArtegraEnhancer-{version}-windows-x64.zip"
    package_zip(output, archive)
    artifacts.append(archive)
    (dist / "SHA256SUMS.txt").write_text("".join(f"{sha256(path)}  {path.name}\n" for path in artifacts))
    print(json.dumps({"folder": str(output), "artifacts": [path.name for path in artifacts], "smoke": smoke, "gpu_validation": False}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installer", action="store_true")
    parser.add_argument("--skip-smoke", action="store_true")
    parser.add_argument("--allow-missing-docs", action="store_true", help="Development build only")
    args = parser.parse_args()
    build(installer=args.installer, smoke=not args.skip_smoke, allow_missing_docs=args.allow_missing_docs)
