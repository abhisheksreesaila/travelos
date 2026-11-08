"""F-206, the agreed story (D-354): the cover in a real browser. The poster shows at once, scrolling (and a finger on a phone) moves the story
through its eleven scenes, every window's card fits between the header and the bottom of the screen (a landscape phone and a 768-tall laptop
too) and every paper scene's headline starts below the header, each feature's real screenshot loads only as it nears the screen and in the
visitor's layout and mode (the site's own switch too), the world plays the right stretch of its timeline in each window and rests under a paper
scene, reduced motion, no WebGL and a weak phone get the calm stills without ever asking for three.js, the live world loads and stops drawing when
it is covered or the tab is hidden, it gives up for the stills (and gives the GPU back) when even its lowest resolution is too slow, day and night
follow the site, nothing scrolls sideways, a phone gets 16 px text and 48 px targets, a notch never covers anything, the words read at full
strength in both modes, and production ignores the tools' switches. 390 and 1440 wide, light and dark."""
import hashlib
import re
from pathlib import Path

import pytest

from gitaway.pages import cover as cover_page
from tests_browser.helpers import DESKTOP, PHONE

ROOT = Path(__file__).resolve().parent.parent
HEAVY = re.compile(r"/assets/vendor/three|/assets/js/cover/world\.js|/assets/cover/tahoe-")
SHOT = re.compile(r"/assets/cover/shots/")
SIZES = {"390": PHONE, "1440": DESKTOP}
N = 11                                         # the story's scenes (tests/test_cover.py STORY)
WINDOWS = (0, 1, 7, 10)                        # the scenes where the world shows through
PAPERS = (2, 3, 4, 5, 6, 8, 9)                 # the scenes with a screenshot
# a phone with enough memory for the live world but too few cores to count as strong: it gets the lightest tier without ?q
MODEST_PHONE = "Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 4 });"
READY = f"window.GA_COVER && window.GA_COVER.scenes().length === {N}"


@pytest.fixture
def cover(browser, base_url):
    made = []

    def open_cover(viewport=DESKTOP, scheme="light", motion="no-preference", init=None, query="", stub_world=False, insets=None):
        phone = viewport["width"] < 760 or viewport["height"] < 520
        ctx = browser.new_context(viewport=viewport, color_scheme=scheme, reduced_motion=motion, has_touch=phone, is_mobile=phone)
        ctx.set_default_timeout(15000)
        made.append(ctx)
        page = ctx.new_page()
        page.requests = []
        page.on("request", lambda r: page.requests.append(r.url))
        if init:
            page.add_init_script(init)
        if stub_world:                                    # the live page without the world: an empty module, so the page stays live and loads fast
            page.route(re.compile(r"/assets/js/cover/world\.js"), lambda r: r.fulfill(status=200, content_type="text/javascript", body="export {};"))
        if insets:                                        # a notch: what env(safe-area-inset-*) reports on an iPhone on its side
            page.context.new_cdp_session(page).send("Emulation.setSafeAreaInsetsOverride", {"insets": insets})
        page.goto(f"{base_url}/{query}")
        return page

    yield open_cover
    for c in made:
        c.close()


def _heavy(page):
    return [u for u in page.requests if HEAVY.search(u)]


def _scroll_to_scene(page, i, at=0.5):
    page.evaluate("([i, at]) => { const t = window.GA_COVER.scenes()[i]; window.scrollTo(0, t.s + (t.e - t.s) * at); }", [i, at])
    page.wait_for_function(f"document.documentElement.dataset.cvScene === '{i}'")


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("size", ["390", "1440"])
def test_the_poster_shows_at_once_for_day_or_night(cover, size, scheme):
    page = cover(SIZES[size], scheme, motion="reduce")
    layout = "phone" if size == "390" else "wide"
    want = f"/assets/cover/stills/a-0-{layout}-{scheme}.webp"
    page.wait_for_function(f"(() => {{ const im = document.querySelector('.cv-poster img'); return (im.currentSrc || im.src).endsWith('{want}') && im.complete && im.naturalWidth > 0; }})()", timeout=30000)
    assert page.evaluate(f"document.documentElement.classList.contains('cv-{scheme}')")
    assert page.eval_on_selector(".cv-poster img", "e => getComputedStyle(e).opacity") == "1"
    assert page.locator("h1").inner_text().replace("\n", " ").strip() == "Planning a trip shouldn’t feel like homework."


