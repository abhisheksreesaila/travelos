"""F-206, cover v5 (D-410 on, over v4's D-400 to D-406): the cover in a real browser. The opening shows at once in the visitor's day or night;
each chapter is a stage whose screen stays while the scroll moves a camera over the app (the booking screen zooms to the flight beside the stay,
glides over the weather and the drive and pulls back, and where you book shows; the trips deal in and one becomes Lena and Sam's; the cockpit
dives into the day, which arrives whole, never half see-through, then the screen loops through the day, Ask and the chat on its own, only while
it is on screen; the pins drop), on a laptop as on a phone (the calm desktop's exception, D-401); the moments that play on their own run on the
motion tokens; a finger scrolls the whole story on a phone, starting on any screen; reduced motion, a short screen or no script give a still, readable
page; each screenshot loads only as it nears, in the visitor's layout and mode; the page never asks for three.js; nothing scrolls sideways from
320 to 1440; a phone gets 16 px text and 48 px targets; a notch never covers anything; the words read at full strength in both modes; scrolling
the booking stage on a CPU four times slower makes no long task; and production ignores the review switch."""
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


def _at(page, key, p):
    """Scroll the real page to a point of a stage and wait for the conductor to play it."""
    page.evaluate("([k, p]) => window.scrollTo(0, GA_COVER.yAt(k, p))", [key, p])
    page.wait_for_function(f"Math.abs(GA_COVER.progress('{key}') - {p}) < 0.01")


def _box(page, sel):
    return page.evaluate(f"(() => {{ const r = document.querySelector('{sel}').getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; }})()")


def _scale(page, sel):
    return page.evaluate(f"new DOMMatrix(getComputedStyle(document.querySelector('{sel}')).transform).a")


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("size", ["390", "1440"])
def test_the_opening_shows_at_once_in_day_or_night_over_a_laptop_and_a_phone(cover, size, scheme):
    page = cover(SIZES[size], scheme)
    assert page.evaluate(f"document.documentElement.classList.contains('cv-{scheme}')")
    assert page.locator("h1").inner_text().replace("\n", " ").strip() == "Take a trip. Leave a trail."
    assert page.locator(".cv-hero .cv-btn").inner_text().strip() == "Plan a trip"
    vw, vh = SIZES[size]["width"], SIZES[size]["height"]
    for sel in (".cv-hero h1", ".cv-lede", ".cv-hero .cv-btn"):
        x, y, w, h = _box(page, sel)
        assert y + h <= vh and abs(x + w / 2 - vw / 2) <= 2, (sel, x, y, w, h)        # the whole line on the first screen, centred
    screens = page.evaluate("[...document.querySelectorAll('.cv-hero .cv-screen')].filter((e) => e.getClientRects().length).map((e) => e.getBoundingClientRect().top)")
    assert screens and min(screens) < vh                                             # the app is already on the first screen
    assert page.evaluate("getComputedStyle(document.querySelector('.cv-hero .cv-devices')).transform").startswith("matrix3d")   # tilted
    _at(page, "hero", 1)
    assert page.evaluate("getComputedStyle(document.querySelector('.cv-hero-copy')).opacity") == "0"
    assert abs(_scale(page, ".cv-hero .cv-devices") - 1) < 0.01                     # set down flat
    bg = page.evaluate("getComputedStyle(document.querySelector('.cv-hero')).backgroundColor")
    assert bg == ("rgb(7, 11, 20)" if scheme == "dark" else "rgb(230, 238, 249)")


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_each_chapter_has_its_own_colour(cover, scheme):
    page = cover(DESKTOP, scheme, motion="reduce")
    tints = page.evaluate("[...document.querySelectorAll('.cv-stage')].map((s) => getComputedStyle(s).backgroundColor)")
    assert len(tints) == 8 and len(set(tints)) == 8, tints
    em = page.evaluate("[...document.querySelectorAll('.cv-stage h2 em')].map((e) => getComputedStyle(e).color)")
    assert len(set(em)) >= 5, em                                                    # the second tone is the chapter's kind colour


