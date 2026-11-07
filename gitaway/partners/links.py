"""The deep links of the booking lanes (F-198): a search at a site, filled in from the trip, with no affiliate parameter of any kind. Pure functions; no network.

Each builder takes a Search (a Place, dates, adults, kids' ages, the home airport) and returns the https URL, or None when the site cannot be searched for it
(no airport for a flight, a place Klook does not have). What each site's URL takes, and where it was checked, is D-220:

    aviasales      /search/<FROM><DDMM><TO><DDMM><adults><children><infants>, or the home page with the search filled in when the home airport is not known (F-195)
    expedia_stay   Expedia's documented lodging deeplink: dates, one room, adults, each child's age
    airbnb_stay    /s/<Town--Region>/homes with checkin, checkout, adults, children (2 to 12), infants (under 2); Airbnb takes no ages
    vrbo_stay      /search with destination, startDate, endDate, adults, children as 1_<age>,...
    booking_stay   searchresults.html with ss, dates, group_adults, group_children, one age= per child (for when the Booking.com program is approved, D-222)
    expedia_car    Expedia's documented car deeplink: at the airport (else near the town), an SUV with snow chains and a ski rack (Equipment=W,S) on a winter trip to a snow place,
                   a minivan for six or more
    getyourguide   /s/?q=<place>&date_from&date_to over the trip's full days
    klook_stay, klook_todo   Klook's search (or its Disneyland Resort page), only where Klook has the place
"""

from dataclasses import dataclass
from datetime import date, timedelta
from urllib.parse import quote, urlencode

from gitaway import catalog
from gitaway.partners.places import Place

WINTER = (11, 12, 1, 2, 3, 4)       # months a snow place needs chains and a ski rack
MINIVAN_FROM = 6                    # travelers who need a minivan (a standard SUV seats five)
KLOOK_DISNEYLAND = "https://www.klook.com/en-US/destination/p50042790-disneyland-resort/"     # D-160


@dataclass(frozen=True)
class Search:
    place: Place
    depart: date
    return_: date
    adults: int
    kid_ages: tuple = ()
    home: str = ""      # the traveler's own airport, "" when they have not said

    @property
    def travelers(self) -> int:
        return self.adults + len(self.kid_ages)

    @property
    def nights(self) -> int:
        return (self.return_ - self.depart).days

    @property
    def winter_snow(self) -> bool:
        return self.place.snow and self.depart.month in WINTER


def _q(value) -> str:
    return quote(str(value), safe="")


def aviasales(s: Search) -> str | None:
    if not s.place.iata:
        return None
    adults, children, infants = catalog.passengers(s.adults, s.kid_ages)
    if s.home:
        kids = f"{children}{infants}" if infants else str(children) if children else ""
        return f"https://www.aviasales.com/search/{s.home}{s.depart:%d%m}{s.place.iata}{s.return_:%d%m}{adults}{kids}"
    query = {"destination_iata": s.place.iata, "depart_date": s.depart.isoformat(), "return_date": s.return_.isoformat(), "adults": adults,
             **({"children": children} if children else {}), **({"infants": infants} if infants else {})}
    return "https://www.aviasales.com/?" + urlencode(query)


def expedia_stay(s: Search) -> str:
    kids = "".join(f"&Room1-Child{i}Age={age}" for i, age in enumerate(s.kid_ages, 1))
    return (f"https://www.expedia.com/go/hotel/search/Destination/{s.depart.isoformat()}/{s.return_.isoformat()}?CityName={_q(s.place.city)}"
            f"&NumRoom=1&NumAdult-Room1={s.adults}" + (f"&NumChild-Room1={len(s.kid_ages)}{kids}" if s.kid_ages else ""))


def airbnb_stay(s: Search) -> str:
    slug = "--".join(_q(part.replace(" ", "-")) for part in (s.place.city, s.place.region) if part)
    adults = s.adults + sum(a > 12 for a in s.kid_ages)
    children, infants = sum(2 <= a <= 12 for a in s.kid_ages), sum(a < 2 for a in s.kid_ages)
    return (f"https://www.airbnb.com/s/{slug}/homes?checkin={s.depart.isoformat()}&checkout={s.return_.isoformat()}&adults={adults}"
            + (f"&children={children}" if children else "") + (f"&infants={infants}" if infants else ""))


def vrbo_stay(s: Search) -> str:
    kids = _q(",".join(f"1_{a}" for a in s.kid_ages))
    return (f"https://www.vrbo.com/search?destination={_q(s.place.town)}&startDate={s.depart.isoformat()}&endDate={s.return_.isoformat()}&adults={s.adults}"
            + (f"&children={kids}" if s.kid_ages else ""))


def booking_stay(s: Search) -> str:
    query = [("ss", s.place.town), ("checkin", s.depart.isoformat()), ("checkout", s.return_.isoformat()), ("group_adults", s.adults), ("group_children", len(s.kid_ages)),
             *[("age", a) for a in s.kid_ages], ("no_rooms", 1), ("lang", "en-us"), ("selected_currency", "USD")]
    return "https://www.booking.com/searchresults.html?" + urlencode(query)


def expedia_car(s: Search) -> str:
    kind, where = ("Airport", f"PickUpLoc={s.place.iata}&DiffDropLoc=0") if s.place.iata else ("Place", f"PickUpLoc={_q(s.place.town)}&Distance=10")
    car = "MiniVan" if s.travelers >= MINIVAN_FROM else "SUV" if s.winter_snow else "NoPreference"
    return (f"https://www.expedia.com/go/car/search/{kind}/{s.depart.isoformat()}/{s.return_.isoformat()}?{where}&PickUpTime=11AM&DropTime=11AM&Class={car}"
            + ("&Equipment=W,S" if s.winter_snow else ""))


def getyourguide(s: Search) -> str:
    start, end = (s.depart + timedelta(days=1), s.return_ - timedelta(days=1)) if s.nights >= 2 else (s.depart, s.return_)
    return f"https://www.getyourguide.com/s/?q={_q(s.place.name)}&date_from={start.isoformat()}&date_to={end.isoformat()}"


def _klook_search(words) -> str:
    return f"https://www.klook.com/en-US/search/result/?query={_q(words)}"


def klook_stay(s: Search) -> str | None:
    return _klook_search(f"{s.place.city} hotels") if s.place.klook else None


def klook_todo(s: Search) -> str | None:
    if not s.place.klook:
        return None
    return KLOOK_DISNEYLAND if s.place.focus == "disney" else _klook_search(f"{s.place.city} attractions")
