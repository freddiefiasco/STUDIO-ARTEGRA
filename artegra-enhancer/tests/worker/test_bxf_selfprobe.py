"""Gate G1u's core (engine/bxf/selfprobe.py, B18): its ops are G1's (tools/gate_g1.py) under the same names with the same calls
(equal values on the same synthetic planes), so a local table speaks the committed tables' language; an injected op that
differs band against whole is classed whole-mapped, its table is written in the g1_table format for this environment and read
back by g1.load(local=...); without forced heights it runs each op at exactly the band heights the executor picks for it at the
given widths and budgets, skipping none of them, so the table covers every call of the finish there (fin-chk-1); run by path,
isolated, it exits 0 with a table, 2 past its time limit and 3 on a bad request or a shape over --cap-gib, each with a plain
reason. Skipped where torch or scipy is not installed:
    python -B -m unittest tests.worker.test_bxf_selfprobe   (artegra-enhancer folder). Synthetic only."""
import importlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

HAVE = all(importlib.util.find_spec(m) is not None for m in ('torch', 'scipy'))
ROOT = Path(__file__).resolve().parents[2]


def engine(name):
    pkg = 'cu_banded_engine'
    if pkg not in sys.modules:
        spec = importlib.util.spec_from_file_location(pkg, ROOT / 'engine' / '__init__.py',
                                                      submodule_search_locations=[str(ROOT / 'engine')])
        mod = importlib.util.module_from_spec(spec)
        sys.modules[pkg] = mod
        spec.loader.exec_module(mod)
    return importlib.import_module(f'{pkg}.{name}')


