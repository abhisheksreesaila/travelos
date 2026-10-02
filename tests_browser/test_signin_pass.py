"""F-052: the sign-in boarding pass in a real browser: reduced motion parks the plane at its destination and stills the sky;
on a phone the sky is a short banner above the pass, with no sideways scroll, the 13px text floor and 44px targets."""
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


def visible_plane(page):
    return page.evaluate("""() => {
        const el = [...document.querySelectorAll('.si-plane')].find(e => e.closest('.si-stage').offsetParent !== null);
        const s = getComputedStyle(el);
        return {distance: s.offsetDistance, animation: s.animationName, path: s.offsetPath};
    }""")


@pytest.mark.parametrize("viewport", [DESKTOP, PHONE])
@pytest.mark.parametrize("name", CONTEXTS)
def test_reduced_motion_is_calm_and_the_plane_is_parked_at_its_destination(open_signin, name, viewport):
    page = open_signin(CONTEXTS[name], viewport)
    plane = visible_plane(page)
    assert plane["distance"] == "100%" and plane["animation"] == "none" and plane["path"].startswith("path(")
    still = page.evaluate("""() => [...document.querySelectorAll('.si-sun, .si-cloud, .si-stick, .si-route, .si-card')]
        .filter(e => e.offsetParent !== null || e.closest('svg')).map(e => getComputedStyle(e).animationName).filter(n => n !== 'none')""")
    assert still == []


def test_with_motion_the_plane_flies(open_signin):
    page = open_signin(CONTEXTS["search"], motion="no-preference")
    assert visible_plane(page)["animation"] == "si-fly"
    first = page.evaluate("getComputedStyle(document.querySelector('.si-stage-d .si-plane')).offsetDistance")
    page.wait_for_timeout(700)
    assert page.evaluate("getComputedStyle(document.querySelector('.si-stage-d .si-plane')).offsetDistance") != first


@pytest.mark.parametrize("name", CONTEXTS)
def test_the_phone_gets_a_short_banner_above_the_pass(open_signin, name):
    page = open_signin(CONTEXTS[name], PHONE)
    box = page.evaluate("""() => {
        const r = s => document.querySelector(s).getBoundingClientRect();
        return {sky: r('.si-sky'), card: r('.si-card'), w: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth};
    }""")
    assert box["sky"]["bottom"] > box["card"]["top"] - 1 and box["sky"]["top"] < box["card"]["top"]   # above, the pass tucks over its edge
    assert box["sky"]["height"] < 260 and box["sky"]["width"] == PHONE["width"]
    assert box["w"] == box["cw"]   # no sideways scroll
    assert page.is_visible(".si-stage-m") and not page.is_visible(".si-stage-d")


@pytest.mark.parametrize("name", CONTEXTS)
def test_phone_targets_and_text_floor(open_signin, name):
    page = open_signin(CONTEXTS[name], PHONE)
    page.click(".si-sum")  # the dev sign-in box is tucked away when Google is on; here it is open already, so this closes it
    page.click(".si-sum")
    small = page.evaluate("""() => [...document.querySelectorAll('.si-card *, .si-sky *')].filter(e => e.offsetParent && !e.closest('svg') && !e.children.length
        && e.textContent.trim() && parseFloat(getComputedStyle(e).fontSize) < 13).map(e => e.textContent.trim())""")
    assert small == []
    targets = page.evaluate("""() => [...document.querySelectorAll('.si-card a, .si-card button, .si-card summary')].filter(e => e.offsetParent)
        .map(e => [e.textContent.trim(), e.getBoundingClientRect().height])""")
    assert targets and all(h >= 44 for _, h in targets), targets


@pytest.mark.parametrize("name", CONTEXTS)
def test_desktop_fits_without_sideways_scroll_and_shows_the_pass(open_signin, name):
    page = open_signin(CONTEXTS[name], DESKTOP)
    assert page.evaluate("document.documentElement.scrollWidth === document.documentElement.clientWidth")
    card = page.evaluate("(() => { const r = document.querySelector('.si-card').getBoundingClientRect(); return [r.top, r.bottom]; })()")
    assert card[0] >= 0 and card[1] <= DESKTOP["height"]   # the whole pass is on screen at 1440x900
    assert page.locator("#si-email").evaluate("e => document.activeElement === e")   # focus starts in the dialog


@pytest.fixture
def with_google(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")


def test_the_google_button_is_named_continue_with_google(open_signin, with_google):
    page = open_signin(CONTEXTS["search"], PHONE)
    assert page.get_by_role("link", name="Continue with Google", exact=True).count() == 1


GEOMETRY = """() => {
    const vis = e => e.closest('.si-stage').offsetParent !== null;
    const rect = e => { const r = e.getBoundingClientRect(); return {l: r.left, t: r.top, r: r.right, b: r.bottom, w: r.width, text: e.textContent.trim()}; };
    const q = s => [...document.querySelectorAll(s)].filter(vis);
    const sky = document.querySelector('.si-sky').getBoundingClientRect(), card = document.querySelector('.si-card').getBoundingClientRect();
    return {sticks: q('.si-stick').map(rect), codes: q('.si-code').map(rect), sun: q('.si-sun').map(rect)[0], plane: q('.si-plane').map(rect)[0],
            sky: {l: sky.left, t: sky.top, r: sky.right, b: sky.bottom}, cardTop: card.top, scroll: [document.documentElement.scrollWidth, document.documentElement.clientWidth]};
}"""


def hit(a, b):
    return a["l"] < b["r"] and b["l"] < a["r"] and a["t"] < b["b"] and b["t"] < a["b"]


WIDTHS = [(1440, 900), (1001, 800), (1000, 800), (900, 800), (800, 800), (721, 800), (390, 844), (320, 640)]


@pytest.mark.parametrize("w,h", WIDTHS)
@pytest.mark.parametrize("name", CONTEXTS)
def test_stickers_and_labels_never_overlap_at_any_width(open_signin, name, w, h):
    g = open_signin(CONTEXTS[name], {"width": w, "height": h}).evaluate(GEOMETRY)
    things = g["sticks"] + g["codes"]
    for i, a in enumerate(things):
        for b in things[i + 1:]:
            assert not hit(a, b), (a["text"], b["text"])
        assert a["l"] >= g["sky"]["l"] and a["r"] <= g["sky"]["r"], a["text"]
        if w <= 1000:  # stacked: the pass tucks over the sky's lower edge, so nothing may hide under it
            assert a["b"] <= g["cardTop"] and a["t"] >= g["sky"]["t"], a["text"]
    if w <= 1000:
        assert not any(hit(s, g["sun"]) for s in g["sticks"])
    assert g["scroll"][0] == g["scroll"][1]


@pytest.mark.parametrize("w,h", WIDTHS)
def test_the_parked_plane_stays_off_the_destination_label(open_signin, w, h):
    g = open_signin(CONTEXTS["search"], {"width": w, "height": h}).evaluate(GEOMETRY)
    assert not hit(g["plane"], g["codes"][1]) and not hit(g["plane"], g["codes"][0])


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
