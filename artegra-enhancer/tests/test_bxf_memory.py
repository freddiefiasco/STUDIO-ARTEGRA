"""engine/bxf/memory.finish_commit_gb, the finish's own commit as an upper bound (contracts.g1u): it bounds every registered
fresh-process measurement of the finish (tests/fixtures/bxf_finish_memory.json: sizes, tier, band budget, the ops run whole,
and the measured peak less the process's inputs-only baseline), per tier and per op classification, and with the table each
ran with (fin-chk-1: whole_passes_for counts every pass, whole-plane op and the stage output the table leaves whole),
including whole-mapped ops' transients, lf.dm on a narrow stage and a band over its budget; it grows with the plane, the budget
and the process count; only registered values are accepted; its EW list is the finish's. Wave 3: the bound at the production
values, tier 3 at 32,000 px wide stages with each row's branch label, and the work disk (SCRATCH_BPO, STAGE_PLANES_BPO)
against the scratch folder and the volume of every finish that ran alone. numpy only."""
import ast
import importlib
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GIB = 2 ** 30
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


def gate_g2_constant(name):
    """A module constant of tools/gate_g2.py, read from its source (no numpy or torch import)."""
    tree = ast.parse((ROOT / 'tools' / 'gate_g2.py').read_text(encoding='utf8'))
    node = next(n for n in tree.body if isinstance(n, ast.Assign) and getattr(n.targets[0], 'id', '') == name)
    return ast.literal_eval(node.value)


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

    def test_the_measurements_are_bounded_with_the_table_they_ran_with(self):
        """fin-chk-1: the planner passes the worker's table, not its classed-whole ops. Each tier-0 measurement ran with a
        committed table in its own environment (g1-2.9.1: TABLES[0]; g1-runtime: TABLES[1]) or with every op whole ('all':
        AllWhole); the bound with that table must hold too."""
        M, g1, g1t = engine('bxf.memory'), engine('bxf.g1'), engine('bxf.g1_table')
        data = json.loads(FIXTURE.read_text(encoding='utf8'))
        tables = {'g1-2.9.1': g1.Table(g1t.TABLES[0], g1t.TABLES[0]['environment']),
                  'g1-runtime': g1.Table(g1t.TABLES[1], g1t.TABLES[1]['environment']), 'all': g1.AllWhole(),
                  'g1-node': g1.Table(g1t.TABLES[2], g1t.TABLES[2]['environment'])}      # the render node class (wave 3)
        seen = set()
        for m in data['measurements']:
            if m['tier'] != 'bxf':
                continue
            t = tables[m['whole_ops']]
            seen.add(m['whole_ops'])
            bound = M.finish_commit_gb(m['output_size'], m['input_size'], m['band_gb'], m['processes'], 'bxf', table=t,
                                       output_rows=m.get('output_rows'))
            self.assertGreaterEqual(bound, m['own_gib'], m)
            whole = M.whole_passes_for(t, m['output_size'], m['band_gb'])
            if m['whole_ops'] == 'all':
                self.assertEqual(len(whole), len(M.PASSES) + len(M.WHOLE_CALLS) + 1)
        self.assertEqual(seen, set(tables))

    def test_the_production_values_are_measured_and_bounded_with_the_margin(self):
        """Wave 3 (fin3-mem-a, fin3-mem-b): the BXF's Job peak commit (its pool processes counted) in a fresh process at
        pc64's values (3 GiB, 2 processes), ws128's (6 GiB, 4) and pc48's (2 GiB, 1) on the release bar's finish planes with
        protect and release masks on, with the render node class's committed table, and once with every op whole. The bound
        holds each with the module's margin (MARGIN_WAVE3: a raise leaves at least that); a point that did not land keeps
        today's bound (contracts.conservative_bounds), so only the landed points are asserted."""
        M, g1, g1t = engine('bxf.memory'), engine('bxf.g1'), engine('bxf.g1_table')
        data = json.loads(FIXTURE.read_text(encoding='utf8'))
        node = g1.Table(g1t.TABLES[2], g1t.TABLES[2]['environment'])
        wave3 = [m for m in data['measurements'] if m['source'].startswith('fin3-mem-')]
        self.assertTrue(wave3)
        values = set()
        for m in wave3:
            self.assertEqual(m['mask_case'], 'protect+release', m)
            self.assertAlmostEqual(m['own_gib'], m['peak_gib'] - m['inputs_only_gib'], places=3)   # the Job peak, not the process's
            self.assertGreaterEqual(m['peak_gib'] + 1e-9, m['process_peak_gib'], m)
            if m['tier'] == 'bxf':
                values.add((m['band_gb'], m['processes']))
                t = g1.AllWhole() if m['whole_ops'] == 'all' else node
                bound = M.finish_commit_gb(m['output_size'], m['input_size'], m['band_gb'], m['processes'], 'bxf', table=t,
                                           output_rows=m.get('output_rows'))
            else:
                bound = M.finish_commit_gb(m['output_size'], m['input_size'], 2.0, 1, 'tier3')
            self.assertGreaterEqual(bound, M.MARGIN_WAVE3 * m['own_gib'], m)
        self.assertTrue({(3.0, 2), (6.0, 4)} <= values, values)                    # the two production values off 2 GiB / 1
        self.assertTrue(any(m['whole_ops'] == 'all' for m in wave3 if m['tier'] == 'bxf'))
        self.assertTrue(any(m['processes'] == 4 and m['output_size'][0] * m['output_size'][1] > 1.2e8 for m in wave3))
        big = {(m['band_gb'], m['processes']) for m in wave3 if m['output_size'][0] * m['output_size'][1] > 4.8e8}
        self.assertTrue({(3.0, 2), (6.0, 4)} <= big, big)                       # 8x of 3500 x 2188's pass 3 (490 MP)

    def test_tier3_bounds_the_widest_stage(self):
        """plan-chk-5 (wave 3): 5.0.1's whole finish, protect and release on, at 32,000 px wide stages on the worker runtime:
        finish_commit_gb(tier='tier3') bounds every row with the margin. Only a row whose scene exercises every branch
        (branches_not_exercised []) shows the bound with every branch on: the 1,200 and 2,400 row stages. Under BASE's height
        tools/gate_g2.scene crops the base tile to its top rows, so a thinner row has no floor (from 0.66 of the tile's
        height), no litter (from 0.70) and no sky gaps, and at 160 pre rows no badges (hardware islands and the colour filter,
        from 0.34 of the stage): it is labelled with what it did not exercise and is no evidence for those branches (F3C-2;
        tests/worker/test_bxf_tier3_scenes.py checks each label against the scene)."""
        M = engine('bxf.memory')
        data = json.loads(FIXTURE.read_text(encoding='utf8'))
        base_h, branches = gate_g2_constant('BASE')[0], set(gate_g2_constant('BRANCHES'))
        floor = {'material_components', 'material_dropped', 'litter_kept'}
        wide = [m for m in data['measurements'] if m['tier'] == 'tier3' and m['output_size'][0] >= 32000]
        self.assertTrue(wide)
        for m in wide:
            self.assertIn('branches_not_exercised', m, m['source'])           # every wide row says what it did not run
            gone, pre_h = set(m['branches_not_exercised']), m['input_size'][1]
            self.assertLessEqual(gone, branches, m['source'])
            self.assertEqual(sorted(gone), m['branches_not_exercised'], m['source'])
            if pre_h >= base_h:                                                 # a whole base tile holds every branch
                self.assertEqual(gone, set(), m['source'])
            if pre_h <= 0.66 * base_h:                                          # above the tile's floor: none of it
                self.assertLessEqual(floor, gone, m['source'])
            self.assertEqual(bool(gone), 'not every branch' in m['source'], m['source'])
            self.assertGreaterEqual(M.finish_commit_gb(m['output_size'], m['input_size'], 2.0, 1, 'tier3'),
                                    M.MARGIN_WAVE3 * m['own_gib'], m)
        full = {m['output_size'][1] for m in wide if not m['branches_not_exercised']}
        self.assertLessEqual({1200, 2400}, full, 'the every-branch evidence at 32,000 px')

    def test_the_work_disk_bounds_every_scratch_and_every_finish_alone(self):
        """F3C-1 (wave 3): SCRATCH_BPO bytes per finish-plane px is at least the BXF scratch folder's sampled peak in every
        wave-3 run, per finish-plane px and per output px of these planes (a finish plane at most 8 rows over its crop),
        and at a factor-1.5 stage (a 6x plan's last pass; work_disk_checks); with STAGE_PLANES_BPO (init, creative, structure
        and the output, u8 3 each) and the pre plane's 3 B per input px it bounds the scratch volume's free-space drop of
        every finish that ran alone in its packet (ran_alone; a drop beside another step is not the finish's own). The merge
        role counts STAGE_PLANES_BPO + SCRATCH_BPO (310 in wave 3) in banded_plan.DISK_O, planes.live_bytes' O term and
        PHASE_PLANES['finish'] (the finish package's adds.bound_raises); neither figure is ever lowered below its wave-3
        value."""
        M = engine('bxf.memory')
        data = json.loads(FIXTURE.read_text(encoding='utf8'))
        rows = [m for m in data['measurements'] if m['source'].startswith(('fin3-mem-a ', 'fin3-mem-b ')) and m['tier'] == 'bxf']
        self.assertEqual(len(rows), 16)
        self.assertGreaterEqual(M.SCRATCH_BPO, 298)                             # wave 3's floors: raise only
        self.assertGreaterEqual(M.STAGE_PLANES_BPO, 12)
        checks = data['work_disk_checks']
        self.assertTrue(any(c['factor'] == 1.5 for c in checks))
        for c in checks:
            (w, h) = c['output_size']
            self.assertAlmostEqual(c['scratch_bytes'] / (w * h), c['scratch_bpo'], places=1)
            self.assertGreaterEqual(M.SCRATCH_BPO * w * h, c['scratch_bytes'], c['source'])
        alone = []
        for m in rows:
            (w, h), (pw, ph) = m['output_size'], m['input_size']
            self.assertLessEqual(h - m['output_rows'], 8, m['source'])
            self.assertAlmostEqual(m['scratch_bytes'] / (w * h), m['scratch_bpo'], places=1)
            self.assertGreaterEqual(M.SCRATCH_BPO * w * h, m['scratch_bytes'], m['source'])
            self.assertGreaterEqual(M.SCRATCH_BPO * w * m['output_rows'], m['scratch_bytes'], m['source'])
            if m['ran_alone']:
                alone.append(m)
                self.assertGreaterEqual((M.STAGE_PLANES_BPO + M.SCRATCH_BPO) * w * h + 3 * pw * ph, m['volume_drop_bytes'],
                                        m['source'])
        self.assertGreaterEqual(len(alone), 7)
        self.assertTrue(any(m['output_size'][0] * m['output_size'][1] > 4.8e8 for m in alone))     # 490 MP, alone
        self.assertTrue({m['processes'] for m in alone} >= {1, 2, 4})

    def test_each_raised_coefficient_is_pinned_to_its_evidence(self):
        """Wave 3 raises memory.py's own coefficients only (never lowers one): RAISED names each, the value before, the value
        now and the measurement that forced it, which is in the fixture."""
        M = engine('bxf.memory')
        data = json.loads(FIXTURE.read_text(encoding='utf8'))
        sources = {m['source'].split(',')[0] for m in data['measurements']}
        for name, (before, now, evidence) in M.RAISED.items():
            self.assertEqual(getattr(M, name), now, name)
            self.assertGreater(now, before, name)
            self.assertIn(evidence, sources, name)

    def test_an_uncovered_whole_plane_op_the_output_and_an_overrun_count(self):
        M, g1 = engine('bxf.memory'), engine('bxf.g1')

        class Except(g1.AllBanded):
            def __init__(self, *missing):
                self.missing = set(missing)

            def banded(self, *ops, geom=None):
                return not (set(ops) & self.missing)
        f = M.finish_commit_gb
        size, pre = (8000, 5000), (4000, 2500)
        base = f(size, pre, 2.0, 1, 'bxf', table=g1.AllBanded())
        self.assertEqual(base, f(size, pre, 2.0, 1, 'bxf'))
        self.assertEqual(M.whole_passes_for(Except('E6 label out=mapped'), size, 2.0), ['E6 label out=mapped'])
        self.assertAlmostEqual(f(size, pre, 2.0, 1, 'bxf', table=Except('E6 label out=mapped')) - base,
                               M.WHOLE_CALLS['E6 label out=mapped'] * 8000 * 5000 / GIB)
        self.assertEqual(M.whole_passes_for(Except('shadow_toe_u8'), size, 2.0), ['write_output'])
        self.assertAlmostEqual(f(size, pre, 2.0, 1, 'bxf', table=Except('shadow_toe_u8')) - base,
                               M.OUTPUT_WHOLE_BPP * 8000 * 5000 / GIB)
        self.assertAlmostEqual(f(size, pre, 2.0, 1, 'bxf', ['shadow_toe_u8']) - base, M.OUTPUT_WHOLE_BPP * 8000 * 5000 / GIB)
        self.assertAlmostEqual(f(size, pre, 2.0, 1, 'bxf', ['E5 median']) - base, M.WHOLE_CALLS['E5 median'] * 8000 * 5000 / GIB)
        # at 32,000 px the mm clamp's band (288 + 2 x 40 rows at 340 B/px) is over a 2 GiB budget even at the smallest height
        self.assertAlmostEqual(M.band_peak_gb((32000, 20000), 2.0), 368 * 32000 * 340 / GIB)
        self.assertEqual(M.band_peak_gb((32000, 20000), 6.0), 6.0)
        self.assertEqual(M.band_peak_gb((32000, 20000), 2.0, whole=['clamped', 'post']),
                         max(2.0, (288 + 2 * 72) * 32000 * 120 / GIB))
        self.assertAlmostEqual(f((32000, 20000), (16000, 10000), 2.0, 1, 'bxf') - f((32000, 20000), (16000, 10000), 6.0, 1, 'bxf'),
                               368 * 32000 * 340 / GIB - 6.0)
        with self.assertRaises(KeyError):
            M.whole_bytes_per_px('not a pass')

    def test_calls_and_passes_agree(self):
        M = engine('bxf.memory')
        self.assertEqual(sorted(M.CALLS), sorted(M.PASSES))
        for k, calls in M.CALLS.items():
            self.assertGreaterEqual(len(calls), 1, k)
            self.assertEqual(M.PASSES[k][0], max(c[0] for c in calls), k)
            for bpp, reach, ops in calls:
                self.assertTrue(set(ops).isdisjoint(M.EW), k)
                self.assertGreaterEqual(reach, 0, k)
        self.assertEqual(len(M.CALLS['clamped']), 2)
        self.assertTrue(set(M.OUTPUT_OPS) & set(M.EW))

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
