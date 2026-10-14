"""F-143: Family chat in the panel, in a real browser (a mouse, at 1440 and 1280). The Family tab and the top bar's Family list the trip's chats (the whole trip first, then each plan's) with
unread counts and open a chat below with its message bar, without a page load; "People and invites" goes to /family; /trip/family/thread opened directly lands on the day with the chats open;
a message from another member shows without reloading (in the Family pane and in a plan's pane), nothing moves when it arrives, and nothing is asked for while the pane is closed or the tab
is hidden. 1000 (tablet) and 390 (phone) keep today's Family page. Screenshots on request: F143_SHOTS=<folder>."""
import os
import re
import uuid

import pytest
from playwright.sync_api import expect

from tests_browser.helpers import DESKTOP, PHONE
from tests_browser.test_day_grid import open_day
from tests_browser.test_topbar import LAPTOP
from tests_browser.test_trip_canvas import WIDE, canvas_page, model  # noqa: F401 - fixtures

SATURDAY = 1
NO_SCROLL = "[document.documentElement.scrollWidth <= document.documentElement.clientWidth, document.documentElement.scrollHeight <= document.documentElement.clientHeight, window.scrollY]"
TABLET = {"width": 1000, "height": 800}


def shot(page, name):
    if os.environ.get("F143_SHOTS"):
        page.screenshot(path=os.path.join(os.environ["F143_SHOTS"], name))


class Mate:
    """A second member of Ari's family (an editor), signed in in their own browser context, who says things."""

    def __init__(self, ctx, base):
        self.ctx, self.base = ctx, base

    def say(self, text, act="", part=""):
        if act:
            r = self.ctx.request.post(f"{self.base}/trip/talk/message", form={"text": text, "act": act, "part": part}, headers={"X-Fragment": "1"}, max_redirects=0)
        else:
            r = self.ctx.request.post(f"{self.base}/trip/family/message", form={"text": text, "scope": "trip"}, headers={"X-Fragment": "1"}, max_redirects=0)
        assert r.ok, r.text()


@pytest.fixture
def mates(browser, base_url):
    made = []

    def make(page):
        email = f"mate.{uuid.uuid4().hex[:8]}@gmail.com"
        r = page.context.request.post(f"{base_url}/family/invite", form={"email": email, "role": "editor"}, max_redirects=0)
        assert r.status in (200, 303), r.status
        ctx = browser.new_context(viewport=PHONE, reduced_motion="reduce")
        ctx.set_default_timeout(9000)
        made.append(ctx)
        ctx.request.post(f"{base_url}/signin", form={"email": email, "next": "/", "intent": "save"}, max_redirects=0)
        return Mate(ctx, base_url)

    yield make
    for c in made:
        c.close()


@pytest.fixture(params=[DESKTOP, LAPTOP], ids=["1440", "1280"])
def desk(request, canvas_page):
    page = canvas_page(viewport=request.param, touch=False)
    return page


def park(page):
    return page.locator(".cz-gb.is-park").first.get_attribute("data-act")


def dock(page):
    return page.locator("#cz-dock")


def mode(page):
    return dock(page).get_attribute("data-mode")


def tab(page):
    return dock(page).locator('.cz-dock-tab[data-tab="family"]')


def rows(page):
    return dock(page).locator(".cz-fam-th")


def thread(page):
    return dock(page).locator("#ft-thread")


def open_family(page):
    tab(page).click()
    expect(dock(page).locator(".cz-fam")).to_be_visible()
    expect(thread(page)).to_be_visible()


