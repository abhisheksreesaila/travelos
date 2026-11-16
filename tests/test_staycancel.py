"""F-274: a stay booked here through LiteAPI is cancelled from its booking page (gitaway/pages/staycancel.py): the policy as it was shown, an editor's tick and button, LiteAPI's cancel,
what came back said, the stay marked Cancelled on the trip, asked once. A sample booking has no cancel; a viewer sees the policy and no button."""
import re
from html import unescape

import pytest

from gitaway import catalog, familydb, importer, session as ses, tripimport as ti
from tests.test_matrixbook_live import CANCEL, BOOK, GUEST, Live, pay_pane, payments, real, token  # noqa: F401 (real is the fixture)
from tests.test_matrixbook_page import person, sign_in, stays_booked, text


def booked_stay(client):
    """Book a stay through the payment form's path and give back (the trip id, the booking page of its check in)."""
    html, _ = pay_pane(client)
    client.get(f"/plan/matrix/book/return?token={token(html)}")
    trip_id = stays_booked()[0]["trip_id"]
    plan = importer.plan_of(person(), trip_id)
    spec = next(x for x in ti.block_specs(plan) if x.kind == "checkin")
    return trip_id, f"/trip/booking?block={spec.id}"


def words(html):
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", html)).split())


def test_a_stay_booked_here_shows_its_policy_and_a_cancel_button_to_an_editor(real, client):
    trip, href = booked_stay(client)
    page = client.get(href).text
    assert "Non-refundable: if you cancel, nothing comes back." in words(page) and 'id="bk-cancel-go"' in page and 'name="booking" value="uuJxfM0--"' in page
    assert 'name="sure"' in page and "I want to cancel this stay" in words(page) and "Booked on LiteAPI" in words(page)


def test_cancelling_a_non_refundable_stay_says_nothing_comes_back_and_marks_the_stay(real, client):
    trip, href = booked_stay(client)
    r = client.post("/trip/booking/cancel", data={"booking": "uuJxfM0--", "sure": "1", "next": href}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == href
    sent = [c for c in real.asked if c[0] == CANCEL + "uuJxfM0--"]
    assert len(sent) == 1 and sent[0][3] == "PUT" and sent[0][2] is None
    page = client.get(href).text
    assert "Cancelled. Nothing comes back: LiteAPI charged $340.10 for cancelling." in words(page) and "bk-cancel-go" not in page
    assert [h.booked_on for h in importer.plan_of(person(), trip).hotels] == ["Cancelled on LiteAPI"]
    client.post("/trip/booking/cancel", data={"booking": "uuJxfM0--", "sure": "1", "next": href})
    assert len([c for c in real.asked if c[0] == CANCEL + "uuJxfM0--"]) == 1      # asked once


def test_cancelling_a_refundable_stay_says_what_comes_back(real, client):
    real.answers["cancel"] = "cancel_refundable.json"
    trip, href = booked_stay(client)
    paid = payments()[0]["charge_cents"]
    client.post("/trip/booking/cancel", data={"booking": "uuJxfM0--", "sure": "1", "next": href})
    assert f"Cancelled. LiteAPI says {catalog.money(min(52066, paid))} comes back to the card you paid with." in words(client.get(href).text)


def test_a_refund_is_never_said_to_be_more_than_the_card_paid(real, client):
    """With a voucher LiteAPI's refund_amount is the undiscounted price ($520.66 for a $468.60 charge, recorded): the page says what the card paid."""
    real.answers["cancel"] = "cancel_refundable.json"
    trip, href = booked_stay(client)
    with ses.family(person()) as fam:
        familydb.run(fam.db, "UPDATE matrix_payments SET charge_cents = 46860")
        fam.db.conn.commit()
    client.post("/trip/booking/cancel", data={"booking": "uuJxfM0--", "sure": "1", "next": href})
    assert "Cancelled. LiteAPI says $468.60 comes back to the card you paid with." in words(client.get(href).text)


def test_without_the_tick_or_when_liteapi_refuses_nothing_changes_and_the_page_says_why(real, client):
    trip, href = booked_stay(client)
    r = client.post("/trip/booking/cancel", data={"booking": "uuJxfM0--", "next": href}, follow_redirects=False)
    assert r.headers["location"] == href + "&err=cancel_tick" and not [c for c in real.asked if c[0].startswith(CANCEL)]
    assert "Tick the box to say you mean to cancel this stay." in words(client.get(r.headers["location"]).text)
    real.answers["cancel"] = "cancel_unknown.json"
    r = client.post("/trip/booking/cancel", data={"booking": "uuJxfM0--", "sure": "1", "next": href}, follow_redirects=False)
    assert r.headers["location"] == href + "&err=cancel"
    page = client.get(r.headers["location"]).text
    assert "could not cancel that just now" in words(page) and "bk-cancel-go" in page
    assert [h.booked_on for h in importer.plan_of(person(), trip).hotels] == ["LiteAPI"]


def test_a_booking_that_is_not_ours_or_a_sample_is_never_sent_to_liteapi(real, client):
    trip, href = booked_stay(client)
    client.post("/trip/booking/cancel", data={"booking": "someone-elses", "sure": "1", "next": href})
    with ses.family(person()) as fam:
        familydb.run(fam.db, "INSERT INTO matrix_bookings (id, booking_id, hotel, checkin, checkout, sample, created_at) VALUES ('s', 'SAMPLE-ABC', 'H', '2026-12-12', '2026-12-16', 1, 'now')")
        fam.db.conn.commit()
    client.post("/trip/booking/cancel", data={"booking": "SAMPLE-ABC", "sure": "1", "next": href})
    assert not [c for c in real.asked if c[0].startswith(CANCEL)]


def test_the_way_back_cannot_be_made_to_leave_the_booking_pages(real, client):
    trip, href = booked_stay(client)
    for evil in ("https://evil.example/", "//evil.example", "/admin", "/trip/booking\nSet-Cookie: x"):
        r = client.post("/trip/booking/cancel", data={"booking": "uuJxfM0--", "next": evil}, follow_redirects=False)
        assert r.headers["location"].startswith("/trip/plan"), evil


def test_a_viewer_sees_the_policy_and_no_button_and_cannot_cancel(real, client, monkeypatch):
    trip, href = booked_stay(client)
    from gitaway import access
    monkeypatch.setattr(access, "request_role", lambda: "viewer")
    page = client.get(href).text
    assert "Non-refundable" in words(page) and "bk-cancel-go" not in page


def test_a_signed_out_post_goes_to_sign_in_and_a_viewers_post_is_refused(real, client):
    trip, href = booked_stay(client)
    client.post("/logout")
    r = client.post("/trip/booking/cancel", data={"booking": "uuJxfM0--", "sure": "1", "next": href}, follow_redirects=False)
    assert r.status_code in (303, 401, 403) and not [c for c in real.asked if c[0].startswith(CANCEL)]
