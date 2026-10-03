"""F-069: the Help tab in a real browser at 390: the confirmation behind a tap, call links, a number fixed right there, the family's number
from the family page, no sideways scroll, and Help opening offline for the person who opened it before (and only for them)."""
from datetime import date

import pytest
from playwright.sync_api import expect

from gitaway import catalog, tripday
from tests.test_trip_import import TEMPLATE
from tests_browser.helpers import PHONE
from tests_browser.test_phone_polish import OVERFLOW, SMALL_CONTROLS, SMALL_TEXT


@pytest.fixture
def clock(monkeypatch):
    monkeypatch.setattr(catalog, "today", lambda *_: date(2026, 10, 17))
    monkeypatch.setattr(tripday, "now_minute", lambda *_: 16 * 60)


@pytest.fixture
def phone_page(browser, base_url, clock):
    contexts = []

    def make(who="ari.rivera@example.com", workers="block"):
        ctx = browser.new_context(viewport=PHONE, reduced_motion="reduce", has_touch=True, is_mobile=True, service_workers=workers)
        ctx.set_default_timeout(6000)
        contexts.append(ctx)
        ctx.request.post(f"{base_url}/signin", form={"email": who, "next": "/", "intent": "save"}, max_redirects=0)
        return ctx

    yield make
    for c in contexts:
        c.set_offline(False)
        c.close()


def trip_in(ctx, base_url):
    ctx.request.post(f"{base_url}/trips/import/save", form={"text": TEMPLATE}, max_redirects=0)


def test_help_at_390_confirmation_tap_call_links_and_no_sideways_scroll(phone_page, base_url):
    ctx = phone_page()
    trip_in(ctx, base_url)
    page = ctx.new_page()
    page.goto(base_url + "/trip/help")
    expect(page.locator("#hp-hotel")).to_contain_text("The Example Hotel Santa Monica")
    expect(page.locator("#hp-hotel")).to_contain_text("123 Ocean Ave")
    expect(page.locator("#hp-in")).to_contain_text("3:00 PM")
    expect(page.locator("#hp-out")).to_contain_text("11:00 AM")
    assert page.locator("#hp-hotel a[href='tel:+13105550100']").count() == 1
    assert page.locator("#hp-car a[href='tel:+13105550199']").count() == 1
    assert page.get_attribute("#hp-911", "href") == "tel:911"
    assert "maps" in page.get_attribute("#hp-directions", "href")
    number = page.locator("#hp-hotel .tp-conf-num")
    expect(number).to_be_hidden()  # behind a tap
    page.locator("#hp-hotel .hp-conf-sum").click()
    expect(number).to_be_visible()
    expect(number).to_have_text("987654321")
    assert page.evaluate(OVERFLOW) == 0
    assert page.evaluate(SMALL_TEXT) == []
    assert page.evaluate(SMALL_CONTROLS) == []
    page.set_viewport_size({"width": 320, "height": 640})
    assert page.evaluate(OVERFLOW) == 0
    # the Help tab of the bar is the current one
    expect(page.locator("#ph-tab-help")).to_have_attribute("aria-current", "page")


def test_fixing_a_number_right_there_and_the_family_number_from_the_family_page(phone_page, base_url):
    ctx = phone_page()
    trip_in(ctx, base_url)
    page = ctx.new_page()
    page.goto(base_url + "/trip/help")
    page.locator("[data-fix='hotel0'] summary").click()
    field = page.locator("[data-fix='hotel0'] input[name=phone]")
    field.fill("+1 310 555 0177")
    page.get_by_role("button", name="Save the number").click()
    page.wait_for_url("**/trip/help")
    assert page.locator("#hp-hotel a[href='tel:+13105550177']").count() == 1
    page.locator("[data-fix='hotel0'] summary").click()
    page.locator("[data-fix='hotel0'] input[name=phone]").fill("nope")
    page.get_by_role("button", name="Save the number").click()
    expect(page.locator("#hp-problem")).to_contain_text("did not look right")
    page.locator("[data-fix='hotel0'] summary").click()
    page.get_by_role("link", name="Cancel").click()  # Cancel goes back to Help
    page.wait_for_url("**/trip/help")
    # my own number: Help offers it, the family page takes it, Help then lists it
    page.goto(base_url + "/trip/help")
    page.locator("#hp-add-mine").click()
    page.wait_for_url("**/family**")
    page.fill("#fam-phone", "+1 415 555 0142")
    page.get_by_role("button", name="Save my number").click()
    page.wait_for_url("**/family#my-phone")
    page.goto(base_url + "/trip/help")
    assert page.locator("#hp-contacts a[href='tel:+14155550142']").count() == 1
    assert page.locator("#hp-add-mine").count() == 0
    assert page.evaluate(OVERFLOW) == 0


def test_help_opens_offline_for_the_person_who_opened_it_and_not_for_somebody_else(phone_page, base_url):
    ari = phone_page(workers="allow")
    trip_in(ari, base_url)
    page = ari.new_page()
    page.goto(base_url + "/trip/help")
    page.evaluate("navigator.serviceWorker.ready.then(() => true)")
    page.reload()
    page.wait_for_function("navigator.serviceWorker.controller !== null")
    page.goto(base_url + "/trip/help")  # visited with the worker in charge: saved
    online = page.locator("#hp-hotel").inner_text()
    ari.set_offline(True)
    page.goto(base_url + "/trip/help")
    assert page.locator("#hp-hotel").inner_text() == online
    expect(page.locator("#hp-911")).to_have_attribute("href", "tel:911")
    assert page.locator("#hp-hotel a[href='tel:+13105550100']").count() == 1
    ari.set_offline(False)
    sam = phone_page("sam.lee@example.com", workers="allow")
    page2 = sam.new_page()
    page2.goto(base_url + "/community")
    page2.evaluate("navigator.serviceWorker.ready.then(() => true)")
    page2.reload()
    page2.wait_for_function("navigator.serviceWorker.controller !== null")
    sam.set_offline(True)
    page2.goto(base_url + "/trip/help")  # Sam never opened Help: the offline page, never Ari's hotel
    body = page2.locator("body").inner_text()
    assert "Example Hotel" not in body and "offline" in body.lower()
