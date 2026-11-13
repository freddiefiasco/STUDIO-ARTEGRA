"""Media implementation."""


import re
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from engine import controls, planner
from service import images
from service.util import atomic_write_json, link_or_copy, new_id, now_iso, read_json, sha256_file

MEDIA_ID_RE = re.compile(r'^m[0-9a-f]{12}$')
MAX_PATHS = 1000
DUPLICATE_NOTE = 'This file is identical to another image in the list.'
FILES = ('source.png', 'alpha.png', 'exif.bin', 'thumb.jpg', 'proxy.jpg', 'thumb.png', 'proxy.png')
VIEW_FILES = ('view.jpg', 'proxy.jpg', 'thumb.jpg')                           
VIEW_FILES_ALPHA = ('view-alpha.png', 'view.jpg', 'proxy.png', 'thumb.png')   
DISPLAY_TYPES = {'.png': 'image/png', '.jpg': 'image/jpeg'}
IMAGE_FIELDS = ('width', 'height', 'format', 'mode', 'bit_depth', 'alpha', 'icc', 'exif', 'orientation', 'notes')


def ram_refusal(plan, ram_cap_gb):
    """Plain reason when an otherwise valid plan needs more memory than the cap (DESIGN §6: refuse before starting instead of
    failing mid-run), else None."""
    if not plan.ok or not ram_cap_gb or plan.peak_ram_gb <= float(ram_cap_gb):
        return None
    return (f'This upscale would need about {plan.peak_ram_gb:.0f} GB of memory, more than the {float(ram_cap_gb):g} GB the '
            'app may use. Choose a smaller upscale or a smaller image.')


def plan_text(plan, ram_cap_gb=None, minutes=None):
    """Human text for a plan: output size, time, passes, notes (shown under the scale buttons). minutes: the finish time
    to say (the Standard finish time with Settings as they are, `finish.standard.minutes`); None = the planner's own."""
    if not plan.ok:
        return {'summary': plan.reason, 'notes': list(plan.suggestions)}
    refused = ram_refusal(plan, ram_cap_gb)
    if refused:
        return {'summary': refused, 'notes': []}
    w, h = plan.output_size
    mins = plan.minutes if minutes is None else minutes
    t = f'about {mins:.0f} min' if mins < 90 else f'about {mins / 60:.1f} h'
    n = len(plan.stages)
    notes = []
    if any(s.supersample < 2 for s in plan.stages):
        notes.append('Later passes use a lighter setting so the image fits in memory.')
    passes = f'{n} pass' + ('es' if n > 1 else '')
    return {'output': f'{w:,} \u00d7 {h:,} px ({w * h / 1e6:.1f} MP)', 'eta': t, 'passes': passes,
            'summary': f'Output {w:,} \u00d7 {h:,} \u00b7 {t} \u00b7 {passes}',
            'ram': f'about {plan.peak_ram_gb:.0f} GB memory', 'notes': notes}


def plan_dict(plan, ram_cap_gb=None, finish_fn=None):
    """Planner dict for the API, with the memory check applied (ok false and a reason when the cap is too small).
    finish_fn(minutes, plan) -> the `finish` object (the finish time per mode; engine contract part 2, section 1)."""
    d = plan.to_dict()
    refused = ram_refusal(plan, ram_cap_gb)
    if refused:
        d.update(ok=False, reason=refused, suggestions=['Choose a smaller upscale'], ram_refused=True)
    said = None
    if finish_fn is not None:
        d['finish'] = finish_fn(plan.minutes, plan)
        said = said_minutes(plan.minutes, d['finish'])
    return dict(d, text=plan_text(plan, ram_cap_gb, said))


def said_minutes(minutes, finish):
    """The Standard finish time for a plan's text: the planner's minutes times the factor in force (not yet rounded)."""
    factor = ((finish or {}).get('standard') or {}).get('factor')
    return None if factor is None else float(minutes) * factor


