"""Comfy main implementation."""


import os
import runpy
import sys

# The engine has its own Python; reuse the desktop package's verified MSVC
# libraries before Comfy imports Torch, retaining the DLL-directory handle.
_app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_dll_search_support = runpy.run_path(os.path.join(_app_root, 'runtime', 'windows_dlls.py'))

root, site = sys.argv[1], sys.argv[2]
sys.path[:0] = [root, site]
for k in ('PYTORCH_CUDA_ALLOC_CONF', 'PYTORCH_ALLOC_CONF'):
    parts = [x for x in os.environ.get(k, '').split(',') if x and not x.strip().lower().startswith('backend:')]
    os.environ[k] = ','.join([*parts, 'backend:native'])
sys.argv = [os.path.join(root, 'main.py'), *sys.argv[3:]]
runpy.run_path(sys.argv[0], run_name='__main__')
