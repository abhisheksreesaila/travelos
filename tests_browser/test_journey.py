"""F-300 in a real browser: /trip/plan as a journey. The road shows the booking (flights as arcs, the stay as a band, locks that shake), a person hovers the line and adds a plan, drags it to retime
it (15 minutes at a time) and it is kept after a reload; plans too close together fold into one ghost card whose list opens; the Grid is one tap away and is the grid it always was. Phone 390
and laptop 1440, light and dark. Set F300_SHOTS=1 for docs/report/f300-*.png."""
import os
import time
from pathlib import Path

import pytest
from playwright.sync_api import expect

from tests.test_calendar import PICK
from tests_browser.helpers import DESKTOP, PHONE, open_more
from tests_browser.look import audit

SHOTS = Path(__file__).resolve().parent.parent / "docs" / "report"
DAYS = ["Fri 16", "Sat 17", "Sun 18", "Mon 19", "Tue 20"]


@pytest.fixture
def trip(browser, base_url):
    """trip(viewport, scheme="light", plans=()) -> a page on /trip/plan for a family with a booked trip (its own). `plans` are written first as (day, start, end, title). Contexts are closed after the test."""
    contexts = []

    def make(viewport, scheme="light", plans=()):
        phone = viewport["width"] < 720
        ctx = browser.new_context(viewport=viewport, reduced_motion="reduce", has_touch=phone, is_mobile=phone)
        ctx.set_default_timeout(5000)
        ctx.add_init_script("if (!sessionStorage.getItem('seeded')) { sessionStorage.setItem('seeded', '1'); localStorage.setItem('ga-plan-view', 'journey'); }")      # the default, once, whatever the suite's other tests keep
        if scheme == "dark":
            ctx.add_init_script("localStorage.setItem('ga-mode', 'dark')")
        contexts.append(ctx)
        ctx.request.post(f"{base_url}/signin", form={"email": f"jny{time.time_ns()}@example.com", "next": "/", "intent": "save"}, max_redirects=0)
        ctx.request.post(f"{base_url}/_test/pay", form=PICK, max_redirects=0)
        for day, start, end, title in plans:
            r = ctx.request.post(f"{base_url}/trip/plan/write", form={"op": "add", "day": str(day), "start": str(start), "end": str(end), "title": title, "kind": "fun"})
            assert r.ok, r.text()
        page = ctx.new_page()
        page.errors = []
        page.on("pageerror", lambda e: page.errors.append(str(e)))
        page.goto(f"{base_url}/trip/plan")
        page.wait_for_selector(".pj-ev")
        return page

    yield make
    for c in contexts:
        c.close()


def shot(page, name):
    if os.environ.get("F300_SHOTS"):
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f"f300-{name}.png"))


def card(page, title):
    return page.locator(f".pj-ev:has(b:text-is('{title}'))")


def tick(page, day, label="12 PM"):
    """The `day`th tick that reads `label` (the road shows every third hour at Day zoom, so each day has one 12 PM), scrolled to the middle of the road. -> its centre x on the screen."""
    find = "([d, l]) => [...document.querySelectorAll('.pj-tick')].filter(x => x.firstChild.textContent === l)[d]"
    page.evaluate(f"(a) => {{ const t = ({find})(a); t.scrollIntoView({{inline: 'center', block: 'nearest'}}); }}", [day, label])
    page.wait_for_timeout(150)
    return page.evaluate(f"(a) => {{ const r = ({find})(a).getBoundingClientRect(); return r.x + r.width / 2; }}", [day, label])


def line_y(page):
    """The screen y of the road's line."""
    return page.evaluate("() => { const p = document.querySelector('.pj'); return p.getBoundingClientRect().top + parseFloat(p.style.getPropertyValue('--ly')); }")


def per_hour(page):
    """Pixels the road spends on an hour at the zoom it is at (the distance between two ticks over the hours between them)."""
    return page.evaluate("""() => { const t = [...document.querySelectorAll('.pj-tick')].slice(0, 2).map(x => parseFloat(x.style.left));
        return (t[1] - t[0]) / ({0: 6, 1: 3, 2: 1}[+document.querySelector('.pj-seg [aria-pressed=true]').dataset.z]); }""")


def when(page, title):
    return card(page, title).locator(".tm").inner_text().split(" · ")[0]      # the time, before whose plan it is


def add_on_the_line(page, day, title):
    x = tick(page, day)
    page.mouse.move(x, line_y(page))
    expect(page.locator(".pj-ghost span")).to_have_text(f"+ Add at {DAYS[day]} 12:00 PM")
    page.mouse.click(x, line_y(page))
    expect(page.locator(".pj-add")).to_be_visible()
    page.fill(".pj-add input", title)
    page.click(".pj-add .go")
    expect(card(page, title)).to_be_visible()
    return card(page, title)


