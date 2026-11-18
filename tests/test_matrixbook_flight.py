"""F-276: the checkout books the flight too (gitaway/pages/matrixbook.py, flightcheckout.py, flightcancel.py): verify first, the travellers form, two payment forms (the flight's first), the flight booked
only from the form's return, the pass, the trip's flights, the booking page's cancel with the quote first. LiteAPI's flight answers are the sandbox's own recordings (tests/fixtures/liteapi_flight) and its
stay answers the payment recordings; nothing reaches the network."""

import re

import pytest

from gitaway import auth, familydb, importer, liteapi, matrixbook as mb, session as ses
from gitaway.pages import tripmatrix as mx
from tests.flight_support import BOOK as FBOOK, BOOKING_ID, CANCELS, Fly, PREBOOK as FPREBOOK, VERIFY, price, status
from tests.test_liteapi_pay import LIVE
from tests.test_matrixbook_live import FORM, FRAG, Live, MATRIX, PREBOOK, BOOK, person, sign_in, text, token
from tests.test_matrixbook_page import stays_booked  # noqa: F401

TRAVELLERS = {"first": "Maya", "last": "Okafor", "t0_dob": "1985-04-12", "t0_sex": "F", "t0_nat": "US", "t1_first": "Daniel", "t1_last": "Okafor", "t1_dob": "1983-09-03", "t1_sex": "M", "t1_nat": "US",
              "t2_first": "Leo", "t2_last": "Okafor", "t2_dob": "2019-06-01", "t2_sex": "M", "t2_nat": "US", "t3_first": "Zoe", "t3_last": "Okafor", "t3_dob": "2016-03-15", "t3_sex": "F", "t3_nat": "US",
              "email": "maya.okafor@example.com", "cc": "1", "phone": "415 555 0100", "agree": "on", "req": "Quiet room", "arrive": "Evening"}
RETURN = "/plan/matrix/book/flight/return"
STAY_RETURN = "/plan/matrix/book/return"


def square_flight_cents(client):
    s = mx.state("San Diego", "SFO", "2026-12-12", "2026-12-16", "2", "7,10", "2", "", "")
    _, _, sq, _ = mx._square_of(s, "sandiego", "2026-12-12", "fam-x")
    return sq.flight.cents


@pytest.fixture
def flying(client, monkeypatch):
    """A live key where real booking is on, signed in; the square's stay and flight answered from the recordings, the flight's price at what the square shows."""
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setenv("LITEAPI_KEY", LIVE)
    monkeypatch.setenv("GITAWAY_LIVE_BOOKING", "1")
    monkeypatch.setattr(auth, "production", lambda: False)
    stays = Live()
    fly = Fly(other=stays, swap={"2026-12-18": "2026-12-12", "2026-12-22": "2026-12-16"})      # the recordings' dates moved to the square's week
    monkeypatch.setattr(liteapi, "TRANSPORT", fly)
    sign_in(client)
    panel = client.get("/plan/matrix/tile?" + MATRIX.split("?")[1] + "&lane=sandiego&w=2026-12-12").json()["drawer"]
    stays.shown = int(re.search(r'data-c="(\d+)"', re.search(r'<button[^>]*data-room="0"[^>]*>', panel).group(0)).group(1)) / 100
    cents = square_flight_cents(client)

    def verify_at(total):
        def edit(doc):
            doc["data"][0]["journey"]["pricing"]["display"]["total"] = total / 100
        return edit

    def prebook_at(total):
        def edit(doc):
            doc["data"][0]["price"] = total / 100
        return edit
    fly.answers["verify"], fly.answers["prebook"] = verify_at(cents), prebook_at(cents)
    fly.stays, fly.cents = stays, cents
    fly.asked.clear()
    stays.asked.clear()
    return fly


def sheet(client):
    return client.post("/plan/matrix/book", data=FORM, headers=FRAG)


