"""Read-only platform checks shared by the app and runtime setup.

No GPU is initialized and no driver, registry value, or pagefile is changed.
"""
from __future__ import annotations

import ctypes
import platform
import re
import sys


PLATFORM_REQUIREMENT = (
    "Artegra Enhancer requires native x64 Windows 10 22H2 (build 19045) "
    "or Windows 11 22H2 (build 22621) or newer. "
    "32-bit Windows and Windows on ARM are not supported by this runtime."
)


def current_platform() -> dict:
    """Use native architecture, including when Python itself runs under emulation."""
    info = {"system": sys.platform, "architecture": platform.machine().lower(),
            "major": 0, "minor": 0, "build": 0, "product_type": 1}
    if sys.platform != "win32":
        return info
    version = sys.getwindowsversion()
    info.update(major=version.major, minor=version.minor, build=version.build,
                product_type=version.product_type)
    # SYSTEM_INFO is 48 bytes on x64 (36 on x86). The first WORD always contains
    # wProcessorArchitecture. The oversized buffer works for either process ABI.
    system_info = ctypes.create_string_buffer(64)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetNativeSystemInfo.argtypes = [ctypes.c_void_p]
    kernel.GetNativeSystemInfo.restype = None
    kernel.GetNativeSystemInfo(ctypes.byref(system_info))
    architecture = ctypes.c_ushort.from_buffer(system_info).value
    info["architecture"] = {9: "amd64", 12: "arm64", 0: "x86"}.get(architecture, "unknown")
    return info


def evaluate_platform(info: dict) -> dict:
    errors, warnings = [], []
    major, build = int(info.get("major", 0)), int(info.get("build", 0))
    architecture = str(info.get("architecture", "")).lower()
    supported_build = major >= 10 and (19045 <= build < 22000 or build >= 22621)
    if (info.get("system") != "win32" or architecture not in {"amd64", "x86_64"}
            or not supported_build):
        errors.append(PLATFORM_REQUIREMENT)
    elif info.get("product_type", 1) != 1:
        warnings.append("Windows Server is not qualified for this desktop application.")
    return {"errors": errors, "warnings": warnings, "platform": dict(info)}


def require_supported_platform() -> dict:
    report = evaluate_platform(current_platform())
    if report["errors"]:
        raise ValueError(" ".join(report["errors"]))
    return report


def evaluate_nvidia_driver(version: str) -> dict:
    """CUDA 13 family minimum, with a recommendation for the pinned 13.2 stack.

    A passing version check does not prove the wheel or a particular GPU works.
    Older 13.x-compatible drivers may lack newer PTX or driver features.
    """
    errors, warnings = [], []
    match = re.fullmatch(r"\s*(\d+)(?:\.\d+)+\s*", str(version))
    if not match:
        warnings.append("NVIDIA driver version could not be read. Install a current NVIDIA Studio driver if the engine fails to start.")
    elif int(match.group(1)) < 580:
        errors.append("The pinned CUDA 13.2 runtime needs NVIDIA driver 580 or newer. Install an NVIDIA Studio driver from branch 595 or newer and restart Windows.")
    elif int(match.group(1)) < 595:
        warnings.append("This driver relies on CUDA minor-version compatibility. NVIDIA driver branch 595 or newer is recommended for the pinned CUDA 13.2 runtime, especially if CUDA or PTX errors occur.")
    return {"errors": errors, "warnings": warnings}
