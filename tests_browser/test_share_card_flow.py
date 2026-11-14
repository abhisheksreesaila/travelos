"""F-234: Share to Instagram on the Tahoe cockpit, in a real browser at 390 and 1440: the button is there and 48px on a phone; a tap grows the sheet out of it (GA.motion on a phone,
the calm fade on a laptop); the preview is the 1080 x 1350 card; the switches change it; the phone's Share hands the PNG to navigator.share; a laptop downloads it and copies the link;
the public page opens signed out and says nothing private. Screenshots: F234_SHOTS=<folder> pixi run pytest -p no:randomly tests_browser/test_share_card_flow.py -k screenshots"""

import os
import re

import pytest

from tests_browser.cockpit_support import open_cockpit
from tests_browser.helpers import DESKTOP, PHONE

SHARE_STUB = """(() => {
  window.__shared = [];
  navigator.canShare = (d) => !!(d && d.files && d.files.length && d.files[0].type === 'image/png');
  navigator.share = (d) => { window.__shared.push({ n: d.files[0].name, type: d.files[0].type, size: d.files[0].size, text: d.text }); return Promise.resolve(); };
  window.__copied = [];
  if (navigator.clipboard) navigator.clipboard.writeText = (t) => { window.__copied.push(t); return Promise.resolve(); };
})()"""


@pytest.fixture
def ctxs():
    made = []
    yield made
    for c in made:
        c.close()


@pytest.fixture
def cockpit(browser, base_url, monkeypatch, ctxs):
    def make(viewport=DESKTOP, stub=False, **kw):
        page = open_cockpit(browser, base_url, monkeypatch, ctxs, viewport=viewport, motion=True, **kw)
        if stub:
            page.add_init_script(SHARE_STUB)
            page.reload(wait_until="domcontentloaded")
            page.wait_for_selector("#ck-paper[data-ready='1']")
        return page
    return make


def open_sheet(page):
    page.click("#sh-open")
    page.wait_for_selector(".sh-box")
    page.wait_for_function("() => { const i = document.querySelector('#sh-img'); return i && i.complete && i.naturalWidth > 0; }")


def test_the_button_is_on_the_cockpit_on_a_phone_and_a_laptop(cockpit):
    for vp in (PHONE, DESKTOP):
        page = cockpit(viewport=vp)
        b = page.locator("#sh-open")
        assert b.is_visible() and b.inner_text().strip() == "Share to Instagram"
        assert b.bounding_box()["height"] >= (48 if vp is PHONE else 32)      # a phone's target is 48px (--target); a mouse needs less
        assert page.evaluate("() => document.documentElement.scrollWidth <= innerWidth")


def test_a_tap_opens_the_sheet_with_the_real_card_and_choices_off(cockpit):
    page = cockpit(viewport=PHONE)
    open_sheet(page)
    assert page.evaluate("() => [document.querySelector('#sh-img').naturalWidth, document.querySelector('#sh-img').naturalHeight]") == [1080, 1350]
    assert page.locator("input[name=names]").is_checked() is False and page.locator("input[name=exact]").is_checked() is False
    assert page.locator("#sh-link").input_value().startswith("https://gitaway.me/s/")
    assert page.url.endswith("/trip/cockpit") or "/trip/cockpit" in page.url      # the page did not navigate
    assert page.locator("#sh-open").get_attribute("aria-expanded") == "true"
    page.keyboard.press("Escape")
    page.wait_for_selector(".sh-box", state="detached")
    assert page.locator("#sh-open").get_attribute("aria-expanded") == "false"


def test_on_a_phone_the_sheet_grows_out_of_the_button_with_the_spring(cockpit):
    page = cockpit(viewport=PHONE)
    page.evaluate("() => { GA.motion.log.length = 0; }")
    open_sheet(page)
    log = page.evaluate("() => GA.motion.log.filter(m => m.kind === 'open').map(m => ({ from: m.from, easing: m.easing }))")
    assert log, "GA.motion.open was not called"
    box = page.locator("#sh-open").bounding_box()
    assert abs(log[0]["from"]["left"] - box["x"]) < 2 and abs(log[0]["from"]["top"] - box["y"]) < 2      # it grows from the button


