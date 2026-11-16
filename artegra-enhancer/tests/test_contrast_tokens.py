"""Slider rulers and progress tracks meet WCAG 2.2 SC 1.4.11 (3:1 against their ground): audit items AUD-13 and AUD-17."""
import re
from pathlib import Path

TOKENS = (Path(__file__).resolve().parents[1] / "ui" / "qml" / "creative" / "Tokens.qml").read_text(encoding="utf-8")


def colour(name):
    match = re.search(r"readonly property color " + name + r': "#([0-9A-Fa-f]{6})"', TOKENS)
    assert match, name
    return match.group(1)


def luminance(hex6):
    def channel(v):
        v /= 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(int(hex6[i:i + 2], 16)) for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def test_tracks_reach_three_to_one_on_their_ground():
    assert ratio(colour("trackInk"), colour("ink")) >= 3.0
    assert ratio(colour("trackStage"), colour("stage")) >= 3.0


def test_the_value_tick_and_progress_fill_stay_clear_of_the_track():
    for track in ("trackInk", "trackStage"):
        assert ratio(colour("text1"), colour(track)) >= 3.0
