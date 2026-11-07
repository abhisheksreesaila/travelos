"""The paper map's geo pack (F-201): for the region a trip happens in, the relief image the cockpit's paper map is printed on (WebP, light and dark) and
the OpenStreetMap shapes drawn over it (main roads, named lakes, towns, state and country lines). Ported from docs/design/cockpit/tools/fetch_geo.py and
gen_relief.py.

    region(points, anchor)   the box the map covers: the places within REACH_KM of the trip's stay (so not the home airport), padded, MIN_KM a side at least
    build(box, month)        one Overpass query and AWS Terrain Tiles (terrarium elevation) drawn into a soft hillshade: snow above a snow line that follows the
                             month and the latitude, the sea where the ground is below zero; returns a Pack, raises PackError on any failure
    ensure(session)          the open trip's places -> its pack: linked to a pack already built for the same region, else queued for the one worker (never on the
                             event loop, never waited for)
    stored(session)          the open trip's pack (key, box, shapes and the two images), or None

Never a pack from a bad answer, never more than one build at a time (F-201 review):
- An Overpass answer with a "remark" (it timed out or hit its size limit: its elements are partial) or with no road, lake and town at all is a failure. A busy
  box is asked once more with the main roads only (motorway, trunk).
- One worker thread builds packs, one at a time, from a bounded queue (QUEUE_MAX), so at most one relief is ever in memory, and a build has DEADLINE seconds
  for all its calls. Reads are capped (Overpass OVERPASS_CAP, a tile TILE_CAP; [maxsize] in the query too), redirects are refused, and a tile must be a
  256 x 256 PNG before it is decoded. The relief is as big as its elevation needs (LONG_SIDE at most).
- Attempts are kept in the database (`geo_packs`: the day, the count, when the last one failed and why): TRIP_BUDGET builds per trip and FAMILY_BUDGET per
  family a day (UTC), DAILY_CAP for the whole server (Overpass asks one user for under 10,000 queries a day), and a failed build waits RETRY seconds. A tab
  that keeps asking, or a restart, cannot start more.
- Packs are shared by region (the community database's `geo_regions`: the box, the season, the version): a trip in a region already built links to it, so the
  forks of one trip do not ask Overpass again. The shared row holds no person: a box, OpenStreetMap shapes and a relief. The family's `geo_packs` row is the
  trip's link and its attempts; it is deleted with the trip and never written back for a trip that is gone.

The network is reached only through TRANSPORT (tests replace it; the test fixtures refuse it). Overpass gets one query every 5 seconds for the whole process
and the tile bucket ten a second; a 429 or 403 leaves either alone for ten minutes (gitaway.geo.Gate). What leaves the server: the box's corners (to Overpass)
and tile numbers (to AWS); never a place name, a person or a booking.
"""

import hashlib
import io
import json
import logging
import math
import queue
import threading
import time
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

import numpy as np
from PIL import Image
from sqlalchemy import text

from gitaway import around, community, familydb, geo, session as ses

log = logging.getLogger(__name__)

VERSION = 3                 # what a pack holds and how it is drawn: a pack of an older version is built again (3: shared regions, capped reads)
OVERPASS = "https://overpass-api.de/api/interpreter"
TILES = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
TIMEOUT = 60                # seconds one call may take
DEADLINE = 180              # seconds a whole build may take, every call included
QUERY_TIMEOUT = 60          # Overpass's own [timeout]: it stops and says so in a "remark"
QUERY_MAXSIZE = 64 * 1024 * 1024      # Overpass's own [maxsize] (64 MiB of memory for the query)
OVERPASS_CAP = 24 * 1024 * 1024       # bytes read from Overpass at most (the Tahoe box was 6.5 MB; the Disneyland box would be about 30 MB)
TILE_CAP = 1024 * 1024                # bytes of one elevation tile at most (they are about 100 KB)
REACH_KM = 160              # a place further than this from the stay is another region: the home airport, a far day trip
MIN_KM = 24                 # the box is at least this wide and this tall
PAD = 0.16                  # of the places' own span, on every side
EDGE_KM = 10                # and every place at least this far inside the edge: a day's camera on one stop near the edge still shows map, not the sheet's edge
MAX_TILES = 30              # elevation tiles per pack: the zoom is the highest that needs no more
LONG_SIDE = 2048            # pixels on the relief's long side, at most
MIN_SIDE = 768              # ... and at least
UPSAMPLE = 1.4              # relief pixels for each elevation pixel: more is only blur (and memory)
QUALITY = 78                # WebP quality (method 4: about as small as 6 at half the time): 50-110 KB a mode for the Tahoe basin
RETRY = 1800                # seconds before a failed build is tried again
TRIP_BUDGET = 6             # builds per trip a day
FAMILY_BUDGET = 30          # builds per family a day
DAILY_CAP = 500             # builds for the whole server a day (each is one Overpass query; Overpass asks for under 10,000 a day)
QUEUE_MAX = 6               # builds waiting for the worker; more are told to wait
MAX_ROAD_POINTS = 3200      # all roads together, after simplifying (the shapes stay near 30 KB)
MAX_LAKES = 14
MAX_TOWNS = 10

OVERPASS_GATE = geo.Gate(5.0)   # Overpass asks for light use: one query every 5 s for the whole process (a pack needs one, two for a busy box)
TILE_GATE = geo.Gate(0.1)       # the public tile bucket has no stated limit; stay polite

