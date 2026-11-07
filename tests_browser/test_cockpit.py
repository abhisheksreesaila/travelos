"""F-201: the trip cockpit in a real browser, on the founder's Tahoe trip (tests_browser/cockpit_support.py), at 390 and 1440 (and 1280x800), light and dark (dark: the
shared tokens with Direction A's dark values injected, as F-200 will ship them): no sideways scroll, the desktop fits the window, phone targets of at least 48px,
a tap on a day opens its ticket and re-flies the paper map, the map works offline once loaded, the street map loads only when asked, and the motion is the
phone's Liquid (GA.motion grows the ticket out of the stub), the desktop's calm fade, and a fade under reduced motion.
Screenshots: F201_SHOTS=<folder> pixi run pytest -p no:randomly tests_browser/test_cockpit.py -k screenshots"""

import os
import re

import pytest

from tests_browser.cockpit_support import open_cockpit
from tests_browser.helpers import DESKTOP, PHONE

LAPTOP = {"width": 1280, "height": 800}
MODES = [(PHONE, False), (PHONE, True), (DESKTOP, False), (DESKTOP, True)]
IDS = ["390-light", "390-dark", "1440-light", "1440-dark"]


@pytest.fixture
def ctxs():
    made = []
    yield made
    for c in made:
        c.set_offline(False)
        c.close()


@pytest.fixture
def cockpit(browser, base_url, monkeypatch, ctxs):
    def make(viewport=DESKTOP, **kw):
        return open_cockpit(browser, base_url, monkeypatch, ctxs, viewport=viewport, **kw)
    return make


def plane(page):
    return page.evaluate("() => getComputedStyle(document.querySelector('.pp-plane')).transform")


def labels(page):
    return page.evaluate("() => [...document.querySelectorAll('.pp-tags .pp-lbl')].map(l => l.textContent)")


# ---- the layout ---------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("viewport,dark", MODES, ids=IDS)
def test_no_sideways_scroll_in_either_mode(cockpit, viewport, dark):
    page = cockpit(viewport, dark=dark)
    sw, cw = page.evaluate("() => [document.documentElement.scrollWidth, document.documentElement.clientWidth]")
    assert sw <= cw, (sw, cw)
    assert page.locator(".ck-stub").count() == 8


@pytest.mark.parametrize("viewport", [DESKTOP, LAPTOP], ids=["1440x900", "1280x800"])
def test_the_desktop_fits_the_window_and_the_open_ticket_fits_its_stub(cockpit, viewport):
    page = cockpit(viewport)
    got = page.evaluate("""() => { const open = document.querySelector('.ck-stub.is-open'), r = open.getBoundingClientRect(), acts = open.querySelector('.ck-open .ck-acts').getBoundingClientRect();
      const week = document.querySelector('.ck-week').getBoundingClientRect(), wallet = document.querySelector('.ck-wallet').getBoundingClientRect();
      const overflow = [...document.querySelectorAll('.ck-stub:not(.is-open) .ck-closed, .ck-pass')].filter(n => n.scrollHeight > n.clientHeight + 1).length;
      return { page: document.documentElement.scrollHeight, inner: innerHeight, stubBottom: r.bottom, actsBottom: acts.bottom, weekBottom: week.bottom, walletBottom: wallet.bottom, overflow }; }""")
    assert got["page"] <= got["inner"] + 1, got                         # no page scroll: everything fits 1440x900 and 1280x800
    assert got["actsBottom"] <= got["stubBottom"] + 0.5, got            # Start directions is inside today's ticket
    assert got["weekBottom"] <= got["inner"] and got["walletBottom"] <= got["inner"]
    assert got["overflow"] == 0, got                                    # no stub or pass cuts its words off


