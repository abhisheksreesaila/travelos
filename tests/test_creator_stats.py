"""F-192: a creator's stats. Readers are counted without cookies and without keeping anything personal; every check goes through the HTTP seam or reads the table itself."""

import re
import sqlite3
from datetime import date, timedelta

import pytest
from sqlalchemy import text

from gitaway import affiliate, auth, community, stats
from tests.live_trips import live_trip
from tests.pagebody import without_bar
from tests.test_signin import sign_in

CHROME = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Version/17.0 Mobile/15E148 Safari/604.1"
FIREFOX = "Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0"
TODAY = date(2026, 11, 6)


@pytest.fixture(autouse=True)
def live(monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setattr(stats, "_today", lambda: TODAY)
    stats.reset()


def read(client, slug, ip="203.0.113.7", ua=CHROME):
    return client.get(f"/trips/{slug}", headers={"x-forwarded-for": ip, "user-agent": ua})


def table(name):
    with community.connect() as db:
        return [dict(r._mapping) for r in db.conn.execute(text(f"SELECT * FROM {name}")).fetchall()]


def put(slug, day, views=0, forks=0, plans=0):
    with community.connect() as db:
        db.conn.execute(text("INSERT INTO trip_days (slug, day, views, forks, plans) VALUES (:s, :d, :v, :f, :p)"), {"s": slug, "d": day.isoformat(), "v": views, "f": forks, "p": plans})
        db.conn.commit()


def ago(n):
    return TODAY - timedelta(days=n)


def numbers(owner, trip=None):
    r = stats.report(owner)
    return r["total"] if trip is None else next(t for t in r["trips"] if t["slug"] == trip)


# ---- counting readers ------------------------------------------------------------------------------------------------

def test_one_reader_counts_once_a_day_however_often_they_reload(client):
    row, _, s = live_trip()
    for _ in range(4):
        assert read(client, row["slug"]).status_code == 200
    assert numbers(s["user_id"])["all"]["views"] == 1


def test_another_address_or_another_browser_is_another_reader(client):
    row, _, s = live_trip()
    read(client, row["slug"], ip="203.0.113.7", ua=CHROME)
    read(client, row["slug"], ip="203.0.113.8", ua=CHROME)
    read(client, row["slug"], ip="203.0.113.7", ua=FIREFOX)
    assert numbers(s["user_id"])["all"]["views"] == 3


def test_the_same_reader_counts_again_on_the_next_day(client, monkeypatch):
    row, _, _ = live_trip()
    read(client, row["slug"])
    monkeypatch.setattr(stats, "_today", lambda: TODAY + timedelta(days=1))
    read(client, row["slug"])
    assert [(d["day"], d["views"]) for d in table("trip_days")] == [("2026-11-06", 1), ("2026-11-07", 1)]


def test_the_same_reader_on_two_trips_counts_on_each(client):
    a, _, s = live_trip(title="Three easy days in Santa Monica")
    b, _, _ = live_trip(title="A long weekend in Malibu")
    read(client, a["slug"])
    read(client, b["slug"])
    assert sorted(t["all"]["views"] for t in stats.report(s["user_id"])["trips"]) == [1, 1]


@pytest.mark.parametrize("ua", ["Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)", "curl/8.5.0", "python-requests/2.32", "WhatsApp/2.24.1",
                                "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; bingbot/2.0)", "facebookexternalhit/1.1", "Slackbot-LinkExpanding 1.0", "HeadlessChrome/120.0", ""])
def test_known_bots_and_empty_user_agents_are_not_readers(client, ua):
    row, _, s = live_trip()
    assert read(client, row["slug"], ua=ua).status_code == 200      # the page still works for them
    assert numbers(s["user_id"])["all"]["views"] == 0


def test_the_creators_own_views_are_not_counted_but_another_signed_in_person_is(client):
    row, _, s = live_trip()
    sign_in(client, "maya@example.com")
    read(client, row["slug"])
    assert numbers(s["user_id"])["all"]["views"] == 0
    sign_in(client, "sam")
    read(client, row["slug"], ip="198.51.100.4")
    assert numbers(s["user_id"])["all"]["views"] == 1


def test_only_live_published_trips_are_counted(client):
    row, _, _ = live_trip()
    assert read(client, "no-such-trip-zzz").status_code == 404
    community.take_down(row["slug"])
    assert read(client, row["slug"]).status_code == 404
    assert table("trip_days") == [] and table("view_seen") == []


def test_no_ip_address_and_no_user_agent_is_kept_anywhere(client):
    row, _, _ = live_trip()
    read(client, row["slug"], ip="203.0.113.77", ua=CHROME)
    with sqlite3.connect(str(auth.data_dir() / "community.db")) as raw:
        tables = [n for (n,) in raw.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
        dump = " ".join(str(v) for n in tables if n != "published" for r in raw.execute(f'SELECT * FROM "{n}"') for v in r)
        columns = {c[1] for n in tables for c in raw.execute(f'PRAGMA table_info("{n}")')}
    assert "203.0.113.77" not in dump and "iPhone" not in dump and "Safari" not in dump
    assert not columns & {"ip", "ua", "user_agent", "address"}
    assert [(r["h"] != "203.0.113.77", len(r["h"])) for r in table("view_seen")] == [(True, 20)]


def test_the_hash_of_a_reader_changes_every_day_so_yesterday_cannot_be_linked_to_today(client, monkeypatch):
    row, _, _ = live_trip()
    read(client, row["slug"])
    first = [r["h"] for r in table("view_seen")]
    monkeypatch.setattr(stats, "_today", lambda: TODAY + timedelta(days=1))
    read(client, row["slug"])
    second = [r["h"] for r in table("view_seen")]
    assert len(second) == 1 and second != first            # yesterday's row was purged, and today's hash is made with a new salt


def test_yesterdays_seen_rows_are_purged_when_a_new_day_starts(client, monkeypatch):
    row, _, _ = live_trip()
    for i in range(3):
        read(client, row["slug"], ip=f"203.0.113.{i}")
    assert len(table("view_seen")) == 3
    monkeypatch.setattr(stats, "_today", lambda: TODAY + timedelta(days=1))
    read(client, row["slug"], ip="203.0.113.9")
    assert [r["day"] for r in table("view_seen")] == ["2026-11-07"]
    assert sum(d["views"] for d in table("trip_days")) == 4          # the counts stay, only the who-was-here is gone


# ---- forks, "Plan this trip" taps, partner clicks ---------------------------------------------------------------------

def test_a_fork_is_counted_for_the_day_and_all_time(client):
    row, _, s = live_trip()
    sign_in(client, "sam")
    client.post("/fork", data={"next": f"/trips/{row['slug']}"}, follow_redirects=False)
    assert table("trip_days") == [{"slug": row["slug"], "day": "2026-11-06", "views": 0, "forks": 1, "plans": 0}]
    assert numbers(s["user_id"])["all"]["forks"] == 1


def plan_from(client, row, handle, ip="203.0.113.7", ua=CHROME):
    return client.get(f"/plan?to=la&d=2027-03-05&r=2027-03-08&a=2&via={handle}", headers={"referer": f"http://testserver/trips/{row['slug']}", "x-forwarded-for": ip, "user-agent": ua})


def test_a_tap_on_plan_this_trip_counts_once_per_reader_per_day_and_not_the_creator(client):
    row, handle, s = live_trip()
    plan_from(client, row, handle)
    plan_from(client, row, handle)
    plan_from(client, row, handle, ip="203.0.113.8")
    assert numbers(s["user_id"], row["slug"])["all"]["plans"] == 2
    sign_in(client, "maya@example.com")
    plan_from(client, row, handle, ip="203.0.113.9")
    assert numbers(s["user_id"], row["slug"])["all"]["plans"] == 2


def test_a_plan_link_not_clicked_on_the_creators_own_page_is_not_a_tap(client):
    row, handle, s = live_trip()
    client.get(f"/plan?to=la&d=2027-03-05&r=2027-03-08&a=2&via={handle}", headers={"referer": "https://elsewhere.example/post"})
    client.get(f"/plan?to=la&d=2027-03-05&r=2027-03-08&a=2&via={handle}")
    assert numbers(s["user_id"])["all"]["plans"] == 0


def test_partner_clicks_say_whose_marker_earned(client):
    _, handle, s = live_trip()
    for own in (True, True, False):
        affiliate.log_click(handle, "aviasales" if own else "klook", "flight" if own else "stay", own)
    c = stats.report(s["user_id"])["clicks"]
    assert (c["all"], c["own"], c["gitaway"]) == (3, 2, 1)


# ---- the windows ----------------------------------------------------------------------------------------------------

def test_seven_days_thirty_days_and_all_time_count_the_right_days(client):
    row, _, s = live_trip()
    put(row["slug"], ago(0), views=1, forks=1, plans=1)
    put(row["slug"], ago(6), views=2)           # the 7th day back is still in "7 days"
    put(row["slug"], ago(7), views=4)           # one day further is only in 30
    put(row["slug"], ago(29), views=8)
    put(row["slug"], ago(30), views=16, forks=2)
    t = numbers(s["user_id"], row["slug"])
    assert (t["7"]["views"], t["30"]["views"], t["all"]["views"]) == (3, 15, 31)
    assert (t["7"]["forks"], t["30"]["forks"]) == (1, 1)
    assert t["7"]["plans"] == 1


def test_the_sparkline_has_one_point_per_day_oldest_first(client):
    row, _, s = live_trip()
    put(row["slug"], ago(29), views=5)
    put(row["slug"], ago(0), views=2)
    spark = numbers(s["user_id"], row["slug"])["spark"]
    assert len(spark) == 30 and spark[0] == 5 and spark[-1] == 2 and sum(spark) == 7


def test_partner_clicks_are_windowed_by_the_day_they_happened(client):
    _, handle, s = live_trip()
    affiliate.log_click(handle, "aviasales", "flight", True)
    with community.connect() as db:
        db.conn.execute(text("UPDATE via_clicks SET clicked_at = :t"), {"t": f"{ago(10).isoformat()}T09:00:00.000000+00:00"})
        db.conn.commit()
    c = stats.report(s["user_id"])["clicks"]
    assert (c["7"], c["30"], c["all"]) == (0, 1, 1)


def test_the_total_adds_up_the_trips(client):
    a, _, s = live_trip(title="Three easy days in Santa Monica")
    b, _, _ = live_trip(title="A long weekend in Malibu")
    put(a["slug"], ago(1), views=3, forks=1)
    put(b["slug"], ago(2), views=4, plans=2)
    t = stats.report(s["user_id"])["total"]
    assert (t["7"]["views"], t["7"]["forks"], t["7"]["plans"]) == (7, 1, 2)


# ---- the page ---------------------------------------------------------------------------------------------------------

def test_signed_out_goes_to_sign_in(client):
    r = client.get("/creators/stats", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/signin?next=/creators/stats")


def test_someone_who_never_published_sees_no_numbers_and_the_way_to_start(client):
    sign_in(client, "sam")
    body = without_bar(client.get("/creators/stats").text)
    assert 'id="cs-empty"' in body and 'href="/creators/import"' in body and 'id="cs-total"' not in body


def test_a_creator_sees_their_own_trips_and_never_another_creators(client):
    mine, _, _ = live_trip(title="Three easy days in Santa Monica")
    other, _, _ = live_trip("jo@example.com", "Jo Park", "Five days on Maui")
    put(mine["slug"], ago(1), views=12, forks=3, plans=5)
    put(other["slug"], ago(1), views=999)
    sign_in(client, "maya@example.com")
    body = without_bar(client.get("/creators/stats").text)
    assert "Three easy days in Santa Monica" in body and "Five days on Maui" not in body and "999" not in body
    assert re.search(r'id="cs-readers"[^>]*>12<', body)


def test_the_page_shows_readers_forks_taps_and_clicks_for_the_chosen_window(client):
    row, handle, _ = live_trip()
    put(row["slug"], ago(2), views=12, forks=3, plans=5)
    put(row["slug"], ago(20), views=100, forks=10, plans=50)
    affiliate.log_click(handle, "aviasales", "flight", True)
    affiliate.log_click(handle, "klook", "stay", False)
    sign_in(client, "maya@example.com")

    def shown(w):
        body = without_bar(client.get(f"/creators/stats?w={w}").text)
        return [re.search(rf'id="cs-{k}"[^>]*>(\d+)<', body).group(1) for k in ("readers", "forks", "taps", "clicks")]

    assert shown("7") == ["12", "3", "5", "2"]
    assert shown("30") == ["112", "13", "55", "2"]
    assert shown("all") == ["112", "13", "55", "2"]
    assert shown("bogus") == shown("30")                     # an unknown window is the default
    body = without_bar(client.get("/creators/stats").text)
    assert "1 with your marker" in body and "1 through GitAway" in body
    assert "$" not in body


def test_each_trip_has_a_sparkline(client):
    row, _, _ = live_trip()
    put(row["slug"], ago(1), views=4)
    sign_in(client, "maya@example.com")
    body = without_bar(client.get("/creators/stats").text)
    assert re.search(r'<svg[^>]*aria-label="Readers a day, last 30 days: 4 in all"', body)


def test_settings_and_the_creators_own_profile_link_to_the_stats_but_nobody_elses_does(client):
    _, handle, _ = live_trip()
    sign_in(client, "maya@example.com")
    assert 'href="/creators/stats"' in client.get("/creators/settings").text
    assert 'href="/creators/stats"' in client.get(f"/creators/{handle}").text
    sign_in(client, "sam")
    assert 'href="/creators/stats"' not in client.get(f"/creators/{handle}").text
    client.cookies.clear()
    assert 'href="/creators/stats"' not in client.get(f"/creators/{handle}").text


def test_stats_is_not_a_creator_handle():
    assert "stats" in community.RESERVED_HANDLES


def test_the_admin_creators_table_shows_readers_all_time(client, monkeypatch):
    row, handle, _ = live_trip()
    put(row["slug"], ago(40), views=30)
    put(row["slug"], ago(1), views=12)
    monkeypatch.setenv("GITAWAY_ADMIN_EMAILS", "cap@example.com")
    sign_in(client, "cap@example.com")
    body = client.get("/admin").text
    assert re.search(rf'id="c-{handle}".*?42 readers', body, re.S)


def test_the_privacy_page_says_how_readers_are_counted(client):
    body = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", client.get("/privacy").text)).replace("&#x27;", "'")
    for phrase in ("How readers of a creator's trip are counted", "no cookie", "once a day", "never stored", "a short code made from your address and browser", "thrown away at the end of the day",
                   "Known bots", "the creator's own visits"):
        assert phrase in body, phrase
