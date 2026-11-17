"""F-284 in a real browser: "See it from above". The card sits in the opened square's hotel (here a sample square, whose card opens the recorded Hilton Los Angeles Airport), and opens a full-screen
sheet on a phone (390) and a panel on a laptop (1440). No test reaches a map service or needs a Google key: the two libraries are stubbed at their pinned addresses (a fake MapLibre and a fake
CesiumJS that count what the page does to them), and the Google key is a made-up string. What is proved here: nothing is requested before the tap, the map and the pins appear from what the server
read, closing destroys the map and gives its WebGL context back, Satellite and Photoreal appear only with a key, each open is counted by the server and "Back tomorrow" appears past the cap.
Set F284_SHOTS=1 for docs/report/f284-*.png (they show the stub's blank map; the real one is looked at on a dev server)."""
import json
import os
import re
from pathlib import Path

import pytest
from playwright.sync_api import expect
from sqlalchemy import text

from gitaway import aerial, community, gridsource, liteapi
from tests_browser.helpers import DESKTOP, PHONE
from tests_browser.test_matrixbook_sheet import BookStand, open_square  # noqa: F401
from tests_browser.test_tripmatrix import matrix, stand  # noqa: F401 (fixtures)

SHOTS = Path(__file__).resolve().parent.parent / "docs" / "report"
KEY = "AIza-test-key-not-real"

FAKE_MAPLIBRE = """
window.__av = window.__av || { maps: 0, removed: 0, lost: 0, layers: {}, sources: {}, markers: 0, markersRemoved: 0, centres: [] };
(function () {
  var A = window.__av;
  function Canvas() { this.getContext = function () { return { getExtension: function () { return { loseContext: function () { A.lost++; } }; } }; }; }
  function Map(o) {
    var self = this, h = {}, bearing = o.bearing || 0; A.maps++; A.centres.push(o.center); A.style = o.style;
    this.on = function (t, f) { (h[t] = h[t] || []).push(f); return this; };
    this.once = function (t, f) { this.on(t, f); return this; };
    setTimeout(function () { (h['style.load'] || []).forEach(function (f) { f(); }); (h['load'] || []).forEach(function (f) { f(); }); (h['render'] || []).forEach(function (f) { f(); }); }, 30);
    this.getCanvas = function () { return new Canvas(); };
    this.remove = function () { A.removed++; };
    this.resize = function () {}; this.isStyleLoaded = function () { return true; };
    this.getLayer = function (id) { return A.layers[id] || null; };
    this.addLayer = function (l) { A.layers[l.id] = l; };
    this.removeLayer = function (id) { delete A.layers[id]; };
    this.getSource = function (id) { return A.sources[id] ? { setData: function (d) { A.sources[id].data = d; } } : null; };
    this.addSource = function (id, s) { A.sources[id] = s; };
    this.setLayoutProperty = function (id, k, v) { if (A.layers[id]) A.layers[id][k] = v; };
    this.getStyle = function () { return { layers: [{ id: 'land', type: 'fill' }, { id: 'labels', type: 'symbol' }] }; };
    this.getBearing = function () { return bearing; }; this.setBearing = function (b) { bearing = b; };
    this.easeTo = function () {}; this.jumpTo = function () {}; this.fitBounds = function () {};
  }
  function Marker(o) { A.markers++; this.setLngLat = function () { return this; }; this.addTo = function () { return this; }; this.remove = function () { A.markersRemoved++; }; }
  function Bounds() { this.extend = function () { return this; }; }
  window.maplibregl = { Map: Map, Marker: Marker, LngLatBounds: Bounds };
})();
"""

