"""Halo Reduction (beta), the per-job option of the Large-image finish (node_pack/claude_banded/bxf/dehalo.py; HANDOVER-ENGINE-CORE.md
13a), against round 2's own code: tests/fixtures/halo2_v4finish_08a5fc28.py is a frozen copy of halo2/fix 08a5fc28's
node_pack/claude_creative/v4finish.py (sha256 pinned below), loaded by path, whose v4_finish(..., dehalo='edge3f') is the CPU
replay round 2 measured (HALO-FIX.md section 6.1). Synthetic scenes and sizes only.

- the clamp in row bands (each read with its declared reach) equals the oracle's whole calls, value for value, at f 1.5, 2
  (a first pass) and 4, 6, 8 (a later pass with its anchor), on cards whose rims the clamp removes, with bands that hold no
  edge of geometry, on a card with no edge of geometry (the finish's own output) and on one where nothing is removed (no
  chroma pass), with the power checks (pixels changed, the thin-line guard engaged, the chroma pass ran);
- the banded exact finish with the option on equals the oracle's finish through to_u8, the shadow toe and the stage crop, 0
  differing values, in every option case of gate G2, for a first pass and for a later pass with an anchor, with numpy and
  scipy banded and with every op whole; with the option off it is 5.0.1's finish (the classic chain), unchanged;
- the node: the option's inputs reach the finish through planes, its record names the option only when it ran, tier 3
  refuses the option in plain words, and a value outside the option's set is refused.
Skipped where torch or scipy is not installed:  python -B -m unittest tests.worker.test_halo_reduction  (artegra-enhancer)."""
import hashlib
import importlib
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

HAVE = all(importlib.util.find_spec(m) is not None for m in ('torch', 'scipy'))
ROOT = Path(__file__).resolve().parents[2]
ORACLE = ROOT / 'tests' / 'fixtures' / 'halo2_v4finish_08a5fc28.py'
ORACLE_SHA256 = '113fc161d0915f464eda251426dc28bfa962289f666d3d87c7fe2a3d55ee8115'
DEHALO = ROOT / 'node_pack' / 'claude_banded' / 'bxf' / 'dehalo.py'
U8 = np.arange(256, dtype=np.float32) / 255.0
_MODS = {}


def by_path(name, path):
    if name not in _MODS:
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _MODS[name] = mod
    return _MODS[name]


def oracle():
    return by_path('cu_test_halo2_oracle_v4finish', ORACLE)


def port():
    return by_path('cu_test_halo_port_dehalo', DEHALO)


def bits(a):
    return np.ascontiguousarray(np.asarray(a, np.float32)).view(np.uint32)


