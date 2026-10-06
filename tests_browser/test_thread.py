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
    for sel in ("#ft-send", "#ft-quiet", "#ft-text", "#ft-invite"):
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


def test_a_tab_for_a_trip_that_is_gone_shows_a_short_friendly_error(pair):
    ari, _ = pair()
    ari.evaluate("document.querySelector('#ft-compose input[name=trip]').value = 'gone-trip'; document.getElementById('ft-thread').setAttribute('data-trip', 'gone-trip')")
    ari.locator("#ft-text").fill("Hello?")
    ari.locator("#ft-send").click()
    expect(ari.locator("#ft-thread .ft-me")).to_contain_text("This trip changed. Reload the page.")   # the bubble says so and keeps the text
    expect(ari.locator("#ft-thread .ft-me")).to_contain_text("Hello?")


# ---- F-094: lighter and instant ------------------------------------------------------------------------------------------

def test_the_chat_photos_switch_is_two_small_words_and_the_invite_stays_small(pair):
    ari, _ = pair()
    chat, photos = ari.locator("#fam-chat"), ari.locator("#fam-photos")
    assert ari.locator("#famseg").bounding_box()["height"] <= 48                      # one slim line, not a big pill of buttons
    assert abs(ari.locator("#ft-invite").bounding_box()["y"] - ari.locator("#famseg").bounding_box()["y"]) < 8 and ari.locator("#ft-invite").bounding_box()["height"] >= 43.9
    expect(chat).to_have_attribute("aria-current", "true")
    photos.click()
    expect(photos).to_have_attribute("aria-current", "true")
    expect(ari.locator("#ft-chat")).to_be_hidden()
    chat.click()
    expect(ari.locator("#ft-chat")).to_be_visible()
    assert ari.locator("#ft-invite").evaluate("e => getComputedStyle(e).backgroundColor") in ("rgba(0, 0, 0, 0)", "transparent")   # not a big button
    assert ari.locator("#ft-text").bounding_box()["y"] < 844 and ari.locator("#ft-thread").bounding_box()["y"] < 260   # the thread starts high


def test_send_shows_the_bubble_at_once_then_confirms(pair):
    ari, _ = pair()
    ari.route("**/trip/family/message", lambda route: (ari.wait_for_timeout(1500), route.continue_())[1])
    ari.locator("#ft-text").fill("On my way")
    ari.locator("#ft-send").click()
    bubble = ari.locator("#ft-thread .ft-me")
    expect(bubble).to_contain_text("On my way", timeout=400)                           # before the server answered
    expect(bubble).to_have_class(re.compile("is-sending"))
    assert ari.locator("#ft-text").input_value() == "" and ari.evaluate("document.activeElement.id") == "ft-text"
    expect(bubble).not_to_have_class(re.compile("is-sending"), timeout=6000)             # the server confirmed
    assert ari.locator("#ft-thread .ft-msg").count() == 1
    ari.wait_for_timeout(5600)                                                            # a poll later: still one
    assert ari.locator("#ft-thread .ft-msg").count() == 1


def test_a_failed_send_says_so_keeps_the_text_and_retry_sends_it(pair):
    ari, _ = pair()
    ari.route("**/trip/family/message", lambda route: route.abort())
    ari.locator("#ft-text").fill("Meet at the gate")
    ari.locator("#ft-send").click()
    bubble = ari.locator("#ft-thread .ft-me")
    expect(bubble).to_contain_text("Meet at the gate")
    expect(bubble).to_contain_text("Not sent")
    retry = bubble.get_by_role("button", name="Retry")
    expect(retry).to_be_visible()
    expect(ari.locator("#ft-compose ~ .sr-only[role=status], #ft-thread ~ .sr-only[role=status]")).to_contain_text("Message not sent")   # spoken too
    assert retry.bounding_box()["height"] >= 43.9
    ari.unroute("**/trip/family/message")
    retry.click()
    expect(ari.locator("#ft-thread .is-failed, #ft-thread .is-sending")).to_have_count(0)
    expect(ari.locator("#ft-thread .ft-msg")).to_have_count(1)
    expect(ari.locator("#ft-thread .ft-me")).to_contain_text("Meet at the gate")
    assert ari.evaluate("document.activeElement.id") == "ft-text"


def test_retry_after_a_lost_reply_is_one_message(pair):
    ari, mate = pair()
    ari.route("**/trip/family/message", lambda route: (route.fetch(), route.abort())[1])   # the server saves it, the reply never comes back
    ari.locator("#ft-text").fill("Saved but unheard")
    ari.locator("#ft-send").click()
    expect(ari.locator("#ft-thread .is-failed")).to_have_count(1)
    ari.unroute("**/trip/family/message")
    ari.locator("#ft-thread .ft-retry").click()
    expect(ari.locator("#ft-thread .is-failed, #ft-thread .is-sending")).to_have_count(0)
    expect(ari.locator("#ft-thread .ft-msg")).to_have_count(1)
    ari.wait_for_timeout(5600)                                                              # a poll later: still one, here and for the other
    assert ari.locator("#ft-thread .ft-msg").count() == 1
    expect(mate.locator("#ft-thread .ft-msg")).to_have_count(1, timeout=9000)


def test_a_poll_that_brings_my_own_message_replaces_the_failed_bubble(pair):
    ari, _ = pair()
    ari.route("**/trip/family/message", lambda route: (route.fetch(), route.abort())[1])
    ari.locator("#ft-text").fill("Heard by the poll")
    ari.locator("#ft-send").click()
    expect(ari.locator("#ft-thread .is-failed")).to_have_count(1)
    expect(ari.locator("#ft-thread .is-failed")).to_have_count(0, timeout=9000)             # the next poll swaps in the real one
    expect(ari.locator("#ft-thread .ft-msg")).to_have_count(1)


