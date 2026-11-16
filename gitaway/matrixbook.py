"""Booking a trip matrix square's stays through LiteAPI: its sandbox (F-233, D-480 to D-489) or, with a live key, for real through LiteAPI's payment form (F-274, D-840 to D-849).

    clean_guest(first, last, email)         (liteapi.Guest, {}) or (None, {field: problem}): the lead guest, trimmed, length-limited, letters only in the names
    prepare(parts, dates, family, sample)   a Prep: each stay's offer prebooked (the room checked and its final price read), or why it could not be
    hold(family, prep, square) / held(family, token, square)   the prebooked rooms kept 15 minutes in the process (5 a family), bound to their square, for the guest form to finish
    book(prep, guest, db, family, trip_id, user_id)   a Result: each stay booked once, stored in the family's `matrix_bookings`, a repeated press finds the stored row
    allow(person)                           the per-person limit on Book presses (counted in community.db)
    mode(), pays_by_form()                  what Book does; whether the card is paid in LiteAPI's form (LIVE, or a sandbox key with GITAWAY_SANDBOX_FORM=1)
    code_shape(code)                        a voucher code's shape, checked here before LiteAPI is asked
    save_prebook / pay_start / finish       the form's path: the ids saved at once, the guest kept until booked, the booking made once after payment
    cancel(db, family, booking_id, user_id) a booking cancelled through LiteAPI and what came back

With a sandbox key: no real card or money is involved, and every word on a sheet says "Sandbox booking: nothing is charged". With a live key (`mode()` LIVE): the card is LiteAPI's own
form's (GitAway never renders a card field, sees or stores a card), the stay is prebooked with `usePaymentSdk`, saved at once in `matrix_payments`, paid in the form and booked with
`TRANSACTION_ID` (`finish`); `liteapi` refuses every other live call. On the showcase (sample squares) nothing is sent to LiteAPI: a stand-in prebook and booking say "Sample booking: nothing is booked or
charged". A guest's name and email are personal data: validated here, sent to LiteAPI and kept nowhere by us (D-510), escaped on output, never logged.
"""

import hashlib
import logging
import os
import re
import secrets
import threading
import time
from dataclasses import dataclass, replace
from datetime import date

from sqlalchemy.exc import IntegrityError

from gitaway import auth, catalog, familydb, liteapi, showcase

NOTHING_CHARGED = "Sandbox booking: nothing is charged"
log = logging.getLogger(__name__)
SAMPLE_WORDS = "Sample booking: nothing is booked or charged"
SOON_WORDS = "Booking opens soon"
LIVE_WORDS = "Sold by Nuitée through LiteAPI. Your card is charged when you pay"
SANDBOX, STAND_IN, SOON, LIVE = "sandbox", "stand-in", "soon", "live"
MANY = "many"                   # a square of several stays is not booked in one go with the payment form (one payment, one stay)
PURGE_UNPAID, PURGE_GUEST = 1, 7      # days: an unpaid prebook row is dropped after one, a lead guest's name and email are blanked after seven
CODE_MISSES_A_DAY = 30          # wrong codes the whole site answers in a day before "Have a code?" is off until tomorrow (L1: codes cannot be guessed freely)
TOLERANCE_CENTS = 100           # a room's final price within a dollar of the square's is "the price shown" (a live margin lands within a cent; this is for rounding, not for a moved price)
_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,31}$")
HOLD = 15 * 60                  # seconds a prebooked room is kept for the guest form
HELD_PER_FAMILY = 5             # prebooked rooms kept per family, the oldest dropped first
PER_MINUTE, PER_DAY = 5, 20     # Book presses a person may make (both routes), counted in community.db
NAME_MAX, EMAIL_MAX = 40, 120
_NAME = re.compile(r"^[^\W\d_](?:[^\W\d_]|[ '’.\-])*$")      # letters first; letters, spaces, apostrophes, dots and hyphens after
_EMAIL = re.compile(r"^[A-Za-z0-9.!#$%&*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.\-]*[A-Za-z0-9])?\.[A-Za-z]{2,}\Z", re.ASCII)      # printable ASCII before the @: no NUL, DEL, bidi marks or quotes
SAID = {liteapi.GONE: "That room was just taken. Go back to the matrix and open the square again for today’s rooms.",
        liteapi.OVER: "Today’s searches are used up. Try again tomorrow.",
        liteapi.BUSY: "LiteAPI is busy right now. Try again in a minute.",
        liteapi.OFF: "Booking needs the LiteAPI sandbox key; this site has none (or a live one, which never books).",
        liteapi.FAILED: "LiteAPI did not answer just now. Nothing was booked. Try again in a minute.",
        liteapi.DUPLICATE: "LiteAPI says this room is already booked, but we could not find the booking. Check your bookings with LiteAPI before booking again.",
        liteapi.BAD_CODE: "That code is not valid. Check it, or book without one.",
        MANY: "A trip of several places is booked one stay at a time for now. Book one place’s stay here and the other another time."}


