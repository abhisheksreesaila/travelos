"""F-285: booking emails (D-910..D-914). A booked stay sends one email to the lead guest before the guest's address is blanked; a stay cancelled in the app sends one with the refund LiteAPI
reported; each is sent once (a marker on the booking's row), off the request thread, with no address or name in any log line, and no SMTP settings means no email and no error.
Nothing here touches the network: `bookingmail.deliver` is a fake that keeps what it was given."""
import logging
import re
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from email import message_from_string, policy

import pytest

from gitaway import bookingjobs, bookingmail, familydb, liteapi, matrixbook as mb, session as ses, tripmatrix as tm
from tests.test_matrixbook_page import person
from tests.test_f274_review import aged
from tests.test_liteapi_pay import Pay, live as live_key  # noqa: F401
from tests.test_matrixbook_live import real  # noqa: F401 (a fixture: a live key, signed in)
from tests.test_matrixbook_pay import DAYS, PART, family, live  # noqa: F401 (fixtures)

LEAD = liteapi.Guest("Anne-Marie", "O’Neil", "anne.oneil@example.com", "+1 415 555 0100", "")
ADDRESS = "660 K Street, San Diego, CA 92101"
SMTP = {"SMTP_HOST": "smtp.resend.com", "SMTP_USER": "resend", "SMTP_PASSWORD": "re_not_a_key", "SMTP_MAIL_FROM": "GitAway <trips@gitaway.me>", "SMTP_SSL": "true", "SMTP_PORT": "465"}


class Outbox:
    """What `bookingmail.deliver` was asked to send: (to, subject, text, html), and the thread each ran on."""

    def __init__(self):
        self.sent, self.fail = [], False

    def __call__(self, to, mail):
        if self.fail:
            raise OSError("550 mailbox unavailable for " + to)
        self.sent.append((to, mail.subject, mail.text, mail.html))


@pytest.fixture
def outbox(monkeypatch):
    box = Outbox()
    for k, v in SMTP.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(bookingmail, "deliver", box)
    monkeypatch.setattr(bookingmail, "_spawn", lambda fn, *a: fn(*a))      # the thread, run in line so the test can read what it sent
    return box


def paid(db, user, guests="2 adults", part=None, guest=LEAD):
    """A prebooked stay whose guest opened the payment form: the row finish() books."""
    prep = mb.prepare((part or replace(PART, address=ADDRESS),), DAYS, "fam", sdk=True)
    assert prep.ok
    mb.save_prebook(db, prep.token, user, prep.rows[0], guests=guests)
    assert mb.pay_start(db, prep.token, user, guest, "trip-1")
    return prep


def booking_row(db):
    return familydb.rows(db, "SELECT * FROM matrix_bookings")[0]


def body(raw_html):
    return " ".join(re.sub(r"<[^>]+>", " ", re.sub(r"<(style|head)[^>]*>.*?</\1>", "", raw_html, flags=re.S)).replace("&amp;", "&").replace("&#x27;", "'").replace("&#39;", "'").split())


# ---- the booked email ------------------------------------------------------------------------------------------------------------------------

def test_a_booked_stay_sends_one_email_to_the_lead_guest_with_everything_the_guest_paid_for(live, family, outbox):
    db, user = family
    prep = paid(db, user)
    res = mb.finish(db, "fam", prep.token, user)
    assert res.ok
    (to, subject, text, html), = outbox.sent
    done, pay = res.done[0], mb.payment(db, prep.token)
    assert to == "anne.oneil@example.com"
    assert subject == f"Booked: {done.hotel}, Dec 16 to 19"
    for line in (done.hotel, ADDRESS, "Wed, Dec 16, 2026", "Sat, Dec 19, 2026", "2 adults", done.room, done.booking_id, "$340.10", "$120", mb.MERCHANT,
                 pay["policy"], "Hi Anne-Marie"):
        assert line in text, line
        assert line.replace("’", "’") in body(html), line
    assert done.confirmation and done.confirmation in text and done.confirmation in body(html)
    assert f"https://gitaway.me/plan/matrix/book/return?token={prep.token}" in text and "https://gitaway.me/trip/plan?arrive=1" in text
    assert f'href="https://gitaway.me/plan/matrix/book/return?token={prep.token}"' in html and 'href="https://gitaway.me/trip/plan?arrive=1"' in html
    assert booking_row(db)["booked_email_at"] != ""


