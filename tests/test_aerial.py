"""See it from above (F-284, D-905..D-909): the truth pins read from OpenStreetMap, the card, the routes and the daily count behind Google's imagery.

The pins are read from two recorded real Overpass answers (tests/fixtures/aerial/, scripts/record_aerial_fixture.py, 16 Nov 2026): Hilton Los Angeles Airport and Hyatt Regency Lake Tahoe;
no test reaches the network, and no test needs a Google key."""

import json
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import text

from gitaway import aerial, community, csp, liteapi
from gitaway.pages import aerialview, hotelview, tripmatrix
from tests.test_signin import sign_in

FIX = Path(__file__).parent / "fixtures" / "aerial"
HOTEL_FIX = Path(__file__).parent / "fixtures" / "liteapi_hotel"
LAX = ("Hilton Los Angeles Airport", 33.9461921, -118.3816538)
TAHOE = ("Hyatt Regency Lake Tahoe", 39.2407285, -119.9426988)


def recorded(name) -> bytes:
    return json.dumps(json.loads((FIX / name).read_text())["data"]).encode()


@pytest.fixture(autouse=True)
def clean():
    aerial._failed.clear()
    aerial._down.clear()
    aerial._inflight.clear()
    aerial.clear()
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
    assert len(f.calls) == len(aerial.HOSTS)
    with community.connect() as db:
        assert db.conn.execute(text("SELECT COUNT(*) FROM aerial_osm")).scalar() == 0


def test_every_host_failing_is_remembered_so_a_tab_that_keeps_asking_does_not_hammer_overpass(overpass):
    f = overpass(502, OSError("refused"))
    assert aerial.pins("lp1", LAX[1], LAX[2], LAX[0]) is None and len(f.calls) == len(aerial.HOSTS)
    assert aerial.pins("lp1", LAX[1], LAX[2], LAX[0]) is None and len(f.calls) == len(aerial.HOSTS)      # not asked again within FAIL_WAIT


def test_a_kept_answer_older_than_a_week_is_asked_again_and_when_nobody_answers_the_old_copy_is_shown_as_a_saved_copy(overpass):
    overpass(recorded("osm-lax.json"))
    aerial.pins("lp1b8e6", LAX[1], LAX[2], LAX[0])
    old = (datetime.now(timezone.utc) - timedelta(days=9)).isoformat(timespec="seconds")
    with community.connect() as db:
        db.conn.execute(text("UPDATE aerial_osm SET fetched = :t"), {"t": old})
        db.conn.commit()
    f = overpass(502, 502)
    got = aerial.pins("lp1b8e6", LAX[1], LAX[2], LAX[0])
    assert len(f.calls) == len(aerial.HOSTS) and got["source"] == "saved" and "OpenStreetMap is busy right now, so these are from a copy saved on" in got["source_text"]


def test_a_hotel_whose_coordinates_changed_is_not_served_the_old_answer(overpass):
    f = overpass(recorded("osm-lax.json"), recorded("osm-tahoe.json"))
    aerial.pins("lp1", LAX[1], LAX[2], "A")
    got = aerial.pins("lp1", TAHOE[1], TAHOE[2], "A")
    assert len(f.calls) == 2 and got["pins"][2]["title"] == "Ski Beach"


def test_overpass_is_asked_at_fixed_hosts_only_with_a_generic_user_agent(monkeypatch):
    assert aerial.HOSTS == ("overpass-api.de", "overpass.kumi.systems", "maps.mail.ru")
    assert aerial.PATHS == {"maps.mail.ru": "/osm/tools/overpass/api/interpreter"}
    with pytest.raises(ValueError):
        aerial._http("evil.example", "x", 1)
    ua = aerial.user_agent()
    assert re.fullmatch(r"GitAway/1\.0 https://\S+", ua) and "@" not in ua
    q = aerial.query(33.9461921, -118.3816538)
    assert "around:2000,33.946192,-118.381654" in q and "[timeout:20]" in q


def test_a_third_mirror_is_asked_at_its_own_path_when_the_first_two_fail(overpass):
    f = overpass(502, TimeoutError("past the deadline"), recorded("osm-lax.json"))
    got = aerial.pins("lp1b8e6", LAX[1], LAX[2], LAX[0])
    assert [c[0] for c in f.calls] == ["overpass-api.de", "overpass.kumi.systems", "maps.mail.ru"]
    assert got["source_text"].startswith("From OpenStreetMap (maps.mail.ru)") and got["headline"] == "Between two flight paths · 15 car parks within 500 m"


