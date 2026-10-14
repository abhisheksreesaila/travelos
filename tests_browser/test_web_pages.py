"""F-146: Family, the trip details and Start in the web look (top bar, white cards, trip type), in a real browser.

Each page fits 1440x900 without page scroll, has no sideways scroll at any width, and every button on it is pressed here (lesson 2026-10-01).
"""
import uuid
from pathlib import Path

import pytest
from playwright.sync_api import expect

from tests_browser.helpers import DESKTOP, PHONE

TEMPLATE = (Path(__file__).resolve().parent.parent / "docs" / "trip-template.md").read_text()
WIDTHS = [(1440, 900), (1280, 800), (1000, 800), (800, 800), (390, 844), (320, 700)]


@pytest.fixture
def contexts(browser):
    made = []

    def new(viewport=DESKTOP):
        ctx = browser.new_context(viewport=viewport, reduced_motion="reduce")
        ctx.set_default_timeout(5000)
        made.append(ctx)
        return ctx

    yield new
    for c in made:
        c.close()


def sign_in(ctx, base_url, email):
    ctx.request.post(f"{base_url}/signin", form={"email": email, "next": "/", "intent": "save"}, max_redirects=0)


@pytest.fixture
def ari(contexts, base_url):
    """Ari, signed in with the template trip imported, and a page on /family."""
    ctx = contexts()
    sign_in(ctx, base_url, "ari.rivera@example.com")
    assert ctx.request.post(f"{base_url}/trips/import/save", form={"text": TEMPLATE}, max_redirects=0).status == 303
    return ctx, ctx.new_page()


def fits(page):
    return page.evaluate("[document.documentElement.scrollHeight, document.documentElement.clientHeight]")


def no_sideways_scroll(page):
    return page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")


def join_as(contexts, base_url, owner_page, email, role="editor"):
    """Invite `email` from the owner's /family page and join through the link in a second browser; returns the second person's page."""
    owner_page.goto(f"{base_url}/family")
    owner_page.fill("#fam-email", email)
    owner_page.select_option("#fam-role-pick", role)
    owner_page.click("#fam-invite-form button[type=submit]")
    owner_page.wait_for_selector("[data-link]")
    link = owner_page.locator("[data-link]").first.input_value()
    ctx = contexts()
    other = ctx.new_page()
    other.goto(link)
    other.click("#join-signin")
    other.fill("#si-email", email)
    other.click("#si-dev-form button[type=submit]")
    other.wait_for_url("**/trip/canvas*")
    return other


# ---- the look and the fit ----------------------------------------------------------------------------------------------

@pytest.mark.parametrize("path", ["/family", "/trip/details", "/start"])
def test_each_page_has_the_top_bar_white_cards_and_the_trip_type_and_fits_1440_by_900(ari, base_url, path):
    ctx, page = ari
    page.goto(f"{base_url}{path}")
    expect(page.locator(".ga-topbar")).to_be_visible()
    expect(page.locator(".ga-tb-nav")).to_contain_text("Family")
    card = {"/family": ".fam-sec", "/trip/details": ".ti-sec", "/start": ".st-card"}[path]
    style = page.locator(card).first.evaluate("e => { const s = getComputedStyle(e); return [s.backgroundColor, parseFloat(s.borderTopLeftRadius), s.boxShadow] }")
    assert style[0] == "rgb(255, 255, 255)" and style[1] >= 18 and style[2] != "none", style
    assert "Bricolage" in page.locator("h1").first.evaluate("e => getComputedStyle(e).fontFamily")
    scroll_h, client_h = fits(page)
    assert scroll_h <= client_h, f"{path} scrolls: {scroll_h} > {client_h}"


@pytest.mark.parametrize("path", ["/family", "/trip/details", "/start"])
@pytest.mark.parametrize("size", WIDTHS, ids=[f"{w}" for w, _ in WIDTHS])
def test_no_page_scrolls_sideways_at_any_width(ari, base_url, path, size):
    ctx, page = ari
    page.set_viewport_size({"width": size[0], "height": size[1]})
    page.goto(f"{base_url}{path}")
    assert no_sideways_scroll(page)
    if size[0] >= 1280:
        assert fits(page)[0] <= fits(page)[1]


def test_a_family_with_many_people_keeps_the_page_still_and_scrolls_the_list(ari, contexts, base_url):
    ctx, page = ari
    for i in range(3):
        join_as(contexts, base_url, page, f"member{i}.{uuid.uuid4().hex[:6]}@example.com")
    for i in range(6):
        page.goto(f"{base_url}/family")
        page.fill("#fam-email", f"guest{i}.{uuid.uuid4().hex[:6]}@example.com")
        page.click("#fam-invite-form button[type=submit]")
        page.wait_for_selector("[data-link]")
    page.goto(f"{base_url}/family")
    expect(page.locator(".fam-invite")).to_have_count(6)
    assert no_sideways_scroll(page)
    assert fits(page)[0] <= fits(page)[1]  # the lists scroll inside their cards, the page stays put
    assert page.locator("#fam-pending").evaluate("e => getComputedStyle(e).overflowY") == "auto"
    assert page.locator("#fam-members").evaluate("e => getComputedStyle(e).overflowY") == "auto"
    expect(page.locator(".fam-member")).to_have_count(4)
    assert page.locator("#fam-members").evaluate("e => e.scrollHeight > e.clientHeight")  # four members do not fit the 15rem cap: the list scrolls inside its card


# ---- /family: every button ---------------------------------------------------------------------------------------------

