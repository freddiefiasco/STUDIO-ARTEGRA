"""5.0.2 build wave 3, the worker guard (BUILD-WAVE-3 service item 5; contracts.worker_banded and bolt): the Large-image input
check also covers the Large-image Bolt graph (graph_banded.build_product with Bolt's constants and the shipped Fast recipe), so
ClaudeSpotTilesBanded's seam_overlap is in it; without the shipped recipe no Bolt graph can be built and none is checked.
cn_reuse and seam_dual are declared by the spot fork but sent by no graph this app builds (classic or Large-image), so no
check can ask for them; this is pinned here. (Worker._check_banded's order fix is tested in tests/test_integ_worker.py.)
Sizes only."""
import unittest
from unittest import mock

from engine import fast_recipe, graph_banded, graph_v5t
from service import runner, workers


def spot_inputs(graphs):
    out = set()
    for g in graphs:
        for n in g.values():
            if n['class_type'] == graph_banded.SPOT_CLASS:
                out |= set(n['inputs'])
    return out


class TheBoltGraph(unittest.TestCase):
    def test_built_with_the_shipped_recipe(self):
        r = fast_recipe.recipe()
        self.assertEqual(f"{r['name']}@{r['version']}", graph_banded.BOLT_RECIPE)       # the shipped one
        graphs = workers.banded_bolt_graphs()
        self.assertTrue(graphs)
        for g in graphs:
            classes = {n['class_type'] for n in g.values()}
            if graph_banded.SPOT_CLASS in classes:
                self.assertIn('LoraLoaderModelOnly', classes)
                spot = next(n for n in g.values() if n['class_type'] == graph_banded.SPOT_CLASS)
                self.assertEqual(spot['inputs']['seam_overlap'], graph_banded.BOLT['seam_overlap'])
        lives = {n['inputs'].get('live_preview') for g in graphs for n in g.values()
                 if n['class_type'] == graph_banded.SPOT_CLASS}
        self.assertTrue(set(graph_v5t.PRODUCT_LIVE_MODES) <= lives)
        self.assertTrue(any(n['class_type'] == 'CUPlaneCheckpoint' for g in graphs for n in g.values()))   # part A
        self.assertTrue(any(n['class_type'] == 'CUFinishBanded' and 'finish_tier' in n['inputs']
                            for g in graphs for n in g.values()))

    def test_seam_overlap_is_in_the_large_image_check(self):
        req = workers.required_inputs(banded=True)
        self.assertIn('seam_overlap', req[graph_banded.SPOT_CLASS])
        self.assertIn('seam_overlap', workers.required_inputs(multi=True, banded=True)[graph_banded.SPOT_CLASS])
        declared = set(graph_banded.NODE_SPECS[graph_banded.SPOT_CLASS][0]) | set(
            graph_banded.NODE_OPTIONAL[graph_banded.SPOT_CLASS])
        self.assertLessEqual(set(req[graph_banded.SPOT_CLASS]), declared)

    def test_an_old_pack_without_it_is_logged(self):
        spec = {cls: {'input': {'required': {k: ['*'] for k in graph_banded.NODE_SPECS[cls][0]},
                                'optional': {k: ['*'] for k in graph_banded.NODE_OPTIONAL.get(cls, ())
                                             if k != 'seam_overlap'}}} for cls in graph_banded.NODE_SPECS}
        self.assertEqual(workers.undeclared_inputs(spec, banded=True), {graph_banded.SPOT_CLASS: ['seam_overlap']})

    def test_two_cards(self):
        multi = workers.banded_bolt_graphs(multi=True)
        self.assertTrue(any(n['class_type'] == 'MultiGPU_WorkUnits' for g in multi for n in g.values()))

    def test_without_the_shipped_recipe_no_bolt_graph(self):
        with mock.patch.object(fast_recipe, 'RECIPE', runner._test_fast_recipe()):         # CU_FAST_TEST's stand-in
            self.assertEqual(workers.banded_bolt_graphs(), [])
            req = workers.required_inputs(banded=True)
        self.assertNotIn('seam_overlap', req[graph_banded.SPOT_CLASS])
        self.assertEqual(set(req), set(graph_banded.NODE_SPECS))                            # the Redux check is whole
        with mock.patch.object(fast_recipe, 'RECIPE', None):
            self.assertEqual(workers.banded_bolt_graphs(), [])

    def test_cn_reuse_and_seam_dual_are_sent_by_no_graph(self):
        big = spot_inputs(workers.banded_graphs()) | spot_inputs(workers.banded_graphs(multi=True))
        self.assertFalse({'cn_reuse', 'seam_dual'} & big)
        classic = set(workers.required_inputs().get('ClaudeSpotTiles', ())) | set(
            workers.required_inputs(multi=True).get('ClaudeSpotTiles', ()))
        self.assertFalse({'cn_reuse', 'seam_dual'} & classic)

    def test_the_classic_check_has_no_large_image_class(self):
        self.assertFalse(set(workers.required_inputs()) & set(graph_banded.NODE_SPECS))
        self.assertFalse(set(workers.required_inputs(multi=True)) & set(graph_banded.NODE_SPECS))


if __name__ == '__main__':
    unittest.main()
