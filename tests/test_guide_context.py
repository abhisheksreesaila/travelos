"""F-263: guides in context. Which guides the rails offer for a place (the showcase's labelled samples, published creator guides, nothing else), the free time planning finds, the sheet's contents
for booking and planning, and Add to my plan dropping stops (one, or a free morning in order) into the calendar with the guide's name on them and an Undo. Nothing here reaches a network or a model."""
import json
import re
from dataclasses import replace
from html import unescape
from urllib.parse import parse_qs, urlsplit

from gitaway import community, guide as gd, guideplan, itineraries, planv2 as pv, tripcal as cal
from tests.test_calendar import book
from tests.test_guides import lisbon, named, publish, stranger  # noqa: F401 (the fixture and helpers)
from tests.test_roles import crew  # noqa: F401 - a fixture: Ari (admin), an editor and a viewer
from tests.test_signin import person, sign_in
from tests.test_tripmatrix_page import MATRIX

TACOS = "sun-tacos-and-tide-pools"
CURL = lambda day=0, booked="": ""      # noqa: E731
MATRIX_LA = MATRIX.split("?")[1].replace("San+Diego", "Los+Angeles")


def sheet(client, **q):
    return client.get("/guides/sheet", params=q)


def view():
    return pv.view(person("ari"), CURL)


def dry(monkeypatch, days=5):
    forecast = pv.Wx(74, 52, "Sunny", "sun", False, False, "Forecast · MET Norway")
    monkeypatch.setattr(pv, "sky", lambda t: ([forecast] * days, []))
    return forecast


def afternoon(client, monkeypatch):
    """A booked trip on dry days whose whole first day is taken, so what is free is the next morning (8:00 AM to 1:00 PM), long enough for two stops of the sample guide: -> (free, day number, keys)."""
    book(client)
    dry(monkeypatch)
    lo, hi = view().windows[0]
    client.post("/trip/plan/write", data={"op": "add", "day": "0", "start": str(lo), "end": str(hi), "title": "Slow day", "kind": "food"})
    free = guideplan.free_time(view())
    assert (free.day, free.name, free.part, free.start, free.end) == (1, "Saturday", "morning", 8 * 60, 13 * 60)
    n, keys = guideplan.fit_day(gd.from_trip(itineraries.get(TACOS)), free)
    return free, n, keys


# ---- which guides show for a place -----------------------------------------------------------------------------------------------------

def test_the_showcase_offers_its_labelled_sample_guides_for_their_place_only(client):
    cards, total = gd.for_place(person("ari"), "Los Angeles")
    assert [(c.slug, c.real, c.days) for c in cards] == [(TACOS, False, 5)] and total == 1
    assert gd.for_place(person("ari"), "Los Angeles, California")[0] == cards      # a place written the way a trip writes it
    assert gd.for_place(person("ari"), "San Diego") == ((), 0)      # the Okafors' San Diego trip is a family's trip, not a guide
    assert gd.for_place(person("ari"), "") == ((), 0) and gd.for_place(person("ari"), "Boise") == ((), 0)


def test_off_the_showcase_only_published_guides_show_and_the_samples_do_not(lisbon):
    client, d = lisbon
    assert gd.for_place(person("ari"), "Lisbon") == ((), 0) and gd.for_place(person("ari"), "Los Angeles") == ((), 0)      # nothing is published yet, and no sample is shown
    assert publish(client, named(client, d))["ok"]
    cards, total = gd.for_place(person("ari"), "Lisbon")
    assert [(c.slug, c.real) for c in cards] == [(d["slug"], True)] and total == 1
    assert gd.for_place(person("ari"), "Los Angeles") == ((), 0) and gd.for_place(person("ari"), "Paris") == ((), 0)
    community.set_review(d["slug"], "pending")      # waiting for the captain's yes: reached by its link only, so never offered
    assert gd.for_place(person("ari"), "Lisbon") == ((), 0)


# ---- the free time planning finds --------------------------------------------------------------------------------------------------

