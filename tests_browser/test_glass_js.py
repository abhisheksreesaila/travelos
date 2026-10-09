"""F-096: three tabs and a touch of glass, in a real browser at 390 and 320. The bar is Today, Ask, Family in three equal columns with Ask in the true centre; the day heading's map
button opens that day's map; the tab bar and the sheets are translucent with a strong blur and a tinted base; the text on them keeps 4.5:1 even over the darkest thing behind (and the
bar over the busiest day); cards stay solid; screenshots go to the folder named by GLASS_SHOTS when it is set."""
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
  const sheet = document.querySelector('.cz-sheet'), bar = document.querySelector('.ph-tabs-r');
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


def over(bg, backdrop):
    r, g, b, a = bg
    return tuple(a * c + (1 - a) * k for c, k in zip((r, g, b), backdrop))


@pytest.mark.parametrize("viewport", [PHONE, NARROW], ids=["390", "320"])
def test_the_bar_is_a_today_pill_on_the_left_and_a_capsule_on_the_right(imported_page, base_url, viewport):
    """F-133: Calendar's bar: Today a pill at the left edge, Ask and Family one capsule at the right edge, every target 44px."""
    page = imported_page(viewport=viewport)
    day(page, base_url, 1)
    assert page.locator(".ph-tab").count() == 3
    today, cap = page.locator("#ph-tab-today").bounding_box(), page.locator(".ph-tabs-r").bounding_box()
    assert today["x"] < 24 and cap["x"] + cap["width"] > viewport["width"] - 24 and abs((today["y"] + today["height"] / 2) - (cap["y"] + cap["height"] / 2)) < 1.5
    for k in ("today", "ask", "family"):
        b = page.locator(f"#ph-tab-{k}").bounding_box()
        assert b["width"] >= 43.5 and b["height"] >= 43.5
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
def test_the_bar_and_the_sheets_are_glass_and_keep_their_contrast(imported_page, base_url, viewport):
    page = imported_page(viewport=viewport)
    day(page, base_url, 1)
    if SHOTS and viewport is PHONE:
        Path(SHOTS).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(SHOTS) / "day-390.png"))
        page.locator(".ph-tabs").screenshot(path=str(Path(SHOTS) / "tabbar-390.png"))
    bar = page.evaluate(COLOURS)["bar"]
    bg = parse(bar["bg"])
    assert 0.6 < bg[3] < 0.95 and "blur(" in bar["filter"]      # translucent, strongly blurred, tinted base
    for backdrop in ((0, 0, 0), (30, 26, 46)):   # black and the dark Up next card behind the bar
        assert contrast(parse(bar["text"]), over(bg, backdrop)) >= 4.5
    # the inactive labels are the lightest text on the bar: measure them too
    label = parse(page.evaluate("getComputedStyle(document.querySelector('#ph-tab-ask')).color"))
    assert contrast(label, over(bg, (0, 0, 0))) >= 4.5
    ink3 = parse(page.evaluate("getComputedStyle(document.querySelector('#ph-tab-today')).color"))
    assert contrast(ink3, over(bg, (0, 0, 0))) >= 4.5

    page.goto(f"{base_url}/trip/canvas?day=1&sos=1")
    page.wait_for_selector(".cz-sheet-sos")
    sheet = page.evaluate(COLOURS)["sheet"]
    sbg = parse(sheet["bg"])
    assert 0.7 < sbg[3] < 0.95 and "blur(" in sheet["filter"]
    scrimmed = (0x1E * 0.4, 0x1A * 0.4, 0x2E * 0.4)       # the darkest page there is, behind the dark scrim
    assert contrast(parse(sheet["text"]), over(sbg, scrimmed)) >= 4.5
    ink3 = parse(page.evaluate("getComputedStyle(document.querySelector('.cz-sheet > p, .cz-sheet > * > p') || document.querySelector('.cz-sheet h2')).color"))
    assert contrast(ink3, over(sbg, scrimmed)) >= 4.5
    assert page.evaluate("getComputedStyle(document.querySelector('.cz-sheet .bk-sos-row, .cz-sheet .tp-btn')).backdropFilter") == "none"      # cards inside stay solid


def test_a_booking_sheet_over_a_park_day_is_glass(imported_page, base_url):
    page = imported_page()
    day(page, base_url, 1)
    link = page.locator("a[href*='booked=']").first
    if link.count():
        link.click()
        page.wait_for_selector(".cz-sheet-bk")
    else:
        page.goto(f"{base_url}/trip/canvas?day=0&booked=b-in")
        page.wait_for_selector(".cz-sheet-bk")
    assert "blur(" in page.evaluate(COLOURS)["sheet"]["filter"]
    if SHOTS:
        Path(SHOTS).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(SHOTS) / "sheet-390.png"))
