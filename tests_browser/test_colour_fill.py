"""F-167: plan blocks are filled with their kind's tint (like a Teams meeting), not a white card with a coloured edge.
Laptop day and week at 1440 and 1280, tablet and phone day at 800 and 390. Rules: design-system/DESIGN-SYSTEM.md "Blocks filled with their kind's colour (F-167)".
Screenshots on request: F167_SHOTS=<folder>."""
import os
import re

import pytest
from playwright.sync_api import expect

from gitaway import tripcal as cal
from tests.test_signin import person
from tests_browser.helpers import DESKTOP, PHONE
from tests_browser.test_topbar import LAPTOP, TABLET, signed_in  # noqa: F401 - fixture

WHITE = "rgb(255, 255, 255)"
INK = "rgb(30, 26, 46)"
# kind -> (fill, edge), both from tokens.css
KIND = {"food": ("rgb(255, 241, 194)", "rgb(255, 201, 60)"), "outdoors": ("rgb(212, 247, 234)", "rgb(72, 209, 160)"),
        "culture": ("rgb(236, 228, 255)", "rgb(195, 178, 255)"), "travel": ("rgb(221, 238, 255)", "rgb(90, 176, 255)"),
        "fun": ("rgb(255, 227, 241)", "rgb(255, 140, 198)")}
ALL = pytest.mark.parametrize("viewport", [DESKTOP, LAPTOP, TABLET, PHONE], ids=["1440", "1280", "800", "390"])
DESK = pytest.mark.parametrize("viewport", [DESKTOP, LAPTOP], ids=["1440", "1280"])
SMALL = pytest.mark.parametrize("viewport", [TABLET, PHONE], ids=["800", "390"])
PLANS = ((9 * 60, 10 * 60 + 30, "Fun morning", "fun"), (12 * 60 + 30, 14 * 60, "Lunch at Grand Central Market", "food"), (15 * 60, 16 * 60, "Beach walk", "outdoors"),
         (16 * 60 + 30, 17 * 60 + 30, "Getty museum", "culture"), (18 * 60, 19 * 60, "Drive to the pier", "travel"),
         (19 * 60 + 30, 20 * 60, "Short coffee stop", "food"), (20 * 60 + 15, 20 * 60 + 30, "Quick call", "fun"),
         (21 * 60, 22 * 60, "Late show", "culture"), (21 * 60, 22 * 60, "Night walk", "outdoors"))      # the last two at once: side by side (lanes)


def shot(page, name):
    if os.environ.get("F167_SHOTS"):
        page.screenshot(path=os.path.join(os.environ["F167_SHOTS"], name))


def seed():
    me = person("ari")
    for s, e, title, kind in PLANS:
        cal.add_activity(me, day=0, start=s, end=e, title=title, kind=kind, fine=True)


def rgb(s):
    """Chrome reports a mixed colour as `color(srgb 0.94 0.97 1)`, a plain one as `rgb(r, g, b)`."""
    nums = [float(x) for x in re.findall(r"[\d.]+", s)[:3]]
    return [v * 255 for v in nums] if s.startswith("color(") else nums


def lum(c):
    f = [v / 255 for v in c]
    f = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in f]
    return 0.2126 * f[0] + 0.7152 * f[1] + 0.0722 * f[2]


def quiet(tint):
    """A booking's fill: its kind's tint at 45% over white (`color-mix(in srgb, tint 45%, white)`), as rgb numbers."""
    return [255 - (255 - v) * 0.45 for v in rgb(tint)]


def is_quiet(bg, tint):
    return all(abs(a - b) <= 1.5 for a, b in zip(rgb(bg), quiet(tint)))


def contrast(a, b):
    la, lb = sorted((lum(rgb(a)), lum(rgb(b))), reverse=True)
    return (la + 0.05) / (lb + 0.05)