def test_phone_targets_are_at_least_48px(cockpit):
    page = cockpit(PHONE)
    small = page.evaluate("""() => [...document.querySelectorAll('#main a, #main button, #main summary')].filter(n => {
        const r = n.getBoundingClientRect(), shut = n.closest('details:not([open])');
        return r.width > 0 && r.height > 0 && getComputedStyle(n).visibility !== 'hidden' && n.closest('[hidden]') === null && (!shut || n.tagName === 'SUMMARY') && (r.width < 47.5 || r.height < 47.5);
      }).map(n => (n.className || n.tagName) + ' ' + n.textContent.trim().slice(0, 30) + ' ' + Math.round(n.getBoundingClientRect().width) + 'x' + Math.round(n.getBoundingClientRect().height))""")
    assert small == [], small


@pytest.mark.parametrize("viewport,dark", MODES, ids=IDS)
def test_text_keeps_its_contrast_in_light_and_dark(cockpit, viewport, dark):
    page = cockpit(viewport, dark=dark)
    worst = page.evaluate("""() => {
      const rgb = (c) => { const v = (c.match(/[\\d.]+/g) || []).map(Number); return /^color\\(srgb/.test(c) ? [v[0] * 255, v[1] * 255, v[2] * 255, v.length > 3 ? v[3] : 1] : v.slice(0, 4); };      // color-mix() computes to color(srgb r g b)
      const lum = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
      const bg = (n) => {      // the colour behind the text: translucent fills composited over the first opaque one under them (a 20% white over a kind fill is not the kind fill)
        const layers = [];
        while (n) { const c = rgb(getComputedStyle(n).backgroundColor); if (c.length >= 3) { const a = c.length > 3 ? c[3] : 1; if (a > 0) layers.push([c[0], c[1], c[2], a]); if (a >= 0.99) break; } n = n.parentElement; }
        let out = [255, 255, 255];
        for (const [r, g, b, a] of layers.reverse()) out = [r * a + out[0] * (1 - a), g * a + out[1] * (1 - a), b * a + out[2] * (1 - a)];
        return out; };
      const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
      const picks = '.ck-eyebrow, .ck-title, .ck-d b, .ck-d span, .ck-it b, .ck-t, .ck-up-t, .ck-kv dt, .ck-kv dd, .ck-lg-t, .ck-lg-d, .ck-pass-t, .ck-pass-s, .ck-bo, .ck-ref, .ck-chip, .ck-free, .ck-on, .ck-cxl, .ck-p-b em, .ck-p-b b, .ck-more, .ck-more-s, .ck-tag, .ck-cap a, .ck-credits a';
      return [...document.querySelectorAll(picks)].filter(n => n.getBoundingClientRect().width > 0 && !n.closest('[hidden]') && !n.closest('.ck-sky'))
        .map(n => [ratio(rgb(getComputedStyle(n).color), bg(n)), n.className + ' ' + n.textContent.trim().slice(0, 24)]).sort((a, b) => a[0] - b[0]).slice(0, 3); }""")
    assert worst[0][0] >= 4.5, worst


def test_dark_follows_the_page_with_the_dark_relief_and_water(cockpit):
    page = cockpit(DESKTOP, dark=True)
    assert page.locator("#ck-paper[data-dark]").count() == 1
    assert page.evaluate("() => document.querySelector('.pp-relief').getAttribute('href')").endswith("-dark.webp")
    light = cockpit(DESKTOP)
    assert light.locator("#ck-paper[data-dark]").count() == 0
    assert light.evaluate("() => document.querySelector('.pp-relief').getAttribute('href')").endswith("-light.webp")


# ---- a tap on a day -----------------------------------------------------------------------------------------------------