def mode() -> str:
    """What Book does (F-267, D-768, reopened by F-274, D-841): SANDBOX books in LiteAPI's sandbox (a `sand_` key, as F-233; a sample square is a stand-in by its own flag); LIVE books for
    real through LiteAPI's payment form (a live key in production, for anyone signed in); STAND_IN plays the sample booking and asks LiteAPI to book nothing (a live key anywhere but
    production unless GITAWAY_LIVE_BOOKING=1, and the showcase with one); SOON books nothing and says so (a live key in production switched off with GITAWAY_LIVE_BOOKING=0).
    `liteapi` refuses every live call that is not the payment form's path, whatever this says."""
    if liteapi.mode() == "live":
        if showcase.on():
            return STAND_IN
        return LIVE if liteapi.real_booking() else SOON if auth.production() else STAND_IN
    return SANDBOX


def pays_by_form() -> bool:
    """Is the card paid in LiteAPI's payment form (and the booking made with the transaction id)? Always with real booking; with a sandbox key only when GITAWAY_SANDBOX_FORM=1, so
    the whole path can be tried against the sandbox with its test card, and by default the sandbox books as it did in F-233."""
    return mode() == LIVE or (mode() == SANDBOX and os.environ.get("GITAWAY_SANDBOX_FORM", "").strip() == "1")


def words(sample: bool = False) -> str:
    """The one sentence that says what a booking here is, for the sheet's pill and the panel's foot."""
    if sample or mode() == STAND_IN:
        return SAMPLE_WORDS
    return {SOON: SOON_WORDS, LIVE: LIVE_WORDS}.get(mode(), NOTHING_CHARGED if not pays_by_form() else "Sandbox booking: the form takes LiteAPI’s test card, nothing is charged")


def stands_in(sample: bool = False) -> bool:
    """Is this booking the sample stand-in: a sample square, or a live key off production (its squares are real but nothing may be booked)?"""
    return sample or mode() == STAND_IN


@dataclass(frozen=True)
class Row:
    place: str
    part: object                 # tripmatrix.StayPart
    prebook: liteapi.Prebook

    @property
    def total_cents(self) -> int:
        """What the stay costs: what is charged (LiteAPI's final price, less a voucher's discount) plus what the hotel takes at the desk."""
        return self.prebook.charge_cents + self.prebook.due_at_stay_cents


@dataclass(frozen=True)
class Prep:
    status: str                  # liteapi.OK or why not
    rows: tuple = ()
    sample: bool = False
    token: str = ""
    voucher: str = ""            # the code the rooms were prebooked with ("" for none): what the checkout shows as applied

    @property
    def ok(self) -> bool:
        return self.status == liteapi.OK

    @property
    def total_cents(self) -> int:
        return sum(r.total_cents for r in self.rows)

    @property
    def changed(self) -> bool:
        """The room's price (or terms) moved from what the square showed, so the person is told before booking."""
        return any(r.prebook.changed or abs(r.prebook.charge_cents + r.prebook.discount_cents + r.prebook.due_at_stay_cents - r.part.cents) > TOLERANCE_CENTS for r in self.rows)

    @property
    def words(self) -> str:
        return SAMPLE_WORDS if self.sample else words()


