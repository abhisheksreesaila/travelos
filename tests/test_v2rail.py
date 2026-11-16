"""F-251: the widget rail. Every widget has one real source or is not drawn; Uber, traffic and what is on are the showcase's made-up samples, labelled Sample, and not drawn off it.
The pieces are plain functions (gitaway/v2rail.py); the route draws them (gitaway/pages/v2rail.py)."""
import re
from datetime import datetime, timezone
from html import unescape

from gitaway import airportdrive, geo, interests, tripmatrix as tm, v2rail
from gitaway.pages import tripmatrix as page
from tests.geo_support import Router
from tests.test_signin import person, sign_in
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


def _card(client, name, lane="sandiego", url=None):
    """One chip's card: asked the way a tap asks it (F-277, D-870)."""
    got = client.get((url or RAIL.replace("lane=sandiego", f"lane={lane}")) + f"&wg={name}")
    return unescape(got.json()["card"]) if got.status_code == 200 else got.status_code


def test_on_the_showcase_the_rail_is_chips_and_each_card_is_asked_for_when_tapped(sample, client):
    j = client.get(RAIL).json()
    html = unescape(j["html"])
    assert j["lane"] == "sandiego" and "Around San Diego" in html and "Extra info · tap any" in html and "New: tap for weather, drive times, guides…" in html
    assert 'class="wg ' not in html and 'class="d5' not in html and "in a straight line" not in html      # chips only: no card is built until a chip is tapped
    assert html.count('class="wchip v2-glass"') == 8      # weather, where, uber, traffic, food, trend, about, guides
    names = re.findall(r'data-wg="([^"]*)"', html)
    assert names == ["guides", "weather", "where", "uber", "traffic", "food", "trend", "about"]      # a chip is named for its widget (a loop variable once renamed the food chip after a restaurant)
    weather = _card(client, "weather")
    assert "Weather" in weather and "Typical mid December · not a forecast yet." in weather and weather.count('class="d5 is-typ') == 5
    where = _card(client, "where")
    assert "Where you will be" in where and "in a straight line" in where and "Schematic" not in where      # no router in tests: no drive, so no map and no minutes
    assert "Uber to the hotel" in _card(client, "uber") and "Traffic when you land" in _card(client, "traffic") and "Happening that week" in _card(client, "trend")
    assert _card(client, "uber").count('class="smp"') == 1
    about = _card(client, "about")
    assert "About San Diego" in about and "Source" in about and "Show all 4" in about
    assert "Masala Coast" in _card(client, "food") and "Food that fits you" in _card(client, "food")


def test_off_the_showcase_the_made_up_widgets_are_not_drawn(real, client):
    html = unescape(client.get(RAIL).json()["html"])
    assert 'data-wg="weather"' in html and 'data-wg="about"' in html and 'data-wg="where"' in html
    for made_up in ("Uber", "Traffic when you land", "Happening that week", "Sample", "Masala Coast"):
        assert made_up not in html, made_up
    assert "Nothing known for this yet." in _card(client, "uber") and "UberX" not in _card(client, "uber")      # asked for by name anyway: never the sample


def test_a_chip_costs_nothing_until_it_is_tapped(sample, client, monkeypatch):
    """F-277: the row asks no weather and no drive; the tap asks one widget's data once."""
    from gitaway import weather
    calls = []
    monkeypatch.setattr(v2rail, "sky", lambda *a, **k: calls.append("sky") or weather.TripWeather((None,), "", "", None, False))
    monkeypatch.setattr(airportdrive, "drive", lambda *a, **k: calls.append("drive") or None)
    monkeypatch.setattr(airportdrive, "between", lambda *a, **k: calls.append("between") or None)
    monkeypatch.setattr(weather, "forecast", lambda *a, **k: calls.append("forecast") or None)
    sign_in(client)
    for lane in ("sandiego", "orangecounty"):
        html = unescape(client.get(RAIL.replace("lane=sandiego", f"lane={lane}")).json()["html"])
        assert 'data-wg="weather"' in html and 'data-wg="where"' in html
    assert calls == []
    _card(client, "weather")
    assert calls == ["sky"]
    _card(client, "where", "orangecounty")
    assert calls == ["sky", "drive", "between"]


