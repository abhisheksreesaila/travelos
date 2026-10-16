"""F-162: the laptop week on one time axis, measured with real rects at 1440 and 1280 (100% zoom).
Rules: docs/design/colour-timeline.md (frame ct-week-desk), design-system/DESIGN-SYSTEM.md "The colour timeline (F-159)" and "The week on one time axis (F-162)".
The days are columns on one shared hour axis; a plan or booking sits at its start, is as tall as it lasts (a card under 30 minutes is drawn 30 tall so a line of text fits), coloured by kind only.
Screenshots on request: F162_SHOTS=<folder>."""
import os

import pytest
from playwright.sync_api import expect

from gitaway import tripcal as cal
from tests.test_signin import person
from tests_browser.helpers import DESKTOP
from tests_browser.test_topbar import LAPTOP, signed_in  # noqa: F401 - fixture

BOTH = pytest.mark.parametrize("viewport", [DESKTOP, LAPTOP], ids=["1440", "1280"])
NO_SCROLL = "document.documentElement.scrollWidth <= document.documentElement.clientWidth && document.documentElement.scrollHeight <= document.documentElement.clientHeight"
CARD = "rgb(255, 255, 255)"
KINDS = {"food": ("rgb(255, 201, 60)", "rgb(255, 241, 194)"), "outdoors": ("rgb(72, 209, 160)", "rgb(212, 247, 234)"), "culture": ("rgb(195, 178, 255)", "rgb(236, 228, 255)"),
         "fun": ("rgb(255, 125, 190)", None), "travel": ("rgb(90, 176, 255)", "rgb(221, 238, 255)")}
RECTS = """() => {
  const r = n => { const b = n.getBoundingClientRect(); return { x: b.left, y: b.top, w: b.width, h: b.height, r: b.right, b: b.bottom }; };
  const labels = [...document.querySelectorAll('.cz-wax .cz-wax-h')].map(n => ({ ...r(n), hr: +n.dataset.h }));
  const items = [...document.querySelectorAll('.cz-wcol .cz-wi')].map(n => ({ day: +n.closest('.cz-wcol').dataset.day, s: +n.dataset.s, e: +n.dataset.e, booked: n.classList.contains('is-booked'), title: n.querySelector('.cz-wi-t').textContent.trim(), ...r(n) }));
  return { labels, items, wk: r(document.querySelector('#cz-wk')), cols: [...document.querySelectorAll('.cz-wcol')].map(r) };
}"""


def shot(page, name):
    if os.environ.get("F162_SHOTS"):
        page.screenshot(path=os.path.join(os.environ["F162_SHOTS"], name))


def plans():
    """Same time in two columns, two plans at one time in one column, a short plan, a 15 minute plan."""
    me = person("ari")
    cal.add_activity(me, day=1, start=12 * 60 + 30, end=14 * 60, title="Lunch at Grand Central Market", kind="food")
    cal.add_activity(me, day=2, start=12 * 60 + 30, end=14 * 60, title="Sunday brunch at the beach", kind="outdoors")
    cal.add_activity(me, day=1, start=12 * 60 + 30, end=13 * 60 + 30, title="Kids' bike rental", kind="fun")      # at the same time as lunch: lanes
    cal.add_activity(me, day=1, start=17 * 60, end=17 * 60 + 30, title="Ice cream on the pier", kind="food")
    cal.add_activity(me, day=2, start=9 * 60, end=10 * 60, title="Griffith Observatory", kind="culture")
    cal.add_activity(me, day=2, start=16 * 60, end=16 * 60 + 15, title="Call Grandma", kind="fun", fine=True)


def week(signed_in, viewport):
    page = signed_in(viewport, path="/trip/canvas")
    plans()
    page.reload()
    page.wait_for_selector("#cz-wk .cz-wi")
    return page


