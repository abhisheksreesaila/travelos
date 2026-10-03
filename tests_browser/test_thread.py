"""F-070: the Family tab in a real browser at phone width: a message posted in one browser appears in a second family member's browser within the
poll interval, the thread stops asking while the page is hidden, the Quiet switch works, nothing scrolls sideways, and the service worker shows a
family push and opens /trip/family when it is tapped."""
import re
import uuid

import pytest
from playwright.sync_api import expect

from tests_browser.helpers import PHONE

NARROW = {"width": 320, "height": 640}


@pytest.fixture
def pair(browser, base_url):
    """pair() -> (ari's page, the invited editor's page), both on /trip/family of the sample trip, phone width."""
    contexts = []

    def sign_in(email):
        ctx = browser.new_context(viewport=PHONE, reduced_motion="reduce", has_touch=True, is_mobile=True)
        ctx.set_default_timeout(5000)
        contexts.append(ctx)
        ctx.request.post(f"{base_url}/signin", form={"email": email, "next": "/", "intent": "save"}, max_redirects=0)
        return ctx

    def make():
        ari = sign_in("ari.rivera@example.com")
        ari.request.post(f"{base_url}/pay", form={"f": "f1", "h": "h1", "c": "c1"}, max_redirects=0)
        mate = f"mate.{uuid.uuid4().hex[:8]}@gmail.com"
        ari.request.post(f"{base_url}/family/invite", form={"email": mate, "role": "editor"}, max_redirects=0)
        other = sign_in(mate)
        pages = []
        for ctx in (ari, other):
            ctx.set_default_timeout(9000)
            page = ctx.new_page()
            page.goto(f"{base_url}/trip/family")
            pages.append(page)
        return pages

    yield make
    for c in contexts:
        c.close()


def overflow(page):
    return page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")


def test_a_message_posted_in_one_browser_appears_in_the_other_within_the_poll_interval(pair):
    ari, mate = pair()
    expect(ari.locator("#ft-empty")).to_be_visible()
    ari.locator("#ft-text").fill("Pool at four if anyone is up for it")
    ari.locator("#ft-send").click()
    expect(ari.locator("#ft-thread .ft-me")).to_contain_text("Pool at four if anyone is up for it")     # the sender sees it at once
    expect(ari.locator("#ft-empty")).to_be_hidden()
    assert ari.locator("#ft-text").input_value() == ""
    expect(mate.locator("#ft-thread .ft-msg")).to_contain_text("Pool at four if anyone is up for it", timeout=9000)   # ~5 s poll
    expect(mate.locator("#ft-thread .ft-nm")).to_have_text("Ari")
    assert mate.locator("#ft-thread .ft-me").count() == 0
    mate.locator("#ft-text").fill("Yes!")
    mate.locator("#ft-send").click()
    expect(ari.locator("#ft-thread .ft-msg").nth(1)).to_contain_text("Yes!", timeout=9000)
    assert ari.locator("#ft-thread .ft-msg").count() == 2                                                 # nothing doubled by the polls


def test_a_plan_change_shows_up_as_a_card_for_the_other_browser(pair, base_url):
    ari, mate = pair()
    ari.context.request.post(f"{base_url}/calendar/activities", form={"id": "a1", "day": "1", "start": "10:00", "end": "11:00", "title": "Griffith Observatory", "kind": "culture"}, max_redirects=0)
    card = mate.locator("#ft-thread .ft-sys")
    expect(card).to_contain_text("added Griffith Observatory on", timeout=9000)
    expect(card).to_contain_text("Plan change")
    assert card.count() == 1


def test_the_thread_does_not_ask_while_hidden_and_asks_again_when_shown(pair):
    ari, mate = pair()
    asked = []
    mate.on("request", lambda r: asked.append(r.url) if "/trip/family/thread" in r.url else None)
    mate.evaluate("""() => { Object.defineProperty(document, "visibilityState", { configurable: true, get: () => "hidden" }); document.dispatchEvent(new Event("visibilitychange")); }""")
    ari.locator("#ft-text").fill("Anyone there?")
    ari.locator("#ft-send").click()
    expect(ari.locator("#ft-thread .ft-me")).to_contain_text("Anyone there?")
    mate.wait_for_timeout(6500)                                                       # longer than the poll interval
    assert asked == [] and mate.locator("#ft-thread .ft-msg").count() == 0
    mate.evaluate("""() => { Object.defineProperty(document, "visibilityState", { configurable: true, get: () => "visible" }); document.dispatchEvent(new Event("visibilitychange")); }""")
    expect(mate.locator("#ft-thread .ft-msg")).to_contain_text("Anyone there?", timeout=3000)   # asked at once, not after another interval
    assert len(asked) >= 1


