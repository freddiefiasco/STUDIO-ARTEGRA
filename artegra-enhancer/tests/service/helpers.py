"""Synthetic image fixtures and independent output decoders for CPU-only tests."""
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zlib
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[2]


def tmpdir(prefix='cu-test-'):
    return Path(tempfile.mkdtemp(prefix=prefix))


# 5.0.2 build wave 3 (BUILD-WAVE-3 contracts.split_premise): the split tests choose their strip height from the planner at
# run time, so a refit of the memory model (the plan package) moves the height, not the test's premise.
SPLIT_WIDTH, SPLIT_FACTOR = 4000, 8
SPLIT_HEIGHTS = (64, 96, 128, 160, 192, 224, 256, 320, 384, 448, 512, 640, 768, 896, 1024)
DEV_PROVEN = {'ws128': 2000.0, 'pc64': 2000.0, 'pc48': 2000.0}     # the launcher's CU_TEST_DEV_CHANNEL sizes


def split_strip_height(cap=None, width=SPLIT_WIDTH, factor=SPLIT_FACTOR, heights=SPLIT_HEIGHTS, proven=None,
                       bxf_available=False, service=True):
    """The smallest strip height H of `heights` for which `factor`x of `width` x H is a Large-image plan that splits every pass
    at this memory cap (default: this computer's default cap, as a service started without a cap setting has it), planned
    now by the planner the service runs. service=True plans as the real-service tests' service does (a developer build's
    sizes `proven`, BXF_AVAILABLE as given, no start-up probe table); service=False plans with this process's planner as it
    stands (the in-process tests' own patches). None when no listed height splits every pass."""
    from contextlib import ExitStack
    from unittest import mock
    from engine import banded_plan, planner
    if cap is None:
        from service import settings
        cap = settings.default_ram_cap_gb()
    with ExitStack() as stack:
        if service:
            stack.enter_context(mock.patch.dict(banded_plan.BANDED_PROVEN_MP, proven or DEV_PROVEN))
            stack.enter_context(mock.patch.object(banded_plan, 'BXF_AVAILABLE', bool(bxf_available)))
            stack.enter_context(mock.patch.object(banded_plan, 'BXF_TABLE', None, create=True))
        for h in heights:
            p = planner.plan(width, h, factor, ram_cap_gb=float(cap))
            if p.ok and p.engine == 'banded' and p.stages and all(s.split_finish for s in p.stages):
                return h
    return None


def rmtree(p):
    shutil.rmtree(p, ignore_errors=True)


