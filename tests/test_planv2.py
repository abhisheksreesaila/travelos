"""F-252: planning v2. The page at /trip/plan draws the open trip's calendar with what is booked on it, quick add, move and resize write through the calendar's own model, the rail
says only what has a source, and planning together is the family's existing members and chats."""

import json
import re
from html import unescape
from dataclasses import replace
from datetime import date

import pytest

from gitaway import planv2 as pv, showcase, tripcal as cal
from tests.test_calendar import FORM, book
from tests.test_members import addr, browser, invite
from tests.test_signin import person, sign_in


def data(html):
    return json.loads(re.search(r'<script type="application/json" id="pl-data">(.*?)</script>', html, re.S).group(1))


def evs(html):
    """{id: attributes} of every event drawn in a calendar fragment or page."""
    out = {}
    for m in re.finditer(r'<(?:a|div)\s[^>]*class="ev [^"]*"[^>]*>', html):
        a = dict(re.findall(r'([\w-]+)="([^"]*)"', m.group(0)))
        out[a["data-id"]] = a
    return out


def write(client, **form):
    return client.post("/trip/plan/write", data=form, follow_redirects=False)


def add(client, **over):
    return write(client, op="add", day="1", start="600", end="660", title="Venice Canals stroll", kind="outdoors", **over)


@pytest.fixture
def booked(client):
    book(client)
    return client


# ---- the page ----------------------------------------------------------------------------------------------------------------

