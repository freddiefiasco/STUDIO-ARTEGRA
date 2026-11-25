"""Small graphics cards keep every job 5.0.1 runs (the product owner, 26 Nov 2026: "As we develop artegra enhancer it needs to facilitate
more and more nvidia cards, not less").

5.0.1 checks no graphics memory: it starts every plan it makes and lets a step that does not fit the card spill into shared
memory. 5.0.2 first refused those plans on cards of 24 GB or less, and with the SAM ceiling at 33 MP it refused more of them.
Now, on such a card:
1. SAM follows the card. A pass whose stock SAM3_Detect step would not fit the card's usable memory takes the lean SAM node
   (ClaudeSAM3DetectLean: SAM3_Detect's own masks, only the kept mask upsampled), at any size; above SAM_STOCK_MAX_MP every
   card takes it, as before. A card over 24 GB keeps planner.sam_lean exactly, so its graphs are bd0a8194's byte for byte.
2. A Classic plan that still needs more graphics memory than the card has is admitted, as 5.0.1 admits it, with a plain
   note that it can take longer than the time shown. Nothing a 5.0.1 build runs is refused for graphics memory.
3. Plans are not touched: a plan dict is the same on every card.

In-process (Runner built with object.__new__ and stubs; no service process, no GPU). Sizes only."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from engine import controls, graph_v5t, planner, vram_model
from service import mask_graph, memory_policy
from service.errors import ApiError
from service.runner import Runner, sam_lean_graph

LEAN = 'ClaudeSAM3DetectLean'
BAL = memory_policy.PROFILES['balanced']
REF = memory_policy.PROFILES['reference']
CARDS = {6: 6.0, 8: 8.0, 10: 10.0, 11: 11.0, 12: 11.99, 16: 15.99, 20: 19.99, 24: 23.99, 32: 31.84, 48: 47.99}
PADDED = [(512, 512), (1000, 1000), (2000, 2000), (2350, 1762), (3100, 3100), (3500, 2188), (4000, 4000), (5000, 5000),
          (5500, 6000), (5745, 5745), (7000, 4376), (9408, 7056)]


def card(gb, index=0):
    return {'index': index, 'uuid': f'GPU-{gb}-{index}', 'name': f'NVIDIA Test {gb} GB', 'mem_total_gb': CARDS[gb],
            'mem_free_gb': CARDS[gb] - 1.0}


def runner(cards, profile='auto', cap=122.2):
    r = object.__new__(Runner)
    r.settings = SimpleNamespace(get=lambda: {'gpus': [c['index'] for c in cards], 'memory_profile': profile,
                                              'ram_cap_gb': cap})
    r.gpu_list = lambda max_age=None: ([dict(c) for c in cards], None)
    r.log = mock.Mock()
    return r


def stock_moment(w, h, profile=BAL):
    return vram_model.RESIDENT_GB[profile.name]['sam'] + (vram_model.SAM_STOCK_BPI + vram_model.SAM_KEPT_BPI) * vram_model.G \
        * w * h / 1e6


def stage_graph(pw, ph, f=2, s=1, protect=True, **kw):
    p, _ = controls.resolve({} if protect else {'protect': []})
    return graph_v5t.build_product('x.png', pw, ph, p, 'x', f=f, s=s, **kw)[0]


def classes(g):
    return sorted(n['class_type'] for n in g.values())


class TheSamChoiceFollowsTheCard(unittest.TestCase):
    def test_cards_over_24_gb_and_unknown_cards_keep_the_planner_rule(self):
        for total in (None, 0, 31.84, 47.99, 96.0):
            for prof in (BAL, REF, 'reference', 'balanced'):
                for (w, h) in PADDED:
                    self.assertEqual(vram_model.card_sam_lean(w, h, total, prof), planner.sam_lean(w, h), (total, w, h))

    def test_a_small_card_takes_the_lean_node_wherever_the_stock_step_does_not_fit(self):
        for gb in (6, 8, 10, 11, 12, 16, 20, 24):
            total = CARDS[gb]
            for (w, h) in PADDED:
                for prof in (BAL, REF):
                    want = planner.sam_lean(w, h) or stock_moment(w, h, prof) > vram_model.usable_gb(total)
                    self.assertEqual(vram_model.card_sam_lean(w, h, total, prof), want, (gb, w, h, prof.name))
        self.assertTrue(vram_model.card_sam_lean(3100, 3100, 8.0, BAL))            # 9.6 MP: 5.73 GiB stock, 5.5 usable
        self.assertFalse(vram_model.card_sam_lean(3000, 3000, 8.0, BAL))           # 9.0 MP: 5.50 GiB stock, fits
        self.assertFalse(vram_model.card_sam_lean(2000, 2000, 8.0, BAL))           # 4 MP: stock fits
        self.assertFalse(vram_model.card_sam_lean(5000, 5000, 23.99, BAL))         # 25 MP fits a 24 GB card
        self.assertTrue(vram_model.card_sam_lean(5000, 5000, 23.99, REF))          # not with the reference resident set

    def test_the_moments_count_the_cards_choice(self):
        st = {'index': 0, 'padded_size': (2800, 3500), 'render_size': (11200, 14000)}
        stock = vram_model.classic_moments(st, BAL, True)
        self.assertEqual(stock, vram_model.classic_moments(st, BAL, True, lean=False))       # card-less: the planner rule
        on8 = vram_model.classic_moments(st, BAL, True, total_gb=8.0)
        self.assertEqual(on8, vram_model.classic_moments(st, BAL, True, lean=True))
        self.assertLess(on8['sam'], stock['sam'])
        self.assertEqual(vram_model.classic_moments(st, BAL, True, total_gb=31.84), stock)
        p = planner.plan(2800, 3500, 2, ram_cap_gb=59.0)
        self.assertEqual(vram_model.classic_plan_vram_gb(p, BAL, True), vram_model.classic_plan_vram_gb(p, BAL, True, None))
        self.assertLess(vram_model.classic_plan_vram_gb(p, BAL, True, total_gb=8.0)[0],
                        vram_model.classic_plan_vram_gb(p, BAL, True)[0])
        self.assertLessEqual(vram_model.classic_plan_vram_gb(p, BAL, True, total_gb=8.0)[0], vram_model.usable_gb(8.0))


class TheStageGraphTakesTheChoice(unittest.TestCase):
    """The graph builders stay bd0a8194's (engine/graph_v5t.py and engine/fast_recipe.py are frozen): the runner swaps the
    SAM class of the graph they build (runner.sam_lean_graph), which is exactly the graph graph_v5t builds for a SAM input
    above the ceiling."""

    def test_the_swap_is_the_builders_own_lean_graph(self):
        for (pw, ph, f, s) in ((5752, 5752, 2, 1), (7000, 5000, 2, 1.5), (9408, 7056, 1.5, 1)):
            lean = stage_graph(pw, ph, f, s)                                  # above the ceiling: the builder's lean graph
            self.assertIn(LEAN, classes(lean))
            with mock.patch.object(planner, 'SAM_STOCK_MAX_MP', float('inf')):
                stock = stage_graph(pw, ph, f, s)
            self.assertIn('SAM3_Detect', classes(stock))
            self.assertEqual(sam_lean_graph(stock), lean, (pw, ph))
            self.assertEqual(sam_lean_graph(lean), lean)

    def test_below_the_ceiling_only_the_sam_class_changes(self):
        stock = stage_graph(2800, 3500)
        lean = sam_lean_graph(stock)
        self.assertIn('SAM3_Detect', classes(stock))
        self.assertNotIn('SAM3_Detect', classes(lean))
        self.assertEqual(sorted(stock), sorted(lean))
        for nid, node in stock.items():
            self.assertEqual(lean[nid], dict(node, class_type=LEAN) if node['class_type'] == 'SAM3_Detect' else node)
        off = stage_graph(2800, 3500, protect=False)
        self.assertIs(sam_lean_graph(off), off)

    def test_the_protected_area_preview_follows_the_card(self):
        p, _ = controls.resolve({'protect': ['architecture']})
        args = ('x.png', p['protect_terms'], p['protect'], 'm')
        stock = mask_graph.build(*args, size=(3100, 3100))
        self.assertNotIn(LEAN, classes(stock))
        self.assertEqual(mask_graph.build(*args, size=(3100, 3100), card_totals=[31.84], profile=REF), stock)
        lean = mask_graph.build(*args, size=(3100, 3100), card_totals=[8.0], profile=BAL)
        self.assertEqual(lean, {k: (dict(v, class_type=LEAN) if v['class_type'] == 'SAM3_Detect' else v)
                                for k, v in stock.items()})
        self.assertEqual(mask_graph.build(*args, size=(3100, 3100), card_totals=[31.84, 8.0], profile=BAL), lean)


class NothingIsRefusedForClassicGraphicsMemory(unittest.TestCase):
    """The sweep's classes (lead-smallcard sweep, 26 Nov): stock SAM, x4, blur, and SAM then x4."""
    CASES = ((777, 777, 6, True), (1520, 1762, 6, False), (1520, 1762, 6, True), (3000, 777, 4, False),
             (2800, 3500, 2, True), (4000, 4000, 2, True))

    def test_no_classic_plan_is_refused_on_any_card(self):
        for gb in CARDS:
            r = runner([card(gb)])
            for w, h, f, protect in self.CASES:
                p = planner.plan(w, h, f, ram_cap_gb=122.2)
                self.assertTrue(p.ok and p.engine == 'classic', (w, h, f))
                self.assertIsNone(r._vram_refusal(p, protect=protect), (gb, w, h, f, protect))
                self.assertIsNone(r._vram_refusal(p.to_dict(), protect=protect, cards=[card(gb)]), (gb, w, h, f))

    def test_a_plan_the_lean_node_fits_runs_without_a_note(self):
        r = runner([card(8)])
        for (w, h, f) in ((777, 777, 6), (2800, 3500, 2), (2048, 2048, 4), (2560, 1440, 4)):
            p = planner.plan(w, h, f, ram_cap_gb=59.0)
            self.assertIsNone(r._card_vram_problem(p, card(8), True), (w, h, f))
            self.assertIsNone(r._vram_note(p, protect=True), (w, h, f))

    def test_a_plan_that_still_does_not_fit_gets_the_note(self):
        r = runner([card(8)])
        p = planner.plan(1520, 1762, 6, ram_cap_gb=122.2)
        note = r._vram_note(p, protect=False)
        self.assertEqual(note, 'This image needs about 9 GB of graphics memory with the Classic engine; this card has 8 GB. '
                               'It still runs, but the part that does not fit may use shared memory, so it can take longer '
                               'than the time shown.')
        self.assertIsNone(runner([card(32)])._vram_note(p, protect=True))
        self.assertIsNone(runner([card(12)])._vram_note(p, protect=True))
        two = runner([card(8, 0), card(8, 1)])
        self.assertIn('the largest graphics card in use has 8 GB', two._vram_note(p, protect=False))
        self.assertIsNone(runner([card(8, 0), card(16, 1)])._vram_note(p, protect=True))     # the 16 GB card fits it

    def test_the_plan_card_says_the_note_and_stays_ok(self):
        r = runner([card(8)])
        r.finish_info = lambda minutes, plan=None: None
        r.memory_info = lambda: {'profiles': []}
        p = planner.plan(1520, 1762, 6, ram_cap_gb=122.2)
        res = r.plan_check(p)
        self.assertTrue(res['ok'])
        self.assertNotIn('vram_refused', res)
        self.assertIn(r._vram_note(p, protect=True), res['text']['notes'])
        r32 = runner([card(32)])
        r32.finish_info, r32.memory_info = r.finish_info, r.memory_info
        from service.media import plan_dict
        self.assertEqual(r32.plan_check(p), dict(plan_dict(p, 122.2, r.finish_info), memory={'profiles': []}))

    def test_the_scheduler_still_prefers_a_card_the_plan_fits(self):
        p = planner.plan(1520, 1762, 6, ram_cap_gb=122.2).to_dict()
        it = {'plan': p, 'settings': {'protect': []}}
        store = SimpleNamespace(item=lambda j, i: it, get=lambda j: {'settings': {}})
        r = runner([card(8, 0), card(16, 1)])
        r.store = store
        self.assertFalse(r._fits_worker('j', 'i', SimpleNamespace(gpu=0)))          # waits for the 16 GB card
        self.assertTrue(r._fits_worker('j', 'i', SimpleNamespace(gpu=1)))
        r8 = runner([card(8, 0), card(8, 1)])                                       # fits no card: runs, as 5.0.1
        r8.store = store
        self.assertTrue(r8._fits_worker('j', 'i', SimpleNamespace(gpu=0)))
        r6 = runner([card(6, 0)])
        r6.store = store
        self.assertTrue(r6._fits_worker('j', 'i', SimpleNamespace(gpu=0)))


