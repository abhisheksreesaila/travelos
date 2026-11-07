"""The founder's Tahoe trip, F-201's test case: Sat Dec 19 to Sat Dec 26 2026, SFO to Reno on United, 2 adults and kids 8 and 11, a cabin near Heavenly
in South Lake Tahoe, a Hertz SUV, ski school, snowshoeing at Taylor Creek and a snowmobile tour at Zephyr Cove. The places, the drive lines and drive
times are real (OpenStreetMap, OSRM) and the elevation is real (AWS Terrain Tiles): they come from the cockpit design's data,
docs/design/cockpit/data/geo.js and dem.js, so nothing here reaches the network.

    seed(client)             import the trip as the signed-in person (the import page's own route), add its plans and fill the map cache through gitaway.geo
    geo_fetch(url)           a stand-in for gitaway.geo.fetch: Nominatim and OSRM answered from the design's data
    pack_transport(url, ...) a stand-in for gitaway.geopack.TRANSPORT: the Overpass query and the terrain tiles answered from the same data
    NOW                      Monday Dec 21 2026, 9:12 AM at the lake (a snow day in the design): 17:12 UTC
"""

import base64
import io
import json
import math
import re
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qs, unquote_plus, urlsplit

import numpy as np
from PIL import Image

DATA = Path(__file__).resolve().parent.parent / "docs" / "design" / "cockpit" / "data"
NOW = datetime(2026, 12, 21, 17, 12, tzinfo=timezone.utc)

TEMPLATE = """```yaml
trip:
  title: Tahoe at Christmas
  destination: South Lake Tahoe
  start: 2026-12-19
  end: 2026-12-26
  booked_on: Expedia
  timezone: America/Los_Angeles

travelers:
  - name: Abhi
  - name: Maya
  - name: Kid 1
    age: 11
  - name: Kid 2
    age: 8

flights:
  - airline: United
    number: UA 5521
    from: SFO
    to: RNO
    depart: 2026-12-19 12:40
    arrive: 2026-12-19 13:47
    confirmation: KQ7821
    seats: 21A, 21B, 21C, 21D
  - airline: United
    number: UA 5522
    from: RNO
    to: SFO
    depart: 2026-12-26 13:30
    arrive: 2026-12-26 14:41
    confirmation: KQ7821

hotel:
  name: Cabin near Heavenly
  address: Ski Run Boulevard, South Lake Tahoe, CA 96150
  check_in: 2026-12-19 16:30
  check_out: 2026-12-26 10:00
  confirmation: "VR4821936"

car:
  company: Hertz
  pickup: RNO, 2026-12-19 14:20
  dropoff: RNO, 2026-12-26 11:45
  confirmation: "H77418215"
  car: Mid-size SUV, AWD
```
"""

# (day, start, end, title, kind): the plans the family made
PLANS = (
    (1, "08:45", "15:00", "Ski school at Heavenly", "outdoors"),
    (1, "18:00", "19:30", "Chili night", "food"),
    (2, "10:00", "12:00", "Snowshoe at Taylor Creek", "outdoors"),
    (2, "12:30", "13:30", "Lunch in town", "food"),
    (3, "11:00", "13:00", "Snowmobile tour at Zephyr Cove", "fun"),
    (4, "08:45", "15:00", "Ski school at Heavenly", "outdoors"),
    (4, "16:00", "17:00", "Emerald Bay sunset", "fun"),
    (5, "11:00", "13:00", "Heavenly Gondola", "fun"),
    (5, "18:00", "19:30", "Christmas Eve dinner", "food"),
    (6, "09:00", "10:00", "Presents", "fun"),
    (6, "13:00", "15:00", "Sledding", "outdoors"),
)

HOTEL = "Cabin near Heavenly, Ski Run Boulevard, South Lake Tahoe, CA 96150"
# what gitaway.tripgeo looks up for each stop -> the design's place key
PLACES = {"rno airport": "rno", HOTEL.lower(): "cabin", "ski school at heavenly, south lake tahoe": "heavenly",
          "snowshoe at taylor creek, south lake tahoe": "taylor", "snowmobile tour at zephyr cove, south lake tahoe": "zephyr",
          "emerald bay sunset, south lake tahoe": "emerald", "heavenly gondola, south lake tahoe": "gondola"}