# --- synthetic cards -------------------------------------------------------------------------------------------------------
def card(h0, w0, seed, kind='card'):
    """An original of h0 x w0 px (u8): blocks of different tones with hard edges (vertical ones run the height, so they cross
    every band join), a 1 px dark pole, a 1 px light bar and a thin coloured strip. kind 'sparse': only the top and bottom
    fifths hold them; 'flat': no edge at all."""
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:h0, 0:w0].astype(np.float32)
    img = np.full((h0, w0, 3), (0.55, 0.53, 0.50), np.float32)
    if kind == 'flat':
        img += rng.normal(0, 0.01, img.shape).astype(np.float32)
        return np.clip(img * 255 + 0.5, 0, 255).astype(np.uint8)
    rows = (y < 0.18 * h0) | (y > 0.82 * h0) if kind == 'sparse' else np.ones_like(y, bool)
    for _ in range(8):
        x0 = int(rng.integers(0, max(1, w0 - 6)))
        bw = int(rng.integers(max(3, w0 // 6), max(4, w0 // 2)))
        y0 = int(rng.integers(0, max(1, h0 // 2)))
        bh = int(rng.integers(max(4, h0 // 5), max(5, h0)))
        m = (x >= x0) & (x < x0 + bw) & (y >= y0) & (y < y0 + bh) & rows
        img[m] = rng.uniform(0.1, 0.9, 3) * np.array([1.0, 0.95, 0.88])
    img[rows & (x == w0 // 3)] = (0.06, 0.06, 0.07)
    img[rows & (x == (2 * w0) // 3)] = (0.95, 0.95, 0.93)
    img[rows & (y >= h0 // 2) & (y < h0 // 2 + 2) & (x > 2)] = (0.80, 0.25, 0.15)
    img += rng.normal(0, 0.004, img.shape).astype(np.float32)
    return np.clip(img * 255 + 0.5, 0, 255).astype(np.uint8)


def rendered(src_u8, H, W, seed, inert=False):
    """A stand-in finish output with rims: the source's bicubic at (H, W), sharpened (an overshoot at every edge), with grain;
    inert: the bilinear alone (inside the clamp's envelope everywhere)."""
    from PIL import Image
    from scipy.ndimage import gaussian_filter
    rng = np.random.default_rng(seed + 7)
    a = np.asarray(Image.fromarray(src_u8).resize((W, H), Image.BILINEAR if inert else Image.BICUBIC)).astype(np.float32) / 255
    if inert:
        return a
    s = max(1.0, H / src_u8.shape[0] * 0.6)
    out = a + 0.9 * (a - gaussian_filter(a, (s, s, 0))) + rng.normal(0, 0.008, a.shape).astype(np.float32)
    return np.clip(out, 0, 1).astype(np.float32)


def up_luma(src_f32, H, W):
    import torch
    import torch.nn.functional as F
    return F.interpolate(torch.from_numpy(np.ascontiguousarray(oracle().luma(src_f32)))[None, None], size=(H, W),
                         mode='bilinear', align_corners=False, antialias=False)[0, 0].numpy().astype(np.float32)


def clamp_case(h0, w0, stage_f, later, seed=3, kind='card', heights=(288,), inert=False):
    """The oracle's whole post and final clamps against the port's bands on one card; later: the pass input is the original
    upsampled to the pass frame (its anchor) by that factor, and f is output px per original px."""
    from PIL import Image
    O, P = oracle(), port()
    orig = card(h0, w0, seed, kind)
    src8 = orig if not later else np.asarray(Image.fromarray(orig).resize((int(round(w0 * later)), int(round(h0 * later))),
                                                                          Image.BILINEAR))
    H, W = int(round(src8.shape[0] * stage_f)), int(round(src8.shape[1] * stage_f))
    S = U8[src8]
    f = H / h0 if later else H / S.shape[0]
    Yref, Ys = up_luma(S, H, W), O.luma(S).astype(np.float32)
    out = rendered(src8, H, W, seed, inert)
    Y2 = O.luma(out).astype(np.float32)
    want_post = O.edge_profile_clamp3(Y2, Yref, f, Ysrc=Ys, guard='fringe')
    dYp = (want_post - Y2).astype(np.float32)
    want_fin = O._final_clamp3(out, (Yref, f, Ys, S, 'fringe'), dYp)
    rec = {'f': f, 'post_changed': int(np.count_nonzero(bits(want_post) != bits(Y2))),
           'guard_matters': int(np.count_nonzero(bits(O.edge_profile_clamp3(Y2, Yref, f, Ysrc=Ys, guard='bil'))
                                                 != bits(want_post)))}
    Ys_p, D0, D2 = (np.zeros(S.shape[:2], np.float32) for _ in range(3))
    P.source_planes(lambda a, b: S[a:b], Ys_p, D0, D2, rows=100)
    rec['ys_equal'] = bool(np.array_equal(bits(Ys_p), bits(Ys)))
    for h in heights:
        got_post = P.clamp_luma_bands(Y2, Yref, f, Ys_p, np.zeros_like(Y2), h)
        r0, rf = np.zeros_like(out), np.zeros_like(out)
        which, st = P.final_clamp_bands(out, Yref, f, Ys_p, D0, D2, (got_post - Y2).astype(np.float32), r0, rf, h)
        got_fin = {'out': out, 'res0': r0, 'resf': rf}[which]
        rec[h] = {'post_diff': int(np.count_nonzero(bits(got_post) != bits(want_post))),
                  'fin_diff': int(np.count_nonzero(bits(got_fin) != bits(want_fin))), 'which': which, 'stats': st}
    return rec


@unittest.skipUnless(HAVE, 'torch and scipy are not installed here (run on the worker runtime)')
class TheOracle(unittest.TestCase):
    def test_the_oracle_is_round_2s_frozen_finish(self):
        self.assertEqual(hashlib.sha256(ORACLE.read_bytes()).hexdigest(), ORACLE_SHA256)
        self.assertIn('edge3f', oracle().v4_finish.__doc__)
        self.assertEqual(port().PORTED_FROM, 'halo2/fix 08a5fc28 node_pack/claude_creative/v4finish.py')

    def test_the_ported_parameters_and_reach_are_round_2s(self):
        O, P = oracle(), port()
        self.assertEqual(P.DEHALO, O.DEHALO)
        self.assertEqual(P.DEHALO3, O.DEHALO3)
        self.assertEqual(P.DEHALO3_GUARD, O.DEHALO3_GUARD)
        self.assertEqual((P.LINE_BINS, P.LINE_HALF), (O.LINE_BINS, O.LINE_HALF))
        for f in (1.5, 2, 3, 4, 6, 8):
            self.assertEqual(P.edge_profile_clamp3_reach(f), O.edge_profile_clamp3_reach(f))
        self.assertEqual([P.edge_profile_clamp3_reach(f) for f in (2, 4, 6, 8)], [174, 334, 494, 654])


@unittest.skipUnless(HAVE, 'torch and scipy are not installed here (run on the worker runtime)')
class TheClampInBands(unittest.TestCase):
    """The port's band drivers against the oracle's whole calls: 0 differing float32 values, post and final."""

    def check(self, rec, which='resf', changed=True):
        self.assertTrue(rec['ys_equal'])
        for h in [k for k in rec if isinstance(k, int)]:
            self.assertEqual(rec[h]['post_diff'], 0, rec)
            self.assertEqual(rec[h]['fin_diff'], 0, rec)
            self.assertEqual(rec[h]['which'], which, rec)
        if changed:
            self.assertGreater(rec['post_changed'], 0, rec)
            self.assertGreater(rec['guard_matters'], 0, rec)          # the thin-line guard decides pixels on this card
        return rec

    def test_a_first_pass_at_2x_and_1_5x(self):
        self.check(clamp_case(576, 192, 2, None, heights=(288, 576)))
        self.check(clamp_case(576, 192, 1.5, None))

    def test_a_later_pass_with_its_anchor_at_4x_6x_and_8x(self):
        self.check(clamp_case(288, 64, 2, 2, heights=(288, 576)))      # f 4: reach 334
        self.check(clamp_case(192, 48, 1.5, 4))                        # f 6: reach 494
        self.check(clamp_case(180, 24, 2, 4))                          # f 8: reach 654

    def test_bands_that_hold_no_edge_of_geometry(self):
        for args in ((1152, 96, 2, None, 8, 'sparse'), (720, 48, 2, 2, 8, 'sparse')):
            rec = self.check(clamp_case(*args))
            self.assertGreater(rec[288]['stats']['bands_without_edges'], 0, rec)

    def test_no_edge_of_geometry_is_the_finishs_own_output_and_nothing_removed_skips_the_chroma_pass(self):
        self.check(clamp_case(576, 192, 2, None, 6, 'flat'), which='out', changed=False)
        rec = self.check(clamp_case(576, 192, 2, None, 4, 'card', inert=True), which='res0', changed=False)
        self.assertEqual(rec['post_changed'], 0)


# --- the finish ------------------------------------------------------------------------------------------------------------
def gate_g2():
    from tests.worker.test_bxf_finish import tool
    return tool('gate_g2')


def scene(h, w, seed, later):
    """(pre, creative, structure, init, protect, release, anchor or None, anchor_factor or None) at stage factor 2: G2's
    scene; for a later pass the original is the pre at half size and the anchor that original upsampled back to the pre's
    frame (Pillow's bilinear, as the service makes it), anchor_factor 4."""
    from PIL import Image
    pre, cr, st, it, pm, rm = gate_g2().scene(h, w, 2, seed=seed)
    if not later:
        return pre, cr, st, it, pm, rm, None, None
    orig = np.asarray(Image.fromarray(pre).resize((w // 2, h // 2), Image.BILINEAR))
    anchor = np.asarray(Image.fromarray(orig).resize((w, h), Image.BILINEAR))
    return pre, cr, st, it, pm, rm, anchor, 2.0 * w / orig.shape[1]


def oracle_chain(pre, creative, structure, init, protect, release, opts, out_size, anchor=None, anchor_factor=None):
    """Round 2's ClaudeV4Finish (dehalo 'edge3f') -> ClaudeShadowToe -> SaveImage on the same 8-bit inputs, then the crop."""
    G2, V = gate_g2(), oracle()
    toe = G2.classic_function('shadow_toe_u8')
    a = [V.quantize_8bit(U8[t][..., :3]) for t in (creative, structure, init, pre)]
    g = None if opts.get('glow') in (None, 'none') else opts['glow']
    o = V.v4_finish(*a, protect if opts.get('protect') else None, smooth=opts['smooth'], protect_dilate=12, protect_feather=4.0,
                    islands=opts['islands'], chroma_clamp=opts['chroma_clamp'], keep_blacks=opts['keep_blacks'],
                    clamp=opts['clamp'], lf=opts['lf'], glow=g, fin_b0_hi=opts['fin_b0_hi'],
                    release=release if (opts.get('release') and opts.get('protect')) else None,
                    island_after_lf=bool(opts['island_after_lf']), dehalo='edge3f',
                    anchor=None if anchor is None else U8[anchor][..., :3], anchor_factor=anchor_factor)
    o = V.to_u8(o).astype(np.float32) / 255.0
    u8 = np.clip(np.round(o * 255), 0, 255).astype(np.uint8)
    saved = np.clip(255. * (toe(u8, *G2.TOE).astype(np.float32) / 255.0), 0, 255).astype(np.uint8)
    ow, oh = out_size
    return np.ascontiguousarray(saved[:oh, :ow])


def bxf_chain(inputs, opts, out_size, work, table, dehalo=None, height=None, extra=None):
    """The banded exact finish on planes in `work` (G2's bxf_chain with the option's inputs): (output u8, BXF record). extra:
    finish keywords given as they are (an 'anchor' array is put in a plane first), in place of the scene's own."""
    G2 = gate_g2()
    F, E = G2.bxf_module()
    planes = E('planes')
    pre, cr, st, it, pm, rm, anchor, factor = inputs
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    maps = {}
    for name, arr in (('creative', cr), ('structure', st), ('init', it), ('pre', pre)):
        maps[name] = planes.from_array(work / f'{name}.plane', arr).map('r')
    kw = {} if dehalo is None else dict(dehalo=dehalo, anchor=anchor, anchor_factor=factor)
    if extra is not None:
        kw = dict(extra)
    if kw.get('anchor') is not None:
        kw['anchor'] = planes.from_array(work / 'anchor.plane', kw['anchor']).map('r')
    b = F.BXF(G2.v4(), G2.classic_function('shadow_toe_u8'), E, work / 'bxf', band_gb=2.0, table=table, band_height=height)
    g = None if opts.get('glow') in (None, 'none') else opts['glow']
    try:
        res = b.finish(maps['creative'], maps['structure'], maps['init'], maps['pre'], pm if opts.get('protect') else None,
                       rm if (opts.get('release') and opts.get('protect')) else None, smooth=opts['smooth'],
                       protect_dilate=12, protect_feather=4.0, islands=opts['islands'], chroma_clamp=opts['chroma_clamp'],
                       keep_blacks=opts['keep_blacks'], clamp=opts['clamp'], lf=opts['lf'], glow=g,
                       fin_b0_hi=opts['fin_b0_hi'], island_after_lf=bool(opts['island_after_lf']), **kw)
        ow, oh = out_size
        outp = planes.Plane.create(work / 'output.plane', (oh, ow, 3), 'u8', producer='halo reduction test')
        b.write_output(res, G2.TOE[0], G2.TOE[1], outp)
        outp.finish()
        got = outp.read_rows(0, oh)
        rec = dict(b.record(0), workspace_peak_bytes=int(b.ws.peak_bytes))
        del res
    finally:
        b.close()
    return got, rec


def tables():
    from tests.worker.test_bxf_finish import numpy_scipy_banded
    F, E = gate_g2().bxf_module()
    g1 = E('bxf.g1')
    out = {'numpy-scipy banded': numpy_scipy_banded(g1), 'whole': g1.AllWhole()}
    if g1.load().applies:
        out['g1'] = g1.load()
    return out


H0, W0 = 264, 300            # the pre (a stage factor of 2: the finish plane is 528 x 600)
SIZE = (2 * W0 - 3, 2 * H0 - 5)


@unittest.skipUnless(HAVE, 'torch and scipy are not installed here (run on the worker runtime)')
class TheFinishWithTheOption(unittest.TestCase):
    def test_on_equals_round_2s_finish_in_every_option_case_first_pass_and_later_pass(self):
        G2 = gate_g2()
        tabs = tables()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            for later in (False, True):
                ins = scene(H0, W0, 11, later)
                for name, opts in G2.CASES.items():
                    if later and name not in ('v4f', 'v4f-protect-release', 'lead', 'no-clamp-glow'):
                        continue                        # a later pass: the anchor's cases (every branch runs at the first)
                    want = oracle_chain(*ins[:6], opts, SIZE, anchor=ins[6], anchor_factor=ins[7])
                    off = G2.classic_chain(*ins[:6], opts, SIZE)
                    for label, tab in tabs.items():
                        if label != 'numpy-scipy banded' and name not in ('v4f', 'v4f-protect-release', 'lead'):
                            continue                    # every case with numpy / scipy banded; three with every op whole
                        got, rec = bxf_chain(ins, opts, SIZE, Path(td) / f'{later}-{name}-{label}'.replace(' ', '-'), tab,
                                             dehalo='edge3f', height=288)
                        self.assertEqual(int(np.count_nonzero(got != want)), 0, (later, name, label))
                        self.assertEqual(rec['dehalo']['mode'], 'edge3f')
                        self.assertEqual(rec['dehalo']['guard'], 'fringe')
                        self.assertEqual(rec['dehalo']['f'], 4.0 if later else 2.0)
                    self.assertGreater(int(np.count_nonzero(want != off)), 0, (later, name))   # the option changes pixels

    def test_off_is_5_0_1s_finish_and_its_record_does_not_name_the_option(self):
        G2 = gate_g2()
        ins = scene(H0, W0, 11, False)
        tab = tables()['numpy-scipy banded']
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            for name in ('v4f', 'v4f-protect-release'):
                opts = G2.CASES[name]
                want = G2.classic_chain(*ins[:6], opts, SIZE)
                got, rec = bxf_chain(ins, opts, SIZE, Path(td) / name, tab, height=288)
                self.assertEqual(int(np.count_nonzero(got != want)), 0, name)
                self.assertNotIn('dehalo', rec)

    def test_the_band_height_is_pixel_neutral(self):
        G2 = gate_g2()
        ins = scene(H0, W0, 12, True)
        tab = tables()['numpy-scipy banded']
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            a, ra = bxf_chain(ins, G2.CASES['v4f'], SIZE, Path(td) / 'a', tab, dehalo='edge3f', height=288)
            b, rb = bxf_chain(ins, G2.CASES['v4f'], SIZE, Path(td) / 'b', tab, dehalo='edge3f', height=576)
            self.assertEqual(int(np.count_nonzero(a != b)), 0)
            self.assertEqual((ra['dehalo']['band_height'], rb['dehalo']['band_height']), (288, 576))

    def test_values_outside_the_options_set_are_refused_in_plain_words(self):
        G2 = gate_g2()
        ins = scene(H0, W0, 11, True)
        A = ins[6]
        tab = tables()['numpy-scipy banded']
        cases = ((dict(dehalo='edge3', anchor=A, anchor_factor=4.0), 'dehalo'),
                 (dict(dehalo='edge3f', anchor=A, anchor_factor=None), 'anchor_factor'),
                 (dict(dehalo='edge3f', anchor=A, anchor_factor=0.5), 'anchor_factor'),
                 (dict(dehalo='edge3f', anchor=np.ascontiguousarray(A[:-2]), anchor_factor=4.0), 'anchor'),
                 (dict(anchor=A, anchor_factor=4.0), 'anchor'))
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            for i, (kw, why) in enumerate(cases):
                with self.assertRaises(ValueError) as cm:
                    bxf_chain(ins, G2.CASES['v4f'], SIZE, Path(td) / f'bad{i}', tab, height=288, extra=kw)
                self.assertIn(why, str(cm.exception), kw)


@unittest.skipUnless(HAVE, 'torch and scipy are not installed here (run on the worker runtime)')
class TheNode(unittest.TestCase):
    def test_the_node_runs_the_option_through_planes_and_tier_3_refuses_it(self):
        from tests.worker.test_bxf_finish import fake_classic_pack
        G2 = gate_g2()
        fake_classic_pack(G2, self)
        pack = G2.load_pack()
        bxf = importlib.import_module(pack.__name__ + '.bxf')
        planes = pack._engine('planes')
        ins = scene(H0, W0, 13, True)
        opts = dict(G2.V4F, protect=True, release=True)
        want = oracle_chain(*ins[:6], opts, SIZE, anchor=ins[6], anchor_factor=ins[7])
        self.assertIn('dehalo', bxf.CUFinishBanded.INPUT_TYPES()['optional'])
        self.assertEqual(bxf.CUFinishBanded.INPUT_TYPES()['optional']['dehalo'][0], ['off', 'edge3f'])
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            td = Path(td)
            refs = {}
            for name, arr in (('pre', ins[0]), ('creative', ins[1]), ('structure', ins[2]), ('init', ins[3]),
                              ('protect', ins[4][..., None]), ('release', ins[5][..., None]), ('anchor', ins[6])):
                planes.from_array(td / f'{name}.plane', arr)
                refs[name] = pack.PlaneRef(td / f'{name}.plane', 'r1')
            kw = dict(smooth_lo=0.2, smooth_hi=0.5, protect_dilate=12, protect_feather=4.0, islands=True, chroma_clamp=True,
                      finish='bxf-1', toe_amount=0.40, toe_scale=0.06, output_width=SIZE[0], output_height=SIZE[1],
                      filename_prefix='cu', run_id='r1', quantize_8bit=True, keep_blacks='render', clamp='agree5',
                      lf='hybmin', glow='skygaps', fin_b0_hi=6.0, island_after_lf=True)
            ins_ = {k: refs[k] for k in ('creative', 'structure', 'init', 'pre', 'protect', 'release')}
            try:
                bxf.FORCE = 'bxf'
                r = bxf.CUFinishBanded().run(output_plane=str(td / 'out-on.plane'), dehalo='edge3f', anchor=refs['anchor'],
                                             anchor_factor=ins[7], **ins_, **kw)
                p = planes.validate(r['ui']['planes'][0]['path'], shape=(SIZE[1], SIZE[0], 3), dtype='u8')
                self.assertEqual(int(np.count_nonzero(p.read_rows(0, SIZE[1]) != want)), 0)
                rec = r['ui']['planes'][0]['finish']
                self.assertEqual((rec['dehalo']['mode'], rec['dehalo']['f']), ('edge3f', 4.0))
                self.assertEqual(p.header['finish']['dehalo']['mode'], 'edge3f')
                off = bxf.CUFinishBanded().run(output_plane=str(td / 'out-off.plane'), **ins_, **kw)
                self.assertNotIn('dehalo', off['ui']['planes'][0]['finish'])
                off2 = bxf.CUFinishBanded().run(output_plane=str(td / 'out-off2.plane'), dehalo='off', **ins_, **kw)
                self.assertEqual(planes.Plane.open(td / 'out-off.plane').data_sha256(),
                                 planes.Plane.open(td / 'out-off2.plane').data_sha256())
                with self.assertRaises(ValueError) as cm:
                    bxf.CUFinishBanded().run(output_plane=str(td / 'out-bad.plane'), dehalo='edge2f', **ins_, **kw)
                self.assertIn('dehalo', str(cm.exception))
                bxf.FORCE = 'tier3'
                with self.assertRaises(pack.NotBuilt) as cm:
                    bxf.CUFinishBanded().run(output_plane=str(td / 'out-t3.plane'), dehalo='edge3f', anchor=refs['anchor'],
                                             anchor_factor=ins[7], **ins_, **kw)
                self.assertIn('Halo Reduction', str(cm.exception))
                self.assertFalse((td / 'out-t3.plane').exists())
            finally:
                bxf.FORCE = None
            self.assertFalse(any(q.name.startswith('bxf-work') for q in td.iterdir()))


# --- the memory bound (engine/bxf/memory.DEHALO_BPP) ---------------------------------------------------------------------
_CHILD = r"""
import ctypes, ctypes.wintypes as wt, gc, importlib.util, json, sys
import numpy as np

class PMC(ctypes.Structure):
    _fields_ = [('cb', wt.DWORD), ('PageFaultCount', wt.DWORD)] + [(n, ctypes.c_size_t) for n in (
        'PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage', 'QuotaPagedPoolUsage',
        'QuotaPeakNonPagedPoolUsage', 'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage')]

def commit():
    c = PMC(); c.cb = ctypes.sizeof(c)
    k32 = ctypes.WinDLL('kernel32'); k32.GetCurrentProcess.restype = wt.HANDLE
    ps = ctypes.WinDLL('psapi'); ps.GetProcessMemoryInfo.argtypes = [wt.HANDLE, ctypes.POINTER(PMC), wt.DWORD]
    assert ps.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb)
    return c.PagefileUsage, c.PeakPagefileUsage

spec = importlib.util.spec_from_file_location('dh', sys.argv[1]); D = importlib.util.module_from_spec(spec)
spec.loader.exec_module(D)
z = np.load(sys.argv[2]); f = float(sys.argv[3]); which = sys.argv[4]
out, Yref, Ys, D0, D2 = (np.array(z[k]) for k in ('out', 'Yref', 'Ys', 'D0', 'D2'))
Y2 = D.luma(out).astype(np.float32); o1 = np.zeros_like(Y2); dY = np.zeros_like(Y2)
r0, rf = np.zeros_like(out), np.zeros_like(out)
for a in (o1, dY, r0, rf):
    a[...] = 0
gc.collect()
base, _ = commit()
R = D.edge_profile_clamp3_reach(f)
if which == 'post':
    D.clamp_luma_bands(Y2, Yref, f, Ys, o1, 2304, halo=R)
else:
    D.final_clamp_bands(out, Yref, f, Ys, D0, D2, dY, r0, rf, 2304, halo=R)
_, peak = commit()
print(json.dumps({'bytes': peak - base, 'px': int(out.shape[0] * out.shape[1])}))
"""


def dense(H, W, f, seed=1):
    """A finish output, its reference and its source with an edge of geometry near every pixel (blocks every 6-7 source px,
    dark lines), the case that makes the clamp's arrays largest (every pixel near an edge)."""
    from PIL import Image
    rng = np.random.default_rng(seed)
    h, w = int(round(H / f)), int(round(W / f))
    src = np.full((h, w, 3), 0.5, np.float32)
    for y0 in range(0, h, 6):
        for x0 in range(0, w, 7):
            src[y0:y0 + 4, x0:x0 + 5] = rng.uniform(0.05, 0.95, 3)
    src[:, ::13] = 0.05
    s8 = np.clip(src * 255 + 0.5, 0, 255).astype(np.uint8)
    out = np.asarray(Image.fromarray(s8).resize((W, H), Image.BICUBIC)).astype(np.float32) / 255
    out = np.clip(out * 1.15 - 0.07 + rng.normal(0, 0.01, out.shape).astype(np.float32), 0, 1).astype(np.float32)
    ref = np.asarray(Image.fromarray(s8).resize((W, H), Image.BILINEAR)).astype(np.float32) / 255
    return out, ref, s8.astype(np.float32) / 255


@unittest.skipUnless(HAVE and sys.platform == 'win32', 'torch and scipy, and Windows (the process commit counters)')
class TheMemoryBound(unittest.TestCase):
    def test_one_band_call_stays_under_the_counted_bytes_per_pixel(self):
        """The process's peak commit above its inputs during one band call (the whole band read: core 288 rows plus the
        reach above and below), in a fresh process, on dense edges: at most engine/bxf/memory.DEHALO_BPP per pixel read."""
        import json
        import subprocess
        src = (ROOT / 'engine' / 'bxf' / 'memory.py').read_text(encoding='utf8')
        bpp = float(next(line.split('=')[1] for line in src.splitlines() if line.startswith('DEHALO_BPP =')))
        P = port()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            child = Path(td) / 'child.py'
            child.write_text(_CHILD, encoding='utf8')
            for f, W in ((2.0, 1600), (4.0, 1200), (8.0, 800)):
                H = 288 + 2 * P.edge_profile_clamp3_reach(f)
                out, refrgb, S = dense(H, W, f)
                Ys, D0, D2 = (np.zeros(S.shape[:2], np.float32) for _ in range(3))
                P.source_planes(lambda a, b: S[a:b], Ys, D0, D2)
                npz = Path(td) / f'in-{f:g}.npz'
                np.savez(npz, out=out, Yref=P.luma(refrgb).astype(np.float32), Ys=Ys, D0=D0, D2=D2)
                for which in ('post', 'final'):
                    r = subprocess.run([sys.executable, '-B', str(child), str(DEHALO), str(npz), str(f), which],
                                       capture_output=True, text=True, timeout=900)
                    self.assertEqual(r.returncode, 0, r.stderr[-2000:])
                    rec = json.loads(r.stdout.strip().splitlines()[-1])
                    per_px = rec['bytes'] / rec['px']
                    self.assertLessEqual(per_px, bpp, (f, which, per_px))
                    self.assertGreater(per_px, 0.25 * bpp if which == 'final' else 0.2 * bpp, (f, which, per_px))


if __name__ == '__main__':
    unittest.main()
