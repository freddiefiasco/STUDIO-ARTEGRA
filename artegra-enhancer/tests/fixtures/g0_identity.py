"""The identity record of 5.0.1 (engine design, section 3, gates G0a-G0c): what every 5.0.1 plan makes, so that 5.0.2 can
be checked against it.

- G0a: the published planner is frozen in tests/fixtures/planner_5_0_1.py (engine/planner.py of 5.0.1, verbatim); its
  sha256 is recorded here so the copy cannot drift.
- G0b: the sha256 of every pass graph that the classic builders make for a grid of 5.0.1 plans (sizes x factors x memory
  caps, wherever 5.0.1 accepts), across the product's option sets, before and after the memory profiles.
- G0c: the sha256 of the classic engine's files (graph builders, Bolt recipe, node pack and its manifest).

Run against a source tree to write the record (the 5.0.1 fixture was made from the 5.0.1 tree, read-only):
    python -B tests/fixtures/g0_identity.py --root <artegra-enhancer folder> --out tests/fixtures/g0_identity_5_0_1.json
The test (tests/test_engine_identity.py) calls compute() on this tree and compares. Sizes only; no image is read."""
import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

FROZEN = ('engine/graph_v5t.py', 'engine/fast_recipe.py', 'engine/controls.py', 'engine/run_order.py', 'engine/schedule.py',
          'node_pack/MANIFEST.json', 'node_pack/claude_creative/__init__.py', 'node_pack/claude_creative/spot.py',
          'node_pack/claude_creative/v4finish.py', 'node_pack/claude_creative/live.py', 'node_pack/claude_creative/noise.py',
          'node_pack/claude_creative/imageops.py', 'node_pack/claude_creative/spot_timing.py',
          'node_pack/claude_creative/LICENSE.txt')
SIZES = [(w, h) for w in (512, 777, 1280, 1600, 2188, 2800, 3500, 4096, 6000) for h in (512, 1600, 2188, 2800, 3500)]
FACTORS = (2, 4, 6, 8)
CAPS = (None, 45.2, 59.0, 61.2, 100.0, 122.2)


def _sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf8')).hexdigest()


