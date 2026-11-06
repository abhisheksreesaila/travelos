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


def test_a_childs_name_in_a_day_note_is_flagged_in_the_preview(family):
    save(family, note_2="Mira loved the teacups.")
    says = re.search(WARN, preview(family))
    assert says and says.group(1) == "It mentions Mira from your family. Check they're happy to be on a public page."
    assert re.search(r'<input[^>]*name="names_ok"[^>]*type="checkbox"|<input[^>]*type="checkbox"[^>]*name="names_ok"', preview(family))
    assert "Yes, Mira is happy to be named" in preview(family)


@pytest.mark.parametrize("field, text, who", [
    ("tip", ["Theo needs a booster seat on Space Mountain."], "Theo"),
    ("title", "Mira and Theo at Disneyland", "Mira and Theo"),
    ("note_1", "Dinner with Priya and the kids.", "Priya"),
])
def test_a_name_anywhere_in_the_public_text_is_flagged(family, field, text, who):
    save(family, **{field: text})
    says = re.search(WARN, preview(family))
    assert says and says.group(1) == f"It mentions {who} from your family. Check they're happy to be on a public page."


def test_a_name_on_a_stop_is_flagged_too(family):
    family.post("/trip/plans", data={"id": "a1", "day": "1", "start": "10:00", "title": "Mira's birthday lunch", "kind": "fun"}, follow_redirects=False)
    save(family)
    assert "It mentions Mira from your family." in preview(family)


def test_a_name_on_a_boarding_pass_is_flagged(client):
    imported(client)           # the plain template: its children are "Kid 1" and "Kid 2"
    passes.save_pass(person("ari"), flight=passes.flights(person("ari"))[0]["key"], traveller="Juniper Cole")
    save(client, note_1="Juniper slept the whole flight.")
    assert "It mentions Juniper from your family." in preview(client)


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

def test_publishing_a_page_that_names_a_child_waits_for_the_tick(family):
    save(family, note_2="Mira loved the teacups.")
    r = publish_it(family)
    assert r.status_code == 409
    assert "This page names Mira from your family. Tick the box to say they are happy to be on a public page, then publish." in unescape(r.text)
    assert live() == [] and community.creator_of(person("ari")["user_id"]) is None        # no page, and no profile address was made either


def test_with_the_tick_it_goes_live(family):
    save(family, note_2="Mira loved the teacups.")
    r = publish_it(family, names_ok="1")
    assert r.status_code == 303 and r.headers["location"].startswith("/trip/publish?live=1")
    (row,) = live()
    assert "Mira loved the teacups." in row["snapshot"]


def test_a_page_that_names_no_one_publishes_with_no_tick(family):
    save(family, note_2="Rope drop at eight.")
    assert publish_it(family).status_code == 303 and len(live()) == 1


def test_updating_a_page_after_adding_a_name_asks_again(family):
    save(family, note_2="Rope drop at eight.")
    publish_it(family)
    save(family, note_2="Theo rode it twice.")
    assert publish_it(family).status_code == 409
    assert "Rope drop at eight." in live()[0]["snapshot"] and "Theo" not in live()[0]["snapshot"]


def test_the_name_check_reads_a_photos_caption_and_alt_text(family):
    trip = Itinerary(slug="x", title="Our week", headline="Our week:", accent="Ari's", place="LA", lede="", author="Ari",
                     days=[Day(1, "DAY 1", "Day one", "", [Stop("", "Teacups")], photos=[Polaroid("/p.jpg", "Photo from day 1, Theo on the carousel", "Theo on the carousel")])])
    assert publish.mentions(person("ari"), trip) == ["Theo"]


@pytest.mark.parametrize("names, said", [(["Mira"], "Mira"), (["Mira", "Theo"], "Mira and Theo"), (["Mira", "Theo", "Sam"], "Mira, Theo and Sam")])
def test_names_are_listed_the_way_a_person_would_say_them(names, said):
    assert publish.join_names(names) == said


def test_two_names_make_the_tick_and_the_refusal_read_properly(family):
    save(family, note_2="Mira loved it and Theo rode twice.")
    assert "Yes, Mira and Theo are happy to be named" in preview(family)
    assert "This page names Mira and Theo from your family." in unescape(publish_it(family).text)