def test_the_stages_alternate_sides_on_a_laptop(cover):
    """Not everything centred (D-405): the words sit beside the camera, left in Book and Creators, right in Head start, With you and Trail."""
    page = cover(DESKTOP)
    for key, words_left in (("book", True), ("head", False), ("with", False), ("trail", False), ("creators", True)):
        _at(page, key, 0.5)
        copy = _box(page, f".cv-{key} .cv-copy")
        other = _box(page, {"book": ".cv-lens", "head": ".cv-deal", "with": ".cv-with .cv-devices", "trail": ".cv-trail .cv-deal", "creators": ".cv-creators .cv-deal"}[key])
        mid_c, mid_o = copy[0] + copy[2] / 2, other[0] + other[2] / 2
        assert (mid_c < mid_o) == words_left, (key, copy, other)


@pytest.mark.parametrize("size", ["390", "1440"])
def test_scrolling_moves_the_story_through_every_scene(cover, size):
    page = cover(SIZES[size], motion="reduce")
    for i in range(N):
        _scroll_to_scene(page, i)
    assert page.locator(".cv-last h2").inner_text().replace("\n", " ").strip() == "Take a trip. Leave a trail."


@pytest.mark.parametrize("size", ["390", "1440"])
def test_the_booking_stage_holds_its_screen_while_the_camera_zooms_pans_and_pulls_back(cover, size):
    """On the phone and the laptop alike (D-401): zoom to the flight beside the stay, glide over the weather and the drive, pull back to the
    whole page, where the partners show (D-413: three moves, no numbers, rings or chips flying)."""
    page = cover(SIZES[size])
    lenses, ks = [], {}
    for p, word, spot in ((0.3, "0", "fs"), (0.52, "1", "wx"), (0.7, "1", "drive"), (0.95, "2", None)):
        _at(page, "book", p)
        page.wait_for_timeout(450)
        assert page.evaluate("GA_COVER.beat()") == word, p
        assert page.evaluate(f"getComputedStyle(document.querySelector('.cv-beat[data-beat=\"{word}\"]')).opacity") == "1"
        on = page.evaluate("[...document.querySelectorAll('.cv-spot')].filter((s) => getComputedStyle(s).opacity === '1').map((s) => s.dataset.spot)")
        assert on == ([spot] if spot else []), (p, on)
        ks[p] = _scale(page, ".cv-cam")
        lenses.append(_box(page, ".cv-lens"))
        assert page.evaluate("getComputedStyle(document.querySelector('.cv-partners')).opacity") == ("1" if word == "2" else "0"), p
    assert ks[0.3] > 1.3 and ks[0.52] > 1.6 and ks[0.7] > 1.6 and ks[0.95] <= 1.01, ks
    assert max(b[1] for b in lenses) - min(b[1] for b in lenses) <= 2 and max(b[0] for b in lenses) - min(b[0] for b in lenses) <= 2    # the screen stayed put
    chips = page.evaluate("[...document.querySelectorAll('.cv-chip')].map((c) => [c.classList.contains('soon'), c.textContent.trim()])")
    assert [t for soon, t in chips if not soon] == ["AviasalesFlights", "KlookStays, cars, things to do"]
    assert all(t.endswith("Soon") for soon, t in chips if soon) and len(chips) == 5


def test_the_trips_deal_in_and_one_becomes_lena_and_sams(cover):
    page = cover(DESKTOP)
    _at(page, "head", 0.01)
    assert page.evaluate("getComputedStyle(document.querySelector('.cv-trip[data-k=\"2\"]')).opacity") == "0"
    _at(page, "head", 0.34)
    assert page.evaluate("[...document.querySelectorAll('.cv-trip')].every((c) => getComputedStyle(c).opacity === '1')")
    _at(page, "head", 0.42)
    assert page.evaluate("document.querySelector('.cv-trip.pick').classList.contains('done')")
    assert page.locator(".cv-trip.pick .cv-fb-b").is_visible()                      # Imported
    assert page.locator(".cv-head .cv-stamp, .cv-burst").count() == 0                # one move, no stamp or burst on top of it
    _at(page, "head", 0.95)
    assert page.evaluate("getComputedStyle(document.querySelector('.cv-head .cv-morph')).opacity") == "1"
    assert page.evaluate("getComputedStyle(document.querySelector('.cv-head .cv-deal')).opacity") == "0"
    assert abs(_scale(page, ".cv-head .cv-morph") - 1) < 0.01


