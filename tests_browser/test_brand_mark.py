"""D-61, F-200, F-296 follow-ups (D-966): the logo looks identical on every page, in light and in dark: one mark (layout.mark()), a near-black tile (a white one in dark mode) with a white fork
(black in dark) and one orange dot, and the wordmark (Inter 560 in the v2 bar, 25px, 22px on a phone; the cover draws its own Geist 750). Measured in a real browser on the cover, sign-in, the
reading pages, the creators, the family and import pages: every page now wears the v2 bar (F-272), which this test once did not count (it found one logo and failed)."""
import pytest

from tests_browser.helpers import DESKTOP, PHONE

TRIP = "d=2027-03-05&r=2027-03-09&a=2"
MEASURE = """() => [...document.querySelectorAll('.ga-brand-mark')].filter(e => e.getClientRects().length).map(e => {
  const t = getComputedStyle(e), n = e.parentElement.querySelector('.ga-brand-name, .si-brand, .v2-brand-name'), w = getComputedStyle(n), svg = getComputedStyle(e.querySelector('svg'));
  return {tile: [t.backgroundColor, t.width, t.height, t.borderRadius], fork: [svg.width, svg.height], strokes: ['.mk-l', '.mk-a', '.mk-b', '.mk-c'].map(s => getComputedStyle(e.querySelector(s)).stroke),
          word: [w.fontFamily, w.fontWeight, w.fontSize, w.letterSpacing, w.textTransform, w.color], text: n.textContent};
})"""
ORANGE = "rgb(242, 85, 0)"      # the one dot (F-296 follow-ups, D-966)
LOOK = {"light": {"tile": "rgb(29, 29, 31)", "strokes": ["rgb(255, 255, 255)"] * 3 + [ORANGE], "word": "rgb(29, 29, 31)"},
        "dark": {"tile": "rgb(255, 255, 255)", "strokes": ["rgb(29, 29, 31)"] * 3 + [ORANGE], "word": "rgb(245, 245, 247)"}}
COVER = {"light": "rgb(245, 245, 247)", "dark": "rgb(245, 245, 247)"}      # the cover's wordmark ink (the Stage look, F-296): F-301 made the cover dark whatever the mode, so its mark is the dark one in both


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

    for path in ("/", "/signin", "/privacy", "/terms"):
        look(path)
    ctx.request.post(f"{base_url}/signin", form={"email": "ari.rivera@example.com", "next": "/", "intent": "pay"}, max_redirects=0)
    ctx.request.post(f"{base_url}/_test/pay", form={"f": "f1", "h": "h1", "c": "c1"}, max_redirects=0)
    for path in ("/creators", _creator(page, base_url), "/family", "/trip/details", "/trips/import"):      # M5 triage: /plan, /partners, the canvas, /trip and /trip/ask are retired (F-254); the v2 pages draw their own mark
        look(path)
    ctx.close()
    return found


@pytest.mark.parametrize("mode", ["light", "dark"])
@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["laptop", "phone"])
def test_the_logo_is_one_mark_and_one_wordmark_on_every_page(browser, base_url, viewport, mode):
    found = _everywhere(browser, base_url, viewport, mode)
    seen = [m for _, marks in found for m in marks]
    assert len(seen) >= 8, f"the logo shows on most pages: {[(p, len(m)) for p, m in found]}"
    first, want = next(m for p, marks in found if p != "/" for m in marks[:1]), LOOK[mode]      # M5 triage: the cover's postcard (F-266) is the one page whose wordmark takes its own size and ink; its tile, fork and text are held to the same rule below
    assert first["tile"][0] == want["tile"] and first["strokes"] == want["strokes"], first      # the ink (or white) tile, the fork's line and its three kind-coloured nodes
    size = "25px" if viewport is DESKTOP else "22px"      # every page but the cover wears the v2 bar: Inter 560, a phone's a little smaller (F-272; this said Geist 750, the old header's)
    assert first["word"][0].startswith("Inter") and first["word"][1] == "560" and first["word"][2] == size and first["word"][4] == "none" and first["word"][5] == want["word"], first["word"]
    for path, marks in found:
        for m in marks:
            if path == "/":      # the cover: the same colours, font and weight, and its own size and ink (F-266, measured on the running cover at both widths)
                dark = LOOK["dark"]      # the cover is always dark (F-301)
                assert m["tile"] == [dark["tile"], "36px", "36px", "10px"], f"/: the cover's tile {m['tile']}"
                assert m["fork"] == ["24px", "24px"] and m["strokes"] == dark["strokes"], f"/: the cover's fork {m['fork']}"
                assert m["word"] == ["Geist, system-ui, sans-serif", "750", "24px", "-0.72px", "none", COVER[mode]], f"/: the cover's wordmark {m['word']}"
            else:
                assert m["tile"] == first["tile"], f"{path}: the tile differs"
                assert m["fork"] == first["fork"] and m["strokes"] == first["strokes"], f"{path}: the fork differs"
                assert m["word"] == first["word"], f"{path}: the wordmark differs"
            assert m["text"] == "GitAway", path
