"""Schedule an Uber, simulated faithfully (F-038). Research: docs/research/uber-api.md.

The shape follows Uber's Guest Rides API: an estimates call returns products with a `fare_id`, a price and an ETA; creating a
trip takes the guest (name and phone), pickup, dropoff, `product_id`, `fare_id` and `scheduling.pickup_time` (ms since the
epoch); a trip can be cancelled; and its status uses the documented names (scheduled, processing, accepted, arriving,
in_progress, completed, rider_canceled), which the screens turn into friendly words. The airport-to-hotel leg is a Reserve-style
booking (airport pickups need Reserve); the hotel-to-airport leg is an ordinary scheduled ride.

THE SEAM. `RideProvider` is the interface (`estimates`, `schedule`, `status`, `cancel`). The screens talk only to `provider()`,
which picks the implementation from `UBER_MODE` ("simulated" is the only one for now). A real Uber client implements the same four
methods and is returned from `provider()` once API access is granted. `SimulatedUber` is deterministic: nothing here calls out,
nothing is booked, and a guest's phone number stays in the family's own database.

STORAGE. `list_rides`, `get_ride`, `save_ride`, `cancel_ride` and `step_ride` keep the rides in the family's database (the `rides`
table, F-040): they are the only code that touches it. A ride belongs to the family and to a set of picks (`key`), so every member
sees it on any trip booked with those picks. Each row holds the compact dict `to_dict` makes. The rider's phone number is
stored there too, private to the family.
"""

import hashlib
import json
import math
import os
import re
import uuid
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
from typing import Protocol
from urllib.parse import quote
from zoneinfo import ZoneInfo

from fh_saas.utils_sql import delete_record, insert_only, update_record

from gitaway import catalog, familydb, session as ses

TZ = ZoneInfo("America/Los_Angeles")
MODES = ("simulated",)
SIMULATED_LABEL = "Simulated: no real ride is booked"
MIN_LEAD = timedelta(minutes=5)
MAX_LEAD = {"SCHEDULED": timedelta(days=30), "RESERVE": timedelta(days=90)}  # a normal scheduled ride, and Uber Reserve
DEMO_LEAD = timedelta(days=7)
MAX_RIDES = 40  # a family-wide backstop; each trip has at most one live ride per leg
MAX_NAME = 30
LEGS = ("arrive", "depart")


class RideError(ValueError):
    """A ride the demo refuses; the message is fit to show the traveler."""


def now(demo=False):
    """The clock the simulation follows: real Los Angeles time. The sample trip's rides (`demo`) follow a fixed clock instead, noon a week
    before departure, so the demo never rots; there the Step control moves a ride on."""
    if demo:
        return datetime.combine(catalog.SAMPLE_TRIP.depart - DEMO_LEAD, time(12, 0), tzinfo=TZ)
    return datetime.now(TZ)


# ---- places and legs ----------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Place:
    name: str
    address: str
    lat: float
    lng: float
    area: str  # the airport code, or the rides table's area ("Santa Monica", ..., "city")


AIRPORTS = {
    "LAX": Place("Los Angeles International Airport (LAX)", "1 World Way, Los Angeles, CA 90045", 33.9416, -118.4085, "LAX"),
    "BUR": Place("Hollywood Burbank Airport (BUR)", "2627 N Hollywood Way, Burbank, CA 91505", 34.2007, -118.3590, "BUR"),
}
AREAS = {
    "Santa Monica": (34.0195, -118.4912, "Santa Monica, CA"), "Venice": (33.9850, -118.4695, "Venice, Los Angeles, CA"),
    "Downtown": (34.0407, -118.2468, "Downtown Los Angeles, CA"), "city": (34.0522, -118.2437, "Los Angeles, CA"),
}
CITY_CENTRE = "Los Angeles city centre"


def _hotel(airport, stay_id):
    """The dropoff or pickup place for a stay id (or the city centre when there is none)."""
    stay = catalog.offer(stay_id) if stay_id else None
    area = catalog.ride_area(airport, stay)
    lat, lng, address = AREAS[area]
    return Place(stay.name if stay else CITY_CENTRE, address, lat, lng, area)


def imported_hotel(name, address) -> Place:
    """The hotel of an imported trip (F-042): its own name and address; the map point is the city centre (nothing here looks addresses up)."""
    lat, lng, _ = AREAS["city"]
    return Place(name, address, lat, lng, "city")


