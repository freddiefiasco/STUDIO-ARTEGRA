"""Store implementation."""


import copy
import json
import re
import threading
import time
from pathlib import Path

from service.util import atomic_write_json, now_iso, read_json, same_record

STATES = ('queued', 'preparing', 'running', 'finishing', 'done', 'failed', 'cancelled', 'interrupted', 'stopped')
ACTIVE = frozenset({'preparing', 'running', 'finishing'})
TERMINAL = frozenset({'done', 'failed', 'cancelled'})
WAITING = frozenset({'queued', 'interrupted'})
TRANSITIONS = {
    'queued': {'preparing', 'cancelled', 'failed', 'stopped'},
    'preparing': {'running', 'finishing', 'queued', 'failed', 'cancelled', 'interrupted', 'stopped'},
    'running': {'running', 'finishing', 'failed', 'cancelled', 'interrupted', 'stopped'},
    'finishing': {'done', 'failed', 'cancelled', 'interrupted'},
    'interrupted': {'queued', 'done', 'failed', 'cancelled', 'stopped'},
    'stopped': {'queued', 'cancelled'},
    'done': set(), 'failed': {'queued'}, 'cancelled': {'queued'},
}
JOB_ID_RE = re.compile(r'^j[0-9a-f]{12}$')
REQUEST_ID_RE = re.compile(r'^[0-9a-f]{32}$')
PROGRESS_FIELDS = frozenset({'stage_progress', 'progress', 'eta_s', 'message'})


class StateError(RuntimeError):
    pass


class Conflict(Exception):
    pass


class NotFound(KeyError):
    pass


def check_transition(old, new):
    if new not in STATES:
        raise StateError(f'unknown state {new!r}')
    if new not in TRANSITIONS[old]:
        raise StateError(f'illegal transition {old} -> {new}')


def derive_job_state(items):
    states = [it['state'] for it in items]
    if any(s in ACTIVE for s in states):
        return 'running'
    if any(s in ('queued', 'interrupted') for s in states):
        return 'running' if any(s in TERMINAL or s == 'stopped' for s in states) else 'queued'
    if any(s == 'stopped' for s in states):
        return 'stopped'
    if all(s == 'done' for s in states):
        return 'done'
    if any(s == 'failed' for s in states):
        return 'failed'
    return 'cancelled'


def summarise(job, parallelism=1):
    """Derived fields for the API: counts, overall progress (weighted by planned minutes) and the remaining time. With two
    GPUs two images run at once, so the remaining work is divided by the number of images that can run in parallel."""
    counts = {s: 0 for s in STATES}
    total_w, done_w, eta, open_items = 0.0, 0.0, 0.0, 0
    for it in job['items']:
        counts[it['state']] += 1
        w = max(0.1, float(it['plan'].get('minutes') or 1.0))
        total_w += w
        if it['state'] in TERMINAL or it['state'] == 'stopped':
            done_w += w
        else:
            open_items += 1
            done_w += w * float(it.get('progress') or 0.0)
            if it.get('eta_s') is not None:
                eta += float(it['eta_s'])
            else:
                eta += w * 60 * waiting_factor(job, it)
    eta /= max(1, min(int(parallelism or 1), open_items))
    return {'counts': {k: v for k, v in counts.items() if v}, 'total': len(job['items']),
            'progress': round(done_w / total_w, 4) if total_w else 1.0,
            'eta_s': None if job['state'] in TERMINAL or job['state'] == 'stopped' else round(eta)}


def waiting_factor(job, it):
    """What a waiting image's planned minutes are multiplied by for the ETA: its own finish-time factor (`run.factor`: the
    mode, "Match earlier results", the cards) times the job's measured pace (actual / expected time of the passes finished so
    far; 1.0 before any). Records written before the port have only `speed_factor` (actual / planned) or `eta_factor`."""
    factor = (it.get('run') or {}).get('factor')
    if factor is None:
        return job.get('speed_factor', job.get('eta_factor', 1.0))
    if job.get('pace') is not None:
        return factor * float(job['pace'])
    return factor