_clock = time.monotonic


def _now() -> datetime:
    """The UTC now the budgets and the retry count from (tests move it)."""
    return datetime.now(timezone.utc)


class PackError(RuntimeError):
    """The pack could not be built: nothing is stored and the next try waits RETRY seconds. `why` says what failed, never where: refused, wait, time, size,
    remark (Overpass timed out or ran out of room), empty, unreadable, network, redirect, tile."""

    def __init__(self, why, detail=""):
        super().__init__(f"{why} {detail}".strip())
        self.why = why


class _NoRedirect(HTTPRedirectHandler):
    """A pack's hosts never redirect; a redirect is refused rather than followed somewhere else."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise PackError("redirect", str(code))


_OPENER = build_opener(_NoRedirect)


def _cap(url) -> int:
    return TILE_CAP if "/terrarium/" in url else OVERPASS_CAP


def transport(url, data=None, timeout=TIMEOUT) -> bytes:
    """GET `url` (or POST the form `data`) and return the body: no redirect, at most the URL's cap (by its Content-Length, then while reading, in chunks), and
    no longer than `timeout` seconds in all. Raises on any failure. Tests replace TRANSPORT."""
    cap, stop = _cap(url), _clock() + timeout
    req = Request(url, data=data, headers={"User-Agent": geo.USER_AGENT, "Accept": "*/*"})
    with _OPENER.open(req, timeout=timeout) as r:  # noqa: S310 - fixed https hosts above
        size = str(r.headers.get("Content-Length", "") or "")
        if size.isdigit() and int(size) > cap:
            raise PackError("size", size)
        out = bytearray()
        while True:
            chunk = r.read(65536)
            if not chunk:
                return bytes(out)
            out += chunk
            if len(out) > cap:
                raise PackError("size", f">{cap}")
            if _clock() > stop:
                raise PackError("time")


TRANSPORT = transport


def _call(gate, url, data=None, deadline=None):
    """TRANSPORT(url) through its gate, never past `deadline` (a _clock() time) and never more than the URL's cap. A 429 or 403 shuts the gate. Raises PackError."""
    if deadline is not None and deadline - _clock() < 1:
        raise PackError("time")
    if not gate.wait(deadline):
        raise PackError("wait" if gate.is_shut() else "time")
    left = TIMEOUT if deadline is None else max(1.0, min(TIMEOUT, deadline - _clock()))
    try:
        body = TRANSPORT(url, data=data, timeout=left)
    except PackError:
        raise
    except Exception as e:
        if getattr(e, "code", None) in (429, 403):
            gate.back_off()
        raise PackError("network", type(e).__name__) from e
    if not isinstance(body, (bytes, bytearray)) or len(body) > _cap(url):
        raise PackError("size")
    if deadline is not None and _clock() > deadline:
        raise PackError("time")
    return bytes(body)


# ---- distances and boxes --------------------------------------------------------------------------------------------

def km_between(a, b) -> float:
    """Great-circle kilometres between two (lat, lon) pairs (gitaway.around's one haversine)."""
    return around.metres(a[0], a[1], b[0], b[1]) / 1000


def box_km(box) -> tuple:
    """(width, height) of a (west, south, east, north) box in kilometres, at its middle latitude."""
    w, s, e, n = box
    return (e - w) * 111.32 * math.cos(math.radians((s + n) / 2)), (n - s) * 110.57


def region(points, anchor=None):
    """The (west, south, east, north) box the paper map covers, or None with no points. `points` are (lat, lon); `anchor` (the stay) decides what is near:
    anything over REACH_KM from it is left out. Longitudes are read from the anchor's side of the date line, so a trip across it is one short span, never the
    whole globe; the box stops at ±180° (Overpass and the tiles cannot cross it). The places' span is padded by PAD on each side (at least EDGE_KM), made at
    least MIN_KM a side, and rounded out to 0.01 degree."""
    pts = [(float(a), float(b)) for a, b in points if a is not None and b is not None and -85 < a < 85 and -180 <= b <= 180]
    if not pts:
        return None
    a = anchor or pts[0]
    near = [(lat, a[1] + ((lon - a[1] + 540) % 360 - 180)) for lat, lon in pts if km_between(a, (lat, lon)) <= REACH_KM] or [(a[0], a[1])]
    s, n = min(p[0] for p in near), max(p[0] for p in near)
    w, e = min(p[1] for p in near), max(p[1] for p in near)
    mid = (s + n) / 2
    kx, ky = 111.32 * math.cos(math.radians(mid)), 110.57
    half_w = max((e - w) * kx * (1 + 2 * PAD), (e - w) * kx + 2 * EDGE_KM, MIN_KM) / 2 / kx
    half_h = max((n - s) * ky * (1 + 2 * PAD), (n - s) * ky + 2 * EDGE_KM, MIN_KM) / 2 / ky
    cx, cy = (w + e) / 2, mid
    return (max(-180.0, math.floor((cx - half_w) * 100) / 100), max(-85.0, math.floor((cy - half_h) * 100) / 100),
            min(180.0, math.ceil((cx + half_w) * 100) / 100), min(85.0, math.ceil((cy + half_h) * 100) / 100))


def covers(box, points, margin_km=2.0) -> bool:
    """True when every point lies inside `box`, at least `margin_km` from its edge."""
    w, s, e, n = box
    for lat, lon in points:
        kx = 111.32 * math.cos(math.radians(lat))
        if not (w + margin_km / kx <= lon <= e - margin_km / kx and s + margin_km / 110.57 <= lat <= n - margin_km / 110.57):
            return False
    return True


