"""F-197 "What to book and when": a countdown checklist per destination, from facts checked against official sites (gitaway/planfacts.py, sources in docs/decisions.md D-213 and D-214),
with the dates worked out from the trip's own first day. A place we have not checked gets an honest generic list that says so."""

from datetime import date

import pytest

from gitaway import planfacts as pf

START = date(2027, 3, 15)        # a Monday
TODAY = date(2026, 11, 6)


def by_title(items):
    return {i["title"]: i for i in items}


@pytest.mark.parametrize("where,key", [("Disneyland, California", "disneyland"), ("Disneyland Resort", "disneyland"), ("Anaheim", "disneyland"), ("disney california adventure", "disneyland"),
                                       ("New York City", "nyc"), ("NYC", "nyc"), ("Manhattan, New York", "nyc"), ("Brooklyn", "nyc"),
                                       ("Oahu", "oahu"), ("O'ahu, Hawaii", "oahu"), ("Honolulu", "oahu"), ("Waikiki", "oahu"),
                                       ("Lisbon", None), ("Disney World, Florida", None), ("New York State", None), ("", None)])
def test_a_place_is_matched_only_when_we_have_checked_it(where, key):
    p = pf.place_for(where)
    assert (p.key if p else None) == key


def test_disneyland_dining_opens_60_days_before_the_first_day():
    items = by_title(pf.checklist("Disneyland, California", START, TODAY))
    dining = items["Dining reservations"]
    assert dining["when"] == date(2027, 1, 14) and dining["label"] == "Opens Thu, Jan 14" and not dining["now"]
    assert "60 days" in dining["detail"]


def test_the_list_is_soonest_first_and_the_on_the_day_items_come_last():
    items = pf.checklist("Disneyland, California", START, TODAY)
    dated = [i["when"] for i in items if i["when"]]
    assert dated == sorted(dated) and items[-1]["when"] is None and items[-1]["label"] == "On the day"
    assert any("Lightning Lane" in i["title"] for i in items if i["when"] is None)


def test_a_date_already_past_says_now():
    items = by_title(pf.checklist("Disneyland, California", date(2026, 11, 30), TODAY))
    assert items["Dining reservations"]["label"] == "Now" and items["Dining reservations"]["now"]
    assert items["Dining reservations"]["when"] == TODAY


def test_the_dates_move_with_the_trip():
    a = by_title(pf.checklist("Disneyland, California", START, TODAY))["Dining reservations"]["when"]
    b = by_title(pf.checklist("Disneyland, California", date(2027, 4, 15), TODAY))["Dining reservations"]["when"]
    assert (b - a).days == (date(2027, 4, 15) - START).days


@pytest.mark.parametrize("where", ["New York City", "Oahu"])
def test_every_checked_place_has_its_own_list_with_dates(where):
    items = pf.checklist(where, START, TODAY)
    assert len(items) >= 4 and any(i["when"] for i in items)
    assert [i["title"] for i in items] != [g.title for g in pf.GENERIC] and not any("not checked" in i["detail"] for i in items)


def test_a_place_we_have_not_checked_gets_the_generic_list_that_says_so():
    items = pf.checklist("Lisbon", START, TODAY)
    assert [i["title"] for i in items] == [g.title for g in sorted(pf.GENERIC, key=lambda g: -g.days)]
    assert any("not checked" in i["detail"] for i in items)
    assert pf.intro("Lisbon").startswith("We have not checked") and "official" in pf.intro("Disneyland, California")


def test_no_fact_names_a_price_or_opening_hours():
    """Every line passes the agent's own filter whole: not one sentence of it would be dropped as a price or opening hours."""
    from gitaway import planforme as pfm
    lines = [x for p in pf.PLACES.values() for b in p.items for x in (b.title, b.detail)] + [x for b in pf.GENERIC for x in (b.title, b.detail)]
    lines += [f for p in pf.PLACES.values() for f in p.facts if "Height minimums" not in f]      # the heights list is numbers on purpose, and says nothing of money or hours
    for line in lines:
        assert pfm._claim(line, 2000) == line, line


def test_every_item_fits_a_trip_note_whole():
    from gitaway import tripcal
    for where in ("Disneyland", "NYC", "Oahu", "Lisbon"):
        for start in (START, date(2026, 11, 20)):      # a dated label and "Book now"
            for i in pf.checklist(where, start, TODAY):
                note = pf.note_text(i, tripcal.MAX_NOTE)
                assert len(note) <= tripcal.MAX_NOTE and note.endswith(i["detail"]), note
