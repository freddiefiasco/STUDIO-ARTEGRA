"""tools/proof/comfy_nodes/cu_proof: the instrumentation dumps what the spec names, losslessly, and changes nothing it runs.

A stand-in for ComfyUI's execution.get_output_data and comfy.controlnet.ControlNet (the hook points) runs small graphs of
stand-in nodes with and without the instrumentation; their outputs must be the same objects with the same bits, the graph
untouched, and the dumps bit-equal to the values. Needs torch (the worker interpreter):
    "<Python 3.11 with torch>" -B -m unittest tests.proof.test_instrument      (from the artegra-enhancer folder)"""
import asyncio
import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

import numpy as np

HAVE_TORCH = importlib.util.find_spec('torch') is not None
ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / 'tools' / 'proof' / 'comfy_nodes' / 'cu_proof' / '__init__.py'


def load_pack():
    name = 'cu_proof_under_test'
    sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location(name, PACK, submodule_search_locations=[str(PACK.parent)])
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def fake_comfy():
    """execution.get_output_data and comfy.controlnet.ControlNet as the hook points look in ComfyUI 0.42."""
    ex = types.ModuleType('fake_execution')

    async def get_output_data(prompt_id, unique_id, obj, input_data_all, execution_block_cb=None, pre_execute_cb=None,
                              v3_data=None):
        r = getattr(obj, obj.FUNCTION)(**{k: v[0] for k, v in input_data_all.items()})
        return [[x] for x in r], {}, False, False
    ex.get_output_data = get_output_data
    cn = types.ModuleType('fake_controlnet')

    class ControlNet:
        def __init__(self, k):
            self.k = k

        def get_control(self, x_noisy, t, cond, batched_number, transformer_options):
            return {'output': [x_noisy * self.k, None], 'middle': [x_noisy + self.k]}
    cn.ControlNet = ControlNet
    return ex, cn


