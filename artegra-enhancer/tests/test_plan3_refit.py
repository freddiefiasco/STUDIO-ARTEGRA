"""The refit of the Large-image planner to upper bounds of what is measured (engine/banded_plan.py, engine/planes.py; build
wave 3, contracts.conservative_bounds and contracts.restart). Sizes and figures only:
(a) tier 3 counts the largest of T3, the finish package's bound (memory.finish_commit_gb tier 3) and 5.0.1's model;
(b) every phase that runs in a stage's first engine counts its nodes' retained commit (phase-aware) and CUCannyPlane's
    CPU-device figures;
(c) every stage after the first counts what the previous finish left in its engine, where that is measured for every
    setting the finish may run with (plan-chk3-2: none in 5.0.2) and fits, or starts in a fresh engine (fresh_worker, with
    SPLIT_MINUTES): never neither;
(d) the disk figure covers the stage folder at the finish, with the measured BXF scratch;
(e) LFDM_NARROW_PX comes from the worker runtime's tables;
(f) admission compares 1.05 x the unrounded upper bound (plan-chk-1);
and terms='wave2' gives wave 2's figures exactly (tests/fixtures/plan3_wave2_stage_figures.json, taken at the base)."""
import dataclasses
import json
import unittest
from pathlib import Path
from unittest import mock

from engine import banded_plan as B
from engine import planes, planner
from engine.bxf import g1, g1_table
from engine.bxf import memory as M

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / 'tests' / 'fixtures'
MEAS = json.loads((FIX / 'plan3_measurements.json').read_text(encoding='utf8'))
WAVE2 = json.loads((FIX / 'plan3_wave2_stage_figures.json').read_text(encoding='utf8'))
PROVEN = {k: 10_000.0 for k in B.BANDED_PROVEN_MP}
CAPS = {'pc64': 59.0, 'ws128': 122.2, 'pc48': 45.2}
NODE = {'ws128': 1, 'pc64': 2, 'pc48': 2}
ROWS = [(3500, 2188, 4), (3500, 2188, 6), (3500, 2188, 8), (2800, 3500, 4), (2800, 3500, 6), (2800, 3500, 8),
        (4000, 2500, 8), (4000, 4000, 8), (5333, 3333, 6), (1280, 1600, 4), (2048, 2048, 2), (64, 3000, 2), (560, 3457, 2),
        (1280, 1600, 8), (2188, 3500, 6), (8000, 3000, 2)]
GIB = float(2 ** 30)


def node_table(i):
    t = g1_table.TABLES[i]
    return g1.Table(t, env=dict(t['environment']))


def raw_stages(w, h, factor):
    cur, out = (w, h), []
    for i, f in enumerate(planner.STAGE_FACTORS[factor]):
        st = B.stage_choice(cur, f, i)
        out.append(st)
        cur = st['output_size']
    return out


def mp(size):
    return size[0] * size[1] / 1e6


def plans(tables=True, kinds=None):
    """Every row's plan on every machine class, with the node's committed table and with the override (kinds: those, or
    'tier3' too, the fail-closed default)."""
    for mc, cap in CAPS.items():
        for w, h, f in ROWS:
            for kind in kinds or (('table', 'override') if tables else ('override',)):
                patches = [mock.patch.dict(B.BANDED_PROVEN_MP, PROVEN)]
                if kind == 'table':
                    patches += [mock.patch.object(B, 'BXF_TABLE', node_table(NODE[mc])),
                                mock.patch.object(B, 'BXF_TABLE_SOURCE', 'committed')]
                elif kind == 'override':
                    patches += [mock.patch.object(B, 'BXF_AVAILABLE', True)]
                for p in patches:
                    p.start()
                try:
                    yield mc, cap, (w, h, f), kind, B.plan_banded(w, h, f, cap)
                finally:
                    for p in reversed(patches):
                        p.stop()


