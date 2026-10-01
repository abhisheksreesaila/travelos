"""The trip calendar model (F-019): booked blocks, the traveler's activities, clashes and notes.

Pure functions over a session dict (like gitaway.session), so the HTTP layer and tests share one seam.

Booked blocks (outbound flight, check in, check out, return flight) are derived from the booking and the catalog each
time and are never stored. Activities and notes live in the signed cookie session:

    session["cal"] = {"<traveler id>[~long]": {"q": last id number, "a": [activity], "n": [note], "x": last deleted}}
    activity = {"i": "a3", "d": day index, "s": start minute, "e": end minute, "t": title, "k": kind, "b": author or absent}
    note     = {"i": "n4", "t": text, "a": activity id or absent, "b": author or absent}

"b" is the friend who wrote it ("Mom"); absent means the traveler. "l" in the state is set once the scripted live add
(F-020) has happened or been skipped, so it never repeats.

A cookie holds about 4 KB, so BUDGET caps the session and the calendar refuses more with a friendly message.
Times are minutes after midnight. Ids are stable; adding with an id that already exists is a no-op (a refresh).
"""

import json
import re
from dataclasses import dataclass, replace
from datetime import date, timedelta
from urllib.parse import parse_qs

from gitaway import catalog, context, rides as ride_model, session as ses

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
BUDGET = ses.BUDGET
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
    """The trip a booking was made for (the sample trip when it holds none, as older bookings do)."""
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

def _lane(b, key, kind):
    """The offer a booking `b` holds for one lane, or None when that lane was skipped (older bookings always have all three)."""
    given = b.get(key)
    return catalog.offer(given) if given and given in {o.id for o in catalog.offers(kind)} else None  # the retired "c3" no car reads as skipped


def flight_of(b):
    """The flight offer of booking `b`, or None when the traveler is driving. THE SEAM for the flight window (F-021): the arrival and
    departure limits come from the "b-out" and "b-back" blocks, which only exist with a flight, so with none there is no limit."""
    return _lane(b, "flight", "flight")


def stay_of(b):
    """The stay offer of booking `b`, or None when the traveler is staying with friends."""
    return _lane(b, "stay", "stay")


def car_of(b):
    """The rental car offer of booking `b`, or None when there is no car."""
    return _lane(b, "car", "car")


def stay_pick_of(b):
    """The StayPick (rooms and add-ons) a booking `b` holds, or None with no stay. Older bookings have none and mean the default room."""
    return catalog.stay_pick(b["stay"], b.get("rooms") or None, b.get("add") or None, trip_of(b)) if stay_of(b) else None


def flight_pick_of(b):
    """The FlightPick (fare and checked bags) a booking `b` holds, or None with no flight. Older bookings have none and mean Basic with no bags."""
    return catalog.flight_pick(b["flight"], b.get("fare") or None, b.get("bags") or None, trip_of(b)) if flight_of(b) else None


def rides_of(b):
    """The catalog.Rides estimate of booking `b` (a flight and no car), or None. It is not charged and not stored: it follows the picks."""
    f = flight_of(b)
    return catalog.rides(f, stay_of(b), trip_of(b)) if f and not car_of(b) else None


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
    flight, stay = flight_of(b), stay_of(b)
    out = []
    for leg in ride_model.LEGS:
        plan = ride_model.leg_plan(leg, flight, stay, trip)
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


def grid_start(blocks):
    """7 AM, or the hour of an earlier booked block (a 6:40 AM flight)."""
    earliest = min([DEFAULT_START, *(x.start for x in blocks)])
    return earliest // 60 * 60


# ---- state ---------------------------------------------------------------------------------------------------------

def _seed():
    rows = [(1, 10, 13, "Griffith Observatory", "culture"), (2, 9, 11, "Venice Canals stroll", "outdoors"),
            (4, 13, 15, "Tacos at Mariscos La Ola", "food"), (7, 10, 12, "Getty Center", "culture"),
            (9, 14, 16, "Bike the Strand", "outdoors"), (12, 11, 13, "Hollywood sign hike", "outdoors"),
            (15, 18, 20, "Dinner on the pier", "food"), (18, 9, 11, "Farmers Market brunch", "fun")]
    return {"q": len(rows), "a": [{"i": f"a{n}", "d": d, "s": s * 60, "e": e * 60, "t": t, "k": k}
                                  for n, (d, s, e, t, k) in enumerate(rows, 1)], "n": [], "x": None}


