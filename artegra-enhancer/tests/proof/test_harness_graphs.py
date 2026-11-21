"""tools/proof/harness.py: both executors' graphs for every reference pair of design 7.1, the classic's equal to the identity
record, the dump spec of each, and the harness's own worker command against the product's. Sizes only; no image, no worker."""
import json
import tempfile
import types
import unittest
from pathlib import Path

import numpy as np

from engine import graph_banded, graph_v5t
from tests.proof import comfy_stub
from tools.proof import harness, phases

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = json.loads((ROOT / 'tests' / 'fixtures' / 'g0_identity_5_0_1.json').read_text(encoding='utf8'))
CAP = 59.0                      # the 64 GB machine class


def stock_view(g):
    return {k: (dict(v, class_type='SAM3_Detect') if v.get('class_type') == 'ClaudeSAM3DetectLean' else v)
            for k, v in g.items()}


class PairGraphs(unittest.TestCase):
    def test_every_7_1_pair_builds_on_both_executors(self):
        self.assertEqual(set(harness.PAIRS), {'k4', 'k3', 'k2', 'k1.5', 'chain4x', 'W1', 'W2'})
        for name, stages in harness.PAIRS.items():
            plan = harness.forced_plan(stages, harness.pair_cap(name))
            self.assertTrue(plan.ok, f'{name}: {plan.reason}')
            self.assertEqual(plan.engine, 'banded')
            self.assertTrue(plan.banded['forced'])
            for st, bst in zip(stages, plan.stages):
                g, info = harness.classic_graph(st)
                b, binfo = harness.bes_graph(st, plan, 'w/planes/s%d' % st.index, 'w/planes/s%d/input.plane' % st.index,
                                             'run1')
                self.assertEqual(info['output'], binfo['output'], name)
                self.assertEqual(tuple(bst.render_size), info['render'], name)
                self.assertIn('ClaudeV4Finish', {v['class_type'] for v in g.values()})
                self.assertIn('CUFinishBanded', {v['class_type'] for v in b.values()})
                self.assertEqual(binfo['stage_output'], (st.w * st.f, st.h * st.f))

    def test_the_k_of_each_pair(self):
        ks = {name: [float(s.f * s.s) for s in st] for name, st in harness.PAIRS.items()}
        self.assertEqual(ks, {'k4': [4.0], 'k3': [3.0], 'k2': [2.0], 'k1.5': [1.5], 'chain4x': [4.0, 4.0], 'W1': [4.0, 2.0],
                              'W2': [4.0, 4.0, 2.0]})

    def test_the_chain_is_the_plan_5_0_1_makes(self):
        from engine import planner
        for cap in (59.0, 122.2):
            p = planner.plan_501(1280, 1600, 4, ram_cap_gb=cap)
            got = [(s.factor, s.supersample, tuple(s.padded_size)) for s in p.stages]
            want = [(float(s.f), float(s.s), s.padded) for s in harness.PAIRS['chain4x']]
            self.assertEqual(got, want, cap)

    def test_classic_graph_hash_equals_the_identity_record(self):
        base = FIXTURE['graphs']['base']
        found, absent = [], []
        for name, stages in harness.PAIRS.items():
            for st in stages:
                g, _ = harness.classic_graph(st)
                key = harness.fixture_key(st)
                if key in base:
                    # 5.0.1's record, with 5.0.2's registered lean SAM (inputs above SAM_STOCK_MAX_MP) read back as stock
                    self.assertEqual(harness.graph_sha(stock_view(g)), base[key], f'{name} {key}')
                    found.append(key)
                else:
                    absent.append(key)
                    # outside the identity grid: the same builder, called directly, with the record's own naming
                    pk = harness.stage_params(st)
                    d, _ = graph_v5t.build_product(f'cu_j_i_s{st.index}.png', *st.padded, pk, f'cu_j_i_s{st.index}',
                                                   f=st.f, s=st.s)
                    self.assertEqual(harness.graph_sha(g), harness.graph_sha(d))
        self.assertEqual(sorted(set(found)), ['1280x1600/f2/s2/k0', '2560x3200/f2/s1/k1', '2560x3200/f2/s2/k1',
                                              '2800x3504/f2/s1.5/k0', '3500x2188/f2/s2/k0', '5120x6400/f2/s1/k2',
                                              '7000x4376/f2/s1/k1'])
        self.assertEqual(absent, ['3008x2000/f1.5/s1/k2'])

    def test_bes_graph_uses_the_forced_plans_constants(self):
        st = harness.PAIRS['k4'][0]
        plan = harness.forced_plan([st], CAP)
        b, info = harness.bes_graph(st, plan, 'w/p', 'w/p/input.plane', 'r')
        fin = [v for v in b.values() if v['class_type'] == 'CUFinishBanded'][0]
        self.assertEqual(fin['inputs']['finish'], plan.banded['finish'])
        self.assertEqual(info['planes']['output'], graph_banded.plane_path('w/p', 'output'))


