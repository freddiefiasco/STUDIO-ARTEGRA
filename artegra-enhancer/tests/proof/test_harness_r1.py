"""R1's harness fixes (build wave 3, package proof; the first GPU development runs integ-dev-1 and integ-dev-2):
- phase_run.ComfyEngine makes every base folder the product's worker makes (service/workers.Worker._start), custom_nodes and
  cache included: ComfyUI's prestartup lists <base>/custom_nodes and a worker without it exits at once (integ-dev-1);
- phase_run sends every prompt under a canonical UUID prompt id, which the runtime ComfyUI requires (integ-dev-2: 400
  invalid_prompt_id for '<pair>-<executor>-s<k>-<hex8>'), keeps the readable run id in the graph and the record, and keys the
  instrumentation's dump folder by the prompt id. The transport stub refuses a non-UUID id as ComfyUI does, so a harness
  that relied on any other id fails here (as it failed on the node). No ComfyUI, no port, no GPU."""
import json
import re
import tempfile
import types
import unittest
import uuid
from pathlib import Path
from unittest import mock

from tests.proof import comfy_stub
from tests.proof.test_phase_run import SMALL, CHAIN, FakeEngine, fake_gate, fake_oracle_for, u8
from tools.proof import harness, phase_run

APP = Path(__file__).resolve().parents[2]


def canonical(v):
    return comfy_stub.valid_job_id(v)


class Folders(unittest.TestCase):
    def test_the_harness_makes_every_folder_the_product_worker_makes(self):
        src = (APP / 'service' / 'workers.py').read_text(encoding='utf8')
        m = re.search(r"for d in \(([^)]*)\):\s*\n\s*\(self\.dir / d\)\.mkdir", src)
        self.assertIsNotNone(m, 'service/workers.Worker._start no longer makes its folders in one loop')
        product = {x.strip().strip("'\"") for x in m.group(1).split(',') if x.strip()}
        self.assertTrue({'custom_nodes', 'cache'} <= product, product)
        self.assertTrue(product <= set(phase_run.WORKER_DIRS), sorted(product - set(phase_run.WORKER_DIRS)))
        self.assertIn('proof', phase_run.WORKER_DIRS)

    def test_a_worker_that_needs_custom_nodes_at_start_starts(self):
        """A stand-in process that, like ComfyUI's prestartup, exits at once when <base>/custom_nodes is missing: the
        harness's engine starts it (the folder exists before the process), and so do cache and the dump root."""
        seen = {}

        class Proc:
            def __init__(self, cmd, cwd=None, env=None, log_path=None, memory_limit_bytes=None):
                base = Path(cwd)
                seen.update({d: (base / d).is_dir() for d in ('custom_nodes', 'cache', 'input', 'output', 'proof')})
                self.code = None if (base / 'custom_nodes').is_dir() else 1
                self.pid, self.job = 4242, None

            def poll_root(self):
                return self.code

            def close(self):
                return {'all_owned_processes_terminated': True}

            def limits(self):
                return {}

        class Client:
            def __init__(self, port):
                pass

            def system_stats(self):
                if seen.get('custom_nodes') is not True:
                    raise ConnectionRefusedError('the worker exited')
                return {'system': {}}

        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(harness, 'worker_yaml', lambda cfg, proof_dir: ''), \
                mock.patch.object(harness, 'worker_command', lambda *a, **k: (['python', '--reserve-vram', '1'], {})), \
                mock.patch('service.windows_job.WindowsJobProcess', Proc), mock.patch('service.comfy.ComfyClient', Client):
            e = phase_run.ComfyEngine(types.SimpleNamespace(), APP, Path(d) / 'run', 'GPU-stub', 1, 8.0, ready_timeout_s=5)
            self.assertIsNotNone(e.ready_at)
            self.assertEqual(e.output_dir, Path(d) / 'run' / 'worker' / 'output')
            e.stop()
        self.assertEqual(seen, {'custom_nodes': True, 'cache': True, 'input': True, 'output': True, 'proof': True})


