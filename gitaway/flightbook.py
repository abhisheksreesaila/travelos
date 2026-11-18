"""Flights booked through LiteAPI (F-276, D-972..D-979): the second half of "Book this trip", next to `matrixbook` (the stay).

    prepare(part, family, sample)           an FPrep: the square's flight verified with LiteAPI (the price now, the fare's facts, any price change), or a sample one (no call)
    clean_travellers(values, ...)           (travellers, contact, errors): one person per seat, as their ID says, and the lead's email and phone; every rule is ours, LiteAPI books what it is sent
    save_prebook / payment / finish         the form's path: the ids saved at once, the book made once from the form's return, the passengers blanked once it is booked
    book_sample(...)                        a labelled sample flight (the showcase, the sandbox without its form, a live key off production): a row, no call
    refresh(db, tenant, row, spender)       ask LiteAPI where a PENDING_CONFIRMATION booking is now; one "tickets issued" email when it turns CONFIRMED
    quote / cancel                          the cancel quote first (refund and penalty in money), then the cancel (a pending one says pending)
    add_to_trip(session, trip_id, row)      the outbound and return flights become locked blocks on the family's trip (and Today)

Payment: a flight is only ever paid in LiteAPI's payment form (`usePaymentSdk`) and booked with its `TRANSACTION_ID`, and only from the form's return: the sandbox accepted a book for a payment
never made (D-978), so nothing but the person's return to `/plan/matrix/book/flight/return` books a flight, never the worker. The passengers (names, birth dates, passport numbers, email, phone) are
personal data: validated here, sent to LiteAPI and nobody else, kept in `matrix_flight_payments` only until the flight is booked (the lead's first name and email until the tickets email is
sent, at most 7 days: `purge`), escaped on output, never logged.
"""

import hashlib
import json
import logging
import re
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError

from gitaway import catalog, familydb, liteapi, matrixbook as mb, zones
from gitaway.countries import CODES, COUNTRIES

log = logging.getLogger("gitaway.flightbook")
SAMPLE_WORDS = "Sample flight booking: nothing is booked or charged"
QUOTE_VALID = timedelta(minutes=15)      # a cancel is only made on a quote this fresh
CHECK_AFTER = (1, 3, 10, 30, 60)          # minutes before the worker's first, second ... lookup of a booking still waiting for its tickets; five tries, then the page says it is still waiting
PAYING, BOOKING, BOOKED, EXPIRED, NEEDS_HELP = "paying", "booking", "booked", "expired", "needs_help"
NEEDS_QUOTE = "needs quote"
GENDERS = (("F", "Female"), ("M", "Male"), ("X", "Another or unspecified"))      # as on the passport or ID (LiteAPI: M, F, X)
KINDS = {0: "adult", 1: "child", 2: "infant"}
US_ZONES = {"America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles", "America/Phoenix", "America/Anchorage", "Pacific/Honolulu"}
SOON_WORDS = "Flight booking opens soon. Your flight isn't booked yet."
HAVE_WORDS = "Your flight is already booked."
OPEN_AFTER = timedelta(minutes=15)      # a flight's payment form younger than this may still be paid: a second prebook of the same token waits for it
PAID_OK = ("succeeded", "completed")      # LiteAPI's paymentStatus after a book; anything else present is not a paid flight
SAID = {liteapi.GONE: "That fare is no longer available. Go back to the matrix and open the square again for today’s flights.",
        liteapi.OVER: "Today’s booking calls are used up. Try again tomorrow.",
        liteapi.BUSY: "LiteAPI is busy right now. Try again in a minute.",
        liteapi.OFF: "Flights can only be booked while booking is open.",
        liteapi.FAILED: "LiteAPI did not answer just now. Nothing was booked or charged. Try again in a minute."}


# ---- the words about a flight ----------------------------------------------------------------------------------------------

def refund_words(refundable: bool) -> str:
    return "Refundable: you get the fare back if you cancel" if refundable else "Not refundable: cancelling returns only some taxes"


def change_words(changeable: bool) -> str:
    return "Changeable: the airline allows it, for a fee" if changeable else "Not changeable: the dates cannot be moved"


def _clock(at: datetime) -> str:
    return f"{at.hour % 12 or 12}:{at.minute:02d} {'AM' if at.hour < 12 else 'PM'}"


def day_words(at) -> str:
    return f"{at:%a}, {at:%b} {at.day}"


def seg_words(s) -> str:
    """"Fri, Dec 18 · SFO 3:50 PM → SAN 5:29 PM · ND 6278" for one flight."""
    number = f" · {s.code} {s.number}".rstrip() if s.number else ""
    return f"{day_words(s.depart)} · {s.origin} {_clock(s.depart)} → {s.destination} {_clock(s.arrive)}{' next day' if s.arrive.date() > s.depart.date() else ''}{number}"


def bags_words(v) -> tuple:
    """(what the fare carries, what costs extra and is not sold here yet), in LiteAPI's words; either may be empty."""
    inc = ", ".join(v.bags_included)
    paid = ", ".join(f"{w} {catalog.money(c)}" if c else w for w, c in v.bags_paid)
    return (f"Included: {inc}" if inc else ""), (f"Extra, not sold here yet: {paid}" if paid else "")


