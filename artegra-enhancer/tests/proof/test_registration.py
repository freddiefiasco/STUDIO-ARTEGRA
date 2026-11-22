"""tools/proof/registration.py: stable hashes, the plan and graph marks from the build's planner, sealing before the result,
the write-once registration, and a moved mark detected."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from engine import banded_plan
from tools.proof import harness, node_table, registration as R

CAP = 59.0


def render_node_table():
    """Plan as the service and the proof rows do on a 64 GB render node (contracts.g1u): its committed G1 table (TABLES[2]).
    Wave-3 merge: under the shipped tier 3 the refit splits chain4x's second stage at 59.0; with the node's table neither
    stage splits, which the cases below take as their premise."""
    return mock.patch.multiple(banded_plan, BXF_TABLE=node_table.committed(2), BXF_TABLE_SOURCE='committed')


class Hashes(unittest.TestCase):
    def test_canonical_hash_ignores_key_order_and_is_stable(self):
        a = {'b': [1, 2, {'z': 1, 'y': 'x'}], 'a': 1.5}
        b = {'a': 1.5, 'b': [1, 2, {'y': 'x', 'z': 1}]}
        self.assertEqual(R.sha(a), R.sha(b))
        import hashlib
        want = hashlib.sha256(b'{"a":1.5,"b":[1,2,{"y":"x","z":1}]}').hexdigest()     # the identity record's own hashing
        self.assertEqual(R.sha(a), want)
        self.assertEqual(R.sha(a), harness.graph_sha(a))
        self.assertNotEqual(R.sha(a), R.sha(dict(a, a=1.5000001)))

    def test_tree_hash_changes_with_a_file_and_not_with_pycache(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / 'engine').mkdir()
            (d / 'engine' / 'x.py').write_text('a = 1\n', encoding='utf8')
            h1 = R.tree_sha256(d, ('engine',))
            (d / 'engine' / '__pycache__').mkdir()
            (d / 'engine' / '__pycache__' / 'x.cpython-313.pyc').write_bytes(b'\0junk')
            self.assertEqual(R.tree_sha256(d, ('engine',))['sha256'], h1['sha256'])
            (d / 'engine' / 'x.py').write_text('a = 2\n', encoding='utf8')
            self.assertNotEqual(R.tree_sha256(d, ('engine',))['sha256'], h1['sha256'])


class PlanMarks(unittest.TestCase):
    def test_marks_of_a_forced_plan(self):
        plan = harness.forced_plan(harness.PAIRS['chain4x'], CAP)
        m = R.plan_marks(plan, CAP)
        self.assertEqual(m['plan_dict_sha256'], R.sha(plan.to_dict()))
        self.assertEqual(m['constants'], {k: plan.banded[k] for k in ('finish', 'canvas', 'recipe', 'halo_fix')})
        self.assertEqual(len(m['stages']), 2)
        s0 = m['stages'][0]
        st = plan.stages[0]
        exp, up, _, source = R.stage_peaks(st, plan.banded['machine_class'], st.split_finish)
        self.assertAlmostEqual(s0['peak_expected_gb'], round(exp, 2))
        self.assertAlmostEqual(s0['peak_upper_gb'], round(up, 2))
        self.assertEqual(s0['peak_source'], source)
        self.assertTrue(source.startswith(('banded_plan.stage_peaks', 'banded_plan.banded_peak_gb')))
        if source == 'banded_plan.stage_peaks':
            pk = banded_plan.stage_peaks(st, plan.banded['machine_class'], st.split_finish)
            self.assertEqual((exp, up), (pk['exp'][0], pk['up'][0]))
        self.assertEqual(s0['vram_bound_gb'], round(banded_plan.banded_vram_gb(st), 2))
        self.assertEqual(s0['deadline_s'], round((3 * st.minutes * 1.0 + 10) * 60))
        lo, hi = s0['time_band_min']
        self.assertAlmostEqual(lo, round(st.minutes * 0.7, 1))
        self.assertAlmostEqual(hi, round(st.minutes * 1.3, 1))

    def test_peaks_use_banded_peak_gb_once_the_planner_has_it(self):
        plan = harness.forced_plan(harness.PAIRS['k4'], CAP)
        fake = lambda st, mclass, split: {'expected': 11.0, 'upper': 22.0, 'phase': 'finish'}
        with mock.patch.object(banded_plan, 'banded_peak_gb', fake, create=True):
            s0 = R.plan_marks(plan, CAP)['stages'][0]
        self.assertEqual((s0['peak_expected_gb'], s0['peak_upper_gb'], s0['peak_source']),
                         (11.0, 22.0, 'banded_plan.banded_peak_gb'))
        other = lambda st, mclass: 30.0                      # another signature: fall back to stage_peaks and say why
        with mock.patch.object(banded_plan, 'banded_peak_gb', other, create=True):
            s1 = R.plan_marks(plan, CAP)['stages'][0]
        self.assertTrue(s1['peak_source'].startswith('banded_plan.stage_peaks (banded_peak_gb'))

    def test_card_factor_scales_the_deadline_only(self):
        plan = harness.forced_plan(harness.PAIRS['k4'], CAP)
        a, b = R.plan_marks(plan, CAP), R.plan_marks(plan, CAP, card_factor=2.5)
        self.assertEqual(b['stages'][0]['deadline_s'], round((3 * plan.stages[0].minutes * 2.5 + 10) * 60))
        self.assertEqual(a['plan_dict_sha256'], b['plan_dict_sha256'])
        c = R.plan_marks(plan, CAP, card_factor=0.5)
        self.assertEqual(c['stages'][0]['deadline_s'], a['stages'][0]['deadline_s'])     # cf = max(1, card_factor)


WS_CAP = 122.2


class WorkerBounds(unittest.TestCase):
    """The harness's Job holds the ComfyUI worker alone, while peak_upper_gb is the service Job's bound (the worker's phases
    plus banded_plan.SERVICE_GB): the worker-only bound is registered beside it, per part for a split stage."""

    def test_the_worker_bound_is_the_service_bound_less_the_service(self):
        with render_node_table():
            self._worker_bound()

    def _worker_bound(self):
        plan = harness.forced_plan(harness.PAIRS['chain4x'], CAP)
        self.assertFalse(any(s.split_finish for s in plan.stages))           # the premise
        m = R.plan_marks(plan, CAP)
        self.assertEqual(m['service_gb'], banded_plan.SERVICE_GB)
        self.assertIn('alone', m['worker_bound_rule'])
        for row, st in zip(m['stages'], plan.stages):
            up = banded_plan.stage_peaks(st, plan.banded['machine_class'], False)['up'][0]
            self.assertEqual(row['peak_upper_gb'], round(up, 2))                         # unchanged: the service Job's
            self.assertEqual(row['worker_peak_upper_gb'], round(up - banded_plan.SERVICE_GB, 2))
            self.assertNotIn('parts', row)
        self.assertNotIn('service_gb', R.plan_marks(harness.forced_plan(harness.PAIRS['k4'], CAP), CAP)['stages'][0])

    def test_a_split_stage_has_a_bound_per_part(self):
        # the banded exact finish's bounds (contract finish_tier): under the shipped tier 3 the whole finish binds part B at
        # the workstation cap, so 'A binds at the decode' holds only where the BXF is counted (build wave 2 merge)
        with mock.patch.object(banded_plan, 'BXF_AVAILABLE', True, create=True):
            self._parts()

    def _parts(self):
        for name, stages in harness.PAIRS.items():
            plan = harness.forced_plan(stages, WS_CAP)
            m = R.plan_marks(plan, WS_CAP)
            for row, st in zip(m['stages'], plan.stages):
                self.assertTrue(row['split_finish'], name)
                ph = banded_plan.stage_peaks(st, plan.banded['machine_class'], True)['phases_up']
                a, b = row['parts']['A'], row['parts']['B']
                self.assertEqual(a['phases'], ['P0', 'sampling', 'decode'])
                self.assertEqual(b['phases'], ['finish'])
                self.assertEqual(a['peak_upper_gb'], round(max(ph['P0'], ph['sampling'], ph['decode']), 2))
                self.assertEqual(b['peak_upper_gb'], round(ph['finish'], 2))
                self.assertEqual(a['worker_peak_upper_gb'],
                                 round(max(ph['P0'], ph['sampling'], ph['decode']) - banded_plan.SERVICE_GB, 2))
                self.assertEqual(b['worker_peak_upper_gb'], round(ph['finish'] - banded_plan.SERVICE_GB, 2))
                self.assertEqual(a['peak_upper_gb'], row['peak_upper_gb'])              # A binds at the decode
                self.assertLess(b['peak_upper_gb'], a['peak_upper_gb'])
                self.assertEqual(row['parts_source'], 'banded_plan.stage_peaks phases_up')

    def test_part_bounds_without_phase_bounds_fall_back_to_the_stage_upper(self):
        plan = harness.forced_plan(harness.PAIRS['k4'], WS_CAP)
        real = banded_plan.stage_peaks

        def no_phases(*a, **k):
            r = dict(real(*a, **k))
            r.pop('phases_up')
            return r
        with mock.patch.object(banded_plan, 'stage_peaks', no_phases):
            row = R.plan_marks(plan, WS_CAP)['stages'][0]
        self.assertEqual(row['parts']['B']['peak_upper_gb'], row['peak_upper_gb'])
        self.assertIn('no phase bounds', row['parts_source'])

    def memory(self, cap, workers):
        plan = harness.forced_plan(harness.PAIRS['chain4x'], cap)
        return R.plan_marks(plan, cap), R.memory_check(R.plan_marks(plan, cap), workers)

    def test_memory_check_per_worker_and_segment(self):
        with render_node_table():
            self._per_worker()

    def _per_worker(self):
        m, r = self.memory(CAP, [{'n': 0, 'segments': [[0, None], [1, None]], 'job_peak_bytes': int(30 * 2 ** 30)}])
        self.assertFalse(any(s['split_finish'] for s in m['stages']))        # the premise
        b = max(m['stages'][0]['worker_peak_upper_gb'], m['stages'][1]['worker_peak_upper_gb'])
        self.assertTrue(r['pass'], r)
        self.assertEqual(r['workers'][0]['bound_gb'], b)
        self.assertIn('never subtracted', r['rule'])
        over_gb = m['stages'][0]['worker_peak_upper_gb'] + 1.0          # just over stage 0's worker bound
        _, over = self.memory(CAP, [{'n': 0, 'segments': [[0, None]], 'job_peak_bytes': int(over_gb * 2 ** 30)}])
        self.assertFalse(over['pass'])
        self.assertEqual(over['workers'][0]['fails'], ['peak over the bound'])
        _, none = self.memory(CAP, [{'n': 0, 'segments': [[0, None]], 'job_peak_bytes': None}])
        self.assertFalse(none['pass'])
        self.assertEqual(none['workers'][0]['fails'], ['the Job peak was not measured'])
        self.assertFalse(R.memory_check(m, [])['pass'])

    def test_memory_check_of_split_workers_uses_their_parts(self):
        m, r = self.memory(WS_CAP, [
            {'n': 0, 'segments': [[0, 'A']], 'job_peak_bytes': int(20 * 2 ** 30)},
            {'n': 1, 'segments': [[0, 'B'], [1, 'A']], 'job_peak_bytes': int(20 * 2 ** 30)},
            {'n': 2, 'segments': [[1, 'B']], 'job_peak_bytes': int(20 * 2 ** 30)}])
        s0, s1 = m['stages']
        self.assertEqual([w['bound_gb'] for w in r['workers']], [
            s0['parts']['A']['worker_peak_upper_gb'],
            max(s0['parts']['B']['worker_peak_upper_gb'], s1['parts']['A']['worker_peak_upper_gb']),
            s1['parts']['B']['worker_peak_upper_gb']])
        self.assertTrue(r['pass'])
        _, wrong = self.memory(WS_CAP, [{'n': 0, 'segments': [[0, None]], 'job_peak_bytes': 1}])
        self.assertEqual(wrong['workers'][0]['fails'], ['no registered bound for a segment this worker ran'])
        self.assertIsNone(R.segment_bound_gb(m, 0, 'C'))
        m59, _ = self.memory(CAP, [])
        self.assertIsNone(R.segment_bound_gb(m59, 0, 'A'))                   # a part of a stage the plan does not split


class Sealing(unittest.TestCase):
    def doc(self):
        plan = harness.forced_plan(harness.PAIRS['k4'], CAP)
        st = harness.PAIRS['k4'][0]
        g, _ = harness.classic_graph(st)
        return R.registration('R1-k4', build={'tree_sha256': 'ab' * 32}, marks=[
            R.mark('plan', R.plan_marks(plan, CAP), 'equal to the run record'),
            R.mark('graph_sha256', {'pass1': harness.graph_sha(g)}, 'equal to the submitted graph'),
            R.mark('pixels', {'expect': 'zero', 'reference': 'classic 5.0.1 on the same card'}, '0 differing values per phase'),
        ])

    def test_write_once_and_verify(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'registered-R1-k4.json'
            sha = R.write_registration(p, self.doc())
            self.assertEqual(len(sha), 64)
            self.assertEqual(R.verify(p), [])
            with self.assertRaises(FileExistsError):
                R.write_registration(p, self.doc())

    def test_a_moved_mark_is_detected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'registered.json'
            R.write_registration(p, self.doc())
            d1 = json.loads(p.read_text(encoding='utf8'))
            d1['marks'][2]['value']['expect'] = 'tier01'
            p.write_text(json.dumps(d1), encoding='utf8')
            problems = R.verify(p)
            self.assertTrue(any('pixels' in x for x in problems), problems)
            d2 = json.loads(p.read_text(encoding='utf8'))
            d2['marks'][2]['value']['expect'] = 'zero'
            d2['marks'][2]['rule'] = 'loosened'
            self.assertTrue(any('pixels' in x for x in R.verify(d2)))

    def test_moved_between_two_registrations(self):
        a = R.seal(self.doc())
        b = R.seal(self.doc())
        self.assertEqual(R.moved_marks(a, b), [])
        c = self.doc()
        c['marks'][1]['value']['pass1'] = '00' * 32
        self.assertEqual(R.moved_marks(a, R.seal(c)), ['graph_sha256'])

    def test_registered_before_the_result(self):
        s = R.seal(self.doc(), registered_at='2026-11-21T10:00:00+11:00')
        self.assertTrue(R.registered_before(s, '2026-11-21T10:00:01+11:00'))
        self.assertFalse(R.registered_before(s, '2026-11-21T09:59:59+11:00'))
        self.assertFalse(R.registered_before(s, '2026-11-20T23:00:00+00:00'))


if __name__ == '__main__':
    unittest.main()
