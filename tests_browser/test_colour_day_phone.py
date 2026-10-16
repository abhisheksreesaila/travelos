"""F-160: the phone and tablet day as a colour timeline (the same rail, start times, cards, tiles and neutral day chips as the laptop's F-159), pinned in a real browser at 390 and 800.
Rules: docs/design/colour-timeline.md, design-system/DESIGN-SYSTEM.md "The colour timeline". Screenshots on request: F160_SHOTS=<folder>.
The phone keeps its 44px target per plan (test_day_grid.py), so a plan under 45 minutes is a compact row at least 44px tall: cards may touch each other on a crowded day, labels never may."""
import os

import pytest
from playwright.sync_api import expect

from gitaway import tripcal as cal
from tests.test_signin import person
from tests_browser.helpers import PHONE
from tests_browser.test_day_dock import SAT_NOON, at
from tests_browser.test_colour_day import CARD, CORALS, GEOMETRY, GRAPE, INK, INK_2, MINT, NO_SCROLL, PAPER_2, SKY, SUN, SUN_INK, SUN_TINT, crowd, day, hits, style
from tests_browser.test_topbar import TABLET, signed_in  # noqa: F401 - fixture

BOTH = pytest.mark.parametrize("viewport", [PHONE, TABLET], ids=["390", "800"])


def shot(page, name, full=True):
    if os.environ.get("F160_SHOTS"):
        page.screenshot(path=os.path.join(os.environ["F160_SHOTS"], name), full_page=full)


def edge(card, color):
    """The card's left edge in the kind's colour: an inset shadow 3px wide on a laptop's 12px root, 4px on a phone's 16px root (the same 0.25rem)."""
    shadow = card.evaluate("e => getComputedStyle(e).boxShadow")
    return any(f"{color} {w}px 0px 0px 0px inset" in shadow for w in (3, 4))


@BOTH
def test_plans_and_bookings_are_white_cards_with_a_kind_tile_and_edge(signed_in, viewport):
    page = day(signed_in, viewport)
    lunch = page.locator(".cz-gb", has_text="Lunch at Grand Central Market")
    sunset = page.locator(".cz-gb", has_text="Santa Monica Pier sunset")
    for card, accent, tint, ink in ((lunch, SUN, SUN_TINT, SUN_INK), (sunset, MINT, "rgb(212, 247, 234)", "rgb(22, 134, 95)")):
        assert card.evaluate("e => getComputedStyle(e).backgroundColor") == CARD
        assert card.evaluate("e => getComputedStyle(e).borderTopWidth") == "1px"
        assert edge(card, accent), card.evaluate("e => getComputedStyle(e).boxShadow")      # the kind's left edge
        tile = card.locator(".cz-gb-tile")
        expect(tile).to_be_visible()
        assert tile.evaluate("e => getComputedStyle(e).backgroundColor") == tint
        assert tile.evaluate("e => getComputedStyle(e).color") == ink
        assert tile.locator("svg").count() == 1
    flight = page.locator(".cz-gbk", has_text="Skylark")
    hotel = page.locator(".cz-gbk", has_text="Check in")
    for card, accent, tint in ((flight, SKY, "rgb(221, 238, 255)"), (hotel, GRAPE, "rgb(236, 228, 255)")):
        assert card.evaluate("e => getComputedStyle(e).backgroundColor") == CARD
        assert edge(card, accent), card.evaluate("e => getComputedStyle(e).boxShadow")
        assert card.locator(".cz-gbk-tile").evaluate("e => getComputedStyle(e).backgroundColor") == tint
        pill = card.locator(".cz-bk-tag")
        expect(pill).to_have_text("Booked")
        assert pill.evaluate("e => [getComputedStyle(e).backgroundColor, getComputedStyle(e).color, getComputedStyle(e).textTransform]") == [PAPER_2, INK_2, "uppercase"]
    plan_pill = lunch.locator(".cz-gb-tag")
    expect(plan_pill).to_have_text("Plan")
    assert plan_pill.evaluate("e => [getComputedStyle(e).backgroundColor, getComputedStyle(e).color]") == [PAPER_2, INK_2]
    assert style(page, ".cz-day-body", "backgroundColor", "borderTopColor", "borderTopWidth") == [CARD, "rgba(30, 26, 46, 0.1)", "1px"]      # the day panel: white with a hairline
    shot(page, f"day-{viewport['width']}.png")
    assert page.evaluate(NO_SCROLL.split(" && ")[0])


