"""The trip calendar model (F-019): booked blocks, the traveler's activities, clashes and notes.

Pure functions over a session dict (like gitaway.session), so the HTTP layer and tests share one seam.

Booked blocks (outbound flight, check in, check out, return flight) are derived from the booking and the catalog each
time and are never stored. Activities and notes live in the signed cookie session:

    session["cal"] = {"<traveler id>[~long]": {"q": last id number, "a": [activity], "n": [note], "x": last deleted}}
    activity = {"i": "a3", "d": day index, "s": start minute, "e": end minute, "t": title, "k": kind}
    note     = {"i": "n4", "t": text, "a": activity id or absent}

A cookie holds about 4 KB, so BUDGET caps the session and the calendar refuses more with a friendly message.
Times are minutes after midnight. Ids are stable; adding with an id that already exists is a no-op (a refresh).
"""

import json
import re
from dataclasses import dataclass, replace
from datetime import date, timedelta

from gitaway import catalog, context, session as ses

LONG = "long"  # the hidden ?demo=long fixture: a 20-day trip that crosses into November
LONG_RETURN = date(2026, 11, 4)
GRID_END = 22 * 60
DEFAULT_START = 7 * 60
SNAP = 15
MIN_LEN = 30
CHECK_IN = 15 * 60
CHECK_OUT = 11 * 60
STAY_LEN = 60
MAX_TITLE = 40
MAX_NOTE = 140
BUDGET = 2900  # bytes of session JSON; the cookie is base64 of it plus a signature, under the 4 KB browsers keep

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


@dataclass(frozen=True)
class Note:
    id: str
    text: str
    act: str | None = None


# ---- trip and formatting -------------------------------------------------------------------------------------------

def trip(demo=""):
    t = catalog.SAMPLE_TRIP
    return replace(t, return_=LONG_RETURN) if demo == LONG else t


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

def booked_blocks(b, t):
    """The locked blocks a booking `b` puts on the calendar of trip `t`."""
    flight, stay = catalog.offer(b["flight"]), catalog.offer(b["stay"])
    last = (t.return_ - t.depart).days
    return [
        Block("b-out", 0, flight.depart_min, flight.arrive_min, f"{flight.name} · {t.origin} → {flight.airport}", "booked", True, "plane"),
        Block("b-in", 0, CHECK_IN, CHECK_IN + STAY_LEN, f"Check in · {stay.name}", "booked", True, "bed"),
        Block("b-out2", last, CHECK_OUT, CHECK_OUT + STAY_LEN, f"Check out · {stay.name}", "booked", True, "bed"),
        Block("b-back", last, flight.back_depart_min, flight.back_arrive_min, f"{flight.name} · {flight.airport} → {t.origin}", "booked", True, "plane"),
    ]


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
    t = trip(demo)
    return b, t, booked_blocks(b, t)


def _act(d):
    return Activity(d["i"], d["d"], d["s"], d["e"], d["t"], d["k"])


def _note(d):
    return Note(d["i"], d["t"], d.get("a"))


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

def _snap(m):
    return round(m / SNAP) * SNAP


def _minutes(value, what):
    if isinstance(value, int):
        return value
    m = _TIME.match((value or "").strip())
    if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
        raise CalendarError(f"Pick a {what} time.")
    return int(m.group(1)) * 60 + int(m.group(2))


def _clean(session, demo, *, day, start, end, title, kind):
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
    s, e = _snap(_minutes(start, "start")), _snap(_minutes(end, "end"))
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
    if id and any(a["i"] == id for a in state["a"]):
        return _act(next(a for a in state["a"] if a["i"] == id))
    if id and id[0] != "a":
        raise CalendarError("That id is not valid.")
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
        end=row["e"] if end is None else end, title=row["t"] if title is None else title, kind=row["k"] if kind is None else kind)
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
    if id and any(n["i"] == id for n in state["n"]):
        return _note(next(n for n in state["n"] if n["i"] == id))
    if id and id[0] != "n":
        raise CalendarError("That id is not valid.")
    if act and not any(a["i"] == act for a in state["a"]):
        raise CalendarError("That activity is gone.")
    id = id or f"n{state['q'] + 1}"
    state["q"] = max(state["q"], _number(id))
    row = {"i": id, "t": text, **({"a": act} if act else {})}
    state["n"].append(row)
    _save(session, demo, state)
    return _note(row)
