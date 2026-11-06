"""F-183: a creator pastes a link, watches a calm skeleton, reviews the draft, fixes an unsure stop, picks a picture, ticks "This is my post" and publishes; a stranger then reads it with the source
link back. In a real browser at phone (390) and laptop (1440) width, with a fake Claude and a fake web (the server runs in this process). Set F183_SHOTS=1 to save screenshots to docs/report/f183-*.png."""
import os
import re
from pathlib import Path

import pytest
from playwright.sync_api import expect

from gitaway import ai, safefetch
from tests.creator_import_support import Model, Web, page as html_page, picture
from tests_browser.helpers import DESKTOP, PHONE

SHOTS = Path(__file__).resolve().parent.parent / "docs" / "report"
POST = "https://blog.example.com/santa-monica-with-kids"
IDS = ["390", "1440"]


def shot(page, name):
    if os.getenv("F183_SHOTS"):
        page.wait_for_timeout(700)      # let the page-change motion settle
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f"f183-{name}.png"), full_page=True)


def overflow(page):
    return page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")


def too_small(page, selector):
    """Controls under 40px tall (44px is the target on the phone's 16px root; the laptop's root is 12px)."""
    return page.evaluate("""sel => [...document.querySelectorAll(sel)].filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && r.height < 40; })
        .map(e => (e.getAttribute('name') || e.id || e.textContent.trim()).slice(0, 30))""", selector)


def press_draft_without_leaving(page):
    """Press "Draft my trip" the way the page's script sees it (a submit with the button as its submitter) but stop the browser from leaving: while a navigation is pending Playwright cannot read or
    screenshot the old page, so this is the only way to look at the skeleton. The real press, through to the editor, is the rest of the test."""
    page.evaluate("""() => { const f = document.getElementById('ci-form'); f.addEventListener('submit', e => e.preventDefault()); f.requestSubmit(document.getElementById('ci-draft')); }""")


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-a-real-key")
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")      # the live site: nothing is published yet, and the import must still be reachable
    monkeypatch.setattr(ai, "ANTHROPIC_TRANSPORT", Model())
    monkeypatch.setattr(safefetch, "TRANSPORT", Web({POST: html_page(), "https://blog.example.com/img/pier.jpg": picture(taken="2026:03:20 10:30:00", gps=(34.0094, -118.4973)),
                                                    "https://blog.example.com/img/canals.jpg": picture("png"), "https://blog.example.com/img/cover.jpg": picture()}))


