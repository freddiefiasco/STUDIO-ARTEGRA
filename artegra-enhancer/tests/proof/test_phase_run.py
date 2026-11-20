"""tools/proof/phase_run.py end to end on a stand-in engine (no ComfyUI, no port, no GPU): the stand-in writes what the
instrumentation writes, for both executors, in each executor's own storage; the run finds 0 per phase, then locates an
injected difference at its first phase, reports a missing intermediate, and a chain feeds each executor's own next stage."""
import json
import tempfile
import unittest
import zlib
from pathlib import Path

import numpy as np

from engine import planes
from tools.proof import harness, phase_run

T = planes.U8_TO_F32
SMALL = (harness.Stage(300, 200, 2, 2, 0),)
CHAIN = (harness.Stage(300, 200, 2, 2, 0), harness.Stage(600, 400, 2, 1, 1))


def u8(role, shape, salt=0):
    rng = np.random.default_rng(zlib.crc32(f'{role}/{salt}'.encode()))
    return rng.integers(0, 256, shape).astype(np.uint8)


class FakeEngine:
    """Writes, for each prompt, the dumps and events the instrumentation would, from the spec, and the BES's contract
    stage output plane; `change` alters one BES role, `drop` leaves one out."""

    def __init__(self, executor, run_dir, change=None, drop=None):
        self.ex, self.change, self.drop = executor, change or {}, drop or ()
        self.dir = Path(run_dir) / 'worker'
        self.input_dir, self.dump_root = self.dir / 'input', self.dir / 'proof'
        self.input_dir.mkdir(parents=True, exist_ok=True)
        self.dump_root.mkdir(parents=True, exist_ok=True)
        self.client = self
        self.log = ''
        self.history_ = {}

    # the ComfyUI client
    def prompt(self, graph, client_id, prompt_id=None):
        d = self.dump_root / prompt_id
        spec = json.loads((d / 'spec.json').read_text(encoding='utf8'))
        st = spec['stage']
        ow, oh = st['output']
        pw, ph = st['padded']
        evs = [{'type': 'env', 'torch_threads': 24, 'interop_threads': 24, 'omp_mkl': {}, 't': 0}]
        for nid in graph:
            evs.append({'type': 'node', 'node': nid, 'class': graph[nid]['class_type'], 'phase': spec['phase_of_node'][nid],
                        't0': 1.0, 't1': 2.0})
        for nid, outs in spec['roles'].items():
            for o, role, form in outs:
                if role in self.drop:
                    continue
                arr = self.make(role, form, (pw * 2, ph * 2, ow, oh), st['index'])
                path = d / 'dumps' / (role.replace('/', '_') + '.plane')
                planes.from_array(path, arr)
                evs.append({'type': 'dump', 'role': role, 'form': form, 'node': nid, 'class': graph[nid]['class_type'],
                            'output': o, 'kind': 'plane', 'path': str(path)})
        for s in sorted(set(spec['cn']['nodes'].values())):
            for i in range(2):
                evs.append({'type': 'cn', 'role': f'cn/{s}/0', 'call': i, 'keys': ['output/0'],
                            'sha256': [f'{s}{i}{st["index"]}'], 'dtypes': ['torch.float16'], 'shapes': [[1]], 'files': None})
        if self.ex == 'bes':
            out = Path(spec['files']['stage_output']['path'])
            planes.from_array(out, self.make('stage_output', 'save8_crop', (pw * 2, ph * 2, ow, oh), st['index'])[:oh, :ow])
            if any(v['class_type'] == 'ClaudeSpotTilesBanded' for v in graph.values()):
                self.log += '[claude_banded] wsum_min=0.5 evals=30 windows=4\n'
        with open(d / 'events.jsonl', 'w', encoding='utf8') as f:
            for e in evs:
                f.write(json.dumps(e) + '\n')
        self.history_[prompt_id] = {'status': {'status_str': 'success', 'completed': True, 'messages': []}}
        return {'prompt_id': prompt_id}

    def history(self, prompt_id):
        return {prompt_id: self.history_[prompt_id]} if prompt_id in self.history_ else {}

    def make(self, role, form, sizes, k):
        W2, H2, ow, oh = sizes
        shape = {'canvas': (H2, W2, 3), 'init': (oh, ow, 3), 'hint': (H2, W2, 3), 'edges': (H2, W2), 'raw8': (oh, ow, 3),
                 'rawlo8': (oh, ow, 3), 'finish': (oh, ow, 3), 'stage_output': (oh, ow, 3)}.get(role.split('/')[0])
        if role.startswith(('sam/', 'union/')):
            shape = (40, 60, 1)
        if role.startswith('latent/'):
            shape = (64, 16, 1)
        u = u8(role, shape, k)
        if role in self.change and self.ex == 'bes':
            u = u.copy()
            u.reshape(-1)[0] ^= 1
        if form in ('bitwise',):
            return T[u]
        if form == 'edges':
            e = u > 127
            return e[..., None].repeat(3, -1).astype(np.float32) if self.ex == 'classic' else (e * 255).astype(np.uint8)[..., None]
        if form in ('u8_table', 'q8', 'save8_crop', 'round8'):
            return T[u] if self.ex == 'classic' else u
        raise AssertionError(form)

    def log_text(self):
        return self.log

    def job_peak(self):
        return 3 << 30

    def stop(self):
        pass


