"""The blind pairs of engine design 7.4 and their sealed key. numpy and Pillow.

Per case:
- 8 edge crops: the worst segments of the union of both outputs' M1 worst lists (ranked by the halo index, so neither engine
  picks them; a segment whose crop centre is within MIN_CENTRE_DIST px of one already taken is skipped);
- 4 crops at band and tile boundaries, the positions taken from the plan (tools/proof/seams.positions), the same for X and Y;
- 1 flat area and 1 textured area, chosen on the source;
- the whole frame as a <= 2048 px proxy, made by the same Lanczos code for both (engine/lanczos_bands: Pillow's own two-pass
  Lanczos, on arrays or by bands on planes, giving the same bytes);
- each crop 512 x 512 at 1:1, beside the source crop at the source's own resolution.
X and Y: X is the Classic engine's output when the first byte of sha256(case id + "/" + crop id) is even, else the Large-image
engine's. Byte-identical X and Y are kept as blind controls (a judge who calls one different shows the floor of judging).

What the judges see carries no engine: the folder <case>/<crop>/ holds source.png, X.png and Y.png, written in that order
(never classic first), as PNG with no text chunks; PAIRS.json lists the pairs, kinds and boxes only. The key
(sealed/KEY.json, which the judges never open) is written once, outside the pairs folder, with its sha256 beside it."""
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

from tools.proof import colour

CROP = 512
PROXY_SIDE = 2048
N_EDGES, N_BOUNDARIES = 8, 4
MIN_CENTRE_DIST = 128
KEY_FORMAT, PAIRS_FORMAT = 'cu-blind-key-1', 'cu-blind-pairs-1'
ORDER_RULE = 'X is the classic when the first byte of sha256(case id + "/" + crop id) is even, else the Large-image engine'


def order(case_id, crop_id):
    b0 = hashlib.sha256(f'{case_id}/{crop_id}'.encode('utf8')).digest()[0]
    return {'X': 'classic', 'Y': 'bes'} if b0 % 2 == 0 else {'X': 'bes', 'Y': 'classic'}


