"""F-040: a family's trips, bookings, calendar, friends and remembered picks live in its tenant database.

Covers: they survive a restart, the cookie holds only the sign-in, two family members share one trip, a family has several trips
with a switcher, edits at the same moment lose nothing, and schema changes go through fh-saas migrations.
"""

import json
import re
import sqlite3
import subprocess
import sys
import threading
from contextlib import contextmanager
from pathlib import Path

import pytest
from sqlalchemy import text

from gitaway import auth, catalog, familydb, session as ses, tripcal as cal
from tests.test_calendar import FORM, add, book, tag
from tests.test_signin import EMAILS, person, session_data, sign_in, stored_calendar

ROOT = Path(__file__).resolve().parent.parent
THREE_NIGHTS = dict(d="2026-10-16", r="2026-10-19", a="2", k="4,7")


# ---- helpers -------------------------------------------------------------------------------------------------------

@contextmanager
def add_member(traveler, to="ari"):
    """Make `traveler` an editor of `to`'s family, the way an invite will (F-043), and yield their session. Undone afterwards.

    Their own family is switched off while they are in this one, so a sign-in lands them here.
    """
    from fh_saas.db_host import HostDatabase
    owner, guest = person(to), person(traveler)  # both exist now, each with a family of their own
    host = HostDatabase.from_env().db.conn
    mine = host.execute(text("SELECT id FROM core_memberships WHERE user_id = :u"), {"u": guest["user_id"]}).scalars().all()
    host.execute(text("UPDATE core_memberships SET is_active = 0 WHERE user_id = :u"), {"u": guest["user_id"]})
    host.execute(text("INSERT INTO core_memberships (id, user_id, tenant_id, profile_id, role, is_active, created_at) VALUES (:id, :u, :t, :u, 'editor', 1, :at)"),
                 {"id": f"test-{traveler}-in-{to}", "u": guest["user_id"], "t": owner["tenant_id"], "at": familydb.now()})
    host.commit()
    try:
        yield person(traveler)
    finally:
        host.execute(text("DELETE FROM core_memberships WHERE id = :id"), {"id": f"test-{traveler}-in-{to}"})
        for mid in mine:
            host.execute(text("UPDATE core_memberships SET is_active = 1 WHERE id = :id"), {"id": mid})
        host.commit()


def tenant_file(session):
    """The SQLite file of a person's family, read directly (not through the app)."""
    return Path(auth.data_dir()) / f"{session['tenant_id']}_db.db"


def count(session, table):
    con = sqlite3.connect(tenant_file(session))
    try:
        return con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        con.close()


def restart():
    """Forget everything this process holds in memory about a family database: what a server restart does."""
    from fh_saas.db_tenant import _reset_tenant_db_cache
    _reset_tenant_db_cache()
    familydb.forget_schema_cache()


def trip_buttons(html):
    """[(trip id, is the open one)] for the trip switcher on the calendar, in the order shown."""
    out = []
    for m in re.findall(r"<button[^>]*data-trip=\"[^\"]+\"[^>]*>", html):
        attrs = dict(re.findall(r'([\w-]+)="([^"]*)"', m))
        out.append((attrs["data-trip"], attrs.get("aria-current") == "true"))
    return out


# ---- stored in the family database, and surviving a restart --------------------------------------------------------

def test_trips_bookings_activities_notes_and_friends_are_rows_in_the_family_file(client):
    book(client)
    add(client, id="a1")
    client.post("/calendar/notes", data={"id": "n2", "text": "Bring hats"})
    client.post("/calendar/friends", data={"name": "Mom"})
    s = person()
    assert [count(s, t) for t in ("trips", "bookings", "activities", "notes", "friends")] == [1, 1, 1, 1, 1]
    assert set(session_data(client)) <= set(ses.AUTH_KEYS)  # the cookie holds only the sign-in


def test_everything_survives_a_restart_of_the_server(client):
    book(client)
    add(client, id="a1", title="Venice Canals stroll")
    client.post("/calendar/notes", data={"id": "n2", "text": "Bring hats", "act": "a1"})
    client.post("/calendar/friends", data={"name": "Mom"})
    client.get("/plan?f=f2&h=h3&c=c1")
    before = client.get("/calendar?view=days").text
    restart()
    again = client.get("/calendar?view=days").text  # same cookie, nothing in memory
    assert "Venice Canals stroll" in again and "Mom" in again
    assert tag(before, "data-id", "a1") == tag(again, "data-id", "a1")
    assert [n["t"] for n in stored_calendar()["n"]] == ["Bring hats"] and ses.remembered_plan(person()).startswith("f=f2")


