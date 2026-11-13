"""The standalone node catalogue must not advertise missing optional extensions."""
import ast
from pathlib import Path


def test_no_unsupported_legacy_extension_is_registered():
    source = Path(__file__).resolve().parents[1] / 'node_pack/claude_creative/__init__.py'
    tree = ast.parse(source.read_text())
    catalogs = {
        statement.targets[0].id: set(ast.literal_eval(key) for key in statement.value.keys)
        for statement in tree.body
        if isinstance(statement, ast.Assign)
        and isinstance(statement.targets[0], ast.Name)
        and statement.targets[0].id in {'NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS'}
    }
    legacy = {'ClaudeUSDUTileSeed', 'ClaudeUSDUFixedContext', 'ClaudeUSDUSharedNoise'}
    for names in catalogs.values():
        assert names.isdisjoint(legacy)
        assert {'ClaudeSpotTiles', 'ClaudeUpscaleModelTiled', 'ClaudeV4Finish'} <= names
    assert len(catalogs) == 2
