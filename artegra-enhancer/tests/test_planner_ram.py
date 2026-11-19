"""5.0.1: the planner fits each stage to the memory cap before it refuses an image (engine/planner.py), its estimate is an
upper bound of measured peaks, and every plan 5.0.0-beta.1 could run keeps its stages, so its graph and pixels.

Sizes only: no test reads this computer's RAM (tests/conftest.py pins it). The Beta's planner is frozen in
tests/fixtures/beta_planner_5_0_0b1.py (engine/planner.py at the tag artegra-enhancer-v5.0.0-beta.1)."""
import importlib.util
import os
import unittest
from pathlib import Path
from unittest import mock

from engine import controls, planner
from service import engine_options, memory_policy, settings
from service.media import LIGHTER_FOR_MEMORY, plan_text, ram_refusal
from service.util import same_plan

PC_RAM_GIB = 61.56        # a 64 GB PC as Windows reports it (one RTX 5090)
WS_RAM_GIB = 127.37       # a 128 GB workstation (two RTX 5090s)
PC_CAP, WS_CAP = settings.default_ram_cap_gb(PC_RAM_GIB), settings.default_ram_cap_gb(WS_RAM_GIB)

_spec = importlib.util.spec_from_file_location('beta_planner', Path(__file__).parent / 'fixtures' / 'beta_planner_5_0_0b1.py')
beta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(beta)

GRID = [(w, h) for w in (512, 777, 1000, 1280, 1600, 2048, 2188, 2800, 3000, 3500, 3840, 4096, 5000, 6000)
        for h in (512, 777, 1600, 2188, 2400, 2800, 3500, 4000)]


def beta_cap(total):
    """5.0.0-beta.1's default cap."""
    return settings.beta_default_ram_cap_gb(total)


def stages(p):
    return [(s.factor, s.supersample, tuple(s.padded_size), tuple(s.render_size), tuple(s.output_size)) for s in p.stages]


def out_mp(stage):
    return stage.output_size[0] * stage.output_size[1] / 1e6


def bolt_info():
    with mock.patch.dict(os.environ, {'CU_FAST': '1'}):
        return engine_options.fast_info()


class TheBetaPlanIsKept(unittest.TestCase):
    def test_without_a_cap_every_plan_is_the_betas(self):
        for w, h in GRID:
            for f in controls.SCALES:
                new, old = planner.plan(w, h, f), beta.plan(w, h, f)
                self.assertEqual((new.ok, stages(new), new.reason), (old.ok, stages(old), old.reason), (w, h, f))
                self.assertFalse(new.ram_limited, (w, h, f))

    def test_every_plan_the_beta_could_run_keeps_its_stages(self):
        """What the Beta ran (planned within its default cap) plans the same stages at the new default cap, so the same
        graph and pixels, and is never refused or lightened."""
        ran = {}
        for total in (47.7, PC_RAM_GIB, WS_RAM_GIB):      # the Beta ran nothing on 16 or 32 GB
            old_cap, new_cap = beta_cap(total), settings.default_ram_cap_gb(total)
            self.assertGreaterEqual(new_cap, old_cap)
            ran[total] = 0
            for w, h in GRID:
                for f in controls.SCALES:
                    old = beta.plan(w, h, f)
                    if not old.ok or old.peak_ram_gb > old_cap:
                        continue
                    ran[total] += 1
                    new = planner.plan(w, h, f, ram_cap_gb=new_cap)
                    self.assertEqual(stages(new), stages(old), (total, w, h, f))
                    self.assertFalse(new.ram_limited, (total, w, h, f))
                    self.assertIsNone(ram_refusal(new, new_cap), (total, w, h, f))
        self.assertTrue(all(n > 0 for n in ran.values()), ran)  # plans were compared on every machine size
        self.assertGreater(sum(ran.values()), 200)

    def test_the_estimate_is_never_above_the_betas(self):
        for w, h in GRID:
            for f in controls.SCALES:
                for s in planner.plan(w, h, f).stages:
                    old = 30 + 0.15 * s.render_mp + 0.43 * out_mp(s)
                    self.assertLessEqual(planner.stage_peak(s), old + 1e-9, (w, h, f))


