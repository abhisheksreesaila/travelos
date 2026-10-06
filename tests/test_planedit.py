"""F-097 / F-098: changing a plan by touch, at the model (gitaway.planedit): move and resize with a 5-minute grain and a 15-minute minimum, rename, delete and the
Undo of each, all through the calendar's own rules (gitaway.tripcal), and one coalesced card for the family however many times a plan is nudged."""

import pytest

from gitaway import familydb, familythread, planedit, session as ses, tripcal as cal
from tests.test_calendar_model import booked_session


@pytest.fixture
def announced(monkeypatch):
    seen = []
    monkeypatch.setattr(familythread, "announce", lambda session, trip_id, title, body, exclude="": seen.append((title, body, exclude)))
    return seen


@pytest.fixture
def ari():
    return booked_session()


def cards(session):
    with ses.family(session) as fam:
        return familydb.rows(fam.db, "SELECT * FROM thread WHERE kind = 'change' ORDER BY rowid", )


def lunch(session, start=12 * 60, end=13 * 60):
    return cal.add_activity(session, day=1, start=start, end=end, title="Lunch at the pier", kind="food")


def test_a_move_keeps_the_length_and_saves_through_the_calendar(ari, announced):
    a = lunch(ari)
    got = planedit.change(ari, a.id, start=12 * 60 + 30, end=13 * 60 + 30)
    assert (got["act"].start, got["act"].end) == (12 * 60 + 30, 13 * 60 + 30)
    assert (cal.get_activity(ari, a.id).start, cal.get_activity(ari, a.id).end) == (12 * 60 + 30, 13 * 60 + 30)
    assert got["undo"] == {"act": a.id, "day": 1, "start": 12 * 60, "end": 13 * 60, "title": "Lunch at the pier", "after": {"day": 1, "start": 750, "end": 810, "title": "Lunch at the pier"}}


def test_a_resize_can_use_five_minutes_and_fifteen_as_the_shortest(ari):
    a = lunch(ari)
    got = planedit.change(ari, a.id, end=12 * 60 + 15)
    assert (got["act"].start, got["act"].end) == (12 * 60, 12 * 60 + 15)
    got = planedit.change(ari, a.id, end=12 * 60 + 40)
    assert got["act"].end == 12 * 60 + 40
    with pytest.raises(cal.CalendarError) as e:
        planedit.change(ari, a.id, end=12 * 60 + 10)
    assert "15 minutes" in str(e.value)


def test_the_desktop_form_keeps_its_fifteen_minute_snap_and_thirty_minute_minimum(ari):
    a = lunch(ari)
    assert cal.update_activity(ari, a.id, end=12 * 60 + 40).end == 12 * 60 + 45
    with pytest.raises(cal.CalendarError):
        cal.update_activity(ari, a.id, end=12 * 60 + 15)


def test_times_nobody_changed_are_never_resnapped_or_held_to_the_forms_minimum(ari, announced):
    """Review: a plan made on the phone (12:05, or 15 minutes long) must still be renamable and savable from the desktop form and by Ask."""
    a = lunch(ari)
    planedit.change(ari, a.id, start=12 * 60 + 5, end=12 * 60 + 20)               # 12:05, 15 minutes
    base = len(cards(ari))
    got = cal.update_activity(ari, a.id, title="Lunch 2")                          # a title-only edit, as the desktop and Ask make it
    assert (got.start, got.end, got.title) == (12 * 60 + 5, 12 * 60 + 20, "Lunch 2")
    assert [c["text"] for c in cards(ari)[base:]] == [f"{cards(ari)[-1]['text']}"] and "renamed" in cards(ari)[-1]["text"] and "moved" not in cards(ari)[-1]["text"]
    got = cal.update_activity(ari, a.id, day=1, start="12:05", end="12:20", title="Lunch 3", kind="food")      # the desktop form re-sends every field
    assert (got.start, got.end) == (12 * 60 + 5, 12 * 60 + 20)
    with pytest.raises(cal.CalendarError):                                         # but a time that did change is held to the form's rules
        cal.update_activity(ari, a.id, end="12:25")


def test_undo_refuses_when_someone_changed_the_plan_since(ari):
    a = lunch(ari)
    got = planedit.change(ari, a.id, start=12 * 60 + 30, end=13 * 60 + 30)
    assert got["undo"]["after"] == {"day": 1, "start": 12 * 60 + 30, "end": 13 * 60 + 30, "title": "Lunch at the pier"}
    planedit.change(ari, a.id, title="Dinner instead")                             # another member's later change
    with pytest.raises(cal.CalendarError) as e:
        planedit.restore(ari, got["undo"])
    assert "Someone changed it since" in str(e.value) and cal.get_activity(ari, a.id).title == "Dinner instead" and cal.get_activity(ari, a.id).start == 12 * 60 + 30


