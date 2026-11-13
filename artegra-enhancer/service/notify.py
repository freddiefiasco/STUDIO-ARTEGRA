"""Notify implementation."""


import json
import os
import re
import shutil
import threading
import time
from pathlib import Path

from service.util import now_iso

APP_ID = 'StudioArtegra.ArtegraEnhancerPilot'
POWERSHELL_APP_ID = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\\WindowsPowerShell\\v1.0\\powershell.exe'
TITLE = 'Artegra Enhancer'
NO_WINDOW = 0x08000000
PS = r'''
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$null = [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]
$null = [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime]
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$toast = $xml.CreateElement('toast')
$launch = [Environment]::GetEnvironmentVariable('CU_TOAST_LAUNCH')
if ($launch) { $toast.SetAttribute('activationType', 'protocol'); $toast.SetAttribute('launch', $launch) }
$null = $xml.AppendChild($toast)
$visual = $xml.CreateElement('visual')
$null = $toast.AppendChild($visual)
$binding = $xml.CreateElement('binding')
$binding.SetAttribute('template', 'ToastGeneric')
$null = $visual.AppendChild($binding)
foreach ($name in @('CU_TOAST_TITLE', 'CU_TOAST_BODY')) {
    $t = $xml.CreateElement('text')
    $null = $t.AppendChild($xml.CreateTextNode([Environment]::GetEnvironmentVariable($name)))
    $null = $binding.AppendChild($t)
}
$toastObj = New-Object Windows.UI.Notifications.ToastNotification $xml
$notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier([Environment]::GetEnvironmentVariable('CU_TOAST_APPID'))
if ([Environment]::GetEnvironmentVariable('CU_TOAST_CHECK') -eq '1') { 'ready'; exit 0 }
$notifier.Show($toastObj)
'shown'
'''


def app_id():
    """The registered Artegra Enhancer id when the installer registered it, else Windows PowerShell's (read only)."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Classes\AppUserModelId' + '\\' + APP_ID):
            return APP_ID
    except OSError:
        return POWERSHELL_APP_ID
    except ImportError:
        return POWERSHELL_APP_ID


PROTOCOL = 'artegra-enhancer-pilot'
LAUNCH = PROTOCOL + ':creative-upscaler'


LAUNCH_SCRIPT_RE = re.compile(r'"([^"]+\.vbs)"', re.I)       


def _protocol_command():
    """The command the artegra-enhancer-pilot: address runs (HKCU Software\\Classes\\artegra-enhancer-pilot\\shell\\open\\command), or
    None (read only)."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Software\\Classes\\' + PROTOCOL + '\\shell\\open\\command') as k:
            return winreg.QueryValueEx(k, '')[0]
    except (OSError, ImportError):
        return None


def launch_target_ok(command):
    """True when the registered command names a launcher script (.vbs) that exists."""
    m = LAUNCH_SCRIPT_RE.search(str(command or ''))
    return bool(m) and Path(m.group(1)).is_file()


def launch_uri():
    """'artegra-enhancer-pilot:creative-upscaler' when the installer registered that protocol and the launcher script it runs is
    there (clicking the toast then opens the Creative Upscaler tab), else '' (a click only dismisses it). 12 Nov (QA
    INSTALL-5): only the key was checked, so a key left after the launcher was removed made a click on a toast open wscript's
    own "can not find script file" box."""
    return LAUNCH if launch_target_ok(_protocol_command()) else ''


def powershell():
    root = os.environ.get('SystemRoot', '')
    p = Path(root) / 'System32' / 'WindowsPowerShell' / 'v1.0' / 'powershell.exe'
    return str(p) if p.is_file() else shutil.which('powershell.exe')