class StepDown(unittest.TestCase):
    def peaks(self, w, h, f):
        """The plan's first stage at each supersample, by planning with the render cap just above each render size."""
        out = {}
        for s in planner.SUPERSAMPLES:
            p = planner.plan(w, h, f, render_cap=w * h * (f * float(s)) ** 2 / 1e6 + 0.5)
            st = p.stages[0]
            out[float(s)] = round(planner.stage_peak(st), 1)
        return out

    def test_the_fullest_supersample_that_fits_is_taken(self):
        pk = self.peaks(3500, 2188, 2)
        self.assertGreater(pk[2.0], pk[1.5])
        self.assertGreater(pk[1.5], pk[1.0])
        for cap, want in ((pk[2.0], 2.0), (pk[2.0] - 0.1, 1.5), (pk[1.5], 1.5), (pk[1.5] - 0.1, 1.0), (pk[1.0], 1.0)):
            p = planner.plan(3500, 2188, 2, ram_cap_gb=cap)
            self.assertEqual(p.stages[0].supersample, want, cap)
            self.assertEqual(p.ram_limited, want < 2.0, cap)
            self.assertIsNone(ram_refusal(p, cap), cap)
            self.assertEqual(p.output_size, (7000, 4376))         # only the supersample changes, never the output

    def test_when_nothing_fits_the_refusal_names_the_least_memory(self):
        pk = self.peaks(3500, 2188, 2)
        p = planner.plan(3500, 2188, 2, ram_cap_gb=pk[1.0] - 0.1)
        self.assertTrue(p.ok)
        self.assertEqual(p.stages[0].supersample, 1.0)
        self.assertEqual(p.peak_ram_gb, pk[1.0])
        self.assertIn(f'about {pk[1.0]:.0f} GB', ram_refusal(p, pk[1.0] - 0.1))

    def test_at_any_cap_a_plan_is_refused_only_when_its_lightest_supersample_does_not_fit(self):
        """The planner and the memory check agree to the rounding: a chosen plan is never refused while a lighter one fits,
        and a plan whose full version passes the check is never lightened."""
        checked = 0
        for w, h in GRID + [(2289, 3079), (1815, 3883), (1800, 3917), (1500, 1070), (861, 8183)]:
            for f in controls.SCALES:
                full = planner.plan(w, h, f)
                if not full.ok:
                    continue
                for cap in sorted({full.peak_ram_gb, round(full.peak_ram_gb - 0.1, 1), round(full.peak_ram_gb + 0.1, 1),
                                   40.0, 50.0, PC_CAP, WS_CAP}):
                    p = planner.plan(w, h, f, ram_cap_gb=cap)
                    checked += 1
                    if full.peak_ram_gb <= cap:
                        self.assertEqual(stages(p), stages(full), (w, h, f, cap))
                        self.assertFalse(p.ram_limited, (w, h, f, cap))
                    if ram_refusal(p, cap):
                        lightest = planner.plan(w, h, f, ram_cap_gb=0.1)
                        self.assertGreater(lightest.peak_ram_gb, cap, (w, h, f, cap))
                        self.assertEqual(p.peak_ram_gb, lightest.peak_ram_gb, (w, h, f, cap))   # it names the least
        self.assertGreater(checked, 1000)

    def test_the_plan_says_it_was_lightened_for_memory(self):
        pk = self.peaks(3500, 2188, 2)
        p = planner.plan(3500, 2188, 2, ram_cap_gb=pk[2.0] - 0.1)
        self.assertEqual(plan_text(p, pk[2.0] - 0.1)['notes'], [LIGHTER_FOR_MEMORY])
        self.assertEqual(plan_text(planner.plan(3500, 2188, 2), 1e9)['notes'], [])
        self.assertTrue(p.to_dict()['ram_limited'])

    def test_a_one_pass_plan_never_mentions_later_passes(self):
        p = planner.plan(3072, 3072, 2)                        # over the render cap at supersample 2: one pass at 1.5
        self.assertEqual(p.stages[0].supersample, 1.5)
        self.assertEqual(plan_text(p, 1e9)['notes'], ['Uses a lighter setting at this size.'])
        q = planner.plan(1280, 1600, 8)
        if any(s.supersample < 2 for s in q.stages) and not q.ram_limited:
            self.assertEqual(plan_text(q, 1e9)['notes'], ['Later passes use a lighter setting at this size.'])


