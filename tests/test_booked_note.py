"""F-046: the first note on an imported trip names only the lanes the trip really has, also after Replace."""
import re
from html import unescape

from gitaway import session as ses
from tests.test_signin import person
from tests.test_trip_import import TEMPLATE, imported, no_car


def first_note(client):
    from gitaway.pages import dayshared
    return dayshared.booked_note(ses.booking(person()))

