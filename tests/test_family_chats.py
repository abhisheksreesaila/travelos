"""F-143: the trip's chats and what is unread in them (gitaway/familychats.py): the whole trip first, then each plan's and part's; unread counts per person; read marks that never
move back; and the panel's routes (the list, the pane, a thread opened directly on a laptop, the live poll with `read=1`)."""
import re

import pytest

from gitaway import canvas, familychats as fc, familythread as ft, plantalk, tripcal as cal
from tests.test_canvas import azure  # noqa: F401 - fixtures
from tests.test_canvas_pages import added
from tests.test_signin import person
from tests.test_thread import crew  # noqa: F401 - fixture (Ari, an editor and a viewer)


@pytest.fixture
def chats(crew, azure):
    """(ari's session, the editor's client, the viewer's client, the park plan's id, its Lunch part's id, the plain plan's id) on a trip with a park block and a plain plan."""
    from tests.test_calendar import add
    client, ed, vi = crew
    added(client)
    add(client)
    ari = person("ari")
    plan = canvas.plan(ari)["blocks"]
    park = next(a for a in cal.activities(ari) if a.id in plan)
    lunch = next(p for p in plan[park.id]["parts"] if p["name"] == "Lunch")
    stroll = next(a for a in cal.activities(ari) if a.title == "Venice Canals stroll")
    return ari, ed, vi, park.id, lunch["id"], stroll.id


def say(client, text, **more):
    r = client.post("/trip/family/message", data={"text": text}, headers={"X-Fragment": "1"}) if not more else client.post("/trip/talk/message", data={"text": text, **more}, headers={"X-Fragment": "1"})
    assert r.status_code == 200, r.text


def test_keys_name_the_whole_trip_a_plan_and_a_part():
    assert fc.key_of() == "trip" and fc.key_of("a3") == "a3" and fc.key_of("a3", "p1") == "a3:p1"
    assert fc.split("trip") == ("", "") and fc.split("a3") == ("a3", "") and fc.split("a3:p1") == ("a3", "p1")
    assert fc.split("../x") == ("", "") and fc.split("a3:p/1") == ("", "") and fc.split(None) == ("", "")


def test_the_whole_trip_comes_first_then_each_chat_with_its_newest_line(chats):
    ari, ed, _, park, lunch, stroll = chats
    say(ed, "Are we bringing the scooter?")
    say(ed, "Eggslut line is short", act=park, part=lunch)
    say(ed, "Churros after", act=stroll)
    rows = fc.threads(ari)
    assert [r["key"] for r in rows] == ["trip", stroll, f"{park}:{lunch}"]            # newest chat first after the whole trip
    assert rows[0]["title"] == "Whole trip" and rows[0]["last"] == "Are we bringing the scooter?" and rows[0]["who"] == "Ed"
    assert rows[1]["title"] == "Venice Canals stroll" and rows[1]["last"] == "Churros after"
    assert rows[2]["title"].startswith("Lunch") and rows[2]["n"] == 1


def test_a_chat_nobody_spoke_in_is_left_out_unless_it_is_the_open_one(chats):
    ari, _, _, park, _, stroll = chats
    assert [r["key"] for r in fc.threads(ari)] == ["trip"] and fc.threads(ari)[0]["last"] == ""         # the whole trip is always there
    ft.post_message(ari, "hello")
    assert [r["key"] for r in fc.threads(ari)] == ["trip"] and fc.threads(ari)[0]["last"] == "hello"
    assert [r["key"] for r in fc.threads(ari, stroll)] == ["trip", stroll]
    assert [r["key"] for r in fc.threads(ari, "a999")] == ["trip"]                        # a plan that is not there is not a chat


def test_unread_counts_others_messages_per_chat_and_not_my_own(chats):
    ari, ed, vi, park, lunch, stroll = chats
    say(ed, "one"), say(vi, "two"), say(ed, "three", act=stroll), say(ed, "four", act=park)
    ft.post_message(ari, "mine")
    plantalk.post_message(ari, stroll, "", "mine too")
    by = {r["key"]: r["unread"] for r in fc.threads(ari)}
    assert by == {"trip": 2, stroll: 1, park: 1} and fc.unread_total(ari) == 4


def test_a_plan_change_card_is_not_unread(chats):
    ari, ed, *_ = chats
    ed.post("/trip/plans", data={"day": "1", "start": "10:00", "title": "Pier walk", "kind": "fun"})
    assert fc.unread_total(ari) == 0


def test_a_read_mark_clears_that_chat_and_never_moves_back(chats):
    ari, ed, _, park, _, stroll = chats
    say(ed, "one"), say(ed, "two", act=stroll)
    newest = fc.newest(ari)
    fc.mark_read(ari, "trip", newest)
    assert {r["key"]: r["unread"] for r in fc.threads(ari)} == {"trip": 0, stroll: 1}
    say(ed, "three")
    fc.mark_read(ari, "trip", 1)                                                          # an old number does not un-read anything
    assert {r["key"]: r["unread"] for r in fc.threads(ari)}["trip"] == 1
    fc.mark_read(ari, stroll, fc.newest(ari))
    assert fc.unread_total(ari) == 1


def test_the_everything_mark_clears_every_chat_and_bad_keys_are_ignored(chats):
    ari, ed, _, park, _, stroll = chats
    say(ed, "one"), say(ed, "two", act=stroll)
    fc.mark_read(ari, "../x", 99), fc.mark_read(ari, "trip", "nope"), fc.mark_read(ari, "trip", -1)
    assert fc.unread_total(ari) == 2
    fc.mark_read(ari, "*", fc.newest(ari))
    assert fc.unread_total(ari) == 0


def test_the_whole_trip_scope_leaves_out_plan_chats(chats):
    ari, ed, _, _, _, stroll = chats
    say(ed, "everyone"), say(ed, "on the stroll", act=stroll)
    said = lambda **kw: [i["text"] for i in ft.items(ari, **kw) if i["kind"] == "message"]  # noqa: E731
    assert said() == ["everyone", "on the stroll"]            # the phone's Family tab keeps showing all of it
    assert said(scope="trip") == ["everyone"]
    assert any(i["kind"] == "change" for i in ft.items(ari, scope="trip"))                 # plan-change cards belong to the whole trip
