"""F-206: the cover in a real browser. The poster shows at once, scrolling (and a finger on a phone) moves the story through its chapters, every
card fits between the header and the bottom of the screen (a landscape phone and a 768-tall laptop too), reduced motion, no WebGL and a weak phone
get the calm stills without ever asking for three.js, the live world loads and stops drawing when it is covered or the tab is hidden, it gives up
for the stills (and gives the GPU back) when even its lowest resolution is too slow, day and night follow the site, nothing scrolls sideways, a
phone gets 16 px text and 48 px targets, a notch never covers anything, a screen reader gets the plan's details, and production ignores the tools'
switches. 390 and 1440 wide, light and dark."""
import hashlib
import re
from pathlib import Path

import pytest

from gitaway.pages import cover as cover_page
from tests_browser.helpers import DESKTOP, PHONE

ROOT = Path(__file__).resolve().parent.parent
HEAVY = re.compile(r"/assets/vendor/three|/assets/js/cover/world\.js|/assets/cover/tahoe-")
SIZES = {"390": PHONE, "1440": DESKTOP}
# a phone with enough memory for the live world but too few cores to count as strong: it gets the lightest tier without ?q
MODEST_PHONE = "Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 4 });"


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
        if size == "1440":
            assert page.locator(".cv-rail button").nth(i).get_attribute("aria-current") == "step"
    assert page.locator(".cv-last h2").inner_text().replace("\n", " ").strip() == "Take a trip. Leave a trail."


CARD = """i => { const el = document.querySelector(i === 0 ? '.cv-hero-copy' : `[data-chapter="${i}"] .cv-card`), r = el.getBoundingClientRect();
  return { top: r.top, bottom: r.bottom, left: r.left, right: r.right, head: document.querySelector('.cv-top').getBoundingClientRect().bottom,
           vh: innerHeight, hidden: el.scrollHeight - el.clientHeight }; }"""


@pytest.mark.parametrize("how", ["live", "stills"])
@pytest.mark.parametrize("size", [(844, 390), (1366, 768), (320, 568)], ids=["844x390", "1366x768", "320x568"])
def test_every_card_fits_between_the_header_and_the_bottom_of_the_screen(cover, size, how):
    """A landscape phone and a 768-tall laptop read every chapter whole: no card runs under the header or off the bottom, and none hides words
    behind its own scroll (the card scrolls only on screens shorter still)."""
    w, h = size
    page = cover({"width": w, "height": h}, motion="reduce" if how == "stills" else "no-preference", stub_world=how == "live")
    page.wait_for_function("window.GA_COVER && window.GA_COVER.anchors().length === 7")
    assert page.evaluate("document.documentElement.classList.contains('cv-live')") == (how == "live")
    for i in range(7):
        _scroll_to_chapter(page, i)
        box = page.evaluate(CARD, i)
        assert box["head"] - 0.5 <= box["top"] and box["bottom"] <= box["vh"] + 0.5, (i, box)
        assert box["hidden"] <= 1, (i, box)


def test_a_notch_never_covers_the_header_a_card_or_the_closing_screen(cover):
    """An iPhone on its side: the notch and the rounded corners take 47 px each side (viewport-fit=cover hands that space to the page)."""
    page = cover({"width": 844, "height": 390}, motion="reduce", insets={"left": 47, "right": 47, "top": 0, "bottom": 21})
    page.wait_for_function("window.GA_COVER && window.GA_COVER.anchors().length === 7")
    clear = "sel => [...document.querySelectorAll(sel)].filter(e => e.getClientRects().length).map(e => { const r = e.getBoundingClientRect(); return [e.className || e.tagName, Math.round(r.left), Math.round(r.right)]; })"
    for i in range(7):
        _scroll_to_chapter(page, i)
        box = page.evaluate(CARD, i)
        assert box["left"] >= 47 and box["right"] <= 844 - 47, (i, box)
    boxes = page.evaluate(clear, ".cv-top > *")
    page.evaluate("document.querySelector('.cv-close').scrollIntoView({ block: 'end' })")
    boxes += page.evaluate(clear, ".cv-close .pf-card, .cv-foot > *, .cv-foot nav a")
    assert len(boxes) >= 6 and all(l >= 47 and r <= 844 - 47 for _, l, r in boxes), boxes


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
    lo = hashlib.sha256((ROOT / "assets/cover/tahoe-lo.bin.gz").read_bytes()).hexdigest()[:10]
    assert any("three.cover.min.js?v=" in u for u in page.requests) and any(u.endswith(f"/assets/cover/tahoe-lo.bin.gz?v={lo}") for u in page.requests)
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
    page.wait_for_function("window.GA_COVER && window.GA_COVER.anchors().length === 7")
    for i in (0, 3, 6):
        _scroll_to_chapter(page, i)
        assert page.evaluate("document.documentElement.scrollWidth") <= page.evaluate("document.documentElement.clientWidth"), (width, i)


