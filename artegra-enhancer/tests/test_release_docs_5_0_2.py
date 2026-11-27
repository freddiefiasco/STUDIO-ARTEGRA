"""The 5.0.2 release text's figures are the shipped planner's (eng:package, the release step).

- README's table of which engine makes which size (Redux, three render sizes, 64 GB and 128 GB PCs) is what planner.plan
  answers at each class's default cap with that class's committed node table, as the service plans once the processor check
  has run.
- The Large-image size limits the text names (about 213 MP on a 64 GB PC, 131 MP on a 128 GB PC) are
  engine/banded_plan.BANDED_PROVEN_MP, and 4x of a 2800 x 3500 render (157 MP) is refused on a 128 GB PC and made on a 64 GB
  one.
- The work-drive figures (about 46 GB at 4x of a 3500 x 2188 render, about 80 GB for an 8x result of about 213 MP) are the
  plans' own.
- The text no longer offers 32,000 px or the 185 GB example: no proof row made either, and this build refuses both.
Sizes only."""
import re
import unittest
from pathlib import Path
from unittest import mock

from engine import banded_plan as B
from engine import planner
from tests.test_plan3_sizing import node_table

ROOT = Path(__file__).resolve().parents[1]
CAPS = {'64 GB': ('pc64', 59.0), '128 GB': ('ws128', 122.2)}
DOCS = ('README.md', 'KNOWN-ISSUES.md', 'CHANGELOG.md', 'docs/RELEASE-NOTES.md', 'docs/FAQ.md', 'docs/TIPS.md',
        'docs/TROUBLESHOOTING.md')


def read(rel):
    return (ROOT / rel).read_text(encoding='utf-8')


def current_section(rel, heading):
    text = read(rel)
    i = text.index(heading)
    j = text.find('\n## ', i + 1)
    return text[i:j if j > 0 else None]


class OnTheNode:
    def __init__(self, mc):
        self.patches = [mock.patch.object(B, 'BXF_TABLE', node_table(mc)), mock.patch.object(B, 'BXF_TABLE_SOURCE', 'committed')]

    def __enter__(self):
        for p in self.patches:
            p.start()

    def __exit__(self, *exc):
        for p in reversed(self.patches):
            p.stop()


def answer(w, h, f, cap):
    p = planner.plan(w, h, f, ram_cap_gb=cap)
    if p.ok and p.engine == 'banded':
        return 'Large-image'
    if p.ok and p.peak_ram_gb <= cap:
        return 'Classic'
    return 'Refused'


class TheReadmeTable(unittest.TestCase):
    def test_every_cell_is_the_planners_answer(self):
        section = current_section('README.md', '## Which engine makes which size')
        rows = re.findall(r'^\| (\d[\d,]*) × (\d[\d,]*) \| (\d+ GB) \| (.+?) \| (.+?) \| (.+?) \| (.+?) \|$', section, re.M)
        self.assertEqual(len(rows), 6)
        for w, h, pc, *cells in rows:
            mc, cap = CAPS[pc]
            with OnTheNode(mc):
                want = [answer(int(w), int(h), f, cap) for f in (2, 4, 6, 8)]
            self.assertEqual(cells, want, (w, h, pc))


class TheNamedLimits(unittest.TestCase):
    def test_the_size_limits_are_the_release_figures(self):
        self.assertEqual(round(B.BANDED_PROVEN_MP['pc64']), 213)
        self.assertEqual(int(B.BANDED_PROVEN_MP['ws128']), 131)
        for rel in ('README.md', 'KNOWN-ISSUES.md', 'CHANGELOG.md', 'docs/RELEASE-NOTES.md', 'docs/FAQ.md'):
            text = read(rel)
            self.assertIn('213 MP', text, rel)
        for rel in ('README.md', 'KNOWN-ISSUES.md', 'CHANGELOG.md', 'docs/RELEASE-NOTES.md', 'docs/FAQ.md'):
            self.assertIn('131 MP', read(rel), rel)

    def test_4x_of_2800_x_3500_is_made_on_64_gb_and_refused_on_128_gb(self):
        with OnTheNode('pc64'):
            self.assertEqual(answer(2800, 3500, 4, 59.0), 'Large-image')
        with OnTheNode('ws128'):
            self.assertEqual(answer(2800, 3500, 4, 122.2), 'Refused')

    def test_the_work_drive_figures_are_the_plans(self):
        with OnTheNode('pc64'):
            four = planner.plan(3500, 2188, 4, ram_cap_gb=59.0)
            eight = planner.plan(1632, 2040, 8, ram_cap_gb=59.0)
        self.assertEqual(round(max(s.disk_gb for s in four.stages)), 46)
        self.assertEqual(round(max(s.disk_gb for s in eight.stages)), 80)
        for rel in ('KNOWN-ISSUES.md', 'docs/TIPS.md'):
            text = read(rel)
            self.assertIn('about 46 GB', text, rel)
            self.assertIn('about 80 GB', text, rel)

    def test_no_text_offers_what_this_build_refuses(self):
        for rel in DOCS:
            text = read(rel)
            self.assertNotIn('32,000 px on the longest side', text, rel)
            self.assertNotIn('185 GB', text, rel)
            self.assertNotIn('no longer spills', text, rel)
        with OnTheNode('pc64'):
            self.assertEqual(answer(3500, 2188, 8, 59.0), 'Refused')
        with OnTheNode('ws128'):
            self.assertEqual(answer(3500, 2188, 8, 122.2), 'Refused')


if __name__ == '__main__':
    unittest.main()
