"""docs/SOURCE-MAP.json covers the code (docs/PROVENANCE.md): every file under engine/, service/, node_pack/, ui/qml/ and
cu_service.py is listed once, and every listed file exists. Its recorded hashes are the files as 5.0.0-beta.1 released them;
the layers 5.0.1 and 5.0.2 mark the files a later release changed, so a file without such a layer must still be byte for byte
what 5.0.0-beta.1 released, and a file new after 5.0.0-beta.1 carries its release's layer and no hashes until that release
records them. A package that adds or changes a file there is red here until the merge role updates the map."""
import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / 'docs' / 'SOURCE-MAP.json'
SCOPE_DIRS = ('engine', 'service', 'node_pack', 'ui/qml')
SCOPE_FILES = ('cu_service.py',)
LATER = {'5.0.1', '5.0.2'}


def in_scope():
    out = [f for f in SCOPE_FILES if (ROOT / f).is_file()]
    for d in SCOPE_DIRS:
        out += [p.relative_to(ROOT).as_posix() for p in (ROOT / d).rglob('*')
                if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc']
    return sorted(out)


def entries():
    return json.loads(MAP.read_text(encoding='utf-8'))['files']


class TheSourceMap(unittest.TestCase):
    def test_every_file_in_scope_is_listed_once_and_every_listed_file_exists(self):
        listed = [e['path'] for e in entries()]
        self.assertEqual(len(listed), len(set(listed)), 'a file is listed twice')
        self.assertEqual(sorted(set(in_scope()) - set(listed)), [], 'files missing from docs/SOURCE-MAP.json')
        self.assertEqual(sorted(set(listed) - set(in_scope())), [], 'listed files that do not exist')
        self.assertEqual(listed, sorted(listed))

    def test_a_file_without_a_later_layer_is_as_5_0_0_beta_1_released_it(self):
        changed = [e['path'] for e in entries() if not (LATER & set(e['layers']))
                   and hashlib.sha256((ROOT / e['path']).read_bytes()).hexdigest() != e['public_sha256']]
        self.assertEqual(changed, [], 'changed after 5.0.0-beta.1 without a 5.0.1 or 5.0.2 layer')

    def test_a_file_new_after_5_0_0_beta_1_has_its_release_layer_and_no_hashes_yet(self):
        for e in entries():
            if e['merge'] in ('5.0.1 (new)', '5.0.2 (new)'):
                self.assertIn(e['merge'].split()[0], e['layers'], e['path'])
                for k in ('source_sha256', 'final_v5_sha256', 'public_sha256'):
                    self.assertIsNone(e[k], (e['path'], k))
            else:
                self.assertIsNotNone(e['public_sha256'], e['path'])


if __name__ == '__main__':
    unittest.main()