def facts_of(v) -> dict:
    """What is shown before paying, kept with the booking: the fare family, the bags, refundable and changeable."""
    inc, paid = bags_words(v)
    return {"fare": v.fare, "included": inc, "paid": paid, "refundable": v.refundable, "changeable": v.changeable}


def seg_dict(s) -> dict:
    return {"dir": s.direction, "o": s.origin, "t": s.destination, "dep": s.depart.isoformat(), "arr": s.arrive.isoformat(), "air": s.airline, "c": s.code, "n": s.number, "m": s.minutes}


def seg_of(d: dict) -> liteapi.Seg:
    return liteapi.Seg(d["dir"], d["o"], d["t"], datetime.fromisoformat(d["dep"]), datetime.fromisoformat(d["arr"]), d["air"], d["c"], d["n"], d.get("m", 0))


def segs_of(row) -> tuple:
    try:
        return tuple(seg_of(d) for d in json.loads(row["legs"] or "[]"))
    except (ValueError, KeyError, TypeError):
        return ()


def facts_of_row(row) -> dict:
    try:
        return json.loads(row["facts"] or "{}")
    except ValueError:
        return {}


def route_words(segs) -> str:
    out = [s for s in segs if s.direction != "INBOUND"] or list(segs)
    return f"{out[0].origin} to {out[-1].destination}" if out else ""


def airline_words(segs) -> str:
    return " + ".join(dict.fromkeys(s.airline for s in segs if s.airline))


def international(segs) -> bool:
    """Does the route leave the United States? An airport the table does not know counts as abroad: a passport is then asked for, never forgotten."""
    return any(zones.AIRPORTS.get(a) not in US_ZONES for s in segs for a in (s.origin, s.destination))


# ---- verifying the offer before anyone pays -----------------------------------------------------------------------------------

@dataclass(frozen=True)
class FPrep:
    status: str                        # liteapi.OK, or why not
    sample: bool = False               # no call was made and none will be: a labelled sample flight
    verified: liteapi.FlightVerified | None = None
    offer_id: str = ""
    shown_cents: int = 0               # what the square said
    soon: bool = False                 # a live key with flights switched off (D-980): the flight is not booked here yet and the checkout says so
    have: dict | None = None           # the flight of this square is already booked (a row of matrix_flights): the stay alone is booked now

    @property
    def real(self) -> bool:
        """Is this flight booked through LiteAPI by this checkout?"""
        return not self.sample and not self.soon and self.have is None

    @property
    def ok(self) -> bool:
        return self.status == liteapi.OK

    @property
    def cents(self) -> int:
        return self.verified.cents if self.verified else self.shown_cents

    @property
    def changed(self) -> bool:
        """The price moved since the square (LiteAPI's flag, or more than a dollar's rounding): the person is told before paying."""
        return bool(self.verified) and (self.verified.price_changed or abs(self.verified.cents - self.shown_cents) > mb.TOLERANCE_CENTS)

    @property
    def segments(self) -> tuple:
        return self.verified.segments if self.verified else ()


def prepare(part, family: str = "", sample: bool = False) -> FPrep:
    """Verify the square's flight with LiteAPI (a flight with no offer id, or any sample, is a labelled sample: nothing is asked of LiteAPI)."""
    if part is None:
        return FPrep(liteapi.GONE)
    if sample or not part.offer_id:
        return FPrep(liteapi.OK, True, None, "", part.cents)
    if liteapi.mode() == "live" and not liteapi.flights_live():
        return FPrep(liteapi.OK, False, None, part.offer_id, part.cents, soon=True)
    got = liteapi.flight_verify(part.offer_id, family)
    if not got.ok:
        return FPrep(got.status)
    return FPrep(liteapi.OK, False, got.items[0], part.offer_id, part.cents)


# ---- the travellers form ------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Traveller:
    kind: int                          # 0 adult, 1 child, 2 infant (LiteAPI's passengerType)
    first: str
    last: str
    birthday: date
    gender: str
    nationality: str
    doc: tuple = ()                    # (number, issuing country, expiry date) for an international route


@dataclass(frozen=True)
class Contact:
    first: str
    last: str
    email: str
    cc: str                            # country calling code, digits
    phone: str                         # the number, digits


def seats(adults: int, kid_ages) -> tuple:
    """One (kind, searched age) a seat, adults first: the people the flight was priced for. Kids under 2 fly as infants (`liteapi.flights`)."""
    return tuple((0, None) for _ in range(adults)) + tuple((2 if a < 2 else 1, a) for a in kid_ages)


def field(i: int, name: str) -> str:
    """The form's name for traveller `i`'s `name`: the lead's names are plain `first` and `last` (the stay's guest), the rest `t<i>_<name>`."""
    return name if i == 0 and name in ("first", "last") else f"t{i}_{name}"


def years(born: date, on: date) -> int:
    return on.year - born.year - ((on.month, on.day) < (born.month, born.day))


_DOC = re.compile(r"^[A-Z0-9]{5,12}\Z")
_CC = re.compile(r"^[0-9]{1,3}\Z")
_NUMBER = re.compile(r"^[0-9]{4,14}\Z")