@pytest.mark.parametrize("size", ["390", "1440"])
def test_the_plan_comes_with_you_then_the_screen_loops_on_its_own(cover, size):
    page = cover(SIZES[size])
    scr = ".cv-phone" if size == "390" else ".cv-laptop"
    layer = lambda n: f"getComputedStyle(document.querySelector('{scr} [data-layer=\"{n}\"]')).opacity"      # noqa: E731
    feat = lambda i: f"getComputedStyle(document.querySelectorAll('.cv-feat')[{i}]).opacity"                # noqa: E731
    _at(page, "with", 0.1)
    page.wait_for_timeout(450)
    assert page.evaluate(feat(0)) == "1" and page.evaluate(layer("cockpit")) == "1" and page.evaluate(layer("day")) == "0"
    # the dive: wherever the scroll stops, the day is either not there yet or whole (v4's messy halfway, two see-through screens, is gone)
    for p in (0.2, 0.28, 0.33, 0.36, 0.39, 0.42):
        _at(page, "with", p)
        page.wait_for_timeout(450)
        assert page.evaluate(layer("day")) in ("0", "1"), p
    assert page.evaluate(layer("day")) == "1" and page.evaluate(feat(1)) == "1"
    # then the screen plays Ask and the chat on its own, the words following, with no more scrolling
    _at(page, "with", 0.7)
    page.wait_for_function(f"{layer('ask')} === '1' && {feat(2)} === '1'")
    page.wait_for_function(f"{layer('family')} === '1' && {feat(3)} === '1'", timeout=8000)
    assert abs(page.evaluate("GA_COVER.progress('with')") - 0.7) < 0.01           # the loop played with no scrolling
    # off screen it waits
    _at(page, "tips", 0.9)
    page.wait_for_timeout(200)
    now = page.evaluate(f"[...document.querySelectorAll('{scr} .cv-layer.cur')].map((l) => l.dataset.layer).join()")
    page.wait_for_timeout(3200)
    assert page.evaluate(f"[...document.querySelectorAll('{scr} .cv-layer.cur')].map((l) => l.dataset.layer).join()") == now


def test_the_pins_drop_with_their_tips_and_the_trail_slides_in(cover):
    page = cover(PHONE)
    _at(page, "tips", 0.2)
    page.wait_for_timeout(450)
    assert page.evaluate("[...document.querySelectorAll('.cv-mpin')].map((p) => p.classList.contains('on'))") == [True, False, False, False]
    assert float(page.evaluate("document.querySelector('.cv-draw[data-road=\"50\"]').style.strokeDashoffset")) < 1
    _at(page, "tips", 0.95)
    page.wait_for_timeout(450)
    assert page.evaluate("[...document.querySelectorAll('.cv-mpin')].every((p) => p.classList.contains('on'))")
    assert page.evaluate("getComputedStyle(document.querySelector('.cv-tip[data-k=\"3\"]')).opacity") == "1"
    heart = "getComputedStyle(document.querySelector('.cv-beat-heart')).animationPlayState"
    assert page.evaluate(heart) == "paused"                                         # the trail's heart beats only while it is on screen
    _at(page, "trail", 0.6)
    assert page.evaluate(heart) == "running"
    assert page.evaluate("getComputedStyle(document.querySelector('.cv-trail .cv-deal')).opacity") == "1"
    assert page.locator(".cv-trail .cv-num").inner_text() == "12"


def test_the_moments_move_only_on_the_motion_tokens(cover):
    page = cover(PHONE)
    tok = page.evaluate("""() => { const s = getComputedStyle(document.documentElement); return ['--motion-spring-dur', '--motion-spring', '--motion-screen-dur'].map((k) => s.getPropertyValue(k).trim()); }""")
    secs = lambda v: f"{float(v.rstrip('ms')) / 1000:g}s"      # noqa: E731
    for sel in (".cv-stamp", ".cv-mpin-in"):
        d, f = page.evaluate(f"(() => {{ const s = getComputedStyle(document.querySelector('{sel}')); return [s.transitionDuration, s.transitionTimingFunction]; }})()")
        assert d.split(", ")[0] == secs(tok[0]), (sel, d)
        nums = lambda s: [float(x) for x in re.findall(r"[\d.]+", s)]      # noqa: E731
        assert nums(f.split("),")[0]) == nums(tok[1]), (sel, f)
    for sel in (".cv-beat", ".cv-partners", '.cv-with [data-layer="ask"]', '.cv-with [data-layer="day"]'):
        assert page.evaluate(f"getComputedStyle(document.querySelector('{sel}')).transitionDuration").split(", ")[0] == secs(tok[2]), sel