FAKE_CESIUM = """
window.__av = window.__av || { maps: 0, removed: 0, lost: 0, layers: {}, sources: {}, markers: 0, markersRemoved: 0, centres: [] };
(function () {
  var A = window.__av;
  var P = { add: function () {} }, post = { addEventListener: function (n, f) { setTimeout(f, 20); }, removeEventListener: function () {} };
  function Viewer(el, o) {
    A.viewers = (A.viewers || 0) + 1; A.viewerOptions = o;
    this.scene = { skyAtmosphere: {}, globe: undefined, primitives: P, postRender: post, context: { _gl: { getExtension: function () { return { loseContext: function () { A.lost++; } }; } } },
      canvas: {}, sampleHeightMostDetailed: function (pts) { return Promise.resolve(pts.map(function () { return { height: 30 }; })); } };
    this.camera = { lookAt: function () { A.looked = (A.looked || 0) + 1; }, flyToBoundingSphere: function () {} };
    this.entities = { removeAll: function () {}, add: function (e) { A.entities = (A.entities || 0) + 1; } };
    this.destroy = function () { A.destroyed = (A.destroyed || 0) + 1; };
  }
  window.Cesium = { Viewer: Viewer, GoogleMaps: {}, Math: { toRadians: function (d) { return d * Math.PI / 180; } },
    createGooglePhotorealistic3DTileset: function (id, opts) { A.key = window.Cesium.GoogleMaps.defaultApiKey; A.tilesetOptions = opts; return Promise.resolve({ allTilesLoaded: { addEventListener: function () {} } }); },
    Cartesian3: { fromDegrees: function () { return {}; } }, Cartographic: { fromDegrees: function () { return {}; } }, Cartesian2: function () {}, BoundingSphere: function () {}, HeadingPitchRange: function () {},
    Color: { fromCssColorString: function () { return {}; }, WHITE: {} }, LabelStyle: { FILL_AND_OUTLINE: 1 },
    ScreenSpaceEventHandler: function () { this.setInputAction = function () {}; }, ScreenSpaceEventType: { LEFT_DOWN: 1, RIGHT_DOWN: 2, WHEEL: 3, PINCH_START: 4 } };
})();
"""


class Stubs:
    """The two libraries and Google's session call, answered by the test; `asked` is every request that went to a library or tile host (the page may make none before the tap)."""

    def __init__(self, page):
        self.asked = []
        page.route(re.compile(r"https://(unpkg\.com|cdn\.jsdelivr\.net|tiles\.openfreemap\.org|tile\.googleapis\.com)/.*"), self.answer)

    def answer(self, route):
        url = route.request.url
        self.asked.append(url)
        if url.endswith("maplibre-gl.js"):
            return route.fulfill(content_type="application/javascript", body=FAKE_MAPLIBRE)
        if url.endswith("Cesium.js"):
            return route.fulfill(content_type="application/javascript", body=FAKE_CESIUM)
        if "createSession" in url:
            return route.fulfill(content_type="application/json", body=json.dumps({"session": "sess-1"}))
        route.fulfill(content_type="text/css", body="")


@pytest.fixture
def sample(monkeypatch, stand):  # noqa: F811
    monkeypatch.setattr(gridsource, "SQUARE", BookStand(sample=True))
    monkeypatch.setattr(liteapi, "TRANSPORT", lambda *a: (_ for _ in ()).throw(AssertionError("LiteAPI was asked")))
    monkeypatch.setenv("GITAWAY_SHOWCASE", "1")
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "")
    monkeypatch.setattr(aerial, "SRI", {"maplibre": "", "cesium": ""})      # the stubs are not the pinned files, so their hashes would not match; test_aerial.py (unit) holds the real hashes to the pinned versions
    with community.connect() as db:
        db.conn.execute(text("DELETE FROM aerial_opens"))
        db.conn.commit()


def opened(page, viewport):
    stubs = Stubs(page)
    drawer = open_square(page, viewport)
    return stubs, drawer, drawer.locator(".dr-sampleslot .av-card")


def av(page, field):
    return page.evaluate(f"() => (window.__av || {{}}).{field}")


def shot(page, name):
    if os.environ.get("F284_SHOTS"):
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f"f284-{name}.png"))