@dataclass(frozen=True)
class Done:
    booking_id: str
    hotel: str
    room: str
    place: str
    checkin: str
    checkout: str
    total_cents: int
    due_at_stay_cents: int
    refundable: bool
    confirmation: str
    sample: bool
    trip_id: str = ""


@dataclass(frozen=True)
class Result:
    status: str                  # liteapi.OK or why not
    done: tuple = ()             # every stay booked so far, this press or an earlier one
    left: int = 0                # stays of the square not booked yet

    @property
    def ok(self) -> bool:
        return self.status == liteapi.OK and not self.left


# ---- the lead guest ---------------------------------------------------------------------------------------------------

def _tidy(v) -> str:
    return " ".join(str(v or "").split())


def clean_guest(first, last, email):
    """(Guest, {}) or (None, {field: problem}). The names are letters, spaces, apostrophes, dots and hyphens (1 to NAME_MAX); the email one address (at most EMAIL_MAX):
    LiteAPI's sandbox books anything, so every check is ours."""
    f, l, e = _tidy(first), _tidy(last), _tidy(email)
    errors = {}
    for field, v, what in (("first", f, "first name"), ("last", l, "last name")):
        if not v:
            errors[field] = f"Add the lead guest’s {what}."
        elif len(v) > NAME_MAX or not _NAME.match(v):
            errors[field] = f"The {what} is letters only, up to {NAME_MAX}."
    if not e:
        errors["email"] = "Add an email for the confirmation."
    elif len(e) > EMAIL_MAX or not _EMAIL.match(e) or ".." in e:
        errors["email"] = "That does not look like an email address."
    return (None, errors) if errors else (liteapi.Guest(f, l, e), {})


def code_shape(text) -> tuple:
    """(code, "") or ("", problem): a voucher code as typed, trimmed, letters, digits, hyphens and underscores, 2 to 32. "" is no code. Whether LiteAPI accepts it is its answer to prebook."""
    c = _tidy(text)
    if not c:
        return "", ""
    return (c, "") if _CODE.match(c) else ("", "A code is letters and digits, up to 32.")


# ---- what else the checkout asks (F-251) -------------------------------------------------------------------------------

REQUESTS = ("Crib in the room", "Rooms close together", "High floor", "Quiet room", "Early check-in", "Accessible room", "Vegetarian breakfast")
ARRIVALS = ("Morning", "Afternoon", "Evening", "Late night")
PHONE_MAX = 20
_PHONE = re.compile(r"^\+?[0-9][0-9 ().\-]{4,18}[0-9]$")


@dataclass(frozen=True)
class Extras:
    """The checkout's contact and requests questions. LiteAPI's sandbox is sent the lead guest's name and email only: these are asked, shown on the review and the pass and then gone
    (never sent, never stored, never logged: D-510 and D-620)."""
    phone: str = ""
    requests: tuple = ()
    arrive: str = ""


def clean_extras(phone, requests, arrive):
    """(Extras, {field: problem}): the cleaned values even when the phone is bad (the form echoes them back). The phone is optional: digits, spaces, dots, brackets and hyphens (a leading +), at most PHONE_MAX. The requests and the arrival are the
    fixed lists above (a word that is not on them is dropped: a form cannot add a request of its own); `requests` is one string, the picked requests joined by "|"."""
    p = _tidy(phone)
    errors = {}
    if p and (len(p) > PHONE_MAX or not _PHONE.match(p)):
        errors["phone"] = "That does not look like a phone number."
    picked = {x.strip() for x in str(requests or "").split("|")}
    arrive = _tidy(arrive)
    return Extras(p, tuple(r for r in REQUESTS if r in picked), arrive if arrive in ARRIVALS else ""), errors


