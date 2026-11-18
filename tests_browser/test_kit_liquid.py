"""F-264 in a real browser: the liquid design kit's gallery (kit/liquid/index.html, opened from disk, no server). Every word over each sky (five moods and the quiet one) in light and dark at
1440 and 390 reads 4.5:1 on the pixels the page really paints (the method of tests_browser/words.py), the sun becomes the moon, every target is 48px, and press, sheet, menu, combobox, folds, toasts
and the mode toggle work. Set F264_SHOTS=1 for kit/liquid/shots/gallery-<width>-<scheme>.jpg."""
import os
import re
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from tests_browser.words import lum

KIT = Path(__file__).resolve().parent.parent / "kit" / "liquid"
URL = (KIT / "index.html").as_uri()
LAPTOP = {"width": 1440, "height": 1500}      # tall: every word of the gallery is on screen at once
PHONE = {"width": 390, "height": 3400}
SKIES = ["shore", "snow", "hills", "party", "city", "quiet"]

WORDS_JS = """() => [...document.querySelectorAll('body *')].filter(e => !['SCRIPT', 'STYLE'].includes(e.tagName) && [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())).map(e => {
  const r = e.getBoundingClientRect(), s = getComputedStyle(e);
  return {t: e.textContent.trim().slice(0, 30), x: r.left, y: r.top, w: r.width, h: r.height, c: s.color, shown: r.width > 2 && r.height > 2 && s.visibility === 'visible' && +s.opacity > 0 && r.top >= 0 && r.bottom <= innerHeight};
}).filter(w => w.shown)"""


@pytest.fixture
def gallery(browser):
    contexts = []

    def open_gallery(viewport, scheme="light", motion=False):
        ctx = browser.new_context(viewport=viewport, color_scheme=scheme, reduced_motion=None if motion else "reduce")
        ctx.set_default_timeout(5000)
        contexts.append(ctx)
        page = ctx.new_page()
        page.goto(URL)
        page.wait_for_selector(".lq-sky .foot")
        page.evaluate("document.fonts.ready")
        return page

    yield open_gallery
    for c in contexts:
        c.close()


