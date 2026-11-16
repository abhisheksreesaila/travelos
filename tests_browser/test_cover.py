"""F-266, cover v3 "one postcard" in a real browser (docs/briefs/cover-v3.md, D-762): one stage pinned with CSS sticky over eight beats; the beat changes as the page scrolls (the words,
the ring's inked word, the card's shape, one face on show); the sky turns to snow on Go; reduced motion, ?still and a page without its script show every beat as a card with its words
under it; nothing scrolls sideways at 390 or 1440; dark follows the site's own choice (localStorage ga-mode); the wish is a real form that opens the visitor's own matrix; nothing takes
the keyboard; every word that is text (not a drawing) reads at 4.5:1 and a phone gets its type floor and 48 px targets, in both modes. The script's rules (no scroll handler, no layout
read, no transform) are read from its text in tests/test_cover.py; here the page is checked for any transform written to an element."""
import pytest

from tests_browser.helpers import DESKTOP, PHONE
from tests_browser.look import audit

SIZES = {"390": PHONE, "1440": DESKTOP}
HEADLINES = ("Every trip starts as a wish.", "Every way to go, on one card.", "Tap a square. That's the trip.", "Everyone gets a pen.", "Then you just go.",
             "Bring it home as a guide.", "Give it to the world.", "And someone else's trip begins.")
RING = ("Wish", "Compare", "Book", "Plan", "Go", "Share", "Post", "Pass it on")
WIDE_CARD = {0: (520, 340), 1: (640, 400), 2: (380, 410), 3: (660, 430), 4: (540, 350), 5: (400, 540), 6: (400, 500), 7: (520, 340)}      # cover.css, in drawing units
PHONE_CARD = {**WIDE_CARD, 0: (520, 400), 1: (520, 380), 3: (520, 440), 4: (520, 340), 7: (520, 400)}


@pytest.fixture
def cover(browser, base_url):
    made = []

    def open_cover(viewport=DESKTOP, mode="light", motion="no-preference", query="", js=True, wait=True):
        phone = viewport["width"] < 760
        ctx = browser.new_context(viewport=viewport, reduced_motion=motion, has_touch=phone, is_mobile=phone, java_script_enabled=js)
        ctx.set_default_timeout(15000)
        made.append(ctx)
        if mode == "dark":
            ctx.add_init_script("try { localStorage.setItem('ga-mode', 'dark'); } catch (e) {}")      # the site's own choice (mode.js), not the system's
        page = ctx.new_page()
        page.goto(f"{base_url}/{query}")
        if js and wait:
            page.wait_for_function("!!window.GA_COVER")
        return page

    yield open_cover
    for c in made:
        c.close()


def _show(page, k):
    """Scroll the real page until beat k's marker crosses the line in the middle of the screen, and wait for the story to say so."""
    page.evaluate("k => document.querySelectorAll('.beats i')[k].scrollIntoView({behavior: 'instant', block: 'start'})", k)
    page.wait_for_function(f"document.querySelector('.stage').dataset.beat === '{k}'")


def _card(page):
    return page.evaluate("(() => { const c = document.querySelector('.pc'); return [c.offsetWidth, c.offsetHeight]; })()")      # the layout box: the first beat's card bobs (tilts) a little


def _words(page):
    return page.evaluate("[...document.querySelectorAll('.cap.now :is(h1, h2)')].map(h => h.innerText.replace(/\\s+/g, ' ').trim())")


def _inked(page):
    return page.evaluate("[...document.querySelectorAll('.ring text.now')].map(t => t.textContent)")


