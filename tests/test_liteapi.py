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


def test_an_answer_in_a_shape_we_never_saw_is_a_failure_not_a_crash(monkeypatch):
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    odd = {"data": [{"hotelId": "x", "roomTypes": ["not an object"],
                     "journeys": [{"segments": [{"direction": "out"}], "offers": [{"offerId": "o"}]}]}], "hotels": [{"id": "x"}]}
    f = Fake(body=json.dumps(odd).encode())
    monkeypatch.setattr(liteapi, "TRANSPORT", f)
    assert stays().status == liteapi.FAILED
    assert flights().status == liteapi.FAILED
    assert stays().status == liteapi.FAILED and len(f.asked) == 2      # kept briefly: a retry spends no budget


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


def test_admin_says_which_liteapi_and_how_many_searches_today(client, monkeypatch, fake):
    from tests.test_signin import sign_in
    monkeypatch.setenv("GITAWAY_ADMIN_EMAILS", "ari.rivera@example.com")
    sign_in(client, "ari")
    stays()
    flights()
    stays()                                                        # kept: not a search
    html = client.get("/admin").text
    assert '<span class="ad-k">LiteAPI</span>' in html and '>sandbox · 2 searches today</span>' in html and KEY not in html
    monkeypatch.delenv("LITEAPI_KEY")
    assert ">off · 2 searches today</span>" in client.get("/admin").text


# --- the trip grid's seam (gitaway/gridsource.py)

def grid_trip(home="SFO"):
    from gitaway import catalog
    return catalog.parse_trip(home, "sd", "2026-12-12", "2026-12-16", "2", "7,10")


def test_off_the_showcase_the_grid_reads_liteapi(fake, monkeypatch):
    from gitaway import gridsource
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    found = gridsource.offers(grid_trip(), family="t1")
    assert found.sample is False and found.problem == "" and found.checked is not None
    legs = {(u, b["legs"][0]["origin"], b["legs"][0]["destination"]) if b and "legs" in b else (u, b and b.get("cityName")) for u, _, b in fake.asked}
    assert legs == {("https://api.liteapi.travel/v3.0/flights/rates", "SFO", "SAN"), ("https://api.liteapi.travel/v3.0/hotels/rates", "San Diego")}
    f = found.flights[0]
    assert (f.name, f.airport, f.depart_min, f.arrive_min, f.stops, f.cents, f.stops_text, f.overnight) == ("Frontier Airlines 3382", "SAN", 16 * 60 + 33, 18 * 60 + 16, 0, 11484, "Nonstop", False)
    assert [x.stops_text for x in found.flights].count("1 stop") >= 1
    s = found.stays[0]
    assert s.name and s.cents == 59694 + 16000                    # the resort fee paid at the hotel is part of the whole trip, and the room says so
    assert "Room only" in s.detail and "$160 of it paid at the hotel" in s.detail and s.rating
    assert found.drive_min(f, s) is None and found.book(f) == ()   # no drive is guessed; booking opens later (F-222)
    assert liteapi.searches_today() == 2


def test_every_price_in_a_square_came_from_liteapi(fake, monkeypatch):
    from gitaway import gridsource
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    found = gridsource.offers(grid_trip())
    real_f = {x.cents for x in liteapi.read_flights(answer("flight_rates.json"), datetime.now(timezone.utc))}
    real_s = {x.cents + x.due_at_stay_cents for x in liteapi.read_stays(answer("hotel_rates.json"), datetime.now(timezone.utc))}
    assert {f.cents for f in found.flights} <= real_f and {s.cents for s in found.stays} <= real_s


def test_with_no_key_or_no_home_airport_the_grid_has_nothing(monkeypatch):
    from gitaway import gridsource
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    assert gridsource.offers(grid_trip()) is None                 # no key
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    f = Fake()
    monkeypatch.setattr(liteapi, "TRANSPORT", f)
    assert gridsource.offers(grid_trip(home="")) is None and f.asked == []      # flying from the sample's San Francisco would be invented


