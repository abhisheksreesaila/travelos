"""F-021 review fixes: cookie budget, the booked trip's real length, titles, undo and escaping."""

import dataclasses
import re

from gitaway import itineraries, session as ses, tripcal as cal
from tests.test_calendar import FORM, add, book
from tests.test_forks import OTHER, SD, TRIP, apply, fork, plan_keys, titles
from tests.test_signin import session_data, sign_in

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
    data = session_data(client)
    assert "forks" not in data and "saves" not in data


def test_forks_and_saves_are_refused_before_the_cookie_overflows(client):
    book(client)
    for i in range(40):
        r = add(client, id=f"a{i + 1}", day=str(1 + i % 3), start="12:00", end="12:30", title=f"Plan number {i:02d} " + "x" * 20)
        if r.status_code == 409:
            break
    refused = []
    for slug in (TRIP, OTHER, SD, "dog-friendly-big-sur-drive"):
        r = client.post("/fork", data={"next": f"/trips/{slug}"}, follow_redirects=False)
        refused.append(r.status_code)
        assert r.status_code in (303, 409)
        r2 = client.post("/save", data={"next": f"/trips/{slug}"}, follow_redirects=False)
        refused.append(r2.status_code)
        assert len(str(session_data(client)).replace("'", '"')) <= ses.BUDGET + 200
        assert cookie_size(client) <= 3600
    assert 409 in refused, "a nearly full cookie must say no"
    page = client.post("/fork", data={"next": f"/trips/{SD}"})
    assert page.status_code == 409 and "full" in page.text


def test_signing_in_to_fork_with_no_room_says_so(client):
    sign_in(client)
    book(client)
    for i in range(80):
        if add(client, id=f"a{i + 1}", day=str(1 + i % 3), start="12:00", end="12:30", title=f"Plan number {i:02d} " + "x" * 20).status_code == 409:
            break
    for i in range(30):  # then small notes, until not even one more fits
        client.post("/calendar/notes", data={"id": f"n{900 + i}", "text": "y" * max(1, 40 - 15 * (i // 10))})
    r = client.get(f"/signin?next=/trips/{TRIP}&intent=fork", follow_redirects=False)
    assert r.status_code == 409 and "full" in r.text


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
    assert "Mon 19" not in html or "Mon 19 ·" in html
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
    assert cal.trip_of(session_data(client)["bookings"]["ari"]).return_.day == 4


# ---- titles ---------------------------------------------------------------------------------------------------------

def test_short_titles_never_exceed_the_limit_or_come_back_empty():
    long_word = "W" * 60
    assert cal._short(long_word) == "W" * cal.MAX_TITLE
    assert 0 < len(cal._short("Aaaa " + "b" * 60)) <= cal.MAX_TITLE
    assert cal._short("&" * 50) == "&" * cal.MAX_TITLE or cal._short("&" * 50)
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
    own = [a["i"] for a in session_data(client)["cal"]["ari"]["a"] if a["t"] == "Mine"]
    mom = [a["i"] for a in session_data(client)["cal"]["ari"]["a"] if a.get("b") == "Mom"]
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
