"""Booking emails (F-285, D-910..D-914): the email a guest gets when a stay is booked, and the one when it is cancelled in the app.

    booked(db, booking, pay, guest)         the booked email to the lead guest: called by `matrixbook.finish` while the guest's address is still on the row, before it is blanked
    cancelled(db, booking_id, to, refund_cents, fee_cents)   the cancelled email, with what LiteAPI reported, to the person who pressed Cancel (their sign-in address: the guest's is gone)
    booked_mail(d) / cancelled_mail(d)      the words: a `Mail` of subject, plain text and HTML (inline styles and tables, no external CSS, fonts or images: Gmail and Apple Mail)
    message(to, subject, text, html)        the message, plain and HTML parts (`render_mime` is its text)
    deliver(to, mail)                       the one place that talks SMTP (fh-saas's settings: SMTP_HOST, SMTP_USER, SMTP_PASSWORD, SMTP_MAIL_FROM; Resend's, D-910); tests replace it

Why not fh-saas `send_email`: it renders a markdown template (no hand-built HTML with a plain part) and logs the recipient's address at INFO and in its errors; a booking's guest
address must never reach a log (D-912). `get_smtp_config()` is still the one source of the settings, so the same four names turn mail on. No settings, no email, no error.

Once only: `claim` sets the booking row's marker (`booked_email_at`, `cancel_email_at`, columns added by migrations 008 and 009) before the thread starts, so a reload, the worker and the return
page finishing together, or a second press of Cancel can send only one. A send that fails is one log line with the booking id and is not retried. A sample booking is never emailed.
Every word from LiteAPI or the guest is escaped in the HTML and stripped of line breaks in the subject (header injection); the address is checked against the booking form's own pattern.
"""

import logging
import re
import smtplib
import ssl
import threading
from dataclasses import dataclass
from datetime import date
from email.message import EmailMessage
from html import escape

from gitaway import blogbutton, catalog, familydb, walletpass
from gitaway.matrixbook import _EMAIL

log = logging.getLogger("gitaway.bookingmail")
RETURN_PATH = "/plan/matrix/book/return"      # the booking's pass (`pages.matrixbook.RETURN`), for the person who booked
PLAN_PATH = "/trip/plan?arrive=1"
SOLD_BY = "Sold by Nuitée through LiteAPI"
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f  ]+")


class NoTLS(Exception):
    """The settings name neither SMTP_SSL nor STARTTLS: `deliver` refuses to send."""


@dataclass(frozen=True)
class Mail:
    subject: str
    text: str
    html: str


def smtp():
    """fh-saas's mail settings, or None when they are not all set (no email, no error)."""
    from fh_saas import utils_email
    try:
        return utils_email.get_smtp_config()
    except ValueError:
        return None


def one_line(v, limit: int = 120) -> str:
    """Text from outside as one plain line: no control characters or line breaks (a subject cannot be made to carry a header)."""
    return " ".join(_CONTROL.sub(" ", str(v or "")).split())[:limit]


def address_ok(v) -> bool:
    v = str(v or "")
    return len(v) <= 120 and bool(_EMAIL.match(v)) and ".." not in v


# ---- the words ---------------------------------------------------------------------------------------------------------------------------------

def _day(iso) -> str:
    d = date.fromisoformat(str(iso)[:10])
    return f"{d:%a}, {d:%b} {d.day}, {d.year}"


def _span(a, b) -> str:
    x, y = date.fromisoformat(str(a)[:10]), date.fromisoformat(str(b)[:10])
    return f"{x:%b} {x.day} to {y.day}" if (x.year, x.month) == (y.year, y.month) else f"{x:%b} {x.day} to {y:%b} {y.day}"


def _url(path) -> str:
    return blogbutton.base_url() + path


def _came_back(refund: int, fee: int) -> str:
    """What LiteAPI said about the cancel, in words (the same as the booking page's)."""
    if fee and refund:
        return f"LiteAPI charged {catalog.money(fee)} for cancelling, and {catalog.money(refund)} comes back to the card you paid with."
    if fee:
        return f"Nothing comes back: LiteAPI charged {catalog.money(fee)} for cancelling."
    if refund:
        return f"{catalog.money(refund)} comes back to the card you paid with."
    return "Nothing was charged for cancelling."