def test_the_first_free_morning_is_named_by_its_weekday_and_a_plan_in_it_moves_the_offer_on(client, monkeypatch):
    book(client)
    dry(monkeypatch)
    v = view()
    free = guideplan.free_time(v)
    first = dict(v.days)[0]
    assert (free.day, free.part, free.name, free.short) == (0, "morning" if free.start < 13 * 60 else "afternoon", first.strftime("%A"), first.strftime("%a"))
    assert free.minutes >= guideplan.MIN_FREE and free.said == f"Your {free.name} {free.part} is free."
    assert not any(free.start < b and a < free.end for a, b in pv._busy(v, free.day))      # never over a booking
    for i in range(1, 5):      # fill the next days' mornings: 8:00 to 1:00
        lo, hi = v.windows[i]
        client.post("/trip/plan/write", data={"op": "add", "day": str(i), "start": str(max(lo, 480)), "end": str(min(hi, 780)), "title": f"Busy {i}", "kind": "fun"})
    after = guideplan.free_time(view())
    assert (after.day, after.part) == (free.day, free.part)      # still the first one; the busy mornings are skipped, not offered
    lo, hi = v.windows[free.day]
    client.post("/trip/plan/write", data={"op": "add", "day": str(free.day), "start": str(free.start), "end": str(free.end), "title": "Taken", "kind": "fun"})
    moved = guideplan.free_time(view())
    assert (moved.day, moved.part) != (free.day, free.part) and (moved.day, moved.start) > (free.day, free.start)


def test_a_day_with_a_real_forecast_of_rain_is_not_offered_but_a_typical_wet_day_is(client, monkeypatch):
    book(client)
    sun = dry(monkeypatch)
    rain = pv.Wx(60, 48, "Rain", "rain", False, False, "Forecast · MET Norway")
    monkeypatch.setattr(pv, "sky", lambda t: ([rain, sun, sun, sun, sun], []))
    assert guideplan.free_time(view()).day == 1
    typical = replace(rain, typical=True, label="Typical · not a forecast yet")
    monkeypatch.setattr(pv, "sky", lambda t: ([typical, sun, sun, sun, sun], []))
    assert guideplan.free_time(view()).day == 0
    monkeypatch.setattr(pv, "sky", lambda t: ([rain] * 5, []))
    assert guideplan.free_time(view()) is None      # nothing dry: nothing offered


def test_the_guide_day_that_fits_the_free_time_best_is_named_and_a_gap_that_fits_one_stop_is_not_a_morning():
    g = gd.from_trip(itineraries.get(TACOS))
    five_hours = guideplan.Free(1, "Saturday", "Sat", "morning", 8 * 60, 13 * 60)
    n, keys = guideplan.fit_day(g, five_hours)
    stops = {s.key: s for d in g.days for s in d.stops}
    assert keys == [s.key for s in g.days[n - 1].stops][:len(keys)] and len(keys) >= 2      # the day's first stops, in order
    assert sum(guideplan.minutes_of(stops[k]) for k in keys) <= five_hours.minutes
    assert all(len(keys) >= len(other) for other in [guideplan.fit_day(g, five_hours)[1]])
    assert guideplan.fit_day(g, guideplan.Free(1, "Saturday", "Sat", "morning", 8 * 60, 8 * 60 + 150)) is None      # 2.5 hours: one stop, so no morning to offer


# ---- Add to my plan: a free morning, in order, tagged -------------------------------------------------------------------------------------------

