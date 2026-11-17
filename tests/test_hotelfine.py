"""F-282: the fine print up front (gitaway/hotelfine.py, drawn by pages/fineprint.py), over the recorded Hilton Los Angeles Airport answers (tests/fixtures/liteapi_hotel). `hotel.json` has no
`hotelImportantInformation`, so the tests that need it add the field the way LiteAPI documents it (a string of HTML lines): that text is written here, not recorded."""
import json
from pathlib import Path

import pytest

from gitaway import hotelfine, liteapi

FIX = Path(__file__).parent / "fixtures" / "liteapi_hotel"
# SYNTHETIC: written for these tests, not LiteAPI data (the recorded Hilton answer has no important information)
IMPORTANT = ("<p>A resort fee of USD 35 per night is charged at the property.</p><p>Guests must be 21 or older to check in.</p>"
             "<p>Parking is available for USD 42 per night.</p><br>Quiet hours start at 10 PM.")
BARE = {"data": {"name": "X", "id": "x1"}}


def hotel(important=None):
    d = json.loads((FIX / "hotel.json").read_text(encoding="utf-8"))
    if important is not None:
        d["data"][liteapi.IMPORTANT_FIELD] = important
    return liteapi.read_hotel(d)


GRIPE = "Breakfast was pricey and parking costs extra"      # SYNTHETIC: the recorded reviews each name one topic, so none shares two words with a sentiment line; three get this one


def reviews_doc(gripe=True):
    """reviews100.json, with (SYNTHETIC) cons on three reviews that share two words with the Pricey complaint."""
    doc = json.loads((FIX / "reviews100.json").read_text(encoding="utf-8"))
    if gripe:
        for i in (1, 4, 9):
            doc["data"][i]["cons"] = GRIPE
    return doc


@pytest.fixture(scope="module")
def hundred():
    return liteapi.read_reviews(reviews_doc())


def test_the_hotels_important_information_is_its_lines_as_plain_text_and_absent_when_it_gave_none():
    assert hotel().important == ()
    assert hotel(IMPORTANT).important == ("A resort fee of USD 35 per night is charged at the property.", "Guests must be 21 or older to check in.",
                                          "Parking is available for USD 42 per night.", "Quiet hours start at 10 PM.")
    assert hotel("<p><script>x()</script>Pets <b>welcome</b></p>").important == ("Pets welcome",)


def test_costs_not_in_the_price_are_the_hotels_own_lines_that_name_money_and_each_wears_heads_up():
    fp = hotelfine.build(hotel(IMPORTANT), None)
    flagged = [i.title for i in fp.costs if i.flag]
    assert flagged == ["A resort fee of USD 35 per night is charged at the property.", "Parking is available for USD 42 per night."]
    assert "Guests must be 21 or older to check in." not in [i.title for i in fp.costs]      # not about money: a policy
    assert "Guests must be 21 or older to check in." in [i.title for i in fp.policies] and "Quiet hours start at 10 PM." in [i.title for i in fp.policies]


def test_with_no_important_information_parking_is_listed_but_its_price_is_not_and_nothing_is_flagged():
    fp = hotelfine.build(hotel(), None)
    assert [(i.title, i.note, i.flag) for i in fp.costs] == [("Parking", "Listed by the hotel; the price is not listed", False)]
    gone = liteapi.read_hotel(BARE)
    assert [(i.title, i.state) for i in hotelfine.build(gone, None).costs] == [("Parking: not listed", "unknown")]


def test_check_in_and_check_out_are_the_hotels_times_or_not_listed():
    fp = hotelfine.build(hotel(), None)
    assert [i.title for i in fp.policies[:2]] == ["Check-in from 04:00 PM", "Check-out by 12:00 PM"]
    gone = liteapi.read_hotel(BARE)
    assert [i.title for i in hotelfine.build(gone, None).policies[:2]] == ["Check-in: not listed", "Check-out: not listed"]
    assert hotelfine.build(hotel(), None).checkin_minutes == 16 * 60 and hotelfine.build(gone, None).checkin_minutes is None


