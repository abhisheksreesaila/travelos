"""Where the trip grid's flights and stays come from (F-217): one seam, so a real source drops in without touching the page.

    offers(trip, family)   a Found (flights, stays, the drive between them, where each is booked, whether it is sample data, what went wrong), or None when there is nothing to show

On the showcase the source is its invented catalog (gitaway/catalog.py), so `sample` is True and the page says so. Off it the source is LiteAPI (F-220, D-424:
gitaway/liteapi.py) once LITEAPI_KEY is set and the trip says where the family flies from: every price in a square is LiteAPI's, a stay's with the fees paid at the
hotel added (D-425). No key, or no home airport, answers None; a spent budget or a search that failed answers a Found with no offers and `problem` said in words,
never an empty grid. The drive is not known yet (None) and nothing is booked yet (F-222). `SOURCE` is what tests replace.
"""

import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from gitaway import catalog, liteapi, partners, showcase
from gitaway.tripgrid import Flight, Stay

MAX_FLIGHTS = MAX_STAYS = 12     # the page draws up to 12 columns
COUNTRY = "US"                   # every place the grid knows (catalog.DESTINATIONS) is in the United States
SPENT = "Today’s price searches are used up. Try again tomorrow."
FAILED = "The prices did not come back just now. Try again in a few minutes."
NONE = "No flights or no stays came back for these dates. Try other dates."


@dataclass(frozen=True)
class Found:
    flights: tuple
    stays: tuple
    drive_min: Callable      # (flight, stay) -> minutes from its airport to the stay, or None when not known
    book: Callable           # (flight or stay) -> ((label, href), ...): where it is booked, never on GitAway
    sample: bool             # invented data: the page says so
    problem: str = ""        # why there are no offers (a spent budget, a failed search), said in words
    checked: datetime | None = None     # when the older of the answers was fetched


def _stops(text) -> int:
    m = re.match(r"(\d+) stop", text or "")
    return int(m.group(1)) if m else 0


def _catalog(trip):
    flights = tuple(Flight(o.id, o.name, o.airport, o.depart_min, o.arrive_min, _stops(o.stops), o.price_cents, o.stops or "Nonstop",
                           overnight=o.arrive_min < o.depart_min) for o in catalog.offers("flight", trip))
    offers = {o.id: o for o in catalog.offers("stay", trip)}
    stays = tuple(Stay(o.id, o.name, o.headline, o.detail, o.price_cents, o.tags, o.rating) for o in offers.values())

    def drive_min(flight, stay):
        return catalog.ride_base(flight.airport, catalog.ride_area(flight.airport, offers[stay.id]), "arrive")[1]

    def book(item):
        offer = catalog.offer(item.id, trip)
        return ((f"Book on {partners.for_offer(offer).name}", partners.go_href(offer, trip)),)

    return Found(flights, stays, drive_min, book, True) if flights and stays else None


def _stops_text(n: int) -> str:
    return "Nonstop" if n == 0 else f"{n} stop{'s' if n > 1 else ''}"


def _flight(f: liteapi.Flight) -> Flight:
    out = f.legs[0]
    number = out.flights[0].split(" ", 1)[-1] if out.flights else ""
    return Flight(f.id, f"{f.airline} {number}".strip(), out.destination, out.depart.hour * 60 + out.depart.minute, out.arrive.hour * 60 + out.arrive.minute, out.stops, f.cents,
                  _stops_text(out.stops), overnight=out.arrive.date() > out.depart.date())


def _stay(s: liteapi.Stay) -> Stay:
    room = (s.room, "Breakfast" if s.board == "breakfast" else s.board.capitalize(), "Refundable" if s.refundable else "Non-refundable",
            f"{catalog.money(s.due_at_stay_cents)} of it paid at the hotel" if s.due_at_stay_cents else "")
    rating = " · ".join(x for x in (f"{s.rating:g} of 10" if s.rating else "", f"{s.reviews:,} reviews" if s.reviews else "") if x)
    return Stay(s.id, s.name, s.address, " · ".join(x for x in room if x), s.cents + s.due_at_stay_cents, rating=rating)


def _liteapi(trip, family=""):
    home, there = trip.home, trip.airports[0] if trip.airports else ""
    if not liteapi.key() or not home or not there:
        return None
    party = {"adults": trip.adults, "kid_ages": trip.kid_ages, "family": family}
    with ThreadPoolExecutor(2) as pool:      # side by side: flights take up to 16 s, stays 2
        fl = pool.submit(liteapi.flights, legs=((home, there, trip.depart), (there, home, trip.return_)), **party)
        st = pool.submit(liteapi.stays, city=trip.stay_area, country=COUNTRY, checkin=trip.depart, checkout=trip.return_, **party)
        fl, st = fl.result(), st.result()
    answers = (fl, st)
    if any(a.status == liteapi.OFF for a in answers):
        return None
    problem = SPENT if any(a.status == liteapi.OVER for a in answers) else (FAILED if not all(a.ok for a in answers) else "")
    seen, flights = set(), []
    for f in fl.items if not problem else ():
        if f.legs[0].flights not in seen and len(flights) < MAX_FLIGHTS:      # each outbound flight once, at its cheapest way home
            seen.add(f.legs[0].flights)
            flights.append(_flight(f))
    stays = tuple(_stay(s) for s in st.items[:MAX_STAYS]) if not problem else ()
    if not problem and not (flights and stays):
        problem, flights, stays = NONE, [], ()
    return Found(tuple(flights), stays, lambda flight, stay: None, lambda item: (), False, problem, min((a.fetched for a in answers if a.fetched), default=None))


def _source(trip, family=""):
    return _catalog(trip) if showcase.on() else _liteapi(trip, family)


SOURCE = _source


def offers(trip, family=""):
    return SOURCE(trip, family)
