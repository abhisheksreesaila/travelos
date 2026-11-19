"""F-299, static since F-301: "Why another travel site?" in a real browser. Six cards, only GitAway's faces (no flip, no Elsewhere face, no Watch again, no script); each keeps the old way as one
struck line the visitor can read (thin, light strike, the words at 4.5:1 or better); the same with motion, with reduced motion, ?still and no script; nothing scrolls sideways at 390 or 1440."""
import pytest

from tests_browser.helpers import DESKTOP, PHONE
from tests_browser.test_cover import cover  # noqa: F401  (the fixture)

SIZES = {"390": PHONE, "1440": DESKTOP}


def _lum(rgb):
    def ch(c):
        c /= 255
        return c / 12.92 if c <= .03928 else ((c + .055) / 1.055) ** 2.4
    r, g, b = rgb
    return .2126 * ch(r) + .7152 * ch(g) + .0722 * ch(b)


def _ratio(a, b):
    hi, lo = sorted((_lum(a), _lum(b)), reverse=True)
    return (hi + .05) / (lo + .05)


@pytest.mark.parametrize("how", ["motion", "reduced", "still", "nojs"])
def test_every_card_shows_gitaway_at_once_with_the_struck_line(cover, how):
    page = cover(DESKTOP, motion="reduce" if how == "reduced" else "no-preference", query="?still" if how == "still" else "", js=how != "nojs", wait=how in ("motion",))
    assert page.evaluate("[...document.querySelectorAll('.wy-card')].every(c => getComputedStyle(c).opacity === '1' && getComputedStyle(c).visibility === 'visible' && c.getClientRects().length)")
    assert page.locator(".wy-card").count() == 6
    assert page.locator(".wy-was s").count() == 6
    assert page.locator(".wy-was").first.inner_text() == "Elsewhere: $189 a night*"
    assert page.locator("#why-again, .wy-e, .wy-g").count() == 0      # no Watch again, no Elsewhere face


@pytest.mark.parametrize("size", ["390", "1440"])
def test_the_struck_line_is_thin_light_and_readable(cover, size):
    page = cover(SIZES[size], query="?still")
    row = page.evaluate("""() => { const w = document.querySelector('.wy-was'), s = w.querySelector('s'), st = getComputedStyle(s), card = getComputedStyle(w.closest('.wy-card'));
        return { word: getComputedStyle(w).color, ground: card.backgroundColor, line: st.textDecorationLine, thick: st.textDecorationThickness, deco: st.textDecorationColor, sColor: st.color, size: parseFloat(getComputedStyle(w).fontSize) }; }""")
    rgb = lambda c: [float(x) for x in c[c.index("(") + 1:c.index(")")].replace("/", " ").replace(",", " ").split()[:3]]      # noqa: E731
    assert row["line"] == "line-through" and row["thick"] == "1px"      # a thin strike
    assert row["sColor"] == row["word"]      # the struck words keep the readable colour
    assert _ratio(rgb(row["word"]), rgb(row["ground"])) >= 4.5, row
    assert row["size"] >= 14      # a phone's type floor
    alpha = float(row["deco"].split("/")[-1].strip(" )")) if "/" in row["deco"] else (float(row["deco"].rsplit(",", 1)[-1].strip(" )")) if row["deco"].startswith("rgba") else 1.0)
    assert alpha < 1, row["deco"]      # the strike is softened, not the full signal colour


@pytest.mark.parametrize("size", ["390", "1440"])
def test_it_fits_the_screen_and_is_dark(cover, size):
    page = cover(SIZES[size], query="?still")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert page.evaluate("[...document.querySelectorAll('.wy-card')].every(c => c.getBoundingClientRect().right <= innerWidth - 8 && c.getBoundingClientRect().left >= 8)")      # nothing is clipped by the page's overflow
    tops = page.evaluate("[...document.querySelectorAll('.wy-card')].map(c => Math.round(c.getBoundingClientRect().top + scrollY))")
    assert len(set(tops)) == (6 if size == "390" else 3)      # one column on a phone, two by three on a laptop
    assert page.evaluate("getComputedStyle(document.querySelector('.wy-card')).backgroundColor") == "rgb(28, 28, 30)"
