"""F-251: the widget rail. Every widget has one real source or is not drawn; Uber, traffic and what is on are the showcase's made-up samples, labelled Sample, and not drawn off it.
The pieces are plain functions (gitaway/v2rail.py); the route draws them (gitaway/pages/v2rail.py)."""
from datetime import datetime, timezone
from html import unescape

from gitaway import geo, tripmatrix as tm, v2rail
from gitaway.pages import tripmatrix as page
from tests.test_plan_widgets import Router
from tests.test_tripmatrix_page import MATRIX, real, sample  # noqa: F401 (fixtures)

RAIL = "/plan/matrix/rail?" + MATRIX.split("?")[1] + "&lane=sandiego&w=2026-12-12"


def test_the_distance_from_home_is_a_straight_line_between_two_airports_we_have_coordinates_for():
    assert 440 <= v2rail.miles("SFO", "SAN") <= 455 and v2rail.miles("SFO", "SFO") is None and v2rail.miles("SFO", "ZZZ") is None and v2rail.miles("", "SAN") is None


def _square(lane, w, flight, stay=100_000):
    f = tm.FlightPart("Air", "o", "b", 0, flight)
    return tm.Square(lane.key, w.key, tm.OK, f, (tm.StayPart(lane.places[0].name, 4, "Inn", "r", "room only", True, 0, "", "", stay),), 10, datetime.now(timezone.utc), False, (f,), ())


def _lanes():
    s = page.state("San Diego", "SFO", "2026-12-12", "2026-12-16", "2", "7,10", "2")
    return s, page.lanes_of(s), page.windows_of(s)


def test_a_cheaper_airport_is_another_airport_whose_known_flights_cost_less_and_nothing_else():
    s, lanes, windows = _lanes()
    w = next(x for x in windows if x.asked)
    by = {"sandiego": _square(lanes[0], w, 60_000), "losangeles": _square(lanes[1], w, 52_000, 120_000), "orangecounty": _square(lanes[2], w, 41_000, 90_000)}
    known = lambda ln, win: by.get(ln.key)      # noqa: E731
    got = v2rail.cheaper_airport(s, lanes[0], w, lanes, known)
    assert (got.iata, got.place, got.base_iata, got.save_cents, got.trip_cents, got.lane) == ("SNA", "Orange County", "SAN", 19_000, 131_000 - 160_000, "orangecounty")      # the biggest saving wins
    assert v2rail.cheaper_airport(s, lanes[2], w, lanes, known) is None                 # the cheapest airport has none cheaper
    assert v2rail.cheaper_airport(s, lanes[0], w, lanes, lambda ln, win: None) is None      # nothing known, nothing said
    dearer = {**by, "orangecounty": _square(lanes[2], w, 70_000), "losangeles": _square(lanes[1], w, 60_000)}
    assert v2rail.cheaper_airport(s, lanes[0], w, lanes, lambda ln, win: dearer.get(ln.key)) is None      # same price or dearer is not cheaper


def test_breakfast_hotels_are_the_sources_own_board_each_once():
    rooms = (tm.RoomPart("Std", "room only", True, 0, 100), tm.RoomPart("Dlx", "breakfast", True, 0, 130))
    a, b = (tm.StayPart("SD", 4, n, "Std", "room only", True, 0, "", "", 100, rooms=rooms) for n in ("A", "B"))
    f = tm.FlightPart("Air", "o", "b", 0, 1)
    sq = tm.Square("k", "w", tm.OK, f, (a,), None, None, False, (f,), ((a, b), ))
    assert [(st.name, r.room) for st, r in v2rail.breakfast(sq)] == [("A", "Dlx"), ("B", "Dlx")]
    plain = tm.Square("k", "w", tm.OK, f, (tm.StayPart("SD", 4, "C", "Std", "room only", True, 0, "", "", 100),), None, None, False, (f,), ())
    assert v2rail.breakfast(plain) == []


def test_the_samples_that_fit_what_the_family_is_into():
    food = v2rail.SAMPLE["San Diego"]["food"]
    assert [f[0] for f in v2rail.fits(food, ("seafood",))] == ["Harbor Fish Shack"]
    assert [f[0] for f in v2rail.fits(food, ())] == [food[0][0], food[1][0], food[2][0]]      # nothing picked: the first few
    assert [f[0] for f in v2rail.fits(food, ("hikes",))] == [food[0][0], food[1][0], food[2][0]]      # nothing fits: the first few


def test_on_the_showcase_the_rail_has_the_real_widgets_and_the_made_up_ones_say_sample(sample, client):
    j = client.get(RAIL).json()
    html = unescape(j["html"])
    assert j["lane"] == "sandiego" and "Around San Diego" in html and "Weather" in html and "Typical mid December · not a forecast yet." in html and html.count('class="d5 is-typ') == 5
    assert "Where you will be" in html and "in a straight line" in html and "Schematic" not in html      # no router in tests: no drive, so no map and no minutes
    assert "Uber to the hotel" in html and "Traffic when you land" in html and "Happening that week" in html and html.count('class="smp"') >= 4
    assert "About San Diego" in html and "Source" in html and "Show all 4" in html
    assert "Masala Coast" in html and "Food that fits you" in html
    assert "live traffic" not in html or "No live traffic" in html


def test_off_the_showcase_the_made_up_widgets_are_not_drawn(real, client):
    html = unescape(client.get(RAIL).json()["html"])
    assert "Weather" in html and "About San Diego" in html and "Where you will be" in html
    for made_up in ("Uber", "Traffic when you land", "Happening that week", "Sample", "Masala Coast"):
        assert made_up not in html, made_up


def test_the_rail_for_a_place_with_nothing_to_say_is_just_its_head(sample, client):
    j = client.get("/plan/matrix/rail?" + MATRIX.split("?")[1] + "&lane=orangecounty&w=2026-12-12").json()
    html = unescape(j["html"])
    assert "Around Orange County" in html and "Uber to the hotel" in html and "About Orange County" in html


def test_a_rail_for_a_bad_address_is_a_400_and_an_unknown_lane_falls_back_to_the_asked_place(sample, client):
    assert client.get("/plan/matrix/rail?to=Boise&home=SFO&d=2026-12-12&r=2026-12-16").status_code == 400
    assert client.get("/plan/matrix/rail?" + MATRIX.split("?")[1] + "&lane=nowhere&w=nope").json()["lane"] == "sandiego"


def test_the_drives_are_the_routers_own_times_the_airport_run_and_the_stay_to_the_asked_place(sample, client, monkeypatch):
    router = Router(3900)      # 65 minutes whatever is asked
    monkeypatch.setattr(geo, "fetch", router)
    html = unescape(client.get("/plan/matrix/rail?" + MATRIX.split("?")[1] + "&lane=orangecounty&w=2026-12-12").json()["html"])
    assert "SNA airport → Newport Beach" in html and "Newport Beach → San Diego" in html and html.count("65 min") >= 3      # two rows and the map's two labels
    assert "Schematic, not to scale" in html and "No live traffic" in html
    asked = len(router.urls)
    client.get("/plan/matrix/rail?" + MATRIX.split("?")[1] + "&lane=orangecounty&w=2026-12-12")
    assert len(router.urls) == asked      # kept: each drive is asked once
