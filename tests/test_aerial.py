"""See it from above (F-284, D-905..D-909): the truth pins read from OpenStreetMap, the card, the routes and the daily count behind Google's imagery.

The pins are read from two recorded real Overpass answers (tests/fixtures/aerial/, scripts/record_aerial_fixture.py, 16 Nov 2026): Hilton Los Angeles Airport and Hyatt Regency Lake Tahoe;
no test reaches the network, and no test needs a Google key."""

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import text

from gitaway import aerial, community, csp, liteapi
from gitaway.pages import aerialview, hotelview, tripmatrix

FIX = Path(__file__).parent / "fixtures" / "aerial"
HOTEL_FIX = Path(__file__).parent / "fixtures" / "liteapi_hotel"
LAX = ("Hilton Los Angeles Airport", 33.9461921, -118.3816538)
TAHOE = ("Hyatt Regency Lake Tahoe", 39.2407285, -119.9426988)


def recorded(name) -> bytes:
    return json.dumps(json.loads((FIX / name).read_text())["data"]).encode()


@pytest.fixture(autouse=True)
def clean():
    aerial._failed.clear()
    with community.connect() as db:
        db.conn.execute(text("DELETE FROM aerial_osm"))
        db.conn.execute(text("DELETE FROM aerial_opens"))
        db.conn.commit()
    yield


class Overpass:
    """A stand-in for the two hosts: `script` is a list of (host answer) per call, in order; a string body is a 200, an int a status, an exception is raised."""
    def __init__(self, *script):
        self.script, self.calls = list(script), []

    def __call__(self, host, q, timeout):
        self.calls.append((host, timeout, q))
        step = self.script.pop(0) if self.script else 503
        if isinstance(step, Exception):
            raise step
        if isinstance(step, int):
            return step, b""
        return 200, step


@pytest.fixture
def overpass(monkeypatch):
    def install(*script):
        f = Overpass(*script)
        monkeypatch.setattr(aerial, "TRANSPORT", f)
        return f
    return install


# ---- the pins, from a recorded real answer -------------------------------------------------------------------------------------

def pins_of(which):
    r = aerial.sample(which)
    return {p["kind"]: (p["title"], p["sub"], p["m"], p["far"], p["by"], p["dist"]) for p in r["pins"]}, r


def test_hilton_lax_has_the_flight_path_the_freeway_and_the_lots_each_with_its_distance():
    pins, r = pins_of("lax")
    assert pins["flight"] == ("Runway 07L/25R", "Nearest terminal 1.2 km · American Eagle Terminal", 717, "11 min", "walk", "720 m")
    assert pins["road"] == ("I 405 · San Diego Freeway", "Freeway: traffic noise", 1209, "19 min", "walk", "1.2 km")
    assert pins["water"][0] == "No beach or shore within 2 km" and pins["water"][2] is None      # an absence is said as what the map holds, not as a verdict
    assert pins["shop"] == ("Ralphs", "Nearest supermarket", 1869, "7 min", "drive", "1.9 km")
    assert pins["food"] == ("7 restaurants together", "32 within 2 km", 1793, "7 min", "drive", "1.8 km")
    assert pins["park"] == ("Sky Center", "15 car parks within 500 m, 4 multi-storey", 92, "1 min", "walk", "90 m")
    assert [h["text"] for h in r["heads"]] == ["Between two flight paths", "15 car parks within 500 m"]
    assert r["heads"][0]["more"] == "Landing planes pass 670 m to one side and 720 m to the other, 1.5 km before the runways"
    assert r["headline"] == "Between two flight paths · 15 car parks within 500 m"


def test_hyatt_tahoe_has_a_beach_a_few_minutes_away_and_no_airport():
    pins, r = pins_of("tahoe")
    assert pins["water"] == ("Ski Beach", "Beach", 344, "5 min", "walk", "340 m")
    assert pins["road"] == ("SR 28 · Tahoe Boulevard", "Main road: through traffic", 669, "10 min", "walk", "670 m")
    assert pins["flight"][0] == "No airport within 2 km" and pins["flight"][2] is None
    assert pins["food"] == ("11 restaurants together", "Tahoe Boulevard · 22 within 2 km", 1246, "19 min", "walk", "1.2 km")
    assert [(h["text"], h["good"]) for h in r["heads"]] == [("Beach 5 min walk", True), ("18 car parks within 500 m", False)]


