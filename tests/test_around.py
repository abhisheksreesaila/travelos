"""F-073: Around you through the HTTP seam, with Overpass, the geocoder and the model faked: the page and its chips, the cards (distance, open now, Directions,
Call, Add to plan), the family's food preference, the fallback to the hotel, roles, Add to plan through the calendar, the Ideas button and the privacy page."""
import json
import re
from datetime import datetime, timezone
from html import unescape
from urllib.parse import parse_qs, unquote, urlparse

import pytest

from gitaway import ai, around, catalog, geo
from tests.test_canvas import azure  # noqa: F401 - fixture of the canvas tests
from tests.test_map import Maps
from tests.test_trip_canvas import trip  # noqa: F401 - fixture: a trip with parts and steps, one called Lunch
from tests.test_members import addr, browser, invite
from tests.test_signin import sign_in, stored_calendar
from tests.test_trip_import import imported, visible
from tests.test_trip_phone import IPHONE, plan

HOME = (34.0100, -118.4900)       # the hotel in tests.test_map.PLACES: "Check in" on day 0


def place(name, dlat=0.0, dlon=0.0, **tags):
    t = {k.replace("_", ":", 1) if k.startswith(("diet_", "contact_")) else k: v for k, v in tags.items()}
    t["name"] = name
    return {"type": "node", "id": 1, "lat": HOME[0] + dlat, "lon": HOME[1] + dlon, "tags": t}


class World(Maps):
    """The map services: the geocoder and router of tests.test_map, plus an Overpass that answers `els` and remembers the queries."""

    def __init__(self, *els):
        super().__init__()
        self.els, self.overpass = list(els), []

    def __call__(self, url, timeout=0):
        if "overpass-api.de" in url:
            self.overpass.append(unquote(url.split("data=")[1]))
            return {"elements": self.els}
        return super().__call__(url, timeout)


@pytest.fixture(autouse=True)
def slow_clock(monkeypatch):
    """Each search is 3 seconds after the last, so the per-person limit stays out of the way unless a test sets its own clock."""
    from gitaway.pages import around_ui
    t = [0.0]

    def tick():
        t[0] += 3.0
        return t[0]
    around_ui.LIMITS.clear()
    monkeypatch.setattr(around_ui, "_now", tick)


@pytest.fixture
def world(monkeypatch):
    w = World(place("Green Bowl", 0.002, phone="+1 310 555 0142", opening_hours="Mo-Su 09:00-21:00", website="https://greenbowl.example", diet_vegetarian="only", cuisine="vegetarian"),
              place("Plant Cafe", 0.004, diet_vegetarian="yes"),
              place("Night Owl", 0.001, opening_hours="Mo-Su 22:00-23:00", diet_vegetarian="yes"),
              place("Hours Unknown Deli", 0.006, diet_vegetarian="yes"))
    monkeypatch.setattr(geo, "fetch", w)
    monkeypatch.setattr(catalog, "now_utc", lambda: datetime(2026, 10, 17, 19, 40, tzinfo=timezone.utc))   # Saturday 12:40 PM in Los Angeles
    monkeypatch.setattr(catalog, "today", lambda *_: datetime(2026, 10, 17).date())
    return w


def search(client, cat="veg", lat=HOME[0], lon=HOME[1], mode="walk", day="1", **extra):
    data = {"cat": cat, "mode": mode, "day": day, **extra}
    if lat is not None:
        data.update(lat=str(lat), lon=str(lon))
    return client.post("/trip/map/around", data=data)


def cards(html):
    return re.findall(r'<div data-place="([^"]*)" class="ar-card"', unescape(html))


def tag_href(html, klass):
    """The href of the <a> whose class list ends in `klass`."""
    tag = re.search(r'<a [^>]*class="[^"]*\b%s"[^>]*>' % klass, html).group(0)
    return unescape(re.search(r'href="([^"]+)"', tag).group(1))


def one_card(html, name):
    m = re.search(r'(<div data-place="%s" class="ar-card".*?)(?=<div data-place=|<p id="ar-how"|$)' % re.escape(name), html, re.S)
    return m.group(1)


# ---- the page ------------------------------------------------------------------------------------------------------------