def booked_mail(d: dict) -> Mail:
    """`d`: first, hotel, address, place, checkin, checkout (ISO), guests, room, booking_id, confirmation, charge_cents, due_cents, policy, token, sandbox."""
    hotel, first = one_line(d["hotel"]), one_line(d.get("first"), 40)
    rows = [("Hotel", hotel), ("Address", one_line(d.get("address"), 200)), ("Check in", _day(d["checkin"])), ("Check out", _day(d["checkout"])), ("Guests", one_line(d.get("guests"), 80)),
            ("Room", one_line(d.get("room"))), ("LiteAPI booking id", one_line(d["booking_id"], 60)), ("Hotel confirmation", one_line(d.get("confirmation"), 60)),
            ("Total charged", catalog.money(d["charge_cents"])), ("Paid at the hotel", catalog.money(d["due_cents"]) if d["due_cents"] else "Nothing: no fees at the hotel")]
    rows = [(k, v) for k, v in rows if v]
    policy = one_line(d.get("policy"), 400) or "See the booking page for the cancelling policy."
    tag = "Sandbox booking: nothing was charged." if d.get("sandbox") else ""
    mine, plan = _url(f"{RETURN_PATH}?token={d['token']}"), _url(PLAN_PATH)
    wallet = [(label, _url(path)) for label, path in d.get("wallet") or ()]      # F-288: our signed download routes (they sign in first), never an attachment
    hello = f"Hi {first}," if first else "Hi,"
    lead = f"Your stay at {hotel} is booked."
    note = "The hotel keeps your name for check-in: bring an ID that matches it."
    text = "\n".join([hello, "", lead, *([tag] if tag else []), "", *[f"{k}: {v}" for k, v in rows], "", f"Cancelling: {policy}", "", note, "", f"Open your booking: {mine}",
                      *[f"{label}: {url}" for label, url in wallet], f"Plan this trip: {plan}", "", f"{SOLD_BY}. GitAway never sees or keeps your card.", ""])
    html = _shell(f"Booked: {hotel}", hello, lead, tag, rows, [("Cancelling", policy)], note, [("Open your booking", mine, True), *[(label, url, False) for label, url in wallet], ("Plan this trip", plan, False)],
                  f"{SOLD_BY}. GitAway never sees or keeps your card.")
    return Mail(f"Booked: {hotel}, {_span(d['checkin'], d['checkout'])}", text, html)


def cancelled_mail(d: dict) -> Mail:
    """`d`: hotel, checkin, checkout (ISO), booking_id, refund_cents, fee_cents, sandbox."""
    hotel = one_line(d["hotel"])
    said = _came_back(d["refund_cents"], d["fee_cents"])
    rows = [("Hotel", hotel), ("Check in", _day(d["checkin"])), ("Check out", _day(d["checkout"])), ("LiteAPI booking id", one_line(d["booking_id"], 60)),
            ("Refund", catalog.money(d["refund_cents"])), ("Cancelling cost", catalog.money(d["fee_cents"]))]
    tag = "Sandbox booking: nothing was charged." if d.get("sandbox") else ""
    plan = _url(PLAN_PATH)
    lead = f"Your stay at {hotel} is cancelled."
    note = "Refunds go back to the card you paid with. Your bank can take a few days to show it."
    text = "\n".join(["Hi,", "", lead, *([tag] if tag else []), "", said, "", *[f"{k}: {v}" for k, v in rows], "", note, "", f"Plan this trip: {plan}", "", f"{SOLD_BY}.", ""])
    html = _shell(f"Cancelled: {hotel}", "Hi,", lead, tag, rows, [("What LiteAPI reported", said)], note, [("Plan this trip", plan, True)], f"{SOLD_BY}.")
    return Mail(f"Cancelled: {hotel}, {_span(d['checkin'], d['checkout'])}", text, html)


