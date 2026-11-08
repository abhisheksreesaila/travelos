"""F-096, F-200: the tab bar and the map button. Map is a small button in the day heading that opens that day's map, not a tab. F-200 (the free-and-polished brief) replaced
F-096's glass: the tab bar (now five tabs: Trip, Plan, Ask in the true centre, Book, Family) and the sheets are opaque, with no glass or blur anywhere; cards and text stay solid."""

import re
from pathlib import Path

from tests.test_booked import trip  # noqa: F401 - fixture
from tests.test_trip_canvas import bare, tag

CSS = Path(__file__).resolve().parent.parent / "assets" / "css"
SUPPORTS = "@supports ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px))) and (color: color-mix(in srgb, red 50%, transparent))"   # needs color-mix too: iOS 15.4–16.1 keep the solid base


def test_the_day_heading_has_a_map_button_that_opens_that_days_map(trip):
    for n in (0, 2):
        a = tag(bare(trip.get(f"/trip/canvas?day={n}").text), "cz-mapbtn")
        assert f'href="/trip/map?day={n}"' in a and 'aria-label="Map of this day"' in a and "data-zoom" not in a
        assert trip.get(f"/trip/map?day={n}").status_code == 200
    assert "cz-mapbtn" not in bare(trip.get("/trip/canvas").text)      # the week has no map button
    assert trip.get("/trip/map").status_code == 200


def test_the_bar_has_no_map_tab_on_any_trip_screen(trip):
    for url in ("/trip/canvas", "/trip/canvas?day=1", "/trip/ask", "/trip/family", "/trip/map"):
        html = trip.get(url).text
        nav = re.search(r'<nav[^>]*class="ph-tabs".*?</nav>', html, re.S).group(0)
        assert len(re.findall(r"<a ", nav)) == 5 and "ph-tab-map" not in nav


def test_the_bar_and_the_sheets_are_opaque_with_no_glass_or_blur():
    for name, sel in (("phone.css", ".ph-tabs"), ("trip_canvas.css", ".cz .cz-sheet"), ("ask_sheet.css", ".ak-sheet")):
        css = (CSS / name).read_text(encoding="utf-8")
        assert "backdrop-filter" not in css and SUPPORTS not in css, name
        rules = re.findall(r"(?:^|[},\s])" + re.escape(sel) + r" \{([^}]*)\}", css)
        assert any("background: var(--card-2)" in r and "var(--sh3)" in r for r in rules), name      # raised and opaque, the strongest shadow


def test_cards_and_text_stay_solid():
    for name in ("phone.css", "trip_canvas.css", "trip.css", "base.css"):
        css = (CSS / name).read_text(encoding="utf-8")
        for rule in re.findall(r"([^{}]+)\{([^{}]*backdrop-filter[^{}]*)\}", css):
            assert not re.search(r"\.(tp-card|tp-row|cz-block|cz-card|bk-sos-row)\b", rule[0]), rule[0]


def test_the_map_starts_with_the_way_back_to_its_day(trip):
    page = bare(trip.get("/trip/map?day=2").text)       # Map has no tab now: the way back is on the page
    assert 'href="/trip/canvas?day=2"' in tag(page, "mp-back") and "Back to" in page
