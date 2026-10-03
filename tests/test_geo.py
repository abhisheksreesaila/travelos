"""F-068: places get coordinates once (cached per family, one lookup a second), drive times and routes come from a public router and are cached.
No test touches the network: `geo.fetch` is replaced by a fake that records its calls."""
import pytest

from gitaway import familydb, geo
from tests.test_signin import person

NOM = [{"lat": "34.1184", "lon": "-118.3004", "display_name": "Griffith Observatory, Los Angeles, California"}]


class Fake:
    """A stand-in for geo.fetch: answers by URL, remembers every call, and has a clock the throttle can sleep on."""

    def __init__(self):
        self.calls, self.now, self.slept = [], 100.0, []
        self.nominatim, self.osrm = NOM, {"code": "Ok", "routes": [{"duration": 1500.0, "geometry": {"type": "LineString", "coordinates": [[-118.0, 34.0], [-118.3, 34.1]]}}]}

    def __call__(self, url, timeout=0):
        self.calls.append(url)
        if isinstance(self.nominatim, Exception) and "nominatim" in url:
            raise self.nominatim
        if isinstance(self.osrm, Exception) and "osrm" in url:
            raise self.osrm
        if "nominatim" in url and self.nominatim is NOM:  # each new place is somewhere else
            n = sum("nominatim" in c for c in self.calls)
            return [{**NOM[0], "lat": str(34.0 + n / 100)}]
        return self.nominatim if "nominatim" in url else self.osrm

    def clock(self):
        return self.now

    def sleep(self, s):
        self.slept.append(s)
        self.now += s


@pytest.fixture
def fake(monkeypatch):
    f = Fake()
    monkeypatch.setattr(geo, "fetch", f)
    monkeypatch.setattr(geo, "_clock", f.clock)
    monkeypatch.setattr(geo, "_sleep", f.sleep)
    monkeypatch.setattr(geo.NOMINATIM_GATE, "gap", 1.0)
    monkeypatch.setattr(geo.OSRM_GATE, "gap", 0.25)
    monkeypatch.setattr(geo.NOMINATIM_GATE, "last", None)
    monkeypatch.setattr(geo.OSRM_GATE, "last", None)
    monkeypatch.setattr(geo.NOMINATIM_GATE, "shut_until", None)
    monkeypatch.setattr(geo.OSRM_GATE, "shut_until", None)
    return f


@pytest.fixture
def db():
    with familydb.using(person()) as handle:
        yield handle


def test_a_place_is_looked_up_once_then_comes_from_the_cache(fake, db):
    assert geo.coords("Griffith Observatory, Los Angeles", db) == (34.01, -118.3004)
    assert geo.coords("griffith  observatory, los angeles", db) == (34.01, -118.3004)
    assert len(fake.calls) == 1
    assert fake.calls[0].startswith("https://nominatim.openstreetmap.org/search?format=json&q=Griffith") and fake.calls[0].endswith("&limit=1")


def test_the_cache_is_per_family(fake, db):
    geo.coords("Griffith Observatory", db)
    with familydb.using(person("sam")) as other:
        geo.coords("Griffith Observatory", other)
    assert len(fake.calls) == 2


def test_a_place_that_is_not_found_is_remembered_and_says_so(fake, db):
    fake.nominatim = []
    assert geo.coords("Nowhere in Particular", db) is None
    assert geo.state("Nowhere in Particular", db) == (geo.MISSING, None)
    assert geo.coords("Nowhere in Particular", db) is None
    assert len(fake.calls) == 1


def test_a_failed_lookup_is_not_remembered_so_it_is_tried_again(fake, db):
    fake.nominatim = OSError("down")
    assert geo.coords("Griffith Observatory", db) is None
    assert geo.state("Griffith Observatory", db) == (None, None)  # unknown, not "missing"
    fake.nominatim = NOM
    assert geo.coords("Griffith Observatory", db) == (34.02, -118.3004)


def test_at_most_one_lookup_a_second(fake, db):
    geo.coords("Place one", db)
    geo.coords("Place two", db)
    geo.coords("Place three", db)
    assert len(fake.calls) == 3
    assert sum(fake.slept) >= 2.0 - 1e-6 and all(s <= 1.0 for s in fake.slept)


def test_an_airport_needs_no_lookup(fake, db):
    lat, lon = geo.coords("LAX airport", db)
    assert 33.9 < lat < 34.0 and -118.5 < lon < -118.3
    assert fake.calls == []


def test_lookup_off_never_calls_out(fake, db):
    assert geo.coords("Griffith Observatory", db, lookup=False) is None
    assert fake.calls == []


def test_drive_minutes_are_cached(fake, db):
    a, b = (34.0, -118.0), (34.1, -118.3)
    assert geo.drive_minutes(a, b, db) == 25
    assert geo.drive_minutes(a, b, db) == 25
    assert len(fake.calls) == 1
    assert fake.calls[0].startswith("https://router.project-osrm.org/route/v1/driving/-118.0,34.0;-118.3,34.1?overview=full&geometries=geojson")