def test_each_mirror_is_called_at_its_own_address_and_no_other(monkeypatch):
    seen = []

    def fake_get(conn, target, headers, deadline, cap):
        seen.append((conn.host, target.split("?")[0]))
        return 200, {}, b"{}"
    monkeypatch.setattr(aerial, "get_by_deadline", fake_get)
    monkeypatch.setattr(aerial, "_lookup", lambda host, deadline: ["192.0.2.1"])
    for host in aerial.HOSTS:
        aerial._http(host, "x", 1)
    assert seen == [("overpass-api.de", "/api/interpreter"), ("overpass.kumi.systems", "/api/interpreter"), ("maps.mail.ru", "/osm/tools/overpass/api/interpreter")]
    with pytest.raises(ValueError):
        aerial._http("overpass.private.coffee", "x", 1)      # not a listed host


def test_a_failing_mirror_sits_out_for_a_few_minutes_then_is_asked_again(overpass):
    f = overpass(502, recorded("osm-lax.json"), recorded("osm-tahoe.json"), recorded("osm-lax.json"))
    aerial.pins("lpa", LAX[1], LAX[2], "A")
    assert [c[0] for c in f.calls] == ["overpass-api.de", "overpass.kumi.systems"]
    aerial.pins("lpb", TAHOE[1], TAHOE[2], "B")      # another hotel: the first host is still sitting out
    assert [c[0] for c in f.calls] == ["overpass-api.de", "overpass.kumi.systems", "overpass.kumi.systems"]
    assert 180 <= aerial.MIRROR_WAIT <= 600
    aerial._down["overpass-api.de"] -= aerial.MIRROR_WAIT + 1      # its time is up
    aerial.pins("lpc", LAX[1] + 0.01, LAX[2], "C")
    assert f.calls[-1][0] == "overpass-api.de"


def test_every_mirror_sitting_out_asks_nobody(overpass):
    f = overpass()
    for host in aerial.HOSTS:
        aerial._down[host] = time.monotonic()
    assert aerial.pins("lp1", LAX[1], LAX[2], LAX[0]) is None and f.calls == []


def test_a_background_ask_is_given_longer_than_a_tap_because_nobody_waits_for_it(overpass):
    f = overpass(recorded("osm-lax.json"), recorded("osm-lax.json"))
    aerial.pins("lpt", LAX[1], LAX[2], LAX[0])
    aerial.warm("lpbg", LAX[1] + 0.01, LAX[2], "A")
    aerial.run_pending()
    assert f.calls[0][1] == aerial.HOST_TIMEOUT and f.calls[1][1] == aerial.BACKGROUND_TIMEOUT > aerial.HOST_TIMEOUT


# ---- pins asked when the hotel is shown ----------------------------------------------------------------------------------------

def test_showing_a_hotel_queues_its_pins_and_once_kept_the_card_says_the_heads_up(live, monkeypatch):
    from fasthtml.common import to_xml
    f = live(recorded("osm-lax.json"))
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "")
    first = to_xml(hotelview.fragment("lp1b8e6"))
    assert aerial.NEUTRAL in first and f.calls == []      # drawing the hotel asked nobody: the job waits for a worker
    assert aerial.run_pending() == 1 and len(f.calls) == 1
    assert "Between two flight paths · 15 car parks within 500 m" in to_xml(hotelview.fragment("lp1b8e6"))
    assert aerial.run_pending() == 0 and len(f.calls) == 1      # kept: nothing queued, nothing asked


def test_a_hotel_is_queued_once_while_its_job_is_waiting_and_a_kept_hotel_is_never_queued(live):
    live(recorded("osm-lax.json"))
    assert aerial.warm("lp1b8e6", LAX[1], LAX[2], LAX[0]) is True
    assert aerial.warm("lp1b8e6", LAX[1], LAX[2], LAX[0]) is False      # one in flight per hotel
    assert aerial.run_pending() == 1
    assert aerial.warm("lp1b8e6", LAX[1], LAX[2], LAX[0]) is False      # fresh and kept


