"""Talk to plan (F-024): the scripted sentence, its mapping onto a trip's real days, and placement. Pure functions."""

from datetime import date

import pytest

from gitaway import tripcal as cal, voice

SAMPLE = [date(2026, 10, 16 + i) for i in range(5)]          # Fri 16 .. Tue 20
TWO_NIGHTS = [date(2026, 10, 21 + i) for i in range(3)]      # Wed 21 .. Fri 23: no Sunday, no Monday
ONE_DAY = [date(2026, 10, 21)]


def by_key(plans):
    return {p.key: p for p in plans}


def client_session(client):
    """A plain session dict equal to the client's cookie."""
    from tests.test_signin import session_data
    return session_data(client)


def test_the_sentence_is_scripted_and_names_every_plan():
    s = voice.SENTENCE.lower()
    for word in ("tacos", "observatory", "pool", "beach"):
        assert word in s
    assert voice.SENTENCE.split()[0] == "Tacos"


def test_the_question_offers_the_first_two_evenings_of_the_trip():
    q = voice.question(SAMPLE)
    assert q.text == "Tacos on which night?"
    assert [(o.day, o.label) for o in q.options] == [(0, "Fri 16, 6:30 PM"), (1, "Sat 17, 6:30 PM")]
    assert [o.day for o in voice.question(ONE_DAY).options] == [0]       # a one-day trip has one evening to offer
    assert voice.question(SAMPLE).option(7) is None and voice.question(SAMPLE).option(1).day == 1


def test_sunday_and_monday_land_on_the_trips_own_sunday_and_monday():
    plans = by_key(voice.plans(SAMPLE, "The Tidewater", night=0))
    assert plans["v0"].day == 0 and (plans["v0"].start, plans["v0"].end) == (18 * 60 + 30, 20 * 60)
    assert plans["v1"].day == 2 and plans["v1"].title == "Griffith Observatory at sunset"   # Sun 18
    assert plans["v2"].day == 3 and plans["v2"].title == "Pool time at The Tidewater"       # Mon 19
    assert plans["v3"].day == 4                                                              # the last day (Tue 20)
    assert len(plans) == 4


def test_the_night_answer_moves_the_tacos():
    assert by_key(voice.plans(SAMPLE, "X", night=1))["v0"].day == 1
    assert "v0" not in by_key(voice.plans(SAMPLE, "X", night=None))        # unanswered: the tacos wait for the question
    assert "v0" not in by_key(voice.plans(SAMPLE, "X", night=9))           # not one of the offered nights


def test_a_trip_without_a_sunday_or_monday_uses_a_full_middle_day_and_says_so():
    plans = by_key(voice.plans(TWO_NIGHTS, "X", night=0))                 # Wed 21 .. Fri 23: the only middle day is Thu 22
    assert plans["v1"].day == 1 and plans["v2"].day == 1 and plans["v3"].day == 2
    assert voice.fallback_notes(TWO_NIGHTS) == {"v1": "No Sunday on this trip, so Thu 22", "v2": "No Monday on this trip, so Thu 22"}
    assert voice.fallback_notes(SAMPLE) == {}
    four = [date(2026, 10, 21 + i) for i in range(4)]                       # Wed .. Sat: Sunday takes the last middle day, Monday the first
    p4 = by_key(voice.plans(four, "X", night=0))
    assert (p4["v1"].day, p4["v2"].day) == (2, 1)


def test_a_two_day_trip_has_no_middle_day_so_it_uses_the_days_it_has():
    plans = by_key(voice.plans(TWO_NIGHTS[:2], "X", night=0))
    assert all(0 <= p.day < 2 for p in plans.values())


def test_the_tacos_night_never_offers_the_observatory_evening():
    assert [o.day for o in voice.question(TWO_NIGHTS).options] == [0]       # Thu is the observatory's day
    assert [o.day for o in voice.question(SAMPLE).options] == [0, 1]
    assert [o.day for o in voice.question(ONE_DAY).options] == [0]          # nothing else to offer: the clash is shown instead


def test_the_beach_walk_only_talks_about_a_flight_home_when_there_is_one():
    assert by_key(voice.plans(SAMPLE, "X", night=0))["v3"].title == "Beach walk before the flight home"
    assert by_key(voice.plans(SAMPLE, "X", night=0, home=False))["v3"].title == "Beach walk"


def test_a_one_day_trip_never_points_past_its_last_day():
    plans = voice.plans(ONE_DAY, "X", night=0)
    assert {p.day for p in plans} == {0}


def test_every_title_fits_a_calendar_title():
    assert all(len(p.title) <= cal.MAX_TITLE for p in voice.plans(SAMPLE, "A very long hotel name that goes on and on forever", night=0))


def test_the_plans_sit_in_the_gaps_on_the_sample_trip(client):
    from tests.test_calendar import book
    book(client)
    placed = voice.preview(client_session(client), night=0)
    assert [x.state for x in placed] == ["free"] * 4
    assert [x.plan.day for x in placed] == [0, 2, 3, 4]


def test_on_a_two_night_trip_plans_over_the_flights_are_kept_and_nothing_crashes(client):
    from tests.test_calendar import book
    book(client, d="2026-10-21", r="2026-10-22", a="2")
    s = client_session(client)
    placed = voice.preview(s, night=0)
    assert len(placed) == 4
    assert all(x.state in ("free", "clash") for x in placed)
    assert all(x.clash for x in placed if x.state == "clash")             # a hard one (past the trip) says why
    assert all(x.checked for x in placed if not x.hard)                   # overlapping a flight is never a reason to skip


def test_the_note_lists_what_was_planned_and_fits_a_note():
    plans = voice.plans(SAMPLE, "The Tidewater", night=0)
    text = voice.note_text(plans, SAMPLE)
    assert text.startswith("Planned by voice: ") and "Tacos" in text and len(text) <= cal.MAX_NOTE
    assert len(voice.note_text(plans * 6, SAMPLE)) <= cal.MAX_NOTE


@pytest.mark.parametrize("night", [None, 0, 1])
def test_plan_keys_are_stable(night):
    keys = [p.key for p in voice.plans(SAMPLE, "X", night=night)]
    assert keys == sorted(set(keys))


def test_the_sentence_drops_the_pool_clause_when_there_is_no_stay():
    assert "pool" in voice.sentence(True).lower() and voice.sentence(True) == voice.SENTENCE
    no = voice.sentence(False)
    assert "pool" not in no.lower() and no.startswith("Tacos for dinner") and no.endswith("a beach walk on our last day.") and ", and a beach walk" in no


def test_with_no_stay_there_is_no_pool_plan():
    keys = [p.key for p in voice.plans(SAMPLE, None, night=0)]
    assert keys == ["v0", "v1", "v3"]