def test_tapping_a_day_on_the_desktop_opens_its_ticket_and_reflies_the_map(cockpit):
    page = cockpit(DESKTOP)
    page.evaluate("() => { window.__same = 1; }")
    before = plane(page)
    assert "Snowshoe at Taylor Creek" in " ".join(labels(page))
    page.locator("#ck-stub-4 .ck-hit").click()
    page.wait_for_function("() => document.querySelector('#ck-paper').dataset.day === '4'")
    assert page.locator("#ck-stub-4.is-open").count() == 1 and page.locator("#ck-stub-2.is-open").count() == 0
    assert page.locator("#ck-stub-4 .ck-open").is_visible() and not page.locator("#ck-stub-2 .ck-open").is_visible()
    assert plane(page) != before
    assert any("Emerald Bay sunset" in t for t in labels(page)) and not any("Taylor Creek" in t for t in labels(page))
    assert re.search(r"/trip/cockpit\?day=4", page.url) and page.evaluate("() => window.__same") == 1      # no page load: the address follows in place
    page.locator("#ck-stub-2 .ck-hit").click()
    page.wait_for_function("() => document.querySelector('#ck-paper').dataset.day === '2'")
    assert plane(page) == before


def test_tapping_a_day_on_the_phone_shows_its_ticket_and_reflies_the_map(cockpit):
    page = cockpit(PHONE)
    before = plane(page)
    assert page.locator('.ck-tk[data-day="2"]').is_visible()
    page.locator("#ck-stub-5 .ck-hit").scroll_into_view_if_needed()
    page.locator("#ck-stub-5 .ck-hit").click()
    page.wait_for_function("() => document.querySelector('#ck-paper').dataset.day === '5'")
    assert page.locator('.ck-tk[data-day="5"]').is_visible() and not page.locator('.ck-tk[data-day="2"]').is_visible()
    assert "Thu Dec 24 · Heavenly Gondola" in page.locator('.ck-tk[data-day="5"]').text_content()
    assert page.locator("#ck-ticket .ck-temp").inner_text() == page.locator('.ck-tk[data-day="5"]').get_attribute("data-temp")
    assert plane(page) != before and any("Heavenly Gondola" in t for t in labels(page))
    assert page.locator("#ck-stub-5.is-open").count() == 1


def test_open_the_day_reaches_the_plans_and_today_reaches_the_day_view(cockpit, base_url):
    page = cockpit(DESKTOP)
    page.locator("#ck-stub-4 .ck-hit").click()
    page.locator('#ck-stub-4 [data-open-day="4"]').click()
    page.wait_for_url(re.compile(r"/trip/canvas\?day=4"))
    page.wait_for_selector("#cz")
    page.go_back()
    page.wait_for_selector("#ck-week")


# ---- the map: offline once loaded; the street map only when asked ----------------------------------------------------------

def test_the_paper_map_works_offline_once_loaded(browser, base_url, monkeypatch, ctxs):
    from tests_browser.cockpit_support import seed
    ctx = browser.new_context(viewport=DESKTOP, service_workers="allow", reduced_motion="reduce")
    ctx.set_default_timeout(15000)
    ctxs.append(ctx)
    seed(base_url, ctx, monkeypatch)
    page = ctx.new_page()
    page.goto(f"{base_url}/community")
    page.evaluate("navigator.serviceWorker.ready.then(() => true)")
    page.reload()
    page.wait_for_function("navigator.serviceWorker.controller !== null")
    page.goto(f"{base_url}/trip/cockpit")
    page.wait_for_selector("#ck-paper[data-ready='1']")
    page.wait_for_function("() => [...document.querySelectorAll('img, image')].length > 0")
    page.wait_for_timeout(800)            # the worker saves the page and the pack after answering
    ctx.set_offline(True)
    page.reload()
    page.wait_for_selector("#ck-paper[data-ready='1']")
    loaded = page.evaluate("""() => new Promise(done => { const href = document.querySelector('.pp-relief').getAttribute('href'); const img = new Image();
      img.onload = () => done([img.naturalWidth, href]); img.onerror = () => done([0, href]); img.src = href; })""")
    assert loaded[0] > 100, loaded                                       # the relief came from the worker's cache
    assert page.evaluate("() => document.querySelectorAll('.pp-lake').length") > 0          # and the shapes
    page.locator("#ck-stub-4 .ck-hit").click()
    page.wait_for_function("() => document.querySelector('#ck-paper').dataset.day === '4'")       # a tap still re-flies it