class DumpSpecs(unittest.TestCase):
    def test_both_executors_name_the_same_roles(self):
        for name, stages in harness.PAIRS.items():
            plan = harness.forced_plan(stages, CAP)
            for st in stages:
                g, info = harness.classic_graph(st)
                b, binfo = harness.bes_graph(st, plan, 'w/p', 'w/p/input.plane', 'r')
                cs, bs = harness.dump_spec(g, info, 'classic', st), harness.dump_spec(b, binfo, 'bes', st)
                croles = {r for v in cs['roles'].values() for _, r, _ in v} | set(cs['files'])
                broles = {r for v in bs['roles'].values() for _, r, _ in v} | set(bs['files'])
                self.assertEqual(croles - phases.OPTIONAL_ROLES, broles, name)
                for role in croles:
                    phases.phase_of(role)
                self.assertIn('sam/protect/0', croles)
                self.assertIn('union/protect', croles)
                for spec, graph in ((cs, g), (bs, b)):
                    self.assertTrue(set(spec['roles']) <= set(graph), name)
                    self.assertEqual(set(spec['phase_of_node']), set(graph), name)
                    self.assertEqual(sorted(spec['cn']['nodes'].values()), ['ks1', 'ks2'])

    def test_canvas_form_follows_k(self):
        for name, want in (('k4', 'bitwise'), ('k3', 'u8_table'), ('k2', 'u8_table'), ('k1.5', 'u8_table')):
            st = harness.PAIRS[name][0]
            g, info = harness.classic_graph(st)
            spec = harness.dump_spec(g, info, 'classic', st)
            forms = {r: f for v in spec['roles'].values() for _, r, f in v}
            self.assertEqual(forms['canvas'], want, name)
            self.assertEqual(forms['init'], 'u8_table')
            self.assertEqual(forms['raw8'], 'q8')
            self.assertEqual(forms['edges'], 'edges')

    def test_the_spec_leaves_the_graph_unchanged(self):
        st = harness.PAIRS['k4'][0]
        g, info = harness.classic_graph(st)
        before = harness.graph_sha(g)
        spec = harness.dump_spec(g, info, 'classic', st)
        json.dumps(spec)
        self.assertEqual(harness.graph_sha(g), before)
        self.assertEqual(harness.graph_sha(harness.prompt_graph(g, spec)), before)


WS_CAP = 122.2                  # the 128 GB machine class: the forced plan splits every stage's finish (L3r)


