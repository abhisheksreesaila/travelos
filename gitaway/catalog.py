"""The fake SFO → LA catalog behind the booking workspace.

Everything here is invented sample data (airlines, hotels, rental companies, prices) that looks real.
Prices are integer cents for the whole party and whole trip, taxes and fees included.
"""

from dataclasses import dataclass, field
from datetime import date
import re
from itertools import product


@dataclass(frozen=True)
class TripSearch:
    origin: str
    origin_name: str
    destination_name: str
    airports: tuple  # airports that serve the destination
    depart: date
    return_: date
    adults: int
    kid_ages: tuple

    @property
    def nights(self) -> int:
        return (self.return_ - self.depart).days

    @property
    def travelers(self) -> int:
        return self.adults + len(self.kid_ages)

    @property
    def summary(self) -> str:
        kids = len(self.kid_ages)
        parts = [f"{self.adults} adult{'s' if self.adults != 1 else ''}"]
        if kids:
            parts.append(f"{kids} kid{'s' if kids != 1 else ''}")
        return ", ".join(parts)


@dataclass(frozen=True)
class Offer:
    id: str
    kind: str  # flight | stay | car
    name: str
    headline: str  # the big line on the card: times for flights, area for stays, vehicle for cars
    detail: str
    price_cents: int
    badges: tuple = ()
    tags: tuple = ()
    rating: str = ""
    area_photo: str = ""  # a neighbourhood photo (assets/photos), never a picture of the property
    airport: str = ""  # flights only: where it lands
    # Flights only, minutes after midnight: out on the first day, back on the last day.
    depart_min: int = 0
    arrive_min: int = 0
    back_depart_min: int = 0
    back_arrive_min: int = 0


SAMPLE_TRIP = TripSearch("SFO", "San Francisco", "Los Angeles", ("LAX", "BUR"), date(2026, 10, 16), date(2026, 10, 20), 2, (4, 7))

_OFFERS = [
    Offer("f1", "flight", "Skylark Air 214", "8:05 → 9:32", "Nonstop to LAX · 1h 27m · back Tue 2:10 PM", 123_600, ("Best nonstop",), airport="LAX",
          depart_min=485, arrive_min=572, back_depart_min=850, back_arrive_min=937),
    Offer("f2", "flight", "Pacific Hop 88", "6:40 → 8:02", "Nonstop to LAX · 1h 22m · very early start", 110_400, airport="LAX",
          depart_min=400, arrive_min=482, back_depart_min=750, back_arrive_min=832),
    Offer("f3", "flight", "Golden Gate Air 530", "11:15 → 12:44", "Nonstop to LAX · 1h 29m · extra legroom", 139_200, airport="LAX",
          depart_min=675, arrive_min=764, back_depart_min=960, back_arrive_min=1049),
    Offer("f4", "flight", "Skylark Air 902", "9:20 → 12:05", "1 stop in SJC, lands LAX · 2h 45m", 96_800, ("Cheapest",), airport="LAX",
          depart_min=560, arrive_min=725, back_depart_min=785, back_arrive_min=950),
    Offer("f5", "flight", "Pacific Hop 312", "10:10 → 11:30", "Nonstop to Burbank (BUR) · 1h 20m · tiny, easy airport", 118_000, airport="BUR",
          depart_min=610, arrive_min=690, back_depart_min=920, back_arrive_min=1000),
    Offer("h1", "stay", "The Tidewater", "Santa Monica", "2 rooms · 3 min walk to the beach", 154_000,
          tags=("Kid friendly", "Pool"), rating="4.8 · 1.2k reviews", area_photo="santa-monica-beach-pier.jpg"),
    Offer("h2", "stay", "Casa Palmera", "Venice", "Family suite · 8 min walk to the beach", 118_800,
          tags=("Pet friendly", "Kitchen"), rating="4.6 · 860 reviews", area_photo="venice-beach-los-angeles-hero.jpg"),
    Offer("h3", "stay", "Hotel Marigold", "Downtown", "2 queens · 35 min drive to the beach", 89_200,
          tags=("Great value",), rating="4.4 · 2.3k reviews"),
    Offer("c1", "car", "Breeze Rentals", "Compact SUV", "2 car seats included", 31_200),
    Offer("c2", "car", "Coastline Cars", "Minivan", "Room for strollers", 39_800),
    Offer("c3", "car", "No car", "Rideshare & Metro", "Estimated for the week", 18_000),
]
_BY_ID = {o.id: o for o in _OFFERS}


