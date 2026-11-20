"""CUFinishBanded, the finish of a Large-image stage (engine design ENGINE-DESIGN.md section 2.5), in the plan's finish variant
(bxf-1 = 5.0.1's finish; HALO-FIX.md reads "STATUS: NOT FIXED", so there is no other variant), writing the stage output plane
(u8, cropped to the stage's output size).

The fallback ladder (registered in the design before any result):
  tier 0, the banded exact finish (BXF, bxf/finish.py): every op banded where gate G1 measured it band-invariant on this
          environment, else run whole on mapped planes; its proof is G2 (0 differing values against the classic chain);
  tier 3, the whole oracle: 5.0.1's own v4_finish and shadow toe run whole on the planes (exact by construction), only up to
          FINISH_WHOLE_MAX_MP; larger outputs are refused.
The BXF runs when the G1 table applies to this environment (engine/bxf/g1.py: the same torch, numpy, scipy, CPU capability and
processor as G1 measured) and the option set is the 8-bit product set; otherwise tier 3. The band budget and the process count
are the registered defaults (2 GiB, 1 process) in this build: they are not graph inputs yet (wave 2 wires them from the plan).

Importing this module imports nothing beyond the pack's own helpers (G0d); the finish code loads when the node runs."""
import importlib
import sys

from .. import _engine, PlaneRef, NotBuilt, _out, _progress, _RUN, _DIR, _classic_pack, FINISH_WHOLE_MAX_MP

VARIANTS = ('bxf-1',)
FORCE = None            # tests and gates only: 'bxf' or 'tier3' (None: the ladder decides)


def _v4(cc):
    name = cc.__name__ + '.v4finish'
    return sys.modules[name] if name in sys.modules else importlib.import_module(name)


