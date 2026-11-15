"""Conservative profile selection and memory safeguards."""
from copy import deepcopy
from types import SimpleNamespace
import pytest

from engine import controls, graph_v5t, fast_recipe
from service import memory_policy as m
from service.settings import default_ram_cap_gb, validate, SettingsError
from service.workers import COMFY_FLAGS, comfy_command, parse_nvidia_smi


@pytest.mark.parametrize('vram,expected', [(32,'reference'),(24.001,'reference'),(24,'balanced'),
    (16,'balanced'),(12,'balanced'),(10,'balanced'),(8,'balanced'),(0,'reference'),(-1,'reference'),
    (None,'reference'),(float('nan'),'reference'),(float('inf'),'reference'),(True,'reference')])
def test_auto_uses_conservative_profile_only_at_known_positive_capacity_up_to_24(vram, expected):
    assert m.choose_profile(vram).name == expected
    assert set(m.PROFILES) == {'reference','balanced'}


@pytest.mark.parametrize('vram', [32,24,16,12,10,8,None,float('nan')])
def test_explicit_preference_is_honored(vram):
    assert m.choose_profile(vram,'reference') == m.PROFILES['reference']
    assert m.choose_profile(vram,'balanced') == m.PROFILES['balanced']


@pytest.mark.parametrize('requested', ['compact','minimum','high',None,True,[],{}])
def test_unqualified_requests_are_rejected(requested):
    with pytest.raises(ValueError, match='qualification has not passed'):
        m.choose_profile(32, requested)


@pytest.mark.parametrize('fast', [False,True])
@pytest.mark.parametrize('vram', [32,24,16,12,10])
def test_graph_and_metadata_unchanged_at_every_capacity(fast, vram):
    params,_=controls.resolve({'seed':'20261102'})
    build=fast_recipe.build if fast else graph_v5t.build_product
    graph,info=build('input.png',768,768,params,'qa',live_preview='rough')
    original,original_info=deepcopy(graph),deepcopy(info)
    same,sameinfo=m.apply_graph(graph,info,m.choose_profile(vram,'reference'))
    assert same is graph and sameinfo is info
    assert same==original and sameinfo==original_info


def test_launch_flags_and_reference_graph_cannot_accept_unqualified_profile(tmp_path):
    cfg=SimpleNamespace(runtime_python=tmp_path/'python.exe',comfy_main=tmp_path/'main.py',
                        site_packages=tmp_path/'site',models_dir=tmp_path/'models')
    reference=comfy_command(cfg,tmp_path,1234,tmp_path/'models.yaml')
    for capacity in (32,24,16,12,10):
        assert comfy_command(cfg,tmp_path,1234,tmp_path/'models.yaml',m.choose_profile(capacity,'reference'))==reference
    assert '--lowvram' not in reference and '--cache-none' not in reference
    assert m.launch_flags(COMFY_FLAGS,m.PROFILES['reference'])==COMFY_FLAGS
    unqualified=m.MemoryProfile('minimum',512,512,256,1,True,1.0)
    with pytest.raises(ValueError,match='qualification has not passed'):
        m.launch_flags(COMFY_FLAGS,unqualified)
    with pytest.raises(ValueError,match='qualification has not passed'):
        m.apply_graph({}, {}, unqualified)


def test_ram_budget_never_assumes_large_machine():
    assert default_ram_cap_gb(16)==12
    assert default_ram_cap_gb(32)==28
    assert default_ram_cap_gb(64)==57.6
    assert default_ram_cap_gb(128)==115.2
    assert default_ram_cap_gb(float('nan'))==16

def test_first_image_checks_ram_and_commit():
    memory={'avail_phys_gb':50,'commit_available_gb':60}
    assert m.admission_problem(35,[],57.6,memory) is None
    assert 'commit' in m.admission_problem(35,[],57.6,dict(memory,commit_available_gb=20))
    assert 'system RAM' in m.admission_problem(35,[],57.6,dict(memory,avail_phys_gb=8))
    assert 'could not be read' in m.admission_problem(35,[],57.6,None)
    assert 'budget' in m.admission_problem(35,[35],57.6,memory)

def test_warm_worker_only_reuses_current_owned_commit():
    memory={'avail_phys_gb':15,'commit_available_gb':10}
    assert m.admission_problem(35,[],57.6,memory,reusable_commit_gb=30) is None
    assert 'commit' in m.admission_problem(35,[],57.6,memory,reusable_commit_gb=0)

def test_memory_settings_and_driver_parse():
    for good in ('auto', 'reference', 'balanced'):
        assert validate({'memory_profile':good},[],False)['memory_profile']==good
    for bad in ('compact','minimum','high',None,True,[],{}):
        with pytest.raises(SettingsError):
            validate({'memory_profile':bad},[],False)
    rows=parse_nvidia_smi('0, GPU-abc, NVIDIA RTX 5090, 30000, 32607, 595.98')
    assert rows[0]['driver_version']=='595.98'
    assert 'driver_version' not in parse_nvidia_smi('0, GPU-a, GPU, 1000, 2000')[0]


def test_driver_tool_discovery_without_path(tmp_path, monkeypatch):
    from service import workers
    monkeypatch.setattr(workers.shutil, 'which', lambda _: None)
    win=tmp_path/'Windows'; pf=tmp_path/'Program Files'
    monkeypatch.setenv('SystemRoot', str(win))
    monkeypatch.setenv('ProgramFiles', str(pf))
    monkeypatch.setenv('ProgramW6432', str(pf))
    assert workers.find_nvidia_smi() is None
    legacy=pf/'NVIDIA Corporation'/'NVSMI'/'nvidia-smi.exe'
    legacy.parent.mkdir(parents=True); legacy.touch()
    assert workers.find_nvidia_smi()==str(legacy)
    system=win/'System32'/'nvidia-smi.exe'
    system.parent.mkdir(parents=True); system.touch()
    assert workers.find_nvidia_smi()==str(system)


def test_reference_preference_change_does_not_restart_unchanged_worker():
    import threading
    from service.runner import Runner
    stopped=[]
    worker=SimpleNamespace(busy=False, memory_profile=m.PROFILES['reference'],
                           stop=lambda why: stopped.append(why))
    runner=SimpleNamespace(_lock=threading.RLock(),
        settings=SimpleNamespace(get=lambda: {'gpus':[0],'memory_profile':'reference'}),
        gpu_list=lambda: ([{'index':0,'mem_total_gb':16}],None),
        workers={0:worker},multi={},store=SimpleNamespace(parallelism=1))
    Runner._sync_workers(runner)
    assert not stopped and worker.memory_profile==m.PROFILES['reference']
