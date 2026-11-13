"""F-227, the cover rebuilt as one stage (docs/decisions.md D-426 on), in a real browser: the opening shows at once in the visitor's day or night;
one product frame stays pinned (CSS sticky) while the three parts pass it, beside it on a laptop and under it on a phone; when the part changes the
outgoing screen fades and the incoming one settles in on the Liquid spring, and each screen's moments (the words, the squares, the find lighting up,
the hearts landing, the card forming) play once on the same springs (D-444); under reduced motion the frame still pins and the screens swap with a
plain fade, every moment at rest; a short screen, ?still or no script get the still, each screen with its words; nothing follows the scroll (no
frame asked for, no transform written while scrolling) and a CPU four times slower makes no long task; a finger scrolls it; nothing scrolls sideways
from 320 to 1440; every word reads at 4.5:1 and a phone gets its type floor and 48 px targets, in both modes; a notch covers nothing."""
import pytest

from tests_browser.helpers import DESKTOP, PHONE
from tests_browser.look import audit

SIZES = {"390": PHONE, "1440": DESKTOP}
READY = "!!window.GA_COVER"
SPRING = "cubic-bezier(0.3, 1.12, 0.4, 1)"


@pytest.fixture
def cover(browser, base_url):
    made = []

    def open_cover(viewport=DESKTOP, scheme="light", motion="no-preference", init=None, query="", insets=None, js=True):
        phone = viewport["width"] < 760
        ctx = browser.new_context(viewport=viewport, color_scheme=scheme, reduced_motion=motion, has_touch=phone, is_mobile=phone, java_script_enabled=js)
        ctx.set_default_timeout(15000)
        made.append(ctx)
        page = ctx.new_page()
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


def _show(page, n):
    """Scroll the real page until part n's words cross cover.js's line (the middle of a laptop's screen, 70% down a phone's) and it shows."""
    page.evaluate("""n => { const c = document.querySelector(`.cv-ch[data-n="${n}"]`), top = c.getBoundingClientRect().top + scrollY;
      window.scrollTo(0, innerWidth >= 1100 ? top : top - innerHeight * 0.6); }""", str(n))
    page.wait_for_function(f"document.querySelector('.cv-stage').dataset.part === '{n}'")


def _box(page, sel):
    return page.evaluate("s => { const r = document.querySelector(s).getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; }", sel)


def _opacity(page, sel):
    return page.evaluate("s => [...document.querySelectorAll(s)].map((e) => getComputedStyle(e).opacity)", sel)


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("size", ["390", "1440"])
def test_the_opening_shows_at_once_in_day_or_night(cover, size, scheme):
    page = cover(SIZES[size], scheme)
    assert page.locator("h1").inner_text().replace("\n", " ").strip() == "Compare the whole trip. Choose it together."
    vw, vh = SIZES[size]["width"], SIZES[size]["height"]
    for sel in (".cv-hero h1", ".cv-lede", ".cv-hero .cv-ctas"):
        x, y, w, h = _box(page, sel)
        assert y + h <= vh and abs(x + w / 2 - vw / 2) <= 2, (sel, x, y, w, h)          # the line and the doors on the first screen, centred
    doors = page.evaluate("[...document.querySelectorAll('.cv-hero .cv-btn')].map((b) => b.getBoundingClientRect()).map((r) => [r.left, r.right])")
    assert abs((min(l for l, _ in doors) + max(r for _, r in doors)) / 2 - vw / 2) <= 2, doors
    _, band_top, _, _ = _box(page, ".cv-band")
    assert band_top < vh                                                             # the places are already showing
    assert page.evaluate("getComputedStyle(document.body).backgroundColor") == ("rgb(0, 0, 0)" if scheme == "dark" else "rgb(242, 242, 245)")
    sky = page.evaluate("getComputedStyle(document.querySelector('.pa[data-art=\"san-diego\"]')).getPropertyValue('--sky1').trim()")
    assert sky == ("#0A1830" if scheme == "dark" else "#D9ECFA")                     # the place's night palette in dark mode, its day one in light