@pytest.fixture
def creator(browser, base_url):
    contexts = []

    def make(viewport):
        ctx = browser.new_context(viewport=viewport, has_touch=viewport is PHONE, is_mobile=viewport is PHONE)
        ctx.set_default_timeout(9000)
        contexts.append(ctx)
        ctx.request.post(f"{base_url}/signin", form={"email": "maya.chen@example.com", "next": "/", "intent": "save"}, max_redirects=0)
        return ctx

    yield make
    for c in contexts:
        c.close()


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=IDS)
def test_paste_a_link_review_the_draft_publish_and_a_stranger_reads_it(setup, creator, browser, base_url, viewport):
    ctx = creator(viewport)
    page = ctx.new_page()
    page.goto(f"{base_url}/creators/import")
    expect(page.locator("h1")).to_have_text("Turn your post into a trip")
    assert overflow(page) <= 1
    if viewport is PHONE:
        assert not too_small(page, "main button:not(.sr-only), main .btn, main input:not([type=hidden]), main textarea")
    shot(page, f"paste-{viewport['width']}")

    page.fill("#ci-link", POST)
    press_draft_without_leaving(page)
    expect(page.locator("#ci-skel")).to_be_visible()       # the calm skeleton while the model works
    expect(page.locator("#ci-skel")).to_contain_text("Reading your post and drafting the days")
    expect(page.locator("#ci-form")).to_be_hidden()
    assert overflow(page) <= 1
    shot(page, f"skeleton-{viewport['width']}")
    page.reload()
    expect(page.locator("#ci-skel")).to_be_hidden()
    page.fill("#ci-link", POST)
    page.click("#ci-draft")
    expect(page.locator("h1")).to_have_text("Check your draft")
    assert overflow(page) <= 1
    if viewport is PHONE:
        assert not too_small(page, "main button:not(.sr-only), main .btn, main input:not([type=hidden]):not(.sr-only), main select, main textarea, main summary")
    expect(page.locator("#ci-source a")).to_have_attribute("href", POST)
    expect(page.locator("#ci-unsure")).to_contain_text("1 stop GitAway was not sure of is marked")
    expect(page.locator("input[name=d0s0_name]")).to_have_value("Santa Monica Pier")
    expect(page.locator("input[name=d1s1_name]")).to_have_value("Unnamed stop")
    shot(page, f"editor-{viewport['width']}")

    page.fill("input[name=d1s1_name]", "Pacific Park")                   # fix what GitAway was not sure of
    page.fill("#ci-name", "Maya Chen")
    page.click("button[value='add_stop:0']")                            # the add-a-stop button adds a row and keeps what was typed
    expect(page.locator("input[name=d0s2_name]")).to_have_value("")
    expect(page.locator("input[name=d1s1_name]")).to_have_value("Pacific Park")
    page.fill("input[name=d0s2_name]", "Carousel")
    page.click("button[value='del_stop:0:1']")                           # and the remove button takes that row out
    expect(page.locator("input[name=d0s1_name]")).to_have_value("Carousel")
    page.locator(".pb-photo").nth(1).click()                            # one of the post's pictures, by tapping it
    expect(page.locator(".pb-pick").nth(1)).to_be_checked()
    page.click("#pb-preview")
    expect(page.locator("#pb-pv")).to_contain_text("exactly what strangers will see")
    expect(page.locator(".source-card .src-link")).to_have_attribute("href", POST)
    assert overflow(page) <= 1
    shot(page, f"preview-{viewport['width']}")

    page.click("#pb-publish")                                            # without "This is my post" it must not publish
    expect(page.locator("#pb-error")).to_contain_text("This is my post")
    page.check("#ci-own")
    page.click("#pb-publish")
    expect(page.locator("#pb-view")).to_be_visible()
    href = page.locator("#pb-view").get_attribute("href")
    shot(page, f"live-{viewport['width']}")

    stranger = browser.new_context(viewport=viewport, has_touch=viewport is PHONE, is_mobile=viewport is PHONE)
    p = stranger.new_page()
    p.goto(base_url + href)
    expect(p.locator("h1")).to_contain_text("Three easy days in Santa Monica")
    expect(p.locator("#day-2 .stop-title", has_text="Pacific Park")).to_be_visible()
    expect(p.get_by_text("From the blog")).to_be_visible()
    link = p.locator(".source-card .src-link")
    expect(link).to_have_attribute("href", POST)
    expect(link).to_have_text("Read the original post")
    img = p.locator(".polaroid img").first
    img.scroll_into_view_if_needed()
    assert img.evaluate("i => i.complete && i.naturalWidth > 0")        # the public copy of the picked picture loads
    assert overflow(p) <= 1
    shot(p, f"public-{viewport['width']}")
    stranger.close()


def test_the_skeleton_is_still_and_the_form_still_works_with_reduced_motion(setup, browser, base_url):
    ctx = browser.new_context(viewport=PHONE, reduced_motion="reduce", has_touch=True, is_mobile=True)
    ctx.set_default_timeout(9000)
    ctx.request.post(f"{base_url}/signin", form={"email": "maya.chen@example.com", "next": "/", "intent": "save"}, max_redirects=0)
    page = ctx.new_page()
    page.goto(f"{base_url}/creators/import")
    page.fill("#ci-text", "Day 1 Santa Monica Pier at 10:00 AM and the Third Street Promenade. Day 2 Venice Canals.")
    press_draft_without_leaving(page)
    expect(page.locator("#ci-skel")).to_be_visible()
    page.reload()
    page.fill("#ci-text", "Day 1 Santa Monica Pier at 10:00 AM and the Third Street Promenade. Day 2 Venice Canals.")
    page.click("#ci-draft")
    expect(page.locator("h1")).to_have_text("Check your draft")
    ctx.close()


def test_not_switched_on_yet_is_friendly_and_the_text_editor_still_works(browser, base_url, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    ctx = browser.new_context(viewport=PHONE, has_touch=True, is_mobile=True)
    ctx.set_default_timeout(9000)
    ctx.request.post(f"{base_url}/signin", form={"email": "maya.chen@example.com", "next": "/", "intent": "save"}, max_redirects=0)
    page = ctx.new_page()
    page.goto(f"{base_url}/creators/import")
    expect(page.locator("#ci-off")).to_have_text("Drafting from a link is not switched on yet. You can still paste your text and write the trip yourself.")
    page.fill("#ci-text", "Day 1 Santa Monica Pier. Day 2 Venice Canals.")
    page.click("#ci-manual")
    expect(page.locator("h1")).to_have_text("Check your draft")
    expect(page.locator("#ci-pasted")).to_contain_text("Day 1 Santa Monica Pier")
    page.fill("#ci-title", "My two days")
    page.fill("input[name=d0s0_name]", "Santa Monica Pier")
    page.click("#pb-save")
    expect(page.locator("#ci-title")).to_have_value("My two days")
    assert overflow(page) <= 1
    ctx.close()
