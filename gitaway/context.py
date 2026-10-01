"""Sample context for the workspace panes (F-016): weather, events, news and the schematic map.

Everything here is invented sample data for Los Angeles on the trip dates (Fri Oct 16 - Tue Oct 20, 2026).
No real forecast, event or news source is used; the panes label it as sample data.
"""

from dataclasses import dataclass

SAMPLE_NOTE = "Sample data"


@dataclass(frozen=True)
class Weather:
    day: str        # "Fri 16"
    temp_f: int
    sky: str
    icon: str       # gitaway.icons name
    fill: str       # tint token name


# Temperatures equal the itinerary page's per-day weather for the sample trip (a test keeps them in step).
WEATHER = [
    Weather("Fri 16", 75, "clear skies", "sun", "sun"),
    Weather("Sat 17", 73, "sunny", "sun", "sun"),
    Weather("Sun 18", 70, "some clouds", "cloud", "sky"),
    Weather("Mon 19", 72, "sunny", "sun", "sun"),
    Weather("Tue 20", 77, "warm", "sun", "sun"),
]


@dataclass(frozen=True)
class Event:
    when: str
    title: str
    sub: str
    fill: str


EVENTS = [
    Event("Sat 17", "Boardwalk Chalk Festival", "Venice · free · all day", "mint"),
    Event("Sun 18", "Family Movie on the Lawn", "Griffith Park · sunset", "grape"),
    Event("Mon 19", "Tide Pool Ranger Walk", "Point Dume · 10 AM · kids welcome", "sky"),
]


@dataclass(frozen=True)
class News:
    title: str
    sub: str


NEWS = [
    News("Pier parking lot reopens after repaving", "Santa Monica · this week"),
    News("Extra Metro E Line trains on weekends", "Downtown to the coast · through October"),
]


@dataclass(frozen=True)
class MapPoint:
    x: int
    y: int
    label: str


# Schematic coordinates on a 320 x 150 canvas: ocean on the left, coast running down the page.
MAP_SIZE = (320, 150)
LAX = MapPoint(182, 124, "LAX")
BUR = MapPoint(284, 20, "BUR")
LANDMARK = MapPoint(236, 60, "Griffith Park")

# Per stay: where its area pin sits, and the nearest beach point the "hotel to beach" line runs to.
STAY_PINS = {
    "h1": (MapPoint(134, 34, "Santa Monica"), (100, 44)),
    "h2": (MapPoint(136, 84, "Venice"), (102, 92)),
    "h3": (MapPoint(198, 84, "Downtown"), (104, 66)),
}


def map_for_stay(stay):
    """Pin and beach-line figures for one stay Offer, plus the caption shown under the map."""
    pin, (bx, by) = STAY_PINS[stay.id]
    return {
        "x": pin.x, "y": pin.y, "label": pin.label, "bx": bx, "by": by,
        "caption": f"{stay.name}, {stay.headline} · {stay.detail.split(' · ')[-1]}",
    }


# ---- context that follows the trip (F-036) --------------------------------------------------------------------------
# The constants above are the sample trip (Oct 16-20, 2026). Any other trip gets invented data made from its own dates:
# the same date always gives the same weather, so a day does not change when the trip around it does.

from datetime import date, timedelta

SAMPLE_DEPART, SAMPLE_RETURN = date(2026, 10, 16), date(2026, 10, 20)
WEATHER_DAYS_SHOWN = 10  # a long trip shows its first ten days; the pane says how many there are

_LA_HIGHS = (68, 69, 70, 73, 74, 78, 84, 85, 83, 78, 73, 68)  # typical LA highs by month, deg F
_SKIES = (("sunny", "sun", "sun"), ("clear skies", "sun", "sun"), ("some clouds", "cloud", "sky"),
          ("mostly sunny", "sun", "sun"), ("breezy", "cloud", "sky"))


def _hash(d: date, salt: int = 0) -> int:
    return ((d.toordinal() + salt) * 2654435761) % 2**32


def _is_sample(trip) -> bool:
    return trip.depart == SAMPLE_DEPART and trip.return_ == SAMPLE_RETURN


def trip_days(trip) -> list:
    """Every date of the trip, departure to return."""
    return [trip.depart + timedelta(days=i) for i in range((trip.return_ - trip.depart).days + 1)]


def _label(d: date) -> str:
    return f"{d:%a} {d.day}"


def weather_for(trip) -> list:
    """One Weather per trip day: the sample's own for the sample trip, else invented from each date."""
    if _is_sample(trip):
        return WEATHER
    out = []
    for d in trip_days(trip):
        h = _hash(d)
        jitter = (h >> 8) % 9 - 4
        sky, icon, fill = _SKIES[(h >> 16) % len(_SKIES)]
        if d.month in (12, 1, 2, 3) and jitter <= -3:
            sky, icon, fill = "light showers", "cloud", "sky"
        out.append(Weather(_label(d), _LA_HIGHS[d.month - 1] + jitter, sky, icon, fill))
    return out


_EVENT_POOL = (
    ("Boardwalk Chalk Festival", "Venice · free · all day", "mint"),
    ("Family Movie on the Lawn", "Griffith Park · sunset", "grape"),
    ("Tide Pool Ranger Walk", "Point Dume · 10 AM · kids welcome", "sky"),
    ("Farmers Market and Street Music", "Santa Monica · 9 AM to 1 PM", "sun"),
    ("Kite Day on the Beach", "Manhattan Beach · free · afternoon", "bubble"),
    ("Planetarium Family Show", "Griffith Observatory · 6 PM", "grape"),
    ("Food Truck Roundup", "Downtown · 5 to 9 PM", "sun"),
    ("Sunset Jazz on the Pier", "Santa Monica · free · 6 PM", "mint"),
)


def events_for(trip) -> list:
    """Up to three events on different days of the trip, picked by date."""
    if _is_sample(trip):
        return EVENTS
    days = trip_days(trip)
    count = min(3, len(days))
    slots = {(k + 1) * len(days) // (count + 1) for k in range(count)}  # spread across the trip
    slots |= set(range(len(days))) - slots if len(slots) < count else set()
    slots = sorted(slots)[:count]
    out, used = [], set()
    for i in slots:
        d = days[i]
        j = _hash(d, 7) % len(_EVENT_POOL)
        while j in used:
            j = (j + 1) % len(_EVENT_POOL)
        used.add(j)
        title, sub, fill = _EVENT_POOL[j]
        out.append(Event(_label(d), title, sub, fill))
    return out


_NEWS_POOL = (
    ("Pier parking lot reopens after repaving", "Santa Monica · {month}"),
    ("Extra Metro E Line trains on weekends", "Downtown to the coast · through {month}"),
    ("Free shuttle links the beach towns", "South Bay · {month}"),
    ("Griffith Park trails open early on weekends", "Los Feliz · {month}"),
    ("New bike lanes along the Venice boardwalk", "Venice · {month}"),
    ("Aquarium adds late hours for families", "Long Beach · {month}"),
)


def news_for(trip) -> list:
    """Two news items, picked by the trip's first day and dated to its month."""
    if _is_sample(trip):
        return NEWS
    month = f"{trip.depart:%B}"
    start = _hash(trip.depart, 3) % len(_NEWS_POOL)
    return [News(t, s.format(month=month)) for t, s in (_NEWS_POOL[(start + i) % len(_NEWS_POOL)] for i in range(2))]