def box_key(box) -> str:
    return ",".join(f"{v:.2f}" for v in box)


def parse_box(text_):
    return tuple(float(v) for v in str(text_).split(","))


# ---- lines: simplify and join ---------------------------------------------------------------------------------------

def simplify(points, tol):
    """Douglas-Peucker on [(x, y)] (iterative, so a long road cannot run out of stack). The ends are kept."""
    if len(points) < 3:
        return list(points)
    a = np.asarray(points, dtype=float)
    keep = np.zeros(len(a), dtype=bool)
    keep[0] = keep[-1] = True
    stack = [(0, len(a) - 1)]
    while stack:
        i, j = stack.pop()
        if j - i < 2:
            continue
        p, q = a[i], a[j]
        seg = q - p
        n = math.hypot(seg[0], seg[1])
        mid = a[i + 1:j]
        d = np.hypot(mid[:, 0] - p[0], mid[:, 1] - p[1]) if n < 1e-12 else np.abs(seg[0] * (mid[:, 1] - p[1]) - seg[1] * (mid[:, 0] - p[0])) / n
        k = int(np.argmax(d))
        if d[k] > tol:
            keep[i + 1 + k] = True
            stack += [(i, i + 1 + k), (i + 1 + k, j)]
    return [tuple(x) for x in a[keep]]


def chain(lines):
    """Join lines that share an end point into longer lines (either direction). Lines are lists of (x, y); order inside the result is not kept."""
    pool = {i: list(l) for i, l in enumerate(lines) if len(l) >= 2}
    ends = {}
    for i, l in pool.items():
        ends.setdefault(l[0], set()).add(i)
        ends.setdefault(l[-1], set()).add(i)

    def take(i):
        l = pool.pop(i)
        ends[l[0]].discard(i)
        ends[l[-1]].discard(i)
        return l

    out = []
    while pool:
        c = take(next(iter(pool)))
        grown = True
        while grown:
            grown = False
            for at_end in (True, False):
                pt = c[-1] if at_end else c[0]
                hits = ends.get(pt)
                if not hits:
                    continue
                l = take(next(iter(hits)))
                if at_end:
                    c += l[1:] if l[0] == pt else l[::-1][1:]
                else:
                    c = (l[:-1] if l[-1] == pt else l[::-1][:-1]) + c
                grown = True
        out.append(c)
    return out


def _area(ring) -> float:
    """Shoelace area of a ring in square degrees (enough to rank lakes inside one box)."""
    s = 0.0
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        s += x1 * y2 - x2 * y1
    return abs(s) / 2


GRID = 20000                # the shapes' points are whole numbers on a GRID x GRID lattice over the box (2 to 5 m at a trip's scale), stored as steps from
                            # the point before: about a third of the bytes of plain coordinates, and the app sends JSON uncompressed


def encode(pts, box):
    """[x0, y0, dx1, dy1, ...] for a line of (lon, lat): x east from the box's west edge, y south from its north edge, in GRID steps."""
    w, s, e, n = box
    out, px, py = [], 0, 0
    for lon, lat in pts:
        x, y = round((lon - w) / (e - w) * GRID), round((n - lat) / (n - s) * GRID)
        out += [x - px, y - py]
        px, py = x, y
    return out


def decode(d, box):
    """The (lon, lat) points of an encoded line."""
    w, s, e, n = box
    out, x, y = [], 0, 0
    for i in range(0, len(d) - 1, 2):
        x, y = x + d[i], y + d[i + 1]
        out.append((w + x / GRID * (e - w), n - y / GRID * (n - s)))
    return out


# ---- shapes: one Overpass query ---------------------------------------------------------------------------------------

def overpass_query(box, light=False) -> str:
    """Main roads (secondary ones too when the box is small; motorways and trunk roads only when `light`, for a busy box) and state and country lines, cut to
    the box; named lakes and reservoirs whole (a lake cut by the box is a broken ring: Lake Tahoe went missing when it was cut); cities and towns. Overpass is
    told how long it may take and how much memory it may use."""
    w, s, e, n = box
    bb = f"{s:.4f},{w:.4f},{n:.4f},{e:.4f}"
    roads = "motorway|trunk" if light else "motorway|trunk|primary" if max(box_km(box)) > 120 else "motorway|trunk|primary|secondary"
    return (f'[out:json][timeout:{QUERY_TIMEOUT}][maxsize:{QUERY_MAXSIZE}];(way["highway"~"^({roads})$"]({bb});way["boundary"="administrative"]["admin_level"~"^(2|4)$"]({bb}););'
            f'out geom({bb}) qt;(way["natural"="water"]["name"]({bb});relation["natural"="water"]["name"]({bb}););out geom qt;node["place"~"^(city|town)$"]["name"]({bb});out qt;')


def _lines(geometry):
    """An element's geometry as lines of (lon, lat); Overpass leaves a gap (null) where a cut way leaves the box."""
    out, cur = [], []
    for p in geometry or []:
        if p is None:
            if len(cur) >= 2:
                out.append(cur)
            cur = []
        else:
            cur.append((float(p["lon"]), float(p["lat"])))
    if len(cur) >= 2:
        out.append(cur)
    return out


ROAD_RANK = {"motorway": 0, "trunk": 1, "primary": 2, "secondary": 3}


