"""The partner registry (F-198): which site each booking lane sends a family to, and whether GitAway earns from it. Booking is links only (the brief's model).

    LANES                  flight, stay, car, todo, direct (lift tickets and ski school, bought at the resort)
    lane(lane, search)     [LaneLink, ...] for one lane: the first is the lane's button, the rest are "also on" links; [] when the lane has nothing for this trip
    lanes(search)          {lane: [LaneLink, ...]} for every lane
    find(lane, site, s)    the one LaneLink a click names, rebuilt from the trip on the server (a click never carries a URL)
    go_url(link, sub_id)   where that click goes: Aviasales with our marker, a tracked link from the partner-links API, or the plain search itself

A site PAYS when its program is connected here: Aviasales with TRAVELPAYOUTS_MARKER; Klook, and any site named in PARTNER_TRACKED (comma separated, e.g. "booking,expedia" once
those programs approve the project), through the partner-links API (TRAVELPAYOUTS_TOKEN, marker and TRAVELPAYOUTS_TRS). Every other site is a plain link: the search filled in,
no affiliate parameter, and the words "No commission" (D-219). Klook is only offered while it pays and only where it has the place (D-221); Booking.com only once it is chosen.
PARTNER_FLIGHT, PARTNER_STAY, PARTNER_CAR, PARTNER_TODO name the site a lane leads with (e.g. PARTNER_STAY=booking). Nothing here touches the network; `go_url` may (the
partner-links API, at click time only).
"""

import os
from dataclasses import dataclass

from gitaway.partners import links, travelpayouts

LANES = ("flight", "stay", "car", "todo", "direct")
NAMES = {"aviasales": "Aviasales", "expedia": "Expedia", "airbnb": "Airbnb", "vrbo": "Vrbo", "booking": "Booking.com", "klook": "Klook", "getyourguide": "GetYourGuide"}
PAID_NOTE, PLAIN_NOTE, DIRECT_NOTE = "We may earn a commission", "No commission", "Buy direct · No commission"


@dataclass(frozen=True)
class Choice:
    site: str
    build: object             # links.<builder>(search) -> url | None
    program: str = ""         # "marker" (Aviasales), "tracked" (always the partner-links API: Klook), "" (a plain link unless PARTNER_TRACKED names it)
    listed: bool = True       # False: offered only when PARTNER_<LANE> chooses it (Booking.com, until its program approves us)


# A lane's sites in the order they are offered, before PARTNER_<LANE> moves one to the front.
CHOICES = {
    "flight": (Choice("aviasales", links.aviasales, "marker"),),
    "stay": (Choice("klook", links.klook_stay, "tracked"), Choice("expedia", links.expedia_stay), Choice("airbnb", links.airbnb_stay), Choice("vrbo", links.vrbo_stay),
             Choice("booking", links.booking_stay, listed=False)),
    "car": (Choice("expedia", links.expedia_car),),
    "todo": (Choice("klook", links.klook_todo, "tracked"), Choice("getyourguide", links.getyourguide)),
}


@dataclass(frozen=True)
class LaneLink:
    lane: str
    site: str
    name: str
    url: str
    paid: bool
    tracked: bool = False     # the click goes through the partner-links API

    @property
    def note(self) -> str:
        return DIRECT_NOTE if self.lane == "direct" else PAID_NOTE if self.paid else PLAIN_NOTE


def _setting(name) -> str:
    return os.getenv(name, "").strip().lower()


def tracked_sites() -> set:
    return {s.strip() for s in _setting("PARTNER_TRACKED").split(",") if s.strip()}


def _pays(choice) -> tuple:
    """(pays, tracked) for a site here and now."""
    if choice.program == "marker":
        return bool(travelpayouts.marker()), False
    tracked = choice.program == "tracked" or choice.site in tracked_sites()
    return (tracked and travelpayouts.connected()), tracked


def lane(lane_key, search) -> list:
    if lane_key == "direct":
        return [LaneLink("direct", f"resort-{i}", name, url, False) for i, (name, url) in enumerate(search.place.resorts)] if search.place.snow else []
    lead = _setting(f"PARTNER_{lane_key.upper()}")
    out = []
    for choice in CHOICES.get(lane_key, ()):
        if not choice.listed and choice.site != lead:
            continue
        pays, tracked = _pays(choice)
        if choice.program == "tracked" and not pays:      # Klook only while its links are tracked: an untracked Klook search earns nothing and is no better than the plain sites
            continue
        url = choice.build(search)
        if url:
            out.append(LaneLink(lane_key, choice.site, NAMES[choice.site], url, pays, tracked and pays))
    out.sort(key=lambda x: x.site != lead)      # stable: the chosen site first, the rest in their order
    return out


def lanes(search) -> dict:
    return {k: lane(k, search) for k in LANES}


def find(lane_key, site, search):
    return next((x for x in lane(lane_key, search) if x.site == site), None) if lane_key in LANES else None


def go_url(link: LaneLink, sub_id: str, own: str = "") -> str:
    """Where a click on `link` goes. `own` is a creator's own Aviasales marker (F-184). Never raises; a tracked link that cannot be made falls back to the plain search
    (Klook's to our plain Klook partner link)."""
    if not link.paid:
        return link.url
    if link.site == "aviasales":
        return travelpayouts.aviasales_link(link.url, sub_id, own)
    if link.site == "klook":
        return travelpayouts.klook_link(link.url, sub_id)
    return travelpayouts.tracked_link(link.url, sub_id)