def test_on_the_showcase_the_grid_keeps_the_sample_even_with_a_key(fake, monkeypatch):
    from gitaway import gridsource
    monkeypatch.setenv("GITAWAY_SHOWCASE", "1")
    assert gridsource.offers(grid_trip()).sample is True and fake.asked == []


def test_over_budget_or_a_failure_is_said_not_shown_as_an_empty_grid(fake, monkeypatch):
    from gitaway import gridsource
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setattr(liteapi, "A_DAY", 0)
    found = gridsource.offers(grid_trip())
    assert found.flights == () and found.stays == () and "searches" in found.problem
    monkeypatch.setattr(liteapi, "A_DAY", 100)
    monkeypatch.setattr(liteapi, "TRANSPORT", Fake(status=503, body=b"{}"))
    found = gridsource.offers(grid_trip())
    assert found.flights == () and "did not come back" in found.problem


def test_the_grid_page_says_the_problem(client, monkeypatch):
    from gitaway import gridsource
    monkeypatch.setenv("GITAWAY_SHOWCASE", "1")
    monkeypatch.setattr(gridsource, "SOURCE", lambda trip, family="": gridsource.Found((), (), lambda f, s: None, lambda i: (), False, problem=gridsource.SPENT))
    r = client.get("/plan/grid?to=sd&d=2026-12-12&r=2026-12-16&a=2&home=SFO")
    assert r.status_code == 200 and gridsource.SPENT in r.text and "tg-scroll" not in r.text


def test_nothing_found_is_said_too(monkeypatch):
    from gitaway import gridsource
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    monkeypatch.setattr(liteapi, "TRANSPORT", Fake(body=json.dumps({"data": [], "hotels": []}).encode()))
    found = gridsource.offers(grid_trip())
    assert found.flights == () and found.stays == () and found.problem == gridsource.NONE


# --- F-229: one gate, one call for the same search, flights through the stream

import threading      # noqa: E402
import time           # noqa: E402

STREAM = raw("flight_rates_stream.sse")
TIMES = json.loads(raw("flight_rates_stream.times.json"))


def messages(sse: bytes) -> list:
    """The recorded stream as its messages, each a list of byte lines ending in the blank line."""
    out, msg = [], []
    for line in sse.split(b"\n"):
        msg.append(line + b"\n")
        if not line and len(msg) > 1:
            out.append(msg)
            msg = []
    return out


class Streamer:
    """A TRANSPORT that plays the recorded stream back, each message at `scale` times its recorded arrival time (no `rates-complete` when `complete` is False)."""

    def __init__(self, scale=0.0, complete=True, head_s=0.0, sse=STREAM):
        self.scale, self.complete, self.head_s, self.sse, self.asked, self.cut = scale, complete, head_s, sse, [], threading.Event()

    def __call__(self, url, headers, body, timeout):
        self.asked.append((url, headers, json.loads(body) if body else None))
        if "/hotels/rates" in url:
            return 200, "application/json", raw("hotel_rates.json")
        time.sleep(self.head_s)
        return 200, "text/event-stream", Lines(self)


class Lines:
    def __init__(self, s):
        self.s, self.t0 = s, time.monotonic()

    def __iter__(self):
        for msg, t in zip(messages(self.s.sse), TIMES):
            if t["event"] == "rates-complete" and not self.s.complete:
                break
            while time.monotonic() - self.t0 < t["at"] * self.s.scale:
                if self.s.cut.is_set():
                    return
                time.sleep(0.005)
            yield from msg
        while not self.s.complete and not self.s.cut.is_set():      # the sandbox sometimes never says rates-complete: the line stays open
            time.sleep(0.005)

    def cut(self):
        self.s.cut.set()


def test_the_stream_was_recorded_from_the_sandbox_with_chunks_then_complete():
    events = [m[0].decode().strip() for m in messages(STREAM)]
    assert events == ["event: rates-chunk"] * 6 + ["event: rates-complete"] and [t["event"] for t in TIMES] == [e[7:] for e in events]
    first = json.loads(messages(STREAM)[1][1][6:])
    assert set(first["data"][0]) >= {"journeys", "searchId"}                  # a chunk is shaped like the plain answer