def test_on_a_laptop_it_is_the_calm_fade_not_a_zoom(cockpit):
    page = cockpit(viewport=DESKTOP)
    page.evaluate("() => { GA.motion.log.length = 0; }")
    open_sheet(page)
    assert page.evaluate("() => GA.motion.calm()") is True
    assert page.evaluate("() => GA.motion.log.filter(m => m.kind === 'open').every(m => m.easing !== undefined)")


def test_a_switch_changes_the_card_and_the_link_stays(cockpit):
    page = cockpit(viewport=DESKTOP)
    open_sheet(page)
    before = page.locator("#sh-img").get_attribute("src")
    link = page.locator("#sh-link").input_value()
    page.locator("input[name=exact]").check(force=True)
    page.wait_for_function("(b) => document.querySelector('#sh-img').getAttribute('src') !== b", arg=before)
    page.wait_for_function("() => { const i = document.querySelector('#sh-img'); return i.complete && i.naturalWidth > 0; }")
    assert page.locator("#sh-link").input_value() == link
    assert page.locator("#sh-dl").get_attribute("href") == page.locator("#sh-img").get_attribute("src")


def test_the_phone_hands_the_card_to_its_share_sheet(cockpit):
    page = cockpit(viewport=PHONE, stub=True)
    open_sheet(page)
    page.wait_for_selector("#sh-share:not([hidden])")
    page.wait_for_timeout(300)      # the picture is fetched ahead; the tap runs inside the share
    page.click("#sh-share")
    page.wait_for_function("() => window.__shared.length === 1")
    shared = page.evaluate("() => window.__shared[0]")
    assert (shared["n"], shared["type"]) == ("trip-card.png", "image/png") and shared["size"] > 20000
    assert "Tahoe at Christmas" in shared["text"] and "/s/" in shared["text"]


def test_a_laptop_downloads_the_card_and_copies_the_link(cockpit):
    page = cockpit(viewport=DESKTOP, stub=True)
    open_sheet(page)
    page.evaluate("() => { document.querySelector('#sh-share').hidden = true; }")
    with page.expect_download() as d:
        page.click("#sh-dl")
    dl = d.value
    assert dl.suggested_filename == "trip-card.png"
    from PIL import Image
    assert Image.open(dl.path()).size == (1080, 1350)
    page.click("#sh-copy")
    page.wait_for_function("() => window.__copied.length === 1")
    assert page.evaluate("() => window.__copied[0]") == page.locator("#sh-link").input_value()
    assert page.locator("#sh-live").inner_text() == "Link copied."


def test_the_public_page_opens_signed_out(cockpit, browser, base_url, ctxs):
    page = cockpit(viewport=DESKTOP)
    open_sheet(page)
    link = page.locator("#sh-link").input_value().replace("https://gitaway.me", base_url)
    stranger = browser.new_context(viewport=PHONE)
    ctxs.append(stranger)
    p = stranger.new_page()
    p.goto(link, wait_until="domcontentloaded")
    assert p.locator("h1").inner_text() == "Tahoe at Christmas"
    body = p.inner_text("body")
    assert "8 days" in body and "December 2026" in body and re.search(r"\bAri\b|Kid 1|KQ7821|Hertz", body) is None
    assert p.evaluate("() => document.documentElement.scrollWidth <= innerWidth")


@pytest.mark.skipif(not os.environ.get("F234_SHOTS"), reason="screenshots only on request")
def test_screenshots(cockpit):
    out = os.environ["F234_SHOTS"]
    os.makedirs(out, exist_ok=True)
    for name, vp in (("390", PHONE), ("1440", DESKTOP)):
        page = cockpit(viewport=vp, fonts=True)
        page.screenshot(path=f"{out}/f234-{name}-cockpit-button.png")
        open_sheet(page)
        page.wait_for_timeout(900)
        page.screenshot(path=f"{out}/f234-{name}-sheet.png")
        page.locator("input[name=exact]").check(force=True)
        page.locator("input[name=names]").check(force=True)
        page.wait_for_timeout(1200)
        page.screenshot(path=f"{out}/f234-{name}-sheet-choices-on.png")
        if name == "1440":
            png = page.request.get(page.locator("#sh-img").evaluate("e => e.src"))
            open(f"{out}/f234-card.png", "wb").write(png.body())
