"""F-261 (D-700, D-701): the calm palette and the quiet reading sky.

Ink and indigo carry the UI; the pink-to-violet gradient is the Instagram share card's alone (gitaway/sharecard.py), so no v2 stylesheet may draw it. The palette is tokens in
assets/css/v2-tokens.css (--cta-bg, --head-bg, --pass-bg), so changing it later is one place. A reading page (a guide, the creator's details editor, the import) opts in with
`layout.page(..., quiet=True)`: its sky has no sun, moon, clouds, shore or mood object."""
import re
from pathlib import Path

import pytest

from gitaway import v2
from tests.test_signin import sign_in

CSS = Path(__file__).resolve().parent.parent / "assets" / "css"
V2_STYLES = ["v2-tokens.css", "v2.css", "v2-moods.css", "v2drawer.css", "v2plan.css", "v2rail.css", "cv2.css", "cvedit.css", "matrixbook.css"]
PINK_VIOLET = re.compile(r"#8b2fc9|#c92a5e|#9333ea|#db2777|#c026d3|rgb\(\s*139[ ,]+47[ ,]+201|rgb\(\s*201[ ,]+42[ ,]+94|rgb\(\s*147[ ,]+51[ ,]+234|rgb\(\s*219[ ,]+39[ ,]+119", re.I)


@pytest.mark.parametrize("name", V2_STYLES)
def test_no_v2_stylesheet_draws_the_pink_to_violet_gradient(name):
    css = (CSS / name).read_text()
    assert "--sunset" not in css
    for m in re.finditer(r"(?:repeating-)?(?:linear|radial|conic)-gradient\([^;{}]*", css):
        assert not PINK_VIOLET.search(m.group(0)), (name, m.group(0)[:120])


def test_the_palette_is_tokens_in_one_place_light_and_dark():
    css = (CSS / "v2-tokens.css").read_text()
    dark = css[css.index(':root[data-mode="dark"]:has(.v2)'):]
    for token in ("--cta-bg", "--pass-bg", "--quiet-glow"):
        assert css.count(f"{token}:") == 2 and token in dark       # defined once for light and once for dark
    assert re.search(r"--cta-bg: #4338CA;", css) and "--head-bg: var(--card-solid)" in css


def test_the_primary_actions_take_the_indigo_token():
    for name, selector in (("v2drawer.css", ".dr-book"), ("v2plan.css", ".pl .save"), ("matrixbook.css", ".mxb-plan"), ("matrixbook.css", ".mxb-b1.sun")):
        rule = re.search(r"^" + re.escape(selector) + r" \{[^}]*\}", (CSS / name).read_text(), re.M).group(0)
        assert "background: var(--cta-bg)" in rule, (name, selector)


def test_a_quiet_sky_has_no_sun_moon_clouds_shore_or_mood_object():
    quiet = str(v2.bg(quiet=True))
    assert 'data-sky="quiet"' in quiet and "is-quiet" in quiet
    for part in ("sunball", "moon", "cloud", "shore", "stars", "data-mood"):
        assert part not in quiet
    busy = str(v2.bg())
    assert "sunball" in busy and "shore" in busy


def test_reading_pages_ask_for_the_quiet_sky_and_booking_and_the_cover_do_not(client):
    sign_in(client)
    assert 'data-sky="quiet"' in client.get("/creators/import").text
    ask = client.get("/plan/ask").text
    assert "sunball" in ask and 'data-sky="quiet"' not in ask
    assert "sunball" in client.get("/for-creators").text