class SplitFinish(unittest.TestCase):
    """At the workstation's cap the forced plan sets split_finish on every stage, and the BES stage is then two prompts, as
    service/banded_runner.run_stage makes them: A ends in CUPlaneCheckpoint, B reads A's planes and finishes."""

    def test_the_finish_gate_plane_is_named_only_where_the_finish_exposes_one(self):
        st = harness.PAIRS['k4'][0]
        plan = harness.forced_plan([st], CAP)
        b, info = harness.bes_graph(st, plan, 'w/p', 'w/p/input.plane', 'r')
        self.assertNotIn('gate', harness.dump_spec(b, info, 'bes', st)['files'])       # the base finish: none
        info = dict(info, planes=dict(info['planes'], gate='w/p/gate.plane'))
        spec = harness.dump_spec(b, info, 'bes', st)
        self.assertEqual(spec['files']['gate'], {'path': 'w/p/gate.plane', 'form': 'bitwise'})

    def test_every_pair_splits_at_the_workstation_cap_and_none_at_the_node_cap(self):
        for name, stages in harness.PAIRS.items():
            ws, node = harness.forced_plan(stages, WS_CAP), harness.forced_plan(stages, CAP)
            self.assertTrue(ws.ok and node.ok, name)
            self.assertEqual([harness.bes_parts(s) for s in ws.stages], [('A', 'B')] * len(stages), name)
            self.assertEqual([harness.bes_parts(s) for s in node.stages], [(None,)] * len(stages), name)

    def test_parts_a_and_b_name_what_the_one_prompt_names(self):
        for name, stages in harness.PAIRS.items():
            plan = harness.forced_plan(stages, WS_CAP)
            for st in stages:
                one, oinfo = harness.bes_graph(st, plan, 'w/p', 'w/p/input.plane', 'r')
                a, ainfo = harness.bes_graph(st, plan, 'w/p', 'w/p/input.plane', 'ra', part='A')
                b, binfo = harness.bes_graph(st, plan, 'w/p', 'w/p/input.plane', 'rb', part='B')
                ca = {v['class_type'] for v in a.values()}
                cb = {v['class_type'] for v in b.values()}
                self.assertIn('CUPlaneCheckpoint', ca, name)
                self.assertNotIn('CUFinishBanded', ca, name)
                self.assertEqual(cb, {'CUPlaneInput', 'CUFinishBanded'}, name)       # no model loader in B
                so, sa, sb = (harness.dump_spec(g, i, 'bes', st) for g, i in ((one, oinfo), (a, ainfo), (b, binfo)))
                self.assertEqual((sa['part'], sb['part'], so['part']), ('A', 'B', None))
                roles = lambda s: {r for v in s['roles'].values() for _, r, _ in v} | set(s['files'])
                self.assertEqual(roles(sa) | roles(sb), roles(so), name)
                self.assertEqual(roles(sb), {'stage_output'}, name)
                self.assertNotIn('stage_output', roles(sa), name)
                self.assertEqual(sb['files']['stage_output']['path'], so['files']['stage_output']['path'])
                self.assertEqual(sorted(sa['cn']['nodes'].values()), ['ks1', 'ks2'])
                self.assertEqual(sb['cn']['nodes'], {})
                self.assertTrue(set(sa['roles']) <= set(a) and set(sa['phase_of_node']) == set(a))
                self.assertEqual(sb['gate'], so['gate'])
                fin = [v for v in b.values() if v['class_type'] == 'CUFinishBanded'][0]['inputs']
                ref = [v for v in one.values() if v['class_type'] == 'CUFinishBanded'][0]['inputs']
                self.assertEqual({k: v for k, v in fin.items() if not isinstance(v, list) and k != 'run_id'},
                                 {k: v for k, v in ref.items() if not isinstance(v, list) and k != 'run_id'}, name)

    def test_the_parts_are_the_service_s_own_graphs(self):
        from engine import graph_banded as gb
        st = harness.PAIRS['k4'][0]
        plan = harness.forced_plan([st], WS_CAP)
        for part in ('A', 'B'):
            mine, _ = harness.bes_graph(st, plan, 'w/p', 'w/p/input.plane', 'r', part=part)
            svc, _ = gb.build_product('w/p/input.plane', *st.padded, harness.stage_params(st), 'cu_j_i_s0', 'w/p', 'r',
                                      f=st.f, s=st.s, constants=plan.banded, part=part, output_size=st.output)
            self.assertEqual(harness.graph_sha(mine), harness.graph_sha(svc), part)

    def test_a_part_graph_with_the_wrong_ending_is_refused(self):
        st = harness.PAIRS['k4'][0]
        plan = harness.forced_plan([st], WS_CAP)
        a, ainfo = harness.bes_graph(st, plan, 'w/p', 'w/p/input.plane', 'r', part='A')
        b, binfo = harness.bes_graph(st, plan, 'w/p', 'w/p/input.plane', 'r', part='B')
        with self.assertRaises(ValueError):
            harness.dump_spec(a, dict(ainfo, part=None), 'bes', st)           # no finish in A
        with self.assertRaises(ValueError):
            harness.dump_spec(b, dict(binfo, part='C'), 'bes', st)