FAKE_LIBRE = """window.__libre = { maps: [], controls: [] };
window.maplibregl = { Map: function (o) { window.__libre.maps.push(o); var self = this; this.on = function (ev, fn) { if (ev === 'load') setTimeout(fn, 10); return self; };
  this.addSource = function () {}; this.addLayer = function (l) { (window.__libre.layers = window.__libre.layers || []).push(l.id); }; this.remove = function () { window.__libre.removed = true; };
  this.loaded = function () { return true; }; this.addControl = function (c, where) { window.__libre.controls.push([c.kind, where]); return self; }; },
  NavigationControl: function (o) { this.kind = 'nav:' + (o && o.showCompass === false ? 'zoom' : 'all'); },
  Marker: function () { var m = this; this.setLngLat = function () { return m; }; this.addTo = function () { window.__libre.markers = (window.__libre.markers || 0) + 1; return m; }; } };"""
VENDOR = "/assets/vendor/maplibre-gl-5.24.0/"


def test_open_map_loads_the_street_map_only_when_tapped_from_this_site(cockpit):
    page = cockpit(DESKTOP, sw="block")          # (the service worker would answer /assets/ itself, past page.route)
    asked = []
    page.route(f"**{VENDOR}**", lambda route: (asked.append(route.request.url), route.fulfill(status=200, content_type="application/javascript" if route.request.url.split("?")[0].endswith(".js") else "text/css",
                                                                                               body=FAKE_LIBRE if route.request.url.split("?")[0].endswith(".js") else "")))
    page.wait_for_timeout(300)
    assert asked == [] and page.evaluate("() => typeof window.maplibregl") == "undefined"          # nothing until asked
    page.evaluate("() => { GA.cockpit.libre.js = ''; GA.cockpit.libre.css = ''; }")                # (the stand-in library has no pinned hash: the real file's is checked in tests/test_cockpit_page.py)
    page.locator("#ck-open-map").click()
    page.wait_for_function("() => window.__libre && window.__libre.maps.length === 1")
    assert any(u.split("?")[0].endswith(VENDOR + "maplibre-gl.js") for u in asked)                    # from this site, not a CDN
    opts = page.evaluate("() => window.__libre.maps[0]")
    assert opts["style"] == "https://tiles.openfreemap.org/styles/positron" and opts["container"] == "ck-street"
    page.wait_for_function("() => (window.__libre.layers || []).includes('ck-route')")
    assert page.evaluate("() => window.__libre.controls") == [["nav:zoom", "top-right"]]               # + and - for a finger or a mouse
    assert page.locator("#ck-sheet .ck-sheet-box[role=dialog][aria-modal=true]").count() == 1 and page.locator("#ck-sheet").is_visible()
    assert page.evaluate("() => getComputedStyle(document.documentElement).overflow + ' ' + getComputedStyle(document.body).overflow") == "hidden hidden"     # the page behind does not scroll
    page.keyboard.press("Tab")
    page.keyboard.press("Tab")
    assert page.evaluate("() => !!document.activeElement.closest('#ck-sheet')")                    # the focus stays in the dialog
    page.keyboard.press("Escape")
    page.wait_for_function("() => document.getElementById('ck-sheet').hidden")
    assert page.evaluate("() => document.activeElement.id") == "ck-open-map"
    assert page.evaluate("() => getComputedStyle(document.body).overflow") != "hidden"


