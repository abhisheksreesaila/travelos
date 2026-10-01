"""The trip calendar model (F-019): booked blocks, activities, clashes, notes.

Public functions take the signed-in person's session, like gitaway.session, and read and write the family database
(gitaway.familydb). Callers never see which store is underneath: activities, notes and friends belong to the trip the person
has open, so every member of the family sees and edits the same calendar.

Booked blocks (outbound flight, check in, check out, return flight) are derived from the booking and the catalog each
time and are never stored. Activities and notes are rows (tables activities, notes, cal_state):

    activity = Activity(id "a3", day index, start minute, end minute, title, kind, by: the friend who added it, "" for family)
    note     = Note(id "n4", text, act: activity id or None, by)

`cal_state` holds, per trip, the last id number handed out and whether the scripted live add (F-020) has happened. The scope
"long" (?demo=long) is a second, separate calendar on the same trip. Times are minutes after midnight. Ids are stable;
adding with an id that already exists is a no-op (a refresh). Every change is one transaction on its own rows (see familydb).
"""

import re
from dataclasses import dataclass, replace
from datetime import date, timedelta
from urllib.parse import parse_qs

from fh_saas.utils_sql import delete_record, insert_only, update_record

from gitaway import catalog, context, familydb, rides as ride_model, session as ses, tripimport

LONG = "long"  # the hidden ?demo=long fixture: a 20-day trip that crosses into November
LONG_RETURN = date(2026, 11, 4)
GRID_END = 22 * 60
DEFAULT_START = 7 * 60
SNAP = 15
MIN_LEN = 30
CHECK_IN = 15 * 60
CHECK_OUT = 11 * 60
STAY_LEN = 90
MAX_TITLE = 40
MAX_NOTE = 140
LIVE_FRIEND = "Mom"
LIVE_TITLE = "Travel Town steam trains"
LIVE_DAY = 2  # Sunday on the sample trip
LIVE_START = 10 * 60
LIVE_LEN = 150
LIVE_NOTE = "Added Travel Town on Sunday. The little one will love the trains."

# kind -> (label, tint token name)
KINDS = {"fun": ("Fun", "bubble"), "food": ("Food", "sun"), "outdoors": ("Outdoors", "mint"),
         "culture": ("Culture", "grape"), "travel": ("Travel", "sky")}

_ID = re.compile(r"^[an]\d{1,4}$")
_TIME = re.compile(r"^(\d{1,2}):(\d{2})$")


class CalendarError(ValueError):
    """A change the calendar refuses; the message is fit to show the traveler."""


@dataclass(frozen=True)
class Block:
    id: str
    day: int
    start: int
    end: int
    title: str
    kind: str
    locked: bool = False
    icon: str = ""
    tag: str = ""   # "Booked elsewhere · Expedia" on an imported trip's blocks (F-042); such a block opens its booking detail


@dataclass(frozen=True)
class Activity:
    id: str
    day: int
    start: int
    end: int
    title: str
    kind: str
    by: str = ""  # the friend who added it; "" is the traveler


@dataclass(frozen=True)
class Note:
    id: str
    text: str
    act: str | None = None
    by: str = ""


# ---- trip and formatting -------------------------------------------------------------------------------------------

def trip_of(booking=None):
    """The trip a booking was made for (the sample trip when it holds none, as older bookings do). An imported trip has its real dates and party."""
    if booking and booking.get("imported"):
        return tripimport.trip_search(_plan(booking))
    if not booking or not booking.get("trip"):
        return catalog.SAMPLE_TRIP
    p = {k: v[0] for k, v in parse_qs(booking["trip"]).items()}
    return catalog.trip_from_url(p.get("d"), p.get("r"), p.get("a"), p.get("k"))


def trip(demo="", booking=None):
    """The trip on the calendar: the booking's (default: the sample trip), or the 20-day fixture of ?demo=long."""
    t = trip_of(booking)
    if demo != LONG:
        return t
    return replace(t, return_=LONG_RETURN if t.depart < LONG_RETURN else t.depart + timedelta(days=19))  # always after departure


def days(t):
    return [t.depart + timedelta(days=i) for i in range((t.return_ - t.depart).days + 1)]


def range_label(a, b):
    """'Oct 16 – 20' inside a month, 'Oct 16 – Nov 4' across one."""
    end = f"{b.day}" if (a.year, a.month) == (b.year, b.month) else f"{b.strftime('%b')} {b.day}"
    return f"{a.strftime('%b')} {a.day} – {end}"


def fmt_time(m):
    h, mm = divmod(m, 60)
    return f"{h % 12 or 12}:{mm:02d} {'AM' if h < 12 else 'PM'}"


def hhmm(m):
    return f"{m // 60:02d}:{m % 60:02d}"


def weather_for(i):
    """Sample weather for day `i`; the five sample days repeat on a longer trip."""
    return context.WEATHER[i % len(context.WEATHER)]


# ---- booked blocks -------------------------------------------------------------------------------------------------

def _plan(b):
    """The tripimport.Plan of an imported booking `b` (its stored template), or None for a demo booking."""
    return tripimport.from_doc(b["imported"]) if b and b.get("imported") else None


plan_of = _plan  # public name for the screens


def is_imported(b) -> bool:
    return bool(b and b.get("imported"))


def _lane(b, key, kind):
    """The offer a booking `b` holds for one lane, or None when that lane was skipped (older bookings always have all three)."""
    given = b.get(key)
    if b.get("imported"):  # booked elsewhere (F-042): stand-ins for the offers, built from the stored template
        build = {"flight": tripimport.flight_offer, "stay": tripimport.stay_offer, "car": tripimport.car_offer}[kind]
        return build(_plan(b), given) if given else None
    return catalog.offer(given) if given and given in {o.id for o in catalog.offers(kind)} else None  # the retired "c3" no car reads as skipped


