"""F-206, cover v3 (D-380 to D-392): the cover in a real browser. The opening shows at once in the visitor's day or night, scrolling (and a finger
on a phone) moves the story through every scene, every heading sits on the page's centre line, the booking tour holds its screen while three
beats pass and rings (on a phone, zooms to) the part each speaks of, the reveals fade in on the motion tokens and reduced motion shows everything
at once, without the script everything still shows, each screenshot loads only as it nears the screen and in the visitor's layout and mode (the
site's own switch too), the page never asks for three.js or the world, nothing scrolls sideways from 320 to 1440, a phone gets 16 px text and
48 px targets, a notch never covers anything, the words read at full strength in both modes, and production ignores the review switch."""
import re

import pytest

from gitaway.pages import cover as cover_page
from tests_browser.helpers import DESKTOP, PHONE

HEAVY = re.compile(r"/assets/vendor/three|/assets/js/cover/|/assets/cover/tahoe-|/assets/cover/stills")
SHOT = re.compile(r"/assets/cover/shots/")
SIZES = {"390": PHONE, "1440": DESKTOP}
N = 8                                          # the story's scenes and the close (tests/test_cover.py STORY, plus the close)
READY = "!!window.GA_COVER"


@pytest.fixture
def cover(browser, base_url):
    made = []

    def open_cover(viewport=DESKTOP, scheme="light", motion="no-preference", init=None, query="", insets=None, js=True):
        phone = viewport["width"] < 760
        ctx = browser.new_context(viewport=viewport, color_scheme=scheme, reduced_motion=motion, has_touch=phone, is_mobile=phone, java_script_enabled=js)
        ctx.set_default_timeout(15000)
        made.append(ctx)
        page = ctx.new_page()
        page.requests = []
        page.on("request", lambda r: page.requests.append(r.url))
        if init:
            page.add_init_script(init)
        if insets:                                        # a notch: what env(safe-area-inset-*) reports on an iPhone on its side
            page.context.new_cdp_session(page).send("Emulation.setSafeAreaInsetsOverride", {"insets": insets})
        page.goto(f"{base_url}/{query}")
        if js:
            page.wait_for_function(READY)
        return page

    yield open_cover
    for c in made:
        c.close()


def _scroll_to_scene(page, i):
    page.evaluate("i => window.scrollTo(0, GA_COVER.scenes()[i] + 2)", i)
    page.wait_for_function(f"document.documentElement.dataset.cvScene === '{i}'")


def _to_beat(page, i):
    page.evaluate("i => window.scrollTo(0, GA_COVER.beatY(i))", i)
    page.wait_for_function(f"GA_COVER.beat() === {i}")


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("size", ["390", "1440"])
def test_the_opening_shows_at_once_centred_in_day_or_night(cover, size, scheme):
    page = cover(SIZES[size], scheme)
    assert page.evaluate(f"document.documentElement.classList.contains('cv-{scheme}')")
    assert page.locator("h1").inner_text().replace("\n", " ").strip() == "Take a trip. Leave a trail."
    assert page.locator(".cv-open .cv-btn").inner_text().strip() == "Plan a trip"
    vw = SIZES[size]["width"]
    for sel in (".cv-open h1", ".cv-lede", ".cv-open .cv-btn"):
        box = page.locator(sel).bounding_box()
        assert box["y"] + box["height"] <= SIZES[size]["height"], sel            # the whole opening is on the first screen
        assert abs(box["x"] + box["width"] / 2 - vw / 2) <= 2, (sel, box)
    bg = page.evaluate("getComputedStyle(document.body).backgroundColor")
    assert bg == ("rgb(0, 0, 0)" if scheme == "dark" else "rgb(242, 242, 245)")


@pytest.mark.parametrize("size", ["390", "1440"])
def test_every_heading_and_screen_sits_on_the_centre_line(cover, size):
    page = cover(SIZES[size], motion="reduce")
    off = page.evaluate("""() => [...document.querySelectorAll('main h1, main h2, main h3, .cv-say, .cv-eyebrow, .cv-beats, .cv-lens, .cv-frame, .cv-ill, .cv-last h2, .cv-ctas, .cv-foot p')]
      .filter((e) => e.getClientRects().length).map((e) => { const r = e.getBoundingClientRect(), c = r.left + r.width / 2;
        return [e.className || e.tagName, e.textContent.trim().slice(0, 24), Math.round(c - document.documentElement.clientWidth / 2)]; })""")
    assert len(off) >= 30 and all(abs(d) <= 2 for *_, d in off), [o for o in off if abs(o[2]) > 2]
    aligned = page.evaluate("() => [...document.querySelectorAll('main h1, main h2, main h3, .cv-say, .cv-beat, .cv-lede')].map((e) => getComputedStyle(e).textAlign)")
    assert set(aligned) == {"center"}


