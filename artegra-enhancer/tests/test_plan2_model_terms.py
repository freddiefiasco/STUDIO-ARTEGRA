"""The memory and time model's missing terms (engine/banded_plan.py; build wave 2, merge report items 13, 17 and 18). Each term
is counted, from the code or a measurement, as an upper bound until R2 fits it:
- memory: lf.dm's whole run on narrow stages (12 B per finish pixel below the conv frontier), the RGBA viewer copies in the
  service term (views-docs V2: about twice the RGB copy, two at once plus the finish's proxies), CUCannyPlane's private
  row-band working set (gpu-nodes G4); the decoder's registered bound is kept above the measured 72,000 B per render column
  + 0.1 GiB;
- time: the spot fork's per-window host crop uploads, CUSam3DetectLean's float32 view written and read per SAM term, and the
  plane band I/O;
- no admitted Large-image plan is more than 100 times taller than wide (Pillow 12.3.0 runs its vertical pass first past
  that; engine/lanczos_bands.py does not);
- no term lowers a figure: with the terms every phase is at least the design's.
Sizes only."""
import json
import unittest
from pathlib import Path
from unittest import mock

from engine import banded_plan as B
from engine import controls, planner

ROOT = Path(__file__).resolve().parents[1]
PROVEN = {k: 10_000.0 for k in B.BANDED_PROVEN_MP}
CAPS = {'pc64': 59.0, 'ws128': 122.2, 'pc48': 45.2}
GIB = float(2 ** 30)
ROWS = [(3500, 2188, 4), (3500, 2188, 6), (3500, 2188, 8), (2800, 3500, 4), (2800, 3500, 6), (2800, 3500, 8),
        (4000, 2500, 8), (4000, 4000, 8), (5333, 3333, 6), (1280, 1600, 4), (2048, 2048, 2), (64, 3000, 2), (560, 3457, 2)]


def raw_stages(w, h, factor):
    cur, out = (w, h), []
    for i, f in enumerate(planner.STAGE_FACTORS[factor]):
        st = B.stage_choice(cur, f, i)
        out.append(st)
        cur = st['output_size']
    return out


def mp(size):
    return size[0] * size[1] / 1e6


def finish_size(st):
    return int(st['padded_size'][0] * st['factor']), int(st['padded_size'][1] * st['factor'])


