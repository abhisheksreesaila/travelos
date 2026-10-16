"""F-178: the family thread as iMessage-style bubbles, in a real browser: on the phone's Family tab (390) and in the laptop panel (1440). Mine on the right in a filled bubble with white text,
theirs on the left in grey, the name once per run, the avatar, time and tail on the last of a run, and a message sent or polled live joins the run the way a server-drawn one does.
Screenshots on request: F178_SHOTS=<folder>."""
import os
import re

import pytest
from playwright.sync_api import expect

from tests_browser.helpers import DESKTOP
from tests_browser.test_day_grid import open_day
from tests_browser.test_family_panel import SATURDAY, dock, mates, open_family, thread  # noqa: F401 - fixtures
from tests_browser.test_thread import pair  # noqa: F401 - fixture
from tests_browser.test_trip_canvas import canvas_page, model  # noqa: F401 - fixtures

CORAL_DEEP, WHITE, BUBBLE_GREY, INK = [201, 67, 31], [255, 255, 255], [233, 230, 238], [30, 26, 46]


def shot(page, name):
    if os.environ.get("F178_SHOTS"):
        page.screenshot(path=os.path.join(os.environ["F178_SHOTS"], name))


def _lum(rgb):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(rgb[0]) + 0.7152 * ch(rgb[1]) + 0.0722 * ch(rgb[2])


