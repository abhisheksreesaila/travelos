"""F-274 review fixes (D-848, D-849): the booking worker finishes paid-but-unbooked stays whatever the kill switch says and purges every family's kept data daily; a stuck count on /admin;
the report-only CSP on the matrix; the daily cap on wrong codes; a partial refund said with its fee; the margin proven through prebook; small hardening (same-site cancel, another's row,
the privacy words)."""
import json
import logging
import re
from datetime import datetime, timedelta, timezone

import pytest

from gitaway import auth, bookingjobs, csp, familydb, liteapi, matrixbook as mb, session as ses
from gitaway.pages import staycancel
from tests.test_liteapi_pay import FIX, Pay
from tests.test_matrixbook_live import FORM, FRAG, GUEST, code, pay_pane, payments, real, sheet, token  # noqa: F401 (real is a fixture)
from tests.test_matrixbook_page import person, stays_booked, text
from tests.test_matrixbook_pay import DAYS, PART, family, live, pay, prepared  # noqa: F401 (fixtures)


def aged(db, token_, minutes=0, days=0):
    old = (datetime.now(timezone.utc) - timedelta(minutes=minutes, days=days)).isoformat(timespec="seconds")
    familydb.run(db, "UPDATE matrix_payments SET updated_at = :t, created_at = :t WHERE id = :i", t=old, i=token_)
    db.conn.commit()


# ---- M1: the worker --------------------------------------------------------------------------------------------------------------------

def test_a_payment_stuck_for_ten_minutes_is_booked_by_the_worker_even_with_booking_switched_off(live, family, monkeypatch):
    db, user = family
    prep = prepared(live)
    pay(db, user, prep)
    monkeypatch.setenv("GITAWAY_LIVE_BOOKING", "0")
    assert bookingjobs.run_once() == 0 and not [1 for u, *_ in live.asked if u.endswith("/rates/book")]      # five seconds old: the guest may still be paying
    aged(db, prep.token, minutes=11)
    assert bookingjobs.stuck_count() == 1
    assert bookingjobs.run_once() == 1
    sent = [b for u, _, b, _ in live.asked if u.endswith("/rates/book")]
    assert len(sent) == 1 and sent[0]["payment"] == {"method": "TRANSACTION_ID", "transactionId": "tr_cts_j_DBi8RkjWF1hJDzmsryP"} and "ACC_CREDIT_CARD" not in json.dumps(live.asked)
    assert [(r["booking_id"], r["sample"]) for r in familydb.rows(db, "SELECT * FROM matrix_bookings")] == [("uuJxfM0--", 0)]
    assert mb.payment(db, prep.token)["status"] == "booked" and bookingjobs.stuck_count() == 0
    assert bookingjobs.run_once() == 0 and len([1 for u, *_ in live.asked if u.endswith("/rates/book")]) == 1      # and never twice


def test_a_payment_liteapi_still_refuses_stays_stuck_and_is_counted(live, family, monkeypatch):
    db, user = family
    prep = prepared(live)
    pay(db, user, prep)
    aged(db, prep.token, minutes=30)
    monkeypatch.setattr(liteapi, "TRANSPORT", Pay(book="book_unpaid.json"))
    assert bookingjobs.run_once() == 0 and bookingjobs.stuck_count() == 1 and mb.payment(db, prep.token)["status"] == "paying"


def test_the_admin_page_counts_the_stuck_payments(live, family, client, monkeypatch):
    db, user = family
    prep = prepared(live)
    pay(db, user, prep)
    monkeypatch.setenv("GITAWAY_ADMIN_EMAILS", "ari.rivera@example.com")
    stuck = lambda html: re.search(r'id="ad-stuck"[^>]*>\s*(\d+)\s*<', html).group(1)
    assert stuck(client.get("/admin").text) == "0"      # just paid: not stuck yet
    aged(db, prep.token, minutes=30)
    html = client.get("/admin").text
    assert stuck(html) == "1" and "Paid, not booked" in html


def test_the_worker_is_started_with_the_app():
    from pathlib import Path
    import main
    assert "on_startup=[morning.start, draftjobs.start, planforme.start, bookingjobs.start]" in Path(main.__file__).read_text()


# ---- M2: the daily purge over every family --------------------------------------------------------------------------------------------

