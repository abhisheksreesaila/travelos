"""F-163: the phone week as white day cards (weekday, date and title; a mini hour bar with kind-coloured segments; the day's items as compact rows with their start time and tile), pinned at 390,
and the tablet (800) showing the same stack. Rules: docs/design/colour-timeline.md (frame ct-week-phone), design-system/DESIGN-SYSTEM.md "The week as day cards (F-163)".
Colour is the kind of thing only (the tile, the bar's segments); the cards, their headers and the Today pill carry no day colour. Screenshots on request: F163_SHOTS=<folder>."""
import os

import pytest
from playwright.sync_api import expect

from gitaway import catalog, tripcal as cal
from tests.test_signin import person
from tests_browser.helpers import PHONE
from tests_browser.test_day_dock import SAT_NOON
from tests_browser.test_topbar import TABLET, signed_in  # noqa: F401 - fixture

BOTH = pytest.mark.parametrize("viewport", [PHONE, TABLET], ids=["390", "800"])
CARD = "rgb(255, 255, 255)"
INK = "rgb(30, 26, 46)"
INK_2 = "rgb(74, 68, 96)"
PAPER_2 = "rgb(250, 247, 242)"
HAIRLINE = "rgba(30, 26, 46, 0.1)"
SUN, SUN_TINT = "rgb(255, 201, 60)", "rgb(255, 241, 194)"
MINT, MINT_TINT = "rgb(72, 209, 160)", "rgb(212, 247, 234)"
SKY, SKY_TINT = "rgb(90, 176, 255)", "rgb(221, 238, 255)"
GRAPE, GRAPE_TINT = "rgb(195, 178, 255)", "rgb(236, 228, 255)"
LONG = "Griffith Observatory planetarium show"


def shot(page, name):
    if os.environ.get("F163_SHOTS"):
        page.screenshot(path=os.path.join(os.environ["F163_SHOTS"], name), full_page=True)


def plans(busy=False):
    """Day 0 (the sample's flight, hotel and car bookings) gets a lunch and a sunset; day 1 a long title; day 2 stays free in the sample."""
    me = person("ari")
    cal.add_activity(me, day=0, start=12 * 60 + 30, end=14 * 60, title="Lunch at Grand Central Market", kind="food")
    cal.add_activity(me, day=0, start=17 * 60 + 30, end=19 * 60, title="Santa Monica Pier sunset", kind="outdoors")
    cal.add_activity(me, day=1, start=9 * 60, end=11 * 60, title=LONG, kind="culture")
    if busy:
        for n, (s, e, title, kind) in enumerate(((7 * 60, 8 * 60, "Early walk", "outdoors"), (10 * 60, 10 * 60 + 15, "Call Grandma", "fun"), (12 * 60, 13 * 60, "Tacos", "food"),
                                                  (15 * 60, 16 * 60, "Museum", "culture"), (21 * 60, 23 * 60, "Late show", "fun"))):
            cal.add_activity(me, day=3, start=s, end=e, title=title, kind=kind, fine=True)


def week(signed_in, viewport, busy=False):
    page = signed_in(viewport, path="/trip/canvas")
    plans(busy)
    page.reload()
    expect(page.locator("#cz-week .cz-row").first).to_be_visible()
    return page


CARDS = """() => [...document.querySelectorAll('#cz-week .cz-row')].map(row => {
  const cs = e => getComputedStyle(e), r = e => { const b = e.getBoundingClientRect(); return {x: b.left, y: b.top, w: b.width, h: b.height, r: b.right, b: b.bottom}; };
  const head = row.querySelector('.cz-row-link');
  return {day: +row.dataset.day, free: row.classList.contains('is-free'), today: row.classList.contains('is-today'), rect: r(row), bg: cs(row).backgroundColor, border: cs(row).borderTopColor + ' ' + cs(row).borderTopWidth, shadow: cs(row).boxShadow,
    headBg: cs(head).backgroundColor, headText: head.textContent.replace(/\\s+/g, ' ').trim(), headClass: head.className, rowClass: row.className,
    rows: [...row.querySelectorAll('.cz-wcard')].map(c => ({text: c.textContent.replace(/\\s+/g, ' ').trim(), r: r(c), booked: c.classList.contains('is-booked'), kind: c.dataset.kind})),
    tiles: [...row.querySelectorAll('.cz-wr-tile')].length};
})"""


def cards(page):
    return page.evaluate(CARDS)


