"""The uninstaller's quit path end to end: a running app window (demo engine, offscreen) is asked to quit through its
single-instance connection and closes by itself, with its service, well before any process would have to be ended."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from host import run_record

ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(os.name != "nt", reason="the app's process records use the Windows API")


def alive(pid):
    return run_record.identity(pid) is not None


def test_a_running_window_quits_gracefully_and_takes_its_engine_with_it(tmp_path):
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software", QSG_RENDER_LOOP="basic",
               CU_FAKE_STAGE_SECONDS="0.2")
    for key in [k for k in env if k.startswith("CU_") and k != "CU_FAKE_STAGE_SECONDS"]:
        env.pop(key)
    if os.name == "nt":
        env["QT_QPA_FONTDIR"] = str(Path(os.environ["SystemRoot"]) / "Fonts")
    log = (tmp_path / "host-output.txt").open("wb")
    host = subprocess.Popen([sys.executable, "-B", "-m", "host.app", "--demo", "--state", str(tmp_path)],
                            cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    state = (tmp_path / "demo").resolve()
    try:
        deadline = time.monotonic() + 90
        record = service = None
        while time.monotonic() < deadline and host.poll() is None:
            record = run_record.read(state)
            try:
                service = json.loads((state / "service.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                service = None
            if record and service and alive(service.get("pid", 0)):
                break
            time.sleep(0.2)
        assert record and service, (tmp_path / "host-output.txt").read_text(errors="replace")[-3000:]
        host_pid, service_pid = record["host"]["pid"], service["pid"]
        assert alive(host_pid) and alive(service_pid)

        started = time.monotonic()
        quit_code = subprocess.run([sys.executable, "-B", "-m", "host.app", "--quit-running", "--state", str(tmp_path),
                                    "--timeout", "30"], cwd=ROOT, env=env, timeout=120).returncode
        took = time.monotonic() - started
        assert quit_code == 0
        assert took < 20, f"the window did not quit by itself ({took:.1f} s); it had to be ended"
        host.wait(30)
        assert host.returncode != run_record.QUIT_EXIT_CODE
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline and alive(service_pid):
            time.sleep(0.2)
        assert not alive(host_pid) and not alive(service_pid)
        assert run_record.read(state) is None
    finally:
        if host.poll() is None:
            host.kill()
            host.wait(10)
        log.close()