def test_an_eight_day_old_guest_is_blanked_for_a_family_that_never_prebooks_again(live, family):
    db, user = family
    prep = prepared(live)
    pay(db, user, prep)
    aged(db, prep.token, days=8)
    assert mb.payment(db, prep.token)["guest_email"] == "test.traveler@example.com"      # nobody has asked yet: nothing runs by itself in a request
    bookingjobs.stop()      # a fresh worker: its first pass purges
    bookingjobs.run_once()
    kept = mb.payment(db, prep.token)
    assert (kept["guest_first"], kept["guest_email"], kept["guest_phone"], kept["guest_remarks"]) == ("", "", "", "") and kept["transaction_id"]
    assert bookingjobs._state["purged"] is not None


def test_the_purge_runs_once_an_hour_not_every_pass(live, family, monkeypatch):
    db, user = family
    calls = []
    monkeypatch.setattr(mb, "purge", lambda d: calls.append(1))
    bookingjobs.stop()
    now = datetime.now(timezone.utc)
    bookingjobs.run_once(now)
    first = len(calls)      # one purge a family the test data folder holds
    assert first >= 1
    bookingjobs.run_once(now + timedelta(minutes=30))
    assert len(calls) == first
    bookingjobs.run_once(now + timedelta(hours=1, minutes=1))
    assert len(calls) == 2 * first


# ---- M3: the report-only policy -----------------------------------------------------------------------------------------------------------

def test_the_matrix_reports_what_a_script_policy_would_block_and_blocks_nothing(client):
    r = client.get("/plan/matrix?to=San+Diego&home=SFO&d=2026-12-12&r=2026-12-16&a=2&k=7,10&x=2")
    policy = r.headers["content-security-policy-report-only"]
    assert policy == csp.POLICY and r.headers["content-security-policy"] == "frame-ancestors 'none'"      # the enforced one is as it was
    for host in ("https://payment-wrapper.liteapi.travel", "https://js.stripe.com", "https://*.hcaptcha.com", "https://m.stripe.network", "https://r.stripe.com"):
        assert host in policy, host
    assert "script-src 'self' https://payment-wrapper" in policy and "'unsafe-inline' https://payment" not in policy.split("script-src")[1].split(";")[0]
    inline = [t for t in re.findall(r"<script(?![^>]*\bsrc=)[^>]*>", r.text) if "application/json" not in t]
    assert inline == []      # no inline script runs on the page (two data blocks of JSON do not execute): no nonce or hash is needed


def test_other_pages_carry_no_report_only_policy(client):
    for path in ("/", "/signin", "/privacy", "/healthz"):
        assert "content-security-policy-report-only" not in client.get(path).headers, path
    assert csp.applies("/plan/matrix") and csp.applies("/plan/matrix/tile") and not csp.applies("/plan/matrixx") and not csp.applies("/plan/ask")


# ---- L1: wrong codes -------------------------------------------------------------------------------------------------------------------------

def test_after_thirty_wrong_codes_in_a_day_the_code_box_is_off_and_it_is_logged(real, client, monkeypatch, caplog):
    html = sheet(client)
    assert "Have a code?" in text(html)
    monkeypatch.setattr(mb, "PER_MINUTE", 1000)
    monkeypatch.setattr(mb, "PER_DAY", 1000)
    monkeypatch.setattr(mb, "CODE_MISSES_A_DAY", 3)
    with caplog.at_level(logging.WARNING):
        results = [code(client, html, "NOSUCH" + str(i)).status_code for i in range(3)]
    assert results == [422, 422, 422] and "booking codes are off for today: 3 wrong codes were tried" in caplog.text
    before = len(real.calls(liteapi_prebook()))
    r = code(client, html, "ANOTHER1")
    assert r.status_code == 403 and r.json()["error"] == "Codes are off for today. Book without one." and len(real.calls(liteapi_prebook())) == before
    assert "Have a code?" not in text(sheet(client))      # the box is gone from a new sheet
    assert code(client, html, "").status_code == 200      # taking a code off still works


def liteapi_prebook():
    from tests.test_liteapi_book import PREBOOK
    return PREBOOK


def test_a_malformed_code_counts_as_a_wrong_one_and_a_good_code_does_not(real, client, monkeypatch):
    html = sheet(client)
    monkeypatch.setattr(mb, "PER_MINUTE", 1000)
    monkeypatch.setattr(mb, "PER_DAY", 1000)
    code(client, html, "<b>")
    assert mb._misses_today() == 1
    code(client, html, "F274SANDBOX")
    assert mb._misses_today() == 1


# ---- the reviewer's fixes -----------------------------------------------------------------------------------------------------------------------

