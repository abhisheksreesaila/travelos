"""F-201: the paper map's geo pack. A trip's region (its places near the stay, never the home airport) gets a relief image, light and dark, and the
OpenStreetMap shapes the map draws over it, built once when the places are known and kept with the trip. Built from the Tahoe trip's real data
(tests/tahoe.py) through a stand-in transport: no test reaches the network."""

import io
import json

import pytest
from PIL import Image

from gitaway import familydb, geo, geopack
from tests import tahoe
from tests.test_signin import person, sign_in


@pytest.fixture
def real_data(monkeypatch):
    """Overpass and the terrain tiles answered from the design's Tahoe data; the build runs in the test's own thread."""
    tahoe.CALLS.clear()
    monkeypatch.setattr(geopack, "TRANSPORT", tahoe.pack_transport)
    monkeypatch.setattr(geopack, "LONG_SIDE", 512)      # quick to draw; the real size has its own test
    return tahoe.CALLS


@pytest.fixture
def trip(client, monkeypatch):
    monkeypatch.setattr(geopack, "LONG_SIDE", 512)
    sign_in(client)
    tahoe.seed(client, monkeypatch)
    return client


TAHOE = {k: tahoe.place(k) for k in ("cabin", "rno", "heavenly", "taylor", "zephyr", "emerald", "gondola")}
SFO = geo.AIRPORT_COORDS["SFO"]


# ---- the region --------------------------------------------------------------------------------------------------------

def test_the_region_holds_every_stop_near_the_stay_and_leaves_the_home_airport_out():
    box = geopack.region([*TAHOE.values(), SFO], anchor=TAHOE["cabin"])
    w, s, e, n = box
    for name, (lat, lon) in TAHOE.items():
        assert w < lon < e and s < lat < n, name
    assert not (w < SFO[1] < e and s < SFO[0] < n)
    kw, kh = geopack.box_km(box)
    assert 45 < kw < 60 and 75 < kh < 95           # Reno airport to Emerald Bay: about 29 by 63 km of places, padded (the design's box was 50 by 77)
    for lat, lon in TAHOE.values():                 # every place well inside, so a day's camera on one stop still shows map
        assert min(geopack.km_between((lat, lon), (lat, w)), geopack.km_between((lat, lon), (lat, e)), geopack.km_between((lat, lon), (s, lon)), geopack.km_between((lat, lon), (n, lon))) >= geopack.EDGE_KM
    assert all(round(v * 100) == pytest.approx(v * 100) for v in box)   # rounded out to 0.01 degree, so the same places give the same box


def test_a_single_place_gets_a_box_of_the_smallest_size_around_it():
    box = geopack.region([TAHOE["cabin"]])
    kw, kh = geopack.box_km(box)
    assert geopack.MIN_KM <= kw < geopack.MIN_KM + 3 and geopack.MIN_KM <= kh < geopack.MIN_KM + 3
    assert geopack.region([]) is None


def test_covers_needs_every_place_inside_with_a_margin():
    box = geopack.region(TAHOE.values(), anchor=TAHOE["cabin"])
    assert geopack.covers(box, TAHOE.values())
    assert not geopack.covers(box, [SFO])
    w, s, e, n = box
    assert not geopack.covers(box, [(s + 0.001, (w + e) / 2)])      # on the edge: no room for its label


# ---- lines --------------------------------------------------------------------------------------------------------

def test_simplify_keeps_the_ends_and_the_corners_and_drops_what_is_straight():
    line = [(0, 0), (1, 0.001), (2, 0), (3, 0.001), (4, 0), (4, 1), (4, 2)]
    assert geopack.simplify(line, 0.01) == [(0, 0), (4, 0), (4, 2)]
    assert geopack.simplify(line[:2], 0.01) == line[:2]


