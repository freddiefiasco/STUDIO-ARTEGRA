"""Windows job implementation."""


from __future__ import annotations

import ctypes
import os
import socket
import struct
import subprocess
import threading
import time
from ctypes import wintypes as W
from pathlib import Path


class ProcessContainmentError(RuntimeError):
    pass


class SECURITY_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("nLength", W.DWORD), ("lpSecurityDescriptor", W.LPVOID), ("bInheritHandle", W.BOOL)]


class STARTUPINFO(ctypes.Structure):
    _fields_ = [("cb", W.DWORD), ("lpReserved", W.LPWSTR), ("lpDesktop", W.LPWSTR),
                ("lpTitle", W.LPWSTR), ("dwX", W.DWORD), ("dwY", W.DWORD),
                ("dwXSize", W.DWORD), ("dwYSize", W.DWORD), ("dwXCountChars", W.DWORD),
                ("dwYCountChars", W.DWORD), ("dwFillAttribute", W.DWORD),
                ("dwFlags", W.DWORD), ("wShowWindow", W.WORD), ("cbReserved2", W.WORD),
                ("lpReserved2", ctypes.POINTER(ctypes.c_ubyte)), ("hStdInput", W.HANDLE),
                ("hStdOutput", W.HANDLE), ("hStdError", W.HANDLE)]


class STARTUPINFOEX(ctypes.Structure):
    _fields_ = [("StartupInfo", STARTUPINFO), ("lpAttributeList", W.LPVOID)]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [("hProcess", W.HANDLE), ("hThread", W.HANDLE),
                ("dwProcessId", W.DWORD), ("dwThreadId", W.DWORD)]


class BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", W.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", W.DWORD),
                ("Affinity", ctypes.c_size_t), ("PriorityClass", W.DWORD), ("SchedulingClass", W.DWORD)]


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint64) for name in ("ReadOperationCount", "WriteOperationCount",
                "OtherOperationCount", "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]


class EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [("BasicLimitInformation", BASIC_LIMIT_INFORMATION), ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]


class BASIC_ACCOUNTING_INFORMATION(ctypes.Structure):
    _fields_ = [("TotalUserTime", ctypes.c_int64), ("TotalKernelTime", ctypes.c_int64),
                ("ThisPeriodTotalUserTime", ctypes.c_int64), ("ThisPeriodTotalKernelTime", ctypes.c_int64),
                ("TotalPageFaultCount", W.DWORD), ("TotalProcesses", W.DWORD),
                ("ActiveProcesses", W.DWORD), ("TotalTerminatedProcesses", W.DWORD)]


KILL_ON_JOB_CLOSE = 0x2000
LIMIT_JOB_MEMORY = 0x0200
FILE_APPEND_DATA = 0x0004
SYNCHRONIZE = 0x00100000
OPEN_ALWAYS = 4
STILL_ACTIVE = 259


def _api():
    if os.name != "nt":
        raise ProcessContainmentError("Contained launch requires Windows")
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    signatures = {
        "CreateJobObjectW": ([ctypes.POINTER(SECURITY_ATTRIBUTES), W.LPCWSTR], W.HANDLE),
        "SetInformationJobObject": ([W.HANDLE, ctypes.c_int, W.LPVOID, W.DWORD], W.BOOL),
        "QueryInformationJobObject": ([W.HANDLE, ctypes.c_int, W.LPVOID, W.DWORD, W.LPVOID], W.BOOL),
        "AssignProcessToJobObject": ([W.HANDLE, W.HANDLE], W.BOOL),
        "TerminateJobObject": ([W.HANDLE, W.UINT], W.BOOL),
        "TerminateProcess": ([W.HANDLE, W.UINT], W.BOOL),
        "ResumeThread": ([W.HANDLE], W.DWORD),
        "GetExitCodeProcess": ([W.HANDLE, ctypes.POINTER(W.DWORD)], W.BOOL),
        "WaitForSingleObject": ([W.HANDLE, W.DWORD], W.DWORD),
        "CloseHandle": ([W.HANDLE], W.BOOL),
        "CreateFileW": ([W.LPCWSTR, W.DWORD, W.DWORD, ctypes.POINTER(SECURITY_ATTRIBUTES), W.DWORD, W.DWORD, W.HANDLE], W.HANDLE),
        "InitializeProcThreadAttributeList": ([W.LPVOID, W.DWORD, W.DWORD, ctypes.POINTER(ctypes.c_size_t)], W.BOOL),
        "UpdateProcThreadAttribute": ([W.LPVOID, W.DWORD, ctypes.c_size_t, W.LPVOID, ctypes.c_size_t, W.LPVOID, W.LPVOID], W.BOOL),
        "DeleteProcThreadAttributeList": ([W.LPVOID], None),
        "CreateProcessW": ([W.LPCWSTR, W.LPWSTR, W.LPVOID, W.LPVOID, W.BOOL, W.DWORD, W.LPVOID,
                            W.LPCWSTR, ctypes.POINTER(STARTUPINFOEX), ctypes.POINTER(PROCESS_INFORMATION)], W.BOOL),
        "GetCurrentProcess": ([], W.HANDLE),
        "IsProcessInJob": ([W.HANDLE, W.HANDLE, ctypes.POINTER(W.BOOL)], W.BOOL),
        "OpenProcess": ([W.DWORD, W.BOOL, W.DWORD], W.HANDLE),
    }
    for name, (args, result) in signatures.items():
        getattr(api, name).argtypes = args
        getattr(api, name).restype = result
    return api


def _error(operation):
    code = ctypes.get_last_error()
    return ProcessContainmentError(f"{operation} failed: Windows error {code}: {ctypes.FormatError(code).strip()}")


def process_alive(pid):
    """True while a process with this pid exists (query-only handle; used by tests and diagnostics)."""
    api = _api()
    handle = api.OpenProcess(0x1000, False, int(pid))  
    if not handle:
        return False
    try:
        code = W.DWORD()
        if not api.GetExitCodeProcess(handle, ctypes.byref(code)):
            raise _error("GetExitCodeProcess")
        return code.value == STILL_ACTIVE
    finally:
        api.CloseHandle(handle)


def _set_limits(api, job, memory_limit_bytes):
    limits = EXTENDED_LIMIT_INFORMATION()
    limits.BasicLimitInformation.LimitFlags = KILL_ON_JOB_CLOSE
    if memory_limit_bytes:
        limits.BasicLimitInformation.LimitFlags |= LIMIT_JOB_MEMORY
        limits.JobMemoryLimit = int(memory_limit_bytes)
    if not api.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
        raise _error("SetInformationJobObject(KILL_ON_JOB_CLOSE, JobMemoryLimit)")


def _query_limits(api, job):
    info = EXTENDED_LIMIT_INFORMATION()
    if not api.QueryInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info), None):
        raise _error("QueryInformationJobObject(extended)")
    return {'kill_on_job_close': bool(info.BasicLimitInformation.LimitFlags & KILL_ON_JOB_CLOSE),
            'job_memory_limit': int(info.JobMemoryLimit) if info.BasicLimitInformation.LimitFlags & LIMIT_JOB_MEMORY else None,
            'peak_job_memory_used': int(info.PeakJobMemoryUsed)}


