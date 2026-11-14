"""F-195 (6), F-198: in production a reader (from a creator's trip or not) gets one honest card per lane, never invented offers.

The workspace's flights, stays and cars are an invented catalog (labelled "Preview: sample prices"); sending a creator's reader there made the booking path point at things that do not
exist. Through the HTTP seam; no test reaches the network.
"""

import re
import socket
from html import unescape
from urllib.parse import parse_qs, urlsplit

import pytest

from gitaway import session as ses
from gitaway.partners import prices, travelpayouts
from tests.live_trips import live_trip
from tests.pagebody import without_bar
from tests.test_affiliate import FakeApi, nokeys, seen_on  # noqa: F401 (the fixture)
from tests.test_signin import person, sign_in

TRIP = "d=2027-03-05&r=2027-03-09&a=2"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("a code path tried to use the network")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    prices.clear()
    monkeypatch.setattr(prices, "TRANSPORT", lambda *a: {"success": True, "data": []})     # the Data API has seen nothing: no price is shown


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
    """The booking lanes' buttons (F-198: /book/<lane>?site=...)."""
    return [h.replace("&amp;", "&") for h in re.findall(r'href="(/book/[^"]+)"[^>]*class="btn btn-ink ps-go"', html)]


def lane_site(href):
    q = parse_qs(urlsplit(href).query)
    return urlsplit(href).path.rsplit("/", 1)[1], q["site"][0]


def test_a_reader_from_a_creators_trip_gets_one_card_per_lane_and_no_invented_offers(client, live):
    _, handle, _ = live
    html = client.get(f"/plan?to=la&{TRIP}&via={handle}").text
    text = words(html)
    for card in ("Search flights to Los Angeles", "Find stays near Los Angeles", "Tickets and things to do"):
        assert text.count(card) == 1, card
    for invented in ("Skylark", "Pacific Hop", "Tidewater", "Preview: sample prices", "Sample data", "$"):
        assert invented not in text, invented
    assert [lane_site(h) for h in go_links(html)] == [("flight", "aviasales"), ("stay", "klook"), ("car", "expedia"), ("todo", "klook")]
    assert "We may earn a commission" in text and "No commission" in text      # Aviasales and Klook pay; the Expedia car is a plain link


def test_the_cards_say_where_they_lead_and_for_when(client, live):
    _, handle, _ = live
    text = words(client.get(f"/plan?to=hi&{TRIP}&k=4,7&via={handle}").text)
    assert "Mar 5 – 9" in text and "2 adults, 2 kids" in text
    assert "Search on Aviasales" in text and "Find stays on Klook" in text and "Things to do on Klook" in text and "Find cars on Expedia" in text


def test_a_disneyland_trip_asks_for_anaheim_and_disneyland_tickets(client, live):
    _, handle, _ = live
    html = client.get(f"/plan?to=la&{TRIP}&focus=disney&via={handle}").text
    text = words(html)
    assert "Search flights to Disneyland" in text and "Find stays near Anaheim" in text and "Disneyland Resort tickets" in text and "See tickets on Klook" in text
    assert all("place=Disneyland" in h for h in go_links(html))


def test_the_cookie_alone_is_enough_to_stay_honest_through_a_change_of_dates(client, live):
    _, handle, _ = live
    client.get(f"/plan?to=la&{TRIP}&via={handle}", headers=seen_on(handle))
    assert "Search flights to Los Angeles" in words(client.get("/plan?to=la&d=2027-04-02&r=2027-04-06&a=3").text)


def test_in_production_nobody_gets_the_invented_workspace(client, live):
    """F-198 (6): the catalog's made-up flights, hotels and prices are for the showcase and local copies only."""
    for url in (f"/plan?to=la&{TRIP}", f"/plan?to=la&{TRIP}&via=nobody"):
        text = words(client.get(url).text)
        assert "Search flights to Los Angeles" in text and "Skylark" not in text and "Preview: sample prices" not in text, url
    for url in ("/plan", "/plan?f=f1&h=h1&c=c1"):        # no place named: the form asks where, and nothing invented is drawn
        text = words(client.get(url).text)
        assert "Where are you going?" in text and "Skylark" not in text and "$" not in text, url
    for hidden in ("/plan/quote?f=f1", "/plan/explore?h=h1"):
        assert client.get(hidden).status_code == 404, hidden


def test_on_a_local_copy_the_workspace_stays_the_designed_sample(client, nokeys, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "1")
    _, handle, _ = live_trip()
    text = words(client.get(f"/plan?to=la&{TRIP}&via={handle}").text)
    assert "Skylark" in text and "Search flights to" not in text


def test_without_keys_every_lane_is_a_plain_link_that_says_no_commission(client, nokeys, monkeypatch):
    """F-198: a plain link needs no agreement and no key, so the lanes work before any program is connected; they earn nothing and say so."""
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    _, handle, _ = live_trip()
    html = client.get(f"/plan?to=la&{TRIP}&via={handle}").text
    assert [lane_site(h) for h in go_links(html)] == [("flight", "aviasales"), ("stay", "expedia"), ("car", "expedia"), ("todo", "getyourguide")]
    text = words(html)
    assert "We may earn a commission" not in text and text.count("No commission") == 4
    loc = client.get(go_links(html)[1], follow_redirects=False).headers["location"]
    assert loc.startswith("https://www.expedia.com/go/hotel/search/Destination/2027-03-05/2027-03-09?CityName=Los%20Angeles") and "marker" not in loc