def _key(session, demo):
    t = ses.current_traveler(session)
    return f"{t.id}~{LONG}" if t and demo == LONG else (t.id if t else None)


def _load(session, demo):
    key = _key(session, demo)
    found = (session.get("cal") or {}).get(key)
    if found is not None:
        return json.loads(json.dumps(found))
    return _seed() if demo == LONG else {"q": 0, "a": [], "n": [], "x": None}


def _save(session, demo, state, enforce=True):
    old = session.get("cal")
    session["cal"] = {**(old or {}), _key(session, demo): state}
    if enforce and len(json.dumps(dict(session))) > BUDGET:
        if old is None:
            session.pop("cal", None)
        else:
            session["cal"] = old
        raise CalendarError("This demo calendar is full. Delete something to make room.")


def _context(session, demo):
    if not ses.current_traveler(session):
        raise CalendarError("Sign in to use the trip calendar.")
    b = ses.booking(session)
    if not b:
        raise CalendarError("Book a trip first, then plan the gaps.")
    t = trip(demo, b)
    return b, t, booked_blocks(b, t)


def _act(d):
    return Activity(d["i"], d["d"], d["s"], d["e"], d["t"], d["k"], d.get("b", ""))


def _note(d):
    return Note(d["i"], d["t"], d.get("a"), d.get("b", ""))


def _number(id_):
    return int(id_[1:])


def next_id(session, demo=""):
    """The number the next new activity or note will use (as text). Forms carry it so a refresh cannot duplicate."""
    return str(_load(session, demo)["q"] + 1)


def activities(session, demo=""):
    if not ses.current_traveler(session):
        return []
    return sorted((_act(a) for a in _load(session, demo)["a"]), key=lambda a: (a.day, a.start, a.id))


def get_activity(session, id_, demo=""):
    return next((a for a in activities(session, demo) if a.id == id_), None)


def notes(session, demo=""):
    if not ses.current_traveler(session):
        return []
    return [_note(n) for n in _load(session, demo)["n"]]


def last_deleted(session, demo=""):
    x = _load(session, demo)["x"] if ses.current_traveler(session) else None
    return _act(x["a"]) if x else None


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


def _clean(session, demo, *, day, start, end, title, kind, old=None):
    """Validate an activity. `old` is the (day, start, end) it already has: when unchanged, the flight window is not re-checked,
    so renaming an older item (or a friend's) still works."""
    _, t, blocks = _context(session, demo)
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


# ---- activities ----------------------------------------------------------------------------------------------------

def add_activity(session, *, day, start, end, title, kind="fun", demo="", id=None):
    """Add an activity. An `id` that already exists returns the existing one, so a refreshed form adds nothing."""
    _valid_id(id)
    day, s, e, title = _clean(session, demo, day=day, start=start, end=end, title=title, kind=kind)
    state = _load(session, demo)
    if id and id[0] != "a":
        raise CalendarError("That id is not valid.")
    if id and id in state.get("g", []):
        return None  # deleted a moment ago: a re-posted add must not revive it (Undo does)
    same = next((a for a in state["a"] if a["i"] == id), None) if id else None
    if same and (same["d"], same["s"], same["e"], same["t"], same["k"]) == (day, s, e, title, kind):
        return _act(same)  # the same form posted again: a refresh
    if same:
        id = None  # another tab took this id: give this one a fresh id rather than dropping it
    id = id or f"a{state['q'] + 1}"
    state["q"] = max(state["q"], _number(id))
    row = {"i": id, "d": day, "s": s, "e": e, "t": title, "k": kind}
    state["a"].append(row)
    _save(session, demo, state)
    return _act(row)