@pytest.mark.parametrize("size", ["390", "1440"])
def test_scrolling_moves_the_story_through_every_scene(cover, size):
    page = cover(SIZES[size], motion="reduce")
    page.wait_for_function(READY)
    for i in range(N):
        _scroll_to_scene(page, i)
        if size == "1440":
            assert page.locator(".cv-rail button").nth(i).get_attribute("aria-current") == "step"
    assert page.locator(".cv-last h2").inner_text().replace("\n", " ").strip() == "Take a trip. Leave a trail."


def test_each_window_plays_its_stretch_of_the_world_and_a_paper_scene_covers_it(cover):
    """The why is the guidebook (the world's chapter 0), Lena and Sam's lake its chapter 1, the pier at sunset chapter 4 and the fork tree chapter
    6; while a paper scene fills the screen the world is covered and told to rest."""
    page = cover(DESKTOP, motion="reduce")
    page.wait_for_function(READY)
    for i, chapter in zip(WINDOWS, (0, 1, 4, 6)):
        _scroll_to_scene(page, i, 0.7)
        st = page.evaluate("GA_COVER.state()")
        assert int(st["exact"] // 2) == chapter and page.evaluate("GA_COVER.visible"), (i, st)      # where the scroll puts the world (its camera eases after it)
    for i in PAPERS:
        _scroll_to_scene(page, i, 0)
        page.evaluate("window.scrollBy(0, 2)")
        page.wait_for_function("!GA_COVER.visible")


CARD = """i => { const el = document.querySelector(i === 0 ? '.cv-hero-copy' : `[data-scene="${i}"] .cv-card`), r = el.getBoundingClientRect();
  const head = Math.max(...[...document.querySelectorAll('.cv-top, .cv-top > *')].map((e) => e.getBoundingClientRect().bottom));
  return { top: r.top, bottom: r.bottom, left: r.left, right: r.right, head, vh: innerHeight, hidden: el.scrollHeight - el.clientHeight }; }"""
WORDS = """i => { const el = document.querySelector(`[data-scene="${i}"] .cv-words`), r = el.getBoundingClientRect(), s = el.closest('section').getBoundingClientRect();
  const head = Math.max(...[...document.querySelectorAll('.cv-top, .cv-top > *')].map((e) => e.getBoundingClientRect().bottom));
  return { top: r.top - s.top, left: r.left, right: r.right, head }; }"""


@pytest.mark.parametrize("how", ["live", "stills"])
@pytest.mark.parametrize("size", [(844, 390), (1366, 768), (320, 568)], ids=["844x390", "1366x768", "320x568"])
def test_every_card_fits_between_the_header_and_the_bottom_of_the_screen(cover, size, how):
    """A landscape phone and a 768-tall laptop read every window whole: no card runs under the header or off the bottom, and none hides words
    behind its own scroll; a paper scene's words start below the header."""
    w, h = size
    page = cover({"width": w, "height": h}, motion="reduce" if how == "stills" else "no-preference", stub_world=how == "live")
    page.wait_for_function(READY)
    assert page.evaluate("document.documentElement.classList.contains('cv-live')") == (how == "live")
    for i in WINDOWS:
        _scroll_to_scene(page, i)
        box = page.evaluate(CARD, i)
        assert box["head"] - 0.5 <= box["top"] and box["bottom"] <= box["vh"] + 0.5, (i, box)
        assert box["hidden"] <= 1, (i, box)
    page.evaluate("window.scrollTo(0, 0)")
    for i in PAPERS:
        box = page.evaluate(WORDS, i)
        assert box["top"] >= box["head"] - 0.5, (i, box)


def test_a_notch_never_covers_the_header_a_card_or_the_closing_screen(cover):
    """An iPhone on its side: the notch and the rounded corners take 47 px each side (viewport-fit=cover hands that space to the page)."""
    page = cover({"width": 844, "height": 390}, motion="reduce", insets={"left": 47, "right": 47, "top": 0, "bottom": 21})
    page.wait_for_function(READY)
    clear = "sel => [...document.querySelectorAll(sel)].filter(e => e.getClientRects().length).map(e => { const r = e.getBoundingClientRect(); return [e.className || e.tagName, Math.round(r.left), Math.round(r.right)]; })"
    for i in WINDOWS:
        _scroll_to_scene(page, i)
        box = page.evaluate(CARD, i)
        assert box["left"] >= 47 and box["right"] <= 844 - 47, (i, box)
    boxes = page.evaluate(clear, ".cv-top > *, .cv-words, .cv-frame")
    page.evaluate("document.querySelector('.cv-close').scrollIntoView({ block: 'end' })")
    boxes += page.evaluate(clear, ".cv-close .pf-card, .cv-foot > *, .cv-foot nav a")
    assert len(boxes) >= 20 and all(l >= 47 and r <= 844 - 47 for _, l, r in boxes), boxes


@pytest.mark.parametrize("size", ["390", "1440"])
def test_the_skip_link_shows_above_the_header_when_tabbed_to(cover, size):
    page = cover(SIZES[size], motion="reduce")
    page.keyboard.press("Tab")
    assert page.evaluate("document.activeElement.classList.contains('ga-skip')")
    assert page.evaluate("""() => { const r = document.querySelector('.ga-skip').getBoundingClientRect(), e = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
      return !!(e && e.closest('.ga-skip')); }""")


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
    page.wait_for_function(READY)
    cdp = page.context.new_cdp_session(page)
    for _ in range(4):
        _swipe(page, cdp, 195, 720, 195, 180)
    assert page.evaluate("scrollY") > 1500
    assert int(page.evaluate("document.documentElement.dataset.cvScene")) >= 1
    # a swipe that starts on a screenshot scrolls the page too
    _scroll_to_scene(page, 3, 0)
    box = page.locator('[data-scene="3"] .cv-shot').bounding_box()
    before = page.evaluate("scrollY")
    cx, cy = box["x"] + box["width"] / 2, min(box["y"] + 60, 760)
    _swipe(page, cdp, cx, cy, cx, cy - 300)
    assert page.evaluate("scrollY") > before + 150


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("size", ["390", "1440"])
def test_each_screenshot_loads_as_it_nears_in_the_visitors_layout_and_mode(cover, size, scheme):
    page = cover(SIZES[size], scheme, motion="reduce")
    page.wait_for_function(READY)
    page.wait_for_timeout(400)
    assert not [u for u in page.requests if SHOT.search(u) and "-trail-" in u]          # far below the fold: not yet
    layout = "phone" if size == "390" else "wide"
    want = "600" if layout == "phone" else "1440|960"
    for i, name in zip(PAPERS, ("plan", "cockpit", "day", "ask", "family", "trail", "creators")):
        _scroll_to_scene(page, i, 0)
        page.wait_for_function(f"""(() => {{ const im = document.querySelector('[data-scene="{i}"] .cv-shot img');
          return im.complete && im.naturalWidth > 0 && /\\/{name}-{layout}-{scheme}-({want})\\.webp$/.test(im.currentSrc); }})()""")
    got = [u for u in page.requests if SHOT.search(u)]
    assert all(f"-{layout}-{scheme}-" in u for u in got), got


def test_the_screenshots_follow_the_sites_own_switch(cover):
    page = cover(PHONE, "light", motion="reduce")
    page.wait_for_function(READY)
    page.evaluate("document.documentElement.dataset.theme = 'dark'")
    page.wait_for_function("document.documentElement.classList.contains('cv-dark')")
    _scroll_to_scene(page, 5, 0)
    page.wait_for_function("""(() => { const im = document.querySelector('[data-scene="5"] .cv-shot img');
      return im.complete && im.naturalWidth > 0 && im.currentSrc.endsWith('/ask-phone-dark-600.webp'); })()""")


@pytest.mark.parametrize("size", ["390", "1440"])
def test_reduced_motion_gets_the_stills_and_never_asks_for_three(cover, size):
    page = cover(SIZES[size], motion="reduce")
    assert page.evaluate("document.documentElement.classList.contains('cv-still')")
    layout = "phone" if size == "390" else "wide"
    page.wait_for_function(READY)
    for i, still in ((1, 1), (7, 4), (10, 6)):
        _scroll_to_scene(page, i, 0.7)
        page.wait_for_function(f"(() => {{ const im = document.querySelector('.cv-stills img.on'); return im && im.src.endsWith('/a-{still}-{layout}-light.webp') && im.complete && im.naturalWidth > 0; }})()")
    page.wait_for_timeout(300)
    assert _heavy(page) == []
    assert page.locator(".cv-stage canvas.on").count() == 0


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
    lo = hashlib.sha256((ROOT / "assets/cover/tahoe-lo.bin.gz").read_bytes()).hexdigest()[:10]
    assert any("three.cover.min.js?v=" in u for u in page.requests) and any(u.endswith(f"/assets/cover/tahoe-lo.bin.gz?v={lo}") for u in page.requests)
    page.wait_for_function("window.__cover && window.__cover.running")
    frame = page.evaluate("window.__cover.S.renderer.info.render.frame")
    page.wait_for_function(f"window.__cover.S.renderer.info.render.frame > {frame + 2}")
    # a paper scene covers the whole stage: the loop stops
    _scroll_to_scene(page, 3, 0)
    page.evaluate("window.scrollBy(0, 2)")
    page.wait_for_function("!window.__cover.running")
    frame = page.evaluate("window.__cover.S.renderer.info.render.frame")
    page.wait_for_timeout(400)
    assert page.evaluate("window.__cover.S.renderer.info.render.frame") == frame
    # the next window draws again; the closing screen stops it; a hidden tab stops it
    _scroll_to_scene(page, 7, 0.6)
    page.wait_for_function("window.__cover.running")
    page.evaluate("document.querySelector('.cv-close').scrollIntoView({ block: 'start' })")
    page.wait_for_function("!window.__cover.running")
    _scroll_to_scene(page, 10)
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
    assert page.evaluate("window.__cover.S.renderer.getContext().isContextLost()")         # and the GPU's memory is given back


def test_switching_day_and_night_does_not_pile_up_guidebooks(cover):
    """Each switch builds the guidebook again for the new light; the old one's geometry and textures are freed, not left on the GPU."""
    page = cover({"width": 900, "height": 600}, query="?q=low")
    page.wait_for_function("document.documentElement.classList.contains('cv-ready')", timeout=60000)
    page.wait_for_function("window.__cover && window.__cover.running")

    def switch(theme):
        page.evaluate(f"document.documentElement.dataset.theme = '{theme}'")
        frame = page.evaluate("window.__cover.S.renderer.info.render.frame")
        page.wait_for_function(f"window.__cover.S.renderer.info.render.frame > {frame + 3}")
        return page.evaluate("(() => { const m = window.__cover.S.renderer.info.memory; return [m.geometries, m.textures]; })()")

    switch("dark")
    before = switch("light")
    for theme in ("dark", "light", "dark", "light"):
        after = switch(theme)
    assert after == before


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
    page.wait_for_function(READY)
    for i in (0, 2, 5, 9, 10):
        _scroll_to_scene(page, i)
        assert page.evaluate("document.documentElement.scrollWidth") <= page.evaluate("document.documentElement.clientWidth"), (width, i)


def test_a_phone_reads_16px_text_and_taps_48px_targets(cover):
    page = cover(PHONE, motion="reduce")
    page.wait_for_function(READY)
    small = page.evaluate("""() => [...document.querySelectorAll('.cv-card p, .cv-lede, .cv-say, .cv-tabs li, .cv-foot p, .cv-btn, .cv-foot nav a')]
      .filter(e => e.getClientRects().length && !e.closest('.cv-anchors'))
      .map(e => [e.textContent.trim().slice(0, 30), parseFloat(getComputedStyle(e).fontSize)]).filter(([, s]) => s < 16)""")
    assert small == []
    eyebrows = page.evaluate("() => [...document.querySelectorAll('.cv-eyebrow')].map(e => parseFloat(getComputedStyle(e).fontSize))")
    assert len(eyebrows) == N and min(eyebrows) >= 13                                # all-caps labels only
    targets = page.evaluate("""() => [...document.querySelectorAll('.cv-top a, .cv-ctas a, .cv-foot nav a, .cv-close .pf-card a')]
      .filter(e => e.getClientRects().length).map(e => [e.textContent.trim(), e.getBoundingClientRect().height])""")
    assert len(targets) >= 6 and all(h >= 48 for _, h in targets), targets


def test_a_landscape_tablet_taps_48px_scene_buttons(cover):
    page = cover({"width": 1024, "height": 768}, motion="reduce")
    page.wait_for_function(READY)
    sizes = page.evaluate("() => [...document.querySelectorAll('.cv-rail button')].map(b => { const r = b.getBoundingClientRect(); return [r.width, r.height]; })")
    assert len(sizes) == N and all(w >= 48 and h >= 48 for w, h in sizes), sizes


def test_a_scene_button_takes_you_to_its_scene(cover):
    page = cover(DESKTOP, motion="reduce")
    page.wait_for_function(READY)
    page.locator(".cv-rail button").nth(6).click()
    page.wait_for_function("document.documentElement.dataset.cvScene === '6'")


@pytest.mark.parametrize("size", ["390", "1440"])
def test_the_footer_links_sit_at_least_8px_apart(cover, size):
    page = cover(SIZES[size], motion="reduce")
    page.evaluate("document.querySelector('.cv-foot').scrollIntoView({ block: 'end' })")
    gaps = page.evaluate("""() => { const r = [...document.querySelectorAll('.cv-foot nav a')].map(a => a.getBoundingClientRect()), out = [];
      for (let i = 1; i < r.length; i++) if (Math.abs(r[i].top - r[i - 1].top) < 2) out.push(r[i].left - r[i - 1].right); return out; }""")
    assert gaps and min(gaps) >= 8, gaps


@pytest.mark.parametrize("width", [390, 360, 320])
def test_a_phone_shows_the_early_preview_label_beside_the_logo_and_sign_in(cover, width):
    """The honest label stays on a phone, the logo whole (D-61); on the narrowest phones it takes a short second row under the logo."""
    page = cover({"width": width, "height": 700}, motion="reduce")
    assert page.locator(".cv-tag").is_visible() and page.locator(".cv-top .ga-brand-name").is_visible()
    boxes = page.evaluate("() => [...document.querySelectorAll('.cv-top > *')].map(e => { const r = e.getBoundingClientRect(); return [e.className.split(' ')[0], r.left, r.top, r.right, r.bottom]; })")
    assert sorted(b[0] for b in boxes) == ["cv-btn", "cv-tag", "ga-brand"]
    assert all(0 <= l and r <= width for _, l, _, r, _ in boxes), boxes
    for i, (_, l0, t0, r0, b0) in enumerate(boxes):
        for _, l1, t1, r1, b1 in boxes[i + 1:]:
            assert r0 <= l1 or r1 <= l0 or b0 <= t1 or b1 <= t0, boxes                  # never on top of one another


CONTRAST = """sel => { const lin = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
  const rgb = (s) => s.match(/[\\d.]+/g).map(Number), L = ([r, g, b]) => 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b), out = [];
  const bgOf = (e) => { for (; e; e = e.parentElement) { const c = rgb(getComputedStyle(e).backgroundColor); if (c.length < 4 || c[3] > 0.99) { if (c.length < 4 || c[3] > 0) return c.slice(0, 3); } } return [255, 255, 255]; };
  for (const el of document.querySelectorAll(sel)) {
    if (!el.textContent.trim() || !el.getClientRects().length) continue;
    const fg = rgb(getComputedStyle(el).color).slice(0, 3), bg = bgOf(el), l1 = L(fg), l2 = L(bg);
    out.push([el.textContent.trim().slice(0, 24), (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05)]);
  }
  return out; }"""


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_every_headline_and_its_words_read_at_full_strength(cover, scheme):
    """Each scene's headline sits on an opaque surface, never on the world itself: the cards over the world and the paper scenes, in both modes."""
    page = cover(DESKTOP, scheme, motion="reduce")
    page.wait_for_function(READY)
    ratios = page.evaluate(CONTRAST, ".cv-card h2, .cv-card p, .cv-paper h2, .cv-say, .cv-lede, .cv-eyebrow, .cv-hero h1")
    assert len(ratios) >= 30 and min(r for _, r in ratios) >= 4.5, sorted(ratios, key=lambda x: x[1])[:4]
    for i in WINDOWS[1:]:
        assert page.evaluate(f"""(() => {{ const c = getComputedStyle(document.querySelector('[data-scene="{i}"] .cv-card')).backgroundColor; return !/rgba\\(.*, 0(\\.\\d+)?\\)$/.test(c); }})()""")


def test_the_worlds_labels_pass_under_the_cards(cover):
    page = cover(DESKTOP, stub_world=True)
    page.wait_for_function(READY)
    _scroll_to_scene(page, 1)
    assert page.evaluate("""() => { const probe = document.createElement('div'); probe.className = 'cv-lbl'; probe.style.cssText = 'opacity:1;visibility:visible;pointer-events:auto;width:2000px;height:2000px';
      document.querySelector('.cv-anchors').appendChild(probe);
      const r = document.querySelector('[data-scene="1"] .cv-card h2').getBoundingClientRect(), e = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
      return !!(e && e.closest('.cv-card')); }""")


def test_production_ignores_the_tools_switches(cover, monkeypatch):
    """Without data-debug (production), ?measure no longer lets a weak phone download the world and ?q no longer picks the tier."""
    monkeypatch.setattr(cover_page, "debug", lambda: False)
    page = cover(PHONE, init="Object.defineProperty(navigator, 'deviceMemory', { get: () => 1 });", query="?measure&q=high&cam=0,0,0,1,1,1,40&shot=4")
    page.wait_for_function("document.documentElement.classList.contains('cv-still')")
    page.wait_for_timeout(500)
    assert _heavy(page) == []
    assert page.evaluate("[GA_COVER.tier, ['measure', 'capture', 'q', 'cam', 'shot'].some((k) => GA_COVER.Q.has(k))]") == ["low", False]


def test_in_production_the_world_keeps_its_insides_to_itself(cover, monkeypatch):
    monkeypatch.setattr(cover_page, "debug", lambda: False)
    page = cover(PHONE, init=MODEST_PHONE)
    page.wait_for_function("document.documentElement.classList.contains('cv-ready')", timeout=60000)
    assert page.evaluate("GA_COVER.tier") == "low"
    assert page.evaluate("[typeof window.__cover, typeof window.__frames, typeof window.__work]") == ["undefined"] * 3


@pytest.mark.parametrize("label,path", [("Start a trip", "/start"), ("Leave a trail", "/for-creators"), ("See trips people shared", "/community")])
def test_each_door_at_the_end_opens_its_page(cover, base_url, label, path):
    page = cover(DESKTOP, motion="reduce")
    page.wait_for_function(READY)
    _scroll_to_scene(page, 10)
    page.locator(".cv-ctas a", has_text=label).click()
    page.wait_for_url(f"{base_url}{path}")
    assert page.locator("main").count() >= 1
