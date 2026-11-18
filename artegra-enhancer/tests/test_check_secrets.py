"""The secret scans: the file export, and with --history every commit of every branch and tag (QA1-04)."""
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tools import check_secrets

ROOT = Path(__file__).resolve().parents[1]


def test_the_file_scans_alone_by_default():
    commands = check_secrets.scan_commands(Path("export"), "gitleaks.exe", "trufflehog.exe")
    assert [c[1][:2] for c in commands] == [["gitleaks.exe", "dir"], ["trufflehog.exe", "filesystem"]]
    assert all(c[2] is None for c in commands)


def test_history_scans_every_ref_offline():
    commands = check_secrets.scan_commands(Path("export"), "gitleaks.exe", "trufflehog.exe", history=True)
    gitleaks, trufflehog = commands[2][1], commands[3][1]
    assert gitleaks[:3] == ["gitleaks.exe", "git", "."] and "--log-opts=--all" in gitleaks and "--redact" in gitleaks
    assert trufflehog[:3] == ["trufflehog.exe", "git", "file://."]
    assert {"--fail", "--no-update", "--no-verification"} <= set(trufflehog)
    top = Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], cwd=ROOT, text=True).strip())
    assert commands[2][2] == commands[3][2] == top
    assert [c[0] for c in commands[2:]] == ["gitleaks.exe (history)", "trufflehog.exe (history)"]


def test_a_finding_fails_the_run_and_its_value_is_never_printed(capsys):
    fake = "ghp_" + "x" * 36
    answers = iter([SimpleNamespace(returncode=0, stdout="", stderr=""),
                    SimpleNamespace(returncode=1, stdout=fake, stderr=fake)])
    with mock.patch.object(check_secrets.subprocess, "run", side_effect=lambda *a, **k: next(answers)) as run:
        code = check_secrets.run_scans([("a", ["a"], None), ("b (history)", ["b"], Path("."))])
    out = capsys.readouterr().out
    assert code == 1
    assert "a: passed" in out and "b (history): FAILED" in out
    assert fake not in out
    assert run.call_args_list[1].kwargs["cwd"] == Path(".")
