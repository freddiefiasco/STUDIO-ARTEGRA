"""The engine, node pack and service stay as the verified merge left them.

The Beta's engine/, node_pack/ and service/ are the final v5's code plus the standalone layer and the documented Beta
layer, checked file by file against the final v5 by a private verification (docs/PROVENANCE.md). This test pins the
result: the code normal form of every file (Python without comments and docstrings; other files byte for byte) must
match tests/fixtures/beta-normalised-hashes.json. A change to the code of any of these files fails here until the
merge is verified again and the fixture regenerated with `python tests/test_final_v5_layer.py --write`.

The fixture lists one {"path", "sha256"} object per file, like docs/SOURCE-MAP.json, so that no hash directly
follows a file name (secret scanners read a name such as service/api.py followed by a long value as a key).
"""
import ast
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "beta-normalised-hashes.json"
SCOPE = ("engine", "node_pack", "service")


class _Strip(ast.NodeTransformer):
    def _doc(self, node):
        self.generic_visit(node)
        body = getattr(node, "body", None)
        if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
                and isinstance(body[0].value.value, str):
            node.body = body[1:] or [ast.Pass()]
        return node
    visit_Module = visit_FunctionDef = visit_AsyncFunctionDef = visit_ClassDef = _doc


def normal_form(path: Path) -> bytes:
    data = path.read_bytes()
    if path.suffix == ".py":
        return ast.unparse(_Strip().visit(ast.parse(data.decode("utf-8")))).encode("utf-8")
    return data


def current():
    out = {}
    for top in SCOPE:
        for path in sorted((ROOT / top).rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                out[path.relative_to(ROOT).as_posix()] = hashlib.sha256(normal_form(path)).hexdigest()
    return out


def pinned_hashes():
    entries = json.loads(FIXTURE.read_text(encoding="utf-8"))["files"]
    pinned = {entry["path"]: entry["sha256"] for entry in entries}
    assert len(pinned) == len(entries), "a file is listed twice"
    return pinned


def test_engine_node_pack_and_service_code_is_the_verified_merge():
    pinned = pinned_hashes()
    now = current()
    assert sorted(now) == sorted(pinned), "files were added or removed"
    changed = sorted(rel for rel in now if now[rel] != pinned[rel])
    assert changed == [], changed


if __name__ == "__main__" and "--write" in sys.argv:
    FIXTURE.write_text(json.dumps({"about": "SHA-256 of each file's code normal form after the verified merge "
                                            "(see tests/test_final_v5_layer.py).",
                                   "files": [{"path": path, "sha256": digest}
                                             for path, digest in sorted(current().items())]},
                                  indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(FIXTURE)