@BOTH
def test_every_item_prints_its_start_on_the_rail_and_no_label_overlaps(signed_in, viewport):
    page = day(signed_in, viewport, short=True)
    got = page.evaluate("""() => {
      const rect = e => { const r = e.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; };
      const starts = [...document.querySelectorAll('.cz-g-start')].map(e => ({text: e.querySelector('.cz-g-st-t').textContent + ' ' + e.querySelector('.cz-g-st-m').textContent, r: rect(e), shown: getComputedStyle(e).display !== 'none',
        big: parseFloat(getComputedStyle(e.querySelector('.cz-g-st-t')).fontSize), weight: getComputedStyle(e.querySelector('.cz-g-st-t')).fontWeight}));
      const hours = [...document.querySelectorAll('.cz-g-hour')].filter(e => getComputedStyle(e).display !== 'none').map(e => ({text: e.textContent, r: rect(e), size: parseFloat(getComputedStyle(e).fontSize)}));
      return {starts, hours};
    }""")
    assert sorted(s["text"] for s in got["starts"]) == ["10:00 AM", "12:30 PM", "3:00 PM", "5:30 PM", "8:05 AM"]
    for s in got["starts"]:
        assert s["shown"] and s["weight"] == "800" and s["big"] >= 1.4 * got["hours"][0]["size"], s
    boxes = [(f"start {s['text']}", s["r"]) for s in got["starts"]] + [(f"hour {h['text']}", h["r"]) for h in got["hours"]]
    for i, (na, a) in enumerate(boxes):
        for nb, b in boxes[i + 1:]:
            assert a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1], f"{na} overlaps {nb}"
    shown = {h["text"] for h in got["hours"]}
    assert not shown & {"8 AM", "10 AM", "12 PM", "1 PM", "3 PM", "5 PM", "6 PM"}      # each is within 30 minutes of a printed start
    assert {"7 AM", "9 AM", "11 AM", "2 PM", "4 PM", "7 PM"} <= shown


@BOTH
def test_the_rail_is_a_hairline_and_a_start_has_a_dot_in_its_kinds_colour(signed_in, viewport):
    page = day(signed_in, viewport)
    rail = page.locator(".cz-g-zoom").evaluate("e => { const s = getComputedStyle(e, '::before'); return [s.content, s.width, s.backgroundColor]; }")
    assert rail == ['""', "1px", "rgba(30, 26, 46, 0.1)"], rail
    dot = page.locator(".cz-g-start", has_text="12:30").locator(".cz-g-st-dot")
    assert dot.evaluate("e => getComputedStyle(e).backgroundColor") == SUN


@BOTH
def test_day_chips_are_neutral_pills_and_the_ink_day_header_and_coloured_chips_are_gone(signed_in, viewport):
    page = day(signed_in, viewport)
    assert page.locator(".cz-dpills, .cz-strip").count() == 0      # the coloured dates and the tablet's week strip: the neutral chips replace both
    head = style(page, ".cz-view[data-day] .cz-head", "backgroundColor", "boxShadow", "color")
    assert head[0] == "rgba(0, 0, 0, 0)" and head[1] == "none" and head[2] == INK, head      # no ink card
    chips = page.locator(".cz-hchip")
    expect(chips).to_have_count(5)
    got = chips.evaluate_all("""els => els.map(e => { const s = getComputedStyle(e), r = e.getBoundingClientRect(); return {open: e.classList.contains('is-open'), bg: s.backgroundColor, color: s.color,
      radius: parseFloat(s.borderTopLeftRadius), h: r.height, w: r.width, before: getComputedStyle(e, '::before').content, shown: r.width > 0}; })""")
    assert [g["open"] for g in got] == [True, False, False, False, False]
    assert got[0]["bg"] == INK and got[0]["color"] == CARD
    for g in got[1:]:
        assert g["bg"] == CARD and g["color"] == INK, g
    for g in got:
        assert g["before"] in ("none", "normal") and g["radius"] >= g["h"] / 2 - 1 and g["shown"], g      # a pill, no coloured key
    expect(page.locator(".cz-hchip.is-open .cz-hc-head")).to_have_text("Fly in · check in")
    assert page.locator(".cz-hchip:not(.is-open) .cz-hc-head").first.evaluate("e => e.getBoundingClientRect().width <= 2")      # the other titles stay for a screen reader
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")