class SharedJob:
    """Parent Job for several contained processes: kill-on-close and one JobMemoryLimit for all of them together."""

    def __init__(self, memory_limit_bytes=None):
        self.api = _api()
        self._lock = threading.RLock()
        self.memory_limit_bytes = int(memory_limit_bytes) if memory_limit_bytes else None
        self.job = self.api.CreateJobObjectW(None, None)
        if not self.job:
            raise _error("CreateJobObjectW(shared)")
        try:
            _set_limits(self.api, self.job, self.memory_limit_bytes)
        except BaseException:
            self.close()
            raise

    def set_memory_limit(self, memory_limit_bytes):
        """Change the total cap (settings change); applies to the processes already inside at once."""
        with self._lock:
            if not self.job:
                raise ProcessContainmentError("The shared job is closed")
            _set_limits(self.api, self.job, memory_limit_bytes)
            self.memory_limit_bytes = int(memory_limit_bytes) if memory_limit_bytes else None

    def limits(self):
        with self._lock:
            return _query_limits(self.api, self.job) if self.job else {}

    def active_processes(self):
        with self._lock:
            if not self.job:
                return 0
            info = BASIC_ACCOUNTING_INFORMATION()
            if not self.api.QueryInformationJobObject(self.job, 1, ctypes.byref(info), ctypes.sizeof(info), None):
                raise _error("QueryInformationJobObject(shared)")
            return info.ActiveProcesses

    def assign(self, process_handle):
        with self._lock:
            if not self.job:
                raise ProcessContainmentError("The shared job is closed")
            if not self.api.AssignProcessToJobObject(self.job, process_handle):
                raise _error("AssignProcessToJobObject(shared parent job)")

    def close(self):
        """Close the parent job (kills anything still inside it)."""
        with self._lock:
            job, self.job = self.job, None
        if job:
            self.api.TerminateJobObject(job, 1)
            self.api.CloseHandle(job)


