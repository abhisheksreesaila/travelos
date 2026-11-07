"""F-096, F-200: the tab bar, the map button and the sheets, in a real browser at 390 and 320. F-200 (the free-and-polished brief) replaced F-096's glass and F-133's two pills:
the bar is one opaque floating bar of five tabs (Trip, Plan, Ask in the true centre, Book, Family), every target 48px; the day heading's map button opens that day's map; the bar
and the sheets are opaque (no glass or blur anywhere) and their words keep 4.5:1; screenshots go to the folder named by GLASS_SHOTS when it is set."""
import os
import re
from pathlib import Path

import pytest
from playwright.sync_api import expect

from tests_browser.helpers import PHONE
from tests_browser.test_booked import day, imported_page  # noqa: F401 - fixtures
from tests_browser.test_trip_canvas import NARROW, canvas_page, model  # noqa: F401

SHOTS = os.environ.get("GLASS_SHOTS")

COLOURS = """() => {
  const rgba = (el) => getComputedStyle(el).backgroundColor;
  const sheet = document.querySelector('.cz-sheet'), bar = document.querySelector('.ph-tabs');
  const out = {};
  for (const [k, el] of [['sheet', sheet], ['bar', bar]]) if (el) {
    const cs = getComputedStyle(el);
    out[k] = {bg: cs.backgroundColor, filter: cs.backdropFilter || cs.webkitBackdropFilter, text: getComputedStyle(el.querySelector(k === 'bar' ? '.ph-tab' : 'h2')).color};
  }
  return out;
}"""


def parse(c):
    m = re.findall(r"[\d.]+", c)
    r, g, b = (float(x) for x in m[:3])
    if c.startswith("color("):      # color-mix answers in 0..1
        r, g, b = r * 255, g * 255, b * 255
    return r, g, b, float(m[3]) if len(m) > 3 else 1.0


def lum(rgb):
    def f(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(rgb[0]) + 0.7152 * f(rgb[1]) + 0.0722 * f(rgb[2])


def contrast(fg, bg):
    a, b = lum(fg), lum(bg)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


@pytest.mark.parametrize("viewport", [PHONE, NARROW], ids=["390", "320"])
def test_the_bar_is_one_floating_bar_of_five_tabs_with_ask_in_the_middle(imported_page, base_url, viewport):
    page = imported_page(viewport=viewport)
    day(page, base_url, 1)
    assert page.locator(".ph-tab").count() == 5
    bar = page.locator(".ph-tabs").bounding_box()
    assert bar["x"] >= 8 and bar["x"] + bar["width"] <= viewport["width"] - 8 and viewport["height"] - (bar["y"] + bar["height"]) >= 4      # it floats: clear of the edges
    boxes = [page.locator(f"#ph-tab-{k}").bounding_box() for k in ("trip", "plan", "ask", "book", "family")]
    assert all(b["width"] >= 47.5 and b["height"] >= 47.5 for b in boxes), boxes
    assert all(a["x"] + a["width"] <= b["x"] + 0.5 for a, b in zip(boxes, boxes[1:]))      # in order, side by side
    ask = boxes[2]
    assert abs(ask["x"] + ask["width"] / 2 - (bar["x"] + bar["width"] / 2)) < 1.5            # Ask in the true centre
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")


@pytest.mark.parametrize("viewport", [PHONE, NARROW], ids=["390", "320"])
def test_the_map_button_opens_that_days_map(imported_page, base_url, viewport):
    page = imported_page(viewport=viewport)
    day(page, base_url, 2)
    btn = page.locator("#cz-mapbtn")
    box, sos = btn.bounding_box(), page.locator("#cz-sos").bounding_box()
    assert box["width"] >= 43.5 and box["height"] >= 43.5 and abs(box["y"] - sos["y"]) < 6 and box["x"] + box["width"] <= sos["x"] + 1      # beside SOS
    expect(btn).to_have_attribute("aria-label", "Map of this day")
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    btn.click()
    page.wait_for_url(re.compile(r"/trip/map\?day=2"))
    expect(page.locator("#mp-daychip")).to_be_visible()
    page.goto(f"{base_url}/trip/map")
    expect(page.locator("#mp-daychip")).to_be_visible()


@pytest.mark.parametrize("viewport", [PHONE, NARROW], ids=["390", "320"])
def test_the_bar_and_the_sheets_are_opaque_and_keep_their_contrast(imported_page, base_url, viewport):
    page = imported_page(viewport=viewport)
    day(page, base_url, 1)
    if SHOTS and viewport is PHONE:
        Path(SHOTS).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(SHOTS) / "day-390.png"))
        page.locator(".ph-tabs").screenshot(path=str(Path(SHOTS) / "tabbar-390.png"))
    bar = page.evaluate(COLOURS)["bar"]
    bg = parse(bar["bg"])
    assert bg[3] == 1 and bar["filter"] in ("none", None, "")       # opaque, no blur
    for tab in ("plan", "book", "family"):      # the inactive labels are the lightest words on the bar
        assert contrast(parse(page.evaluate(f"getComputedStyle(document.querySelector('#ph-tab-{tab}')).color")), bg[:3]) >= 4.5

    page.goto(f"{base_url}/trip/canvas?day=1&sos=1")
    page.wait_for_selector(".cz-sheet-sos")
    sheet = page.evaluate(COLOURS)["sheet"]
    sbg = parse(sheet["bg"])
    assert sbg[3] == 1 and sheet["filter"] in ("none", None, "")
    assert contrast(parse(sheet["text"]), sbg[:3]) >= 4.5
    ink3 = parse(page.evaluate("getComputedStyle(document.querySelector('.cz-sheet > p, .cz-sheet > * > p') || document.querySelector('.cz-sheet h2')).color"))
    assert contrast(ink3, sbg[:3]) >= 4.5


def test_a_booking_sheet_over_a_park_day_is_opaque(imported_page, base_url):
    page = imported_page()
    day(page, base_url, 1)
    link = page.locator("a[href*='booked=']").first
    if link.count():
        link.click()
        page.wait_for_selector(".cz-sheet-bk")
    else:
        page.goto(f"{base_url}/trip/canvas?day=0&booked=b-in")
        page.wait_for_selector(".cz-sheet-bk")
    sheet = page.evaluate(COLOURS)["sheet"]
    assert parse(sheet["bg"])[3] == 1 and sheet["filter"] in ("none", None, "")
    if SHOTS:
        Path(SHOTS).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(SHOTS) / "sheet-390.png"))
