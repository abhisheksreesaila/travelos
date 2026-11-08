"""Fetches the real map data the cockpit artboards draw, from free sources only:
places (Nominatim), lake outlines (Nominatim polygons), main roads (Overpass), drive routes and times (OSRM demo
router, which the app already uses), and elevation (AWS Terrain Tiles, terrarium encoding).

Raw responses are cached in ~/.cache/cockpit-geo-raw (fetched once, politely: one request a second).
Writes data/geo.js (window.GEO) and data/dem.js (window.DEM).

    pixi run python -I docs/design/cockpit/tools/fetch_geo.py
"""
import base64, io, json, math, time, urllib.parse, urllib.request
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent.parent
RAW = Path.home() / ".cache" / "cockpit-geo-raw"
RAW.mkdir(parents=True, exist_ok=True)
UA = "GitAway design mockup (github.com/abhisheksreesaila/travelos)"

# The trip's world: Reno airport down to South Lake Tahoe.
BBOX = (-120.20, 38.84, -119.62, 39.54)  # west, south, east, north

PLACES = {  # key: (query, label) — the label is what the artboards print
    "rno": ("Reno-Tahoe International Airport", "Reno airport"),
    "cabin": ("Ski Run Boulevard, South Lake Tahoe", "Cabin"),
    "heavenly": (None, "Heavenly · California Lodge"),  # Nominatim misses it; Overpass: way "Heavenly California Lodge"
    "gondola": ("Heavenly Village, South Lake Tahoe", "Heavenly Village"),
    "taylor": ("Taylor Creek Visitor Center, South Lake Tahoe", "Taylor Creek"),
    "zephyr": ("Zephyr Cove Resort", "Zephyr Cove"),
    "emerald": ("Inspiration Point, Emerald Bay", "Emerald Bay"),
    "spooner": ("Spooner Summit, Nevada", "Spooner Summit"),
    "grocery": (None, "Groceries"),  # Overpass: the supermarket on US 50 between Stateline and Ski Run
}
FALLBACK = {  # used if a query finds nothing (lat, lon)
    "heavenly": (38.93492, -119.94038), "taylor": (38.9357, -120.0544), "emerald": (38.9506, -120.1087),
    "spooner": (39.1053, -119.9150), "grocery": (38.94713, -119.95927), "cabin": (38.9296, -119.9583),
}
TOWNS = ["Reno, Nevada", "Carson City, Nevada", "Minden, Nevada", "Stateline, Nevada", "South Lake Tahoe, California",
         "Tahoe City, California", "Incline Village, Nevada", "Truckee, California", "Kings Beach, California",
         "Meyers, California", "Glenbrook, Nevada"]
LAKES = {"tahoe": "Lake Tahoe", "fallen": "Fallen Leaf Lake, California", "washoe": "Washoe Lake, Nevada",
         "donner": "Donner Lake, California", "marlette": "Marlette Lake, Nevada"}
ROADS = ["US 50", "I 580", "US 395", "SR 431", "SR 28", "CA 89", "SR 207", "CA 28", "CA 267", "I 80", "SR 341", "SR 19"]  # Nevada routes are tagged SR


def get(url, name, binary=False):
    f = RAW / name
    if f.exists():
        data = f.read_bytes()
    else:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
        f.write_bytes(data)
        time.sleep(1.1)
    return data if binary else json.loads(data)


def nominatim(q, polygon=False):
    params = {"q": q, "format": "json", "limit": 1}
    if polygon:
        params.update(polygon_geojson=1, polygon_threshold=0.0004)
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(params)
    name = "nom-" + ("poly-" if polygon else "") + "".join(c if c.isalnum() else "_" for c in q)[:80] + ".json"
    res = get(url, name)
    return res[0] if res else None


def dp(points, tol):
    """Douglas-Peucker on [(x, y)]."""
    if len(points) < 3:
        return points
    a, b = np.array(points[0], dtype=float), np.array(points[-1], dtype=float)
    ab = b - a
    n = float(np.hypot(*ab))
    pts = np.array(points[1:-1], dtype=float)
    if n < 1e-12:  # a closed ring: distance to the shared end point
        d = np.hypot(pts[:, 0] - a[0], pts[:, 1] - a[1])
    else:
        d = np.abs(ab[0] * (pts[:, 1] - a[1]) - ab[1] * (pts[:, 0] - a[0])) / n
    i = int(np.argmax(d))
    if d[i] > tol:
        return dp(points[: i + 2], tol)[:-1] + dp(points[i + 1:], tol)
    return [points[0], points[-1]]


def r5(v):
    return round(v, 5)


