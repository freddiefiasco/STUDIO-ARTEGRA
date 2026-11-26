"""The published SBOM describes the shipped package, not the build environment (QA1-06)."""
import json

import pytest

from tools import build_release as br

PYTHON = {"python": "3.13.14", "python_url": "https://www.python.org/ftp/python/3.13.14/python-3.13.14-embed-amd64.zip",
          "python_archive_sha256": "90" * 32}
FONTS = {"ui/qml/creative/fonts/InstrumentSans-Regular.ttf": "aa" * 32,
         "ui/qml/creative/fonts/InstrumentSans-Medium.ttf": "bb" * 32}


def component(name, version):
    return {"bom-ref": f"{name}=={version}", "name": name, "version": version, "type": "library",
            "purl": f"pkg:pypi/{name.lower()}@{version}"}


def build_environment():
    names = [("PySide6", "6.12.0"), ("PySide6_Essentials", "6.12.0"), ("PySide6_Addons", "6.12.0"),
             ("PySide6_WebEngine", "6.12.0.140"), ("shiboken6", "6.12.0"), ("numpy", "2.5.4"), ("pillow", "12.3.0"),
             ("pyinstaller", "6.20.0"), ("pytest", "9.0.2"), ("cyclonedx-bom", "7.2.1"), ("artegra-enhancer-pilot", "5.0.0b1")]
    return {"bomFormat": "CycloneDX", "specVersion": "1.6", "metadata": {"properties": [{"name": "cdx:reproducible", "value": "true"}]},
            "components": [component(*n) for n in names],
            "dependencies": [{"ref": "PySide6==6.12.0", "dependsOn": ["PySide6_Addons==6.12.0", "PySide6_Essentials==6.12.0",
                                                                     "PySide6_WebEngine==6.12.0.140"]},
                             {"ref": "PySide6_Essentials==6.12.0", "dependsOn": ["shiboken6==6.12.0"]},
                             {"ref": "pillow==12.3.0", "dependsOn": ["pytest==9.0.2"]},
                             {"ref": "pyinstaller==6.20.0", "dependsOn": ["pefile==1"]}]}


SHIPPED = {"pyside6": "6.12.0", "pyside6-essentials": "6.12.0", "pyside6-addons": "6.12.0", "shiboken6": "6.12.0",
           "numpy": "2.5.4", "pillow": "12.3.0"}


def test_only_the_shipped_distributions_and_the_bundled_runtime_and_font():
    out = br.shipped_sbom(build_environment(), SHIPPED, "5.0.0-beta.1", PYTHON, FONTS)
    names = [c["name"] for c in out["components"]]
    for absent in ("pyinstaller", "pytest", "cyclonedx-bom", "PySide6_WebEngine", "artegra-enhancer-pilot"):
        assert absent not in names
    assert {br.normal_name(n) for n in names if n[0] != "I" and " " not in n} == set(SHIPPED)
    root = out["metadata"]["component"]
    assert (root["name"], root["version"], root["type"]) == ("Artegra Enhancer (Beta)", "5.0.0-beta.1", "application")
    runtime = next(c for c in out["components"] if c["name"] == "CPython embeddable package")
    assert runtime["version"] == "3.13.14" and runtime["hashes"][0]["content"] == "90" * 32
    assert runtime["licenses"] == [{"license": {"id": "PSF-2.0"}}]
    packs = [c for c in out["components"] if c["name"].endswith(" node pack")]          # 5.0.2: both node packs, GPL
    assert [c["name"] for c in packs] == ["claude_creative node pack", "claude_banded node pack"]
    assert all(c["licenses"] == [{"license": {"id": "GPL-3.0-only"}}] and c["version"] == "5.0.0-beta.1" for c in packs)
    fonts = [c for c in out["components"] if c.get("group") == "Instrument Sans"]
    assert [f["name"] for f in fonts] == ["InstrumentSans-Medium.ttf", "InstrumentSans-Regular.ttf"]
    assert all(f["licenses"] == [{"license": {"id": "OFL-1.1"}}] for f in fonts)
    assert out["metadata"]["properties"] == [{"name": "cdx:reproducible", "value": "true"}]
    assert "pilot" not in json.dumps(out).lower()


def test_every_dependency_reference_resolves():
    out = br.shipped_sbom(build_environment(), SHIPPED, "5.0.0-beta.1", PYTHON, FONTS)
    refs = {c["bom-ref"] for c in out["components"]} | {out["metadata"]["component"]["bom-ref"]}
    assert len(refs) == len(out["components"]) + 1
    for entry in out["dependencies"]:
        assert entry["ref"] in refs
        assert set(entry.get("dependsOn", [])) <= refs
    root = next(e for e in out["dependencies"] if e["ref"] == "artegra-enhancer")
    assert {"PySide6==6.12.0", "numpy==2.5.4", "pillow==12.3.0", "cpython-embed==3.13.14"} <= set(root["dependsOn"])
    pyside = next(e for e in out["dependencies"] if e["ref"] == "PySide6==6.12.0")
    assert pyside["dependsOn"] == ["PySide6_Addons==6.12.0", "PySide6_Essentials==6.12.0"]
    assert "dependsOn" not in next(e for e in out["dependencies"] if e["ref"] == "pillow==12.3.0")


def test_the_same_input_gives_the_same_document():
    a = br.shipped_sbom(build_environment(), SHIPPED, "5.0.0-beta.1", PYTHON, FONTS)
    b = br.shipped_sbom(build_environment(), dict(reversed(list(SHIPPED.items()))), "5.0.0-beta.1", PYTHON, dict(reversed(list(FONTS.items()))))
    assert json.dumps(a, indent=2) == json.dumps(b, indent=2)


def test_a_shipped_distribution_missing_from_the_document_stops_the_build():
    with pytest.raises(ValueError, match="every shipped distribution"):
        br.shipped_sbom(build_environment(), dict(SHIPPED, extra="1.0"), "5.0.0-beta.1", PYTHON, FONTS)


def test_site_distributions_reads_names_and_versions(tmp_path):
    for folder, name, version in (("PySide6_Essentials-6.12.0.dist-info", "PySide6_Essentials", "6.12.0"),
                                  ("pillow-12.3.0.dist-info", "pillow", "12.3.0")):
        (tmp_path / folder).mkdir()
        (tmp_path / folder / "METADATA").write_text(f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n\nName: not a header\n",
                                                    encoding="utf-8")
    assert br.site_distributions(tmp_path) == {"pyside6-essentials": "6.12.0", "pillow": "12.3.0"}
