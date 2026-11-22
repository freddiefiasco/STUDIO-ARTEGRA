"""Gate G7's wave-3 runs and the flags that follow them (engine/banded_plan.py; build wave 3, the plan package's item 3 and
plan-chk-6). Each verdict is recorded from the worker runtime (sizes, seeds, schedules and differing counts only):
- plan2-g7-bolt-schedules (tests/fixtures/plan3_g7_bolt.json): Bolt's 8 executed steps at its Looks' denoise. PASS sets
  BOLT_BROWNIAN_CAPPED, so a Bolt plan's brownian_cache is 8; anything else keeps it at 45;
- plan3-g7-redux-looks (tests/fixtures/plan3_g7_redux_looks.json): Redux's 30 steps at every Look's own stage 0-2 denoise.
  BROWNIAN_CAPPED stays True only on its PASS beside wave 2's plan2-g7-runtime; anything else, or no record, returns it to
  False (every plan's cache 45, counted).
Needs no torch."""
import json
import unittest
from pathlib import Path
from unittest import mock

from engine import banded_plan as B
from engine import controls, graph_banded, planner

FIX = Path(__file__).resolve().parents[1] / 'tests' / 'fixtures'


def verdict(name):
    path = FIX / name
    return json.loads(path.read_text(encoding='utf8')) if path.is_file() else None


def passed(v):
    return bool(v and v['verdict'] == 'PASS' and v['identical'] and not v.get('quick')
                and all(c[k] == 0 for c in v['cases'] for k in ('capped8', 'prefetch45', 'prefetch_capped8')))


class TheFlagsFollowTheVerdicts(unittest.TestCase):
    def test_bolts_own_schedules(self):
        v = verdict('plan3_g7_bolt.json')
        self.assertIsNotNone(v)
        self.assertEqual(v['dev_run'], 'plan2-g7-bolt-schedules')
        self.assertEqual((v['steps'], v['denoise']), (8, [0.436, 0.51, 0.58, 0.55]))
        self.assertEqual(len(v['cases']), 3 * 4 * 3)
        self.assertEqual(B.BOLT_BROWNIAN_CAPPED, passed(v))
        light, default = (controls.resolve({'preset': n})[0] for n in ('Light', 'Default'))
        self.assertEqual(sorted(v['denoise']), sorted({light['denoise'], light['structure'], default['denoise'],
                                                       default['structure']}))

    def test_redux_schedules(self):
        runtime, looks = verdict('plan2_g7_runtime.json'), verdict('plan3_g7_redux_looks.json')
        self.assertTrue(passed(runtime))
        self.assertEqual(B.BROWNIAN_CAPPED, passed(runtime) and passed(looks))
        if looks is not None:
            self.assertEqual(looks['dev_run'], 'plan3-g7-redux-looks')
            self.assertEqual(looks['steps'], 30)
            rows = [(r['look'], r['stage'], r['creative'], r['structure']) for r in looks['looks']]
            want = []
            for look in controls.PRESET_ORDER:
                p = controls.resolve({'preset': look})[0]
                for k in range(3):
                    s = controls.stage_params(p, k)
                    want.append((look, k, s['denoise'], s['structure']))
            self.assertEqual(rows, want)
            members = sorted(m for g in looks['schedule_groups'] for m in g['members'])
            self.assertEqual(members, sorted({x for r in want for x in r[2:]}))
            self.assertEqual(sorted(looks['denoise']), sorted(g['representative'] for g in looks['schedule_groups']))

    def test_a_bolt_plan_caps_the_cache_now(self):
        c = planner.plan(2048, 2048, 2, ram_cap_gb=59.0)
        with mock.patch.object(B, 'BXF_AVAILABLE', True):
            f = B.plan_forced(c, 59.0, mode='fast')
        self.assertTrue(f.ok, f.reason)
        want = 8 if (B.BROWNIAN_CAPPED and B.BOLT_BROWNIAN_CAPPED) else 45
        self.assertEqual(f.banded['brownian_cache'], want)
        self.assertEqual(B.constants('bolt')['brownian_cache'], want)
        p = controls.resolve({})[0]
        st = f.stages[0]
        g, _ = graph_banded.build_product('in.plane', *st.padded_size, p, 'x', 'pl', 'r', f=st.factor, s=st.supersample,
                                          constants=f.banded)
        spot = next(n['inputs'] for n in g.values() if n['class_type'] == graph_banded.SPOT_CLASS)
        self.assertEqual(spot.get('brownian_cache', 45), want)
        # only the expected figure falls with the cap; the upper model's X was measured with the full cache in it
        full = B.stage_peaks(st, 'pc64', st.split_finish, brownian_capped=False)
        capped = B.stage_peaks(st, 'pc64', st.split_finish, brownian_capped=True)
        self.assertEqual(full['up'], capped['up'])
        self.assertEqual(B.stage_peaks(st, 'pc64', st.split_finish)['exp'], (capped if want == 8 else full)['exp'])


class TheCapReachesOnlyComparedSchedules(unittest.TestCase):
    def test_the_schedule_set_is_the_verdicts(self):
        want = {}
        for name in ('plan2_g7_runtime.json', 'plan3_g7_redux_looks.json', 'plan3_g7_bolt.json'):
            v = verdict(name)
            self.assertTrue(passed(v), name)
            members = ([m for g in v['schedule_groups'] for m in g['members']] if 'schedule_groups' in v else v['denoise'])
            want.setdefault(v['steps'], set()).update(graph_banded.g7_schedule(v['steps'], d) for d in members)
        self.assertEqual({k: set(v) for k, v in graph_banded.G7_SCHEDULES.items()}, want)

    def test_a_custom_schedule_keeps_45(self):
        consts = dict(B.constants('redux'), brownian_cache=8)
        look = controls.stage_params(controls.resolve({})[0], 0)
        custom = dict(look, denoise=0.70, structure=0.66)                 # creativity 100, restoration 90: not compared
        self.assertNotIn(graph_banded.g7_schedule(30, 0.70), graph_banded.G7_SCHEDULES[30])
        self.assertEqual(graph_banded.brownian_cache_for(consts, look), 8)
        self.assertEqual(graph_banded.brownian_cache_for(consts, custom), 45)
        self.assertEqual(graph_banded.brownian_cache_for(dict(consts, brownian_cache=45), look), 45)
        for params, want in ((look, 8), (custom, 45)):
            g, _ = graph_banded.build_stage('in.plane', 1752, 1096, params, 'x', 'pl', 'r', constants=consts)
            spot = next(n['inputs'] for n in g.values() if n['class_type'] == graph_banded.SPOT_CLASS)
            self.assertEqual(spot.get('brownian_cache', 45), want)
        for name in controls.PRESET_ORDER:                                 # every Look of every pass is compared
            p = controls.resolve({'preset': name})[0]
            for k in range(3):
                self.assertEqual(graph_banded.brownian_cache_for(consts, controls.stage_params(p, k)), 8, (name, k))
        for name in ('Light', 'Default'):                                  # and Bolt's
            p = controls.resolve({'preset': name})[0]
            self.assertEqual(graph_banded.brownian_cache_for(dict(consts, mode='bolt'), p, 'bolt'), 8, name)


if __name__ == '__main__':
    unittest.main()
