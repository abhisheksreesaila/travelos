"""See it from above (F-284, D-905..D-909, docs/design/flyaround): what is around a hotel, read from OpenStreetMap by the server, and the gate to Google's imagery.

    pins(key, lat, lon, name)        the truth pins and the heads-up for a hotel: asked of Overpass once, kept AGE days in community.db (`aerial_osm`), None when no host answered and nothing is kept
    sample(which)                    the same for the showcase's recorded answers (tests/fixtures/aerial/): Hilton Los Angeles Airport and Hyatt Regency Lake Tahoe, labelled as a saved copy
    warm(key, lat, lon, name, who)   ask a hotel's pins in the background when its square shows it (a bounded queue, one worker thread, one job in flight per hotel); run_pending() does the queue now (tests)
    teaser(key)                      the heads-up line for the card, only from what is kept (it never waits on the network); "" when nothing is kept
    open_google()                    one more photoreal or satellite open today: ("ok", the browser key), ("full", None) past GOOGLE_3D_A_DAY (default 100) or ("off", None) without GOOGLE_MAPS_API_KEY
    analyse(lat, lon, data)          pins and heads-up from an Overpass answer, every distance worked out here (the page only draws them)

Nothing here is invented: a pin is an OpenStreetMap feature with its own tags, a heads-up line is worded from the distances computed from those, and "nothing mapped within 2 km" says only
what the map holds. The page's key for Google is handed out only by `open_google`, which counts each open in the database (a restart does not reset it): each open is a billed root request.

Overpass is asked at fixed mirrors only (HOSTS, each in turn when the one before fails; a failing mirror sits out MIRROR_WAIT), one GET each within HOST_TIMEOUT (BACKGROUND_TIMEOUT when nobody waits) through gitaway/deadline.py's watchdog, a generic User-Agent (never a person's
address), at most MAX_BYTES read, two asks at a time. A 200 is not success (F-201's lesson): an answer with a `remark` about a timeout or memory, or with no elements, is a failure and is never
kept. `TRANSPORT` is the one function that touches the network, (host, query, timeout) -> (status, body bytes); tests replace it.
"""

import http.client
import json
import logging
import math
import os
import queue
import socket
import ssl
import threading
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

from sqlalchemy import text

from gitaway import community
from gitaway.deadline import get as get_by_deadline, handshake
from gitaway.weather import _lookup

log = logging.getLogger("gitaway.aerial")

HOSTS = ("overpass-api.de", "overpass.kumi.systems", "maps.mail.ru")      # fixed mirrors, tried in this order (checked 17 Nov 2026; overpass.private.coffee gave no answer to a tiny query and is not listed)
PATH = "/api/interpreter"
PATHS = {"maps.mail.ru": "/osm/tools/overpass/api/interpreter"}      # a mirror that does not serve at PATH
RADIUS = 2000
HOST_TIMEOUT = 8.0                   # seconds a host has, lookup to last byte, when a person waits for the answer
BACKGROUND_TIMEOUT = 40.0            # ... when a worker asks ahead and nobody waits (the mirrors answer slowly on a busy day)
MIRROR_WAIT = 300.0                  # a mirror that failed is not asked again for this long, by anyone
QUEUE_MAX = 16                       # hotels waiting for a background ask; the rest are dropped (the tap asks for itself)
ASYNC = True                         # False in the tests, which run the queue with run_pending()
PINS_PER_PERSON_A_DAY = 30           # fresh Overpass asks one visitor or family may start in a day (kept answers are free)
BUSY, LIMIT = {"busy": True}, {"limit": True}      # what `pins` answers when Overpass has no free slot, or this person has used their fresh asks
AT_ONCE = 2                          # asks to Overpass in flight at once, for the whole site
FAIL_WAIT = 60.0                     # after every host failed, nobody asks again for that hotel for this long
MAX_BYTES = 4_000_000
AGE = timedelta(days=7)              # a kept answer is fresh this long ("cached per hotel for days")
STALE = timedelta(days=60)           # when no host answers, a kept answer this old is still shown, said to be a saved copy
VERSION = 1                          # bump when `analyse` changes: kept answers of an older version are asked again
DEFAULT_A_DAY = 100
DEFAULT_PER_PERSON = 10
FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "aerial"
SAMPLES = {"lax": ("Hilton Los Angeles Airport", 33.9461921, -118.3816538, "osm-lax.json"),
           "tahoe": ("Hyatt Regency Lake Tahoe", 39.2407285, -119.9426988, "osm-tahoe.json")}
