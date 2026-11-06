"""The partner seam (autopilot M2): GitAway is a control plane. It sends a family to a partner who keeps the booking, the refund and the liability.

Two Travelpayouts partners and a deep link: flights -> Aviasales (a search link carrying `marker=<marker>.<subid>`, plus a redundant `&sub_id=<subid>` for the autopilot contract), stays, cars and things to do -> Klook
(a Klook page turned into a tracked link by the partner-links API at /go time, D-70), rides -> Uber (a deep link). Each knows where it sends a
traveler (`target_url`) and what it pays (`estimate_cents`). The network is touched in one place, `travelpayouts.klook_link`, at click time with
a short timeout and a fallback; no test reaches it.
"""

from dataclasses import dataclass
from urllib.parse import quote, urlencode

from gitaway import catalog


@dataclass(frozen=True)
class Partner:
    key: str            # in URLs: /sandbox/<key>/...
    name: str           # what the traveler reads: "Book on <name>"
    lanes: tuple        # flight | stay | car | todo | ride: the lanes it sells
    rate_bps: int = 0   # estimated commission as basis points of the price (110 = 1.1%)

    def estimate_cents(self, price_cents: int) -> int:
        """What this partner would pay GitAway for a booking of `price_cents` (an estimate; the real figure comes from the statistics API)."""
        return price_cents * self.rate_bps // 10_000

    def target_url(self, offer, trip) -> str:
        """The partner's own page for this offer: where the traveler lands after the tracked link."""
        return TARGETS[offer.kind](offer, trip)


def _aviasales(o, trip):
    """Aviasales' search for this trip. With the reader's home airport: its short link `<from><DDMM><to><DDMM><adults><children><infants>` (trailing zeros left off; probed
    in a browser 2026-11-06: "...2003" + "22" is 4 passengers, "201" is 3). Without one, its home page with the rest of the search filled in, and Aviasales asks where from
    (it guesses from where the reader is; the marker and the passengers stay on the link). Never a guessed origin of ours (F-195)."""
    adults, children, infants = trip.passengers
    if trip.home:
        kids = f"{children}{infants}" if infants else str(children) if children else ""
        return f"https://www.aviasales.com/search/{trip.home}{trip.depart:%d%m}{o.airport}{trip.return_:%d%m}{adults}{kids}"
    query = {"destination_iata": o.airport, "depart_date": trip.depart.isoformat(), "return_date": trip.return_.isoformat(), "adults": adults,
             **({"children": children} if children else {}), **({"infants": infants} if infants else {})}
    return "https://www.aviasales.com/?" + urlencode(query)


def _klook_search(query: str) -> str:
    return f"https://www.klook.com/en-US/search/result/?query={quote(query)}"


# Klook's own page for Disneyland Resort in Anaheim, with its park tickets (found on Klook's pages through search 2026-11-06; Klook answers 403 to this machine, so not opened: D-145).
KLOOK_DISNEYLAND = "https://www.klook.com/en-US/destination/p50042790-disneyland-resort/"


def _klook_stay(o, trip):
    return _klook_search(trip.stay_area + " hotels")


def _klook_todo(o, trip):
    """Tickets and things to do on Klook: Disneyland Resort tickets for a Disneyland trip, else the place's attractions."""
    return KLOOK_DISNEYLAND if trip.focus == "disney" else _klook_search(trip.destination_name + " attractions")


def _klook_car(o, trip):
    return f"https://www.klook.com/en-US/search/result/?query={quote(trip.destination_name + ' car rental')}"


def uber_deep_link(pickup: str, dropoff: str) -> str:
    """Uber's universal deep link (the ride lane): opens the Uber app, or m.uber.com, with the pickup and dropoff filled in. No account, no key."""
    start = f"pickup[formatted_address]={quote(pickup)}" if pickup else "pickup=my_location"
    return f"https://m.uber.com/ul/?action=setPickup&{start}&dropoff[formatted_address]={quote(dropoff)}"


def _uber(o, trip):
    return uber_deep_link("", trip.destination_name)


TARGETS = {"flight": _aviasales, "stay": _klook_stay, "car": _klook_car, "todo": _klook_todo, "ride": _uber}

# Rates are estimates (D-71): Aviasales ~1.1% of the fare, Klook 5% (Travelpayouts' Klook page: 5%, 2% on "special activities"), rides nothing.
PARTNERS = (
    Partner("aviasales", "Aviasales", ("flight",), rate_bps=110),
    Partner("klook", "Klook", ("stay", "car", "todo"), rate_bps=500),
    Partner("uber", "Uber", ("ride",)),
)
_BY_KEY = {p.key: p for p in PARTNERS}
_BY_LANE = {lane: p for p in PARTNERS for lane in p.lanes}


def for_lane(lane: str) -> Partner:
    """The partner of a lane ("flight", "stay", "car" or "ride"). Raises KeyError."""
    return _BY_LANE[lane]


def get(key: str) -> Partner | None:
    return _BY_KEY.get(key)


def for_offer(offer) -> Partner:
    """The partner an offer of the catalog is booked on."""
    return for_lane(offer.kind)


def available() -> bool:
    """Is there anywhere to send a traveler? The sandbox on a local copy (showcase), or a real Travelpayouts marker. In production without a marker, no "Book on" links."""
    from gitaway import showcase
    from gitaway.partners import travelpayouts
    return showcase.on() or bool(travelpayouts.marker())
