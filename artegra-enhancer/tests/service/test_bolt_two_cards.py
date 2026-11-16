"""Two-card Bolt: a lone Bolt image shares two cards only on the hardware that sharing was proven on (two identical
desktop RTX 5090 cards with the original memory settings). Everywhere else Bolt runs one image per card, and the finish
time says so. Redux keeps its own rules."""
import unittest

from service import memory_policy
from tests.service.test_fast_split import TwoCardBase
from tests.service.test_fast_v5 import NO_OVERRIDES

RTX5090 = 'NVIDIA GeForce RTX 5090'


def card(i, name=RTX5090, total=31.84):
    return {'index': i, 'name': name, 'mem_total_gb': total, 'mem_free_gb': total - 1}


class Predicate(unittest.TestCase):
    def test_two_identical_desktop_5090_cards_with_original_settings_share(self):
        self.assertTrue(memory_policy.fast_share_hardware([card(0), card(1)], [0, 1], 'auto'))
        self.assertTrue(memory_policy.fast_share_hardware([card(0), card(1)], [1, 0], 'reference'))

    def test_everything_else_runs_one_image_per_card(self):
        f = memory_policy.fast_share_hardware
        self.assertFalse(f([card(0), card(1)], [0, 1], 'balanced'))
        self.assertFalse(f([card(0), card(1, 'NVIDIA GeForce RTX 4090', 23.99)], [0, 1], 'auto'))
        self.assertFalse(f([card(0, RTX5090 + ' Laptop GPU', 23.9), card(1, RTX5090 + ' Laptop GPU', 23.9)], [0, 1], 'auto'))
        self.assertFalse(f([card(0, total=24.0), card(1, total=24.0)], [0, 1], 'reference'))
        self.assertFalse(f([card(0), card(1), card(2)], [0, 1, 2], 'auto'))
        self.assertFalse(f([card(0)], [0], 'auto'))
        self.assertFalse(f([card(0), card(1)], [0], 'auto'))
        self.assertFalse(f([card(0), card(1, total=30.0)], [0, 1], 'auto'))
        self.assertFalse(f([card(0), card(1)], [0, 5], 'auto'))
        self.assertFalse(f([card(0), dict(card(1), mem_total_gb=None)], [0, 1], 'auto'))
        self.assertFalse(f([card(0), card(1)], [0, 1], 'compact'))
        self.assertFalse(f([], [], 'auto'))


class OtherCards(TwoCardBase):
    runs = 0

    def fast_split(self, settings=None, gpus='2', **env):
        OtherCards.runs += 1
        self.svc = self.service(env=dict(NO_OVERRIDES, CU_FAKE_STAGE_SECONDS='1', CU_FAKE_GPUS=gpus, CU_FAST='1', **env),
                                settings=settings or {}, state=f'state-{OtherCards.runs}')
        h = self.health()
        self.assertTrue(h['engine']['fast']['available'], h['engine']['fast'])
        return h['engine']['fast']['split']

    def test_cards_the_proof_did_not_run_on_take_one_image_each(self):
        self.two_cards(CU_FAST='1', CU_FAKE_GPU_NAME='Test graphics card')
        h = self.health()
        self.assertEqual((h['engine']['fast']['available'], h['engine']['fast']['split']), (True, False))
        m, f = self.plan_single()
        self.assertEqual(f['single']['fast'], {'minutes': round(m * 0.37, 1), 'factor': 0.37, 'cards': 1})
        self.assertEqual(f['single']['standard'], {'minutes': round(m * 0.523, 1), 'factor': 0.523, 'cards': 2})
        self.lanes(self.inputs(2))
        self.assertEqual(self.svc.shutdown(), 0)

    def test_laptop_mixed_small_or_three_cards_do_not_share(self):
        for env in ({'CU_FAKE_GPU_NAME': RTX5090 + ' Laptop GPU', 'CU_FAKE_GPU_MEM_GB': '23.9'},
                    {'CU_FAKE_GPU_NAME': RTX5090 + '|NVIDIA GeForce RTX 4090'},
                    {'CU_FAKE_GPU_NAME': RTX5090, 'CU_FAKE_GPU_MEM_GB': '24'},
                    {'CU_FAKE_GPU_NAME': RTX5090, 'gpus': '3'}):
            with self.subTest(env=env):
                self.assertIs(self.fast_split(**dict(env)), False)
                m, f = self.plan_single()
                self.assertEqual(f['single']['fast']['cards'], 1)
                self.assertEqual(self.svc.shutdown(), 0)

    def test_save_gpu_memory_keeps_bolt_on_one_card(self):
        self.assertIs(self.fast_split(CU_FAKE_GPU_NAME=RTX5090), True)
        code, saved, _ = self.svc.post('/api/settings', {'memory_profile': 'balanced'})
        self.assertEqual(code, 200, saved)
        self.assertIs(self.health()['engine']['fast']['split'], False)
        m, f = self.plan_single()
        self.assertEqual(f['single']['fast'], {'minutes': round(m * 0.37, 1), 'factor': 0.37, 'cards': 1})
        self.assertEqual(self.svc.shutdown(), 0)

    def test_the_proven_cards_share(self):
        self.assertIs(self.fast_split(CU_FAKE_GPU_NAME=RTX5090), True)
        m, f = self.plan_single()
        self.assertEqual(f['single']['fast'], {'minutes': round(m * 0.308, 1), 'factor': 0.308, 'cards': 2})
        self.assertEqual(self.svc.shutdown(), 0)


if __name__ == '__main__':
    unittest.main()