def update_activity(session, id_, *, day=None, start=None, end=None, title=None, kind=None, demo=""):
    """Edit or move an activity; fields left as None keep their value. Booked blocks are locked."""
    if id_.startswith("b-"):
        raise CalendarError("Booked items are locked. Change your booking to move them.")
    state = _load(session, demo)
    row = next((a for a in state["a"] if a["i"] == id_), None)
    if row is None:
        raise CalendarError("That activity is gone.")
    day, s, e, title = _clean(
        session, demo, day=row["d"] if day is None else day, start=row["s"] if start is None else start,
        end=row["e"] if end is None else end, title=row["t"] if title is None else title, kind=row["k"] if kind is None else kind,
        old=(row["d"], row["s"], row["e"]))
    row.update(d=day, s=s, e=e, t=title, k=kind or row["k"])
    _save(session, demo, state)
    return _act(row)


def delete_activity(session, id_, demo=""):
    """Delete an activity and its notes, keeping them for one undo. None when there is nothing to delete."""
    state = _load(session, demo)
    row = next((a for a in state["a"] if a["i"] == id_), None)
    if row is None:
        return None
    state["a"] = [a for a in state["a"] if a["i"] != id_]
    state["x"] = {"a": row, "n": [n for n in state["n"] if n.get("a") == id_]}
    state["g"] = [*state.get("g", []), id_][-6:]
    state["n"] = [n for n in state["n"] if n.get("a") != id_]
    _save(session, demo, state, enforce=False)
    return _act(row)


def undo_delete(session, id_, demo=""):
    """Put back the activity `id_` if it is the one last deleted."""
    state = _load(session, demo)
    x = state["x"]
    if not x or x["a"]["i"] != id_ or any(a["i"] == id_ for a in state["a"]):
        return None
    state["a"].append(x["a"])
    state["n"] = sorted([*state["n"], *x["n"]], key=lambda n: _number(n["i"]))
    state["x"] = None
    state["g"] = [g for g in state.get("g", []) if g != id_]
    _save(session, demo, state)
    return _act(x["a"])


# ---- notes ---------------------------------------------------------------------------------------------------------

def add_note(session, text, act=None, demo="", id=None):
    """Add a note to the trip, or to one activity. An existing `id` is a refresh and adds nothing."""
    _valid_id(id)
    _context(session, demo)
    text = " ".join((text or "").split())
    if not text:
        raise CalendarError("Write something first.")
    if len(text) > MAX_NOTE:
        raise CalendarError(f"Keep notes to {MAX_NOTE} characters.")
    state = _load(session, demo)
    if id and id[0] != "n":
        raise CalendarError("That id is not valid.")
    same = next((n for n in state["n"] if n["i"] == id), None) if id else None
    if same and (same["t"], same.get("a")) == (text, act):
        return _note(same)
    if act and not any(a["i"] == act for a in state["a"]):
        raise CalendarError("That activity is gone.")
    if same:
        id = None
    id = id or f"n{state['q'] + 1}"
    state["q"] = max(state["q"], _number(id))
    row = {"i": id, "t": text, **({"a": act} if act else {})}
    state["n"].append(row)
    _save(session, demo, state)
    return _note(row)


# ---- scripted liveness (F-020) -------------------------------------------------------------------------------------

def live_pending(session, demo=""):
    """True while Mom is invited and her scripted add has not happened (or been skipped) for this trip."""
    if not (ses.current_traveler(session) and ses.booking(session) and ses.friend_named(session, LIVE_FRIEND)):
        return False
    return not _load(session, demo).get("l")


def _free_slot(blocks, state, day, gs):
    """The first start for LIVE_LEN minutes with nothing on it: 10:00, then later mornings, then earlier ones."""
    taken = [(b.start, b.end) for b in blocks if b.day == day] + [(a["s"], a["e"]) for a in state["a"] if a["d"] == day]
    lo, hi = day_window(blocks, day)  # not before you land, not too close to the flight home
    later = range(LIVE_START, 12 * 60 + 1, 30)
    earlier = range(LIVE_START - 30, gs - 1, -30)
    for s in [*later, *earlier]:
        if s >= max(gs, lo) and s + LIVE_LEN <= hi and not any(s < e and b < s + LIVE_LEN for b, e in taken):
            return s
    return None


