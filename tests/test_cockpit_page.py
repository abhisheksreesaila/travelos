"""F-201: the trip cockpit's page over HTTP, on the founder's Tahoe trip (tests/tahoe.py): every day a stub that links to it, today's ticket with the leg turn by
turn, the wallet with masked references and each booking's sheet, the paper map's data and its pack (only to its own family, kept by browsers for good), and
every function of the trip one tap away. "Now" is Monday Dec 21 2026, 9:12 AM at the lake."""

import json
import re

import pytest

from gitaway import catalog, geopack
from tests import tahoe
from tests.test_calendar import tag
from tests.test_signin import person, sign_in
from tests.test_trip_canvas import bare, text


def at(monkeypatch, utc):
    monkeypatch.setattr(catalog, "now_utc", lambda: utc)
    monkeypatch.setattr(catalog, "today", lambda: utc.astimezone(catalog.TZ).date())


@pytest.fixture
def tahoe_trip(client, monkeypatch):
    monkeypatch.setattr(geopack, "TRANSPORT", tahoe.pack_transport)
    monkeypatch.setattr(geopack, "LONG_SIDE", 512)
    sign_in(client)
    tahoe.seed(client, monkeypatch)
    assert geopack.ensure(person("ari")) == "ready"
    at(monkeypatch, tahoe.NOW)
    return client


def data_of(html):
    return json.loads(re.search(r'<script type="application/json" id="ck-data">(.*?)</script>', html, re.S).group(1))


def stub(html, i):
    """One day's stub, as its HTML (up to the next stub)."""
    start = html.index(f'id="ck-stub-{i}"')
    end = html.find('id="ck-stub-', start + 10)
    return html[start:end if end > 0 else len(html)]


def test_signed_out_goes_to_sign_in_and_no_trip_to_start(client):
    assert client.get("/trip/cockpit", follow_redirects=False).headers["location"].startswith("/signin")
    sign_in(client)
    assert client.get("/trip/cockpit", follow_redirects=False).headers["location"] == "/start"


def test_the_page_is_a_gitaway_page_with_its_own_styles_and_scripts(tahoe_trip):
    html = tahoe_trip.get("/trip/cockpit").text
    assert html.index("/assets/css/tokens.css") < html.index("/assets/css/base.css") < html.index("/assets/css/cockpit.css")
    for src in ("/assets/js/wx.js", "/assets/js/paper.js", "/assets/js/cockpit.js"):
        assert src in html
    assert tag(html, "id", "ph-tab-today")["aria-current"] == "page"          # the first tab is the trip's home
    assert 'aria-current="page" class="ga-tb-link ga-tb-trip"' in html        # the top bar marks Trip


def test_every_day_is_a_stub_that_links_to_it_with_its_sky_and_times(tahoe_trip):
    html = bare(tahoe_trip.get("/trip/cockpit").text)
    assert html.count('class="ck-stub') == 8
    monday = stub(html, 2)
    assert 'class="ck-stub is-open is-today"' in monday and 'aria-current="true"' in monday
    assert 'href="/trip/cockpit?day=2"' in monday and 'data-day="2"' in monday
    first = stub(html, 0)
    assert "Fly SFO → RNO" in first and "Pick up car" in first and "Check in" in first
    assert '<span class="ck-on">United · Hertz · Stay</span>' in re.sub(r"<svg.*?</svg>", "", first)
    assert "Nothing to book" in stub(html, 3)
    assert "data-wx='{\"kind\":\"cloud\"" in first and 'data-calm="1" class="ck-temp"' in first and "(sample weather)" in first


def test_todays_ticket_says_when_to_leave_and_how_to_drive_there(tahoe_trip):
    html = bare(tahoe_trip.get("/trip/cockpit").text)
    page = text(html)
    assert "Today · up next · leave in 30 min" in page and "Snowshoe at Taylor Creek" in page
    assert "Leave 9:42 Drive 18 min Starts 10:00 Distance 8.2 mi" in page
    assert "Head northwest on Ski Run Boulevard 1 mi" in page and "Turn left on Lake Tahoe Boulevard (US 50) 3.8 mi" in page and "Turn right on Emerald Bay Road (CA 89) 3.2 mi" in page      # the router's own steps
    go = tag(html, "data-go", "1")
    assert go["href"].startswith("https://www.google.com/maps/search/?api=1&amp;query=Snowshoe+at+Taylor+Creek") and go["target"] == "_blank"
    assert tag(html, "data-open-day", "today")["href"] == "/trip/canvas?day=2"          # Today's plan: the day view with its plans, notes and chat