@BOTH
def test_the_hour_axis_is_one_column_on_the_left_from_7_am_to_10_pm(signed_in, viewport):
    page = week(signed_in, viewport)
    m = page.evaluate(RECTS)
    hours = page.evaluate("[...document.querySelectorAll('.cz-wax .cz-wax-h')].map(n => [n.dataset.h, n.textContent.trim()])")
    assert hours[0] == ["420", "7 AM"] and hours[-1] == ["1320", "10 PM"] and len(hours) == 16
    assert all(l["r"] <= m["cols"][0]["x"] + 0.5 for l in m["labels"])      # left of every column
    ys = [l["y"] for l in m["labels"]]
    steps = {round(b - a, 1) for a, b in zip(ys, ys[1:])}
    assert len(steps) == 1 and 30 <= steps.pop() <= 60      # evenly spaced
    assert page.evaluate(NO_SCROLL), "the page scrolls"
    assert page.evaluate("(w => w.scrollHeight <= w.clientHeight && w.scrollWidth <= w.clientWidth)(document.querySelector('#cz-wk'))"), "the week panel scrolls inside itself"      # a fraction of a pixel over is a permanent scrollbar on a desktop with visible scrollbars
    assert m["labels"][-1]["b"] <= m["wk"]["b"] + 1 and m["labels"][0]["y"] >= m["wk"]["y"]      # the whole axis is inside the week area, which is inside the window
    assert m["wk"]["b"] <= viewport["height"]
    shot(page, f"axis-{viewport['width']}.png")


@BOTH
def test_every_item_sits_at_its_start_and_is_as_tall_as_it_lasts_and_items_at_one_time_share_a_y(signed_in, viewport):
    page = week(signed_in, viewport)
    m = page.evaluate(RECTS)
    ys = sorted(l["y"] for l in m["labels"])
    hh = ys[1] - ys[0]
    base = m["labels"][0]["y"] + m["labels"][0]["h"] / 2      # the 7 AM line: a label is centred on its hour line
    assert len(m["items"]) == 10      # the sample trip's four bookings and the six plans
    for it in m["items"]:
        want_top = base + (it["s"] - 420) / 60 * hh
        assert abs(it["y"] - want_top) <= 1.5, (it["title"], it["y"], want_top)
        drawn = max(it["e"] - it["s"], 30)
        assert abs(it["h"] - drawn / 60 * hh) <= 2, (it["title"], it["h"], drawn / 60 * hh)
    lunch = {i["day"]: i for i in m["items"] if i["s"] == 12 * 60 + 30}
    assert abs(lunch[1]["y"] - lunch[2]["y"]) < 0.5      # 12:30 on Saturday and on Sunday: the same y
    assert len({round(i["y"], 0) for i in m["items"] if i["s"] == 12 * 60 + 30 and i["day"] in (1, 2)}) == 1
    flight = next(i for i in m["items"] if i["title"].endswith("SFO → LAX"))
    assert abs(flight["y"] - (base + (flight["s"] - 420) / 60 * hh)) <= 1.5      # a booking too


@BOTH
def test_no_card_overlaps_another_and_every_card_stays_inside_its_column(signed_in, viewport):
    page = week(signed_in, viewport)
    m = page.evaluate(RECTS)
    cols = {i: c for i, c in enumerate(m["cols"])}
    for a in m["items"]:
        c = cols[a["day"]]
        assert c["x"] - 0.5 <= a["x"] and a["r"] <= c["r"] + 0.5 and a["w"] > 40, a["title"]
    for i, a in enumerate(m["items"]):
        for b in m["items"][i + 1:]:
            if a["day"] != b["day"]:
                continue
            across = min(a["r"], b["r"]) - max(a["x"], b["x"])
            down = min(a["b"], b["b"]) - max(a["y"], b["y"])
            assert not (across > 0.5 and down > 0.5), (a["title"], b["title"])      # two plans at the same time sit side by side, never over one another
    same = [i for i in m["items"] if i["day"] == 1 and i["s"] == 12 * 60 + 30]
    assert len(same) == 2 and abs(same[0]["x"] - same[1]["x"]) > 20 and abs(same[0]["w"] - same[1]["w"]) < 1      # lanes of equal width


@BOTH
def test_card_text_is_inside_its_card(signed_in, viewport):
    page = week(signed_in, viewport)
    bad = page.evaluate("""() => [...document.querySelectorAll('.cz-wcol .cz-wi')].flatMap(card => { const c = card.getBoundingClientRect();
        return [...card.querySelectorAll('.cz-wi-ico, .cz-wi-t, .cz-wi-time, .cz-wi-tag')].filter(n => n.getClientRects().length && getComputedStyle(n).display !== 'none').map(n => { const b = n.getBoundingClientRect();
          return { card: card.querySelector('.cz-wi-t').textContent, part: n.className, in: b.left >= c.left - 0.5 && b.right <= c.right + 0.5 && b.top >= c.top - 0.5 && b.bottom <= c.bottom + 0.5, wide: n.scrollWidth > n.clientWidth + 1 }; }); })
        .filter(x => !x.in || (x.wide && x.part.includes('time')))""")
    assert bad == [], bad
    texts = page.evaluate("[...document.querySelectorAll('.cz-wi-time')].filter(n => n.getClientRects().length).map(n => n.textContent.trim())")
    assert "12:30 – 2:00 PM" in texts      # the true time, printed in the card