def _imported_hotel_of(plan) -> tuple:
    """(name, address) of the hotel end of `plan` when it is an imported trip's hotel, else ()."""
    if not plan.stay_id.startswith("imp-"):
        return ()
    place = plan.dropoff if plan.kind == "arrive" else plan.pickup
    return (place.name, place.address)


@dataclass(frozen=True)
class LegPlan:
    """One leg of the trip as a ride: where, when and for how many. Everything an estimates call needs."""
    kind: str  # arrive | depart
    airport: str
    stay_id: str  # "" for the city centre
    pickup: Place
    dropoff: Place
    pickup_time: datetime
    party: int
    minutes: int  # on the road
    advance: str  # RESERVE (the airport pickup) | SCHEDULED
    demo: bool = False  # the sample trip: it follows the fixed demo clock

    @property
    def pickup_ms(self) -> int:
        return int(self.pickup_time.timestamp() * 1000)

    @property
    def route(self) -> str:
        return f"{self.pickup.name} → {self.dropoff.name}"

    @property
    def short_route(self) -> str:
        """"LAX → The Tidewater", as the calendar block says it."""
        a, b = (self.pickup, self.dropoff)
        return f"{a.area if a.area in AIRPORTS else a.name} → {b.area if b.area in AIRPORTS else b.name}"


