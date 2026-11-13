"""Runner implementation."""


import copy
import ctypes
import json
import os
import re
import shutil
import threading
import time
import uuid
from fractions import Fraction
from pathlib import Path

import numpy as np

from engine import controls, fast_recipe, graph_v5t, planner
from service import API_CONTRACT, SERVICE, VERSION, config, engine_options, gpu_policy, images, mask_graph
from service.comfy import ComfyError, ComfyUnavailable, ProgressTracker, PromptRejected, rejection_text
from service.errors import ApiError
from service.live import LiveBoard
from service.media import ram_refusal
from service.notify import BatchWatch, Notifier
from service.settings import SettingsError, env_float, probe_writable
from service.store import ACTIVE, REQUEST_ID_RE, TERMINAL, WAITING, Conflict, NotFound, StateError
from service.util import (atomic_write_json, canonical_json, link_or_copy, new_id, now_iso, same_record, sha256_bytes,
                          sha256_file)
from service.workers import MultiCardWorker, Worker, WorkerError, query_gpus

GB = 1 << 30
ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001


SILENT_NODES = {'ClaudeV4Finish': ('output', 15.0), 'ClaudeShadowToe': ('output', 1.0), 'VAEDecodeTiled': ('render', 4.0),
                'VAEEncodeTiled': ('render', 2.0), 'ImageUpscaleWithModel': ('render', 4.0), 'ClaudeUpscaleModelTiled': ('render', 6.0),
                'ClaudeProtectGate': ('input', 1.0), 'ClaudeCannyTiled': ('render', 1.0),
                'SAM3_Detect': ('input', 10.0), 'ImageScale': ('render', 0.5), 'ImageBlur': ('render', 0.5)}
FINISH_S_PER_MP = 0.6          
HEALTH_INTERVAL_S = 15.0


FAST_CHECK_WAIT_S = 20.0
SWEEP_INTERVAL_S = 6 * 3600.0
FAILED_WORK_KEEP_S = 3 * 86400.0
JOB_LOG_KEEP_S = 14 * 86400.0
PARTIAL_RE = re.compile(r'^\..+_cu\d+x\.[0-9a-f]{8}\.partial\.(png|tif|jpg)$')
SIDECAR_TMP_RE = re.compile(r'^\..+\.json\.[0-9a-f]{6}\.tmp$')
WORKER_FILE_RE = re.compile(r'^cu_(j[0-9a-f]{12})_(i\d{3,4})_s\d+')

CONTROL_TEXT = [
    ('Slider values differ from the preset',
     'The slider values do not match the chosen preset. Choose Custom to use your own values.'),
    ('Protect must be a list of',
     'Choose protected areas from People, Furniture and objects, Vehicles, Windows and glass, Architecture.'),
    ('Unknown protect option', 'That protect option is not available. Choose the protected areas one by one.'),
    ('Upscale must be', 'Choose an upscale of 2×, 4×, 6× or 8×.'),
    ('Output format must be one of', 'Choose an output format: PNG 8-bit, PNG 16-bit, TIFF 16-bit or JPEG.'),
]


RELEASING_TEXT = 'This image is still releasing its graphics card. Try again in a moment.'


def plain_control_error(e):
    """Plain sentence for a controls.ControlError (see CONTROL_TEXT); slider names are capitalised."""
    text = str(e)
    for prefix, plain in CONTROL_TEXT:
        if text.startswith(prefix):
            return plain
    m = re.match(r'(creativity|resemblance|restoration) (.*)$', text)
    if m:
        return f'{m.group(1).capitalize()} {m.group(2)}.'
    return text if text.endswith('.') else text + '.'


class ItemFailure(Exception):
    def __init__(self, text, event='item_failed', data=None, kill_worker=False, keep_work=False):
        super().__init__(text)
        self.text, self.event, self.data, self.kill_worker, self.keep_work = text, event, data or {}, kill_worker, keep_work


class Cancelled(Exception):
    pass


class Interrupted(Exception):
    pass


class EngineNotReady(Exception):
    def __init__(self, message, ref=None):
        super().__init__(message)
        self.ref = ref


class _WaitOutput(Exception):
    """The output folder cannot be used right now (plain reason); finishing waits and tries again."""


class ItemContext:
    def __init__(self, jid, iid, worker):
        self.jid, self.iid, self.worker = jid, iid, worker
        self.cancel = threading.Event()
        self.shutdown = False
        self.prompt_id = None
        self.speed = None              
        self.pace = None               
        self.factor = 1.0              
        self.stage_factors = None      
        self.worker_released = False   
        self.stop = False              


        self.superseded = False
        self.ending = False


def _test_fast_recipe():
    """A stand-in Fast recipe for the fake engine (CU_FAST_TEST=1, tests only): the Standard graph with 8 steps and cfg 2, so
    the Mode plumbing (store, planner, runner, sidecar) can be proven before the ENGINE FAST role installs the real one. It is
    never installed with the real engine."""
    def build(input_name, w, h, params, prefix, f, s, live_preview):
        return graph_v5t.build_product(input_name, w, h, dict(params, steps=8, cfg=2.0), prefix, f=f, s=s, speed_stack=True,
                                       live_preview=live_preview)
    return {'name': 'test-fast', 'version': '0', 'proof': 'none: a stand-in for the fake engine', 'eta_factor': 0.3,
            'models': {}, 'looks': ('Light', 'Default'), 'max_factor': 2, 'speed_stack': True, 'split_ok': False,
            'build': build}


SAMPLER_TRUST_AT = 0.25      


def too_large(detail):
    """Runner implementation."""
    if not isinstance(detail, dict):
        return False
    return any(e.get('type') == 'value_bigger_than_max' for ne in (detail.get('node_errors') or {}).values()
               if isinstance(ne, dict) for e in (ne.get('errors') or []) if isinstance(e, dict))


def stage_left_s(elapsed, frac, expected_s, sampling_s=None, frac_at_sampling=None, sampler_done=None):
    """Seconds left in the running pass (the item's finish time; QA NEW A, 12 Nov 2026).

    Until the sampler has reported a step, the weighted node fraction says nothing about time: the nodes before it (loaders,
    SAM, the DAT2 upscale, the VAE encode) finish in a second or two on a warm engine, faster than their weight, so the old
    extrapolation `(1 - frac) / frac * elapsed` read about 17 s at 10 % of every image on the workstation, then grew with the
    wait for the sampler to about 1,090 s (showcase 9ebb555e, S4 2x on both cards: the pass took 690 s). So: before the
    sampler, the pass's expected time (`expected_s`: planned x the measured speed of the finished passes, else x the image's
    finish-time factor) minus the time so far, never under 5 % of it. Once the sampler reports steps, the rest is measured
    from the fraction gained since its first step (`sampling_s` seconds ago, at `frac_at_sampling`), blended in over the
    first SAMPLER_TRUST_AT of the sampling (`sampler_done`, 0-1 over the pass's samplers)."""
    planned_left = max(expected_s - elapsed, 0.05 * expected_s)
    if sampling_s is None or sampler_done is None or frac_at_sampling is None or frac <= frac_at_sampling + 1e-6:
        return planned_left
    measured_left = (1.0 - frac) * sampling_s / (frac - frac_at_sampling)
    w = min(1.0, max(0.0, sampler_done / SAMPLER_TRUST_AT))
    return w * measured_left + (1.0 - w) * planned_left


def _frac(v):
    """Planner floats -> exact numbers for graph_v5t (1.5 -> Fraction(3, 2), 2.0 -> 2)."""
    fr = Fraction(v).limit_denominator(8)
    return int(fr) if fr.denominator == 1 else fr


def free_ram_gb():
    """Free physical memory in GB (Windows GlobalMemoryStatusEx), or None when it cannot be read."""
    if os.name != 'nt':
        return None

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong), ('ullTotalPhys', ctypes.c_ulonglong),
                    ('ullAvailPhys', ctypes.c_ulonglong), ('ullTotalPageFile', ctypes.c_ulonglong),
                    ('ullAvailPageFile', ctypes.c_ulonglong), ('ullTotalVirtual', ctypes.c_ulonglong),
                    ('ullAvailVirtual', ctypes.c_ulonglong), ('ullAvailExtendedVirtual', ctypes.c_ulonglong)]
    st = MEMORYSTATUSEX()
    st.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
        return None
    return st.ullAvailPhys / GB


