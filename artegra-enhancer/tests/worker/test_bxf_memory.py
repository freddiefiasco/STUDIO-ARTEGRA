"""engine/bxf/memory.py on the worker's libraries: its CALLS table is the finish's own (every local call the BXF makes in every
option case, with its bytes per pixel, reach and ops), every table lookup the finish makes is one of memory.lookups() (so
whole_passes_for and the self-probe's plan see what the executor asks: fin-chk-1), and a table with a hole runs whole exactly
the passes whole_passes_for names; finish_commit_gb bounds a fresh-process measurement made here (each finish alone in a fresh
process, tools/gate_g2.py --measure: the peak commit less the process's inputs-only baseline), at tier 3 and at tier 0 with
this environment's table (every op whole when no table applies), on a narrow stage where lf.dm runs whole. Skipped where torch
or scipy is not installed:
    python -B -m unittest tests.worker.test_bxf_memory   (artegra-enhancer folder). Synthetic only."""
import importlib
import importlib.util
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

HAVE = all(importlib.util.find_spec(m) is not None for m in ('torch', 'scipy'))
ROOT = Path(__file__).resolve().parents[2]


def tool(name):
    spec = importlib.util.spec_from_file_location(f'cu_test_mem_{name}', ROOT / 'tools' / f'{name}.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CASES8 = ('v4f', 'lead', 'mm', 'hyb', 'v4f-protect-release', 'no-clamp-glow', 'pre_narrow', 'islands-before-lf')


class Spy:
    """A table that records every lookup (ops, geometry) and answers as `inner` does."""

    applies = True
    mismatch = []

    def __init__(self, inner):
        self.inner, self.seen = inner, []

    def verdict(self, op):
        return self.inner.verdict(op)

    def covers(self, op, geom=None):
        return self.inner.covers(op, geom)

    def banded(self, *ops, geom=None):
        r = self.inner.banded(*ops, geom=geom)
        self.seen.append((tuple(ops), geom, r))
        return r

    def why_not(self):
        return None


@unittest.skipUnless(HAVE, 'torch and scipy are not installed here (run on the worker runtime)')
class ThePassTableIsTheFinishs(unittest.TestCase):
    def test_every_call_its_bytes_per_pixel_reach_and_ops(self):
        G2 = tool('gate_g2')
        F, E = G2.bxf_module()
        loc, M, g1 = E('bxf.local'), E('bxf.memory'), E('bxf.g1')
        seen = {}
        orig = loc.Runner.__call__

        def call(self, name, fn, inputs, outputs, reach, ops, bytes_per_px=64.0, pool_op=None):
            k = M.pass_key(name)
            own = tuple(o for o in ops if o not in F.EW)
            seen.setdefault(k, set()).add((float(bytes_per_px), int(reach), own))
            return orig(self, name, fn, inputs, outputs, reach, ops, bytes_per_px, pool_op)
        loc.Runner.__call__ = call
        try:
            with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
                for c in CASES8:
                    G2.run_case(c, G2.CASES[c], 263, 301, Path(td) / c, g1.AllBanded(), 2.0, height=288)
        finally:
            loc.Runner.__call__ = orig
        self.assertEqual(sorted(seen), sorted(M.CALLS))
        for k, vals in seen.items():                  # a pass with two calls (clamped: lead, mm) lists both
            self.assertEqual(sorted((b, r, tuple(sorted(o))) for b, r, o in vals),        # in any order: lookups are sets
                             sorted((float(b), r, tuple(sorted(o))) for b, r, o in M.CALLS[k]), k)
        for k, vals in seen.items():                  # the one-table form: its largest band, all ops
            bpp, ops = M.PASSES[k]
            self.assertEqual(float(bpp), max(v[0] for v in vals), k)
            self.assertEqual(sorted(ops), sorted(set(o for v in vals for o in v[2])), k)
        self.assertEqual(tuple(F.EW), M.EW)

    def test_every_lookup_is_one_memory_names(self):
        """Every table lookup of every option case (the band executor's, BXF.on's and the stage output's) is in
        memory.lookups() for its plane, on a table that covers everything and on one with holes (where the whole-plane
        fallbacks and the conditional pow lookups run)."""
        G2 = tool('gate_g2')
        F, E = G2.bxf_module()
        M, g1 = E('bxf.memory'), E('bxf.g1')

        class Holes(g1.AllBanded):
            def banded(self, *ops, geom=None):
                return not ({'torch pow 2.4 channels-last', 'torch pow 1/2.4 channels-last', 'E2 tbb r=3',
                             'E6 label out=mapped', 'E5 median', 'E4 zoom order=0 f64 out=mapped', 'shadow_toe_u8'} & set(ops))
        h, w = 263, 301
        W, H = G2.up(w, 2), G2.up(h, 2)
        ow, oh = G2.stage_size(h, w)
        for inner in (g1.AllBanded(), Holes(), g1.AllWhole()):
            for height in (288, None):
                known = {(frozenset(ops), geom) for _, _, ops, geom, _ in M.lookups((W, H), 2.0, height=height, output_rows=oh)}
                with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
                    for c in CASES8:
                        spy = Spy(inner)
                        G2.run_case(c, G2.CASES[c], h, w, Path(td) / c, spy, 2.0, height=height)
                        for ops, geom, _ in spy.seen:
                            self.assertIn((frozenset(ops), geom), known, (type(inner).__name__, height, c, ops, geom))
        self.assertEqual((ow, oh), (W - 3, H - 5))

    def test_a_hole_runs_whole_exactly_the_passes_memory_names(self):
        G2 = tool('gate_g2')
        F, E = G2.bxf_module()
        M, g1 = E('bxf.memory'), E('bxf.g1')
        h, w = 263, 301
        W, H = G2.up(w, 2), G2.up(h, 2)
        ow, oh = G2.stage_size(h, w)
        for hole in ('v4.rgb2lab', 'gaussian_filter s=1.0', 'torch exact ops', 'E2 tbb r=3'):
            class Hole(g1.AllBanded):
                def banded(self, *ops, geom=None, hole=hole):
                    return hole not in ops
            with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
                ran = set()
                for c in CASES8:
                    spy = Spy(Hole())
                    rec = G2.run_case(c, G2.CASES[c], h, w, Path(td) / c, spy, 2.0, height=288)
                    ran |= {M.pass_key(n) for n in rec['bxf']['whole_passes'] if M.pass_key(n) in M.PASSES}
                    ran |= {ops[0] for ops, geom, r in spy.seen if not r and geom.h is None}
                    ran |= {'write_output' for ops, geom, r in spy.seen if not r and ops == M.OUTPUT_OPS}
            want = set(M.whole_passes_for(Hole(), (W, H), 2.0, height=288, output_rows=oh))
            self.assertEqual(sorted(ran), sorted(want), hole)
            self.assertTrue(want, hole)


@unittest.skipUnless(HAVE, 'torch and scipy are not installed here (run on the worker runtime)')
class TheBoundHoldsHere(unittest.TestCase):
    def test_a_fresh_process_measurement_on_a_narrow_stage(self):
        G2, G1 = tool('gate_g2'), tool('gate_g1')
        F, E = G2.bxf_module()
        M, g1 = E('bxf.memory'), E('bxf.g1')
        t = g1.load()                                 # the table the finish itself runs with here (every op whole if none)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            G2.main(['--out', td, '--pre', '600x500', '--cases', 'v4f', '--measure', '--phase', 'none', '--no-branch-rule'])
            rec = [json.loads(x) for x in (Path(td) / 'g2-results.jsonl').read_text(encoding='utf8').splitlines()][-1]
        out, inp = (2 * 600 - 3, 2 * 500 - 5), (600, 500)
        for what, tier in (('classic', 'tier3'), ('bxf', 'bxf')):
            m = rec['measure'][what]
            own = m['peak_commit_gib'] - m['inputs_only']['peak_commit_gib']
            bound = M.finish_commit_gb((2 * 600, 2 * 500), inp, 2.0, 1, tier, table=t if tier == 'bxf' else None,
                                       output_rows=out[1])
            self.assertGreaterEqual(bound, own, (what, m))
        self.assertLess(out[0], M.NARROW_W)


if __name__ == '__main__':
    unittest.main()
