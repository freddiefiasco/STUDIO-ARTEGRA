"""The release text for the engines (engine design 2.5, 2.10, 3.1; B15).

While it is a draft (this build): the release notes' Engines section offers one variant per proof outcome, every variant keeps
the disclosures, and the known issues, FAQ, tips, troubleshooting and changelog have their engine entries, each inside a
release-draft block, so tools/build_release.py refuses to package them. Once the release step (eng:package) has chosen the
variant from the proof record and removed the markers, the draft tests skip and the finished-text tests run: one variant kept,
the same disclosures, and the text can be packaged."""
import re
from pathlib import Path

import pytest

from tools import build_release

ROOT = Path(__file__).resolve().parents[1]
OPEN, CLOSE = build_release.RELEASE_DRAFT_MARKER, '<!-- /release-draft -->'
DOCS = ('docs/RELEASE-NOTES.md', 'KNOWN-ISSUES.md', 'docs/FAQ.md', 'docs/TIPS.md', 'docs/TROUBLESHOOTING.md', 'CHANGELOG.md')

TIER_0 = ("The Large-image engine runs the same enhancement steps as the Classic engine over the whole image. On our test PCs, "
          "at the sizes both engines can run, its results were pixel-identical to the Classic engine's. It also keeps the "
          "Classic engine's look, including its edge halos.")
VARIANT_WORDS = ("its results were pixel-identical to the Classic engine's",
                 "its results were identical to the Classic engine's except for isolated one-level differences",
                 "its results were judged equal to the Classic engine's at 1:1")
DISCLOSURES = ("small areas the enhancement invented back to the x4 upscaling model's picture",
               "carries the source's broad tones (its low frequencies) into the result",
               'light and dark halos along strong edges of geometry',
               'With Protect on, a large pass no longer spills into shared graphics memory',
               'Finish times now count the work on large inputs and outputs',
               'makes only the sizes the Classic engine cannot make on your computer',
               'up to 32,000 px on the longest side')


def read(rel):
    return (ROOT / rel).read_text(encoding='utf-8')


DRAFTING = any(OPEN in read(rel) for rel in DOCS)
draft_only = pytest.mark.skipif(not DRAFTING, reason='the release text is finished (no release-draft marker remains)')
finished_only = pytest.mark.skipif(DRAFTING, reason='the release text is still a draft')


def drafts(text):
    """The text inside each release-draft block."""
    out, pos = [], 0
    while True:
        i = text.find(OPEN, pos)
        if i < 0:
            return out
        j = text.index(CLOSE, i)
        out.append(text[i:j])
        pos = j + len(CLOSE)


# --- while the text is a draft ------------------------------------------------------------------------------------------

@draft_only
def test_every_engine_entry_is_a_closed_draft_block():
    for rel in DOCS:
        text = read(rel)
        blocks = drafts(text)
        assert blocks, rel
        assert text.count(OPEN) == text.count(CLOSE) == len(blocks), rel
        outside = text
        for b in blocks:
            outside = outside.replace(b, '')
        assert 'Large-image' not in outside, rel                    # nothing about the new engine escapes its draft


@draft_only
def test_draft_text_cannot_be_packaged():
    with pytest.raises(RuntimeError, match='Draft release text'):
        build_release.check_release_text(ROOT)


@draft_only
def test_the_release_notes_offer_one_variant_per_proof_outcome():
    draft = drafts(read('docs/RELEASE-NOTES.md'))[0]
    variants = re.findall(r'^Variant \(([^)]*)\): (.*)$', draft, re.M)
    assert [v[0].split(',')[0] for v in variants] == ['proof tier 0', 'proof tier 1', 'proof tier 2']
    assert variants[0][1].strip() == TIER_0                                         # design 2.5, word for word
    for (label, body), words in zip(variants, VARIANT_WORDS):
        assert words in body, label
        assert 'On our test PCs' in body and 'including its edge halos' in body
    assert 'pixel-identical' not in variants[1][1]
    assert 'identical' not in variants[2][1]
    assert "release owner's approval" in variants[2][0]
    assert 'halo fix' not in draft.lower().replace('there is no halo-fix variant', '').replace('the halo fix is not proven', '')


@draft_only
def test_the_disclosures_every_variant_keeps():
    draft = drafts(read('docs/RELEASE-NOTES.md'))[0]
    for words in DISCLOSURES:
        assert words in draft, words
    assert 'every pixel' not in draft.lower()


@draft_only
def test_the_known_issues_cover_disk_time_halos_small_cards_and_48_gb_pcs():
    block = drafts(read('KNOWN-ISSUES.md'))[0]
    for words in ('free space', 'about 55 GB at 8× of a 3500 × 2188 render', 'can take hours', 'halos',
                  'less than 32 GB of memory have not been tested', 'Setup still needs 64 GB', '48 GB PCs'):
        assert words in block, words
    assert 'about 55 GB' in drafts(read('docs/TIPS.md'))[0]


@draft_only
def test_troubleshooting_quotes_the_engines_own_messages():
    from tests.test_views_strings import listed
    entries = set(listed())
    rows = re.findall(r'^\| (.+?) \| .+ \|$', drafts(read('docs/TROUBLESHOOTING.md'))[0], re.M)
    rows = [r for r in rows if r not in ('Message', '---')]
    assert rows and all(r in entries for r in rows), rows


# --- always -------------------------------------------------------------------------------------------------------------

def test_the_5_0_1_notes_are_kept():
    text = read('docs/RELEASE-NOTES.md')
    assert '# Artegra Enhancer (Beta) 5.0.1 Beta 1' in text
    assert '/releases/download/artegra-enhancer-v5.0.1-beta.1/ArtegraEnhancer-5.0.1b1-Setup.exe' in text


def test_the_55_gb_is_what_the_planner_asks_for():
    from unittest import mock
    from engine import banded_plan, planner
    with mock.patch.dict(banded_plan.BANDED_PROVEN_MP, {'pc64': 2000.0}):
        p = planner.plan(3500, 2188, 8, ram_cap_gb=59.0)
    assert p.engine == 'banded' and round(max(s.disk_gb for s in p.stages)) == 55


# --- once the release step has finished the text ------------------------------------------------------------------------

@finished_only
def test_the_finished_text_can_be_packaged():
    build_release.check_release_text(ROOT)


@finished_only
def test_the_finished_release_notes_keep_one_variant_and_every_disclosure():
    text = read('docs/RELEASE-NOTES.md')
    assert 'Variant (' not in text
    assert sum(words in text for words in VARIANT_WORDS) == 1
    for words in DISCLOSURES:
        assert words in text, words
