"""The trip matrix's sums (F-222): places down, start days across, each square the whole trip (the flight and every stay, for the whole party).

    lanes(place, nearby)            the rows: the asked place, its nearby places (partners/places.py NEARBY), and each nearby place joined with it ("Los Angeles + San Diego")
    windows(depart, return_, flex)  the columns: the same nights starting up to `flex` days either side, never before today
    stays_for(lane, window), legs_for(lane, window, home)   what a source searches for one square: two places split the nights and fly in to the first, home from the second
    marks(lanes, windows, totals, budget)   each answered square's marks: "find", "low" (the cheapest start in its lane), "over" (the budget)
    find(lanes, windows, totals)    the discovery: a nearby trip that beats or nearly matches the asked place on the same dates, said in words
    order(lanes, windows)           which squares to ask for first: the asked square, then the nearest dates and the likeliest places

Nothing here fetches or invents: a total is a source's (gitaway/gridsource.py `square`), a square still waiting has none and gets no mark. assets/js/tripmatrix.js
marks the squares with the same rules as answers land (`marks`, `find`): change one, change the other (tests_browser/test_tripmatrix.py compares them).
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from gitaway.partners import places as places_

NEARLY_CENTS = 15_000      # a nearby trip up to $150 more than the asked place on the same dates "nearly matches" it (D-427)
MAX_FLEX = 3
OK, OVER, FAILED, NONE, NO_SAMPLE = "ok", "over budget", "failed", "none", "no sample"
SAID = {OVER: "Today’s price searches are used up. Back tomorrow.", FAILED: "Couldn’t search just now. Try again in a few minutes.",
        NONE: "No flights or no stays came back for these dates.", NO_SAMPLE: "No sample prices for this place. Real prices need a LiteAPI key."}
SHORT = {OVER: "Used up today", FAILED: "Couldn’t search", NONE: "None found", NO_SAMPLE: "No sample"}
MARKS = ("find", "low", "over")


@dataclass(frozen=True)
class Lane:
    key: str              # "sandiego", "losangeles+sandiego"
    name: str             # "San Diego", "Los Angeles + San Diego"
    places: tuple         # (Place,) or (the first Place, the second Place)
    asked: bool = False

    @property
    def combo(self) -> bool:
        return len(self.places) == 2


@dataclass(frozen=True)
class Window:
    depart: date
    return_: date
    asked: bool = False

    @property
    def key(self) -> str:
        return self.depart.isoformat()

    @property
    def nights(self) -> int:
        return (self.return_ - self.depart).days


@dataclass(frozen=True)
class FlightPart:
    airline: str
    out: str              # "SFO 8:05 AM → SAN 9:32 AM · Nonstop"
    back: str
    stops: int
    cents: int            # the whole party, both ways


@dataclass(frozen=True)
class StayPart:
    place: str
    nights: int
    name: str
    room: str
    board: str            # "room only", "breakfast", ...
    refundable: bool
    due_at_stay_cents: int     # paid at the hotel, already in `cents` (D-425)
    photo: str            # the hotel's own photo from the source, or ""
    rating: str           # "9.4 of 10 · 1,063 reviews", or ""
    cents: int            # all its nights, the whole party, fees paid at the hotel included


@dataclass(frozen=True)
class Square:
    lane: str
    window: str
    status: str
    flight: FlightPart | None = None
    stays: tuple = ()
    drive: int | None = None          # minutes from the first airport to the first stay's town, when a router said
    fetched: datetime | None = None   # when the older of its answers was fetched
    sample: bool = False

    @property
    def key(self) -> str:
        return key(self.lane, self.window)

    @property
    def ok(self) -> bool:
        return self.status == OK and self.flight is not None and bool(self.stays)

    @property
    def cents(self) -> int | None:
        return self.flight.cents + sum(s.cents for s in self.stays) if self.ok else None


@dataclass(frozen=True)
class Find:
    lane: str
    window: str
    diff_cents: int       # this square minus the asked place's on the same dates
    words: str            # "Los Angeles + San Diego, $50 more than San Diego alone"
    when: str             # "Dec 12 to 16"

    @property
    def key(self) -> str:
        return key(self.lane, self.window)


def key(lane_key, window_key) -> str:
    return f"{lane_key}|{window_key}"


def dollars(cents: int) -> str:
    """Whole dollars, half up: 206_050 -> "$2,061". A square is too small for cents; the panel says the cents (catalog.money)."""
    return f"${(int(cents) + 50) // 100:,}"


def when(w: Window) -> str:
    a, b = w.depart, w.return_
    return f"{a:%b} {a.day} to " + (f"{b.day}" if (a.year, a.month) == (b.year, b.month) else f"{b:%b} {b.day}")


# ---- rows and columns -----------------------------------------------------------------------------------------------

def lanes(place, nearby=True) -> tuple:
    near = places_.nearby(place) if nearby else ()
    out = [Lane(place.slug, place.name, (place,), True)] + [Lane(p.slug, p.name, (p,)) for p in near]
    out += [Lane(f"{p.slug}+{place.slug}", f"{p.name} + {place.name}", (p, place)) for p in near]
    return tuple(out)


def lane(place, lane_key, nearby=True) -> Lane | None:
    return next((x for x in lanes(place, nearby) if x.key == lane_key), None)


def windows(depart, return_, flex, today) -> tuple:
    flex = max(0, min(MAX_FLEX, int(flex or 0)))
    nights = timedelta(days=(return_ - depart).days)
    starts = [depart + timedelta(days=i) for i in range(-flex, flex + 1)]
    return tuple(Window(d, d + nights, d == depart) for d in starts if d >= today)


def window(depart, return_, flex, today, window_key) -> Window | None:
    return next((w for w in windows(depart, return_, flex, today) if w.key == window_key), None)


def stays_for(lane_: Lane, w: Window):
    """((place, checkin, checkout), ...): one place has every night; two split them, the first place the shorter half. None for one night and two places."""
    if not lane_.combo:
        return ((lane_.places[0], w.depart, w.return_),)
    if w.nights < 2:
        return None
    middle = w.depart + timedelta(days=w.nights // 2)
    return ((lane_.places[0], w.depart, middle), (lane_.places[1], middle, w.return_))


def legs_for(lane_: Lane, w: Window, home: str) -> tuple:
    """Out to the first place's airport, home from the last one's (an open jaw for two places)."""
    return ((home, lane_.places[0].iata, w.depart), (lane_.places[-1].iata, home, w.return_))


def order(lanes_, windows_) -> list:
    """Square keys, the asked square first, then by days from the asked start plus the lane's place in the list; earlier dates first on a tie."""
    asked = next((i for i, w in enumerate(windows_) if w.asked), 0)
    ranked = sorted(((abs(j - asked) + i, i, j) for i in range(len(lanes_)) for j in range(len(windows_))))
    return [key(lanes_[i].key, windows_[j].key) for _, i, j in ranked]


