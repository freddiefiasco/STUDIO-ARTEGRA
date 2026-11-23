"""5.0.2 build wave 3: what the merge of the five packages applied and relies on, checked in process (sizes only).

- The finish package's bound raises (its adds.bound_raises, for the merge role): the banded exact finish's scratch folder
  peaked at 297.5 B per finish-plane pixel in every wave-3 run (engine/bxf/memory.SCRATCH_BPO 298, with the stage's own
  init, creative, structure and output planes, STAGE_PLANES_BPO 12), so the planner's disk figure (banded_plan.DISK_O) and
  the service's disk check (engine/planes.live_bytes and disk_need) count 310 B per finish-plane pixel, over the stage's
  finish plane (banded_plan.finish_px: the padded output, never fewer pixels than the output).
- The ruling on the physical-memory rule's finish phase (service/banded_runner.PHASE_PLANES['finish']): it counts the planes
  the finish still touches, 130 B per finish-plane pixel (STAGE_PLANES_BPO 12 + banded_runner.FINISH_LIVE_BPO 118, the
  Workspace's peak live count, 116.0 measured in every wave-3 row), not the folder's 310: the other 180 B are freed scratch
  files a view still maps, file-backed (np.memmap), never read or written again, so they cost disk only.
- plan-chk-5 (the plan package's later item for the merge role): the planner's tier-3 finish phase bounds every tier-3
  measurement at a 32,000 px wide stage (tests/fixtures/bxf_finish_memory.json) with the finish module's margin.
- contracts.g1u end to end, both sides: the service's G1u assigns the planner's table from the engine runtime's environment;
  a planned stage's bxf_whole_passes are memory.whole_passes_for on that committed table; the engine it starts carries the
  local table path the planner's table used, and the finish node's own g1.load() there reads the same table (the same
  decision at every lookup of the stage), with no local table and with a local table's veto on top.
- contracts.restart on the merged planner: every Large-image pass after the first starts in a fresh engine (the fake engine's
  runs are tests/test_service3_restart.py, tests/test_integ_large_image_job.py and tests/test_service3_keep_planes.py)."""
import json
import os
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from engine import banded_plan as B
from engine import planes, planner
from engine.bxf import g1
from engine.bxf import memory as M
from service import banded_runner as BR
from service import bxf_probe, workers

ROOT = Path(__file__).resolve().parents[1]
FINISH_FIXTURE = ROOT / 'tests' / 'fixtures' / 'bxf_finish_memory.json'
GIB = float(1 << 30)
# the target rows, the design's 5333 x 3333 6x, and thin, odd, padded and tall shapes (TALL_MAX allows 100:1)
ROWS = [(3500, 2188, 4), (3500, 2188, 6), (3500, 2188, 8), (2800, 3500, 4), (2800, 3500, 6), (2800, 3500, 8),
        (4000, 4000, 8), (5333, 3333, 6), (4000, 160, 8), (8000, 300, 4), (16000, 160, 2), (9999, 1001, 2), (333, 7777, 4),
        (300, 16000, 2), (1001, 1003, 6), (257, 25600, 1.25)]


def raw_stages(w, h, f):
    cur, out = (w, h), []
    for i, ff in enumerate(planner.STAGE_FACTORS.get(f, [Fraction(f).limit_denominator(8)])):
        st = B.stage_choice(cur, ff, i)
        out.append(st)
        cur = st['output_size']
    return out


def stages():
    for w, h, f in ROWS:
        for st in raw_stages(w, h, f):
            yield (w, h, f), st


def px(size):
    return int(size[0]) * int(size[1])


