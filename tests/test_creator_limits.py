"""F-182 (H1, L2): what one creator, and all creators together, may spend in a day. The counters are atomic (a burst of parallel requests cannot all read "19" and each write "20"),
the picture fetches are counted too (un-pick and re-pick forever was a free fetcher), and one site-wide ceiling stops many sign-ups from running up the model bill."""

import threading

import pytest

from gitaway import creatordraft as cd
from tests.creator_import_support import with_edits
from tests.test_creator_import import drafted, fields_of, me, model, save, web  # noqa: F401  (fixtures)
from tests.test_signin import tid


@pytest.fixture(autouse=True)
def _clean():
    cd.clear()
    yield
    cd.clear()


def test_sixty_parallel_tries_for_one_person_count_exactly_the_daily_limit(monkeypatch):
    monkeypatch.setattr(cd, "DAILY_LIMIT", 7)
    got = []

    def go():
        got.append(cd.allow("racer"))
    threads = [threading.Thread(target=go) for _ in range(60)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert got.count("") == 7 and got.count("person") == 53


def test_the_site_wide_ceiling_stops_everyone_and_a_refused_try_costs_the_person_nothing(monkeypatch):
    monkeypatch.setenv("GITAWAY_CREATOR_IMPORT_SITE_LIMIT", "3")
    assert [cd.allow(f"p{i}") for i in range(5)] == ["", "", "", "site", "site"]
    monkeypatch.setenv("GITAWAY_CREATOR_IMPORT_SITE_LIMIT", "10")
    assert cd.allow("p3") == "" and cd.allow("p3") == ""     # p3 was refused twice by the ceiling and still has all their own tries


def test_the_site_ceiling_defaults_to_500_a_day(monkeypatch):
    monkeypatch.delenv("GITAWAY_CREATOR_IMPORT_SITE_LIMIT", raising=False)
    assert cd.site_limit() == 500
    monkeypatch.setenv("GITAWAY_CREATOR_IMPORT_SITE_LIMIT", "nonsense")
    assert cd.site_limit() == 500


def test_the_ceiling_shows_the_creator_a_plain_sentence(me, model, web, monkeypatch):   # noqa: F811
    monkeypatch.setenv("GITAWAY_CREATOR_IMPORT_SITE_LIMIT", "0")
    r = me.post("/creators/import", data={"do": "draft", "link": "https://blog.example.com/santa-monica-with-kids"}, follow_redirects=False)
    assert r.status_code == 422 and cd.SITE_LIMIT_HIT in r.text.replace("&#x27;", "'") and model.requests == [] and web.calls == []


def test_re_picking_pictures_over_and_over_hits_a_daily_picture_limit(drafted, web, monkeypatch):   # noqa: F811
    monkeypatch.setattr(cd, "PICTURE_LIMIT", 3)
    client, did = drafted
    before = len(web.calls)
    for _ in range(5):
        save(client, did, with_edits(fields_of(client, did), pick=["1"]))
        save(client, did, with_edits(fields_of(client, did), pick=[]))
    assert len(web.calls) - before == 3          # the fourth and later picks fetched nothing
    save(client, did, with_edits(fields_of(client, did), pick=["1"]))
    assert cd.get(tid(), did)["picks"] == []


def test_a_picture_already_copied_costs_no_fetch_and_no_count(drafted, web, monkeypatch):   # noqa: F811
    monkeypatch.setattr(cd, "PICTURE_LIMIT", 1)
    client, did = drafted
    save(client, did, with_edits(fields_of(client, did), pick=["1"]))
    save(client, did, with_edits(fields_of(client, did), pick=["1"], title="Changed title"))
    assert cd.get(tid(), did)["picks"] == [1]