def test_open_map_without_a_connection_says_the_paper_map_still_works(cockpit):
    page = cockpit(PHONE, sw="block")
    page.route(f"**{VENDOR}**", lambda route: route.abort())
    page.evaluate("() => { new MutationObserver(() => { const s = document.getElementById('ck-libre'); if (s) window.__sri = s.integrity; }).observe(document.head, { childList: true }); }")
    page.locator("#ck-open-map").click()
    page.wait_for_function("() => /needs a connection/.test(document.getElementById('ck-street-msg').textContent)")
    assert page.evaluate("() => window.__sri") == "sha384-5+cfbwT0iiub6VsQAdn6yz16nr6sDiQoHx6tm4O8OVYXHYOxcffFmCJBL0dgdvGp"      # the vendored file is pinned by its hash too
    page.locator("#ck-sheet .ck-x").click()
    page.wait_for_function("() => document.getElementById('ck-sheet').hidden")


# ---- motion ---------------------------------------------------------------------------------------------------------------

MOVES = """() => GA.motion.log.slice(-4).map(m => ({ kind: m.kind, calm: !!m.calm, dur: m.dur, easing: m.easing }))"""


def test_the_phone_grows_the_ticket_out_of_the_stub_on_the_spring(cockpit):
    page = cockpit(PHONE, motion=True)
    page.locator("#ck-ticket").scroll_into_view_if_needed()
    page.evaluate("() => { GA.motion.log.length = 0; }")
    page.evaluate("() => GA.cockpit.select(3, document.getElementById('ck-stub-3'))")
    moves = page.evaluate(MOVES)
    assert moves and moves[-1]["kind"] == "open" and not moves[-1]["calm"], moves
    spring = page.evaluate("() => getComputedStyle(document.documentElement).getPropertyValue('--motion-spring').trim()")
    assert moves[-1]["easing"] == spring and moves[-1]["dur"] == page.evaluate("() => GA.motion.t('spring')")
    tr = page.evaluate("() => getComputedStyle(document.querySelector('.pp-plane')).transitionTimingFunction")
    assert tr.startswith("cubic-bezier(0.3, 1.12")          # the map flies on the spring token too


def test_the_desktop_is_the_calm_fade_and_the_map_eases_without_overshoot(cockpit):
    page = cockpit(DESKTOP, motion=True)
    page.evaluate("() => { GA.motion.log.length = 0; }")
    page.locator("#ck-stub-5 .ck-hit").click()
    moves = page.evaluate(MOVES)
    assert moves and all(m["calm"] for m in moves), moves                      # only GA.motion's desk fade
    running = page.evaluate("""() => document.getAnimations().filter(a => a.playState === 'running').map(a => [a.effect.target.className, a.transitionProperty || a.animationName || 'js',
      (a.effect.getKeyframes()[0] || {}).transform ? 'moves' : 'still'])""")
    moving = [r for r in running if r[2] == "moves" or r[1] in ("transform", "scale", "translate")]
    assert all("pp-plane" in r[0] for r in moving), running                  # nothing moves but the map's camera
    tr = page.evaluate("() => getComputedStyle(document.querySelector('.pp-plane')).transitionTimingFunction")
    assert tr.startswith("cubic-bezier(0.22, 1, 0.36, 1)")                   # --motion-zoom: most of the way at once, a soft landing, no overshoot


def test_reduced_motion_is_a_fade_and_the_map_jumps(cockpit):
    page = cockpit(PHONE)                     # the fixture's contexts reduce motion
    page.evaluate("() => { GA.motion.log.length = 0; }")
    page.evaluate("() => GA.cockpit.select(6, document.getElementById('ck-stub-6'))")
    kinds = [m["kind"] for m in page.evaluate(MOVES)]
    assert kinds and set(kinds) == {"fade"}, kinds
    assert page.evaluate("() => getComputedStyle(document.querySelector('.pp-plane')).transitionDuration") == "0s"
    assert page.evaluate("() => document.querySelectorAll('.pp-route.draw').length") == 0


