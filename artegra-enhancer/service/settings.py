"""Settings implementation."""


import ctypes
import math
import os
import secrets
import threading
from pathlib import Path

from service.util import atomic_write_json, read_json

BASE_KEYS = ('output_dir', 'gpus', 'idle_minutes')
EXTRA_KEYS = ('detailed_preview', 'notify', 'hold_sleep', 'match_earlier', 'split', 'faster')
EXTRA_DEFAULTS = {'detailed_preview': True, 'notify': True, 'hold_sleep': True, 'match_earlier': False, 'split': None,
                  'faster': False}
SPLIT_DEFAULT = 'default'         
EXTRA_NAME = 'settings-extra.json'
API_KEYS = BASE_KEYS + EXTRA_KEYS
FILE_KEYS = BASE_KEYS + ('ram_cap_gb',)
META_NAME = 'settings-meta.json'
META_SCHEMA = 'creative-upscaler-settings-meta-v1'
OLD_DEFAULT_GPUS = [0]            
OLD_DEFAULT_RAM_CAP_GB = 110      
RAM_GUARD_GB = 1.0                
ALL_GPUS = 'all'


class SettingsError(ValueError):
    pass


def machine_ram_gb():
    """Physical memory of this computer in GiB (Windows GlobalMemoryStatusEx), or None when it cannot be read."""
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
    return st.ullTotalPhys / (1 << 30)


def default_ram_cap_gb(total_gb=None):
    """The machine minus the 1 GiB guard, rounded down to 0.1 GiB (WS: 127.4 GiB -> 126.3). 110 when unknown."""
    total = machine_ram_gb() if total_gb is None else total_gb
    if not total or total - RAM_GUARD_GB < 8:
        return OLD_DEFAULT_RAM_CAP_GB
    return math.floor((total - RAM_GUARD_GB) * 10) / 10


def probe_writable(folder, create=True):
    """Make sure `folder` exists (creating only the last level, when its parent exists) and a file can be written and removed
    there. A mistyped folder path is refused instead of being created."""
    p = Path(folder)
    try:
        if not p.is_dir():
            if not create:
                raise SettingsError(f'The folder {p} does not exist.')
            if not p.parent.is_dir():
                raise SettingsError(f'The folder {p.parent} does not exist. Choose an existing folder.')
            p.mkdir(exist_ok=True)
        probe = p / f'.cu-write-test-{secrets.token_hex(4)}'
        with open(probe, 'wb') as f:
            f.write(b'ok')
        probe.unlink()
    except SettingsError:
        raise
    except OSError as e:
        raise SettingsError(f'The folder {p} cannot be written to ({e.strerror or e}). Choose another folder.')


def validate(values, available_gpus, check_output=True, allow_all=False):
    out = {}
    if 'output_dir' in values:
        v = values['output_dir']
        if not isinstance(v, str) or not v.strip():
            raise SettingsError('The output folder must be a folder path.')
        p = Path(v.strip())
        if not p.is_absolute():
            raise SettingsError('The output folder must be a full path, using the file or folder picker.')
        if check_output:
            probe_writable(p)
        out['output_dir'] = str(p)
    if 'gpus' in values:
        v = values['gpus']
        if allow_all and v == ALL_GPUS:
            out['gpus'] = ALL_GPUS
        else:
            if (not isinstance(v, list) or not v or any(isinstance(g, bool) or not isinstance(g, int) for g in v)
                    or len(set(v)) != len(v)):
                raise SettingsError('Graphics cards must be a list of card numbers, for example [0] or [0, 1], or "all".'
                                    if allow_all else
                                    'Graphics cards must be a list of card numbers, for example [0] or [0, 1].')
            unknown = [g for g in v if g not in available_gpus]
            if unknown:
                
                
                raise SettingsError(', '.join(f'GPU {g + 1}' for g in unknown)
                                    + (' was' if len(unknown) == 1 else ' were') + ' not found. Available: '
                                    + (', '.join(f'GPU {g + 1}' for g in available_gpus) or 'none') + '.')
            out['gpus'] = sorted(v)
    if 'idle_minutes' in values:
        v = values['idle_minutes']
        if isinstance(v, bool) or not isinstance(v, int) or not 1 <= v <= 1440:
            raise SettingsError('Idle time must be a whole number of minutes from 1 to 1440.')
        out['idle_minutes'] = v
    if 'ram_cap_gb' in values:
        v = values['ram_cap_gb']
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not 8 <= v <= 2048:
            raise SettingsError('ram_cap_gb must be a number of gigabytes from 8 to 2048.')
        out['ram_cap_gb'] = v
    for k in ('detailed_preview', 'notify', 'hold_sleep', 'match_earlier', 'faster'):
        if k in values:
            if not isinstance(values[k], bool):
                raise SettingsError(f'{k} must be true or false.')
            out[k] = values[k]
    if 'split' in values:
        v = values['split']
        if v is None or (allow_all and v == SPLIT_DEFAULT):
            if v is None and allow_all:
                raise SettingsError('split must be true, false or "default".')
            out['split'] = None
        elif isinstance(v, bool):
            out['split'] = v
        else:
            raise SettingsError('split must be true, false or "default".' if allow_all else 'split must be true, false or null.')
    return out


