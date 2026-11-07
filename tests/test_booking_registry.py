"""F-198: the partner registry. Each lane uses a paying partner when it is connected, else a plain link that says "No commission"; switching a lane is config."""

import socket
from datetime import date

import pytest

from gitaway.partners import links, places, registry, travelpayouts

TAHOE = links.Search(places.resolve("Lake Tahoe"), date(2026, 12, 19), date(2026, 12, 26), 2, (8, 11), home="SFO")
DISNEY = links.Search(places.resolve("Disneyland"), date(2027, 3, 5), date(2027, 3, 9), 2, (5, 8), home="SFO")
KEYS = ("TRAVELPAYOUTS_MARKER", "TRAVELPAYOUTS_TOKEN", "TRAVELPAYOUTS_TRS", "KLOOK_FALLBACK_URL", "PARTNER_TRACKED",
        "PARTNER_FLIGHT", "PARTNER_STAY", "PARTNER_CAR", "PARTNER_TODO")


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    travelpayouts._CACHE.clear()
    for k in KEYS:
        monkeypatch.delenv(k, raising=False)

    def refuse(*a, **k):
        raise AssertionError("the registry tried to use the network")
    monkeypatch.setattr(socket.socket, "connect", refuse)


@pytest.fixture
def connected(monkeypatch):
    monkeypatch.setenv("TRAVELPAYOUTS_MARKER", "801445")
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "tok")
    monkeypatch.setenv("TRAVELPAYOUTS_TRS", "596534")


def keys(lane, search=TAHOE):
    return [(x.site, x.paid) for x in registry.lane(lane, search)]


def test_with_no_programs_every_lane_is_a_plain_link_that_says_so():
    assert keys("flight") == [("aviasales", False)]
    assert keys("stay") == [("expedia", False), ("airbnb", False), ("vrbo", False)]
    assert keys("car") == [("expedia", False)]
    assert keys("todo") == [("getyourguide", False)]
    for lane in registry.LANES:
        for x in registry.lane(lane, TAHOE):
            assert x.note.endswith("No commission"), (lane, x)
    assert registry.lane("stay", TAHOE)[0].url == links.expedia_stay(TAHOE)


def test_lift_tickets_are_buy_direct_at_a_snow_place_only():
    direct = registry.lane("direct", TAHOE)
    assert [(x.name, x.url) for x in direct] == list(places.TAHOE_RESORTS)
    assert all(not x.paid and x.note == "Buy direct · No commission" for x in direct)
    assert registry.lane("direct", DISNEY) == []


def test_aviasales_pays_with_a_marker():
    import os
    os.environ["TRAVELPAYOUTS_MARKER"] = "801445"
    try:
        flight = registry.lane("flight", TAHOE)[0]
        assert (flight.paid, flight.note) == (True, "We may earn a commission")
        assert registry.go_url(flight, "ab12cd_laketahoe_261219_flight") == ("https://www.aviasales.com/search/SFO1912RNO261222?marker=801445.ab12cd_laketahoe_261219_flight"
                                                                               "&sub_id=ab12cd_laketahoe_261219_flight")
    finally:
        del os.environ["TRAVELPAYOUTS_MARKER"]


def test_klook_goes_first_where_it_has_the_place(connected):
    assert keys("stay", DISNEY)[0] == ("klook", True)
    assert keys("todo", DISNEY) == [("klook", True), ("getyourguide", False)]
    assert keys("stay", TAHOE)[0] == ("expedia", False)       # Klook is thin at Tahoe: the plain link takes over
    assert keys("todo", TAHOE) == [("getyourguide", False)]


def test_klook_is_not_offered_without_the_partner_links_api(monkeypatch):
    monkeypatch.setenv("TRAVELPAYOUTS_MARKER", "801445")      # a marker alone makes no tracked Klook link
    assert "klook" not in [s for s, _ in keys("stay", DISNEY)]


def test_a_klook_click_goes_through_the_partner_links_api(connected, monkeypatch):
    seen = []
    monkeypatch.setattr(travelpayouts, "_post", lambda url, headers, body, timeout: seen.append(body) or {"result": {"links": [{"code": "success", "partner_url": "https://klook.tpx.lv/t"}]}})
    todo = registry.lane("todo", DISNEY)[0]
    assert registry.go_url(todo, "s1") == "https://klook.tpx.lv/t"
    assert seen[0]["links"] == [{"url": links.KLOOK_DISNEYLAND, "sub_id": "s1"}]


def test_a_plain_link_goes_straight_to_the_site_with_nothing_added():
    stay = registry.lane("stay", TAHOE)[0]
    assert registry.go_url(stay, "s1") == links.expedia_stay(TAHOE)


def test_switching_a_lane_is_config(monkeypatch):
    monkeypatch.setenv("PARTNER_STAY", "airbnb")
    assert keys("stay") == [("airbnb", False), ("expedia", False), ("vrbo", False)]
    monkeypatch.setenv("PARTNER_STAY", "booking")       # Booking.com is listed only once chosen
    assert keys("stay")[0] == ("booking", False)
    assert registry.lane("stay", TAHOE)[0].url == links.booking_stay(TAHOE)
    monkeypatch.setenv("PARTNER_STAY", "nonsense")
    assert keys("stay")[0] == ("expedia", False)
    monkeypatch.setenv("PARTNER_TODO", "GetYourGuide ")
    assert keys("todo")[0] == ("getyourguide", False)


def test_a_newly_approved_program_is_config_not_code(connected, monkeypatch):
    """The day Booking.com approves our project: PARTNER_STAY=booking and PARTNER_TRACKED=booking, and stays pay through the same partner-links API."""
    monkeypatch.setenv("PARTNER_STAY", "booking")
    monkeypatch.setenv("PARTNER_TRACKED", "booking, expedia")
    assert keys("stay", TAHOE)[:2] == [("booking", True), ("expedia", True)]
    assert keys("car", TAHOE) == [("expedia", True)]
    monkeypatch.setattr(travelpayouts, "_post", lambda *a: (_ for _ in ()).throw(TimeoutError("timed out")))
    stay = registry.lane("stay", TAHOE)[0]
    assert registry.go_url(stay, "s1") == links.booking_stay(TAHOE)      # the API failed: the click still lands on the plain search


def test_a_flight_lane_needs_a_destination_airport():
    bend = links.Search(places.resolve("Bend, Oregon"), TAHOE.depart, TAHOE.return_, 2, ())
    assert registry.lane("flight", bend) == []
    assert keys("stay", bend)[0] == ("expedia", False)


def test_find_rebuilds_a_link_on_the_server():
    """A click names only the lane and the site; the URL is built again from the trip, never taken from the browser."""
    assert registry.find("stay", "vrbo", TAHOE).url == links.vrbo_stay(TAHOE)
    assert registry.find("stay", "klook", TAHOE) is None
    assert registry.find("direct", "resort-2", TAHOE).url == "https://www.kirkwood.com/"
    assert registry.find("nope", "vrbo", TAHOE) is None
