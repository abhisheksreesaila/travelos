"""Bakes the real Lake Tahoe the cover's world stands on (F-206), from the data the trip cockpit fetched once (docs/design/cockpit/tools/fetch_geo.py,
raw responses cached in ~/.cache/cockpit-geo-raw): AWS Terrain Tiles elevation (z11, about 60 m), the lake outlines from OpenStreetMap (Nominatim),
the main roads (Overpass) and the drive routes (OSRM). Nothing is fetched here.

Writes assets/cover/:
  tahoe-hi.bin.gz, tahoe-lo.bin.gz   the ground, 60 m and 120 m: heights in 0.5 m steps above or below the lake, delta-coded, plus the signed
                                     distance to the shore of Lake Tahoe and Fallen Leaf Lake (water draws only where it is negative)
  tahoe-geo.json.gz                  world-space vectors: places, the story's trails (real roads and routes), roads, towns, lake outlines

World space: metres, x east and z south of the pier at the end of Ski Run Boulevard, y up from the surface of Lake Tahoe (1897 m).
The gzip files carry no timestamp (mtime=0), so the same data always bakes to the same bytes, and the same content hash in the world's URLs.

    pixi run python -I cover3d/tools/bake_tahoe.py

Needs Pillow (in pixi.toml) and numpy, which the pixi environment has only because another package pulls it in: pixi.toml does not list it by
name, so if a dependency change ever drops it, `pixi add numpy` before baking.
"""
import gzip
import heapq
import io
import json
import math
import re
import struct
from pathlib import Path

import numpy as np
from PIL import Image

RAW = Path.home() / ".cache" / "cockpit-geo-raw"
REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "assets" / "cover"
COCKPIT_GEO = REPO / "docs" / "design" / "cockpit" / "data" / "geo.js"

W, S, E, N = -120.23, 38.83, -119.78, 39.32          # the world: the whole bowl, Fallen Leaf Lake, Spooner Summit, the north shore
LAKE_LEVEL = 1897.0                                   # Lake Tahoe's surface, metres (the DEM is flat over the water at this height)
FALLEN_LEAF_LEVEL = 1945.0
PIER_SHORE = (38.9526, -119.9446)                     # where Ski Run Boulevard meets the lake (Ski Run Marina); the pier starts at the nearest shore
STEP = 0.5                                            # height quantum, metres
Z = 11

PHI = math.radians(39.0)
M_LAT = 111132.92 - 559.82 * math.cos(2 * PHI) + 1.175 * math.cos(4 * PHI)
M_LON = 111412.84 * math.cos(PHI) - 93.5 * math.cos(3 * PHI)


def cockpit():
    text = COCKPIT_GEO.read_text()
    return json.loads(re.search(r"window\.GEO = (\{.*\});", text, re.S).group(1))


def raw(name):
    return json.loads((RAW / name).read_text())


# ---------------------------------------------------------------- projection
class World:
    def __init__(self, lat0, lon0):
        self.lat0, self.lon0 = lat0, lon0

    def xz(self, lat, lon):
        return ((lon - self.lon0) * M_LON, (self.lat0 - lat) * M_LAT)

    def ll(self, x, z):
        return (self.lat0 - z / M_LAT, self.lon0 + x / M_LON)


