"""fin-chk-1: the start-up self-probe (engine/bxf/selfprobe.py, G1u) measures exactly the shapes the finish will look up, and
the planner counts whatever a table leaves whole (engine/bxf/memory.whole_passes_for and finish_commit_gb(table=...)). A table
made of the probe's planned shapes, all clean, covers every pass, whole-plane op and the stage output of every registered
target's stage at its widths and band budgets; a stage width or budget it was not asked about reads whole and is counted; the
check's case (a cap hole at 2,304 rows for the colour conversions every pass names, and a stage narrower than 8,192 px) runs
those passes whole and the bound counts them. Sizes and synthetic tables only; numpy only (no probe runs here)."""
import importlib
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GIB = 2 ** 30


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
    spec = importlib.util.spec_from_file_location('cu_test_probe_plan_gate_g1', ROOT / 'tools' / 'gate_g1.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ENV = {'torch': 't', 'numpy': 'n', 'scipy': 's', 'cpu_capability': 'c', 'numpy_simd': ['X'], 'processor': 'p'}


def probe_ops():
    """{name: (kind, reach)} of the probe's ops: G1's probes but the pool (the committed table records each one's kind and
    reach; tests/worker/test_bxf_selfprobe.py checks the probe's own definitions are G1's)."""
    t = engine('bxf.g1_table').TABLES[0]
    return {n: (o['kind'], int(o.get('reach', 0))) for n, o in t['ops'].items() if o.get('cls') != 'pool'}


def table_of(planned, ops, drop=None):
    """The local table the probe writes when every planned shape is clean (its points as selfprobe.probe records them).
    drop(name, W, h): leave that op's shape out (a hole)."""
    g1, sp = engine('bxf.g1'), engine('bxf.selfprobe')
    clean = {}
    for (W, h), names in planned.items():
        for name in names:
            if drop is not None and drop(name, W, h):
                continue
            kind, reach = ops[name]
            for r in sp.RESTS:
                geom = g1.Geometry(h + r, W, h, reach) if kind == 'local' else g1.Geometry(h + r, W)
                key, pt = g1.point(geom)
                if pt is not None:
                    clean.setdefault(name, {}).setdefault(key, []).append(list(pt))
    out = {}
    for name, (kind, _) in ops.items():
        c = clean.get(name)
        out[name] = {'verdict': 'banded', 'domain': {'key': 'height' if kind == 'local' else 'any',
                                                     'w_max': {k: max(p[0] for p in v) for k, v in c.items()},
                                                     'frontier': {k: sp.pareto(v) for k, v in c.items()}}} if c else \
            {'verdict': 'whole'}
    return g1.Table({'environment': ENV, 'ops': out}, ENV)


class TheProbesPlan(unittest.TestCase):
    def test_a_table_of_its_shapes_covers_every_lookup_of_every_target_stage(self):
        M, sp, G1 = engine('bxf.memory'), engine('bxf.selfprobe'), gate_g1()
        ops = probe_ops()
        looked = {o for _, _, names, _, _ in M.lookups((14000, 8752), 2.0) for o in names}
        self.assertLessEqual(looked, set(ops))                    # the probe knows every op the finish looks up
        widths = sorted({W for W, _ in G1.TARGET_PLANES})
        for b in (2.0, 3.0, 6.0):
            t = table_of(sp.plan(ops, widths, [b]), ops)
            for W, H in G1.TARGET_PLANES:
                self.assertEqual(M.whole_passes_for(t, (W, H), b), [], (W, H, b))
                self.assertEqual(M.whole_passes_for(t, (W, H), b, output_rows=H - 5), [], (W, H, b))
        t = table_of(sp.plan(ops, [7000, 14000]), ops)            # every registered budget by default
        for b in (2.0, 3.0, 6.0):
            for W, H in ((7000, 4376), (14000, 8752), (8192, 9000)):
                self.assertEqual(M.whole_passes_for(t, (W, H), b), [], (W, H, b))

    def test_a_width_or_budget_it_was_not_asked_about_reads_whole_and_is_counted(self):
        M, sp = engine('bxf.memory'), engine('bxf.selfprobe')
        ops = probe_ops()
        t = table_of(sp.plan(ops, [14000], [2.0]), ops)
        narrow = M.whole_passes_for(t, (7000, 4376), 2.0)          # narrower than every probed width: nothing is covered
        self.assertTrue(set(M.PASSES) <= set(narrow))
        self.assertIn('write_output', narrow)
        self.assertTrue(set(M.WHOLE_CALLS) <= set(narrow))
        self.assertGreater(len(M.whole_passes_for(t, (14000, 8752), 6.0)), 0)   # a budget it did not probe picks other heights
        self.assertEqual(M.whole_passes_for(t, (14000, 8752), 2.0), [])
        b = M.finish_commit_gb((7000, 4376), (3500, 2188), 2.0, 1, 'bxf', table=t)
        self.assertAlmostEqual(b - M.finish_commit_gb((7000, 4376), (3500, 2188), 2.0, 1, 'bxf'), 340 * 7000 * 4376 / GIB)

    def test_each_local_op_runs_only_at_a_height_a_call_picks(self):
        """Memory follows the executor: a looked-up local op is probed at the heights its own calls pick at that width and
        budget (EW ops: every call's), the output's ops at its 1,152-row bands, everything else at the smallest height."""
        M, sp, bands = engine('bxf.memory'), engine('bxf.selfprobe'), engine('bands')
        ops = probe_ops()
        for W in (128, 5600, 14000, 32000):
            for b in (2.0, 6.0):
                planned = sp.plan(ops, [W], [b])
                self.assertEqual(sorted({w for w, _ in planned}), sorted({W, 8192}))
                for (w, h), names in planned.items():
                    picked = {}
                    for _, kind, looked, geom, _ in M.lookups((w, 10 ** 6), b):
                        for n in looked:
                            picked.setdefault(n, set()).add(min(bands.BAND_HEIGHTS) if kind == 'plane' else geom.h)
                    for n in names:
                        self.assertIn(h, picked.get(n, {min(bands.BAND_HEIGHTS)}), (n, w, h, b))
        self.assertEqual(sorted(sp.plan(ops, [300], heights=(288, 576))), [(300, 288), (300, 576), (8192, 288), (8192, 576)])
        self.assertEqual(sp.widths_of(300), [300, 8192])
        self.assertEqual(sp.budgets_of(None), [2.0, 3.0, 6.0])
        with self.assertRaises((AssertionError, ValueError)):
            sp.budgets_of([4.0])


class TheChecksCase(unittest.TestCase):
    """fin-chk-1's evidence: the first G1u table skipped v4.rgb2lab and v4.lab2rgb at 2,304 rows at the plan width (a per-op cap)
    and probed no width below 8,192 px. Those holes run passes whole; the bound counts them, where the classed-whole ops alone
    (the adds' first instruction) did not."""

    def holed(self):
        sp = engine('bxf.selfprobe')
        ops = probe_ops()
        hole = {'v4.rgb2lab', 'v4.lab2rgb'}
        return table_of(sp.plan(ops, [14000], [2.0]), ops, drop=lambda n, W, h: n in hole and W == 14000 and h == 2304)

    def test_the_passes_a_hole_reaches_run_whole_and_are_counted(self):
        M, loc = engine('bxf.memory'), engine('bxf.local')
        t = self.holed()
        got = M.whole_passes_for(t, (14000, 8752), 2.0)
        run = loc.Runner(t, 2.0)
        want = sorted({k for k, calls in M.CALLS.items() for bpp, reach, own in calls
                       if run.would_band(tuple(own) + M.EW, 8752, 14000, reach, bpp)[0] == 'whole'})
        self.assertEqual(got, want)
        self.assertGreater(len(got), 2)
        classed_whole = [n for n in probe_ops() if t.verdict(n) != 'banded']
        self.assertEqual(classed_whole, [])                       # the table classes no op whole: the verdicts alone say nothing
        old = M.finish_commit_gb((14000, 8752), (7000, 4376), 2.0, 1, 'bxf', classed_whole)
        new = M.finish_commit_gb((14000, 8752), (7000, 4376), 2.0, 1, 'bxf', table=t)
        top = max(M.whole_bytes_per_px(n) for n in got)
        self.assertAlmostEqual(new - old, top * 14000 * 8752 / GIB)
        self.assertGreater(new, old + 1.0)

    def test_the_runners_decision_is_the_bounds(self):
        M, loc, g1 = engine('bxf.memory'), engine('bxf.local'), engine('bxf.g1')
        t = self.holed()
        for W, H in ((14000, 8752), (14000, 300), (9000, 7000), (20000, 9000), (8192, 2305)):
            for b in (2.0, 3.0, 6.0):
                for height in (None, 288, 2304):
                    run = loc.Runner(t, b, height=height)
                    want = {k for k, calls in M.CALLS.items() for bpp, reach, own in calls
                            if run.would_band(tuple(own) + M.EW, H, W, reach, bpp)[0] == 'whole'}
                    want |= {op for op in M.WHOLE_CALLS if not t.banded(op, geom=g1.Geometry(H, W))}
                    if not t.banded(*M.OUTPUT_OPS, geom=g1.Geometry(H, W, M.OUTPUT_HEIGHT, 0)):
                        want.add('write_output')
                    self.assertEqual(M.whole_passes_for(t, (W, H), b, height=height), sorted(want), (W, H, b, height))


if __name__ == '__main__':
    unittest.main()
