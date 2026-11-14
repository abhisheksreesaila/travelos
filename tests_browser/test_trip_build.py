"""F-055: the guided trip builder in a real (headless) browser at phone width: walk every question, preview, save, see it on its days.
Waits are on selectors and state, never on sleeps."""
import re
from datetime import datetime, timedelta, timezone

import pytest
from playwright.sync_api import expect

from gitaway import catalog
from tests_browser.helpers import PHONE


def day_label(d):
    """How the date picker names a day for a screen reader: "Friday, October 16"."""
    return f"{d:%A}, {d:%B} {d.day}"


@pytest.fixture
def phone(browser, base_url):
    ctx = browser.new_context(viewport=PHONE, reduced_motion="reduce")
    ctx.set_default_timeout(5000)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.errors = errors
    ctx.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "save"}, max_redirects=0)
    yield page
    ctx.close()


def setv(page, selector, value):
    """Set a field the themed picker has dressed (the real control is clipped behind it) and tell the page, as a pick would."""
    page.eval_on_selector(selector, "(el, v) => { el.value = v; el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); }", value)


def fill_all(page, values):
    for name, value in values.items():
        setv(page, f'[name="{name}"]', value)


def no_sideways_scroll(page):
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")


def big_enough(page):
    """Every button and link the person presses is at least 44px tall at phone width."""
    small = page.evaluate("""() => [...document.querySelectorAll('#tb-form button, #tb-form a, #tb-form input[type=radio] + span')]
        .filter(e => e.offsetParent !== null && !e.classList.contains('tb-default'))
        .filter(e => e.getBoundingClientRect().height < 43.5).map(e => e.textContent.trim())""")
    assert not small, small


def next_step(page, title):
    page.click("#tb-next")
    expect(page.locator("#tb-heading")).to_have_text(title)
    no_sideways_scroll(page)
    big_enough(page)


def test_walk_the_whole_builder_at_390_and_see_the_trip_on_its_days(phone, base_url):
    page = phone
    # The trip's dates are relative to the app's "today" (conftest pins catalog.today), and the browser's clock is set to that same day, so the picker opens on the month the trip is in
    # whatever the real date is. Sixteen days ahead and a four-night stay, as the test always did.
    leave = catalog.today() + timedelta(days=16)
    home = leave + timedelta(days=4)
    page.clock.set_fixed_time(datetime.combine(catalog.today(), datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=12))
    page.goto(f"{base_url}/trips/build")
    expect(page.locator("#tb-count")).to_have_text("Step 1 of 7")
    expect(page.get_by_label("Trip name")).to_be_visible()
    big_enough(page)
    # step 1: a mistake first, with its message on the field
    page.click("#tb-next")
    expect(page.locator("#tb-err-title")).to_have_text("The trip name is needed.")
    expect(page.locator("input#tb-title")).to_have_attribute("aria-invalid", "true")
    page.get_by_label("Trip name").fill("LA with the kids")
    page.get_by_label("Where to?").fill("Los Angeles")
    next_step(page, "When are you going?")
    # step 2: the range picker
    page.get_by_role("button", name=re.compile("^Leaving:")).click()
    for _ in range(3):      # the picker opens on the month of "today"; the trip may be in the next one
        if page.get_by_role("dialog").get_by_role("button", name=re.compile("^" + day_label(leave))).count():
            break
        page.get_by_role("dialog").get_by_role("button", name="Next month").click()
    page.get_by_role("dialog").get_by_role("button", name=re.compile("^" + day_label(leave))).click()
    page.get_by_role("dialog").get_by_role("button", name=re.compile("^" + day_label(home))).click()
    page.get_by_role("button", name="Done").click()
    assert page.input_value("#tb-start") == leave.isoformat() and page.input_value("#tb-end") == home.isoformat()
    next_step(page, "Who’s going?")
    # step 3: the steppers show only the rows that apply
    expect(page.locator('[data-row="k1"]')).to_be_hidden()
    page.get_by_role("button", name="More kids").click()
    page.get_by_role("button", name="More kids").click()
    expect(page.locator('[data-row="k2"]')).to_be_visible()
    expect(page.locator('[data-row="k3"]')).to_be_hidden()
    fill_all(page, {"k1": "7", "k2": "4", "an1": "Abhi", "ae1": "you@gmail.com", "an2": "Priya"})
    next_step(page, "How are you getting there?")
    # step 4: dates are already the trip's; "I'm not flying" hides the legs
    assert page.input_value('[name="leg0_depart_date"]') == leave.isoformat() and page.input_value('[name="leg1_depart_date"]') == home.isoformat()
    page.locator("#tb-flying-no").check()
    expect(page.locator('[data-when="flying"]')).to_be_hidden()
    page.locator("#tb-flying-yes").check()
    expect(page.locator('[data-when="flying"]')).to_be_visible()
    fill_all(page, {"leg0_airline": "Alaska Airlines", "leg0_number": "AS 1234", "leg0_from": "SFO", "leg0_to": "LAX", "leg0_depart_time": "08:05", "leg0_arrive_time": "09:32", "leg0_confirmation": "ABCDEF",
                    "leg1_airline": "Alaska Airlines", "leg1_number": "AS 1235", "leg1_from": "LAX", "leg1_to": "SFO", "leg1_depart_time": "14:10", "leg1_arrive_time": "15:37", "leg1_confirmation": "ABCDEF"})
    next_step(page, "Where are you staying?")
    # step 5: check-in and check-out come from the dates; go back and forward to see the answers stay
    assert page.input_value('[name="hotel0_check_in_date"]') == leave.isoformat() and page.input_value('[name="hotel0_check_out_date"]') == home.isoformat()
    fill_all(page, {"hotel0_name": "The Example Hotel Santa Monica", "hotel0_address": "123 Ocean Ave, Santa Monica, CA 90401", "hotel0_confirmation": "987654321"})
    page.click("#tb-back")
    expect(page.locator("#tb-heading")).to_have_text("How are you getting there?")
    assert page.input_value('[name="leg0_number"]') == "AS 1234"
    next_step(page, "Where are you staying?")
    assert page.input_value('[name="hotel0_name"]') == "The Example Hotel Santa Monica"
    next_step(page, "Do you have a rental car?")
    # step 6: no car
    expect(page.locator('[data-when="rent"]')).to_be_hidden()
    next_step(page, "Anything else to remember?")
    fill_all(page, {"booked_on": "Expedia"})
    page.click("#tb-next")
    # the importer's own preview
    expect(page.locator("h1")).to_have_text("Check your trip")
    expect(page.locator("#ti-preview-body")).to_contain_text("Alaska Airlines AS 1234 · SFO → LAX")
    expect(page.locator("#ti-hotel")).to_contain_text("123 Ocean Ave, Santa Monica")
    expect(page.locator("#ti-travelers")).to_contain_text("age 7")
    no_sideways_scroll(page)
    page.click("#ti-save")
    page.wait_for_url("**/trip/cockpit*")      # the trip's home (F-201)
    expect(page.locator("#ck-week")).to_be_visible()
    assert not page.errors


def test_the_first_run_welcome_offers_the_builder_and_the_template(phone, base_url):
    phone.goto(f"{base_url}/forks")
    welcome = phone.locator(".fr-path-multi")
    expect(welcome.get_by_role("link", name="Answer a few questions")).to_have_attribute("href", "/trips/build")
    expect(welcome.get_by_role("link", name="Paste the template")).to_have_attribute("href", "/trips/import")
    no_sideways_scroll(phone)
