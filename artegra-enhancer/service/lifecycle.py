"""Lifecycle implementation."""
import ctypes
import os
import threading
import time
from ctypes import wintypes as W
from service.settings import env_float

CHOICES = ('stop', 'finish')


class HostWatch:
    """Hold a process handle so PID reuse cannot keep an abandoned engine alive."""
    names = ()
    gone_s = 0.0

    def __init__(self, log, pid, probe=None):
        self.log = log
        self.pid = int(pid)
        self.pids = {self.pid}
        self._gone = False
        self._probe = probe
        self._handle = None
        self._api = None
        if probe is None and os.name == 'nt':
            api = ctypes.WinDLL('kernel32', use_last_error=True)
            api.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
            api.OpenProcess.restype = W.HANDLE
            api.WaitForSingleObject.argtypes = [W.HANDLE, W.DWORD]
            api.WaitForSingleObject.restype = W.DWORD
            api.CloseHandle.argtypes = [W.HANDLE]
            self._handle = api.OpenProcess(0x100000, False, self.pid)
            if not self._handle:
                raise OSError('The owning host process could not be opened.')
            self._api = api
        self.poll()
        if self._gone:
            self.close()
            raise OSError('The owning host process has already exited.')

    def poll(self):
        if self._gone:
            return
        if self._probe is not None:
            alive = bool(self._probe(self.pid))
        elif self._api is not None:
            status = self._api.WaitForSingleObject(self._handle, 0)
            if status == 0xFFFFFFFF:
                raise OSError('The owning host process could not be checked.')
            alive = status == 258
        else:
            try:
                os.kill(self.pid, 0)
                alive = True
            except ProcessLookupError:
                alive = False
        if not alive:
            self._gone = True
            self.pids.clear()

    def gone(self):
        return self._gone

    def info(self):
        return {'host_pid': self.pid, 'open': int(not self._gone), 'seen': True}

    def close(self):
        if self._handle is not None:
            self._api.CloseHandle(self._handle)
            self._handle = None