def flight_of(b):
    """The flight offer of booking `b`, or None when the traveler is driving. THE SEAM for the flight window (F-021): the arrival and
    departure limits come from the "b-out" and "b-back" blocks, which only exist with a flight, so with none there is no limit."""
    return _lane(b, "flight", "flight")


def stay_of(b):
    """The stay offer of booking `b`, or None when the traveler is staying with friends."""
    return _lane(b, "stay", "stay")


def stay_for(b, leg):
    """The stay a ride leg ("arrive" or "depart") goes to or leaves from: an imported trip with several hotels has one for each night."""
    return tripimport.stay_offer(_plan(b), b["stay"], leg) if is_imported(b) and b.get("stay") else stay_of(b)


def car_of(b):
    """The rental car offer of booking `b`, or None when there is no car."""
    return _lane(b, "car", "car")


def stay_pick_of(b):
    """The StayPick (rooms and add-ons) a booking `b` holds, or None with no stay. Older bookings have none and mean the default room."""
    return catalog.stay_pick(b["stay"], b.get("rooms") or None, b.get("add") or None, trip_of(b)) if stay_of(b) and not is_imported(b) else None


def flight_pick_of(b):
    """The FlightPick (fare and checked bags) a booking `b` holds, or None with no flight. Older bookings have none and mean Basic with no bags."""
    return catalog.flight_pick(b["flight"], b.get("fare") or None, b.get("bags") or None, trip_of(b)) if flight_of(b) and not is_imported(b) else None


def rides_of(b):
    """The catalog.Rides estimate of booking `b` (a flight and no car), or None. It is not charged and not stored: it follows the picks.

    An imported trip (F-042) has rides when it lands at an airport the rides table knows (LAX, BUR) and has a flight home."""
    f = flight_of(b)
    if not f or car_of(b):
        return None
    if is_imported(b):
        return catalog.rides(f, None, trip_of(b)) if f.airport in ride_model.AIRPORTS and f.back_depart_min is not None else None
    return catalog.rides(f, stay_of(b), trip_of(b))


def _ride_day_start(plan, t):
    """(day index, start minute) of a ride leg on trip `t`, or None when the pickup falls outside the trip."""
    day = (plan.pickup_time.date() - t.depart).days
    return (day, plan.pickup_time.hour * 60 + plan.pickup_time.minute) if 0 <= day <= (t.return_ - t.depart).days else None


def ride_blocks(session, b, t):
    """The simulated Uber rides (F-038) that belong to booking `b`, as locked blocks (kind "ride", id = the ride id). Cancelled rides have none.
    A ride belongs to a booking with the same flight, stay and trip, and only when there is no car."""
    if not rides_of(b):
        return []
    blocks = []
    for r in ride_model.list_rides(session):
        where = _ride_day_start(r.plan, t) if r.key == ride_model.booking_key(b) and not r.canceled else None
        if where:
            blocks.append(Block(r.id, where[0], where[1], where[1] + r.minutes, f"Uber · {r.product_name} · {r.plan.short_route}", "ride", True, "car"))
    return blocks


def ride_offers(session, b, t):
    """One block per leg of booking `b` that has no live ride yet ("ro-arrive", "ro-depart"): the calendar offers to schedule an Uber there."""
    if not rides_of(b):
        return []
    have = {r.leg for r in ride_model.list_rides(session) if r.key == ride_model.booking_key(b) and not r.canceled}
    trip = trip_of(b)
    flight = flight_of(b)
    out = []
    for leg in ride_model.LEGS:
        plan = ride_model.leg_plan(leg, flight, stay_for(b, leg), trip)
        where = _ride_day_start(plan, t)
        if leg not in have and where:
            out.append(Block(f"ro-{leg}", where[0], where[1], where[1] + plan.minutes, f"Schedule an Uber · {plan.short_route}", "rideoffer", False, "car"))
    return out


def booked_sentence(b):
    """What /booked says is on the calendar. A car has no block there, so a car-only booking says only that the car is booked."""
    words = booked_words(b)
    if not words:
        return "Your car is booked. It has no block on the calendar, but you can still fill the gaps with your crew."
    return f"Your {words} on the trip calendar. Now the fun part: fill the gaps with your crew."


def oxford(items):
    """"a", "a and b", "a, b, and c": a plain list with an Oxford comma."""
    items = list(items)
    if len(items) < 3:
        return " and ".join(items)
    return ", ".join(items[:-1]) + ", and " + items[-1]


def booked_words(b):
    """"flights and hotel are", "hotel is", "flights are" for the calendar's welcome lines; "car is" with only a car."""
    parts = (["flights"] if flight_of(b) else []) + (["hotel"] if stay_of(b) else [])
    if not parts:
        return ""
    return " and ".join(parts) + (" are" if len(parts) > 1 or parts[0] == "flights" else " is")


def booked_blocks(b, t):
    """The locked blocks a booking `b` puts on the calendar of trip `t`: the two flights with a flight, check in and check out with a stay."""
    if is_imported(b):
        return imported_blocks(_plan(b), t)
    flight, stay = flight_of(b), stay_of(b)
    last = (t.return_ - t.depart).days
    blocks = []
    if flight:
        fp = flight_pick_of(b)
        fare = "" if fp.is_default else f" · {fp.short}"
        blocks.append(Block("b-out", 0, flight.depart_min, flight.arrive_min, f"{flight.name} · {t.origin} → {flight.airport}{fare}", "booked", True, "plane"))
    if stay:
        blocks.append(Block("b-in", 0, CHECK_IN, CHECK_IN + STAY_LEN, f"Check in · {stay.name} · {stay_pick_of(b).rooms_summary}", "booked", True, "bed"))
        blocks.append(Block("b-out2", last, CHECK_OUT, CHECK_OUT + STAY_LEN, f"Check out · {stay.name}", "booked", True, "bed"))
    if flight:
        blocks.append(Block("b-back", last, flight.back_depart_min, flight.back_arrive_min, f"{flight.name} · {flight.airport} → {t.origin}{fare}", "booked", True, "plane"))
    return blocks