def confirm(client, html, **over):
    return client.post("/plan/matrix/book/confirm", data={**FORM, "token": token(html), **TRAVELLERS, **over}, headers=FRAG)


def booked_flights():
    with ses.family(person()) as fam:
        return familydb.rows(fam.db, "SELECT * FROM matrix_flights")


def flight_payments():
    with ses.family(person()) as fam:
        return familydb.rows(fam.db, "SELECT * FROM matrix_flight_payments")


def money(cents):
    return f"${cents / 100:,.2f}"


# ---- the sheet: the flight is verified first and the questions are an airline's ----------------------------------------------------

def test_the_sheet_verifies_the_flight_then_the_stay_and_asks_who_is_travelling(flying, client):
    r = sheet(client)
    html, words = r.text, text(r.text)
    assert flying.calls(VERIFY) == [{"offerId": flying.calls(VERIFY)[0]["offerId"]}] and len(flying.calls(VERIFY)) == 1
    assert flying.calls(FPREBOOK) == [] and len(flying.stays.calls(PREBOOK)) == 1      # the flight is verified (nothing held); the stay is held
    assert "Who is travelling?" in words and "Where should we send the tickets?" in words
    assert re.findall(r'data-traveller="(\d)"', html) == ["0", "1", "2", "3"]
    assert "Lead traveller" in words and "kid, age 7" in words and "kid, age 10" in words
    for name in ("first", "last", "t0_dob", "t0_sex", "t0_nat", "t1_first", "t3_dob", "email", "cc", "phone"):
        assert f'name="{name}"' in html, name
    assert "Passport number" not in html and 'name="t0_docno"' not in html      # a domestic route asks for no passport
    assert 'name="agree"' in html and "I have read the fare and hotel rules, including whether the flight and each stay are refundable." in words


def test_the_flights_facts_are_said_before_paying_in_the_offers_own_words(flying, client):
    words = text(sheet(client).text)
    assert "Economy Light" in words and "Included: Personal item (backpack/handbag)" in words
    assert "Extra, not sold here yet: Carry-on bag $33.66, Checked bag 23kg $50.48" in words
    assert "Not refundable: cancelling returns only some taxes." in words and "Not changeable: the dates cannot be moved." in words


def test_both_charges_are_said_up_front_with_the_flight_first(flying, client):
    words = text(sheet(client).text)
    m = re.search(r"Two charges from Nuitée: the flight (\$[\d,.]+), then the stay (\$[\d,.]+)", words)
    assert m and m[1] == money(flying.cents) and "The flight goes first" in words
    assert f"Continue · {money(flying.cents)}" in words or f"Continue · ${flying.cents // 100:,}" in words


def test_a_flight_price_that_moved_is_said_before_paying(flying, client, monkeypatch):
    flying.answers["verify"] = price(flying.cents + 4000)
    words = text(sheet(client).text)
    assert f"The flight’s price moved: it was {money(flying.cents)} on the square and is {money(flying.cents + 4000)} now." in words


def test_an_offer_that_is_gone_says_so_and_holds_no_room(flying, client):
    flying.answers["verify"] = (404, {"error": {"code": 40401, "description": "offer expired"}})
    r = sheet(client)
    assert "That fare is no longer available." in text(r.text) and flying.stays.calls(PREBOOK) == []


def test_a_flight_booked_here_is_never_a_link_to_another_site(flying, client):
    html = sheet(client).text
    assert "airline’s site" not in html and "Search flights on" not in html and "aviasales" not in html.lower()


# ---- the travellers form is the server's rule --------------------------------------------------------------------------------