@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["1440", "390"])
def test_nothing_loads_before_the_tap_then_the_map_and_the_pins_come_from_what_the_server_read(matrix, sample, viewport):  # noqa: F811
    page = matrix(viewport, signed_in=True)
    stubs, drawer, card = opened(page, viewport)
    expect(card).to_be_visible()
    expect(card).to_contain_text("Sample view")
    expect(card).to_contain_text("See it from above")
    assert stubs.asked == [] and av(page, "maps") is None      # not a library, not a tile before the tap
    card.click()
    sheet = page.locator(".av-sheet")
    expect(sheet).to_be_visible()
    expect(sheet.locator("#av-title")).to_have_text("Hilton Los Angeles Airport")
    expect(sheet.locator(".av-hd")).to_contain_text("Heads up: Between two flight paths · 15 car parks within 500 m")
    expect(sheet.locator(".av-hd")).to_contain_text("Landing planes pass 670 m to one side and 720 m to the other")
    pins = sheet.locator(".av-pin")
    assert pins.count() == 6
    expect(pins.nth(0)).to_contain_text("Runway 07L/25R")
    expect(pins.nth(0)).to_contain_text("11 min")
    expect(pins.nth(0)).to_contain_text("walk · 720 m")
    expect(pins.nth(3)).to_contain_text("Ralphs")
    expect(pins.nth(3)).to_contain_text("7 min")
    expect(pins.nth(3)).to_contain_text("drive · 1.9 km")
    expect(pins.nth(2)).to_be_disabled()      # no beach within 2 km: a pin with no place
    expect(sheet.locator(".av-src")).to_contain_text("Sample: a copy of OpenStreetMap saved on 16 Nov 2026")
    page.wait_for_function("() => window.__av && window.__av.maps === 1")
    assert [u for u in stubs.asked if u.endswith(".js")] == ["https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js"]      # the pinned version only, and no 3D library
    assert abs(av(page, "centres")[0][1] - 33.9461921) < 1e-6 and abs(av(page, "centres")[0][0] + 118.3816538) < 1e-6      # the server's coordinates, not the page's
    page.wait_for_function("() => window.__av.layers['av-3d']")
    assert av(page, "style").endswith("/styles/liberty") and "av-3d" in av(page, "layers") and "av-lines" in av(page, "sources")
    page.wait_for_function("() => window.__av.markers === 6")      # the hotel and the five pins that have a place
    attribution = sheet.locator(".av-attr")
    expect(attribution).to_contain_text("OpenFreeMap")
    expect(attribution).to_contain_text("© OpenStreetMap contributors")
    expect(sheet.locator(".av-seg button")).to_have_text(["Map"])      # without a Google key there is no satellite and no photoreal
    expect(card.locator(".av-l")).to_have_text("Between two flight paths · 15 car parks within 500 m")
    assert page.evaluate("() => document.body.scrollWidth <= window.innerWidth")
    shot(page, f"sheet-{viewport['width']}")


@pytest.mark.parametrize("how", ["close", "escape"])
def test_closing_destroys_the_map_gives_back_its_webgl_context_and_returns_focus_to_the_card(matrix, sample, how):  # noqa: F811
    page = matrix(PHONE, signed_in=True)
    stubs, drawer, card = opened(page, PHONE)
    card.click()
    page.wait_for_function("() => window.__av && window.__av.markers === 6")
    if how == "close":
        page.locator(".av-close").click()
    else:
        page.keyboard.press("Escape")
    expect(page.locator(".av-sheet")).to_have_count(0)
    assert (av(page, "removed"), av(page, "lost"), av(page, "markersRemoved")) == (1, 1, 6)
    assert page.evaluate("() => document.activeElement.classList.contains('av-card')") and page.evaluate("() => document.body.classList.contains('av-open')") is False
    assert page.locator(".av-scrim").count() == 0
    card.click()      # again: a new map, the same pins, nothing left over from the first
    page.wait_for_function("() => window.__av.maps === 2")
    expect(page.locator(".av-pin")).to_have_count(6)


