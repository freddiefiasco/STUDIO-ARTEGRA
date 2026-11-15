"""Hardware-independent guards; real card qualification is recorded separately."""
from copy import deepcopy
from types import SimpleNamespace
import pytest

from engine import controls, graph_v5t, fast_recipe
from service import memory_policy as m
from service.settings import default_ram_cap_gb, validate, SettingsError
from service.workers import COMFY_FLAGS, comfy_command, parse_nvidia_smi

@pytest.mark.parametrize('vram,expected', [(32,'reference'), (24,'balanced'), (16,'compact'),
                                           (12,'minimum'), (10,'minimum'), (None,'minimum'),
                                           (float('nan'),'minimum')])
def test_profile_for_installed_capacity(vram, expected):
    assert m.choose_profile(vram).name == expected

@pytest.mark.parametrize('vram,requested,expected', [(10,'balanced','minimum'),(16,'balanced','compact'),
                                                  (32,'minimum','minimum'),(32,'balanced','balanced')])
def test_override_can_only_reduce_memory(vram, requested, expected):
    assert m.choose_profile(vram, requested).name == expected

@pytest.mark.parametrize('fast', [False,True])
def test_graph_reference_unchanged_and_compatibility_preserves_recipe(fast):
    params,_=controls.resolve({'seed':'20261102'})
    build=fast_recipe.build if fast else graph_v5t.build_product
    graph,info=build('input.png',768,768,params,'qa',live_preview='rough')
    original=deepcopy(graph)
    same,sameinfo=m.apply_graph(graph,info,m.PROFILES['reference'])
    assert same is graph and sameinfo is info and same==original
    changed,changedinfo=m.apply_graph(graph,info,m.PROFILES['minimum'])
    assert graph==original
    for key,node in graph.items():
        new=changed[key]
        assert new['class_type']==node['class_type']
        if node['class_type']=='ClaudeSpotTiles':
            assert new['inputs']['tile_px']==512
            assert new['inputs']['batch_windows']==1
            assert not new['inputs']['pag_fuse']
            if fast:
                assert new['inputs']['seam_overlap']==16
        elif node['class_type'] in ('VAEEncodeTiled','VAEDecodeTiled'):
            assert new['inputs']['tile_size']==512 and new['inputs']['overlap']==64
        elif node['class_type']=='ClaudeUpscaleModelTiled':
            assert new['inputs']['tile']==256 and new['inputs']['margin']==64
        elif node['class_type']=='ClaudeCannyTiled':
            assert new['inputs']['tile']==1024
        else:
            assert new==node  # checkpoint, LoRA, seeds, conditioning, samples and finish untouched
    assert changedinfo['output']==info['output']

def test_launch_keeps_reference_and_adds_low_memory_flags(tmp_path):
    cfg=SimpleNamespace(runtime_python=tmp_path/'python.exe',comfy_main=tmp_path/'main.py',
                        site_packages=tmp_path/'site',models_dir=tmp_path/'models')
    ref=comfy_command(cfg,tmp_path,1234,tmp_path/'models.yaml')
    assert '--lowvram' not in ref and '--cache-none' not in ref
    small=comfy_command(cfg,tmp_path,1234,tmp_path/'models.yaml',m.PROFILES['minimum'])
    assert all(f in small for f in ('--lowvram','--cache-none','--disable-smart-memory','--disable-dynamic-vram'))
    assert COMFY_FLAGS[COMFY_FLAGS.index('--reserve-vram')+1]=='0.8'

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
    assert validate({'memory_profile':'compact'},[],False)['memory_profile']=='compact'
    for bad in ('reference','high',None,True,[],{}):
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


def test_idle_workers_restart_on_profile_change():
    import threading
    from service.runner import Runner
    stopped=[]
    worker=SimpleNamespace(busy=False, memory_profile=m.PROFILES['reference'],
                           stop=lambda why: stopped.append(why))
    runner=SimpleNamespace(_lock=threading.RLock(),
        settings=SimpleNamespace(get=lambda: {'gpus':[0],'memory_profile':'minimum'}),
        gpu_list=lambda: ([{'index':0,'mem_total_gb':32}],None),
        workers={0:worker},multi={},store=SimpleNamespace(parallelism=1))
    Runner._sync_workers(runner)
    assert len(stopped)==1 and worker.memory_profile==m.PROFILES['minimum']
    Runner._sync_workers(runner)
    assert len(stopped)==1