def test_the_map_tab_has_two_segments_and_around_you_has_the_seven_chips(client, world):
    imported(client)
    stops = client.get("/trip/map?day=1").text
    assert 'id="mp-seg-stops"' in stops and 'id="mp-seg-around"' in stops and 'href="/trip/map?view=around&amp;day=1"' in stops
    page = client.get("/trip/map?view=around&day=1").text
    labels = re.findall(r'id="ar-chip-(\w+)"', page)
    assert labels == ["veg", "coffee", "groc", "big", "rx", "gas", "wc"]
    t = " ".join(visible(page).split())
    for word in ("Vegetarian food", "Coffee", "Groceries", "Costco / Walmart", "Pharmacy", "Gas", "Restrooms", "Use my location", "Walking", "Driving"):
        assert word in t
    assert "only when you tap" in t and "does not keep it" in t
    assert 'aria-current="true"' in re.search(r'<a [^>]*id="mp-seg-around"[^>]*>', page).group(0)
    assert world.overpass == []                      # opening the page searches nothing
    assert "/assets/js/around.js" in page and "/assets/css/around.css" in page


def test_nothing_is_picked_until_the_family_says_vegetarian_and_then_the_vegetarian_chip_is(client, world):
    imported(client)
    page = client.get("/trip/map?view=around&day=1").text
    assert 'aria-pressed="true"' not in re.search(r'id="ar-chips".*?</div>', page, re.S).group(0)
    assert "Family food preference: none" in " ".join(visible(page).split())
    client.post("/family/food", data={"vegetarian": "1"})
    page = client.get("/trip/map?view=around&day=1").text
    assert re.search(r'<button[^>]*id="ar-chip-veg"[^>]*aria-pressed="true"', page) or re.search(r'aria-pressed="true"[^>]*id="ar-chip-veg"', page)
    t = " ".join(visible(page).split())
    assert "From your family profile:" in t and "Vegetarian" in t and "real vegetarian dishes" in t or "serve real vegetarian dishes" in t


def test_the_ideas_link_opens_around_you_on_the_food_chip_whatever_the_preference(client, world):
    imported(client)
    page = client.get("/trip/map?view=around&cat=coffee&day=0").text
    assert re.search(r'id="ar-chip-coffee"[^>]*aria-pressed="true"', page) or re.search(r'aria-pressed="true"[^>]*id="ar-chip-coffee"', page)
    page = client.get("/trip/map?view=around&cat=bogus").text
    assert page.count('aria-pressed="true"') == 1       # only the walking range is on


def test_a_meal_part_gets_an_ideas_button_that_opens_around_you_on_its_day(trip):
    html = trip.get("/trip/canvas?block=a1").text
    ideas = re.findall(r'<a [^>]*class="[^"]*ar-ideas[^"]*"[^>]*>', html)
    assert len(ideas) == 1                                          # the one part called Lunch
    assert 'href="/trip/map?view=around&amp;day=0&amp;cat=veg"' in ideas[0] or re.search(r'href="/trip/map\?view=around&amp;day=\d&amp;cat=veg"', ideas[0])
    assert "Ideas" in visible(html)
    follow = trip.get(unescape(re.search(r'href="([^"]+)"', ideas[0]).group(1)))
    assert follow.status_code == 200 and 'id="ar-chip-veg"' in follow.text


# ---- the cards -----------------------------------------------------------------------------------------------------------

def test_a_chip_finds_places_with_distance_open_now_directions_call_and_add_to_plan(client, world):
    imported(client)
    client.post("/family/food", data={"vegetarian": "1"})
    r = search(client)
    assert r.status_code == 200
    assert cards(r.text)[0] == "Green Bowl"
    assert "Night Owl" in cards(r.text)         # closed now, but listed after the open ones
    assert cards(r.text).index("Night Owl") > cards(r.text).index("Green Bowl")
    card = one_card(r.text, "Green Bowl")
    t = " ".join(visible(card).split())
    assert "Open now" in t and re.search(r"0\.\d mi", t) and "about 3 min walk" in t and "Directions" in t and "Call" in t and "Add to plan" in t
    assert "Closed now" in one_card(r.text, "Night Owl") and "Hours unknown" in one_card(r.text, "Hours Unknown Deli")
    assert 'href="tel:+13105550142"' in card
    assert "tel:" not in one_card(r.text, "Plant Cafe")              # no phone, no Call
    assert "rating" in r.text.lower() and "no ratings" in r.text      # says there are none; never invents one
    assert not re.search(r"\d\.\d ?(stars?|/5)|★", visible(r.text))
    q = world.overpass[0]
    assert '"diet:vegetarian"~"^(yes|only)$"' in q and "(around:1500,34.01,-118.49)" in q


