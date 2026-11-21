"""5.0.2 (build wave 2, service package, item 3; admission check A5; ENGINE-DESIGN 2.3 and 6; judge P5): admission counts
the physical memory a Large-image image's planes take in the file cache, beside commit. Windows counts the file cache as
available memory, so a running image's planes read as free: each Large-image image is counted from the plane contract
(banded_plan's stage sizes) and the registered phase bounds (banded_plan.stage_peaks, read-only), checked against the
available physical memory, and the image waits or is refused in plain words, naming the size. Two images at once on the
workstation only when both fit.

Check S1: an image is counted at its worst phase, not at the phase that binds its commit: the most commit and planes it
holds at one time (1.05 x a phase's upper bound plus the planes that phase touches, over every stage and phase) in the
two-image sum and the room test, and the most planes any phase touches in the lone-image rule and the queue-time refusal.
A machine that runs Classic images only is admitted as 5.0.1.

In process: banded_runner's functions on plans from engine/banded_plan.py, and Runner._admit with a Runner made without its
start-up (the pattern of tests/test_memory_api.py). Sizes only."""
import threading
import unittest
from types import SimpleNamespace
from unittest import mock

from engine import banded_plan, controls, planes, planner
from service import banded_runner, memory_policy
from service.runner import Runner

PROVEN = {'ws128': 1e9, 'pc64': 1e9, 'pc48': 1e9}
TOTAL_64, TOTAL_128 = 63.7, 127.7
GIB = float(1 << 30)
PHASES = ('P0', 'sampling', 'decode', 'finish')
MASKS = banded_runner.sam_planes(controls.resolve({})[0])        # the default protected areas' masks and unions (9)
CAPS = {45.2: 47.8, 59.0: TOTAL_64, 122.2: TOTAL_128}            # each machine class's default cap: its physical memory
ROWS = [(3500, 2188, 4), (3500, 2188, 6), (3500, 2188, 8), (2800, 3500, 4), (2800, 3500, 6), (2800, 3500, 8),
        (4000, 2500, 8), (4000, 4000, 8)]


def banded(w, h, f, cap):
    """A Large-image plan (proven sizes patched in; the finish tier counted as the banded finish above 300 MP)."""
    with mock.patch.object(banded_plan, 'BXF_AVAILABLE', True, create=True):
        p = banded_plan.plan_banded(w, h, f, cap, proven=PROVEN)
    assert p.ok, p.reason
    return p