class CUFinishBanded:
    """The finish of a Large-image stage, in the plan's finish variant, writing the stage output plane (cropped to the
    stage's output size). Variant bxf-1 is 5.0.1's finish: the banded exact finish (tier 0) where this environment's G1 table
    applies, else 5.0.1's own v4_finish and shadow toe run whole on the planes (tier 3), refused above FINISH_WHOLE_MAX_MP."""
    @classmethod
    def INPUT_TYPES(cls):
        f = lambda d, lo, hi, st=0.01: ("FLOAT", {"default": d, "min": lo, "max": hi, "step": st})
        i = lambda d: ("INT", {"default": d, "min": 1, "max": 65536})
        return {"required": {"creative": ("PLANE",), "structure": ("PLANE",), "init": ("PLANE",), "pre": ("PLANE",),
                             "smooth_lo": f(0.3, 0.0, 1.0), "smooth_hi": f(0.6, 0.0, 1.0),
                             "protect_dilate": ("INT", {"default": 12, "min": 0, "max": 256}),
                             "protect_feather": f(4.0, 0.0, 64.0, 0.5),
                             "islands": ("BOOLEAN", {"default": True}), "chroma_clamp": ("BOOLEAN", {"default": True}),
                             "finish": (["bxf-1"], {"default": "bxf-1"}), "toe_amount": f(0.40, 0.0, 0.9),
                             "toe_scale": f(0.06, 0.005, 0.5, 0.005), "output_width": i(1024), "output_height": i(1024),
                             "output_plane": ("STRING", {"default": ""}), "filename_prefix": ("STRING", {"default": "cu"}),
                             **_RUN},
                "optional": {"protect": ("PLANE",), "release": ("PLANE",), "quantize_8bit": ("BOOLEAN", {"default": True}),
                             "keep_blacks": (["pre_narrow", "render"], {"default": "pre_narrow"}),
                             "clamp": (["lead", "mm", "agree5"], {"default": "lead"}),
                             "lf": (["hyb", "hybmin"], {"default": "hyb"}),
                             "glow": (["none", "skygaps"], {"default": "none"}),
                             "fin_b0_hi": ("FLOAT", {"default": 2.4, "min": 1.6, "max": 1000.0, "step": 0.1}),
                             "island_after_lf": ("BOOLEAN", {"default": False})}}
    RETURN_TYPES = ()
    FUNCTION = "run"
    OUTPUT_NODE = True
    CATEGORY = "claude_banded"

    @staticmethod
    def choose(mp, quantize_8bit=True, table=None):
        """('bxf' | 'tier3', reason) for a finish of `mp` output megapixels (pure; the ladder of section 2.5)."""
        if FORCE in ('bxf', 'tier3'):
            return FORCE, 'forced'
        why = None
        if not quantize_8bit:
            why = 'the banded finish makes the 8-bit product finish only'
        else:
            t = table if table is not None else _engine('bxf.g1').load()
            why = t.why_not()
        if why is None:
            return 'bxf', 'the G1 table applies to this environment'
        if mp <= FINISH_WHOLE_MAX_MP:
            return 'tier3', why
        raise NotBuilt(f'the banded finish cannot run here ({why}); the whole finish runs only up to {FINISH_WHOLE_MAX_MP:.0f} MP')

    def run(self, creative, structure, init, pre, smooth_lo, smooth_hi, protect_dilate, protect_feather, islands, chroma_clamp,
            finish, toe_amount, toe_scale, output_width, output_height, output_plane, filename_prefix, run_id, protect=None,
            release=None, quantize_8bit=True, keep_blacks='pre_narrow', clamp='lead', lf='hyb', glow='none', fin_b0_hi=2.4,
            island_after_lf=False):
        if finish not in VARIANTS:
            raise ValueError(f'this build makes the finish variant bxf-1 only (got {finish})')
        if smooth_hi <= smooth_lo:
            raise ValueError('CUFinishBanded: smooth_hi must be > smooth_lo')
        cp = creative.plane()
        mode, why = self.choose(cp.shape[0] * cp.shape[1] / 1e6, quantize_8bit)
        args = (creative, structure, init, pre, smooth_lo, smooth_hi, protect_dilate, protect_feather, islands, chroma_clamp,
                finish, toe_amount, toe_scale, output_width, output_height, output_plane, filename_prefix, run_id, protect,
                release, quantize_8bit, keep_blacks, clamp, lf, glow, fin_b0_hi, island_after_lf)
        if mode == 'bxf':
            return self._bxf(*args)
        return self._tier3(*args)

    def _bxf(self, creative, structure, init, pre, smooth_lo, smooth_hi, protect_dilate, protect_feather, islands, chroma_clamp,
             finish, toe_amount, toe_scale, output_width, output_height, output_plane, filename_prefix, run_id, protect, release,
             quantize_8bit, keep_blacks, clamp, lf, glow, fin_b0_hi, island_after_lf, band_gb=None, processes=None):
        """Tier 0: the banded exact finish. band_gb / processes: registered values (defaults: the smallest, 2 GiB, 1)."""
        import numpy as np
        from pathlib import Path
        planes, bands = _engine('planes'), _engine('bands')
        band_gb = bands.check_band_budget(bands.BXF_DEFAULT_BUDGET_GB if band_gb is None else band_gb)
        processes = bands.check_process_count(bands.BXF_DEFAULT_PROCESSES if processes is None else processes)
        cc = _classic_pack()
        F = importlib.import_module(__name__ + '.finish')
        pbar = _progress(120)
        count = [0]

        def tick(name):
            if count[0] < 120:
                count[0] += 1
                pbar.update(1)
        work = Path(output_plane).parent / f'bxf-work-{run_id or "run"}'
        b = F.BXF(_v4(cc), cc.shadow_toe_u8, _engine, work, band_gb=band_gb, processes=processes, progress=tick)
        try:
            maps = [r.plane().map('r') for r in (creative, structure, init, pre)]
            pm = np.asarray(protect.plane().map('r'), np.float32)[..., 0] if protect is not None else None
            rm = np.asarray(release.plane().map('r'), np.float32)[..., 0] if (release is not None and pm is not None) else None
            g = None if glow in (None, 'none') else glow
            o = b.finish(*maps, pm, rm, smooth=(smooth_lo, smooth_hi), protect_dilate=protect_dilate,
                         protect_feather=protect_feather, islands=islands, chroma_clamp=chroma_clamp, keep_blacks=keep_blacks,
                         clamp=clamp, lf=lf, glow=g, fin_b0_hi=None if float(fin_b0_hi) == 2.4 else float(fin_b0_hi),
                         island_after_lf=bool(island_after_lf))
            out = planes.Plane.create(output_plane, (output_height, output_width, 3), 'u8',
                                      producer=f'CUFinishBanded {finish} tier0', run_id=run_id)
            b.write_output(o, float(toe_amount), float(toe_scale), out)
            del o, maps
            sha = out.finish()
        finally:
            b.close()
        return {"ui": {"planes": [{'role': 'output', 'path': str(out.path), 'sha256': sha}]}}

    def _tier3(self, creative, structure, init, pre, smooth_lo, smooth_hi, protect_dilate, protect_feather, islands,
               chroma_clamp, finish, toe_amount, toe_scale, output_width, output_height, output_plane, filename_prefix, run_id,
               protect, release, quantize_8bit, keep_blacks, clamp, lf, glow, fin_b0_hi, island_after_lf):
        """Tier 3 (the base build's body, unchanged): 5.0.1's own v4_finish and shadow toe run whole on the planes."""
        import numpy as np
        planes = _engine('planes')
        cp = creative.plane()
        if cp.shape[0] * cp.shape[1] / 1e6 > FINISH_WHOLE_MAX_MP:
            raise NotBuilt(f'the banded finish is not built in this version; the whole finish runs only up to '
                           f'{FINISH_WHOLE_MAX_MP:.0f} MP')
        cc = _classic_pack()
        v4 = sys.modules[cc.__name__ + '.v4finish'] if (cc.__name__ + '.v4finish') in sys.modules else \
            importlib.import_module(cc.__name__ + '.v4finish')
        t = planes.U8_TO_F32
        a = [t[r.plane().map('r')[..., :3]] for r in (creative, structure, init, pre)]
        if quantize_8bit:
            a = [v4.quantize_8bit(x) for x in a]
        pm = np.asarray(protect.plane().map('r'), np.float32)[..., 0] if protect is not None else None
        rm = np.asarray(release.plane().map('r'), np.float32)[..., 0] if (release is not None and pm is not None) else None
        g = None if glow in (None, 'none') else glow
        o = v4.v4_finish(*a, pm, smooth=(smooth_lo, smooth_hi), protect_dilate=protect_dilate, protect_feather=protect_feather,
                         islands=islands, chroma_clamp=chroma_clamp, keep_blacks=keep_blacks, clamp=clamp, lf=lf, glow=g,
                         fin_b0_hi=None if float(fin_b0_hi) == 2.4 else float(fin_b0_hi), release=rm,
                         island_after_lf=bool(island_after_lf))
        u8 = v4.to_u8(o) if quantize_8bit else np.clip(np.round(np.clip(o, 0, 1) * 255), 0, 255).astype(np.uint8)
        u8 = cc.shadow_toe_u8(u8, float(toe_amount), float(toe_scale))
        u8 = np.ascontiguousarray(u8[:output_height, :output_width])
        out = planes.Plane.create(output_plane, (output_height, output_width, 3), 'u8', producer=f'CUFinishBanded {finish} tier3',
                                  run_id=run_id)
        for y in range(0, output_height, 1152):
            out.write_rows(y, u8[y:y + 1152])
        sha = out.finish()
        return {"ui": {"planes": [{'role': 'output', 'path': str(out.path), 'sha256': sha}]}}