class Lifecycle:
    """The policy above. The runner asks release_reason() on its scheduler thread (so a release happens the moment the last
    image frees its card) and reports released(); this object's own thread polls the app and decides when the service exits."""

    def __init__(self, runner, log, watch=None, on_exit=None, exit_when_closed=True, poll_s=None):
        self.runner = runner
        self.log = log
        self.watch = watch
        self.on_exit = on_exit
        self.exit_when_closed = bool(exit_when_closed)
        self.poll_s = env_float('CU_APP_POLL_SECONDS', 1.0) if poll_s is None else float(poll_s)
        self.closing = False           
        self.finish_requested = False
        self.finish_at = None
        self._finish_pids = set()
        self.choice = None
        self._gone_logged = False
        self._released_for_gone = False
        self._exit_started = False
        self.background_since = None   
        self._stop = threading.Event()
        self._thread = None
        self._lock = threading.Lock()

    def start(self):
        if self.watch is None:
            return
        self.watch.poll()                
        self._thread = threading.Thread(target=self._loop, name='app-watch', daemon=True)
        self._thread.start()
        self.log.info('app_watch_started', 'Watching Artegra Enhancer: the engine frees the graphics cards when it closes',
                      data={'images': list(self.watch.names), 'gone_s': self.watch.gone_s, 'poll_s': self.poll_s,
                            'exit_when_closed': self.exit_when_closed, 'app': self.watch.info()})

    def stop(self):
        self._stop.set()
        if self._thread is not None and threading.current_thread() is not self._thread:
            self._thread.join(timeout=max(2, self.poll_s + 1))
        if self.watch is not None:
            self.watch.close()

    def _loop(self):
        while not self._stop.wait(self.poll_s):
            try:
                self.watch.poll()
                self.tick()
            except Exception as e:   
                self.log.exception('app_watch_error', 'The app watch hit an error and carries on', e)

    def tick(self):
        """One step of the policy (the thread calls it after every poll; tests call it directly)."""
        gone = self.watch is not None and self.watch.gone()
        
        if gone and not self._exit_started:
            self._exit_started = True
            self.closing = True
            self.log.info('host_exited', 'The owning window has closed; stopping its engine.')
            if self.on_exit is not None:
                threading.Thread(target=self.on_exit, name='host-exit', daemon=False).start()
            return
        with self._lock:
            if self.finish_requested and self.watch is not None and self.watch.pids - self._finish_pids:
                self.finish_requested = False
                self.background_since = None
                self.log.info('app_reopened', 'Artegra Enhancer was opened again, so the engine stays warm',
                              data={'pids': sorted(self.watch.pids)})
            if (self.background_since is not None and not self.finish_requested and self.watch is not None
                    and self.watch.pids - self._finish_pids and not gone):
                self.background_since = None       
            if gone and not self._gone_logged:
                self._gone_logged = True
                w = self.runner.work_summary()
                if self.background_since is None and (w.get('images_running') or w.get('images_saving')
                                                      or w.get('images_waiting')):
                    self.background_since = time.monotonic()
                self.log.info('app_closed', 'Artegra Enhancer has closed', data=dict(self.runner.work_summary(),
                                                                                      app=self.watch.info()))
                self.runner.wake()
            elif not gone and self._gone_logged:
                self._gone_logged = False
                self._released_for_gone = False
                self.background_since = None
            
            candidate = (gone and self.exit_when_closed and not self._exit_started and not self.closing
                         and self._released_for_gone)
        want_exit = False
        if candidate and self.runner.quiet():           
            with self._lock:
                if not self._exit_started and not self.closing:
                    self._exit_started = want_exit = True
        if want_exit:
            self.log.info('service_exit_app_closed', 'Artegra Enhancer has closed and nothing is left to do, so the engine '
                          'closes too; the tab starts it again when it is next opened', data=self.watch.info())
            if self.on_exit is not None:
                threading.Thread(target=self.on_exit, name='app-closed-exit', daemon=False).start()

    def release_reason(self):
        """'finish' (the person chose Finish in the background), 'app_closed' (no app left), or None (keep warm)."""
        with self._lock:
            if self.finish_requested:
                return 'finish'
        if self.watch is not None and self.watch.gone() and not self._released_for_gone:
            return 'app_closed'
        return None

    def released(self, reason, stopped):
        """The runner stopped every worker for `reason` (nothing needed a graphics card any more)."""
        with self._lock:
            if reason == 'finish':
                self.finish_requested = False
            if reason == 'app_closed' or (self.watch is not None and self.watch.gone()):
                self._released_for_gone = True
        why = 'the batch finished in the background' if reason == 'finish' else 'Artegra Enhancer has closed'
        
        self.log.info('workers_released', ('The graphics cards were freed: ' if stopped else 'No engine was running: ') + why,
                      data={'reason': reason, 'workers': stopped, 'app': self.watch.info() if self.watch else None,
                            'since_choice_s': None if self.finish_at is None else round(time.monotonic() - self.finish_at, 1)})

    def close_request(self, choice):
        """POST /api/lifecycle/close. Returns the reply; 'stop' is carried out by the caller (App.stop) after replying."""
        if choice not in CHOICES:
            raise ValueError(choice)
        summary = self.runner.work_summary()
        with self._lock:
            self.choice = choice
            if choice == 'finish':
                self.finish_requested = True
                self.finish_at = time.monotonic()
                self._finish_pids = set(self.watch.pids) if self.watch is not None else set()


                others_open = len(self._finish_pids) > 1
                if (not others_open and (summary.get('images_running') or summary.get('images_saving')
                                         or summary.get('images_waiting'))):
                    self.background_since = self.finish_at
        if choice == 'finish':
            self.log.info('app_close_finish', 'Artegra Enhancer is closing: the images still upscaling finish in the '
                          'background, then the graphics cards are freed', data=summary)
            self.runner.wake()
        else:
            self.log.info('app_close_stop', 'Artegra Enhancer is closing: the images still upscaling stop now and continue '
                          'the next time the app is opened', data=summary)
        return {'choice': choice, 'stopping': choice == 'stop', 'finish_in_background': choice == 'finish', **summary}

    def in_background(self):
        """True while the window is gone (Finish in the background, or the app closed) and this batch still runs."""
        with self._lock:
            return self.background_since is not None

    def batch_ended(self):
        """The runner: the batch that ran in the background has ended (its notification, if due, is already sent). The next
        batch is in the background only if the window goes again (12 Nov, QA LIFECYCLE-3: the flag stayed set when a window
        was kept, so every later batch raised a notification while that window was open)."""
        with self._lock:
            if self.background_since is not None:
                self.background_since = None
                self.log.info('background_ended', 'The batch that ran in the background has ended',
                              data={'finish_in_background': self.finish_requested})

    def info(self):
        with self._lock:
            out = {'watching': self.watch is not None, 'closing': self.closing, 'finish_in_background': self.finish_requested,
                   'in_background': self.background_since is not None,
                   'when_app_closes': 'exit' if self.exit_when_closed else 'stay', 'choice': self.choice}
        out['app'] = self.watch.info() if self.watch is not None else None
        out['app_closed'] = bool(self.watch is not None and self.watch.gone())
        return out