def gradient(w, h, seed=0):
    """Deterministic RGB test picture with structure (gradients + noise)."""
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:h, 0:w]
    a = np.stack([(x * 255 // max(1, w - 1)), (y * 255 // max(1, h - 1)), ((x + y) * 3) % 256], -1).astype(np.int32)
    a = np.clip(a + rng.integers(-12, 12, a.shape), 0, 255).astype(np.uint8)
    return a


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


# ---- independent readers for the service's own 16-bit encoders --------------------------------------------------------
def read_png16(path):
    data = Path(path).read_bytes()
    assert data[:8] == b'\x89PNG\r\n\x1a\n'
    pos, idat, chunks = 8, b'', {}
    while pos < len(data):
        n = struct.unpack('>I', data[pos:pos + 4])[0]
        tag = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + n]
        crc = struct.unpack('>I', data[pos + 8 + n:pos + 12 + n])[0]
        assert zlib.crc32(tag + body) & 0xFFFFFFFF == crc, tag
        if tag == b'IDAT':
            idat += body
        else:
            chunks[tag] = body
        pos += 12 + n
    w, h, depth, ctype = struct.unpack('>IIBB', chunks[b'IHDR'][:10])
    c = {2: 3, 6: 4}[ctype]
    raw = zlib.decompress(idat)
    stride = w * c * 2
    rows = np.frombuffer(raw, np.uint8).reshape(h, stride + 1)
    out = np.zeros((h, stride), np.uint8)
    prev = np.zeros(stride, np.uint8)
    for y in range(h):
        ft, line = rows[y, 0], rows[y, 1:]
        if ft == 0:
            cur = line
        elif ft == 2:
            cur = (line.astype(np.uint16) + prev).astype(np.uint8)
        else:
            raise AssertionError(f'unexpected filter {ft}')
        out[y] = cur
        prev = cur
    arr = out.view('>u2').reshape(h, w, c).astype(np.uint16)
    return arr, depth, chunks


def read_tiff16(path):
    data = Path(path).read_bytes()
    assert data[:4] == b'II*\x00'
    ifd = struct.unpack('<I', data[4:8])[0]
    n = struct.unpack('<H', data[ifd:ifd + 2])[0]
    tags = {}
    sizes = {2: 1, 3: 2, 4: 4, 7: 1}
    for i in range(n):
        tag, typ, cnt, val = struct.unpack('<HHI4s', data[ifd + 2 + 12 * i:ifd + 14 + 12 * i])
        size = sizes[typ] * cnt
        raw = val[:size] if size <= 4 else data[struct.unpack('<I', val)[0]:struct.unpack('<I', val)[0] + size]
        if typ == 3:
            tags[tag] = struct.unpack(f'<{cnt}H', raw)
        elif typ == 4:
            tags[tag] = struct.unpack(f'<{cnt}I', raw)
        else:
            tags[tag] = raw
    w, h, c = tags[256][0], tags[257][0], tags[277][0]
    rps = tags[278][0]
    rows = []
    for off, cnt in zip(tags[273], tags[279]):
        d = np.frombuffer(zlib.decompress(data[off:off + cnt]), '<u2').astype(np.int64)
        d = d.reshape(-1, w, c)
        if tags.get(317, (1,))[0] == 2:
            d = np.cumsum(d, axis=1) & 0xFFFF
        rows.append(d)
    arr = np.concatenate(rows, 0)[:h].astype(np.uint16)
    assert arr.shape[0] == h and rps >= 1
    return arr, tags



def write_image(path, arr, **save):
    Image.fromarray(arr).save(path, **save)
    return Path(path)

class ServiceProcess:
    """The real service with the fake engine, on the standalone's host contract: a per-run token file, this test
    process as the owning host, and a port in 18950-18969 chosen by the service. Same API as the final v5's driver."""

    def __init__(self, state, env=None, port=None, output_dir=None, settings=None, config=None, args=()):
        import secrets
        self.args = list(args)
        self.state = Path(state)
        self.state.mkdir(parents=True, exist_ok=True)
        self.port = port if port and 18950 <= port <= 18969 else 18950
        self.token = secrets.token_hex(32)
        self.token_path = self.state / ('session-' + secrets.token_hex(6) + '.token')
        self.token_path.write_text(self.token, encoding='utf8')
        base = {k: v for k, v in os.environ.items() if not k.startswith('CU_') and k not in ('PYTHONHOME', 'PYTHONPATH')}
        self.env = dict(base, PYTHONDONTWRITEBYTECODE='1', CU_OPEN_DRYRUN='1', **(env or {}))
        import PIL
        pkg_dirs = {str(Path(np.__file__).resolve().parents[1]), str(Path(PIL.__file__).resolve().parents[1])}
        self.env['PYTHONPATH'] = os.pathsep.join([str(REPO), *sorted(pkg_dirs)])
        self.proc = None
        if output_dir is not None or settings is not None:
            s = dict(settings or {})
            if output_dir is not None:
                s['output_dir'] = str(output_dir)
            (self.state / 'settings.json').write_text(json.dumps(s), encoding='utf8')
        cfg = dict(config or {})
        if output_dir is not None:
            cfg.setdefault('default_output_dir', str(output_dir))
        if cfg:
            (self.state / 'config.json').write_text(json.dumps(cfg), encoding='utf8')
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def start(self, timeout=60):
        self.out = open(self.state / f'service-stdout-{time.strftime("%H%M%S")}-{os.getpid()}.txt', 'ab')
        executable = getattr(sys, '_base_executable', sys.executable)
        self.proc = subprocess.Popen([executable, '-B', '-m', 'tests.qa.launch_service', '--state', str(self.state),
                                      '--port', str(self.port), '--fake-engine', '--host-pid', str(os.getpid()),
                                      '--token-file', str(self.token_path)] + self.args,
                                     cwd=str(REPO), env=self.env, stdout=self.out, stderr=subprocess.STDOUT)
        t0 = time.monotonic()
        while time.monotonic() - t0 < timeout:
            if self.proc.poll() is not None:
                raise AssertionError(f'service exited with {self.proc.returncode}; see {self.out.name}')
            try:
                info = json.loads((self.state / 'service.json').read_text(encoding='utf8'))
                if info.get('pid') == self.proc.pid:
                    self.port = info['port']
                    self.get('/health')
                    return self
            except (OSError, ValueError, KeyError) as e:
                self.last_start_error = e
            time.sleep(0.1)
        raise AssertionError('service did not become ready')

    def request(self, method, path, body=None, timeout=30, raw=False, auth=True):
        data = None if body is None else json.dumps(body).encode('utf8')
        headers = {'Content-Type': 'application/json'}
        if auth:
            headers['Authorization'] = 'Bearer ' + self.token
        req = urllib.request.Request(f'http://127.0.0.1:{self.port}{path}', data=data, method=method, headers=headers)
        try:
            with self.opener.open(req, timeout=timeout) as r:
                payload = r.read()
                return r.status, (payload if raw else json.loads(payload) if payload else None), dict(r.headers)
        except urllib.error.HTTPError as e:
            payload = e.read()
            return e.code, (payload if raw else json.loads(payload) if payload else None), dict(e.headers)

    def auth(self):
        return {'Authorization': 'Bearer ' + self.token}

    def get(self, path, **kw):
        return self.request('GET', path, **kw)

    def post(self, path, body=None, **kw):
        return self.request('POST', path, body if body is not None else {}, **kw)

    def wait_job(self, jid, pred, timeout=60, interval=0.1):
        t0 = time.monotonic()
        last = None
        while time.monotonic() - t0 < timeout:
            code, job, _ = self.get(f'/api/jobs/{jid}')
            last = job
            if code == 200 and pred(job):
                return job
            time.sleep(interval)
        raise AssertionError(f'timed out waiting for job {jid}: {json.dumps(last)[:3000]}')

    def shutdown(self, timeout=60):
        if self.proc is None or self.proc.poll() is not None:
            return self.proc.returncode if self.proc else None
        try:
            self.post('/api/shutdown', timeout=10)
        except OSError as e:
            self.last_shutdown_error = e
        try:
            return self.proc.wait(timeout)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(10)
            raise AssertionError('service did not exit after /api/shutdown')
        finally:
            self.out.close()

    def kill(self):
        if self.proc is not None and self.proc.poll() is None:
            self.proc.kill()
            self.proc.wait(10)
        if getattr(self, 'out', None):
            self.out.close()

    def log_lines(self):
        lines = []
        for p in sorted((self.state / 'logs').glob('app-*.jsonl')):
            for line in p.read_text(encoding='utf8').splitlines():
                if line.strip():
                    lines.append(json.loads(line))
        return lines

    def renders(self, gpu=0):
        p = self.state / 'workers' / f'gpu{gpu}' / 'fake-renders.jsonl'
        if not p.exists():
            return []
        return [json.loads(x) for x in p.read_text(encoding='utf8').splitlines() if x.strip()]