def shapes(data, box) -> dict:
    """What the paper map draws, from Overpass's JSON: roads (chained per ref and name, simplified), the largest named lakes as rings, up to MAX_TOWNS towns
    (cities first, then by population, none crowding another) and the state and country lines. Lines are `encode`d ("d"); towns keep (lat, lon)."""
    w, s, e, n = box
    span = max(e - w, n - s)
    tol = span / 1600
    roads, waters, towns, borders = {}, [], [], []
    for el in data.get("elements", []) if isinstance(data, dict) else []:
        t = el.get("tags") or {}
        kind = el.get("type")
        if kind == "node" and t.get("place") in ("city", "town") and t.get("name") and "lat" in el:
            try:
                pop = int(str(t.get("population", "0")).replace(",", "").split(".")[0] or 0)
            except ValueError:
                pop = 0
            towns.append({"name": t["name"][:40], "lat": round(float(el["lat"]), 4), "lon": round(float(el["lon"]), 4), "city": t["place"] == "city", "pop": pop})
        elif kind == "way" and t.get("highway") in ROAD_RANK:
            ref = (t.get("ref") or "").split(";")[0].strip()[:16]
            name = (t.get("name") or "").strip()[:48]
            if ref or name:
                roads.setdefault((ref, name, t["highway"]), []).extend(_lines(el.get("geometry")))
        elif kind == "way" and t.get("natural") == "water":
            for l in _lines(el.get("geometry")):
                if len(l) >= 4 and l[0] == l[-1]:
                    waters.append((t.get("name", "")[:48], l))
        elif kind == "relation" and t.get("natural") == "water":
            outer = [l for m in el.get("members") or [] if m.get("type") == "way" and m.get("role", "outer") in ("outer", "") for l in _lines(m.get("geometry"))]
            for ring in chain(outer):
                if len(ring) >= 4 and ring[0] == ring[-1]:
                    waters.append((t.get("name", "")[:48], ring))
        elif kind == "way" and t.get("boundary") == "administrative" and t.get("maritime") != "yes":
            borders.extend(_lines(el.get("geometry")))

    out_roads = []
    for factor in (1, 2, 4, 8):
        out_roads = []
        for (ref, name, cls), lines in sorted(roads.items(), key=lambda kv: ROAD_RANK[kv[0][2]]):
            for c in chain(lines):
                c = simplify(c, tol * factor)
                if len(c) >= 2 and math.hypot(c[0][0] - c[-1][0], c[0][1] - c[-1][1]) > span * 0.012:
                    out_roads.append({**({"ref": ref} if ref else {}), **({"name": name} if name else {}), "d": encode(c, box)})      # (no empty keys: many short roads)
        if sum(len(r["d"]) for r in out_roads) <= MAX_ROAD_POINTS * 2:
            break

    least = (e - w) * (n - s) * 0.0008       # a lake of a few km² in a 50 by 80 km box (Fallen Leaf Lake) is kept
    lakes = sorted(((_area(r), nm, r) for nm, r in waters), key=lambda x: -x[0])
    out_lakes = [{"name": nm, "d": encode(simplify(r, tol * 0.8), box)} for a, nm, r in lakes if a >= least][:MAX_LAKES]

    kept = []
    for t in sorted(towns, key=lambda t: (not t["city"], -t["pop"], t["name"])):
        if all(abs(t["lon"] - k["lon"]) > (e - w) * 0.07 or abs(t["lat"] - k["lat"]) > (n - s) * 0.04 for k in kept):
            kept.append(t)
        if len(kept) == MAX_TOWNS:
            break
    out_borders = [encode(simplify(c, tol * 1.5), box) for c in chain(borders)]
    return {"v": VERSION, "box": list(box), "km": [round(x, 2) for x in box_km(box)], "grid": GRID, "roads": out_roads, "lakes": out_lakes,
            "towns": [{k: t[k] for k in ("name", "lat", "lon", "city")} for t in kept], "borders": [b for b in out_borders if len(b) >= 4]}


def fetch_shapes(box, deadline=None, light=False) -> dict:
    """The shapes for a box from one Overpass query (through TRANSPORT and its gate). An answer with a "remark" (Overpass timed out or ran out of room, so
    its elements are partial) or with no road, lake and town at all is a PackError, never shapes."""
    body = _call(OVERPASS_GATE, OVERPASS, data=urlencode({"data": overpass_query(box, light)}).encode(), deadline=deadline)
    try:
        data = json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as e:
        raise PackError("unreadable") from e
    if not isinstance(data, dict) or not isinstance(data.get("elements", []), list):
        raise PackError("unreadable")
    if data.get("remark"):
        raise PackError("remark")
    try:
        got = shapes(data, box)
    except (ValueError, KeyError, TypeError) as e:
        raise PackError("unreadable") from e
    if not (got["roads"] or got["lakes"] or got["towns"]):
        raise PackError("empty")
    return got


# ---- elevation: AWS Terrain Tiles -----------------------------------------------------------------------------------

