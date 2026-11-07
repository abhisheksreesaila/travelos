"""The paper map's geo pack (F-201): for the region a trip happens in, the relief image the cockpit's paper map is printed on (WebP, light and dark) and
the OpenStreetMap shapes drawn over it (main roads, named lakes, towns, state and country lines). Built once, when the trip's places are known, and
kept with the trip in the family database (`geo_packs`, about 120 KB a mode). Ported from docs/design/cockpit/tools/fetch_geo.py and gen_relief.py.

    region(points, anchor)   the box the map covers: the places within REACH_KM of the trip's stay (so not the home airport), padded, MIN_KM a side at least
    build(box, month)        one Overpass call for the shapes and AWS Terrain Tiles (terrarium elevation) drawn into a soft hillshade: snow above a snow line
                             that follows the month and the latitude, the sea where the ground is below zero; returns a Pack (raises on any failure)
    ensure(session)          the open trip's places -> its pack: built in a background thread when none covers them (never on the event loop, never waited for);
                             a failed build is tried again after RETRY seconds
    stored(session)          the open trip's pack row (shapes and the two images), or None

The network is reached only through TRANSPORT (tests replace it; the test fixtures refuse it). Overpass gets one query every 5 seconds for the whole process
and the tile bucket ten a second; a 429 or 403 leaves either alone for ten minutes (gitaway.geo.Gate). What leaves the server: the box's corners (to Overpass)
and tile numbers (to AWS); never a place name, a person or a booking.
"""

import hashlib
import io
import json
import logging
import math
import threading
import time
from collections import Counter
from dataclasses import dataclass
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np
from PIL import Image

from gitaway import familydb, geo, session as ses

log = logging.getLogger(__name__)

VERSION = 2                 # what a pack holds and how it is drawn: a pack of an older version is built again
OVERPASS = "https://overpass-api.de/api/interpreter"
TILES = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
TIMEOUT = 90                # seconds one call may take: Overpass took 30 s for the Tahoe box (6.5 MB) when tried live; the build is in the background
REACH_KM = 160              # a place further than this from the stay is another region: the home airport, a far day trip
MIN_KM = 24                 # the box is at least this wide and this tall
PAD = 0.16                  # of the places' own span, on every side
EDGE_KM = 10                # and every place at least this far inside the edge: a day's camera on one stop near the edge still shows map, not the sheet's edge
MAX_TILES = 30              # elevation tiles per pack: the zoom is the highest that needs no more
LONG_SIDE = 2048            # pixels on the relief's long side (the paper map is 1000 units across: about 1 to 2 pixels a unit)
QUALITY = 78                # WebP quality (method 4: about as small as 6 at half the time): 50-110 KB a mode for the Tahoe basin
RETRY = 1800                # seconds before a failed build is tried again
MAX_ROAD_POINTS = 3200      # all roads together, after simplifying (the shapes stay near 30 KB)
MAX_LAKES = 14
MAX_TOWNS = 10

OVERPASS_GATE = geo.Gate(5.0)   # Overpass asks for light use: one query every 5 s for the whole process (a pack needs one)
TILE_GATE = geo.Gate(0.1)       # the public tile bucket has no stated limit; stay polite

_clock = time.monotonic


def transport(url, data=None, timeout=TIMEOUT) -> bytes:
    """GET `url` (or POST the form `data`) and return the body. Raises on any failure. Tests replace TRANSPORT."""
    req = Request(url, data=data, headers={"User-Agent": geo.USER_AGENT, "Accept": "*/*"})
    with urlopen(req, timeout=timeout) as r:  # noqa: S310 - fixed https hosts above
        return r.read()


TRANSPORT = transport


class PackError(RuntimeError):
    """The pack could not be built (a service refused, a tile failed): nothing is stored and the next visit after RETRY tries again."""


def _call(gate, url, data=None):
    if not gate.wait():
        raise PackError("the service asked us to wait")
    try:
        return TRANSPORT(url, data=data, timeout=TIMEOUT)
    except Exception as e:
        if getattr(e, "code", None) in (429, 403):
            gate.back_off()
        raise PackError(f"{type(e).__name__}") from e


# ---- distances and boxes --------------------------------------------------------------------------------------------

def km_between(a, b) -> float:
    """Great-circle kilometres between two (lat, lon) pairs."""
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371.0 * math.asin(min(1.0, math.sqrt(h)))


def box_km(box) -> tuple:
    """(width, height) of a (west, south, east, north) box in kilometres, at its middle latitude."""
    w, s, e, n = box
    return (e - w) * 111.32 * math.cos(math.radians((s + n) / 2)), (n - s) * 110.57


