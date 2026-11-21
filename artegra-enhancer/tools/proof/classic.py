"""5.0.1's classic finish and protect gate, run whole on a stage's planes: the oracle of the finish phase (engine design 7.2
"until the BXF exists", and the floor of 7.3) and the derived protect gate of the SAM phase. Needs torch, numpy, scipy and Pillow:
the worker runtime's interpreter, never the app's.

The classic code is the build's own node_pack/claude_creative, read, never patched: v4finish.py is imported from that folder
under a private package name, and the node classes ClaudeV4Finish, ClaudeShadowToe and ClaudeProtectGate (with
shadow_toe_u8 and _mask_union_np) are compiled from that folder's __init__.py as written, into the same private package, so
the classic graph's own finish runs, call for call, without ComfyUI. The planes are read through the classic's own 8-bit
table (engine/planes.U8_TO_F32), which is what LoadImage and the finish's quantize_8bit make of 8-bit data.

    python -B -m tools.proof.classic finish --job <job.json> --out <output.plane> [--threads N] [--pow-chunk 333]
job.json: {"app": <artegra-enhancer folder>, "planes": {"creative", "structure", "init", "pre", "protect"?, "release"?},
           "inputs": the CUFinishBanded inputs of the stage's Large-image graph (the classic finish's values)}"""
import argparse
import ast
import importlib
import importlib.util
import json
import sys
import types
from pathlib import Path

import numpy as np

PKG = 'cu_proof_classic'
NODE_DEFS = ('_mask_union_np', 'ClaudeV4Finish', 'shadow_toe_u8', 'ClaudeShadowToe', 'ClaudeProtectGate')
FINISH_KEYS = ('smooth_lo', 'smooth_hi', 'protect_dilate', 'protect_feather', 'islands', 'chroma_clamp', 'quantize_8bit',
               'keep_blacks', 'clamp', 'lf', 'glow', 'fin_b0_hi', 'island_after_lf')


def load(app):
    """The classic pack's finish code from <app>/node_pack/claude_creative: a namespace with v4finish and the node classes."""
    pack = Path(app) / 'node_pack' / 'claude_creative'
    if PKG in sys.modules and getattr(sys.modules[PKG], '_cu_from', None) != str(pack):
        for k in [k for k in sys.modules if k == PKG or k.startswith(PKG + '.')]:
            del sys.modules[k]
    if PKG not in sys.modules:
        pkg = types.ModuleType(PKG)
        pkg.__path__ = [str(pack)]
        pkg._cu_from = str(pack)
        sys.modules[PKG] = pkg
        v4 = importlib.import_module(PKG + '.v4finish')
        src = (pack / '__init__.py').read_text(encoding='utf8')
        tree = ast.parse(src)
        body = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in NODE_DEFS]
        if sorted(n.name for n in body) != sorted(NODE_DEFS):
            raise RuntimeError(f'the classic pack does not define {NODE_DEFS}')
        mod = types.ModuleType(PKG + '.nodes')
        mod.__package__ = PKG
        import torch
        mod.__dict__.update(torch=torch, json=json, np=np)
        m = ast.Module(body=body, type_ignores=[])
        exec(compile(m, str(pack / '__init__.py'), 'exec'), mod.__dict__)
        sys.modules[PKG + '.nodes'] = mod
        pkg.v4finish, pkg.nodes = v4, mod
    return sys.modules[PKG]


def _plane_u8_image(path):
    """A u8 plane as the classic's IMAGE tensor [1, H, W, 3] (the 8-bit table; what LoadImage gives for 8-bit data)."""
    import torch
    from engine import planes
    p = planes.validate(path)
    a = planes.U8_TO_F32[p.read_rows(0, p.shape[0])[..., :3]]
    return torch.from_numpy(np.ascontiguousarray(a))[None]


def _plane_mask(path):
    import torch
    from engine import planes
    p = planes.validate(path)
    a = p.read_rows(0, p.shape[0])[..., 0].astype(np.float32)
    return torch.from_numpy(np.ascontiguousarray(a))[None]


def finish_inputs(graph):
    """The classic finish's values of a Large-image stage graph: its CUFinishBanded inputs that are not planes."""
    fin = [v for v in graph.values() if v['class_type'] == 'CUFinishBanded']
    if len(fin) != 1:
        raise ValueError('the graph has no single CUFinishBanded')
    return {k: v for k, v in fin[0]['inputs'].items() if not (isinstance(v, list) and len(v) == 2)}


