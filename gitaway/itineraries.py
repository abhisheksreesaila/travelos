"""Fake community itineraries for the scrapbook page. Sample data only: US units (°F, $)."""

from dataclasses import dataclass, field
from urllib.parse import urlsplit

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
    url: str = ""


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
    forks: int = 0                               # how many families forked this trip
    source: Source | None = None
    polaroids: list = field(default_factory=list)
    weather: tuple = ("74°F", "mostly sunny")
    route: str = "SFO → LAX · 1h 27m"
    author: str = "the author"
    theme: str = "sunset"


def safe_href(url) -> str:
    """The url when it is an http(s) link with a host, else "". User-written source links never reach an href otherwise."""
    if not isinstance(url, str) or any(c in url for c in "\x00\r\n\t "):
        return ""
    parts = urlsplit(url.strip())
    return url.strip() if parts.scheme in ("http", "https") and parts.netloc else ""


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
        Day(5, "TUE, OCT 20", "Market brunch, fly home", "77°F, warm and clear", [
            Stop("9:00 AM", "Farmers Market brunch", "food", "bubble",
                 meta="Fresh fruit, pastries and a very good breakfast burrito."),
            Stop("11:30 AM", "Check out: The Tidewater", "bed", "sun", booked=True,
                 meta="Late checkout kept the rooms until noon."),
            Stop("2:10 PM", "Skylark Air 219 · LAX → SFO", "plane", "sun", booked=True,
                 meta="Home by 3:37 PM, with time for a proper nap."),
        ], collapsed=True),
    ]
    forks = 312
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
               ("$3,480", "all-in, as they booked it"), (str(forks), "families forked it")],
        source=Source("Maya & Theo Adventures · YouTube · 18 min", "Our LA family week: what we'd do again",
                      VENICE, "Venice Beach boardwalk in Los Angeles", "https://www.youtube.com/"),
        polaroids=[Polaroid(PIER, "Santa Monica Pier and beach", "the pier at golden hour"),
                   Polaroid(VENICE, "Venice Beach, Los Angeles", "Venice, day two")],
        author="Maya & Theo",
        forks=forks,
    )


def _short(slug, title, headline, accent, place, lede, days, tags, author, forks, stats, route, source=None):
    """A compact community trip: a few days, a few stops each, sticker collage instead of photos."""
    return Itinerary(slug=slug, title=title, headline=headline, accent=accent, place=place, lede=lede, days=days,
                     tags=tags, stats=[*stats, (str(forks), "families forked it")], forks=forks, source=source, author=author, route=route)


def _la_for_two() -> Itinerary:
    days = [
        Day(1, "THU, NOV 5", "Arrive and unwind", "72°F, clear", [
            Stop("11:00 AM", "Late brunch in Silver Lake", "food", "sun", meta="Slow start. Share the lemon ricotta pancakes."),
            Stop("4:00 PM", "Golden hour at Griffith Park", "tree", "mint", tag="Couple friendly", tag_color="bubble",
                 meta="Walk the Hollywood Reservoir loop, then the sunset from the Observatory lawn."),
        ]),
        Day(2, "FRI, NOV 6", "Beach, no alarm", "74°F, sunny", [
            Stop("10:30 AM", "Coffee and the Venice Canals", "waves", "mint", meta="Quiet bridges before the crowds. Easy flat walking."),
            Stop("2:00 PM", "Sunset sail from Marina del Rey", "waves", "sky", tag="Couple friendly", tag_color="bubble",
                 meta="Two-hour sunset sail, around $85 each. Bring a jacket."),
        ]),
        Day(3, "SAT, NOV 7", "Museums and wine", "71°F, some clouds", [
            Stop("11:00 AM", "The Getty Center", "sight", "grape", meta="Free entry, parking is the only charge. Gardens first."),
            Stop("6:30 PM", "Dinner in Los Feliz", "food", "bubble", tag="Couple friendly", tag_color="bubble",
                 meta="Book the corner table by the window."),
        ]),
        Day(4, "SUN, NOV 8", "One more morning", "73°F, sunny", [
            Stop("9:30 AM", "Farmers market and a long breakfast", "food", "sun", meta="Fruit, pastries and nowhere to be."),
        ]),
    ]
    return _short("la-for-two-slow-mornings", "LA for two, slow mornings", "Slow mornings, long dinners: LA for", "two",
                  "Los Angeles, California", "Four unhurried days for a couple: late breakfasts, golden hours and one very good sunset sail.",
                  days, [Tag("Couple friendly", "bubble", "couple", -3), Tag("Easy pace", "sky", "clock", 2)], "Jo & Dee", 128,
                  [("4 days", "Thu Nov 5 – Sun Nov 8"), ("2 people", "a couple's long weekend")], "SFO → LAX · 1h 27m")


