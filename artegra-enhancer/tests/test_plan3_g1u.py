"""The planner's half of the start-up probe, G1u (engine/banded_plan.py; build wave 3, contracts.g1u). Sizes and synthetic
tables only.

The service (and the tests, and the proof harness) assigns the module attributes banded_plan.BXF_TABLE (what
engine/bxf/g1.load() returns for the ENGINE's environment) and BXF_TABLE_SOURCE ('committed', 'local', 'committed+local');
the planner never does. A set BXF_TABLE always decides the finish tier: 'bxf' when it applies, 'tier3' when it does not. Only
while it is None does BXF_AVAILABLE count (the tests' override: today's banded-finish figures, no table term). With neither,
'tier3' (fail closed). A 'bxf' stage planned with a table counts at least engine/bxf/memory.finish_commit_gb(..., table=) in its
finish phase, never less than wave 2's terms, and records what the table runs whole (bxf_whole_passes) and the bound it counted
(bxf_finish_gb). The plan constant 'bxf_table' (non-pixel) names the table counted. probe_widths names the finish-plane widths
the probe must measure."""
import dataclasses
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from engine import banded_plan as B
from engine import graph_banded, planner
from engine.bxf import g1, g1_table
from engine.bxf import memory as M

ROOT = Path(__file__).resolve().parents[1]
PROVEN = {k: 10_000.0 for k in B.BANDED_PROVEN_MP}
CAPS = {'pc64': 59.0, 'ws128': 122.2, 'pc48': 45.2}
NODE = {'ws128': 1, 'pc64': 2, 'pc48': 2}            # TABLES[1]: this workstation's class; TABLES[2]: the render nodes'
TARGET = [(3500, 2188, 4), (3500, 2188, 6), (3500, 2188, 8), (2800, 3500, 4), (2800, 3500, 6), (2800, 3500, 8),
          (16000, 16000, 2), (1280, 1600, 4), (1280, 1600, 8), (2048, 2048, 2), (4000, 2500, 4), (5333, 3333, 2)]


def node_table(i):
    """A committed table read as the node it was measured on reads it (its own environment; no torch is imported)."""
    t = g1_table.TABLES[i]
    return g1.Table(t, env=dict(t['environment']))


def foreign_table(i):
    """The same table read on another processor: it does not apply."""
    t = g1_table.TABLES[i]
    return g1.Table(t, env=dict(t['environment'], processor='another processor'))


class Holed:
    """A synthetic table that applies and bands every op except those in `hole` (g1's table interface)."""
    applies = True
    mismatch = []

    def __init__(self, hole=()):
        self.hole = set(hole)

    def verdict(self, op):
        return 'whole' if op in self.hole else 'banded'

    def covers(self, op, geom=None):
        return op not in self.hole

    def banded(self, *ops, geom=None):
        return bool(ops) and all(self.covers(o, geom) for o in ops)

    def why_not(self):
        return None


def state(table=None, source=None, available=False):
    return [mock.patch.object(B, 'BXF_TABLE', table), mock.patch.object(B, 'BXF_TABLE_SOURCE', source),
            mock.patch.object(B, 'BXF_AVAILABLE', available)]


class _With:
    def __init__(self, patches):
        self.patches = patches

    def __enter__(self):
        for p in self.patches:
            p.start()

    def __exit__(self, *a):
        for p in reversed(self.patches):
            p.stop()


def using(table=None, source=None, available=False):
    return _With(state(table, source, available) + [mock.patch.dict(B.BANDED_PROVEN_MP, PROVEN)])


def raw_stages(w, h, factor):
    cur, out = (w, h), []
    for i, f in enumerate(planner.STAGE_FACTORS[factor]):
        st = B.stage_choice(cur, f, i)
        out.append(st)
        cur = st['output_size']
    return out


