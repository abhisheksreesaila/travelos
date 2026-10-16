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
    assert live
    assert live[0].engine.pool.checkedout() == 0      # the finished request left no connection out

    def explode(db, sql, **p):
        raise RuntimeError("boom")

    live.clear()
    monkeypatch.setattr(familydb, "rows", explode)
    with pytest.raises(RuntimeError):
        client.get("/trip/canvas?day=1&frag=1", headers=FRAG)
    monkeypatch.undo()
    probe = familydb.require_tenant_access(person("ari"))
    try:
        assert probe.engine.pool.checkedout() == 1      # only the probe itself: the failed request left no connection out
    finally:
        probe.conn.close()


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


def test_a_request_holds_no_pool_connection_between_uses(client):
    """The scope keeps the verified, ready handle but not a connection: a dozen prefetches at once must not run the pool (5 + 10) dry."""
    ari = person("ari")
    with familydb.request_scope():
        with familydb.using(ari) as db:
            pool = db.engine.pool
            assert pool.checkedout() == 1
        assert pool.checkedout() == 0
        held = [familydb.family_db(ari) for _ in range(12)]
        assert len({id(h.conn) for h in held}) == 12      # every use has its own connection
        for h in held:
            h.conn.close()
        assert pool.checkedout() == 0


def test_a_lent_handle_has_its_own_connection_and_its_own_table_cache(client):
    """fastsql's table objects remember the handle they were made on, so each lent handle starts with an empty cache of its own."""
    ari = person("ari")
    with familydb.request_scope():
        first, second = familydb.family_db(ari), familydb.family_db(ari)
        try:
            assert first._tables is not second._tables and first.conn is not second.conn
            first._tables["probe"] = "first"
            assert "probe" not in second._tables and "probe" not in familydb.family_db(ari)._tables
        finally:
            first.conn.close()
            second.conn.close()


def test_no_gitaway_code_uses_fastsqls_table_api_on_a_family_handle():
    """fastsql's table API (`db.t`, `db["x"]`, create, transform) does not work on a tenant handle and would share `meta` between lent handles: use SQL."""
    import re
    from pathlib import Path
    pattern = re.compile(r"\bdb\.t\b|\bdb\[|\.db\.t\b|\.db\[|\bdb\.create\(|\.transform\(")
    hits = [f"{p.name}:{n}" for p in sorted((Path(__file__).resolve().parents[1] / "gitaway").rglob("*.py"))
            for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
            if pattern.search(line) and not line.lstrip().startswith(("#", "with the other lent", "`db.create`"))]
    assert hits == [], hits


class Counting(dict):
    def __init__(self, *a):
        super().__init__(*a)
        self.reads = {}

    def __getitem__(self, k):
        self.reads[k] = self.reads.get(k, 0) + 1
        return super().__getitem__(k)

    def get(self, k, default=None):
        self.reads[k] = self.reads.get(k, 0) + 1
        return super().get(k, default)


def test_the_scope_reads_the_family_and_person_from_the_session_once(client):
    """The cache key and the membership check must see the same family, even if the session changes between two reads."""
    sess = Counting(person("ari"))
    with familydb.request_scope():
        with familydb.using(sess) as db:
            assert db is not None
    assert sess.reads["tenant_id"] == 1 and sess.reads["user_id"] <= 2, sess.reads
