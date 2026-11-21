"""The whole Large-image job on the fake engine, in this process (BUILD-WAVE-2 package integ, item 2): no service and no port.

A Runner made with the app's own parts (config, Settings, JobStore, MediaLibrary, Logger) but without its start-up (no scheduler
or health thread, no HTTP server), a worker of the service's own class (service/workers.Worker) whose fake engine runs in this
process without its HTTP server: service/fake_comfy.FakeComfy's own submit (the graph validation against NODE_SPECS) and
_execute (the run order, the output nodes' planes), queued and run in the caller's thread by a client in place of ComfyClient.
The job goes the service's own way: Runner.create_job (the planner: banded_plan.plan_banded, or plan_forced with the developer
force switch), Runner._dispatch, Runner._run_item_safe in its item thread, banded_runner.run_stage for every pass (the split
finish restarting the worker through Worker.stop and ensure_started), Runner._finish with banded_runner.encode_publish (the
streamed writers of service/plane_io.py), and the viewer routes of service/api.py (_Handler.r_region, r_proxy, r_thumb), called
in-process.

Covered: full-width plans whose longest side is 28,000 px and 32,000 px, every pass; every node of the merged
graph_banded.NODE_SPECS in the graphs the engine was given; the split finish (the workstation class splits every stage) and
the one-prompt stage (the 64 GB class); resume from the sub-stage checkpoint after the engine died in prompt B of a pass (a new
Runner on the same state, as after a restart); every writer (PNG 8 and 16, TIFF 16 and BigTIFF, JPEG) on an RGBA input; the
viewer's lossless region, proxy and sized copy cut from the result plane; the developer force switch (plan_forced). Thin
plans (64 px tall inputs) keep it cheap; one full-area stage (8x of 3500 x 2188: a 28,000 x 17,504 px result, 490 MP, which sets
banded_plan.BXF_AVAILABLE test-locally) runs only with CU_INTEG_FULL_AREA=1 (about 60 GB of free work disk; run it alone).
Sizes and synthetic pictures only."""
import io
import json
import os
import shutil
import tempfile
import threading
import time
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np
from PIL import Image

from engine import banded_plan, graph_banded, planes
from service import api, build_channel, config, fake_comfy, plane_io, workers
from service.logs import Logger
from service.media import MediaLibrary
from service.runner import Runner
from service.settings import Settings
from service.store import JobStore
from tests.service.helpers import gradient, read_png16, read_tiff16

ROOT = Path(__file__).resolve().parents[1]
PROVEN = {'ws128': 2000.0, 'pc64': 2000.0, 'pc48': 2000.0}
RAM_WS, RAM_PC = 128.0, 61.56              # the workstation's class (cap 122.8 GiB) and a 64 GB PC's (59.0 GiB)
FULL_AREA = os.environ.get('CU_INTEG_FULL_AREA') == '1'


class EngineDied(BaseException):
    """The engine process ended in the middle of a prompt (the fake's CU_FAKE_FAULT crash, in this process): the item thread
    ends with no record written, as the service process would."""


class InProcessFake(fake_comfy.FakeComfy):
    """The fake engine without its HTTP server or WebSocket: start() binds nothing. die_at = (stage, part): the engine dies
    once at that prompt's output node (part 'B' is a split stage's finish prompt)."""
    registry = {}
    die_at = None

    def __init__(self, root, gpu=0, **kw):
        super().__init__(root, gpu=gpu, stage_seconds=0.0, faults='', fault_dir=None)

    def start(self):
        port = 100000 + len(InProcessFake.registry)      # a key for the client, never a socket
        InProcessFake.registry[port] = self
        self.port = port
        self.alive = True
        return port

    def stop(self):
        self.alive = False

    def _save_planes(self, graph, nid, wider=0):
        die = InProcessFake.die_at
        if die is not None and graph[nid]['class_type'] == 'CUFinishBanded':
            prefix = graph[nid]['inputs']['filename_prefix']
            part_b = not any(v['class_type'] == 'KSampler' for v in graph.values())
            if prefix.endswith(f'_s{die[0]}') and part_b == (die[1] == 'B'):
                InProcessFake.die_at = None
                raise EngineDied(prefix)
        return super()._save_planes(graph, nid, wider)