class TheFinishWorkDiskIsCountedPerFinishPlanePixel(unittest.TestCase):
    PER_O = M.STAGE_PLANES_BPO + M.SCRATCH_BPO

    def test_the_o_term_is_the_finish_modules_figure_everywhere(self):
        self.assertEqual(self.PER_O, 310)                                     # wave 3: 12 + 298
        self.assertGreaterEqual(B.DISK_O, self.PER_O)
        self.assertEqual(planes.live_bytes(0, 0, 1), B.DISK_O)                # planes.py is loaded by path: one figure
        self.assertEqual((planes.live_bytes(1, 0, 0), planes.live_bytes(0, 1, 0)), (B.DISK_I, B.DISK_R))
        self.assertEqual(BR.PHASE_PLANES['finish'][:3], (3, 0, 0))           # the pre plane, 3 B per input px

    def test_the_finish_plane_is_never_smaller_than_the_output(self):
        padded = 0
        for row, st in stages():
            fw, fh = B.finish_size(st)
            self.assertGreaterEqual(B.finish_px(st), px(st['output_size']), row)
            self.assertEqual(B.finish_px(st), max(fw * fh, px(st['output_size'])), row)
            padded += B.finish_px(st) > px(st['output_size'])
        self.assertGreater(padded, 0, 'the grid holds padded stages, where the finish plane is the larger')

    def test_the_planners_disk_figure_covers_the_measured_work_disk(self):
        for row, st in stages():
            I, R, F = px(st['padded_size']), px(st['render_size']), B.finish_px(st)
            want = self.PER_O * F + B.DISK_I * I + B.DISK_R * R
            self.assertGreaterEqual(B.banded_disk_gb(st) * 1e9 + 1.0, want, (row, st['index']))

    def test_the_services_disk_check_covers_it_and_adds_its_tenth(self):
        for row, st in stages():
            I, R, F = px(st['padded_size']), px(st['render_size']), B.finish_px(st)
            want = self.PER_O * F + B.DISK_I * I + B.DISK_R * R
            self.assertGreaterEqual(planes.live_bytes(I, R, F), want, row)
            self.assertGreaterEqual(planes.disk_need(I, R, F), int(1.1 * want), row)

    def test_the_physical_rules_finish_phase_counts_its_live_planes(self):
        live = M.STAGE_PLANES_BPO + BR.FINISH_LIVE_BPO
        for row, st in stages():
            I, F = px(st['padded_size']), B.finish_px(st)
            for masks in (0, 5):
                got = BR.stage_planes_bytes(st, 'finish', masks)
                self.assertEqual(got, live * F + 3 * I + BR.MASK_BPI * I * masks, (row, masks))

    def test_every_measured_scratch_folder_and_every_finish_alone_is_covered(self):
        data = json.loads(FINISH_FIXTURE.read_text(encoding='utf8'))
        rows = [m for m in data['measurements'] if m.get('scratch_bytes')] + list(data.get('work_disk_checks') or [])
        self.assertGreaterEqual(len(rows), 16)
        alone = 0
        for m in rows:
            plane = px(m['output_size'])
            self.assertGreaterEqual((B.DISK_O - M.STAGE_PLANES_BPO) * plane, m['scratch_bytes'], m['source'])
            if m.get('ran_alone'):
                alone += 1
                self.assertGreaterEqual(B.DISK_O * plane + B.DISK_I * px(m['input_size']), m['volume_drop_bytes'],
                                        m['source'])
        self.assertGreaterEqual(alone, 7)


class TheRulingOnThePhysicalRulesFinishTerm(unittest.TestCase):
    """The wave-3 merge's ruling (23 Nov): the RAM rule's finish phase counts the stage's planes and the finish's live
    scratch, 130 B per finish-plane pixel; the disk figure and the disk check keep the folder's 310."""

    def test_the_finish_term_is_the_stage_planes_and_the_live_scratch(self):
        self.assertEqual(BR.PHASE_PLANES['finish'][3], M.STAGE_PLANES_BPO + BR.FINISH_LIVE_BPO)
        self.assertEqual(BR.PHASE_PLANES['finish'][3], 130)
        self.assertLessEqual(BR.PHASE_PLANES['finish'][3], B.DISK_O)        # never more than the folder on disk

    def test_the_live_scratch_bounds_every_measured_workspace_count(self):
        self.assertGreaterEqual(BR.FINISH_LIVE_BPO, 118)
        data = json.loads(FINISH_FIXTURE.read_text(encoding='utf8'))
        rows = [m for m in data['measurements'] if m.get('workspace_bpo') is not None]
        self.assertGreaterEqual(len(rows), 16)
        for m in rows:
            self.assertGreaterEqual(BR.FINISH_LIVE_BPO, m['workspace_bpo'], m['source'])

    def test_the_disk_keeps_the_folders_figure(self):
        self.assertGreaterEqual(B.DISK_O, 310)
        self.assertGreaterEqual(planes.live_bytes(0, 0, 1), 310)
        self.assertEqual(planes.live_bytes(0, 0, 1), B.DISK_O)
        self.assertEqual(B.DISK_O, M.STAGE_PLANES_BPO + M.SCRATCH_BPO)