@pytest.mark.parametrize("size", ["390", "1440"])
def test_reduced_motion_is_a_still_readable_page(cover, size):
    page = cover(SIZES[size], motion="reduce")
    assert page.evaluate("document.documentElement.classList.contains('cv-calm') && !document.documentElement.classList.contains('cv-film')")
    assert page.evaluate("[...document.querySelectorAll('.cv-stick')].every((s) => getComputedStyle(s).position !== 'sticky')")
    hidden = page.evaluate("""() => [...document.querySelectorAll('.cv-beat, .cv-trip, .cv-tip, .cv-feat, .cv-chip, .cv-partners, .cv-quote, .cv-morph, .cv-last')]
      .filter((e) => getComputedStyle(e).opacity !== '1' || !e.getClientRects().length).map((e) => e.className)""")
    assert hidden == []
    assert page.evaluate("[...document.querySelectorAll('.cv-stage, .cv-stage *')].every((e) => !e.style.transform)")       # nothing moved
    page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
    page.wait_for_timeout(200)
    assert page.evaluate("[...document.querySelectorAll('.cv-stage *')].every((e) => !e.style.transform)")


def test_a_short_screen_gets_the_still_too(cover):
    page = cover({"width": 844, "height": 390})
    assert page.evaluate("GA_COVER.film") is False
    assert page.evaluate("[...document.querySelectorAll('.cv-stick')].every((s) => getComputedStyle(s).position !== 'sticky')")
    assert page.evaluate("[...document.querySelectorAll('.cv-beat')].every((e) => getComputedStyle(e).opacity === '1')")


def test_without_the_script_every_word_and_picture_shows(cover):
    page = cover(PHONE, js=False)
    assert page.evaluate("[...document.querySelectorAll('.cv-beat, .cv-trip, .cv-tip, .cv-feat, .cv-chip, .cv-partners, .cv-quote, .cv-morph')].every((e) => getComputedStyle(e).opacity === '1')")
    assert page.locator(".cv-beat").count() == 3 and all(page.locator(".cv-beat").nth(k).is_visible() for k in range(3))
    assert page.locator(".cv-chip.soon").count() == 3


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("size", ["390", "1440"])
def test_each_screenshot_loads_as_it_nears_in_the_visitors_layout_and_mode(cover, size, scheme):
    page = cover(SIZES[size], scheme)
    page.wait_for_timeout(400)
    assert not [u for u in page.requests if SHOT.search(u) and ("-creators-" in u or "-family-" in u)]       # far below the fold: not yet
    layout = "phone" if size == "390" else "wide"
    for key, p, name, sel in (("book", 0.3, "book", '[data-shot="book"]'), ("head", 0.9, "trail", '[data-shot="trail"]'),
                              ("with", 0.95, "family", f'.cv-{"phone" if layout == "phone" else "laptop"} [data-shot="family"]'),
                              ("creators", 0.9, "creators", '.cv-creators [data-shot="creators"]')):
        _at(page, key, p)
        want = rf"/book-wide-{scheme}-(960|1600)\.webp$" if name == "book" else rf"/{name}-{layout}-{scheme}-({'600' if layout == 'phone' else '960|1440'})\.webp$"
        page.wait_for_function(f"""(() => {{ const im = document.querySelector('{sel} img');
          return im.complete && im.naturalWidth > 0 && new RegExp({want!r}).test(im.currentSrc); }})()""")
    got = [u for u in page.requests if SHOT.search(u)]
    assert all(f"-{scheme}-" in u for u in got), got
    if layout == "phone":
        assert not [u for u in got if "-wide-" in u and "book-" not in u], got          # a phone never downloads the laptop's screens


