"""Config implementation."""


import json
import os
import shutil
from dataclasses import dataclass, field, fields
from pathlib import Path

from engine import graph_v5t
from service.util import sha256_file, sha256_bytes

APP_ROOT = Path(__file__).resolve().parents[1]

_RUNTIME = APP_ROOT / 'runtime-not-configured'
_MODELS = APP_ROOT / 'models-not-configured'
DEFAULTS = {
    'runtime_python': _RUNTIME / 'python.exe',
    'site_packages': _RUNTIME / 'site-packages',
    'comfy_main': _RUNTIME / 'ComfyUI' / 'main.py',
    'models_dir': _MODELS,
    'claude_models_dir': _MODELS,
    'node_pack_dir': APP_ROOT / 'node_pack' / 'claude_creative',
    'default_output_dir': Path.home() / 'Pictures' / 'Artegra Enhancer',
    'vae_approx_dir': _MODELS / 'vae_approx',
}
STATE_DIRS = ('jobs', 'media', 'work', 'workers', 'logs')

MODEL_FOLDERS = {'ckpt': 'checkpoints', 'upscaler': 'upscale_models', 'cn_tile': 'controlnet', 'cn_line': 'controlnet',
                 'sam': 'checkpoints'}
MANIFEST_NAME = 'MANIFEST.json'
NODE_PACK_PROBLEM = 'Some Creative Upscaler engine files are missing or changed. Reinstall Creative Upscaler.'


class ConfigError(ValueError):
    pass


@dataclass
class Config:
    state_dir: Path
    fake_engine: bool = False
    runtime_python: Path = DEFAULTS['runtime_python']
    site_packages: Path = DEFAULTS['site_packages']
    comfy_main: Path = DEFAULTS['comfy_main']
    models_dir: Path = DEFAULTS['models_dir']
    claude_models_dir: Path = DEFAULTS['claude_models_dir']
    node_pack_dir: Path = DEFAULTS['node_pack_dir']
    default_output_dir: Path = DEFAULTS['default_output_dir']
    vae_approx_dir: Path = DEFAULTS['vae_approx_dir']
    
    
    two_card_proof: bool = False
    overrides: dict = field(default_factory=dict)

    @property
    def app_root(self):
        return APP_ROOT

    @property
    def jobs_dir(self):
        return self.state_dir / 'jobs'

    @property
    def media_dir(self):
        return self.state_dir / 'media'

    @property
    def work_dir(self):
        return self.state_dir / 'work'

    @property
    def workers_dir(self):
        return self.state_dir / 'workers'

    @property
    def logs_dir(self):
        return self.state_dir / 'logs'

    @property
    def manifest_path(self):
        return self.node_pack_dir.parent / MANIFEST_NAME

    def describe(self):
        return {f.name: str(getattr(self, f.name)) for f in fields(self) if f.name not in ('overrides',)}


PATH_KEYS = [k for k in DEFAULTS]


def load(state_dir, fake_engine=False, config_file=None):
    state_dir = Path(state_dir).resolve()
    cfg = Config(state_dir=state_dir, fake_engine=bool(fake_engine))
    path = Path(config_file) if config_file else state_dir / 'config.json'
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding='utf8'))
        except (OSError, ValueError) as e:
            raise ConfigError(f'The configuration file {path} could not be read: {e}')
        if not isinstance(data, dict):
            raise ConfigError(f'The configuration file {path} must contain a JSON object')
        unknown = set(data) - set(PATH_KEYS)
        if unknown:
            raise ConfigError(f'The configuration file {path} has unknown keys: ' + ', '.join(sorted(unknown)))
        for k, v in data.items():
            if not isinstance(v, str) or not v.strip():
                raise ConfigError(f'{k} in {path} must be a folder or file path')
            value = Path(v).expanduser()
            setattr(cfg, k, value.resolve() if value.is_absolute() else (path.parent / value).resolve())
        cfg.overrides = dict(data)
    elif config_file:
        raise ConfigError(f'The configuration file {path} does not exist')
    return cfg


def ensure_state_dirs(cfg):
    cfg.state_dir.mkdir(parents=True, exist_ok=True)
    for d in STATE_DIRS:
        (cfg.state_dir / d).mkdir(exist_ok=True)


NODE_PACK_REPAIR = ('the pack and its MANIFEST.json must come from the same engine build: redeploy the app with its own '
                    'node_pack/ (install/deploy.py); do not run tools/sync_node_pack.py, whose source is the older 9ea176c pack')


def tree_sha256(files):
    """One hash for the whole pack: sha256 over sorted 'relative/path:sha256' lines."""
    return sha256_bytes('\n'.join(f'{k}:{files[k]["sha256"]}' for k in sorted(files)).encode('utf8'))