@pytest.mark.parametrize("size", ["390", "1440"])
def test_scrolling_moves_the_story_through_every_scene(cover, size):
    page = cover(SIZES[size], motion="reduce")
    for i in range(N):
        _scroll_to_scene(page, i)
    assert page.locator(".cv-last h2").inner_text().replace("\n", " ").strip() == "Take a trip. Leave a trail."


@pytest.mark.parametrize("size", ["390", "1440"])
def test_the_booking_tour_holds_the_screen_while_each_beat_rings_its_part(cover, size):
    page = cover(SIZES[size])
    rects = []
    for i in range(3):
        _to_beat(page, i)
        page.wait_for_timeout(450)
        on = page.evaluate("() => [...document.querySelectorAll('.cv-beat')].map((b) => getComputedStyle(b).opacity)")
        assert on[i] == "1" and all(o == "0" for k, o in enumerate(on) if k != i), on
        rings = page.evaluate(f"() => [...document.querySelectorAll('.cv-ring')].map((r) => [r.dataset.beat, getComputedStyle(r).opacity])")
        assert {b for b, o in rings if o == "1"} == {str(i)}, rings
        assert page.locator(".cv-steps li.on").get_attribute("data-beat") == str(i)
        lens = page.locator(".cv-lens").bounding_box()
        beat = page.locator(f'.cv-beat[data-beat="{i}"]').bounding_box()
        assert beat["y"] + beat["height"] <= lens["y"] + 1 and lens["y"] + lens["height"] <= SIZES[size]["height"] + 1, (beat, lens)   # words above, the screen whole
        assert page.evaluate(f"""(() => {{ const r = document.querySelector('.cv-ring[data-beat="{i}"]').getBoundingClientRect(), l = document.querySelector('.cv-lens').getBoundingClientRect();
          const cx = r.left + r.width / 2, cy = r.top + r.height / 2; return cx > l.left && cx < l.right && cy > l.top && cy < l.bottom; }})()"""), i   # its part is in view
        rects.append(lens)
    assert max(r["y"] for r in rects) - min(r["y"] for r in rects) <= 2                # the screen stayed put
    transform = page.evaluate("getComputedStyle(document.querySelector('.cv-lens-in')).transform")
    if size == "390":
        assert transform != "none" and float(page.evaluate("getComputedStyle(document.querySelector('.cv-lens-in')).getPropertyValue('--k')")) > 1.5
    else:
        assert transform == "none"                                                      # a laptop does not zoom (calm desktop)


def test_the_tour_moves_only_on_the_motion_tokens(cover):
    page = cover(PHONE)
    tok = page.evaluate("""() => { const s = getComputedStyle(document.documentElement); return ['--motion-screen-dur', '--motion-zoom'].map((k) => s.getPropertyValue(k).trim()); }""")
    inner = page.evaluate("(() => { const s = getComputedStyle(document.querySelector('.cv-lens-in')); return [s.transitionDuration, s.transitionTimingFunction]; })()")
    nums = lambda s: [float(x) for x in re.findall(r"[\d.]+", s)]      # noqa: E731  (0.22 and .22 are the same ease)
    assert inner[0] == f"{float(tok[0].rstrip('ms')) / 1000:g}s" and nums(inner[1]) == nums(tok[1])


@pytest.mark.parametrize("size", ["390", "1440"])
def test_reveals_fade_in_as_the_story_reaches_them_and_reduced_motion_shows_all(cover, size):
    page = cover(SIZES[size])
    assert page.evaluate("document.documentElement.classList.contains('cv-run')")
    far = page.locator(".cv-close .cv-rv")
    assert far.evaluate("e => getComputedStyle(e).opacity") == "0"                      # not yet reached
    page.evaluate("document.querySelector('.cv-close').scrollIntoView()")
    page.wait_for_function("getComputedStyle(document.querySelector('.cv-close .cv-rv')).opacity === '1'")
    calm = cover(SIZES[size], motion="reduce")
    assert calm.evaluate("document.documentElement.classList.contains('cv-calm')")
    assert calm.evaluate("[...document.querySelectorAll('.cv-rv')].every((e) => getComputedStyle(e).opacity === '1' && getComputedStyle(e).transform === 'none')")
    assert calm.evaluate("getComputedStyle(document.querySelector('.cv-beat')).transitionDuration") == "0s"