class Settings:
    def __init__(self, path, default_output_dir, log, total_ram_gb=None):
        self.path = Path(path)
        self.meta_path = self.path.with_name(META_NAME)
        self.extra_path = self.path.with_name(EXTRA_NAME)
        self.extra = dict(EXTRA_DEFAULTS)
        self.extra_kept = {}               
        self.split_default_fn = None       
        self.log = log
        self._lock = threading.Lock()
        self.gpus_fn = None                
        self.machine_ram_gb = machine_ram_gb() if total_ram_gb is None else total_ram_gb
        self.default_ram_cap = default_ram_cap_gb(self.machine_ram_gb)
        self.defaults = {'output_dir': str(default_output_dir), 'gpus': ALL_GPUS, 'idle_minutes': 10,
                         'ram_cap_gb': self.default_ram_cap}
        self.values = dict(self.defaults)     
        self.chosen = {'gpus': False, 'ram_cap_gb': False}
        self.origin = {'gpus': 'default', 'ram_cap_gb': 'default'}
        self.load_problem = None
        if self.path.exists():
            try:
                data = read_json(self.path)
                if not isinstance(data, dict):
                    raise SettingsError('settings.json must contain a JSON object')
                unknown = set(data) - set(FILE_KEYS)
                if unknown:
                    raise SettingsError('unknown keys ' + ', '.join(sorted(unknown)))
                
                gpus = data.pop('gpus', None)
                clean = validate(data, [], check_output=False)
                if gpus is not None:
                    clean.update(validate({'gpus': gpus}, gpus))
                self._apply_loaded(clean, self._read_meta())
            except (OSError, ValueError) as e:
                self.load_problem = ('The saved settings could not be read, so the defaults are in use. Choose your output '
                                     'folder again.')
                self.log.error('settings_load_failed', self.load_problem, data={'path': str(self.path), 'error': str(e),
                                                                                  'type': type(e).__name__})
        if self.extra_path.exists():
            try:
                data = read_json(self.extra_path)
                if not isinstance(data, dict):
                    raise SettingsError('settings-extra.json must contain a JSON object')
                self.extra_kept = {k: v for k, v in data.items() if k not in EXTRA_KEYS}
                if self.extra_kept:
                    self.log.info('settings_extra_unknown', 'Settings this version does not use were kept as they are',
                                  data={'keys': sorted(self.extra_kept)})
                self.extra.update(validate({k: v for k, v in data.items() if k in EXTRA_KEYS}, [], check_output=False))
            except (OSError, ValueError) as e:
                self.load_problem = self.load_problem or ('The saved settings could not be read, so the defaults are in use. '
                                                          'Check Settings again.')
                self.log.error('settings_load_failed', 'The v4 settings could not be read; their defaults are in use',
                               data={'path': str(self.extra_path), 'error': str(e)})
        self.log.info('settings_loaded', 'Settings loaded', data=dict(self.values, **self.extra, origin=dict(self.origin),
                                                                       machine_ram_gb=self._round(self.machine_ram_gb),
                                                                       default_ram_cap_gb=self.default_ram_cap))

    @staticmethod
    def _round(v):
        return None if v is None else round(v, 2)

    def _read_meta(self):
        """settings-meta.json, or None when it is missing or unreadable (the pre-v3 rule then applies; never an error)."""
        if not self.meta_path.exists():
            return None
        try:
            meta = read_json(self.meta_path)
            if not isinstance(meta, dict) or meta.get('schema') != META_SCHEMA:
                raise ValueError('not a settings meta record')
            return meta
        except (OSError, ValueError) as e:
            self.log.warn('settings_meta_unreadable', 'The record of which settings were chosen could not be read; saved '
                          'values that equal the old defaults are treated as defaults', data={'path': str(self.meta_path),
                                                                                               'error': str(e)})
            return None

    def _apply_loaded(self, clean, meta):
        for key, old_default in (('gpus', OLD_DEFAULT_GPUS), ('ram_cap_gb', OLD_DEFAULT_RAM_CAP_GB)):
            if key not in clean:
                continue
            saved = clean.pop(key)
            rec = (meta or {}).get(key)
            if isinstance(rec, dict) and rec.get('saved') == saved and isinstance(rec.get('chosen'), bool):
                chosen, origin = rec['chosen'], 'chosen' if rec['chosen'] else 'default'
            elif saved == old_default:
                chosen, origin = False, 'migrated'
                self.log.info('settings_migrated', f'The saved {key} {saved} was the old default; the new default is used',
                              data={'key': key, 'saved': saved, 'meta': rec, 'new_default': self.defaults[key]})
            else:
                chosen, origin = True, 'chosen'
            self.chosen[key], self.origin[key] = chosen, origin
            if chosen:
                self.values[key] = saved
        self.values.update(clean)

    
    def default_gpus(self):
        gpus = []
        if self.gpus_fn is not None:
            try:
                gpus = sorted(int(g) for g in (self.gpus_fn() or []))
            except (TypeError, ValueError) as e:
                self.log.warn('gpus_default_unreadable', f'The graphics card list could not be read: {e}')
                gpus = []
        return gpus or list(OLD_DEFAULT_GPUS)

    def get(self):
        with self._lock:
            values, chosen = dict(self.values), dict(self.chosen)
            extra = {k: (dict(v) if isinstance(v, dict) else v) for k, v in self.extra.items()}
        values['gpus'] = list(values['gpus']) if chosen['gpus'] else self.default_gpus()
        values['gpus_chosen'] = chosen['gpus']
        values.update(extra)
        values['split_chosen'] = extra['split'] is not None
        values['split'] = extra['split'] if extra['split'] is not None else self.split_default()
        return values

    def split_default(self):
        """The default of `split`: on once the two-card proof has passed (the runner says; False without a runner)."""
        try:
            return bool(self.split_default_fn()) if self.split_default_fn is not None else False
        except Exception as e:   
            self.log.warn('split_default_unreadable', f'The default for sharing an image between GPUs could not be read: {e}')
            return False

    def file_values(self):
        """What settings.json holds: the earlier versions' schema, with the GPU list in force (so a rollback keeps it)."""
        v = self.get()
        return {k: v[k] for k in FILE_KEYS}

    
    def update(self, patch, available_gpus):
        if not isinstance(patch, dict):
            raise SettingsError('Settings must be a JSON object.')
        unknown = set(patch) - set(API_KEYS)
        if unknown:
            raise SettingsError('These settings cannot be changed here: ' + ', '.join(sorted(unknown)))
        clean = validate(patch, available_gpus, allow_all=True)
        extra = {k: clean.pop(k) for k in EXTRA_KEYS if k in clean}
        with self._lock:
            old_values, old_chosen, old_extra = dict(self.values), dict(self.chosen), dict(self.extra)
            new_values, new_chosen = dict(self.values), dict(self.chosen)
            if 'gpus' in clean:
                new_chosen['gpus'] = clean['gpus'] != ALL_GPUS
                new_values['gpus'] = clean.pop('gpus')
            new_values.update(clean)
            self.values, self.chosen = new_values, new_chosen
            self.extra = dict(old_extra, **extra)
            try:
                if clean or 'gpus' in patch or not extra:
                    self._write_locked()
                if extra:
                    atomic_write_json(self.extra_path, dict(self.extra_kept, **self.extra))
            except BaseException:
                self.values, self.chosen, self.extra = old_values, old_chosen, old_extra
                raise
            if 'gpus' in patch:
                self.origin['gpus'] = 'chosen' if new_chosen['gpus'] else 'default'
        self.log.info('settings_changed', 'Settings changed', data={'old': dict(old_values, **old_extra),
                                                                    'new': dict(new_values, **self.extra),
                                                                    'gpus_chosen': new_chosen['gpus']})
        return self.get()

    def _write_locked(self):
        """settings.json (earlier schema) and then the meta record of what was chosen. Called with the lock held."""
        values, chosen = dict(self.values), dict(self.chosen)
        values['gpus'] = list(values['gpus']) if chosen['gpus'] else self.default_gpus()
        data = {k: values[k] for k in FILE_KEYS}
        atomic_write_json(self.path, data)
        atomic_write_json(self.meta_path, {'schema': META_SCHEMA,
                                           'gpus': {'chosen': chosen['gpus'], 'saved': data['gpus']},
                                           'ram_cap_gb': {'chosen': chosen['ram_cap_gb'], 'saved': data['ram_cap_gb']}})

    def save_defaults_if_missing(self):
        if not self.path.exists():
            with self._lock:
                self._write_locked()


def env_float(name, default):
    """Test/tuning knob from the environment (documented in runner.py); invalid values are refused loudly."""
    v = os.environ.get(name)
    if v is None or v == '':
        return default
    try:
        return float(v)
    except ValueError:
        raise SettingsError(f'Environment variable {name} must be a number (got {v!r})')
