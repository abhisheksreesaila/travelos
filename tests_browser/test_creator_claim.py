"""F-188: the captain drafts a creator's post privately (laptop), copies the message, and the creator opens the claim link signed in as someone else (phone, 390), taps "This is my post — publish it"
and a stranger reads the public page. A real browser with a fake Claude and a fake web (the server runs in this process). F188_SHOTS=1 saves screenshots to docs/report/f188-*.png."""
import os
import re
from pathlib import Path

import pytest
from playwright.sync_api import expect

from gitaway import ai, safefetch
from tests.creator_import_support import ANSWER, Model, Web, page as html_page, picture
from tests_browser.helpers import DESKTOP, PHONE

SHOTS = Path(__file__).resolve().parent.parent / "docs" / "report"
POST = "https://blog.example.com/santa-monica-with-kids"
CAPTAIN = "captain.lee@example.com"
CLEAN = {**ANSWER, "days": [ANSWER["days"][0], {"stops": [ANSWER["days"][1]["stops"][0]]}]}


def shot(page, name):
    if os.getenv("F188_SHOTS"):
        page.wait_for_timeout(700)
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f"f188-{name}.png"), full_page=True)


def overflow(page):
    return page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")


def too_small(page, selector):
    return page.evaluate("""sel => [...document.querySelectorAll(sel)].filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && r.height < 40; })
        .map(e => (e.getAttribute('name') || e.id || e.textContent.trim()).slice(0, 30))""", selector)


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
        ctx = browser.new_context(viewport=viewport, has_touch=viewport is PHONE, is_mobile=viewport is PHONE)
        ctx.set_default_timeout(9000)
        contexts.append(ctx)
        if email:
            ctx.request.post(f"{base_url}/signin", form={"email": email, "next": "/", "intent": "save"}, max_redirects=0)
        return ctx

    yield make
    for c in contexts:
        c.close()


def test_the_captain_drafts_copies_the_message_and_the_creator_publishes_from_the_link(person, base_url):
    cap = person(DESKTOP, CAPTAIN)
    cap.grant_permissions(["clipboard-read", "clipboard-write"], origin=base_url)
    admin = cap.new_page()
    admin.goto(f"{base_url}/admin")
    expect(admin.locator("#cc-section h2").first).to_have_text("Draft for a creator")
    expect(admin.locator("#cc-made")).to_have_text("0")
    assert overflow(admin) <= 1
    shot(admin, "admin-1440")

    admin.fill("#cc-link", POST)
    admin.fill("#cc-name", "Maya Chen")
    admin.click("#cc-go")
    expect(admin.locator("#cc-msg-0")).to_be_visible()
    message = admin.locator("#cc-msg-0").input_value()
    assert message.startswith("Hi Maya,") and "Three easy days in Santa Monica" in message and message.rstrip().endswith("Captain")
    expect(admin.locator("#cc-made")).to_have_text("1")
    admin.click("#cc-msg-0-copy")
    expect(admin.locator("#ga-toast")).to_contain_text("Copied")
    assert admin.evaluate("navigator.clipboard.readText()") == message
    shot(admin, "admin-drafted-1440")
    path = re.search(r"https://gitaway\.me(/claim/[A-Za-z0-9_-]{43})", message).group(1)

    # the creator, on a phone, signed in as someone else
    me = person(PHONE, "maya.chen@example.com")
    p = me.new_page()
    p.goto(base_url + path)
    expect(p.locator("h1").first).to_have_text("Maya Chen, your post is ready as a trip")
    expect(p.locator("#cl-publish")).to_have_text("This is my post — publish it")
    expect(p.locator("#cl-edit")).to_have_text("Edit first")
    assert overflow(p) <= 1 and not too_small(p, "#cl-bar button, #cl-bar .btn")
    box = p.locator("#cl-publish").bounding_box()
    assert box["height"] >= 44 and box["width"] >= 300
    shot(p, "claim-390")
    p.check("#cl-confirm")
    p.tap("#cl-publish")
    expect(p.locator("#pb-view")).to_be_visible()
    shot(p, "live-390")
    href = p.locator("#pb-view").get_attribute("href")

    other = person(PHONE, "late.comer@example.com").new_page()                       # the same link again: already claimed
    other.goto(base_url + path)
    expect(other.locator("h1")).to_have_text("Already claimed")
    shot(other, "claimed-390")

    stranger = person(PHONE).new_page()
    stranger.goto(base_url + href)
    expect(stranger.locator("h1")).to_contain_text("Three easy days in Santa Monica")
    expect(stranger.get_by_text("From the blog")).to_be_visible()
    shot(stranger, "public-390")

    admin.reload()
    expect(admin.locator("#cc-claimed")).to_have_text("1")
    expect(admin.locator("#cc-published")).to_have_text("1")
    expect(admin.locator("#cc-goal")).to_have_text("1 of 150 creators published from drafts.")
    shot(admin, "admin-after-1440")


def test_the_admin_section_fits_a_phone_and_its_buttons_are_big_enough(person, base_url):
    cap = person(PHONE, CAPTAIN)
    page = cap.new_page()
    page.goto(f"{base_url}/admin")
    page.fill("#cc-link", POST)
    page.fill("#cc-name", "Maya Chen")
    page.tap("#cc-go")
    expect(page.locator("#cc-msg-0")).to_be_visible()
    page.tap("#cc-csv summary")
    expect(page.locator(".cc-pick").first).to_be_visible()
    assert overflow(page) <= 1
    assert not too_small(page, "#cc-section button, #cc-section .btn, #cc-section .cc-input, #cc-section .cc-pick, #cc-section summary")
    shot(page, "admin-drafted-390")
