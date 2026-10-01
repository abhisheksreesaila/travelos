"""F-046: the first note on an imported trip names only the lanes the trip really has, also after Replace."""
import re
from html import unescape

from gitaway import session as ses
from tests.test_signin import person
from tests.test_trip_import import TEMPLATE, imported, no_car


def first_note(client):
    html = client.get("/calendar?view=days").text
    return unescape(re.search(r'cal-note-first.*?class="cal-notetext">([^<]*)<', html, re.S).group(1))


def test_the_first_note_names_the_car_only_when_there_is_one(client):
    imported(client)
    assert "flights, hotel, and car are on the calendar" in first_note(client)
    trip_id = ses.trips(person())[0].id
    assert client.post("/trips/import/save", data={"text": no_car(), "replace": trip_id}, follow_redirects=False).status_code == 303
    note = first_note(client)
    assert "car" not in note.replace("Booked elsewhere", "") and "Your flights and hotel are on the calendar" in note


def test_a_stay_only_import_says_so(client):
    only_hotel = re.sub(r"\nflights:.*?(?=\nhotel:)", "", no_car(), flags=re.S)
    imported(client, only_hotel)
    assert "Your hotel is on the calendar" in first_note(client)
