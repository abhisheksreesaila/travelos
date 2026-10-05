"""F-091: talk on the block. Text, photos and voice notes on a plan or on one part of a park day: the model (what is accepted, where it is kept, the counts), the
thread and the push, and the routes (roles, another family's file is not served, Range for iPhone audio). The park day is the captain's Universal + California
Adventure messages through the canned model answer (no network); the plain plan is the calendar's "Venice Canals stroll"."""

import re
from html import unescape

import pytest

from gitaway import canvas, familydb, familythread as ft, plantalk, session as ses, tripcal as cal, voicenotes
from tests.photo_files import image
from tests.test_canvas import announced, azure  # noqa: F401 - fixtures
from tests.test_canvas_pages import added
from tests.test_members import addr, browser, invite
from tests.test_signin import person, sign_in, tid
from tests.test_thread import FakePush, subscribe
from tests.voice_files import voice


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

def test_the_kind_comes_from_the_first_bytes_not_the_name_or_claimed_type():
    assert [voicenotes.kind_of(voice(k)) for k in ("webm", "mp4", "ogg")] == ["webm", "mp4", "ogg"]
    for bad in (b"RIFF....WAVEfmt ", b"ID3\x03\x00", b"%PDF-1.7", b"<svg/>", b"MZ\x90\x00", image("jpeg"), image("heic"), b"\x00\x00"):
        assert voicenotes.kind_of(bad) is None


def test_empty_big_wrong_type_and_missing_length_are_refused_with_plain_messages():
    with pytest.raises(voicenotes.VoiceError, match="empty"):
        voicenotes.check(b"", 5)
    with pytest.raises(voicenotes.VoiceError, match="too large") as big:
        voicenotes.check(voice("webm", voicenotes.MAX_BYTES + 1), 5)
    assert big.value.status == 413
    with pytest.raises(voicenotes.VoiceError, match="not a voice note") as wrong:
        voicenotes.check(image("jpeg"), 5)
    assert wrong.value.status == 415
    for secs in ("", None, "abc", 0, -3, "nan"):
        with pytest.raises(voicenotes.VoiceError, match="no length"):
            voicenotes.check(voice(), secs)
    with pytest.raises(voicenotes.VoiceError, match="up to 3 minutes"):
        voicenotes.check(voice(), 200)


def test_three_minutes_is_allowed_and_the_length_is_whole_seconds():
    assert voicenotes.check(voice(), 180)[1] == 180
    assert voicenotes.check(voice(), 180.4)[1] == 180
    assert voicenotes.check(voice("mp4"), 0.4)[1] == 1
    assert voicenotes.check(voice("ogg"), "42.6")[1] == 43


def test_a_voice_note_is_stored_under_the_volume_in_the_familys_trip_folder(trip, ari):
    act, lunch, _ = ids(ari)
    plantalk.post_voice(ari, act, lunch, voice("mp4"), 12)
    [it] = plantalk.items(ari, act, lunch)
    path = voicenotes.path_of(it["payload"]["file"])
    assert path and path.is_file() and voicenotes.root().resolve() in path.parents and path.suffix == ".m4a"
    assert it["payload"]["mime"] == "audio/mp4" and it["payload"]["secs"] == 12
    assert ".." not in it["payload"]["file"] and voicenotes.path_of("../../etc/passwd") is None and voicenotes.path_of("") is None


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


def test_counts_per_plan_and_part_with_voice_and_photo_flags(trip, ari):
    act, lunch, stroll = ids(ari)
    assert plantalk.counts(ari) == {}
    plantalk.post_message(ari, act, "", "hi")
    plantalk.post_voice(ari, act, lunch, voice(), 5)
    plantalk.post_message(ari, act, lunch, "yes")
    plantalk.post_photo(ari, stroll, "", image("jpeg"), "canal")
    ft.post_message(ari, "a plain thread message")          # not on a plan: not counted
    assert plantalk.counts(ari) == {(act, ""): {"n": 1, "voice": False, "photo": False}, (act, lunch): {"n": 2, "voice": True, "photo": False},
                                    (stroll, ""): {"n": 1, "voice": False, "photo": True}}


