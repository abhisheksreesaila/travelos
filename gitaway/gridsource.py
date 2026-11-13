"""Where the trip grid's flights and stays come from (F-217): one seam, so a real source drops in without touching the page.

    offers(trip, family)   a Found (flights, stays, the drive between them, where each is booked, whether it is sample data, what went wrong), or None when there is nothing to show

On the showcase the source is its invented catalog (gitaway/catalog.py), so `sample` is True and the page says so. Off it the source is LiteAPI (F-220, D-424:
gitaway/liteapi.py) once LITEAPI_KEY is set and the trip says where the family flies from: every price in a square is LiteAPI's, a stay's with the fees paid at the
hotel added (D-425). No key, or no home airport, answers None; a spent budget or a search that failed answers a Found with no offers and `problem` said in words,
never an empty grid. The drive is not known yet (None) and nothing is booked yet (F-222). `SOURCE` is what tests replace.

    square(lane, window, adults=, kid_ages=, home=, family=, peek=False, rank=0)   one square of the trip matrix (F-222): a tripmatrix.Square, the whole trip for
                                                                           one place (or two) and one start day. `peek`: only what is known without a call, else None.
                                                                           `rank`: the square's place in the page's order (F-229), its turn at liteapi's gate.

The matrix's squares come the same two ways: on the showcase the catalog (its places only; another place says it has no sample), its prices moved by the start
day's weekday (SAMPLE_DAY, D-436) so the sample shows a cheapest start; off it LiteAPI: the cheapest flight, and the cheapest stay guests rate RATED or more
(the cheapest of all when none is, D-437). `SQUARE` is what tests replace.
"""

import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from gitaway import airportdrive, catalog, liteapi, partners, showcase, tripgrid, tripmatrix as tm
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


# ---- one square of the trip matrix (F-222) ------------------------------------------------------------------------------

RATED = 8.0                  # out of 10: the stay a square shows is the cheapest guests rate this or more, when there is one
SAMPLE_DAY = (0.98, 0.95, 0.96, 1.0, 1.06, 1.08, 1.03)      # Monday to Sunday: the sample's prices by the start day (showcase only, D-436)


def sample_day(cents: int, day) -> int:
    return int(round(cents * SAMPLE_DAY[day.weekday()] / 100)) * 100


def _day_clock(when) -> str:
    return f"{when:%a}, {when:%b} {when.day} · " if when else ""


def _catalog_square(lane, w, adults, kid_ages, home):
    dests = [next((d for d in catalog.DESTINATIONS if d.name == p.name), None) for p in lane.places]
    if not all(dests):
        return tm.Square(lane.key, w.key, tm.NO_SAMPLE, sample=True)
    split = tm.stays_for(lane, w)
    if split is None:
        return tm.Square(lane.key, w.key, tm.NONE, sample=True)
    kids = ",".join(map(str, kid_ages))
    try:
        trips = [catalog.parse_trip(home or catalog.ORIGIN[0], d.key, a.isoformat(), b.isoformat(), str(adults), kids) for d, (_, a, b) in zip(dests, split)]
        first = catalog.parse_trip(home or catalog.ORIGIN[0], dests[0].key, w.depart.isoformat(), w.return_.isoformat(), str(adults), kids)
    except catalog.TripError:
        return tm.Square(lane.key, w.key, tm.NONE, sample=True)
    f = min(catalog.offers("flight", first), key=lambda o: (o.price_cents, o.id))
    back = lane.places[-1].iata
    flight = tm.FlightPart(f.name, f"{_day_clock(w.depart)}{first.origin} {tripgrid.clock(f.depart_min)} → {f.airport} {tripgrid.clock(f.arrive_min)} · {f.stops or 'Nonstop'}",
                           f"{_day_clock(w.return_)}{back} {tripgrid.clock(f.back_depart_min)} → {first.origin} {tripgrid.clock(f.back_arrive_min)}", _stops(f.stops),
                           sample_day(f.price_cents, w.depart))
    stays = []
    for place, trip, (_, a, b) in zip(lane.places, trips, split):
        st = min(catalog.offers("stay", trip), key=lambda o: (o.price_cents, o.id))
        stays.append(tm.StayPart(place.name, (b - a).days, st.name, st.detail, "room only", True, 0, "", st.rating, sample_day(st.price_cents, a)))
    first_stay = min(catalog.offers("stay", trips[0]), key=lambda o: (o.price_cents, o.id))
    drive = catalog.ride_base(f.airport, catalog.ride_area(f.airport, first_stay), "arrive")[1]
    return tm.Square(lane.key, w.key, tm.OK, flight, tuple(stays), drive, None, True)


