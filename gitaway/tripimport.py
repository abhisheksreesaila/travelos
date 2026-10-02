"""Import a trip booked elsewhere (F-042): parse docs/trip-template.md, keep it, and turn it into what the calendar and rides read.

PARSING. `parse(text)` takes the whole markdown of the template (the fenced yaml block is found) or just the YAML, reads it with
PyYAML `safe_load` only (no tags, no anchors or aliases), checks everything and returns a `Parsed(plan, warnings)`, or raises
`ImportProblem` whose `errors` are friendly, line-specific sentences ("Line 24: ..."). Input is bounded (MAX_BYTES). The template
stays backwards compatible: every field it shows is accepted as it is shipped.

A `Plan` is the validated trip: the party, flight legs (any number, connections included), a hotel, an optional car, notes. `to_doc`
and `from_doc` turn it into the JSON the family database keeps (table `trip_imports`, gitaway.familydb_import).

THE SEAMS. The calendar and rides read a booking through gitaway.tripcal, which asks this module for duck-typed stand-ins of the
catalog offers: `flight_offer` (the arrival at the destination and the departure home, with their real dates), `stay_offer` (the
hotel, with its address) and `car_offer`, and for the trip itself `trip_search` (the real dates and party). `block_specs` says which
calendar blocks a plan puts down, and `detail_rows` what a block's booking detail shows (the confirmation numbers live only there
and on the trip details page: never in a block title, a shared snapshot, a URL or a page's meta).

THE DESTINATION. With connections the destination is where the longest wait is: the leg before it lands there ("b-out", the flight
window's first arrival), the leg after it leaves ("b-back", the last departure). One leg alone has only an arrival.
"""

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import yaml

from gitaway import catalog, zones

MAX_BYTES = 50_000
MAX_TRAVELERS = 12
MAX_LEGS = 12
ONE_WAY_WAIT = timedelta(hours=12)   # a wait this long between legs is the stay; shorter ones are connections
MAX_DAYS = 31      # a trip is at most this many calendar days long
MAX_NOTES = 2000
SOURCE = "imported"

_AIRPORT = re.compile(r"^[A-Za-z]{3}$")
_EMAIL = re.compile(r"^[^@\s,;<>]+@[^@\s,;<>]+\.[^@\s,;<>]+$")
_STAMP = re.compile(r"^(\d{4}-\d{2}-\d{2})[ T](\d{1,2}):(\d{2})(?::\d{2}(?:\.\d+)?)?\s*(?:Z|[+-]\d{2}(?::?\d{2})?)?$")  # a UTC offset is accepted and ignored: times are local
_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
KNOWN = ("trip", "travelers", "flights", "hotel", "hotels", "car", "notes")


class ImportProblem(ValueError):
    """A template the importer cannot use. `errors` lists every problem as a sentence fit to show; `warnings` are the harmless ones."""

    def __init__(self, errors, warnings=()):
        self.errors = list(errors)
        self.warnings = list(warnings)
        super().__init__(self.errors[0] if self.errors else "Could not read that")


# ---- the plan -------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Traveler:
    name: str
    email: str = ""
    age: int | None = None

    @property
    def is_kid(self) -> bool:
        return self.age is not None and self.age < 18


@dataclass(frozen=True)
class Leg:
    airline: str
    number: str
    origin: str
    dest: str
    depart: datetime   # local time at the origin
    arrive: datetime   # local time at the destination
    confirmation: str = ""
    seats: str = ""

    @property
    def name(self) -> str:
        return f"{self.airline} {self.number}".strip()


@dataclass(frozen=True)
class Lodging:
    name: str
    address: str
    check_in: datetime
    check_out: datetime
    confirmation: str = ""
    room: str = ""
    rooms: int = 1
    phone: str = ""


@dataclass(frozen=True)
class Rental:
    company: str
    pickup_place: str
    pickup: datetime
    dropoff_place: str
    dropoff: datetime
    confirmation: str = ""
    car: str = ""


def _split(legs):
    """(index of the arrival leg, index of the departure leg or None): the legs either side of the longest wait."""
    if not legs:
        return None, None
    gaps = [(legs[i + 1].depart - legs[i].arrive, -i) for i in range(len(legs) - 1)]
    if not gaps or max(gaps)[0] < ONE_WAY_WAIT:  # no long wait anywhere: one way (connections included), the last leg is the arrival
        return len(legs) - 1, None
    i = -max(gaps)[1]  # open-jaw trips (home from another airport) split here too
    return i, i + 1