def _date(v) -> date | None:
    try:
        return date.fromisoformat(str(v).strip()) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(v).strip()) else None
    except ValueError:
        return None


def _title(kind: int, gender: str) -> str:
    return {"F": "MS", "M": "MR"}.get(gender, "") if kind == 0 else ""


def clean_travellers(values, adults: int, kid_ages, depart: date, back: date | None, abroad: bool, today: date | None = None):
    """(travellers, contact, {field name: problem}) from the form. Every traveller: first and last name as on their ID (letters, spaces, apostrophes, dots and hyphens), birth date, gender (M, F, X)
    and nationality (a listed country); a child's or infant's birth date must make them the age the flight was priced for on the day they fly (an infant also on the way back); an adult is 18 or over; a
    passport number, the country that issued it and its expiry (after the trip) only for an international route. The lead traveller's email and mobile number (country code and number)."""
    today = today or catalog.today()
    get = lambda n: mb._tidy(values.get(n, ""))      # noqa: E731
    errors, people = {}, []
    for i, (kind, age) in enumerate(seats(adults, kid_ages)):
        who = "the lead traveller" if i == 0 else f"traveller {i + 1}"
        first, last = get(field(i, "first")), get(field(i, "last"))
        for f, v, word in (("first", first, "first name"), ("last", last, "last name")):
            if not v:
                errors[field(i, f)] = f"Add {who}’s {word} as it is on their ID."
            elif len(v) > mb.NAME_MAX or not mb._NAME.match(v):
                errors[field(i, f)] = f"The {word} is letters only, up to {mb.NAME_MAX}."
        born = _date(get(field(i, "dob")))
        if born is None:
            errors[field(i, "dob")] = f"Add {who}’s birth date."
        elif born > today or years(born, today) > 120:
            errors[field(i, "dob")] = "That birth date does not look right."
        elif kind == 0 and years(born, depart) < 18:
            errors[field(i, "dob")] = "An adult is 18 or over on the day of the flight. A younger traveller is added as a kid when you search."
        elif kind != 0 and years(born, depart) != age:
            errors[field(i, "dob")] = f"This kid was searched as {age}: the birth date must make them {age} on {depart:%b} {depart.day}."
        elif kind == 2 and back and years(born, back) >= 2:
            errors[field(i, "dob")] = "This child turns 2 before the flight home, which needs a seat of their own. Search again with their age."
        gender, nation = get(field(i, "sex")), get(field(i, "nat")).upper()
        if gender not in {g for g, _ in GENDERS}:
            errors[field(i, "sex")] = "Choose the gender as on the ID: F, M or X."
        if nation not in CODES:
            errors[field(i, "nat")] = "Choose the nationality from the list."
        doc = ()
        if abroad:
            number, issuer, expiry = get(field(i, "docno")).replace(" ", "").upper(), get(field(i, "docc")).upper(), _date(get(field(i, "docx")))
            if not _DOC.match(number):
                errors[field(i, "docno")] = "Add the passport number: 5 to 12 letters and digits."
            if issuer not in CODES:
                errors[field(i, "docc")] = "Choose the country that issued it."
            if expiry is None or expiry <= (back or depart) or expiry > today + timedelta(days=365 * 25):
                errors[field(i, "docx")] = "The passport must still be valid after the trip: add its expiry date."
            doc = (number, issuer, expiry)
        if not any(k in errors for k in (field(i, n) for n in ("first", "last", "dob", "sex", "nat", "docno", "docc", "docx"))):
            people.append(Traveller(kind, first, last, born, gender, nation, doc))
    email, cc, number = get("email"), get("cc").lstrip("+") or "1", re.sub(r"[ ().\-]", "", get("phone"))
    if not email:
        errors["email"] = "Add an email for the tickets."
    elif len(email) > mb.EMAIL_MAX or not mb._EMAIL.match(email) or ".." in email:
        errors["email"] = "That does not look like an email address."
    if not _CC.match(cc):
        errors["cc"] = "The country code is 1 to 3 digits."
    if not _NUMBER.match(number):
        errors["phone"] = "Add a mobile number the airline can reach: 4 to 14 digits."
    contact = Contact(people[0].first, people[0].last, email, cc, number) if len(people) == len(seats(adults, kid_ages)) and not errors else None
    return (tuple(people) if not errors else (), contact, errors)


def contact_body(c: Contact) -> dict:
    return {"firstName": c.first, "lastName": c.last, "email": c.email, "phoneCountryCode": c.cc, "phoneNumber": c.phone}


def passengers_body(people) -> list:
    out = []
    for p in people:
        one = {"passengerType": p.kind, **({"title": _title(p.kind, p.gender)} if _title(p.kind, p.gender) else {}), "firstName": p.first, "lastName": p.last, "birthday": p.birthday.isoformat(),
               "gender": p.gender, "nationality": p.nationality}
        if p.doc:
            one.update({"documentType": "passport", "documentNumber": p.doc[0], "documentIssueCountry": p.doc[1], "documentExpiry": p.doc[2].isoformat()})
        out.append(one)
    return out