class InProcessClient:
    """service/comfy.ComfyClient's calls the runner makes, on an InProcessFake: a prompt is validated and queued by the fake's
    own submit and run at once by its own _execute; history, object_info and system_stats are read from it."""

    def __init__(self, port):
        self.fake = InProcessFake.registry[port]
        self.prompts_sent = 0

    def prompt(self, graph, client_id, prompt_id=None):
        try:
            pid, _ = self.fake.submit(graph, client_id, prompt_id)
        except fake_comfy.GraphInvalid as e:
            from service.comfy import PromptRejected
            raise PromptRejected('rejected', detail={'error': str(e), 'node_errors': e.node_errors})
        self.prompts_sent += 1
        with self.fake._lock:
            job = self.fake._queue.pop(0)
            self.fake._running = job
        try:
            self.fake._execute(*job)
        finally:
            self.fake._running = None
        return pid

    def history(self, prompt_id, timeout=None):
        return self.fake.history.get(prompt_id)

    def object_info(self, timeout=None):
        return self.fake.object_info()

    def system_stats(self, timeout=None):
        return {'devices': [{'name': f'Test graphics card {self.fake.gpu + 1}', 'vram_free': 30 << 30}]}

    def interrupt(self, timeout=None):
        self.fake.interrupt()

    def queue(self, timeout=None):
        return self.fake.queue_state()


class NoFeed:
    """No progress feed (the runner then polls the engine's history, as when the feed is down)."""
    connected, generation, disconnects, last_message = False, 0, 0, {'type': 'none'}

    def __init__(self, *a):
        pass

    def start(self):
        pass

    def stop(self):
        pass

    def subscribe(self, *a):
        pass

    def unsubscribe(self, *a):
        pass


