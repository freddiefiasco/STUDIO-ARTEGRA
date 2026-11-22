"""5.0.2 build wave 3, the finish record against the plan and the sidecar (BUILD-WAVE-3 service item 4; contracts.g1u): after
each Large-image stage the finish record's whole passes (the UI planes' or the output plane header's 'finish') are compared
with the stage's bxf_whole_passes; a local pass run whole that the plan did not count is a warning event bxf_whole_mismatch
with both lists, in the timings and the sidecar (the image is not failed). The sidecar gains engine.cpu_capability,
engine.bxf_table and, per stage, the whole passes and the ops a local table moved to whole (design 2.10). A classic sidecar
is unchanged.

The record's names are the BXF's pass names (acc2.4, lf.dm, ...); engine/bxf/memory.pass_key maps them to the planner's
PASSES keys (acc<it>.4), the namespace of memory.whole_passes_for. In this process on the fake engine, whose finish records
CU_FAKE_BXF_WHOLE as its whole passes. Sizes and synthetic pictures only."""
import json
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from engine import banded_plan
from engine.bxf import memory
from service import banded_runner
import tests.test_integ_large_image_job as J
import tests.test_service3_g1u as G


class Store:
    def __init__(self, stages):
        self.it = {'timings': {'stages': stages}}

    def item(self, jid, iid):
        return self.it

    def update_item(self, jid, iid, **kw):
        self.it.update(kw)


class TheComparison(unittest.TestCase):
    def runner(self, stages):
        return SimpleNamespace(store=Store(stages), log=G.Log())

    def test_the_names_are_the_planners(self):
        keys, other = banded_runner.ran_whole({'whole_passes': ['acc2.4', 'ld0.3.sq', 'lf.dm', 'lf.x']})
        self.assertEqual(keys, sorted({memory.pass_key('acc2.4'), memory.pass_key('ld0.3.sq'), 'lf.dm'}))
        self.assertTrue(set(keys) <= set(memory.PASSES))
        self.assertEqual(other, ['lf.x'])                       # a whole-plane fallback's plane name: not a pass key

    def test_a_pass_run_whole_that_the_plan_did_not_count_is_a_warning(self):
        r = self.runner([{'index': 1, 'part': None}])
        ctx = SimpleNamespace(jid='j1', iid='i001')
        st = {'bxf_whole_passes': ['lf.dm']}
        out = banded_runner.check_finish_record(r, ctx, 1, 3, st, None,
                                                {'tier': 0, 'whole_passes': ['acc2.4', 'lf.dm']})
        self.assertEqual(out['bxf_whole_mismatch'], ['acc<it>.4'])
        warn = [x for x in r.log.lines if x[1] == 'bxf_whole_mismatch']
        self.assertEqual(len(warn), 1)
        self.assertEqual(warn[0][3]['not_counted'], ['acc<it>.4'])
        self.assertEqual(warn[0][3]['planned'], ['lf.dm'])
        ent = r.store.it['timings']['stages'][0]
        self.assertEqual(ent['whole_passes'], ['acc2.4', 'lf.dm'])
        self.assertEqual(ent['bxf_whole_passes'], ['lf.dm'])
        self.assertEqual(ent['bxf_whole_mismatch'], ['acc<it>.4'])

    def test_no_warning_when_counted_for_tier_3_or_without_a_count(self):
        ctx = SimpleNamespace(jid='j1', iid='i001')
        for st, rec in (({'bxf_whole_passes': ['acc<it>.4', 'lf.dm']}, {'tier': 0, 'whole_passes': ['acc2.4', 'lf.dm']}),
                        ({'bxf_whole_passes': []}, {'tier': 3, 'finish_tier': 'tier3', 'why': 'x'}),
                        ({}, {'tier': 0, 'whole_passes': ['acc2.4']})):
            r = self.runner([{'index': 0, 'part': 'B'}])
            out = banded_runner.check_finish_record(r, ctx, 0, 1, st, 'B', rec)
            self.assertNotIn('bxf_whole_mismatch', out)
            self.assertEqual([x for x in r.log.lines if x[1] == 'bxf_whole_mismatch'], [])
        self.assertIsNone(banded_runner.check_finish_record(self.runner([]), ctx, 0, 1, {}, None, None))

    def test_the_record_is_read_from_the_ui_planes_or_the_header(self):
        rec = {'tier': 0, 'whole_passes': ['lf.dm']}
        hist = {'outputs': {'9': {'planes': [{'role': 'output', 'path': 'x', 'finish': rec}]}}}
        self.assertEqual(banded_runner.finish_record(hist), rec)
        out = SimpleNamespace(header={'finish': rec})
        self.assertEqual(banded_runner.finish_record({'outputs': {}}, out), rec)
        self.assertIsNone(banded_runner.finish_record(None, SimpleNamespace(header={})))


class ThroughTheService(G.GlobalsRestored, J.Base):
    ram_gb = J.RAM_PC

    def test_logged_recorded_and_in_the_sidecar(self):
        with mock.patch.object(banded_plan, 'BXF_AVAILABLE', True), \
                mock.patch.dict(os.environ, {'CU_FAKE_BXF_WHOLE': 'acc2.4,lf.dm'}):
            svc = self.service()
            mid = svc.add(J.strip_input(self.td / 'in', 'wide.png', 3500, 64))
            job = svc.job([mid], {'scale': 8})
            jid = job['id']
            it = svc.item(jid)
            self.assertEqual(it['plan']['banded']['finish_tier'], 'bxf')
            plan = json.loads(json.dumps(it['plan']))
            for st in plan['stages']:
                st['bxf_whole_passes'] = ['lf.dm']               # the plan package sets it; here, the plan counted lf.dm
            svc.store.update_item(jid, 'i001', plan=plan)
            self.assertEqual(svc.run_all(), [])
        it = self.done(svc, jid)                                  # the image is not failed
        warn = [e for e in svc.events() if e['event'] == 'bxf_whole_mismatch']
        self.assertEqual([e['stage'] for e in warn], [0, 1, 2])
        self.assertEqual(warn[0]['data']['not_counted'], ['acc<it>.4'])
        side = json.loads(Path(it['sidecar']).read_text(encoding='utf8'))
        eng = side['engine']
        self.assertIn('cpu_capability', eng)
        self.assertIn('bxf_table', eng)
        self.assertEqual([x['index'] for x in eng['bxf_stages']], [0, 1, 2])
        for x in eng['bxf_stages']:
            self.assertEqual(x['finish_tier'], 'bxf')
            self.assertEqual(x['whole_passes'], ['acc2.4', 'lf.dm'])
            self.assertEqual(x['bxf_whole_passes'], ['lf.dm'])
            self.assertEqual(x['bxf_whole_mismatch'], ['acc<it>.4'])
            self.assertEqual(x['moved_to_whole'], [])

    def test_a_classic_sidecar_is_unchanged(self):
        svc = self.service()
        mid = svc.add(J.strip_input(self.td / 'in', 'small.png', 640, 480))
        job = svc.job([mid], {'scale': 2})
        self.assertEqual(svc.run_all(), [])
        it = self.done(svc, job['id'])
        side = json.loads(Path(it['sidecar']).read_text(encoding='utf8'))
        for key in ('cpu_capability', 'bxf_table', 'bxf_stages', 'executor'):
            self.assertNotIn(key, side['engine'])


if __name__ == '__main__':
    unittest.main()
