"""F-164: at 721 to 1019px the day and week heading controls (Day | Week switch, SOS, map, filter chips, the Trip menu, the way back) have text of at least 13px and a hit
target of at least 44px, and the heading does not wrap onto extra rows. The phone (390) and laptop (1440, 1280) headings keep the sizes they had on master (recorded
before the change). Screenshots on request: F164_SHOTS=<folder>."""
import os

import pytest

from tests_browser.helpers import DESKTOP, PHONE
from tests_browser.test_topbar import LAPTOP, TABLET, signed_in  # noqa: F401 - fixture

CONTROLS = {"switch": ".cz-head .cz-seg", "sos": ".cz-head .cz-sos", "map": ".cz-head .cz-mapbtn", "filters": ".cz-bar .cz-kchip",
            "trip": ".cz-head summary", "back": ".cz-head .cz-back"}
# every visible control: [text, smallest text size inside it (0: no text), width, height]
MEASURE = """(sel) => [...document.querySelectorAll(sel)].filter(e => { const r = e.getBoundingClientRect(); return r.width && r.height && getComputedStyle(e).visibility !== 'hidden'; }).map(e => {
  const r = e.getBoundingClientRect(); const own = [e, ...e.querySelectorAll('*')].filter(n => [...n.childNodes].some(c => c.nodeType === 3 && c.textContent.trim()));
  return [(e.textContent || '').trim().slice(0, 12), own.length ? Math.min(...own.map(n => parseFloat(getComputedStyle(n).fontSize))) : 0, Math.round(r.width * 10) / 10, Math.round(r.height * 10) / 10]; })"""
# the heading's height, and how far the switch / SOS / map sit below the words' top: a wrapped control drops onto its own row
HEAD = """() => { const h = document.querySelector('.cz-view .cz-head'), t = h.querySelector('.cz-head-text').getBoundingClientRect();
  const low = [...h.querySelectorAll('.cz-seg, .cz-sos, .cz-mapbtn')].map(e => e.getBoundingClientRect()).filter(r => r.height).map(r => Math.round(r.top - t.top));
  return [Math.round(h.getBoundingClientRect().height), low.length ? Math.max(...low) : 0, Math.round(t.height)]; }"""
LEVELS = {"day": "/trip/canvas?day=0", "week": "/trip/canvas"}
ALL = pytest.mark.parametrize("level", LEVELS)

# master's sizes before F-164, from the same measure: [text, text size, width, height] per control (the Trip menu's text and width follow the trip's dates and name, so only its [size, height] count)
SW = {12: [["Day", 12, 33, 33], ["Week", 12, 40, 33]], 13: [["Day", 13, 44, 44], ["Week", 13, 45, 44]]}
LAP_FILTERS = [["All", 12, 38, 28], ["Plans", 12, 53, 28], ["Hotels", 12, 61, 28], ["Flights", 12, 62, 28], ["Car", 12, 43, 28], ["Chats", 12, 57, 28]]
PHONE_FILTERS = [["All", 14, 44, 44], ["Plans", 14, 50, 44], ["Hotels", 14, 57, 44], ["Flights", 14, 60, 44], ["Car", 14, 44, 44], ["Chats", 14, 53, 44]]
BEFORE = {
    (1440, "day"): {"switch": SW[12], "map": [["", 0, 32, 32]], "filters": LAP_FILTERS, "trip": [11.4996, 17.3]},
    (1440, "week"): {"switch": SW[12], "filters": LAP_FILTERS, "trip": [11.4996, 17.3]},
    (1280, "day"): {"switch": SW[12], "map": [["", 0, 32, 32]], "filters": LAP_FILTERS, "trip": [11.4996, 17.3]},
    (1280, "week"): {"switch": SW[12], "filters": LAP_FILTERS, "trip": [11.4996, 17.3]},
    (390, "day"): {"sos": [["SOS", 13, 44, 44]], "map": [["", 0, 44, 44]], "filters": PHONE_FILTERS, "trip": [13, 47.5], "back": [["Trip", 17, 75.3, 44]]},
    (390, "week"): {"switch": SW[13], "sos": [["SOS", 13, 44, 44]], "filters": PHONE_FILTERS, "trip": [13, 67]},
}


def measure(page):
    page.evaluate("document.querySelectorAll('.cz-kinds').forEach(e => e.hidden = false)")      # the script shows the filter row; show it for the scan
    out = {k: page.evaluate(MEASURE, sel) for k, sel in CONTROLS.items()}
    out["head"] = page.evaluate(HEAD)
    return out


def open_page(signed_in, viewport, level):
    page = signed_in(viewport, path=LEVELS[level])
    page.wait_for_selector(".cz-view .cz-head")
    page.wait_for_timeout(300)
    return page


@ALL
def test_every_tablet_heading_control_is_13px_text_in_a_44px_target(signed_in, level):
    page = open_page(signed_in, TABLET, level)
    got = measure(page)
    assert len(got["switch"]) == 2 and len(got["sos"]) == 1 and len(got["filters"]) == 6 and len(got["trip"]) == 1      # the scan finds every control
    if level == "day":
        assert len(got["map"]) == 1 and len(got["back"]) == 1
    for name in ("switch", "sos", "map", "filters", "trip", "back"):
        for text, font, w, h in got[name]:
            if font:
                assert font >= 13, (name, text, font)
            assert w >= 44 and h >= 44, (name, text, w, h)
    shots = os.environ.get("F164_SHOTS")
    if shots:
        page.locator(".cz-view .cz-head").first.screenshot(path=os.path.join(shots, f"{level}-800.png"))


@ALL
def test_the_tablet_heading_stays_on_one_row(signed_in, level):
    page = open_page(signed_in, TABLET, level)
    height, drop, words = measure(page)["head"]
    assert drop < 40, (drop, words)      # the switch, SOS and map start within one line of the words' top (a line is ~32px): not on a row of their own


@pytest.mark.parametrize("viewport", [TABLET, PHONE], ids=["800", "390"])
@ALL
def test_the_trip_menu_rows_are_13px_text_in_44px_rows(signed_in, viewport, level):
    page = open_page(signed_in, viewport, level)
    page.locator(".cz-head summary").first.click()
    page.wait_for_timeout(400)
    rows = page.evaluate(MEASURE, ".cz-head .ga-tb-phonepick .ga-tb-item")
    assert rows, "the Trip menu opens with rows"
    for text, font, w, h in rows:
        if font:
            assert font >= 13, (text, font)
        assert h >= 44, (text, h)


@pytest.mark.parametrize("viewport", [DESKTOP, LAPTOP, PHONE], ids=["1440", "1280", "390"])
@ALL
def test_the_phone_and_laptop_headings_keep_their_sizes(signed_in, viewport, level):
    page = open_page(signed_in, viewport, level)
    got = measure(page)
    want = BEFORE[(viewport["width"], level)]
    for name, rows in want.items():
        have = [got[name][0][1], got[name][0][3]] if name == "trip" else got[name]
        assert have == rows, (name, have)
