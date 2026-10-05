"""F-073: Around you's model (gitaway/around.py) with the services faked: the Overpass query and its parsing, opening hours, the cache, the throttle and
back-off, the family's food preference, and the AI ranking with its checks and its fallback. No test reaches the network."""
import json
from datetime import datetime
from urllib.parse import unquote

import pytest

from gitaway import ai, around, geo
from tests.test_signin import person

NOW = datetime(2026, 10, 5, 12, 40)      # a Monday


def answer(*els):
    return {"elements": list(els)}


def node(name=None, lat=33.81, lon=-117.92, **tags):
    t = {k.replace("_", ":", 1) if k.startswith(("diet_", "contact_")) else k: v for k, v in tags.items()}
    if name:
        t["name"] = name
    return {"type": "node", "id": abs(hash((name, lat))) % 10**6, "lat": lat, "lon": lon, "tags": t}


class Overpass:
    def __init__(self, *els, fail=None):
        self.calls, self.els, self.fail = [], els, fail

    def __call__(self, url, timeout=0):
        self.calls.append(url)
        if self.fail:
            raise self.fail
        return answer(*self.els)


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    around.clear_cache()
    for gate in around.GATES:                 # every Overpass mirror has its own gate (F-095)
        monkeypatch.setattr(gate, "gap", 0.0)
        monkeypatch.setattr(gate, "shut_until", None)
    yield
    around.clear_cache()


# ---- the query and parsing -----------------------------------------------------------------------------------------------

@pytest.mark.parametrize("cat,needles", [
    ("veg", ['"diet:vegetarian"~"^(yes|only)$"', 'cuisine', 'restaurant|fast_food|cafe']),
    ("coffee", ['"amenity"="cafe"']),
    ("groc", ['supermarket|convenience|greengrocer']),
    ("big", ['"brand"~"Costco|Walmart",i']),
    ("rx", ['"amenity"="pharmacy"']),
    ("gas", ['"amenity"="fuel"']),
    ("wc", ['"amenity"="toilets"']),
])
def test_each_chip_has_its_tags_a_bounded_radius_and_the_rounded_point(cat, needles):
    q = around.build_query(cat, 33.812345, -117.918999, 1500)
    for n in needles:
        assert n in q
    assert "(around:1500,33.812,-117.919)" in q
    assert q.startswith("[out:json][timeout:8];") and "out center tags" in q


def test_the_vegetarian_preference_is_strict_and_without_it_limited_veg_places_come_too():
    strict = around.build_query("veg", 1, 2, 1500, True)
    loose = around.build_query("veg", 1, 2, 1500, False)
    assert "limited" not in strict and "limited" in loose


def test_parsing_reads_nodes_and_ways_phone_hours_web_and_names_the_nameless():
    got = around.parse(answer(
        node("Green Bowl", phone="+1 714 555 0100", opening_hours="Mo-Su 09:00-21:00", website="https://greenbowl.example", cuisine="vegetarian"),
        {"type": "way", "id": 2, "center": {"lat": 33.82, "lon": -117.93}, "tags": {"name": "Plant Cafe", "contact:phone": "714-555-0111", "website": "javascript:x"}},
        node(None, lat=33.8, lon=-117.9, amenity="toilets"),
        node("Green Bowl"),                         # the same name at the same spot: once
        {"type": "node", "id": 9, "tags": {"name": "No position"}},
        "junk"), "wc")
    assert [p["name"] for p in got] == ["Green Bowl", "Plant Cafe", "Public restroom"]
    gb = got[0]
    assert gb["phone"] == "+1 714 555 0100" and gb["hours"] == "Mo-Su 09:00-21:00" and gb["website"] == "https://greenbowl.example" and gb["tags"]["cuisine"] == "vegetarian"
    assert got[1]["phone"] == "714-555-0111" and got[1]["website"] == "" and (got[1]["lat"], got[1]["lon"]) == (33.82, -117.93)


