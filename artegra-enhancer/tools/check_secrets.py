"""Scan a tracked-source export, and with --history every commit, without sending candidates to external services."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def scan_commands(target, gitleaks, trufflehog, history=False):
    """(label, command, working folder) for each scan. The file scans read the export in `target`; the history scans
    read every commit reachable from any branch or tag of the repository that holds ROOT."""
    commands = [
        (Path(gitleaks).name, [gitleaks, "dir", str(target), "--redact", "--no-banner"], None),
        (Path(trufflehog).name, [trufflehog, "filesystem", str(target), "--fail", "--no-update", "--no-verification", "--json"], None),
    ]
    if history:
        repo = Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], cwd=ROOT, text=True).strip())
        commands += [
            (Path(gitleaks).name + " (history)", [gitleaks, "git", ".", "--redact", "--no-banner", "--log-opts=--all"], repo),
            (Path(trufflehog).name + " (history)", [trufflehog, "git", "file://.", "--fail", "--no-update", "--no-verification", "--json"], repo),
        ]
    return commands


def run_scans(commands):
    leaked = False
    for label, command, cwd in commands:
        result = subprocess.run(command, capture_output=True, text=True, cwd=cwd)
        print(label + ": " + ("passed" if result.returncode == 0 else "FAILED"))
        if result.returncode:
            leaked = True
            # Do not print scanner matches, which can contain the secret itself.
            print("Review the source privately. Candidate values were not printed or verified over the network.")
    return int(leaked)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gitleaks", default=os.environ.get("GITLEAKS_EXE", str(ROOT / ".local/tools/gitleaks.exe") if (ROOT / ".local/tools/gitleaks.exe").is_file() else "gitleaks"))
    parser.add_argument("--trufflehog", default=os.environ.get("TRUFFLEHOG_EXE", str(ROOT / ".local/tools/trufflehog.exe") if (ROOT / ".local/tools/trufflehog.exe").is_file() else "trufflehog"))
    parser.add_argument("--history", action="store_true", help="also scan every commit of every branch and tag")
    args = parser.parse_args()
    # The history scans run in the repository's top folder, so a scanner given as a relative path is made absolute.
    gitleaks, trufflehog = (str(Path(exe).resolve()) if Path(exe).is_file() else exe for exe in (args.gitleaks, args.trufflehog))
    paths = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).split(b"\0")
    prefix = subprocess.check_output(["git", "rev-parse", "--show-prefix"], cwd=ROOT, text=True).strip()
    if not any(paths):
        raise SystemExit("Stage the reviewed source files before scanning.")
    with tempfile.TemporaryDirectory(prefix="artegra-source-scan-") as directory:
        target = Path(directory).resolve()
        for name in paths:
            if not name:
                continue
            relative = Path(name.decode())
            destination = (target / relative).resolve()
            if not destination.is_relative_to(target):
                raise ValueError("Invalid tracked path")
            source = ROOT / relative
            if source.is_symlink():
                raise ValueError("Symlinks need explicit review")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(subprocess.check_output(["git", "show", ":" + prefix + relative.as_posix()], cwd=ROOT))
        return run_scans(scan_commands(target, gitleaks, trufflehog, args.history))


if __name__ == "__main__":
    raise SystemExit(main())
