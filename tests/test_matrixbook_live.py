"""F-274: the booking sheet with LiteAPI's payment form (a live key where real booking is on; the sandbox with GITAWAY_SANDBOX_FORM=1 runs the same path). LiteAPI's answers are the
sandbox's own recordings (tests/fixtures/liteapi_pay). The card is LiteAPI's form's: no page here carries a card field, a card number or LiteAPI's keys beyond the form's own."""
import json
import re

import pytest

from gitaway import auth, familydb, liteapi, matrixbook as mb, session as ses
from gitaway.pages import matrixbook as page
from tests.test_liteapi import KEY, Fake
from tests.test_liteapi_pay import FIX, LIVE
from tests.test_matrixbook_page import FORM, FRAG, MATRIX, person, sign_in, stays_booked, text, token, trip_lodging
from tests.test_liteapi_book import BOOK, PREBOOK

SECRET = "[secretKey]"
GUEST = {"first": "Anne-Marie", "last": "O’Neil", "email": "anne@example.com", "phone": "+1 415 555 0100", "agree": "on", "req": "Quiet room", "arrive": "Evening"}
CANCEL = "https://book.liteapi.travel/v3.0/bookings/"


def recording(name, nights=True, shown=None, discount=0.0):
    """A recording as the square's nights; priced as the square shows its stay (`shown` dollars with the $120 fee paid at the hotel), less a voucher's discount."""
    doc = json.loads((FIX / name).read_text())
    raw = json.dumps(doc["body"]).replace("2026-12-16", "2026-12-12").replace("2026-12-19", "2026-12-16") if nights else json.dumps(doc["body"])
    body = json.loads(raw)
    if shown is not None and "price" in body.get("data", {}):
        body["data"]["price"] = round(shown - 120, 2)
        body["data"]["sellingPriceToUser"] = round(shown - 120 - discount, 2)
        if discount:
            body["data"]["voucherTotalAmount"] = discount
    return doc["status"], json.dumps(body).encode()


class Live(Fake):
    """The searches from the recordings, and the payment-form calls from the payment recordings; every call remembered with its method."""

    def __init__(self, **answers):
        super().__init__()
        self.answers = {"prebook": None, "book": "book_nonrefundable.json", "cancel": "cancel_nonrefundable.json", **answers}
        self.shown = None

    def __call__(self, url, headers, body, timeout, method=""):
        if url in (PREBOOK, BOOK) or url.startswith(CANCEL):
            sent = json.loads(body) if body else None
            self.asked.append((url, headers, sent, method))
            what = "prebook" if url == PREBOOK else "book" if url == BOOK else "cancel"
            if what == "prebook":
                voucher = (sent or {}).get("voucherCode")
                name = self.answers["prebook"] or ("prebook_voucher.json" if voucher == "F274SANDBOX" else "prebook_bad_voucher.json" if voucher else "prebook_sdk.json")
                status, payload = recording(name, shown=self.shown, discount=round((self.shown - 120) * 0.1, 2) if name == "prebook_voucher.json" and self.shown else 0)
            elif what == "book":
                status, payload = recording(self.answers["book"], nights=False)
            else:
                status, payload = recording(self.answers["cancel"], nights=False)
            return status, "application/json", payload
        return super().__call__(url, headers, body, timeout)

    def calls(self, url):
        return [c[2] for c in self.asked if c[0] == url]


@pytest.fixture(autouse=True)
def _fresh():
    mb.forget()


@pytest.fixture
def real(client, monkeypatch):
    """A live key where real booking is on, signed in. The shown price of the square is read, and the prebooks are priced like it."""
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setenv("LITEAPI_KEY", LIVE)
    monkeypatch.setenv("GITAWAY_LIVE_BOOKING", "1")
    monkeypatch.setattr(auth, "production", lambda: False)
    fake = Live()
    monkeypatch.setattr(liteapi, "TRANSPORT", fake)
    from tests.flight_support import strip_flight_offers
    strip_flight_offers(monkeypatch)      # these tests are about the stay: its flight is the labelled sample (the flight's own tests: tests/test_matrixbook_flight.py)
    sign_in(client)
    panel = client.get("/plan/matrix/tile?" + MATRIX.split("?")[1] + "&lane=sandiego&w=2026-12-12").json()["drawer"]
    fake.shown = int(re.search(r'data-c="(\d+)"', re.search(r'<button[^>]*data-room="0"[^>]*>', panel).group(0)).group(1)) / 100
    fake.asked.clear()
    return fake