def region(points, anchor=None):
    """The (west, south, east, north) box the paper map covers, or None with no points. `points` are (lat, lon); `anchor` (the stay) decides what is near:
    anything over REACH_KM from it is left out. The places' span is padded by PAD on each side (at least EDGE_KM), made at least MIN_KM a side, and rounded
    out to 0.01 degree."""
    pts = [(float(a), float(b)) for a, b in points if a is not None and b is not None and -85 < a < 85 and -180 <= b <= 180]
    if not pts:
        return None
    a = anchor or pts[0]
    near = [p for p in pts if km_between(a, p) <= REACH_KM] or [a]
    s, n = min(p[0] for p in near), max(p[0] for p in near)
    w, e = min(p[1] for p in near), max(p[1] for p in near)
    mid = (s + n) / 2
    kx, ky = 111.32 * math.cos(math.radians(mid)), 110.57
    half_w = max((e - w) * kx * (1 + 2 * PAD), (e - w) * kx + 2 * EDGE_KM, MIN_KM) / 2 / kx
    half_h = max((n - s) * ky * (1 + 2 * PAD), (n - s) * ky + 2 * EDGE_KM, MIN_KM) / 2 / ky
    cx, cy = (w + e) / 2, mid
    return (math.floor((cx - half_w) * 100) / 100, math.floor((cy - half_h) * 100) / 100,
            math.ceil((cx + half_w) * 100) / 100, math.ceil((cy + half_h) * 100) / 100)


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


def roads_lonlat(shapes) -> list:
    """The pack's roads as [{"ref", "name", "pts": [(lon, lat), ...]}] (for working out a drive's turns)."""
    if not shapes:
        return []
    box = tuple(shapes["box"])
    return [{"ref": r.get("ref", ""), "name": r.get("name", ""), "pts": decode(r["d"], box)} for r in shapes["roads"]]


# ---- shapes: one Overpass call ---------------------------------------------------------------------------------------

def overpass_query(box) -> str:
    """Main roads (secondary ones too when the box is small) and state and country lines, cut to the box; named lakes and reservoirs whole (a lake cut by the
    box is a broken ring: Lake Tahoe went missing when it was cut); cities and towns."""
    w, s, e, n = box
    bb = f"{s:.4f},{w:.4f},{n:.4f},{e:.4f}"
    roads = "motorway|trunk|primary" if max(box_km(box)) > 120 else "motorway|trunk|primary|secondary"
    return (f'[out:json][timeout:80];(way["highway"~"^({roads})$"]({bb});way["boundary"="administrative"]["admin_level"~"^(2|4)$"]({bb}););out geom({bb}) qt;'
            f'(way["natural"="water"]["name"]({bb});relation["natural"="water"]["name"]({bb}););out geom qt;'
            f'node["place"~"^(city|town)$"]["name"]({bb});out qt;')


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


def fetch_shapes(box) -> dict:
    """The shapes for a box, from one Overpass query (through TRANSPORT and its gate). Raises PackError."""
    body = _call(OVERPASS_GATE, OVERPASS, data=urlencode({"data": overpass_query(box)}).encode())
    try:
        return shapes(json.loads(body.decode("utf-8")), box)
    except (ValueError, KeyError, TypeError) as e:
        raise PackError("Overpass answered something we could not read") from e


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
    """Metres above sea level for each pixel of a terrarium tile: R * 256 + G + B / 256 - 32768."""
    a = np.asarray(Image.open(io.BytesIO(png)).convert("RGB"), dtype=np.float32)
    return a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768


def fetch_dem(box, z):
    """(mosaic of metres, tx0, ty0) for the box at zoom z, one tile at a time through TRANSPORT and its gate. Raises PackError."""
    tx0, ty0, tx1, ty1 = tiles_for(box, z)
    mos = np.zeros(((ty1 - ty0 + 1) * 256, (tx1 - tx0 + 1) * 256), dtype=np.float32)
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            png = _call(TILE_GATE, TILES.format(z=z, x=tx, y=ty))
            try:
                h = terrarium(png)
            except Exception as e:
                raise PackError("an elevation tile could not be read") from e
            if h.shape != (256, 256):
                raise PackError("an elevation tile had the wrong size")
            mos[(ty - ty0) * 256:(ty - ty0 + 1) * 256, (tx - tx0) * 256:(tx - tx0 + 1) * 256] = h
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