def test_the_road_draws_the_booking_a_stay_band_flight_arcs_and_the_days(trip):
    page = trip(DESKTOP)
    assert page.locator(".pj-stay").inner_text().startswith("The Tidewater · 4 nights · booked")
    assert page.locator(".pj-arc").count() == 2 and page.locator(".pj-day").count() == 5
    assert page.locator(".pj-ev.locked").count() >= 2
    assert "Clear skies · 75°/63°" in page.locator(".pj-day").first.inner_text() and "Daylight 6:58 AM to 6:19 PM" in page.locator(".pj-day").first.inner_text()
    assert page.locator(".pj-notes").inner_text().strip() == "Sample weather"
    assert page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth") <= 1
    shot(page, "1440-road")
    assert page.errors == []


def test_hovering_the_line_adds_a_plan_that_a_reload_keeps(trip):
    page = trip(DESKTOP)
    add_on_the_line(page, 2, "Pier walk")
    assert when(page, "Pier walk") == "12:00–1:00 PM"
    page.reload()
    page.wait_for_selector(".pj-ev")
    assert when(page, "Pier walk") == "12:00–1:00 PM"            # it is stored, not only drawn
    page.click("[data-mode-set='grid']")
    expect(page.locator(".ev[data-title='Pier walk']")).to_be_visible()      # and it is the same plan the grid shows
    assert page.errors == []


def test_dragging_a_plan_retimes_it_in_quarter_hours_and_a_reload_keeps_it(trip):
    page = trip(DESKTOP)
    c = add_on_the_line(page, 2, "Pier walk")
    h = per_hour(page)
    box = c.bounding_box()
    page.mouse.move(box["x"] + 40, box["y"] + 20)
    page.mouse.down()
    page.mouse.move(box["x"] + 40 + 10, box["y"] + 20, steps=3)
    page.mouse.move(box["x"] + 40 + h * 65 / 60, box["y"] + 20, steps=6)                  # an hour and five minutes: it snaps to 1:00 PM, not 1:05
    expect(page.locator(".pj-bubble")).to_have_text("Sun 18 · 1:00 PM")
    shot(page, "1440-dragging")
    page.mouse.up()
    page.wait_for_function("t => [...document.querySelectorAll('.pj-ev')].some(n => n.querySelector('b').textContent === t && n.querySelector('.tm').textContent.startsWith('1:00'))", arg="Pier walk")
    assert when(page, "Pier walk") == "1:00–2:00 PM"
    page.reload()
    page.wait_for_selector(".pj-ev")
    assert when(page, "Pier walk") == "1:00–2:00 PM"
    assert page.errors == []


def test_a_booked_thing_shakes_when_dragged_and_opens_its_booking_when_tapped(trip, base_url):
    page = trip(DESKTOP)
    stay = page.locator(".pj-ev.locked:has(.kd:text('Stay'))").first
    box = stay.bounding_box()
    page.mouse.move(box["x"] + 40, box["y"] + 20)
    page.mouse.down()
    page.mouse.move(box["x"] + 140, box["y"] + 20, steps=5)
    page.mouse.up()
    assert "shake" in stay.get_attribute("class") and page.url == f"{base_url}/trip/plan"
    assert stay.bounding_box()["x"] == box["x"]                                                # it did not move
    stay.click()
    page.wait_for_url("**/trip/booking?block=*")


def test_plans_too_close_together_fold_into_one_ghost_card_that_opens_and_spreads_out(trip):
    plans = [(1, 14 * 60, 14 * 60 + 30, "Sled hill"), (1, 14 * 60 + 30, 15 * 60, "Cocoa"), (1, 15 * 60, 15 * 60 + 30, "Snowman"), (1, 15 * 60 + 15, 15 * 60 + 45, "Boots back"),
             (1, 15 * 60 + 45, 16 * 60 + 15, "Gondola"), (1, 16 * 60 + 15, 16 * 60 + 45, "Big sign")]
    page = trip(DESKTOP, plans=plans)
    tick(page, 1, "3 PM")
    crowd = page.locator(".pj-crowd")
    expect(crowd).to_have_count(1)
    n = int(crowd.locator("b").inner_text().split(" ")[0])
    shown = page.locator(".pj-ev:not(.locked)").count()
    assert n >= 2 and n + shown == 6                                                           # every plan is on the road or in the ghost card
    assert crowd.locator(".dots i").count() == n and page.locator(".pj-gdot").count() == n     # a hollow ring on the line for each one
    box = crowd.bounding_box()
    page.mouse.move(box["x"] + 40, box["y"] + 20)
    expect(crowd.locator(".pj-peek")).to_be_visible()
    assert crowd.locator(".pj-peek li").count() == n
    shot(page, "1440-crowd")
    crowd.locator(".spread").click()
    assert page.locator(".pj-seg [aria-pressed=true]").inner_text() == "Hours"
    assert page.locator(".pj-ev:not(.locked)").count() > shown                                  # more of them have room at Hours
    assert page.errors == []


