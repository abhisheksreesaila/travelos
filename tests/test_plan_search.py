"""F-195 (6): a reader who arrives from a creator's trip in production gets one honest card per lane, never invented offers.

The workspace's flights, stays and cars are an invented catalog (labelled "Preview: sample prices"); sending a creator's reader there made the booking path point at things that do not
exist. Through the HTTP seam; no test reaches the network.
"""

import re
import socket
from html import unescape
from urllib.parse import parse_qs, urlsplit

import pytest

from gitaway.partners import travelpayouts
from tests.live_trips import live_trip
from tests.pagebody import without_bar
from tests.test_affiliate import FakeApi, nokeys, seen_on  # noqa: F401 (the fixture)
from tests.test_signin import sign_in

TRIP = "d=2027-03-05&r=2027-03-09&a=2"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("a code path tried to use the network")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)


@pytest.fixture
def live(nokeys, monkeypatch):
    """Production with our Travelpayouts keys, and a creator whose trip the reader came from."""
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setenv("TRAVELPAYOUTS_MARKER", "801445")
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "tok")
    monkeypatch.setenv("TRAVELPAYOUTS_TRS", "596534")
    monkeypatch.setattr(travelpayouts, "_post", FakeApi())
    return live_trip()


def words(html):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", without_bar(html))))


def go_links(html):
    return [h.replace("&amp;", "&") for h in re.findall(r'href="(/go/[^"]+)"', html)]


def test_a_reader_from_a_creators_trip_gets_one_card_per_lane_and_no_invented_offers(client, live):
    _, handle, _ = live
    html = client.get(f"/plan?to=la&{TRIP}&via={handle}").text
    text = words(html)
    for card in ("Search flights to Los Angeles", "Find stays near Los Angeles", "Tickets and things to do"):
        assert text.count(card) == 1, card
    for invented in ("Skylark", "Pacific Hop", "Tidewater", "Preview: sample prices", "Sample data", "$"):
        assert invented not in text, invented
    assert [h.split("?")[0] for h in go_links(html)] == ["/go/search-flight", "/go/search-stay", "/go/search-todo"]
    assert "we may earn a commission" in text


def test_the_cards_say_where_they_lead_and_for_when(client, live):
    _, handle, _ = live
    text = words(client.get(f"/plan?to=hi&{TRIP}&k=4,7&via={handle}").text)
    assert "Mar 5 – 9" in text and "2 adults, 2 kids" in text
    assert "Search on Aviasales" in text and "Find stays on Klook" in text and "See things to do on Klook" in text


def test_a_disneyland_trip_asks_for_anaheim_and_disneyland_tickets(client, live):
    _, handle, _ = live
    html = client.get(f"/plan?to=la&{TRIP}&focus=disney&via={handle}").text
    text = words(html)
    assert "Find stays near Anaheim" in text and "Disneyland Resort tickets" in text and "See tickets on Klook" in text
    assert all("focus=disney" in h for h in go_links(html))


def test_the_cookie_alone_is_enough_to_stay_honest_through_a_change_of_dates(client, live):
    _, handle, _ = live
    client.get(f"/plan?to=la&{TRIP}&via={handle}", headers=seen_on(handle))
    assert "Search flights to Los Angeles" in words(client.get("/plan?to=la&d=2027-04-02&r=2027-04-06&a=3").text)


def test_nobody_from_a_creator_gets_the_normal_workspace_as_before(client, live):
    text = words(client.get(f"/plan?to=la&{TRIP}").text)
    assert "Preview: sample prices" in text and "Search flights to" not in text
    assert "Search flights to" not in words(client.get(f"/plan?to=la&{TRIP}&via=nobody").text)


def test_on_a_local_copy_the_workspace_stays_the_designed_sample(client, nokeys, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "1")
    _, handle, _ = live_trip()
    text = words(client.get(f"/plan?to=la&{TRIP}&via={handle}").text)
    assert "Skylark" in text and "Search flights to" not in text


def test_without_keys_the_cards_are_there_but_lead_nowhere_and_say_so(client, nokeys, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    _, handle, _ = live_trip()
    html = client.get(f"/plan?to=la&{TRIP}&via={handle}").text
    assert go_links(html) == [] and "Booking links are not switched on yet" in words(html)


def test_a_flight_click_from_the_card_leaves_from_the_readers_airport_with_the_kids_apart(client, live):
    _, handle, _ = live
    html = client.get(f"/plan?to=la&{TRIP}&k=4,7&home=jfk&via={handle}").text
    flight = [h for h in go_links(html) if "search-flight" in h][0]
    loc = client.get(flight, follow_redirects=False).headers["location"]
    assert loc.startswith("https://www.aviasales.com/search/JFK0503LAX090322?marker=801445.")
    asks = client.get(f"/plan?to=la&{TRIP}&via={handle}").text
    loc = client.get([h for h in go_links(asks) if "search-flight" in h][0], follow_redirects=False).headers["location"]
    assert loc.startswith("https://www.aviasales.com/?destination_iata=LAX&") and "SFO" not in loc


def test_the_reader_can_say_where_they_fly_from_and_it_is_checked(client, live):
    _, handle, _ = live
    html = client.get(f"/plan?to=la&{TRIP}&via={handle}").text
    form = re.search(r'<form[^>]*action="/plan"[^>]*>(.*?)</form>', html, re.S).group(1)
    names = dict(re.findall(r'<input[^>]*name="([^"]+)"[^>]*value="([^"]*)"', form))
    assert names["to"] == "la" and names["d"] == "2027-03-05" and names["via"] == handle and "home" in names
    ok = client.get(f"/plan?to=la&{TRIP}&via={handle}&home=ord").text
    assert 'name="home"' in ok and 'value="ORD"' in ok and "flying from ORD" in words(ok)
    bad = client.get(f"/plan?to=la&{TRIP}&via={handle}&home=O1D")
    assert bad.status_code == 200 and 'role="alert"' in bad.text and "three-letter airport code" in words(bad.text)
    assert "O1D" in bad.text and all("home=" not in h for h in go_links(bad.text))        # kept in the box, never in a link


def test_the_honest_page_keeps_the_creator_cookie_rules(client, live):
    _, handle, _ = live
    r = client.get(f"/plan?to=la&{TRIP}&via={handle}", headers=seen_on(handle))
    assert f"ga_via={handle}" in r.headers["set-cookie"]
    assert "set-cookie" not in client.get(f"/plan?to=la&{TRIP}&via={handle}", headers={"referer": "https://evil.example/"}).headers


def test_the_honest_page_leaves_no_remembered_picks_behind(client, live):
    _, handle, _ = live
    sign_in(client, "ari")
    client.get(f"/plan?to=la&{TRIP}&via={handle}")
    assert 'class="st-continue"' not in client.get("/start").text
