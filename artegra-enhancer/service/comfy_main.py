"""Comfy main implementation."""


import os
import runpy
import sys

root, site = sys.argv[1], sys.argv[2]
sys.path[:0] = [root, site]
for k in ('PYTORCH_CUDA_ALLOC_CONF', 'PYTORCH_ALLOC_CONF'):
    parts = [x for x in os.environ.get(k, '').split(',') if x and not x.strip().lower().startswith('backend:')]
    os.environ[k] = ','.join([*parts, 'backend:native'])
sys.argv = [os.path.join(root, 'main.py'), *sys.argv[3:]]
runpy.run_path(sys.argv[0], run_name='__main__')
