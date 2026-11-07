"""F-197 the offer and an example plan in a real browser, at phone (390) and laptop (1440) width: no sideways scroll, every tap target at least 48px on the phone (40px on the laptop),
the one button always in reach on the phone, the FAQ opens, and an example opens from the offer and leads to the intake with its place filled in. With PLAN_FOR_ME_REVIEW on, as it will be live.
Set F197_SHOTS=1 to save screenshots to docs/report/f197-*.png."""
import os
from pathlib import Path

import pytest
from playwright.sync_api import expect

from tests_browser.helpers import DESKTOP, PHONE
from tests_browser.test_plan_for_me import overflow, too_small

SHOTS = Path(__file__).resolve().parent.parent / "docs" / "report"
IDS = ["390", "1440"]
TARGETS = "#pf a, #pf button, #pf summary, #pf .btn"


def shot(page, name, full=True):
    if os.getenv("F197_SHOTS"):
        page.wait_for_timeout(500)
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f"f197-{name}.png"), full_page=full)


@pytest.fixture
def visitor(browser, monkeypatch):
    monkeypatch.setenv("PLAN_FOR_ME_REVIEW", "1")
    contexts = []

    def make(viewport):
        ctx = browser.new_context(viewport=viewport, has_touch=viewport is PHONE, is_mobile=viewport is PHONE, device_scale_factor=2 if viewport is PHONE else 1)
        ctx.set_default_timeout(20000)
        contexts.append(ctx)
        return ctx.new_page()

    yield make
    for c in contexts:
        c.close()


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=IDS)
def test_the_offer_fits_every_tap_is_big_enough_and_the_one_button_is_always_in_reach(visitor, base_url, viewport):
    w = viewport["width"]
    page = visitor(viewport)
    page.goto(f"{base_url}/plan-for-me")
    expect(page.locator("h1")).to_contain_text("A calm Disneyland trip with your kids")
    expect(page.locator("#pf-terms")).to_have_text("$29 for the first 10 families, then $49")
    expect(page.locator("#pf-spots")).to_have_text("10 of 10 founding spots left")
    expect(page.locator("#pf-promise")).to_contain_text("Not useful? Reply within 7 days for a full refund.")
    assert page.locator(".btn-primary").count() == 1
    assert overflow(page) <= 1
    assert not too_small(page, TARGETS), too_small(page, TARGETS)
    shot(page, f"offer-top-{w}", full=False)
    cta = page.locator("#pf-cta")
    expect(cta).to_be_in_viewport()
    page.locator("#pf-faq").scroll_into_view_if_needed()
    expect(cta).to_be_in_viewport()          # on the phone it stays at the bottom of the screen; on the laptop the price column stays in view
    page.locator(".pf-q summary").first.click()
    expect(page.locator(".pf-q").first.locator("p")).to_be_visible()
    assert overflow(page) <= 1
    shot(page, f"offer-{w}")
    cta.click()
    expect(page).to_have_url(f"{base_url}/plan-for-me/start")
    expect(page.locator("#pf-form")).to_be_visible()


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=IDS)
def test_an_example_opens_from_the_offer_reads_like_a_trip_and_leads_to_the_intake(visitor, base_url, viewport):
    w = viewport["width"]
    page = visitor(viewport)
    page.goto(f"{base_url}/plan-for-me")
    page.locator("#pf-ex-disneyland").click()
    expect(page).to_have_url(f"{base_url}/plan-for-me/example/disneyland")
    expect(page.locator("h1")).to_have_text("Disneyland with a 3- and a 7-year-old")
    expect(page.locator(".pv-day")).to_have_count(3)
    expect(page.locator("#pv-book")).to_contain_text("Dining reservations")
    expect(page.locator("#pv-party")).to_contain_text("kids 3 (38 in) and 7 (48 in)")
    assert overflow(page) <= 1
    assert not too_small(page, TARGETS), too_small(page, TARGETS)
    tint = page.locator(".pv-stop[data-kind=food]").first.evaluate("e => getComputedStyle(e).backgroundColor")
    fun = page.locator(".pv-stop[data-kind=fun]").first.evaluate("e => getComputedStyle(e).backgroundColor")
    assert tint != fun and "rgba(0, 0, 0, 0)" not in (tint, fun)          # each kind wears its own colour, like the delivered trip
    shot(page, f"example-disneyland-top-{w}", full=False)
    shot(page, f"example-disneyland-{w}")
    page.locator("#pf-cta").click()
    expect(page.locator("#pf-where")).to_have_value("Disneyland, California")


@pytest.mark.parametrize("slug", ["new-york-city", "oahu"])
def test_the_other_examples_fit_the_phone(visitor, base_url, slug):
    page = visitor(PHONE)
    page.goto(f"{base_url}/plan-for-me/example/{slug}")
    expect(page.locator("#pv-book")).to_be_visible()
    assert overflow(page) <= 1
    assert not too_small(page, TARGETS), too_small(page, TARGETS)
    shot(page, f"example-{slug}-390")
