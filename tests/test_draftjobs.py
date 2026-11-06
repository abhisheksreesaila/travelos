"""F-190: drafting several posts in the background (gitaway/draftjobs.py): a job table and a worker, never a request held open. Fake Claude and fake web as in F-183; nothing reaches the network."""

import time

import pytest

from gitaway import ai, creatordraft as cd, draftjobs as dj, importsource, safefetch
from tests.creator_import_support import Model, Web, page

KEY = "sk-ant-not-a-real-key-0000"
POSTS = [f"https://blog.example.com/post-{i}" for i in range(1, 6)]


@pytest.fixture(autouse=True)
def _clean():
    cd.clear()
    dj.clear()
    yield
    dj.stop()
    cd.clear()
    dj.clear()


@pytest.fixture
def model(monkeypatch):
    m = Model()
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    monkeypatch.setattr(ai, "ANTHROPIC_TRANSPORT", m)
    return m


@pytest.fixture
def web(monkeypatch):
    w = Web({u: page() for u in POSTS})
    monkeypatch.setattr(safefetch, "TRANSPORT", w)
    return w


def items(*urls):
    return [(u, "A title") for u in urls]


def rows(owner):
    return [(r["status"], r["url"]) for r in dj.listing(owner)]


def test_a_batch_is_queued_at_once_and_each_post_is_drafted_later_one_at_a_time(model, web):
    assert dj.enqueue("p1", "Maya", items(*POSTS[:3])) == (3, "")
    assert model.requests == [] and web.calls == []                         # nothing was fetched or asked while the request was open
    assert [r["status"] for r in dj.listing("p1")] == ["drafting"] * 3
    assert dj.run_pending() == 3
    assert sorted(r["url"] for r in dj.listing("p1")) == sorted(POSTS[:3]) and {r["status"] for r in dj.listing("p1")} == {"ready"}
    assert len(model.requests) == 3 and web.calls == POSTS[:3]


def test_a_finished_draft_is_the_persons_own_with_their_name_and_a_source_card(model, web):
    dj.enqueue("p1", "Maya Chen", items(POSTS[0]))
    dj.run_pending()
    (row,) = dj.listing("p1")
    d = cd.get("p1", row["id"])
    assert d["name"] == "Maya Chen" and d["source"]["url"] == POSTS[0] and d["title"] == "Three easy days in Santa Monica" and cd.get("p2", row["id"]) is None


def test_no_more_than_twenty_posts_in_a_batch(model, web):
    many = [f"https://blog.example.com/p{i}" for i in range(30)]
    assert dj.enqueue("p1", "M", items(*many)) == (20, "")
    assert len(dj.listing("p1")) == 20


def test_every_post_in_a_batch_counts_against_the_daily_limit_and_the_creator_is_told_how_many_are_left(monkeypatch):
    monkeypatch.setattr(cd, "DAILY_LIMIT", 5)
    assert dj.remaining("p1") == 5
    assert dj.enqueue("p1", "M", items(*POSTS[:3])) == (3, "") and dj.remaining("p1") == 2
    assert dj.enqueue("p1", "M", items(*POSTS)) == (2, "person") and dj.remaining("p1") == 0     # two more fit, the rest are refused with nothing counted
    assert len(dj.listing("p1")) == 5
    assert dj.enqueue("p1", "M", items(POSTS[0])) == (0, "person")
    assert dj.remaining("p2") == 5      # another person is untouched


def test_the_site_wide_ceiling_counts_too(monkeypatch):
    monkeypatch.setenv("GITAWAY_CREATOR_IMPORT_SITE_LIMIT", "4")
    assert dj.enqueue("p1", "M", items(*POSTS[:3])) == (3, "") and dj.remaining("p2") == 1
    assert dj.enqueue("p2", "M", items(*POSTS[:3])) == (1, "site")
    assert dj.remaining("p3") == 0


def test_a_post_that_cannot_be_read_fails_alone_with_a_sentence_and_the_rest_carry_on(model, web):
    web.pages[POSTS[1]] = (404, {"content-type": "text/html"}, b"")
    dj.enqueue("p1", "M", items(*POSTS[:3]))
    dj.run_pending()
    got = {r["url"]: r for r in dj.listing("p1")}
    assert got[POSTS[0]]["status"] == "ready" and got[POSTS[2]]["status"] == "ready"
    assert got[POSTS[1]]["status"] == "failed" and got[POSTS[1]]["error"] == "That website would not let GitAway read the page. You can paste the text of your post instead."