def test_a_hotel_that_just_failed_is_not_queued_again_within_the_wait(live):
    f = live(502, 502, 502)
    aerial.warm("lpf", LAX[1], LAX[2], LAX[0])
    aerial.run_pending()
    assert len(f.calls) == len(aerial.HOSTS) and aerial.warm("lpf", LAX[1], LAX[2], LAX[0]) is False


def test_the_background_ask_counts_against_the_person_once_and_the_taps_use_of_it_is_free(client, live, monkeypatch):
    monkeypatch.setattr(aerial, "PINS_PER_PERSON_A_DAY", 1)
    f = live(recorded("osm-lax.json"), recorded("osm-tahoe.json"))
    aerial.warm("lp1b8e6", LAX[1], LAX[2], LAX[0], "visitor-1")
    aerial.run_pending()
    got = client.get("/plan/matrix/aerial/pins", params={"id": tok("lp1b8e6")}).json()      # the tap, a moment later, reads what is kept
    assert got["ok"] is True and got["source"] == "kept" and len(f.calls) == 1
    aerial.warm("lpother", TAHOE[1], TAHOE[2], TAHOE[0], "visitor-1")      # the person's one fresh ask is spent: nothing is asked
    assert aerial.run_pending() == 1 and len(f.calls) == 1
    assert aerial.teaser("lpother") == ""


def test_a_job_that_finds_overpass_busy_gives_the_persons_ask_back(live, monkeypatch):
    monkeypatch.setattr(aerial, "PINS_PER_PERSON_A_DAY", 1)
    f = live(recorded("osm-lax.json"))
    taken = [aerial._SLOTS.acquire(blocking=False) for _ in range(aerial.AT_ONCE)]
    try:
        aerial.warm("lpbusy", LAX[1], LAX[2], LAX[0], "visitor-2")
        aerial.run_pending()
    finally:
        for _ in taken:
            aerial._SLOTS.release()
    assert f.calls == [] and aerial.warm("lpbusy", LAX[1], LAX[2], LAX[0], "visitor-2") is True      # not stuck in flight, and the allowance is still whole
    aerial.run_pending()
    assert len(f.calls) == 1 and aerial.teaser("lpbusy") != ""


def test_the_hotel_route_returns_while_overpass_is_still_thinking(client, live, monkeypatch):
    """With real workers the hotel's fragment comes back at once; the pins arrive when Overpass does."""
    gate, started = threading.Event(), threading.Event()
    body = recorded("osm-lax.json")

    def slow(host, q, timeout):
        started.set()
        gate.wait(10)
        return 200, body
    monkeypatch.setattr(aerial, "TRANSPORT", slow)
    monkeypatch.setattr(aerial, "ASYNC", True)
    try:
        j = client.get("/plan/matrix/hotel", params={"id": hotelview.token("lp1b8e6")}).json()
        assert "See it from above" in j["html"] and started.wait(5) and aerial.teaser("lp1b8e6") == ""      # asked, and not waited for
        gate.set()
        for _ in range(100):
            if aerial.teaser("lp1b8e6"):
                break
            time.sleep(0.05)
        assert aerial.teaser("lp1b8e6") == "Between two flight paths · 15 car parks within 500 m"
    finally:
        gate.set()
        aerial.stop()


# ---- the count behind Google's imagery ------------------------------------------------------------------------------------------

def test_without_a_google_key_nothing_is_offered_and_nothing_counted(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "")
    assert aerial.offered() is False and aerial.open_google("u1") == ("off", None) and aerial.opens_today() == 0


def test_the_key_is_handed_out_until_the_daily_cap_and_then_it_is_back_tomorrow(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "AIza-test-not-real")
    monkeypatch.setenv("GOOGLE_3D_A_DAY", "3")
    assert [aerial.open_google("u1") for _ in range(5)] == [("ok", "AIza-test-not-real")] * 3 + [("full", None)] * 2
    assert aerial.opens_today() == 3      # the refused opens are not counted


