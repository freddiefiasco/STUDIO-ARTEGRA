"""5.0.2 build wave 3: what the merge of the five packages applied and relies on, checked in process (sizes only).

- The finish package's bound raises (its adds.bound_raises, for the merge role): the banded exact finish's scratch folder
  peaked at 297.5 B per finish-plane pixel in every wave-3 run (engine/bxf/memory.SCRATCH_BPO 298, with the stage's own
  init, creative, structure and output planes, STAGE_PLANES_BPO 12), so the planner's disk figure (banded_plan.DISK_O), the
  service's disk check (engine/planes.live_bytes and disk_need) and the physical-memory rule's finish phase
  (service/banded_runner.PHASE_PLANES['finish']) count 310 B per finish-plane pixel, over the stage's finish plane
  (banded_plan.finish_px: the padded output, never fewer pixels than the output).
- plan-chk-5 (the plan package's later item for the merge role): the planner's tier-3 finish phase bounds every tier-3
  measurement at a 32,000 px wide stage (tests/fixtures/bxf_finish_memory.json) with the finish module's margin."""
import json
import unittest
from fractions import Fraction
from pathlib import Path

from engine import banded_plan as B
from engine import planes, planner
from engine.bxf import memory as M
from service import banded_runner as BR

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
        self.assertGreaterEqual(BR.PHASE_PLANES['finish'][3], self.PER_O)
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

    def test_the_physical_rules_finish_phase_counts_it(self):
        for row, st in stages():
            I, F = px(st['padded_size']), B.finish_px(st)
            for masks in (0, 5):
                got = BR.stage_planes_bytes(st, 'finish', masks)
                self.assertGreaterEqual(got, self.PER_O * F + 3 * I + BR.MASK_BPI * I * masks, (row, masks))

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


if __name__ == '__main__':
    unittest.main()
