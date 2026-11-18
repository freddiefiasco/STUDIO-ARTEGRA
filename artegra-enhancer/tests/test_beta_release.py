"""Artegra Enhancer (Beta) 5.0.0-beta.1: one name and one version everywhere, an upgrade in place from the alpha,
and an installer that registers a proper uninstaller."""
import hashlib
import json
import re
import tomllib
from pathlib import Path

from host import config
from tools import build_release

ROOT = Path(__file__).resolve().parents[1]
ISS = (ROOT / "installer" / "ArtegraEnhancer.iss").read_text(encoding="utf-8")


def test_one_version_everywhere():
    assert config.VERSION == "5.0.0-beta.1"
    assert tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"] == "5.0.0b1"
    assert build_release.versions() == ("5.0.0b1", "5.0.0-beta.1", "5.0.0.101")
    assert '#define AppVersion "5.0.0-beta.1"' in ISS and '#define FileVersion "5.0.0b1"' in ISS
    assert "OutputBaseFilename=ArtegraEnhancer-{#FileVersion}-Setup" in ISS
    lock = (ROOT / "uv.lock").read_text(encoding="utf-8")
    assert re.search(r'name = "artegra-enhancer-pilot"\nversion = "5\.0\.0b1"', lock)


def test_the_download_links_point_at_this_release():
    tag = "artegra-enhancer-v5.0.0-beta.1"
    for doc in ("README.md", "INSTALL.md"):
        text = (ROOT / doc).read_text(encoding="utf-8")
        assert f"/releases/download/{tag}/ArtegraEnhancer-5.0.0b1-Setup.exe" in text, doc
        assert "0.1.0-alpha.4/" not in text and "0.1.0a4-Setup" not in text, doc


def test_the_name_a_person_sees():
    assert config.DISPLAY_NAME == "Artegra Enhancer (Beta)"
    for line in ("AppName=Artegra Enhancer (Beta)", "UninstallDisplayName=Artegra Enhancer (Beta)",
                 "DefaultGroupName=Artegra Enhancer (Beta)", "VersionInfoProductName=Artegra Enhancer (Beta)",
                 "AppPublisher=Studio Artegra", "UninstallDisplayIcon={app}\\ArtegraEnhancer.exe",
                 "SetupIconFile=ArtegraEnhancer.ico"):
        assert line in ISS, line
    main = (ROOT / "ui" / "qml" / "Main.qml").read_text(encoding="utf-8")
    assert "hostBridge.displayName" in main and "Creative Upscaler" not in main


def test_the_upgrade_from_the_alpha_keeps_everything():
    # Same AppId, folder and data key; the consent fingerprint (models.manifest.json + LICENSE.txt) is unchanged, so
    # the app does not ask an alpha user to accept again and the models are checked, not downloaded again.
    assert "AppId={{2B6628CA-E890-46BF-A894-E5D1E004707F}" in ISS
    assert "DefaultDirName={localappdata}\\Programs\\ArtegraEnhancer" in ISS
    assert "SetPreviousData(PreviousDataKey, 'AIDataDirectory', StoragePage.Values[0]);" in ISS
    assert hashlib.sha256((ROOT / "LICENSE.txt").read_bytes()).hexdigest() == \
        "3a3c23ce8580575ddb6b2dcf32468594c0ff16aa125ec6f5cb49e1de03a9ca1a"
    assert hashlib.sha256((ROOT / "models.manifest.json").read_bytes()).hexdigest() == \
        "a5e384ee6a7d931eade37728cb171d5aeab01215ad88a6ecf6349b4888f685b7"
    assert (config.APP_NAME, config.ORGANIZATION) == ("Artegra Enhancer", "Studio Artegra")


def test_the_alphas_shortcuts_are_replaced():
    for name in ('"{userprograms}\\Artegra Enhancer\\Artegra Enhancer.lnk"',
                 '"{userprograms}\\Artegra Enhancer\\Uninstall Artegra Enhancer.lnk"',
                 '"{autodesktop}\\Artegra Enhancer.lnk"'):
        assert f"Type: files; Name: {name}" in ISS
    assert 'Type: dirifempty; Name: "{userprograms}\\Artegra Enhancer"' in ISS
    assert 'Name: "{group}\\Uninstall Artegra Enhancer (Beta)"; Filename: "{uninstallexe}"' in ISS
    assert 'Name: "{group}\\Artegra Enhancer (Beta)"; Filename: "{app}\\ArtegraEnhancer.exe"' in ISS


