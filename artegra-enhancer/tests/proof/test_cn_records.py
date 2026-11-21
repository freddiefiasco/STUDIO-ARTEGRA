"""ControlNet call records in the phase diff: None output slots (D6) and the hint crops of each call (D8, T3, Q1), so a
hint-layout difference is told apart from a ControlNet difference. Records as tools/proof/comfy_nodes/cu_proof writes them;
numpy only (the instrumentation's own test, tests/proof/test_instrument, runs it under torch)."""
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from tools.proof import harness_io, phases


def call(sha, files=None, dtypes=None, layout=None):
    c = {'sha256': list(sha), 'dtypes': dtypes or ['torch.float16' if s else None for s in sha]}
    if files is not None:
        c['files'] = files
    if layout is not None:
        c['layout'] = layout
    return c


class NoneSlots(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.d = Path(self._t.name)

    def tearDown(self):
        self._t.cleanup()

    def bin(self, name, arr):
        p = self.d / name
        np.asarray(arr).tofile(p)
        return str(p)

    def test_none_on_both_sides_is_skipped_and_the_tensor_slot_counted_exactly(self):
        x = np.arange(8, dtype=np.float16)
        y = x.copy()
        y[3] += 1
        a = {'kind': 'cn', 'calls': [call(['ha', None], [self.bin('a0', x), None])]}
        b = {'kind': 'cn', 'calls': [call(['hb', None], [self.bin('b0', y), None])]}
        r = phases.compare_entries(a, b, 'cn')
        self.assertEqual((r['count'], r['exact'], r['first_call']), (1, True, 0))

    def test_none_against_a_tensor_is_a_difference(self):
        x = np.arange(8, dtype=np.float16)
        a = {'kind': 'cn', 'calls': [call(['h0', None], [self.bin('a0', x), None])]}
        b = {'kind': 'cn', 'calls': [call(['h0', 'h1'], [self.bin('b0', x), self.bin('b1', x)])]}
        r = phases.compare_entries(a, b, 'cn')
        self.assertEqual(r['count'], 1)
        self.assertFalse(r['exact'])
        self.assertEqual(r['first_call'], 0)

    def test_equal_slots_with_a_none_are_zero(self):
        a = {'kind': 'cn', 'calls': [call(['h0', None])]}
        self.assertEqual(phases.compare_entries(a, json.loads(json.dumps(a)), 'cn')['count'], 0)

    def test_none_slots_without_values_still_compare_by_hash(self):
        a = {'kind': 'cn', 'calls': [call(['h0', None])]}
        b = {'kind': 'cn', 'calls': [call(['h9', None])]}
        r = phases.compare_entries(a, b, 'cn')
        self.assertEqual((r['count'], r['exact']), (1, False))


class HintCrops(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.d = Path(self._t.name)

    def tearDown(self):
        self._t.cleanup()

    def write(self, prompt, evs):
        p = self.d / prompt
        p.mkdir()
        with open(p / 'events.jsonl', 'w', encoding='utf8') as f:
            for e in evs:
                f.write(json.dumps(e) + '\n')
        return p

    def hint_ev(self, sha, n, layout):
        return {'type': 'cn', 'role': 'cn_hint/ks1/0', 'call': n, 'keys': ['cond_hint'], 'sha256': [sha],
                'dtypes': ['torch.float16'], 'shapes': [[1, 3, 64, 64]], 'files': None, 'layout': [layout]}

    def test_the_hint_role_is_in_the_hints_phase_and_compared_as_cn(self):
        self.assertEqual(phases.phase_of('cn_hint/ks1/0'), 'hints')
        self.assertEqual(phases.form_of('cn_hint/ks1/0'), 'cn')

    def test_hint_records_are_collected_and_old_events_still_load(self):
        lay = {'device': 'cuda:0', 'contiguous': True, 'channels_last': False, 'stride': [12288, 4096, 64, 1]}
        evs = [self.hint_ev('h0', 0, lay), self.hint_ev('h1', 1, lay),
               {'type': 'cn', 'role': 'cn/ks1/0', 'call': 0, 'sha256': ['o0'], 'dtypes': ['torch.float16']}]
        man = harness_io.collect(self.write('p1', evs))
        self.assertEqual(sorted(man['roles']), ['cn/ks1/0', 'cn_hint/ks1/0'])
        self.assertEqual(man['errors'], [])
        h = man['roles']['cn_hint/ks1/0']
        self.assertEqual([c['sha256'] for c in h['calls']], [['h0'], ['h1']])
        self.assertEqual(h['calls'][0]['layout'], [lay])
        self.assertIsNone(man['roles']['cn/ks1/0']['calls'][0].get('files'))      # absent key read as None

    def test_a_hint_crop_difference_is_located_apart_from_the_controlnet_outputs(self):
        lay = {'device': 'cuda:0', 'contiguous': True, 'channels_last': False, 'stride': [1]}
        c = {'cn/ks1/0': {'kind': 'cn', 'calls': [call(['o0'])]},
             'cn_hint/ks1/0': {'kind': 'cn', 'calls': [call(['h0'], layout=[lay])]}}
        b = {'cn/ks1/0': {'kind': 'cn', 'calls': [call(['o1'])]},
             'cn_hint/ks1/0': {'kind': 'cn', 'calls': [call(['h1'], layout=[lay])]}}
        rep = phases.count(c, b)
        roles = next(p for p in rep['phases'] if p['phase'] == 'hints')['roles']
        self.assertEqual(roles['cn_hint/ks1/0']['count'], 1)       # the crops differ: the layout, not the model
        b['cn_hint/ks1/0'] = c['cn_hint/ks1/0']
        rep = phases.count(c, b)
        roles = next(p for p in rep['phases'] if p['phase'] == 'hints')['roles']
        self.assertEqual(roles['cn_hint/ks1/0']['count'], 0)       # same crops, different outputs: the ControlNet
        self.assertEqual(roles['cn/ks1/0']['count'], 1)

    def test_a_memory_layout_difference_alone_is_reported_not_counted(self):
        l1 = {'device': 'cuda:0', 'contiguous': True, 'channels_last': False, 'stride': [12288, 4096, 64, 1]}
        l2 = {'device': 'cuda:0', 'contiguous': False, 'channels_last': True, 'stride': [12288, 1, 192, 3]}
        a = {'kind': 'cn', 'calls': [call(['h0'], layout=[l1])]}
        b = {'kind': 'cn', 'calls': [call(['h0'], layout=[l2])]}
        r = phases.compare_entries(a, b, 'cn')
        self.assertEqual(r['count'], 0)
        self.assertEqual(r['layout_differs'], [0])

    def test_check_complete_wants_hint_records_once_the_spec_asks(self):
        spec = {'roles': {}, 'files': {}, 'cn': {'nodes': {'7': 'ks1'}, 'hints': True}}
        man = {'roles': {'cn/ks1/0': {}}}
        self.assertEqual(harness_io.check_complete(man, spec), ['cn_hint/ks1/*'])
        man['roles']['cn_hint/ks1/0'] = {}
        self.assertEqual(harness_io.check_complete(man, spec), [])
        spec['cn'].pop('hints')                                      # an earlier spec: hints were not recorded
        self.assertEqual(harness_io.check_complete({'roles': {'cn/ks1/0': {}}}, spec), [])


if __name__ == '__main__':
    unittest.main()