# ---- opening hours -------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("spec,when,want", [
    ("24/7", datetime(2026, 10, 5, 3, 0), True),
    ("Mo-Su 09:00-21:00", datetime(2026, 10, 5, 12, 40), True),
    ("Mo-Su 09:00-21:00", datetime(2026, 10, 5, 21, 0), False),
    ("Mo-Fr 08:00-17:00", datetime(2026, 10, 10, 10, 0), False),            # a Saturday: no rule, closed
    ("Mo-Fr 08:00-17:00; Sa 09:00-13:00", datetime(2026, 10, 10, 10, 0), True),
    ("Mo-Sa 09:00-18:00; Su off", datetime(2026, 10, 11, 12, 0), False),    # a Sunday
    ("Mo-Su 09:00-12:00,13:00-17:00", datetime(2026, 10, 5, 12, 30), False),
    ("Mo-Su 09:00-12:00,13:00-17:00", datetime(2026, 10, 5, 13, 30), True),
    ("Fr-Sa 18:00-02:00", datetime(2026, 10, 10, 1, 0), True),               # Saturday 1 AM is still Friday night
    ("Fr-Sa 18:00-02:00", datetime(2026, 10, 9, 23, 0), True),
    ("Fr-Sa 18:00-02:00", datetime(2026, 10, 12, 1, 0), False),             # Monday 1 AM follows a Sunday that was closed
    ("09:00-17:00", datetime(2026, 10, 7, 9, 0), True),                      # no days: every day
    ("Mo-Su 00:00-24:00", datetime(2026, 10, 7, 23, 59), True),
    ("Mo-Su 09:00-21:00; PH off", datetime(2026, 10, 5, 12, 40), True),     # holidays are not known: the ordinary hours stand
    ("Sa-Mo 10:00-12:00", datetime(2026, 10, 5, 11, 0), True),               # a range of days that wraps the week
])
def test_open_now(spec, when, want):
    assert around.open_now(spec, when) is want


@pytest.mark.parametrize("spec", ["", None, "Apr-Oct Mo-Fr 10:00-18:00", "sunrise-sunset", "Mo-Fr 10:00+", "week 1-5 Mo 10:00-12:00"])
def test_hours_it_cannot_read_are_unknown_never_a_guess(spec):
    assert around.open_now(spec, NOW) is None
    assert around.open_label(None) == "Hours unknown"


def test_labels():
    assert around.open_label(True) == "Open now" and around.open_label(False) == "Closed now"
    assert around.miles_label(40) == "under 0.1 mi" and around.miles_label(805) == "0.5 mi"
    assert around.minutes_label(400, "walk") == "about 5 min walk" and around.minutes_label(100, "walk") == "about 1 min walk" and around.minutes_label(6000, "drive") == "about 10 min drive"
    assert around.next_half_hour(datetime(2026, 10, 5, 12, 40)) == 13 * 60 and around.next_half_hour(datetime(2026, 10, 5, 12, 0)) == 12 * 60 + 30


# ---- the service: cache, throttle, back-off ------------------------------------------------------------------------------

def test_a_second_search_for_the_same_spot_comes_from_the_cache_for_thirty_minutes(monkeypatch):
    f = Overpass(node("Green Bowl", diet_vegetarian="yes"))
    monkeypatch.setattr(geo, "fetch", f)
    t = [1000.0]
    monkeypatch.setattr(around, "_clock", lambda: t[0])
    around.search("veg", 33.8121, -117.9190, "walk", NOW, pref=True)
    around.search("veg", 33.8123, -117.9191, "walk", NOW, pref=True)     # a few metres away: the same rounded point
    assert len(f.calls) == 1
    around.search("veg", 33.8121, -117.9190, "drive", NOW, pref=True)    # another radius: asked again
    around.search("wc", 33.8121, -117.9190, "walk", NOW)                  # another category: asked again
    assert len(f.calls) == 3
    t[0] += 31 * 60
    around.search("veg", 33.8121, -117.9190, "walk", NOW, pref=True)
    assert len(f.calls) == 4


def test_the_request_names_us_and_carries_only_the_rounded_point(monkeypatch):
    f = Overpass(node("A"))
    monkeypatch.setattr(geo, "fetch", f)
    around.search("coffee", 33.812345, -117.918999, "walk", NOW)
    assert f.calls[0].startswith("https://overpass-api.de/api/interpreter?data=")
    assert "33.812345" not in unquote(f.calls[0]) and "33.812" in unquote(f.calls[0])
    assert "GitAway" in geo.USER_AGENT and "railway.app" in geo.USER_AGENT


def test_calls_are_at_least_a_gap_apart_for_the_whole_process(monkeypatch):
    f = Overpass(node("A"))
    monkeypatch.setattr(geo, "fetch", f)
    monkeypatch.setattr(around.GATE, "gap", 2.0)
    slept = []
    monkeypatch.setattr(geo, "_sleep", slept.append)
    t = [50.0]
    monkeypatch.setattr(geo, "_clock", lambda: t[0])
    around.GATE.last = None
    around.search("coffee", 1.0, 2.0, "walk", NOW)
    around.search("gas", 1.0, 2.0, "walk", NOW)
    assert len(f.calls) == 2 and slept and 1.9 <= slept[0] <= 2.0