class BoltAndMemory(unittest.TestCase):
    def reasons(self, w, h, cap):
        """(the tray's reason, the queue's reason) for Bolt 2x of w x h at this cap, None when Bolt takes it."""
        p = planner.plan(w, h, 2, ram_cap_gb=cap)
        _, eff = controls.resolve({'mode': 'fast'})
        info = bolt_info()
        tray = engine_options.finish_info(p.minutes, fast_available=True, plan=p.to_dict())['fast_refusal']
        queue = engine_options.fast_refusal(eff, info, p.to_dict())
        return (tray or {}).get('reason'), (queue or (None,))[0]

    def test_the_tray_and_start_give_the_same_reason(self):
        for w, h in GRID:
            for cap in (20.0, 30.0, 45.0, PC_CAP, WS_CAP):
                tray, queue = self.reasons(w, h, cap)
                self.assertEqual(tray, queue, (w, h, cap))

    def test_memory_only_when_a_bigger_computer_could_run_it_in_bolt(self):
        pk = StepDown().peaks(3500, 2188, 2)
        self.assertEqual(self.reasons(3500, 2188, pk[2.0] - 0.1), ('memory', 'memory'))
        self.assertEqual(self.reasons(3500, 2188, pk[2.0]), (None, None))
        p = planner.plan(3500, 2188, 2, ram_cap_gb=pk[2.0] - 0.1)
        _, eff = controls.resolve({'mode': 'fast'})
        text = engine_options.fast_refusal(eff, bolt_info(), p.to_dict())[1]
        self.assertIn('more memory', text)
        self.assertIn('Redux', text)

    def test_an_image_bolt_cannot_take_anywhere_says_size_at_every_cap(self):
        # 3072 x 3072 (9.4 MP) is over Bolt's size whatever the memory: its full plan is already lighter than 2
        self.assertLess(planner.plan(3072, 3072, 2).stages[0].supersample, 2.0)
        for cap in (20.0, 40.0, 45.0, PC_CAP, WS_CAP, None):
            self.assertEqual(self.reasons(3072, 3072, cap), ('size', 'size'), cap)
        for cap in (20.0, 45.0, PC_CAP, None):
            self.assertEqual(self.reasons(2800, 3500, cap), ('size', 'size'), cap)

    def test_when_nothing_fits_bolt_does_not_send_the_person_to_redux(self):
        pk = StepDown().peaks(3500, 2188, 2)
        cap = pk[1.0] - 0.1                                    # not even the lightest setting fits
        p = planner.plan(3500, 2188, 2, ram_cap_gb=cap)
        self.assertIsNotNone(ram_refusal(p, cap))
        self.assertEqual(self.reasons(3500, 2188, cap), ('memory_all', 'memory_all'))
        _, eff = controls.resolve({'mode': 'fast'})
        text = engine_options.fast_refusal(eff, bolt_info(), p.to_dict())[1]
        self.assertNotIn('Redux', text)

    def test_the_start_time_check_still_sees_a_lightened_plan_as_not_bolts(self):
        pk = StepDown().peaks(3500, 2188, 2)
        p = planner.plan(3500, 2188, 2, ram_cap_gb=pk[2.0] - 0.1)
        self.assertEqual(engine_options.fast_plan_refusal(p.to_dict()), 'size')


