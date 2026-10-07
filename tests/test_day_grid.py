"""F-097 / F-098: the day as a time grid, through HTTP. A plan is a block whose place and height are its time, overlaps sit side by side, bookings are quiet lines at their
times, today has a now line, a blank day keeps Talk / Paste, a viewer gets no gestures; and the write behind them (POST /trip/canvas/plan: edit, undo, delete) goes through
the calendar's own rules. The trip is the demo booking (Fri 16 fly in, Sat 17 Universal, Sun 18 free, Mon 19 California Adventure, Tue 20 fly home)."""

import json
import re

from gitaway import tripcal as cal
from tests.test_canvas import azure, rows  # noqa: F401 - fixtures
from tests.test_canvas_pages import added, crew  # noqa: F401 - fixtures
from tests.test_signin import person
from tests.test_trip_canvas import bare, tag, text, trip, uni_id  # noqa: F401 - fixtures


def day(client, n):
    r = client.get(f"/trip/canvas?day={n}")
    assert r.status_code == 200
    return bare(r.text)


def blocks(page):
    """[{attribute: value}] of every plan block on the grid (an element whose class list starts with cz-gb)."""
    from html import unescape
    out = []
    for m in re.finditer(r"<(?:div|a)\b((?:[^>\"']|\"[^\"]*\"|'[^']*')*)>", page):
        attrs = {k: unescape(a or b) for k, a, b in re.findall(r"""([\w-]+)=(?:"([^"]*)"|'([^']*)')""", m.group(1))}
        if "cz-gb" in attrs.get("class", "").split():
            out.append(attrs)
    return out


def style(attrs):
    return dict(re.findall(r"--(\w+):([\d.]+)", attrs["style"]))


def plan(session, title, start, end, day=2, kind="fun"):
    return cal.add_activity(session, day=day, start=start, end=end, title=title, kind=kind)


# ---- the grid ------------------------------------------------------------------------------------------------------------

def test_a_plan_is_a_block_whose_place_and_height_are_its_time(trip):
    me = person("ari")
    lunch = plan(me, "Lunch at the pier", 12 * 60, 13 * 60 + 30)
    page = day(trip, 2)
    grid = tag(page, "cz-grid")
    assert 'data-lo="420"' in grid and 'data-hi="1320"' in grid and "--n:15" in grid       # 7 AM to 10 PM
    (b,) = blocks(page)
    assert (b["data-act"], b["data-s"], b["data-e"], b["data-title"]) == (lunch.id, "720", "810", "Lunch at the pier")
    assert style(b) == {"s": "300", "l": "90", "lane": "0", "lanes": "1"}                  # 300 minutes after 7 AM, 90 long
    assert "12:00 – 1:30 PM" in text(page) and "Lunch at the pier" in text(page)


def test_a_park_day_is_one_tall_block_that_opens_its_block_and_shows_its_parts(trip):
    page = day(trip, 1)
    (b,) = blocks(page)
    assert "is-park" in b["class"] and b["data-steps"] == "16" and style(b)["l"] == "720"       # 9 AM to 9 PM
    for part in ("Lower Lot", "Lunch", "Harry Potter world", "Upper Lot"):
        assert part in page
    assert f'href="/trip/canvas?block={uni_id()}"' in page and 'data-zk="blk-' in page


def test_overlaps_sit_side_by_side_and_a_later_plan_starts_a_new_row(trip):
    me = person("ari")
    plan(me, "Pool", 10 * 60, 12 * 60)
    plan(me, "Spa", 11 * 60, 12 * 60 + 30)
    plan(me, "Dinner", 18 * 60, 19 * 60)
    got = {b["data-title"]: style(b) for b in blocks(day(trip, 2))}
    assert (got["Pool"]["lane"], got["Pool"]["lanes"]) == ("0", "2") and (got["Spa"]["lane"], got["Spa"]["lanes"]) == ("1", "2")
    assert (got["Dinner"]["lane"], got["Dinner"]["lanes"]) == ("0", "1")


