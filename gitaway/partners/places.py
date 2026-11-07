"""Any destination, by name (F-198): a free-text place to what the booking lanes need. No fixed list of places limits a trip.

    resolve(text, iata="")   the Place for what a person typed ("Lake Tahoe", "lake tahoe, ca", "Bend, Oregon"); `iata` is a three-letter airport they gave, which wins
    clean_iata(text)         the airport code in capitals, or "" when it is not three letters

A Place knows its name, the town stays are searched in and its region (state), the nearest airport with scheduled flights (IATA), whether it is a snow place
(winter car options, lift tickets), the resorts that sell lift tickets and ski school direct, and whether Klook has it (D-221). The table is small and hand-checked:
common US family destinations. A place that is not in it still gets every lane: stays, cars and things to do search by its name, and the flight lane asks for the
airport (`iata`). Resort addresses answered 200 (or a bot wall at vail.com) on 2026-11-06; deeper pages are not linked because they move every season.
"""

import re
from dataclasses import dataclass

_IATA = re.compile(r"[A-Z]{3}")
MAX_NAME = 60


@dataclass(frozen=True)
class Place:
    name: str             # what the lanes call it: "Lake Tahoe"
    city: str             # where stays and cars are searched: "South Lake Tahoe"
    region: str = ""      # the state or country: "California"
    iata: str = ""        # the nearest airport with scheduled flights, "" when we do not know it
    snow: bool = False    # a ski place: an SUV with snow chains and a ski rack in winter, and the resorts' own lift tickets
    resorts: tuple = ()   # ((resort, its own site), ...): "Buy direct", no commission
    klook: bool = False   # Klook sells stays and things to do here (D-221); elsewhere Klook is skipped
    focus: str = ""       # "disney": things to do go to Klook's Disneyland Resort page
    known: bool = False   # from the table (False: built from what the person typed)
    states: tuple = ()    # other states a typed suffix may name for this place ("Lake Tahoe, NV")

    @property
    def town(self) -> str:
        """"South Lake Tahoe, California": the stay search's words."""
        return f"{self.city}, {self.region}" if self.region else self.city

    @property
    def slug(self) -> str:
        """Letters and digits only, for a SubID and a click log: "laketahoe"."""
        return re.sub(r"[^a-z0-9]", "", self.name.lower())[:20] or "place"


TAHOE_RESORTS = (("Heavenly", "https://www.skiheavenly.com/"), ("Northstar", "https://www.northstarcalifornia.com/"), ("Kirkwood", "https://www.kirkwood.com/"),
                 ("Palisades Tahoe", "https://www.palisadestahoe.com/"), ("Sierra-at-Tahoe", "https://sierraattahoe.com/"))