def test_a_phone_reads_16px_text_and_taps_48px_targets(cover):
    page = cover(PHONE, motion="reduce")
    page.wait_for_function("window.GA_COVER && window.GA_COVER.anchors().length === 7")
    small = page.evaluate("""() => [...document.querySelectorAll('.cv-card p, .cv-card li, .cv-lede, .cv-foot p, .cv-btn, .cv-foot nav a, .cv-wd span:not(.k), .cv-wd b')]
      .filter(e => e.getClientRects().length && !e.closest('.cv-anchors'))
      .map(e => [e.textContent.trim().slice(0, 30), parseFloat(getComputedStyle(e).fontSize)]).filter(([, s]) => s < 16)""")
    assert small == []
    eyebrows = page.evaluate("() => [...document.querySelectorAll('.cv-eyebrow, .cv-wd .k')].map(e => parseFloat(getComputedStyle(e).fontSize))")
    assert min(eyebrows) >= 13                                                        # all-caps labels only
    targets = page.evaluate("""() => [...document.querySelectorAll('.cv-top a, .cv-ctas a, .cv-foot nav a, .cv-close .pf-card a')]
      .filter(e => e.getClientRects().length).map(e => [e.textContent.trim(), e.getBoundingClientRect().height])""")
    assert len(targets) >= 6 and all(h >= 48 for _, h in targets), targets


def test_a_landscape_tablet_taps_48px_chapter_buttons(cover):
    page = cover({"width": 1024, "height": 768}, motion="reduce")
    page.wait_for_function("window.GA_COVER && window.GA_COVER.anchors().length === 7")
    sizes = page.evaluate("() => [...document.querySelectorAll('.cv-rail button')].map(b => { const r = b.getBoundingClientRect(); return [r.width, r.height]; })")
    assert len(sizes) == 7 and all(w >= 48 and h >= 48 for w, h in sizes), sizes


@pytest.mark.parametrize("size", ["390", "1440"])
def test_the_footer_links_sit_at_least_8px_apart(cover, size):
    page = cover(SIZES[size], motion="reduce")
    page.evaluate("document.querySelector('.cv-foot').scrollIntoView({ block: 'end' })")
    gaps = page.evaluate("""() => { const r = [...document.querySelectorAll('.cv-foot nav a')].map(a => a.getBoundingClientRect()), out = [];
      for (let i = 1; i < r.length; i++) if (Math.abs(r[i].top - r[i - 1].top) < 2) out.push(r[i].left - r[i - 1].right); return out; }""")
    assert gaps and min(gaps) >= 8, gaps


@pytest.mark.parametrize("width", [390, 320])
def test_a_phone_shows_the_early_preview_label_between_the_logo_and_sign_in(cover, width):
    page = cover({"width": width, "height": 700}, motion="reduce")
    assert page.locator(".cv-tag").is_visible()
    boxes = page.evaluate("() => [...document.querySelectorAll('.cv-top > *')].map(e => { const r = e.getBoundingClientRect(); return [e.className, r.left, r.right]; })")
    assert [c.split()[0] for c, _, _ in boxes] == ["ga-brand", "cv-tag", "cv-btn"]
    assert boxes[0][1] >= 0 and boxes[-1][2] <= width
    for (_, _, r0), (_, l1, _) in zip(boxes, boxes[1:]):
        assert r0 <= l1, boxes                                                          # side by side, never on top of one another


CONTRAST = """() => { const lin = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
  const rgb = (s) => s.match(/[\\d.]+/g).map(Number), L = ([r, g, b]) => 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b), out = [];
  for (const w of document.querySelectorAll('[data-chapter="3"] .cv-wd')) {
    const bg = rgb(getComputedStyle(w).backgroundColor);
    for (const el of w.querySelectorAll('.k, b, span, .by')) {
      if (!el.textContent.trim() || !el.getClientRects().length) continue;
      const fg = rgb(getComputedStyle(el).color);
      let a = fg.length > 3 ? fg[3] : 1;
      for (let e = el; e !== w.parentElement; e = e.parentElement) a *= parseFloat(getComputedStyle(e).opacity);
      const f = fg.slice(0, 3).map((c, i) => c * a + bg[i] * (1 - a)), l1 = L(f), l2 = L(bg);
      out.push([el.textContent.trim().slice(0, 24), (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05)]);
    }
  }
  return out; }"""


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_the_widgets_words_read_at_full_strength(cover, scheme):
    page = cover(DESKTOP, scheme, motion="reduce")
    page.wait_for_function("window.GA_COVER && window.GA_COVER.anchors().length === 7")
    _scroll_to_chapter(page, 3)
    ratios = page.evaluate(CONTRAST)
    assert len(ratios) >= 18 and min(r for _, r in ratios) >= 4.5, sorted(ratios, key=lambda x: x[1])[:4]