@dataclass(frozen=True)
class Plan:
    title: str
    destination: str
    start: date
    end: date
    booked_on: str
    itinerary: str
    travelers: tuple
    legs: tuple = ()
    hotels: tuple = ()
    rental: Rental | None = None
    notes: str = ""
    timezone: str = zones.DEFAULT   # IANA name: where "today" and "up next" are measured (F-057)

    @property
    def adults(self) -> int:
        return sum(1 for t in self.travelers if not t.is_kid)

    @property
    def kid_ages(self) -> tuple:
        return tuple(sorted(t.age for t in self.travelers if t.is_kid))

    @property
    def home(self) -> str:
        """Where the first flight leaves from (the sample's SFO when there is no flight)."""
        return self.legs[0].origin if self.legs else catalog.ORIGIN[0]

    def _split(self):
        return _split(self.legs)

    @property
    def arrive_leg(self):
        i, _ = self._split()
        return self.legs[i] if i is not None else None

    @property
    def depart_leg(self):
        _, j = self._split()
        return self.legs[j] if j is not None else None

    @property
    def party_text(self) -> str:
        kids, adults = len(self.kid_ages), self.adults
        parts = [f"{adults} adult{'s' if adults != 1 else ''}"]
        if kids:
            parts.append(f"{kids} kid{'s' if kids != 1 else ''}")
        return ", ".join(parts)


@dataclass(frozen=True)
class Parsed:
    plan: Plan
    warnings: tuple = ()


# ---- reading the text -----------------------------------------------------------------------------------------------

def _block(text):
    """(yaml text, the line number its first line has in `text`): the fenced block of a pasted template, or all of it."""
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if re.match(r"^\s*```", line):
            if start is None:
                lang = line.strip()[3:].strip().lower()
                if lang in ("", "yaml", "yml"):
                    start = i + 1
            else:
                return "\n".join(lines[start:i]), start
    if start is not None:  # the closing fence was left off
        return "\n".join(lines[start:]), start
    return text, 0


MAX_DEPTH = 10   # a template is a few levels deep (section, list item, field); anything deeper is refused


class _TooDeep(Exception):
    pass


TOO_DEEP = "That is nested too deeply to be a trip template. Check the indentation and brackets."


def _walk(node, path, out, depth=0):
    """Fill `out` with {path tuple: line number (1-based, in the yaml)} for every key and list item."""
    if depth > MAX_DEPTH:
        raise _TooDeep
    if isinstance(node, yaml.MappingNode):
        for k, v in node.value:
            key = k.value if isinstance(k, yaml.ScalarNode) else str(k)
            out[path + (key,)] = k.start_mark.line + 1
            _walk(v, path + (key,), out, depth + 1)
    elif isinstance(node, yaml.SequenceNode):
        for i, v in enumerate(node.value):
            out[path + (i,)] = v.start_mark.line + 1
            _walk(v, path + (i,), out, depth + 1)


def _plain(r, node, path=()):
    """The node as plain data in which every scalar is its raw text (so 012345, yes, 12:30:45 and 0x1F stay exactly as typed) and an
    empty value is None. Nothing is constructed from tags, so no YAML type can run code. A repeated key is an error."""
    if isinstance(node, yaml.ScalarNode):
        return None if node.tag == "tag:yaml.org,2002:null" else node.value
    if isinstance(node, yaml.SequenceNode):
        return [_plain(r, v, path + (i,)) for i, v in enumerate(node.value)]
    out = {}
    for k, v in node.value:
        if not isinstance(k, yaml.ScalarNode):
            r.bad(path, "A name before a colon should be plain text.")
            continue
        if k.value in out:
            r.bad(path + (k.value,), f"“{k.value}” appears twice. Keep one, and put all of its details under it.")
            continue
        out[k.value] = _plain(r, v, path + (k.value,))
    return out


class _Reader:
    """Collects the errors, each tagged with the line of the field it is about."""

    def __init__(self, lines, offset):
        self.lines, self.offset = lines, offset
        self.errors, self.warnings = [], []

    def line(self, path):
        while path and path not in self.lines:
            path = path[:-1]
        return (self.lines.get(path, 0) + self.offset) if path else 0

    def bad(self, path, message):
        n = self.line(path)
        self.errors.append((f"Line {n}: " if n else "") + message)

    def warn(self, path, message):
        n = self.line(path)
        self.warnings.append((f"Line {n}: " if n else "") + message)