def offers(kind: str) -> list[Offer]:
    """Offers in one workspace lane, in display order."""
    return [o for o in _OFFERS if o.kind == kind]


def offer(offer_id: str) -> Offer:
    """One offer by id. Raises KeyError for an unknown id."""
    return _BY_ID[offer_id]


def money(cents: int) -> str:
    """Whole-dollar display used across the app: 308800 -> '$3,088'."""
    dollars, rem = divmod(cents, 100)
    return f"${dollars:,}" if rem == 0 else f"${cents / 100:,.2f}"


# ---- stay details: rooms, add-ons, highlights, policy, sample photos, points of interest (F-026) --------------------

PARTY = SAMPLE_TRIP.travelers  # rooms must sleep at least this many
MAX_PER_ROOM = 4  # the most of one room type


@dataclass(frozen=True)
class Room:
    id: str  # two lower-case letters, unique within its stay
    name: str
    view: str
    beds: str
    sleeps: int
    price_cents: int  # per room, for the whole stay, taxes in
    tint: str  # a design fill class behind the sample photo
    photo: str = ""  # a file in assets/photos, or "" for a tint placeholder


@dataclass(frozen=True)
class Addon:
    id: str
    name: str
    short: str  # how the choose bar and the calendar name it
    price_cents: int


@dataclass(frozen=True)
class Poi:
    kind: str  # hotel | beach | sight | food | park | train
    name: str
    label: str  # the short pin label
    x: int  # percent across the map plane
    y: int
    walk: str  # "3 min walk"; empty for the hotel itself
    note: str


@dataclass(frozen=True)
class StayDetail:
    chips: tuple
    highlights: tuple
    policy: str
    samples: tuple  # (label, photo file or "")
    rooms: tuple  # of Room; the first sleeps the whole party and is the default
    coast: bool
    pois: tuple  # of Poi; the first is the hotel

    @property
    def near(self):
        """The first three points of interest, for the always-visible walks strip."""
        return tuple(self.pois[1:4])


ADDONS = (
    Addon("bf", "Breakfast for 4", "Breakfast", 32_000),
    Addon("lc", "Late checkout, 2 PM", "Late checkout", 4_000),
    Addon("pk", "Parking, 4 nights", "Parking", 18_000),
)
_ADDON_BY_ID = {a.id: a for a in ADDONS}

