"""F-021 review fixes: cookie budget, the booked trip's real length, titles, undo and escaping."""

import dataclasses
import re

from fh_saas.utils_sql import insert_only

from gitaway import community, familydb, itineraries, session as ses, tripcal as cal
from tests.test_calendar import FORM, add, book
from tests.test_forks import OTHER, SD, TRIP, apply, fork, plan_keys, titles
from tests.test_signin import person, session_data, sign_in, stored_booking, stored_calendar, tid

THREE_NIGHTS = dict(d="2026-10-16", r="2026-10-19", a="2", k="4,7")
TWENTY_DAYS = dict(d="2026-10-16", r="2026-11-04", a="2", k="4,7")


def cookie_size(client):
    return len(client.cookies.get("session_") or "")


# ---- cookie budget -------------------------------------------------------------------------------------------------

def test_made_up_slugs_are_not_forked_or_saved(client):
    sign_in(client)
    for path in ("/trips/nope", "/trips/shared-0123456789"):
        client.post("/fork", data={"next": path})
        client.post("/save", data={"next": path})
        client.get(f"/signin?next={path}&intent=fork")
        client.get(f"/signin?next={path}&intent=save")
    assert ses.forks(session_data(client)) == [] and ses.saved(session_data(client)) == []


def test_a_busy_calendar_does_not_limit_forks_and_saves(client):
    """F-041: forks and saves live in the family's database, and so does the calendar (F-040): neither touches the cookie."""
    book(client)
    for i in range(40):
        if add(client, id=f"a{i + 1}", day=str(1 + i % 3), start="12:00", end="12:30", title=f"Plan number {i:02d} " + "x" * 20).status_code == 409:
            break
    for slug in (TRIP, OTHER, SD, "dog-friendly-big-sur-drive"):
        assert client.post("/fork", data={"next": f"/trips/{slug}"}, follow_redirects=False).status_code == 303
        assert client.post("/save", data={"next": f"/trips/{slug}"}, follow_redirects=False).status_code == 303
    assert len(ses.forks(session_data(client))) == 4 and len(ses.saved(session_data(client))) == 4
    assert client.get(f"/signin?next=/trips/{TRIP}&intent=fork", follow_redirects=False).status_code == 303


# ---- the booked trip's real length ---------------------------------------------------------------------------------

def day_heads(html):
    return len(re.findall(r'class="fk-day"', html))


def test_forks_follow_a_three_night_trip(client):
    book(client, **THREE_NIGHTS)
    fork(client)
    html = client.get(f"/forks?open={TRIP}").text
    assert day_heads(html) == 4 and "--n:4" in html
    keys = plan_keys(html)
    assert keys["d5s0"] == (False, True) and "After your trip ends" in html  # the fork's 5th day is past a 4-day trip
    apply(client, "d5s0", "d2s0")
    assert titles(client) == ["Venice Canals stroll"]


def test_forks_follow_a_twenty_day_trip_with_a_day_window(client):
    book(client, **TWENTY_DAYS)
    fork(client)
    html = client.get(f"/forks?open={TRIP}").text
    assert day_heads(html) == 20 and "--n:20" in html
    assert 'class="fk-scroll"' in html  # days sit in a scroller that shows a window, not one row of 20
    assert "fk-nav" in html
    assert plan_keys(html)["d5s0"][0] is True  # a day that exists on a long trip is open
    r = apply(client, "d5s0")
    assert r.status_code == 303 and titles(client) == ["Farmers Market brunch"]
    assert cal.trip_of(stored_booking()).return_.day == 4


# ---- titles ---------------------------------------------------------------------------------------------------------

def test_short_titles_never_exceed_the_limit_or_come_back_empty():
    long_word = "W" * 60
    assert cal._short(long_word) == "W" * cal.MAX_TITLE
    assert 0 < len(cal._short("Aaaa " + "b" * 60)) <= cal.MAX_TITLE
    assert cal._short("&" * 50) == "&" * cal.MAX_TITLE
    assert cal._short("   ") == "Plan"
    assert cal._short("Short one") == "Short one"
    cut = cal._short("Venice Beach Boardwalk & skate park and then the whole long afternoon")
    assert len(cut) <= cal.MAX_TITLE and not cut.endswith((" ", "&"))


# ---- undo -----------------------------------------------------------------------------------------------------------