LAST_MIN = 24 * 60 - 1  # nothing booked runs past 11:59 PM
CAR_LEN = 30  # an imported car's pickup and dropoff are small blocks this long


def imported_blocks(plan, t):
    """The locked blocks an imported trip (F-042) puts on the calendar of trip `t`, each tagged "Booked elsewhere · <where>".

    Every flight leg, each hotel's check in and check out, and the car's pickup and dropoff. "b-out" is the arrival at the destination and
    "b-back" the flight home, so the flight window (day_window, window_problem) follows the real first arrival and last departure.
    A block never runs past 11:59 PM. A red-eye is two blocks, the leaving evening and the landing morning: the one the window reads keeps
    the id ("b-out" is the landing morning, "b-back" the leaving evening); the other gets "-d" (leaves) or "-a" (arrives).
    """
    tag = f"Booked elsewhere · {plan.booked_on}"
    last = (t.return_ - t.depart).days
    out = []

    def put(block_id, at_day, start, end, title, icon):
        if 0 <= at_day <= last:
            start = min(start, LAST_MIN - 1)  # keep the true time; only a 11:59 PM start is nudged so the block has a height
            out.append(Block(block_id, at_day, start, min(max(end, start + 15), LAST_MIN) if start + 15 <= LAST_MIN else LAST_MIN, title, "booked", True, icon, tag))

    for spec in tripimport.block_specs(plan):
        x = spec.item
        if spec.kind == "leg":
            title = f"{x.name} · {x.origin} → {x.dest}"
            d0, d1 = (x.depart.date() - t.depart).days, (x.arrive.date() - t.depart).days
            if d1 == d0:
                put(spec.id, d0, _min(x.depart), _min(x.arrive), title, "plane")
            else:  # lands after midnight
                landing_id, leaving_id = (spec.id, spec.id + "-d") if spec.id == "b-out" else (spec.id + "-a", spec.id)
                put(leaving_id, d0, _min(x.depart), LAST_MIN, title, "plane")
                put(landing_id, d1, 0, _min(x.arrive), title, "plane")
        elif spec.kind in ("checkin", "checkout"):
            at = x.check_in if spec.kind == "checkin" else x.check_out
            put(spec.id, (at.date() - t.depart).days, _min(at), _min(at) + STAY_LEN, f"{'Check in' if spec.kind == 'checkin' else 'Check out'} · {x.name}", "bed")
        else:
            at = x.pickup if spec.kind == "pickup" else x.dropoff
            where = x.pickup_place if spec.kind == "pickup" else x.dropoff_place
            put(spec.id, (at.date() - t.depart).days, _min(at), _min(at) + CAR_LEN, f"{'Pick up' if spec.kind == 'pickup' else 'Drop off'} {x.company} car · {where}", "car")
    return out


def _min(at):
    return at.hour * 60 + at.minute


def booking_detail(b, block_id):
    """(title, [(label, value)]) of one booked block of an imported booking, confirmation number included; None for anything else.
    The only place a confirmation number is drawn (with the trip details page): both are for signed-in family members only."""
    if not is_imported(b):
        return None
    plan = _plan(b)
    block_id = block_id.removesuffix("-d").removesuffix("-a")  # the other half of a red-eye opens the same booking
    spec = next((s for s in tripimport.block_specs(plan) if s.id == block_id), None)
    return tripimport.detail_rows(spec, plan) if spec else None


AIRPORT_BUFFER = catalog.AIRPORT_BUFFER  # one source: minutes before the flight home that a plan must be finished by


def day_window(blocks, day):
    """(first start, last end) for plans on `day`: nothing before the arrival flight lands on the first day, and nothing
    later than AIRPORT_BUFFER minutes before the flight home leaves on the last day. Pure."""
    lo, hi = grid_start(blocks), GRID_END
    for b in blocks:
        if b.id == "b-out" and b.day == day:
            lo = max(lo, b.end)
        if b.id == "b-back" and b.day == day:
            hi = min(hi, b.start - AIRPORT_BUFFER)
    return lo, hi


def window_problem(blocks, day, start, end):
    """("land", landing minute) when a plan starts before you land, ("home", latest end) when it ends too close to the flight
    home, else None. Pure."""
    for b in blocks:
        if b.id == "b-out" and b.day == day and start < b.end:
            return "land", b.end
        if b.id == "b-back" and b.day == day and end > b.start - AIRPORT_BUFFER:
            return "home", b.start - AIRPORT_BUFFER
    return None


def window_message(problem):
    """The sentence the calendar shows for a window_problem."""
    kind, at = problem
    if kind == "land":
        return f"You land at {fmt_time(at)} on the first day. Plan after that."
    return f"Your flight home leaves at {fmt_time(at + AIRPORT_BUFFER)}. Finish by {fmt_time(at)}."


def window_note(problem):
    """The short clash note for a fork plan (see Placement.clash)."""
    kind, at = problem
    return f"before you land at {fmt_time(at)}" if kind == "land" else f"too close to your flight home (finish by {fmt_time(at)})"