def dump(people, contact: Contact) -> str:
    return json.dumps({"c": asdict(contact), "p": [{**asdict(p), "birthday": p.birthday.isoformat(), "doc": [p.doc[0], p.doc[1], p.doc[2].isoformat()] if p.doc else []} for p in people]})


def load(blob: str):
    """(travellers, contact) from `dump`, or (None, None) when the passengers are gone (booked, or past the 7 days)."""
    try:
        d = json.loads(blob)
        people = tuple(Traveller(p["kind"], p["first"], p["last"], date.fromisoformat(p["birthday"]), p["gender"], p["nationality"],
                                 (p["doc"][0], p["doc"][1], date.fromisoformat(p["doc"][2])) if p["doc"] else ()) for p in d["p"])
        return people, Contact(**d["c"])
    except (ValueError, KeyError, TypeError):
        return None, None


# ---- the prebook, saved at once; the book, made once from the form's return --------------------------------------------------

def reference(family: str, token: str) -> str:
    """The id of a flight booking row: this family's token, hashed: a second return finds the first row."""
    return hashlib.sha256(f"{family}|{token}|flight".encode()).hexdigest()[:32]


def payment(db, token: str) -> dict | None:
    return familydb.row(db, "SELECT * FROM matrix_flight_payments WHERE id = :i", i=token)


def payment_for_stay(db, stay_token: str) -> dict | None:
    return familydb.row(db, "SELECT * FROM matrix_flight_payments WHERE stay_token = :s ORDER BY created_at DESC", s=stay_token)


def booked_for_square(db, back_href: str) -> dict | None:
    """The flight already booked through LiteAPI from this square (its address is what the prebook kept), not cancelled: a second Book of the square books the stay alone."""
    if not back_href:
        return None
    row = familydb.row(db, "SELECT f.* FROM matrix_flights f JOIN matrix_flight_payments p ON p.booking_id = f.booking_id WHERE p.back_href = :h AND f.sample = 0 "
                           "AND f.status NOT IN ('CANCELLED', 'CANCELLED_WITH_CHARGES') AND NOT EXISTS (SELECT 1 FROM matrix_cancels c WHERE c.booking_id = f.booking_id) ORDER BY f.created_at DESC", h=back_href)
    return row


def row_for(db, booking_id: str) -> dict | None:
    return familydb.row(db, "SELECT * FROM matrix_flights WHERE booking_id = :b", b=booking_id)


def row_for_ref(db, ref: str) -> dict | None:
    """The booking whose short reference (what a trip's flight carries as its confirmation) is `ref`."""
    return familydb.row(db, "SELECT * FROM matrix_flights WHERE ref = :r OR booking_id = :r", r=ref) if ref else None


def form_open(db, token: str) -> bool:
    """Is a payment form for this token open (less than OPEN_AFTER old), or its flight booked or being booked? A second prebook then waits: the first form may be paid, and its return must
    still find its own prebook (never replaced by another transaction)."""
    old = familydb.row(db, "SELECT status, updated_at FROM matrix_flight_payments WHERE id = :i", i=token)
    if not old:
        return False
    if old["status"] != PAYING:
        return True
    try:
        return datetime.fromisoformat(familydb.now()) - datetime.fromisoformat(old["updated_at"]) < OPEN_AFTER
    except (TypeError, ValueError):
        return False


def save_prebook(db, token: str, user_id: str, fp: FPrep, pre: liteapi.FlightPrebook, people, contact: Contact, trip_id: str, stay_token: str, back_href: str, party: str) -> bool:
    """Save the prebook the moment it answers (LiteAPI cannot give its ids back): the ids, the amount, the flights and the facts shown before paying, and the passengers LiteAPI's booking needs,
kept only until it is booked. The form's `secretKey` is not saved. A form under OPEN_AFTER old, or a booked one, is never replaced (False: the caller sends the person to the return page). An older
    unbooked form is set aside under its own id, passengers blanked, ids kept: it may have been paid, and the captain matches it on /admin."""
    purge(db)
    v = fp.verified
    with familydb.transaction(db):
        old = familydb.row(db, "SELECT status, updated_at FROM matrix_flight_payments WHERE id = :i", i=token)
        if old and old["status"] != PAYING:
            return False
        if old and datetime.fromisoformat(familydb.now()) - datetime.fromisoformat(old["updated_at"]) < OPEN_AFTER:
            return False
        if old:
            familydb.run(db, "UPDATE matrix_flight_payments SET id = :n, travellers = '' WHERE id = :i", n=f"{token}~{familydb.now()}", i=token)
        familydb.run(db, "INSERT INTO matrix_flight_payments (id, user_id, trip_id, status, prebook_id, transaction_id, charge_cents, airline, route, legs, facts, party, stay_token, back_href, "
                         "travellers, contact, created_at, updated_at) VALUES (:i, :u, :t, 'paying', :pb, :tx, :c, :a, :r, :l, :f, :p, :s, :b, :tr, :ct, :now, :now)",
                     i=token, u=user_id, t=trip_id, pb=pre.prebook_id, tx=pre.transaction_id, c=pre.cents, a=airline_words(v.segments)[:120], r=route_words(v.segments),
                     l=json.dumps([seg_dict(s) for s in v.segments]), f=json.dumps(facts_of(v)), p=party[:80], s=stay_token, b=back_href[:400], tr=dump(people, contact),
                     ct=json.dumps({"first": contact.first, "email": contact.email}), now=familydb.now())
    return True


