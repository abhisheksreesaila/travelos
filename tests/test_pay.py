from urllib.parse import quote as q

from gitaway import catalog, session as ses
from tests.test_signin import person, session_data, sign_in, stored_booking, tid

PICK = "f=f2&h=h3&c=c1"
DATA = {"f": "f2", "h": "h3", "c": "c1"}


def total(f="f2", h="h3", c="c1"):
    return catalog.money(catalog.quote(f, h, c).total_cents)


def test_signed_in_book_link_goes_straight_to_the_sheet(client):
    sign_in(client)
    html = client.get(f"/plan?{PICK}").text
    assert 'href="/plan/pay?f=f2&amp;h=h3&amp;c=c1"' in html
    assert "intent=pay" not in html
    assert client.get(f"/plan/quote?{PICK}").json()["ledger"]["book"] == "/plan/pay?f=f2&h=h3&c=c1"


def test_signed_out_book_link_goes_to_sign_in_with_pay_intent(client):
    html = client.get(f"/plan?{PICK}").text
    assert f'href="/signin?next={q("/plan/pay?" + PICK, safe="")}&amp;intent=pay"' in html


def test_sign_in_with_pay_intent_lands_on_the_sheet_and_cancel_goes_back_to_the_picks(client):
    html = client.get(f"/signin?next={q('/plan/pay?' + PICK, safe='')}&intent=pay").text
    assert 'id="si-cancel"' in html and 'href="/plan?f=f2&amp;h=h3&amp;c=c1" id="si-cancel"' in html
    r = sign_in(client, next="/plan/pay?" + PICK, intent="pay")
    assert r.headers["location"] == "/plan/pay?" + PICK
    assert "Pay " + total() in client.get(r.headers["location"]).text


def test_sheet_shows_the_quote(client):
    sign_in(client, "sam")
    html = client.get(f"/plan/pay?{PICK}").text
    assert 'role="dialog"' in html and f"Pay {total()}" in html
    for o in ("f2", "h3", "c1"):
        offer = catalog.offer(o)
        assert offer.name in html and catalog.money(offer.price_cents) in html
    assert "Demo card ending 4242" in html and "Sam Kim pays" in html
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
    b = stored_booking()
    client.post("/pay", data=DATA, follow_redirects=False)
    assert stored_booking() == b and len(ses.trips(person())) == 1
    assert set(session_data(client)) <= set(ses.AUTH_KEYS)  # the cookie holds only the sign-in
    assert b["total_cents"] == catalog.quote("f2", "h3", "c1").total_cents and b["id"].startswith("GA-")


def test_booked_shows_flight_and_hotel(client):
    sign_in(client)
    client.post("/pay", data=DATA)
    html = client.get("/booked").text
    assert "going to LA!" in html
    assert "Pacific Hop 88" in html and "Hotel Marigold" in html and "Open my trip calendar" in html
    assert 'href="/calendar"' in html
    assert client.get("/calendar?view=days").status_code == 200


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
    assert stored_booking()["flight"] == "f1"


def test_forged_total_is_ignored(client):
    sign_in(client)
    client.post("/pay", data={**DATA, "total_cents": "1", "total": "$1"})
    assert stored_booking()["total_cents"] == catalog.quote("f2", "h3", "c1").total_cents


def test_paying_different_picks_replaces_the_booking(client):
    sign_in(client)
    client.post("/pay", data=DATA)
    first = stored_booking()
    client.post("/pay", data={"f": "f1", "h": "h1", "c": "c1"})
    second = stored_booking()
    assert second["id"] != first["id"] and second["stay"] == "h1"
    assert "The Tidewater" in client.get("/booked").text


def test_celebration_is_a_page_not_a_dialog_and_confetti_sits_behind_the_card(client):
    import re
    from pathlib import Path
    sign_in(client)
    client.post("/pay", data=DATA)
    html = client.get("/booked").text
    assert 'role="dialog"' not in html and "aria-modal" not in html and "<section" in html
    css = (Path(__file__).parent.parent / "assets/css/pay.css").read_text()
    z = lambda sel: int(re.search(re.escape(sel) + r"\s*\{[^}]*z-index:\s*(\d+)", css).group(1))
    assert z(".pay-confetti") < z(".pay-done")


def test_pay_and_booked_pages_load_page_css_after_tokens_and_base_once_each(client):
    sign_in(client)
    client.post("/pay", data=DATA)
    for path in (f"/plan/pay?{PICK}", "/booked"):
        html = client.get(path).text
        for css in ("tokens", "base", "pay"):
            assert html.count(f"/assets/css/{css}.css") == 1, (path, css)
        assert html.index("/assets/css/tokens.css") < html.index("/assets/css/base.css") < html.index("/assets/css/pay.css"), path
