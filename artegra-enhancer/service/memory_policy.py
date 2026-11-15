"""Conservative VRAM profiles and read-only Windows memory admission.

Profiles change tiling, so their output is not promised to match Reference.
The reference profile does not rewrite graphs or launch flags.
"""
from copy import deepcopy
import ctypes
from dataclasses import asdict, dataclass
import math
import os

GIB = 1 << 30
PROFILE_NAMES = ('auto', 'balanced', 'compact', 'minimum')

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
                    qualification='reference' if self.name == 'reference' else 'compatibility candidate',
                    note='' if self.name == 'reference' else
                    'Smaller tiles and sequential processing reduce graphics memory; output and speed may differ.')

PROFILES = {
    'reference': MemoryProfile('reference', 1024, 1024, 512, 2, False, 0.8),
    'balanced': MemoryProfile('balanced', 1024, 768, 512, 1, True, 1.0),
    'compact': MemoryProfile('compact', 768, 512, 384, 1, True, 1.0),
    'minimum': MemoryProfile('minimum', 512, 512, 256, 1, True, 1.0),
}
ORDER = tuple(PROFILES)

def choose_profile(total_gb, requested='auto'):
    if requested not in PROFILE_NAMES:
        raise ValueError('Memory profile must be auto, balanced, compact or minimum.')
    try:
        total = float(total_gb)
    except (TypeError, ValueError):
        total = 0.0
    if not math.isfinite(total):
        total = 0.0
    automatic = 'reference' if total >= 28 else 'balanced' if total >= 20 else 'compact' if total >= 14 else 'minimum'
    chosen = automatic if requested == 'auto' else ORDER[max(ORDER.index(automatic), ORDER.index(requested))]
    return PROFILES[chosen]

def launch_flags(flags, profile):
    result = list(flags)
    if not profile.offload:
        return result
    result[result.index('--reserve-vram') + 1] = str(profile.reserve_vram_gb)
    result += ['--lowvram', '--disable-smart-memory', '--cache-none']
    return result

def apply_graph(graph, info, profile):
    if profile.name == 'reference':
        return graph, info
    graph, info = deepcopy(graph), deepcopy(info)
    for node in graph.values():
        inputs, kind = node['inputs'], node['class_type']
        if kind == 'ClaudeSpotTiles':
            inputs.update(tile_px=min(inputs['tile_px'], profile.tile_px), batch_windows=1,
                          pag_fuse=False, cn_reuse=False, noise_prefetch=False, fp16_acc_scoped=False)
        elif kind in ('VAEEncodeTiled', 'VAEDecodeTiled'):
            inputs['tile_size'] = min(inputs['tile_size'], profile.vae_tile)
        elif kind == 'ClaudeUpscaleModelTiled':
            inputs['tile'] = min(inputs['tile'], profile.dat_tile)
        elif kind == 'ClaudeCannyTiled':
            inputs['tile'] = min(inputs['tile'], 1024)
    info['spot_options'] = dict(info['spot_options'], batch_windows=1, pag_fuse=False, cn_reuse=False,
                                noise_prefetch=False, fp16_acc_scoped=False)
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