def test_another_days_ticket_lists_its_plan_and_opens_the_day(tahoe_trip):
    html = bare(tahoe_trip.get("/trip/cockpit?day=4").text)
    wed = stub(html, 4)
    assert 'class="ck-stub is-open"' in wed
    assert "Wed Dec 23 · Ski school at Heavenly" in text(wed) and "8:45 Ski school at Heavenly" in text(wed) and "4:00 Emerald Bay sunset" in text(wed)
    assert tag(wed, "data-open-day", "4")["href"] == "/trip/canvas?day=4"
    panels = {m.group(1): "hidden" in m.group(0) for m in re.finditer(r'<div[^>]*data-day="(\d)"[^>]*class="ck-tk"[^>]*>', html)}
    assert len(panels) == 8 and panels["4"] is False and all(panels[k] for k in panels if k != "4")    # the phone's ticket shows that day, the others hidden


def test_the_wallet_shows_passes_with_masked_references_and_never_the_whole_number(tahoe_trip):
    html = bare(tahoe_trip.get("/trip/cockpit").text)
    page = text(html)
    assert "Flight home · Sat 26 RNO → SFO · 1:30 PM United UA 5522" in page and "Ref ••21" in page
    assert "Stay · 5 nights left Cabin near Heavenly" in page and "Ref ••936" in page
    assert "Mid-size SUV, AWD Hertz · return Sat 26 11:45 AM" in page and "Ref ••215" in page
    assert "Booked on" not in page and page.count("Booked Ref") == 3          # no partner is known per booking yet (F-198): just "Booked"
    assert 'href="/trip/canvas?day=7&amp;booked=b-back" class="ck-cxl"' in html        # Details: the booking's own sheet (the number behind a tap, phone, address)
    for whole in ("KQ7821", "VR4821936", "H77418215"):
        assert whole not in html


def test_the_map_data_is_in_the_page_and_the_pack_is_named_by_its_build(tahoe_trip):
    html = tahoe_trip.get("/trip/cockpit").text
    d = data_of(html)
    row = geopack.stored(person("ari"))
    assert d["state"] == "ready" and d["pack"]["key"] == row["key"] and d["open"] == 2
    assert d["pack"]["light"] == f"/trip/cockpit/pack/{row['key']}-light.webp" and d["pack"]["shapes"] == f"/trip/cockpit/pack/{row['key']}.json"
    assert len(d["days"]) == 8 and d["days"][2]["min"] == 18 and len(d["days"][2]["route"]) > 10
    assert set(d["icons"]) >= {"plane", "bed", "car", "tree"} and d["box"] == list(geopack.parse_box(row["box"]))
    assert 'id="ck-open-map"' in html and "Open map" in html


def test_the_pack_is_served_to_its_own_family_and_kept_for_good(tahoe_trip, client):
    key = geopack.stored(person("ari"))["key"]
    shapes = tahoe_trip.get(f"/trip/cockpit/pack/{key}.json")
    assert shapes.status_code == 200 and shapes.json()["lakes"][0]["name"] == "Lake Tahoe"
    assert shapes.headers["cache-control"] == "private, max-age=31536000, immutable"
    for mode in ("light", "dark"):
        img = tahoe_trip.get(f"/trip/cockpit/pack/{key}-{mode}.webp")
        assert img.status_code == 200 and img.headers["content-type"] == "image/webp" and img.content[8:12] == b"WEBP"
    assert tahoe_trip.get("/trip/cockpit/pack/0123456789abcdef.json").status_code == 404
    assert tahoe_trip.get(f"/trip/cockpit/pack/{key}-sepia.webp").status_code == 404


def test_another_family_and_a_stranger_never_get_the_pack(tahoe_trip):
    from starlette.testclient import TestClient
    from main import app
    key = geopack.stored(person("ari"))["key"]
    stranger = TestClient(app, client=("127.0.0.1", 50000))
    assert stranger.get(f"/trip/cockpit/pack/{key}.json").status_code == 404
    sign_in(stranger, "sam")
    from tests.test_calendar import PICK
    stranger.post("/pay", data=PICK)
    assert stranger.get(f"/trip/cockpit/pack/{key}.json").status_code == 404
    assert stranger.get(f"/trip/cockpit/pack/{key}-light.webp").status_code == 404


