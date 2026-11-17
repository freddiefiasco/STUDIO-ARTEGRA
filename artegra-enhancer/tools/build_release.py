"""Build the Windows standalone host, optional per-user installer and portable zip."""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]
NAME = "ArtegraEnhancer"
PUBLIC_MATERIAL = ("LICENSE.txt", "README.md", "CHANGELOG.md", "INSTALL.md", "KNOWN-ISSUES.md", "PRIVACY.md", "BETA-TERMS.md", "THIRD-PARTY-NOTICES.txt", "models.manifest.json", "MODEL-LICENSES.md", "asset-hashes.json", "tools/verify_models.py", "installer/TERMS.txt")
DESKTOP_DISTRIBUTIONS = ("PySide6", "PySide6-Essentials", "PySide6-Addons", "shiboken6", "numpy", "pillow")


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


def setup_terms(root: Path = ROOT) -> str:
    """One consent page containing the exact disclosed Redux and Bolt terms."""
    catalogue = json.loads((root / "models.manifest.json").read_text(encoding="utf-8-sig"))
    models = [model for model in catalogue["models"]
              if model.get("required_for_standard") or model["id"] == "hyper-sdxl-8steps-cfg"]
    sections = [
        "ARTEGRA ENHANCER (BETA) — SOFTWARE AND MODEL TERMS\n\n"
        "Setup installs Artegra Enhancer and automatically downloads the files needed "
        "for Redux and Bolt enhancement. An internet connection is required. "
        "Allow about 40 GB of free space for installation, including temporary files.\n\n"
        "By selecting 'I accept the software and model terms' and installing, you accept the Studio "
        "Artegra evaluation terms and the publisher cards and applicable terms for "
        "the six models listed below. Acceptance is recorded on this computer. "
        "Please read the full saved terms included after this summary. No account, "
        "model-host token or separate setup command is required.\n\n"
        "Model weights are obtained directly from their named publishers. Each "
        "download is verified before use. Studio Artegra does not grant rights to "
        "third-party models. These licences have different conditions. In particular, "
        "TTPlanet declares an OpenRAIL family without an exact version or full text; "
        "its no-adult-content request and that uncertainty are disclosed below.\n\n"
        "Your images are processed locally and are not uploaded by setup. Closing "
        "setup preserves downloaded data so installation can resume. Uninstalling "
        "the app never removes your images. It keeps the downloaded AI files and your "
        "settings unless you choose to remove them.\n\n"
        "STUDIO ARTEGRA SOFTWARE TERMS\n\n" + (root / "LICENSE.txt").read_text(encoding="utf-8").strip(),
    ]
    for model in models:
        path = (root / model["license_file"]).resolve()
        if not path.is_relative_to(root.resolve()) or sha256(path) != model["license_snapshot_sha256"]:
            raise ValueError(f"The saved terms do not match the catalogue: {model['id']}")
        sections.append(
            f"{model['display_name']}\n"
            f"{model['acceptance_notice']}\n"
            f"Publisher: {model['model_card_url']}\n"
            f"Terms: {model['license_url']}\n"
            f"Saved terms: {model['license_file']}\n\n"
            + path.read_text(encoding="utf-8").strip()
        )
    return ("\n\n" + "=" * 72 + "\n\n").join(sections) + "\n"


def copy_public_material(output: Path):
    for relative in PUBLIC_MATERIAL:
        source = ROOT / relative
        if source.exists():
            target = output / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    for relative in ("licenses", "docs"):
        if (ROOT / relative).is_dir():
            shutil.copytree(ROOT / relative, output / relative, dirs_exist_ok=True)


def desktop_path_file() -> str:
    # The application and only its bundled packages are importable. No site
    # initialisation, user installation, registry entry or current directory.
    return "python313.zip\n.\nLib/site-packages\n..\n"


