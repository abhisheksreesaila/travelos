"""F-235, F-253: a creator pastes a popular post (The Planet D's "48 Hours in Lisbon", recorded through the app's own safe fetcher and robots check: tests/fixtures/creator_import), watches it
become a trip (the post's card grows with its title and lead picture, its own sentences arrive highlighted, the days and stops land under the story line, "Your guide is ready"), opens the book,
turns its pages, fixes a word in place and publishes it, and a stranger reads it. In headless Chromium at phone (390) and laptop (1440) width; the post's picture is served from the recording, the
model's answer from the recording. Set F253_SHOTS=1 to save docs/report/f253-*.png (the prototype-vs-build screenshots are made by scripts/f253_shots.py)."""
import os
import time
from pathlib import Path

import pytest
from playwright.sync_api import expect

from gitaway import ai, safefetch
from tests.creator_import_support import RECORDED, Model, recorded
from tests_browser.helpers import DESKTOP, PHONE

SHOTS = Path(__file__).resolve().parent.parent / "docs" / "report"
IDS = ["390", "1440"]
expect.set_options(timeout=30000)      # the days land one by one, as slowly as a person reads (the recorded model waits 2.5 s first)


def shot(page, name):
    if os.getenv("F253_SHOTS"):
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f"f253-{name}.png"), full_page=True)


def overflow(page):
    return page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")


class Slow(Model):
    """The recorded answer, after a pause: the page has to wait for the model, so what it shows while waiting can be looked at."""

    def __call__(self, kwargs, timeout):
        time.sleep(2.5)
        return super().__call__(kwargs, timeout)


@pytest.fixture
def lisbon(monkeypatch):
    url, web, answer = recorded()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-a-real-key")
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setattr(ai, "ANTHROPIC_TRANSPORT", Slow(answer))
    monkeypatch.setattr(safefetch, "TRANSPORT", web)
    return url


def open_import(browser, base_url, viewport, path="/creators/import", **ctx):
    c = browser.new_context(viewport=viewport, has_touch=viewport is PHONE, is_mobile=viewport is PHONE, **ctx)
    c.set_default_timeout(30000)
    c.request.post(f"{base_url}/signin", form={"email": "maya.chen@example.com", "next": "/", "intent": "save"}, max_redirects=0)
    page = c.new_page()
    page.route("https://theplanetd.com/images/**", lambda r: r.fulfill(status=200, content_type="image/jpeg", body=(RECORDED / "lead.jpg").read_bytes()))
    page.goto(f"{base_url}{path}")
    return c, page


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=IDS)
def test_the_post_becomes_a_guide_that_is_opened_fixed_and_published(lisbon, browser, base_url, viewport):
    ctx, page = open_import(browser, base_url, viewport, "/guides/make")
    page.click("#fc-example-chip")
    expect(page.locator("#fc-text")).to_have_value(lisbon)       # the example chip is the real post the fixture records
    page.click("#fc-draft")
    # while the model works: the post's own title, site and picture, its own sentences highlighted, no days yet
    expect(page.locator("#postT")).to_have_text("48 Hours in Lisbon, Itinerary")
    expect(page.locator("#postCard.pic")).to_be_visible()
    assert page.locator("#postImg").evaluate("i => i.complete && i.naturalWidth > 0")
    expect(page.locator("#postBy")).to_have_text("by The Planet D")
    expect(page.locator("#postSite")).to_have_text("theplanetd.com")
    expect(page.locator("#postOk")).to_be_visible()
    expect(page.locator("#river .snt q").first).to_contain_text("")
    assert page.locator("#days .dayb").count() == 0 and page.locator("#ready").is_hidden()
    sentence = page.locator("#river .snt q").first.inner_text().strip("“”")
    assert len(sentence) >= 30 and "http" not in sentence
    assert overflow(page) <= 1
    shot(page, f"import-reading-{viewport['width']}")
    # then the days and stops land, the sentences that name a stop are tagged with it, and the book is ready
    expect(page.locator("#days .dayb")).to_have_count(3)
    expect(page.locator("#ready")).to_be_visible()
    expect(page.locator("#itinCount")).to_have_text("17 stops")
    expect(page.locator("#days .pc")).to_have_count(17)
    expect(page.locator("#readyLine")).to_have_text("3 days · 17 stops · 4 tips, from your post")
    river = page.locator("#river").inner_text()      # the last six: the post's own sentence, then the stop it names
    assert "Located near Pena Palace is The Moorish Castle." in river and "Day 3 · Moorish Castle" in river
    assert overflow(page) <= 1
    shot(page, f"import-ready-{viewport['width']}")
    page.click("#openBook")
    # the guide: the run sheet of the post's own words, the day strip, a card per stop
    page.wait_for_url("**/guide")
    expect(page.locator("h1 .ed")).to_have_text("48 hours in Lisbon")
    expect(page.locator(".dbtn")).to_have_count(3)
    expect(page.locator(".g-card")).to_have_count(17)
    assert overflow(page) <= 1
    shot(page, f"guide-owner-{viewport['width']}")
    # a stop opens its details: a panel beside the sheet on a laptop, a sheet over it on a phone; the arrow keys step through the stops
    page.locator(".g-chev.g-open").first.click()
    expect(page.locator("#g-panel")).to_be_visible()
    expect(page.locator("#g-pbody h2")).to_have_text("Belem Tower")
    expect(page.locator("#g-pbody .g-words p")).to_contain_text("admired it from the outside")
    expect(page.locator("#g-pbody .g-tipbox")).to_contain_text("Go to Belém Tower before the crowds.")
    shot(page, f"guide-stop-{viewport['width']}")
    page.keyboard.press("ArrowDown")
    expect(page.locator("#g-pbody h2")).to_have_text("Jerónimos Monastery")
    expect(page.locator(".g-pk")).to_have_text("Sight")
    page.click("#g-close")
    expect(page.locator("#g-panel")).to_be_hidden()
    # a word fixed in place, kept by the server
    word = page.locator('[data-k="d0.head"]')
    word.click()
    page.keyboard.press("Control+A")
    page.keyboard.type("A better heading")
    page.keyboard.press("Enter")
    expect(page.locator("#toast")).to_contain_text("Fixed in the postcard")
    # Publish: the tick first, then the link, the Instagram card and the badge
    page.click("#pubBtn")
    expect(page.locator("#pubGo")).to_be_disabled()
    page.click("#mine")
    page.click("#pubGo")
    expect(page.locator("#sharep")).to_be_visible()
    expect(page.locator("#sharep")).to_contain_text("Your postcard is out")
    link = page.locator("#shLink").inner_text()
    assert link.startswith("gitaway.me/trips/") and not link.endswith("/book")
    assert 'src="https://gitaway.me/badge/plan-this-trip.svg"' in page.locator("#shCode").inner_text()
    expect(page.locator("#shCard")).to_have_attribute("src", f"/trips/{link.split('/trips/')[1]}/card.png")
    page.wait_for_function("document.getElementById('shCard').complete && document.getElementById('shCard').naturalWidth === 1080")
    shot(page, f"guide-published-{viewport['width']}")
    # a stranger opens it: the same guide, as a reader's, with Plan this trip and no editing
    reader = browser.new_context(viewport=viewport)
    rp = reader.new_page()
    rp.goto(f"{base_url}/trips/{link.split('/trips/')[1]}")
    expect(rp.locator("#gpage")).to_have_attribute("data-mode", "reader")
    expect(rp.locator("#g-day1 h2")).to_have_text("A better heading")
    assert rp.locator(".ed").count() == 0 and rp.locator("[data-k].ed").count() == 0
    expect(rp.locator("#g-plan")).to_have_attribute("href", "/plan/ask")
    reader.close()
    ctx.close()