class Runner:
    def __init__(self, cfg, settings, store, media, log):
        self.cfg, self.settings, self.store, self.media, self.log = cfg, settings, store, media, log
        if cfg.fake_engine:
            self.mode = 'fake-process' if os.environ.get('CU_FAKE_PROCESS') == '1' else 'fake'
        else:
            self.mode = 'comfy'
        self.stall_s = env_float('CU_STALL_SECONDS', 600.0)
        self.deadline_override = env_float('CU_DEADLINE_SECONDS', 0.0) or None
        self.cancel_grace_s = env_float('CU_CANCEL_GRACE_SECONDS', 20.0)
        
        
        self.shutdown_grace_s = env_float('CU_SHUTDOWN_GRACE_SECONDS', 5.0)
        self.output_wait_s = env_float('CU_OUTPUT_WAIT_SECONDS', 1800.0)
        self.unreachable_s = env_float('CU_UNREACHABLE_SECONDS', 30.0)
        self.mask_claim_s = env_float('CU_MASK_CLAIM_SECONDS', 20.0)
        self.test_crash = os.environ.get('CU_TEST_CRASH') if cfg.fake_engine else None
        if self.test_crash not in (None, '', 'finish'):
            raise SettingsError(f'CU_TEST_CRASH must be "finish" (got {self.test_crash!r})')
        self.open_dryrun = os.environ.get('CU_OPEN_DRYRUN') == '1'
        self.fake_gpus = int(env_float('CU_FAKE_GPUS', 2.0)) if cfg.fake_engine else 0
        if cfg.fake_engine and not 1 <= self.fake_gpus <= 8:
            raise SettingsError(f'CU_FAKE_GPUS must be 1 to 8 (got {self.fake_gpus})')
        self.workers = {}
        self.ctx = {}
        self.threads = {}
        self._lock = threading.RLock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread = None
        self._health_thread = None
        self.accepting = True
        self.port = None
        self.shared_job = None
        self._gpu_cache = (0.0, None, None)       
        self._gpu_lock = threading.Lock()
        self._snap = None                         
        self._snap_lock = threading.Lock()
        self._snap_ready = threading.Event()
        self._snap_wake = threading.Event()
        self._refresh_lock = threading.Lock()
        self._finish_slots = threading.BoundedSemaphore(1)
        self._mask_inflight = {}
        self._mask_waiting = 0
        self._views_inflight = {}
        self._held = {}                           
        self._last_sweep = None                   
        self.lifecycle = None                     
        self._release_waiting = None              
        self.live = LiveBoard(log)                
        self.notifier = Notifier(log, cfg.state_dir, dry_run=True if cfg.fake_engine else None)
        self.batch = BatchWatch(self.notifier, enabled=lambda: bool(self.settings.get().get('notify', True)),
                                background=lambda: bool(self.lifecycle is not None and self.lifecycle.in_background()))
        self._notifying = False
        self._sleep_held = False
        self._decoder_ok = None                   
        self._front_seq = 0.0
        self.multi = {}                           
        self._topology = None
        self._fast_files_ok = None                
        self._fast_hashes = {}                    
        self._split_said = {}                     
        self._held_vram = {}                      
        self.fake_vram_free = None                
        if cfg.fake_engine and os.environ.get('CU_FAKE_VRAM_FREE'):
            try:
                self.fake_vram_free = [float(x) for x in os.environ['CU_FAKE_VRAM_FREE'].split(',')]
            except ValueError:
                raise SettingsError('CU_FAKE_VRAM_FREE must be numbers separated by commas, for example 32,14')
        
        self._fast_test = bool(cfg.fake_engine and os.environ.get('CU_FAST_TEST') == '1')
        if self._fast_test:
            fast_recipe.RECIPE = _test_fast_recipe()
        self.settings.split_default_fn = self._split_proven
        self.store.run_fn = self._run_would
        self.media.finish_fn = self.finish_info
        self.media.ram_cap_fn = lambda: self.settings.get()['ram_cap_gb']
        self.settings.gpus_fn = self.available_gpus   
        self.node_pack = config.verify_node_pack(cfg.node_pack_dir, cfg.manifest_path)
        self.log.info('runner_init', f'Engine mode {self.mode}', data={
            'mode': self.mode, 'stall_s': self.stall_s, 'deadline_override_s': self.deadline_override,
            'cancel_grace_s': self.cancel_grace_s, 'shutdown_grace_s': self.shutdown_grace_s,
            'output_wait_s': self.output_wait_s, 'unreachable_s': self.unreachable_s,
            'node_pack': self.node_pack, 'two_card_proof': bool(getattr(cfg, 'two_card_proof', False)),
            'split_proven': self._split_proven(), 'split_earlier_proven': self._split_earlier_proven()})

    
    def gpu_list(self, max_age=None):
        """(gpus, problem) from the last nvidia-smi run. Never runs nvidia-smi itself (that is the health-probe thread's job,
        or _refresh_gpus on a worker thread), so it is safe on HTTP threads."""
        if self.mode != 'comfy':
            free = self.fake_vram_free or []
            return [{'index': g, 'uuid': f'FAKE-{g}', 'name': f'Test graphics card {g + 1}', 'mem_total_gb': 32.0,
                     'mem_free_gb': free[g] if g < len(free) else 32.0} for g in range(self.fake_gpus)], None
        _, gpus, problem = self._gpu_cache
        return list(gpus or []), problem

    def _refresh_gpus(self):
        """Run nvidia-smi (contained, up to 20 s). One at a time; callers that arrive meanwhile get the fresh result."""
        if self.mode != 'comfy':
            return self.gpu_list()
        started = time.monotonic()
        with self._gpu_lock:
            if self._gpu_cache[0] >= started:
                return self.gpu_list()
            try:
                gpus, problem = query_gpus(self.log, self.cfg.workers_dir / 'probe'), None
            except (WorkerError, OSError) as e:
                gpus, problem = [], str(e)
                self.log.warn('gpu_query_failed', str(e), data={'detail': getattr(e, 'detail', None)})
            self._gpu_cache = (time.monotonic(), gpus, problem)
        return self.gpu_list()

    def available_gpus(self):
        return [g['index'] for g in self.gpu_list()[0]]

    def gpu_probe_pending(self):
        """True until the health-probe thread has run nvidia-smi once (the first seconds after start, real engine only)."""
        return self.mode == 'comfy' and self._gpu_cache[0] == 0.0

    def _gpu_lookup(self):
        """GPU table for a worker start (item thread): refreshed when it is missing or the last query failed."""
        gpus, problem = self.gpu_list()
        if not gpus or problem:
            gpus, problem = self._refresh_gpus()
        return {g['index']: g for g in gpus}

    
    def recover(self):
        n = self.store.recover(self._stage_file_ok, self._published_check)
        if n:
            self.log.info('recovery_done', f'{n} image(s) recovered after a restart')
        for jid, iid in getattr(self.store, 'recovered_done', []):
            threading.Thread(target=self._views_safe, args=(jid, iid), name=f'views-{jid}-{iid}', daemon=True).start()
        return n

    def start(self):
        self._thread = threading.Thread(target=self._loop, name='scheduler', daemon=True)
        self._thread.start()
        self._health_thread = threading.Thread(target=self._health_loop, name='health-probe', daemon=True)
        self._health_thread.start()

    def wake(self):
        self._wake.set()

    def _loop(self):
        while not self._stop.is_set():
            self._wake.wait(0.5)
            self._wake.clear()
            if self._stop.is_set():
                break
            try:
                self._sync_workers()
                self._dispatch()
                self._idle_check()
            except Exception as e:   
                self.log.exception('scheduler_error', 'The scheduler hit an error and carries on', e)
                self._stop.wait(1.0)

    def _ensure_shared_job(self):
        """One parent Job for every contained worker (its JobMemoryLimit = ram_cap_gb caps all workers together)."""
        if self.shared_job is not None or self.mode == 'fake' or os.name != 'nt':
            return self.shared_job
        from service.windows_job import SharedJob
        cap = float(self.settings.get()['ram_cap_gb'])
        self.shared_job = SharedJob(memory_limit_bytes=int(cap * GB))
        self.log.info('shared_job_created', f'All engine processes share one memory cap of {cap:g} GB',
                      data={'ram_cap_gb': cap})
        return self.shared_job

    def _sync_workers(self):
        gpus = self.settings.get()['gpus']
        with self._lock:
            self.store.parallelism = max(1, len(gpus))
            for g in gpus:
                if g not in self.workers:
                    self.workers[g] = Worker(g, self.cfg, self.settings, self.log, self.mode, shared_job=self._ensure_shared_job())
            for g in list(self.workers):
                if g not in gpus and not self.workers[g].busy:
                    self.workers[g].stop(f'GPU {g + 1} was turned off in Settings')
                    del self.workers[g]

    def _admit(self, jid, iid):
        """Memory admission for a second image beside a running one (see module docstring). Returns True to start it."""
        need = float(self.store.item(jid, iid)['plan'].get('peak_ram_gb') or 0.0)
        running = []
        for (j, i), c in self.ctx.items():
            if not c.worker_released:
                try:
                    running.append(float(self.store.item(j, i)['plan'].get('peak_ram_gb') or 0.0))
                except NotFound:
                    continue
        if not running:
            self._held.pop((jid, iid), None)
            return True
        cap = float(self.settings.get()['ram_cap_gb'])
        free = free_ram_gb() if self.mode == 'comfy' else None
        reason = None
        if sum(running) + need > cap:
            reason = 'cap'
        elif free is not None and need > free - 4.0:
            reason = 'free'
        if reason is None:
            self._held.pop((jid, iid), None)
            return True
        if self._held.get((jid, iid)) != reason:
            self._held[(jid, iid)] = reason
            self.log.info('item_held_memory', 'Waiting for memory: the other graphics card is working on a large image',
                          job=jid, item=iid, data={'need_gb': need, 'running_gb': running, 'cap_gb': cap,
                                                   'free_gb': None if free is None else round(free, 1), 'reason': reason})
            self.store.update_item(jid, iid, message='Waiting for memory: the other graphics card is working on a large image',
                                   if_state={'queued'})
        return False

    def _split_proven(self):
        """The two-card proof has passed (engine_options.SPLIT_PROVEN, True since 12 Nov), or this process is the proof run
        itself (service/app.py --two-card-proof, real engine or fake). Fake engine only, for tests: CU_SPLIT_TEST=1 says the
        proof passed, CU_SPLIT_TEST=0 that it did not (a build with SPLIT_PROVEN False), whatever the constant says."""
        if getattr(self.cfg, 'two_card_proof', False):
            return True
        test = os.environ.get('CU_SPLIT_TEST', '').strip() if self.cfg.fake_engine else ''
        if test in ('0', '1'):
            return test == '1'
        return bool(engine_options.SPLIT_PROVEN)

    def _split_earlier_proven(self):
        """An image that matches earlier results may be shared too (engine_options.SPLIT_EARLIER_PROVEN, True since 12 Nov),
        or this process is the proof run that decides it (--two-card-proof). Fake engine only, for tests:
        CU_SPLIT_EARLIER_TEST=0 / 1 says it as that constant would (0: such an image stays on one card, the state of a build
        whose SPLIT_EARLIER_PROVEN is False). CU_SPLIT_TEST does not say it."""
        if getattr(self.cfg, 'two_card_proof', False):
            return True
        test = os.environ.get('CU_SPLIT_EARLIER_TEST', '').strip() if self.cfg.fake_engine else ''
        if test in ('0', '1'):
            return test == '1'
        return bool(engine_options.SPLIT_EARLIER_PROVEN)

    def _split_on(self):
        """One image may be shared: proven, Settings `split` on (its default once proven) and two or more cards in use."""
        if not self._split_proven():
            return False
        st = self.settings.get()
        return bool(st['split']) and len(st['gpus']) > 1

    def _split_cards(self):
        """nvidia-smi's rows with the free memory a shared image would find on each card: what the driver reported plus what
        this app's own engines held there at that moment (they are idle and are stopped before a shared image starts, or the
        card is busy and no split is planned). Never runs nvidia-smi (health-probe thread)."""
        out = []
        for c in self.gpu_list()[0]:
            free = c.get('mem_free_gb')
            held = float(self._held_vram.get(c['index'], 0.0))
            out.append(dict(c, mem_free_gb=None if free is None else round(float(free) + held, 2),
                            held_by_this_app_gb=round(held, 2)))
        return out

    def _say_split_skipped(self, key, name, short):
        """Activity, once per image and set of cards: a card is under the floor, so this image runs on one GPU (preview design)."""
        short = [(g, v) for g, v in short]
        if not short or self._split_said.get(key) == tuple(g for g, _ in short):
            return
        self._split_said[key] = tuple(g for g, _ in short)
        if len(self._split_said) > 2000:
            self._split_said.pop(next(iter(self._split_said)))
        self.log.info('split_skipped', engine_options.under_floor_text(short, gpu_policy.MIN_SPLIT_FREE_VRAM_GB,
                                                                       tail=f'{name} runs on one GPU'),
                      job=key[0], item=key[1], data={'under_floor': [{'gpu': g, 'vram_free_gb': v} for g, v in short],
                                                     'floor_gb': gpu_policy.MIN_SPLIT_FREE_VRAM_GB})

    def _dispatch_split(self):
        """One image on several cards (gpu_policy). Returns True when the lanes must not dispatch now (an image was started
        on a split worker, or the cards are being kept for one). Called with self._lock held."""
        gpus = sorted(self.settings.get()['gpus'])
        order = [k for k in self.store.queue_order() if k not in self.ctx]
        running = sum(1 for c in self.ctx.values() if not c.worker_released)
        cards = [dict(c, mem_free_gb=32.0 if c.get('mem_free_gb') is None else c['mem_free_gb']) for c in self._split_cards()]
        mp, first, shareable, mode = 0.0, None, True, 'standard'
        if order:
            try:
                first = self.store.item(*order[0])
                
                
                mp = sum(float(s.get('render_mp') or 0.0) for s in (first['plan'].get('stages') or []))
                
                
                mode, match, _ = self._run_choice(self.store.get(order[0][0]), first)
                shareable = engine_options.split_allowed(mode, match, earlier_proven=self._split_earlier_proven())
            except NotFound:
                order, first = [], None
        warm = [tuple(getattr(w, 'gpus', (w.gpu,))) for w in list(self.workers.values()) + list(self.multi.values())
                if w.state in ('ready', 'starting')]             
        topo = gpu_policy.plan_topology(cards, gpus, len(order), running, self._topology, split_enabled=shareable,
                                        ram_cap_gb=float(self.settings.get()['ram_cap_gb']), waiting_mp=mp, warm=warm)
        if not shareable and len(gpus) > 1 and topo.mode == 'lanes':      
            topo.reason = 'the next image runs on one card: ' + ('Fast mode' if mode == 'fast' else 'it matches earlier results')
        if first is not None and topo.under_floor and topo.mode == 'lanes':
            self._say_split_skipped(order[0], first['name'], topo.under_floor)
        if topo is not self._topology and (self._topology is None or topo.workers != self._topology.workers):
            self.log.info('topology', f'Graphics cards: {topo.mode} ({topo.reason})',
                          data={'mode': topo.mode, 'workers': [list(w) for w in topo.workers], 'saving_s': round(topo.saving_s)})
        self._topology = topo
        if topo.mode != 'split' or not order:
            if topo.mode != 'split' and order:


                for key, mw in list(self.multi.items()):
                    if not mw.busy:
                        mw.stop('one image per card again')
                        del self.multi[key]
            return any(mw.busy for mw in self.multi.values())
        group = tuple(topo.workers[0])
        if any(self.workers.get(g) is not None and self.workers[g].busy for g in group):
            return True                                          
        mw = self.multi.get(group)
        if mw is not None and mw.busy:
            return True
        for g in group:                                          
            w = self.workers.get(g)
            if w is not None and (w.proc is not None or w.fake is not None or w.state in ('ready', 'starting')):
                w.stop('the cards work on one image together')
        if mw is None:
            mw = self.multi[group] = MultiCardWorker(list(group), self.cfg, self.settings, self.log, self.mode,
                                                     shared_job=self._ensure_shared_job())
        jid, iid = order[0]
        if not self._admit(jid, iid):
            return True
        name = self.store.item(jid, iid)['name']
        ctx = ItemContext(jid, iid, mw)
        self.ctx[(jid, iid)] = ctx
        mw.busy = True
        for g in group:
            if g in self.workers:
                self.workers[g].busy = True                      
        try:
            rec = self.store.update_item(jid, iid, state='preparing', message='Preparing', message_log_ref=None,
                                         gpu=group[0], cards=list(group), run=self._frozen_run(jid, iid, mw),
                                         if_state={'queued'}, event='item_dispatched',
                                         msg=f'{mw.name} started {name}', data={'gpu': group[0], 'cards': list(group)})
            if rec is None:
                raise StateError('the image left the queue before it could start')
            self.batch.started()
            t = threading.Thread(target=self._run_item_safe, args=(mw, ctx), name=f'item-{jid}-{iid}', daemon=True)
            self.threads[(jid, iid)] = t
            t.start()
        except BaseException:
            self.ctx.pop((jid, iid), None)
            self.threads.pop((jid, iid), None)
            mw.busy = False
            for g in group:
                if g in self.workers:
                    self.workers[g].busy = False
            raise
        return True

    def _dispatch(self):
        with self._lock:
            if not self.accepting or self._mask_waiting:
                return
            if self._split_on():
                if self._dispatch_split():
                    return
            else:
                
                
                for key, mw in list(self.multi.items()):
                    if not mw.busy:
                        mw.stop('each image runs on one card again')
                        del self.multi[key]
            for g in sorted(self.workers):
                w = self.workers[g]
                if w.busy or (w.state == 'failed' and time.monotonic() < w.next_start_after):
                    continue
                nxt = self.store.next_queued(exclude=set(self.ctx))
                if nxt is None:
                    return
                jid, iid = nxt
                if not self._admit(jid, iid):
                    return                     
                name = self.store.item(jid, iid)['name']
                ctx = ItemContext(jid, iid, w)
                self.ctx[nxt] = ctx
                w.busy = True
                try:
                    self._rebalance_caps()
                    rec = self.store.update_item(jid, iid, state='preparing', message='Preparing', message_log_ref=None,
                                                 gpu=g, cards=[g], run=self._frozen_run(jid, iid, w),
                                                 if_state={'queued'}, event='item_dispatched',
                                                 msg=f'GPU {g + 1} started {name}', data={'gpu': g})
                    self.batch.started()
                    if rec is None:
                        raise StateError('the image left the queue before it could start')
                    t = threading.Thread(target=self._run_item_safe, args=(w, ctx), name=f'item-{jid}-{iid}', daemon=True)
                    self.threads[nxt] = t
                    t.start()
                except BaseException:
                    
                    self.ctx.pop(nxt, None)
                    self.threads.pop(nxt, None)
                    w.busy = False
                    self._rebalance_caps()
                    raise

    
    def _rebalance_caps(self):
        """Each worker's own Job cap = the total cap minus the planned peaks of the images the OTHER workers are working on
        (see the module docstring). Called with self._lock held, whenever an image takes or frees a worker."""
        total = float(self.settings.get()['ram_cap_gb'])
        peaks = {}
        for (j, i), c in self.ctx.items():
            if c.worker_released:
                continue
            try:
                need = float(self.store.item(j, i)['plan'].get('peak_ram_gb') or 0.0)
            except NotFound:
                continue
            peaks[c.worker.gpu] = peaks.get(c.worker.gpu, 0.0) + need
        for g, w in self.workers.items():
            w.set_memory_cap(max(1.0, total - sum(p for gg, p in peaks.items() if gg != g)), total)

    
    def work_summary(self):
        """Counts of the images not finished yet, for the lifecycle log and the close reply."""
        counts = {'queued': 0, 'preparing': 0, 'running': 0, 'finishing': 0, 'interrupted': 0}
        for jid, iid in self.store.active_items():
            try:
                st = self.store.item(jid, iid)['state']
            except NotFound:
                continue
            counts[st] = counts.get(st, 0) + 1
        queued = 0
        for job in self.store.list(limit=200):
            if job.get('state') in TERMINAL:
                continue
            queued += sum(1 for it in job.get('items', []) if it.get('state') in ('queued', 'interrupted'))
        return {'images_running': counts['preparing'] + counts['running'], 'images_saving': counts['finishing'],
                'images_waiting': queued}

    def work_summary_busy(self):
        w = self.work_summary()
        return bool(w['images_running'] or w['images_saving'] or w['images_waiting'])

    def quiet(self):
        """Nothing to do and no engine running: the service may exit (lifecycle thread)."""
        with self._lock:
            if self.ctx or self._mask_inflight or self._mask_waiting or self._views_inflight or self._notifying:
                return False
            if any(w.busy or w.state in ('ready', 'starting', 'stopping') or w.proc is not None or w.fake is not None
                   for w in list(self.workers.values()) + list(self.multi.values())):
                return False
        return self.store.next_queued() is None

    def _lifecycle_release(self):
        """Stop every worker at once when the app has closed (or "Finish in the background" was chosen) and no image needs a
        graphics card any more. Runs on the scheduler thread, which an image wakes when it frees its card."""
        lc = self.lifecycle
        reason = lc.release_reason() if lc is not None else None
        if reason is None:
            self._release_waiting = None
            return
        with self._lock:
            gpu_items = sum(1 for c in self.ctx.values() if not c.worker_released)
            queued = self.store.next_queued(exclude=set(self.ctx)) is not None
            busy = sorted({g for w in list(self.workers.values()) + list(self.multi.values()) if w.busy
                           for g in getattr(w, 'gpus', (w.gpu,))})
            if gpu_items or queued or busy:
                waiting = (reason, gpu_items, queued, tuple(busy))
                if self._release_waiting != waiting:
                    self._release_waiting = waiting
                    self.log.info('release_waiting', 'The graphics cards are freed when the images still upscaling are done',
                                  data={'reason': reason, 'images_on_cards': gpu_items, 'images_queued': queued,
                                        'busy_cards': busy})
                return
            self._release_waiting = None
            stopped = []
            for w in list(self.workers.values()) + list(self.multi.values()):
                if w.proc is not None or w.fake is not None or w.state in ('ready', 'starting'):
                    w.stop('the app closed' if reason == 'app_closed' else 'the batch finished in the background')
                    stopped += list(getattr(w, 'gpus', (w.gpu,)))     
            stopped = sorted(set(stopped))
        lc.released(reason, stopped)

    def _work_left(self, exclude=None):
        with self._lock:
            if any(k != exclude for k in self.ctx):
                return True
        return self.store.next_queued(exclude={exclude} if exclude else ()) is not None

    def _sleep_check(self):
        """Hold off sleep while a batch runs (Settings hold_sleep); called on the scheduler thread, which keeps the request."""
        want = bool(self.settings.get().get('hold_sleep', True)) and self._work_left()
        if want == self._sleep_held:
            return
        ok = True
        if self.mode == 'comfy' and os.name == 'nt':
            flags = ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if want else 0)
            ok = bool(ctypes.windll.kernel32.SetThreadExecutionState(ctypes.c_uint(flags)))
        self._sleep_held = want if ok else False
        self.log.info('sleep_held' if want else 'sleep_released', 'Sleep is held off while images upscale' if want else
                      'Sleep is allowed again', data={'ok': ok, 'applied': self.mode == 'comfy' and os.name == 'nt'})

    def _batch_check(self):
        """The batch's end: the Windows notification when the window is gone (service/notify.py)."""
        if self.batch.started_at is None or self._work_left():
            return
        self._notifying = True
        try:
            self.batch.idle()
        finally:
            self._notifying = False
        if self.lifecycle is not None:     
            self.lifecycle.batch_ended()

    def _idle_check(self):
        self._sleep_check()
        self._batch_check()
        self._lifecycle_release()
        idle = self.settings.get()['idle_minutes'] * 60
        with self._lock:
            queued = self.store.next_queued(exclude=set(self.ctx)) is not None
            for w in list(self.workers.values()) + list(self.multi.values()):
                if w.state == 'ready' and not w.busy and time.monotonic() - w.last_used > idle:
                    w.stop(f'idle for {idle / 60:.0f} min')
                elif w.state == 'failed' and not w.busy:
                    clean = w.preflight_failed and not self.problems(engine_only=True)
                    if clean or (not queued and time.monotonic() >= w.next_start_after):
                        self._reset_worker(w, 'the problem has cleared' if clean else 'nothing is waiting for it')

    def _reset_worker(self, w, why):
        self.log.info('worker_reset', f'The engine on GPU {w.gpu + 1} is ready to try again ({why})',
                      data={'gpu': w.gpu, 'problem': w.problem, 'why': why})
        w.state, w.problem, w.problem_ref, w.preflight_failed = 'stopped', None, None, False
        w.next_start_after = 0.0

    def retry_engine(self):
        """POST /api/engine/retry: forget start failures and their back-off, re-check paths now, wake the scheduler."""
        with self._lock:
            n = 0
            for w in self.workers.values():
                if w.state == 'failed' and not w.busy:
                    w.start_failures = 0
                    self._reset_worker(w, 'asked to try again')
                    n += 1
        started = time.monotonic()
        self.invalidate_problems()                
        while time.monotonic() - started < 5.0:
            snap = self._snapshot()
            if snap is not None and snap['t'] >= started:
                break
            time.sleep(0.05)
        self.wake()
        self.log.info('engine_retry', 'Trying the engine again' if n else 'Checked the engine again', data={'reset': n})
        return self.health()

    def shutdown(self, timeout=30.0):
        with self._lock:
            self.accepting = False
            ctxs = list(self.ctx.values())
            threads = list(self.threads.values())
            for c in ctxs:
                c.shutdown = True
        self.log.info('runner_shutdown', 'Stopping: running images will continue next time')
        deadline = time.monotonic() + timeout


        with self._lock:
            on_card = [t for (k, t) in list(self.threads.items()) if k in self.ctx and not self.ctx[k].worker_released]
        for t in on_card:
            t.join(max(0.0, deadline - time.monotonic()))
        with self._lock:
            workers = list(self.workers.values()) + list(self.multi.values())
        for w in workers:
            w.stop('service shutdown', kill=False)
        for t in threads:
            t.join(max(0.0, deadline - time.monotonic()))
        self._stop.set()
        self._wake.set()
        self._snap_wake.set()
        if self._thread is not None:
            self._thread.join(5.0)
        if self._sleep_held:            
            self._sleep_held = False
            self.log.info('sleep_released', 'Sleep is allowed again', data={'why': 'service shutdown'})
        with self._lock:
            workers = list(self.workers.values()) + list(self.multi.values())
        for w in workers:               
            w.stop('service shutdown', kill=False)
        if self.shared_job is not None:
            self.shared_job.close()
        try:
            self.store.flush()
        except OSError as e:
            self.log.error('shutdown_flush_failed', f'Progress could not be saved at exit: {e}')
        still = [t.name for t in threads if t.is_alive()]
        if still:
            self.log.warn('shutdown_threads_left', 'Some images were still saving at exit; they are recovered next start',
                          data={'threads': still})

    
    def create_job(self, body):
        if not self.accepting:
            raise ApiError(503, 'shutting_down', 'The app is closing. Try again in a moment.')
        if not isinstance(body, dict):
            raise ApiError(400, 'bad_request', 'The request must be a JSON object.')
        unknown = set(body) - {'client_request_id', 'media_ids', 'settings', 'output_dir'}
        if unknown:
            raise ApiError(400, 'bad_request', 'Unsupported fields: ' + ', '.join(sorted(unknown)))
        rid = body.get('client_request_id')
        if not isinstance(rid, str) or not REQUEST_ID_RE.match(rid):
            raise ApiError(400, 'bad_request', 'client_request_id must be 32 lowercase hexadecimal characters.')
        body_hash = sha256_bytes(canonical_json(body))
        try:
            existing = self.store.find_request(rid, body_hash)
        except Conflict as e:
            raise ApiError(409, 'request_conflict', 'This request id was already used for a different upscale.',
                           data={'job_id': str(e)})
        if existing is not None:
            self.log.info('job_request_repeat', 'Repeated request returned the existing job', job=existing['id'])
            return existing, False
        mids = body.get('media_ids')
        if not isinstance(mids, list) or not mids or not all(isinstance(m, str) for m in mids):
            raise ApiError(400, 'bad_request', 'Choose at least one image (media_ids must be a list of image ids).')
        if len(mids) > 1000:
            raise ApiError(400, 'bad_request', 'A batch can hold at most 1000 images.')
        recs = []
        for m in mids:
            try:
                recs.append(self.media.get(m))
            except KeyError:
                raise ApiError(400, 'unknown_image', 'One of the images is no longer in the list. Add it again.',
                               data={'media_id': m})
        settings = body.get('settings', {})
        if not isinstance(settings, dict):
            raise ApiError(400, 'bad_settings', 'Settings must be a JSON object.')
        try:
            params, effective = controls.resolve(settings)
        except controls.ControlError as e:
            raise ApiError(400, 'bad_settings', plain_control_error(e), data={'detail': str(e)})
        self._check_mode(effective)
        out_dir = body.get('output_dir') or self.settings.get()['output_dir']
        if not isinstance(out_dir, str) or not Path(out_dir).is_absolute():
            raise ApiError(400, 'bad_output_dir', 'The output folder must be a full folder path.')
        try:
            probe_writable(out_dir)
        except SettingsError as e:
            raise ApiError(400, 'bad_output_dir', str(e))
        scale, fmt = effective['scale'], effective['output_format']
        ram_cap = float(self.settings.get()['ram_cap_gb'])
        items, refusals, out_bytes, work_bytes = [], [], 0, 0
        fast_now = self.fast_info() if effective.get('mode') == 'fast' else None
        fast_refused = []                
        for i, rec in enumerate(recs):
            plan = planner.plan(rec['width'], rec['height'], scale)
            reason = plan.reason if not plan.ok else ram_refusal(plan, ram_cap)
            if reason:
                refusals.append(f'{rec["name"]} ({reason})')
                continue
            if fast_now is not None:
                bad = engine_options.fast_refusal(effective, fast_now, plan)
                if bad is not None:
                    fast_refused.append((rec['name'], bad))
                    continue
            ow, oh = plan.output_size
            ch = 4 if rec['alpha'] and fmt != 'jpeg' else 3
            out_bytes += ow * oh * ch * (2 if fmt in ('png16', 'tiff16') else 1)
            work_bytes = max(work_bytes, sum(s.output_size[0] * s.output_size[1] * 3 for s in plan.stages))
            notes = list(rec.get('notes') or [])
            if rec['alpha'] and fmt == 'jpeg':
                notes.append('JPEG has no transparency: the transparent areas are filled. Choose PNG or TIFF to keep them.')
            if rec.get('duplicate_of'):
                notes.append('This file is identical to another image in the list.')
            n = len(plan.stages)
            mid = rec['id']
            items.append({'id': f'i{i + 1:03d}', 'media_id': mid, 'source': rec['path'], 'name': rec['name'],
                          'size': [rec['width'], rec['height']], 'alpha': rec['alpha'], 'sha256': rec['sha256'],
                          'format': rec['format'], 'bit_depth': rec['bit_depth'], 'plan': plan.to_dict(),
                          'state': 'queued', 'stage_index': 0, 'stage': 0, 'stages': n, 'stages_done': 0,
                          'stage_progress': 0.0, 'progress': 0.0, 'progress_estimated': False, 'eta_s': None,
                          'message': 'Waiting', 'message_log_ref': None, 'output': None, 'sidecar': None, 'error': None,
                          'notes': notes, 'cancel_requested': False, 'publishing': None, 'result_ready': False,
                          'thumb_url': f'/api/media/{mid}/thumb', 'proxy_url': f'/api/media/{mid}/proxy',
                          'timings': {'queued': now_iso(), 'stages': []}, 'history': [{'ts': now_iso(), 'state': 'queued'}]})
        if refusals:
            raise ApiError(400, 'plan_refused', f'These images cannot be upscaled {scale}×: ' + '; '.join(refusals),
                           data={'refused': refusals})
        if fast_refused:
            
            (reason, message) = fast_refused[0][1]
            raise ApiError(400, 'fast_unavailable', message,
                           data={'reason': reason, 'refused': [name for name, _ in fast_refused]})
        self._check_free(out_dir, out_bytes * 1.05 + 0.25 * GB, 'the output folder')
        self._check_free(self.cfg.work_dir, work_bytes * 1.2 + 1 * GB, 'the app work folder')
        jid = new_id('j')
        job = {'id': jid, 'created': now_iso(), 'client_request_id': rid, 'body_hash': body_hash, 'settings': settings,
               'effective': effective, 'output_dir': str(Path(out_dir)), 'output_format': fmt, 'items': items,
               'app_version': VERSION, 'node_pack_sha256': self.node_pack.get('tree_sha256'), 'engine_mode': self.mode,
               'eta_factor': self._run_would(None, None, effective.get('mode', 'standard'))['factor']}
        work = self.cfg.work_dir / jid
        try:
            for it in items:
                self.media.copy_for_job(it['media_id'], work / it['id'])
            rec, created = self.store.create(job)
        except Conflict as e:
            shutil.rmtree(work, ignore_errors=True)
            raise ApiError(409, 'request_conflict', 'This request id was already used for a different upscale.',
                           data={'job_id': str(e)})
        except BaseException:
            shutil.rmtree(work, ignore_errors=True)
            raise
        if not created:
            shutil.rmtree(work, ignore_errors=True)
        self.wake()
        return rec, created

    def _check_free(self, path, need, label):
        try:
            free = shutil.disk_usage(path).free
        except OSError as e:
            raise ApiError(400, 'disk_unavailable', f'The free space of {label} could not be read ({e.strerror or e}).')
        if free < need:
            raise ApiError(400, 'disk_full', f'Not enough free space in {label}: needs about {need / GB:.1f} GB, '
                                             f'{free / GB:.1f} GB free.')

    def plan_check(self, plan):
        """Planner dict for POST /api/plan with the memory check applied and the finish time per mode (`finish`)."""
        from service.media import plan_dict
        return plan_dict(plan, self.settings.get()['ram_cap_gb'], self.finish_info)

    
    @staticmethod
    def _item_mode(job, it):
        return ((it or {}).get('effective') or (job or {}).get('effective') or {}).get('mode', 'standard')

    def _fast_check_due(self):
        """The health probe reads the Fast recipe's files (real engine, a recipe installed, Fast offerable): only then can
        their check be pending."""
        return bool(self.mode == 'comfy' and fast_recipe.describe()['installed']
                    and (engine_options.fast_proven() or self._fast_test))

    def _fast_files_pending(self):
        """True until the probe has read the recipe's files once since the service started (FCK3)."""
        return self._fast_files_ok is None and self._fast_check_due()

    def _fast_info_to_start(self):
        """fast_info() for a Fast image about to start (item threads only, never an HTTP thread). FCK3 (13 Nov 2026): while
        the probe has not yet read the LoRA once (an image recovered after a restart can reach its start first), the files
        are read here first, so a Fast image starts only on a checked file. Old: it started on an unchecked one."""
        if self._fast_files_pending():
            self._refresh_health()
        return self.fast_info()

    def fast_info(self):
        """/health engine.fast (contract part 2, section 3; fast-contract section 1.1). 13 Nov 2026 (FAST FIX, the
        independent check's FCK3): until the probe has read the LoRA once, Fast reads `checking` and is not offered, so it
        is never offered on a file nobody has hashed (the 12-step Hyper-SD LoRA beside it has the same size). Old: a file
        not yet checked counted as present (`self._fast_files_ok is not False`)."""
        files_ok = self._fast_files_ok if self._fast_check_due() else True
        return engine_options.fast_info(files_ok, proven=True if self._fast_test else None)

    def faster_info(self):
        """/health engine.faster (fast-contract section 1.2): offered (FASTER_PROVEN), and on with Settings `faster`."""
        st = self.settings.get()
        return engine_options.faster_info(bool(st.get('faster')), bool(st.get('match_earlier')))

    def _faster_wanted(self):
        """A Standard image that starts from its source now runs Faster (offered, on, "Match earlier results" off)."""
        return bool(self.faster_info()['on'])

    def _check_mode(self, effective, plan=None):
        """ApiError 400 fast_unavailable when the settings ask for Fast and Fast cannot make them: not available, a scale
        above the recipe's largest factor, a Look it does not offer, or (with the image's plan) an image too large for it
        (fast-contract section 3; `data.reason` says which). A request for Fast in the first seconds after the service
        started waits up to FAST_CHECK_WAIT_S for the probe's first round (no file is read on this thread), then is
        refused with `checking` if the files are still unchecked (FCK3)."""
        if (effective or {}).get('mode') == 'fast' and self._fast_files_pending():
            self._snap_ready.wait(FAST_CHECK_WAIT_S)
        bad = engine_options.fast_refusal(effective, self.fast_info(), plan)
        if bad is not None:
            raise ApiError(400, 'fast_unavailable', bad[1], data={'reason': bad[0]})

    def finish_info(self, minutes, plan=None):
        """`finish` of a plan object: the finish time per mode with Settings as they are now (`fast` only for a plan Fast
        can make, with `fast_refusal` saying why not; `faster` while it is offered), one card's, and `single`: one image of
        this plan started now on its own, on the cards the split policy would give it (FC3)."""
        match = bool(self.settings.get().get('match_earlier'))
        fast = self.fast_info()
        cards = {'standard': self._cards_if_started('standard', match, plan),
                 'fast': self._cards_if_started('fast', False, plan) if fast['available'] else 1}
        return engine_options.finish_info(minutes, match, fast['available'], plan=plan,
                                          faster_available=self.faster_info()['available'], fast_reason=fast['reason'],
                                          cards=cards)

    def _running_count(self):
        return sum(1 for c in list(self.ctx.values()) if not c.worker_released)

    def _cards_if_started(self, mode, match_earlier, plan, queued=1, running=0):
        """How many cards an image of `plan` would run on if it started now (13 Nov 2026, FAST PORT FIX, the independent
        check's FC3): what the split policy gives the next waiting image (gpu_policy.plan_topology, as _dispatch_split asks
        it, with the cards' free memory, the warm engines and the switch cost), for `queued` images waiting and `running`
        rendering. The defaults (1, 0) are an image on its own: the plan objects' `finish.single`. Never runs nvidia-smi,
        never changes the topology in use (the policy is asked about a copy)."""
        if not self._split_on():
            return 1
        if not engine_options.split_allowed(mode, match_earlier, earlier_proven=self._split_earlier_proven()):
            return 1
        st = self.settings.get()
        gpus = sorted(st['gpus'])
        cards = [dict(c, mem_free_gb=32.0 if c.get('mem_free_gb') is None else c['mem_free_gb']) for c in self._split_cards()]
        warm = [tuple(getattr(w, 'gpus', (w.gpu,))) for w in list(self.workers.values()) + list(self.multi.values())
                if w.state in ('ready', 'starting')]
        cur = copy.copy(self._topology) if self._topology is not None else None
        topo = gpu_policy.plan_topology(cards, gpus, max(1, int(queued)), int(running), cur, split_enabled=True,
                                        ram_cap_gb=float(st['ram_cap_gb']), waiting_mp=engine_options.plan_render_mp(plan),
                                        warm=warm)
        return len(topo.workers[0]) if topo.mode == 'split' and topo.workers else 1

    def _run_would(self, job, it, mode, waiting=None):
        """store.run_fn: the `run` an image would get if it started from its source now (it follows Settings), on the cards
        the split policy would give it now (FC3: a single image the cards would share reads 0.523 before it starts, and runs
        as Standard when Faster is on, as it will). waiting: the number of images in the queue (the store counts them once
        per view; counted here when not given). `cards` stays [] until the image is dispatched."""
        match = bool(self.settings.get().get('match_earlier'))
        plan = (it or {}).get('plan')
        cards = 1
        if it is not None:
            if waiting is None:
                waiting = len(self.store.queue_order())
            queued = int(waiting) + (0 if it.get('state') == 'queued' else 1)
            cards = self._cards_if_started(mode, match and mode != 'fast', plan, queued, self._running_count())
        return dict(engine_options.run_info(mode, match_earlier=match, split=cards > 1, cards=cards,
                                            faster=self._faster_wanted(), plan=plan), cards=[])

    def _run_choice(self, job, it):
        """(mode, match_earlier, faster) an image will run with if it starts now: from finished passes it keeps the numbers
        it started with; from its source it takes Settings' "Match earlier results" and "Speed up upscaling" as they are."""
        mode = self._item_mode(job, it)
        prev = it.get('run') if isinstance(it.get('run'), dict) and it['run'].get('frozen') else None
        later = int(it.get('stage_index') or 0) > 0
        if prev is None and later and mode == 'standard':


            return mode, True, False
        resume = prev is not None and later and prev.get('mode') == mode
        match = bool(prev.get('match_earlier')) if resume else bool(self.settings.get().get('match_earlier'))
        faster = bool(prev.get('faster')) if resume else self._faster_wanted()
        match = match and mode != 'fast'
        return mode, match, faster and mode != 'fast' and not match

    def _frozen_run(self, jid, iid, worker):
        """The image starts: what it runs with, fixed for every pass (stored on the item as `run`). An image that goes on
        from finished passes keeps the numbers it started with, so one image never mixes the two; from its source it takes
        Settings' "Match earlier results" and "Speed up upscaling" as they are now. An image shared by several cards does not
        run Faster until FASTER_SPLIT_PROVEN (engine_options.run_info). Called with self._lock held, at dispatch."""
        job, it = self.store.get(jid), self.store.item(jid, iid)
        mode, match, faster = self._run_choice(job, it)
        cards = list(getattr(worker, 'gpus', (worker.gpu,)))
        run = engine_options.run_info(mode, match_earlier=match, frozen=True, split=len(cards) > 1, cards=len(cards),
                                      faster=faster, plan=it.get('plan'))
        if faster and not run['faster']:
            self.log.info('faster_not_shared', f'{it["name"]} runs on {len(cards)} GPUs, so Speed up upscaling is not used '
                          'for it', job=jid, item=iid, data={'cards': cards, 'faster_split': engine_options.faster_split_on()})
        return dict(run, cards=cards)

    
    def cancel_item(self, jid, iid):
        with self._lock:
            it = self.store.item(jid, iid)
            st = it['state']
            ctx = self.ctx.get((jid, iid))
            if st in ('queued', 'interrupted', 'stopped'):
                self.store.update_item(jid, iid, state='cancelled', message='Cancelled', eta_s=None, event='item_cancelled',
                                       msg=f'Cancelled {it["name"]}' + (' before it started' if st != 'stopped' else ''),
                                       if_state={'queued', 'interrupted', 'stopped'})
                self._cleanup_work(jid, iid)
                self.live.drop(jid, iid)
            elif st == 'preparing':
                
                
                if ctx is not None:
                    ctx.stop = False          
                    ctx.cancel.set()
                self.store.update_item(jid, iid, state='cancelled', message='Cancelled', eta_s=None, cancel_requested=True,
                                       if_state={'preparing'}, event='item_cancelled',
                                       msg=f'Cancelled {it["name"]} while the engine was starting')
                if ctx is None:
                    self._cleanup_work(jid, iid)
            elif st in ('running', 'finishing'):
                if ctx is not None:
                    ctx.stop = False          
                    ctx.cancel.set()
                else:
                    self.log.warn('cancel_no_context', 'Active item without a worker context', job=jid, item=iid)
                self.store.update_item(jid, iid, message='Cancelling', cancel_requested=True, if_state={'running', 'finishing'},
                                       event='cancel_requested', msg=f'Cancelling {it["name"]}')
        self.wake()

    
    @staticmethod
    def _item_request(job, it):
        """The settings request an image runs with: its own (even {} = every default) or, when it has none, the job's.
        12 Nov (QA ENGINE-2): `it.get('settings') or ...` made an image's own {} fall through to the job's request, so it
        rendered with the job's Look, seed and protect while its record and sidecar said Default."""
        own = it.get('settings')
        return own if own is not None else job['settings']

    @staticmethod
    def _item_effective(job, it):
        return it.get('effective') or job['effective']

    def _plan_for(self, rec, request):
        """(effective, plan dict, extra notes) for an image and a settings request; ApiError when they cannot run."""
        if not isinstance(request, dict):
            raise ApiError(400, 'bad_settings', 'Settings must be a JSON object.')
        try:
            _, eff = controls.resolve(request)
        except controls.ControlError as e:
            raise ApiError(400, 'bad_settings', plain_control_error(e), data={'detail': str(e)})
        self._check_mode(eff)
        scale = eff['scale']
        plan = planner.plan(rec['width'], rec['height'], scale)
        reason = plan.reason if not plan.ok else ram_refusal(plan, float(self.settings.get()['ram_cap_gb']))
        if reason:
            raise ApiError(400, 'plan_refused', f'{rec["name"]} cannot be upscaled {scale}×: {reason}', data={'reason': reason})
        self._check_mode(eff, plan)          
        notes = []
        if rec['alpha'] and eff['output_format'] == 'jpeg':
            notes.append('JPEG has no transparency: the transparent areas are filled. Choose PNG or TIFF to keep them.')
        return eff, plan.to_dict(), notes

    def _base_notes(self, it):
        return [n for n in (it.get('notes') or []) if not n.startswith('JPEG has no transparency')]

    def _reset_stage_files(self, jid, iid, n, keep):
        """Keep the finished stage files when `keep` (same plan and settings), else remove them. Returns the stage to start."""
        work = self.cfg.work_dir / jid / iid
        if keep:
            return next((i for i in range(n) if not self._stage_file_ok(jid, iid, i)), n)
        for f in list(work.glob('stage*')) if work.is_dir() else []:
            try:
                f.unlink()
            except OSError as e:
                self.log.warn('work_cleanup_failed', f'A finished pass could not be removed: {e}', job=jid, item=iid)
        return 0


    def _kept_dir(self, jid, iid):
        return self.cfg.work_dir / jid / iid / 'kept'

    @staticmethod
    def _kept_matches(kept, eff, plan):
        return bool(kept) and same_record(kept.get('effective'), eff) and same_record(kept.get('plan'), plan)

    def _set_passes_aside(self, jid, iid, it, eff_now):
        """The settings change: move this image's finished passes (made with `eff_now` and its plan) to the kept folder.
        Returns the kept record for the item (an earlier one stays when there were no finished passes)."""
        work = self.cfg.work_dir / jid / iid
        kept_rec = it.get('kept_passes')
        k = int(it.get('stage_index') or 0)
        files = sorted(work.glob('stage*')) if work.is_dir() else []
        if k <= 0 or not files:
            self._reset_stage_files(jid, iid, len(it['plan']['stages']), keep=False)   
            return kept_rec
        d = self._kept_dir(jid, iid)
        try:
            if d.exists():
                shutil.rmtree(d)                     
            d.mkdir(parents=True)
            for f in files:
                os.replace(f, d / f.name)
        except OSError as e:
            self.log.warn('passes_aside_failed', f'The finished passes could not be set aside, so they are removed: {e}',
                          job=jid, item=iid)
            self._reset_stage_files(jid, iid, len(it['plan']['stages']), keep=False)
            shutil.rmtree(d, ignore_errors=True)
            return None
        self.log.info('passes_kept', f'{k} finished pass{"es" if k > 1 else ""} kept aside while the settings differ',
                      job=jid, item=iid, data={'stage_index': k})
        return {'effective': eff_now, 'plan': it['plan'], 'stage_index': k}

    def _restore_passes(self, jid, iid, kept_rec):
        """Settings match the kept passes again: put them back. Returns the stage to start (the first one not finished)."""
        work = self.cfg.work_dir / jid / iid
        d = self._kept_dir(jid, iid)
        n = len(kept_rec['plan']['stages'])
        self._reset_stage_files(jid, iid, n, keep=False)     
        try:
            for f in sorted(d.iterdir()) if d.is_dir() else []:
                os.replace(f, work / f.name)
            if d.is_dir():
                d.rmdir()
        except OSError as e:
            self.log.warn('passes_restore_failed', f'The kept passes could not all be put back; the image starts from its '
                          f'source: {e}', job=jid, item=iid)
            self._reset_stage_files(jid, iid, n, keep=False)
            self._drop_kept(jid, iid)
            return 0
        k = min(int(kept_rec.get('stage_index') or 0), self._reset_stage_files(jid, iid, n, keep=True))
        self.log.info('passes_restored', f'The settings match the finished passes again: it goes on from pass {k + 1}'
                      if k < n else 'The settings match the finished passes again', job=jid, item=iid,
                      data={'stage_index': k})
        return k

    def _drop_kept(self, jid, iid):
        d = self._kept_dir(jid, iid)
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
            if d.exists():
                self.log.warn('work_cleanup_failed', f'Kept passes could not all be removed: {d}', job=jid, item=iid)

    def stop_image(self, media_id, jid=None, iid=None):
        """POST /api/cancel?image=: the open item of that image (or the one named) -> stop_item. Returns (job, item)."""
        if jid or iid:
            if not (jid and iid):
                raise ApiError(400, 'bad_request', 'Give both job and item.')
            try:
                it = self.store.item(jid, iid)
            except NotFound:
                raise ApiError(404, 'not_found', 'Unknown job or item.')
            if media_id and it['media_id'] != media_id:
                raise ApiError(400, 'bad_request', 'That item is not this image.')
        else:
            open_ = self.store.items_where(lambda j, x: x.get('media_id') == media_id
                                           and x['state'] in ('queued', 'preparing', 'running', 'interrupted', 'finishing'))
            if not open_:
                raise ApiError(404, 'unknown_image', 'This image is not being upscaled or waiting.')
            order = {k: i for i, k in enumerate(self.store.queue_order())}
            open_.sort(key=lambda r: (r[1]['state'] not in ACTIVE, order.get((r[0], r[1]['id']), 1 << 30)))
            jid, iid = open_[0][0], open_[0][1]['id']
        self.stop_item(jid, iid)
        return jid, iid

    def stop_item(self, jid, iid):
        with self._lock:
            job = self.store.get(jid)
            it = next((x for x in job['items'] if x['id'] == iid), None)
            if it is None:
                raise NotFound(f'{jid}/{iid}')
            st, ctx = it['state'], self.ctx.get((jid, iid))
            eff = self._item_effective(job, it)
            if st in WAITING:
                self.store.update_item(jid, iid, state='stopped', message='Stopped', eta_s=None, gpu=None, cards=[],
                                       ran_with=eff, ran_with_request=self._item_request(job, it), at=None, queue_front=None,
                                       if_state=WAITING, event='item_stopped', msg=f'Stopped {it["name"]} before it started')
            elif st == 'running' and ctx is not None and ctx.worker_released:


                raise ApiError(409, 'not_stoppable', 'This image is being saved and cannot be stopped now.')
            elif st in ('preparing', 'running') and ctx is not None:
                ctx.stop = True
                ctx.cancel.set()
                at = self.live.at(jid, iid)
                if st == 'preparing':     
                    self.store.update_item(jid, iid, state='stopped', message='Stopped', eta_s=None, gpu=None, cards=[],
                                           ran_with=eff, ran_with_request=self._item_request(job, it), at=at,
                                           if_state={'preparing'}, event='item_stopped',
                                           msg=f'Stopped {it["name"]} while it was being prepared')
                else:
                    self.store.update_item(jid, iid, message='Stopping', stop_requested=True, ran_with=eff,
                                           ran_with_request=self._item_request(job, it), if_state={'running'},
                                           event='stop_requested', msg=f'Stopping {it["name"]}')
            elif st == 'finishing':
                raise ApiError(409, 'not_stoppable', 'This image is being saved and cannot be stopped now.')
            else:
                raise ApiError(409, 'not_stoppable', f'This image is {st} and cannot be stopped.', data={'state': st})
        self.wake()

    def _end_stopped(self, w, ctx):
        jid, iid = ctx.jid, ctx.iid
        at = self.live.freeze(jid, iid, 'stopped')
        try:
            job = self.store.get(jid)
            it = next(x for x in job['items'] if x['id'] == iid)
        except (NotFound, StopIteration):
            return
        if it['state'] != 'stopped':
            where = ''
            if at and at.get('pass') and at.get('step'):
                where = f' at the {at["pass"]} pass, step {at["step"]}'
            self._record(jid, iid, state='stopped', message='Stopped', eta_s=None, gpu=None, cards=[], stop_requested=False,
                         at=at, ran_with=self._item_effective(job, it), ran_with_request=self._item_request(job, it),
                         event='item_stopped', msg=f'Stopped {it["name"]}{where}', data={'at': at})
        elif at:
            self._record(jid, iid, at=at, stop_requested=False)
        if not ctx.worker_released:
            self._cleanup_item_worker_files(w, jid, iid)

    def requeue_item(self, jid, iid, settings=None, front=True, as_before=False):
        """POST /api/jobs/<job>/items/<item>/requeue: a stopped, failed or cancelled image -> queued (contract section 4).
        settings: these settings; as_before: the settings it last ran with ("Queue again as before"); neither: its own."""
        if not self.accepting:
            raise ApiError(503, 'shutting_down', 'The app is closing. Try again in a moment.')
        if settings is not None and not isinstance(settings, dict):
            raise ApiError(400, 'bad_settings', 'Settings must be a JSON object.')
        with self._lock:
            job = self.store.get(jid)
            it = next((x for x in job['items'] if x['id'] == iid), None)
            if it is None:
                raise NotFound(f'{jid}/{iid}')
            if it['state'] not in ('stopped', 'failed', 'cancelled'):
                raise ApiError(409, 'not_requeueable', f'This image is {it["state"]} and cannot be queued again.',
                               data={'state': it['state']})
            unwinding = self.ctx.get((jid, iid))
            if unwinding is not None and not self._may_supersede(unwinding, it['state'], ('stopped', 'cancelled')):
                raise ApiError(409, 'not_requeueable', RELEASING_TEXT, data={'state': it['state']})
            try:
                rec = self.media.get(it['media_id'])
            except KeyError:
                raise ApiError(400, 'unknown_image', 'This image is no longer in the list. Add it again.')
            kept_rec = self.store.item(jid, iid).get('kept_passes')
            ran = it.get('ran_with') or self._item_effective(job, it)
            if as_before:
                req = it.get('ran_with_request') or self._item_request(job, it)
            else:
                req = self._item_request(job, it) if settings is None else settings
            eff, plan, extra_notes = self._plan_for(rec, req)
            work = self.cfg.work_dir / jid / iid
            if not (work / 'input.png').is_file():
                shutil.rmtree(work, ignore_errors=True)
                self.media.copy_for_job(it['media_id'], work)
            n = len(plan['stages'])
            changed = not same_record(eff, ran)      
            same = not changed and same_record(plan, it['plan'])
            if it['state'] == 'stopped' and self._kept_matches(kept_rec, eff, plan):
                k = self._restore_passes(jid, iid, kept_rec)       
            else:
                k = self._reset_stage_files(jid, iid, n, keep=same and it['state'] == 'stopped')
                self._drop_kept(jid, iid)
            self._front_seq = max(time.time(), self._front_seq + 0.001)
            own = settings is not None or as_before or it.get('settings') is not None
            timings = {'queued': now_iso(), 'stages': [x for x in (it.get('timings') or {}).get('stages', [])
                                                       if x.get('index', n) < k and x.get('finished')]}
            text = f'Queued {it["name"]} again' + (' with new settings' if changed else '')
            self.store.update_item(jid, iid, state='queued', settings=req if own else None, effective=eff if own else None,
                                   plan=plan, stage_index=k, stage=min(k, n - 1), stages=n, stages_done=k, stage_progress=0.0,
                                   progress=0.0, progress_estimated=False, eta_s=None, message='Waiting', message_log_ref=None,
                                   output=None, sidecar=None, error=None, cancel_requested=False, stop_requested=False,
                                   publishing=None, result_ready=False, gpu=None, cards=[], at=None, ran_with=None,
                                   ran_with_request=None, kept_passes=None,
                                   queue_front=self._front_seq if front else None, timings=timings,
                                   notes=self._base_notes(it) + extra_notes, if_state={'stopped', 'failed', 'cancelled'},
                                   event='item_requeued_by_user', msg=text,
                                   data={'front': bool(front), 'stage_index': k, 'settings_changed': changed,
                                         'effective': eff})
            if unwinding is not None:
                
                
                unwinding.superseded = True
            self.live.drop(jid, iid)
        self.wake()
        return self.store.get(jid)

    def set_item_settings(self, refs, settings):
        """POST /api/items/settings (contract section 5): each listed waiting or stopped image takes these settings."""
        if not isinstance(refs, list) or not refs or len(refs) > 1000:
            raise ApiError(400, 'bad_request', 'Send {items: [{job_id, item_id}, ...], settings: {...}}.')
        if not isinstance(settings, dict):
            raise ApiError(400, 'bad_settings', 'Settings must be a JSON object.')
        try:
            controls.resolve(settings)
        except controls.ControlError as e:
            raise ApiError(400, 'bad_settings', plain_control_error(e), data={'detail': str(e)})
        applied, refused = [], []
        for ref in refs:
            jid = ref.get('job_id') if isinstance(ref, dict) else None
            iid = ref.get('item_id') if isinstance(ref, dict) else None
            if not isinstance(jid, str) or not isinstance(iid, str):
                raise ApiError(400, 'bad_request', 'Each item needs job_id and item_id.')
            with self._lock:
                try:
                    job = self.store.get(jid)
                except NotFound:
                    refused.append({'job_id': jid, 'item_id': iid, 'code': 'not_found', 'reason': 'Unknown job.'})
                    continue
                it = next((x for x in job['items'] if x['id'] == iid), None)
                if it is None:
                    refused.append({'job_id': jid, 'item_id': iid, 'code': 'not_found', 'reason': 'Unknown image in this job.'})
                    continue
                if it['state'] in ACTIVE:
                    refused.append({'job_id': jid, 'item_id': iid, 'code': 'started', 'reason': 'This image has started.'})
                    continue
                unwinding = self.ctx.get((jid, iid))
                if unwinding is not None and not self._may_supersede(unwinding, it['state'], ('stopped',)):
                    
                    refused.append({'job_id': jid, 'item_id': iid, 'code': 'started', 'reason': RELEASING_TEXT})
                    continue
                if it['state'] not in ('queued', 'interrupted', 'stopped'):
                    refused.append({'job_id': jid, 'item_id': iid, 'code': 'bad_state',
                                    'reason': f'This image is {it["state"]}.'})
                    continue
                try:
                    rec = self.media.get(it['media_id'])
                    eff, plan, extra_notes = self._plan_for(rec, settings)
                except KeyError:
                    refused.append({'job_id': jid, 'item_id': iid, 'code': 'unknown_image',
                                    'reason': 'This image is no longer in the list.'})
                    continue
                except ApiError as e:
                    refused.append({'job_id': jid, 'item_id': iid, 'code': e.code, 'reason': e.message})
                    continue
                n = len(plan['stages'])
                eff_now = self._item_effective(job, it)
                same = same_record(eff, eff_now) and same_record(plan, it['plan'])
                raw = self.store.item(jid, iid)
                kept_rec = raw.get('kept_passes')
                if same:
                    k = it['stage_index']
                elif self._kept_matches(kept_rec, eff, plan):
                    k, kept_rec = self._restore_passes(jid, iid, kept_rec), None   
                else:
                    kept_rec, k = self._set_passes_aside(jid, iid, raw, eff_now), 0
                rec2 = self.store.update_item(jid, iid, settings=settings, effective=eff, plan=plan, stages=n,
                                              stage_index=k, stage=min(k, n - 1), stages_done=k, kept_passes=kept_rec,
                                              notes=self._base_notes(it) + extra_notes,
                                              if_state={'queued', 'interrupted', 'stopped'}, event='item_settings_changed',
                                              msg=f'New settings for {it["name"]}', data={'effective': eff})
                if rec2 is None:
                    refused.append({'job_id': jid, 'item_id': iid, 'code': 'started', 'reason': 'This image has started.'})
                    continue
                applied.append({'job_id': jid, 'item_id': iid, 'effective': eff, 'plan': plan})
        self.wake()
        return {'applied': applied, 'refused': refused}

    def cancel_job(self, jid):
        """Queued images first (so the other GPU cannot pick the next one meanwhile), then the running ones."""
        with self._lock:
            job = self.store.get(jid)
            open_items = [it for it in job['items'] if it['state'] not in TERMINAL]
            for it in sorted(open_items, key=lambda x: x['state'] in ACTIVE):
                self.cancel_item(jid, it['id'])

    def _cleanup_work(self, jid, iid):
        d = self.cfg.work_dir / jid / iid
        try:
            if d.exists():
                shutil.rmtree(d, ignore_errors=True)
                if d.exists():
                    self.log.warn('work_cleanup_failed', f'Work files could not all be removed: {d}', job=jid, item=iid)
            parent = self.cfg.work_dir / jid
            if parent.exists() and not any(parent.iterdir()):
                parent.rmdir()
        except OSError as e:
            self.log.warn('work_cleanup_failed', f'Work files could not all be removed: {e}', job=jid, item=iid)

    def _cleanup_worker_files(self, w, prefix, input_name=None):
        """Remove a prompt's input and output files from the worker folders. Never raises: a file the engine still holds
        (Windows sharing violation) is logged and removed by the next housekeeping sweep."""
        paths = [w.input_dir / input_name] if input_name else []
        try:
            paths += list(w.input_dir.glob(prefix + '*')) + list(w.output_dir.glob(prefix + '_*'))
        except OSError as e:
            self.log.warn('worker_cleanup_failed', f'Worker files could not be listed: {e}', data={'gpu': w.gpu})
            return
        for p in paths:
            try:
                if p.exists():
                    p.unlink()
            except OSError as e:
                self.log.warn('worker_cleanup_failed', f'Worker file {p.name} could not be removed: {e}',
                              data={'gpu': w.gpu, 'path': str(p)})

    def _cleanup_item_worker_files(self, w, jid, iid):
        """Every input/output file of this item's passes in the worker folders (cu_<job>_<item>_s<k>...)."""
        rx = re.compile(rf'^cu_{jid}_{iid}_s\d+([._]|$)')
        for d in (w.input_dir, w.output_dir):
            try:
                names = [p for p in d.iterdir() if rx.match(p.name)] if d.is_dir() else []
            except OSError as e:
                self.log.warn('worker_cleanup_failed', f'Worker files could not be listed: {e}', data={'gpu': w.gpu})
                continue
            for p in names:
                try:
                    p.unlink()
                except OSError as e:
                    self.log.warn('worker_cleanup_failed', f'Worker file {p.name} could not be removed: {e}',
                                  data={'gpu': w.gpu, 'path': str(p)})

    
    def _stage_file_ok(self, jid, iid, k):
        """A stage file counts as finished only when it exists and its PNG structure is intact (a crash can leave a file
        whose data never reached the disk); a damaged one is logged and rendered again."""
        p = self.cfg.work_dir / jid / iid / f'stage{k}.png'
        if not p.is_file():
            return False
        from PIL import Image
        try:
            with Image.open(p) as im:
                im.verify()
            return True
        except (OSError, ValueError, SyntaxError) as e:
            self.log.warn('stage_file_damaged', f'Pass {k + 1} of this image is damaged and is made again', job=jid,
                          item=iid, stage=k, data={'path': str(p), 'error': str(e)})
            return False

    def _published_check(self, job, it, raise_errors=False):
        """(output, sidecar) when this item's output is already in its output folder, else None. Looks at the item's own
        `publishing` record first (the output was being renamed into place), then at the sidecars named after the image
        (glob-free match, so names such as 'photo [1]' work). A missing sidecar of a published output is written. Every
        outcome is logged. With raise_errors an unreachable folder raises OSError instead of answering None."""
        jid, iid = job['id'], it['id']
        out_dir = Path(job['output_dir'])
        stem = images.safe_stem(it['name'])
        prefix = f'{stem}_cu{self._item_effective(job, it)["scale"]}x'
        try:
            pub = it.get('publishing')
            if pub and Path(pub['output']).is_file() and Path(pub['output']).stat().st_size == pub.get('bytes'):
                out = Path(pub['output'])
                side = next((s for s in images.sidecar_candidates(out) if s.is_file() and self._sidecar_matches(s, jid, iid)),
                            None)
                if side is None:
                    side = images.write_sidecar(out, pub['sidecar_json'].encode('utf8'))
                    self.log.info('sidecar_rewritten', f'The recipe file of {out.name} was written after a restart',
                                  job=jid, item=iid, data={'output': str(out), 'sidecar': str(side)})
                self.log.info('published_check', f'{out.name} was already saved', job=jid, item=iid,
                              data={'output': str(out), 'sidecar': str(side), 'via': 'publishing record'})
                return str(out), str(side)
            if pub and Path(pub['output']).is_file():
                self.log.warn('published_check_mismatch', f'{Path(pub["output"]).name} is incomplete; the result is saved '
                              'again under a new name', job=jid, item=iid, data={'publishing': {k: v for k, v in pub.items()
                                                                                                 if k != 'sidecar_json'}})
            names = sorted(e.name for e in os.scandir(out_dir) if e.is_file()) if out_dir.is_dir() else []
            for name in names:
                if not (name.startswith(prefix) and name.endswith('.json')):
                    continue
                side = out_dir / name
                meta = self._read_sidecar(side)
                if meta is None or meta.get('job') != jid or meta.get('item') != iid:
                    continue
                out = Path((meta.get('output') or {}).get('path') or '')
                want = (meta.get('output') or {}).get('bytes')
                if out.is_file() and (want is None or out.stat().st_size == want):
                    self.log.info('published_check', f'{out.name} was already saved', job=jid, item=iid,
                                  data={'output': str(out), 'sidecar': str(side), 'via': 'sidecar'})
                    return str(out), str(side)
                self.log.warn('published_check_mismatch', f'{name} names this image but its output is missing or '
                              'incomplete; the result is saved again', job=jid, item=iid, data={'sidecar': str(side)})
        except (OSError, images.OutputError) as e:
            self.log.warn('published_check_failed', f'The output folder {out_dir} could not be checked: {e}', job=jid,
                          item=iid, data={'error': str(e), 'raise': raise_errors})
            if raise_errors:
                raise OSError(str(e)) if not isinstance(e, OSError) else e
            return None
        self.log.debug('published_check', 'No saved result found for this image', job=jid, item=iid,
                       data={'output_dir': str(out_dir), 'prefix': prefix})
        return None

    def _read_sidecar(self, path):
        try:
            meta = json.loads(Path(path).read_text(encoding='utf8'))
            return meta if isinstance(meta, dict) else None
        except ValueError as e:
            self.log.warn('sidecar_unreadable', f'The recipe file {Path(path).name} could not be read: {e}',
                          data={'path': str(path)})
            return None

    def _sidecar_matches(self, path, jid, iid):
        meta = self._read_sidecar(path)
        return meta is not None and meta.get('job') == jid and meta.get('item') == iid

    
    def _user_cancelled(self, ctx):
        if ctx.cancel.is_set():
            return True
        try:
            return self.store.item(ctx.jid, ctx.iid)['state'] in ('cancelled', 'stopped')
        except NotFound:
            return False

    def _fail_fields(self, jid, iid):
        """Where a failed image stopped and what it ran with (its last live frame is kept)."""
        at = self.live.freeze(jid, iid, 'failed')
        try:
            job = self.store.get(jid)
            it = next(x for x in job['items'] if x['id'] == iid)
            return {'at': at, 'ran_with': self._item_effective(job, it), 'ran_with_request': self._item_request(job, it),
                    'gpu': None, 'cards': []}
        except (NotFound, StopIteration):
            return {'at': at}

    def _run_item_safe(self, w, ctx):
        jid, iid = ctx.jid, ctx.iid
        try:
            self._run_item(w, ctx)
        except Cancelled:
            self._end_cancelled(w, ctx)
        except Interrupted:
            if self._user_cancelled(ctx):
                self._end_cancelled(w, ctx)
            else:
                self._end_interrupted(ctx)
        except EngineNotReady as e:
            if self._user_cancelled(ctx):
                self._end_cancelled(w, ctx)
            elif ctx.shutdown or not self.accepting:
                self._end_interrupted(ctx)
            else:
                self._record(jid, iid, state='queued', message=f'Waiting for the engine: {e}', message_log_ref=e.ref,
                             event='item_waiting', level='warn', msg=f'Waiting for the engine: {e}',
                             data={'log_ref': e.ref})
        except ItemFailure as e:
            ref = self.log.error(e.event, e.text, job=jid, item=iid, stage=self._stage_of(jid, iid), data=e.data)
            if e.kill_worker:
                w.stop(f'{e.event} (ref {ref})', kill=True)
            if self._user_cancelled(ctx):
                self._end_cancelled(w, ctx)
            else:
                self._record(jid, iid, state='failed', message=e.text, eta_s=None, error={'text': e.text, 'log_ref': ref},
                             event='item_state', msg=f'Failed: {e.text}', level='warn', data={'log_ref': ref},
                             **self._fail_fields(jid, iid))
                if not e.keep_work:
                    self._cleanup_work(jid, iid)
                self._cleanup_item_worker_files(w, jid, iid)
                self.batch.finished('failed', self._work_left(exclude=(jid, iid)))
        except StateError as e:
            if self._user_cancelled(ctx):   
                self.log.info('item_cancel_race', 'The image was cancelled while it was being started', job=jid, item=iid,
                              data={'detail': str(e)})
                self._end_cancelled(w, ctx)
            else:
                ref = self.log.exception('item_crashed', 'Unexpected state change while processing an image', e, job=jid,
                                         item=iid)
                text = f'Something went wrong while processing this image. Details are in the log (ref {ref}).'
                self._record(jid, iid, state='failed', message=text, eta_s=None, error={'text': text, 'log_ref': ref},
                             **self._fail_fields(jid, iid))
                self._cleanup_item_worker_files(w, jid, iid)
                self.batch.finished('failed', self._work_left(exclude=(jid, iid)))
        except Exception as e:   
            ref = self.log.exception('item_crashed', 'Unexpected error while processing an image', e, job=jid, item=iid)
            if self._user_cancelled(ctx):
                self._end_cancelled(w, ctx)
            else:
                text = f'Something went wrong while processing this image. Details are in the log (ref {ref}).'
                self._record(jid, iid, state='failed', message=text, eta_s=None, error={'text': text, 'log_ref': ref},
                             **self._fail_fields(jid, iid))
                self._cleanup_item_worker_files(w, jid, iid)
                self.batch.finished('failed', self._work_left(exclude=(jid, iid)))
        finally:
            self._release_worker(w, ctx)
            with self._lock:
                self.ctx.pop((jid, iid), None)
                self.threads.pop((jid, iid), None)
            self.wake()

    def _record(self, jid, iid, **kw):
        """Final state write of an item thread; a failure here is logged, never raised over the original outcome. A state
        the item cannot go to from where it is, while it is still preparing, running or finishing, would leave it there with
        no thread for the rest of the session (12 Nov, QA CONTRACT-1: 'finishing' -> 'stopped'), so it fails instead, with a
        plain sentence and the log reference; its work files are kept."""
        try:
            return self.store.update_item(jid, iid, **kw)
        except StateError as e:
            ref = self.log.exception('item_state_failed', 'Could not record the outcome of an image', e, job=jid, item=iid,
                                     data={'wanted': kw.get('state')})
            try:
                cur = self.store.item(jid, iid)['state']
            except NotFound:
                return None
            if cur not in ACTIVE:
                return None
            text = f'Something went wrong while this image was stopping. Queue it again. Details are in the log (ref {ref}).'
            try:
                return self.store.update_item(jid, iid, state='failed', message=text, eta_s=None, gpu=None, cards=[],
                                              error={'text': text, 'log_ref': ref}, stop_requested=False,
                                              event='item_state', level='warn', msg=f'Failed: {text}',
                                              data={'log_ref': ref, 'wanted': kw.get('state'), 'was': cur})
            except Exception as e2:   
                self.log.exception('item_state_failed', 'Could not record the outcome of an image', e2, job=jid, item=iid,
                                   data={'wanted': 'failed'})
                return None
        except Exception as e:   
            self.log.exception('item_state_failed', 'Could not record the outcome of an image', e, job=jid, item=iid,
                               data={'wanted': kw.get('state')})
            return None

    @staticmethod
    def _may_supersede(ctx, state, states):
        """A requeue or a settings change may take over an image whose thread is still unwinding: its stop or cancel is
        recorded (`state` in `states`) and the thread has not begun its own end writes (only waiting for its engine start).
        Called with self._lock held."""
        return ctx.cancel.is_set() and not ctx.ending and not ctx.worker_released and state in states

    def _claim_end(self, ctx):
        """The item thread is about to write how its image ended: False when a requeue took the image over meanwhile."""
        with self._lock:
            if ctx.superseded:
                return False
            ctx.ending = True
            return True

    def _end_cancelled(self, w, ctx):
        jid, iid = ctx.jid, ctx.iid
        if not self._claim_end(ctx):
            self.log.info('item_end_superseded', 'The image was queued again while its engine was starting; the new run '
                          'takes over', job=jid, item=iid)
            if not ctx.worker_released:
                self._cleanup_item_worker_files(w, jid, iid)
            return
        if ctx.stop:
            try:
                cur = self.store.item(jid, iid)
            except NotFound:
                cur = {}
            if cur.get('state') != 'cancelled' and not cur.get('cancel_requested'):   
                return self._end_stopped(w, ctx)
        self.live.drop(jid, iid)
        try:
            already = self.store.item(jid, iid)['state'] == 'cancelled'
        except NotFound:
            already = True


        self._cleanup_work(jid, iid)
        if not already:
            self._record(jid, iid, state='cancelled', message='Cancelled', eta_s=None, event='item_cancelled',
                         msg='Cancelled; unfinished files removed')
        if not ctx.worker_released:
            self._cleanup_item_worker_files(w, jid, iid)

    def _end_interrupted(self, ctx):
        self._record(ctx.jid, ctx.iid, state='interrupted', eta_s=None,
                     message='Paused because the app closed; it continues next time', event='item_interrupted',
                     level='warn', msg='Paused because the app closed; finished passes are kept')

    def _release_worker(self, w, ctx):
        with self._lock:
            if ctx.worker_released:
                return
            ctx.worker_released = True
            w.busy = False
            for g in getattr(w, 'gpus', ()):
                if g in self.workers:
                    self.workers[g].busy = False
            w.last_used = time.monotonic()
            self._rebalance_caps()
        self.wake()

    def _stage_of(self, jid, iid):
        try:
            return self.store.item(jid, iid).get('stage_index')
        except NotFound:
            return None

    def _check_cancel(self, ctx):
        if ctx.cancel.is_set():
            raise Cancelled()
        if ctx.shutdown or not self.accepting:
            raise Interrupted()

    def _check_finish_cancel(self, ctx):
        """While the result is saved: a Cancel or the app closing still ends the save, a per-image stop never does (stop_item
        refuses once the card is released; one that raced in anyway is answered by the save completing, never by an image
        left in 'finishing' with no thread: 12 Nov, QA CONTRACT-1)."""
        if ctx.cancel.is_set() and not ctx.stop:
            raise Cancelled()
        if ctx.shutdown or not self.accepting:
            raise Interrupted()

    def _active_update(self, jid, iid, **fields):
        """Field update that only applies while the item is still being worked on (never overwrites 'Cancelled')."""
        return self.store.update_item(jid, iid, if_state=ACTIVE, **fields)

    def _preflight(self, w, refresh=True):
        """Real engine only: refuse to start a worker while paths/models are missing (the item waits, health says why).
        Uses the health snapshot; a stale snapshot with problems is refreshed first when `refresh` (item threads only,
        never an HTTP thread)."""
        if self.mode != 'comfy':
            return
        probs = self.problems(engine_only=True)
        if refresh and probs and time.monotonic() - (self._snapshot() or {}).get('t', 0.0) > 5.0:
            self._refresh_health()
            probs = self.problems(engine_only=True)
        if probs:
            if w.problem != probs[0] or not w.problem_ref:      
                w.problem_ref = self.log.error('engine_not_ready', probs[0], data={
                    'gpu': w.gpu, 'problems': probs, 'details': (self._snapshot() or {}).get('details')})
            w.state, w.problem, w.preflight_failed = 'failed', probs[0], True
            w.next_start_after = time.monotonic() + 30.0
            raise EngineNotReady(probs[0], ref=w.problem_ref)

    def _run_item(self, w, ctx):
        jid, iid = ctx.jid, ctx.iid
        job = self.store.get(jid)
        it = next(x for x in job['items'] if x['id'] == iid)
        stages = it['plan']['stages']
        n = len(stages)
        params, _ = controls.resolve(self._item_request(job, it))
        work = self.cfg.work_dir / jid / iid
        k0 = int(it['stage_index'])
        run = it.get('run') or {}
        ctx.factor = float(run.get('factor') or 1.0)
        
        
        sf = run.get('stage_factors')
        ctx.stage_factors = [float(x) for x in sf] if isinstance(sf, list) and len(sf) == n and len(set(sf)) > 1 else None
        self._check_cancel(ctx)
        if k0 < n and run.get('mode') == 'fast' and not self._fast_info_to_start()['available']:
            raise ItemFailure('Fast mode is not available, so this image was not upscaled. Queue it again in Standard.',
                              event='fast_unavailable', data={'fast': self.fast_info()}, keep_work=True)
        if k0 < n and run.get('mode') == 'fast' and engine_options.fast_plan_refusal(it['plan']) == 'size':
            
            raise ItemFailure(engine_options.FAST_SIZE_FAILURE, event='fast_unavailable', data={'reason': 'size'},
                              keep_work=True)
        if k0 < n:
            src = work / ('input.png' if k0 == 0 else f'stage{k0 - 1}.png')
            if not src.is_file():
                raise ItemFailure('The work files for this image are missing. Add the image again and start a new upscale.',
                                  event='work_missing', data={'missing': str(src)})
            if w.state != 'ready' or not w.alive():
                self._active_update(jid, iid, message='Starting the engine')
            self._preflight(w)
            try:
                w.ensure_started(self._gpu_lookup() if self.mode == 'comfy' else None,
                                 abort=lambda: ctx.shutdown or not self.accepting)
            except WorkerError as e:
                self._check_cancel(ctx)
                raise EngineNotReady(str(e), ref=(e.detail or {}).get('log_ref') if isinstance(e.detail, dict) else None)
            self._check_cancel(ctx)
            timings = dict(it['timings'])
            timings.setdefault('started', now_iso())
            how = (', Fast mode' if run.get('mode') == 'fast' else ', matching earlier results' if run.get('match_earlier')
                   else ', sped up' if run.get('faster') else '')
            self._drop_kept(jid, iid)        
            self._active_update(jid, iid, timings=timings, kept_passes=None, event='item_started',
                                msg=f'Started {it["name"]} ({n} pass{"es" if n > 1 else ""}'
                                    + (f', from pass {k0 + 1})' if k0 else ')') + how,
                                data={'gpu': w.gpu, 'plan_minutes': it['plan']['minutes'], 'stage_index': k0,
                                      'run': {k: v for k, v in run.items() if k != 'minutes'}})
            for k in range(k0, n):
                self._check_cancel(ctx)
                self._run_stage(w, ctx, job, params, k, n)
        with self._lock:                  
            self._check_cancel(ctx)
            self._release_worker(w, ctx)  
        self._finish(ctx, job)

    def _run_stage(self, w, ctx, job, params, k, n):
        jid, iid = ctx.jid, ctx.iid
        it = self.store.item(jid, iid)
        st = it['plan']['stages'][k]
        f, s = _frac(st['factor']), _frac(st['supersample'])
        work = self.cfg.work_dir / jid / iid
        src = work / ('input.png' if k == 0 else f'stage{k - 1}.png')
        ow, oh = st['output_size']
        rw, rh = st['render_size']
        self._stage_disk_check(jid, iid, work, ow * oh * 3 + rw * rh * 3 // 4)
        arr = images.load_rgb(src)
        if [arr.shape[1], arr.shape[0]] != list(st['input_size']):
            raise ItemFailure('An intermediate result has an unexpected size, so this image was stopped.',
                              event='stage_input_size', data={'expected': st['input_size'], 'got': [arr.shape[1], arr.shape[0]]})
        pw, ph = st['padded_size']
        padded = images.pad_reflect(arr, (pw, ph))
        prefix = f'cu_{jid}_{iid}_s{k}'
        name = prefix + '.png'
        self._cleanup_worker_files(w, prefix, name)
        images.save_png_atomic(padded, w.input_dir / name, compress_level=1)
        pk = controls.stage_params(params, k)
        run = it.get('run') or self._run_would(None, it, self._item_mode(job, it))
        live_mode = engine_options.live_mode(self.detailed_info()['on'])
        if run.get('mode') == 'fast':      
            try:
                graph, info = fast_recipe.build(name, pw, ph, pk, prefix, f=f, s=s, live_preview=live_mode)
            except fast_recipe.FastTooLarge:
                raise ItemFailure(engine_options.FAST_SIZE_FAILURE, event='fast_unavailable', data={'reason': 'size'},
                                  keep_work=True)
            except fast_recipe.FastUnavailable:
                raise ItemFailure('Fast mode is not available, so this image was not upscaled. Queue it again in Standard.',
                                  event='fast_unavailable', keep_work=True)
        else:                              


            stack = bool(run.get('speed_stack', True))
            graph, info = graph_v5t.build_product(name, pw, ph, pk, prefix, f=f, s=s,
                                                  speed_stack=stack, live_preview=live_mode,
                                                  faster=bool(run.get('faster')) and stack
                                                  and k in engine_options.faster_stages(it['plan']),
                                                  creative_first=engine_options.creative_first_on(
                                                      shared=isinstance(w, MultiCardWorker)))
        opts = dict(info['spot_options'])
        if isinstance(w, MultiCardWorker):
            cards = [g for g in self.gpu_list()[0] if g['index'] in w.gpus]
            graph = graph_v5t.add_multigpu(graph, len(w.gpus), balance=gpu_policy.balance_mode(cards) if cards else 'auto')
            opts = dict(opts, window_split=True)
        expected = (int(round(pw * f)), int(round(ph * f)))
        if tuple(info['output']) != expected or tuple(info['render']) != (rw, rh):
            raise ItemFailure('This image was stopped because of an internal size mismatch. Details are in the log.',
                              event='graph_size_mismatch', data={'info': str(info), 'stage': st})
        atomic_write_json(work / f'stage{k}.graph.json', graph)
        timings = dict(it['timings'])
        timings['stages'] = [x for x in timings.get('stages', []) if x.get('index') != k]
        timings['stages'].append({'index': k, 'started': now_iso(), 'planned_minutes': st['minutes'], 'spot_options': opts,
                                  'fast': info.get('fast'), 'faster': info.get('faster'), 'run_order': info.get('run_order'),
                                  'live_groups': bool(getattr(w, 'live_groups', False))})
        self.store.update_item(jid, iid, state='running', stage_index=k, stage=k, stages=n, stages_done=k, stage_progress=0.0,
                               progress_estimated=False, message=f'Pass {k + 1} of {n}', timings=timings,
                               event='stage_start', msg=f'Pass {k + 1} of {n} started',
                               data={'factor': float(f), 'supersample': float(s), 'input': st['input_size'],
                                     'padded': [pw, ph], 'render': [rw, rh], 'output': [ow, oh], 'denoise': pk['denoise'],
                                     'structure': pk['structure'], 'seed': str(pk['seed']), 'nodes': len(graph),
                                     'protect_terms': pk['protect_terms'], 'graph': str(work / f'stage{k}.graph.json'),
                                     'engine_options': opts, 'run_order': info.get('run_order'),
                                     'live_groups': bool(getattr(w, 'live_groups', False))})
        canvas = self._live_begin(ctx, it, k, n, st, info, opts, arr)
        t0 = time.monotonic()
        pid = str(uuid.uuid4())
        tracker = ProgressTracker(graph, pid)

        def on_msg(obj, tracker=tracker, canvas=canvas):
            if obj.get('type') == 'claude.live':
                tracker.touch()
                data = obj.get('data') or {}
                if data.get('kind') == 'group':
                    tracker.on_group(data)     
                if canvas is not None:
                    canvas.on_frame(data, obj.get('jpeg') or b'')
            else:
                tracker.on_message(obj)
        ws = w.ws
        if ws is not None:
            ws.subscribe(pid, on_msg)      
        try:
            try:
                got = w.client.prompt(graph, w.client_id, prompt_id=pid)
            except PromptRejected as e:
                if too_large(e.detail):
                    
                    
                    raise ItemFailure(f'Pass {k + 1} of {n} is larger than the engine can take, so this image was not '
                                      'finished. Choose a smaller upscale for it.', event='prompt_too_large',
                                      data={'detail': e.detail, 'summary': rejection_text(e.detail)}, keep_work=True)
                raise ItemFailure(f'The engine could not accept pass {k + 1} of {n}: it is missing a part it needs (model or '
                                  'plug-in). Details are in the log.', event='prompt_rejected',
                                  data={'detail': e.detail, 'summary': rejection_text(e.detail)})
            except ComfyUnavailable as e:
                raise ItemFailure(f'The engine stopped answering at the start of pass {k + 1} of {n}.',
                                  event='worker_unreachable', data={'detail': e.detail}, kill_worker=True)
            if got != pid:     
                self.log.warn('prompt_id_replaced', 'The engine chose its own prompt id', job=jid, item=iid, stage=k,
                              data={'sent': pid, 'got': got})
                if ws is not None:
                    ws.unsubscribe(pid)
                    ws.subscribe(got, on_msg)
                pid = tracker.prompt_id = got
            ctx.prompt_id = pid
            self.log.info('prompt_queued', f'Pass {k + 1} of {n} sent to the engine', job=jid, item=iid, stage=k,
                          data={'prompt_id': pid, 'gpu': w.gpu})
            deadline = self.deadline_override or (3 * st['minutes'] + 10) * 60
            hist = self._wait_prompt(w, ctx, graph, pid, k, n, it['plan'], deadline, prefix, name, st, tracker)
        finally:
            if ws is not None:
                ws.unsubscribe(pid)
        out_file = self._output_file(w, hist)
        img = images.load_rgb(out_file)
        if (img.shape[1], img.shape[0]) != expected:
            raise ItemFailure(f'The engine result for pass {k + 1} of {n} has the wrong size, so this image was stopped.',
                              event='stage_output_size', data={'expected': expected, 'got': [img.shape[1], img.shape[0]]})
        images.save_png_atomic(images.crop(img, (ow, oh)), work / f'stage{k}.png', compress_level=1)
        self._cleanup_worker_files(w, prefix, name)
        secs = time.monotonic() - t0
        ratio = secs / max(1.0, st['minutes'] * 60)
        ctx.speed = ratio if ctx.speed is None else (ctx.speed + ratio) / 2
        sfs = getattr(ctx, 'stage_factors', None)
        pace = ratio / max(0.01, sfs[k] if sfs else getattr(ctx, 'factor', 1.0))   
        ctx.pace = pace if ctx.pace is None else (ctx.pace + pace) / 2
        it = self.store.item(jid, iid)
        timings = dict(it['timings'])
        for x in timings['stages']:
            if x['index'] == k:
                x.update(finished=now_iso(), seconds=round(secs, 1))
        self.store.set_job_fields(jid, speed_factor=round(ctx.speed, 4), pace=round(ctx.pace, 4))
        self.store.update_item(jid, iid, stage_index=k + 1, stage=k, stages_done=k + 1, stage_progress=0.0, timings=timings,
                               if_state=ACTIVE, event='stage_done',
                               msg=(f'Pass {k + 1} of {n} finished in {secs:.0f} s' if n > 1 else f'Upscaled {it["name"]} in {secs:.0f} s'),
                               data={'seconds': round(secs, 1), 'planned_minutes': st['minutes'], 'prompt_id': pid})

    def _spot_options(self):
        """ClaudeSpotTiles engine options a new Standard image would get now (service/engine_options.py); an image that has
        started uses its own frozen `run` (see _run_stage)."""
        st = self.settings.get()
        on = engine_options.detailed_state(st.get('detailed_preview', True), self._decoder_ok is not False)['on']
        return engine_options.spot_options(on, speed_stack=not st.get('match_earlier'))

    def detailed_info(self):
        st = self.settings.get()
        return engine_options.detailed_state(st.get('detailed_preview', True), self._decoder_ok is not False)

    def _live_begin(self, ctx, it, k, n, st, info, opts, arr):
        """The item's live canvas for stage k (None when the graph has the preview off). Never raises."""
        mode = opts.get('live_preview')
        if mode not in ('rough', 'detailed'):
            return None
        try:
            from PIL import Image
            ow, oh = st['output_size']
            pw, ph = st['padded_size']
            iw, ih = st['input_size']
            src = Image.fromarray(arr[:ih, :iw]) if arr is not None else None
            
            
            full_scale = None
            if mode == 'detailed' and engine_options.live_regions_on():
                full_scale = engine_options.live_tile_scale(getattr(ctx.worker, 'live_max_side', None), st['render_size'],
                                                            st['supersample'])
            c = self.live.begin(ctx.jid, ctx.iid, media_id=it['media_id'], stage=k, stages=n, out_size=(ow, oh),
                                supersample=float(st['supersample']), frame=it['plan']['output_size'],
                                samplers=info.get('samplers'), mode=mode, cards=list(getattr(ctx.worker, 'gpus', [ctx.worker.gpu])),
                                alpha=bool(it.get('alpha')),
                                source=src, full_scale=full_scale,
                                
                                
                                run_order=info.get('run_order'), groups=bool(getattr(ctx.worker, 'live_groups', False)))
            return c
        except Exception as e:   
            self.log.exception('live_begin_failed', 'The live preview could not be set up for this pass', e, job=ctx.jid,
                               item=ctx.iid, stage=k)
            return None

    def live_summary(self):
        """GET /api/live (contract section 2)."""
        def extra(jid, iid):
            try:
                it = self.store.item(jid, iid)
            except NotFound:
                return {}
            t = it.get('timings') or {}
            return {'eta_s': it.get('eta_s'), 'timing_elapsed_since': t.get('started')}
        out = self.live.summary(extra)
        for it in out['items']:
            since = it.pop('timing_elapsed_since', None)
            if since:
                try:
                    from datetime import datetime
                    it['timing']['elapsed_s'] = round(time.time() - datetime.fromisoformat(since).timestamp(), 1)
                except (TypeError, ValueError):
                    it['timing']['elapsed_s'] = None
            else:
                it['timing']['elapsed_s'] = None
        out['detailed'] = self.detailed_info()
        return out

    def _stage_disk_check(self, jid, iid, work, need):
        try:
            free = shutil.disk_usage(work).free
        except OSError as e:
            raise ItemFailure(f'The app work folder could not be checked ({e.strerror or e}).', event='disk_check_failed')
        if free < need + 1 * GB:
            raise ItemFailure(f'Not enough free disk space for the work files: needs about {(need + GB) / GB:.1f} GB, '
                              f'{free / GB:.1f} GB free. Free some space and start again.', event='disk_full')

    def _output_file(self, w, hist):
        for node in (hist.get('outputs') or {}).values():
            for im in node.get('images') or []:
                if im.get('type') == 'output':
                    p = w.output_dir / (im.get('subfolder') or '') / im['filename']
                    if p.is_file():
                        return p
        raise ItemFailure('The engine finished but its result file is missing.', event='output_missing',
                          data={'outputs': hist.get('outputs')})

    def stall_limit(self, graph, node, st):
        """Seconds of silence allowed while `node` runs (see SILENT_NODES)."""
        cls = graph.get(node, {}).get('class_type') if node is not None else None
        if cls not in SILENT_NODES:
            return self.stall_s
        basis, s_per_mp = SILENT_NODES[cls]
        size = {'output': st['output_size'], 'render': st['render_size'], 'input': st['padded_size']}[basis]
        return max(self.stall_s, 3.0 * s_per_mp * size[0] * size[1] / 1e6)

    def _wait_prompt(self, w, ctx, graph, pid, k, n, plan, deadline_s, prefix, input_name, st, tracker):
        jid, iid = ctx.jid, ctx.iid
        ws = w.ws
        start = time.monotonic()
        last_poll, last_store, unreachable_since, paused_logged = 0.0, 0.0, None, False
        ws_down_since = None
        gen = ws.generation if ws is not None else 0
        mins = [s_['minutes'] for s_ in plan['stages']]
        total = sum(mins) or 1.0
        shown = 0.0
        samplers = [nid for nid, nd in graph.items() if nd.get('class_type') == 'KSampler']
        sampling_from = None           
        while True:
            if ctx.cancel.is_set() or ctx.shutdown or not self.accepting:
                self._interrupt_prompt(w, ctx, pid, 'cancel' if ctx.cancel.is_set() else 'shutdown')
                self._cleanup_worker_files(w, prefix, input_name)
                if ctx.cancel.is_set():
                    raise Cancelled()
                raise Interrupted()
            if not w.alive():
                code = w.exit_code()
                raise ItemFailure(f'The engine closed unexpectedly during pass {k + 1} of {n}'
                                  + (f' (exit code {code}).' if code is not None else '.')
                                  + ' It is restarted for the next image.', event='worker_crashed',
                                  data={'exit_code': code, 'prompt_id': pid, 'log': str(w.log_file())}, kill_worker=True)
            now = time.monotonic()
            ws_ok = ws is not None and ws.connected
            every = 0.25 if tracker.finished else (10.0 if ws_ok else 2.0)
            if now - last_poll >= every:
                last_poll = now
                try:
                    h = w.client.history(pid, timeout=10.0)
                    unreachable_since = None
                    if not ws_ok:
                        tracker.touch()        
                except ComfyUnavailable as e:
                    h = None
                    unreachable_since = unreachable_since or now
                    if now - unreachable_since > self.unreachable_s:
                        raise ItemFailure(f'The engine stopped answering during pass {k + 1} of {n}. It is restarted '
                                          'for the next image.', event='worker_unreachable', data={'detail': e.detail},
                                          kill_worker=True)
                except ComfyError as e:
                    h = None
                    self.log.warn('history_error', f'History read failed: {e}', job=jid, item=iid, stage=k,
                                  data={'detail': e.detail})
                if h:
                    status = h.get('status') or {}
                    if status.get('completed') and status.get('status_str') == 'success':
                        return h
                    if status.get('status_str') == 'error':
                        raise ItemFailure(self._engine_error_text(status, k, n, plan.get('factor'),
                                                                  cards=list(getattr(w, 'gpus', ()))), event='engine_error',
                                          data={'messages': status.get('messages'), 'prompt_id': pid})
                    
            if ws_ok:
                if ws_down_since is not None or ws.generation != gen:
                    tracker.touch()            
                    gen = ws.generation
                    if paused_logged:
                        self.log.info('stall_watch_resumed', 'Progress feed back: stall watchdog running again', job=jid,
                                      item=iid, stage=k)
                paused_logged, ws_down_since = False, None
                limit = self.stall_limit(graph, tracker.current, st)
                if tracker.idle_seconds() > limit:
                    node = tracker.current
                    raise ItemFailure(f'The engine stopped making progress during pass {k + 1} of {n} (nothing for '
                                      f'{limit / 60:.0f} min). It is restarted for the next image.', event='stall',
                                      data={'idle_s': round(tracker.idle_seconds()), 'limit_s': round(limit),
                                            'node': node, 'class': graph.get(node, {}).get('class_type'),
                                            'prompt_id': pid}, kill_worker=True)
            else:
                ws_down_since = ws_down_since or now
                if not paused_logged and now - ws_down_since > 5.0:
                    self.log.warn('stall_watch_paused', 'Progress feed down: stall watchdog paused, deadline still '
                                  'applies; polling every 2 s', job=jid, item=iid, stage=k)
                    paused_logged = True
            if now - start > deadline_s:
                raise ItemFailure(f'Pass {k + 1} of {n} took far longer than expected (over {deadline_s / 60:.0f} min) '
                                  'and was stopped. The engine is restarted for the next image.', event='deadline',
                                  data={'deadline_s': deadline_s, 'prompt_id': pid}, kill_worker=True)
            if now - last_store >= 0.5:
                last_store = now
                elapsed = now - start
                frac = tracker.fraction()
                cls = graph.get(tracker.current, {}).get('class_type') if tracker.current is not None else None
                estimated = not ws_ok or cls in SILENT_NODES
                
                sfs = getattr(ctx, 'stage_factors', None)
                if sfs:            
                    planned_s = max(1.0, mins[k] * 60 * sfs[k] * (ctx.pace if ctx.pace is not None else 1.0))
                else:
                    planned_s = max(1.0, mins[k] * 60 * (ctx.speed if ctx.speed is not None else ctx.factor))
                if estimated:          
                    frac = max(frac, min(0.95, elapsed / planned_s))
                frac = shown = max(shown, frac)
                done_m = sum(mins[:k])
                overall = (done_m + frac * mins[k]) / total
                sp = tracker.node_progress(samplers)
                if sp is not None and sampling_from is None:
                    sampling_from = (now, frac)                     
                left = stage_left_s(elapsed, frac, planned_s, None if sampling_from is None else now - sampling_from[0],
                                    None if sampling_from is None else sampling_from[1], sp)
                if sfs:            
                    pace = ctx.pace if ctx.pace is not None else min(20.0, max(0.001, (elapsed + left)
                                                                              / max(1.0, mins[k] * 60 * sfs[k])))
                    eta = left + sum(m * x for m, x in zip(mins[k + 1:], sfs[k + 1:])) * 60 * pace
                else:
                    if ctx.speed is not None:
                        later = ctx.speed
                    else:          
                        later = min(20.0, max(0.001, (elapsed + left) / max(1.0, mins[k] * 60)))
                    eta = left + sum(mins[k + 1:]) * 60 * later
                self._active_update(jid, iid, stage_progress=round(frac, 4), progress=round(overall * 0.99, 4),
                                    progress_estimated=estimated, eta_s=round(eta),
                                    message=f'Pass {k + 1} of {n} · {frac * 100:.0f}%')
            tracker.changed.wait(0.25)
            tracker.changed.clear()

    def _engine_error_text(self, status, k, n, factor=None, cards=None):
        """Plain sentence for an engine error. A smaller upscale is suggested only when there is one (2x is the smallest).
        cards: the GPU numbers of a worker that holds several (one image on two cards); an out-of-memory error then names the
        card (TRIALS-R1 6.3 item 8): PyTorch says "GPU <n>" counting the worker's own cards, mapped here to the GPU's number."""
        err = next((m[1] for m in status.get('messages') or [] if isinstance(m, list) and m and m[0] == 'execution_error'), {})
        text = f"{err.get('exception_type', '')} {err.get('exception_message', '')}".lower()
        where = f' in pass {k + 1} of {n}' if n > 1 else ''   
        smaller = factor is None or float(factor) > min(controls.SCALES)
        if 'out of memory' in text or 'outofmemory' in text:
            m = re.search(r'\bgpu (\d+)\b', text) if cards and len(cards) > 1 else None
            if m is not None and int(m.group(1)) < len(cards):
                return (f'GPU {cards[int(m.group(1))] + 1} ran out of memory{where}. '
                        + ('Try a smaller upscale, or close other programs that use it.' if smaller else
                           'Close other programs that use it, then try again.'))
            return (f'The graphics card ran out of memory{where}. '
                    + ('Try a smaller upscale, or close other programs that use it.' if smaller else
                       'Close other programs that use it, then try again.'))
        if 'memoryerror' in text or 'not enough memory' in text or 'paging file' in text or 'cpuallocator' in text:
            ram = self.settings.get()['ram_cap_gb']
            return (f'The engine ran out of system memory (limit {ram:g} GB){where}. '
                    + ('Try a smaller upscale.' if smaller else 'Close other programs, then try again.'))
        if any(m[0] == 'execution_interrupted' for m in status.get('messages') or [] if isinstance(m, list) and m):
            return f'The engine stopped{where} unexpectedly.'
        return f'The engine stopped with an error{where}. Details are in the log.'

    def _interrupt_prompt(self, w, ctx, pid, reason):
        self.log.info('interrupt_sent', f'Stopping the running pass ({reason})', job=ctx.jid, item=ctx.iid,
                      data={'prompt_id': pid, 'gpu': w.gpu})
        try:
            w.client.interrupt(timeout=5.0)
            w.client.delete_queued([pid], timeout=5.0)
        except ComfyError as e:
            self.log.warn('interrupt_failed', f'Interrupt could not be sent: {e}', job=ctx.jid, item=ctx.iid)
        grace = self.shutdown_grace_s if reason == 'shutdown' else self.cancel_grace_s
        deadline = time.monotonic() + grace
        while time.monotonic() < deadline:
            if not w.alive():
                return
            try:
                if w.client.history(pid, timeout=5.0):
                    return
                q = w.client.queue(timeout=5.0)
                ids = {x[1] for x in q.get('queue_running', []) + q.get('queue_pending', []) if len(x) > 1}
                if pid not in ids:
                    return
            except ComfyError as e:
                self.log.warn('interrupt_check_failed', f'Engine state could not be read: {e}', job=ctx.jid, item=ctx.iid)
                break
            time.sleep(0.25)
        self.log.warn('interrupt_timeout', f'The pass did not stop within {grace:.0f} s; stopping the engine',
                      job=ctx.jid, item=ctx.iid, data={'prompt_id': pid})
        w.stop(f'did not stop after {reason}', kill=True)

    
    def _take_test_crash(self, kind):
        """CU_TEST_CRASH hook (fake engine only): True once per marker file, like the fake engine's faults."""
        if self.test_crash != kind:
            return False
        d = self.cfg.workers_dir / 'fake-faults'
        d.mkdir(parents=True, exist_ok=True)
        try:
            with open(d / f'test-crash-{kind}.fired', 'x', encoding='utf8') as f:
                f.write(now_iso())
            return True
        except FileExistsError:
            return False

    def _output_folder_problem(self, out_dir, need):
        """Plain reason why the output folder cannot take the result right now, else None. Raises OSError when the folder
        cannot be reached at all."""
        out_dir = Path(out_dir)
        if not out_dir.is_dir():
            if not out_dir.parent.is_dir():
                return f'the folder {out_dir} is not reachable'
            out_dir.mkdir(exist_ok=True)
        free = shutil.disk_usage(out_dir).free
        if free < need * 1.05 + 0.1 * GB:
            return (f'there is not enough free space in {out_dir} ({free / GB:.1f} GB free, about {need / GB:.1f} GB '
                    'needed). Free some space')
        return None

    def _finish_slot(self, ctx, jid, iid):
        """Runner implementation."""
        waiting = False
        while not self._finish_slots.acquire(timeout=0.5):
            self._check_finish_cancel(ctx)
            if not waiting:
                waiting = True
                self._active_update(jid, iid, message='Waiting to save (another image is being saved)')
        if waiting:
            self._active_update(jid, iid, message='Saving the result')

    def _finish(self, ctx, job):
        jid, iid = ctx.jid, ctx.iid
        if self._take_test_crash('finish'):
            self.log.warn('test_crash', 'CU_TEST_CRASH=finish: exiting now (test hook)', job=jid, item=iid)
            os._exit(70)
        it = self.store.item(jid, iid)
        plan = it['plan']
        n = len(plan['stages'])
        work = self.cfg.work_dir / jid / iid
        W, H = plan['output_size']
        self.live.set_state(jid, iid, 'finishing')
        self.store.update_item(jid, iid, state='finishing', stage=n - 1, stages=n, stages_done=n, stage_index=n,
                               stage_progress=1.0, progress=0.99, progress_estimated=False,
                               eta_s=int(round(FINISH_S_PER_MP * W * H / 1e6)) + 1, message='Saving the result',
                               event='item_finishing', msg=f'Saving {it["name"]}')
        last = work / f'stage{n - 1}.png'
        fmt = self._item_effective(job, it)['output_format']
        ext = images.OUTPUT_EXT[fmt]
        out_dir = Path(job['output_dir'])
        stem = images.safe_stem(it['name'])
        factor = plan['factor']
        need = W * H * 4 * (2 if fmt in ('png16', 'tiff16') else 1)
        waited_since, last_reason, logged_long = None, None, False
        out = side = info = out_sha = None
        result_ready = False
        while True:
            self._check_finish_cancel(ctx)
            try:
                found = self._published_check(job, self.store.item(jid, iid), raise_errors=True)
                if found:                 
                    out, side = Path(found[0]), Path(found[1])
                    meta = self._read_sidecar(side) or {}
                    info = {k: v for k, v in (meta.get('output') or {}).items() if k in ('format', 'icc', 'alpha', 'exif',
                                                                                          'bits')}
                    out_sha = (meta.get('output') or {}).get('sha256')
                    result_ready = self._make_views_from_work(jid, iid, work, W, H)
                    break
                reason = self._output_folder_problem(out_dir, need)
                if reason:
                    raise _WaitOutput(reason)
                if not last.is_file():
                    raise ItemFailure('The finished image is missing from the work folder, so it could not be saved.',
                                      event='final_missing', data={'path': str(last)})
                self._finish_slot(ctx, jid, iid)
                try:
                    out, side, info, out_sha, result_ready = self._encode_publish(ctx, job, it, work, last, out_dir, stem,
                                                                                  factor, fmt, ext, W, H)
                finally:
                    self._finish_slots.release()
                break
            except images.SidecarPending as e:
                out, info, out_sha = e.output, e.info, e.out_sha
                side, result_ready = self._wait_sidecar(ctx, e), e.result_ready
                break
            except (ItemFailure, Cancelled, Interrupted):
                raise
            except images.OutputError as e:
                raise ItemFailure(f'The result could not be named in {out_dir}: {e}.', event='output_name', keep_work=True)
            except (OSError, _WaitOutput) as e:
                now = time.monotonic()
                waited_since = waited_since or now
                plain = str(e) if isinstance(e, _WaitOutput) else f'the folder {out_dir} cannot be written to ({getattr(e, "strerror", None) or e})'
                if plain != last_reason:
                    last_reason = plain
                    self.log.warn('output_write_waiting', f'Saving waits: {plain}', job=jid, item=iid,
                                  data={'error': str(e), 'waited_s': round(now - waited_since)})
                    self._active_update(jid, iid, message=f'Waiting for the output folder: {plain}. The finished image is '
                                                          'safe and is saved as soon as the folder can be used.')
                if not logged_long and now - waited_since > self.output_wait_s:
                    logged_long = True
                    self.log.error('output_wait_long', f'Still waiting for the output folder after '
                                   f'{(now - waited_since) / 60:.0f} min: {plain}', job=jid, item=iid,
                                   data={'output_dir': str(out_dir)})
                for _ in range(int(min(15.0, max(1.0, self.output_wait_s / 4)) * 4)):
                    self._check_finish_cancel(ctx)
                    time.sleep(0.25)
        it = self.store.item(jid, iid)
        timings = dict(it['timings'], finished=now_iso())
        q = f'kind=result&job={jid}&item={iid}'
        mid = it['media_id']
        urls = {k: f'/api/media/{mid}/{k}?{q}' for k in ('thumb', 'proxy', 'region')}
        extra = {'result_urls': urls, 'result_thumb_url': urls['thumb'], 'result_proxy_url': urls['proxy'],
                 'result_region_url': urls['region']} if result_ready else {'result_urls': None}
        try:                                    
            out_bytes = Path(out).stat().st_size
        except OSError as e:
            out_bytes = None
            self.log.warn('output_size_unread', f'The size of {Path(out).name} could not be read: {e}', job=jid, item=iid)
        self.store.update_item(jid, iid, state='done', output=str(out), sidecar=str(side) if side else None, progress=1.0,
                               stage_progress=1.0, eta_s=0, message='Done' if side else 'Done (the recipe file could not '
                               'be written)', timings=timings,
                               output_info=dict(info or {}, sha256=out_sha, bytes=out_bytes, size=[W, H]),
                               result_ready=result_ready, publishing=None, stop_requested=False, **extra,
                               gpu=None, cards=[], event='item_done', msg=f'Saved {Path(out).name}',
                               data={'output': str(out), 'sidecar': str(side) if side else None, 'sha256': out_sha,
                                     **(info or {})})
        self._cleanup_work(jid, iid)
        self.live.drop(jid, iid)
        self.batch.finished('done', self._work_left(exclude=(jid, iid)))

    def _encode_publish(self, ctx, job, it, work, last, out_dir, stem, factor, fmt, ext, W, H):
        """Encode to a dot-named temp file in the output folder, publish it (sidecar first) and write the viewer copies.
        Returns (output, sidecar, info, sha256, result_ready)."""
        jid, iid = ctx.jid, ctx.iid
        rgb = images.load_rgb(last)
        if (rgb.shape[1], rgb.shape[0]) != (W, H):
            raise ItemFailure('The finished image has an unexpected size, so it was not saved.', event='final_size',
                              data={'expected': [W, H], 'got': [rgb.shape[1], rgb.shape[0]]}, keep_work=True)
        alpha = self._final_alpha(work, W, H)
        exif = (work / 'exif.bin').read_bytes() if (work / 'exif.bin').is_file() else None
        tmp = out_dir / f'.{stem}_cu{factor}x.{new_id("", 8)}.partial{ext}'
        try:
            info = images.encode(tmp, rgb, alpha, fmt, exif, software=f'Creative Upscaler {VERSION}')
            out_sha = sha256_file(tmp)
            nbytes = tmp.stat().st_size
            sidecar = self._sidecar(job, it, info, out_sha, (W, H), nbytes)
            self._check_finish_cancel(ctx)            
            
            result_ready = self._write_views(jid, iid, rgb, alpha)

            def on_reserved(path, data):
                self.store.update_item(jid, iid, publishing={'output': str(path), 'bytes': nbytes, 'sha256': out_sha,
                                                             'sidecar_json': data.decode('utf8')}, if_state={'finishing'})

            
            suffix = '_fast' if ((it.get('run') or {}).get('mode') or self._item_mode(job, it)) == 'fast' else ''
            try:
                out, side = images.reserve_and_publish(
                    tmp, out_dir, stem, factor, ext,
                    lambda p: json.dumps(dict(sidecar, output=dict(sidecar['output'], path=str(p), name=p.name)),
                                         indent=1, ensure_ascii=False).encode('utf8'),
                    on_reserved=on_reserved,
                    log_fn=lambda m: self.log.warn('temp_cleanup_failed', m, job=jid, item=iid), suffix=suffix)
            except images.SidecarPending as e:
                tmp = None
                e.info, e.out_sha, e.result_ready = info, out_sha, result_ready
                raise
            tmp = None
            return out, side, info, out_sha, result_ready
        finally:
            if tmp is not None:
                try:
                    if Path(tmp).exists():
                        Path(tmp).unlink()
                except OSError as e:
                    self.log.warn('temp_cleanup_failed', f'Temporary file {tmp} could not be removed: {e}', job=jid,
                                  item=iid)

    def _wait_sidecar(self, ctx, e):
        """The output is published but its sidecar is not: retry only the sidecar until it is written. A cancel now ends
        the image as done without the recipe file (the picture is already saved and is never deleted)."""
        jid, iid = ctx.jid, ctx.iid
        self.log.warn('sidecar_pending', f'{e.output.name} is saved but its recipe file is not yet: {e.cause}', job=jid,
                      item=iid, data={'output': str(e.output)})
        self._active_update(jid, iid, message='Saved; waiting for the output folder to write the recipe file')
        while True:
            try:
                side = images.write_sidecar(e.output, e.data,
                                            log_fn=lambda m: self.log.warn('temp_cleanup_failed', m, job=jid, item=iid))
                self.log.info('sidecar_written', f'Recipe file written for {e.output.name}', job=jid, item=iid,
                              data={'sidecar': str(side)})
                return side
            except (OSError, images.OutputError) as err:
                self.log.debug('sidecar_retry', f'Recipe file not written yet: {err}', job=jid, item=iid)
            for _ in range(60):
                if ctx.shutdown or not self.accepting:
                    raise Interrupted()
                if ctx.cancel.is_set() and not ctx.stop:
                    self.log.warn('sidecar_skipped', 'Cancelled while only the recipe file was missing; the image is kept',
                                  job=jid, item=iid, data={'output': str(e.output)})
                    return None
                time.sleep(0.25)

    def _final_alpha(self, work, W, H):
        if not (work / 'alpha.png').is_file():
            return None
        from PIL import Image
        return np.asarray(images.load_alpha(work / 'alpha.png').resize((W, H), Image.LANCZOS), dtype=np.uint8)

    def _write_views(self, jid, iid, rgb, alpha):
        try:
            self.media.write_result_views(jid, iid, rgb, alpha)
            return True
        except (OSError, ValueError) as e:
            self.log.warn('result_view_failed', f'The viewer copy of the result could not be made: {e}', job=jid, item=iid)
            return False

    def _make_views_from_work(self, jid, iid, work, W, H):
        """Viewer copies for a result found already saved (restart): from the last stage file while it is still there."""
        if self.media.result_views_ready(jid, iid):
            return True
        last = sorted(work.glob('stage*.png'))
        if not last:
            return False
        try:
            rgb = images.load_rgb(work / f'stage{len(last) - 1}.png')
            if (rgb.shape[1], rgb.shape[0]) != (W, H):
                return False
            return self._write_views(jid, iid, rgb, self._final_alpha(work, W, H))
        except OSError as e:
            self.log.warn('result_view_failed', f'The viewer copy could not be made: {e}', job=jid, item=iid)
            return False

    def ensure_result_views(self, jid, iid):
        """Viewer copies of a done item, rebuilt when missing (an item completed at a restart, or a failed copy). One build
        per item at a time; returns True when the files exist."""
        if self.media.result_views_ready(jid, iid):
            return True
        key = (jid, iid)
        with self._lock:
            ev = self._views_inflight.get(key)
            owner = ev is None
            if owner:
                ev = self._views_inflight[key] = threading.Event()
        if not owner:
            ev.wait(300.0)
            return self.media.result_views_ready(jid, iid)
        try:
            it = self.store.item(jid, iid)
            if it['state'] != 'done':
                return False
            W, H = it['plan']['output_size']
            work = self.cfg.work_dir / jid / iid
            ok = self._make_views_from_work(jid, iid, work, W, H)
            if not ok and it.get('output') and Path(it['output']).is_file():
                from PIL import Image
                with Image.open(it['output']) as im:
                    im.load()
                    alpha = np.asarray(im.getchannel('A'), dtype=np.uint8) if 'A' in im.getbands() else None
                    rgb = np.asarray(im.convert('RGB'), dtype=np.uint8)
                ok = self._write_views(jid, iid, rgb, alpha)
            if ok:
                q = f'kind=result&job={jid}&item={iid}'
                urls = {k: f'/api/media/{it["media_id"]}/{k}?{q}' for k in ('thumb', 'proxy', 'region')}
                self.store.update_item(jid, iid, result_ready=True, result_urls=urls, result_thumb_url=urls['thumb'],
                                       result_proxy_url=urls['proxy'], result_region_url=urls['region'], if_state={'done'},
                                       event='result_views_rebuilt', msg='Viewer copy of the result made again')
                if work.exists():
                    self._cleanup_work(jid, iid)
            return ok
        except (OSError, ValueError, NotFound) as e:
            self.log.warn('result_view_failed', f'The viewer copy of the result could not be made again: {e}', job=jid,
                          item=iid)
            return False
        finally:
            with self._lock:
                self._views_inflight.pop(key, None)
            ev.set()

    def _views_safe(self, jid, iid):
        try:
            self.ensure_result_views(jid, iid)
        except Exception as e:   
            self.log.exception('result_view_failed', 'The viewer copy of a recovered result could not be made', e, job=jid,
                               item=iid)

    def _sidecar(self, job, it, info, out_sha, size, nbytes=None):
        eff = dict(self._item_effective(job, it))
        eff.setdefault('mode', 'standard')
        params, _ = controls.resolve(self._item_request(job, it))
        from service.store import run_view
        run = run_view(it, eff, self._run_would)          
        stages = sorted((it.get('timings') or {}).get('stages') or [], key=lambda x: x.get('index', 0))
        used = stages[-1].get('spot_options') if stages else None     
        fast = next((x.get('fast') for x in reversed(stages) if x.get('fast')), None)
        faster_stages = [x.get('index') for x in stages if x.get('faster')]
        faster = (dict(next(x['faster'] for x in stages if x.get('faster')), stages=faster_stages) if faster_stages
                  else None)
        return {
            'app': SERVICE, 'app_version': VERSION, 'service_contract': API_CONTRACT, 'contract': controls.CONTRACT,
            'job': job['id'], 'item': it['id'], 'created': now_iso(),
            'source': {'path': it['source'], 'name': it['name'], 'sha256': it['sha256'], 'size': it['size'],
                       'format': it['format'], 'bit_depth': it['bit_depth'], 'alpha': it['alpha']},
            'effective': eff, 'plan': it['plan'], 'seed': eff['seed'],
            'stage_seeds': [str(controls.stage_params(params, k)['seed']) for k in range(len(it['plan']['stages']))],
            'timings': it['timings'],
            'node_pack': {'sha256': self.node_pack.get('tree_sha256'), 'files': self.node_pack.get('files')},
            'run': run,
            'engine': {'mode': self.mode, 'graph': 'engine/fast_recipe.py' if fast else 'engine/graph_v5t.py',
                       'models': graph_v5t.MODELS, 'speed_stack': bool(run.get('speed_stack')), 'fast': fast,
                       'faster': faster,
                       'spot_options': used if used is not None else self._spot_options()},
            'input_sha256': it['sha256'], 'output_sha256': out_sha,
            'output': {'path': None, 'name': None, 'sha256': out_sha, 'bytes': nbytes, 'size': list(size), **info},
            'notes': it.get('notes') or [],
        }

    
    def mask_preview(self, media_id, protect=None, quick=None):
        if not self.accepting:
            raise ApiError(503, 'shutting_down', 'The app is closing. Try again in a moment.')
        try:
            rec = self.media.get(media_id)
        except KeyError:
            raise ApiError(404, 'unknown_image', 'This image is not in the list any more. Add it again.')
        req = {}
        if protect is not None:
            req['protect'] = protect
        if quick:
            req['quick_protect'] = quick
        try:
            params, eff = controls.resolve(req)
        except controls.ControlError as e:
            raise ApiError(400, 'bad_settings', plain_control_error(e), data={'detail': str(e)})
        terms = params['protect_terms']
        release = params.get('release_terms') or []
        key = sha256_bytes(canonical_json({'terms': terms, 'release': release, 'sam': params['protect'], 'gate': 'exact-v1',
                                           'image': rec['sha256']}))[:12]
        path = self.media.mask_file(media_id, key)
        result = {'mask_url': f'/api/media/{media_id}/mask/{key}', 'terms': terms, 'release_terms': release,
                  'categories': eff['protect'], 'quick_protect': eff['quick_protect']}
        if path.is_file():
            return dict(result, cached=True)
        from PIL import Image
        if not terms:
            with Image.open(self.media.path(media_id, 'proxy.jpg')) as im:
                size = im.size
            images.save_atomic(Image.new('L', size, 0), path, 'PNG')
            return dict(result, cached=False)
        flight_key = (media_id, key)
        with self._lock:
            ev = self._mask_inflight.get(flight_key)
            owner = ev is None
            if owner:
                ev = self._mask_inflight[flight_key] = threading.Event()
        if not owner:     
            if not ev.wait(150.0):
                raise ApiError(503, 'mask_pending', 'The protected-area preview is still being made. Try again in a moment.')
            if path.is_file():
                return dict(result, cached=True)
            raise ApiError(503, 'mask_failed', 'The protected-area preview could not be made. Try again.')
        try:
            self._mask_preview_run(media_id, key, terms, params, path)
        finally:
            with self._lock:
                self._mask_inflight.pop(flight_key, None)
            ev.set()
        return dict(result, cached=False)

    def _claim_worker_wait(self):
        """A free worker for a mask preview. While it waits (up to CU_MASK_CLAIM_SECONDS) the scheduler holds the next image,
        so the preview gets the first worker that comes free."""
        deadline = time.monotonic() + self.mask_claim_s
        with self._lock:
            self._mask_waiting += 1
        try:
            while True:
                w = self._claim_worker()
                if w is not None or time.monotonic() >= deadline or not self.accepting:
                    return w
                time.sleep(0.25)
        finally:
            with self._lock:
                self._mask_waiting -= 1
            self.wake()

    def _mask_preview_run(self, media_id, key, terms, params, path):
        from PIL import Image
        w = self._claim_worker_wait()
        if w is None:
            raise ApiError(503, 'engine_busy', 'The protected-area preview cannot run while images are being upscaled. Try '
                                               'again when the queue has finished.')
        prefix = f'cu_mask_{media_id}_{key}'
        name = prefix + '.png'
        pid = None
        try:
            try:
                self._preflight(w, refresh=False)
                w.ensure_started(self._gpu_lookup() if self.mode == 'comfy' else None, abort=lambda: not self.accepting)
                link_or_copy(self.media.path(media_id, 'source.png'), w.input_dir / name)
                graph = mask_graph.build(name, terms, params['protect'], prefix, release_terms=params.get('release_terms') or [])
                pid = str(uuid.uuid4())
                pid = w.client.prompt(graph, w.client_id, prompt_id=pid)
                self.log.info('mask_preview_started', 'Finding protected areas', data={'media': media_id, 'terms': terms,
                                                                                       'prompt_id': pid})
                h = self._wait_simple(w, pid, timeout=600.0)
                out = self._output_file(w, h)
                with Image.open(out) as im:
                    m = im.convert('L')
                m = images.mask_proxy(m)   
                images.save_atomic(m, path, 'PNG')
                self.log.info('mask_preview_done', 'Protected-area preview ready', data={'media': media_id, 'key': key})
            except EngineNotReady as e:
                raise ApiError(503, 'engine_not_ready', str(e), ref=e.ref)
            except WorkerError as e:
                ref = (e.detail or {}).get('log_ref') if isinstance(e.detail, dict) else None
                raise ApiError(503, 'engine_not_ready', str(e), ref=ref)
            except ItemFailure as e:
                ref = self.log.error(e.event, e.text, data=dict(e.data, media=media_id, prompt_id=pid))
                if e.kill_worker:
                    w.stop(f'mask preview {e.event}', kill=True)
                elif pid is not None:
                    self._interrupt_quiet(w, pid)
                raise ApiError(502, 'engine_error', e.text, ref=ref)
            except PromptRejected as e:
                ref = self.log.error('mask_prompt_rejected', 'The engine refused the protected-area preview',
                                     data={'summary': rejection_text(e.detail), 'detail': e.detail})
                raise ApiError(502, 'engine_error', 'The engine is missing a part it needs (model or plug-in). Details are in '
                                                    'the log.', ref=ref)
            except ComfyError as e:
                ref = self.log.error('mask_engine_error', f'Protected-area preview: {e}', data={'detail': str(e.detail),
                                                                                                 'prompt_id': pid})
                if pid is not None:
                    self._interrupt_quiet(w, pid)   
                raise ApiError(502, 'engine_error', 'The engine stopped answering during the protected-area preview.',
                               ref=ref)
        finally:
            with self._lock:                  
                w.busy = False
                w.last_used = time.monotonic()
            self._cleanup_worker_files(w, prefix, name)
            self.wake()

    def _interrupt_quiet(self, w, pid):
        try:
            if w.client is not None:
                w.client.interrupt(timeout=5.0)
                w.client.delete_queued([pid], timeout=5.0)
        except ComfyError as e:
            self.log.warn('interrupt_failed', f'The preview could not be stopped: {e}', data={'prompt_id': pid})

    def _claim_worker(self):
        """A free one-card engine for a mask preview. A card a shared engine holds is never given a second engine: a card
        whose shared engine is idle is preferred last, and that engine is stopped first, as the lanes' dispatch does (12 Nov,
        QA LIFECYCLE-5 / Q-15: since the split is on, a preview after a shared image started a lane engine on card 1 while the
        warm shared engine still held it, two models on one card)."""
        with self._lock:
            self._sync_workers()
            held = {}                              
            for key, mw in self.multi.items():
                if mw.busy or mw.state in ('ready', 'starting', 'stopping') or mw.proc is not None or mw.fake is not None:
                    for g in mw.gpus:
                        held.setdefault(g, []).append(key)
            cands = sorted(self.workers.values(), key=lambda w: (w.gpu in held, w.state != 'ready', w.gpu))
            for w in cands:
                if w.busy or (w.state == 'failed' and time.monotonic() < w.next_start_after):
                    continue
                keys = held.get(w.gpu, [])
                if any(self.multi[k].busy for k in keys):
                    continue                       
                for key in keys:
                    mw = self.multi.pop(key)
                    mw.stop(f'the protected-area preview needs GPU {w.gpu + 1}')
                w.busy = True
                return w
        return None

    def _wait_simple(self, w, pid, timeout):
        t0 = time.monotonic()
        while time.monotonic() - t0 < timeout:
            if not w.alive():
                raise ItemFailure('The engine closed unexpectedly during the protected-area preview.', event='worker_crashed',
                                  kill_worker=True)
            h = w.client.history(pid, timeout=10.0)
            if h:
                status = h.get('status') or {}
                if status.get('completed') and status.get('status_str') == 'success':
                    return h
                if status.get('status_str') == 'error':
                    raise ItemFailure('The engine stopped with an error during the protected-area preview.',
                                      event='engine_error', data={'messages': status.get('messages')})
            time.sleep(0.25)
        raise ItemFailure('The protected-area preview took too long and was stopped.', event='deadline', kill_worker=True)

    
    def _snapshot(self):
        with self._snap_lock:
            return self._snap

    def invalidate_problems(self):
        """Ask the health-probe thread for a fresh snapshot now (after a settings change)."""
        self._snap_wake.set()

    def _refresh_health(self):
        """Path checks (network drive, node pack hashes) -> snapshot. One refresh at a time; never on an HTTP thread."""
        started = time.monotonic()
        with self._refresh_lock:
            snap = self._snapshot()
            if snap is not None and snap['t'] >= started:
                return snap               
            details = []
            out_dir = self.settings.get()['output_dir']
            probs = config.problems(self.cfg, output_dir=None, details=details)
            out_problem = config.output_dir_problem(out_dir)
            if self.mode == 'comfy':
                ok = engine_options.decoder_path(self.cfg.vae_approx_dir).is_file()
                if ok != self._decoder_ok:
                    self.log.log('info' if ok else 'warn', 'live_decoder', 'The detailed live preview can be used' if ok else
                                 'The detailed live preview cannot be used: its decoder file cannot be read; the rough preview '
                                 'is used', data={'path': str(engine_options.decoder_path(self.cfg.vae_approx_dir))})
                self._decoder_ok = ok
            else:
                self._decoder_ok = True
            self._fast_files_ok = self._fast_files_check()
            new = {'t': time.monotonic(), 'checked_at': now_iso(), 'problems': probs, 'output_dir': out_dir,
                   'output_problem': out_problem, 'details': details}
            old = snap or {}
            if old.get('problems') != probs or old.get('output_problem') != out_problem:
                level = 'warn' if probs or out_problem else 'info'
                self.log.log(level, 'health_changed', ('Problems found: ' + ' '.join(probs + ([out_problem] if out_problem
                                                                                              else [])))
                             if level == 'warn' else 'All checks passed', data={'problems': probs, 'details': details,
                                                                                 'output_problem': out_problem})
            with self._snap_lock:
                self._snap = new
            self._snap_ready.set()
            return new

    def _fast_files_check(self):
        """The installed Fast recipe's model files can be read in the product models folder (real engine), and its LoRA is
        the file the proof rendered: the first one the engine would find (models_dir, then claude_models_dir) has the
        recipe's size and sha256 (FASTMODE-R3 5.2; hashed once per change of its size or time, in this background probe).
        True when no recipe is installed, while Fast is not offered (its proof has not passed: nothing is read), or with the
        fake engine. A missing or wrong file is logged once per change."""
        if not self._fast_check_due():
            return True
        d = fast_recipe.describe()
        bases = (self.cfg.models_dir, self.cfg.claude_models_dir)      
        missing, wrong = [], []
        for folder, names in d['models'].items():
            for name in names:
                found = next((Path(b) / folder / name for b in bases if (Path(b) / folder / name).is_file()), None)
                if found is None:
                    missing.append(f'{folder}/{name}')
                    continue
                lora = d.get('lora')
                if lora and name == lora['file']:
                    why = self._fast_file_mismatch(found, lora)
                    if why:
                        wrong.append({'path': str(found), 'problem': why})
        ok = not missing and not wrong
        if ok != self._fast_files_ok:
            self.log.log('info' if ok else 'warn', 'fast_files', 'Fast mode can be used' if ok else
                         'Fast mode cannot be used: a file it needs cannot be read', data={'missing': missing, 'wrong': wrong})
        return ok

    def _fast_file_mismatch(self, path, want):
        """None when `path` has the size and sha256 `want` names, else the developer reason (the hash is kept per size and
        modification time, so an unchanged file on the NAS is read once per process)."""
        try:
            st = path.stat()
        except OSError as e:
            return f'cannot be read ({e})'
        if st.st_size != int(want['bytes']):
            return f'{st.st_size} bytes, the recipe names {want["bytes"]}'
        key = (str(path), st.st_size, st.st_mtime_ns)
        if key not in self._fast_hashes:
            try:
                self._fast_hashes = {key: sha256_file(path)}
            except OSError as e:
                return f'cannot be read ({e})'
        got = self._fast_hashes[key]
        return None if got == want['sha256'] else f'sha256 {got}, the recipe names {want["sha256"]}'

    def _health_loop(self):
        next_gpu = 0.0
        threading.Thread(target=self.notifier.check, name='notify-check', daemon=True).start()
        while not self._stop.is_set():
            try:
                self._refresh_health()
                now = time.monotonic()
                if self.mode == 'comfy' and now >= next_gpu:
                    _, problem = self._refresh_gpus()
                    busy = any(w.state == 'ready' for w in list(self.workers.values()))
                    next_gpu = now + (HEALTH_INTERVAL_S if busy or problem or not self.gpu_list()[0] else 120.0)
                    self._vram_update()
                self.media.decoded.evict_idle()
                if self._last_sweep is None or now - self._last_sweep > SWEEP_INTERVAL_S:
                    self._last_sweep = now          
                    threading.Thread(target=self._sweep_safe, name='housekeeping', daemon=True).start()
            except Exception as e:   
                self.log.exception('health_probe_error', 'The health check hit an error and carries on', e)
            self._snap_wake.wait(HEALTH_INTERVAL_S)
            self._snap_wake.clear()

    def _vram_update(self):
        """After an nvidia-smi run (health-probe thread): each worker's free graphics memory, read for every card it holds (a
        multi-card worker holds several), and what this app's own engines hold on each card (their torch reservation from
        /system_stats), which the split's free-memory floor counts as free (_split_cards)."""
        by_index = {g['index']: g for g in self.gpu_list()[0]}
        held = {}
        for w in list(self.workers.values()) + list(self.multi.values()):
            cards = list(getattr(w, 'gpus', (w.gpu,)))
            rows = [by_index[c] for c in cards if c in by_index]
            if not rows:
                continue
            w.vram_free_gb = rows[0]['mem_free_gb']
            w.vram_free_by_card = {r['index']: r['mem_free_gb'] for r in rows}
            for r in rows:
                if w.busy and r['mem_free_gb'] < 1.0:
                    self.log.warn('vram_low', f'Graphics card {r["index"] + 1} has only {r["mem_free_gb"]:.1f} GB of its own '
                                  'memory free', data={'gpu': r['index'], 'worker': cards, **r})
            client = w.client
            if w.state != 'ready' or client is None:
                continue
            try:
                devices = client.system_stats(timeout=5.0).get('devices') or []
            except ComfyError:
                continue
            for c, dev in zip(cards, devices):
                held[c] = held.get(c, 0.0) + float(dev.get('torch_vram_total') or 0.0) / GB
        self._held_vram = {c: round(v, 2) for c, v in held.items()}

    def problems(self, engine_only=False):
        """Plain problems from the last snapshot (no file system access here)."""
        snap = self._snapshot()
        if snap is None:
            return []
        probs = list(snap['problems'])
        if not engine_only and snap['output_problem']:
            probs.append(snap['output_problem'])
        return probs

    def output_dir_status(self):
        """(writable, plain problem) of the configured output folder from the snapshot."""
        snap = self._snapshot()
        if snap is None or snap['output_dir'] != self.settings.get()['output_dir']:
            return None, None              
        return snap['output_problem'] is None, snap['output_problem']

    @staticmethod
    def _worker_state(w):
        if w.state == 'ready':
            return 'working' if w.busy else 'idle'
        if w.state == 'stopped' and w.busy:
            return 'starting'
        return w.state

    def health(self):
        if not self._snap_ready.is_set():
            self._snap_ready.wait(2.0)    
        snap = self._snapshot()
        probs = self.problems()
        probs += self.store.load_problems
        if self.store.save_problem:
            probs.append(self.store.save_problem)
        if self.settings.load_problem:
            probs.append(self.settings.load_problem)
        gpus, gpu_problem = self.gpu_list()
        if gpu_problem and gpu_problem not in probs:
            probs.append(gpu_problem)
        by_index = {g['index']: g for g in gpus}
        settings = self.settings.get()
        enabled = settings['gpus']
        with self._lock:
            workers = []
            for g in enabled:
                w = lane = self.workers.get(g)


                shared = next((m for m in self.multi.values() if g in m.gpus and m.state != 'stopped'), None)
                if shared is not None and (lane is None or lane.state == 'stopped'):
                    w = shared
                vram = by_index.get(g, {}).get('mem_free_gb')
                if w is None:
                    workers.append({'gpu': g, 'name': by_index.get(g, {}).get('name', f'Graphics card {g + 1}'), 'state': 'stopped',
                                    'vram_free_gb': vram, 'busy': False, 'port': None, 'pid': None, 'starts': 0,
                                    'problem': None, 'log_ref': None, 'mode': self.mode, 'memory_cap_gb': None,
                                    'job_id': None, 'item_id': None, 'media_id': None, 'cards': [g]})
                    continue
                i = w.info()
                i['state'] = self._worker_state(w)
                on = next(((j, x) for (j, x), c in self.ctx.items() if not c.worker_released
                           and (c.worker is w or w.gpu in getattr(c.worker, 'gpus', ()))), None)
                if on is not None:
                    try:
                        mid = self.store.item(*on)['media_id']
                    except NotFound:
                        mid = None
                    i.update(job_id=on[0], item_id=on[1], media_id=mid)
                else:
                    i.update(job_id=None, item_id=None, media_id=None)
                i['cards'] = [w.gpu]
                if w is shared:                   
                    i.pop('gpus', None)
                    i.update(gpu=g, cards=list(shared.gpus),
                             name=lane.name if lane is not None else by_index.get(g, {}).get('name', f'Graphics card {g + 1}'))
                if on is not None and isinstance(self.ctx[on].worker, MultiCardWorker):
                    i['cards'] = list(self.ctx[on].worker.gpus)
                    i['state'] = 'working'
                i['problem'] = w.problem if w.state == 'failed' else None
                i['log_ref'] = w.problem_ref if w.state == 'failed' else None
                if self.mode == 'comfy':
                    if g in by_index:
                        i['name'] = by_index[g]['name']
                    if vram is not None:
                        i['vram_free_gb'] = vram
                workers.append(i)
                if i['problem'] and i['problem'] not in probs:
                    probs.append(i['problem'])
            active = len(self.ctx)
        engine_problems = self.problems(engine_only=True) + ([gpu_problem] if gpu_problem else [])
        lc = self.lifecycle.info() if self.lifecycle is not None else None
        if lc is not None:
            lc['notify'] = self.notifier.info()
        proven = self._split_proven()
        split = engine_options.split_info(
            bool(settings['split']), list(enabled), self._split_cards(), proven=proven,
            match_earlier=bool(settings.get('match_earlier')), earlier_proven=self._split_earlier_proven(),
            floor_gb=gpu_policy.MIN_SPLIT_FREE_VRAM_GB, topology=None if self._topology is None else
            {'mode': self._topology.mode, 'workers': [list(x) for x in self._topology.workers]})
        fast = self.fast_info()
        faster = self.faster_info()
        return {'ok': not probs and snap is not None, 'service': SERVICE, 'version': VERSION, 'contract': API_CONTRACT,
                'features': {'live': True, 'stop_image': True, 'requeue': True, 'item_settings': True, 'alpha_kept': True,
                             'notify': True, 'hold_sleep': True, 'split': proven, 'match_earlier': True,
                             'fast': fast['available'], 'faster': faster['available'],
                             
                             
                             'sized_proxy': True, 'live_regions': engine_options.live_regions_on(),
                             
                             **engine_options.live_switches()},
                'controls_contract': controls.CONTRACT, 'pid': os.getpid(), 'port': self.port,
                'fake_engine': self.cfg.fake_engine, 'checked_at': snap['checked_at'] if snap else None,
                'checking': snap is None,
                'engine': {'ready': snap is not None and not engine_problems and self.accepting, 'mode': self.mode,
                           'workers': workers, 'active_items': active,
                           'node_pack_sha256': self.node_pack.get('tree_sha256'),
                           'gpus_chosen': bool(settings['gpus_chosen']), 'ram_cap_gb': settings['ram_cap_gb'],
                           'sleep_held': self._sleep_held,
                           'speed': engine_options.speed_info(bool(settings.get('match_earlier')), split['on'],
                                                              fast_available=fast['available'], faster=faster),
                           'live': dict(self.detailed_info(), **engine_options.live_switches()), 'split': split,
                           'fast': fast, 'faster': faster},
                'lifecycle': lc,
                'problems': probs}

    
    def _sweep_safe(self):
        try:
            self.sweep()
        except Exception as e:   
            self.log.exception('sweep_failed', 'Housekeeping hit an error', e)

    def sweep(self):
        """Remove leftovers (see module docstring). Only files this service names are touched; every removal is logged."""
        removed = {'work': 0, 'worker_files': 0, 'partials': 0, 'views': 0, 'job_logs': 0}
        jobs = {jid: self.store.get(jid) for jid in self.store.job_ids()}
        with self._lock:
            busy = set(self.ctx)
        now = time.time()

        def rm(path, kind):
            try:
                if Path(path).is_dir():
                    shutil.rmtree(path)
                else:
                    Path(path).unlink()
                removed[kind] += 1
            except OSError as e:
                self.log.warn('sweep_remove_failed', f'{path} could not be removed: {e}', data={'path': str(path)})

        try:
            for d in list(self.cfg.work_dir.iterdir()):
                job = jobs.get(d.name)
                if job is None:
                    if d.is_dir() and now - d.stat().st_mtime > 600:    
                        rm(d, 'work')
                    continue
                states = {it['id']: it['state'] for it in job['items']}
                for sub in list(d.iterdir()):
                    st = states.get(sub.name)
                    if (d.name, sub.name) in busy:
                        continue
                    if st is None or st in ('done', 'cancelled') or (st in ('failed', 'stopped')
                                                                       and now - sub.stat().st_mtime > FAILED_WORK_KEEP_S):
                        rm(sub, 'work')
                if d.exists() and not any(d.iterdir()):
                    rm(d, 'work')
            masks_busy = bool(self._mask_inflight)
            for wd in self.cfg.workers_dir.glob('gpu*'):
                for sub in ('input', 'output'):
                    for p in (wd / sub).glob('cu_*') if (wd / sub).is_dir() else []:
                        m = WORKER_FILE_RE.match(p.name)
                        if (m and (m.group(1), m.group(2)) in busy) or (p.name.startswith('cu_mask_') and masks_busy):
                            continue
                        if now - p.stat().st_mtime > 300:
                            rm(p, 'worker_files')
            results = self.cfg.media_dir / 'results'
            for d in list(results.iterdir()) if results.is_dir() else []:
                if d.name.split('_')[0] not in jobs:
                    rm(d, 'views')
            for p in self.cfg.jobs_dir.glob('j*.jsonl'):
                job = jobs.get(p.stem)
                if (job is None or job['state'] in TERMINAL) and now - p.stat().st_mtime > JOB_LOG_KEEP_S:
                    rm(p, 'job_logs')
            folders = {str(Path(j['output_dir'])) for j in jobs.values()} | {self.settings.get()['output_dir']}
            for folder in folders:
                try:
                    names = [e for e in os.scandir(folder) if e.is_file()] if Path(folder).is_dir() else []
                except OSError as e:
                    self.log.debug('sweep_skip', f'Output folder {folder} not checked: {e}')
                    continue
                for e in names:
                    if (PARTIAL_RE.match(e.name) or SIDECAR_TMP_RE.match(e.name)) and now - e.stat().st_mtime > 3600:
                        rm(e.path, 'partials')
        except OSError as e:
            self.log.warn('sweep_failed', f'Housekeeping stopped early: {e}')
        if any(removed.values()):
            self.log.info('sweep_done', 'Old temporary files removed', data=removed)
        return removed

    
    def open_path(self, path):
        if not isinstance(path, str) or not path.strip():
            raise ApiError(400, 'bad_request', 'Send the path of an output file or folder.')
        p = Path(path)
        configured = Path(self.settings.get()['output_dir'])
        try:
            real = p.resolve(strict=True)
        except (OSError, RuntimeError):
            if str(p).rstrip('\\/').lower() == str(configured).rstrip('\\/').lower():
                raise ApiError(404, 'not_found', 'The output folder has not been created yet. It is created when the first '
                                                 'image is saved.')
            raise ApiError(404, 'not_found', 'That file or folder no longer exists.')
        files, folders = self.store.output_paths()
        folders.add(str(configured.resolve()).lower())   
        key = str(real).lower()
        if real.is_file():
            if key not in files:
                raise ApiError(403, 'not_allowed', 'Only results written by Creative Upscaler can be opened from here.')
            how = 'select'
        else:
            if key not in folders:
                raise ApiError(403, 'not_allowed', 'Only output folders that Creative Upscaler wrote to can be opened here.')
            how = 'folder'
        self.log.info('open_path', f'Opening {real} in Explorer ({how})', data={'path': str(real), 'dryrun': self.open_dryrun})
        if not self.open_dryrun:
            if how == 'select':
                os.startfile('explorer.exe', arguments=f'/select,"{real}"')
            else:
                os.startfile(str(real))
        return {'opened': str(real), 'how': how, 'dryrun': self.open_dryrun}
