"""tools/proof/phase_run.compare_sides: the identity of two kept sides of ONE executor (W5a's cross-card BES against W1b's
BES; R5's emulated-card BES against the uncapped BES), on the stand-in engine of test_phase_run (no ComfyUI, no GPU). Equal
runs read 0 everywhere; one changed value is found at its first phase; sides of another executor, seed or plan, or a side
that did not run, are refused."""
import tempfile
import unittest
from pathlib import Path

from tests.proof.test_phase_run import CHAIN, SMALL, FakeEngine, u8
from tools.proof import phase_run


def side(d, name, executor='bes', stages=SMALL, cap=59.0, seed=None, **fake):
    def launcher(ex, rd):
        return FakeEngine(ex, rd, **fake)
    src = u8('source', (stages[0].h, stages[0].w, 3))
    return phase_run.run_side('t', stages, cap, src, Path(d) / name, launcher, executor, seed=seed)


class CompareSides(unittest.TestCase):
    def test_two_equal_bes_sides_read_zero_in_every_phase(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = side(d, 'c0'), side(d, 'c1')
            rep = phase_run.compare_sides('t', SMALL, 59.0, a, b)
        self.assertTrue(rep['pass'], rep.get('error') or rep['stages'])
        self.assertEqual(rep['mode'], 'same:bes')
        row = rep['stages'][0]
        self.assertTrue(row['phase_diff']['zero'])
        roles = {r for p in row['phase_diff']['phases'] for r in p['roles']}
        self.assertIn('stage_output', roles)                  # the BES's own output, compared with the other BES's
        self.assertTrue(all(v['form'] == 'bitwise' for p in row['phase_diff']['phases'] for k, v in p['roles'].items()
                            if not k.startswith(('cn/', 'cn_hint/'))))
        self.assertEqual(row['stage_output_sha256']['a'], row['stage_output_sha256']['b'])
        self.assertTrue(rep['memory']['a']['pass'] and rep['memory']['b']['pass'])

    def test_one_changed_value_is_found_at_its_first_phase(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = side(d, 'c0', stages=CHAIN), side(d, 'c1', stages=CHAIN, change={'raw8'})
            rep = phase_run.compare_sides('t', CHAIN, 59.0, a, b)
        self.assertFalse(rep['pass'])
        self.assertEqual([s['phase_diff']['first_differing_phase'] for s in rep['stages']], ['decodes', 'decodes'])
        dec = next(p for p in rep['stages'][0]['phase_diff']['phases'] if p['phase'] == 'decodes')
        self.assertEqual(dec['differing'], 1)

    def test_a_classic_side_or_a_different_seed_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            a, c = side(d, 'c0'), side(d, 'cl', executor='classic')
            rep = phase_run.compare_sides('t', SMALL, 59.0, a, c)
            self.assertFalse(rep['pass'])
            self.assertIn("not 'bes'", rep['error'])
            s2 = side(d, 's2', seed=20261120)
            rep = phase_run.compare_sides('t', SMALL, 59.0, a, s2)
            self.assertFalse(rep['pass'])
            self.assertIn('differ in seed', rep['error'])
            rep = phase_run.compare_sides('t', SMALL, 122.2, a, side(d, 'c1'))
            self.assertIn('not of this pair, cap and plan', rep['error'])

    def test_a_side_whose_stage_failed_fails_the_identity(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = side(d, 'c0'), side(d, 'c1', fail='bes')
            rep = phase_run.compare_sides('t', SMALL, 59.0, a, b)
        self.assertFalse(rep['pass'])
        self.assertEqual(rep['stages'][0]['error'], 'a run of this stage did not finish')

    def test_a_role_on_one_side_only_differs(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = side(d, 'c0'), side(d, 'c1', drop=('raw8',))
            rep = phase_run.compare_sides('t', SMALL, 59.0, a, b)
        self.assertFalse(rep['pass'])
        self.assertIn('raw8', rep['stages'][0]['phase_diff']['missing'])


if __name__ == '__main__':
    unittest.main()