def test_fits_your_family_is_what_the_facilities_say_plus_the_families_average_with_enough_reviews(hundred):
    fp = hotelfine.build(hotel(), hundred)
    titles = {i.title: i for i in fp.family}
    assert titles["Family rooms"].state == "ok" and titles["Swimming pool"].state == "ok"
    assert titles["Cribs: not listed"].state == "unknown" and titles["Kids’ club: not listed"].state == "unknown" and titles["Connecting rooms: not listed"].state == "unknown"
    assert titles["Largest room sleeps 4"].state == "ok"
    assert "Families with children: 7.8 on average, from 8 of the last 100 reviews." in titles
    few = liteapi.HotelReviews(hundred.items[:20], (), (), (), 20)
    assert not [i for i in hotelfine.build(hotel(), few).family if i.title.startswith("Families with children")]      # too few of their own: nothing said
    assert not [i for i in hotelfine.build(hotel(), None).family if i.title.startswith("Families with children")]


def test_the_usual_line_holds_the_ordinary_facilities_and_none_that_are_said_elsewhere(hundred):
    fp = hotelfine.build(hotel(), hundred)
    assert fp.usual.startswith("The usual: ") and "WiFi available" in fp.usual and "Fitness facilities" in fp.usual
    assert "Swimming pool" not in fp.usual and "Family rooms" not in fp.usual and "Parking" not in fp.usual
    assert hotelfine.build(liteapi.read_hotel(BARE), None).usual == ""


def test_a_complaint_finds_the_reviews_whose_cons_mention_it_in_the_drawers_newest_first_order(hundred):
    fp = hotelfine.build(hotel(), hundred)
    drawer = hotelfine.newest_first(hundred.items)
    assert [r.date for r in drawer] == sorted((r.date for r in drawer), reverse=True) and len(drawer) == 100
    words = ("breakfast", "tax", "parking", "lobby", "shop", "pricey")
    pricey = next(c for c in fp.complaints if c.text.startswith("Pricey"))
    assert pricey.count >= 3
    two = lambda r: sum(w in r.cons.lower() for w in words) >= 2      # noqa: E731
    assert pricey.ids and all(two(drawer[i]) for i in pricey.ids)
    assert pricey.count == len(pricey.ids) == sum(1 for r in drawer if two(r))
    water = next(c for c in fp.complaints if c.text.startswith("No in-room water"))
    assert water.ids == () and water.count == 0      # no review says it: listed, with no reviews to open


def test_what_guests_complain_about_is_the_sentiment_cons_only(hundred):
    assert [c.text for c in hotelfine.build(hotel(), hundred).complaints] == list(hundred.cons)
    assert hotelfine.build(hotel(), None).complaints == ()


def test_a_complaint_needs_two_meaningful_words_in_a_review_and_a_near_miss_does_not_count():
    def rev(cons):
        return liteapi.Review("A", "2026-11-10", 5, "couple", "us", "", "", cons, "")
    rv = liteapi.HotelReviews((rev("Parking is dear"), rev("Breakfast was pricey and the parking too"), rev("The hotel room was reported small"), rev("Great")), (), (), ("Pricey breakfast and parking", "Hotel guests reported small rooms"), 4)
    first, second = hotelfine.build(hotel(), rv).complaints
    drawer = hotelfine.newest_first(rv.items)
    assert [drawer[i].cons for i in first.ids] == ["Breakfast was pricey and the parking too"] and first.count == 1      # "Parking is dear" shares one word: a near miss
    assert second.ids == () and second.count == 0      # "hotel", "guests", "reported", "room(s)" are generic: only "small" is left, one word


def test_the_recorded_reviews_alone_match_no_complaint_so_every_one_says_so():
    rv = liteapi.read_reviews(reviews_doc(gripe=False))
    assert [c.count for c in hotelfine.build(hotel(), rv).complaints] == [0, 0, 0, 0, 0]
