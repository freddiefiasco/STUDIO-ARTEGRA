"""DEVELOPER BUILDS ONLY: the graphics-memory cap of the small-card emulation R5 (engine design ENGINE-DESIGN.md 8.1; gate G0g's
build-channel guard).

ComfyUI's --reserve-vram changes only its own model-management arithmetic: SAM masks, kornia tiles, the DAT and VAE tile
activations and the latent are not capped by it, so on a 32 GB card an emulated 12 GB run would quietly use the spare memory
instead of failing. For R5, an engine of a DEVELOPER build (service/build_channel.py says CHANNEL = 'dev', as
tools/make_dev_build.py writes it) that sees CU_DEV_VRAM_CAP_GB caps PyTorch's allocator on every visible card with
torch.cuda.set_per_process_memory_fraction(cap / total) when this module is imported, so an overshoot is an out-of-memory
error. The fraction caps PyTorch's allocator only; the CUDA context and driver allocations are outside it (R5 adds them from
the Windows counters). A RELEASE build ignores the variable and logs that it did.

Importing this module changes nothing unless a developer build sees the variable (G0d): it does not import torch, reads the
build channel from the app's service/build_channel.py as text (never imported; the engine inherits the user's environment,
so the channel is never taken from an environment variable), and adds no other module."""
import logging
import os
import re
from pathlib import Path

ENV = 'CU_DEV_VRAM_CAP_GB'
CHANNEL_FILE = Path(__file__).resolve().parents[2] / 'service' / 'build_channel.py'
_CHANNEL_RE = re.compile(r"^CHANNEL\s*=\s*'(dev|release)'\s*$", re.M)


def build_channel(path=None):
    """'dev' or 'release', read from the app's service/build_channel.py as text; 'release' when it cannot be read (a
    packaged build ships no such file, so it is always release)."""
    try:
        text = Path(path or CHANNEL_FILE).read_text(encoding='utf8')
    except (OSError, UnicodeDecodeError):
        return 'release'
    m = _CHANNEL_RE.search(text)
    return m.group(1) if m else 'release'


def apply(env=None, channel=None, torch_module=None, log=None):
    """Cap every visible card's PyTorch allocator at CU_DEV_VRAM_CAP_GB in a developer build. Returns the caps set
    ([{device, total_gb, fraction}]) or None (no variable, a release build, a bad value or no CUDA). Never raises."""
    env = os.environ if env is None else env
    raw = str(env.get(ENV, '') or '').strip()
    if not raw:
        return None
    log = log or logging.getLogger('claude_banded')
    ch = channel or build_channel()
    if ch != 'dev':
        log.warning('claude_banded: %s is set, but this is a release build, so it is ignored', ENV)
        return None
    try:
        cap = float(raw)
        if not cap > 0:
            raise ValueError(raw)
    except ValueError:
        log.warning('claude_banded: %s must be a number of GB (got %r); ignored', ENV, raw)
        return None
    try:
        if torch_module is None:
            import torch as torch_module
        if not torch_module.cuda.is_available():
            log.warning('claude_banded: %s is set, but no CUDA device is visible; ignored', ENV)
            return None
        out = []
        for i in range(torch_module.cuda.device_count()):
            total = torch_module.cuda.get_device_properties(i).total_memory / float(1 << 30)
            frac = min(1.0, cap / total)
            torch_module.cuda.set_per_process_memory_fraction(frac, i)
            out.append({'device': i, 'total_gb': round(total, 3), 'fraction': round(frac, 6)})
        log.warning('claude_banded: DEVELOPER BUILD: PyTorch capped at %.2f GB per card for the small-card emulation: %s',
                    cap, out)
        return out
    except Exception as e:        # the emulation is a developer convenience; it never stops the engine
        log.warning('claude_banded: the developer VRAM cap could not be set: %s', e)
        return None


CAPS = apply()
