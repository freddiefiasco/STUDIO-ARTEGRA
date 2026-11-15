"""The real isolated worker launcher must tolerate non-Latin Windows paths."""
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

from service.workers import comfy_command


def test_isolated_worker_logs_unicode_even_when_environment_requests_ascii(tmp_path):
    root = tmp_path / "Image tools \u6f14\u793a"
    root.mkdir()
    entry = root / "main.py"
    entry.write_text("import json,sys\nprint(json.dumps({'utf8':sys.flags.utf8_mode}))\nprint('Image tools \\u6f14\\u793a')\n", encoding="utf-8")
    config = SimpleNamespace(runtime_python=Path(sys.executable), comfy_main=entry, site_packages=root,
                             models_dir=tmp_path / "models")
    command = comfy_command(config, tmp_path, 12345, tmp_path / "models.yaml")
    result = subprocess.run(command, capture_output=True, env=dict(os.environ, PYTHONIOENCODING="ascii", PYTHONUTF8="0"), timeout=20)
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    lines = result.stdout.decode("utf-8").splitlines()
    assert json.loads(lines[0])["utf8"] == 1
    assert lines[1] == "Image tools \u6f14\u793a"
