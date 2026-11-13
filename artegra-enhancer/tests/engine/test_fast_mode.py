"""Fast recipe boundaries for the selected v5 preview."""
import copy
import pytest
from engine import controls, fast_recipe, graph_v5t, planner
from service import engine_options


def test_preview_fast_recipe_is_enabled_without_unproven_split():
    assert fast_recipe.installed()
    assert engine_options.FAST_PROVEN is True
    assert engine_options.FAST_SPLIT_PROVEN is False
    assert engine_options.FASTER_PROVEN is False
    assert fast_recipe.LORA['sha256'] == '55b51334c85061afff5eff7c550b61963c8b8607a5868bbe4f26db49374719b1'


def test_fast_graph_uses_exact_recipe_and_preserves_standard_inputs():
    params, _ = controls.resolve({})
    original = copy.deepcopy(params)
    standard_before, _ = graph_v5t.build_product('image.png', 1024, 768, params, 'output')
    graph, info = fast_recipe.build('image.png', 1024, 768, params, 'output')
    assert params == original
    samplers = [node['inputs'] for node in graph.values() if node['class_type'] == 'KSampler']
    assert len(samplers) == 2
    assert all(item['steps'] == 8 and item['cfg'] == 5.0 for item in samplers)
    loras = [node['inputs'] for node in graph.values() if node['class_type'] == 'LoraLoaderModelOnly']
    assert len(loras) == 1 and loras[0]['strength_model'] == 0.25
    assert loras[0]['lora_name'] == fast_recipe.LORA['file']
    standard_after, _ = graph_v5t.build_product('image.png', 1024, 768, params, 'output')
    assert standard_before == standard_after


def test_fast_rejects_unproved_supersampling():
    params, _ = controls.resolve({})
    with pytest.raises(fast_recipe.FastUnavailable):
        fast_recipe.build('image.png', 1024, 768, params, 'output', s=1)


def test_missing_fast_lora_does_not_offer_fast():
    assert not engine_options.fast_info(files_ok=False)['available']
    assert engine_options.fast_info(files_ok=True)['available']