# (aliases, Place). The first alias is the name lanes use. Airports: the nearest one with year-round scheduled flights.
_TABLE = (
    (("lake tahoe", "tahoe", "south lake tahoe", "stateline"), Place("Lake Tahoe", "South Lake Tahoe", "California", "RNO", True, TAHOE_RESORTS, states=("Nevada",))),
    (("tahoe city", "truckee", "olympic valley", "north lake tahoe", "kings beach"), Place("Tahoe City", "Tahoe City", "California", "RNO", True, TAHOE_RESORTS, states=("Nevada",))),
    (("mammoth lakes", "mammoth"), Place("Mammoth Lakes", "Mammoth Lakes", "California", "RNO", True, (("Mammoth Mountain", "https://www.mammothmountain.com/"),))),
    (("big bear lake", "big bear"), Place("Big Bear Lake", "Big Bear Lake", "California", "ONT", True, (("Big Bear Mountain Resort", "https://www.bigbearmountainresort.com/"),))),
    (("park city",), Place("Park City", "Park City", "Utah", "SLC", True, (("Park City Mountain", "https://www.parkcitymountain.com/"), ("Deer Valley", "https://www.deervalley.com/")))),
    (("salt lake city", "snowbird", "alta"), Place("Salt Lake City", "Salt Lake City", "Utah", "SLC", True, (("Snowbird", "https://www.snowbird.com/"),))),
    (("vail", "beaver creek"), Place("Vail", "Vail", "Colorado", "EGE", True, (("Vail", "https://www.vail.com/"), ("Beaver Creek", "https://www.beavercreek.com/")))),
    (("breckenridge", "keystone"), Place("Breckenridge", "Breckenridge", "Colorado", "DEN", True, (("Breckenridge", "https://www.breckenridge.com/"),))),
    (("aspen", "snowmass"), Place("Aspen", "Aspen", "Colorado", "ASE", True, (("Aspen Snowmass", "https://www.aspensnowmass.com/"),))),
    (("steamboat springs", "steamboat"), Place("Steamboat Springs", "Steamboat Springs", "Colorado", "HDN", True, (("Steamboat", "https://www.steamboat.com/"),))),
    (("telluride",), Place("Telluride", "Telluride", "Colorado", "MTJ", True, (("Telluride", "https://www.telluride.com/"),))),
    (("jackson hole", "jackson", "teton village"), Place("Jackson Hole", "Jackson", "Wyoming", "JAC", True, (("Jackson Hole Mountain Resort", "https://www.jacksonhole.com/"),))),
    (("sun valley", "ketchum"), Place("Sun Valley", "Sun Valley", "Idaho", "SUN", True, (("Sun Valley", "https://www.sunvalley.com/"),))),
    (("disneyland", "disneyland resort", "disney land", "anaheim", "disney california adventure"), Place("Disneyland", "Anaheim", "California", "SNA", klook=True, focus="disney")),
    (("los angeles", "la", "hollywood", "santa monica"), Place("Los Angeles", "Los Angeles", "California", "LAX", klook=True)),
    (("san diego",), Place("San Diego", "San Diego", "California", "SAN", klook=True)),
    (("san francisco", "sf"), Place("San Francisco", "San Francisco", "California", "SFO", klook=True)),
    (("yosemite", "yosemite national park"), Place("Yosemite", "Yosemite National Park", "California", "FAT")),
    (("palm springs",), Place("Palm Springs", "Palm Springs", "California", "PSP")),
    (("santa barbara",), Place("Santa Barbara", "Santa Barbara", "California", "SBA")),
    (("napa", "napa valley", "sonoma"), Place("Napa", "Napa", "California", "SFO")),
    (("monterey", "carmel", "carmel-by-the-sea"), Place("Monterey", "Monterey", "California", "MRY")),
    (("las vegas", "vegas"), Place("Las Vegas", "Las Vegas", "Nevada", "LAS", klook=True)),
    (("zion", "zion national park", "springdale"), Place("Zion National Park", "Springdale", "Utah", "LAS")),
    (("grand canyon", "grand canyon national park"), Place("Grand Canyon", "Grand Canyon Village", "Arizona", "FLG")),
    (("sedona",), Place("Sedona", "Sedona", "Arizona", "PHX")),
    (("phoenix", "scottsdale"), Place("Phoenix", "Phoenix", "Arizona", "PHX")),
    (("seattle",), Place("Seattle", "Seattle", "Washington", "SEA", klook=True)),
    (("portland",), Place("Portland", "Portland", "Oregon", "PDX")),
    (("denver",), Place("Denver", "Denver", "Colorado", "DEN")),
    (("yellowstone", "yellowstone national park"), Place("Yellowstone", "West Yellowstone", "Montana", "BZN")),
    (("chicago",), Place("Chicago", "Chicago", "Illinois", "ORD", klook=True)),
    (("austin",), Place("Austin", "Austin", "Texas", "AUS")),
    (("nashville",), Place("Nashville", "Nashville", "Tennessee", "BNA")),
    (("new orleans",), Place("New Orleans", "New Orleans", "Louisiana", "MSY")),
    (("new york", "new york city", "nyc", "manhattan"), Place("New York", "New York", "New York", "JFK", klook=True)),
    (("boston",), Place("Boston", "Boston", "Massachusetts", "BOS", klook=True)),
    (("washington dc", "washington, dc", "washington d.c.", "dc"), Place("Washington, DC", "Washington", "District of Columbia", "DCA", klook=True)),
    (("orlando", "walt disney world", "disney world"), Place("Orlando", "Orlando", "Florida", "MCO", klook=True)),
    (("miami", "miami beach"), Place("Miami", "Miami", "Florida", "MIA", klook=True)),
    (("honolulu", "oahu", "waikiki"), Place("Honolulu", "Honolulu", "Hawaii", "HNL", klook=True)),
    (("maui", "lahaina", "kaanapali", "wailea"), Place("Maui", "Kahului", "Hawaii", "OGG", klook=True)),
    (("kauai", "poipu", "princeville"), Place("Kauai", "Lihue", "Hawaii", "LIH")),
    (("big island", "kona", "kailua-kona"), Place("Big Island", "Kailua-Kona", "Hawaii", "KOA")),
    (("anchorage",), Place("Anchorage", "Anchorage", "Alaska", "ANC")),
)
_ALIASES = {alias: place for aliases, place in _TABLE for alias in aliases}