def test_flights_ask_for_the_stream_and_only_the_cheapest_offer(monkeypatch):
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    s = Streamer()
    monkeypatch.setattr(liteapi, "TRANSPORT", s)
    got = flights()
    url, headers, body = s.asked[0]
    assert headers["Accept"] == "text/event-stream" and body["filters"] == {"showCheapestOfferOnly": True}
    assert got.ok and got.complete
    assert got.items[0].cents == 7660 and got.items[0].airline == "Alaska Airlines"   # the cheapest seen in any chunk
    ids = [f.id for f in got.items]
    assert len(ids) == len(set(ids))                                             # a journey sent in several chunks is one flight, at its cheapest
    assert next(f for f in got.items if f.id == "0066a9a93554c975").cents == 13484


def test_a_stream_that_never_completes_stops_a_while_after_the_first_real_chunk(monkeypatch):
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    monkeypatch.setattr(liteapi, "STREAM_GRACE", 0.3)
    monkeypatch.setattr(liteapi, "STREAM_CAP", 3.0)
    monkeypatch.setattr(liteapi, "BULK", 2)          # the recording keeps 2 or 3 journeys of each chunk's hundreds; the lone test-airline chunk has 1
    s = Streamer(scale=0.1, complete=False)          # the bulk at 0.57 s, the cheapest at 0.99 s: past the grace
    monkeypatch.setattr(liteapi, "TRANSPORT", s)
    t0 = time.monotonic()
    got = flights()
    took = time.monotonic() - t0
    assert got.ok and not got.complete and 0.8 <= took < 1.5, took
    assert got.items[0].cents == 13484                                           # what came by then: the cheapest found, said as such
    assert s.cut.is_set()                                                        # the line is cut, not left open


def test_a_lone_test_airline_chunk_does_not_start_the_grace(monkeypatch):
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    monkeypatch.setattr(liteapi, "STREAM_GRACE", 0.3)
    monkeypatch.setattr(liteapi, "STREAM_CAP", 3.0)
    monkeypatch.setattr(liteapi, "BULK", 2)
    head = b"".join(messages(STREAM)[0])          # the one Nuitee Air journey the sandbox sends at once
    monkeypatch.setattr(liteapi, "TRANSPORT", Streamer(scale=0.1, complete=False, sse=head))
    t0 = time.monotonic()
    got = flights()
    assert time.monotonic() - t0 >= 2.9 and got.ok and got.items[0].airline == "Nuitée Air"      # the cap, then the one found


def test_a_stream_with_nothing_by_the_cap_fails_honestly(monkeypatch, caplog):
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    monkeypatch.setattr(liteapi, "STREAM_CAP", 0.4)
    s = Streamer(head_s=0.0, complete=False, sse=b"")
    monkeypatch.setattr(liteapi, "TRANSPORT", s)
    t0 = time.monotonic()
    with caplog.at_level(logging.WARNING, logger="gitaway.liteapi"):
        got = flights()
    assert got.status == liteapi.FAILED and time.monotonic() - t0 < 1.0 and KEY not in caplog.text and s.cut.is_set()


def test_a_transport_that_hangs_before_answering_is_cut_at_the_cap(monkeypatch):
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    monkeypatch.setattr(liteapi, "STREAM_CAP", 0.3)
    monkeypatch.setattr(liteapi, "TRANSPORT", Streamer(head_s=2.0))
    t0 = time.monotonic()
    assert flights().status == liteapi.FAILED and time.monotonic() - t0 < 1.0


@pytest.mark.parametrize("bad", [b"event: rates-chunk\ndata: {not json\n\n", b'event: rates-chunk\ndata: {"data": "x"}\n\n',
                                 b'event: error\ndata: {"error": {"code": 51099}}\n\n',
                                 b'event: rates-chunk\ndata: {"data": [{"journeys": [{"segments": [{"direction": 1}], "offers": "x"}]}]}\n\n'])
