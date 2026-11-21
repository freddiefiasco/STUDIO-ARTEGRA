"""tools/proof/tally.py: verdict files validate against the manifest, the key maps X and Y to engines, controls are apart, the
key is opened only after both verdict files, and BLIND-TALLY.json validates (and a tampered one does not)."""
import copy
import unittest

from tools.proof import pairs, tally

MANIFEST = [{'pair': f'C1/{c}', 'case': 'C1', 'crop': c, 'kind': k}
            for c, k in (('edge01', 'edge'), ('edge02', 'edge'), ('flat', 'flat'), ('proxy', 'proxy'))]


def key():
    rows = []
    for r in MANIFEST:
        o = pairs.order('C1', r['crop'])
        rows.append({'pair': r['pair'], 'X': o['X'], 'Y': o['Y'], 'identical': r['crop'] == 'flat'})
    return {'format': pairs.KEY_FORMAT, 'manifest_sha256': 'm' * 64, 'pairs': {x['pair']: x for x in rows}}


def verdicts(judge, call_for_bes='same', when='2026-11-22T10:00:00+11:00', control_call='same'):
    k = key()
    out = {}
    for r in MANIFEST:
        kp = k['pairs'][r['pair']]
        if kp['identical']:
            e = {c: control_call for c in tally.CRITERIA}
        else:
            bes = 'X' if kp['X'] == 'bes' else 'Y'
            other = 'Y' if bes == 'X' else 'X'
            call = {'same': 'same', 'better': bes, 'worse': other}[call_for_bes]
            e = {c: call for c in tally.CRITERIA}
        e['artefacts'] = [{'in': 'X', 'kind': 'ringing', 'x': 10, 'y': 20, 'note': 'rim'}] if r['crop'] == 'edge01' else []
        out[r['pair']] = e
    return {'format': tally.VERDICT_FORMAT, 'judge': judge, 'written_at': when, 'pairs_manifest_sha256': 'm' * 64,
            'verdicts': out}


SHAS = {'guardian': 'a' * 64, 'technical_qa': 'b' * 64}
OPEN = '2026-11-22T12:00:00+11:00'


class Verdicts(unittest.TestCase):
    def test_valid_and_invalid_files(self):
        self.assertEqual(tally.validate_verdicts(verdicts('guardian'), MANIFEST), [])
        bad = verdicts('guardian')
        del bad['verdicts']['C1/edge02']
        bad['verdicts']['C1/edge01']['halos'] = 'better'
        bad['verdicts']['C1/edge01']['artefacts'][0]['x'] = 900
        errs = tally.validate_verdicts(bad, MANIFEST)
        self.assertTrue(any('edge02: no verdict' in e for e in errs))
        self.assertTrue(any('halos must be' in e for e in errs))
        self.assertTrue(any('inside the crop' in e for e in errs))
        self.assertTrue(tally.validate_verdicts(dict(verdicts('x'), judge='someone'), MANIFEST))
        self.assertTrue(tally.validate_verdicts(dict(verdicts('guardian'), written_at='2026-11-22 10:00'), MANIFEST))


class Tally(unittest.TestCase):
    def run_tally(self, g='same', q='same', control='same'):
        v = {'guardian': verdicts('guardian', g, control_call=control), 'technical_qa': verdicts('technical_qa', q)}
        return tally.tally(v, key(), MANIFEST, SHAS, 'k' * 64, OPEN)

    def test_same_everywhere_is_same_or_better_and_validates(self):
        t = self.run_tally()
        self.assertEqual(tally.validate_tally(t), [])
        c = t['cases']['C1']
        self.assertEqual((c['pairs'], c['controls']), (3, 1))
        self.assertEqual(c['by_criterion']['halos']['guardian'], {'bes_better': 0, 'same': 3, 'classic_better': 0})
        self.assertTrue(t['result']['all_cases_same_or_better'])
        self.assertEqual({a['engine'] for a in c['artefacts']}, {key()['pairs']['C1/edge01']['X']})

    def test_the_key_maps_calls_to_engines(self):
        t = self.run_tally(g='better', q='worse')
        c = t['cases']['C1']
        self.assertEqual(c['by_criterion']['fidelity']['guardian']['bes_better'], 3)
        self.assertEqual(c['by_criterion']['fidelity']['technical_qa']['classic_better'], 3)
        self.assertEqual(c['verdict']['technical_qa']['result'], 'worse')
        self.assertEqual(c['verdict']['guardian']['result'], 'same_or_better')
        self.assertEqual(t['result']['worse_cases'], ['C1'])
        self.assertEqual(tally.validate_tally(t), [])

    def test_controls_called_different_are_listed_not_counted(self):
        t = self.run_tally(control='X')
        c = t['cases']['C1']
        self.assertEqual(c['controls_called_different'][0]['pair'], 'C1/flat')
        self.assertTrue(t['result']['all_cases_same_or_better'])

    def test_key_opened_too_early_or_a_judge_missing_is_refused(self):
        v = {'guardian': verdicts('guardian', when='2026-11-22T13:00:00+11:00'), 'technical_qa': verdicts('technical_qa')}
        with self.assertRaises(ValueError):
            tally.tally(v, key(), MANIFEST, SHAS, 'k' * 64, OPEN)
        with self.assertRaises(ValueError):
            tally.tally({'guardian': verdicts('guardian')}, key(), MANIFEST, SHAS, 'k' * 64, OPEN)

    def test_a_tampered_tally_does_not_validate(self):
        t = self.run_tally(q='worse')
        bad = copy.deepcopy(t)
        bad['cases']['C1']['verdict']['technical_qa']['result'] = 'same_or_better'
        self.assertTrue(tally.validate_tally(bad))
        bad = copy.deepcopy(t)
        bad['result']['all_cases_same_or_better'] = True
        self.assertTrue(tally.validate_tally(bad))
        bad = copy.deepcopy(t)
        bad['cases']['C1']['by_criterion']['halos']['guardian']['same'] += 1
        self.assertTrue(tally.validate_tally(bad))


if __name__ == '__main__':
    unittest.main()