class ThePlaneCount(unittest.TestCase):
    def test_masks_follow_the_graph(self):
        self.assertEqual(banded_runner.sam_planes({}), 0)
        self.assertEqual(banded_runner.sam_planes({'protect_terms': ['person']}), 1)
        self.assertEqual(banded_runner.sam_planes({'protect_terms': list('abc')}), 4)                # 3 masks + 1 union
        self.assertEqual(banded_runner.sam_planes({'protect_terms': list('abcdefghi')}), 12)         # 9 + 2 + 1
        self.assertEqual(banded_runner.sam_planes({'protect_terms': list('ab'), 'release_terms': ['window']}), 4)
        params, _ = controls.resolve({})
        self.assertEqual(banded_runner.sam_planes(params),
                         sum(banded_runner.sam_planes({'protect_terms': params.get(k)}) for k in ('protect_terms', 'release_terms')))

    def test_no_phase_counts_more_than_the_stage_holds(self):
        for w, h, f, cap in ((3500, 2188, 8, 59.0), (2800, 3500, 6, 59.0), (3500, 2188, 6, 122.2), (2800, 3500, 8, 122.2),
                             (4000, 4000, 8, 122.2), (3500, 2188, 4, 45.2)):
            for st in banded(w, h, f, cap).stages:
                (pw, ph), (rw, rh), (ow, oh) = st.padded_size, st.render_size, st.output_size
                I, R, O = pw * ph, rw * rh, ow * oh
                for masks in (0, 6):
                    whole = planes.live_bytes(I, R, O) + banded_runner.MASK_BPI * I * masks
                    for phase in ('P0', 'sampling', 'decode', 'finish'):
                        self.assertLessEqual(banded_runner.stage_planes_bytes(st, phase, masks), whole,
                                             (w, h, f, st.index, phase))
                k = 12 if (rw, rh) == (4 * pw, 4 * ph) else 3                     # the canvas: f32 at k = 4, else u8
                self.assertEqual(banded_runner.stage_planes_bytes(st, 'finish', 6), 3 * I + 36 * O + 4 * I * 6)
                self.assertEqual(banded_runner.stage_planes_bytes(st, 'P0', 6), 51 * I + (k + 13) * R + 3 * O + 4 * I * 6)
                self.assertEqual(banded_runner.stage_planes_bytes(st, 'sampling', 6), (k + 13) * R)   # no mask is read
                self.assertEqual(banded_runner.stage_planes_bytes(st, 'decode', 6), 13 * R + 6 * O)

    def test_the_most_planes_any_phase_touches_are_counted(self):
        """Check S1: not the planes of the phase that binds commit (at the base, decode at every stage of 8x 3500 x 2188
        on the workstation: 13 R + 6 O, 8.7 GiB); its last finish touches 3 I + 36 O and the masks (20.9 GiB)."""
        for w, h, f, cap in ((3500, 2188, 8, 122.2), (3500, 2188, 8, 59.0), (2800, 3500, 6, 59.0), (4000, 4000, 8, 122.2)):
            p = banded(w, h, f, cap)
            want = max(banded_runner.stage_planes_bytes(st, ph, MASKS) for st in p.stages for ph in PHASES)
            self.assertAlmostEqual(banded_runner.plan_planes_gb(p, MASKS), want / GIB)
            self.assertAlmostEqual(banded_runner.plan_planes_gb(p.to_dict(), MASKS), want / GIB)
        p = banded(3500, 2188, 8, 122.2)
        binding = max(banded_runner.stage_planes_bytes(st, st.binding_phase, MASKS) for st in p.stages)
        last = p.stages[-1]
        self.assertGreater(banded_runner.stage_planes_bytes(last, 'finish', MASKS), binding)
        self.assertAlmostEqual(banded_runner.plan_planes_gb(p, MASKS),
                               banded_runner.stage_planes_bytes(last, 'finish', MASKS) / GIB)

    def test_a_classic_plan_has_no_planes(self):
        self.assertEqual(banded_runner.plan_planes_gb(planner.plan(3500, 2188, 2, ram_cap_gb=59.0)), 0.0)
        self.assertEqual(banded_runner.plan_planes_gb(planner.plan(3500, 2188, 2, ram_cap_gb=59.0).to_dict()), 0.0)


class TheWorstFigure(unittest.TestCase):
    """An image's most commit and planes at one time: over its stages and their phases, 1.05 x the phase's registered upper
    bound plus the planes that phase touches. It bounds every phase of the package's own physical model."""

    def phases(self, p, cap):
        mclass = banded_plan.machine_class(cap)
        return [banded_plan.MARGIN * gb + banded_runner.stage_planes_bytes(st, ph, MASKS) / GIB
                for st in p.stages for ph, gb in banded_plan.stage_peaks(st, mclass, st.split_finish)['phases_up'].items()]

    def test_it_is_the_largest_phase_of_any_stage(self):
        seen = 0
        with mock.patch.object(banded_plan, 'BXF_AVAILABLE', True, create=True):
            for cap in CAPS:
                for w, h, f in ROWS:
                    p = banded_plan.plan_banded(w, h, f, cap, proven=PROVEN)
                    if not p.ok:
                        continue
                    seen += 1
                    worst = banded_runner.plan_worst_gb(p, MASKS)
                    self.assertAlmostEqual(worst, max(self.phases(p, cap)), msg=(w, h, f, cap))
                    self.assertAlmostEqual(banded_runner.plan_worst_gb(p.to_dict(), MASKS), worst, msg=(w, h, f, cap))
                    planes_gb = banded_runner.plan_planes_gb(p, MASKS)
                    self.assertLessEqual(worst, p.peak_ram_gb + planes_gb + 0.1, (w, h, f, cap))   # the need is rounded
        self.assertGreaterEqual(seen, 12)

    def test_it_holds_the_phases_the_check_found_uncounted(self):
        """The check's figures (at the base): 8x 3500 x 2188 was counted as 54.4 + 8.7 GiB at its decode; on the
        workstation its last finish holds 54.3 + 20.9 GiB and on a 64 GB PC its last P0 54.0 + 18.6 GiB."""
        for cap, phase in ((122.2, 'finish'), (59.0, 'P0')):
            p = banded(3500, 2188, 8, cap)
            last = p.stages[-1]
            up = banded_plan.stage_peaks(last, banded_plan.machine_class(cap), last.split_finish)['phases_up'][phase]
            held = banded_plan.MARGIN * up + banded_runner.stage_planes_bytes(last, phase, MASKS) / GIB
            self.assertGreaterEqual(banded_runner.plan_worst_gb(p, MASKS), held)

    def test_a_classic_plan_counts_its_need(self):
        c = planner.plan(3500, 2188, 2, ram_cap_gb=59.0)
        self.assertEqual(banded_runner.plan_worst_gb(c, MASKS), c.peak_ram_gb)
        self.assertEqual(banded_runner.plan_worst_gb(c.to_dict(), MASKS), c.peak_ram_gb)

    def test_without_its_machine_class_it_takes_the_one_given_else_need_and_the_most_planes(self):
        p = banded(3500, 2188, 8, 122.2)
        d = p.to_dict()
        d['banded'] = dict(d['banded'], machine_class=None)
        self.assertAlmostEqual(banded_runner.plan_worst_gb(d, MASKS, 'ws128'), banded_runner.plan_worst_gb(p, MASKS))
        self.assertAlmostEqual(banded_runner.plan_worst_gb(d, MASKS),
                               d['peak_ram_gb'] + banded_runner.plan_planes_gb(d, MASKS))
        d['banded']['machine_class'] = 'ws128'
        d['stages'][0] = dict(d['stages'][0], padded_size=None)        # a phase bound that cannot be read: never raises
        with mock.patch.object(banded_runner, 'stage_planes_bytes', return_value=0):
            self.assertAlmostEqual(banded_runner.plan_worst_gb(d, MASKS), d['peak_ram_gb'])


