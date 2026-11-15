"""F-028, F-034, F-036: small polish. CSS is checked as text (no browser in the test suite); the running app was checked in Chromium."""

import re
from pathlib import Path

CSS_DIR = Path(__file__).resolve().parent.parent / "assets/css"


def css(name):
    return re.sub(r"/\*.*?\*/", "", (CSS_DIR / name).read_text(), flags=re.S)


def phone_blocks(text):
    """The text of every `@media (max-width: 720px) {...}` block, joined."""
    out = []
    for m in re.finditer(r"@media \(max-width: 720px\)", text):
        depth, i = 0, text.index("{", m.start())
        for j in range(i, len(text)):
            depth += text[j] == "{"
            depth -= text[j] == "}"
            if depth == 0:
                out.append(text[i:j])
                break
    return "\n".join(out)


def test_phone_text_floor_is_13px():
    """F-034, F-200: every small size goes through a floor: --text-min for words (16px on phones since F-200, 12px elsewhere) or --label-min for an all-caps label (13px on
    phones, 12px elsewhere), so nothing on a phone is under 13px."""
    tokens = css("tokens.css")
    phone = re.search(r"@media \(max-width: 720px\)\s*\{\s*:root\s*\{([^}]*)", tokens).group(1)
    assert "--text-min: 16px" in phone and "--label-min: 13px" in phone
    for path in CSS_DIR.glob("*.css"):
        for m in re.finditer(r"font(?:-size)?:\s*(?:[\w-]+\s+)*?(max\(var\(--(?:text|label)-min\), )?(\d*\.?\d+)rem", css(path.name)):
            assert m.group(1) or float(m.group(2)) * 16 >= 13, f"{path.name}: {m.group(0)} is under 13px on a phone"


def test_no_ellipsis_in_any_css():
    """F-034: labels wrap or shorten, never `text-overflow: ellipsis` (docs/lessons.md)."""
    for path in CSS_DIR.glob("*.css"):
        assert not re.search(r"text-overflow\s*:\s*ellipsis", css(path.name)), path.name


TAP_TARGETS = {  # file -> selectors that must be at least 2.75rem (44px at the 16px phone root) in a phone block
    "base.css": [".ga-brand", ".ga-nav a"],
    "workspace.css": [".ws-focus", ".ws-expand", ".ws-fork", ".ws-forklist"],
    "creators.css": [".cr-link", ".cr-hint a"],
    "cv2.css": [".cv .hub-search input"],
    "forks.css": [".fk-link"],
    "phone.css": [".ph-tab"],
    "trip.css": [".tp-chip", ".tp-tab", ".tp-back", ".tp-go", ".tp-full", ".tp-btn", ".tp-kind"],
}

