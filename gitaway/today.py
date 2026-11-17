"""Today: the next thing, on the day (F-287, D-926..D-930, docs/briefs/trip-day.md). The logic of /trip/today and of the card on the planner; the page is gitaway/pages/today.py.

    state(trip, now)      "before" | "travel" | "during" | "after": where the trip is. A travel day has a flight in the air or a stay to check in to or out of
    near(trip, now)       True within NEAR_DAYS of the start and until the trip ends: the planner shows its Today card then
    build(trip, now, drives=)  -> Today   what the day shows, in order, for the family's `trip` at `now`
    from_booking(session, b)   -> Trip    the family's booking (a pasted one, or the sample's) as plain facts

Pure and dated: `now` is a naive local time at the trip, so a test passes one. Nothing is invented: a phone number, an address, a confirmation code or an airline's check-in page is
carried only when the booking or a table of the airline's own pages has it; the "leave by" time is an estimate and says so (the drive from airportdrive.py, the airport buffer here).
The weather, the Uber link and the page's words are the page's; this module only says what the day holds.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from gitaway import catalog, tripcal as cal, tripday as td, zones

NEAR_DAYS = 3
CHECKIN_OPENS = timedelta(hours=24)       # what the airlines GitAway links to say: online check-in opens a day before
BUFFER = {"domestic": td.DOMESTIC_EARLY, "international": td.INTERNATIONAL_EARLY}      # minutes to be at the airport before a departure
# The airlines' own check-in pages, only those a person has opened and found (2026-11-17). An airline not listed has no link: nothing is guessed.
CHECKIN_PAGES = {"delta": "https://www.delta.com/us/en/check-in/overview", "southwest": "https://www.southwest.com/air/check-in/index.html"}


@dataclass(frozen=True)
class Flight:
    airline: str
    number: str
    origin: str
    dest: str
    depart: datetime
    arrive: datetime
    confirmation: str = ""

    @property
    def name(self) -> str:
        return f"{self.airline} {self.number}".strip()


@dataclass(frozen=True)
class Stay:
    name: str
    check_in: datetime
    check_out: datetime
    address: str = ""
    area: str = ""            # the sample stay's neighbourhood, where it has no street address
    confirmation: str = ""
    phone: str = ""
    booked_on: str = ""


@dataclass(frozen=True)
class Plan:
    day: date
    start: int                # minutes after midnight
    end: int
    title: str


@dataclass(frozen=True)
class Trip:
    title: str
    place: str                # the destination: "Los Angeles"
    start: date
    end: date
    flights: tuple = ()
    stays: tuple = ()
    plans: tuple = ()
    home: str = ""            # the town the trip leaves from, when the booking says (the sample's), else ""
    sample: bool = False      # the showcase's own sample trip: everything on it is sample data and the page says so


@dataclass(frozen=True)
class LeaveBy:
    at: datetime
    drive: int                # minutes by car
    buffer: int               # minutes at the airport
    town: str                 # where the drive starts

    def words(self) -> str:
        h, m = divmod(self.buffer, 60)
        buf = f"{h} h" + (f" {m} min" if m else "") if h else f"{m} min"
        return f"An estimate: {self.drive} min by car from {self.town}, plus {buf} at the airport."


@dataclass(frozen=True)
class FlightItem:
    flight: Flight
    at: datetime
    past: bool
    opens: datetime           # when online check-in opens
    checkin_url: str          # the airline's page, "" when we have none
    leave: LeaveBy | None


@dataclass(frozen=True)
class StayItem:
    stay: Stay
    at: datetime              # the moment that puts it in the day: the check-in, the check-out, or the start of the day
    past: bool
    phase: str                # checkin | checkout | staying


@dataclass(frozen=True)
class Today:
    state: str                # before | travel | during | after
    day: int                  # the trip day's index (0 on the first), clamped into the trip
    to_go: int                # days until the start (0 once under way)
    items: tuple = ()         # travel day: FlightItem and StayItem in time order, those not yet past first
    flights: tuple = ()       # before: FlightItem for each flight, so the card can say when check-in opens
    stay: Stay | None = None  # the stay that covers today (during and travel), or the first one before
    plans: tuple = ()         # during: today's Plans in time order


def _date(now) -> date:
    return now.date() if isinstance(now, datetime) else now


def _flies(trip, d) -> bool:
    return any(f.depart.date() == d for f in trip.flights)


def _stays(trip, d) -> bool:
    return any(s.check_in.date() == d or s.check_out.date() == d for s in trip.stays)


def state(trip, now) -> str:
    d = _date(now)
    if d < trip.start:
        return "before"
    if d > trip.end:
        return "after"
    return "travel" if _flies(trip, d) or _stays(trip, d) else "during"


def near(trip, now) -> bool:
    d = _date(now)
    return trip.start - timedelta(days=NEAR_DAYS) <= d <= trip.end


def buffer_for(flight) -> int:
    """Minutes to be at the airport before `flight`: the domestic one inside the US, the international one when either end is not."""
    zs = (zones.AIRPORTS.get(flight.origin), zones.AIRPORTS.get(flight.dest))
    return BUFFER["domestic" if all(z in zones._US_ZONES for z in zs) else "international"]


def checkin_url(flight) -> str:
    """The airline's own check-in page, or "" when GitAway does not have it."""
    low = flight.airline.lower()
    return next((url for key, url in CHECKIN_PAGES.items() if key in low), "")


