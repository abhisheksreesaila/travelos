"""F-190: a creator pastes their blog's address on the import page, ticks posts from the list, and watches "My drafts" fill in on its own while a background worker drafts them one at a time.
In a real browser at phone (390) and laptop (1440) width, with a fake Claude (slow, so the drafting state can be seen) and a fake web; the server and its worker thread run in this process.
Set F190_SHOTS=1 to save screenshots to docs/report/f190-*.png."""
import os
import time
from pathlib import Path

import pytest
from playwright.sync_api import expect

from gitaway import ai, draftjobs, safefetch
from tests.creator_import_support import Model, Web, page as html_page
from tests_browser.helpers import DESKTOP, PHONE

SHOTS = Path(__file__).resolve().parent.parent / "docs" / "report"
SITE = "https://blog.example.com"
SLUGS = ["three-days-in-san-diego-with-kids", "disneyland-itinerary-for-toddlers", "my-favourite-pancakes"]
SITEMAP = ('<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
           + "".join(f"<url><loc>{SITE}/{s}</loc><lastmod>2025-0{i + 4}-1{i}</lastmod></url>" for i, s in enumerate(SLUGS)) + "</urlset>")
IDS = ["390", "1440"]


class SlowModel(Model):
    def __call__(self, kwargs, timeout):
        time.sleep(2.5)
        return super().__call__(kwargs, timeout)


def shot(page, name):
    if os.getenv("F190_SHOTS"):
        page.wait_for_timeout(700)      # let the page-change motion settle
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f"f190-{name}.png"), full_page=True)


def overflow(page):
    return page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")


def too_small(page, selector):
    return page.evaluate("""sel => [...document.querySelectorAll(sel)].filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && r.height < 40; })
        .map(e => (e.getAttribute('name') || e.id || e.textContent.trim()).slice(0, 30))""", selector)


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-a-real-key")
    monkeypatch.setattr(ai, "ANTHROPIC_TRANSPORT", SlowModel())
    monkeypatch.setattr(safefetch, "TRANSPORT", Web({f"{SITE}/sitemap.xml": (200, {"content-type": "application/xml"}, SITEMAP.encode()), **{f"{SITE}/{s}": html_page() for s in SLUGS}}))
    draftjobs.start(poll=0.2)         # the app's own startup does this; make sure the worker is up whichever test ran first
    yield
    draftjobs.stop()


@pytest.fixture
def creator(browser, base_url):
    contexts = []

    def make(viewport):
        ctx = browser.new_context(viewport=viewport, has_touch=viewport is PHONE, is_mobile=viewport is PHONE)
        ctx.set_default_timeout(20000)
        contexts.append(ctx)
        ctx.request.post(f"{base_url}/signin", form={"email": "maya.chen@example.com", "next": "/", "intent": "save"}, max_redirects=0)
        return ctx

    yield make
    for c in contexts:
        c.close()


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=IDS)
def test_find_my_posts_tick_some_and_watch_them_become_drafts(setup, creator, base_url, viewport):
    w = viewport["width"]
    page = creator(viewport).new_page()
    page.goto(f"{base_url}/creators/import")
    expect(page.locator("#cdr-bulk")).to_contain_text("Import several posts")
    assert overflow(page) <= 1
    if viewport is PHONE:
        assert not too_small(page, "#cdr-bulk button, #cdr-bulk .btn, #cdr-bulk input")
    shot(page, f"import-{w}")

    page.fill("#cdr-bulk #cdr-site", SITE)
    page.click("#cdr-bulk #cdr-find")
    expect(page.locator("h1")).to_have_text("Pick your posts")
    expect(page.locator(".cdr-t")).to_have_text(["Three days in san diego with kids", "Disneyland itinerary for toddlers", "My favourite pancakes"])
    expect(page.locator("#cdr-left")).to_have_text("You can have 20 more posts drafted today, up to 20 at a time.")
    expect(page.locator("#cdr-go")).to_be_disabled()
    expect(page.locator("#cdr-count")).to_have_text("0 ticked")
    assert overflow(page) <= 1
    if viewport is PHONE:
        assert not too_small(page, "main .cdr-pick, main button, main .btn")
    page.locator(".cdr-pick").nth(0).click()
    page.locator(".cdr-pick").nth(1).click()
    expect(page.locator("#cdr-count")).to_have_text("2 ticked")
    expect(page.locator("#cdr-go")).to_be_enabled()
    shot(page, f"pick-{w}")

    page.click("#cdr-go")
    page.wait_for_url("**/creators/drafts?queued=2")
    expect(page.locator("#cdr-queued")).to_have_text("Drafting 2 posts in the background.")
    expect(page.locator("#cdr-list")).to_have_attribute("data-busy", "1")
    expect(page.locator(".cdr-drafting").first).to_be_visible()
    assert overflow(page) <= 1
    shot(page, f"drafting-{w}")

    # nothing reloads the page: the list asks the server every few seconds and fills itself in
    marker = page.evaluate("window.__stay = 1")
    expect(page.locator("#cdr-list")).to_have_attribute("data-busy", "0", timeout=30000)
    expect(page.locator(".cdr-ready")).to_have_count(2)
    expect(page.locator("#cdr-busy")).to_have_count(0)
    assert page.evaluate("window.__stay") == 1 and marker == 1
    assert overflow(page) <= 1
    if viewport is PHONE:
        assert not too_small(page, "main .cdr-acts .btn, main .cdr-acts summary, main a.cdr-name")
    shot(page, f"ready-{w}")

    page.locator(".cdr-acts .btn", has_text="Open").first.click()
    expect(page.locator("h1")).to_have_text("Check your draft")
    page.go_back()
    expect(page.locator(".cdr-item")).to_have_count(2)
    page.locator(".cdr-del summary").first.click()
    page.locator(".cdr-del .pb-unpub-yes").first.click()
    expect(page.locator(".cdr-item")).to_have_count(1)
    assert overflow(page) <= 1


def test_a_blog_with_nothing_to_read_says_so_on_the_page(setup, creator, base_url, monkeypatch):
    gone = (404, {"content-type": "text/html"}, b"")
    monkeypatch.setattr(safefetch, "TRANSPORT", Web({f"{SITE}/sitemap.xml": gone, SITE + "/": html_page("<html></html>"), SITE + "/feed": gone}))
    page = creator(PHONE).new_page()
    page.goto(f"{base_url}/creators/drafts/scan")
    page.fill("#cdr-site", SITE)
    page.click("#cdr-find")
    expect(page.locator("#cdr-err")).to_contain_text("could not find a list of posts")
    expect(page.locator("#cdr-site")).to_have_value(SITE)
    assert overflow(page) <= 1