def test_chain_joins_ways_that_meet_in_either_direction():
    a, b, c = [(0, 0), (1, 0)], [(2, 0), (1, 0)], [(2, 0), (3, 1)]
    got = geopack.chain([a, b, c, [(9, 9), (9, 8)]])
    lines = sorted(got, key=len)
    assert lines[0] in ([(9, 9), (9, 8)], [(9, 8), (9, 9)])
    assert lines[1] in ([(0, 0), (1, 0), (2, 0), (3, 1)], [(3, 1), (2, 0), (1, 0), (0, 0)])


# ---- shapes from Overpass ------------------------------------------------------------------------------------------

def test_shapes_keep_named_roads_the_big_lakes_the_towns_and_the_state_line():
    box = geopack.region(TAHOE.values(), anchor=TAHOE["cabin"])
    got = geopack.shapes(tahoe.overpass_answer(), box)
    refs = {r.get("ref") for r in got["roads"]}
    assert {"US 50", "CA 89", "I 580"} <= refs
    us50 = [r for r in got["roads"] if r.get("ref") == "US 50"]
    assert us50 and all(r["name"] == "Lake Tahoe Boulevard" for r in us50)
    lakes = [l["name"] for l in got["lakes"]]
    assert lakes[0] == "Lake Tahoe" and "Fallen Leaf Lake" in lakes          # largest first
    towns = [t["name"] for t in got["towns"]]
    assert towns[0] in ("Reno", "Carson City") and "South Lake Tahoe" in towns and len(towns) <= geopack.MAX_TOWNS
    assert got["borders"] and len(got["borders"][0]) >= 2
    assert got["box"] == list(box) and got["v"] == geopack.VERSION and got["grid"] == geopack.GRID
    assert len(json.dumps(got, separators=(",", ":"))) < 30_000         # the app sends JSON uncompressed: the shapes are steps on a grid


def test_a_line_comes_back_from_its_steps_within_a_few_metres():
    box = (-120.16, 38.84, -119.71, 39.59)
    line = [(-119.94831, 38.93586), (-119.9524, 38.9411), (-120.05384, 38.93572)]
    back = geopack.decode(geopack.encode(line, box), box)
    assert len(back) == 3 and all(geopack.km_between((a[1], a[0]), (b[1], b[0])) < 0.005 for a, b in zip(line, back))
    roads = geopack.roads_lonlat(geopack.shapes(tahoe.overpass_answer(), box))
    assert any(r["ref"] == "US 50" and len(r["pts"]) > 2 and isinstance(r["pts"][0][0], float) for r in roads)


def test_the_overpass_query_asks_for_the_box_and_nothing_personal():
    q = geopack.overpass_query((-120.2, 38.84, -119.62, 39.54))
    assert "38.8400,-120.2000,39.5400,-119.6200" in q
    import re
    assert re.search(r'way\["highway"[^;]*;way\["boundary"[^;]*;\);out geom\(38\.8400,-120\.2000,39\.5400,-119\.6200\) qt;', q)     # roads and borders cut to the box
    assert re.search(r'relation\["natural"="water"\]\["name"\]\([^)]*\);\);out geom qt;', q)        # lakes whole: a lake cut by the box is a broken ring (Lake Tahoe went missing)
    assert "secondary" not in geopack.overpass_query((-122.0, 37.0, -118.0, 39.0))       # a big box keeps to the main roads


# ---- elevation and the relief ----------------------------------------------------------------------------------------

def test_terrarium_tiles_decode_to_metres():
    png = tahoe.terrain_tile(11, 341, 780)
    h = geopack.terrarium(png)
    assert h.shape == (256, 256)
    assert 1300 < h.min() < h.max() < 3300           # the Tahoe basin: the Carson Valley up to the peaks


