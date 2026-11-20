"""5.0.2: the engine named plainly (engine design sections 2.10 and 3.1, D3), in the plan card, the plan answers, the input
list's scales and the result's sidecar, with measured facts only (which engine, the time, the output size, the disk space and
the memory class), and never a claim the build cannot back ("every pixel is generated", "identical" as a promise about the
person's computer). Sizes only; the /api/plan handler with stubs, as tests/test_memory_api.py builds them."""
import re
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from engine import banded_plan, planner
from service import banded_runner, media, naming
from service.api import _Handler
from service.errors import ApiError
from service.runner import Runner

ROOT = Path(__file__).resolve().parents[1]
PROVEN = {'ws128': 2000.0, 'pc64': 2000.0, 'pc48': 2000.0}
CAP = 59.0


@pytest.fixture
def proven():
    with mock.patch.dict(banded_plan.BANDED_PROVEN_MP, PROVEN):
        yield


def plan_handler(body, cap=CAP, check=None):
    """The real POST /api/plan handler and the real Runner.plan_check, on stubs (no service process)."""
    runner = SimpleNamespace(settings=SimpleNamespace(get=lambda: {'ram_cap_gb': cap, 'memory_profile': 'auto', 'gpus': []}),
                             finish_info=lambda minutes, plan=None: {'standard': {'minutes': minutes, 'factor': 1.0}},
                             memory_info=lambda: {'profiles': []}, _check_mode=mock.Mock(), _lock=threading.RLock())
    runner.plan_check = check or (lambda p: Runner.plan_check(runner, p))
    h = object.__new__(_Handler)
    h.app = SimpleNamespace(runner=runner, media=None)
    h._body = lambda: body
    h._json = mock.Mock()
    return h


def answer(body, **kw):
    h = plan_handler(body, **kw)
    h.r_plan({})
    status, out = h._json.call_args.args
    assert status == 200
    return out


class TestPlanCard:
    def test_a_classic_plan_names_the_classic_engine_and_keeps_its_plan_keys(self):
        p = planner.plan(3500, 2188, 2, ram_cap_gb=CAP)
        text = media.plan_text(p, CAP)
        assert text['engine'] == media.ENGINE_CLASSIC == 'Engine: Classic'
        assert 'disk' not in text and 'memory_class' not in text
        assert 'engine' not in p.to_dict()                    # 5.0.1's plan dict, key for key (G0a)

    def test_a_large_image_plan_names_its_engine_and_its_measured_facts(self, proven):
        p = planner.plan(3500, 2188, 8, ram_cap_gb=CAP)
        assert (p.ok, p.engine) == (True, 'banded')
        text = media.plan_text(p, CAP)
        assert text['engine'] == 'Engine: Large-image (this size is beyond the Classic engine on this computer)'
        assert text['output'] == '28,000 × 17,504 px (490.1 MP)'
        assert text['disk'] == f'about {max(s.disk_gb for s in p.stages):.0f} GB free disk space for the work files'
        assert text['memory_class'] == 'Memory class: 64 GB PC'
        assert text['eta'].startswith('about ')
        assert not any('halo' in n.lower() for n in text['notes'])      # bxf-1 keeps the Classic look: no halo line
        assert p.banded['finish'] == 'bxf-1' and banded_plan.FINISH_VARIANTS == ('bxf-1',)

    def test_the_halo_line_appears_only_for_a_ported_fix(self, proven):
        p = planner.plan(3500, 2188, 8, ram_cap_gb=CAP)
        p.banded = dict(p.banded, finish='bxf-1h')
        assert media.ENGINE_HALO_NOTE in media.plan_text(p, CAP)['notes']

    def test_a_forced_comparison_plan_says_so(self, proven):
        classic = planner.plan(3500, 2188, 2, ram_cap_gb=CAP)
        forced = banded_plan.plan_forced(classic, CAP)
        assert media.plan_text(forced, CAP)['engine'] == media.ENGINE_LARGE_FORCED

    def test_a_refused_plan_names_no_engine(self):
        p = planner.plan(3500, 2188, 8, ram_cap_gb=CAP)          # nothing is proven in this build: 5.0.1's refusal
        assert not p.ok
        assert 'engine' not in media.plan_text(p, CAP)
        d = media.plan_dict(p, CAP)
        assert d['executor'] is None and 'engine' not in d

    def test_the_input_lists_scales_say_which_engine(self, proven):
        sc = media.scales_for(3500, 2188, CAP)
        assert sc['2']['executor'] == 'classic' and sc['2']['text']['engine'] == media.ENGINE_CLASSIC
        assert sc['8']['executor'] == 'large-image' and sc['8']['text']['engine'] == media.ENGINE_LARGE

    def test_refused_scales_name_no_engine(self):
        sc = media.scales_for(3500, 2188, CAP)                  # nothing proven: 8x is 5.0.1's refusal
        assert sc['8']['ok'] is False and sc['8']['executor'] is None and 'engine' not in sc['8']['text']