_HOME = "You are here. Tap a pin to fly to it."
_STAY_DETAILS = {
    "h1": StayDetail(
        chips=("Sea view", "Pool", "Crib available", "3 min to the beach"),
        highlights=("Kids eat free at the pool café", "Beach towels and sand toys to borrow", "Quiet floors above the 3rd"),
        policy="Free cancellation until Oct 13. After that, the first night is charged.",
        samples=(("Lobby", "lobby-front-desk.jpg"), ("Pool", "pool-courtyard.jpg"), ("Room", "room-purple-window.jpg"), ("Breakfast", "breakfast-buffet.jpg")),
        rooms=(
            Room("cq", "City-view Double Queen", "City view", "2 queen beds", 4, 154_000, "fill-grape-tint", "room-bed-lamp.jpg"),
            Room("ok", "Ocean-view King", "Ocean view", "1 king bed", 2, 106_000, "fill-sky-tint", "room-purple-window.jpg"),
            Room("fs", "Family suite", "Ocean view", "King + bunk beds", 5, 198_000, "fill-sun-tint", "room-balcony-view.jpg"),
        ),
        coast=True,
        pois=(
            Poi("hotel", "The Tidewater", "The Tidewater", 44, 50, "", _HOME),
            Poi("beach", "Santa Monica Beach", "Beach", 33, 45, "3 min walk", "Wide sand, lifeguards, and the bike path."),
            Poi("sight", "Santa Monica Pier", "Pier", 34, 64, "6 min walk", "Ferris wheel, arcade and the aquarium under the pier."),
            Poi("food", "Third Street Promenade", "Promenade", 60, 40, "9 min walk", "Car-free shopping street with street performers."),
            Poi("park", "Tongva Park playground", "Playground", 66, 25, "10 min walk", "Splash pads and hills to roll down."),
            Poi("train", "Metro E Line", "Metro", 72, 60, "12 min walk", "Train to Culver City and Downtown."),
        ),
    ),
    "h2": StayDetail(
        chips=("Pet friendly", "Kitchen", "Crib available", "Bikes to borrow"),
        highlights=("Full kitchen in every suite", "Walk to the canals", "Dogs stay free"),
        policy="Free cancellation until Oct 9. After that, 50% of the stay is charged.",
        samples=(("Courtyard", "pool-courtyard.jpg"), ("Kitchen", ""), ("Suite", "room-balcony-view.jpg"), ("Canals", "")),
        rooms=(
            Room("fk", "Family suite with kitchen", "Garden view", "Queen + sofa bed", 4, 118_800, "fill-mint-tint", "room-dark-wood.jpg"),
            Room("gs", "Garden studio", "Garden view", "1 queen bed", 2, 68_000, "fill-bubble-tint", "room-bed-lamp.jpg"),
            Room("cs", "Canal-view suite", "Canal view", "King + 2 twins", 4, 142_000, "fill-sky-tint", "room-purple-window.jpg"),
        ),
        coast=True,
        pois=(
            Poi("hotel", "Casa Palmera", "Casa Palmera", 46, 52, "", _HOME),
            Poi("beach", "Venice Beach", "Beach", 33, 50, "8 min walk", "Boardwalk, skate park and muscle beach."),
            Poi("sight", "Venice Canals", "Canals", 52, 67, "4 min walk", "Footbridges and rowboats, lovely at sunset."),
            Poi("food", "Abbot Kinney Blvd", "Abbot Kinney", 60, 40, "6 min walk", "Cafés, ice cream and small shops."),
            Poi("park", "Penmar Park", "Park", 66, 25, "15 min walk", "Playground and a big lawn for dogs."),
        ),
    ),
    "h3": StayDetail(
        chips=("Great value", "Rooftop pool", "Near the Metro"),
        highlights=("Metro to the beach in 45 minutes", "Rooftop pool open till 10", "Free museum shuttle"),
        policy="Free cancellation until the day before check-in.",
        samples=(("Rooftop", "rooftop-bar.jpg"), ("Room", "room-bed-lamp.jpg"), ("Lobby", "lobby-front-desk.jpg"), ("Breakfast", "breakfast-buffet.jpg")),
        rooms=(
            Room("qq", "Double Queen", "City view", "2 queen beds", 4, 89_200, "fill-sun-tint", "room-dark-wood.jpg"),
            Room("kk", "King room", "City view", "1 king bed", 2, 52_000, "fill-grape-tint", "room-bed-lamp.jpg"),
            Room("cy", "City suite", "Skyline view", "King + sofa bed", 4, 116_000, "fill-sky-tint", "room-balcony-view.jpg"),
        ),
        coast=False,
        pois=(
            Poi("hotel", "Hotel Marigold", "Marigold", 48, 50, "", _HOME),
            Poi("train", "Metro 7th St", "Metro", 56, 61, "3 min walk", "Trains to the beach, Hollywood and Pasadena."),
            Poi("park", "Grand Park", "Grand Park", 66, 25, "5 min walk", "Fountains the kids can splash in."),
            Poi("food", "Grand Central Market", "Food hall", 36, 62, "4 min walk", "Forty food stalls under one roof."),
            Poi("sight", "The Broad", "The Broad", 38, 32, "7 min walk", "Free modern art museum with the mirror room."),
            Poi("beach", "Santa Monica Beach", "Beach, 35 min", 22, 48, "35 min drive", "Or about 50 minutes on the Metro E Line."),
        ),
    ),
}