CARDS = """(sel) => [...document.querySelectorAll(sel)].map(e => { const s = getComputedStyle(e), q = x => e.querySelector(x), c = x => q(x) ? getComputedStyle(q(x)) : null;
  const tile = c('.cz-gb-tile, .cz-gbk-tile, .cz-wi-ico'), pill = c('.cz-gb-tag, .cz-bk-tag, .cz-wi-tag');
  const vis = x => x && x.display !== 'none';
  return { title: e.textContent.trim().slice(0, 30), kind: [...e.classList].find(k => k.startsWith('cz-k-')) || '', booked: e.classList.contains('cz-gbk') || e.classList.contains('is-booked'),
    bg: s.backgroundColor, shadow: s.boxShadow, titleInk: (c('.cz-gb-t, .cz-bk-t, .cz-wi-t') || {}).color, time: vis(c('.cz-gb-when, .cz-gb-st, .cz-bk-time, .cz-wi-time')) ? c('.cz-gb-when, .cz-gb-st, .cz-bk-time, .cz-wi-time').color : null,
    tileBg: vis(tile) ? tile.backgroundColor : null, tileInk: vis(tile) ? tile.color : null, pillBg: vis(pill) ? pill.backgroundColor : null, pillInk: vis(pill) ? pill.color : null }; })"""


def day(signed_in, viewport):
    page = signed_in(viewport, path="/trip/canvas?day=0")
    seed()
    page.reload()
    expect(page.locator(".cz-gb").first).to_be_visible()
    return page


def week(signed_in, viewport):
    page = signed_in(viewport, path="/trip/canvas")
    seed()
    page.reload()
    page.wait_for_selector("#cz-wk .cz-wi")
    return page


def check(cards):
    plans = [c for c in cards if not c["booked"]]
    assert {c["kind"].removeprefix("cz-k-") or "fun" for c in plans} == set(KIND)      # every kind is on the page
    for c in plans:
        fill, edge = KIND[c["kind"].removeprefix("cz-k-") or "fun"]
        assert c["bg"] == fill, c["title"]      # filled with the kind's tint, so never white
        assert any(f"{edge} {w}px 0px 0px 0px inset" in c["shadow"] for w in (3, 4)), (c["title"], c["shadow"])      # the darker kind edge on the left
        assert c["titleInk"] == INK
        assert contrast(c["titleInk"], c["bg"]) >= 4.5
        if c["time"]:
            assert contrast(c["time"], c["bg"]) >= 4.5, c["title"]
        if c["tileBg"]:
            assert c["tileBg"] == WHITE      # a white tile reads on every tint
            assert contrast(c["tileInk"], c["tileBg"]) >= 4.5
        if c["pillBg"]:
            assert contrast(c["pillInk"], c["pillBg"]) >= 4.5
            assert c["pillBg"] != c["bg"]
    bookings = [c for c in cards if c["booked"]]
    assert len(bookings) >= 2
    for c in bookings:
        tint = KIND["travel"][0] if "Skylark" in c["title"] else KIND["culture"][0]      # the flight is sky, the hotel grape
        assert is_quiet(c["bg"], tint), (c["title"], c["bg"])      # exactly its kind's tint at 45% over white: quieter than any plan's fill, never white
        assert contrast(c["titleInk"], c["bg"]) >= 4.5
        assert c["tileBg"] in (None, WHITE)
        assert c["pillBg"] is None or contrast(c["pillInk"], c["pillBg"]) >= 4.5


@ALL
def test_every_day_plan_is_filled_with_its_kinds_tint(signed_in, viewport):
    page = day(signed_in, viewport)
    check(page.evaluate(CARDS, ".cz-gb:not(.is-new):not(.is-more), .cz-gbk"))
    width = lambda t: page.locator(".cz-gb", has_text=t).evaluate("e => e.getBoundingClientRect().width")
    assert width("Late show") < width("Fun morning") * 0.85 and width("Night walk") < width("Fun morning") * 0.85      # the side-by-side pair is among those checked
    shot(page, f"day-{page.viewport_size['width']}.png")


