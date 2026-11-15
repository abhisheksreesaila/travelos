"""F-261 in a real browser: the calm palette and the quiet reading sky (D-700, D-701).

* A reading page (a creator's book, the details editor, the import) shows no sun, moon, clouds, shore or mood object, only the soft gradient; booking (/plan/ask) and planning (/trip/plan)
  keep theirs.
* Every primary action (Book my trip, Save plan, the pass's Plan this trip) is one solid indigo, never a gradient, and reads 4.5:1; the planning hero is a card with ink on it; the pass is a
  solid deep indigo. Dark is set through localStorage ga-mode.
* Every word on a reading page reads 4.5:1 on the pixels the page really paints (the method of test_moods.py), light and dark, at 1440 and 390.
Set F261_SHOTS=1 for docs/report/f261-<label>-<page>-<width>.png (F261_LABEL=before on the code before the change, default after)."""
import os
import re
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from playwright.sync_api import expect

from tests_browser.helpers import DESKTOP, PHONE
from tests_browser.test_creator_edit import drafted, lisbon  # noqa: F401 (fixture and helper)
from tests_browser.test_matrixbook_sheet import open_square, sandbox  # noqa: F401 (fixtures and helper)
from tests_browser.test_moods import WORDS_JS, lum
from tests_browser.test_planv2 import plan  # noqa: F401 (fixture)
from tests_browser.test_tripmatrix import matrix, stand  # noqa: F401 (fixtures)

SHOTS = Path(__file__).resolve().parent.parent / "docs" / "report"
OBJECTS = ".v2-bg .sunball, .v2-bg .moon, .v2-bg .cloud, .v2-bg .shore, .v2-bg .stars"
CTA_JS = """(sel) => [...document.querySelectorAll(sel)].filter(e => e.getBoundingClientRect().width > 0).map(e => { const s = getComputedStyle(e);
  return {sel, bg: s.backgroundColor, image: s.backgroundImage, fg: s.color}; })"""


def ratio(a, b):
    hi, lo = max(lum(a), lum(b)), min(lum(a), lum(b))
    return (hi + 0.05) / (lo + 0.05)


def rgb(c):
    return [float(x) for x in re.findall(r"[\d.]+", c)[:3]]


def shot(page, page_name, viewport):
    if os.environ.get("F261_SHOTS"):
        page.wait_for_timeout(900)
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f"f261-{os.environ.get('F261_LABEL', 'after')}-{page_name}-{viewport['width']}.png"))


def painted_words_read(page):
    """The words that fail 4.5:1 on the painted pixels (hide every word, photograph, compare with the median pixel where it sits)."""
    words = page.evaluate(WORDS_JS.replace("'.v2-top *, #main *'", "'.v2-top *, #main *:not(.book-wrap *)'"))      # the book itself is paper, drawn in 3D: its own tests (F-253) read it
    assert len(words) > 5
    page.add_style_tag(content="#main *, .v2-top * { color: transparent !important; text-decoration-color: transparent !important; }")
    img = Image.open(BytesIO(page.screenshot())).convert("RGB")
    low = []
    for w in words:
        box = (int(w["x"]), int(w["y"]), int(w["x"] + w["w"]), int(w["y"] + w["h"]))
        if box[0] < 0 or box[1] < 0 or box[2] > img.width or box[3] > img.height:
            continue      # off the screen (the guide's tiles scroll sideways on a phone): there are no painted pixels to read it on
        px = sorted(img.crop(box).getdata(), key=lum)
        bg = px[len(px) // 2]
        m = re.findall(r"[\d.]+", w["c"])
        fg = [float(x) * (255 if w["c"].startswith("color(srgb") else 1) for x in m[:3]]
        a = float(m[3]) if len(m) > 3 else 1.0
        fg = [f * a + b * (1 - a) for f, b in zip(fg, bg)]
        if ratio(fg, bg) < 4.5:
            low.append((w["t"], round(ratio(fg, bg), 2)))
    return low


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["390", "1440"])
def test_reading_pages_have_a_quiet_sky_and_every_word_reads_on_it(browser, base_url, lisbon, viewport, scheme):  # noqa: F811
    c, page, did = drafted(browser, base_url, viewport, lisbon, dark=scheme == "dark")
    for path, name in ((f"/creators/import/{did}/guide", "guide"), (f"/creators/import/{did}", "editor"), ("/creators/import", "import")):
        page.goto(base_url + path)
        page.wait_for_selector(".v2-bg")
        page.wait_for_timeout(500)
        assert page.evaluate("document.documentElement.dataset.mode") == scheme
        assert page.get_attribute(".v2-bg", "data-sky") == "quiet", path
        assert page.locator(OBJECTS).count() == 0, path
        assert page.evaluate("getComputedStyle(document.querySelector('.v2-bg')).backgroundImage").count("gradient") >= 2      # the soft gradient is there
        shot(page, name, viewport)
        assert painted_words_read(page) == [], path
    c.close()