def _stay_part(place, a, b, s: liteapi.Stay) -> tm.StayPart:
    board = "breakfast" if s.board == "breakfast" else s.board
    rating = " · ".join(x for x in (f"{s.rating:g} of 10" if s.rating else "", f"{s.reviews:,} reviews" if s.reviews else "") if x)
    return tm.StayPart(place.name, (b - a).days, s.name, s.room, board, s.refundable, s.due_at_stay_cents, s.photo, rating, s.cents + s.due_at_stay_cents)


def _leg_words(leg) -> str:
    return (f"{_day_clock(leg.depart)}{leg.origin} {tripgrid.clock(leg.depart.hour * 60 + leg.depart.minute)} → {leg.destination} "
            f"{tripgrid.clock(leg.arrive.hour * 60 + leg.arrive.minute)}{' next day' if leg.arrive.date() > leg.depart.date() else ''} · {_stops_text(leg.stops)}")


def _pick_stay(items):
    return next((s for s in items if (s.rating or 0) >= RATED), items[0])


def _liteapi_square(lane, w, adults, kid_ages, home, family, peek, rank=0):
    split = tm.stays_for(lane, w)
    if not home or split is None:
        return None if peek else tm.Square(lane.key, w.key, tm.FAILED if not home else tm.NONE)
    party = {"adults": adults, "kid_ages": tuple(kid_ages), "family": family, "cached_only": peek, "rank": rank}
    legs = tm.legs_for(lane, w, home)
    asks = [lambda: liteapi.flights(legs=legs, **party)] + [lambda p=p, a=a, b=b: liteapi.stays(city=p.city, country=COUNTRY, checkin=a, checkout=b, **party) for p, a, b in split]
    if peek:
        answers = [ask() for ask in asks]
        if any(a is None for a in answers):
            return None
    else:
        with ThreadPoolExecutor(len(asks)) as pool:       # side by side: a flight takes up to 16 s, a stay 2
            answers = [f.result() for f in [pool.submit(ask) for ask in asks]]
    fetched = min((a.fetched for a in answers if a.fetched), default=None)
    if any(a.status == liteapi.OVER for a in answers):
        return tm.Square(lane.key, w.key, tm.OVER, fetched=fetched)
    if not all(a.ok for a in answers):
        return tm.Square(lane.key, w.key, tm.FAILED, fetched=fetched)
    fl, *st = answers
    if not fl.items or not all(a.items for a in st):
        return tm.Square(lane.key, w.key, tm.NONE, fetched=fetched)
    f = fl.items[0]
    flight = tm.FlightPart(f.airline, _leg_words(f.legs[0]), _leg_words(f.legs[-1]) if len(f.legs) > 1 else "", f.stops, f.cents, fl.complete)
    stays = tuple(_stay_part(p, a, b, _pick_stay(ans.items)) for (p, a, b), ans in zip(split, st))
    first = lane.places[0]
    drive = airportdrive.kept(first.iata, first.town) if peek else airportdrive.drive(first.iata, first.town)
    return tm.Square(lane.key, w.key, tm.OK, flight, stays, drive.minutes if drive else None, fetched)


def _square(lane, w, adults=2, kid_ages=(), home="", family="", peek=False, rank=0):
    if showcase.on():
        return _catalog_square(lane, w, adults, kid_ages, home)
    return _liteapi_square(lane, w, adults, kid_ages, home, family, peek, rank)


SQUARE = _square


def square(lane, window, adults=2, kid_ages=(), home="", family="", peek=False, rank=0):
    return SQUARE(lane, window, adults=adults, kid_ages=tuple(kid_ages), home=home, family=family, peek=peek, rank=rank)