class Inputs(unittest.TestCase):
    def test_padded_png_and_plane_hold_the_same_pixels(self):
        from PIL import Image
        from engine import planes
        rng = np.random.default_rng(0)
        src = rng.integers(0, 256, (21, 30, 3)).astype(np.uint8)
        st = harness.Stage(30, 21, 2, 1.5, 0)
        with tempfile.TemporaryDirectory() as d:
            png, plane = harness.prepare_inputs(src, st, Path(d) / 'input', Path(d) / 'planes')
            with Image.open(png) as im:
                a = np.asarray(im.convert('RGB'))
            pl = planes.validate(plane)
            p = pl.read_rows(0, pl.shape[0])
            self.assertEqual(a.shape[:2], (st.padded[1], st.padded[0]))
            self.assertTrue(np.array_equal(a, np.asarray(p)))
            self.assertTrue(np.array_equal(a[:21, :30], src))
            self.assertEqual(Path(png).name, 'cu_j_i_s0.png')


class WorkerCommand(unittest.TestCase):
    def test_only_the_whitelist_and_one_custom_nodes_entry_differ_from_the_product(self):
        from service import workers
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            cfg = types.SimpleNamespace(runtime_python=d / 'py' / 'python.exe', comfy_main=d / 'ComfyUI' / 'main.py',
                                        site_packages=d / 'site', models_dir=d / 'models', claude_models_dir=d / 'cm',
                                        node_pack_dir=d / 'app' / 'node_pack' / 'claude_creative', vae_approx_dir=d / 'va' / 'v')
            prod = workers.comfy_command(cfg, d / 'w', 18999, d / 'w' / 'x.yaml')
            mine, extra = harness.worker_command(cfg, d / 'w', 18999, d / 'w' / 'x.yaml', d / 'app' / 'tools' / 'proof')
            added = extra['whitelist_added']
            self.assertTrue(set(added) <= {'claude_banded', 'cu_proof'} and 'cu_proof' in added)
            self.assertEqual([a for a in mine if a not in added], prod)          # nothing else differs
            i = mine.index('--whitelist-custom-nodes')
            wl = mine[i + 1:i + 1 + next((n for n, a in enumerate(mine[i + 1:]) if str(a).startswith('--')),
                                         len(mine) - i - 1)]
            self.assertEqual(set(wl), {'claude_creative', 'claude_banded', 'cu_proof'})
            prod_yaml = workers.extra_model_paths_yaml(cfg)
            mine_yaml = harness.worker_yaml(cfg, d / 'app' / 'tools' / 'proof')
            self.assertTrue(mine_yaml.startswith(prod_yaml))
            tail = mine_yaml[len(prod_yaml):]
            self.assertIn('custom_nodes: comfy_nodes', tail)
            self.assertEqual(tail.count('custom_nodes'), 1)

    def test_a_product_whitelist_that_already_has_the_banded_pack_gets_only_cu_proof(self):
        from unittest import mock
        from service import workers
        prod = ['py', 'main.py', '--disable-all-custom-nodes', '--whitelist-custom-nodes', 'claude_creative', 'claude_banded',
                '--later-flag', 'x']
        with mock.patch.object(workers, 'comfy_command', lambda *a, **k: list(prod)):
            mine, extra = harness.worker_command(None, 'w', 1, 'y', 'p')
        self.assertEqual(extra['whitelist_added'], ['cu_proof'])
        self.assertEqual(mine, prod[:6] + ['cu_proof'] + prod[6:])
        with mock.patch.object(workers, 'comfy_command', lambda *a, **k: ['py', '--whitelist-custom-nodes', 'other']):
            with self.assertRaises(ValueError):
                harness.worker_command(None, 'w', 1, 'y', 'p')