def test_bookings_are_quiet_lines_at_their_times_beside_the_plans(trip):
    me = person("ari")
    plan(me, "Beach walk", 10 * 60, 11 * 60, day=0)
    page = day(trip, 0)
    lines = re.findall(r'<a\b[^>]*class="cz-bk cz-gbk"[^>]*>.*?</a>', page, re.S)
    assert len(lines) == 2 and "has-bk" in tag(page, "cz-grid")
    flight, hotel = lines
    assert "8:05 AM" in text(flight) and 'href="/trip/canvas?day=0&amp;booked=b-out"' in flight and "--s:65" in flight       # 8:05 is 65 minutes after 7
    assert "3:00 PM" in text(hotel) and "Check in" in text(hotel) and 'href="/trip/canvas?day=0&amp;booked=b-in"' in hotel and "--s:480" in hotel
    assert 'data-kind="flight"' in flight and 'data-kind="hotel"' in hotel                                                    # the Plans | Hotels | Flights filter still reads them


def test_bookings_close_together_slide_apart_but_keep_their_true_time(trip):
    from gitaway.pages import tripcanvas as tc
    x = lambda i, s: cal.Block(i, 0, s, s + 30, i, "booked", True, "bed")  # noqa: E731
    got = tc.grid_bookings([x("b1", 600), x("b2", 610), x("b3", 700)])
    assert [(b.id, t) for b, t in got] == [("b1", 600), ("b2", 640), ("b3", 700)]


def test_the_grid_is_wide_enough_for_an_early_and_a_late_plan_and_never_cut(trip):
    me = person("ari")
    plan(me, "Late swim", 21 * 60 + 30, 22 * 60)
    grid = tag(day(trip, 2), "cz-grid")
    assert 'data-hi="1320"' in grid
    from gitaway.pages import tripcanvas as tc
    lo, hi = tc.grid_range([cal.Activity("a1", 2, 5 * 60 + 30, 23 * 60, "x", "fun")], [])
    assert (lo, hi) == (5 * 60, 23 * 60)


def test_a_blank_day_gives_an_editor_the_grid_under_one_compact_talk_and_paste_row(trip):
    """F-101: empty time can be held on a blank day too; the big empty card is a one-row card above the grid. A viewer keeps the plain blank view."""
    page = day(trip, 2)
    assert 'id="cz-grid"' in page and blocks(page) == [] and 'cz-say-compact' in tag(page, "cz-empty")
    assert page.index('id="cz-say-talk"') < page.index('id="cz-grid"') and 'id="cz-say-paste"' in page
    assert "Nothing planned yet" not in text(page) and "paste it from a message" not in text(page)
    assert 'class="cz-gadd' not in page and re.search(r'data-next="\d+"', tag(page, "cz-grid"))       # the keyboard's "Add a plan" is drawn by the script; the grid carries the calendar's next number


def test_a_viewer_keeps_the_plain_blank_day(crew, azure):
    ari, viewer = crew
    added(ari)
    seen = bare(viewer.get("/trip/canvas?day=2").text)
    assert 'id="cz-grid"' not in seen and "Nothing planned yet" in text(seen) and 'id="cz-say-talk"' not in seen
    assert not re.search(r'data-next="\d', tag(bare(viewer.get("/trip/canvas?day=1").text), "cz-grid"))


def test_a_blank_day_with_bookings_draws_them_as_lines_on_the_editors_grid(trip):
    page = day(trip, 0)
    assert 'id="cz-grid"' in page and blocks(page) == [] and page.count('class="cz-bk cz-gbk"') == 2 and 'id="cz-say-talk"' in page


def test_today_has_a_now_line_on_the_grid(trip, monkeypatch):
    from datetime import datetime, timezone
    from gitaway import catalog
    now = datetime(2026, 10, 17, 19, 40, tzinfo=timezone.utc)      # Saturday 12:40 PM in Los Angeles: day 1, the Universal day
    monkeypatch.setattr(catalog, "now_utc", lambda: now)
    monkeypatch.setattr(catalog, "today", lambda: now.astimezone(catalog.TZ).date())
    page = day(trip, 1)
    line = tag(page, "cz-nowline")
    assert 'data-m="760"' in line and "--s:340" in line
    assert 'id="cz-nowline"' not in day(trip, 3)


