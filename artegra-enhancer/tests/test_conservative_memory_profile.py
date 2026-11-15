"""Conservative profile: exact graph and launch differences from Reference."""
from copy import deepcopy

import pytest

from engine import controls, fast_recipe, graph_v5t
from service import memory_policy
from service.workers import COMFY_FLAGS


@pytest.mark.parametrize('mode', ['standard', 'fast'])
@pytest.mark.parametrize('live', ['rough', 'detailed'])
def test_balanced_candidate_only_changes_window_batch(mode, live):
    params, _ = controls.resolve({'preset': 'Default', 'seed': '314159', 'scale': 2})
    build = fast_recipe.build if mode == 'fast' else graph_v5t.build_product
    graph, info = build('input.png', 384, 384, params, 'candidate', live_preview=live)
    before_graph, before_info = deepcopy(graph), deepcopy(info)
    expected_graph, expected_info = deepcopy(graph), deepcopy(info)
    count = 0
    for node in expected_graph.values():
        if node['class_type'] == 'ClaudeSpotTiles':
            assert node['inputs']['batch_windows'] == 2
            assert node['inputs']['tile_px'] == 1024
            assert node['inputs']['noise_prefetch'] is True
            assert node['inputs']['pag_fuse'] is True
            assert node['inputs']['fp16_acc_scoped'] is True
            node['inputs']['batch_windows'] = 1
            count += 1
    assert count > 0
    expected_info['spot_options']['batch_windows'] = 1
    got_graph, got_info = memory_policy.apply_graph(graph, info, memory_policy.PROFILES['balanced'])
    assert got_graph == expected_graph
    assert got_info == expected_info
    assert graph == before_graph and info == before_info
    profile = memory_policy.PROFILES['balanced']
    assert (profile.tile_px, profile.vae_tile, profile.dat_tile) == (1024, 1024, 512)


def test_balanced_candidate_only_changes_loading_and_reserve():
    before = list(COMFY_FLAGS)
    expected = list(COMFY_FLAGS)
    expected[expected.index('--reserve-vram') + 1] = '1.0'
    expected.append('--lowvram')
    actual = memory_policy.launch_flags(COMFY_FLAGS, memory_policy.PROFILES['balanced'])
    assert actual == expected
    assert '--cache-none' not in actual
    assert '--disable-smart-memory' not in actual
    assert COMFY_FLAGS == before
    assert memory_policy.launch_flags(COMFY_FLAGS, memory_policy.PROFILES['reference']) == before


@pytest.mark.parametrize('requested', ['compact','minimum'])
def test_failed_experimental_profiles_stay_rejected(requested):
    with pytest.raises(ValueError, match='qualification has not passed'):
        memory_policy.choose_profile(32, requested)