def test_the_cap_defaults_to_a_hundred_and_survives_a_restart_because_the_count_is_in_the_database(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "AIza-test-not-real")
    monkeypatch.delenv("GOOGLE_3D_A_DAY", raising=False)
    assert aerial.cap() == 100
    monkeypatch.setenv("GOOGLE_3D_A_DAY", "2")
    aerial.open_google("u1")
    aerial.open_google("u1")
    community._ready.clear()      # a new process: nothing in memory, only the database
    aerial._failed.clear()
    assert aerial.open_google("u1") == ("full", None)
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
    assert aerial.open_google("u1") == ("ok", "AIza-test-not-real") and aerial.open_google("u1") == ("full", None)
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
    assert re.search(r'data-aerial="lp1b8e6\.\d{10}\.[0-9a-f]{24}"', html) and 'data-keyed=""' in html
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
    return aerialview.sign(key)


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
    sign_in(client)
    ask = lambda **kw: client.post("/plan/matrix/aerial/open", data={"id": tok("lp1b8e6"), "view": "photo", **kw})  # noqa: E731
    first, second, third = ask(), ask(view="sat"), ask()
    assert (first.status_code, first.json()) == (200, {"ok": True, "key": "AIza-test-not-real"}) and second.json()["ok"] is True
    assert third.status_code == 429 and third.json()["message"] == "Back tomorrow" and third.json()["full"] is True and "AIza" not in third.text
    assert "no-store" in third.headers["cache-control"] and aerial.opens_today() == 2


def test_the_open_route_without_a_key_is_off_and_a_blind_post_spends_nothing(client, monkeypatch):
    sign_in(client)
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
    for host in ("https://unpkg.com/maplibre-gl@4.7.1/dist/", "https://cdn.jsdelivr.net/npm/cesium@1.123.0/", "https://tiles.openfreemap.org", "https://tile.googleapis.com"):
        assert host in csp.POLICY, host
    assert "blob:" in csp.POLICY.split("worker-src")[1].split(";")[0]
    assert "https://unpkg.com " not in csp.POLICY and "https://cdn.jsdelivr.net " not in csp.POLICY and "https://cdn.jsdelivr.net;" not in csp.POLICY      # the exact versioned folders, not the whole hosts
    assert "unpkg.com" in src and "cdn.jsdelivr.net" in src and "tile.googleapis.com" in src


def test_the_sample_card_names_the_recorded_hotel_and_says_sample(monkeypatch):
    from fasthtml.common import to_xml
    monkeypatch.setenv("GITAWAY_SHOWCASE", "1")
    html = to_xml(aerialview.sample_card("Lake Tahoe"))
    assert "Sample view" in html and "Hyatt Regency Lake Tahoe" in html and "Beach 5 min walk · 18 car parks within 500 m" in html and "See it from above" in html
    assert "Hilton Los Angeles Airport" in to_xml(aerialview.sample_card("San Diego"))
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    assert aerialview.sample_card("San Diego") == ""


def test_a_sample_squares_fine_print_has_the_sample_card_once_and_none_off_the_showcase(client, monkeypatch):
    from tests.test_tripmatrix_page import MATRIX
    square = "/plan/matrix/square?" + MATRIX.split("?")[1] + "&lane=sandiego&w=2026-12-12"
    monkeypatch.setenv("GITAWAY_SHOWCASE", "1")
    html = client.get(square).text
    assert html.count('class="av-card"') == 1 and html.count("Sample view") == 1 and "Hilton Los Angeles Airport" in html      # F-282: one card, in the fine print's "Getting there and around", opening the recorded real hotel
    assert len(re.findall(r'data-aerial="sample-lax\.\d{10}\.[0-9a-f]{24}"', html)) == 1


def test_the_card_uses_none_of_the_data_names_the_drawers_clicks_read(monkeypatch):
    """assets/js/v2drawer.js treats any button in the drawer with data-hotel, data-room, data-tab, data-fl or data-act as its own: a card named data-hotel hid the hotel it sat in (F-284 browser run)."""
    from fasthtml.common import to_xml
    monkeypatch.setenv("GITAWAY_SHOWCASE", "1")
    html = to_xml(aerialview.sample_card("San Diego"))
    for name in ("data-hotel", "data-room", "data-tab", "data-fl", "data-act", "data-gal-go", "data-show"):
        assert name + "=" not in html, name


# ---- the security fixes: sign-in, per-person allowance, token age, busy, atomic counts ----------------------------------------------------

