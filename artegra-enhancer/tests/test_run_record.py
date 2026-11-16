"""The run record and the uninstaller's quit path: only the app's own recorded processes, never by name."""
import hashlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

from host import run_record

windows_only = pytest.mark.skipif(os.name != "nt", reason="process identity uses the Windows API")


@windows_only
def test_this_process_is_identified_by_pid_creation_time_and_path():
    me = run_record.identity(os.getpid())
    assert me["pid"] == os.getpid() and me["created"] > 0
    assert Path(me["image"]).name.lower().startswith("python")
    assert run_record.matches(me)
    assert not run_record.matches(dict(me, created=me["created"] + 1))
    assert not run_record.matches(dict(me, image=me["image"] + ".other"))
    assert run_record.identity(0) is None


@windows_only
def test_the_record_is_written_atomically_and_removed_only_by_its_owner(tmp_path):
    data = run_record.write(tmp_path, tmp_path / "app", launcher_pid=os.getpid())
    assert run_record.record_path(tmp_path).is_file()
    assert data["host"]["pid"] == os.getpid()
    assert data["launcher"] is None          # this test runner is not the app's launcher
    assert run_record.read(tmp_path)["host"] == data["host"]
    foreign = dict(data, host=dict(data["host"], pid=data["host"]["pid"] + 1))
    run_record.record_path(tmp_path).write_text(__import__("json").dumps(foreign), encoding="utf-8")
    run_record.remove(tmp_path)
    assert run_record.record_path(tmp_path).is_file()
    run_record.write(tmp_path, tmp_path / "app")
    run_record.remove(tmp_path)
    assert not run_record.record_path(tmp_path).exists()


def test_the_connection_name_is_the_hosts_own_rule(tmp_path):
    state = tmp_path / "production"
    expected = "artegra-enhancer-" + hashlib.sha256(str(state).encode()).hexdigest()[:24]
    assert run_record.server_name(state) == expected
    source = (Path(__file__).resolve().parents[1] / "host" / "app.py").read_text(encoding="utf-8")
    assert 'server_name = "artegra-enhancer-" + hashlib.sha256(str(state).encode()).hexdigest()[:24]' in source


def test_nothing_recorded_means_nothing_to_close(tmp_path):
    assert run_record.quit_running([tmp_path / "production", tmp_path / "demo"], timeout=0.1) == 0


@windows_only
def test_a_stale_record_of_an_ended_process_is_ignored(tmp_path):
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    entry = run_record.identity(child.pid)
    child.wait()
    state = tmp_path / "production"
    state.mkdir()
    (state / "run").mkdir()
    (state / "run" / "host.json").write_text(__import__("json").dumps({"schema": 1, "host": entry, "launcher": None}), encoding="utf-8")
    assert run_record.quit_running([state], timeout=0.5) == 0


@windows_only
def test_a_recorded_process_that_does_not_quit_is_ended_and_nothing_else(tmp_path):
    keep = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    target = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        state = tmp_path / "production"
        (state / "run").mkdir(parents=True)
        record = {"schema": 1, "host": run_record.identity(target.pid), "launcher": None}
        (state / "run" / "host.json").write_text(__import__("json").dumps(record), encoding="utf-8")
        assert run_record.quit_running([state], timeout=0.5) == 0
        assert target.wait(10) == run_record.QUIT_EXIT_CODE
        assert keep.poll() is None
    finally:
        for p in (keep, target):
            if p.poll() is None:
                p.kill()
                p.wait(10)


@windows_only
def test_a_reused_pid_is_never_ended(tmp_path):
    other = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        state = tmp_path / "production"
        (state / "run").mkdir(parents=True)
        entry = dict(run_record.identity(other.pid), created=1)        # the same PID, another process
        (state / "run" / "host.json").write_text(__import__("json").dumps({"schema": 1, "host": entry}), encoding="utf-8")
        assert run_record.quit_running([state], timeout=0.2) == 0
        assert other.poll() is None
    finally:
        other.kill()
        other.wait(10)


def test_the_launcher_stays_quiet_for_the_quit_path():
    source = (Path(__file__).resolve().parents[1] / "installer" / "launcher.cs").read_text(encoding="utf-8")
    assert '"--quit-running"' in source and '"--uninstall-cleanup"' in source
    assert "result != 0x41E0" in source and run_record.QUIT_EXIT_CODE == 0x41E0
    assert 'EnvironmentVariables["ENHANCER_LAUNCHER_PID"]' in source


def test_the_host_answers_quit_on_its_single_instance_connection():
    source = (Path(__file__).resolve().parents[1] / "host" / "app.py").read_text(encoding="utf-8")
    assert "run_record.QUIT_MESSAGE" in source and '"quitForUninstall"' in source
    assert 'if argv and argv[0] == "--quit-running":' in source
    main_qml = (Path(__file__).resolve().parents[1] / "ui" / "qml" / "Main.qml").read_text(encoding="utf-8")
    assert "function quitForUninstall()" in main_qml