def test_the_samples_say_they_are_a_saved_copy_and_that_the_sample_hotels_are_made_up():
    r = aerial.sample("lax")
    assert r["sample"] is True and r["name"] == "Hilton Los Angeles Airport" and (r["lat"], r["lon"]) == (LAX[1], LAX[2])
    assert r["source_text"].startswith("Sample: a copy of OpenStreetMap saved on 16 Nov 2026, within 2 km.") and "made up" in r["source_text"]
    assert aerial.sample("nowhere") is None


def test_a_pin_without_a_place_has_no_coordinates_and_one_with_has_both():
    r = aerial.sample("lax")
    water = next(p for p in r["pins"] if p["kind"] == "water")
    assert (water["lat"], water["lon"]) == (None, None)
    flight = next(p for p in r["pins"] if p["kind"] == "flight")
    assert 33.9 < flight["lat"] < 34.0 and -118.5 < flight["lon"] < -118.3


# ---- asking Overpass ----------------------------------------------------------------------------------------------------------

def test_the_first_host_answers_and_the_answer_is_kept_for_the_next_time(overpass):
    f = overpass(recorded("osm-lax.json"))
    got = aerial.pins("lp1b8e6", LAX[1], LAX[2], LAX[0])
    assert got["source"] == "live" and got["headline"] == "Between two flight paths · 15 car parks within 500 m"
    assert got["source_text"].startswith("From OpenStreetMap (overpass-api.de), asked on ") and got["source_text"].endswith(", within 2 km.")
    again = aerial.pins("lp1b8e6", LAX[1], LAX[2], LAX[0])
    assert again["source"] == "kept" and again["pins"] == got["pins"] and len(f.calls) == 1


def test_the_second_host_is_asked_when_the_first_fails_and_each_gets_a_short_deadline(overpass):
    f = overpass(TimeoutError("past the deadline"), recorded("osm-lax.json"))
    got = aerial.pins("lp1b8e6", LAX[1], LAX[2], LAX[0])
    assert [c[0] for c in f.calls] == ["overpass-api.de", "overpass.kumi.systems"] and all(c[1] == aerial.HOST_TIMEOUT for c in f.calls) and aerial.HOST_TIMEOUT <= 10
    assert got["source_text"].startswith("From OpenStreetMap (overpass.kumi.systems)")


def test_a_200_with_a_remark_about_a_timeout_or_no_elements_is_a_failure_and_is_never_kept(overpass):
    half = json.dumps({"elements": [{"type": "node", "id": 1, "lat": 1, "lon": 2, "tags": {}}], "remark": 'runtime error: Query timed out in "query" at line 3'}).encode()
    f = overpass(half, json.dumps({"elements": []}).encode())
    assert aerial.pins("lp1", LAX[1], LAX[2], LAX[0]) is None
    assert len(f.calls) == 2
    with community.connect() as db:
        assert db.conn.execute(text("SELECT COUNT(*) FROM aerial_osm")).scalar() == 0


def test_every_host_failing_is_remembered_so_a_tab_that_keeps_asking_does_not_hammer_overpass(overpass):
    f = overpass(502, OSError("refused"))
    assert aerial.pins("lp1", LAX[1], LAX[2], LAX[0]) is None and len(f.calls) == 2
    assert aerial.pins("lp1", LAX[1], LAX[2], LAX[0]) is None and len(f.calls) == 2      # not asked again within FAIL_WAIT


def test_a_kept_answer_older_than_a_week_is_asked_again_and_when_nobody_answers_the_old_copy_is_shown_as_a_saved_copy(overpass):
    overpass(recorded("osm-lax.json"))
    aerial.pins("lp1b8e6", LAX[1], LAX[2], LAX[0])
    old = (datetime.now(timezone.utc) - timedelta(days=9)).isoformat(timespec="seconds")
    with community.connect() as db:
        db.conn.execute(text("UPDATE aerial_osm SET fetched = :t"), {"t": old})
        db.conn.commit()
    f = overpass(502, 502)
    got = aerial.pins("lp1b8e6", LAX[1], LAX[2], LAX[0])
    assert len(f.calls) == 2 and got["source"] == "saved" and "OpenStreetMap is busy right now, so these are from a copy saved on" in got["source_text"]


def test_a_hotel_whose_coordinates_changed_is_not_served_the_old_answer(overpass):
    f = overpass(recorded("osm-lax.json"), recorded("osm-tahoe.json"))
    aerial.pins("lp1", LAX[1], LAX[2], "A")
    got = aerial.pins("lp1", TAHOE[1], TAHOE[2], "A")
    assert len(f.calls) == 2 and got["pins"][2]["title"] == "Ski Beach"


