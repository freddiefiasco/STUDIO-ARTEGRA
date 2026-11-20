"""tools/proof/harness.py: both executors' graphs for every reference pair of design 7.1, the classic's equal to the identity
record, the dump spec of each, and the harness's own worker command against the product's. Sizes only; no image, no worker."""
import json
import tempfile
import types
import unittest
from pathlib import Path

import numpy as np

from engine import graph_banded, graph_v5t
from tools.proof import harness, phases

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = json.loads((ROOT / 'tests' / 'fixtures' / 'g0_identity_5_0_1.json').read_text(encoding='utf8'))
CAP = 59.0                      # the 64 GB node class, where R1 runs


class PairGraphs(unittest.TestCase):
    def test_every_7_1_pair_builds_on_both_executors(self):
        self.assertEqual(set(harness.PAIRS), {'k4', 'k3', 'k2', 'k1.5', 'chain4x'})
        for name, stages in harness.PAIRS.items():
            plan = harness.forced_plan(stages, CAP)
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
        self.assertEqual(ks, {'k4': [4.0], 'k3': [3.0], 'k2': [2.0], 'k1.5': [1.5], 'chain4x': [4.0, 4.0]})

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
                    self.assertEqual(harness.graph_sha(g), base[key], f'{name} {key}')
                    found.append(key)
                else:
                    absent.append(key)
                    # outside the identity grid: the same builder, called directly, with the record's own naming
                    pk = harness.stage_params(st)
                    d, _ = graph_v5t.build_product(f'cu_j_i_s{st.index}.png', *st.padded, pk, f'cu_j_i_s{st.index}',
                                                   f=st.f, s=st.s)
                    self.assertEqual(harness.graph_sha(g), harness.graph_sha(d))
        self.assertEqual(sorted(set(found)), ['1280x1600/f2/s2/k0', '2560x3200/f2/s1/k1', '2560x3200/f2/s2/k1',
                                              '2800x3504/f2/s1.5/k0', '3500x2188/f2/s2/k0'])
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
            i = prod.index('--whitelist-custom-nodes')
            self.assertEqual(mine[:i + 1], prod[:i + 1])
            self.assertEqual(mine[i + 1:], ['claude_creative', 'claude_banded', 'cu_proof'])
            prod_yaml = workers.extra_model_paths_yaml(cfg)
            mine_yaml = harness.worker_yaml(cfg, d / 'app' / 'tools' / 'proof')
            self.assertTrue(mine_yaml.startswith(prod_yaml))
            tail = mine_yaml[len(prod_yaml):]
            self.assertIn('custom_nodes: comfy_nodes', tail)
            self.assertEqual(tail.count('custom_nodes'), 1)
            self.assertEqual(extra['whitelist_added'], ['claude_banded', 'cu_proof'])


class Runner(unittest.TestCase):
    def test_waits_for_history_and_reports_errors(self):
        class Fake:
            def __init__(self, status):
                self.calls, self.status = 0, status

            def prompt(self, graph, client_id, prompt_id=None):
                self.pid = prompt_id
                return {'prompt_id': prompt_id}

            def history(self, prompt_id):
                self.calls += 1
                if self.calls < 3:
                    return {}
                return {prompt_id: {'status': {'status_str': self.status, 'completed': self.status == 'success',
                                               'messages': [['execution_error', {'exception_message': 'boom'}]]},
                                    'outputs': {}}}
        ok = Fake('success')
        h = harness.run_prompt(ok, {'1': {'class_type': 'X', 'inputs': {}}}, 'p1', poll_s=0, timeout_s=5)
        self.assertEqual(ok.pid, 'p1')
        self.assertEqual(h['status']['status_str'], 'success')
        with self.assertRaises(harness.RunFailed) as e:
            harness.run_prompt(Fake('error'), {}, 'p2', poll_s=0, timeout_s=5)
        self.assertIn('boom', str(e.exception))


if __name__ == '__main__':
    unittest.main()
