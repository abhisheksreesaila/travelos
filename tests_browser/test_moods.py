"""F-260 in a real browser: each of the five skies (`/plan/ask?mood=`, the showcase's preview) in light and dark at 1440 and 390. The words over the sky read 4.5:1 on the pixels the
page really paints (the method of test_v2_targets.py: hide the words, photograph, compare each word with the median pixel where it sits); the sun shows by day and the moon and stars by night.
Set F260_SHOTS=1 for docs/report/f260-<mood>-<scheme>-<width>.png."""
import os
import re
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from gitaway import moods
from tests_browser.helpers import DESKTOP, PHONE

SHOTS = Path(__file__).resolve().parent.parent / "docs" / "report"

WORDS_JS = """() => [...document.querySelectorAll('.v2-top *, #main *')].filter(e => [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())).map(e => {
  const r = e.getBoundingClientRect(), s = getComputedStyle(e);
  return {t: e.textContent.trim().slice(0, 30), x: r.left, y: r.top, w: r.width, h: r.height, c: s.color, shown: r.width > 2 && r.height > 2 && s.visibility === 'visible' && +s.opacity > 0 && r.top >= 0 && r.bottom <= innerHeight};
}).filter(w => w.shown)"""


def lum(c):
    v = [x / 255 for x in c[:3]]
    v = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in v]
    return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]


@pytest.fixture
def sky(browser, base_url):
    contexts = []

    def sky(mood, scheme, viewport):
        ctx = browser.new_context(viewport=viewport, reduced_motion="reduce")
        ctx.set_default_timeout(5000)
        contexts.append(ctx)
        if scheme == "dark":
            ctx.add_init_script("try { localStorage.setItem('ga-mode', 'dark'); } catch (e) {}")
        page = ctx.new_page()
        page.goto(f"{base_url}/plan/ask?mood={mood}")
        page.wait_for_selector(f".v2-bg[data-mood='{mood}']")
        page.wait_for_timeout(300)
        return page

    yield sky
    for c in contexts:
        c.close()


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["390", "1440"])
@pytest.mark.parametrize("mood", moods.MOODS)
def test_every_word_over_each_sky_reads_4_5_to_1_and_the_sun_becomes_the_moon(sky, mood, scheme, viewport):
    page = sky(mood, scheme, viewport)
    if os.environ.get("F260_SHOTS"):
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f"f260-{mood}-{scheme}-{viewport['width']}.png"))
    state = page.evaluate("""() => { const o = s => { const e = document.querySelector('.v2-bg ' + s); return e ? +getComputedStyle(e).opacity : null; };
      return {moon: o('.moon'), stars: o('.stars'), sun: o('.sunball'), mode: document.documentElement.dataset.mode, foot: document.querySelectorAll('.v2-bg .shore *').length}; }""")
    assert state["mode"] == scheme
    assert (state["moon"], state["stars"]) == ((1, 1) if scheme == "dark" else (0, 0))
    if scheme == "dark":
        assert state["sun"] == 0
    elif mood != "celebration":
        assert state["sun"] == 1      # the dusk has no sun
    assert state["foot"] > 4          # the mood's one object is drawn
    words = page.evaluate(WORDS_JS)
    assert len(words) > 8
    page.add_style_tag(content="#main *, .v2-top * { color: transparent !important; text-decoration-color: transparent !important; }")
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


def test_a_real_address_cannot_set_the_mood_off_the_showcase(browser, base_url, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    page = browser.new_page()
    page.goto(f"{base_url}/plan/ask?mood=snow")
    assert page.get_attribute(".v2-bg", "data-mood") == "beach"
    page.close()
