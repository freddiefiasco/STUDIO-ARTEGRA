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
import re
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from engine import controls, graph_v5t, planner, vram_model
from service import api, mask_graph, media, memory_policy
from service.errors import ApiError
from service.runner import Runner, is_vram_note, sam_lean_graph

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
        self.assertEqual(note, 'May run slowly: this image needs about 9 GB of graphics memory with the Classic engine; '
                               'this card has 8 GB. The part that does not fit may use shared memory, so it can take '
                               'longer than the time shown. A pass that takes far longer than expected is stopped.')
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


class TheTimeWarningReachesTheWindow(unittest.TestCase):
    """Round 2 (the verifiers, 26 Nov): the note was only in the service's data. The window draws a waiting image's plan
    from its scales (GET /api/inputs, media.scales_for) or from POST /api/plan, a queued image from its item notes, and the
    Activity feed only api.USER_EVENTS. So each of those carries it, for both protect choices where the window has not yet
    said which, and the words say what is true: it may run slowly, and a pass far over its time is stopped (as in 5.0.1)."""
    SPILL = (1520, 1762, 6)                       # 8 GB card: needs more than the card has with either protect choice

    def notes_of(self, r, w, h, f):
        p = planner.plan(w, h, f, ram_cap_gb=122.2)
        return p, {'on': r._vram_note(p, protect=True), 'off': r._vram_note(p, protect=False)}

    def test_the_words_say_it_may_run_slowly_and_can_be_stopped(self):
        r = runner([card(8)])
        note = r._vram_note(planner.plan(*self.SPILL, ram_cap_gb=122.2), protect=False)
        self.assertTrue(note.startswith('May run slowly: '), note)
        self.assertNotIn('still runs', note)
        self.assertIn('longer than the time shown', note)
        self.assertTrue(note.endswith('A pass that takes far longer than expected is stopped.'), note)
        self.assertTrue(is_vram_note(note))
        self.assertFalse(is_vram_note('JPEG has no transparency: the transparent areas are filled.'))
        src = Path(__file__).resolve().parents[1].joinpath('service', 'runner.py').read_text(encoding='utf-8')
        self.assertIn("raise ItemFailure(f'Pass {k + 1} of {n} took far longer than expected (over", src)   # the stop it names

    def test_the_plan_cards_of_waiting_images_carry_the_note(self):
        r = runner([card(8)])
        scales = media.scales_for(1520, 1762, 122.2, None, vram_note_fn=r.plan_vram_notes)
        p, want = self.notes_of(r, *self.SPILL)
        self.assertTrue(want['on'] and want['off'])
        self.assertEqual(scales['6']['vram_note'], want)
        self.assertTrue(scales['6']['ok'])
        lean_fits = media.scales_for(2800, 3500, 59.0, None, vram_note_fn=r.plan_vram_notes)
        self.assertNotIn('vram_note', lean_fits['2'])                      # the lean SAM step fits: no note
        for gb in (12, 24, 32, 48):                                        # no note: the entries are bd0a8194's
            rg = runner([card(gb)])
            self.assertEqual(media.scales_for(1520, 1762, 122.2, None, vram_note_fn=rg.plan_vram_notes),
                             media.scales_for(1520, 1762, 122.2, None), gb)
        self.assertEqual(media.scales_for(1520, 1762, 122.2, None, vram_note_fn=runner([]).plan_vram_notes),
                         media.scales_for(1520, 1762, 122.2, None))        # cards not read yet

    def test_a_plan_card_that_cannot_be_noted_is_still_listed(self):
        def broken(plan):
            raise RuntimeError('no cards')
        self.assertEqual(media.scales_for(1520, 1762, 122.2, None, vram_note_fn=broken),
                         media.scales_for(1520, 1762, 122.2, None))

    def test_the_image_list_uses_the_runners_hook(self):
        r = runner([card(8)])
        lib = object.__new__(media.MediaLibrary)
        lib.ram_cap_fn, lib.finish_fn, lib.vram_note_fn = (lambda: 122.2), None, r.plan_vram_notes
        lib._duplicate_of = lambda rec: None
        rec = {'id': 'm', 'name': 'x.png', 'path': 'x.png', 'width': 1520, 'height': 1762, 'format': 'PNG', 'bit_depth': 8,
               'alpha': False, 'icc': None, 'exif': None, 'notes': [], 'sha256': '0' * 64, 'added': 'now'}
        self.assertEqual(lib.preview(rec)['scales']['6']['vram_note'], self.notes_of(r, *self.SPILL)[1])
        src = Path(__file__).resolve().parents[1].joinpath('service', 'runner.py').read_text(encoding='utf-8')
        self.assertIn('self.media.vram_note_fn = self.plan_vram_notes', src)
        self.assertIn('vram_note_fn', media.MediaLibrary.__init__.__code__.co_names)   # a library starts with no hook

    def test_the_plan_answer_carries_the_note_for_both_choices(self):
        r = runner([card(8)])
        r.finish_info = lambda minutes, plan=None: None
        r.memory_info = lambda: {'profiles': []}
        p, want = self.notes_of(r, *self.SPILL)
        res = r.plan_check(p)
        self.assertTrue(res['ok'])
        self.assertEqual(res['vram_note'], want)
        r32 = runner([card(32)])
        r32.finish_info, r32.memory_info = r.finish_info, r.memory_info
        self.assertNotIn('vram_note', r32.plan_check(p))

    def test_the_start_line_reaches_the_activity_feed(self):
        self.assertIn('vram_spill_expected', api.USER_EVENTS)
        src = Path(__file__).resolve().parents[1].joinpath('service', 'runner.py').read_text(encoding='utf-8')
        self.assertIn("""self.log.warn('vram_spill_expected', f'{it["name"]}: {spill}'""", src)    # it names the image

    def test_a_large_image_refusal_names_the_smaller_classic_image_it_accepts(self):
        """With Large-image sizes admitted (a developer build) and the Reference profile forced on a 12 GB card, no smaller
        image of 2048 x 2048's shape fits the card at 6x, but the Classic engine accepts smaller ones (with the note), so the
        refusal says so instead of only that none fits."""
        from engine import banded_plan
        with mock.patch.dict(banded_plan.BANDED_PROVEN_MP, {k: 2000.0 for k in banded_plan.BANDED_PROVEN_MP}):
            r = runner([card(12)], profile='reference')
            r.fake_memory, r.mode = None, 'fake'
            big = planner.plan(2048, 2048, 6, ram_cap_gb=122.2)
            self.assertEqual((big.ok, big.engine), (True, 'banded'))
            said = r._vram_refusal(big, protect=True)
            self.assertRegex(said, r'^A 12,288 × 12,288 px result needs about \d+ GB of graphics memory with the Large-image '
                                   r'engine; this card has 12 GB\. No smaller image of this shape fits this card at 6× with '
                                   r'either engine\. The Classic engine accepts a smaller image, up to a result of about '
                                   r"[\d,]+ × [\d,]+ px, but it may run slowly: it does not fit the card's graphics "
                                   r'memory\.$')
            w, h = (int(x.replace(',', '')) for x in re.search(r'about ([\d,]+) × ([\d,]+) px, but', said).groups())
            q = planner.plan(w // 6, h // 6, 6, ram_cap_gb=122.2)
            self.assertEqual((q.ok, q.engine), (True, 'classic'))
            self.assertIsNone(r._vram_refusal(q, protect=True))
            self.assertIsNotNone(r._vram_note(q, protect=True))
            self.assertIsNone(runner([card(12)])._vram_refusal(big, protect=True))      # Auto: admitted, as before


if __name__ == '__main__':
    unittest.main()
