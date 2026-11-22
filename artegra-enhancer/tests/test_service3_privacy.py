"""5.0.2 build wave 3, privacy and release text in the service package's files (BUILD-WAVE-3 service item 7):
- the 'Temporary file ...' log line of a Large-image result (service/banded_runner.encode_publish): the support bundle's scrub
  removes a full path from it as it removes 5.0.1's lines (service/runner.py, service/images.py), and the line itself now
  names the file only;
- S3: a Classic engine image held beside a running Large-image image is not told about Large-image work files of its own;
- the copy reviews of wave 2 (wp/2-service/copy-review-1.txt and -2.txt): the Large-image pass failures name the engine, the
  Classic engine's sentences stay 5.0.1's, and the smallest card the Large-image engine runs on is KNOWN-ISSUES' 12 GB.
Sizes and synthetic values only."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np

import support_bundle
from engine import planes, vram_model
from service import banded_runner, plane_io
from service import runner as runner_mod
import tests.test_service3_g1u as G

ROOT = Path(__file__).resolve().parents[1]
# built at run time, so this file holds no path of its own (tools/public_scan.py)
BS = chr(92)
PATHS = ('C' + chr(58) + BS + BS.join(('Users', 'someone', 'Pictures', 'Client render.partial.png')),
         BS * 2 + BS.join(('nas-host', 'share', 'Client render.partial.png')),
         '/home/someone/Client render.partial.png')


class TheTemporaryFileLine(unittest.TestCase):
    def test_the_bundle_scrub_removes_a_full_path(self):
        for path in PATHS:
            for line in (f'Temporary file {path} could not be removed: [WinError 32] in use',
                         f'Temporary file {Path(path).name} could not be removed: in use'):
                row = json.dumps({'event': 'temp_cleanup_failed', 'msg': line, 'level': 'warn'})
                out = json.dumps(support_bundle.sanitize(json.loads(row)))
                for part in ('someone', 'nas-host', 'share', 'Client render'):
                    self.assertNotIn(part, out, (path, out))

    def test_the_large_image_line_names_the_file_only(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            work, out_dir = td / 'work', td / 'someone' / 'out'
            work.mkdir()
            out_dir.mkdir(parents=True)
            last = planes.from_array(work / 'stage0.u8', np.zeros((8, 8, 3), np.uint8))
            log = G.Log()
            r = SimpleNamespace(log=log)
            ctx = SimpleNamespace(jid='j1', iid='i001')

            def encode(tmp, plane, fmt, **kw):
                Path(tmp).write_bytes(b'partial')
                raise RuntimeError('boom')
            real_unlink = Path.unlink

            def unlink(self, *a, **k):
                if '.partial' in self.name:
                    raise PermissionError(13, 'Access is denied')
                return real_unlink(self, *a, **k)
            with mock.patch.object(plane_io, 'encode', encode), mock.patch.object(Path, 'unlink', unlink):
                with self.assertRaises(RuntimeError):
                    banded_runner.encode_publish(r, ctx, {}, {}, work, last.path, out_dir, 'Client render', 2, 'png8',
                                                 '.png', 8, 8)
            line = next(x for x in log.lines if x[1] == 'temp_cleanup_failed')
            self.assertNotIn(str(out_dir), line[2])
            self.assertNotIn('someone', line[2])
            self.assertIn('.partial.png', line[2])
            self.assertIn('Access is denied', line[2])


class S3TheClassicCandidate(unittest.TestCase):
    def test_it_is_not_told_about_work_files_of_its_own(self):
        memory = {'avail_phys_gb': 2.0, 'total_phys_gb': 64.0}
        running = [(30.0, 12.0)]
        classic = {'engine': 'classic', 'output_size': [7000, 4376]}
        banded = {'engine': 'banded', 'output_size': [28000, 17504]}
        c = banded_runner.physical_problem(classic, 20.0, 0.0, running, memory)
        b = banded_runner.physical_problem(banded, 20.0, 4.0, running, memory)
        self.assertEqual(c, banded_runner.PHYS_WAIT_OTHERS_CLASSIC.format(w=7000, h=4376))
        self.assertNotIn('needs for its Large-image work files', c)
        self.assertIn("another image's Large-image work files", c)
        self.assertEqual(b, banded_runner.PHYS_WAIT_OTHERS.format(w=28000, h=17504))


class TheCopyReviews(unittest.TestCase):
    def test_the_large_image_pass_failures_name_the_engine(self):
        src = (ROOT / 'service' / 'banded_runner.py').read_text(encoding='utf8')
        self.assertNotIn("'The engine ", src)
        self.assertNotIn("f'The engine ", src)
        for text in (banded_runner.RESTART_FAILED, banded_runner.RESTART_MEMORY, banded_runner.RESTART_BEFORE_FAILED,
                     banded_runner.RESTART_BEFORE_MEMORY):
            self.assertTrue(text.startswith('The Large-image engine '), text)

    def test_the_engine_error_sentence(self):
        r = SimpleNamespace(settings=SimpleNamespace(get=lambda: {'ram_cap_gb': 59.0}))
        err = {'messages': [['execution_error', {'exception_type': 'RuntimeError', 'exception_message': 'boom'}]]}
        mem = {'messages': [['execution_error', {'exception_type': 'MemoryError', 'exception_message': 'x'}]]}
        cut = {'messages': [['execution_interrupted', {}]]}
        text = runner_mod.Runner._engine_error_text
        # the Classic engine's sentences are 5.0.1's
        self.assertEqual(text(r, err, 1, 3), 'The engine stopped with an error in pass 2 of 3. Details are in the log.')
        self.assertEqual(text(r, mem, 1, 3, 4), 'The engine ran out of system memory (limit 59\xa0GB) in pass 2 of 3. '
                                                'Try a smaller upscale.')
        self.assertEqual(text(r, cut, 0, 1), 'The engine stopped unexpectedly.')
        # a Large-image pass names its engine
        self.assertEqual(text(r, err, 1, 3, large=True),
                         'The Large-image engine stopped with an error in pass 2 of 3. Details are in the log.')
        self.assertTrue(text(r, mem, 1, 3, 4, large=True).startswith('The Large-image engine ran out of system memory'))
        self.assertEqual(text(r, cut, 0, 1, large=True), 'The Large-image engine stopped unexpectedly.')

    def test_the_smallest_card_is_known_issues_12_gb(self):
        self.assertFalse(vram_model.EIGHT_GB_PROVEN)
        small = runner_mod.BANDED_SMALL_CARD.format(gb=12)
        self.assertEqual(small, 'The Large-image engine runs only on graphics cards with 12 GB of memory or more.')
        known = (ROOT / 'KNOWN-ISSUES.md').read_text(encoding='utf8')
        self.assertIn('runs only on graphics cards with 12 GB of memory or more', known)
        self.assertNotIn('proven', runner_mod.BANDED_UNPROVEN)
        self.assertNotIn('proven', runner_mod.BANDED_8GB)


if __name__ == '__main__':
    unittest.main()
