"""F-030: the site is sized in rem off one root size, so a single number scales every screen."""

import re
from pathlib import Path

CSS_DIR = Path(__file__).resolve().parent.parent / "assets/css"
CSS = sorted(CSS_DIR.glob("*.css"))


def strip_queries(css):
    return re.sub(r"@(media|container)[^{]*\{", "{", css)


def test_root_size_is_75_percent_and_phones_return_to_full_size():
    tokens = (CSS_DIR / "tokens.css").read_text()
    assert re.search(r":root\s*\{\s*(/\*.*?\*/\s*)?font-size:\s*12px", tokens, re.S)
    assert re.search(r"@media \(max-width: 720px\)\s*\{\s*:root\s*\{\s*font-size:\s*16px", tokens)


def test_no_fixed_pixel_sizes_left_except_hairlines():
    for path in CSS:
        css = re.sub(r"/\*.*?\*/", "", strip_queries(path.read_text()), flags=re.S)
        if path.name == "tokens.css":
            css = css.replace("font-size: 12px", "").replace("font-size: 16px", "").replace("--r-pill: 999px", "").replace("--text-min: 11px", "").replace("--text-min: 13px", "")
        found = [m for m in re.findall(r"(?<![\w.])(-?[\d.]+)px", css) if m not in ("1", "-1", "0")]
        assert not found, f"{path.name}: unscaled px values {found[:5]}"


def test_icons_scale_with_the_root():
    from gitaway.icons import icon

    svg = str(icon("plane", 24))
    assert "--ico:1.5rem" in svg and "width:1.5rem" not in svg  # no inline width/height: page CSS can override
    base = (CSS_DIR / "base.css").read_text()
    assert 'svg[style*="--ico"]' in base
    # the itinerary rules that resize icons must stay able to win (same specificity, loaded later)
    assert ".btn-round svg { width:" in (CSS_DIR / "itinerary.css").read_text()


def test_calendar_hour_grid_is_in_rem(client):
    from tests.test_calendar import book

    book(client)
    html = client.get("/calendar?view=days").text
    assert re.search(r"--top:[\d.]+rem;--h:[\d.]+rem", html)
    assert not re.search(r"--top:[\d.]+px", html)
    assert "HOUR_REM = 3" in client.get("/assets/js/calendar.js").text


def test_no_text_below_11px_on_desktop_and_tablet():
    """Any font size under 11px at the 12px root (0.9167rem) must go through the --text-min floor."""
    for path in CSS:
        css = re.sub(r"/\*.*?\*/", "", path.read_text(), flags=re.S)
        for m in re.finditer(r"font(?:-size)?:\s*(?:\w+\s+)*?(max\(var\(--text-min\), )?(\d*\.?\d+)rem", css):
            if float(m.group(2)) * 12 < 11:
                assert m.group(1), f"{path.name}: {m.group(0)} renders under 11px"
    tokens = (CSS_DIR / "tokens.css").read_text()
    assert "--text-min: 11px" in tokens and "--text-min: 13px" in tokens
