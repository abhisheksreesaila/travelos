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