def test_the_relief_is_drawn_light_and_dark_true_to_the_ground_and_small(real_data, monkeypatch):
    monkeypatch.setattr(geopack, "LONG_SIDE", 2048)
    box = geopack.region(TAHOE.values(), anchor=TAHOE["cabin"])
    z = geopack.pick_zoom(box)
    mos, tx0, ty0 = geopack.fetch_dem(box, z)
    out = geopack.render(mos, z, tx0, ty0, box, month=12)
    w, h = geopack.relief_size(box)
    kw, kh = geopack.box_km(box)
    assert max(w, h) == geopack.LONG_SIDE and abs(w / h - kw / kh) < 0.01
    for mode in ("light", "dark"):
        img = Image.open(io.BytesIO(out[mode]))
        assert img.format == "WEBP" and img.size == (w, h)
        assert len(out[mode]) < 150_000, (mode, len(out[mode]))
    import numpy as np
    light = np.asarray(Image.open(io.BytesIO(out["light"])).convert("L")).mean()
    dark = np.asarray(Image.open(io.BytesIO(out["dark"])).convert("L")).mean()
    assert light > 3 * dark          # dark really is dark


def test_snow_lies_above_a_winter_snow_line_and_only_on_high_peaks_in_summer():
    assert geopack.snow_line(39, 12) == 2050 and geopack.snow_line(39, 7) > 3000
    assert geopack.snow_line(-39, 7) == 2050                        # the southern winter
    assert geopack.snow_line(21, 12) > 4000                         # Hawaii: none