def _when_gmt(iso: str) -> str:
    """"Dec 10, 6:59 PM GMT" from LiteAPI's cancel time, else its own text."""
    from datetime import datetime
    try:
        at = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return iso
    return f"{at:%b} {at.day}, {at.hour % 12 or 12}:{at:%M} {'AM' if at.hour < 12 else 'PM'} GMT"


def policy_words(pre) -> str:
    """What LiteAPI says about cancelling, in sentences: a refundable stay's first deadline, then what cancelling costs after it and after each later step (LiteAPI gave two for a real
    San Diego stay: $148.88 from Dec 10, the whole price from Dec 11), a non-refundable one's plain word."""
    if not pre.refundable:
        return "Non-refundable: if you cancel, nothing comes back."
    costly = [(t, f) for t, f in pre.tiers if f > 0]      # a step of 0 is no charge: LiteAPI's "fully refundable"
    if pre.tiers and not costly:
        return "Free cancellation: nothing is charged if you cancel."
    if costly:
        (first, fee), later = costly[0], costly[1:]
        return (f"Free cancellation until {_when_gmt(first)}. After that, cancelling costs {catalog.money(fee)}" + "".join(f"; from {_when_gmt(t)}, {catalog.money(f)}" for t, f in later) + ".")
    return "Refundable: you can cancel it from the booking page."


def with_extras(guest: liteapi.Guest, extras: Extras) -> liteapi.Guest:
    """The lead guest with the mobile number and the requests the checkout asked, for a real booking (the card sandbox booking sends the name and email only): the requests are words
    of the fixed list, so a remark is never typed text."""
    asks = "; ".join(extras.requests) + (f". Arriving in the {extras.arrive.lower()}." if extras.arrive else "")
    return replace(guest, phone=extras.phone, remarks=asks.strip(". ")[:200] + ("." if asks.strip(". ") else ""))


# ---- prebooking ------------------------------------------------------------------------------------------------------

def _sample_prebook(part, a: date, b: date) -> liteapi.Prebook:
    return liteapi.Prebook("sample", "", part.room, a, b, part.cents - part.due_at_stay_cents, part.due_at_stay_cents, part.refundable, False, liteapi.now())


def prepare(parts, dates, family: str = "", sample: bool = False, sdk: bool = False, voucher: str = "") -> Prep:
    """Prebook each stay's offer (one call each, in the square's order). A stay with no offer of its own (a sample square) gets a stand-in; any other failure ends it. `sdk`: ask for the
    payment form's keys (real booking, or the sandbox with the form), which pays one stay at a time; `voucher`: a code LiteAPI reprices the stay with."""
    if sdk and not sample and len(parts) > 1:
        return Prep(MANY)
    rows = []
    for part, (place, a, b) in zip(parts, dates):
        if sample or not part.offer_id:
            rows.append(Row(place, part, _sample_prebook(part, a, b)))
            continue
        got = liteapi.prebook(part.offer_id, family, sdk=sdk, voucher=voucher)
        if not got.ok:
            return Prep(got.status, (), False)
        pre = got.items[0]
        if (pre.checkin, pre.checkout) != (a, b):      # a rate for other nights is never booked as these
            return Prep(liteapi.FAILED, (), False)
        if sdk and not (pre.secret_key and pre.transaction_id):      # the payment form cannot open without them
            return Prep(liteapi.FAILED, (), False)
        rows.append(Row(place, part, pre))
    return Prep(liteapi.OK, tuple(rows), sample, secrets.token_urlsafe(12), voucher)


_HELD: dict = {}      # token -> (family, prep, kept at, the square it was prebooked for)
_LOCK = threading.Lock()


def hold(family: str, prep: Prep, square: tuple) -> str:
    """Keep the prebooked room for `family`, bound to `square` (its key and the address words it was asked with). At most HELD_PER_FAMILY a family: its oldest goes first."""
    with _LOCK:
        for k in [k for k, v in _HELD.items() if time.monotonic() - v[2] > HOLD]:
            del _HELD[k]
        mine = [k for k, v in _HELD.items() if v[0] == family]
        for k in mine[: max(0, len(mine) - HELD_PER_FAMILY + 1)]:
            del _HELD[k]
        _HELD[prep.token] = (family, prep, time.monotonic(), square)
    return prep.token