def sky(page, name):
    page.click("[data-lq-quiet]" if name == "quiet" else f"[data-lq-mood={name}]")


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("viewport", [PHONE, LAPTOP], ids=["390", "1440"])
@pytest.mark.parametrize("name", SKIES)
def test_every_word_over_each_sky_reads_4_5_to_1_and_the_sun_becomes_the_moon(gallery, name, scheme, viewport):
    page = gallery(viewport, scheme)
    sky(page, name)
    state = page.evaluate("""() => { const o = s => { const e = document.querySelector('.lq-sky ' + s); return e && getComputedStyle(e).display !== 'none' ? +getComputedStyle(e).opacity : null; };
      return {moon: o('.moon'), stars: o('.stars'), sun: o('.sun'), mode: document.documentElement.dataset.mode, foot: document.querySelectorAll('.lq-sky .foot *').length}; }""")
    assert state["mode"] == scheme
    if name == "quiet":
        assert (state["moon"], state["sun"], state["stars"]) == (None, None, None)      # a reading sky has no objects
    else:
        assert (state["moon"], state["stars"]) == ((1, 1) if scheme == "dark" else (0, 0))
        assert state["sun"] == (None if name == "party" else 0 if scheme == "dark" else 1)      # the dusk has no sun
        assert state["foot"] > 4      # the mood's one object is drawn
    words = page.evaluate(WORDS_JS)
    assert len(words) > 40
    page.add_style_tag(content="body * { color: transparent !important; text-decoration-color: transparent !important; }")
    shot = Image.open(BytesIO(page.screenshot())).convert("RGB")
    low = []
    for w in words:
        box = (int(w["x"]), int(w["y"]), int(w["x"] + w["w"]), int(w["y"] + w["h"]))
        px = sorted(shot.crop(box).getdata(), key=lum)
        bg = px[len(px) // 2]
        m = re.findall(r"[\d.]+", w["c"])
        fg = [float(x) * (255 if w["c"].startswith("color(srgb") else 1) for x in m[:3]]
        a = float(m[3]) if len(m) > 3 else 1.0
        fg = [f * a + b * (1 - a) for f, b in zip(fg, bg)]
        hi, lo = max(lum(fg), lum(bg)), min(lum(fg), lum(bg))
        if (hi + 0.05) / (lo + 0.05) < 4.5:
            low.append((w["t"], round((hi + 0.05) / (lo + 0.05), 2)))
    assert not low, low


TARGETS_JS = """() => [...document.querySelectorAll('button, a[href], input, [role=menuitem]')].filter(e => { const r = e.getBoundingClientRect(), s = getComputedStyle(e);
  return r.width > 0 && r.height > 0 && s.visibility === 'visible' && !e.closest('[hidden]'); }).map(e => { const r = e.getBoundingClientRect(); return [e.textContent.trim().slice(0, 20) || e.getAttribute('aria-label') || e.name, Math.round(r.width * 10) / 10, Math.round(r.height * 10) / 10]; })
  .filter(([, w, h]) => w < 47.5 || h < 47.5)"""


@pytest.mark.parametrize("viewport", [PHONE, LAPTOP], ids=["390", "1440"])
def test_every_target_is_48px_including_the_open_menu_and_a_toast(gallery, viewport):
    page = gallery(viewport)
    page.click("#me")
    page.click("[data-lq-toast='Moved to Friday']")
    page.wait_for_selector(".lq-toast button")
    assert page.evaluate(TARGETS_JS) == []
    assert page.evaluate("document.querySelectorAll('.lq-menu [role=menuitem]').length") == 3


def test_a_button_goes_in_when_pressed_and_springs_back(gallery):
    page = gallery(LAPTOP, motion=True)
    btn = page.locator(".lq-btn", has_text="Primary")
    box = btn.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down()
    page.wait_for_timeout(300)      # the press is 90ms
    assert btn.evaluate("e => getComputedStyle(e).scale") == "0.96"
    page.mouse.up()
    page.wait_for_timeout(900)      # the release is 480ms on the spring
    assert btn.evaluate("e => getComputedStyle(e).scale") == "none"


def test_a_sheet_grows_from_its_button_on_a_phone_and_fades_on_a_laptop_and_folds_away(gallery):
    keys = """() => { const a = document.getElementById('sheet').getAnimations()[0]; return a ? a.effect.getKeyframes().flatMap(k => Object.keys(k)).filter(k => ['clipPath', 'transform', 'opacity'].includes(k)).filter((k, i, all) => all.indexOf(k) === i).sort() : []; }"""
    page = gallery({"width": 390, "height": 844}, motion=True)
    page.click("[data-lq-sheet=sheet]")
    assert page.evaluate(keys) == ["clipPath", "opacity", "transform"]      # clipped to the button's rectangle and let out on the spring
    page.wait_for_function("document.getElementById('sheet').getAnimations().length === 0")
    assert page.is_visible("#sheet") and page.evaluate("document.activeElement.id") == "sheet"
    page.keyboard.press("Escape")
    page.wait_for_function("document.getElementById('sheet').hidden")
    assert page.evaluate("document.activeElement.dataset.lqSheet") == "sheet"      # focus is back on the button
    page = gallery({"width": 1440, "height": 900}, motion=True)
    page.click("[data-lq-sheet=sheet]")
    assert page.evaluate(keys) == ["opacity"]      # a laptop: a calm fade, nothing grows
    page.wait_for_function("document.getElementById('sheet').getAnimations().length === 0")
    page.click("#sheet [data-lq-close]")
    page.wait_for_function("document.getElementById('sheet').hidden")
    page.click("[data-lq-sheet=drawer]")
    box = page.locator("#drawer").bounding_box()
    assert box["x"] + box["width"] > 1400 and box["height"] > 860      # the drawer is a panel at the right edge of a laptop
    page.click(".lq-scrim")
    page.wait_for_function("document.getElementById('drawer').hidden")


def test_the_avatar_menu_opens_walks_with_the_arrows_and_closes_on_escape_and_outside(gallery):
    page = gallery(LAPTOP)
    page.click("#me")
    assert page.get_attribute("#me", "aria-expanded") == "true" and page.is_visible("#menu")
    assert page.evaluate("document.activeElement.textContent") == "Profile"
    page.keyboard.press("ArrowDown")
    assert page.evaluate("document.activeElement.textContent") == "Settings"
    page.keyboard.press("Escape")
    page.wait_for_function("document.getElementById('menu').hidden")
    assert page.evaluate("document.activeElement.id") == "me" and page.get_attribute("#me", "aria-expanded") == "false"
    page.click("#me")
    page.mouse.click(20, 800)
    page.wait_for_function("document.getElementById('menu').hidden")


def test_the_search_box_suggests_and_choosing_only_fills_the_box(gallery):
    page = gallery(LAPTOP)
    page.fill("[data-lq-combobox]", "gl")
    page.wait_for_selector(".lq-opt")
    assert page.locator(".lq-opt").all_inner_texts() == ["Glass\nover the sky"]
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    assert page.input_value("[data-lq-combobox]") == "Glass"
    assert not page.is_visible("#sug")
    page.fill("[data-lq-combobox]", "s")
    page.wait_for_selector(".lq-opt")
    page.keyboard.press("Escape")
    assert not page.is_visible("#sug")


def test_the_cards_open_one_at_a_time(gallery):
    page = gallery(LAPTOP)
    heads = page.locator(".lq-fold-h")
    assert [heads.nth(i).get_attribute("aria-expanded") for i in range(3)] == ["true", "false", "false"]
    heads.nth(2).click()
    assert [heads.nth(i).get_attribute("aria-expanded") for i in range(3)] == ["false", "false", "true"]
    assert page.locator(".lq-fold.is-open").count() == 1


def test_a_toast_says_it_and_undo_replaces_it(gallery):
    page = gallery(LAPTOP)
    page.click("[data-lq-toast='Moved to Friday']")
    assert page.locator(".lq-toast").all_inner_texts() == ["Moved to Friday\nUndo"]
    page.click(".lq-toast button")
    page.wait_for_function("document.querySelector('.lq-toast .lq-toast-t').textContent === 'Undone'")
    assert page.locator(".lq-toast").count() == 1


def test_the_mode_toggle_is_remembered(gallery):
    page = gallery(LAPTOP)
    assert page.evaluate("document.documentElement.dataset.mode") == "light"
    page.click("[data-lq-mode]")
    assert page.evaluate("[document.documentElement.dataset.mode, localStorage.getItem('lq-mode'), document.querySelector('[data-lq-mode]').getAttribute('aria-pressed')]") == ["dark", "dark", "true"]
    page.reload()
    assert page.evaluate("document.documentElement.dataset.mode") == "dark"


@pytest.mark.skipif(not os.environ.get("F264_SHOTS"), reason="screenshots only on request")
@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("width", [1440, 390])
def test_save_the_gallery_screenshots(gallery, width, scheme):
    page = gallery({"width": width, "height": 900 if width == 1440 else 844}, scheme)
    assert page.evaluate("document.documentElement.scrollWidth") == width      # no sideways scroll
    png = page.screenshot()
    img = Image.open(BytesIO(png)).convert("RGB")
    (KIT / "shots").mkdir(exist_ok=True)
    img.save(KIT / "shots" / f"gallery-{width}-{scheme}.jpg", quality=55, optimize=True)
