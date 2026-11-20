"""Memory accounting and honest times of the Large-image engine (engine design ENGINE-DESIGN.md 2.3, 2.10, 6; T15), and
eng:sam-501's open issue: a Large-image plan's minutes are wall minutes, so they are said as they are, while every classic
time stays 5.0.1's (with 5.0.2's honest minutes). In-process: Runner with SimpleNamespace stubs. Sizes only."""
import unittest
from types import SimpleNamespace
from unittest import mock

from engine import banded_plan, controls, planner
from service import banded_runner, engine_options, plane_io
from service.media import plan_dict, said_minutes
from service.runner import Runner

SIZES = [(w, h) for w in (512, 1280, 2188, 3500, 6000) for h in (512, 1600, 2800, 3500)]
GIB = float(1 << 30)


def banded_plan_of(w=2048, h=2048, f=2, cap=59.0):
    return banded_plan.plan_forced(planner.plan(w, h, f, ram_cap_gb=cap), cap)


class ModeFactor(unittest.TestCase):
    def test_classic_times_are_unchanged(self):
        for w, h in SIZES:
            for f in controls.SCALES:
                p = planner.plan(w, h, f, ram_cap_gb=122.2)
                if not p.ok:
                    continue
                io = engine_options.plan_io_share(p)
                for stack in (True, False):
                    run = engine_options.run_info('standard', match_earlier=not stack, plan=p)
                    self.assertEqual(run['factor'], engine_options.eta_factor(stack, 1, 'standard', io_share=io))
                    fin = engine_options.finish_info(p.minutes, match_earlier=not stack, plan=p)
                    self.assertEqual(fin['standard']['factor'], engine_options.eta_factor(stack))
                    self.assertEqual(fin['standard']['minutes'], round(p.minutes * engine_options.eta_factor(stack), 1))
                    two = engine_options.finish_info(p.minutes, match_earlier=not stack, plan=p, cards={'standard': 2})
                    self.assertEqual(two['single']['standard']['factor'], engine_options.eta_factor(stack, 2, io_share=io))
        self.assertEqual(engine_options.ETA_STACK, 0.70)

    def test_a_large_image_plan_says_its_wall_minutes(self):
        p = banded_plan_of()
        self.assertEqual(p.engine, 'banded')
        self.assertEqual(p.minutes, round(sum(s.minutes for s in p.stages), 1))
        for stack in (True, False):
            run = engine_options.run_info('standard', match_earlier=not stack, plan=p)
            self.assertEqual(run['factor'], 1.0)
            self.assertEqual(engine_options.run_info('standard', plan=p.to_dict(), split=True, cards=2)['factor'], 1.0)
            fin = engine_options.finish_info(p.minutes, match_earlier=not stack, plan=p, cards={'standard': 2},
                                             faster_available=True)
            self.assertEqual(fin['standard'], {'minutes': p.minutes, 'factor': 1.0})
            self.assertEqual(fin['single']['standard'], {'minutes': p.minutes, 'factor': 1.0, 'cards': 2})
            self.assertIsNone(fin['fast'])
            self.assertEqual(said_minutes(p.minutes, fin), p.minutes)          # the plan card says the wall minutes
        d = plan_dict(p, 59.0, lambda m, plan=None: engine_options.finish_info(m, plan=plan))
        self.assertIn(f'about {p.minutes:.0f} min' if p.minutes < 90 else f'about {p.minutes / 60:.1f} h', d['text']['eta'])

    def test_the_banded_minutes_are_wall_minutes_on_one_5090(self):
        st = banded_plan_of().stages[0]
        I, R, O = (s[0] * s[1] / 1e6 for s in (st.padded_size, st.render_size, st.output_size))
        secs = banded_plan.T_P0_I * I + (banded_plan.T_SAMPLE_R + banded_plan.T_DECODE_R) * R + banded_plan.T_FINISH_O * O
        self.assertAlmostEqual(st.minutes, round(secs / 60 * banded_plan.IO_BUDGET + (5.0 if st.split_finish else 0), 1))