@DESK
def test_every_week_plan_is_filled_with_its_kinds_tint(signed_in, viewport):
    page = week(signed_in, viewport)
    check(page.evaluate(CARDS, ".cz-wi"))
    shot(page, f"week-{viewport['width']}.png")


@SMALL
def test_the_week_of_day_cards_keeps_white_rows(signed_in, viewport):
    """F-163's phone week rows are list rows inside a day card, not calendar blocks: they stay white with the kind's tile (the mini bar carries the colour)."""
    page = signed_in(viewport, path="/trip/canvas")
    seed()
    page.reload()
    expect(page.locator("#cz-week .cz-row").first).to_be_visible()
    assert page.locator("#cz-week .cz-wcard").first.evaluate("e => getComputedStyle(e).backgroundColor") in (WHITE, "rgba(0, 0, 0, 0)")
    shot(page, f"week-{viewport['width']}.png")


STICKY = """() => { const b = document.querySelector('.cz-gb[data-act]'); const head = b.querySelector('.cz-gb-head'), note = b.querySelector('.cz-gb-note');
  const stick = parseFloat(getComputedStyle(head).top) || 0, h = head.getBoundingClientRect(), n = note.getBoundingClientRect();
  let sc = b.parentElement; while (sc && !/(auto|scroll)/.test(getComputedStyle(sc).overflowY)) sc = sc.parentElement;      // the day's own scroller on a laptop, else the page
  (sc || window).scrollBy(0, h.top - stick + (n.top - h.top) - 0.4 * h.height);      // scrolled until the note's top sits under the stuck head's lower part
  const r = n => { const x = n.getBoundingClientRect(); return { t: x.top, b: x.bottom }; }, hs = getComputedStyle(head), bs = getComputedStyle(b);
  return { head: r(head), note: r(note), headBg: hs.backgroundColor, blockBg: bs.backgroundColor, sticky: hs.position }; }"""


@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["1440", "390"])
def test_a_stuck_title_covers_the_note_it_slides_over(signed_in, viewport):
    """The sticky head (F-110) once had the card's white behind it; on a filled block it must carry the block's own fill, or the note prints through the title."""
    page = signed_in(viewport, path="/trip/canvas?day=0")
    me = person("ari")
    a = cal.add_activity(me, day=0, start=9 * 60, end=14 * 60, title="Long day at the park", kind="outdoors")
    cal.add_note(me, "Bring sunscreen, hats and a lot of water for everyone", act=a.id)
    page.reload()
    expect(page.locator(".cz-gb-note")).to_be_visible()
    got = page.evaluate(STICKY)
    assert got["sticky"] == "sticky"
    assert got["head"]["t"] < got["note"]["b"] and got["note"]["t"] < got["head"]["b"] or got["note"]["t"] < got["head"]["t"]      # the head is down over (or past) the note's place
    assert got["headBg"] == got["blockBg"] == KIND["outdoors"][0]      # opaque, the block's own tint: whatever is under the title is covered


PANELS = """() => [...document.querySelectorAll('.cz-day-body, .cz-hchip, .cz-hchips, .cz-wcol, .cz-wh, .cz-wk, #cz-wk, .cz-dock, .cz-row')].filter(e => e.getClientRects().length).map(e => [e.className, getComputedStyle(e).backgroundColor])"""
NEUTRAL = ("rgba(0, 0, 0, 0)", WHITE, INK, "rgb(250, 247, 242)")      # clear, white card, the open day's ink chip, paper


@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["1440", "390"])
def test_days_stay_uncoloured_only_kinds_carry_colour(signed_in, viewport):
    """Day chips, the day panel and the week's columns and headers never take a kind or day tint."""
    for make in (day, week) if viewport is DESKTOP else (day,):
        page = make(signed_in, viewport)
        got = page.evaluate(PANELS)
        assert got
        assert all(bg in NEUTRAL for _, bg in got), [g for g in got if g[1] not in NEUTRAL]