def held(family: str, token: str, square: tuple) -> Prep | None:
    """The room kept under `token`, only for the family and the very square it was kept for."""
    with _LOCK:
        found = _HELD.get(token or "")
    return found[1] if found and found[0] == family and found[3] == square and time.monotonic() - found[2] <= HOLD else None


def allow(person: str) -> bool:
    """Count one Book press by `person` and say whether it may go on: at most PER_MINUTE a minute and PER_DAY a day, kept in community.db (who and when, nothing else)."""
    from datetime import timedelta

    from sqlalchemy import text

    from gitaway import community
    at = liteapi.now()
    with _LOCK, community.connect() as db:
        db.conn.execute(text("DELETE FROM book_presses WHERE at < :old"), {"old": (at - timedelta(days=2)).isoformat()})
        minute = db.conn.execute(text("SELECT COUNT(*) FROM book_presses WHERE person = :p AND at > :t"), {"p": person, "t": (at - timedelta(minutes=1)).isoformat()}).scalar()
        day = db.conn.execute(text("SELECT COUNT(*) FROM book_presses WHERE person = :p AND at > :t"), {"p": person, "t": (at - timedelta(days=1)).isoformat()}).scalar()
        if minute >= PER_MINUTE or day >= PER_DAY:
            db.conn.commit()
            return False
        db.conn.execute(text("INSERT INTO book_presses (person, at) VALUES (:p, :t)"), {"p": person or "guest", "t": at.isoformat()})
        db.conn.commit()
    return True


def forget() -> None:
    with _LOCK:
        _HELD.clear()


# ---- booking -----------------------------------------------------------------------------------------------------------

def reference(family: str, token: str, i: int) -> str:
    """The idempotency key of one stay of one prebooked square: pressing Book twice sends the same one, so LiteAPI books once."""
    return hashlib.sha256(f"{family}|{token}|{i}".encode()).hexdigest()[:32]


def _stored(row) -> Done:
    return Done(row["booking_id"], row["hotel"], row["room"], row["place"], row["checkin"], row["checkout"], row["total_cents"], row["due_at_stay_cents"], bool(row["refundable"]),
                row["confirmation"], bool(row["sample"]), row["trip_id"])


def _insert(db, ref, trip_id, user_id, *, booking_id, place, hotel, room, checkin, checkout, total, due, refundable, confirmation, sample) -> None:
    familydb.run(db, "INSERT INTO matrix_bookings (id, trip_id, user_id, booking_id, place, hotel, room, checkin, checkout, total_cents, due_at_stay_cents, refundable, confirmation, "
                     "sample, created_at) VALUES (:i, :t, :u, :b, :p, :h, :r, :a, :o, :c, :d, :f, :k, :s, :now)",
                 i=ref, t=trip_id, u=user_id, b=booking_id, p=place, h=hotel[:120], r=room[:120], a=checkin, o=checkout, c=total, d=due, f=1 if refundable else 0,
                 k=confirmation[:60], s=1 if sample else 0, now=familydb.now())


def _save(db, ref, trip_id, user_id, row: Row, booking: liteapi.Booking | None, sample: bool) -> None:
    pre = row.prebook
    _insert(db, ref, trip_id, user_id, booking_id=("SAMPLE-" + ref[:8].upper()) if booking is None else booking.booking_id, place=row.place,
            hotel=row.part.name if booking is None else (booking.hotel or row.part.name), room=pre.room, checkin=pre.checkin.isoformat(), checkout=pre.checkout.isoformat(),
            total=(booking.cents + pre.due_at_stay_cents) if booking else row.total_cents, due=pre.due_at_stay_cents, refundable=pre.refundable,
            confirmation="SAMPLE" if booking is None else booking.confirmation, sample=sample)