def test_the_filters_kinds_and_day_toggle_stay(trip):
    page = day(trip, 1)
    for ident in ("cz-z-day", "cz-z-week", "cz-sos"):
        assert f'id="{ident}"' in page
    assert 'class="cz-kinds"' in page and 'class="cz-filters"' in page and 'data-prev=' in page and 'data-next=' in page
    (b,) = blocks(page)
    assert b["data-kind"] == "block" or b["data-kind"] == "plan"
    assert "data-who" in b and "data-lists" in b            # the who and list filters light a block when any of its steps match


def test_an_editor_can_lift_blocks_and_has_a_keyboard_way_in(trip):
    me = person("ari")
    plan(me, "Lunch", 12 * 60, 13 * 60)
    page = day(trip, 2)
    assert 'data-edit="1"' in trip.get("/trip/canvas?day=2").text and 'class="cz-gb-grip"' in page
    assert 'class="sr-only cz-gb-menubtn">Change Lunch<' in page
    (b,) = blocks(page)
    assert b["data-talk"].startswith(f"/trip/talk?act={b['data-act']}") and b["data-steps"] == "0"      # F-098: the hold menu's Chat, and what a delete would take with it
    assert 'src="/assets/js/day_menu.js' in trip.get("/trip/canvas?day=2").text
    assert re.search(r'<a [^>]*href="/trip/talk\?act=%s[^"]*"[^>]*class="cz-gb-open"' % b["data-act"], page)         # a tap on a plan opens its chat for editors too


def test_a_viewer_gets_the_grid_and_no_gestures(crew, azure):
    ari, viewer = crew
    added(ari)
    plan(person("ari"), "Lunch", 12 * 60, 13 * 60)
    page = bare(viewer.get("/trip/canvas?day=2").text)
    assert 'data-edit="1"' not in viewer.get("/trip/canvas?day=2").text and 'id="cz-grid"' in page
    assert "cz-gb-grip" not in page and "cz-gb-menubtn" not in page
    (b,) = blocks(page)
    assert "data-talk" not in page and re.search(r'<a [^>]*href="/trip/talk\?act=[^"]*"[^>]*class="cz-gb-open"', page)                # a tap on a plan goes to its chat, for a viewer too
    park = bare(viewer.get("/trip/canvas?day=1").text)
    assert "cz-gb-grip" not in park and f'href="/trip/canvas?block={uni_id()}"' in park


# ---- the write ------------------------------------------------------------------------------------------------------------

def edit(client, act, **fields):
    return client.post("/trip/canvas/plan", data={"op": "edit", "act": act, **fields}, headers={"X-Canvas": "1"})


def test_moving_a_plan_saves_it_and_answers_with_the_toast_and_an_undo(trip):
    me = person("ari")
    a = plan(me, "Lunch", 12 * 60, 13 * 60)
    r = edit(trip, a.id, start=12 * 60 + 30, end=13 * 60 + 30)
    got = r.json()
    assert r.status_code == 200 and got["toast"] == "Lunch moved to 12:30 PM" and got["plan"]["start"] == 750
    assert got["undo"] == {"act": a.id, "day": 2, "start": 720, "end": 780, "title": "Lunch", "after": {"day": 2, "start": 750, "end": 810, "title": "Lunch"}}
    assert cal.get_activity(me, a.id).start == 750
    back = trip.post("/trip/canvas/plan", data={"op": "undo", "undo": json.dumps(got["undo"])}, headers={"X-Canvas": "1"})
    assert back.json()["toast"] == "Put back" and cal.get_activity(me, a.id).start == 720


def test_resizing_takes_five_minutes_and_says_when_it_now_ends(trip):
    me = person("ari")
    a = plan(me, "Lunch", 12 * 60, 13 * 60)
    got = edit(trip, a.id, start=12 * 60, end=12 * 60 + 35).json()
    assert got["toast"] == "Lunch now ends 12:35 PM" and cal.get_activity(me, a.id).end == 12 * 60 + 35
    assert edit(trip, a.id, start=12 * 60, end=12 * 60 + 15).json()["plan"]["end"] == 12 * 60 + 15