class PlansStoredByTheBeta(unittest.TestCase):
    def test_a_beta_plan_matches_the_same_plan_made_now(self):
        for w, h, f in ((1000, 1000, 4), (2048, 2048, 2), (1280, 1600, 2), (3500, 2188, 2)):
            old = beta.plan(w, h, f).to_dict()                 # no ram_limited, the Beta's estimate
            new = planner.plan(w, h, f, ram_cap_gb=1e9).to_dict()
            self.assertNotIn('ram_limited', old)
            self.assertTrue(same_plan(old, new), (w, h, f))

    def test_a_different_supersample_is_a_different_plan(self):
        a = planner.plan(3500, 2188, 2).to_dict()
        b = planner.plan(3500, 2188, 2, ram_cap_gb=a['peak_ram_gb'] - 0.1).to_dict()
        self.assertFalse(same_plan(a, b))


PAGEFILE = 'C' + ':' + '\\pagefile.sys'     # the PagingFiles registry form, built so no file names a drive path


class StartingAnImage(unittest.TestCase):
    def test_a_system_managed_page_file_counts_its_room_to_grow(self):
        grow = memory_policy.pagefile_growth_gb
        self.assertAlmostEqual(grow(61.56, 65.56, entries=['?:\\pagefile.sys'], free_gb=500.0, volume_gb=4000.0),
                               3 * 61.56 - 4.0)
        self.assertAlmostEqual(grow(61.56, 65.56, entries=[PAGEFILE + ' 0 0'], free_gb=20.0, volume_gb=4000.0), 19.0)
        # Windows also keeps a system-managed page file under an eighth of its drive
        self.assertAlmostEqual(grow(61.56, 65.56, entries=[PAGEFILE + ' 0 0'], free_gb=400.0, volume_gb=500.0), 62.5 - 4.0)
        self.assertAlmostEqual(grow(61.56, 65.56, entries=[PAGEFILE + ' 4096 16384'], free_gb=500.0), 12.0)
        self.assertEqual(grow(61.56, 61.56, entries=[], free_gb=500.0), 0.0)

    def test_a_plan_at_the_cap_starts_on_a_64_gb_pc_with_a_small_system_managed_page_file(self):
        memory = {'avail_phys_gb': 50.0, 'commit_available_gb': 50.0, 'commit_growth_gb': 150.0}
        self.assertIsNone(memory_policy.admission_problem(PC_CAP, [], PC_CAP, memory))
        fixed = dict(memory, commit_growth_gb=0.0)
        self.assertIn('commit', memory_policy.admission_problem(PC_CAP, [], PC_CAP, fixed))

    def test_an_idle_engine_on_another_card_is_stopped_only_when_its_memory_is_needed(self):
        a, b = object(), object()
        self.assertEqual(memory_policy.idle_engines_to_stop(90.0, [], WS_CAP, [(a, 30.0), (b, 5.0)]), [a, b])
        self.assertEqual(memory_policy.idle_engines_to_stop(50.0, [], WS_CAP, [(a, 30.0)]), [])
        self.assertEqual(memory_policy.idle_engines_to_stop(80.0, [], WS_CAP, []), [])

    def test_a_plan_at_the_cap_leaves_windows_room_on_a_64_gb_pc(self):
        # a plan at the cap measures at most cap / margin, so at least 4 GiB of the RAM stays for Windows and the app
        self.assertGreaterEqual(PC_RAM_GIB - PC_CAP / planner.PEAK_MARGIN, 4.0)

    def test_a_second_image_waits_in_plain_words(self):
        memory = {'avail_phys_gb': 100.0, 'commit_available_gb': 200.0, 'commit_growth_gb': 0.0}
        why = memory_policy.admission_problem(70.0, [60.0], WS_CAP, memory)
        self.assertEqual(why, 'Waiting for memory: another image is using the memory this one needs. It starts when '
                              'that one finishes.')


