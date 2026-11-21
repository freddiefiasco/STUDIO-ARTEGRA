"""The phase diff of engine design section 7.2: every intermediate of the Classic engine against the same intermediate of the
Large-image engine (BES), counted per phase, so a difference is located at its first phase. numpy and engine/planes only.

Phases, in run order (a difference in an earlier phase explains the later ones; the first differing phase is where to look):
  sam           each SAM term mask ('sam/<group>/<i>'), the unions ('union/protect', 'union/release'), the protect gate
                ('gate', derived on both sides from the dumped unions by the classic's own protect_gate)
  x4            the canvas and init
  hints         hint, edges and the ControlNet outputs of the first 64 windows ('cn/<sampler node>/<instance>')
  vae_samplers  the latent after the encode, after KS1 and after KS2 ('latent/encode', 'latent/ks1', 'latent/ks2')
  decodes       raw8 and rawlo8
  finish        the finish output, then the stage output

The two executors store some intermediates differently by design, so each role is compared in ONE canonical form, never raw:
  bitwise       the same dtype, every element's bits (float32 -0.0 against 0.0 differs; NaN payloads count)
  u8_table      a float plane against a u8 plane through the classic's own conversion (engine/planes.U8_TO_F32), float32 bits:
                the canvas at k != 4 and init (ImageScale lanczos makes k/255 floats; the BES stores k)
  q8            a float plane truncated to 8 bits as the finish's quantize_8bit does (np.clip(255. * x, 0, 255).astype(uint8))
                against a u8 plane: raw8 and rawlo8 (the classic's area-scaled decodes; the BES stores them so)
  round8        a float plane rounded to 8 bits as ClaudeShadowToe reads it, against u8: the finish output
  edges         ClaudeCannyTiled's 0/1 float, 3 channels (which must agree), against the BES's one-channel u8 (0 / non-0)
  save8_crop    the classic's toe output as SaveImage writes it (np.clip(255. * x, 0, 255).astype(uint8)), cropped at the top
                left to the BES's stage output plane (the classic renders the padded stage; the service crops)
  cn            ControlNet call records: sha256 per output tensor per call, values where both runs kept them

A role present on one side only is a difference ('missing'), except the optional roles (the BES has no separate pre-toe
finish output until its banded finish exposes one), which are listed as not compared."""
import numpy as np

from engine import planes as _planes

PHASES = ('sam', 'x4', 'hints', 'vae_samplers', 'decodes', 'finish')
ROLE_PHASE = {'sam': 'sam', 'union': 'sam', 'gate': 'sam', 'canvas': 'x4', 'init': 'x4', 'hint': 'hints', 'edges': 'hints',
              'cn': 'hints', 'latent': 'vae_samplers', 'raw8': 'decodes', 'rawlo8': 'decodes', 'finish': 'finish',
              'stage_output': 'finish'}
DEFAULT_FORMS = {'sam': 'bitwise', 'union': 'bitwise', 'gate': 'bitwise', 'canvas': 'u8_table', 'init': 'u8_table',
                 'hint': 'bitwise', 'edges': 'edges', 'cn': 'cn', 'latent': 'bitwise', 'raw8': 'q8', 'rawlo8': 'q8',
                 'finish': 'round8', 'stage_output': 'save8_crop'}
FORMS = ('bitwise', 'u8_table', 'q8', 'round8', 'edges', 'save8_crop', 'cn')
OPTIONAL_ROLES = frozenset({'finish'})
T = _planes.U8_TO_F32


def phase_of(role):
    return ROLE_PHASE[str(role).split('/')[0]]


def form_of(role, a=None, b=None):
    fa, fb = (a or {}).get('form'), (b or {}).get('form')
    if fa and fb and fa != fb:
        raise ValueError(f'{role}: the two runs name different compared forms ({fa}, {fb})')
    return fa or fb or DEFAULT_FORMS[str(role).split('/')[0]]


