"""F-206: the cover in a real browser. The poster shows at once, scrolling (and a finger on a phone) moves the story through its chapters, reduced
motion, no WebGL and a weak phone get the calm stills without ever asking for three.js, the live world loads and stops drawing when it is covered
or the tab is hidden, it gives up for the stills when even its lowest resolution is too slow, day and night follow the site, nothing scrolls
sideways, and a phone gets 16 px text and 48 px targets. 390 and 1440 wide, light and dark."""
import re

import pytest

from tests_browser.helpers import DESKTOP, PHONE

HEAVY = re.compile(r"/assets/vendor/three|/assets/js/cover/world\.js|/assets/cover/tahoe-")
SIZES = {"390": PHONE, "1440": DESKTOP}


@pytest.fixture
def cover(browser, base_url):
    made = []

    def open_cover(viewport=DESKTOP, scheme="light", motion="no-preference", init=None, query=""):
        phone = viewport["width"] < 760
        ctx = browser.new_context(viewport=viewport, color_scheme=scheme, reduced_motion=motion, has_touch=phone, is_mobile=phone)
        ctx.set_default_timeout(15000)
        made.append(ctx)
        page = ctx.new_page()
        page.requests = []
        page.on("request", lambda r: page.requests.append(r.url))
        if init:
            page.add_init_script(init)
        page.goto(f"{base_url}/{query}")
        return page

    yield open_cover
    for c in made:
        c.close()


def _heavy(page):
    return [u for u in page.requests if HEAVY.search(u)]


def _scroll_to_chapter(page, i):
    page.evaluate("i => { const a = window.GA_COVER.anchors()[i]; window.scrollTo(0, a.s + (a.e - a.s) * 0.5); }", i)
    page.wait_for_function(f"document.documentElement.dataset.cvChapter === '{i}'")


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("size", ["390", "1440"])
def test_the_poster_shows_at_once_for_day_or_night(cover, size, scheme):
    page = cover(SIZES[size], scheme, motion="reduce")
    layout = "phone" if size == "390" else "wide"
    want = f"/assets/cover/stills/a-0-{layout}-{scheme}.webp"
    page.wait_for_function(f"(() => {{ const im = document.querySelector('.cv-poster img'); return (im.currentSrc || im.src).endsWith('{want}') && im.complete && im.naturalWidth > 0; }})()", timeout=30000)
    assert page.evaluate(f"document.documentElement.classList.contains('cv-{scheme}')")
    assert page.eval_on_selector(".cv-poster img", "e => getComputedStyle(e).opacity") == "1"
    assert page.locator("h1").inner_text().replace("\n", " ").strip() == "Don’t read about it. Go."


@pytest.mark.parametrize("size", ["390", "1440"])
def test_scrolling_moves_the_story_through_every_chapter(cover, size):
    page = cover(SIZES[size], motion="reduce")
    page.wait_for_function("window.GA_COVER && window.GA_COVER.anchors().length === 7")
    for i in range(7):
        _scroll_to_chapter(page, i)
        assert page.locator(f'[data-chapter="{i}"]').get_attribute("class").split().count("is-on") == 1
        assert page.locator(".cv-ch.is-on").count() == 1
        if size == "1440":
            assert page.locator(".cv-rail button").nth(i).get_attribute("aria-current") == "step"
    assert page.locator(".cv-last h2").inner_text().replace("\n", " ").strip() == "Take a trip. Leave a trail."


def _swipe(page, cdp, x0, y0, x1, y1, steps=12):
    """A finger: touch start, a dozen moves a frame apart, touch end (the way a phone delivers it; synthetic scroll gestures do not scroll headless Chromium)."""
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x0, "y": y0}]})
    for k in range(1, steps + 1):
        cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x0 + (x1 - x0) * k / steps, "y": y0 + (y1 - y0) * k / steps}]})
        page.wait_for_timeout(16)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    page.wait_for_timeout(500)