def _text(r, data, key, path, label, *, required=False, limit=80, default=""):
    value = data.get(key)
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            r.bad(path + (key,) if key in data else path, f"{label} is missing. Add a line like “{key}: …”.")
        return default
    if isinstance(value, (dict, list)):
        r.bad(path + (key,), f"{label} should be plain text, not a list.")
        return default
    value = " ".join(str(value).split())  # `value` is always the raw text of the scalar (see _plain): 012345 stays 012345, yes stays yes
    if len(value) > limit:
        r.bad(path + (key,), f"{label} is too long (at most {limit} characters).")
        return value[:limit]
    return value


def _day(r, value, path, label):
    """A date from `YYYY-MM-DD` (YAML may already have read it as a date)."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and _DAY.match(value.strip()):
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            pass
    r.bad(path, f"{label} should be a date like 2026-10-16.")
    return None


def _stamp(r, value, path, label, default_time=None):
    """A local date and time from `YYYY-MM-DD HH:MM` (a plain date works too when `default_time` is given)."""
    if isinstance(value, datetime):
        return value.replace(second=0, microsecond=0, tzinfo=None)
    if isinstance(value, date) and default_time:
        return datetime.combine(value, default_time)
    if isinstance(value, str):
        m = _STAMP.match(value.strip())
        if m:
            h, mi = int(m.group(2)), int(m.group(3))
            try:
                if h > 23 or mi > 59:
                    raise ValueError
                return datetime.combine(date.fromisoformat(m.group(1)), datetime.min.time()).replace(hour=h, minute=mi)
            except ValueError:
                pass
        if default_time and _DAY.match(value.strip()):
            try:
                return datetime.combine(date.fromisoformat(value.strip()), default_time)
            except ValueError:
                pass
    r.bad(path, f"{label} should be a date and a 24-hour time like 2026-10-16 08:05.")
    return None


def _mapping(r, value, path, label):
    if isinstance(value, dict):
        return value
    r.bad(path, f"{label} should be a list of “name: value” lines.")
    return None


def _airport(r, data, key, path, label):
    raw = data.get(key)
    if not (isinstance(raw, str) and _AIRPORT.match(raw.strip())):
        r.bad(path + (key,) if key in data else path, f"{label} should be a three-letter airport code like SFO.")
        return ""
    return raw.strip().upper()


def _place_time(r, value, path, label):
    """"LAX, 2026-10-16 10:00" -> ("LAX", datetime)."""
    if isinstance(value, str) and "," in value:
        place, _, when = value.rpartition(",")
        at = _stamp(r, when.strip(), path, label)
        if place.strip():
            return " ".join(place.split())[:80], at
    r.bad(path, f"{label} should be a place, a comma and a date and time, like “LAX, 2026-10-16 10:00”.")
    return "", None


def _read_travelers(r, doc):
    raw = doc.get("travelers")
    if not isinstance(raw, list) or not raw:
        r.bad(("travelers",) if "travelers" in doc else (), "Add at least one traveler under “travelers:”.")
        return ()
    if len(raw) > MAX_TRAVELERS:
        r.bad(("travelers",), f"That is more than {MAX_TRAVELERS} travelers. Keep it to the people on the booking.")
    out = []
    for i, item in enumerate(raw[:MAX_TRAVELERS]):
        path = ("travelers", i)
        item = _mapping(r, item, path, f"Traveler {i + 1}")
        if item is None:
            continue
        name = _text(r, item, "name", path, f"Traveler {i + 1}’s name", required=True, limit=40)
        email = _text(r, item, "email", path, f"{name or 'Traveler ' + str(i + 1)}’s email", limit=80)
        if email and not _EMAIL.match(email):
            r.bad(path + ("email",), f"“{email}” does not look like an email address.")
            email = ""
        age = item.get("age")
        if age is not None:
            if isinstance(age, str) and age.strip().isascii() and age.strip().isdigit() and int(age) <= 120:
                age = int(age)
            else:
                r.bad(path + ("age",), f"{name or 'Traveler ' + str(i + 1)}’s age should be a whole number from 0 to 120.")
                age = None
        if name:
            out.append(Traveler(name, email.lower(), age))
    if out and all(t.is_kid for t in out):
        r.bad(("travelers",), "Add at least one adult (a traveler without an age, or 18 or older).")
    return tuple(out)


def _read_flights(r, doc):
    raw = doc.get("flights")
    if raw is None:
        return ()
    if not isinstance(raw, list):
        r.bad(("flights",), "“flights:” should be a list with one entry per leg.")
        return ()
    if len(raw) > MAX_LEGS:
        r.bad(("flights",), f"That is more than {MAX_LEGS} flight legs.")
    out = []
    for i, item in enumerate(raw[:MAX_LEGS]):
        path = ("flights", i)
        label = f"Flight leg {i + 1}"
        item = _mapping(r, item, path, label)
        if item is None:
            continue
        airline = _text(r, item, "airline", path, f"{label}’s airline", required=True, limit=40)
        number = _text(r, item, "number", path, f"{label}’s flight number", required=True, limit=12)
        origin, dest = _airport(r, item, "from", path, f"{label}’s “from”"), _airport(r, item, "to", path, f"{label}’s “to”")
        depart = _stamp(r, item.get("depart"), path + ("depart",), f"{label}’s “depart”") if item.get("depart") is not None else None
        arrive = _stamp(r, item.get("arrive"), path + ("arrive",), f"{label}’s “arrive”") if item.get("arrive") is not None else None
        for key, got in (("depart", depart), ("arrive", arrive)):
            if item.get(key) is None:
                r.bad(path, f"{label} has no “{key}”. Add a line like “{key}: 2026-10-16 08:05”.")
        confirmation = _text(r, item, "confirmation", path, f"{label}’s confirmation", limit=20)
        seats = _text(r, item, "seats", path, f"{label}’s seats", limit=60)
        if depart and arrive and not (-1 <= (arrive.date() - depart.date()).days <= 2):
            r.bad(path + ("arrive",), f"{label} lands {abs((arrive.date() - depart.date()).days)} days from when it leaves. Check the dates.")
        if airline and number and origin and dest and depart and arrive:
            if origin == dest:
                r.bad(path, f"{label} leaves from and lands at {origin}. Check the airports.")
            else:
                out.append(Leg(airline, number, origin, dest, depart, arrive, confirmation, seats))
    out.sort(key=lambda leg: leg.depart)
    return tuple(out)


def _one_hotel(r, item, path, label):
    item = _mapping(r, item, path, label)
    if item is None:
        return None
    name = _text(r, item, "name", path, f"{label}’s name", required=True, limit=80)
    address = _text(r, item, "address", path, f"{label}’s address", required=True, limit=120)
    check_in = _stamp(r, item.get("check_in"), path + ("check_in",), f"{label}’s “check_in”", datetime.min.time().replace(hour=15)) if item.get("check_in") is not None else None
    check_out = _stamp(r, item.get("check_out"), path + ("check_out",), f"{label}’s “check_out”", datetime.min.time().replace(hour=11)) if item.get("check_out") is not None else None
    for key in ("check_in", "check_out"):
        if item.get(key) is None:
            r.bad(path, f"{label} has no “{key}”. Add a line like “{key}: 2026-10-16 15:00”.")
    if check_in and check_out and check_out <= check_in:
        r.bad(path + ("check_out",), "Check-out has to be after check-in.")
    rooms = item.get("rooms", "1")
    if rooms is None:
        rooms = "1"
    if isinstance(rooms, str) and rooms.strip().isascii() and rooms.strip().isdigit() and 1 <= int(rooms) <= 8:
        rooms = int(rooms)
    else:
        r.bad(path + ("rooms",), "“rooms” should be a whole number from 1 to 8.")
        rooms = 1
    confirmation = _text(r, item, "confirmation", path, f"{label}’s confirmation", limit=30)
    room = _text(r, item, "room", path, f"{label}’s room", limit=80)
    phone = _text(r, item, "phone", path, f"{label}’s phone", limit=30)
    if not (name and address and check_in and check_out and check_out > check_in):
        return None
    return Lodging(name, address, check_in, check_out, confirmation, room, rooms, phone)


MAX_HOTELS = 6


def _read_hotels(r, doc):
    """The hotels: one under `hotel:`, or several under `hotels:` (a list). Returned oldest check-in first."""
    if doc.get("hotel") is not None and doc.get("hotels") is not None:
        r.bad(("hotels",), "Use either “hotel:” (one hotel) or “hotels:” (a list), not both.")
        return ()
    if doc.get("hotels") is not None:
        raw = doc["hotels"]
        if not isinstance(raw, list):
            r.bad(("hotels",), "“hotels:” should be a list with one entry per hotel.")
            return ()
        if len(raw) > MAX_HOTELS:
            r.bad(("hotels",), f"That is more than {MAX_HOTELS} hotels.")
        found = [_one_hotel(r, item, ("hotels", i), f"Hotel {i + 1}") for i, item in enumerate(raw[:MAX_HOTELS])]
    elif doc.get("hotel") is not None:
        found = [_one_hotel(r, doc["hotel"], ("hotel",), "The hotel")]
    else:
        return ()
    out = sorted((h for h in found if h), key=lambda h: h.check_in)
    for a, b in zip(out, out[1:]):
        if b.check_in < a.check_out:
            r.bad(("hotels", found.index(b)) if "hotels" in doc else ("hotel",), f"{b.name} starts before {a.name} ends. Two stays cannot overlap.")
    return tuple(out)


def _read_car(r, doc):
    raw = doc.get("car")
    if raw is None:
        return None
    path = ("car",)
    item = _mapping(r, raw, path, "The car")
    if item is None:
        return None
    company = _text(r, item, "company", path, "The car company", required=True, limit=40)
    pick = drop = None
    where_p = where_d = ""
    for key in ("pickup", "dropoff"):
        if item.get(key) is None:
            r.bad(path, f"The car has no “{key}”. Add a line like “{key}: LAX, 2026-10-16 10:00”.")
    if item.get("pickup") is not None:
        where_p, pick = _place_time(r, item["pickup"], path + ("pickup",), "The car’s “pickup”")
    if item.get("dropoff") is not None:
        where_d, drop = _place_time(r, item["dropoff"], path + ("dropoff",), "The car’s “dropoff”")
    if pick and drop and drop <= pick:
        r.bad(path + ("dropoff",), "The car has to be dropped off after it is picked up.")
    confirmation = _text(r, item, "confirmation", path, "The car’s confirmation", limit=30)
    car = _text(r, item, "car", path, "The car’s type", limit=40)
    if not (company and pick and drop and drop > pick):
        return None
    return Rental(company, where_p, pick, where_d, drop, confirmation, car)


def _check_inside(r, plan_start, plan_end, legs, hotels, rental):
    """Everything has to fall on a day of the trip, so it has somewhere to show on the calendar. A red-eye may leave the evening before
    the trip starts or land the morning after it ends."""
    def inside(day):
        return plan_start <= day <= plan_end

    for i, leg in enumerate(legs):
        for key, at, lo, hi in (("depart", leg.depart, plan_start - timedelta(days=1), plan_end), ("arrive", leg.arrive, plan_start, plan_end + timedelta(days=1))):
            if not lo <= at.date() <= hi:
                r.bad(("flights", i, key), f"Flight leg {i + 1} {'leaves' if key == 'depart' else 'lands'} on {at:%b} {at.day}, which is outside your trip dates ({plan_start:%b} {plan_start.day} – {plan_end:%b} {plan_end.day}). Change “start” or “end”, or the flight.")
    for i, hotel in enumerate(hotels):
        for key, at in (("check_in", hotel.check_in), ("check_out", hotel.check_out)):
            if not inside(at.date()):
                r.bad(("hotel", key), f"{hotel.name}’s {key.replace('_', '-')} is on {at:%b} {at.day}, which is outside your trip dates. Change “start” or “end”, or the hotel.")
    if rental:
        for key, at in (("pickup", rental.pickup), ("dropoff", rental.dropoff)):
            if not inside(at.date()):
                r.bad(("car", key), f"The car {key} is on {at:%b} {at.day}, which is outside your trip dates. Change “start” or “end”, or the car.")


def parse(text) -> Parsed:
    """Read a filled-in template (the whole markdown or only the YAML). Raises ImportProblem with every problem found."""
    if not isinstance(text, str) or not text.strip():
        raise ImportProblem(["Paste your filled-in template first."])
    if len(text.encode("utf-8", "ignore")) > MAX_BYTES:
        raise ImportProblem([f"That is too long. A trip template is a page or two (at most {MAX_BYTES // 1000} KB)."])
    body, offset = _block(text)
    try:
        for event in yaml.parse(body, Loader=yaml.SafeLoader):
            if isinstance(event, yaml.AliasEvent) or (isinstance(event, yaml.NodeEvent) and getattr(event, "anchor", None)):
                raise ImportProblem([f"Line {event.start_mark.line + 1 + offset}: anchors and aliases (& and *) are not supported. Write each value out."])
        node = yaml.compose(body, Loader=yaml.SafeLoader)
    except RecursionError:
        raise ImportProblem([TOO_DEEP])
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        where = f"Line {mark.line + 1 + offset}: " if mark else ""
        what = (getattr(e, "problem", "") or "it could not be read").capitalize()
        hint = " Check the spacing: lines under a heading are indented by two spaces, and a value with a colon in it needs quotes." if mark else ""
        raise ImportProblem([f"{where}{what}.{hint}".replace("..", ".")])
    if not isinstance(node, yaml.MappingNode):
        raise ImportProblem(["That does not look like the template. Paste the block that starts with “trip:”."])
    lines = {}
    try:
        _walk(node, (), lines)
    except _TooDeep:
        raise ImportProblem([TOO_DEEP])
    r = _Reader(lines, offset)
    doc = _plain(r, node)

    trip = doc.get("trip")
    tp = ("trip",)
    title = destination = booked_on = itinerary = ""
    start = end = None
    if not isinstance(trip, dict):
        r.bad(tp if "trip" in doc else (), "The template needs a “trip:” section with a title, destination, start and end.")
    else:
        title = _text(r, trip, "title", tp, "The trip’s title", required=True, limit=60)
        destination = _text(r, trip, "destination", tp, "The trip’s destination", required=True, limit=60)
        booked_on = _text(r, trip, "booked_on", tp, "“booked_on”", limit=30) or "elsewhere"
        itinerary = _text(r, trip, "itinerary_number", tp, "The itinerary number", limit=30)
        for key in ("start", "end"):
            if trip.get(key) is None:
                r.bad(tp, f"The trip has no “{key}” date. Add a line like “{key}: 2026-10-16”.")
        start = _day(r, trip.get("start"), tp + ("start",), "The trip’s “start”") if trip.get("start") is not None else None
        end = _day(r, trip.get("end"), tp + ("end",), "The trip’s “end”") if trip.get("end") is not None else None
        if start and end:
            if end < start:
                r.bad(tp + ("end",), "The trip ends before it starts. Check “start” and “end”.")
            elif (end - start).days + 1 > MAX_DAYS:
                r.bad(tp + ("end",), f"A trip can be at most {MAX_DAYS} days long.")
    travelers = _read_travelers(r, doc)
    legs = _read_flights(r, doc)
    hotels = _read_hotels(r, doc)
    rental = _read_car(r, doc)
    notes = doc.get("notes")
    if notes is not None and not isinstance(notes, str):
        r.bad(("notes",), "“notes:” should be text. Use “notes: |” and indent the lines below it.")
        notes = ""
    notes = (notes or "").strip()
    if len(notes) > MAX_NOTES:
        r.bad(("notes",), f"The notes are too long (at most {MAX_NOTES} characters).")
        notes = notes[:MAX_NOTES]
    for key in doc:
        if key not in KNOWN:
            r.warn((str(key),), f"“{key}” is not a section GitAway uses, so it was skipped. The sections are: {', '.join(KNOWN)}.")
    zone = zones.DEFAULT
    chosen = trip.get("timezone") if isinstance(trip, dict) else None
    if chosen is not None:
        zone = zones.valid(chosen if isinstance(chosen, str) else "")
        if zone is None:
            r.bad(tp + ("timezone",), f"The trip’s time zone “{chosen}” is not one GitAway knows. Use a name like America/New_York or Europe/Paris (or delete the line).")
            zone = zones.DEFAULT
    elif isinstance(trip, dict):
        arrive = legs[_split(legs)[0]].dest if legs else ""
        zone, note = zones.resolve(arrive, destination)
        if note:
            r.warn(tp, note)
    if not (legs or hotels or rental) and not r.errors:
        r.bad((), "Add at least one of flights, a hotel or a car, or there is nothing to put on the calendar.")
    if start and end and not r.errors:
        _check_inside(r, start, end, legs, hotels, rental)
    if r.errors:
        raise ImportProblem(r.errors, r.warnings)
    return Parsed(Plan(title, destination, start, end, booked_on, itinerary, travelers, legs, hotels, rental, notes, zone), tuple(r.warnings))


# ---- the family database's copy -------------------------------------------------------------------------------------

def _iso(at):
    return at.strftime("%Y-%m-%dT%H:%M")


def to_doc(plan: Plan) -> dict:
    """The plan as plain JSON-able data (what the family database keeps)."""
    doc = {"v": 1, "trip": {"title": plan.title, "destination": plan.destination, "start": plan.start.isoformat(), "end": plan.end.isoformat(),
                            "booked_on": plan.booked_on, "itinerary": plan.itinerary, "timezone": plan.timezone},
           "travelers": [{"name": t.name, "email": t.email, "age": t.age} for t in plan.travelers],
           "flights": [{"airline": f.airline, "number": f.number, "from": f.origin, "to": f.dest, "depart": _iso(f.depart), "arrive": _iso(f.arrive),
                        "confirmation": f.confirmation, "seats": f.seats} for f in plan.legs],
           "notes": plan.notes}
    if plan.hotels:
        doc["hotels"] = [{"name": h.name, "address": h.address, "check_in": _iso(h.check_in), "check_out": _iso(h.check_out),
                          "confirmation": h.confirmation, "room": h.room, "rooms": h.rooms, "phone": h.phone} for h in plan.hotels]
    if plan.rental:
        c = plan.rental
        doc["car"] = {"company": c.company, "pickup_place": c.pickup_place, "pickup": _iso(c.pickup), "dropoff_place": c.dropoff_place,
                      "dropoff": _iso(c.dropoff), "confirmation": c.confirmation, "car": c.car}
    return doc


def from_doc(doc: dict) -> Plan:
    """The Plan a stored doc holds (trusted: it was validated when it was saved)."""
    at = datetime.fromisoformat
    t = doc["trip"]
    hs, c = doc.get("hotels", [doc["hotel"]] if doc.get("hotel") else []), doc.get("car")
    return Plan(
        t["title"], t["destination"], date.fromisoformat(t["start"]), date.fromisoformat(t["end"]), t["booked_on"], t.get("itinerary", ""),
        tuple(Traveler(x["name"], x.get("email", ""), x.get("age")) for x in doc["travelers"]),
        tuple(Leg(f["airline"], f["number"], f["from"], f["to"], at(f["depart"]), at(f["arrive"]), f.get("confirmation", ""), f.get("seats", "")) for f in doc.get("flights", [])),
        tuple(Lodging(h["name"], h["address"], at(h["check_in"]), at(h["check_out"]), h.get("confirmation", ""), h.get("room", ""), h.get("rooms", 1), h.get("phone", "")) for h in hs),
        Rental(c["company"], c["pickup_place"], at(c["pickup"]), c["dropoff_place"], at(c["dropoff"]), c.get("confirmation", ""), c.get("car", "")) if c else None,
        doc.get("notes", ""), t.get("timezone") or zones.DEFAULT)


# ---- what the calendar and the rides read ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ImportedTrip(catalog.TripSearch):
    """The catalog's TripSearch for an imported trip: real dates and party. `name` is the title the family gave it; `tz` its time zone (F-057)."""
    name: str = ""
    tz: str = zones.DEFAULT

    @property
    def title(self) -> str:
        return self.name or super().title