def copy_locked_distribution(name: str, destination: Path, expected: str) -> dict:
    distribution = importlib.metadata.distribution(name)
    if distribution.version != expected:
        raise RuntimeError(f"Build dependency {name} must be {expected}, found {distribution.version}")
    source_root = Path(distribution.locate_file("")).resolve()
    copied = 0
    for item in distribution.files or ():
        relative = Path(str(item))
        # Wheel entry-point scripts are development tools, not app dependencies.
        if relative.is_absolute() or ".." in relative.parts:
            continue
        if "__pycache__" in relative.parts or relative.suffix == ".pyc" or relative.name in {"direct_url.json", "INSTALLER", "REQUESTED"}:
            continue
        source = Path(distribution.locate_file(item)).resolve()
        if not source.is_relative_to(source_root) or not source.is_file():
            raise ValueError(f"Unsafe or missing dependency file: {name}/{relative}")
        if item.hash:
            digest = hashlib.new(item.hash.mode, source.read_bytes()).digest()
            encoded = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
            if encoded != item.hash.value:
                raise ValueError(f"Installed dependency differs from its wheel record: {name}/{relative}")
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied += 1
    if not copied:
        raise ValueError(f"No distributable package files found for {name}")
    return {"name": name, "version": distribution.version, "files": copied}