def test_the_sea_is_drawn_where_the_ground_is_below_zero():
    import numpy as np
    mos = np.full((256, 256), -20.0, dtype=np.float32)
    mos[:, 128:] = 300.0
    box = (-119.0, 33.0, -118.0, 34.0)
    geopack.LONG_SIDE, long_side = 400, geopack.LONG_SIDE
    tx0, ty0, _, _ = geopack.tiles_for(box, 5)
    try:
        out = geopack.render(mos, 5, tx0, ty0, box, month=6)
    finally:
        geopack.LONG_SIDE = long_side
    img = Image.open(io.BytesIO(out["light"])).convert("RGB")
    sea = geopack.PALETTES["light"]["sea"]
    px = [img.getpixel((x, img.height // 2)) for x in range(img.width)]
    wet = sum(1 for p in px if all(abs(a - b) < 12 for a, b in zip(p, sea)))
    assert 0 < wet < len(px)


# ---- building, politely ---------------------------------------------------------------------------------------------

def test_a_build_asks_overpass_once_and_only_the_tiles_it_needs(real_data):
    box = geopack.region(TAHOE.values(), anchor=TAHOE["cabin"])
    pack = geopack.build(box, month=12)
    overpass = [u for u in real_data if "overpass" in u]
    tiles = [u for u in real_data if "terrarium" in u]
    tx0, ty0, tx1, ty1 = geopack.tiles_for(box, geopack.pick_zoom(box))
    assert len(overpass) == 1 and len(tiles) == (tx1 - tx0 + 1) * (ty1 - ty0 + 1) <= geopack.MAX_TILES
    assert len(pack.key) == 16
    assert pack.key == geopack.build(box, month=12).key            # the same pack has the same name


def test_the_gates_space_out_the_calls(real_data, monkeypatch):
    waits = []
    monkeypatch.setattr(geopack.OVERPASS_GATE, "wait", lambda deadline=None: waits.append("overpass") or True)
    monkeypatch.setattr(geopack.TILE_GATE, "wait", lambda deadline=None: waits.append("tile") or True)
    geopack.build(geopack.region([TAHOE["cabin"]]), month=12)
    assert waits[0] == "overpass" and waits.count("overpass") == 1 and waits.count("tile") == len(real_data) - 1


def test_a_refusal_shuts_the_gate_and_nothing_is_built(monkeypatch):
    class Refused(Exception):
        code = 429

    def refuse(url, data=None, timeout=0):
        raise Refused()
    monkeypatch.setattr(geopack, "TRANSPORT", refuse)
    with pytest.raises(geopack.PackError):
        geopack.build(geopack.region([TAHOE["cabin"]]), month=12)
    assert geopack.OVERPASS_GATE.is_shut()


def test_the_network_is_off_in_tests_unless_a_test_says_otherwise():
    with pytest.raises(OSError):
        geopack.TRANSPORT("https://overpass-api.de/api/interpreter")
    assert geopack.ASYNC is False


# ---- once per trip, kept with it -------------------------------------------------------------------------------------

def test_a_trip_with_places_gets_its_pack_once_and_keeps_it(trip, real_data):
    me = person("ari")
    assert geopack.ensure(me) == "ready"
    first = len(real_data)
    assert first > 1
    row = geopack.stored(me)
    assert row["version"] == geopack.VERSION and row["size"] > len(row["light"]) + len(row["dark"]) > 0
    assert Image.open(io.BytesIO(row["light"])).format == "WEBP" and Image.open(io.BytesIO(row["dark"])).format == "WEBP"
    shapes = json.loads(row["shapes"])
    assert shapes["lakes"][0]["name"] == "Lake Tahoe"
    w, s, e, n = geopack.parse_box(row["box"])
    assert w < TAHOE["emerald"][1] and e > TAHOE["rno"][1] and n > TAHOE["rno"][0]
    assert geopack.ensure(me) == "ready" and len(real_data) == first       # built once: a second visit asks nothing


def test_the_home_airport_never_stretches_the_box(trip, real_data):
    me = person("ari")
    geopack.ensure(me)
    w, s, e, n = geopack.parse_box(geopack.stored(me)["box"])
    assert not (w < SFO[1] < e) and geopack.box_km((w, s, e, n))[0] < 120


def test_a_new_place_outside_the_box_builds_it_again(trip, real_data, monkeypatch):
    me = person("ari")
    geopack.ensure(me)
    old = geopack.stored(me)["key"]
    from gitaway import tripcal as cal
    cal.add_activity(me, day=3, start=15 * 60, end=16 * 60, title="Kirkwood day trip", kind="outdoors")
    with familydb.using(me) as db:      # Kirkwood: 28 km south of the cabin, south of the box the first stops made
        geo._put(db, "place", "kirkwood day trip, south lake tahoe", lat=38.6850, lon=-120.0652, data="Kirkwood")
    assert geopack.needed(me)[0] == "build"
    assert geopack.ensure(me) == "ready" and geopack.stored(me)["key"] != old


def test_a_trip_with_no_known_place_has_no_pack_and_asks_nothing(client, monkeypatch, real_data):
    sign_in(client)
    tahoe.seed(client, monkeypatch, maps=False)
    assert geopack.ensure(person("ari")) == "none" and real_data == []


def test_a_failed_build_stores_nothing_and_waits_before_trying_again(trip, monkeypatch):
    calls = []

    def down(url, data=None, timeout=0):
        calls.append(url)
        raise OSError("offline")
    monkeypatch.setattr(geopack, "TRANSPORT", down)
    me = person("ari")
    assert geopack.ensure(me) == "waiting" and geopack.stored(me) is None
    assert geopack.ensure(me) == "waiting" and len(calls) == 1         # not tried again at once
    geopack.forget_failures()
    monkeypatch.setattr(geopack, "TRANSPORT", tahoe.pack_transport)
    assert geopack.ensure(me) == "ready"


def test_a_build_in_the_background_never_holds_up_the_caller(trip, monkeypatch):
    import threading
    gate = threading.Event()

    def slow(url, data=None, timeout=0):
        gate.wait(5)
        return tahoe.pack_transport(url, data, timeout)
    monkeypatch.setattr(geopack, "TRANSPORT", slow)
    monkeypatch.setattr(geopack, "ASYNC", True)
    me = person("ari")
    assert geopack.ensure(me) == "building"
    assert geopack.ensure(me) == "building"                 # one build per trip at a time
    gate.set()
    for t in [t for t in threading.enumerate() if t.name == "geo-pack"]:
        t.join(10)
    assert geopack.stored(me) is not None


def test_another_familys_pack_is_never_theirs(trip, real_data, client):
    geopack.ensure(person("ari"))
    assert geopack.stored(person("sam")) is None


def test_deleting_the_trip_takes_its_pack(trip, real_data):
    from gitaway import importer, session as ses
    me = person("ari")
    geopack.ensure(me)
    ses.booking(me)
    trip_id = ses.open_trip_id()
    assert importer.delete(me, trip_id)
    with familydb.using(me) as db:
        assert geopack.load(db, trip_id) is None