def sheet(client):
    return client.post("/plan/matrix/book", data=FORM, headers=FRAG).text


def pay_pane(client, html=None, **over):
    html = html or sheet(client)
    return html, client.post("/plan/matrix/book/confirm", data={**FORM, "token": token(html), **GUEST, **over}, headers=FRAG)


def payments():
    with ses.family(person()) as fam:
        return familydb.rows(fam.db, "SELECT * FROM matrix_payments")


# ---- the sheet: prebook with the form, ids saved, the words ---------------------------------------------------------------------------

def test_the_sheet_prebooks_for_the_payment_form_saves_the_ids_and_says_who_sells_it(real, client):
    html = sheet(client)
    words = text(html)
    assert real.calls(PREBOOK) == [{"offerId": real.calls(PREBOOK)[0]["offerId"], "usePaymentSdk": True}] and len(real.calls(PREBOOK)) == 1
    assert "Booked and paid through Nuitée (LiteAPI), the merchant of record. GitAway never sees your card." in words and "Non-refundable: if you cancel, nothing comes back." in words
    assert "Have a code?" in words and "Continue · $" in words and "Your card is charged when you pay" in words
    rows = payments()
    assert len(rows) == 1 and (rows[0]["status"], rows[0]["prebook_id"], rows[0]["transaction_id"], rows[0]["charge_cents"]) == ("prebooked", "nXPI8qf8C", "tr_cts_j_DBi8RkjWF1hJDzmsryP", 72993)      # the square shows $849.93: $729.93 now and the $120 fee at the hotel
    assert rows[0]["policy"] == "Non-refundable: if you cancel, nothing comes back."
    for secret in ("nXPI8qf8C", "tr_cts_j_DBi8RkjWF1hJDzmsryP", SECRET):      # none of LiteAPI's keys is on the questions
        assert secret not in html


def test_a_real_booking_does_not_start_with_a_made_up_guest_and_asks_for_a_mobile_number(real, client):
    html = sheet(client)
    for name in ("first", "last", "email"):
        assert f'name="{name}" value=""' in html, name
    assert "Test" not in text(html).split("Who is the lead guest?")[1][:200] and "example.com" not in html and "this is the sandbox" not in html
    assert re.search(r'<input[^>]*name="phone"[^>]*\brequired\b', html) and "Mobile number" in text(html)


def test_the_sheet_never_renders_a_card_field_of_ours(real, client):
    for html in (sheet(client), pay_pane(client)[1].text):
        assert not re.search(r'<input[^>]*(autocomplete="cc-|cardnumber|name="(card|cc|cvc|cvv)")', html, re.I)