SRI = {"maplibre": "sha384-SYKAG6cglRMN0RVvhNeBY0r3FYKNOJtznwA0v7B5Vp9tr31xAHsZC0DqkQ/pZDmj", "cesium": "sha384-xAdxnnaIzRit+cIXQWeImuZHfoK0MA0EaxSb8rlO3RaT9NWVqgvICnDMtPUI/aar"}      # integrity hashes of maplibre-gl@4.7.1/dist/maplibre-gl.js and cesium@1.123.0/Build/Cesium/Cesium.js, checked 16 Nov 2026 (assets/js/aerial.js VERSIONS)
NEUTRAL = "Freeways, flight paths, water and parking around the hotel"
_BAD = ("runtime error", "timed out", "out of memory", "too many requests", "dispatcher_client")      # Overpass's own words for a partial answer (`remark`)
_LOCK = threading.Lock()
_SLOTS = threading.BoundedSemaphore(AT_ONCE)
_failed: dict = {}                   # hotel key -> monotonic time of its last failure
_down: dict = {}                     # mirror -> monotonic time it last failed
_inflight: set = set()               # hotel keys queued or being asked
_Q: queue.Queue = queue.Queue(QUEUE_MAX)
_thread: list = []


# ---- asking Overpass ----------------------------------------------------------------------------------------------------------

def user_agent() -> str:
    """A generic client name and the site's address: Overpass's usage policy asks for one, and it never carries a person's contact."""
    from gitaway.blogbutton import base_url
    return f"GitAway/1.0 {base_url()}"


def query(lat: float, lon: float) -> str:
    """Overpass QL: what matters within RADIUS metres (runways and terminals, freeways and trunk and primary roads, beaches, the coast, named lakes, supermarkets, restaurants, parking
    above ground), tags and centres first, then the geometry of runways, big roads (1.2 km) and shores, which the distances are measured to."""
    a = f"around:{RADIUS},{lat:.6f},{lon:.6f}"
    return f"""[out:json][timeout:20];
(
 way({a})[aeroway=runway];
 way({a})[aeroway=terminal];
 way({a})[highway~"^(motorway|trunk|primary)$"];
 nwr({a})[natural=beach];
 way({a})[natural=coastline];
 nwr({a})[shop=supermarket];
 nwr({a})[amenity=restaurant];
 nwr({a})[amenity=parking][parking!=underground];
);
out tags center qt;
rel({a})[natural=water][name];
way(r)({a});
out tags geom qt;
(way({a})[aeroway=runway];way(around:1200,{lat:.6f},{lon:.6f})[highway~"^(motorway|trunk|primary)$"];way({a})[natural=coastline];);
out tags geom qt;"""


def _connection(host, ips, deadline):
    class Conn(http.client.HTTPSConnection):
        def connect(self):
            raw, failed = None, None
            for i, ip in enumerate(ips):
                left = deadline - time.monotonic()
                if left <= 0:
                    break
                try:
                    raw = socket.create_connection((ip, self.port), left / (len(ips) - i))
                    break
                except OSError as e:
                    failed = e
            if raw is None:
                raise failed or TimeoutError(f"no address of {host} answered in time")
            handshake(self, raw, self._context, deadline)

    return Conn(host, 443, timeout=max(0.05, deadline - time.monotonic()), context=ssl.create_default_context())


