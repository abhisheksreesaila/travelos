"""Booking a trip matrix square's stays through LiteAPI's sandbox (F-233, D-480 to D-489): plain functions, no framework.

    clean_guest(first, last, email)         (liteapi.Guest, {}) or (None, {field: problem}): the lead guest, trimmed, length-limited, letters only in the names
    prepare(parts, dates, family, sample)   a Prep: each stay's offer prebooked (the room checked and its final price read), or why it could not be
    hold(family, prep, square) / held(family, token, square)   the prebooked rooms kept 15 minutes in the process (5 a family), bound to their square, for the guest form to finish
    book(prep, guest, db, family, trip_id, user_id)   a Result: each stay booked once, stored in the family's `matrix_bookings`, a repeated press finds the stored row
    allow(person)                           the per-person limit on Book presses (counted in community.db)

Only the sandbox: `liteapi.prebook` and `liteapi.book` refuse any key that is not `sand_...`, so no real card or money is ever involved, and every word on a sheet says
"Sandbox booking: nothing is charged". On the showcase (sample squares) nothing is sent to LiteAPI: a stand-in prebook and booking say "Sample booking: nothing is booked or
charged". A guest's name and email are personal data: validated here, sent to LiteAPI and kept nowhere by us (D-490), escaped on output, never logged.
"""

import hashlib
import re
import secrets
import threading
import time
from dataclasses import dataclass
from datetime import date

from gitaway import familydb, liteapi

NOTHING_CHARGED = "Sandbox booking: nothing is charged"
SAMPLE_WORDS = "Sample booking: nothing is booked or charged"
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
        liteapi.DUPLICATE: "LiteAPI says this room is already booked, but we could not find the booking. Check your bookings with LiteAPI before booking again."}


@dataclass(frozen=True)
class Row:
    place: str
    part: object                 # tripmatrix.StayPart
    prebook: liteapi.Prebook

    @property
    def total_cents(self) -> int:
        """What the stay costs: LiteAPI's final price plus what the hotel takes at the desk."""
        return self.prebook.cents + self.prebook.due_at_stay_cents


@dataclass(frozen=True)
class Prep:
    status: str                  # liteapi.OK or why not
    rows: tuple = ()
    sample: bool = False
    token: str = ""

    @property
    def ok(self) -> bool:
        return self.status == liteapi.OK

    @property
    def total_cents(self) -> int:
        return sum(r.total_cents for r in self.rows)

    @property
    def changed(self) -> bool:
        """The room's price (or terms) moved from what the square showed, so the person is told before booking."""
        return any(r.prebook.changed or r.total_cents != r.part.cents for r in self.rows)

    @property
    def words(self) -> str:
        return SAMPLE_WORDS if self.sample else NOTHING_CHARGED


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


# ---- prebooking ------------------------------------------------------------------------------------------------------

def _sample_prebook(part, a: date, b: date) -> liteapi.Prebook:
    return liteapi.Prebook("sample", "", part.room, a, b, part.cents - part.due_at_stay_cents, part.due_at_stay_cents, part.refundable, False, liteapi.now())


def prepare(parts, dates, family: str = "", sample: bool = False) -> Prep:
    """Prebook each stay's offer (one call each, in the square's order). A stay with no offer of its own (a sample square) gets a stand-in; any other failure ends it."""
    rows = []
    for part, (place, a, b) in zip(parts, dates):
        if sample or not part.offer_id:
            rows.append(Row(place, part, _sample_prebook(part, a, b)))
            continue
        got = liteapi.prebook(part.offer_id, family)
        if not got.ok:
            return Prep(got.status, (), False)
        if (got.items[0].checkin, got.items[0].checkout) != (a, b):      # a rate for other nights is never booked as these
            return Prep(liteapi.FAILED, (), False)
        rows.append(Row(place, part, got.items[0]))
    return Prep(liteapi.OK, tuple(rows), sample, secrets.token_urlsafe(12))


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


def _save(db, ref, trip_id, user_id, row: Row, booking: liteapi.Booking | None, sample: bool) -> None:
    pre = row.prebook
    id_ = ("SAMPLE-" + ref[:8].upper()) if booking is None else booking.booking_id
    hotel = row.part.name if booking is None else (booking.hotel or row.part.name)
    familydb.run(db, "INSERT INTO matrix_bookings (id, trip_id, user_id, booking_id, place, hotel, room, checkin, checkout, total_cents, due_at_stay_cents, refundable, confirmation, "
                     "sample, created_at) VALUES (:i, :t, :u, :b, :p, :h, :r, :a, :o, :c, :d, :f, :k, :s, :now)",
                 i=ref, t=trip_id, u=user_id, b=id_, p=row.place, h=hotel[:120], r=pre.room[:120], a=pre.checkin.isoformat(), o=pre.checkout.isoformat(),
                 c=(booking.cents + pre.due_at_stay_cents) if booking else row.total_cents, d=pre.due_at_stay_cents, f=1 if pre.refundable else 0,
                 k=("SAMPLE" if booking is None else booking.confirmation)[:60], s=1 if sample else 0, now=familydb.now())


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
        with familydb.transaction(db):
            _save(db, ref, trip_id, user_id, row, booking, prep.sample)
        done.append(_stored(familydb.rows(db, "SELECT * FROM matrix_bookings WHERE id = :i", i=ref)[0]))
    return Result(liteapi.OK, tuple(done), 0)


def add_to_trip(session, trip_id: str, done) -> None:
    """Put the booked stays on the family's trip as lodging ("Booked on LiteAPI sandbox"), so the trip's cockpit shows them. Pressing Book again adds nothing twice."""
    from dataclasses import replace
    from datetime import datetime, time

    from gitaway import importer, tripimport as ti
    plan = importer.plan_of(session, trip_id)
    if plan is None:
        return
    have = {h.confirmation for h in plan.hotels}
    where = "GitAway sample" if any(d.sample for d in done) else "LiteAPI sandbox"
    new = tuple(ti.Lodging(d.hotel[:80], d.place, datetime.combine(date.fromisoformat(d.checkin), time(15)), datetime.combine(date.fromisoformat(d.checkout), time(11)),
                           d.booking_id, d.room[:80], 1, "", where) for d in done if d.booking_id not in have)
    if new:
        importer.save(session, replace(plan, hotels=plan.hotels + new, booked_on=where if plan.booked_on in ("", "elsewhere") else plan.booked_on), replace=trip_id)