def test_signed_out_signs_in_and_without_a_booking_starts_one(client):
    r = client.get("/trip/plan", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/signin?next=%2Ftrip%2Fplan"
    sign_in(client)
    assert client.get("/trip/plan", follow_redirects=False).headers["location"] == "/plan/ask"


def test_the_arrival_names_the_trip_its_dates_the_family_and_the_days_to_go(booked):
    r = booked.get("/trip/plan")
    assert r.status_code == 200
    d = data(r.text)
    assert d["summary"]["title"] == cal.trip("", None).title
    assert "Oct 16" in r.text and "Oct 20" in r.text and "4 nights" in r.text
    assert re.search(r'<b class="num">(\d+)</b><span>days? to go</span>', r.text)       # the clock is pinned before the trip: a real count
    assert 'class="av' in r.text and "Planning together" in r.text or "together" in r.text.lower()


def test_the_calendar_day_headers_carry_weather_and_a_typical_day_is_labelled(booked, monkeypatch):
    typical = pv.Wx(74, 52, "Typical", "sun", True, False, "Typical · not a forecast yet")
    monkeypatch.setattr(pv, "sky", lambda t: ([typical] * 5, []))
    html = booked.get("/trip/plan/cal?view=week").text
    assert html.count("74°") >= 5 and "Typical weather for the time of year, not a forecast yet." in html
    assert "Rain likely" not in html and "nudge" not in booked.get("/trip/plan").text      # nothing wet: no nudge


def test_a_real_forecast_of_rain_nudges_and_a_typical_wet_day_does_not(booked, monkeypatch):
    dry = pv.Wx(74, 52, "Sunny", "sun", False, False, "Forecast · MET Norway")
    wet = pv.Wx(63, 49, "Rain", "rain", False, False, "Forecast · MET Norway")
    monkeypatch.setattr(pv, "sky", lambda t: ([dry, dry, wet, dry, dry], []))
    page = booked.get("/trip/plan").text
    assert "Rain on Sunday" in page and 'data-show="2"' in page and "Rain likely" in booked.get("/trip/plan/cal").text
    typical_wet = replace(wet, typical=True, label="Typical · not a forecast yet")
    monkeypatch.setattr(pv, "sky", lambda t: ([dry, dry, typical_wet, dry, dry], []))
    assert "Rain on" not in booked.get("/trip/plan").text and "Rain likely" not in booked.get("/trip/plan/cal").text


def test_the_sample_trips_weather_says_sample_and_a_real_trip_never_borrows_it(booked, monkeypatch):
    assert "Sample weather" in booked.get("/trip/plan/cal").text
    monkeypatch.setattr(showcase, "on", lambda: False)      # off the showcase the sample trip is not the sample: weather.py's NOAA typical days, labelled
    html = booked.get("/trip/plan/cal").text
    assert "Sample weather" not in html and "Typical weather for the time of year, not a forecast yet." in html


# ---- writes: add, move, resize, undo -------------------------------------------------------------------------------------------

def test_adding_a_plan_writes_it_through_the_calendar_and_answers_the_grid(booked):
    r = add(booked)
    assert r.status_code == 200
    j = r.json()
    assert j["toast"] == "Venice Canals stroll added" and j["plan"]["start"] == 600 and j["plan"]["end"] == 660 and j["plan"]["kind"] == "outdoors"
    assert evs(j["grid"])[j["plan"]["act"]]["data-title"] == "Venice Canals stroll"
    stored = [(a.day, a.start, a.end, a.title, a.kind) for a in cal.activities(person("ari"))]
    assert stored == [(1, 600, 660, "Venice Canals stroll", "outdoors")]
    assert evs(booked.get("/trip/plan/cal?view=week").text)[j["plan"]["act"]]["data-start"] == "600"


def test_moving_and_resizing_a_plan_saves_to_the_model_and_undo_puts_it_back(booked):
    act = add(booked).json()["plan"]["act"]
    moved = write(booked, op="edit", act=act, start="780", end="840", day="2").json()
    assert moved["plan"]["day"] == 2 and moved["plan"]["start"] == 780 and moved["plan"]["end"] == 840 and moved["toast"] == "Venice Canals stroll saved"
    resized = write(booked, op="edit", act=act, end="900").json()
    assert (resized["plan"]["start"], resized["plan"]["end"]) == (780, 900)
    assert [(a.day, a.start, a.end) for a in cal.activities(person("ari"))] == [(2, 780, 900)]
    back = write(booked, op="undo", undo=json.dumps(resized["undo"])).json()
    assert (back["plan"]["start"], back["plan"]["end"]) == (780, 840)
    again = write(booked, op="undo", undo=json.dumps(moved["undo"])).json()
    assert (again["plan"]["day"], again["plan"]["start"], again["plan"]["end"]) == (1, 600, 660)
    assert [(a.day, a.start, a.end) for a in cal.activities(person("ari"))] == [(1, 600, 660)]


def test_delete_and_its_undo(booked):
    act = add(booked).json()["plan"]["act"]
    gone = write(booked, op="delete", act=act).json()
    assert gone["toast"] == "Venice Canals stroll removed" and act not in evs(gone["grid"]) and cal.activities(person("ari")) == []
    back = write(booked, op="undo", undo=json.dumps(gone["undo"])).json()
    assert back["toast"] == "Venice Canals stroll is back" and [a.title for a in cal.activities(person("ari"))] == ["Venice Canals stroll"]


def test_the_calendars_own_words_refuse_what_cannot_be_written(booked):
    r = write(booked, op="add", day="1", start="1300", end="1360", title="Too late", kind="fun")
    assert r.status_code == 422 and r.json()["error"] == "Plan between 7:00 AM and 10:00 PM."
    r = write(booked, op="add", day="9", start="600", end="660", title="Nowhere", kind="fun")
    assert r.status_code == 422 and r.json()["error"] == "Pick a day inside your trip."
    r = write(booked, op="edit", act="b-in", start="600")
    assert r.status_code == 422 and r.json()["error"] == "Booked items are locked. Change your booking to move them."
    assert cal.activities(person("ari")) == []


def test_a_plan_made_here_is_the_one_the_old_add_route_makes_and_shows_in_the_thread(booked):
    add(booked)
    from gitaway import familythread
    assert [i["text"] for i in familythread.items(person("ari")) if i["kind"] == "change"] == ["Ari added Venice Canals stroll on Sat 10:00 AM"]


# ---- roles ---------------------------------------------------------------------------------------------------------------------

@pytest.fixture
def crew(client):
    book(client)
    vi = addr("vi")
    invite(client, vi, "viewer")
    viewer = browser(client)
    sign_in(viewer, vi)
    return client, viewer


def test_a_viewer_reads_the_calendar_but_cannot_change_it(crew):
    owner, viewer = crew
    act = add(owner).json()["plan"]["act"]
    page = viewer.get("/trip/plan")
    assert page.status_code == 200 and data(page.text)["edit"] is False and "data-add" not in page.text and act in evs(page.text)
    for form in ({"op": "add", "day": "1", "start": "600", "end": "660", "title": "Mine", "kind": "fun"}, {"op": "edit", "act": act, "start": "700"}, {"op": "delete", "act": act}):
        assert viewer.post("/trip/plan/write", data=form, follow_redirects=False).status_code == 403
    assert viewer.post("/trip/plan/suggest", data={"id": "f0"}, follow_redirects=False).status_code == 403
    assert [(a.start, a.title) for a in cal.activities(person("ari"))] == [(600, "Venice Canals stroll")]


# ---- overlaps ---------------------------------------------------------------------------------------------------------------------

def ev(id, start, end, locked=False):
    return pv.Ev(id, 0, start, end, id, "fun", locked)


def test_overlaps_sit_two_across_and_the_rest_wait_in_a_count():
    shown, more = pv.lanes([ev("a", 600, 720), ev("b", 630, 700), ev("c", 640, 690), ev("d", 650, 680), ev("e", 900, 960)])
    lanes = {e.id: (lane, across) for e, lane, across in shown}
    assert lanes == {"a": (0, 2), "b": (1, 2), "e": (0, 1)}
    assert [(start, [e.id for e in hid]) for start, hid in more] == [(640, ["c", "d"])]


def test_a_booking_takes_its_lane_before_a_plan_does():
    shown, _ = pv.lanes([ev("plan", 600, 700), ev("flight", 600, 700, locked=True), ev("other", 600, 700)])
    assert {e.id: lane for e, lane, _ in shown} == {"flight": 0, "other": 1}


# ---- the rail ---------------------------------------------------------------------------------------------------------------------

def view_with(wet=(), plans=(), days=3, windows=(420, 1320)):
    dry = pv.Wx(70, 50, "Sunny", "sun", False, False)
    rainy = pv.Wx(60, 48, "Rain", "rain", False, False)
    d = [(i, date(2026, 12, 15 + i)) for i in range(days)]
    return pv.View("t", "Place", "", 2, "2 adults", "3", "days to go", d, [rainy if i in wet else dry for i in range(days)], [], [], list(plans), 420, 1320, 0, [], [], [], (), "admin",
                   {i: windows for i in range(days)})


def test_the_plus_picks_a_dry_day_first_the_quietest_first_and_never_over_anything():
    plans = [pv.Ev("a1", 1, 600, 660, "x", "fun"), pv.Ev("a2", 1, 840, 900, "y", "fun")]
    v = view_with(wet={0}, plans=plans)
    assert pv.pick_slot(v, "outdoors", 120) == (2, 600)                  # day 0 is wet, day 1 has two plans: day 2 is dry and empty
    assert pv.pick_slot(v, "food", 90, indoor=True) == (0, 720)          # a meal indoors may go on the wet day (the quietest), at noon
    held = replace(v, booked=[pv.Ev("b-x", 2, 570, 700, "Flight", "flight", True)])
    assert pv.pick_slot(held, "outdoors", 120) == (2, 840)               # day 2 is busy from 9:30 to 11:40: mid morning is taken, so 2 PM


def test_a_slot_stays_inside_the_days_window_and_none_when_nothing_is_free():
    v = view_with(days=1, windows=(900, 1080))       # a day that only has 3 PM to 6 PM (the flight lands at 3)
    assert pv.pick_slot(v, "outdoors", 120)[1] >= 900
    assert pv.pick_slot(v, "outdoors", 240) is None


def test_the_rail_offers_sample_places_on_the_showcase_only_and_says_sample(booked, monkeypatch):
    page = booked.get("/trip/plan").text
    assert "Fits you" in page and 'class="smp"' in page and 'data-sug="f0"' in page
    assert data(page)["sugg"][0]["id"] == "f0" and data(page)["showcase"] is True
    monkeypatch.setattr(showcase, "on", lambda: False)
    page = booked.get("/trip/plan").text
    assert "Fits you" not in page and "Others went" not in page and data(page)["sugg"] == []


def test_the_plus_drops_a_suggestion_into_a_free_slot_and_tells_where(booked):
    r = booked.post("/trip/plan/suggest", data={"id": "f0"})
    assert r.status_code == 200
    j = r.json()
    assert j["plan"]["kind"] == "food" and j["plan"]["end"] - j["plan"]["start"] == 90 and re.fullmatch(r"\w{3} \d+ · \d+:\d\d [AP]M", j["landed"])
    assert [a.title for a in cal.activities(person("ari"))] == [j["toast"].split(" added")[0]]
    assert booked.post("/trip/plan/suggest", data={"id": "nope"}).status_code == 422


def test_fits_you_follows_what_the_family_said_it_likes(booked):
    from gitaway import interests
    interests.save(person("ari"), ["seafood"])
    v = pv.view(person("ari"), lambda **k: "")
    assert v.interests == ("seafood",) and [s["title"] for s in pv.fits(v, pv.suggestions(v))] == ["Pier Oyster Bar"]      # the sample trip is Los Angeles


# ---- planning together ------------------------------------------------------------------------------------------------------------

def test_the_drawer_lists_the_family_with_roles_and_the_admin_sees_the_waiting_invites(crew):
    owner, viewer = crew
    mail = addr("wait")
    invite(owner, mail, "editor")
    page = owner.get("/trip/plan").text
    drawer = re.search(r'<aside[^>]*id="pl-side".*?</aside>', page, re.S).group(0)
    assert "Admin" in drawer and "Viewer" in drawer and "(you)" in drawer
    assert mail in drawer and "/join/" in drawer and "Invite someone" in drawer
    assert mail not in viewer.get("/trip/plan").text and "Invite someone" not in viewer.get("/trip/plan").text      # only an admin sees the invites


def test_what_changed_lists_the_plan_changes_the_family_was_told(booked):
    act = add(booked).json()["plan"]["act"]
    write(booked, op="edit", act=act, start="780", end="840")
    page = booked.get("/trip/plan").text
    assert 'id="pl-changes"' in page and "added Venice Canals stroll" in page.replace("&amp;", "&")


# ---- the way in ------------------------------------------------------------------------------------------------------------------

def test_the_save_moment_and_share_are_on_the_page(booked):
    page = booked.get("/trip/plan").text
    assert 'id="pl-save"' in page and 'id="pl-sheet"' in page and 'id="sh-open"' in page and 'href="/trip/share"' in page


def test_the_viewport_of_a_long_trip_is_a_window_of_seven_days(booked):
    html = booked.get("/trip/plan/cal?view=week&frm=0&cols=3").text
    assert html.count('data-day=') >= 3 and 'data-state="week|0|3|0"' in html
    day = booked.get("/trip/plan/cal?view=day&day=9").text
    assert 'data-state="day|0|7|4"' in day and html.count('class="col') == 3


def test_a_write_made_while_looking_at_another_day_lands_on_the_plans_own_day(booked):
    j = write(booked, op="add", day="1", start="600", end="660", title="Venice Canals stroll", kind="outdoors", view="day", frm="0", cols="5", vday="3").json()
    assert j["plan"]["day"] == 1 and [a.day for a in cal.activities(person("ari"))] == [1]
    assert 'data-state="day|0|5|3"' in j["grid"] and 'data-title="Venice Canals stroll"' not in j["grid"]      # the grid answers for the day being looked at (day 3), the plan is on day 1


def test_the_day_view_names_its_day_in_the_chips_and_keeps_a_header_row_only_to_say_rain(booked, monkeypatch):
    day = booked.get("/trip/plan/cal?view=day&day=2").text
    assert 'class="g-head"' not in day and day.count('class="dchip"') == 5 and 'aria-pressed="true"' in day
    dry = pv.Wx(74, 52, "Sunny", "sun", False, False, "Forecast · MET Norway")
    wet = replace(dry, word="Rain", cond="rain")
    monkeypatch.setattr(pv, "sky", lambda t: ([dry, dry, wet, dry, dry], []))
    assert "Rain likely" in booked.get("/trip/plan/cal?view=day&day=2").text


# ---- F-293 (D-946): the secondary things are on demand, in one More menu ------------------------------------------------------------

def more_menu(html):
    """The trip's More menu: its button and its menu, as html."""
    start = html.rfind("<div", 0, html.index('id="pl-more"'))
    return html[start:html.index("</div>", html.index('id="pl-more-menu"')) + 6]


def test_the_trip_header_holds_one_more_button_and_shares_planning_together_and_save_wait_inside_it(booked):
    page = booked.get("/trip/plan").text
    more = more_menu(page)
    assert more.count('data-more="1"') == 1 and re.search(r'aria-haspopup="menu"[^>]*aria-expanded="false"|aria-expanded="false"[^>]*aria-haspopup="menu"', more)
    labels = re.findall(r'role="menuitem"[^>]*>(?:<svg.*?</svg>)?(?:<span[^>]*>)?([^<]+)', more, re.S)
    assert [x.strip() for x in labels if x.strip() and not x.strip().isdigit()] == ["Plan together", "Save plan", "Share to Instagram"]
    for what in ('id="pl-together"', 'id="pl-save"', 'id="sh-open"'):
        assert what in more and page.count(what) == 1, what          # each only inside the menu: nothing of them at rest
    assert 'class="dock' not in page and 'class="pl-bar' not in page      # the phone's floating Together/Save bar and the desktop's bar of them are gone


def test_a_viewer_s_more_menu_has_no_share(crew):
    owner, viewer = crew
    more = more_menu(viewer.get("/trip/plan").text)
    assert 'id="pl-together"' in more and 'id="pl-save"' in more and "sh-open" not in more and "Share to Instagram" not in more
