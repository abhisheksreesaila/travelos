"""F-042: the importer reads docs/trip-template.md exactly as shipped, and says what is wrong in plain, line-specific words."""

from datetime import date, datetime
from pathlib import Path

import pytest

from gitaway import tripimport as ti

TEMPLATE = (Path(__file__).resolve().parent.parent / "docs" / "trip-template.md").read_text()


def yaml_of(text):
    return text.split("```yaml\n")[1].split("```")[0]


def fails(text):
    with pytest.raises(ti.ImportProblem) as e:
        ti.parse(text)
    return e.value.errors


def test_the_template_as_shipped_parses_whole_markdown_or_just_the_block():
    for text in (TEMPLATE, yaml_of(TEMPLATE)):
        plan = ti.parse(text).plan
        assert (plan.title, plan.destination, plan.start, plan.end, plan.booked_on) == ("LA with the kids", "Los Angeles", date(2026, 10, 16), date(2026, 10, 20), "Expedia")
        assert plan.itinerary == "7123456789012"
        assert [t.name for t in plan.travelers] == ["Abhi", "Priya", "Kid 1", "Kid 2"] and plan.adults == 2 and plan.kid_ages == (4, 7)
        assert plan.travelers[0].email == "you@gmail.com"
        out, back = plan.legs
        assert (out.name, out.origin, out.dest, out.depart, out.arrive, out.confirmation, out.seats) == (
            "Alaska Airlines AS 1234", "SFO", "LAX", datetime(2026, 10, 16, 8, 5), datetime(2026, 10, 16, 9, 32), "ABCDEF", "12A, 12B, 12C, 12D")
        assert (back.origin, back.dest, back.depart) == ("LAX", "SFO", datetime(2026, 10, 20, 14, 10))
        h = plan.hotels[0]
        assert (h.name, h.address, h.check_in, h.check_out, h.confirmation, h.room, h.rooms) == (
            "The Example Hotel Santa Monica", "123 Ocean Ave, Santa Monica, CA 90401", datetime(2026, 10, 16, 15), datetime(2026, 10, 20, 11), "987654321", "2 Queen Beds, Ocean View", 1)
        c = plan.rental
        assert (c.company, c.pickup_place, c.pickup, c.dropoff_place, c.dropoff, c.confirmation, c.car) == (
            "Hertz", "LAX", datetime(2026, 10, 16, 10), "LAX", datetime(2026, 10, 20, 12), "H1234567", "Midsize SUV")
        assert plan.notes.startswith("Anything else")


def test_the_destination_legs_and_the_stored_copy_round_trip():
    plan = ti.parse(TEMPLATE).plan
    assert plan.arrive_leg.dest == "LAX" and plan.depart_leg.origin == "LAX" and plan.home == "SFO"
    assert ti.from_doc(ti.to_doc(plan)) == plan


CONNECTIONS = """trip:
  title: Connecting
  destination: Los Angeles
  start: 2026-10-16
  end: 2026-10-20
travelers:
  - name: Abhi
flights:
  - {airline: Alaska, number: AS 1, from: SFO, to: SEA, depart: 2026-10-16 05:00, arrive: 2026-10-16 07:00}
  - {airline: Alaska, number: AS 2, from: SEA, to: LAX, depart: 2026-10-16 08:00, arrive: 2026-10-16 10:45}
  - {airline: Alaska, number: AS 3, from: LAX, to: DEN, depart: 2026-10-20 06:00, arrive: 2026-10-20 09:30}
  - {airline: Alaska, number: AS 4, from: DEN, to: SFO, depart: 2026-10-20 11:00, arrive: 2026-10-20 12:30}
"""


def test_a_connection_finds_the_destination_by_the_longest_wait():
    plan = ti.parse(CONNECTIONS).plan
    assert [f"{f.origin}{f.dest}" for f in plan.legs] == ["SFOSEA", "SEALAX", "LAXDEN", "DENSFO"]
    assert plan.arrive_leg.dest == "LAX" and plan.depart_leg.origin == "LAX"
    ids = [s.id for s in ti.block_specs(plan) if s.kind == "leg"]
    assert ids == ["b-leg1", "b-out", "b-back", "b-leg4"]


def test_sections_can_be_left_out_and_comments_are_ignored():
    text = "# my trip\ntrip:\n  title: Weekend\n  destination: Los Angeles\n  start: 2026-10-16\n  end: 2026-10-18\ntravelers:\n  - name: Abhi\nhotel:\n  name: Inn\n  address: 1 Main St\n  check_in: 2026-10-16\n  check_out: 2026-10-18\n"
    plan = ti.parse(text).plan
    assert plan.legs == () and plan.rental is None and plan.hotels[0].check_in.hour == 15 and plan.hotels[0].check_out.hour == 11 and plan.booked_on == "elsewhere"


