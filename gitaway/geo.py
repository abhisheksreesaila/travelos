"""Where places are and how long it takes to drive between them (F-068), from free public services and no keys.

- `coords(place, db)` -> (lat, lon) | None: OpenStreetMap's Nominatim, at most one request a second for the whole process, with GitAway's
  User-Agent (their usage policy). Airports ("LAX airport") come from gitaway.airport_coords and are never looked up.
- `drive_minutes(a, b, db)` -> minutes | None and `route(points, db)` -> a GeoJSON line | None: OSRM's public server.
- Everything the services answer is cached in the family's own database (`geo_cache`), so each place and each drive is asked once.
  "No such place" is cached too; a failed call is not, so the next visit tries again.
- Nothing here is ever called from a test with the network: tests replace `fetch`. Pages never wait on the network for long: `warm` fills what it
  can inside a time budget and says how much is left, and `warm_async` finishes the rest in a background thread.
- `cached_minutes` reads only the cache, for pages (Today's "Leave by") that must not wait.
"""

import json
import re
import threading
import time
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from sqlalchemy import text

from gitaway import familydb
from gitaway.airport_coords import AIRPORT_COORDS

USER_AGENT = "GitAway/1.0 (+https://web-production-2d117.up.railway.app)"
NOMINATIM = "https://nominatim.openstreetmap.org/search?format=json&q={q}&limit=1"
OSRM = "https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson"
TIMEOUT = 4  # seconds a single call may take
MISSING = "missing"  # state(): the service has no such place
_AIRPORT = re.compile(r"^([A-Z]{3}) airport$")

_clock = time.monotonic
_sleep = time.sleep


class Gate:
    """At most one call per `gap` seconds, shared by every thread of the process."""

    def __init__(self, gap):
        self.gap, self.last, self.lock = gap, None, threading.Lock()

    def delay(self) -> float:
        """Seconds a call made now would have to wait."""
        return 0.0 if self.last is None else max(0.0, self.last + self.gap - _clock())

    def wait(self):
        with self.lock:
            if (d := self.delay()) > 0:
                _sleep(d)
            self.last = _clock()


NOMINATIM_GATE = Gate(1.0)  # Nominatim's policy: an absolute maximum of one request per second
OSRM_GATE = Gate(0.25)      # the public router has no stated limit; stay polite


def fetch(url, timeout=TIMEOUT):
    """GET a URL and parse the JSON. Raises on any failure. Tests replace this."""
    with urlopen(Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}), timeout=timeout) as r:  # noqa: S310 - fixed https hosts above
        return json.loads(r.read().decode("utf-8"))


def _norm(place) -> str:
    return " ".join(str(place or "").lower().split())


# ---- the cache --------------------------------------------------------------------------------------------------------

def _get(db, kind, key):
    if db is None:
        return None
    return familydb.row(db, "SELECT * FROM geo_cache WHERE pk = :pk", pk=f"{kind}|{key}")


def _put(db, kind, key, *, lat=None, lon=None, found=1, data=""):
    if db is None:
        return
    with familydb.transaction(db):
        familydb.run(db, "INSERT OR REPLACE INTO geo_cache (pk, kind, key, lat, lon, found, data, created_at) VALUES (:pk, :kind, :key, :lat, :lon, :found, :data, :at)",
                     pk=f"{kind}|{key}", kind=kind, key=key, lat=lat, lon=lon, found=found, data=data, at=familydb.now())


# ---- places -----------------------------------------------------------------------------------------------------------

def as_place(place) -> str:
    """The text to look up: a bare airport code (a car desk "LAX") means that airport."""
    p = str(place or "").strip()
    return f"{p} airport" if len(p) == 3 and p.isalpha() and p.isupper() else p


def state(place, db=None):
    """(what is known, display name): (None, None) when never looked up (or the lookup failed), (MISSING, None) when the service has no such place,
    else ((lat, lon), display name). Reads only the table of airports and the cache."""
    m = _AIRPORT.match(str(place or "").strip())
    if m and m.group(1) in AIRPORT_COORDS:
        return AIRPORT_COORDS[m.group(1)], f"{m.group(1)} airport"
    hit = _get(db, "place", _norm(place))
    if hit is None:
        return None, None
    if not hit["found"]:
        return MISSING, None
    return (hit["lat"], hit["lon"]), hit["data"] or None