def live_add(session, demo=""):
    """Mom adds her activity and a note, once per traveler per trip. Returns the new Activity, or None.

    None means nothing was added: she is not invited, it already happened, or no free slot was left (then the script is
    marked done so it does not try again). Posting it again is a no-op, so a reload never duplicates it.
    """
    if not live_pending(session, demo):
        return None
    _, t, blocks = _context(session, demo)
    friend = ses.friend_named(session, LIVE_FRIEND)
    state = _load(session, demo)
    day = min(LIVE_DAY, (t.return_ - t.depart).days)  # a short trip has no third day: use its last
    start = _free_slot(blocks, state, day, grid_start(blocks))
    state["l"] = 1
    if start is None:
        # Unenforced on purpose: the only growth is the one-byte-ish "l": 1 flag (about 6 bytes of JSON), and refusing it
        # would make the script retry on every load. The same bound applies to the fallback below.
        _save(session, demo, state, enforce=False)
        return None
    n = state["q"]
    act = {"i": f"a{n + 1}", "d": day, "s": start, "e": start + LIVE_LEN, "t": LIVE_TITLE, "k": "fun", "b": friend.name}
    state["a"].append(act)
    state["n"].append({"i": f"n{n + 2}", "t": LIVE_NOTE.replace("on Sunday", f"on {(t.depart + timedelta(days=day)):%A}"), "a": act["i"], "b": friend.name})
    state["q"] = n + 2
    try:
        _save(session, demo, state)
    except CalendarError:
        state["a"].pop()
        state["n"].pop()
        state["q"] = n
        _save(session, demo, state, enforce=False)
        return None
    return _act(act)


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
    _, t, blocks = _context(session, demo)
    return place_plans(plans, blocks, activities(session, demo), len(days(t)), grid_start(blocks))


def preview_fork(session, itinerary, demo=""):
    """The Placements of `itinerary` on the signed-in traveler's calendar."""
    return preview_plans(session, fork_plans(itinerary), demo)


def apply_plans(session, plans, picks, by="", note=None, demo=""):
    """Add the picked `plans` to the calendar as activities and return (activities, note), oldest first.

    `note` is an optional function of the plans actually added that returns a trip note's text (or None). Hard clashes and
    plans already on the calendar are skipped, so posting the same picks again adds nothing, and then no note is added either.
    All or nothing: a full cookie raises CalendarError and leaves the calendar as it was.
    """
    wanted = set(picks)
    chosen = [x.plan for x in preview_plans(session, plans, demo) if x.plan.key in wanted and not x.hard and x.state != "have"]
    state = _load(session, demo)
    added, n = [], state["q"]
    for p in chosen:
        n += 1
        row = {"i": f"a{n}", "d": p.day, "s": p.start, "e": p.end, "t": p.title, "k": p.kind}
        if by.strip():
            row["b"] = " ".join(by.split())[:MAX_BY]
        state["a"].append(row)
        added.append(_act(row))
    text = " ".join((note(chosen) if note and chosen else "").split())[:MAX_NOTE]
    made = None
    if text:
        n += 1
        made = {"i": f"n{n}", "t": text}
        state["n"].append(made)
    if added:
        state["q"] = n
        _save(session, demo, state)
    return added, _note(made) if made and added else None


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
    state = _load(session, demo)
    drop = {a["i"] for a in state["a"] if a["i"] in gone and a.get("b", "") == author and (a["d"], a["s"], a["t"]) in mine}
    if drop:
        state["a"] = [a for a in state["a"] if a["i"] not in drop]
        state["n"] = [n for n in state["n"] if n.get("a") not in drop]
    if note_id and note_prefix:
        state["n"] = [n for n in state["n"] if not (n["i"] == note_id and not n.get("a") and n["t"].startswith(note_prefix))]
    if not drop and state["n"] == _load(session, demo)["n"]:
        return 0
    _save(session, demo, state, enforce=False)
    return len(drop)


def remove_applied(session, itinerary, ids, by="", demo=""):
    """Undo an apply of `itinerary`: see remove_plans. Returns how many were removed."""
    return remove_plans(session, fork_plans(itinerary), ids, by, demo=demo) if " ".join(by.split()) else 0