def test_with_the_live_world_a_screen_reader_still_gets_the_plans_details(cover):
    """On a laptop the world stamps the plan's widgets into itself (aria-hidden copies); the card keeps the real ones, visually hidden, and they
    take no keyboard stop. In the stills the same row is visible and, when it scrolls, can be scrolled from the keyboard."""
    page = cover(DESKTOP, stub_world=True)
    page.wait_for_function("window.GA_COVER && window.GA_COVER.anchors().length === 7")
    assert page.evaluate("document.documentElement.classList.contains('cv-live')")
    _scroll_to_chapter(page, 3)
    group = page.get_by_role("group", name="The trip, planned")
    assert group.count() == 1
    for words in ("28°", "Cabin → Taylor Creek sled hill", "SFO → RNO", "Booked on Vrbo", "Booked on Klook"):
        assert group.get_by_text(words).count() == 1, words
    box = group.bounding_box()
    assert box["width"] <= 1 and box["height"] <= 1 and group.get_attribute("tabindex") is None


def test_in_the_stills_a_keyboard_scrolls_the_plans_row(cover):
    page = cover({"width": 1366, "height": 768}, motion="reduce")
    page.wait_for_function("window.GA_COVER && window.GA_COVER.anchors().length === 7")
    _scroll_to_chapter(page, 3)
    row = page.locator('[data-chapter="3"] .cv-wds')
    assert row.is_visible() and row.evaluate("e => e.scrollWidth > e.clientWidth + 1")
    assert row.get_attribute("tabindex") == "0"
    row.focus()
    page.keyboard.press("ArrowRight")
    page.wait_for_function("document.querySelector('[data-chapter=\"3\"] .cv-wds').scrollLeft > 20")


def test_the_worlds_labels_and_leader_lines_pass_under_the_cards(cover):
    page = cover(DESKTOP, stub_world=True)
    page.wait_for_function("window.GA_COVER && window.GA_COVER.anchors().length === 7")
    _scroll_to_chapter(page, 3)
    assert page.evaluate("""() => { const probe = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      probe.setAttribute('class', 'leaders'); probe.style.pointerEvents = 'auto'; document.querySelector('.cv-anchors').appendChild(probe);
      const r = document.querySelector('[data-chapter="3"] .cv-card h2').getBoundingClientRect(), e = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
      return !!(e && e.closest('.cv-card')); }""")


def test_production_ignores_the_tools_switches(cover, monkeypatch):
    """Without data-debug (production), ?measure no longer lets a weak phone download the world and ?q no longer picks the tier."""
    monkeypatch.setattr(cover_page, "debug", lambda: False)
    page = cover(PHONE, init="Object.defineProperty(navigator, 'deviceMemory', { get: () => 1 });", query="?measure&q=high&cam=0,0,0,1,1,1,40")
    page.wait_for_function("document.documentElement.classList.contains('cv-still')")
    page.wait_for_timeout(500)
    assert _heavy(page) == []
    assert page.evaluate("[GA_COVER.tier, ['measure', 'capture', 'q', 'cam'].some((k) => GA_COVER.Q.has(k))]") == ["low", False]


def test_in_production_the_world_keeps_its_insides_to_itself(cover, monkeypatch):
    monkeypatch.setattr(cover_page, "debug", lambda: False)
    page = cover(PHONE, init=MODEST_PHONE)
    page.wait_for_function("document.documentElement.classList.contains('cv-ready')", timeout=60000)
    assert page.evaluate("GA_COVER.tier") == "low"
    assert page.evaluate("[typeof window.__cover, typeof window.__frames, typeof window.__work]") == ["undefined"] * 3


@pytest.mark.parametrize("label,path", [("Start a trip", "/start"), ("Leave a trail", "/for-creators"), ("See trips people shared", "/community")])
def test_each_door_at_the_end_opens_its_page(cover, base_url, label, path):
    page = cover(DESKTOP, motion="reduce")
    page.wait_for_function("window.GA_COVER && window.GA_COVER.anchors().length === 7")
    _scroll_to_chapter(page, 6)
    page.locator(".cv-ctas a", has_text=label).click()
    page.wait_for_url(f"{base_url}{path}")
    assert page.locator("main").count() >= 1
