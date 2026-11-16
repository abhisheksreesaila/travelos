"""F-052, F-200, F-272: sign-in in a real browser. The cover's language (v2: the sky, Newsreader and Inter, a near-opaque paper card; the founder found the old boarding pass too small):
a 34px title on a phone, 17px words, 56px buttons, every target at least 48px, the trip card with its stub; on a laptop the side beside the card carries the line
"Compare the whole trip. Choose it together." and one paper postcard of the trip, and the whole page fits 1440x900. Light and dark, no sideways scroll at 320, 390 and 1440,
and every piece of text 4.5:1 against what is behind it (tests_browser/look.py audit)."""
import pytest

from tests_browser.helpers import DESKTOP, PHONE
from tests_browser.look import audit

CONTEXTS = {
    "cold": "/signin?next=/&intent=save",
    "search": "/signin?next=%2Fplan%3Ff%3Df1%26d%3D2026-10-16%26r%3D2026-10-20%26a%3D2%26k%3D4&intent=pay",
    "fork": "/signin?next=/trips/sun-tacos-and-tide-pools&intent=fork",
}


@pytest.fixture
def open_signin(browser, base_url):
    contexts = []

    def open_signin(path, viewport=DESKTOP, motion="reduce"):
        ctx = browser.new_context(viewport=viewport, reduced_motion=motion)
        ctx.set_default_timeout(5000)
        contexts.append(ctx)
        page = ctx.new_page()
        page.goto(base_url + path)
        page.wait_for_selector("#si-dialog")
        return page

    yield open_signin
    for c in contexts:
        c.close()


@pytest.mark.parametrize("name", CONTEXTS)
def test_the_phone_is_one_column_big_and_easy_to_tap(open_signin, name):
    page = open_signin(CONTEXTS[name], PHONE)
    look = page.evaluate("""() => {
        const size = s => parseFloat(getComputedStyle(document.querySelector(s)).fontSize), r = s => document.querySelector(s).getBoundingClientRect();
        return {title: size('#si-title'), desc: size('#si-desc'), dest: size('#si-dest'), dev: r('.si-dev').height, sky: getComputedStyle(document.querySelector('.si-sky')).display,
                w: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth};
    }""")
    assert (look["title"], look["desc"], look["dest"]) == (34, 17, 17), look
    assert look["dev"] >= 56 and look["sky"] == "none" and look["w"] == look["cw"], look      # the 56px button, no half beside it, no sideways scroll
    targets = page.evaluate("""() => [...document.querySelectorAll('.si-card a, .si-card button, .si-card summary, .si-card input, #si-cancel')].filter(e => e.offsetParent && getComputedStyle(e).display !== 'inline')
        .map(e => [e.id || e.textContent.trim(), Math.round(Math.min(e.getBoundingClientRect().width, e.getBoundingClientRect().height))])""")
    assert targets and all(m >= 48 for _, m in targets), targets
    links = page.evaluate("[...document.querySelectorAll('.si-legal a')].map(e => Math.round(e.getBoundingClientRect().height))")
    assert links and all(h >= 48 for h in links), links      # Terms and Privacy are words in the sentence, each with a 48px tall hit area


@pytest.mark.parametrize("name", CONTEXTS)
def test_the_laptop_has_the_line_and_the_postcard_beside_the_card_and_fits(open_signin, name):
    page = open_signin(CONTEXTS[name], DESKTOP)
    assert page.evaluate("document.documentElement.scrollWidth === document.documentElement.clientWidth")
    assert page.locator(".si-line").inner_text().replace("\n", " ") == "Compare the whole trip. Choose it together."
    assert page.locator(".si-line-sub").inner_text() == "Flights and stays side by side, one total a square. Book it, plan it with your family, share it in one card."
    box = lambda sel: page.evaluate("s => [...document.querySelectorAll(s)].map(e => { const r = e.getBoundingClientRect(); return [e.className, r.left, r.top, r.right, r.bottom]; })", sel)
    (card,), (sky,), postcards = box(".si-card"), box(".si-sky"), box(".si-pc")
    boxes = [card, sky, *postcards]
    assert len(postcards) == 1 and sky[2] <= card[1] + 1                                  # the line and the one postcard on the left, the card on the right
    assert all(b[1] >= 0 and b[2] >= 0 and b[4] <= DESKTOP["height"] for b in boxes), boxes      # everything on screen at 1440x900, no scrolling
    assert page.locator("#si-email").evaluate("e => document.activeElement === e")   # focus starts in the dialog
    assert round(page.evaluate("parseFloat(getComputedStyle(document.querySelector('#si-desc')).fontSize)")) == 17
    assert page.evaluate("getComputedStyle(document.querySelector('#si-title')).fontFamily").startswith("Newsreader")      # the cover's voice, Newsreader, over Inter's words
    assert page.evaluate("getComputedStyle(document.querySelector('#si-desc')).fontFamily").startswith("Inter")