def test_directions_go_to_apple_maps_on_an_iphone_and_google_elsewhere_with_the_place_not_the_person(client, world):
    imported(client)
    g = one_card(search(client).text, "Green Bowl")
    href = tag_href(g, "ar-dir")
    assert href.startswith("https://www.google.com/maps/search/?api=1&query=Green%20Bowl%2034.01200")
    r = client.post("/trip/map/around", data={"cat": "veg", "mode": "walk", "day": "1", "lat": "34.01", "lon": "-118.49"}, headers=IPHONE)
    a = tag_href(one_card(r.text, "Green Bowl"), "ar-dir")
    assert a.startswith("https://maps.apple.com/?q=Green%20Bowl&ll=34.01200,-118.49000")
    assert "34.0100,-118.4900" not in a                                 # the place's position, not the person's


def test_the_drive_range_is_wider_and_says_minutes_by_car(client, world):
    imported(client)
    r = search(client, mode="drive")
    assert "(around:8000," in world.overpass[0] and "min drive" in r.text and "about 5 miles by car" not in r.text


def test_every_chip_works_and_nothing_found_says_so(client, world):
    imported(client)
    world.els[:] = []
    for cat in around.CATEGORIES:
        r = search(client, cat=cat)
        assert r.status_code == 200 and 'id="ar-empty"' in r.text and "Nothing found" in r.text, cat
    assert len(world.overpass) == 7


def test_a_bad_chip_is_refused_and_a_failing_service_is_one_sentence(client, world, monkeypatch):
    imported(client)
    assert search(client, cat="nope").status_code == 422
    monkeypatch.setattr(geo, "fetch", lambda url, timeout=0: (_ for _ in ()).throw(OSError("down")) if "overpass" in url else world(url, timeout))
    r = search(client, cat="gas")
    assert r.status_code == 503 and around.NO_PLACES in r.text and "down" not in r.text


def test_signed_out_gets_a_plain_401(client, world):
    assert search(client).status_code == 401


# ---- where you are -------------------------------------------------------------------------------------------------------

def test_if_the_phone_will_not_say_the_hotel_is_used_and_the_page_says_so(client, world):
    imported(client)
    r = search(client, lat=None, lon=None, denied="1", day="0")
    t = " ".join(visible(r.text).split())
    assert "we couldn’t use your location" in t.lower() or "couldn't use your location" in t.lower()
    assert "near The Example Hotel Santa Monica, your hotel tonight." in t
    assert cards(r.text)
    assert "(around:1500,34.01,-118.49)" in world.overpass[0]


def test_with_no_position_and_nothing_on_the_map_for_the_day_it_asks_for_the_location(client, world, monkeypatch):
    imported(client)
    monkeypatch.setattr(geo, "fetch", lambda url, timeout=0: [] if "nominatim" in url else (_ for _ in ()).throw(OSError("down")))
    r = search(client, lat=None, lon=None, day="2")                    # a free day: nothing to place, and the geocoder knows nothing
    assert r.status_code == 503 and "can’t tell where you are" in r.text and "Allow your location" in r.text


def test_a_bad_position_is_ignored_not_trusted(client, world):
    imported(client)
    r = search(client, lat="999", lon="abc", day="0")
    assert r.status_code == 200 and "The Example Hotel" in visible(r.text)


