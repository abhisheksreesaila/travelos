from urllib.parse import quote as q

from gitaway import catalog
from tests.test_signin import session_data, sign_in

PICK = "f=f2&h=h3&c=c1"
DATA = {"f": "f2", "h": "h3", "c": "c1"}


def total(f="f2", h="h3", c="c1"):
    return catalog.money(catalog.quote(f, h, c).total_cents)


def test_signed_in_book_link_goes_straight_to_the_sheet(client):
    sign_in(client)
    html = client.get(f"/plan?{PICK}").text
    assert 'href="/plan/pay?f=f2&amp;h=h3&amp;c=c1"' in html
    assert "intent=pay" not in html
    assert '"book": "/plan/pay?f=f2&h=h3&c=c1"' in html


def test_signed_out_book_link_goes_to_sign_in_with_pay_intent(client):
    html = client.get(f"/plan?{PICK}").text
    assert f'href="/signin?next={q("/plan?" + PICK, safe="")}&amp;intent=pay"' in html


def test_sheet_shows_the_quote(client):
    sign_in(client, "sam")
    html = client.get(f"/plan/pay?{PICK}").text
    assert 'role="dialog"' in html and f"Pay {total()}" in html
    for o in ("f2", "h3", "c1"):
        offer = catalog.offer(o)
        assert offer.name in html and catalog.money(offer.price_cents) in html
    assert "Demo card ending 4242" in html and "Sam pays" in html
    assert "Simulated checkout. No money moves and nothing is really booked." in html
    assert "LA, Oct 16" in html


def test_sheet_signed_out_goes_to_sign_in(client):
    r = client.get(f"/plan/pay?{PICK}", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/signin?next=")
    assert "intent=pay" in r.headers["location"]


def test_pay_without_traveler_redirects_to_sign_in(client):
    r = client.post("/pay", data=DATA, follow_redirects=False)
    assert r.status_code == 303 and "/signin" in r.headers["location"] and "intent=pay" in r.headers["location"]


def test_pay_twice_makes_one_booking(client):
    sign_in(client)
    r1 = client.post("/pay", data=DATA, follow_redirects=False)
    assert r1.status_code == 303 and r1.headers["location"] == "/booked"
    first = session_data(client)["bookings"]
    client.post("/pay", data=DATA, follow_redirects=False)
    assert session_data(client)["bookings"] == first
    b = first["ari"]
    assert b["total_cents"] == catalog.quote("f2", "h3", "c1").total_cents and b["id"].startswith("GA-")


def test_booked_shows_flight_and_hotel(client):
    sign_in(client)
    client.post("/pay", data=DATA)
    html = client.get("/booked").text
    assert "going to LA!" in html
    assert "Pacific Hop 88" in html and "Hotel Marigold" in html and "Open my trip calendar" in html
    assert 'href="/calendar"' in html
    assert client.get("/calendar").status_code == 200


def test_booked_without_booking_redirects_to_plan(client):
    assert client.get("/booked", follow_redirects=False).headers["location"] == "/plan"
    sign_in(client)
    assert client.get("/booked", follow_redirects=False).headers["location"] == "/plan"


def test_bookings_are_per_traveler(client):
    sign_in(client, "ari")
    client.post("/pay", data=DATA)
    sign_in(client, "sam")
    assert client.get("/booked", follow_redirects=False).status_code == 303


def test_pay_ignores_junk_picks(client):
    sign_in(client)
    client.post("/pay", data={"f": "zzz", "h": "h3", "c": "c1"})
    assert session_data(client)["bookings"]["ari"]["flight"] == "f1"