def test_the_map_state_answers_while_a_pack_is_built(client, monkeypatch):
    sign_in(client)
    tahoe.seed(client, monkeypatch)
    at(monkeypatch, tahoe.NOW)
    html = client.get("/trip/cockpit").text          # the network is off in tests: the build fails and waits
    assert data_of(html)["state"] == "waiting" and "could not be drawn just now" in html
    later(monkeypatch, geopack.RETRY + 5)                # the failure is kept: the next try is after RETRY
    monkeypatch.setattr(geopack, "TRANSPORT", tahoe.pack_transport)
    monkeypatch.setattr(geopack, "LONG_SIDE", 512)
    m = client.get("/trip/cockpit/map")
    assert m.status_code == 200 and m.headers["cache-control"] == "no-store"
    assert m.json()["state"] == "ready" and m.json()["pack"]["key"] == geopack.stored(person("ari"))["key"]
    assert client.get("/trip/cockpit/map").json()["state"] == "ready"


def test_a_viewer_reads_the_cockpit_too(tahoe_trip, monkeypatch):
    from gitaway import access
    monkeypatch.setattr(access, "request_role", lambda: "viewer")
    html = tahoe_trip.get("/trip/cockpit").text
    assert "Snowshoe at Taylor Creek" in html and 'id="ck-week"' in html and "<form" not in html.split('id="main"')[1].split("</main>")[0]


def test_the_sample_trip_has_a_cockpit_too(client):
    from tests.test_calendar import book
    book(client)
    html = client.get("/trip/cockpit").text
    assert html.count('class="ck-stub') == 5 and 'id="ck-wallet"' in html and "Ref " not in text(html)
    assert data_of(html)["state"] in ("none", "waiting", "building")


def test_a_pack_of_an_older_form_is_never_read_and_the_trip_relinks(tahoe_trip, monkeypatch):
    """A trip linked to a pack of an older version (its shapes in another form) is not shown that pack: the page never breaks on it (found on a live dev server),
    its key no longer answers, and the trip is linked to its region's current pack, or waits for one."""
    from gitaway import familydb
    me = person("ari")
    old = geopack.stored(me)["key"]
    with familydb.using(me) as db, familydb.transaction(db):
        familydb.run(db, "UPDATE geo_packs SET version = 1, region = 'v1|old', key = 'feedfacefeedface'")
    assert geopack.stored(me) is None
    assert tahoe_trip.get("/trip/cockpit/pack/feedfacefeedface.json").status_code == 404
    r = tahoe_trip.get("/trip/cockpit")
    assert r.status_code == 200 and "Today · up next" in text(r.text)
    assert data_of(r.text)["state"] == "ready" and data_of(r.text)["pack"]["key"] == old          # relinked to the current pack of its region, nothing asked
    assert geopack.stored(me)["version"] == geopack.VERSION


def later(monkeypatch, seconds):
    from datetime import datetime, timedelta, timezone
    then = datetime.now(timezone.utc) + timedelta(seconds=seconds)
    monkeypatch.setattr(geopack, "_now", lambda: then)


def test_on_a_flight_day_todays_ticket_opens_everyones_boarding_passes(tahoe_trip, monkeypatch):
    from datetime import datetime, timezone
    at(monkeypatch, datetime(2026, 12, 26, 20, 20, tzinfo=timezone.utc))       # Saturday 12:20 PM: the car is back, the flight home is up next
    html = bare(tahoe_trip.get("/trip/cockpit").text)
    passes = tag(html, "data-passes", "1")
    assert passes and passes["href"] == "/trip/canvas?day=7&amp;booked=b-back"     # the flight's sheet: every traveller's pass, the gate view
    assert "Boarding passes" in html
    at(monkeypatch, tahoe.NOW)
    assert 'data-passes="1"' not in tahoe_trip.get("/trip/cockpit").text           # not on a day without a flight


# ---- review fixes (F-201 review) ----------------------------------------------------------------------------------------

def test_a_day_that_is_a_digit_but_not_a_number_opens_today(tahoe_trip):
    r = tahoe_trip.get("/trip/cockpit?day=%C2%B2")          # "²" is a digit to str.isdigit() but not to int()
    assert r.status_code == 200 and 'data-open="2"' in r.text


