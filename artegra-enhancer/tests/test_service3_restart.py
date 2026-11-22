"""5.0.2 build wave 3, the fresh engine before a pass (BUILD-WAVE-3 contracts.restart): banded_runner.run_stage restarts the
engine with restart_worker's commit-fall check before a stage whose plan sets fresh_worker, once before prompt A (and the
split's own restart before prompt B), never for a fresh engine or a stage that resumes from its checkpoint, and records it
(event banded_stage_restart; the stage's timings entry gains restart_before with the l3r_record fields). And the restart of
an engine started with another local G1u table than the planner's (contracts.g1u).

In this process on the fake engine (tests/test_integ_large_image_job.py's harness); the plan's fresh_worker flag (the plan
package sets it) is set on the stored plan here. Sizes and synthetic pictures only."""
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from service import banded_runner, bxf_probe
import tests.test_integ_large_image_job as J
from tests.service.helpers import split_strip_height
import tests.test_service3_g1u as G

L3R = ('job_peak_commit_a_end_gb', 'job_peak_commit_b_start_gb', 'stopped_worker_last_commit_gb', 'commit_fall_gb')


def flag(svc, jid, stages):
    it = svc.item(jid)
    plan = json.loads(json.dumps(it['plan']))
    for k in stages:
        plan['stages'][k]['fresh_worker'] = True
    svc.store.update_item(jid, it['id'], plan=plan)


def restarts(svc, event='banded_stage_restart'):
    return [e for e in svc.events() if e['event'] == event]


class OneShotStages(G.GlobalsRestored, J.Base):
    """8x of 3500 x 64 on a 64 GB PC's class: three one-prompt passes."""
    ram_gb = J.RAM_PC

    def test_one_restart_before_each_flagged_pass_after_the_first(self):
        svc = self.service()
        mid = svc.add(J.strip_input(self.td / 'in', 'wide.png', 3500, 64))
        job = svc.job([mid], {'scale': 8})
        jid = job['id']
        self.assertFalse(any(s['split_finish'] for s in job['items'][0]['plan']['stages']))
        flag(svc, jid, (0, 1, 2))
        self.assertEqual(svc.run_all(), [])
        it = self.done(svc, jid)
        ev = restarts(svc)
        self.assertEqual([e['stage'] for e in ev], [1, 2])                # the first pass's engine is fresh: none
        self.assertEqual(restarts(svc, 'banded_split_restart'), [])
        self.assertEqual(len(restarts(svc, 'banded_stage_restart_commit')), 2)
        ents = {(x['index'], x.get('part')): x for x in it['timings']['stages']}
        self.assertNotIn('restart_before', ents[(0, None)])
        for k in (1, 2):
            rec = ents[(k, None)]['restart_before']
            self.assertEqual(set(L3R) | set(banded_runner.L3R_EXTRA) | {'why'}, set(rec))
            self.assertEqual(rec['why'], 'fresh_worker')
            self.assertEqual(rec['commit_check'], 'unmeasured')            # no shared Job in this process
        self.assertEqual(svc.worker.starts, 3)

    def test_no_flag_no_restart(self):
        svc = self.service()
        mid = svc.add(J.strip_input(self.td / 'in', 'wide.png', 3500, 64))
        job = svc.job([mid], {'scale': 8})
        self.assertEqual(svc.run_all(), [])
        self.done(svc, job['id'])
        self.assertEqual(restarts(svc), [])
        self.assertEqual(svc.worker.starts, 1)