def main():
    out = {"bbox": BBOX, "places": {}, "towns": [], "lakes": {}, "roads": [], "routes": {}, "stateline": None,
           "sources": {}}

    # Places
    for key, (q, label) in PLACES.items():
        hit = nominatim(q) if q else None
        if hit and BBOX[0] <= float(hit["lon"]) <= BBOX[2] and BBOX[1] <= float(hit["lat"]) <= BBOX[3]:
            lat, lon = float(hit["lat"]), float(hit["lon"])
            src = "nominatim"
        else:
            lat, lon = FALLBACK[key]
            src = "overpass" if q is None else "fallback"
        out["places"][key] = {"label": label, "lat": r5(lat), "lon": r5(lon), "src": src}
        print(f"place {key:9s} {lat:.5f} {lon:.5f} {src}")
    for q in TOWNS:
        hit = nominatim(q)
        if hit:
            out["towns"].append({"name": q.split(",")[0], "lat": r5(float(hit["lat"])), "lon": r5(float(hit["lon"]))})

    # Lakes (simplified polygons straight from Nominatim)
    for key, q in LAKES.items():
        hit = nominatim(q, polygon=True)
        if not hit or "geojson" not in hit:
            print("lake missing", key)
            continue
        g = hit["geojson"]
        polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"] if g["type"] == "MultiPolygon" else []
        rings = []
        for poly in polys:
            ring = poly[0]
            ring = dp([(x, y) for x, y in ring], 0.0006 if key == "tahoe" else 0.0004)
            rings.append([[r5(x), r5(y)] for x, y in ring])
        out["lakes"][key] = rings
        print(f"lake {key}: {sum(len(r) for r in rings)} pts")

    # Roads (Overpass): main routes in the box, merged per ref, simplified
    w, s, e, n = BBOX
    refs = "|".join(r.replace(" ", " ") for r in ROADS)
    q = f"""[out:json][timeout:90];
way["highway"~"motorway|trunk|primary|secondary"]["ref"~"^({refs})($|;)"]({s},{w},{n},{e});
out geom;"""
    data = get("https://overpass-api.de/api/interpreter?data=" + urllib.parse.quote(q), "overpass-roads-v2.json")
    by_ref = {}
    for el in data.get("elements", []):
        ref = el.get("tags", {}).get("ref", "").split(";")[0]
        if ref not in ROADS or "geometry" not in el:
            continue
        line = [(p["lon"], p["lat"]) for p in el["geometry"]]
        by_ref.setdefault(ref, []).append(line)
    for ref, lines in by_ref.items():
        # chain the ways end to end where they meet, then simplify each chain
        chains = []
        pool = [list(l) for l in lines]
        while pool:
            c = pool.pop()
            grown = True
            while grown:
                grown = False
                for i, l in enumerate(pool):
                    if l[0] == c[-1]:
                        c += l[1:]
                    elif l[-1] == c[0]:
                        c = l[:-1] + c
                    elif l[-1] == c[-1]:
                        c += l[::-1][1:]
                    elif l[0] == c[0]:
                        c = l[::-1][:-1] + c
                    else:
                        continue
                    pool.pop(i)
                    grown = True
                    break
            chains.append(c)
        kept = 0
        for c in chains:
            c = dp(c, 0.0007)
            if len(c) >= 2 and math.hypot(c[0][0] - c[-1][0], c[0][1] - c[-1][1]) > 0.004:
                out["roads"].append({"ref": ref, "pts": [[r5(x), r5(y)] for x, y in c]})
                kept += 1
        print(f"road {ref}: {kept} chains")

    # Drive routes (OSRM demo router; the app caches the same calls in gitaway/geo.py)
    P = out["places"]
    legs = {
        "d1": ["rno", "grocery", "cabin"], "d2": ["cabin", "heavenly"], "d3": ["cabin", "taylor"],
        "d4": ["cabin", "zephyr"], "d5": ["cabin", "heavenly", "emerald", "cabin"], "d6": ["cabin", "gondola"],
        "d8": ["cabin", "rno"], "alt": ["rno", "cabin"],  # alt: the airport to the cabin, with OSRM's alternative
    }
    for key, stops in legs.items():
        coords = ";".join(f"{P[k]['lon']},{P[k]['lat']}" for k in stops)
        alt = "true" if key == "alt" else "false"
        url = f"https://router.project-osrm.org/route/v1/driving/{coords}?overview=full&geometries=geojson&steps=true&alternatives={alt}"
        res = get(url, f"osrm-{key}.json")
        routes = []
        for rt in res.get("routes", [])[:2]:
            line = dp([tuple(p) for p in rt["geometry"]["coordinates"]], 0.00025)
            legs_out = []
            for leg in rt["legs"]:
                steps = []
                for st in leg.get("steps", []):
                    nm = st.get("ref") or st.get("name") or ""
                    if st["distance"] > 800 and nm:
                        steps.append({"road": nm, "km": round(st["distance"] / 1000, 1), "min": round(st["duration"] / 60),
                                      "type": st["maneuver"].get("type"), "mod": st["maneuver"].get("modifier", "")})
                legs_out.append({"min": round(leg["duration"] / 60), "km": round(leg["distance"] / 1000, 1),
                                 "summary": leg.get("summary", ""), "steps": steps})
            routes.append({"min": round(rt["duration"] / 60), "km": round(rt["distance"] / 1000, 1),
                           "pts": [[r5(x), r5(y)] for x, y in line], "legs": legs_out})
        out["routes"][key] = {"stops": stops, "alts": routes}
        print(f"route {key}: " + " | ".join(f"{r['min']} min {r['km']} km ({len(r['pts'])} pts) via {r['legs'][0]['summary']}" for r in routes))

    # California-Nevada line: north along 120°W to the lake's middle, then the oblique line south-east.
    # The oblique line runs from (39.0 N, 120.0 W) to the Colorado River (35.0019 N, 114.6333 W).
    slope = (-114.6333 + 120.0) / (39.0 - 35.0019)
    out["stateline"] = [[-120.0, 39.54], [-120.0, 39.0], [r5(-120.0 + (39.0 - 38.84) * slope), 38.84]]

    out["sources"] = {
        "places": "OpenStreetMap via Nominatim (ODbL)", "lakes": "OpenStreetMap via Nominatim (ODbL)",
        "roads": "OpenStreetMap via Overpass API (ODbL)", "routes": "OSRM demo router on OpenStreetMap data",
        "elevation": "AWS Terrain Tiles (Mapzen terrarium): USGS 3DEP/NED, SRTM and others",
    }
    (HERE / "data" / "geo.js").write_text(
        "/* Real map data for the cockpit artboards, fetched by tools/fetch_geo.py. "
        "© OpenStreetMap contributors (ODbL); routes from OSRM. */\nwindow.GEO = " + json.dumps(out, separators=(",", ":")) + ";\n")
    print("geo.js", (HERE / "data" / "geo.js").stat().st_size, "bytes")

    # Elevation grid (AWS Terrain Tiles, terrarium: h = R*256 + G + B/256 - 32768)
    Z = 11
    def tile_xy(lon, lat):
        x = (lon + 180) / 360 * 2 ** Z
        y = (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * 2 ** Z
        return x, y
    x0, y0 = tile_xy(w, n)
    x1, y1 = tile_xy(e, s)
    tx0, ty0, tx1, ty1 = int(x0), int(y0), int(x1), int(y1)
    mosaic = np.zeros(((ty1 - ty0 + 1) * 256, (tx1 - tx0 + 1) * 256), dtype=np.float32)
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            png = get(f"https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{Z}/{tx}/{ty}.png", f"dem-{Z}-{tx}-{ty}.png", binary=True)
            a = np.asarray(Image.open(io.BytesIO(png)).convert("RGB"), dtype=np.float32)
            h = a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768
            mosaic[(ty - ty0) * 256:(ty - ty0 + 1) * 256, (tx - tx0) * 256:(tx - tx0 + 1) * 256] = h
    # resample to an even lon/lat grid (GW x GH), aspect true to ground distance
    GW = 168
    km_w = (e - w) * 111.32 * math.cos(math.radians((s + n) / 2))
    km_h = (n - s) * 110.57
    GH = round(GW * km_h / km_w)
    grid = np.zeros((GH, GW), dtype=np.float32)
    for j in range(GH):
        lat = n - (j + 0.5) / GH * (n - s)
        for i in range(GW):
            lon = w + (i + 0.5) / GW * (e - w)
            px, py = tile_xy(lon, lat)
            fx, fy = (px - tx0) * 256, (py - ty0) * 256
            # average a 3x3 patch: smooth, toy-like
            ix, iy = int(fx), int(fy)
            patch = mosaic[max(iy - 2, 0):iy + 3, max(ix - 2, 0):ix + 3]
            grid[j, i] = float(patch.mean())
    lo, hi = float(grid.min()), float(grid.max())
    q = np.clip(np.round((grid - lo) / (hi - lo) * 65535), 0, 65535).astype("<u2")
    b64 = base64.b64encode(q.tobytes()).decode()
    (HERE / "data" / "dem.js").write_text(
        "/* Elevation for the cockpit's toy maps: AWS Terrain Tiles (terrarium), resampled by tools/fetch_geo.py. "
        "Row-major, north row first, uint16 scaled to [min, max] metres. */\n"
        f"window.DEM = {{w:{GW},h:{GH},min:{lo:.1f},max:{hi:.1f},km:[{km_w:.2f},{km_h:.2f}],bbox:{list(BBOX)},lake:1897,data:'{b64}'}};\n")
    print(f"dem.js {GW}x{GH} min {lo:.0f} max {hi:.0f} m, {(HERE / 'data' / 'dem.js').stat().st_size} bytes")
    np.save(RAW / "grid.npy", grid)


if __name__ == "__main__":
    main()