def test_a_tapped_chip_opens_its_day(signed_in):
    page = day(signed_in, PHONE)
    page.locator(".cz-hchip", has_text="17").click()
    expect(page.locator(".cz-view[data-day]")).to_have_attribute("data-day", "1")
    expect(page.locator(".cz-hchip.is-open")).to_contain_text("17")


@BOTH
def test_text_is_never_under_13px_and_targets_are_at_least_44px(signed_in, viewport):
    page = day(signed_in, viewport, short=True)
    got = page.evaluate("""() => {
      const seen = (e, r) => r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== 'hidden' && !(r.width <= 2 && r.height <= 2);
      const small = [], tiny = [];
      document.querySelectorAll('.cz-view[data-day] *, .ph-tabs *, .cz-fold *').forEach(e => {
        const r = e.getBoundingClientRect(); if (!seen(e, r) || e.closest('.ga-tb-pop')) return;      // (the closed trip menu waits above the screen)
        const text = [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
        if (text && parseFloat(getComputedStyle(e).fontSize) < 12.99) small.push(e.className.toString() + ' ' + e.textContent.trim().slice(0, 20) + ' ' + getComputedStyle(e).fontSize);
      });
      document.querySelectorAll('.cz-hchip, .cz-kchip, .cz-back, .cz-mapbtn, .cz-head .cz-sos, .cz-gb, .cz-gbk, .cz-seg').forEach(e => {
        const r = e.getBoundingClientRect(); if (!seen(e, r) || e.closest('.cz-fold')) return;
        if (r.height < 43.5 || r.width < 43.5) tiny.push(e.className.toString() + ' ' + Math.round(r.width) + 'x' + Math.round(r.height));
      });
      return {small, tiny};
    }""")
    assert got["small"] == [], got["small"]
    assert got["tiny"] == [], got["tiny"]


@BOTH
def test_the_day_is_one_column_under_the_heading(signed_in, viewport):
    page = day(signed_in, viewport)
    body, main = page.locator(".cz-day-body").bounding_box(), page.locator(".cz-day-main").bounding_box()
    assert main["width"] >= body["width"] * 0.9, (body, main)      # the Set aside tray is under the day, never beside it
    assert page.locator(".cz-view[data-day]").evaluate("e => e.scrollWidth <= e.clientWidth")
    heads = page.evaluate("""() => ['.cz-head', '.cz-hchips', '.cz-bar', '#cz-grid'].map(s => { const e = document.querySelector('.cz-view[data-day] ' + s); const r = e && e.getBoundingClientRect(); return r && r.width ? Math.round(r.top) : null; })""")
    assert heads[0] is not None and heads[3] is not None and heads[0] < heads[3], heads


@BOTH
def test_coral_is_only_the_primary_buttons_and_the_now_line(signed_in, viewport):
    page = day(signed_in, viewport)
    bad = page.evaluate("""corals => [...document.querySelectorAll('.cz-view[data-day] *')].filter(e => {
        const r = e.getBoundingClientRect(), s = getComputedStyle(e);
        if (!r.width || !r.height || s.visibility === 'hidden' || s.display === 'none') return false;
        const paints = [s.color, s.backgroundColor, s.borderTopColor, s.borderLeftColor].filter(c => corals.includes(c));
        return paints.length && !e.closest('.cz-desk-btn, .cz-dock-btn, .tp-btn, .cz-nowline, .cz-ask-mic, .cz-compose-go, .cz-sos');
      }).map(e => e.className.toString() + ' ' + (e.textContent || '').trim().slice(0, 20))""", list(CORALS))
    assert bad == [], bad


@BOTH
def test_a_short_plan_keeps_its_title_on_one_line_inside_its_card(signed_in, viewport):
    page = day(signed_in, viewport, short=True)
    card = page.locator(".cz-gb", has_text="Coffee at the corner")
    title = card.locator(".cz-gb-t")
    assert title.evaluate("e => e.getBoundingClientRect().height") <= title.evaluate("e => parseFloat(getComputedStyle(e).lineHeight)") * 1.2
    inside = card.evaluate("""e => { const c = e.getBoundingClientRect(); return [...e.querySelectorAll('.cz-gb-tile, .cz-gb-tag, .cz-gb-when')].filter(x => getComputedStyle(x).display !== 'none')
      .map(x => { const r = x.getBoundingClientRect(); return r.top >= c.top - 0.5 && r.bottom <= c.bottom + 0.5 && r.right <= c.right + 0.5; }); }""")
    assert inside and all(inside), inside


