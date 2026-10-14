"""F-142: Ask in the panel. The server side: the panel marks itself for an editor (data-ask, the compose bar's "or press /"), the week says which day Ask opens, the box answers the panel's
fragment for each mode (talk starts the microphone, paste and type leave it to be tapped) and a viewer gets none of it. The browser side is tests_browser/test_day_ask.py."""
import re

from tests.test_canvas import azure  # noqa: F401 - fixture
from tests.test_canvas_pages import added, crew  # noqa: F401 - fixtures
from tests.test_day_dock import dock
from tests.test_trip_canvas import bare, text, trip  # noqa: F401 - fixtures

ASK = {"X-Ask": "1"}


def page(client, url):
    r = client.get(url)
    assert r.status_code == 200
    return bare(r.text)


def test_an_editors_panel_is_marked_for_ask_and_its_compose_bar_says_press_slash(trip):
    d = dock(page(trip, "/trip/canvas?day=1"))
    assert re.search(r'<aside\b[^>]*\bdata-ask="1"', d)
    bar = re.search(r'<a\b[^>]*id="cz-dock-compose".*?</a>', d, re.S).group(0)
    assert text(bar).startswith("Type to Ask") and "or press" in text(bar) and "<kbd" in bar and ">/<" in bar


def test_a_viewers_panel_has_no_ask(crew, azure):
    ari, viewer = crew
    added(ari)
    d = dock(page(viewer, "/trip/canvas?day=1"))
    assert "data-ask" not in d.split(">", 1)[0] and "cz-dock-compose" not in d
    assert viewer.get("/trip/ask?day=1", headers=ASK).status_code == 403          # and the box itself is refused


def test_the_week_says_which_day_ask_opens(trip):
    section = re.search(r'<section\b[^>]*data-level="week"[^>]*>', page(trip, "/trip/canvas")).group(0)
    assert re.search(r'data-ask-day="\d"', section)


def test_the_panels_box_follows_the_mode_it_was_asked_for(trip):
    talk = trip.get("/trip/ask?day=1&mode=talk", headers=ASK).text
    paste = trip.get("/trip/ask?day=1&mode=paste", headers=ASK).text
    plain = trip.get("/trip/ask?day=1&mode=type", headers=ASK).text
    phone = trip.get("/trip/ask?day=1", headers=ASK).text
    assert 'data-mode="talk"' in talk and 'data-mode="paste"' in paste
    assert "data-mode" not in plain                                          # typing: the note is focused, the microphone waits to be tapped
    assert 'data-mode="talk"' in phone                                       # the phone's sheet is as it was
    for html in (talk, paste, plain):
        assert 'id="ak-mic"' in html and 'id="ak-text"' in html and 'id="ak-paste"' in html and 'id="ak-day"' in html