def test_the_grid_is_one_tap_away_and_is_the_grid_it_was_and_the_choice_is_kept(trip):
    page = trip(DESKTOP)
    assert page.locator(".g-inner").is_hidden() and page.locator(".pj").is_visible()
    page.click("[data-mode-set='grid']")
    expect(page.locator(".g-inner")).to_be_visible()
    assert page.locator(".pj").is_hidden() and page.locator(".pl-trip").is_visible()
    shot(page, "1440-grid")
    page.reload()
    page.wait_for_selector(".g-inner")
    assert page.locator(".g-inner").is_visible()                                               # kept on the device
    page.click("[data-mode-set='journey']")
    expect(page.locator(".pj-ev").first).to_be_visible()
    assert page.locator(".g-inner").is_hidden()


def test_zoom_changes_the_scale_keeps_the_centre_and_trip_shows_every_day(trip):
    page = trip(DESKTOP)
    page.click(".pj-seg [data-z='2']")
    expect(page.locator(".pj-seg [data-z='2']")).to_have_attribute("aria-pressed", "true")
    assert page.locator(".pj-tick").count() > 60                                               # an hour at a time
    page.click(".pj-seg [data-z='0']")
    assert page.locator(".pj-tick").count() < 25 and page.locator(".pj-day").count() == 5
    assert page.evaluate("document.querySelector('.pj-track').offsetWidth") < 5 * 24 * 22 + 200
    assert not page.locator("#pj-now").is_visible()                                            # the trip is ahead: no Now


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["1440", "390"])
def test_the_cards_follow_the_mode_and_the_page_never_scrolls_sideways(trip, viewport, scheme):
    page = trip(viewport, scheme)
    assert page.evaluate("document.documentElement.dataset.mode") == scheme
    bg = page.evaluate("() => getComputedStyle(document.querySelector('.pj-ev')).backgroundColor.match(/\\d+/g).slice(0, 3).map(Number)")
    assert (sum(bg) / 3 > 200) == (scheme == "light"), bg
    assert page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth") <= 1
    shot(page, f"{viewport['width']}{'-dark' if scheme == 'dark' else ''}-road")
    m = audit(page)
    assert m["wide"] <= 1 and m["low"] == [] and m["glass"] == [] and m["small"] == [] and m["tiny"] == [], m      # 4.5:1 text, 48px targets, nothing under the type floor
    open_more(page, "#pl-together").click()                                                    # the trip's More menu is in the journey's bar
    expect(page.locator("#pl-side")).to_be_visible()
    page.wait_for_timeout(400)
    shot(page, f"{viewport['width']}{'-dark' if scheme == 'dark' else ''}-together")
    assert page.errors == []


def test_on_a_phone_a_tap_on_the_line_adds_and_a_tap_on_a_plan_moves_it_by_quarter_hours(trip):
    page = trip(PHONE)
    x = tick(page, 1)
    page.touchscreen.tap(x, line_y(page))
    expect(page.locator(".pj-add")).to_be_visible()
    page.fill(".pj-add input", "Beach hour")
    page.click(".pj-add .go")
    expect(card(page, "Beach hour")).to_be_visible()
    assert when(page, "Beach hour") == "12:00–1:00 PM"
    card(page, "Beach hour").tap()
    page.click("button[aria-label='Beach hour 15 minutes later']")
    page.wait_for_function("t => [...document.querySelectorAll('.pj-ev')].some(n => n.querySelector('b').textContent === t && n.querySelector('.tm').textContent.startsWith('12:15'))", arg="Beach hour")
    assert when(page, "Beach hour") == "12:15–1:15 PM"
    shot(page, "390-moved")
    assert page.errors == []


