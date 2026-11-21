"""G0d for every engine/bxf module (5.0.2 wave 2 changed g1, g1_table, local, pool, _child, selection and added selfprobe and
memory): importing each, as the worker loads the engine (by path as cu_banded_engine), adds no module outside numpy and the
package itself (no torch, no scipy), and changes no global state (sys.path, the recursion limit, numpy's print options and
error state, os.environ, the thread count, the working folder). Each import runs in a fresh process. numpy only."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULES = ('g1', 'g1_table', 'local', 'pool', 'selection', 'selfprobe', 'memory', 'ops', 'uniform', 'pooling', 'components',
           'work')

PROBE = r'''
import importlib, importlib.util, json, os, sys, threading
import numpy as np
root, name = sys.argv[1], sys.argv[2]
def state():
    return {'path': list(sys.path), 'rec': sys.getrecursionlimit(), 'np': repr(np.get_printoptions()), 'err': np.geterr(),
            'env': dict(os.environ), 'threads': threading.active_count(), 'cwd': os.getcwd()}
eng = os.path.join(root, 'engine')
spec = importlib.util.spec_from_file_location('cu_banded_engine', os.path.join(eng, '__init__.py'),
                                              submodule_search_locations=[eng])
m = importlib.util.module_from_spec(spec)
sys.modules['cu_banded_engine'] = m
spec.loader.exec_module(m)
before, mods = state(), set(sys.modules)
importlib.import_module('cu_banded_engine.bxf.' + name)
after = state()
new = sorted(k for k in set(sys.modules) - mods if not k.startswith('cu_banded_engine'))
print(json.dumps({'same': before == after, 'diff': [k for k in before if before[k] != after[k]], 'new': new}))
'''


class G0d(unittest.TestCase):
    def test_importing_each_bxf_module_changes_nothing(self):
        for name in MODULES:
            r = subprocess.run([sys.executable, '-B', '-c', PROBE, str(ROOT), name], capture_output=True, text=True, timeout=300)
            self.assertEqual(r.returncode, 0, (name, r.stderr[-2000:]))
            out = json.loads(r.stdout.strip().splitlines()[-1])
            self.assertTrue(out['same'], (name, out['diff']))
            heavy = [k for k in out['new'] if k.split('.')[0] in ('torch', 'scipy', 'PIL')]
            self.assertEqual(heavy, [], name)


if __name__ == '__main__':
    unittest.main()
