"""F-161: adding and moving in the colour timeline's look, driven in a real browser at 390 (phone), 800 (tablet) and 1440 (laptop, a real mouse).
Rules: docs/design/colour-timeline.md (States: Adding, Moving), design-system/DESIGN-SYSTEM.md "The colour timeline". Screenshots on request: F161_SHOTS=<folder>.

Moving: a faint dashed ghost stays at the plan's old slot, a dashed landing slot shows where it will drop, the rail's start time turns coral and follows the snapped time while the old one is dimmed,
and on a laptop a day chip under the mouse says "Drop to move to <day>". Adding: the draft opens in the touched gap with a dashed coral edge, its title field focused, the kinds' chips in their
colours and its rail time in coral. Everything is measured with real rectangles: the landing slot's top is the snapped minute on the grid, and the rail's live time sits on it.
The behaviour (thresholds, saves, undo, viewers) is pinned by the older day tests, which run unchanged."""
import os

import pytest
from playwright.sync_api import expect

from gitaway import tripcal as cal
from tests.test_signin import person
from tests_browser.helpers import DESKTOP, PHONE
from tests_browser.test_colour_day import CARD, day
from tests_browser.test_colour_day_phone import crowded
from tests_browser.test_day_grid import fire, show, slide
from tests_browser.test_topbar import TABLET, signed_in  # noqa: F401 - fixture

CORAL, CORAL_DEEP, INK_2 = "rgb(255, 115, 82)", "rgb(201, 67, 31)", "rgb(74, 68, 96)"
HOW = pytest.mark.parametrize("viewport", [PHONE, TABLET, DESKTOP], ids=["390", "800", "1440"])
KIND_COLOURS = {"fun": ["rgb(255, 227, 241)", "rgb(194, 59, 130)"], "food": ["rgb(255, 241, 194)", "rgb(138, 98, 0)"], "outdoors": ["rgb(212, 247, 234)", "rgb(22, 134, 95)"],
                "culture": ["rgb(236, 228, 255)", "rgb(106, 79, 214)"], "travel": ["rgb(221, 238, 255)", "rgb(27, 111, 201)"]}

GEO = """() => { const g = document.querySelector('#cz-grid'), z = g.querySelector('.cz-g-zoom'), lo = +g.dataset.lo, hi = +g.dataset.hi;
  return { top: z.getBoundingClientRect().top, ppm: z.offsetHeight / (hi - lo), lo }; }"""

# what the grid shows of one plan's move: the ghost, the landing slot, the rail's live and dimmed start, every in tops of real rectangles
MOVE = """(act) => {
  const g = document.querySelector('#cz-grid'), rect = e => { const b = e.getBoundingClientRect(); return { top: b.top, height: b.height, left: b.left, width: b.width }; };
  const ghost = g.querySelector('.cz-g-ghost'), land = g.querySelector('.cz-g-land'), live = g.querySelector('.cz-g-start.is-live'), card = g.querySelector('.cz-gb[data-act="' + act + '"]');
  const was = [...g.querySelectorAll('.cz-g-start.is-was')], css = (e, ...p) => { const s = getComputedStyle(e); return p.map(k => s[k]); };
  return { ghosts: g.querySelectorAll('.cz-g-ghost').length, lands: g.querySelectorAll('.cz-g-land').length, lives: g.querySelectorAll('.cz-g-start.is-live').length,
    ghost: ghost && { ...rect(ghost), css: css(ghost, 'borderTopStyle', 'borderTopColor', 'borderTopWidth') },
    land: land && { ...rect(land), css: css(land, 'borderTopStyle', 'borderTopColor') },
    live: live && { ...rect(live), t: live.querySelector('.cz-g-st-t').textContent, m: live.querySelector('.cz-g-st-m').textContent, css: css(live, 'color'), mcss: css(live.querySelector('.cz-g-st-m'), 'color'),
                    dot: css(live.querySelector('.cz-g-st-dot'), 'backgroundColor') },
    was: was.map(w => ({ t: w.querySelector('.cz-g-st-t').textContent, op: css(w, 'opacity')[0], deco: css(w.querySelector('.cz-g-st-t'), 'textDecorationLine')[0], f: w.dataset.for })),
    card: card && rect(card), under: g.querySelectorAll('.is-under').length }; }"""

