"""The community database (F-041): published trips are snapshots anyone can open; forks and saves belong to the family."""

import re

from starlette.testclient import TestClient

from gitaway import community, familydb_social as social
from tests.test_calendar import add, book
from tests.test_signin import session_data, sign_in, tid

TRIP = "sun-tacos-and-tide-pools"


def device(client):
    """Another browser: the same app with no cookies."""
    return TestClient(client.app, client=("127.0.0.1", 50000))


def shared_slug(owner="ari"):
    return community.rows(kind="shared", owner=tid(owner))[0]["slug"]


def share(client, **data):
    return client.post("/share", data=data, follow_redirects=False)


def main_html(html):
    return html.split("<main")[1].split("</main>")[0]


def test_a_shared_trip_is_stored_in_the_community_db_with_its_owner(client):
    book(client)
    add(client, title="Venice Canals stroll")
    share(client)
    [row] = community.rows()
    assert row["kind"] == "shared" and row["owner_user"] == tid("ari") and row["owner_family"] == session_data(client)["tenant_id"]
    assert "Venice Canals stroll" in row["snapshot"] and row["tags"] == ["kid"]
    assert "hub" not in session_data(client)  # nothing about it lives in the cookie any more


def test_the_shared_page_works_signed_out_on_another_device_and_for_another_family(client):
    book(client)
    add(client, title="Venice Canals stroll")
    share(client)
    slug = shared_slug()
    for other in (device(client), _signed_in(client, "sam")):
        r = other.get(f"/trips/{slug}")
        assert r.status_code == 200 and "Venice Canals stroll" in r.text and "Skylark Air 214" in r.text
    assert slug in device(client).get("/discover").text


def _signed_in(client, who):
    other = device(client)
    sign_in(other, who)
    return other


def test_the_shared_page_is_a_snapshot_so_later_calendar_edits_do_not_change_it(client):
    book(client)
    add(client, title="Venice Canals stroll")
    share(client)
    slug = shared_slug()
    add(client, id="a2", title="Surprise helicopter ride", day="2")
    assert "Surprise helicopter" not in device(client).get(f"/trips/{slug}").text
    share(client)  # re-sharing updates the snapshot
    assert "Surprise helicopter" in device(client).get(f"/trips/{slug}").text
    assert len(community.rows()) == 1


def test_the_owner_can_unpublish_and_nobody_else_can(client):
    book(client)
    share(client)
    slug = shared_slug()
    sam = _signed_in(client, "sam")
    assert not community.unpublish(session_data(sam), slug)
    assert device(client).get(f"/trips/{slug}").status_code == 200
    assert community.unpublish(session_data(client), slug)
    assert device(client).get(f"/trips/{slug}").status_code == 404 and slug not in device(client).get("/discover").text


def test_the_snapshot_has_no_notes_friends_reference_or_prices(client):
    book(client)
    client.post("/calendar/friends", data={"name": "Grandma Zelda"})
    add(client)
    client.post("/calendar/notes", data={"id": "n9", "text": "Secret passcode hunter2", "act": "a1"})
    share(client)
    row = community.rows()[0]
    slug = row["slug"]
    blob = row["snapshot"] + row["title"] + str(row["meta"])
    html = main_html(device(client).get(f"/trips/{slug}").text)
    booking = session_data(client)["bookings"][tid("ari")] if "bookings" in session_data(client) else {}
    for private in ["hunter2", "Grandma Zelda", "/join/", "GA-", "gitaway.example", "$", "total_cents"] + ([booking["id"]] if booking else []):
        assert private not in blob and private not in html, private
    assert re.fullmatch(r"shared-[0-9a-f]{10}", slug)


def test_forks_and_saves_are_per_family_and_survive_a_restart(client):
    sign_in(client, "ari")
    client.post("/fork", data={"next": f"/trips/{TRIP}"})
    client.post("/save", data={"next": "/trips/la-for-two-slow-mornings"})
    tenant = session_data(client)["tenant_id"]
    assert social.slugs({"tenant_id": tenant}, "forks") == [TRIP] and social.slugs({"tenant_id": tenant}, "saves") == ["la-for-two-slow-mornings"]
    assert "forks" not in session_data(client) and "saves" not in session_data(client)
    sam = _signed_in(client, "sam")
    assert "No forks yet" in sam.get("/forks").text and social.slugs(session_data(sam), "forks") == []  # another family sees none of them
    # a restart: a new browser, a new process-level state, the same data folder
    social._ready.clear(), community._ready.clear()
    again = _signed_in(client, "ari")
    html = again.get("/forks").text
    assert "Sun, tacos" in html and "LA for two" in html


def test_forking_a_community_trip_from_another_family_keeps_it_in_the_forkers_family(client):
    book(client)
    share(client)
    slug = shared_slug()
    sam = _signed_in(client, "sam")
    assert sam.post("/fork", data={"next": f"/trips/{slug}"}, follow_redirects=False).status_code == 303
    assert "LA with the kids" in sam.get("/forks").text
    assert "LA with the kids" not in client.get("/forks").text and social.slugs(session_data(client), "forks") == []  # Ari's family did not fork it


def test_the_done_page_and_calendar_explain_the_snapshot_and_offer_unpublish(client):
    book(client)
    assert "/share/unpublish" not in client.get("/calendar").text and "Update shared page" not in client.get("/calendar").text
    share(client)
    slug = shared_slug()
    done = client.get("/share/done").text
    assert "This is a snapshot. Share again to update it." in done and 'action="/share/unpublish"' in done
    cal = client.get("/calendar").text
    assert "Update shared page" in cal and 'action="/share/unpublish"' in cal
    r = client.post("/share/unpublish", data={"slug": slug}, follow_redirects=False)
    assert r.status_code == 303 and community.get(slug) is None
    assert "Share trip" in client.get("/calendar").text


def test_only_the_owner_can_unpublish_over_http(client):
    book(client)
    share(client)
    slug = shared_slug()
    assert device(client).post("/share/unpublish", data={"slug": slug}, follow_redirects=False).status_code == 303
    sam = _signed_in(client, "sam")
    sam.post("/share/unpublish", data={"slug": slug})
    assert community.get(slug) is not None


def test_the_fork_count_skips_vanished_trips_with_one_community_query(client, monkeypatch):
    from gitaway import forks
    book(client)
    share(client)
    sam = _signed_in(client, "sam")
    slug = shared_slug()
    sam.post("/fork", data={"next": f"/trips/{slug}"})
    sam.post("/fork", data={"next": f"/trips/{TRIP}"})
    assert forks.count(session_data(sam)) == 2
    calls = []
    real = community.existing
    monkeypatch.setattr(community, "existing", lambda s: calls.append(list(s)) or real(s))
    forks.count(session_data(sam))
    assert calls == [[slug]]
    community.unpublish(session_data(client), slug)
    assert forks.count(session_data(sam)) == 1


def test_the_share_slug_is_keyed_with_the_server_secret(monkeypatch):
    from gitaway import session as ses, share as sh
    b = {"id": "GA-12345678"}
    first = sh.slug_for("u1", b)
    monkeypatch.setattr(ses, "cache_secret", lambda: b"another secret")
    assert sh.slug_for("u1", b) != first and sh.slug_for("u1", b) == sh.slug_for("u1", b)