class _Arr:
    """An intermediate read in row bands: a plane file, an .npy file (memory-mapped) or, in tests, an array."""

    def __init__(self, entry):
        kind = entry.get('kind', 'plane')
        if kind == 'plane':
            self._p = _planes.Plane.open(entry['path'])
            self.shape, self.dtype = self._p.shape, self._p.dtype
            self.rows = self._p.read_rows
        elif kind in ('npy', 'array'):
            a = np.load(entry['path'], mmap_mode='r') if kind == 'npy' else np.asarray(entry['array'])
            if a.ndim == 2:
                a = a[..., None]
            if a.ndim != 3:
                raise ValueError(f'an intermediate must be H x W (x C), not {a.shape}')
            self._a = a
            self.shape, self.dtype = tuple(a.shape), a.dtype
            self.rows = lambda y0, y1: np.ascontiguousarray(self._a[y0:y1])
        else:
            raise ValueError(f'unknown intermediate kind {kind!r}')


def _is_float(a):
    return a.dtype.kind == 'f'


def _bits(a):
    if a.dtype.kind == 'f':
        return a.view({2: np.uint16, 4: np.uint32, 8: np.uint64}[a.dtype.itemsize])
    return a


def _canon(form, x, other_dtype):
    """(canonical array, form-error mask or None) of one side's band."""
    if form == 'bitwise':
        return x, None
    if form == 'u8_table':
        return (T[x] if x.dtype == np.uint8 else x.astype(np.float32, copy=False)), None
    if form in ('q8', 'save8_crop'):
        return (x if x.dtype == np.uint8 else np.clip(255. * x.astype(np.float32, copy=False), 0, 255).astype(np.uint8)), None
    if form == 'round8':
        return (x if x.dtype == np.uint8 else np.clip(np.round(x.astype(np.float32) * 255), 0, 255).astype(np.uint8)), None
    if form == 'edges':
        if x.dtype == np.uint8:
            return x[..., 0] != 0, None
        c0 = x[..., 0]
        err = ~np.isin(c0, (0.0, 1.0))
        for c in range(1, x.shape[2]):
            err |= x[..., c] != c0
        return c0 > 0.5, err
    raise ValueError(f'unknown compared form {form!r}')


def compare_entries(a, b, form, band_rows=1024):
    """Count the differing elements of intermediate a (the reference, the classic) against b (the BES) in `form`."""
    if form == 'cn':
        return _compare_cn(a, b)
    A, B = _Arr(a), _Arr(b)
    out = {'form': form, 'shape_a': list(A.shape), 'shape_b': list(B.shape), 'count': 0, 'elements': 0, 'max_abs': 0.0,
           'first_row': None}
    if form == 'save8_crop':
        ok = A.shape[0] >= B.shape[0] and A.shape[1] >= B.shape[1] and A.shape[2] == B.shape[2]
        H, W = B.shape[0], B.shape[1]
    elif form == 'edges':
        ok = A.shape[:2] == B.shape[:2]
        H, W = A.shape[0], A.shape[1]
    else:
        ok = A.shape == B.shape and (form != 'bitwise' or A.dtype == B.dtype)
        H, W = A.shape[0], A.shape[1]
    if not ok:
        n = max(int(np.prod(A.shape)), int(np.prod(B.shape)))
        return dict(out, status='shape', count=n, elements=n, max_abs=None)
    for y0 in range(0, H, band_rows):
        y1 = min(H, y0 + band_rows)
        ra, rb = A.rows(y0, y1), B.rows(y0, y1)
        if form == 'save8_crop':
            ra = ra[:, :W]
        ca, ea = _canon(form, ra, B.dtype)
        cb, eb = _canon(form, rb, A.dtype)
        if ca.dtype != cb.dtype:
            ca, cb = ca.astype(np.float32), cb.astype(np.float32)
        diff = _bits(np.ascontiguousarray(ca)) != _bits(np.ascontiguousarray(cb))
        for e in (ea, eb):
            if e is not None:
                diff |= e if e.shape == diff.shape else e[..., None]
        n = int(diff.sum())
        out['elements'] += int(diff.size)
        if n:
            out['count'] += n
            if out['first_row'] is None:
                out['first_row'] = y0 + int(np.argmax(diff.reshape(diff.shape[0], -1).any(1)))
            if ca.dtype != np.bool_:
                with np.errstate(invalid='ignore'):
                    d = np.abs(ca.astype(np.float64) - cb.astype(np.float64))[diff]
                m = float(np.nanmax(d)) if d.size and np.isfinite(d).any() else float('nan')
                out['max_abs'] = m if out['max_abs'] is None or not np.isfinite(out['max_abs']) else max(out['max_abs'], m)
            else:
                out['max_abs'] = 1.0
    out['status'] = 'differ' if out['count'] else 'equal'
    return out