_INK, _INK2, _LINE, _SKY, _CTA = "#0F1124", "#41455E", "#E3E5F3", "#DCEBF9", "#4338CA"
_SANS = "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
_SERIF = "Newsreader, Georgia, 'Times New Roman', serif"


def _shell(title, hello, lead, tag, rows, blocks, note, buttons, foot) -> str:
    """One layout for both emails: the v2 look in tables and inline styles (a near-opaque white card on a pale sky, a serif headline, indigo buttons). Everything dynamic goes through `escape`."""
    e = lambda v: escape(str(v), quote=True)      # noqa: E731
    table = "".join(f'<tr><td style="padding:9px 0;border-top:1px solid {_LINE};font:14px/1.4 {_SANS};color:{_INK2};width:38%;vertical-align:top">{e(k)}</td>'
                    f'<td style="padding:9px 0;border-top:1px solid {_LINE};font:15px/1.4 {_SANS};color:{_INK};font-weight:600;vertical-align:top">{e(v)}</td></tr>' for k, v in rows)
    more = "".join(f'<p style="margin:20px 0 0;font:14px/1.5 {_SANS};color:{_INK2}"><strong style="color:{_INK}">{e(k)}</strong><br>{e(v)}</p>' for k, v in blocks)
    btns = "".join(f'<td style="padding:0 10px 10px 0"><a href="{e(u)}" style="display:inline-block;padding:13px 20px;border-radius:12px;font:600 15px/1.25 {_SANS};text-decoration:none;'
                   + (f'background:{_CTA};color:#FFFFFF;border:1px solid {_CTA}' if main else f'background:#FFFFFF;color:{_CTA};border:1px solid {_CTA}') + f'">{e(label)}</a></td>' for label, u, main in buttons)
    badge = (f'<p style="margin:14px 0 0;padding:10px 12px;border-radius:10px;background:#FFF4C2;font:14px/1.4 {_SANS};color:#5C4300">{e(tag)}</p>') if tag else ""
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="color-scheme" content="light">'
            f'<title>{e(title)}</title></head><body style="margin:0;padding:0;background:{_SKY}">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{_SKY}"><tr><td align="center" style="padding:24px 12px">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:560px">'
            f'<tr><td style="padding:0 4px 14px;font:700 18px/1 {_SANS};color:{_INK}">GitAway</td></tr>'
            f'<tr><td style="background:#FFFFFF;border-radius:20px;padding:28px 24px;border:1px solid #D2DDF0">'
            f'<p style="margin:0 0 6px;font:15px/1.4 {_SANS};color:{_INK2}">{e(hello)}</p>'
            f'<h1 style="margin:0;font:600 28px/1.15 {_SERIF};color:{_INK};letter-spacing:-0.01em">{e(lead)}</h1>{badge}'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:20px">{table}</table>{more}'
            f'<p style="margin:20px 0 0;font:14px/1.5 {_SANS};color:{_INK2}">{e(note)}</p>'
            f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin-top:22px"><tr>{btns}</tr></table></td></tr>'
            f'<tr><td style="padding:14px 6px 0;font:13px/1.5 {_SANS};color:{_INK2}">{e(foot)}</td></tr>'
            f'</table></td></tr></table></body></html>')


# ---- sending -----------------------------------------------------------------------------------------------------------------------------------

def message(to, subject, text, html) -> EmailMessage:
    """The message: plain text and HTML alternatives, from SMTP_MAIL_FROM. A header value with a line break is refused by `EmailMessage` (and never reaches here: see `one_line`, `address_ok`)."""
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = smtp()["from_email"], to, subject
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    return msg


def render_mime(to, subject, text, html) -> str:
    return message(to, subject, text, html).as_string()


def deliver(to, mail: Mail) -> None:
    """Send one message through the configured SMTP server (Resend: smtp.resend.com, port 465 with SMTP_SSL=true or 587 with STARTTLS). Raises on any failure; the caller logs without the address."""
    cfg, context = smtp(), ssl.create_default_context()
    if not (cfg["use_ssl"] or cfg["use_tls"]):      # a password and a guest's details never cross the network in the clear
        raise NoTLS("SMTP without TLS")
    server = smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=20, context=context) if cfg["use_ssl"] else smtplib.SMTP(cfg["host"], cfg["port"], timeout=20)
    with server:
        if cfg["use_tls"] and not cfg["use_ssl"]:
            server.starttls(context=context)
        server.login(cfg["user"], cfg["password"])
        server.send_message(message(to, mail.subject, mail.text, mail.html))