class TheSuitesRamFigure(unittest.TestCase):
    def test_only_a_positive_number_replaces_the_computers_figure(self):
        for bad in ('', 'abc', '0', '-1', 'inf', 'nan'):
            with mock.patch.dict(os.environ, {settings.TEST_RAM_ENV: bad}):
                got = settings.machine_ram_gb()
                self.assertTrue(got is None or 0 < got < float('inf'), (bad, got))
                self.assertNotEqual(got, 61.56)
        with mock.patch.dict(os.environ, {settings.TEST_RAM_ENV: '61.56'}):
            self.assertEqual(settings.machine_ram_gb(), 61.56)


class UpgradingFromTheBeta(unittest.TestCase):
    def settings(self, tmp, saved, meta=None):
        state = Path(tmp)
        (state / 'settings.json').write_text(__import__('json').dumps({'ram_cap_gb': saved}), encoding='utf8')
        if meta is not None:
            (state / 'settings-meta.json').write_text(__import__('json').dumps(meta), encoding='utf8')
        log = mock.Mock()
        return settings.Settings(state / 'settings.json', state, log, total_ram_gb=PC_RAM_GIB)

    def test_the_betas_default_becomes_the_new_default_even_without_the_meta_file(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            s = self.settings(tmp, beta_cap(PC_RAM_GIB))
            self.assertEqual(s.get()['ram_cap_gb'], PC_CAP)

    def test_a_value_set_by_hand_stays(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self.settings(tmp, 66).get()['ram_cap_gb'], 66)


class ReleaseTargets(unittest.TestCase):
    """Max's cases (19 Nov 2026), at the default cap of a 64 GB PC with one RTX 5090 and of the 128 GB workstation."""

    def test_3500_x_2188_at_2x_runs_in_redux_and_bolt_at_full_quality(self):
        for cap in (PC_CAP, WS_CAP):
            for w, h in ((3500, 2188), (2188, 3500)):
                p = planner.plan(w, h, 2, ram_cap_gb=cap)
                self.assertEqual([s.supersample for s in p.stages], [2.0], (w, h, cap))
                self.assertFalse(p.ram_limited)
                self.assertIsNone(ram_refusal(p, cap), (w, h, cap))
                _, eff = controls.resolve({'mode': 'fast'})
                self.assertIsNone(engine_options.fast_refusal(eff, bolt_info(), p.to_dict()), (w, h, cap))

    def test_2800_x_3500_at_2x_runs_in_redux_as_the_beta_planned_it(self):
        for cap in (PC_CAP, WS_CAP):
            p = planner.plan(2800, 3500, 2, ram_cap_gb=cap)
            self.assertEqual([s.supersample for s in p.stages], [1.5], cap)
            self.assertIsNone(ram_refusal(p, cap), cap)

    def test_1280_x_1600_at_4x_runs_in_redux_at_full_quality(self):
        for cap in (PC_CAP, WS_CAP):
            p = planner.plan(1280, 1600, 4, ram_cap_gb=cap)
            self.assertEqual([s.supersample for s in p.stages], [2.0, 2.0], cap)
            self.assertIsNone(ram_refusal(p, cap), cap)

    def test_the_largest_jobs_need_the_workstation(self):
        for w, h, f in ((3500, 2188, 4), (1280, 1600, 6), (1280, 1600, 8)):
            pc, ws = planner.plan(w, h, f, ram_cap_gb=PC_CAP), planner.plan(w, h, f, ram_cap_gb=WS_CAP)
            self.assertIn('GB of memory', ram_refusal(pc, PC_CAP), (w, h, f))
            self.assertIsNone(ram_refusal(ws, WS_CAP), (w, h, f))


if __name__ == '__main__':
    unittest.main()