def _http(host, q, timeout):
    """One GET `https://<host>/api/interpreter?data=<q>`, all of it (lookup, connect, handshake, answer) within `timeout` seconds: (status, body). `host` must be one of HOSTS; a redirect is
    an answer that is not a 200 and is never followed."""
    if host not in HOSTS:
        raise ValueError("GitAway asks only the Overpass hosts it lists")
    deadline = time.monotonic() + timeout
    conn = _connection(host, _lookup(host, deadline), deadline)
    status, _headers, body = get_by_deadline(conn, f"{PATHS.get(host, PATH)}?data={quote(q, safe='')}", {"User-Agent": user_agent(), "Accept": "application/json", "Accept-Encoding": "identity"}, deadline, MAX_BYTES + 1)
    return status, body


TRANSPORT = _http


def _read(body) -> dict | None:
    """An Overpass answer that is a whole answer: JSON with elements and no remark about a runtime error. Anything else is None."""
    if not body or len(body) > MAX_BYTES:
        return None
    try:
        data = json.loads(body)
    except ValueError:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("elements"), list) or not data["elements"]:
        return None
    if any(w in str(data.get("remark", "")).lower() for w in _BAD):
        return None
    return data


def ask(lat: float, lon: float, timeout: float = HOST_TIMEOUT) -> tuple | None:
    """(the answer, the host that gave it) from the first of HOSTS that gives a whole one, else None. A mirror that failed lately is skipped (MIRROR_WAIT). Two asks at a time; a request that
    finds both slots taken gets BUSY at once."""
    if not _SLOTS.acquire(blocking=False):      # both slots are busy: no request holds a worker thread waiting for Overpass; the page says "busy"
        return BUSY
    try:
        q = query(lat, lon)
        for host in HOSTS:
            if time.monotonic() - _down.get(host, -MIRROR_WAIT) < MIRROR_WAIT:
                continue
            try:
                status, body = TRANSPORT(host, q, timeout)
            except (OSError, TimeoutError, ValueError) as e:        # refused, a bad certificate, the deadline: the next host
                log.warning("Overpass %s: %s", host, type(e).__name__)
                _down[host] = time.monotonic()
                continue
            data = _read(body) if status == 200 else None
            if data is not None:
                _down.pop(host, None)
                return data, host
            log.warning("Overpass %s answered %s without a whole answer", host, status)
            _down[host] = time.monotonic()
        return None
    finally:
        _SLOTS.release()


# ---- geometry: every distance is worked out here -----------------------------------------------------------------------------

R_EARTH = 6371008.8


def _proj(lat0):
    k = math.cos(math.radians(lat0))
    return lambda lat, lon: (math.radians(lon) * R_EARTH * k, math.radians(lat) * R_EARTH)


def haversine(a, b) -> float:
    dlat, dlon = math.radians(b[0] - a[0]), math.radians(b[1] - a[1])
    s = math.sin(dlat / 2) ** 2 + math.cos(math.radians(a[0])) * math.cos(math.radians(b[0])) * math.sin(dlon / 2) ** 2
    return 2 * R_EARTH * math.asin(math.sqrt(s))


def nearest_on_line(hotel, pts):
    """(metres, (lat, lon)) of the point of a polyline nearest the hotel (flat around the hotel, exact enough under 2 km)."""
    p = _proj(hotel[0])
    h = p(*hotel)
    best = (math.inf, pts[0])
    for i in range(len(pts) - 1):
        a, b = p(*pts[i]), p(*pts[i + 1])
        vx, vy = b[0] - a[0], b[1] - a[1]
        length = vx * vx + vy * vy or 1
        t = max(0, min(1, ((h[0] - a[0]) * vx + (h[1] - a[1]) * vy) / length))
        d = math.hypot(h[0] - (a[0] + t * vx), h[1] - (a[1] + t * vy))
        if d < best[0]:
            best = (d, (pts[i][0] + t * (pts[i + 1][0] - pts[i][0]), pts[i][1] + t * (pts[i + 1][1] - pts[i][1])))
    return best


def runway_relation(hotel, pts):
    """How a runway's line meets the hotel: sideways from the centreline, how far past the nearer end, and which side (the same for parallel runways drawn either way)."""
    p = _proj(hotel[0])
    h, a, b = p(*hotel), p(*pts[0]), p(*pts[-1])
    vx, vy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(vx, vy) or 1
    ux, uy = vx / length, vy / length
    along = (h[0] - a[0]) * ux + (h[1] - a[1]) * uy
    cross = (h[0] - a[0]) * uy - (h[1] - a[1]) * ux
    past = -along if along < 0 else along - length if along > length else 0
    sign = (cross > 0) - (cross < 0)
    return abs(cross), past, sign * ((ux > 0) - (ux < 0) or 1)


