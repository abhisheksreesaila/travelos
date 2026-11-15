"""What the widget rail beside the matrix knows (F-251, D-620..): plain functions, no framework. The rail follows the place you look at (a lane) and the start day you opened, and every
widget has one real source or is not shown; the pieces with no source are the showcase's own made-up samples, said so on their widget, and nothing off the showcase.

    sky(place, first)                 weather.TripWeather for five days from `first` (typical days say so; MET Norway's credit is `weather.notes`)
    where(s, lane)                    Where: the airport's drive to the stay's town and the stay's town to the asked place (OSRM, typical, no live traffic), the home airport's distance in a straight line
    cheaper_airport(s, lane, w, ...)  another airport near the asked place whose flights, already known for these days, cost less (a real fare compare, nothing is searched), or None
    breakfast(sq)                     the hotels of a square whose rate includes breakfast (the source's own board)
    about(place)                      placefacts' sourced facts for the place, each with its page
    sample(place)                     the showcase's made-up Uber, traffic, food and what's-on for a few places, or None (never off the showcase: the caller checks `showcase.on()`)

Nothing is invented: a drive no router answered, a fare not known and a place with no facts are left out, and a widget with nothing left is not drawn (gitaway/pages/v2rail.py).
"""

import math
from dataclasses import dataclass
from datetime import timedelta

from gitaway import airportdrive, placefacts, tripmatrix as tm

DAYS = 5
MILES_PER_KM = 0.621371


@dataclass(frozen=True)
class Where:
    airport: str                # the stay's airport (the lane's first place's)
    town: str                   # where the stay is, in words
    airport_min: int | None     # minutes by car from the airport to the town, or None
    asked: str                  # the asked place's name when the lane is not the asked place, else ""
    asked_min: int | None       # minutes by car from the stay's town to the asked place's town, or None
    home: str                   # the home airport
    home_miles: int | None      # a straight line from the home airport to this one, in miles

    @property
    def rows(self) -> int:
        return sum(x is not None for x in (self.airport_min, self.asked_min, self.home_miles))


@dataclass(frozen=True)
class Cheaper:
    iata: str              # the cheaper airport
    place: str             # the place it serves
    lane: str              # that place's lane on the matrix
    base_iata: str         # the airport asked for
    save_cents: int        # how much less its flights cost for the whole party, both ways
    trip_cents: int        # the whole trip there minus the whole trip at the asked place (negative: cheaper), same dates


def sky(place: str, first):
    """Five days of weather for `place` from `first`: weather.trip_weather's, so a forecast where it reaches and NOAA's typical days labelled as such, else nothing for a day."""
    from gitaway.pages.skystrip import weather_for      # here: the pages import this module
    return weather_for(place, first, first + timedelta(days=DAYS - 1))


def miles(a: str, b: str) -> int | None:
    """Statute miles in a straight line between two airports we have coordinates for, else None."""
    p, q = airportdrive.AIRPORTS.get(str(a or "").upper()), airportdrive.AIRPORTS.get(str(b or "").upper())
    if not p or not q or a == b:
        return None
    (la1, lo1), (la2, lo2) = map(lambda c: tuple(map(math.radians, c)), (p, q))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return round(2 * 6371 * math.asin(math.sqrt(h)) * MILES_PER_KM)


def where(s, lane, look_up=True) -> Where:
    """The drives for the lane's first place. `look_up` False only reads what is already known (no call), as a page drawn before its answers land does."""
    place = lane.places[0]
    ask = airportdrive.drive if look_up else (lambda i, t: airportdrive.kept(i, t))
    drive = ask(place.iata, place.town) if place.iata else None
    asked = "" if lane.asked or s.place.name == place.name else s.place.name
    between = (airportdrive.between if look_up else airportdrive.kept_between)(place.town, s.place.town) if asked else None
    return Where(place.iata, place.city, drive.minutes if drive else None, asked, between.minutes if between else None, s.home, miles(s.home, place.iata))


def cheaper_airport(s, lane, w, lanes, known) -> Cheaper | None:
    """Among the single-place lanes, an airport other than this lane's whose flights for the same dates cost less than this lane's (both already known: `known(lane, w)` answers a
    square from what is kept, never a search). The biggest saving wins. A lane with no known square, a different airport that is dearer or the same airport: nothing."""
    here = known(lane, w)
    if here is None or not here.ok or not lane.places[0].iata:
        return None
    best = None
    for other in lanes:
        if other.combo or other.key == lane.key or not other.places[0].iata or other.places[0].iata == lane.places[0].iata:
            continue
        sq = known(other, w)
        if sq is None or not sq.ok:
            continue
        save = here.flight.cents - sq.flight.cents
        if save > 0 and (best is None or save > best.save_cents):
            best = Cheaper(other.places[0].iata, other.places[0].name, other.key, lane.places[0].iata, save, sq.cents - here.cents)
    return best


