"""cu_proof: the phase-diff instrumentation (engine design 7.2). DEVELOPER ONLY: it lives under tools/proof, never under
node_pack, and ships in no release. The harness's own worker loads it as one more custom-nodes folder (tools/proof/harness.py
worker_command); the product's workers never do.

It adds no node to any graph and edits none: an added output node would change the order ComfyUI runs the classic's nodes in
(ComfyUI picks an available output node first). Instead, when the worker was started with CU_PROOF_DIR, it wraps two functions
at run time, for both executors alike:
- ComfyUI's execution.get_output_data (one call per node run): after the node's own function returns, each output the
  prompt's dump spec names (<CU_PROOF_DIR>/<prompt id>/spec.json, written by the harness before it submits the prompt) is
  written losslessly as a plane (engine/planes.py; float32, float16 and uint8 as they are, bfloat16 as its 16-bit pattern),
  and a Large-image node's plane output is recorded by its path. The node's outputs are returned as they came (the same
  objects; nothing is copied back or changed in place). Every node's start and end time is recorded, for the time per phase.
- comfy.controlnet.ControlNet.get_control: the first `calls` calls per sampler node and ControlNet instance are recorded
  by the sha256 of every output tensor, and the first `full_calls` of them with their values.
At each prompt's first node it records torch.get_num_threads(), the interop threads and the OMP/MKL environment.
Its own memory is recorded too, since the worker's Job counts it: every dump and ControlNet record carries host_bytes, the
bytes of the host buffers it allocated and held at once (a GPU tensor's CPU copy, a contiguous copy, the sha256 read buffer
of the plane write, the bytes hashed for a ControlNet output), and a dump carries commit_delta_bytes, the process's measured
private commit with the copies held less before them (Windows; None elsewhere). Planes are file-backed and add no commit.
A prompt without a spec is not touched. A failure inside the instrumentation never fails the prompt: it is recorded as an
error event, and the harness voids the run."""
import ctypes
import hashlib
import importlib
import importlib.util
import json
import os
import sys
import threading
import time
from pathlib import Path

_APP = Path(__file__).resolve().parents[4]
_LOCK = threading.RLock()
_STATE = {'root': None, 'specs': {}, 'env_done': set(), 'cn_ord': {}, 'cn_calls': {}, 'current': None}


def _planes():
    name = 'cu_proof_engine_planes'
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, _APP / 'engine' / 'planes.py')
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    return sys.modules[name]


def _dir(prompt_id):
    return Path(_STATE['root']) / str(prompt_id)


def _spec(prompt_id):
    with _LOCK:
        if prompt_id not in _STATE['specs']:
            p = _dir(prompt_id) / 'spec.json'
            _STATE['specs'][prompt_id] = json.loads(p.read_text(encoding='utf8')) if p.is_file() else None
        return _STATE['specs'][prompt_id]


def _event(prompt_id, ev):
    line = json.dumps(ev, sort_keys=True) + '\n'
    with _LOCK:
        with open(_dir(prompt_id) / 'events.jsonl', 'a', encoding='utf8') as f:
            f.write(line)


def _error(prompt_id, where, e):
    try:
        _event(prompt_id, {'type': 'error', 'where': where, 'message': f'{type(e).__name__}: {e}', 't': time.time()})
    except Exception:
        pass


def env_record():
    import torch
    keys = ('OMP_', 'MKL_', 'KMP_', 'OPENBLAS_', 'NUMEXPR_')
    rec = {'torch_threads': torch.get_num_threads(), 'interop_threads': torch.get_num_interop_threads(),
           'omp_mkl': {k: v for k, v in sorted(os.environ.items()) if k.upper().startswith(keys)},
           'torch': torch.__version__, 'cuda': torch.version.cuda, 'pid': os.getpid()}
    try:
        rec['cpu_capability'] = torch.backends.cpu.get_cpu_capability()
    except Exception:
        pass
    try:
        if torch.cuda.is_available():
            rec['device'] = torch.cuda.get_device_name(torch.cuda.current_device())
            rec['cudnn'] = torch.backends.cudnn.version()
            rec['tf32_matmul'] = bool(torch.backends.cuda.matmul.allow_tf32)
            rec['tf32_cudnn'] = bool(torch.backends.cudnn.allow_tf32)
    except Exception:
        pass
    return rec


SHA_CHUNK = 64 << 20            # engine/planes.Plane.data_sha256's read buffer (Plane.finish hashes the data with it)


class _PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
    _fields_ = [('cb', ctypes.c_uint32), ('PageFaultCount', ctypes.c_uint32)] + [
        (n, ctypes.c_size_t) for n in ('PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage',
                                       'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage', 'QuotaNonPagedPoolUsage',
                                       'PagefileUsage', 'PeakPagefileUsage', 'PrivateUsage')]