@BOTH
def test_a_crowded_day_never_overlaps_rail_labels_or_hours(signed_in, viewport):
    page = signed_in(viewport, path="/trip/canvas?day=0")
    crowd()
    page.reload()
    expect(page.locator(".cz-gb").first).to_be_visible()
    got = page.evaluate(GEOMETRY)
    for i, a in enumerate(got["marks"]):
        for b in got["marks"][i + 1:]:
            assert not hits(a, b), f"{a['name']} overlaps {b['name']}"
    for c in got["cards"]:
        inside = lambda r: r["t"] >= c["t"] - 0.5 and r["b"] <= c["b"] + 0.5 and r["r"] <= c["r"] + 0.5      # noqa: E731
        if c["when"]:
            assert inside(c["when"]), f"{c['name']}: time outside its card {c}"
        if c["tile"]:
            assert inside(c["tile"]), f"{c['name']}: tile outside its card {c}"
    for d in got["drift"]:
        assert d["below"] is None or -0.5 <= d["below"] <= 8, d      # a start label never sits more than a few px below its own card's top
    starts = page.locator(".cz-g-start").all_inner_texts()
    assert len([s for s in starts if s.replace("\n", " ") == "8:00 PM"]) == 1      # two plans at the same minute share one label
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    shot(page, f"crowd-{viewport['width']}.png")


@BOTH
def test_a_run_of_short_plans_keeps_each_label_by_its_card_and_the_hours_visible(signed_in, viewport):
    page = signed_in(viewport, path="/trip/canvas?day=0")
    me = person("ari")
    for i, title in enumerate(("Stop one", "Stop two", "Stop three", "Stop four")):
        start = 9 * 60 + 15 + 15 * i
        cal.add_activity(me, day=0, start=start, end=start + 15, title=title, kind="fun", fine=True)
    page.reload()
    expect(page.locator(".cz-gb").first).to_be_visible()
    got = page.evaluate(GEOMETRY)
    assert got["drift"], got
    for i, a in enumerate(got["marks"]):
        for b in got["marks"][i + 1:]:
            assert not hits(a, b), f"{a['name']} overlaps {b['name']}"
    for d in got["drift"]:
        assert d["below"] is None or -0.5 <= d["below"] <= 8, d
    for c in got["cards"]:
        if c["when"]:
            assert c["t"] - 0.5 <= c["when"]["t"] and c["when"]["b"] <= c["b"] + 0.5, f"{c['name']}: its time shows inside the card ({c})"
    shown = {m["name"] for m in got["marks"]}
    assert {"hour 11 AM", "hour 1 PM", "hour 2 PM", "hour 4 PM"} <= shown
    shot(page, f"run-{viewport['width']}.png")


@BOTH
def test_on_today_the_ink_up_next_card_sits_above_the_day_in_one_column(signed_in, viewport, monkeypatch):
    at(monkeypatch, SAT_NOON)
    page = signed_in(viewport, path="/trip/canvas?day=1")
    page.reload()
    expect(page.locator(".cz-now")).to_be_visible()
    up, panel = page.locator(".cz-now").bounding_box(), page.locator(".cz-day-body").bounding_box()
    chips = page.locator(".cz-hchips").bounding_box()
    assert chips["y"] + chips["height"] <= up["y"] + 1 and up["y"] + up["height"] <= panel["y"] + 1      # chips, then Up next, then the day
    assert abs(up["width"] - panel["width"]) <= 2      # the one column
    assert page.locator(".cz-now .cz-up, .cz-now [id=tp-up]").first.evaluate("e => getComputedStyle(e).backgroundColor") == INK      # the one ink card
    assert page.locator(".cz-hchip.is-today").count() == 1
    shot(page, f"today-{viewport['width']}.png")
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")


def test_the_folded_bar_still_comes_in_when_the_top_has_scrolled_away(signed_in):
    page = day(signed_in, PHONE)
    page.evaluate("window.scrollTo(0, 400)")
    expect(page.locator(".cz-fold.is-on")).to_have_count(1)
    assert page.locator(".cz-fold-bar").evaluate("e => getComputedStyle(e).backgroundColor") == CARD      # no ink bar either
    shot(page, "folded-390.png")
    page.evaluate("window.scrollTo(0, 0)")
    expect(page.locator(".cz-fold.is-on")).to_have_count(0)


