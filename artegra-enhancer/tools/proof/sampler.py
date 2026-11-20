"""The proof runs' 2 s sampler (engine design 9.2) and the Job counters, on Windows, through ctypes (no extra package).

Recorded every interval (one JSON line per sample):
- every Job it is given: its current commit and PeakJobMemoryUsed (JobObjectMemoryUsageInformation; the peak is also what the
  run record takes from the Job, not from the samples);
- every process it is given (the service, each worker, found through their Jobs): commit (PrivateUsage), working set, their
  peaks, and the I/O byte counters (disk read and write bytes, cumulative);
- the system: commit total and limit, available memory, the file cache (SystemCache), the page files in use, and the
  memory counters "Pages Input/sec" (hard-fault pages read), "Page Reads/sec" (hard-fault reads) and "Cache Bytes";
- dedicated and shared GPU memory per process and per adapter from the Windows counters "GPU Process Memory(*)" and
  "GPU Adapter Memory(*)" (nvidia-smi shows no shared use under WDDM): the S0b driver's counters, as it reads them;
- the phase the run is in, when a phase function is given (the time per phase comes from the instrumentation's timeline).
The probes and counters are the ones the earlier GPU safety check read, unchanged."""
import ctypes
import json
import re
import struct
import sys
import threading
import time
from ctypes import wintypes
from pathlib import Path

GIB = float(1 << 30)

if sys.platform == 'win32':
    k32 = ctypes.WinDLL('kernel32', use_last_error=True)
    psapi = ctypes.WinDLL('psapi', use_last_error=True)
    ntdll = ctypes.WinDLL('ntdll')
    k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k32.OpenProcess.restype = wintypes.HANDLE
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    k32.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
                                              ctypes.POINTER(wintypes.DWORD)]
    k32.QueryInformationJobObject.restype = wintypes.BOOL
    k32.GetProcessIoCounters.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
    k32.GetProcessIoCounters.restype = wintypes.BOOL
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
    psapi.GetPerformanceInfo.argtypes = [ctypes.c_void_p, wintypes.DWORD]
    ntdll.NtQuerySystemInformation.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong)]
    ntdll.NtQuerySystemInformation.restype = ctypes.c_long


class PMC_EX(ctypes.Structure):
    _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD), ('PeakWorkingSetSize', ctypes.c_size_t),
                ('WorkingSetSize', ctypes.c_size_t), ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                ('QuotaPagedPoolUsage', ctypes.c_size_t), ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                ('QuotaNonPagedPoolUsage', ctypes.c_size_t), ('PagefileUsage', ctypes.c_size_t),
                ('PeakPagefileUsage', ctypes.c_size_t), ('PrivateUsage', ctypes.c_size_t)]


class PERF(ctypes.Structure):
    _fields_ = [('cb', wintypes.DWORD), ('CommitTotal', ctypes.c_size_t), ('CommitLimit', ctypes.c_size_t),
                ('CommitPeak', ctypes.c_size_t), ('PhysicalTotal', ctypes.c_size_t), ('PhysicalAvailable', ctypes.c_size_t),
                ('SystemCache', ctypes.c_size_t), ('KernelTotal', ctypes.c_size_t), ('KernelPaged', ctypes.c_size_t),
                ('KernelNonpaged', ctypes.c_size_t), ('PageSize', ctypes.c_size_t), ('HandleCount', wintypes.DWORD),
                ('ProcessCount', wintypes.DWORD), ('ThreadCount', wintypes.DWORD)]


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [('ReadOperationCount', ctypes.c_uint64), ('WriteOperationCount', ctypes.c_uint64),
                ('OtherOperationCount', ctypes.c_uint64), ('ReadTransferCount', ctypes.c_uint64),
                ('WriteTransferCount', ctypes.c_uint64), ('OtherTransferCount', ctypes.c_uint64)]


class JOB_PIDS(ctypes.Structure):
    _fields_ = [('NumberOfAssignedProcesses', wintypes.DWORD), ('NumberOfProcessIdsInList', wintypes.DWORD),
                ('ProcessIdList', ctypes.c_size_t * 512)]


class JOB_MEM(ctypes.Structure):          # JobObjectMemoryUsageInformation (28)
    _fields_ = [('JobMemory', ctypes.c_uint64), ('PeakJobMemoryUsed', ctypes.c_uint64)]


def proc_mem(pid):
    h = k32.OpenProcess(0x1000 | 0x10, False, int(pid))
    if not h:
        return None
    try:
        c = PMC_EX()
        c.cb = ctypes.sizeof(c)
        if not psapi.GetProcessMemoryInfo(h, ctypes.byref(c), c.cb):
            return None
        return {'private': int(c.PrivateUsage), 'ws': int(c.WorkingSetSize), 'peak_commit': int(c.PeakPagefileUsage),
                'peak_ws': int(c.PeakWorkingSetSize), 'page_faults': int(c.PageFaultCount)}
    finally:
        k32.CloseHandle(h)


