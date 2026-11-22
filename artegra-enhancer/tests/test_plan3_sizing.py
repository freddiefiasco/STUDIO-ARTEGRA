"""The Large-image planner's figures for the target rows with each machine class's committed G1 table, as the service plans
on that node (G1u; tests/fixtures/plan3_sizing.json, written by the plan package's wp/3-plan/sizing.py; its TARGET-FIT.md
reads the same figures). TABLES[1] is this workstation's class (ws128), TABLES[2] the render nodes' (pc64, and pc48: a 64 GB
node run at the 45.2 cap). Sizes and GiB only."""
import json
import unittest
from pathlib import Path

from engine.bxf import g1, g1_table
from tests.test_plan2_model_terms import check_rows

ROOT = Path(__file__).resolve().parents[1]
NODE = {'ws128': 1, 'pc64': 2, 'pc48': 2}


def node_table(mc):
    t = g1_table.TABLES[NODE[mc]]
    return g1.Table(t, env=dict(t['environment']))


class TheTargetRowsOnEachNode(unittest.TestCase):
    def test_the_pinned_figures_with_the_node_tables(self):
        rows = json.loads((ROOT / 'tests' / 'fixtures' / 'plan3_sizing.json').read_text(encoding='utf8'))['rows']
        self.assertGreater(len(rows), 20)
        self.assertEqual({r['how'] for r in rows}, {'table'})
        check_rows(self, rows, node_table)

    def test_what_the_honest_bound_costs(self):
        """The rows the release bar names that no committed table admits now (TARGET-FIT.md says why, for Max)."""
        rows = json.loads((ROOT / 'tests' / 'fixtures' / 'plan3_sizing.json').read_text(encoding='utf8'))['rows']
        refused = {(r['w'], r['h'], r['factor'], r['machine_class']) for r in rows if not r['ships']}
        for key in ((3500, 2188, 8, 'pc64'), (2800, 3500, 8, 'pc64'), (2800, 3500, 8, 'ws128')):
            self.assertIn(key, refused)


if __name__ == '__main__':
    unittest.main()