def snowy_saturday(t, where):
    """MET-shaped hours for the trip's second day (what gitaway/journey.py's forecast_points makes from weather.py; the server side of it is tests/test_journey.py): cool and clear until noon, cloud
    after, light snow from 2 PM, steady from 4 PM, over at 8 PM."""
    out = []
    for h in range(6, 22):
        snow = 14 <= h < 20
        out.append({"t": 1440 + h * 60, "h": 1, "f": 24 + (h - 6) // 2, "c": 100.0 if h >= 12 else 20.0, "p": (0.3 if h < 16 else 1.2) if snow else 0.0, "s": "snow" if snow else ""})
    return out


def test_a_real_forecast_draws_its_hours_a_snow_curtain_a_heads_up_and_falls_only_while_it_snows(trip, monkeypatch):
    from gitaway import journey
    monkeypatch.setattr(journey, "forecast_points", snowy_saturday)
    page = trip(DESKTOP, plans=[(1, 15 * 60, 16 * 60, "Sled hill"), (1, 9 * 60, 10 * 60, "Coffee")])
    flakes = lambda: page.evaluate("() => { const c = document.querySelector('.pj-fall'), d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let n = 0; for (let i = 3; i < d.length; i += 4) if (d[i]) n++; return n; }")
    sky = lambda: page.evaluate("() => getComputedStyle(document.querySelector('.pj')).getPropertyValue('--jv-sky-top').trim()")
    tick(page, 1, "9 AM")                                                                      # clear, cool, before the snow
    page.wait_for_timeout(200)
    clear_sky = sky()
    assert flakes() == 0 and "Snow" not in card(page, "Coffee").inner_text()
    tick(page, 1, "6 PM")                                                                      # in the middle of the snow
    page.wait_for_timeout(200)
    assert page.locator(".pj-curtain span").inner_text() == "Snow · 2 PM to 8 PM"
    assert "Snow, 2 PM to 8 PM" in card(page, "Sled hill").inner_text()                      # the Heads up is the forecast's own words, only on the plan it covers
    assert flakes() > 100 and sky() != clear_sky                                                # snow is falling and the sky has greyed
    assert "28°" in page.locator(".pj-tick:has-text('3 PM') em").all_inner_texts()[0]           # the hour's own temperature on its tick (15:00: 24 + 4)
    shot(page, "1440-snow")
    assert page.errors == []


def test_typical_weather_says_it_is_not_a_forecast_and_draws_no_hours_or_snow(trip, monkeypatch):
    from gitaway import planv2 as pv
    typical = pv.Wx(41, 22, "Typical", "snow", True, False, "Typical late October · not a forecast yet")
    monkeypatch.setattr(pv, "sky", lambda t: ([typical] * 5, [("Snow or rain about 1 day in 3. From NOAA climate normals for Los Angeles, 1991–2020.", "")]))
    page = trip(DESKTOP)
    day = page.locator(".pj-day").first.inner_text()
    assert "Typical · 41°/22°" in day and "Not a forecast yet" in day
    assert page.locator(".pj-notes").inner_text().startswith("Typical weather for the time of year, not a forecast yet.")
    assert page.locator(".pj-curtain").count() == 0 and page.locator(".pj-tick em").count() == 0      # typical days are a line under the day, never hours or falling snow
    assert page.evaluate("() => { const c = document.querySelector('.pj-fall'); return c.getContext('2d').getImageData(0, 0, c.width, c.height).data.some(v => v); }") is False


def test_during_the_trip_now_is_marked_in_the_places_time_and_the_button_goes_there(trip, monkeypatch):
    from datetime import datetime, timezone
    from gitaway import catalog
    during = datetime(2026, 10, 18, 22, 20, tzinfo=timezone.utc)                              # 3:20 PM on Sun Oct 18 in Los Angeles (PDT)
    monkeypatch.setattr(catalog, "now_utc", lambda: during)
    monkeypatch.setattr(catalog, "today", lambda: during.date())
    page = trip(DESKTOP)
    expect(page.locator("#pj-now")).to_be_visible()
    assert page.locator(".pj-now span").inner_text() == "NOW"
    page.evaluate("() => document.querySelector('.pj-road').scrollTo(0, 0)")
    page.click("#pj-now")
    page.wait_for_function("() => { const r = document.querySelector('.pj-road'), n = document.querySelector('.pj-now').getBoundingClientRect(); return Math.abs(n.x - (r.getBoundingClientRect().x + r.clientWidth / 2)) < 4; }")


def test_the_hills_take_the_places_own_colour_so_two_places_look_different(trip, monkeypatch):
    from gitaway import placecolor
    seen = {}
    for name, colour in (("green", "#17834A"), ("violet", "#7D4CF0")):
        monkeypatch.setattr(placecolor, "of", lambda place, c=colour: (c, "#FFFFFF"))
        page = trip(DESKTOP)
        seen[name] = page.evaluate("() => ['--jv-r1', '--jv-r2', '--jv-r3'].map(v => document.querySelector('.pj').style.getPropertyValue(v))")
        assert all(seen[name]) and page.errors == []
    assert all(a != b for a, b in zip(seen["green"], seen["violet"]))