# a printed start that disagrees with its plan: every shown label's clock against the true start of the first plan or booking it is for
STALE = """() => { const out = [], pad = n => (n < 10 ? '0' : '') + n;
  document.querySelectorAll('#cz-grid .cz-g-start').forEach(l => { if (getComputedStyle(l).display === 'none') return;
    const id = l.dataset.for.split(' ')[0], c = document.querySelector('.cz-gb[data-act="' + id + '"]'); if (!c) return;
    const m = +c.dataset.s, h = Math.floor(m / 60) % 24, want = ((h % 12) || 12) + ':' + pad(m % 60) + (h < 12 ? 'AM' : 'PM');
    if (l.textContent !== want) out.push(l.textContent + ' for ' + c.dataset.title + ' (starts ' + want + ')'); });
  return { stale: out, left: document.querySelectorAll('.is-live, .is-was, .is-under, .cz-g-ghost, .cz-g-land, .cz-g-dropnote').length }; }"""


def shot(page, name):
    if os.environ.get("F161_SHOTS"):
        page.screenshot(path=os.path.join(os.environ["F161_SHOTS"], name))


def geo(page):
    return page.evaluate(GEO)


def y_of(page, minute):
    g = geo(page)
    return g["top"] + (minute - g["lo"]) * g["ppm"]


def clock(minute):
    h = minute // 60 % 24
    return f"{h % 12 or 12}:{minute % 60:02d}", "AM" if h < 12 else "PM"


class Hand:
    """One pointer on the page: a finger (held, synthetic touch pointer events, as test_day_grid.py) at 390 and 800, the real mouse at 1440."""

    def __init__(self, page):
        self.page, self.mouse = page, page.viewport_size["width"] >= 1020

    def see(self, selector):
        if self.mouse:
            self.page.locator(selector).first.scroll_into_view_if_needed()
        else:
            show(self.page, selector)
        self.page.wait_for_timeout(40)

    def down(self, x, y):
        if self.mouse:
            self.page.mouse.move(x, y)
            self.page.mouse.down()
        else:
            fire(self.page, "pointerdown", x, y)

    def lift(self, x, y):
        """Press a plan and keep going until it is in the air (a hold with a finger, a few pixels with the mouse)."""
        self.down(x, y)
        if self.mouse:
            self.page.mouse.move(x + 4, y + 12, steps=3)
            self.page.wait_for_selector(".cz-gb.is-held")
        else:
            self.page.wait_for_timeout(480)

    def move(self, frm, to):
        if self.mouse:
            self.page.mouse.move(*to, steps=8)
        else:
            slide(self.page, frm, to)
        self.page.wait_for_timeout(60)

    def up(self, x, y):
        if self.mouse:
            self.page.mouse.up()
        else:
            fire(self.page, "pointerup", x, y)

    def up_and_read(self, x, y, js, arg=None):
        """Let go and read the page in the same breath, before the save's answer and the refresh that follows can redraw anything."""
        if self.mouse:
            self.page.mouse.up()
            return self.page.evaluate(js, arg)
        return self.page.evaluate("([x, y, js, arg]) => { const el = document.elementFromPoint(x, y) || document.body; el.dispatchEvent(new PointerEvent('pointerup', { pointerId: 7, pointerType: 'touch', clientX: x, clientY: y, bubbles: true, cancelable: true, isPrimary: true })); return eval(js)(arg); }", [x, y, js, arg])


def centre(page, selector):
    b = page.locator(selector).first.bounding_box()
    return b["x"] + b["width"] / 2, b["y"] + b["height"] / 2


# ---- moving ---------------------------------------------------------------------------------------------------------------------------------

