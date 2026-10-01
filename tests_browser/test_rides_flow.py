"""F-038: schedule an Uber in a real (headless) browser: workspace card -> choose -> confirm -> ride -> step the simulation -> cancel,
then the ride on the calendar. Waits are on selectors and state, never on sleeps."""
import pytest
from playwright.sync_api import expect

from tests_browser.helpers import DESKTOP, PHONE

PICKS = "f=f1&h=h1&c=none"


@pytest.fixture
def signed_in(browser, base_url):
    """signed_in(viewport) -> a page signed in as the first demo traveler. Contexts are closed after the test."""
    contexts = []

    def make(viewport):
        ctx = browser.new_context(viewport=viewport, reduced_motion="reduce")
        ctx.set_default_timeout(5000)
        contexts.append(ctx)
        page = ctx.new_page()
        ctx.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "ride"}, max_redirects=0)
        page.goto(f"{base_url}/plan?{PICKS}")
        page.wait_for_selector("#ws-rides-card")
        return page

    yield make
    for c in contexts:
        c.close()


def no_sideways_scroll(page):
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")


def schedule_arrival(page, product="x"):
    page.click('[data-schedule="arrive"]')
    expect(page.locator("#rd-sim")).to_be_visible()
    page.click(f'[data-choose="{product}"]')
    page.fill("[name=first]", "Ari")
    page.fill("[name=last]", "Rivera")
    page.fill("[name=phone]", "(310) 555-0123")
    page.click("#rd-go")
    expect(page.locator("#rd-status")).to_have_attribute("data-status", "scheduled")


@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["desktop", "phone"])
def test_schedule_step_and_cancel(signed_in, viewport):
    page = signed_in(viewport)
    schedule_arrival(page)
    expect(page.locator("#rd-sim")).to_contain_text("Simulated: no real ride is booked")
    no_sideways_scroll(page)
    seen = []
    for expected in ("accepted", "arriving", "in_progress"):
        page.click("#rd-step")
        expect(page.locator("#rd-status")).to_have_attribute("data-status", expected)
        seen.append(expected)
        expect(page.locator("#rd-cancel")).to_have_count(1 if expected == "accepted" else 0)  # free until the driver arrives
    assert seen == ["accepted", "arriving", "in_progress"]
    page.click("#rd-step")
    expect(page.locator("#rd-status")).to_have_text("Completed")
    expect(page.locator("#rd-step")).to_have_count(0)


@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["desktop", "phone"])
def test_cancel_a_scheduled_ride(signed_in, viewport):
    page = signed_in(viewport)
    schedule_arrival(page, "c")
    page.click("#rd-step")
    expect(page.locator("#rd-status")).to_have_attribute("data-status", "accepted")
    page.click("#rd-cancel")
    expect(page.locator("#rd-status")).to_have_attribute("data-status", "rider_canceled")
    expect(page.locator("#rd-status")).to_have_text("Cancelled")
    expect(page.locator("#rd-step")).to_have_count(0)
    no_sideways_scroll(page)


def test_a_bad_phone_keeps_what_was_typed_and_says_why(signed_in):
    page = signed_in(DESKTOP)
    page.click('[data-schedule="depart"]')
    page.click('[data-choose="x"]')
    page.fill("[name=first]", "Ari")
    page.fill("[name=last]", "Rivera")
    page.fill("[name=phone]", "12345")
    page.click("#rd-go")
    expect(page.locator("#rd-error")).to_contain_text("phone")
    expect(page.locator("[name=first]")).to_have_value("Ari")
    expect(page.locator("[name=phone]")).to_have_value("12345")


@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["desktop", "phone"])
def test_a_scheduled_ride_shows_on_the_booked_trip_and_its_calendar(signed_in, viewport):
    page = signed_in(viewport)
    schedule_arrival(page)
    page.goto(page.url.split("/rides")[0] + "/plan/pay?" + PICKS)
    page.click("#pay-go")
    expect(page.locator("#pay-ride-box")).to_contain_text("UberX · LAX → The Tidewater")
    page.click("#pay-cal")
    page.wait_for_selector(".cal-whole")
    expect(page.locator(".cal-w-ride", has_text="Uber · UberX · LAX → The Tidewater")).to_be_visible()
    page.click("text=Day by day")
    page.wait_for_selector("#cal-scroll")
    block = page.locator('.cal-ride[data-block="r1"]')
    expect(block).to_have_attribute("data-start", str(9 * 60 + 32 + 30))
    no_sideways_scroll(page)
    block.click()  # the block opens the ride
    expect(page.locator("#rd-status")).to_have_attribute("data-status", "scheduled")
    assert page.url.endswith("/rides/r1")


def test_a_departure_ride_is_drawn_over_check_out_at_a_readable_width(signed_in):
    page = signed_in(DESKTOP)
    page.click('[data-schedule="depart"]')
    page.click('[data-choose="x"]')
    page.fill("[name=first]", "Ari")
    page.fill("[name=last]", "Rivera")
    page.fill("[name=phone]", "(310) 555-0123")
    page.click("#rd-go")
    expect(page.locator("#rd-status")).to_have_attribute("data-status", "scheduled")
    page.goto(page.url.split("/rides")[0] + "/plan/pay?" + PICKS)
    page.click("#pay-go")
    page.click("#pay-cal")
    page.click("text=Day by day")
    page.wait_for_selector("#cal-scroll")
    ride = page.locator('.cal-ride[data-block="r1"]')
    checkout = page.locator('.cal-booked[data-block="b-out2"]')
    rb, cb = ride.bounding_box(), checkout.bounding_box()
    assert rb["width"] >= 120
    assert rb["width"] >= cb["width"] - 8  # full width, not a sliver beside check out
    assert rb["y"] < cb["y"] + cb["height"] and cb["y"] < rb["y"] + rb["height"]  # it does overlap check out in time
    assert ride.get_attribute("aria-label").startswith("Simulated ride: Uber · UberX · The Tidewater → LAX")
    ride.hover()
    expect(ride).to_contain_text("The Tidewater → LAX")