class TestPlanAnswer:
    def test_classic(self):
        out = answer({'width': 3500, 'height': 2188, 'scale': 2})
        assert out['ok'] and out['executor'] == 'classic'
        assert 'engine' not in out                            # the plan's own keys stay 5.0.1's
        assert out['text']['engine'] == media.ENGINE_CLASSIC

    def test_large_image(self, proven):
        out = answer({'width': 3500, 'height': 2188, 'scale': 8})
        assert out['ok'] and out['engine'] == 'banded' and out['executor'] == 'large-image'
        assert out['text']['engine'] == media.ENGINE_LARGE
        assert out['output_size'] == [28000, 17504]

    def test_refused_for_size_or_memory(self):
        out = answer({'width': 3500, 'height': 2188, 'scale': 8})
        assert not out['ok'] and out['executor'] is None and 'engine' not in out['text']
        out = answer({'width': 3500, 'height': 2188, 'scale': 2}, cap=20.0)
        assert not out['ok'] and out['executor'] is None

    def test_a_refusal_from_plan_check_names_no_engine(self):
        """The Classic engine's graphics-memory pre-check (the admission package's) refuses through Runner.plan_check."""
        def check(p):
            d = media.plan_dict(p, CAP)
            d.update(ok=False, reason='This image needs about 30 GB of graphics memory with the Classic engine; '
                                      'this card has 12 GB.')
            return d
        out = answer({'width': 3500, 'height': 2188, 'scale': 2}, check=check)
        assert out['executor'] is None and 'engine' not in out['text']

    def test_bad_requests_are_still_refused(self):
        with pytest.raises(ApiError):
            answer({'width': 3500, 'height': 2188, 'scale': 3})


class TestSidecarAndQueue:
    def test_the_sidecar_names_the_large_image_engine(self, proven):
        p = planner.plan(3500, 2188, 8, ram_cap_gb=CAP)
        fields = banded_runner.sidecar_fields(p.to_dict())
        assert fields['executor'] == 'large-image' and fields['finish'] == 'bxf-1' and fields['halo_fix'] is None
        assert naming.engine_of(p.to_dict()) == 'large-image'

    def test_a_record_without_an_engine_key_is_classic(self):
        assert naming.engine_of({'output_size': [7000, 4376], 'stages': []}) == 'classic'
        assert naming.engine_of({}) == 'classic'
        assert naming.engine_label({'engine': 'banded'}) == 'Large-image'
        assert naming.engine_label({'executor': 'classic', 'engine': 'banded'}) == 'Classic'   # the answer's own word wins
        assert naming.ENGINE_LABELS == {'classic': 'Classic', 'large-image': 'Large-image'}
        assert naming.memory_class_label('pc48') == '48 GB' and naming.memory_class_label(None) == ''


# --- copy: no claim the build cannot back -------------------------------------------------------------------------------

COPY_FILES = ['README.md', 'KNOWN-ISSUES.md', 'CHANGELOG.md'] + [f'docs/{n}' for n in (
    'RELEASE-NOTES.md', 'STRINGS.md', 'FAQ.md', 'TIPS.md', 'TROUBLESHOOTING.md', 'COMPATIBILITY.md')]
EVERY_PIXEL = re.compile(r'(?i)every\s+(?:output\s+)?pixel\s+is\s+(?:generated|enhanced|made)')
ENGINE_WORD = re.compile(r'(?i)\b(?:engine|classic|large-image)\b')


def copy_texts():
    from tests.test_mode_names import js_literals, py_literals
    out = []
    for rel in COPY_FILES:
        p = ROOT / rel
        if p.is_file():
            out.append((rel, p.read_text(encoding='utf-8')))
    for p in sorted((ROOT / 'service').glob('*.py')) + sorted((ROOT / 'host').glob('*.py')):
        out += [(p.name, s) for s in py_literals(p.read_text(encoding='utf-8'))]
    for p in sorted((ROOT / 'ui').rglob('*.qml')) + sorted((ROOT / 'ui').rglob('*.js')):
        out += [(p.name, lit) for kind, lit in js_literals(p.read_text(encoding='utf-8')) if kind == 'string']
    return out


def sentences(text):
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+|\n\s*\n|\n[-*|] ', text) if s.strip()]


def test_no_copy_says_every_pixel_is_generated():
    found = [(name, m.group(0)) for name, text in copy_texts() for m in EVERY_PIXEL.finditer(text)]
    assert found == []


def test_identical_about_the_engines_is_said_only_of_our_test_pcs():
    """'Identical' may describe two identical graphics cards or a duplicate file, and the release text's tier-0 and tier-1
    variants (engine design 2.5) may say what was measured "On our test PCs". It is never a promise about the person's own
    computer: in 5.0.2 the two engines never run the same plan for a person."""
    bad = []
    for name, text in copy_texts():
        for s in sentences(text):
            if 'identical' not in s.lower() or not ENGINE_WORD.search(s):
                continue
            if re.search(r'(?i)identical (?:RTX|desktop|graphics|cards?)|two identical', s):
                continue
            if 'On our test PCs' in s or re.search(r'(?i)never .{0,40}"?identical', s):
                continue
            bad.append((name, s[:160]))
    assert bad == []


def test_the_scan_finds_what_it_looks_for():
    assert EVERY_PIXEL.search('Every pixel is generated by the enhancer.')
    assert [s for s in sentences('One. Two engines give identical results! Three') if 'identical' in s]
