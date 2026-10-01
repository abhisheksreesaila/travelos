"""F-053: a brand-new family's first-run path, in a real browser at phone and desktop width: the three ways in are all visible,
nothing scrolls sideways, touch targets are big enough on a phone, and each way in lands on a working page."""
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
        ctx.request.post(f"{base_url}/signin", form={"email": NEW, "next": "/start", "intent": "save"}, max_redirects=0)
        return ctx.new_page()

    yield make
    for c in contexts:
        c.close()


def no_sideways_scroll(page):
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth"), page.url


@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["desktop", "phone"])
@pytest.mark.parametrize("path", ["/start", "/calendar", "/forks"])
def test_the_three_ways_in_are_visible_and_fit(new_family, base_url, viewport, path):
    page = new_family(viewport)
    page.goto(f"{base_url}{path}")
    for label in ("Plan a trip", "Import a trip you booked", "Browse community trips"):
        link = page.locator(".fr-path", has_text=label).first
        expect(link).to_be_visible()
        box = link.bounding_box()
        assert box["x"] >= 0 and box["x"] + box["width"] <= viewport["width"], (path, label)
        if viewport is PHONE:
            assert box["height"] >= 44, (path, label)
    no_sideways_scroll(page)


@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["desktop", "phone"])
def test_each_way_in_lands_on_a_working_page(new_family, base_url, viewport):
    page = new_family(viewport)
    page.goto(f"{base_url}/start")
    page.locator(".fr-path", has_text="Import a trip you booked").click()
    expect(page.locator("textarea")).to_be_visible()
    no_sideways_scroll(page)
    page.goto(f"{base_url}/start")
    page.locator(".fr-path", has_text="Browse community trips").click()
    expect(page.locator("h1")).to_have_text("Community trips")
    expect(page.get_by_role("link", name="Share yours").first).to_be_visible()
    expect(page.get_by_role("link", name="Turn a link into a trip").first).to_be_visible()
    no_sideways_scroll(page)
    page.goto(f"{base_url}/start")
    page.locator(".fr-path", has_text="Plan a trip").click()
    expect(page.locator("#st-form")).to_be_visible()
    assert page.url.endswith("#st-form")
    no_sideways_scroll(page)
