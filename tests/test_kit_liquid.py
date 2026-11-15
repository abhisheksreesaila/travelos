"""F-264: the kit's optional FastHTML helpers (kit/liquid/liquid.py) draw the markup liquid.css and liquid.js expect."""
import sys
from pathlib import Path

from fasthtml.common import H2, Main, P, to_xml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "kit" / "liquid"))
import liquid  # noqa: E402


def test_page_shell_is_a_body_with_a_sky_a_pill_with_the_current_section_and_the_account_menu():
    bar = liquid.top_bar([("home", "Home", "/"), ("docs", "Docs", "/docs")], "docs", {"initials": "AB", "name": "Ada Byron", "items": [("Settings", "/settings")], "signout": "/out"})
    html = "".join(to_xml(x) for x in liquid.page_shell(bar, Main(liquid.glass_card(H2("Hi")), liquid.card(P("Words"))), title="T", mood="snow", quiet=False))
    assert '<body class="lq">' in html and 'class="lq-sky"' in html and 'data-mood="snow"' in html
    assert '<a href="/docs" aria-current="page">Docs</a>' in html and '<a href="/">Home</a>' in html
    assert 'aria-label="Ada Byron: account menu"' in html and '<a href="/settings" role="menuitem" tabindex="-1">Settings</a>' in html and 'action="/out"' in html
    assert '<div class="lq-card lq-glass">' in html and '<div class="lq-card">' in html
    assert 'href="/liquid/liquid.css"' in html and 'src="/liquid/liquid.js"' in html


def test_a_quiet_sky_and_an_unknown_mood():
    assert 'class="lq-sky is-quiet"' in to_xml(liquid.sky("city", quiet=True))
    assert 'data-mood="shore"' in to_xml(liquid.sky("volcano"))


def test_a_drawer_is_a_hidden_sheet_opened_by_id():
    html = to_xml(liquid.sheet("d", "Details", P("x"), drawer=True))
    assert html.startswith("<div ") and all(a in html.split(">")[0] for a in ('id="d"', 'class="lq-sheet is-drawer"', "hidden", 'aria-label="Details"')) and "data-lq-close" in html
