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

    def __init__(self, executor, run_dir, change=None, drop=None, fail=None, no_output=False, threads=24, peak_gb=3.0,
                 stop_record=None, one_wsum_line=False):
        self.ex, self.change, self.drop, self.fail, self.no_output = executor, change or {}, drop or (), fail, no_output
        self.threads, self.peak_gb, self.stop_record, self.stopped = threads, peak_gb, stop_record, False
        self.one_wsum_line = one_wsum_line
        self.run_dir, self.prompts, self.inputs_seen = Path(run_dir), [], []
        self.dir = Path(run_dir) / 'worker'
        self.input_dir, self.dump_root = self.dir / 'input', self.dir / 'proof'
        self.input_dir.mkdir(parents=True, exist_ok=True)
        self.dump_root.mkdir(parents=True, exist_ok=True)
        self.client = comfy_stub.StubComfy(self.run_graph, polls_until_done=0)
        self.log = ''

    def run_graph(self, graph, prompt_id):
        """What the worker does with one accepted prompt; returns ComfyUI's status record for its history entry."""
        d = self.dump_root / prompt_id
        assert not self.stopped, 'a prompt reached a stopped worker'
        self.prompts.append(graph)
        self.inputs_seen.append(sorted(p.name for p in self.input_dir.iterdir()))   # the worker's input folder now
        if self.fail == self.ex:
            return comfy_stub.error_status(prompt_id, 'CUDA out of memory', node_id='12', node_type='KSampler')
        spec = json.loads((d / 'spec.json').read_text(encoding='utf8'))
        st = spec['stage']
        ow, oh = st['output']
        pw, ph = st['padded']
        evs = [{'type': 'env', 'torch_threads': self.threads, 'interop_threads': 24, 'omp_mkl': {}, 't': 0}]
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
                            'output': o, 'kind': 'plane', 'path': str(path), 'host_bytes': int(arr.nbytes),
                            'commit_delta_bytes': None})
        for s in sorted(set(spec['cn']['nodes'].values())):
            for i in range(2):
                evs.append({'type': 'cn', 'role': f'cn/{s}/0', 'call': i, 'keys': ['output/0'],
                            'sha256': [f'{s}{i}{st["index"]}'], 'dtypes': ['torch.float16'], 'shapes': [[1]], 'files': None})
                hint = f'h{s}{i}{st["index"]}' + ('x' if 'cn_hint' in self.change and self.ex == 'bes' else '')
                evs.append({'type': 'cn', 'role': f'cn_hint/{s}/0', 'call': i, 'keys': ['cond_hint'], 'sha256': [hint],
                            'dtypes': ['torch.float16'], 'shapes': [[1, 3, 8, 8]], 'files': None,
                            'layout': [{'device': 'cuda:0', 'contiguous': self.ex == 'classic', 'channels_last': False,
                                        'stride': [1]}]})
        if self.ex == 'bes' and 'stage_output' in spec['files'] and not self.no_output:
            out = Path(spec['files']['stage_output']['path'])
            planes.from_array(out, self.make('stage_output', 'save8_crop', (pw * 2, ph * 2, ow, oh), st['index'])[:oh, :ow])
        if self.ex == 'bes':                       # one line per banded sampling call (KS1 and KS2), as the node prints
            n = sum(1 for v in graph.values() if v['class_type'] == 'KSampler') - int(self.one_wsum_line)
            self.log += '[claude_banded] wsum_min=0.5 evals=30 windows=4\n' * max(0, n)
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
        return None if self.peak_gb is None else int(self.peak_gb * 2 ** 30)

    def stop(self):
        self.stopped = True
        return self.stop_record


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
    def run_it(self, stages=SMALL, cap=59.0, pair=None, per=None, **fake):
        """per(executor, n) -> FakeEngine keywords for that executor's n-th launch. self.launched: (executor, run dir
        relative to the work folder, engine) per launch, in order."""
        self.launched = []

        def launcher(ex, rd):
            n = sum(1 for e, _, _ in self.launched if e == ex)
            e = FakeEngine(ex, rd, **dict(fake, **((per or (lambda ex, n: {}))(ex, n))))
            self.launched.append((ex, Path(rd).relative_to(d).as_posix(), e))
            return e
        with tempfile.TemporaryDirectory() as d:
            src = u8('source', (stages[0].h, stages[0].w, 3))
            k = [stages[0].index]
            rep = phase_run.run_pair('t', stages, cap, src, d, launcher, Path('.'), gate_fn=fake_gate,
                                     oracle_fn=fake_oracle_for(k), **(pair or {}))
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

    # --- wave 2: wsum lines per sampler, the gate's source, the hint crops, stored sides ---------------------------------

    def test_one_wsum_line_for_two_banded_samplers_fails_the_pair(self):
        rep = self.run_it(one_wsum_line=True)
        w = rep['runs']['bes']['wsum']
        self.assertEqual((w['lines'], w['expected'], w['pass']), (1, 2, False))
        self.assertFalse(rep['pass'])

    def test_the_gate_row_says_it_is_union_derived(self):
        rep = self.run_it()
        g = rep['stages'][0]['gate']
        self.assertEqual(g['source'], 'union-derived')
        self.assertIn('adds nothing beyond the union roles', g['note'])
        sam = rep['stages'][0]['phase_diff']['phases'][0]['roles']
        self.assertTrue(rep['stages'][0]['phase_diff']['zero'])
        self.assertIn('gate', sam)

    def test_a_hint_crop_difference_is_the_first_differing_role_of_the_hints_phase(self):
        rep = self.run_it(change={'cn_hint'})
        s = rep['stages'][0]
        self.assertFalse(s['pass'])
        self.assertEqual(s['phase_diff']['first_differing_phase'], 'hints')
        hints = next(p for p in s['phase_diff']['phases'] if p['phase'] == 'hints')['roles']
        self.assertGreater(hints['cn_hint/ks1/0']['count'], 0)
        self.assertEqual(hints['cn/ks1/0']['count'], 0)                       # the ControlNet outputs agree
        # the stand-in's crops differ in contiguity between executors (the classic's contiguous, the BES's not): listed per
        # call, never counted (the values are what the ControlNet sees)
        self.assertEqual(hints['cn_hint/ks1/0']['layout_differs'], [0, 1])
        self.assertEqual(hints['cn_hint/ks1/0']['count'], 2)
        self.assertEqual(rep['stages'][0]['missing'], {'classic': [], 'bes': []})

    def test_sides_run_apart_and_compared_later_equal_one_pair_run(self):
        with tempfile.TemporaryDirectory() as d:
            launched = []

            def launcher(ex, rd):
                e = FakeEngine(ex, rd)
                launched.append((ex, e))
                return e
            src = u8('source', (SMALL[0].h, SMALL[0].w, 3))
            c = phase_run.run_side('t', SMALL, 59.0, src, d, launcher, 'classic')
            self.assertTrue((Path(d) / 'classic' / 'side.json').is_file())
            b = phase_run.run_side('t', SMALL, 59.0, src, d, launcher, 'bes')
            c2 = phase_run.load_side(Path(d) / 'classic' / 'side.json')
            rep = phase_run.compare_runs('t', SMALL, 59.0, c2, b, d, Path('.'), gate_fn=fake_gate,
                                         oracle_fn=fake_oracle_for([0]))
            self.assertTrue(rep['pass'], json.dumps(rep['stages'], indent=1)[:2000])
            self.assertEqual([e for e, _ in launched], ['classic', 'bes'])
            wrong = phase_run.compare_runs('t', SMALL, 122.2, c2, b, d, Path('.'), gate_fn=fake_gate,
                                           oracle_fn=fake_oracle_for([0]))
            self.assertIn('not of this pair, cap and plan', wrong['error'])
            self.assertEqual(c['seed'], None)

    def test_a_classic_seed_b_side_is_built_with_its_seed(self):
        with tempfile.TemporaryDirectory() as d:
            src = u8('source', (SMALL[0].h, SMALL[0].w, 3))
            engines = []

            def launcher(ex, rd):
                engines.append(FakeEngine(ex, rd))
                return engines[-1]
            side = phase_run.run_side('t', SMALL, 59.0, src, d, launcher, 'classic', seed=20261120)
            self.assertEqual(side['seed'], 20261120)
            g = engines[0].prompts[0]
            seeds = {v['inputs'].get('seed') for v in g.values() if v['class_type'] in ('KSampler', 'ClaudeSpotTiles')}
            self.assertEqual(seeds, {20261120})
            want = harness.classic_graph(SMALL[0], 'base', phase_run.base_params(20261120))[0]
            self.assertEqual(side['run']['stages'][0]['graph_sha256'], harness.graph_sha(want))
            self.assertNotEqual(side['run']['stages'][0]['graph_sha256'],
                                harness.graph_sha(harness.classic_graph(SMALL[0])[0]))

    # --- the split finish (L3r) at the workstation's cap ---------------------------------------------------------------

    def test_a_split_stage_runs_part_b_on_a_fresh_worker(self):
        plan = harness.forced_plan(SMALL, 122.2)
        self.assertTrue(plan.stages[0].split_finish)
        rep = self.run_it(cap=122.2)
        self.assertTrue(rep['pass'], json.dumps(rep['stages'], indent=1)[:3000])
        self.assertEqual([(e, r) for e, r, _ in self.launched], [('classic', 'classic'), ('bes', 'bes'),
                                                                 ('bes', 'bes/restart1')])
        bes = [e for x, _, e in self.launched if x == 'bes']
        self.assertTrue(all(e.stopped for _, _, e in self.launched))
        self.assertEqual([len(e.prompts) for e in bes], [1, 1])                       # A on the first, B on the fresh one
        a, b = bes[0].prompts[0], bes[1].prompts[0]
        self.assertIn('CUPlaneCheckpoint', {v['class_type'] for v in a.values()})
        self.assertEqual({v['class_type'] for v in b.values()}, {'CUPlaneInput', 'CUFinishBanded'})   # no loader in B
        runs = rep['runs']['bes']
        self.assertEqual([w['segments'] for w in runs['workers']], [[[0, 'A']], [[0, 'B']]])
        st = runs['stages'][0]
        self.assertTrue(st['split_finish'])
        self.assertEqual([p['part'] for p in st['parts']], ['A', 'B'])
        self.assertEqual(sorted(st['prompt_id']), ['A', 'B'])
        self.assertEqual(st['stage_output_entry']['part'], 'B')
        self.assertTrue(runs['wsum']['pass'])                                          # its lines are in A's worker log
        self.assertEqual((runs['wsum']['lines'], runs['wsum']['expected']), (2, 2))    # KS1 and KS2 of part A
        self.assertEqual(rep['runs']['classic']['workers'][0]['segments'], [[0, None]])
        self.assertEqual(rep['stages'][0]['phase_diff']['first_differing_phase'], None)

    def test_a_split_chain_restarts_before_the_fresh_pass_and_before_each_part_b(self):
        rep = self.run_it(stages=CHAIN, cap=122.2)
        self.check_split_fresh_chain(rep)

    def check_split_fresh_chain(self, rep):
        """Build wave 4: CHAIN at the workstation's cap splits both stages and its second sets fresh_worker, so the second
        pass restarts before A (the worker that ran part B of the first has run a prompt) and before B."""
        plan = harness.forced_plan(CHAIN, 122.2)
        self.assertEqual([(s.split_finish, s.fresh_worker) for s in plan.stages], [(True, False), (True, True)])   # premise
        self.assertTrue(rep['pass'], json.dumps(rep['stages'], indent=1)[:2000])
        self.assertEqual([w['segments'] for w in rep['runs']['bes']['workers']],
                         [[[0, 'A']], [[0, 'B']], [[1, 'A']], [[1, 'B']]])
        self.assertEqual([r for e, r, _ in self.launched if e == 'bes'],
                         ['bes', 'bes/restart1', 'bes/restart2', 'bes/restart3'])
        self.assertEqual(rep['runs']['bes']['stages'][1]['restart_before'],
                         {'why': 'fresh_worker', 'stopped_worker': 1, 'worker': 2, 'stopped_cleanly': True})
        self.assertNotIn('restart_before', rep['runs']['bes']['stages'][0])
        self.assertTrue(all(e.stopped for _, _, e in self.launched))
        c, b = rep['runs']['classic']['stages'], rep['runs']['bes']['stages']
        self.assertEqual(c[0]['stage_output_sha256'], b[0]['stage_output_sha256'])
        self.assertEqual([w['segments'] for w in rep['runs']['classic']['workers']], [[[0, None], [1, None]]])
        self.assertTrue(rep['memory']['layout']['pass'], rep['memory']['layout'])
        self.assertTrue(rep['memory']['pass'], rep['memory'])

    # --- build wave 4: a fresh engine before a pass whose plan asks for one (contracts.restart) ----------------------------

    def check_two_unsplit_stages_the_second_fresh(self, rep):
        plan = harness.forced_plan(CHAIN, 59.0)
        self.assertEqual([(s.split_finish, s.fresh_worker) for s in plan.stages], [(False, False), (False, True)])  # premise
        self.assertTrue(rep['pass'], json.dumps(rep['stages'], indent=1)[:2000])
        self.assertEqual([(e, r) for e, r, _ in self.launched], [('classic', 'classic'), ('bes', 'bes'),
                                                                 ('bes', 'bes/restart1')])
        bes = [e for x, _, e in self.launched if x == 'bes']
        self.assertEqual([len(e.prompts) for e in bes], [1, 1])                  # one pass on each worker
        self.assertTrue(all(e.stopped for e in bes))
        runs = rep['runs']['bes']
        self.assertEqual([w['segments'] for w in runs['workers']], [[[0, None]], [[1, None]]])
        # each pass's inputs are prepared in its own worker's input folder, before its prompt
        self.assertEqual([e.inputs_seen for e in bes], [[[harness.names(CHAIN[0])[0]]], [[harness.names(CHAIN[1])[0]]]])
        self.assertEqual(runs['stages'][1]['restart_before'],
                         {'why': 'fresh_worker', 'stopped_worker': 0, 'worker': 1, 'stopped_cleanly': True})
        self.assertEqual([w['segments'] for w in rep['runs']['classic']['workers']], [[[0, None], [1, None]]])
        # each worker's Job peak is its own, held to its own pass's bound
        from tools.proof import registration
        marks = registration.plan_marks(plan, 59.0)
        self.assertEqual([w['bound_gb'] for w in rep['memory']['workers']],
                         [marks['stages'][0]['worker_peak_upper_gb'], marks['stages'][1]['worker_peak_upper_gb']])
        self.assertTrue(rep['memory']['layout']['pass'], rep['memory']['layout'])
        self.assertTrue(rep['memory']['pass'], rep['memory'])

    def test_two_unsplit_stages_the_second_fresh_launch_two_bes_workers(self):
        self.check_two_unsplit_stages_the_second_fresh(self.run_it(stages=CHAIN))

    def flagged(self, *flags):
        """harness.forced_plan with fresh_worker set on the stages named (by index), for both of run_pair's plan calls."""
        from unittest import mock
        real = harness.forced_plan

        def plan(*a, **k):
            p = real(*a, **k)
            for s in p.stages:
                if s.index in flags:
                    s.fresh_worker = True
            return p
        return mock.patch.object(harness, 'forced_plan', plan)

    def check_fresh_first_stage(self, rep, n_bes, segments):
        self.assertTrue(rep['pass'], json.dumps(rep['stages'], indent=1)[:2000])
        self.assertEqual([r for e, r, _ in self.launched if e == 'bes'], ['bes'] + [f'bes/restart{i}' for i in
                                                                                   range(1, n_bes)])
        self.assertEqual([w['segments'] for w in rep['runs']['bes']['workers']], segments)
        self.assertNotIn('restart_before', rep['runs']['bes']['stages'][0])
        self.assertTrue(rep['memory']['pass'], rep['memory'])

    def test_a_fresh_first_stage_makes_no_extra_restart(self):
        with self.flagged(0):
            rep = self.run_it()                                          # one stage, flagged: its worker is fresh
            self.assertTrue(harness.forced_plan(SMALL, 59.0).stages[0].fresh_worker)
        self.check_fresh_first_stage(rep, 1, [[[0, None]]])
        with self.flagged(0, 1):
            rep = self.run_it(stages=CHAIN)                              # both flagged: one restart, before the second
        self.check_fresh_first_stage(rep, 2, [[[0, None]], [[1, None]]])
        with self.flagged(0):
            rep = self.run_it(cap=122.2)                                 # a split first stage, flagged: B's restart only
        self.check_fresh_first_stage(rep, 2, [[[0, 'A']], [[0, 'B']]])

    def test_a_worker_that_does_not_stop_before_a_fresh_pass_stops_the_chain(self):
        rep = self.run_it(stages=CHAIN, per=lambda ex, n: {'stop_record': {'all_owned_processes_terminated': False}}
                          if ex == 'bes' else {})
        self.assertFalse(rep['pass'])
        self.assertEqual([r for e, r, _ in self.launched if e == 'bes'], ['bes'])      # no fresh worker started
        st = rep['runs']['bes']['stages']
        self.assertEqual([s['status'] for s in st], ['success', 'failed'])
        self.assertIn('did not stop, so pass 2 was not run in a fresh worker', st[1]['error'])
        self.assertEqual(st[1]['restart_before'], {'why': 'fresh_worker', 'stopped_worker': 0, 'stopped_cleanly': False})
        self.assertEqual(rep['stages'][1]['error'], 'a run of this stage did not finish')
        self.assertFalse(rep['memory']['pass'])                         # the run stopped before the plan's second worker

    def test_a_mutant_that_skips_the_restart_turns_them_red(self):
        """The harness's restart rule taken away (registration.fresh_before False in phase_run only): the chain runs both
        passes on one worker. The checks above fail on it, and so does the memory mark (the plan's layout)."""
        import types as _t
        from unittest import mock
        from tools.proof import registration
        mutant = _t.ModuleType('registration_mutant')
        mutant.__dict__.update({k: getattr(registration, k) for k in dir(registration) if not k.startswith('__')})
        mutant.fresh_before = lambda stage, segments_run: False
        with mock.patch.object(phase_run, 'registration', mutant):
            two = self.run_it(stages=CHAIN)
            self.assertFalse(two['memory']['pass'])
            self.assertIn('the plan\'s layout is [[[0, None]], [[1, None]]]', two['memory']['layout']['why'])
            with self.assertRaises(AssertionError):
                self.check_two_unsplit_stages_the_second_fresh(two)
            split = self.run_it(stages=CHAIN, cap=122.2)
            with self.assertRaises(AssertionError):
                self.check_split_fresh_chain(split)
        self.assertEqual([w['segments'] for w in two['runs']['bes']['workers']], [[[0, None], [1, None]]])

    def test_part_b_is_not_run_when_the_worker_of_part_a_does_not_stop(self):
        rep = self.run_it(cap=122.2, per=lambda ex, n: {'stop_record': {'all_owned_processes_terminated': False}})
        self.assertFalse(rep['pass'])
        self.assertEqual([r for e, r, _ in self.launched if e == 'bes'], ['bes'])      # no fresh worker started
        st = rep['runs']['bes']['stages'][0]
        self.assertEqual(st['status'], 'failed')
        self.assertIn('did not stop', st['error'])
        self.assertEqual(rep['stages'][0]['error'], 'a run of this stage did not finish')

    def test_the_thread_rule_covers_the_fresh_worker_of_part_b(self):
        rep = self.run_it(cap=122.2, per=lambda ex, n: {'threads': 12} if (ex, n) == ('bes', 1) else {})
        s = rep['stages'][0]
        self.assertFalse(rep['pass'])
        self.assertEqual(len(s['threads']), 1)
        self.assertTrue(s['threads'][0].startswith('part B: torch_threads'))

    # --- the memory mark on the harness's own Jobs (design 9.2 R1) -------------------------------------------------------

    def test_the_memory_mark_uses_the_worker_only_bound(self):
        from engine import banded_plan
        from tools.proof import registration
        rep = self.run_it()
        mem = rep['memory']
        self.assertTrue(mem['pass'], mem)
        marks = registration.plan_marks(harness.forced_plan(SMALL, 59.0), 59.0)
        w = mem['workers'][0]
        self.assertEqual(w['bound_gb'], marks['stages'][0]['worker_peak_upper_gb'])
        self.assertAlmostEqual(w['bound_gb'], marks['stages'][0]['peak_upper_gb'] - banded_plan.SERVICE_GB, places=1)
        self.assertEqual(w['job_peak_commit_gb'], 3.0)
        self.assertGreater(w['instrument_host_gb_max'], 0)          # the instrumentation's own bytes, beside the peak
        self.assertIn('no service process', mem['rule'])

    def test_the_memory_mark_of_a_split_stage_bounds_each_worker_by_its_part(self):
        from tools.proof import registration
        rep = self.run_it(cap=122.2)
        marks = registration.plan_marks(harness.forced_plan(SMALL, 122.2), 122.2)
        parts = marks['stages'][0]['parts']
        self.assertEqual([w['bound_gb'] for w in rep['memory']['workers']],
                         [parts['A']['worker_peak_upper_gb'], parts['B']['worker_peak_upper_gb']])
        self.assertTrue(rep['memory']['pass'])

    def test_a_peak_over_the_bound_or_unmeasured_fails_the_memory_mark_only(self):
        over = self.run_it(per=lambda ex, n: {'peak_gb': 40.0} if ex == 'bes' else {})
        self.assertTrue(over['pass'])                                     # the exactness marks are separate
        self.assertFalse(over['memory']['pass'])
        self.assertEqual(over['memory']['workers'][0]['fails'], ['peak over the bound'])
        none = self.run_it(per=lambda ex, n: {'peak_gb': None} if ex == 'bes' else {})
        self.assertFalse(none['memory']['pass'])
        self.assertIsNone(none['runs']['bes']['job_peak_commit_gb'])

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