@HOW
def test_a_plan_in_the_air_leaves_a_ghost_shows_a_landing_slot_and_a_coral_rail_time_that_follow_the_snapped_minute(signed_in, viewport):
    page = day(signed_in, viewport)
    act = page.locator(".cz-gb", has_text="Lunch at Grand Central Market").get_attribute("data-act")
    hand, sel = Hand(page), f'.cz-gb[data-act="{act}"]'
    hand.see(sel)
    at_rest = page.evaluate(MOVE, act)
    x, y = centre(page, sel)
    old_top, old_h = at_rest["card"]["top"], at_rest["card"]["height"]
    assert at_rest["ghosts"] == 0 and at_rest["lives"] == 0 and at_rest["was"] == []
    hand.lift(x, y)
    g = geo(page)
    to = (x, y + g["ppm"] * 60 + g["ppm"] * 4)                               # an hour later, and a little over: it snaps to 15 minutes
    hand.move((x, y), to)
    m = page.evaluate(MOVE, act)
    snapped = 13 * 60 + 30
    assert (m["ghosts"], m["lands"], m["lives"]) == (1, 1, 1)
    # the ghost stays at the old slot, faint and dashed
    assert abs(m["ghost"]["top"] - old_top) <= 1.5 and abs(m["ghost"]["height"] - old_h) <= 1.5, (m["ghost"], old_top, old_h)
    assert m["ghost"]["css"][0] == "dashed" and m["ghost"]["css"][1] == "rgba(30, 26, 46, 0.16)", m["ghost"]["css"]      # --hairline-2: faint
    # the landing slot is dashed and sits on the snapped minute, the size of the plan
    want = g["top"] + (snapped - g["lo"]) * g["ppm"]
    assert abs(m["land"]["top"] - want) <= 1.5, (m["land"]["top"], want)
    assert abs(m["land"]["height"] - old_h) <= 1.5 and abs(m["land"]["left"] - m["ghost"]["left"]) <= 1.5
    assert m["land"]["css"] == ["dashed", INK_2]
    # the rail: the live start in coral at the same minute, on the landing slot; the old one dimmed and struck through
    assert (m["live"]["t"], m["live"]["m"]) == clock(snapped) and abs(m["live"]["top"] - m["land"]["top"]) <= 1.5, (m["live"], m["land"])
    assert m["live"]["css"] == [CORAL_DEEP] and m["live"]["mcss"] == [CORAL_DEEP] and m["live"]["dot"] == [CORAL]
    assert len(m["was"]) == 1 and m["was"][0]["t"] == "12:30" and m["was"][0]["op"] == "0.45" and m["was"][0]["deco"] == "line-through" and m["was"][0]["f"] == act
    assert "1:30 – 3:00 PM" in page.locator(".cz-g-label").inner_text().replace("\n", " ")
    # and it follows: another quarter hour on, everything moves with it
    again = (x, to[1] + g["ppm"] * 15)
    hand.move(to, again)
    m2 = page.evaluate(MOVE, act)
    assert (m2["live"]["t"], m2["live"]["m"]) == clock(snapped + 15) and abs(m2["land"]["top"] - (want + g["ppm"] * 15)) <= 1.5 and abs(m2["live"]["top"] - m2["land"]["top"]) <= 1.5
    assert abs(m2["ghost"]["top"] - old_top) <= 1.5      # (the ghost did not go with it)
    hand.move(again, to)
    shot(page, f"move-{viewport['width']}.png")
    # let go: the plan lands where the slot was, and the rail already shows the new time (read before the refresh)
    after = hand.up_and_read(*to, "a => [...document.querySelectorAll('.cz-g-start[data-for=\"' + a + '\"]')].map(l => [l.textContent, l.className.includes('is-live'), l.className.includes('is-was')])", act)
    assert after == [["1:30PM", False, False]], after
    expect(page.locator(".ga-toast")).to_contain_text("moved to 1:30 PM")
    assert cal.get_activity(person("ari"), act).start == snapped
    page.wait_for_function("() => !document.querySelector('.cz-g-ghost')")
    assert page.evaluate(STALE) == {"stale": [], "left": 0}
    card = page.evaluate(MOVE, act)["card"]
    assert abs(card["top"] - (geo(page)["top"] + (snapped - g["lo"]) * g["ppm"])) <= 1.5      # the drop result is the slot's minute