# a leg between two design places -> (route, which leg of it)
LEGS = {("rno", "cabin"): ("alt", 0), ("cabin", "heavenly"): ("d2", 0), ("cabin", "taylor"): ("d3", 0), ("cabin", "zephyr"): ("d4", 0),
        ("heavenly", "emerald"): ("d5", 1), ("cabin", "gondola"): ("d6", 0), ("cabin", "rno"): ("d8", 0)}
# names OpenStreetMap gives the main roads where the trip drives them (the design's data keeps only the route numbers)
ROAD_NAMES = {"US 50": "Lake Tahoe Boulevard", "CA 89": "Emerald Bay Road"}


def _js(name):
    s = (DATA / name).read_text()
    return s[s.index("=") + 1:s.rindex(";")].strip()


@lru_cache(maxsize=1)
def geo_data() -> dict:
    return json.loads(_js("geo.js"))


@lru_cache(maxsize=1)
def dem():
    """(metres as an array, north row first, and the box): the design's elevation grid."""
    s = _js("dem.js")
    meta = {k: float(v) for k, v in re.findall(r"(w|h|min|max):([\d.]+)", s)}
    raw = np.frombuffer(base64.b64decode(re.search(r"data:'([^']+)'", s).group(1)), dtype="<u2").astype(np.float32)
    grid = meta["min"] + raw.reshape(int(meta["h"]), int(meta["w"])) / 65535 * (meta["max"] - meta["min"])
    return grid, tuple(geo_data()["bbox"])


def place(key):
    p = geo_data()["places"][key]
    return p["lat"], p["lon"]


def _leg_line(route, i):
    """The route's line between its stops i and i+1: OSRM's line is split at the point nearest each stop."""
    r = geo_data()["routes"][route]
    pts = r["alts"][0]["pts"]
    stops = [place(k) for k in r["stops"]]
    cut = [0] + [min(range(len(pts)), key=lambda j: (pts[j][0] - lon) ** 2 + (pts[j][1] - lat) ** 2) for lat, lon in stops[1:-1]] + [len(pts) - 1]
    return pts[cut[i]:cut[i + 1] + 1], r["alts"][0]["legs"][i]["min"]


def geo_fetch(url, timeout=0):
    """gitaway.geo.fetch for the trip: Nominatim knows the trip's places, OSRM knows the drives between them. Anything else is refused, like the network."""
    u = urlsplit(url)
    if "nominatim" in u.netloc:
        q = " ".join(unquote_plus(parse_qs(u.query)["q"][0]).lower().split())
        key = PLACES.get(q)
        if not key:
            return []
        lat, lon = place(key)
        return [{"lat": str(lat), "lon": str(lon), "display_name": geo_data()["places"][key]["label"]}]
    if "osrm" in u.netloc:
        (lon1, lat1), (lon2, lat2) = [tuple(map(float, p.split(","))) for p in u.path.rsplit("/", 1)[1].split(";")]
        near = lambda lat, lon: min(geo_data()["places"], key=lambda k: (place(k)[0] - lat) ** 2 + (place(k)[1] - lon) ** 2)  # noqa: E731
        a, b = near(lat1, lon1), near(lat2, lon2)
        if (a, b) not in LEGS:
            raise OSError("no such drive in the fixture")
        line, minutes = _leg_line(*LEGS[(a, b)])
        return {"code": "Ok", "routes": [{"duration": minutes * 60, "geometry": {"type": "LineString", "coordinates": line}}]}
    raise OSError("the network is off in tests")


