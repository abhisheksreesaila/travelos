"""D-61: the logo looks identical on every page (the captain: "it's green and orange somewhere, it needs to be orange"). One orange tile with the dark fork, one wordmark,
measured in a real browser on the landing, the sign-in card, the old pages, /plan, the creators, the partners log, the trip canvas with its top bar and the phone's pages."""
import pytest

from tests_browser.helpers import DESKTOP, PHONE

TRIP = "d=2027-03-05&r=2027-03-09&a=2"
MEASURE = """() => [...document.querySelectorAll('.ga-brand-mark, .si-logo')].filter(e => e.getClientRects().length).map(e => {
  const t = getComputedStyle(e), n = e.parentElement.querySelector('.ga-brand-name, .si-brand'), w = getComputedStyle(n), svg = getComputedStyle(e.querySelector('svg'));
  return {tile: [t.backgroundColor, t.width, t.height, t.borderRadius, t.boxShadow, t.color], fork: [svg.width, svg.height],
          word: [w.fontFamily, w.fontWeight, w.fontSize, w.letterSpacing, w.textTransform, w.color], text: n.textContent};
})"""
ORANGE = "rgb(255, 115, 82)"


def _marks(page):
    return page.evaluate(MEASURE)


def _creator(page, base_url):
    page.goto(f"{base_url}/creators")
    hrefs = page.eval_on_selector_all("a[href^='/creators/']", "els => els.map(e => e.getAttribute('href'))")
    return next(h for h in hrefs if h.rsplit("/", 1)[-1] not in ("draft", "finish", "done"))


def _everywhere(browser, base_url, viewport):
    """(path, marks) for every page that shows a logo at this width, signed out first, then signed in."""
    ctx = browser.new_context(viewport=viewport, has_touch=viewport is PHONE, is_mobile=viewport is PHONE, reduced_motion="reduce")
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


@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["laptop", "phone"])
def test_the_logo_is_one_orange_mark_and_one_wordmark_on_every_page(browser, base_url, viewport):
    found = _everywhere(browser, base_url, viewport)
    seen = [m for _, marks in found for m in marks]
    assert len(seen) >= 8, f"the logo shows on most pages: {[(p, len(m)) for p, m in found]}"
    first = seen[0]
    assert first["tile"][0] == ORANGE and first["tile"][5] == "rgb(30, 26, 46)"
    assert first["word"][0].startswith('"Bricolage Grotesque"') and first["word"][1] == "800" and first["word"][4] == "none"
    for path, marks in found:
        for m in marks:
            assert m["tile"] == first["tile"], f"{path}: the tile differs"
            assert m["fork"] == first["fork"], f"{path}: the fork differs"
            assert m["word"] == first["word"], f"{path}: the wordmark differs"
            assert m["text"] == "GitAway", path
