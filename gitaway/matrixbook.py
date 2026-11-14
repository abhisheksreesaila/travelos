"""Booking a trip matrix square's stays through LiteAPI's sandbox (F-233, D-480 to D-489): plain functions, no framework.

    clean_guest(first, last, email)         (liteapi.Guest, {}) or (None, {field: problem}): the lead guest, trimmed, length-limited, letters only in the names
    prepare(parts, dates, family, sample)   a Prep: each stay's offer prebooked (the room checked and its final price read), or why it could not be
    hold(family, prep) / held(family, token)   the prebooked rooms kept 15 minutes in the process, for the guest form to finish
    book(prep, guest, db, family, trip_id, user_id)   a Result: each stay booked once, stored in the family's `matrix_bookings`, a repeated press finds the stored row
    for_trip(db, trip_id)                   the stays booked for a trip, for its page

Only the sandbox: `liteapi.prebook` and `liteapi.book` refuse any key that is not `sand_...`, so no real card or money is ever involved, and every word on a sheet says
"Sandbox booking: nothing is charged". On the showcase (sample squares) nothing is sent to LiteAPI: a stand-in prebook and booking say "Sample booking: nothing is booked or
charged". A guest's name and email are personal data: validated here, stored in the family's own database, escaped on output, never logged.
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
HELD_MAX = 200
NAME_MAX, EMAIL_MAX = 40, 120
_NAME = re.compile(r"^[^\W\d_](?:[^\W\d_]|[ '’.\-])*$")      # letters first; letters, spaces, apostrophes, dots and hyphens after
_EMAIL = re.compile(r"^[^@\s<>\"',;:()\[\]\\]+@[A-Za-z0-9](?:[A-Za-z0-9.\-]*[A-Za-z0-9])?\.[A-Za-z]{2,}$")
SAID = {liteapi.GONE: "That room was just taken. Go back to the matrix and open the square again for today’s rooms.",
        liteapi.OVER: "Today’s searches are used up. Try again tomorrow.",
        liteapi.BUSY: "LiteAPI is busy right now. Try again in a minute.",
        liteapi.OFF: "Booking needs the LiteAPI sandbox key; this site has none (or a live one, which never books).",
        liteapi.FAILED: "LiteAPI did not answer just now. Nothing was booked. Try again in a minute.",
        liteapi.DUPLICATE: "That was already booked a moment ago."}


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
    guest_name: str
    guest_email: str
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


_HELD: dict = {}
_LOCK = threading.Lock()


def hold(family: str, prep: Prep) -> str:
    with _LOCK:
        for k in [k for k, (_, _, at) in _HELD.items() if time.monotonic() - at > HOLD]:
            del _HELD[k]
        while len(_HELD) >= HELD_MAX:
            del _HELD[next(iter(_HELD))]
        _HELD[prep.token] = (family, prep, time.monotonic())
    return prep.token


def held(family: str, token: str) -> Prep | None:
    with _LOCK:
        found = _HELD.get(token or "")
    return found[1] if found and found[0] == family and time.monotonic() - found[2] <= HOLD else None


def forget() -> None:
    with _LOCK:
        _HELD.clear()


# ---- booking -----------------------------------------------------------------------------------------------------------

def reference(family: str, token: str, i: int) -> str:
    """The idempotency key of one stay of one prebooked square: pressing Book twice sends the same one, so LiteAPI books once."""
    return hashlib.sha256(f"{family}|{token}|{i}".encode()).hexdigest()[:32]


def _stored(row) -> Done:
    return Done(row["booking_id"], row["hotel"], row["room"], row["place"], row["checkin"], row["checkout"], row["total_cents"], row["due_at_stay_cents"], bool(row["refundable"]),
                row["confirmation"], row["guest_name"], row["guest_email"], bool(row["sample"]), row["trip_id"])


def for_trip(db, trip_id: str) -> list:
    return [_stored(r) for r in familydb.rows(db, "SELECT * FROM matrix_bookings WHERE trip_id = :t ORDER BY created_at, id", t=trip_id)]


def _save(db, ref, trip_id, user_id, row: Row, booking: liteapi.Booking | None, guest: liteapi.Guest, sample: bool) -> None:
    pre = row.prebook
    id_ = ("SAMPLE-" + ref[:8].upper()) if booking is None else booking.booking_id
    hotel = row.part.name if booking is None else (booking.hotel or row.part.name)
    familydb.run(db, "INSERT INTO matrix_bookings (id, trip_id, user_id, booking_id, place, hotel, room, checkin, checkout, total_cents, due_at_stay_cents, refundable, confirmation, "
                     "guest_name, guest_email, sample, created_at) VALUES (:i, :t, :u, :b, :p, :h, :r, :a, :o, :c, :d, :f, :k, :g, :e, :s, :now)",
                 i=ref, t=trip_id, u=user_id, b=id_, p=row.place, h=hotel[:120], r=pre.room[:120], a=pre.checkin.isoformat(), o=pre.checkout.isoformat(),
                 c=(booking.cents + pre.due_at_stay_cents) if booking else row.total_cents, d=pre.due_at_stay_cents, f=1 if pre.refundable else 0,
                 k=("SAMPLE" if booking is None else booking.confirmation)[:60], g=f"{guest.first} {guest.last}", e=guest.email, s=1 if sample else 0, now=familydb.now())


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
            if not got.ok:
                return Result(got.status, tuple(done), len(prep.rows) - len(done))
            booking = got.items[0]
        with familydb.transaction(db):
            _save(db, ref, trip_id, user_id, row, booking, guest, prep.sample)
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
