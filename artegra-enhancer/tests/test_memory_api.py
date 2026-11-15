"""Exercise the actual settings endpoint while a worker or preview owns the engine."""
from types import SimpleNamespace
import threading
from unittest.mock import Mock
import pytest
from service.api import _Handler
from service.errors import ApiError
from service.settings import validate


def handler(body, activity=None):
    saved = {'memory_profile': 'auto'}
    settings = SimpleNamespace(get=lambda: dict(saved))
    def update(value, gpus):
        saved.update(validate(value, gpus, check_output=False))
        return dict(saved)
    settings.update = update
    runner = SimpleNamespace(_lock=threading.RLock(), ctx={}, _mask_inflight={}, _mask_waiting=0,
                             workers={}, multi={}, available_gpus=lambda: [],
                             faster_info=lambda: {'available': False},
                             invalidate_problems=Mock(), wake=Mock(), _sync_workers=Mock())
    if activity == 'image': runner.ctx[('j1', 'i1')] = object()
    if activity == 'mask': runner._mask_inflight['m1'] = object()
    if activity == 'waiting_mask': runner._mask_waiting = 1
    if activity == 'worker': runner.workers[0] = SimpleNamespace(busy=True)
    if activity == 'multi': runner.multi[0] = SimpleNamespace(busy=True)
    h = object.__new__(_Handler)
    h.app = SimpleNamespace(settings=settings, runner=runner)
    h._body = lambda: body
    h._settings_out = lambda s: s
    h._json = Mock()
    return h, saved


@pytest.mark.parametrize('activity', ['image', 'mask', 'waiting_mask', 'worker', 'multi'])
def test_profile_change_during_work_is_rejected_without_mutation(activity):
    h, saved = handler({'memory_profile': 'balanced'}, activity)
    with pytest.raises(ApiError) as exc:
        h.r_settings_post({})
    assert exc.value.status == 409
    assert saved['memory_profile'] == 'auto'
    h.app.runner.wake.assert_not_called()
    h.app.runner._sync_workers.assert_not_called()


def test_idle_reference_preference_is_saved_and_wakes_scheduler():
    h, saved = handler({'memory_profile': 'auto'})
    h.r_settings_post({})
    assert saved['memory_profile'] == 'auto'
    h._json.assert_called_once_with(200, saved)
    h.app.runner.wake.assert_called_once()
    h.app.runner._sync_workers.assert_called_once()


def test_unknown_profile_is_rejected():
    h, saved = handler({'memory_profile': 'unlimited'})
    with pytest.raises(ApiError) as exc:
        h.r_settings_post({})
    assert exc.value.status == 400
    assert saved['memory_profile'] == 'auto'


def test_idle_balanced_setting_persists_and_restarts_warm_worker(tmp_path):
    from service.settings import Settings
    from service.runner import Runner
    from service import memory_policy
    settings=Settings(tmp_path/'settings.json',tmp_path,Mock(),total_ram_gb=64)
    h,_=handler({'memory_profile':'balanced'})
    runner=h.app.runner
    runner.settings=settings
    runner.gpu_list=lambda: ([{'index':0,'name':'QA GPU','mem_total_gb':32}],None)
    runner.store=SimpleNamespace(parallelism=1)
    stopped=[]
    worker=SimpleNamespace(busy=False,memory_profile=memory_policy.PROFILES['reference'],
                           stop=lambda reason: stopped.append(reason))
    runner.workers={0:worker}
    runner._sync_workers=lambda: Runner._sync_workers(runner)
    h.app.settings=settings
    h.r_settings_post({})
    assert settings.get()['memory_profile']=='balanced'
    assert Settings(tmp_path/'settings.json',tmp_path,Mock(),total_ram_gb=64).get()['memory_profile']=='balanced'
    assert stopped==['memory profile changed']
    assert worker.memory_profile==memory_policy.PROFILES['balanced']
    runner._sync_workers()
    assert stopped==['memory profile changed']
    h._json.assert_called_once()
    assert h._json.call_args.args[0]==200
    assert h._json.call_args.args[1]['memory_profile']=='balanced'
