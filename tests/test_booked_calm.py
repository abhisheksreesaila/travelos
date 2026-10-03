"""F-059: booked items are calm, colourful and clearly booked: a soft tint per kind, not black; "Booked elsewhere" said once, quietly."""
import re
from datetime import date
from html import unescape

from tests.test_calendar import tag
from tests.test_trip_import import imported
from tests.test_trip_phone import at  # noqa: F401  (the clock fixture)

KINDS = {"b-out": "flight", "b-back": "flight", "b-in": "hotel", "b-out2": "hotel", "b-car-pick": "car", "b-car-drop": "car"}


def shown(html):
    """What a sighted person reads: the page without tags, attributes (aria-labels), scripts and screen-reader-only text."""
    html = re.sub(r"<(script|style)\b.*?</\1>", " ", html, flags=re.S)
    html = re.sub(r'<span class="sr-only">.*?</span>', " ", html, flags=re.S)
    return unescape(re.sub(r"<[^>]+>", " ", html))


def test_each_booked_block_wears_its_kind_and_keeps_its_icon_lock_and_labels(client):
    imported(client)
    html = client.get("/calendar?view=days").text
    for bid, kind in KINDS.items():
        node = tag(html, "data-block", bid)
        assert f"cal-bk-{kind}" in node["class"] and "cal-booked" in node["class"], bid
        assert "Booked, locked, Booked elsewhere · Expedia" in node["aria-label"], bid  # screen readers still hear all of it
        block = re.search(r'<a\s[^>]*data-block="%s".*?</a>' % bid, html, re.S).group(0)
        assert "cal-lock" in block and "<svg" in block
    assert "Check in 3:00 PM" in shown(html) and "Check out 11:00 AM" in shown(html)


def test_booked_elsewhere_is_said_once_quietly_not_on_every_block(client):
    imported(client)
    for url in ("/calendar?view=days", "/calendar?view=whole", "/calendar"):
        assert shown(client.get(url).text).lower().count("booked elsewhere") == 1, url
    assert "cal-elsewhere" not in client.get("/calendar?view=days").text


def test_the_whole_trip_list_and_day_dots_follow_the_palette(client):
    imported(client)
    html = client.get("/calendar?view=whole").text
    assert "cal-bk-flight" in html and "cal-bk-hotel" in html and "cal-bk-car" in html
    days = client.get("/calendar?view=days").text  # the day chips (and their dots) are on the day views
    assert re.search(r"cal-dot cal-dot-booked cal-bk-(flight|hotel|car)", days)


def test_the_phone_today_view_tints_by_kind_and_says_booked_elsewhere_once(client, at):
    imported(client)
    at(date(2026, 10, 17), "07:00")  # the arrival day from the next morning: its whole list shows (today's up-next item moves into the card)
    html = client.get("/trip?day=0").text
    assert "tp-k-sky" in html and "tp-k-grape" in html and "tp-k-sun" in html  # flight, hotel, car
    assert shown(html).lower().count("booked elsewhere") == 1
    assert "booked on Expedia" not in shown(html)
