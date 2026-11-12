"""The trip grid's sums (F-217): every flight against every stay, as one number a square.

    build(trip, flights, stays, drive_min, clock_shift)   a Grid: a Cell for each flight and stay (the whole trip's cost, and the first day as each traveler lives it)
    Grid.lowest, Grid.easiest(who), Grid.tone(...)        which square is marked, and how each one is drawn
    Flight, Stay                                          what a source (gitaway/gridsource.py) hands in: plain facts, no pages

Nothing here is invented or fetched: a fact a source did not give (a lift, an airline's pet rule) is never scored, and the day says to ask instead.
The first day's times are sums of what the flight and the drive say, with two stated allowances: up BEFORE_FLIGHT minutes before take-off, BAGS minutes
from landing to the kerb. The ease score is a rough weighting of ours (D-418), shown as a word, never as a number.
"""

from dataclasses import dataclass, field

BEFORE_FLIGHT = 150      # minutes from getting up to take-off
BAGS = 45                # minutes from landing to leaving the airport
EARLY = 5 * 60           # getting up before 5:00 AM is an early start
LATE = 21 * 60           # reaching the door after 9:00 PM is past a kid's bedtime
WHOS = ("kids", "senior", "pet")
WHO_NAMES = {"kids": "Kids’ day", "senior": "Their day", "pet": "Pet’s day"}
WORDS = ((0, "easy day"), (2, "fair day"), (5, "hard day"))
VERY_HARD = "very hard day"
HARD_FROM = 6            # a score from here is drawn greyed, like a square over budget
PET_TAG = "Pet friendly"


@dataclass(frozen=True)
class Flight:
    id: str
    name: str            # "Skylark Air 214"
    airport: str         # where it lands
    depart_min: int      # minutes after midnight, at home
    arrive_min: int      # minutes after midnight, there; before depart_min means the next morning
    stops: int
    cents: int           # for the whole party
    each_cents: int      # a person
    stops_text: str = "Nonstop"
    overnight: bool = False   # lands the next day


@dataclass(frozen=True)
class Stay:
    id: str
    name: str
    area: str            # "Santa Monica"
    detail: str          # "2 rooms · 3 min walk to the beach"
    cents: int           # all the nights, for the party
    tags: tuple = ()
    rating: str = ""


@dataclass(frozen=True)
class Day:
    who: str
    score: int
    word: str            # "easy day"
    facts: tuple         # ((label, value), ...), three of them
    verdict: str
    note: str            # the allowance or the thing to ask, said small


@dataclass(frozen=True)
class Cell:
    flight: Flight
    stay: Stay
    cents: int
    days: dict           # who -> Day


@dataclass(frozen=True)
class Grid:
    flights: tuple
    stays: tuple
    whos: tuple                          # whose first day is worked out, in WHOS order
    cells: dict = field(default_factory=dict)      # (flight id, stay id) -> Cell

    def cell(self, flight_id, stay_id) -> Cell | None:
        return self.cells.get((flight_id, stay_id))

    @property
    def lowest(self) -> Cell | None:
        return min(self.cells.values(), key=lambda c: (c.cents, c.flight.id, c.stay.id), default=None)

    def easiest(self, who) -> Cell | None:
        """The easiest first day for `who`, the cheaper of two as easy; None when nobody like that is going."""
        if who not in self.whos:
            return None
        return min(self.cells.values(), key=lambda c: (c.days[who].score, c.cents, c.flight.id, c.stay.id), default=None)

    def tone(self, cell, pick, lens="price", who="", budget_cents=None) -> str:
        """How a square is drawn: "mine" (the pick), "best" (the lowest, or the easiest under the Ease lens), "bad" (over budget, or a very hard day), else "plain"."""
        if pick and (cell.flight.id, cell.stay.id) == pick:
            return "mine"
        if lens == "ease" and who in self.whos:
            return "best" if cell is self.easiest(who) else ("bad" if cell.days[who].score >= HARD_FROM else "plain")
        if cell is self.lowest:
            return "best"
        return "bad" if budget_cents and cell.cents > budget_cents else "plain"