def test_a_photo_on_a_plan_is_pinned_to_it_and_shows_in_the_thread(trip, ari):
    from gitaway import photos
    _, _, stroll = ids(ari)
    p = plantalk.post_photo(ari, stroll, "", image("jpeg"), "  by the water ")
    assert p["plan_id"] == stroll and p["plan_title"] == "Venice Canals stroll"
    [it] = [i for i in ft.items(ari) if i["kind"] == "photo"]
    assert it["payload"]["act"] == stroll and it["payload"]["part"] == "" and it["payload"]["photo"] == p["id"] and it["text"] == "by the water"
    assert [i["kind"] for i in plantalk.items(ari, stroll)] == ["photo"]
    assert photos.get(ari, p["id"])


def test_labels_name_the_plan_and_the_part(trip, ari):
    act, lunch, stroll = ids(ari)
    lab = plantalk.labels(ari)
    assert lab[(stroll, "")] == "Venice Canals stroll" and lab[(act, "")] == "Universal studios itinerary" or lab[(act, "")]
    assert lab[(act, lunch)].startswith("Lunch · ")


@pytest.mark.parametrize("act,part,msg", [("a999", "", "plan is not here"), ("", "", "plan is not here"), ("<script>", "", "plan is not here")])
def test_a_plan_that_is_not_here_is_refused(trip, ari, act, part, msg):
    with pytest.raises(ft.ThreadError, match=msg):
        plantalk.post_message(ari, act, part, "hello")
    with pytest.raises(ft.ThreadError, match=msg):
        plantalk.post_voice(ari, act, part, voice(), 3)
    assert [i for i in ft.items(ari) if i["kind"] != "change"] == []


def test_a_part_that_is_not_in_that_plan_is_refused(trip, ari):
    act, lunch, stroll = ids(ari)
    with pytest.raises(ft.ThreadError, match="part of the plan is not here"):
        plantalk.post_message(ari, stroll, lunch, "hello")
    with pytest.raises(ft.ThreadError, match="part of the plan is not here"):
        plantalk.post_message(ari, act, "p999", "hello")


def test_empty_and_huge_text_is_refused_and_a_refused_voice_note_leaves_no_file(trip, ari):
    act, _, _ = ids(ari)
    for bad in ("", "   ", "x" * (ft.MAX_MESSAGE + 1)):
        with pytest.raises(ft.ThreadError):
            plantalk.post_message(ari, act, "", bad)
    before = sorted(voicenotes.root().rglob("*")) if voicenotes.root().exists() else []
    for data, secs in ((b"", 4), (image("png"), 4), (voice("webm", voicenotes.MAX_BYTES + 5), 4), (voice(), 999)):
        with pytest.raises(voicenotes.VoiceError):
            plantalk.post_voice(ari, act, "", data, secs)
    assert (sorted(voicenotes.root().rglob("*")) if voicenotes.root().exists() else []) == before
    assert [i for i in ft.items(ari) if i["kind"] != "change"] == []


def test_a_bad_photo_on_a_plan_is_refused(trip, ari):
    from gitaway import photos
    act, _, _ = ids(ari)
    for data in (b"", b"%PDF-1.7 nope", image("jpeg")[:5]):
        with pytest.raises(photos.PhotoError):
            plantalk.post_photo(ari, act, "", data)
    assert [i for i in ft.items(ari) if i["kind"] != "change"] == []


def test_deleting_the_trip_removes_its_voice_notes(trip, ari):
    act, _, _ = ids(ari)
    plantalk.post_voice(ari, act, "", voice(), 3)
    assert list(voicenotes.root().rglob("*.webm"))
    with ses.family(ari) as fam:
        trip_id = fam.trip_id
    voicenotes.purge_trip(ari.get("tenant_id"), trip_id)
    assert not list(voicenotes.root().rglob("*.webm"))


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
    plantalk.post_voice(ari, act, lunch, voice(), 7)
    ft.drain()
    [(endpoint, payload)] = pushes.sent
    assert endpoint.endswith("/ed") and payload["title"] == "Ari" and payload["body"].startswith("on Lunch · ") and payload["body"].endswith(": voice note")
    assert "$" not in payload["body"]
    assert KEYS  # (the keys the family's phones used)
