"""F-076: the legal links are pressed in a browser, and the pages do not scroll sideways at 390."""
import pytest

from tests_browser.helpers import DESKTOP, PHONE


@pytest.fixture
def open_page(browser, base_url):
    ctxs = []

    def go(path, viewport=DESKTOP):
        ctx = browser.new_context(viewport=viewport, reduced_motion="reduce")
        ctx.set_default_timeout(5000)
        ctxs.append(ctx)
        page = ctx.new_page()
        page.goto(base_url + path)
        return page
    yield go
    for c in ctxs:
        c.close()


@pytest.mark.parametrize("start", ["/", "/signin"])
@pytest.mark.parametrize("label,path", [("Privacy", "/privacy"), ("Terms", "/terms")])
def test_links_land_on_the_page(open_page, start, label, path):
    page = open_page(start)
    scope = page.locator("#si-legal") if start == "/signin" else page.locator("footer")
    scope.locator("a", has_text=label).click()
    page.wait_for_url("**" + path)
    assert page.locator("h1").inner_text() in ("Privacy policy", "Terms of use")


@pytest.mark.parametrize("path", ["/privacy", "/terms"])
def test_no_sideways_scroll_on_a_phone(open_page, path):
    page = open_page(path, PHONE)
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
