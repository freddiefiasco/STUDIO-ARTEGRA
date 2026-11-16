import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from engine import controls, fast_recipe, graph_v5t
from service import engine_options as eo

PACKET = Path(os.environ.get('CU_FAST_FIX_PACKET') or Path(__file__).resolve().parent / 'no-fast-fix-packet')
R_OWN = 'H8-e8-s25-c5-p3-k+so16+stk'


class Factor(unittest.TestCase):
    def env(self, split):
        return mock.patch.dict(os.environ, {'CU_FAST_SPLIT': split, 'CU_FAST': '1'})

    def test_the_share_is_the_measured_one(self):
        self.assertEqual(eo.ETA_FAST_SAMPLING, {R_OWN: round(211.4 / 1269.4, 3)})
        self.assertEqual(eo.ETA_FAST_SAMPLING[R_OWN], 0.167)
        self.assertEqual(fast_recipe.RECIPE['name'], R_OWN)


        self.assertEqual(eo.FAST_SPLIT_SAMPLING_FACTOR, 1.59)
        self.assertTrue(eo.FAST_SPLIT_PROVEN)

    def test_the_build_as_it_ships(self):
        with mock.patch.dict(os.environ, {'CU_FAST': '1'}):
            os.environ.pop('CU_FAST_SPLIT', None)
            self.assertEqual(eo.eta_factor(mode='fast', cards=2), round(0.37 - 0.167 * (1 - 1 / 1.59), 3))
            self.assertEqual(eo.eta_factor(mode='fast', cards=2), 0.308)
            self.assertEqual(eo.eta_factor(mode='fast', cards=1), 0.37)
            self.assertEqual(eo.run_info('fast', split=True, cards=2)['factor'], 0.308)
            f = eo.finish_info(100, fast_available=True, cards={'standard': 2, 'fast': 2})
            self.assertEqual(f['fast'], {'minutes': 37.0, 'factor': 0.37})
            self.assertEqual(f['single']['fast'], {'minutes': 30.8, 'factor': 0.308, 'cards': 2})
        with self.env('0'):
            self.assertEqual(eo.eta_factor(mode='fast', cards=2), 0.37)

    def test_no_two_card_credit_while_the_flag_is_off(self):
        with self.env('0'), mock.patch.object(eo, 'FAST_SPLIT_SAMPLING_FACTOR', 1.3):
            self.assertEqual(eo.eta_factor(mode='fast', cards=2), 0.37)
            self.assertEqual(eo.run_info('fast', split=True, cards=2)['factor'], 0.37)
            f = eo.finish_info(100, fast_available=True, cards={'standard': 2, 'fast': 2})
            self.assertEqual(f['single']['fast'], {'minutes': 37.0, 'factor': 0.37, 'cards': 2})

    def test_no_credit_until_fs2_measures_the_factor(self):


        with self.env('1'), mock.patch.object(eo, 'FAST_SPLIT_SAMPLING_FACTOR', None):
            self.assertEqual(eo.eta_factor(mode='fast', cards=2), 0.37)
            self.assertEqual(eo.run_info('fast', split=True, cards=2)['factor'], 0.37)

    def test_the_shared_figure_once_measured(self):
        want = round(0.37 - 0.167 * (1 - 1 / 1.3), 3)
        self.assertEqual(want, 0.331)
        with self.env('1'), mock.patch.object(eo, 'FAST_SPLIT_SAMPLING_FACTOR', 1.3):
            self.assertEqual(eo.eta_factor(mode='fast', cards=2), want)
            self.assertEqual(eo.eta_factor(mode='fast', cards=1), 0.37)
            self.assertEqual(eo.run_info('fast', split=True, cards=2)['factor'], want)
            self.assertEqual(eo.run_info('fast', split=False, cards=2)['factor'], 0.37)
            f = eo.finish_info(100, fast_available=True, cards={'standard': 2, 'fast': 2})
            self.assertEqual(f['fast'], {'minutes': 37.0, 'factor': 0.37})
            self.assertEqual(f['single']['fast'], {'minutes': 33.1, 'factor': want, 'cards': 2})
            self.assertEqual(f['single']['standard'], {'minutes': 52.3, 'factor': 0.523, 'cards': 2})

    def test_a_recipe_with_no_measured_share_gets_no_credit(self):
        d = dict(fast_recipe.describe(), recipe='another-recipe')
        with self.env('1'), mock.patch.object(eo, 'FAST_SPLIT_SAMPLING_FACTOR', 1.3), \
                mock.patch.object(fast_recipe, 'describe', return_value=d):
            self.assertEqual(eo.eta_factor(mode='fast', cards=2), float(d['factor']))

    def test_standard_is_unchanged(self):
        for split in ('0', '1'):
            with self.env(split), mock.patch.object(eo, 'FAST_SPLIT_SAMPLING_FACTOR', 1.3):
                self.assertEqual([eo.eta_factor(True), eo.eta_factor(True, 2), eo.eta_factor(False), eo.eta_factor(False, 2)],
                                 [0.7, 0.523, 0.947, 0.747])
                self.assertEqual(eo.run_info('standard', split=True, cards=2)['factor'], 0.523)


