"""The trip matrix's sums (F-222): places down, start days across, each square the whole trip (the flight and every stay, for the whole party).

    lanes(place, nearby)            the rows: the asked place, its nearby places (partners/places.py NEARBY), and each nearby place joined with it ("Los Angeles + San Diego")
    windows(depart, return_, flex)  the columns: the same nights starting up to `flex` days either side, never before today
    stays_for(lane, window), legs_for(lane, window, home)   what a source searches for one square: two places split the nights and fly in to the first, home from the second
    marks(lanes, windows, totals, budget)   each answered square's marks: "find", "low" (the cheapest start in its lane), "over" (the budget)
    find(lanes, windows, totals)    the discovery: a nearby trip that costs less than, or the same as, the asked place on the same dates, said in words
    order(lanes, windows)           which squares to ask for first: the asked square, then the nearest dates and the likeliest places
    head_start(lanes, windows)      which squares the server starts searching as the page is drawn (F-229): the asked square, its day, its place
    rank(lanes, windows)            each square's turn at LiteAPI's gate (F-229): the head start first, then `order`

Nothing here fetches or invents: a total is a source's (gitaway/gridsource.py `square`), a square still waiting has none and gets no mark. assets/js/tripmatrix.js
marks the squares with the same rules as answers land (`marks`, `find`): change one, change the other (tests_browser/test_tripmatrix.py compares them).
"""

from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta

from gitaway.partners import places as places_

NEARLY_CENTS = 0           # a nearby trip is a find only when it costs no more than the asked place on the same dates (D-860: D-435 let a dearer one through and the page called it a find)
MAX_FLEX = 3
OK, OVER, FAILED, NONE, NO_SAMPLE, BUSY, LIMIT = "ok", "over budget", "failed", "none", "no sample", "busy", "visitor limit"
SAID = {OVER: "Today’s price searches are used up. Back tomorrow.", FAILED: "Couldn’t search just now. Try again in a few minutes.",
        BUSY: "Lots of searches right now. This one is asked again in a moment.",
        LIMIT: "You have used today’s free searches. The squares you have already seen stay open.",
        NONE: "No flights or no stays came back for these dates.", NO_SAMPLE: "No sample prices for this place. Real prices need a LiteAPI key."}
SHORT = {OVER: "Used up today", FAILED: "Couldn’t search", NONE: "None found", NO_SAMPLE: "No sample", BUSY: "Busy, trying again", LIMIT: "Sign in to go on"}
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
    complete: bool = True      # False: the search was stopped at its deadline (F-229), so this is the cheapest found by then


@dataclass(frozen=True)
class RoomPart:
    """One room of a hotel (F-251): what the opened square lets the family choose between. The numbers are a StayPart's own, for that room."""
    room: str
    board: str
    refundable: bool
    due_at_stay_cents: int
    cents: int            # all its nights, the whole party, fees paid at the hotel included
    offer_id: str = ""


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
    offer_id: str = ""    # LiteAPI's offer for this room, verbatim and never shown (F-233: what a booking prebooks); "" for a sample
    address: str = ""     # the hotel's street address from the source, or "" (F-242: the opened square and the pass show it)
    rooms: tuple = ()     # F-251: the hotel's rooms the source gave (the shown room first, at most liteapi.MAX_ROOMS), each a RoomPart; one or none means there is no choice
    hotel_id: str = ""    # F-275: LiteAPI's id of the hotel (for its photos and reviews, asked when the square is opened); "" for a sample


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
    flights: tuple = ()               # F-242: the flights the source gave (the shown one first, at most MAX_ALTS); one or none means there is no choice
    stay_alts: tuple = ()             # F-242: for each stay of `stays`, the stays the source gave for it (the shown one first, at most MAX_ALTS)

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
    words: str            # "Los Angeles + San Diego, $10 less than San Diego alone"
    when: str             # "Dec 12 to 16"

    @property
    def key(self) -> str:
        return key(self.lane, self.window)


MAX_ALTS = 3


def _hotels(sq: Square, stays: tuple) -> list:
    """The StayPart each stay index names, one per stay of the square."""
    alts = sq.stay_alts or tuple((s,) for s in sq.stays)
    return [a[i] for a, i in zip(alts, stays)]