@pytest.mark.parametrize("size", ["390", "1440"])
def test_the_beats_change_as_the_page_scrolls(cover, size):
    page = cover(SIZES[size])
    assert page.evaluate("getComputedStyle(document.querySelector('.stage')).position") == "sticky"      # one stage, pinned by CSS
    assert page.evaluate("document.documentElement.classList.contains('cv-film')")
    cards = PHONE_CARD if size == "390" else WIDE_CARD
    seen = {}
    for k in range(8):
        _show(page, k)
        page.wait_for_timeout(1300)      # the card has settled
        assert _words(page) == [HEADLINES[k]] and _inked(page) == [RING[k]]
        assert page.evaluate("document.querySelector('.pager [aria-current]').dataset.k") == str(k)      # the pager's one lit stop
        on = page.evaluate("[...document.querySelectorAll('.side')].map(s => +getComputedStyle(s).opacity)")
        assert on[k] == 1 and sum(on) == 1, on      # one face on show: the others crossfaded away
        w, h = _card(page)
        seen[k] = w / h
        assert abs(w / h - cards[k][0] / cards[k][1]) < 0.02, (k, w, h)      # the one card reshapes to this beat's shape
    assert len({round(r, 2) for r in seen.values()}) >= 6      # and the shapes are different beats' own
    for k in (3, 0):      # going back up plays the story backwards
        _show(page, k)
        assert _words(page) == [HEADLINES[k]]
    assert page.evaluate("document.querySelectorAll('[style*=\"transform\"]').length") == 0      # no script wrote a transform


@pytest.mark.parametrize("size", ["390", "1440"])
def test_the_sky_turns_to_snow_on_go_and_back(cover, size):
    page = cover(SIZES[size])
    assert page.evaluate("document.querySelector('.cv-sky').dataset.mood") == "shore"
    _show(page, 4)
    page.wait_for_function("document.querySelector('.cv-sky').dataset.mood === 'snow'")
    page.wait_for_function("getComputedStyle(document.querySelector('.cv-sky'), '::after').opacity === '1'")      # the snow sky fades in
    _show(page, 6)
    assert page.evaluate("document.querySelector('.cv-sky').dataset.mood") == "shore"


def test_the_ring_turns_and_the_other_families_cards_come_nearer_one_step_per_beat(cover):
    page = cover(DESKTOP)
    turn = lambda: page.evaluate("getComputedStyle(document.querySelector('.ring svg')).rotate")      # noqa: E731
    near = lambda: page.evaluate("[...document.querySelectorAll('.gal i')].map(i => getComputedStyle(i).opacity).join()")      # noqa: E731
    first, gallery = turn(), near()
    _show(page, 1)
    page.wait_for_timeout(1700)
    assert turn() != first and near() != gallery
    assert abs(float(turn().replace("deg", "")) - (-22.5 - 45)) < 0.5      # one eighth of a turn per beat
    _show(page, 0)
    page.wait_for_timeout(1700)
    assert turn() == first and near() == gallery      # back on the wish, as it began


@pytest.mark.parametrize("size", ["390", "1440"])
def test_still_mode_shows_every_beat_as_a_card_with_its_words(cover, size):
    """?still, reduced motion and no script give the same page: nothing is pinned or travels; each beat's card is followed by its words."""
    for kwargs in ({"query": "?still"}, {"motion": "reduce"}):
        page = cover(SIZES[size], **kwargs)
        assert not page.evaluate("document.documentElement.classList.contains('cv-film')")
        assert page.evaluate("getComputedStyle(document.querySelector('.stage')).position") != "sticky"
        assert page.evaluate("getComputedStyle(document.querySelector('.pager')).display") == "none"
        tops = page.evaluate("""() => [...document.querySelectorAll('.side')].map((s, k) => {
            const r = s.getBoundingClientRect(), c = document.querySelector(`.cap[data-k="${k}"]`).getBoundingClientRect();
            return [k, r.height > 100, +getComputedStyle(s).opacity, getComputedStyle(s).visibility, c.top >= r.bottom - 1, c.height > 40]; })""")
        assert all(h and o == 1 and v == "visible" and below and tall for _, h, o, v, below, tall in tops), tops
        order = page.evaluate("[0, 1, 2, 3, 4, 5, 6, 7].flatMap(k => ['.side', '.cap'].map(c => document.querySelector(`${c}[data-k=\"${k}\"]`).getBoundingClientRect().top + scrollY))")
        assert order == sorted(order), order      # card 0, words 0, card 1, words 1 ...
        assert page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth") <= 1