class TheCheck(unittest.TestCase):
    def setUp(self):
        self.p = banded(3500, 2188, 8, 59.0)                       # 28,000 x 17,504 px
        self.planes = banded_runner.plan_planes_gb(self.p, 6)

    def test_a_lone_image_waits_until_its_planes_fit_beside_its_start(self):
        gb = min(self.p.peak_ram_gb, 8.0) + self.planes + 4.0
        ok = banded_runner.physical_problem(self.p, self.p.peak_ram_gb, self.planes, [],
                                            {'avail_phys_gb': gb + 0.1, 'total_phys_gb': TOTAL_64})
        self.assertIsNone(ok)
        why = banded_runner.physical_problem(self.p, self.p.peak_ram_gb, self.planes, [],
                                             {'avail_phys_gb': gb - 0.1, 'total_phys_gb': TOTAL_64})
        self.assertTrue(why.startswith('Waiting for memory: '))
        self.assertIn('28,000 × 17,504 px', why)
        self.assertIn(f'about {int(-(-gb // 1))} GB', why)
        self.assertIn('Close other memory-heavy apps.', why)

    def test_an_unread_memory_adds_nothing(self):
        self.assertIsNone(banded_runner.physical_problem(self.p, 54.4, self.planes, [], None))
        self.assertIsNone(banded_runner.physical_problem(self.p, 54.4, self.planes, [], {'avail_phys_gb': None}))

    def test_a_running_images_planes_read_as_free_and_are_counted_back(self):
        other = (40.0, 20.0)
        mem = {'avail_phys_gb': 54.4 + self.planes + 4.0 + 10.0, 'total_phys_gb': 1e9}      # room for this one's planes
        why = banded_runner.physical_problem(self.p, 54.4, self.planes, [other], mem)        # but not for the other's too
        self.assertIn('another image is using the system memory (RAM)', why)
        self.assertIn('28,000 × 17,504 px', why)
        mem['avail_phys_gb'] += 10.0
        self.assertIsNone(banded_runner.physical_problem(self.p, 54.4, self.planes, [other], mem))

    def test_two_images_on_the_workstation_only_when_both_fit(self):
        ws = banded(3500, 2188, 8, 122.2)
        need, pl, worst = ws.peak_ram_gb, banded_runner.plan_planes_gb(ws, 6), banded_runner.plan_worst_gb(ws, 6)
        mem = {'avail_phys_gb': 120.0, 'total_phys_gb': TOTAL_128}
        self.assertIsNone(banded_runner.physical_problem(ws, need, pl, [], mem, worst))      # the first starts
        self.assertGreater(2 * worst + 4.0, TOTAL_128)
        why = banded_runner.physical_problem(ws, need, pl, [(worst, pl)], dict(mem, avail_phys_gb=126.0), worst)
        self.assertIn('It starts when that one finishes.', why)                               # the second waits
        small = banded(3500, 2188, 6, 122.2)                                                  # 21,000 x 13,128 px
        sn, sp, sw = small.peak_ram_gb, banded_runner.plan_planes_gb(small, 0), banded_runner.plan_worst_gb(small, 0)
        mem = {'avail_phys_gb': 120.0, 'total_phys_gb': TOTAL_128}
        self.assertLessEqual(sw + 30.0 + 4.0, TOTAL_128)
        self.assertIsNone(banded_runner.physical_problem(small, sn, sp, [(30.0, 0.0)], mem, sw))  # beside a classic image
        self.assertIsNotNone(banded_runner.physical_problem(small, sn, sp, [(TOTAL_128 - sw - 3.0, 0.0)], mem, sw))

    def test_the_room_test_counts_this_images_worst_phase_and_the_others_planes(self):
        ws = banded(3500, 2188, 6, 122.2)
        need, pl, worst = ws.peak_ram_gb, banded_runner.plan_planes_gb(ws, MASKS), banded_runner.plan_worst_gb(ws, MASKS)
        other = (30.0, 10.0)                                       # its 10 GiB of planes read as free
        room = worst + 10.0 + 4.0
        mem = {'avail_phys_gb': room + 0.1, 'total_phys_gb': 1e9}
        self.assertIsNone(banded_runner.physical_problem(ws, need, pl, [other], mem, worst))
        mem['avail_phys_gb'] = room - 0.1
        self.assertIsNotNone(banded_runner.physical_problem(ws, need, pl, [other], mem, worst))
        self.assertGreater(worst, need)                            # more than the commit-binding phase's need alone

    def test_a_size_this_computer_can_never_hold_is_refused_naming_it(self):
        big = banded(4000, 4000, 8, 122.2)                                                    # 32,000 x 32,000 px
        pl = banded_runner.plan_planes_gb(big, 6)
        lone = banded_runner.lone_need_gb(big.peak_ram_gb, pl)
        total = lone + banded_runner.PHYS_IDLE_GB - 1.0                                       # an idle computer could not
        why = banded_runner.physical_refusal(big, big.peak_ram_gb, pl, total)
        self.assertIn('32,000 × 32,000 px', why)
        self.assertIn(f'more than this computer can free ({total:.0f} GB in all)', why)
        self.assertIsNone(banded_runner.physical_refusal(big, big.peak_ram_gb, pl, lone + banded_runner.PHYS_IDLE_GB))
        self.assertIsNone(banded_runner.physical_refusal(big, big.peak_ram_gb, pl, TOTAL_128))
        self.assertIsNone(banded_runner.physical_refusal(big, big.peak_ram_gb, pl, None))
        self.assertIsNone(banded_runner.physical_refusal(self.p, 54.4, 0.0, 1.0))            # a classic plan: no planes