def walk_min(m) -> int:
    return max(1, round(m * 1.25 / 80))


def drive_min(m) -> int:
    return max(1, round(m * 1.4 / 500 + 2))


def how_far(m) -> tuple:
    """("7 min", "walk") up to a twenty minute walk, else the drive."""
    w = walk_min(m)
    return (f"{w} min", "walk") if w <= 20 else (f"{drive_min(m)} min", "drive")


def metres(m) -> str:
    return f"{round(m / 10) * 10} m" if m < 950 else f"{m / 1000:.1f} km"


# ---- the pins and the heads-up -----------------------------------------------------------------------------------------------

def _at(e):
    if e.get("center"):
        return (e["center"]["lat"], e["center"]["lon"])
    if e.get("lat") is not None:
        return (e["lat"], e["lon"])
    return None


def _pin(kind, title, sub, d=None, at=None) -> dict:
    far = how_far(d) if d is not None else None
    return {"kind": kind, "title": title, "sub": sub, "m": round(d) if d is not None else None, "far": far[0] if far else "", "by": far[1] if far else "", "dist": metres(d) if d is not None else "",
            "lat": at[0] if at else None, "lon": at[1] if at else None}


def analyse(lat: float, lon: float, data: dict) -> dict:
    """{"pins": [six pins], "heads": [{text, more, good}], "headline"} from an Overpass answer: flights, road, water, grocery, food and parking, each nearest or densest, each with its distance
    from the hotel's door as the crow flies; a heads-up only for what is loud (a flight path, a freeway under 400 m, many car parks) or good (water within a 15 minute walk)."""
    hotel = (lat, lon)
    geoms, items = {}, []
    for e in data.get("elements", []):
        if e.get("geometry"):
            geoms[e["id"]] = (e.get("tags") or {}, [(g["lat"], g["lon"]) for g in e["geometry"]])
        else:
            items.append(e)

    def tags(e):
        return e.get("tags") or {}

    def named(t, fallback):
        return t.get("name") or t.get("brand") or t.get("ref") or fallback

    def rw(ref):
        return f"runway {ref}" if ref else "the runway"

    pins, heads = [], []
    best, approaches = None, []
    for t, pts in geoms.values():
        if t.get("aeroway") != "runway" or len(pts) < 2:
            continue
        d, at = nearest_on_line(hotel, pts)
        side, past, sign = runway_relation(hotel, pts)
        if best is None or d < best[0]:
            best = (d, at, f"Runway {t['ref']}" if t.get("ref") else "Runway")
        if side < 900 and 0 < past < 6000:
            approaches.append((side, past, sign, t.get("ref") or ""))
    terms = sorted(((haversine(hotel, _at(e)), e) for e in items if tags(e).get("aeroway") == "terminal" and _at(e)), key=lambda x: x[0])
    term = terms[0] if terms else None
    if best:
        pins.append(_pin("flight", best[2], f"Nearest terminal {metres(term[0])} · {named(tags(term[1]), 'terminal')}" if term else "Airport runway", best[0], best[1]))
    elif term:
        pins.append(_pin("flight", named(tags(term[1]), "Airport terminal"), "Airport terminal", term[0], _at(term[1])))
    else:
        pins.append(_pin("flight", "No airport within 2 km", "Nothing mapped"))
    approaches.sort(key=lambda a: a[0])
    flight = approaches[0] if approaches else None
    if flight and flight[0] < 400:
        heads.append((3, "Under the flight path", f"In line with {rw(flight[3])}, {metres(flight[1])} past its end"))
    elif flight and len({a[2] for a in approaches}) > 1:
        pos = next(a for a in approaches if a[2] > 0)
        neg = next(a for a in approaches if a[2] < 0)
        heads.append((3, "Between two flight paths", f"Landing planes pass {(metres(pos[0]) + ' ') if pos[0] < 1000 else ''}to one side and {metres(neg[0])} to the other, {metres(flight[1])} before the runways"))
    elif flight:
        heads.append((3, "Beside the flight path", f"{rw(flight[3]).capitalize()}'s approach passes {metres(flight[0])} away, {metres(flight[1])} before the runway"))
    elif best and best[0] < 1500:
        heads.append((3, f"Runway {metres(best[0])} away", "Expect jet noise, day and night"))

    def nearest_road(kinds):
        r = None
        for t, pts in geoms.values():
            if t.get("highway") in kinds and len(pts) > 1:
                d, at = nearest_on_line(hotel, pts)
                if r is None or d < r[0]:
                    r = (d, at, t)
        if r is None:      # the geometry query reaches 1.2 km; the rest of the 2 km is known by its centre
            c = sorted(((haversine(hotel, _at(e)), e) for e in items if tags(e).get("highway") in kinds and _at(e)), key=lambda x: x[0])
            if c:
                r = (c[0][0], _at(c[0][1]), tags(c[0][1]))
        return r

    road = nearest_road(("motorway", "trunk")) or nearest_road(("primary",))
    if road:
        d, at, t = road
        ref = (t.get("ref") or "").split(";")[0]
        label = f"{ref} · {t['name']}" if ref and t.get("name") else (t.get("ref") or t.get("name") or ("Freeway" if t.get("highway") == "motorway" else "Highway"))
        hw = t.get("highway")
        pins.append(_pin("road", label, "Freeway: traffic noise" if hw == "motorway" else "Highway: through traffic" if hw == "trunk" else "Main road: through traffic", d, at))
        if d < 400 and hw != "primary":
            heads.append((2.5 if d < 200 else 1.5, f"{'Freeway' if hw == 'motorway' else 'Highway'} {metres(d)} away", label))
    else:
        pins.append(_pin("road", "No freeway within 2 km", "Nothing mapped"))

    water = None      # a beach, the coast, or a named lake's shore
    for t, pts in geoms.values():
        if t.get("aeroway") or t.get("highway") or len(pts) < 2:
            continue
        d, at = nearest_on_line(hotel, pts)
        title = "Ocean shore" if t.get("natural") == "coastline" else (f"{t['name']} shore" if t.get("name") else "Lake shore")
        if water is None or d < water[0]:
            water = (d, at, title, "Nearest water's edge")
    for e in items:
        if tags(e).get("natural") != "beach" or not _at(e):
            continue
        d = haversine(hotel, _at(e))
        if water is None or d < water[0] + 150:
            if water is None or d < water[0] or water[3] != "Beach":
                water = (d, _at(e), named(tags(e), "Beach"), "Beach")
    if water:
        pins.append(_pin("water", water[2], water[3], water[0], water[1]))
        if walk_min(water[0]) <= 15:
            heads.append((1, f"{'Beach' if water[3] == 'Beach' else 'Water'} {walk_min(water[0])} min walk", water[2], True))
    else:
        pins.append(_pin("water", "No beach or shore within 2 km", "Nothing mapped"))

    shops = sorted(((haversine(hotel, _at(e)), e) for e in items if tags(e).get("shop") == "supermarket" and _at(e)), key=lambda x: x[0])
    if shops:
        pins.append(_pin("shop", named(tags(shops[0][1]), "Supermarket"), "Nearest supermarket", shops[0][0], _at(shops[0][1])))
    else:
        pins.append(_pin("shop", "No supermarket within 2 km", "Nothing mapped"))

    rs = [(e, _at(e)) for e in items if tags(e).get("amenity") == "restaurant" and _at(e)]      # the densest cluster: most others within 200 m
    if rs:
        top = None
        for _, p in rs:
            near = [o for o in rs if haversine(p, o[1]) < 200]
            if top is None or len(near) > len(top):
                top = near
        c = (sum(o[1][0] for o in top) / len(top), sum(o[1][1] for o in top) / len(top))
        street = next((tags(o[0])["addr:street"] for o in top if tags(o[0]).get("addr:street")), "")
        pins.append(_pin("food", f"{len(top)} restaurants together" if len(top) > 1 else named(tags(top[0][0]), "Restaurant"), f"{street + ' · ' if street else ''}{len(rs)} within 2 km", haversine(hotel, c), c))
    else:
        pins.append(_pin("food", "No restaurants within 2 km", "Nothing mapped"))

    lots = sorted(((haversine(hotel, _at(e)), e) for e in items if tags(e).get("amenity") == "parking" and _at(e)), key=lambda x: x[0])
    if lots:
        near = [x for x in lots if x[0] < 500]
        multi = sum(1 for x in near if tags(x[1]).get("parking") == "multi-storey")
        first = tags(lots[0][1])
        pins.append(_pin("park", named(first, "Parking garage" if first.get("parking") == "multi-storey" else "Parking lot"),
                         f"{len(near)} car parks within 500 m{f', {multi} multi-storey' if multi else ''}", lots[0][0], _at(lots[0][1])))
        if len(near) >= 12:
            heads.append((0.8, f"{len(near)} car parks within 500 m", "Mapped surface lots around the hotel"))
    else:
        pins.append(_pin("park", "No mapped parking nearby", "Nothing mapped"))

    heads.sort(key=lambda h: -h[0])
    out = [{"text": h[1], "more": h[2], "good": bool(h[3]) if len(h) > 3 else False} for h in heads]
    return {"pins": pins, "heads": out, "headline": " · ".join(h["text"] for h in out[:2]) if out else "Nothing loud mapped nearby"}