class TheWorkersCardDecidesItsGraph(unittest.TestCase):
    def test_the_choice_for_an_engine(self):
        r = runner([card(8, 0), card(32, 1)])
        w8 = SimpleNamespace(gpu=0, memory_profile=BAL)
        w32 = SimpleNamespace(gpu=1, memory_profile=REF)
        shared = SimpleNamespace(gpu=0, gpus=(0, 1), memory_profile=BAL)
        self.assertTrue(r._sam_lean_for(w8, 3100, 3100))
        self.assertFalse(r._sam_lean_for(w8, 2000, 2000))
        self.assertIsNone(r._sam_lean_for(w32, 3100, 3100))           # over 24 GB: the planner rule (None)
        self.assertTrue(r._sam_lean_for(shared, 3100, 3100))          # one image on two cards: the smaller decides
        self.assertIsNone(runner([])._sam_lean_for(w8, 3100, 3100))  # cards not read yet: the planner rule

    def test_run_stage_builds_the_graph_for_its_card(self):
        import numpy as np
        from service import runner as runner_mod

        class Stop(Exception):
            pass

        def graph_of(cards, gpu, profile, protect=True, mode='standard', size=(2800, 3500)):
            r = runner(cards)
            p = planner.plan(*size, 2, ram_cap_gb=122.2).to_dict()
            it = {'plan': p, 'timings': {'stages': []}, 'run': {'mode': mode, 'speed_stack': True}}
            r.store = SimpleNamespace(item=lambda j, i: it)
            r.cfg = SimpleNamespace(work_dir=Path(td))
            r._stage_disk_check = lambda *a: None
            r._cleanup_worker_files = lambda *a: None
            r.detailed_info = lambda: {'on': False}
            params, _ = controls.resolve(dict({} if protect else {'protect': []}, mode=mode))
            w = SimpleNamespace(gpu=gpu, memory_profile=profile, input_dir=Path(td))
            got = {}

            def write(path, graph):
                got['graph'] = graph
                raise Stop()
            st = p['stages'][0]
            with mock.patch.object(runner_mod.images, 'load_rgb',
                                   return_value=np.zeros((st['input_size'][1], st['input_size'][0], 3), np.uint8)), \
                    mock.patch.object(runner_mod.images, 'pad_reflect', side_effect=lambda a, s: a), \
                    mock.patch.object(runner_mod.images, 'save_png_atomic'), \
                    mock.patch.object(runner_mod, 'atomic_write_json', side_effect=write):
                with self.assertRaises(Stop):
                    r._run_stage(w, SimpleNamespace(jid='j', iid='i'), {}, params, 0, 1)
            return got['graph']

        with tempfile.TemporaryDirectory() as td:
            on32 = graph_of([card(32)], 0, REF)
            on8 = graph_of([card(8)], 0, BAL)
            off8 = graph_of([card(8)], 0, BAL, protect=False)
            bolt32 = graph_of([card(32)], 0, REF, mode='fast', size=(3000, 3100))    # 9.3 MP at s 2
            bolt8 = graph_of([card(8)], 0, BAL, mode='fast', size=(3000, 3100))
        self.assertIn('SAM3_Detect', classes(bolt32))
        self.assertIn(LEAN, classes(bolt8))
        self.assertNotIn('SAM3_Detect', classes(bolt8))
        self.assertIn('LoraLoaderModelOnly', classes(bolt8))               # Bolt's own graph, with the card's SAM step
        self.assertNotIn(LEAN, classes(off8))
        self.assertIn('SAM3_Detect', classes(on32))
        self.assertNotIn(LEAN, classes(on32))
        self.assertIn(LEAN, classes(on8))
        self.assertNotIn('SAM3_Detect', classes(on8))
        self.assertEqual(sorted(on8), sorted(on32))