def test_without_the_script_every_word_and_picture_shows(cover, base_url):
    page = cover(PHONE, js=False)
    assert page.locator(".cv-rv").count() > 8
    assert page.evaluate("[...document.querySelectorAll('.cv-rv, .cv-beat')].every((e) => getComputedStyle(e).opacity === '1')")
    assert page.locator(".cv-beat").count() == 3 and all(page.locator(".cv-beat").nth(k).is_visible() for k in range(3))


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("size", ["390", "1440"])
def test_each_screenshot_loads_as_it_nears_in_the_visitors_layout_and_mode(cover, size, scheme):
    page = cover(SIZES[size], scheme, motion="reduce")
    page.wait_for_timeout(400)
    assert not [u for u in page.requests if SHOT.search(u) and "-creators-" in u]       # far below the fold: not yet
    layout = "phone" if size == "390" else "wide"
    for name in ("book", "trail", "cockpit", "day", "ask", "family", "creators"):
        page.evaluate(f"document.querySelector('[data-shot=\"{name}\"]').scrollIntoView({{ block: 'center' }})")
        want = rf"/book-wide-{scheme}-(960|1600)\.webp$" if name == "book" else rf"/{name}-{layout}-{scheme}-({'600' if layout == 'phone' else '960|1440'})\.webp$"
        page.wait_for_function(f"""(() => {{ const im = document.querySelector('[data-shot="{name}"] img');
          return im.complete && im.naturalWidth > 0 && new RegExp({want!r}).test(im.currentSrc); }})()""")
    got = [u for u in page.requests if SHOT.search(u)]
    assert all(f"-{scheme}-" in u for u in got) and all("-book-" in u or "book-" in u.rsplit("/", 1)[-1] or f"-{layout}-" in u for u in got), got


def test_the_screenshots_follow_the_sites_own_switch(cover):
    page = cover(PHONE, "light", motion="reduce")
    page.evaluate("document.documentElement.dataset.theme = 'dark'")
    page.wait_for_function("document.documentElement.classList.contains('cv-dark')")
    page.evaluate("document.querySelector('[data-shot=\"ask\"]').scrollIntoView({ block: 'center' })")
    page.wait_for_function("""(() => { const im = document.querySelector('[data-shot="ask"] img');
      return im.complete && im.naturalWidth > 0 && im.currentSrc.endsWith('/ask-phone-dark-600.webp'); })()""")
    page.evaluate("delete document.documentElement.dataset.theme")
    page.wait_for_function("document.documentElement.classList.contains('cv-light')")
    page.emulate_media(color_scheme="dark")
    page.wait_for_function("document.documentElement.classList.contains('cv-dark')")
    assert page.evaluate("getComputedStyle(document.body).backgroundColor") == "rgb(0, 0, 0)"


@pytest.mark.parametrize("size", ["390", "1440"])
def test_the_page_never_asks_for_three_or_the_world(cover, size):
    page = cover(SIZES[size])
    page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
    page.wait_for_timeout(600)
    assert [u for u in page.requests if HEAVY.search(u)] == []
    assert page.locator("canvas").count() == 0


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
    cdp = page.context.new_cdp_session(page)
    for _ in range(4):
        _swipe(page, cdp, 195, 720, 195, 180)
    assert page.evaluate("scrollY") > 1500
    assert int(page.evaluate("document.documentElement.dataset.cvScene")) >= 1
    # a swipe that starts on the booking screenshot, or on a feature's, scrolls the page too
    for sel in (".cv-lens", '[data-shot="cockpit"]'):
        page.evaluate(f"document.querySelector('{sel}').scrollIntoView({{ block: 'center' }})")
        page.wait_for_timeout(200)
        box = page.locator(sel).bounding_box()
        before = page.evaluate("scrollY")
        cx, cy = box["x"] + box["width"] / 2, min(box["y"] + box["height"] / 2, 700)
        _swipe(page, cdp, cx, cy, cx, cy - 300)
        assert page.evaluate("scrollY") > before + 150, sel


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("width", [1440, 1280, 1000, 800, 390, 320])
def test_nothing_scrolls_sideways(cover, width, scheme):
    page = cover({"width": width, "height": 844 if width < 760 else 900}, scheme, motion="reduce")
    for i in range(N):
        _scroll_to_scene(page, i)
        assert page.evaluate("document.documentElement.scrollWidth") <= page.evaluate("document.documentElement.clientWidth"), (width, i)
    for i in range(3):
        _to_beat(page, i)
        assert page.evaluate("document.documentElement.scrollWidth") <= page.evaluate("document.documentElement.clientWidth"), (width, "beat", i)


