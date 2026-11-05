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

# Each place's airport pins and landmark pin on the same schematic canvas (Los Angeles is the three above).
PLACE_MARKS = {
    "la": ((LAX, BUR), LANDMARK),
    "sd": ((MapPoint(190, 112, "SAN"),), MapPoint(236, 56, "Balboa Park")),
    "hi": ((MapPoint(150, 124, "HNL"),), MapPoint(268, 96, "Diamond Head")),
    "nyc": ((MapPoint(286, 112, "JFK"), MapPoint(60, 40, "EWR")), MapPoint(210, 40, "Central Park")),
}

# Per stay: where its area pin sits, and the nearest beach point the "hotel to beach" line runs to.
STAY_PINS = {
    "h1": (MapPoint(134, 34, "Santa Monica"), (100, 44)),
    "h2": (MapPoint(136, 84, "Venice"), (102, 92)),
    "h3": (MapPoint(198, 84, "Downtown"), (104, 66)),
    "sdh1": (MapPoint(120, 96, "Coronado"), (96, 100)),
    "sdh2": (MapPoint(130, 28, "La Jolla"), (100, 34)),
    "sdh3": (MapPoint(190, 76, "Gaslamp"), (104, 84)),
    "hih1": (MapPoint(210, 100, "Waikiki"), (176, 108)),
    "hih2": (MapPoint(150, 84, "Ala Moana"), (124, 94)),
    "hih3": (MapPoint(260, 108, "Diamond Head"), (232, 118)),
    "nych1": (MapPoint(200, 50, "Midtown"), (200, 50)),
    "nych2": (MapPoint(236, 96, "Brooklyn"), (212, 104)),
    "nych3": (MapPoint(168, 112, "Lower Manhattan"), (150, 120)),
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

_HIGHS = {  # typical highs by month, deg F
    "la": (68, 69, 70, 73, 74, 78, 84, 85, 83, 78, 73, 68),
    "sd": (66, 66, 67, 69, 70, 72, 75, 77, 76, 73, 70, 66),
    "hi": (80, 80, 81, 82, 84, 86, 87, 88, 88, 86, 83, 81),
    "nyc": (39, 42, 50, 62, 72, 80, 85, 83, 76, 65, 54, 44),
}
_SKIES = (("sunny", "sun", "sun"), ("clear skies", "sun", "sun"), ("some clouds", "cloud", "sky"),
          ("mostly sunny", "sun", "sun"), ("breezy", "cloud", "sky"))


def _hash(d: date, salt: int = 0) -> int:
    return ((d.toordinal() + salt) * 2654435761) % 2**32


def _is_sample(trip) -> bool:
    return trip.key == "la" and trip.depart == SAMPLE_DEPART and trip.return_ == SAMPLE_RETURN


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
        out.append(Weather(_label(d), _HIGHS[trip.key][d.month - 1] + jitter, sky, icon, fill))
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


_EVENT_POOLS = {
    "sd": (
        ("Tide Pool Walk at Cabrillo", "Point Loma · 10 AM · kids welcome", "sky"),
        ("Family Movie on the Sand", "Coronado Beach · sunset", "grape"),
        ("Fleet Science Night", "Balboa Park · 6 PM", "mint"),
        ("Farmers Market and Street Music", "Little Italy · 8 AM to 1 PM", "sun"),
        ("Sea Lion Watch", "La Jolla Cove · free · all day", "bubble"),
        ("Zoo After Dark", "San Diego Zoo · 5 to 9 PM", "grape"),
    ),
    "hi": (
        ("Hula Under the Stars", "Waikiki · free · 6:30 PM", "mint"),
        ("Sunrise Hike", "Diamond Head · 6 AM · bring water", "sky"),
        ("Friday Night Fireworks", "Waikiki Beach · 7:45 PM", "grape"),
        ("Farmers Market", "Kapiolani · 7 AM to 11 AM", "sun"),
        ("Outrigger Canoe Ride", "Waikiki · 9 AM · kids welcome", "bubble"),
        ("Lei-Making Class", "Ala Moana · 2 PM", "mint"),
    ),
    "nyc": (
        ("Free Concert in the Park", "Central Park · 3 PM", "mint"),
        ("Puppet Show for Kids", "Upper West Side · 11 AM", "grape"),
        ("Brooklyn Flea Market", "DUMBO · 10 AM to 5 PM", "sun"),
        ("Harbor Ferry at Sunset", "Battery Park · 5:30 PM", "sky"),
        ("Natural History Night", "Museum Mile · 6 PM", "bubble"),
        ("Skyline Lights", "Top of the Rock · 8 PM", "grape"),
    ),
}


def events_for(trip) -> list:
    """Up to three events on different days of the trip, picked by date."""
    if _is_sample(trip):
        return EVENTS
    days = trip_days(trip)
    pool = _EVENT_POOLS.get(trip.key, _EVENT_POOL)
    count = min(3, len(days))
    slots = {(k + 1) * len(days) // (count + 1) for k in range(count)}  # spread across the trip
    slots |= set(range(len(days))) - slots if len(slots) < count else set()
    slots = sorted(slots)[:count]
    out, used = [], set()
    for i in slots:
        d = days[i]
        j = _hash(d, 7) % len(pool)
        while j in used:
            j = (j + 1) % len(pool)
        used.add(j)
        title, sub, fill = pool[j]
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


_NEWS_POOLS = {
    "sd": (
        ("Coronado ferry adds weekend sailings", "Downtown to Coronado · {month}"),
        ("Free trolley rides for kids on Sundays", "Downtown · {month}"),
        ("La Jolla Cove opens a new lookout", "La Jolla · {month}"),
        ("Balboa Park museums extend their hours", "Balboa Park · {month}"),
    ),
    "hi": (
        ("Diamond Head trail needs a timed reservation", "Honolulu · {month}"),
        ("Waikiki beach shuttle runs every 20 minutes", "Waikiki · {month}"),
        ("Free hula shows return to Kuhio Beach", "Waikiki · {month}"),
        ("Ala Moana beach park adds shaded picnic tables", "Ala Moana · {month}"),
    ),
    "nyc": (
        ("Extra subway service on weekends", "Midtown to Brooklyn · {month}"),
        ("Brooklyn Bridge Park opens a new playground", "Brooklyn · {month}"),
        ("Statue of Liberty ferries run later", "Battery Park · {month}"),
        ("Central Park carousel open daily", "Central Park · {month}"),
    ),
}


def news_for(trip) -> list:
    """Two news items, picked by the trip's first day and dated to its month."""
    if _is_sample(trip):
        return NEWS
    month = f"{trip.depart:%B}"
    pool = _NEWS_POOLS.get(trip.key, _NEWS_POOL)
    start = _hash(trip.depart, 3) % len(pool)
    return [News(t, s.format(month=month)) for t, s in (pool[(start + i) % len(pool)] for i in range(2))]