def io_counters(pid):
    h = k32.OpenProcess(0x1000, False, int(pid))
    if not h:
        return None
    try:
        c = IO_COUNTERS()
        if not k32.GetProcessIoCounters(h, ctypes.byref(c)):
            return None
        return {'read_bytes': int(c.ReadTransferCount), 'write_bytes': int(c.WriteTransferCount),
                'other_bytes': int(c.OtherTransferCount)}
    finally:
        k32.CloseHandle(h)


def job_pids(job):
    if not job:
        return []
    lst = JOB_PIDS()
    if not k32.QueryInformationJobObject(job, 3, ctypes.byref(lst), ctypes.sizeof(lst), None):
        return []
    return [int(x) for x in lst.ProcessIdList[:lst.NumberOfProcessIdsInList]]


def job_memory(job):
    """(current commit, PeakJobMemoryUsed) of a Job handle, bytes."""
    if not job:
        return None, None
    m = JOB_MEM()
    if not k32.QueryInformationJobObject(job, 28, ctypes.byref(m), ctypes.sizeof(m), None):
        return None, None
    return int(m.JobMemory), int(m.PeakJobMemoryUsed)


def perf():
    p = PERF()
    p.cb = ctypes.sizeof(p)
    if not psapi.GetPerformanceInfo(ctypes.byref(p), p.cb):
        return None
    ps = int(p.PageSize)
    return {'commit_total': p.CommitTotal * ps, 'commit_limit': p.CommitLimit * ps, 'commit_peak': p.CommitPeak * ps,
            'phys_total': p.PhysicalTotal * ps, 'phys_avail': p.PhysicalAvailable * ps, 'cache': p.SystemCache * ps}


def pagefiles(page_size=4096):
    """[(name, total, in use, peak)] bytes, from SystemPageFileInformation."""
    buf = ctypes.create_string_buffer(8192)
    ret = ctypes.c_ulong()
    if ntdll.NtQuerySystemInformation(18, buf, 8192, ctypes.byref(ret)) != 0:
        return []
    raw, off, out = buf.raw, 0, []
    base = ctypes.addressof(buf)
    while True:
        nxt, total, inuse, peak = struct.unpack_from('<IIII', raw, off)
        length = struct.unpack_from('<H', raw, off + 16)[0]
        ptr = struct.unpack_from('<Q', raw, off + 24)[0]
        name = ''
        if ptr and length and base <= ptr < base + 8192:
            name = raw[ptr - base:ptr - base + length].decode('utf-16-le', 'replace')
        out.append([name, total * page_size, inuse * page_size, peak * page_size])
        if nxt == 0 or len(out) > 16:
            break
        off += nxt
    return out


class PDH_FMT(ctypes.Structure):
    _fields_ = [('CStatus', wintypes.DWORD), ('pad', wintypes.DWORD), ('largeValue', ctypes.c_longlong)]


class PDH_FMT_D(ctypes.Structure):
    _fields_ = [('CStatus', wintypes.DWORD), ('pad', wintypes.DWORD), ('doubleValue', ctypes.c_double)]


class PDH_ITEM(ctypes.Structure):
    _fields_ = [('szName', wintypes.LPWSTR), ('FmtValue', PDH_FMT)]


