"""F-299: "Why another travel site?" in a real browser. Each card opens on its grey Elsewhere face and flips to GitAway by itself about a second after it is well in view (no switch);
"Watch again" replays; reduced motion, ?still and no script show the GitAway faces with their struck lines at once; nothing scrolls sideways at 390 or 1440; both modes."""
import pytest

from tests_browser.helpers import DESKTOP, PHONE
from tests_browser.test_cover import cover  # noqa: F401  (the fixture)

SIZES = {"390": PHONE, "1440": DESKTOP}


def _faces(page, k):
    """Card k: has it flipped (.on), and the real opacity of its Elsewhere and GitAway faces."""
    return page.evaluate("k => { const c = document.querySelectorAll('.wy-card')[k], o = (f) => +getComputedStyle(c.querySelector(f)).opacity; return [c.classList.contains('on'), o('.wy-e'), o('.wy-g')]; }", k)


def _bring(page, k):
    page.evaluate("k => document.querySelectorAll('.wy-card')[k].scrollIntoView({behavior: 'instant', block: 'center'})", k)


@pytest.mark.parametrize("size", ["390", "1440"])
def test_a_card_opens_on_elsewhere_then_flips_to_gitaway_on_its_own(cover, size):
    page = cover(SIZES[size])
    assert page.evaluate("document.documentElement.classList.contains('cv-flip')")
    assert page.evaluate("innerWidth") == SIZES[size]["width"]      # a face wider than its card would stretch a phone's layout viewport (and show the cards cut at the right)
    assert [_faces(page, k) for k in range(6)] == [[False, 1, 0]] * 6      # far off screen: every card is on its grey face
    _bring(page, 0)
    page.wait_for_timeout(300)
    assert _faces(page, 0) == [False, 1, 0]      # a beat after it came into view it is still Elsewhere
    page.wait_for_function("document.querySelectorAll('.wy-card')[0].classList.contains('on')")
    page.wait_for_function("(() => { const c = document.querySelectorAll('.wy-card')[0]; return +getComputedStyle(c.querySelector('.wy-g')).opacity === 1 && +getComputedStyle(c.querySelector('.wy-e')).opacity === 0; })()")
    for k in range(1, 6):      # every card flips once it is in view
        _bring(page, k)
        page.wait_for_function(f"document.querySelectorAll('.wy-card')[{k}].classList.contains('on')")
    page.wait_for_function("[...document.querySelectorAll('.wy-card')].every(c => +getComputedStyle(c.querySelector('.wy-g')).opacity === 1)")


@pytest.mark.parametrize("size", ["390", "1440"])
def test_watch_again_plays_it_once_more(cover, size):
    page = cover(SIZES[size])
    _bring(page, 0)
    page.wait_for_function("document.querySelectorAll('.wy-card.on').length > 0")
    page.click("#why-again")
    page.wait_for_function("document.querySelectorAll('.wy-card.on').length === 0")
    _bring(page, 0)
    page.wait_for_function("document.querySelectorAll('.wy-card')[0].classList.contains('on')")      # the cards in view flip again by themselves


@pytest.mark.parametrize("how", ["reduced", "still", "nojs"])
def test_the_still_shows_gitaway_at_once_with_the_struck_line(cover, how):
    page = cover(DESKTOP, motion="reduce" if how == "reduced" else "no-preference", query="?still" if how == "still" else "", js=how != "nojs", wait=False)
    assert not page.evaluate("document.documentElement.classList.contains('cv-flip')")
    assert page.evaluate("[...document.querySelectorAll('.wy-card')].every(c => getComputedStyle(c.querySelector('.wy-e')).display === 'none' && getComputedStyle(c.querySelector('.wy-g')).opacity === '1')")
    assert page.locator(".wy-was s").count() == 6
    assert page.locator(".wy-was s").first.inner_text() == "$189 a night*"
    assert not page.locator("#why-again").is_visible()


@pytest.mark.parametrize("mode", ["light", "dark"])
@pytest.mark.parametrize("size", ["390", "1440"])
def test_it_fits_the_screen_in_both_modes(cover, size, mode):
    page = cover(SIZES[size], mode=mode, query="?still")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert page.evaluate("[...document.querySelectorAll('.wy-card, .wy-band')].every(c => c.getBoundingClientRect().right <= innerWidth - 8 && c.getBoundingClientRect().left >= 8)")      # nothing is clipped by the page's overflow
    tops = page.evaluate("[...document.querySelectorAll('.wy-card')].map(c => Math.round(c.getBoundingClientRect().top + scrollY))")
    assert len(set(tops)) == (6 if size == "390" else 3)      # one column on a phone, two by three on a laptop