def prepare_desktop_runtime(output: Path, cache: Path) -> dict:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from runtime import setup_runtime
    if not setup_runtime.PYTHON_VERSION.startswith("3.13."):
        raise RuntimeError("The desktop package currently requires the CPython 3.13 ABI.")
    url, digest = setup_runtime.ASSETS["python"]
    archive = cache / ("python-" + setup_runtime.PYTHON_VERSION + "-embed-amd64.zip")
    cache.mkdir(parents=True, exist_ok=True)
    setup_runtime.download(url, digest, archive)
    runtime = output / "desktop-runtime"
    setup_runtime.safe_extract(archive, runtime)
    (runtime / "python313._pth").write_text(desktop_path_file(), encoding="ascii")
    site = runtime / "Lib/site-packages"
    site.mkdir(parents=True)
    locked = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    versions = {package["name"].lower().replace("_", "-"): package["version"]
                for package in locked["package"] if "version" in package}
    packages = [copy_locked_distribution(name, site, versions[name.lower()]) for name in DESKTOP_DISTRIBUTIONS]
    receipt = {"format": "official-embedded-python-and-unpacked-packages", "python": setup_runtime.PYTHON_VERSION,
               "python_url": url, "python_archive_sha256": digest, "packages": packages,
               "python_exe_sha256": sha256(runtime / "python.exe"),
               "pythonw_exe_sha256": sha256(runtime / "pythonw.exe")}
    (runtime / "PACKAGE-PROVENANCE.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def compile_launchers(output: Path):
    windows = Path(os.environ["SystemRoot"])
    compiler = next((path for path in (windows / "Microsoft.NET/Framework64/v4.0.30319/csc.exe",
                                      windows / "Microsoft.NET/Framework/v4.0.30319/csc.exe") if path.is_file()), None)
    if compiler is None:
        raise RuntimeError("The Windows .NET Framework C# compiler is required to build the launcher.")
    source = ROOT / "installer/launcher.cs"
    icon = ROOT / "installer/ArtegraEnhancer.ico"
    common = [compiler, "/nologo", "/platform:x64", "/optimize+", "/win32icon:" + str(icon)]
    run(common + ["/target:winexe", "/reference:System.Windows.Forms.dll", "/out:" + str(output / (NAME + ".exe")), source])
    internal = output / "setup-internal"
    internal.mkdir()
    run(common + ["/target:exe", "/define:SETUP_WORKER", "/out:" + str(internal / "PrepareArtegra.exe"), source])
    return {"source_sha256": sha256(source), "compiler_sha256": sha256(compiler), "icon_sha256": sha256(icon),
            "main_sha256": sha256(output / (NAME + ".exe")),
            "helper_sha256": sha256(internal / "PrepareArtegra.exe")}


def publish_staging(staging: Path, output: Path, build_dir: Path):
    # Replace only our exact generated output. Preserve the previous package;
    # never recursively delete a computed directory or follow a directory link.
    root = ROOT.resolve()
    for path in (staging, output, build_dir):
        if path.is_symlink() or getattr(path, "is_junction", lambda: False)() or not path.resolve().is_relative_to(root):
            raise ValueError("Build output must be a real directory inside this checkout.")
    if output != ROOT / "dist" / NAME:
        raise ValueError("Unexpected release output directory")
    if output.exists():
        output.rename(build_dir / ("previous-output-" + uuid.uuid4().hex))
    staging.rename(output)


def versions():
    """(PEP 440 version for file names, display version, Windows file version) for one release, checked to agree."""
    import re
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    display = re.search(r'^VERSION = "([^"]+)"', (ROOT / "host" / "config.py").read_text(encoding="utf-8"), re.M).group(1)
    m = re.fullmatch(r"(\d+\.\d+\.\d+)(?:-(alpha|beta|rc)\.(\d+))?", display)
    if not m:
        raise ValueError("host/config.py VERSION must look like 5.0.0 or 5.0.0-beta.1")
    pep440 = m.group(1) + ({"alpha": "a", "beta": "b", "rc": "rc"}[m.group(2)] + m.group(3) if m.group(2) else "")
    if pep440 != version:
        raise ValueError(f"pyproject.toml version {version} does not match host/config.py VERSION {display}")
    numbers = [int(x) for x in m.group(1).split(".")]
    build_number = {"alpha": 0, "beta": 1, "rc": 2}.get(m.group(2), 9) * 100 + int(m.group(3) or 0)
    return version, display, ".".join(map(str, numbers + [build_number]))


def build(*, installer=False, smoke=True, allow_missing_docs=False):
    if sys.platform != "win32" or sys.maxsize <= 2**32:
        raise RuntimeError("Build this release on Windows x64.")
    version, display_version, file_version = versions()
    (ROOT / "installer" / "TERMS.txt").write_text(setup_terms(), encoding="utf-8-sig")
    build_dir, dist = ROOT / "build" / "release", ROOT / "dist"
    build_dir.mkdir(parents=True, exist_ok=True)
    dist.mkdir(exist_ok=True)
    staging = build_dir / ("standalone-" + uuid.uuid4().hex)
    staging.mkdir()
    data_paths = ("host", "ui", "service", "engine", "node_pack", "runtime", "cu_service.py", "support_bundle.py")
    for name in data_paths:
        source = ROOT / name
        if source.is_dir():
            shutil.copytree(source, staging / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            shutil.copy2(source, staging / name)
    if not allow_missing_docs:
        for name in ("docs", "licenses", "LICENSE.txt", "THIRD-PARTY-NOTICES.txt"):
            if not (ROOT / name).exists():
                raise FileNotFoundError(f"Required release material is missing: {name}")
    copy_public_material(staging)
    python_receipt = prepare_desktop_runtime(staging, build_dir / "downloads")
    launcher_receipt = compile_launchers(staging)
    (staging / "PACKAGE-PROVENANCE.json").write_text(json.dumps({"desktop": python_receipt, "launcher": launcher_receipt}, indent=2) + "\n", encoding="utf-8")
    output = dist / NAME
    publish_staging(staging, output, build_dir)
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
            raise RuntimeError(f"Packaged startup check failed; see {build_dir / 'smoke-result.json'}")
    artifacts = []
    if installer:
        compiler = shutil.which("ISCC.exe") or next((str(path) for path in (ROOT / '.local' / 'inno' / 'ISCC.exe', Path(os.environ.get("ProgramFiles", "")) / "Inno Setup 7" / "ISCC.exe",) if path.exists()), None)
        if not compiler:
            raise RuntimeError("Inno Setup 7.1 or newer is required for --installer; the standalone folder is built.")
        run([compiler, f"/DAppVersion={display_version}", f"/DFileVersion={version}", f"/DVersionInfo={file_version}",
             f"/DSourceDir={output}", f"/DOutputDir={dist}", ROOT / "installer" / "ArtegraEnhancer.iss"])
        artifacts.append(dist / f"ArtegraEnhancer-{version}-Setup.exe")
    archive = dist / f"ArtegraEnhancer-{version}-windows-x64.zip"
    package_zip(output, archive)
    artifacts.append(archive)
    # The SBOM is published beside the installer and the zip, so the checksums cover it too.
    shutil.copy2(sbom, dist / sbom.name)
    artifacts.append(dist / sbom.name)
    (dist / "SHA256SUMS.txt").write_text("".join(f"{sha256(path)}  {path.name}\n" for path in artifacts))
    print(json.dumps({"folder": str(output), "artifacts": [path.name for path in artifacts], "smoke": smoke, "gpu_validation": False}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installer", action="store_true")
    parser.add_argument("--skip-smoke", action="store_true")
    parser.add_argument("--allow-missing-docs", action="store_true", help="Development build only")
    args = parser.parse_args()
    build(installer=args.installer, smoke=not args.skip_smoke, allow_missing_docs=args.allow_missing_docs)