def _box(cx, cy, W, H, size=CROP):
    """A size x size box centred on (cx, cy), moved (never cut) to lie inside W x H."""
    s = min(size, W, H)
    x0 = int(min(max(0, round(cx) - s // 2), W - s))
    y0 = int(min(max(0, round(cy) - s // 2), H - s))
    return [x0, y0, x0 + s, y0 + s]


def _far(c, chosen, d=MIN_CENTRE_DIST):
    return all((c[0] - x) ** 2 + (c[1] - y) ** 2 >= d * d for x, y in chosen)


def select_crops(worst_a, worst_b, positions, source_u8, f):
    """The registered crop set of one case: [{'id', 'kind', 'box' (output px) or None, 'center'?, ...}]."""
    src = np.asarray(source_u8)
    H, W = src.shape[0] * f, src.shape[1] * f
    crops, centres = [], []
    seen = set()
    union = sorted([dict(w, _o=i) for i, w in enumerate(list(worst_a or []) + list(worst_b or []))],
                   key=lambda w: (-(w.get('halo_index') or 0.0), w['_o']))
    for w in union:
        c = (int(w['x']), int(w['y']))
        if c in seen or not _far(c, centres):
            continue
        seen.add(c)
        centres.append(c)
        crops.append({'id': f'edge{len(centres):02d}', 'kind': 'edge', 'center': list(c), 'box': _box(*c, W, H),
                      'halo_index': w.get('halo_index')})
        if len(centres) == N_EDGES:
            break
    rows = sorted({int(v) for vs in (positions.get('rows') or {}).values() for v in vs})
    cols = sorted({int(v) for vs in (positions.get('cols') or {}).values() for v in vs})
    used = set()
    for i in range(1, N_BOUNDARIES + 1):
        cand = [r for r in rows if r not in used]
        if not cand:
            break
        y = min(cand, key=lambda r: abs(r - H * i / (N_BOUNDARIES + 1)))
        used.add(y)
        x = min(cols, key=lambda c: abs(c - W / 2)) if cols else W // 2
        kinds = sorted(k for k, vs in (positions.get('rows') or {}).items() if y in vs)
        crops.append({'id': f'band{i:02d}', 'kind': 'boundary', 'row': y, 'col': x if cols else None, 'kinds': kinds,
                      'center': [int(x), int(y)], 'box': _box(x, y, W, H)})
    L = colour.lstar(src).astype(np.float64)
    hp = np.abs(L - colour.gaussian(L, 1.0))
    w = max(8, int(round(CROP / f)))
    step = max(4, w // 2)
    best_flat, best_tex = None, None
    ys = sorted(set(range(0, max(1, src.shape[0] - w + 1), step)) | {max(0, src.shape[0] - w)})
    xs = sorted(set(range(0, max(1, src.shape[1] - w + 1), step)) | {max(0, src.shape[1] - w)})
    for y0 in ys:
        for x0 in xs:
            sd = float(L[y0:y0 + w, x0:x0 + w].std())
            tx = float(np.median(hp[y0:y0 + w, x0:x0 + w]))      # the median: fine texture, not a few strong edges
            if best_flat is None or sd < best_flat[0]:
                best_flat = (sd, x0, y0)
            if best_tex is None or tx > best_tex[0]:
                best_tex = (tx, x0, y0)
    for kind, best in (('flat', best_flat), ('textured', best_tex)):
        cx, cy = (best[1] + w / 2) * f, (best[2] + w / 2) * f
        crops.append({'id': kind, 'kind': kind, 'center': [int(cx), int(cy)], 'box': _box(cx, cy, W, H),
                      'score': round(best[0], 4)})
    crops.append({'id': 'proxy', 'kind': 'proxy', 'box': None})
    return crops


def proxy(img, side=PROXY_SIDE):
    """The whole frame as a <= side px proxy by engine/lanczos_bands (Pillow's Lanczos; banded on a plane, same bytes)."""
    from engine import lanczos_bands
    if isinstance(img, dict):
        from engine import planes
        p = planes.Plane.open(img['path'])
        H, W, C = p.shape
        size = lanczos_bands.proxy_size(W, H, side)
        dst = lanczos_bands.ArrayRows(np.zeros((size[1], size[0], C), np.uint8))
        tmp = lanczos_bands.ArrayRows(np.zeros((H, size[0], C), np.uint8)) if (size[0] != W and size[1] != H) else None
        lanczos_bands.resize(p, dst, tmp)
        return dst.a[..., :3]
    a = np.asarray(img)
    size = lanczos_bands.proxy_size(a.shape[1], a.shape[0], side)
    return lanczos_bands.resize_array(np.ascontiguousarray(a[..., :3]), size)


def _crop(img, box):
    x0, y0, x1, y1 = box
    if isinstance(img, dict):
        from engine import planes
        return planes.Plane.open(img['path']).read_region(x0, y0, x1, y1)[..., :3]
    return np.ascontiguousarray(np.asarray(img)[y0:y1, x0:x1, :3])


def save_png(arr, path):
    """PNG with no text chunks (Pillow writes IHDR, IDAT and IEND only when given no pnginfo)."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.ascontiguousarray(arr, np.uint8), 'RGB').save(path, format='PNG', compress_level=6)


def _fsha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def make_pairs(case_id, classic_out, bes_out, source_u8, f, crops, pairs_dir):
    """Write every crop's source.png, X.png and Y.png. Returns (manifest rows for the judges, key rows)."""
    src = np.asarray(source_u8)[..., :3]
    man, key = [], []
    for c in crops:
        pid = f'{case_id}/{c["id"]}'
        o = order(case_id, c['id'])
        if c['kind'] == 'proxy':
            arrs = {'classic': proxy(classic_out), 'bes': proxy(bes_out)}
            sc = proxy(src)
            sbox = None
        else:
            arrs = {'classic': _crop(classic_out, c['box']), 'bes': _crop(bes_out, c['box'])}
            x0, y0, x1, y1 = c['box']
            sbox = [x0 // f, y0 // f, -(-x1 // f), -(-y1 // f)]
            sc = src[sbox[1]:sbox[3], sbox[0]:sbox[2]]
        d = Path(pairs_dir) / case_id / c['id']
        save_png(sc, d / 'source.png')
        save_png(arrs[o['X']], d / 'X.png')
        save_png(arrs[o['Y']], d / 'Y.png')
        man.append({'pair': pid, 'case': case_id, 'crop': c['id'], 'kind': c['kind'], 'box': c['box'], 'source_box': sbox,
                    'files': {'source': f'{pid}/source.png', 'X': f'{pid}/X.png', 'Y': f'{pid}/Y.png'}})
        key.append({'pair': pid, 'X': o['X'], 'Y': o['Y'], 'identical': bool(np.array_equal(arrs['classic'], arrs['bes'])),
                    'sha256': {'X': _fsha(d / 'X.png'), 'Y': _fsha(d / 'Y.png')}})
    return man, key


def write_manifest(pairs_dir, rows):
    p = Path(pairs_dir) / 'PAIRS.json'
    data = json.dumps({'format': PAIRS_FORMAT, 'crop': CROP, 'proxy_side': PROXY_SIDE, 'pairs': rows}, indent=1,
                      sort_keys=True).encode('utf8')
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, 'xb') as f:
        f.write(data)
    return hashlib.sha256(data).hexdigest()


def write_key(key_path, rows, pairs_dir, manifest_sha256):
    """Write the sealed key once, outside the pairs folder, and its sha256 beside it. Returns the sha256."""
    kp, pd = Path(key_path).resolve(), Path(pairs_dir).resolve()
    if kp == pd or pd in kp.parents:
        raise ValueError('the key must not be inside the pairs folder')
    doc = {'format': KEY_FORMAT, 'rule': ORDER_RULE, 'manifest_sha256': manifest_sha256,
           'pairs': {r['pair']: {k: v for k, v in r.items() if k != 'pair'} for r in rows}}
    data = json.dumps(doc, indent=1, sort_keys=True).encode('utf8')
    kp.parent.mkdir(parents=True, exist_ok=True)
    with open(kp, 'xb') as f:
        f.write(data)
    sha = hashlib.sha256(data).hexdigest()
    (kp.parent / (kp.name + '.sha256')).write_text(sha + '\n', encoding='utf8')
    return sha


def read_key(key_path, expected_sha256):
    data = Path(key_path).read_bytes()
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        raise ValueError('the key does not match its sealed sha256')
    doc = json.loads(data.decode('utf8'))
    if doc.get('format') != KEY_FORMAT:
        raise ValueError('not a blind key')
    return doc
