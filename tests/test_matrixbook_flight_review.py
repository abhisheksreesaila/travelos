"""F-276 review round 1 (D-980) at the routes: flights are off for a live key unless GITAWAY_LIVE_FLIGHTS=1 (at the gate and in the checkout), a second Book of a square with a booked flight books the stay
alone, a form still open is not replaced, the flight form shows the prebook's price, a reload of the flight's return after the stay is paid shows no payment form, a cancel quote counts as a press, and the
captain sees only ids. Fixtures and helpers are those of tests/test_matrixbook_flight.py."""

import re
from datetime import datetime, timedelta, timezone

from fasthtml.common import to_xml

from gitaway import familydb, liteapi, session as ses
from tests.flight_support import BOOK as FBOOK, CANCELS, PREBOOK as FPREBOOK, VERIFY
from tests.test_matrixbook_flight import FORM, FRAG, RETURN, STAY_RETURN, booked_flights, confirm, flight_payments, flying, money, paid_flight, person, sheet, text, token  # noqa: F401 (flying is a fixture)
from tests.test_matrixbook_live import BOOK, GUEST, PREBOOK

SOON = "Flight booking opens soon. Your flight isn't booked yet."


def switch_off(monkeypatch):
    monkeypatch.delenv("GITAWAY_LIVE_FLIGHTS", raising=False)


def test_a_live_key_without_the_switch_sends_no_flight_call_at_the_gate(flying, monkeypatch):  # noqa: F811
    switch_off(monkeypatch)
    assert liteapi.flights_live() is False
    assert liteapi.flight_verify("offer-1", "fam").status == liteapi.OFF
    assert liteapi.flight_prebook("offer-1", {"firstName": "Maya"}, [{"firstName": "Maya"}], "", "fam").status == liteapi.OFF
    assert flying.asked == []
    monkeypatch.setenv("GITAWAY_LIVE_FLIGHTS", "1")
    assert liteapi.flight_verify("offer-1", "fam").ok and liteapi.flight_prebook("offer-1", {"firstName": "Maya"}, [{"firstName": "Maya"}], "", "fam").ok


def test_the_stays_prebook_is_not_a_flight_and_the_switch_does_not_touch_it(flying, monkeypatch):  # noqa: F811
    switch_off(monkeypatch)
    assert liteapi._allowed({"offerId": "o", "usePaymentSdk": True}) is True
    assert liteapi._allowed({"offerId": "o", "usePaymentSdk": True, "contact": {}, "passengers": []}) is False


def test_a_live_key_without_the_switch_books_the_stay_and_says_the_flight_opens_soon(flying, client, monkeypatch):  # noqa: F811
    switch_off(monkeypatch)
    html = sheet(client).text
    words = text(html)
    assert SOON in words and "Who is travelling?" not in words and "Who is the lead guest?" in words
    assert "Sample flight booking" not in words and "airline’s site" not in html and "Search flights on" not in html
    assert flying.calls(VERIFY) == [] and flying.calls(FPREBOOK) == [] and len(flying.stays.calls(PREBOOK)) == 1
    assert "Flight ·" not in words      # no flight line in the sum: the stay alone is booked
    r = client.post("/plan/matrix/book/confirm", data={**FORM, "token": token(html), **GUEST}, headers=FRAG)
    assert "Pay for your stay" in text(r.text) and flying.calls(FPREBOOK) == [] and flying.calls(FBOOK) == [] and booked_flights() == []
    client.get(f"{STAY_RETURN}?token={token(html)}")
    assert len(flying.stays.calls(BOOK)) == 1 and booked_flights() == [] and flying.calls(FPREBOOK) == []      # the stay is booked; no flight row, none pretended


def test_with_the_switch_on_the_flow_is_the_flights(flying, client):  # noqa: F811
    assert "Who is travelling?" in text(sheet(client).text) and len(flying.calls(VERIFY)) == 1


# ---- a booked flight is not bought again ----------------------------------------------------------------------------------

def test_a_second_book_after_a_booked_flight_and_a_failed_stay_books_the_stay_alone(flying, client):  # noqa: F811
    _, tok, _ = paid_flight(client)
    client.get(f"{RETURN}?token={tok}")
    flying.stays.answers["book"] = "book_unpaid.json"
    client.get(f"{STAY_RETURN}?token={tok}")      # the stay failed
    flying.stays.answers["book"] = "book_nonrefundable.json"
    before = (len(flying.calls(VERIFY)), len(flying.calls(FPREBOOK)), len(flying.calls(FBOOK)))
    html = sheet(client).text
    words = text(html)
    assert "Your flight is already booked." in words and "Who is travelling?" not in words and "Who is the lead guest?" in words
    r = client.post("/plan/matrix/book/confirm", data={**FORM, "token": token(html), **GUEST}, headers=FRAG)
    assert "Pay for your stay" in text(r.text)
    assert (len(flying.calls(VERIFY)), len(flying.calls(FPREBOOK)), len(flying.calls(FBOOK))) == before and len(booked_flights()) == 1


