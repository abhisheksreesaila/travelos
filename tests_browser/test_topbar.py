"""F-139: one top bar for the signed-in web. A real browser presses each top-bar link and checks where it lands, and checks where the bar shows:
from 1020px up (the laptop), not on the tablet (721 to 1019 keeps its own header) and not on the phone (bottom tabs, no bar)."""
import pytest
from playwright.sync_api import expect

from tests_browser.helpers import DESKTOP, PHONE

SAMPLE = {"f": "f1", "h": "h1", "c": "c1"}
SECOND = {**SAMPLE, "d": "2026-10-23", "r": "2026-10-26", "a": "2", "k": "4,7"}
TABLET = {"width": 800, "height": 900}
LAPTOP = {"width": 1280, "height": 800}


@pytest.fixture
def signed_in(browser, base_url):
    """signed_in(viewport, trips=1, path="/trip/canvas?day=0") -> a page on `path`, signed in as a family with that many trips (none: `trips=0`)."""
    contexts = []

    def make(viewport, trips=1, path="/trip/canvas?day=0"):
        ctx = browser.new_context(viewport=viewport, reduced_motion="reduce")
        ctx.set_default_timeout(5000)
        contexts.append(ctx)
        ctx.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "pay"}, max_redirects=0)
        for pick in (SAMPLE, SECOND)[:trips]:
            ctx.request.post(f"{base_url}/pay", form=pick, max_redirects=0)
        page = ctx.new_page()
        page.goto(f"{base_url}{path}")
        return page

    yield make
    for c in contexts:
        c.close()


BAR = ".ga-topbar"


@pytest.mark.parametrize("viewport", [DESKTOP, LAPTOP], ids=["1440", "1280"])
@pytest.mark.parametrize("path", ["/trip/canvas?day=0", "/trip/canvas", "/family", "/trip/details", "/trip/ask", "/trip/family", "/calendar"])
def test_every_signed_in_page_shows_the_same_bar(signed_in, viewport, path):
    page = signed_in(viewport, path=path)
    bar = page.locator(BAR)
    expect(bar).to_be_visible()
    nav = bar.locator(".ga-tb-nav")
    expect(nav.locator("a")).to_have_text(["Trip", "Family", "Ask/"])
    expect(bar.locator(".ga-tb-picker")).to_be_visible()
    expect(bar.locator(".ga-tb-sos")).to_be_visible()
    expect(bar.locator(".ga-tb-account")).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    assert page.evaluate("document.querySelector('.ga-topbar').getBoundingClientRect().height") < 70


def test_the_section_you_are_in_is_marked(signed_in):
    for path, label in [("/trip/canvas?day=0", "Trip"), ("/trip/canvas", "Trip"), ("/trip/details", "Trip"), ("/family", "Family"), ("/trip/family", "Family"), ("/trip/ask", "Ask/")]:
        page = signed_in(DESKTOP, path=path)
        expect(page.locator(f"{BAR} .ga-tb-nav a[aria-current='page']")).to_have_text([label])


def test_trip_opens_the_trips_day(signed_in):
    page = signed_in(DESKTOP, path="/family")
    page.click(f"{BAR} .ga-tb-trip")
    page.wait_for_url("**/trip/canvas?day=0*")      # before the trip: its first day
    expect(page.locator("#cz")).to_be_visible()
    expect(page.locator(f"{BAR} .ga-tb-nav a[aria-current='page']")).to_have_text(["Trip"])


def test_family_opens_the_family_chat(signed_in):
    page = signed_in(DESKTOP)
    page.click(f"{BAR} .ga-tb-family")
    page.wait_for_url("**/trip/family")
    expect(page.locator(BAR)).to_be_visible()
    expect(page.locator("#main")).to_be_visible()


def test_ask_opens_the_ask_box_and_the_slash_key_goes_there_too(signed_in):
    page = signed_in(DESKTOP)
    page.click(f"{BAR} .ga-tb-ask")
    page.wait_for_url("**/trip/ask")
    expect(page.locator("#main textarea").first).to_be_visible()      # the Ask box: say or type the plan
    page = signed_in(DESKTOP, path="/trip/canvas?day=0")
    page.keyboard.press("/")
    page.wait_for_url("**/trip/ask")


def test_the_slash_key_leaves_a_field_alone(signed_in):
    page = signed_in(DESKTOP, path="/family")
    page.fill("input[name=phone]", "")
    page.focus("input[name=phone]")
    page.keyboard.type("/")
    assert page.url.endswith("/family")
    expect(page.locator("input[name=phone]")).to_have_value("/")


def test_sos_opens_the_emergency_sheet(signed_in):
    page = signed_in(DESKTOP, path="/family")
    page.click(f"{BAR} .ga-tb-sos")
    page.wait_for_url("**/trip/canvas?sos=1*")
    expect(page.locator(".cz-sheet")).to_be_visible()


