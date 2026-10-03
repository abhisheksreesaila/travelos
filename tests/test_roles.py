"""F-043: roles. Viewers read and change nothing; editors change the plans but not the family; admins do both.

The guard test walks every POST route the app has, so a new write route is refused for viewers unless someone lists it as open here
and in gitaway/access.py on purpose."""

import re

import pytest

from gitaway import access, members
from tests.test_calendar import FORM, book
from tests.test_members import addr, browser, invite, tenant
from tests.test_signin import session_data, sign_in, stored_calendar

# Every POST route a viewer may use, and why. Anything else must be refused (403) for a viewer.
OPEN_FOR_VIEWERS = {
    "/signin", "/logout", "/signout",                         # signing in and out
    "/family/phone",                                         # my own phone number (F-069)
    "/trips/switch", "/family/switch", "/family/stay",       # which trip I look at, which family I work in, dismissing the joined notice
    "/creators", "/creators/draft", "/creators/finish",       # a creator draft is the person's own, published to the community
    "/join/{token}",                                          # using an invite link: joining another family
    "/trip/morning", "/trip/morning/time", "/trip/morning/off", "/trip/morning/status",   # a person's own phone reminder (F-066)
    "/trip/photos", "/trip/photos/remove",                     # a viewer may add photos; removing is author-or-admin, checked by the route (F-071)
    "/passkeys/register/options", "/passkeys/register", "/passkeys/auth/options", "/passkeys/auth", "/passkeys/remove",   # a person's own Face ID sign-in (F-074)
    "/trip/family/message", "/trip/family/quiet",             # a viewer may talk in the family thread and silence their own pushes (F-070)
}
ADMIN_ONLY = {"/family/invite", "/family/invite/revoke", "/family/role", "/family/remove", "/trip/delete"}


def post_routes():
    from main import app
    found = {}
    for r in app.routes:
        if "POST" in (getattr(r, "methods", None) or ()):
            found[r.path] = r
    return found


def concrete(path):
    return re.sub(r"\{[^}]+\}", "x", path)


@pytest.fixture
def crew(client):
    """Ari (admin, with a booked trip), an editor and a viewer, each in their own browser."""
    book(client)
    editor_mail, viewer_mail = addr("ed"), addr("vi")
    invite(client, editor_mail, "editor"), invite(client, viewer_mail, "viewer")
    ed, vi = browser(client), browser(client)
    sign_in(ed, editor_mail), sign_in(vi, viewer_mail)
    return client, ed, vi


def test_every_post_route_refuses_a_viewer_unless_it_is_on_the_open_list(crew):
    _, _, viewer = crew
    routes = post_routes()
    assert len(routes) > 25  # the walk really found the app's routes
    open_ones = set()
    for path in sorted(routes, key=lambda p: p in ("/logout", "/signout")):  # signing out ends the session: last
        r = viewer.post(concrete(path), data={}, follow_redirects=False)
        if r.status_code != 403:
            open_ones.add(path)
    assert open_ones == OPEN_FOR_VIEWERS, f"a viewer may use {sorted(open_ones - OPEN_FOR_VIEWERS)}; refused none of {sorted(OPEN_FOR_VIEWERS - open_ones)}"


def test_the_open_list_in_the_guard_is_the_one_this_test_expects():
    listed = set(access.OPEN_POSTS) | {p + "{token}" for p in access.OPEN_PREFIXES}
    assert listed == OPEN_FOR_VIEWERS


def test_family_admin_routes_refuse_editors_too(crew):
    _, editor, _ = crew
    for path in ADMIN_ONLY:
        r = editor.post(path, data={}, follow_redirects=False)
        assert r.status_code == 403 and "Only a family admin" in r.text, path


def test_editors_are_not_refused_the_plan_routes(crew):
    _, editor, _ = crew
    for path in post_routes():
        if path in OPEN_FOR_VIEWERS or path in ADMIN_ONLY or path == "/pay":
            continue
        assert editor.post(concrete(path), data={}, follow_redirects=False).status_code != 403, path


def test_a_refused_viewer_gets_a_friendly_message_and_nothing_changes(crew):
    owner, _, viewer = crew
    before = stored_calendar()
    r = viewer.post("/calendar/activities", data={"id": "a1", **FORM}, follow_redirects=False)
    assert r.status_code == 403 and "look at this family" in r.text and 'id="cal-app"' in r.text  # the calendar again, with the message
    r = viewer.post("/share", data={}, follow_redirects=False)
    assert r.status_code == 403 and "Ask a family admin to make you an editor" in r.text and "Back to the calendar" in r.text
    assert stored_calendar() == before


def test_viewers_cannot_write_through_the_other_family_routes_either(crew):
    owner, _, viewer = crew
    for path, data in [("/calendar/notes", {"id": "n1", "text": "hello"}), ("/calendar/friends", {"name": "Mom"}), ("/save", {"next": "/trips/sun-tacos-and-tide-pools"}),
                       ("/rides", {}), ("/forks/apply", {}), ("/calendar/undo", {}), ("/fork", {"next": "/trips/sun-tacos-and-tide-pools"}), ("/pay", {"f": "f1"})]:
        assert viewer.post(path, data=data, follow_redirects=False).status_code == 403, path
    assert stored_calendar()["n"] == [] and stored_calendar()["a"] == []


def test_a_viewer_still_reads_everything_and_may_switch_trips(crew):
    owner, editor, viewer = crew
    editor.post("/calendar/activities", data={"id": "a1", **FORM})
    html = viewer.get("/calendar?view=days").text
    assert "Venice Canals stroll" in html and "LA with the kids" in html
    assert viewer.post("/trips/switch", data={"trip": "x"}, follow_redirects=False).status_code == 303
    assert viewer.get("/family").status_code == 200


def test_an_editor_edits_the_calendar_and_the_viewer_sees_it(crew):
    owner, editor, viewer = crew
    assert editor.post("/calendar/activities", data={"id": "a1", **FORM}, follow_redirects=False).status_code == 303
    assert "Venice Canals stroll" in viewer.get("/calendar?view=days").text
    assert editor.post("/family/invite", data={"email": addr(), "role": "viewer"}, follow_redirects=False).status_code == 403


def test_a_signed_out_post_is_not_a_role_question(client):
    r = client.post("/calendar/activities", data={"id": "a1", **FORM}, follow_redirects=False)
    assert r.status_code == 303 and "/signin" in r.headers["location"]


def test_a_request_with_a_forged_role_in_the_cookie_still_follows_the_membership(crew):
    """The cookie says tenant_role; the role in force is the membership row."""
    _, _, viewer = crew
    assert session_data(viewer)["tenant_role"] == "viewer"
    assert members.role_in(session_data(viewer)["user_id"], tenant(viewer)) == "viewer"


def test_a_refusal_page_is_private_no_store(crew):
    """F-062: the refusal can show the family's calendar, so the browser must not keep it either."""
    _, _, viewer = crew
    r = viewer.post("/calendar/activities", data=FORM, follow_redirects=False)
    assert r.status_code == 403
    assert r.headers["cache-control"] == "private, no-store"
