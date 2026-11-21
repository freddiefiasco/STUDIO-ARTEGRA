"""The banded exact finish (BXF, node_pack/claude_banded/bxf) against 5.0.1's classic chain (ClaudeV4Finish -> ClaudeShadowToe ->
SaveImage, read from node_pack/claude_creative by path), on procedural scenes that exercise every branch (tools/gate_g2.py's
scenes): G2 at a small size with bands of 288 rows (several band joins), every option case, with every op banded and with
every op whole; the node's tier-0 and tier-3 paths through planes; tier 3 byte-equal to the base build's node (the class pinned
in tests/fixtures/finish_banded_5_0_2_base.txt); G2r (a fresh process)
is in tools/gate_g2.py --fresh. Per-op oracle checks: every local op of gate G1, run whole on mapped planes, equals the classic
call on private arrays, and banded equals whole wherever G1 expects band-invariance at any size.
Skipped where torch or scipy is not installed:  python -B -m unittest tests.worker.test_bxf_finish  (artegra-enhancer folder)."""
import importlib
import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path

import numpy as np

HAVE = all(importlib.util.find_spec(m) is not None for m in ('torch', 'scipy'))
ROOT = Path(__file__).resolve().parents[2]


def tool(name):
    spec = importlib.util.spec_from_file_location(f'cu_test_{name}', ROOT / 'tools' / f'{name}.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


FAKE_CLASSIC = 'cu_test_fake_claude_creative'


def fake_classic_pack(G2, test):
    """A stand-in for the classic pack as ComfyUI loads it (CUFinishBanded finds it by its node classes), registered for
    `test` only: its cleanup removes it, because _classic_pack() takes the first such module in sys.modules, and a stand-in
    left behind would be found by later tests in the same process (the gpu-nodes tests install their own)."""
    name = FAKE_CLASSIC
    if name not in sys.modules:
        m = types.ModuleType(name)
        m.NODE_CLASS_MAPPINGS = {'ClaudeV4Finish': object, 'ClaudeShadowToe': object}
        m.shadow_toe_u8 = G2.classic_function('shadow_toe_u8')
        sys.modules[name] = m
        sys.modules[name + '.v4finish'] = G2.v4()
        test.addCleanup(lambda: [sys.modules.pop(k, None) for k in (name, name + '.v4finish')])
    return sys.modules[name]


@unittest.skipUnless(HAVE, 'torch and scipy are not installed here (run on the worker runtime)')
def numpy_scipy_banded(g1):
    """Every numpy / scipy op and classic function banded at any geometry, every torch op whole: the band machinery's joins on
    the ops G1 finds band-invariant on every runtime it ran on, at every width from 128 px. (Banding the torch ops too, the old
    'all' table, is not exact on every runtime: on torch 2.14.1 the band-split ops give 3 values up to 2 levels off in the 'hyb'
    case at this size, where G1 classes them whole or outside their domain; their exactness is G1's and G2's with the table.)"""
    class T(g1.AllBanded):
        def covers(self, op, geom=None):
            return not (op.startswith('torch') or op.startswith('E9') or op.startswith('E4 upsample'))

        def banded(self, *ops, geom=None):
            return bool(ops) and all(self.covers(o) for o in ops)
    return T()


class G2Small(unittest.TestCase):
    def test_every_case_banded_and_whole_gives_0_differing_values(self):
        """Every option case, 288-row bands (several joins): the numpy / scipy ops banded, every op whole, and this
        environment's own G1 table where one applies: 0 differing values in the stage output each time."""
        G2 = tool('gate_g2')
        F, E = G2.bxf_module()
        g1 = E('bxf.g1')
        tables = {'numpy-scipy banded': numpy_scipy_banded(g1), 'whole': 'whole'}
        if g1.load().applies:
            tables['g1'] = 'g1'
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            for label, table in tables.items():
                for name, opts in G2.CASES.items():
                    rec = G2.run_case(name, opts, 263, 301, Path(td) / label.replace(' ', '-'), table, 2.0, height=288)
                    self.assertEqual(rec['differing_values'], 0, (label, name, rec))
                    if name == 'v4f' and label == 'numpy-scipy banded':
                        br = rec['bxf']['branches']
                        for k in ('hw_kept', 'cf_components', 'litter_components', 'agree2_big', 'sky_kept'):
                            self.assertGreater(br.get(k, 0), 0, (k, br))

    def test_the_node_tiers_through_planes_and_tier_3_equals_the_base_builds_node(self):
        from tests.test_bxf_node import base_class
        G2 = tool('gate_g2')
        fake_classic_pack(G2, self)
        pack = G2.load_pack()
        bxf = importlib.import_module(pack.__name__ + '.bxf')
        self.assertIs(pack.NODE_CLASS_MAPPINGS['CUFinishBanded'], bxf.CUFinishBanded)
        base = base_class(pack)                     # the base build's tier-3-only node, not the registered class
        self.assertIsNot(base, bxf.CUFinishBanded)
        planes = pack._engine('planes')
        h, w = 263, 301
        pre, cr, st, it, pm, rm = G2.scene(h, w, 2, seed=5)
        size = (2 * w - 3, 2 * h - 5)
        opts = dict(G2.V4F, protect=True, release=True)
        want = G2.classic_chain(pre, cr, st, it, pm, rm, opts, size)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            td = Path(td)
            refs = {}
            for name, arr in (('creative', cr), ('structure', st), ('init', it), ('pre', pre), ('protect', pm[..., None]),
                              ('release', rm[..., None])):
                planes.from_array(td / f'{name}.plane', arr)
                refs[name] = pack.PlaneRef(td / f'{name}.plane', 'r1')
            kw = dict(smooth_lo=0.2, smooth_hi=0.5, protect_dilate=12, protect_feather=4.0, islands=True, chroma_clamp=True,
                      finish='bxf-1', toe_amount=0.40, toe_scale=0.06, output_width=size[0], output_height=size[1],
                      filename_prefix='cu', run_id='r1', quantize_8bit=True, keep_blacks='render', clamp='agree5', lf='hybmin',
                      glow='skygaps', fin_b0_hi=6.0, island_after_lf=True)
            ins = {k: refs[k] for k in ('creative', 'structure', 'init', 'pre', 'protect', 'release')}
            outs = {}
            try:
                for force in ('bxf', 'tier3'):
                    bxf.FORCE = force
                    r = bxf.CUFinishBanded().run(output_plane=str(td / f'out-{force}.plane'), **ins, **kw)
                    p = planes.validate(r['ui']['planes'][0]['path'], shape=(size[1], size[0], 3), dtype='u8')
                    self.assertIn('tier0' if force == 'bxf' else 'tier3', p.header['producer'])
                    outs[force] = p.read_rows(0, size[1])
            finally:
                bxf.FORCE = None
            today = base().run(output_plane=str(td / 'out-today.plane'), **ins, **kw)
            outs['today'] = planes.validate(today['ui']['planes'][0]['path']).read_rows(0, size[1])
            for k, v in outs.items():
                self.assertEqual(int(np.count_nonzero(v != want)), 0, k)
            self.assertEqual(planes.Plane.open(td / 'out-tier3.plane').data_sha256(),
                             planes.Plane.open(td / 'out-today.plane').data_sha256())
            self.assertFalse(any(p.name.startswith('bxf-work') for p in td.iterdir()))


@unittest.skipUnless(HAVE, 'torch and scipy are not installed here (run on the worker runtime)')
class TheStandInIsForOneTest(unittest.TestCase):
    def test_the_classic_stand_in_does_not_outlive_its_test(self):
        """Run in one process with the gpu-nodes tests (the merged worker suite), a stand-in left in sys.modules was the
        pack _classic_pack() found there, and their own stand-ins (with the classic files as submodules) went unused."""
        G2 = tool('gate_g2')
        inner = unittest.TestCase()
        self.assertIs(fake_classic_pack(G2, inner), sys.modules[FAKE_CLASSIC])
        inner.doCleanups()
        self.assertNotIn(FAKE_CLASSIC, sys.modules)
        self.assertNotIn(FAKE_CLASSIC + '.v4finish', sys.modules)


@unittest.skipUnless(HAVE, 'torch and scipy are not installed here (run on the worker runtime)')
class EveryOpTheFinishAsksAboutIsAG1Probe(unittest.TestCase):
    """A misspelt op name would read 'whole' (exact, but not memory-bounded): every name the BXF looks up must be a G1 probe."""

    def test_names(self):
        G1, G2 = tool('gate_g1'), tool('gate_g2')
        probes = {p.name for p in G1.probes()}
        asked = set()

        class Recording:
            applies = True
            mismatch = []

            def verdict(self, op):
                asked.add(op)
                return 'banded'

            def covers(self, op, geom=None):
                asked.add(op)
                return True

            def banded(self, *ops, geom=None):
                asked.update(ops)
                return True

            def why_not(self):
                return None
        F, E = G2.bxf_module()
        g1 = E('bxf.g1')
        orig = g1.load
        try:
            g1.load = lambda env=None: Recording()
            with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
                for name in ('v4f', 'lead', 'mm', 'hyb', 'pre_narrow', 'v4f-protect-release', 'no-clamp-glow'):
                    G2.run_case(name, G2.CASES[name], 263, 301, Path(td), 'g1', 2.0, height=288)
                G2.run_case('v4f', G2.CASES['v4f'], 263, 301, Path(td) / 'p2', 'g1', 2.0, height=288, processes=2)   # pool probes
        finally:
            g1.load = orig
        self.assertTrue(asked)
        self.assertEqual(sorted(asked - probes), [])


@unittest.skipUnless(HAVE, 'torch and scipy are not installed here (run on the worker runtime)')
class TheNodesNewInputs(unittest.TestCase):
    """contracts.finish_inputs / finish_tier: the band budget and the process count are pixel-neutral (every scratch plane and
    the stage output equal at 2, 3 and 6 GiB and at 1, 2 and 4 processes; with 2 and 4 the pool carries its passes); 'tier3'
    runs the whole finish (the pinned base node's bytes), 'bxf' refuses a finish this worker's table does not cover, before
    any output plane exists."""

    def planes(self, b):
        return {n: np.array(b.ws.get(n)) for n in b.ws.names()}

    @staticmethod
    def numpy_scipy_banded(g1):
        """Every numpy / scipy op banded at any geometry, every torch op whole (the torch ops are G1's to class per runtime;
        numpy and scipy are band-invariant at these sizes on every runtime G1 ran on)."""
        class T(g1.AllBanded):
            def covers(self, op, geom=None):
                return not (op.startswith('torch') or op.startswith('E9') or op.startswith('E4 upsample'))

            def banded(self, *ops, geom=None):
                return bool(ops) and all(self.covers(o) for o in ops)
        return T()

    def test_the_pool_and_the_budget_are_pixel_neutral_and_the_pool_carries_its_passes(self):
        G2 = tool('gate_g2')
        F, E = G2.bxf_module()
        g1 = E('bxf.g1')
        h, w = 300, 290
        pre, cr, st, it, pm, rm = G2.scene(h, w, 2, seed=7)
        size = (2 * w - 3, 2 * h - 5)
        opts = dict(G2.CASES['v4f'])
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            ref = None
            for gb, n in ((2.0, 1), (2.0, 2), (2.0, 4), (3.0, 1), (6.0, 2)):
                got, info, b = G2.bxf_chain(pre, cr, st, it, pm, rm, opts, size, Path(td) / f'{gb}-{n}', self.numpy_scipy_banded(g1), gb,
                                            keep=True, height=288 if gb == 2.0 else None, processes=n)
                try:
                    pl = self.planes(b)
                    pooled = info['record']['pool_passes']
                    if n == 1:
                        self.assertEqual(pooled, [])
                    else:
                        self.assertIn('gmz', pooled)
                        self.assertTrue(any(x.startswith('gg') and x.endswith('.0') for x in pooled), pooled)
                    self.assertEqual(info['record']['processes'], n)
                    self.assertEqual(info['record']['band_gb'], gb)
                    if ref is None:
                        ref = (got, pl)
                        continue
                    self.assertEqual(int(np.count_nonzero(got != ref[0])), 0, (gb, n))
                    self.assertEqual(sorted(pl), sorted(ref[1]), (gb, n))
                    for k, v in pl.items():
                        a, c = ref[1][k], v
                        u = f'u{a.itemsize}' if a.dtype.kind == 'f' else None
                        diff = int(np.count_nonzero(a.view(u) != c.view(u))) if u else int(np.count_nonzero(a != c))
                        self.assertEqual(diff, 0, (gb, n, k))
                finally:
                    b.close()

    def test_tier3_is_the_base_node_and_bxf_refuses_what_its_table_does_not_cover(self):
        from unittest import mock
        from tests.test_bxf_node import base_class
        G2 = tool('gate_g2')
        fake_classic_pack(G2, self)
        pack = G2.load_pack()
        bxf = importlib.import_module(pack.__name__ + '.bxf')
        planes = pack._engine('planes')
        g1 = pack._engine('bxf.g1')
        h, w = 263, 301
        pre, cr, st, it, pm, rm = G2.scene(h, w, 2, seed=5)
        size = (2 * w - 3, 2 * h - 5)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            td = Path(td)
            refs = {}
            for name, arr in (('creative', cr), ('structure', st), ('init', it), ('pre', pre)):
                planes.from_array(td / f'{name}.plane', arr)
                refs[name] = pack.PlaneRef(td / f'{name}.plane', 'r1')
            kw = dict(smooth_lo=0.2, smooth_hi=0.5, protect_dilate=12, protect_feather=4.0, islands=True, chroma_clamp=True,
                      finish='bxf-1', toe_amount=0.40, toe_scale=0.06, output_width=size[0], output_height=size[1],
                      filename_prefix='cu', run_id='r1', quantize_8bit=True, keep_blacks='render', clamp='agree5', lf='hybmin',
                      glow='skygaps', fin_b0_hi=6.0, island_after_lf=True)
            r3 = bxf.CUFinishBanded().run(output_plane=str(td / 'out-tier3.plane'), **refs, **kw, finish_tier='tier3')
            self.assertEqual(r3['ui']['planes'][0]['finish']['tier'], 3)
            base = base_class(pack)
            base().run(output_plane=str(td / 'out-base.plane'), **refs, **kw)
            self.assertEqual(planes.Plane.open(td / 'out-tier3.plane').data_sha256(),
                             planes.Plane.open(td / 'out-base.plane').data_sha256())
            other = g1.Table({'environment': {}, 'ops': {}}, {'torch': 'x'})
            with mock.patch.object(g1, 'load', lambda env=None, local=None: other):
                with self.assertRaises(pack.NotBuilt) as cm:
                    bxf.CUFinishBanded().run(output_plane=str(td / 'out-bxf.plane'), **refs, **kw, finish_tier='bxf')
                self.assertIn('counted only the banded finish', str(cm.exception))
                self.assertFalse((td / 'out-bxf.plane').exists())
                r = bxf.CUFinishBanded().run(output_plane=str(td / 'out-ladder.plane'), **refs, **kw)     # the ladder: tier 3
                self.assertEqual(r['ui']['planes'][0]['finish']['tier'], 3)
            self.assertEqual(planes.Plane.open(td / 'out-ladder.plane').data_sha256(),
                             planes.Plane.open(td / 'out-base.plane').data_sha256())
            with mock.patch.object(g1, 'load', lambda env=None, local=None: self.numpy_scipy_banded(g1)):
                r0 = bxf.CUFinishBanded().run(output_plane=str(td / 'out-bxf0.plane'), **refs, **kw, finish_tier='bxf',
                                              band_gb=3.0, processes=2)
            rec = r0['ui']['planes'][0]['finish']
            self.assertEqual((rec['tier'], rec['band_gb'], rec['processes']), (0, 3.0, 2))
            p0 = planes.Plane.open(td / 'out-bxf0.plane')
            self.assertEqual(p0.header['finish'], rec)
            self.assertEqual(p0.data_sha256(), planes.Plane.open(td / 'out-base.plane').data_sha256())


@unittest.skipUnless(HAVE, 'torch and scipy are not installed here (run on the worker runtime)')
class NarrowStage(unittest.TestCase):
    """bxf-chk-1: on a narrow stage whose last band is small (a 578-row stage at 288-row bands: a 2-row last band), the BXF
    reads the committed G1 table's domain: the s=4 torch conv (lf.dm) runs whole below the width G1 measured it clean at on
    such a band (here 600 and 1,200 px) and banded at 1,500 px, where G1 measured it clean (the routing, asserted anywhere,
    with the table read as if this were its own environment). Where the committed table applies (the libraries and CPU G1
    measured), the stage output and every float plane also equal the classic's own intermediates, plane by plane;
    elsewhere the table certifies nothing, so exactness is not asserted there (G1 on that runtime writes its own table)."""

    def test_the_float_planes_of_narrow_stages_equal_the_classics(self):
        G2 = tool('gate_g2')
        F, E = G2.bxf_module()
        g1, g1t = E('bxf.g1'), E('bxf.g1_table')
        tab = g1.Table(g1t.TABLE, g1t.TABLE['environment'])
        applies = g1.load().applies
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            for h, w, dm in ((289, 300, 'whole'), (289, 600, 'whole'), (289, 750, 'banded')):
                rec = G2.run_case('v4f-protect-release', G2.CASES['v4f-protect-release'], h, w, Path(td) / f'{w}', tab, 2.0,
                                  height=288, phase=applies, branch_rule=False)
                self.assertEqual('lf.dm' in rec['bxf']['whole_passes'], dm == 'whole', (w, rec['bxf']['whole_passes']))
                if applies:
                    self.assertEqual(rec['differing_values'], 0, (w, rec))
                    self.assertTrue(rec['phase_ok'], (w, rec['phase']))
                    for k in G2.PHASE_REQUIRED:
                        self.assertEqual(rec['phase']['planes'][k], 0, (w, k))


@unittest.skipUnless(HAVE, 'torch and scipy are not installed here (run on the worker runtime)')
class PerOpOracle(unittest.TestCase):
    """Each G1 local op: whole on mapped planes equals the classic call on private arrays (0 differing values); banded equals
    whole for every op G1 classes as size-independent (E1 numpy/scipy and the classic functions; torch ops are G1's to class)."""

    def test_every_local_op(self):
        G1 = tool('gate_g1')
        loc = G1.engine('bxf.local')
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            for T, W in ((583, 67), (1159, 41)):
                data = G1.Data(T, W, seed=T)
                mdata = G1.Mapped(data, Path(td) / f'm{T}')
                for p in G1.probes():
                    if p.kind != 'local':
                        continue
                    want = G1._outs(p.fn(*p.inputs(data)))
                    whole = G1._outs(p.fn(*[np.asarray(a) for a in p.inputs(mdata)]))
                    for a, b in zip(want, whole):
                        self.assertEqual(G1.differing(a, b)[0], 0, ('whole-mapped', p.name, T, W))
                    if p.cls == 'E1':
                        got = [np.empty(np.asarray(x).shape, np.asarray(x).dtype) for x in want]
                        loc.run_bands(lambda *a: tuple(G1._outs(p.fn(*a))), p.inputs(mdata), got, 288, p.reach)
                        for a, b in zip(want, got):
                            self.assertEqual(G1.differing(a, b)[0], 0, ('banded', p.name, T, W))
                mdata.close()


if __name__ == '__main__':
    unittest.main()