@BOTH
def test_the_week_is_one_white_card_per_day_with_a_hairline_and_no_day_colour(signed_in, viewport):
    page = week(signed_in, viewport)
    got = cards(page)
    assert [c["day"] for c in got] == [0, 1, 2, 3, 4]
    for c in got:
        assert c["bg"] == CARD and c["border"] == f"{HAIRLINE} 1px", c
        assert c["shadow"] == "none" or "0px 0px 0px 0px" in c["shadow"], c      # no shadow at rest
        assert c["headBg"] in ("rgba(0, 0, 0, 0)", CARD), c      # the header is not coloured
        assert "tp-t-" not in c["rowClass"] + c["headClass"]
    assert page.evaluate("document.querySelectorAll('#cz-week [class*=\"tp-t-\"], #cz-week .cz-badge').length") == 0      # no day tint, no coloured day badge
    xs = {round(c["rect"]["x"], 1) for c in got} | {round(c["rect"]["r"], 1) for c in got}
    assert len(xs) == 2      # one stack: every card has the same left and right edge (the tablet shows the same stack, one column)
    ys = [c["rect"] for c in got]
    assert all(a["b"] <= b["y"] for a, b in zip(ys, ys[1:]))      # stacked top to bottom
    shot(page, f"week-{viewport['width']}.png")
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")


@BOTH
def test_a_card_says_weekday_date_and_title_and_today_is_an_ink_pill(signed_in, viewport):
    page = week(signed_in, viewport)
    got = cards(page)
    assert got[0]["headText"].startswith("Fri 16 ") and "Fly in" in got[0]["headText"]
    assert got[2]["headText"].startswith("Sun 18 ")
    head = page.locator("#cz-week .cz-row").first.locator(".cz-row-link")
    day = head.locator(".cz-wd-day")
    assert day.evaluate("e => [getComputedStyle(e).fontFamily.split(',')[0], getComputedStyle(e).fontWeight, getComputedStyle(e).color]") == ["Bricolage Grotesque", "800", INK]
    assert head.locator(".cz-wd-head").evaluate("e => getComputedStyle(e).color") == INK_2


def test_today_is_an_ink_pill_on_the_card_of_today(signed_in, monkeypatch):
    monkeypatch.setattr(catalog, "now_utc", lambda: SAT_NOON)
    monkeypatch.setattr(catalog, "today", lambda: SAT_NOON.astimezone(catalog.TZ).date())
    page = signed_in(PHONE, path="/trip/canvas")
    pill = page.locator("#cz-week .cz-row.is-today .cz-today")
    expect(pill).to_have_text("Today")
    assert pill.evaluate("e => [getComputedStyle(e).backgroundColor, getComputedStyle(e).color]") == [INK, CARD]
    assert page.locator("#cz-week .cz-row.is-today").get_attribute("data-day") == "1"
    assert page.locator("#cz-week .cz-today").count() == 1
    assert page.locator("#cz-week .cz-row.is-today").evaluate("e => getComputedStyle(e).backgroundColor") == CARD      # today's card is not tinted


@BOTH
def test_the_mini_bar_has_kind_coloured_segments_at_their_times(signed_in, viewport):
    page = week(signed_in, viewport)
    bar = page.locator("#cz-week .cz-row[data-day='0'] .cz-mb")
    expect(bar).to_be_visible()
    labels = bar.locator(".cz-mb-h").all_inner_texts()
    assert labels == ["7 AM", "10 AM", "1 PM", "4 PM", "7 PM", "10 PM"]
    got = page.evaluate("""() => { const row = document.querySelector('#cz-week .cz-row[data-day="0"]'), track = row.querySelector('.cz-mb-track').getBoundingClientRect();
      return {track: {x: track.left, w: track.width}, segs: [...row.querySelectorAll('.cz-mb-seg')].map(s => { const b = s.getBoundingClientRect(); return {x: b.left, w: b.width, bg: getComputedStyle(s).backgroundColor, s: +s.dataset.s, e: +s.dataset.e, kind: s.dataset.kind}; })}; }""")
    lo, span = 7 * 60, 15 * 60
    assert len(got["segs"]) == 5      # the flight, lunch, hotel, sunset and the car
    for s in got["segs"]:
        assert s["x"] == pytest.approx(got["track"]["x"] + got["track"]["w"] * (s["s"] - lo) / span, abs=1), s      # left matches the item's start
        assert s["w"] == pytest.approx(got["track"]["w"] * (max(s["e"], s["s"] + 15) - s["s"]) / span, abs=1), s      # width matches its length
    colour = {(s["s"], s["kind"]): s["bg"] for s in got["segs"]}
    assert colour[(12 * 60 + 30, "plan")] == SUN and colour[(17 * 60 + 30, "plan")] == MINT
    assert SKY in {s["bg"] for s in got["segs"]} and GRAPE in {s["bg"] for s in got["segs"]}      # the flight and the hotel
    assert bar.locator(".cz-mb-seg").first.evaluate("e => parseFloat(getComputedStyle(e).height)") >= 4


@BOTH
def test_the_bar_widens_for_an_early_or_late_item(signed_in, viewport):
    page = week(signed_in, viewport, busy=True)
    labels = page.locator("#cz-week .cz-row[data-day='3'] .cz-mb-h").all_inner_texts()
    assert labels[0] == "7 AM" and labels[-1] == "11 PM"
    late = page.evaluate("""() => { const row = document.querySelector('#cz-week .cz-row[data-day="3"]'), t = row.querySelector('.cz-mb-track').getBoundingClientRect();
      return [...row.querySelectorAll('.cz-mb-seg')].map(s => { const b = s.getBoundingClientRect(); return b.left >= t.left - 0.5 && b.right <= t.right + 0.5; }); }""")
    assert late and all(late)      # a 9 PM to 11 PM show stays inside the bar