def test_a_cancelled_flight_is_bought_again_by_the_next_book(flying, client):  # noqa: F811
    _, tok, _ = paid_flight(client)
    client.get(f"{RETURN}?token={tok}")
    row = booked_flights()[0]
    head, nxt = {"origin": "http://testserver"}, "/trip/booking?block=b-out"
    client.post("/trip/booking/flight/cancel", data={"booking": row["booking_id"], "step": "quote", "next": nxt}, headers=head)
    client.post("/trip/booking/flight/cancel", data={"booking": row["booking_id"], "step": "confirm", "sure": "1", "next": nxt}, headers=head)
    assert "Who is travelling?" in text(sheet(client).text)


# ---- a form still open ----------------------------------------------------------------------------------------------------

def test_a_second_confirm_while_the_first_form_is_open_makes_no_second_transaction(flying, client):  # noqa: F811
    html = sheet(client).text
    confirm(client, html)
    r = confirm(client, html)
    words = text(r.text)
    assert "A payment form for this flight is already open." in words and "do not pay twice" in words and len(flying.calls(FPREBOOK)) == 1
    link = re.search(r"<a[^>]*data-flight-return[^>]*>", r.text)
    assert link and f"/plan/matrix/book/flight/return?token={token(html)}" in link[0].replace("&amp;", "&")
    assert len(flight_payments()) == 1 and flight_payments()[0]["status"] == "paying"
    got = client.get(f"{RETURN}?token={token(html)}")      # the first form's return still books it
    assert "Your flight is booked" in text(got.text) and len(flying.calls(FBOOK)) == 1


# ---- the flight form's amount ----------------------------------------------------------------------------------------------

def test_the_flight_form_shows_what_the_prebook_says_is_charged(flying, client):  # noqa: F811
    flying.answers["prebook"] = lambda doc: doc["data"][0].__setitem__("price", (flying.cents + 50) / 100)      # fifty cents off the verify: inside the rounding, but what the card pays
    r = confirm(client, sheet(client).text)
    shown = re.search(r'data-charge[^>]*>\$([\d,.]+)<', r.text) or re.search(r'>\$([\d,.]+)</span>[^<]*(?=.*data-charge)', r.text)
    assert shown and f"${shown[1]}" == money(flying.cents + 50).replace(".00", "")
    assert f"the flight {money(flying.cents + 50).replace('.00', '')} now" in text(r.text)


# ---- the return page after the stay is paid ---------------------------------------------------------------------------------

def test_reloading_the_flights_return_after_the_stay_is_paid_shows_no_payment_form(flying, client):  # noqa: F811
    _, tok, _ = paid_flight(client)
    client.get(f"{RETURN}?token={tok}")
    client.get(f"{STAY_RETURN}?token={tok}")
    r = client.get(f"{RETURN}?token={tok}")
    assert "Your stay is booked too." in text(r.text) and "data-pay-root" not in r.text and "Now pay for your stay" not in text(r.text)
    link = re.search(r"<a[^>]*data-see-pass[^>]*>", r.text)
    assert link and f"/plan/matrix/book/return?token={tok}" in link[0]
    assert len(flying.calls(FBOOK)) == 1 and len(flying.stays.calls(BOOK)) == 1


# ---- the cancel quote is a press ------------------------------------------------------------------------------------------

def test_a_cancel_quote_counts_as_a_booking_press(flying, client):  # noqa: F811
    _, tok, _ = paid_flight(client)
    client.get(f"{RETURN}?token={tok}")
    row = booked_flights()[0]
    data, head = {"booking": row["booking_id"], "step": "quote", "next": "/trip/booking?block=b-out"}, {"origin": "http://testserver"}
    places = [client.post("/trip/booking/flight/cancel", data=data, headers=head, follow_redirects=False).headers["location"] for _ in range(6)]
    assert any("err=flight_slow" in p for p in places)
    assert len([c for c in flying.asked if c[0] == CANCELS and c[2] is None]) < 6      # the refused presses never asked LiteAPI


# ---- what the captain is shown -----------------------------------------------------------------------------------------------

def test_the_admin_lists_a_form_left_open_with_its_transaction_and_no_traveller(flying, client):  # noqa: F811
    from gitaway.pages import admin
    paid_flight(client)
    assert admin._flights_to_match() == ""      # a form just opened is not yet "maybe paid"
    with ses.family(person()) as fam:
        with familydb.transaction(fam.db):
            familydb.run(fam.db, "UPDATE matrix_flight_payments SET updated_at = :t", t=(datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat(timespec="seconds"))
    html = to_xml(admin._flights_to_match())
    assert "Flights to match" in html and "tr_cts_HX7MNE9cTvRSWyWn_QAcm" in html and "paying" in html
    assert "Okafor" not in html and "maya" not in html.lower() and "example.com" not in html


def test_an_unpaid_form_reloaded_again_and_again_stops_asking_liteapi(flying, client):  # noqa: F811
    _, tok, _ = paid_flight(client)
    flying.answers["book"] = (400, {"error": {"code": 2014, "description": "payment not completed"}})
    codes = [client.get(f"{RETURN}?token={tok}").status_code for _ in range(6)]
    asked = len(flying.calls(FBOOK))
    assert codes[-1] == 429 and asked < 6 and codes.count(402) == asked      # the refused reloads made no LiteAPI call
    assert "a lot of booking tries" in text(client.get(f"{RETURN}?token={tok}").text) and len(flying.calls(FBOOK)) == asked
