"""F-159: the laptop day as a colour timeline, pinned in a real browser at 1440 and 1280 (and the phone and tablet unchanged).
Rules: docs/design/colour-timeline.md, design-system/DESIGN-SYSTEM.md "The colour timeline (F-159)". Screenshots on request: F159_SHOTS=<folder>."""
import os

import pytest
from playwright.sync_api import expect

from gitaway import tripcal as cal
from tests.test_signin import person
from tests_browser.helpers import DESKTOP, PHONE
from tests_browser.test_topbar import LAPTOP, TABLET, signed_in  # noqa: F401 - fixture

INK = "rgb(30, 26, 46)"
CARD = "rgb(255, 255, 255)"
PAPER_2 = "rgb(250, 247, 242)"
INK_2 = "rgb(77, 71, 99)"
CORALS = ("rgb(255, 115, 82)", "rgb(201, 67, 31)")
SUN, SUN_TINT, SUN_INK = "rgb(255, 201, 60)", "rgb(255, 241, 194)", "rgb(138, 98, 0)"
MINT = "rgb(61, 214, 140)"
SKY = "rgb(78, 168, 255)"
GRAPE = "rgb(168, 140, 255)"
NO_SCROLL = "document.documentElement.scrollWidth <= document.documentElement.clientWidth && document.documentElement.scrollHeight <= document.documentElement.clientHeight"
BOTH = pytest.mark.parametrize("viewport", [DESKTOP, LAPTOP], ids=["1440", "1280"])


def shot(page, name):
    if os.environ.get("F159_SHOTS"):
        page.screenshot(path=os.path.join(os.environ["F159_SHOTS"], name))


def plans(short=False):
    """The frame's day: the sample's flight (8:05) and hotel (3:00 PM) bookings, a lunch and a sunset; `short` adds a 30 minute coffee."""
    me = person("ari")
    lunch = cal.add_activity(me, day=0, start=12 * 60 + 30, end=14 * 60, title="Lunch at Grand Central Market", kind="food")
    sunset = cal.add_activity(me, day=0, start=17 * 60 + 30, end=19 * 60, title="Santa Monica Pier sunset", kind="outdoors")
    if short:
        cal.add_activity(me, day=0, start=10 * 60, end=10 * 60 + 30, title="Coffee at the corner bakery on Spring Street", kind="fun")
    return lunch, sunset


def day(signed_in, viewport, short=False):
    page = signed_in(viewport, path="/trip/canvas?day=0")
    plans(short)
    page.reload()
    expect(page.locator(".cz-gb").first).to_be_visible()
    return page


def style(page, selector, *props):
    return page.locator(selector).first.evaluate("(e, props) => { const s = getComputedStyle(e); return props.map(p => s[p]); }", list(props))


