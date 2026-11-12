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
    ("just the 2 of us, kids ages 5, 7, 12/20 to 12/24 to Reno", 2, (5, 7), True),    # the days of a date are never ages
])
def test_who_is_going(words, adults, kids, given):
    ask = ts.read(words, TODAY)
    assert (ask.adults, ask.kid_ages, ask.ages_given) == (adults, kids, given)
    assert ask.place == "Reno"


def test_nobody_said_who_is_going():
    assert ts.read("to Reno", TODAY).party_given is False
    assert ts.read("a couple to Reno", TODAY).party_given is True


@pytest.mark.parametrize("words", ["40 adults to Reno, Dec 12 to 16", "family of 12 to Reno, Dec 12 to 16", "6 adults and 4 kids to Reno, Dec 12 to 16"])
def test_more_travelers_than_a_booking_takes_is_said_not_cut_down(words):
    ask = ts.read(words, TODAY)
    assert ask.too_many and ask.unread == ("party",)


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


@pytest.mark.parametrize("words, depart, ret", [
    ("SFO to Orlando, Dec 12 to 16, 2027", date(2027, 12, 12), date(2027, 12, 16)),
    ("to Orlando, Dec 12, 2027 to Dec 16, 2027", date(2027, 12, 12), date(2027, 12, 16)),
    ("to Orlando, Dec 28 to Jan 3, 2028", date(2027, 12, 28), date(2028, 1, 3)),      # a year typed once, after a trip that crosses it, is the return's
    ("to Orlando 12/12/2027 to 12/16/2027", date(2027, 12, 12), date(2027, 12, 16)),
    ("to Orlando 12/12/27 - 12/16/27", date(2027, 12, 12), date(2027, 12, 16)),
])
def test_a_typed_year_is_taken_at_its_word(words, depart, ret):
    ask = ts.read(words, TODAY)
    assert (ask.depart, ask.return_, ask.place) == (depart, ret, "Orlando")


@pytest.mark.parametrize("words", ["to Orlando, Dec 12 to 16, 2020", "to Orlando 12/12/2020 to 12/16/2020", "to Orlando, Oct 1 to 5, 2026"])
def test_a_typed_year_in_the_past_is_not_moved_to_another_year(words):
    assert "dates" in ts.read(words, TODAY).unread


def test_by_myself_is_one_adult_and_not_a_place_to_be_near():
    ask = ts.read("to San Diego, Dec 12 to 16, by myself", TODAY)
    assert (ask.adults, ask.near, ask.place) == (1, "", "San Diego")


@pytest.mark.parametrize("words", ["to Reno, less than 600 miles from home", "to Reno for up to 5 nights", "to Reno under $25,000", "to Reno under $300", "to Reno with under 3 kids"])
def test_a_number_that_is_not_a_budget_is_not_read_as_one(words):
    assert ts.read(words, TODAY).budget_cents is None


def test_the_nights_form_reads_wherever_its_two_halves_are():
    ask = ts.read("For 4 nights from SFO to San Diego on Dec 12", TODAY)
    assert (ask.origin, ask.place, ask.depart, ask.return_) == ("SFO", "San Diego", date(2026, 12, 12), date(2026, 12, 16))
    ask = ts.read("İstanbul lovers: SFO to San Diego, Dec 12 to 16", TODAY)             # a letter whose lower case is longer never shifts the cut
    assert (ask.origin, ask.place, ask.depart) == ("SFO", "San Diego", date(2026, 12, 12))


# ---- F-222: "or nearby" and "give or take N days" ----

MATRIX = "A family of 4, SFO to San Diego or nearby, Dec 12 to 16 give or take 2 days, under $3,000."


def test_or_nearby_and_give_or_take_are_read_and_written_back():
    ask = ts.read(MATRIX, TODAY)
    assert (ask.origin, ask.place, ask.nearby, ask.flex) == ("SFO", "San Diego", True, 2)
    assert (ask.depart, ask.return_, ask.budget_cents, ask.travelers) == (date(2026, 12, 12), date(2026, 12, 16), 300_000, 4)
    assert ask.unread == ()
    assert ts.write(ask) == MATRIX
    assert ts.read(ts.write(ask), TODAY) == ask


@pytest.mark.parametrize("words", ["to San Diego or nearby", "to San Diego or somewhere nearby", "to San Diego or near by, Dec 12 to 16", "to San Diego or close by",
                                   "to San Diego, or nearby, Dec 12 to 16"])
def test_or_nearby_in_the_forms_people_type(words):
    ask = ts.read(words, TODAY)
    assert (ask.place, ask.nearby, ask.near) == ("San Diego", True, "")


def test_without_or_nearby_it_is_that_place_and_near_is_still_a_stay_near_something():
    ask = ts.read("to San Diego near the zoo, Dec 12 to 16", TODAY)
    assert (ask.place, ask.nearby, ask.near) == ("San Diego", False, "zoo")


@pytest.mark.parametrize("words, flex", [
    ("to Orlando, Dec 12 to 16 give or take 2 days", 2),
    ("to Orlando, Dec 12 to 16, give or take a day", 1),
    ("to Orlando, Dec 12 to 16 give or take 1 day", 1),
    ("to Orlando, Dec 12 to 16 give or take three days", 3),
    ("to Orlando, Dec 12 to 16 plus or minus 2 days", 2),
    ("to Orlando, Dec 12 to 16 +/- 2 days", 2),
    ("to Orlando, Dec 12 to 16 ± 2 days", 2),
    ("to Orlando, Dec 12 to 16, 2 days either way", 2),
    ("to Orlando, flexible by 3 days, Dec 12 to 16", 3),
    ("to Orlando, Dec 12 to 16 exactly", 0),
    ("to Orlando, Dec 12 to 16 give or take 0 days", 0),
    ("to Orlando, Dec 12 to 16", None),
])
def test_give_or_take_in_the_forms_people_type(words, flex):
    ask = ts.read(words, TODAY)
    assert (ask.place, ask.depart, ask.return_, ask.flex) == ("Orlando", date(2026, 12, 12), date(2026, 12, 16), flex)
    assert ask.unread == () and ask.budget_cents is None and ask.kid_ages == ()


@pytest.mark.parametrize("words", ["to Orlando, Dec 12 to 16 give or take 5 days", "to Orlando, Dec 12 to 16 give or take a week", "to Orlando, Dec 12 to 16 give or take some days"])
def test_a_give_or_take_it_cannot_read_is_named_never_guessed(words):
    ask = ts.read(words, TODAY)
    assert ask.flex is None and ask.unread == ("flex",)
    assert ask.place == "Orlando" and ask.depart == date(2026, 12, 12)


def test_exact_dates_and_one_day_are_written_in_words_that_read_back():
    for words, said in (("to Orlando, Dec 12 to 16 exactly", "to Orlando, Dec 12 to 16 exactly."), ("to Orlando, Dec 12 to 16 give or take a day", "to Orlando, Dec 12 to 16 give or take 1 day.")):
        ask = ts.read(words, TODAY)
        assert ts.write(ask) == "2 adults, " + said
        again = ts.read(ts.write(ask), TODAY)
        assert (again.flex, again.depart, again.return_, again.place) == (ask.flex, ask.depart, ask.return_, ask.place)


def test_the_new_parts_are_their_own_keys_for_the_page():
    found = dict(ts.parts(ts.read(MATRIX, TODAY)))
    assert found["route"] == "SFO to San Diego or nearby" and found["flex"] == "give or take 2 days" and found["dates"] == "Dec 12 to 16"