# ---- kept answers -------------------------------------------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _row(key):
    with community.connect() as db:
        return db.conn.execute(text("SELECT lat, lon, version, fetched, host, body FROM aerial_osm WHERE hotel = :k"), {"k": key}).mappings().first()


def _keep(key, lat, lon, host, result) -> None:
    with community.connect() as db:
        db.conn.execute(text("INSERT INTO aerial_osm (hotel, lat, lon, version, fetched, host, body) VALUES (:k, :a, :o, :v, :f, :h, :b) "
                             "ON CONFLICT(hotel) DO UPDATE SET lat = :a, lon = :o, version = :v, fetched = :f, host = :h, body = :b"),
                          {"k": key, "a": lat, "o": lon, "v": VERSION, "f": _now().isoformat(timespec="seconds"), "h": host, "b": json.dumps(result)})
        db.conn.commit()


def _kept(key, lat, lon, within):
    """(result, fetched datetime, host) of a kept answer for these coordinates, version and age; None otherwise."""
    row = _row(key)
    if not row or row["version"] != VERSION or abs(row["lat"] - lat) > 1e-4 or abs(row["lon"] - lon) > 1e-4:
        return None
    fetched = datetime.fromisoformat(row["fetched"])
    if _now() - fetched > within:
        return None
    return json.loads(row["body"]), fetched, row["host"]