def _big_sur() -> Itinerary:
    days = [
        Day(1, "SAT, MAR 6", "Monterey and the coast road", "62°F, fog then sun", [
            Stop("10:00 AM", "Dog-friendly beach at Carmel", "waves", "mint", tag="Pet friendly", tag_color="mint",
                 meta="Off-leash on the sand, on-leash in town. Bring water."),
            Stop("2:00 PM", "Bixby Bridge pull-out", "sight", "sky", meta="Park on the north side. Dogs welcome on a short leash."),
        ]),
        Day(2, "SUN, MAR 7", "Trails and tails", "64°F, sunny", [
            Stop("9:00 AM", "Pfeiffer Beach and Keyhole Rock", "waves", "mint", tag="Pet friendly", tag_color="mint",
                 meta="Dogs allowed on the beach. Purple sand if you look."),
            Stop("1:00 PM", "Picnic at Julia Pfeiffer Burns", "tree", "mint", tag="Pet friendly", tag_color="mint",
                 meta="The overlook trail allows leashed dogs for the waterfall view."),
        ]),
        Day(3, "MON, MAR 8", "Drive home slowly", "63°F, clear", [
            Stop("11:00 AM", "Nepenthe terrace lunch", "food", "sun", tag="Pet friendly patio", tag_color="mint",
                 meta="Ask for the terrace. Water bowls are out."),
        ]),
    ]
    src = Source("@trailsandtails · Instagram · reel", "Big Sur with a dog, the whole drive", "", "", "https://www.instagram.com/")
    return _short("dog-friendly-big-sur-drive", "Dog-friendly Big Sur drive", "A coast road for you and the dog:", "Big Sur",
                  "Monterey to Big Sur, California", "Three days down Highway 1 with a dog who has strong opinions about beaches.",
                  days, [Tag("Pet friendly · 4 stops", "mint", "paw", -3)], "@trailsandtails", 87,
                  [("3 days", "Sat Mar 6 – Mon Mar 8"), ("1 dog", "plus two people")], "SFO → MRY · 1h 5m", source=src)


def _san_diego() -> Itinerary:
    days = [
        Day(1, "FRI, JUN 12", "Zoo day", "76°F, sunny", [
            Stop("9:00 AM", "San Diego Zoo, the early shift", "star", "sun", tag="Kid friendly",
                 meta="Pandas first, then the bus tour. Pack lunch, the snacks add up."),
            Stop("4:00 PM", "Pool at the motel", "waves", "sky", meta="A cheap motel with a pool beats a fancy one without."),
        ]),
        Day(2, "SAT, JUN 13", "Tide pools", "72°F, breezy", [
            Stop("10:00 AM", "Cabrillo tide pools at low tide", "waves", "mint", tag="Kid friendly",
                 meta="Check the tide table. Look, don't touch. Free after the parking."),
            Stop("1:00 PM", "Fish tacos at Ocean Beach", "food", "sun", meta="Under $10 a head."),
        ]),
        Day(3, "SUN, JUN 14", "Beach and bikes", "75°F, sunny", [
            Stop("9:30 AM", "Coronado beach and sandcastles", "sun", "sun", tag="Kid friendly",
                 meta="Wide and flat, gentle waves."),
        ]),
        Day(4, "MON, JUN 15", "Go home happy", "74°F, sunny", [
            Stop("10:00 AM", "Balboa Park, one museum only", "sight", "grape", tag="Kid friendly",
                 meta="Pick the science center and skip the rest."),
        ]),
    ]
    return _short("san-diego-on-a-budget", "San Diego on a budget", "Cheap and cheerful:", "San Diego with kids",
                  "San Diego, California", "Four sunny days for a family of four that came in well under the usual price.",
                  days, [Tag("Kid friendly", "sun", "kid", -3), Tag("Budget", "sky", "clock", 2)], "the Okafors", 96,
                  [("4 days", "Fri Jun 12 – Mon Jun 15"), ("4 people", "2 adults, kids 5 & 9")], "SFO → SAN · 1h 35m")


ITINERARIES = {t.slug: t for t in [_sun_tacos(), _la_for_two(), _big_sur(), _san_diego()]}


def get(slug: str) -> Itinerary | None:
    return ITINERARIES.get(slug)