@HOW
def test_a_refused_save_puts_the_rail_time_back_with_the_plan(signed_in, viewport):
    page = day(signed_in, viewport)
    act = page.locator(".cz-gb", has_text="Lunch at Grand Central Market").get_attribute("data-act")
    page.route("**/trip/canvas/plan", lambda route: route.abort())
    hand, sel = Hand(page), f'.cz-gb[data-act="{act}"]'
    hand.see(sel)
    x, y = centre(page, sel)
    hand.lift(x, y)
    g = geo(page)
    to = (x, y + g["ppm"] * 60 + g["ppm"] * 4)
    hand.move((x, y), to)
    assert page.evaluate(MOVE, act)["live"]["t"] == "1:30"
    hand.up(*to)
    expect(page.locator(".ga-toast")).to_contain_text("Could not save")
    assert cal.get_activity(person("ari"), act).start == 12 * 60 + 30
    page.wait_for_function("() => !document.querySelector('.cz-g-ghost')")
    assert page.evaluate(STALE) == {"stale": [], "left": 0}
    assert page.locator(f'.cz-g-start[data-for="{act}"]').text_content() == "12:30PM"


@HOW
def test_letting_go_where_it_began_or_cancelling_leaves_no_ghost_slot_or_dimmed_time(signed_in, viewport):
    page = day(signed_in, viewport)
    act = page.locator(".cz-gb", has_text="Lunch at Grand Central Market").get_attribute("data-act")
    hand, sel = Hand(page), f'.cz-gb[data-act="{act}"]'
    hand.see(sel)
    x, y = centre(page, sel)
    hand.lift(x, y)
    step = geo(page)["ppm"] * 15
    hand.move((x, y), (x + 3, y + step + 1))
    m = page.evaluate(MOVE, act)
    assert (m["live"]["t"], m["live"]["m"]) == ("12:45", "PM") and abs(m["land"]["top"] - m["ghost"]["top"] - step) <= 1.5      # one quarter hour on
    hand.move((x + 3, y + step + 1), (x, y))
    m = page.evaluate(MOVE, act)
    assert (m["live"]["t"], m["live"]["m"]) == ("12:30", "PM") and abs(m["land"]["top"] - m["ghost"]["top"]) <= 1.5      # back on the ghost: nothing to move
    if hand.mouse:
        page.keyboard.press("Escape")
    else:
        fire(page, "pointercancel", x, y)
    page.wait_for_function("() => !document.querySelector('.cz-g-ghost')")
    assert page.evaluate(STALE) == {"stale": [], "left": 0}
    assert cal.get_activity(person("ari"), act).start == 12 * 60 + 30


