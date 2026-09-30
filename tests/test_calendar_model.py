"""The trip calendar model (F-019): booked blocks, activities, clashes, notes. Pure functions over a session dict."""

from datetime import date

import pytest

from gitaway import catalog, session as ses, tripcal as cal


def booked_session(flight="f1", stay="h1", car="c1", traveler="ari"):
    s = {}
    ses.sign_in(s, traveler)
    ses.book(s, catalog.quote(flight, stay, car))
    return s


def test_flights_have_out_and_back_times_that_match_their_headline():
    for o in catalog.offers("flight"):
        start = o.headline.split(" → ")[0]
        h, m = (int(x) for x in start.split(":"))
        assert o.depart_min % 60 == m and o.depart_min // 60 in (h, h + 12)
        assert 0 < o.arrive_min - o.depart_min < 4 * 60
        assert o.back_depart_min > 12 * 60 - 60 and o.back_arrive_min > o.back_depart_min
    assert catalog.offer("f1").back_depart_min == 14 * 60 + 10  # "back Tue 2:10 PM"


def test_booked_blocks_follow_the_picked_flight_and_stay():
    b = ses.booking(booked_session("f1", "h1"))
    blocks = {x.id: x for x in cal.booked_blocks(b, cal.trip())}
    out, back = blocks["b-out"], blocks["b-back"]
    assert (out.day, out.start, out.end) == (0, 8 * 60 + 5, 9 * 60 + 32)
    assert out.title == "Skylark Air 214 · SFO → LAX"
    assert (back.day, back.start, back.end) == (4, 14 * 60 + 10, 15 * 60 + 37)
    assert back.title == "Skylark Air 214 · LAX → SFO"
    assert (blocks["b-in"].day, blocks["b-in"].start) == (0, 15 * 60) and "The Tidewater" in blocks["b-in"].title
    assert (blocks["b-out2"].day, blocks["b-out2"].start) == (4, 11 * 60) and "Check out" in blocks["b-out2"].title
    assert all(x.locked and x.kind == "booked" for x in blocks.values())


def test_a_different_flight_moves_the_booked_blocks():
    b = ses.booking(booked_session("f5", "h3"))
    blocks = {x.id: x for x in cal.booked_blocks(b, cal.trip())}
    assert blocks["b-out"].start == 10 * 60 + 10 and "SFO → BUR" in blocks["b-out"].title
    assert "BUR → SFO" in blocks["b-back"].title and "Hotel Marigold" in blocks["b-in"].title


def test_the_grid_starts_at_seven_or_earlier_when_a_flight_leaves_before_seven():
    assert cal.grid_start(cal.booked_blocks(ses.booking(booked_session("f1")), cal.trip())) == 7 * 60
    assert cal.grid_start(cal.booked_blocks(ses.booking(booked_session("f2")), cal.trip())) == 6 * 60


def test_month_crossing_ranges_read_correctly():
    assert cal.range_label(date(2026, 10, 16), date(2026, 10, 20)) == "Oct 16 – 20"
    assert cal.range_label(date(2026, 10, 16), date(2026, 11, 4)) == "Oct 16 – Nov 4"
    assert cal.range_label(date(2026, 12, 30), date(2027, 1, 2)) == "Dec 30 – Jan 2"
    t = cal.trip("long")
    assert len(cal.days(t)) == 20 and t.return_ == date(2026, 11, 4)
    assert len(cal.days(cal.trip())) == 5


def test_add_activity_keeps_a_stable_id_and_a_refresh_does_not_duplicate():
    s = booked_session()
    a = cal.add_activity(s, day=1, start="10:00", end="11:30", title="Venice Canals stroll", kind="outdoors", id="a1")
    again = cal.add_activity(s, day=1, start="10:00", end="11:30", title="Venice Canals stroll", kind="outdoors", id="a1")
    assert a.id == again.id == "a1"
    assert [x.id for x in cal.activities(s)] == ["a1"]
    assert (a.day, a.start, a.end, a.kind) == (1, 600, 690, "outdoors")
    assert cal.next_id(s) == "2"  # the next free number, used by the forms


def test_activities_are_kept_per_traveler_and_per_trip():
    s = booked_session()
    cal.add_activity(s, day=1, start="10:00", end="11:00", title="A", kind="fun")
    assert cal.activities(s, demo="long") != cal.activities(s)
    assert [x.title for x in cal.activities(s)] == ["A"]
    ses.sign_in(s, "sam")
    ses.book(s, catalog.quote("f1", "h1", "c1"))
    assert cal.activities(s) == []


def test_times_snap_to_fifteen_minutes():
    s = booked_session()
    a = cal.add_activity(s, day=1, start="10:08", end="11:22", title="Snap", kind="fun")
    assert (a.start, a.end) == (10 * 60 + 15, 11 * 60 + 15)


@pytest.mark.parametrize("kw,words", [
    (dict(title="  ", start="10:00", end="11:00"), "title"),
    (dict(title="x", start="11:00", end="10:00"), "after"),
    (dict(title="x", start="10:00", end="10:15"), "30 minutes"),
    (dict(title="x", start="05:00", end="07:00"), "between"),
    (dict(title="x", start="21:00", end="23:00"), "between"),
    (dict(title="x", start="nope", end="10:00"), "time"),
    (dict(title="x" * 41, start="10:00", end="11:00"), "40"),
    (dict(title="x", start="10:00", end="11:00", kind="bogus"), "kind"),
    (dict(title="x", start="10:00", end="11:00", day=9), "day"),
])
def test_bad_activities_are_refused_with_a_reason(kw, words):
    s = booked_session()
    kw = {"day": 1, "kind": "fun", **kw}
    with pytest.raises(cal.CalendarError) as e:
        cal.add_activity(s, **kw)
    assert words in str(e.value)
    assert cal.activities(s) == []