# ---- marks ----------------------------------------------------------------------------------------------------------

def find(lanes_, windows_, totals) -> Find | None:
    """The nearby trip that beats or nearly matches (NEARLY_CENTS) the asked place on the same start day: the lowest difference wins, two places together
    before one on a tie, then the lane's and the day's order. Only squares that have real totals take part."""
    asked = next((x for x in lanes_ if x.asked), None)
    if asked is None:
        return None
    best = None
    for j, w in enumerate(windows_):
        base = totals.get(key(asked.key, w.key))
        if base is None:
            continue
        for i, x in enumerate(lanes_):
            got = totals.get(key(x.key, w.key))
            if x.asked or got is None or got - base > NEARLY_CENTS:
                continue
            rank = (got - base, 0 if x.combo else 1, i, j)
            if best is None or rank < best[0]:
                best = (rank, x, w, got - base)
    if best is None:
        return None
    _, x, w, diff = best
    alone = " alone" if x.combo and asked.places[0] in x.places else ""
    said = (f"{dollars(-diff)} less than {asked.name}" if diff < 0 else f"the same as {asked.name}" if diff == 0 else f"{dollars(diff)} more than {asked.name}{alone}")
    return Find(x.key, w.key, diff, f"{x.name}, {said}", when(w))


def marks(lanes_, windows_, totals, budget_cents=None) -> dict:
    """{square key: marks in MARKS order} for every square with a total. "low" needs two answers in the lane to compare."""
    found = find(lanes_, windows_, totals)
    out = {}
    for x in lanes_:
        known = [(totals[key(x.key, w.key)], j, w) for j, w in enumerate(windows_) if key(x.key, w.key) in totals]
        low = min(known)[2].key if len(known) >= 2 else None
        for cents, _, w in known:
            k = key(x.key, w.key)
            on = {"find": found is not None and found.key == k, "low": w.key == low, "over": bool(budget_cents) and cents > budget_cents}
            out[k] = tuple(m for m in MARKS if on[m])
    return out
