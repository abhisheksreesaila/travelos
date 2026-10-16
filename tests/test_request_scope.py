"""F-172: one request opens its family's database once and reuses it (docs/family-db.md "One handle per request").

Opening costs a host-database membership check (under one lock) and a clone of the family's ~28-table metadata; a day fragment
used to open 27 times. These tests count the real opens, and prove the shared handle never crosses requests or families."""

import threading

import pytest
from starlette.testclient import TestClient

from gitaway import familydb
from tests.test_calendar import add, book
from tests.test_signin import person


@pytest.fixture
def opens(monkeypatch):
    """The number of real family-database opens (membership check + handle), counted from here on."""
    n = {"n": 0}
    real = familydb.require_tenant_access

    def counted(source):
        n["n"] += 1
        return real(source)

    monkeypatch.setattr(familydb, "require_tenant_access", counted)
    return n


def other_client():
    from main import app
    return TestClient(app, client=("127.0.0.1", 50000))


FRAG = {"X-Canvas": "1"}


def test_a_day_fragment_opens_the_family_database_at_most_twice(client, opens):
    book(client)
    add(client, id="a1", title="Ari plan", day="1")
    opens["n"] = 0
    r = client.get("/trip/canvas?day=1&frag=1", headers=FRAG)
    assert r.status_code == 200 and "Ari plan" in r.text
    assert opens["n"] <= 2, opens["n"]


def test_the_week_and_the_plan_card_open_it_at_most_twice(client, opens):
    book(client)
    add(client, id="a1", title="Ari plan", day="1")
    for url in ("/trip/canvas?frag=1", "/trip/canvas/card?act=a1"):
        opens["n"] = 0
        assert client.get(url, headers=FRAG).status_code == 200
        assert opens["n"] <= 2, (url, opens["n"])


def test_every_handle_a_request_opened_is_closed_when_it_ends_even_on_an_error(client, monkeypatch):
    book(client)
    live = []
    real = familydb.require_tenant_access

    def tracked(source):
        db = real(source)
        live.append(db)
        return db

    monkeypatch.setattr(familydb, "require_tenant_access", tracked)
    client.get("/trip/canvas?day=1&frag=1", headers=FRAG)
    assert live and all(db.conn.closed for db in live)

    def explode(db, sql, **p):
        raise RuntimeError("boom")

    live.clear()
    monkeypatch.setattr(familydb, "rows", explode)
    with pytest.raises(RuntimeError):
        client.get("/trip/canvas?day=1&frag=1", headers=FRAG)
    assert live and all(db.conn.closed for db in live)


def test_two_concurrent_requests_for_two_families_stay_separate(client):
    book(client)
    add(client, id="a1", title="Ari's secret plan", day="1")
    sam = other_client()
    book(sam, "sam")
    add(sam, id="a1", title="Sam's secret plan", day="1")
    seen = {"ari": [], "sam": []}

    def get(name, c):
        for _ in range(8):
            seen[name].append(c.get("/trip/canvas?day=1&frag=1", headers=FRAG).text)

    threads = [threading.Thread(target=get, args=("ari", client)), threading.Thread(target=get, args=("sam", sam))]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(seen["ari"]) == len(seen["sam"]) == 8
    assert all("Ari&#x27;s secret plan" in h or "Ari's secret plan" in h for h in seen["ari"])
    assert not any("Sam's secret" in h or "Sam&#x27;s secret" in h for h in seen["ari"])
    assert not any("Ari's secret" in h or "Ari&#x27;s secret" in h for h in seen["sam"])
    assert all("Sam&#x27;s secret plan" in h or "Sam's secret plan" in h for h in seen["sam"])


def join(db, who):
    familydb.ensure_member(db, who["user_id"], "x@example.com", "X")


def count(db, uid):
    return familydb.rows(db, "SELECT COUNT(*) AS n FROM members WHERE id = :u", u=uid)[0]["n"]


def test_inside_one_request_another_familys_session_gets_that_familys_database(client):
    ari, sam = person("ari"), person("sam")
    assert ari["tenant_id"] != sam["tenant_id"]
    with familydb.request_scope():
        with familydb.using(ari) as a1:
            join(a1, ari)
            with familydb.using(sam) as s1:
                join(s1, sam)
                assert a1.conn is not s1.conn
                assert count(s1, ari["user_id"]) == 0 and count(s1, sam["user_id"]) == 1
        with familydb.using(ari) as a2:
            assert count(a2, ari["user_id"]) == 1 and count(a2, sam["user_id"]) == 0


def test_a_person_who_is_not_a_member_gets_nothing_inside_a_scope(client):
    sam = person("sam")
    stranger = {**sam, "tenant_id": person("ari")["tenant_id"]}   # sam's id pointed at ari's family
    with familydb.request_scope():
        with familydb.using(sam) as ok:
            assert ok is not None
        with familydb.using(stranger) as db:
            assert db is None


def test_a_nested_close_leaves_the_handle_usable_and_no_transaction_stays_open(client):
    ari = person("ari")
    with familydb.request_scope():
        with familydb.using(ari) as outer:
            join(outer, ari)
            with familydb.using(ari):
                pass
            assert count(outer, ari["user_id"]) == 1          # the inner close did not close the outer's handle
            with familydb.transaction(outer):
                familydb.run(outer, "UPDATE members SET id = id WHERE 0")
            separate = familydb.require_tenant_access(ari)     # a second real connection to the same file writes at once
            try:
                familydb.run(separate, "UPDATE members SET id = id WHERE 0")
                separate.conn.commit()
            finally:
                separate.conn.close()