def test_a_cancel_with_a_fee_and_a_partial_refund_says_both():
    """cancel_partial.json is hand-shaped (LiteAPI's CANCELLED_WITH_CHARGES with a refund_amount): a fee and part of the money back."""
    c = json.loads((FIX / "cancel_partial.json").read_text())["body"]["data"]
    row = {"status": c["status"], "refund_cents": round(c["refund_amount"] * 100), "fee_cents": round(c["cancellation_fee"] * 100)}
    assert staycancel._came_back(row) == "Cancelled. LiteAPI charged $148.88 for cancelling, and $371.78 comes back to the card you paid with."
    assert staycancel._came_back(row, 30000) == "Cancelled. LiteAPI charged $148.88 for cancelling, and $300 comes back to the card you paid with."      # never more than the card paid
    assert staycancel._came_back({"status": "CANCELLED_WITH_CHARGES", "refund_cents": 0, "fee_cents": 34010}) == "Cancelled. Nothing comes back: LiteAPI charged $340.10 for cancelling."
    assert staycancel._came_back({"status": "CANCELLED", "refund_cents": 52066, "fee_cents": 0}) == "Cancelled. LiteAPI says $520.66 comes back to the card you paid with."
    assert staycancel._came_back({"status": "CANCELLED", "refund_cents": 0, "fee_cents": 0}) == "Cancelled. Nothing was charged."


def test_a_room_whose_card_price_moved_without_a_voucher_is_said_to_have_moved(live):
    from dataclasses import replace
    prep = mb.prepare((PART,), DAYS, "fam", sdk=True)
    assert prep.changed is False
    row = prep.rows[0]
    moved = mb.Prep(prep.status, (mb.Row(row.place, row.part, replace(row.prebook, pays_cents=36010)),), False, prep.token)      # the card is charged $20 more than the square said, no voucher
    assert moved.changed is True


def test_the_margin_proved_through_prebook_the_price_charged_is_the_price_shown():
    """tests/fixtures/liteapi_pay/margin_prebook.json (scripts/probe_liteapi_margin.py, sandbox, 2026-11-16): a search with margin 16 and a prebook of each offer."""
    rows = json.loads((FIX / "margin_prebook.json").read_text())["rows"]
    assert len(rows) == 6 and all(r["prebook_status"] == 200 for r in rows)
    assert all(r["pays"] == r["prebook_price"] == r["retail"] and abs(r["pays"] - r["shown"]) <= 0.011 for r in rows)
    assert [r["pays"] for r in rows][:3] == [394.48, 496.08, 401.74] and [r["shown"] for r in rows][:3] == [394.48, 496.08, 401.74]


# ---- L2, L3, L4 -----------------------------------------------------------------------------------------------------------------------------------

def test_another_persons_paying_row_is_not_described_to_this_one(real, client):
    html, _ = pay_pane(client)
    with ses.family(person()) as fam:
        familydb.run(fam.db, "UPDATE matrix_payments SET user_id = 'someone-else'")
        fam.db.conn.commit()
    r = client.get(f"/plan/matrix/book/return?token={token(html)}")
    words = text(r.text)
    assert r.status_code == 404 and "We could not find that booking." in words and "Payment reference" not in words and "tr_cts" not in r.text and real.calls(liteapi_book()) == []


def liteapi_book():
    from tests.test_liteapi_book import BOOK
    return BOOK


def test_a_cross_site_cancel_cancels_nothing(real, client):
    from tests.test_staycancel import booked_stay
    trip, href = booked_stay(client)
    n = len(real.asked)
    r = client.post("/trip/booking/cancel", data={"booking": "uuJxfM0--", "sure": "1", "next": href}, headers={"Origin": "https://evil.example"}, follow_redirects=False)
    assert r.status_code == 403 and len(real.asked) == n
    r = client.post("/trip/booking/cancel", data={"booking": "uuJxfM0--", "sure": "1", "next": href}, headers={"Sec-Fetch-Site": "cross-site"}, follow_redirects=False)
    assert r.status_code == 403 and len(real.asked) == n


def test_the_privacy_page_names_the_mobile_number_and_the_requests(real, client):
    words = " ".join(text(client.get("/privacy").text).split())
    assert "first name, last name, email and mobile number that you typed, the requests you ticked and a voucher code" in words
    assert "holds the guest's name, email, mobile number and requests only until the booking is made" in words.replace("’", "'")
