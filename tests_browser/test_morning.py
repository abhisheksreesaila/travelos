"""F-066: the Morning plan card in a real browser, with the push API stubbed (a headless browser cannot get a real push subscription):
the iPhone browser tab is told to add GitAway to the Home Screen, the switch asks for permission once, subscribes with the server's public
key and posts the subscription, the time follows the picker, and turning it off unsubscribes and deletes it. Also the service worker's push
and click handlers, run against a fake `self`."""
import json

import pytest
from playwright.sync_api import expect

from gitaway import morning
from scripts import vapid_keys
from tests_browser.helpers import PHONE

IPHONE_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
PAIR = vapid_keys.make_pair()

# What a phone's push API does, in a few lines: permission starts as `perm`, subscribe() hands back a subscription once, and everything
# that was asked is written to window.__push so the test can look.
STUB = """(perm) => {
  window.__push = { asked: 0, subscribed: 0, unsubscribed: 0, key: null, sub: null };
  let state = perm;
  const make = () => ({ endpoint: "https://push.example.com/send/stub1", toJSON() { return { endpoint: this.endpoint, keys: { p256dh: "BStubP256dhKey", auth: "StubAuthSecret" } }; },
                        unsubscribe: async () => { window.__push.unsubscribed++; window.__push.sub = null; sessionStorage.removeItem("stub"); return true; } });
  window.Notification = { get permission() { return state; }, requestPermission: async () => { window.__push.asked++; state = %(answer)s; return state; } };
  window.PushManager = function PushManager() {};
  const mgr = {
    getSubscription: async () => { if (!window.__push.sub && sessionStorage.getItem("stub")) window.__push.sub = make(); return window.__push.sub; },  // survives a reload, like the phone's
    subscribe: async (opts) => { window.__push.subscribed++; window.__push.key = Array.from(opts.applicationServerKey); window.__push.sub = make(); sessionStorage.setItem("stub", "1"); return window.__push.sub; },
  };
  Object.defineProperty(ServiceWorkerRegistration.prototype, "pushManager", { get() { return mgr; } });
}"""


@pytest.fixture(autouse=True)
def keys(monkeypatch):
    monkeypatch.setenv("GITAWAY_VAPID_PUBLIC", PAIR["public"]), monkeypatch.setenv("GITAWAY_VAPID_PRIVATE", PAIR["private"]), monkeypatch.setenv("GITAWAY_VAPID_SUBJECT", "mailto:a@b.co")


@pytest.fixture
def phone(browser, base_url):
    """phone(perm=None, answer="granted", **context) -> a signed-in page on /trip with the sample trip booked. With `perm` the push API is stubbed."""
    contexts = []

    def make(perm=None, answer="granted", **ctx_args):
        ctx = browser.new_context(viewport=PHONE, reduced_motion="reduce", has_touch=True, is_mobile=True, **ctx_args)
        ctx.set_default_timeout(5000)
        contexts.append(ctx)
        ctx.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "save"}, max_redirects=0)
        ctx.request.post(f"{base_url}/pay", form={"f": "f1", "h": "h1", "c": "c1"}, max_redirects=0)
        page = ctx.new_page()
        if perm:
            page.add_init_script(script=f"({STUB % {'answer': json.dumps(answer)}})({json.dumps(perm)})")
        page.goto(f"{base_url}/trip")
        return page

    yield make
    for c in contexts:
        c.close()


def state(page):
    return page.locator("#tp-morning").get_attribute("data-state")


def stored(page):
    return page.evaluate("fetch('/trip/morning/status', {method: 'POST', body: new URLSearchParams({endpoint: 'https://push.example.com/send/stub1'})}).then(r => r.json())")


def test_an_iphone_browser_tab_is_told_to_add_gitaway_to_the_home_screen(phone):
    page = phone(user_agent=IPHONE_UA)
    expect(page.locator("#tp-morning-install")).to_contain_text("Add GitAway to your Home Screen to get a morning plan")
    expect(page.locator("#tp-morning-switch")).to_be_hidden()
    expect(page.locator("#tp-morning-timerow")).to_be_hidden()
    assert state(page) == "install"


def test_the_switch_asks_once_subscribes_with_the_servers_key_and_saves_the_default_time(phone):
    page = phone("default")
    expect(page.locator("#tp-morning-install")).to_be_hidden()
    switch = page.locator("#tp-morning-switch")
    expect(switch).to_be_visible()
    assert switch.get_attribute("aria-checked") == "false" and state(page) == "off"
    expect(page.locator("#tp-morning-timerow")).to_be_hidden()
    switch.click()
    expect(page.locator("#tp-morning-timerow")).to_be_visible()
    assert switch.get_attribute("aria-checked") == "true" and state(page) == "on"
    push = page.evaluate("window.__push")
    assert push["asked"] == 1 and push["subscribed"] == 1 and len(push["key"]) == 65 and push["key"][0] == 4  # an uncompressed P-256 point: the public key
    assert stored(page) == {"on": True, "time": "07:30"}
    expect(page.locator("#tp-morning-timerow .ga-pick-btn")).to_contain_text("7:30 AM")
    assert morning.count_all() == 1


def test_the_time_picker_changes_the_time_the_server_keeps(phone):
    page = phone("default")
    page.locator("#tp-morning-switch").click()
    expect(page.locator("#tp-morning-timerow")).to_be_visible()
    page.locator("#tp-morning-timerow .ga-pick-btn").click()
    page.get_by_role("option", name="6:45 AM").click()
    expect(page.locator("#tp-morning-timerow .ga-pick-btn")).to_contain_text("6:45 AM")
    page.wait_for_function("fetch('/trip/morning/status', {method: 'POST', body: new URLSearchParams({endpoint: 'https://push.example.com/send/stub1'})}).then(r => r.json()).then(j => j.time === '06:45')")
    assert stored(page) == {"on": True, "time": "06:45"}


