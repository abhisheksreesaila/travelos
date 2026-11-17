"""F-281 (D-890..D-894, docs/briefs/matrix-v5.md): the v2 pages' sky is the Harbour ground, a deep navy with a warm glow low on the horizon and two ridges, the same in light and dark
(light a little brighter), so the frosted glass over it has something to frost. The reading pages keep their quiet sky. Colours are tokens in v2-tokens.css; the art is inline SVG."""
import re
from pathlib import Path

from gitaway import v2

CSS = Path(__file__).resolve().parent.parent / "assets" / "css"
TOKENS = (CSS / "v2-tokens.css").read_text()
DARK = TOKENS[TOKENS.index(':root[data-mode="dark"]:has(.v2)'):]
LIGHT = TOKENS[:TOKENS.index(':root[data-mode="dark"]:has(.v2)')]
GROUND = ("--hb-a", "--hb-b", "--hb-c", "--hb-glow", "--hb-ridge", "--hb-ridge-2")


def test_the_harbour_ground_is_tokens_for_light_and_for_dark():
    for token in GROUND:
        assert f"{token}:" in LIGHT and f"{token}:" in DARK, token
    assert "--sky-ink: #F4F7FB" in LIGHT and "--sky-ink-2:" in LIGHT      # the words on the ground are one colour in both modes
    assert "--hb-a: #1B2A41" in LIGHT and "--hb-c: #7A4C30" in LIGHT and "--hb-glow: #F2B47A" in LIGHT      # the approved prototype's values (docs/design/matrix-v5)
    assert "--hb-a: #0D1420" in DARK and "--hb-c: #4A2E1E" in DARK


def test_the_busy_sky_draws_the_ridges_and_the_quiet_sky_does_not():
    busy = str(v2.bg())
    assert busy.count('class="r1"') == 1 and busy.count('class="r2"') == 1 and 'class="ridges"' in busy
    assert "ridges" not in str(v2.bg(quiet=True))


def test_the_ground_paints_with_the_tokens_and_not_with_literal_colours():
    css = re.sub(r"/\*.*?\*/", "", (CSS / "v2.css").read_text(), flags=re.S)
    rule = re.search(r"\.v2-bg:not\(\.is-quiet\) \{[^}]*\}", css).group(0)
    assert "var(--hb-a)" in rule and "var(--hb-b)" in rule and "var(--hb-c)" in rule and "var(--hb-glow)" in rule
    assert not re.search(r"#[0-9a-f]{3,8}\b", rule, re.I)
    assert "var(--hb-ridge)" in css and "var(--hb-ridge-2)" in css
