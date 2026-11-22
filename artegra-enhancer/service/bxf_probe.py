"""The service's half of the start-up probe of the banded exact finish (gate G1u; engine design 2.4 and 2.10; BUILD-WAVE-3
contracts.g1u).

The banded exact finish (BXF) bands an op only where gate G1 measured it band-invariant on the same libraries and CPU class
(engine/bxf/g1.py). Which table applies is a fact about the ENGINE's runtime (its torch, numpy and scipy, the CPU capability
torch and numpy dispatch on, and the processor), not about the service's own Python. So the service:

1. reads the engine runtime's environment: engine/bxf/g1.environment() run by the runtime interpreter (-I -B -S, the
   runtime's site-packages and the app root on sys.path, CUDA hidden, inside a kill-on-close Job, with a timeout). The
   reading is cached in <state>/bxf/environment.json, keyed by the interpreter (its path, size and time), the runtime's
   site-packages and its torch, numpy and scipy distributions, and this computer's processor string, so a changed runtime or
   a state folder moved to another computer is read again;
2. loads the table the finish will load: g1.load(env=<that environment>, local=<state>/bxf/local-table.json if present,
   else ''), and assigns engine/banded_plan.BXF_TABLE (the table when it applies, else None, so BXF_AVAILABLE keeps its
   meaning) and BXF_TABLE_SOURCE ('committed', 'local', 'committed+local' or None) at start and after every change, before
   any Large-image plan is made; the runner re-plans its queued Large-image images after a change;
3. runs engine/bxf/selfprobe.py ONLY when no committed table applies to that environment (an exact match was measured by G1
   on that CPU class: this workstation and the render nodes match engine/bxf/g1_table.TABLES[1] and TABLES[2]), for the
   finish widths and the band budget of the images waiting, by path with the runtime interpreter, at below-normal priority,
   inside the engines' shared Job (its commit counts against the memory cap), never beside a running image (the runner's
   rule), killed at its deadline; its table is written to a part file and renamed only on exit 0, so a partial table is
   never read. Exit 2 (out of time) or 3 (failed, or over --cap-gib) leaves the plans at tier 3 with a plain reason, and
   no probe at that band budget runs again this session, whatever widths later images need.
Every engine start's environment carries CU_BXF_LOCAL_TABLE (engine/bxf/g1.LOCAL_TABLE_ENV): the local table the planner's
table used, else '' (local_table_env()), so the finish node in the worker loads the planner's table.

With the fake engine the environment read and the probe use stand-ins the tests control (TEST_ENVIRONMENT and TEST_PROBE,
set by tests and by tests/qa/launch_service.py only); without them G1u is off and nothing is assigned (today's behaviour).
Sizes and synthetic tables only in tests."""
import json
import math
import os
import platform
import subprocess
import sys
import threading
import time
from pathlib import Path

from engine import banded_plan
from engine.bxf import g1

LOCAL_TABLE_ENV = g1.LOCAL_TABLE_ENV          # 'CU_BXF_LOCAL_TABLE'
ENV_VERSION = 1
ENV_FILE = 'environment.json'
ENV_LOG = 'environment-read.log'
LOCAL_TABLE = 'local-table.json'
PROBE_PART = 'local-table.json.part'        # selfprobe.py writes <part>.tmp and renames it to <part>; the service renames
PROBE_LOG = 'probe.log'                     # <part> to LOCAL_TABLE on exit 0 only
ENV_TIMEOUT_S = 180.0                       # the runtime's cold torch import can take minutes
ENV_MARK = 'CU_G1_ENV '
BELOW_NORMAL_PRIORITY_CLASS = 0x4000

# The probe's time, an upper bound (fin-g1u-rt, wp/2-finish-dev-runs.json: 1,209 s for --width 14000 with 8,192 px, every
# registered height, on this workstation's CPU): seconds per px of probed width (8,192 px and each stage width) per band
# budget, times PROBE_SLOW for a slower processor, plus a fixed start-up; the service kills the probe at that deadline, so
# it is the honest upper bound the waiting image shows. Refit from the finish package's g1u_timings (BUILD-WAVE-3 finish item 4).
PROBE_S_PER_PX = 1209.0 / (8192 + 14000)
PROBE_SLOW = 3.0
PROBE_START_S = 120.0
PROBE_KILL_GRACE_S = 15.0                   # the probe's own --seconds is the deadline; the service kills it this much later
PROBE_POLL_S = 0.25
PROBE_SPARE_GB = 2.0                        # commit left to the service and Windows beside the probe (--cap-gib)

