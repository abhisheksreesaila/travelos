"""Fake community itineraries for the scrapbook page. Sample data only: US units (°F, $)."""

from dataclasses import dataclass, field

PIER = "/assets/photos/santa-monica-beach-pier.jpg"
VENICE = "/assets/photos/venice-beach-los-angeles-hero.jpg"

DAY_COLORS = ["sun", "mint", "grape", "sky", "bubble"]
BOARD_LIMIT = 4
STOP_LIMIT = 6


@dataclass(frozen=True)
class Stop:
    time: str
    title: str
    kind: str = "star"          # icon name from gitaway.icons
    bubble: str = "sun"         # tint of the icon bubble
    booked: bool = False
    tag: str = ""
    tag_color: str = "sun"
    meta: str = ""
    note: str = ""
    photo: str = ""
    photo_alt: str = ""


@dataclass(frozen=True)
class Day:
    n: int
    date: str
    title: str
    weather: str = ""
    stops: list = field(default_factory=list)
    collapsed: bool = False


@dataclass(frozen=True)
class Source:
    byline: str        # "Maya & Theo Adventures · YouTube · 18 min"
    title: str
    thumb: str
    thumb_alt: str
    url: str = "#"


@dataclass(frozen=True)
class Tag:
    label: str
    color: str
    icon: str
    tilt: float = 0


@dataclass(frozen=True)
class Polaroid:
    src: str
    alt: str
    caption: str


@dataclass(frozen=True)
class Itinerary:
    slug: str
    title: str
    headline: str            # h1 text before the underlined accent words
    accent: str
    place: str
    lede: str
    days: list
    tags: list = field(default_factory=list)
    stats: list = field(default_factory=list)   # (value, label) pairs
    source: Source | None = None
    polaroids: list = field(default_factory=list)
    weather: tuple = ("74°F", "mostly sunny")
    route: str = "SFO → LAX · 1h 27m"
    author: str = "the author"
    theme: str = "sunset"


def day_color(n: int) -> str:
    return DAY_COLORS[(n - 1) % len(DAY_COLORS)]


def board_cards(day: Day):
    """The mini cards a board column shows, and how many more stops are hidden."""
    return day.stops[:BOARD_LIMIT], max(0, len(day.stops) - BOARD_LIMIT)


def _sun_tacos() -> Itinerary:
    days = [
        Day(1, "FRI, OCT 16", "Touch down & tacos", "75°F, clear skies", [
            Stop("8:05 AM", "Skylark Air 214 · SFO → LAX", "plane", "sun", booked=True,
                 meta="Lands 9:32 AM, nonstop. Window seats on the left for the coastline on approach."),
            Stop("11:00 AM", "Check in: The Tidewater, Santa Monica", "bed", "sun", booked=True,
                 meta="Two connecting rooms, ocean side. They held our bags until the rooms were ready."),
            Stop("1:00 PM", "Santa Monica Pier & Pacific Park", "star", "bubble", tag="Kid friendly",
                 meta="Ferris wheel first, before the lines build. Wristbands beat single tickets with two kids.",
                 note="The carousel, three times. Worth it."),
            Stop("6:30 PM", "Tacos at Mariscos La Ola", "food", "mint", tag="Pet friendly patio", tag_color="mint",
                 meta="Fish tacos and horchata. Get there before 7 or queue with everyone else."),
        ]),
        Day(2, "SAT, OCT 17", "Canals & boardwalk", "73°F, sunny", [
            Stop("9:00 AM", "Venice Canals stroll", "waves", "mint", tag="Pet friendly", tag_color="mint",
                 meta="Quiet little bridges, stroller friendly, ducks included. About 45 minutes at kid speed."),
            Stop("11:00 AM", "Venice Beach Boardwalk & skate park", "sun", "sun",
                 meta="Watch the skaters from the rail, then sandcastles by lifeguard tower 26.",
                 photo=VENICE, photo_alt="Venice Beach, Los Angeles"),
            Stop("2:30 PM", "Bike the Strand to Marina del Rey", "bike", "sky", tag="Kid friendly",
                 meta="Family tandem rentals by the pier, flat all the way. Around $38 for two hours.",
                 note="Sunscreen. Then more sunscreen."),
        ]),
        Day(3, "SUN, OCT 18", "Steam trains & stars", "70°F, some clouds", [
            Stop("10:00 AM", "Travel Town, Griffith Park", "train", "grape", tag="Kid friendly",
                 meta="Climb aboard old steam engines, then ride the little train loop. Free to walk in.",
                 note="Our 4-year-old: best day of his life."),
            Stop("1:00 PM", "Picnic under the oaks", "tree", "mint", tag="Pet friendly", tag_color="mint",
                 meta="Grab sandwiches on the way in. Shade and restrooms near the merry-go-round."),
            Stop("4:00 PM", "Griffith Observatory at sunset", "star", "grape",
                 meta="Get there by 4, parking fills fast. The free telescopes open after dark."),
        ]),
        Day(4, "MON, OCT 19", "Dinos & tar pits", "72°F, sunny", [
            Stop("9:30 AM", "Dinosaur hall", "star", "sky", tag="Kid friendly",
                 meta="Go straight to the dinosaur hall before the school groups arrive."),
            Stop("1:00 PM", "La Brea Tar Pits", "tree", "mint",
                 meta="Watch the fossil lab through the glass, then walk the park around the pits."),
            Stop("5:00 PM", "Pool time", "waves", "sun",
                 meta="Back at the hotel for a long, lazy swim before an early dinner."),
        ], collapsed=True),
        Day(5, "TUE, OCT 20", "Market brunch, fly home", "71°F, clear skies", [
            Stop("9:00 AM", "Farmers Market brunch", "food", "bubble",
                 meta="Fresh fruit, pastries and a very good breakfast burrito."),
            Stop("11:30 AM", "Check out: The Tidewater", "bed", "sun", booked=True,
                 meta="Late checkout kept the rooms until noon."),
            Stop("2:10 PM", "Skylark Air 219 · LAX → SFO", "plane", "sun", booked=True,
                 meta="Home by 3:37 PM, with time for a proper nap."),
        ], collapsed=True),
    ]
    return Itinerary(
        slug="sun-tacos-and-tide-pools",
        title="Sun, tacos & tide pools",
        headline="Sun, tacos & tide pools: LA with",
        accent="little ones",
        place="Los Angeles, California",
        lede="Five sunny days from San Francisco to Santa Monica, planned by a family of four who wanted "
             "beach mornings, museum afternoons and early bedtimes.",
        days=days,
        tags=[Tag("Kid friendly", "sun", "kid", -3), Tag("Pet friendly · 3 stops", "mint", "paw", 2),
              Tag("Easy pace", "sky", "clock", -1.5)],
        stats=[("5 days", "Fri Oct 16 – Tue Oct 20"), ("4 people", "2 adults, kids 4 & 7"),
               ("$3,480", "all-in, as they booked it"), ("312", "families forked it")],
        source=Source("Maya & Theo Adventures · YouTube · 18 min", "Our LA family week: what we'd do again",
                      VENICE, "Venice Beach boardwalk in Los Angeles"),
        polaroids=[Polaroid(PIER, "Santa Monica Pier and beach", "the pier at golden hour"),
                   Polaroid(VENICE, "Venice Beach, Los Angeles", "Venice, day two")],
        author="Maya & Theo",
    )


ITINERARIES = {t.slug: t for t in [_sun_tacos()]}


def get(slug: str) -> Itinerary | None:
    return ITINERARIES.get(slug)
