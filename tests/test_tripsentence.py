"""F-217: the search as one sentence. `tripsentence.read` reads it with plain rules and guesses nothing; `write` says it back."""
from datetime import date

import pytest

from gitaway import tripsentence as ts

TODAY = date(2026, 11, 11)
FULL = "A family of 4 with Grandma and the dog, SFO to Orlando, Dec 12 to 16, within 20 miles of Disney, under $3,000."


def test_the_whole_sentence_is_read_part_by_part():
    ask = ts.read(FULL, TODAY)
    assert (ask.adults, ask.kid_ages, ask.ages_given) == (2, (8, 8), False)
    assert (ask.senior, ask.pet) == ("Grandma", "dog")
    assert (ask.origin, ask.place) == ("SFO", "Orlando")
    assert (ask.depart, ask.return_) == (date(2026, 12, 12), date(2026, 12, 16))
    assert (ask.near, ask.miles, ask.budget_cents) == ("Disney", 20, 300_000)
    assert ask.unread == ()


def test_it_writes_the_sentence_back_and_reads_its_own_words():
    ask = ts.read(FULL, TODAY)
    assert ts.write(ask) == FULL
    assert ts.read(ts.write(ask), TODAY) == ask


@pytest.mark.parametrize("words, depart, ret", [
    ("to Maui, December 28 to January 3", date(2026, 12, 28), date(2027, 1, 3)),
    ("to Maui, Jan 5 - 9", date(2027, 1, 5), date(2027, 1, 9)),                       # a month that has passed this year is next year's
    ("to Maui, 2026-12-12 to 2026-12-16", date(2026, 12, 12), date(2026, 12, 16)),
    ("to Maui 12/12 to 12/16", date(2026, 12, 12), date(2026, 12, 16)),
    ("to Maui, Dec 12th through 16th", date(2026, 12, 12), date(2026, 12, 16)),
    ("to Maui on Dec 12 for 4 nights", date(2026, 12, 12), date(2026, 12, 16)),
    ("to Maui, Nov 11 to 14", date(2026, 11, 11), date(2026, 11, 14)),                 # today is not the past
])
def test_dates_in_the_forms_people_type(words, depart, ret):
    ask = ts.read(words, TODAY)
    assert (ask.depart, ask.return_) == (depart, ret)
    assert ask.place == "Maui"


@pytest.mark.parametrize("words", ["to Maui, Feb 30 to Mar 2", "to Maui, 2026-10-01 to 2026-10-05", "to Maui, Dec 16 to Dec 12 2026 or so", "to Maui sometime in spring",
                                    "to Maui, 2026-12-01 to 2027-03-01"])
def test_dates_it_cannot_read_are_left_empty_never_guessed(words):
    ask = ts.read(words, TODAY)
    if "Dec 16 to Dec 12" in words:      # a return before the leaving day is next year's Dec 12: more than MAX_NIGHTS, so no dates
        assert (ask.depart, ask.return_) == (None, None)
    assert "dates" in ask.unread


@pytest.mark.parametrize("words, adults, kids, given", [
    ("2 adults and 3 kids to Reno", 2, (8, 8, 8), False),
    ("two adults, kids ages 4 and 7, to Reno", 2, (4, 7), True),
    ("a couple to Reno", 2, (), False),
    ("just me, to Reno", 1, (), False),
    ("family of five to Reno", 2, (8, 8, 8), False),
    ("to Reno", 2, (), False),
    ("40 adults to Reno", 2, (), False),                                              # more than a booking takes: the usual two, and the party counts as not said
])
def test_who_is_going(words, adults, kids, given):
    ask = ts.read(words, TODAY)
    assert (ask.adults, ask.kid_ages, ask.ages_given) == (adults, kids, given)
    assert ask.place == "Reno"


def test_nobody_said_who_is_going():
    assert ts.read("to Reno", TODAY).party_given is False
    assert ts.read("a couple to Reno", TODAY).party_given is True
    assert ts.read("40 adults to Reno", TODAY).party_given is False


@pytest.mark.parametrize("words, cents", [("to Reno under $3,000", 300_000), ("to Reno, budget 2500", 250_000), ("to Reno for $3k", 300_000), ("to Reno, up to $1,999.50", 199_950),
                                          ("to Reno", None), ("to Reno under $900,000,000", None)])
def test_the_budget(words, cents):
    assert ts.read(words, TODAY).budget_cents == cents


@pytest.mark.parametrize("words, origin, place", [
    ("SFO to Lake Tahoe, Dec 12 to 16", "SFO", "Lake Tahoe"),
    ("from OAK to New York in December", "OAK", "New York"),
    ("flying to San Diego with the kids", "", "San Diego"),
    ("a week in Honolulu", "", "Honolulu"),
    ("somewhere warm", "", ""),
])
def test_the_route(words, origin, place):
    ask = ts.read(words, TODAY)
    assert (ask.origin, ask.place) == (origin, place)


def test_near_without_miles_and_pets_and_seniors():
    ask = ts.read("2 adults with my mom and our cat to San Diego near the zoo, Dec 12 to 16", TODAY)
    assert (ask.near, ask.miles, ask.senior, ask.pet) == ("zoo", None, "my mom", "cat")
    assert ts.write(ask) == "2 adults with my mom and the cat, to San Diego, Dec 12 to 16, near zoo."


def test_a_place_never_swallows_the_rest_of_the_sentence_or_an_attack():
    ask = ts.read("to Orlando with breakfast under $2,000 <script>alert(1)</script>" + "x" * 500, TODAY)
    assert ask.place == "Orlando"
    assert len(ts.write(ask)) < 200


def test_empty_and_odd_input():
    for words in ("", None, "   ", "12345", "to to to"):
        ask = ts.read(words, TODAY)
        assert "place" in ask.unread or ask.place