def test_booking_and_planning_keep_their_sun_and_shore(browser, base_url, plan):  # noqa: F811
    page = plan(DESKTOP)
    for url in (f"{base_url}/plan/ask", f"{base_url}/trip/plan"):
        page.goto(url)
        page.wait_for_selector(".v2-bg")
        assert page.get_attribute(".v2-bg", "data-sky") is None
        assert page.locator(".v2-bg .sunball").count() == 1 and page.locator(".v2-bg .shore").count() == 1, url
        expect(page.locator(".v2-bg .sunball")).to_be_visible()
        assert page.evaluate("+getComputedStyle(document.querySelector('.v2-bg .sunball')).opacity") > 0.8, url


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_planning_is_calm_a_card_for_the_hero_and_solid_indigo_for_save(plan, scheme):  # noqa: F811
    page = plan(DESKTOP, scheme)
    hero = page.evaluate("""() => { const s = getComputedStyle(document.querySelector('.pl-trip'));
      return {bg: s.backgroundColor, image: s.backgroundImage, fg: s.color, h1: getComputedStyle(document.querySelector('.pl-trip h1')).color}; }""")
    assert hero["image"] == "none"      # a card: no gradient on it
    card = rgb(hero["bg"])
    assert ratio(rgb(hero["h1"]), card) >= 4.5 and ratio(rgb(hero["fg"]), card) >= 4.5
    save = page.evaluate(CTA_JS, ".pl .save")[0]
    assert save["image"] == "none" and rgb(save["bg"]) == ([67, 56, 202] if scheme == "light" else [79, 70, 229])
    assert ratio(rgb(save["fg"]), rgb(save["bg"])) >= 4.5


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["390", "1440"])
def test_book_my_trip_the_sheet_and_the_pass_are_solid_indigo(matrix, sandbox, viewport, scheme):  # noqa: F811
    page = matrix(viewport, signed_in=True, scheme=scheme)
    page.evaluate(f"localStorage.setItem('ga-mode', '{scheme}')")
    page.reload()
    page.wait_for_selector("#mx.is-live")
    page.wait_for_function("() => document.getElementById('mx').dataset.busy === '0'")
    panel = open_square(page, viewport)
    shot(page, "matrix-drawer", viewport)
    book = page.evaluate(CTA_JS, ".dr-book")[0]
    want = [67, 56, 202] if scheme == "light" else [79, 70, 229]
    assert book["image"] == "none" and rgb(book["bg"]) == want and ratio(rgb(book["fg"]), want) >= 4.5
    panel.locator(".dr-book").click()
    expect(page.locator(".mxb-sheet")).to_be_visible()
    page.wait_for_timeout(700)
    shot(page, "matrix-book", viewport)
    sheet = page.evaluate("""() => { const e = document.querySelector('.mxb-b1, [data-cont]'); const s = e && getComputedStyle(e); return s && {image: s.backgroundImage}; }""")
    assert sheet is None or "gradient" not in sheet["image"]
    pass_bg = page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--pass-bg').trim()")
    assert pass_bg == ("#1E1B4B" if scheme == "light" else "#2A2670") and ratio([255, 255, 255], [int(pass_bg[i:i + 2], 16) for i in (1, 3, 5)]) >= 4.5


@pytest.mark.skipif(not os.environ.get("F261_SHOTS"), reason="screenshots only on request")
@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["390", "1440"])
def test_screenshots_of_the_books_and_the_matrix(browser, base_url, lisbon, matrix, sandbox, viewport):  # noqa: F811
    """No assertions: the same pages photographed before (F261_LABEL=before, on the old code) and after, to docs/report."""
    c, page, did = drafted(browser, base_url, viewport, lisbon)
    for path, name in ((f"/creators/import/{did}/guide", "guide"), (f"/creators/import/{did}", "editor")):
        page.goto(base_url + path)
        page.wait_for_selector(".v2-bg")
        shot(page, name, viewport)
    c.close()
    page = matrix(viewport, signed_in=True)
    panel = open_square(page, viewport)
    shot(page, "matrix-drawer", viewport)
    panel.locator(".dr-book").click()
    expect(page.locator(".mxb-sheet")).to_be_visible()
    page.wait_for_timeout(700)
    shot(page, "matrix-book", viewport)


@pytest.mark.skipif(not os.environ.get("F261_SHOTS"), reason="screenshots only on request")
@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["390", "1440"])
def test_screenshots_of_planning(plan, viewport):  # noqa: F811
    page = plan(viewport)
    page.wait_for_timeout(600)
    shot(page, "plan", viewport)