class TheTableDecidesTheTier(unittest.TestCase):
    def test_defaults_are_none_and_fail_closed(self):
        self.assertIsNone(B.BXF_TABLE)
        self.assertIsNone(B.BXF_TABLE_SOURCE)
        self.assertIs(B.BXF_AVAILABLE, False)
        self.assertEqual(B.finish_tier(), 'tier3')
        with using():
            p = B.plan_banded(2800, 3500, 4, 122.2)
        self.assertTrue(p.ok, p.reason)
        self.assertEqual(p.banded['finish_tier'], 'tier3')
        self.assertIsNone(p.banded['bxf_table'])
        for s in p.stages:
            self.assertIsNone(s.bxf_whole_passes)
            self.assertIsNone(s.bxf_finish_gb)

    def test_a_table_that_applies_gives_bxf(self):
        for mc, cap in CAPS.items():
            t = node_table(NODE[mc])
            with using(t, 'committed'):
                self.assertEqual(B.finish_tier(), 'bxf')
                p = B.plan_banded(2800, 3500, 4, cap)
            if p.ok:
                self.assertEqual(p.banded['finish_tier'], 'bxf')
                self.assertEqual(p.banded['bxf_table'], 'committed')

    def test_a_table_that_does_not_apply_gives_tier3_even_with_the_override(self):
        for available in (False, True):
            with using(foreign_table(1), 'committed', available):
                self.assertEqual(B.finish_tier(), 'tier3')
                p = B.plan_banded(2800, 3500, 4, 122.2)
            self.assertTrue(p.ok, p.reason)
            self.assertEqual(p.banded['finish_tier'], 'tier3')
            self.assertIsNone(p.banded['bxf_table'])

    def test_the_override_counts_only_while_no_table_is_set(self):
        with using(None, None, True):
            self.assertEqual(B.finish_tier(), 'bxf')
            p = B.plan_banded(2800, 3500, 4, 122.2)
        self.assertEqual(p.banded['bxf_table'], 'override')
        for s in p.stages:
            self.assertEqual(s.bxf_whole_passes, [])
            self.assertIsNone(s.bxf_finish_gb)                 # no table term: today's banded-finish figures

    def test_with_both_set_the_table_decides_so_the_proof_harness_plans_as_the_service(self):
        for mc, cap in CAPS.items():
            t = node_table(NODE[mc])
            for w, h, f in TARGET:
                with using(t, 'committed', True):
                    a = B.plan_banded(w, h, f, cap)
                with using(t, 'committed', False):
                    b = B.plan_banded(w, h, f, cap)
                self.assertEqual(a.to_dict(), b.to_dict(), (w, h, f, mc))
                if a.ok:
                    self.assertEqual(a.banded['bxf_table'], 'committed')
                    for s in a.stages:
                        band = B.MACHINE_CLASSES[mc]['band_gb']
                        self.assertEqual(s.bxf_whole_passes, M.whole_passes_for(t, B.finish_size(s), band,
                                                                                output_rows=s.output_size[1]))

    def test_the_tier_is_read_once_per_plan(self):
        """A plan made while the service reassigns the table counts one table throughout (a snapshot)."""
        t = node_table(1)
        calls = []
        real = M.finish_commit_gb

        def swap(*a, **k):
            calls.append(k.get('table'))
            B.BXF_TABLE = foreign_table(1)                    # the service assigns a new table mid-plan
            return real(*a, **k)
        with using(t, 'committed'), mock.patch.object(M, 'finish_commit_gb', swap):
            p = B.plan_banded(3500, 2188, 4, 122.2)
        self.assertTrue(p.ok, p.reason)
        self.assertEqual({s.finish_tier for s in p.stages}, {'bxf'})
        self.assertTrue(calls and all(c is t for c in calls))