def test_a_phone_reads_16px_text_and_taps_48px_targets(cover):
    page = cover(PHONE, motion="reduce")
    small = page.evaluate("""() => [...document.querySelectorAll('main p, main li, main b, main span, .cv-btn, .cv-foot p, .cv-foot nav a, .cv-ill b')]
      .filter(e => e.getClientRects().length && e.textContent.trim() && !e.closest('.cv-eyebrow, .cv-steps, .cv-tag, .cv-hint'))
      .map(e => [e.textContent.trim().slice(0, 30), parseFloat(getComputedStyle(e).fontSize)]).filter(([, s]) => s < 16)""")
    assert small == []
    eyebrows = page.evaluate("() => [...document.querySelectorAll('.cv-eyebrow')].map(e => parseFloat(getComputedStyle(e).fontSize))")
    assert len(eyebrows) == 4 and min(eyebrows) >= 13                                # all-caps labels only
    targets = page.evaluate("""() => [...document.querySelectorAll('.cv-top a, .cv-ctas a, .cv-foot nav a, .cv-close .pf-card a')]
      .filter(e => e.getClientRects().length).map(e => [e.textContent.trim(), e.getBoundingClientRect().height])""")
    assert len(targets) >= 7 and all(h >= 48 for _, h in targets), targets


def test_a_notch_never_covers_the_header_the_story_or_the_close(cover):
    """An iPhone on its side: the notch and the rounded corners take 47 px each side (viewport-fit=cover hands that space to the page)."""
    page = cover({"width": 844, "height": 390}, motion="reduce", insets={"left": 47, "right": 47, "top": 0, "bottom": 21})
    clear = """sel => [...document.querySelectorAll(sel)].filter(e => e.getClientRects().length).map(e => { const r = e.getBoundingClientRect();
      return [e.className || e.tagName, Math.round(r.left), Math.round(r.right)]; })"""
    boxes = page.evaluate(clear, ".cv-top > *, main h1, main h2, main h3, .cv-say, .cv-lens, .cv-frame, .cv-ill, .cv-close .pf-card, .cv-foot > *, .cv-foot nav a")
    assert len(boxes) >= 30 and all(l >= 47 and r <= 844 - 47 for _, l, r in boxes), [b for b in boxes if b[1] < 47 or b[2] > 797]


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


@pytest.mark.parametrize("size", [(320, 568), (390, 844), (1280, 800)], ids=["320x568", "390x844", "1280x800"])
def test_the_tours_words_clear_the_header(cover, size):
    w, h = size
    page = cover({"width": w, "height": h})
    for i in range(3):
        _to_beat(page, i)
        head = page.evaluate("Math.max(...[...document.querySelectorAll('.cv-top, .cv-top > *')].map((e) => e.getBoundingClientRect().bottom))")
        beat = page.locator(f'.cv-beat[data-beat="{i}"]').bounding_box()
        lens = page.locator(".cv-lens").bounding_box()
        assert beat["y"] >= head - 0.5 and lens["y"] + lens["height"] <= h + 0.5 and lens["height"] >= 0.3 * h, (i, head, beat, lens)


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
    page = cover(DESKTOP, scheme, motion="reduce")
    ratios = page.evaluate(CONTRAST, "main h1, main h2, main h3, .cv-say, .cv-lede, .cv-eyebrow, .cv-beat, .cv-disc, .cv-cap, .cv-ill b, .cv-ill p, .cv-mute, .cv-stops li, .cv-fake-btn, .cv-foot p")
    assert len(ratios) >= 40 and min(r for _, r in ratios) >= 4.5, sorted(ratios, key=lambda x: x[1])[:4]


def test_production_ignores_the_review_switch(cover, monkeypatch):
    """?beat= holds the tour on a beat for the review tools; without data-debug (production) the scroll decides."""
    page = cover(DESKTOP, query="?beat=2")
    assert page.evaluate("GA_COVER.beat()") == 2
    monkeypatch.setattr(cover_page, "debug", lambda: False)
    page = cover(DESKTOP, query="?beat=2")
    assert page.evaluate("GA_COVER.beat()") == 0 and page.evaluate("GA_COVER.debug") is False


@pytest.mark.parametrize("label,path", [("Plan a trip", "/start"), ("See trips people shared", "/community")])
def test_each_door_at_the_end_opens_its_page(cover, base_url, label, path):
    page = cover(DESKTOP, motion="reduce")
    page.evaluate("document.querySelector('.cv-close').scrollIntoView()")
    page.locator(".cv-close .cv-ctas a", has_text=label).click()
    page.wait_for_url(f"{base_url}{path}")
    assert page.locator("main").count() >= 1


@pytest.mark.parametrize("label,path", [("Plan a trip", "/start"), ("Bring your post", "/for-creators")])
def test_the_doors_in_the_story_open_their_pages(cover, base_url, label, path):
    page = cover(PHONE, motion="reduce")
    link = page.locator("main .cv-ctas a", has_text=label).first
    link.scroll_into_view_if_needed()
    link.click()
    page.wait_for_url(f"{base_url}{path}")