class Runner(unittest.TestCase):
    """run_prompt against the client the engines hold: service.comfy.ComfyClient, whose history() returns the prompt's entry
    (ComfyUI's /history/<id> answer is {<id>: entry}); only the client's transport is stubbed (tests/proof/comfy_stub)."""

    def test_the_real_client_sees_a_prompt_finish(self):
        c = comfy_stub.StubComfy(polls_until_done=2)
        graph = {'1': {'class_type': 'X', 'inputs': {}}}
        h = harness.run_prompt(c, graph, 'p1', poll_s=0, timeout_s=5)
        self.assertEqual(h['status']['status_str'], 'success')
        self.assertEqual(sorted(h), ['meta', 'outputs', 'prompt', 'status'])
        self.assertEqual(c.entries['p1']['prompt'][2], graph)
        self.assertEqual(c.polls['p1'], 3)                                 # {} twice while it runs, then the entry
        self.assertEqual(c.calls[0], ('/prompt', ['client_id', 'prompt', 'prompt_id']))

    def test_the_real_client_reports_an_execution_error(self):
        c = comfy_stub.StubComfy(lambda g, pid: comfy_stub.error_status(pid, 'boom'), polls_until_done=1)
        with self.assertRaises(harness.RunFailed) as e:
            harness.run_prompt(c, {}, 'p2', poll_s=0, timeout_s=5)
        self.assertIn('boom', str(e.exception))
        self.assertIn('KSampler (node 7)', str(e.exception))
        self.assertNotIn('did not finish', str(e.exception))

    def test_an_interrupted_prompt_fails(self):
        def interrupted(g, pid):
            return {'status_str': 'error', 'completed': False,
                    'messages': [['execution_start', {}], ['execution_interrupted', {'prompt_id': pid, 'node_id': '3'}]]}
        with self.assertRaises(harness.RunFailed) as e:
            harness.run_prompt(comfy_stub.StubComfy(interrupted, 0), {}, 'p3', poll_s=0, timeout_s=5)
        self.assertIn('interrupted', str(e.exception))

    def test_a_prompt_that_never_finishes_times_out(self):
        c = comfy_stub.StubComfy(polls_until_done=10 ** 9)
        with self.assertRaises(harness.RunFailed) as e:
            harness.run_prompt(c, {}, 'p4', poll_s=0.01, timeout_s=0.05)
        self.assertIn('did not finish', str(e.exception))

    def test_the_raw_history_answer_is_read_as_a_fallback(self):
        e = {'status': comfy_stub.success_status('p5'), 'outputs': {}}
        self.assertIs(harness.history_entry(e, 'p5'), e)                  # the client's answer: the entry
        self.assertIs(harness.history_entry({'p5': e}, 'p5'), e)          # ComfyUI's raw answer
        self.assertIsNone(harness.history_entry({}, 'p5'))
        self.assertIsNone(harness.history_entry(None, 'p5'))
        self.assertIsNone(harness.history_entry({'other': e}, 'p5'))

        class Raw:
            def prompt(self, graph, client_id, prompt_id=None):
                return prompt_id

            def history(self, prompt_id):
                return {prompt_id: e}
        self.assertIs(harness.run_prompt(Raw(), {}, 'p5', poll_s=0, timeout_s=5), e)


if __name__ == '__main__':
    unittest.main()