def test_a_free_stretch_is_dropped_in_one_stop_after_another_tagged_with_the_guide_and_undo_takes_it_out(client, monkeypatch):
    free, n, keys = afternoon(client, monkeypatch)
    assert (n, keys) == (1, ["d0s0", "d0s1"])
    r = client.post("/guides/add", data={"slug": TACOS, "k": keys, "to": str(free.day), "after": str(free.start)})
    j = r.json()
    assert r.status_code == 200 and [a["key"] for a in j["added"]] == keys and j["skipped"] == []
    starts = [(a["start"], a["end"]) for a in j["added"]]
    assert starts[0][0] == free.start and all(starts[i][1] == starts[i + 1][0] for i in range(len(starts) - 1)) and starts[-1][1] <= free.end      # one after the other, inside the free time
    assert j["toast"] == f"{len(keys)} stops added to {free.short}, {cal.fmt_time(starts[0][0])} to {cal.fmt_time(starts[-1][1])}"
    assert {a.day for a in cal.activities(person("ari")) if a.title != "Slow day"} == {free.day} and sorted(a.title for a in cal.activities(person("ari"))) == sorted(["Slow day", *[a["title"] for a in j["added"]]])
    page = client.get("/trip/plan/cal").text
    assert page.count("From Maya&#x27;s guide") + page.count("From Maya's guide") >= len(keys)      # the calendar says whose they are
    for a in reversed(j["added"]):
        assert client.post("/trip/plan/write", data={"op": "undo", "undo": json.dumps(a["undo"])}).status_code == 200
    assert [a.title for a in cal.activities(person("ari"))] == ["Slow day"]
    assert "From Maya" not in client.get("/trip/plan/cal").text      # and the tag went with them


def test_a_free_stretch_skips_what_is_already_in_the_plan_and_says_how_many(client, monkeypatch):
    free, n, keys = afternoon(client, monkeypatch)
    g = gd.from_trip(itineraries.get(TACOS))
    stop = g.find(keys[0])
    client.post("/trip/plan/write", data={"op": "add", "day": "3", "start": "600", "end": "660", "title": stop.name[:40], "kind": "fun"})      # one of them is already there
    j = client.post("/guides/add", data={"slug": TACOS, "k": keys, "to": str(free.day), "after": str(free.start)}).json()
    assert j["skipped"] == [stop.name] and len(j["added"]) == len(keys) - 1
    assert j["toast"].endswith(". 1 left out: already there, or no free time.")


def test_a_day_under_a_real_forecast_of_rain_is_refused_in_the_calendars_words_and_nothing_is_added(client, monkeypatch):
    book(client)
    sun = dry(monkeypatch)
    rain = pv.Wx(60, 48, "Rain", "rain", False, False, "Forecast · MET Norway")
    monkeypatch.setattr(pv, "sky", lambda t: ([sun, rain, sun, sun, sun], []))
    first = dict(view().days)[1].strftime("%A")
    r = client.post("/guides/add", data={"slug": TACOS, "k": ["d0s0", "d0s1"], "to": "1", "after": "480"})
    assert r.status_code == 422 and r.json() == {"error": f"Rain is forecast for {first}, so nothing was added there."} and cal.activities(person("ari")) == []
    assert client.post("/guides/add", data={"slug": TACOS, "k": ["d0s0"], "to": "9", "after": "480"}).json() == {"error": "That day is not in your trip."}


def test_one_stop_still_lands_on_a_dry_day_and_a_viewer_cannot_add(crew, monkeypatch):
    client, _, viewer = crew
    sun = dry(monkeypatch)
    rain = pv.Wx(60, 48, "Rain", "rain", False, False, "Forecast · MET Norway")
    monkeypatch.setattr(pv, "sky", lambda t: ([rain, rain, sun, rain, rain], []))
    j = client.post("/guides/add", data={"slug": TACOS, "k": ["d0s1"]}).json()
    assert len(j["added"]) == 1 and [a.day for a in cal.activities(person("ari"))] == [2]      # the + goes where it is dry
    assert viewer.post("/guides/add", data={"slug": TACOS, "k": ["d0s2"], "to": "2", "after": "480"}).status_code == 403


# ---- the sheet ------------------------------------------------------------------------------------------------------------------------