def test_signed_out_nobody_gets_the_key_or_spends_the_count_and_the_page_is_told_to_sign_in(client, monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "AIza-test-not-real")
    r = client.post("/plan/matrix/aerial/open", data={"id": tok("lp1b8e6"), "view": "photo"})
    j = r.json()
    assert r.status_code == 401 and j["ok"] is False and j["signin"] is True and "AIza" not in r.text and aerial.opens_today() == 0
    assert j["message"] == "Fly around the hotel in 3D" and "Sign in" in j["more"] and j["href"].startswith("/signin")      # F-289: an invitation with the way in


def test_the_sign_in_invitation_brings_the_visitor_back_to_the_same_page_and_never_elsewhere(client, monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "AIza-test-not-real")
    here = client.post("/plan/matrix/aerial/open", data={"id": tok("lp1b8e6"), "view": "photo"}, headers={"referer": "http://testserver/plan/matrix?to=San+Diego"}).json()["href"]
    away = client.post("/plan/matrix/aerial/open", data={"id": tok("lp1b8e6"), "view": "photo"}, headers={"referer": "https://evil.example/plan/matrix"}).json()["href"]
    assert here.startswith("/signin?next=%2Fplan%2Fmatrix")      # back to the same page, our own path only
    assert "evil" not in away
    lookalike = client.post("/plan/matrix/aerial/open", data={"id": tok("lp1b8e6"), "view": "photo"}, headers={"referer": "http://testserver.evil.com/plan/matrix"}).json()["href"]
    assert "evil" not in lookalike and lookalike == "/signin"      # a host that only starts like ours falls back to plain sign-in


def test_a_viewer_may_open_the_views_because_they_only_look(client, monkeypatch):
    from gitaway import access
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "AIza-test-not-real")
    assert access.needed("POST", "/plan/matrix/aerial/open") is None
    sign_in(client)
    assert client.post("/plan/matrix/aerial/open", data={"id": tok("lp1b8e6"), "view": "sat"}).json()["ok"] is True


def test_each_person_has_a_daily_allowance_on_top_of_the_sites_and_a_refusal_gives_nothing_back_or_takes_nothing(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "AIza-test-not-real")
    monkeypatch.setenv("GOOGLE_3D_PER_PERSON_A_DAY", "2")
    monkeypatch.setenv("GOOGLE_3D_A_DAY", "4")
    assert [aerial.open_google("a")[0] for _ in range(3)] == ["ok", "ok", "person"]
    assert [aerial.open_google("b")[0] for _ in range(3)] == ["ok", "ok", "person"]
    assert aerial.open_google("c")[0] == "full" and aerial.opens_today() == 4
    assert aerial.open_google("c")[0] == "full" and aerial.person_cap() == 2      # the site's refusal handed c's own count back: c was never charged for it
    monkeypatch.setenv("GOOGLE_3D_A_DAY", "5")
    assert aerial.open_google("c")[0] == "ok"
    monkeypatch.delenv("GOOGLE_3D_PER_PERSON_A_DAY")
    assert aerial.person_cap() == 10


def test_a_card_token_stops_working_after_six_hours_and_a_forged_time_does_not_work(client, live):
    import time
    live(recorded("osm-lax.json"))
    old = aerialview.sign("lp1b8e6", now=time.time() - aerialview.TOKEN_AGE - 60)
    assert aerialview.unsign(old) == "" and aerialview.unsign(aerialview.sign("lp1b8e6")) == "lp1b8e6"
    assert client.get("/plan/matrix/aerial/pins", params={"id": old}).status_code == 404
    fresh = aerialview.sign("lp1b8e6")
    key, at, sig = fresh.rsplit(".", 2)
    assert aerialview.unsign(f"{key}.{int(at) + 1}.{sig}") == "" and aerialview.unsign(hotelview.token("lp1b8e6")) == ""      # the hotel view's own token is not this route's
    assert hotelview.unsign(hotelview.token("lp1b8e6")) == "lp1b8e6"      # and it still works where it did


