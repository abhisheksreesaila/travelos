"""LiteAPI (F-220): stays and flights parsed from answers the sandbox really gave (tests/fixtures/liteapi, recorded 2026-11-12), the cache, the daily budgets."""

import json
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from gitaway import liteapi

FIX = Path(__file__).parent / "fixtures" / "liteapi"
KEY = "sand_test-key-not-real"
IN, OUT = date(2026, 12, 12), date(2026, 12, 16)


def raw(name) -> bytes:
    return (FIX / name).read_bytes()


def answer(name) -> dict:
    return json.loads(raw(name))


class Fake:
    """A TRANSPORT that answers from the recorded fixtures and remembers what was asked."""

    def __init__(self, status=200, body=None, ctype="application/json"):
        self.asked, self.status, self.body, self.ctype = [], status, body, ctype

    def __call__(self, url, headers, body, timeout):
        self.asked.append((url, headers, json.loads(body) if body else None))
        if self.body is not None:
            return self.status, self.ctype, self.body
        if "/hotels/rates" in url:
            return 200, "application/json", raw("hotel_rates.json")
        if "/flights/rates" in url:
            return 200, "application/json; charset=utf-8", raw("flight_rates.json")
        if "/data/hotel" in url:
            return 200, "application/json", raw("hotel_detail.json")
        raise AssertionError(url)


@pytest.fixture
def fake(monkeypatch):
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    f = Fake()
    monkeypatch.setattr(liteapi, "TRANSPORT", f)
    return f


def stays(**over):
    return liteapi.stays(**{"city": "San Diego", "country": "US", "checkin": IN, "checkout": OUT, "adults": 2, "kid_ages": (7, 10), **over})


def flights(**over):
    return liteapi.flights(**{"legs": (("SFO", "SAN", IN), ("SAN", "SFO", OUT)), "adults": 2, "kid_ages": (7, 10), **over})


# --- reading what the sandbox said

def test_stays_are_each_hotels_cheapest_room_in_cents_taxes_included():
    at = datetime(2026, 11, 12, 19, 50, tzinfo=timezone.utc)
    got = liteapi.read_stays(answer("hotel_rates.json"), at)
    assert [s.id for s in got] == ["lp369ef", "lp280e6", "lp1fa70", "lp3f338", "lp1f5cb"]      # cheapest first
    assert [s.cents for s in got] == [59694, 60879, 65389, 73430, 118092]
    first = got[0]
    hotel = next(h for h in answer("hotel_rates.json")["hotels"] if h["id"] == "lp369ef")
    offer = next(d for d in answer("hotel_rates.json")["data"] if d["hotelId"] == "lp369ef")["roomTypes"][0]
    assert first.name == hotel["name"] and first.photo == hotel["main_photo"] and first.thumbnail == hotel["thumbnail"]
    assert (first.lat, first.lng, first.stars, first.rating, first.reviews) == (hotel["latitude"], hotel["longitude"], hotel["stars"], hotel["rating"], hotel["review_count"])
    assert first.room == "Standard Room, 2 Queen Beds" and first.board == "room only" and first.refundable is False
    assert first.offer_id == offer["offerId"]                     # verbatim
    assert first.due_at_stay_cents == 16000                       # the resort fee the total leaves out ("included": false), paid at the hotel
    assert first.fetched == at


def only(test) -> dict:
    """The recorded answer with only the rooms that pass `test`, so the cheapest left is one of them."""
    a = answer("hotel_rates.json")
    for h in a["data"]:
        h["roomTypes"] = [rt for rt in h["roomTypes"] if test(rt["rates"][0])]
    a["data"] = [h for h in a["data"] if h["roomTypes"]]
    return a


def test_a_refundable_room_with_breakfast_is_read_as_such():
    got = liteapi.read_stays(only(lambda r: r["boardType"] == "BI"), datetime.now(timezone.utc))
    assert got and all(s.board == "breakfast" for s in got)
    got = liteapi.read_stays(only(lambda r: r["cancellationPolicies"]["refundableTag"] == "RFN"), datetime.now(timezone.utc))
    assert got and all(s.refundable for s in got)


def test_an_answer_without_data_or_with_an_error_is_not_read_as_nothing_found():
    for bad in (answer("error_400.json"), {}, {"data": "x"}, [], None):
        with pytest.raises(liteapi.Unreadable):
            liteapi.read_stays(bad, datetime.now(timezone.utc))
        with pytest.raises(liteapi.Unreadable):
            liteapi.read_flights(bad, datetime.now(timezone.utc))
    assert liteapi.read_stays({"data": [], "hotels": []}, datetime.now(timezone.utc)) == ()