def test_a_model_failure_is_a_failed_row_with_the_assistants_own_sentence(model, web):
    model.stop, model.answer = "refusal", "x"
    dj.enqueue("p1", "M", items(POSTS[0]))
    dj.run_pending()
    (r,) = dj.listing("p1")
    assert (r["status"], r["error"]) == ("failed", "The assistant could not draft from that. Try pasting the text of your post instead.")


def test_something_unexpected_is_a_failed_row_with_a_fixed_sentence_and_never_the_exception_text(model, web, monkeypatch):
    monkeypatch.setattr(cd, "make", lambda *a, **k: 1 / 0)
    dj.enqueue("p1", "M", items(POSTS[0]))
    dj.run_pending()
    (r,) = dj.listing("p1")
    assert (r["status"], r["error"]) == ("failed", dj.UNEXPECTED)


def test_a_job_that_was_running_when_the_server_stopped_is_picked_up_again_and_not_counted_twice(model, web):
    dj.enqueue("p1", "M", items(*POSTS[:2]))
    before = dj.remaining("p1")
    assert dj.claim() is not None                    # the worker took one, then the process died
    assert rows("p1")[0][0] == "drafting"
    dj.reset_running()                               # what start() does on boot
    assert dj.run_pending() == 2 and {r["status"] for r in dj.listing("p1")} == {"ready"} and dj.remaining("p1") == before


def test_one_post_at_a_time_per_person_but_other_people_go_ahead(model, web):
    dj.enqueue("p1", "M", items(*POSTS[:2]))
    dj.enqueue("p2", "N", items(POSTS[2]))
    first = dj.claim()
    second = dj.claim()
    assert {first["owner"], second["owner"]} == {"p1", "p2"}      # p1's second post waits while its first is being drafted
    assert dj.claim() is None


def test_in_the_showcase_without_a_key_a_batch_drafts_fixtures_and_fetches_nothing(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(safefetch, "TRANSPORT", lambda *a: pytest.fail("fetched"))
    assert cd.mode() == "sample"
    dj.enqueue("p1", "M", items(*POSTS[:2]))
    dj.run_pending()
    assert [r["status"] for r in dj.listing("p1")] == ["ready", "ready"]


def test_the_list_holds_every_draft_the_person_has_with_published_ones_marked_and_drafting_first(model, web):
    mine = cd.blank("p1", importsource.offline("", "my own words"), "M")
    dj.enqueue("p1", "M", items(POSTS[0]))
    ready = cd.get("p1", mine["id"])
    cd._store("p1", ready, published_by="p1")
    got = dj.listing("p1")
    assert [(r["status"], r["id"] == mine["id"]) for r in got] == [("drafting", False), ("published", True)]
    assert dj.listing("p2") == []


def test_a_failed_post_can_be_removed_by_its_owner_only(model, web):
    web.pages[POSTS[0]] = (404, {"content-type": "text/html"}, b"")
    dj.enqueue("p1", "M", items(POSTS[0]))
    dj.run_pending()
    (r,) = dj.listing("p1")
    assert dj.remove("p2", r["id"]) is False and len(dj.listing("p1")) == 1
    assert dj.remove("p1", r["id"]) is True and dj.listing("p1") == []


def test_a_drafting_post_cannot_be_removed(model, web):
    dj.enqueue("p1", "M", items(POSTS[0]))
    (r,) = dj.listing("p1")
    assert dj.remove("p1", r["id"]) is False


def test_the_worker_thread_drafts_a_queued_batch_by_itself(model, web):
    dj.start(poll=0.05)
    dj.enqueue("p1", "M", items(*POSTS[:2]))
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and any(r["status"] != "ready" for r in dj.listing("p1")):
        time.sleep(0.05)
    assert [r["status"] for r in dj.listing("p1")] == ["ready", "ready"]


def test_starting_twice_makes_one_set_of_workers():
    a = dj.start(poll=0.05)
    assert dj.start(poll=0.05) is a