def test_a_finger_scrolls_the_story_on_a_phone(cover):
    page = cover(PHONE, motion="reduce")
    page.wait_for_function("window.GA_COVER && window.GA_COVER.anchors().length === 7")
    cdp = page.context.new_cdp_session(page)
    for _ in range(4):
        _swipe(page, cdp, 195, 720, 195, 180)
    assert page.evaluate("scrollY") > 1500
    assert int(page.evaluate("document.documentElement.dataset.cvChapter")) >= 1
    # a swipe up that starts on the plan's widget row still scrolls the page; a swipe sideways scrolls the row
    _scroll_to_chapter(page, 3)
    box = page.locator('[data-chapter="3"] .cv-wds').bounding_box()
    cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    before = page.evaluate("scrollY")
    _swipe(page, cdp, cx, cy, cx, cy - 300)
    assert page.evaluate("scrollY") > before + 150
    _scroll_to_chapter(page, 3)
    box = page.locator('[data-chapter="3"] .cv-wds').bounding_box()
    cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    row = page.locator('[data-chapter="3"] .cv-wds')
    _swipe(page, cdp, cx + 120, cy, cx - 160, cy)
    assert row.evaluate("e => e.scrollLeft") > 60


@pytest.mark.parametrize("size", ["390", "1440"])
def test_reduced_motion_gets_the_stills_and_never_asks_for_three(cover, size):
    page = cover(SIZES[size], motion="reduce")
    assert page.evaluate("document.documentElement.classList.contains('cv-still')")
    layout = "phone" if size == "390" else "wide"
    page.wait_for_function("window.GA_COVER && window.GA_COVER.anchors().length === 7")
    for i in (1, 3, 6):
        _scroll_to_chapter(page, i)
        page.wait_for_function(f"(() => {{ const im = document.querySelector('.cv-stills img.on'); return im && im.src.endsWith('/a-{i}-{layout}-light.webp') && im.complete && im.naturalWidth > 0; }})()")
    page.wait_for_timeout(300)
    assert _heavy(page) == []
    assert page.locator(".cv-stage canvas.on").count() == 0
    _scroll_to_chapter(page, 3)
    assert page.locator('[data-chapter="3"] .cv-wds').is_visible()                    # the plan's widgets sit in the card


def test_without_webgl_the_stills_show_and_three_never_loads(cover):
    page = cover(DESKTOP, init="HTMLCanvasElement.prototype.getContext = function () { return null; };")
    page.wait_for_function("document.documentElement.classList.contains('cv-still')")
    page.wait_for_timeout(500)
    assert _heavy(page) == []


def test_a_weak_phone_gets_the_stills_without_downloading_the_world(cover):
    page = cover(PHONE, init="Object.defineProperty(navigator, 'deviceMemory', { get: () => 1 });")
    page.wait_for_function("document.documentElement.classList.contains('cv-still')")
    page.wait_for_timeout(500)
    assert _heavy(page) == []


def test_the_live_world_loads_draws_and_rests_when_covered_or_hidden(cover):
    page = cover({"width": 900, "height": 600}, query="?q=low")
    page.wait_for_function("document.documentElement.classList.contains('cv-ready')", timeout=60000)
    assert page.locator(".cv-stage canvas.on").count() == 1
    assert any("three.cover.min.js" in u for u in page.requests) and any("tahoe-lo.bin.gz" in u for u in page.requests)
    page.wait_for_function("window.__cover && window.__cover.running")
    frame = page.evaluate("window.__cover.S.renderer.info.render.frame")
    page.wait_for_function(f"window.__cover.S.renderer.info.render.frame > {frame + 2}")
    # the closing screen covers the whole stage: the loop stops
    page.evaluate("document.querySelector('.cv-close').scrollIntoView({ block: 'start' })")
    page.wait_for_function("!window.__cover.running")
    frame = page.evaluate("window.__cover.S.renderer.info.render.frame")
    page.wait_for_timeout(400)
    assert page.evaluate("window.__cover.S.renderer.info.render.frame") == frame
    # back into the story it draws again; a hidden tab stops it
    _scroll_to_chapter(page, 6)
    page.wait_for_function("window.__cover.running")
    page.evaluate("() => { Object.defineProperty(document, 'hidden', { configurable: true, get: () => true }); document.dispatchEvent(new Event('visibilitychange')); }")
    page.wait_for_function("!window.__cover.running")
    page.evaluate("() => { Object.defineProperty(document, 'hidden', { configurable: true, get: () => false }); document.dispatchEvent(new Event('visibilitychange')); }")
    page.wait_for_function("window.__cover.running")