def test_overpass_is_asked_at_fixed_hosts_only_with_a_generic_user_agent(monkeypatch):
    assert aerial.HOSTS == ("overpass-api.de", "overpass.kumi.systems")
    with pytest.raises(ValueError):
        aerial._http("evil.example", "x", 1)
    ua = aerial.user_agent()
    assert re.fullmatch(r"GitAway/1\.0 https://\S+", ua) and "@" not in ua
    q = aerial.query(33.9461921, -118.3816538)
    assert "around:2000,33.946192,-118.381654" in q and "[timeout:20]" in q


# ---- the count behind Google's imagery ------------------------------------------------------------------------------------------

def test_without_a_google_key_nothing_is_offered_and_nothing_counted(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "")
    assert aerial.offered() is False and aerial.open_google() == ("off", None) and aerial.opens_today() == 0


def test_the_key_is_handed_out_until_the_daily_cap_and_then_it_is_back_tomorrow(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "AIza-test-not-real")
    monkeypatch.setenv("GOOGLE_3D_A_DAY", "3")
    assert [aerial.open_google() for _ in range(5)] == [("ok", "AIza-test-not-real")] * 3 + [("full", None)] * 2
    assert aerial.opens_today() == 3      # the refused opens are not counted


def test_the_cap_defaults_to_a_hundred_and_survives_a_restart_because_the_count_is_in_the_database(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "AIza-test-not-real")
    monkeypatch.delenv("GOOGLE_3D_A_DAY", raising=False)
    assert aerial.cap() == 100
    monkeypatch.setenv("GOOGLE_3D_A_DAY", "2")
    aerial.open_google()
    aerial.open_google()
    community._ready.clear()      # a new process: nothing in memory, only the database
    aerial._failed.clear()
    assert aerial.open_google() == ("full", None)
    with community.connect() as db:
        assert db.conn.execute(text("SELECT n FROM aerial_opens")).scalar() == 2
    monkeypatch.setenv("GOOGLE_3D_A_DAY", "not a number")
    assert aerial.cap() == 100


def test_yesterdays_count_does_not_carry_over(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "AIza-test-not-real")
    monkeypatch.setenv("GOOGLE_3D_A_DAY", "1")
    with community.connect() as db:
        db.conn.execute(text("INSERT INTO aerial_opens (day, n) VALUES ('2020-01-01', 99)"))
        db.conn.commit()
    assert aerial.open_google() == ("ok", "AIza-test-not-real") and aerial.open_google() == ("full", None)
    with community.connect() as db:
        assert db.conn.execute(text("SELECT COUNT(*) FROM aerial_opens")).scalar() == 1


# ---- the card and the routes ---------------------------------------------------------------------------------------------------

def hotel_with(lat=33.9461921, lng=-118.3816538):
    d = json.loads((HOTEL_FIX / "hotel.json").read_text())
    if lat is not None:
        d["data"]["location"] = {"latitude": lat, "longitude": lng}
    return json.dumps(d).encode()


@pytest.fixture
def live(monkeypatch, overpass):
    monkeypatch.setenv("LITEAPI_KEY", "sand_test-key-not-real")
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setattr(liteapi, "_CACHE", {})
    monkeypatch.setattr(liteapi, "TRANSPORT", lambda url, headers, body, timeout: (200, "application/json", hotel_with()))
    return overpass


def test_liteapi_hotel_carries_its_coordinates_from_location_and_none_when_it_gave_none_or_nonsense():
    h = liteapi.read_hotel(json.loads(hotel_with()))
    assert (h.lat, h.lng) == (33.9461921, -118.3816538)
    assert (liteapi.read_hotel(json.loads(hotel_with(None))).lat, liteapi.read_hotel(json.loads(hotel_with(None))).lng) == (None, None)
    for bad in ((0, 0), (91, 10), (10, 181)):
        assert liteapi.read_hotel(json.loads(hotel_with(*bad))).lat is None


def test_the_hotels_fragment_has_the_card_with_a_signed_id_and_no_coordinates(monkeypatch):
    from fasthtml.common import to_xml
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "")
    html = to_xml(hotelview.rich(liteapi.read_hotel(json.loads(hotel_with()))))
    assert "See it from above" in html and "Know this before you book" in html
    assert aerial.NEUTRAL in html      # nothing is kept yet: the card says what it shows, it did not wait on Overpass
    assert re.search(r'data-aerial="lp1b8e6\.[0-9a-f]{24}"', html) and 'data-keyed=""' in html
    assert "33.94" not in html and "-118.38" not in html
    assert "See it from above" not in to_xml(hotelview.rich(liteapi.read_hotel(json.loads(hotel_with(None)))))      # no place, no card


