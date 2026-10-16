"""F-177: Family opens at once, the first time too. On the laptop (1440) the pane is fetched ahead when the page has been idle a moment, so the Family tab and the top bar's Family (from the day or
the week) show the messages in the same frame as the click, with no page load and no request waited for, even with the server slowed 700 ms. A panel draws the newest 30 messages and
"Earlier messages" (pressed here) puts the 30 before them above, keeping the place. The phone's Family tab is still the page it was. Set F177_TIMES=1 to print the numbers (ms from click to messages)."""
import os
import re
import time

from playwright.sync_api import expect

from tests_browser.helpers import DESKTOP, PHONE
from tests_browser.test_day_grid import open_day
from tests_browser.test_family_panel import dock, mates, mode, tab, thread  # noqa: F401 - fixtures
from tests_browser.test_trip_canvas import canvas_page, model  # noqa: F401 - fixtures

SATURDAY = 1
SLOW = 0.7
IDLE_MS = 2500
SERVER = re.compile(r"/trip/family/(panel|list|thread|seen)")


def slow(page, seen, slow_server):
    """Every family request waits 700 ms in the server itself (conftest `slow_server`: an asyncio sleep, so nothing in the test's thread is held up) and is recorded in `seen`."""
    slow_server(r"^/trip/family/(panel|list|thread|seen)", SLOW)
    page.on("request", lambda r: SERVER.search(r.url) and seen.append((SERVER.search(r.url).group(1), time.monotonic())))


WATCH = """() => {
  window.__ms = null;
  const mark = () => { if (window.__ms === null && document.querySelector('#cz-dock #ft-thread .ft-bub')) window.__ms = performance.now() - window.__down; };
  document.addEventListener('pointerdown', () => { window.__down = performance.now(); }, { capture: true, once: true });
  new MutationObserver(mark).observe(document.documentElement, { childList: true, subtree: true });
}"""


def timed(page, click, ready):
    """Milliseconds from the pointer going down until the first message is in the panel, measured in the page itself (the test's own thread is held up by the slowed routes)."""
    page.evaluate(WATCH)
    click()
    expect(ready).to_be_visible()
    page.wait_for_function("window.__ms !== null")
    return round(page.evaluate("window.__ms"))


def say(n):
    print(f"F177 {n}") if os.environ.get("F177_TIMES") else None


def test_the_family_tab_shows_the_messages_in_the_click_frame_with_the_server_slowed(canvas_page, mates, slow_server):
    page = canvas_page(viewport=DESKTOP, touch=False)
    mate = mates(page)
    mate.say("Are we bringing the scooter?")
    open_day(page, SATURDAY)
    seen = []
    slow(page, seen, slow_server)
    page.evaluate("window.__loaded = 1")
    page.wait_for_timeout(IDLE_MS)                                  # idle a moment: the pane is fetched ahead (slowly)
    asked = [s[0] for s in seen]
    assert "panel" in asked                                         # (it was asked for before anyone clicked)
    before = len(seen)
    ms = timed(page, lambda: tab(page).click(), thread(page).locator(".ft-bub").first)
    say(f"warm click -> messages visible: {ms} ms (server slowed {int(SLOW * 1000)} ms)")
    assert mode(page) == "family" and page.evaluate("window.__loaded") == 1          # no page load
    expect(thread(page).locator(".ft-bub").first).to_contain_text("Are we bringing the scooter?")
    assert ms < 400, ms                                              # nothing was waited for
    assert [s[0] for s in seen[before:]].count("panel") == 0         # (no panel request after the click)


def test_the_top_bar_family_on_the_day_is_just_as_fast(canvas_page, mates, slow_server):
    page = canvas_page(viewport=DESKTOP, touch=False)
    mate = mates(page)
    mate.say("Top bar hello")
    open_day(page, SATURDAY)
    seen = []
    slow(page, seen, slow_server)
    page.evaluate("window.__loaded = 1")
    page.wait_for_timeout(IDLE_MS)
    ms = timed(page, lambda: page.locator(".ga-tb-family").click(), thread(page).locator(".ft-bub").first)
    say(f"top bar (day) click -> messages visible: {ms} ms")
    assert mode(page) == "family" and page.evaluate("window.__loaded") == 1 and ms < 400, ms
    expect(thread(page).locator(".ft-bub").first).to_contain_text("Top bar hello")


