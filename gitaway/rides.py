"""Schedule an Uber, simulated faithfully (F-038). Research: docs/research/uber-api.md.

The shape follows Uber's Guest Rides API: an estimates call returns products with a `fare_id`, a price and an ETA; creating a
trip takes the guest (name and phone), pickup, dropoff, `product_id`, `fare_id` and `scheduling.pickup_time` (ms since the
epoch); a trip can be cancelled; and its status uses the documented names (scheduled, processing, accepted, arriving,
in_progress, completed, rider_canceled), which the screens turn into friendly words. The airport-to-hotel leg is a Reserve-style
booking (airport pickups need Reserve); the hotel-to-airport leg is an ordinary scheduled ride.

THE SEAM. `RideProvider` is the interface (`estimates`, `schedule`, `status`, `cancel`). The screens talk only to `provider()`,
which picks the implementation from `UBER_MODE` ("simulated" is the only one for now). A real Uber client implements the same four
methods and is returned from `provider()` once API access is granted. `SimulatedUber` is deterministic: nothing here calls out,
nothing is booked, and a guest's phone number never leaves the session.

STORAGE. `list_rides`, `save_ride`, `cancel_ride` (and `step_ride`) keep the rides in the session cookie for now, under the same
byte budget as everything else there. They are the only code that touches `session["rides"]`, so F-040 can swap them for the
family database. Session shape: "rides": {"<traveler id>": [compact ride dict, see to_dict]}.
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

from gitaway import catalog, session as ses

TZ = ZoneInfo("America/Los_Angeles")
MODES = ("simulated",)
SIMULATED_LABEL = "Simulated: no real ride is booked"
MIN_LEAD = timedelta(minutes=5)
MAX_LEAD = {"SCHEDULED": timedelta(days=30), "RESERVE": timedelta(days=90)}  # a normal scheduled ride, and Uber Reserve
MAX_RIDES = 6
MAX_NAME = 30
LEGS = ("arrive", "depart")


class RideError(ValueError):
    """A ride the demo refuses; the message is fit to show the traveler."""


def now():
    """The clock the simulation follows. The date comes from catalog.today() so tests (and the demo's fixed dates) stay put."""
    return datetime.combine(catalog.today(), datetime.now(TZ).timetz())


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
    area = catalog.ride_area(airport, stay)
    _dollars, minutes = catalog.ride_base(airport, area, kind)
    hotel = _hotel(airport, stay.id if stay else "")
    if kind == "arrive":
        day, at = trip.depart, flight.arrive_min + catalog.CURB_MINUTES
        pickup, dropoff = AIRPORTS[airport], hotel
    else:
        day, at = trip.return_, (flight.back_depart_min - catalog.AIRPORT_BUFFER - minutes) // 5 * 5
        pickup, dropoff = hotel, AIRPORTS[airport]
    when = datetime.combine(day, time(at // 60, at % 60), tzinfo=TZ)
    return LegPlan(kind, airport, stay.id if stay else "", pickup, dropoff, when, trip.travelers, minutes, "RESERVE" if kind == "arrive" else "SCHEDULED")


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
    return _fare_id(plan.kind, plan.pickup_ms, plan.airport, _hotel(plan.airport, plan.stay_id).area, key, cents)


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

    @property
    def plan(self) -> LegPlan:
        hotel = _hotel(self.airport, self.stay_id)
        out, back = (AIRPORTS[self.airport], hotel) if self.leg == "arrive" else (hotel, AIRPORTS[self.airport])
        return LegPlan(self.leg, self.airport, self.stay_id, out, back, self.pickup_time, self.party, self.minutes,
                       "RESERVE" if self.leg == "arrive" else "SCHEDULED")

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
        lead = plan.pickup_time - now()
        if lead < MIN_LEAD:
            raise RideError("Pick a time at least 5 minutes from now. That pickup is too soon or has passed.")
        if lead > MAX_LEAD[plan.advance]:
            days = MAX_LEAD[plan.advance].days
            raise RideError(f"Uber takes bookings up to {days} days ahead for this kind of ride. Try again closer to {plan.pickup_time:%b} {plan.pickup_time.day}.")
        request_id = "sim_" + hashlib.sha256(f"{req.key}|{req.ride_id}|{plan.kind}|{plan.pickup_ms}".encode()).hexdigest()[:12]
        key = next(p.key for p in PRODUCTS if _product_id(p.key) == req.product_id)
        return RideRecord(req.ride_id, request_id, req.key, plan.kind, key, req.product_id, req.fare_id, match.cents, match.cars, plan.pickup_time,
                          plan.minutes, plan.party, plan.airport, plan.stay_id, req.guest)

    def _stage(self, r: RideRecord, at) -> int:
        at = at or now()
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
        return RideStatus(name, LABELS[name], _TIMELINE_AT[stage], stage == 5, driver, vehicle, plate, can_cancel=stage < 4, can_step=stage < 5,
                          next_action=STEP_ACTIONS.get(nxt, ""))

    def cancel(self, record: RideRecord, at: datetime | None = None) -> RideRecord:
        if record.canceled:
            raise RideError("This ride is already cancelled.")
        if self._stage(record, at) >= 4:
            raise RideError("This ride is already on its trip, so it can't be cancelled.")
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

def deeplink(plan: LegPlan, product_key=None) -> str:
    """Open the Uber app (or m.uber.com) with the pickup, dropoff and product filled in. Deeplinks cannot schedule, so this books nothing
    here and sends nothing back: the traveler requests the ride in Uber."""
    def spot(p):
        return quote(json.dumps({"latitude": p.lat, "longitude": p.lng, "addressLine1": p.name, "addressLine2": p.address}, separators=(",", ":")), safe="")

    client = os.environ.get("UBER_CLIENT_ID", "")
    parts = ([f"client_id={quote(client, safe='')}"] if client else []) + [f"pickup={spot(plan.pickup)}", f"drop[0]={spot(plan.dropoff)}"]
    if product_key:
        parts.append(f"product_id={_product_id(product(product_key).key)}")
    return "https://m.uber.com/looking?" + "&".join(parts)


# ---- storage: the session cookie for now (F-040 swaps these for the family database) -------------------------------

def context_key(flight_id, stay_id, trip_query) -> str:
    """Which picks a ride belongs to: the flight, the stay and the trip dates. A booking with the same picks shows the ride."""
    return hashlib.sha256(f"{flight_id or ''}|{stay_id or ''}|{trip_query or ''}".encode()).hexdigest()[:8]


def booking_key(b) -> str:
    return context_key(b.get("flight"), b.get("stay"), b.get("trip"))


def to_dict(r: RideRecord) -> dict:
    """The compact form kept in the cookie: about 200 bytes."""
    d = {"i": r.id, "k": r.key, "l": r.leg[0], "p": r.product, "c": r.cents, "u": r.cars, "t": int(r.pickup_time.timestamp()), "m": r.minutes, "n": r.party,
         "a": r.airport, "g": [r.guest.first, r.guest.last], "ph": r.guest.phone}
    for key, value in (("h", r.stay_id), ("x", r.step), ("s", 1 if r.canceled else 0)):
        if value:
            d[key] = value
    return d


def from_dict(d: dict) -> RideRecord:
    leg = "arrive" if d["l"] == "a" else "depart"
    pickup = datetime.fromtimestamp(d["t"], TZ)
    ms = int(pickup.timestamp() * 1000)
    fare = _fare_id(leg, ms, d["a"], _hotel(d["a"], d.get("h", "")).area, d["p"], d["c"])
    request_id = "sim_" + hashlib.sha256(f"{d['k']}|{d['i']}|{leg}|{ms}".encode()).hexdigest()[:12]
    return RideRecord(d["i"], request_id, d["k"], leg, d["p"], _product_id(d["p"]), fare, d["c"], d["u"], pickup, d["m"], d["n"], d["a"], d.get("h", ""),
                      Guest(d["g"][0], d["g"][1], d["ph"]), d.get("x", 0), bool(d.get("s")))


def _mine(session):
    t = ses.current_traveler(session)
    return (session.get("rides") or {}).get(t.id, []) if t else []


def list_rides(session) -> list[RideRecord]:
    """The signed-in traveler's rides, oldest first. Empty when signed out."""
    return [from_dict(d) for d in _mine(session)]


def get_ride(session, ride_id) -> RideRecord | None:
    return next((r for r in list_rides(session) if r.id == ride_id), None)


def next_ride_id(session) -> str:
    return "r" + str(max([int(d["i"][1:]) for d in _mine(session)] or [0]) + 1)


def _write(session, rows):
    t = ses.current_traveler(session)
    old = session.get("rides")
    session["rides"] = {**(old or {}), t.id: rows}  # reassign the whole dict so the cookie session notices
    if len(json.dumps(dict(session))) > ses.BUDGET:
        if old is None:
            session.pop("rides", None)
        else:
            session["rides"] = old
        raise RideError("This demo is full. Delete something from your calendar to make room, then schedule the ride.")


def save_ride(session, record: RideRecord) -> RideRecord:
    """Add a ride, or replace the one with the same id. A leg has one live ride per set of picks: a cancelled one is replaced by a new one.
    Raises RideError when it already has a live ride, or when the session cookie has no room."""
    if not ses.current_traveler(session):
        raise RideError("Sign in to schedule a ride.")
    rows = list(_mine(session))
    same = [d for d in rows if d["i"] != record.id and d["k"] == record.key and d["l"] == record.leg[0]]
    if any(not d.get("s") for d in same) and not record.canceled:
        raise RideError("You already have an Uber scheduled for that leg. Cancel it first to schedule another.")
    rows = [d for d in rows if d not in same and not (d.get("s") and d["k"] != record.key)]  # drop the cancelled one it replaces, and stale cancelled rides
    new = to_dict(record)
    if any(d["i"] == record.id for d in rows):
        rows = [new if d["i"] == record.id else d for d in rows]
    elif len(rows) >= MAX_RIDES:
        raise RideError(f"That is {MAX_RIDES} rides already. This demo keeps it small.")
    else:
        rows.append(new)
    _write(session, rows)
    return record


def cancel_ride(session, ride_id, at=None) -> RideRecord:
    """Cancel a ride through the provider and keep it as cancelled. Raises RideError."""
    r = get_ride(session, ride_id)
    if not r:
        raise RideError("We couldn't find that ride.")
    return save_ride(session, provider().cancel(r, at))


def step_ride(session, ride_id, at=None) -> RideRecord:
    """The Step control: the simulator's next driver action. Raises RideError when the provider cannot step."""
    r, p = get_ride(session, ride_id), provider()
    if not r:
        raise RideError("We couldn't find that ride.")
    if not getattr(p, "can_step", False):
        raise RideError("Only the simulation can be stepped.")
    return save_ride(session, p.advance(r, at))


def schedule_ride(session, req: ScheduleRequest) -> RideRecord:
    """Ask the provider to schedule the ride, then keep it. Raises RideError."""
    return save_ride(session, provider().schedule(req))


def date_label(d: date) -> str:
    return f"{d:%a %b} {d.day}"