@pytest.mark.parametrize("code", [429, 403])
def test_a_refusal_shuts_the_door_for_ten_minutes_and_the_person_gets_a_sentence(monkeypatch, code):
    e = OSError("no")
    e.code = code
    f = Overpass(fail=e)
    monkeypatch.setattr(geo, "fetch", f)
    with pytest.raises(around.AroundError) as err:
        around.search("coffee", 1.0, 2.0, "walk", NOW)
    assert str(err.value) == around.NO_PLACES
    assert all(g.is_shut() for g in around.GATES)          # each mirror refused us, so each is left alone
    with pytest.raises(around.AroundError):
        around.search("gas", 1.0, 2.0, "walk", NOW)
    assert len(f.calls) == len(around.MIRRORS)   # each mirror asked once; the second search never left the machine


def test_a_failure_is_not_cached(monkeypatch):
    monkeypatch.setattr(geo, "fetch", Overpass(fail=OSError("down")))
    with pytest.raises(around.AroundError):
        around.search("coffee", 1.0, 2.0, "walk", NOW)
    monkeypatch.setattr(geo, "fetch", Overpass(node("Back Up", lat=1.0, lon=2.0)))
    assert around.search("coffee", 1.0, 2.0, "walk", NOW)["items"][0]["name"] == "Back Up"


def test_a_garbled_answer_is_a_failure(monkeypatch):
    monkeypatch.setattr(geo, "fetch", lambda url, timeout=0: {"remark": "runtime error"})
    with pytest.raises(around.AroundError):
        around.search("coffee", 1.0, 2.0, "walk", NOW)


def test_the_tests_never_reach_the_network():
    with pytest.raises(around.AroundError):
        around.search("coffee", 1.0, 2.0, "walk", NOW)


# ---- ranking -------------------------------------------------------------------------------------------------------------

def near(name, dlat, **tags):
    return node(name, lat=33.8121 + dlat, lon=-117.9190, **tags)


def test_without_the_model_places_are_nearest_first_with_closed_ones_last_and_at_most_five(monkeypatch):
    monkeypatch.setattr(geo, "fetch", Overpass(
        near("Far", 0.0090), near("Closed Near", 0.0005, opening_hours="Mo-Su 01:00-02:00"), near("Mid", 0.0040),
        near("Open Near", 0.0010, opening_hours="Mo-Su 09:00-21:00"), near("Unknown", 0.0020), near("Six", 0.0100), near("Seven", 0.0110)))
    r = around.search("coffee", 33.8121, -117.9190, "walk", NOW)
    assert r["ai"] is False
    names = [c["name"] for c in r["items"]]
    assert names == ["Open Near", "Unknown", "Mid", "Far", "Six"]          # Closed Near is nearer than all but is last of the seven, so it is cut
    first = r["items"][0]
    assert first["open_label"] == "Open now" and first["walk"].startswith("about ") and first["dist"].endswith("mi") and first["why"] == ""


def test_places_outside_the_radius_are_left_out(monkeypatch):
    monkeypatch.setattr(geo, "fetch", Overpass(near("Across Town", 0.05)))
    assert around.search("coffee", 33.8121, -117.9190, "walk", NOW)["items"] == []
    around.clear_cache()
    assert [c["name"] for c in around.search("coffee", 33.8121, -117.9190, "drive", NOW)["items"]] == ["Across Town"]   # 5.5 km is inside 8 km


class Model:
    """A fake AI service: answers with `picks`; remembers what it was sent."""

    def __init__(self, picks=None, status=200):
        self.picks, self.status, self.sent = picks, status, []

    def __call__(self, url, headers, body, timeout):
        self.sent.append(json.loads(body))
        content = json.dumps({"picks": self.picks})
        return self.status, json.dumps({"choices": [{"message": {"content": content}}], "usage": {"prompt_tokens": 100, "completion_tokens": 20}})


@pytest.fixture
def azure(monkeypatch):
    for k, v in (("AZURE_OPENAI_API_KEY", "k"), ("AZURE_OPENAI_ENDPOINT", "https://x.example/openai/v1"), ("AZURE_OPENAI_DEPLOYMENT", "d")):
        monkeypatch.setenv(k, v)


