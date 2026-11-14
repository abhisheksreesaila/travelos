"""F-235: a creator pastes a popular post (The Planet D's "48 Hours in Lisbon", recorded: tests/fixtures/creator_import) and watches it become a trip: its title and lead picture appear as it is
read, its own sentences keep the wait company, then days and stops land one by one, then Publish. In headless Chromium at phone (390) and laptop (1440) width; the post's picture is served from the
recording, the model's answer from the recording. Set F235_SHOTS=1 to save docs/report/f235-*.png."""
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


def shot(page, name):
    if os.getenv("F235_SHOTS"):
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f"f235-{name}.png"), full_page=True)


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


def open_import(browser, base_url, viewport, **ctx):
    c = browser.new_context(viewport=viewport, has_touch=viewport is PHONE, is_mobile=viewport is PHONE, **ctx)
    c.set_default_timeout(9000)
    c.request.post(f"{base_url}/signin", form={"email": "maya.chen@example.com", "next": "/", "intent": "save"}, max_redirects=0)
    page = c.new_page()
    page.route("https://theplanetd.com/images/**", lambda r: r.fulfill(status=200, content_type="image/jpeg", body=(RECORDED / "lead.jpg").read_bytes()))
    page.goto(f"{base_url}/creators/import")
    return c, page


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=IDS)
def test_the_trip_is_made_in_front_of_the_creator_then_published(lisbon, browser, base_url, viewport):
    ctx, page = open_import(browser, base_url, viewport)
    page.fill("#ci-link", lisbon)
    page.click("#ci-draft")
    # while the model works: the post's own title and picture, its own sentences, no days yet
    expect(page.locator("#cm-title")).to_have_text("48 Hours in Lisbon, Itinerary")
    expect(page.locator(".cm-img.in")).to_be_visible()
    assert page.locator(".cm-img").evaluate("i => i.complete && i.naturalWidth > 0")
    expect(page.locator("#cm-by")).to_have_text("by The Planet D")
    assert page.locator(".cm-day").count() == 0 and page.locator("#cm-done").is_hidden()
    expect(page.locator("#cm-word")).to_contain_text("“")
    sentence = page.locator("#cm-word").inner_text().strip("“”")
    assert len(sentence) >= 30 and "http" not in sentence
    assert "is-on" in page.locator(".cm-step").nth(1).get_attribute("class")
    assert overflow(page) <= 1
    shot(page, f"import-reading-{viewport['width']}")
    # then the days and stops land
    expect(page.locator(".cm-day")).to_have_count(3)
    expect(page.locator(".cm-stop")).to_have_count(17)
    expect(page.locator(".cm-day-h").first).to_contain_text("Belem Tower")
    expect(page.locator("#cm-publish")).to_be_visible()
    expect(page.locator("#cm-count")).to_have_text("3 days, 17 stops in Lisbon, Portugal.")
    expect(page.locator(".cm-step.is-done")).to_have_count(3)
    expect(page.locator("#cm-log")).to_have_text("Laid out 3 days: 17 stops placed")
    assert overflow(page) <= 1
    if viewport is PHONE:
        small = page.evaluate("""() => [...document.querySelectorAll('#ci-magic .btn, #ci-magic .ci-own-l')].filter(e => { const r = e.getBoundingClientRect(); return r.height > 0 && r.height < 44; }).map(e => e.id)""")
        assert not small, small
    shot(page, f"import-landed-{viewport['width']}")
    # publish without the tick is not possible; with it, the trip is live (unlisted: the creator's email is not at the post's site)
    page.click("#cm-publish")
    assert page.locator("#cm-own").evaluate("e => !e.validity.valid")
    page.check("#cm-own")
    page.click("#cm-publish")
    expect(page.locator(".pb-live")).to_contain_text("It's live")
    expect(page.locator("#pb-view")).to_be_visible()
    shot(page, f"import-live-{viewport['width']}")
    ctx.close()


def test_with_reduced_motion_the_whole_trip_is_there_at_once(lisbon, browser, base_url):
    ctx, page = open_import(browser, base_url, PHONE, reduced_motion="reduce")
    page.fill("#ci-link", lisbon)
    page.click("#ci-draft")
    expect(page.locator("#cm-done")).to_be_visible()
    animated = page.evaluate("() => [...document.querySelectorAll('#ci-magic *')].filter(e => getComputedStyle(e).animationName !== 'none' && getComputedStyle(e).animationName !== '').map(e => e.className)")
    assert animated == []
    assert page.locator(".cm-stop").count() == 17
    ctx.close()


def test_a_refused_post_says_why_and_gives_the_form_back(lisbon, browser, base_url, monkeypatch):
    web = safefetch.TRANSPORT
    web.pages["https://theplanetd.com/robots.txt"] = (200, {"content-type": "text/plain"}, b"User-agent: *\nDisallow: /\n")
    ctx, page = open_import(browser, base_url, PHONE)
    page.fill("#ci-link", lisbon)
    page.click("#ci-draft")
    expect(page.locator("#ci-error")).to_contain_text("robots.txt asks AI tools not to read this page")
    expect(page.locator("#ci-form")).to_be_visible()
    expect(page.locator("#ci-link")).to_have_value(lisbon)
    assert page.locator("#ci-magic").is_hidden()
    ctx.close()
