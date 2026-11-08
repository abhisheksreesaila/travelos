"""F-210 part A in a real browser at phone (390) and laptop (1440) width, sample data off: Where to? takes a typed place, and "Make this a trip" on Where to? and on /plan's
lanes makes the family's trip and lands on the cockpit."""
import re

import pytest
from playwright.sync_api import expect

from tests_browser.helpers import DESKTOP, PHONE

IDS = ["390", "1440"]


@pytest.fixture(autouse=True)
def real(monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")


def signed_in(browser, base_url, viewport):
    ctx = browser.new_context(viewport=viewport, has_touch=viewport is PHONE, is_mobile=viewport is PHONE, reduced_motion="reduce")
    ctx.set_default_timeout(9000)
    ctx.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": ""}, max_redirects=0)
    return ctx


def tap(el, viewport):
    el.tap() if viewport is PHONE else el.click()


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=IDS)
def test_where_to_takes_any_place_and_makes_it_a_trip(browser, base_url, viewport):
    ctx = signed_in(browser, base_url, viewport)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{base_url}/start")
    expect(page.locator("#st-form input[name=to]")).to_have_count(0)
    expect(page.locator("#st-form")).not_to_contain_text("Sample prices")
    box = page.locator("#st-place")
    box.fill("Lisbon")
    make = page.locator("#st-make")
    if viewport is PHONE:
        assert make.bounding_box()["height"] >= 48 and box.bounding_box()["height"] >= 40
    tap(make, viewport)
    page.wait_for_url(re.compile(r"/trip/cockpit"))
    expect(page.locator("body")).to_contain_text("Lisbon")
    assert not errors, errors
    ctx.close()


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=IDS)
def test_the_booking_lanes_make_a_trip_too(browser, base_url, viewport):
    ctx = signed_in(browser, base_url, viewport)
    page = ctx.new_page()
    page.goto(f"{base_url}/start")
    page.locator("#st-place").fill("Lake Tahoe")
    tap(page.locator("#st-form .st-go").first, viewport)
    page.wait_for_url(re.compile(r"/plan\?place=Lake"))
    make = page.locator("#ps-make button")
    expect(make).to_have_text(re.compile("Make this a trip"))
    if viewport is PHONE:
        assert make.bounding_box()["height"] >= 48
    tap(make, viewport)
    page.wait_for_url(re.compile(r"/trip/cockpit"))
    expect(page.locator("body")).to_contain_text("Lake Tahoe")
    ctx.close()