def test_a_missing_or_wrong_traveller_field_opens_the_question_with_the_typed_words_and_asks_liteapi_nothing(flying, client):
    html = sheet(client).text
    r = confirm(client, html, t2_first="", t3_dob="2016-12-31", t1_sex="", email="nope")
    words = text(r.text)
    assert "Add traveller 3’s first name as it is on their ID." in words and "This kid was searched as 10: the birth date must make them 10 on Dec 12." in words
    assert "Choose the gender as on the ID: F, M or X." in words and "That does not look like an email address." in words
    assert 'value="Maya"' in r.text and 'value="Daniel"' in r.text and 'aria-invalid="true"' in r.text      # what was typed is kept
    assert flying.calls(FPREBOOK) == [] and flight_payments() == []
    assert 'data-step="0"' in r.text      # the travellers question opens first


def test_hostile_words_in_a_name_come_back_escaped_and_reach_no_one(flying, client):
    html = sheet(client).text
    r = confirm(client, html, first="<script>alert(1)</script>")
    assert "<script>alert(1)" not in r.text and flying.calls(FPREBOOK) == []


def test_a_tick_is_the_servers_rule_too(flying, client):
    r = confirm(client, sheet(client).text, agree="")
    assert "Tick the box to say you have read the fare and hotel rules." in text(r.text) and flying.calls(FPREBOOK) == []


def test_an_absurd_form_is_cut_not_read_whole(flying, client):
    html = sheet(client).text
    r = confirm(client, html, **{f"junk{i}": "x" * 5000 for i in range(600)})
    assert r.status_code == 200 and flying.calls(FPREBOOK) != []      # the known fields are read, the rest dropped


# ---- the flight's payment form comes first -------------------------------------------------------------------------------------

def test_a_complete_form_prebooks_the_flight_with_the_travellers_and_answers_its_payment_form(flying, client):
    html = sheet(client).text
    r = confirm(client, html)
    words = text(r.text)
    assert "Pay for your flight" in words and 'data-flight="1"' in r.text and "Two charges from Nuitée:" in words
    sent = flying.calls(FPREBOOK)
    assert len(sent) == 1 and sent[0]["usePaymentSdk"] is True and sent[0]["sessionId"].startswith("session_")
    assert [(p["passengerType"], p["firstName"], p["birthday"]) for p in sent[0]["passengers"]] == [(0, "Maya", "1985-04-12"), (0, "Daniel", "1983-09-03"), (1, "Leo", "2019-06-01"), (1, "Zoe", "2016-03-15")]
    assert sent[0]["contact"] == {"firstName": "Maya", "lastName": "Okafor", "email": "maya.okafor@example.com", "phoneCountryCode": "1", "phoneNumber": "4155550100"}
    assert re.search(r'data-return="http://testserver/plan/matrix/book/flight/return\?token=[A-Za-z0-9_-]+"', r.text) and 'data-secret="[secretKey]"' in r.text
    assert flying.calls(FBOOK) == [] and flying.stays.calls(BOOK) == []      # nothing is booked until a card has paid
    rows = flight_payments()
    assert len(rows) == 1 and (rows[0]["status"], rows[0]["charge_cents"], rows[0]["stay_token"], rows[0]["route"]) == ("paying", flying.cents, token(html), "SFO to SAN")
    assert "[secretKey]" not in str(rows[0])
    with ses.family(person()) as fam:
        stay = familydb.rows(fam.db, "SELECT * FROM matrix_payments")[0]
    assert (stay["status"], stay["guest_first"], stay["guest_phone"]) == ("paying", "Maya", "+14155550100")      # the stay's guest is the lead traveller, kept for after the flight


def test_the_sheet_never_renders_a_card_field_of_ours_for_the_flight(flying, client):
    r = confirm(client, sheet(client).text)
    assert not re.search(r'(autocomplete="cc-|name="[^"]*(card|cvc|cvv)[^"]*")', r.text, re.I)


def test_a_flight_whose_price_moved_while_held_is_shown_again_and_nothing_is_paid(flying, client):
    html = sheet(client).text
    flying.answers["prebook"] = lambda doc: doc["data"][0].__setitem__("price", (flying.cents + 3000) / 100)
    r = confirm(client, html)
    assert f"The flight’s price moved while we held it: it is {money(flying.cents + 3000)} now. Look it over and press Continue again." in text(r.text)
    assert 'data-pay-root' not in r.text and flight_payments() == []