@BOTH
def test_items_are_compact_rows_with_start_time_tile_title_and_a_grey_pill(signed_in, viewport):
    page = week(signed_in, viewport)
    row = page.locator("#cz-week .cz-row[data-day='0']")
    items = row.locator(".cz-wcard")
    assert items.count() == 5
    times = [t.strip() for t in row.locator(".cz-wr-time").all_inner_texts()]
    assert times == ["8:05 AM", "12:30 PM", "3:00 PM", "5:30 PM", "6:45 PM"], times
    lunch = row.locator(".cz-wcard", has_text="Lunch at Grand Central Market")
    sunset = row.locator(".cz-wcard", has_text="Santa Monica Pier sunset")
    for card, tint, kind in ((lunch, SUN_TINT, "food"), (sunset, MINT_TINT, "outdoors")):
        tile = card.locator(".cz-wr-tile")
        assert tile.locator("svg").count() == 1
        assert tile.evaluate("e => getComputedStyle(e).backgroundColor") == tint, kind
        pill = card.locator(".cz-wr-tag")
        expect(pill).to_have_text("Plan")
        assert pill.evaluate("e => [getComputedStyle(e).backgroundColor, getComputedStyle(e).color, getComputedStyle(e).textTransform]") == [PAPER_2, INK_2, "uppercase"]
        assert card.evaluate("e => getComputedStyle(e).backgroundColor") in ("rgba(0, 0, 0, 0)", CARD)      # a row is not tinted: only its tile
    flight, hotel = row.locator(".cz-wcard.is-booked", has_text="Skylark"), row.locator(".cz-wcard.is-booked", has_text="Check in")
    for card, tint in ((flight, SKY_TINT), (hotel, GRAPE_TINT)):
        assert card.locator(".cz-wr-tile").evaluate("e => getComputedStyle(e).backgroundColor") == tint
        expect(card.locator(".cz-wr-tag")).to_have_text("Booked")
        assert card.locator(".cz-wr-tag").evaluate("e => getComputedStyle(e).backgroundColor") == PAPER_2


@BOTH
def test_text_is_13px_or_more_and_every_target_is_44px(signed_in, viewport):
    page = week(signed_in, viewport, busy=True)
    small = page.evaluate("""() => [...document.querySelectorAll('#cz-week *')].filter(e => e.childNodes.length && [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())
      && getComputedStyle(e).display !== 'none' && e.getBoundingClientRect().width).map(e => [e.className, parseFloat(getComputedStyle(e).fontSize)]).filter(([c, s]) => s < 13)""")
    assert small == []
    short = page.evaluate("""() => [...document.querySelectorAll('#cz-week a, #cz-week .cz-wcard, #cz-week .cz-row-link')].filter(e => e.getBoundingClientRect().width).map(e => [e.className, Math.round(e.getBoundingClientRect().height * 10) / 10]).filter(([c, h]) => h < 44)""")
    assert short == []


def test_a_long_title_wraps_at_spaces_to_two_lines_and_fades(signed_in):
    page = week(signed_in, PHONE)
    title = page.locator("#cz-week .cz-row[data-day='1'] .cz-wr-t", has_text="Griffith Observatory planetarium")
    got = title.evaluate("""e => { const cs = getComputedStyle(e), lh = parseFloat(cs.lineHeight) || parseFloat(cs.fontSize) * 1.15; return {h: e.clientHeight, sh: e.scrollHeight, lh, wrap: cs.overflowWrap, cut: e.classList.contains('is-cut'), mask: cs.maskImage || cs.webkitMaskImage}; }""")
    assert got["h"] <= got["lh"] * 2 + 2 and got["sh"] > got["h"] + 1, got      # two lines, then cut
    assert got["cut"] and "linear-gradient" in got["mask"] and got["wrap"] == "normal", got
    short = page.locator("#cz-week .cz-row[data-day='0'] .cz-wr-t", has_text="Lunch").evaluate("e => e.classList.contains('is-cut')")
    assert short is False


@BOTH
def test_an_empty_day_says_free_day_with_say_the_plan(signed_in, viewport):
    page = week(signed_in, viewport)
    free = page.locator("#cz-week .cz-row.is-free")
    assert free.count() == 1 and free.get_attribute("data-day") == "2"
    expect(free).to_contain_text("Free day")
    say = free.locator("a", has_text="Say the plan")
    expect(say).to_be_visible()
    assert say.get_attribute("href") == "/trip/ask?day=2&mode=talk"
    assert say.evaluate("e => e.getBoundingClientRect().height") >= 44
    assert free.locator(".cz-wcard").count() == 0 and free.locator(".cz-mb-seg").count() == 0