class TheFinishBoundIsCounted(unittest.TestCase):
    def test_finish_commit_gb_with_the_table_is_counted_and_never_below_wave_2(self):
        for mc, cap in CAPS.items():
            t = node_table(NODE[mc])
            mcd = B.MACHINE_CLASSES[mc]
            for w, h, f in TARGET:
                with using(t, 'committed'):
                    p = B.plan_banded(w, h, f, cap)
                with using(None, None, True):
                    o = B.plan_banded(w, h, f, cap)
                for k, st in enumerate(raw_stages(w, h, f)):
                    want = M.finish_commit_gb(B.finish_size(st), st['padded_size'], mcd['band_gb'], mcd['processes'], 'bxf',
                                              table=t, output_rows=st['output_size'][1])
                    for split in (False, True):
                        d = dict(st, finish_tier='bxf', bxf_finish_gb=want)
                        up = B.stage_peaks(d, mc, split)['phases_up']['finish']
                        x_up = B.X0 + B.XR_UP * B._mp(st['render_size']) + B.XRES
                        v_fin = B.CTX_GB if split else max(B.V0 + B.V_R * B._mp(st['render_size']),
                                                          B.VS0 + B.VS_BPR * B.G * B._mp(st['render_size']))
                        self.assertGreaterEqual(up + 1e-9, v_fin + x_up + want + B.service_gb(st), (w, h, f, mc, k))
                        wave2 = B.stage_peaks(dict(st, finish_tier='bxf'), mc, split)['phases_up']['finish']
                        self.assertGreaterEqual(up + 1e-9, wave2, (w, h, f, mc, k))
                    if p.ok:
                        self.assertAlmostEqual(p.stages[k].bxf_finish_gb, want, places=9)
                    if o.ok:
                        self.assertIsNone(o.stages[k].bxf_finish_gb)

    def test_a_table_with_a_hole_runs_those_passes_whole_and_counts_more(self):
        hole = ('gaussian_filter s=16.0', 'E5 median', 'torch pow 2.4 channels-last')
        full, holed = Holed(), Holed(hole)
        for mc, cap in (('ws128', 122.2), ('pc64', 59.0)):
            band = B.MACHINE_CLASSES[mc]['band_gb']
            with using(full, 'local'):
                a = B.plan_banded(3500, 2188, 4, cap)
            with using(holed, 'committed+local'):
                b = B.plan_banded(3500, 2188, 4, cap)
            self.assertTrue(a.ok and b.ok, (a.reason, b.reason))
            self.assertEqual(b.banded['bxf_table'], 'committed+local')
            for sa, sb in zip(a.stages, b.stages):
                want = M.whole_passes_for(holed, B.finish_size(sb), band, output_rows=sb.output_size[1])
                self.assertEqual(sb.bxf_whole_passes, want)
                self.assertIn('hw.rel', want)                     # its gaussian s=16.0
                self.assertIn('E5 median', want)
                self.assertIn('lf.powx', want)
                self.assertEqual(sa.bxf_whole_passes, [])
                self.assertGreater(sb.bxf_finish_gb, sa.bxf_finish_gb)
                # at the same split and the same engine start (both follow the bound: a holed finish's retention is not
                # measured, so the stage after it starts in a fresh engine)
                same = dict(dataclasses.asdict(sb), fresh_worker=sa.fresh_worker, carry_gb=sa.carry_gb,
                            warm_engine=sa.warm_engine)
                for split in (False, True):
                    self.assertGreater(B.stage_peaks(same, mc, split)['phases_up']['finish'],
                                       B.stage_peaks(sa, mc, split)['phases_up']['finish'])
                    self.assertGreaterEqual(B.stage_peaks(same, mc, split)['up'][0], B.stage_peaks(sa, mc, split)['up'][0])

    def test_a_stored_stage_gives_its_own_figures_whatever_the_table_now(self):
        t = node_table(1)
        with using(t, 'committed'):
            p = B.plan_banded(3500, 2188, 4, 122.2)
        d = p.to_dict()
        for s, sd in zip(p.stages, d['stages']):
            for now in (None, foreign_table(1), Holed(('E5 median',))):
                with using(now, 'committed'):
                    self.assertEqual(round(B.stage_peaks(s, 'ws128', s.split_finish)['up'][0], 1), s.peak_upper_gb)
                    self.assertEqual(round(B.stage_peaks(sd, 'ws128', sd['split_finish'])['up'][0], 1), s.peak_upper_gb)

    def test_the_stage_dict_carries_the_table_record(self):
        t = node_table(2)
        with using(t, 'committed'):
            p = B.plan_banded(3500, 2188, 4, 59.0)
        self.assertTrue(p.ok, p.reason)
        d = p.to_dict()
        self.assertEqual(json.loads(json.dumps(d)), d)
        self.assertEqual(d['banded']['bxf_table'], 'committed')
        for s in d['stages']:
            self.assertIsInstance(s['bxf_whole_passes'], list)
            self.assertEqual(s['bxf_whole_passes'], sorted(s['bxf_whole_passes']))
            self.assertIsInstance(s['bxf_finish_gb'], float)
        with using():
            q = B.plan_banded(3500, 2188, 4, 122.2)
        for s in q.to_dict()['stages']:                        # tier 3: None (the service reads None as absent)
            self.assertIsNone(s['bxf_whole_passes'])
            self.assertIsNone(s['bxf_finish_gb'])


