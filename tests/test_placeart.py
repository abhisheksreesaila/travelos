"""F-223: the place art, one drawn set of ten (docs/design/trip-matrix/art.js), as inline SVG the matrix and the trip can show."""
import re
from pathlib import Path

import pytest

from gitaway import placeart
from gitaway.partners import places

CSS = Path(__file__).resolve().parent.parent / "assets" / "css" / "placeart.css"


def test_there_are_ten_and_every_one_is_a_place_in_the_table():
    assert len(placeart.SLUGS) == 10
    for slug in placeart.SLUGS:
        place = places.resolve(placeart.name(slug))
        assert place.known and place.slug == slug, slug


@pytest.mark.parametrize("slug", placeart.SLUGS)
def test_each_drawing_is_safe_inline_svg_with_its_own_night(slug):
    day, night = placeart.art(slug), placeart.art(slug, night=True)
    for svg in (day, night):
        assert svg.startswith("<svg ") and svg.endswith("</svg>")
        assert "<script" not in svg.lower() and not re.search(r"\bon\w+=", svg)
        assert not re.search(r"(href|src)=\"(?!#)", svg) and "http" not in svg.replace("http://www.w3.org/2000/svg", "")
        assert "<text" not in svg and "<image" not in svg      # no words and no photos in a drawing
        assert "var(--pa-sky1)" in svg and 'role="img"' in svg and 'aria-label="' in svg
    assert day != night
    sky = lambda svg: re.search(r"--pa-sky1:(#[0-9A-F]{6})", svg).group(1)
    assert sky(day) != sky(night)


def test_the_day_drawing_follows_the_mode_and_a_night_one_stays_night():
    day, night = placeart.art("sandiego"), placeart.art("sandiego", night=True)
    assert 'data-sky="auto"' in day and "--pa-n-sky1:" in day
    assert 'data-sky="night"' in night and "--pa-n-sky1:" not in night
    css = CSS.read_text(encoding="utf-8")
    assert ':root[data-mode="dark"] .pa-svg[data-sky="auto"]' in css and "prefers-color-scheme: dark" in css
    for var in placeart.VARS:
        assert f"--pa-{var}: var(--pa-n-{var}) !important" in css, var


def test_names_dashes_and_case_all_find_the_same_drawing():
    assert placeart.kind("San Diego") == placeart.kind("san-diego") == placeart.kind("sandiego") == "beach"
    assert placeart.art("Lake Tahoe") is not None


def test_a_place_without_art_gets_none_so_the_page_shows_its_plain_tint():
    assert placeart.art("boise") is None and placeart.kind("boise") is None
    assert placeart.art("") is None and placeart.kind(None) is None


def test_kinds():
    assert {s: placeart.kind(s) for s in placeart.SLUGS} == {
        "sandiego": "beach", "losangeles": "city", "newyork": "city", "laketahoe": "snow", "orlando": "park", "palmsprings": "desert",
        "santabarbara": "beach", "orangecounty": "beach", "honolulu": "beach", "yosemite": "hike"}


def test_new_york_has_the_statue_and_tahoe_has_pines_and_snow():
    assert "Statue of Liberty" in placeart.art("newyork")
    tahoe = placeart.art("laketahoe")
    assert "Pines" in tahoe and tahoe.count("var(--pa-snow)") >= 5


def test_the_weather_layer_is_drawn_only_when_asked_and_rain_hides_the_sun():
    plain = placeart.art("laketahoe")
    assert "pa-wx" not in plain
    rain = placeart.art("laketahoe", wx="rain")
    assert 'class="pa-rn"' in rain and re.search(r'class="pa-sun" style="[^"]*opacity:0\b', rain)
    with pytest.raises(ValueError):
        placeart.art("laketahoe", wx="hail")


def test_two_drawings_on_one_page_never_share_a_gradient():
    ids = re.findall(r'<linearGradient id="([^"]+)"', placeart.art("orlando") + placeart.art("orlando", night=True))
    assert len(ids) == len(set(ids)) == 2


def test_motion_only_moves_and_stops_under_reduced_motion():
    css = CSS.read_text(encoding="utf-8")
    assert "prefers-reduced-motion: reduce" in css
    assert not re.search(r"(?<![\w.-])\d*\.?\d+m?s\b", re.sub(r"/\*.*?\*/", "", css, flags=re.S)), "times come from the --motion-* tokens"


def test_the_preview_shows_every_drawing_on_the_showcase_and_is_gone_in_production(client, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "1")
    r = client.get("/dev/placeart")
    assert r.status_code == 200 and r.text.count('class="pa-svg"') == 2 * len(placeart.SLUGS) + len(placeart.WX) + 1   # and the Tahoe strip wears its own
    assert "Typical, not a forecast yet" in r.text and "No weather for this place yet" in r.text
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    assert client.get("/dev/placeart").status_code == 404
