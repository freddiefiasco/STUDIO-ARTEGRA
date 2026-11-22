"""5.0.2 build wave 3, the service's half of the start-up probe (G1u; BUILD-WAVE-3 contracts.g1u; service/bxf_probe.py):
the engine runtime's environment read and cached, the table the planner counts assigned before any Large-image plan, the
re-plan of queued images when the table changes (same pixels, the sub-stage checkpoint and the work folder kept), and the
engine's CU_BXF_LOCAL_TABLE.

In this process: G1u with a stub environment read, a Runner of the app's own parts on the fake engine (the in-process harness
of tests/test_integ_large_image_job.py), synthetic tables and sizes only. Where the base planner lacks the plan package's
BXF_TABLE (contracts.g1u), finish_tier is patched to the contract's precedence (a set BXF_TABLE decides, else BXF_AVAILABLE)."""
import json
import os
import sys
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from engine import banded_plan
from engine.bxf import g1
from service import banded_runner, bxf_probe, workers
from service.util import same_plan
import tests.test_integ_large_image_job as J

ROOT = Path(__file__).resolve().parents[1]
# The plan package's planner has the contract's precedence itself (BXF_TABLE as a module attribute); the base's does not, so
# only then is finish_tier patched to it (read at import, before any test patches the attribute with create=True)
PLANNER_G1U = 'BXF_TABLE' in vars(banded_plan)


def committed_env(i=1):
    return dict(g1.committed_tables()[i]['environment'])


def unmatched_env():
    """An environment no committed table matches (another processor)."""
    return dict(g1.committed_tables()[-1]['environment'], processor='Test processor (no G1 table)')


def local_table(env, widths=(8192,), band_gb=(6.0,), whole=()):
    """A local table in the g1_table format for `env`: the committed runtime table's ops, with `whole` classed whole."""
    data = json.loads(json.dumps(g1.committed_tables()[-1]))
    data.update(gate='G1u', environment=dict(env), widths=sorted({int(w) for w in widths} | {8192}),
                band_gb=sorted(float(b) for b in band_gb))
    for op in whole:
        data['ops'][op] = {'verdict': 'whole', 'differing': 1}
    return data


def write_local(state, data):
    d = Path(state) / 'bxf'
    d.mkdir(parents=True, exist_ok=True)
    (d / bxf_probe.LOCAL_TABLE).write_text(json.dumps(data), encoding='utf8')
    return d / bxf_probe.LOCAL_TABLE


def finish_tier_model():
    """contracts.g1u's precedence, as the plan package builds it: a set BXF_TABLE decides, else BXF_AVAILABLE."""
    t = getattr(banded_plan, 'BXF_TABLE', None)
    if t is not None:
        return 'bxf' if t.applies else 'tier3'
    return 'bxf' if banded_plan.BXF_AVAILABLE else 'tier3'


class Log:
    def __init__(self):
        self.lines = []

    def _add(self, level, event, msg, **kw):
        self.lines.append((level, event, msg, kw.get('data')))

    def info(self, event, msg, **kw):
        self._add('info', event, msg, **kw)

    def warn(self, event, msg, **kw):
        self._add('warn', event, msg, **kw)

    def exception(self, event, msg, e, **kw):
        self._add('error', event, msg, **kw)

    def events(self, level=None):
        return [e for lv, e, *_ in self.lines if level is None or lv == level]


class GlobalsRestored(unittest.TestCase):
    """Every test here leaves the planner's module attributes and the G1u stand-ins as it found them."""

    def setUp(self):
        self._g = [mock.patch.object(banded_plan, 'BXF_TABLE', None, create=True),
                   mock.patch.object(banded_plan, 'BXF_TABLE_SOURCE', None, create=True),
                   mock.patch.dict(bxf_probe._STATE, {'local': ''}),
                   mock.patch.object(bxf_probe, 'TEST_ENVIRONMENT', None),
                   mock.patch.object(bxf_probe, 'TEST_PROBE', None)]
        for p in self._g:
            p.start()
        super().setUp()

    def tearDown(self):
        super().tearDown()
        for p in reversed(self._g):
            p.stop()


