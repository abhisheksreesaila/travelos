"""Idempotency and id safety for the trip calendar model."""

from gitaway import tripcal as cal
from tests.test_calendar_model import booked_session


def test_a_reposted_add_of_a_deleted_activity_does_not_revive_it():
    s = booked_session()
    cal.add_activity(s, day=1, start="10:00", end="11:00", title="Pier", kind="fun", id="a1")
    cal.delete_activity(s, "a1")
    assert cal.add_activity(s, day=1, start="10:00", end="11:00", title="Pier", kind="fun", id="a1") is None
    assert cal.activities(s) == []
    assert cal.undo_delete(s, "a1").title == "Pier"  # Undo still works


def test_an_id_collision_between_tabs_gets_a_fresh_id_instead_of_being_dropped():
    s = booked_session()
    a = cal.add_activity(s, day=1, start="10:00", end="11:00", title="Tab one", kind="fun", id="a1")
    b = cal.add_activity(s, day=2, start="13:00", end="14:00", title="Tab two", kind="food", id="a1")
    assert a.id == "a1" and b.id != "a1" and b.title == "Tab two"
    assert {x.title for x in cal.activities(s)} == {"Tab one", "Tab two"}
    n1 = cal.add_note(s, "First", id="n9")
    n2 = cal.add_note(s, "Second", id="n9")
    assert n1.id == "n9" and n2.id != "n9" and len(cal.notes(s)) == 2
    assert cal.add_note(s, "First", id="n9").id == "n9"  # the same note re-posted is still a no-op