@unittest.skipUnless(HAVE_TORCH, 'needs torch (the worker interpreter)')
class Instrumentation(unittest.TestCase):
    def setUp(self):
        import torch
        self.torch = torch
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.ex, self.cn = fake_comfy()
        self.pack = load_pack()
        self.addCleanup(self._tmp.cleanup)

    def nodes(self):
        torch, cnmod = self.torch, self.cn

        class Img:
            FUNCTION = 'run'

            def run(self, seed):
                g = torch.Generator().manual_seed(seed)
                return (torch.rand((1, 20, 30, 3), generator=g),)

        class Mask:
            FUNCTION = 'run'

            def run(self, image):
                return ((image[..., 0] > 0.5).float(),)

        class Lat:
            FUNCTION = 'run'

            def run(self, image):
                controls = [cnmod.ControlNet(2.0), cnmod.ControlNet(3.0)]
                for i in range(5):
                    for c in controls:
                        c.get_control(image[:, :4, :4, 0] + i, None, None, 1, {})
                return ({'samples': image.permute(0, 3, 1, 2)[:, :3].contiguous()},)
        return Img(), Mask(), Lat()

    def run_graph(self, prompt_id):
        img, mask, lat = self.nodes()
        go = self.ex.get_output_data
        out = {}

        async def run():
            out['1'] = await go(prompt_id, '1', img, {'seed': [7]})
            out['2'] = await go(prompt_id, '2', mask, {'image': [out['1'][0][0][0]]})
            out['3'] = await go(prompt_id, '3', lat, {'image': [out['1'][0][0][0]]})
        asyncio.run(run())
        return out

    def spec(self, prompt_id, full_calls=2, calls=3):
        d = self.root / prompt_id
        d.mkdir(parents=True)
        spec = {'executor': 'classic', 'roles': {'1': [[0, 'canvas', 'bitwise']], '2': [[0, 'union/protect', 'bitwise']],
                                                 '3': [[0, 'latent/ks1', 'bitwise']]},
                'files': {}, 'cn': {'nodes': {'3': 'ks1'}, 'calls': calls, 'full_calls': full_calls},
                'phase_of_node': {'1': 'x4', '2': 'sam', '3': 'vae_samplers'}}
        (d / 'spec.json').write_text(json.dumps(spec), encoding='utf8')
        return spec

    def test_outputs_are_unchanged_objects_and_bits(self):
        plain = self.run_graph('p0')
        self.assertTrue(self.pack.install(self.ex, self.cn, root=self.root))
        self.spec('p1')
        hooked = self.run_graph('p1')
        for nid in plain:
            a, b = plain[nid][0][0][0], hooked[nid][0][0][0]
            a = a['samples'] if isinstance(a, dict) else a
            b = b['samples'] if isinstance(b, dict) else b
            self.assertTrue(self.torch.equal(a, b), nid)
            self.assertEqual(a.dtype, b.dtype)

    def test_dumps_are_bit_equal_and_found_by_role(self):
        sys.path.insert(0, str(ROOT))
        from engine import planes
        from tools.proof import harness_io
        self.pack.install(self.ex, self.cn, root=self.root)
        self.spec('p2')
        out = self.run_graph('p2')
        man = harness_io.collect(self.root / 'p2')
        self.assertEqual(man['errors'], [])
        canvas = out['1'][0][0][0][0].numpy()
        got = planes.validate(man['roles']['canvas']['path']).read_rows(0, 20)
        self.assertTrue(np.array_equal(got.view(np.uint32), canvas.view(np.uint32)))
        m = planes.validate(man['roles']['union/protect']['path'])
        self.assertEqual(m.shape, (20, 30, 1))
        lat = out['3'][0][0][0]['samples'][0].numpy()            # [C, h, w] stored as [C*h, w, 1]
        p = planes.validate(man['roles']['latent/ks1']['path'])
        self.assertEqual(p.shape, (3 * 20, 30, 1))
        self.assertTrue(np.array_equal(p.read_rows(0, 60)[..., 0], lat.reshape(60, 30)))
        self.assertEqual(json.loads(json.dumps(p.header['inputs']))['tensor_shape'], [1, 3, 20, 30])
        self.assertEqual([e['node'] for e in man['timeline']], ['1', '2', '3'])
        self.assertEqual(man['env'][0]['torch_threads'], self.torch.get_num_threads())
        self.assertIn('omp_mkl', man['env'][0])

    def test_a_role_on_two_cache_twins_is_dumped_once_by_the_node_that_ran(self):
        """W1c (26 Nov 2026): at k 2 the canvas and the init are two identical ImageScale nodes; ComfyUI runs one and
        serves the other from its cache. harness.dump_spec puts both roles on both twins; the node that runs dumps each
        role once, and a later twin (were it to run) dumps nothing again: no 'dumped twice', nothing missing."""
        sys.path.insert(0, str(ROOT))
        from tools.proof import harness_io
        self.pack.install(self.ex, self.cn, root=self.root)
        d = self.root / 'p6'
        d.mkdir(parents=True)
        spec = {'executor': 'classic', 'roles': {'1': [[0, 'init', 'bitwise'], [0, 'canvas', 'bitwise']],
                                                 '4': [[0, 'canvas', 'bitwise'], [0, 'init', 'bitwise']]},
                'files': {}, 'cn': {}, 'phase_of_node': {'1': 'x4', '4': 'x4'}}
        (d / 'spec.json').write_text(json.dumps(spec), encoding='utf8')
        img, _, _ = self.nodes()
        go = self.ex.get_output_data

        async def run():
            await go('p6', '1', img, {'seed': [7]})
            await go('p6', '4', img, {'seed': [7]})          # the twin, had the cache not served it
        asyncio.run(run())
        man = harness_io.collect(d)
        self.assertEqual(man['errors'], [])
        self.assertEqual(sorted(r for r in man['roles']), ['canvas', 'init'])
        self.assertEqual({man['roles'][r]['node'] for r in ('canvas', 'init')}, {'1'})
        self.assertEqual(harness_io.check_complete(man, spec), [])

    def test_controlnet_calls_recorded_per_sampler_and_instance(self):
        self.pack.install(self.ex, self.cn, root=self.root)
        self.spec('p3', full_calls=2, calls=3)
        self.run_graph('p3')
        sys.path.insert(0, str(ROOT))
        from tools.proof import harness_io
        man = harness_io.collect(self.root / 'p3')
        self.assertEqual(sorted(man['roles']), ['canvas', 'cn/ks1/0', 'cn/ks1/1', 'cn_hint/ks1/0', 'cn_hint/ks1/1',
                                                'latent/ks1', 'union/protect'])
        c0 = man['roles']['cn/ks1/0']
        self.assertEqual(len(c0['calls']), 3)                   # capped at `calls` of the 5 made
        self.assertEqual([bool(c.get('files')) for c in c0['calls']], [True, True, False])
        self.assertEqual(c0['calls'][0]['keys'], ['middle/0', 'output/0', 'output/1'])
        self.assertIsNone(c0['calls'][0]['sha256'][2])           # a None output is recorded as None

    def test_the_hint_crop_of_each_call_is_recorded_by_value_with_its_layout(self):
        torch, cnmod = self.torch, self.cn
        self.pack.install(self.ex, self.cn, root=self.root)
        self.spec('p6', full_calls=1, calls=3)
        base = torch.rand((1, 3, 8, 8), generator=torch.Generator().manual_seed(3))
        crops = []

        class Spot:
            FUNCTION = 'run'

            def run(self, image):
                a, b = cnmod.ControlNet(2.0), cnmod.ControlNet(3.0)
                for i in range(2):
                    h = base[..., i:i + 4, :4].contiguous()
                    a.cond_hint = h                                           # what the spot code sets per window
                    b.cond_hint = h.to(memory_format=torch.channels_last)    # the same values, another layout
                    crops.append(h)
                    a.get_control(image[:, :4, :4, 0], None, None, 1, {})
                    b.get_control(image[:, :4, :4, 0], None, None, 1, {})
                return ({'samples': image.permute(0, 3, 1, 2)[:, :3].contiguous()},)
        img, _, _ = self.nodes()
        go = self.ex.get_output_data

        async def run():
            x = await go('p6', '1', img, {'seed': [7]})
            await go('p6', '3', Spot(), {'image': [x[0][0][0]]})
        asyncio.run(run())
        sys.path.insert(0, str(ROOT))
        import hashlib
        from tools.proof import harness_io, phases
        man = harness_io.collect(self.root / 'p6')
        h0, h1 = man['roles']['cn_hint/ks1/0'], man['roles']['cn_hint/ks1/1']
        want = [hashlib.sha256(c.numpy().tobytes()).hexdigest() for c in crops]
        self.assertEqual([c['sha256'][0] for c in h0['calls']], want)
        self.assertEqual([c['sha256'][0] for c in h1['calls']], want)          # values hashed, not the layout
        self.assertEqual(h0['calls'][0]['shapes'], [[1, 3, 4, 4]])
        self.assertFalse(h0['calls'][0]['layout'][0]['channels_last'])
        self.assertTrue(h1['calls'][0]['layout'][0]['channels_last'])
        self.assertTrue(h0['calls'][0]['files'][0])                            # the first full_calls keep the values
        self.assertIsNone(h0['calls'][1]['files'])
        r = phases.compare_entries(h0, h1, 'cn')
        self.assertEqual(r['count'], 0)
        self.assertEqual(r['layout_differs'], [0, 1])

    def test_its_own_host_buffers_are_recorded(self):
        sys.path.insert(0, str(ROOT))
        from tools.proof import harness_io
        self.pack.install(self.ex, self.cn, root=self.root)
        self.spec('p5', full_calls=1, calls=2)
        self.run_graph('p5')
        evs = harness_io.events(self.root / 'p5')
        dumps = {e['role']: e for e in evs if e['type'] == 'dump'}
        # CPU outputs already contiguous are dumped in place: only the sha256 read buffer of the plane write is new
        self.assertEqual(dumps['canvas']['host_bytes'], 20 * 30 * 3 * 4)
        self.assertEqual(dumps['latent/ks1']['host_bytes'], 3 * 20 * 30 * 4)
        for e in dumps.values():
            if sys.platform == 'win32':
                self.assertIsInstance(e['commit_delta_bytes'], int)
        cns = [e for e in evs if e['type'] == 'cn' and e['role'].startswith('cn/')]
        self.assertTrue(cns)
        self.assertTrue(all(e['host_bytes'] == 0 for e in evs if e['type'] == 'cn' and e['role'].startswith('cn_hint/')))
        self.assertTrue(all(e['host_bytes'] == 4 * 4 * 4 for e in cns), cns[:2])    # the hashed bytes of one 1x4x4 output
        rec = harness_io.collect(self.root / 'p5')['instrument']
        self.assertEqual(rec['host_bytes_max'], 3 * 20 * 30 * 4)
        self.assertEqual(rec['records_without_host_bytes'], 0)
        self.assertEqual(rec['host_bytes_dumps_total'], sum(e['host_bytes'] for e in dumps.values()))

    def test_a_copy_is_counted_and_an_in_place_tensor_is_not(self):
        t = self.torch.arange(24, dtype=self.torch.float32).reshape(2, 3, 4)
        y, n = self.pack._host_copy(t)
        self.assertEqual(n, 0)
        self.assertEqual(y.data_ptr(), t.data_ptr())
        nc = t.permute(2, 1, 0)                                        # not contiguous: a copy of 96 bytes is made
        y, n = self.pack._host_copy(nc)
        self.assertEqual(n, 96)
        self.assertTrue(self.torch.equal(y, nc))
        self.assertIsInstance(self.pack.private_bytes(), int if sys.platform == 'win32' else type(None))

    def test_inert_without_a_spec_or_root(self):
        self.assertFalse(self.pack.install(self.ex, self.cn, root=None))
        self.pack.install(self.ex, self.cn, root=self.root)
        self.run_graph('nospec')
        self.assertFalse((self.root / 'nospec').exists())

    def test_install_twice_wraps_once(self):
        self.pack.install(self.ex, self.cn, root=self.root)
        f = self.ex.get_output_data
        self.pack.install(self.ex, self.cn, root=self.root)
        self.assertIs(self.ex.get_output_data, f)

    def test_the_pack_registers_no_graph_node_that_a_graph_uses(self):
        self.assertEqual(sorted(self.pack.NODE_CLASS_MAPPINGS), ['CUProofInfo'])


if __name__ == '__main__':
    unittest.main()