def test_the_skies_live_and_pause_under_reduced_motion(cockpit):
    lively = cockpit(DESKTOP, motion=True)
    lively.wait_for_timeout(600)
    frames = lively.evaluate("() => [...document.querySelectorAll('.ck-stub .ck-sky canvas')].map(c => c.__wx && c.__wx.frames)")
    assert len(frames) == 8 and all(f and f > 5 for f in frames), frames
    still = cockpit(DESKTOP)
    still.wait_for_timeout(600)
    assert still.evaluate("() => [...document.querySelectorAll('.ck-sky canvas')].every(c => c.__wx && c.__wx.frames === 0)")


# ---- screenshots for the founder --------------------------------------------------------------------------------------------

@pytest.mark.skipif(not os.environ.get("F201_SHOTS"), reason="screenshots only when F201_SHOTS names a folder")
@pytest.mark.parametrize("viewport,dark", MODES + [(LAPTOP, False)], ids=IDS + ["1280-light"])
def test_screenshots(cockpit, viewport, dark):
    out = os.environ["F201_SHOTS"]
    os.makedirs(out, exist_ok=True)
    name = f"{viewport['width']}-{'dark' if dark else 'light'}"
    page = cockpit(viewport, dark=dark, motion=True, full=True, fonts=True)
    page.wait_for_function("() => document.fonts.status === 'loaded'")
    page.wait_for_timeout(1200)
    page.screenshot(path=f"{out}/f201-cockpit-{name}.png")
    if viewport["width"] < 1020:          # the phone's second screen: the week and the wallet (a full-page capture would draw the floating tab bar mid-page)
        page.locator("#ck-sec-week").scroll_into_view_if_needed()
        page.evaluate("() => window.scrollBy(0, -12)")
        page.wait_for_timeout(500)
        page.screenshot(path=f"{out}/f201-cockpit-{name}-2.png")
    if viewport is DESKTOP and not dark:
        page.locator("#ck-stub-4 .ck-hit").click()
        page.wait_for_timeout(1400)
        page.screenshot(path=f"{out}/f201-cockpit-day5-{name}.png")


# ---- review fixes (F-201 review) ----------------------------------------------------------------------------------------

FINE_PRINT = ".ck-t, .ck-lg-d, .ck-cap, .ck-tag, .ck-word, .ck-src, .ck-on, .ck-free, .ck-sec span, .pp-lbl, .pp-time, .ck-more, .ck-p-t, .ck-p-b em, .ck-credits"


def test_phone_text_follows_the_type_rule(cockpit):
    """At 390: body and secondary text 16px, fine print (times, distances, tags, credits, the sky's words) 14px, only all-caps labels 13px."""
    page = cockpit(PHONE)
    bad = page.evaluate("""(fine) => {
      const out = [], walk = document.createTreeWalker(document.getElementById('main'), NodeFilter.SHOW_TEXT);
      while (walk.nextNode()) {
        const t = walk.currentNode, el = t.parentElement;
        if (!t.textContent.trim() || !el || el.closest('[hidden], .sr-only, .ga-tb-pop, script, svg')) continue;      // (the paper map's own town names are artwork in its units, scaled with it)
        const r = el.getBoundingClientRect(); if (!r.width || !r.height || getComputedStyle(el).visibility === 'hidden') continue;
        const cs = getComputedStyle(el), px = parseFloat(cs.fontSize), caps = cs.textTransform === 'uppercase';
        const small = el.closest(fine);
        if (px < 13 || (px < 14 && !caps) || (px < 16 && !caps && !small)) out.push(px + 'px ' + (el.className || el.tagName) + ': ' + t.textContent.trim().slice(0, 24));
      }
      return out; }""", FINE_PRINT)
    assert bad == [], bad[:12]


def test_tablet_targets_are_48px_too(cockpit):
    page = cockpit({"width": 820, "height": 1180})          # an iPad: the phone's layout at the 12px root
    small = page.evaluate("""() => [...document.querySelectorAll('#main a, #main button, #main summary')].filter(n => {
        const r = n.getBoundingClientRect(), shut = n.closest('details:not([open])');
        return r.width > 0 && r.height > 0 && n.closest('[hidden]') === null && (!shut || n.tagName === 'SUMMARY') && (r.width < 47.5 || r.height < 47.5);
      }).map(n => (n.className || n.tagName) + ' ' + Math.round(n.getBoundingClientRect().width) + 'x' + Math.round(n.getBoundingClientRect().height))""")
    assert small == [], small


