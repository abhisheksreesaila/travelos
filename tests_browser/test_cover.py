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
ZOOM = "cubic-bezier(0.22, 1, 0.36, 1)"
INDIGO, PINK, ORANGE = "rgb(67, 56, 202)", "rgb(201, 42, 94)", "rgb(194, 65, 12)"      # tokens.css --k-flight, --k-food, --k-tix: each part's colour


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
    assert page.evaluate("getComputedStyle(document.body).backgroundColor") == "rgb(242, 242, 245)"      # D-460: light by default, whatever the system says
    sky = page.evaluate("getComputedStyle(document.querySelector('.pa[data-art=\"san-diego\"]')).getPropertyValue('--sky1').trim()")
    assert sky == "#D9ECFA"                                                          # the place's day palette (dark is the button's: the next test)


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
        page.wait_for_timeout(1400)      # D-459: about a second for the change
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
    assert styles == ["cv-settle", "1.02s", ZOOM, "opacity, visibility", "1.02s, 0s"], styles      # D-459: one slow, soft length, no overshoot
    page.wait_for_timeout(1400)
    assert page.evaluate("getComputedStyle(document.querySelector('.cv-L2')).transform") in ("none", "matrix(1, 0, 0, 1, 0, 0)")      # settled, at rest


def test_each_screens_moments_play_once_on_the_springs(cover):
    page = cover(DESKTOP)
    assert not page.evaluate("document.querySelector('.cv-L1').classList.contains('go')")       # nothing plays before the frame is on screen
    _show(page, 1)
    page.wait_for_function("document.querySelector('.cv-L1').classList.contains('go')")
    page.wait_for_timeout(2900)
    assert set(_opacity(page, ".cv-L1 :is(.cv-w, .cv-c, .cv-plus, .cv-disc, .cv-stripw)")) == {"1"}
    lit = page.evaluate("(() => { const s = getComputedStyle(document.querySelector('.cv-c.lit')); return [s.backgroundColor, s.animationName, s.animationTimingFunction]; })()")
    assert lit[0] == INDIGO and lit[1] == "cv-pop, cv-lit" and SPRING in lit[2], lit                   # the find lights up on the spring, in part 1's colour
    _show(page, 2)
    page.wait_for_timeout(2000)
    hearts = page.evaluate("[...document.querySelectorAll('.cv-L2 .cv-hf')].map((h) => [getComputedStyle(h).opacity, getComputedStyle(h).animationName, getComputedStyle(h).animationTimingFunction])")
    assert hearts == [["1", "cv-land", SPRING]] * 4, hearts
    _show(page, 3)
    page.wait_for_timeout(1200)
    assert page.evaluate("getComputedStyle(document.querySelector('.cv-ig')).animationName") == "cv-form, cv-lift" and _opacity(page, ".cv-ig, .cv-creator") == ["1", "1"]
    _show(page, 1)                                                                       # back again: the moments do not replay
    states = page.evaluate("document.querySelector('.cv-L1 .cv-c').getAnimations().map((a) => a.playState)")
    assert states == ["finished"], states


@pytest.mark.parametrize("size", ["390", "1440"])
def test_the_screen_changes_when_its_words_arrive_and_the_other_words_wait_dimmed(cover, size):
    """D-456 (founder 2026-11-13: "the text comes a little slowly and the information a little early; it has to be in sync"): the part changes
    when its words (the card, not the tall block around it) reach the line, so at the change they are on the screen in full; the words of the
    other parts wait faint on a laptop and brighten as they land (D-459) (stacked, the words come in under the frame and none wait dimmed)."""
    page = cover(SIZES[size])
    vh, part, seen = SIZES[size]["height"], "1", []
    top = page.evaluate("document.querySelector('.cv-stage').getBoundingClientRect().top + scrollY")
    y = top - vh
    while part != "3":
        y += 30
        page.evaluate(f"window.scrollTo(0, {y})")
        page.wait_for_timeout(40)
        now = page.evaluate("document.querySelector('.cv-stage').dataset.part")
        if now != part:
            part = now
            seen.append((now, _box(page, f".cv-ch{now} h2")))
    assert [n for n, _ in seen] == ["2", "3"], seen
    for n, (_, t, _, h) in seen:
        assert 0 <= t and t + h <= vh, (n, t, h, vh)                                   # the new headline is on the screen at the change
    page.wait_for_timeout(1400)
    assert _opacity(page, ".cv-card") == (["0", "0", "1"] if size == "1440" else ["1", "1", "1"])      # D-459: the words land, they unfade (never faint: 4.5:1 or not shown)