def test_flights_are_each_journeys_cheapest_offer_for_the_whole_party():
    at = datetime(2026, 11, 12, 19, 48, tzinfo=timezone.utc)
    got = liteapi.read_flights(answer("flight_rates.json"), at)
    j = answer("flight_rates.json")["data"][0]["journeys"]
    assert len(got) == len(j) and [f.cents for f in got] == sorted(f.cents for f in got)
    cheap = got[0]
    assert cheap.cents == 11484 and cheap.airline == "Frontier Airlines" and cheap.id == "0066a9a93554c975"
    assert cheap.offer_id == j[0]["cheapestOffer"]["offerId"] and cheap.expires == datetime(2026, 11, 12, 19, 57, 58, 910000, tzinfo=timezone.utc)
    out, back = cheap.legs
    assert (out.direction, out.origin, out.destination, out.depart, out.arrive, out.stops, out.minutes, out.flights) == \
        ("OUTBOUND", "SFO", "SAN", datetime(2026, 12, 12, 16, 33), datetime(2026, 12, 12, 18, 16), 0, 103, ("F9 3382",))
    assert (back.origin, back.destination, back.minutes) == ("SAN", "SFO", 115)
    assert (cheap.carry_on, cheap.checked, cheap.bags) == (False, False, ("One Personal Article",))
    assert cheap.refundable is False and cheap.fetched == at
    nuitee = next(f for f in got if f.airline == "Nuitée Air")
    assert nuitee.cents == 73029                                   # 2 adults at $208.65 and 2 children at $156.49: the party, not a person
    one_stop = next(f for f in got if len(f.legs[0].flights) == 1 and len(f.legs[1].flights) == 2)
    assert one_stop.legs[0].stops == 0 and one_stop.legs[1].stops == 1
    assert one_stop.legs[1].minutes == next(x for x in j if x["journeyKey"] == one_stop.id)["legDurations"][1]["duration"]["minutes"]


def test_the_streamed_answer_reads_the_same_as_the_plain_one():
    sse = liteapi.read_body("text/event-stream", raw("flight_rates.sse"))
    got = liteapi.read_flights(sse, datetime.now(timezone.utc))
    assert len(got) == 2 and got[0].cents == 11484 and got[0].airline == "Frontier Airlines"
    with pytest.raises(liteapi.Unreadable):
        liteapi.read_body("text/event-stream", b'event: error\ndata: {"error": {"code": 51099}}\n\n')


def test_html_in_a_hotels_description_is_stripped():
    text = liteapi.strip_html(answer("hotel_detail.json")["data"]["hotelDescription"])
    assert "<" not in text and "&amp;" not in text and "Beachfront Luxury at Pacific Terrace Hotel" in text
    assert liteapi.strip_html("<p>A &amp; B</p><p>C<br>D</p><script>x()</script>") == "A & B\n\nC\nD"


# --- the calls

def test_a_city_search_asks_the_way_the_sandbox_answered(fake):
    got = stays()
    assert got.status == liteapi.OK and len(got.items) == 5
    url, headers, body = fake.asked[0]
    assert url == "https://api.liteapi.travel/v3.0/hotels/rates" and headers["X-API-Key"] == KEY
    assert body["cityName"] == "San Diego" and body["countryCode"] == "US" and (body["checkin"], body["checkout"]) == ("2026-12-12", "2026-12-16")
    assert body["occupancies"] == [{"adults": 2, "children": [7, 10]}] and body["currency"] == "USD" and body["guestNationality"] == "US"


def test_a_search_near_a_point_sends_the_point_and_radius(fake):
    stays(city="", country="", lat=32.7157, lng=-117.1611, radius_m=5000)
    body = fake.asked[0][2]
    assert (body["latitude"], body["longitude"], body["radius"]) == (32.7157, -117.1611, 5000) and "cityName" not in body


def test_a_flight_search_sends_legs_and_the_party(fake):
    got = flights(kid_ages=(7, 1))
    assert got.status == liteapi.OK and got.items[0].cents == 11484
    url, headers, body = fake.asked[0]
    assert url == "https://api.liteapi.travel/v3.0/flights/rates" and headers["X-API-Key"] == KEY
    assert body["legs"] == [{"origin": "SFO", "destination": "SAN", "date": "2026-12-12", "direction": "OUTBOUND"},
                            {"origin": "SAN", "destination": "SFO", "date": "2026-12-16", "direction": "INBOUND"}]
    assert (body["adults"], body["children"], body["childrenAges"], body["infants"], body["infantAges"]) == (2, 1, [7], 1, [1])
    assert body["currency"] == "USD" and body["country"] == "US"