def clamp(sq: Square, pk: tuple) -> tuple:
    """`pk` (the flight index, one index per stay and one room index per stay, as `picks` read them) made to fit `sq`: an index the square does not have (a stale or forged
    form) is the shown part. A room index is read against the hotel chosen, never the shown one."""
    flight = pk[0] if 0 <= pk[0] < len(sq.flights) else 0
    alts = sq.stay_alts or ((),) * len(sq.stays)
    stays = tuple(i if i is not None and 0 <= i < len(a) else 0 for i, a in zip(tuple(pk[1]) + (None,) * len(sq.stays), alts))
    asked = tuple(pk[2]) if len(pk) > 2 else ()
    hotels = _hotels(sq, stays)
    rooms = tuple(i if i is not None and 0 <= i < len(h.rooms) else 0 for i, h in zip(asked + (None,) * len(hotels), hotels))
    return flight, stays, rooms


def with_room(st: StayPart, i: int) -> StayPart:
    """The stay in its `i`th room (the shown room's numbers become that room's), or as it is when it has no such room."""
    if not 0 <= i < len(st.rooms):
        return st
    r = st.rooms[i]
    return replace(st, room=r.room, board=r.board, refundable=r.refundable, due_at_stay_cents=r.due_at_stay_cents, cents=r.cents, offer_id=r.offer_id)


def pick(sq: Square, flight: int = 0, stays: tuple = (), rooms: tuple = ()) -> Square:
    """The square with another flight, other stays and/or other rooms chosen (F-242: "switch in place"; F-251: rooms): `flight` is an index into `sq.flights`, `stays` one index per
    stay into its `stay_alts`, `rooms` one per stay into the chosen hotel's `rooms`. An index the square does not have keeps the shown part, never raises. The total moves with
    the choice."""
    fl, st, rm = clamp(sq, (flight, stays, rooms))
    picked = _hotels(sq, st) if sq.stay_alts else list(sq.stays)
    picked = tuple(with_room(h, i) for h, i in zip(picked, rm + (0,) * len(picked)))
    out = replace(sq, stays=picked) if (any(st) or any(rm)) else sq
    return replace(out, flight=sq.flights[fl]) if sq.flights else out


def picks(flight="", stays="", rooms="") -> tuple:
    """What a form said was chosen (F-242, F-251): ("1", "0,2", "1,0") is (1, (0, 2), (1, 0)). Anything else (a letter, a long number, nothing) is the shown part, never an error."""
    def n(v):
        v = str(v).strip()
        return int(v) if v.isascii() and v.isdecimal() and len(v) <= 2 else None      # isdigit() also passes "²", which int() refuses
    return (n(flight) or 0, tuple(n(x) for x in str(stays).split(",")[:2]), tuple(n(x) for x in str(rooms).split(",")[:2]))


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


def head_start(lanes_, windows_) -> list:
    """((Lane, Window), ...) the server starts searching as the page is drawn (F-229, gitaway/matrixwarm.py): the asked square, the asked start day for every
    place, then the asked place on every other day, the nearest first, earlier dates first on a tie."""
    asked_l = next((x for x in lanes_ if x.asked), lanes_[0])
    j0 = next((j for j, w in enumerate(windows_) if w.asked), 0)
    days = sorted((j for j in range(len(windows_)) if j != j0), key=lambda j: (abs(j - j0), j))
    return [(x, windows_[j0]) for x in sorted(lanes_, key=lambda x: not x.asked)] + [(asked_l, windows_[j]) for j in days]


def rank(lanes_, windows_) -> dict:
    """{square key: its turn at LiteAPI's gate}: the head start's order, then the page's (`order`) for the rest."""
    first = [key(x.key, w.key) for x, w in head_start(lanes_, windows_)]
    rest = [k for k in order(lanes_, windows_) if k not in set(first)]
    return {k: i for i, k in enumerate(first + rest)}


# ---- marks ----------------------------------------------------------------------------------------------------------

def find(lanes_, windows_, totals) -> Find | None:
    """The nearby trip that costs less than or the same as (NEARLY_CENTS = 0) the asked place on the same start day: never a dearer one (D-860): the lowest difference wins, two places together
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
    said = f"{dollars(-diff)} less than {asked.name}{alone}" if diff < 0 else f"the same as {asked.name}{alone}"
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