def test_a_press_squashes_on_touch(browser, base_url, monkeypatch, ctxs):
    from tests_browser.cockpit_support import seed
    ctx = browser.new_context(viewport=PHONE, is_mobile=True, has_touch=True, reduced_motion="reduce")
    ctx.set_default_timeout(15000)
    ctxs.append(ctx)
    seed(base_url, ctx, monkeypatch)
    page = ctx.new_page()
    page.goto(f"{base_url}/trip/cockpit", wait_until="domcontentloaded")
    page.wait_for_selector("#ck-paper[data-ready='1']")
    button = page.locator("#ck-ticket .ck-btn-tonal").first
    box = button.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down()
    squash = button.evaluate("b => getComputedStyle(b).transform")
    page.mouse.up()
    assert squash.startswith("matrix(0.96, 0, 0, 0.96"), squash


def test_the_skys_number_cross_fades_when_the_day_changes(cockpit):
    page = cockpit(PHONE, motion=True)
    page.evaluate("() => GA.cockpit.select(4, document.getElementById('ck-stub-4'))")
    anims = page.evaluate("""() => document.querySelector('#ck-ticket .ck-temp').getAnimations().map(a => [Math.round(a.effect.getTiming().duration), Object.keys(a.effect.getKeyframes()[0]).filter(k => k === 'opacity').length])""")
    assert anims and anims[0][1] == 1
    token = page.evaluate("() => GA.motion.t('desk')")
    assert anims[0][0] == token == 140


def test_a_plan_title_with_markup_never_breaks_the_page(browser, base_url, monkeypatch, ctxs):
    from gitaway import tripcal as cal
    from tests.test_signin import person
    page = open_cockpit(browser, base_url, monkeypatch, ctxs, viewport=DESKTOP)
    cal.add_activity(person("ari"), day=3, start=13 * 60, end=14 * 60, title="Lunch <!--<script> in town", kind="food")
    page.reload(wait_until="domcontentloaded")
    page.wait_for_selector("#ck-paper[data-ready='1']")
    assert page.locator("#ck-stub-3").inner_text().count("Lunch <!--<script> in town") == 1
    assert page.locator(".ck-stub").count() == 8


def test_places_that_arrive_after_the_page_loaded_show_up_without_a_reload(browser, base_url, monkeypatch, ctxs):
    from gitaway import familydb, geo, geopack, tripgeo
    from tests import tahoe
    from tests_browser.cockpit_support import seed
    ctx = browser.new_context(viewport=DESKTOP, reduced_motion="reduce")
    ctx.set_default_timeout(15000)
    ctxs.append(ctx)
    me = seed(base_url, ctx, monkeypatch, pack=False, maps=False)
    page = ctx.new_page()
    page.add_init_script("window.__ckPollMs = 250")
    page.goto(f"{base_url}/trip/cockpit", wait_until="domcontentloaded")
    page.wait_for_function("() => window.GA && GA.cockpit")
    assert page.locator("#ck-open-map").is_hidden()
    monkeypatch.setattr(geopack, "TRANSPORT", tahoe.pack_transport)       # (first: a poll between the two must not meet a refusing transport)
    monkeypatch.setattr(geo, "fetch", tahoe.geo_fetch)
    with familydb.using(me) as db:
        for group in tripgeo.day_places(me):
            geo.warm(db, group, budget=30)
    page.wait_for_function("() => [...document.querySelectorAll('.pp-tags .pp-lbl')].some(l => /Taylor Creek/.test(l.textContent))", timeout=20000)
    assert page.locator("#ck-open-map").is_visible()
