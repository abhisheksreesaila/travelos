"""Filling the map cache for a whole trip (F-068), so "Leave by" works without opening the Map first.

`day_places` lists, for each day, the places in order (the stay the night before, then the day's stops); `warm` hands them to gitaway.geo's background
fill. It runs after a trip is saved or edited (gitaway.importer.save) and, throttled to once per trip per hour, when Today draws. Never blocks.
"""

import time

from gitaway import geo, session as ses, tripcal as cal, tripday as td

_KICKED = {}  # (family, trip) -> when Today last started a fill
HOUR = 3600


def day_places(session) -> list:
    """[[place, ...] for each day]: where you slept the night before (when the trip says), then every stop with a place, in time order."""
    b = ses.booking(session)
    if not b:
        return []
    t = cal.trip("", b)
    dates = cal.days(t)
    blocks = cal.booked_blocks(b, t)
    acts = cal.activities(session)
    dest = t.destination_name
    out = []
    for i in range(len(dates)):
        stops = []
        for blk in blocks:
            if blk.day == i and (p := td._place_of(blk, td.hotel_place(b, dates, i))):
                stops.append((blk.at, p))
        stops += [(a.start, f"{a.title}, {dest}") for a in acts if a.day == i]
        flies = any(blk.day == i and blk.icon == "plane" for blk in blocks)  # a travel day starts at the airport, not at the stay
        before = td.hotel_place(b, dates, i - 1) if i and not flies else ""
        day = ([before] if before else []) + [geo.as_place(p) for _, p in sorted(stops)]
        if len(day) > 1 or (day and not before):
            out.append(day)
    return out


def warm(session, force=False):
    """Start the background fill for the open trip. Without `force` (Today) at most once an hour for the same trip and the same places: a new plan
    is a new set of places, so it is looked up on the next draw."""
    groups = day_places(session)
    if not groups:
        return
    key = (session.get("tenant_id"), ses.open_trip_id(), repr(groups))
    now = time.monotonic()
    if not force and now - _KICKED.get(key, -HOUR * 2) < HOUR:
        return
    for k in [k for k, t in _KICKED.items() if now - t >= HOUR]:
        del _KICKED[k]
    _KICKED[key] = now
    geo.warm_async(session, groups)
