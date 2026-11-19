"""Pure configuration validation; no downloads or runtime imports."""
from __future__ import annotations

import json
import os
from pathlib import Path

APP_NAME = "Artegra Enhancer"
ORGANIZATION = "Studio Artegra"
# The name and version a person sees. APP_NAME and ORGANIZATION stay as they were: they set the state folder,
# the single-instance name and the Qt settings, so an upgrade from an alpha keeps everything.
DISPLAY_NAME = "Artegra Enhancer (Beta)"
VERSION = "5.0.1-beta.1"
APP_ID = "{2B6628CA-E890-46BF-A894-E5D1E004707F}"
PORTS = range(18950, 18970)


def read_choices(path: Path) -> dict:
    if not path.exists():
        return {"models_dir": "", "output_dir": "", "runtime_dir": ""}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("The saved settings could not be read. Choose Repair installation to restore them.")
    return {key: str(data.get(key, "")) for key in ("models_dir", "output_dir", "runtime_dir")}


def service_configuration(choices: dict, *, demo: bool = False) -> dict:
    """Translate managed installation locations into the service's path contract."""
    output = Path(choices.get("output_dir") or "")
    if not choices.get("output_dir") or not output.is_dir() or not os.access(output, os.W_OK):
        raise ValueError("The output folder isn't available. Choose another save location in Settings.")
    if demo:
        return {"default_output_dir": str(output.resolve())}
    models = Path(choices.get("models_dir") or "")
    if not choices.get("models_dir") or not models.is_dir():
        raise ValueError("Some image tools are missing. Choose Repair installation to restore them.")
    runtime = Path(choices.get("runtime_dir") or "")
    if not choices.get("runtime_dir") or not runtime.is_dir():
        raise ValueError("The image tools aren't installed yet. Complete setup or choose Repair installation.")
    receipt = runtime / "runtime-receipt.json"
    try:
        info = json.loads(receipt.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("The image tools aren't set up correctly. Choose Repair installation to restore them.") from exc
    if not isinstance(info, dict) or info.get("schema") != 1 or info.get("installed") is not True:
        raise ValueError("The installation needs attention. Choose Repair installation to restore the image tools.")
    paths = {}
    for source, target, is_dir in (("python", "runtime_python", False), ("site_packages", "site_packages", True), ("comfy_main", "comfy_main", False)):
        value = info.get(source)
        if not isinstance(value, str) or not value:
            raise ValueError("The installation is incomplete. Choose Repair installation to finish it.")
        path = Path(value)
        path = (runtime / path).resolve() if not path.is_absolute() else path.resolve()
        if not (path.is_dir() if is_dir else path.is_file()):
            raise ValueError("Some image-tool files are missing. Choose Repair installation to restore them.")
        paths[target] = str(path)
    paths.update(models_dir=str(models.resolve()), claude_models_dir=str(models.resolve()),
                 vae_approx_dir=str(models.resolve() / "vae_approx"), default_output_dir=str(output.resolve()))
    return paths


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def validate_handshake(data: dict, child_pid: int) -> int:
    if not isinstance(data, dict) or data.get("pid") != child_pid:
        raise ValueError("The engine start record does not belong to this window.")
    port = data.get("port")
    if isinstance(port, bool) or not isinstance(port, int) or port not in PORTS:
        raise ValueError("The engine did not choose an allowed local connection.")
    return port
