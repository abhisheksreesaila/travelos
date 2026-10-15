"""F-158: the calm laptop skin, pinned in a real browser so it cannot drift back. At 1440 and 1280 (the laptop) the day, the week, the panel and the family, import and start pages are flat hairline surfaces
(no layered shadow on a card, a 1px hairline edge), the buttons are flat pills (no ledge, no lift), the day and the week carry the two-tone heading (the title, then its second phrase in coral), the data rows
have their tiles, and Up next is the one solid accent block. At 390 (phone) and 800 (tablet) none of that shows: the buttons keep their ledge, the day keeps its ink header and the second phrase is not drawn.
Assets: assets/css/desk_skin.css (loaded last by layout.styles()). Screenshots on request: F158_SHOTS=<folder>."""
import os
import re

import pytest
from playwright.sync_api import expect

from gitaway import tripcal as cal
from tests.test_signin import person
from tests_browser.helpers import DESKTOP, PHONE
from tests_browser.test_topbar import LAPTOP, TABLET, signed_in  # noqa: F401 - fixture

INK = "rgb(30, 26, 46)"
CORAL = "rgb(255, 115, 82)"
CORAL_DEEP = "rgb(201, 67, 31)"
HAIRLINE = "rgba(30, 26, 46, 0.1)"
NO_SCROLL = "document.documentElement.scrollWidth <= document.documentElement.clientWidth && document.documentElement.scrollHeight <= document.documentElement.clientHeight"
BOTH = pytest.mark.parametrize("viewport", [DESKTOP, LAPTOP], ids=["1440", "1280"])


def shot(page, name):
    if os.environ.get("F158_SHOTS"):
        page.screenshot(path=os.path.join(os.environ["F158_SHOTS"], name))


def plans():
    me = person("ari")
    cal.add_activity(me, day=0, start=12 * 60 + 30, end=14 * 60, title="Lunch at Grand Central Market", kind="food")
    return cal.add_activity(me, day=0, start=17 * 60 + 30, end=19 * 60, title="Santa Monica Pier sunset", kind="outdoors")


def style(page, selector, *props):
    """The computed style properties of the first match."""
    return page.locator(selector).first.evaluate("(e, props) => { const s = getComputedStyle(e); return props.map(p => s[p]); }", list(props))


def is_flat(shadow):
    """No visible shadow: `none`, or only zero-size transparent ones (the skin's --shadow-sm and --shadow-md, which keep a plan block's key bar valid)."""
    return shadow == "none" or all(part.strip().startswith("rgba(0, 0, 0, 0)") for part in re.split(r",\s*(?=rgba?\()", shadow))


@BOTH
def test_the_day_is_flat_hairline_cards_and_the_panel_too(signed_in, viewport):
    page = signed_in(viewport, path="/trip/canvas?day=0")
    act = plans()
    page.goto(page.url.split("?")[0] + f"?day=0&plan={act.id}")
    expect(page.locator("#cz-dock[data-mode=plan] .cz-pp")).to_be_visible()
    for sel in (".cz-day-body", "#cz-dock"):
        shadow, width, color, radius = style(page, sel, "boxShadow", "borderTopWidth", "borderTopColor", "borderTopLeftRadius")
        assert is_flat(shadow), f"{sel} has a shadow: {shadow}"
        assert (width, color) == ("1px", HAIRLINE), f"{sel}: {width} {color}"
        assert 13 <= float(radius[:-2]) <= 15, f"{sel} radius {radius}"      # 14px design: 1.1667rem at the 12px root
    shot(page, f"day-plan-{viewport['width']}.png")
    assert page.evaluate(NO_SCROLL)


@BOTH
def test_buttons_are_flat_pills_with_no_ledge_and_no_lift(signed_in, viewport):
    page = signed_in(viewport, path="/trip/canvas?day=0")
    for sel in ("#cz-desk-paste", "#cz-desk-talk", "#cz-up-directions", "#cz-up-open"):
        shadow, transform, radius = style(page, sel, "boxShadow", "transform", "borderTopLeftRadius")
        assert is_flat(shadow) and transform == "none", f"{sel}: {shadow} {transform}"
        assert float(radius[:-2]) > 10, f"{sel} is not a pill"
    assert style(page, "#cz-desk-talk", "backgroundColor")[0] == CORAL      # primary: coral
    assert style(page, "#cz-desk-paste", "borderTopWidth")[0] == "1px"       # secondary: a hairline
    page.goto(page.url.split("/trip")[0] + "/family")
    for button in page.locator(".fam .btn").all()[:4]:
        shadow, transform = button.evaluate("e => [getComputedStyle(e).boxShadow, getComputedStyle(e).transform]")
        assert is_flat(shadow) and transform == "none", f"/family button: {shadow}"


@BOTH
def test_the_day_and_the_week_have_the_two_tone_heading(signed_in, viewport):
    page = signed_in(viewport, path="/trip/canvas?day=0")
    expect(page.locator("#cz-title")).to_have_text("Friday")
    two = page.locator(".cz-view[data-day] .ga-h-two")
    expect(two).to_be_visible()
    assert two.inner_text().strip() == "Fly in, check in."
    assert style(page, ".cz-view[data-day] .ga-h-two", "color")[0] == CORAL_DEEP
    assert style(page, "#cz-title", "color")[0] == INK
    page.goto(page.url.split("?")[0])
    two = page.locator(".cz-view[data-level=week] .ga-h-two")
    expect(two).to_be_visible()
    assert two.inner_text().strip() == "Five days in LA."          # the trip's real length and place
    assert style(page, ".cz-view[data-level=week] .ga-h-two", "color")[0] == CORAL_DEEP
    assert page.evaluate(NO_SCROLL)
    shot(page, f"week-{viewport['width']}.png")