def leave_by(flight, drive, town) -> LeaveBy | None:
    """When to leave for `flight`, as an estimate: its departure less `drive` minutes (airportdrive's, from `town`) and the airport buffer; None without a drive."""
    if not drive or not town:
        return None
    buf = buffer_for(flight)
    return LeaveBy(flight.depart - timedelta(minutes=drive + buf), drive, buf, town)


def drive_town(trip, flight, stay=None) -> str:
    """Where the drive to `flight`'s airport starts: the trip's home town for the flight that leaves home ("" when the booking does not say), else the stay's address or the destination."""
    if flight == min(trip.flights, key=lambda f: f.depart):
        return trip.home
    return stay.address if stay and stay.address else trip.place


def _flight_item(trip, f, now, drives) -> FlightItem:
    drive = drives.get(f.origin)
    stay = next((s for s in trip.stays if s.check_in.date() <= f.depart.date() <= s.check_out.date()), None)
    return FlightItem(f, f.depart, f.depart <= now, f.depart - CHECKIN_OPENS, checkin_url(f), leave_by(f, drive, drive_town(trip, f, stay)))


def _stay_item(s, d, now) -> StayItem:
    if s.check_in.date() == d:
        return StayItem(s, s.check_in, s.check_in <= now, "checkin")
    if s.check_out.date() == d:
        return StayItem(s, s.check_out, s.check_out <= now, "checkout")
    return StayItem(s, datetime.combine(d, datetime.min.time()), False, "staying")


def build(trip, now, drives=None) -> Today:
    """What the day shows. `drives`: {departure airport: minutes by car}, the airportdrive answers the page asked for (none, no leave-by time)."""
    drives = drives or {}
    d = _date(now)
    st = state(trip, now)
    day = max(0, min((trip.end - trip.start).days, (d - trip.start).days))
    to_go = max(0, (trip.start - d).days)
    covering = next((s for s in trip.stays if s.check_in.date() <= d <= s.check_out.date()), None)
    first = trip.stays[0] if trip.stays else None
    if st == "before":
        return Today(st, 0, to_go, flights=tuple(_flight_item(trip, f, now, drives) for f in sorted(trip.flights, key=lambda f: f.depart)), stay=first)
    if st == "after":
        return Today(st, day, 0)
    stay_here = [_stay_item(s, d, now) for s in trip.stays if s.check_in.date() <= d <= s.check_out.date()]
    if st == "during":
        plans = tuple(sorted((p for p in trip.plans if p.day == d), key=lambda p: (p.start, p.title)))
        return Today(st, day, 0, stay=covering, plans=plans)
    flights = [_flight_item(trip, f, now, drives) for f in trip.flights if f.depart.date() == d]
    items = sorted([*flights, *[i for i in stay_here if i.phase != "staying"]], key=lambda i: (i.past, i.at))
    return Today(st, day, 0, items=tuple(items), stay=covering)


# ---- the booking as plain facts ---------------------------------------------------------------------------------------------------------

def _minutes(d, m) -> datetime:
    return datetime.combine(d, datetime.min.time()) + timedelta(minutes=m)


def from_booking(session, b, acts=None) -> Trip:
    """The open trip's booking `b` as a Trip: a pasted booking's legs and hotels as written, the sample's flight and stay from the catalog (labelled sample). `acts`: the family's plans."""
    t = cal.trip("", b)
    plans = tuple(Plan(t.depart + timedelta(days=a.day), a.start, a.end, a.title) for a in (acts if acts is not None else cal.activities(session)))
    if cal.is_imported(b):
        p = cal.plan_of(b)
        flights = tuple(Flight(x.airline, x.number, x.origin, x.dest, x.depart, x.arrive, x.confirmation) for x in p.legs)
        stays = tuple(Stay(h.name, h.check_in, h.check_out, h.address, "", h.confirmation, h.phone, cal.booked_on(p, h)) for h in p.hotels)
        return Trip(p.title, p.destination, p.start, p.end, flights, stays, plans)
    flight, stay = cal.flight_of(b), cal.stay_of(b)
    sample = bool(b) and catalog.SAMPLE_TRIP == t
    flights = ()
    if flight:
        airline, _, number = flight.name.rpartition(" ")
        flights = (Flight(airline, number, t.origin, flight.airport, _minutes(t.depart, flight.depart_min), _minutes(t.depart, flight.arrive_min)),
                   Flight(airline, number, flight.airport, t.origin, _minutes(t.return_, flight.back_depart_min), _minutes(t.return_, flight.back_arrive_min)))
    stays = (Stay(stay.name, _minutes(t.depart, cal.CHECK_IN), _minutes(t.return_, cal.CHECK_OUT), area=stay.headline),) if stay else ()
    return Trip(t.title, t.destination_name, t.depart, t.return_, flights, stays, plans, home=t.origin_name, sample=sample)


def local_now(zone) -> datetime:
    """The clock at the trip, as a naive datetime: the day is `catalog.today_in(zone)` (the app's one "today", which tests pin), the time the zone's own."""
    return datetime.combine(catalog.today_in(zone), catalog.now_utc().astimezone(ZoneInfo(zone or zones.DEFAULT)).time().replace(tzinfo=None))
