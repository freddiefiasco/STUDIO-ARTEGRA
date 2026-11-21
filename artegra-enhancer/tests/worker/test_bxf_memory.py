"""engine/bxf/memory.py on the worker's libraries: its PASSES table is the finish's own (every local pass the BXF makes in every
option case, with its bytes per pixel and ops), and finish_commit_gb bounds a fresh-process measurement made here (each
finish alone in a fresh process, tools/gate_g2.py --measure: the peak commit less the process's inputs-only baseline), at
tier 3 and at tier 0 with the ops this environment's table runs whole (every op when no table applies), on a narrow stage
where lf.dm runs whole. Skipped where torch or scipy is not installed:
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


@unittest.skipUnless(HAVE, 'torch and scipy are not installed here (run on the worker runtime)')
class ThePassTableIsTheFinishs(unittest.TestCase):
    def test_every_pass_its_bytes_per_pixel_and_ops(self):
        G2 = tool('gate_g2')
        F, E = G2.bxf_module()
        loc, M, g1 = E('bxf.local'), E('bxf.memory'), E('bxf.g1')
        seen = {}
        orig = loc.Runner.__call__

        def call(self, name, fn, inputs, outputs, reach, ops, bytes_per_px=64.0, pool_op=None):
            k = M.pass_key(name)
            own = tuple(sorted(o for o in ops if o not in F.EW))
            seen.setdefault(k, set()).add((float(bytes_per_px), own))
            self_ = orig(self, name, fn, inputs, outputs, reach, ops, bytes_per_px, pool_op)
            return self_
        loc.Runner.__call__ = call
        try:
            with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
                for c in ('v4f', 'lead', 'mm', 'hyb', 'v4f-protect-release', 'no-clamp-glow', 'pre_narrow', 'islands-before-lf'):
                    G2.run_case(c, G2.CASES[c], 263, 301, Path(td) / c, g1.AllBanded(), 2.0, height=288)
        finally:
            loc.Runner.__call__ = orig
        self.assertEqual(sorted(seen), sorted(M.PASSES))
        for k, vals in seen.items():                  # a pass in several variants (clamped: lead, mm): its largest band, all ops
            bpp, ops = M.PASSES[k]
            self.assertEqual(float(bpp), max(v[0] for v in vals), k)
            self.assertEqual(sorted(ops), sorted(set(o for v in vals for o in v[1])), k)
        self.assertEqual(tuple(F.EW), M.EW)


@unittest.skipUnless(HAVE, 'torch and scipy are not installed here (run on the worker runtime)')
class TheBoundHoldsHere(unittest.TestCase):
    def test_a_fresh_process_measurement_on_a_narrow_stage(self):
        G2, G1 = tool('gate_g2'), tool('gate_g1')
        F, E = G2.bxf_module()
        M, g1 = E('bxf.memory'), E('bxf.g1')
        t = g1.load()
        names = [p.name for p in G1.probes()]
        whole = list(M.EW) if not t.applies else [n for n in names if t.verdict(n) != 'banded']
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            G2.main(['--out', td, '--pre', '600x500', '--cases', 'v4f', '--measure', '--phase', 'none', '--no-branch-rule'])
            rec = [json.loads(x) for x in (Path(td) / 'g2-results.jsonl').read_text(encoding='utf8').splitlines()][-1]
        out, inp = (2 * 600 - 3, 2 * 500 - 5), (600, 500)
        for what, tier in (('classic', 'tier3'), ('bxf', 'bxf')):
            m = rec['measure'][what]
            own = m['peak_commit_gib'] - m['inputs_only']['peak_commit_gib']
            bound = M.finish_commit_gb((2 * 600, 2 * 500), inp, 2.0, 1, tier, whole if tier == 'bxf' else ())
            self.assertGreaterEqual(bound, own, (what, m))
        self.assertLess(out[0], M.NARROW_W)


if __name__ == '__main__':
    unittest.main()