class EveryRowStartsOnAnIdleComputer(unittest.TestCase):
    """A plan the planner admits either starts on an idle computer or is refused at queue time: never a wait that cannot
    end. Every target row of the handover's table (4x, 6x and 8x of 3500 x 2188 and 2800 x 3500) and the 32,000 px rows,
    on each machine class at its default cap, with the default protected areas' masks (MASKS, 9) and the most planes any
    phase touches."""

    def test_every_admitted_row_fits_an_idle_computer_of_its_class(self):
        admitted = 0
        with mock.patch.object(banded_plan, 'BXF_AVAILABLE', True, create=True):
            for cap, total in CAPS.items():
                for w, h, f in ROWS:
                    p = banded_plan.plan_banded(w, h, f, cap, proven=PROVEN)
                    if not p.ok:
                        continue
                    admitted += 1
                    pl = banded_runner.plan_planes_gb(p, MASKS)
                    self.assertIsNone(banded_runner.physical_refusal(p, p.peak_ram_gb, pl, total), (w, h, f, cap))
                    idle = {'avail_phys_gb': total - banded_runner.PHYS_IDLE_GB, 'total_phys_gb': total}
                    self.assertIsNone(banded_runner.physical_problem(p, p.peak_ram_gb, pl, [], idle), (w, h, f, cap))
        self.assertGreaterEqual(admitted, 12)


class Store:
    def __init__(self, items, settings=None):
        self.items = items
        self.settings = settings or {}
        self.updates = []

    def item(self, jid, iid):
        return self.items[(jid, iid)]

    def get(self, jid):
        return {'id': jid, 'settings': self.settings}

    def update_item(self, jid, iid, **kw):
        self.updates.append((jid, iid, kw))