def test_a_flight_prebook_liteapi_refuses_says_nothing_was_booked_and_saves_nothing(flying, client):
    html = sheet(client).text
    flying.answers["prebook"] = (400, {"error": {"code": 43002, "description": "invalid passenger"}})
    r = confirm(client, html)
    assert "Nothing was booked or charged." in text(r.text) and flight_payments() == [] and 'data-pay-root' not in r.text


def test_a_stale_token_is_refused_before_anything_is_asked(flying, client):
    r = confirm(client, "name=\"token\" value=\"not-a-held-room\"")
    assert "That room check has expired" in text(r.text) and flying.calls(FPREBOOK) == []


# ---- the return books the flight once and shows the stay's form ----------------------------------------------------------------

def paid_flight(client, **over):
    html = sheet(client).text
    r = confirm(client, html, **over)
    return html, token(html), r


def test_the_flights_return_books_it_with_the_transaction_id_and_shows_the_stays_own_form(flying, client):
    html, tok, _ = paid_flight(client)
    r = client.get(f"{RETURN}?token={tok}&redirect_status=succeeded")
    words = text(r.text)
    assert r.status_code == 200 and "Your flight is booked" in words and "SFO to SAN" in words
    assert flying.calls(FBOOK) == [{"prebookId": "01a1effe-2d7f-78b4-9e13-1596fd089221", "payment": {"method": "TRANSACTION_ID", "transactionId": "tr_cts_HX7MNE9cTvRSWyWn_QAcm"}}]
    assert "ACC_CREDIT_CARD" not in str(flying.asked)
    assert "FH-26B-1VO6TJ6Z" in words and "JSS7LG" not in html      # LiteAPI's short reference is on the pass; the airline's locator once LiteAPI gives it
    assert "Tickets issued: the airline has confirmed" in words and "Airline booking reference" in words and "ND 50CVYQ" in words      # asked once on the way in
    assert "Now pay for your stay" in words and "The second of two charges from Nuitée" in words
    assert re.search(r'data-return="http://testserver/plan/matrix/book/return\?token=' + re.escape(tok) + '"', r.text) and 'data-secret="[secretKey]"' in r.text
    row = booked_flights()[0]
    assert (row["status"], row["trip_id"] != "", row["total_cents"], row["sample"]) == ("CONFIRMED", True, 56907, 0)
    assert flight_payments()[0]["travellers"] == "" and "Okafor" not in str(flight_payments())      # the passengers are gone once it is booked


def test_a_reload_books_nothing_again(flying, client):
    _, tok, _ = paid_flight(client)
    client.get(f"{RETURN}?token={tok}&redirect_status=succeeded")
    r = client.get(f"{RETURN}?token={tok}&redirect_status=succeeded")
    assert "Your flight is booked" in text(r.text) and len(flying.calls(FBOOK)) == 1 and len(booked_flights()) == 1


def test_a_payment_the_processor_says_failed_books_nothing(flying, client):
    _, tok, _ = paid_flight(client)
    r = client.get(f"{RETURN}?token={tok}&redirect_status=failed")
    assert r.status_code == 402 and "nothing was booked or charged" in text(r.text) and flying.calls(FBOOK) == [] and booked_flights() == []


def test_a_form_nobody_paid_says_so_and_books_nothing(flying, client):
    _, tok, _ = paid_flight(client)
    flying.answers["book"] = (400, {"error": {"code": 2014, "description": "payment not completed"}})
    r = client.get(f"{RETURN}?token={tok}")
    assert r.status_code == 402 and "the payment is not complete yet" in text(r.text) and booked_flights() == []
    flying.answers["book"] = "book"
    assert client.get(f"{RETURN}?token={tok}").status_code == 200 and len(booked_flights()) == 1      # paid after all