def contrast(a, b):
    hi, lo = sorted((_lum(a), _lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def colours(loc):
    """(background, text) of an element as [r, g, b] lists."""
    return loc.evaluate("e => { const c = getComputedStyle(e), p = s => s.match(/[\\d.]+/g).slice(0, 3).map(Number); return [p(c.backgroundColor), p(c.color)]; }")


def page_colour(loc):
    """The colour behind an element: the first painted background up its parents."""
    return loc.evaluate("e => { for (let n = e; n; n = n.parentElement) { const c = getComputedStyle(n).backgroundColor; if (c !== 'rgba(0, 0, 0, 0)') return c.match(/[\\d.]+/g).slice(0, 3).map(Number); } return [255, 255, 255]; }")


def seen(msgs):
    """What the page shows per message: the name drawn, the avatar visible, the time drawn, a tail (a sharp bottom corner)."""
    return msgs.evaluate_all("""els => els.map(e => { const nm = e.querySelector('.ft-nm'), av = e.querySelector('.ft-av'), t = e.querySelector('.ft-time'), s = getComputedStyle(e.querySelector('.ft-bub'));
      return { name: !!nm && getComputedStyle(nm).display !== 'none', avatar: !!av && getComputedStyle(av).visibility !== 'hidden', time: !!t && getComputedStyle(t).display !== 'none',
        tail: Math.min(parseFloat(s.borderBottomLeftRadius), parseFloat(s.borderBottomRightRadius)) < 6 }; })""")


def runs(th):
    return th.locator(".ft-msg").evaluate_all("els => els.map(e => ['ft-first', 'ft-last'].filter(c => e.classList.contains(c)).join('+'))")


def say(ctx, base, text):
    r = ctx.request.post(f"{base}/trip/family/message", form={"text": text, "scope": "trip"}, headers={"X-Fragment": "1"}, max_redirects=0)
    assert r.ok, r.text()


def check_look(th):
    """th holds three messages from someone else, then one of mine."""
    theirs, mine = th.locator(".ft-msg:not(.ft-me)"), th.locator(".ft-me")
    box, mb, tb = th.bounding_box(), mine.last.bounding_box(), theirs.first.bounding_box()
    assert mb["x"] + mb["width"] > box["x"] + box["width"] - 24, (mb, box)          # mine against the right edge
    assert tb["x"] < box["x"] + 60, (tb, box)                                         # theirs at the left, by the avatar
    bg, fg = colours(mine.last.locator(".ft-bub"))
    assert (bg, fg) == (CORAL_DEEP, WHITE), (bg, fg)                                  # white on the filled colour
    assert contrast(bg, fg) >= 4.5
    gbg, gfg = colours(theirs.first.locator(".ft-bub"))
    assert (gbg, gfg) == (BUBBLE_GREY, INK), (gbg, gfg)                               # ink on soft grey
    assert contrast(gbg, gfg) >= 4.5
    assert seen(theirs) == [dict(name=True, avatar=False, time=False, tail=False), dict(name=False, avatar=False, time=False, tail=False), dict(name=False, avatar=True, time=True, tail=True)]
    for loc in (theirs.first.locator(".ft-nm"), theirs.last.locator(".ft-time"), mine.last.locator(".ft-time")):      # the name and the quiet time are small, and still AA on the page
        size, fg = loc.evaluate("e => { const s = getComputedStyle(e); return [parseFloat(s.fontSize), s.color.match(/[\\d.]+/g).slice(0, 3).map(Number)]; }")
        assert contrast(fg, page_colour(loc)) >= 4.5 and size <= 14, (size, fg)


def test_the_phone_family_tab_draws_bubbles_and_live_messages_join_the_run(pair, base_url):
    ari, mate = pair()
    for t in ("One from Maya", "Two from Maya", "Three from Maya"):
        say(mate.context, base_url, t)
    ari.reload()
    th = ari.locator("#ft-thread")
    ari.locator("#ft-text").fill("My first")
    ari.locator("#ft-send").click()                                                     # sent live
    expect(th.locator(".ft-me .ft-bub")).to_have_text("My first")
    assert runs(th) == ["ft-first", "", "ft-last", "ft-first+ft-last"]                  # the live one sits in its own run, the three keep theirs
    check_look(th)
    shot(ari, "phone-live.png")
    ari.reload()
    assert runs(th) == ["ft-first", "", "ft-last", "ft-first+ft-last"]                  # the same as the server draws it
    ari.locator("#ft-text").fill("My second")
    ari.locator("#ft-send").click()
    expect(th.locator(".ft-me .ft-bub").nth(1)).to_have_text("My second")
    assert runs(th) == ["ft-first", "", "ft-last", "ft-first", "ft-last"]               # it joins my run: my first loses its tail, my second has it
    assert [s["tail"] for s in seen(th.locator(".ft-me"))] == [False, True]
    say(mate.context, base_url, "Four from Maya")                                       # polled in
    expect(th.locator(".ft-msg")).to_have_count(6, timeout=9000)
    assert runs(th) == ["ft-first", "", "ft-last", "ft-first", "ft-last", "ft-first+ft-last"]
    ari.reload()
    assert runs(th) == ["ft-first", "", "ft-last", "ft-first", "ft-last", "ft-first+ft-last"]
    shot(ari, "phone-b.png")


@pytest.fixture
def desk(canvas_page):
    return canvas_page(viewport=DESKTOP, touch=False)


def test_the_laptop_panel_draws_the_same_bubbles_and_a_sent_one_joins_the_run(desk, mates):
    mate = mates(desk)
    open_day(desk, SATURDAY)
    for t in ("One from Maya", "Two from Maya", "Three from Maya"):
        mate.say(t)
    open_day(desk, SATURDAY)
    open_family(desk)
    th = thread(desk)
    dock(desk).locator("#ft-text").fill("Mine, from the panel")
    dock(desk).locator("#ft-send").click()
    expect(th.locator(".ft-me .ft-bub")).to_have_text("Mine, from the panel")
    assert runs(th) == ["ft-first", "", "ft-last", "ft-first+ft-last"]
    check_look(th)
    dock(desk).locator("#ft-text").fill("Mine again")
    dock(desk).locator("#ft-send").click()
    expect(th.locator(".ft-me .ft-bub").nth(1)).to_have_text("Mine again")
    assert runs(th) == ["ft-first", "", "ft-last", "ft-first", "ft-last"]
    shot(desk, "panel-1440.png")