def test_dragging_the_top_knob_changes_only_the_start_through_the_same_rules_and_says_so(trip):
    """F-110: the start edge is a resize too: same route, same refusals, the card coalesced, its own toast, and an Undo that puts the start back."""
    me = person("ari")
    a = plan(me, "Lunch", 12 * 60, 13 * 60)
    got = edit(trip, a.id, start=12 * 60 + 20, end=13 * 60).json()
    assert got["toast"] == "Lunch now starts 12:20 PM" and (cal.get_activity(me, a.id).start, cal.get_activity(me, a.id).end) == (12 * 60 + 20, 13 * 60)
    assert edit(trip, a.id, start=13 * 60, end=13 * 60).status_code == 422               # not shorter than the minimum
    assert edit(trip, a.id, start=6 * 60, end=13 * 60).status_code == 422                # not before the day's first hour
    back = trip.post("/trip/canvas/plan", data={"op": "undo", "undo": json.dumps(got["undo"])}, headers={"X-Canvas": "1"})
    assert back.json()["toast"] == "Put back" and cal.get_activity(me, a.id).start == 12 * 60


def test_a_rename_is_trimmed_and_a_nothing_change_says_nothing(trip):
    me = person("ari")
    a = plan(me, "Lunch", 12 * 60, 13 * 60)
    got = edit(trip, a.id, title="  Tacos   at the pier ").json()
    assert got["toast"] == "Renamed to Tacos at the pier" and cal.get_activity(me, a.id).title == "Tacos at the pier"
    same = edit(trip, a.id, title="Tacos at the pier").json()
    assert same["toast"] == "" and same["undo"] is None


def test_the_calendars_refusals_come_back_plainly_and_change_nothing(trip):
    me = person("ari")
    a = plan(me, "Lunch", 12 * 60, 13 * 60)
    for fields, words in (({"title": ""}, "Give it a title."), ({"title": "x" * 41}, "40 characters"), ({"start": 600, "end": 600}, "after the start"),
                          ({"start": 300, "end": 400}, "Plan between"), ({"start": "nine"}, "not one we can read"), ({"end": 12 * 60 + 5}, "15 minutes")):
        r = edit(trip, a.id, **fields)
        assert r.status_code == 422 and words in r.json()["error"], fields
    assert (cal.get_activity(me, a.id).start, cal.get_activity(me, a.id).title) == (720, "Lunch")
    assert edit(trip, "b-out", start=600, end=700).status_code == 422 and edit(trip, "a99", start=600, end=700).status_code == 422


def test_delete_says_how_much_went_with_a_park_day_and_undo_puts_it_all_back(trip):
    me = person("ari")
    a = plan(me, "Lunch", 12 * 60, 13 * 60)
    got = trip.post("/trip/canvas/plan", data={"op": "delete", "act": a.id}, headers={"X-Canvas": "1"}).json()
    assert got["toast"] == "Lunch deleted" and got["undo"] == {"deleted": a.id} and cal.get_activity(me, a.id) is None
    back = trip.post("/trip/canvas/plan", data={"op": "undo", "undo": json.dumps(got["undo"])}, headers={"X-Canvas": "1"}).json()
    assert back["toast"] == "Lunch is back" and cal.get_activity(me, a.id).start == 720
    uni = uni_id()
    park = trip.post("/trip/canvas/plan", data={"op": "delete", "act": uni}, headers={"X-Canvas": "1"}).json()
    assert park["toast"] == "Universal Studios Hollywood and its 16 steps deleted"
    trip.post("/trip/canvas/plan", data={"op": "undo", "undo": json.dumps(park["undo"])}, headers={"X-Canvas": "1"})
    assert cal.get_activity(me, uni) is not None and len(rows(me, "SELECT * FROM block_steps WHERE act_id = :a", a=uni)) == 16


