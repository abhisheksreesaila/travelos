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
    """A stranger's landing is the cover (F-206): off the showcase it has no sample community part, no link to Community trips while nobody has
    published, and its first door opens the start page."""
    page = visit("/", viewport)
    assert no_sideways_scroll(page)
    assert page.locator("#community-trips, .forkline, .creators, .trip-row").count() == 0
    assert page.get_by_text("Community trips").count() == 0 and page.get_by_text("Been somewhere wonderful?").count() == 0
    assert page.locator('a[href="/community"]').count() == 0                             # See trips people shared waits until someone has
    page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
    page.locator(".cv-ctas a", has_text="Start a trip").click()
    page.wait_for_url("**/start**")


@SIZES
def test_the_signed_in_landing_keeps_its_illustrations_and_a_neutral_door(visit, viewport, base_url):
    page = visit("/start", viewport)
    page.context.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "save"}, max_redirects=0)
    page.goto(f"{base_url}/")
    assert no_sideways_scroll(page)
    assert page.locator("#community-trips, .forkline, .creators, .trip-row").count() == 0
    assert page.locator("#cal").count() == 1 and page.locator(".feature").count() == 4   # the illustrations stay
    assert page.locator(".search .field-value.is-hint").count() == 4
    page.get_by_role("button", name="Plan a trip").click()                                # the one door still opens the start page
    page.wait_for_url("**/start**")


@SIZES
def test_production_plan_asks_where_and_shows_no_invented_offers(visit, viewport):
    """F-198 (6): off the showcase /plan never draws the sample workspace; it asks where you are going, and a place gets the honest lanes."""
    page = visit("/plan", viewport)
    assert page.get_by_role("heading", name="Where are you going?").is_visible()
    assert page.locator(".ws-preview").count() == 0 and page.locator("#ws-total").count() == 0
    assert no_sideways_scroll(page)
    page = visit("/plan?place=San+Diego&d=2027-03-05&r=2027-03-09&a=2", viewport)
    assert page.locator("h2.ps-name").first.inner_text() == "Search flights to San Diego"
    assert page.locator(".ws-preview").count() == 0 and no_sideways_scroll(page)


@SIZES
def test_a_hidden_page_is_a_plain_404(visit, viewport):
    page = visit("/community", viewport)
    assert page.get_by_text("Nothing here").is_visible()
    assert no_sideways_scroll(page)
