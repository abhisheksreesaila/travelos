"""F-052, F-200: sign-in in a real browser. Direction A (the founder found the old boarding pass too small): a 34px title on a phone, 17px words, 56px buttons,
every target at least 48px, the trip card with its stub; on a laptop the left half carries the line "Take a trip. Leave a trail." and the trip's widgets, and the
whole page fits 1440x900. Same in light and dark (tests_browser/test_direction_a_pages.py measures contrast)."""
import pytest

from tests_browser.helpers import DESKTOP, PHONE

CONTEXTS = {
    "cold": "/signin?next=/start&intent=save",
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
def test_the_laptop_has_the_line_and_the_trips_widgets_beside_the_card_and_fits(open_signin, name):
    page = open_signin(CONTEXTS[name], DESKTOP)
    assert page.evaluate("document.documentElement.scrollWidth === document.documentElement.clientWidth")
    assert page.locator(".si-line").inner_text().replace("\n", " ") == "Take a trip. Leave a trail."
    assert page.locator(".si-line-sub").inner_text() == "Share the whole trip, not just the photos, so the next family can follow it, make it theirs, and say thanks."
    box = lambda sel: page.evaluate("s => [...document.querySelectorAll(s)].map(e => { const r = e.getBoundingClientRect(); return [e.className, r.left, r.top, r.right, r.bottom]; })", sel)
    (card,), (sky,), widgets = box(".si-card"), box(".si-sky"), box(".si-w")
    boxes = [card, sky, *widgets]
    assert len(widgets) == 3 and sky[3] <= card[1]                                  # the line and the widgets on the left, the card on the right
    assert all(b[2] >= 0 and b[4] <= DESKTOP["height"] for b in boxes), boxes      # everything on screen at 1440x900, no scrolling
    assert page.locator("#si-email").evaluate("e => document.activeElement === e")   # focus starts in the dialog
    assert round(page.evaluate("parseFloat(getComputedStyle(document.querySelector('#si-desc')).fontSize)")) == 16


@pytest.fixture
def with_google(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")


def test_the_google_button_is_named_continue_with_google(open_signin, with_google):
    page = open_signin(CONTEXTS["search"], PHONE)
    assert page.get_by_role("link", name="Continue with Google", exact=True).count() == 1


WIDTHS = [(1440, 900), (1280, 800), (1020, 800), (1019, 800), (800, 800), (721, 800), (390, 844), (320, 640)]


@pytest.mark.parametrize("w,h", WIDTHS)
def test_the_stub_labels_stay_on_one_line(open_signin, w, h):
    page = open_signin(CONTEXTS["search"], {"width": w, "height": h})
    tops = page.evaluate("[...document.querySelectorAll('.si-k')].map(e => [Math.round(e.getBoundingClientRect().height), Math.round(e.getBoundingClientRect().top)])")
    assert len({t for _, t in tops}) == 1 and len({hh for hh, _ in tops}) == 1, tops   # same height, same row: the values line up
    assert page.evaluate("document.documentElement.scrollWidth === document.documentElement.clientWidth")


def test_the_dev_summary_shows_a_chevron_that_turns_when_open(open_signin):
    page = open_signin(CONTEXTS["cold"], PHONE)
    chev = page.locator(".si-sum svg")
    assert chev.is_visible()
    open_t = chev.evaluate("e => getComputedStyle(e).transform")
    page.click(".si-sum")
    assert chev.evaluate("e => getComputedStyle(e).transform") != open_t