def test_the_sites_own_switch_turns_the_cover_and_its_art_dark(cover):
    page = cover(DESKTOP, "light", init="try { localStorage.setItem('ga-mode', 'dark'); } catch (e) {}")
    assert page.evaluate("document.documentElement.dataset.mode") == "dark"
    assert page.evaluate("getComputedStyle(document.body).backgroundColor") == "rgb(0, 0, 0)"
    assert page.evaluate("getComputedStyle(document.querySelector('.pa[data-art=\"lake-tahoe\"]')).getPropertyValue('--sky1').trim()") == "#081428"


@pytest.mark.parametrize("size", ["390", "1440"])
def test_the_frame_stays_pinned_while_the_parts_pass_and_swaps_its_screen(cover, size):
    page = cover(SIZES[size])
    tops = []
    for n in (1, 2, 3, 2, 1):
        _show(page, n)
        page.wait_for_timeout(700)
        tops.append(_box(page, ".cv-frame")[1])
        assert _opacity(page, ".cv-L") == ["1" if k == n else "0" for k in (1, 2, 3)], n
        assert page.evaluate("[...document.querySelectorAll('.cv-L')].map((l) => getComputedStyle(l).visibility)") == [
            "visible" if k == n else "hidden" for k in (1, 2, 3)], n                    # a faded screen is not read, pointed at or tabbed to
        frame = _box(page, ".cv-frame")
        words = _box(page, f".cv-ch{n} h2")
        vh = SIZES[size]["height"]
        assert 0 <= words[1] and words[1] + words[3] <= vh, (n, words)                 # the part's words are on the screen with it
        if size == "390":
            assert words[1] >= frame[1] + frame[3], (n, words, frame)                  # under the pinned frame, not behind it
        else:
            assert words[0] + words[2] <= frame[0]                                     # beside it
    assert max(tops) - min(tops) <= 1, tops                                           # pinned: the frame never moved
    assert 0 <= tops[0] and tops[0] + _box(page, ".cv-frame")[3] <= SIZES[size]["height"]


@pytest.mark.parametrize("size", ["390", "1440"])
def test_the_incoming_screen_settles_in_on_the_spring_and_the_outgoing_one_fades(cover, size):
    """D-444: Liquid on the phone and the laptop alike (the cover's exception to the calm desktop, D-401), started by a class, on the tokens."""
    page = cover(SIZES[size])
    _show(page, 1)
    page.wait_for_timeout(500)
    _show(page, 2)
    styles = page.evaluate("""() => { const s = (q) => getComputedStyle(document.querySelector(q));
      return [s('.cv-L2').animationName, s('.cv-L2').animationDuration, s('.cv-L2').animationTimingFunction, s('.cv-L1').transitionProperty, s('.cv-L1').transitionDuration]; }""")
    assert styles == ["cv-settle", "0.38s", SPRING, "opacity, visibility", "0.24s, 0s"], styles
    page.wait_for_timeout(600)
    assert page.evaluate("getComputedStyle(document.querySelector('.cv-L2')).transform") in ("none", "matrix(1, 0, 0, 1, 0, 0)")      # settled, at rest


