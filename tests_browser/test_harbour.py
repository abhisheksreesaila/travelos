"""F-281 (D-890..D-894, docs/briefs/matrix-v5.md) in a real browser: the Stage (F-296: a flat grey ground; it replaced the Harbour ground) and the Fill chips.

* The v2 pages' sky is the Stage (F-296: a flat grey ground; it replaced the Harbour ground) (the approved prototype's colours) in light and dark; a reading page keeps its quiet sky.
* Every word on the page (on the ground, on glass, on a card, on the chips' tray) reads 4.5:1 on the pixels the page really paints, light and dark, at 1440 and 390 (the method of test_moods.py:
  hide the words, photograph, compare each word with the median pixel where it sits). `F281_RATIOS=1` prints the lowest ratio per kind of surface for the decision line.
* The extra-info tray is titled "More to know before you pick"; its chips have a coloured icon, a title, a teaser and, where the server has one, a count; 48px targets; opening one still fetches
  on demand (F-277: tests_browser/test_rail_extra.py). `F281_SHOTS=1` writes docs/report/f281-<page>-<width>-<scheme>.png.
"""
import os
import re
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from playwright.sync_api import expect

from tests_browser.helpers import DESKTOP, PHONE, set_mode
from tests_browser.test_calm_palette import ratio, rgb
from tests_browser.words import WORDS_JS, lum
from tests_browser.test_tripmatrix import matrix, stand  # noqa: F401 (fixtures)

REPORT = Path(__file__).resolve().parent.parent / "docs" / "report"
STAGE = {"light": "rgb(245, 245, 247)", "dark": "rgb(0, 0, 0)"}      # --stage (F-296, D-956)
KINDS_JS = """() => [...document.querySelectorAll('.v2-top *, #main *')].filter(e => [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())).map(e => {
  const r = e.getBoundingClientRect(), s = getComputedStyle(e);
  const kind = e.closest('.rl-tray') ? 'tray' : e.closest('.v2-glass') ? 'glass' : e.closest('.mx-card, .sentence, .v2-card, [class*=card]') ? 'card' : 'ground';
  return {t: e.textContent.trim().slice(0, 30), kind, x: r.left, y: r.top, w: r.width, h: r.height, c: s.color,
          shown: r.width > 2 && r.height > 2 && s.visibility === 'visible' && +s.opacity > 0 && r.top >= 0 && r.bottom <= innerHeight && r.left >= 0 && r.right <= innerWidth,
          closed: !!((d) => d && !d.open && !e.closest('summary'))(e.closest('details')),
          hit: (on => on(0.5) && [0.05, 0.95].some(on))(f => (h => !!h && e.contains(h))(document.elementFromPoint(r.left + r.width * f, r.top + r.height / 2)))};      // review: a word whose middle and one end are in view is measured; one a floating bar sits on (its middle covered) is not
}).filter(w => w.shown && !w.closed && w.hit)"""      # not a word in a closed popover, and not one a floating bar or the grid's edge cuts