def oracle_finish(app, planes_in, inputs, out_path=None):
    """ClaudeV4Finish -> ClaudeShadowToe -> SaveImage's 8-bit conversion, cropped to (output_width, output_height), on the
    stage's planes. Returns (stage output u8 array, finish output u8 array (pre-toe, rounded as the toe reads it), sha256 of
    the written plane or None)."""
    from engine import planes
    cc = load(app).nodes
    kw = {k: inputs[k] for k in FINISH_KEYS if k in inputs}
    t = {r: _plane_u8_image(planes_in[r]) for r in ('creative', 'structure', 'init', 'pre')}
    if planes_in.get('protect'):
        kw['protect'] = _plane_mask(planes_in['protect'])
        if planes_in.get('release'):
            kw['release'] = _plane_mask(planes_in['release'])
    fin = cc.ClaudeV4Finish().run(t['creative'], t['structure'], t['init'], t['pre'], **kw)[0]
    toe = cc.ClaudeShadowToe().run(fin, float(inputs['toe_amount']), float(inputs['toe_scale']))[0]
    u8 = np.clip(255. * toe[0].cpu().numpy(), 0, 255).astype(np.uint8)
    ow, oh = int(inputs['output_width']), int(inputs['output_height'])
    u8 = np.ascontiguousarray(u8[:oh, :ow])
    fin8 = np.clip(np.round(fin[0].cpu().numpy() * 255), 0, 255).astype(np.uint8)
    sha = None
    if out_path:
        sha = planes.from_array(out_path, u8, producer='oracle finish (ClaudeV4Finish + ClaudeShadowToe + SaveImage)').header['sha256']
    return u8, fin8, sha


def derived_gate(app, union_path, dilate, feather, release_path=None, out_path=None):
    """The protect gate at PRE resolution (ClaudeProtectGate: v4finish.protect_gate before its resize), from a dumped union
    mask plane (and the release union): the SAM phase's 'gate' role, derived the same way for both executors."""
    from engine import planes
    cc = load(app).nodes
    pm = _plane_mask(union_path)
    rm = _plane_mask(release_path) if release_path else None
    g = cc.ClaudeProtectGate().run(pm, int(dilate), float(feather), release=rm)[0][0].numpy().astype(np.float32)
    if out_path:
        planes.from_array(out_path, g[..., None], producer='derived protect gate (ClaudeProtectGate)')
    return g


def chunked_pow(rows=333):
    """Install torch pow (Tensor ** scalar, torch.pow with a scalar exponent) evaluated in `rows`-row chunks along the
    second-last axis: the E9 chunk-boundary variant of design 7.3's noise floor. Returns an undo function."""
    import torch
    orig_t, orig_f = torch.Tensor.__pow__, torch.pow

    def chunk(x, e, f):
        if not isinstance(x, torch.Tensor) or x.dim() < 2 or x.shape[-2] <= rows or isinstance(e, torch.Tensor):
            return f(x, e)
        return torch.cat([f(x[..., i:i + rows, :], e) for i in range(0, x.shape[-2], rows)], dim=-2)

    torch.Tensor.__pow__ = lambda self, e: chunk(self, e, orig_t)
    torch.pow = lambda x, e, *a, **k: chunk(x, e, orig_f) if not a and not k else orig_f(x, e, *a, **k)

    def undo():
        torch.Tensor.__pow__, torch.pow = orig_t, orig_f
    return undo


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    f = sub.add_parser('finish')
    f.add_argument('--job', required=True)
    f.add_argument('--out', required=True)
    f.add_argument('--threads', type=int)
    f.add_argument('--pow-chunk', type=int)
    g = sub.add_parser('gate')
    g.add_argument('--app', required=True)
    g.add_argument('--union', required=True)
    g.add_argument('--release')
    g.add_argument('--dilate', type=int, required=True)
    g.add_argument('--feather', type=float, required=True)
    g.add_argument('--out', required=True)
    a = ap.parse_args(argv)
    import os
    import torch
    if a.cmd == 'gate':
        sys.path.insert(0, str(Path(a.app)))
        derived_gate(a.app, a.union, a.dilate, a.feather, a.release, a.out)
        from engine import planes
        print(json.dumps({'sha256': planes.validate(a.out).header['sha256']}))
        return
    if a.threads:
        torch.set_num_threads(a.threads)
    job = json.loads(Path(a.job).read_text(encoding='utf8'))
    sys.path.insert(0, str(Path(job['app'])))
    if a.pow_chunk:
        chunked_pow(a.pow_chunk)
    _, _, sha = oracle_finish(job['app'], job['planes'], job['inputs'], a.out)
    print(json.dumps({'sha256': sha, 'threads': torch.get_num_threads(), 'pow_chunk': a.pow_chunk,
                      'omp_mkl': {k: v for k, v in sorted(os.environ.items()) if k.upper().startswith(('OMP_', 'MKL_'))}}))


if __name__ == '__main__':
    main()
