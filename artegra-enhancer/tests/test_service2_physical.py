"""5.0.2 (build wave 2, service package, item 3; admission check A5; ENGINE-DESIGN 2.3 and 6; judge P5): admission counts
the physical memory a Large-image image's planes take in the file cache, beside commit. Windows counts the file cache as
available memory, so a running image's planes read as free: each Large-image image's planes are counted from the plane
contract at the phase that binds each stage's peak (banded_plan's stage sizes and binding_phase), checked against the
available physical memory, and the image waits or is refused in plain words, naming the size. Two images at once on the
workstation only when both fit. A machine that runs Classic images only is admitted as 5.0.1.

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
                whole = planes.live_bytes(pw * ph, rw * rh, ow * oh)
                before = [banded_runner.stage_planes_bytes(st, phase) for phase in ('P0', 'sampling', 'decode')]
                self.assertLessEqual(max(before), whole, (w, h, f, st.index))
                self.assertEqual(banded_runner.stage_planes_bytes(st, 'finish'), whole)
                self.assertLessEqual(before[0], before[2])          # the decode adds the two decoded passes
                self.assertEqual(banded_runner.stage_planes_bytes(st, 'finish', masks=6),
                                 whole + banded_runner.MASK_BPI * pw * ph * 6)

    def test_the_binding_phase_of_each_stage_is_the_one_counted(self):
        p = banded(3500, 2188, 8, 122.2)                           # every stage's peak bound by its decode here
        self.assertEqual([s.binding_phase for s in p.stages], ['decode'] * 3)
        st = p.stages[-1]
        (pw, ph), (rw, rh), (ow, oh) = st.padded_size, st.render_size, st.output_size
        I, R, O = pw * ph, rw * rh, ow * oh
        want = 51 * I + 16 * R + 3 * O + 6 * O                    # input, big8, canvas u8, hint, edges, init; creative, structure
        self.assertEqual(banded_runner.stage_planes_bytes(st), want)
        self.assertAlmostEqual(banded_runner.plan_planes_gb(p), want / 2 ** 30)
        self.assertAlmostEqual(banded_runner.plan_planes_gb(p.to_dict()), want / 2 ** 30)

    def test_a_classic_plan_has_no_planes(self):
        self.assertEqual(banded_runner.plan_planes_gb(planner.plan(3500, 2188, 2, ram_cap_gb=59.0)), 0.0)
        self.assertEqual(banded_runner.plan_planes_gb(planner.plan(3500, 2188, 2, ram_cap_gb=59.0).to_dict()), 0.0)


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
        need, pl = ws.peak_ram_gb, banded_runner.plan_planes_gb(ws, 6)
        mem = {'avail_phys_gb': 120.0, 'total_phys_gb': TOTAL_128}
        self.assertIsNone(banded_runner.physical_problem(ws, need, pl, [], mem))             # the first starts
        both = 2 * (need + pl) + 4.0
        self.assertGreater(both, TOTAL_128)                                                   # 2 x (54.4 + 20.0) + 4
        why = banded_runner.physical_problem(ws, need, pl, [(need, pl)], dict(mem, avail_phys_gb=126.0))
        self.assertIn('It starts when that one finishes.', why)                               # the second waits
        small = banded(3500, 2188, 6, 122.2)                                                  # 21,000 x 13,128 px
        sn, sp = small.peak_ram_gb, banded_runner.plan_planes_gb(small, 0)
        self.assertLessEqual(sn + sp + 30.0 + 4.0 + 4.0, TOTAL_128)
        self.assertIsNone(banded_runner.physical_problem(small, sn, sp, [(30.0, 4.0)],
                                                         {'avail_phys_gb': 120.0, 'total_phys_gb': TOTAL_128}))

    def test_a_size_this_computer_can_never_hold_is_refused_naming_it(self):
        big = banded(4000, 4000, 8, 122.2)                                                    # 32,000 x 32,000 px
        pl = banded_runner.plan_planes_gb(big, 6)
        why = banded_runner.physical_refusal(big, big.peak_ram_gb, pl, 96.0)
        self.assertIn('32,000 × 32,000 px', why)
        self.assertIn('more than this computer has (96 GB)', why)
        self.assertIsNone(banded_runner.physical_refusal(big, big.peak_ram_gb, pl, TOTAL_128))
        self.assertIsNone(banded_runner.physical_refusal(big, big.peak_ram_gb, pl, None))
        self.assertIsNone(banded_runner.physical_refusal(self.p, 54.4, 0.0, 1.0))            # a classic plan: no planes


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
        planes_gb = banded_runner.plan_planes_gb(p, banded_runner.sam_planes(controls.resolve({})[0]))
        self.assertLessEqual(p.peak_ram_gb + planes_gb + c.peak_ram_gb + 4.0, TOTAL_128)     # both fit the computer
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
        r.mode, r.fake_memory = 'fake', {'avail_phys_gb': 90.0, 'total_phys_gb': 96.0}
        why = r._physical_refusal(big, controls.resolve({})[0])
        self.assertIn('32,000 × 32,000 px', why)
        r.fake_memory = {'avail_phys_gb': 120.0, 'total_phys_gb': TOTAL_128}
        self.assertIsNone(r._physical_refusal(big, controls.resolve({})[0]))
        self.assertIsNone(r._physical_refusal(big.to_dict(), controls.resolve({})[0]))
        self.assertIsNone(r._physical_refusal(planner.plan(3500, 2188, 2, ram_cap_gb=59.0), {}))


if __name__ == '__main__':
    unittest.main()