def test_the_page_data_survives_a_plan_title_with_markup(tahoe_trip):
    from gitaway import tripcal as cal
    cal.add_activity(person("ari"), day=3, start=13 * 60, end=14 * 60, title="Lunch <!--<script> in town", kind="food")
    html = tahoe_trip.get("/trip/cockpit").text
    raw = re.search(r'<script type="application/json" id="ck-data">(.*?)</script>', html, re.S).group(1)
    assert "<" not in raw and ">" not in raw and "&" not in raw                 # nothing in the data can end the script or open a comment
    assert json.loads(raw)["open"] == 2


def test_every_id_the_cockpit_draws_is_unique(tahoe_trip):
    """The cockpit's own ids (the top bar's trip menu, drawn once for the laptop and once in a phone's heading, is the shell's: the canvas draws it the same way)."""
    html = tahoe_trip.get("/trip/cockpit").text
    ids = [i for i in re.findall(r'\sid="([^"]+)"', html) if not i.startswith("ga-tb-")]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    assert dupes == [] and "ck-week" in ids


def test_the_eyebrow_names_the_family_not_the_viewer(tahoe_trip):
    from gitaway import members
    page = text(tahoe_trip.get("/trip/cockpit").text)
    label = members.family_label(person("ari")["tenant_id"])
    assert f"{label} · day 3 of 8" in page and label != "A family"


def test_a_pass_says_booked_with_no_trip_wide_partner(tahoe_trip):
    page = text(tahoe_trip.get("/trip/cockpit").text)
    assert "Booked on" not in page and page.count("Booked ") >= 3       # the trip's one "booked on" is not the airline's or the car company's


def test_open_map_is_not_offered_while_no_place_is_known(client, monkeypatch):
    sign_in(client)
    tahoe.seed(client, monkeypatch, maps=False)
    html = client.get("/trip/cockpit").text
    button = re.search(r'<button[^>]*id="ck-open-map"[^>]*>', html).group(0)
    assert data_of(html)["state"] == "none" and re.search(r"\shidden[\s>]", button)      # drawn hidden: it shows when a place arrives (the map asks again)


def test_a_six_road_route_shows_three_steps_and_the_rest_behind_more(tahoe_trip):
    """Wherever the ticket cuts the steps it says "+N more", and the rest open in place (a details element: keyboard and screen readers, no script)."""
    from gitaway import familydb, geo
    six = [{"k": "depart", "d": "", "n": "Ski Run Boulevard", "r": "", "m": 1600, "b": 331}, {"k": "turn", "d": "left", "n": "Lake Tahoe Boulevard", "r": "US 50", "m": 2000},
           {"k": "turn", "d": "right", "n": "Tahoe Keys Boulevard", "r": "", "m": 900}, {"k": "turn", "d": "left", "n": "Venice Drive", "r": "", "m": 700},
           {"k": "turn", "d": "right", "n": "Emerald Bay Road", "r": "CA 89", "m": 4100}, {"k": "turn", "d": "slight right", "n": "Taylor Creek Road", "r": "", "m": 400},
           {"k": "arrive", "d": "", "n": "", "r": "", "m": 0}]
    me = person("ari")
    with familydb.using(me) as db:
        cabin, taylor = geo.state(tahoe.HOTEL, db)[0], geo.state("Snowshoe at Taylor Creek, South Lake Tahoe", db)[0]
        leg = json.loads(geo._get(db, "drive", geo._pair_key(cabin, taylor))["data"])
        geo._put(db, "drive", geo._pair_key(cabin, taylor), data=json.dumps({**leg, "s": six}))
    html = bare(tahoe_trip.get("/trip/cockpit").text)
    monday = stub(html, 2)
    shown = re.search(r'<ol[^>]*class="ck-legs"[^>]*>(.*?)</ol>', monday, re.S).group(1)
    assert shown.count('class="ck-lg"') == 3
    more = re.search(r'<details class="ck-more"><summary[^>]*>(.*?)</summary>(.*?)</details>', monday, re.S)
    assert more and "+3 more" in text(more.group(1)) and more.group(2).count('class="ck-lg"') == 3
    assert "Turn left on Venice Drive" in text(more.group(2)) and "Bear right onto Taylor Creek Road" in text(more.group(2))


