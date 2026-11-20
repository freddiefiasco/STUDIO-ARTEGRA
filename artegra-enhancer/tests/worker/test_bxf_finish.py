"""The banded exact finish (BXF, node_pack/claude_banded/bxf) against 5.0.1's classic chain (ClaudeV4Finish -> ClaudeShadowToe ->
SaveImage, read from node_pack/claude_creative by path), on procedural scenes that exercise every branch (tools/gate_g2.py's
scenes): G2 at a small size with bands of 288 rows (several band joins), every option case, with every op banded and with
every op whole; the node's tier-0 and tier-3 paths through planes; tier 3 byte-equal to today's node; G2r (a fresh process)
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


def fake_classic_pack(G2):
    """A stand-in for the classic pack as ComfyUI loads it (CUFinishBanded finds it by its node classes)."""
    name = 'cu_test_fake_claude_creative'
    if name not in sys.modules:
        m = types.ModuleType(name)
        m.NODE_CLASS_MAPPINGS = {'ClaudeV4Finish': object, 'ClaudeShadowToe': object}
        m.shadow_toe_u8 = G2.classic_function('shadow_toe_u8')
        sys.modules[name] = m
        sys.modules[name + '.v4finish'] = G2.v4()
    return sys.modules[name]


@unittest.skipUnless(HAVE, 'torch and scipy are not installed here (run on the worker runtime)')
class G2Small(unittest.TestCase):
    def test_every_case_banded_and_whole_gives_0_differing_values(self):
        G2 = tool('gate_g2')
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            for table in ('all', 'whole'):
                for name, opts in G2.CASES.items():
                    rec = G2.run_case(name, opts, 263, 301, Path(td) / table, table, 2.0, height=288)
                    self.assertEqual(rec['differing_values'], 0, (table, name, rec))
                    if name == 'v4f' and table == 'all':
                        br = rec['bxf']['branches']
                        for k in ('hw_kept', 'cf_components', 'litter_components', 'agree2_big', 'sky_kept'):
                            self.assertGreater(br.get(k, 0), 0, (k, br))

    def test_the_node_tiers_through_planes_and_tier_3_equals_todays_node(self):
        G2 = tool('gate_g2')
        fake_classic_pack(G2)
        pack = G2.load_pack()
        bxf = importlib.import_module(pack.__name__ + '.bxf')
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
            today = pack.NODE_CLASS_MAPPINGS['CUFinishBanded']().run(output_plane=str(td / 'out-today.plane'), **ins, **kw)
            outs['today'] = planes.validate(today['ui']['planes'][0]['path']).read_rows(0, size[1])
            for k, v in outs.items():
                self.assertEqual(int(np.count_nonzero(v != want)), 0, k)
            self.assertEqual(planes.Plane.open(td / 'out-tier3.plane').data_sha256(),
                             planes.Plane.open(td / 'out-today.plane').data_sha256())
            self.assertFalse(any(p.name.startswith('bxf-work') for p in td.iterdir()))


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
        finally:
            g1.load = orig
        self.assertTrue(asked)
        self.assertEqual(sorted(asked - probes), [])


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