def test_the_uninstaller_finds_a_state_folder_chosen_at_install():
    assert "SetPreviousData(PreviousDataKey, 'StateDirectory', StateDirectory);" in ISS
    assert "'Inno Setup CodeFile: StateDirectory'" in ISS
    assert "[UninstallDelete]" not in ISS


def test_the_uninstall_options_form_uses_the_inno_setup_7_call():
    # Inno Setup 7 takes the client size and scales it itself; the old call without arguments does not compile, and
    # scaling the size again would make the form too big at 125 % and 150 %.
    assert "Form := CreateCustomForm(440, 176, False, True);" in ISS
    assert "CreateCustomForm()" not in ISS
    assert "Form.ClientWidth :=" not in ISS and "Form.ClientHeight :=" not in ISS


def test_the_checksums_cover_every_published_file():
    # The release publishes the installer, the zip and the SBOM; SHA256SUMS.txt lists all three, as alpha 4's did.
    source = (ROOT / "tools" / "build_release.py").read_text(encoding="utf-8")
    assert "shutil.copy2(sbom, dist / sbom.name)" in source and "artifacts.append(dist / sbom.name)" in source
    assert source.index("artifacts.append(dist / sbom.name)") < source.index('(dist / "SHA256SUMS.txt")')


def test_the_icon_is_pinned_and_compiled_into_both_launchers():
    pins = json.loads((ROOT / "asset-hashes.json").read_text())
    icon = ROOT / "installer" / "ArtegraEnhancer.ico"
    assert pins["installer/ArtegraEnhancer.ico"] == hashlib.sha256(icon.read_bytes()).hexdigest()
    assert icon.read_bytes()[:4] == b"\x00\x00\x01\x00"
    source = (ROOT / "tools" / "build_release.py").read_text(encoding="utf-8")
    assert '"/win32icon:" + str(icon)' in source


def test_no_alpha_wording_is_left_where_people_read_it():
    from tests.test_mode_names import js_literals, py_literals
    word = re.compile(r"(?i)alpha")
    found = []
    for path in sorted((ROOT / "host").glob("*.py")):
        if path.name == "updates.py":          # parses other releases' tags, such as 0.1.0-alpha.4
            continue
        found += [(path.name, s) for s in py_literals(path.read_text(encoding="utf-8")) if word.search(s)]
    for path in sorted((ROOT / "ui" / "qml").rglob("*.qml")):
        found += [(path.name, s) for kind, s in js_literals(path.read_text(encoding="utf-8")) if kind == "string" and word.search(s)]
    for path in (ROOT / "installer" / "ArtegraEnhancer.iss", ROOT / "installer" / "launcher.cs"):
        found += [(path.name, line) for line in path.read_text(encoding="utf-8").splitlines() if word.search(line)]
    # The docs may name the alpha releases people upgrade from, but never call this release an alpha.
    self_description = re.compile(r"(?i)(?:this|the|public|pilot) (?:pilot )?alpha(?! 4)|alpha limits|alpha evaluation")
    for name in ("README.md", "INSTALL.md", "KNOWN-ISSUES.md", "PRIVACY.md", "BETA-TERMS.md", "FEEDBACK.md",
                 "docs/RELEASE-NOTES.md", "docs/COMPATIBILITY.md", "docs/BUILDING.md", "../README.md"):
        if not (ROOT / name).is_file():         # the repository's root README, absent in an app-only copy
            continue
        text = (ROOT / name).read_text(encoding="utf-8")
        found += [(name, m.group(0)) for m in self_description.finditer(text)]
    assert found == []
    assert not (ROOT / "PILOT-TERMS.md").exists()


def test_the_beta_terms_are_shipped_and_marked_for_review():
    terms = (ROOT / "BETA-TERMS.md").read_text(encoding="utf-8")
    assert "Draft for Max's legal review" in terms
    assert "BETA-TERMS.md" in build_release.PUBLIC_MATERIAL
