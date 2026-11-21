"""A BXF pool process (python -I -S -B _child.py <engine dir> [package dir ...]): puts the parent's package folders on its path
(the parent's numpy and scipy, engine/bxf/pool.package_dirs), loads the engine package by path as cu_banded_engine (as
node_pack/claude_banded does), says 'ready',
then runs band jobs read from stdin (one JSON line each) on file-backed memory maps, answering one JSON line per job. It sets
no thread count and imports no torch. Started by engine/bxf/pool.py only."""
import importlib
import importlib.util
import json
import sys
from pathlib import Path


def _load(engine_dir):
    name = 'cu_banded_engine'
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, Path(engine_dir) / '__init__.py',
                                                      submodule_search_locations=[str(engine_dir)])
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    return importlib.import_module(name + '.bxf.pool')


def main():
    for d in reversed(sys.argv[2:]):
        if d not in sys.path:
            sys.path.insert(0, d)
    import numpy as np
    pool = _load(sys.argv[1])
    print('ready', flush=True)
    for line in sys.stdin:
        job = json.loads(line)
        if job.get('quit'):
            break
        try:
            ins = [np.memmap(s['path'], dtype=np.dtype(s['dtype']), mode='r', offset=s['offset'], shape=tuple(s['shape']))
                   for s in job['inputs']]
            outs = [np.memmap(s['path'], dtype=np.dtype(s['dtype']), mode='r+', offset=s['offset'], shape=tuple(s['shape']))
                    for s in job['outputs']]
            pool.run_parts(job['op'], job['params'], ins, outs, job['parts'], job['axis'])
            for o in outs:
                o.flush()
            del ins, outs
            print(json.dumps({'ok': True}), flush=True)
        except Exception as e:                    # reported to the parent, which raises
            print(json.dumps({'ok': False, 'error': f'{type(e).__name__}: {e}'}), flush=True)


if __name__ == '__main__':
    main()
