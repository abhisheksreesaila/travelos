"""F-194 (7): a family's public trip page is checked for the names of the people on the trip, children included (the imported trip's travellers, the names on boarding passes, the
family's members). A name the public text says blocks publishing until the editor ticks that those people are happy to be named: nothing goes live (and no profile address is made) before."""

import re
from html import unescape

import pytest

from gitaway import community, passes, publish
from gitaway.itineraries import Day, Itinerary, Polaroid, Stop
from tests.test_signin import person, sign_in
from tests.test_trip_import import TEMPLATE, imported

NAMED = TEMPLATE.replace("name: Kid 1", "name: Mira Rivera").replace("name: Kid 2", "name: Theo")


@pytest.fixture
def family(client):
    """Ari with the imported LA trip whose two children are Mira (7) and Theo (4)."""
    imported(client, NAMED)
    return client


def save(client, **over):
    data = {"title": "Our Disneyland week", "name": "Ari", "stickers": ["kid"], **over}
    r = client.post("/trip/publish/save", data=data, follow_redirects=False)
    assert r.status_code == 303, r.text[:300]


def preview(client):
    return unescape(client.get("/trip/publish/preview").text)


def publish_it(client, **form):
    return client.post("/trip/publish", data=form, follow_redirects=False)


def live():
    return community.rows(kind="scrapbook")


WARN = r'id="pb-warn"[^>]*>(.*?)</p>'


def test_nothing_flagged_when_the_public_text_names_no_one(family):
    save(family, note_2="Rope drop at eight, then the teacups.", tip=["Bring a poncho."])
    assert 'id="pb-warn"' not in preview(family) and "names_ok" not in preview(family)


def test_the_name_inside_another_word_is_not_the_name(family):
    save(family, note_2="We walked to the Miracle Mile and watched a Theodolite demo.")
    assert 'id="pb-warn"' not in preview(family)


def test_the_placeholder_names_an_import_makes_are_not_people(client):
    imported(client)           # "Kid 1", "Kid 2" and the title "LA with the kids"
    save(client, note_1="A kid friendly day for every kid.")
    assert 'id="pb-warn"' not in preview(client)


def test_the_person_publishing_may_say_their_own_name(family):
    save(family, note_2="Ari carried the stroller all day.")
    assert 'id="pb-warn"' not in preview(family)


# ---- it blocks -----------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("names, said", [(["Mira"], "Mira"), (["Mira", "Theo"], "Mira and Theo"), (["Mira", "Theo", "Sam"], "Mira, Theo and Sam")])
def test_names_are_listed_the_way_a_person_would_say_them(names, said):
    assert publish.join_names(names) == said