def verify_node_pack(node_pack_dir, manifest_path=None):
    """Check the vendored node pack against MANIFEST.json. Returns {ok, tree_sha256, files, problems, details}: `problems` is
    the plain sentence for the user, `details` the developer facts for the log (files, manifest, the repair tool)."""
    node_pack_dir = Path(node_pack_dir)
    manifest_path = Path(manifest_path) if manifest_path else node_pack_dir.parent / MANIFEST_NAME
    res = {'ok': False, 'tree_sha256': None, 'files': 0, 'problems': [], 'details': []}
    if not node_pack_dir.is_dir():
        res['problems'].append(NODE_PACK_PROBLEM)
        res['details'].append(f'node pack folder missing: {node_pack_dir}; ' + NODE_PACK_REPAIR)
        return res
    try:
        man = json.loads(manifest_path.read_text(encoding='utf8'))
        files = man['files']
        if not isinstance(files, dict) or not files:
            raise ValueError('no files listed')
    except (OSError, ValueError, KeyError, TypeError) as e:
        res['problems'].append(NODE_PACK_PROBLEM)
        res['details'].append(f'node pack manifest {manifest_path} missing or unreadable ({e}); ' + NODE_PACK_REPAIR)
        return res
    bad = []
    for rel, meta in sorted(files.items()):
        p = node_pack_dir / rel
        try:
            if sha256_file(p) != meta['sha256']:
                bad.append(f'{rel} (changed)')
        except OSError:
            bad.append(f'{rel} (missing)')
    extra = sorted(str(p.relative_to(node_pack_dir)).replace('\\', '/') for p in node_pack_dir.rglob('*.py')
                   if '__pycache__' not in p.parts and str(p.relative_to(node_pack_dir)).replace('\\', '/') not in files)
    bad += [f'{rel} (not in the manifest)' for rel in extra]
    if bad:
        res['problems'].append(NODE_PACK_PROBLEM)
        res['details'].append('node pack does not match its manifest: ' + ', '.join(bad[:20])
                              + (' ...' if len(bad) > 20 else '') + '; ' + NODE_PACK_REPAIR)
        return res
    res.update(ok=True, tree_sha256=man.get('tree_sha256') or tree_sha256(files), files=len(files))
    if man.get('tree_sha256') and man['tree_sha256'] != tree_sha256(files):
        res.update(ok=False)
        res['problems'].append(NODE_PACK_PROBLEM)
        res['details'].append('node pack manifest tree hash does not match its file list; ' + NODE_PACK_REPAIR)
    return res


def find_model(cfg, key):
    name = graph_v5t.MODELS[key]
    for base in (cfg.models_dir, cfg.claude_models_dir):
        p = Path(base) / MODEL_FOLDERS[key] / name
        if p.is_file():
            return p
    return None


def output_dir_problem(path):
    """Plain sentence if the output folder cannot be used, else None (no files are created here)."""
    p = Path(path)
    if p.is_dir():
        if not os.access(p, os.W_OK):
            return f'The output folder {p} is read-only. Choose another folder in Output.'
        return None
    parent = p.parent
    if parent.is_dir():
        return None   
    return f'The output folder {p} is not reachable. Choose another folder in Output.'


def problems(cfg, output_dir=None, details=None):
    """Plain sentences for /health. Engine paths are checked only for the real engine. When `details` is a list, the
    developer facts behind each problem (paths, file names) are appended to it for the log."""
    details = details if details is not None else []
    out = []
    np_res = verify_node_pack(cfg.node_pack_dir, cfg.manifest_path)
    out += np_res['problems']
    details += np_res['details']
    if output_dir is not None:
        msg = output_dir_problem(output_dir)
        if msg:
            out.append(msg)
    for d in STATE_DIRS:
        if not (cfg.state_dir / d).is_dir():
            out.append(f'The app state folder {cfg.state_dir / d} is missing.')
    if cfg.fake_engine:
        return out
    missing_runtime = [str(p) for p, ok in ((cfg.runtime_python, Path(cfg.runtime_python).is_file()),
                                            (cfg.site_packages, Path(cfg.site_packages).is_dir()),
                                            (cfg.comfy_main, Path(cfg.comfy_main).is_file())) if not ok]
    if missing_runtime:
        root = Path(cfg.runtime_python).parents[2] if len(Path(cfg.runtime_python).parents) > 2 else Path(cfg.runtime_python)
        out.append(f'The image engine is not installed where expected ({root}). Reinstall it or ask for help.')
        details.append('engine runtime paths missing: ' + ', '.join(missing_runtime))
    if not Path(cfg.models_dir).is_dir():
        out.append(f'The models folder {cfg.models_dir} is not reachable. Connect the network drive, then try again.')
    else:
        missing = [graph_v5t.MODELS[k] for k in MODEL_FOLDERS if find_model(cfg, k) is None]
        if missing:
            out.append(f'Some model files are missing from {cfg.models_dir}: ' + ', '.join(missing) + '.')
    if shutil.which('nvidia-smi') is None:
        out.append('The graphics card driver tools were not found, so the graphics cards cannot be used. Reinstall the '
                   'NVIDIA graphics driver.')
        details.append('nvidia-smi not on PATH')
    return out