def test_undo_only_removes_what_that_apply_added(client):
    book(client)
    client.post("/calendar/friends", data={"name": "Mom"})
    client.post("/calendar/live")
    fork(client)
    add(client, id="a9", title="Mine")
    first = apply(client, "d1s2")
    ids = re.search(r"applied=([a0-9,]+)", first.headers["location"]).group(1)
    own = [a["i"] for a in stored_calendar()["a"] if a["t"] == "Mine"]
    mom = [a["i"] for a in stored_calendar()["a"] if a.get("b") == "Mom"]
    client.post("/forks/undo", data={"ids": ",".join([*own, *mom]), "src": TRIP})  # a hand-made id list
    assert "Mine" in titles(client) and "Travel Town steam trains" in titles(client)
    client.post("/forks/undo", data={"ids": ids, "src": OTHER})  # the wrong fork
    assert "Santa Monica Pier & Pacific Park" in titles(client)
    client.post("/forks/undo", data={"ids": ids})  # no fork named
    assert "Santa Monica Pier & Pacific Park" in titles(client)
    r = client.post("/forks/undo", data={"ids": ids, "src": TRIP}, follow_redirects=False)
    assert r.status_code == 303 and "Santa Monica Pier & Pacific Park" not in titles(client)
    assert "Mine" in titles(client)


def test_the_applied_banner_posts_the_fork_with_its_ids(client):
    book(client)
    fork(client)
    html = client.get(apply(client, "d1s2").headers["location"]).text
    assert 'name="src" value="%s"' % TRIP in html


# ---- escaping -------------------------------------------------------------------------------------------------------

def test_a_hostile_fork_title_and_author_stay_text(client, monkeypatch):
    base = itineraries.get(TRIP)
    days = [dataclasses.replace(d, stops=[dataclasses.replace(s, title="<script>alert(1)</script> bite") if i == 3 else s for i, s in enumerate(d.stops)])
            if d.n == 1 else d for d in base.days]
    evil = dataclasses.replace(base, slug="evil-trip", title="<img src=x onerror=alert(2)>", author='"><script>alert(3)</script>', days=days)
    monkeypatch.setitem(itineraries.ITINERARIES, "evil-trip", evil)
    book(client)
    fork(client, "evil-trip")
    for url in ("/forks", "/forks?open=evil-trip"):
        html = client.get(url).text
        assert "<script>alert" not in html and "<img src=x" not in html
        assert "&lt;img src=x" in html
    r = apply(client, "d1s2", "d1s3", slug="evil-trip")
    html = client.get(r.headers["location"]).text
    assert "<script>alert" not in html and "onerror=alert(2)>" not in html.replace("&lt;", "")
    cal_html = client.get("/calendar?view=days").text
    assert "<script>alert" not in cal_html


# ---- the flight windows, through the calendar and the preview ---------------------------------------------------------

def test_the_calendar_accepts_a_plan_before_you_land(client):
    book(client)
    assert add(client, day="0", start="07:00", end="07:45").status_code == 303   # F-086: overlapping the flight is fine
    assert add(client, id="a2", day="0", start="10:00", end="11:00").status_code == 303


def test_the_calendar_accepts_a_plan_close_to_the_flight_home(client):
    book(client, **THREE_NIGHTS)
    assert add(client, day="3", start="12:30", end="13:15").status_code == 303  # the flight home leaves at 2:10 PM
    assert add(client, id="a2", day="3", start="08:00", end="09:00", title="Brunch").status_code == 303
    assert add(client, id="a3", day="2", start="17:00", end="19:00", title="Dinner").status_code == 303  # other days are free


def test_moving_a_plan_later_than_the_flight_home_is_allowed_too(client):
    book(client, **THREE_NIGHTS)
    add(client, id="a1", day="1", start="10:00", end="11:00")
    r = client.post("/calendar/activities/a1/move", data={"day": "3", "start": "16:00", "end": "17:00"}, follow_redirects=False)
    assert r.status_code == 303
    assert any(a["i"] == "a1" and a["d"] == 3 for a in stored_calendar()["a"])


def test_a_fork_plan_after_the_flight_home_is_kept_and_can_be_applied(client):
    book(client, **THREE_NIGHTS)
    fork(client)
    html = client.get(f"/forks?open={TRIP}").text
    keys = plan_keys(html)
    assert keys["d4s2"] == (True, False)  # Pool time, 5 to 7 PM on the day the 2:10 PM flight leaves: kept (F-086)
    apply(client, "d4s2")
    assert [a["t"] for a in stored_calendar()["a"]] == ["Pool time"] or len(stored_calendar()["a"]) == 1


