"""F-043: invite -> copy the link -> a second person opens it, signs in with the dev sign-in, joins and sees the trip.
Also: the family page fits the screen at desktop and phone widths (lesson: measure the sideways scroll), and a viewer cannot edit in the browser."""
import uuid

import pytest
from playwright.sync_api import expect

from tests_browser.helpers import DESKTOP, PHONE

SAMPLE = {"f": "f1", "h": "h1", "c": "c1"}


@pytest.fixture
def contexts(browser):
    made = []

    def new(viewport):
        ctx = browser.new_context(viewport=viewport, reduced_motion="reduce")
        ctx.set_default_timeout(5000)
        made.append(ctx)
        return ctx

    yield new
    for c in made:
        c.close()


def owner_page(contexts, base_url, viewport):
    ctx = contexts(viewport)
    ctx.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "pay"}, max_redirects=0)
    ctx.request.post(f"{base_url}/pay", form=SAMPLE, max_redirects=0)
    page = ctx.new_page()
    page.goto(f"{base_url}/family")
    return page


def invite_from_page(page, email, role):
    page.fill("#fam-email", email)
    page.select_option("#fam-role-pick", role)
    page.click("#fam-invite-form button[type=submit]")
    page.wait_for_selector("[data-link]")
    return page.locator("[data-link]").first.input_value()


def no_sideways_scroll(page):
    return page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")


@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["desktop", "phone"])
def test_invite_then_join_as_a_second_dev_user_and_see_the_trip(contexts, base_url, viewport):
    page = owner_page(contexts, base_url, viewport)
    sam = f"sam.kim@{uuid.uuid4().hex[:8]}.example.com"
    link = invite_from_page(page, sam, "editor")
    assert link.startswith(f"{base_url}/join/")
    expect(page.locator("#fam-pending")).to_contain_text(sam)
    assert no_sideways_scroll(page)

    other = contexts(viewport).new_page()
    other.goto(link)
    expect(other.locator("#join-signin")).to_be_visible()
    assert sam not in other.content()  # a stranger with the link does not see the full address
    other.click("#join-signin")
    other.fill("#si-email", sam)
    other.click("#si-dev-form button[type=submit]")
    other.wait_for_url("**/calendar")
    other.goto(f"{base_url}/calendar?view=days")
    expect(other.locator("h1")).to_contain_text("LA with the kids")
    expect(other.locator(".cal-presence")).to_contain_text("Ari Rivera is planning with you")
    other.goto(f"{base_url}/family")
    expect(other.locator("#fam-role")).to_contain_text("editor")
    expect(other.locator(".fam-member")).to_have_count(2)
    assert no_sideways_scroll(other)

    page.reload()  # the owner: the invite is used, two members are listed
    expect(page.locator(".fam-member")).to_have_count(2)
    expect(page.locator("#fam-pending")).to_have_count(0)


def test_a_viewer_can_look_but_the_calendar_shows_why_they_cannot_change_it(contexts, base_url):
    page = owner_page(contexts, base_url, DESKTOP)
    vi = f"vi.ewer@{uuid.uuid4().hex[:8]}.example.com"
    invite_from_page(page, vi, "viewer")
    ctx = contexts(DESKTOP)
    ctx.request.post(f"{base_url}/signin", form={"email": vi, "next": "/", "intent": "save"}, max_redirects=0)
    other = ctx.new_page()
    other.goto(f"{base_url}/calendar?view=days")
    expect(other.locator("#cal-viewer")).to_be_visible()
    expect(other.locator("#cal-invite-btn")).to_have_count(0)
    expect(other.locator(".cal-dayadd").first).to_be_hidden()  # no way to add: the plus, the empty-day card and the note box are gone
    expect(other.locator(".cal-composer")).to_be_hidden()
    # a write posted from the page is refused with the message on the calendar, and nothing is added
    other.evaluate("""async () => { await fetch('/calendar/activities', {method: 'POST', body: new URLSearchParams({id: 'a1', day: '1', start: '10:00', end: '11:00', title: 'Sneaky', kind: 'fun'})}); }""")
    other.reload()
    expect(other.locator("text=Sneaky")).to_have_count(0)


def test_the_family_page_has_no_sideways_scroll_at_the_narrow_widths(contexts, base_url):
    for width in (1440, 1280, 1000, 800, 390, 320):
        page = owner_page(contexts, base_url, {"width": width, "height": 800})
        invite_from_page(page, f"narrow{width}@{uuid.uuid4().hex[:8]}.example.com", "viewer")
        assert no_sideways_scroll(page), width


SHARE_STUB = "window.__shared = []; navigator.share = (d) => { window.__shared.push(d); return Promise.resolve(); }; 0"


def test_share_invite_opens_the_share_sheet_with_a_short_message_and_the_link(contexts, base_url):
    page = owner_page(contexts, base_url, PHONE)
    sam = f"sam.kim@{uuid.uuid4().hex[:8]}.example.com"
    link = invite_from_page(page, sam, "editor")
    page.evaluate(SHARE_STUB)
    page.get_by_role("button", name="Share invite").click()
    shared = page.evaluate("window.__shared")
    assert shared == [{"title": "Join our trip on GitAway", "text": f"Join our trip on GitAway. Sign in with {sam} to see the plan.", "url": link}]
    assert no_sideways_scroll(page)


def test_share_invite_copies_the_link_and_says_copied_where_sharing_is_not_available(contexts, base_url):
    ctx = contexts(DESKTOP)
    ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=base_url)
    ctx.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "pay"}, max_redirects=0)
    ctx.request.post(f"{base_url}/pay", form=SAMPLE, max_redirects=0)
    page = ctx.new_page()
    page.goto(f"{base_url}/family")
    link = invite_from_page(page, f"sam.kim@{uuid.uuid4().hex[:8]}.example.com", "viewer")
    page.evaluate("Object.defineProperty(navigator, 'share', {value: undefined, configurable: true}); 0")
    button = page.locator("[data-share]")  # by attribute: its name changes to Copied
    button.click()
    expect(button).to_have_text("Copied")
    assert page.evaluate("navigator.clipboard.readText()") == link


def test_the_invite_form_explains_that_no_email_is_sent(contexts, base_url):
    page = owner_page(contexts, base_url, DESKTOP)
    expect(page.locator("#fam-noemail")).to_contain_text("GitAway doesn't send email")