@BOTH
def test_cards_are_kind_filled_with_the_kinds_edge_and_tile_and_a_grey_pill(signed_in, viewport):
    page = week(signed_in, viewport)
    lunch = page.locator(".cz-wi", has_text="Lunch at Grand Central Market")
    brunch = page.locator(".cz-wi", has_text="Sunday brunch")
    museum = page.locator(".cz-wi", has_text="Griffith Observatory")
    for card, (edge, tint) in ((lunch, KINDS["food"]), (brunch, KINDS["outdoors"]), (museum, KINDS["culture"])):
        assert card.evaluate("n => getComputedStyle(n).backgroundColor") == tint      # F-167: filled with the kind's tint
        assert f"{edge} 3px 0px 0px 0px inset" in card.evaluate("n => getComputedStyle(n).boxShadow")
        assert card.locator(".cz-wi-ico").evaluate("n => getComputedStyle(n).backgroundColor") == CARD
        assert card.locator(".cz-wi-ico svg").count() == 1
    expect(lunch.locator(".cz-wi-tag")).to_have_text("Plan")
    assert lunch.locator(".cz-wi-tag").evaluate("n => [getComputedStyle(n).backgroundColor, getComputedStyle(n).color]") == ["rgb(250, 247, 242)", "rgb(74, 68, 96)"]
    flight = page.locator(".cz-wi.is-booked", has_text="· SFO → LAX")
    hotel = page.locator(".cz-wi.is-booked", has_text="Check in")
    for card, (edge, tint) in ((flight, KINDS["travel"]), (hotel, KINDS["culture"])):
        assert f"{edge} 3px 0px 0px 0px inset" in card.evaluate("n => getComputedStyle(n).boxShadow")
        assert card.locator(".cz-wi-ico").evaluate("n => getComputedStyle(n).backgroundColor") == CARD
        expect(card.locator(".cz-wi-tag")).to_have_text("Booked")
    shot(page, f"cards-{viewport['width']}.png")


@BOTH
def test_column_headers_are_neutral_and_a_free_day_is_a_soft_dashed_slot(signed_in, viewport):
    page = week(signed_in, viewport)
    heads = page.evaluate("""() => [...document.querySelectorAll('.cz-wcol')].map(c => { const h = c.querySelector('.cz-wh'), s = getComputedStyle(h);
        return { bg: s.backgroundColor, text: h.textContent.replace(/\\s+/g, ' ').trim(), cls: c.className, pill: getComputedStyle(h.querySelector('.cz-wh-no, .cz-wh-today')).backgroundColor, dow: getComputedStyle(h.querySelector('.cz-wh-day')).color }; })""")
    assert len(heads) == 5
    assert all(h["bg"] in ("rgba(0, 0, 0, 0)", CARD) and "cz-wt-" not in h["cls"] for h in heads), heads      # no day colour
    assert len({h["dow"] for h in heads}) == 1 and len({h["pill"] for h in heads}) <= 2      # the same ink for every day (today's pill is the one other)
    assert heads[0]["text"].startswith("Fri 16") and "Fly in, check in" in heads[0]["text"] and heads[1]["text"].startswith("Sat 17")
    free = page.locator(".cz-wcol[data-day='3'] .cz-wfree")
    expect(free).to_contain_text("Free day")
    expect(free.get_by_role("link", name="Say the plan")).to_be_visible()
    assert free.evaluate("n => getComputedStyle(n).borderTopStyle") == "dashed"
    f, col = free.bounding_box(), page.locator(".cz-wcol[data-day='3']").bounding_box()
    assert f["height"] > 150 and f["x"] > col["x"] and f["x"] + f["width"] < col["x"] + col["width"]      # a slot in the column, not a strip
    assert page.locator(".cz-wcol[data-day='1'] .cz-wfree").count() == 0