def test_a_stream_in_a_shape_we_never_saw_is_a_failure_not_a_crash(monkeypatch, bad):
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    monkeypatch.setattr(liteapi, "STREAM_CAP", 0.5)
    monkeypatch.setattr(liteapi, "TRANSPORT", Streamer(sse=bad, complete=False))
    assert flights().status == liteapi.FAILED


def test_a_stream_too_big_is_a_failure(monkeypatch):
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    monkeypatch.setattr(liteapi, "MAX_BYTES", 20_000)
    monkeypatch.setattr(liteapi, "TRANSPORT", Streamer())
    assert flights().status == liteapi.FAILED


class Slow:
    """A TRANSPORT that takes `s` seconds and counts how many calls are in flight at once."""

    def __init__(self, s=0.2):
        self.s, self.now, self.most, self.calls, self.lock = s, 0, 0, 0, threading.Lock()

    def __call__(self, url, headers, body, timeout):
        with self.lock:
            self.now += 1
            self.calls += 1
            self.most = max(self.most, self.now)
        time.sleep(self.s)
        with self.lock:
            self.now -= 1
        return 200, "application/json", raw("hotel_rates.json" if "/hotels/" in url else "flight_rates.json")


def together(*calls):
    out = [None] * len(calls)
    threads = [threading.Thread(target=lambda i=i, c=c: out.__setitem__(i, c())) for i, c in enumerate(calls)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
    return out


def test_at_most_three_calls_are_in_flight_site_wide(monkeypatch):
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    slow = Slow()
    monkeypatch.setattr(liteapi, "TRANSPORT", slow)
    got = together(*[lambda a=a: stays(adults=a) for a in range(1, 8)], lambda: flights(), lambda: liteapi.about("lp1f5cb"))
    assert liteapi.AT_ONCE == 3 and slow.most == 3 and slow.calls == 9
    assert all(g.ok for g in got[:8])


def test_the_same_search_in_flight_is_joined_not_asked_twice(monkeypatch):
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    slow = Slow(0.3)
    monkeypatch.setattr(liteapi, "TRANSPORT", slow)
    got = together(*[lambda: stays(family="t1")] * 4, lambda: stays(family="t2"))
    assert slow.calls == 1 and all(g.ok for g in got) and len({g.items for g in got}) == 1
    assert liteapi.searches_today() == 1                                         # one call, one search counted


def test_a_joiner_whose_first_asker_was_over_budget_asks_on_its_own(monkeypatch):
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    slow = Slow(0.2)
    monkeypatch.setattr(liteapi, "TRANSPORT", slow)
    real_spend = liteapi._spend
    monkeypatch.setattr(liteapi, "can_search", lambda family: (time.sleep(0.1), family != "broke")[1])      # the first asker is still deciding when the second joins
    got = together(lambda: stays(family="broke"), lambda: (time.sleep(0.02), stays(family="rich"))[1])
    assert got[0].status == liteapi.OVER and got[1].ok and slow.calls == 1
    monkeypatch.setattr(liteapi, "_spend", real_spend)


def test_the_budget_says_whether_a_family_can_still_search(fake, monkeypatch):
    monkeypatch.setattr(liteapi, "PER_FAMILY_A_DAY", 1)
    assert liteapi.can_search("t1")
    stays(family="t1")
    assert not liteapi.can_search("t1") and liteapi.can_search("t2")


def test_the_gate_lets_the_most_wanted_call_through_first(monkeypatch):
    """A call carries its square's rank (0: the asked square): when a place comes free, the lowest rank waiting goes next, whatever came first."""
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    order, lock = [], threading.Lock()

    def note(url, headers, body, timeout):
        with lock:
            order.append(json.loads(body)["occupancies"][0]["adults"])
        time.sleep(0.15)
        return 200, "application/json", raw("hotel_rates.json")
    monkeypatch.setattr(liteapi, "TRANSPORT", note)
    threads = []
    for adults, rank in ((1, 50), (2, 50), (3, 50), (4, 40), (5, 30), (6, 0), (7, 20)):      # the first three take the gate; the rest wait
        threads.append(threading.Thread(target=lambda a=adults, r=rank: stays(adults=a, rank=r)))
        threads[-1].start()
        time.sleep(0.02)
    for t in threads:
        t.join(10)
    assert order[:3] == [1, 2, 3] and order[3:] == [6, 7, 5, 4]


def test_a_joiner_lends_its_rank_to_the_search_it_joined(monkeypatch):
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    order, lock = [], threading.Lock()

    def note(url, headers, body, timeout):
        with lock:
            order.append(json.loads(body)["occupancies"][0]["adults"])
        time.sleep(0.15)
        return 200, "application/json", raw("hotel_rates.json")
    monkeypatch.setattr(liteapi, "TRANSPORT", note)
    plan = ((1, 50), (2, 50), (3, 50), (4, 40), (5, 90), (5, 0))      # 5 is queued last, then the asked square wants it too
    threads = []
    for adults, rank in plan:
        threads.append(threading.Thread(target=lambda a=adults, r=rank: stays(adults=a, rank=r)))
        threads[-1].start()
        time.sleep(0.02)
    for t in threads:
        t.join(10)
    assert order == [1, 2, 3, 5, 4]


def test_no_turn_at_the_gate_is_busy_and_not_kept(monkeypatch):
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    monkeypatch.setattr(liteapi, "GATE_WAIT", 0.1)
    slow = Slow(0.5)
    monkeypatch.setattr(liteapi, "TRANSPORT", slow)
    got = together(*[lambda a=a: stays(adults=a) for a in range(1, 5)])
    assert sorted(g.status for g in got) == [liteapi.BUSY] + [liteapi.OK] * 3 and liteapi.searches_today() == 3
    late = next(a for a, g in zip(range(1, 5), got) if g.status == liteapi.BUSY)
    assert stays(adults=late).ok                                                 # asked again, it searches: the wait was not the answer


# --- the review's fixes: no request waits long at the gate; a stream keeps its place until it is done; an empty rates-complete

def test_a_family_over_its_budget_is_told_at_once_without_waiting_at_the_gate(monkeypatch):
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    monkeypatch.setattr(liteapi, "PER_FAMILY_A_DAY", 1)
    slow = Slow(0.6)
    monkeypatch.setattr(liteapi, "TRANSPORT", slow)
    assert stays(family="t1").ok
    hold = [threading.Thread(target=lambda a=a: stays(adults=a, family=f"b{a}")) for a in (3, 4, 5)]      # the gate is full
    for t in hold:
        t.start()
    time.sleep(0.05)
    t0 = time.monotonic()
    assert stays(adults=6, family="t1").status == liteapi.OVER and time.monotonic() - t0 < 0.2
    for t in hold:
        t.join(5)


def test_a_long_line_at_the_gate_is_busy_at_once_and_not_kept(monkeypatch):
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    monkeypatch.setattr(liteapi, "MAX_WAITING", 2)
    slow = Slow(0.5)
    monkeypatch.setattr(liteapi, "TRANSPORT", slow)
    threads = [threading.Thread(target=lambda a=a: stays(adults=a)) for a in range(1, 6)]      # 3 in flight, 2 waiting: the line is full
    for t in threads:
        t.start()
        time.sleep(0.02)
    t0 = time.monotonic()
    busy = stays(adults=9)
    assert busy.status == liteapi.BUSY and time.monotonic() - t0 < 0.2 and liteapi.searches_today() == 3
    for t in threads:
        t.join(5)
    assert stays(adults=9).ok                                                     # not kept: asked again, it searches


def test_a_request_waits_only_its_own_short_while_at_the_gate(monkeypatch):
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    slow = Slow(1.0)
    monkeypatch.setattr(liteapi, "TRANSPORT", slow)
    threads = [threading.Thread(target=lambda a=a: stays(adults=a)) for a in range(1, 4)]
    for t in threads:
        t.start()
    time.sleep(0.05)
    t0 = time.monotonic()
    got = stays(adults=7, wait=0.2)
    assert got.status == liteapi.BUSY and 0.15 < time.monotonic() - t0 < 0.5
    t0 = time.monotonic()
    joined = stays(adults=1, wait=0.1)                                            # joining a search in flight waits its short while, plus the call's own time at most
    assert joined.ok and time.monotonic() - t0 < 1.2
    for t in threads:
        t.join(5)
    assert liteapi.TILE_WAIT <= 15 and liteapi.GATE_WAIT >= liteapi.TILE_WAIT


def test_a_stream_keeps_its_place_at_the_gate_until_its_thread_is_done(monkeypatch):
    """Past the cap before the headers came: the gate place stays taken until the transport gives up, and the late answer is closed at once."""
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    monkeypatch.setattr(liteapi, "STREAM_CAP", 0.2)
    s = Streamer(head_s=0.8)
    monkeypatch.setattr(liteapi, "TRANSPORT", s)
    t0 = time.monotonic()
    assert flights().status == liteapi.FAILED and time.monotonic() - t0 < 0.7    # the asker is not held
    assert liteapi._TURNS.free == liteapi.AT_ONCE - 1                             # but the place is: the line is still being opened
    deadline = time.monotonic() + 3
    while liteapi._TURNS.free < liteapi.AT_ONCE and time.monotonic() < deadline:
        time.sleep(0.02)
    assert liteapi._TURNS.free == liteapi.AT_ONCE and time.monotonic() - t0 >= 0.75      # given back when the transport came back
    assert s.cut.is_set()                                                         # and what came back late was closed, not read


@pytest.mark.parametrize("tail", [b"event: rates-complete\n\n", b"event: rates-complete\ndata: {}\n\n", b"event: rates-complete\ndata: \n\n"])
def test_an_empty_rates_complete_ends_the_stream_and_keeps_what_came(monkeypatch, tail):
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    chunks = b"".join(b"".join(m) for m in messages(STREAM)[:6])
    s = Streamer(sse=chunks + tail)
    monkeypatch.setattr(liteapi, "STREAM_CAP", 3.0)
    monkeypatch.setattr(liteapi, "TRANSPORT", s)
    t0 = time.monotonic()
    got = flights()
    assert got.ok and got.complete and got.items[0].cents == 7660 and time.monotonic() - t0 < 1.0


def test_a_stay_search_asks_for_one_rate_per_hotel(fake):
    """Measured 2026-11-13: one rate a hotel is 104 KB instead of 7.8 MB, at the same price (none of 27 hotels dearer), so the search asks for one."""
    liteapi.stays(checkin=date(2026, 12, 12), checkout=date(2026, 12, 16), adults=2, kid_ages=(7, 10), city="San Diego", country="US")
    assert fake.asked[-1][2]["maxRatesPerHotel"] == 1


def test_a_connection_liteapi_drops_is_asked_once_more(monkeypatch):
    import http.client
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    f, drops = Fake(), {"n": 1}

    def flaky(url, headers, body, timeout):
        if drops["n"]:
            drops["n"] -= 1
            raise http.client.RemoteDisconnected("Remote end closed connection without response")
        return f(url, headers, body, timeout)
    monkeypatch.setattr(liteapi, "TRANSPORT", flaky)
    got = liteapi.stays(checkin=date(2026, 12, 12), checkout=date(2026, 12, 16), adults=2, kid_ages=(7, 10), city="San Diego", country="US")
    assert got.ok and got.items and len(f.asked) == 1


def test_a_timeout_is_not_asked_again(monkeypatch):
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    calls = []

    def slow(url, headers, body, timeout):
        calls.append(url)
        raise TimeoutError("timed out")
    monkeypatch.setattr(liteapi, "TRANSPORT", slow)
    got = liteapi.stays(checkin=date(2026, 12, 12), checkout=date(2026, 12, 16), adults=2, kid_ages=(7, 10), city="San Diego", country="US")
    assert not got.ok and len(calls) == 1