# Test stand-ins (fake engine only; set by tests and tests/qa/launch_service.py, never by the app itself):
TEST_ENVIRONMENT = None     # the engine environment: a dict, or a callable returning one (raise to fail the read)
TEST_PROBE = None           # the probe's command prefix in place of [<runtime python>, -I, -B, -S, <selfprobe.py>]

ENV_CODE = r'''
import json, sys
sys.path[:0] = [sys.argv[1], sys.argv[2]]
from engine.bxf import g1
print('CU_G1_ENV ' + json.dumps(g1.environment(), sort_keys=True), flush=True)
'''

# The state the service reports (the plan's figures and the item messages read it)
_STATE = {'local': ''}


def local_table_env():
    """The value of CU_BXF_LOCAL_TABLE for an engine started now: the local table the planner's table used, else ''."""
    return _STATE['local']


def app_root():
    return Path(__file__).resolve().parents[1]


def selfprobe_path():
    return app_root() / 'engine' / 'bxf' / 'selfprobe.py'


def runtime_key(cfg):
    """What the cached environment is keyed on: the interpreter (path, size, time), the site-packages folder and the torch,
    numpy and scipy distributions in it, and this computer's processor string."""
    py, site = Path(cfg.runtime_python), Path(cfg.site_packages)

    def stat(p):
        try:
            s = p.stat()
            return [int(s.st_size), int(s.st_mtime)]
        except OSError:
            return None
    dists = {}
    for name in ('torch', 'numpy', 'scipy'):
        try:
            dists[name] = sorted(x.name for x in site.glob(f'{name}-*.dist-info'))
        except OSError:
            dists[name] = []
    return {'version': ENV_VERSION, 'python': str(py), 'python_stat': stat(py), 'site_packages': str(site), 'dists': dists,
            'processor': platform.processor() or platform.machine()}


def _atomic_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f'.{os.getpid()}.tmp')
    tmp.write_text(json.dumps(obj, indent=1, sort_keys=True), encoding='utf8')
    os.replace(tmp, path)


def parse_environment(text):
    """The environment dict from the read's output (its last marked line), or None."""
    for line in reversed((text or '').splitlines()):
        if line.startswith(ENV_MARK):
            try:
                env = json.loads(line[len(ENV_MARK):])
            except ValueError:
                return None
            return env if isinstance(env, dict) and all(k in env for k in g1.ENV_KEYS) else None
    return None


def env_command(cfg):
    return [str(cfg.runtime_python), '-I', '-B', '-S', '-c', ENV_CODE, str(cfg.site_packages), str(app_root())]