def test_a_flight_click_from_the_card_leaves_from_the_readers_airport_with_the_kids_apart(client, live):
    _, handle, _ = live
    html = client.get(f"/plan?to=la&{TRIP}&k=4,7&home=jfk&via={handle}").text
    flight = [h for h in go_links(html) if "/book/flight" in h][0]
    loc = client.get(flight, follow_redirects=False).headers["location"]
    assert loc.startswith("https://www.aviasales.com/search/JFK0503LAX090322?marker=801445.")
    asks = client.get(f"/plan?to=la&{TRIP}&via={handle}").text
    loc = client.get([h for h in go_links(asks) if "/book/flight" in h][0], follow_redirects=False).headers["location"]
    assert loc.startswith("https://www.aviasales.com/?destination_iata=LAX&") and "SFO" not in loc


def test_the_reader_can_say_where_they_fly_from_and_it_is_checked(client, live):
    _, handle, _ = live
    html = client.get(f"/plan?to=la&{TRIP}&via={handle}").text
    form = re.findall(r'<form[^>]*action="/plan"[^>]*>(.*?)</form>', html, re.S)[1]      # the flight card's airport form (the first is where, when and who)
    names = dict(re.findall(r'<input[^>]*name="([^"]+)"[^>]*value="([^"]*)"', form))
    assert names["place"] == "Los Angeles" and names["d"] == "2027-03-05" and names["via"] == handle and "home" in names
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
    assert not ses.remembered_plan(person("ari"))


def test_dates_that_have_passed_become_the_next_ones_worth_searching_with_the_same_length(client, live):
    """A stale link, or a bare /plan with the sample's old October dates, must not send a reader to a search for the past."""
    _, handle, _ = live
    html = client.get(f"/plan?to=la&d=2026-01-05&r=2026-01-09&a=2&via={handle}").text
    assert "Nov 20 – 24" in words(html) and "d=2026-11-20&r=2026-11-24" in html.replace("&amp;", "&")      # the first Friday 45 days on from the test's fixed "today", 5 days long


def test_dates_ahead_are_left_alone(client, live):
    _, handle, _ = live
    assert "Mar 5 – 9" in words(client.get(f"/plan?to=la&{TRIP}&via={handle}").text)


def test_changing_dates_keeps_a_reader_with_no_cookie_on_the_honest_page(client, live):
    """F-195 review, F-198: a pasted /plan?via= link sets no cookie (D-125), so `via` itself rides in the page's own where-when-who form."""
    _, handle, _ = live
    page = client.get(f"/plan?to=la&{TRIP}&via={handle}", headers={"referer": "https://evil.example/"})
    assert "set-cookie" not in page.headers
    form = re.search(r'<form[^>]*id="ps-trip"[^>]*>(.*?)</form>|<form[^>]*action="/plan"[^>]*id="ps-trip"[^>]*>(.*?)</form>', page.text, re.S)
    assert form and re.search(rf'name="via"[^>]*value="{handle}"', form.group(0))
    after = client.get(f"/plan?place=Los+Angeles&d=2027-04-02&r=2027-04-06&a=3&via={handle}")
    assert "set-cookie" not in after.headers
    text = words(after.text)
    assert "Search flights to Los Angeles" in text and "Apr 2 – 6 · 3 adults" in text and "Skylark" not in text and all(f"via={handle}" in h for h in go_links(after.text))


def test_an_old_where_to_link_with_a_via_opens_the_matrix_without_it(client, live, monkeypatch):
    old = {"go": "1", "to": "la", "d": "2027-04-02", "r": "2027-04-06", "a": "3", "n": "0", "via": "nobody-here"}
    assert client.get("/start", params=old, follow_redirects=False).headers["location"] == "/trips/import"      # off the showcase with no LiteAPI key there is no matrix
    monkeypatch.setenv("LITEAPI_KEY", "a-key")
    r = client.get("/start", params=old, follow_redirects=False)
    assert r.headers["location"] == "/plan/matrix?to=Los+Angeles&d=2027-04-02&r=2027-04-06&a=3"      # F-231: an old link's sample city is just its name, and the matrix has no honest-page mode to keep


def test_off_the_showcase_a_place_alone_brings_no_sample_kids(live):
    """F-210: /plan?place=Lisbon with no party must not carry the sample family's kids into the page or a trip made from it."""
    from gitaway.pages import plan_search
    search, _ = plan_search.search_from(place="Lisbon", iata="LIS")
    assert search.kid_ages == ()
    search, _ = plan_search.search_from(place="Lisbon", iata="LIS", d="2027-05-01", r="2027-05-06", a="2", k="6")
    assert search.kid_ages == (6,)