def _run(title, body, check, timeout=30, log_dir=None, script=None):
    """Run the toast script (`script`: tests only) in Windows PowerShell inside its own kill-on-close Windows Job
    (service/windows_job.py run_contained, as nvidia-smi), hidden, closed after `timeout` s. Its output goes to a file in
    `log_dir`, removed afterwards. 12 Nov (QA LIFECYCLE-6): it ran through a plain subprocess.run, so a service ended during a
    toast or the start-up check left powershell.exe running (AGENTS invariant 5). Returns (ok, detail)."""
    exe = powershell()
    if os.name != 'nt' or not exe:
        return False, 'powershell_missing'
    from service.windows_job import ProcessContainmentError, run_contained
    env = dict(os.environ, CU_TOAST_TITLE=title, CU_TOAST_BODY=body, CU_TOAST_APPID=app_id(), CU_TOAST_CHECK='1' if check else '0',
               CU_TOAST_LAUNCH=launch_uri())
    import base64
    enc = base64.b64encode((script or PS).encode('utf-16-le')).decode('ascii')
    d = Path(log_dir) if log_dir else Path(os.environ.get('TEMP') or '.') / 'cu-notify'
    log_path = d / f'toast-{os.getpid()}-{threading.get_ident()}-{time.monotonic_ns()}.txt'
    try:
        d.mkdir(parents=True, exist_ok=True)
        code, text = run_contained([os.path.abspath(exe), '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                                    '-WindowStyle', 'Hidden', '-EncodedCommand', enc], timeout=timeout, log_path=log_path,
                                   env=env)
    except (OSError, ProcessContainmentError) as e:
        return False, f'{type(e).__name__}: {e}'
    leftover = _remove_quietly(log_path)
    if code is None:
        return False, f'timed out after {timeout} s; the helper was stopped' + leftover
    
    
    out = [ln.strip() for ln in (text or '').splitlines()]
    ok = code == 0 and ('ready' if check else 'shown') in out
    return bool(ok), None if ok else (text or '')[-500:] + leftover


def _remove_quietly(path):
    """Remove a helper's output file; '' when gone, else a note for the detail (the next run uses a new name)."""
    try:
        if Path(path).exists():
            Path(path).unlink()
        return ''
    except OSError as e:
        return f' (its output file {Path(path).name} could not be removed: {e})'


def duration_text(seconds):
    m = max(1, int(round(seconds / 60.0)))
    if m < 60:
        return f'{m} min'
    h, m = divmod(m, 60)
    return f'{h} h {m} min' if m else f'{h} h'


def batch_end_text(done, failed, seconds):
    if done:
        text = f'{done} image{"s" if done != 1 else ""} upscaled in {duration_text(seconds)}'
        return text + (f'. {failed} failed.' if failed else '')
    return f'{failed} image{"s" if failed != 1 else ""} failed.'


FAILED_TEXT = '1 image failed. The rest carried on.'


class Notifier:
    """Raises the toasts above. dry_run: record only (tests, the fake engine). The availability check runs once, on a thread."""

    def __init__(self, log, state_dir, dry_run=None):
        self.log = log
        self.record = Path(state_dir) / 'notifications.jsonl'
        self.scratch = Path(state_dir) / 'notify'        
        if dry_run is None:
            dry_run = os.environ.get('CU_NOTIFY_DRYRUN') == '1'
        self.dry_run = bool(dry_run)
        self._avail = (None, None)            
        self._lock = threading.Lock()
        self.sent = []

    def check(self):
        """Look once whether Windows can show a notification (no toast is shown). Never raises."""
        if self.dry_run:
            self._avail = (True, None)
            return self._avail
        try:
            ok, why = _run(TITLE, 'check', check=True, log_dir=self.scratch)
        except Exception as e:   
            ok, why = False, f'{type(e).__name__}: {e}'
        self._avail = (ok, None if ok else 'unavailable')
        self.log.log('info' if ok else 'warn', 'notify_check', 'Windows can show notifications from the engine' if ok else
                     'Windows cannot show notifications from the engine', data={'app_id': app_id(), 'detail': why})
        return self._avail

    def info(self):
        ok, why = self._avail
        return {'available': bool(ok) if ok is not None else None, 'reason': why if ok is not None else 'checking',
                'app_id_registered': app_id() == APP_ID, 'opens_tab': bool(launch_uri()), 'dry_run': self.dry_run}

    def available(self):
        return self._avail[0] is True

    def send(self, body, kind):
        """Show (or record) one toast; returns True when it was shown or recorded. Never raises."""
        row = {'ts': now_iso(), 'title': TITLE, 'body': body, 'kind': kind, 'dry_run': self.dry_run}
        ok, why = True, None
        if not self.dry_run:
            try:
                ok, why = _run(TITLE, body, check=False, log_dir=self.scratch)
            except Exception as e:
                ok, why = False, f'{type(e).__name__}: {e}'
        row['shown'] = ok and not self.dry_run
        with self._lock:
            self.sent.append(row)
            try:
                with self.record.open('a', encoding='utf8') as f:
                    f.write(json.dumps(row) + '\n')
            except OSError as e:
                self.log.warn('notify_record_failed', f'The notification record could not be written: {e}')
        self.log.log('info' if ok else 'warn', 'notify_sent' if ok else 'notify_failed',
                     f'Windows notification: {body}' if ok else 'The Windows notification could not be shown',
                     data={'kind': kind, 'dry_run': self.dry_run, 'detail': why})
        return ok


class BatchWatch:
    """Counts one batch (from the first image that starts after the engine was idle to the moment nothing is left) and decides
    which notification is due. The runner calls started(), finished(state) and idle(); `background()` says whether the window
    is gone with this batch still running (service/lifecycle.py)."""

    def __init__(self, notifier, enabled, background, clock=time.time):
        self.notifier, self.enabled, self.background, self.clock = notifier, enabled, background, clock
        self.started_at = None
        self.done = 0
        self.failed = 0
        self.lock = threading.Lock()

    def started(self):
        with self.lock:
            if self.started_at is None:
                self.started_at = self.clock()
                self.done = self.failed = 0

    def finished(self, state, others_left):
        """An image ended (done / failed). others_left: images still queued or running."""
        with self.lock:
            if self.started_at is None:
                return
            if state == 'done':
                self.done += 1
            elif state == 'failed':
                self.failed += 1
                due = others_left and self.enabled() and self.background()
            else:
                return
        if state == 'failed' and due:
            self.notifier.send(FAILED_TEXT, 'image_failed')

    def idle(self):
        """Nothing left to do: the batch ended. Sends the end notification when it is due."""
        with self.lock:
            if self.started_at is None:
                return None
            done, failed, secs = self.done, self.failed, self.clock() - self.started_at
            self.started_at = None
            self.done = self.failed = 0
        if (done or failed) and self.enabled() and self.background():
            text = batch_end_text(done, failed, secs)
            self.notifier.send(text, 'batch_end')
            return text
        return None