def run_view(it, effective, run_fn=None, job=None, waiting=None):
    """The item's `run` for the API (contract part 2, section 1): the frozen record of an image that has started, else what
    it would run with now (run_fn, from Settings), with `minutes` = the planner's minutes times the factor. An image that
    waits to start from its source again (queued again with new settings, or sent back to the queue before its first pass
    began) will take Settings as they are when it starts, so it reads as not frozen; one that goes on from finished passes
    keeps its record. waiting: the number of images in the queue, passed on to run_fn (the cards a waiting image would
    get depend on it; 13 Nov, FAST PORT FIX, FC3)."""
    run = it.get('run')
    from_source = it.get('state') in WAITING and int(it.get('stage_index') or 0) == 0
    if not (isinstance(run, dict) and run.get('frozen')) or from_source:
        mode = (effective or {}).get('mode', 'standard')
        if run_fn is None:
            run = None
        else:
            run = run_fn(job, it, mode, waiting=waiting) if waiting is not None else run_fn(job, it, mode)
        if run is None:
            run = {'mode': mode, 'match_earlier': False, 'speed_stack': True, 'frozen': False, 'split': False, 'factor': None}
    run = dict(run)
    minutes = (it.get('plan') or {}).get('minutes')
    run['minutes'] = None if run.get('factor') is None or minutes is None else round(float(minutes) * run['factor'], 1)
    return run


def transparency(item, effective):
    """'kept' / 'not_kept' / 'none' for an image's alpha with its output format (preview design; the finish re-attaches the alpha)."""
    if not item.get('alpha'):
        return 'none'
    return 'not_kept' if (effective or {}).get('output_format') == 'jpeg' else 'kept'