def node_pack_copy(dest):
    """The app's node packs with MANIFEST-banded.json made for this tree (tools/make_banded_manifest.manifest on the copy), so
    the runner's pack check passes whatever this worktree changed in claude_banded; the classic MANIFEST.json is copied."""
    from tools import make_banded_manifest
    np_dir = Path(dest) / 'node_pack'
    shutil.copytree(ROOT / 'node_pack', np_dir, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    with mock.patch.object(make_banded_manifest, 'ROOT', Path(dest)):
        m = make_banded_manifest.manifest()
    (np_dir / 'MANIFEST-banded.json').write_text(json.dumps(m, indent=2) + '\n', encoding='utf8')
    return np_dir / 'claude_creative'


class InProcessService:
    """The service's parts in this process (service/app.py _run without the server, the lifecycle and Runner.start)."""

    def __init__(self, state, ram_gb, dev=True):
        self.state = Path(state)
        cfg = config.load(self.state, fake_engine=True)
        config.ensure_state_dirs(cfg)
        cfg.default_output_dir = self.state / 'out'
        cfg.default_output_dir.mkdir(exist_ok=True)
        pack = self.state.parent / 'app'
        cfg.node_pack_dir = (pack / 'node_pack' / 'claude_creative' if (pack / 'node_pack').is_dir()
                             else node_pack_copy(pack))
        self.cfg = cfg
        self.log = Logger(cfg.logs_dir, cfg.jobs_dir, echo=False)
        self.settings = Settings(self.state / 'settings.json', cfg.default_output_dir, self.log, total_ram_gb=ram_gb)
        self.store = JobStore(cfg.jobs_dir, self.log)
        self.store.load_all()
        self.media = MediaLibrary(cfg.media_dir, self.log)
        env = {'CU_FAKE_GPUS': '1', 'CU_SPLIT_TEST': '0'}
        with mock.patch.dict(os.environ, env), mock.patch.object(build_channel, 'CHANNEL', 'dev' if dev else 'release'):
            for k in ('CU_FAKE_PROCESS', 'CU_TEST_CRASH', 'CU_FAKE_VRAM_FREE', 'CU_FAST_TEST', 'CU_DEADLINE_SECONDS'):
                os.environ.pop(k, None)
            self.runner = Runner(cfg, self.settings, self.store, self.media, self.log)
        self.worker = workers.Worker(0, cfg, self.settings, self.log, 'fake')
        self.runner.workers = {0: self.worker}
        self.runner.recover()

    def add(self, path):
        items, rejected = self.media.add_paths([str(path)])
        assert not rejected, rejected
        return items[0]['id']

    def job(self, mids, settings, force=None):
        body = {'client_request_id': uuid.uuid4().hex, 'media_ids': list(mids), 'settings': settings,
                'output_dir': str(self.cfg.default_output_dir)}
        if force:
            body['dev_force_engine'] = force
        with mock.patch.object(build_channel, 'CHANNEL', 'dev'):
            job, _ = self.runner.create_job(body)
        return job

    def run_all(self, timeout=600):
        """Dispatch until nothing is queued, each image in its own item thread as the scheduler runs it; returns the
        exceptions that ended an item thread without a record (the engine dying)."""
        died = []

        def hook(args):
            died.append(args.exc_value)
        old = threading.excepthook
        threading.excepthook = hook
        try:
            end = time.monotonic() + timeout
            while time.monotonic() < end:
                self.runner._dispatch()
                threads = list(self.runner.threads.values())
                for t in threads:
                    t.join(max(1.0, end - time.monotonic()))
                if not threads and self.store.next_queued(exclude=set()) is None:
                    break
                if died:
                    break
        finally:
            threading.excepthook = old
        return died

    def item(self, jid):
        return self.store.get(jid)['items'][0]

    def events(self):
        out = []
        for p in sorted(self.cfg.logs_dir.glob('app-*.jsonl')):
            out += [json.loads(x) for x in p.read_text(encoding='utf8').splitlines() if x.strip()]
        return out

    def prompts(self):
        return [json.loads(p.read_text(encoding='utf8')) for p in sorted(self.cfg.workers_dir.rglob('fake-prompts/*.json'))]

    def renders(self):
        p = self.cfg.workers_dir / 'gpu0' / 'fake-renders.jsonl'
        return [json.loads(x) for x in p.read_text(encoding='utf8').splitlines() if x.strip()] if p.is_file() else []

    def route(self, method, mid, **q):
        """A viewer route of service/api.py, called in this process: (status, body, headers)."""
        h = object.__new__(api._Handler)
        h.app = SimpleNamespace(runner=self.runner, media=self.media, store=self.store, log=self.log, settings=self.settings)
        got = {}

        def send(status, body, ctype='application/json; charset=utf-8', extra=None):
            got.update(status=status, body=body, ctype=ctype, headers=dict(extra or {}))
        h._send = send
        try:
            getattr(api._Handler, method)(h, {k: str(v) for k, v in q.items()}, mid)
        except api.ApiError as e:
            return e.status, str(e), {}
        return got['status'], got['body'], got['headers']


def strip_input(d, name, w, h, alpha=False, seed=1):
    d = Path(d)
    d.mkdir(parents=True, exist_ok=True)
    a = gradient(w, h, seed)
    if alpha:
        al = np.tile(np.linspace(0, 255, w).astype(np.uint8), (h, 1))
        Image.fromarray(np.dstack([a, al])).save(d / name)
    else:
        Image.fromarray(a).save(d / name)
    return d / name


PROTECT_ALL = {'protect': ['people', 'furniture', 'vehicles', 'windows', 'architecture']}     # every category: protect and release terms


class Base(unittest.TestCase):
    ram_gb = RAM_WS

    def setUp(self):
        self.td = Path(tempfile.mkdtemp(prefix='cu-integ-'))
        self.patches = [mock.patch.dict(banded_plan.BANDED_PROVEN_MP, PROVEN), mock.patch.object(Image, 'MAX_IMAGE_PIXELS', None)]
        for p in self.patches:
            p.start()
        InProcessFake.die_at = None
        self.engine = [mock.patch.object(fake_comfy, 'FakeComfy', InProcessFake),
                       mock.patch.object(workers, 'ComfyClient', InProcessClient),
                       mock.patch.object(workers, 'WsListener', NoFeed)]
        for p in self.engine:
            p.start()

    def tearDown(self):
        for p in reversed(self.engine + self.patches):
            p.stop()
        InProcessFake.registry.clear()
        shutil.rmtree(self.td, ignore_errors=True)

    def service(self, state='state', ram_gb=None):
        return InProcessService(self.td / state, self.ram_gb if ram_gb is None else ram_gb)

    def done(self, svc, jid):
        it = svc.item(jid)
        self.assertEqual(it['state'], 'done', (it.get('message'), it.get('error')))
        return it

    def classes(self, svc):
        out = set()
        for g in svc.prompts():
            out |= {n['class_type'] for n in g.values()}
        return out


class Every32000PxPass(Base):
    """8x of 4000 x 64 on the workstation class: 32,000 x 512 px in three passes, each with the split finish."""

    def test_every_pass_every_node_and_the_viewer(self):
        svc = self.service()
        mid = svc.add(strip_input(self.td / 'in', 'wide.png', 4000, 64))
        job = svc.job([mid], dict(PROTECT_ALL, scale=8))
        plan = job['items'][0]['plan']
        self.assertEqual(plan.get('engine'), 'banded', plan)
        self.assertEqual(plan['output_size'], [32000, 512])
        self.assertEqual(len(plan['stages']), 3)
        self.assertTrue(all(s['split_finish'] for s in plan['stages']))
        self.assertFalse(plan['banded']['forced'])
        self.assertEqual(svc.run_all(), [])
        it = self.done(svc, job['id'])
        with Image.open(it['output']) as im:
            self.assertEqual((im.size, im.mode), ((32000, 512), 'RGB'))
            out = np.asarray(im)
        side = json.loads(Path(it['sidecar']).read_text(encoding='utf8'))
        self.assertEqual(side['engine']['executor'], 'large-image')
        self.assertEqual(side['engine']['finish'], 'bxf-1')
        self.assertIsNone(side['engine']['halo_fix'])
        self.assertEqual(side['output']['writer'], 'streamed')
        # every pass ran: part A and part B of each, A then B
        parts = [(r['prefix'].rsplit('_', 2)[-2:] if r['prefix'].endswith('_a') else [r['prefix'][-2:], 'b'])
                 for r in svc.renders()]
        self.assertEqual(parts, [['s0', 'a'], ['s0', 'b'], ['s1', 'a'], ['s1', 'b'], ['s2', 'a'], ['s2', 'b']])
        self.assertTrue(all(r['status'] == 'success' for r in svc.renders()))
        ev = [e['event'] for e in svc.events()]
        self.assertEqual(ev.count('banded_split_restart'), 3)
        self.assertEqual(ev.count('banded_split_commit_unmeasured'), 3)       # no shared Job in this process
        self.assertEqual(svc.worker.banded_missing, [])                       # the whitelisted pack's classes are all there
        # every node of the merged NODE_SPECS was in a graph the engine accepted, and no whole-image node
        cls = self.classes(svc)
        self.assertTrue(set(graph_banded.NODE_SPECS) <= cls, sorted(set(graph_banded.NODE_SPECS) - cls))
        self.assertFalse(cls & {'LoadImage', 'ImageScale', 'SaveImage', 'ClaudeV4Finish', 'VAEDecodeTiled', 'VAEEncodeTiled',
                                'SAM3_Detect', 'ClaudeSAM3DetectLean', 'ImageBlur', 'ClaudeCannyTiled'})
        # the viewer: a lossless region of the kept plane equals the file's pixels; the proxy and the sized copy
        q = dict(kind='result', job=job['id'], item=it['id'])
        code, png, hdr = svc.route('r_region', it['media_id'], x=31000, y=100, w=1000, h=300, **q)
        self.assertEqual(code, 200, png[:300])
        with Image.open(io.BytesIO(png)) as im:
            np.testing.assert_array_equal(np.asarray(im), out[100:400, 31000:32000])
        self.assertEqual(hdr.get('X-Image-Size'), '32000,512')
        code, body, hdr = svc.route('r_region', it['media_id'], x=28000, y=0, w=4000, h=512, **q)     # the last 4,096 px
        self.assertEqual(code, 200)
        with Image.open(io.BytesIO(body)) as im:
            np.testing.assert_array_equal(np.asarray(im), out[:, 28000:32000])
        code, body, hdr = svc.route('r_region', it['media_id'], x=0, y=0, w=32000, h=512, **q)
        self.assertEqual(code, 400)                                            # a region is at most 4,096 px a side
        for kind in ('r_proxy', 'r_thumb'):
            code, jpg, hdr = svc.route(kind, it['media_id'], **q)
            self.assertEqual(code, 200, kind)
            with Image.open(io.BytesIO(jpg)) as im:
                self.assertLessEqual(max(im.size), 4096)
        code, jpg, hdr = svc.route('r_proxy', it['media_id'], w=2000, h=100, **q)
        self.assertEqual(code, 200, jpg[:300])
        self.assertEqual(hdr.get('X-Image-Size'), '32000,512')
        self.assertFalse((svc.cfg.work_dir / job['id']).exists())             # the work folder is gone after the result


class Every28000PxPassAndWriter(Base):
    """8x of 3500 x 64 with transparency on a 64 GB PC's class: 28,000 x 512 px in three one-prompt passes (no split), through
    every writer; and TIFF 16 as BigTIFF with the switch moved down test-locally."""
    ram_gb = RAM_PC

    def run_fmt(self, svc, src, fmt):
        mid = svc.add(src)
        job = svc.job([mid], {'scale': 8, 'output_format': fmt})
        plan = job['items'][0]['plan']
        self.assertEqual(plan.get('engine'), 'banded', plan)
        self.assertEqual(plan['banded']['machine_class'], 'pc64')
        self.assertFalse(any(s['split_finish'] for s in plan['stages']))
        self.assertEqual(svc.run_all(), [])
        return job, self.done(svc, job['id'])

    def test_every_writer_on_an_rgba_input(self):
        svc = self.service()
        src = strip_input(self.td / 'in', 'alpha.png', 3500, 64, alpha=True)
        W, H = 28000, 512
        want_a = np.asarray(Image.open(src).getchannel('A').resize((W, H), Image.LANCZOS))
        for fmt in ('png8', 'png16', 'tiff16', 'jpeg'):
            with self.subTest(fmt=fmt):
                job, it = self.run_fmt(svc, src, fmt)
                if fmt == 'png8':
                    with Image.open(it['output']) as im:
                        self.assertEqual((im.size, im.mode), ((W, H), 'RGBA'))
                        np.testing.assert_array_equal(np.asarray(im)[..., 3], want_a)   # banded alpha = Pillow's whole LANCZOS
                elif fmt == 'png16':
                    arr, depth, _ = read_png16(it['output'])
                    self.assertEqual((arr.shape, depth), ((H, W, 4), 16))
                elif fmt == 'tiff16':
                    self.assertEqual(Path(it['output']).read_bytes()[:4], b'II*\x00')
                    arr = read_tiff16(it['output'])[0]
                    self.assertEqual(arr.shape[:2], (H, W))
                else:
                    with Image.open(it['output']) as im:
                        self.assertEqual((im.size, im.mode), ((W, H), 'RGB'))
                side = json.loads(Path(it['sidecar']).read_text(encoding='utf8'))
                self.assertEqual(side['output']['writer'], 'streamed')
                # RGBA viewer copies: the region carries the alpha
                code, png, hdr = svc.route('r_region', it['media_id'], x=27000, y=10, w=500, h=200, kind='result',
                                           job=job['id'], item=it['id'])
                self.assertEqual(code, 200, png[:200])
                with Image.open(io.BytesIO(png)) as im:
                    self.assertEqual(im.mode, 'RGBA' if fmt != 'jpeg' else im.mode)
        cls = self.classes(svc)
        self.assertNotIn('CUPlaneCheckpoint', cls)                             # no split on this class for these sizes
        self.assertIn('CUFinishBanded', cls)

    def test_tiff16_as_bigtiff(self):
        svc = self.service()
        src = strip_input(self.td / 'in', 'wide.png', 3500, 64)
        with mock.patch.object(plane_io, 'BIGTIFF_ABOVE', 1 << 20):
            job, it = self.run_fmt(svc, src, 'tiff16')
        data = Path(it['output']).read_bytes()
        self.assertEqual(data[:4], b'II+\x00')                                # BigTIFF (version 43)
        with Image.open(it['output']) as im:
            self.assertEqual(im.size, (28000, 512))


class ResumeFromTheCheckpoint(Base):
    """The engine dies in prompt B of a pass; a new Runner on the same state (as after a restart) goes on from that pass's
    saved first part: prompt A of that pass runs once in all, and the result is whole."""

    def test_each_pass(self):
        for k in (0, 1, 2):
            with self.subTest(stage=k):
                state = f'state-{k}'
                svc = self.service(state)
                mid = svc.add(strip_input(self.td / f'in{k}', 'wide.png', 4000, 64))
                job = svc.job([mid], {'scale': 8})
                InProcessFake.die_at = (k, 'B')
                died = svc.run_all()
                self.assertEqual(len(died), 1)
                self.assertIsInstance(died[0], EngineDied)
                self.assertIn(svc.item(job['id'])['state'], ('running', 'preparing'))
                ck = svc.cfg.work_dir / job['id'] / 'i001' / 'planes' / f's{k}' / 'checkpoint.json'
                self.assertTrue(ck.is_file())
                svc2 = self.service(state)                                     # the restart
                self.assertEqual(svc2.item(job['id'])['state'], 'queued')
                self.assertEqual(svc2.item(job['id'])['stage_index'], k)
                self.assertEqual(svc2.run_all(), [])
                it = self.done(svc2, job['id'])
                with Image.open(it['output']) as im:
                    self.assertEqual(im.size, (32000, 512))
                a_runs = [r for r in svc2.renders() if r['prefix'].endswith(f'_s{k}_a')]
                self.assertEqual(len(a_runs), 1)                               # prompt A of pass k ran once in all
                self.assertIn('banded_checkpoint_resume', [e['event'] for e in svc2.events()])


class TheForceSwitch(Base):
    def test_a_classic_plan_through_the_large_image_engine(self):
        from engine import planner
        svc = self.service()
        mid = svc.add(strip_input(self.td / 'in', 'small.png', 640, 480))
        classic = planner.plan(640, 480, 2, ram_cap_gb=float(svc.settings.get()['ram_cap_gb']))
        job = svc.job([mid], {'scale': 2}, force='banded')
        plan = job['items'][0]['plan']
        self.assertEqual(plan['engine'], 'banded')
        self.assertTrue(plan['banded']['forced'])
        keys = ('factor', 'supersample', 'padded_size', 'render_size', 'output_size')
        self.assertEqual([[list(s[k]) if isinstance(s[k], (list, tuple)) else s[k] for k in keys] for s in plan['stages']],
                         [[list(getattr(s, k)) if isinstance(getattr(s, k), (list, tuple)) else getattr(s, k) for k in keys]
                          for s in classic.stages])
        self.assertEqual(svc.run_all(), [])
        it = self.done(svc, job['id'])
        with Image.open(it['output']) as im:
            self.assertEqual(im.size, (1280, 960))
        side = json.loads(Path(it['sidecar']).read_text(encoding='utf8'))
        self.assertTrue(side['engine']['forced_for_comparison'])


@unittest.skipUnless(FULL_AREA, 'the full-area stage needs about 60 GB of free work disk: CU_INTEG_FULL_AREA=1')
class FullAreaStage(Base):
    """8x of 3500 x 2188 on the workstation class: its last pass is a full-area 14,000 x 8,752 -> 28,000 x 17,504 px stage
    (490 MP, over the 300 MP whole finish, so banded_plan.BXF_AVAILABLE is set test-locally as the plan's tier needs)."""

    def test_the_last_pass_at_full_area(self):
        with mock.patch.object(banded_plan, 'BXF_AVAILABLE', True, create=True):
            svc = self.service()
            mid = svc.add(strip_input(self.td / 'in', 'full.png', 3500, 2188))
            job = svc.job([mid], {'scale': 8})
            plan = job['items'][0]['plan']
            self.assertEqual(plan['output_size'], [28000, 17504])
            self.assertEqual(plan['stages'][-1]['input_size'], [14000, 8752])
            self.assertEqual(svc.run_all(timeout=3600), [])
        it = self.done(svc, job['id'])
        with Image.open(it['output']) as im:
            self.assertEqual(im.size, (28000, 17504))
            self.assertEqual(np.asarray(im.crop((27000, 17000, 28000, 17504))).shape, (504, 1000, 3))
        q = dict(kind='result', job=job['id'], item=it['id'])
        code, png, hdr = svc.route('r_region', it['media_id'], x=27000, y=17000, w=1000, h=504, **q)
        self.assertEqual(code, 200)
        with Image.open(io.BytesIO(png)) as a, Image.open(it['output']) as b:
            np.testing.assert_array_equal(np.asarray(a), np.asarray(b.crop((27000, 17000, 28000, 17504))))
        code, jpg, hdr = svc.route('r_proxy', it['media_id'], **q)
        self.assertEqual(code, 200)


if __name__ == '__main__':
    unittest.main()