class _Pdh:
    PATHS = {}

    def __init__(self):
        self.pdh = ctypes.WinDLL('pdh')
        self.pdh.PdhOpenQueryW.argtypes = [wintypes.LPCWSTR, ctypes.c_size_t, ctypes.POINTER(ctypes.c_void_p)]
        self.pdh.PdhAddEnglishCounterW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR, ctypes.c_size_t,
                                                   ctypes.POINTER(ctypes.c_void_p)]
        self.pdh.PdhCollectQueryData.argtypes = [ctypes.c_void_p]
        self.pdh.PdhCloseQuery.argtypes = [ctypes.c_void_p]
        self.pdh.PdhGetFormattedCounterArrayW.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
                                                          ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
        self.pdh.PdhGetFormattedCounterValue.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
                                                         ctypes.c_void_p]
        self.q, self.c, self.opened = None, {}, 0.0
        self.open()

    def open(self):
        if self.q:
            self.pdh.PdhCloseQuery(self.q)
        q = ctypes.c_void_p()
        r = self.pdh.PdhOpenQueryW(None, 0, ctypes.byref(q))
        if r != 0:
            raise OSError(f'PdhOpenQueryW {r & 0xffffffff:#x}')
        self.q, self.c = q, {}
        for k, p in self.PATHS.items():
            h = ctypes.c_void_p()
            r = self.pdh.PdhAddEnglishCounterW(q, p, 0, ctypes.byref(h))
            if r != 0:
                raise OSError(f'PdhAddEnglishCounterW {p}: {r & 0xffffffff:#x}')
            self.c[k] = h
        self.pdh.PdhCollectQueryData(q)
        self.opened = time.time()

    def collect(self):
        if self.pdh.PdhCollectQueryData(self.q) != 0:
            raise OSError('PdhCollectQueryData failed')

    def array(self, h):
        size, n = wintypes.DWORD(0), wintypes.DWORD(0)
        self.pdh.PdhGetFormattedCounterArrayW(h, 0x400, ctypes.byref(size), ctypes.byref(n), None)
        if not size.value:
            return {}
        buf = (ctypes.c_byte * size.value)()
        r = self.pdh.PdhGetFormattedCounterArrayW(h, 0x400, ctypes.byref(size), ctypes.byref(n), buf)
        if r != 0:
            raise OSError(f'PdhGetFormattedCounterArrayW {r & 0xffffffff:#x}')
        arr = ctypes.cast(buf, ctypes.POINTER(PDH_ITEM))
        return {arr[i].szName: int(arr[i].FmtValue.largeValue) for i in range(n.value) if arr[i].FmtValue.CStatus in (0, 1)}

    def value(self, h):
        v = PDH_FMT_D()
        r = self.pdh.PdhGetFormattedCounterValue(h, 0x200, None, ctypes.byref(v))
        return float(v.doubleValue) if r == 0 and v.CStatus in (0, 1) else None

    def close(self):
        if self.q:
            self.pdh.PdhCloseQuery(self.q)
            self.q = None


class GpuCounters(_Pdh):
    """"GPU Process Memory" and "GPU Adapter Memory" Dedicated and Shared Usage (bytes), every instance (S0b's counters)."""
    PATHS = {'p_ded': r'\GPU Process Memory(*)\Dedicated Usage', 'p_sh': r'\GPU Process Memory(*)\Shared Usage',
             'a_ded': r'\GPU Adapter Memory(*)\Dedicated Usage', 'a_sh': r'\GPU Adapter Memory(*)\Shared Usage'}
    INST = re.compile(r'pid_(\d+)_(luid_0x[0-9A-Fa-f]{8}_0x[0-9A-Fa-f]{8})_phys_(\d+)')
    AINST = re.compile(r'(luid_0x[0-9A-Fa-f]{8}_0x[0-9A-Fa-f]{8})_phys_(\d+)')

    def read(self):
        """{'proc': {pid: [dedicated, shared]} (summed over adapters), 'proc_adapter': {'pid/luid': [d, s]},
        'adapter': {luid: [dedicated, shared]}}"""
        if time.time() - self.opened > 60:          # new processes appear as new instances: reopen each minute
            self.open()
        self.collect()
        proc, pa, ad = {}, {}, {}
        for k, idx in (('p_ded', 0), ('p_sh', 1)):
            for name, v in self.array(self.c[k]).items():
                m = self.INST.fullmatch(name)
                if m:
                    proc.setdefault(m.group(1), [0, 0])[idx] += v
                    pa.setdefault(f'{m.group(1)}/{m.group(2)}', [0, 0])[idx] += v
        for k, idx in (('a_ded', 0), ('a_sh', 1)):
            for name, v in self.array(self.c[k]).items():
                m = self.AINST.fullmatch(name)
                if m:
                    ad.setdefault(m.group(1), [0, 0])[idx] += v
        return {'proc': proc, 'proc_adapter': pa, 'adapter': ad}


class MemoryCounters(_Pdh):
    """Hard faults (pages read in per second, reads per second) and the file cache, system-wide."""
    PATHS = {'pages_input_per_s': r'\Memory\Pages Input/sec', 'page_reads_per_s': r'\Memory\Page Reads/sec',
             'cache_bytes': r'\Memory\Cache Bytes'}

    def read(self):
        self.collect()
        return {k: self.value(h) for k, h in self.c.items()}


