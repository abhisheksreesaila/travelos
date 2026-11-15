"""F-143: the trip's chats and what is unread in them (gitaway/familychats.py): the whole trip first, then each plan's and part's; unread counts per person; read marks that never
move back; and the panel's routes (the list, the pane, a thread opened directly on a laptop, the live poll with `read=1`)."""
import re

import pytest

from gitaway import canvas, familychats as fc, familythread as ft, plantalk, tripcal as cal
from tests.test_canvas import azure  # noqa: F401 - fixtures
from tests.canvas_samples import added
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


def test_a_chat_nobody_spoke_in_is_left_out_unless_it_is_the_open_one(chats):
    ari, _, _, park, _, stroll = chats
    assert [r["key"] for r in fc.threads(ari)] == ["trip"] and fc.threads(ari)[0]["last"] == ""         # the whole trip is always there
    ft.post_message(ari, "hello")
    assert [r["key"] for r in fc.threads(ari)] == ["trip"] and fc.threads(ari)[0]["last"] == "hello"
    assert [r["key"] for r in fc.threads(ari, stroll)] == ["trip", stroll]
    assert [r["key"] for r in fc.threads(ari, "a999")] == ["trip"]                        # a plan that is not there is not a chat


def test_a_plan_change_card_is_not_unread(chats):
    ari, ed, *_ = chats
    ed.post("/trip/plans", data={"day": "1", "start": "10:00", "title": "Pier walk", "kind": "fun"})
    assert fc.unread_total(ari) == 0


# ---- two trips: a read mark belongs to its trip ------------------------------------------------------------------------------

def _someone_says(trip_id, text, act=""):
    """A message by another member written straight into a trip of Ari's family (the numbers of the rows run on across trips; plan ids repeat in each)."""
    from gitaway import familydb, session as ses
    with ses.family(person("ari")) as fam:
        with familydb.transaction(fam.db):
            ft._insert(fam.db, trip_id, "message", "someone-else", "Sam", text, {"act": act, "part": ""} if act else None)


def _open(trip_id):
    from gitaway import session as ses
    s = person("ari")
    ses.switch_trip(s, trip_id)
    return s