def test_the_calendars_rules_refuse_what_they_always_refused(ari):
    a = lunch(ari)
    for kw, words in (({"start": 13 * 60, "end": 12 * 60}, "after the start"), ({"start": 5 * 60, "end": 6 * 60}, "Plan between"), ({"end": 23 * 60}, "Plan between"),
                      ({"title": ""}, "title"), ({"title": "x" * 41}, "40 characters")):
        with pytest.raises(cal.CalendarError) as e:
            planedit.change(ari, a.id, **kw)
        assert words in str(e.value)
    assert (cal.get_activity(ari, a.id).start, cal.get_activity(ari, a.id).title) == (12 * 60, "Lunch at the pier")


def test_overlaps_are_allowed_families_split_up(ari):
    a = lunch(ari)
    b = cal.add_activity(ari, day=1, start=9 * 60, end=10 * 60, title="Pier walk", kind="outdoors")
    got = planedit.change(ari, b.id, start=12 * 60, end=13 * 60)
    assert got["act"].start == a.start


def test_a_booked_block_and_a_missing_plan_are_refused(ari):
    with pytest.raises(cal.CalendarError):
        planedit.change(ari, "b-out", start=9 * 60, end=10 * 60)
    with pytest.raises(cal.CalendarError):
        planedit.change(ari, "a99", start=9 * 60, end=10 * 60)


def test_rename_trims_and_keeps_the_time(ari):
    a = lunch(ari)
    got = planedit.change(ari, a.id, title="  Tacos   by the pier ")
    assert got["act"].title == "Tacos by the pier" and got["act"].start == a.start
    assert got["undo"]["title"] == "Lunch at the pier"


def test_undo_puts_back_the_exact_time_and_name_through_the_same_rules(ari):
    a = lunch(ari)
    got = planedit.change(ari, a.id, start=14 * 60, end=15 * 60, title="Later lunch")
    back = planedit.restore(ari, got["undo"])
    assert (back.start, back.end, back.title) == (12 * 60, 13 * 60, "Lunch at the pier")
    with pytest.raises(cal.CalendarError):
        planedit.restore(ari, {"act": a.id, "day": 1, "start": 30, "end": 20, "title": "x"})
    with pytest.raises(cal.CalendarError):
        planedit.restore(ari, None)
    with pytest.raises(cal.CalendarError):
        planedit.restore(ari, {"act": "b-out", "day": 1, "start": 600, "end": 660, "title": "x"})


def test_one_nudge_tells_the_family_once_and_more_nudges_change_that_card_in_place(ari, announced):
    a = lunch(ari)
    base = len(cards(ari))
    planedit.change(ari, a.id, start=12 * 60 + 30, end=13 * 60 + 30)
    planedit.change(ari, a.id, start=13 * 60, end=14 * 60)
    planedit.change(ari, a.id, end=14 * 60 + 30)
    now = cards(ari)[base:]
    assert len(now) == 1 and "Lunch at the pier" in now[0]["text"] and "1:00 PM" in now[0]["text"]
    assert [t for t, _, _ in announced].count("Plan changed") == 2     # the add, and this one move: the later nudges are no second push


def test_undoing_back_to_where_it_began_takes_the_card_away(ari, announced):
    a = lunch(ari)
    base = len(cards(ari))
    got = planedit.change(ari, a.id, start=12 * 60 + 30, end=13 * 60 + 30)
    assert len(cards(ari)) == base + 1
    planedit.restore(ari, got["undo"])
    assert len(cards(ari)) == base


def test_a_rename_is_its_own_card_and_someone_elses_card_is_left_alone(ari, announced):
    a = lunch(ari)
    base = len(cards(ari))
    planedit.change(ari, a.id, title="Tacos")
    assert "renamed" in cards(ari)[-1]["text"] and len(cards(ari)) == base + 1


def test_delete_asks_nothing_of_the_model_and_undelete_puts_it_back(ari, announced):
    a = lunch(ari)
    gone = planedit.delete(ari, a.id)
    assert gone["title"] == "Lunch at the pier" and cal.get_activity(ari, a.id) is None
    back = planedit.undelete(ari, a.id)
    assert back.id == a.id and cal.get_activity(ari, a.id).start == 12 * 60
    with pytest.raises(cal.CalendarError):
        planedit.delete(ari, "a99")
