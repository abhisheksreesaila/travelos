"""F-198 through the HTTP seam: the booking lanes for any destination, on the captain's own test trip (Lake Tahoe, Dec 19 to 26 2026, from SFO, 2 adults, kids 8 and 11).

Every button goes through /book/<lane>; each must land on exactly the link of docs/research/booking-any-trip.md section 3 (with no keys: plain links, nothing added). No test reaches the network.
"""

import re
import socket
from html import unescape
from urllib.parse import parse_qs, urlsplit

import pytest

from gitaway.partners import links, places, prices, travelpayouts
from tests.pagebody import without_bar
from tests.test_signin import sign_in

TAHOE = "/plan?place=Lake+Tahoe&d=2026-12-19&r=2026-12-26&a=2&k=8,11&home=SFO"
KEYS = ("TRAVELPAYOUTS_MARKER", "TRAVELPAYOUTS_TOKEN", "TRAVELPAYOUTS_TRS", "KLOOK_FALLBACK_URL", "PARTNER_TRACKED", "PARTNER_FLIGHT", "PARTNER_STAY", "PARTNER_CAR", "PARTNER_TODO")
RESEARCH = {   # docs/research/booking-any-trip.md section 3, for this trip
    ("flight", "aviasales"): "https://www.aviasales.com/search/SFO1912RNO261222",
    ("stay", "expedia"): "https://www.expedia.com/go/hotel/search/Destination/2026-12-19/2026-12-26?CityName=South%20Lake%20Tahoe&NumRoom=1&NumAdult-Room1=2&NumChild-Room1=2"
                         "&Room1-Child1Age=8&Room1-Child2Age=11",
    ("stay", "airbnb"): "https://www.airbnb.com/s/South-Lake-Tahoe--California/homes?checkin=2026-12-19&checkout=2026-12-26&adults=2&children=2",
    ("stay", "vrbo"): "https://www.vrbo.com/search?destination=South%20Lake%20Tahoe%2C%20California&startDate=2026-12-19&endDate=2026-12-26&adults=2&children=1_8%2C1_11",
    ("car", "expedia"): "https://www.expedia.com/go/car/search/Airport/2026-12-19/2026-12-26?PickUpLoc=RNO&DiffDropLoc=0&PickUpTime=11AM&DropTime=11AM&Class=SUV&Equipment=W,S",
    ("todo", "getyourguide"): "https://www.getyourguide.com/s/?q=Lake%20Tahoe&date_from=2026-12-20&date_to=2026-12-25",
    ("direct", "resort-0"): "https://www.skiheavenly.com/", ("direct", "resort-1"): "https://www.northstarcalifornia.com/", ("direct", "resort-2"): "https://www.kirkwood.com/",
    ("direct", "resort-3"): "https://www.palisadestahoe.com/", ("direct", "resort-4"): "https://sierraattahoe.com/",
}


@pytest.fixture(autouse=True)
def production(monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    for k in KEYS:
        monkeypatch.delenv(k, raising=False)
    travelpayouts._CACHE.clear()
    prices.clear()
    monkeypatch.setattr(prices, "TRANSPORT", lambda *a: {"success": True, "data": []})

    def refuse(*a, **k):
        raise AssertionError("a code path tried to use the network")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)


def words(html):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", without_bar(html))))


def book_links(html):
    return [h.replace("&amp;", "&") for h in re.findall(r'href="(/book/[^"]+)"', html)]


def key(href):
    return urlsplit(href).path.rsplit("/", 1)[1], parse_qs(urlsplit(href).query)["site"][0]


def test_the_tahoe_trip_has_every_lane_and_each_lands_on_the_researched_link(client):
    html = client.get(TAHOE).text
    text = words(html)
    for card in ("Search flights to Lake Tahoe", "Find stays near South Lake Tahoe", "Rent a car at RNO", "Tickets and things to do", "Lift tickets and ski school"):
        assert text.count(card) == 1, card
    assert "Dec 19 – 26 · 2 adults, 2 kids · flying from SFO" in text and "An SUV with snow chains and a ski rack" in text
    found = {key(h): h for h in book_links(html)}
    assert set(found) == set(RESEARCH)
    for k, href in found.items():
        assert client.get(href, follow_redirects=False).headers["location"] == RESEARCH[k], k
    assert "We may earn a commission" not in text and "No commission" in text and "Buy direct · No commission" in text
    assert "$" not in text      # no prices of our own, and the Data API had none


def test_a_plain_link_is_not_sponsored_and_a_paid_one_is(client, monkeypatch):
    html = client.get(TAHOE).text
    assert not re.search(r'rel="sponsored[^"]*"[^>]*data-site="expedia"|data-site="expedia"[^>]*rel="sponsored', html)
    monkeypatch.setenv("TRAVELPAYOUTS_MARKER", "801445")
    paid = client.get(TAHOE).text
    flight = re.search(r'<a[^>]*data-lane="flight"[^>]*>', paid).group(0)
    assert 'rel="sponsored noopener"' in flight and "We may earn a commission" in words(paid)
    loc = client.get(next(h for h in book_links(paid) if "/book/flight" in h), follow_redirects=False).headers["location"]
    assert loc.startswith("https://www.aviasales.com/search/SFO1912RNO261222?marker=801445.anon_laketahoe_261219_flight")


def test_a_real_cached_fare_shows_with_when_it_was_checked(client, monkeypatch):
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "tok")
    monkeypatch.setattr(prices, "TRANSPORT", lambda *a: {"success": True, "data": [{"price": 187}]})
    html = client.get(TAHOE).text
    what = re.search(r'id="ps-flight".*?<p class="ps-what">(.*?)</p>', html, re.S).group(1)
    assert re.fullmatch(r"from \$187 a person, checked \w{3} \d{1,2}, \d{1,2}:\d{2} [AP]M", unescape(what))


