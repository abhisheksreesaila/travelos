"""F-235: the two joyful pages' own tokens (--fc-* on For creators, --hub-* on Community trips). Read from the real stylesheets: the two dark blocks are the same, every token has a light and a dark
value, and the text pairs the browser audit cannot measure (it skips gradients: the sunset wash, the sky, the buttons) are 4.5:1 or better in both modes. The header nav is still layout.NAV."""
import re
from pathlib import Path

import pytest

from gitaway import layout

CSS = Path(__file__).resolve().parent.parent / "assets" / "css"


def block(css, start):
    i = css.index(start)
    return dict(re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", css[i:css.index("}", i)]))


def modes(name, scope):
    css = (CSS / name).read_text(encoding="utf-8")
    light = block(css, f"{scope} {{\n  color-scheme: light;")
    by_system = block(css, f":root:not([data-mode=\"light\"]) {scope} {{")
    by_choice = block(css, f":root[data-mode=\"dark\"] {scope} {{")
    return light, by_system, by_choice


def lum(hexcolour):
    r, g, b = (int(hexcolour[i:i + 2], 16) / 255 for i in (1, 3, 5))
    c = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in (r, g, b)]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def ratio(a, b):
    x, y = sorted((lum(a), lum(b)), reverse=True)
    return (x + 0.05) / (y + 0.05)


@pytest.mark.parametrize("name,scope", [("for_creators.css", ".fc"), ("hub.css", ".hub")])
def test_the_two_dark_blocks_are_the_same_and_every_token_has_both_modes(name, scope):
    light, by_system, by_choice = modes(name, scope)
    assert by_system == by_choice, "the two dark blocks must stay the same"
    colours = {k for k in light if k != "--fc-shadow" and k != "--hub-shadow"}
    assert colours <= set(by_choice), f"no dark value for {colours - set(by_choice)}"


FC_PAIRS = [("--fc-ink", "--fc-wash-1"), ("--fc-ink", "--fc-wash-2"), ("--fc-ink", "--fc-wash-3"), ("--fc-ink", "--fc-wash-4"), ("--fc-ink-2", "--fc-wash-1"), ("--fc-ink-2", "--fc-wash-2"),
            ("--fc-ink-2", "--fc-wash-3"), ("--fc-ink-2", "--fc-wash-4"), ("--fc-ink", "--fc-bg"), ("--fc-ink-2", "--fc-bg"), ("--fc-ink-2", "--fc-card"), ("--fc-ink-2", "--fc-tint"),
            ("--fc-a", "--fc-card"), ("--fc-a", "--fc-bg"), ("--fc-on", "--fc-a"), ("--fc-on", "--fc-b"), ("--fc-on", "--fc-c"), ("--fc-bg", "--fc-ink"),
            ("--fc-a-i", "--fc-a-t"), ("--fc-b-i", "--fc-b-t"), ("--fc-c-i", "--fc-c-t"), ("--fc-g-i", "--fc-g-t"), ("--fc-a-i", "--fc-tint"), ("--fc-b-i", "--fc-tint"), ("--fc-c-i", "--fc-tint"),
            ("--fc-g-i", "--fc-tint"), ("--fc-b-i", "--fc-g-t")]
HUB_PAIRS = [("--hub-ink", "--hub-sky-1"), ("--hub-ink", "--hub-sky-2"), ("--hub-ink", "--hub-sand"), ("--hub-ink-2", "--hub-sky-1"), ("--hub-ink-2", "--hub-sky-2"), ("--hub-ink-2", "--hub-sand"),
             ("--hub-ink", "--hub-card"), ("--hub-ink-2", "--hub-card"), ("--hub-ink", "--hub-paper"), ("--hub-ink-2", "--hub-paper"), ("--hub-lagoon", "--hub-card"), ("--hub-lagoon", "--hub-paper"),
             ("--hub-on", "--hub-lagoon"), ("--hub-stamp", "--hub-card"), ("--hub-paper", "--hub-ink"), ("--hub-share-ink", "--hub-share-a"), ("--hub-share-ink", "--hub-share-b"),
             ("--hub-share-a", "--hub-share-ink"), ("--hub-ink", "--hub-cloud")]


@pytest.mark.parametrize("name,scope,pairs", [("for_creators.css", ".fc", FC_PAIRS), ("hub.css", ".hub", HUB_PAIRS)])
@pytest.mark.parametrize("which", ["light", "dark"])
def test_every_text_pair_is_4_5_to_1_or_better(name, scope, pairs, which):
    light, _, dark = modes(name, scope)
    tokens = light if which == "light" else {**light, **dark}
    low = {f"{fg} on {bg}": round(ratio(tokens[fg], tokens[bg]), 2) for fg, bg in pairs if ratio(tokens[fg], tokens[bg]) < 4.5}
    assert not low, low


def test_the_header_nav_is_still_the_sites_three_links():
    assert layout.NAV == [("For creators", "/for-creators"), ("Community trips", "/community"), ("Plan a trip", "/plan/matrix")]      # D-462: drawn as plan_href()


def test_both_pages_use_only_the_motion_tokens_and_no_blur():
    for name in ("for_creators.css", "hub.css", "creatorimport.css"):
        css = re.sub(r"/\*.*?\*/", "", (CSS / name).read_text(encoding="utf-8"), flags=re.S)
        assert not re.findall(r"(?<![\w-])\d*\.?\d+m?s\b(?!\))", re.sub(r"var\(--[\w-]+\)", "", css)), name
        assert "blur(" not in css and "backdrop-filter" not in css
