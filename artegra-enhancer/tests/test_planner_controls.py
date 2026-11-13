import unittest

from engine import controls, planner


class Planner(unittest.TestCase):
    def test_v5t_default_is_one_2x2_stage(self):
        for w, h in ((2048, 2048), (3840, 2400), (3500, 2188), (3000, 2000)):
            p = planner.plan(w, h, 2)
            self.assertTrue(p.ok, p.reason)
            self.assertEqual(len(p.stages), 1)
            st = p.stages[0]
            self.assertEqual((st.factor, st.supersample), (2.0, 2.0))
            self.assertEqual(st.padded_size, (w, h))        # the judged scenes need no padding
            self.assertEqual(st.render_size, (4 * w, 4 * h))
            self.assertEqual(p.output_size, (2 * w, 2 * h))

    def test_minutes_match_measured_runs(self):
        self.assertAlmostEqual(planner.plan(2048, 2048, 2).minutes, 23.4, delta=1.0)   # S4 measured 23.4
        self.assertAlmostEqual(planner.plan(3840, 2400, 2).minutes, 44.8, delta=1.5)   # S2 measured 44.8

    def test_odd_sizes_are_padded_and_cropped_exactly(self):
        p = planner.plan(1001, 777, 2)
        st = p.stages[0]
        self.assertEqual(st.padded_size, (1002, 778)); self.assertEqual(st.render_size, (4008, 3112))
        self.assertEqual(p.output_size, (2002, 1554))
        for f in (4, 6, 8):
            q = planner.plan(1001, 777, f)
            self.assertTrue(q.ok, q.reason)
            self.assertEqual(q.output_size, (1001 * f, 777 * f))
            for s in q.stages:
                self.assertEqual(s.render_size[0] % 8, 0); self.assertEqual(s.render_size[1] % 8, 0)

    def test_stage_chains(self):
        self.assertEqual([s.factor for s in planner.plan(1000, 800, 4).stages], [2.0, 2.0])
        self.assertEqual([s.factor for s in planner.plan(1000, 800, 6).stages], [2.0, 2.0, 1.5])
        self.assertEqual([s.factor for s in planner.plan(1000, 800, 8).stages], [2.0, 2.0, 2.0])

    def test_supersample_drops_to_stay_in_envelope(self):
        p = planner.plan(1024, 1024, 8)   # 8192 x 8192 output (67 MP)
        self.assertTrue(p.ok, p.reason)
        self.assertEqual(p.stages[0].supersample, 2.0)
        for s in p.stages:
            self.assertLessEqual(s.render_mp, planner.RENDER_CAP_MP)

    def test_refusals_are_plain_and_helpful(self):
        p = planner.plan(4000, 3000, 8)
        self.assertFalse(p.ok); self.assertIn('largest supported output', p.reason); self.assertTrue(p.suggestions)
        self.assertFalse(planner.plan(40, 400, 2).ok)
        self.assertFalse(planner.plan(1000, 1000, 3).ok)


class Controls(unittest.TestCase):
    def test_default_is_v5t(self):
        p, e = controls.resolve({})
        self.assertEqual((p['denoise'], p['tile_frac'], p['structure'], p['s_tile'], p['s_line']), (0.58, 0.4, 0.55, 0.75, 0.7))
        self.assertEqual(p['protect_terms'], ['person', 'sofa', 'bed', 'chair', 'bench', 'table', 'car', 'window'])
        self.assertEqual((p['fin_b0_hi'], p['toe']), (6.0, (0.40, 0.06)))
        self.assertEqual(e['preset'], 'Default'); self.assertEqual(e['scale'], 2)

    def test_presets_and_custom(self):
        self.assertEqual(controls.PRESET_ORDER, ['Light', 'Default', 'Strong', 'Heavy', 'Extreme'])
        p, e = controls.resolve({'preset': 'Extreme'})
        self.assertEqual(p['denoise'], 0.6448)
        p, e = controls.resolve({'preset': 'Default', 'custom': True, 'creativity': 70})
        self.assertEqual(e['preset'], 'Custom'); self.assertEqual(p['denoise'], 0.628)
        # mapping v2 anchors (6 Nov calibration) and the judged ladder
        self.assertEqual([controls.creativity_denoise(c) for c in (0, 10, 50, 100)], [0.40, 0.436, 0.58, 0.70])
        ladder = [controls.resolve({'preset': n})[0]['denoise'] for n in controls.PRESET_ORDER]
        self.assertEqual(ladder, [0.436, 0.58, 0.604, 0.6232, 0.6448])
        self.assertEqual(ladder, sorted(ladder))
        with self.assertRaises(controls.ControlError):
            controls.resolve({'creativity': 70})          # slider without custom -> rejected, not ignored
        with self.assertRaises(controls.ControlError):
            controls.resolve({'preset': 'Medium'})
        with self.assertRaises(controls.ControlError):
            controls.resolve({'custom': True, 'creativity': 101})
        with self.assertRaises(controls.ControlError):
            controls.resolve({'colour': 1})

    def test_protect_and_quick_option(self):
        p, e = controls.resolve({'quick_protect': 'architecture_only_people_vegetation'})
        self.assertNotIn('person', p['protect_terms']); self.assertIn('wall', p['protect_terms'])
        self.assertEqual(e['protect'], ['furniture', 'vehicles', 'windows', 'architecture'])
        with self.assertRaises(controls.ControlError):
            controls.resolve({'protect': ['trees']})

    def test_seed_rules(self):
        self.assertEqual(controls.parse_seed('42'), 42)
        self.assertEqual(controls.parse_seed(None), controls.DEFAULT_SEED)
        for bad in ('9223372036854775808', '-1', '1.5', True, 'abc'):
            with self.assertRaises(controls.ControlError):
                controls.parse_seed(bad)

    def test_later_stages_lower_creativity(self):
        p, _ = controls.resolve({})
        s1, s2 = controls.stage_params(p, 1), controls.stage_params(p, 2)
        self.assertLess(s1['denoise'], p['denoise']); self.assertLess(s2['denoise'], s1['denoise'])
        self.assertEqual(s1['seed'], p['seed'] + 1)
        self.assertEqual(controls.stage_params(p, 0), p)

    def test_describe_is_complete(self):
        d = controls.describe()
        self.assertEqual([x['name'] for x in d['presets']], controls.PRESET_ORDER)
        self.assertEqual([x['key'] for x in d['sliders']], ['creativity', 'resemblance', 'restoration'])
        self.assertEqual(d['scales'], [2, 4, 6, 8])


if __name__ == '__main__':
    unittest.main()
