"""The Large-image finish re-run on a stage's stored planes (engine design 9.2 R1f, R3f, W10, W11a, W11b; D7): the build's
own node_pack/claude_banded CUFinishBanded, loaded as ComfyUI loads a pack (outside ComfyUI, no model, no card), run on the
planes a stage kept, with the stage graph's own finish values and, where the row asks, a second band height and process
count from the registered sets or a finish tier (contracts.finish_inputs). Needs the worker runtime (torch, scipy).

    python -B -m tools.proof.finish_rerun --job <job.json> --out <output.plane> [--band-gb 3] [--processes 2] [--tier bxf]

job.json is the oracle job's shape (tools/proof/phase_run.compare_runs writes it beside each BES stage): {"app",
"inputs": the CUFinishBanded values of the stage graph (classic.finish_inputs), "planes": {"creative", "structure", "init",
"pre", "protect"?, "release"?}}. The output plane is the re-run's own (never the stage's). An input this build's node does
not declare is refused in plain words (FinishInputMissing), never dropped. Prints {"sha256", "settings", "record"}."""
import argparse
import importlib.util
import json
import sys
from pathlib import Path

PACK = 'cu_proof_banded_pack'
RERUN_KEYS = ('band_gb', 'processes', 'finish_tier')
PLANE_ROLES = ('creative', 'structure', 'init', 'pre', 'protect', 'release')


class FinishInputMissing(RuntimeError):
    pass


def load_pack(app):
    """A fresh copy of <app>/node_pack/claude_banded under a private package name, registered before its __init__ runs (as
    ComfyUI's custom-node loader registers a pack, so its relative node imports resolve to this copy)."""
    for name in [m for m in sys.modules if m == PACK or m.startswith(PACK + '.')]:
        del sys.modules[name]
    root = Path(app) / 'node_pack' / 'claude_banded'
    spec = importlib.util.spec_from_file_location(PACK, root / '__init__.py', submodule_search_locations=[str(root)])
    mod = importlib.util.module_from_spec(spec)
    sys.modules[PACK] = mod
    try:
        spec.loader.exec_module(mod)
    except BaseException:
        del sys.modules[PACK]
        raise
    return mod


def node_optional(node_cls):
    return set(((node_cls.INPUT_TYPES() or {}).get('optional') or {}).keys())


def rerun_kwargs(node_cls, inputs, planes, out_path, plane_ref, band_gb=None, processes=None, finish_tier=None,
                 run_id='proof-rerun'):
    """The keyword arguments of the node's run(): the stage's values, the planes as the node's plane handles, the re-run's
    own output plane, and the asked settings; refuses a setting the node does not declare."""
    kw = {k: v for k, v in dict(inputs).items() if k not in PLANE_ROLES}
    kw['output_plane'] = str(out_path)
    kw['run_id'] = run_id
    for role in PLANE_ROLES:
        if planes.get(role):
            kw[role] = plane_ref(planes[role], run_id)
    asked = {k: v for k, v in (('band_gb', band_gb), ('processes', processes), ('finish_tier', finish_tier)) if v is not None}
    missing = sorted(set(asked) - node_optional(node_cls))
    if missing:
        raise FinishInputMissing('this build\'s CUFinishBanded takes no ' + ', '.join(missing) + ' (contracts.finish_inputs)')
    kw.update(asked)
    return kw


def rerun(app, job, out_path, band_gb=None, processes=None, finish_tier=None, pack=None):
    """Run the finish once on the job's planes into out_path. Returns {'sha256', 'settings', 'record'}."""
    from engine import planes
    pack = pack or load_pack(app)
    node = pack.CUFinishBanded if hasattr(pack, 'CUFinishBanded') else pack.bxf.CUFinishBanded
    kw = rerun_kwargs(node, job['inputs'], job['planes'], out_path, pack.PlaneRef, band_gb, processes, finish_tier)
    res = node().run(**kw)
    rec = res if isinstance(res, dict) else None
    return {'sha256': planes.validate(out_path).header['sha256'], 'record': rec,
            'settings': {'band_gb': band_gb, 'processes': processes, 'finish_tier': finish_tier}}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--job', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--band-gb', type=float)
    ap.add_argument('--processes', type=int)
    ap.add_argument('--tier')
    a = ap.parse_args(argv)
    job = json.loads(Path(a.job).read_text(encoding='utf8'))
    sys.path.insert(0, str(Path(job['app'])))
    out = rerun(job['app'], job, a.out, a.band_gb, a.processes, a.tier)
    print(json.dumps(out, default=str))


if __name__ == '__main__':
    main()