def clean_iata(text) -> str:
    code = (text or "").strip().upper()
    return code if _IATA.fullmatch(code) else ""


def _key(text) -> str:
    return " ".join(str(text or "").lower().replace("–", "-").split())


STATES = {"al": "Alabama", "ak": "Alaska", "az": "Arizona", "ar": "Arkansas", "ca": "California", "co": "Colorado", "ct": "Connecticut", "de": "Delaware", "dc": "District of Columbia",
          "fl": "Florida", "ga": "Georgia", "hi": "Hawaii", "id": "Idaho", "il": "Illinois", "in": "Indiana", "ia": "Iowa", "ks": "Kansas", "ky": "Kentucky", "la": "Louisiana",
          "me": "Maine", "md": "Maryland", "ma": "Massachusetts", "mi": "Michigan", "mn": "Minnesota", "ms": "Mississippi", "mo": "Missouri", "mt": "Montana", "ne": "Nebraska",
          "nv": "Nevada", "nh": "New Hampshire", "nj": "New Jersey", "nm": "New Mexico", "ny": "New York", "nc": "North Carolina", "nd": "North Dakota", "oh": "Ohio",
          "ok": "Oklahoma", "or": "Oregon", "pa": "Pennsylvania", "ri": "Rhode Island", "sc": "South Carolina", "sd": "South Dakota", "tn": "Tennessee", "tx": "Texas",
          "ut": "Utah", "vt": "Vermont", "va": "Virginia", "wa": "Washington", "wv": "West Virginia", "wi": "Wisconsin", "wy": "Wyoming"}
_STATE_NAMES = {v.lower(): v for v in STATES.values()} | {"calif": "California"}
_COUNTRY = {"usa", "us", "u s a", "united states", "united states of america"}


def _state(suffix):
    """The state a typed suffix names ("CA", "Calif.", "Nevada"), "" for the country alone, None for anything else."""
    word = " ".join(suffix.replace(".", " ").split())
    if word in _COUNTRY:
        return ""
    return STATES.get(word) or _STATE_NAMES.get(word)


def _known(text):
    """The table's place for what was typed, or None. A state typed after a comma must be the place's own (F-198 review: "Portland, ME" is not Portland, Oregon, and
    "Jackson, NH" is not Jackson Hole); then the text is the person's own place."""
    key = _key(text)
    if key in _ALIASES:
        return _ALIASES[key]
    head, _, suffix = key.rpartition(",")
    place = _ALIASES.get(head.strip()) if head else None
    if place is None:
        return None
    state = _state(suffix.strip())
    if state is None:
        return None
    return place if state == "" or state in (place.region, *place.states) else None


def resolve(text, iata="") -> Place | None:
    """The Place for what a person typed, or None when they typed nothing. A known place keeps its table entry (its airport unless `iata` is given); any other text
    is its own place: the part before the first comma is the town, the rest the region, and the airport is `iata` or unknown."""
    name = " ".join("".join(c for c in str(text or "") if c.isprintable()).split())[:MAX_NAME].strip(" ,")
    if not name:
        return None
    code = clean_iata(iata)
    place = _known(name)
    if place:
        return Place(**{**place.__dict__, "known": True, **({"iata": code} if code else {})})
    city, _, region = (p.strip() for p in name.partition(","))
    return Place(name, city or name, region, code)