def leg_plan(kind, flight, stay, trip) -> LegPlan:
    """The arrival (landing + the curb buffer) or departure (flight - airport buffer - drive time) ride for a flight and a stay (None: the city centre)."""
    if kind not in LEGS:
        raise RideError("Pick the arrival or the departure ride.")
    airport = flight.airport
    if airport not in AIRPORTS:
        raise RideError("GitAway can only schedule rides to and from Los Angeles airports for now.")
    area = catalog.ride_area(airport, stay)
    _dollars, minutes = catalog.ride_base(airport, area, kind)
    imported = stay is not None and hasattr(stay, "address")  # an imported trip's hotel (F-042)
    hotel = imported_hotel(stay.name, stay.address) if imported else _hotel(airport, stay.id if stay else "")
    if kind == "arrive":
        day, at = getattr(flight, "arrive_date", None) or trip.depart, flight.arrive_min + catalog.CURB_MINUTES
        pickup, dropoff = AIRPORTS[airport], hotel
    else:
        if flight.back_depart_min is None:
            raise RideError("There is no flight home on this trip, so there is no departure ride to schedule.")
        day, at = getattr(flight, "back_date", None) or trip.return_, (flight.back_depart_min - catalog.AIRPORT_BUFFER - minutes) // 5 * 5
        pickup, dropoff = hotel, AIRPORTS[airport]
    if at >= 24 * 60:  # a landing at 11:40 PM plus the curb time is after midnight
        day, at = day + timedelta(days=1), at - 24 * 60
    elif at < 0:  # a flight at 1 AM: the ride is the evening before
        day, at = day - timedelta(days=1), at + 24 * 60
    when = datetime.combine(day, time(at // 60, at % 60), tzinfo=TZ)
    return LegPlan(kind, airport, stay.id if stay else "", pickup, dropoff, when, trip.travelers, minutes, "RESERVE" if kind == "arrive" else "SCHEDULED", trip == catalog.SAMPLE_TRIP)


# ---- estimates ----------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Product:
    key: str
    name: str
    blurb: str
    seats: int
    percent: int  # of the standard fare
    eta: int  # minutes until a driver could reach the pickup


PRODUCTS = (
    Product("x", "UberX", "Affordable everyday rides", 4, 100, 4),
    Product("c", "Comfort", "Newer cars with extra legroom", 4, 125, 6),
    Product("xl", "UberXL", "Fits bigger groups and more bags", catalog.XL_SEATS, catalog._XL_PERCENT, 8),
)


def product(key) -> Product:
    found = next((p for p in PRODUCTS if p.key == key), None)
    if not found:
        raise RideError("Pick one of the rides.")
    return found


@dataclass(frozen=True)
class Estimate:
    """One product from an estimates call (Guest Rides: product_estimates[]). `cents` is for all the cars the party needs."""
    key: str
    name: str
    blurb: str
    seats: int
    product_id: str
    fare_id: str
    cents: int
    cars: int
    fits: bool
    note: str
    trip_minutes: int
    pickup_eta_min: int
    advance: str  # advance_booking_type: RESERVE | SCHEDULED

    @property
    def display(self) -> str:
        return catalog.money(self.cents)


def _product_id(key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"gitaway-simulated-uber:{key}"))


def _fare_id(kind, pickup_ms, airport, area, key, cents):
    """A fare id is bound to the quote (product, leg, time, places, price): a changed quote makes the old id stale."""
    return "fare_" + hashlib.sha256(f"{key}|{kind}|{pickup_ms}|{airport}|{area}|{cents}".encode()).hexdigest()[:10]


def _fare_for(plan: LegPlan, key, cents):
    return _fare_id(plan.kind, plan.pickup_ms, plan.airport, (plan.dropoff if plan.kind == "arrive" else plan.pickup).area, key, cents)


def _price(plan: LegPlan, p: Product):
    """(cars, cents, fits) for product `p` on `plan`: whole dollars from the rides table, like the workspace rides card."""
    cars = math.ceil(plan.party / p.seats)
    fits = cars == 1 or p.key == "xl"  # only the XL goes in several cars; a standard car that cannot seat the party is not offered
    dollars, _ = catalog.ride_base(plan.airport, plan.pickup.area if plan.kind == "depart" else plan.dropoff.area, plan.kind)
    return cars, (dollars * p.percent // 100) * 100 * cars, fits


# ---- the interface ------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Guest:
    first: str
    last: str
    phone: str  # E.164

    @property
    def name(self) -> str:
        return f"{self.first} {self.last}"

    @property
    def phone_shown(self) -> str:
        p = self.phone
        return f"+1 ({p[2:5]}) {p[5:8]}-{p[8:]}" if p.startswith("+1") and len(p) == 12 else p


@dataclass(frozen=True)
class ScheduleRequest:
    """What creating a trip needs (Guest Rides: POST /v1/guests/trips): the leg, the guest, `product_id`, `fare_id`, and our own ids."""
    plan: LegPlan
    guest: Guest
    product_id: str
    fare_id: str
    ride_id: str  # our short id, "r1"
    key: str  # which booked picks the ride belongs to (see context_key)


@dataclass(frozen=True)
class RideRecord:
    """A scheduled ride, as GitAway keeps it. `step` is the furthest stage the sandbox-style Step control has reached."""
    id: str
    request_id: str
    key: str
    leg: str
    product: str
    product_id: str
    fare_id: str
    cents: int
    cars: int
    pickup_time: datetime
    minutes: int
    party: int
    airport: str
    stay_id: str
    guest: Guest
    step: int = 0
    canceled: bool = False
    demo: bool = False
    hotel: tuple = ()  # (name, address) of an imported trip's hotel (F-042); empty for a catalog stay, which `stay_id` names

    @property
    def plan(self) -> LegPlan:
        hotel = imported_hotel(*self.hotel) if self.hotel else _hotel(self.airport, self.stay_id)
        out, back = (AIRPORTS[self.airport], hotel) if self.leg == "arrive" else (hotel, AIRPORTS[self.airport])
        return LegPlan(self.leg, self.airport, self.stay_id, out, back, self.pickup_time, self.party, self.minutes,
                       "RESERVE" if self.leg == "arrive" else "SCHEDULED", self.demo)

    @property
    def product_name(self) -> str:
        return product(self.product).name


STAGES = ("scheduled", "processing", "accepted", "arriving", "in_progress", "completed")
TIMELINE = (("scheduled", "Scheduled"), ("accepted", "Driver assigned"), ("arriving", "Arriving"), ("in_progress", "On trip"), ("completed", "Completed"))
_TIMELINE_AT = (0, 0, 1, 2, 3, 4)  # the timeline step each stage shows on
LABELS = {"scheduled": "Scheduled", "processing": "Finding a driver", "accepted": "Driver assigned", "arriving": "Arriving",
          "in_progress": "On trip", "completed": "Completed", "rider_canceled": "Cancelled"}
STEP_ACTIONS = {"accepted": "ACCEPT", "arriving": "ARRIVED", "in_progress": "BEGIN_TRIP", "completed": "DROPOFF"}  # the sandbox's driver-state calls
# minutes before the pickup that each stage starts (Uber dispatches ahead so the driver arrives at the pickup time)
_STARTS = ((1, 30), (2, 20), (3, 5))
_DRIVERS = (("Marisol", "Toyota Camry", "Silver"), ("Dev", "Honda Accord", "Black"), ("Tomasz", "Hyundai Sonata", "White"),
            ("Aisha", "Toyota Prius", "Blue"), ("Luis", "Kia K5", "Gray"), ("Priya", "Tesla Model 3", "White"))


@dataclass(frozen=True)
class RideStatus:
    name: str  # the documented status: scheduled, processing, accepted, arriving, in_progress, completed, rider_canceled
    label: str  # the friendly words
    step: int  # the timeline step (0-4); -1 once cancelled
    terminal: bool
    driver: str | None = None
    vehicle: str | None = None
    plate: str | None = None
    can_cancel: bool = False
    can_step: bool = False
    next_action: str = ""  # the sandbox call the Step control makes next


class RideProvider(Protocol):
    """Everything the screens need from Uber. A real client implements these four; `advance` is the sandbox's driver-state control
    and only the simulator offers it (`can_step`)."""

    def estimates(self, plan: LegPlan) -> tuple[Estimate, ...]:
        """Products with price, ETA and ids for a leg (Guest Rides: POST /v1/guests/trips/estimates)."""

    def schedule(self, req: ScheduleRequest) -> RideRecord:
        """Create the trip for the guest at `plan.pickup_time` (POST /v1/guests/trips). Raises RideError."""

    def status(self, record: RideRecord, at: datetime | None = None) -> RideStatus:
        """Where the trip is (GET /v1/guests/trips/{request_id})."""

    def cancel(self, record: RideRecord, at: datetime | None = None) -> RideRecord:
        """Cancel it (DELETE /v1/guests/trips/{request_id}). Raises RideError."""


class SimulatedUber:
    """Uber, deterministic and offline. The status follows the clock relative to the pickup time, and `advance` moves a ride on
    by hand (the sandbox's ACCEPT, ARRIVED, BEGIN_TRIP, DROPOFF) so it can be demoed without waiting."""

    can_step = True

    def estimates(self, plan: LegPlan) -> tuple[Estimate, ...]:
        out = []
        for p in PRODUCTS:
            cars, cents, fits = _price(plan, p)
            note = "" if fits and cars == 1 else f"{cars} cars for your group of {plan.party}" if fits else f"Seats {p.seats}. Your group of {plan.party} needs an XL."
            out.append(Estimate(p.key, p.name, p.blurb, p.seats, _product_id(p.key), _fare_for(plan, p.key, cents), cents, cars if fits else 0, fits, note,
                                plan.minutes, p.eta, plan.advance))
        return tuple(out)

    def schedule(self, req: ScheduleRequest) -> RideRecord:
        plan = req.plan
        match = next((e for e in self.estimates(plan) if e.product_id == req.product_id), None)
        if not match:
            raise RideError("Pick one of the rides.")
        if not match.fits:
            raise RideError(f"{match.name} seats {match.seats}. Your group of {plan.party} needs an XL.")
        if match.fare_id != req.fare_id:  # Uber answers 409 when the quoted fare is gone: quote again
            raise RideError("That price has changed. Choose a ride again to get a fresh price.")
        lead = plan.pickup_time - now(plan.demo)
        if lead < MIN_LEAD:
            raise RideError("Pick a time at least 5 minutes from now. That pickup is too soon or has passed.")
        if lead > MAX_LEAD[plan.advance]:
            days = MAX_LEAD[plan.advance].days
            raise RideError(f"Uber takes bookings up to {days} days ahead for this kind of ride. Try again closer to {plan.pickup_time:%b} {plan.pickup_time.day}.")
        request_id = "sim_" + hashlib.sha256(f"{req.key}|{req.ride_id}|{plan.kind}|{plan.pickup_ms}".encode()).hexdigest()[:12]
        key = next(p.key for p in PRODUCTS if _product_id(p.key) == req.product_id)
        return RideRecord(req.ride_id, request_id, req.key, plan.kind, key, req.product_id, req.fare_id, match.cents, match.cars, plan.pickup_time,
                          plan.minutes, plan.party, plan.airport, plan.stay_id, req.guest, demo=plan.demo, hotel=_imported_hotel_of(plan))

    def _stage(self, r: RideRecord, at) -> int:
        at = at or now(r.demo)
        by_clock = 0
        if at >= r.pickup_time + timedelta(minutes=r.minutes):
            by_clock = 5
        elif at >= r.pickup_time:
            by_clock = 4
        else:
            for stage, before in _STARTS:
                if at >= r.pickup_time - timedelta(minutes=before):
                    by_clock = stage
        return max(by_clock, r.step)

    def status(self, record: RideRecord, at: datetime | None = None) -> RideStatus:
        if record.canceled:
            return RideStatus("rider_canceled", LABELS["rider_canceled"], -1, True)
        stage = self._stage(record, at)
        name = STAGES[stage]
        driver = vehicle = plate = None
        if stage >= 2:
            who = int(hashlib.sha256(record.request_id.encode()).hexdigest(), 16)
            driver, car, color = _DRIVERS[who % len(_DRIVERS)]
            vehicle = f"{color} {car}"
            plate = f"{who % 9 + 1}{chr(65 + who // 9 % 26)}{chr(65 + who // 234 % 26)}{chr(65 + who // 6084 % 26)}{who // 158184 % 900 + 100}"
        nxt = STAGES[2 if stage < 2 else stage + 1] if stage < 5 else ""
        return RideStatus(name, LABELS[name], _TIMELINE_AT[stage], stage == 5, driver, vehicle, plate, can_cancel=stage < 3, can_step=stage < 5,
                          next_action=STEP_ACTIONS.get(nxt, ""))

    def cancel(self, record: RideRecord, at: datetime | None = None) -> RideRecord:
        if record.canceled:
            raise RideError("This ride is already cancelled.")
        if self._stage(record, at) >= 3:
            raise RideError("Your driver is arriving or has arrived, so this ride can't be cancelled.")
        return replace(record, canceled=True)

    def advance(self, record: RideRecord, at: datetime | None = None) -> RideRecord:
        """The Step control: the next sandbox driver action (ACCEPT, ARRIVED, BEGIN_TRIP, DROPOFF)."""
        if record.canceled:
            raise RideError("This ride is cancelled, so there is nothing to step.")
        stage = self._stage(record, at)
        if stage >= 5:
            raise RideError("This ride is finished.")
        return replace(record, step=2 if stage < 2 else stage + 1)


def provider(mode=None) -> RideProvider:
    """The ride provider for `UBER_MODE` ("simulated", the default). A real Uber client is added here once API access is granted."""
    mode = mode or os.environ.get("UBER_MODE", "simulated")
    if mode == "simulated":
        return SimulatedUber()
    raise RideError(f"UBER_MODE={mode} is not available. Use UBER_MODE=simulated.")


# ---- the guest ----------------------------------------------------------------------------------------------------

def _name(value, which):
    value = " ".join((value or "").split())
    if not value or len(value) > MAX_NAME or not value[0].isalpha() or not all(c.isalpha() or c in " -'" for c in value):
        raise RideError(f"Enter the rider's {which} name (letters only, up to {MAX_NAME}).")
    return value


def phone_e164(raw):
    """A plausible mobile number as E.164 ("+13105550123"), or None. Ten digits (or a leading 1) mean the US; other countries need a +."""
    raw = (raw or "").strip()
    if not raw or not re.fullmatch(r"[0-9 ().+-]+", raw):
        return None
    digits = re.sub(r"\D", "", raw)
    if raw.startswith("+"):
        pass
    elif len(digits) == 10:
        digits = "1" + digits
    elif not (len(digits) == 11 and digits[0] == "1"):
        return None
    if not 8 <= len(digits) <= 15 or digits[0] == "0" or len(set(digits[1:])) == 1:
        return None
    if digits[0] == "1" and (len(digits) != 11 or digits[1] in "01" or digits[4] in "01"):  # US numbers: area code and exchange start 2 to 9
        return None
    return "+" + digits


def validate_guest(first, last, phone) -> Guest:
    """The rider Uber texts the ride link to. Raises RideError with a message fit to show. The phone number stays in the session."""
    first, last = _name(first, "first"), _name(last, "last")
    e164 = phone_e164(phone)
    if not e164:
        raise RideError("Enter a mobile phone number Uber can text, like (310) 555-0123.")
    return Guest(first, last, e164)


# ---- the Uber app deeplink ----------------------------------------------------------------------------------------

def deeplink(plan: LegPlan) -> str:
    """Open the Uber app (or m.uber.com) with the pickup and dropoff filled in (no product: those ids are per city and need Uber's API). Deeplinks cannot schedule, so this books nothing
    here and sends nothing back: the traveler requests the ride in Uber."""
    def spot(p):
        return quote(json.dumps({"latitude": p.lat, "longitude": p.lng, "addressLine1": p.name, "addressLine2": p.address}, separators=(",", ":")), safe="")

    client = os.environ.get("UBER_CLIENT_ID", "")
    parts = ([f"client_id={quote(client, safe='')}"] if client else []) + [f"pickup={spot(plan.pickup)}", f"drop[0]={spot(plan.dropoff)}"]
    return "https://m.uber.com/looking?" + "&".join(parts)


# ---- storage: the family database (gitaway.familydb, table rides) ---------------------------------------------------

def context_key(flight_id, stay_id, trip_query) -> str:
    """Which picks a ride belongs to: the flight, the stay and the trip dates. A booking with the same picks shows the ride."""
    return hashlib.sha256(f"{flight_id or ''}|{stay_id or ''}|{trip_query or ''}".encode()).hexdigest()[:8]


def booking_key(b) -> str:
    return context_key(b.get("flight"), b.get("stay"), b.get("trip"))


def to_dict(r: RideRecord) -> dict:
    """The compact form stored in the family database's `rides` table (about 200 bytes of JSON)."""
    d = {"i": r.id, "k": r.key, "l": r.leg[0], "p": r.product, "c": r.cents, "u": r.cars, "t": int(r.pickup_time.timestamp()), "m": r.minutes, "n": r.party,
         "a": r.airport, "g": [r.guest.first, r.guest.last], "ph": r.guest.phone, "q": r.request_id, "fi": r.fare_id}
    for key, value in (("h", r.stay_id), ("x", r.step), ("s", 1 if r.canceled else 0), ("d", 1 if r.demo else 0), ("ho", list(r.hotel))):
        if value:
            d[key] = value
    return d


def from_dict(d: dict) -> RideRecord:
    leg = "arrive" if d["l"] == "a" else "depart"
    pickup = datetime.fromtimestamp(d["t"], TZ)
    return RideRecord(d["i"], d["q"], d["k"], leg, d["p"], _product_id(d["p"]), d["fi"], d["c"], d["u"], pickup, d["m"], d["n"], d["a"], d.get("h", ""),
                      Guest(d["g"][0], d["g"][1], d["ph"]), d.get("x", 0), bool(d.get("s")), bool(d.get("d")), tuple(d.get("ho", ())))


def _stored(db):
    """The family's ride rows, oldest first (the number in the id, then insertion order)."""
    return familydb.rows(db, "SELECT * FROM rides ORDER BY seq, rowid")


def list_rides(session) -> list[RideRecord]:
    """The family's rides, oldest first: every member sees every ride, and a booking with the same picks shows them. Empty when signed out."""
    with ses.family(session) as fam:
        return [from_dict(json.loads(r["data"])) for r in _stored(fam.db)] if fam else []


def get_ride(session, ride_id) -> RideRecord | None:
    with ses.family(session) as fam:
        found = familydb.row(fam.db, "SELECT data FROM rides WHERE id = :id", id=ride_id) if fam else None
        return from_dict(json.loads(found["data"])) if found else None


def next_ride_id(session) -> str:
    with ses.family(session) as fam:
        return "r" + str((familydb.row(fam.db, "SELECT MAX(seq) AS n FROM rides")["n"] or 0) + 1) if fam else "r1"


def _trip_of_key(db, key, prefer):
    """The family trip whose booking these picks (`key`) belong to: the open one if it matches, else any. "" when nothing is booked with them yet."""
    found = []
    for t in familydb.trips(db):
        b = familydb.booking_for_trip(db, t["id"])
        if b and booking_key(b) == key:
            found.append(t["id"])
    return prefer if prefer in found else (found[0] if found else "")


def _apply(session, make, ride_id=None):
    """Write one ride in one locked transaction. `make(stored)` gets the stored RideRecord for `ride_id` (re-read after the lock is taken, so a
    cancel or step always acts on the ride as it is now) and returns the record to keep. Raises RideError."""
    with ses.family(session) as fam:
        if not fam:
            raise RideError("Sign in to schedule a ride.")
        db = fam.db
        with familydb.transaction(db):
            familydb.lock(db)  # from here to the commit nobody else writes, so the checks below cannot go stale
            rows = [(r, json.loads(r["data"])) for r in _stored(db)]
            old = next(((r, d) for r, d in rows if r["id"] == ride_id), None) if ride_id else None
            if ride_id and not old:
                raise RideError("We couldn't find that ride.")
            record = make(from_dict(old[1]) if old else None)
            mine = next((r for r, _ in rows if r["id"] == record.id), None)
            if mine and mine["request_id"] != record.request_id:
                raise RideError("Someone in your family just scheduled a ride. Look at the calendar, then try again.")
            if mine and next(d for r, d in rows if r is mine).get("s") and not record.canceled:
                raise RideError("This ride is cancelled, so it can't be changed. Schedule a new one.")
            same = [(r, d) for r, d in rows if d["i"] != record.id and d["k"] == record.key and d["l"] == record.leg[0]]
            if any(not d.get("s") for _, d in same) and not record.canceled:
                raise RideError("You already have an Uber scheduled for that leg. Cancel it first to schedule another.")
            for r, _ in same:  # the cancelled ride on this very leg is replaced; no live ride and no ride a trip uses is touched
                delete_record(db, "rides", r["id"], "id", auto_commit=False)
            used = {booking_key(b) for b in (familydb.booking_for_trip(db, t["id"]) for t in familydb.trips(db)) if b}
            for r, d in rows:  # a cancelled ride that no trip's picks match any more is of no use to anyone
                if d.get("s") and d["k"] not in used and r["id"] != record.id and (r, d) not in same:
                    delete_record(db, "rides", r["id"], "id", auto_commit=False)
                    rows = [x for x in rows if x[0] is not r]
            data = json.dumps(to_dict(record), separators=(",", ":"))
            if mine:
                update_record(db, "rides", record.id, "id", auto_commit=False, data=data)
            else:
                trip_id = _trip_of_key(db, record.key, fam.trip_id)
                live = [1 for r, d in rows if trip_id and r["trip_id"] == trip_id and not d.get("s") and (r, d) not in same]
                if len(live) >= len(LEGS) and not record.canceled:
                    raise RideError("That trip already has a ride for the arrival and one for the departure.")
                if sum(1 for r, d in rows if not d.get("s") and (r, d) not in same) >= MAX_RIDES:  # cancelled rides do not count
                    raise RideError(f"That is {MAX_RIDES} rides already. This demo keeps it small.")
                insert_only(db, "rides", {"id": record.id, "seq": int(record.id[1:]), "trip_id": trip_id, "key": record.key, "leg": record.leg,
                                          "request_id": record.request_id, "data": data, "created_by": fam.traveler.id, "created_at": familydb.now()},
                            ["id"], auto_commit=False)
    return record


def save_ride(session, record: RideRecord) -> RideRecord:
    """Add a ride, or replace the one with the same id. A leg has one live ride per set of picks: a cancelled one is replaced by a new one.
    A cancelled ride is never brought back. Raises RideError when the leg already has a live ride, when another member took the same ride id
    a moment ago, or when the trip or the family has too many."""
    return _apply(session, lambda _stored: record, ride_id=None)


def cancel_ride(session, ride_id, at=None) -> RideRecord:
    """Cancel a ride through the provider and keep it as cancelled. Raises RideError."""
    return _apply(session, lambda cur: provider().cancel(cur, at), ride_id)


def step_ride(session, ride_id, at=None) -> RideRecord:
    """The Step control: the simulator's next driver action. Raises RideError when the provider cannot step."""
    p = provider()
    if not getattr(p, "can_step", False):
        raise RideError("Only the simulation can be stepped.")
    return _apply(session, lambda cur: p.advance(cur, at), ride_id)


def schedule_ride(session, req: ScheduleRequest) -> RideRecord:
    """Ask the provider to schedule the ride, then keep it. Raises RideError."""
    return save_ride(session, provider().schedule(req))


def date_label(d: date) -> str:
    return f"{d:%a %b} {d.day}"
