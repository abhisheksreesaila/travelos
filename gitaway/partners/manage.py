"""Where a booking lives (F-198): the partner's own page to change or cancel it. GitAway never handles a change, a cancellation or a refund (the brief's model).

    find(name)                          the Manage page for a partner, airline or car company named in free text ("Expedia", "Alaska Airlines", "Enterprise Rent-A-Car"), or None
    for_booking(kind, item, partner)    (partner shown, Manage or None) for one booking: where it was booked, and where it is changed. A flight bought through Aviasales is changed with
                                        the airline (Aviasales sells nothing itself); a car with no partner given is the rental company's own

Every address was opened from this machine on 2026-11-06 (D-228): answered 200, or redirected to the site's own sign-in for that page (Booking.com, Airbnb, Klook), or a bot wall
(429/403/406, marked `walled`) on a page we found on the site's own help or in its developer docs. GetYourGuide, Hertz, Thrifty and Dollar answered only their home page, so the
button opens that and the partner's sign-in takes it from there.
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Manage:
    name: str
    url: str
    walled: bool = False    # the page answered a bot wall to us, so it was not opened (D-228)


SITES = {
    "expedia": Manage("Expedia", "https://www.expedia.com/trips", True),
    "booking": Manage("Booking.com", "https://secure.booking.com/mytrips.html"),
    "airbnb": Manage("Airbnb", "https://www.airbnb.com/trips"),
    "vrbo": Manage("Vrbo", "https://www.vrbo.com/trips", True),
    "klook": Manage("Klook", "https://www.klook.com/bookings/"),
    "getyourguide": Manage("GetYourGuide", "https://www.getyourguide.com/", True),
    "aviasales": Manage("Aviasales", "https://www.aviasales.com/faq/i-want-to-return-or-exchange-my-ticket-how-do-i-do-that"),
    "hertz": Manage("Hertz", "https://www.hertz.com/us/en"),
    "avis": Manage("Avis", "https://www.avis.com/en/reservation/view-modify-cancel"),
    "budget": Manage("Budget", "https://www.budget.com/en/reservation/view-modify-cancel"),
    "enterprise": Manage("Enterprise", "https://www.enterprise.com/en/reserve/view-modify-cancel.html", True),
    "national": Manage("National", "https://www.nationalcar.com/en/reserve/view-modify-cancel.html"),
    "alamo": Manage("Alamo", "https://www.alamo.com/en/reserve/view-modify-cancel.html", True),
    "sixt": Manage("Sixt", "https://www.sixt.com/account/#/manage-booking"),
    "thrifty": Manage("Thrifty", "https://www.thrifty.com/us/en"),
    "dollar": Manage("Dollar", "https://www.dollar.com/us/en"),
    "united": Manage("United", "https://www.united.com/en/us/manageres/mytrips", True),
    "delta": Manage("Delta", "https://www.delta.com/my-trips/search"),
    "american": Manage("American Airlines", "https://www.aa.com/reservation/view/find-your-trip", True),
    "southwest": Manage("Southwest", "https://www.southwest.com/air/manage-reservation/"),
    "jetblue": Manage("JetBlue", "https://www.jetblue.com/manage-trips"),
    "alaska": Manage("Alaska Airlines", "https://www.alaskaair.com/booking/reservation-lookup", True),
    "frontier": Manage("Frontier", "https://www.flyfrontier.com/travel/my-trips/manage-trip/"),
}
# A partner's own name and the ways it is written (F-198 review: only the name itself, never a name that merely contains a partner's word: "American Express Travel", "Budget Travel" and
# "Tahoe Booking Co" get no button). Matched after lower-casing, ".com" and punctuation dropped, and a trailing company word ("rent a car", "airlines", "inc") taken off.
_NAMES = {"expedia": "expedia", "booking": "booking", "airbnb": "airbnb", "vrbo": "vrbo", "homeaway": "vrbo", "klook": "klook", "getyourguide": "getyourguide",
          "get your guide": "getyourguide", "aviasales": "aviasales", "hertz": "hertz", "avis": "avis", "budget": "budget", "enterprise": "enterprise", "national": "national",
          "alamo": "alamo", "sixt": "sixt", "thrifty": "thrifty", "dollar": "dollar", "united": "united", "delta": "delta", "american": "american", "southwest": "southwest",
          "jetblue": "jetblue", "jet blue": "jetblue", "alaska": "alaska", "frontier": "frontier"}
_TAIL = re.compile(r"\s+(?:rent a car|car rental|car rentals|rental cars?|airlines|air lines|airways|air|inc|llc|co)$")


def _name(text) -> str:
    name = " ".join(re.sub(r"[^a-z0-9]+", " ", str(text or "").lower().replace(".com", " ")).split())
    while True:
        cut = _TAIL.sub("", name)
        if cut == name or not cut:
            return name
        name = cut


def find(name) -> Manage | None:
    """The Manage page when `name` is a partner's own name ("Expedia", "expedia.com", "Enterprise Rent-A-Car", "Delta Air Lines"), else None."""
    key = _NAMES.get(_name(name))
    return SITES[key] if key else None


def for_booking(kind, item, partner="") -> tuple:
    """(where it was booked as shown, Manage or None). `partner` is where it was booked ("" when we were not told); `kind` is leg, checkin, checkout, pickup, dropoff or ticket."""
    site = find(partner)
    if kind == "leg" and (site is None or site.name == "Aviasales"):
        return partner, find(getattr(item, "airline", "")) or site
    if kind in ("pickup", "dropoff") and site is None:
        return partner or item.company, find(item.company)
    return partner, site
