"""F-253: the creator pages (landing, import, guides) wear design language v2 (docs/design/creators-v2, guides-v2). Their stylesheets are assets/css/cv2.css and guides.css over v2-tokens.css. Read from the real files:
the book keeps its paper in both modes, so every text pair on it is 4.5:1 or better in light and dark (the browser audit cannot measure a gradient), and
the stylesheets writes no time, no blur and no ellipsis of its own. (This replaced F-235's tests of for_creators.css and hub.css, the two stylesheets this design retires.)"""
import re
from pathlib import Path

import pytest

from gitaway import layout

CSS = Path(__file__).resolve().parent.parent / "assets" / "css"


def tokens(block_start):
    css = (CSS / "v2-tokens.css").read_text(encoding="utf-8")
    i = css.index(block_start)
    return dict(re.findall(r"(--[\w-]+)\s*:\s*(#[0-9A-Fa-f]{6})\b", css[i:css.index("\n}", i)]))


def lum(hexcolour):
    r, g, b = (int(hexcolour[i:i + 2], 16) / 255 for i in (1, 3, 5))
    c = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in (r, g, b)]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def ratio(a, b):
    x, y = sorted((lum(a), lum(b)), reverse=True)
    return (x + 0.05) / (y + 0.05)


LIGHT = lambda: tokens(":root:has(.v2) {")                          # noqa: E731
DARK = lambda: {**LIGHT(), **tokens(':root[data-mode="dark"]:has(.v2) {')}      # noqa: E731
BOOK_PAIRS = [("--bk-ink", "--bk-paper"), ("--bk-ink-2", "--bk-paper"), ("--bk-ink", "--bk-paper-2"), ("--bk-ink-2", "--bk-paper-2"), ("--bk-ink", "--bk-card"), ("--bk-ink-2", "--bk-card"),
              ("--bk-ink", "--bk-plate")]


@pytest.mark.parametrize("which", ["light", "dark"])
def test_every_text_pair_on_the_paper_is_4_5_to_1_or_better(which):
    t = LIGHT() if which == "light" else DARK()
    low = {f"{fg} on {bg}": round(ratio(t[fg], t[bg]), 2) for fg, bg in BOOK_PAIRS if ratio(t[fg], t[bg]) < 4.5}
    assert not low, low


def test_the_cover_nav_is_guides_and_plan_a_trip():
    assert layout.NAV == [("Postcards", "/guides"), ("Find a trip", "/plan/matrix")]      # F-289      # D-462: drawn as plan_href(); F-262: Guides replaced For creators and Community trips


@pytest.mark.parametrize("sheet", ["cv2.css", "guides.css"])
def test_the_stylesheet_uses_only_the_motion_tokens_and_no_blur_or_ellipsis(sheet):
    css = re.sub(r"/\*.*?\*/", "", (CSS / sheet).read_text(encoding="utf-8"), flags=re.S)
    assert not [t for t in re.findall(r"(?<![\w-])(\d*\.?\d+)m?s\b(?!\))", re.sub(r"var\(--[\w-]+\)", "", css)) if t not in ("0", "0.0")]
    assert "blur(" not in css and "backdrop-filter" not in css and "text-overflow" not in css and "line-clamp" not in css


def test_the_old_creator_and_hub_stylesheets_are_gone():
    assert not (CSS / "for_creators.css").exists() and not (CSS / "hub.css").exists() and not (CSS.parent / "js" / "for_creators.js").exists()
