"""F-251 review: every control on the widget rail (.wg), the drawer (.dr) and the checkout (.mxb) is a 48px target (laptop and phone, light and dark), and every word on the glass rail reads 4.5:1
on the pixels the blur really paints (the method of test_tripmatrix.py's rail test, here on the phone's row of cards too)."""
from io import BytesIO

import pytest
from playwright.sync_api import expect

from tests_browser.helpers import DESKTOP, PHONE, open_rail
from tests_browser.test_matrixbook_sheet import fill, open_square, to_review  # noqa: F401 (fixtures and helpers)
from tests_browser.test_tripmatrix import WORDS_JS, matrix, stand  # noqa: F401 (fixtures)
from tests_browser.test_tripview import alt  # noqa: F401 (fixture)

CONTROLS = ("a[href], button, summary, select, textarea, [role=button], [role=radio], [role=tab], input:not([type=hidden]):not([type=checkbox]):not([type=radio]), "
            "label:has(> input[type=checkbox]), label:has(> input[type=radio])")

SMALL_JS = """([scope, controls]) => [...document.querySelectorAll(scope)].flatMap(root => [...root.querySelectorAll(controls)]).filter(el => {
    const r = el.getBoundingClientRect(), s = getComputedStyle(el);
    if (r.width <= 4 || r.height <= 4 || s.visibility !== 'visible' || el.closest('[hidden], [disabled], [aria-hidden="true"]') || parseFloat(s.opacity) === 0) return false;
    if (s.display === 'inline' && el.parentElement && [...el.parentElement.childNodes].some(n => n !== el && n.nodeType === 3 && n.textContent.trim())) return false;     // an inline link in a sentence
    return Math.min(r.width, r.height) < 47.5;
  }).map(el => (el.getAttribute('aria-label') || el.textContent || el.className).replace(/\\s+/g, ' ').trim().slice(0, 40) + ' ' + Math.round(el.getBoundingClientRect().width) + 'x' + Math.round(el.getBoundingClientRect().height))"""


def small(page, scope):
    return page.evaluate(SMALL_JS, [scope, CONTROLS])


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["390", "1440"])
def test_the_rail_the_drawer_and_the_checkout_controls_are_all_48px_targets(matrix, alt, viewport, scheme):  # noqa: F811
    page = matrix(viewport, signed_in=True, scheme=scheme)
    open_rail(page)
    expect(page.locator("#mx-rail .wg:not([hidden])").first).to_be_visible()
    page.wait_for_timeout(700)
    assert small(page, "#mx-rail") == [], "the rail"
    view = open_square(page, viewport)
    page.wait_for_timeout(900)
    assert small(page, ".dr") == [], "the drawer, the stay open and the flights a summary card"
    view.locator(".dr-fly .dr-mini").click()      # F-258: one side at a time, so the flights' own controls are measured open, the stay as its summary
    page.wait_for_timeout(700)
    assert small(page, ".dr") == [], "the drawer, the flights open and the stay a summary card"
    view.locator(".dr-stay .dr-mini").click()
    page.wait_for_timeout(700)
    view.locator(".dr-book").click()
    expect(page.locator(".mxb-sheet")).to_be_visible()
    page.wait_for_timeout(900)
    assert small(page, ".mxb") == [], "the checkout, the guest"
    fill(page)
    page.wait_for_timeout(500)
    assert small(page, ".mxb") == [], "the checkout, the contact"
    page.click("[data-cont]")
    page.wait_for_timeout(500)
    assert small(page, ".mxb") == [], "the checkout, the requests"
    page.click("[data-cont]")
    page.wait_for_timeout(500)
    assert small(page, ".mxb") == [], "the checkout, the review"
    page.click(".mxb-agree")
    page.click(".mxb-go")
    expect(page.locator(".mxb-id").first).to_contain_text("SAMPLE-")
    page.wait_for_timeout(1200)
    assert small(page, ".mxb") == [], "the pass"
    assert page.errors == []


def lum(c):
    v = [x / 255 for x in c[:3]]
    v = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in v]
    return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["390", "1440"])
def test_every_word_on_the_glass_rail_reads_on_the_painted_pixels(matrix, viewport, scheme):
    """Hide every word on the rail, photograph the page and compare each word's colour with the median pixel where it sits (look.py skips a gradient)."""
    import re

    from PIL import Image
    page = matrix(viewport)
    page.evaluate(f"localStorage.setItem('ga-mode', '{scheme}')")
    page.reload()
    page.wait_for_selector("#mx.is-live")
    page.wait_for_function("() => document.getElementById('mx').dataset.busy === '0'")
    open_rail(page)
    expect(page.locator("#mx-rail .wg:not([hidden])").first).to_be_visible()
    page.wait_for_timeout(900)
    page.evaluate("() => { const r = document.getElementById('mx-rail'); r.scrollLeft = 0; }")
    words = [w for w in page.evaluate(WORDS_JS.replace("'#mx *'", "'#mx-rail *'").replace("!e.closest('.mx-pop, .mx-isle, .mx-side, .is-off')", "true")) if w["shown"]]
    assert len(words) > 8
    page.add_style_tag(content="#mx-rail * { color: transparent !important; text-decoration-color: transparent !important; }")
    shot = Image.open(BytesIO(page.screenshot(full_page=True))).convert("RGB")
    low = []
    for w in words:
        box = (int(w["x"]), int(w["y"]), int(w["x"] + w["w"]), int(w["y"] + w["h"]))
        if box[2] > shot.width or box[3] > shot.height or box[0] < 0:
            continue
        px = sorted(shot.crop(box).getdata(), key=lum)
        bg = px[len(px) // 2]
        m = re.findall(r"[\d.]+", w["c"])
        fg = [float(x) * (255 if w["c"].startswith("color(srgb") else 1) for x in m[:3]]
        a = float(m[3]) if len(m) > 3 else 1.0
        fg = [f * a + b * (1 - a) for f, b in zip(fg, bg)]
        hi, lo = max(lum(fg), lum(bg)), min(lum(fg), lum(bg))
        if (hi + 0.05) / (lo + 0.05) < 4.5:
            low.append((w["t"], round((hi + 0.05) / (lo + 0.05), 2), w["k"]))
    assert not low, low