def trip_search(plan: Plan) -> ImportedTrip:
    arrive = plan.arrive_leg
    airports = (arrive.dest,) if arrive else ()
    return ImportedTrip(plan.home, plan.home, plan.destination, airports, plan.start, plan.end, max(plan.adults, 1), plan.kid_ages, plan.title, plan.timezone)


@dataclass(frozen=True)
class ImportedFlight:
    """Stands in for a catalog flight Offer: where the family lands, when, and when they fly home, with the real dates."""
    id: str
    name: str
    airport: str          # where the arrival leg lands
    arrive_min: int       # minutes after midnight, local
    arrive_date: date
    back_depart_min: int | None
    back_date: date | None
    back_airport: str = ""
    kind: str = "flight"
    headline: str = ""
    depart_min: int = 0
    back_arrive_min: int = 0


@dataclass(frozen=True)
class ImportedStay:
    """Stands in for a catalog stay Offer: the hotel, with its address (the rides go to it)."""
    id: str
    name: str
    address: str
    kind: str = "stay"
    headline: str = ""


@dataclass(frozen=True)
class ImportedCar:
    id: str
    name: str
    kind: str = "car"


def _minutes(at: datetime) -> int:
    return at.hour * 60 + at.minute


def flight_offer(plan: Plan, offer_id: str) -> ImportedFlight | None:
    """The arrival at the destination and the departure home, or None with no flights."""
    a, d = plan.arrive_leg, plan.depart_leg
    if a is None:
        return None
    return ImportedFlight(offer_id, a.name, a.dest, _minutes(a.arrive), a.arrive.date(), _minutes(d.depart) if d else None, d.depart.date() if d else None,
                          d.origin if d else "", depart_min=_minutes(a.depart), back_arrive_min=_minutes(d.arrive) if d else 0)