class MemoryTerms(unittest.TestCase):
    def test_lf_dm_whole_on_narrow_stages(self):
        narrow = B.stage_choice((560, 3457), 2, 0)              # a 1,120 px stage: lf.dm ran whole there (bxf G2 n5)
        wide = B.stage_choice((3500, 2188), 2, 0)               # 7,000 px
        wider = B.stage_choice((4570, 2000), 2, 0)              # 9,140 px: banded (bxf G2 at 18-73 MP and at 32,000 px)
        self.assertEqual(B.lfdm_gb(narrow), B.LFDM_BPO * B.G * mp(finish_size(narrow)))
        self.assertGreater(B.lfdm_gb(wide), 0.0)                 # below LFDM_NARROW_PX: counted (the runtime's frontier may move)
        self.assertEqual(B.lfdm_gb(wider), 0.0)
        self.assertEqual(B.LFDM_BPO, 12)
        self.assertGreaterEqual(B.LFDM_NARROW_PX, 2 * 3271)      # twice the widest conv frontier G1 measured (bxf-g1-2)
        for st in (narrow, wide):
            on = B.stage_peaks(st, 'pc64', False, tier='bxf')['phases_up']
            off = B.stage_peaks(st, 'pc64', False, tier='bxf', terms=False)['phases_up']
            self.assertAlmostEqual(on['finish'] - off['finish'], B.lfdm_gb(st) + B.service_gb(st) - B.SERVICE_GB)

    def test_the_rgba_viewer_copies_are_in_the_service_term(self):
        rgb_mib, rgba_mib = 299, 620                             # V2: one copy of a 32,000 px wide result, measured
        self.assertGreaterEqual(B.VIEW_COPY_BPC * 32000, rgba_mib * 2 ** 20)
        self.assertGreaterEqual(B.VIEW_COPY_BPC * 32000, 2 * rgb_mib * 2 ** 20)
        self.assertEqual(B.VIEW_COPIES, 3)                       # SizedPlaneCopies' two at once, and the finish's proxies
        for w, h, f in ROWS:
            for st in raw_stages(w, h, f):
                want = B.SERVICE_GB + B.VIEW_COPIES * B.VIEW_COPY_BPC * st['output_size'][0] / GIB
                self.assertAlmostEqual(B.service_gb(st), want)
                pk = B.stage_peaks(st, 'ws128', False, tier='bxf')
                off = B.stage_peaks(st, 'ws128', False, tier='bxf', terms=False)
                for ph in ('sampling', 'decode'):
                    self.assertAlmostEqual(pk['phases_up'][ph] - off['phases_up'][ph], want - B.SERVICE_GB)

    def test_cannys_private_row_band_working_set(self):
        # gpu-nodes check G4: +1.85 / +1.93 / +1.95 GiB peak commit at a 32,000 px u8 canvas, 2,100 / 4,200 / 8,400 rows (CPU)
        for rows, got in ((2100, 1.85), (4200, 1.93), (8400, 1.95)):
            st = {'padded_size': (16000, rows // 2), 'render_size': (32000, rows), 'output_size': (32000, rows), 'factor': 2.0,
                  'supersample': 1.0}
            self.assertGreaterEqual(B.canny_gb(st), got, rows)
            self.assertLess(B.canny_gb(st), 1.5 * got)
        f32 = {'padded_size': (4000, 1000), 'render_size': (16000, 4000), 'output_size': (8000, 2000), 'factor': 2.0,
               'supersample': 2.0}                               # k = 4: the canvas is float32
        u8 = dict(f32, supersample=1.0, padded_size=(8000, 2000), render_size=(16000, 4000))
        self.assertGreaterEqual(B.canny_gb(f32) - B.canny_gb(u8), (2048 + 16) * 16000 * 9 / GIB - 1e-9)
        for w, h, f in ROWS:
            for st in raw_stages(w, h, f):
                on = B.stage_peaks(st, 'pc64', False, tier='bxf')['phases_up']['P0']
                off = B.stage_peaks(st, 'pc64', False, tier='bxf', terms=False)['phases_up']['P0']
                self.assertAlmostEqual(on - off, B.canny_gb(st) + B.service_gb(st) - B.SERVICE_GB)

    def test_the_decoder_bound_is_kept_above_its_measurement(self):
        """CUDecodePlane measured 72,000 B per render column + 0.1 GiB (torch 2.9.1 CPU); the registered DEC_ROWS x DEC_BPX
        (90,624 B per column) + 0.5 GiB stays: R2 measures the runtime's allocator."""
        self.assertEqual((B.DEC_ROWS, B.DEC_BPX), (1088 + 576 + 2112, 24))
        for w in (1024, 7000, 14000, 28000, 32000):
            self.assertGreaterEqual(B.DEC_ROWS * w * B.DEC_BPX / GIB + 0.5, 72_000 * w / GIB + 0.1)
        self.assertGreaterEqual(B.DEC_ROWS * B.DEC_BPX / 72_000, 1.25)

    def test_no_term_lowers_a_figure(self):
        for w, h, f in ROWS:
            for mc in CAPS:
                for st in raw_stages(w, h, f):
                    for split in (False, True):
                        for tier in ('bxf', 'tier3'):
                            on = B.stage_peaks(st, mc, split, tier=tier)
                            off = B.stage_peaks(st, mc, split, tier=tier, terms=False)
                            for ph, v in off['phases_up'].items():
                                self.assertGreaterEqual(on['phases_up'][ph], v, (w, h, f, mc, split, tier, ph))
                            self.assertGreaterEqual(on['exp'][0], off['exp'][0])
                            self.assertGreaterEqual(on['up'][0], off['up'][0])


class TimeTerms(unittest.TestCase):
    def test_the_new_terms_are_added_as_upper_bounds(self):
        for w, h, f in ROWS:
            for st in raw_stages(w, h, f):
                I, R = mp(st['padded_size']), mp(st['render_size'])
                crop = B.CROP_BPR * R * 1e6 / (B.HOST_CROP_GBPS * 1e9)
                sam = B.SAM_TERMS_MAX * B.SAM_VIEW_BPI * I * 1e6 / (B.PLANE_IO_GBPS * 1e9)
                io = B.PLANE_IO_PASSES * B.banded_disk_gb(st) / B.PLANE_IO_GBPS
                for split in (False, True):
                    base = B.banded_minutes(st, split, terms=False)
                    self.assertAlmostEqual(B.banded_minutes(st, split), base + (crop + sam + io) / 60.0)
                    self.assertGreater(crop, 0)
                    self.assertGreater(sam, 0)
                    self.assertGreater(io, 0)

    def test_the_base_formula_is_kept(self):
        st = raw_stages(3500, 2188, 8)[-1]
        I, R, O = mp(st['padded_size']), mp(st['render_size']), mp(st['output_size'])
        secs = B.T_P0_I * I + (B.T_SAMPLE_R + B.T_DECODE_R) * R + B.T_FINISH_O * O
        self.assertAlmostEqual(B.banded_minutes(st, True, terms=False), secs / 60 * B.IO_BUDGET + B.SPLIT_MINUTES)

    def test_the_crop_term_counts_every_window_crop_of_both_samplers(self):
        steps = controls.stage_params(controls.resolve({})[0], 0)['steps']
        self.assertEqual(steps, B.STEPS)
        # per window and evaluation (cn_plane.BoundHint.crop_array, window_tensor): KS1 copies the tile hint's crop out of
        # its plane (f32, 12 B/px); KS2 the tile hint's (12 B/px) and the edges' (u8 1 B, as float32 4 B, repeated to 3
        # channels 12 B); with the windows' overlap and up to two evaluations per step (CFG's group and PAG's)
        self.assertEqual(B.CROP_BPR, (12 + 12 + 17) * B.CROP_OVERLAP * B.CROP_EVALS * B.STEPS)
        self.assertGreaterEqual(B.CROP_OVERLAP, 1.0)
        self.assertGreaterEqual(B.CROP_EVALS, 2)

    def test_the_sam_view_is_written_and_read_per_term(self):
        self.assertEqual(B.SAM_TERMS_MAX, len(controls.PROTECT_ORDER) + len(controls.RELEASE_VEGETATION))
        self.assertEqual(B.SAM_VIEW_BPI, 24)
        st = {'padded_size': (16000, 16000), 'render_size': (32000, 32000), 'output_size': (32000, 32000), 'factor': 2.0,
              'supersample': 1.0}                                # I = 256 MP: about 28 GB written, as much read
        self.assertGreaterEqual(B.SAM_TERMS_MAX * B.SAM_VIEW_BPI * 256e6, 2 * 27.6e9)


class TallImages(unittest.TestCase):
    def test_no_admitted_plan_is_more_than_100_times_taller_than_wide(self):
        sides = (64, 100, 128, 300, 512, 1000, 2188, 3500, 4000, 6400, 8000, 16000)
        n = refused_tall = 0
        with mock.patch.dict(B.BANDED_PROVEN_MP, PROVEN), mock.patch.object(B, 'BXF_AVAILABLE', True):
            for w in sides:
                for h in sides:
                    for f in (2, 4, 6, 8):
                        for cap in CAPS.values():
                            plans = [B.plan_banded(w, h, f, cap)]
                            c = planner.plan_501(w, h, f, ram_cap_gb=cap)          # the classic plan, for the forced path
                            if c.ok and c.peak_ram_gb <= cap:
                                plans.append(B.plan_forced(c, cap))
                            for p in plans:
                                if not p.ok:
                                    refused_tall += 'too tall' in p.reason
                                    continue
                                n += 1
                                for s in p.stages:
                                    for size in (s.input_size, s.padded_size, s.render_size, s.output_size):
                                        self.assertLessEqual(size[1], B.TALL_MAX * size[0], (w, h, f, cap, s.index))
        self.assertGreater(n, 500)
        self.assertGreater(refused_tall, 0)

    def test_a_tall_narrow_image_is_refused_in_plain_words(self):
        with mock.patch.dict(B.BANDED_PROVEN_MP, PROVEN), mock.patch.object(B, 'BXF_AVAILABLE', True):
            p = B.plan_banded(64, 8000, 2, 122.2)                  # 128 x 16,000 px: 125 times taller than wide
            self.assertFalse(p.ok)
            self.assertIn('too tall', p.reason)
            self.assertIn('128 × 16,000 px', p.reason)
            self.assertTrue(B.plan_banded(8000, 64, 2, 122.2).ok)  # wide and short is fine: Pillow's order is horizontal first
            c = planner.plan(64, 8000, 2, ram_cap_gb=122.2)
            self.assertTrue(c.ok)
            self.assertEqual(c.engine, 'classic')                   # the Classic engine keeps it, as 5.0.1
            self.assertFalse(B.plan_forced(c, 122.2).ok)


class PinnedFigures(unittest.TestCase):
    """The figures the model gives the target rows now (tests/fixtures/plan2_sizing.json), for the merge role and the docs:
    every value is the upper bound at that size, and the ships verdict follows from it."""

    def test_the_pinned_figures(self):
        rows = json.loads((ROOT / 'tests' / 'fixtures' / 'plan2_sizing.json').read_text(encoding='utf8'))['rows']
        self.assertGreater(len(rows), 30)
        with mock.patch.dict(B.BANDED_PROVEN_MP, PROVEN):
            for r in rows:
                with mock.patch.object(B, 'BXF_AVAILABLE', r['tier'] == 'bxf'), \
                        mock.patch.object(B, 'BROWNIAN_CAPPED', r['brownian_cache'] == 8):
                    p = B.plan_banded(r['w'], r['h'], r['factor'], r['cap'])
                    key = (r['w'], r['h'], r['factor'], r['cap'], r['tier'], r['brownian_cache'])
                    self.assertEqual(p.ok, r['ships'], (key, p.reason))
                    st = raw_stages(r['w'], r['h'], r['factor'])
                    mc = B.machine_class(r['cap'])
                    splits = [B.split_needed(s, mc, r['cap']) for s in st]
                    pk = [B.stage_peaks(s, mc, sp) for s, sp in zip(st, splits)]
                    u = max(pk, key=lambda d: d['up'][0])
                    e = max(pk, key=lambda d: d['exp'][0])
                    self.assertEqual(''.join('s' if x else '-' for x in splits), r['split'], key)
                    self.assertEqual((round(u['up'][0], 1), u['up'][1]), (r['upper_gb'], r['upper_phase']), key)
                    self.assertEqual((round(e['exp'][0], 1), e['exp'][1]), (r['expected_gb'], r['expected_phase']), key)
                    if p.ok:
                        self.assertEqual(p.peak_ram_gb, round(B.MARGIN * r['upper_gb'], 1), key)


if __name__ == '__main__':
    unittest.main()