def sample(jobs=None, pids=None, gpu=None, mem=None, phase=None):
    """One sample. jobs: {name: Job handle}; pids: {role: pid} (plus every process inside the jobs)."""
    rec = {'t': time.time(), 'jobs': {}, 'procs': {}}
    roles = {str(p): r for r, p in (pids or {}).items() if p}
    for name, h in (jobs or {}).items():
        cur, peak = job_memory(h)
        rec['jobs'][name] = {'commit': cur, 'peak': peak}
        for p in job_pids(h):
            roles.setdefault(str(p), f'{name}:{p}')
    for p, role in roles.items():
        m = proc_mem(int(p))
        if m is None:
            continue
        rec['procs'][p] = dict(m, role=role, **(io_counters(int(p)) or {}))
    rec['perf'] = perf()
    rec['pagefile'] = pagefiles()
    if mem is not None:
        try:
            rec['mem'] = mem.read()
        except OSError as e:
            rec['mem_error'] = str(e)
    if gpu is not None:
        try:
            g = gpu.read()
            rec['gpu'] = {'proc': {p: v for p, v in g['proc'].items() if p in roles}, 'adapter': g['adapter']}
        except OSError as e:
            rec['gpu_error'] = str(e)
    if phase is not None:
        rec['phase'] = phase()
    return rec


class Sampler(threading.Thread):
    """Samples every interval_s into a JSON-lines file until stop(). pids: a callable returning {role: pid} (processes come
    and go: a worker restarts for the split finish)."""

    def __init__(self, out_path, interval_s=2.0, jobs=None, pids=None, gpu=True, mem=True, phase=None):
        super().__init__(daemon=True)
        self.out = Path(out_path)
        self.interval_s = float(interval_s)
        self.jobs = jobs or (lambda: {})
        self.pids = pids or (lambda: {})
        self.phase = phase
        self._halt = threading.Event()
        self.errors = []
        self.gpu = self._try(GpuCounters) if gpu else None
        self.mem = self._try(MemoryCounters) if mem else None

    def _try(self, cls):
        try:
            return cls()
        except OSError as e:
            self.errors.append(f'{cls.__name__}: {e}')
            return None

    def run(self):
        self.out.parent.mkdir(parents=True, exist_ok=True)
        with open(self.out, 'a', encoding='utf8') as f:
            while not self._halt.is_set():
                t0 = time.time()
                try:
                    jobs = self.jobs() if callable(self.jobs) else self.jobs
                    rec = sample(jobs, self.pids(), self.gpu, self.mem, self.phase)
                except Exception as e:          # a probe failure is recorded, never fatal to the run
                    rec = {'t': t0, 'error': f'{type(e).__name__}: {e}'}
                f.write(json.dumps(rec, sort_keys=True) + '\n')
                f.flush()
                self._halt.wait(max(0.0, self.interval_s - (time.time() - t0)))

    def stop(self, timeout=10):
        self._halt.set()
        self.join(timeout)
        for c in (self.gpu, self.mem):
            if c is not None:
                c.close()


def read_samples(path):
    return [json.loads(x) for x in Path(path).read_text(encoding='utf8').splitlines() if x.strip()]


def _peaks(rows):
    out = {'job_commit_gb': {}, 'proc_commit_gb': 0.0, 'proc_ws_gb': 0.0, 'gpu_dedicated_gb': 0.0, 'gpu_shared_gb': 0.0}
    for r in rows:
        for name, j in (r.get('jobs') or {}).items():
            if j.get('commit') is not None:
                out['job_commit_gb'][name] = max(out['job_commit_gb'].get(name, 0.0), round(j['commit'] / GIB, 2))
        procs = r.get('procs') or {}
        out['proc_commit_gb'] = max(out['proc_commit_gb'], round(sum(p.get('private', 0) for p in procs.values()) / GIB, 2))
        out['proc_ws_gb'] = max(out['proc_ws_gb'], round(sum(p.get('ws', 0) for p in procs.values()) / GIB, 2))
        g = (r.get('gpu') or {}).get('proc') or {}
        out['gpu_dedicated_gb'] = max(out['gpu_dedicated_gb'], round(sum(v[0] for v in g.values()) / GIB, 2))
        out['gpu_shared_gb'] = max(out['gpu_shared_gb'], round(sum(v[1] for v in g.values()) / GIB, 2))
    return out


def summarize(samples, timeline=None):
    """Peaks over the run and per phase (a sample belongs to the phase whose node was running at its time), and each
    phase's seconds from the timeline. The peak commit of a run is read from its Job (job_memory), not from these samples."""
    out = {'samples': len(samples), 'peak': _peaks(samples), 'per_phase': {}}
    for ev in timeline or []:
        ph = ev.get('phase') or 'other'
        rows = [s for s in samples if ev['t0'] <= s.get('t', -1) <= ev['t1']]
        cur = out['per_phase'].setdefault(ph, {'seconds': 0.0, 'rows': []})
        cur['seconds'] = round(cur['seconds'] + ev['t1'] - ev['t0'], 3)
        cur['rows'].extend(rows)
    for ph, cur in out['per_phase'].items():
        rows = cur.pop('rows')
        cur.update(_peaks(rows), samples=len(rows))
    return out