def grid_end(blocks):
    """The hour grid's last minute: 10 PM, or the hour after the latest booked block (an 11:30 PM check in), at most midnight."""
    latest = max([GRID_END, *(x.end for x in blocks)])
    return min(-(-latest // 60) * 60, 24 * 60)


def grid_start(blocks):
    """7 AM, or the hour of an earlier booked block (a 6:40 AM flight)."""
    earliest = min([DEFAULT_START, *(x.start for x in blocks)])
    return earliest // 60 * 60


# ---- state (the family database) -----------------------------------------------------------------------------------

MAX_ACTIVITIES = 400  # per trip: a sane ceiling so one family cannot grow its database without end
MAX_NOTES = 800
MAX_DEAD = 20  # deleted ids remembered per trip, so a stale re-post of one is refused
_SEED_ROWS = [(1, 10, 13, "Griffith Observatory", "culture"), (2, 9, 11, "Venice Canals stroll", "outdoors"),
              (4, 13, 15, "Tacos at Mariscos La Ola", "food"), (7, 10, 12, "Getty Center", "culture"),
              (9, 14, 16, "Bike the Strand", "outdoors"), (12, 11, 13, "Hollywood sign hike", "outdoors"),
              (15, 18, 20, "Dinner on the pier", "food"), (18, 9, 11, "Farmers Market brunch", "fun")]


def _scope(demo):
    return LONG if demo == LONG else ""


def _pk(trip_id, scope, id_):
    return f"{trip_id}~{scope}~{id_}"


def _number(id_):
    return int(id_[1:])


def _act(r):
    return Activity(r["act_id"], r["day"], r["start_min"], r["end_min"], r["title"], r["kind"], r["author"] or "")


def _note(r):
    return Note(r["note_id"], r["body"], r["act_id"], r["author"] or "")


def _begin(db, trip_id, scope, who=""):
    """Start a write on one trip's calendar: take the write lock, make sure its counters exist, and return them.

    The first time the hidden ?demo=long fixture is opened for a trip, its eight sample activities are made here. Call it
    first inside `familydb.transaction`; everything read afterwards is current until the commit, so no write is lost.
    """
    pk = f"{trip_id}~{scope}"
    seed = _SEED_ROWS if scope == LONG else []
    made = familydb.run(db, "INSERT OR IGNORE INTO cal_state (pk, trip_id, scope, q, live) VALUES (:pk, :t, :s, :q, 0)", pk=pk, t=trip_id, s=scope, q=len(seed))
    if made and seed:
        at = familydb.now()
        for n, (d, s, e, title, kind) in enumerate(seed, 1):
            insert_only(db, "activities", {"pk": _pk(trip_id, scope, f"a{n}"), "trip_id": trip_id, "scope": scope, "act_id": f"a{n}", "seq": n, "day": d,
                                           "start_min": s * 60, "end_min": e * 60, "title": title, "kind": kind, "author": "", "added_by": who,
                                           "gone": 0, "created_at": at}, ["pk"], auto_commit=False)
    return familydb.row(db, "SELECT * FROM cal_state WHERE pk = :pk", pk=pk)


def _peek(db, trip_id, scope):
    """The counters of a trip's calendar for reading (the ?demo=long fixture is made the first time it is seen)."""
    st = familydb.row(db, "SELECT * FROM cal_state WHERE pk = :pk", pk=f"{trip_id}~{scope}")
    if st is None and scope == LONG:
        with familydb.transaction(db):
            st = _begin(db, trip_id, scope)
    return st or {"q": 0, "live": 0}


def _live_acts(db, trip_id, scope):
    return familydb.rows(db, "SELECT * FROM activities WHERE trip_id = :t AND scope = :s AND gone = 0", t=trip_id, s=scope)


def _need(fam, demo):
    """(booking, trip, booked blocks) for the open trip, or CalendarError when signed out or nothing is booked."""
    if fam is None:
        raise CalendarError("Sign in to use the trip calendar.")
    b = fam.booking()
    if not b:
        raise CalendarError("Book a trip first, then plan the gaps.")
    t = trip(demo, b)
    return b, t, booked_blocks(b, t)


def _bump(db, trip_id, scope, q):
    familydb.run(db, "UPDATE cal_state SET q = MAX(q, :q) WHERE pk = :pk", q=q, pk=f"{trip_id}~{scope}")


def next_id(session, demo=""):
    """The number the next new activity or note will use (as text). Forms carry it so a refresh cannot duplicate."""
    with ses.family(session) as fam:
        if not fam or not fam.trip_id:
            return "1"
        return str(_peek(fam.db, fam.trip_id, _scope(demo))["q"] + 1)


def activities(session, demo=""):
    with ses.family(session) as fam:
        if not fam or not fam.trip_id:
            return []
        scope = _scope(demo)
        _peek(fam.db, fam.trip_id, scope)
        return sorted((_act(r) for r in _live_acts(fam.db, fam.trip_id, scope)), key=lambda a: (a.day, a.start, a.id))


def get_activity(session, id_, demo=""):
    return next((a for a in activities(session, demo) if a.id == id_), None)


def notes(session, demo=""):
    with ses.family(session) as fam:
        if not fam or not fam.trip_id:
            return []
        scope = _scope(demo)
        _peek(fam.db, fam.trip_id, scope)
        return [_note(r) for r in familydb.rows(fam.db, "SELECT * FROM notes WHERE trip_id = :t AND scope = :s AND gone = 0 ORDER BY seq, rowid", t=fam.trip_id, s=scope)]


def last_deleted(session, demo=""):
    with ses.family(session) as fam:
        if not fam or not fam.trip_id:
            return None
        gone = familydb.row(fam.db, "SELECT * FROM activities WHERE trip_id = :t AND scope = :s AND gone = 1", t=fam.trip_id, s=_scope(demo))
        return _act(gone) if gone else None


# ---- validation ----------------------------------------------------------------------------------------------------

def snap(m):
    return round(m / SNAP) * SNAP


def parse_time(value, what):
    if isinstance(value, int):
        return value
    m = _TIME.match((value or "").strip())
    if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
        raise CalendarError(f"Pick a {what} time.")
    return int(m.group(1)) * 60 + int(m.group(2))


def _clean(t, blocks, *, day, start, end, title, kind, old=None):
    """Validate an activity on trip `t` with booked `blocks`. `old` is the (day, start, end) it already has: when unchanged, the
    flight window is not re-checked, so renaming an older item (or a friend's) still works."""
    title = " ".join((title or "").split())
    if not title:
        raise CalendarError("Give it a title.")
    if len(title) > MAX_TITLE:
        raise CalendarError(f"Keep the title to {MAX_TITLE} characters.")
    if kind not in KINDS:
        raise CalendarError("Pick a kind.")
    n = (t.return_ - t.depart).days + 1
    try:
        day = int(day)
    except (TypeError, ValueError):
        raise CalendarError("Pick a day.")
    if not 0 <= day < n:
        raise CalendarError("Pick a day inside your trip.")
    s, e = snap(parse_time(start, "start")), snap(parse_time(end, "end"))
    lo = grid_start(blocks)
    if not (lo <= s and e <= GRID_END):
        raise CalendarError(f"Plan between {fmt_time(lo)} and {fmt_time(GRID_END)}.")
    if e <= s:
        raise CalendarError("The end has to be after the start.")
    if e - s < MIN_LEN:
        raise CalendarError(f"Give it at least {MIN_LEN} minutes.")
    for b in blocks:
        if b.day == day and s < b.end and b.start < e:
            raise CalendarError(f"That overlaps {b.title} ({fmt_time(b.start)} – {fmt_time(b.end)}). Pick a gap.")
    if (day, s, e) != old and (problem := window_problem(blocks, day, s, e)):
        raise CalendarError(window_message(problem))
    return day, s, e, title


def _valid_id(id_):
    if id_ is not None and not _ID.match(id_):
        raise CalendarError("That id is not valid.")


FULL = "This trip already has a lot planned. Delete something to make room."


def _insert_activity(db, fam, scope, id_, seq, d, s, e, title, kind, author=""):
    insert_only(db, "activities", {"pk": _pk(fam.trip_id, scope, id_), "trip_id": fam.trip_id, "scope": scope, "act_id": id_, "seq": seq, "day": d,
                                   "start_min": s, "end_min": e, "title": title, "kind": kind, "author": author, "added_by": fam.traveler.id,
                                   "gone": 0, "created_at": familydb.now()}, ["pk"], auto_commit=False)


def _insert_note(db, fam, scope, id_, seq, text, act=None, author=""):
    insert_only(db, "notes", {"pk": _pk(fam.trip_id, scope, id_), "trip_id": fam.trip_id, "scope": scope, "note_id": id_, "seq": seq, "body": text,
                              "act_id": act, "author": author, "added_by": fam.traveler.id, "gone": 0, "created_at": familydb.now()}, ["pk"], auto_commit=False)


# ---- activities ----------------------------------------------------------------------------------------------------

def add_activity(session, *, day, start, end, title, kind="fun", demo="", id=None):
    """Add an activity. An `id` that already exists returns the existing one, so a refreshed form adds nothing."""
    _valid_id(id)
    with ses.family(session) as fam:
        _, t, blocks = _need(fam, demo)
        day, s, e, title = _clean(t, blocks, day=day, start=start, end=end, title=title, kind=kind)
        if id and id[0] != "a":
            raise CalendarError("That id is not valid.")
        db, scope = fam.db, _scope(demo)
        with familydb.transaction(db):
            st = _begin(db, fam.trip_id, scope, fam.traveler.id)
            same = familydb.row(db, "SELECT * FROM activities WHERE trip_id = :t AND scope = :s AND act_id = :i", t=fam.trip_id, s=scope, i=id) if id else None
            if same and same["gone"]:
                return None  # deleted a moment ago: a re-posted add must not revive it (Undo does)
            if not same and id and id in (st.get("dead") or "").split(","):
                return None  # deleted and removed from the file: a stale re-post must not bring it back
            if same and (same["day"], same["start_min"], same["end_min"], same["title"], same["kind"]) == (day, s, e, title, kind):
                return _act(same)  # the same form posted again: a refresh
            if same:
                id = None  # another tab took this id: give this one a fresh id rather than dropping it
            if len(_live_acts(db, fam.trip_id, scope)) >= MAX_ACTIVITIES:
                raise CalendarError(FULL)
            id = id or f"a{st['q'] + 1}"
            _insert_activity(db, fam, scope, id, _number(id), day, s, e, title, kind)
            _bump(db, fam.trip_id, scope, _number(id))
            return Activity(id, day, s, e, title, kind)


def update_activity(session, id_, *, day=None, start=None, end=None, title=None, kind=None, demo=""):
    """Edit or move an activity; fields left as None keep their value (and are not written, so two people changing different
    fields of the same item both keep their change). Booked blocks are locked."""
    if id_.startswith("b-"):
        raise CalendarError("Booked items are locked. Change your booking to move them.")
    with ses.family(session) as fam:
        _, t, blocks = _need(fam, demo)
        db, scope = fam.db, _scope(demo)
        with familydb.transaction(db):
            _begin(db, fam.trip_id, scope, fam.traveler.id)
            row = familydb.row(db, "SELECT * FROM activities WHERE trip_id = :t AND scope = :s AND act_id = :i AND gone = 0", t=fam.trip_id, s=scope, i=id_)
            if row is None:
                raise CalendarError("That activity is gone.")
            d, s, e, name = _clean(
                t, blocks, day=row["day"] if day is None else day, start=row["start_min"] if start is None else start,
                end=row["end_min"] if end is None else end, title=row["title"] if title is None else title, kind=row["kind"] if kind is None else kind,
                old=(row["day"], row["start_min"], row["end_min"]))
            changes = {}
            if (day, start, end) != (None, None, None):
                changes.update(day=d, start_min=s, end_min=e)
            if title is not None:
                changes["title"] = name
            if kind:
                changes["kind"] = kind
            update_record(db, "activities", row["pk"], "pk", auto_commit=False, **changes)
            return _act({**row, "day": d, "start_min": s, "end_min": e, "title": name if title is not None else row["title"], "kind": kind or row["kind"]})


def delete_activity(session, id_, demo=""):
    """Delete an activity and its notes, keeping them for one undo. None when there is nothing to delete."""
    with ses.family(session) as fam:
        if not fam or not fam.trip_id:
            return None
        db, scope = fam.db, _scope(demo)
        with familydb.transaction(db):
            st = _begin(db, fam.trip_id, scope, fam.traveler.id)
            row = familydb.row(db, "SELECT * FROM activities WHERE trip_id = :t AND scope = :s AND act_id = :i AND gone = 0", t=fam.trip_id, s=scope, i=id_)
            if row is None:
                return None
            familydb.run(db, "DELETE FROM notes WHERE trip_id = :t AND scope = :s AND gone = 1", t=fam.trip_id, s=scope)  # the earlier one can no longer be undone: remove it for good
            familydb.run(db, "DELETE FROM activities WHERE trip_id = :t AND scope = :s AND gone = 1", t=fam.trip_id, s=scope)
            familydb.run(db, "UPDATE activities SET gone = 1 WHERE pk = :pk", pk=row["pk"])
            dead = [d for d in (st.get("dead") or "").split(",") if d] + [id_]
            familydb.run(db, "UPDATE cal_state SET dead = :d WHERE pk = :pk", d=",".join(dead[-MAX_DEAD:]), pk=f"{fam.trip_id}~{scope}")
            familydb.run(db, "UPDATE notes SET gone = 1 WHERE trip_id = :t AND scope = :s AND act_id = :i AND gone = 0", t=fam.trip_id, s=scope, i=id_)
            return _act(row)


def undo_delete(session, id_, demo=""):
    """Put back the activity `id_` if it is the one last deleted."""
    with ses.family(session) as fam:
        if not fam or not fam.trip_id:
            return None
        db, scope = fam.db, _scope(demo)
        with familydb.transaction(db):
            _begin(db, fam.trip_id, scope, fam.traveler.id)
            row = familydb.row(db, "SELECT * FROM activities WHERE trip_id = :t AND scope = :s AND act_id = :i AND gone = 1", t=fam.trip_id, s=scope, i=id_)
            if row is None:
                return None
            familydb.run(db, "UPDATE activities SET gone = 0 WHERE pk = :pk", pk=row["pk"])
            familydb.run(db, "UPDATE notes SET gone = 0 WHERE trip_id = :t AND scope = :s AND act_id = :i AND gone = 1", t=fam.trip_id, s=scope, i=id_)
            return _act(row)


# ---- notes ---------------------------------------------------------------------------------------------------------

def add_note(session, text, act=None, demo="", id=None):
    """Add a note to the trip, or to one activity. An existing `id` is a refresh and adds nothing."""
    _valid_id(id)
    with ses.family(session) as fam:
        _need(fam, demo)
        text = " ".join((text or "").split())
        if not text:
            raise CalendarError("Write something first.")
        if len(text) > MAX_NOTE:
            raise CalendarError(f"Keep notes to {MAX_NOTE} characters.")
        if id and id[0] != "n":
            raise CalendarError("That id is not valid.")
        db, scope = fam.db, _scope(demo)
        with familydb.transaction(db):
            st = _begin(db, fam.trip_id, scope, fam.traveler.id)
            same = familydb.row(db, "SELECT * FROM notes WHERE trip_id = :t AND scope = :s AND note_id = :i", t=fam.trip_id, s=scope, i=id) if id else None
            if same and (same["body"], same["act_id"]) == (text, act):
                return _note(same)
            if act and not familydb.row(db, "SELECT 1 AS x FROM activities WHERE trip_id = :t AND scope = :s AND act_id = :i AND gone = 0", t=fam.trip_id, s=scope, i=act):
                raise CalendarError("That activity is gone.")
            if same:
                id = None
            if familydb.row(db, "SELECT COUNT(*) AS n FROM notes WHERE trip_id = :t AND scope = :s AND gone = 0", t=fam.trip_id, s=scope)["n"] >= MAX_NOTES:
                raise CalendarError(FULL)
            id = id or f"n{st['q'] + 1}"
            _insert_note(db, fam, scope, id, _number(id), text, act or None)
            _bump(db, fam.trip_id, scope, _number(id))
            return Note(id, text, act or None)


# ---- scripted liveness (F-020) -------------------------------------------------------------------------------------

def _live_friend(db, trip_id):
    """The name the scripted friend is invited under on this trip, or None."""
    found = familydb.row(db, "SELECT name FROM friends WHERE trip_id = :t AND lower(name) = :n", t=trip_id, n=LIVE_FRIEND.casefold())
    return found["name"] if found else None


def live_pending(session, demo=""):
    """True while Mom is invited and her scripted add has not happened (or been skipped) for this trip. Only ever true on a demo trip."""
    with ses.family(session) as fam:
        if not fam or not fam.trip_id or not fam.is_demo() or not fam.booking() or not _live_friend(fam.db, fam.trip_id):
            return False
        return not _peek(fam.db, fam.trip_id, _scope(demo))["live"]


def _free_slot(blocks, acts, day, gs):
    """The first start for LIVE_LEN minutes with nothing on it: 10:00, then later mornings, then earlier ones."""
    taken = [(b.start, b.end) for b in blocks if b.day == day] + [(a.start, a.end) for a in acts if a.day == day]
    lo, hi = day_window(blocks, day)  # not before you land, not too close to the flight home
    later = range(LIVE_START, 12 * 60 + 1, 30)
    earlier = range(LIVE_START - 30, gs - 1, -30)
    for s in [*later, *earlier]:
        if s >= max(gs, lo) and s + LIVE_LEN <= hi and not any(s < e and b < s + LIVE_LEN for b, e in taken):
            return s
    return None


def live_add(session, demo=""):
    """Mom adds her activity and a note, once per trip. Returns the new Activity, or None.

    None means nothing was added: she is not invited, it already happened, or no free slot was left (then the script is
    marked done so it does not try again). Posting it again is a no-op, so a reload never duplicates it.
    """
    with ses.family(session) as fam:
        if not fam or not fam.trip_id or not fam.is_demo() or not fam.booking():  # the scripted friend only plays on the demo trip (F-043)
            return None
        _, t, blocks = _need(fam, demo)
        db, scope = fam.db, _scope(demo)
        with familydb.transaction(db):
            st = _begin(db, fam.trip_id, scope, fam.traveler.id)
            name = _live_friend(db, fam.trip_id)
            if st["live"] or not name:
                return None
            day = min(LIVE_DAY, (t.return_ - t.depart).days)  # a short trip has no third day: use its last
            start = _free_slot(blocks, [_act(r) for r in _live_acts(db, fam.trip_id, scope)], day, grid_start(blocks))
            familydb.run(db, "UPDATE cal_state SET live = 1 WHERE pk = :pk", pk=f"{fam.trip_id}~{scope}")
            if start is None:
                return None
            n = st["q"]
            note = LIVE_NOTE.replace("on Sunday", f"on {(t.depart + timedelta(days=day)):%A}")
            _insert_activity(db, fam, scope, f"a{n + 1}", n + 1, day, start, start + LIVE_LEN, LIVE_TITLE, "fun", name)
            _insert_note(db, fam, scope, f"n{n + 2}", n + 2, note, f"a{n + 1}", name)
            _bump(db, fam.trip_id, scope, n + 2)
            return Activity(f"a{n + 1}", day, start, start + LIVE_LEN, LIVE_TITLE, "fun", name)


# ---- applying a fork (F-021) ---------------------------------------------------------------------------------------

FORK_LEN = 120   # minutes a forked stop gets when the itinerary only gives a start time
FORK_MEAL_LEN = 90
MAX_BY = 20
_STOP_TIME = re.compile(r"^(\d{1,2}):(\d{2})\s*([AP]M)$", re.I)
_FORK_KIND = {"food": "food", "tree": "outdoors", "waves": "outdoors", "bike": "outdoors", "sun": "outdoors",
              "sight": "culture", "train": "travel", "car": "travel", "plane": "travel"}


@dataclass(frozen=True)
class Plan:
    """One thing from a fork, as a calendar activity waiting for a slot. `key` is stable per fork ("d2s1": day 2, stop 1)."""
    key: str
    day: int       # index into the traveler's trip days (0 is the first)
    start: int
    end: int
    title: str
    kind: str


@dataclass(frozen=True)
class Placement:
    """Where a Plan lands on the traveler's calendar.

    state "free": the slot is open. "clash": something is in the way (`clash` says what; `hard` means it can never be
    applied: a booked block, a day past the trip or hours outside the grid). "have": the same plan is already there.
    """
    plan: Plan
    state: str
    clash: str = ""
    hard: bool = False

    @property
    def checked(self):
        return self.state == "free"


def _short(title):
    """The title cut at a word to fit MAX_TITLE (or hard at MAX_TITLE when there is no word break); never an ellipsis, never empty."""
    title = " ".join(title.split())
    if len(title) <= MAX_TITLE:
        return title or "Plan"
    head = title[:MAX_TITLE + 1]
    cut = head.rsplit(" ", 1)[0] if " " in head else head[:MAX_TITLE]
    return cut.rstrip(" ,&-:·") or title[:MAX_TITLE]


def stop_start(text):
    """Minutes after midnight for a stop time like '1:00 PM', or None when it is not a clock time."""
    m = _STOP_TIME.match((text or "").strip())
    if not m or not 1 <= int(m.group(1)) <= 12 or int(m.group(2)) > 59:
        return None
    return int(m.group(1)) % 12 * 60 + int(m.group(2)) + (720 if m.group(3).upper() == "PM" else 0)


def fork_plans(itinerary):
    """The Plans in a fork's itinerary: every stop with a clock time that is not one of the author's own bookings.

    Day n of the fork lands on day n of the traveler's trip. A stop has only a start, so it gets a typical length.
    """
    out = []
    for d in itinerary.days:
        for i, s in enumerate(d.stops):
            start = stop_start(s.time)
            if s.booked or start is None:
                continue
            length = FORK_MEAL_LEN if s.kind == "food" else FORK_LEN
            out.append(Plan(f"d{d.n}s{i}", d.n - 1, start, start + length, _short(s.title), _FORK_KIND.get(s.kind, "fun")))
    return out


def _overlap(a, day, start, end):
    return a.day == day and start < a.end and a.start < end


def place_plans(plans, blocks, acts, n_days, gs):
    """Place `plans` in the empty slots around the booked `blocks` and the existing `acts` (the traveler's and friends'). Pure.

    Returns one Placement per plan, in order. A plan that only overlaps another plan (a friend's, the traveler's or an
    earlier plan of the fork) is a soft clash: unchecked by default but still allowed. Nothing here changes its inputs.
    """
    out, taken = [], []
    for p in plans:
        if any(a.day == p.day and a.start == p.start and a.title.casefold() == p.title.casefold() for a in acts):
            out.append(Placement(p, "have"))
        elif p.day >= n_days:
            out.append(Placement(p, "clash", "after your trip ends", True))
        elif p.start < gs or p.end > GRID_END:
            out.append(Placement(p, "clash", f"outside {fmt_time(gs)} to {fmt_time(GRID_END)}", True))
        elif (hit := next((b for b in blocks if _overlap(b, p.day, p.start, p.end)), None)):
            out.append(Placement(p, "clash", f"clashes with {hit.title}", True))
        elif (problem := window_problem(blocks, p.day, p.start, p.end)):
            out.append(Placement(p, "clash", window_note(problem), True))
        elif (soft := next((x for x in [*acts, *taken] if _overlap(x, p.day, p.start, p.end)), None)):
            owner = f"{soft.by}'s " if getattr(soft, "by", "") else ""
            out.append(Placement(p, "clash", f"clashes with {owner}{soft.title}"))
        else:
            out.append(Placement(p, "free"))
            taken.append(p)
    return out


def preview_plans(session, plans, demo=""):
    """The Placements of `plans` on the signed-in traveler's calendar. Raises CalendarError when signed out or nothing is booked."""
    with ses.family(session) as fam:
        _, t, blocks = _need(fam, demo)
        scope = _scope(demo)
        _peek(fam.db, fam.trip_id, scope)
        return place_plans(plans, blocks, [_act(r) for r in _live_acts(fam.db, fam.trip_id, scope)], len(days(t)), grid_start(blocks))


def preview_fork(session, itinerary, demo=""):
    """The Placements of `itinerary` on the signed-in traveler's calendar."""
    return preview_plans(session, fork_plans(itinerary), demo)


def apply_plans(session, plans, picks, by="", note=None, demo=""):
    """Add the picked `plans` to the calendar as activities and return (activities, note), oldest first.

    `note` is an optional function of the plans actually added that returns a trip note's text (or None). Hard clashes and
    plans already on the calendar are skipped, so posting the same picks again adds nothing, and then no note is added either.
    All or nothing: one transaction, so a refusal leaves the calendar as it was.
    """
    wanted = set(picks)
    with ses.family(session) as fam:
        _, t, blocks = _need(fam, demo)
        db, scope = fam.db, _scope(demo)
        with familydb.transaction(db):
            st = _begin(db, fam.trip_id, scope, fam.traveler.id)
            acts = _live_acts(db, fam.trip_id, scope)
            placed = place_plans(plans, blocks, [_act(r) for r in acts], len(days(t)), grid_start(blocks))
            chosen = [x.plan for x in placed if x.plan.key in wanted and not x.hard and x.state != "have"]
            if len(acts) + len(chosen) > MAX_ACTIVITIES:
                raise CalendarError(FULL)
            added, n = [], st["q"]
            author = " ".join(by.split())[:MAX_BY] if by.strip() else ""
            for p in chosen:
                n += 1
                _insert_activity(db, fam, scope, f"a{n}", n, p.day, p.start, p.end, p.title, p.kind, author)
                added.append(Activity(f"a{n}", p.day, p.start, p.end, p.title, p.kind, author))
            text = " ".join((note(chosen) if note and chosen else "").split())[:MAX_NOTE]
            made = None
            if text and added:
                n += 1
                _insert_note(db, fam, scope, f"n{n}", n, text)
                made = Note(f"n{n}", text)
            if added:
                _bump(db, fam.trip_id, scope, n)
            return added, made


def apply_fork(session, itinerary, picks, by="", demo=""):
    """Add the picked plans of `itinerary` to the calendar as activities and return them (oldest first). See apply_plans."""
    return apply_plans(session, fork_plans(itinerary), picks, by, demo=demo)[0]


def remove_plans(session, plans, ids, by="", note_id=None, note_prefix="", demo=""):
    """Undo an apply: remove the activities in `ids` that came from `plans` (same author, day, start and title as one of them).

    Anything else in `ids` (the traveler's own plans, a friend's) stays, so a made-up id list cannot delete it. `note_id` removes
    the whole-trip note that apply added, but only when its text starts with `note_prefix`. Returns how many activities were removed.
    """
    author = " ".join(by.split())[:MAX_BY]
    mine = {(p.day, p.start, p.title) for p in plans}
    gone = set(ids)
    with ses.family(session) as fam:
        if not fam or not fam.trip_id:
            return 0
        db, scope = fam.db, _scope(demo)
        with familydb.transaction(db):
            _begin(db, fam.trip_id, scope, fam.traveler.id)
            drop = [r for r in _live_acts(db, fam.trip_id, scope) if r["act_id"] in gone and (r["author"] or "") == author and (r["day"], r["start_min"], r["title"]) in mine]
            for r in drop:
                familydb.run(db, "DELETE FROM notes WHERE trip_id = :t AND scope = :s AND act_id = :i", t=fam.trip_id, s=scope, i=r["act_id"])
                delete_record(db, "activities", r["pk"], "pk", auto_commit=False)
            if note_id and note_prefix:
                familydb.run(db, "DELETE FROM notes WHERE trip_id = :t AND scope = :s AND note_id = :i AND act_id IS NULL AND body LIKE :p ESCAPE '\\'",
                             t=fam.trip_id, s=scope, i=note_id, p=note_prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%")
            return len(drop)


def remove_applied(session, itinerary, ids, by="", demo=""):
    """Undo an apply of `itinerary`: see remove_plans. Returns how many were removed."""
    return remove_plans(session, fork_plans(itinerary), ids, by, demo=demo) if " ".join(by.split()) else 0