def test_the_planning_sheet_names_the_free_time_the_day_that_fits_and_opens_stops_in_place(client, monkeypatch):
    free, n, keys = afternoon(client, monkeypatch)
    v = view()
    r = sheet(client, slug=TACOS, ctx="plan")
    j = r.json()
    html = j["html"]
    a, z = v.days[0][1], v.days[-1][1]
    assert r.status_code == 200 and j["title"] == "Sun, tacos & tide pools" and j["sample"] is True and "/assets/css/guides.css" in j["css"]
    assert f"Your plan</b> · {a:%b} {a.day} to {z.day} · {free.name} {free.part} free" in html
    assert "Your Saturday morning is free." in html and f"Day {n} fits it." in html
    assert f'data-add-day="{" ".join(keys)}"' in html and f'data-to="{free.day}"' in html and f'data-after="{free.start}"' in html
    assert f"Add this {free.part} to {free.short}" in html
    assert html.count('class="g-inplace"') == 16 and html.count(" inert") == 16      # every stop's details sit inside its card, folded and inert
    assert html.count('data-add="d') == 16 * 2 and "<aside" not in html and 'id="g-panel"' not in html       # a "+" and an "Add to my plan" for every stop, and no second panel to open
    assert "Sample guide" in html and 'href="/trips/sun-tacos-and-tide-pools"' in html and ">Plan this trip<" not in html


def test_the_booking_sheet_names_your_search_and_plans_nothing(client):
    q = {"slug": TACOS, "ctx": "book", **dict(p.split("=") for p in MATRIX_LA.replace("+", " ").split("&")), "lane": "losangeles", "w": "2026-12-12"}
    html = sheet(client, **q).json()["html"]
    assert re.search(r"Your trips</b> · Los Angeles, Dec 12 · 4 nights · \$[\d,]+ picked\s*</p>", html)
    assert "data-add" not in html and "Add this" not in html and ">Plan this trip<" in html and "From the creator" not in html
    assert 'data-ctx="book"' in html


def test_the_sheet_refuses_what_it_does_not_know_and_a_viewer_is_told_why_there_are_no_adds(crew):
    client, _, viewer = crew
    assert sheet(client, slug=TACOS, ctx="nowhere").status_code == 400
    assert sheet(client, slug="no-such-guide", ctx="plan").json() == {"error": "That guide is not here any more."}
    assert sheet(client, slug="san-diego-on-a-budget", ctx="plan").status_code == 404      # a family's trip is not a guide
    html = sheet(viewer, slug=TACOS, ctx="plan").json()["html"]
    assert "Only editors of the family can change its plan." in html and "data-add" not in html and "is free." not in html


# ---- the rails' card -------------------------------------------------------------------------------------------------------------------------

def test_booking_rail_lists_the_places_guides_labelled_sample_and_each_opens_its_sheet(client):
    sign_in(client)
    html = client.get("/plan/matrix/rail?" + MATRIX_LA + "&lane=losangeles&w=2026-12-12").json()["html"]
    assert "Guides for Los Angeles" in html and "Sun, tacos &amp; tide pools" in html and ">Sample<" in html and "5 days" in html
    href = unescape(re.search(r'data-sheet="([^"]+)"', html).group(1))
    q = parse_qs(urlsplit(href).query)
    assert urlsplit(href).path == "/guides/sheet" and (q["slug"], q["ctx"], q["lane"], q["w"], q["to"], q["d"]) == (["sun-tacos-and-tide-pools"], ["book"], ["losangeles"], ["2026-12-12"], ["Los Angeles"], ["2026-12-12"])
    assert re.search(r'<a [^>]*href="/guides\?q=Los%20Angeles"[^>]*>All Los Angeles guides</a>', html)
    san_diego = client.get("/plan/matrix/rail?" + MATRIX.split("?")[1] + "&lane=sandiego&w=2026-12-12").json()["html"]
    assert "Guides for" not in san_diego      # no guide of San Diego: no card, not an empty one


def test_planning_rail_lists_the_trips_guides_and_off_the_showcase_with_none_published_nothing(client, monkeypatch):
    book(client)
    page = client.get("/trip/plan").text
    assert "Guides for Los Angeles" in page and 'data-sheet="/guides/sheet?slug=sun-tacos-and-tide-pools&amp;ctx=plan"' in page and "It opens over your plan" in page
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    assert "Guides for" not in client.get("/trip/plan").text