def scales_for(w, h, ram_cap_gb=None, finish_fn=None):
    out = {}
    for f in controls.SCALES:
        p = planner.plan(w, h, f)
        refused = ram_refusal(p, ram_cap_gb)
        finish = finish_fn(p.minutes, p) if finish_fn is not None else None
        out[str(f)] = {'ok': p.ok and not refused, 'output_size': list(p.output_size), 'minutes': p.minutes,
                       'passes': len(p.stages) if p.ok else 0, 'reason': refused or p.reason,
                       'suggestions': ['Choose a smaller upscale'] if refused else p.suggestions,
                       'text': plan_text(p, ram_cap_gb, said_minutes(p.minutes, finish))}
        if finish is not None:
            out[str(f)]['finish'] = finish
    return out


class MediaLibrary:
    def __init__(self, media_dir, log):
        self.dir = Path(media_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / 'results').mkdir(exist_ok=True)
        self.log = log
        self._lock = threading.RLock()
        self.records = {}
        self._pending_sha = {}           
        self._pending_path = {}          
        self.ram_cap_fn = None           
        self.finish_fn = None            
        self.decoded = images.DecodedCache(size=2)
        self.sized = images.SizedCopies(self.decoded)     
        self._load()

    def _load(self):
        for d in sorted(self.dir.iterdir()):
            if not MEDIA_ID_RE.match(d.name):
                continue
            p = d / 'media.json'
            try:
                rec = read_json(p)
            except (OSError, ValueError) as e:
                self.log.error('media_load_failed', f'Input record {p} could not be read; it is not listed', data={'error': str(e)})
                continue
            if (d / 'source.png').is_file():
                self.records[rec['id']] = rec
            else:
                self.log.warn('media_incomplete', f'Input {d.name} has no engine file; it is not listed')
        self.log.info('media_loaded', f'{len(self.records)} inputs loaded')

    
    def expand(self, paths):
        files, rejected = [], []
        if not isinstance(paths, list) or not paths:
            raise ValueError('Send a list of file or folder paths.')
        if len(paths) > MAX_PATHS:
            raise ValueError(f'Add at most {MAX_PATHS} paths at a time.')
        for raw in paths:
            if not isinstance(raw, str) or not raw.strip():
                rejected.append({'path': str(raw), 'reason': 'Not a file path.'})
                continue
            p = Path(raw.strip())
            if not p.is_absolute():
                rejected.append({'path': raw, 'reason': 'Use a full path (using the file or folder picker.jpg).'})
            elif p.is_dir():
                found = sorted((c for c in p.iterdir() if c.is_file() and c.suffix.lower() in images.INPUT_EXTENSIONS),
                               key=lambda c: c.name.lower())
                if not found:
                    rejected.append({'path': raw, 'reason': 'This folder has no supported images (PNG, JPEG, TIFF, WebP, BMP).'})
                if len(found) > MAX_PATHS:
                    raise ValueError(f'The folder {p.name} has more than {MAX_PATHS} images; add it in parts.')
                files += found
            elif p.is_file():
                files.append(p)
            else:
                rejected.append({'path': raw, 'reason': 'The file or folder was not found.'})
        unique, seen = [], set()
        for f in files:                   
            key = str(f.resolve()).lower()
            if key not in seen:
                seen.add(key)
                unique.append(f)
        if len(unique) > MAX_PATHS:
            raise ValueError(f'These folders hold more than {MAX_PATHS} images; add them in parts.')
        return unique, rejected

    def add_paths(self, paths):
        files, rejected = self.expand(paths)
        items = [None] * len(files)

        def one(i, f):
            try:
                items[i] = self.preview(self.add_file(f))
            except images.InputRejected as e:
                rejected.append({'path': str(f), 'reason': e.reason})
                self.log.info('input_rejected', f'{f.name}: {e.reason}', data={'path': str(f)})
            except OSError as e:
                rejected.append({'path': str(f), 'reason': 'The file could not be read.'})
                self.log.warn('input_read_failed', f'{f}: {e}', data={'path': str(f)})

        with ThreadPoolExecutor(max_workers=2) as ex:   
            for fut in [ex.submit(one, i, f) for i, f in enumerate(files)]:
                fut.result()
        return [x for x in items if x is not None], rejected

    def _same_file(self, path, st):
        """Existing record of exactly this file (path, size and modification time), if its engine file is still there."""
        with self._lock:
            for r in self.records.values():
                if (str(r.get('path', '')).lower() == str(path).lower() and r.get('bytes') == st.st_size
                        and r.get('mtime_ns') == st.st_mtime_ns):
                    return r
        return None

    def add_file(self, path):
        path = Path(path).resolve()
        key = str(path).lower()
        while True:                       
            with self._lock:
                busy = self._pending_path.get(key)
                if busy is None:
                    self._pending_path[key] = threading.Event()
                    break
            busy.wait()
        try:
            return self._add_file_once(path)
        finally:
            with self._lock:
                self._pending_path.pop(key).set()

    def _add_file_once(self, path):
        st = path.stat()
        same = self._same_file(path, st)
        if same is not None and (self.dir / same['id'] / 'source.png').is_file():
            self.log.info('input_already_added', f'{path.name} is already in the list', data={'media': same['id'],
                                                                                                'path': str(path)})
            return dict(same)
        sha = sha256_file(path)
        mid = new_id('m')
        d = self.dir / mid
        with self._lock:
            dup = next((r for r in sorted(self.records.values(), key=lambda r: (r['added'], r['id']))
                        if r['sha256'] == sha), None)
            dup_pending = self._pending_sha.get(sha)
            if dup is None and dup_pending is None:
                self._pending_sha[sha] = mid
        try:
            return self._add_file(path, st, sha, mid, d, dup, dup_pending)
        finally:
            with self._lock:
                if self._pending_sha.get(sha) == mid:
                    del self._pending_sha[sha]

    def _add_file(self, path, st, sha, mid, d, dup, dup_pending):
        rec = None
        if dup is not None and (self.dir / dup['id'] / 'source.png').is_file():
            d.mkdir(parents=True)
            try:
                for name in FILES:
                    src = self.dir / dup['id'] / name
                    if src.is_file():
                        link_or_copy(src, d / name)
                rec = {k: dup[k] for k in IMAGE_FIELDS if k in dup}
            except OSError as e:
                self.log.warn('duplicate_copy_failed', f'Could not reuse the files of {dup["id"]}: {e}; decoding again')
                shutil.rmtree(d, ignore_errors=True)
                rec = None
        if rec is None:
            try:
                rec = images.normalise(path, d)
            except BaseException:
                shutil.rmtree(d, ignore_errors=True)
                raise
        rec.update(id=mid, path=str(path), name=path.name, sha256=sha, bytes=st.st_size, mtime_ns=st.st_mtime_ns,
                   added=now_iso(), duplicate_of=dup['id'] if dup else dup_pending)
        atomic_write_json(d / 'media.json', rec)
        with self._lock:
            self.records[mid] = rec
        self.log.info('input_added', f'Added {path.name} ({rec["width"]} × {rec["height"]}, {rec["format"]})',
                      data={'media': mid, 'path': str(path), 'sha256': sha, 'alpha': rec['alpha'], 'icc': rec['icc'],
                            'bit_depth': rec['bit_depth'], 'duplicate_of': rec['duplicate_of'], 'notes': rec['notes']})
        return rec

    
    def get(self, mid):
        with self._lock:
            rec = self.records.get(mid)
        if rec is None:
            raise KeyError(mid)
        return dict(rec)

    def list(self):
        with self._lock:
            recs = sorted(self.records.values(), key=lambda r: (r['added'], r['id']))
        return [self.preview(r) for r in recs]

    def _duplicate_of(self, rec):
        """The earlier image in the list with the same content, if it is still in the list."""
        with self._lock:
            if rec.get('duplicate_of') in self.records:
                return rec['duplicate_of']
            earlier = [r for r in self.records.values() if r['sha256'] == rec['sha256'] and r['id'] != rec['id']
                       and (r['added'], r['id']) < (rec['added'], rec['id'])]
        return min(earlier, key=lambda r: (r['added'], r['id']))['id'] if earlier else None

    def path(self, mid, name):
        return self.dir / mid / name

    @staticmethod
    def display_file(folder, kind):
        """(path, content type) of the thumb or proxy to serve from an image's or a result's folder: the RGBA PNG when there is
        one, else the JPEG (opaque images, and records made before v3)."""
        if kind not in ('thumb', 'proxy'):
            raise ValueError(kind)
        png = Path(folder) / f'{kind}.png'
        p = png if png.is_file() else Path(folder) / f'{kind}.jpg'
        return p, DISPLAY_TYPES[p.suffix]

    def source_layer(self, mid):
        """(colour file, alpha file or None) of an image's full-size picture for the 1:1 region route."""
        a = self.dir / mid / 'alpha.png'
        return self.dir / mid / 'source.png', (a if a.is_file() else None)

    @staticmethod
    def result_layer(result_dir):
        """(colour file, alpha file or None) of a result's full-size view for the 1:1 region route."""
        a = Path(result_dir) / 'view-alpha.png'
        return Path(result_dir) / 'view.jpg', (a if a.is_file() else None)

    def preview(self, rec):
        w, h = rec['width'], rec['height']
        dup = self._duplicate_of(rec)
        notes = list(rec['notes']) + ([DUPLICATE_NOTE] if dup else [])
        cap = self.ram_cap_fn() if self.ram_cap_fn is not None else None
        return {'id': rec['id'], 'name': rec['name'], 'path': rec['path'], 'width': w, 'height': h,
                'megapixels': round(w * h / 1e6, 2), 'format': rec['format'], 'bit_depth': rec['bit_depth'],
                'alpha': rec['alpha'], 'icc': rec['icc'], 'exif': rec['exif'], 'notes': notes,
                'duplicate': dup is not None, 'duplicate_of': dup, 'sha256': rec['sha256'], 'added': rec['added'],
                'thumb_url': f'/api/media/{rec["id"]}/thumb', 'proxy_url': f'/api/media/{rec["id"]}/proxy',
                'scales': scales_for(w, h, cap, self.finish_fn)}

    def delete(self, mid):
        with self._lock:
            rec = self.records.pop(mid, None)
        if rec is None:
            raise KeyError(mid)
        shutil.rmtree(self.dir / mid, ignore_errors=False)
        self.log.info('input_removed', f'Removed {rec["name"]} from the list', data={'media': mid})

    def copy_for_job(self, mid, dst_dir):
        """Hard-link (or copy) the engine files into a job's work folder so the job never depends on the library."""
        dst_dir = Path(dst_dir)
        dst_dir.mkdir(parents=True, exist_ok=True)
        for name, dst in (('source.png', 'input.png'), ('alpha.png', 'alpha.png'), ('exif.bin', 'exif.bin')):
            src = self.dir / mid / name
            if src.is_file():
                link_or_copy(src, dst_dir / dst)

    
    def result_dir(self, jid, iid):
        return self.dir / 'results' / f'{jid}_{iid}'

    def result_views_ready(self, jid, iid):
        d = self.result_dir(jid, iid)
        return any(all((d / n).is_file() for n in names) for names in (VIEW_FILES, VIEW_FILES_ALPHA))

    def write_result_views(self, jid, iid, rgb, alpha):
        """Viewer copies of a result. Opaque: view.jpg, proxy.jpg, thumb.jpg, exactly as before v3. With alpha: view-alpha.png,
        view.jpg (colour not flattened), proxy.png and thumb.png (images.write_result_views_rgba)."""
        from PIL import Image
        d = self.result_dir(jid, iid)
        d.mkdir(parents=True, exist_ok=True)
        if alpha is not None:
            images.write_result_views_rgba(d, rgb, alpha)
            return d
        im = Image.fromarray(rgb)
        images.save_atomic(im, d / 'view.jpg', 'JPEG', quality=95, subsampling=0)
        images.write_preview(im, None, d / 'proxy.jpg', images.PROXY_SIDE, 90)
        images.write_preview(im, None, d / 'thumb.jpg', images.THUMB_SIDE, 85)
        return d

    def mask_file(self, mid, key):
        if not re.fullmatch(r'[0-9a-f]{12}', key):
            raise KeyError(key)
        return self.dir / mid / f'mask-{key}.png'
