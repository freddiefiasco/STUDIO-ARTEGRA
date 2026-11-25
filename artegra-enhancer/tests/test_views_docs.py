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
               'up to 32,000 px on the longest side',
               'It still needs more memory for larger outputs')
CARDS_PLACEHOLDER = '<the graphics cards from the proof record>'          # KNOWN-ISSUES; the release step fills it (S6)

# The Large-image engine's memory grows with the output (engine/banded_plan.py stage_peaks: the sampler state per render
# pixel, the X_up term per render MP and the finish terms per output pixel), so no text may say that it follows the band, the
# chunk or the tile rather than the image (Max's rule: nothing dressed up as more than it is).
_UNIT = r'(?:bands?|chunks?|tiles?|strips?|windows?)'
_DEPENDS = (r'(?:follows?|track(?:s|ed)?|depends?(?: only)? on|scales? with|(?:is |are )?set by|(?:is |are )?bounded by|'
            r'(?:is |are )?capped by|(?:is |are )?limited (?:by|to)|stays? (?:within|inside))')
_MEMORY_CLAIMS = (
    re.compile(rf'\bmemory\b.*\b{_DEPENDS}\b.*\b{_UNIT}\b'),                       # memory follows the band
    re.compile(rf'\b{_UNIT}\b.*\b(?:sets?|bounds?|caps?|limits?|decides?)\b.*\bmemory\b'),   # the tile sets the memory
    re.compile(rf'\bmemory\b.*\b{_UNIT}\b.*\b(?:rather than|instead of|not)\b.*\b(?:whole|entire|full)\b'),
    re.compile(rf'\b{_UNIT}\b.*\b(?:rather than|instead of|not)\b.*\b(?:whole|entire|full)\b.*\bmemory\b'),
    re.compile(r"\bmemory\b.*\b(?:does not|doesn't|never|no longer|will not|won't)\b \w*\s?(?:grow|increase|rise|depend|scale)"),
    re.compile(r'\bmemory\b.*\b(?:independent of|regardless of|whatever|no matter)\b.*\b(?:size|image|output|resolution)'),
    re.compile(r"\b(?:does not|doesn't|never|no longer|will not|won't) (?:need|use|take)s? (?:any )?more\b.*\bmemory\b.*"
               r'\b(?:larger|bigger)\b'),
)


def memory_follows_the_band(text):
    """The sentences of `text` that say memory follows the band (or chunk, tile) rather than the image."""
    sentences = re.split(r'(?<=[.!?])\s+|\n+', text.replace('**', ''))
    return [s for s in sentences if 'memory' in s.lower() and any(p.search(s.lower()) for p in _MEMORY_CLAIMS)]


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
    for words in ('free space', 'about 185 GB at 8× of a 3500 × 2188 render', 'can take hours', 'halos',
                  'Setup still needs 64 GB', '48 GB PCs'):
        assert words in block, words
    # V4: the small cards are named and nothing implies a card was tested that no proof record shows (eng:package adds the
    # cards tested from the proof record)
    assert 'runs only on graphics cards with 12 GB of memory or more' in block
    assert not re.search(r'less than \d+ GB of memory have not been tested', block)
    assert not re.search(r'(?i)tested on (?:the )?RTX', block)
    assert 'about 185 GB' in drafts(read('docs/TIPS.md'))[0]


@draft_only
def test_the_known_issues_keep_a_place_for_the_cards_the_proof_ran():
    """S6: the draft no longer says which cards the Large-image engine ran on, so it keeps an explicit placeholder that the
    release step fills from the proof record ('run on', never 'tested')."""
    block = drafts(read('KNOWN-ISSUES.md'))[0]
    assert CARDS_PLACEHOLDER in block
    assert not re.search(r'(?i)\btested\b', block)


# The start-up probe and the fresh engine between passes (build wave 3; contracts.g1u and contracts.restart). The minutes are
# the finish package's G1u timings on our test PC's processor (fin-fix-g1u-rt: 1,338 s and 1,510 s), not a bound for every
# computer: the only bound is the service's own deadline, so no text says "up to N minutes" (and none repeats the design's
# guess of a minute or two).
G1U_SECONDS = (1338, 1510)
PROBE_MINUTES = 'about 22 to 25 minutes'
PROBE_DOCS = ('docs/RELEASE-NOTES.md', 'KNOWN-ISSUES.md', 'docs/TIPS.md', 'docs/TROUBLESHOOTING.md', 'docs/FAQ.md')