def test_with_no_script_the_still_is_what_you_get(cover):
    page = cover(DESKTOP, js=False)
    assert page.evaluate("document.querySelectorAll('.side').length") == 8
    assert page.evaluate("getComputedStyle(document.querySelector('.stage')).position") != "sticky"
    assert page.locator(".cap").nth(7).inner_text().count("trip begins")
    assert page.evaluate("[...document.querySelectorAll('.cap')].every(c => getComputedStyle(c).opacity === '1' && getComputedStyle(c).visibility === 'visible')")


@pytest.mark.parametrize("mode", ["light", "dark"])
@pytest.mark.parametrize("size", ["390", "1440"])
def test_nothing_scrolls_sideways_in_either_layout(cover, size, mode):
    film = cover(SIZES[size], mode)
    for k in (0, 3, 7):
        _show(film, k)
        assert film.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth") <= 1, k
    film.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")      # the close and the foot
    assert film.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth") <= 1
    assert film.locator(".cv-close .cv-ctas a", has_text="Start a trip").is_visible()


def test_dark_follows_the_sites_own_choice_and_light_is_the_default(cover):
    light = cover(DESKTOP)
    assert light.evaluate("document.documentElement.dataset.mode") == "light"
    assert float(light.evaluate("getComputedStyle(document.querySelector('.cv-sky .sun')).opacity")) == 1
    assert float(light.evaluate("getComputedStyle(document.querySelector('.cv-sky .moon')).opacity")) == 0
    dark = cover(DESKTOP, "dark")
    assert dark.evaluate("document.documentElement.dataset.mode") == "dark"
    dark.wait_for_timeout(1300)
    assert float(dark.evaluate("getComputedStyle(document.querySelector('.cv-sky .moon')).opacity")) == 1 and float(dark.evaluate("getComputedStyle(document.querySelector('.cv-sky .sun')).opacity")) == 0
    assert dark.evaluate("getComputedStyle(document.querySelector('.cap.now h1')).color") == "rgb(244, 245, 251)"      # the v2 ink of the dark mode
    paper = dark.evaluate("getComputedStyle(document.querySelector('.pc')).backgroundColor")
    assert paper == "rgb(237, 230, 215)"      # the postcard is paper in both modes (dimmed in the dark)
    dark.click(".cv-mode")      # the bar's button is the site's switch: it turns the page and the choice is kept
    assert dark.evaluate("document.documentElement.dataset.mode") == "light"
    assert dark.evaluate("localStorage.getItem('ga-mode')") is None


@pytest.mark.parametrize("size", ["390", "1440"])
def test_the_wish_is_a_real_form_nothing_takes_the_keyboard_and_it_opens_the_matrix(cover, size, base_url):
    page = cover(SIZES[size])
    assert page.evaluate("document.activeElement === document.body")      # no autofocus
    box = page.locator(".cv-wish textarea")
    assert box.get_attribute("placeholder") == "Somewhere warm, then snow, for 4 of us, mid-December." and box.input_value() == ""
    r = page.evaluate("['.cv-wish textarea', '.cv-wish .go'].map(s => { const e = document.querySelector(s); return [e.offsetWidth, e.offsetHeight]; })")      # (the pill pops in: its layout box, not its first frames)
    assert all(w >= 48 and h >= 48 for w, h in r), r      # 48 px targets
    assert page.evaluate("getComputedStyle(document.querySelector('.cv-wish .sent')).opacity") == "1"      # the sample writes itself over the empty box
    box.click(force=True)      # (the first card bobs a little until the pointer or the keyboard is on it: Playwright's "stable" wait would never end)
    assert page.evaluate("getComputedStyle(document.querySelector('.cv-wish .sent')).opacity") == "0"      # and gives way to the visitor's own words
    box.fill("San Diego Dec 12 to 16")
    box.press("Enter")
    page.wait_for_url("**/plan/matrix?**")
    assert "to=San+Diego" in page.url and base_url in page.url
    page.goto(f"{base_url}/")
    page.wait_for_function("!!window.GA_COVER")
    page.locator(".cv-wish textarea").fill("San Diego")
    page.locator(".cv-wish .go").click(force=True)      # the pill sends it too; a place with no time stays on the ask, in its words, the box filled
    page.wait_for_url("**/plan/ask")
    assert "Say when" in page.locator("#v2-error").inner_text() and page.locator("#v2-q").input_value() == "San Diego"