class PlanChk5TheTier3FinishPhaseBoundsTheWideStages(unittest.TestCase):
    def test_every_32000_px_tier3_measurement(self):
        data = json.loads(FINISH_FIXTURE.read_text(encoding='utf8'))
        wide = [m for m in data['measurements'] if m['tier'] == 'tier3' and m['output_size'][0] >= 32000]
        self.assertGreaterEqual(len(wide), 4)
        for m in wide:
            st = B.stage_choice(tuple(m['input_size']), 2, 0)
            self.assertEqual(tuple(st['output_size']), tuple(m['output_size']), m['source'])
            for mc in B.MACHINE_CLASSES:
                for split in (False, True):
                    fin = B.stage_peaks(st, mc, split, tier='tier3')['phases_up']['finish']
                    self.assertGreaterEqual(fin, M.MARGIN_WAVE3 * m['own_gib'], (m['source'], mc, split))
                    self.assertGreaterEqual(fin, M.finish_commit_gb(B.finish_size(st), tuple(st['padded_size']),
                                                                    B.MACHINE_CLASSES[mc]['band_gb'],
                                                                    B.MACHINE_CLASSES[mc]['processes'], 'tier3'))


class Log:
    def info(self, *a, **k):
        pass

    warn = warning = exception = info


# the rows the committed tables are planned on, at each machine class's default cap, with the sizes proven (planning only)
G1U_ROWS = ((3500, 2188, 4), (2800, 3500, 4), (3500, 2188, 8), (2800, 3500, 6), (4000, 160, 8), (8000, 300, 4))
CAPS = (59.0, 122.2, 45.2)


