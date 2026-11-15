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