TAPPABLE = """() => [...document.querySelectorAll('.cz-gb:not(.is-new):not(.is-more), .cz-gbk:not(.is-pill), .cz-lanemore')].map(e => {
  e.scrollIntoView({block: 'center'}); const r = e.getBoundingClientRect(), x = r.left + r.width / 2; let seen = 0;      // (centred, clear of the tab bar)
  for (let y = Math.ceil(r.top); y < r.bottom; y++) { const hit = document.elementFromPoint(x, y + 0.5); if (hit && e.contains(hit)) seen++; }
  const start = e.dataset.act ? e.querySelector('.cz-gb-when, .cz-gb-st') : null;
  const shown = [...e.querySelectorAll('.cz-gb-when, .cz-gb-st')].filter(n => getComputedStyle(n).display !== 'none');
  const clipped = [...e.querySelectorAll('.cz-gb-when, .cz-gb-st, .cz-gb-t')].filter(n => getComputedStyle(n).display !== 'none' && n.scrollWidth > n.clientWidth + 1).map(n => n.className);
  return {id: e.dataset.act || e.dataset.zk, name: e.textContent.trim().slice(0, 16), l: r.left, t: r.top + scrollY, r: r.right, b: r.bottom + scrollY, tappable: seen, timeShown: shown.length > 0, clipped,
    near: [...document.querySelectorAll('.cz-g-start')].some(s => (s.dataset.for || '').split(' ').includes(e.dataset.act || '') && getComputedStyle(s).display !== 'none')};
})"""


def crowded(page):
    crowd()
    me = person("ari")
    for i, title in enumerate(("Stop one", "Stop two", "Stop three", "Stop four")):
        start = 9 * 60 + 15 + 15 * i
        cal.add_activity(me, day=0, start=start, end=start + 15, title=title, kind="fun", fine=True)
    cal.add_activity(me, day=0, start=15 * 60 + 30, end=16 * 60, title="Gelato", kind="food")      # beside the hotel's slim booking pill
    cal.add_activity(me, day=0, start=15 * 60 + 40, end=16 * 60 + 10, title="Souvenirs", kind="fun")
    page.reload()
    expect(page.locator(".cz-gb").first).to_be_visible()


@BOTH
def test_no_card_overlaps_another_and_each_is_a_44px_tap_area_with_its_start_in_view(signed_in, viewport):
    page = signed_in(viewport, path="/trip/canvas?day=0")
    crowded(page)
    cards = page.evaluate(TAPPABLE)
    for i, a in enumerate(cards):
        for b in cards[i + 1:]:
            assert min(a["r"], b["r"]) - max(a["l"], b["l"]) <= 1 or min(a["b"], b["b"]) - max(a["t"], b["t"]) <= 1, f"{a['name']} overlaps {b['name']}"
        assert a["tappable"] >= 43.5, f"{a['name']}: only {a['tappable']}px of it can be tapped"
        assert a["clipped"] == [], f"{a['name']}: text cut off {a['clipped']}"
        if a["id"] and a["id"].startswith("a"):
            assert a["near"] or a["timeShown"], f"{a['name']}: nothing shows when it starts"
    shot(page, f"crowd2-{viewport['width']}.png")
    page.evaluate("window.scrollTo(0, 330)")
    shot(page, f"crowd2-view-{viewport['width']}.png", full=False)
    page.evaluate("window.scrollTo(0, 0)")
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")


@BOTH
def test_a_short_title_with_room_is_not_cut_or_faded(signed_in, viewport):
    page = signed_in(viewport, path="/trip/canvas?day=0")
    crowd()
    page.reload()
    title = page.locator(".cz-gb", has_text="Bakery run").locator(".cz-gb-t")
    got = title.evaluate("""e => { const r = document.createRange(); r.selectNodeContents(e); const w = r.getBoundingClientRect(), b = e.getBoundingClientRect(), pad = parseFloat(getComputedStyle(e).paddingRight);
      return {textRight: w.right, edge: b.right - pad, pad, fade: getComputedStyle(e).webkitMaskImage}; }""")
    assert got["textRight"] <= got["edge"] + 0.5, got      # all of "Bakery run" is left of where the fade starts