@BOTH
def test_the_week_is_numbered_columns_with_data_rows(signed_in, viewport):
    page = signed_in(viewport, path="/trip/canvas")
    plans()
    page.reload()
    cols = page.locator(".cz-wcol")
    expect(cols).to_have_count(5)
    expect(page.locator(".cz-wcol .cz-wh-no")).to_have_text(["01", "02", "03", "04", "05"])
    expect(page.locator(".cz-wcol").first.locator(".cz-wh-sum")).to_have_text("2 bookings · 2 plans")
    expect(page.locator(".cz-wcol").nth(2).locator(".cz-wh-sum")).to_have_text("Nothing planned")
    shadow, width, color = style(page, ".cz-wcol:nth-child(2)", "boxShadow", "borderTopWidth", "borderTopColor")
    assert is_flat(shadow) and (width, color) == ("1px", HAIRLINE)
    assert style(page, ".cz-wcol .cz-wh", "backgroundColor")[0] in ("rgba(0, 0, 0, 0)", "transparent")      # a flat header, not a day-colour block
    row_border = style(page, ".cz-wcol .cz-wi", "borderBottomWidth", "borderBottomColor")
    assert row_border == ["1px", HAIRLINE]                                                  # a hairline between rows


def test_up_next_is_the_only_accent_block(signed_in):
    page = signed_in(DESKTOP, path="/trip/canvas?day=0")
    plans()
    page.reload()
    expect(page.locator("#cz-up")).to_be_visible()
    got = page.evaluate("""() => [...document.querySelectorAll('body *')].filter(e => {
        const r = e.getBoundingClientRect(), bg = getComputedStyle(e).backgroundColor;
        return r.width >= 160 && r.height >= 60 && r.width * r.height < 1e6 && (bg === 'rgb(30, 26, 46)' || bg === 'rgb(255, 115, 82)');
      }).map(e => e.id || e.className)""")
    assert got == ["cz-up"], got
    tiles = page.locator("#cz-later .cz-later-tile")
    expect(tiles.first).to_be_visible()      # Later today is a data row: a tile, the name over its kind, the time at the right
    assert style(page, "#cz-later .cz-later-tile", "borderTopLeftRadius")[0] != "0px"
    shot(page, "day-idle-1440.png")


@BOTH
def test_the_other_pages_use_the_same_surfaces_and_headings(signed_in, viewport):
    page = signed_in(viewport, path="/family")
    expect(page.locator(".fam h1")).to_have_text("Your family")
    expect(page.locator(".fam-head .ga-h-two")).to_be_visible()
    shadow, width, color = style(page, ".fam-sec", "boxShadow", "borderTopWidth", "borderTopColor")
    assert is_flat(shadow) and (width, color) == ("1px", HAIRLINE)
    assert page.evaluate(NO_SCROLL)
    shot(page, f"family-{viewport['width']}.png")
    page.goto(page.url.split("/family")[0] + "/start")
    expect(page.locator(".st-hero h1")).to_have_text("Where to?")
    expect(page.locator(".st-hero .ga-h-two")).to_be_visible()
    assert is_flat(style(page, ".st-card", "boxShadow")[0])
    assert page.evaluate(NO_SCROLL)
    page.goto(page.url.split("/start")[0] + "/trip/map")
    expect(page.locator("#tp-title-h")).to_have_text("Map")
    expect(page.locator(".tp-head-text .ga-h-two")).to_be_visible()
    page.goto(page.url.split("/trip")[0] + "/trips/import")
    expect(page.locator(".ti-title")).to_have_text("Import a trip")
    expect(page.locator(".ti-head .ga-h-two")).to_be_visible()
    assert is_flat(style(page, ".ti-card", "boxShadow")[0])


def test_the_top_bar_is_flat_text_links_with_a_coral_underline(signed_in):
    page = signed_in(DESKTOP, path="/trip/canvas?day=0")
    bar = ".ga-topbar"
    width, color = style(page, bar, "borderBottomWidth", "borderBottomColor")
    assert (width, color) == ("1px", HAIRLINE)
    nav = style(page, f"{bar} .ga-tb-nav", "backgroundColor", "boxShadow")
    assert nav[0] in ("rgba(0, 0, 0, 0)", "transparent") and is_flat(nav[1])
    cur = style(page, f"{bar} .ga-tb-link[aria-current=page]", "borderBottomColor", "borderBottomWidth", "backgroundColor")
    assert cur[0] == CORAL and cur[1] != "0px" and cur[2] in ("rgba(0, 0, 0, 0)", "transparent")      # the current link: ink text with a coral underline, no pill


@pytest.mark.parametrize("viewport", [PHONE, TABLET], ids=["390", "800"])
def test_the_phone_and_the_tablet_keep_their_look(signed_in, viewport):
    page = signed_in(viewport, path="/trip/canvas?day=0")
    expect(page.locator(".ga-h-two").first).to_be_hidden()      # the second phrase is drawn on a laptop only
    head = style(page, ".cz-view[data-day] .cz-head", "backgroundColor", "borderTopLeftRadius")
    assert head[0] == INK and float(head[1][:-2]) > 14      # the day keeps its ink header
    page.goto(page.url.split("/trip")[0] + "/family")
    buttons = page.locator(".fam .btn")
    shadow = buttons.first.evaluate("e => getComputedStyle(e).boxShadow")
    assert re.search(r"0px (3|4)px 0px", shadow), f"the tactile ledge is gone: {shadow}"      # the phone keeps its tactile buttons
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