def _file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _planner_501(root):
    """The published planner: the frozen fixture copy when it exists, else the tree's engine/planner.py (the 5.0.1 tree)."""
    fix = Path(root) / 'tests' / 'fixtures' / 'planner_5_0_1.py'
    path = fix if fix.is_file() else Path(root) / 'engine' / 'planner.py'
    spec = importlib.util.spec_from_file_location('planner_501_for_g0', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def accepted_plans(planner):
    """Every (w, h, factor, cap) of the grid that 5.0.1 accepts (ok, and within the cap when there is one), with its plan."""
    out = []
    for w, h in SIZES:
        for f in FACTORS:
            for cap in CAPS:
                p = planner.plan(w, h, f, ram_cap_gb=cap)
                if p.ok and (cap is None or p.peak_ram_gb <= cap):
                    out.append(((w, h, f, cap), p))
    return out


def unique_stages(plans):
    """(padded w, padded h, f, s, k) of every stage of the accepted plans, each once."""
    seen = set()
    for _, p in plans:
        for s in p.stages:
            seen.add((s.padded_size[0], s.padded_size[1], s.factor, s.supersample, s.index))
    return sorted(seen)


def _frac(v):
    from fractions import Fraction
    return Fraction(v).limit_denominator(8)


def graph_records(stages):
    """{option set: {stage key: graph sha256}} for every stage and option set the product can build."""
    from engine import controls, fast_recipe, graph_v5t
    from service import memory_policy
    bal = memory_policy.PROFILES['balanced']
    ref = memory_policy.PROFILES['reference']
    p_def, _ = controls.resolve({})
    p_off, _ = controls.resolve({'protect': []})
    p_all, _ = controls.resolve({'protect': list(controls.PROTECT_ORDER)})
    sets = {
        'base': dict(params=p_def),
        'live_detailed': dict(params=p_def, live='detailed'),
        'live_rough': dict(params=p_def, live='rough'),
        'stack_off': dict(params=p_def, stack=False),
        'stack_off_live_detailed': dict(params=p_def, stack=False, live='detailed'),
        'faster': dict(params=p_def, faster=True),
        'creative_first_two_cards': dict(params=p_def, creative_first=True, cards=2),
        'two_cards_static': dict(params=p_def, cards=2, balance='static'),
        'protect_off': dict(params=p_off),
        'protect_all_release': dict(params=p_all, live='detailed'),
        'balanced': dict(params=p_def, profile=bal),
        'balanced_two_cards': dict(params=p_def, profile=bal, cards=2, live='rough'),
        'reference_profile': dict(params=p_def, profile=ref),
        'bolt': dict(params=p_def, bolt=True),
        'bolt_live_detailed_balanced': dict(params=p_def, bolt=True, live='detailed', profile=bal),
    }
    out = {}
    for name, o in sets.items():
        rec = {}
        for (pw, ph, f, s, k) in stages:
            pk = controls.stage_params(o['params'], k)
            prefix = f'cu_j_i_s{k}'
            fr, sr = _frac(f), _frac(s)
            if o.get('bolt'):
                if f != 2 or s != 2:
                    continue
                g, info = fast_recipe.build(prefix + '.png', pw, ph, pk, prefix, f=fr, s=sr, live_preview=o.get('live'))
            else:
                g, info = graph_v5t.build_product(prefix + '.png', pw, ph, pk, prefix, f=fr, s=sr,
                                                  speed_stack=o.get('stack', True), live_preview=o.get('live'),
                                                  faster=o.get('faster', False), creative_first=o.get('creative_first', False))
            if 'profile' in o:
                g, info = memory_policy.apply_graph(g, info, o['profile'])
            if o.get('cards'):
                g = graph_v5t.add_multigpu(g, o['cards'], balance=o.get('balance', 'auto'))
            rec[f'{pw}x{ph}/f{f:g}/s{s:g}/k{k}'] = _sha(g)
        out[name] = rec
    return out


def chain_and_preview_records():
    from engine import controls, graph_v5t
    p, _ = controls.resolve({'protect': list(controls.PROTECT_ORDER)})
    rec = {}
    for (w, h, stages) in ((1024, 1024, [(2, 2), (2, 1)]), (1280, 1600, [(2, 2), (2, 2), (2, 1)]), (1000, 504, [(1.5, 2)])):
        chain, cw, ch = [], w, h
        for k, (f, s) in enumerate(stages):
            fr, sr = _frac(f), _frac(s)
            chain.append((cw, ch, fr, sr, controls.stage_params(p, k), f'c{k}'))
            cw, ch = int(cw * fr), int(ch * fr)
        g, _ = graph_v5t.build_chain('x.png', chain, spot_options=graph_v5t.product_options(True, 'detailed'))
        rec[f'chain/{w}x{h}/{len(stages)}'] = _sha(g)
    for terms, release in ((['wall'], ['tree']), (p['protect_terms'], p['release_terms']), (['person'], [])):
        rec[f'gate/{len(terms)}/{len(release)}'] = _sha(graph_v5t.build_gate_preview('x.png', terms, release, p['protect'], 'g'))
    rec['mask/1'] = _sha(graph_v5t.build_mask_preview('x.png', [('a', ['wall']), ('b', ['tree', 'person'])], p['protect'], 'm'))
    rec['mask/all'] = _sha(graph_v5t.build_mask_preview('x.png', [('all', p['protect_terms'])], p['protect'], 'm'))
    return rec


def compute(root):
    root = Path(root)
    planner = _planner_501(root)
    plans = accepted_plans(planner)
    stages = unique_stages(plans)
    graphs = graph_records(stages)
    return {
        'planner_sha256': _file_sha(root / 'tests' / 'fixtures' / 'planner_5_0_1.py')
        if (root / 'tests' / 'fixtures' / 'planner_5_0_1.py').is_file() else _file_sha(root / 'engine' / 'planner.py'),
        'frozen': {rel: _file_sha(root / rel) for rel in FROZEN},
        'plans': {f'{w}x{h}/f{f}/cap{cap}': _sha(p.to_dict()) for (w, h, f, cap), p in plans},
        'graphs': graphs,
        'other_graphs': chain_and_preview_records(),
        'counts': {'plans': len(plans), 'stages': len(stages), 'graphs': sum(len(v) for v in graphs.values())},
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args(argv)
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(Path(a.root).resolve()))
    rec = compute(Path(a.root).resolve())
    Path(a.out).write_text(json.dumps(rec, indent=1, sort_keys=True) + '\n', encoding='utf8')
    print(json.dumps(rec['counts']))


if __name__ == '__main__':
    main()