def test_day_arrows_are_not_offered_when_the_trip_is_three_days_or_fewer(client):
    book(client, d="2026-10-16", r="2026-10-18", a="2", k="4,7")
    fork(client)
    html = client.get(f"/forks?open={TRIP}").text
    assert day_heads(html) == 3 and "fk-nav" not in html


def test_a_creator_trip_can_be_forked_saved_and_applied(client):
    book(client)
    client.post("/creators", data={"link": "https://www.youtube.com/watch?v=our-la-family-week"})
    client.post("/creators/draft", data={"form": "1", "do": "submit", "ok1": "1", "ok2": "1", "title": "Sun, tacos & tides"})
    slug = community.rows(kind="creator", owner=tid("ari"))[0]["slug"]
    assert client.post("/fork", data={"next": f"/trips/{slug}"}, follow_redirects=False).status_code == 303
    assert client.post("/save", data={"next": f"/trips/{slug}"}, follow_redirects=False).status_code == 303
    assert "Sun, tacos &amp; tides" in client.get("/forks").text
    html = client.get(f"/forks?open={slug}").text
    keys = plan_keys(html)
    assert keys and any(checked for checked, _ in keys.values())
    free = [k for k, (checked, _) in keys.items() if checked]
    r = apply(client, *free, slug=slug)
    assert r.status_code == 303 and "applied=" in r.headers["location"]
    assert len(titles(client)) == len(free)


# ---- Mom and old items respect the same window ------------------------------------------------------------------------

TWO_NIGHTS = dict(d="2026-10-16", r="2026-10-18", a="2", k="4,7")  # the last day is index 2, where Mom's scripted add happens


def test_moms_scripted_add_stays_inside_the_flight_window_on_a_short_trip(client):
    book(client, f="f2", **TWO_NIGHTS)  # f2's flight home leaves at 12:30 PM, so the last day closes at 10:30 AM
    client.post("/calendar/friends", data={"name": "Mom"})
    client.post("/calendar/live")
    mom = [a for a in stored_calendar()["a"] if a.get("b") == "Mom"]
    assert len(mom) == 1 and mom[0]["d"] == 2
    b = stored_booking()
    blocks = cal.booked_blocks(b, cal.trip_of(b))
    assert cal.window_problem(blocks, mom[0]["d"], mom[0]["s"], mom[0]["e"]) is None
    assert mom[0]["e"] <= 10 * 60 + 30


def test_moms_add_is_skipped_when_no_slot_fits_the_window(client, monkeypatch):
    book(client, f="f2", **TWO_NIGHTS)
    monkeypatch.setattr(cal, "LIVE_LEN", 600)  # ten hours cannot fit anywhere on that last day
    client.post("/calendar/friends", data={"name": "Mom"})
    client.post("/calendar/live")
    assert not [a for a in stored_calendar()["a"] if a.get("b") == "Mom"]


def test_renaming_and_moving_an_older_item_late_both_work(client):
    book(client, f="f2", **{"d": "2026-10-16", "r": "2026-10-20", "a": "2", "k": "4,7"})  # a 12:30 PM flight: the last day closes at 10:30 AM
    with ses.family(person()) as fam:  # an item from before that rule: put in the table directly, past the check
        insert_only(fam.db, "activities", {"pk": f"{fam.trip_id}~~a1", "trip_id": fam.trip_id, "scope": "", "act_id": "a1", "seq": 1, "day": 4, "start_min": 540,
                                           "end_min": 645, "title": "Old plan", "kind": "fun", "author": "", "added_by": "", "gone": 0, "created_at": familydb.now()}, ["pk"])
        familydb.run(fam.db, "INSERT OR IGNORE INTO cal_state (pk, trip_id, scope, q, live) VALUES (:pk, :t, '', 1, 0)", pk=f"{fam.trip_id}~", t=fam.trip_id)
        fam.db.conn.commit()
    r = client.post("/calendar/activities/a1", data={"title": "Renamed", "day": "4", "start": "09:00", "end": "10:45", "kind": "fun"}, follow_redirects=False)
    assert r.status_code == 303 and "Renamed" in titles(client)
    r = client.post("/calendar/activities/a1", data={"title": "Renamed", "day": "4", "start": "09:15", "end": "11:00", "kind": "fun"}, follow_redirects=False)
    assert r.status_code == 303  # F-086: moving it later than the flight window is allowed too