def stay_detail(stay_id: str) -> StayDetail:
    """Rooms, highlights, policy, photos and map points for one stay. Raises KeyError for an unknown id."""
    return _STAY_DETAILS[stay_id]


def addon(addon_id: str) -> Addon:
    return _ADDON_BY_ID[addon_id]


FIT_TEXT = {"none": "Pick at least one room", "full": f"Room for all {PARTY}"}
_ROOMS_RE = re.compile(r"(?:[a-z]{2}[0-9])*")
_ADDS_RE = re.compile(r"(?:[a-z]{2})*")


@dataclass(frozen=True)
class Item:
    """One priced line of the itemized ledger, pay sheet and calendar. `cents` is for the whole line (count included)."""
    lane: str  # flight | stay | car
    name: str
    qty: int
    cents: int
    detail: str = ""


@dataclass(frozen=True)
class StayPick:
    """One stay with the rooms and add-ons chosen for it. Build with parse_stay or stay_pick, not by hand."""
    stay_id: str
    rooms: tuple = ()  # (room id, count) in catalog order, counts 1..MAX_PER_ROOM
    addons: tuple = ()  # add-on ids in catalog order

    @property
    def detail(self) -> StayDetail:
        return stay_detail(self.stay_id)

    @property
    def sleeps(self) -> int:
        by_id = {r.id: r for r in self.detail.rooms}
        return sum(by_id[i].sleeps * n for i, n in self.rooms)

    @property
    def fits(self) -> bool:
        return self.sleeps >= PARTY

    @property
    def fit(self) -> str:
        return "none" if not self.rooms else ("full" if self.fits else "short")

    @property
    def fit_text(self) -> str:
        return f"Sleeps {self.sleeps} of {PARTY} · add a room" if self.fit == "short" else FIT_TEXT[self.fit]

    @property
    def counts(self) -> dict:
        """Every room of the stay with its count (0 when not picked), in catalog order."""
        have = dict(self.rooms)
        return {r.id: have.get(r.id, 0) for r in self.detail.rooms}

    @property
    def rooms_code(self) -> str:
        """The compact URL form: "" for the default room, else e.g. "ok2" or "ok2fs1"."""
        return "" if self.rooms == _default_rooms(self.stay_id) else "".join(f"{i}{n}" for i, n in self.rooms)

    @property
    def add_code(self) -> str:
        return "".join(self.addons)

    @property
    def query(self) -> str:
        """The URL params that carry this pick beyond the defaults; "" for the default pick."""
        return (f"&rooms={self.rooms_code}" if self.rooms_code else "") + (f"&add={self.add_code}" if self.addons else "")

    @property
    def items(self) -> tuple:
        by_id = {r.id: r for r in self.detail.rooms}
        rooms = tuple(Item("stay", by_id[i].name, n, by_id[i].price_cents * n, f"{by_id[i].beds} · sleeps {by_id[i].sleeps}") for i, n in self.rooms)
        adds = tuple(Item("stay", a.name, 1, a.price_cents) for a in map(addon, self.addons))
        return rooms + adds

    @property
    def cents(self) -> int:
        return sum(i.cents for i in self.items)

    @property
    def rooms_summary(self) -> str:
        by_id = {r.id: r for r in self.detail.rooms}
        return " + ".join(by_id[i].name + (f" ×{n}" if n > 1 else "") for i, n in self.rooms)

    @property
    def summary(self) -> str:
        """"Ocean-view King ×2 + Breakfast", as shown in the choose bar, the ledger and the calendar."""
        parts = ([self.rooms_summary] if self.rooms else []) + [addon(a).short for a in self.addons]
        return " + ".join(parts) if parts else "No room picked yet"


