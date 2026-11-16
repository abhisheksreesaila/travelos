"""F-053: a brand-new family's first-run path, in a real browser at phone and desktop width: the ways in are all visible,
nothing scrolls sideways, touch targets are big enough on a phone, and each way in lands on a working page.
M5 triage: the /forks page with the three cards is retired (F-254, D-761); the way in is /plan/ask, with the import beside the ask and Guides in the bar."""
import pytest
from playwright.sync_api import expect

from tests_browser.helpers import DESKTOP, PHONE

NEW = "browser.firstrun@example.com"


@pytest.fixture
def new_family(browser, base_url):
    contexts = []

    def make(viewport):
        ctx = browser.new_context(viewport=viewport, reduced_motion="reduce")
        ctx.set_default_timeout(5000)
        contexts.append(ctx)
        ctx.request.post(f"{base_url}/signin", form={"email": NEW, "next": "/plan/ask", "intent": "save"}, max_redirects=0)
        return ctx.new_page()

    yield make
    for c in contexts:
        c.close()


def no_sideways_scroll(page):
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth"), page.url


@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["desktop", "phone"])
def test_the_ways_in_are_visible_and_fit(new_family, base_url, viewport):
    page = new_family(viewport)
    page.goto(f"{base_url}/plan/ask")
    expect(page.locator("#v2-q")).to_be_visible()      # plan a trip: the ask
    link = page.locator("#ak-import")      # import a trip you booked
    expect(link).to_be_visible()
    box = link.bounding_box()
    assert box["x"] >= 0 and box["x"] + box["width"] <= viewport["width"]
    if viewport is PHONE:
        assert box["height"] >= 44
    no_sideways_scroll(page)


@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["desktop", "phone"])
def test_each_way_in_lands_on_a_working_page(new_family, base_url, viewport):
    page = new_family(viewport)
    page.goto(f"{base_url}/plan/ask")
    page.locator("#ak-import").click()
    page.wait_for_url("**/trips/import")
    expect(page.locator("textarea")).to_be_visible()
    no_sideways_scroll(page)
    page.locator("#ti-build").click()      # F-055: or answer a few questions
    expect(page.locator("#tb-heading")).to_have_text("Where are you going?")
    no_sideways_scroll(page)
    page.goto(f"{base_url}/guides")      # browse what other people did
    expect(page.locator("h1").first).to_be_visible()
    no_sideways_scroll(page)


def test_the_invite_form_fields_are_tall_enough_on_a_phone(new_family, base_url):
    page = new_family(PHONE)
    page.goto(f"{base_url}/family")
    for sel in ("#fam-email", "#fam-role-pick-ga"):  # the role select is dressed: its visible control is the picker button
        assert page.locator(sel).bounding_box()["height"] >= 44, sel
