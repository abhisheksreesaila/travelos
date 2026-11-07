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
    assert "Head northwest 0.9 mi" in page and "Turn left on Lake Tahoe Boulevard (US 50) 3.9 mi" in page and "Turn right on Emerald Bay Road (CA 89) 3.4 mi" in page
    go = tag(html, "id", "ck-go")
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
    assert "Flight home · Sat 26 RNO → SFO · 1:30 PM United UA 5522" in page and "Ref ••821" in page
    assert "Stay · 5 nights left Cabin near Heavenly" in page and "Ref ••936" in page
    assert "Mid-size SUV, AWD Hertz · return Sat 26 11:45 AM" in page and "Ref ••215" in page
    assert page.count("Booked on Expedia") == 3
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
    geopack.forget_failures()
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


def test_a_pack_of_an_older_form_waits_for_its_rebuild_instead_of_breaking_the_page(tahoe_trip, monkeypatch):
    """A pack built by an older version (its shapes in another form) is no pack: the page shows the map being drawn, its key no longer answers, and the next
    build replaces it (found on a live dev server: the page read the old form and failed)."""
    from gitaway import familydb
    me = person("ari")
    old = geopack.stored(me)["key"]
    with familydb.using(me) as db, familydb.transaction(db):
        familydb.run(db, "UPDATE geo_packs SET version = 1, shapes = :s", s='{"roads": [{"ref": "US 50", "name": "", "pts": [[-120.0, 39.0], [-119.9, 39.1]]}], "lakes": [], "towns": [], "borders": []}')
    monkeypatch.setattr(geopack, "TRANSPORT", lambda url, data=None, timeout=0: (_ for _ in ()).throw(OSError("offline")))
    r = tahoe_trip.get("/trip/cockpit")
    assert r.status_code == 200 and data_of(r.text)["state"] == "waiting" and data_of(r.text)["pack"] is None
    assert "Today · up next" in text(r.text)                       # the ticket does not need the pack
    assert tahoe_trip.get(f"/trip/cockpit/pack/{old}.json").status_code == 404
    geopack.forget_failures()
    monkeypatch.setattr(geopack, "TRANSPORT", tahoe.pack_transport)
    assert data_of(tahoe_trip.get("/trip/cockpit").text)["state"] == "ready" and geopack.stored(me)["version"] == geopack.VERSION