def book(prep: Prep, guest: liteapi.Guest, db, family: str, trip_id: str, user_id: str) -> Result:
    """Book every stay of `prep` for `guest`. A stay already stored under its reference (an earlier press) is not booked again. Stops at the first stay LiteAPI will not
    book, with the ones before it stored: the next press books only what is left."""
    done = []
    for i, row in enumerate(prep.rows):
        ref = reference(family, prep.token, i)
        mine = familydb.rows(db, "SELECT * FROM matrix_bookings WHERE id = :i", i=ref)
        if mine:
            done.append(_stored(mine[0]))
            continue
        booking = None
        if not prep.sample:
            got = liteapi.book(row.prebook.prebook_id, guest, ref, family)
            if got.status == liteapi.DUPLICATE:      # LiteAPI holds a booking under our reference but we hold no row (an answer was lost): ask for it, never say it is done unseen
                got = liteapi.booking_for(ref, family)
                if not got.ok:
                    return Result(liteapi.DUPLICATE, tuple(done), len(prep.rows) - len(done))
            if not got.ok:
                return Result(got.status, tuple(done), len(prep.rows) - len(done))
            booking = got.items[0]
        try:
            with familydb.transaction(db):
                _save(db, ref, trip_id, user_id, row, booking, prep.sample)
        except IntegrityError:      # a second press of the same square stored this stay first: its row is the booking
            pass
        done.append(_stored(familydb.rows(db, "SELECT * FROM matrix_bookings WHERE id = :i", i=ref)[0]))
    return Result(liteapi.OK, tuple(done), 0)


# ---- the payment form's path (F-274, D-842) ----------------------------------------------------------------------------------

def mark_cancelled(session, trip_id: str, booking_id: str) -> None:
    """The cancelled stay stays on the family's trip but says so ("Cancelled on LiteAPI"), so the plan does not count a stay that is gone. Cancelling again changes nothing."""
    from gitaway import importer, tripimport as ti
    plan = importer.plan_of(session, trip_id) if trip_id else None
    if plan is None or not any(h.confirmation == booking_id and not h.booked_on.startswith("Cancelled") for h in plan.hotels):
        return
    hotels = tuple(replace(h, booked_on="Cancelled on " + (h.booked_on.replace("Booked on ", "") or "LiteAPI")) if h.confirmation == booking_id else h for h in plan.hotels)
    importer.save(session, replace(plan, hotels=hotels), replace=trip_id)


def stuck(db, before: str) -> list:
    """The payments left `paying` (the guest was sent to the card form) since before `before` (an ISO time): paid, perhaps, and not booked."""
    return familydb.rows(db, "SELECT * FROM matrix_payments WHERE status = 'paying' AND updated_at < :t ORDER BY updated_at", t=before)


def _misses_today() -> int:
    from datetime import timedelta

    from sqlalchemy import text

    from gitaway import community
    with community.connect() as db:
        return db.conn.execute(text("SELECT COUNT(*) FROM book_presses WHERE person = 'code-miss' AND at > :t"), {"t": (liteapi.now() - timedelta(days=1)).isoformat()}).scalar()


def codes_open() -> bool:
    """Is "Have a code?" on? It goes off for the rest of the day (24 hours) once the whole site has been told CODE_MISSES_A_DAY wrong codes."""
    return _misses_today() < CODE_MISSES_A_DAY


def code_missed() -> None:
    """Count one wrong code (site-wide, in community.db with the presses: no one is named) and log once when that turns codes off."""
    from sqlalchemy import text

    from gitaway import community
    with community.connect() as db:
        db.conn.execute(text("INSERT INTO book_presses (person, at) VALUES ('code-miss', :t)"), {"t": liteapi.now().isoformat()})
        db.conn.commit()
    if _misses_today() == CODE_MISSES_A_DAY:
        log.warning("booking codes are off for today: %s wrong codes were tried", CODE_MISSES_A_DAY)