class SplitStages(G.GlobalsRestored, J.Base):
    """8x of 4000 x H on the workstation class, H the smallest strip whose every pass is split (prompt A, a fresh engine,
    prompt B), from the planner at run time (contracts.split_premise)."""
    ram_gb = J.RAM_WS

    def height(self, svc):
        h = split_strip_height(float(svc.settings.get()['ram_cap_gb']), service=False)
        self.assertIsNotNone(h)
        return h

    def test_before_a_and_before_b(self):
        svc = self.service()
        mid = svc.add(J.strip_input(self.td / 'in', 'wide.png', 4000, self.height(svc)))
        job = svc.job([mid], {'scale': 8})
        jid = job['id']
        self.assertTrue(all(s['split_finish'] for s in job['items'][0]['plan']['stages']))
        flag(svc, jid, (1,))
        self.assertEqual(svc.run_all(), [])
        it = self.done(svc, jid)
        self.assertEqual([e['stage'] for e in restarts(svc)], [1])
        self.assertEqual(len(restarts(svc, 'banded_split_restart')), 3)    # each pass's prompt B, as before
        ents = {(x['index'], x.get('part')): x for x in it['timings']['stages']}
        self.assertEqual(ents[(1, 'A')]['restart_before']['why'], 'fresh_worker')
        self.assertNotIn('restart_before', ents[(1, 'B')])

    def test_a_resumed_pass_needs_none_before_b(self):
        svc = self.service('state-a')
        mid = svc.add(J.strip_input(self.td / 'in', 'wide.png', 4000, self.height(svc)))
        job = svc.job([mid], {'scale': 8})
        jid = job['id']
        flag(svc, jid, (1,))
        J.InProcessFake.die_at = (1, 'B')
        died = svc.run_all()
        self.assertEqual(len(died), 1)
        self.assertEqual([e['stage'] for e in restarts(svc)], [1])        # before A, in the first run
        svc2 = self.service('state-a')
        n_before = len(restarts(svc2))
        self.assertEqual(svc2.run_all(), [])
        self.done(svc2, jid)
        self.assertEqual(len(restarts(svc2)), n_before)                   # the resumed pass: no restart before B
        self.assertIn('banded_checkpoint_resume', [e['event'] for e in svc2.events()])


class TheTableTheEngineLoads(G.GlobalsRestored, J.Base):
    ram_gb = J.RAM_PC

    def test_an_engine_started_with_another_local_table_is_restarted(self):
        svc = self.service()
        mid = svc.add(J.strip_input(self.td / 'in', 'wide.png', 3500, 64))
        job = svc.job([mid], {'scale': 8})
        svc.worker.ensure_started()
        self.assertEqual(svc.worker.bxf_local_table, '')
        svc.worker.client.prompts_sent = 1                                  # it has run a prompt (a classic image)
        bxf_probe._STATE['local'] = str(svc.state / 'bxf' / 'local-table.json')
        self.assertEqual(svc.run_all(), [])
        self.done(svc, job['id'])
        ev = restarts(svc)
        self.assertEqual([e['stage'] for e in ev], [0])
        self.assertEqual(svc.worker.bxf_local_table, bxf_probe._STATE['local'])

    def test_restart_before_rules(self):
        w = SimpleNamespace(state='ready', alive=lambda: True, client=SimpleNamespace(prompts_sent=0), bxf_local_table='')
        self.assertIsNone(banded_runner.restart_before(None, w, None, 1, 3, {'fresh_worker': True}))   # fresh: none
        self.assertIsNone(banded_runner.restart_before(None, w, None, 1, 3, {}))
        w.client.prompts_sent = 2
        self.assertIsNone(banded_runner.restart_before(None, w, None, 1, 3, {}))       # no flag, same table: none
        with mock.patch.object(banded_runner, 'restart_worker', return_value={'commit_check': 'passed'}) as rw:
            rec = banded_runner.restart_before(None, w, None, 1, 3, {'fresh_worker': True})
            self.assertEqual(rec['why'], 'fresh_worker')
            self.assertEqual(rw.call_args.kwargs['event'], 'banded_stage_restart')
            self.assertIn('Pass 2 of 3', rw.call_args.kwargs['text'])
            w.client.prompts_sent = 0
            bxf_probe._STATE['local'] = str(Path('state') / 'bxf' / 'local-table.json')
            self.assertEqual(banded_runner.restart_before(None, w, None, 0, 3, {})['why'], 'table')


if __name__ == '__main__':
    unittest.main()
