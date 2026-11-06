"""F-182 (M2): content that was taken down, or unpublished, can still be deleted by its owner, and deleting really deletes: the snapshot, the picture files, the draft. The takedowns row stays,
so a taken-down address can never come back. (This reverses the second half of D-106, "the owner cannot unpublish a taken-down trip": see D-120.)"""

import pytest

from gitaway import community, publish
from gitaway import creatordraft as cd
from tests.creator_import_support import with_edits
from tests.test_creator_import import drafted, fields_of, me, model, named, save, web  # noqa: F401  (fixtures and helpers)
from tests.test_publish import family, go_live, stranger  # noqa: F401
from tests.test_signin import person, tid


def _live_with_a_picture(client, did):
    named(client, did)
    save(client, did, with_edits(fields_of(client, did), pick=["1"], cover="1"))
    client.post(f"/creators/import/{did}", data={"do": "publish", "own": "1"})
    slug = cd.get(tid(), did)["slug"]
    assert (publish.root() / slug).is_dir() and list((publish.root() / slug).iterdir())
    return slug


def test_the_owner_can_unpublish_a_trip_the_captain_took_down_and_it_is_really_gone(drafted):
    client, did = drafted
    slug = _live_with_a_picture(client, did)
    community.take_down(slug)
    assert client.post(f"/creators/import/{did}", data={"do": "unpublish"}, follow_redirects=False).status_code == 303
    assert community.get(slug, hidden=True) is None                  # the snapshot is deleted, not just hidden
    assert community.is_down(slug) is True                           # the takedown stays: the address can never come back
    assert not (publish.root() / slug).exists() or not list((publish.root() / slug).iterdir())


def test_community_unpublish_deletes_a_taken_down_row(drafted):
    client, did = drafted
    slug = _live_with_a_picture(client, did)
    community.take_down(slug)
    assert community.unpublish({"user_id": tid()}, slug) is True and community.get(slug, hidden=True) is None
    assert community.unpublish({"user_id": tid("sam")}, slug) is False


def test_unpublishing_a_draft_deletes_its_picture_copies_and_forgets_them(drafted):
    client, did = drafted
    slug = _live_with_a_picture(client, did)
    client.post(f"/creators/import/{did}", data={"do": "unpublish"})
    assert not (publish.root() / slug).exists() or not list((publish.root() / slug).iterdir())
    d = cd.get(tid(), did)
    assert d["live"] is False and d["copies"] == {} and d["picks"] == [] and d["cover"] == ""      # the draft stays; the pictures are picked again if wanted
    assert d["title"].startswith("Three easy days")


def test_a_draft_can_be_deleted_with_its_files_and_its_public_page_even_when_taken_down(drafted):
    client, did = drafted
    slug = _live_with_a_picture(client, did)
    community.take_down(slug)
    r = client.post(f"/creators/import/{did}", data={"do": "delete"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/creators/import"
    assert cd.get(tid(), did) is None and community.get(slug, hidden=True) is None and community.is_down(slug) is True
    assert not (publish.root() / slug).exists()
    assert client.get(f"/creators/import/{did}").status_code == 404


def test_deleting_a_draft_that_was_never_published_works_and_is_the_owners_only(drafted, client):
    c, did = drafted
    other = client.__class__(client.app, client=("127.0.0.1", 50000))
    from tests.test_signin import sign_in
    sign_in(other, "sam")
    assert other.post(f"/creators/import/{did}", data={"do": "delete"}, follow_redirects=False).status_code == 404
    assert cd.get(tid(), did) is not None
    assert c.post(f"/creators/import/{did}", data={"do": "delete"}, follow_redirects=False).status_code == 303 and cd.get(tid(), did) is None


def test_the_editor_offers_delete_with_a_confirm_step(drafted):
    client, did = drafted
    html = client.get(f"/creators/import/{did}").text
    assert 'id="ci-delete"' in html and 'value="delete"' in html


def test_a_family_trip_taken_down_by_the_captain_can_still_be_unpublished_by_its_owner(family):
    client, pid = family
    row = go_live(client, pid)
    slug = row["slug"]
    community.take_down(slug)
    assert client.post("/trip/publish/unpublish", follow_redirects=False).status_code == 303
    assert community.get(slug, hidden=True) is None and community.is_down(slug) and not (publish.root() / slug).exists()


def test_deleting_a_family_trip_removes_a_taken_down_page_and_its_files_too(family):
    client, pid = family
    row = go_live(client, pid)
    slug = row["slug"]
    community.take_down(slug)
    s = person()
    from gitaway import familydb, session as ses
    with ses.family(s) as fam:
        trip_id = familydb.row(fam.db, "SELECT trip_id FROM publications WHERE slug = :s", s=slug)["trip_id"]
    publish.take_down_trip(s, trip_id)
    assert community.get(slug, hidden=True) is None and not (publish.root() / slug).exists()
