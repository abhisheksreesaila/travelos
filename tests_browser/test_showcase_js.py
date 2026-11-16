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
def test_landing_has_no_community_or_creators_and_no_sideways_scroll(visit, viewport, monkeypatch):
    """A stranger's landing is the cover (F-266): off the showcase it has no sample community part; Guides is in its header (D-458, F-262), whose page says nobody has shared yet.
    Its door needs no sign-in (D-761): with no LiteAPI key there is no matrix, so Start a trip goes to the import of a trip already booked, which signs you in first."""
    monkeypatch.delenv("LITEAPI_KEY", raising=False)
    page = visit("/", viewport)
    assert no_sideways_scroll(page)
    assert page.locator("#community-trips, .forkline, .creators, .trip-row").count() == 0
    assert page.get_by_text("Been somewhere wonderful?").count() == 0
    page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
    page.locator(".cv-close .cv-ctas a", has_text="Start a trip").click()
    page.wait_for_url("**/signin?next=/trips/import*")      # the import keeps a trip, so it asks who you are first
    page.goto(page.url.split("/signin")[0] + "/guides")
    assert page.get_by_text("No guides yet").first.is_visible()


@SIZES
def test_the_front_door_opens_the_way_in_signed_in_or_not(visit, viewport, base_url, monkeypatch):
    """D-761: Start a trip is the same door for everyone. With a LiteAPI key it opens the ask (/plan/ask); off the showcase without one there is no matrix, so it opens the import of a trip already booked.
    A signed-in family with no trip has no landing (F-231): "/" sends it to the same place."""
    page = visit("/", viewport)
    page.context.request.post(f"{base_url}/signin", form={"email": "front.door@example.com", "next": "/", "intent": "save"}, max_redirects=0)      # a family with no trip
    for key, want in ((None, "**/trips/import"), ("a-key", "**/plan/ask")):      # signed in here, so the import opens at once
        if key:
            monkeypatch.setenv("LITEAPI_KEY", key)
        else:
            monkeypatch.delenv("LITEAPI_KEY", raising=False)
        page.goto(f"{base_url}/")
        page.wait_for_url(want)
        assert no_sideways_scroll(page)
        assert page.locator("#cal, .feature, .search, .forkline").count() == 0


@SIZES
def test_production_ask_shows_no_invented_offers(visit, viewport, monkeypatch):
    """F-198 (6), F-257: off the showcase the old /plan (retired, F-254) lands on the ask, which draws no sample prices or offers."""
    monkeypatch.setenv("LITEAPI_KEY", "a-key")
    page = visit("/plan", viewport)
    page.wait_for_url("**/plan/ask")
    assert page.get_by_role("combobox").or_(page.get_by_role("textbox")).first.is_visible()
    assert page.get_by_text("Preview: sample prices").count() == 0 and page.locator(".ws-preview").count() == 0
    assert no_sideways_scroll(page)


@SIZES
def test_a_hidden_page_is_a_plain_404(visit, viewport):
    page = visit("/sandbox", viewport)
    assert page.get_by_text("404 Not Found").is_visible()
    assert no_sideways_scroll(page)