def relief_size(box) -> tuple:
    """(width, height) in pixels: true to ground distance, LONG_SIDE on the long side."""
    kw, kh = box_km(box)
    return (LONG_SIDE, max(1, round(LONG_SIDE * kh / kw))) if kw >= kh else (max(1, round(LONG_SIDE * kw / kh)), LONG_SIDE)


def render(mos, z, tx0, ty0, box, month) -> dict:
    """{"light": WebP bytes, "dark": WebP bytes}: the elevation sampled on an even lon/lat grid (so it lines up with the map's projection), smoothed twice,
    lit from the north-west 40 degrees up; ground coloured by height (low, the forest band between the 10th and 60th percentile, snow above the snow line),
    the sea where it is below zero. Lakes are left to the map, which draws them over it."""
    w, s, e, n = box
    W, H = relief_size(box)
    lons = w + (np.arange(W, dtype=np.float64) + .5) / W * (e - w)
    lats = n - (np.arange(H, dtype=np.float64) + .5) / H * (n - s)
    px = ((lons + 180) / 360 * 2 ** z - tx0) * 256
    py = ((1 - np.log(np.tan(np.radians(lats)) + 1 / np.cos(np.radians(lats))) / np.pi) / 2 * 2 ** z - ty0) * 256
    ix = np.clip(px.astype(int), 0, mos.shape[1] - 2)
    iy = np.clip(py.astype(int), 0, mos.shape[0] - 2)
    fx = (px - ix).astype(np.float32)[None, :]
    fy = (py - iy).astype(np.float32)[:, None]
    a, b = mos[iy][:, ix], mos[iy][:, ix + 1]
    c, d = mos[iy + 1][:, ix], mos[iy + 1][:, ix + 1]
    zz = a * (1 - fx) * (1 - fy) + b * fx * (1 - fy) + c * (1 - fx) * fy + d * fx * fy
    del a, b, c, d
    for _ in range(2):  # a light 3x3 smoothing, twice: softer, toy-like relief
        zp = np.pad(zz, 1, mode="edge")
        zz = sum(zp[1 + dy:zp.shape[0] - 1 + dy, 1 + dx:zp.shape[1] - 1 + dx] for dy in (-1, 0, 1) for dx in (-1, 0, 1)) / 9
    sea = zz <= 0.5
    cell = box_km(box)[0] / W * 1000  # metres per pixel
    dzdx = np.gradient(zz, axis=1) / cell
    dzdy = np.gradient(zz, axis=0) / cell
    az, alt = np.radians(315), np.radians(40)
    slope = np.arctan(np.hypot(dzdx, dzdy) * 1.25)
    aspect = np.arctan2(-dzdx, dzdy)
    shade = np.clip(np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect), 0, 1)
    del dzdx, dzdy, slope, aspect
    land = zz[~sea]
    lo, hi = (np.percentile(land, 10), np.percentile(land, 60)) if land.size else (0.0, 1.0)
    t_mid = np.clip((zz - lo) / max(hi - lo, 50.0), 0, 1)[..., None]
    t_snow = np.clip((zz - snow_line((s + n) / 2, month)) / 450, 0, 1)[..., None]
    k = shade[..., None] - 0.62   # flat ground is about 0.64: leave it, darken the shaded side, lift the sunny side a little
    dark_amt = np.clip(-k * 1.25, 0, 0.55)
    lift_amt = np.clip(k * 0.9, 0, 0.25)
    out = {}
    for name, p in PALETTES.items():
        base = np.array(p["low"], np.float32) * (1 - t_mid) + np.array(p["mid"], np.float32) * t_mid
        base = base * (1 - t_snow) + np.array(p["snow"], np.float32) * t_snow
        rgb = base * (1 - dark_amt) + np.array(p["shade"], np.float32) * dark_amt
        rgb = rgb * (1 - lift_amt) + np.array(p["lift"], np.float32) * lift_amt
        rgb[sea] = p["sea"]
        buf = io.BytesIO()
        Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), mode="RGB").save(buf, "WEBP", quality=QUALITY, method=4)
        out[name] = buf.getvalue()
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


def build(box, month=1) -> Pack:
    """Fetch and draw the pack for a box (blocking: seconds of network and about a second of drawing; run it in a thread). Raises PackError."""
    data = fetch_shapes(box)
    z = pick_zoom(box)
    mos, tx0, ty0 = fetch_dem(box, z)
    images = render(mos, z, tx0, ty0, box, month)
    blob = json.dumps(data, separators=(",", ":"), sort_keys=True).encode()
    key = hashlib.sha256(blob + images["light"] + images["dark"] + f"{VERSION}".encode()).hexdigest()[:16]
    return Pack(key, tuple(box), data, images["light"], images["dark"])


