"""The identity record of 5.0.1 (engine design, section 3, gates G0a-G0c): what every 5.0.1 plan makes, so that 5.0.2 can
be checked against it.

- G0a: the published planner is frozen in tests/fixtures/planner_5_0_1.py (engine/planner.py of 5.0.1, verbatim); its
  sha256 is recorded here so the copy cannot drift.
- G0b: the sha256 of every pass graph that the classic builders make for a grid of 5.0.1 plans (sizes x factors x memory
  caps, wherever 5.0.1 accepts), across the product's option sets, before and after the memory profiles.
- G0c: the sha256 of the classic engine's files (graph builders, Bolt recipe, node pack and its manifest).

Run against a source tree to write the record (the 5.0.1 fixture was made from the 5.0.1 tree, read-only):
    python -B tests/fixtures/g0_identity.py --root <artegra-enhancer folder> --out tests/fixtures/g0_identity_5_0_1.json
The test (tests/test_engine_identity.py) calls compute() on this tree and compares. Sizes only; no image is read.

5.0.2's one registered exception to the graph record (Max, 20 Nov 2026: "Fold into 5.0.2"): a protect-on stage whose padded
input is above engine/planner.SAM_STOCK_MAX_MP takes ClaudeSAM3DetectLean in place of SAM3_Detect (same inputs, same node
ids). compute() also returns each graph's hash with that class read back as SAM3_Detect ('graphs_stock_view'), which must be
5.0.1's record everywhere, and sam_exception() lists the graphs and plans the exception changes; this tree's record of it is
tests/fixtures/sam_lean_5_0_2.json:
    python -B tests/fixtures/g0_identity.py --root . --exception-out tests/fixtures/sam_lean_5_0_2.json"""
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


LEAN_CLASS = 'ClaudeSAM3DetectLean'


def stock_view(g):
    """The graph with 5.0.2's lean SAM class read back as SAM3_Detect (every other byte as built)."""
    return {k: (dict(v, class_type='SAM3_Detect') if v.get('class_type') == LEAN_CLASS else v) for k, v in g.items()}


def product_graphs(stages):
    """(option set, stage key, graph) for every stage and option set the product can build."""
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
    for name, o in sets.items():
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
            yield name, f'{pw}x{ph}/f{f:g}/s{s:g}/k{k}', g


def graph_records(stages, view=None):
    """{option set: {stage key: graph sha256}} for every stage and option set the product can build (view: applied to each
    graph before it is hashed)."""
    out = {}
    for name, key, g in product_graphs(stages):
        out.setdefault(name, {})[key] = _sha(view(g) if view else g)
    return out


def sam_exception(root):
    """5.0.2's registered exception, as this tree makes it: the ceiling and its source, the graphs of the record that take the
    lean SAM class ({option set: [stage keys]}), the 5.0.1 plans of the grid with a stage above the ceiling, the new node-pack
    file and the classic tree hash."""
    import hashlib as _h
    from engine import planner as tree_planner
    from service import config
    root = Path(root)
    plans = accepted_plans(_planner_501(root))
    stages = unique_stages(plans)
    graphs = {}
    for name, key, g in product_graphs(stages):
        if any(v['class_type'] == LEAN_CLASS for v in g.values()):
            graphs.setdefault(name, []).append(key)
    plan_keys = sorted(f'{w}x{h}/f{f}/cap{cap}' for (w, h, f, cap), p in plans
                       if any(tree_planner.sam_lean(*s.padded_size) for s in p.stages))
    pack = root / 'node_pack' / 'claude_creative'
    return {
        'about': ('5.0.2 registered exception to the identity rule (Max, 20 Nov 2026: "Fold into 5.0.2"): a protect-on stage '
                  'whose padded input is above engine/planner.SAM_STOCK_MAX_MP takes ClaudeSAM3DetectLean in place of '
                  'SAM3_Detect, with the same inputs and node ids. "graphs" and "plans" are the ones of the identity grid it '
                  'changes; every other graph is 5.0.1's byte for byte. Written by tests/fixtures/g0_identity.py '
                  '--exception-out.'),
        'lean_class': LEAN_CLASS,
        'sam_stock_max_mp': tree_planner.SAM_STOCK_MAX_MP,
        'source': tree_planner.SAM_STOCK_MAX_SOURCE,
        'graphs': {k: sorted(v) for k, v in sorted(graphs.items())},
        'plans': plan_keys,
        'counts': {'graphs': sum(len(v) for v in graphs.values()), 'plans': len(plan_keys),
                   'stages_above': sum(1 for (pw, ph, f, s, k) in stages if tree_planner.sam_lean(pw, ph))},
        'new_files': {'node_pack/claude_creative/sam_lean.py': _h.sha256((pack / 'sam_lean.py').read_bytes()).hexdigest()},
        'classic_tree_sha256': config.verify_node_pack(pack)['tree_sha256'],
    }


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
    out = {
        'planner_sha256': _file_sha(root / 'tests' / 'fixtures' / 'planner_5_0_1.py')
        if (root / 'tests' / 'fixtures' / 'planner_5_0_1.py').is_file() else _file_sha(root / 'engine' / 'planner.py'),
        'frozen': {rel: _file_sha(root / rel) for rel in FROZEN},
        'plans': {f'{w}x{h}/f{f}/cap{cap}': _sha(p.to_dict()) for (w, h, f, cap), p in plans},
        'graphs': graphs,
        'other_graphs': chain_and_preview_records(),
        'counts': {'plans': len(plans), 'stages': len(stages), 'graphs': sum(len(v) for v in graphs.values())},
    }
    if (root / 'node_pack' / 'claude_creative' / 'sam_lean.py').is_file():         # 5.0.2: the lean SAM class read back
        out['graphs_stock_view'] = graph_records(stages, view=stock_view)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True)
    ap.add_argument('--out')
    ap.add_argument('--exception-out')
    a = ap.parse_args(argv)
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(Path(a.root).resolve()))
    if a.exception_out:
        exc = sam_exception(Path(a.root).resolve())
        Path(a.exception_out).write_text(json.dumps(exc, indent=1, sort_keys=True) + '
', encoding='utf8')
        print(json.dumps(exc['counts']))
    if not a.out:
        return
    rec = compute(Path(a.root).resolve())
    Path(a.out).write_text(json.dumps(rec, indent=1, sort_keys=True) + '\n', encoding='utf8')
    print(json.dumps(rec['counts']))


if __name__ == '__main__':
    main()