def test_no_key_means_off_and_nothing_is_asked(monkeypatch):
    monkeypatch.delenv("LITEAPI_KEY", raising=False)
    monkeypatch.setattr(liteapi, "TRANSPORT", lambda *a: pytest.fail("asked without a key"))
    assert stays().status == liteapi.OFF and flights().status == liteapi.OFF and liteapi.mode() == "off"
    monkeypatch.setenv("LITEAPI_KEY", "sand_x")
    assert liteapi.mode() == "sandbox"
    monkeypatch.setenv("LITEAPI_KEY", "prod_x")
    assert liteapi.mode() == "live"


def test_answers_are_kept_and_know_their_age(fake, monkeypatch):
    t0 = datetime(2026, 11, 12, 20, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(liteapi, "now", lambda: t0)
    first = stays()
    monkeypatch.setattr(liteapi, "now", lambda: t0 + timedelta(minutes=10))
    again = stays()
    assert len(fake.asked) == 1 and again.items == first.items and again.age() == timedelta(minutes=10)
    flights()
    monkeypatch.setattr(liteapi, "now", lambda: t0 + liteapi.STAY_KEEP + timedelta(seconds=1))
    stays()
    flights()                                                      # flights are kept longer than stays
    assert [u for u, _, _ in fake.asked].count("https://api.liteapi.travel/v3.0/hotels/rates") == 2
    assert [u for u, _, _ in fake.asked].count("https://api.liteapi.travel/v3.0/flights/rates") == 1
    assert liteapi.STAY_KEEP < liteapi.FLIGHT_KEEP
    stays(adults=3)                                                # another party is another search
    assert len(fake.asked) == 4


def test_a_family_over_its_daily_budget_is_told_so(fake, monkeypatch):
    monkeypatch.setattr(liteapi, "PER_FAMILY_A_DAY", 2)
    assert stays(family="t1").status == liteapi.OK
    assert stays(family="t1", adults=3).status == liteapi.OK
    over = stays(family="t1", adults=4)
    assert over.status == liteapi.OVER and over.items == () and len(fake.asked) == 2
    assert stays(family="t1").status == liteapi.OK                 # a kept answer costs nothing
    assert stays(family="t2", adults=4).status == liteapi.OK       # another family has its own
    assert liteapi.searches_today() == 3


def test_the_site_has_a_daily_budget_too(fake, monkeypatch):
    monkeypatch.setattr(liteapi, "A_DAY", 2)
    assert flights(family="a").status == liteapi.OK and flights(family="b", adults=1).status == liteapi.OK
    assert flights(family="c", adults=3).status == liteapi.OVER and len(fake.asked) == 2


def test_a_failure_is_failed_said_once_without_the_key_and_kept_briefly(monkeypatch, caplog):
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    f = Fake(status=400, body=raw("error_400.json"))
    monkeypatch.setattr(liteapi, "TRANSPORT", f)
    with caplog.at_level(logging.WARNING, logger="gitaway.liteapi"):
        assert stays().status == liteapi.FAILED
        assert stays().status == liteapi.FAILED
    assert len(f.asked) == 1 and len(caplog.records) == 1 and KEY not in caplog.text and "400" in caplog.text

    def boom(url, headers, body, timeout):
        raise OSError(f"refused with {headers['X-API-Key']}")
    monkeypatch.setattr(liteapi, "TRANSPORT", boom)
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="gitaway.liteapi"):
        assert flights().status == liteapi.FAILED
    assert KEY not in caplog.text and len(caplog.records) == 1


def test_a_200_with_an_error_or_too_big_is_a_failure(monkeypatch):
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    monkeypatch.setattr(liteapi, "TRANSPORT", Fake(body=raw("error_400.json")))
    assert stays().status == liteapi.FAILED
    liteapi.clear()
    monkeypatch.setattr(liteapi, "MAX_BYTES", 1000)
    monkeypatch.setattr(liteapi, "TRANSPORT", Fake())
    assert stays().status == liteapi.FAILED


def test_the_hotels_own_words_come_stripped_and_kept(fake):
    got = liteapi.about("lp1f5cb")
    assert got.startswith("Beachfront Luxury at Pacific Terrace Hotel") and "<" not in got
    assert liteapi.about("lp1f5cb") == got and len(fake.asked) == 1
    assert fake.asked[0][0] == "https://api.liteapi.travel/v3.0/data/hotel?hotelId=lp1f5cb" and fake.asked[0][2] is None


def test_the_tests_never_reach_liteapi():
    """conftest refuses the network and unsets the key, like the other sources."""
    with pytest.raises(OSError):
        liteapi.TRANSPORT("https://api.liteapi.travel/v3.0/hotels/rates", {}, b"{}", 1)
    assert liteapi.mode() == "off"
