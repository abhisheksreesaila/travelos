"""F-091: talk on the block. Text on a plan (photos and voice notes retired in F-254) or on one part of a park day: the model (what is accepted, where it is kept, the counts), the
thread and the push, and the routes (roles, another family's file is not served, Range for iPhone audio). The park day is the captain's Universal + California
Adventure messages through the canned model answer (no network); the plain plan is the calendar's "Venice Canals stroll"."""

import re
from html import unescape

import pytest

from gitaway import canvas, familydb, familythread as ft, plantalk, session as ses, tripcal as cal
from tests.test_canvas import announced, azure  # noqa: F401 - fixtures
from tests.canvas_samples import added
from tests.test_members import addr, browser, invite
from tests.test_signin import person, sign_in, tid
from tests.test_thread import FakePush, subscribe


@pytest.fixture
def trip(client, azure):
    """Ari with the Universal + DCA trip: a park block (parts incl. Lunch) and, on another day, a plain plan."""
    from tests.test_calendar import add, book
    book(client)
    added(client)
    add(client)
    return client


@pytest.fixture
def ari():
    return person("ari")


def ids(ari):
    """(the park block's id, its Lunch part's id, the plain plan's id)."""
    plan = canvas.plan(ari)["blocks"]
    act = next(a for a in cal.activities(ari) if a.id in plan)
    lunch = next(p for p in plan[act.id]["parts"] if p["name"] == "Lunch")
    stroll = next(a for a in cal.activities(ari) if a.title == "Venice Canals stroll")
    return act.id, lunch["id"], stroll.id


# ---- the voice files -------------------------------------------------------------------------------------------------------

# ---- the model: where things belong ----------------------------------------------------------------------------------------

def test_a_plan_and_a_part_each_hold_their_own_messages(trip, ari):
    act, lunch, stroll = ids(ari)
    plantalk.post_message(ari, act, "", "  Lunch at   noon?  ")
    plantalk.post_message(ari, act, lunch, "Mario Kart after lunch")
    plantalk.post_message(ari, stroll, "", "See you at the canals")
    assert [i["text"] for i in plantalk.items(ari, act)] == ["Lunch at noon?"]
    assert [i["text"] for i in plantalk.items(ari, act, lunch)] == ["Mario Kart after lunch"]
    assert [i["text"] for i in plantalk.items(ari, stroll)] == ["See you at the canals"]
    its = [i for i in ft.items(ari) if i["kind"] != "change"]   # the family thread has all three, each with the plan and part it belongs to
    assert [(i["kind"], i["payload"]["act"], i["payload"]["part"]) for i in its] == [("message", act, ""), ("message", act, lunch), ("message", stroll, "")]
    assert its[0]["name"] == "Ari" and its[0]["author"] == tid("ari")


def test_the_chat_after_a_number_is_only_what_is_new(trip, ari):
    act, _, _ = ids(ari)
    plantalk.post_message(ari, act, "", "one")
    first = plantalk.items(ari, act)[-1]["n"]
    plantalk.post_message(ari, act, "", "two")
    assert [i["text"] for i in plantalk.items(ari, act, since=first)] == ["two"]


def test_labels_name_the_plan_and_the_part(trip, ari):
    act, lunch, stroll = ids(ari)
    lab = plantalk.labels(ari)
    assert lab[(stroll, "")] == "Venice Canals stroll" and lab[(act, "")] == "Universal studios itinerary" or lab[(act, "")]
    assert lab[(act, lunch)].startswith("Lunch · ")


@pytest.mark.parametrize("act,part,msg", [("a999", "", "plan is not here"), ("", "", "plan is not here"), ("<script>", "", "plan is not here")])
def test_a_plan_that_is_not_here_is_refused(trip, ari, act, part, msg):
    with pytest.raises(ft.ThreadError, match=msg):
        plantalk.post_message(ari, act, part, "hello")
    assert [i for i in ft.items(ari) if i["kind"] != "change"] == []


def test_a_part_that_is_not_in_that_plan_is_refused(trip, ari):
    act, lunch, stroll = ids(ari)
    with pytest.raises(ft.ThreadError, match="part of the plan is not here"):
        plantalk.post_message(ari, stroll, lunch, "hello")
    with pytest.raises(ft.ThreadError, match="part of the plan is not here"):
        plantalk.post_message(ari, act, "p999", "hello")


def test_empty_and_huge_text_is_refused_and_leaves_nothing(trip, ari):
    act, _, _ = ids(ari)
    for bad in ("", "   ", "x" * (ft.MAX_MESSAGE + 1)):
        with pytest.raises(ft.ThreadError):
            plantalk.post_message(ari, act, "", bad)
    assert [i for i in ft.items(ari) if i["kind"] != "change"] == []


# ---- the push --------------------------------------------------------------------------------------------------------------

@pytest.fixture
def pushes(client, monkeypatch):
    fake = FakePush()
    monkeypatch.setattr(ft, "SENDER", fake)
    return fake


def test_the_family_gets_a_push_with_names_and_the_plan_only(trip, pushes):
    from tests.test_thread import KEYS
    ari = person("ari")
    act, lunch, _ = ids(ari)
    ed_mail = addr("ed")
    invite(trip, ed_mail, "editor")
    ed = browser(trip)
    sign_in(ed, ed_mail)
    subscribe(ed, "https://push.example.com/send/ed")
    plantalk.post_message(ari, act, lunch, "Meet at noon")
    ft.drain()
    [(endpoint, payload)] = pushes.sent
    assert endpoint.endswith("/ed") and payload["title"] == "Ari" and payload["body"].startswith("on Lunch · ") and payload["body"].endswith("Meet at noon")
    assert "$" not in payload["body"]
    assert KEYS  # (the keys the family's phones used)