@BOTH
def test_plans_and_bookings_are_white_cards_with_a_kind_tile_and_edge(signed_in, viewport):
    page = day(signed_in, viewport)
    lunch = page.locator(".cz-gb", has_text="Lunch at Grand Central Market")
    sunset = page.locator(".cz-gb", has_text="Santa Monica Pier sunset")
    for card, accent, tint, ink in ((lunch, SUN, SUN_TINT, SUN_INK), (sunset, MINT, "rgb(212, 247, 230)", "rgb(11, 122, 69)")):
        assert card.evaluate("e => getComputedStyle(e).backgroundColor") == CARD
        assert card.evaluate("e => getComputedStyle(e).borderTopWidth") == "1px"
        shadow = card.evaluate("e => getComputedStyle(e).boxShadow")
        assert f"{accent} 3px 0px 0px 0px inset" in shadow, shadow      # the 3px left edge in the kind's colour
        tile = card.locator(".cz-gb-tile")
        assert tile.evaluate("e => getComputedStyle(e).backgroundColor") == tint
        assert tile.evaluate("e => getComputedStyle(e).color") == ink
        assert tile.locator("svg").count() == 1
    flight = page.locator(".cz-gbk", has_text="Skylark")
    hotel = page.locator(".cz-gbk", has_text="Check in")
    for card, accent, tint in ((flight, SKY, "rgb(219, 238, 255)"), (hotel, GRAPE, "rgb(237, 231, 255)")):
        assert card.evaluate("e => getComputedStyle(e).backgroundColor") == CARD
        assert f"{accent} 3px 0px 0px 0px inset" in card.evaluate("e => getComputedStyle(e).boxShadow")
        assert card.locator(".cz-gbk-tile").evaluate("e => getComputedStyle(e).backgroundColor") == tint
        pill = card.locator(".cz-bk-tag")
        expect(pill).to_have_text("Booked")
        assert pill.evaluate("e => [getComputedStyle(e).backgroundColor, getComputedStyle(e).color, getComputedStyle(e).textTransform]") == [PAPER_2, INK_2, "uppercase"]
    plan_pill = lunch.locator(".cz-gb-tag")
    expect(plan_pill).to_have_text("Plan")
    assert plan_pill.evaluate("e => [getComputedStyle(e).backgroundColor, getComputedStyle(e).color]") == [PAPER_2, INK_2]
    panel = style(page, ".cz-day-body", "backgroundColor", "borderTopColor", "borderTopWidth")
    assert panel == [CARD, "rgba(30, 26, 46, 0.1)", "1px"]      # the day panel: white with a hairline, no day tint
    shot(page, f"day-{viewport['width']}.png")
    assert page.evaluate(NO_SCROLL)


@BOTH
def test_every_item_prints_its_start_on_the_rail_and_no_label_overlaps(signed_in, viewport):
    page = day(signed_in, viewport, short=True)
    got = page.evaluate("""() => {
      const rect = e => { const r = e.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; };
      const starts = [...document.querySelectorAll('.cz-g-start')].map(e => ({text: e.querySelector('.cz-g-st-t').textContent + ' ' + e.querySelector('.cz-g-st-m').textContent, r: rect(e), ids: e.dataset.for,
        big: parseFloat(getComputedStyle(e.querySelector('.cz-g-st-t')).fontSize), weight: getComputedStyle(e.querySelector('.cz-g-st-t')).fontWeight}));
      const hours = [...document.querySelectorAll('.cz-g-hour')].filter(e => getComputedStyle(e).display !== 'none').map(e => ({text: e.textContent, r: rect(e), size: parseFloat(getComputedStyle(e).fontSize)}));
      const cards = [...document.querySelectorAll('.cz-gb, .cz-gbk')].map(e => ({id: e.dataset.act || e.dataset.zk, top: e.getBoundingClientRect().top}));
      return {starts, hours, cards};
    }""")
    assert sorted(s["text"] for s in got["starts"]) == ["10:00 AM", "12:30 PM", "3:00 PM", "5:30 PM", "8:05 AM"]
    for s in got["starts"]:
        assert s["weight"] == "800" and s["big"] >= 1.4 * got["hours"][0]["size"], s      # big: about 1.5x an hour label
    for card in got["cards"]:      # a start time beside every item: its label's top is within half an hour of the card's top
        near = [s for s in got["starts"] if abs(s["r"][1] - card["top"]) < 40]
        assert near, card
    boxes = [(f"start {s['text']}", s["r"]) for s in got["starts"]] + [(f"hour {h['text']}", h["r"]) for h in got["hours"]]
    for i, (na, a) in enumerate(boxes):
        for nb, b in boxes[i + 1:]:
            assert a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1], f"{na} overlaps {nb}"
    shown = {h["text"] for h in got["hours"]}
    assert not shown & {"8 AM", "10 AM", "12 PM", "1 PM", "3 PM", "5 PM", "6 PM"}      # each is within 30 minutes of a printed start
    assert {"7 AM", "9 AM", "11 AM", "2 PM", "4 PM", "7 PM"} <= shown      # the others stay