def test_drive_minutes_is_none_on_any_failure(fake, db):
    fake.osrm = OSError("down")
    assert geo.drive_minutes((34.0, -118.0), (34.1, -118.3), db) is None
    fake.osrm = {"code": "NoRoute", "routes": []}
    assert geo.drive_minutes((34.0, -118.0), (34.1, -118.3), db) is None
    fake.osrm = "garbage"
    assert geo.drive_minutes((34.0, -118.0), (34.1, -118.3), db) is None


def test_route_joins_the_legs_into_one_line(fake, db):
    line = geo.route([(34.0, -118.0), (34.1, -118.3), (34.2, -118.5)], db)
    assert line["type"] == "LineString" and len(line["coordinates"]) >= 3
    assert geo.route([(34.0, -118.0)], db) is None
    fake.osrm = OSError("down")
    assert geo.route([(35.0, -117.0), (35.1, -117.3)], db) is None


def test_cached_minutes_between_places_never_calls_out(fake, db):
    assert geo.cached_minutes("Griffith Observatory", "Santa Monica Pier", db) is None
    geo.warm(db, ["Griffith Observatory", "Santa Monica Pier"], budget=30)
    n = len(fake.calls)
    assert geo.cached_minutes("Griffith Observatory", "Santa Monica Pier", db) == 25
    assert len(fake.calls) == n


def test_warm_stops_when_the_budget_runs_out_and_reports_what_is_left(fake, db):
    left = geo.warm(db, ["A place", "B place", "C place", "D place"], budget=1.5)
    assert 0 < left
    assert len(fake.calls) < 7


# ---- bounded time, back off, no double lookups (review of F-068) --------------------------------------------------------

def test_a_slow_service_cannot_hold_the_page_past_its_budget(db, monkeypatch):
    import time

    def slow(url, timeout=0):
        time.sleep(min(timeout, 10))  # a service that never answers: the call ends when its timeout does
        raise TimeoutError("slow")
    monkeypatch.setattr(geo, "fetch", slow)
    monkeypatch.setattr(geo, "_clock", time.monotonic)
    monkeypatch.setattr(geo, "_sleep", time.sleep)
    monkeypatch.setattr(geo.NOMINATIM_GATE, "gap", 1.0)
    monkeypatch.setattr(geo.NOMINATIM_GATE, "last", None)
    start = time.monotonic()
    geo.warm(db, ["Place one", "Place two", "Place three"], budget=1.0)
    assert time.monotonic() - start < 2.0


def test_a_call_gives_up_instead_of_queueing_behind_another_thread(monkeypatch):
    import threading
    import time
    monkeypatch.setattr(geo, "_clock", time.monotonic)
    gate = geo.Gate(1.0)
    gate.lock.acquire()  # a background thread is holding the slot
    done = []
    t0 = time.monotonic()
    threading.Thread(target=lambda: done.append(gate.wait(time.monotonic() + 0.3))).start()
    time.sleep(0.6)
    gate.lock.release()
    assert done == [False] and time.monotonic() - t0 < 1.5


def test_a_429_or_403_shuts_the_service_for_ten_minutes(fake, db):
    import urllib.error
    fake.nominatim = urllib.error.HTTPError("u", 429, "Too Many Requests", {}, None)
    assert geo.coords("First place", db) is None
    n = len(fake.calls)
    fake.nominatim = NOM
    assert geo.coords("Second place", db) is None and len(fake.calls) == n  # shut: not even asked
    fake.now += 601
    assert geo.coords("Second place", db) is not None
    fake.osrm = urllib.error.HTTPError("u", 403, "Forbidden", {}, None)
    assert geo.drive_minutes((34.0, -118.0), (34.1, -118.3), db) is None
    fake.osrm = Fake().osrm
    calls = len(fake.calls)
    assert geo.drive_minutes((34.0, -118.0), (34.2, -118.4), db) is None and len(fake.calls) == calls


def test_a_place_another_thread_stored_while_we_waited_is_not_asked_again(fake, db, monkeypatch):
    real_wait = geo.NOMINATIM_GATE.wait

    def wait_then_someone_else_stores_it(deadline=None):
        ok = real_wait(deadline)
        geo._put(db, "place", geo._norm("Shared place"), lat=1.0, lon=2.0, data="Shared place")
        return ok
    monkeypatch.setattr(geo.NOMINATIM_GATE, "wait", wait_then_someone_else_stores_it)
    assert geo.coords("Shared place", db) == (1.0, 2.0)
    assert fake.calls == []


def test_cached_coords_and_place_name_drives_read_only_the_cache_inside_a_scope(fake):
    session = person()
    assert geo.cached_coords("Griffith Observatory") is None  # outside a scope there is no database to read
    with geo.cache_scope(session) as db:
        assert geo.cached_coords("Griffith Observatory") is None and fake.calls == []
        geo.warm(db, ["Griffith Observatory", "Santa Monica Pier"], budget=30)
        n = len(fake.calls)
        assert geo.cached_coords("Griffith Observatory") == (34.01, -118.3004)
        assert geo.drive_minutes("Griffith Observatory", "Santa Monica Pier") == 25
        assert geo.drive_minutes("Griffith Observatory", "Nowhere Else") is None
        assert geo.cached_coords("LAX") is not None and len(fake.calls) == n  # a bare code is that airport; none of this called out
