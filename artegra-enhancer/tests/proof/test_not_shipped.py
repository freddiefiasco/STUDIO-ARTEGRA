"""The proof tools are developer-only: the release build ships none of tools/proof (nor the instrumentation's custom-nodes
folder), and a developer build carries them."""
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _tuple(src, name):
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f'{name} not found')


class NotShipped(unittest.TestCase):
    def test_release_build_copies_no_proof_tool(self):
        src = (ROOT / 'tools' / 'build_release.py').read_text(encoding='utf8')
        public = _tuple(src, 'PUBLIC_MATERIAL')
        self.assertFalse([p for p in public if p.startswith('tools/proof')])
        self.assertEqual([p for p in public if p.startswith('tools/')], ['tools/verify_models.py'])
        # the app's code the package is made from: tools/build_release.py's DATA_PATHS (a module constant since 5.0.2's
        # stage_sources; build() stages through it and copies nothing else of tools/ but PUBLIC_MATERIAL's verify_models)
        data = _tuple(src, 'DATA_PATHS')
        self.assertNotIn('tools', data)
        self.assertFalse([p for p in data if p.startswith('tools')])
        tree = ast.parse(src)
        fns = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
        loops = [n for n in ast.walk(fns['stage_sources']) if isinstance(n, ast.For)]
        self.assertTrue(any(isinstance(n.iter, ast.Name) and n.iter.id == 'DATA_PATHS' for n in loops))
        calls = {n.func.id for n in ast.walk(fns['build']) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        self.assertIn('stage_sources', calls)
        self.assertFalse([n for n in ast.walk(fns['build']) if isinstance(n, ast.Constant) and isinstance(n.value, str)
                          and n.value.startswith('tools')])

    def test_the_instrumentation_is_not_in_the_node_packs(self):
        self.assertFalse(list((ROOT / 'node_pack').rglob('cu_proof*')))
        self.assertTrue((ROOT / 'tools' / 'proof' / 'comfy_nodes' / 'cu_proof' / '__init__.py').is_file())

    def test_a_developer_build_carries_the_tools(self):
        src = (ROOT / 'tools' / 'make_dev_build.py').read_text(encoding='utf8')
        self.assertIn('tools', _tuple(src, 'COPY'))


if __name__ == '__main__':
    unittest.main()
