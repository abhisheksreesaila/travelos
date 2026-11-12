"""Where the trip grid's flights and stays come from (F-217): one seam, so a real source drops in without touching the page.

    offers(trip)   (flights, stays, drive_min, sample) for a trip, or None when there is nothing real or sample to show

Today the only source is the showcase's invented catalog (gitaway/catalog.py), so `sample` is True and the page says so; off the showcase there is no source and
this answers None (the grid's routes are in showcase.HIDDEN). A real stay source (Stay22's Direct Travel API, docs/briefs/unified-booking.md) needs the founder's
key and one real call before it is written (docs/lessons.md: a parser tested only on made-up data misses the service's shape). `SOURCE` is what tests replace.
"""

import re

from gitaway import catalog, showcase
from gitaway.tripgrid import Flight, Stay


def _stops(text) -> int:
    m = re.match(r"(\d+) stop", text or "")
    return int(m.group(1)) if m else 0


def _catalog(trip):
    flights = tuple(Flight(o.id, o.name, o.airport, o.depart_min, o.arrive_min, _stops(o.stops), o.price_cents, o.price_cents // max(1, trip.travelers), o.stops or "Nonstop",
                           overnight=o.arrive_min < o.depart_min) for o in catalog.offers("flight", trip))
    offers = {o.id: o for o in catalog.offers("stay", trip)}
    stays = tuple(Stay(o.id, o.name, o.headline, o.detail, o.price_cents, o.tags, o.rating) for o in offers.values())

    def drive_min(flight, stay):
        return catalog.ride_base(flight.airport, catalog.ride_area(flight.airport, offers[stay.id]), "arrive")[1]

    return (flights, stays, drive_min, True) if flights and stays else None


def _source(trip):
    return _catalog(trip) if showcase.on() else None


SOURCE = _source


def offers(trip):
    return SOURCE(trip)