def hotel_for(plan: Plan, leg=None):
    """The hotel for a ride: the arrival goes to the hotel that starts on the landing day (else the first), the departure leaves the one that
    ends on the flight-home day (else the last). With no leg, the first."""
    if not plan.hotels:
        return None
    if leg == "arrive":
        a = plan.arrive_leg
        return next((h for h in plan.hotels if a and h.check_in.date() == a.arrive.date()), plan.hotels[0])
    if leg == "depart":
        d = plan.depart_leg
        return next((h for h in reversed(plan.hotels) if d and h.check_out.date() == d.depart.date()), plan.hotels[-1])
    return plan.hotels[0]


def stay_offer(plan: Plan, offer_id: str, leg=None) -> ImportedStay | None:
    h = hotel_for(plan, leg)
    return ImportedStay(offer_id, h.name, h.address) if h else None


def car_offer(plan: Plan, offer_id: str) -> ImportedCar | None:
    return ImportedCar(offer_id, plan.rental.company) if plan.rental else None


@dataclass(frozen=True)
class Spec:
    """One calendar block a plan puts down: its id ("b-out" is the arrival, "b-back" the flight home), what it is, and the thing itself."""
    id: str
    kind: str   # leg | checkin | checkout | pickup | dropoff
    item: object


def block_specs(plan: Plan) -> list:
    out = []
    arrive, depart = plan.arrive_leg, plan.depart_leg
    for i, leg in enumerate(plan.legs):
        out.append(Spec("b-out" if leg is arrive else "b-back" if leg is depart else f"b-leg{i + 1}", "leg", leg))
    for i, h in enumerate(plan.hotels):  # the first hotel keeps the ids the demo's stay has
        out += [Spec("b-in" if i == 0 else f"b-hin{i + 1}", "checkin", h), Spec("b-out2" if i == 0 else f"b-hout{i + 1}", "checkout", h)]
    if plan.rental:
        out += [Spec("b-car-pick", "pickup", plan.rental), Spec("b-car-drop", "dropoff", plan.rental)]
    return out