# ---- kept with the trip ----------------------------------------------------------------------------------------------

def save(db, trip_id, pack: Pack):
    """Store (or replace) the trip's pack in one short transaction."""
    with familydb.transaction(db):
        familydb.run(db, "INSERT OR REPLACE INTO geo_packs (trip_id, key, version, box, shapes, light, dark, size, built_at) "
                         "VALUES (:t, :k, :v, :b, :s, :l, :d, :z, :at)",
                     t=trip_id, k=pack.key, v=VERSION, b=box_key(pack.box), s=json.dumps(pack.shapes, separators=(",", ":")), l=pack.light, d=pack.dark,
                     z=pack.size, at=familydb.now())


def load(db, trip_id):
    """The trip's stored pack row, or None."""
    return familydb.row(db, "SELECT * FROM geo_packs WHERE trip_id = :t", t=trip_id) if db is not None and trip_id else None


def meta(db, trip_id):
    """The trip's pack without its images (key, version, box), or None: what deciding whether to build needs."""
    return familydb.row(db, "SELECT key, version, box FROM geo_packs WHERE trip_id = :t", t=trip_id) if db is not None and trip_id else None


def stored(session):
    """The open trip's pack row (key, box, shapes JSON, light and dark WebP bytes), or None while there is none. A pack of another VERSION is no pack: its
    shapes are in an older form (the page would break on them), so it waits for its rebuild like a trip with none."""
    trip_id = ses.open_trip_id() or _trip_id(session)
    with familydb.using(session) as db:
        row = load(db, trip_id)
    return row if row and row["version"] == VERSION else None


def _trip_id(session):
    ses.booking(session)            # resolves the open trip
    return ses.open_trip_id()


def parse_box(text):
    return tuple(float(v) for v in str(text).split(","))


# ---- which places, and building in the background --------------------------------------------------------------------

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


ASYNC = True        # tests switch it off: the build then runs in the calling thread
_BUSY = set()
_FAILED = {}        # (family, trip) -> when its last build failed
_LOCK = threading.Lock()


def needed(session):
    """(state, box): "none" while no place of the trip is known, "ready" when the stored pack covers them, else "build" and the box to build."""
    pts, anchor = trip_points(session)
    box = region(pts, anchor)
    if box is None:
        return "none", None
    with familydb.using(session) as db:
        row = meta(db, ses.open_trip_id())
    if row and row["version"] == VERSION and covers(parse_box(row["box"]), [p for p in pts if km_between(anchor or pts[0], p) <= REACH_KM]):
        return "ready", parse_box(row["box"])
    return "build", box


def ensure(session) -> str:
    """Make sure the open trip has a pack: "ready", "building" (started now or already running), "waiting" (the last try failed less than RETRY seconds ago)
    or "none" (no place of the trip is known yet). Never blocks the caller unless ASYNC is off (tests)."""
    state, box = needed(session)
    if state != "build":
        return state
    from gitaway import tripcal as cal
    trip_id = ses.open_trip_id()
    month = cal.trip("", ses.booking(session)).depart.month
    key = (session.get("tenant_id"), trip_id)
    with _LOCK:
        if key in _BUSY:
            return "building"
        if key in _FAILED and _clock() - _FAILED[key] < RETRY:
            return "waiting"
        _BUSY.add(key)
    snapshot = dict(session)

    def run():
        ok = False
        try:
            pack = build(box, month)
            with familydb.using(snapshot) as db:
                if db is not None:
                    save(db, trip_id, pack)
                    ok = True
        except Exception as e:  # a pack never matters enough to raise: the map shows its quiet empty state and the next visit tries again
            cause = e.__cause__
            why = f" ({type(cause).__name__} {getattr(cause, 'code', '') or ''}".rstrip() + ")" if cause else ""
            log.warning("geo pack for a trip could not be built: %s%s", type(e).__name__, why)      # content-free: what failed (PackError (HTTPError 502)), never where
        finally:
            with _LOCK:
                _BUSY.discard(key)
                if ok:
                    _FAILED.pop(key, None)
                else:
                    _FAILED[key] = _clock()
        return ok

    if not ASYNC:
        return "ready" if run() else "waiting"
    threading.Thread(target=run, daemon=True, name="geo-pack").start()
    return "building"


def forget_failures():
    """Tests: let the next ensure() try at once."""
    with _LOCK:
        _FAILED.clear()