def test_one_trip_carries_the_story_from_part_to_part(cover):
    """D-456: the lit square, the family's square and the card to post are one trip; only it is named for the view transition that changes
    the part, so it grows from one into the next while the rest of the screen cross-fades."""
    count = """window.__vt = 0; const start = document.startViewTransition.bind(document);
      document.startViewTransition = (f) => { window.__vt++; return start(f); };"""
    page = cover(DESKTOP, init=count)
    named = "[...document.querySelectorAll('.cv-stage *')].filter((e) => getComputedStyle(e).viewTransitionName === 'cv-find').map((e) => e.className)"
    for n, cls in (("1", "cv-c lit"), ("2", "cv-sq"), ("3", "cv-ig"), ("1", "cv-c lit")):
        _show(page, n)
        page.wait_for_timeout(500)
        assert page.evaluate(named) == [cls], n
    assert page.evaluate("getComputedStyle(document.documentElement).viewTransitionName") == "none"      # the page itself is never captured
    assert page.evaluate("window.__vt") == 3                                             # each change of part was one transition


def test_a_quick_reader_back_and_forth_lands_on_the_part_in_front_of_them(cover):
    """A second change while a transition is starting wins: the frame ends on the part whose words are at the line."""
    page = cover(DESKTOP)
    _show(page, 1)
    page.evaluate("""() => { const c = (n) => document.querySelector(`.cv-ch${n}`).getBoundingClientRect().top + scrollY;
      window.scrollTo(0, c(2)); setTimeout(() => window.scrollTo(0, c(1)), 30); }""")
    page.wait_for_timeout(1800)
    assert page.evaluate("document.querySelector('.cv-stage').dataset.part") == "1"
    assert _opacity(page, ".cv-L") == ["1", "0", "0"]