def _default_rooms(stay_id):
    return ((stay_detail(stay_id).rooms[0].id, 1),)


def _parse_add(add):
    if add is None or not _ADDS_RE.fullmatch(add):
        return ()
    ids = {add[k:k + 2] for k in range(0, len(add), 2)}
    return tuple(a.id for a in ADDONS if a.id in ids)


def parse_stay(stay_id: str, rooms=None, add=None) -> StayPick:
    """Read a stay pick from URL text without repairing capacity, so an edit in progress can be described.

    `rooms` None means the default room; "" means none picked. Malformed text, or a count above the limit, falls back to the
    default room; unknown ids drop out, a repeated room keeps its first count and a zero count means not picked.
    Malformed add-ons mean none.
    """
    by_id = {r.id: r for r in stay_detail(stay_id).rooms}
    if rooms is None or not _ROOMS_RE.fullmatch(rooms):
        return StayPick(stay_id, _default_rooms(stay_id), _parse_add(add))
    seen = {}
    for k in range(0, len(rooms), 3):
        rid, n = rooms[k:k + 2], int(rooms[k + 2])
        if n > MAX_PER_ROOM:
            return StayPick(stay_id, _default_rooms(stay_id), _parse_add(add))
        if rid in by_id and rid not in seen:
            seen[rid] = n
    chosen = tuple((r.id, seen[r.id]) for r in stay_detail(stay_id).rooms if seen.get(r.id))
    return StayPick(stay_id, chosen, _parse_add(add))


def stay_pick(stay_id: str, rooms=None, add=None) -> StayPick:
    """A stay pick that can be booked: rooms that are missing, bad, or sleep fewer than the party become the default room."""
    p = parse_stay(stay_id, rooms, add)
    return p if p.fits else StayPick(stay_id, _default_rooms(stay_id), p.addons)


@dataclass(frozen=True)
class Quote:
    flight_id: str
    stay_id: str
    car_id: str
    lines: tuple = field(default=())
    total_cents: int = 0
    above_cheapest_cents: int = 0
    items: tuple = field(default=())
    stay: StayPick = None

    def lane_cents(self, lane: str) -> int:
        return sum(i.cents for i in self.items if i.lane == lane)


def _cheapest_ids():
    return min(
        product(*(offers(k) for k in ("flight", "stay", "car"))),
        key=lambda combo: sum(o.price_cents for o in combo),
    )


def quote(flight_id: str, stay_id: str, car_id: str, stay: StayPick = None) -> Quote:
    """The itemized cost ledger for one pick in each lane. Unknown ids raise KeyError.

    `stay` (a StayPick for this stay; default: the default room) sets the rooms and add-ons. A pick for another stay
    raises KeyError, and one that sleeps fewer than the party raises ValueError.
    """
    lines = tuple(offer(i) for i in (flight_id, stay_id, car_id))
    for line, kind in zip(lines, ("flight", "stay", "car")):
        if line.kind != kind:
            raise KeyError(f"{line.id} is a {line.kind}, not a {kind}")
    stay = stay or stay_pick(stay_id)
    if stay.stay_id != stay_id:
        raise KeyError(f"{stay.stay_id} is not {stay_id}")
    if not stay.fits:
        raise ValueError(f"{stay.summary}: {stay.fit_text}")
    flight, _, car = lines
    items = (Item("flight", flight.name, 1, flight.price_cents, flight.detail), *stay.items, Item("car", car.name, 1, car.price_cents, car.detail))
    total = sum(i.cents for i in items)
    floor = sum(o.price_cents for o in _cheapest_ids())
    return Quote(flight_id, stay_id, car_id, lines, total, max(0, total - floor), items, stay)


def cheapest() -> Quote:
    f, s, c = _cheapest_ids()
    return quote(f.id, s.id, c.id)