def test_the_screenshots_follow_the_sites_own_switch(cover):
    page = cover(PHONE, "light", motion="reduce")
    page.evaluate("document.documentElement.dataset.theme = 'dark'")
    page.wait_for_function("document.documentElement.classList.contains('cv-dark')")
    page.evaluate("document.querySelector('.cv-creators [data-shot=\"creators\"]').scrollIntoView({ block: 'center' })")
    page.wait_for_function("""(() => { const im = document.querySelector('.cv-creators [data-shot="creators"] img');
      return im.complete && im.naturalWidth > 0 && im.currentSrc.endsWith('/creators-phone-dark-600.webp'); })()""")
    page.evaluate("delete document.documentElement.dataset.theme")
    page.wait_for_function("document.documentElement.classList.contains('cv-light')")
    page.emulate_media(color_scheme="dark")
    page.wait_for_function("document.documentElement.classList.contains('cv-dark')")
    assert page.evaluate("getComputedStyle(document.body).backgroundColor") == "rgb(7, 11, 20)"


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


def test_a_finger_scrolls_the_film_on_a_phone(cover):
    """The film never holds the page: a finger moves it from anywhere, the pinned booking screen and a device's screen included, and the camera follows."""
    page = cover(PHONE)
    cdp = page.context.new_cdp_session(page)
    for _ in range(4):
        _swipe(page, cdp, 195, 720, 195, 180)
    assert page.evaluate("scrollY") > 1500
    assert int(page.evaluate("document.documentElement.dataset.cvScene")) >= 1
    for key, sel in (("book", ".cv-lens"), ("with", ".cv-phone .cv-screen"), ("tips", ".cv-mapbox")):
        _at(page, key, 0.3)
        page.wait_for_timeout(200)
        x, y, w, h = _box(page, sel)
        before, p0 = page.evaluate("scrollY"), page.evaluate(f"GA_COVER.progress('{key}')")
        cx, cy = x + w / 2, min(y + h / 2, 700)
        _swipe(page, cdp, cx, cy, cx, cy - 300)
        assert page.evaluate("scrollY") > before + 150, sel
        assert page.evaluate(f"GA_COVER.progress('{key}')") > p0, key


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("width", [1440, 1280, 1000, 800, 390, 320])
def test_nothing_scrolls_sideways(cover, width, scheme):
    page = cover({"width": width, "height": 844 if width < 760 else 900}, scheme)
    wide = "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
    for key in ("hero", "book", "head", "with", "tips", "trail", "creators", "end"):
        for p in (0, 0.5, 0.9):
            _at(page, key, p)
            assert page.evaluate(wide), (width, key, p)
    calm = cover({"width": width, "height": 844 if width < 760 else 900}, scheme, motion="reduce")
    for i in range(N):
        _scroll_to_scene(calm, i)
        assert calm.evaluate(wide), (width, "still", i)


def test_a_phone_reads_16px_text_and_taps_48px_targets(cover):
    page = cover(PHONE, motion="reduce")
    small = page.evaluate("""() => [...document.querySelectorAll('main p, main li, main b, main span, .cv-btn, .cv-foot p, .cv-foot nav a, .cv-ill b, .cv-last h2')]
      .filter(e => e.getClientRects().length && e.textContent.trim() && !e.closest('.cv-eyebrow, .cv-soon, .cv-tag, .cv-hint, .cv-stamp, .cv-url'))
      .map(e => [e.textContent.trim().slice(0, 30), parseFloat(getComputedStyle(e).fontSize)]).filter(([, s]) => s < 16)""")
    assert small == []
    eyebrows = page.evaluate("() => [...document.querySelectorAll('.cv-eyebrow')].map(e => parseFloat(getComputedStyle(e).fontSize))")
    assert len(eyebrows) == 4 and min(eyebrows) >= 13                                # all-caps labels only
    soon = page.evaluate("() => [...document.querySelectorAll('.cv-soon')].map(e => [getComputedStyle(e).textTransform, parseFloat(getComputedStyle(e).fontSize)])")
    assert len(soon) == 3 and all(t == "uppercase" and s >= 13 for t, s in soon), soon    # the partners' "Soon" is an all-caps label too
    targets = page.evaluate("""() => [...document.querySelectorAll('.cv-top a, .cv-ctas a, .cv-foot nav a, .cv-close .pf-card a')]
      .filter(e => e.getClientRects().length).map(e => [e.textContent.trim(), e.getBoundingClientRect().height])""")
    assert len(targets) >= 7 and all(h >= 48 for _, h in targets), targets