def test_a_device_too_slow_even_at_the_lowest_resolution_gets_the_stills(cover):
    page = cover({"width": 900, "height": 600}, query="?q=low")
    page.wait_for_function("document.documentElement.classList.contains('cv-ready')", timeout=60000)
    scales = page.evaluate("""() => { const g = window.__cover.loop.gov, out = []; g.t = 10;
      for (let k = 0; k < 40 && !g.done; k++) { for (let i = 0; i < 45; i++) g.feed(0.06); out.push(g.scale); } return out; }""")
    assert scales[0] < 1 and min(scales) == pytest.approx(0.55, abs=0.01)          # the pixel ratio steps down first
    page.wait_for_function("document.documentElement.classList.contains('cv-still')")
    assert not page.evaluate("window.__cover.running") and page.locator(".cv-stage canvas.on").count() == 0


def test_day_or_night_follows_the_sites_own_switch(cover):
    page = cover(DESKTOP, "light", motion="reduce")
    assert page.evaluate("document.documentElement.classList.contains('cv-light')")
    page.evaluate("document.documentElement.dataset.theme = 'dark'")
    page.wait_for_function("document.documentElement.classList.contains('cv-dark')")
    page.wait_for_function("document.querySelector('.cv-poster img').src.endsWith('a-0-wide-dark.webp')")
    page.evaluate("delete document.documentElement.dataset.theme")
    page.wait_for_function("document.documentElement.classList.contains('cv-light')")
    page.emulate_media(color_scheme="dark")
    page.wait_for_function("document.documentElement.classList.contains('cv-dark')")
    assert page.evaluate("getComputedStyle(document.body).backgroundColor") == "rgb(0, 0, 0)"


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("width", [1440, 1280, 1000, 800, 390, 320])
def test_nothing_scrolls_sideways(cover, width, scheme):
    page = cover({"width": width, "height": 844 if width < 760 else 900}, scheme, motion="reduce")
    page.wait_for_function("window.GA_COVER && window.GA_COVER.anchors().length === 7")
    for i in (0, 3, 6):
        _scroll_to_chapter(page, i)
        assert page.evaluate("document.documentElement.scrollWidth") <= page.evaluate("document.documentElement.clientWidth"), (width, i)


def test_a_phone_reads_16px_text_and_taps_48px_targets(cover):
    page = cover(PHONE, motion="reduce")
    page.wait_for_function("window.GA_COVER && window.GA_COVER.anchors().length === 7")
    small = page.evaluate("""() => [...document.querySelectorAll('.cv-card p, .cv-card li, .cv-lede, .cv-foot p:not(.cv-fine), .cv-btn, .cv-foot nav a, .cv-wd span:not(.k), .cv-wd b')]
      .filter(e => e.getClientRects().length && !e.closest('.cv-anchors'))
      .map(e => [e.textContent.trim().slice(0, 30), parseFloat(getComputedStyle(e).fontSize)]).filter(([, s]) => s < 16)""")
    assert small == []
    eyebrows = page.evaluate("() => [...document.querySelectorAll('.cv-eyebrow, .cv-wd .k')].map(e => parseFloat(getComputedStyle(e).fontSize))")
    assert min(eyebrows) >= 13                                                        # all-caps labels only
    targets = page.evaluate("""() => [...document.querySelectorAll('.cv-top a, .cv-ctas a, .cv-foot nav a, .cv-close .pf-card a')]
      .filter(e => e.getClientRects().length).map(e => [e.textContent.trim(), e.getBoundingClientRect().height])""")
    assert len(targets) >= 6 and all(h >= 48 for _, h in targets), targets


@pytest.mark.parametrize("label,path", [("Start a trip", "/start"), ("Leave a trail", "/for-creators"), ("See trips people shared", "/community")])
def test_each_door_at_the_end_opens_its_page(cover, base_url, label, path):
    page = cover(DESKTOP, motion="reduce")
    page.wait_for_function("window.GA_COVER && window.GA_COVER.anchors().length === 7")
    _scroll_to_chapter(page, 6)
    page.locator(".cv-ctas a", has_text=label).click()
    page.wait_for_url(f"{base_url}{path}")
    assert page.locator("main").count() >= 1