def test_a_request_that_never_answers_ends_as_a_failed_send_and_the_chat_goes_on(pair):
    ari, mate = pair()
    ari.evaluate("document.getElementById('ft-thread').setAttribute('data-send-timeout', '800')")
    ari.route("**/trip/family/message", lambda route: None)                                  # never answered
    ari.locator("#ft-text").fill("Into the void")
    ari.locator("#ft-send").click()
    expect(ari.locator("#ft-thread .is-failed")).to_have_count(1, timeout=4000)
    mate.locator("#ft-text").fill("Still here")
    mate.locator("#ft-send").click()
    expect(ari.locator("#ft-thread .ft-msg").filter(has_text="Still here")).to_have_count(1, timeout=9000)   # polls were not frozen


def test_two_quick_sends_keep_their_order_when_confirmed(pair):
    ari, _ = pair()
    ari.route("**/trip/family/message", lambda route: (ari.wait_for_timeout(500), route.continue_())[1])
    for word in ("Alpha", "Bravo"):
        ari.locator("#ft-text").fill(word)
        ari.locator("#ft-send").click()
    expect(ari.locator("#ft-thread .is-sending")).to_have_count(0, timeout=6000)
    assert ari.locator("#ft-thread .ft-msg").all_inner_texts()[0].count("Alpha") == 1
    assert ari.locator("#ft-thread .ft-msg").all_inner_texts()[1].count("Bravo") == 1


def test_a_refused_message_goes_back_to_the_box_with_the_reason(pair):
    ari, _ = pair()
    ari.evaluate("document.getElementById('ft-text').removeAttribute('maxlength')")
    ari.locator("#ft-text").fill("x" * 700)
    ari.locator("#ft-send").click()
    expect(ari.locator("#ft-error")).to_contain_text("Keep messages to")
    expect(ari.locator("#ft-thread .ft-msg")).to_have_count(0)
    assert ari.locator("#ft-text").input_value() == "x" * 700 and ari.evaluate("document.activeElement.id") == "ft-text"


def test_new_bubbles_fade_in_unless_motion_is_reduced(pair):
    ari, mate = pair()
    for p in (ari, mate):
        p.emulate_media(reduced_motion="no-preference")
    mate.evaluate("""() => { window.__fade = []; new MutationObserver(ms => ms.forEach(m => m.addedNodes.forEach(n => { if (n.nodeType === 1) window.__fade.push(n.getAnimations().map(a => a.effect.getTiming().duration)); }))).observe(document.getElementById('ft-thread'), { childList: true }); }""")
    ari.locator("#ft-text").fill("Fade me")
    ari.locator("#ft-send").click()
    expect(mate.locator("#ft-thread .ft-msg")).to_contain_text("Fade me", timeout=9000)
    durations = mate.evaluate("window.__fade")
    assert durations and durations[0][0] == 280                                   # --motion-settle-dur: the one soft spring (F-109)
    ari.evaluate("""() => { window.__fade = []; new MutationObserver(ms => ms.forEach(m => m.addedNodes.forEach(n => { if (n.nodeType === 1) window.__fade.push(n.getAnimations().length); }))).observe(document.getElementById('ft-thread'), { childList: true }); }""")
    ari.locator("#ft-text").fill("Mine fades too")
    ari.locator("#ft-send").click()
    expect(ari.locator("#ft-thread .ft-me").last).to_contain_text("Mine fades too")
    assert ari.evaluate("window.__fade")[0] >= 1
    mate.emulate_media(reduced_motion="reduce")
    mate.evaluate("window.__fade = []")
    ari.locator("#ft-text").fill("Still")
    ari.locator("#ft-send").click()
    expect(mate.locator("#ft-thread .ft-msg").last).to_contain_text("Still", timeout=9000)
    assert all(not d for d in mate.evaluate("window.__fade"))


@pytest.mark.parametrize("viewport", [PHONE, NARROW], ids=["390", "320"])
def test_the_pending_and_failed_bubbles_fit_the_phone(pair, viewport):
    ari, _ = pair()
    ari.set_viewport_size(viewport)
    ari.route("**/trip/family/message", lambda route: route.abort())
    ari.locator("#ft-text").fill("A long message with a_very_long_unbroken_word_that_could_push_the_bubble_wider_than_the_phone_if_nothing_wrapped_it")
    ari.locator("#ft-send").click()
    expect(ari.locator("#ft-thread .ft-me")).to_contain_text("Not sent")
    assert overflow(ari) <= 0
    assert ari.locator("#ft-thread .ft-me button").bounding_box()["height"] >= 43.9
    small = ari.evaluate("""() => [...document.querySelectorAll('#ft *')].filter(e => [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim()) && parseFloat(getComputedStyle(e).fontSize) < 13).length""")
    assert small == 0
    assert ari.evaluate("""() => [...document.querySelectorAll('#ft *')].filter(e => e.type !== 'file' && getComputedStyle(e).textOverflow === 'ellipsis').map(e => e.tagName + '.' + e.className + '#' + e.id)""") == []


def test_two_messages_arriving_in_one_poll_both_show(pair):
    ari, mate = pair()
    for word in ("One", "Two", "Three"):
        ari.locator("#ft-text").fill(word)
        ari.locator("#ft-send").click()
        expect(ari.locator("#ft-thread .ft-msg .ft-bub").filter(has_text=word)).to_have_count(1)
    expect(mate.locator("#ft-thread .ft-msg")).to_have_count(3, timeout=9000)
    assert mate.locator("#ft-thread .ft-msg").all_inner_texts()[2].count("Three") == 1
