"""F-074: Face ID sign-in in a real browser, with Chromium's virtual authenticator (internal transport, user verification on, resident keys).

At 390: add a passkey from /family, sign out, sign in with the Face ID button and land signed in; the Today card in the Home Screen app
(Not now, then Turn on); Remove; a browser with no passkey support never shows the button. Every button is pressed.
The page is opened on `localhost`: a passkey's site cannot be an IP address."""
import sys
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
    expect(page.locator(".pk-item .pk-name")).to_have_text("Windows PC" if sys.platform == "win32" else "Mac" if sys.platform == "darwin" else "Linux computer")   # named after the headless browser's own system
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
    welcome = page.locator("#si-welcome")
    expect(welcome).to_be_visible()   # storyboard frame 2, full screen for a beat
    expect(welcome).to_contain_text("Welcome back, Faceid")
    expect(welcome).to_contain_text("Signed in with Face ID. No password, no code by text.")
    expect(welcome).to_contain_text("Your passkey stays on this")
    assert welcome.bounding_box()["width"] == PHONE["width"] and welcome.bounding_box()["height"] == PHONE["height"]
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
    expect(page.locator("#si-dialog")).to_be_visible()
    expect(page.locator("#si-faceid")).to_be_hidden()   # F-088: removing Face ID on this phone forgets it, so the button is gone here
    assert page.evaluate("localStorage.getItem('ga-faceid-on')") is None


def test_the_today_card_in_the_home_screen_app_not_now_then_turn_on(phone, site):
    page, ctx = phone(init=STANDALONE)
    ctx.request.post(f"{site}/pay", form={"f": "f1", "h": "h1", "c": "c1"}, max_redirects=0)
    page.goto(f"{site}/trip/help")      # F-092: the card moved from Today to Help
    card = page.locator("#pk-card")
    expect(card).to_be_visible()
    expect(card).to_contain_text("Use Face ID next time")
    no_sideways_scroll(page)
    page.get_by_role("button", name="Not now").click()
    expect(card).to_be_hidden()
    page.reload()
    expect(page.locator("#hp-sos")).to_be_visible()      # Help is drawn
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
    page.goto(f"{site}/trip/help")      # F-092: the card moved from Today to Help
    expect(page.locator("#hp-sos")).to_be_visible()      # Help is drawn
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


REMEMBER = "localStorage.setItem('ga-faceid-on', 'old-passkey')"


def test_face_id_button_is_not_offered_on_a_phone_that_never_set_it_up(phone, site):
    page, _ = phone(init=NO_AUTOFILL, sign_in=False)
    page.goto(f"{site}/signin")
    expect(page.locator("#si-dialog")).to_be_visible()
    expect(page.locator("#si-faceid")).to_be_hidden()
    expect(page.get_by_role("button", name="Sign in with Face ID")).to_have_count(0)
    no_sideways_scroll(page)


def test_face_id_button_shows_on_a_phone_that_remembers_it(phone, site):
    page, _ = phone(init=NO_AUTOFILL + ";" + REMEMBER, sign_in=False)
    page.goto(f"{site}/signin")
    expect(page.get_by_role("button", name="Sign in with Face ID")).to_be_visible()
    no_sideways_scroll(page)


def test_a_passkey_this_address_does_not_know_says_so_points_to_google_and_hides_the_button(phone, site):
    page, ctx = phone(init=NO_AUTOFILL)   # the phone still holds a passkey this server no longer has (as one made before the move)
    add_from_family(page, site)
    pid = page.locator(".pk-item").get_attribute("data-passkey-id")
    ctx.request.post(f"{site}/passkeys/remove", form={"id": pid}, max_redirects=0)   # removed elsewhere: this phone's flag stays
    ctx.clear_cookies()
    page.goto(f"{site}/signin")
    page.get_by_role("button", name="Sign in with Face ID").click()
    status = page.locator("#si-faceid-status")
    expect(status).to_contain_text("Face ID is not set up for this address on this phone.")
    expect(status).to_contain_text("Use Continue with Google instead.")
    expect(status).to_have_class("si-note si-faceid-status is-bad")
    expect(page.locator("#si-faceid")).to_be_hidden()
    assert page.evaluate("localStorage.getItem('ga-faceid-on')") is None
    page.reload()
    expect(page.locator("#si-faceid")).to_be_hidden()   # and it stays gone


def test_a_cancelled_face_id_says_so_and_points_to_google_but_keeps_the_button(phone, site):
    cancel = "navigator.credentials.get = () => Promise.reject(new DOMException('no', 'NotAllowedError'))"
    page, _ = phone(init=NO_AUTOFILL + ";" + REMEMBER + ";" + cancel, sign_in=False)
    page.goto(f"{site}/signin")
    page.get_by_role("button", name="Sign in with Face ID").click()
    status = page.locator("#si-faceid-status")
    expect(status).to_contain_text("Face ID was cancelled. Use Continue with Google instead.")
    expect(status).to_have_class("si-note si-faceid-status is-bad")
    expect(page.locator("#si-faceid")).to_be_visible()   # the phone still has its passkey: try again
    no_sideways_scroll(page)


def test_a_successful_face_id_sign_in_remembers_the_phone(phone, site):
    page, ctx = phone(init=NO_AUTOFILL)
    add_from_family(page, site)
    page.evaluate("localStorage.removeItem('ga-faceid-on')")   # as if this phone only knew the passkey from the keychain
    ctx.clear_cookies()
    page.goto(f"{site}/signin?next=/family")
    expect(page.locator("#si-faceid")).to_be_hidden()
    page.evaluate("localStorage.setItem('ga-faceid-on', '1')")
    page.reload()
    page.get_by_role("button", name="Sign in with Face ID").click()
    page.wait_for_url(f"{site}/family")
    assert page.evaluate("localStorage.getItem('ga-faceid-on')") not in (None, "1")   # now holds the passkey's id


def test_setting_up_face_id_remembers_the_phone(phone, site):
    page, _ = phone(init=NO_AUTOFILL)
    add_from_family(page, site)
    assert page.evaluate("localStorage.getItem('ga-faceid-on')")


def test_a_phone_with_a_passkey_but_no_flag_gets_face_id_back_with_one_tap(phone, site):
    page, ctx = phone(init=NO_AUTOFILL)
    add_from_family(page, site)
    page.evaluate("localStorage.clear()")   # a phone from before the flag existed: signed in with Google, the server lists its passkey, the phone has no flag
    page.goto(f"{site}/family")   # the server excludes the passkey it knows, so the phone answers InvalidStateError ("already registered")
    page.get_by_role("button", name="Add another phone").click()
    expect(page.locator("#pk-done")).to_be_visible()
    expect(page.locator("#pk-done")).to_have_text("Face ID is on for this phone.")
    assert page.evaluate("localStorage.getItem('ga-faceid-on')") == "1"
    ctx.clear_cookies()
    page.goto(f"{site}/signin")
    expect(page.get_by_role("button", name="Sign in with Face ID")).to_be_visible()
