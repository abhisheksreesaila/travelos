"""D-61, F-200: the logo looks identical on every page, in light and in dark. Direction A's mark (docs/design/reskin): an ink tile (a white one in dark mode) with the fork's
three nodes in kind colours, so the colour belongs to the trip, and the wordmark in Geist 750 (the old orange tile and Bricolage wordmark were D-61's; the brief dropped "orange everywhere").
Measured in a real browser on the landing, sign-in, the old pages, /plan, the creators, the partners log, the trip canvas with its top bar and the phone's pages."""
import pytest

from tests_browser.helpers import DESKTOP, PHONE

TRIP = "d=2027-03-05&r=2027-03-09&a=2"
MEASURE = """() => [...document.querySelectorAll('.ga-brand-mark, .si-logo')].filter(e => e.getClientRects().length).map(e => {
  const t = getComputedStyle(e), n = e.parentElement.querySelector('.ga-brand-name, .si-brand'), w = getComputedStyle(n), svg = getComputedStyle(e.querySelector('svg'));
  return {tile: [t.backgroundColor, t.width, t.height, t.borderRadius], fork: [svg.width, svg.height], strokes: ['.mk-l', '.mk-a', '.mk-b', '.mk-c'].map(s => getComputedStyle(e.querySelector(s)).stroke),
          word: [w.fontFamily, w.fontWeight, w.fontSize, w.letterSpacing, w.textTransform, w.color], text: n.textContent};
})"""
LOOK = {"light": {"tile": "rgb(11, 11, 13)", "strokes": ["rgb(255, 255, 255)", "rgb(140, 140, 255)", "rgb(211, 140, 255)", "rgb(255, 154, 92)"], "word": "rgb(11, 11, 13)"},
        "dark": {"tile": "rgb(245, 245, 247)", "strokes": ["rgb(11, 11, 13)", "rgb(67, 56, 202)", "rgb(139, 47, 201)", "rgb(194, 65, 12)"], "word": "rgb(245, 245, 247)"}}


def _marks(page):
    return page.evaluate(MEASURE)


def _creator(page, base_url):
    page.goto(f"{base_url}/creators")
    hrefs = page.eval_on_selector_all("a[href^='/creators/']", "els => els.map(e => e.getAttribute('href'))")
    return next(h for h in hrefs if h.rsplit("/", 1)[-1] not in ("draft", "finish", "done"))


def _everywhere(browser, base_url, viewport, mode="light"):
    """(path, marks) for every page that shows a logo at this width, signed out first, then signed in."""
    ctx = browser.new_context(viewport=viewport, has_touch=viewport is PHONE, is_mobile=viewport is PHONE, reduced_motion="reduce", color_scheme=mode)
    if mode == "dark":                                   # D-460: dark is the person's choice (the footer's button), not the system's
        ctx.add_init_script("try { localStorage.setItem('ga-mode', 'dark'); } catch (e) {}")
    page = ctx.new_page()
    found = []

    def look(path):
        page.goto(base_url + path)
        found.append((path, _marks(page)))

    for path in ("/", "/signin", "/start", "/community", "/privacy"):
        look(path)
    ctx.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "pay"}, max_redirects=0)
    ctx.request.post(f"{base_url}/pay", form={"f": "f1", "h": "h1", "c": "c1"}, max_redirects=0)
    for path in (f"/plan?to=hi&{TRIP}", "/creators", _creator(page, base_url), "/partners", "/trip/canvas?day=1", "/trip", "/family", "/trip/ask"):
        look(path)
    ctx.close()
    return found


@pytest.mark.parametrize("mode", ["light", "dark"])
@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["laptop", "phone"])
def test_the_logo_is_one_mark_and_one_wordmark_on_every_page(browser, base_url, viewport, mode):
    found = _everywhere(browser, base_url, viewport, mode)
    seen = [m for _, marks in found for m in marks]
    assert len(seen) >= 8, f"the logo shows on most pages: {[(p, len(m)) for p, m in found]}"
    first, want = seen[0], LOOK[mode]
    assert first["tile"][0] == want["tile"] and first["strokes"] == want["strokes"], first      # the ink (or white) tile, the fork's line and its three kind-coloured nodes
    assert first["word"][0].startswith("Geist") and first["word"][1] == "750" and first["word"][4] == "none" and first["word"][5] == want["word"], first["word"]
    for path, marks in found:
        for m in marks:
            assert m["tile"] == first["tile"], f"{path}: the tile differs"
            assert m["fork"] == first["fork"] and m["strokes"] == first["strokes"], f"{path}: the fork differs"
            assert m["word"] == first["word"], f"{path}: the wordmark differs"
            assert m["text"] == "GitAway", path