def breakfast(sq) -> list:
    """The hotels of the square (every one the source gave, each once) whose rate includes breakfast."""
    seen, out = set(), []
    for alts in (sq.stay_alts or tuple((st,) for st in sq.stays)):
        for st in alts:
            for r in (st.rooms or (tm.RoomPart(st.room, st.board, st.refundable, st.due_at_stay_cents, st.cents, st.offer_id),)):
                if r.board == "breakfast" and st.name not in seen:
                    seen.add(st.name)
                    out.append((st, r))
    return out


def about(place) -> tuple:
    return placefacts.facts(place.name if hasattr(place, "name") else place)


# ---- the showcase's own made-up widgets -------------------------------------------------------------------------------------------------------------------
# Nothing here is a fact: it is the prototype's sample content, shown only on the showcase and labelled Sample on its widget. A place not listed has none.
# food: (name, what, minutes away, the interests it fits)
SAMPLE = {
    "San Diego": {"uber": ("$21–26", "$34–41"), "traffic": (22, 18, 27, 41, 33, 19), "route": "I-5, the airport to the beach",
                  "food": (("Masala Coast", "Indian · veg thali", 6, ("vegetarian",)), ("Green Lantern Kitchen", "Vegetarian · kids menu", 10, ("vegetarian", "kids")),
                           ("Harbor Fish Shack", "Seafood · by the water", 8, ("seafood",)), ("Bean & Wave", "Cafe · pastries", 4, ("cafes",))),
                  "trend": (("Bay boat parade of lights", "Weekend evenings in December"), ("Whale-watching season opens", "Grey whales head south from mid December"), ("Garden lights at the park", "Night walks, family tickets"))},
    "Los Angeles": {"uber": ("$32–39", "$48–58"), "traffic": (38, 31, 46, 64, 52, 29), "route": "I-405, the airport to Santa Monica",
                    "food": (("Saffron & Salt", "Indian · South Indian dosas", 9, ("vegetarian",)), ("Plant Table", "Vegetarian · all day", 5, ("vegetarian", "kids")),
                             ("Pier Oyster Bar", "Seafood", 7, ("seafood",)), ("Sunlit Cafe", "Cafe · breakfast all day", 3, ("cafes",))),
                    "trend": (("Holiday light walk at the zoo", "Evenings through December"), ("Observatory telescopes open late", "Clear-night weekends"), ("Pier ice rink", "Family sessions in the mornings"))},
    "Orange County": {"uber": ("$24–29", "$37–45"), "traffic": (24, 21, 30, 48, 36, 22), "route": "SNA to Newport Beach",
                      "food": (("Curry Leaf House", "Indian · Gujarati thali", 11, ("vegetarian",)), ("Seed Kitchen", "Vegetarian · kid friendly", 7, ("vegetarian", "kids")),
                               ("Dory Dock", "Seafood · harbor view", 9, ("seafood",)), ("Morning Tide Cafe", "Cafe", 5, ("cafes",))),
                      "trend": (("Harbor boat parade", "Newport, mid December"), ("Theme park holiday nights", "Book the early entry"), ("Tide-pool walks", "Low tides this month"))},
    "Santa Barbara": {"uber": ("$27–33", "$41–49"), "traffic": (16, 14, 19, 26, 21, 15), "route": "SBA to the waterfront",
                      "food": (("Spice of Mission", "Indian · veg-friendly", 5, ("vegetarian",)), ("Garden Fork", "Vegetarian", 4, ("vegetarian",)),
                               ("Wharf Catch", "Seafood · on the wharf", 6, ("seafood",)), ("Funk Zone Coffee", "Cafe", 3, ("cafes",))),
                      "trend": (("Parade of lights at the harbor", "Mid December"), ("Butterfly grove season", "Monarchs overwinter here"), ("Wharf seafood night market", "Fridays"))},
}
TIMES = ("12p", "2p", "4p", "5p", "7p", "9p")


def sample(place) -> dict | None:
    return SAMPLE.get(place.name if hasattr(place, "name") else place)


def fits(food, interests) -> list:
    """The sample places that fit what the family is into (the first two when nothing is picked or nothing fits)."""
    want = set(interests or ())
    match = [f for f in food if want & set(f[3])]
    return (match or list(food))[:3]