def engine_start_section():
    text = read('docs/STRINGS.md')
    i = text.index('### Engine start and the start-up probe')
    return text[i:text.index('\n### ', i + 1)]


@draft_only
def test_the_drafts_say_what_the_start_up_probe_is():
    assert PROBE_MINUTES == f'about {round(G1U_SECONDS[0] / 60)} to {round(G1U_SECONDS[1] / 60)} minutes'
    for rel in PROBE_DOCS:
        block = ' '.join(drafts(read(rel)))
        assert 'first Large-image image' in block and 'processor' in block, rel     # what it measures, and when
        assert 'measured before this release' in block, rel                         # not where a committed table applies
        assert 'waits' in block, rel                                                # the image waits for it
        assert PROBE_MINUTES in block and 'slower' in block, rel                    # ours, and longer on a slower one
        assert not re.search(r'(?i)\bup to (?:about )?\d+ ?min', block), rel
        assert not re.search(r'(?i)a minute or two|\b1[-– ]?(?:to )?2 min', block), rel


@draft_only
def test_the_drafts_say_a_large_image_upscale_may_restart_the_engine():
    for rel in PROBE_DOCS:
        block = ' '.join(drafts(read(rel)))
        assert re.search(r'restarts? the image engine between passes', block), rel
        assert 'estimated time' in block, rel                                       # its minutes are in the estimate


def test_the_engine_start_section_describes_the_wired_probe():
    section = engine_start_section()
    assert 'does not run the probe yet' not in section and 'comes later' not in section
    assert 'before its first Large-image image' in section and 'waits' in section
    assert 'no table in the app covers' in section


@draft_only
def test_the_recorded_copy_findings_are_acted_on():
    """S4 (wp/2-service/copy-review-1.txt and -2.txt): the findings in this package's release text."""
    every = ' '.join(b for rel in DOCS for b in drafts(read(rel)))
    assert 'keeps its sizes' not in every                                          # 'Bolt keeps its sizes' was unclear
    assert 'as 5.0.1 does' not in every                                            # the Large-image engine is new
    assert not re.search(r'gives the time\b', every)                               # the time is an estimate
    assert 'Its plan gives the estimated time' in drafts(read('docs/TIPS.md'))[0]
    assert 'Bolt stays on the Classic engine' in drafts(read('KNOWN-ISSUES.md'))[0]
    # The queue row's tag is the last field of its line, which the row drops when it does not fit (CuListRow.fitFields),
    # so no draft says that the row always names the engine, and the known issues say where it is always named.
    assert not re.search(r"(?i)(?:the image's row|its row in the list)(?: and| say| name)", every)
    assert 'names its engine only when the row has room' in drafts(read('KNOWN-ISSUES.md'))[0]
    # STRINGS' intro (both reviews, rules 1 and 2): no promise of 5.0.1's pixels; the identity tests check the graphs
    intro = read('docs/STRINGS.md').split('## Engines (5.0.2)')[1].split('###')[0]
    assert 'its pixels' not in intro and 'graphs' in intro
    # and the release notes' own version of it (rule 2: no promise of the same result on the person's computer)
    notes = drafts(read('docs/RELEASE-NOTES.md'))[0]
    assert 'the same pixels' not in notes and 'the same passes and settings as 5.0.1' in notes


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


def test_the_disk_figure_is_what_the_planner_asks_for():
    from unittest import mock
    from engine import banded_plan, planner
    # 8x of 3500 x 2188 is a 490 MP pass: planned with the banded finish counted (contract finish_tier, build wave 2). Since
    # build wave 3 it runs on a 128 GB computer only (the refit refuses it on a 64 GB PC), and its third pass's folder counts
    # the finish's measured work disk, 310 B per finish-plane pixel (banded_plan.DISK_O): 185 GB, up from 55
    with mock.patch.dict(banded_plan.BANDED_PROVEN_MP, {'ws128': 2000.0}),             mock.patch.object(banded_plan, 'BXF_AVAILABLE', True, create=True):
        p = planner.plan(3500, 2188, 8, ram_cap_gb=122.2)
    assert p.engine == 'banded' and round(max(s.disk_gb for s in p.stages)) == 185