def test_with_reduced_motion_the_whole_trip_is_there_at_once(lisbon, browser, base_url):
    ctx, page = open_import(browser, base_url, PHONE, reduced_motion="reduce")
    page.fill("#ci-link", lisbon)
    page.click("#ci-draft")
    expect(page.locator("#ready")).to_be_visible()
    still = page.evaluate("() => [...document.querySelectorAll('#imp *')].filter(e => { const s = getComputedStyle(e); return s.animationName !== 'none' && parseFloat(s.animationDuration) > 0; }).map(e => e.className)")
    assert still == []
    assert page.locator("#days .pc").count() == 17
    ctx.close()


def test_a_refused_post_says_why_and_gives_the_form_back(lisbon, browser, base_url):
    web = safefetch.TRANSPORT
    web.pages["https://theplanetd.com/robots.txt"] = (200, {"content-type": "text/plain"}, b"User-agent: *\nDisallow: /\n")
    ctx, page = open_import(browser, base_url, PHONE)
    page.fill("#ci-link", lisbon)
    page.click("#ci-draft")
    expect(page.locator("#ci-error")).to_contain_text("robots.txt asks AI tools not to read this page")
    expect(page.locator("#ci-form")).to_be_visible()
    expect(page.locator("#ci-link")).to_have_value(lisbon)
    assert page.locator("#imp").is_hidden()
    ctx.close()


def test_a_retry_after_a_cut_short_stream_starts_clean(lisbon, browser, base_url):
    """The first answer is cut after "read" (a dropped connection); the retry must not show the first attempt's title, ticks or days, and must end with the right three days."""
    ctx, page = open_import(browser, base_url, PHONE)
    calls = []

    def first_cut_then_real(route):
        calls.append(1)
        if len(calls) == 1:
            line = '{"event": "read", "title": "First attempt", "by": "Nobody", "image": "", "site": "first.example", "kind": "blog", "chars": 10, "words": ["The first attempt read this sentence of the post."]}\n'
            route.fulfill(status=200, content_type="application/x-ndjson", body=line)
        else:
            route.continue_()

    page.route("**/creators/import", first_cut_then_real, times=2)
    page.fill("#ci-link", lisbon)
    page.click("#ci-draft")
    expect(page.locator("#ci-error")).to_contain_text("The draft was cut short")
    expect(page.locator("#ci-form")).to_be_visible()
    page.click("#ci-draft")
    expect(page.locator("#postT")).to_have_text("48 Hours in Lisbon, Itinerary")      # not "First attempt"
    assert page.locator("#postSite").inner_text().lower() == "theplanetd.com"
    assert page.locator("#ci-error").count() == 0
    expect(page.locator("#days .dayb")).to_have_count(3)
    expect(page.locator("#itinCount")).to_have_text("17 stops")
    expect(page.locator("#readyLine")).to_have_text("3 days · 17 stops · 4 tips, from your post")
    ctx.close()
