"""Memory accounting and honest times of the Large-image engine (engine design ENGINE-DESIGN.md 2.3, 2.10, 6; T15), and
eng:sam-501's open issue: a Large-image plan's minutes are wall minutes, so they are said as they are, while every classic
time stays 5.0.1's (with 5.0.2's honest minutes). In-process: Runner with SimpleNamespace stubs. Sizes only."""
import shutil
import tempfile
import unittest
from pathlib import Path
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

    def big_banded(self):
        """8x of 3500 x 2188 on the workstation: a Large-image plan whose stage 0 renders at supersample 2, the one Faster
        would run on (engine_options.faster_stages)."""
        p = banded_plan.plan_banded(3500, 2188, 8, 122.2, proven={'ws128': 1e9, 'pc64': 1e9, 'pc48': 1e9})
        self.assertEqual(p.engine, 'banded')
        self.assertEqual(float(p.stages[0].supersample), 2.0)
        self.assertEqual(engine_options.faster_stages(p), [0])
        return p

    def test_a_large_image_plan_runs_no_stage_faster_and_says_so(self):
        p = self.big_banded()
        for plan in (p, p.to_dict()):
            for split, cards in ((False, 1), (True, 2)):
                run = engine_options.run_info('standard', faster=True, plan=plan, split=split, cards=cards)
                self.assertFalse(run['faster'])
                self.assertEqual(run['factor'], 1.0)
                self.assertNotIn('stage_factors', run)
            fin = engine_options.finish_info(p.minutes, plan=plan, faster_available=True, cards={'standard': 2})
            self.assertEqual(fin['faster'], {'minutes': p.minutes, 'factor': 1.0, 'stages': []})
            self.assertEqual(fin['single']['faster'], {'minutes': p.minutes, 'factor': 1.0, 'cards': 2, 'stages': []})
            # the run and the plan card agree: no stage runs Faster, and the time said is the wall minutes
            self.assertEqual(run['faster'], bool(fin['faster']['stages']))

    def test_a_classic_plan_with_faster_is_unchanged(self):
        c = planner.plan(1280, 1600, 2, ram_cap_gb=59.0)
        self.assertEqual(engine_options.faster_stages(c), [0])
        run = engine_options.run_info('standard', faster=True, plan=c)
        self.assertTrue(run['faster'])
        self.assertEqual(run['factor'], engine_options.faster_factor(c, engine_options.eta_factor(True, 1, 'standard',
                                                                       io_share=engine_options.plan_io_share(c))))
        fin = engine_options.finish_info(c.minutes, plan=c, faster_available=True)
        self.assertEqual(fin['faster']['stages'], [0])

    def test_the_frozen_run_and_the_graph_of_a_large_image_stage_have_no_faster(self):
        """With Speed up upscaling on in Settings: the frozen run of a Large-image image says faster False, the log says why
        in its own words, and banded_runner builds stage 0's graph without Faster."""
        p = self.big_banded().to_dict()
        r = object.__new__(Runner)
        r.store = SimpleNamespace(get=lambda jid: {'id': jid, 'settings': {}},
                                  item=lambda jid, iid: {'name': 'x.png', 'plan': p, 'stage_index': 0, 'run': None})
        r.log = mock.Mock()
        r._item_mode = lambda job, it: 'standard'
        r.settings = SimpleNamespace(get=lambda: {'match_earlier': False})
        r._faster_wanted = lambda: True
        r.card_factor_of = lambda w: 1.0
        run = Runner._frozen_run(r, 'j', 'i', SimpleNamespace(gpu=0))
        self.assertFalse(run['faster'])
        self.assertEqual(run['factor'], 1.0)
        said = [c for c in r.log.info.call_args_list if c.args[0] == 'faster_not_large_image']
        self.assertEqual(len(said), 1)
        self.assertEqual(said[0].args[1], 'x.png uses the Large-image engine, so Speed up upscaling is not used for it')
        self.assertFalse(any(c.args[0] == 'faster_not_shared' for c in r.log.info.call_args_list))
        from engine import graph_banded
        built = []
        real = graph_banded.build_product

        def spy(*a, **kw):
            built.append(kw.get('faster'))
            raise ValueError('stop after the build call (test)')
        q = dict(p, stages=[dict(st) for st in p['stages']])
        q['stages'][0]['split_finish'] = True               # the graph is then built before any plane is made
        with mock.patch.object(graph_banded, 'build_product', spy):
            ctx = SimpleNamespace(jid='j', iid='i', shutdown=False)
            it = {'plan': q, 'run': run, 'settings': {}}
            rr = SimpleNamespace(banded_pack={'ok': True, 'tree_sha256': 'x'}, cfg=SimpleNamespace(work_dir=Path('.')),
                                 _stage_disk_check=lambda *a: None, detailed_info=lambda: {'on': False},
                                 _run_would=lambda job, it, mode: run, _item_mode=lambda job, it: 'standard')
            work = Path(tempfile.mkdtemp(prefix='cu-faster-'))
            try:
                rr.cfg.work_dir = work
                (work / 'j' / 'i').mkdir(parents=True)
                (work / 'j' / 'i' / 'input.png').write_bytes(b'')
                with self.assertRaises(Exception):
                    banded_runner.run_stage(rr, SimpleNamespace(memory_profile=None), ctx, {'settings': {}},
                                            controls.resolve({})[0], 0, len(p['stages']), it)
            finally:
                shutil.rmtree(work, ignore_errors=True)
        self.assertTrue(built)
        self.assertIs(built[0], False)
        self.assertIs(real, graph_banded.build_product)

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
