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
        assert c["bg"] not in {p["bg"] for p in plans} and c["bg"] != WHITE      # a quieter fill than any plan's tint
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
