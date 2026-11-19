"""The lean SAM node through the service, on the fake engine (5.0.2; Max, 20 Nov 2026: "Fold into 5.0.2").

A pass whose padded input is above engine/planner.SAM_STOCK_MAX_MP, and a protected-area preview of a source above it, send
ClaudeSAM3DetectLean in place of SAM3_Detect; at or below it they send 5.0.1's SAM3_Detect. The ceiling is lowered here so a
small synthetic image crosses it (the rule itself is tested on sizes in tests/test_sam_lean_and_times.py)."""
import unittest
from unittest import mock

from engine import planner
from service import mask_graph
from tests.service.test_qa_engine import Base, wait

LEAN = 'ClaudeSAM3DetectLean'


def sam_classes(graph):
    return sorted({n['class_type'] for n in graph.values() if n['class_type'] in ('SAM3_Detect', LEAN)})


class LeanSamThroughTheService(Base):
    def test_the_protected_area_preview_follows_the_size_of_its_source(self):
        s = self.svc()
        mids = s.inputs(1)                                            # 96 x 72 px, 0.0069 MP
        with mock.patch.object(mask_graph, 'build', wraps=mask_graph.build) as spy:
            res = s.runner.mask_preview(mids[0], protect=['people'])
            self.assertTrue(res['mask_url'])
            self.assertEqual(spy.call_args.kwargs['size'], (96, 72))
            with mock.patch.object(planner, 'SAM_STOCK_MAX_MP', 0.005):
                res = s.runner.mask_preview(mids[0], protect=['architecture'])
                self.assertTrue(res['mask_url'])
        got = [sam_classes(g) for g in s.prompts().values() if sam_classes(g)]
        self.assertEqual(sorted(got), [[LEAN], ['SAM3_Detect']])

    def test_a_pass_above_the_ceiling_runs_the_lean_node_and_finishes(self):
        s = self.svc()
        mids = s.inputs(2)
        jid = s.job(mids[:1])
        wait(lambda: s.item(jid)['state'] == 'done', 60, 'the first image')
        with mock.patch.object(planner, 'SAM_STOCK_MAX_MP', 0.005):
            jid2 = s.job(mids[1:])
            it = wait(lambda: (lambda x: x if x['state'] in ('done', 'failed') else None)(s.item(jid2)), 60, 'the second')
        self.assertEqual(it['state'], 'done', it.get('error'))
        stages = [g for g in s.prompts().values() if any(n['class_type'] == 'ClaudeV4Finish' for n in g.values())]
        self.assertEqual(sorted(sam_classes(g)[0] for g in stages), [LEAN, 'SAM3_Detect'])


if __name__ == '__main__':
    unittest.main()