def private_bytes():
    """This process's private commit (PrivateUsage) in bytes on Windows, else None: what the worker's Job counts."""
    if os.name != 'nt':
        return None
    try:
        c = _PROCESS_MEMORY_COUNTERS_EX()
        c.cb = ctypes.sizeof(c)
        k32, psapi = ctypes.WinDLL('kernel32'), ctypes.WinDLL('psapi')
        k32.GetCurrentProcess.restype = ctypes.c_void_p
        psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32]
        if not psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb):
            return None
        return int(c.PrivateUsage)
    except Exception:
        return None


def _host_copy(t):
    """(the tensor on the CPU and contiguous, bytes the instrumentation allocated for it): a GPU tensor's CPU copy and a
    contiguous copy are new host buffers; a CPU tensor that is already contiguous is used in place (0 bytes)."""
    x = t.detach()
    n = 0
    if x.device.type != 'cpu':
        x = x.cpu()
        n += x.numel() * x.element_size()
    y = x.contiguous()
    if y.data_ptr() != x.data_ptr():
        n += y.numel() * y.element_size()
    return y, n


def _as_plane_array(t, role):
    """(numpy array H x W x C, tensor shape, torch dtype, host bytes allocated) of a tensor output, without changing it."""
    import torch
    shape = list(t.shape)
    x, host = _host_copy(t)
    dt = str(x.dtype)
    if x.dtype == torch.bfloat16:
        x = x.view(torch.int16)
    a = x.numpy()
    if dt == 'torch.bfloat16':
        a = a.view('<u2')
    if role.startswith('latent/'):
        if a.ndim != 4 or a.shape[0] != 1:
            raise ValueError(f'{role}: a latent must be [1, C, h, w], not {shape}')
        return a.reshape(a.shape[1] * a.shape[2], a.shape[3], 1), shape, dt, host
    if a.ndim == 4:
        if a.shape[0] != 1:
            raise ValueError(f'{role}: batch {a.shape[0]} (the proof runs one image)')
        return a[0], shape, dt, host
    if a.ndim == 3:
        if a.shape[0] != 1:
            raise ValueError(f'{role}: a mask batch of {a.shape[0]}')
        return a[0][..., None], shape, dt, host
    if a.ndim == 2:
        return a[..., None], shape, dt, host
    raise ValueError(f'{role}: cannot dump a tensor of shape {shape}')


def _dump(prompt_id, node, cls, out_idx, role, form, value):
    ev = {'type': 'dump', 'role': role, 'form': form, 'node': str(node), 'class': cls, 'output': int(out_idx)}
    if isinstance(value, dict) and 'samples' in value:
        value = value['samples']
    if hasattr(value, 'path') and hasattr(value, 'run_id') and not hasattr(value, 'detach'):
        p = _planes().Plane.open(value.path)
        ev.update(kind='plane', path=str(value.path), sha256=p.header.get('sha256'), produced=True, host_bytes=0)
        _event(prompt_id, ev)
        return
    before = private_bytes()
    a, shape, dt, host = _as_plane_array(value, role)
    held = private_bytes()
    planes = _planes()
    path = _dir(prompt_id) / 'dumps' / (role.replace('/', '_') + '.plane')
    p = planes.Plane.create(path, a.shape, a.dtype, producer='cu_proof', run_id=str(prompt_id),
                            inputs={'node': str(node), 'class': cls, 'output': int(out_idx), 'tensor_shape': shape,
                                    'torch_dtype': dt})
    for y in range(0, a.shape[0], 1024):
        p.write_rows(y, a[y:y + 1024])          # unbuffered file writes from the array's own memory
    # the instrumentation's own allocation (design 9.2 R1's memory mark counts the worker's Job, so it is recorded): the host
    # copies above, still alive while Plane.finish reads the plane back through its sha256 buffer
    ev['host_bytes'] = int(host) + min(SHA_CHUNK, int(a.nbytes))
    ev['commit_delta_bytes'] = None if before is None or held is None else int(held - before)
    ev.update(kind='plane', path=str(path), sha256=p.finish(), tensor_shape=shape, torch_dtype=dt)
    _event(prompt_id, ev)


def _after(prompt_id, unique_id, obj, res, t0, t1):
    spec = _spec(prompt_id)
    if spec is None:
        return
    nid = str(unique_id)
    cls = type(obj).__name__ if not isinstance(obj, type) else obj.__name__
    with _LOCK:
        first = prompt_id not in _STATE['env_done']
        _STATE['env_done'].add(prompt_id)
    if first:
        _event(prompt_id, dict(env_record(), type='env', t=t0))
    _event(prompt_id, {'type': 'node', 'node': nid, 'class': cls, 'phase': spec.get('phase_of_node', {}).get(nid),
                       't0': t0, 't1': t1})
    output, _ui, has_subgraph, pending = res
    if pending or has_subgraph:
        if spec['roles'].get(nid):
            _event(prompt_id, {'type': 'error', 'where': 'dump', 'node': nid,
                               'message': 'a named node returned a pending or expanded result; not dumped'})
        return
    for out_idx, role, form in spec['roles'].get(nid, []):
        try:
            _dump(prompt_id, nid, cls, out_idx, role, form, output[out_idx][0])
        except Exception as e:
            _error(prompt_id, f'dump {role}', e)