def test_the_position_is_not_kept(client, world, monkeypatch):
    imported(client)
    sent = []
    real = geo.fetch
    monkeypatch.setattr(geo, "fetch", lambda url, timeout=0: (sent.append(url), real(url, timeout))[1])
    search(client, lat=34.01234, lon=-118.49876)
    assert all("34.01234" not in unquote(u) and "118.49876" not in unquote(u) for u in sent)      # the service gets it rounded
    from gitaway import familydb
    from tests.test_signin import person
    p = person("ari")
    with familydb.using(p) as db:
        for t in familydb.rows(db, "SELECT name FROM sqlite_master WHERE type='table'"):
            dump = json.dumps([dict(r) for r in familydb.rows(db, f'SELECT * FROM "{t["name"]}"')], default=str)
            assert "34.01234" not in dump and "118.49876" not in dump, t["name"]
    assert "34.01234" not in json.dumps(ai.usage_rows(), default=str)


# ---- the food preference -------------------------------------------------------------------------------------------------

def test_with_the_preference_on_only_places_that_serve_vegetarian_food_are_asked_for(client, world):
    imported(client)
    search(client)
    assert "limited" in world.overpass[0]                  # off: places with some vegetarian dishes are listed too
    client.post("/family/food", data={"vegetarian": "1"})
    around.clear_cache()
    search(client)
    assert "limited" not in world.overpass[1] and "only" in world.overpass[1]


