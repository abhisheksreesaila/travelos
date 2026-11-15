"""The v2 sky's mood (F-260, D-690..D-697): which of five skies a page wears, chosen by a plain rule from the trip's place and dates.

    beach        today's sky: a sun, clouds, the shore
    snow         a cool sky and a snowy peak
    hike         green and gold, a mountain trail
    celebration  dusk violet and fireworks
    city         a skyline

`choose(place, start, end)` is the rule (pure); `preview(path)` reads the showcase's `?mood=`. A place the table does not know, and a page with no
trip, wear beach (the look the founder loves; a skyline over a town we know nothing about would be a guess). The place kinds are hand-made from partners/places.py's table:
tests/test_moods.py fails when a place is added there without a kind here."""

from datetime import date, timedelta

from gitaway import showcase
from gitaway.partners import places

MOODS = ("beach", "snow", "hike", "celebration", "city")
DEFAULT = "beach"

COAST = ("Los Angeles", "San Diego", "Santa Barbara", "Orange County", "Monterey", "Honolulu", "Maui", "Kauai", "Big Island", "Miami")
PARK = ("Yosemite", "Palm Springs", "Napa", "Zion National Park", "Grand Canyon", "Sedona", "Yellowstone")
CITY = ("Disneyland", "San Francisco", "Las Vegas", "Phoenix", "Seattle", "Portland", "Chicago", "Austin", "Nashville", "New Orleans", "New York", "Boston", "Washington, DC",
        "Orlando", "Anchorage")
MOUNTAIN = ("Denver",)      # beside every ski place (Place.snow): the Rockies' own front door

WINTER = (12, 1, 2, 3)      # the months a mountain is white

# A known big event: (place, first day, last day) as (month, day); a window may wrap the new year. The founder's: New York at New Year.
EVENTS = (("New York", (12, 28), (1, 2)), ("Las Vegas", (12, 30), (1, 1)))


def kind(place) -> str:
    """"coast", "mountain", "park" or "city" for a place of the table; "" for any other place."""
    if place is None or not place.known:
        return ""
    if place.snow or place.name in MOUNTAIN:
        return "mountain"
    return next((k for k, names in (("coast", COAST), ("park", PARK), ("city", CITY)) if place.name in names), "")


def _event(place, start: date, end: date) -> bool:
    for name, (m1, d1), (m2, d2) in EVENTS:
        if place.name != name:
            continue
        for year in range(start.year - 1, end.year + 1):
            first, last = date(year, m1, d1), date(year + (1 if (m2, d2) < (m1, d1) else 0), m2, d2)
            if start <= last and end >= first:
                return True
    return False


def choose(place, start: date | None = None, end: date | None = None) -> str:
    """The mood for a trip to `place` between `start` and `end` (either may be None). A known event wins; then the place's kind: a coast is beach, a mountain is snow in
    winter (the trip's middle day) and hike otherwise, a park is hike, a city is city."""
    k = kind(place)
    if not k:
        return DEFAULT
    start = start or end
    end = end or start
    if start and end and _event(place, start, end):
        return "celebration"
    if k == "coast":
        return "beach"
    if k == "city":
        return "city"
    if k == "mountain" and start and end and (start + (end - start) / 2).month in WINTER:
        return "snow"
    return "hike"


def preview(path: str = "") -> str:
    """The mood a `?mood=` in the address asks for (the showcase only: a real family's sky is never set by a link), else ""."""
    from urllib.parse import parse_qs, urlsplit
    if not showcase.on():
        return ""
    asked = parse_qs(urlsplit(path).query).get("mood", [""])[0]
    return asked if asked in MOODS else ""


def of_text(text: str, start: date | None = None, end: date | None = None) -> str:
    """`choose` for a place a person or a post wrote ("Lake Tahoe, CA")."""
    return choose(places.resolve(text), start, end)