class Wave2IsKept(unittest.TestCase):
    def test_terms_wave2_gives_the_bases_figures(self):
        n = 0
        for rec in WAVE2['stages']:
            st = {k: (tuple(v) if isinstance(v, list) else v) for k, v in rec.items()
                  if k in ('index', 'factor', 'supersample', 'input_size', 'padded_size', 'render_size', 'output_size')}
            for key, want in rec['peaks'].items():
                mc, split, tier, lora = key.split('|')
                # wave 2's flags: Redux capped the Brownian cache, Bolt did not (BOLT_BROWNIAN_CAPPED became True in wave 3)
                pk = B.stage_peaks(st, mc, bool(int(split)), tier=tier, lora_gb=float(lora), terms='wave2',
                                   brownian_capped=float(lora) == 0.0)
                self.assertAlmostEqual(pk['exp'][0], want['exp'][0], places=9, msg=key)
                self.assertEqual(pk['exp'][1], want['exp'][1], key)
                self.assertAlmostEqual(pk['up'][0], want['up'][0], places=9, msg=key)
                self.assertEqual(pk['up'][1], want['up'][1], key)
                for ph, v in want['phases_up'].items():
                    self.assertAlmostEqual(pk['phases_up'][ph], v, places=9, msg=key)
                n += 1
            for split, want in rec['minutes'].items():
                self.assertAlmostEqual(B.banded_minutes(st, bool(int(split)), terms='wave2'), want, places=9)
        self.assertGreater(n, 700)

    def test_the_refit_only_adds(self):
        """Every figure is at least wave 2's, but for lf.dm's whole run, which the runtime tables count only below
        LFDM_NARROW_PX (wave 2: 8,192 px; item (e)): on a 'bxf' stage between the two widths the finish phase is lower by
        exactly that term (a planned table's finish bound covers lf.dm itself, by its own lookups)."""
        for rec in WAVE2['stages']:
            st = {k: (tuple(v) if isinstance(v, list) else v) for k, v in rec.items()
                  if k in ('index', 'factor', 'supersample', 'input_size', 'padded_size', 'render_size', 'output_size')}
            for mc in CAPS:
                for split in (False, True):
                    for tier in B.FINISH_TIERS:
                        for way in ({}, {'carry_gb': 2.38, 'warm_engine': True}, {'fresh_worker': True}):
                            s = dict(st, **way)
                            now = B.stage_peaks(s, mc, split, tier=tier)
                            w2 = B.stage_peaks(s, mc, split, tier=tier, terms='wave2')
                            drop = B.lfdm_gb(s, 'wave2') - B.lfdm_gb(s) if tier == 'bxf' else 0.0
                            for ph in B.PHASES:
                                self.assertGreaterEqual(now['phases_up'][ph] + 1e-9 + (drop if ph == 'finish' else 0.0),
                                                        w2['phases_up'][ph])
                            self.assertGreaterEqual(B.banded_minutes(s, split) + 1e-12, B.banded_minutes(s, split, 'wave2'))


