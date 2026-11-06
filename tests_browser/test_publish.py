"""F-181: publish a family trip as a creator page, in a real browser at phone (390) and laptop (1440) width: the editor (tap photos, a cover, notes, tips), the
preview, publish, what a signed-out stranger sees (photos load, notes, tips, "Plan this trip"), the creator profile and Community trips with the showcase off,
a signed-in stranger forking it, and unpublishing. Set F181_SHOTS=1 to save screenshots to docs/report/f181-*.png."""
import os
import re
from pathlib import Path

import pytest
from playwright.sync_api import expect

from tests.photo_files import image
from tests.test_trip_import import TEMPLATE
from tests_browser.helpers import DESKTOP, PHONE

SHOTS = Path(__file__).resolve().parent.parent / "docs" / "report"
NOTE, TIP = "Rope drop at 8 and the Matterhorn first.", "Bring a poncho for Splash Mountain season."


def shot(page, name):
    if os.getenv("F181_SHOTS"):
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f"f181-{name}.png"), full_page=True)


def overflow(page):
    return page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")


def sign_in(ctx, base_url, email):
    ctx.request.post(f"{base_url}/signin", form={"email": email, "next": "/", "intent": "save"}, max_redirects=0)


@pytest.fixture
def real(monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")


@pytest.fixture
def family(browser, base_url):
    """family(viewport) -> (page on /trip/publish, context). Ari has the imported LA trip, a plan and three photos (two on day 2, one on day 3), taken with a GPS position."""
    contexts = []

    def make(viewport=PHONE):
        ctx = browser.new_context(viewport=viewport, reduced_motion="reduce", has_touch=viewport is PHONE, is_mobile=viewport is PHONE)
        ctx.set_default_timeout(9000)
        contexts.append(ctx)
        sign_in(ctx, base_url, "ari.rivera@example.com")
        ctx.request.post(f"{base_url}/trips/import/save", form={"text": TEMPLATE}, max_redirects=0)
        ctx.request.post(f"{base_url}/trip/plans", form={"id": "a1", "day": "1", "start": "10:00", "title": "Rope drop at the park", "kind": "fun"}, max_redirects=0)
        for taken, color in (("2026:10:17 09:10:00", (200, 90, 60)), ("2026:10:17 14:20:00", (60, 120, 200)), ("2026:10:18 16:20:00", (90, 170, 90))):
            r = ctx.request.post(f"{base_url}/trip/photos", multipart={"photo": {"name": "p.jpg", "mimeType": "image/jpeg", "buffer": image("jpeg", size=(640, 480), color=color, taken=taken, gps=(33.81, -117.91))}},
                                 headers={"X-Fragment": "1"})
            assert r.ok, r.text()
        page = ctx.new_page()
        page.goto(f"{base_url}/trip/publish")
        return page, ctx

    yield make
    for c in contexts:
        c.close()


def fill_and_publish(page):
    tiles = page.locator(".pb-photo")
    expect(tiles).to_have_count(3)
    tiles.nth(0).click()
    tiles.nth(1).click()
    tiles.nth(2).click()
    page.locator(".pb-cover-b").nth(1).click()   # the second photo is the cover
    expect(page.locator(".pb-pick").nth(1)).to_be_checked()
    page.fill("#pb-title", "Our Disneyland week")
    page.fill("#pb-note-2", NOTE)
    page.locator("input[name=tip]").first.fill(TIP)
    page.get_by_text("Kid friendly").click()
    page.click("#pb-preview")
    expect(page.locator("#pb-pv")).to_be_visible()
    expect(page.locator("#pb-pv")).to_contain_text("exactly what strangers will see")
    page.click("#pb-publish")
    expect(page.locator("#pb-view")).to_be_visible()
    return page.locator("#pb-view").get_attribute("href")


def test_the_editor_on_the_phone_is_touch_sized_and_never_scrolls_sideways(family):
    page, _ = family(PHONE)
    expect(page.locator("h1")).to_have_text("Publish this trip")
    assert overflow(page) <= 1
    small = page.evaluate("""() => [...document.querySelectorAll('main button, main .btn, main label.pb-pill, main .pb-cover-b, main summary')]
        .filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && r.height < 40; }).map(e => e.textContent.trim().slice(0, 24))""")
    assert not small, f"under 40px tall: {small}"
    shot(page, "editor-phone")


def test_publish_from_the_phone_then_a_stranger_reads_it_and_it_comes_down(family, browser, base_url, real):
    page, ctx = family(PHONE)
    href = fill_and_publish(page)
    assert overflow(page) <= 1
    shot(page, "live-phone")
    page.goto(f"{base_url}/trip/publish/preview")
    shot(page, "preview-phone")
    assert overflow(page) <= 1

    stranger = browser.new_context(viewport=PHONE, has_touch=True, is_mobile=True, reduced_motion="reduce")
    p = stranger.new_page()
    p.goto(base_url + href)
    expect(p.locator("h1")).to_contain_text("Our Disneyland week")
    expect(p.get_by_text(NOTE)).to_be_visible()
    expect(p.get_by_text(TIP)).to_be_visible()
    expect(p.locator("a.by")).to_have_text("By Ari")
    plan = p.locator("#plan-this").first
    assert re.search(r"/plan\?.*to=la", plan.get_attribute("href"))
    imgs = p.locator(".day-photo img")
    expect(imgs).to_have_count(3)
    for i in range(3):
        imgs.nth(i).scroll_into_view_if_needed()
        assert imgs.nth(i).evaluate("i => i.complete && i.naturalWidth > 0")
    assert overflow(p) <= 1
    shot(p, "public-phone")

    p.click("a.by")
    expect(p.locator("h1")).to_have_text("Ari")
    assert overflow(p) <= 1
    shot(p, "profile-phone")
    p.goto(f"{base_url}/community")
    expect(p.locator(".hub-card")).to_have_count(1)
    assert overflow(p) <= 1
    shot(p, "community-phone")

    # a signed-in stranger forks it
    fan = browser.new_context(viewport=PHONE, has_touch=True, is_mobile=True, reduced_motion="reduce")
    sign_in(fan, base_url, "sam.fan@example.com")
    f = fan.new_page()
    f.goto(base_url + href)
    f.click("a.btn-primary.btn-hero")
    f.goto(f"{base_url}/forks")
    expect(f.locator("#fk-side")).to_contain_text("Our Disneyland week")
    fan.close()

    # unpublish: it is gone for the stranger, and the photo copy too
    copy = p.goto(base_url + href) and None
    src = p.locator(".day-photo img").first.get_attribute("src")
    page.goto(f"{base_url}/trip/publish")
    page.click("#pb-unpublish")
    page.click("#pb-unpublish-yes")
    expect(page.locator(".pb-chip")).to_contain_text("Draft")
    assert p.goto(base_url + href).status == 404
    assert p.goto(base_url + src).status == 404
    stranger.close()


def test_the_laptop_editor_preview_and_public_page_are_calm_and_fit(family, browser, base_url, real):
    page, ctx = family(DESKTOP)
    assert overflow(page) <= 1
    shot(page, "editor-laptop")
    href = fill_and_publish(page)
    shot(page, "live-laptop")
    stranger = browser.new_context(viewport=DESKTOP, reduced_motion="reduce")
    p = stranger.new_page()
    p.goto(base_url + href)
    expect(p.get_by_text(NOTE)).to_be_visible()
    assert overflow(p) <= 1
    shot(p, "public-laptop")
    p.goto(f"{base_url}/creators/ari")
    assert overflow(p) <= 1
    shot(p, "profile-laptop")
    p.goto(f"{base_url}/community")
    assert overflow(p) <= 1
    stranger.close()


def test_the_public_and_publish_pages_wear_the_coast_look_with_no_blur(family, browser, base_url, real):
    page, ctx = family(PHONE)
    href = fill_and_publish(page)
    stranger = browser.new_context(viewport=PHONE, reduced_motion="reduce")
    p = stranger.new_page()
    for path in ("/trip/publish", "/trip/publish/preview"):
        page.goto(base_url + path)
        look = page.evaluate("() => ({fam: document.documentElement.classList.contains('oq-family-travel'), blur: [...document.querySelectorAll('*')].some(e => { const s = getComputedStyle(e); return (s.backdropFilter && s.backdropFilter !== 'none') || (s.filter || '').includes('blur'); })})")
        assert look["fam"] and not look["blur"], path
    for path in (href, "/creators/ari", "/creators", "/community"):
        p.goto(base_url + path)
        look = p.evaluate("() => ({fam: document.documentElement.classList.contains('oq-family-travel'), accent: getComputedStyle(document.documentElement).getPropertyValue('--oq-accent').trim(), blur: [...document.querySelectorAll('*')].some(e => { const s = getComputedStyle(e); return (s.backdropFilter && s.backdropFilter !== 'none') || (s.filter || '').includes('blur'); })})")
        assert look["fam"] and look["accent"] == "#c0401c" and not look["blur"], path
    stranger.close()