def test_an_activity_may_not_overlap_a_booked_item_and_the_error_names_it():
    s = booked_session()  # day 0: flight 8:05-9:32, check in 3-4:30 PM
    with pytest.raises(cal.CalendarError) as e:
        cal.add_activity(s, day=0, start="09:00", end="10:00", title="Clash", kind="fun")
    assert "overlaps Skylark Air 214 · SFO → LAX" in str(e.value) and "8:05 AM" in str(e.value)
    with pytest.raises(cal.CalendarError):
        cal.add_activity(s, day=0, start="14:30", end="15:30", title="Clash", kind="fun")
    with pytest.raises(cal.CalendarError):
        cal.add_activity(s, day=4, start="13:00", end="14:30", title="Clash", kind="fun")  # return flight 2:10 PM
    touching = cal.add_activity(s, day=0, start="09:45", end="10:45", title="Just after", kind="fun")
    assert touching.start == 9 * 60 + 45
    cal.add_activity(s, day=0, start="16:30", end="17:30", title="After check in", kind="fun")


def test_activities_may_overlap_each_other():
    s = booked_session()
    cal.add_activity(s, day=1, start="10:00", end="12:00", title="One", kind="fun")
    cal.add_activity(s, day=1, start="11:00", end="13:00", title="Two", kind="food")
    assert len(cal.activities(s)) == 2


def test_update_and_move_an_activity():
    s = booked_session()
    a = cal.add_activity(s, day=1, start="10:00", end="11:00", title="Old", kind="fun")
    cal.update_activity(s, a.id, title="New", kind="food")
    moved = cal.update_activity(s, a.id, day=2, start="13:00", end="14:15")
    assert (moved.title, moved.kind, moved.day, moved.start, moved.end) == ("New", "food", 2, 780, 855)
    assert cal.get_activity(s, a.id) == moved
    with pytest.raises(cal.CalendarError):
        cal.update_activity(s, a.id, day=0, start="09:00", end="10:00")  # onto the flight
    assert cal.get_activity(s, a.id) == moved


def test_booked_items_and_unknown_ids_cannot_be_edited():
    s = booked_session()
    with pytest.raises(cal.CalendarError) as e:
        cal.update_activity(s, "b-out", start="10:00", end="11:00")
    assert "locked" in str(e.value)
    with pytest.raises(cal.CalendarError):
        cal.update_activity(s, "a99", title="x")


def test_delete_then_undo_restores_the_activity_and_its_notes():
    s = booked_session()
    a = cal.add_activity(s, day=1, start="10:00", end="11:00", title="Pier", kind="fun", id="a1")
    cal.add_note(s, "Go early", act=a.id, id="n2")
    assert cal.delete_activity(s, a.id).id == "a1"
    assert cal.activities(s) == [] and cal.notes(s) == []
    assert cal.delete_activity(s, a.id) is None  # a refresh of the delete is harmless
    back = cal.undo_delete(s, "a1")
    assert back.title == "Pier" and [n.text for n in cal.notes(s)] == ["Go early"]
    assert cal.undo_delete(s, "a1") is None and len(cal.activities(s)) == 1


def test_notes_attach_to_an_activity_or_the_trip_and_are_idempotent():
    s = booked_session()
    a = cal.add_activity(s, day=1, start="10:00", end="11:00", title="Pier", kind="fun", id="a1")
    n1 = cal.add_note(s, "  Bring hats  ", id="n2")
    n2 = cal.add_note(s, "Wristbands are cheaper", act=a.id, id="n3")
    assert cal.add_note(s, "Bring hats", id="n2").id == "n2"
    assert [n.id for n in cal.notes(s)] == ["n2", "n3"]
    assert (n1.text, n1.act) == ("Bring hats", None) and n2.act == "a1"
    with pytest.raises(cal.CalendarError):
        cal.add_note(s, "   ")
    with pytest.raises(cal.CalendarError):
        cal.add_note(s, "x" * 141)
    with pytest.raises(cal.CalendarError):
        cal.add_note(s, "hi", act="a42")


def test_the_long_demo_comes_with_a_few_planned_items():
    s = booked_session()
    demo = cal.activities(s, demo="long")
    assert 4 <= len(demo) <= 10 and len({a.day for a in demo}) > 3
    assert max(a.day for a in demo) < 20
    added = cal.add_activity(s, day=3, start="10:00", end="11:00", title="Mine", kind="fun", demo="long")
    assert added.id not in {a.id for a in demo} and len(cal.activities(s, demo="long")) == len(demo) + 1


def test_the_calendar_refuses_more_when_the_cookie_budget_is_spent():
    s = booked_session()
    with pytest.raises(cal.CalendarError) as e:
        for i in range(200):
            cal.add_activity(s, day=1 + i % 3, start=f"{8 + i % 12:02d}:00", end=f"{8 + i % 12:02d}:30", title="x" * 40, kind="fun")
    assert "full" in str(e.value)
    assert len(str(s)) < 4000


def test_signed_out_or_unbooked_travelers_have_no_calendar():
    s = {}
    with pytest.raises(cal.CalendarError):
        cal.add_activity(s, day=1, start="10:00", end="11:00", title="x", kind="fun")
    ses.sign_in(s, "ari")
    with pytest.raises(cal.CalendarError) as e:
        cal.add_activity(s, day=1, start="10:00", end="11:00", title="x", kind="fun")
    assert "Book a trip first" in str(e.value)
    assert cal.activities(s) == []
