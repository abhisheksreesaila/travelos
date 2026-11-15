"""F-258: every button and tappable card on a v2 page goes in when pressed and springs back (omxqua's press), none under reduced motion. One shared rule set in assets/css/v2.css uses the
individual `scale` property (it never fights a transform). A real mouse presses each control on a laptop, reads its computed `scale` while the button is down, lets go away from it (so no
click fires) and reads it settle back. A phone's headless Chromium does not set :active for CDP touches (docs/lessons.md: it did not scroll either), so there the browser is told the element
is :active (CDP `CSS.forcePseudoState`), which runs the same rule and the same transition."""
import re
from pathlib import Path

import pytest

from tests_browser.helpers import DESKTOP, PHONE
from tests_browser.test_matrixbook_sheet import open_square
from tests_browser.test_tripmatrix import matrix, stand  # noqa: F401 (fixtures)
from tests_browser.test_tripview import alt  # noqa: F401 (fixture)

# the sentence's words, the sections pill and the avatar (the top bar), a start-day square, the rail's buttons, the drawer's options, cards, close and Book my trip
CONTROLS = [".v2-w", ".v2-sections a:not([aria-current])", ".v2-round", ".mx-sq", ".wg .mini-btn", ".dr-opt", ".dr-alt", ".dr-mini", ".dr-x", ".dr-book", ".dr-save"]
MAY_BE_ABSENT = (".wg .mini-btn", ".v2-sections a:not([aria-current])", ".dr-save")      # not on every page of the stand
SCALE_JS = "el => { const s = getComputedStyle(el).scale; return s === 'none' ? 1 : parseFloat(s); }"


def press_and_release(page, sel):
    el = page.locator(sel).locator("visible=true").first
    el.scroll_into_view_if_needed()
    if page.viewport_size["width"] < 600:
        cdp = page.context.new_cdp_session(page)
        cdp.send("DOM.enable")
        cdp.send("CSS.enable")
        page.evaluate("sel => [...document.querySelectorAll(sel)].filter(e => e.getClientRects().length)[0].setAttribute('data-press-probe', '1')", sel)
        root = cdp.send("DOM.getDocument", {"depth": 0})["root"]["nodeId"]
        node = cdp.send("DOM.querySelector", {"nodeId": root, "selector": "[data-press-probe]"})["nodeId"]
        cdp.send("CSS.forcePseudoState", {"nodeId": node, "forcedPseudoClasses": ["active"]})
        page.wait_for_timeout(250)
        down = el.evaluate(SCALE_JS)
        cdp.send("CSS.forcePseudoState", {"nodeId": node, "forcedPseudoClasses": []})
        page.evaluate("() => document.querySelector('[data-press-probe]').removeAttribute('data-press-probe')")
    else:
        box = el.bounding_box()
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        page.mouse.down()
        page.wait_for_timeout(250)
        down = el.evaluate(SCALE_JS)
        page.mouse.move(2, 2)
        page.mouse.up()
    page.wait_for_timeout(900)
    return down, el.evaluate(SCALE_JS)


@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["1440", "390"])
def test_every_button_and_card_presses_in_and_springs_back(matrix, alt, viewport):  # noqa: F811
    page = matrix(viewport, motion=True, signed_in=True)
    open_square(page, viewport)
    page.wait_for_timeout(1200)
    for sel in CONTROLS:
        if page.locator(sel).locator("visible=true").count() == 0:
            assert sel in MAY_BE_ABSENT, f"{sel} is not on the page"
            continue
        down, after = press_and_release(page, sel)
        assert down == pytest.approx(0.96, abs=0.005), f"{sel} went to {down} while pressed"
        assert after == pytest.approx(1, abs=0.001), f"{sel} is at {after} after letting go"
    assert page.errors == []


def test_nothing_presses_under_reduced_motion(matrix, alt):  # noqa: F811
    page = matrix(DESKTOP, motion=False, signed_in=True)
    open_square(page, DESKTOP)
    for sel in (".v2-w", ".dr-opt", ".dr-book"):
        down, after = press_and_release(page, sel)
        assert down == 1 and after == 1, sel


def test_the_press_is_the_shared_rule_and_pages_no_longer_press_by_transform():
    """The rule exists for the listed selectors and the old per-page `:active { transform: scale() }` presses (which would press twice) are gone from the v2 stylesheets."""
    css = Path(__file__).resolve().parent.parent / "assets" / "css"
    shared = (css / "v2.css").read_text()
    assert "scale: var(--v2-press-scale)" in shared and "transition: scale var(--v2-release) var(--spring)" in shared
    for name in ("v2", "v2drawer", "tripmatrix", "matrixbook", "v2plan", "v2rail", "cv2"):
        for line in (css / f"{name}.css").read_text().splitlines():
            if ":active" in line and "::after" not in line and " .bx" not in line and ".mxb-cb" not in line:
                assert not re.search(r":active[^{]*\{[^}]*transform", line), f"{name}.css presses by transform: {line.strip()}"
