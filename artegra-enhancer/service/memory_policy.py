"""Quality-verified reference rendering and read-only Windows memory admission.

Unqualified low-memory transformations are withheld after an image-quality failure.
VRAM capacity alone does not establish a safe alternate rendering recipe.
"""
import ctypes
from dataclasses import asdict, dataclass
import os

GIB = 1 << 30
PROFILE_NAMES = ('auto', 'reference')
UNQUALIFIED_MESSAGE = ('Low-memory profiles are unavailable because image-quality qualification has not passed. '
                       'Use Auto or Reference; smaller NVIDIA cards remain unqualified.')

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
        return dict(asdict(self), changes_output=False,
                    qualification='reference graph; hardware qualification is separate', note='')

PROFILES = {
    'reference': MemoryProfile('reference', 1024, 1024, 512, 2, False, 0.8),
}


def choose_profile(total_gb, requested='auto'):
    """Keep the verified recipe at every capacity; no silent experimental fallback."""
    if requested not in PROFILE_NAMES:
        raise ValueError(UNQUALIFIED_MESSAGE)
    return PROFILES['reference']


def _require_reference(profile):
    if profile != PROFILES['reference']:
        raise ValueError(UNQUALIFIED_MESSAGE)


def launch_flags(flags, profile):
    _require_reference(profile)
    return list(flags)


def apply_graph(graph, info, profile):
    _require_reference(profile)
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
    return {name + '_gb': getattr(status, name) / GIB for name in
            ('total_phys', 'avail_phys', 'commit_limit', 'commit_available')}

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

def admission_problem(need_gb, running_gb, cap_gb, memory, reusable_commit_gb=0.0):
    if sum(running_gb) + need_gb > cap_gb:
        return 'Waiting for memory: this image exceeds the available application memory budget.'
    if memory is None:
        return 'Waiting for memory: Windows memory availability could not be read.'
    # Leave room for Windows/UI. A pagefile can back commit, but cannot substitute this RAM headroom.
    physical_need = need_gb if running_gb else min(need_gb, 8.0)
    if memory['avail_phys_gb'] < physical_need + 4.0:
        return 'Waiting for memory: close other memory-heavy apps to free system RAM.'
    additional = max(0.0, need_gb - max(0.0, reusable_commit_gb))
    if memory['commit_available_gb'] < additional + 2.0:
        return ('Waiting for memory: Windows has insufficient commit headroom. Close other apps or enable '
                'a system-managed pagefile on a drive with free space.')
    return None