def clock(minutes: int) -> str:
    minutes = round(minutes / 5) * 5 % 1440
    h, m = divmod(minutes, 60)
    return f"{h % 12 or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"


def word(score: int) -> str:
    return next((w for top, w in WORDS if score <= top), VERY_HARD)


def day(who, flight: Flight, stay: Stay, drive_min: int | None, clock_shift: int = 0) -> Day:
    """The first day for one kind of traveler. `drive_min` is the airport-to-stay drive (None: not known, so the day ends at the kerb); `clock_shift` is how many
    minutes the place's clocks run ahead of home's (0: the same time)."""
    up = flight.depart_min - BEFORE_FLIGHT
    door = (flight.arrive_min + BAGS + (drive_min or 0)) % 1440
    late = not flight.overnight and (door > LATE or door < EARLY)
    early = up < EARLY
    where = "At the door" if drive_min is not None else "Out of the airport"
    allow = f"Up {BEFORE_FLIGHT // 60} h {BEFORE_FLIGHT % 60} min before take-off; {BAGS} min for bags" + (f", then a {drive_min} min drive." if drive_min is not None else ".")
    score = (5 if flight.overnight else 0) + (2 if early else 0)
    if who == "kids":
        score += (3 if late else 0) + 2 * flight.stops
        third = ("Feels like", clock(door - clock_shift)) if clock_shift else ("Changes", str(flight.stops) if flight.stops else "None")
        if flight.overnight:
            verdict = "A night on the plane. You arrive before the room is ready."
        elif late:
            verdict = "You reach the stay past bedtime" + (f", though it feels like {clock(door - clock_shift)} to the kids." if clock_shift > 0 else ".")
        elif early:
            verdict = "A very early start, then an easy rest of the day."
        elif flight.stops:
            verdict = "A change of planes on the way, with the kids in tow."
        else:
            verdict = "An easy day: a normal morning and there in good time."
        return Day(who, score, word(score), (("Up at", clock(up)), (where, clock(door)), third), verdict, allow)
    if who == "senior":
        score += (2 if late else 0) + 3 * flight.stops
        if flight.overnight:
            verdict = "A night on the plane is a lot to ask."
        elif flight.stops:
            verdict = "A change of planes: ask the airline for help between gates when you book."
        elif late:
            verdict = "A late arrival, but no change of planes."
        elif early:
            verdict = "A very early start, and no change of planes."
        else:
            verdict = "A gentle day: no change of planes and there in good time."
        return Day(who, score, word(score), (("Changes", str(flight.stops) if flight.stops else "None"), ("Up at", clock(up)), (where, clock(door))), verdict,
                   "We do not know this stay's lifts or steps. Ask for a ground-floor or step-free room.")
    takes = PET_TAG in stay.tags
    score = (6 if not takes else 0) + 2 * flight.stops + (2 if flight.overnight else 0)
    verdict = (f"{stay.name} is not listed as taking pets. Ask before you book." if not takes
               else ("The stay takes pets, but a change of planes is hard on an animal." if flight.stops else "The stay takes pets, and the flight is one hop."))
    return Day(who, score, word(score), (("Stay", "Takes pets" if takes else "Ask first"), ("Changes", str(flight.stops) if flight.stops else "None"), (where, clock(door))), verdict,
               "We do not know this airline's rule for animals in the cabin. Ask the airline.")


def build(flights, stays, whos=(), drive_min=None, clock_shift: int = 0) -> Grid:
    """`drive_min(flight, stay)` gives the drive's minutes or None; `whos` are the travelers whose day to work out (any of WHOS)."""
    whos = tuple(w for w in WHOS if w in whos)
    cells = {}
    for s in stays:
        for f in flights:
            minutes = drive_min(f, s) if drive_min else None
            cells[(f.id, s.id)] = Cell(f, s, f.cents + s.cents, {w: day(w, f, s, minutes, clock_shift) for w in whos})
    return Grid(tuple(flights), tuple(stays), whos, cells)
