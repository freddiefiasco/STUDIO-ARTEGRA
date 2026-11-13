"""Logs implementation."""


import datetime
import json
import os
import re
import secrets
import sys
import threading
import traceback
from pathlib import Path

LEVELS = {'debug': 10, 'info': 20, 'warn': 30, 'error': 40}
_APP_RE = re.compile(r'^app-(\d{8})\.jsonl$')
_ID_RE = re.compile(r'^[A-Za-z0-9_-]{1,64}$')


def new_ref():
    return secrets.token_hex(4)


class Logger:
    def __init__(self, logs_dir, jobs_dir, retention_days=14, echo=True):
        self.logs_dir = Path(logs_dir)
        self.jobs_dir = Path(jobs_dir)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.retention_days = retention_days
        self.echo = echo
        self._lock = threading.Lock()
        self._day = None
        self.write_failures = 0

    
    def log(self, level, event, msg, job=None, item=None, stage=None, data=None, ref=None):
        """Write one line; returns the log_ref (given or None)."""
        now = datetime.datetime.now().astimezone()
        rec = {'ts': now.isoformat(timespec='milliseconds'), 'level': level, 'event': event, 'job': job, 'item': item,
               'stage': stage, 'msg': msg, 'data': data}
        if ref:
            rec['log_ref'] = ref
        line = json.dumps(rec, ensure_ascii=False, default=str) + '\n'
        day = now.strftime('%Y%m%d')
        with self._lock:
            if day != self._day:
                self._day = day
                self._rotate_locked(now.date())
            self._append(self.logs_dir / f'app-{day}.jsonl', line)
            if job and _ID_RE.match(str(job)):
                self._append(self.jobs_dir / f'{job}.jsonl', line)
        if self.echo:
            self._echo(rec)
        return ref

    def debug(self, event, msg, **kw):
        return self.log('debug', event, msg, **kw)

    def info(self, event, msg, **kw):
        return self.log('info', event, msg, **kw)

    def warn(self, event, msg, **kw):
        return self.log('warn', event, msg, **kw)

    def error(self, event, msg, ref=None, **kw):
        return self.log('error', event, msg, ref=ref or new_ref(), **kw)

    def exception(self, event, msg, exc, ref=None, **kw):
        """Log an exception with its traceback; returns the log_ref to show the user."""
        data = dict(kw.pop('data', None) or {})
        data['exception'] = f'{type(exc).__name__}: {exc}'
        data['traceback'] = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))[-6000:]
        return self.log('error', event, msg, ref=ref or new_ref(), data=data, **kw)

    def _append(self, path, line):
        try:
            with open(path, 'a', encoding='utf8') as f:
                f.write(line)
        except OSError as e:
            
            self.write_failures += 1
            self._stderr(f'LOG WRITE FAILED ({path}): {e}; line: {line.strip()[:500]}')

    def _echo(self, rec):
        extra = f" [{rec['log_ref']}]" if rec.get('log_ref') else ''
        ids = ' '.join(f'{k}={rec[k]}' for k in ('job', 'item', 'stage') if rec.get(k) is not None)
        self._stderr(f"{rec['ts'][11:23]} {rec['level'].upper():5} {rec['event']} {ids} {rec['msg']}{extra}".replace('  ', ' '))

    def _stderr(self, text):
        stream = sys.stderr
        if stream is None:   
            return
        try:
            stream.write(text + '\n')
            stream.flush()
        except (OSError, ValueError, UnicodeEncodeError):
            self.echo = False

    
    def rotate(self):
        with self._lock:
            self._rotate_locked(datetime.date.today())

    def _rotate_locked(self, today):
        cutoff = today - datetime.timedelta(days=self.retention_days)
        for p in self.logs_dir.glob('app-*.jsonl'):
            m = _APP_RE.match(p.name)
            if not m:
                continue
            try:
                d = datetime.datetime.strptime(m.group(1), '%Y%m%d').date()
            except ValueError:
                continue
            if d < cutoff:
                try:
                    p.unlink()
                except OSError as e:
                    self._stderr(f'Old log {p} could not be removed: {e}')

    
    def recent(self, job=None, limit=200, min_level='debug', pred=None):
        """Most recent lines (oldest first) from the job log, or from the app logs of today and yesterday. `pred(record)`
        keeps only matching lines (the activity drawer's user-facing events); `limit` counts kept lines."""
        limit = max(1, min(int(limit), 2000))
        if job is not None:
            if not _ID_RE.match(str(job)):
                return []
            files = [self.jobs_dir / f'{job}.jsonl']
        else:
            files = sorted(self.logs_dir.glob('app-*.jsonl'))[-2:]
        floor = LEVELS.get(min_level, 10)
        out = []
        for p in reversed(files):
            for line in reversed(_tail_lines(p, limit * 4 if floor > 10 or pred is not None else limit)):
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(rec, dict) or 'event' not in rec:
                    continue
                if LEVELS.get(rec.get('level'), 20) >= floor and (pred is None or pred(rec)):
                    out.append(rec)
                if len(out) >= limit:
                    break
            if len(out) >= limit:
                break
        return list(reversed(out))


def _tail_lines(path, n):
    """Last n lines of a text file without reading all of it."""
    try:
        size = os.path.getsize(path)
    except OSError:
        return []
    block = 65536
    data = b''
    with open(path, 'rb') as f:
        pos = size
        while pos > 0 and data.count(b'\n') <= n:
            step = min(block, pos)
            pos -= step
            f.seek(pos)
            data = f.read(step) + data
    lines = data.decode('utf8', errors='replace').splitlines()
    if pos > 0 and lines:
        lines = lines[1:]   
    return [l for l in lines[-n:] if l.strip()]