def _words(fetched: datetime, host: str, saved: bool) -> str:
    day = f"{fetched.day} {fetched:%b %Y}"
    return (f"OpenStreetMap is busy right now, so these are from a copy saved on {day}, within 2 km." if saved
            else f"From OpenStreetMap ({host}), asked on {day}, within 2 km.")


def teaser(key: str) -> str:
    """The card's one line: the top heads-up of a kept answer, "" when nothing fresh is kept (the card then says what it shows, never waiting on the network)."""
    row = _row(key)
    if not row or row["version"] != VERSION or _now() - datetime.fromisoformat(row["fetched"]) > STALE:
        return ""
    return json.loads(row["body"]).get("headline", "")


def pins(key: str, lat: float, lon: float, name: str, who: str = "", timeout: float = HOST_TIMEOUT) -> dict | None:
    """The hotel's truth: {"name", "lat", "lon", "pins", "heads", "headline", "source", "source_text"} or None when Overpass gave nothing and nothing is kept. Fresh kept answers cost nothing;
    otherwise one ask (two hosts at most); every host failing is remembered for FAIL_WAIT so a tab that keeps asking cannot hammer a public service."""
    kept = _kept(key, lat, lon, AGE)
    if kept:
        result, fetched, host = kept
        return {**result, "name": name, "lat": lat, "lon": lon, "source": "kept", "source_text": _words(fetched, host, False)}
    if time.monotonic() - _failed.get(key, -FAIL_WAIT) >= FAIL_WAIT:
        if who and not _take("pins:" + who, PINS_PER_PERSON_A_DAY):
            return LIMIT
        got = ask(lat, lon, timeout)
        if got is BUSY:      # no slot free: nothing was asked, so the person's pin is given back
            if who:
                _give("pins:" + who)
            return BUSY
        if got:
            _failed.pop(key, None)
            result = analyse(lat, lon, got[0])
            _keep(key, lat, lon, got[1], result)
            return {**result, "name": name, "lat": lat, "lon": lon, "source": "live", "source_text": _words(_now(), got[1], False)}
        _failed[key] = time.monotonic()
    old = _kept(key, lat, lon, STALE)
    if old:
        return {**old[0], "name": name, "lat": lat, "lon": lon, "source": "saved", "source_text": _words(old[1], old[2], True)}
    return None