def test_the_email_is_built_before_the_guests_address_is_blanked_and_the_row_then_holds_none(live, family, outbox):
    db, user = family
    prep = paid(db, user)
    mb.finish(db, "fam", prep.token, user)
    pay = mb.payment(db, prep.token)
    assert (pay["guest_email"], pay["guest_first"], pay["status"]) == ("", "", "booked") and len(outbox.sent) == 1


def test_a_second_finish_and_a_reload_of_the_return_page_send_nothing_more(live, family, outbox):
    db, user = family
    prep = paid(db, user)
    mb.finish(db, "fam", prep.token, user)
    mb.finish(db, "fam", prep.token, user)
    assert len(outbox.sent) == 1


def test_two_finishers_at_once_send_one_email(live, family, outbox, monkeypatch):
    """The return page and the worker can finish the same stay together: the one who wins the marker sends."""
    db, user = family
    prep = paid(db, user)
    real_claim = bookingmail.claim
    calls = []
    monkeypatch.setattr(bookingmail, "claim", lambda *a, **k: calls.append(1) or real_claim(*a, **k))
    mb.finish(db, "fam", prep.token, user)
    familydb.run(db, "UPDATE matrix_payments SET guest_email = 'anne.oneil@example.com', guest_first = 'Anne-Marie', guest_last = 'O’Neil', status = 'paying' WHERE id = :i", i=prep.token)
    mb.finish(db, "fam", prep.token, user)      # the same stay, found already booked, the address still on the row: the marker says it was sent
    assert len(calls) >= 1 and len(outbox.sent) == 1


def test_the_workers_late_finish_sends_the_email_too(live, family, outbox):
    db, user = family
    prep = paid(db, user)
    aged(db, prep.token, minutes=30)
    assert bookingjobs.run_once(datetime.now(timezone.utc) + timedelta(minutes=1)) == 1
    assert [s[0] for s in outbox.sent] == ["anne.oneil@example.com"]


def test_no_smtp_settings_means_no_email_no_marker_and_no_error(live, family, outbox, monkeypatch):
    for k in SMTP:
        monkeypatch.delenv(k)
    db, user = family
    prep = paid(db, user)
    assert mb.finish(db, "fam", prep.token, user).ok
    assert outbox.sent == [] and booking_row(db)["booked_email_at"] == ""


def test_a_mail_server_that_refuses_is_a_log_line_with_the_booking_id_and_the_booking_stands(live, family, outbox, caplog):
    db, user = family
    outbox.fail = True
    prep = paid(db, user)
    with caplog.at_level(logging.INFO):
        res = mb.finish(db, "fam", prep.token, user)
    assert res.ok
    lines = [r.getMessage() for r in caplog.records if r.name == "gitaway.bookingmail"]
    assert lines == [f"booking email failed: {res.done[0].booking_id}"]


def test_no_log_line_carries_the_address_or_the_names(live, family, outbox, caplog):
    db, user = family
    prep = paid(db, user)
    with caplog.at_level(logging.DEBUG):
        res = mb.finish(db, "fam", prep.token, user)
    logged = "\n".join(r.getMessage() for r in caplog.records)
    assert f"booking email sent: {res.done[0].booking_id}" in logged
    for private in ("anne.oneil", "example.com", "Anne-Marie", "O’Neil", ADDRESS):
        assert private not in logged


def test_the_send_runs_on_its_own_thread(live, family, monkeypatch):
    seen = {}
    for k, v in SMTP.items():
        monkeypatch.setenv(k, v)
    import threading

    def deliver(to, mail):
        seen["thread"] = threading.current_thread()
        seen["done"].set()
    seen["done"] = threading.Event()
    monkeypatch.setattr(bookingmail, "deliver", deliver)
    db, user = family
    prep = paid(db, user)
    mb.finish(db, "fam", prep.token, user)
    assert seen["done"].wait(5) and seen["thread"] is not threading.main_thread() and seen["thread"].name == "booking-mail"


# ---- what a stranger's text cannot do ---------------------------------------------------------------------------------------------------------

