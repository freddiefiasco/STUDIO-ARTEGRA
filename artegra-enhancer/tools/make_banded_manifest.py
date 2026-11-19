"""Write node_pack/MANIFEST-banded.json for the Large-image engine's node pack (node_pack/claude_banded). The classic pack's
MANIFEST.json is never touched. Run after changing a file of the banded pack:  python tools/make_banded_manifest.py"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def manifest():
    sys.path.insert(0, str(ROOT))
    from service.config import tree_sha256
    d = ROOT / 'node_pack' / 'claude_banded'
    files = {}
    for p in sorted(d.rglob('*')):
        if p.is_file() and '__pycache__' not in p.parts:
            b = p.read_bytes()
            files[p.relative_to(d).as_posix()] = {'sha256': hashlib.sha256(b).hexdigest(), 'bytes': len(b)}
    return {'source': 'Artegra Enhancer 5.0.2 development branch engine/5.0.2: the Large-image engine nodes',
            'files': files, 'tree_sha256': tree_sha256(files)}


if __name__ == '__main__':
    (ROOT / 'node_pack' / 'MANIFEST-banded.json').write_text(json.dumps(manifest(), indent=2) + '\n', encoding='utf8')
