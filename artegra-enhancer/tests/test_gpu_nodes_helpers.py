"""Shared helpers of the gpu-nodes tests (no tests here): the Large-image node pack loaded by path under a private name, its
new modules, and a stand-in for the classic node pack where a module looks it up (_classic_pack)."""
import importlib
import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK_DIR = ROOT / 'node_pack' / 'claude_banded'
PACK_NAME = 'claude_banded_gpu_tests'
MODULES = {'CUCannyPlane': 'canny_plane', 'CUEncodePlane': 'vae_planes', 'CUDecodePlane': 'vae_planes',
           'ClaudeSpotTilesBanded': 'spot_banded', 'CUControlNetApplyPlane': 'cn_plane', 'CUSam3DetectLean': 'sam_plane'}


def load_pack():
    """node_pack/claude_banded as a package named PACK_NAME (registered, so its modules' relative imports resolve)."""
    if PACK_NAME in sys.modules:
        return sys.modules[PACK_NAME]
    spec = importlib.util.spec_from_file_location(PACK_NAME, PACK_DIR / '__init__.py', submodule_search_locations=[str(PACK_DIR)])
    mod = importlib.util.module_from_spec(spec)
    sys.modules[PACK_NAME] = mod
    try:
        spec.loader.exec_module(mod)
    except BaseException:
        del sys.modules[PACK_NAME]
        raise
    return mod


def module(name):
    """One of the package's new modules (canny_plane, vae_planes, spot_banded, noise_banded, cn_plane, sam_plane)."""
    load_pack()
    return importlib.import_module(f'{PACK_NAME}.{name}')


def node_class(name):
    return getattr(module(MODULES[name]), name)


def fake_classic_pack(name='cu_fake_classic_pack', **attrs):
    """A module that _classic_pack() finds (NODE_CLASS_MAPPINGS with ClaudeV4Finish and ClaudeShadowToe, shadow_toe_u8), with
    __path__ set to node_pack/claude_creative so `<name>.live`, `.spot_timing`, `.noise` and `.sam_lean` import the classic
    files themselves (its __init__.py is not run). Install with mock.patch.dict(sys.modules, {name: mod})."""
    mod = types.ModuleType(name)
    mod.__path__ = [str(ROOT / 'node_pack' / 'claude_creative')]
    mod.NODE_CLASS_MAPPINGS = {'ClaudeV4Finish': object, 'ClaudeShadowToe': object, **attrs.pop('mappings', {})}
    mod.shadow_toe_u8 = lambda *a: None
    for k, v in attrs.items():
        setattr(mod, k, v)
    return mod