@BOTH
def test_day_tabs_are_neutral_pills_and_the_open_one_is_ink(signed_in, viewport):
    page = day(signed_in, viewport)
    chips = page.locator(".cz-hchip")
    expect(chips).to_have_count(5)
    got = chips.evaluate_all("""els => els.map(e => { const s = getComputedStyle(e), b = getComputedStyle(e, '::before');
      return {open: e.classList.contains('is-open'), bg: s.backgroundColor, color: s.color, radius: parseFloat(s.borderTopLeftRadius), height: e.getBoundingClientRect().height, before: b.content, dow: getComputedStyle(e.querySelector('.cz-hc-dow')).color}; })""")
    assert [g["open"] for g in got] == [True, False, False, False, False]
    assert got[0]["bg"] == INK and got[0]["color"] == CARD
    for g in got[1:]:
        assert g["bg"] == CARD and g["color"] == INK, g
    for g in got:
        assert g["before"] in ("none", "normal"), g      # no coloured key per day
        assert g["radius"] >= g["height"] / 2 - 1, g      # a pill
    assert style(page, ".cz-hchip.is-open .cz-hc-num", "color")[0] == CARD
    assert page.evaluate(NO_SCROLL)


@BOTH
def test_coral_is_only_the_primary_buttons_and_the_now_line(signed_in, viewport):
    page = day(signed_in, viewport)
    bad = page.evaluate("""corals => [...document.querySelectorAll('.cz-view[data-day] *, #cz-dock *')].filter(e => {
        const r = e.getBoundingClientRect(), s = getComputedStyle(e);
        if (!r.width || !r.height || s.visibility === 'hidden' || s.display === 'none') return false;
        const paints = [s.color, s.backgroundColor, s.borderTopColor, s.borderLeftColor].filter(c => corals.includes(c));
        const owns = e.closest('.cz-desk-btn, .cz-dock-btn, .tp-btn, .cz-nowline, .cz-ask-mic, .cz-compose-go, .cz-dock-un, .cz-fam-un, .cz-ask-send');
        return paints.length && !owns;
      }).map(e => e.className.toString() + ' ' + (e.textContent || '').trim().slice(0, 20))""", list(CORALS))
    assert bad == [], bad
    up = page.locator("#cz-up")
    assert up.evaluate("e => getComputedStyle(e).backgroundColor") == INK      # Up next stays the one ink card
    shot(page, f"day-idle-{viewport['width']}.png")


@BOTH
def test_a_short_plan_keeps_its_title_on_one_line(signed_in, viewport):
    page = day(signed_in, viewport, short=True)
    card = page.locator(".cz-gb", has_text="Coffee at the corner")
    title = card.locator(".cz-gb-t")
    line = title.evaluate("e => parseFloat(getComputedStyle(e).lineHeight)")
    assert title.evaluate("e => e.getBoundingClientRect().height") <= line * 1.2
    assert card.evaluate("e => e.getBoundingClientRect().height") >= 40      # a minimum height keeps it readable
    assert card.locator(".cz-gb-tile").evaluate("e => e.getBoundingClientRect().bottom <= e.closest('.cz-gb').getBoundingClientRect().bottom")


@BOTH
def test_the_day_fits_the_screen_with_a_plan_open(signed_in, viewport):
    page = day(signed_in, viewport)
    assert page.evaluate(NO_SCROLL)


@pytest.mark.parametrize("viewport", [PHONE, TABLET], ids=["390", "800"])
def test_the_phone_and_the_tablet_are_unchanged(signed_in, viewport):
    page = day(signed_in, viewport)
    for sel in (".cz-g-start", ".cz-gb-tile", ".cz-gb-tag"):
        for e in page.locator(sel).all():
            assert e.evaluate("e => getComputedStyle(e).display") == "none", sel
    assert page.locator(".cz-gbk-tile").first.evaluate("e => getComputedStyle(e).display") == "contents"      # a booking's icon sits in its row as before
    hours = page.locator(".cz-g-hour")
    assert all(h.evaluate("e => getComputedStyle(e).display") != "none" for h in hours.all())      # every hour label stays
    lunch = page.locator(".cz-gb", has_text="Lunch at Grand Central Market")
    assert lunch.evaluate("e => getComputedStyle(e).backgroundColor") == SUN_TINT      # the block keeps its tint
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