class JobStore:
    def __init__(self, jobs_dir, log, progress_interval=2.0):
        self.dir = Path(jobs_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.log = log
        self.progress_interval = progress_interval
        self._lock = threading.RLock()
        self._jobs = {}
        self._requests = {}
        self._dirty_since = {}
        self.load_problems = []
        self.save_problem = None          
        self.parallelism = 1              
        self.run_fn = None                
        self.recovered_done = []          

    
    def load_all(self):
        with self._lock:
            for p in sorted(self.dir.glob('j*.json')):
                if not JOB_ID_RE.match(p.stem):
                    continue
                try:
                    job = read_json(p)
                    if job.get('id') != p.stem or not isinstance(job.get('items'), list):
                        raise ValueError('not a job record')
                except (OSError, ValueError) as e:
                    bad = p.with_name(p.name + f'.unreadable-{time.strftime("%Y%m%d-%H%M%S")}')
                    try:
                        p.rename(bad)
                    except OSError as e2:
                        self.log.error('job_quarantine_failed', f'Unreadable job record {p} could not be moved aside: {e2}')
                    msg = f'A job record could not be read and was set aside ({bad.name}).'
                    self.load_problems.append(msg)
                    self.log.error('job_load_failed', msg, data={'path': str(p), 'error': str(e)})
                    continue
                self._jobs[job['id']] = job
                if job.get('client_request_id'):
                    self._requests[job['client_request_id']] = (job['id'], job.get('body_hash'))
            for p in self.dir.glob('*.tmp'):   
                self.log.warn('stale_tmp_removed', f'Removed leftover temporary file {p.name}')
                p.unlink()
        self.log.info('jobs_loaded', f'{len(self._jobs)} job records loaded', data={'jobs': len(self._jobs)})
        return len(self._jobs)

    def _save(self, job, force=True):
        jid = job['id']
        now = time.monotonic()
        if not force:
            first = self._dirty_since.setdefault(jid, now)
            if now - first < self.progress_interval:
                return
        job['updated'] = now_iso()
        try:
            atomic_write_json(self.dir / f'{jid}.json', job)
        except OSError as e:
            msg = f'The app could not save its job list ({e.strerror or e}). Free some space on drive C: or restart the app.'
            if self.save_problem != msg:
                self.log.error('job_save_failed', msg, job=jid, data={'path': str(self.dir / f'{jid}.json'), 'error': str(e)})
            self.save_problem = msg
            raise
        self._dirty_since.pop(jid, None)
        if self.save_problem is not None:
            self.log.info('job_save_recovered', 'Job records can be saved again', job=jid)
            self.save_problem = None

    def flush(self):
        with self._lock:
            for jid in list(self._dirty_since):
                self._save(self._jobs[jid], force=True)

    
    def find_request(self, request_id, body_hash):
        """Existing job for this request id, None if new; raises Conflict when the id was used with another body."""
        with self._lock:
            hit = self._requests.get(request_id)
            if hit is None:
                return None
            jid, h = hit
            if h != body_hash:
                raise Conflict(jid)
            return self.get(jid)

    def create(self, job):
        """Store a new job (record built by the runner). Idempotent on client_request_id + body hash."""
        with self._lock:
            existing = self.find_request(job['client_request_id'], job['body_hash'])
            if existing is not None:
                return existing, False
            job['state'] = derive_job_state(job['items'])
            self._save(job)                     
            self._jobs[job['id']] = job
            self._requests[job['client_request_id']] = (job['id'], job['body_hash'])
            n = len(job['items'])
            self.log.info('job_created', f'Started {n} image' + ('s' if n != 1 else ''), job=job['id'],
                          data={'items': [it['id'] for it in job['items']], 'output_dir': job['output_dir'],
                                'effective': job['effective']})
            return self.get(job['id']), True

    def get(self, jid, ranks=None):
        with self._lock:
            job = self._jobs.get(jid)
            if job is None:
                raise NotFound(jid)
            out = copy.deepcopy(job)
            if ranks is None:
                ranks = {k: i + 1 for i, k in enumerate(self._queue_order_locked())}
        out['effective'].setdefault('mode', 'standard')     
        for it in out['items']:          
            own = it.get('effective')
            it['effective'] = own or out['effective']
            it['effective'].setdefault('mode', 'standard')
            if it.get('ran_with'):
                it['ran_with'].setdefault('mode', 'standard')
            it['run'] = run_view(it, it['effective'], self.run_fn, out, waiting=len(ranks))
            it.setdefault('settings', None)
            it.setdefault('ran_with', None)
            it.setdefault('ran_with_request', None)
            it.setdefault('at', None)
            it.setdefault('gpu', None)
            it.setdefault('cards', [it['gpu']] if it.get('gpu') is not None else [])
            
            it['settings_changed'] = bool(it['ran_with']) and not same_record(it['ran_with'], it['effective'])
            it['transparency'] = transparency(it, it['effective'])
            it['queue_rank'] = ranks.get((jid, it['id']))
            it.pop('kept_passes', None)    
        out['summary'] = summarise(out, self.parallelism)
        return out

    def exists(self, jid):
        with self._lock:
            return jid in self._jobs

    def list(self, limit=50):
        with self._lock:
            ids = sorted(self._jobs, key=lambda j: (self._jobs[j]['created'], j), reverse=True)[:limit]
            ranks = {k: i + 1 for i, k in enumerate(self._queue_order_locked())}
        return [self.get(j, ranks) for j in ids]

    def item(self, jid, iid):
        with self._lock:
            job = self._jobs.get(jid)
            if job is None:
                raise NotFound(jid)
            for it in job['items']:
                if it['id'] == iid:
                    return copy.deepcopy(it)
        raise NotFound(f'{jid}/{iid}')

    def _item_ref(self, jid, iid):
        job = self._jobs.get(jid)
        if job is None:
            raise NotFound(jid)
        for it in job['items']:
            if it['id'] == iid:
                return job, it
        raise NotFound(f'{jid}/{iid}')

    
    def update_item(self, jid, iid, state=None, event=None, msg=None, level='info', log_stage=None, data=None, if_state=None,
                    **fields):
        """Apply a state change and/or field updates to one item, persist and log. Returns a copy of the item.
        `stage` is an item field like any other; the log line's stage is log_stage, else the item's new `stage` field.
        if_state: apply only while the item is in one of these states (returns None, unchanged, otherwise).
        Copy-on-write: if the save fails the exception propagates and nothing changes in memory."""
        with self._lock:
            job, it = self._item_ref(jid, iid)
            old = it['state']
            if if_state is not None and old not in if_state:
                return None
            new_it = copy.deepcopy(it)
            if state is not None and state != old:   
                check_transition(old, state)
                new_it['state'] = state
                new_it.setdefault('history', []).append({'ts': now_iso(), 'state': state})
            new_it.update(fields)
            items = [new_it if x is it else x for x in job['items']]
            new_job_state = derive_job_state(items)
            job_changed = new_job_state != job['state']
            new_job = dict(job, items=items, state=new_job_state)
            only_progress = state is None and set(fields) <= PROGRESS_FIELDS and not job_changed
            self._save(new_job, force=not only_progress)
            self._jobs[jid] = new_job
            if job_changed:
                self.log.info('job_state', f'Job is now {new_job_state}', job=jid, data={'state': new_job_state})
            if event:
                self.log.log(level, event, msg or event, job=jid, item=iid,
                             stage=log_stage if log_stage is not None else fields.get('stage'),
                             data=dict(data or {}, **({'state': state} if state else {})))
            return copy.deepcopy(new_it)

    def set_job_fields(self, jid, **fields):
        with self._lock:
            job = self._jobs.get(jid)
            if job is None:
                raise NotFound(jid)
            new_job = dict(job, **fields)
            self._save(new_job)
            self._jobs[jid] = new_job

    def items_where(self, pred):
        """[(job id, item copy)] of every item for which pred(job, item) is true (jobs in creation order)."""
        with self._lock:
            out = []
            for jid in sorted(self._jobs, key=lambda j: (self._jobs[j]['created'], j)):
                job = self._jobs[jid]
                out += [(jid, copy.deepcopy(it)) for it in job['items'] if pred(job, it)]
            return out

    def job_ids(self):
        with self._lock:
            return set(self._jobs)

    def _queue_order_locked(self):
        """Every queued item in dispatch order: images queued again at the head (newest first), then FIFO across jobs
        (creation order), items in order."""
        front, rest = [], []
        for jid in sorted(self._jobs, key=lambda j: (self._jobs[j]['created'], j)):
            job = self._jobs[jid]
            if job['state'] in TERMINAL:
                continue
            for it in job['items']:
                if it['state'] == 'queued':
                    (front if it.get('queue_front') else rest).append((it.get('queue_front') or 0, jid, it['id']))
        front.sort(key=lambda x: -x[0])
        return [(j, i) for _, j, i in front + rest]

    def queue_order(self):
        with self._lock:
            return self._queue_order_locked()

    def next_queued(self, exclude=()):
        """The next image to start (queue_order), skipping `exclude`."""
        with self._lock:
            for key in self._queue_order_locked():
                if key not in exclude:
                    return key
        return None

    def active_items(self):
        with self._lock:
            return [(j['id'], it['id']) for j in self._jobs.values() for it in j['items'] if it['state'] in ACTIVE]

    def output_paths(self):
        """Every output file and folder this service has written (for POST /api/open)."""
        files, folders = set(), set()
        with self._lock:
            for j in self._jobs.values():
                folders.add(str(Path(j['output_dir']).resolve()).lower())
                for it in j['items']:
                    for k in ('output', 'sidecar'):
                        if it.get(k):
                            files.add(str(Path(it[k]).resolve()).lower())
                            folders.add(str(Path(it[k]).resolve().parent).lower())
        return files, folders

    def latest_result(self, media_id):
        """(job, item) of the most recently finished result of an input image, or None (no deep copies)."""
        best = None
        with self._lock:
            for j in self._jobs.values():
                for it in j['items']:
                    if it.get('media_id') == media_id and it['state'] == 'done':
                        fin = (it.get('timings') or {}).get('finished', '')
                        if best is None or fin > best[0]:
                            best = (fin, j['id'], it['id'])
        return best[1:] if best else None

    
    def recover(self, stage_file_exists, published_check=None):
        """Restart recovery (see module docstring). stage_file_exists(jid, iid, k) -> bool (False also for an unreadable
        file); published_check(job, item) -> (output, sidecar) when the item's output was already published, else None.
        Returns the number of items changed; `recovered_done` lists the (job, item) completed from a published output."""
        changed, recovered_done = 0, []
        with self._lock:
            todo = [(jid, it['id']) for jid in sorted(self._jobs) for it in self._jobs[jid]['items']
                    if it['state'] in ACTIVE or it['state'] == 'interrupted']
            for jid, iid in todo:
                _, it = self._item_ref(jid, iid)
                was = it['state']
                if was != 'interrupted':
                    self.update_item(jid, iid, state='interrupted', event='item_interrupted', level='warn',
                                     msg=f'The app stopped while working on {it["name"]}', data={'was': was})
                job, it = self._item_ref(jid, iid)
                pub = published_check(job, it) if published_check else None
                n = len(it['plan']['stages'])
                if pub:
                    self.update_item(jid, iid, state='done', output=pub[0], sidecar=pub[1], progress=1.0, eta_s=0,
                                     stage=n - 1, stages=n, stages_done=n, stage_index=n, publishing=None,
                                     message='Done', event='item_recovered_done',
                                     msg='The result had already been saved before the restart; nothing was made again',
                                     data={'output': pub[0], 'sidecar': pub[1]})
                    recovered_done.append((jid, iid))
                    changed += 1
                    continue
                if it.get('cancel_requested'):
                    self.update_item(jid, iid, state='cancelled', message='Cancelled', eta_s=None, event='item_cancelled',
                                     msg='Cancelled (the cancel was asked for before the app stopped)', data={'was': was})
                    changed += 1
                    continue
                if it.get('stop_requested'):
                    self.update_item(jid, iid, state='stopped', message='Stopped', eta_s=None, gpu=None, cards=[],
                                     event='item_stopped', msg=f'Stopped {it["name"]} (the stop was asked for before the app '
                                                               'stopped)', data={'was': was})
                    changed += 1
                    continue
                k = next((i for i in range(n) if not stage_file_exists(jid, iid, i)), n)
                text = f'Resuming at pass {k + 1} of {n} after a restart' if k < n else 'Saving the result after a restart'
                self.update_item(jid, iid, state='queued', stage_index=k, stage=min(k, n - 1), stages=n, stages_done=k,
                                 stage_progress=0.0, eta_s=None, message=text, event='item_requeued', msg=text,
                                 data={'stage_index': k, 'stages': n, 'was': was})
                changed += 1
        self.recovered_done = recovered_done
        return changed
