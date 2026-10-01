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


def test_phone_expanded_cars_hides_the_context_column():
    """F-028: expanding Cars on a phone shows only Cars. `.ws-grid[data-expanded] .ws-context { display: flex }` has the same weight
    as the Cars rule, so the Cars rule must come after it inside the phone block."""
    text = css("workspace.css")
    phone = phone_blocks(text)
    show = phone.index(".ws-grid[data-expanded] .ws-context { display: flex")
    hide = phone.index('.ws-grid[data-expanded="cars"] .ws-context { display: none; }')
    assert hide > show
    assert "[data-pane] { display: flex; }" not in phone  # an expanded context pane hides its siblings, as on desktop


def test_phone_text_floor_is_13px():
    """F-034: every small size goes through --text-min, which is 13px on phones and 11px elsewhere."""
    tokens = css("tokens.css")
    assert re.search(r"@media \(max-width: 720px\)\s*\{\s*:root\s*\{[^}]*--text-min: 13px", tokens)
    for path in CSS_DIR.glob("*.css"):
        for m in re.finditer(r"font(?:-size)?:\s*(?:\w+\s+)*?(max\(var\(--text-min\), )?(\d*\.?\d+)rem", css(path.name)):
            assert m.group(1) or float(m.group(2)) * 16 >= 13, f"{path.name}: {m.group(0)} is under 13px on a phone"


def test_no_ellipsis_in_any_css():
    """F-034: labels wrap or shorten, never `text-overflow: ellipsis` (docs/lessons.md)."""
    for path in CSS_DIR.glob("*.css"):
        assert not re.search(r"text-overflow\s*:\s*ellipsis", css(path.name)), path.name


TAP_TARGETS = {  # file -> selectors that must be at least 2.75rem (44px at the 16px phone root) in a phone block
    "base.css": [".ga-brand", ".ga-nav a"],
    "workspace.css": [".ws-focus", ".ws-expand", ".ws-fork", ".ws-forklist"],
    "creators.css": [".cr-link", ".cr-hint a"],
    "hub.css": [".hub-search input"],
    "calendar.css": [".cal-seg", ".cal-w-head", ".cal-w-empty a", ".cal-dayadd"],
    "forks.css": [".fk-link"],
    "trip.css": [".tp-chip", ".tp-tab", ".tp-back", ".tp-go", ".tp-full", ".tp-btn", ".tp-kind"],
}


def test_phone_touch_targets_are_44px():
    """F-034: links, buttons and inputs get 2.75rem (44px) of height on a phone."""
    for name, selectors in TAP_TARGETS.items():
        phone = phone_blocks(css(name))
        for sel in selectors:
            rules = re.findall(r"(?:^|[},\s])" + re.escape(sel) + r"(?:\s*,[^{}]*)?\s*\{([^}]*)\}", phone)
            assert any(re.search(r"(?<![\w-])(?:min-)?height:\s*2\.75rem", r) for r in rules), f"{name}: {sel} lacks a 44px phone target"


def test_stay_card_tags_wrap_instead_of_clipping():
    """F-036: at 1000 wide the tag row clipped "Pool" and "Pet friendly"."""
    rule = re.search(r"(?m)^\.ws-tags\s*\{([^}]*)\}", css("workspace.css")).group(1)
    assert "flex-wrap: wrap" in rule and "overflow: hidden" not in rule


def test_landing_clips_sideways_overflow_from_the_pop_in():
    """F-036: the 1.06 overshoot of the door and feature pop-in must not widen the page."""
    text = css("landing.css")
    assert re.search(r"#main\s*\{[^}]*overflow-x:\s*clip", text)
    assert "scale(1.06)" in text or "scale(1.06)" in css("base.css")  # the overshoot is still there; it is contained, not removed