def test_invite_someone_takes_a_lone_admin_to_the_invite_form(ari, base_url):
    ctx, page = ari
    page.goto(f"{base_url}/family")
    page.click("#fam-alone a:has-text('Invite someone')")
    assert page.url.endswith("/family#invite")
    expect(page.locator("#invite")).to_be_in_viewport()
    page.fill("#fam-email", "pat@example.com")
    expect(page.locator("#fam-email")).to_have_value("pat@example.com")


def test_the_invitations_section_keeps_its_stable_id_and_the_invite_form_works(ari, base_url):
    ctx, page = ari
    page.goto(f"{base_url}/family#invite")
    expect(page.locator("section#invite")).to_be_visible()
    page.fill("#fam-email", "kim@example.com")
    page.click("#fam-invite-form button[type=submit]")  # Create invite link
    expect(page.locator("#fam-pending")).to_contain_text("kim@example.com")


def test_copy_link_and_revoke(ari, base_url):
    ctx, page = ari
    page.goto(f"{base_url}/family")
    page.fill("#fam-email", "lee@example.com")
    page.click("#fam-invite-form button[type=submit]")
    page.wait_for_selector("[data-link]")
    page.evaluate("Object.defineProperty(navigator, 'share', {value: undefined})")
    page.click("button[data-copy]")  # Copy link
    expect(page.locator("button[data-copy]")).to_have_text("Copied")
    page.click("button[data-share]")  # Share invite: no share sheet here, so it copies and says so
    expect(page.locator("button[data-share]")).to_have_text("Copied")
    page.click("#fam-pending button:has-text('Revoke')")
    expect(page.locator("#fam-pending")).to_have_count(0)


def test_save_my_number_and_the_vegetarian_switch(ari, base_url):
    ctx, page = ari
    page.goto(f"{base_url}/family")
    page.fill("#fam-phone", "+1 310 555 0142")
    page.click("#fam-phone-form button[type=submit]")  # Save my number
    page.wait_for_url("**/family#my-phone")
    expect(page.locator("#fam-phone")).to_have_value("+1 310 555 0142")
    page.click("#fam-food-toggle")  # Vegetarian
    expect(page.locator("#fam-food-toggle")).to_have_attribute("aria-pressed", "true")


def test_change_role_remove_leave_and_switch_family(ari, contexts, base_url):
    ctx, page = ari
    sam = f"sam.{uuid.uuid4().hex[:6]}@example.com"
    other = join_as(contexts, base_url, page, sam, "editor")
    page.goto(f"{base_url}/family")
    row = page.locator(f".fam-member:has-text('{sam}')")
    row.locator("select").select_option("viewer")
    row.locator("button:has-text('Change')").click()
    expect(page.locator(f".fam-member:has-text('{sam}') .fam-role-tag")).to_have_text("Viewer")
    # Leave: the only admin cannot go, and the page says why
    page.once("dialog", lambda d: d.accept())
    page.locator(".fam-member:has-text('(you)') button:has-text('Leave')").click()
    expect(page.locator("#fam-error")).to_be_visible()
    # Switch: Sam is in two families now (their own and Ari's)
    other.goto(f"{base_url}/family")
    expect(other.locator("#fam-switcher")).to_be_visible()
    other.locator("#fam-switcher button:has-text('Switch')").click()
    expect(other.locator("#fam-switcher .fam-here")).to_be_visible()
    # Remove
    page.once("dialog", lambda d: d.accept())
    page.locator(f".fam-member:has-text('{sam}') button:has-text('Remove')").click()
    expect(page.locator(".fam-member")).to_have_count(1)


# ---- /trip/details: every button ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("button,url", [("#ti-cal", "**/trip/canvas*"), ("#ti-edit-trip", "**/trips/build/edit?trip=*"), ("#ti-correct", "**/trips/import"), ("#ti-delete", "**/trip/delete?trip=*")])
def test_every_trip_details_button_lands_where_it_says(ari, base_url, button, url):
    ctx, page = ari
    page.goto(f"{base_url}/trip/details")
    page.click(button)
    page.wait_for_url(url)


# ---- /start: every button ----------------------------------------------------------------------------------------------

def test_start_import_continue_steppers_and_find_my_trip(ari, base_url):
    ctx, page = ari
    page.goto(f"{base_url}/start")
    page.click("#st-import")
    page.wait_for_url("**/trips/import")
    page.goto(f"{base_url}/start")
    page.click(".st-continue")
    page.wait_for_url("**/trip/canvas*")
    page.goto(f"{base_url}/start")
    expect(page.locator("#st-form input[name=to][value=la]")).to_be_checked()
    adults = page.locator("[data-field=a] .ga-step-btn.is-more")  # the plus of the Adults stepper
    adults.click()
    page.click("#st-form button[type=submit]")  # Find my trip
    page.wait_for_url("**/plan?*")
    assert "a=3" in page.url


def test_start_for_a_family_with_no_trip_shows_the_welcome_beside_the_form_and_still_fits(contexts, base_url):
    ctx = contexts()
    sign_in(ctx, base_url, f"new.{uuid.uuid4().hex[:6]}@example.com")
    page = ctx.new_page()
    page.goto(f"{base_url}/start")
    expect(page.locator(".st .fr")).to_be_visible()
    expect(page.locator(".st-card")).to_be_visible()
    assert fits(page)[0] <= fits(page)[1]
    page.click(".st .fr-path >> nth=0")  # "Plan a trip" scrolls to / focuses the form
    assert no_sideways_scroll(page)