CASES = [
    ('fast', 'Light', 1024, 768, {}), ('fast', 'Default', 1024, 768, {}), ('fast', 'Default', 2048, 2048, {}),
    ('standard', 'Default', 1024, 768, {'speed_stack': True, 'creative_first': False}),
    ('standard', 'Default', 1024, 768, {'speed_stack': True, 'creative_first': True}),
    ('standard', 'Default', 2048, 2048, {'speed_stack': True, 'creative_first': False}),
    ('standard', 'Strong', 1024, 768, {'speed_stack': False, 'creative_first': False}),
]

BUILD = r'''
import json, sys
from engine import controls, fast_recipe, graph_v5t
out = []
for kind, look, w, h, opts in json.loads(sys.argv[1]):
    pk = controls.stage_params(controls.resolve({'preset': look, 'scale': 2})[0], 0)
    if kind == 'fast':
        g, info = fast_recipe.build('x.png', w, h, pk, 'x', live_preview='detailed')
    else:
        g, info = graph_v5t.build_product('x.png', w, h, pk, 'x', live_preview='detailed', **opts)
    out.append([g, graph_v5t.add_multigpu(g, 2, balance='auto')])
print(json.dumps(out, sort_keys=True))
'''


def build_here():
    out = []
    for kind, look, w, h, opts in CASES:
        pk = controls.stage_params(controls.resolve({'preset': look, 'scale': 2})[0], 0)
        if kind == 'fast':
            g, _ = fast_recipe.build('x.png', w, h, pk, 'x', live_preview='detailed')
        else:
            g, _ = graph_v5t.build_product('x.png', w, h, pk, 'x', live_preview='detailed', **opts)
        out.append([g, graph_v5t.add_multigpu(g, 2, balance='auto')])
    return json.loads(json.dumps(out, sort_keys=True))


@unittest.skipUnless((PACKET / 'engine' / 'fast_recipe.py').is_file(), 'the FAST FIX packet is not part of this repository (set CU_FAST_FIX_PACKET)')
class Graphs(unittest.TestCase):
    def test_one_card_and_shared_graphs_equal_the_proven_packets(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith(('CU_', 'CLAUDE_'))}
        p = subprocess.run([sys.executable, '-B', '-c', BUILD, json.dumps(CASES)], cwd=str(PACKET), env=env,
                           capture_output=True, text=True, timeout=300)
        self.assertEqual(p.returncode, 0, p.stderr[-2000:])
        theirs, ours = json.loads(p.stdout), build_here()
        self.assertEqual(len(ours), len(CASES))
        for case, a, b in zip(CASES, ours, theirs):
            self.assertEqual(a[0], b[0], f'one card: {case}')
            self.assertEqual(a[1], b[1], f'two cards: {case}')

        g1, g2 = ours[1]
        added = {k for k in g2 if k not in g1}
        self.assertEqual([g2[k]['class_type'] for k in added], ['MultiGPU_WorkUnits'])
        spot = next(k for k, v in g1.items() if v['class_type'] == 'ClaudeSpotTiles')
        self.assertEqual({k: v for k, v in g2[spot]['inputs'].items() if k not in ('window_split', 'balance', 'weights')},
                         g1[spot]['inputs'])
        lora = [v for v in g2.values() if v['class_type'] == 'LoraLoaderModelOnly']
        self.assertEqual(len(lora), 1)


if __name__ == '__main__':
    unittest.main()
