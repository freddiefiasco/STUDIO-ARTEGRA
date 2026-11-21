"""engine/bxf/memory.finish_commit_gb, the finish's own commit as an upper bound (contracts.g1u): it bounds every registered
fresh-process measurement of the finish (tests/fixtures/bxf_finish_memory.json: sizes, tier, band budget, the ops run whole,
and the measured peak less the process's inputs-only baseline), per tier and per op classification, including whole-mapped
ops' transients and lf.dm on a narrow stage; it grows with the plane, the budget and the process count; only registered
values are accepted; its EW list is the finish's. numpy only."""
import ast
import importlib
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests' / 'fixtures' / 'bxf_finish_memory.json'


def engine(name):
    pkg = 'cu_banded_engine'
    if pkg not in sys.modules:
        spec = importlib.util.spec_from_file_location(pkg, ROOT / 'engine' / '__init__.py',
                                                      submodule_search_locations=[str(ROOT / 'engine')])
        mod = importlib.util.module_from_spec(spec)
        sys.modules[pkg] = mod
        spec.loader.exec_module(mod)
    return importlib.import_module(f'{pkg}.{name}')


class TheBound(unittest.TestCase):
    def test_it_bounds_every_registered_measurement(self):
        M = engine('bxf.memory')
        data = json.loads(FIXTURE.read_text(encoding='utf8'))
        self.assertGreaterEqual(len(data['measurements']), 4)
        tiers = set()
        for m in data['measurements']:
            whole = data['whole_ops'][m['whole_ops']] if isinstance(m['whole_ops'], str) else m['whole_ops']
            bound = M.finish_commit_gb(m['output_size'], m['input_size'], m['band_gb'], m['processes'], m['tier'], whole)
            self.assertGreaterEqual(bound, m['own_gib'], m)
            tiers.add(m['tier'])
        self.assertEqual(tiers, {'bxf', 'tier3'})
        self.assertTrue(any(m['whole_ops'] == 'all' for m in data['measurements']))       # every op whole: the worst transient
        self.assertTrue(any(m['output_size'][0] < M.NARROW_W for m in data['measurements']))   # a narrow stage (lf.dm whole)

    def test_it_grows_with_the_plane_the_budget_and_the_pool(self):
        M = engine('bxf.memory')
        f = M.finish_commit_gb
        self.assertLess(f((8000, 5000), (4000, 2500), 2.0, 1, 'bxf'), f((16000, 10000), (8000, 5000), 2.0, 1, 'bxf'))
        self.assertLess(f((8000, 5000), (4000, 2500), 2.0, 1, 'bxf'), f((8000, 5000), (4000, 2500), 6.0, 1, 'bxf'))
        self.assertLess(f((8000, 5000), (4000, 2500), 2.0, 1, 'bxf'), f((8000, 5000), (4000, 2500), 2.0, 2, 'bxf'))
        self.assertLess(f((8000, 5000), (4000, 2500), 2.0, 1, 'bxf'), f((8000, 5000), (4000, 2500), 2.0, 1, 'tier3'))
        self.assertEqual(f((8000, 5000), (4000, 2500), 2.0, 1, 'tier3'), f((8000, 5000), (4000, 2500), 2.0, 1, 3))
        self.assertEqual(f((8000, 5000), (4000, 2500), 2.0, 1, 'bxf'), f((8000, 5000), (4000, 2500), 2.0, 1, 0))

    def test_whole_ops_and_narrow_stages_add_their_transient(self):
        M = engine('bxf.memory')
        f = M.finish_commit_gb
        base = f((8000, 5000), (4000, 2500), 2.0, 1, 'bxf')
        self.assertAlmostEqual(f((8000, 5000), (4000, 2500), 2.0, 1, 'bxf', ['torch _blur s=4.0 (_sep conv)']) - base,
                               40 * 8000 * 5000 / 2 ** 30)
        self.assertAlmostEqual(f((8000, 5000), (4000, 2500), 2.0, 1, 'bxf', ['v4.fin_post srcwarm']) - base,
                               260 * 8000 * 5000 / 2 ** 30)
        self.assertAlmostEqual(f((8000, 5000), (4000, 2500), 2.0, 1, 'bxf', ['v4.luma']) - base,      # every pass names EW
                               340 * 8000 * 5000 / 2 ** 30)
        self.assertEqual(f((8000, 5000), (4000, 2500), 2.0, 1, 'bxf', ['not an op']), base)
        narrow = f((1200, 13828), (600, 6914), 2.0, 1, 'bxf')
        self.assertIn('lf.dm', M.whole_passes((), 1200))
        self.assertNotIn('lf.dm', M.whole_passes((), 5600))
        self.assertAlmostEqual(narrow - f((1200, 13828), (600, 6914), 2.0, 1, 'bxf', ()) , 0.0)
        self.assertGreater(narrow, 2.0 + M.BXF_GB + 40 * 1200 * 13828 / 2 ** 30 - 1e-9)

    def test_registered_values_only(self):
        M = engine('bxf.memory')
        for bad in ((4.0, 1, 'bxf'), (2.0, 3, 'bxf'), (2.0, 1, 'tier1'), (2.0, 1, 'ladder')):
            with self.assertRaises((AssertionError, ValueError)):
                M.finish_commit_gb((100, 100), (50, 50), *bad)
        with self.assertRaises(ValueError):
            M.finish_commit_gb((0, 100), (50, 50), 2.0, 1, 'bxf')

    def test_pass_keys_and_the_finishs_ew(self):
        M = engine('bxf.memory')
        self.assertEqual(M.pass_key('acc2.4'), 'acc<it>.4')
        self.assertEqual(M.pass_key('ld0.3.sq'), 'ld<it>.3.sq')
        self.assertEqual(M.pass_key('gg3.0'), 'gg<it>.0')
        self.assertEqual(M.pass_key('ycur1'), 'ycur<it>')
        self.assertEqual(M.pass_key('eq2'), 'eq2')
        src = (ROOT / 'node_pack' / 'claude_banded' / 'bxf' / 'finish.py').read_text(encoding='utf8')
        ew = next(n for n in ast.parse(src).body if isinstance(n, ast.Assign) and getattr(n.targets[0], 'id', '') == 'EW')
        self.assertEqual(ast.literal_eval(ew.value), M.EW)
        self.assertGreater(M.tier3_gb_per_output_mp(), 0)


if __name__ == '__main__':
    unittest.main()