def test_a_token_that_is_not_ours_or_not_a_token_books_nothing(flying, client):
    assert client.get(f"{RETURN}?token=abc", follow_redirects=False).headers["location"] == "/plan/ask"
    r = client.get(f"{RETURN}?token=notaprebookedtoken123")
    assert r.status_code == 404 and flying.calls(FBOOK) == []


def test_signed_out_the_flights_return_goes_to_sign_in_and_back(flying, client):
    _, tok, _ = paid_flight(client)
    client.cookies.clear()
    r = client.get(f"{RETURN}?token={tok}", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/signin") and flying.calls(FBOOK) == []


def test_the_booked_flight_is_on_the_trip_as_locked_legs_and_asks_nothing_twice(flying, client):
    _, tok, _ = paid_flight(client)
    client.get(f"{RETURN}?token={tok}")
    client.get(f"{RETURN}?token={tok}")
    with ses.family(person()) as fam:
        trip_id = fam.trip_id
    plan = importer.plan_of(person(), trip_id)
    assert [(leg.origin, leg.dest, leg.confirmation, leg.booked_on) for leg in plan.legs] == [("SFO", "SAN", "FH-26B-1VO6TJ6Z", "LiteAPI"), ("SAN", "SFO", "FH-26B-1VO6TJ6Z", "LiteAPI")]
    for day, block in (("2026-12-12", "b-out"), ("2026-12-16", "b-back")):      # the outbound and the return, locked on their days, each opening its booking
        page = client.get(f"/trip/plan?day={day}").text
        assert f"/trip/booking?block={block}" in page, day


def test_the_stay_is_paid_next_and_the_pass_shows_both(flying, client):
    html, tok, _ = paid_flight(client)
    client.get(f"{RETURN}?token={tok}")
    r = client.get(f"{STAY_RETURN}?token={tok}")
    words = text(r.text)
    assert "You’re booked" in words and "Flight" in words and "SFO to SAN" in words and "FH-26B-1VO6TJ6Z" in words and "uuJxfM0--" in words
    assert len(flying.stays.calls(BOOK)) == 1 and len(flying.calls(FBOOK)) == 1


def test_if_the_stay_fails_after_the_flight_the_page_says_the_flight_is_booked_and_what_to_do(flying, client):
    _, tok, _ = paid_flight(client)
    client.get(f"{RETURN}?token={tok}")
    flying.stays.answers["book"] = "book_unpaid.json"
    r = client.get(f"{STAY_RETURN}?token={tok}")
    words = text(r.text)
    assert "Your flight SFO to SAN is booked" in words and "only the stay is not" in words and "cancel the flight" in words
    assert 'data-see-flight="1"' in r.text and len(booked_flights()) == 1


def test_a_lost_hold_after_the_flight_says_the_flight_is_booked_and_offers_the_square_again(flying, client):
    _, tok, _ = paid_flight(client)
    mb.forget()      # the process restarted: the held room and its form key are gone
    r = client.get(f"{RETURN}?token={tok}")
    words = text(r.text)
    assert "Your flight is booked" in words and "Your room is no longer held" in words and "Now pay for your stay" not in words
    link = re.search(r"<a[^>]*data-try-stay[^>]*>", r.text)
    assert link and 'href="/plan/matrix/square?' in link[0]      # the square again, with its own words


def test_a_viewer_cannot_book_a_flight_through_the_return(flying, client, monkeypatch):
    from gitaway import access
    _, tok, _ = paid_flight(client)
    monkeypatch.setattr(access, "request_role", lambda: "viewer")
    r = client.get(f"{RETURN}?token={tok}")
    assert r.status_code == 403 and flying.calls(FBOOK) == []


# ---- modes ------------------------------------------------------------------------------------------------------------------

def test_the_kill_switch_books_no_flight_and_asks_liteapi_nothing(flying, client, monkeypatch):
    monkeypatch.setattr(auth, "production", lambda: True)
    monkeypatch.setenv("GITAWAY_LIVE_BOOKING", "0")
    r = client.post("/plan/matrix/book", data=FORM, headers=FRAG)
    assert r.status_code == 403 and "Booking opens soon" in text(r.text) and flying.asked == [] and flying.stays.asked == []


def test_a_live_key_off_production_plays_a_sample_flight_and_asks_liteapi_nothing_about_it(client, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setenv("LITEAPI_KEY", LIVE)
    monkeypatch.delenv("GITAWAY_LIVE_BOOKING", raising=False)
    monkeypatch.setattr(auth, "production", lambda: False)
    stays = Live()
    fly = Fly(other=stays)
    monkeypatch.setattr(liteapi, "TRANSPORT", fly)
    sign_in(client)
    html = client.post("/plan/matrix/book", data=FORM, headers=FRAG).text
    assert fly.asked == [] and "Sample flight booking: nothing is booked or charged" in text(html) and "Who is the lead guest?" in text(html)


@pytest.fixture
def sample(client, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "1")
    sign_in(client)


def test_a_sample_square_plays_a_labelled_sample_flight_with_no_call(sample, client):
    html = client.post("/plan/matrix/book", data=FORM, headers=FRAG).text
    assert "Sample flight booking: nothing is booked or charged" in text(html)
    r = client.post("/plan/matrix/book/confirm", data={**FORM, "token": token(html), "first": "Anne-Marie", "last": "O’Neil", "email": "anne@example.com", "agree": "on"}, headers=FRAG)
    words = text(r.text)
    assert 'data-at="booked"' in r.text[:300] and "Sample flight booking: nothing is booked or charged" in words and "Flight" in words
    rows = booked_flights()
    assert len(rows) == 1 and rows[0]["sample"] == 1 and rows[0]["booking_id"].startswith("SAMPLE-")
    with ses.family(person()) as fam:
        trip_id = fam.trip_id
    assert len(importer.plan_of(person(), trip_id).legs) == 2


def test_pressing_book_twice_on_a_sample_square_adds_the_flight_once(sample, client):
    html = client.post("/plan/matrix/book", data=FORM, headers=FRAG).text
    data = {**FORM, "token": token(html), "first": "Anne-Marie", "last": "O’Neil", "email": "anne@example.com", "agree": "on"}
    client.post("/plan/matrix/book/confirm", data=data, headers=FRAG)
    client.post("/plan/matrix/book/confirm", data=data, headers=FRAG)
    assert len(booked_flights()) == 1
    with ses.family(person()) as fam:
        trip_id = fam.trip_id
    assert len(importer.plan_of(person(), trip_id).legs) == 2


# ---- the booking page: status, then the cancel with the quote first ------------------------------------------------------------

def booked_trip(client):
    _, tok, _ = paid_flight(client)
    client.get(f"{RETURN}?token={tok}")
    return tok


def the_page(client):
    return client.get("/trip/booking?block=b-out")


def test_the_flights_booking_page_shows_its_status_references_and_fare_rules(flying, client):
    booked_trip(client)
    r = the_page(client)
    words = text(r.text)
    assert r.status_code == 200 and "Tickets issued: the airline has confirmed" in words and "FH-26B-1VO6TJ6Z" in words and "ND 50CVYQ" in words
    assert "Economy Light · Not refundable: cancelling returns only some taxes. Not changeable: the dates cannot be moved." in words
    assert "Booked and paid through Nuitée (LiteAPI), the merchant of record." in words and "See what cancelling would cost" in words and "Cancel this flight" not in words


def test_a_flight_still_waiting_says_waiting_for_the_airline(flying, client):
    flying.answers["booking"] = status("PENDING_CONFIRMATION")
    booked_trip(client)
    assert "Waiting for the airline to confirm your tickets" in text(the_page(client).text)


def test_cancelling_shows_the_quote_in_money_first_and_cancels_nothing(flying, client):
    booked_trip(client)
    row = booked_flights()[0]
    r = client.post("/trip/booking/flight/cancel", data={"booking": row["booking_id"], "step": "quote", "next": "/trip/booking?block=b-out"}, headers={"origin": "http://testserver"}, follow_redirects=True)
    words = text(r.text)
    assert "If you cancel now: $71.14 comes back to the card you paid with, and cancelling costs $497.94." in words and "Cancel this flight" in words
    assert [c for c in flying.asked if c[0] == CANCELS and c[2] == {}] == []      # the quote asked LiteAPI (a GET), nothing was cancelled


def test_the_confirm_cancels_on_the_quote_and_says_what_liteapi_reported(flying, client):
    booked_trip(client)
    row = booked_flights()[0]
    head = {"origin": "http://testserver"}
    nxt = "/trip/booking?block=b-out"
    client.post("/trip/booking/flight/cancel", data={"booking": row["booking_id"], "step": "quote", "next": nxt}, headers=head)
    r = client.post("/trip/booking/flight/cancel", data={"booking": row["booking_id"], "step": "confirm", "sure": "1", "next": nxt}, headers=head, follow_redirects=True)
    words = text(r.text)
    assert "Cancelled. LiteAPI charged $497.94 for cancelling, and $71.14 comes back to the card you paid with." in words and "Cancel this flight" not in words
    assert len([c for c in flying.asked if c[0] == CANCELS and c[2] == {}]) == 1
    with ses.family(person()) as fam:
        trip_id = fam.trip_id
    assert [leg.booked_on for leg in importer.plan_of(person(), trip_id).legs] == ["Cancelled on LiteAPI"] * 2


def test_a_confirm_without_a_quote_or_the_tick_cancels_nothing(flying, client):
    booked_trip(client)
    row = booked_flights()[0]
    head, nxt = {"origin": "http://testserver"}, "/trip/booking?block=b-out"
    r = client.post("/trip/booking/flight/cancel", data={"booking": row["booking_id"], "step": "confirm", "sure": "1", "next": nxt}, headers=head, follow_redirects=True)
    assert "That quote is out of date. See what cancelling would cost again, then confirm." in text(r.text)
    client.post("/trip/booking/flight/cancel", data={"booking": row["booking_id"], "step": "quote", "next": nxt}, headers=head)
    r = client.post("/trip/booking/flight/cancel", data={"booking": row["booking_id"], "step": "confirm", "next": nxt}, headers=head, follow_redirects=True)
    assert "Tick the box to say you mean to cancel this flight." in text(r.text)
    assert [c for c in flying.asked if c[0] == CANCELS and c[2] == {}] == []


def test_a_cancel_liteapi_has_accepted_says_pending(flying, client):
    booked_trip(client)
    row = booked_flights()[0]
    head, nxt = {"origin": "http://testserver"}, "/trip/booking?block=b-out"
    flying.answers["cancel"] = (202, {"data": {"bookingId": BOOKING_ID, "status": "CANCELLATION_PENDING"}})
    client.post("/trip/booking/flight/cancel", data={"booking": row["booking_id"], "step": "quote", "next": nxt}, headers=head)
    r = client.post("/trip/booking/flight/cancel", data={"booking": row["booking_id"], "step": "confirm", "sure": "1", "next": nxt}, headers=head, follow_redirects=True)
    assert "Cancellation requested. LiteAPI has accepted it and the airline has not finished." in text(r.text)


def test_a_cross_site_form_or_a_stranger_cancels_nothing(flying, client):
    booked_trip(client)
    row = booked_flights()[0]
    r = client.post("/trip/booking/flight/cancel", data={"booking": row["booking_id"], "step": "quote"}, headers={"origin": "https://evil.example"})
    assert r.status_code == 403
    client.cookies.clear()
    r = client.post("/trip/booking/flight/cancel", data={"booking": row["booking_id"], "step": "quote"}, headers={"origin": "http://testserver"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/signin") and [c for c in flying.asked if c[0] == CANCELS] == []


def test_the_viewer_sees_the_status_and_no_cancel_button(flying, client, monkeypatch):
    from gitaway import access
    booked_trip(client)
    monkeypatch.setattr(access, "request_role", lambda: "viewer")
    words = text(the_page(client).text)
    assert "Tickets issued: the airline has confirmed" in words and "See what cancelling would cost" not in words


def test_a_sample_flight_shows_its_label_and_never_a_cancel(sample, client):
    html = client.post("/plan/matrix/book", data=FORM, headers=FRAG).text
    client.post("/plan/matrix/book/confirm", data={**FORM, "token": token(html), "first": "Anne-Marie", "last": "O’Neil", "email": "anne@example.com", "agree": "on"}, headers=FRAG)
    words = text(the_page(client).text)
    assert "Sample flight booking: nothing is booked or charged" in words and "cancelling" not in words.lower()


def test_today_shows_the_booked_flight_on_its_airports_clocks(flying, client):
    booked_trip(client)
    from gitaway import session as s2, today as td
    trip = td.from_booking(person(), s2.booking(person()))
    assert [(f.name, f.origin, f.dest, f.confirmation) for f in trip.flights] == [("Nuitée Air 6278", "SFO", "SAN", "FH-26B-1VO6TJ6Z"), ("Nuitée Air 3060", "SAN", "SFO", "FH-26B-1VO6TJ6Z")]
    assert "Nuitée Air 6278" in text(client.get("/trip/today?day=2026-12-18").text)


def test_the_worker_follows_a_pending_flight_to_confirmed_and_sends_one_email(flying, client, monkeypatch):
    from datetime import datetime, timedelta, timezone

    from gitaway import bookingjobs, bookingmail
    sent = []
    for k, v in {"SMTP_HOST": "smtp.resend.com", "SMTP_USER": "resend", "SMTP_PASSWORD": "re_not_a_key", "SMTP_MAIL_FROM": "GitAway <trips@gitaway.me>", "SMTP_SSL": "true", "SMTP_PORT": "465"}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(bookingmail, "deliver", lambda to, mail: sent.append((to, mail.subject)))
    monkeypatch.setattr(bookingmail, "_spawn", lambda fn, *a: fn(*a))
    flying.answers["booking"] = status("PENDING_CONFIRMATION")
    tok = paid_flight(client)[1]
    client.get(f"{RETURN}?token={tok}")
    assert booked_flights()[0]["status"] == "PENDING_CONFIRMATION" and len(sent) == 1      # the booked email, saying it waits for the airline
    sent.clear()
    flying.answers["booking"] = "booking_get"
    bookingjobs.run_once(datetime.now(timezone.utc) + timedelta(minutes=5))
    assert booked_flights()[0]["status"] == "CONFIRMED" and [s[1] for s in sent] == ["Tickets issued: flight SFO to SAN, Sat, Dec 12, 2026"]
    bookingjobs.run_once(datetime.now(timezone.utc) + timedelta(minutes=30))
    assert [m[1] for m in sent if m[1].startswith("Tickets issued")] == ["Tickets issued: flight SFO to SAN, Sat, Dec 12, 2026"]      # still one


def test_the_flight_never_asks_the_worker_to_book(flying, client):
    from datetime import datetime, timedelta, timezone

    from gitaway import bookingjobs
    paid_flight(client)      # the form was opened, nobody returned
    bookingjobs.run_once(datetime.now(timezone.utc) + timedelta(hours=3))
    assert flying.calls(FBOOK) == [] and booked_flights() == []