def test_a_square_in_the_sandbox_without_the_form_books_as_it_did(client, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    monkeypatch.delenv("GITAWAY_SANDBOX_FORM", raising=False)
    from tests.test_matrixbook_page import Sandbox
    fake = Sandbox()
    monkeypatch.setattr(liteapi, "TRANSPORT", fake)
    sign_in(client)
    html = client.post("/plan/matrix/book", data=FORM, headers=FRAG).text
    assert fake.calls(PREBOOK) == [{"offerId": fake.calls(PREBOOK)[0]["offerId"], "usePaymentSdk": False}] and "Book for $" in text(html) and "Continue to payment" not in html


# ---- the guest, then the payment form ------------------------------------------------------------------------------------------------

def test_the_guest_form_answers_with_liteapis_payment_form_and_nothing_is_booked_yet(real, client):
    html, r = pay_pane(client)
    words = text(r.text)
    assert 'data-at="pay"' in r.text and 'data-pay-root="1"' in r.text and f'data-secret="{SECRET}"' in r.text and 'data-key="live"' in r.text
    assert f'data-return="http://testserver/plan/matrix/book/return?token={token(html)}"' in r.text
    assert "Pay for your stay" in words and "Charged now" in words and "Booked and paid through Nuitée (LiteAPI), the merchant of record. GitAway never sees your card." in words and "Non-refundable" in words
    assert real.calls(BOOK) == [] and len(real.calls(PREBOOK)) == 1                    # no second prebook, no booking
    row = payments()[0]
    assert (row["status"], row["guest_first"], row["guest_last"], row["guest_email"], row["guest_phone"], row["guest_remarks"]) == (
        "paying", "Anne-Marie", "O’Neil", "anne@example.com", "+1 415 555 0100", "Quiet room. Arriving in the evening.")
    assert row["trip_id"] and stays_booked() == []                                  # the square became the family's trip; no stay is booked until the payment


def test_the_mobile_number_the_tick_and_the_guest_are_the_servers_rules_before_the_form_opens(real, client):
    html = sheet(client)
    said = {}
    for over, field in (({"phone": ""}, "phone"), ({"agree": ""}, "agree"), ({"email": "nope"}, "email"), ({"first": "<b>"}, "first")):      # four presses and the sheet: the limit is five a minute
        r = client.post("/plan/matrix/book/confirm", data={**FORM, "token": token(html), **GUEST, **over}, headers=FRAG)
        assert 'data-at="guest"' in r.text and 'data-pay-root' not in r.text, field
        said[field] = text(r.text)
    assert "Add a mobile number: the booking needs one." in said["phone"] and "Tick the box" in said["agree"] and "does not look like an email" in said["email"] and "letters only" in said["first"]
    assert payments()[0]["status"] == "prebooked" and real.calls(BOOK) == []


def test_a_guest_typed_hostile_words_come_back_escaped_and_never_reach_the_payment_pane(real, client):
    html = sheet(client)
    r = client.post("/plan/matrix/book/confirm", data={**FORM, "token": token(html), **GUEST, "first": '"><script>alert(1)</script>'}, headers=FRAG)
    assert "<script>alert" not in r.text and "&lt;script&gt;" in r.text or "letters only" in text(r.text)
    assert payments()[0]["guest_first"] in ("", None)


def test_another_squares_or_an_unknown_token_gets_no_payment_form(real, client):
    r = client.post("/plan/matrix/book/confirm", data={**FORM, "token": "not-a-held-room", **GUEST}, headers=FRAG)
    assert "expired or is not for this square" in text(r.text) and "data-pay-root" not in r.text and real.calls(BOOK) == []


# ---- after the payment form ------------------------------------------------------------------------------------------------------------

def paid(client):
    html, _ = pay_pane(client)
    return token(html), client.get(f"/plan/matrix/book/return?token={token(html)}&payment_intent=pi_x&redirect_status=succeeded")


def test_after_the_form_the_stay_is_booked_with_the_transaction_id_and_the_pass_is_drawn(real, client):
    tok, r = paid(client)
    words = re.sub(r"\s+", " ", text(r.text))
    assert r.status_code == 200 and "You’re booked" in words and "Booking id uuJxfM0--" in words and "Hotel confirmation test" in words
    assert "Booked and paid through Nuitée (LiteAPI), the merchant of record. GitAway never sees your card." in words and "Non-refundable" in words and 'href="/trip/plan?arrive=1"' in r.text
    sent = real.calls(BOOK)
    assert len(sent) == 1 and sent[0]["payment"] == {"method": "TRANSACTION_ID", "transactionId": "tr_cts_j_DBi8RkjWF1hJDzmsryP"} and sent[0]["prebookId"] == "nXPI8qf8C"
    assert sent[0]["holder"] == {"firstName": "Anne-Marie", "lastName": "O’Neil", "email": "anne@example.com", "phone": "+1 415 555 0100"}
    assert sent[0]["guests"][0]["remarks"] == "Quiet room. Arriving in the evening." and "ACC_CREDIT_CARD" not in json.dumps(real.asked)
    row = payments()[0]
    assert (row["status"], row["booking_id"], row["guest_email"], row["guest_phone"]) == ("booked", "uuJxfM0--", "", "")
    assert [(b["booking_id"], b["sample"], b["total_cents"]) for b in stays_booked()] == [("uuJxfM0--", 0, 84993)]
    assert [(h.confirmation, h.booked_on) for h in trip_lodging()] == [("uuJxfM0--", "LiteAPI")]
    assert "anne@example.com" not in r.text and "+1 415" not in r.text                  # the page says no more than the booking holds


def test_a_reload_of_the_return_page_shows_the_same_booking_and_books_nothing_again(real, client):
    tok, first = paid(client)
    again = client.get(f"/plan/matrix/book/return?token={tok}")
    assert again.status_code == 200 and "Booking id uuJxfM0--" in re.sub(r"\s+", " ", text(again.text))
    assert len(real.calls(BOOK)) == 1 and len(stays_booked()) == 1 and len(trip_lodging()) == 1


def test_a_payment_liteapi_does_not_have_says_do_not_pay_again_and_keeps_the_reference_for_another_try(real, client, monkeypatch):
    html, _ = pay_pane(client)
    real.answers["book"] = "book_unpaid.json"
    r = client.get(f"/plan/matrix/book/return?token={token(html)}")
    words = text(r.text)
    assert r.status_code == 502 and "Do not pay again" in words and "Payment reference: tr_cts_j_DBi8RkjWF1hJDzmsryP" in words
    assert stays_booked() == [] and payments()[0]["status"] == "paying"
    real.answers["book"] = "book_nonrefundable.json"
    assert "Booking id uuJxfM0--" in re.sub(r"\s+", " ", text(client.get(f"/plan/matrix/book/return?token={token(html)}").text))      # it arrived: the same reference books


def test_the_return_page_books_nothing_for_a_prebook_nobody_gave_a_guest_to(real, client):
    html = sheet(client)
    r = client.get(f"/plan/matrix/book/return?token={token(html)}")
    assert r.status_code == 404 and "We could not find that booking" in text(r.text) and real.calls(BOOK) == []


@pytest.mark.parametrize("tok", ["", "x", "../../etc", "a" * 41, "a b c d e f g h", "<script>"])
def test_a_bad_token_is_sent_back_to_the_search_and_asks_liteapi_nothing(real, client, tok):
    r = client.get("/plan/matrix/book/return", params={"token": tok}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/plan/ask" and real.calls(BOOK) == []


def test_signed_out_the_return_goes_to_sign_in_and_back(real, client):
    html, _ = pay_pane(client)
    client.post("/logout")
    r = client.get(f"/plan/matrix/book/return?token={token(html)}", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/signin?next=") and real.calls(BOOK) == []


def test_someone_elses_payment_is_not_theirs_to_finish(real, client):
    html, _ = pay_pane(client)
    client.post("/logout")
    sign_in(client, "sam")
    r = client.get(f"/plan/matrix/book/return?token={token(html)}")
    assert r.status_code in (404, 303, 502) and real.calls(BOOK) == [] and stays_booked() == []


def test_a_viewer_cannot_book_through_the_return_page(real, client, monkeypatch):
    html, _ = pay_pane(client)
    from gitaway import access
    monkeypatch.setattr(access, "request_role", lambda: "viewer")
    r = client.get(f"/plan/matrix/book/return?token={token(html)}")
    assert r.status_code == 403 and real.calls(BOOK) == []


# ---- have a code ----------------------------------------------------------------------------------------------------------------------

def code(client, html, text_="F274SANDBOX", **extra):
    return client.post("/plan/matrix/book/code", data={**FORM, "token": token(html), "code": text_, **extra})


def test_a_code_reprices_the_stay_and_only_the_checkout_shows_the_discount(real, client):
    html = sheet(client)
    assert "F274" not in html and re.search(r'<div[^>]*\bhidden\b[^>]*class="mxb-off"|<div[^>]*class="mxb-off"[^>]*\bhidden\b', html)      # the first sheet says nothing of a code: its discount row is hidden
    r = code(client, html)
    j = r.json()
    assert r.status_code == 200 and j["code"] == "F274SANDBOX" and j["token"] != token(html)
    assert j["discount"] == "$72.99" and j["said"] == "Code F274SANDBOX applied." and j["moved"] == ""
    assert real.calls(PREBOOK)[-1]["voucherCode"] == "F274SANDBOX" and real.calls(PREBOOK)[-1]["usePaymentSdk"] is True
    assert j["stay"] == "$776.94" and j["go"] == f"Continue · {j['stay']}"
    new = {r_["id"]: r_ for r_ in payments()}[j["token"]]
    assert (new["voucher_code"], new["discount_cents"], new["charge_cents"]) == ("F274SANDBOX", 7299, 65694)


def test_the_discounted_stay_is_what_the_card_pays_through_to_the_booking(real, client):
    html = sheet(client)
    j = code(client, html).json()
    r = client.post("/plan/matrix/book/confirm", data={**FORM, "token": j["token"], **GUEST}, headers=FRAG)
    assert "$656.94" in text(r.text) and 'data-pay-root="1"' in r.text
    client.get(f"/plan/matrix/book/return?token={j['token']}")
    assert real.calls(BOOK)[0]["prebookId"] == "3JH4qYGIc"


@pytest.mark.parametrize("typed, status", [("NOSUCHCODE", 422), ("a", 422), ("two words", 422), ("<script>", 422), ("x" * 40, 422)])
def test_a_code_that_is_not_valid_is_said_and_the_stay_is_unchanged(real, client, typed, status):
    html = sheet(client)
    r = code(client, html, typed)
    assert r.status_code == status and "error" in r.json() and "token" not in r.json()
    assert "<script>" not in r.text


def test_a_code_needs_the_held_room_the_form_and_a_person_signed_in(real, client):
    html = sheet(client)
    assert code(client, 'name="token" value="nope"').status_code == 409
    n = len(real.calls(PREBOOK))
    client.post("/logout")
    assert code(client, html).status_code == 401 and len(real.calls(PREBOOK)) == n


def test_removing_the_code_prebooks_the_stay_again_at_its_price(real, client):
    html = sheet(client)
    j = code(client, html, "").json()
    assert j["discount"] == "" and j["said"] == "Code removed." and "voucherCode" not in real.calls(PREBOOK)[-1]


# ---- the switch and the stand-in ---------------------------------------------------------------------------------------------------------

def test_switched_off_the_new_routes_do_nothing(real, client, monkeypatch):
    monkeypatch.setattr(auth, "production", lambda: True)
    monkeypatch.setenv("GITAWAY_LIVE_BOOKING", "0")
    n = len(real.asked)
    assert client.post("/plan/matrix/book/code", data={**FORM, "token": "t", "code": "X1"}).status_code == 400
    assert client.get("/plan/matrix/book/return?token=abcdefgh1234").status_code == 404      # nothing to finish: it asks LiteAPI nothing
    assert len(real.asked) == n


def test_switched_off_a_guest_who_already_paid_is_still_booked_by_the_return_page(real, client, monkeypatch):
    """D-848: the switch stops new prebooks; the return page and LiteAPI's TRANSACTION_ID book go on for a row the guest already paid."""
    html, _ = pay_pane(client)
    monkeypatch.setattr(auth, "production", lambda: True)
    monkeypatch.setenv("GITAWAY_LIVE_BOOKING", "0")
    r = client.get(f"/plan/matrix/book/return?token={token(html)}")
    assert r.status_code == 200 and "Booking id uuJxfM0--" in re.sub(r"\s+", " ", text(r.text)) and len(real.calls(BOOK)) == 1
    assert client.post("/plan/matrix/book", data=FORM, headers=FRAG).status_code == 403      # and nothing new is prebooked


def test_the_return_address_is_the_sites_own_in_production_never_the_requests_host(monkeypatch):
    class Req:
        base_url = "http://evil.example/"
    monkeypatch.setattr(auth, "production", lambda: True)
    monkeypatch.setenv("GITAWAY_PUBLIC_URL", "https://gitaway.me")
    assert page.return_url(Req(), "tok123") == "https://gitaway.me/plan/matrix/book/return?token=tok123"
    monkeypatch.setattr(auth, "production", lambda: False)
    assert page.return_url(Req(), "tok123") == "http://evil.example/plan/matrix/book/return?token=tok123"


def test_the_sandbox_with_the_form_switched_on_runs_the_same_path_with_the_sandbox_public_key(client, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    monkeypatch.setenv("GITAWAY_SANDBOX_FORM", "1")
    fake = Live()
    monkeypatch.setattr(liteapi, "TRANSPORT", fake)
    from tests.flight_support import strip_flight_offers
    strip_flight_offers(monkeypatch)
    sign_in(client)
    panel = client.get("/plan/matrix/tile?" + MATRIX.split("?")[1] + "&lane=sandiego&w=2026-12-12").json()["drawer"]
    fake.shown = int(re.search(r'data-c="(\d+)"', re.search(r'<button[^>]*data-room="0"[^>]*>', panel).group(0)).group(1)) / 100
    html, r = pay_pane(client)
    assert 'data-key="sandbox"' in r.text and "4242 4242 4242 4242" in text(r.text) and "Sandbox booking" in text(html)
    client.get(f"/plan/matrix/book/return?token={token(html)}")
    assert fake.calls(BOOK)[0]["payment"]["method"] == "TRANSACTION_ID"


def test_the_payment_script_is_loaded_by_the_sheets_script_from_one_address_and_no_page_names_it(real, client):
    """No page or fragment carries a <script src> of LiteAPI's: assets/js/matrixbook.js adds it, from this one address, only when the payment form opens (D-844)."""
    assert liteapi.PAYMENT_SDK == "https://payment-wrapper.liteapi.travel/dist/liteAPIPayment.js?v=a1"
    js = (page.__file__.rsplit("/gitaway/", 1)[0] + "/assets/js/matrixbook.js")
    source = open(js).read()
    assert source.count(liteapi.PAYMENT_SDK) == 1 and source.count("payment-wrapper") == 1
    for html in (sheet(client), pay_pane(client)[1].text, client.get(MATRIX).text):
        assert "payment-wrapper" not in html and "<script src=\"http" not in html


# ---- what is said and kept ----------------------------------------------------------------------------------------------------------------

def test_the_privacy_page_says_what_a_real_booking_sends_and_keeps(real, client):
    words = " ".join(text(client.get("/privacy").text).split())
    assert "Book is a real booking" in words and "never to GitAway, which never sees or keeps a card" in words and "at most seven days" in words and "sandbox" not in words.lower()


def test_the_payment_answers_are_never_cached(real, client):
    html = sheet(client)
    r = client.post("/plan/matrix/book/confirm", data={**FORM, "token": token(html), **GUEST}, headers=FRAG)
    page_r = client.post("/plan/matrix/book/confirm", data={**FORM, "token": token(html), **GUEST})      # without the script: a page of its own
    assert "no-store" in r.headers["cache-control"] and "no-store" in page_r.headers["cache-control"] and f'data-secret="{SECRET}"' in page_r.text
    tok, ret = paid(client)
    assert "no-store" in ret.headers["cache-control"]


def test_no_source_of_the_sheet_has_a_card_field_or_stores_a_card():
    """GitAway never renders, reads or keeps a card (D-842): the sources that draw and script the sheet and the tables hold no card words."""
    from pathlib import Path
    root = Path(__file__).parent.parent
    for name in ("gitaway/pages/matrixbook.py", "assets/js/matrixbook.js", "gitaway/matrixbook.py", "gitaway/familydb_matrix.py"):
        source = (root / name).read_text().lower()
        assert not re.search(r"cc-number|cc-csc|cc-exp|cardnumber|card_number|cvc|cvv", source), name