def test_a_notch_never_covers_the_header_the_story_or_the_close(cover):
    """An iPhone on its side: the notch and the rounded corners take 47 px each side (viewport-fit=cover hands that space to the page)."""
    page = cover({"width": 844, "height": 390}, motion="reduce", insets={"left": 47, "right": 47, "top": 0, "bottom": 21})
    clear = """sel => [...document.querySelectorAll(sel)].filter(e => e.getClientRects().length).map(e => { const r = e.getBoundingClientRect();
      return [e.className || e.tagName, Math.round(r.left), Math.round(r.right)]; })"""
    boxes = page.evaluate(clear, ".cv-top > *, main h1, main h2, main h3, .cv-say, .cv-lens, .cv-frame, .cv-ill, .cv-post, .cv-last, .cv-close .pf-card, .cv-foot > *, .cv-foot nav a")
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


@pytest.mark.parametrize("size", [(320, 568), (390, 844), (1280, 800), (1440, 900)], ids=["320x568", "390x844", "1280x800", "1440x900"])
def test_each_stages_words_clear_the_header_and_its_screen_fits(cover, size):
    w, h = size
    page = cover({"width": w, "height": h})
    head = page.evaluate("Math.max(...[...document.querySelectorAll('.cv-top, .cv-top > *')].map((e) => e.getBoundingClientRect().bottom))")
    for key, p, screen in (("book", 0.5, ".cv-lens"), ("head", 0.3, ".cv-head .cv-deal"), ("with", 0.4, ".cv-with .cv-devices"), ("tips", 0.6, ".cv-mapbox"),
                           ("trail", 0.6, ".cv-trail .cv-deal"), ("creators", 0.2, ".cv-creators .cv-deal")):
        _at(page, key, p)
        x, y, bw, bh = _box(page, f".cv-{key} h2")
        assert y >= head - 0.5 and y + bh <= h, (key, head, y)
        sx, sy, sw, sh = _box(page, screen)
        assert sy + sh <= h + 0.5 and sh >= 0.25 * h and sx >= -0.5 and sx + sw <= w + 0.5, (key, sx, sy, sw, sh)


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
    ratios = page.evaluate(CONTRAST, "main h1, main h1 em, main h2, main h2 em, main h3, .cv-say, .cv-lede, .cv-eyebrow, .cv-beat, .cv-disc, .cv-cap, .cv-ill b, .cv-ill p, .cv-mute, "
                                     ".cv-stops li, .cv-fake-btn, .cv-chip b, .cv-chip-what, .cv-chip-name, .cv-soon, .cv-big, .cv-tip-n, .cv-last h2, .cv-last h2 em, .cv-credit, .cv-foot p")
    assert len(ratios) >= 50 and min(r for _, r in ratios) >= 4.5, sorted(ratios, key=lambda x: x[1])[:4]


@pytest.mark.parametrize("size", ["390", "1440"])
def test_scrolling_the_booking_stage_four_times_slower_makes_no_long_task(cover, size):
    """lessons 2026-10-09: CPU throttled 4x, a long-task observer, the booking stage (the heaviest camera) scrolled through by the wheel."""
    page = cover(SIZES[size])
    _at(page, "book", 0)
    cdp = page.context.new_cdp_session(page)
    cdp.send("Emulation.setCPUThrottlingRate", {"rate": 4})
    page.evaluate("window.__lt = []; new PerformanceObserver((l) => l.getEntries().forEach((e) => window.__lt.push(e.duration))).observe({ entryTypes: ['longtask'] })")
    end = page.evaluate("GA_COVER.yAt('book', 1)")
    while page.evaluate("scrollY") < end - 5:
        page.evaluate("window.scrollBy(0, 40)")
        page.wait_for_timeout(16)
    page.wait_for_timeout(300)
    cdp.send("Emulation.setCPUThrottlingRate", {"rate": 1})
    assert page.evaluate("window.__lt") == []


def test_production_ignores_the_review_switch(cover, monkeypatch):
    """?scene=1&p=0.5 holds the booking stage halfway for the review tools; without data-debug (production) the scroll decides."""
    page = cover(DESKTOP, query="?scene=1&p=0.5")
    page.wait_for_function("GA_COVER.progress('book') === 0.5")
    monkeypatch.setattr(cover_page, "debug", lambda: False)
    page = cover(DESKTOP, query="?scene=1&p=0.5")
    page.wait_for_timeout(300)
    assert page.evaluate("GA_COVER.progress('book')") == 0 and page.evaluate("GA_COVER.debug") is False


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
