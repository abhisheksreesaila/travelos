"""F-064: the live site in a real browser (the showcase switched off, as in production): the landing has no community or creators part and
no sideways scroll at phone and desktop width, a new family's first screens fit, and the workspace says it is a preview."""
import pytest

from tests_browser.helpers import PHONE

WIDE = {"width": 1280, "height": 800}
SIZES = pytest.mark.parametrize("viewport", [WIDE, PHONE], ids=["1280", "390"])


@pytest.fixture
def real(monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")


@pytest.fixture
def visit(browser, base_url, real):
    made = []

    def go(path, viewport):
        ctx = browser.new_context(viewport=viewport, reduced_motion="reduce")
        ctx.set_default_timeout(8000)
        made.append(ctx)
        page = ctx.new_page()
        page.goto(f"{base_url}{path}")
        page.wait_for_timeout(300)
        return page

    yield go
    for c in made:
        c.close()


def no_sideways_scroll(page):
    return page.evaluate("document.documentElement.scrollWidth") <= page.evaluate("document.documentElement.clientWidth")


@SIZES
def test_landing_has_no_community_or_creators_and_no_sideways_scroll(visit, viewport):
    page = visit("/", viewport)
    assert no_sideways_scroll(page)
    assert page.locator("#community-trips, .forkline, .creators, .trip-row").count() == 0
    assert page.get_by_text("Community trips").count() == 0 and page.get_by_text("Leave a trail").count() == 0
    assert page.locator("#cal").count() == 1 and page.locator(".feature").count() == 4   # the illustrations stay
    assert page.locator(".search .field-value.is-hint").count() == 4
    page.get_by_role("button", name="Plan a trip").click()                                # the one door still opens the start page
    page.wait_for_url("**/start**")


@SIZES
def test_workspace_is_labelled_a_preview_and_does_not_scroll_sideways(visit, viewport):
    page = visit("/plan", viewport)
    assert page.locator(".ws-preview").is_visible()
    assert "sample prices" in page.locator(".ws-preview").inner_text()
    assert page.locator('[data-pane="community"]').count() == 0
    assert no_sideways_scroll(page)
    page.keyboard.press("7")                                                              # no pane 7: nothing breaks
    assert page.locator("#ws-total").is_visible()


@SIZES
def test_a_hidden_page_is_a_plain_404(visit, viewport):
    page = visit("/community", viewport)
    assert page.get_by_text("Nothing here").is_visible()
    assert no_sideways_scroll(page)