class PromptIds(unittest.TestCase):
    def run_pair(self, stages=SMALL, cap=59.0, **pair):
        engines = []

        def launcher(ex, rd):
            e = FakeEngine(ex, rd)
            self.assertTrue(e.client.strict_ids)          # the stand-in's transport refuses what ComfyUI refuses
            engines.append(e)
            return e
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__('shutil').rmtree(d, ignore_errors=True))
        src = u8('source', (stages[0].h, stages[0].w, 3))
        rep = phase_run.run_pair('k4', stages, cap, src, d, launcher, Path('.'), gate_fn=fake_gate,
                                 oracle_fn=fake_oracle_for([stages[0].index]), **pair)
        return phase_run.strip_for_json(rep), engines

    def test_every_prompt_goes_under_a_canonical_uuid_and_the_pair_runs(self):
        rep, engines = self.run_pair()
        self.assertTrue(rep['pass'], json.dumps(rep['stages'], indent=1)[:2000])
        self.assertEqual([e.client.refused for e in engines], [[], []])
        for ex in ('classic', 'bes'):
            st = rep['runs'][ex]['stages'][0]
            self.assertTrue(canonical(st['prompt_id']), st['prompt_id'])
            self.assertTrue(st['run_id'].startswith(f'k4-{ex}-s0-'), st['run_id'])
            self.assertEqual(st['parts'][0]['prompt_id'], st['prompt_id'])
        prompt_ids = {e.ex: list(e.client.entries) for e in engines}
        for e in engines:
            for pid in e.client.entries:
                self.assertTrue((e.dump_root / pid / 'spec.json').is_file(), pid)     # the dump folder is the prompt id's
                self.assertTrue((e.dump_root / pid / 'events.jsonl').is_file(), pid)
        self.assertNotEqual(prompt_ids['classic'], prompt_ids['bes'])

    def test_the_readable_run_id_stays_the_graphs_run_id(self):
        rep, engines = self.run_pair()
        bes = next(e for e in engines if e.ex == 'bes')
        st = rep['runs']['bes']['stages'][0]
        run_ids = {v['inputs'].get('run_id') for g in bes.prompts for v in g.values() if 'run_id' in v.get('inputs', {})}
        self.assertEqual(run_ids, {st['run_id']})
        self.assertFalse(any(canonical(r) for r in run_ids))

    def test_a_chain_and_a_split_stage_send_uuids_on_every_worker(self):
        rep, engines = self.run_pair(CHAIN)
        self.assertTrue(rep['pass'], json.dumps(rep['stages'], indent=1)[:2000])
        rep2, engines2 = self.run_pair(SMALL, 122.2)
        for e in engines + engines2:
            self.assertEqual(e.client.refused, [])
            self.assertTrue(e.client.entries and all(canonical(p) for p in e.client.entries))
        split = rep2['runs']['bes']['stages'][0]
        if split.get('split_finish'):
            self.assertEqual(sorted(split['prompt_id']), ['A', 'B'])
            self.assertTrue(all(canonical(v) for v in split['prompt_id'].values()))

    def test_a_refused_prompt_is_a_failed_stage_not_a_crash(self):
        """A prompt ComfyUI refuses (any 400, here the old readable id) is the stage's failure, recorded with its reason."""
        orig = phase_run.new_prompt_id
        with mock.patch.object(phase_run, 'new_prompt_id', lambda: 'k4-classic-s0-' + orig()[:8]):
            rep, engines = self.run_pair()
        self.assertFalse(rep.get('pass'))
        st = rep['runs']['classic']['stages'][0]
        self.assertEqual(st['status'], 'failed')
        self.assertIn('PromptRejected', st['error'])
        self.assertIn('invalid_prompt_id', st['error'])

    def test_the_stub_matches_comfyuis_validator(self):
        for v, ok in ((str(uuid.uuid4()), True), ('k4-bes-s0A-1a2b3c4d', False), (str(uuid.uuid4()).upper(), False),
                      (uuid.uuid4().hex, False), (None, False), (7, False)):
            self.assertEqual(comfy_stub.valid_job_id(v), ok, v)


if __name__ == '__main__':
    unittest.main()
