"""The SAM phase's 'gate' role (D7): compared against the Large-image finish's own gate plane where the finish exposes one,
else derived from both executors' unions and labelled union-derived (adding nothing beyond the union roles)."""
import tempfile
import unittest
from pathlib import Path

from tools.proof import harness, phase_run


class GateSource(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.work = Path(self._t.name)
        self.calls = []
        self.c = {'spec': {'gate': {'dilate': 12, 'feather': 4.0}}}
        self.st = harness.PAIRS['k4'][0]

    def tearDown(self):
        self._t.cleanup()

    def gate_fn(self, union, release, dilate, feather, out):
        self.calls.append((union, release, dilate, feather, str(out)))

    def test_without_a_finish_gate_both_are_derived_and_labelled(self):
        c, b = {'union/protect': {'path': 'c/u'}}, {'union/protect': {'path': 'b/u'}}
        rec = phase_run._gate_roles(c, b, self.c, self.st, self.work, self.gate_fn)
        self.assertEqual(rec['source'], 'union-derived')
        self.assertEqual([x[0] for x in self.calls], ['c/u', 'b/u'])
        self.assertTrue(c['gate']['derived'] and b['gate']['derived'])

    def test_the_finish_gate_plane_is_compared_when_the_finish_exposes_one(self):
        own = {'kind': 'plane', 'path': 'b/gate.plane', 'form': 'bitwise'}
        c, b = {'union/protect': {'path': 'c/u'}}, {'union/protect': {'path': 'b/u'}, 'gate': dict(own)}
        rec = phase_run._gate_roles(c, b, self.c, self.st, self.work, self.gate_fn)
        self.assertEqual(rec['source'], 'the finish gate plane')
        self.assertEqual([x[0] for x in self.calls], ['c/u'])                 # only the classic's is derived
        self.assertEqual(b['gate'], own)
        self.assertTrue(c['gate']['derived'])

    def test_no_union_no_gate(self):
        rec = phase_run._gate_roles({}, {}, self.c, self.st, self.work, self.gate_fn)
        self.assertIsNone(rec['source'])
        self.assertEqual(self.calls, [])


if __name__ == '__main__':
    unittest.main()