class TheTier3Refusal(unittest.TestCase):
    def test_above_the_whole_finish_limit_it_says_the_processor_is_not_measured(self):
        for table in (None, foreign_table(1)):
            with using(table, 'committed' if table else None):
                p = B.plan_banded(3500, 2188, 8, 122.2)
            self.assertFalse(p.ok)
            self.assertIn('28,000 × 17,504 px', p.reason)
            self.assertIn("this computer's processor has not been measured for the Large-image engine yet", p.reason)
            self.assertIn('300 MP', p.reason)
            self.assertIn('Large-image engine', p.reason)


class ProbeWidths(unittest.TestCase):
    def expected(self, w, h, f, cap):
        """The widths of the plan planner.plan routes to with the best table a probe can write (a synthetic table that
        applies and bands every op, this file's own Holed(), not the planner's stand-in): [] where it is not banded or
        refused (plan-chk3-1: the override counted no finish bound, so it named widths no table could admit)."""
        with using(Holed(), 'local'):
            p = planner.plan(w, h, f, ram_cap_gb=cap)
        if p.ok and p.engine == 'banded':
            return sorted({B.finish_size(s)[0] for s in p.stages})
        return []

    def test_the_finish_widths_of_the_bxf_plan_over_the_target_grid(self):
        n = 0
        for mc, cap in CAPS.items():
            for w, h, f in TARGET:
                want = self.expected(w, h, f, cap)
                n += bool(want)
                for table, src, avail in ((None, None, False), (foreign_table(1), 'committed', False),
                                          (node_table(NODE[mc]), 'committed', True), (None, None, True)):
                    with _With(state(table, src, avail)):
                        got = B.probe_widths(w, h, f, cap, proven=PROVEN)
                    self.assertEqual(got, want, (w, h, f, mc))
                    self.assertTrue(all(isinstance(x, int) for x in got))
        self.assertGreater(n, 10)

    def test_none_where_no_large_image_plan_exists(self):
        self.assertEqual(B.probe_widths(3500, 2188, 8, 59.0), [])           # nothing proven in this build
        for w, h, f, cap in ((2048, 2048, 2, 59.0),                        # 5.0.1 runs it: the classic engine's
                             (9000, 9000, 8, 122.2),                       # over 32,000 px
                             (3500, 2188, 4, 30.0),                        # no machine class
                             (64, 8000, 2, 122.2)):                        # too tall
            self.assertEqual(B.probe_widths(w, h, f, cap, proven=PROVEN), [], (w, h, f, cap))
        self.assertEqual(B.probe_widths(3500, 2188, 2, 59.0, mode='fast', proven=PROVEN), [])   # banded Bolt not proven

    def test_none_where_no_table_can_admit_the_image(self):
        """plan-chk3-1's rows: the best table's plan (the finish's own construction bound counted) is refused, so no probe
        can lift the refusal and none is asked for; the override plans them, and every node table refuses them too."""
        for w, h, f, cap in ((3500, 2188, 6, 59.0), (2800, 3500, 6, 59.0), (4000, 4000, 8, 122.2), (5333, 3333, 6, 122.2)):
            self.assertEqual(B.probe_widths(w, h, f, cap, proven=PROVEN), [], (w, h, f, cap))
            with using(Holed(), 'local'):
                self.assertFalse(B.plan_banded(w, h, f, cap).ok, (w, h, f, cap))
            for i in (1, 2):
                with using(node_table(i), 'committed'):
                    self.assertFalse(B.plan_banded(w, h, f, cap).ok, (w, h, f, cap, i))
            with using(None, None, True):
                self.assertTrue(B.plan_banded(w, h, f, cap).ok, (w, h, f, cap))     # the override admits it

    def test_widths_where_a_table_could_admit_the_image(self):
        """Rows the best table admits keep their widths, the node table of this class refusing them or not (another
        processor's probe may write a table that admits them)."""
        for (w, h, f, cap), want in (((3500, 2188, 6, 122.2), [7000, 14000, 21000]),
                                     ((2800, 3500, 8, 122.2), [5600, 11200, 22400]),
                                     ((4000, 2500, 8, 122.2), [8000, 16000, 32000]),
                                     ((3500, 2188, 4, 59.0), [7000, 14000]),
                                     ((2800, 3500, 6, 122.2), [5600, 11200, 16800])):
            self.assertEqual(B.probe_widths(w, h, f, cap, proven=PROVEN), want, (w, h, f, cap))

    def test_never_none_where_a_table_admits_the_image(self):
        """Over a grid of sizes, factors and caps: wherever a node table or a holed table plans the image on the
        Large-image engine, probe_widths names exactly that plan's finish widths (so the probe is asked for every refusal a
        table could lift), and the stand-in's finish bound is at most each table's at every stage."""
        tables = [(node_table(1), 'committed'), (node_table(2), 'committed'), (Holed(('E5 median',)), 'local'),
                  (Holed(('gaussian_filter s=16.0', 'torch pow 2.4 channels-last')), 'local')]
        sides = (1024, 1600, 2188, 2800, 3500, 4000, 5333)
        n = admitted = 0
        for w in sides:
            for h in sides:
                for f in (2, 4, 6, 8):
                    for cap in CAPS.values():
                        got = B.probe_widths(w, h, f, cap, proven=PROVEN)
                        n += 1
                        for table, src in tables:
                            with using(table, src):
                                p = planner.plan(w, h, f, ram_cap_gb=cap)
                            if not (p.ok and p.engine == 'banded'):
                                continue
                            admitted += 1
                            self.assertEqual(got, B.plan_finish_widths(p), (w, h, f, cap, src))
                            mc = B.machine_class(cap)
                            for s in p.stages:
                                best = B.finish_bound(dataclasses.asdict(s), mc, B.PROBE_TABLE)[1]
                                self.assertLessEqual(best, s.bxf_finish_gb + 1e-9, (w, h, f, cap, s.index))
        self.assertGreater(admitted, 100)
        self.assertGreater(n, 500)

    def test_the_stand_in_is_the_best_case_table(self):
        t = B.PROBE_TABLE
        self.assertIs(t.applies, True)
        self.assertIsNone(t.why_not())
        geom = g1.Geometry(1152, 32000, 64, 2)
        self.assertTrue(t.banded('v4.chroma_hc2 warm', *M.EW, geom=geom))
        self.assertTrue(t.covers('E5 median', geom))
        self.assertFalse(t.banded(geom=geom))                                 # no op: nothing to band (as g1's tables)
        for fs, rows in (((14000, 8752), 8752), ((32000, 20000), 20000), ((4000, 30000), 30000)):
            self.assertEqual(M.whole_passes_for(t, fs, 3.0, output_rows=rows), [])
            for band, procs in ((2.0, 1), (3.0, 2), (6.0, 4)):
                self.assertAlmostEqual(M.finish_commit_gb(fs, (fs[0] // 2, fs[1] // 2), band, procs, 'bxf', table=t),
                                       M.finish_commit_gb(fs, (fs[0] // 2, fs[1] // 2), band, procs, 'bxf'), places=12)

    def test_the_service_modes(self):
        a = B.probe_widths(2800, 3500, 6, 122.2, proven=PROVEN)               # 16,800 px: 5.0.1 refuses it
        self.assertTrue(a)
        self.assertEqual(B.probe_widths(2800, 3500, 6, 122.2, mode='standard', proven=PROVEN), a)
        self.assertEqual(B.probe_widths(2800, 3500, 6, 122.2, mode='redux', proven=PROVEN), a)
        self.assertEqual(a, sorted(set(a)))
        self.assertEqual(B.probe_widths(3500, 2188, 4, 122.2, proven=PROVEN), [])  # the classic engine runs it there

    def test_the_widths_of_any_plan(self):
        with using(node_table(1), 'committed'):
            p = B.plan_banded(3500, 2188, 4, 122.2)
        self.assertEqual(B.plan_finish_widths(p), [7000, 14000])
        self.assertEqual(B.plan_finish_widths(p.to_dict()), [7000, 14000])
        self.assertEqual(B.plan_finish_widths(planner.plan(2048, 2048, 2, ram_cap_gb=59.0)), [])


class TheTableConstantIsNotAPixelConstant(unittest.TestCase):
    def test_non_pixel_and_not_a_finish_input(self):
        self.assertIn('bxf_table', B.NON_PIXEL_CONSTANTS)
        self.assertNotIn('bxf_table', B.FINISH_CONSTANTS)
        self.assertEqual(B.FINISH_CONSTANTS, ('bxf_band_gb', 'bxf_processes', 'finish_tier'))
        self.assertNotIn('bxf_table', B.constants())
        for k in B.FINISH_CONSTANTS:
            self.assertIn(k, B.NON_PIXEL_CONSTANTS)

    def test_the_graph_and_the_resume_match_ignore_it(self):
        from service import util
        with using(node_table(1), 'committed'):
            a = B.plan_banded(3500, 2188, 4, 122.2)
        with using(node_table(1), 'local'):
            b = B.plan_banded(3500, 2188, 4, 122.2)
        self.assertNotEqual(a.banded['bxf_table'], b.banded['bxf_table'])
        self.assertTrue(util.same_plan(a.to_dict(), b.to_dict()))
        from engine import controls
        params = controls.stage_params(controls.resolve({})[0], 0)
        st = a.stages[0]
        ga = graph_banded.build_stage('in.plane', *st.padded_size, params, 'p', 'd', 'r', f=st.factor, s=st.supersample,
                                      constants=a.banded, output_size=st.output_size)
        gb = graph_banded.build_stage('in.plane', *st.padded_size, params, 'p', 'd', 'r', f=st.factor, s=st.supersample,
                                      constants=b.banded, output_size=st.output_size)
        self.assertEqual(ga, gb)

    def test_the_sub_stage_checkpoint_ignores_every_non_pixel_constant(self):
        """The service's deny-list (service/banded_runner.CHECKPOINT_IGNORED_CONSTANTS) takes 'bxf_table' in the service
        package of this wave (contracts.g1u): red on this branch until that merge (adds.expected_red)."""
        from service import banded_runner
        self.assertLessEqual(set(B.NON_PIXEL_CONSTANTS), set(banded_runner.CHECKPOINT_IGNORED_CONSTANTS))


NO_TORCH = r'''
import sys
class NoTorch:
    def find_spec(self, name, path=None, target=None):
        if name == 'torch' or name.startswith('torch.'):
            raise ImportError('the planner must not import torch')
        return None
sys.meta_path.insert(0, NoTorch())
from engine import banded_plan as B, planner
from engine.bxf import g1, g1_table
t = g1_table.TABLES[1]
B.BXF_TABLE, B.BXF_TABLE_SOURCE = g1.Table(t, env=dict(t['environment'])), 'committed'
proven = {k: 10000.0 for k in B.BANDED_PROVEN_MP}
n = 0
for w, h, f in ((3500, 2188, 4), (3500, 2188, 8), (2800, 3500, 8), (16000, 16000, 2), (1280, 1600, 4)):
    for cap in (45.2, 59.0, 122.2):
        p = B.plan_banded(w, h, f, cap, proven=proven)
        n += p.ok
        B.probe_widths(w, h, f, cap, proven=proven)
        planner.plan(w, h, f, ram_cap_gb=cap)
assert n > 0, n
assert not [m for m in sys.modules if m == 'torch' or m.startswith('torch.')]
print('ok', n)
'''


class NoTorch(unittest.TestCase):
    def test_the_planner_imports_no_torch(self):
        r = subprocess.run([sys.executable, '-B', '-c', NO_TORCH], cwd=str(ROOT), capture_output=True, text=True,
                           env=dict(os.environ, PYTHONPATH=str(ROOT)), timeout=300)
        self.assertEqual(r.returncode, 0, r.stderr[-3000:])
        self.assertTrue(r.stdout.startswith('ok'), r.stdout)


if __name__ == '__main__':
    unittest.main()