def test_the_card_carries_the_top_heads_up_once_the_pins_are_kept_and_offers_the_other_views_only_with_a_key(live, monkeypatch):
    from fasthtml.common import to_xml
    live(recorded("osm-lax.json"))
    aerial.pins("lp1b8e6", LAX[1], LAX[2], LAX[0])
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "AIza-test-not-real")
    html = to_xml(hotelview.rich(liteapi.read_hotel(json.loads(hotel_with()))))
    assert "Between two flight paths · 15 car parks within 500 m" in html and 'data-keyed="1"' in html


def tok(key):
    return hotelview.token(key)


def test_the_pins_route_reads_the_hotel_place_from_liteapi_and_asks_overpass_for_it(client, live):
    f = live(recorded("osm-lax.json"))
    r = client.get("/plan/matrix/aerial/pins", params={"id": tok("lp1b8e6")})
    j = r.json()
    assert r.status_code == 200 and j["ok"] is True and (j["name"], j["lat"], j["lon"]) == ("Hilton Los Angeles Airport", LAX[1], LAX[2])
    assert j["headline"] == "Between two flight paths · 15 car parks within 500 m" and j["source"] == "live" and j["keyed"] is False
    assert [p["kind"] for p in j["pins"]] == ["flight", "road", "water", "shop", "food", "park"]
    assert "around:2000,33.946192,-118.381654" in f.calls[0][2] and r.headers["cache-control"] == "no-store"


def test_a_made_up_or_unsigned_id_is_nothing_and_asks_nobody(client, live):
    f = live(recorded("osm-lax.json"))
    for bad in ("", "lp1b8e6", "lp1b8e6.000000000000000000000000", "sample-lax", tok("lp1b8e6")[:-1] + ("1" if tok("lp1b8e6")[-1] == "0" else "0")):
        assert client.get("/plan/matrix/aerial/pins", params={"id": bad}).status_code == 404, bad
    assert f.calls == []


def test_the_page_cannot_send_its_own_coordinates(client, live):
    f = live(recorded("osm-lax.json"))
    client.get("/plan/matrix/aerial/pins", params={"id": tok("lp1b8e6"), "lat": "0.5", "lon": "0.5"})
    assert "around:2000,33.946192,-118.381654" in f.calls[0][2]


def test_a_hotel_liteapi_has_no_place_for_has_no_pins(client, monkeypatch):
    monkeypatch.setenv("LITEAPI_KEY", "sand_test-key-not-real")
    monkeypatch.setattr(liteapi, "_CACHE", {})
    monkeypatch.setattr(liteapi, "TRANSPORT", lambda url, headers, body, timeout: (200, "application/json", hotel_with(None)))
    assert client.get("/plan/matrix/aerial/pins", params={"id": tok("lpnoplace")}).status_code == 404


def test_when_overpass_gives_nothing_the_answer_says_so_and_never_draws_made_up_pins(client, live):
    live(502, 502)
    j = client.get("/plan/matrix/aerial/pins", params={"id": tok("lp1b8e6")}).json()
    assert j == {"ok": False, "message": aerialview.NO_PINS, "name": "Hilton Los Angeles Airport", "lat": LAX[1], "lon": LAX[2], "pins": [], "keyed": False}      # the place is known, so the map shows; no pins


def test_the_showcase_answers_a_sample_token_from_the_recording_and_production_refuses_it(client, monkeypatch, overpass):
    f = overpass()
    monkeypatch.setenv("GITAWAY_SHOWCASE", "1")
    j = client.get("/plan/matrix/aerial/pins", params={"id": tok("sample-tahoe")}).json()
    assert j["ok"] and j["name"] == "Hyatt Regency Lake Tahoe" and j["sample"] is True and j["headline"] == "Beach 5 min walk · 18 car parks within 500 m"
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    assert client.get("/plan/matrix/aerial/pins", params={"id": tok("sample-tahoe")}).status_code == 404
    assert f.calls == []      # a recording is never a call


def test_the_open_route_counts_and_hands_over_the_key_and_says_back_tomorrow_past_the_cap(client, monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "AIza-test-not-real")
    monkeypatch.setenv("GOOGLE_3D_A_DAY", "2")
    ask = lambda **kw: client.post("/plan/matrix/aerial/open", data={"id": tok("lp1b8e6"), "view": "photo", **kw})  # noqa: E731
    first, second, third = ask(), ask(view="sat"), ask()
    assert (first.status_code, first.json()) == (200, {"ok": True, "key": "AIza-test-not-real"}) and second.json()["ok"] is True
    assert third.status_code == 429 and third.json()["message"] == "Back tomorrow" and third.json()["full"] is True and "AIza" not in third.text
    assert "no-store" in third.headers["cache-control"] and aerial.opens_today() == 2