def test_without_a_home_airport_there_is_no_price_and_aviasales_asks(client, monkeypatch):
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "tok")
    monkeypatch.setattr(prices, "TRANSPORT", lambda *a: pytest.fail("a price was asked with no origin"))
    html = client.get(TAHOE.replace("&home=SFO", "")).text
    loc = client.get(next(h for h in book_links(html) if "/book/flight" in h), follow_redirects=False).headers["location"]
    assert loc == "https://www.aviasales.com/?destination_iata=RNO&depart_date=2026-12-19&return_date=2026-12-26&adults=2&children=2"


def test_any_place_works_and_the_flight_asks_for_its_airport(client):
    url = "/plan?place=Bend%2C+Oregon&d=2027-03-05&r=2027-03-09&a=2"
    html = client.get(url).text
    text = words(html)
    assert "Book your trip to Bend, Oregon" in text and "Tell us the nearest airport" in text and 'name="iata"' in html
    assert [key(h)[0] for h in book_links(html)] == ["stay", "stay", "stay", "car", "todo"]
    with_airport = client.get(url + "&iata=rdm").text
    assert 'value="RDM"' in with_airport
    loc = client.get(next(h for h in book_links(with_airport) if "/book/flight" in h), follow_redirects=False).headers["location"]
    assert loc.startswith("https://www.aviasales.com/?destination_iata=RDM&")


def test_a_bad_airport_code_is_said_and_kept_out_of_every_link(client):
    r = client.get("/plan?place=Bend%2C+Oregon&d=2027-03-05&r=2027-03-09&a=2&iata=R1M")
    assert r.status_code == 200 and "Use a three-letter airport code, like RNO" in words(r.text) and 'value="R1M"' in r.text
    assert all("iata" not in h for h in book_links(r.text))


def test_a_click_names_a_lane_and_a_site_never_a_url(client):
    assert client.get("/book/stay?site=evil&place=Lake+Tahoe&d=2026-12-19&r=2026-12-26&a=2").status_code == 404
    assert client.get("/book/stay?site=klook&place=Lake+Tahoe&d=2026-12-19&r=2026-12-26&a=2").status_code == 404      # Klook is not offered at Tahoe
    assert client.get("/book/flight?site=aviasales&place=&d=2026-12-19&r=2026-12-26&a=2").status_code == 404
    assert client.get("/book/flight?site=aviasales&place=Lake+Tahoe&d=2026-12-19&r=2026-12-26&a=2&home=S1O").status_code == 404
    loc = client.get("/book/stay?site=vrbo&place=Lake+Tahoe&d=2026-12-19&r=2026-12-26&a=2&k=8,11&url=https://evil.example/", follow_redirects=False).headers["location"]
    assert loc == RESEARCH[("stay", "vrbo")]


TAHOE_TRIP = """trip:
  title: Tahoe with the kids
  destination: Lake Tahoe
  start: 2026-12-19
  end: 2026-12-26
  booked_on: Expedia
travelers:
  - name: Ari
  - name: Sam
  - name: Kid 1
    age: 8
  - name: Kid 2
    age: 11
hotel:
  name: Lakeside Cabin
  address: 1 Lake Ave, South Lake Tahoe, CA 96150
  check_in: 2026-12-19 16:00
  check_out: 2026-12-26 10:00
  confirmation: "TAHOE123"
"""


def import_tahoe(client, who="ari"):
    sign_in(client, who)
    r = client.post("/trips/import/save", data={"text": TAHOE_TRIP}, follow_redirects=False)
    assert r.status_code == 303, r.text[:400]


def test_a_signed_in_click_is_logged_with_its_subid_and_no_price(client, monkeypatch):
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "tok")      # /partners is shown in production once statistics can be read
    sign_in(client, "ari")
    html = client.get(TAHOE).text
    client.get(next(h for h in book_links(html) if "site=airbnb" in h), follow_redirects=False)
    page = words(client.get("/partners").text)
    assert "Airbnb" in page and "Airbnb · Lake Tahoe" in page and re.search(r"[0-9a-f]{6}_laketahoe_261219_stay", page)


def test_the_open_trip_books_through_the_lanes(client):
    import_tahoe(client)
    r = client.get("/trip/book", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/plan?place=Lake+Tahoe&d=2026-12-19&r=2026-12-26&a=2&k=8%2C11"
    assert 'id="ga-tb-book"' in client.get("/trip/canvas").text
    text = words(client.get(r.headers["location"]).text)
    assert "Book your trip to Lake Tahoe" in text and "Dec 19 – 26 · 2 adults, 2 kids" in text


def test_links_match_the_link_builders():
    """The page and the builders are one source: the researched Tahoe flight is what links.aviasales makes."""
    s = links.Search(places.resolve("Lake Tahoe"), *(__import__("datetime").date(2026, 12, d) for d in (19, 26)), 2, (8, 11), home="SFO")
    assert links.aviasales(s) == RESEARCH[("flight", "aviasales")]


def test_a_typed_mistake_is_said_not_swapped_for_sample_dates(client):
    r = client.get("/plan?place=Lake+Tahoe&d=2026-12-26&r=2026-12-19&a=2&k=8,eleven")
    text = words(r.text)
    assert "Your return must be after you leave." in text and "Pick an age from 0 to 17" in text
    assert book_links(r.text) == [] and re.search(r'<select[^>]*name="n".*?<option value="2" selected>', r.text, re.S)      # what was typed is kept: two kids