def runner(items, running=(), cap=59.0):
    r = object.__new__(Runner)
    r.mode = 'comfy'
    r.store = Store(items)
    r.settings = SimpleNamespace(get=lambda: {'ram_cap_gb': cap})
    r.ctx = {k: SimpleNamespace(worker_released=False, worker=SimpleNamespace(proc=None)) for k in running}
    r.workers, r.multi, r._held = {}, {}, {}
    r.log = mock.Mock()
    r._lock = threading.RLock()
    return r


def memory(avail, total, commit=500.0):
    return {'avail_phys_gb': avail, 'total_phys_gb': total, 'commit_limit_gb': commit, 'commit_available_gb': commit,
            'commit_growth_gb': 0.0}


class TheAdmission(unittest.TestCase):
    def item(self, plan):
        return {'plan': plan.to_dict() if hasattr(plan, 'to_dict') else plan, 'settings': {}}

    def test_a_large_image_image_waits_in_plain_words_and_starts_when_memory_is_free(self):
        p = banded(3500, 2188, 8, 59.0)
        r = runner({('j1', 'i001'): self.item(p)})
        planes_gb = banded_runner.plan_planes_gb(p, banded_runner.sam_planes(controls.resolve({})[0]))
        short = min(p.peak_ram_gb, 8.0) + planes_gb + 4.0 - 1.0
        with mock.patch.object(memory_policy, 'system_memory', return_value=memory(short, TOTAL_64)):
            self.assertFalse(r._admit('j1', 'i001'))
        (_, _, kw), = r.store.updates
        self.assertIn('28,000 × 17,504 px', kw['message'])
        self.assertTrue(kw['message'].startswith('Waiting for memory: '))
        data = r.log.info.call_args.kwargs['data']
        self.assertAlmostEqual(data['planes_gb'], round(planes_gb, 2))
        with mock.patch.object(memory_policy, 'system_memory', return_value=memory(short + 2.0, TOTAL_64)):
            self.assertTrue(r._admit('j1', 'i001'))

    def test_a_second_large_image_image_waits_on_the_workstation_until_both_fit(self):
        p = banded(3500, 2188, 8, 122.2)
        items = {('j1', 'i001'): self.item(p), ('j2', 'i001'): self.item(p)}
        r = runner(items, running=[('j1', 'i001')], cap=122.2)
        with mock.patch.object(memory_policy, 'system_memory', return_value=memory(126.0, TOTAL_128)):
            self.assertFalse(r._admit('j2', 'i001'))
        self.assertIn('another image is using the system memory (RAM)', r.store.updates[-1][2]['message'])

    def test_an_8x_beside_a_6x_of_3500_x_2188_on_the_workstation_waits(self):
        """Check S1: counted at each stage's commit-binding phase the pair came to 127.6 GiB of 127.7 and the 6x was
        admitted with 80 GiB available; at the worst phase of each they hold about 139.6 GiB."""
        big, six = banded(3500, 2188, 8, 122.2), banded(3500, 2188, 6, 122.2)
        items = {('j1', 'i001'): self.item(big), ('j2', 'i001'): self.item(six)}
        r = runner(items, running=[('j1', 'i001')], cap=122.2)
        worst_big, worst_six = banded_runner.plan_worst_gb(big, MASKS), banded_runner.plan_worst_gb(six, MASKS)
        self.assertGreater(worst_big + worst_six + 4.0, TOTAL_128)
        self.assertLessEqual(big.peak_ram_gb + six.peak_ram_gb, 122.2)               # commit alone admits the pair
        with mock.patch.object(memory_policy, 'system_memory', return_value=memory(80.0, TOTAL_128)):
            self.assertFalse(r._admit('j2', 'i001'))
        msg = r.store.updates[-1][2]['message']
        self.assertIn('another image is using the system memory (RAM)', msg)
        self.assertIn('21,000 × 13,128 px', msg)
        data = r.log.info.call_args.kwargs['data']
        self.assertAlmostEqual(data['worst_gb'], round(worst_six, 2))
        self.assertEqual(data['running_worst_gb'], [round(worst_big, 2)])
        r.ctx = {}                                                                     # the 8x has finished
        with mock.patch.object(memory_policy, 'system_memory', return_value=memory(80.0, TOTAL_128)):
            self.assertTrue(r._admit('j2', 'i001'))

    def test_a_running_engine_above_its_plan_raises_its_worst_figure_by_the_excess(self):
        big, six = banded(3500, 2188, 6, 122.2), banded(2800, 3500, 4, 122.2)
        items = {('j1', 'i001'): self.item(big), ('j2', 'i001'): self.item(six)}
        r = runner(items, running=[('j1', 'i001')], cap=122.2)
        r.ctx[('j1', 'i001')].worker = SimpleNamespace(proc=SimpleNamespace(pid=7))
        live = big.peak_ram_gb + 6.0
        with mock.patch.object(memory_policy, 'system_memory', return_value=memory(six.peak_ram_gb + 5.0, TOTAL_128)), \
                mock.patch.object(memory_policy, 'process_private_gb', return_value=live):
            self.assertFalse(r._admit('j2', 'i001'))                 # 5.0.1's own check passes; the planes do not
        data = r.log.info.call_args.kwargs['data']
        self.assertAlmostEqual(data['running_worst_gb'][0], round(banded_runner.plan_worst_gb(big, MASKS) + 6.0, 2))

    def test_a_classic_only_machine_is_admitted_as_5_0_1(self):
        c = planner.plan(3500, 2188, 2, ram_cap_gb=59.0)
        items = {('j1', 'i001'): self.item(c), ('j2', 'i001'): self.item(c)}
        r = runner(items, running=[('j1', 'i001')])
        mem = memory(c.peak_ram_gb + 4.5, TOTAL_64)
        with mock.patch.object(memory_policy, 'system_memory', return_value=mem), \
                mock.patch.object(banded_runner, 'physical_problem', side_effect=AssertionError('checked')):
            ok = r._admit('j2', 'i001')
        self.assertEqual(ok, memory_policy.admission_problem(c.peak_ram_gb, [c.peak_ram_gb], 59.0, mem) is None)

    def test_a_classic_image_beside_a_running_large_image_one_counts_its_planes(self):
        p = banded(3500, 2188, 8, 122.2)
        c = planner.plan(1600, 1200, 2, ram_cap_gb=122.2)
        items = {('j1', 'i001'): self.item(p), ('j2', 'i001'): self.item(c)}
        r = runner(items, running=[('j1', 'i001')], cap=122.2)
        planes_gb = banded_runner.plan_planes_gb(p, MASKS)
        self.assertLessEqual(banded_runner.plan_worst_gb(p, MASKS) + c.peak_ram_gb + 4.0, TOTAL_128)   # both fit
        tight = c.peak_ram_gb + 4.0 + 1.0                                # 5.0.1's own check passes, the planes do not
        with mock.patch.object(memory_policy, 'system_memory', return_value=memory(tight, TOTAL_128)):
            self.assertFalse(r._admit('j2', 'i001'))
        with mock.patch.object(memory_policy, 'system_memory', return_value=memory(tight + planes_gb, TOTAL_128)):
            self.assertTrue(r._admit('j2', 'i001'))

    def test_the_fake_engine_reads_its_own_memory_only_when_given(self):
        p = banded(3500, 2188, 8, 59.0)
        r = runner({('j1', 'i001'): self.item(p)})
        r.mode = 'fake'
        r.fake_memory = None
        self.assertTrue(r._admit('j1', 'i001'))
        r.fake_memory = {'avail_phys_gb': 10.0, 'total_phys_gb': TOTAL_64}
        self.assertFalse(r._admit('j1', 'i001'))


class TheRefusalAtQueueTime(unittest.TestCase):
    def test_refused_naming_the_size_when_the_computer_can_never_hold_it(self):
        big = banded(4000, 4000, 8, 122.2)
        r = runner({})
        r.mode, r.fake_memory = 'fake', {'avail_phys_gb': 30.0, 'total_phys_gb': 36.0}
        why = r._physical_refusal(big, controls.resolve({})[0])
        self.assertIn('32,000 × 32,000 px', why)
        r.fake_memory = {'avail_phys_gb': 120.0, 'total_phys_gb': TOTAL_128}
        self.assertIsNone(r._physical_refusal(big, controls.resolve({})[0]))
        self.assertIsNone(r._physical_refusal(big.to_dict(), controls.resolve({})[0]))
        self.assertIsNone(r._physical_refusal(planner.plan(3500, 2188, 2, ram_cap_gb=59.0), {}))


if __name__ == '__main__':
    unittest.main()
