"""R7 (engine design 9.2): what an allocation on the graphics card costs in host commit, and the work drive's free space.

For each size (2, 8 and 16 GiB by default) the probe reads this process's PrivateUsage, the commit of the Windows Job it runs
in (JobObjectMemoryUsageInformation of the calling process's own Job; None when it is in none) and, where Windows has them,
its "GPU Process Memory" dedicated and shared usage; then allocates that many bytes on the card (torch.cuda, touched so
the pages exist), reads again while holding them, frees them (and empties torch's cache), and reads again. The CUDA
context's own cost is read first, from a one-byte allocation. Each row records the rises and the ratios rise / bytes
allocated: the commit-VRAM ratio that sets the memory model's V. Nothing passes or fails: it is a measurement. The work
drive's total and free bytes are recorded beside it (the 1 GP Large-image rows need 130 GB free there).

    <runtime python> -B -m tools.proof.r7 --out <r7.json> [--sizes 2,8,16] [--device 0] [--work <folder>] [--stub]

--stub replaces the card with host memory (a bytearray, touched), for tests and rehearsals without a card: its rows are
labelled 'stub' and say nothing about a card. Windows (ctypes); torch only without --stub."""
import argparse
import ctypes
import json
import os
import shutil
import sys
import time
from pathlib import Path

GIB = 1 << 30


def own_job_memory():
    """(commit, PeakJobMemoryUsed) bytes of the Job this process runs in, or (None, None) outside a Job or off Windows."""
    if sys.platform != 'win32':
        return None, None
    from tools.proof import sampler
    m = sampler.JOB_MEM()
    ok = sampler.k32.QueryInformationJobObject(None, 28, ctypes.byref(m), ctypes.sizeof(m), None)
    if not ok:
        return None, None
    return int(m.JobMemory), int(m.PeakJobMemoryUsed)


def private_bytes():
    if sys.platform != 'win32':
        return None
    from tools.proof import sampler
    m = sampler.proc_mem(os.getpid())
    return None if m is None else m['private']


class _Gpu:
    """This process's dedicated and shared GPU memory from the Windows counters, or None where they cannot be read."""

    def __init__(self):
        self.c = None
        if sys.platform == 'win32':
            try:
                from tools.proof import sampler
                self.c = sampler.GpuCounters()
            except OSError:
                self.c = None

    def read(self):
        if self.c is None:
            return None, None
        try:
            v = self.c.read()['proc'].get(str(os.getpid()))
        except OSError:
            return None, None
        return (None, None) if v is None else (int(v[0]), int(v[1]))

    def close(self):
        if self.c is not None:
            self.c.close()


def reading(gpu):
    job, peak = own_job_memory()
    ded, sh = gpu.read()
    return {'t': time.time(), 'private': private_bytes(), 'job_commit': job, 'job_peak': peak, 'gpu_dedicated': ded,
            'gpu_shared': sh}


def cuda_allocator(device=0):
    """(alloc(n) -> handle, free(handle), label): n bytes on the card, touched; freed with torch's cache emptied."""
    import torch

    def alloc(n):
        t = torch.empty(int(n), dtype=torch.uint8, device=f'cuda:{device}')
        t.fill_(1)
        torch.cuda.synchronize(device)
        return t

    def free(t):
        del t
        torch.cuda.synchronize(device)
        torch.cuda.empty_cache()
    return alloc, free, f'cuda:{device} ({torch.cuda.get_device_name(device)}, torch {torch.__version__})'


def stub_allocator():
    """Host memory in place of the card (tests and rehearsals): a touched bytearray."""
    def alloc(n):
        b = bytearray(int(n))
        for i in range(0, len(b), 4096):
            b[i] = 1
        return b

    def free(b):
        del b
    return alloc, free, 'stub (host memory, no card)'


def _delta(a, b, key):
    return None if a.get(key) is None or b.get(key) is None else b[key] - a[key]


def _ratio(d, n):
    return None if d is None or not n else round(d / n, 4)


def probe(sizes_bytes, alloc, free, work_dir=None, settle_s=1.0, label='', gpu=None):
    """The probe's record: the context row, one row per size, the work drive's space."""
    gpu = gpu or _Gpu()
    rec = {'format': 'cu-r7-1', 'label': label, 'pid': os.getpid(), 'started': time.time(), 'rows': []}
    try:
        r0 = reading(gpu)
        h = alloc(1)
        time.sleep(settle_s)
        r1 = reading(gpu)
        free(h)
        rec['context'] = {'before': r0, 'after': r1, 'private_rise': _delta(r0, r1, 'private'),
                          'job_commit_rise': _delta(r0, r1, 'job_commit')}
        for n in sizes_bytes:
            before = reading(gpu)
            h = alloc(n)
            time.sleep(settle_s)
            held = reading(gpu)
            free(h)
            h = None
            time.sleep(settle_s)
            after = reading(gpu)
            row = {'bytes': int(n), 'gib': round(n / GIB, 3), 'before': before, 'held': held, 'after': after}
            for k in ('private', 'job_commit', 'gpu_dedicated', 'gpu_shared'):
                row[f'{k}_rise'] = _delta(before, held, k)
                row[f'{k}_left_after_free'] = _delta(before, after, k)
                row[f'{k}_ratio'] = _ratio(row[f'{k}_rise'], n)
            rec['rows'].append(row)
    finally:
        gpu.close()
    if work_dir is not None:
        u = shutil.disk_usage(work_dir)
        rec['work_drive'] = {'path': str(work_dir), 'total_bytes': u.total, 'free_bytes': u.free,
                             'free_gb': round(u.free / 1e9, 1)}
    rec['ended'] = time.time()
    rec['unmeasured'] = sorted({k for r in rec['rows'] for k in ('private', 'job_commit') if r[f'{k}_rise'] is None})
    return rec


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--sizes', default=','.join(str(x) for x in (2, 8, 16)), help='GiB, comma separated')
    ap.add_argument('--sizes-mib', help='MiB, comma separated (tests)')
    ap.add_argument('--device', type=int, default=0)
    ap.add_argument('--work')
    ap.add_argument('--settle', type=float, default=1.0)
    ap.add_argument('--stub', action='store_true')
    a = ap.parse_args(argv)
    sizes = ([int(float(x) * (1 << 20)) for x in a.sizes_mib.split(',')] if a.sizes_mib
             else [int(float(x) * GIB) for x in a.sizes.split(',')])
    alloc, free, label = stub_allocator() if a.stub else cuda_allocator(a.device)
    rec = probe(sizes, alloc, free, a.work, a.settle, label)
    rec['stub'] = bool(a.stub)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(rec, indent=1), encoding='utf8')
    print(json.dumps({'rows': len(rec['rows']), 'unmeasured': rec['unmeasured'], 'stub': rec['stub']}))


if __name__ == '__main__':
    main()