def when_text(at: datetime) -> str:
    h = at.hour % 12 or 12
    return f"{at:%a %b} {at.day}, {h}:{at.minute:02d} {'AM' if at.hour < 12 else 'PM'}"


def detail_rows(spec: Spec, plan: Plan) -> tuple:
    """(title, [(label, value), ...]) of one booked block, with its confirmation number. Only ever drawn for a signed-in family member."""
    x = spec.item
    if spec.kind == "leg":
        rows = [("Flight", x.name), ("From", x.origin), ("To", x.dest), ("Leaves", when_text(x.depart)), ("Arrives", when_text(x.arrive))]
        rows += [("Seats", x.seats)] if x.seats else []
        return f"{x.name} · {x.origin} → {x.dest}", rows + [("Confirmation", x.confirmation or "none given")]
    if spec.kind in ("checkin", "checkout"):
        rows = [("Hotel", x.name), ("Address", x.address), ("Check in", when_text(x.check_in)), ("Check out", when_text(x.check_out))]
        rows += [("Room", x.room)] if x.room else []
        rows += [("Rooms", str(x.rooms))] if x.rooms != 1 else []
        rows += [("Phone", x.phone)] if x.phone else []
        return x.name, rows + [("Confirmation", x.confirmation or "none given")]
    which = "pickup" if spec.kind == "pickup" else "dropoff"
    rows = [("Company", x.company), ("Pick up", f"{x.pickup_place} · {when_text(x.pickup)}"), ("Drop off", f"{x.dropoff_place} · {when_text(x.dropoff)}")]
    rows += [("Car", x.car)] if x.car else []
    return f"{x.company} car {which}", rows + [("Confirmation", x.confirmation or "none given")]
