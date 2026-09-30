"""The calendar joins the shared page shell rules (see docs/lessons.md): tokens, then base, then page CSS."""

from tests.test_calendar import book
from tests.test_signin import sign_in


def test_stylesheets_load_tokens_then_base_then_the_calendar_css_signed_in(client):
    sign_in(client)
    pages = {"no booking": client.get("/calendar").text}
    book(client)
    for url in ["/calendar", "/calendar?demo=long", "/calendar?view=whole", "/calendar?add=1&at=10:00", "/calendar?edit=a1"]:
        pages[url] = client.get(url).text
    for name, html in pages.items():
        assert html.count("/assets/css/tokens.css") == 1 and html.count("/assets/css/base.css") == 1, name
        assert html.index("/assets/css/tokens.css") < html.index("/assets/css/base.css") < html.index("/assets/css/calendar.css"), name


def test_the_calendar_route_is_registered_and_no_longer_a_placeholder(client):
    from gitaway.pages import placeholders
    assert "/calendar" not in placeholders.PLACEHOLDERS
    book(client)
    assert "Your trip calendar" not in client.get("/calendar").text