def purge(db) -> None:
    """Drop what nobody paid for after PURGE_UNPAID days and blank every lead guest's name and email after PURGE_GUEST days (the booking id and amounts stay: they are the record)."""
    from datetime import datetime, timedelta, timezone
    at = datetime.now(timezone.utc)
    with familydb.transaction(db):
        familydb.run(db, "DELETE FROM matrix_payments WHERE status = 'prebooked' AND created_at < :t", t=(at - timedelta(days=PURGE_UNPAID)).isoformat(timespec="seconds"))
        familydb.run(db, "UPDATE matrix_payments SET guest_first = '', guest_last = '', guest_email = '', guest_phone = '', guest_remarks = '' WHERE created_at < :t AND guest_email != ''",
                     t=(at - timedelta(days=PURGE_GUEST)).isoformat(timespec="seconds"))


def save_prebook(db, token: str, user_id: str, row: Row) -> None:
    """Save the prebook the moment it answers: LiteAPI cannot give its `prebookId` and `transactionId` back later. The same token twice keeps the first row. The form's `secretKey` is
    not saved (only the page that shows the form needs it)."""
    purge(db)
    pre = row.prebook
    with familydb.transaction(db):
        familydb.run(db, "INSERT OR IGNORE INTO matrix_payments (id, user_id, place, hotel, room, checkin, checkout, prebook_id, transaction_id, charge_cents, due_at_stay_cents, "
                         "refundable, voucher_code, discount_cents, policy, status, created_at, updated_at) VALUES (:i, :u, :p, :h, :r, :a, :o, :pb, :tx, :c, :d, :f, :v, :x, :pol, 'prebooked', :now, :now)",
                     i=token, u=user_id, p=row.place, h=row.part.name[:120], r=pre.room[:120], a=pre.checkin.isoformat(), o=pre.checkout.isoformat(), pb=pre.prebook_id, tx=pre.transaction_id,
                     c=pre.charge_cents, d=pre.due_at_stay_cents, f=1 if pre.refundable else 0, v=pre.voucher_code, x=pre.discount_cents, pol=policy_words(pre)[:300], now=familydb.now())


def payment(db, token: str) -> dict | None:
    return familydb.row(db, "SELECT * FROM matrix_payments WHERE id = :i", i=token)


def pay_start(db, token: str, user_id: str, guest: liteapi.Guest, trip_id: str) -> bool:
    """The guest filled in the form and the payment form is about to open: keep the lead guest (the booking after the payment needs the name, email, mobile number and requests, and
    the page is left for the form's own) and the trip. Only the person who prebooked, and only before it is booked. False: nothing to pay for."""
    with familydb.transaction(db):
        return familydb.run(db, "UPDATE matrix_payments SET guest_first = :f, guest_last = :l, guest_email = :e, guest_phone = :p, guest_remarks = :m, trip_id = :t, status = 'paying', "
                                "updated_at = :now WHERE id = :i AND user_id = :u AND status IN ('prebooked', 'paying')", f=guest.first, l=guest.last, e=guest.email, p=guest.phone,
                            m=guest.remarks, t=trip_id, i=token, u=user_id, now=familydb.now()) == 1


