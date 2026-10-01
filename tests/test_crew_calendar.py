"""F-043: the calendar's avatars and "planning with you" are the family's real members; the pretend friends and Mom's scripted add
belong to the demo trip only."""

import re
import uuid

import pytest

from gitaway import familydb
from tests.test_calendar import book
from tests.test_members import addr, browser, invite
from tests.test_signin import person, sign_in


def named(local):
    """An address whose display name is clean ("sam.kim" -> Sam Kim) and that nobody else in the run uses."""
    return f"{local}@{uuid.uuid4().hex[:8]}.example.com"


def faces(html):
    """The avatar names in the calendar's top bar."""
    bar = html.split('class="cal-avatars"')[1].split("cal-actions-top")[0]
    return re.findall(r'title="([^"]+)"', bar)


def make_trip_real(traveler="ari"):
    """Turn the open trip into an imported one (what F-042 makes): not a demo trip any more."""
    with familydb.using(person(traveler)) as db:
        with familydb.transaction(db):
            familydb.run(db, "UPDATE trips SET source = 'imported'")


@pytest.fixture
def pair(client):
    """Ari with a booked trip, and Sam Kim (editor) in another browser."""
    book(client)
    sam = named("sam.kim")
    invite(client, sam, "editor")
    other = browser(client)
    sign_in(other, sam)
    return client, other


def test_the_avatars_are_the_real_members(pair):
    ari, sam = pair
    assert faces(ari.get("/calendar?view=days").text)[0] == "Ari Rivera"
    assert "Sam Kim" in faces(ari.get("/calendar?view=days").text)
    seen = faces(sam.get("/calendar?view=days").text)
    assert seen[0] == "Sam Kim" and "Ari Rivera" in seen  # each sees themselves first, then the others


def test_planning_with_you_names_the_real_member(pair):
    ari, sam = pair
    html = ari.get("/calendar?view=days").text
    assert "Sam Kim is planning with you" in html and 'class="cal-presence-dot"' in html
    assert "Ari Rivera is planning with you" in sam.get("/calendar?view=days").text


def test_a_lone_owner_has_nobody_planning_with_them(client):
    book(client)
    html = client.get("/calendar?view=days").text
    assert "planning with you" not in html and faces(html) == ["Ari Rivera"]


def test_more_members_are_named_in_the_presence_line(pair):
    ari, _ = pair
    jo = named("jo.lee")
    invite(ari, jo, "viewer")
    sign_in(browser(ari), jo)
    assert "Sam Kim and Jo Lee are planning with you" in ari.get("/calendar?view=days").text


def test_real_members_show_on_the_demo_trip_too_next_to_the_pretend_friends(pair):
    ari, _ = pair
    ari.post("/calendar/friends", data={"name": "Mom"})
    html = ari.get("/calendar?view=days").text
    assert {"Sam Kim", "Mom"} <= set(faces(html))
    assert "Mom is planning with you" not in html and "Sam Kim is planning with you" in html


# ---- the scripted Mom demo only runs on the demo trip -----------------------------------------------------------------

def test_mom_still_joins_and_adds_travel_town_on_the_demo_trip(client):
    book(client)
    assert client.post("/calendar/friends", data={"name": "Mom"}, follow_redirects=False).status_code == 303
    assert 'data-live="1"' in client.get("/calendar?view=days").text
    r = client.post("/calendar/live", follow_redirects=False)
    assert r.status_code == 303 and "live=1" in r.headers["location"]
    assert "Travel Town" in client.get("/calendar?view=days").text


def test_a_real_trip_has_no_pretend_friends_and_no_scripted_add(client):
    book(client)
    client.post("/calendar/friends", data={"name": "Mom"})  # asked for while it was still a demo trip
    make_trip_real()
    html = client.get("/calendar?view=days").text
    assert 'data-live="1"' not in html and "Mom" not in faces(html)
    r = client.post("/calendar/live", follow_redirects=False)
    assert r.status_code == 303 and "live=1" not in r.headers["location"]
    assert "Travel Town" not in client.get("/calendar?view=days").text


def test_a_real_trip_refuses_the_friend_picker(client):
    book(client)
    make_trip_real()
    r = client.post("/calendar/friends", data={"name": "Mom"}, follow_redirects=False)
    assert r.status_code == 409 and "invite family by email" in r.text
    assert "Mom" not in faces(client.get("/calendar?view=days").text)


def test_a_real_trip_sends_the_invite_button_to_the_family_page(client):
    book(client)
    make_trip_real()
    html = client.get("/calendar?view=days").text
    assert 'id="cal-invite-btn"' in html and 'href="/family#invite"' in html and 'data-id="invite"' not in html
    assert "Quick picks" not in client.get("/calendar?view=days&invite=1").text  # no pretend-friends dialog
    r = client.get("/invite", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/family#invite"


def test_the_demo_trip_keeps_its_invite_dialog_and_points_to_the_real_one(client):
    book(client)
    html = client.get("/calendar?view=days&invite=1").text
    assert "Quick picks" in html and 'href="/family#invite"' in html and "Invite by email on the Family page" in html


def book_html(client):
    return client.get("/calendar?view=days").text


# ---- what a viewer sees ----------------------------------------------------------------------------------------------

def test_a_viewer_sees_the_calendar_with_a_banner_and_no_editing_dialogs(client):
    book(client)
    vi = addr("vi")
    invite(client, vi, "viewer")
    other = browser(client)
    sign_in(other, vi)
    html = other.get("/calendar?view=days").text
    assert 'id="cal-viewer"' in html and "viewer" in html
    assert 'id="cal-invite-btn"' not in html and "Share trip" not in html and "cal-readonly" in html
    assert "cal-readonly" not in book_html(client)
    for path in ("/calendar?view=days&add=1", "/calendar?view=days&edit=a1", "/calendar?view=days&invite=1", "/calendar?voice=1"):
        page = other.get(path).text
        assert "cal-form-title" not in page and "cal-modal" not in page and "vo-panel" not in page, path


def test_an_editor_has_no_viewer_banner_and_an_owner_invites_from_the_family_page(pair):
    ari, sam = pair
    assert 'id="cal-viewer"' not in sam.get("/calendar?view=days").text
    assert "Share trip" in sam.get("/calendar?view=days").text
    make_trip_real()
    assert 'href="/family"' in sam.get("/calendar?view=days").text  # an editor sees a Family button, not Invite
