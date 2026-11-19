"""Conservative window batching and read-only Windows memory safeguards.

Balanced retains the original tiles, weights and numerical options.
Hardware qualification is separate from selecting a memory profile.
"""
from copy import deepcopy
import ctypes
import math
from dataclasses import asdict, dataclass
import os

GIB = 1 << 30
PROFILE_NAMES = ('auto', 'reference', 'balanced')
UNQUALIFIED_MESSAGE = ('Choose Auto, Reference or Balanced. Compact and Minimum are unavailable because '
                       'image-quality qualification has not passed.')

@dataclass(frozen=True)
class MemoryProfile:
    name: str
    tile_px: int
    vae_tile: int
    dat_tile: int
    batch_windows: int
    offload: bool
    reserve_vram_gb: float

    def to_dict(self):
        return dict(asdict(self), changes_output=self.name != 'reference',
                    qualification='reference graph' if self.name == 'reference' else 'conservative memory profile; hardware qualification is separate',
                    note='' if self.name == 'reference' else
                    'Original tile sizes with sequential windows and low-VRAM loading. Results and speed may differ.')

PROFILES = {
    'reference': MemoryProfile('reference', 1024, 1024, 512, 2, False, 0.8),
    'balanced': MemoryProfile('balanced', 1024, 1024, 512, 1, True, 1.0),
}


def choose_profile(total_gb, requested='auto'):
    """Use sequential windows on cards up to 24 GiB; unknown capacity keeps Reference."""
    if requested not in PROFILE_NAMES:
        raise ValueError(UNQUALIFIED_MESSAGE)
    if requested != 'auto':
        return PROFILES[requested]
    try:
        total = 0.0 if isinstance(total_gb, bool) else float(total_gb)
    except (TypeError, ValueError, OverflowError):
        total = 0.0
    return PROFILES['balanced'] if math.isfinite(total) and 0 < total <= 24 else PROFILES['reference']


# Two-card Bolt (one image shared by two cards) was proven only on two identical desktop RTX 5090 cards with the
# original memory settings. Everywhere else a Bolt image runs on one card.
FAST_SHARE_CARD = 'NVIDIA GeForce RTX 5090'
FAST_SHARE_MIN_GB = 31.0


def fast_share_hardware(cards, enabled, requested='auto'):
    """True when a lone Bolt image may share the enabled cards: exactly two, both named exactly FAST_SHARE_CARD (a laptop
    card's name differs), the same total memory of at least FAST_SHARE_MIN_GB, and the original memory settings in effect
    for the shared engine (Auto on such cards, or Original settings chosen)."""
    try:
        wanted = sorted({int(g) for g in enabled})
    except (TypeError, ValueError):
        return False
    rows = {int(c.get('index')): c for c in cards or [] if c.get('index') is not None}
    if len(wanted) != 2 or any(g not in rows for g in wanted):
        return False
    pair = [rows[g] for g in wanted]
    if any(str(c.get('name') or '').strip() != FAST_SHARE_CARD for c in pair):
        return False
    try:
        totals = [float(c.get('mem_total_gb')) for c in pair]
    except (TypeError, ValueError):
        return False
    if not all(math.isfinite(v) for v in totals) or abs(totals[0] - totals[1]) > 0.5 or min(totals) < FAST_SHARE_MIN_GB:
        return False
    try:
        return choose_profile(min(totals), requested).name == 'reference'
    except ValueError:
        return False


def _require_profile(profile):
    if profile not in PROFILES.values():
        raise ValueError(UNQUALIFIED_MESSAGE)


def launch_flags(flags, profile):
    _require_profile(profile)
    result = list(flags)
    if profile.name == 'balanced':
        result[result.index('--reserve-vram') + 1] = '1.0'
        result.append('--lowvram')
    return result


def apply_graph(graph, info, profile):
    _require_profile(profile)
    if profile.name == 'reference':
        return graph, info
    graph, info = deepcopy(graph), deepcopy(info)
    for node in graph.values():
        if node['class_type'] == 'ClaudeSpotTiles':
            node['inputs']['batch_windows'] = 1
    info['spot_options'] = dict(info['spot_options'], batch_windows=1)
    return graph, info


def system_memory():
    """GiB physical/available commit now; ullAvailPageFile is NOT pagefile size."""
    if os.name != 'nt':
        return None
    class Status(ctypes.Structure):
        _fields_ = [('length', ctypes.c_uint32), ('load', ctypes.c_uint32)] + [
            (name, ctypes.c_uint64) for name in ('total_phys', 'avail_phys', 'commit_limit', 'commit_available',
                                               'total_virtual', 'avail_virtual', 'unused')]
    status = Status()
    status.length = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    out = {name + '_gb': getattr(status, name) / GIB for name in
           ('total_phys', 'avail_phys', 'commit_limit', 'commit_available')}
    out['commit_growth_gb'] = pagefile_growth_gb(out['total_phys_gb'], out['commit_limit_gb'])
    return out