def test_with_a_google_key_satellite_and_photoreal_are_offered_each_open_is_counted_and_back_tomorrow_comes_past_the_cap(matrix, sample, monkeypatch):  # noqa: F811
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", KEY)
    monkeypatch.setenv("GOOGLE_3D_A_DAY", "2")
    page = matrix(DESKTOP, signed_in=True)
    stubs, drawer, card = opened(page, DESKTOP)
    card.click()
    seg = page.locator(".av-seg button")
    expect(seg).to_have_text(["Map", "Satellite", "Photoreal"])
    assert "AIza" not in page.content() and aerial.opens_today() == 0      # the key is not in the page until a view asks for it, and the map view asks for nothing
    page.wait_for_function("() => window.__av && window.__av.maps === 1")
    seg.nth(1).click()      # Satellite: one open, Google's tiles over the map
    page.wait_for_function("() => window.__av.sources['google-sat']")
    tiles = av(page, "sources")["google-sat"]["tiles"][0]
    assert tiles == f"https://tile.googleapis.com/v1/2dtiles/{{z}}/{{x}}/{{y}}?session=sess-1&key={KEY}" and aerial.opens_today() == 1
    assert av(page, "layers")["av-3d"]["visibility"] == "none"      # the photo already shows the roofs
    expect(page.locator(".av-attr")).to_contain_text("Imagery © Google")
    seg.nth(0).click()
    seg.nth(1).click()      # back to Satellite in the same sheet: not counted again
    assert aerial.opens_today() == 1
    seg.nth(2).click()      # Photoreal: the second open
    page.wait_for_function("() => window.__av.viewers === 1")
    assert av(page, "key") == KEY and aerial.opens_today() == 2 and av(page, "removed") == 1      # the map was destroyed for the 3D viewer
    options = av(page, "tilesetOptions")
    assert options["cullRequestsWhileMoving"] is False and options["foveatedScreenSpaceError"] is False      # the settings that gave crisp detail while the camera moves
    assert av(page, "viewerOptions")["globe"] is False and av(page, "viewerOptions")["baseLayer"] is False
    shot(page, "photoreal-1440")
    page.locator(".av-close").click()
    expect(page.locator(".av-sheet")).to_have_count(0)
    assert av(page, "destroyed") == 1 and av(page, "lost") == 2      # the viewer destroyed and its context given back, as the map's was
    card.click()      # a new sheet asks again, and the day's two opens are spent
    page.wait_for_function("() => window.__av.maps === 2")
    page.locator(".av-seg button").nth(2).click()
    refused = page.locator(".av-msg")
    expect(refused).to_be_visible()
    expect(refused).to_contain_text("Back tomorrow")
    expect(refused).to_contain_text("The map view still works")
    assert "AIza" not in refused.inner_text() and aerial.opens_today() == 2      # a refused open is not counted and hands out no key
    expect(page.locator(".av-seg button[data-v='map']")).to_have_attribute("aria-pressed", "true")
    shot(page, "back-tomorrow-1440")


@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["1440", "390"])
def test_a_visitor_who_taps_3d_is_invited_to_sign_in_with_a_clear_button_and_no_key(matrix, sample, monkeypatch, viewport):  # noqa: F811
    """F-289 (founder 2026-11-17: "we can put a big sign in to check 3D view and immersive experience"): signed out, Photoreal shows an invitation card with one bold
    "Sign in to see it in 3D" that brings the visitor back here; no key is handed out and nothing is counted."""
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", KEY)
    page = matrix(viewport, signed_in=False)
    stubs, drawer, card = opened(page, viewport)
    card.click()
    page.locator(".av-seg button").nth(2).click()
    msg = page.locator(".av-msg")
    expect(msg).to_be_visible()
    expect(msg).to_contain_text("Fly around the hotel in 3D")
    go = msg.locator("a.av-signin")
    expect(go).to_have_text("Sign in to see it in 3D")
    assert go.get_attribute("href").startswith("/signin") and "plan" in go.get_attribute("href")
    go.scroll_into_view_if_needed()
    expect(go).to_be_visible()
    box = go.bounding_box()
    assert box and box["height"] >= 47.5
    assert "AIza" not in page.content() and aerial.opens_today() == 0
    shot(page, f"signin-3d-{viewport['width']}")
