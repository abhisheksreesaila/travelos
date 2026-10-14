"""F-059: booked items are calm, colourful and clearly booked: a soft tint per kind, not black; "Booked elsewhere" said once, quietly."""
import re
from datetime import date
from html import unescape

from tests.test_trip_import import imported
from tests.test_trip_phone import at  # noqa: F401  (the clock fixture)


def shown(html):
    """What a sighted person reads: the page without tags, attributes (aria-labels), scripts and screen-reader-only text."""
    html = re.sub(r"<(script|style)\b.*?</\1>", " ", html, flags=re.S)
    html = re.sub(r'<span class="sr-only">.*?</span>', " ", html, flags=re.S)
    return unescape(re.sub(r"<[^>]+>", " ", html))


def test_the_phone_today_view_tints_by_kind_and_says_booked_elsewhere_once(client, at):
    imported(client)
    at(date(2026, 10, 17), "07:00")  # the arrival day from the next morning: its whole list shows (today's up-next item moves into the card)
    html = client.get("/trip?day=0").text
    assert "tp-k-sky" in html and "tp-k-grape" in html and "tp-k-sun" in html  # flight, hotel, car
    assert shown(html).lower().count("booked elsewhere") == 1
    assert "booked on Expedia" not in shown(html)