PAGING_KEY = r'SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management'


def pagefile_growth_gb(total_phys_gb, commit_limit_gb, entries=None, free_gb=None, volume_gb=None):
    """GiB the page file can still grow by, so the commit Windows can grant beyond commit_available now. The commit limit
    counts the page file at its current size; a system-managed page file (the Windows default) grows when commit runs
    short, up to three times the RAM and an eighth of its drive, and a custom one up to its maximum. entries: the
    PagingFiles registry lines (read when None); free_gb and volume_gb: free space and size of the page file's drive (read
    when None). 0.0 when it cannot be told."""
    try:
        if entries is None:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, PAGING_KEY) as key:
                entries = list(winreg.QueryValueEx(key, 'PagingFiles')[0] or [])
        current = max(0.0, float(commit_limit_gb) - float(total_phys_gb))
        most = 0.0
        for line in entries:
            parts = str(line).split()
            if not parts:
                continue
            drive = parts[0][:2]
            managed = drive.startswith('?') or (len(parts) >= 3 and parts[1] == '0' and parts[2] == '0') or len(parts) == 1
            if not managed and len(parts) < 3:
                continue
            if free_gb is None or (managed and volume_gb is None):
                import shutil
                root = (os.environ.get('SystemDrive', 'C:') if drive.startswith('?') else drive) + '\\'
                usage = shutil.disk_usage(root)
                room = usage.free / GIB if free_gb is None else float(free_gb)
                volume = usage.total / GIB if volume_gb is None else float(volume_gb)
            else:
                room, volume = float(free_gb), (float(volume_gb) if volume_gb is not None else float('inf'))
            if managed:
                limit = min(3.0 * float(total_phys_gb), volume / 8.0)
            else:
                limit = float(parts[2]) / 1024.0            # custom: initial and maximum size in MB
            most = max(most, min(limit - current, room - 1.0))
        return max(0.0, most)
    except (OSError, ValueError, TypeError, ImportError):
        return 0.0

def process_private_gb(pid):
    """Current commit of this exact owned worker, never its historical peak."""
    if os.name != 'nt' or not pid:
        return 0.0
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD), ('faults', wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in ('peak_ws', 'ws', 'peak_pool_paged', 'pool_paged',
                                                'peak_pool_nonpaged', 'pool_nonpaged', 'pagefile',
                                                'peak_pagefile', 'private')]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x1000 | 0x10, False, int(pid))
    if not handle:
        return 0.0
    try:
        counter = Counters(); counter.cb = ctypes.sizeof(counter)
        query = ctypes.WinDLL('psapi').GetProcessMemoryInfo
        query.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
        return counter.private / GIB if query(handle, ctypes.byref(counter), counter.cb) else 0.0
    finally:
        kernel.CloseHandle(handle)

def idle_engines_to_stop(need_gb, running_gb, cap_gb, idle):
    """The idle engines to stop before an image starts: all of them when their committed memory (idle: [(engine, GiB)])
    plus the planned peaks running now and this image's would pass the cap, else none."""
    held = sum(float(gb or 0.0) for _, gb in idle)
    if held > 0 and sum(running_gb) + need_gb + held > cap_gb:
        return [w for w, _ in idle]
    return []


def admission_problem(need_gb, running_gb, cap_gb, memory, reusable_commit_gb=0.0):
    if sum(running_gb) + need_gb > cap_gb:
        if running_gb:
            return 'Waiting for memory: another image is using the memory this one needs. It starts when that one finishes.'
        return ('Waiting for memory: this image needs more memory than the app may use now. Queue it again at a smaller '
                'upscale.')
    if memory is None:
        return 'Waiting for memory: Windows memory availability could not be read.'
    # Leave room for Windows/UI. A pagefile can back commit, but cannot substitute this RAM headroom.
    physical_need = need_gb if running_gb else min(need_gb, 8.0)
    if memory['avail_phys_gb'] < physical_need + 4.0:
        return 'Waiting for memory: close other memory-heavy apps to free system RAM.'
    additional = max(0.0, need_gb - max(0.0, reusable_commit_gb))
    # the page file grows when commit runs short (system-managed, the Windows default), so its room to grow counts too
    if memory['commit_available_gb'] + float(memory.get('commit_growth_gb') or 0.0) < additional + 2.0:
        return ('Waiting for memory: Windows has insufficient commit headroom. Close other apps or enable '
                'a system-managed pagefile on a drive with free space.')
    return None