def test_the_family_tab_lists_the_chats_with_unread_counts_and_opens_one_below_with_compose(desk, mates):
    mate = mates(desk)
    act = None
    open_day(desk, SATURDAY)
    act = park(desk)
    mate.say("Are we bringing the scooter?")
    mate.say("Eggslut line is short", act=act)
    open_day(desk, SATURDAY)                                                             # (a fresh load of the day: the count comes from the server)
    expect(tab(desk).locator(".cz-dock-un")).to_have_text(re.compile(r"^2"))
    desk.evaluate("window.__loaded = 1")
    tab(desk).click()
    expect(dock(desk).locator(".cz-fam")).to_be_visible()
    assert mode(desk) == "family" and desk.evaluate("window.__loaded") == 1             # no page load
    expect(tab(desk)).to_have_attribute("aria-selected", "true")
    expect(dock(desk).locator("[data-pane=idle]")).to_be_hidden()
    expect(rows(desk)).to_have_count(2)
    expect(rows(desk).nth(0).locator(".cz-fam-tt")).to_have_text("Whole trip")                     # the whole trip first
    expect(rows(desk).nth(0)).to_have_attribute("aria-current", "true")
    expect(rows(desk).nth(0).locator(".cz-fam-ls")).to_contain_text("Are we bringing the scooter?")
    expect(rows(desk).nth(1).locator(".cz-fam-tt")).to_contain_text("Universal")
    expect(rows(desk).nth(1).locator(".cz-fam-un")).to_have_text(re.compile(r"^1"))               # the plan's chat has one unread; the open one has none
    expect(rows(desk).nth(0).locator(".cz-fam-un")).to_have_count(0)
    expect(tab(desk).locator(".cz-dock-un")).to_have_text(re.compile(r"^1"))
    expect(thread(desk).locator(".ft-bub").first).to_contain_text("Are we bringing the scooter?")
    expect(dock(desk).locator("#ft-compose #ft-text")).to_be_visible()                       # compose below, at the panel's foot
    assert "panel=family" in desk.url and "thread=" not in desk.url
    expect(desk.locator(".ga-tb-family")).to_have_attribute("aria-current", "page")
    assert desk.evaluate(NO_SCROLL) == [True, True, 0]
    shot(desk, f"list-{desk.viewport_size['width']}.png")
    rows(desk).nth(1).click()                                                             # another chat: in place
    expect(thread(desk).locator(".ft-bub").first).to_contain_text("Eggslut line is short")
    expect(dock(desk).locator(".cz-fam-hd")).to_contain_text("Universal")
    expect(rows(desk).nth(1)).to_have_attribute("aria-current", "true")
    expect(tab(desk).locator(".cz-dock-un")).to_have_count(0)                              # everything read
    assert f"thread={act}" in desk.url and desk.evaluate("window.__loaded") == 1
    shot(desk, f"thread-{desk.viewport_size['width']}.png")
    dock(desk).locator("#ft-text").fill("Sent with the button")
    dock(desk).locator("#ft-send").click()
    expect(thread(desk).locator(".ft-me")).to_contain_text("Sent with the button")
    expect(dock(desk).locator("#ft-text")).to_have_value("")
    rows(desk).nth(0).click()                                                             # back to the whole trip
    expect(thread(desk).locator(".ft-bub").first).to_contain_text("Are we bringing the scooter?")
    assert "thread=" not in desk.url
    dock(desk).locator("#ft-text").fill("Whole trip reply")
    dock(desk).locator("#ft-send").click()
    expect(thread(desk).locator(".ft-me")).to_contain_text("Whole trip reply")
    desk.reload()                                                                         # the address keeps the chats: the server draws them
    expect(dock(desk).locator(".cz-fam")).to_be_visible()
    expect(thread(desk).locator(".ft-bub").last).to_contain_text("Whole trip reply")
    assert mode(desk) == "family"


def test_people_and_invites_is_a_link_to_the_family_page(desk):
    open_day(desk, SATURDAY)
    open_family(desk)
    link = dock(desk).locator("#cz-fam-people")
    expect(link).to_have_text("People and invites")
    link.click()
    desk.wait_for_url(re.compile(r"/family$"))
    expect(desk.locator(".ga-topbar")).to_be_visible()


def test_the_top_bars_family_opens_the_panel_in_place(desk):
    open_day(desk, SATURDAY)
    desk.evaluate("window.__loaded = 1")
    desk.locator(".ga-topbar .ga-tb-family").click()
    expect(dock(desk).locator(".cz-fam")).to_be_visible()
    assert mode(desk) == "family" and desk.evaluate("window.__loaded") == 1
    expect(desk.locator(".ga-tb-family")).to_have_attribute("aria-current", "page")
    expect(desk.locator(".ga-tb-trip")).not_to_have_attribute("aria-current", "page")
    dock(desk).locator('.cz-dock-tab[data-tab="plan"]').click()                                        # the Plan tab puts Up next back, and the bar follows
    expect(dock(desk).locator("[data-pane=idle]")).to_be_visible()
    expect(desk.locator(".ga-tb-trip")).to_have_attribute("aria-current", "page")
    assert mode(desk) != "family" and "panel=family" not in desk.url