def child_env(extra=None):
    """The environment of the read and the probe: the service's, CUDA hidden, no bytecode written."""
    from service.workers import SECRET_ENV
    env = {k: v for k, v in os.environ.items() if k.upper() not in SECRET_ENV}
    env.update(CUDA_VISIBLE_DEVICES='', PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8')
    env.pop(LOCAL_TABLE_ENV, None)
    env.update(extra or {})
    return env


def moved_to_whole(table):
    """The ops a local table moved to whole: those it classes 'whole' that a committed table (G1's own classification)
    classes 'banded'. [] without a local table."""
    loc = getattr(table, 'local', None) if isinstance(table, g1.Vetoed) else (table if getattr(table, '_local', False) else None)
    if loc is None:
        return []
    banded = set()
    for t in g1.committed_tables():
        banded |= {op for op, v in (t.get('ops') or {}).items() if (v or {}).get('verdict') == 'banded'}
    return sorted(op for op, v in (loc.data.get('ops') or {}).items() if v.get('verdict') != 'banded' and op in banded)


def probe_seconds(widths, band_gbs):
    """The probe's deadline, seconds: an upper bound of its time for these stage widths and band budgets (see PROBE_S_PER_PX)."""
    px = 8192 + sum(int(w) for w in set(int(w) for w in widths) if int(w) != 8192)
    return PROBE_START_S + PROBE_SLOW * PROBE_S_PER_PX * px * max(1, len(set(band_gbs)))


def probe_minutes(widths, band_gbs):
    """The upper bound shown to the person: the deadline at which the service stops the probe, in whole minutes."""
    return int(math.ceil((probe_seconds(widths, band_gbs) + PROBE_KILL_GRACE_S) / 60.0))


class G1u:
    """The G1u state of one service: the engine environment, the table the planner counts, and the probe.

    start() reads the environment in a background thread (the cache makes it instant after the first start) and assigns the
    table; `ready` is set when that is done (an image's plan waits for it, bounded). refresh() loads the table again (after a
    probe) and calls on_change() when what the planner counts changed."""

    def __init__(self, cfg, log, fake=False):
        self.cfg, self.log, self.fake = cfg, log, bool(fake)
        self.dir = Path(cfg.state_dir) / 'bxf'
        self.env = None
        self.table = None
        self.source = None
        self.local = ''
        self.problem = None
        self.ready = threading.Event()
        self.lock = threading.RLock()
        self.on_change = None
        self.failed = {}                 # band_gb -> {'reason', 'widths'}: a probe at this band budget failed this session
        self.requested = {}              # band_gb -> widths a refused image asked to have probed
        self.proc = None                 # the running probe (WindowsJobProcess or Popen)
        self.probing = None              # {'widths', 'band_gb', 'deadline_s', 'started', 'cap_gib'} while a probe runs
        self._stop = threading.Event()

    # --- the environment and the table -------------------------------------------------------------------------------
    @property
    def enabled(self):
        """G1u runs for the real engine, and for the fake one only with the tests' stand-in environment."""
        return (not self.fake) or TEST_ENVIRONMENT is not None

    def start(self, background=True):
        if not self.enabled:
            self.ready.set()
            return None
        if not background:
            self._start_body()
            return None
        t = threading.Thread(target=self._start_body, name='bxf-g1u', daemon=True)
        t.start()
        return t

    def _start_body(self):
        changed = False
        try:
            changed = self.refresh(reason='start', notify=False)
        except Exception as e:           # G1u never stops the service: the plans count tier 3 (fail closed)
            self.problem = str(e)
            self.log.warn('bxf_g1u_failed', 'The Large-image engine could not read its runtime; its images use the whole '
                          'finish for now', data={'error': str(e)})
        finally:
            self.ready.set()
        if changed and self.on_change is not None:      # after `ready`: the re-plan plans without waiting for it
            try:
                self.on_change('start')
            except Exception as e:
                self.log.warn('bxf_replan_failed', 'The queued Large-image images could not be planned again',
                              data={'error': str(e)})

    def wait_ready(self, timeout=60.0):
        return self.ready.wait(timeout) if self.enabled else True

    def environment(self):
        """The engine runtime's environment (cached in the state folder; read again when the runtime key changes), or None
        when it cannot be read."""
        if self.fake:
            env = TEST_ENVIRONMENT() if callable(TEST_ENVIRONMENT) else TEST_ENVIRONMENT
            return dict(env) if isinstance(env, dict) else None
        key = runtime_key(self.cfg)
        path = self.dir / ENV_FILE
        try:
            rec = json.loads(path.read_text(encoding='utf8'))
            if isinstance(rec, dict) and rec.get('key') == key and isinstance(rec.get('environment'), dict):
                return rec['environment']
        except (OSError, ValueError):
            pass
        env, detail = self.read_environment()
        if env is None:
            self.log.warn('bxf_env_unread', 'The Large-image engine could not read its runtime; its images use the whole '
                          'finish for now', data=detail)
            return None
        _atomic_json(path, {'key': key, 'environment': env, 'read': time.strftime('%Y-%m-%dT%H:%M:%S')})
        self.log.info('bxf_env_read', 'Read the Large-image engine runtime', data={'environment': env,
                                                                                    'seconds': detail.get('seconds')})
        return env

    def read_environment(self):
        """(environment or None, detail): g1.environment() run by the runtime interpreter, CUDA hidden, with a timeout."""
        self.dir.mkdir(parents=True, exist_ok=True)
        args = env_command(self.cfg)
        t0 = time.monotonic()
        try:
            if os.name == 'nt':
                from service.windows_job import run_contained
                code, text = run_contained(args, timeout=ENV_TIMEOUT_S, log_path=self.dir / ENV_LOG, cwd=str(self.dir),
                                           env=child_env())
            else:
                r = subprocess.run(args, capture_output=True, text=True, timeout=ENV_TIMEOUT_S, env=child_env(),
                                   cwd=str(self.dir))
                code, text = r.returncode, (r.stdout or '') + (r.stderr or '')
        except (OSError, subprocess.SubprocessError, RuntimeError) as e:
            return None, {'error': str(e), 'seconds': round(time.monotonic() - t0, 1)}
        env = parse_environment(text) if code == 0 else None
        return env, {'exit_code': code, 'seconds': round(time.monotonic() - t0, 1), 'output': (text or '')[-1500:]}

    def local_path(self):
        p = self.dir / LOCAL_TABLE
        return str(p) if p.is_file() else ''

    def load(self, env):
        """(table or None, source, local path used): g1.load on the engine's environment with the local table if present;
        the table only when it applies (fail closed: None leaves BXF_AVAILABLE's meaning)."""
        local = self.local_path()
        t = g1.load(env=env, local=local)
        if not getattr(t, 'applies', False):
            return None, None, ''
        committed = any(g1.Table(x, env).applies for x in g1.committed_tables())
        if isinstance(t, g1.Vetoed):
            return t, 'committed+local', local
        if committed:
            return t, 'committed', ''
        t._local = True
        return t, 'local', local

    def committed_applies(self):
        env = self.env
        return env is not None and any(g1.Table(x, env).applies for x in g1.committed_tables())

    def refresh(self, reason='change', notify=True):
        """Read the environment (cached), load the table and assign it to the planner. Returns True when what the planner
        counts changed (and calls on_change then, unless notify is False)."""
        if not self.enabled:
            return False
        with self.lock:
            env = self.environment()
            self.env = env
            table, source, local = self.load(env) if env is not None else (None, None, '')
            before = (self.source, self.local, self._local_sha())
            self.table, self.source, self.local = table, source, local
            after = (source, local, self._local_sha())
            _STATE['local'] = local
            banded_plan.BXF_TABLE = table
            banded_plan.BXF_TABLE_SOURCE = source
            changed = before != after
        self.log.info('bxf_table', f'Large-image finish table: {source or "none applies (whole finish)"}',
                      data={'reason': reason, 'source': source, 'local': local, 'changed': changed,
                            'cpu_capability': (env or {}).get('cpu_capability'),
                            'committed_applies': self.committed_applies(), 'moved_to_whole': moved_to_whole(table)})
        if changed and notify and self.on_change is not None:
            self.on_change(reason)
        return changed

    def _local_sha(self):
        if not self.local:
            return None
        try:
            st = Path(self.local).stat()
            return (int(st.st_size), int(st.st_mtime_ns))
        except OSError:
            return None

    def cpu_capability(self):
        return (self.env or {}).get('cpu_capability')

    # --- the probe -----------------------------------------------------------------------------------------------------
    def local_coverage(self):
        """(widths, band budgets) the local table was probed at (sets; empty without one), read once per file version (the
        dispatcher asks at every tick)."""
        key = (self.local, self._local_sha())
        if getattr(self, '_coverage', (None, None))[0] != key:
            data = g1.read_local(self.local) if self.local else None
            cov = (set(), set())
            if data:
                cov = ({int(w) for w in data.get('widths') or []}, {float(b) for b in data.get('band_gb') or []})
            self._coverage = (key, cov)
        return self._coverage[1]

    def local_covers(self, widths, band_gb):
        """True when the local table was probed at every one of these widths and at this band budget."""
        have_w, have_b = self.local_coverage()
        return bool(have_w) and {int(w) for w in widths} <= have_w and float(band_gb) in have_b

    def probe_needed(self, widths, band_gb):
        """The probe must run before a Large-image image of these finish widths: G1u is on, the environment was read, no
        committed table applies to it, the local table does not cover these widths and budget, and no probe at this band
        budget failed this session (whatever its widths: a failed check never holds the queue again; mark_failed)."""
        widths = sorted({int(w) for w in widths or [] if int(w) > 0})
        if not (self.enabled and widths and self.ready.is_set() and self.env is not None):
            return False
        if self.committed_applies():
            return False
        if self.local_covers(widths, band_gb):
            return False
        return float(band_gb) not in self.failed

    def mark_failed(self, widths, band_gb, reason):
        """A probe of these widths at this band budget failed (out of time, over its cap, an error, or a table that does not
        apply here): no probe at this budget runs again this session, whatever widths a later image needs, so its images
        go on at tier 3 (a probe of more widths takes longer and holds more, and the same runtime gives the same table).
        The first reason is kept; the requests at this budget are dropped."""
        with self.lock:
            rec = self.failed.setdefault(float(band_gb), {'reason': reason, 'widths': []})
            rec['widths'] = sorted(set(rec['widths']) | {int(w) for w in widths})
            self.requested.pop(float(band_gb), None)

    def probe_widths(self, widths, band_gb):
        """The widths a probe for `widths` runs: these, every width a refused image asked for at this budget, and the
        widths the local table already covers (a later plan is probed again with the union of widths)."""
        have_w, have_b = self.local_coverage()
        have = {w for w in have_w if w != 8192} if float(band_gb) in have_b else set()
        return sorted({int(w) for w in widths} | set(self.requested.get(float(band_gb), ())) | have)

    def request(self, widths, band_gb):
        """A refused image asks for these widths to be probed (the runner starts the probe when nothing runs)."""
        with self.lock:
            self.requested.setdefault(float(band_gb), set()).update(int(w) for w in widths)

    def pending_request(self):
        """(widths, band_gb) a refused image asked for and the probe has not covered, or None."""
        with self.lock:
            for band, ws in sorted(self.requested.items()):
                if ws and self.probe_needed(sorted(ws), band):
                    return sorted(ws), band
        return None

    def probe_command(self, widths, band_gb, cap_gib, seconds, out):
        prefix = list(TEST_PROBE) if (self.fake and TEST_PROBE) else [str(self.cfg.runtime_python), '-I', '-B', '-S',
                                                                       str(selfprobe_path())]
        args = prefix + ['--out', str(out)]
        for w in widths:
            args += ['--width', str(int(w))]
        args += ['--band-gb', f'{float(band_gb):g}', '--site', str(self.cfg.site_packages), '--seconds',
                 str(int(math.ceil(seconds)))]
        if cap_gib is not None:
            args += ['--cap-gib', f'{float(cap_gib):.1f}']
        return args

    def run_probe(self, widths, band_gb, cap_gib=None, parent_job=None, abort=None):
        """Run the probe and wait for it (the caller's thread). Returns {'exit', 'reason', 'seconds', 'widths', 'band_gb',
        'table'}. exit: 0 (the table is written), 2 (out of time, or killed at the deadline), 3 (failed, or over the cap),
        None (stopped because the app is closing). The part file is renamed to the local table on exit 0 only."""
        widths = sorted({int(w) for w in widths})
        seconds = probe_seconds(widths, [band_gb])
        self.dir.mkdir(parents=True, exist_ok=True)
        part = self.dir / PROBE_PART
        for p in (part, part.with_name(part.name + '.tmp')):
            try:
                p.unlink()
            except FileNotFoundError:
                pass
        log_path = self.dir / PROBE_LOG
        try:
            log_path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass
        args = self.probe_command(widths, band_gb, cap_gib, seconds, part)
        rec = {'widths': widths, 'band_gb': float(band_gb), 'cap_gib': cap_gib, 'deadline_s': round(seconds, 1),
               'exit': None, 'reason': None, 'table': None}
        t0 = time.monotonic()
        with self.lock:
            self.probing = dict(rec, started=time.time())
        self.log.info('bxf_probe_start', 'Measuring how this computer\'s processor runs the Large-image finish',
                      data=dict(rec, command=[Path(a).name if os.sep in a or '/' in a else a for a in args]))
        try:
            code = self._run(args, seconds + PROBE_KILL_GRACE_S, log_path, cap_gib, parent_job, abort)
        finally:
            with self.lock:
                self.proc = None
                self.probing = None
        rec['seconds'] = round(time.monotonic() - t0, 1)
        text = ''
        try:
            text = log_path.read_text(encoding='utf8', errors='replace')
        except OSError:
            pass
        line = next((x for x in reversed(text.splitlines()) if x.startswith('selfprobe:')), '')
        if code == 'killed':
            rec['exit'] = 2
            rec['reason'] = PROBE_OUT_OF_TIME
            rec['detail'] = f'stopped at the deadline of {int(seconds + PROBE_KILL_GRACE_S)} s'
        elif code is None:
            rec['reason'] = 'stopped'
        else:
            rec['exit'] = int(code)
            rec['detail'] = line[:300]
            if code == 0:
                if part.is_file() and g1.read_local(part) is not None:
                    os.replace(part, self.dir / LOCAL_TABLE)
                    rec['table'] = str(self.dir / LOCAL_TABLE)
                else:
                    rec['exit'], rec['reason'] = 3, PROBE_FAILED
            elif code == 2:
                rec['reason'] = PROBE_OUT_OF_TIME
            elif 'over the cap' in line:
                rec['exit'], rec['reason'] = 3, PROBE_NO_MEMORY
            else:
                rec['exit'], rec['reason'] = 3, PROBE_FAILED
        for p in (part, part.with_name(part.name + '.tmp')):
            try:
                p.unlink()
            except OSError:
                pass
        if rec['exit'] in (2, 3):
            self.mark_failed(widths, band_gb, rec['reason'])
            self.log.warn('bxf_probe_failed', PROBE_FAILED_LOG.format(reason=rec['reason']), data=rec)
        elif rec['exit'] == 0:
            self.log.info('bxf_probe_done', 'This computer\'s processor was measured for the Large-image finish', data=rec)
        else:
            self.log.info('bxf_probe_stopped', 'The processor check was stopped because the app is closing', data=rec)
        return rec

    def _run(self, args, limit_s, log_path, cap_gib, parent_job, abort):
        """Start the probe and poll it (never a blocking wait, so stop() can kill it at once). Returns its exit code,
        'killed' at the deadline, or None when stopped."""
        env = child_env()
        proc = None
        if os.name == 'nt':
            from service.windows_job import WindowsJobProcess
            limit = int(float(cap_gib) * (1 << 30)) if cap_gib else None
            proc = WindowsJobProcess(args, cwd=str(self.dir), env=env, log_path=log_path, memory_limit_bytes=limit,
                                     parent_job=parent_job)
            try:
                import ctypes
                with proc._lock:
                    if proc.process:
                        ctypes.windll.kernel32.SetPriorityClass(ctypes.c_void_p(proc.process), BELOW_NORMAL_PRIORITY_CLASS)
            except (OSError, AttributeError):
                pass
            poll, kill = proc.poll_root, (lambda: proc.close(timeout=10))
        else:
            fh = open(log_path, 'ab')
            p = subprocess.Popen(args, cwd=str(self.dir), env=env, stdout=fh, stderr=subprocess.STDOUT)
            fh.close()
            proc = p
            poll, kill = p.poll, (lambda: (p.kill(), p.wait(10)))
        with self.lock:
            self.proc = proc
        end = time.monotonic() + float(limit_s)
        try:
            while True:
                if self._stop.is_set() or (abort is not None and abort()):
                    kill()
                    return None
                code = poll()
                if code is not None:
                    return None if self._stop.is_set() else code     # stop() may have ended it from another thread
                if time.monotonic() >= end:
                    kill()
                    return 'killed'
                time.sleep(PROBE_POLL_S)
        finally:
            if os.name == 'nt':
                proc.close(timeout=10)

    def forget_environment(self):
        """Drop the cached environment reading (the next refresh reads the runtime again). The fake engine's stand-in has
        no cache."""
        try:
            (self.dir / ENV_FILE).unlink()
        except OSError:
            pass

    def not_applied(self, widths, band_gb, rec):
        """A probe exited 0 but its table does not apply here or does not cover these widths: recorded as a failed probe
        (the images go on at tier 3; no second probe at this band budget this session)."""
        self.mark_failed(widths, band_gb, PROBE_NOT_APPLIED)
        self.log.warn('bxf_probe_failed', PROBE_FAILED_LOG.format(reason=PROBE_NOT_APPLIED),
                      data=dict(rec, reason=PROBE_NOT_APPLIED, environment=self.env, source=self.source))

    def stop(self):
        """The app is closing: stop a running probe now (its part file is never read)."""
        self._stop.set()
        with self.lock:
            proc = self.proc
        if proc is not None:
            try:
                proc.close(timeout=10) if hasattr(proc, 'close') else proc.kill()
            except Exception:
                pass

    def probe_commit_gb(self):
        """The commit the running probe may hold (its cap), counted by admission; 0.0 when none runs."""
        with self.lock:
            p = self.probing
        return float(p.get('cap_gib') or 0.0) if p else 0.0


PROBE_OUT_OF_TIME = 'it did not finish in time'
PROBE_NO_MEMORY = 'there was not enough free memory for it'
PROBE_FAILED = 'it stopped with an error'
PROBE_NOT_APPLIED = 'its result does not match this computer'
PROBE_FAILED_LOG = ("The processor check for the Large-image engine did not complete ({reason}). Large-image images on this "
                    'computer use the whole finish for now.')
PROBE_WAITING = ('Waiting for the processor check: the Large-image engine first measures this computer\'s processor. '
                 'This takes up to about {m} minutes.')
PROBE_WAITING_OTHERS = ('Waiting for the processor check: the Large-image engine first measures this computer\'s processor, '
                        'when the images before it are done. This takes up to about {m} minutes.')
PROBE_READING = 'Waiting for the Large-image engine to read its runtime.'
PROBE_REQUESTED = (' The app measures this computer\'s processor for the Large-image engine when it is free (up to about {m} '
                   'minutes); then queue the image again.')
