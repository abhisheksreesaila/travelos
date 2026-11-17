"""F-277 (D-870): the extra-info chips stand out and load on demand. The row has its own label and tint, is one scroller on a phone and a laptop, nudges once, and no widget's data is fetched
until its chip is tapped. Shots: F277_SHOTS=1 for docs/report/f277-*.png."""
import os
from pathlib import Path

import pytest
from playwright.sync_api import expect

from tests_browser.helpers import DESKTOP, PHONE, set_mode
from tests_browser.test_tripmatrix import matrix, stand  # noqa: F401 (fixtures)
from tests_browser.test_v2_targets import small

REPORT = Path(__file__).resolve().parent.parent / "docs" / "report"
CARDS_ASKED = "() => performance.getEntriesByType('resource').map(r => r.name).filter(n => n.includes('/plan/matrix/rail') && n.includes('wg='))"


def shot(page, name):
    if os.environ.get("F277_SHOTS"):
        page.wait_for_timeout(700)
        page.screenshot(path=str(REPORT / f"f277-{name}.png"))


def chips(page):
    page.wait_for_selector("#mx-rail .wchip[data-wg]")
    return page.locator("#mx-rail .wchip[data-wg]")


def test_no_widget_data_is_fetched_until_its_chip_is_tapped(matrix):  # noqa: F811
    page = matrix(DESKTOP)
    chips(page)
    page.wait_for_timeout(800)
    assert page.evaluate(CARDS_ASKED) == []      # the chips came, no card's data did
    weather = page.locator("#mx-rail .wchip[data-wg='weather']")
    weather.click()
    expect(page.locator("#wg-weather")).to_be_visible()
    asked = page.evaluate(CARDS_ASKED)
    assert len(asked) == 1 and "wg=weather" in asked[0]
    weather.click()      # fold it, open it again: the card is kept, nothing is asked twice
    expect(page.locator("#wg-weather")).to_be_hidden()
    weather.click()
    expect(page.locator("#wg-weather")).to_be_visible()
    assert len(page.evaluate(CARDS_ASKED)) == 1
    assert page.errors == []


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["390", "1440"])
def test_the_row_is_titled_frosted_one_scroller_and_48px(matrix, viewport, scheme):  # noqa: F811
    page = matrix(viewport, scheme=scheme)
    set_mode(page, scheme)
    row = chips(page)
    label = page.locator("#mx-rail .rl-lab")
    expect(label).to_have_text("More to know before you pick")      # F-281: the tray is titled for what it is for
    tray = page.locator("#mx-rail .rl-chips")
    colours = page.evaluate("""() => { const t = document.querySelector('#mx-rail .rl-chips'), f = document.querySelector('#mx-rail .rl-tray'), l = document.querySelector('#mx-rail .rl-lab');
        return {frost: getComputedStyle(f).backgroundColor, label: getComputedStyle(l).color, overflow: getComputedStyle(t).overflowX}; }""")
    assert colours["overflow"] == "auto"
    assert colours["frost"] in ("rgba(16, 12, 24, 0.6)", "rgba(8, 10, 14, 0.62)")      # a dark frost of its own over the ground, in light and in dark
    assert colours["label"] == "rgb(244, 247, 251)"      # its words are the ground's (the painted-pixel ratios are in test_harbour.py)
    tops = {round(b["y"]) for b in (row.nth(i).bounding_box() for i in range(row.count()))}
    assert len(tops) == 1      # one line: a scroller, never a wrapped pile
    assert min(row.nth(i).bounding_box()["height"] for i in range(row.count())) >= 47.5
    assert small(page, "#mx-rail") == []
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")      # the page itself never scrolls sideways
    box = tray.bounding_box()
    if viewport is PHONE:
        assert tray.evaluate("t => t.scrollWidth > t.clientWidth")      # more chips than fit: it scrolls
        tray.evaluate("t => { t.scrollLeft = 120; }")
        assert tray.evaluate("t => t.scrollLeft") > 0
        assert box["x"] >= 0 and box["x"] + box["width"] <= viewport["width"]
    shot(page, f"row-{viewport['width']}-{scheme}")
    row.nth(1).click()
    expect(page.locator("#mx-rail .wg:not([hidden])")).to_have_count(1)
    shot(page, f"card-{viewport['width']}-{scheme}")


def test_a_gentle_nudge_comes_once_and_goes_when_a_chip_is_used(matrix):  # noqa: F811
    page = matrix(DESKTOP, motion=True)
    chips(page)
    expect(page.locator("#mx-rail .rl-nudge")).to_have_text("New: tap for weather, drive times, guides…")
    assert "v2-nudge" in page.evaluate("getComputedStyle(document.querySelector('#mx-rail .wchip')).animationName")
    page.locator("#mx-rail .wchip[data-wg='weather']").click()
    expect(page.locator("#mx-rail.is-nudge")).to_have_count(0)
    expect(page.locator("#mx-rail .rl-nudge")).to_be_hidden()
    assert page.evaluate("localStorage.getItem('ga-rail-used')") == "1"
    page.reload()
    page.wait_for_selector("#mx-rail .wchip[data-wg]")
    expect(page.locator("#mx-rail .rl-nudge")).to_be_hidden()      # used once: never again


def test_with_reduced_motion_the_nudge_is_words_only_and_a_blocked_store_breaks_nothing(matrix):  # noqa: F811
    page = matrix(DESKTOP, motion=False)
    chips(page)
    assert page.evaluate("getComputedStyle(document.querySelector('#mx-rail .wchip')).animationName") == "none"      # no pulse
    expect(page.locator("#mx-rail .rl-nudge")).to_be_visible()
    shot(page, "nudge-1440-light")
    page.evaluate("""Object.defineProperty(window, 'localStorage', { get() { throw new Error('blocked'); } })""")
    page.locator("#mx-rail .wchip[data-wg='about']").click()
    expect(page.locator("#wg-about")).to_be_visible()
    assert page.errors == []
