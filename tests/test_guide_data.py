"""F-262: what a guide knows (gitaway/guide.py) and where a draft of a planned trip comes from (creatordraft.from_plan). The post is The Planet D's "48 Hours in Lisbon" recorded through the app's
own fetcher (tests/fixtures/creator_import); nothing here reaches the network or a model. Every word of a guide is the creator's own: a stop's why is the post's sentence naming it, a cost only a
price that sentence says, a tip only one of the creator's tips naming the stop, and no travel time between stops (a stop has no coordinates)."""
import json
import re

import pytest

from gitaway import ai, creatordraft, guide as gd, safefetch
from tests.creator_import_support import Model, recorded
from tests.test_calendar import add, book
from tests.test_signin import person, sign_in, tid

KEY = "sk-ant-not-a-real-key-0000"
BELEM = "We didn’t go inside Belém Tower but admired it from the outside."


@pytest.fixture
def lisbon(client, monkeypatch):
    """The recorded post's draft, made by the magic import for a signed-in creator, and what a stranger sees of it once published."""
    url, web, answer = recorded()
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setattr(ai, "ANTHROPIC_TRANSPORT", Model(answer))
    monkeypatch.setattr(safefetch, "TRANSPORT", web)
    sign_in(client)
    r = client.post("/creators/import", data={"do": "draft", "link": url}, headers={"X-Magic": "1"})
    event = [json.loads(line) for line in r.text.splitlines() if line.strip()][-1]
    return creatordraft.get(tid(), event["id"])


def trip_of(d):
    return creatordraft.build(d, creatordraft.private_src(d["id"]), "Maya", True)


def test_a_stops_why_is_the_posts_own_sentence_that_names_it(lisbon):
    g = gd.from_trip(trip_of(lisbon))
    day1 = g.days[0].stops
    assert [s.name for s in day1][:2] == ["Belem Tower", "Jerónimos Monastery"]
    assert day1[0].why == BELEM and day1[0].note == "Go before the crowds."      # the creator's own note is kept beside the post's sentence, not instead of it
    assert day1[1].why.startswith("Just a short walk from Belém Tower is Jerónimos Monastery")
    assert day1[2].why == ""      # the post names Monument of Discoveries in no sentence of its own: nothing is invented to fill the line


def test_a_tip_badge_only_where_a_creator_tip_names_the_stop(lisbon):
    g = gd.from_trip(trip_of(lisbon))
    tips = {s.name: s.tip for d in g.days for s in d.stops if s.tip}
    assert tips == {"Belem Tower": "Go to Belém Tower before the crowds.", "Pastéis de Belém": "Sit inside at Pastéis de Belém: the line moves fast.", "Pena Palace": "Get to Pena Palace early, or book a timed entrance."}
    # the fourth tip (Tram 28 or a tuk-tuk) names no stop, so it is a tip of the guide and on no stop
    assert all(s.tip == "" for s in g.days[0].stops if s.name == "MAAT")


def test_the_tiles_are_only_what_the_guide_knows(lisbon):
    g = gd.from_trip(trip_of(lisbon))
    assert [(t.label, t.value) for t in g.tiles] == [("Days", "3 days"), ("Tips", "4 tips"), ("From", "theplanetd.com")]      # no season, budget, "getting around" or stay: the post's draft does not say
    assert g.tiles[0].sub == "17 stops"


def test_a_cost_is_only_a_price_the_creators_sentence_says():
    assert gd.cost_of("Tickets are $25 for 4 and worth it.") == "$25 for 4"
    assert gd.cost_of("It is about €12 per person.") == "€12 per person"
    assert gd.cost_of("Go before the crowds.") == ""


def test_plan_this_trip_carries_the_place_and_the_length_into_the_ask():
    href = gd.plan_href("San Diego", 2)
    assert href.startswith("/plan/ask?to=San%20Diego&d=") and "&r=" in href
    assert gd.plan_href("Nowhere Special") == "/plan/ask"


def test_a_draft_of_the_planned_trip_keeps_the_plans_and_marks_the_bookings_private(client):
    book(client)
    add(client, "a1", title="Taco lunch", start="12:00", end="13:00")
    me = person()
    d = creatordraft.from_plan(tid(), me, "Ari")
    stops = [(s["time"], s["name"]) for day in d["days"] for s in day["stops"]]
    assert stops == [("12:00 PM", "Taco lunch")] and re.fullmatch(r"\w+day, \w{3} \d+", d["days"][0]["title"]) and d["name"] == "Ari"      # the day is the calendar's own, e.g. "Saturday, Dec 19"
    assert d["private"] and {p["kind"] for p in d["private"]} <= set(creatordraft.PRIVATE_KINDS)
    trip = creatordraft.build(d, creatordraft.private_src(d["id"]), "ari", True)
    shown = json.dumps([(s.title, s.time, s.note) for day in trip.days for s in day.stops])
    for p in d["private"]:
        assert p["title"] not in shown      # a flight or a hotel is never one of the public stops


def test_a_trip_with_nothing_planned_makes_no_draft(client):
    book(client)
    with pytest.raises(creatordraft.HubError) as e:
        creatordraft.from_plan(tid(), person(), "Ari")
    assert str(e.value) == creatordraft.NO_PLANS