@pytest.mark.parametrize("viewport", [PHONE, TABLET], ids=["390", "800"])
def test_a_plan_dragged_over_a_more_card_never_draws_over_it_or_leaves_a_stale_rail_label(signed_in, viewport):
    page = signed_in(viewport, path="/trip/canvas?day=0")
    crowded(page)
    more = page.locator(".cz-lanemore").first
    hidden = more.get_attribute("data-more").split()
    shown_before = page.evaluate("() => [...document.querySelectorAll('#cz-grid .cz-g-start')].filter(l => getComputedStyle(l).display !== 'none').map(l => l.dataset.for)")
    # a plan that is not behind a card, from outside the stretch, taken onto the card's first minute
    cand = page.evaluate("""(hidden) => { const first = Math.min(...hidden.map(i => +document.querySelector('.cz-gb[data-act="' + i + '"]').dataset.s));
      return [...document.querySelectorAll('.cz-gb:not(.is-more):not(.is-new)')].filter(b => /^a/.test(b.dataset.act) && Math.abs(+b.dataset.s - first) >= 90).map(b => [b.dataset.act, +b.dataset.s, +b.dataset.e, first]); }""", hidden)
    assert cand, "the crowded day has a plan away from the +N card"
    act, s0, e0, first = cand[0]
    sel = f'.cz-gb[data-act="{act}"]'
    show(page, sel)
    x, y = centre(page, sel)
    fire(page, "pointerdown", x, y)
    page.wait_for_timeout(480)
    g = geo(page)
    target = (x, y + (first - s0) * g["ppm"])
    # the page scrolls with the plan near an edge; keep it simple: scroll the target into view first and measure from there
    page.evaluate("(t) => window.scrollBy(0, t - innerHeight * 0.5)", target[1])
    page.wait_for_timeout(40)
    g2 = geo(page)
    y2 = y - (g["top"] - g2["top"]) + (first - s0) * g["ppm"]
    slide(page, (x, y), (x, y2), steps=10)
    m = page.evaluate(MOVE, act)
    assert (m["ghosts"], m["lands"], m["lives"]) == (1, 1, 1)
    mid = page.evaluate("""() => { const card = document.querySelector('.cz-lanemore'), ghost = document.querySelector('.cz-g-ghost'), c = card.getBoundingClientRect(), l = document.querySelector('.cz-g-land').getBoundingClientRect(),
        x = c.left + c.width / 2, y = c.top + c.height / 2;
        return { over: l.left <= x && x <= l.right && l.top <= y && y <= l.bottom, same: card.parentNode === ghost.parentNode, card: +getComputedStyle(card).zIndex, ghost: +getComputedStyle(ghost).zIndex }; }""")
    assert mid["over"] and mid["same"] and mid["card"] > mid["ghost"], mid      # the slot reaches the card, and the card is above it: a slot never covers a card (or the plans behind it)
    assert all(page.locator(f'.cz-gb[data-act="{i}"]').evaluate("e => getComputedStyle(e).visibility") == "hidden" for i in hidden)      # the hidden plans stay hidden
    shot(page, f"move-over-more-{viewport['width']}.png")
    fire(page, "pointercancel", x, y2)
    page.wait_for_function("() => !document.querySelector('.cz-g-ghost')")
    state = page.evaluate(STALE)
    assert state == {"stale": [], "left": 0}, state
    shown_after = page.evaluate("() => [...document.querySelectorAll('#cz-grid .cz-g-start')].filter(l => getComputedStyle(l).display !== 'none').map(l => l.dataset.for)")
    assert shown_after == shown_before      # the rail is as it was: no label was lost, none is left over


def test_a_day_chip_under_the_mouse_says_where_the_plan_will_drop(signed_in):
    page = day(signed_in, DESKTOP)
    act = page.locator(".cz-gb", has_text="Lunch at Grand Central Market").get_attribute("data-act")
    hand, sel = Hand(page), f'.cz-gb[data-act="{act}"]'
    hand.see(sel)
    x, y = centre(page, sel)
    hand.lift(x, y)
    chip = page.locator('.cz-hchip[data-move-day="1"]')
    label = chip.get_attribute("data-move-label")
    assert page.locator(".cz-g-dropnote").count() == 0
    cx, cy = centre(page, '.cz-hchip[data-move-day="1"]')
    page.mouse.move(cx, cy, steps=8)
    note = page.locator(".cz-g-dropnote")
    expect(note).to_have_text(f"Drop to move to {label}")
    nb, cb = note.bounding_box(), chip.bounding_box()
    assert nb["y"] >= cb["y"] + cb["height"] - 1 and nb["x"] <= cb["x"] + cb["width"] and nb["x"] + nb["width"] >= cb["x"]      # under the chip it names
    assert note.evaluate("e => parseFloat(getComputedStyle(e).fontSize)") >= 12.99
    shot(page, "move-chip-1440.png")
    page.mouse.move(x, y + 30, steps=6)
    expect(note).to_have_count(0)
    page.mouse.move(cx, cy, steps=6)
    expect(note).to_have_count(1)
    page.mouse.up()
    page.wait_for_function("() => !document.querySelector('.cz-g-dropnote')")
    expect(page.locator(".ga-toast")).to_contain_text("Moved to")


