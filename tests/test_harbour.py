"""F-296 (D-956..D-961, docs/design/palette-bo, look C Stage; it replaced F-281's Harbour ground): the v2 pages' ground is a flat #F5F5F7 (light) or #000 (dark) with nothing drawn on it. Colours are tokens in v2-tokens.css."""
import re
from pathlib import Path

from gitaway import v2

CSS = Path(__file__).resolve().parent.parent / "assets" / "css"
TOKENS = (CSS / "v2-tokens.css").read_text()
DARK = TOKENS[TOKENS.index(':root[data-mode="dark"]:has(.v2)'):]
LIGHT = TOKENS[:TOKENS.index(':root[data-mode="dark"]:has(.v2)')]
STAGE = {"light": ("--stage: #F5F5F7", "--card-solid: #FFFFFF", "--ink: #1D1D1F", "--cta-bg: #1D1D1F", "--pick: #1D1D1F", "--sig: #F25500", "--sig-ink: #B84A00", "--good: #0F766E"),
         "dark": ("--stage: #000000", "--card-solid: #1C1C1E", "--card-2: #2C2C2E", "--ink: #F5F5F7", "--cta-bg: #F5F5F7", "--pick: #F5F5F7")}


def test_the_stage_is_flat_grey_tokens_for_light_and_for_dark():
    """F-296 (D-956): the Harbour ground (--hb-*, ridges, sun, moon) is retired for a flat Apple-grey stage."""
    for token in STAGE["light"]:
        assert token in LIGHT, token
    for token in STAGE["dark"]:
        assert token in DARK, token
    assert "--hb-" not in TOKENS and "--frost" not in TOKENS
    assert "--ground-ink: #1D1D1F" in LIGHT and "--ground-ink: #F5F5F7" in DARK      # the words straight on the stage


def test_the_stage_draws_nothing_busy_or_quiet():
    for sky in (str(v2.bg()), str(v2.bg(quiet=True))):
        for part in ("ridges", "sunball", "shore", "moon", "stars", "data-mood", "<svg"):
            assert part not in sky, part


def test_the_stage_paints_flat_with_the_token():
    css = re.sub(r"/\*.*?\*/", "", (CSS / "v2.css").read_text(), flags=re.S)
    rule = re.search(r"\.v2-bg \{[^}]*\}", css).group(0)
    assert "background: var(--stage)" in rule and "gradient" not in rule
    assert "gradient" not in re.search(r"html:has\(\.v2-bg\) \{[^}]*\}", css).group(0)
    assert "ridges" not in css and "sunball" not in css


def test_the_ground_ink_has_its_own_name_and_never_reuses_direction_as_sky_ink():
    """Overnight walk 2026-11-17: --sky-ink already means the flight kind's ink in tokens.css and the weather ink in v2pages.css; the Harbour ground's word colour reusing it
    turned a pass label near-white on a card and ground words dark on the pages that load v2pages.css. The ground's words are --ground-ink, and v2 never redefines --sky-ink."""
    v2 = "".join((CSS / f).read_text() for f in ("v2-tokens.css", "v2.css", "v2rail.css"))
    assert "--ground-ink:" in v2 and not re.search(r"--sky-ink\s*:", (CSS / "v2-tokens.css").read_text())
    assert "var(--sky-ink" not in (CSS / "v2.css").read_text() + (CSS / "v2rail.css").read_text()