def test_the_top_bar_family_on_the_week_opens_the_day_with_the_chats_without_a_page_load(canvas_page, mates, slow_server):
    page = canvas_page(viewport=DESKTOP, touch=False)
    mate = mates(page)
    mate.say("Week hello")
    page.goto(re.sub(r"^(https?://[^/]+).*", lambda m: f"{m.group(1)}/trip/canvas", page.url))
    page.wait_for_selector(".cz-view[data-level=week]")
    seen = []
    slow(page, seen, slow_server)
    page.evaluate("window.__loaded = 1")
    page.wait_for_timeout(IDLE_MS)
    assert "panel" in [s[0] for s in seen]                           # fetched ahead on the week too
    ms = timed(page, lambda: page.locator(".ga-tb-family").click(), thread(page).locator(".ft-bub").first)
    say(f"top bar (week) click -> day + messages visible: {ms} ms")
    assert page.evaluate("window.__loaded") == 1 and mode(page) == "family" and "panel=family" in page.url, page.url
    expect(page.locator(".cz-view[data-level=day]")).to_be_visible()
    expect(thread(page).locator(".ft-bub").first).to_contain_text("Week hello")


def test_a_click_before_the_page_was_idle_still_opens_and_shows_the_same_messages(canvas_page, mates, slow_server):
    page = canvas_page(viewport=DESKTOP, touch=False)
    mate = mates(page)
    mate.say("Cold hello")
    open_day(page, SATURDAY)
    seen = []
    slow(page, seen, slow_server)
    ms = timed(page, lambda: tab(page).click(), thread(page).locator(".ft-bub").first)
    say(f"cold click (not yet idle) -> messages visible: {ms} ms")
    expect(thread(page).locator(".ft-bub").first).to_contain_text("Cold hello")


def test_earlier_messages_are_asked_for_with_a_button_and_keep_the_place(canvas_page, mates):
    page = canvas_page(viewport=DESKTOP, touch=False)
    mate = mates(page)
    for i in range(1, 46):
        mate.say(f"m{i:02d}")
    open_day(page, SATURDAY)
    tab(page).click()
    expect(thread(page).locator(".ft-bub")).to_have_count(30)
    expect(thread(page).locator(".ft-bub").first).to_contain_text("m16")
    older = dock(page).locator("#ft-older")
    expect(older).to_be_visible()
    older.click()
    expect(thread(page).locator(".ft-bub")).to_have_count(45)
    expect(thread(page).locator(".ft-bub").first).to_contain_text("m01")
    expect(dock(page).locator("#ft-older")).to_have_count(0)         # nothing earlier is left
    # the place is kept: the newest message is still where it was (the reader is not thrown to the top)
    near = page.evaluate("(() => { const t = document.getElementById('ft-thread'); return t.scrollHeight - t.scrollTop - t.clientHeight; })()")
    assert near < 200, near
    mate.say("m46")
    expect(thread(page).locator(".ft-bub").last).to_contain_text("m46", timeout=9000)            # the live poll (every 5 s) still adds to the end


def test_the_phone_family_tab_is_the_page_it_was(canvas_page, mates, slow_server):
    page = canvas_page(viewport=PHONE)
    mate = mates(page)
    mate.say("Phone hello")
    seen = []
    slow(page, seen, slow_server)
    t = time.monotonic()
    page.goto(re.sub(r"^(https?://[^/]+).*", lambda m: f"{m.group(1)}/trip/family", page.url))
    expect(page.locator("#ft-thread .ft-bub").first).to_contain_text("Phone hello")
    say(f"phone Family page -> messages visible: {round((time.monotonic() - t) * 1000)} ms")
    page.wait_for_timeout(IDLE_MS)
    assert "panel" not in [s[0] for s in seen]                         # the phone draws the page itself and fetches no panel ahead
    assert "/trip/family" in page.url and "panel=family" not in page.url


def test_a_message_sent_after_the_prefetch_shows_at_once_on_the_click(canvas_page, mates):
    page = canvas_page(viewport=DESKTOP, touch=False)
    mate = mates(page)
    mate.say("before the prefetch")
    with page.expect_response(re.compile(r"/trip/family/panel"), timeout=9000):
        open_day(page, SATURDAY)                                     # (the page idles a moment, then the pane is fetched ahead)
    mate.say("after the prefetch")                                   # (the copy is only a moment old when it is clicked)
    t = time.monotonic()
    tab(page).click()
    expect(thread(page).locator(".ft-bub").last).to_contain_text("after the prefetch", timeout=3000)
    assert time.monotonic() - t < 3                                  # well under the 5 s poll