@dataclass(frozen=True)
class FResult:
    status: str                  # liteapi.OK, or why not (liteapi.NOT_PAID, GONE, FAILED, BUSY, OVER); BOOKING: another call is making this booking now
    row: dict | None = None      # the matrix_flights row

    @property
    def ok(self) -> bool:
        return self.status == liteapi.OK and self.row is not None


def _set(db, token: str, status: str, where: str = "") -> int:
    with familydb.transaction(db):
        return familydb.run(db, f"UPDATE matrix_flight_payments SET status = :s, updated_at = :now WHERE id = :i {where}", s=status, i=token, now=familydb.now())


def _blank(db, token: str, keep_contact: bool = True) -> None:
    with familydb.transaction(db):
        familydb.run(db, "UPDATE matrix_flight_payments SET travellers = ''" + ("" if keep_contact else ", contact = ''") + " WHERE id = :i", i=token)


def finish(db, family: str, token: str, user_id: str, budget: str = "") -> FResult:
    """After the payment form: book the flight with the transaction id saved at prebook, once. A second call (a reload of the return page) finds the stored booking; only one call makes
    the booking at a time. LiteAPI says NOT_PAID (nothing happened: the row waits), or GONE (the prebook is gone: marked expired, the passengers dropped); a call that failed without an answer
    may have booked, so the row is kept for the captain (`needs_help`) and the person is told not to pay again. Not made by the worker (D-978). The passengers are blanked once it is booked."""
    pay = payment(db, token)
    if not pay or pay["user_id"] != user_id:
        return FResult(liteapi.GONE)
    ref = reference(family, token)
    mine = familydb.row(db, "SELECT * FROM matrix_flights WHERE id = :i", i=ref)
    if mine:
        return FResult(liteapi.OK, mine)
    if _set(db, token, BOOKING, "AND status = 'paying'") != 1:      # one caller books: another return of the same form is told it is being made
        return FResult(BOOKING if payment(db, token)["status"] == BOOKING else liteapi.FAILED)
    people, lead = load(pay["travellers"])
    got = liteapi.flight_book(pay["prebook_id"], pay["transaction_id"], budget or family)
    if got.status in (liteapi.NOT_PAID, liteapi.BUSY, liteapi.OVER):      # nothing was booked: the row goes back to waiting
        _set(db, token, PAYING)
        return FResult(got.status)
    if got.status == liteapi.GONE:
        _set(db, token, EXPIRED)
        _blank(db, token, keep_contact=False)
        return FResult(liteapi.GONE)
    if not got.ok:      # no answer, or one we cannot read: the booking may exist
        _set(db, token, NEEDS_HELP)
        log.warning("flight book of %s needs help (%s)", token[:6], got.status)
        return FResult(liteapi.FAILED)
    b = got.items[0]
    if b.payment_status and b.payment_status not in PAID_OK:      # LiteAPI says the payment is not a paid one: not shown as booked, kept for the captain (D-980)
        _set(db, token, NEEDS_HELP)
        with familydb.transaction(db):
            familydb.run(db, "UPDATE matrix_flight_payments SET booking_id = :b WHERE id = :i", b=b.booking_id, i=token)
        log.warning("flight book of %s answered payment status %s: needs help", token[:6], b.payment_status[:20])
        return FResult(liteapi.FAILED)
    try:
        with familydb.transaction(db):
            familydb.run(db, "INSERT INTO matrix_flights (id, trip_id, user_id, booking_id, ref, pnr, locators, status, payment_status, total_cents, airline, legs, facts, party, ticket_limit, sample, "
                             "checks, next_check_at, created_at) VALUES (:i, :t, :u, :b, :r, :pnr, :loc, :st, :ps, :c, :a, :l, :f, :p, :tl, 0, 0, :nx, :now)",
                         i=ref, t=pay["trip_id"], u=user_id, b=b.booking_id, r=b.ref, pnr=b.pnr, loc=json.dumps(b.airline_pnrs), st=b.status, ps=b.payment_status, c=b.cents,
                         a=pay["airline"], l=json.dumps([seg_dict(s) for s in (b.segments or segs_of(pay))]), f=pay["facts"], p=pay["party"], tl=b.ticket_limit.isoformat() if b.ticket_limit else "",
                         nx=(datetime.fromisoformat(familydb.now()) + timedelta(minutes=CHECK_AFTER[0])).isoformat(timespec="seconds"), now=familydb.now())
    except IntegrityError:      # a second return stored it first
        pass
    row = familydb.row(db, "SELECT * FROM matrix_flights WHERE id = :i", i=ref)
    from gitaway import bookingmail      # the lead's address is still on the row: the booked email goes before the passengers are blanked
    if lead:
        bookingmail.flight_booked(db, row, {"first": lead.first, "email": lead.email}, pay, family)
    with familydb.transaction(db):
        familydb.run(db, "UPDATE matrix_flight_payments SET status = 'booked', booking_id = :b, travellers = '', updated_at = :now WHERE id = :i", b=b.booking_id, i=token, now=familydb.now())
    return FResult(liteapi.OK, row)