def finish(db, family: str, token: str, user_id: str) -> Result:
    """After the payment form: book the stay with the transaction id saved at prebook, once (a second call, or a reload of the return page, finds the stored booking). Nothing is
    booked unless the guest was saved (the form was opened); LiteAPI refuses a transaction that was not paid (HTTP 400, code 2014) and then nothing is stored and the row waits
    for another try. The guest's name and email are blanked once it is booked."""
    pay = payment(db, token)
    if not pay or pay["user_id"] != user_id:
        return Result(liteapi.GONE)
    ref = reference(family, token, 0)
    mine = familydb.rows(db, "SELECT * FROM matrix_bookings WHERE id = :i", i=ref)
    if not mine:
        if pay["status"] != "paying":
            return Result(liteapi.FAILED)
        guest, errors = clean_guest(pay["guest_first"], pay["guest_last"], pay["guest_email"])
        if errors:
            return Result(liteapi.FAILED)
        guest = replace(guest, phone=pay["guest_phone"] or "", remarks=pay["guest_remarks"] or "")
        got = liteapi.book(pay["prebook_id"], guest, ref, family, transaction_id=pay["transaction_id"])
        if got.status == liteapi.DUPLICATE:
            got = liteapi.booking_for(ref, family)
        if not got.ok:
            return Result(got.status)
        booking = got.items[0]
        try:
            with familydb.transaction(db):
                _insert(db, ref, pay["trip_id"], user_id, booking_id=booking.booking_id, place=pay["place"], hotel=booking.hotel or pay["hotel"], room=pay["room"], checkin=pay["checkin"],
                        checkout=pay["checkout"], total=pay["charge_cents"] + pay["due_at_stay_cents"], due=pay["due_at_stay_cents"], refundable=booking.refundable or bool(pay["refundable"]),
                        confirmation=booking.confirmation, sample=False)
        except IntegrityError:      # a second call stored it first
            pass
        mine = familydb.rows(db, "SELECT * FROM matrix_bookings WHERE id = :i", i=ref)
    with familydb.transaction(db):
        familydb.run(db, "UPDATE matrix_payments SET status = 'booked', booking_id = :b, guest_first = '', guest_last = '', guest_email = '', guest_phone = '', guest_remarks = '', updated_at = :now WHERE id = :i",
                     b=mine[0]["booking_id"], i=token, now=familydb.now())
    return Result(liteapi.OK, (_stored(mine[0]),), 0)


def cancel(db, family: str, booking_id: str, user_id: str) -> tuple:
    """Cancel a stay booked through LiteAPI (not a sample one): (status, what_came_back). The status is liteapi.OK with a `liteapi.Cancelled` (its refund and fee in cents), or why not.
    Cancelling again answers what was found the first time and asks LiteAPI nothing."""
    booked = familydb.row(db, "SELECT * FROM matrix_bookings WHERE booking_id = :b AND sample = 0", b=booking_id)
    if not booked:
        return liteapi.GONE, None
    done = familydb.row(db, "SELECT * FROM matrix_cancels WHERE booking_id = :b", b=booking_id)
    if done:
        return liteapi.OK, liteapi.Cancelled(booking_id, done["status"], done["refund_cents"], done["fee_cents"], liteapi.now())
    got = liteapi.cancel(booking_id, family)
    if not got.ok:
        return got.status, None
    c = got.items[0]
    with familydb.transaction(db):
        familydb.run(db, "INSERT OR IGNORE INTO matrix_cancels (booking_id, user_id, status, refund_cents, fee_cents, cancelled_at) VALUES (:b, :u, :s, :r, :f, :now)",
                     b=booking_id, u=user_id, s=c.status, r=c.refund_cents, f=c.fee_cents, now=familydb.now())
    return liteapi.OK, c


def cancelled(db, booking_id: str) -> dict | None:
    """What LiteAPI said came back when this booking was cancelled here, else None."""
    return familydb.row(db, "SELECT * FROM matrix_cancels WHERE booking_id = :b", b=booking_id)


def add_to_trip(session, trip_id: str, done) -> None:
    """Put the booked stays on the family's trip as lodging ("Booked on LiteAPI sandbox", or "LiteAPI" when it was for real), so the trip's cockpit shows them. Pressing Book again adds nothing twice."""
    from dataclasses import replace
    from datetime import datetime, time

    from gitaway import importer, tripimport as ti
    plan = importer.plan_of(session, trip_id)
    if plan is None:
        return
    have = {h.confirmation for h in plan.hotels}
    where = "GitAway sample" if any(d.sample for d in done) else "LiteAPI" if mode() == LIVE else "LiteAPI sandbox"
    new = tuple(ti.Lodging(d.hotel[:80], d.place, datetime.combine(date.fromisoformat(d.checkin), time(15)), datetime.combine(date.fromisoformat(d.checkout), time(11)),
                           d.booking_id, d.room[:80], 1, "", where) for d in done if d.booking_id not in have)
    if new:
        importer.save(session, replace(plan, hotels=plan.hotels + new, booked_on=where if plan.booked_on in ("", "elsewhere") else plan.booked_on), replace=trip_id)