def test_a_real_second_process_sees_the_same_trip(client, tmp_path):
    """A new Python process on the same data folder and cookie, which is what a restart really is."""
    book(client)
    add(client, id="a1", title="Venice Canals stroll")
    cookie = client.cookies.get("session_")
    script = tmp_path / "second.py"
    script.write_text(
        "import os, sys\n"
        "from starlette.testclient import TestClient\n"
        "from main import app\n"
        "c = TestClient(app, client=('127.0.0.1', 50001))\n"
        "c.cookies.set('session_', sys.argv[1])\n"
        "html = c.get('/calendar?view=days').text\n"
        "print('FOUND' if 'Venice Canals stroll' in html else 'MISSING')\n")
    out = subprocess.run([sys.executable, str(script), cookie], cwd=ROOT, capture_output=True, text=True, timeout=120,
                         env={**__import__("os").environ, "PYTHONPATH": str(ROOT), "GITAWAY_DATA_DIR": str(auth.data_dir())})
    assert "FOUND" in out.stdout, out.stdout + out.stderr[-800:]


# ---- two members, one family ---------------------------------------------------------------------------------------

def test_two_members_of_a_family_see_and_edit_the_same_trip():
    ari = person("ari")
    booking = ses.book(ari, catalog.quote("f1", "h1", "c1"))
    cal.add_activity(ari, day=1, start="10:00", end="11:00", title="Ari's plan", kind="fun")
    with add_member("sam", to="ari") as sam:
        assert ses.booking(sam) == booking and sam["tenant_id"] == ari["tenant_id"] and sam["user_id"] != ari["user_id"]
        assert [a.title for a in cal.activities(sam)] == ["Ari's plan"]
        cal.add_activity(sam, day=2, start="13:00", end="14:00", title="Sam's plan", kind="food")
        cal.add_note(sam, "Sam was here")
        assert {a.title for a in cal.activities(ari)} == {"Ari's plan", "Sam's plan"}
        assert [n.text for n in cal.notes(ari)] == ["Sam was here"]
        ses.add_friend(ari, "Mom")
        assert [f.name for f in ses.friends(sam)] == ["Mom"]


def test_two_members_over_http_share_the_calendar(client):
    book(client)
    add(client, id="a1", title="Ari's plan")
    with add_member("sam", to="ari"):
        sign_in(client, "sam")
        assert "Ari&#x27;s plan" in client.get("/calendar?view=days").text or "Ari's plan" in client.get("/calendar?view=days").text
        assert add(client, id="a5", title="Sam's plan", day="2").status_code == 303
    sign_in(client, "ari")
    html = client.get("/calendar?view=days").text
    assert "Sam&#x27;s plan" in html or "Sam's plan" in html


def test_each_member_has_their_own_open_trip_in_the_same_family():
    ari = person("ari")
    first = ses.book(ari, catalog.quote("f1", "h1", "c1"))
    with add_member("sam", to="ari") as sam:
        second = ses.book(sam, catalog.quote("f1", "h1", "c1", trip=catalog.trip_from_url("2026-10-16", "2026-10-19", "2", "4,7")))
        assert ses.booking(sam)["id"] == second["id"] and ses.booking(ari)["id"] == first["id"]  # Sam booking does not move Ari's open trip
        assert len(ses.trips(ari)) == len(ses.trips(sam)) == 2


def test_someone_who_is_not_a_member_cannot_open_the_family_database():
    ari = person("ari")
    ses.book(ari, catalog.quote("f1", "h1", "c1"))
    sam = person("sam")
    sam["tenant_id"] = ari["tenant_id"]  # a forged session naming ari's family
    assert ses.booking(sam) is None and cal.activities(sam) == [] and ses.trips(sam) == []
    with pytest.raises(cal.CalendarError):
        cal.add_activity(sam, day=1, start="10:00", end="11:00", title="x", kind="fun")


# ---- several trips and the switcher ----------------------------------------------------------------------------------

