"""F-222: one square of the trip matrix from its one seam (gitaway/gridsource.py `square`). On the showcase the sample catalog answers and says so; off it LiteAPI
answers, read from the recorded sandbox answers (tests/fixtures/liteapi), and nothing is invented: a spent budget, a failure or nothing found is a status said in words."""
from datetime import date, datetime, timezone

import pytest
from fasthtml.common import to_xml

from gitaway import airportdrive, catalog, gridsource, liteapi, tripmatrix as tm
from gitaway.partners import places
from tests.test_liteapi import KEY, Fake, answer

SD = places.resolve("San Diego")
LANES = {x.key: x for x in tm.lanes(SD, nearby=True)}
W = tm.Window(date(2026, 12, 12), date(2026, 12, 16), True)
PARTY = {"adults": 2, "kid_ages": (7, 10)}


def square(lane="sandiego", w=W, **over):
    return gridsource.square(LANES[lane], w, **{**PARTY, "home": "SFO", **over})


@pytest.fixture
def sample(monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "1")


@pytest.fixture
def real(monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    fake = Fake()
    monkeypatch.setattr(liteapi, "TRANSPORT", fake)
    return fake


def test_on_the_showcase_a_square_is_the_catalogs_cheapest_flight_and_stay_and_says_sample(sample):
    sq = square()
    trip = catalog.parse_trip("SFO", "sd", "2026-12-12", "2026-12-16", "2", "7,10")
    flight = min(catalog.offers("flight", trip), key=lambda o: o.price_cents)
    stay = min(catalog.offers("stay", trip), key=lambda o: o.price_cents)
    assert sq.ok and sq.sample and sq.key == "sandiego|2026-12-12"
    assert sq.flight.cents == gridsource.sample_day(flight.price_cents, W.depart) and sq.stays[0].cents == gridsource.sample_day(stay.price_cents, W.depart)
    assert sq.stays[0].name == stay.name and sq.stays[0].photo == ""          # the catalog's area photos are never shown as a hotel
    assert sq.drive and square(peek=True) == sq                              # nothing to wait for: a peek is the answer


def test_the_sample_moves_with_the_day_so_the_showcase_shows_a_cheapest_start(sample):
    totals = {d: square(w=tm.Window(date(2026, 12, d), date(2026, 12, d + 4))).cents for d in (10, 11, 12, 13, 14)}
    assert len(set(totals.values())) > 1


def test_on_the_showcase_a_place_the_catalog_lacks_has_no_sample_and_two_places_split_the_nights(sample):
    assert square("orangecounty").status == tm.NO_SAMPLE and square("orangecounty").cents is None
    both = square("losangeles+sandiego")
    assert both.ok and [(s.place, s.nights) for s in both.stays] == [("Los Angeles", 2), ("San Diego", 2)]


def test_off_the_showcase_a_square_is_liteapis_cheapest_flight_and_a_well_rated_stay(real):
    sq = square()
    at = datetime(2026, 11, 12, tzinfo=timezone.utc)
    flight = liteapi.read_flights(answer("flight_rates.json"), at)[0]
    stay = liteapi.read_stays(answer("hotel_rates.json"), at)[0]
    assert sq.ok and not sq.sample and sq.fetched
    assert sq.flight.cents == flight.cents and sq.flight.airline == flight.airline
    assert (sq.stays[0].name, sq.stays[0].cents, sq.stays[0].photo) == (stay.name, stay.cents + stay.due_at_stay_cents, stay.photo)
    assert sq.cents == flight.cents + stay.cents + stay.due_at_stay_cents
    asked = [(url.rsplit("/", 2)[-2:], body) for url, _, body in real.asked]
    flights = next(b for u, b in asked if u == ["flights", "rates"])
    assert [(leg["origin"], leg["destination"], leg["date"]) for leg in flights["legs"]] == [("SFO", "SAN", "2026-12-12"), ("SAN", "SFO", "2026-12-16")]
    hotels = next(b for u, b in asked if u == ["hotels", "rates"])
    assert (hotels["cityName"], hotels["checkin"], hotels["checkout"]) == ("San Diego", "2026-12-12", "2026-12-16")


def test_the_cheapest_stay_guests_rate_eight_or_more_wins_over_a_cheaper_poorly_rated_one(real, monkeypatch):
    stays = liteapi.read_stays(answer("hotel_rates.json"), datetime(2026, 11, 12, tzinfo=timezone.utc))
    poor = stays[0].__class__(**{**stays[0].__dict__, "id": "poor", "name": "Cheap and grim", "rating": 6.1, "cents": 10_000})
    real_stays = liteapi.stays
    monkeypatch.setattr(liteapi, "stays", lambda **kw: liteapi.Answer(liteapi.OK, (poor, *stays), stays[0].fetched) if not kw.get("cached_only") else None)
    assert square().stays[0].name == stays[0].name
    lone = liteapi.Answer(liteapi.OK, (poor,), stays[0].fetched)
    monkeypatch.setattr(liteapi, "stays", lambda **kw: lone)
    assert square().stays[0].name == "Cheap and grim"                       # no well-rated one: the cheapest, said with its rating
    monkeypatch.setattr(liteapi, "stays", real_stays)


def test_two_places_fly_in_to_the_first_and_home_from_the_second_and_search_each_stay(real):
    sq = square("losangeles+sandiego")
    assert sq.ok and [(s.place, s.nights) for s in sq.stays] == [("Los Angeles", 2), ("San Diego", 2)]
    bodies = [b for _, _, b in real.asked]
    legs = next(b["legs"] for b in bodies if "legs" in b)
    assert [(l["origin"], l["destination"]) for l in legs] == [("SFO", "LAX"), ("SAN", "SFO")]
    assert sorted((b["cityName"], b["checkin"], b["checkout"]) for b in bodies if "cityName" in b) == [
        ("Los Angeles", "2026-12-12", "2026-12-14"), ("San Diego", "2026-12-14", "2026-12-16")]


def test_a_peek_never_calls_and_only_finds_what_was_already_answered(real):
    assert square(peek=True) is None and real.asked == []
    fetched = square()
    calls = len(real.asked)
    assert square(peek=True) == fetched and len(real.asked) == calls


def test_a_spent_budget_a_failure_and_nothing_found_are_said(real, monkeypatch):
    monkeypatch.setattr(liteapi, "_spend", lambda family: False)
    assert square().status == tm.OVER and tm.SAID[tm.OVER]
    liteapi.clear()
    monkeypatch.undo()
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    monkeypatch.setattr(liteapi, "TRANSPORT", Fake(status=500, body=b"{}"))
    assert square().status == tm.FAILED
    liteapi.clear()
    monkeypatch.setattr(liteapi, "TRANSPORT", Fake(body=b'{"data": [], "hotels": []}'))
    assert square().status == tm.NONE


def test_the_drive_is_the_routers_minutes_from_the_first_airport_or_nothing(real, monkeypatch):
    asked = []
    monkeypatch.setattr(airportdrive, "drive", lambda iata, town: asked.append((iata, town)) or airportdrive.Drive(iata, town, 25))
    assert square().drive == 25 and asked == [("SAN", "San Diego, California")]
    monkeypatch.setattr(airportdrive, "drive", lambda iata, town: None)
    liteapi.clear()
    assert square().drive is None


def test_off_the_showcase_without_a_home_airport_nothing_is_searched(real):
    sq = square(home="")
    assert sq.status == tm.FAILED and real.asked == []


def test_a_flight_search_stopped_at_its_deadline_says_its_the_cheapest_found(monkeypatch, client):
    """F-229: the stream is read until it says complete or its deadline; then the square's flight is the cheapest found by then, and the panel says so."""
    from tests.test_liteapi import Streamer
    from gitaway.pages import tripmatrix as page
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    monkeypatch.setattr(liteapi, "STREAM_CAP", 0.5)
    monkeypatch.setattr(liteapi, "TRANSPORT", Streamer(complete=False))
    sq = square()
    assert sq.ok and sq.flight.complete is False
    s = page.state("San Diego", "SFO", "2026-12-12", "2026-12-16", "2", "7,10", "2")
    assert page.CHEAPEST_FOUND in to_xml(page.panel(s, LANES["sandiego"], W, sq))
    liteapi.clear()
    monkeypatch.setattr(liteapi, "TRANSPORT", Streamer())
    sq = square()
    assert sq.flight.complete is True and page.CHEAPEST_FOUND not in to_xml(page.panel(s, LANES["sandiego"], W, sq))


def test_a_busy_gate_is_said_as_busy_and_not_a_failure(real, monkeypatch):
    monkeypatch.setattr(liteapi, "stays", lambda **kw: None if kw.get("cached_only") else liteapi.Answer(liteapi.BUSY))
    sq = square()
    assert sq.status == tm.BUSY and tm.SHORT[tm.BUSY] and tm.SAID[tm.BUSY] and sq.cents is None


def test_a_tile_waits_a_short_while_and_the_head_start_longer(real, monkeypatch):
    waits = []
    monkeypatch.setattr(liteapi, "flights", lambda **kw: waits.append(kw.get("wait")) or liteapi.Answer(liteapi.FAILED))
    monkeypatch.setattr(liteapi, "stays", lambda **kw: liteapi.Answer(liteapi.FAILED))
    square(wait=liteapi.TILE_WAIT)
    square()
    assert waits == [liteapi.TILE_WAIT, None]
