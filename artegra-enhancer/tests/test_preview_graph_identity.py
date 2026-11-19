"""Compare generated prompts to hashes recorded from the approved preview snapshot.

5.0.2's registered exception (tests/test_engine_identity.py, tests/fixtures/sam_lean_5_0_2.json): a stage whose padded input
is above engine/planner.SAM_STOCK_MAX_MP takes ClaudeSAM3DetectLean in place of SAM3_Detect. With that class read back as
SAM3_Detect every prompt is the snapshot's; the cases whose prompts differ as built are exactly the recorded ones."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "preview_graphs.json"
EXCEPTION = json.loads((Path(__file__).parent / "fixtures" / "sam_lean_5_0_2.json").read_text(encoding="utf-8"))
_G0 = importlib.util.spec_from_file_location("g0_identity_for_previews", Path(__file__).parent / "fixtures" / "g0_identity.py")
G0 = importlib.util.module_from_spec(_G0)
_G0.loader.exec_module(G0)


def graph_digest(case, view=None):
    from engine import controls, fast_recipe, graph_v5t, planner

    params, _ = controls.resolve({"preset": case["look"], "scale": case["scale"], "seed": "20261102"})
    plan = planner.plan(case["width"], case["height"], case["scale"])
    graphs = []
    for index, stage in enumerate(plan.stages):
        values = controls.stage_params(params, index)
        common = dict(f=stage.factor, s=stage.supersample, live_preview=case["preview"])
        if case["mode"] == "fast":
            graph, _ = fast_recipe.build("input.png", *stage.padded_size, values, "output", **common)
        else:
            graph, _ = graph_v5t.build_product(
                "input.png", *stage.padded_size, values, "output", **common,
                speed_stack=case["stack"], creative_first=case["creative_first"],
            )
        graphs.append(view(graph) if view else graph)
    payload = json.dumps(graphs, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


CASES = json.loads(FIXTURE.read_text())["cases"] if FIXTURE.exists() else []


@pytest.mark.parametrize("index", range(len(CASES)))
def test_preview_prompt_identity(index):
    case = CASES[index]
    assert graph_digest(case, view=G0.stock_view) == case["sha256"]
    assert (graph_digest(case) != case["sha256"]) == (index in EXCEPTION["preview_cases"])


def test_reference_covers_standard_and_fast():
    data = json.loads(FIXTURE.read_text())
    assert data["reference_tree"] == "cd2fd9c2f7eec3c7347d57afbd5260a1aaf61e4637a7952999fd1ee0763f6342"
    assert {case["mode"] for case in data["cases"]} == {"standard", "fast"}
    assert len(data["cases"]) >= 80