def book_sample(db, family: str, token: str, trip_id: str, user_id: str, fp: FPrep, segs, party: str) -> dict:
    """A labelled sample flight: a row marked sample, no call, nothing charged. Pressing Book twice finds the first row."""
    ref = reference(family, token)
    try:
        with familydb.transaction(db):
            familydb.run(db, "INSERT INTO matrix_flights (id, trip_id, user_id, booking_id, ref, pnr, locators, status, payment_status, total_cents, airline, legs, facts, party, ticket_limit, sample, "
                             "checks, created_at) VALUES (:i, :t, :u, :b, :r, '', '[]', 'CONFIRMED', 'sample', :c, :a, :l, '{}', :p, '', 1, 0, :now)",
                         i=ref, t=trip_id, u=user_id, b="SAMPLE-" + ref[:8].upper(), r="SAMPLE-" + ref[:8].upper(), c=fp.cents, a=airline_words(segs)[:120] or "Sample airline",
                         l=json.dumps([seg_dict(s) for s in segs]), p=party[:80], now=familydb.now())
    except IntegrityError:
        pass
    return familydb.row(db, "SELECT * FROM matrix_flights WHERE id = :i", i=ref)


_CLOCK = re.compile(r"^(\d{1,2}):(\d{2}) ([AP])M\Z")
_LEG = re.compile(r"^(?:[A-Z][a-z]{2}, [A-Z][a-z]{2} \d+ · )?(?P<o>[A-Z]{3}) (?P<dt>\d{1,2}:\d{2} [AP]M) → (?P<d>[A-Z]{3}) (?P<at>\d{1,2}:\d{2} [AP]M)(?P<next> next day)?")


def _at(day: date, clock: str) -> datetime:
    m = _CLOCK.match(clock)
    h = int(m[1]) % 12 + (12 if m[3] == "P" else 0)
    return datetime(day.year, day.month, day.day, h, int(m[2]))