def six_places(monkeypatch):
    monkeypatch.setattr(geo, "fetch", Overpass(*[near(f"Place {i}", 0.001 * (i + 1), cuisine="vegetarian") for i in range(6)]))


def test_the_model_picks_and_explains_and_what_it_was_sent_has_no_location_or_family(monkeypatch, azure):
    six_places(monkeypatch)
    model = Model([{"id": 2, "why": "Open and close by"}, {"id": 0, "why": "Nearest"}])
    monkeypatch.setattr(ai, "TRANSPORT", model)
    r = around.search("veg", 33.8121, -117.9190, "walk", NOW, pref=True, family="fam1")
    assert r["ai"] is True
    assert [c["name"] for c in r["items"][:2]] == ["Place 2", "Place 0"] and r["items"][0]["why"] == "Open and close by"
    assert len(r["items"]) == 5 and r["items"][2]["why"] == ""        # filled up with the next nearest, no reason
    sent = json.dumps(model.sent[0])
    for forbidden in ("33.81", "-117.9", "lat", "lon", "fam1", "Ari", "Sam"):
        assert forbidden not in sent
    assert "Vegetarian food" in sent and "Place 3" in sent and "true" in sent
    assert ai.usage_rows()[-1]["job"] == "around-you"


def test_places_the_model_made_up_or_repeated_are_dropped_and_none_valid_falls_back(monkeypatch, azure):
    six_places(monkeypatch)
    monkeypatch.setattr(ai, "TRANSPORT", Model([{"id": 99, "why": "x"}, {"id": -1, "why": "x"}, {"id": 1, "why": "Good"}, {"id": 1, "why": "again"}, {"id": "3", "why": "str"}]))
    r = around.search("veg", 33.8121, -117.9190, "walk", NOW, pref=True)
    assert r["ai"] and r["items"][0]["name"] == "Place 1" and [c["name"] for c in r["items"]].count("Place 1") == 1
    around.clear_cache()
    monkeypatch.setattr(ai, "TRANSPORT", Model([{"id": 42, "why": "ghost"}]))
    r = around.search("veg", 33.8121, -117.9190, "walk", NOW, pref=True)
    assert r["ai"] is False and r["items"][0]["name"] == "Place 0"


@pytest.mark.parametrize("how", ["off", "fail", "busy"])
def test_if_the_model_is_off_failing_or_busy_the_order_is_by_distance(monkeypatch, azure, how):
    six_places(monkeypatch)
    if how == "off":
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "")
    elif how == "fail":
        monkeypatch.setattr(ai, "TRANSPORT", Model(status=500))
    else:
        with ai._guard:
            ai._in_flight.add(("around-you", "famX"))
    try:
        r = around.search("veg", 33.8121, -117.9190, "walk", NOW, pref=True, family="famX")
    finally:
        with ai._guard:
            ai._in_flight.discard(("around-you", "famX"))
    assert r["ai"] is False and r["items"][0]["name"] == "Place 0"


# ---- the family's preference ---------------------------------------------------------------------------------------------

def test_the_family_preference_is_kept_per_family():
    ari, sam = person("ari"), person("sam@example.com")
    assert around.vegetarian(ari) is False
    around.set_vegetarian(ari, True)
    assert around.vegetarian(ari) is True and around.vegetarian(sam) is False
    around.set_vegetarian(ari, False)
    assert around.vegetarian(ari) is False


# ---- F-095: when the main Overpass server refuses or is slow, the next mirror answers --------------------------------------------

class Flaky(Overpass):
    """The main server fails (a refusal, a timeout); the mirrors answer."""
    def __call__(self, url, timeout=0):
        self.calls.append(url)
        if url.startswith(around.MIRRORS[0].split("?")[0]):
            raise self.fail
        return answer(*self.els)


@pytest.mark.parametrize("why", ["refused", "timeout"])
def test_the_next_mirror_answers_when_the_main_server_fails(monkeypatch, why):
    e = OSError("no")
    if why == "refused":
        e.code = 429
    else:
        e = TimeoutError("timed out")
    f = Flaky(node("Coffee Commissary", lat=1.0, lon=2.0, amenity="cafe"), fail=e)
    monkeypatch.setattr(geo, "fetch", f)
    got = around.search("coffee", 1.0, 2.0, "walk", NOW)
    assert got["items"][0]["name"] == "Coffee Commissary"
    assert len(f.calls) == 2 and f.calls[1].startswith(around.MIRRORS[1].split("?")[0])
    assert all(m.startswith("https://") for m in around.MIRRORS) and len(around.MIRRORS) >= 3