def admit_runner(items, cap=59.0, mode='fake'):
    """A Runner whose store holds `items` {(jid, iid): (plan dict, format, worker_released)}."""
    r = object.__new__(Runner)
    r.mode = mode
    r.ctx = {k: SimpleNamespace(worker_released=v[2], worker=SimpleNamespace(proc=None)) for k, v in items.items() if v[2] is not None}
    r.store = SimpleNamespace(item=lambda j, i: {'plan': items[(j, i)][0]}, get=lambda j: {'output_format': items[(j, 'i1')][1]},
                              update_item=mock.Mock())
    r.settings = SimpleNamespace(get=lambda: {'ram_cap_gb': cap})
    r._held = {}
    r.log = mock.Mock()
    return r


class Admission(unittest.TestCase):
    def test_the_large_image_need_is_1_05_x_its_upper_bound(self):
        p = banded_plan_of()
        self.assertEqual(p.peak_ram_gb, round(1.05 * max(s.peak_upper_gb for s in p.stages), 1))

    def test_finishing_service_memory(self):
        b = banded_plan_of().to_dict()
        W, H = b['output_size']
        self.assertAlmostEqual(banded_runner.finishing_gb(b, 'png8'), 0.2)
        self.assertAlmostEqual(banded_runner.finishing_gb(b, 'jpeg'), 0.2 + plane_io.jpeg_transient_bytes(W, H) / GIB)
        c = planner.plan(3500, 2188, 2).to_dict()
        Wc, Hc = c['output_size']
        self.assertAlmostEqual(banded_runner.finishing_gb(c, 'png8'), 13 * Wc * Hc / GIB)

    def test_a_classic_only_queue_is_admitted_as_5_0_1(self):
        c = planner.plan(3500, 2188, 2, ram_cap_gb=59.0).to_dict()
        big = dict(c, peak_ram_gb=30.0)
        items = {('j1', 'i1'): (big, 'png8', None), ('j2', 'i1'): (dict(c, peak_ram_gb=30.0), 'png8', True)}
        r = admit_runner(items)
        self.assertEqual(r._finishing_gb(include_classic=False), [])
        self.assertTrue(r._admit('j1', 'i1'))      # the finishing classic image's 13 B/Opx is not counted (as 5.0.1)

    def test_a_large_image_counts_the_finishing_images(self):
        b = dict(banded_plan_of().to_dict(), peak_ram_gb=58.0)
        c = planner.plan(3500, 2188, 4, ram_cap_gb=59.0).to_dict()            # 14,000 x 8,752: 13 B/Opx = 1.48 GiB
        items = {('j1', 'i1'): (b, 'png8', None), ('j2', 'i1'): (c, 'png8', True)}
        r = admit_runner(items)
        self.assertFalse(r._admit('j1', 'i1'))     # 58.0 + 1.48 > 59.0
        self.assertIn('Waiting for memory', r._held[('j1', 'i1')])
        items[('j1', 'i1')] = (dict(b, peak_ram_gb=50.0), 'png8', None)
        self.assertTrue(admit_runner(items)._admit('j1', 'i1'))

    def test_a_finishing_jpeg_large_image_is_counted_for_every_image(self):
        b = banded_plan_of(4000, 4000, 2).to_dict()
        W, H = b['output_size']
        jpeg = banded_runner.finishing_gb(b, 'jpeg')
        c = dict(planner.plan(3500, 2188, 2, ram_cap_gb=59.0).to_dict(), peak_ram_gb=59.0 - jpeg + 0.05)
        items = {('j1', 'i1'): (c, 'jpeg', None), ('j2', 'i1'): (b, 'jpeg', True)}
        r = admit_runner(items)
        self.assertEqual(r._finishing_gb(), [jpeg])
        self.assertFalse(r._admit('j1', 'i1'))

    def test_two_large_images_only_when_both_uppers_x_1_05_fit(self):
        b = dict(banded_plan_of().to_dict(), peak_ram_gb=61.0)
        items = {('j1', 'i1'): (b, 'png8', None), ('j2', 'i1'): (dict(b), 'png8', False)}
        self.assertFalse(admit_runner(items, cap=122.2 - 0.5)._admit('j1', 'i1'))
        self.assertTrue(admit_runner(items, cap=122.2)._admit('j1', 'i1'))


if __name__ == '__main__':
    unittest.main()