def test_the_quiet_switch_changes_in_place_and_is_remembered(pair):
    ari, _ = pair()
    switch = ari.locator("#ft-quiet")
    expect(switch).to_have_attribute("aria-checked", "false")
    switch.click()
    expect(switch).to_have_attribute("aria-checked", "true")
    expect(ari.locator("#ft-quiet-text")).to_contain_text("Quiet: no notifications")
    ari.reload()
    expect(ari.locator("#ft-quiet")).to_have_attribute("aria-checked", "true")           # kept on the server, not just on this page
    ari.locator("#ft-quiet").click()
    expect(ari.locator("#ft-quiet")).to_have_attribute("aria-checked", "false")
    expect(ari.locator("#ft-quiet-text")).to_contain_text("Everyone gets a notification")


def test_an_empty_message_asks_for_words_and_sends_nothing(pair):
    ari, _ = pair()
    ari.locator("#ft-send").click()                                                      # the field is required: the browser stops it
    assert ari.locator("#ft-thread .ft-msg").count() == 0
    ari.locator("#ft-text").fill("   ")
    ari.locator("#ft-send").click()
    expect(ari.locator("#ft-error")).to_contain_text("Write something first.")
    assert ari.locator("#ft-thread .ft-msg").count() == 0


@pytest.mark.parametrize("viewport", [PHONE, NARROW], ids=["390", "320"])
def test_the_tab_fits_the_phone_without_sideways_scroll_and_with_big_enough_targets(pair, viewport):
    ari, _ = pair()
    ari.set_viewport_size(viewport)
    for text in ("A long message with a_very_long_unbroken_word_that_could_push_the_bubble_wider_than_the_phone_if_nothing_wrapped_it " * 2, "Short one"):
        ari.locator("#ft-text").fill(text)
        ari.locator("#ft-send").click()
        expect(ari.locator("#ft-thread .ft-msg").last).to_be_visible()
    assert overflow(ari) <= 0
    for sel in ("#ft-send", "#ft-quiet", "#ft-text"):
        box = ari.locator(sel).bounding_box()
        assert box["height"] >= 43.9 and box["width"] >= 43.9, sel
    small = ari.evaluate("""() => [...document.querySelectorAll('#ft *')].filter(e => e.childNodes.length && [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim()) && parseFloat(getComputedStyle(e).fontSize) < 13).length""")
    assert small == 0


RUN_SW = """async (source) => {
  const handlers = {}, shown = [], opened = [], closed = [];
  const self_ = { location: { origin: location.origin }, addEventListener: (t, f) => { handlers[t] = f; }, skipWaiting() {}, registration: { showNotification: async (title, options) => { shown.push({ title, options }); } },
                  clients: { matchAll: async () => [], openWindow: async (u) => { opened.push(u); }, claim() {} } };
  new Function("self", "caches", "fetch", source)(self_, {}, () => {});
  const wait = [];
  const event = (extra) => Object.assign({ waitUntil: (p) => wait.push(p) }, extra);
  await handlers.push(event({ data: { json: () => ({ title: "Plan changed", body: "Abhi moved Griffith Observatory to Tue 10:00 AM", url: "/trip/family", tag: "family-thread" }) } }));
  await handlers.push(event({ data: { json: () => ({ title: "x", tag: "<script>", url: "https://evil.example.com/x" }) } }));
  await Promise.all(wait.splice(0));
  await handlers.notificationclick(event({ notification: { close: () => closed.push(1), data: shown[0].options.data } }));
  await Promise.all(wait.splice(0));
  return { shown, opened, closed: closed.length };
}"""


def test_the_service_worker_shows_a_family_push_and_a_tap_opens_the_family_tab(browser, base_url):
    page = browser.new_page()
    try:
        page.goto(f"{base_url}/offline")
        out = page.evaluate(RUN_SW, page.evaluate("fetch('/sw.js').then(r => r.text())"))
    finally:
        page.close()
    first, second = out["shown"]
    assert first["title"] == "Plan changed" and first["options"]["tag"] == "family-thread" and first["options"]["data"]["url"] == "/trip/family"
    assert first["options"]["body"] == "Abhi moved Griffith Observatory to Tue 10:00 AM"
    assert second["options"]["tag"] == "morning-plan" and second["options"]["data"]["url"] == "/trip"   # a tag that is not a plain word is ignored, and so is another site's address
    assert out["opened"] == [base_url + "/trip/family"] and out["closed"] == 1