@BOTH
def test_clicking_a_days_header_opens_that_day_and_a_plan_opens_the_day_with_the_plan(signed_in, viewport):
    page = week(signed_in, viewport)
    page.locator(".cz-wcol[data-day='2'] .cz-wh").click()
    page.wait_for_selector(".cz-view[data-level=day][data-day='2']")
    assert "day=2" in page.url and "plan=" not in page.url
    page.locator("#cz-z-week").click()
    page.wait_for_selector(".cz-view[data-level=week]")
    page.locator(".cz-wi", has_text="Lunch at Grand Central Market").click()
    page.wait_for_selector(".cz-view[data-level=day][data-day='1']")
    assert "day=1&plan=" in page.url


def test_a_packed_day_still_fits_the_window_with_no_page_scroll(signed_in):
    page = signed_in(LAPTOP, path="/trip/canvas")
    me = person("ari")
    for h in range(7, 22):
        cal.add_activity(me, day=1, start=h * 60, end=h * 60 + 60, title=f"Stop {h}", kind="fun")
        cal.add_activity(me, day=1, start=h * 60, end=h * 60 + 30, title=f"Side {h}", kind="food")
    page.reload()
    page.wait_for_selector("#cz-wk .cz-wi")
    assert page.evaluate(NO_SCROLL)
    m = page.evaluate(RECTS)
    assert m["wk"]["b"] <= 800


@BOTH
def test_a_card_too_short_for_its_title_shows_it_whole_while_it_is_pointed_at(signed_in, viewport):
    page = week(signed_in, viewport)
    card = page.locator(".cz-wi", has_text="Ice cream on the pier")      # 30 minutes: one row, the title fades if it does not fit
    title = card.locator(".cz-wi-t")
    before = card.bounding_box()
    card.hover()
    after = card.bounding_box()
    assert title.evaluate("n => n.scrollWidth <= n.clientWidth + 1 && getComputedStyle(n).whiteSpace === 'normal'")
    assert after["y"] == before["y"] and after["height"] >= before["height"]      # it grows down from its own start, never up over the card above
    page.mouse.move(5, 5)
    assert abs(card.bounding_box()["height"] - before["height"]) < 0.5      # and folds back


@BOTH
def test_a_filter_hides_the_cards_that_do_not_match_and_the_axis_stays(signed_in, viewport):
    page = week(signed_in, viewport)
    page.locator(".cz-kchip", has_text="Hotels").click()
    expect(page.locator(".cz-wi.is-plan:visible")).to_have_count(0)
    expect(page.locator(".cz-wi.is-booked:visible")).to_have_count(2)      # the sample trip's check in and check out
    expect(page.locator(".cz-wcol[data-day='1'] .cz-wnone")).to_have_text("Nothing for hotels")
    expect(page.locator(".cz-wax-h").first).to_be_visible()


@BOTH
def test_a_short_plan_at_the_end_of_the_day_does_not_stretch_the_axis(signed_in, viewport):
    """A 15 minute plan at 9:45 PM keeps the 30 minute floor, but must not push the axis past 10 PM (it would shrink every hour): the card moves its top up to 9:30 and ends at the axis end; its label says 9:45 PM."""
    page = signed_in(viewport, path="/trip/canvas")
    cal.add_activity(person("ari"), day=2, start=21 * 60 + 45, end=22 * 60, title="Last call at the bar", kind="food", fine=True)
    page.reload()
    page.wait_for_selector("#cz-wk .cz-wi")
    m = page.evaluate(RECTS)
    assert m["labels"][-1]["hr"] == 22 * 60 and len(m["labels"]) == 16      # still 7 AM to 10 PM
    last = next(i for i in m["items"] if i["title"] == "Last call at the bar")
    line = m["labels"][-1]["y"] + m["labels"][-1]["h"] / 2
    hh = m["labels"][1]["y"] - m["labels"][0]["y"]
    assert abs(last["y"] - (line - hh / 2)) <= 1.5 and abs(last["b"] - line) <= 1.5 and abs(last["h"] - hh / 2) <= 2      # 9:30 to 10 PM: 30 minutes tall, on the axis
    inside = page.evaluate("""() => { const c = document.querySelector('.cz-wi[data-s="1305"]'), b = c.getBoundingClientRect(), t = c.querySelector('.cz-wi-t').getBoundingClientRect(), w = c.querySelector('.cz-wi-time').getBoundingClientRect();
        return [t, w].every(r => r.top >= b.top - 0.5 && r.bottom <= b.bottom + 0.5 && r.left >= b.left - 0.5 && r.right <= b.right + 0.5) && c.querySelector('.cz-wi-time').textContent.trim() }""")
    assert inside == "9:45 PM"      # the title and the true time sit inside the card
    assert page.evaluate("(w => w.scrollHeight <= w.clientHeight)(document.querySelector('#cz-wk'))")