def test_unreadable_yaml_names_the_line():
    errs = fails("trip:\n  title: x\n   destination: oops\n")
    assert len(errs) == 1 and errs[0].startswith("Line 3:")
    inside = fails("Some words\n```yaml\ntrip:\n  title: [unclosed\n```\n")
    assert inside[0].startswith("Line 4:") or inside[0].startswith("Line 5:")


@pytest.mark.parametrize("text", ["", "   ", "just some words", "- a\n- b", "42"])
def test_not_a_template_is_a_friendly_error(text):
    assert fails(text)


def test_every_problem_is_reported_with_its_line():
    text = yaml_of(TEMPLATE).replace("from: SFO", "from: San Francisco").replace("arrive: 2026-10-16 09:32", "arrive: tomorrow-ish").replace("check_out: 2026-10-20 11:00", "check_out: 2026-10-15 11:00")
    errs = fails(text)
    joined = "\n".join(errs)
    assert "three-letter airport code" in joined and "date and a 24-hour time" in joined and "Check-out has to be after check-in" in joined
    assert all(e.startswith("Line ") for e in errs) and len(errs) == 3


def test_line_numbers_count_from_the_top_of_a_pasted_markdown_page():
    errs = fails(TEMPLATE.replace("from: SFO", "from: nowhere"))
    n = next(i for i, line in enumerate(TEMPLATE.splitlines(), 1) if "from: SFO" in line)
    assert errs[0].startswith(f"Line {n}:")


def test_things_outside_the_trip_dates_and_odd_shapes_are_refused():
    base = yaml_of(TEMPLATE)
    assert any("outside your trip dates" in e for e in fails(base.replace("end: 2026-10-20", "end: 2026-10-18")))
    assert any("ends before it starts" in e for e in fails(base.replace("end: 2026-10-20", "end: 2026-10-10")))
    assert any("at least one adult" in e for e in fails(base.replace("  - name: Abhi\n", "  - name: Abhi\n    age: 9\n").replace("  - name: Priya\n", "  - name: Priya\n    age: 9\n")))
    assert any("does not look like an email" in e for e in fails(base.replace("priya@gmail.com", "priya at gmail")))
    assert any("age" in e for e in fails(base.replace("age: 7", "age: seven")))
    assert any("pickup" in e for e in fails(base.replace("pickup: LAX, 2026-10-16 10:00", "pickup: LAX")))
    assert any("nothing to put on the calendar" in e for e in fails("trip:\n  title: t\n  destination: d\n  start: 2026-10-16\n  end: 2026-10-17\ntravelers:\n  - name: A\n"))


def test_unknown_sections_warn_without_failing():
    parsed = ti.parse(yaml_of(TEMPLATE) + "\nflight:\n  - x\n")
    assert any("flight" in w and "skipped" in w for w in parsed.warnings)


def test_input_is_bounded_and_yaml_tricks_are_refused():
    assert "too long" in fails("x: " + "a" * 60_000)[0]
    assert "anchors" in fails("a: &x [1, 2]\nb: *x\n")[0]
    assert fails("!!python/object/apply:os.system ['echo hi']")  # safe_load only: no Python objects


# ---- review fixes ---------------------------------------------------------------------------------------------------

def test_text_fields_keep_their_exact_text():
    text = (yaml_of(TEMPLATE)
            .replace("confirmation: ABCDEF              # airline record locator", "confirmation: 012345")
            .replace('confirmation: "987654321"', "confirmation: yes")
            .replace('confirmation: "H1234567"', "confirmation: 12:30:45")
            .replace("seats: 12A, 12B, 12C, 12D         # optional", "seats: 0x1F")
            .replace('phone: "+1 310 555 0100"           # optional', "phone: 0123")
            .replace("room: 2 Queen Beds, Ocean View      # optional", "room: no")
            .replace("number: AS 1234", "number: 0099")
            .replace("name: Kid 1\n", "name: 1e3\n"))
    plan = ti.parse(text).plan
    assert plan.legs[0].confirmation == "012345" and plan.hotels[0].confirmation == "yes" and plan.rental.confirmation == "12:30:45"
    assert plan.legs[0].seats == "0x1F" and plan.hotels[0].phone == "0123" and plan.hotels[0].room == "no"
    assert plan.legs[0].number == "0099" and plan.travelers[2].name == "1e3"
    assert plan.travelers[2].age == 7 and plan.hotels[0].rooms == 1  # numbers still read as numbers where a number is meant


