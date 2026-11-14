"""F-210 part A in a real browser at phone (390) and laptop (1440) width, sample data off: the booking lanes (/plan) take a typed place, and "Make this a trip" there makes
the family's trip and lands on the cockpit. (Where to? was the other form until F-231; the matrix's Save is tests_browser/test_tripmatrix.py.)"""
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
def test_a_place_in_the_booking_lanes_makes_a_trip(browser, base_url, viewport):
    ctx = signed_in(browser, base_url, viewport)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{base_url}/plan?place=Lisbon&d=2027-03-05&r=2027-03-09&a=2")
    make = page.locator("#ps-make button")
    expect(make).to_have_text(re.compile("Make this a trip"))
    if viewport is PHONE:
        assert make.bounding_box()["height"] >= 48
    tap(make, viewport)
    page.wait_for_url(re.compile(r"/trip/cockpit"))
    expect(page.locator("body")).to_contain_text("Lisbon")
    assert not errors, errors
    ctx.close()


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=IDS)
def test_the_booking_lanes_form_takes_any_place_and_makes_it_a_trip_too(browser, base_url, viewport):
    ctx = signed_in(browser, base_url, viewport)
    page = ctx.new_page()
    page.goto(f"{base_url}/plan")
    page.locator("#ps-trip input[name=place]").fill("Lake Tahoe")
    tap(page.locator("#ps-trip button[type=submit]"), viewport)
    page.wait_for_url(re.compile(r"/plan\?place=Lake"))
    make = page.locator("#ps-make button")
    expect(make).to_have_text(re.compile("Make this a trip"))
    if viewport is PHONE:
        assert make.bounding_box()["height"] >= 48
    tap(make, viewport)
    page.wait_for_url(re.compile(r"/trip/cockpit"))
    expect(page.locator("body")).to_contain_text("Lake Tahoe")
    ctx.close()