@BOTH
def test_titles_cut_while_hidden_by_a_filter_are_faded_when_shown_again_even_after_a_reload(signed_in, viewport):
    page = signed_in(viewport, path="/trip/canvas")
    me = person("ari")
    for t, k in (("Breakfast then the Griffith Observatory", "culture"), ("Beach volleyball tournament", "fun"), ("Boogie boarding", "outdoors")):
        cal.add_activity(me, day=1, start=9 * 60, end=11 * 60, title=t, kind=k)
    page.reload()
    page.wait_for_selector("#cz-wk .cz-wi")
    page.locator(".cz-kchip", has_text="Hotels").click()      # the plans are hidden (they measure 0)
    page.reload()                                              # the filter is remembered: the page loads with them hidden
    page.wait_for_selector("#cz-wk .cz-wi", state="attached")
    page.locator(".cz-kchip", has_text="All").click()
    expect(page.locator(".cz-wcol[data-day='1'] .cz-wi:visible")).to_have_count(3)
    page.wait_for_function("() => document.querySelectorAll('.cz-wcol[data-day=\"1\"] .cz-wi-t.is-cut').length >= 2")
    bad = page.evaluate("""() => [...document.querySelectorAll('.cz-wi-t')].filter(t => t.clientWidth && (t.scrollHeight > t.clientHeight + 1 || t.scrollWidth > t.clientWidth + 1) && !(t.classList.contains('is-cut') && getComputedStyle(t).maskImage !== 'none')).map(t => t.textContent)""")
    assert bad == [], bad


@BOTH
def test_a_title_that_does_not_fit_is_faded_not_silently_cut_and_breaks_at_spaces(signed_in, viewport):
    page = signed_in(viewport, path="/trip/canvas")
    me = person("ari")
    cal.add_activity(me, day=1, start=9 * 60, end=11 * 60, title="Breakfast then the Griffith Observatory", kind="culture")
    cal.add_activity(me, day=1, start=9 * 60, end=11 * 60, title="Beach volleyball tournament", kind="fun")
    cal.add_activity(me, day=1, start=9 * 60, end=11 * 60, title="Boogie boarding", kind="outdoors")
    cal.add_activity(me, day=2, start=9 * 60, end=11 * 60, title="Breakfast then lunch at the Griffith", kind="food")
    cal.add_activity(me, day=2, start=9 * 60, end=11 * 60, title="Boogie boarding", kind="outdoors")
    page.reload()
    page.wait_for_selector("#cz-wk .cz-wi")
    got = page.evaluate("""() => [...document.querySelectorAll('.cz-wcol[data-day="1"] .cz-wi-t, .cz-wcol[data-day="2"] .cz-wi-t')].map(t => ({ title: t.textContent, cut: t.scrollHeight > t.clientHeight + 1 || t.scrollWidth > t.clientWidth + 1, marked: t.classList.contains('is-cut'), mask: getComputedStyle(t).maskImage !== 'none',
        brokenWord: (() => { const r = document.createRange(); r.selectNodeContents(t); const lines = new Map(); const w = t.textContent.split(' '); return w.some(word => word.length < 12 && (() => { const i = t.textContent.indexOf(word); const a = document.createRange(); a.setStart(t.firstChild, i); a.setEnd(t.firstChild, i + word.length); return a.getClientRects().length > 1; })()); })() }))""")
    assert len(got) == 5 and any(g["cut"] for g in got)      # the narrow lanes cut the long ones
    assert all(g["marked"] and g["mask"] for g in got if g["cut"]), got
    two = [g for g in got if g["title"].startswith("Breakfast then lunch")][0]
    assert not two["brokenWord"], two      # in a half column a word that fits is never split across two lines (in three lanes a long word has to break)