def gate_g1():
    spec = importlib.util.spec_from_file_location('cu_test_g1u_gate_g1', ROOT / 'tools' / 'gate_g1.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@unittest.skipUnless(HAVE, 'torch and scipy are not installed here (run on the worker runtime)')
class TheProbesAreG1s(unittest.TestCase):
    def test_same_names_classes_reach_and_values(self):
        G1, sp = gate_g1(), engine('bxf.selfprobe')
        V, toe = sp.classic(ROOT / 'node_pack' / 'claude_creative')
        mine = {p.name: p for p in sp.ops(V, toe)}
        theirs = {p.name: p for p in G1.probes() if p.cls != 'pool'}
        self.assertEqual(sorted(mine), sorted(theirs))
        T, W = 583, 67
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            td = Path(td)
            d1, d2 = sp.Data(V, T, W, seed=3), G1.Data(T, W, seed=3)
            for k in ('u8', 'rgb', 'rgb2', 'L', 'L2', 'Y2', 'mask', 'mask2', 'lab', 'energy', 'f64'):
                np.testing.assert_array_equal(d1[k], d2[k], k)
            m1, m2 = sp.Mapped(d1, td / 'a'), G1.Mapped(d2, td / 'b')
            for name, p in mine.items():
                q = theirs[name]
                self.assertEqual((p.cls, p.kind, p.reach, p.bpp), (q.cls, q.kind, q.reach, q.bpp), name)
                if p.kind == 'local':
                    a, b = sp._outs(p.fn(*p.inputs(d1))), G1._outs(q.fn(*q.inputs(d2)))
                    self.assertEqual(len(a), len(b), name)
                    for x, y in zip(a, b):
                        self.assertEqual(sp.differing(x, y)[0], 0, name)
                else:
                    (td / 'c').mkdir(exist_ok=True)
                    self.assertEqual(p.run(d1, m1, T, W, 288, td / 'c'), q.run(d2, m2, T, W, 288, td / 'c'), name)
            m1.close()
            m2.close()

    def test_the_routed_pool_probes_run_at_every_target(self):
        """fin-chk-2: the probes the finish's pool routes read (finish.pool_probe of POOL_ROUTES' ops and params) run at the
        production widths up to 32,000 px and at every registered target's plane; the other pool probes at the widths."""
        G1 = gate_g1()
        spec = importlib.util.spec_from_file_location('cu_test_g1u_finish',
                                                      ROOT / 'node_pack' / 'claude_banded' / 'bxf' / 'finish.py')
        F = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(F)
        V = G1.v4()
        routed = {F.pool_probe('gaussian_filter', {'sigma': float(V.DEF['beta'] * V.SIG[0])}, n) for n in (2, 4)}
        routed |= {F.pool_probe('gradient_mag', {}, n) for n in (2, 4)}
        self.assertEqual(sorted(F.POOL_ROUTES), ['gg<it>.0', 'gmz'])
        pool = {p.name: p for p in G1.probes() if p.cls == 'pool'}
        self.assertLessEqual(routed, set(pool))
        for name, p in pool.items():
            self.assertEqual(tuple(p.widths), tuple(G1.POOL_WIDTHS), name)
            self.assertEqual(p.targets, name in routed, name)
        self.assertTrue(all(p.targets for p in G1.probes() if p.cls != 'pool'))


@unittest.skipUnless(HAVE, 'torch and scipy are not installed here (run on the worker runtime)')
class AnInjectedDifferingOp(unittest.TestCase):
    def test_is_classed_whole_written_and_read_back(self):
        sp, g1, g1t = engine('bxf.selfprobe'), engine('bxf.g1'), engine('bxf.g1_table')
        bad = sp.Op('injected band-dependent', 'E1', 'local', fn=lambda L: (L - L.mean(dtype=np.float32)).astype(np.float32),
                    inputs=lambda d: [d['L']], reach=0, bpp=8)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            td = Path(td)
            table = sp.probe(300, td / 'planes', seconds=600, extra_ops=[bad], only='gaussian_filter s=1.0', heights=(288, 576))
            self.assertEqual(sorted(table['ops']), ['gaussian_filter s=1.0', 'injected band-dependent'])
            self.assertEqual(table['ops']['injected band-dependent']['verdict'], 'whole')
            self.assertGreater(table['ops']['injected band-dependent']['differing'], 0)
            good = table['ops']['gaussian_filter s=1.0']
            self.assertEqual(good['verdict'], 'banded')
            self.assertEqual(good['domain']['key'], 'height')
            self.assertEqual(sorted(good['domain']['frontier']), ['288', '576'])
            self.assertEqual(table['environment'], g1.environment())
            self.assertEqual(table['widths'], [300, 8192])
            path = td / 'local.json'
            sp.write(table, path)
            env = g1.environment()
            with mock.patch.multiple(g1t, TABLES=[], TABLE=None):
                t = g1.load(env=env, local=str(path))
                self.assertTrue(t.applies)
                self.assertTrue(t.banded('gaussian_filter s=1.0', geom=g1.Geometry(289, 300, 288, 4)))
                self.assertTrue(t.banded('gaussian_filter s=1.0', geom=g1.Geometry(6000, 8192, 576, 4)))
                self.assertFalse(t.banded('gaussian_filter s=1.0', geom=g1.Geometry(6000, 8193, 576, 4)))   # wider than probed
                self.assertFalse(t.banded('gaussian_filter s=1.0', geom=g1.Geometry(6000, 8192, 1152, 4)))  # a height not probed
                self.assertFalse(t.banded('injected band-dependent', geom=g1.Geometry(289, 300, 288, 0)))
            committed = {'environment': env, 'ops': {'injected band-dependent': {'verdict': 'banded', 'domain': {
                'key': 'height', 'w_max': {'288': 32000}, 'frontier': {'288': [[128, 1]]}}}}}
            with mock.patch.multiple(g1t, TABLES=[committed], TABLE=committed):
                self.assertTrue(g1.load(env=env, local='').banded('injected band-dependent', geom=g1.Geometry(600, 300, 288, 0)))
                t = g1.load(env=env, local=str(path))                       # the local table vetoes what it saw differ
                self.assertFalse(t.banded('injected band-dependent', geom=g1.Geometry(600, 300, 288, 0)))


@unittest.skipUnless(HAVE, 'torch and scipy are not installed here (run on the worker runtime)')
class ItMeasuresWhatTheExecutorUses(unittest.TestCase):
    def test_every_height_the_executor_picks_is_measured_and_covered(self):
        sp, g1, M = engine('bxf.selfprobe'), engine('bxf.g1'), engine('bxf.memory')
        env = g1.environment()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            for only in ('v4.rgb2lab', 'gaussian_filter s=1.0', 'E5 median'):
                table = sp.probe([200, 1500], Path(td) / 'planes', seconds=900, only=only, band_gb=[2.0])
                self.assertEqual(table['widths'], [200, 1500, 8192])
                self.assertEqual(table['band_gb'], [2.0])
                self.assertIsNone(table['forced_heights'])
                self.assertGreater(table['largest_shape_gib'], 0)
                op = table['ops'][only]
                self.assertNotIn('skipped', op)
                self.assertEqual(op['verdict'], 'banded', op)
                planned = sp.plan([only], [200, 1500], [2.0])
                keys = {str(h) for (W, h) in planned} if op['kind'] == 'local' else {'any'}
                self.assertEqual(sorted(op['domain']['frontier']), sorted(keys))
                t = g1.Table(table, env)
                for W in (200, 1500, 8192):
                    for _, kind, ops_, geom, _ in M.lookups((W, 9000), 2.0):
                        if only in ops_:
                            self.assertTrue(t.covers(only, geom), (only, W, geom))
            with self.assertRaises(sp.TooLarge):
                sp.probe([200], Path(td) / 'big', seconds=900, only='v4.rgb2lab', band_gb=[2.0], cap_gib=1e-6)
            self.assertFalse((Path(td) / 'big').exists())          # refused before any plane was written


@unittest.skipUnless(HAVE, 'torch and scipy are not installed here (run on the worker runtime)')
class ByPath(unittest.TestCase):
    def cmd(self, *args):
        import torch
        import scipy
        site = sorted({str(Path(m.__file__).resolve().parents[1]) for m in (np, scipy, torch)})
        return [sys.executable, '-I', '-S', '-B', str(ROOT / 'engine' / 'bxf' / 'selfprobe.py'), *[str(a) for a in args],
                *[x for d in site for x in ('--site', d)]]

    def test_runs_isolated_by_path_and_exits_plainly(self):
        g1 = engine('bxf.g1')
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            out = Path(td) / 't.json'
            r = subprocess.run(self.cmd('--out', out, '--width', 200, '--only', 'gaussian_filter s=1.0'), capture_output=True,
                               text=True, timeout=1800)
            self.assertEqual(r.returncode, 0, r.stderr[-3000:])
            t = json.loads(out.read_text(encoding='utf8'))
            self.assertEqual(t['gate'], 'G1u')
            self.assertEqual(t['environment'], g1.environment())
            self.assertEqual(t['ops']['gaussian_filter s=1.0']['verdict'], 'banded')
            late = Path(td) / 'late.json'
            r = subprocess.run(self.cmd('--out', late, '--width', 200, '--seconds', 0), capture_output=True, text=True, timeout=1800)
            self.assertEqual(r.returncode, 2)
            self.assertIn('ran out of time', r.stderr)
            self.assertFalse(late.exists())
            r = subprocess.run(self.cmd('--out', late, '--width', 0), capture_output=True, text=True, timeout=600)
            self.assertEqual(r.returncode, 3)
            self.assertIn('--width', r.stderr)
            self.assertNotIn('Traceback', r.stderr)
            two = Path(td) / 'two.json'
            r = subprocess.run(self.cmd('--out', two, '--width', 200, '--width', '300', '--band-gb', 2, '--only',
                                        'gaussian_filter s=1.0'), capture_output=True, text=True, timeout=1800)
            self.assertEqual(r.returncode, 0, r.stderr[-3000:])
            t = json.loads(two.read_text(encoding='utf8'))
            self.assertEqual((t['widths'], t['band_gb']), ([200, 300, 8192], [2.0]))
            for bad, words in ((('--band-gb', 4), '--band-gb'), (('--cap-gib', 0.000001), 'over the cap')):
                r = subprocess.run(self.cmd('--out', late, '--width', 200, '--only', 'gaussian_filter s=1.0', *bad),
                                   capture_output=True, text=True, timeout=600)
                self.assertEqual(r.returncode, 3, bad)
                self.assertIn(words, r.stderr)
                self.assertNotIn('Traceback', r.stderr)
                self.assertFalse(late.exists())


if __name__ == '__main__':
    unittest.main()
