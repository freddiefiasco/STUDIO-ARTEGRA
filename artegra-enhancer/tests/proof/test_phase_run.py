"""tools/proof/phase_run.py end to end on a stand-in engine (no ComfyUI, no port, no GPU): the stand-in writes what the
instrumentation writes, for both executors, in each executor's own storage; the run finds 0 per phase, then locates an
injected difference at its first phase, reports a missing intermediate, and a chain feeds each executor's own next stage."""
import json
import tempfile
import time
import unittest
import zlib
from pathlib import Path

import numpy as np

from engine import planes
from tests.proof import comfy_stub
from tools.proof import harness, phase_run

T = planes.U8_TO_F32
SMALL = (harness.Stage(300, 200, 2, 2, 0),)
CHAIN = (harness.Stage(300, 200, 2, 2, 0), harness.Stage(600, 400, 2, 1, 1))


def u8(role, shape, salt=0):
    rng = np.random.default_rng(zlib.crc32(f'{role}/{salt}'.encode()))
    return rng.integers(0, 256, shape).astype(np.uint8)


class FakeEngine:
    """Writes, for each prompt, the dumps and events the instrumentation would, from the spec, and the BES's contract
    stage output plane; `change` alters BES roles (a set: one bit of the first value; a dict: role -> function of the u8
    array), `drop` leaves roles out, `no_output` leaves out the BES's stage output plane. Its client is service.comfy.ComfyClient with only
    the transport stubbed (tests/proof/comfy_stub), so run_pair's prompt path runs the real client."""

    def __init__(self, executor, run_dir, change=None, drop=None, fail=None, no_output=False):
        self.ex, self.change, self.drop, self.fail, self.no_output = executor, change or {}, drop or (), fail, no_output
        self.dir = Path(run_dir) / 'worker'
        self.input_dir, self.dump_root = self.dir / 'input', self.dir / 'proof'
        self.input_dir.mkdir(parents=True, exist_ok=True)
        self.dump_root.mkdir(parents=True, exist_ok=True)
        self.client = comfy_stub.StubComfy(self.run_graph, polls_until_done=0)
        self.log = ''

    def run_graph(self, graph, prompt_id):
        """What the worker does with one accepted prompt; returns ComfyUI's status record for its history entry."""
        d = self.dump_root / prompt_id
        if self.fail == self.ex:
            return comfy_stub.error_status(prompt_id, 'CUDA out of memory', node_id='12', node_type='KSampler')
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
        if self.ex == 'bes' and 'stage_output' in spec['files'] and not self.no_output:
            out = Path(spec['files']['stage_output']['path'])
            planes.from_array(out, self.make('stage_output', 'save8_crop', (pw * 2, ph * 2, ow, oh), st['index'])[:oh, :ow])
            if any(v['class_type'] == 'ClaudeSpotTilesBanded' for v in graph.values()):
                self.log += '[claude_banded] wsum_min=0.5 evals=30 windows=4\n'
        with open(d / 'events.jsonl', 'w', encoding='utf8') as f:
            for e in evs:
                f.write(json.dumps(e) + '\n')
        return comfy_stub.success_status(prompt_id)

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
            if isinstance(self.change, dict):
                u = self.change[role](u)
            else:
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
    def run_it(self, stages=SMALL, cap=59.0, pair=None, **fake):
        with tempfile.TemporaryDirectory() as d:
            src = u8('source', (stages[0].h, stages[0].w, 3))
            k = [stages[0].index]
            rep = phase_run.run_pair('t', stages, cap, src, d, lambda ex, rd: FakeEngine(ex, rd, **fake), Path('.'),
                                     gate_fn=fake_gate, oracle_fn=fake_oracle_for(k), **(pair or {}))
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

    # --- the finish rule (design 7.2, 7.3) -------------------------------------------------------------------------------

    def lines(self, stages=SMALL, cap=59.0):
        return phase_run.boundary_lines(harness.forced_plan(stages, cap).stages[0])

    def test_one_changed_value_in_the_bxf_finish_is_tier_1_against_the_oracle(self):
        rows, cols = self.lines()
        self.assertTrue(rows and cols)
        self.assertNotIn(0, rows)                    # the changed value (row 0, column 0) is off every boundary
        self.assertNotIn(0, cols)
        rep = self.run_it(change={'stage_output'}, pair={'mode': 'bxf', 'floor_F': 5})
        s = rep['stages'][0]
        self.assertTrue(rep['pass'], json.dumps(s, indent=1)[:3000])
        self.assertEqual((s['bes_finish_tier']['tier'], s['bes_finish_tier']['checks']['count']), (1, 1))
        self.assertTrue(s['bes_finish_tier']['F_registered'])
        self.assertEqual(s['oracle_vs_classic']['count'], 0)
        self.assertEqual(s['bes_stage_output_vs_classic']['count'], 1)
        self.assertTrue(s['before_finish_zero'])
        self.assertEqual(s['rule']['mode'], 'bxf')
        self.assertIn('tier 1 with the registered floor F = 5', s['rule']['finish'])
        self.assertEqual(s['boundaries'], {'rows': len(rows), 'cols': len(cols)})

    def test_without_a_floor_the_bxf_finish_must_be_tier_0(self):
        rep = self.run_it(change={'stage_output'}, pair={'mode': 'bxf'})
        s = rep['stages'][0]
        self.assertFalse(rep['pass'])
        self.assertFalse(s['finish_pass'])
        self.assertIsNone(s['bes_finish_tier']['tier'])
        self.assertIn('count', s['bes_finish_tier']['fails'])
        self.assertIn('tier 0 (no floor F is registered', s['rule']['finish'])
        same = self.run_it(pair={'mode': 'bxf'})
        self.assertTrue(same['pass'])
        self.assertEqual(same['stages'][0]['bes_finish_tier']['tier'], 0)

    def test_a_step_along_a_boundary_row_fails_structure(self):
        rows, _ = self.lines()
        r = rows[len(rows) // 2]
        off = next(y for y in range(5, 400) if y not in rows and y - 1 not in rows and y + 1 not in rows)

        def step(row):
            def f(u):
                u[row, ::2, 0] ^= 1                 # one level on every other pixel: no 8-connected group over 1 px
                return u
            return f
        F = 10_000
        bad = self.run_it(change={'stage_output': step(r)}, pair={'mode': 'bxf', 'floor_F': F})
        t = bad['stages'][0]['bes_finish_tier']
        self.assertFalse(bad['pass'])
        self.assertEqual(t['fails'], ['structure'], t)
        self.assertIn(r, t['checks']['boundary_rows_over'])
        ok = self.run_it(change={'stage_output': step(off)}, pair={'mode': 'bxf', 'floor_F': F})
        self.assertTrue(ok['pass'], ok['stages'][0]['bes_finish_tier'])
        self.assertEqual(ok['stages'][0]['bes_finish_tier']['tier'], 1)

    def test_bxf_still_needs_every_earlier_phase_at_zero(self):
        rep = self.run_it(change={'raw8'}, pair={'mode': 'bxf', 'floor_F': 5})
        s = rep['stages'][0]
        self.assertFalse(rep['pass'])
        self.assertFalse(s['before_finish_zero'])
        self.assertEqual(s['phase_diff']['first_differing_phase'], 'decodes')

    def test_until_bxf_judges_the_oracle_at_zero_and_reports_the_bes_tier(self):
        rep = self.run_it(change={'stage_output'}, pair={'floor_F': 5})
        s = rep['stages'][0]
        self.assertTrue(rep['pass'])                              # the oracle on the BES planes equals the classic
        self.assertEqual(s['rule']['mode'], 'until_bxf')
        self.assertEqual(s['bes_finish_tier']['tier'], 1)         # the BES's own output against the oracle, reported
        self.assertEqual(s['bes_stage_output_vs_classic']['count'], 1)

    def test_a_bes_run_without_its_stage_output_fails_in_both_modes(self):
        for mode in ('until_bxf', 'bxf'):
            rep = self.run_it(no_output=True, pair={'mode': mode, 'floor_F': 5})
            s = rep['stages'][0]
            self.assertFalse(rep['pass'], mode)
            self.assertFalse(s['finish_pass'], mode)
            self.assertIn('stage_output', s['missing']['bes'])

    def test_an_unknown_mode_is_refused(self):
        with self.assertRaises(ValueError):
            self.run_it(pair={'mode': 'bxf-1h'})

    def test_boundary_lines_are_the_stage_s_own(self):
        plan = harness.forced_plan(harness.PAIRS['chain4x'], 59.0)
        r0, c0 = phase_run.boundary_lines(plan.stages[0])
        ow, oh = plan.stages[0].output_size
        self.assertTrue(r0 and max(r0) < oh and max(c0) < ow)
        from tools.proof import seams
        whole = seams.positions(plan.stages[:1], ('classic', 'bes'))
        self.assertEqual(r0, sorted({v for vs in whole['rows'].values() for v in vs}))

    def test_an_execution_error_is_a_failed_stage_not_a_timeout(self):
        t = time.monotonic()
        rep = self.run_it(fail='bes')
        self.assertLess(time.monotonic() - t, 60)
        self.assertFalse(rep['pass'])
        b = rep['runs']['bes']['stages'][0]
        self.assertEqual(b['status'], 'failed')
        self.assertIn('CUDA out of memory', b['error'])
        self.assertEqual(rep['runs']['classic']['stages'][0]['status'], 'success')
        self.assertEqual(rep['stages'][0]['error'], 'a run of this stage did not finish')

    def test_a_chain_feeds_each_executors_own_next_stage(self):
        rep = self.run_it(stages=CHAIN)
        self.assertEqual(len(rep['stages']), 2)
        self.assertTrue(rep['pass'], json.dumps(rep['stages'], indent=1)[:2000])
        c = rep['runs']['classic']['stages']
        b = rep['runs']['bes']['stages']
        self.assertEqual(c[0]['stage_output_sha256'], b[0]['stage_output_sha256'])
        self.assertEqual(c[0]['stage_output_entry']['size'], [600, 400])


if __name__ == '__main__':
    unittest.main()
