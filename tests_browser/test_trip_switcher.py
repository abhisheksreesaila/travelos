"""F-040, F-147: a family with two trips switches between them on a phone and a tablet, where the top bar is not drawn: the trip menu in the heading of the day, the week and Today
holds the trips, Plan another trip and Import a trip you booked. It opens as a bottom sheet that fits the screen. (The laptop's picker is in tests_browser/test_topbar.py.)"""
import re

import pytest
from playwright.sync_api import expect

from tests_browser.helpers import PHONE, seed_plan

TABLET = {"width": 800, "height": 1000}
SAMPLE = {"f": "f1", "h": "h1", "c": "c1"}
THREE_NIGHTS = {**SAMPLE, "d": "2026-10-23", "r": "2026-10-26", "a": "2", "k": "4,7"}
MENU = ".ga-tb-phonepick"


@pytest.fixture
def family_with_two_trips(browser, base_url):
    contexts = []

    def make(viewport, path="/trip/canvas?day=1"):
        ctx = browser.new_context(viewport=viewport, reduced_motion="reduce")
        ctx.set_default_timeout(5000)
        contexts.append(ctx)
        ctx.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "pay"}, max_redirects=0)
        ctx.request.post(f"{base_url}/pay", form=SAMPLE, max_redirects=0)
        seed_plan(ctx.request, base_url, "a1", "1", "10:00", "11:30", "Venice Canals stroll", "outdoors")
        ctx.request.post(f"{base_url}/pay", form=THREE_NIGHTS, max_redirects=0)
        page = ctx.new_page()
        page.goto(f"{base_url}{path}")
        return page

    yield make
    for c in contexts:
        c.close()


def open_menu(page):
    page.click(f"{MENU} > summary")
    pop = page.locator(f"{MENU} .ga-tb-pop")
    expect(pop).to_be_visible()
    return pop


@pytest.mark.parametrize("viewport", [PHONE, TABLET], ids=["390", "800"])
def test_the_menu_fits_the_screen_and_switching_opens_the_other_trip(family_with_two_trips, viewport):
    page = family_with_two_trips(viewport)
    expect(page.locator(f"{MENU} > summary")).to_be_visible()
    root = page.evaluate("parseFloat(getComputedStyle(document.documentElement).fontSize)")
    assert page.locator(f"{MENU} > summary").bounding_box()["height"] >= 2.75 * root - 0.5      # 2.75rem: 44px on a phone
    expect(page.locator(".cz-gb", has_text="Venice Canals stroll")).to_have_count(0)           # the newest trip is open and has nothing planned yet
    pop = open_menu(page)
    box = pop.bounding_box()
    assert box["x"] >= 0 and box["x"] + box["width"] <= viewport["width"] and box["y"] >= 0 and box["y"] + box["height"] <= viewport["height"]
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    expect(page.locator(f'{MENU} .ga-tb-sw[aria-current="true"]')).to_have_count(1)
    page.click(f"{MENU} .ga-tb-sw:not([aria-current])")
    page.wait_for_url(re.compile(r"/trip/canvas"))
    page.goto(page.url.split("?")[0] + "?day=1")
    expect(page.locator(".cz-gb", has_text="Venice Canals stroll").first).to_be_visible()


@pytest.mark.parametrize("viewport", [PHONE, TABLET], ids=["390", "800"])
def test_plan_another_and_import_are_in_the_menu(family_with_two_trips, viewport):
    page = family_with_two_trips(viewport)
    open_menu(page)
    page.click(f'{MENU} a[href="/start"]')
    page.wait_for_url(re.compile(r"/start$"))
    page.go_back()
    open_menu(page)
    page.click(f'{MENU} a[href="/trips/import"]')
    page.wait_for_url(re.compile(r"/trips/import$"))


@pytest.mark.parametrize("path", ["/trip/canvas", "/trip?tab=today"], ids=["week", "today"])
def test_the_week_and_the_old_today_page_carry_the_menu_too(family_with_two_trips, path):
    page = family_with_two_trips(PHONE, path)
    pop = open_menu(page)
    assert pop.bounding_box()["y"] + pop.bounding_box()["height"] <= PHONE["height"]
    page.keyboard.press("Escape")
    expect(page.locator(f"{MENU} .ga-tb-pop")).to_be_hidden()


def test_the_laptop_has_the_bar_picker_and_not_this_one(family_with_two_trips):
    page = family_with_two_trips({"width": 1440, "height": 900})
    expect(page.locator(MENU)).to_be_hidden()
    expect(page.locator(".ga-topbar .ga-tb-picker summary")).to_be_visible()