def fake_gate(union, release, dilate, feather, out):
    p = planes.validate(union)
    planes.from_array(out, p.read_rows(0, p.shape[0]))


def fake_oracle_for(stage_index):
    def oracle(job_path, out):
        job = json.loads(Path(job_path).read_text(encoding='utf8'))
        ow, oh = job['inputs']['output_width'], job['inputs']['output_height']
        pw = planes.validate(job['planes']['pre']).shape
        planes.from_array(out, u8('stage_output', (pw[0] * 2, pw[1] * 2, 3), stage_index[0])[:oh, :ow])
        stage_index[0] += 1
    return oracle


class PhaseRun(unittest.TestCase):
    def run_it(self, stages=SMALL, **fake):
        with tempfile.TemporaryDirectory() as d:
            src = u8('source', (stages[0].h, stages[0].w, 3))
            k = [stages[0].index]
            rep = phase_run.run_pair('t', stages, 59.0, src, d, lambda ex, rd: FakeEngine(ex, rd, **fake), Path('.'),
                                     gate_fn=fake_gate, oracle_fn=fake_oracle_for(k))
            return phase_run.strip_for_json(rep)

    def test_zero_per_phase_and_the_records(self):
        rep = self.run_it()
        self.assertTrue(rep['pass'], json.dumps(rep['stages'], indent=1)[:3000])
        s = rep['stages'][0]
        self.assertTrue(s['phase_diff']['zero'])
        self.assertIn('gate', s['phase_diff']['phases'][0]['roles'])
        self.assertEqual(s['threads'], [])
        self.assertTrue(rep['runs']['bes']['wsum']['pass'])
        self.assertEqual(rep['runs']['classic']['job_peak_commit_gb'], 3.0)
        self.assertEqual(rep['runs']['classic']['stages'][0]['graph_sha256'],
                         harness.graph_sha(harness.classic_graph(SMALL[0])[0]))
        self.assertTrue(rep['plan_forced']['banded']['forced'])

    def test_an_injected_difference_is_located_at_its_first_phase(self):
        rep = self.run_it(change={'hint', 'latent/ks2'})
        s = rep['stages'][0]
        self.assertFalse(rep['pass'])
        self.assertEqual(s['phase_diff']['first_differing_phase'], 'hints')

    def test_a_missing_intermediate_fails_the_pair(self):
        rep = self.run_it(drop={'edges'})
        s = rep['stages'][0]
        self.assertFalse(s['pass'])
        self.assertIn('edges', s['missing']['bes'])

    def test_a_chain_feeds_each_executors_own_next_stage(self):
        rep = self.run_it(stages=CHAIN)
        self.assertEqual(len(rep['stages']), 2)
        self.assertTrue(rep['pass'], json.dumps(rep['stages'], indent=1)[:2000])
        c = rep['runs']['classic']['stages']
        b = rep['runs']['bes']['stages']
        self.assertEqual(c[0]['stage_output_sha256'], b[0]['stage_output_sha256'])


if __name__ == '__main__':
    unittest.main()
