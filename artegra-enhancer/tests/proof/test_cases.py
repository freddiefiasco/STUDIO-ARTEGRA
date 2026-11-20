"""tools/proof/cases.py: the case table's shape, the job bodies of the release path and the force switch, and the held-equal
check that voids a pair. Case ids, inputs and machines here are placeholders."""
import copy
import unittest

from engine import controls
from tools.proof import cases, harness

TABLE = {'seeds': {'A': 1001, 'B': 2002}, 'cases': [
    {'id': 'K1', 'mode': 'redux', 'factor': 2, 'supersamples': [2], 'input': 'in-1', 'node': 'node-a', 'card': 0,
     'runs': ['bes_a', 'classic_b'], 'reuse': {'classic_a': 'r0-record'}},
    {'id': 'K2', 'mode': 'bolt', 'factor': 2, 'supersamples': [2], 'input': 'in-2', 'node': 'node-b', 'card': 0,
     'runs': ['classic_a', 'bes_a', 'classic_b']},
]}


class Table(unittest.TestCase):
    def test_valid_and_invalid(self):
        self.assertEqual(cases.validate_case_table(TABLE), [])
        t = copy.deepcopy(TABLE)
        t['seeds']['B'] = 1001
        t['cases'][1]['factor'] = 4
        t['cases'][0]['runs'] = ['bes_a']
        errs = cases.validate_case_table(t)
        self.assertTrue(any('differ' in e for e in errs))
        self.assertTrue(any('Bolt runs 2x' in e for e in errs))
        self.assertTrue(any('made or reused' in e for e in errs))


class Bodies(unittest.TestCase):
    def test_release_path_and_force_switch_differ_only_by_the_switch(self):
        c = TABLE['cases'][0]
        a = cases.job_body(c, 'classic_a', 'm1', TABLE['seeds'], 'r1')
        x = cases.job_body(c, 'bes_a', 'm1', TABLE['seeds'], 'r2')
        b = cases.job_body(c, 'classic_b', 'm1', TABLE['seeds'], 'r3')
        self.assertNotIn('dev_force_engine', a)
        self.assertEqual(x.pop('dev_force_engine'), 'banded')
        self.assertEqual(a['settings'], x['settings'])
        self.assertEqual(b['settings']['seed'], 2002)
        self.assertEqual(a['settings']['seed'], 1001)
        self.assertEqual(cases.job_body(TABLE['cases'][1], 'classic_a', 'm', TABLE['seeds'], 'r')['settings']['mode'], 'fast')
        controls.resolve(a['settings'])                    # the service accepts these settings
        with self.assertRaises(ValueError):
            cases.job_body(c, 'bes_b', 'm1', TABLE['seeds'], 'r4')


def rec(run, **kw):
    plan = harness.forced_plan(harness.PAIRS['k4'], 59.0).to_dict()
    if run != 'bes_a':
        plan = dict(plan)
        plan.pop('engine', None)
        plan.pop('banded', None)
    job = {'settings': {'scale': 2, 'seed': 2002 if run == 'classic_b' else 1001, 'mode': 'standard'}}
    if run == 'bes_a':
        job['dev_force_engine'] = 'banded'
    r = cases.run_record('K1', run, job, {'sha256': 'in' * 32, 'plan': plan}, {'tree': 't'},
                         {'torch_threads': 24, 'omp_mkl': {}}, 0, 'node-a')
    r.update(kw)
    return r


class Held(unittest.TestCase):
    def test_a_proper_case_is_not_void(self):
        r = cases.check_case({'classic_a': rec('classic_a'), 'bes_a': rec('bes_a'), 'classic_b': rec('classic_b')})
        self.assertFalse(r['void'], r)
        self.assertTrue(r['plan_forced_ok'])

    def test_differing_threads_card_or_seed_void_the_case(self):
        for run, kw, what in (('bes_a', {'threads': {'torch_threads': 12, 'omp_mkl': {}}}, 'threads'),
                              ('bes_a', {'card': 1}, 'card'), ('bes_a', {'seed': 7}, 'seed'),
                              ('classic_b', {'node': 'node-b'}, 'node')):
            recs = {'classic_a': rec('classic_a'), 'bes_a': rec('bes_a'), 'classic_b': rec('classic_b')}
            recs[run] = rec(run, **kw)
            r = cases.check_case(recs)
            self.assertTrue(r['void'], what)
            self.assertIn(what, r['classic_vs_bes'] + r['classic_a_vs_b'])

    def test_a_bes_run_without_the_forced_plan_is_void(self):
        x = rec('bes_a', forced=None)
        r = cases.check_case({'classic_a': rec('classic_a'), 'bes_a': x, 'classic_b': rec('classic_b')})
        self.assertTrue(r['void'])
        self.assertFalse(r['plan_forced_ok'])


if __name__ == '__main__':
    unittest.main()