def _executing():
    try:
        from comfy_execution.utils import get_executing_context
        ctx = get_executing_context()
        if ctx is not None:
            return str(ctx.prompt_id), str(ctx.node_id)
    except Exception:
        pass
    return _STATE['current']


def _record_cn(control, out):
    cur = _executing()
    if not cur:
        return
    prompt_id, nid = cur
    spec = _spec(prompt_id)
    if spec is None:
        return
    cn = spec.get('cn') or {}
    sampler = (cn.get('nodes') or {}).get(nid)
    if sampler is None:
        return
    with _LOCK:
        ords = _STATE['cn_ord'].setdefault((prompt_id, nid), {})
        o = ords.setdefault(id(control), len(ords))
        key = (prompt_id, nid, o)
        n = _STATE['cn_calls'].get(key, 0)
        _STATE['cn_calls'][key] = n + 1
    if n >= int(cn.get('calls', 64)):
        return
    full = n < int(cn.get('full_calls', 4))
    rec = {'type': 'cn', 'role': f'cn/{sampler}/{o}', 'call': n, 'keys': [], 'sha256': [], 'dtypes': [], 'shapes': [],
           'files': [] if full else None, 'host_bytes': 0}
    d = _dir(prompt_id) / 'cn'
    for k in sorted(out or {}):
        vals = out[k] if isinstance(out[k], (list, tuple)) else [out[k]]
        for i, t in enumerate(vals):
            rec['keys'].append(f'{k}/{i}')
            if t is None:
                rec['sha256'].append(None)
                rec['dtypes'].append(None)
                rec['shapes'].append(None)
                if full:
                    rec['files'].append(None)
                continue
            x, host = _host_copy(t)
            import torch
            b = (x.view(torch.int16) if x.dtype == torch.bfloat16 else x).numpy().tobytes()
            rec['host_bytes'] = max(rec['host_bytes'], host + len(b))      # one output's buffers at a time
            rec['sha256'].append(hashlib.sha256(b).hexdigest())
            rec['dtypes'].append(str(t.dtype))
            rec['shapes'].append(list(t.shape))
            if full:
                d.mkdir(parents=True, exist_ok=True)
                f = d / f'{sampler}_{o}_{n}_{k}_{i}.bin'
                f.write_bytes(b)
                rec['files'].append(str(f))
    _event(prompt_id, rec)


def install(execution_module=None, controlnet_module=None, root=None):
    """Wrap execution.get_output_data and ControlNet.get_control (once). root: the dump folder (CU_PROOF_DIR); without it
    nothing is wrapped. Returns True when the instrumentation is active."""
    root = root if root is not None else os.environ.get('CU_PROOF_DIR')
    if not root:
        return False
    _STATE['root'] = str(root)
    ex = execution_module or importlib.import_module('execution')
    orig = ex.get_output_data
    if not getattr(orig, '_cu_proof', False):
        async def get_output_data(prompt_id, unique_id, obj, input_data_all, *args, **kwargs):
            prev = _STATE['current']
            _STATE['current'] = (str(prompt_id), str(unique_id))
            t0 = time.time()
            try:
                res = await orig(prompt_id, unique_id, obj, input_data_all, *args, **kwargs)
            finally:
                _STATE['current'] = prev
            t1 = time.time()
            try:
                _after(str(prompt_id), unique_id, obj, res, t0, t1)
            except Exception as e:
                _error(str(prompt_id), 'after', e)
            return res
        get_output_data._cu_proof = True
        get_output_data.__wrapped__ = orig
        ex.get_output_data = get_output_data
    cnm = controlnet_module or importlib.import_module('comfy.controlnet')
    cls = cnm.ControlNet
    g = cls.get_control
    if not getattr(g, '_cu_proof', False):
        def get_control(self, *args, **kwargs):
            out = g(self, *args, **kwargs)
            try:
                _record_cn(self, out)
            except Exception as e:
                cur = _executing()
                if cur:
                    _error(cur[0], 'controlnet', e)
            return out
        get_control._cu_proof = True
        get_control.__wrapped__ = g
        cls.get_control = get_control
    return True


class CUProofInfo:
    """The instrumentation's state and this worker's thread and OMP/MKL record, as text (not used by any proof graph)."""
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {}}
    RETURN_TYPES = ("STRING",)
    FUNCTION = "run"
    CATEGORY = "cu_proof"

    def run(self):
        return (json.dumps({'active': bool(_STATE['root']), **env_record()}, sort_keys=True),)


NODE_CLASS_MAPPINGS = {'CUProofInfo': CUProofInfo}
NODE_DISPLAY_NAME_MAPPINGS = {'CUProofInfo': 'CUProofInfo'}

if os.environ.get('CU_PROOF_DIR'):
    try:
        install()
    except Exception as _e:          # the worker still runs; the harness sees no events and voids the run
        print(f'[cu_proof] not installed: {_e}', flush=True)