def test_words_from_liteapi_with_markup_and_a_line_break_are_text_in_the_html_and_one_line_in_the_subject(monkeypatch):
    for k, v in SMTP.items():
        monkeypatch.setenv(k, v)
    evil = "Hotel <script>alert(1)</script> & Spa\r\nBcc: spy@example.net"
    mail = bookingmail.booked_mail({"first": "Anne\r\nBcc: x@example.net", "hotel": evil, "address": '1 <b>Main</b> St"><img src=x onerror=1>', "checkin": "2026-12-16", "checkout": "2026-12-19",
                                    "guests": "2 adults", "room": "<i>Queen</i>", "booking_id": "b<1>", "confirmation": "c&d", "charge_cents": 34010, "due_cents": 0, "policy": "<u>Free</u>",
                                    "token": "tok", "sandbox": False})
    assert mail.subject == "Booked: Hotel <script>alert(1)</script> & Spa Bcc: spy@example.net, Dec 16 to 19"
    for raw in ("<script", "<img", "<b>", "<i>", "<u>", "b<1>"):
        assert raw not in mail.html, raw
    for escaped in ("&lt;script&gt;alert(1)&lt;/script&gt; &amp; Spa Bcc: spy@example.net", "&lt;b&gt;Main&lt;/b&gt; St&quot;&gt;&lt;img src=x onerror=1&gt;", "c&amp;d", "b&lt;1&gt;"):
        assert escaped in mail.html, escaped
    parsed = message_from_string(bookingmail.render_mime("anne@example.com", mail.subject, mail.text, mail.html), policy=policy.default)
    assert parsed["To"] == "anne@example.com" and parsed["Bcc"] is None and "\n" not in str(parsed["Subject"]).strip()


def test_a_stored_address_and_party_with_markup_reach_the_email_as_text(live, family, outbox):
    db, user = family
    prep = paid(db, user, guests="2 <b>adults</b>", part=replace(PART, address='1 <b>Main</b> St'))
    mb.finish(db, "fam", prep.token, user)
    html = outbox.sent[0][3]
    assert "<b>" not in html and "1 &lt;b&gt;Main&lt;/b&gt; St" in html and "2 &lt;b&gt;adults&lt;/b&gt;" in html


def test_an_address_with_a_line_break_in_it_is_never_sent(live, family, outbox):
    db, user = family
    prep = paid(db, user)
    familydb.run(db, "UPDATE matrix_payments SET guest_email = :e WHERE id = :i", e="anne@example.com\r\nBcc: x@example.net", i=prep.token)
    mb.finish(db, "fam", prep.token, user)      # clean_guest refuses it: nothing is booked and nothing sent
    assert outbox.sent == []


def test_the_mime_message_has_a_plain_part_and_an_html_part_and_the_senders_address(monkeypatch):
    for k, v in SMTP.items():
        monkeypatch.setenv(k, v)
    raw = bookingmail.render_mime("anne@example.com", "Booked: Hotel", "plain words", "<p>html words</p>")
    msg = message_from_string(raw, policy=policy.default)
    assert (msg["From"], msg["To"], msg["Subject"]) == ("GitAway <trips@gitaway.me>", "anne@example.com", "Booked: Hotel")
    kinds = [p.get_content_type() for p in msg.walk()]
    assert kinds == ["multipart/alternative", "text/plain", "text/html"]
    assert msg.get_body(("plain",)).get_content().strip() == "plain words" and "html words" in msg.get_body(("html",)).get_content()


# ---- the cancelled email ----------------------------------------------------------------------------------------------------------------------

def book_it(db, user, outbox):
    prep = paid(db, user)
    res = mb.finish(db, "fam", prep.token, user)
    outbox.sent.clear()
    return res.done[0]


def test_cancelling_sends_one_email_with_what_liteapi_reported_to_the_person_who_cancelled(live, family, outbox, monkeypatch):
    db, user = family
    done = book_it(db, user, outbox)
    status, got = mb.cancel(db, "fam", done.booking_id, user)
    assert status == liteapi.OK
    bookingmail.cancelled(db, done.booking_id, "traveler@example.com", 19122, 14888)
    (to, subject, text, html), = outbox.sent
    assert to == "traveler@example.com" and subject == f"Cancelled: {done.hotel}, Dec 16 to 19"
    for words in ("$191.22 comes back to the card you paid with", "LiteAPI charged $148.88 for cancelling"):
        assert words in text and words in body(html), words
    for line in (done.hotel, done.booking_id, mb.MERCHANT):
        assert line in text and line in body(html)
    assert booking_row(db)["cancel_email_at"] != ""
    bookingmail.cancelled(db, done.booking_id, "traveler@example.com", 19122, 14888)      # a second press of Cancel
    assert len(outbox.sent) == 1


def test_a_cancel_with_a_fee_and_nothing_back_says_so(live, family, outbox):
    db, user = family
    done = book_it(db, user, outbox)
    bookingmail.cancelled(db, done.booking_id, "traveler@example.com", 0, 14888)
    text = outbox.sent[0][2]
    assert "$148.88" in text and "Nothing comes back" in text


