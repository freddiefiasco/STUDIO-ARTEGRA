"""The interpreter that measures the halo half of a proof comparison (tools/proof/metrics measure, around the halo tools'
halo_metric), and the plain refusal when the halo half is asked for and cannot run (build wave 4, WP3P-5). Standard library
only, so the suite's own interpreter can decide before it measures anything.

The halo tools need their own packages (numpy, scipy, opencv, scikit-image), which the suite's interpreter does not have:
CU_HALO_PY names an interpreter that has them (a path, or a command such as 'py -3.12'), else the Windows launcher's Python
3.12 is tried. CU_HALO_TOOLS (the halo tools folder) asks for the halo half. When it is set and no interpreter with the
packages is found, halo_half raises HaloUnavailable in plain words: a run never passes on fidelity and seams alone while
its halo half was asked for. Without CU_HALO_TOOLS the halo half is left out by choice, and says so."""
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

PACKAGES = ('scipy', 'cv2', 'skimage')
PROBE = 'import ' + ', '.join(PACKAGES)
LEFT_OUT = 'CU_HALO_TOOLS is not set: the halo half is left out (fidelity and seams only)'


class HaloUnavailable(RuntimeError):
    """CU_HALO_TOOLS asks for the halo half and no interpreter with the halo tools' packages was found."""


def _cmd(value):
    return [value] if Path(value).is_file() else shlex.split(value)


def _has_packages(cmd, run):
    try:
        return run(cmd + ['-c', PROBE], capture_output=True, timeout=300).returncode == 0
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return False


def halo_python(env=None, run=subprocess.run, which=shutil.which, platform=sys.platform):
    """(command list or None, what was tried): CU_HALO_PY when it imports the halo packages, else the Windows launcher's
    Python 3.12 when it does, else None."""
    env = os.environ if env is None else env
    tried = []
    v = env.get('CU_HALO_PY')
    if v:
        cmd = _cmd(v)
        if _has_packages(cmd, run):
            return cmd, tried
        tried.append(f"CU_HALO_PY ({v}) does not import {', '.join(PACKAGES)}")
        return None, tried
    if platform == 'win32' and which('py'):
        if _has_packages(['py', '-3.12'], run):
            return ['py', '-3.12'], tried
        tried.append(f"the Windows launcher's Python 3.12 (py -3.12) is missing or does not import {', '.join(PACKAGES)}")
    else:
        tried.append('CU_HALO_PY is not set and there is no Windows launcher (py) to find a Python 3.12')
    return None, tried


def halo_half(env=None, **kw):
    """(halo tools folder, interpreter command) when CU_HALO_TOOLS is set and an interpreter with the packages is found;
    (None, None) when CU_HALO_TOOLS is not set (LEFT_OUT); HaloUnavailable when it is set and none is found."""
    env = os.environ if env is None else env
    halo = env.get('CU_HALO_TOOLS')
    if not halo:
        return None, None
    cmd, tried = halo_python(env, **kw)
    if cmd is None:
        raise HaloUnavailable(f"CU_HALO_TOOLS is set ({halo}), so the halo half must run, but no interpreter with the halo "
                              f"tools' packages ({', '.join(PACKAGES)}) was found: {'; '.join(tried)}. Set CU_HALO_PY to "
                              "one (a path, or a command such as 'py -3.12').")
    return halo, cmd