def test_the_top_bars_family_from_another_page_lands_on_the_day_with_the_chats_open(desk):
    desk.goto(re.sub(r"^(https?://[^/]+).*", r"\1/family", desk.url))
    desk.locator(".ga-topbar .ga-tb-family").click()
    desk.wait_for_url(re.compile(r"/trip/canvas\?day=\d+&panel=family"))
    expect(dock(desk).locator(".cz-fam")).to_be_visible()
    expect(thread(desk)).to_be_visible()


@pytest.mark.parametrize("path", ["/trip/family/thread", "/trip/family"])
def test_opening_the_thread_address_directly_shows_the_day_with_the_chat_open_never_a_blank_page(desk, path):
    desk.goto(re.sub(r"^(https?://[^/]+).*", rf"\1{path}", desk.url))
    desk.wait_for_url(re.compile(r"/trip/canvas\?day=\d+&panel=family"))
    expect(dock(desk).locator(".cz-fam")).to_be_visible()
    expect(thread(desk)).to_be_visible()
    expect(dock(desk).locator("#ft-compose")).to_be_visible()
    expect(desk.locator(".cz-view[data-day]")).to_be_visible()                           # the day itself is there
    assert desk.evaluate("document.body.innerText.trim().length") > 50


def test_a_new_message_shows_without_reloading_and_nothing_moves(desk, mates):
    mate = mates(desk)
    open_day(desk, SATURDAY)
    act = park(desk)
    mate.say("first")
    open_family(desk)
    expect(thread(desk).locator(".ft-bub")).to_have_count(1)
    desk.evaluate("window.__loaded = 1")
    mate.say("Second one, no reload")
    expect(thread(desk).locator(".ft-bub").last).to_contain_text("Second one, no reload", timeout=9000)
    assert desk.evaluate("window.__loaded") == 1
    expect(thread(desk).locator(".ft-bub")).to_have_count(2)                              # nothing doubled by later polls
    assert desk.evaluate("document.querySelector('#ft-thread .ft-msg:last-child').getAnimations({subtree: true}).length") == 0       # no motion on an incoming message (F-118)
    mate.say("In the plan's chat", act=act)                                                 # another chat: its row shows the news, with a count
    expect(rows(desk).nth(1).locator(".cz-fam-ls")).to_contain_text("In the plan's chat", timeout=9000)
    expect(rows(desk).nth(1).locator(".cz-fam-un")).to_have_text(re.compile(r"^1"))
    expect(tab(desk).locator(".cz-dock-un")).to_have_text(re.compile(r"^1"))
    shot(desk, f"arrived-{desk.viewport_size['width']}.png")
    assert desk.evaluate(NO_SCROLL) == [True, True, 0]


def test_the_plan_panes_chat_shows_others_new_messages_without_reloading(desk, mates):
    mate = mates(desk)
    open_day(desk, SATURDAY)
    act = park(desk)
    b = desk.locator(f'.cz-gb[data-act="{act}"]')
    b.scroll_into_view_if_needed()
    box = b.bounding_box()
    desk.mouse.click(box["x"] + box["width"] * 0.7, box["y"] + min(box["height"] * 0.6, 90))
    expect(desk.locator("#cz-pp-msgs")).to_be_visible()
    desk.evaluate("window.__loaded = 1")
    mate.say("Hello from the plan", act=act)
    expect(desk.locator("#cz-pp-msgs").get_by_text("Hello from the plan")).to_be_visible(timeout=9000)
    mate.say("And another", act=act)
    expect(desk.locator("#cz-pp-msgs").get_by_text("And another")).to_be_visible(timeout=9000)
    expect(desk.locator("#cz-pp-msgs .ft-msg")).to_have_count(2)
    assert desk.evaluate("window.__loaded") == 1 and mode(desk) == "plan"
    desk.locator("#cz-dock .cz-pp-text").fill("My reply")                                   # a send after a poll still works and is not doubled
    desk.locator("#cz-dock .cz-pp-send").click()
    expect(desk.locator("#cz-pp-msgs").get_by_text("My reply")).to_be_visible()
    desk.wait_for_timeout(6000)
    expect(desk.locator("#cz-pp-msgs .ft-msg")).to_have_count(3)