# ---- adding ---------------------------------------------------------------------------------------------------------------------------------

def empty_spot(page, minute):
    """A point on empty grid at `minute`, scrolled into view."""
    sel = "#cz-grid .cz-g-plane"
    page.locator("#cz-grid .cz-g-zoom").evaluate("(e, m) => { const g = e.closest('#cz-grid'), lo = +g.dataset.lo, hi = +g.dataset.hi, r = e.getBoundingClientRect(), box = document.querySelector('.cz-view[data-day] .cz-day-body');"
                                                  "const y = r.top + (m - lo) * e.offsetHeight / (hi - lo); if (innerWidth >= 1020 && box) { const b = box.getBoundingClientRect(); box.scrollBy(0, y - b.top - b.height * 0.4); } else window.scrollBy(0, y - innerHeight * 0.4); }", minute)
    page.wait_for_timeout(60)
    b = page.locator(sel).bounding_box()
    return b["x"] + b["width"] * 0.6, y_of(page, minute)


def draft(page, viewport, minute=10 * 60):
    """Start a plan on empty time at `minute` the way the screen does it (a held finger, a dragged mouse) and let go: the title field opens."""
    x, y = empty_spot(page, minute + 7)
    if viewport["width"] >= 1020:
        page.mouse.move(x, y)
        page.mouse.down()
        page.mouse.move(x, y + 12, steps=3)
        page.wait_for_selector(".cz-gb.is-new.is-drawing")
        end = y_of(page, minute + 60) - 3
        page.mouse.move(x, end, steps=6)
        return x, y, end
    fire(page, "pointerdown", x, y)
    page.wait_for_timeout(480)
    return x, y, y


