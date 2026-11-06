"""A creator-imported trip published through the real editor, for the F-196 tests that care about what a stranger sees afterwards (no model, no web: the creator types it)."""

from gitaway import creatordraft
from tests.creator_import_support import as_post, draft_id, form_of, with_edits
from tests.test_signin import tid


def publish_imported(client, name="Maya Chen", title="Three easy days in Santa Monica", link="", **edits):
    """Publish a trip the creator wrote from pasted text (a draft made by the import, so it is a creator-imported trip) and return its slug. `client` is signed in."""
    r = client.post("/creators/import", data={"do": "manual", "text": "Day 1 Santa Monica Pier."}, follow_redirects=False)
    did = draft_id(r)
    fields = form_of(client.get(f"/creators/import/{did}").text, f"/creators/import/{did}", "ci-edit")
    client.post(f"/creators/import/{did}", data=as_post([*with_edits(fields, title=title, name=name, place="la", d0s0_name="Santa Monica Pier", **edits), ("do", "save")]))
    r = client.post(f"/creators/import/{did}", data={"do": "publish", "own": "1"}, follow_redirects=False)
    assert r.status_code == 303, r.text[:400]
    return creatordraft.get(tid(), did)["slug"]