# ---- asking ahead: pins are kept by the time anyone looks ---------------------------------------------------------------------

def warm(key: str, lat: float, lon: float, name: str, who: str = "") -> bool:
    """Queue this hotel's pins when its square shows it, unless a fresh answer is kept, the hotel failed lately, or its job is already queued: True when queued. Never waits and never asks
    here; the job goes through `pins`, so the person's daily allowance is counted once, a kept answer is free and Overpass's two slots still hold."""
    if _kept(key, lat, lon, AGE) or time.monotonic() - _failed.get(key, -FAIL_WAIT) < FAIL_WAIT:
        return False
    with _LOCK:
        if key in _inflight:
            return False
        try:
            _Q.put_nowait((key, lat, lon, name, who))
        except queue.Full:
            return False
        _inflight.add(key)
    if ASYNC:
        _start()
    return True


def _one(job) -> None:
    key, lat, lon, name, who = job
    try:
        pins(key, lat, lon, name, who, BACKGROUND_TIMEOUT)
    except Exception:      # noqa: BLE001 (an ask ahead that fails leaves the pins to the card's tap)
        log.exception("pins ahead failed for a hotel")
    finally:
        with _LOCK:
            _inflight.discard(key)


def _work() -> None:
    while True:
        try:
            job = _Q.get(timeout=30)
        except queue.Empty:
            return      # idle: the next warm starts a worker again
        try:
            _one(job)
        finally:
            _Q.task_done()


def _start() -> None:
    with _LOCK:
        if _thread and _thread[0].is_alive():
            return
        t = threading.Thread(target=_work, daemon=True, name="aerial-warm")
        _thread[:] = [t]
        t.start()


def run_pending() -> int:
    """Do every queued job now, on this thread (tests); the number done."""
    n = 0
    while True:
        try:
            job = _Q.get_nowait()
        except queue.Empty:
            return n
        try:
            _one(job)
            n += 1
        finally:
            _Q.task_done()


def clear() -> None:
    """Forget the queue (tests)."""
    with _LOCK:
        while True:
            try:
                _Q.get_nowait()
            except queue.Empty:
                break
        _inflight.clear()


def stop() -> None:
    """Wait for the worker to finish what it is doing (tests)."""
    for t in list(_thread):
        t.join(5)
    _thread.clear()


def sample(which: str) -> dict | None:
    """The showcase's recorded answer for "lax" or "tahoe" (tests/fixtures/aerial/, made by scripts/record_aerial_fixture.py), said to be a saved copy of a real hotel's surroundings."""
    if which not in SAMPLES:
        return None
    name, lat, lon, file = SAMPLES[which]
    path = FIXTURES / file
    if not path.exists():
        return None
    saved = json.loads(path.read_text())
    result = analyse(lat, lon, saved["data"])
    day = date.fromisoformat(saved["recorded"])
    return {**result, "name": name, "lat": lat, "lon": lon, "source": "sample",
            "source_text": f"Sample: a copy of OpenStreetMap saved on {day.day} {day:%b %Y}, within 2 km. The sample hotels in this square are made up; this is a real one, shown to see how the view works.",
            "sample": True}