def overpass_answer() -> dict:
    """What Overpass would say for the Tahoe box: the design's main roads (named where OpenStreetMap names them), its lakes, towns and the state line."""
    g = geo_data()
    els, n = [], 0
    for r in g["roads"]:
        n += 1
        els.append({"type": "way", "id": n, "tags": {"highway": "primary", "ref": r["ref"], **({"name": ROAD_NAMES[r["ref"]]} if r["ref"] in ROAD_NAMES else {})},
                    "geometry": [{"lon": x, "lat": y} for x, y in r["pts"]]})
    names = {"tahoe": "Lake Tahoe", "fallen": "Fallen Leaf Lake", "washoe": "Washoe Lake", "donner": "Donner Lake", "marlette": "Marlette Lake"}
    for key, rings in g["lakes"].items():
        for ring in rings:
            n += 1
            closed = ring if ring[0] == ring[-1] else ring + ring[:1]
            els.append({"type": "way", "id": n, "tags": {"natural": "water", "name": names[key]}, "geometry": [{"lon": x, "lat": y} for x, y in closed]})
    for t in g["towns"]:
        n += 1
        els.append({"type": "node", "id": n, "lat": t["lat"], "lon": t["lon"], "tags": {"place": "city" if t["name"] in ("Reno", "Carson City") else "town", "name": t["name"]}})
    n += 1
    els.append({"type": "way", "id": n, "tags": {"boundary": "administrative", "admin_level": "4"}, "geometry": [{"lon": x, "lat": y} for x, y in g["stateline"]]})
    return {"elements": els}


def terrain_tile(z, x, y) -> bytes:
    """A terrarium PNG for tile z/x/y sampled from the design's elevation grid (outside it: the grid's lowest ground)."""
    grid, (w, s, e, n) = dem()
    h, wd = grid.shape
    i = np.arange(256) + .5
    lon = (x + i / 256) / 2 ** z * 360 - 180
    lat = np.degrees(np.arctan(np.sinh(np.pi * (1 - 2 * (y + i / 256) / 2 ** z))))
    gx = np.clip((lon - w) / (e - w) * wd - .5, 0, wd - 1.001)
    gy = np.clip((n - lat) / (n - s) * h - .5, 0, h - 1.001)
    x0, y0 = gx.astype(int), gy.astype(int)
    fx, fy = (gx - x0)[None, :], (gy - y0)[:, None]
    zz = (grid[y0][:, x0] * (1 - fx) * (1 - fy) + grid[y0][:, x0 + 1] * fx * (1 - fy) + grid[y0 + 1][:, x0] * (1 - fx) * fy + grid[y0 + 1][:, x0 + 1] * fx * fy) + 32768      # bilinear: the grid is coarse
    rgb = np.stack([np.floor(zz / 256), np.floor(zz % 256), np.floor((zz % 1) * 256)], axis=-1).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(rgb, mode="RGB").save(buf, "PNG")
    return buf.getvalue()


CALLS = []      # every URL pack_transport answered, for tests that count them


def pack_transport(url, data=None, timeout=0):
    """gitaway.geopack.TRANSPORT for the trip: the Overpass query and the terrain tiles, from the design's data."""
    CALLS.append(url)
    if "overpass" in url:
        return json.dumps(overpass_answer()).encode()
    m = re.search(r"/terrarium/(\d+)/(\d+)/(\d+)\.png$", url)
    if m:
        return terrain_tile(*map(int, m.groups()))
    raise OSError("the network is off in tests")


def seed(client, monkeypatch, *, plans=True, maps=True):
    """Import the trip for the person `client` is signed in as, add the plans and fill the map cache (Nominatim and OSRM answered by `geo_fetch`)."""
    from gitaway import geo, tripcal as cal, tripgeo
    from gitaway import familydb
    from tests.test_signin import person
    r = client.post("/trips/import/save", data={"text": TEMPLATE}, follow_redirects=False)
    assert r.status_code in (302, 303), r.text[:300]
    me = person("ari")
    if plans:
        for day, s, e, title, kind in PLANS:
            h1, m1 = map(int, s.split(":"))
            h2, m2 = map(int, e.split(":"))
            cal.add_activity(me, day=day, start=h1 * 60 + m1, end=h2 * 60 + m2, title=title, kind=kind)
    if maps:
        monkeypatch.setattr(geo, "fetch", geo_fetch)
        with familydb.using(me) as db:
            for group in tripgeo.day_places(me):
                geo.warm(db, group, budget=30)
    return me


def km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    return 2 * 6371 * math.asin(math.sqrt(math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2))
