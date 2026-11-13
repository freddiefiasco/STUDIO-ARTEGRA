"""Compare generated prompts to hashes recorded from the approved preview snapshot."""
import hashlib
import json
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "preview_graphs.json"


def graph_digest(case):
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
        graphs.append(graph)
    payload = json.dumps(graphs, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


@pytest.mark.parametrize("case", json.loads(FIXTURE.read_text())["cases"] if FIXTURE.exists() else [])
def test_preview_prompt_identity(case):
    assert graph_digest(case) == case["sha256"]


def test_reference_covers_standard_and_fast():
    data = json.loads(FIXTURE.read_text())
    assert data["reference_tree"] == "cd2fd9c2f7eec3c7347d57afbd5260a1aaf61e4637a7952999fd1ee0763f6342"
    assert {case["mode"] for case in data["cases"]} == {"standard", "fast"}
    assert len(data["cases"]) >= 80
