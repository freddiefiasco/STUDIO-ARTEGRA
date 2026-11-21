"""tools/proof/classic.py: the oracle finish on 8-bit planes gives the classic finish chain's bytes on the classic's own float
inputs (so u8 storage of raw8/rawlo8 is exact through the finish), the derived gate is ClaudeProtectGate's, and the 333-row
pow variant is installed and undone. Synthetic images made here. Needs torch and scipy (the worker interpreter):
    "<Python 3.11 with torch>" -B -m unittest tests.proof.test_classic      (from the artegra-enhancer folder)"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

HAVE = all(importlib.util.find_spec(m) is not None for m in ('torch', 'scipy'))
ROOT = Path(__file__).resolve().parents[2]
V4F = {'smooth_lo': 0.2, 'smooth_hi': 0.5, 'protect_dilate': 12, 'protect_feather': 4.0, 'islands': True,
       'chroma_clamp': True, 'quantize_8bit': True, 'keep_blacks': 'render', 'lf': 'hybmin', 'clamp': 'agree5',
       'glow': 'skygaps', 'fin_b0_hi': 2.4, 'island_after_lf': True, 'toe_amount': 0.4, 'toe_scale': 0.06}


def scene(h, w, seed):
    """A synthetic facade: sky gradient, a darker block with windows, mild texture (uint8)."""
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    img = np.stack([0.55 + 0.3 * y / h, 0.65 + 0.25 * y / h, 0.85 + 0.1 * y / h], -1)
    body = y > 0.35 * h + 0.1 * x
    img[body] = (0.45, 0.40, 0.36)
    for x0 in range(w // 8, w - w // 8, w // 4):
        win = body & (np.abs(x - x0) < w // 16) & (np.abs(y - 0.7 * h) < h // 10)
        img[win] = (0.12, 0.14, 0.18)
    img += rng.normal(0, 0.015, img.shape).astype(np.float32)
    return np.clip(img, 0, 1).astype(np.float32)


@unittest.skipUnless(HAVE, 'needs torch and scipy (the worker interpreter)')
class OracleFinish(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch
        from engine import planes
        from tools.proof import classic
        cls.torch, cls.planes, cls.classic = torch, planes, classic
        cls.tmp = tempfile.TemporaryDirectory()
        d = Path(cls.tmp.name)
        h, w = 192, 256
        pre8 = np.clip(255. * scene(h, w, 1), 0, 255).astype(np.uint8)
        cls.creative_f = scene(2 * h, 2 * w, 2)                       # off-table floats, as the classic's area scale gives
        cls.structure_f = scene(2 * h, 2 * w, 3)
        init8 = np.clip(255. * scene(2 * h, 2 * w, 4), 0, 255).astype(np.uint8)
        mask = np.zeros((h, w), np.float32)
        mask[100:150, 40:90] = 1.0
        rel = np.zeros((h, w), np.float32)
        rel[110:120, 50:60] = 1.0
        q8 = lambda x: np.clip(255. * x, 0, 255).astype(np.uint8)
        cls.p = {'creative': planes.from_array(d / 'creative.plane', q8(cls.creative_f)).path,
                 'structure': planes.from_array(d / 'structure.plane', q8(cls.structure_f)).path,
                 'init': planes.from_array(d / 'init.plane', init8).path, 'pre': planes.from_array(d / 'pre.plane', pre8).path,
                 'protect': planes.from_array(d / 'protect.plane', mask[..., None]).path,
                 'release': planes.from_array(d / 'release.plane', rel[..., None]).path}
        cls.p = {k: str(v) for k, v in cls.p.items()}
        cls.raw = dict(pre8=pre8, init8=init8, mask=mask, rel=rel, h=h, w=w)
        cls.dir = d

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_oracle_on_planes_equals_the_classic_chain_on_floats(self):
        torch, cc = self.torch, self.classic.load(ROOT).nodes
        T = self.planes.U8_TO_F32
        r = self.raw
        inputs = dict(V4F, output_width=2 * r['w'] - 6, output_height=2 * r['h'] - 4)
        kw = {k: V4F[k] for k in self.classic.FINISH_KEYS}
        fin = cc.ClaudeV4Finish().run(torch.from_numpy(self.creative_f)[None], torch.from_numpy(self.structure_f)[None],
                                      torch.from_numpy(T[r['init8']])[None], torch.from_numpy(T[r['pre8']])[None],
                                      protect=torch.from_numpy(r['mask'])[None], release=torch.from_numpy(r['rel'])[None],
                                      **kw)[0]
        toe = cc.ClaudeShadowToe().run(fin, 0.4, 0.06)[0]
        want = np.clip(255. * toe[0].numpy(), 0, 255).astype(np.uint8)[:2 * r['h'] - 4, :2 * r['w'] - 6]
        got, fin8, sha = self.classic.oracle_finish(ROOT, self.p, inputs, self.dir / 'out.plane')
        self.assertEqual(got.shape, want.shape)
        self.assertTrue(np.array_equal(got, want))
        self.assertEqual(sha, self.planes.validate(self.dir / 'out.plane').header['sha256'])
        self.assertEqual(fin8.shape, (2 * r['h'], 2 * r['w'], 3))

    def test_derived_gate_is_the_classic_protect_gate(self):
        torch, cc = self.torch, self.classic.load(ROOT).nodes
        r = self.raw
        want = cc.ClaudeProtectGate().run(torch.from_numpy(r['mask'])[None], 12, 4.0,
                                          release=torch.from_numpy(r['rel'])[None])[0][0].numpy()
        got = self.classic.derived_gate(ROOT, self.p['protect'], 12, 4.0, self.p['release'], self.dir / 'gate.plane')
        self.assertTrue(np.array_equal(got.view(np.uint32), want.astype(np.float32).view(np.uint32)))
        g = self.planes.validate(self.dir / 'gate.plane')
        self.assertEqual(g.shape, (r['h'], r['w'], 1))

    def test_chunked_pow_is_installed_and_undone(self):
        torch = self.torch
        x = torch.rand((1, 3, 1000, 17))
        plain = x ** 2.4
        undo = self.classic.chunked_pow(333)
        try:
            self.assertIsNot(torch.Tensor.__pow__, None)
            chunked = x ** 2.4
            self.assertTrue(torch.allclose(chunked, plain, atol=1e-6))
            self.assertEqual(chunked.shape, plain.shape)
        finally:
            undo()
        self.assertTrue(torch.equal(x ** 2.4, plain))

    def test_cli_finish_with_a_thread_count(self):
        job = {'app': str(ROOT), 'planes': self.p, 'inputs': dict(V4F, output_width=2 * self.raw['w'],
                                                                   output_height=2 * self.raw['h'])}
        jp = self.dir / 'job.json'
        jp.write_text(json.dumps(job), encoding='utf8')
        out = subprocess.run([sys.executable, '-B', '-m', 'tools.proof.classic', 'finish', '--job', str(jp), '--out',
                              str(self.dir / 'cli.plane'), '--threads', '3'], cwd=ROOT, capture_output=True, text=True,
                             env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), timeout=600)
        self.assertEqual(out.returncode, 0, out.stderr[-2000:])
        rec = json.loads(out.stdout.strip().splitlines()[-1])
        self.assertEqual(rec['threads'], 3)
        _, _, sha = self.classic.oracle_finish(ROOT, self.p, job['inputs'])
        u8 = self.planes.validate(self.dir / 'cli.plane')
        self.assertEqual(rec['sha256'], u8.header['sha256'])

    def test_the_phase_runs_default_gate_and_oracle_processes(self):
        from tools.proof import phase_run
        out_g = self.dir / 'cpu_gate.plane'
        phase_run.cpu_gate(sys.executable, ROOT, self.p['protect'], self.p['release'], 12, 4.0, out_g)
        want = self.classic.derived_gate(ROOT, self.p['protect'], 12, 4.0, self.p['release'])
        got = self.planes.validate(out_g)
        self.assertTrue(np.array_equal(got.read_rows(0, got.shape[0])[..., 0].view(np.uint32), want.view(np.uint32)))
        job = {'app': str(ROOT), 'planes': self.p, 'inputs': dict(V4F, output_width=2 * self.raw['w'] - 2,
                                                                   output_height=2 * self.raw['h'])}
        jp = self.dir / 'cpu-oracle-job.json'
        jp.write_text(json.dumps(job), encoding='utf8')
        rec = phase_run.cpu_oracle(sys.executable, ROOT, jp, self.dir / 'cpu_oracle.plane')
        u8, _, _ = self.classic.oracle_finish(ROOT, self.p, job['inputs'])
        o = self.planes.validate(self.dir / 'cpu_oracle.plane')
        self.assertEqual(rec['sha256'], o.header['sha256'])
        self.assertTrue(np.array_equal(o.read_rows(0, o.shape[0]), u8))

    def test_noise_floor_runner_runs_four_classic_variants_and_takes_the_largest_pair(self):
        from tools.proof import noise_floor
        job = {'app': str(ROOT), 'planes': self.p, 'inputs': dict(V4F, output_width=2 * self.raw['w'],
                                                                   output_height=2 * self.raw['h'])}
        jp = self.dir / 'nf-job.json'
        jp.write_text(json.dumps(job), encoding='utf8')
        rec = noise_floor.run(jp, self.dir / 'nf')
        self.assertEqual([v['variant'] for v in rec['variants']], ['default', 'threads7', 'threads13', 'pow333'])
        self.assertEqual([v['threads'] for v in rec['variants'][1:3]], [7, 13])
        self.assertEqual(rec['variants'][3]['pow_chunk'], 333)
        self.assertEqual(len(rec['pairs']), 6)
        self.assertEqual(rec['F'], max(p['count'] for p in rec['pairs']))
        self.assertEqual(rec['size_class'], 'le8')


if __name__ == '__main__':
    unittest.main()