def test_when_overpass_has_no_free_slot_the_page_is_told_busy_at_once_and_nothing_is_marked_failed(client, live):
    f = live(recorded("osm-lax.json"))
    taken = [aerial._SLOTS.acquire(blocking=False) for _ in range(aerial.AT_ONCE)]
    try:
        j = client.get("/plan/matrix/aerial/pins", params={"id": tok("lp1b8e6")}).json()
    finally:
        for _ in taken:
            aerial._SLOTS.release()
    assert j["ok"] is False and j["message"] == "Pins are busy, try again in a moment" and j["pins"] == [] and f.calls == []
    assert client.get("/plan/matrix/aerial/pins", params={"id": tok("lp1b8e6")}).json()["ok"] is True      # a moment later it asks


def test_a_person_has_a_limit_on_fresh_pins_but_kept_answers_are_free(client, live, monkeypatch):
    monkeypatch.setattr(aerial, "PINS_PER_PERSON_A_DAY", 2)
    f = live(recorded("osm-lax.json"), recorded("osm-tahoe.json"), recorded("osm-lax.json"))
    for i, hid in enumerate(("lpa", "lpb")):
        assert client.get("/plan/matrix/aerial/pins", params={"id": tok(hid)}).json()["ok"] is True
    for _ in range(3):      # kept: no ask, no count
        assert client.get("/plan/matrix/aerial/pins", params={"id": tok("lpa")}).json()["source"] == "kept"
    j = client.get("/plan/matrix/aerial/pins", params={"id": tok("lpc")}).json()
    assert j["ok"] is False and j["message"].startswith("You have looked at a lot of places today") and len(f.calls) == 2


def test_a_busy_answer_does_not_use_up_one_of_the_persons_fresh_pins(client, live, monkeypatch):
    """Security re-check: told "busy" asked nothing, so the person's daily pin is given back."""
    monkeypatch.setattr(aerial, "PINS_PER_PERSON_A_DAY", 1)
    live(recorded("osm-lax.json"))
    taken = [aerial._SLOTS.acquire(blocking=False) for _ in range(aerial.AT_ONCE)]
    try:
        for _ in range(3):
            assert client.get("/plan/matrix/aerial/pins", params={"id": tok("lpbusy")}).json()["message"] == "Pins are busy, try again in a moment"
    finally:
        for _ in taken:
            aerial._SLOTS.release()
    assert client.get("/plan/matrix/aerial/pins", params={"id": tok("lpbusy")}).json()["ok"] is True      # the one allowed fresh ask is still there


# ---- F-286 review fixes ---------------------------------------------------------------------------------------------------------

def test_stop_really_ends_an_idle_worker_so_it_cannot_take_a_later_tests_jobs(live, monkeypatch):
    live(recorded("osm-lax.json"))
    monkeypatch.setattr(aerial, "ASYNC", True)
    aerial.warm("lp1b8e6", LAX[1], LAX[2], LAX[0])
    for _ in range(100):
        if aerial.teaser("lp1b8e6"):
            break
        time.sleep(0.05)
    worker = aerial._thread[0]
    started = time.monotonic()
    aerial.stop()
    assert not worker.is_alive() and time.monotonic() - started < 3 and aerial._thread == []


def test_one_hotels_background_job_has_a_total_budget_across_mirrors_so_a_slow_mirror_cannot_hold_a_slot(live, monkeypatch):
    from types import SimpleNamespace
    now = [1000.0]
    monkeypatch.setattr(aerial, "time", SimpleNamespace(monotonic=lambda: now[0]))
    asked = []

    def slow(host, q, timeout):
        asked.append((host, timeout))
        now[0] += timeout      # the mirror uses all the time it is given
        raise TimeoutError("past the deadline")
    monkeypatch.setattr(aerial, "TRANSPORT", slow)
    aerial.warm("lpslow", LAX[1], LAX[2], LAX[0])
    aerial.run_pending()
    assert aerial.BACKGROUND_BUDGET == 60.0
    assert asked == [("overpass-api.de", 40.0), ("overpass.kumi.systems", 20.0)]      # 60 s in all: the third mirror is not asked


def test_the_showcase_hotels_are_made_up_so_showing_one_queues_nothing(live, monkeypatch):
    f = live(recorded("osm-lax.json"))
    monkeypatch.setenv("GITAWAY_SHOWCASE", "1")
    hotelview.fragment("lp1b8e6")
    assert aerial.run_pending() == 0 and f.calls == []