def test_open_in_family_opens_that_plans_chat_in_place(desk, mates):
    mate = mates(desk)
    open_day(desk, SATURDAY)
    act = park(desk)
    mate.say("About the park", act=act)
    b = desk.locator(f'.cz-gb[data-act="{act}"]')
    b.scroll_into_view_if_needed()
    box = b.bounding_box()
    desk.mouse.click(box["x"] + box["width"] * 0.7, box["y"] + min(box["height"] * 0.6, 90))
    expect(desk.locator("#cz-pp-family")).to_be_visible()
    desk.evaluate("window.__loaded = 1")
    desk.locator("#cz-pp-family").click()
    expect(dock(desk).locator(".cz-fam")).to_be_visible()
    assert mode(desk) == "family" and desk.evaluate("window.__loaded") == 1
    expect(dock(desk).locator(".cz-fam-hd")).to_contain_text("Universal")
    expect(thread(desk).locator(".ft-bub").first).to_contain_text("About the park")
    expect(rows(desk).nth(1)).to_have_attribute("aria-current", "true")
    assert f"thread={act}" in desk.url


def test_the_chats_stay_open_when_another_day_is_picked(desk):
    open_day(desk, SATURDAY)
    open_family(desk)
    desk.locator(".cz-hchip").first.click()
    desk.wait_for_function("() => document.querySelector('.cz-view[data-day]').dataset.day === '0'")
    expect(dock(desk).locator(".cz-fam")).to_be_visible()
    assert mode(desk) == "family" and "day=0" in desk.url and "panel=family" in desk.url


def test_nothing_is_asked_for_while_the_pane_is_closed_or_the_tab_is_hidden(desk):
    asked = []
    desk.on("request", lambda r: asked.append(r.url) if re.search(r"/trip/(family/(thread|list)|talk/items)", r.url) else None)
    open_day(desk, SATURDAY)
    desk.wait_for_timeout(6500)
    assert asked == []                                                                    # Up next: no chat is polled
    open_family(desk)
    desk.wait_for_timeout(6500)
    assert any("/trip/family/thread" in u for u in asked) and any("/trip/family/list" in u for u in asked)
    desk.evaluate("() => { Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'hidden' }); document.dispatchEvent(new Event('visibilitychange')); }")
    desk.wait_for_timeout(300)
    asked.clear()
    desk.wait_for_timeout(6500)
    assert asked == []                                                                    # a hidden tab asks for nothing
    desk.evaluate("() => { Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'visible' }); document.dispatchEvent(new Event('visibilitychange')); }")
    desk.wait_for_timeout(1500)
    assert any("/trip/family" in u for u in asked)                                         # and asks once as soon as it is seen again
    dock(desk).locator('.cz-dock-tab[data-tab="plan"]').click()
    desk.wait_for_timeout(300)
    asked.clear()
    desk.wait_for_timeout(6500)
    assert asked == []                                                                    # Up next again: quiet


def test_a_long_chat_scrolls_inside_the_panel_not_the_page(desk, mates):
    mate = mates(desk)
    open_day(desk, SATURDAY)
    for i in range(30):
        mate.say(f"Message number {i} with some words to take space")
    open_family(desk)
    box = thread(desk).evaluate("e => ({ sh: e.scrollHeight, ch: e.clientHeight, top: e.scrollTop, oy: getComputedStyle(e).overflowY })")
    assert box["sh"] > box["ch"] and box["oy"] == "auto" and box["top"] + box["ch"] >= box["sh"] - 4          # the newest message is in view
    assert desk.evaluate(NO_SCROLL) == [True, True, 0]
    bottom = dock(desk).locator("#ft-compose").bounding_box()
    assert bottom["y"] + bottom["height"] <= desk.viewport_size["height"]


@pytest.mark.parametrize("viewport,name", [(TABLET, "1000"), (PHONE, "390")])
def test_a_tablet_and_a_phone_keep_todays_family_chat(canvas_page, viewport, name, mates):
    page = canvas_page(viewport=viewport, touch=viewport is PHONE)
    mates(page).say("Hello family")
    page.goto(re.sub(r"^(https?://[^/]+).*", r"\1/trip/family", page.url))
    page.wait_for_selector("#ft-thread")
    page.wait_for_timeout(500)
    assert page.url.endswith("/trip/family")                                                # no hand-over to the day
    expect(page.locator("#ft-thread")).to_contain_text("Hello family")
    expect(page.locator("#ft-compose")).to_be_visible()
    page.goto(re.sub(r"^(https?://[^/]+).*", r"\1/trip/canvas?day=1", page.url))
    page.wait_for_selector(".cz-view[data-day]")
    expect(page.locator("#cz-dock")).to_be_hidden()                                          # the panel is a laptop's
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
