"""F-096: three tabs and a touch of glass. The tab bar is Today, Ask, Family (Ask in the true centre); Map is a small button in the day heading that opens that day's map;
the tab bar and the sheets are glass only where the browser can blur, solid under prefers-reduced-transparency; cards and text stay solid."""

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
        assert len(re.findall(r"<a ", nav)) == 3 and "ph-tab-map" not in nav


def blocks(css, opener):
    """The text of every top-level rule or at-rule block that starts with `opener`."""
    out, i = [], 0
    while (i := css.find(opener, i)) != -1:
        depth, j = 0, css.index("{", i)
        k = j
        while True:
            depth += (css[k] == "{") - (css[k] == "}")
            if depth == 0:
                break
            k += 1
        out.append(css[j + 1:k])
        i = k
    return out


def test_glass_only_where_the_browser_can_blur_and_solid_when_asked(  ):
    for name, sel in (("phone.css", ".ph-tabs"), ("trip_canvas.css", ".cz .cz-sheet")):
        css = (CSS / name).read_text(encoding="utf-8")
        glass = " ".join(blocks(css, SUPPORTS))
        assert sel in glass and "backdrop-filter: blur(1.25rem)" in glass and "color-mix" in glass
        outside = css
        for b in blocks(css, SUPPORTS):
            outside = outside.replace(b, "")
        assert not re.search(re.escape(sel) + r"[^{]*\{[^}]*backdrop-filter: blur", outside)      # no blur on the base rule
        reduced = " ".join(blocks(css, "@media (prefers-reduced-transparency: reduce)"))
        assert sel in reduced and "backdrop-filter: none" in reduced and "var(--card)" in reduced


def test_cards_and_text_stay_solid():
    for name in ("phone.css", "trip_canvas.css", "trip.css", "base.css"):
        css = (CSS / name).read_text(encoding="utf-8")
        for rule in re.findall(r"([^{}]+)\{([^{}]*backdrop-filter[^{}]*)\}", css):
            assert not re.search(r"\.(tp-card|tp-row|cz-block|cz-card|bk-sos-row)\b", rule[0]), rule[0]


def test_the_map_starts_with_the_way_back_to_its_day(trip):
    page = bare(trip.get("/trip/map?day=2").text)       # Map has no tab now: the way back is on the page
    assert 'href="/trip/canvas?day=2"' in tag(page, "mp-back") and "Back to" in page