# ---------------------------------------------------------------- elevation
def mosaic():
    def tile_xy(lon, lat):
        x = (lon + 180) / 360 * 2 ** Z
        y = (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * 2 ** Z
        return x, y
    x0, y0 = tile_xy(W, N)
    x1, y1 = tile_xy(E, S)
    tx0, ty0, tx1, ty1 = int(x0), int(y0), int(x1), int(y1)
    m = np.zeros(((ty1 - ty0 + 1) * 256, (tx1 - tx0 + 1) * 256), dtype=np.float32)
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            a = np.asarray(Image.open(RAW / f"dem-{Z}-{tx}-{ty}.png").convert("RGB"), dtype=np.float32)
            m[(ty - ty0) * 256:(ty - ty0 + 1) * 256, (tx - tx0) * 256:(tx - tx0 + 1) * 256] = a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768
    return m, tx0, ty0


def sample_dem(m, tx0, ty0, lat, lon):
    px = (lon + 180) / 360 * 2 ** Z
    py = (1 - np.log(np.tan(np.radians(lat)) + 1 / np.cos(np.radians(lat))) / np.pi) / 2 * 2 ** Z
    fx, fy = (px - tx0) * 256 - 0.5, (py - ty0) * 256 - 0.5
    ix, iy = np.floor(fx).astype(int), np.floor(fy).astype(int)
    ax, ay = fx - ix, fy - iy

    def at(dx, dy):
        return m[np.clip(iy + dy, 0, m.shape[0] - 1), np.clip(ix + dx, 0, m.shape[1] - 1)]
    return at(0, 0) * (1 - ax) * (1 - ay) + at(1, 0) * ax * (1 - ay) + at(0, 1) * (1 - ax) * ay + at(1, 1) * ax * ay


# ---------------------------------------------------------------- lakes and distance to their shore
def rings_of(name):
    g = raw(name)[0]["geojson"]
    polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
    return [[(lat, lon) for lon, lat in ring] for poly in polys for ring in poly]


def inside(px, pz, rings):
    """Even-odd test of points against rings (world xz), vectorised over the points."""
    res = np.zeros(px.shape, dtype=bool)
    for ring in rings:
        r = np.asarray(ring)
        x1, z1 = r[:, 0], r[:, 1]
        x2, z2 = np.roll(x1, -1), np.roll(z1, -1)
        for a, b, c, d in zip(x1, z1, x2, z2):
            if b == d:
                continue
            cond = (b > pz) != (d > pz)
            xc = a + (pz - b) * (c - a) / (d - b)
            res ^= cond & (px < xc)
    return res


def dist_to_rings(px, pz, rings, chunk=16000):
    out = np.full(px.size, np.inf, dtype=np.float32)
    fx, fz = px.ravel(), pz.ravel()
    segs = []
    for ring in rings:
        r = np.asarray(ring)
        segs.append(np.column_stack([r[:, 0], r[:, 1], np.roll(r[:, 0], -1), np.roll(r[:, 1], -1)]))
    S_ = np.vstack(segs)
    ax, az, bx, bz = S_.T
    dx, dz = bx - ax, bz - az
    ll = np.maximum(dx * dx + dz * dz, 1e-9)
    for i in range(0, fx.size, chunk):
        X, Zc = fx[i:i + chunk, None], fz[i:i + chunk, None]
        t = np.clip(((X - ax) * dx + (Zc - az) * dz) / ll, 0, 1)
        qx, qz = ax + t * dx - X, az + t * dz - Zc
        out[i:i + chunk] = np.sqrt((qx * qx + qz * qz).min(axis=1))
    return out.reshape(px.shape)


# ---------------------------------------------------------------- encoding
def encode_heights(q):
    """Gradient predictor (left + up - up-left), zig-zag residuals as bytes, 255 escapes to an int16."""
    q = q.astype(np.int32)
    pred = np.zeros_like(q)
    pred[1:, 1:] = q[1:, :-1] + q[:-1, 1:] - q[:-1, :-1]
    pred[0, 1:] = q[0, :-1]
    pred[1:, 0] = q[:-1, 0]
    res = (q - pred).ravel()
    zz = np.where(res >= 0, res * 2, -res * 2 - 1)
    small = zz < 255
    b = np.where(small, zz, 255).astype(np.uint8)
    esc = res[~small].astype("<i2")
    return b.tobytes(), esc.tobytes()


def encode_sdf(d, unit):
    """Signed distance to the shore, metres (negative on the water), as uint8 around 128 in `unit` steps, row-delta coded."""
    v = np.clip(np.round(d / unit) + 128, 0, 255).astype(np.int16)
    delta = np.zeros_like(v)
    delta[:, 0] = v[:, 0]
    delta[:, 1:] = v[:, 1:] - v[:, :-1]
    return (delta & 255).astype(np.uint8).tobytes()


def pack(header, blobs):
    head = json.dumps(header, separators=(",", ":")).encode()
    body = b"GAT1" + struct.pack("<I", len(head)) + head + b"".join(blobs)
    return gzip.compress(body, 9, mtime=0)


# ---------------------------------------------------------------- roads as a graph, for the story's trails
def road_graph(world):
    data = raw("overpass-roads-v2.json")
    nodes, adj, ways = {}, {}, []
    for el in data.get("elements", []):
        geo = el.get("geometry")
        if not geo:
            continue
        pts = [(round(p["lat"], 6), round(p["lon"], 6)) for p in geo]
        if not any(S - 0.02 <= la <= N + 0.02 and W - 0.02 <= lo <= E + 0.02 for la, lo in pts):
            continue
        ref = el.get("tags", {}).get("ref", "").split(";")[0]
        hw = el.get("tags", {}).get("highway", "")
        ways.append((ref, hw, pts))
        for a, b in zip(pts, pts[1:]):
            xa, za = world.xz(*a)
            xb, zb = world.xz(*b)
            d = math.hypot(xb - xa, zb - za)
            adj.setdefault(a, []).append((b, d))
            adj.setdefault(b, []).append((a, d))
            nodes[a], nodes[b] = (xa, za), (xb, zb)
    return nodes, adj, ways


def nearest(nodes, world, lat, lon):
    x, z = world.xz(lat, lon)
    return min(nodes, key=lambda k: (nodes[k][0] - x) ** 2 + (nodes[k][1] - z) ** 2)


def path(nodes, adj, a, b):
    best, prev, pq = {a: 0.0}, {}, [(0.0, a)]
    while pq:
        d, u = heapq.heappop(pq)
        if u == b:
            break
        if d > best.get(u, 1e18):
            continue
        for v, w in adj.get(u, ()):
            nd = d + w
            if nd < best.get(v, 1e18):
                best[v], prev[v] = nd, u
                heapq.heappush(pq, (nd, v))
    out, u = [b], b
    while u != a:
        u = prev[u]
        out.append(u)
    return [nodes[k] for k in reversed(out)]


def simplify(pts, tol):
    """Douglas-Peucker on [(x, z)]."""
    if len(pts) < 3:
        return pts
    a, b = np.array(pts[0]), np.array(pts[-1])
    ab = b - a
    n = float(np.hypot(*ab))
    P = np.array(pts[1:-1])
    d = np.hypot(P[:, 0] - a[0], P[:, 1] - a[1]) if n < 1e-9 else np.abs(ab[0] * (P[:, 1] - a[1]) - ab[1] * (P[:, 0] - a[0])) / n
    i = int(np.argmax(d))
    if d[i] > tol:
        return simplify(pts[: i + 2], tol)[:-1] + simplify(pts[i + 1:], tol)
    return [pts[0], pts[-1]]


def r1(pts):
    return [[round(x, 1), round(z, 1)] for x, z in pts]


def main():
    g = cockpit()
    world0 = World(0, 0)

    # the pier: the shore point of Lake Tahoe nearest the end of Ski Run Boulevard
    tahoe_ll = rings_of("nom-poly-Lake_Tahoe.json")
    outer = tahoe_ll[0]
    # the nearest point on the shore line itself (the outline's vertices can be hundreds of metres apart on a straight shore)
    t0 = World(*PIER_SHORE)
    best, bd, seg = None, 1e18, 0
    for k in range(len(outer)):
        (ax, az), (bx, bz) = t0.xz(*outer[k]), t0.xz(*outer[(k + 1) % len(outer)])
        dx, dz = bx - ax, bz - az
        t = max(0.0, min(1.0, -(ax * dx + az * dz) / max(dx * dx + dz * dz, 1e-9)))
        qx, qz = ax + t * dx, az + t * dz
        if qx * qx + qz * qz < bd:
            bd, best, seg = qx * qx + qz * qz, t0.ll(qx, qz), k
    print(f"pier shore point {math.sqrt(bd):.0f} m from the end of Ski Run Boulevard")
    world = World(*best)
    print(f"origin (pier at the shore) {best[0]:.5f} {best[1]:.5f}")

    tahoe = [[world.xz(la, lo) for la, lo in ring] for ring in tahoe_ll]
    fallen = [[world.xz(la, lo) for la, lo in ring] for ring in rings_of("nom-poly-Fallen_Leaf_Lake__California.json")]
    X0, Z0 = world.xz(N, W)
    X1, Z1 = world.xz(S, E)
    print(f"world x {X0:.0f}..{X1:.0f}  z {Z0:.0f}..{Z1:.0f}  ({(X1 - X0) / 1000:.1f} x {(Z1 - Z0) / 1000:.1f} km)")

    m, tx0, ty0 = mosaic()
    OUT.mkdir(parents=True, exist_ok=True)
    sizes = {}
    for tier, spacing, sdf_spacing in (("hi", 60.0, 30.0), ("lo", 120.0, 60.0)):
        gw, gh = round((X1 - X0) / spacing), round((Z1 - Z0) / spacing)
        xs = X0 + (np.arange(gw) + 0.5) * (X1 - X0) / gw
        zs = Z0 + (np.arange(gh) + 0.5) * (Z1 - Z0) / gh
        XX, ZZ = np.meshgrid(xs, zs)
        LAT, LON = world.ll(XX, ZZ)
        h = sample_dem(m, tx0, ty0, LAT, LON) - LAKE_LEVEL
        # the lakes: carve a floor under the water so the shallows show (a shelf that drops away), and keep a strip of shore above it
        for rings, level in ((tahoe, 0.0), (fallen, FALLEN_LEAF_LEVEL - LAKE_LEVEL)):
            wet = inside(XX, ZZ, rings)
            d = dist_to_rings(XX, ZZ, rings)
            floor = level - np.minimum(1.2 + d * 0.06 + np.maximum(d - 220, 0) * 0.35, 120)
            h = np.where(wet, np.minimum(h, floor), np.where(d < 90, np.maximum(h, level + 0.4 + d * 0.012), h))
        q = np.round(h / STEP).astype(np.int32)
        hb, esc = encode_heights(q)
        # the signed distance to the shore of either lake, on its own finer grid over the lakes' box
        allr = tahoe + fallen
        bx0 = min(min(p[0] for p in r) for r in allr) - 900
        bx1 = max(max(p[0] for p in r) for r in allr) + 900
        bz0 = min(min(p[1] for p in r) for r in allr) - 900
        bz1 = max(max(p[1] for p in r) for r in allr) + 900
        sw, sh = round((bx1 - bx0) / sdf_spacing), round((bz1 - bz0) / sdf_spacing)
        sx = bx0 + (np.arange(sw) + 0.5) * (bx1 - bx0) / sw
        sz = bz0 + (np.arange(sh) + 0.5) * (bz1 - bz0) / sh
        SX, SZ = np.meshgrid(sx, sz)
        dt = dist_to_rings(SX, SZ, tahoe)
        df = dist_to_rings(SX, SZ, fallen)
        wt, wf = inside(SX, SZ, tahoe), inside(SX, SZ, fallen)
        sd = np.minimum(np.where(wt, -dt, dt), np.where(wf, -df, df))
        unit = 4.0 if tier == "hi" else 8.0
        sb = encode_sdf(sd, unit)
        header = {"v": 1, "tier": tier, "lake": LAKE_LEVEL, "step": STEP,
                  "height": {"w": gw, "h": gh, "x0": round(X0, 1), "z0": round(Z0, 1), "x1": round(X1, 1), "z1": round(Z1, 1), "bytes": len(hb), "esc": len(esc) // 2},
                  "sdf": {"w": sw, "h": sh, "x0": round(bx0, 1), "z0": round(bz0, 1), "x1": round(bx1, 1), "z1": round(bz1, 1), "unit": unit, "bytes": len(sb)},
                  "fallenLeaf": FALLEN_LEAF_LEVEL - LAKE_LEVEL}
        blob = pack(header, [hb, esc, sb])
        (OUT / f"tahoe-{tier}.bin.gz").write_bytes(blob)
        sizes[tier] = len(blob)
        print(f"tahoe-{tier}: heights {gw}x{gh} ({spacing:.0f} m), shore {sw}x{sh} ({sdf_spacing:.0f} m), {len(blob) / 1024:.1f} KB  range {h.min():.0f}..{h.max():.0f} m")
        if tier == "hi":
            hi_h = h

    # ---------------------------------------------------------- vectors
    P = {k: v for k, v in g["places"].items()}
    towns = {t["name"]: (t["lat"], t["lon"]) for t in g["towns"]}
    nodes, adj, ways = road_graph(world)

    def at(lat, lon):
        x, z = world.xz(lat, lon)
        return [round(x, 1), round(z, 1)]

    def road(*stops):
        pts = []
        for a, b in zip(stops, stops[1:]):
            seg = path(nodes, adj, nearest(nodes, world, *a), nearest(nodes, world, *b))
            pts += seg if not pts else seg[1:]
        return r1(simplify(pts, 6.0))

    def osrm(name):
        c = raw(name)["routes"][0]["geometry"]["coordinates"]
        return [world.xz(la, lo) for lo, la in c]

    cabin = (P["cabin"]["lat"], P["cabin"]["lon"])
    heavenly = (P["heavenly"]["lat"], P["heavenly"]["lon"])
    emerald = (P["emerald"]["lat"], P["emerald"]["lon"])
    taylor = (P["taylor"]["lat"], P["taylor"]["lon"])
    spooner = (P["spooner"]["lat"], P["spooner"]["lon"])
    zephyr = (P["zephyr"]["lat"], P["zephyr"]["lon"])
    tahoe_city = towns["Tahoe City"]
    kings = towns["Kings Beach"]
    incline = towns["Incline Village"]
    stateline = towns["Stateline"]
    sand = (39.19790, -119.93065)                    # Sand Harbor State Park
    homewood = (39.08560, -120.16070)
    island = (38.95425, -120.10040)                  # Fannette Island
    glenbrook = towns.get("Glenbrook", (39.0882, -119.9393))
    meyers = towns.get("Meyers", (38.8560, -120.0130))
    mt_rose = (39.3130, -119.8870)

    # the route in from Reno airport: the part of the real drive inside the world, ending at the cabin
    route = osrm("osrm-d1.json")
    inside_w = [X0 <= x <= X1 and Z0 <= z <= Z1 for x, z in route]
    k = len(route) - 1
    while k > 0 and inside_w[k - 1]:
        k -= 1
    route_in = r1(simplify(route[k:], 5.0))
    fork = r1(simplify(osrm("osrm-d3.json"), 4.0))            # your trail: the cabin to Taylor Creek's sled hill, 18 min
    # Lena & Sam's five days, all on the real roads: the cabin, Emerald Bay, dinner in Tahoe City, Sand Harbor, then round to Heavenly
    orig = road(cabin, emerald, tahoe_city, kings, incline, sand, glenbrook, zephyr, stateline, heavenly)
    # where the trail turns off the road to each day's place
    days = {"cabin": at(*cabin), "emerald": at(*emerald), "tahoeCity": at(*tahoe_city), "sand": at(*sand), "heavenly": at(*heavenly)}

    # the pier: from the shore point straight out into the lake, along the shore's normal
    a, b = world.xz(*outer[seg]), world.xz(*outer[(seg + 1) % len(outer)])
    tx, tz = b[0] - a[0], b[1] - a[1]
    n = math.hypot(tx, tz)
    nx, nz = -tz / n, tx / n
    if not inside(np.array([nx * 60.0]), np.array([nz * 60.0]), tahoe)[0]:
        nx, nz = -nx, -nz
    pier = {"x": 0.0, "z": 0.0, "dir": [round(nx, 4), round(nz, 4)], "len": 110.0}

    # the next family's cabin, a little west along the shore and up from it
    nxt = (38.94840, -119.95420)

    net = [
        {"who": "Ana & Luis", "forks": 18, "pts": road(nxt, emerald), "end": "see"},
        {"who": "The Kims", "forks": 6, "pts": road(tahoe_city, kings), "end": "food"},
        {"who": "Mia’s ski week", "forks": 41, "pts": road(stateline, (38.9620, -119.9030)), "end": "tix"},
        {"who": "Emerald Bay by kayak", "forks": 12, "pts": r1([world.xz(*p) for p in ((38.9535, -120.1074), (38.9545, -120.1040), island, (38.9560, -120.0960), (38.9578, -120.0905))]), "end": "see"},
        {"who": "Homewood ski day", "forks": 9, "pts": road(tahoe_city, homewood), "end": "tix"},
        {"who": "Spooner sled day", "forks": 3, "pts": road(sand, spooner), "end": "tix"},
        {"who": "Fallen Leaf walk", "forks": 5, "pts": r1([world.xz(*taylor), world.xz(38.9290, -120.0570), world.xz(38.9195, -120.0560), world.xz(38.9100, -120.0545)]), "end": "see"},
        {"who": "Mt Rose drive", "forks": 2, "pts": road(incline, mt_rose), "end": "food"},
    ]

    roads = []
    for ref, hw, pts in ways:
        xz = [world.xz(*p) for p in pts]
        xz = [p for p in xz if X0 - 500 <= p[0] <= X1 + 500 and Z0 - 500 <= p[1] <= Z1 + 500]
        if len(xz) >= 2:
            roads.append({"ref": ref, "kind": hw, "pts": r1(simplify(xz, 8.0))})

    town_list = [("South Lake Tahoe", 2600, 1.0), ("Stateline", 1100, 0.9), ("Meyers", 1300, 0.45), ("Tahoe City", 1200, 0.7), ("Kings Beach", 1300, 0.7),
                 ("Incline Village", 2000, 0.6), ("Glenbrook", 700, 0.3), ("Zephyr Cove", 600, 0.3), ("Homewood", 700, 0.35), ("Truckee", 0, 0)]
    town_out = []
    for name, rad, dens in town_list:
        ll = towns.get(name) or {"Zephyr Cove": zephyr, "Homewood": homewood, "Glenbrook": glenbrook}.get(name)
        if not ll or not rad:
            continue
        town_out.append({"name": name, "at": at(*ll), "r": rad, "d": dens})

    island_xz = at(*island)
    # Heavenly's top: the highest ground within 3 km of where its upper lifts end (the DEM knows it better than a guess)
    hx, hz = world.xz(38.9225, -119.9100)
    gw_, gh_ = hi_h.shape[1], hi_h.shape[0]
    jj, ii = np.mgrid[0:gh_, 0:gw_]
    cx = X0 + (ii + 0.5) * (X1 - X0) / gw_
    cz = Z0 + (jj + 0.5) * (Z1 - Z0) / gh_
    near = np.hypot(cx - hx, cz - hz) < 3000
    k_top = np.argmax(np.where(near, hi_h, -1e9))
    top = [round(float(cx.ravel()[k_top]), 1), round(float(cz.ravel()[k_top]), 1)]
    print(f"Heavenly's top {float(hi_h.ravel()[k_top]) + LAKE_LEVEL:.0f} m at {top}")
    geo = {
        "v": 1, "origin": [round(best[0], 6), round(best[1], 6)], "bounds": [round(X0, 1), round(Z0, 1), round(X1, 1), round(Z1, 1)],
        "places": {"cabin": at(*cabin), "nextCabin": at(*nxt), "heavenly": at(*heavenly), "heavenlyTop": top, "emerald": at(*emerald), "island": island_xz,
                   "tahoeCity": at(*tahoe_city), "sand": at(*sand), "taylor": at(*taylor), "spooner": at(*spooner), "zephyr": at(*zephyr), "stateline": at(*stateline),
                   "kings": at(*kings), "incline": at(*incline), "meyers": at(*meyers), "renoIn": list(route_in[0])},
        "pier": pier, "days": days,
        "trails": {"orig": orig, "fork": fork, "route": route_in, "net": net},
        "roads": roads, "towns": town_out,
        "lakes": {"tahoe": [r1(r) for r in tahoe], "fallen": [r1(r) for r in fallen]},
        "drive": {"fork": {"min": round(raw("osrm-d3.json")["routes"][0]["duration"] / 60), "km": round(raw("osrm-d3.json")["routes"][0]["distance"] / 1000, 1)}},
        "credit": "Elevation: AWS Terrain Tiles (USGS 3DEP and others). Lakes, roads and places: © OpenStreetMap contributors (ODbL). Drives: OSRM.",
    }
    blob = gzip.compress(json.dumps(geo, separators=(",", ":")).encode(), 9, mtime=0)
    (OUT / "tahoe-geo.json.gz").write_bytes(blob)
    sizes["geo"] = len(blob)
    print(f"tahoe-geo: {len(blob) / 1024:.1f} KB; trails orig {len(orig)} pts, fork {len(fork)}, route {len(route_in)}, roads {len(roads)}")
    print("sizes", {k: f"{v / 1024:.1f} KB" for k, v in sizes.items()})


if __name__ == "__main__":
    main()