class EveryTermCoversItsMeasurement(unittest.TestCase):
    def test_node_retention(self):
        for r in MEAS['node_retention']['rows']:
            if r['retained_gib'] > 0:
                self.assertIn(r['node'], B.ALLOC_NODE_GB, r)
                self.assertEqual(B.ALLOC_NODE_GB[r['node']][0], r['phase'])
                self.assertGreaterEqual(B.ALLOC_NODE_GB[r['node']][1], r['retained_gib'], r)
        self.assertGreaterEqual(sum(gb for _, gb in B.ALLOC_NODE_GB.values()), 1.8)     # integ's distinct-node term
        self.assertGreaterEqual(B.CANNY_KEPT_GB, MEAS['canny']['kept_gib'])
        self.assertGreaterEqual(B.CANNY_REPEAT_GB, max(MEAS['canny']['repeat_excess_gib']))

    def test_finish_retention(self):
        """Inside the measured domain (no masks; tier 0 at the pc48 class's 2 GiB and 1 process; tier 3 on every class),
        every stage whose finish plane is the measured size, and every smaller one, counts at least the measurement."""
        fr = MEAS['finish_retention']
        for tier, rows in (('tier3', fr['tier3']), ('bxf', fr['tier0'])):
            for size, gib in rows:
                st = {'padded_size': (1000, 1000), 'factor': 2.0}
                for frac in (1.0, 0.7, 0.25):
                    side = int((size * frac * 1e6) ** 0.5 / 2)
                    s = dict(st, padded_size=(side, side), finish_tier=tier, bxf_whole_passes=[])
                    if mp(B.finish_size(s)) <= size:
                        for mc in (CAPS if tier == 'tier3' else ('pc48',)):
                            got = B.finish_retention_gb(s, mc, masks=('none',))
                            self.assertIsNotNone(got, (tier, size, mc))
                            if frac == 1.0 or tier == 'bxf':
                                self.assertGreaterEqual(got, gib, (tier, size))
        self.assertEqual(set(B.FINISH_RETAIN_T0_WHOLE), set(fr['tier0_whole']))
        self.assertEqual(B.FINISH_RETAIN_T3[-1][0], 73.12)
        self.assertEqual(B.FINISH_RETAIN_T0[-1][0], 73.12)

    def test_unmeasured_retention_is_none(self):
        none = ('none',)
        big = {'padded_size': (7000, 4376), 'factor': 2.0}                     # a 122.5 MP finish: above 73.12 MP
        self.assertIsNone(B.finish_retention_gb(dict(big, finish_tier='tier3'), 'pc48', none))
        self.assertIsNone(B.finish_retention_gb(dict(big, finish_tier='bxf', bxf_whole_passes=[]), 'pc48', none))
        small = {'padded_size': (2285, 2003), 'factor': 2.0}
        t0 = dict(small, finish_tier='bxf', bxf_whole_passes=['lf.powo', 'lf.powx'])
        self.assertEqual(B.finish_retention_gb(t0, 'pc48', none), 0.65)
        self.assertIsNone(B.finish_retention_gb(dict(small, finish_tier='bxf', bxf_whole_passes=['lf.powx', 'post']),
                                                'pc48', none))

    def test_the_retention_is_carried_only_inside_its_measured_domain(self):
        """plan-chk3-2: alloc-finish ran the finish without protect and release masks, tier 0 at a 2 GiB band budget and
        1 process (tests/fixtures/plan3_measurements.json finish_retention.domain). A tier-0 finish at the 64 GB PC's
        3 GiB / 2 or the workstation's 6 GiB / 4 is not measured; neither is any finish with masks, and the planner cannot see
        a job's masks, so by default (every mask setting) nothing is carried."""
        dom = MEAS['finish_retention']['domain']
        self.assertEqual(B.FINISH_RETAIN_BANDS['bxf'], ((dom['band_budget_gb'], dom['processes']),))
        self.assertIsNone(B.FINISH_RETAIN_BANDS['tier3'])
        self.assertEqual(B.FINISH_RETAIN_MASKS, tuple(dom['masks']))
        self.assertEqual(B.FINISH_MASKS, ('none', 'protect', 'protect+release'))
        self.assertLess(set(B.FINISH_RETAIN_MASKS), set(B.FINISH_MASKS))
        small = {'padded_size': (2000, 2000), 'factor': 2.0}                     # a 16 MP finish
        t0 = dict(small, finish_tier='bxf', bxf_whole_passes=['lf.powo'])
        t3 = dict(small, finish_tier='tier3')
        for mc in CAPS:
            for st in (t0, t3):
                self.assertIsNone(B.finish_retention_gb(st, mc))                         # every mask setting: unmeasured
                for masks in (('protect',), ('protect+release',), ('none', 'protect')):
                    self.assertIsNone(B.finish_retention_gb(st, mc, masks))
            self.assertEqual(B.finish_retention_gb(t3, mc, ('none',)), 0.35)            # tier 3 takes no band or process
            want = 0.65 if mc == 'pc48' else None                                        # tier 0: only 2 GiB / 1 measured
            self.assertEqual(B.finish_retention_gb(t0, mc, ('none',)), want, mc)
        self.assertIsNone(B.finish_retention_gb(t0, None, ('none',)))                    # no class: fail closed
        self.assertEqual(B.finish_retention_gb(t3, None, ('none',)), 0.35)
        with self.assertRaises(ValueError):
            B.finish_retention_gb(t0, 'pc48', ('protected',))

    def test_tier3_takes_no_band_budget_or_process_count(self):
        """Why FINISH_RETAIN_BANDS['tier3'] is None: the node's tier-3 body takes neither (read from its source)."""
        import ast
        src = (ROOT / 'node_pack' / 'claude_banded' / 'bxf' / '__init__.py').read_text(encoding='utf8')
        cls = next(n for n in ast.parse(src).body if isinstance(n, ast.ClassDef) and n.name == 'CUFinishBanded')
        fns = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
        t3 = {a.arg for a in fns['_tier3'].args.args + fns['_tier3'].args.kwonlyargs}
        t0 = {a.arg for a in fns['_bxf'].args.args + fns['_bxf'].args.kwonlyargs}
        self.assertFalse({'band_gb', 'processes'} & t3)
        self.assertLessEqual({'band_gb', 'processes'}, t0)
        self.assertLessEqual({'protect', 'release'}, t3 & t0)                            # both take the masks

    def test_tier3_takes_the_largest_of_its_three_bounds(self):
        meas = json.loads((FIX / 'bxf_finish_memory.json').read_text(encoding='utf8'))['measurements']
        for m in meas:
            if m['tier'] != 'tier3':
                continue
            fs = (m['output_size'][0], m['output_size'][1])
            got = M.finish_commit_gb(fs, tuple(m['input_size']), 2.0, 1, 'tier3')
            self.assertGreaterEqual(got, m['own_gib'], m['source'])            # it bounds the runtime's 2.10 GiB at 1.2 MP
        for w, h, f in ROWS:
            for st in raw_stages(w, h, f):
                for mc in CAPS:
                    mcd = B.MACHINE_CLASSES[mc]
                    for split in (False, True):
                        up = B.stage_peaks(st, mc, split, tier='tier3')['phases_up']['finish']
                        I, R, O = mp(st['padded_size']), mp(st['render_size']), mp(st['output_size'])
                        x_up = B.X0 + B.XR_UP * R + B.XRES
                        v_fin = B.CTX_GB if split else max(B.V0 + B.V_R * R, B.VS0 + B.VS_BPR * B.G * R)
                        extra = 0.0 if split else B.alloc_gb('finish')
                        svc = B.service_gb(st)
                        fc = M.finish_commit_gb(B.finish_size(st), st['padded_size'], mcd['band_gb'], mcd['processes'],
                                                'tier3')
                        self.assertGreaterEqual(up + 1e-9, v_fin + x_up + fc + extra + svc)
                        self.assertGreaterEqual(up + 1e-9, v_fin + x_up + B.tier3_finish_gb(mp(B.finish_size(st)), I) + extra
                                                + svc)
                        self.assertGreaterEqual(up + 1e-9, planner.stage_peak_gb(R, O, I) - B.SERVICE_GB + svc)

    def test_disk_covers_the_measured_scratch_and_the_stages_own_planes(self):
        own_o = 3 + 3 + 3 + 3                      # init, creative, structure and the output, u8
        for size, gib in MEAS['bxf_scratch']['rows']:
            self.assertGreaterEqual((B.DISK_O - own_o) * size * 1e6, gib * GIB, size)
        self.assertGreaterEqual(B.DISK_O - own_o, 117)
        self.assertGreaterEqual(B.DISK_I, 3 + 3 + 48 + 12 + 4 * B.SAM_PLANES_MAX)   # input, source, big8, view, masks
        self.assertGreaterEqual(B.DISK_R, 12 + 12 + 1)                    # canvas f32 at k = 4, hint f32, edges u8
        for w, h, f in ROWS:
            for st in raw_stages(w, h, f):
                I, R, O = (st[k][0] * st[k][1] for k in ('padded_size', 'render_size', 'output_size'))
                self.assertEqual(planes.live_bytes(I, R, O), B.DISK_I * I + B.DISK_R * R + B.DISK_O * O)
                self.assertAlmostEqual(B.banded_disk_gb(st) * 1e9, planes.live_bytes(I, R, O), delta=1.0)
                self.assertGreaterEqual(planes.disk_need(I, R, O), int(1.1 * (117 + own_o) * O))
                self.assertGreaterEqual(planes.disk_need(I, R, O), int(1.1 * planes.live_bytes(I, R, O)))
                # every earlier moment of the stage holds less: Canny's three temporaries (6 B per R px) come before the
                # O planes but init, and R is at most about 4 O
                self.assertLessEqual(6 * R, (B.DISK_O - 3) * O)


