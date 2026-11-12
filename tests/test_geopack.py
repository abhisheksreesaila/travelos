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
    roads = geopack.shapes(tahoe.overpass_answer(), box)["roads"]
    assert any(r.get("ref") == "US 50" and len(geopack.decode(r["d"], box)) > 2 for r in roads)


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
    w, h = geopack.relief_size(box, z)
    kw, kh = geopack.box_km(box)
    assert geopack.MIN_SIDE <= max(w, h) <= geopack.LONG_SIDE and abs(w / h - kw / kh) < 0.01
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


def later(monkeypatch, seconds):
    """Move geopack's clock (its UTC now) forward."""
    from datetime import datetime, timedelta, timezone
    then = datetime.now(timezone.utc) + timedelta(seconds=seconds)
    monkeypatch.setattr(geopack, "_now", lambda: then)


def at_noon(monkeypatch, seconds=0):
    """Set geopack's clock to noon UTC today plus some seconds: a daily budget's test must not cross midnight (it ran at 23:33 UTC and failed)."""
    from datetime import datetime, timedelta, timezone
    then = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0) + timedelta(seconds=seconds)
    monkeypatch.setattr(geopack, "_now", lambda: then)


def test_a_failed_build_stores_nothing_and_waits_before_trying_again(trip, monkeypatch):
    calls = []

    def down(url, data=None, timeout=0):
        calls.append(url)
        raise OSError("offline")
    monkeypatch.setattr(geopack, "TRANSPORT", down)
    me = person("ari")
    assert geopack.ensure(me) == "waiting" and geopack.stored(me) is None
    assert geopack.ensure(me) == "waiting" and len(calls) == 1         # not tried again at once
    geopack.forget_failures()                                           # (a restart: nothing in memory)
    assert geopack.ensure(me) == "waiting" and len(calls) == 1         # the failure is kept in the database
    later(monkeypatch, geopack.RETRY + 5)
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
    assert geopack.drain(20)
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


# ---- review fixes (F-201 review): a failure is never a pack; budgets, one build at a time, caps, shared packs -------------------------------

def overpass_says(answer):
    """A transport whose Overpass answer is `answer` (a dict or a callable taking the query), tiles from the Tahoe data."""
    asked = []

    def fake(url, data=None, timeout=0):
        if "overpass" in url:
            from urllib.parse import parse_qs
            query = parse_qs(data.decode())["data"][0]
            asked.append(query)
            got = answer(query) if callable(answer) else answer
            return json.dumps(got).encode()
        return tahoe.pack_transport(url, data, timeout)
    return fake, asked


TIMED_OUT = {"elements": [{"type": "node", "id": 1, "lat": 39.0, "lon": -120.0, "tags": {"place": "town", "name": "Half"}}],
             "remark": "runtime error: Query timed out in \"query\" at line 1 after 61 seconds."}


def test_an_overpass_answer_that_timed_out_is_a_failure_not_a_pack(trip, monkeypatch):
    fake, asked = overpass_says(TIMED_OUT)
    monkeypatch.setattr(geopack, "TRANSPORT", fake)
    me = person("ari")
    assert geopack.ensure(me) == "waiting" and geopack.stored(me) is None
    assert len(asked) == 2 and "motorway|trunk)$" in asked[1] and "primary" not in asked[1]       # asked once more with the main roads only
    with familydb.using(me) as db:
        row = geopack.load(db, ses_trip(me))
    assert row["failed_at"] and row["error"] == "remark" and row["attempts"] == 1
    assert geopack.ensure(me) == "waiting" and len(asked) == 2                                    # not again until RETRY
    later(monkeypatch, geopack.RETRY + 5)
    monkeypatch.setattr(geopack, "TRANSPORT", tahoe.pack_transport)
    assert geopack.ensure(me) == "ready" and geopack.stored(me)["shapes"]


def test_an_empty_overpass_answer_is_a_failure(trip, monkeypatch):
    fake, asked = overpass_says({"elements": []})
    monkeypatch.setattr(geopack, "TRANSPORT", fake)
    with pytest.raises(geopack.PackError) as e:
        geopack.build(geopack.region([TAHOE["cabin"]]), month=12)
    assert e.value.why == "empty"


def test_a_busy_box_falls_back_to_the_main_roads(trip, monkeypatch):
    fake, asked = overpass_says(lambda q: TIMED_OUT if "secondary" in q or "primary" in q else tahoe.overpass_answer())
    monkeypatch.setattr(geopack, "TRANSPORT", fake)
    pack = geopack.build(geopack.region(TAHOE.values(), anchor=TAHOE["cabin"]), month=12)
    assert pack.shapes["roads"] and len(asked) == 2 and "[maxsize:67108864]" in asked[0] and "[timeout:" in asked[0]


