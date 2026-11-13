"""A real authenticated service with a synthetic engine, isolated files and owned children.

The test service runs below normal priority. No model, desktop, or real GPU is used.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

import numpy as np
import PIL

from tests.service.helpers import REPO

TERMINAL = {"done", "failed", "cancelled", "stopped"}


def complete(job):
    return job["state"] in TERMINAL and all(i["state"] in TERMINAL for i in job["items"])


def wait_for(predicate, timeout=30, message="condition did not become true"):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(.05)
    raise AssertionError(message)


class ServiceProcess:
    def __init__(self, state, *, env=None, preferred_port=18950, output=None):
        self.state = Path(state)
        self.state.mkdir(parents=True, exist_ok=True)
        self.output = Path(output) if output else self.state.parent / "output"
        self.output.mkdir(parents=True, exist_ok=True)
        self.port = preferred_port
        self.token = secrets.token_hex(32)
        self.token_path = self.state / ("session-" + secrets.token_hex(6) + ".token")
        self.token_path.write_text(self.token, encoding="utf8")
        self.log_path = self.state / ("service-" + secrets.token_hex(4) + ".txt")
        (self.state / "config.json").write_text(json.dumps({"default_output_dir": str(self.output)}), encoding="utf8")
        self.env = dict(os.environ)
        for key in list(self.env):
            if key.startswith("CU_") or key in {"PYTHONHOME", "PYTHONPATH"}:
                self.env.pop(key, None)
        package_dirs = {str(Path(np.__file__).resolve().parents[1]), str(Path(PIL.__file__).resolve().parents[1])}
        self.env.update(PYTHONPATH=os.pathsep.join([str(REPO), *sorted(package_dirs)]),
                        PYTHONDONTWRITEBYTECODE="1", CU_FAKE_GPUS="1", CU_FAKE_STAGE_SECONDS="0.08",
                        CU_LIVE_PREVIEW="off", CU_OPEN_DRYRUN="1", CU_SHUTDOWN_GRACE_SECONDS="1",
                        OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
        self.env.update(env or {})
        self.process = None
        self.stream = None
        self.cleanup = None
        self.peak_bytes = None
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def start(self):
        # Start in the base interpreter so the listener is the retained process,
        # with only the test environment's numeric/image packages added explicitly.
        executable = getattr(sys, "_base_executable", sys.executable)
        args = [executable, "-B", "-m", "tests.qa.launch_service", "--state", str(self.state), "--config",
                str(self.state / "config.json"), "--host-pid", str(os.getpid()), "--token-file",
                str(self.token_path), "--port", str(self.port), "--fake-engine"]
        if os.name == "nt":
            from service.windows_job import WindowsJobProcess
            self.process = WindowsJobProcess(args, cwd=str(REPO), env=self.env, log_path=self.log_path,
                                             memory_limit_bytes=4 * 1024**3)
        else:
            self.stream = self.log_path.open("ab")
            self.process = subprocess.Popen(args, cwd=REPO, env=self.env, stdout=self.stream,
                                            stderr=subprocess.STDOUT, start_new_session=True)
        def ready():
            assert self.poll() is None, self.logs()
            try:
                record = json.loads((self.state / "service.json").read_text(encoding="utf8"))
                if record["pid"] != self.process.pid:
                    return False
                assert 18950 <= record["port"] <= 18969
                self.port = record["port"]
                return self.get("/health")[0] == 200
            except (OSError, ValueError, KeyError):
                return False
        wait_for(ready, timeout=30, message="service did not start: " + str(self.log_path))
        if os.name == "nt":
            assert self.process.assert_listener_owned(self.port, root_only=True)
        return self

    def poll(self):
        return self.process.poll_root() if os.name == "nt" else self.process.poll()

    def logs(self):
        return self.log_path.read_text(encoding="utf8", errors="replace")[-8000:]

    def request(self, method, path, body=None, *, auth=True, headers=None, raw=False):
        data = None if body is None else json.dumps(body).encode("utf8")
        request_headers = {"Content-Type": "application/json"}
        if auth:
            request_headers["Authorization"] = "Bearer " + self.token
        request_headers.update(headers or {})
        request = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data,
                                         method=method, headers=request_headers)
        try:
            response = self.opener.open(request, timeout=10)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            payload = response.read()
            return response.code, payload if raw else json.loads(payload), dict(response.headers)

    def get(self, path, **kwargs):
        return self.request("GET", path, **kwargs)

    def post(self, path, body=None, **kwargs):
        return self.request("POST", path, {} if body is None else body, **kwargs)

    def add(self, paths):
        code, data, _ = self.post("/api/inputs", {"paths": [str(p) for p in paths]})
        assert code == 200, data
        assert data["rejected"] == [], data
        return data["items"]

    def job(self, media_ids, settings=None, request_id=None):
        body = {"client_request_id": request_id or secrets.token_hex(16), "media_ids": media_ids,
                "settings": settings or {"scale": 2}}
        code, data, _ = self.post("/api/jobs", body)
        assert code in {200, 201}, data
        return data

    def wait_job(self, job_id, predicate=complete, timeout=60):
        last = None
        def check():
            nonlocal last
            assert self.poll() is None, self.logs()
            code, last, _ = self.get("/api/jobs/" + job_id)
            assert code == 200, last
            return last if predicate(last) else False
        try:
            return wait_for(check, timeout=timeout, message="job did not reach expected state")
        except AssertionError as error:
            raise AssertionError(f"{error}; last job={last}") from error

    def renders(self):
        return [json.loads(line) for path in sorted((self.state / "workers").glob("gpu*/fake-renders.jsonl"))
                for line in path.read_text(encoding="utf8").splitlines() if line.strip()]

    def wait_exit(self, timeout=30):
        wait_for(lambda: self.poll() is not None, timeout=timeout, message="service did not exit")
        return self.poll()

    def shutdown(self):
        if self.process is not None and self.poll() is None:
            code, _, _ = self.post("/api/shutdown")
            assert code == 200
            assert self.wait_exit() == 0, self.logs()
        assert not (self.state / "service.json").exists()
        return self.close()

    def close(self):
        if self.process is not None:
            if os.name == "nt":
                self.peak_bytes = self.process.limits().get("peak_job_memory_used")
                self.cleanup = self.process.close(timeout=5)
                assert self.cleanup["all_owned_processes_terminated"], self.cleanup
            else:
                try:
                    os.killpg(self.process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                self.process.wait(timeout=5)
                self.cleanup = {"all_owned_processes_terminated": True}
            self.process = None
        if self.stream:
            self.stream.close()
            self.stream = None
        self.token_path.unlink(missing_ok=True)
        return self.cleanup


def port_open(port):
    with socket.socket() as connection:
        connection.settimeout(.2)
        return connection.connect_ex(("127.0.0.1", port)) == 0