def test_booking_again_with_other_picks_makes_another_trip_instead_of_replacing_the_first(client):
    book(client)
    first = ses.booking(person())
    book(client, **THREE_NIGHTS)
    s = person()
    assert len(ses.trips(s)) == 2 and ses.booking(s)["id"] != first["id"]  # the newest is open
    assert ses.trips(s)[0].current and not ses.trips(s)[1].current


def test_the_calendar_lists_the_trips_and_switching_opens_the_other_with_its_own_activities(client):
    book(client)
    add(client, id="a1", title="Sample trip plan")
    book(client, **THREE_NIGHTS)
    add(client, id="a1", title="Three night plan", day="1")
    html = client.get("/calendar?view=days").text
    buttons = trip_buttons(html)
    assert len(buttons) == 2 and [cur for _, cur in buttons] == [True, False]
    assert "Three night plan" in html and "Sample trip plan" not in html
    other = buttons[1][0]
    r = client.post("/trips/switch", data={"trip": other}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/calendar"
    html = client.get("/calendar?view=days").text
    assert "Sample trip plan" in html and "Three night plan" not in html
    assert [cur for _, cur in trip_buttons(html)] == [False, True]
    assert "Oct 16 – 20" in html  # the sample trip's dates


def test_switching_to_a_trip_that_is_not_the_familys_changes_nothing(client):
    book(client)
    here = ses.booking(person())["id"]
    for junk in ("nope", "", "../x", "a' OR '1'='1"):
        r = client.post("/trips/switch", data={"trip": junk}, follow_redirects=False)
        assert r.status_code in (303, 409)
    assert ses.booking(person())["id"] == here


def test_switching_needs_sign_in(client):
    r = client.post("/trips/switch", data={"trip": "x"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/signin")


def test_the_paid_trip_opens_on_the_calendar_and_pay_again_reopens_it(client):
    book(client)
    first = ses.booking(person())
    book(client, **THREE_NIGHTS)
    book(client)  # the same picks as the first trip: no new trip, it opens again
    s = person()
    assert len(ses.trips(s)) == 2 and ses.booking(s)["id"] == first["id"]


def test_the_switcher_stays_out_of_the_way_with_one_trip(client):
    book(client)
    assert trip_buttons(client.get("/calendar").text) == []


def test_every_trip_has_its_own_ids_notes_friends_and_live_script(client):
    book(client)
    client.post("/calendar/friends", data={"name": "Mom"})
    client.post("/calendar/live")
    assert any(a.get("b") == "Mom" for a in stored_calendar()["a"])
    book(client, **THREE_NIGHTS)
    assert stored_calendar()["a"] == [] and [f.name for f in ses.friends(person())] == []  # nothing carried over
    assert not cal.live_pending(person())  # Mom is not on this trip yet


# ---- at the same moment ---------------------------------------------------------------------------------------------

def test_members_adding_at_the_same_moment_lose_nothing():
    ari = person("ari")
    ses.book(ari, catalog.quote("f1", "h1", "c1"))
    with add_member("sam", to="ari") as sam:
        errors = []

        def work(who, tag_):
            try:
                for i in range(12):
                    cal.add_activity(who, day=1 + i % 3, start=f"{8 + i:02d}:00", end=f"{8 + i:02d}:30", title=f"{tag_} {i}", kind="fun")
                    cal.add_note(who, f"{tag_} note {i}")
            except Exception as e:  # noqa: BLE001 - the test reports whatever went wrong
                errors.append(repr(e))

        threads = [threading.Thread(target=work, args=(who, name)) for who, name in ((ari, "Ari"), (sam, "Sam"), (ari, "Ari2"), (sam, "Sam2"))]
        for t in threads:
            t.start()
        for t in threads:
            t.join(60)
        assert not errors, errors
        acts, notes = cal.activities(ari), cal.notes(ari)
        assert len(acts) == 48 and len({a.id for a in acts}) == 48  # every add kept, every id different
        assert len(notes) == 48 and len({n.id for n in notes}) == 48


def test_two_members_changing_different_fields_of_one_activity_both_keep_their_change():
    ari = person("ari")
    ses.book(ari, catalog.quote("f1", "h1", "c1"))
    a = cal.add_activity(ari, day=1, start="10:00", end="11:00", title="Old", kind="fun")
    with add_member("sam", to="ari") as sam:
        cal.update_activity(ari, a.id, title="Renamed by Ari")
        moved = cal.update_activity(sam, a.id, day=2, start="13:00", end="14:00")  # does not write the title
        assert (moved.title, moved.day) == ("Renamed by Ari", 2)
        assert cal.get_activity(ari, a.id).title == "Renamed by Ari" and cal.get_activity(ari, a.id).start == 13 * 60


def test_booking_the_same_picks_twice_at_once_makes_one_trip():
    ari = person("ari")
    quote = catalog.quote("f1", "h1", "c1")
    threads = [threading.Thread(target=ses.book, args=(ari, quote)) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(60)
    assert len(ses.trips(ari)) == 1 and count(ari, "bookings") == 1


def test_the_next_id_number_never_goes_backwards_or_repeats():
    s = person()
    ses.book(s, catalog.quote("f1", "h1", "c1"))
    a = cal.add_activity(s, day=1, start="10:00", end="11:00", title="One", kind="fun")
    n = cal.add_note(s, "Two")
    assert (a.id, n.id, cal.next_id(s)) == ("a1", "n2", "3")
    cal.delete_activity(s, a.id)
    assert cal.next_id(s) == "3"  # a deleted id is never handed out again


# ---- the schema: tables, extension and migrations ---------------------------------------------------------------------

def test_the_family_tables_list_is_easy_to_extend_and_new_families_get_the_extra_table(monkeypatch):
    class Probe:
        pk: str
        note: str = ""

    monkeypatch.setattr(familydb, "FAMILY_TABLES", [*familydb.FAMILY_TABLES, (Probe, "probe_things", "pk")])
    familydb.forget_schema_cache()
    s = person("ari")
    with familydb.using(s) as db:
        assert db.conn.execute(text("SELECT COUNT(*) FROM probe_things")).scalar() == 0


def test_register_on_open_is_idempotent_and_keeps_the_rows(client):
    book(client)
    add(client, id="a1")
    restart()
    restart()
    assert [a["t"] for a in stored_calendar()["a"]] == ["Venice Canals stroll"]
    with familydb.using(person()) as db:
        familydb.ensure_schema(db, person()["tenant_id"])  # again, directly
        assert count(person(), "activities") == 1


def test_a_migration_is_applied_to_each_family_the_first_time_it_is_opened(tmp_path, monkeypatch):
    (tmp_path / "001_add_pinned_to_trips.sql").write_text("-- UP --\nALTER TABLE trips ADD COLUMN pinned INTEGER DEFAULT 0;\n-- DOWN --\nALTER TABLE trips DROP COLUMN pinned;\n")
    monkeypatch.setattr(familydb, "MIGRATIONS_DIR", tmp_path)
    familydb.forget_schema_cache()
    s = person("ari")
    ses.book(s, catalog.quote("f1", "h1", "c1"))
    with familydb.using(s) as db:
        assert db.conn.execute(text("SELECT pinned FROM trips")).scalar() == 0
        assert db.conn.execute(text("SELECT version FROM _migrations")).scalars().all() == [1]
    familydb.forget_schema_cache()
    with familydb.using(s) as db:  # opened again: not applied twice
        assert db.conn.execute(text("SELECT COUNT(*) FROM _migrations")).scalar() == 1
    with familydb.using(s) as db:  # leave this family's file as the rest of the suite expects it
        db.conn.execute(text("ALTER TABLE trips DROP COLUMN pinned"))
        db.conn.execute(text("DROP TABLE _migrations"))
        db.conn.commit()


# ---- signed out ------------------------------------------------------------------------------------------------------

def test_signed_out_the_workspace_and_pay_sheet_work_without_a_database(client):
    assert client.get("/plan").status_code == 200
    assert client.get("/plan/pay?f=f1&h=h1&c=c1", follow_redirects=False).status_code == 303  # to sign in
    r = client.get("/calendar", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/signin")


def test_the_family_helper_takes_a_request_or_a_session_and_says_no_to_strangers():
    s = person()
    with familydb.using(s) as db:
        assert db is not None and db.conn.execute(text("SELECT COUNT(*) FROM trips")).scalar() == 0
    with familydb.using({}) as db:
        assert db is None
    with pytest.raises(ValueError):
        familydb.family_db({})
    with pytest.raises(PermissionError):
        familydb.family_db({"user_id": s["user_id"], "tenant_id": "someone-elses"})