class SubmitAdmitsWhat501Admits(unittest.TestCase):
    """create_job on a bare Runner with the app's own Settings (as the admission sweep drives it)."""

    def submit(self, gb, w, h, f, protect=True, ram=127.3):
        from service.settings import Settings

        class Admitted(Exception):
            pass
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            log = mock.Mock()
            st = Settings(td / 'settings.json', td, log, total_ram_gb=ram)
            st.split_default_fn = lambda: False
            st.gpus_fn = lambda: [0]
            r = object.__new__(Runner)
            c = card(gb)
            r.gpu_list = lambda max_age=None: ([dict(c)], None)
            r.settings, r.log = st, log
            media = {'id': 'm', 'path': str(td / 'x.png'), 'name': 'x.png', 'width': w, 'height': h, 'alpha': False,
                     'sha256': '0' * 64, 'format': 'PNG', 'bit_depth': 8, 'notes': []}
            r.media = SimpleNamespace(get=lambda m: media, copy_for_job=lambda m, d: None)
            got = {}

            def create(job):
                got['job'] = job
                raise Admitted()
            r.store = SimpleNamespace(find_request=lambda a, b: None, create=create)
            r.cfg = SimpleNamespace(fake_engine=True, two_card_proof=False, work_dir=td / 'work', state_dir=td)
            r.mode, r.accepting, r.node_pack, r.g1u = 'fake', True, {'tree_sha256': None}, None
            r._fast_test, r._fast_files_ok = False, True
            r._snap_ready = SimpleNamespace(wait=lambda t=None: True, set=lambda: None, is_set=lambda: True)
            r.fake_memory = {'total_phys_gb': ram, 'avail_phys_gb': ram - 4.0}
            r._check_free = lambda path, need, label: None
            r._run_would = lambda job, it, mode, waiting=None: {'factor': 1.0}
            r.wake = lambda: None
            settings = {'scale': f} if protect else {'scale': f, 'protect': []}
            body = {'client_request_id': '0' * 32, 'media_ids': ['m'], 'settings': settings, 'output_dir': str(td)}
            try:
                r.create_job(body)
            except Admitted:
                return got['job']['items'][0]
            except ApiError as e:
                return e

    def test_the_sweeps_examples_are_admitted(self):
        for gb, w, h, f, protect, note in ((8, 777, 777, 6, True, False), (8, 1520, 1762, 6, False, True),
                                           (8, 1520, 1762, 6, True, True), (8, 3000, 777, 4, False, True),
                                           (8, 2800, 3500, 2, True, False), (6, 1520, 1762, 6, False, True),
                                           (32, 2800, 3500, 2, True, False)):
            it = self.submit(gb, w, h, f, protect)
            self.assertIsInstance(it, dict, (gb, w, h, f, protect, it))
            has = any('graphics memory' in n for n in it['notes'])
            self.assertEqual(has, note, (gb, w, h, f, protect, it['notes']))
            self.assertEqual(it['plan'], planner.plan(w, h, f, ram_cap_gb=122.2).to_dict())   # the plan is never touched


if __name__ == '__main__':
    unittest.main()