def test_a_busy_day_says_how_many_more_it_has(tahoe_trip):
    from gitaway import tripcal as cal
    me = person("ari")
    for h, title in ((14, "Hot chocolate"), (16, "Tubing"), (20, "Movie night")):
        cal.add_activity(me, day=2, start=h * 60, end=h * 60 + 45, title=title, kind="fun")
    tue = stub(bare(tahoe_trip.get("/trip/cockpit").text), 2)
    assert '<li class="ck-more ck-more3">+2 more</li>' in tue and '<li class="ck-more ck-more2">+3 more</li>' in tue      # 3 shown on a laptop, 2 on a phone


def test_the_map_state_brings_each_days_stops_and_drive_so_late_places_appear(client, monkeypatch):
    """The page asks again while there is no pack or no place yet; the answer carries every day's stops and drive line, so places that arrive after the page
    loaded show up without a reload."""
    sign_in(client)
    tahoe.seed(client, monkeypatch, maps=False)
    at(monkeypatch, tahoe.NOW)
    assert client.get("/trip/cockpit/map").json()["state"] == "none"
    from gitaway import familydb, geo, tripgeo
    monkeypatch.setattr(geo, "fetch", tahoe.geo_fetch)
    me = person("ari")
    with familydb.using(me) as db:
        for group in tripgeo.day_places(me):
            geo.warm(db, group, budget=30)
    monkeypatch.setattr(geopack, "TRANSPORT", tahoe.pack_transport)
    monkeypatch.setattr(geopack, "LONG_SIDE", 512)
    m = client.get("/trip/cockpit/map").json()
    assert m["state"] == "ready" and len(m["days"]) == 8
    assert [s["label"] for s in m["days"][2]["stops"]] == ["Stay", "Snowshoe at Taylor Creek"] and m["days"][2]["min"] == 18 and m["days"][2]["route"]


def test_the_map_credits_its_sources_with_links(tahoe_trip):
    html = tahoe_trip.get("/trip/cockpit").text
    osm = re.findall(r'<a[^>]*href="https://www.openstreetmap.org/copyright"[^>]*>([^<]*)</a>', html)
    terrain = re.findall(r'<a[^>]*href="https://github.com/tilezen/joerd/blob/master/docs/attribution.md"[^>]*>([^<]*)</a>', html)
    assert osm and all(t == "© OpenStreetMap contributors" for t in osm)           # the laptop's caption and the phone's line under the map
    assert terrain and all("USGS" in t for t in terrain)
    privacy = text(tahoe_trip.get("/privacy").text)
    assert "s3.amazonaws.com (elevation-tiles-prod)" in privacy and "USGS" in privacy and "OpenStreetMap contributors" in privacy
    assert "jsdelivr" not in privacy.lower()                                       # the street map's library is this site's own copy now


def test_the_street_maps_library_is_this_sites_pinned_copy_of_maplibre():
    """MapLibre GL JS 5.24.0 is served from /assets/vendor (no CDN in the privacy list), and the page pins it by the hash of those exact files: recomputed here
    from the files themselves, and equal to the hashes jsDelivr serves for maplibre-gl@5.24.0."""
    import base64
    import hashlib
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    js = (root / "assets" / "js" / "cockpit.js").read_text()
    assert "'/assets/vendor/maplibre-gl-5.24.0/'" in js and "jsdelivr" not in js
    upstream = {"maplibre-gl.js": "sha384-5+cfbwT0iiub6VsQAdn6yz16nr6sDiQoHx6tm4O8OVYXHYOxcffFmCJBL0dgdvGp",
                "maplibre-gl.css": "sha384-uTttxo/aOKbdE5RlD/SPzSDoDmNvGlUYPjONi2MN/b7c9HPSvW07OIuyP7uL6jxK"}
    for name, pinned in upstream.items():
        body = (root / "assets" / "vendor" / "maplibre-gl-5.24.0" / name).read_bytes()
        assert "sha384-" + base64.b64encode(hashlib.sha384(body).digest()).decode() == pinned and pinned in js
    assert b"MapLibre GL JS" in (root / "assets" / "vendor" / "maplibre-gl-5.24.0" / "maplibre-gl.js").read_bytes()[:200]      # its licence header is kept


@pytest.mark.parametrize("day", ["", "4"])
def test_no_id_is_used_twice_on_the_page(tahoe_trip, day):
    from collections import Counter
    html = tahoe_trip.get(f"/trip/cockpit?day={day}").text
    twice = [i for i, n in Counter(re.findall(r'\sid="([^"]+)"', html)).items() if n > 1]
    assert twice == [], twice