class G1uEndToEnd(unittest.TestCase):
    def setUp(self):
        self._g = [mock.patch.object(B, 'BXF_TABLE', None, create=True),
                   mock.patch.object(B, 'BXF_TABLE_SOURCE', None, create=True),
                   mock.patch.dict(bxf_probe._STATE, {'local': ''}),
                   mock.patch.dict(B.BANDED_PROVEN_MP, {k: 5000.0 for k in B.BANDED_PROVEN_MP})]
        for g in self._g:
            g.start()
        self.td = tempfile.TemporaryDirectory()
        self.state = Path(self.td.name)

    def tearDown(self):
        self.td.cleanup()
        for g in reversed(self._g):
            g.stop()

    def service_table(self, env):
        """The service's side: G1u.refresh on the engine runtime's environment (its read stubbed), as at start."""
        u = bxf_probe.G1u(SimpleNamespace(state_dir=self.state), Log())
        with mock.patch.object(bxf_probe.G1u, 'environment', return_value=env):
            u.refresh(reason='start', notify=False)
        return u

    def engine_env(self):
        """The environment an engine started now gets (service/workers.Worker._env)."""
        cfg = SimpleNamespace(workers_dir=self.state, state_dir=self.state)
        settings = SimpleNamespace(get=lambda: {'ram_cap_gb': 59.0, 'memory_profile': 'auto'})
        return workers.Worker(0, cfg, settings, Log(), 'fake')._env()

    def planned_stages(self):
        out = []
        for cap in CAPS:
            mc = B.machine_class(cap)
            for w, h, f in G1U_ROWS:
                p = B.plan_banded(w, h, f, cap)
                if p.ok:
                    out += [(mc, st) for st in p.stages]
        return out

    def check(self, env, want_source, local_path):
        u = self.service_table(env)
        self.assertIs(B.BXF_TABLE, u.table)
        self.assertEqual(B.BXF_TABLE_SOURCE, want_source)
        eng = self.engine_env()
        self.assertEqual(eng[g1.LOCAL_TABLE_ENV], local_path)                 # the path the planner's table used
        with mock.patch.dict(os.environ, {g1.LOCAL_TABLE_ENV: eng[g1.LOCAL_TABLE_ENV]}):
            node_table = g1.load(env=env)                                     # the finish node's own load in that engine
        self.assertTrue(node_table.applies)
        stages = self.planned_stages()
        bxf = [(mc, st) for mc, st in stages if st.finish_tier == 'bxf']
        self.assertGreaterEqual(len(bxf), 8)
        self.assertEqual(len(bxf), len(stages))                               # a table applies: no stage at tier 3
        for mc, st in bxf:
            band = B.MACHINE_CLASSES[mc]['band_gb']
            fs, rows = B.finish_size(st), int(st.output_size[1])
            self.assertEqual(list(st.bxf_whole_passes), M.whole_passes_for(node_table, fs, band, output_rows=rows),
                             (mc, st.index, fs))
            for name, _, ops, geom, _ in M.lookups(fs, band, output_rows=rows):
                self.assertEqual(B.BXF_TABLE.banded(*ops, geom=geom), node_table.banded(*ops, geom=geom), (mc, name))
        return u, bxf

    def test_each_committed_table_from_the_planner_to_the_finish_node(self):
        tables = g1.committed_tables()
        self.assertGreaterEqual(len(tables), 3)
        for data in tables:
            env = dict(data['environment'])
            self.check(env, 'committed', '')

    def test_a_local_tables_veto_reaches_both_sides(self):
        data = g1.committed_tables()[2]                                       # the render node class on the worker runtime
        env = dict(data['environment'])
        committed = g1.Table(data, env)
        B.BXF_TABLE, B.BXF_TABLE_SOURCE = committed, 'committed'
        before = {(mc, st.index, tuple(st.output_size)): list(st.bxf_whole_passes) for mc, st in self.planned_stages()}
        # an op that a planned stage looks up and the committed table bands there: the local table measured it differing
        mc0, st0 = self.planned_stages()[0]
        fs, rows = B.finish_size(st0), int(st0.output_size[1])
        looked = [ops for _, kind, ops, geom, _ in M.lookups(fs, B.MACHINE_CLASSES[mc0]['band_gb'], output_rows=rows)
                  if kind == 'local' and committed.banded(*ops, geom=geom)]
        self.assertTrue(looked)
        vetoed = looked[0][0]
        ops = dict(data['ops'])
        local = dict(data, ops=dict(ops, **{vetoed: dict(ops[vetoed], verdict='whole')}))
        path = self.state / 'bxf' / bxf_probe.LOCAL_TABLE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(local), encoding='utf8')
        B.BXF_TABLE = B.BXF_TABLE_SOURCE = None
        u, bxf = self.check(env, 'committed+local', str(path))
        self.assertEqual(B.BXF_TABLE.verdict(vetoed), 'whole')
        after = {(mc, st.index, tuple(st.output_size)): list(st.bxf_whole_passes) for mc, st in bxf}
        self.assertLessEqual(set(after), set(before))                         # a veto never admits more
        gained = [k for k in after if set(after[k]) > set(before[k])]
        refused = set(before) - set(after)                                    # a pass run whole can cost a plan its fit
        self.assertTrue(gained or (mc0, st0.index, tuple(st0.output_size)) in refused)
        self.assertTrue(all(set(after[k]) >= set(before[k]) for k in after))

    def test_no_table_leaves_tier_3_on_both_sides(self):
        env = dict(g1.committed_tables()[2]['environment'], torch='0.0.0+unmeasured')
        u = self.service_table(env)
        self.assertIsNone(B.BXF_TABLE)
        self.assertEqual(self.engine_env()[g1.LOCAL_TABLE_ENV], '')
        self.assertFalse(g1.load(env=env, local='').applies)
        for _, st in self.planned_stages():
            self.assertEqual(st.finish_tier, 'tier3')


class TheRestartContractOnTheMergedPlanner(unittest.TestCase):
    def test_every_pass_after_the_first_starts_in_a_fresh_engine(self):
        with mock.patch.object(B, 'BXF_TABLE', g1.load(env=dict(g1.committed_tables()[1]['environment']), local='')), \
                mock.patch.dict(B.BANDED_PROVEN_MP, {k: 5000.0 for k in B.BANDED_PROVEN_MP}):
            seen = 0
            for cap in CAPS:
                for w, h, f in G1U_ROWS:
                    p = B.plan_banded(w, h, f, cap)
                    if not p.ok or len(p.stages) < 2:
                        continue
                    seen += 1
                    d = p.to_dict()
                    self.assertFalse(d['stages'][0].get('fresh_worker', False), (w, h, f, cap))
                    for st in d['stages'][1:]:
                        self.assertTrue(st.get('fresh_worker'), (w, h, f, cap, st['index']))
            self.assertGreaterEqual(seen, 3)


if __name__ == '__main__':
    unittest.main()