def test_each_screens_moments_play_once_on_the_springs(cover):
    page = cover(DESKTOP)
    assert not page.evaluate("document.querySelector('.cv-L1').classList.contains('go')")       # nothing plays before the frame is on screen
    _show(page, 1)
    page.wait_for_function("document.querySelector('.cv-L1').classList.contains('go')")
    page.wait_for_timeout(2900)
    assert set(_opacity(page, ".cv-L1 :is(.cv-w, .cv-c, .cv-plus, .cv-disc, .cv-stripw)")) == {"1"}
    lit = page.evaluate("(() => { const s = getComputedStyle(document.querySelector('.cv-c.lit')); return [s.backgroundColor, s.animationName, s.animationTimingFunction]; })()")
    assert lit[0] == "rgb(11, 11, 13)" and lit[1] == "cv-pop, cv-lit" and SPRING in lit[2], lit         # the find lights up on the spring
    _show(page, 2)
    page.wait_for_timeout(2000)
    hearts = page.evaluate("[...document.querySelectorAll('.cv-L2 .cv-hf')].map((h) => [getComputedStyle(h).opacity, getComputedStyle(h).animationName, getComputedStyle(h).animationTimingFunction])")
    assert hearts == [["1", "cv-land", SPRING]] * 4, hearts
    _show(page, 3)
    page.wait_for_timeout(1200)
    assert page.evaluate("getComputedStyle(document.querySelector('.cv-ig')).animationName") == "cv-form" and _opacity(page, ".cv-ig, .cv-creator") == ["1", "1"]
    _show(page, 1)                                                                       # back again: the moments do not replay
    states = page.evaluate("document.querySelector('.cv-L1 .cv-c').getAnimations().map((a) => a.playState)")
    assert states == ["finished"], states


@pytest.mark.parametrize("size", ["390", "1440"])
def test_reduced_motion_pins_the_frame_and_swaps_with_a_plain_fade(cover, size):
    page = cover(SIZES[size], motion="reduce")
    assert page.evaluate("document.documentElement.classList.contains('cv-film')")
    tops = []
    for n in (1, 2, 3):
        _show(page, n)
        page.wait_for_timeout(400)
        tops.append(_box(page, ".cv-frame")[1])
        assert _opacity(page, ".cv-L") == ["1" if k == n else "0" for k in (1, 2, 3)]
    assert max(tops) - min(tops) <= 1
    names = page.evaluate("[...document.querySelectorAll('.cv-L, .cv-L *')].map((e) => getComputedStyle(e).animationName).filter((n) => n !== 'none')")
    assert names == []                                                                  # no spring, no moment: a plain fade
    assert page.evaluate("(() => { const s = getComputedStyle(document.querySelector('.cv-L1')); return [s.transitionProperty, s.transitionDuration, s.transitionTimingFunction]; })()") == ["opacity, visibility", "0.12s, 0s", "linear, linear"]
    at_rest = ".cv-L1 :is(.cv-w, .cv-c, .cv-disc), .cv-L2 :is(.cv-hf, .cv-bub), .cv-L3 :is(.cv-ig, .cv-creator)"
    assert set(_opacity(page, at_rest)) == {"1"}
    assert page.evaluate("getComputedStyle(document.querySelector('.cv-c.lit')).backgroundColor") == "rgb(11, 11, 13)"


def _still_order(page):
    """Each screen's top, its own words' top and bottom: [(words top, words bottom, screen top, screen bottom, screen position, opacity)]."""
    return page.evaluate("""() => [1, 2, 3].map((n) => { const w = document.querySelector(`.cv-ch${n} .cv-card`).getBoundingClientRect(),
      l = document.querySelector(`.cv-L${n}`), r = l.getBoundingClientRect(), s = getComputedStyle(l);
      return [w.top + scrollY, w.bottom + scrollY, r.top + scrollY, r.bottom + scrollY, s.position, s.opacity, w.left, r.left]; })""")


@pytest.mark.parametrize("how", ["short phone", "?still", "no script"])
def test_a_short_screen_still_or_no_script_gets_each_screen_with_its_words(cover, how):
    viewport = {"short phone": {"width": 390, "height": 560}, "?still": DESKTOP, "no script": PHONE}[how]
    page = cover(viewport, query="?still" if how == "?still" else "", js=how != "no script")
    rows = _still_order(page)
    assert all(r[4] == "static" and r[5] == "1" for r in rows), rows
    for k, (wt, wb, lt, lb, _, _, wl, ll) in enumerate(rows):
        if viewport["width"] >= 1100:
            assert ll > wl and abs((wt + wb) / 2 - (lt + lb) / 2) < (lb - lt) / 2, rows     # beside its words
        else:
            assert lt >= wb and (k == 2 or rows[k + 1][0] >= lb), rows                       # under its words, before the next part