def test_a_card_for_no_widget_is_a_404(sample, client):
    assert _card(client, "nonsense") == 404


def test_the_rail_for_a_place_with_nothing_to_say_is_just_its_head(sample, client):
    j = client.get("/plan/matrix/rail?" + MATRIX.split("?")[1] + "&lane=orangecounty&w=2026-12-12").json()
    html = unescape(j["html"])
    assert "Around Orange County" in html and 'data-wg="uber"' in html and 'data-wg="about"' in html


def test_a_rail_for_a_bad_address_is_a_400_and_an_unknown_lane_falls_back_to_the_asked_place(sample, client):
    assert client.get("/plan/matrix/rail?to=Boise&home=SFO&d=2026-12-12&r=2026-12-16").status_code == 400
    assert client.get("/plan/matrix/rail?" + MATRIX.split("?")[1] + "&lane=nowhere&w=nope").json()["lane"] == "sandiego"


def test_the_drives_are_the_routers_own_times_the_airport_run_and_the_stay_to_the_asked_place(sample, client, monkeypatch):
    sign_in(client)
    router = Router(3900)      # 65 minutes whatever is asked
    monkeypatch.setattr(geo, "fetch", router)
    html = _card(client, "where", "orangecounty")
    assert "SNA airport → Newport Beach" in html and "Newport Beach → San Diego" in html and html.count("65 min") >= 3      # two rows and the map's two labels
    assert "Schematic, not to scale" in html and "No live traffic" in html
    asked = len(router.urls)
    _card(client, "where", "orangecounty")
    assert len(router.urls) == asked      # kept: each drive is asked once


def test_a_stranger_is_shown_only_the_drives_already_kept_and_the_router_is_not_asked(sample, client, monkeypatch):
    """L-1: the open rail route must not spend the router's budget for anyone. A signed-in person asks (and it is kept); a stranger is then served that kept answer."""
    router = Router(3900)
    monkeypatch.setattr(geo, "fetch", router)
    url = "/plan/matrix/rail?" + MATRIX.split("?")[1] + "&lane=orangecounty&w=2026-12-12&wg=where"
    cold = unescape(client.get(url).json()["card"])
    assert router.urls == [] and "min" not in cold.split("Where you will be")[1].split("</section>")[0].replace("in a straight line", "")
    sign_in(client)
    assert "SNA airport → Newport Beach" in unescape(client.get(url).json()["card"]) and router.urls
    asked = len(router.urls)
    from tests.test_members import browser
    stranger = browser(client)
    warm = unescape(stranger.get(url).json()["card"])
    assert len(router.urls) == asked and "SNA airport → Newport Beach" in warm and "65 min" in warm


def test_a_signed_out_rail_has_no_family_data(sample, client):
    """The family's picked interests are not read for a stranger: Cafes brings Bean & Wave to a signed-in rail, never to a signed-out one."""
    url = RAIL + "&wg=food"
    assert "Bean & Wave" not in unescape(client.get(url).json()["card"])
    sign_in(client)
    interests.save(person(), ["cafes"])
    assert "Bean & Wave" in unescape(client.get(url).json()["card"])
    from tests.test_members import browser
    assert "Bean & Wave" not in unescape(browser(client).get(url).json()["card"])


def test_a_town_that_did_not_geocode_is_not_asked_again_until_fail_wait_has_passed(monkeypatch):
    """L-1: between() keeps a failed geocode, as drive() does, so a nonsense town cannot cost a geocode on every request."""
    calls = []
    monkeypatch.setattr(geo, "find", lambda *a, **k: calls.append(a) or (geo.MISSING, None))
    assert airportdrive.between("Nowhereville, Mars", "San Diego, California") is None
    assert len(calls) == 2      # the two towns looked up once
    assert airportdrive.between("Nowhereville, Mars", "San Diego, California") is None and len(calls) == 2      # then kept, not asked again