def painted_ratios(page):
    """[(kind, text, ratio)] for every visible word, read on the pixels the page paints."""
    words = page.evaluate(KINDS_JS)
    assert len(words) > 2
    hide = page.add_style_tag(content="#main *, .v2-top * { color: transparent !important; text-decoration-color: transparent !important; }")
    shot = Image.open(BytesIO(page.screenshot())).convert("RGB")
    hide.evaluate("e => e.remove()")
    out = []
    for w in words:
        box = (max(int(w["x"]), 0), max(int(w["y"]), 0), min(int(w["x"] + w["w"]), shot.width), min(int(w["y"] + w["h"]), shot.height))
        if box[2] <= box[0] or box[3] <= box[1]:
            continue
        px = sorted(shot.crop(box).getdata(), key=lum)
        bg = px[len(px) // 2]
        m = re.findall(r"[\d.]+", w["c"])
        fg = [float(x) * (255 if w["c"].startswith("color(srgb") else 1) for x in m[:3]]
        a = float(m[3]) if len(m) > 3 else 1.0
        fg = [f * a + b * (1 - a) for f, b in zip(fg, bg)]
        out.append((w["kind"], w["t"], round(ratio(fg, bg), 2), [round(w[k]) for k in ("x", "y", "w", "h")], w["c"], bg))
    return out


def shot(page, name, viewport, scheme):
    if os.environ.get("F281_SHOTS"):
        page.wait_for_timeout(700)
        page.screenshot(path=str(REPORT / f"f281-{name}-{viewport['width']}-{scheme}.png"))


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["390", "1440"])
def test_the_ground_is_the_stage_and_every_word_reads_4_5_to_1_on_it(matrix, viewport, scheme):  # noqa: F811
    page = matrix(viewport, scheme=scheme)
    set_mode(page, scheme)
    page.wait_for_selector("#mx-rail .wchip[data-wg]")
    got = page.evaluate("""() => { const e = document.querySelector('.v2-bg'), s = getComputedStyle(e);
      return {image: s.backgroundImage, bg: s.backgroundColor, kids: e.children.length, html: getComputedStyle(document.documentElement).backgroundColor,
              brand: getComputedStyle(document.querySelector('.v2-brand')).color}; }""")
    assert got["image"] == "none" and got["bg"] == STAGE[scheme] and got["html"] == STAGE[scheme] and got["kids"] == 0      # a flat stage, nothing drawn on it
    assert got["brand"] == ("rgb(29, 29, 31)" if scheme == "light" else "rgb(245, 245, 247)")      # the logo's word is the ground's ink
    shot(page, "matrix", viewport, scheme)
    ratios = []
    for y in (0, 700, 1400, 2100):      # the whole page, a screen at a time
        page.evaluate(f"window.scrollTo(0, {y})")
        page.wait_for_timeout(150)
        ratios += painted_ratios(page)
    low = [r for r in ratios if r[2] < 4.5]
    if os.environ.get("F281_RATIOS"):
        for kind in ("ground", "glass", "card", "tray"):
            mine = [r for r in ratios if r[0] == kind]
            print(f"RATIO {scheme} {viewport['width']} {kind}: min {min((r[2] for r in mine), default=None)} over {len(mine)} words")
    assert low == [], low


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["390", "1440"])
def test_the_chips_are_filled_a_title_a_teaser_a_count_and_48px(matrix, viewport, scheme):  # noqa: F811
    page = matrix(viewport, scheme=scheme)
    set_mode(page, scheme)
    page.wait_for_selector("#mx-rail .wchip[data-wg]")
    expect(page.locator("#mx-rail .rl-lab")).to_have_text("More to know before you pick")
    tray = page.locator("#mx-rail .rl-tray")
    assert tray.evaluate("t => getComputedStyle(t).backgroundColor") == ("rgb(29, 29, 31)" if scheme == "light" else "rgb(44, 44, 46)")      # the dark band, solid (F-296, D-958)
    chips = page.locator("#mx-rail .wchip[data-wg]")
    assert chips.count() >= 5
    for i in range(chips.count()):
        c = chips.nth(i)
        assert c.locator(".ic svg").count() == 1 and c.locator(".tx > span").inner_text().strip() and c.locator(".tx small").inner_text().strip()
        assert c.bounding_box()["height"] >= 47.5
        assert c.evaluate("e => getComputedStyle(e).backgroundImage") == "none"      # a flat chip on the dark band
    weather = page.locator("#mx-rail .wchip[data-wg='weather']")
    expect(weather.locator(".ct")).to_have_text("5 days")
    assert page.locator("#mx-rail .wchip[data-wg='where'] .ct").count() == 0      # a count only where there is one
    weather.click()
    expect(page.locator("#wg-weather")).to_be_visible()
    assert weather.evaluate("e => getComputedStyle(e).backgroundColor") == "rgb(255, 255, 255)"      # opened: a white chip on the dark band, in both modes (F-296)
    shot(page, "chips", viewport, scheme)
    assert [r for r in painted_ratios(page) if r[2] < 4.5] == []
    assert page.errors == []


def test_a_reading_page_is_marked_quiet_on_the_same_stage(browser, base_url):
    page = browser.new_page(viewport=DESKTOP)
    page.goto(base_url + "/privacy")
    page.wait_for_selector(".v2-bg")
    assert page.get_attribute(".v2-bg", "data-sky") == "quiet"
    assert page.locator(".v2-bg *").count() == 0
    assert page.evaluate("getComputedStyle(document.querySelector('.v2-bg')).backgroundImage") == "none"
    page.close()


@pytest.mark.parametrize("path", ["/guides", "/plan/ask"])
@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["390", "1440"])
def test_every_stage_page_not_only_the_matrix_reads_4_5_to_1(browser, base_url, path, viewport, scheme):
    """Overnight walk 2026-11-17: the guides hub's headline was --ink on the deep ground in light mode, near invisible, because only the matrix was measured. Every page on the
    Harbour ground is read the same way: each word against the pixels really painted under it."""
    page = browser.new_page(viewport=viewport)
    page.request.post(base_url + "/signin", data={"email": "harbour@example.com", "next": "/", "intent": "save"})
    page.goto(base_url + "/healthz")
    page.evaluate(f"localStorage.setItem('ga-mode', '{scheme}')")
    page.goto(base_url + path)
    page.wait_for_selector(".v2-bg")
    assert page.get_attribute(".v2-bg", "data-sky") != "quiet"
    page.wait_for_timeout(400)
    ratios = []
    for y in (0, 700):
        page.evaluate(f"window.scrollTo(0, {y})")
        page.wait_for_timeout(150)
        ratios += painted_ratios(page)
    low = [r for r in ratios if r[2] < 4.5]
    page.close()
    assert ratios and low == [], low