def test_the_brand_goes_home(signed_in):
    page = signed_in(DESKTOP, path="/family")
    page.click(f"{BAR} .ga-brand")
    page.wait_for_url(lambda u: u.rstrip("/").count("/") == 2)    # the landing: http://host:port/
    assert page.locator(BAR).count() == 0                            # which keeps its own header


def test_the_picker_switches_trips(signed_in):
    page = signed_in(DESKTOP, trips=2, path="/family")
    first = page.locator(f"{BAR} .ga-tb-pickdates").inner_text()
    page.click(f"{BAR} .ga-tb-picker summary")
    pop = page.locator(f"{BAR} .ga-tb-pop-trip")
    expect(pop).to_be_visible()
    box = pop.bounding_box()
    assert box["x"] >= 0 and box["x"] + box["width"] <= DESKTOP["width"]
    expect(pop.locator("[aria-current='true']")).to_have_count(1)
    page.click(f"{BAR} .ga-tb-sw:not([aria-current])")
    page.wait_for_url("**/trip/canvas?day=0*")
    assert page.locator(f"{BAR} .ga-tb-pickdates").inner_text() != first      # the other trip is open now


def test_the_picker_offers_to_plan_another_trip(signed_in):
    page = signed_in(DESKTOP, path="/family")
    page.click(f"{BAR} .ga-tb-picker summary")
    page.click(f"{BAR} .ga-tb-pop-trip >> text=Plan another trip")
    page.wait_for_url("**/start")


def test_the_avatar_menu_has_people_and_invites_and_signs_out(signed_in):
    page = signed_in(DESKTOP, path="/trip/canvas?day=0")
    page.click(f"{BAR} .ga-tb-account summary")
    expect(page.locator(f"{BAR} .ga-tb-pop-me")).to_contain_text("Ari Rivera")
    page.click(f"{BAR} .ga-tb-pop-me >> text=People and invites")
    page.wait_for_url("**/family")
    page.click(f"{BAR} .ga-tb-account summary")
    page.click(f"{BAR} .ga-tb-pop-me >> text=Sign out")
    page.wait_for_url(lambda u: "/family" not in u)
    page.goto(page.url.rstrip("/") + "/trip/canvas")
    page.wait_for_url("**/signin**")
    assert page.locator(BAR).count() == 0


def test_a_menu_closes_on_escape_and_on_a_press_outside(signed_in):
    page = signed_in(DESKTOP, trips=2, path="/family")
    page.click(f"{BAR} .ga-tb-picker summary")
    expect(page.locator(f"{BAR} .ga-tb-picker")).to_have_attribute("open", "")
    page.keyboard.press("Escape")
    expect(page.locator(f"{BAR} .ga-tb-picker")).not_to_have_attribute("open", "")
    page.click(f"{BAR} .ga-tb-account summary")
    page.click(f"{BAR} .ga-tb-picker summary")                         # opening another closes the first
    expect(page.locator(f"{BAR} .ga-tb-account")).not_to_have_attribute("open", "")
    page.mouse.click(700, 500)
    expect(page.locator(f"{BAR} .ga-tb-picker")).not_to_have_attribute("open", "")


def test_a_family_with_no_trip_gets_start(signed_in):
    page = signed_in(DESKTOP, trips=0, path="/family")
    nav = page.locator(f"{BAR} .ga-tb-nav a")
    expect(nav).to_have_text(["Start", "Family", "Ask/"])
    expect(page.locator(f"{BAR} .ga-tb-picker")).to_have_count(0)
    page.click(f"{BAR} .ga-tb-trip")
    page.wait_for_url("**/start")
    expect(page.locator(BAR)).to_be_visible()


@pytest.mark.parametrize("path", ["/trip/canvas?day=0", "/trip/canvas", "/family", "/trip/ask"])
def test_on_a_phone_nothing_changes(signed_in, path):
    page = signed_in(PHONE, path=path)
    expect(page.locator(BAR)).to_be_hidden()
    if path != "/family":
        expect(page.locator(".ph-tabs")).to_be_visible()       # the bottom tabs stay
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    page.keyboard.press("/")                                    # and "/" does nothing there
    assert "/trip/ask" not in page.url or path == "/trip/ask"


def test_on_a_tablet_the_page_keeps_its_own_header(signed_in):
    page = signed_in(TABLET, path="/family")
    expect(page.locator(BAR)).to_be_hidden()
    expect(page.locator("header.ga-header")).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")


@pytest.mark.parametrize("width", [1020, 1000])
def test_the_bar_shows_from_1020_up(signed_in, width):
    page = signed_in({"width": width, "height": 800}, path="/family")
    assert page.locator(BAR).is_visible() == (width >= 1020)
    assert page.locator("header.ga-header").is_visible() == (width < 1020)
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
