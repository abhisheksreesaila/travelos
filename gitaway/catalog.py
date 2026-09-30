"""The fake SFO → LA catalog behind the booking workspace.

Everything here is invented sample data (airlines, hotels, rental companies, prices) that looks real.
Prices are integer cents for the whole party and whole trip, taxes and fees included.
"""

from dataclasses import dataclass, field
from datetime import date
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


@dataclass(frozen=True)
class Quote:
    flight_id: str
    stay_id: str
    car_id: str
    lines: tuple = field(default=())
    total_cents: int = 0
    above_cheapest_cents: int = 0


def _cheapest_ids():
    return min(
        product(*(offers(k) for k in ("flight", "stay", "car"))),
        key=lambda combo: sum(o.price_cents for o in combo),
    )


def quote(flight_id: str, stay_id: str, car_id: str) -> Quote:
    """The cost ledger for one pick in each lane. Unknown ids raise KeyError."""
    lines = tuple(offer(i) for i in (flight_id, stay_id, car_id))
    for line, kind in zip(lines, ("flight", "stay", "car")):
        if line.kind != kind:
            raise KeyError(f"{line.id} is a {line.kind}, not a {kind}")
    total = sum(o.price_cents for o in lines)
    floor = sum(o.price_cents for o in _cheapest_ids())
    return Quote(flight_id, stay_id, car_id, lines, total, total - floor)


def cheapest() -> Quote:
    f, s, c = _cheapest_ids()
    return quote(f.id, s.id, c.id)
