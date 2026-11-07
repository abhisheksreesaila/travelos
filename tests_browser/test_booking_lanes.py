"""F-198 in a real browser at phone (390) and laptop (1440) width: the booking lanes of the captain's Lake Tahoe trip (Dec 19 to 26 2026, from SFO, 2 adults, kids 8 and 11), in
production with no programs connected. Every lane is there, nothing scrolls sideways, the buttons are touch-sized, and each tap lands on the researched link (the partners' sites
are never reached: their addresses are caught and read). Set F198_SHOTS=1 to save screenshots to docs/report/f198-*.png."""
import os
from pathlib import Path

import pytest
from playwright.sync_api import expect

from gitaway.partners import prices
from tests.test_booking_lanes import RESEARCH
from tests_browser.helpers import DESKTOP, PHONE

SHOTS = Path(__file__).resolve().parent.parent / "docs" / "report"
TAHOE = "/plan?place=Lake+Tahoe&d=2026-12-19&r=2026-12-26&a=2&k=8,11&home=SFO"
PARTNERS = ("https://www.aviasales.com/**", "https://www.expedia.com/**", "https://www.airbnb.com/**", "https://www.vrbo.com/**", "https://www.getyourguide.com/**",
            "https://www.skiheavenly.com/**", "https://www.northstarcalifornia.com/**", "https://www.kirkwood.com/**", "https://www.palisadestahoe.com/**", "https://sierraattahoe.com/**")


@pytest.fixture(autouse=True)
def production(monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "tok")      # the Data API is asked (through the stub below); no marker, no Klook: every lane is a plain link
    for name in ("TRAVELPAYOUTS_MARKER", "TRAVELPAYOUTS_TRS", "PARTNER_STAY", "PARTNER_TRACKED"):
        monkeypatch.delenv(name, raising=False)
    prices.clear()
    monkeypatch.setattr(prices, "TRANSPORT", lambda *a: {"success": True, "data": [{"price": 187}]})
    yield
    prices.clear()


def context(browser, viewport):
    ctx = browser.new_context(viewport=viewport, has_touch=viewport is PHONE, is_mobile=viewport is PHONE, reduced_motion="reduce")
    ctx.set_default_timeout(9000)
    caught = []

    def partner(route, request):
        caught.append(request.url)
        route.fulfill(status=200, content_type="text/html", body="<html><body>the partner</body></html>")
    for pattern in PARTNERS:
        ctx.route(pattern, partner)
    return ctx, caught


def tap(el, viewport):
    el.tap() if viewport is PHONE else el.click()


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["390", "1440"])
def test_the_tahoe_lanes_fit_and_every_tap_lands_on_the_researched_link(browser, base_url, viewport):
    ctx, caught = context(browser, viewport)
    page = ctx.new_page()
    page.goto(base_url + TAHOE)
    expect(page.locator("h2.ps-name")).to_have_text(["Search flights to Lake Tahoe", "Find stays near South Lake Tahoe", "Rent a car at RNO", "Tickets and things to do",
                                                     "Lift tickets and ski school"])
    expect(page.locator("#ps-flight .ps-what")).to_contain_text("from $187 a person, checked")
    expect(page.locator("#ps-car")).to_contain_text("snow chains and a ski rack")
    expect(page.locator("#ps-direct")).to_contain_text("Buy direct · No commission")
    assert page.locator(".ps-note.is-paid").count() == 0
    for width in ((390, 320) if viewport is PHONE else (1440, 1280, 1000)):
        page.set_viewport_size({"width": width, "height": viewport["height"]})
        assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth"), f"sideways scroll at {width}"
    page.set_viewport_size(viewport)
    if viewport is PHONE:
        sizes = page.locator("a.ps-go, a.ps-also, a.ps-resort, .ps-from button, .ps-field input, .ps-field button").evaluate_all("els => els.filter(e => e.getClientRects().length && e.getBoundingClientRect().height > 2).map(e => e.getBoundingClientRect().height)")      # a date field the pickers replaced is a 1px stand-in; its picker button is measured instead
        assert min(sizes) >= 43, sizes
    if os.getenv("F198_SHOTS"):
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f"f198-tahoe-{viewport['width']}.png"), full_page=True)
    for selector, key in (("a.ps-go[data-lane=flight]", ("flight", "aviasales")), ("a.ps-go[data-lane=stay]", ("stay", "expedia")),
                          ("a.ps-also[data-site=airbnb]", ("stay", "airbnb")), ("a.ps-also[data-site=vrbo]", ("stay", "vrbo")), ("a.ps-go[data-lane=car]", ("car", "expedia")),
                          ("a.ps-go[data-lane=todo]", ("todo", "getyourguide")), ("a.ps-resort[data-site=resort-0]", ("direct", "resort-0"))):
        tap(page.locator(selector), viewport)
        page.wait_for_url(lambda url: not url.startswith(base_url))
        assert caught[-1] == RESEARCH[key], (selector, caught[-1])
        page.go_back()
        page.wait_for_url(f"{base_url}/plan?**")
    ctx.close()


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["390", "1440"])
def test_a_place_typed_in_the_form_gets_its_lanes(browser, base_url, viewport):
    ctx, _ = context(browser, viewport)
    page = ctx.new_page()
    page.goto(base_url + "/plan")
    expect(page.locator("h1")).to_have_text("Where are you going?")
    form = page.locator("#ps-trip")
    form.locator("input[name=place]").fill("Lake Tahoe")
    form.locator("input[name=d]").fill("2026-12-19")
    form.locator("input[name=r]").fill("2026-12-26")
    form.locator("input[name=k]").fill("8, 11")
    tap(form.get_by_role("button", name="Search"), viewport)
    page.wait_for_url("**/plan?place=Lake+Tahoe**")
    expect(page.locator("#ps-lede")).to_have_text("Dec 19 – 26 · 2 adults, 2 kids")
    expect(page.locator("#ps-direct")).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    ctx.close()
