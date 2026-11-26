"""Three message fixes of the 5.0.2 release copy review, each a sentence a person reads (handover section 14, 23 Nov 18:35;
eng:check-2 CHK2-2 and CHK2-3):

- W4S-C6: the processor-check sentences gave 'about 1 minutes'. bxf_probe.say formats them, and reads '1 minutes' as
  '1 minute'; the service formats every one of them through it.
- CHK2-2: the Large-image RAM refusal compared the need with what an idle computer can free (its memory less PHYS_IDLE_GB) but
  stated the computer's whole memory beside it, so a refused image could read as fitting. It now states the figure the rule
  compares with, rounded down, beside the need rounded up.
- CHK2-3: when a stopped Large-image engine's Windows Job handle does not close, nothing in the app can end its processes, and
  the card takes no engine until the app restarts. The sentence said 'until it has been closed'; it now says to restart.

Sizes and stubs only."""
import ast
import math
import re
import unittest
from pathlib import Path
from types import SimpleNamespace

from service import banded_runner, bxf_probe

ROOT = Path(__file__).resolve().parents[1]
MINUTE_TEMPLATES = ('PROBE_WAITING', 'PROBE_HELD', 'PROBE_WAITING_OTHERS', 'PROBE_REQUESTED', 'PREVIEW_DURING_CHECK',
                    'READING_REFUSED')


class OneMinute(unittest.TestCase):
    def test_every_minutes_sentence_reads_one_minute(self):
        for name in MINUTE_TEMPLATES:
            t = getattr(bxf_probe, name)
            self.assertIn('{m} minutes', t, name)
            one = bxf_probe.say(t, 1)
            self.assertIn('about 1 minute', one, name)
            self.assertNotIn('1 minutes', one, name)
            self.assertEqual(bxf_probe.say(t, 3), t.format(m=3), name)
            self.assertEqual(bxf_probe.say(t, 11), t.format(m=11), name)          # '11 minutes' is left alone

    def test_the_service_formats_them_only_through_say(self):
        src = (ROOT / 'service' / 'runner.py').read_text(encoding='utf-8')
        for name in MINUTE_TEMPLATES:
            self.assertNotRegex(src, rf'\b{name}\.format\(', name)
        tree = ast.parse(src)
        said = {n.args[0].attr for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, 'attr', None) == 'say'
                and n.args and isinstance(n.args[0], ast.Attribute)}
        self.assertEqual(said, set(MINUTE_TEMPLATES))


def _plan(w, h):
    return SimpleNamespace(output_size=(w, h), stages=[SimpleNamespace(output_size=(w, h))])


class TheRamRefusalStatesWhatItComparesWith(unittest.TestCase):
    def test_a_refused_image_never_reads_as_fitting(self):
        figures = re.compile(r'needs about (\d+) GB of free system memory \(RAM\) to start, counting its Large-image work '
                             r'files, more than the (\d+) GB this computer can free \((\d+) GB in all\)\.$')
        n = 0
        for total in (47.7, 61.6, 63.4, 127.4):
            free = total - banded_runner.PHYS_IDLE_GB
            for over in (0.05, 0.4, 0.6, 0.95, 3.0, 5.9):              # needs just above, and well above, what can be freed
                need = 20.0                                                   # over PHYS_LONE_GB: its share is capped
                planes = free + over - banded_runner.PHYS_LONE_GB - banded_runner.PHYS_SPARE_GB
                lone = banded_runner.lone_need_gb(need, planes)
                self.assertAlmostEqual(lone, free + over)
                why = banded_runner.physical_refusal(_plan(20000, 10000), need, planes, total)
                self.assertIsNotNone(why, (total, over))
                m = figures.search(why)
                self.assertIsNotNone(m, why)
                stated_need, stated_free, stated_total = map(int, m.groups())
                self.assertEqual(stated_need, math.ceil(lone))
                self.assertEqual(stated_free, math.floor(free))
                self.assertGreater(stated_need, stated_free, why)
                self.assertEqual(stated_total, round(total))
                n += 1
        self.assertGreater(n, 12)


class TheLostCardSaysToRestart(unittest.TestCase):
    def test_the_sentence(self):
        text = banded_runner.RELEASE_LOST_TEXT.format(where='GPU 1')
        self.assertIn('could not be stopped after its image', text)
        self.assertIn('until you restart Artegra Enhancer', text)
        self.assertNotIn('until it has been closed', text)
        self.assertIn('until it has been closed', banded_runner.RELEASE_KEPT_TEXT)      # the kept (not lost) engine is closed

    def test_both_lost_paths_use_it(self):
        for rel in ('service/banded_runner.py', 'service/workers.py'):
            src = (ROOT / rel).read_text(encoding='utf-8')
            self.assertIn('RELEASE_LOST_TEXT.format(where=', src, rel)
            for line in src.splitlines():
                if 'mark_lost(' in line and 'def ' not in line:
                    self.assertNotIn('RELEASE_KEPT_TEXT', line, rel)


if __name__ == '__main__':
    unittest.main()