class TheSamTerms(unittest.TestCase):
    def test_the_most_terms_and_mask_planes_a_stage_runs(self):
        """SAM_TERMS_MAX and SAM_PLANES_MAX are the most over every protected-area choice (engine/controls.py; one
        CUSam3DetectLean per term and a union per 8 masks, service/banded_runner.sam_planes)."""
        import itertools
        from engine import controls
        from service import banded_runner
        terms = planes_n = 0
        cats = list(controls.PROTECT_ORDER)
        for n in range(len(cats) + 1):
            for sub in itertools.combinations(cats, n):
                p = controls.resolve({'protect': list(sub)})[0]
                terms = max(terms, len(p.get('protect_terms') or []) + len(p.get('release_terms') or []))
                planes_n = max(planes_n, banded_runner.sam_planes(p))
        self.assertEqual(B.SAM_TERMS_MAX, terms)
        self.assertEqual(B.SAM_PLANES_MAX, planes_n)
        self.assertEqual(B.SAM_TERMS_WAVE2, 9)


class TheEngineTerms(unittest.TestCase):
    def test_phase_aware_node_retention(self):
        nodes = {ph: sum(gb for p, gb in B.ALLOC_NODE_GB.values() if B.PHASES.index(p) <= B.PHASES.index(ph))
                 for ph in B.PHASES}
        canny = B.CANNY_KEPT_GB + B.CANNY_REPEAT_GB
        for ph in B.PHASES:
            self.assertAlmostEqual(B.alloc_gb(ph), nodes[ph] + canny)
            self.assertAlmostEqual(B.alloc_gb(ph, warm=True), sum(gb for _, gb in B.ALLOC_NODE_GB.values()) + canny)
        self.assertLess(B.alloc_gb('P0'), B.alloc_gb('sampling'))          # CUEncodePlane runs in sampling
        self.assertLess(B.alloc_gb('P0'), B.alloc_gb('P0', warm=True))

    def test_each_phase_counts_the_engines_retention_over_the_grid(self):
        for w, h, f in ROWS:
            for st in raw_stages(w, h, f):
                for mc in CAPS:
                    for split in (False, True):
                        for tier in B.FINISH_TIERS:
                            for way in ({}, {'carry_gb': 6.29, 'warm_engine': True}, {'carry_gb': 0.65}):
                                s = dict(st, **way)
                                now = B.stage_peaks(s, mc, split, tier=tier)['phases_up']
                                w2 = B.stage_peaks(s, mc, split, tier=tier, terms='wave2')['phases_up']
                                for ph in B.PHASES:
                                    want = 0.0 if (ph == 'finish' and split) else (way.get('carry_gb', 0.0)
                                                                                    + B.alloc_gb(ph, way.get('warm_engine', False)))
                                    if tier == 'tier3' and ph == 'finish':
                                        self.assertGreaterEqual(now[ph] + 1e-9, w2[ph] + want)
                                    else:
                                        drop = B.lfdm_gb(s, 'wave2') - B.lfdm_gb(s) if ph == 'finish' else 0.0
                                        self.assertAlmostEqual(now[ph] - w2[ph], want - drop, places=9)

    def check_starts(self, open_domain):
        """Every admitted plan's stages: the first starts as it is; each later one counts exactly the previous finish's
        measured retention (finish_retention_gb at the plan's class, every mask setting) or starts in a fresh engine with
        SPLIT_MINUTES, never neither. open_domain: FINISH_RETAIN_MASKS patched to every mask setting, as a registered
        measurement with protect and release would make it."""
        n = fresh = carried = 0
        tier3_classes = set()
        patch = mock.patch.object(B, 'FINISH_RETAIN_MASKS', B.FINISH_MASKS if open_domain else B.FINISH_RETAIN_MASKS)
        with patch:
            for mc, cap, row, kind, p in plans(kinds=('table', 'override', 'tier3')):
                if not p.ok:
                    continue
                for k, s in enumerate(p.stages):
                    if k == 0:
                        self.assertFalse(s.fresh_worker)
                        self.assertEqual(s.carry_gb, 0.0)
                        continue
                    n += 1
                    prev = p.stages[k - 1]
                    ret = B.finish_retention_gb(prev, mc)
                    if s.fresh_worker:
                        fresh += 1
                        self.assertEqual(s.carry_gb, 0.0)
                        self.assertFalse(s.warm_engine)
                        self.assertAlmostEqual(B.banded_minutes(s, s.split_finish)
                                               - B.banded_minutes(dict(dataclasses.asdict(s), fresh_worker=False),
                                                                  s.split_finish), B.SPLIT_MINUTES)
                    else:
                        carried += 1
                        self.assertIsNotNone(ret, (mc, row, kind, k))                # never neither
                        self.assertEqual(s.carry_gb, ret)
                        self.assertGreater(s.carry_gb, 0.0)
                        self.assertEqual(s.warm_engine, not prev.split_finish)
                        if prev.finish_tier == 'bxf':                                # tier 0 measured at 2 GiB / 1 only
                            self.assertEqual(mc, 'pc48', (row, kind, k))
                        else:
                            tier3_classes.add(mc)
                    if ret is None:
                        self.assertTrue(s.fresh_worker, (mc, row, kind, k))
        return n, fresh, carried, tier3_classes

    def test_in_this_version_every_stage_after_the_first_starts_in_a_fresh_engine(self):
        """plan-chk3-2: no finish retention is measured with protect and release masks, which the planner cannot see, so
        every stage after the first starts in a fresh engine, on every machine class, with a node table and the override."""
        n, fresh, carried, _ = self.check_starts(False)
        self.assertGreater(n, 20)
        self.assertEqual(fresh, n)
        self.assertEqual(carried, 0)

    def test_inside_a_measured_domain_the_retention_is_carried(self):
        """With every mask setting measured (patched), a stage after a tier-3 finish of at most 73.12 MP carries its figure
        on any class (it fits on the 64 GB PC and the workstation here), and after a tier-0 finish only on the pc48 class
        (2 GiB, 1 process); elsewhere it starts fresh."""
        n, fresh, carried, tier3_classes = self.check_starts(True)
        self.assertGreater(n, 20)
        self.assertGreater(fresh, 0)
        self.assertGreater(carried, 0)
        self.assertLessEqual({'pc64', 'ws128'}, tier3_classes)                  # tier 3 at 3 GiB / 2 and 6 GiB / 4 too

    def test_the_checkers_example_starts_fresh(self):
        """plan-chk3-2's evidence: 3500 x 2188 6x at 59.0 under the override carried 0.65 GiB from a tier-0 finish at 3 GiB
        / 2 processes into stage 1; now stages 1 and 2 start in fresh engines."""
        with mock.patch.dict(B.BANDED_PROVEN_MP, PROVEN), mock.patch.object(B, 'BXF_AVAILABLE', True):
            p = B.plan_banded(3500, 2188, 6, 59.0)
        self.assertTrue(p.ok, p.reason)
        self.assertEqual([s.finish_tier for s in p.stages], ['bxf'] * 3)
        self.assertEqual([(s.fresh_worker, s.carry_gb, s.warm_engine) for s in p.stages],
                         [(False, 0.0, False), (True, 0.0, False), (True, 0.0, False)])

    def test_the_retention_is_counted_unless_it_would_bind_admission(self):
        with mock.patch.object(B, 'FINISH_RETAIN_MASKS', B.FINISH_MASKS):
            for mc, cap, row, kind, p in plans():
                if not p.ok:
                    continue
                for k, s in enumerate(p.stages[1:], 1):
                    ret = B.finish_retention_gb(p.stages[k - 1], mc)
                    if ret is not None and s.fresh_worker:
                        way = {'fresh_worker': False, 'carry_gb': ret, 'warm_engine': not p.stages[k - 1].split_finish}
                        d = dict(dataclasses.asdict(s), **way)
                        split = B.split_needed(d, mc, cap)
                        up = B.stage_peaks(d, mc, split)['up'][0]
                        self.assertGreater(B.MARGIN * up, cap - B.CAP_SPARE_GB, (mc, row, kind, k))

    def test_the_stage_dict_carries_the_engine_fields(self):
        with mock.patch.dict(B.BANDED_PROVEN_MP, PROVEN), mock.patch.object(B, 'BXF_TABLE', node_table(1)), \
                mock.patch.object(B, 'BXF_TABLE_SOURCE', 'committed'):
            p = B.plan_banded(3500, 2188, 8, 122.2)
        self.assertTrue(p.ok, p.reason)
        d = p.to_dict()
        self.assertEqual(json.loads(json.dumps(d)), d)
        for s, sd in zip(p.stages, d['stages']):
            for k in ('fresh_worker', 'carry_gb', 'warm_engine', 'mode'):
                self.assertIn(k, sd)
            self.assertEqual(round(B.stage_peaks(sd, 'ws128', sd['split_finish'])['up'][0], 1), s.peak_upper_gb)
            self.assertEqual(round(B.banded_minutes(sd, sd['split_finish']), 1), s.minutes)
        self.assertTrue(d['stages'][2]['fresh_worker'])                    # after the 122.5 MP finish: unmeasured