def test_repeated_keys_are_refused_with_the_line():
    base = yaml_of(TEMPLATE)
    errs = fails(base + "\nhotel:\n  name: Second\n")
    assert any("“hotel” appears twice" in e and e.startswith("Line ") for e in errs)
    assert any("appears twice" in e for e in fails(base + "\nflights:\n  - airline: x\n"))
    assert any("appears twice" in e for e in fails(base.replace("    number: AS 1234", "    number: AS 1234\n    number: AS 5")))


HOTELS = """
hotels:
  - name: First Inn
    address: 1 First St, Santa Monica, CA
    check_in: 2026-10-16 15:00
    check_out: 2026-10-18 11:00
    confirmation: "111"
  - name: Second Inn
    address: 2 Second St, Pasadena, CA
    check_in: 2026-10-18 15:00
    check_out: 2026-10-20 11:00
    confirmation: "222"
"""


def one_hotel_list(base):
    return re.sub(r"\nhotel:.*?(?=\ncar:)", HOTELS, base, flags=re.S)


import re


def test_two_hotels_work_and_the_single_form_still_does():
    plan = ti.parse(one_hotel_list(yaml_of(TEMPLATE))).plan
    assert [h.name for h in plan.hotels] == ["First Inn", "Second Inn"]
    ids = [s.id for s in ti.block_specs(plan) if s.kind in ("checkin", "checkout")]
    assert len(ids) == 4 and len(set(ids)) == 4 and ids[:2] == ["b-in", "b-out2"]
    assert ti.stay_offer(plan, "imp-x", "arrive").name == "First Inn" and ti.stay_offer(plan, "imp-x", "depart").name == "Second Inn"
    assert ti.parse(TEMPLATE).plan.hotels[0].name == "The Example Hotel Santa Monica"
    assert ti.from_doc(ti.to_doc(plan)) == plan
    both = yaml_of(TEMPLATE) + HOTELS
    assert any("both" in e for e in fails(both.replace("\nhotels:", "\nhotels:", 1)))
    overlap = one_hotel_list(yaml_of(TEMPLATE)).replace("check_in: 2026-10-18 15:00", "check_in: 2026-10-17 15:00")
    assert any("overlap" in e for e in fails(overlap))


def test_deep_nesting_is_a_friendly_error_not_a_crash():
    assert "nested" in fails("a: " + "[" * 3000 + "]" * 3000)[0].lower()
    assert "nested" in fails("trip:\n" + "".join("  " * i + "k:\n" for i in range(1, 80)))[0].lower()


ONEWAY = CONNECTIONS.split("flights:")[0] + """flights:
  - {airline: Alaska, number: AS 1, from: SFO, to: PHX, depart: 2026-10-16 05:00, arrive: 2026-10-16 08:00}
  - {airline: Alaska, number: AS 2, from: PHX, to: LAX, depart: 2026-10-16 10:00, arrive: 2026-10-16 11:00}
"""


def test_a_one_way_trip_with_a_connection_arrives_at_its_last_leg():
    plan = ti.parse(ONEWAY).plan
    assert plan.arrive_leg.dest == "LAX" and plan.depart_leg is None
    assert ti.flight_offer(plan, "imp-x").airport == "LAX"
    assert ti.trip_search(plan).airports == ("LAX",)


def test_red_eyes_land_the_day_after_the_trip_ends_and_block_the_landing_morning():
    base = yaml_of(TEMPLATE)
    back = base.replace("depart: 2026-10-20 14:10", "depart: 2026-10-20 23:10").replace("arrive: 2026-10-20 15:37", "arrive: 2026-10-21 00:37")
    assert ti.parse(back).plan.legs[1].arrive.day == 21
    out = base.replace("depart: 2026-10-16 08:05", "depart: 2026-10-15 22:05").replace("arrive: 2026-10-16 09:32", "arrive: 2026-10-16 06:32")
    assert ti.parse(out).plan.legs[0].depart.day == 15  # an outbound red-eye may leave the evening before the trip starts
    assert any("outside your trip dates" in e for e in fails(base.replace("depart: 2026-10-16 08:05", "depart: 2026-10-14 22:05")))
    assert any("outside your trip dates" in e for e in fails(base.replace("arrive: 2026-10-20 15:37", "arrive: 2026-10-22 00:37")))


def test_a_section_that_failed_does_not_also_say_nothing_was_booked():
    errs = fails("trip:\n  title: t\n  destination: d\n  start: 2026-10-16\n  end: 2026-10-17\ntravelers:\n  - name: A\nhotel:\n  name: Inn\n")
    assert not any("nothing to put on the calendar" in e for e in errs) and errs