def test_nothing_follows_the_scroll(cover):
    """D-427: while the whole page is scrolled, no frame is asked for and no transform is written; every move is a CSS animation a class started."""
    count = """window.__raf = 0; const raf = window.requestAnimationFrame.bind(window);
      window.requestAnimationFrame = (f) => { window.__raf++; return raf(f); };"""
    page = cover(DESKTOP, init=count)
    page.wait_for_timeout(500)
    page.evaluate("window.__raf = 0")
    end = page.evaluate("document.documentElement.scrollHeight - innerHeight")
    page.mouse.move(700, 450)
    while page.evaluate("scrollY") < end - 5:
        page.mouse.wheel(0, 120)
        page.wait_for_timeout(16)
    page.wait_for_timeout(300)
    assert page.evaluate("window.__raf") == 0
    assert page.evaluate("[...document.querySelectorAll('main [style*=\"transform\"], main [style*=\"opacity\"]')].length") == 0
    assert page.evaluate("document.querySelector('.cv-stage').dataset.part") == "3"


@pytest.mark.parametrize("size", ["390", "1440"])
def test_scrolling_the_stage_four_times_slower_makes_no_long_task(cover, size):
    """lessons 2026-10-09: CPU throttled 4x, a long-task observer, the whole stage scrolled through (scripts/cover_fps.py prints the frame rate)."""
    page = cover(SIZES[size])
    page.evaluate("window.scrollTo(0, document.querySelector('.cv-stage').getBoundingClientRect().top + scrollY - innerHeight)")
    page.wait_for_timeout(300)
    cdp = page.context.new_cdp_session(page)
    cdp.send("Emulation.setCPUThrottlingRate", {"rate": 4})
    page.evaluate("window.__lt = []; new PerformanceObserver((l) => l.getEntries().forEach((e) => window.__lt.push(e.duration))).observe({ entryTypes: ['longtask'] })")
    end = page.evaluate("(() => { const s = document.querySelector('.cv-stage'); return s.getBoundingClientRect().bottom + scrollY; })()")
    while page.evaluate("scrollY") < end:
        page.evaluate("window.scrollBy(0, 40)")
        page.wait_for_timeout(16)
    page.wait_for_timeout(300)
    cdp.send("Emulation.setCPUThrottlingRate", {"rate": 1})
    assert page.evaluate("window.__lt") == []


def _swipe(page, cdp, x0, y0, x1, y1, steps=12):
    """A finger: touch start, a dozen moves a frame apart, touch end (synthetic scroll gestures do not scroll headless Chromium, lessons 2026-11-07)."""
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x0, "y": y0}]})
    for k in range(1, steps + 1):
        cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x0 + (x1 - x0) * k / steps, "y": y0 + (y1 - y0) * k / steps}]})
        page.wait_for_timeout(16)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    page.wait_for_timeout(300)


def test_a_finger_scrolls_the_stage_on_a_phone_starting_on_the_frame(cover):
    page = cover(PHONE)
    _show(page, 1)
    cdp = page.context.new_cdp_session(page)
    seen = set()
    for _ in range(12):
        _swipe(page, cdp, 195, 400, 195, 120)                                            # the finger starts on the pinned frame
        seen.add(page.evaluate("document.querySelector('.cv-stage').dataset.part"))
    assert seen >= {"2", "3"}


@pytest.mark.parametrize("width", [1440, 1280, 1000, 800, 390, 320])
def test_nothing_scrolls_sideways(cover, width):
    vp = {"width": width, "height": 844 if width < 760 else 900}
    wide = "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
    page = cover(vp)
    for n in (1, 2, 3):
        _show(page, n)
        assert page.evaluate(wide), (width, n)
    still = cover(vp, query="?still")
    assert still.evaluate(wide), (width, "still")


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("size", ["390", "1440"])
def test_every_word_of_every_screen_reads_and_a_phone_can_tap(cover, size, scheme):
    """tests_browser/look.py's audit on the still, where all three screens show at once: 4.5:1 text in both modes, the phone's type floor, 48 px
    targets, no glass."""
    page = cover(SIZES[size], scheme, query="?still")
    seen = audit(page)
    assert seen["wide"] <= 1 and not seen["low"] and not seen["tiny"] and not seen["small"] and not seen["glass"], seen


