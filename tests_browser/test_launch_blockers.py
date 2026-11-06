"""F-194: the screens the launch-blocker fixes added, in a real browser at phone (390) and laptop (1440) width: a claim link's read-only preview before sign-in (and its sign-in button), a claim by
someone not at the post's site (unlisted, the captain approves it from the waiting list), the captain editing a pre-draft before he sends it, and the tick a page that names a child waits for."""
import re

import pytest
from playwright.sync_api import expect

from gitaway import ai, safefetch
from tests.creator_import_support import ANSWER, Model, Web, page as html_page, picture
from tests.test_trip_import import TEMPLATE
from tests_browser.helpers import DESKTOP, PHONE

POST = "https://blog.example.com/santa-monica-with-kids"
CAPTAIN = "captain.lee@example.com"
STRANGER = "kim.lee@gmail.com"
CLEAN = {**ANSWER, "days": [ANSWER["days"][0], {"stops": [ANSWER["days"][1]["stops"][0]]}]}
SIZES = pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["390", "1440"])


def overflow(page):
    return page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-a-real-key")
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setenv("GITAWAY_ADMIN_EMAILS", CAPTAIN)
    monkeypatch.setattr(ai, "ANTHROPIC_TRANSPORT", Model(CLEAN))
    monkeypatch.setattr(safefetch, "TRANSPORT", Web({POST: html_page(), "https://blog.example.com/img/pier.jpg": picture(), "https://blog.example.com/img/canals.jpg": picture("png"),
                                                    "https://blog.example.com/img/cover.jpg": picture()}))


@pytest.fixture
def person(browser, base_url):
    contexts = []

    def make(viewport, email=""):
        ctx = browser.new_context(viewport=viewport, has_touch=viewport is PHONE, is_mobile=viewport is PHONE, reduced_motion="reduce")
        ctx.set_default_timeout(9000)
        contexts.append(ctx)
        if email:
            ctx.request.post(f"{base_url}/signin", form={"email": email, "next": "/", "intent": "save"}, max_redirects=0)
        return ctx

    yield make
    for c in contexts:
        c.close()


@pytest.fixture
def drafted(person, base_url):
    """The captain (laptop) drafts the post: returns (the captain's page on /admin, the claim path)."""
    admin = person(DESKTOP, CAPTAIN).new_page()
    admin.goto(f"{base_url}/admin")
    admin.fill("#cc-link", POST)
    admin.fill("#cc-name", "Maya Chen")
    admin.click("#cc-go")
    expect(admin.locator("#cc-msg-0")).to_be_visible()
    return admin, re.search(r"https://gitaway\.me(/claim/[A-Za-z0-9_-]{43})", admin.locator("#cc-msg-0").input_value()).group(1)


@SIZES
def test_a_claim_link_shows_the_trip_before_sign_in_and_its_button_goes_to_sign_in(person, base_url, drafted, viewport):
    _admin, path = drafted
    p = person(viewport).new_page()
    p.goto(base_url + path)
    expect(p.locator("h1").first).to_have_text("Maya Chen, your post is ready as a trip")
    expect(p.get_by_text("Santa Monica Pier").first).to_be_visible()
    assert p.locator("#cl-publish").count() == 0 and overflow(p) <= 1
    if viewport is PHONE:
        assert p.locator("#cl-signin").bounding_box()["height"] >= 43
    p.locator("#cl-signin").click() if viewport is DESKTOP else p.tap("#cl-signin")
    p.wait_for_url(re.compile(r".*/signin\?next=/claim/.*"))
    assert "intent=publish" in p.url


@SIZES
def test_a_claim_by_someone_elsewhere_is_unlisted_until_the_captain_approves_it(person, base_url, drafted, viewport):
    admin, path = drafted
    me = person(viewport, STRANGER).new_page()
    me.goto(base_url + path)
    expect(me.locator("#cl-held")).to_have_text("Your sign-in email is not at blog.example.com, so the captain looks at the trip before it is listed.")
    me.check("#cl-confirm")
    me.locator("#cl-publish").click() if viewport is DESKTOP else me.tap("#cl-publish")
    expect(me.locator(".pb-live")).to_contain_text("It is published but unlisted")
    slug = re.search(r"/trips/([a-z0-9-]+)", me.locator("#pb-view").get_attribute("href")).group(1)

    seen = person(viewport).new_page()
    seen.goto(f"{base_url}/trips/{slug}")
    expect(seen.locator("meta[name=robots]")).to_have_attribute("content", "noindex, nofollow")
    assert seen.locator(".src-by").inner_text() == "blog.example.com · Blog"            # the byline names the site, not the person, until the captain says yes

    admin.reload()
    expect(admin.locator("#ad-waiting li")).to_have_count(1)
    expect(admin.locator(f"#wait-state-{slug}")).to_have_text("Unlisted until you approve it")
    admin.locator(f"#wait-{slug} form[action='/admin/approve'] button").click()
    expect(admin.locator("#ad-waiting-sec")).to_have_count(0)
    seen.reload()
    expect(seen.locator("meta[name=robots]")).to_have_count(0)
    assert seen.locator(".src-by").inner_text() == "Maya Chen · Blog"
    assert "Maya Chen" in person(viewport).new_page().goto(f"{base_url}/creators").text()


def test_the_captain_edits_a_pre_draft_before_he_sends_it(person, base_url, drafted):
    admin, path = drafted
    admin.click(".cc-review")
    admin.wait_for_url(re.compile(r".*/admin/drafts/[0-9a-f]{16}$"))
    expect(admin.locator("h1")).to_have_text("Check this pre-draft")
    assert admin.locator("#ci-pics").count() == 0 and overflow(admin) <= 1
    admin.fill("#ci-title", "Santa Monica, checked by the captain")
    admin.click("#pb-save")
    expect(admin.locator("#ci-title")).to_have_value("Santa Monica, checked by the captain")
    creator = person(PHONE).new_page()
    creator.goto(base_url + path)
    expect(creator).to_have_title(re.compile("Santa Monica, checked by the captain"))
    admin.click("#pb-back-admin")
    admin.wait_for_url(re.compile(r".*/admin#cc-section$"))


@SIZES
def test_a_page_that_names_a_child_waits_for_the_tick(person, base_url, viewport):
    ctx = person(viewport, "ari.rivera@example.com")
    ctx.request.post(f"{base_url}/trips/import/save", form={"text": TEMPLATE.replace("name: Kid 1", "name: Mira Rivera")}, max_redirects=0)
    p = ctx.new_page()
    p.goto(f"{base_url}/trip/publish")
    p.fill("#pb-title", "Our Disneyland week")
    p.fill("#pb-note-2", "Mira loved the teacups.")
    p.click("#pb-preview")
    expect(p.locator("#pb-warn")).to_have_text("It mentions Mira from your family. Check they're happy to be on a public page.")
    expect(p.locator(".pb-names-t")).to_have_text("Yes, Mira is happy to be named")
    p.click("#pb-publish")
    expect(p.locator("#pb-error")).to_have_text("This page names Mira from your family. Tick the box to say they are happy to be on a public page, then publish.")
    p.check("#pb-names-ok")
    p.click("#pb-publish")
    expect(p.locator("#pb-view")).to_be_visible()