def runtime_cfg(td):
    td = Path(td)
    py = td / 'runtime' / 'python.exe'
    site = td / 'runtime' / 'site-packages'
    (site / 'torch-2.14.1+cu132.dist-info').mkdir(parents=True)
    (site / 'numpy-2.5.4.dist-info').mkdir()
    (site / 'scipy-1.18.1.dist-info').mkdir()
    py.write_bytes(b'not a real interpreter')
    state = td / 'state'
    state.mkdir()
    return SimpleNamespace(state_dir=state, runtime_python=py, site_packages=site, fake_engine=False)


class TheEnvironmentRead(GlobalsRestored):
    def test_cached_and_read_again_when_the_runtime_changes(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = runtime_cfg(td)
            g = bxf_probe.G1u(cfg, Log())
            calls = []

            def read():
                calls.append(1)
                return committed_env(), {'seconds': 0.1}
            with mock.patch.object(g, 'read_environment', read):
                self.assertEqual(g.environment(), committed_env())
                self.assertEqual(g.environment(), committed_env())
                self.assertEqual(len(calls), 1)                                    # cached in the state folder
                self.assertTrue((cfg.state_dir / 'bxf' / bxf_probe.ENV_FILE).is_file())
                g2 = bxf_probe.G1u(cfg, Log())                                     # the next start reads the cache
                with mock.patch.object(g2, 'read_environment', read):
                    g2.environment()
                self.assertEqual(len(calls), 1)
                site = Path(cfg.site_packages)
                os.rename(site / 'torch-2.14.1+cu132.dist-info', site / 'torch-2.15.0+cu132.dist-info')
                g.environment()
                self.assertEqual(len(calls), 2)                                    # another torch
                Path(cfg.runtime_python).write_bytes(b'another interpreter, another size')
                g.environment()
                self.assertEqual(len(calls), 3)                                    # another interpreter
                with mock.patch('platform.processor', return_value='Another processor'):
                    g.environment()
                self.assertEqual(len(calls), 4)                                    # the state folder on another computer
                g.environment()
                self.assertEqual(len(calls), 5)                                    # and back

    def test_the_command_hides_cuda_and_runs_isolated(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = runtime_cfg(td)
            args = bxf_probe.env_command(cfg)
            self.assertEqual(args[:5], [str(cfg.runtime_python), '-I', '-B', '-S', '-c'])
            self.assertEqual(args[-2:], [str(cfg.site_packages), str(ROOT)])
            env = bxf_probe.child_env()
            self.assertEqual(env['CUDA_VISIBLE_DEVICES'], '')
            self.assertNotIn(bxf_probe.LOCAL_TABLE_ENV, env)

    def test_an_unreadable_environment_counts_tier_3(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = runtime_cfg(td)
            log = Log()
            g = bxf_probe.G1u(cfg, log)
            with mock.patch.object(g, 'read_environment', return_value=(None, {'exit_code': 1})):
                self.assertFalse(g.refresh())
            self.assertIsNone(banded_plan.BXF_TABLE)
            self.assertIn('bxf_env_unread', log.events('warn'))
            self.assertFalse(g.probe_needed([16000], 6.0))                          # nothing to probe against

    def test_the_marked_line_is_parsed(self):
        env = committed_env()
        text = 'noise\n' + bxf_probe.ENV_MARK + json.dumps(env) + '\n'
        self.assertEqual(bxf_probe.parse_environment(text), env)
        self.assertIsNone(bxf_probe.parse_environment('no mark'))
        self.assertIsNone(bxf_probe.parse_environment(bxf_probe.ENV_MARK + '{"torch": "x"}'))     # keys missing

    @unittest.skipUnless(os.name == 'nt', 'the read runs in a Windows Job')
    def test_a_real_read_by_this_interpreter(self):
        """The read itself, with this process's interpreter standing in for the runtime's (numpy here; torch if present)."""
        import sys
        with tempfile.TemporaryDirectory() as td:
            cfg = SimpleNamespace(state_dir=Path(td), runtime_python=Path(sys.executable),
                                  site_packages=Path(__import__('numpy').__file__).resolve().parents[1], fake_engine=False)
            env, detail = bxf_probe.G1u(cfg, Log()).read_environment()
            self.assertIsNotNone(env, detail)
            self.assertEqual(set(g1.ENV_KEYS) - set(env), set())


class TheTable(GlobalsRestored):
    def g1u(self, td, env):
        cfg = SimpleNamespace(state_dir=Path(td), fake_engine=True)
        bxf_probe.TEST_ENVIRONMENT = env
        g = bxf_probe.G1u(cfg, Log(), fake=True)
        g.start(background=False)
        return g

    def test_a_committed_match_needs_no_probe(self):
        with tempfile.TemporaryDirectory() as td:
            g = self.g1u(td, committed_env(1))
            self.assertIs(banded_plan.BXF_TABLE, g.table)
            self.assertTrue(banded_plan.BXF_TABLE.applies)
            self.assertEqual(banded_plan.BXF_TABLE_SOURCE, 'committed')
            self.assertTrue(g.committed_applies())
            self.assertFalse(g.probe_needed([16000, 32000], 6.0))
            self.assertEqual(bxf_probe.local_table_env(), '')
        for i in (1, 2):                                       # the workstation's and the render nodes' runtime tables
            with tempfile.TemporaryDirectory() as td:
                self.assertEqual(self.g1u(td, committed_env(i)).source, 'committed')

    def test_no_match_leaves_the_planner_at_tier_3_and_asks_for_the_probe(self):
        with tempfile.TemporaryDirectory() as td:
            g = self.g1u(td, unmatched_env())
            self.assertIsNone(banded_plan.BXF_TABLE)            # never a table that does not apply (BXF_AVAILABLE keeps its meaning)
            self.assertIsNone(banded_plan.BXF_TABLE_SOURCE)
            self.assertTrue(g.probe_needed([16000], 6.0))
            self.assertFalse(g.probe_needed([], 6.0))
            g.mark_failed([16000], 6.0, bxf_probe.PROBE_FAILED)
            self.assertFalse(g.probe_needed([16000], 6.0))      # not again this session
            self.assertFalse(g.probe_needed([32000], 6.0))      # nor for other widths at that band budget

    def test_a_local_table_alone_and_its_coverage(self):
        with tempfile.TemporaryDirectory() as td:
            env = unmatched_env()
            path = write_local(td, local_table(env, widths=(16000,), band_gb=(6.0,)))
            g = self.g1u(td, env)
            self.assertEqual(g.source, 'local')
            self.assertTrue(banded_plan.BXF_TABLE.applies)
            self.assertEqual(banded_plan.BXF_TABLE_SOURCE, 'local')
            self.assertEqual(bxf_probe.local_table_env(), str(path))
            self.assertFalse(g.probe_needed([16000], 6.0))
            self.assertTrue(g.probe_needed([16000, 32000], 6.0))        # a later plan of another width
            self.assertTrue(g.probe_needed([16000], 3.0))               # another band budget
            self.assertEqual(g.probe_widths([32000], 6.0), [16000, 32000])   # probed again with the union of widths

    def test_a_local_table_vetoes_on_top_of_a_committed_one(self):
        with tempfile.TemporaryDirectory() as td:
            env = committed_env(1)
            banded_ops = sorted(op for op, v in g1.committed_tables()[1]['ops'].items() if v.get('verdict') == 'banded')
            write_local(td, local_table(env, whole=banded_ops[:1]))
            g = self.g1u(td, env)
            self.assertEqual(g.source, 'committed+local')
            self.assertIsInstance(banded_plan.BXF_TABLE, g1.Vetoed)
            self.assertEqual(banded_plan.BXF_TABLE.verdict(banded_ops[0]), 'whole')
            self.assertEqual(bxf_probe.moved_to_whole(banded_plan.BXF_TABLE), banded_ops[:1])
            self.assertFalse(g.probe_needed([16000], 6.0))              # a committed table applies: never a probe

    def test_a_local_table_of_another_environment_is_not_read(self):
        with tempfile.TemporaryDirectory() as td:
            write_local(td, local_table(dict(unmatched_env(), torch='0.0')))
            g = self.g1u(td, unmatched_env())
            self.assertIsNone(g.source)
            self.assertIsNone(banded_plan.BXF_TABLE)
            self.assertEqual(bxf_probe.local_table_env(), '')

    def test_the_fake_engine_without_a_stand_in_changes_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            g = bxf_probe.G1u(SimpleNamespace(state_dir=Path(td), fake_engine=True), Log(), fake=True)
            sentinel = object()
            banded_plan.BXF_TABLE = sentinel
            g.start()
            self.assertTrue(g.ready.is_set())
            self.assertFalse(g.enabled)
            self.assertIs(banded_plan.BXF_TABLE, sentinel)               # untouched: tests that patch BXF_AVAILABLE keep it
            self.assertFalse(g.refresh())


class ServiceBase(GlobalsRestored, J.Base):
    """The in-process service with the G1u stand-ins and the contract's planner precedence."""
    ram_gb = J.RAM_WS

    def setUp(self):
        super().setUp()
        if not PLANNER_G1U:
            p = mock.patch.object(banded_plan, 'finish_tier', finish_tier_model)
            p.start()
            self.addCleanup(p.stop)

    def service(self, state='state', ram_gb=None, env=None, probe=None):
        bxf_probe.TEST_ENVIRONMENT = env
        bxf_probe.TEST_PROBE = probe
        svc = super().service(state, ram_gb)
        self.assertTrue(svc.runner.g1u.ready.wait(30))
        return svc


class BeforeEveryLargeImagePlan(ServiceBase):
    def test_the_table_is_assigned_before_the_plan_is_made(self):
        seen = []
        real = banded_plan.plan_banded

        def spy(*a, **k):
            seen.append((getattr(banded_plan, 'BXF_TABLE', None), getattr(banded_plan, 'BXF_TABLE_SOURCE', None)))
            return real(*a, **k)

        def slow_env():                         # the read takes a moment; the plan waits for it
            time.sleep(0.5)
            return committed_env(1)
        with mock.patch.object(banded_plan, 'plan_banded', spy):
            bxf_probe.TEST_ENVIRONMENT = slow_env
            svc = J.InProcessService(self.td / 'state', self.ram_gb)
            mid = svc.add(J.strip_input(self.td / 'in', 'wide.png', 4000, 64))
            job = svc.job([mid], {'scale': 8})
        self.assertTrue(seen)
        self.assertTrue(all(t is not None and t.applies and s == 'committed' for t, s in seen), seen)
        plan = job['items'][0]['plan']
        self.assertEqual(plan['banded']['finish_tier'], 'bxf')

    def test_with_no_table_the_plan_counts_tier_3(self):
        svc = self.service(env=unmatched_env())
        mid = svc.add(J.strip_input(self.td / 'in', 'wide.png', 4000, 64))
        job = svc.job([mid], {'scale': 8})
        self.assertEqual(job['items'][0]['plan']['banded']['finish_tier'], 'tier3')


class TheReplanWhenTheTableLands(ServiceBase):
    def test_queued_images_take_the_table_and_keep_their_work(self):
        env = unmatched_env()
        svc = self.service(env=env)
        mid = svc.add(J.strip_input(self.td / 'in', 'wide.png', 4000, 64))
        job = svc.job([mid], {'scale': 8})
        jid, iid = job['id'], 'i001'
        old = svc.item(jid)['plan']
        self.assertEqual(old['banded']['finish_tier'], 'tier3')
        work = svc.cfg.work_dir / jid / iid
        marker = work / 'planes' / 's0' / 'checkpoint.json'
        marker.parent.mkdir(parents=True)
        marker.write_text('{}', encoding='utf8')
        widths = sorted({banded_plan.finish_size(s)[0] for s in old['stages']})
        write_local(svc.state, local_table(env, widths=widths, band_gb=(6.0,)))
        self.assertTrue(svc.runner.g1u.refresh(reason='probe'))
        new = svc.item(jid)['plan']
        self.assertEqual(new['banded']['finish_tier'], 'bxf')
        self.assertTrue(same_plan(old, new))                              # the same pixels
        self.assertEqual(svc.item(jid)['state'], 'queued')
        self.assertTrue((work / 'input.png').is_file())                   # the work folder is kept
        self.assertTrue(marker.is_file())
        self.assertIn('item_replanned', [e['event'] for e in svc.events()])
        self.assertFalse(svc.runner.g1u.refresh(reason='probe'))          # nothing changed: no re-plan
        self.assertEqual(svc.run_all(), [])
        it = self.done(svc, jid)
        self.assertEqual(svc.worker.bxf_local_table, str(svc.state / 'bxf' / bxf_probe.LOCAL_TABLE))
        side = json.loads(Path(it['sidecar']).read_text(encoding='utf8'))
        self.assertEqual(side['engine']['cpu_capability'], env['cpu_capability'])
        self.assertIn('bxf_table', side['engine'])

    def test_a_resumed_pass_keeps_its_checkpoint_when_the_table_lands(self):
        """The contract's case: the engine dies in prompt B of pass 2 at tier 3; after the restart the table lands, the
        queued image is planned again ('bxf'), and the pass goes on from its saved first part: prompt A of it ran once."""
        from tests.service.helpers import split_strip_height
        env = unmatched_env()
        svc = self.service('state-c', env=env)
        h = split_strip_height(float(svc.settings.get()['ram_cap_gb']), service=False)
        self.assertIsNotNone(h)
        mid = svc.add(J.strip_input(self.td / 'in', 'wide.png', 4000, h))
        job = svc.job([mid], {'scale': 8})
        jid = job['id']
        self.assertEqual(job['items'][0]['plan']['banded']['finish_tier'], 'tier3')
        J.InProcessFake.die_at = (1, 'B')
        self.assertEqual(len(svc.run_all()), 1)
        ck = svc.cfg.work_dir / jid / 'i001' / 'planes' / 's1' / 'checkpoint.json'
        self.assertTrue(ck.is_file())
        svc2 = self.service('state-c', env=env)                          # the restart
        self.assertEqual(svc2.item(jid)['state'], 'queued')
        old = svc2.item(jid)['plan']
        write_local(svc2.state, local_table(env, widths=[banded_plan.finish_size(s)[0] for s in old['stages']]))
        self.assertTrue(svc2.runner.g1u.refresh(reason='probe'))
        new = svc2.item(jid)['plan']
        self.assertEqual(new['banded']['finish_tier'], 'bxf')
        self.assertTrue(same_plan(old, new))
        self.assertTrue(ck.is_file())                                      # the re-plan kept the checkpoint
        self.assertEqual(svc2.run_all(), [])
        self.done(svc2, jid)
        self.assertIn('banded_checkpoint_resume', [e['event'] for e in svc2.events()])
        self.assertNotIn('banded_checkpoint_refused', [e['event'] for e in svc2.events()])
        self.assertEqual(len([r for r in svc2.renders() if r['prefix'].endswith('_s1_a')]), 1)   # prompt A of pass 2 once

    def test_a_running_image_is_not_replanned(self):
        env = unmatched_env()
        svc = self.service(env=env)
        mid = svc.add(J.strip_input(self.td / 'in', 'wide.png', 4000, 64))
        job = svc.job([mid], {'scale': 8})
        jid = job['id']
        svc.runner.ctx[(jid, 'i001')] = SimpleNamespace(worker_released=False, worker=svc.worker)
        old = svc.item(jid)['plan']
        write_local(svc.state, local_table(env, widths=[banded_plan.finish_size(s)[0] for s in old['stages']]))
        svc.runner.g1u.refresh(reason='probe')
        self.assertEqual(svc.item(jid)['plan'], old)
        svc.runner.ctx.clear()

    def test_the_checkpoint_ignores_the_table_constant(self):
        self.assertIn('bxf_table', banded_runner.CHECKPOINT_IGNORED_CONSTANTS)
        consts = dict(banded_plan.constants('redux'), machine_class='ws128', bxf_band_gb=6.0, bxf_processes=4,
                      finish_tier='tier3', bxf_table=None)
        later = dict(consts, finish_tier='bxf', bxf_table='local')
        self.assertEqual(banded_runner.checkpoint_constants(consts), banded_runner.checkpoint_constants(later))
        st = {'bxf_whole_passes': [], 'fresh_worker': True}
        plan_a = {'factor': 8, 'input_size': [4000, 64], 'output_size': [32000, 512], 'engine': 'banded', 'banded': consts,
                  'stages': [dict(index=0, factor=2.0, supersample=2.0, input_size=[4000, 64], padded_size=[4000, 64],
                                  render_size=[16000, 256], output_size=[8000, 128])]}
        plan_b = dict(plan_a, banded=later, stages=[dict(plan_a['stages'][0], **st)])
        self.assertTrue(same_plan(plan_a, plan_b))                        # the new stage keys are not pixel keys


class TheEngineEnvironment(GlobalsRestored):
    def worker(self, td, multi=False):
        cfg = SimpleNamespace(workers_dir=Path(td), state_dir=Path(td))
        settings = SimpleNamespace(get=lambda: {'ram_cap_gb': 59.0, 'memory_profile': 'auto'})
        if multi:
            return workers.MultiCardWorker([0, 1], cfg, settings, Log(), 'fake')
        return workers.Worker(0, cfg, settings, Log(), 'fake')

    def test_every_engine_start_carries_the_local_table(self):
        with tempfile.TemporaryDirectory() as td:
            for multi in (False, True):
                w = self.worker(td, multi)
                self.assertIsNone(w.bxf_local_table)
                env = w._env()
                self.assertEqual(env[bxf_probe.LOCAL_TABLE_ENV], '')
                self.assertEqual(w.bxf_local_table, '')
                bxf_probe._STATE['local'] = str(Path(td) / 'bxf' / 'local-table.json')
                env = w._env()
                self.assertEqual(env[bxf_probe.LOCAL_TABLE_ENV], bxf_probe._STATE['local'])
                self.assertEqual(w.bxf_local_table, bxf_probe._STATE['local'])
                self.assertTrue(banded_runner.stale_table(w) is False)
                bxf_probe._STATE['local'] = ''
                self.assertTrue(banded_runner.stale_table(w))               # started with another table: restarted
                os.environ[bxf_probe.LOCAL_TABLE_ENV] = 'a value of the service own environment'
                try:
                    self.assertEqual(w._env()[bxf_probe.LOCAL_TABLE_ENV], '')  # the planner's, never inherited
                finally:
                    del os.environ[bxf_probe.LOCAL_TABLE_ENV]

    def test_the_classic_start_is_unchanged(self):
        """G0d for the engine start: the command line is 5.0.1's (no new argument), the environment gains only
        CU_BXF_LOCAL_TABLE, and the classic node pack never reads it."""
        with tempfile.TemporaryDirectory() as td:
            w = self.worker(td)
            env = w._env()
            base = {k: v for k, v in os.environ.items() if k.upper() not in workers.SECRET_ENV}
            added = set(env) - set(base)
            self.assertLessEqual(added - {bxf_probe.LOCAL_TABLE_ENV}, {
                'TEMP', 'TMP', 'HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE', 'PYTHONDONTWRITEBYTECODE', 'PYTHONNOUSERSITE',
                'PYTHONUNBUFFERED', 'PYTHONIOENCODING', 'CLAUDE_LIVE_MAX_SIDE', 'CLAUDE_LIVE_GROUPS'})
            rt = Path(td) / 'rt'
            cfg = SimpleNamespace(runtime_python=str(rt / 'python.exe'), comfy_main=str(rt / 'ComfyUI' / 'main.py'),
                                  site_packages=str(rt / 'site'), models_dir=str(Path(td) / 'm'))
            args = workers.comfy_command(cfg, td, 1234, Path(td) / 'x.yaml')
            self.assertNotIn(bxf_probe.LOCAL_TABLE_ENV, ' '.join(args))
        for p in (ROOT / 'node_pack' / 'claude_creative').rglob('*.py'):
            self.assertNotIn(bxf_probe.LOCAL_TABLE_ENV, p.read_text(encoding='utf8'), p.name)
        self.assertEqual(bxf_probe.LOCAL_TABLE_ENV, g1.LOCAL_TABLE_ENV)


class TheTestLauncher(GlobalsRestored):
    def test_its_stand_ins_and_no_product_code_reads_them(self):
        from tests.qa import launch_service
        env = launch_service.install_g1u_stand_ins(json.dumps({'environment': 'committed:2', 'probe': [sys.executable, 'x']}))
        self.assertEqual(env, committed_env(2))
        self.assertEqual(bxf_probe.TEST_ENVIRONMENT, committed_env(2))
        self.assertEqual(bxf_probe.TEST_PROBE, [sys.executable, 'x'])
        self.assertEqual(launch_service.install_g1u_stand_ins(json.dumps({'environment': 'unmatched'}))['processor'],
                         'Test processor (no G1 table)')
        for p in list((ROOT / 'service').glob('*.py')) + list((ROOT / 'engine').rglob('*.py')) + list(
                (ROOT / 'host').rglob('*.py')):
            text = p.read_text(encoding='utf8')
            self.assertNotIn('CU_TEST_BXF_G1U', text, p.name)
            if p.name != 'bxf_probe.py':
                self.assertNotIn('TEST_ENVIRONMENT', text, p.name)
                self.assertNotIn('TEST_PROBE', text, p.name)


if __name__ == '__main__':
    unittest.main()