def test_a_notch_never_covers_the_header_the_story_or_the_close(cover):
    """An iPhone on its side: the notch and the rounded corners take 47 px each side."""
    page = cover({"width": 844, "height": 390}, insets={"left": 47, "right": 47, "top": 0, "bottom": 21})
    boxes = page.evaluate("""() => [...document.querySelectorAll('.cv-top > *, main h1, main h2, .cv-say, .cv-L, .cv-band ~ *, .cv-close .cv-ctas, .cv-foot > *')]
      .filter((e) => e.getClientRects().length).map((e) => { const r = e.getBoundingClientRect(); return [e.className || e.tagName, Math.round(r.left), Math.round(r.right)]; })""")
    assert len(boxes) >= 15 and all(l >= 47 and r <= 844 - 47 for _, l, r in boxes), [b for b in boxes if b[1] < 47 or b[2] > 797]


@pytest.mark.parametrize("width", [390, 360, 320])
def test_a_phone_shows_the_early_preview_label_beside_the_logo_and_sign_in(cover, width):
    page = cover({"width": width, "height": 700})
    boxes = page.evaluate("() => [...document.querySelectorAll('.cv-top > *')].map(e => { const r = e.getBoundingClientRect(); return [e.className.split(' ')[0], r.left, r.top, r.right, r.bottom]; })")
    assert sorted(b[0] for b in boxes) == ["cv-btn", "cv-tag", "ga-brand"]
    assert all(0 <= l and r <= width for _, l, _, r, _ in boxes), boxes
    for i, (_, l0, t0, r0, b0) in enumerate(boxes):
        for _, l1, t1, r1, b1 in boxes[i + 1:]:
            assert r0 <= l1 or r1 <= l0 or b0 <= t1 or b1 <= t0, boxes
    assert page.evaluate("document.querySelector('.cv-top .cv-btn').getBoundingClientRect().height") >= 48


@pytest.mark.parametrize("size", ["390", "1440"])
def test_the_doors_open_their_pages(cover, base_url, size):
    page = cover(SIZES[size])
    page.locator(".cv-hero a", has_text="See how it works").click()
    page.wait_for_function("location.hash === '#compare'")
    page.wait_for_timeout(400)
    h2, frame = page.evaluate("[document.querySelector('#compare h2').getBoundingClientRect().top, document.querySelector('.cv-frame').getBoundingClientRect().bottom]")
    assert h2 < SIZES[size]["height"]
    if size == "390":
        assert h2 >= frame - 1, (h2, frame)      # the part's words land below the pinned frame, not under it (D-429's line is there)
    page.locator(".cv-ch3 a", has_text="For creators").click()
    page.wait_for_url("**/for-creators")
    page.goto(f"{base_url}/")
    page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
    page.locator(".cv-close .cv-ctas a", has_text="Start a trip").click()
    page.wait_for_url("**/start**")


@pytest.mark.parametrize("size", [(390, 700), (390, 844), (800, 800), (900, 1000), (1100, 700), (1280, 800), (1440, 900)],
                         ids=["390x700", "390x844", "800x800", "900x1000", "1100x700", "1280x800", "1440x900"])
def test_each_screen_fits_its_frame(cover, size):
    """Nothing in a screen is cut off by the frame, on a short phone, a tablet or a laptop (the sweep found the tablet's calendar cut off)."""
    w, h = size
    page = cover({"width": w, "height": h})
    for n in (1, 2, 3):
        _show(page, n)
        over = page.evaluate("""n => { const f = document.querySelector('.cv-frame').getBoundingClientRect();
          return Math.max(...[...document.querySelectorAll(`.cv-L${n} *`)].filter((e) => e.getClientRects().length).map((e) => e.getBoundingClientRect().bottom)) - f.bottom; }""", n)
        assert over <= 0, (size, n, over)