def tile_xy(lon, lat, z):
    """The fractional slippy-map tile (x, y) of a point at zoom `z`."""
    x = (lon + 180) / 360 * 2 ** z
    y = (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * 2 ** z
    return x, y


def tiles_for(box, z):
    """(tx0, ty0, tx1, ty1): the tiles covering the box at zoom z, inclusive."""
    w, s, e, n = box
    x0, y0 = tile_xy(w, n, z)
    x1, y1 = tile_xy(e, s, z)
    return int(x0), int(y0), int(x1), int(y1)


def pick_zoom(box) -> int:
    """The highest zoom up to 12 whose tiles over the box are no more than MAX_TILES."""
    for z in range(12, 3, -1):
        tx0, ty0, tx1, ty1 = tiles_for(box, z)
        if (tx1 - tx0 + 1) * (ty1 - ty0 + 1) <= MAX_TILES:
            return z
    return 3


def terrarium(png: bytes) -> np.ndarray:
    """Metres above sea level for each pixel of a terrarium tile: R * 256 + G + B / 256 - 32768. Only a 256 x 256 PNG is decoded (the header is read first)."""
    try:
        img = Image.open(io.BytesIO(png), formats=("PNG",))
    except Exception as e:
        raise PackError("tile", "not a PNG") from e
    if img.size != (256, 256):
        raise PackError("tile", "size")
    try:
        a = np.asarray(img.convert("RGB"), dtype=np.float32)
    except Exception as e:
        raise PackError("tile", "unreadable") from e
    return a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768


def fetch_dem(box, z, deadline=None):
    """(mosaic of metres, tx0, ty0) for the box at zoom z, one tile at a time through TRANSPORT and its gate. Raises PackError."""
    tx0, ty0, tx1, ty1 = tiles_for(box, z)
    mos = np.zeros(((ty1 - ty0 + 1) * 256, (tx1 - tx0 + 1) * 256), dtype=np.float32)
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            mos[(ty - ty0) * 256:(ty - ty0 + 1) * 256, (tx - tx0) * 256:(tx - tx0 + 1) * 256] = terrarium(_call(TILE_GATE, TILES.format(z=z, x=tx, y=ty), deadline=deadline))
    return mos, tx0, ty0


# ---- the relief -----------------------------------------------------------------------------------------------------

PALETTES = {
    # gen_relief.py's: low ground, the forest band, snow, the shade and the lift on sunny slopes, and the sea (the map's lake colour)
    "light": {"low": (226, 224, 218), "mid": (196, 205, 196), "snow": (250, 251, 253), "shade": (92, 96, 112), "lift": (255, 255, 255), "sea": (156, 195, 234)},
    "dark": {"low": (34, 34, 38), "mid": (30, 38, 34), "snow": (74, 78, 88), "shade": (0, 0, 0), "lift": (120, 126, 140), "sea": (23, 58, 96)},
}


def snow_line(lat, month) -> float:
    """Metres above which the relief is drawn white: low in a mid-latitude winter, only the highest peaks in summer, none near the equator."""
    winter = month in (12, 1, 2, 3) if lat >= 0 else month in (6, 7, 8, 9)
    shoulder = month in (11, 4) if lat >= 0 else month in (5, 10)
    if abs(lat) < 23:
        return 4600.0
    return 2050.0 if winter else 2700.0 if shoulder else 3700.0


def relief_size(box, z=None) -> tuple:
    """(width, height) in pixels: true to ground distance, its long side as big as the elevation at zoom `z` needs (UPSAMPLE pixels for each of its own),
    between MIN_SIDE and LONG_SIDE. A small box is drawn smaller: more pixels than the elevation has are only blur and memory."""
    kw, kh = box_km(box)
    z = pick_zoom(box) if z is None else z
    metres_per_px = 156543.03 * math.cos(math.radians((box[1] + box[3]) / 2)) / 2 ** z
    side = int(min(LONG_SIDE, max(min(MIN_SIDE, LONG_SIDE), max(kw, kh) * 1000 / metres_per_px * UPSAMPLE)))
    return (side, max(1, round(side * kh / kw))) if kw >= kh else (max(1, round(side * kw / kh)), side)


def _blur(zz):
    """A 3 x 3 box blur, as two 3-tap passes (two temporaries, not nine)."""
    p = np.pad(zz, 1, mode="edge")
    v = p[:-2] + p[1:-1] + p[2:]
    del p
    out = v[:, :-2] + v[:, 1:-1] + v[:, 2:]
    del v
    out /= 9
    return out


def render(mos, z, tx0, ty0, box, month) -> dict:
    """{"light": WebP bytes, "dark": WebP bytes}: the elevation sampled on an even lon/lat grid (so it lines up with the map's projection), smoothed twice,
    lit from the north-west 40 degrees up; ground coloured by height (low, the forest band between the 10th and 60th percentile, snow above the snow line),
    the sea where it is below zero. Lakes are left to the map, which draws them over it. Works in float32 a plane at a time (no H x W x 3 float images), so a
    2048 px relief stays near 150 MB at its peak."""
    w, s, e, n = box
    W, H = relief_size(box, z)
    lons = w + (np.arange(W, dtype=np.float64) + .5) / W * (e - w)
    lats = n - (np.arange(H, dtype=np.float64) + .5) / H * (n - s)
    px = ((lons + 180) / 360 * 2 ** z - tx0) * 256
    py = ((1 - np.log(np.tan(np.radians(lats)) + 1 / np.cos(np.radians(lats))) / np.pi) / 2 * 2 ** z - ty0) * 256
    ix = np.clip(px.astype(int), 0, mos.shape[1] - 2)
    iy = np.clip(py.astype(int), 0, mos.shape[0] - 2)
    fx = (px - ix).astype(np.float32)[None, :]
    fy = (py - iy).astype(np.float32)[:, None]
    zz = mos[iy][:, ix] * ((1 - fx) * (1 - fy))
    zz += mos[iy][:, ix + 1] * (fx * (1 - fy))
    zz += mos[iy + 1][:, ix] * ((1 - fx) * fy)
    zz += mos[iy + 1][:, ix + 1] * (fx * fy)
    for _ in range(2):  # a light 3x3 smoothing, twice: softer, toy-like relief
        zz = _blur(zz)
    sea = zz <= 0.5
    cell = np.float32(box_km(box)[0] / W * 1000)  # metres per pixel
    gx = np.gradient(zz, axis=1)
    gx /= cell
    gy = np.gradient(zz, axis=0)
    gy /= cell
    az, alt = np.radians(315), np.radians(40)
    slope = np.hypot(gx, gy)
    slope *= 1.25
    np.arctan(slope, out=slope)
    aspect = np.arctan2(-gx, gy)
    del gx, gy
    aspect -= np.float32(az)
    np.cos(aspect, out=aspect)                      # cos(aspect - az), which equals cos(az - aspect)
    shade = np.sin(slope)
    shade *= aspect
    shade *= np.float32(np.cos(alt))
    np.cos(slope, out=slope)
    slope *= np.float32(np.sin(alt))
    shade += slope
    del slope, aspect
    np.clip(shade, 0, 1, out=shade)
    land = zz[~sea]
    lo, hi = (float(np.percentile(land, 10)), float(np.percentile(land, 60))) if land.size else (0.0, 1.0)
    del land
    t_mid = np.clip((zz - lo) / max(hi - lo, 50.0), 0, 1).astype(np.float32)
    t_snow = np.clip((zz - snow_line((s + n) / 2, month)) / 450, 0, 1).astype(np.float32)
    del zz
    shade -= 0.62                                   # flat ground is about 0.64: leave it, darken the shaded side, lift the sunny side a little
    dark_amt = np.clip(shade * -1.25, 0, 0.55).astype(np.float32)
    lift_amt = np.clip(shade * 0.9, 0, 0.25).astype(np.float32)
    del shade
    out = {}
    for name, p in PALETTES.items():
        rgb = np.empty((H, W, 3), dtype=np.uint8)
        for c in range(3):
            ch = (1 - t_mid) * p["low"][c]
            ch += t_mid * p["mid"][c]
            ch *= 1 - t_snow
            ch += t_snow * p["snow"][c]
            ch *= 1 - dark_amt
            ch += dark_amt * p["shade"][c]
            ch *= 1 - lift_amt
            ch += lift_amt * p["lift"][c]
            ch[sea] = p["sea"][c]
            np.clip(ch, 0, 255, out=ch)
            rgb[..., c] = ch
            del ch
        buf = io.BytesIO()
        Image.fromarray(rgb, mode="RGB").save(buf, "WEBP", quality=QUALITY, method=4)
        out[name] = buf.getvalue()
        del rgb
    return out


# ---- a pack ---------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Pack:
    key: str          # names this build; it is in the addresses the page loads, so a browser may keep them for good
    box: tuple
    shapes: dict
    light: bytes
    dark: bytes

    @property
    def size(self) -> int:
        return len(json.dumps(self.shapes, separators=(",", ":"))) + len(self.light) + len(self.dark)


def build(box, month=1, deadline=None) -> Pack:
    """Fetch and draw the pack for a box (blocking: seconds of network and about a second of drawing; the worker runs it). Every call shares one deadline
    (DEADLINE seconds). A busy box whose answer timed out or was too big is asked again with the main roads only. Raises PackError."""
    deadline = _clock() + DEADLINE if deadline is None else deadline
    try:
        data = fetch_shapes(box, deadline)
    except PackError as e:
        if e.why not in ("remark", "size"):
            raise
        data = fetch_shapes(box, deadline, light=True)
    z = pick_zoom(box)
    mos, tx0, ty0 = fetch_dem(box, z, deadline)
    images = render(mos, z, tx0, ty0, box, month)
    del mos
    blob = json.dumps(data, separators=(",", ":"), sort_keys=True).encode()
    key = hashlib.sha256(blob + images["light"] + images["dark"] + f"{VERSION}".encode()).hexdigest()[:16]
    return Pack(key, tuple(box), data, images["light"], images["dark"])


def region_key(box, month) -> str:
    """What makes two trips' packs the same: the version, the box and the season (the snow line its month draws)."""
    return f"v{VERSION}|{box_key(box)}|{snow_line((box[1] + box[3]) / 2, month):.0f}"


# ---- shared by region (the community database) ------------------------------------------------------------------------

_ready_shared: set = set()


@contextmanager
def _shared():
    with community.connect() as db:
        url = community._url()
        if url not in _ready_shared:
            db.conn.execute(text("CREATE TABLE IF NOT EXISTS geo_regions (region TEXT PRIMARY KEY, key TEXT NOT NULL, version INTEGER NOT NULL, box TEXT NOT NULL, "
                                 "shapes TEXT NOT NULL, light BLOB NOT NULL, dark BLOB NOT NULL, size INTEGER NOT NULL DEFAULT 0, built_at TEXT NOT NULL)"))
            db.conn.execute(text("CREATE TABLE IF NOT EXISTS geo_pack_days (day TEXT PRIMARY KEY, builds INTEGER NOT NULL DEFAULT 0)"))
            db.conn.commit()
            _ready_shared.add(url)
        yield db


def shared(region):
    """The pack built for a region (key, box, shapes, light, dark, size, version), or None."""
    with _shared() as db:
        r = db.conn.execute(text("SELECT * FROM geo_regions WHERE region = :r"), {"r": region}).mappings().first()
        return dict(r) if r else None


def _put_shared(region, pack: Pack):
    with _shared() as db:
        db.conn.execute(text("INSERT OR IGNORE INTO geo_regions (region, key, version, box, shapes, light, dark, size, built_at) VALUES (:r, :k, :v, :b, :s, :l, :d, :z, :at)"),
                        {"r": region, "k": pack.key, "v": VERSION, "b": box_key(pack.box), "s": json.dumps(pack.shapes, separators=(",", ":")), "l": pack.light,
                         "d": pack.dark, "z": pack.size, "at": familydb.now()})
        db.conn.commit()


def _take_global() -> bool:
    """Count one build against today's DAILY_CAP for the whole server; False when it is used up."""
    day = _now().date().isoformat()
    with _shared() as db:
        db.conn.execute(text("INSERT OR IGNORE INTO geo_pack_days (day, builds) VALUES (:d, 0)"), {"d": day})
        took = db.conn.execute(text("UPDATE geo_pack_days SET builds = builds + 1 WHERE day = :d AND builds < :cap"), {"d": day, "cap": DAILY_CAP}).rowcount
        db.conn.commit()
        return bool(took)


def clear() -> None:
    """Remove every shared pack and day count. For tests."""
    with _shared() as db:
        db.conn.execute(text("DELETE FROM geo_regions"))
        db.conn.execute(text("DELETE FROM geo_pack_days"))
        db.conn.commit()


# ---- the trip's link and attempts (the family database) ---------------------------------------------------------------

_COLS = "trip_id, region, key, version, box, built_at, day, attempts, failed_at, error"


def load(db, trip_id):
    """The trip's row (its linked pack and its attempts), or None."""
    return familydb.row(db, f"SELECT {_COLS} FROM geo_packs WHERE trip_id = :t", t=trip_id) if db is not None and trip_id else None


def _write(db, trip_id, **cols) -> bool:
    """Insert or update the trip's row with `cols`, keeping the rest; never for a trip that is gone (a build that ends after its trip was deleted writes nothing)."""
    old = dict(load(db, trip_id) or {})
    row = {"trip_id": trip_id, "region": "", "key": "", "version": 0, "box": "", "built_at": "", "day": "", "attempts": 0, "failed_at": "", "error": "", **old, **cols}
    with familydb.transaction(db):
        n = familydb.run(db, f"INSERT OR REPLACE INTO geo_packs ({_COLS}) SELECT :trip_id, :region, :key, :version, :box, :built_at, :day, :attempts, :failed_at, :error "
                             "WHERE EXISTS (SELECT 1 FROM trips WHERE id = :trip_id)", **{k: row[k] for k in _COLS.split(", ")})
    return bool(n)


def link(db, trip_id, region, key, box) -> bool:
    """Point the trip at the pack built for `region`. False (and nothing written) when the trip is gone."""
    return _write(db, trip_id, region=region, key=key, version=VERSION, box=box_key(box), built_at=familydb.now(), failed_at="", error="")


def _count_attempt(db, trip_id, box):
    today = _now().date().isoformat()
    row = load(db, trip_id)
    attempts = (row["attempts"] if row and row["day"] == today else 0) + 1
    _write(db, trip_id, day=today, attempts=attempts)


def _note_failure(db, trip_id, why):
    _write(db, trip_id, failed_at=_now().isoformat(timespec="seconds"), error=str(why)[:20])


def _within_budget(db, trip_id) -> bool:
    """Has the trip (TRIP_BUDGET) and its family (FAMILY_BUDGET) a build left today?"""
    today = _now().date().isoformat()
    row = load(db, trip_id)
    if row and row["day"] == today and row["attempts"] >= TRIP_BUDGET:
        return False
    used = familydb.row(db, "SELECT COALESCE(SUM(attempts), 0) AS n FROM geo_packs WHERE day = :d", d=today)
    return (used["n"] if used else 0) < FAMILY_BUDGET


def _failed_recently(row) -> bool:
    if not row or not row["failed_at"]:
        return False
    try:
        return _now() - datetime.fromisoformat(row["failed_at"]) < timedelta(seconds=RETRY)
    except ValueError:
        return False


def stored(session):
    """The open trip's pack (key, box, shapes, light, dark, size, version, region), or None while it has none of this VERSION."""
    trip_id = _trip_id(session)       # this session's open trip (never one an earlier call left behind)
    with familydb.using(session) as db:
        row = load(db, trip_id)
    if not row or not row["region"] or row["version"] != VERSION:
        return None
    got = shared(row["region"])
    return got if got and got["key"] == row["key"] else None


def _trip_id(session):
    ses.booking(session)            # resolves the open trip
    return ses.open_trip_id()


# ---- which places, and building -----------------------------------------------------------------------------------------

def trip_points(session):
    """([(lat, lon)], anchor) for the open trip from the map cache only (gitaway.geo; gitaway.tripgeo fills it): every stop of every day except the home airport,
    and the place the days start from most often (the stay) as the anchor, or None when nothing is known yet."""
    from gitaway import tripcal as cal, tripgeo   # here: tripgeo reads the calendar, which reads this family's database
    b = ses.booking(session)
    if not b:
        return [], None
    t = cal.trip("", b)
    home = " ".join(geo.as_place(t.origin).lower().split()) if getattr(t, "origin", "") else ""
    names = [p if isinstance(p, str) else p[0] for day in tripgeo.day_places(session) for p in day]
    names = [x for x in names if " ".join(x.lower().split()) != home]
    found = {}
    with familydb.using(session) as db:
        for x in dict.fromkeys(names):
            got = geo.state(x, db)[0]
            if isinstance(got, tuple):
                found[x] = got
    seen = Counter(x for x in names if x in found)
    anchor = found[seen.most_common(1)[0][0]] if seen else None
    return list(dict.fromkeys(found.values())), anchor


def needed(session):
    """(state, box, month): "none" while no place of the trip is known, "ready" when its pack covers them (or is the very box its places make), else "build"."""
    from gitaway import tripcal as cal
    pts, anchor = trip_points(session)
    box = region(pts, anchor)
    month = cal.trip("", ses.booking(session)).depart.month
    if box is None:
        return "none", None, month
    with familydb.using(session) as db:
        row = load(db, ses.open_trip_id())
    if row and row["region"] and row["version"] == VERSION and row["region"] == region_key(parse_box(row["box"]), month) and shared(row["region"]):
        linked = parse_box(row["box"])
        near = [p for p in pts if km_between(anchor or pts[0], p) <= REACH_KM]
        if tuple(linked) == tuple(box) or covers(linked, near):
            return "ready", linked, month
    return "build", box, month


ASYNC = True        # tests switch it off: the build then runs in the calling thread
_jobs: queue.Queue = queue.Queue(maxsize=QUEUE_MAX)      # bounded: a full queue tells the caller to wait
_worker = None
_BUSY: set = set()
_LOCK = threading.Lock()


@dataclass
class _Job:
    key: tuple
    session: dict
    trip_id: str
    box: tuple
    month: int
    region: str


def _run(job) -> bool:
    """Build (or find) the region's pack and link the trip to it; a failure is written down with the trip. True when the trip has its pack."""
    ok = False
    try:
        got = shared(job.region)                       # (another trip may have built this region while this one waited)
        if got is None:
            pack = build(job.box, job.month)
            _put_shared(job.region, pack)
            got = shared(job.region)
        with familydb.using(job.session) as db:
            if db is not None and got:
                ok = link(db, job.trip_id, job.region, got["key"], job.box)
    except Exception as e:  # a pack never matters enough to raise: the map shows its quiet empty state and the next try waits RETRY seconds
        why = getattr(e, "why", type(e).__name__)
        log.warning("geo pack for a trip could not be built: %s", why)      # content-free: what failed, never where
        try:
            with familydb.using(job.session) as db:
                if db is not None:
                    _note_failure(db, job.trip_id, why)
        except Exception:
            log.exception("could not note a geo pack failure")
    finally:
        with _LOCK:
            _BUSY.discard(job.key)
    return ok


def _work():
    while True:
        job = _jobs.get()
        try:
            _run(job)
        finally:
            _jobs.task_done()


def _start():
    global _worker
    with _LOCK:
        if _worker is None or not _worker.is_alive():
            _worker = threading.Thread(target=_work, daemon=True, name="geo-pack")
            _worker.start()


def ensure(session) -> str:
    """Make sure the open trip has a pack: "ready" (it has one, or one built for its region was linked), "building" (queued or being built), "waiting" (it
    failed less than RETRY seconds ago, a budget is used up, or the queue is full) or "none" (no place of the trip is known yet). Never blocks the caller
    unless ASYNC is off (tests)."""
    state, box, month = needed(session)
    if state != "build":
        return state
    trip_id, rkey = ses.open_trip_id(), region_key(box, month)
    if shared(rkey):                                   # built already for this region (a fork, a second trip there): link, ask nothing
        with familydb.using(session) as db:
            got = shared(rkey)
            return "ready" if got and link(db, trip_id, rkey, got["key"], box) else "waiting"
    key = (session.get("tenant_id"), trip_id)
    with _LOCK:
        if key in _BUSY:
            return "building"
    with familydb.using(session) as db:
        if _failed_recently(load(db, trip_id)) or not _within_budget(db, trip_id):
            return "waiting"
    if ASYNC and _jobs.qsize() >= QUEUE_MAX:
        return "waiting"
    if not _take_global():
        return "waiting"
    with familydb.using(session) as db:
        _count_attempt(db, trip_id, box)
    job = _Job(key, dict(session), trip_id, box, month, rkey)
    with _LOCK:
        _BUSY.add(key)
    if not ASYNC:
        return "ready" if _run(job) else "waiting"
    _start()
    try:
        _jobs.put_nowait(job)
    except queue.Full:                                 # (filled between the check above and here)
        with _LOCK:
            _BUSY.discard(key)
        return "waiting"
    return "building"


def drain(timeout=60.0) -> bool:
    """Wait until no build is queued or running (tests and a clean shutdown). False when `timeout` seconds pass first."""
    stop = _clock() + timeout
    while _clock() < stop:
        with _LOCK:
            idle = not _BUSY
        if idle and _jobs.unfinished_tasks == 0:
            return True
        time.sleep(0.02)
    return False


def forget_failures():
    """Tests: forget what this process has in memory (as a restart would). Failures and attempts are in the database and stay."""
    with _LOCK:
        _BUSY.clear()