def test_a_cancel_without_smtp_or_with_a_bad_address_sends_nothing_and_marks_nothing(live, family, outbox, monkeypatch):
    db, user = family
    done = book_it(db, user, outbox)
    bookingmail.cancelled(db, done.booking_id, "not an address", 100, 0)
    bookingmail.cancelled(db, done.booking_id, "x@example.com\nBcc: y@example.net", 100, 0)
    for k in SMTP:
        monkeypatch.delenv(k)
    bookingmail.cancelled(db, done.booking_id, "traveler@example.com", 100, 0)
    assert outbox.sent == [] and booking_row(db)["cancel_email_at"] == ""


def test_a_sample_booking_is_never_emailed(live, family, outbox):
    db, user = family
    done = book_it(db, user, outbox)
    familydb.run(db, "UPDATE matrix_bookings SET sample = 1 WHERE booking_id = :b", b=done.booking_id)
    bookingmail.cancelled(db, done.booking_id, "traveler@example.com", 100, 0)
    assert outbox.sent == []


# ---- the migration and the one place the words are ---------------------------------------------------------------------------------------------

def test_the_new_columns_come_by_migration_not_the_baseline():
    from gitaway.familydb_matrix import MatrixBooking, MatrixPayment
    assert not {"hotel_address", "guests"} & set(MatrixPayment.__annotations__)
    assert not {"booked_email_at", "cancel_email_at"} & set(MatrixBooking.__annotations__)


def test_the_return_page_the_email_links_to_is_the_real_one():
    from gitaway.pages import matrixbook as page
    assert bookingmail.RETURN_PATH == page.RETURN


# ---- through the real pages ---------------------------------------------------------------------------------------------------------------------

def test_the_return_page_sends_the_booked_email_with_the_hotels_address_and_the_party(real, client, outbox):
    from tests.test_matrixbook_live import GUEST as FORM_GUEST, pay_pane, token
    html, _ = pay_pane(client)
    assert outbox.sent == []      # paying alone books nothing: the email follows the booking
    client.get(f"/plan/matrix/book/return?token={token(html)}")
    (to, subject, text, page_html), = outbox.sent
    assert to == FORM_GUEST["email"] and subject.startswith("Booked: ") and "Hi Anne-Marie," in text
    assert re.search(r"Address: \S", text) and re.search(r"Guests: (\d+ adults?|one adult|a family of \d+)", text), text
    client.get(f"/plan/matrix/book/return?token={token(html)}")      # a reload of the return page
    assert len(outbox.sent) == 1


def test_pressing_cancel_emails_the_signed_in_person_once_with_what_liteapi_reported(real, client, outbox):
    from tests.test_matrixbook_page import person
    from tests.test_staycancel import booked_stay
    real.answers["cancel"] = "cancel_refundable.json"
    trip, href = booked_stay(client)
    outbox.sent.clear()
    client.post("/trip/booking/cancel", data={"booking": "uuJxfM0--", "sure": "1", "next": href})
    client.post("/trip/booking/cancel", data={"booking": "uuJxfM0--", "sure": "1", "next": href})
    (to, subject, text, html), = outbox.sent
    assert to == person()["email"] and subject.startswith("Cancelled: ")
    assert "comes back to the card you paid with" in text and "uuJxfM0--" in text


def test_a_cancel_that_was_not_ticked_sends_nothing(real, client, outbox):
    from tests.test_staycancel import booked_stay
    trip, href = booked_stay(client)
    outbox.sent.clear()
    client.post("/trip/booking/cancel", data={"booking": "uuJxfM0--", "next": href})      # no tick
    assert outbox.sent == []


# ---- the SMTP leg (Resend: port 465 with SSL, or 587 with STARTTLS) ---------------------------------------------------------------------------------

class FakeSMTP:
    made = []

    def __init__(self, host, port, timeout=None, context=None):
        self.host, self.port, self.steps, self.sent = host, port, [], []
        FakeSMTP.made.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self, context=None):
        self.steps.append("starttls")

    def login(self, user, password):
        self.steps.append(("login", user))

    def send_message(self, msg):
        self.sent.append(msg)


@pytest.mark.parametrize("env, ssl_class, port, steps", [(SMTP, "SMTP_SSL", 465, [("login", "resend")]),
                                                          ({**SMTP, "SMTP_SSL": "false", "SMTP_PORT": "587"}, "SMTP", 587, ["starttls", ("login", "resend")])])