ITEMSIZE = {'float16': 2, 'bfloat16': 2, 'float32': 4, 'float64': 8, 'uint8': 1, 'int8': 1, 'int16': 2, 'int32': 4,
            'int64': 8, 'bool': 1}


def _tensor_diff(fa, fb, dtype):
    """Differing elements of two raw tensor files of one dtype (a torch dtype name such as 'torch.float16')."""
    da, db = np.fromfile(fa, np.uint8), np.fromfile(fb, np.uint8)
    size = ITEMSIZE[str(dtype).replace('torch.', '')]
    if da.size != db.size:
        return max(da.size, db.size) // size
    if size > 1:
        return int((da.reshape(-1, size) != db.reshape(-1, size)).any(1).sum())
    return int((da != db).sum())


def _compare_cn(a, b):
    """ControlNet call records, call by call: equal sha256 lists are 0; otherwise the differing elements when both runs kept
    the values ('files'), else the call counts once and the count is not exact."""
    ca, cb = list(a.get('calls') or []), list(b.get('calls') or [])
    out = {'form': 'cn', 'calls_a': len(ca), 'calls_b': len(cb), 'count': 0, 'exact': True, 'first_call': None,
           'elements': None}
    for i in range(max(len(ca), len(cb))):
        x, y = (ca[i] if i < len(ca) else None), (cb[i] if i < len(cb) else None)
        if x is not None and y is not None and list(x.get('sha256') or []) == list(y.get('sha256') or []):
            continue
        if out['first_call'] is None:
            out['first_call'] = i
        if x is not None and y is not None and x.get('files') and y.get('files') and len(x['files']) == len(y['files']):
            out['count'] += sum(_tensor_diff(fa, fb, dt) for fa, fb, dt in zip(x['files'], y['files'],
                                                                              x.get('dtypes') or ['uint8'] * len(x['files'])))
        else:
            out['count'] += 1
            out['exact'] = False
    out['status'] = 'differ' if out['count'] else 'equal'
    return out


def count(classic, bes, optional=OPTIONAL_ROLES, band_rows=1024):
    """The phase diff of two runs. classic, bes: {role: entry} (entry: {'kind': 'plane' | 'npy' | 'cn', 'path' | 'calls',
    'form'?}). Returns {'phases': [{'phase', 'differing', 'exact', 'roles': {role: result}}], 'first_differing_phase',
    'missing', 'not_compared', 'zero'}."""
    roles = sorted(set(classic) | set(bes), key=lambda r: (PHASES.index(phase_of(r)), r))
    by = {p: {'phase': p, 'differing': 0, 'exact': True, 'roles': {}} for p in PHASES}
    missing, skipped = [], []
    for role in roles:
        ph = by[phase_of(role)]
        a, b = classic.get(role), bes.get(role)
        if a is None or b is None:
            if role.split('/')[0] in optional:
                skipped.append(role)
                continue
            missing.append(role)
            ph['roles'][role] = {'status': 'missing', 'count': 1, 'side': 'bes' if b is None else 'classic'}
            ph['differing'] += 1
            ph['exact'] = False
            continue
        r = compare_entries(a, b, form_of(role, a, b), band_rows=band_rows)
        ph['roles'][role] = r
        ph['differing'] += int(r['count'])
        if r.get('exact') is False or r['status'] == 'shape':
            ph['exact'] = False
    rows = [by[p] for p in PHASES]
    first = next((p['phase'] for p in rows if p['differing']), None)
    return {'phases': rows, 'first_differing_phase': first, 'missing': missing, 'not_compared': skipped,
            'zero': first is None}