def _spawn(fn, *args) -> None:
    """Run `fn` on its own thread: SMTP can be slow and a booking must not wait for a mail server. Tests run it in line."""
    threading.Thread(target=fn, args=args, daemon=True, name="booking-mail").start()


def _send(to, mail: Mail, booking_id: str) -> None:
    try:
        deliver(to, mail)
        log.info("booking email sent: %s", booking_id)
    except NoTLS:
        log.warning("booking email not sent: SMTP without TLS: %s", booking_id)
    except Exception:  # noqa: BLE001 - mail never undoes a booking; the log line has the id and no address, and no exception text (a server's refusal repeats the address)
        log.warning("booking email failed: %s", booking_id)


def claim(db, column: str, booking_id: str) -> bool:
    """Win the right to send: set the booking's marker if it is empty. A sample booking never wins."""
    assert column in ("booked_email_at", "cancel_email_at")
    with familydb.transaction(db):
        return familydb.run(db, f"UPDATE matrix_bookings SET {column} = :now WHERE booking_id = :b AND {column} = '' AND sample = 0", b=booking_id, now=familydb.now()) == 1


def _sandbox() -> bool:
    from gitaway import matrixbook as mb
    return mb.mode() != mb.LIVE


def booked(db, booking: dict, pay: dict, guest, family: str = "") -> None:
    """Email the lead guest `guest` (a `liteapi.Guest`, already validated by `matrixbook.clean_guest`) that `booking` (the matrix_bookings row) is booked, from the saved prebook `pay`. Called before the
    guest's address is blanked. Nothing happens without SMTP settings or for a sample, and a booking is emailed once."""
    try:
        if smtp() is None or not address_ok(guest.email) or not claim(db, "booked_email_at", booking["booking_id"]):
            return
        mail = booked_mail({"first": guest.first, "hotel": booking["hotel"], "address": pay.get("hotel_address"), "checkin": booking["checkin"], "checkout": booking["checkout"],
                            "guests": pay.get("guests"), "room": booking["room"], "booking_id": booking["booking_id"], "confirmation": booking["confirmation"], "charge_cents": pay["charge_cents"],
                            "due_cents": booking["due_at_stay_cents"], "policy": pay.get("policy"), "token": pay["id"], "sandbox": _sandbox(),
                            "wallet": walletpass.links(booking["booking_id"], family, walletpass.MAIL_TTL)})
        _spawn(_send, guest.email, mail, booking["booking_id"])
    except Exception:  # noqa: BLE001 - never undo or hold up a booking over its email
        log.warning("booking email failed: %s", booking.get("booking_id"))


def cancelled(db, booking_id: str, to: str, refund_cents: int, fee_cents: int) -> None:
    """Email `to` (the signed-in person who cancelled) what LiteAPI reported for the cancel of `booking_id`. Once per booking."""
    try:
        row = familydb.row(db, "SELECT * FROM matrix_bookings WHERE booking_id = :b AND sample = 0", b=booking_id)
        if row is None or smtp() is None or not address_ok(to) or not claim(db, "cancel_email_at", booking_id):
            return
        paid = familydb.row(db, "SELECT charge_cents FROM matrix_payments WHERE booking_id = :b", b=booking_id)
        refund_cents = refund_cents if paid is None else min(refund_cents, paid["charge_cents"])      # with a voucher LiteAPI's refund is the undiscounted price: never say more than the card paid
        mail = cancelled_mail({"hotel": row["hotel"], "checkin": row["checkin"], "checkout": row["checkout"], "booking_id": booking_id, "refund_cents": refund_cents, "fee_cents": fee_cents,
                               "sandbox": _sandbox()})
        _spawn(_send, to, mail, booking_id)
    except Exception:  # noqa: BLE001
        log.warning("booking email failed: %s", booking_id)
