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


def test_phone_expanded_context_pane_keeps_the_other_panes_underneath():
    """F-028: base rules hide the other context panes at 0,4,0; the phone rule must win by coming later at the same weight."""
    text = css("workspace.css")
    base_hide = text.index('.ws-grid[data-expanded="weather"] .ws-context > :not([data-pane="weather"])')
    phone = phone_blocks(text)
    rule = ".ws-grid[data-expanded] .ws-context > [data-pane] { display: flex; }"
    assert rule in phone
    assert text.index(rule) > base_hide
    # the expanded pane leads, the others follow
    assert re.search(r'\.ws-grid\[data-expanded="weather"\] \.ws-context > \[data-pane="weather"\][^{]*\{\s*order: -1', phone)