def test_the_pager_and_the_doors_of_the_shown_words(cover):
    page = cover(DESKTOP)
    page.click('.pager button[data-k="5"]')
    page.wait_for_function("document.querySelector('.stage').dataset.beat === '5'")
    assert page.evaluate("document.querySelector('.pager [aria-current]').dataset.k") == "5"
    assert page.evaluate("[...document.querySelectorAll('.cap:not(.now) a')].every(a => getComputedStyle(a).visibility === 'hidden')")      # the captions not shown step out of the tab order
    _show(page, 7)
    assert page.evaluate("[...document.querySelectorAll('.cap.now a')].map(a => a.innerText.trim())") == ["Start a trip", "Browse guides"]
    page.click(".cap.now a:has-text('Browse guides')")
    page.wait_for_url("**/guides")


@pytest.mark.parametrize("mode", ["light", "dark"])
@pytest.mark.parametrize("size", ["390", "1440"])
def test_every_text_reads_and_a_phone_gets_its_floor_and_targets(cover, size, mode):
    """The audit reads the still (every beat's last frame at once: the film's crossfades would be read half faded) and leaves out the drawings (aria-hidden: a screen reader skips them
    too): the captions, the form, the bar, the close and the foot meet 4.5:1, a phone's type floor and 48 px targets."""
    page = cover(SIZES[size], mode, query="?still")
    page.add_style_tag(content='[aria-hidden="true"]:not(.cv-sky) { display: none !important; }')
    seen = audit(page)
    assert seen["wide"] <= 1
    assert not seen["small"], seen["small"]
    assert not seen["low"], seen["low"]
    assert not seen["tiny"], seen["tiny"]
    assert not seen["glass"], seen["glass"]
    assert page.evaluate("[...document.querySelectorAll('.ga-preview-pill')].filter(e => e.getClientRects().length).length") == 1      # one "Early preview" label


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_the_drawings_text_reads_in_both_modes(cover, mode):
    """The postcard's own faces (the matrix, the calendar, the guide, the post): their text is ink on paper, 4.5:1 (the audit skips gradients, so the post's own gradient is not read)."""
    page = cover(DESKTOP, mode, query="?still")
    seen = audit(page)
    assert not seen["low"], seen["low"]
    assert not seen["tiny"] and not seen["small"]


@pytest.mark.parametrize("size", ["390", "1440"])
def test_the_early_preview_line_opens_inside_the_screen_and_escape_closes_it(cover, size):
    page = cover(SIZES[size])
    page.locator(".ga-preview-sum:visible").click()
    line = page.locator(".ga-preview[open] .ga-preview-pop")
    line.wait_for(state="visible")
    assert line.inner_text().startswith("GitAway is new. Things will change;")
    box = line.bounding_box()
    assert box["x"] >= 0 and box["x"] + box["width"] <= SIZES[size]["width"], box      # the line stays on the screen
    page.keyboard.press("Escape")
    page.wait_for_function("!document.querySelector('.ga-preview[open]')")