class WindowsJobProcess:
    def __init__(self, args, *, cwd, env, log_path, memory_limit_bytes=None, parent_job=None):
        self._lock = threading.RLock()
        if not args or not Path(args[0]).is_absolute():
            raise ProcessContainmentError("The owned executable must have an absolute path")
        self.api = _api()
        self.job = None
        self.process = None
        self.pid = None
        self.command = list(map(str, args))
        self.cleanup = None
        self.memory_limit_bytes = int(memory_limit_bytes) if memory_limit_bytes else None
        self.log_path = str(log_path)
        self.parent_job = parent_job
        self.nested_parent_job = W.BOOL()
        if not self.api.IsProcessInJob(self.api.GetCurrentProcess(), None, ctypes.byref(self.nested_parent_job)):
            raise _error("IsProcessInJob(parent)")
        self.job = self.api.CreateJobObjectW(None, None)
        if not self.job:
            raise _error("CreateJobObjectW")
        thread = None
        log = None
        null = None
        attributes = None
        attributes_initialized = False
        info = PROCESS_INFORMATION()
        try:
            _set_limits(self.api, self.job, self.memory_limit_bytes)
            security = SECURITY_ATTRIBUTES(ctypes.sizeof(SECURITY_ATTRIBUTES), None, True)
            
            log = self.api.CreateFileW(self.log_path, FILE_APPEND_DATA | SYNCHRONIZE, 3, ctypes.byref(security), OPEN_ALWAYS,
                                       0x80, None)
            if log == ctypes.c_void_p(-1).value:
                log = None
                raise _error("CreateFileW(owned log)")
            null = self.api.CreateFileW("NUL", 0x80000000, 3, ctypes.byref(security), 3, 0x80, None)
            if null == ctypes.c_void_p(-1).value:
                null = None
                raise _error("CreateFileW(NUL)")
            size = ctypes.c_size_t()
            self.api.InitializeProcThreadAttributeList(None, 1, 0, ctypes.byref(size))
            if not size.value:
                raise _error("InitializeProcThreadAttributeList(size)")
            attributes = ctypes.create_string_buffer(size.value)
            if not self.api.InitializeProcThreadAttributeList(attributes, 1, 0, ctypes.byref(size)):
                raise _error("InitializeProcThreadAttributeList")
            attributes_initialized = True
            handles = (W.HANDLE * 2)(log, null)
            if not self.api.UpdateProcThreadAttribute(attributes, 0, 0x20002, handles, ctypes.sizeof(handles), None, None):
                raise _error("UpdateProcThreadAttribute(HANDLE_LIST)")
            startup = STARTUPINFOEX()
            startup.StartupInfo.cb = ctypes.sizeof(startup)
            startup.StartupInfo.dwFlags = 0x100  
            startup.StartupInfo.hStdInput = null
            startup.StartupInfo.hStdOutput = log
            startup.StartupInfo.hStdError = log
            startup.lpAttributeList = ctypes.cast(attributes, W.LPVOID)
            command = ctypes.create_unicode_buffer(subprocess.list2cmdline(self.command))
            environment = ctypes.create_unicode_buffer("\0".join(f"{key}={value}" for key, value in
                sorted(env.items(), key=lambda item: item[0].upper())) + "\0\0")
            flags = 0x4 | 0x400 | 0x80000 | 0x08000000  
            if not self.api.CreateProcessW(self.command[0], command, None, None, True, flags,
                                          environment, str(cwd), ctypes.byref(startup), ctypes.byref(info)):
                raise _error("CreateProcessW(CREATE_SUSPENDED)")
            self.process, thread, self.pid = info.hProcess, info.hThread, info.dwProcessId
            if self.parent_job is not None:
                
                self.parent_job.assign(self.process)
            if not self.api.AssignProcessToJobObject(self.job, self.process):
                raise _error("AssignProcessToJobObject (enclosing job may reject nesting; child never resumed)")
            if self.api.ResumeThread(thread) == 0xFFFFFFFF:
                raise _error("ResumeThread")
        except BaseException:
            
            
            if info.hProcess and not self.process:
                self.process, self.pid = info.hProcess, info.dwProcessId
            if info.hThread and not thread:
                thread = info.hThread
            if self.process:
                self.api.TerminateProcess(self.process, 1)
            self.close()
            raise
        finally:
            if thread:
                self.api.CloseHandle(thread)
            if attributes_initialized:
                self.api.DeleteProcThreadAttributeList(attributes)
            for handle in (log, null):
                if handle:
                    self.api.CloseHandle(handle)

    def active_processes(self):
        with self._lock:
            if not self.job:
                return 0
            info = BASIC_ACCOUNTING_INFORMATION()
            if not self.api.QueryInformationJobObject(self.job, 1, ctypes.byref(info), ctypes.sizeof(info), None):
                raise _error("QueryInformationJobObject")
            return info.ActiveProcesses

    def limits(self):
        """Current extended limits (memory cap and peak use) of the owned job."""
        with self._lock:
            if not self.job:
                return {}
            return _query_limits(self.api, self.job)

    def poll_root(self):
        with self._lock:
            if not self.process:
                return self.cleanup.get("root_exit_code") if self.cleanup else None
            code = W.DWORD()
            if not self.api.GetExitCodeProcess(self.process, ctypes.byref(code)):
                raise _error("GetExitCodeProcess")
            return None if code.value == STILL_ACTIVE else code.value

    def wait(self, timeout):
        """Wait up to timeout seconds for the root process to exit; returns its exit code or None. Holds the handle lock
        while waiting (used for short helper commands only), so the handle cannot be closed during the wait."""
        with self._lock:
            if not self.process:
                return self.poll_root()
            self.api.WaitForSingleObject(self.process, max(0, int(timeout * 1000)))
            return self.poll_root()

    def assert_listener_owned(self, port, *, root_only=False):
        """Confirm a listening socket belongs to this job, including descendants.

        PID is used only to open a query handle for membership verification;
        all termination remains on the owned job and process handles.
        """
        tcp = ctypes.WinDLL("iphlpapi", use_last_error=True).GetExtendedTcpTable
        tcp.argtypes = [W.LPVOID, ctypes.POINTER(W.DWORD), W.BOOL, W.ULONG, ctypes.c_int, W.ULONG]
        tcp.restype = W.DWORD
        size = W.DWORD()
        result = tcp(None, ctypes.byref(size), False, socket.AF_INET, 3, 0)
        if result not in {0, 122}:
            raise ProcessContainmentError(f"GetExtendedTcpTable(size) failed: {result}")
        for _ in range(3):
            table = ctypes.create_string_buffer(size.value)
            result = tcp(table, ctypes.byref(size), False, socket.AF_INET, 3, 0)
            if result == 0:
                break
            if result != 122:
                raise ProcessContainmentError(f"GetExtendedTcpTable failed: {result}")
        else:
            raise ProcessContainmentError("TCP owner table kept changing; refusing an unverified listener")
        count = struct.unpack_from("<I", table.raw)[0]
        found = False
        for index in range(count):
            state, address, local_port, _, _, pid = struct.unpack_from("<6I", table.raw, 4 + index * 24)
            
            if socket.ntohs(local_port & 0xFFFF) != port:
                continue
            ip = socket.inet_ntoa(struct.pack("<I", address))
            if ip not in {"127.0.0.1", "0.0.0.0"}:
                continue
            handle = self.api.OpenProcess(0x1000, False, pid)  
            if not handle:
                raise _error("OpenProcess(listener query)")
            try:
                owned = W.BOOL()
                if not self.api.IsProcessInJob(handle, self.job, ctypes.byref(owned)):
                    raise _error("IsProcessInJob(listener)")
                if root_only and pid != self.pid:
                    raise ProcessContainmentError(f"Port {port} listener PID is not the exact owned root")
                if not owned.value or ip != "127.0.0.1":
                    raise ProcessContainmentError(f"Port {port} is occupied by a foreign or non-loopback listener; it will not be reused")
            finally:
                self.api.CloseHandle(handle)
            found = True
        return found

    def receipt(self):
        return {"root_pid": self.pid, "command": self.command, "created_suspended": True,
                "assigned_before_resume": True, "kill_on_job_close": True,
                "memory_limit_bytes": self.memory_limit_bytes,
                "job_handle_inherited": False, "inherited_handles": ["owned_log", "NUL"],
                "enclosing_job": bool(self.nested_parent_job.value), "breakaway_enabled": False,
                "shared_parent_job": self.parent_job is not None,
                "shared_memory_limit_bytes": self.parent_job.memory_limit_bytes if self.parent_job is not None else None}

    def close(self, timeout=10):
        """Kill the whole tree and close the handles; idempotent and safe from several threads at once (the second caller
        waits for the first and gets the same cleanup record)."""
        with self._lock:
            if self.cleanup is not None:
                return self.cleanup
            errors = []
            active = None
            root_code = None
            peak = None
            try:
                if self.job:
                    try:
                        peak = self.limits().get('peak_job_memory_used')
                    except ProcessContainmentError as error:
                        errors.append(str(error))
                    if not self.api.TerminateJobObject(self.job, 1):
                        errors.append(str(_error("TerminateJobObject")))
                    deadline = time.monotonic() + timeout
                    while True:
                        try:
                            active = self.active_processes()
                        except ProcessContainmentError as error:
                            errors.append(str(error))
                            break
                        if active == 0 or time.monotonic() >= deadline:
                            break
                        time.sleep(.025)
                if self.process:
                    try:
                        root_code = self.poll_root()
                    except ProcessContainmentError as error:
                        errors.append(str(error))
            finally:
                
                
                job, self.job = self.job, None
                process, self.process = self.process, None
                if job:
                    if not self.api.CloseHandle(job):
                        errors.append(str(_error("CloseHandle(job)")))
                if process:
                    self.api.CloseHandle(process)
            self.cleanup = {"all_owned_processes_terminated": active == 0 and not errors,
                            "active_processes_before_final_close": active,
                            "root_exit_code": root_code, "job_handle_closed": True,
                            "peak_job_memory_used": peak, "errors": errors}
            return self.cleanup

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def run_contained(args, *, timeout, log_path, cwd=None, env=None):
    """Run a short helper command inside its own kill-on-close job; returns (exit code or None on timeout, output text)."""
    log_path = Path(log_path)
    if log_path.exists():
        log_path.unlink()
    proc = WindowsJobProcess(args, cwd=cwd or str(log_path.parent), env=dict(env or os.environ), log_path=log_path)
    try:
        code = proc.wait(timeout)
    finally:
        proc.close(timeout=5)
    try:
        text = log_path.read_text(encoding='utf8', errors='replace')
    except OSError:
        text = ''
    return code, text