def test_the_open_route_without_a_key_is_off_and_a_blind_post_spends_nothing(client, monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "")
    assert client.post("/plan/matrix/aerial/open", data={"id": tok("lp1b8e6"), "view": "photo"}).status_code == 404
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "AIza-test-not-real")
    for data in ({}, {"id": "lp1b8e6", "view": "photo"}, {"id": tok("lp1b8e6"), "view": "map"}, {"id": tok("lp1b8e6"), "view": "../x"}):
        r = client.post("/plan/matrix/aerial/open", data=data)
        assert r.status_code == 400 and "AIza" not in r.text, data
    assert aerial.opens_today() == 0


def test_the_key_is_never_in_a_page(client, monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "AIza-test-not-real")
    monkeypatch.setenv("GITAWAY_SHOWCASE", "1")
    page = client.get("/plan/matrix?to=Lake+Tahoe&home=SFO&d=2026-12-12&r=2026-12-16&a=2&k=7,10&x=2")
    assert "AIza" not in page.text and all("AIza" not in c for c in page.headers.values())
    for path in ("/assets/js/aerial.js", "/assets/css/aerial.css"):
        assert "AIza" not in client.get(path).text


# ---- nothing heavy before the tap, and the policy knows the new hosts ---------------------------------------------------------------

def test_the_matrix_page_loads_our_own_script_and_no_map_library(client):
    page = client.get("/plan/matrix?to=San+Diego&home=SFO&d=2026-12-12&r=2026-12-16&a=2&k=7,10&x=2").text
    assert "/assets/js/aerial.js" in page and "/assets/css/aerial.css" in page
    assert not re.search(r"unpkg|jsdelivr|maplibre|cesium|tile\.googleapis|openfreemap", page, re.I)
    assert tripmatrix.HEAD


def test_the_pinned_library_versions_are_exact_and_the_report_only_policy_lists_their_hosts():
    js = Path(__file__).parent.parent / "assets" / "js" / "aerial.js"
    src = js.read_text()
    assert re.search(r"maplibre: '\d+\.\d+\.\d+'", src) and re.search(r"cesium: '\d+\.\d+\.\d+'", src)
    for host in ("https://unpkg.com", "https://cdn.jsdelivr.net", "https://tiles.openfreemap.org", "https://tile.googleapis.com"):
        assert host in csp.POLICY, host
    assert "blob:" in csp.POLICY.split("worker-src")[1].split(";")[0]
    assert "unpkg.com" in src and "cdn.jsdelivr.net" in src and "tile.googleapis.com" in src


def test_the_sample_card_names_the_recorded_hotel_and_says_sample(monkeypatch):
    from fasthtml.common import to_xml
    monkeypatch.setenv("GITAWAY_SHOWCASE", "1")
    html = to_xml(aerialview.sample_card("Lake Tahoe"))
    assert "Sample view" in html and "Hyatt Regency Lake Tahoe" in html and "Beach 5 min walk · 18 car parks within 500 m" in html and "See it from above" in html
    assert "Hilton Los Angeles Airport" in to_xml(aerialview.sample_card("San Diego"))
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    assert aerialview.sample_card("San Diego") == ""


def test_a_sample_squares_drawer_has_the_sample_card_for_each_of_its_hotels_and_none_off_the_showcase(client, monkeypatch):
    from tests.test_tripmatrix_page import MATRIX
    square = "/plan/matrix/square?" + MATRIX.split("?")[1] + "&lane=sandiego&w=2026-12-12"
    monkeypatch.setenv("GITAWAY_SHOWCASE", "1")
    html = client.get(square).text
    assert html.count('class="av-card"') == 3 and html.count("Sample view") == 3 and "Hilton Los Angeles Airport" in html      # three sample hotels, each opening the recorded real one
    assert len(re.findall(r'data-aerial="sample-lax\.[0-9a-f]{24}"', html)) == 3


def test_the_card_uses_none_of_the_data_names_the_drawers_clicks_read(monkeypatch):
    """assets/js/v2drawer.js treats any button in the drawer with data-hotel, data-room, data-tab, data-fl or data-act as its own: a card named data-hotel hid the hotel it sat in (F-284 browser run)."""
    from fasthtml.common import to_xml
    monkeypatch.setenv("GITAWAY_SHOWCASE", "1")
    html = to_xml(aerialview.sample_card("San Diego"))
    for name in ("data-hotel", "data-room", "data-tab", "data-fl", "data-act", "data-gal-go", "data-show"):
        assert name + "=" not in html, name