def test_each_part_marks_what_its_headline_says_in_its_own_colour(cover):
    """D-457 (founder 2026-11-13: "everything is a number and a place; what am I looking at?"): a phrase of the headline is marked at the moment
    the screen shows it. Compare: the places, then the dates pass; the total stays, indigo. Plan it together: the hearts, then the owner's
    This one, pink. Leave a trail: the card to post, then the creator's trip, orange."""
    page = cover(DESKTOP)
    _show(page, 1)
    page.wait_for_timeout(1000)                                                           # the first beat: every place
    assert page.evaluate("getComputedStyle(document.querySelector('.cv-pl')).animationName") == "cv-glow"
    assert page.evaluate("getComputedStyle(document.querySelector('.cv-ch1 .b1')).animationName") == "cv-pass"
    page.wait_for_timeout(2400)
    css = "([q, p]) => getComputedStyle(document.querySelector(q))[p]"
    assert page.evaluate(css, [".cv-c.lit", "backgroundColor"]) == INDIGO
    assert [page.evaluate(css, [f".cv-ch1 .b{k}", "backgroundSize"]).split()[0] for k in (1, 2, 3)] == ["0%", "0%", "100%"]
    _show(page, 2)
    page.wait_for_timeout(2600)
    assert page.evaluate(css, [".cv-pill", "backgroundColor"]) == PINK and set(page.evaluate(
        "[...document.querySelectorAll('.cv-hb')].map((h) => getComputedStyle(h).backgroundColor)")) == {PINK}
    _show(page, 3)
    page.wait_for_timeout(1800)
    assert ORANGE in page.evaluate(css, [".cv-ig", "boxShadow"]) and ORANGE in page.evaluate(css, [".cv-crow", "boxShadow"])


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
    assert page.evaluate("getComputedStyle(document.querySelector('.cv-c.lit')).backgroundColor") == INDIGO      # the emphasis at rest (D-457)
    assert page.evaluate("getComputedStyle(document.querySelector('.cv-ch1 .cv-hl.b3')).backgroundSize").startswith("100% ")


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
    end = page.evaluate("""(() => { const s = document.querySelector('.cv-stage');      // the stage's end, or the page's if it is shorter
      return Math.min(s.getBoundingClientRect().bottom + scrollY, document.documentElement.scrollHeight - innerHeight) - 1; })()""")
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
    assert sorted(b[0] for b in boxes) == ["cv-btn", "cv-nav", "cv-tag", "ga-brand"]      # D-458: the nav is a row of its own under the logo
    assert all(0 <= l and r <= width for _, l, _, r, _ in boxes), boxes
    for i, (_, l0, t0, r0, b0) in enumerate(boxes):
        for _, l1, t1, r1, b1 in boxes[i + 1:]:
            assert r0 <= l1 or r1 <= l0 or b0 <= t1 or b1 <= t0, boxes
    assert page.evaluate("document.querySelector('.cv-top .cv-btn').getBoundingClientRect().height") >= 48
    tops = {b[0]: b[2] for b in boxes}
    assert abs(tops["cv-btn"] - tops["ga-brand"]) < 16, boxes                          # Sign in stays beside the logo (D-458)
    links = page.evaluate("[...document.querySelectorAll('.cv-nav a')].map(a => a.getBoundingClientRect().top)")
    assert max(links) - min(links) < 1, links                                          # the nav is one row: Creators · Community · Plan a trip


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
    page.wait_for_url("**/signin")                                   # D-462: sign in, then / decides (the matrix or the trip)
    page.goto(f"{base_url}/")
    page.locator(".cv-nav a", has_text="Community trips").click()
    page.wait_for_url("**/community")


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


# ---------- F-232: the cover, world class (docs/decisions.md D-470 on) ----------

WORDS = """() => { const out = [], cv = document.createElement('canvas').getContext('2d', {willReadFrequently: true});
  const rgb = (c) => { cv.clearRect(0, 0, 1, 1); cv.fillStyle = '#000'; cv.fillStyle = c; cv.fillRect(0, 0, 1, 1); return [...cv.getImageData(0, 0, 1, 1).data].slice(0, 3); };
  const take = (e, text) => { const r = e.getBoundingClientRect(), card = e.closest('.cv-card');
    if (card && getComputedStyle(card).opacity !== '1') return;                      // the words of a part that is not on the frame are not on the screen
    const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
    if (!hit || !(e === hit || e.contains(hit))) return;                              // words under the pinned frame are not on the screen either
    if (r.width && r.height && r.top >= 0 && r.bottom <= innerHeight) out.push([text, r.left, r.top, r.width, r.height, rgb(getComputedStyle(e).color)]); };
  document.querySelectorAll('.cv-hero h1 .cv-hw, .cv-hero .cv-lede, .cv-nav a').forEach((e) => take(e, e.textContent.trim()));
  document.querySelectorAll('.cv-ch .cv-card :is(h2, .cv-say, .cv-note, .cv-n)').forEach((e) => take(e, e.textContent.trim().slice(0, 24)));
  document.querySelectorAll('.cv-close h2, .cv-close h2 em').forEach((e) => take(e, e.textContent.trim().slice(0, 24)));
  return out; }"""
HIDE = "* { color: transparent !important; text-decoration-color: transparent !important; } .cv-hl, .cv-n, .cv-st { background: none !important; }"