def post_plan(client, **fields):
    return client.post("/trip/canvas/plan", data=fields, headers={"X-Canvas": "1"})


def test_adding_a_plan_by_touch_saves_it_with_the_calendars_rules_and_undo_removes_it(trip):
    """F-101: op=add makes a plan on the day at the minutes the finger chose; Undo ({"added": id}) takes it away."""
    me = person("ari")
    r = post_plan(trip, op="add", day=2, start=14 * 60 + 15, end=15 * 60 + 15, title="  Pier   walk ")
    got = r.json()
    assert r.status_code == 200 and got["toast"] == "Pier walk added" and got["plan"]["start"] == 14 * 60 + 15 and got["plan"]["end"] == 15 * 60 + 15
    a = cal.get_activity(me, got["plan"]["act"])
    assert (a.day, a.title, a.kind) == (2, "Pier walk", "fun") and got["undo"] == {"added": a.id, "after": {"day": 2, "start": 14 * 60 + 15, "end": 15 * 60 + 15, "title": "Pier walk"}}
    page = day(trip, 2)
    assert [b["data-title"] for b in blocks(page)] == ["Pier walk"]
    back = post_plan(trip, op="undo", undo=json.dumps(got["undo"])).json()
    assert back["toast"] == "Pier walk removed" and cal.get_activity(me, a.id) is None


def test_adding_a_plan_refuses_what_the_calendar_refuses_and_saves_nothing(trip):
    me = person("ari")
    base = len(cal.activities(me))
    for fields, words in (({"title": ""}, "Give it a title."), ({"title": "x" * 41}, "40 characters"), ({"day": 99}, "inside your trip"), ({"day": "x"}, "Pick a day"),
                          ({"start": 21 * 60 + 30, "end": 22 * 60 + 30}, "Plan between"), ({"start": "nine"}, "not one we can read"), ({"end": ""}, "not one we can read")):
        r = post_plan(trip, **{"op": "add", "day": 2, "start": 600, "end": 660, "title": "Ok", **fields})
        assert r.status_code == 422 and words in r.json()["error"], fields
    assert len(cal.activities(me)) == base


def test_a_viewer_cannot_add_a_plan_and_the_grid_offers_it_only_to_editors(crew, azure):
    ari, viewer = crew
    added(ari)
    plan(person("ari"), "Lunch", 12 * 60, 13 * 60)
    base = len(cal.activities(person("ari")))
    assert post_plan(viewer, op="add", day=2, start=600, end=660, title="Sneaky").status_code == 403
    assert len(cal.activities(person("ari"))) == base
    assert 'data-edit="1"' in ari.get("/trip/canvas?day=2").text and 'data-edit' not in viewer.get("/trip/canvas?day=2").text.split('id="cz"')[1].split(">")[0]


def test_an_undo_that_is_not_ours_is_refused(trip):
    for undo in ("", "nope", json.dumps({"act": "a1", "day": "x"}), json.dumps({"deleted": "a99"})):
        r = trip.post("/trip/canvas/plan", data={"op": "undo", "undo": undo}, headers={"X-Canvas": "1"})
        assert r.status_code == 422 and r.json()["error"], undo


def test_without_script_a_write_goes_back_to_the_day_and_a_viewer_is_refused(crew, azure):
    ari, viewer = crew
    added(ari)
    a = plan(person("ari"), "Lunch", 12 * 60, 13 * 60)
    r = ari.post("/trip/canvas/plan", data={"op": "edit", "act": a.id, "start": 750, "end": 810, "next": "/trip/canvas?day=2"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/trip/canvas?day=2" and cal.get_activity(person("ari"), a.id).start == 750
    assert viewer.post("/trip/canvas/plan", data={"op": "edit", "act": a.id, "start": 600, "end": 660}, headers={"X-Canvas": "1"}).status_code == 403
    assert viewer.post("/trip/canvas/plan", data={"op": "delete", "act": a.id}, headers={"X-Canvas": "1"}).status_code == 403
    assert cal.get_activity(person("ari"), a.id).start == 750