def test_turning_it_off_unsubscribes_and_deletes_it_and_turning_it_on_again_does_not_ask_again(phone):
    page = phone("default")
    switch = page.locator("#tp-morning-switch")
    switch.click()
    expect(page.locator("#tp-morning-timerow")).to_be_visible()
    switch.click()
    expect(page.locator("#tp-morning-timerow")).to_be_hidden()
    assert state(page) == "off" and switch.get_attribute("aria-checked") == "false"
    assert page.evaluate("window.__push.unsubscribed") == 1 and morning.count_all() == 0
    switch.click()
    expect(page.locator("#tp-morning-timerow")).to_be_visible()
    assert page.evaluate("window.__push.asked") == 1 and morning.count_all() == 1  # permission is asked once; a second subscription is made


def test_a_returning_visit_shows_it_on_at_the_saved_time(phone):
    page = phone("granted")
    page.locator("#tp-morning-switch").click()
    page.locator("#tp-morning-timerow .ga-pick-btn").click()
    page.get_by_role("option", name="8:00 AM").click()
    expect(page.locator("#tp-morning-timerow .ga-pick-btn")).to_contain_text("8:00 AM")
    page.wait_for_function("fetch('/trip/morning/status', {method: 'POST', body: new URLSearchParams({endpoint: 'https://push.example.com/send/stub1'})}).then(r => r.json()).then(j => j.time === '08:00')")
    page.reload()
    expect(page.locator("#tp-morning-timerow")).to_be_visible()   # the phone still has its subscription, and the server its time
    assert state(page) == "on" and page.locator("#tp-morning-switch").get_attribute("aria-checked") == "true"
    expect(page.locator("#tp-morning-timerow .ga-pick-btn")).to_contain_text("8:00 AM")
    expect(page.locator("#tp-morning-sub")).to_contain_text("8:00 AM")


def test_saying_no_to_notifications_says_where_to_turn_them_on(phone):
    page = phone("default", answer="denied")
    page.locator("#tp-morning-switch").click()
    expect(page.locator("#tp-morning-blocked")).to_contain_text("Settings")
    assert state(page) == "blocked" and morning.count_all() == 0 and page.evaluate("window.__push.subscribed") == 0


def test_the_card_fits_a_narrow_phone_without_sideways_scroll(phone):
    page = phone("default")
    page.locator("#tp-morning-switch").click()
    expect(page.locator("#tp-morning-timerow")).to_be_visible()
    page.set_viewport_size({"width": 320, "height": 640})
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    box = page.locator("#tp-morning-switch").bounding_box()
    assert box["height"] >= 44 and box["width"] >= 44


# ---- the service worker's push handlers -------------------------------------------------------------------------------------

RUN_SW = """async (source) => {
  const handlers = {}, shown = [], opened = [], closed = [];
  const clientsList = window.__clients || [];
  const self_ = { location: { origin: location.origin }, addEventListener: (t, f) => { handlers[t] = f; }, skipWaiting() {}, registration: { showNotification: async (title, options) => { shown.push({ title, options }); } },
                  clients: { matchAll: async () => clientsList, openWindow: async (u) => { opened.push(u); }, claim() {} } };
  new Function("self", "caches", "fetch", source)(self_, {}, () => {});
  const wait = [];
  const event = (extra) => Object.assign({ waitUntil: (p) => wait.push(p) }, extra);
  await handlers.push(event({ data: { json: () => ({ title: "Today in Los Angeles", body: "9:00 AM Beach", url: "/trip" }) } }));
  await Promise.all(wait.splice(0));
  await handlers.push(event({ data: { json: () => { throw new Error("not json"); } } }));
  await Promise.all(wait.splice(0));
  await handlers.push(event({ data: { json: () => ({ title: "x", url: "https://evil.example.com/steal" }) } }));
  await Promise.all(wait.splice(0));
  const note = { close: () => closed.push(1), data: shown[0].options.data };
  await handlers.notificationclick(event({ notification: note }));
  await Promise.all(wait.splice(0));
  const focused = [];
  window.__clients = [{ url: location.origin + "/calendar", focus: async () => focused.push("focus"), navigate: async (u) => focused.push(u) }];
  self_.clients.matchAll = async () => window.__clients;
  await handlers.notificationclick(event({ notification: note }));
  await Promise.all(wait.splice(0));
  return { shown, opened, closed: closed.length, focused };
}"""


def test_the_service_worker_shows_the_push_and_a_tap_opens_the_today_view(browser, base_url):
    page = browser.new_page()
    try:
        page.goto(f"{base_url}/offline")
        source = page.evaluate("fetch('/sw.js').then(r => r.text())")
        out = page.evaluate(RUN_SW, source)
    finally:
        page.close()
    first, second, third = out["shown"]
    assert first["title"] == "Today in Los Angeles" and first["options"]["body"] == "9:00 AM Beach" and first["options"]["data"]["url"] == "/trip"
    assert first["options"]["icon"] == "/assets/icons/icon-192.png" and first["options"]["tag"] == "morning-plan"
    assert second["title"] == "GitAway"                       # a payload that is not JSON still shows something (iOS needs every push shown)
    assert third["options"]["data"]["url"] == "/trip"          # a link to another site is never followed
    assert out["opened"] == [base_url + "/trip"]               # no window open: open one on the Today view
    assert out["closed"] == 2 and out["focused"] == ["focus", base_url + "/trip"]   # a window is open: focus it and take it to Today
