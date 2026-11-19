"""Gate G6 (engine design section 2.3): file-backed planes add no commit. A child process runs inside a Windows Job whose
memory limit is far below the planes it maps, writes and reads them through the Large-image engine's paths, and must neither
hit the limit nor raise its private memory above `--private-max-mib`.

Paths exercised: numpy memmap 'w+' and 'r+' (band writes and whole reads), a numpy ufunc with out= a mapped plane, and,
where torch and scipy are installed (the worker runtime), torch.from_numpy on a mapped plane with an in-place op and
scipy.ndimage.label with output= an int32 mapped plane.

    python tools/gate_g6.py --dir <scratch folder on the work disk> [--job-mib 4096 --planes-gib 16 --private-max-mib 1024]
Prints one JSON line: {"pass": bool, ...}. Windows only."""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def child(d, planes_gib):
    import ctypes
    import ctypes.wintypes as W
    import numpy as np
    sys.path.insert(0, str(ROOT))
    from engine import planes as P

    class PMC(ctypes.Structure):
        _fields_ = [('cb', W.DWORD), ('PageFaultCount', W.DWORD), ('PeakWorkingSetSize', ctypes.c_size_t),
                    ('WorkingSetSize', ctypes.c_size_t), ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaPagedPoolUsage', ctypes.c_size_t), ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaNonPagedPoolUsage', ctypes.c_size_t), ('PagefileUsage', ctypes.c_size_t),
                    ('PeakPagefileUsage', ctypes.c_size_t), ('PrivateUsage', ctypes.c_size_t)]

    k32 = ctypes.WinDLL('kernel32', use_last_error=True)
    k32.GetCurrentProcess.restype = W.HANDLE
    k32.K32GetProcessMemoryInfo.argtypes = [W.HANDLE, ctypes.POINTER(PMC), W.DWORD]
    k32.K32GetProcessMemoryInfo.restype = W.BOOL

    def private():
        c = PMC()
        c.cb = ctypes.sizeof(PMC)
        if not k32.K32GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb):
            raise OSError(ctypes.get_last_error(), 'GetProcessMemoryInfo')
        return c.PrivateUsage, c.PeakPagefileUsage

    out = {'paths': []}
    width = 32000
    rows = max(288, int(planes_gib * (1 << 30) / 3 / (width * 3)))
    t0 = time.time()
    names = []
    for i in range(3):                                   # three u8 planes of H x 32000 x 3
        p = P.Plane.create(Path(d) / f'g6_{i}.plane', (rows, width, 3), 'u8', producer='g6')
        m = p.map('r+')
        for y in range(0, rows, 1152):
            m[y:y + 1152] = (i * 40 + y // 1152) % 256
        m.flush()
        del m
        names.append(p)
    out['paths'].append('memmap r+ band writes')
    a = names[0].map('r')
    b = names[1].map('r+')
    for y in range(0, rows, 2304):                       # ufunc out= a mapped plane
        np.add(a[y:y + 2304], 1, out=b[y:y + 2304], casting='unsafe')
    b.flush()
    out['paths'].append('ufunc out= mapped')
    s = 0
    for y in range(0, rows, 2304):                       # whole read through the map
        s += int(b[y:y + 2304, ::997, 0].sum())
    out['checksum'] = s
    del a, b
    out['paths'].append('memmap r whole read')
    try:
        import torch
        m = names[2].map('r+')
        t = torch.from_numpy(m)
        t.add_(1)
        m.flush()
        del t, m
        out['paths'].append('torch.from_numpy in-place on a mapped plane')
    except ImportError:
        pass
    try:
        from scipy import ndimage
        q = P.Plane.create(Path(d) / 'g6_lab.plane', (rows // 4, width, 1), 'i32', producer='g6')
        src = names[0].map('r')
        lab = q.map('r+')
        ndimage.label(np.asarray(src[:rows // 4, :, 0]) > 128, output=lab[..., 0])
        lab.flush()
        del lab, src
        out['paths'].append('scipy label output= int32 mapped')
    except ImportError:
        pass
    out['private_bytes'], out['peak_pagefile_bytes'] = private()
    out['plane_bytes'] = sum(p.nbytes for p in names)
    out['seconds'] = round(time.time() - t0, 1)
    print(json.dumps(out))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True)
    ap.add_argument('--job-mib', type=int, default=4096)
    ap.add_argument('--planes-gib', type=float, default=16.0)
    ap.add_argument('--private-max-mib', type=int, default=1024)
    ap.add_argument('--child', action='store_true')
    a = ap.parse_args(argv)
    if a.child:
        return child(a.dir, a.planes_gib)
    if os.name != 'nt':
        print(json.dumps({'pass': False, 'reason': 'Windows only'}))
        return 2
    sys.path.insert(0, str(ROOT))
    from service.windows_job import WindowsJobProcess
    d = Path(a.dir)
    d.mkdir(parents=True, exist_ok=True)
    log = d / 'g6-child.log'
    args = [sys.executable, '-B', str(Path(__file__).resolve()), '--child', '--dir', str(d), '--planes-gib', str(a.planes_gib)]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', OPENBLAS_NUM_THREADS='1')   # BLAS buffers are not what G6 measures
    proc = WindowsJobProcess(args, cwd=str(ROOT), env=env, log_path=log,
                             memory_limit_bytes=a.job_mib << 20)
    try:
        code = proc.wait(3600)
        limits = proc.limits()
    finally:
        proc.close(timeout=10)
    text = log.read_text(encoding='utf8', errors='replace') if log.exists() else ''
    res = None
    for line in text.splitlines():
        if line.startswith('{'):
            res = json.loads(line)
    for p in d.glob('g6_*.plane'):
        try:
            p.unlink()
        except OSError:
            pass
    ok = (code == 0 and res is not None and res['peak_pagefile_bytes'] <= (a.private_max_mib << 20)
          and res['plane_bytes'] > (a.job_mib << 20))
    print(json.dumps({'pass': bool(ok), 'exit_code': code, 'job_limit_mib': a.job_mib, 'planes_gib': a.planes_gib,
                      'private_max_mib': a.private_max_mib, 'child': res, 'job': limits,
                      'log_tail': None if ok else text[-1500:]}))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
