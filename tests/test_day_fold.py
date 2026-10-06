"""F-103: the markup of the small Day | Week switch and the folded bar (the behaviour is in tests_browser/test_day_fold.py).
The switch sits inside the heading on the week and the day, not on a row of its own; the day also carries a hidden, inert, id-less copy of the heading's buttons as the compact bar
(the day's name, the switch, SOS, map); the week has no such bar; ids stay unique; the script is loaded."""

import re

from tests.test_canvas import azure, rows  # noqa: F401 - fixtures
from tests.test_canvas_pages import added, crew  # noqa: F401 - fixtures
from tests.test_trip_canvas import bare, tag, trip  # noqa: F401 - fixtures


def heading(page):
    m = re.search(r'<header\b[^>]*class="cz-head[^>]*>(.*?)</header>', page, re.S)
    assert m
    return m.group(1)


def test_the_day_switch_is_inside_the_heading_and_not_on_the_kinds_row(trip):
    page = bare(trip.get("/trip/canvas?day=1").text)
    head = heading(page)
    assert 'id="cz-z-day"' in head and 'id="cz-z-week"' in head and 'class="cz-segs cz-toggle"' in head
    bar = re.search(r'<div class="cz-bar">(.*?)</div>', page, re.S).group(1)
    assert "cz-seg" not in bar and "cz-kinds" in bar


def test_the_week_has_the_switch_in_its_heading_and_no_folded_bar(trip):
    page = bare(trip.get("/trip/canvas").text)
    assert 'id="cz-z-week"' in heading(page) and 'aria-current="page"' in tag(page, "cz-z-week")
    assert "cz-fold" not in page


def test_the_day_has_one_hidden_inert_compact_bar_with_the_switch_sos_and_map(trip):
    page = bare(trip.get("/trip/canvas?day=2").text)
    m = re.search(r'(<div\b[^>]*class="cz-fold"[^>]*>)(.*?)<header', page, re.S)
    assert m
    opening, fold = m.groups()
    assert "inert" in opening and 'aria-hidden="true"' in opening                # out of reach until the script shows it
    assert "Sunday" in fold and fold.count('class="cz-seg"') == 2 and "cz-sos" in fold and "cz-mapbtn" in fold and "cz-fold-name" in fold
    assert 'href="/trip/canvas"' in fold and 'data-zoom="out"' in fold and "day=2&amp;sos=1" in fold.replace("&sos", "&amp;sos")
    assert "id=" not in fold                                                    # the copy has no ids: the heading's stay unique
    for ident in ("cz-z-day", "cz-z-week", "cz-sos", "cz-mapbtn", "cz-title"):
        assert page.count(f'id="{ident}"') == 1, ident


def test_the_fold_script_is_loaded_with_the_canvas(trip):
    assert "/assets/js/day_fold.js" in trip.get("/trip/canvas?day=1").text
    assert trip.get("/assets/js/day_fold.js").status_code == 200