def _lum(rgb):
    lin = [(v / 255 / 12.92) if v / 255 <= 0.03928 else ((v / 255 + 0.055) / 1.055) ** 2.4 for v in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _worst_ratio(shot, box, ink):
    """The lowest contrast between the text colour and any pixel painted where the text sits (the page drawn without its text)."""
    from PIL import Image
    import io
    im = Image.open(io.BytesIO(shot)).convert("RGB")
    _, x, y, w, h, _ = box
    crop = im.crop((int(x), int(y), int(x + w) + 1, int(y + h) + 1))
    worst = 99.0
    for px in set(getattr(crop, 'get_flattened_data', crop.getdata)()):
        a, b = _lum(ink), _lum(px)
        worst = min(worst, (max(a, b) + 0.05) / (min(a, b) + 0.05))
    return worst


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("size", ["390", "1440"])
def test_every_word_on_the_sky_the_washes_and_the_dusk_reads_at_4_5_to_1(cover, size, scheme):
    """D-472, D-474: the audit skips text over a gradient, so this one reads what is painted under each word (the page drawn with its text hidden):
    the opening's sky, clouds and sun, each part's wash and the close's dusk. Reduced motion, so the scene stands still."""
    page = cover(SIZES[size], scheme, motion="reduce", init="try { localStorage.setItem('ga-mode', '%s'); } catch (e) {}" % scheme if scheme == "dark" else None)
    low = []

    def sweep(where):
        words = page.evaluate(WORDS)
        page.add_style_tag(content=HIDE)
        shot = page.screenshot()
        page.evaluate("document.querySelector('style:last-of-type') && [...document.querySelectorAll('style')].pop().remove()")
        for w in words:
            ratio = _worst_ratio(shot, w, w[5])
            if ratio < 4.5:
                low.append((where, w[0], round(ratio, 2)))
        return len(words)

    assert sweep("opening") >= 8
    for n in (1, 2, 3):
        _show(page, n)
        page.wait_for_timeout(500)
        assert sweep(f"part {n}") >= 3
    page.evaluate("document.querySelector('.cv-close').scrollIntoView()")
    page.wait_for_timeout(300)
    assert sweep("close") >= 2
    assert not low, low


GREEN = "rgb(21, 128, 61)"       # tokens.css --k-car: the booked pill


def test_the_find_is_booked_in_the_sandbox_and_the_dots_move_on(cover):
    """D-470: after the find lights up, Book it appears, is pressed, turns green and says Booked; the bar's dots go from Compare to Book."""
    page = cover(DESKTOP)
    _show(page, 1)
    page.wait_for_timeout(1200)
    assert page.evaluate("[getComputedStyle(document.querySelector('.cv-bk1')).opacity, getComputedStyle(document.querySelector('.cv-bk2')).opacity]") == ["1", "0"]
    assert page.evaluate("getComputedStyle(document.querySelector('.cv-L1 .cv-sn.d1')).width") == "21px"            # Compare is still the long dot
    page.wait_for_timeout(5200)
    assert page.evaluate("[getComputedStyle(document.querySelector('.cv-bk1')).opacity, getComputedStyle(document.querySelector('.cv-bk2')).opacity]") == ["0", "1"]
    assert page.evaluate("getComputedStyle(document.querySelector('.cv-book')).backgroundColor") == GREEN
    assert page.evaluate("[...document.querySelectorAll('.cv-L1 .cv-sn')].map((d) => getComputedStyle(d).width)") == ["9px", "21px", "9px", "9px"]      # Book is the long one now


def test_the_totals_count_up_and_end_on_the_real_text(cover):
    """D-471: the family's total counts up from $0 in a pseudo-element while the page's own text waits; at the end the count is gone and the text is back."""
    page = cover(DESKTOP)
    _show(page, 2)
    page.wait_for_timeout(1100)                                                             # a second in: counting (delay 1.4 spring lengths, then 2.4 of them)
    mid = page.evaluate("(() => { const n = document.querySelector('.cv-L2 .cv-num'); return [getComputedStyle(n, '::after').content, getComputedStyle(n.firstChild).color]; })()")
    assert mid[0] not in ('"$2,190"', "none", "normal") and mid[0].startswith('"$') and mid[1] == "rgba(0, 0, 0, 0)", mid
    page.wait_for_timeout(2400)
    done = page.evaluate("(() => { const n = document.querySelector('.cv-L2 .cv-num'); return [getComputedStyle(n, '::after').opacity, getComputedStyle(n.firstChild).color, n.textContent]; })()")
    assert done == ["0", "rgb(11, 11, 13)", "$2,190"], done


def test_a_tap_throws_confetti_and_a_second_tap_throws_it_again(cover):
    """D-475: a heart, "This one" and Booked answer a tap; two class names for one animation so the second tap restarts it. Pressing swells them (scale)."""
    page = cover(DESKTOP)
    _show(page, 2)
    page.wait_for_timeout(2600)
    heart = page.locator(".cv-L2 .cv-hf").first
    names = []
    for _ in range(2):
        heart.dispatch_event("pointerdown")
        names.append(page.evaluate("getComputedStyle(document.querySelector('.cv-L2 .cv-hf'), '::after').animationName"))
    assert names == ["cv-burst-a", "cv-burst-b"], names
    box = heart.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down()
    page.wait_for_timeout(300)
    assert float(page.evaluate("getComputedStyle(document.querySelector('.cv-L2 .cv-hf')).scale")) > 1.1
    page.mouse.up()


def test_each_part_washes_the_stage_in_its_colour_and_never_past_it(cover):
    """D-474: wash 1 is always under; 2 and 3 fade in over it as their part shows; the washes live inside the stage (not over the footer)."""
    page = cover(DESKTOP)
    op = "[...document.querySelectorAll('.cv-wash')].map((w) => getComputedStyle(w).opacity)"
    for n, want in ((1, ["1", "0", "0"]), (2, ["1", "1", "0"]), (3, ["1", "1", "1"]), (2, ["1", "1", "0"]), (1, ["1", "0", "0"])):
        _show(page, n)
        page.wait_for_timeout(1300)
        assert page.evaluate(op) == want, n
    page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
    page.wait_for_timeout(300)
    inside = page.evaluate("""() => { const st = document.querySelector('.cv-stage').getBoundingClientRect();
      return [...document.querySelectorAll('.cv-wash')].map((w) => w.getBoundingClientRect().bottom <= st.bottom + 1); }""")
    assert inside == [True, True, True]
    foot = page.evaluate("(() => { const f = document.querySelector('.cv-foot > p').getBoundingClientRect(); return document.elementFromPoint(f.left + 20, f.top + f.height / 2).closest('footer') !== null; })()")
    assert foot


@pytest.mark.parametrize("size", ["390", "1440"])
def test_the_scene_moves_with_motion_allowed_and_stands_still_without(cover, size):
    """D-472: clouds, sea, sun and stars are CSS loops; reduced motion has none of them (nor the opening's arrivals); out of sight they pause."""
    still = cover(SIZES[size], motion="reduce")
    assert still.evaluate("document.getAnimations().length") == 0
    page = cover(SIZES[size])
    page.wait_for_timeout(300)
    assert page.evaluate("document.querySelector('.cv-hero .cv-cloud.c1').getAnimations().map((a) => a.animationName)") == ["cv-drift"]
    assert page.evaluate("[...document.querySelectorAll('.cv-hero .cv-wave')].map((w) => getComputedStyle(w).animationName)") == ["cv-roll"] * 3
    assert page.evaluate("getComputedStyle(document.querySelector('.cv-hero .cv-cloud.c1')).animationPlayState") == "running"
    page.evaluate("window.scrollTo(0, document.querySelector('.cv-stage').getBoundingClientRect().top + scrollY + 200)")
    page.wait_for_function("document.querySelector('.cv-hero .cv-scene').classList.contains('cv-off')")
    assert page.evaluate("getComputedStyle(document.querySelector('.cv-hero .cv-cloud.c1')).animationPlayState") == "paused"
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_function("!document.querySelector('.cv-hero .cv-scene').classList.contains('cv-off')")
