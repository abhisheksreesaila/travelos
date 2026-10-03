"""F-074: Face ID sign-in in a real browser, with Chromium's virtual authenticator (internal transport, user verification on, resident keys).

At 390: add a passkey from /family, sign out, sign in with the Face ID button and land signed in; the Today card in the Home Screen app
(Not now, then Turn on); Remove; a browser with no passkey support never shows the button. Every button is pressed.
The page is opened on `localhost`: a passkey's site cannot be an IP address."""
import pytest
from playwright.sync_api import expect

from tests_browser.helpers import PHONE

EMAIL = "faceid.fan@example.com"
NO_AUTOFILL = "PublicKeyCredential.isConditionalMediationAvailable = () => Promise.resolve(false)"   # else the virtual authenticator answers the email box's suggestion by itself
STANDALONE ="Object.defineProperty(navigator, 'standalone', {get: () => true})"


def attach(ctx, page):
    """A virtual phone: an internal authenticator that holds resident keys and verifies the user by itself. Returns (cdp session, authenticator id)."""
    cdp = ctx.new_cdp_session(page)
    cdp.send("WebAuthn.enable")
    made = cdp.send("WebAuthn.addVirtualAuthenticator", {"options": {
        "protocol": "ctap2", "transport": "internal", "hasResidentKey": True, "hasUserVerification": True, "isUserVerified": True, "automaticPresenceSimulation": True}})
    return cdp, made["authenticatorId"]


@pytest.fixture
def site(base_url):
    return base_url.replace("127.0.0.1", "localhost")


@pytest.fixture
def phone(browser, site):
    """phone(email=EMAIL, init=None) -> (page, context): 390 wide, a virtual authenticator attached, signed in with the dev sign-in."""
    contexts = []

    def make(email=EMAIL, init=None, sign_in=True, authenticator=True):
        ctx = browser.new_context(viewport=PHONE, reduced_motion="reduce", has_touch=True, is_mobile=True)
        ctx.set_default_timeout(5000)
        contexts.append(ctx)
        page = ctx.new_page()
        if init:
            page.add_init_script(script=init)
        if authenticator:
            attach(ctx, page)
        if sign_in:
            ctx.request.post(f"{site}/signin", form={"email": email, "next": "/", "intent": "save"}, max_redirects=0)
        return page, ctx

    yield make
    for c in contexts:
        c.close()


def no_sideways_scroll(page):
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")


def add_from_family(page, site):
    page.goto(f"{site}/family")
    card = page.locator("#pk-card")
    expect(card).to_be_visible()
    expect(card).to_contain_text("Use Face ID next time")
    page.get_by_role("button", name="Turn on Face ID").click()
    expect(page.locator(".pk-item")).to_have_count(1)   # the page reloaded with the new passkey listed


def test_add_a_passkey_then_sign_in_with_face_id_at_390(phone, site):
    page, ctx = phone(init=NO_AUTOFILL)
    add_from_family(page, site)
    expect(page.locator(".pk-item .pk-name")).to_have_text("Linux computer")
    expect(page.get_by_role("button", name="Add another phone")).to_be_visible()
    expect(page.locator("#pk-card")).not_to_contain_text("Use Face ID next time")
    no_sideways_scroll(page)

    ctx.clear_cookies()   # signed out
    page.goto(f"{site}/signin?next=/family")
    button = page.get_by_role("button", name="Sign in with Face ID")
    expect(button).to_be_visible()
    no_sideways_scroll(page)
    button.click()
    expect(page.locator("#si-faceid-status")).to_have_text("Welcome back, Faceid")
    page.wait_for_url(f"{site}/family")
    expect(page.locator("#fam-who")).to_have_text(f"Signed in as {EMAIL}.")


def test_add_another_phone_button_adds_a_second_passkey(phone, site):
    page, ctx = phone(init=NO_AUTOFILL, authenticator=False)
    cdp, first = attach(ctx, page)
    add_from_family(page, site)
    cdp.send("WebAuthn.removeVirtualAuthenticator", {"authenticatorId": first})   # swap to a second virtual phone, which does not know the first passkey
    attach(ctx, page)
    page.get_by_role("button", name="Add another phone").click()
    expect(page.locator(".pk-item")).to_have_count(2)


def test_remove_deletes_the_passkey_and_it_can_no_longer_sign_in(phone, site):
    page, ctx = phone()
    add_from_family(page, site)
    page.get_by_role("button", name="Remove").click()
    expect(page.locator(".pk-item")).to_have_count(0)
    expect(page.get_by_role("button", name="Turn on Face ID")).to_be_visible()   # offered again
    ctx.clear_cookies()
    page.goto(f"{site}/signin")
    page.get_by_role("button", name="Sign in with Face ID").click()
    expect(page.locator("#si-faceid-status")).to_contain_text("did not work")
    expect(page.locator("#si-faceid-status")).to_have_class("si-note si-faceid-status is-bad")


def test_the_today_card_in_the_home_screen_app_not_now_then_turn_on(phone, site):
    page, ctx = phone(init=STANDALONE)
    ctx.request.post(f"{site}/pay", form={"f": "f1", "h": "h1", "c": "c1"}, max_redirects=0)
    page.goto(f"{site}/trip")
    card = page.locator("#pk-card")
    expect(card).to_be_visible()
    expect(card).to_contain_text("Use Face ID next time")
    no_sideways_scroll(page)
    page.get_by_role("button", name="Not now").click()
    expect(card).to_be_hidden()
    page.reload()
    expect(page.locator("#tp-panel-today")).to_be_visible()
    expect(card).to_be_hidden()   # it stays away on this phone
    page.evaluate("localStorage.clear()")
    page.reload()
    expect(card).to_be_visible()
    page.get_by_role("button", name="Turn on Face ID").click()
    expect(page.locator("#pk-done")).to_be_visible()
    expect(page.locator("#pk-done")).to_have_text("Face ID is on for this phone.")
    page.reload()
    expect(page.locator("#pk-card")).to_have_count(0)   # a person with a passkey is not asked again


def test_the_today_card_is_not_shown_in_a_browser_tab(phone, site):
    page, ctx = phone()
    ctx.request.post(f"{site}/pay", form={"f": "f1", "h": "h1", "c": "c1"}, max_redirects=0)
    page.goto(f"{site}/trip")
    expect(page.locator("#tp-panel-today")).to_be_visible()
    expect(page.locator("#pk-card")).to_be_hidden()


def test_a_browser_without_passkeys_never_shows_the_button(phone, site):
    page, _ = phone(init="delete window.PublicKeyCredential", sign_in=False, authenticator=False)
    page.goto(f"{site}/signin")
    expect(page.locator("#si-dialog")).to_be_visible()
    expect(page.locator("#si-faceid")).to_be_hidden()
    no_sideways_scroll(page)


def test_the_browsers_own_suggestion_signs_in_from_the_email_box(phone, site):
    page, ctx = phone()
    add_from_family(page, site)
    ctx.clear_cookies()
    page.goto(f"{site}/signin?next=/family")   # the virtual authenticator answers the conditional request, as a tap on the suggestion would
    page.wait_for_url(f"{site}/family")
    expect(page.locator("#fam-who")).to_have_text(f"Signed in as {EMAIL}.")
