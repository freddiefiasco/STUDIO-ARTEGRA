"""The window's pages, start-up, engine stop, out-of-memory retry and close prompt, driven end to end (Beta hardening).

Each test runs one scenario of tests/qa/drive_host.py in its own process: the real window, tab and service with the
demo engine, offscreen. Keys are sent as key events. The audit items each one guards are named in the tests.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / "tests" / "qa" / "drive_host.py"

pytest.importorskip("PySide6")
pytest.importorskip("PIL")


def drive(scenario, tmp_path, **env_extra):
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software", QSG_RENDER_LOOP="basic",
               CU_FAKE_STAGE_SECONDS="1.5", CU_FAKE_GPUS="1", CU_LIVE_PREVIEW="off")
    for name in [k for k in env if k.startswith(("CU_FAST", "CU_SPLIT", "CU_FAKE_FAULT"))]:
        env.pop(name)
    if os.name == "nt":
        env["QT_QPA_FONTDIR"] = str(Path(os.environ["SystemRoot"]) / "Fonts")
    env.update(env_extra)
    result = subprocess.run([sys.executable, "-B", str(DRIVER), scenario, str(tmp_path / "state")], cwd=ROOT, env=env,
                            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=400)
    out = result.stdout + result.stderr
    match = re.search(r"^FOUND (.*)$", result.stdout, re.M)
    assert match and result.returncode == 0, out[-4000:]
    return json.loads(match.group(1))


def test_settings_and_about_are_modal(tmp_path):
    """AUD-02: behind Settings or About no key reaches the workspace, Tab stays out of it and Esc closes the page."""
    found = drive("modal", tmp_path)
    for page in ("settingsShown", "aboutShown"):
        assert found[page + "_workspace_visible"] is False
        assert found[page + "_keys_active"] is False
        assert found[page + "_changed"] == {}, found          # Ctrl+Enter, Delete, B, M, 0, 1, F6, ?, Ctrl+. did nothing
        assert found[page + "_tab_entered_workspace"] is False
        assert found[page + "_closed_by_escape"] is True
    assert found["dialog_opened_over_settings"] and found["dialog_closed_by_escape"] and found["settings_still_open_after_dialog"]
    assert found["focus_back_in_workspace"] is True
    assert found["ctrl_enter_starts_after_close"] is True       # the same key works once the page is closed


def test_opening_is_not_setup_and_an_engine_stop_is_not_install(tmp_path):
    """AUD-09: launch shows a plain opening state, no setup steps, no invented bar. AUD-10: an engine crash shows the
    engine's state with Try again, not '1 Install', and unfinished images carry on after Try again."""
    found = drive("states", tmp_path)
    assert found["opening_states"], "the opening state was never seen"
    for seen in found["opening_states"]:
        assert seen["heading"] == "Opening your workspace"
        assert seen["setupSteps"] is False and seen["installationProgress"] is False
        assert seen["setupWelcome"] is False and seen["setupCloseNote"] is False and seen["retryWorkspace"] is False
    after = found["after_crash"]
    assert after["setupHeading"] == {"visible": True, "text": "The image engine is not running"}
    assert after["setupSteps"]["visible"] is False and after["setupWelcome"]["visible"] is False
    assert after["installationProgress"]["visible"] is False and after["setupCloseNote"]["visible"] is False
    assert after["retryWorkspace"]["visible"] is True
    assert found["behind_setup_changed"] == {}, found          # Ctrl+Enter, Delete, M, 0, 1, B behind the setup page
    assert found["behind_setup_tab_entered_workspace"] is False
    assert found["status"] == "The image engine stopped unexpectedly. Choose Try again to start it."
    assert found["after_crash_workspace_visible"] is False
    assert found["resumed_and_finished"] is True


def test_out_of_memory_offers_save_gpu_memory_and_asks_first(tmp_path):
    """AUD-06: an out-of-memory failure no longer offers only the same request: Save GPU memory is offered, asked about
    first, turned on, and the image runs again."""
    found = drive("oom", tmp_path, CU_FAKE_FAULT="oom")
    assert "ran out of memory" in found["failed_text"]
    assert found["retry_visible"] and found["retry_label"] == "Try again with Save GPU memory"
    assert found["asked"] and found["question"] == "Try again with Save GPU memory?"
    assert found["profile_before"] == "auto" and found["profile_while_asking"] == "auto"
    assert found["profile_after"] == "balanced"
    assert found["second_run_done"] == 1


def test_close_prompt_goes_when_the_batch_ends(tmp_path):
    """AUD-37: the close prompt about running images does not stay up saying '0 of 0 done' once none run."""
    found = drive("close", tmp_path, CU_FAKE_STAGE_SECONDS="3")
    assert found["held"] and found["prompt_open"]
    assert found["prompt_open_after_end"] is False
    assert found["window_still_open"] is True


def test_shortcuts_sheet_lists_no_panels_key(tmp_path):
    """AUD-28: this window has no key for the panels (Tab moves focus), so the sheet does not list one."""
    found = drive("sheet", tmp_path)
    assert found["keys"] and not any("panels" in line for line in found["keys"])
    assert "Ctrl Enter: Start upscaling" in found["keys"]


def test_windows_reduced_motion_reaches_the_tab(tmp_path):
    """With Windows' Animation effects off, the Redux and Bolt marks and the tab take their reduced-motion path."""
    found = drive("motion", tmp_path)
    assert found == {"bridge": True, "tokens": True}


def test_reduced_motion_probe_answers_without_error():
    from host.app import windows_reduces_motion
    assert windows_reduces_motion() in (True, False)


def test_preferences_stay_with_their_state_folder(tmp_path):
    """AUD-38: the tab's remembered choices are written to this state folder's preferences.ini, and a second state
    folder starts from the defaults rather than from the first one's choices."""
    first = drive("prefs", tmp_path / "one")
    assert first["scale_at_start"] == 2 and first["ini_exists"] and first["ini_has_scale"]
    second = drive("prefs", tmp_path / "two")
    assert second["scale_at_start"] == 2, "a fresh state folder opened with another copy's scale"


def test_registry_preferences_move_once_into_the_state_folder(tmp_path):
    """An upgrade from a copy that kept them in the registry keeps them, and they leave the registry."""
    from PySide6.QtCore import QSettings
    from host.app import migrate_tab_preferences
    source = QSettings(str(tmp_path / "old.ini"), QSettings.Format.IniFormat)
    source.setValue("CreativeUpscalerTab/settings", '{"scale":4}')
    source.setValue("CreativeUpscalerTab/schema", "1")
    source.setValue("Other/kept", "yes")
    source.sync()
    target = tmp_path / "state" / "preferences.ini"
    target.parent.mkdir()
    assert migrate_tab_preferences(target, source) == 2
    moved = QSettings(str(target), QSettings.Format.IniFormat)
    assert moved.value("CreativeUpscalerTab/settings") == '{"scale":4}'
    again = QSettings(str(tmp_path / "old.ini"), QSettings.Format.IniFormat)
    assert again.value("CreativeUpscalerTab/settings") is None and again.value("Other/kept") == "yes"
    assert migrate_tab_preferences(target, again) == 0           # once only: the file now exists


def test_moved_preferences_are_read_back_by_the_tab(tmp_path):
    """The file the one-time move writes is the one the tab reads through QtCore Settings (JSON values with commas)."""
    found = drive("prefs_seeded", tmp_path)
    assert found["scale"] == 4 and found["protect"] == ["people", "vehicles"]
