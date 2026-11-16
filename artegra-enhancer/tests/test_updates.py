"""Check for updates: recorded GitHub answers, the version order, the request and every failure path. No network."""
import http.client
import io
import json
import ssl
import urllib.error
from pathlib import Path

import pytest

from host import updates
from host.config import VERSION

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "github-releases"


def answer(name):
    return (FIXTURES / name).read_bytes()


def test_the_beta_is_up_to_date_against_todays_list():
    result = updates.check(answer=answer("as-of-2026-11-17.json"))
    assert result["state"] == "current"
    assert result["message"] == "Artegra Enhancer (Beta) 5.0.0 Beta 1 is up to date."


def test_a_newer_beta_is_offered_with_its_release_page():
    result = updates.check(answer=answer("with-beta-2.json"))
    assert result == {"state": "available", "message": "Artegra Enhancer (Beta) 5.0.0 Beta 2 is available.",
                      "latest": "5.0.0-beta.2",
                      "url": "https://github.com/freddiefiasco/STUDIO-ARTEGRA/releases/tag/artegra-enhancer-v5.0.0-beta.2"}


def test_drafts_foreign_tags_and_unparsable_versions_are_skipped_and_a_foreign_link_is_not_used():
    latest, url = updates.newest_release(json.loads(answer("draft-and-foreign.json")))
    assert latest == "5.0.0-beta.1"
    assert url == "https://github.com/freddiefiasco/STUDIO-ARTEGRA/releases/tag/artegra-enhancer-v5.0.0-beta.1"


def test_an_older_alpha_never_reads_as_an_update():
    assert updates.check(answer=answer("alpha-4-only.json"))["state"] == "current"


@pytest.mark.parametrize("data", [answer("empty.json"), answer("malformed.json"), b"", b"{}", b"null",
                                  json.dumps([{"tag_name": 5}]).encode()])
def test_answers_without_a_release_fail_plainly(data):
    result = updates.check(answer=data)
    assert result == {"state": "failed", "message": "Couldn't reach GitHub. Check your connection and try again.",
                      "latest": "", "url": ""}


def test_version_order():
    order = ["0.1.0-alpha.4", "5.0.0-beta.1", "5.0.0-beta.2", "5.0.0-beta.10", "5.0.0-rc.1", "5.0.0", "5.0.1-alpha.1"]
    keys = [updates.parse_version(v) for v in order]
    assert keys == sorted(keys) and len(set(keys)) == len(keys)
    assert updates.parse_version("5.0.0-nightly.1") is None and updates.parse_version("v5.0.0") is None


def test_display_names():
    assert updates.display_version("5.0.0-beta.2") == "5.0.0 Beta 2"
    assert updates.display_version("5.0.0-rc.1") == "5.0.0 Release candidate 1"
    assert updates.display_version("5.0.0-alpha.4") == "5.0.0 Alpha 4"
    assert updates.display_version("5.0.0") == "5.0.0"
    assert updates.display_version(VERSION) == "5.0.0 Beta 1"


def test_the_request_names_the_app_and_nothing_else():
    request = updates.build_request()
    assert request.full_url == "https://api.github.com/repos/freddiefiasco/STUDIO-ARTEGRA/releases?per_page=50"
    assert request.get_method() == "GET" and request.data is None
    headers = {k.lower(): v for k, v in request.header_items()}
    assert headers == {"user-agent": "ArtegraEnhancer/" + VERSION, "accept": "application/vnd.github+json",
                       "x-github-api-version": "2022-11-28"}


class FakeResponse(io.BytesIO):
    def __init__(self, data, status=200):
        super().__init__(data)
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class FakeOpener:
    def __init__(self, outcome):
        self.outcome = outcome
        self.requests = []

    def open(self, request, timeout=None):
        self.requests.append((request, timeout))
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


def test_fetch_uses_one_request_with_the_ten_second_limit():
    opener = FakeOpener(FakeResponse(answer("with-beta-2.json")))
    result = updates.check(opener=opener)
    assert result["state"] == "available"
    (request, timeout), = opener.requests
    assert timeout == 10.0 and request.full_url.startswith("https://api.github.com/")


class CutOffResponse(FakeResponse):
    """An answer that stops part-way through the body, as a proxy, a captive portal or a dropped line can leave it."""

    def read(self, size=-1):
        raise http.client.IncompleteRead(b"[{\"tag_name\": \"artegra-enh", 4096)


@pytest.mark.parametrize("outcome", [
    urllib.error.HTTPError(updates.API_URL, 403, "rate limited", {}, None),
    urllib.error.HTTPError(updates.API_URL, 500, "server error", {}, None),
    urllib.error.URLError("no route"),
    TimeoutError("slow"),
    ssl.SSLError("bad certificate"),
    ConnectionResetError("reset"),
    FakeResponse(b"[]", status=204),
    # http.client's own errors are not OSErrors: a proxy or captive portal answering in a way HTTP does not allow.
    http.client.BadStatusLine("garbage"),
    http.client.LineTooLong("header line"),
    http.client.IncompleteRead(b"["),
    http.client.RemoteDisconnected("closed"),
    CutOffResponse(b""),
    RuntimeError("anything else"),
], ids=lambda outcome: type(outcome).__name__)
def test_network_failures_say_one_plain_sentence(outcome):
    result = updates.check(opener=FakeOpener(outcome))
    assert result == updates.failed()
    assert result["message"] == "Couldn't reach GitHub. Check your connection and try again."


def test_an_oversized_answer_is_refused():
    big = b"[" + b" " * (3 * 1024 * 1024) + b"]"
    assert updates.check(opener=FakeOpener(FakeResponse(big)))["state"] == "failed"


def test_a_slow_answer_is_cut_off_by_the_overall_deadline():
    ticks = iter([0.0, 11.0, 12.0, 13.0])
    with pytest.raises(TimeoutError):
        updates.fetch(FakeOpener(FakeResponse(b"[]")), clock=lambda: next(ticks))


def test_redirects_leave_only_for_the_releases_api():
    handler = updates._SameHostRedirect()
    with pytest.raises(updates.UpdateError):
        handler.redirect_request(updates.build_request(), None, 301, "moved", {}, "http://api.github.com/x")
    with pytest.raises(updates.UpdateError):
        handler.redirect_request(updates.build_request(), None, 301, "moved", {}, "https://example.invalid/x")


def test_starting_the_app_makes_no_update_request():
    host = Path(__file__).resolve().parents[1] / "host"
    calls = {path.name: path.read_text(encoding="utf-8").count("updates.check(") for path in host.glob("*.py")}
    # The check runs only from UpdateBridge (a button); nothing at start-up calls it.
    assert {name: n for name, n in calls.items() if n} == {"updates_qt.py": 1}
    bridge = (host / "updates_qt.py").read_text(encoding="utf-8")
    assert "def check(self):" in bridge and "from host.updates_qt import UpdateBridge" in (host / "app.py").read_text(encoding="utf-8")
    main_qml = (Path(__file__).resolve().parents[1] / "ui" / "qml" / "Main.qml").read_text(encoding="utf-8")
    assert main_qml.count("updateBridge.check()") == 1
    assert "onClicked: updateBridge.check()" in main_qml