@HOW
def test_a_new_plan_opens_in_the_gap_with_a_dashed_coral_edge_its_field_focused_the_kinds_chips_and_its_time_in_coral(signed_in, viewport):
    page = day(signed_in, viewport)
    x, y, end = draft(page, viewport)
    if viewport["width"] >= 1020:                      # while it is being drawn the rail already follows it
        live = page.locator("#cz-grid .cz-g-start.is-live")
        assert (live.locator(".cz-g-st-t").text_content(), live.locator(".cz-g-st-m").text_content()) == ("10:00", "AM")
        page.mouse.up()
    else:
        fire(page, "pointerup", x, y)
    new = page.locator(".cz-gb.is-new")
    field = new.locator(".cz-gb-edit")
    expect(field).to_be_focused()
    assert field.get_attribute("placeholder") == "What's the plan?"
    s = page.evaluate("(a) => { const e = document.querySelector('.cz-gb.is-new'); return [+e.dataset.s, +e.dataset.e]; }", None)
    assert s == [10 * 60, 11 * 60] and not new.evaluate("e => e.classList.contains('is-drawing')")
    # the edge: dashed, coral, two pixels
    assert new.evaluate("e => { const s = getComputedStyle(e); return [s.borderTopStyle, s.borderTopColor, s.borderLeftStyle, s.borderLeftColor, parseFloat(s.borderTopWidth)]; }") == ["dashed", CORAL, "dashed", CORAL, 2]
    assert new.evaluate("e => [getComputedStyle(e).backgroundColor, getComputedStyle(e).boxShadow]") == [CARD, "none"]      # flat once its field is open
    # the draft sits in the gap: its top is the 10:00 line
    gp = geo(page)
    assert abs(new.bounding_box()["y"] - (gp["top"] + (10 * 60 - gp["lo"]) * gp["ppm"])) <= 1.5
    # the rail's time for it: coral, at the draft's top
    live = page.locator("#cz-grid .cz-g-start.is-live")
    assert (live.locator(".cz-g-st-t").text_content(), live.locator(".cz-g-st-m").text_content()) == ("10:00", "AM")
    assert live.evaluate("e => [getComputedStyle(e).color, getComputedStyle(e.querySelector('.cz-g-st-dot')).backgroundColor]") == [CORAL_DEEP, CORAL]
    assert abs(live.bounding_box()["y"] - new.bounding_box()["y"]) <= 1.5
    # the kinds' chips, each in its kind's tint and ink, as big as a finger on a phone
    chips = new.locator(".cz-gb-kinds .cz-kc")
    expect(chips).to_have_count(5)
    got = {c.get_attribute("data-kind"): c.evaluate("e => [getComputedStyle(e).backgroundColor, getComputedStyle(e).color, e.getBoundingClientRect().height, parseFloat(getComputedStyle(e).fontSize)]") for c in chips.all()}
    assert {k: v[:2] for k, v in got.items()} == KIND_COLOURS
    assert all(v[2] >= 43.5 and v[3] >= 12.99 for v in got.values()), got
    assert [c.inner_text().strip() for c in chips.all()] == ["Fun", "Food", "Outdoors", "Culture", "Travel"]
    assert chips.nth(0).get_attribute("aria-checked") == "true"
    shot(page, f"add-{viewport['width']}.png")
    # a chip is a choice that does not take the keyboard away; the draft, its rail dot and the saved plan take its kind
    chips.nth(1).click()
    expect(field).to_be_focused()
    assert "cz-k-food" in new.get_attribute("class") and chips.nth(1).get_attribute("aria-checked") == "true" and chips.nth(0).get_attribute("aria-checked") == "false"
    assert page.locator("#cz-grid .cz-g-start.is-live").get_attribute("class").count("cz-k-food") == 1
    field.fill("Brunch at the pier")
    field.press("Enter")
    expect(page.locator(".ga-toast")).to_contain_text("Brunch at the pier added")
    made = [a for a in cal.activities(person("ari")) if a.title == "Brunch at the pier"]
    assert [(a.kind, a.start, a.end) for a in made] == [("food", 10 * 60, 11 * 60)]
    page.wait_for_function("() => !document.querySelector('.cz-gb.is-new')")
    assert page.evaluate(STALE) == {"stale": [], "left": 0}
    assert page.locator('#cz-grid .cz-g-start', has_text="10:00").count() == 1      # the refreshed day prints its start the usual way


@HOW
def test_a_draft_that_is_dropped_leaves_nothing_on_the_rail_and_a_plain_save_is_fun(signed_in, viewport):
    page = day(signed_in, viewport)
    x, y, end = draft(page, viewport, 10 * 60 + 30)
    if viewport["width"] >= 1020:
        page.mouse.up()
    else:
        fire(page, "pointerup", x, y)
    field = page.locator(".cz-gb.is-new .cz-gb-edit")
    expect(field).to_be_focused()
    page.keyboard.press("Escape")
    page.wait_for_function("() => !document.querySelector('.cz-gb.is-new')")
    assert page.evaluate(STALE) == {"stale": [], "left": 0}
    assert [a for a in cal.activities(person("ari")) if a.start == 10 * 60 + 30] == []
    x, y, end = draft(page, viewport, 10 * 60 + 30)
    if viewport["width"] >= 1020:
        page.mouse.up()
    else:
        fire(page, "pointerup", x, y)
    field = page.locator(".cz-gb.is-new .cz-gb-edit")
    expect(field).to_be_focused()
    field.fill("Souvenirs")
    field.press("Enter")
    expect(page.locator(".ga-toast")).to_contain_text("Souvenirs added")
    assert [a.kind for a in cal.activities(person("ari")) if a.title == "Souvenirs"] == ["fun"]      # no chip touched: Fun, as before
