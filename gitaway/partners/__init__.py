"""The partner seam (autopilot M2): GitAway is a control plane. It sends a family to a partner who keeps the booking, the refund and the liability.

One `Partner` per lane: flights -> Aviasales, stays -> Hotellook (both through Travelpayouts), cars -> DiscoverCars (Travelpayouts), rides ->
Uber (a deep link). Each knows where it sends a traveler (`target_url`) and what it pays (`estimate_cents`). Everything is synthetic and
deterministic today, shaped like the real APIs (gitaway.partners.travelpayouts, .statistics); the real clients are stubs that wake up only
when their keys exist (TRAVELPAYOUTS_TOKEN + TRAVELPAYOUTS_MARKER, later LITEAPI_KEY for hotel prices and DUFFEL_TOKEN for cars) and no
test or code path calls a network.
"""

from dataclasses import dataclass
from urllib.parse import quote

from gitaway import catalog


@dataclass(frozen=True)
class Partner:
    key: str            # in URLs: /sandbox/<key>/...
    name: str           # what the traveler reads: "Book on <name>"
    lane: str           # flight | stay | car | ride
    program_id: int     # Travelpayouts `p` and `campaign_id` of the program (placeholders until the account connects them)
    rate_bps: int = 0   # estimated commission as basis points of the price (110 = 1.1%) ...
    flat_cents: int = 0  # ... or a flat amount per booking

    def estimate_cents(self, price_cents: int) -> int:
        """What this partner would pay GitAway for a booking of `price_cents` (an estimate; the real figure comes from the statistics API)."""
        return self.flat_cents or price_cents * self.rate_bps // 10_000

    def target_url(self, offer, trip) -> str:
        """The partner's own search page for this offer: where the traveler lands after the tracked link."""
        return TARGETS[self.lane](offer, trip)


def _aviasales(o, trip):
    return f"https://www.aviasales.com/search/{trip.origin}{trip.depart:%d%m}{o.airport}{trip.return_:%d%m}{trip.travelers}"


def _hotellook(o, trip):
    return (f"https://search.hotellook.com/hotels?destination={quote(trip.destination_name)}&checkIn={trip.depart.isoformat()}"
            f"&checkOut={trip.return_.isoformat()}&adults={trip.adults}&children={len(trip.kid_ages)}")


def _discovercars(o, trip):
    return (f"https://www.discovercars.com/search?location={quote(trip.destination_name)}&pickup={trip.depart.isoformat()}"
            f"&dropoff={trip.return_.isoformat()}")


def uber_deep_link(pickup: str, dropoff: str) -> str:
    """Uber's universal deep link (the ride lane): opens the Uber app, or m.uber.com, with the pickup and dropoff filled in. No account, no key."""
    start = f"pickup[formatted_address]={quote(pickup)}" if pickup else "pickup=my_location"
    return f"https://m.uber.com/ul/?action=setPickup&{start}&dropoff[formatted_address]={quote(dropoff)}"


def _uber(o, trip):
    return uber_deep_link("", trip.destination_name)


TARGETS = {"flight": _aviasales, "stay": _hotellook, "car": _discovercars, "ride": _uber}

# Rates are estimates (D-20): flights ~1.1% of the fare, hotels ~5% (4 to 6%), cars about $18 a booking, rides nothing (no affiliate programme).
PARTNERS = (
    Partner("aviasales", "Aviasales", "flight", 4114, rate_bps=110),
    Partner("hotellook", "Hotellook", "stay", 4115, rate_bps=500),
    Partner("discovercars", "DiscoverCars", "car", 4116, flat_cents=1_800),
    Partner("uber", "Uber", "ride", 0),
)
_BY_KEY = {p.key: p for p in PARTNERS}
_BY_LANE = {p.lane: p for p in PARTNERS}


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