def test_deliver_logs_in_to_resend_over_ssl_or_starttls_and_sends_both_parts(monkeypatch, env, ssl_class, port, steps):
    import smtplib
    FakeSMTP.made = []
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(smtplib, ssl_class, FakeSMTP)
    bookingmail.deliver("anne@example.com", bookingmail.Mail("Booked: Hotel", "plain", "<p>html</p>"))
    (server,) = FakeSMTP.made
    assert (server.host, server.port, server.steps) == ("smtp.resend.com", port, steps)
    msg = server.sent[0]
    assert (msg["To"], msg["From"], msg["Subject"]) == ("anne@example.com", "GitAway <trips@gitaway.me>", "Booked: Hotel")
    assert [p.get_content_type() for p in msg.walk()] == ["multipart/alternative", "text/plain", "text/html"]


def test_the_test_script_sends_the_sample_through_the_same_code_and_previews_without_sending(outbox, tmp_path, capsys):
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("send_test_email", Path(__file__).resolve().parent.parent / "scripts" / "send_test_email.py")
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    assert script.main(["--to", "me@example.com"]) == 0
    (to, subject, text, html), = outbox.sent
    assert to == "me@example.com" and subject == "Booked: Margaritaville Hotel San Diego Gaslamp Quarter, Dec 16 to 19" and "Sandbox booking: nothing was charged." in text
    assert script.main(["--to", "me@example.com", "--cancelled"]) == 0 and outbox.sent[1][1].startswith("Cancelled: ")
    assert script.main(["--to", "bad address"]) == 2 and len(outbox.sent) == 2
    assert script.main(["--preview", str(tmp_path)]) == 0 and len(outbox.sent) == 2
    assert "Margaritaville" in (tmp_path / "booked.html").read_text() and "Cancelled" in (tmp_path / "cancelled.html").read_text()


def test_the_cancelled_email_never_says_more_came_back_than_the_card_paid(real, client, outbox):
    """With a voucher LiteAPI's refund_amount is the undiscounted price ($520.66 recorded for a $468.60 charge), as the booking page says."""
    from tests.test_staycancel import booked_stay
    real.answers["cancel"] = "cancel_refundable.json"
    trip, href = booked_stay(client)
    with ses.family(person()) as fam:
        familydb.run(fam.db, "UPDATE matrix_payments SET charge_cents = 46860")
        fam.db.conn.commit()
    outbox.sent.clear()
    client.post("/trip/booking/cancel", data={"booking": "uuJxfM0--", "sure": "1", "next": href})
    assert "$468.60 comes back to the card you paid with" in outbox.sent[0][2] and "$520.66" not in outbox.sent[0][2]


# ---- review fixes -----------------------------------------------------------------------------------------------------------------------------

def test_smtp_without_ssl_or_starttls_is_refused_and_logged_with_the_booking_id_only(monkeypatch, caplog):
    import smtplib
    for k, v in {**SMTP, "SMTP_SSL": "false", "SMTP_STARTTLS": "false"}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(smtplib, "SMTP", lambda *a, **k: pytest.fail("connected without TLS"))
    mail = bookingmail.Mail("s", "t", "<p>h</p>")
    with pytest.raises(bookingmail.NoTLS):
        bookingmail.deliver("anne@example.com", mail)
    with caplog.at_level(logging.INFO):
        bookingmail._send("anne@example.com", mail, "bk-1")
    assert [r.getMessage() for r in caplog.records if r.name == "gitaway.bookingmail"] == ["booking email not sent: SMTP without TLS: bk-1"]


def test_the_purge_blanks_the_party_and_hotel_address_with_the_guest_fields(live, family, outbox):
    db, user = family
    prep = paid(db, user)
    mb.finish(db, "fam", prep.token, user)
    row = mb.payment(db, prep.token)
    assert (row["guests"], row["hotel_address"]) == ("2 adults", ADDRESS)      # kept for the booked email until the purge
    mb.purge(db)
    assert (mb.payment(db, prep.token)["guests"], mb.payment(db, prep.token)["hotel_address"]) == ("2 adults", ADDRESS)      # not old enough yet
    old = (datetime.now(timezone.utc) - timedelta(days=mb.PURGE_GUEST + 1)).isoformat(timespec="seconds")
    familydb.run(db, "UPDATE matrix_payments SET created_at = :t", t=old)
    mb.purge(db)
    row = mb.payment(db, prep.token)
    assert (row["guests"], row["hotel_address"], row["status"]) == ("", "", "booked")