def find(place, db=None, *, deadline=None):
    """Ask Nominatim for `place` (when it is not known yet) and cache the answer. Returns state()'s answer. With a `deadline` (a _clock() time) a
    lookup that would have to wait past it is not made."""
    known = state(place, db)
    if known[0] is not None or not _norm(place):
        return known
    if deadline is not None and _clock() + NOMINATIM_GATE.delay() > deadline:
        return known
    NOMINATIM_GATE.wait()
    try:
        found = fetch(NOMINATIM.format(q=quote_plus(str(place).strip())))
        if not isinstance(found, list):
            raise ValueError("unexpected answer")
        top = found[0] if found else None
        if top is not None:
            lat, lon = float(top["lat"]), float(top["lon"])
    except Exception:  # offline, slow, refused or garbled: not remembered, tried again next time
        return None, None
    if top is None:
        _put(db, "place", _norm(place), found=0)
        return MISSING, None
    _put(db, "place", _norm(place), lat=lat, lon=lon, data=str(top.get("display_name", "")))
    return (lat, lon), str(top.get("display_name", "")) or None


def coords(place, db=None, *, lookup=True):
    """(lat, lon) of a place, or None when it is not known (not found, or not looked up yet when `lookup` is False)."""
    got = (find(place, db) if lookup else state(place, db))[0]
    return got if isinstance(got, tuple) else None


# ---- drives -----------------------------------------------------------------------------------------------------------

def _pair_key(a, b):
    return f"{a[0]:.4f},{a[1]:.4f};{b[0]:.4f},{b[1]:.4f}"


def _leg(a, b, db=None, *, fetch_it=True):
    """{"m": minutes, "g": GeoJSON line} for a drive from `a` to `b` (lat, lon pairs), cached; None when unknown or the router fails."""
    key = _pair_key(a, b)
    hit = _get(db, "drive", key)
    if hit is not None:
        try:
            return json.loads(hit["data"])
        except ValueError:
            pass
    if not fetch_it:
        return None
    OSRM_GATE.wait()
    try:
        r = fetch(OSRM.format(lat1=a[0], lon1=a[1], lat2=b[0], lon2=b[1]))
        top = r["routes"][0]
        if r.get("code") != "Ok":
            raise ValueError("no route")
        leg = {"m": max(1, round(float(top["duration"]) / 60)), "g": top["geometry"]}
        if leg["g"].get("type") != "LineString":
            raise ValueError("no line")
    except Exception:
        return None
    _put(db, "drive", key, data=json.dumps(leg))
    return leg


def drive_minutes(a, b, db=None, *, lookup=True):
    """Minutes by car from `a` to `b` ((lat, lon) pairs), or None on any failure."""
    leg = _leg(a, b, db, fetch_it=lookup)
    return leg["m"] if leg else None


def route(points, db=None, *, lookup=True):
    """A GeoJSON LineString through the points in order (lon, lat), or None unless every leg is known."""
    if len(points) < 2:
        return None
    line = []
    for a, b in zip(points, points[1:]):
        leg = _leg(a, b, db, fetch_it=lookup)
        if not leg:
            return None
        line.extend(leg["g"]["coordinates"] if not line else leg["g"]["coordinates"][1:])
    return {"type": "LineString", "coordinates": line}


def cached_minutes(place_a, place_b, db=None):
    """Drive minutes between two places from what is already cached (no network, ever), else None."""
    a, b = coords(place_a, db, lookup=False), coords(place_b, db, lookup=False)
    return drive_minutes(a, b, db, lookup=False) if a and b else None


# ---- filling the cache ------------------------------------------------------------------------------------------------

def warm(db, places, budget=2.0) -> int:
    """Look up the places and the drives between consecutive found ones, for at most about `budget` seconds. Returns how many lookups are left."""
    deadline = _clock() + budget
    for p in places:
        find(p, db, deadline=deadline)
    left = sum(1 for p in places if state(p, db)[0] is None and _norm(p))
    pts = [c for p in places if isinstance(c := state(p, db)[0], tuple)]
    for a, b in zip(pts, pts[1:]):
        if _get(db, "drive", _pair_key(a, b)) is not None or a == b:
            continue
        if _clock() + OSRM_GATE.delay() > deadline:
            left += 1
            continue
        if _leg(a, b, db) is None:
            left += 1
    return left


ASYNC = True  # tests switch it off
_BUSY = set()
_BUSY_LOCK = threading.Lock()


def warm_async(session, places):
    """Finish `warm` in a background thread with its own database handle (the page has already been sent). One thread per family and list of places."""
    places = tuple(p for p in places if _norm(p))
    key = (session.get("tenant_id"), places)
    if not ASYNC or not places:
        return
    with _BUSY_LOCK:
        if key in _BUSY:
            return
        _BUSY.add(key)

    def run():
        try:
            with familydb.using(dict(session)) as db:
                if db is not None:
                    warm(db, list(places), budget=90)
        except Exception:  # a background fill never matters enough to raise
            pass
        finally:
            with _BUSY_LOCK:
                _BUSY.discard(key)

    threading.Thread(target=run, daemon=True, name="geo-warm").start()