def test_reads_are_capped_and_a_too_big_answer_fails_cleanly(monkeypatch):
    class Resp:
        def __init__(self, length, body):
            self.headers, self.body = {"Content-Length": length} if length else {}, body
        def read(self, n=-1):
            chunk, self.body = self.body[:n], self.body[n:]
            return chunk
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    class Opener:
        def __init__(self, resp):
            self.resp = resp
        def open(self, req, timeout=0):
            return self.resp
    monkeypatch.setattr(geopack, "_OPENER", Opener(Resp(str(geopack.OVERPASS_CAP + 1), b"")))
    with pytest.raises(geopack.PackError) as e:
        geopack.transport(geopack.OVERPASS, data=b"x")
    assert e.value.why == "size"
    monkeypatch.setattr(geopack, "_OPENER", Opener(Resp("", b"x" * (geopack.TILE_CAP + 10))))      # no length given: read stops past the cap
    with pytest.raises(geopack.PackError):
        geopack.transport(geopack.TILES.format(z=11, x=1, y=1))
    monkeypatch.setattr(geopack, "_OPENER", Opener(Resp("3", b"abc")))
    assert geopack.transport(geopack.TILES.format(z=11, x=1, y=1)) == b"abc"


def test_the_transport_refuses_a_redirect():
    import http.server
    import threading

    class Redirect(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(302)
            self.send_header("Location", "http://127.0.0.1:1/elsewhere")
            self.end_headers()

        def log_message(self, *a):
            pass
    srv = http.server.HTTPServer(("127.0.0.1", 0), Redirect)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        with pytest.raises(geopack.PackError) as e:
            geopack.transport(f"http://127.0.0.1:{srv.server_port}/terrarium/1/1/1.png", timeout=5)
        assert e.value.why == "redirect"
    finally:
        srv.shutdown()


def test_a_build_has_one_deadline_for_all_its_calls(trip, monkeypatch):
    import time
    def slow(url, data=None, timeout=0):
        time.sleep(0.3)
        return tahoe.pack_transport(url, data, timeout)
    monkeypatch.setattr(geopack, "TRANSPORT", slow)
    monkeypatch.setattr(geopack, "DEADLINE", 1.0)
    with pytest.raises(geopack.PackError) as e:
        geopack.build(geopack.region(TAHOE.values(), anchor=TAHOE["cabin"]), month=12)
    assert e.value.why == "time"


def test_a_tile_must_be_a_small_png_before_it_is_decoded():
    import io as _io
    from PIL import Image as _Image
    jpeg = _io.BytesIO()
    _Image.new("RGB", (256, 256)).save(jpeg, "JPEG")
    big = _io.BytesIO()
    _Image.new("RGB", (512, 512)).save(big, "PNG")
    for bad in (jpeg.getvalue(), big.getvalue(), b"not an image"):
        with pytest.raises(geopack.PackError) as e:
            geopack.terrarium(bad)
        assert e.value.why == "tile"


def ses_trip(me):
    from gitaway import session as ses
    ses.booking(me)
    return ses.open_trip_id()


def test_each_trip_has_a_daily_budget_of_builds(trip, monkeypatch):
    monkeypatch.setattr(geopack, "TRIP_BUDGET", 2)
    monkeypatch.setattr(geopack, "TRANSPORT", lambda url, data=None, timeout=0: (_ for _ in ()).throw(OSError("offline")))
    me = person("ari")
    at_noon(monkeypatch)
    for n in range(2):
        assert geopack.ensure(me) == "waiting"
        at_noon(monkeypatch, (n + 1) * (geopack.RETRY + 5))
    calls = []
    monkeypatch.setattr(geopack, "TRANSPORT", lambda url, data=None, timeout=0: calls.append(url) or tahoe.pack_transport(url, data, timeout))
    assert geopack.ensure(me) == "waiting" and calls == []                # the trip has used today's builds
    at_noon(monkeypatch, 2 * 24 * 3600)
    assert geopack.ensure(me) == "ready"                                  # a new day


def test_a_family_and_the_whole_server_have_daily_budgets_too(trip, monkeypatch, client):
    monkeypatch.setattr(geopack, "FAMILY_BUDGET", 1)
    monkeypatch.setattr(geopack, "TRANSPORT", lambda url, data=None, timeout=0: (_ for _ in ()).throw(OSError("offline")))
    me = person("ari")
    at_noon(monkeypatch)
    assert geopack.ensure(me) == "waiting"                  # one build tried and failed
    at_noon(monkeypatch, geopack.RETRY + 5)
    assert geopack.ensure(me) == "waiting"                  # the family's builds for today are used
    with familydb.using(me) as db:
        assert geopack.load(db, ses_trip(me))["attempts"] == 1
    monkeypatch.setattr(geopack, "FAMILY_BUDGET", 30)
    monkeypatch.setattr(geopack, "DAILY_CAP", 1)
    assert geopack.ensure(me) == "waiting"                  # and the server's (one build already counted today)
    with familydb.using(me) as db:
        assert geopack.load(db, ses_trip(me))["attempts"] == 1


def test_one_build_runs_at_a_time_and_the_queue_is_bounded(trip, monkeypatch):
    import threading
    import time
    active, most, release = [0], [0], threading.Event()
    real = geopack.build

    def counted(box, month=1, deadline=None):
        active[0] += 1
        most[0] = max(most[0], active[0])
        release.wait(5)
        time.sleep(0.05)
        try:
            return real(box, month, deadline)
        finally:
            active[0] -= 1
    monkeypatch.setattr(geopack, "build", counted)
    monkeypatch.setattr(geopack, "TRANSPORT", tahoe.pack_transport)
    monkeypatch.setattr(geopack, "ASYNC", True)
    monkeypatch.setattr(geopack, "QUEUE_MAX", 1)
    me = person("ari")
    assert geopack.ensure(me) == "building"
    time.sleep(0.2)                                          # the worker has taken it: the queue is empty again
    other = dict(me, tenant_id="other-family")              # a second family's build waits in the queue (its db is never opened: the build is what is counted)
    monkeypatch.setattr(geopack, "needed", lambda session: ("build", geopack.region([TAHOE["rno"]]), 12))
    monkeypatch.setattr(geopack, "_within_budget", lambda db, trip_id: True)
    monkeypatch.setattr(geopack, "_count_attempt", lambda db, trip_id, box: None)
    assert geopack.ensure(other) == "building"
    third = dict(me, tenant_id="third-family")
    assert geopack.ensure(third) == "waiting"               # the queue is full: try later
    release.set()
    assert geopack.drain(30) and most[0] == 1


def test_a_region_built_once_is_shared_by_every_trip_in_it(trip, monkeypatch, real_data, client):
    """Forks of one trip do not ask Overpass again: a pack is kept by region (the box, the season, the version) in the shared store; nothing personal is in it."""
    me = person("ari")
    assert geopack.ensure(me) == "ready"
    first = len(real_data)
    other = TestClient_for("sam")
    tahoe.seed(other, monkeypatch, who="sam")
    sam = person("sam")
    assert geopack.ensure(sam) == "ready" and len(real_data) == first          # linked, not built again
    assert geopack.stored(sam)["key"] == geopack.stored(me)["key"]


def TestClient_for(who):
    from starlette.testclient import TestClient
    from main import app
    c = TestClient(app, client=("127.0.0.1", 50000))
    sign_in(c, who)
    return c


def test_a_deleted_trips_pack_row_is_never_written_back(trip, real_data):
    from gitaway import importer
    me = person("ari")
    trip_id = ses_trip(me)
    box = geopack.region(TAHOE.values(), anchor=TAHOE["cabin"])
    assert importer.delete(me, trip_id)
    with familydb.using(me) as db:
        assert geopack.link(db, trip_id, "v|box|season", "0123456789abcdef", box) is False      # a build that finishes after the trip is gone writes nothing
        assert geopack.load(db, trip_id) is None


def test_a_trip_across_the_date_line_gets_a_sane_box():
    fiji = [(-17.80, 179.95), (-17.86, -179.97), (-17.70, 179.80)]
    w, s, e, n = geopack.region(fiji, anchor=fiji[0])
    assert -180 <= w < e <= 180 and e - w < 2 and n - s < 2


def test_the_relief_is_as_big_as_its_elevation_needs_and_light_on_memory(real_data, monkeypatch):
    import tracemalloc
    monkeypatch.setattr(geopack, "LONG_SIDE", 2048)
    small = geopack.region([TAHOE["cabin"]])
    big = geopack.region(TAHOE.values(), anchor=TAHOE["cabin"])
    assert max(geopack.relief_size(small, geopack.pick_zoom(small))) < max(geopack.relief_size(big, geopack.pick_zoom(big))) <= 2048
    z = geopack.pick_zoom(big)
    mos, tx0, ty0 = geopack.fetch_dem(big, z)
    tracemalloc.start()
    geopack.render(mos, z, tx0, ty0, big, 12)
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    assert peak < 260 * 1024 * 1024, peak / 1e6