@pytest.fixture
def with_google(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")


def test_the_google_button_is_named_continue_with_google(open_signin, with_google):
    page = open_signin(CONTEXTS["search"], PHONE)
    assert page.get_by_role("link", name="Continue with Google", exact=True).count() == 1
    assert page.locator("#si-google").evaluate("e => e.getBoundingClientRect().height") >= 56      # the one clear action: a 56px solid button


WIDTHS = [(1440, 900), (1280, 800), (1020, 800), (1019, 800), (800, 800), (721, 800), (390, 844), (320, 640)]


@pytest.mark.parametrize("w,h", WIDTHS)
def test_the_stub_labels_stay_on_one_line(open_signin, w, h):
    page = open_signin(CONTEXTS["search"], {"width": w, "height": h})
    tops = page.evaluate("[...document.querySelectorAll('.si-k')].map(e => [Math.round(e.getBoundingClientRect().height), Math.round(e.getBoundingClientRect().top)])")
    assert len({hh for hh, _ in tops}) == 1, tops                                    # no label wraps: every label is one line tall
    assert len({t for _, t in tops}) == (2 if w < 360 else 1), tops                  # same row so the values line up (a 320px phone gives the third its own row)
    assert page.evaluate("document.documentElement.scrollWidth === document.documentElement.clientWidth")


def test_the_dev_summary_shows_a_chevron_that_turns_when_open(open_signin):
    page = open_signin(CONTEXTS["cold"], PHONE)
    chev = page.locator(".si-sum svg")
    assert chev.is_visible()
    open_t = chev.evaluate("e => getComputedStyle(e).transform")
    page.click(".si-sum")
    assert chev.evaluate("e => getComputedStyle(e).transform") != open_t


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("viewport", [{"width": 320, "height": 640}, PHONE, DESKTOP], ids=["320", "390", "1440"])
def test_it_reads_fits_and_is_easy_to_tap_in_both_modes(browser, base_url, with_google, scheme, viewport):
    """F-272: every piece of text 4.5:1 against what is behind it (the card, the sky, the paper postcard), every tap target 48px, no glass or blur, no sideways scroll."""
    small = viewport["width"] < 700
    ctx = browser.new_context(viewport=viewport, reduced_motion="reduce", color_scheme=scheme, has_touch=small, is_mobile=small)
    ctx.add_init_script(f"try {{ localStorage.setItem('ga-mode', '{scheme}'); }} catch (e) {{}}")      # dark is the person's choice (D-460), not the system's
    try:
        page = ctx.new_page()
        page.goto(base_url + CONTEXTS["search"], wait_until="networkidle")
        seen = audit(page)
        assert page.evaluate("document.documentElement.dataset.mode") == scheme
    finally:
        ctx.close()
    assert seen["wide"] <= 1 and not (seen["small"] or seen["tiny"] or seen["low"] or seen["glass"]), seen


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_the_postcard_is_paper_in_both_modes_and_its_icons_read_on_it(browser, base_url, scheme):
    """The one drawing that keeps its colours in dark mode is the paper postcard (the book's paper tokens); its icons must still be 3:1 on their chips."""
    def lum(rgb):
        def ch(v):
            v /= 255
            return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
        return 0.2126 * ch(rgb[0]) + 0.7152 * ch(rgb[1]) + 0.0722 * ch(rgb[2])

    def contrast(a, b):
        hi, lo = sorted((lum(a), lum(b)), reverse=True)
        return (hi + 0.05) / (lo + 0.05)

    ctx = browser.new_context(viewport=DESKTOP, reduced_motion="reduce", color_scheme=scheme)
    ctx.add_init_script(f"try {{ localStorage.setItem('ga-mode', '{scheme}'); }} catch (e) {{}}")      # dark is the person's choice (D-460), not the system's
    try:
        page = ctx.new_page()
        page.goto(base_url + CONTEXTS["search"])
        got = page.evaluate("""() => {
            const rgb = s => s.match(/[\\d.]+/g).slice(0, 3).map(Number);
            return {paper: rgb(getComputedStyle(document.querySelector('.si-pc')).backgroundColor),
                    icons: [...document.querySelectorAll('.si-chip')].map(c => [rgb(getComputedStyle(c.querySelector('svg')).color), rgb(getComputedStyle(c).backgroundColor)])};
        }""")
    finally:
        ctx.close()
    assert got["paper"] == ([251, 246, 234] if scheme == "light" else [237, 228, 209]), got      # paper in the light, a dimmed paper in the dark: never the card's dark
    assert len(got["icons"]) == 2 and all(contrast(i, bg) >= 3 for i, bg in got["icons"]), got