CLAIMED = ("It works on the image in bands, kept in work files on the work drive, so the memory it needs follows the band "
           "rather than the whole image.",
           'Its memory follows the chunk, not the whole picture.',
           'Memory use depends on the tile size, not the image size.',
           'The memory it needs does not grow with the image.',
           'It needs the same memory whatever the output size.',
           'It does not need more memory for larger images.')
HONEST = ('It works on the image in bands and keeps the image in work files on the work drive.',
          "It still needs more memory for larger outputs, and a size that does not fit this computer's memory is refused "
          'before it starts.',
          'On cards with 24 GB or less, Auto turns on **Save GPU memory**, which processes one tile at a time and loads '
          'models through system memory.',
          'Save GPU memory keeps the original tile sizes and numerical options.',
          'With Protect on, a large pass no longer spills into shared graphics memory: above about 33 MP the protected '
          'areas are found by a step that enlarges only the masks it keeps, using far less graphics memory.')


def test_the_memory_check_finds_the_claim_and_passes_honest_text():
    for s in CLAIMED:
        assert memory_follows_the_band(s), s
    for s in HONEST:
        assert not memory_follows_the_band(s), s


def test_no_text_says_the_memory_follows_the_band_rather_than_the_image():
    for rel in DOCS + ('docs/STRINGS.md',):                       # draft and finished text alike, the whole file
        assert memory_follows_the_band(read(rel)) == [], rel


def test_larger_outputs_need_more_memory_as_the_release_notes_say():
    """The release notes' memory sentence is the planner's: on the 128 GB workstation the Large-image plan's memory rises
    with the output (276, 490 and 1,024 MP), and on a 64 GB PC a 32,000 x 32,000 px result does not fit and is refused
    before it starts (5.0.1's own refusal is the answer)."""
    from unittest import mock
    from engine import banded_plan, planner
    proven = {'ws128': 2000.0, 'pc64': 2000.0, 'pc48': 2000.0}
    with mock.patch.dict(banded_plan.BANDED_PROVEN_MP, proven),             mock.patch.object(banded_plan, 'BXF_AVAILABLE', True, create=True):   # above 300 MP: the banded finish counted
        plans = [planner.plan(w, h, f, ram_cap_gb=122.2) for w, h, f in ((3500, 2188, 6), (3500, 2188, 8), (4000, 4000, 8))]
        assert all(p.ok and p.engine == 'banded' for p in plans)
        outputs = [p.output_size[0] * p.output_size[1] / 1e6 for p in plans]
        peaks = [p.peak_ram_gb for p in plans]
        assert outputs == sorted(outputs) and peaks == sorted(peaks) and peaks[-1] > 1.5 * peaks[0], (outputs, peaks)
        q = banded_plan.plan_banded(4000, 4000, 8, 59.0, proven=proven)
        assert not q.ok and 'GB of memory with the Large-image engine' in q.reason
        assert not planner.plan(4000, 4000, 8, ram_cap_gb=59.0).ok


# --- once the release step has finished the text ------------------------------------------------------------------------

@finished_only
def test_the_finished_text_can_be_packaged():
    build_release.check_release_text(ROOT)


@finished_only
def test_the_finished_text_keeps_no_placeholder():
    """The release step fills every <placeholder> of the draft (the size classes of tier 2, the cards the proof ran)."""
    left = []
    for rel in DOCS:
        text = re.sub(r'<!--.*?-->', '', read(rel), flags=re.S)
        text = re.sub(r'`[^`\n]*`', '', text)
        text = re.sub(r'</?(?:img|a|br|p|sup|sub)\b[^<>]*>', '', text)
        left += [(rel, m) for m in re.findall(r'<[^<>\n]+>', text)]
    assert left == []
    assert CARDS_PLACEHOLDER not in read('KNOWN-ISSUES.md')


@finished_only
def test_the_finished_release_notes_keep_one_variant_and_every_disclosure():
    text = read('docs/RELEASE-NOTES.md')
    assert 'Variant (' not in text
    assert sum(words in text for words in VARIANT_WORDS) == 1
    for words in DISCLOSURES:
        assert words in text, words