def test_the_family_page_has_the_toggle_for_editors_and_a_note_for_viewers(client, world):
    imported(client)
    page = client.get("/family").text
    assert 'id="fam-food-toggle"' in page and "Vegetarian: off" in visible(page)
    r = client.post("/family/food", data={"vegetarian": "1"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/family#fam-food"
    assert "Vegetarian: on" in visible(client.get("/family").text)
    client.post("/family/food", data={"vegetarian": "0"})
    assert "Vegetarian: off" in visible(client.get("/family").text)


# ---- the model's ranking -------------------------------------------------------------------------------------------------

def test_the_model_ranks_and_explains_and_what_it_hears_has_no_position_or_names(client, world, monkeypatch):
    imported(client)
    for k, v in (("AZURE_OPENAI_API_KEY", "k"), ("AZURE_OPENAI_ENDPOINT", "https://x.example/openai/v1"), ("AZURE_OPENAI_DEPLOYMENT", "d")):
        monkeypatch.setenv(k, v)
    heard = []

    def model(url, headers, body, timeout):
        heard.append(body.decode())
        picks = [{"id": 1, "why": "Fully vegetarian and open"}, {"id": 77, "why": "not on the list"}]
        return 200, json.dumps({"choices": [{"message": {"content": json.dumps({"picks": picks})}}], "usage": {"prompt_tokens": 10, "completion_tokens": 5}})
    monkeypatch.setattr(ai, "TRANSPORT", model)
    r = search(client)
    assert "Fully vegetarian and open" in r.text and "GitAway’s assistant" in r.text
    assert "34.01" not in heard[0] and "118.49" not in heard[0] and "Ari" not in heard[0] and "Rivera" not in heard[0]
    assert ai.usage_rows()[-1]["job"] == "around-you" and ai.usage_rows()[-1]["ok"] == 1


def test_a_failing_model_still_gives_the_distance_ordered_cards(client, world, monkeypatch):
    imported(client)
    for k, v in (("AZURE_OPENAI_API_KEY", "k"), ("AZURE_OPENAI_ENDPOINT", "https://x.example/openai/v1"), ("AZURE_OPENAI_DEPLOYMENT", "d")):
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(ai, "TRANSPORT", lambda *a: (500, "x"))
    r = search(client)
    assert r.status_code == 200 and cards(r.text)[0] == "Green Bowl" and "Closest first" in r.text


# ---- Add to plan ---------------------------------------------------------------------------------------------------------

def add_href(html, name):
    return tag_href(one_card(html, name), "ar-add")


def test_add_to_plan_opens_the_calendars_add_form_with_the_name_and_the_next_free_half_hour(client, world):
    imported(client)
    plan(client, id="a1", day="1", start="12:00", end="14:00", title="Busy lunch", kind="food")
    href = add_href(search(client).text, "Green Bowl")
    u = urlparse(href)
    q = parse_qs(u.query)
    assert u.path == "/calendar" and q["add"] == ["1"] and q["title"] == ["Green Bowl"] and q["kind"] == ["food"] and q["view"] == ["days"]
    assert q["at"] == ["14:00"]                       # it is Saturday 12:40 and 12:00-14:00 is taken: the next half hour with an hour free
    form = client.get(href).text
    assert re.search(r'name="title"[^>]*value="Green Bowl"', form) and re.search(r'name="start"[^>]*value="14:00"', form) and re.search(r'name="end"[^>]*value="15:00"', form)
    assert re.search(r'name="day"', form) and 'value="food"' in form


def test_saving_that_form_adds_the_plan_writes_the_card_and_tells_the_family(client, world):
    from gitaway import familythread
    from tests.test_signin import person
    imported(client)
    href = add_href(search(client).text, "Green Bowl")
    form = client.get(href).text
    data = {"id": re.search(r'name="id" value="(a\d+)"', form).group(1), "day": "1", "start": "13:00", "end": "14:00", "title": "Green Bowl", "kind": "food"}
    r = client.post("/calendar/activities", data=data, follow_redirects=False)
    assert r.status_code == 303
    assert any(a["t"] == "Green Bowl" and a["d"] == 1 for a in stored_calendar()["a"])
    items = familythread.items(person("ari"))
    assert any(i["kind"] == "change" and "Green Bowl" in i["text"] for i in items)


def test_it_goes_through_the_calendars_own_checks(client, world):
    imported(client)
    r = client.post("/calendar/activities", data={"id": "a9", "day": "0", "start": "07:00", "end": "08:00", "title": "Green Bowl", "kind": "food"})
    assert r.status_code == 200 and stored_calendar()["a"]      # before the flight lands is fine (F-086): plans may overlap bookings
    r = client.post("/calendar/activities", data={"id": "a10", "day": "9", "start": "07:00", "end": "08:00", "title": "Nowhere", "kind": "food"})
    assert r.status_code == 409                                   # a day outside the trip is still refused


def test_a_long_name_is_cut_to_the_calendars_limit_and_a_bad_kind_is_fun(client, world):
    imported(client)
    form = client.get("/calendar?view=days&add=1&at=12:00&title=" + "x" * 80 + "&kind=hacker").text
    assert re.search(r'name="title"[^>]*value="x{40}"', form) and 'value="fun"' in form


def test_viewers_see_the_cards_but_no_add_to_plan_and_cannot_turn_the_preference_on(client, world):
    imported(client)
    mail = addr()
    invite(client, mail, "viewer")
    viewer = browser(client)
    sign_in(viewer, mail)
    r = viewer.post("/trip/map/around", data={"cat": "veg", "mode": "walk", "day": "1", "lat": "34.01", "lon": "-118.49"})
    assert r.status_code == 200 and "Green Bowl" in r.text and "Directions" in r.text and "Add to plan" not in r.text
    assert viewer.post("/family/food", data={"vegetarian": "1"}).status_code == 403
    page = viewer.get("/family").text
    assert 'id="fam-food-toggle"' not in page and "An editor can change this" in visible(page)
    assert "Closest first" in r.text


# ---- the privacy page ----------------------------------------------------------------------------------------------------

def test_the_privacy_page_says_what_overpass_and_the_model_get_for_around_you(client):
    t = " ".join(visible(client.get("/privacy").text).split())
    for p in ("OpenStreetMap Overpass", "overpass-api.de", "rounded to within about 100 metres", "kept in the server's memory for up to 30 minutes", "not linked to you", "the kind of place you tapped", "only when you tap",
              "does not store your location", "does three jobs", "When you use Around you", "your family's food preference", "the names of nearby places",
              "It never gets your location or the names of your family"):
        assert p in t, p


# ---- the limit per person ------------------------------------------------------------------------------------------------

def test_one_person_cannot_hammer_the_search(client, world, monkeypatch):
    from gitaway.pages import around_ui
    imported(client)
    t = [100.0]
    monkeypatch.setattr(around_ui, "_now", lambda: t[0])
    around_ui.LIMITS.clear()
    assert search(client).status_code == 200
    r = search(client, cat="coffee")                  # again at once: one every 2 seconds
    assert r.status_code == 429 and "one moment" in r.text.lower()
    t[0] += 2.1
    assert search(client, cat="coffee").status_code == 200
    for i in range(12):                                # ten a minute
        t[0] += 2.1
        r = search(client, cat="gas")
        if r.status_code == 429:
            break
    assert r.status_code == 429
    t[0] += 61
    assert search(client, cat="gas").status_code == 200