def sample_segments(part, depart: date, back: date | None) -> tuple:
    """The sample flight's legs, read from the square's own words ("Sat, Dec 12 · SFO 8:05 AM → SAN 9:32 AM · Nonstop") and the window's dates: no number is made up."""
    out = []
    for direction, words, day in (("OUTBOUND", part.out, depart), ("INBOUND", part.back, back)):
        m = _LEG.match(words or "")
        if not m or day is None:
            continue
        dep, arr = _at(day, m["dt"]), _at(day, m["at"])
        arr = arr + timedelta(days=1) if m["next"] or arr < dep else arr
        out.append(liteapi.Seg(direction, m["o"], m["d"], dep, arr, part.airline, "", "", int((arr - dep).total_seconds() // 60)))
    return tuple(out)


# ---- after booking: the status, the tickets -----------------------------------------------------------------------------------

def status_words(row) -> str:
    """What the booking's status means, honestly: LiteAPI's PENDING_CONFIRMATION is not a ticket yet."""
    if row["sample"]:
        return SAMPLE_WORDS
    return {"PENDING_CONFIRMATION": "Waiting for the airline to confirm your tickets", "CONFIRMED": "Tickets issued: the airline has confirmed", "CANCELLED": "Cancelled",
            "CANCELLED_WITH_CHARGES": "Cancelled"}.get(row["status"], "Not confirmed: " + row["status"].replace("_", " ").lower())


def locators(row) -> tuple:
    try:
        return tuple((a, p) for a, p in json.loads(row["locators"] or "[]"))
    except (ValueError, TypeError):
        return ()


def due(db, now) -> list:
    """The bookings the worker should ask LiteAPI about now: still waiting for their tickets (five tries at growing gaps), or cancelled with LiteAPI's answer pending."""
    at = now.isoformat(timespec="seconds")
    waiting = familydb.rows(db, "SELECT * FROM matrix_flights WHERE sample = 0 AND status = 'PENDING_CONFIRMATION' AND COALESCE(checks, 0) < :n AND (next_check_at = '' OR next_check_at <= :t)", n=len(CHECK_AFTER), t=at)
    pending = familydb.rows(db, "SELECT f.* FROM matrix_flights f JOIN matrix_cancels c ON c.booking_id = f.booking_id WHERE f.sample = 0 AND c.status = 'PENDING' AND COALESCE(f.checks, 0) < :n "
                                "AND (COALESCE(f.next_check_at, '') = '' OR f.next_check_at <= :t)", n=len(CHECK_AFTER), t=at)
    return waiting + [p for p in pending if p["booking_id"] not in {w["booking_id"] for w in waiting}]


def _cancel_pending(db, booking_id: str) -> bool:
    return familydb.row(db, "SELECT 1 AS x FROM matrix_cancels WHERE booking_id = :b AND status = 'PENDING'", b=booking_id) is not None


def refresh(db, family: str, row: dict, spender: str = "", now=None) -> dict:
    """Ask LiteAPI where this booking is now and keep the answer: status, the airline's locators, the tickets. Turning CONFIRMED sends the one "tickets issued" email. A failed lookup counts
    as a try (five, at growing gaps) and changes nothing. Returns the row as it is after."""
    now = now or liteapi.now()
    spender = spender or family
    got = liteapi.flight_booking(row["booking_id"], spender)
    if got.status in (liteapi.BUSY, liteapi.OVER):
        with familydb.transaction(db):
            familydb.run(db, "UPDATE matrix_flights SET next_check_at = :t WHERE booking_id = :b", b=row["booking_id"], t=(now + timedelta(minutes=5)).isoformat(timespec="seconds"))
        return row
    n = (row["checks"] or 0) + 1
    wait = CHECK_AFTER[min(n, len(CHECK_AFTER) - 1)]
    if not got.ok:
        with familydb.transaction(db):
            familydb.run(db, "UPDATE matrix_flights SET checks = :n, next_check_at = :t WHERE booking_id = :b", n=n, b=row["booking_id"], t=(now + timedelta(minutes=wait)).isoformat(timespec="seconds"))
        return familydb.row(db, "SELECT * FROM matrix_flights WHERE booking_id = :b", b=row["booking_id"])
    b = got.items[0]
    with familydb.transaction(db):
        familydb.run(db, "UPDATE matrix_flights SET status = :s, payment_status = :ps, pnr = :pnr, locators = :loc, ticket_limit = :tl, checks = :n, next_check_at = :t WHERE booking_id = :b",
                     s=b.status, ps=b.payment_status, pnr=b.pnr or row["pnr"], loc=json.dumps(b.airline_pnrs), tl=b.ticket_limit.isoformat() if b.ticket_limit else row["ticket_limit"],
                     n=n, t=(now + timedelta(minutes=wait)).isoformat(timespec="seconds") if b.pending or _cancel_pending(db, row["booking_id"]) else "", b=row["booking_id"])
        if b.status in ("CANCELLED", "CANCELLED_WITH_CHARGES"):      # a cancel LiteAPI had only accepted is done: say so with the amounts quoted
            familydb.run(db, "UPDATE matrix_cancels SET status = :s WHERE booking_id = :b AND status = 'PENDING'", s=b.status, b=row["booking_id"])
    fresh = familydb.row(db, "SELECT * FROM matrix_flights WHERE booking_id = :b", b=row["booking_id"])
    if b.confirmed and not row["sample"]:
        from gitaway import bookingmail
        bookingmail.flight_tickets(db, fresh, family)
    return fresh


# ---- cancelling ----------------------------------------------------------------------------------------------------------------

def quote(db, family: str, booking_id: str, user_id: str) -> tuple:
    """What cancelling would give back and cost, from LiteAPI, kept so the cancel that follows is made on it: (status, liteapi.FlightQuote | None). Nothing is cancelled."""
    row = familydb.row(db, "SELECT * FROM matrix_flights WHERE booking_id = :b AND sample = 0", b=booking_id)
    if not row:
        return liteapi.GONE, None
    got = liteapi.flight_cancel_quote(booking_id, family)
    if not got.ok:
        return got.status, None
    q = got.items[0]
    with familydb.transaction(db):
        familydb.run(db, "UPDATE matrix_flights SET quote_at = :t, quote_refund_cents = :r, quote_fee_cents = :f WHERE booking_id = :b", t=familydb.now(), r=q.refund_cents, f=q.penalty_cents, b=booking_id)
    return liteapi.OK, q


def quoted(row) -> bool:
    """Was a cancel quote shown for this booking in the last QUOTE_VALID?"""
    try:
        return bool(row["quote_at"]) and datetime.fromisoformat(familydb.now()) - datetime.fromisoformat(row["quote_at"]) <= QUOTE_VALID
    except ValueError:
        return False


def cancel(db, family: str, booking_id: str, user_id: str) -> tuple:
    """Cancel a flight booked through LiteAPI: (status, liteapi.Cancelled | None). Only after a fresh quote (NEEDS_QUOTE otherwise: the person confirms what they were shown). Cancelling again
    answers what was found the first time and asks LiteAPI nothing. A cancel LiteAPI accepted and has not finished is liteapi.PENDING with the quoted amounts."""
    row = familydb.row(db, "SELECT * FROM matrix_flights WHERE booking_id = :b AND sample = 0", b=booking_id)
    if not row:
        return liteapi.GONE, None
    done = familydb.row(db, "SELECT * FROM matrix_cancels WHERE booking_id = :b", b=booking_id)
    if done:
        return (liteapi.PENDING if done["status"] == "PENDING" else liteapi.OK), liteapi.Cancelled(booking_id, done["status"], done["refund_cents"], done["fee_cents"], liteapi.now())
    if not quoted(row):
        return NEEDS_QUOTE, None
    got = liteapi.flight_cancel(booking_id, family)
    if got.status == liteapi.PENDING:
        c = liteapi.Cancelled(booking_id, "PENDING", row["quote_refund_cents"], row["quote_fee_cents"], liteapi.now())
    elif got.ok:
        c = got.items[0]
    else:
        return got.status, None
    with familydb.transaction(db):
        familydb.run(db, "INSERT OR IGNORE INTO matrix_cancels (booking_id, user_id, status, refund_cents, fee_cents, cancelled_at) VALUES (:b, :u, :s, :r, :f, :now)",
                     b=booking_id, u=user_id, s=c.status, r=c.refund_cents, f=c.fee_cents, now=familydb.now())
        if c.status != "PENDING":
            familydb.run(db, "UPDATE matrix_flights SET status = :s WHERE booking_id = :b", s=c.status, b=booking_id)
        else:      # LiteAPI has not finished: the worker follows it at the same capped gaps, five tries counted from now
            familydb.run(db, "UPDATE matrix_flights SET checks = 0, next_check_at = '' WHERE booking_id = :b", b=booking_id)
    return (liteapi.PENDING if c.status == "PENDING" else liteapi.OK), c


def cancelled(db, booking_id: str) -> dict | None:
    return mb.cancelled(db, booking_id)


# ---- the family's trip -----------------------------------------------------------------------------------------------------

def add_to_trip(session, trip_id: str, row: dict) -> None:
    """Put the booked flights on the family's trip: each flight of the booking is a leg, so the calendar locks the outbound and the return, they open the booking, and Today shows them on
    their airports' own clocks. Pressing Book again, or the return page twice, adds nothing twice (a leg carries the booking's reference as its confirmation)."""
    from gitaway import importer, tripimport as ti
    plan = importer.plan_of(session, trip_id) if trip_id else None
    ref = row["ref"] or row["booking_id"]
    if plan is None or any(leg.confirmation == ref for leg in plan.legs):
        return
    where = "GitAway sample" if row["sample"] else "LiteAPI" if mb.mode() == mb.LIVE else "LiteAPI sandbox"
    new = tuple(ti.Leg(s.airline or "Flight", s.number, s.origin, s.destination, s.depart, s.arrive, ref, "", where) for s in segs_of(row))
    if not new:
        return
    legs = tuple(sorted(plan.legs + new, key=lambda leg: leg.depart))
    importer.save(session, replace(plan, legs=legs, booked_on=where if plan.booked_on in ("", "elsewhere") else plan.booked_on), replace=trip_id)


def mark_cancelled(session, trip_id: str, ref: str) -> None:
    """The cancelled flight stays on the trip but says so, so the plan does not count a flight that is gone."""
    from gitaway import importer
    plan = importer.plan_of(session, trip_id) if trip_id else None
    if plan is None or not any(leg.confirmation == ref and not leg.booked_on.startswith("Cancelled") for leg in plan.legs):
        return
    legs = tuple(replace(leg, booked_on="Cancelled on " + (leg.booked_on.replace("Booked on ", "") or "LiteAPI")) if leg.confirmation == ref else leg for leg in plan.legs)
    importer.save(session, replace(plan, legs=legs), replace=trip_id)


def purge(db) -> None:
    """Drop what no longer needs keeping: an expired prebook after PURGE_GUEST days (it may have been paid: it stays on /admin until then, passengers already blanked), every passenger and contact after PURGE_GUEST days (the ids and amounts stay: they are the record)."""
    cut = (datetime.now(timezone.utc) - timedelta(days=mb.PURGE_GUEST)).isoformat(timespec="seconds")
    with familydb.transaction(db):
        familydb.run(db, "DELETE FROM matrix_flight_payments WHERE status = 'expired' AND created_at < :t", t=cut)
        familydb.run(db, "UPDATE matrix_flight_payments SET travellers = '', contact = '' WHERE created_at < :t AND (travellers != '' OR contact != '')", t=cut)
        familydb.run(db, "UPDATE matrix_flight_payments SET travellers = '' WHERE status = 'paying' AND travellers != '' AND created_at < :t",      # a form left open for a day: the passengers go, the ids and the amount stay (like the stay's PURGE_UNPAID)
                     t=(datetime.now(timezone.utc) - timedelta(days=mb.PURGE_UNPAID)).isoformat(timespec="seconds"))


def to_match(db, now=None) -> list:
    """Flight payments the captain may need to match in LiteAPI's dashboard (D-980): a form opened and left over OPEN_AFTER ("maybe paid"), a paid return whose fare was gone (`expired`), a book that may have gone through (`needs_help`) or was
    started and never finished (`booking`), from the last 7 days. Only the ids and the date: never a traveller."""
    now = now or datetime.now(timezone.utc)
    rows = familydb.rows(db, "SELECT id, status, transaction_id, charge_cents, created_at, updated_at FROM matrix_flight_payments WHERE status IN ('paying', 'booking', 'needs_help', 'expired') AND created_at > :w ORDER BY created_at",
                         w=(now - timedelta(days=mb.PURGE_GUEST)).isoformat(timespec="seconds"))
    cut = (now - OPEN_AFTER).isoformat(timespec="seconds")
    return [r for r in rows if r["updated_at"] < cut]


def stuck(db, before: str) -> list:
    """Flight payments whose book call was started (`booking`) or may have gone through (`needs_help`) and is not settled since before `before`: counted on /admin. The worker does not book a flight
    left `paying` (D-978): a form that was only opened is not a payment, and nothing here can tell them apart."""
    return familydb.rows(db, "SELECT * FROM matrix_flight_payments WHERE status IN ('booking', 'needs_help') AND updated_at < :t", t=before)


def country_options() -> tuple:
    return COUNTRIES