class Admission(unittest.TestCase):
    def test_no_admitted_plan_is_over_the_cap_by_its_unrounded_bound(self):
        for mc, cap, row, kind, p in plans():
            if p.ok:
                ups = [B.stage_peaks(s, mc, s.split_finish)['up'][0] for s in p.stages]
                self.assertLessEqual(B.MARGIN * max(ups), cap - B.CAP_SPARE_GB, (mc, row, kind))
                self.assertEqual(p.peak_ram_gb, round(B.MARGIN * max(ups), 1))

    def test_at_the_boundary(self):
        """plan-chk-1: a bound that only rounding brings under the cap is refused."""
        cap = 59.0
        edge = (cap - B.CAP_SPARE_GB) / B.MARGIN                          # 55.238...
        for upper, ok in ((edge - 1e-6, True), (edge + 0.002, False)):
            fake = {'exp': (upper - 1.0, 'P0'), 'up': (upper, 'P0'),
                    'phases_up': {'P0': upper, 'sampling': 1.0, 'decode': 1.0, 'finish': 1.0}}
            with mock.patch.dict(B.BANDED_PROVEN_MP, PROVEN), mock.patch.object(B, 'BXF_AVAILABLE', True), \
                    mock.patch.object(B, 'stage_peaks', lambda *a, **k: fake):
                p = B.plan_banded(3500, 2188, 4, cap)
            self.assertEqual(p.ok, ok, (upper, p.reason))
            if not ok:                                                    # wave 2's rounded rule admitted it
                self.assertLessEqual(round(upper, 1) * B.MARGIN, cap - B.CAP_SPARE_GB)


class LfDmFromTheRuntimeTables(unittest.TestCase):
    def test_never_narrower_than_the_tables_show(self):
        bpp, reach, ops = M.CALLS['lf.dm'][0]
        ops = tuple(ops) + M.EW
        widest = 0
        for i in (1, 2):
            t = node_table(i)
            for band in (2.0, 3.0, 6.0):
                for W in list(range(64, 4000, 7)) + [1457, 1458, 1459, 1460, 2918]:
                    h = M.band_height(W, bpp, band, reach)
                    for H in (15, 16, 29, 30, 64, 289, 577, 1153, 2305, 4377, 8752, 17504, 28000):
                        if H <= B.TALL_MAX * W and not t.banded(*ops, geom=g1.Geometry(H, W, h, reach)):
                            widest = max(widest, W)
        self.assertEqual(widest, 1458)
        self.assertGreaterEqual(B.LFDM_NARROW_PX, widest + 1)
        self.assertEqual(B.LFDM_NARROW_PX, 2 * (widest + 1))                # wave 2's rule: twice the frontier


if __name__ == '__main__':
    unittest.main()