# ---- the key for Google's imagery, counted -------------------------------------------------------------------------------------

def key() -> str:
    return os.getenv("GOOGLE_MAPS_API_KEY", "").strip()


def offered() -> bool:
    """Are satellite and photoreal offered at all? Only with a browser key set; without one the card shows the map view only."""
    return bool(key())


def cap() -> int:
    try:
        return max(0, int(os.getenv("GOOGLE_3D_A_DAY", "").strip() or DEFAULT_A_DAY))
    except ValueError:
        return DEFAULT_A_DAY


def _today() -> str:
    return _now().date().isoformat()


def opens_today() -> int:
    with community.connect() as db:
        return int(db.conn.execute(text("SELECT COALESCE(SUM(n), 0) FROM aerial_opens WHERE day = :d"), {"d": _today()}).scalar())


def person_cap() -> int:
    try:
        return max(0, int(os.getenv("GOOGLE_3D_PER_PERSON_A_DAY", "").strip() or DEFAULT_PER_PERSON))
    except ValueError:
        return DEFAULT_PER_PERSON


def _take(who: str, limit: int) -> bool:
    """One more for `who` today if their count is under `limit`: one conditional UPDATE (the row is made first, OR IGNORE), so two requests, or two processes, cannot both take the last one."""
    day = _today()
    with community.connect() as db:
        db.conn.execute(text("DELETE FROM aerial_person WHERE day != :d"), {"d": day})
        db.conn.execute(text("INSERT OR IGNORE INTO aerial_person (day, who, n) VALUES (:d, :w, 0)"), {"d": day, "w": who})
        ok = db.conn.execute(text("UPDATE aerial_person SET n = n + 1 WHERE day = :d AND who = :w AND n < :c"), {"d": day, "w": who, "c": limit}).rowcount == 1
        db.conn.commit()
    return ok


def _give(who: str) -> None:
    """Give back one taken today (a refusal that asked nothing)."""
    with community.connect() as db:
        db.conn.execute(text("UPDATE aerial_person SET n = n - 1 WHERE day = :d AND who = :w AND n > 0"), {"d": _today(), "w": who})
        db.conn.commit()


def open_google(who: str = "") -> tuple:
    """Count one satellite or photoreal open for `who` (a signed-in person) and give the page the browser key: ("ok", key), ("person", None) when this person's GOOGLE_3D_PER_PERSON_A_DAY
    (default 10) are spent, ("full", None) when the site's GOOGLE_3D_A_DAY are, ("off", None) without GOOGLE_MAPS_API_KEY. Both counts are conditional UPDATEs in one transaction, so a refusal on
    the site's count gives the person's back and no pair of requests can pass the cap together; rows are in the database, kept across restarts, and yesterday's are dropped. The real hard cap
    is Google's own quota on the Map Tiles API (docs/setup.md)."""
    k = key()
    if not k:
        return "off", None
    day, c = _today(), cap()
    with _LOCK, community.connect() as db:
        db.conn.execute(text("DELETE FROM aerial_opens WHERE day != :d"), {"d": day})
        db.conn.execute(text("DELETE FROM aerial_person WHERE day != :d"), {"d": day})
        db.conn.execute(text("INSERT OR IGNORE INTO aerial_person (day, who, n) VALUES (:d, :w, 0)"), {"d": day, "w": "open:" + who})
        db.conn.execute(text("INSERT OR IGNORE INTO aerial_opens (day, n) VALUES (:d, 0)"), {"d": day})
        if db.conn.execute(text("UPDATE aerial_person SET n = n + 1 WHERE day = :d AND who = :w AND n < :c"), {"d": day, "w": "open:" + who, "c": person_cap()}).rowcount != 1:
            db.conn.rollback()
            return "person", None
        if db.conn.execute(text("UPDATE aerial_opens SET n = n + 1 WHERE day = :d AND n < :c"), {"d": day, "c": c}).rowcount != 1:
            db.conn.rollback()
            return "full", None
        db.conn.commit()
    return "ok", k
