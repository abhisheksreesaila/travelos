import base64
import json

import pytest

from gitaway import session as ses


EMAILS = {"ari": "ari.rivera@example.com", "sam": "sam.kim@example.com"}


def sign_in(client, traveler="ari", next="/", intent="save"):
    """The local dev sign-in. `traveler` is "ari", "sam" or any email."""
    return client.post("/signin", data={"email": EMAILS.get(traveler, traveler), "next": next, "intent": intent}, follow_redirects=False)


def tid(traveler="ari"):
    """The traveler id (the fh-saas user id) the dev sign-in gives `traveler` ("ari", "sam" or an email). Same id every time."""
    return person(traveler)["user_id"]


def person(traveler="ari"):
    """A session dict for `traveler` signed in as the dev sign-in does it: a real person with a family database behind the session.
    For tests of the model modules (gitaway.session, gitaway.tripcal), which take the session and read and write that family."""
    import main  # noqa: F401 - makes the process work from the test data folder, so a model-only test never writes databases into the project
    from gitaway import auth
    holder = {}
    auth.sign_in_dev(holder, EMAILS.get(traveler, traveler))
    return holder


def stored_booking(traveler="ari"):
    """The booking of the trip `traveler` has open, read from their family database (None when nothing is booked)."""
    return ses.booking(person(traveler))


def stored_calendar(traveler="ari", demo=""):
    """What the family database holds for the open trip's calendar, in the compact shape the old cookie used:
    {"a": [{"i", "d", "s", "e", "t", "k"; "b" when a friend added it}], "n": [{"i", "t"; "a", "b" when set}], "q": last id number}."""
    from gitaway import tripcal
    s = person(traveler)
    a = [{"i": x.id, "d": x.day, "s": x.start, "e": x.end, "t": x.title, "k": x.kind, **({"b": x.by} if x.by else {})} for x in tripcal.activities(s, demo)]
    n = [{"i": x.id, "t": x.text, **({"a": x.act} if x.act else {}), **({"b": x.by} if x.by else {})} for x in tripcal.notes(s, demo)]
    return {"a": a, "n": n, "q": int(tripcal.next_id(s, demo)) - 1}


def user_id(client):
    """The fh-saas user id the session holds."""
    return session_data(client)["user_id"]


def session_data(client):
    """Decode the signed session cookie (Starlette: base64(json).timestamp.signature)."""
    raw = client.cookies.get("session_").split(".")[0]
    return json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))


def test_dialog_title_depends_on_intent(client):
    for intent, words in [("pay", "book this trip"), ("fork", "fork this trip"),
                          ("invite", "invite your crew"), ("save", "save this trip")]:
        assert words in client.get(f"/signin?intent={intent}&next=/plan").text
    html = client.get("/signin?intent=pay").text
    assert "Dev sign-in (local only)" in html and 'type="email"' in html and 'role="dialog"' in html
    assert "Cancel" in html and "Sign in with Google" not in html  # no Google keys in the tests


def test_unknown_intent_falls_back_to_save(client):
    html = client.get("/signin?intent=<script>").text
    assert "save this trip" in html and "<script>" not in html


def test_signin_stores_traveler_and_redirects_to_next(client):
    r = sign_in(client, "sam", next="/plan?f=1")
    assert r.status_code == 303 and r.headers["location"] == "/plan?f=1"
    assert session_data(client)["email"] == "sam.kim@example.com" and session_data(client)["user_id"]


@pytest.mark.parametrize("bad", ["https://evil.example/x", "//evil.example", "/\\evil.example", "\\\\evil",
                                 "javascript:alert(1)", "/%5Cevil", "", "plan", " //evil", "/\nfoo", "http:/evil",
                                 "/%2F/evil", "/\t/evil"])
def test_open_redirects_fall_back_to_root(client, bad):
    assert ses.safe_next(bad) == "/"
    assert sign_in(client, next=bad).headers["location"] == "/"


def test_safe_next_keeps_local_paths():
    assert ses.safe_next("/plan?f=a&h=b") == "/plan?f=a&h=b"
    assert ses.safe_next("/trips/la-family-week") == "/trips/la-family-week"


def test_signed_in_get_with_bad_next_goes_home(client):
    sign_in(client)
    assert client.get("/signin?next=//evil.example", follow_redirects=False).headers["location"] == "/"


def test_a_bad_email_is_refused_with_a_message(client):
    r = sign_in(client, "nobody")
    assert r.status_code == 400 and 'role="alert"' in r.text and "full email" in r.text
    assert "Sign out" not in client.get("/").text


def test_already_signed_in_goes_straight_to_next(client):
    sign_in(client)
    r = client.get("/signin?next=/plan&intent=pay", follow_redirects=False)
    assert r.status_code in (302, 303, 307) and r.headers["location"] == "/plan"


def test_fork_intent_adds_slug_once_over_http(client):
    sign_in(client, next="/trips/sun-tacos-and-tide-pools", intent="fork")
    sign_in(client, next="/trips/sun-tacos-and-tide-pools", intent="fork")
    sign_in(client, next="/trips/la-for-two-slow-mornings", intent="save")
    assert ses.forks(session_data(client)) == ["sun-tacos-and-tide-pools"]


def test_fork_helpers():
    """Forks belong to the signed-in person's family (their database), not to the cookie."""
    from gitaway import auth
    s = {}
    auth.sign_in_dev(s, EMAILS["ari"])
    assert ses.add_fork(s, "/plan") is False
    assert ses.add_fork(s, "/trips/nope") is False  # a trip that does not exist is not forked
    assert ses.add_fork(s, "/trips/sun-tacos-and-tide-pools?y=1") is True
    assert ses.add_fork(s, "/trips/sun-tacos-and-tide-pools") is False
    assert ses.forks(s) == ["sun-tacos-and-tide-pools"]
    ari = dict(s)
    auth.sign_in_dev(s, EMAILS["sam"])
    assert ses.forks(s) == []
    ses.add_fork(s, "/trips/la-for-two-slow-mornings")
    assert ses.forks(ari) == ["sun-tacos-and-tide-pools"]
    assert ses.current_traveler(ari).initials == "AR"
    ses.sign_out(ari)
    assert ses.current_traveler(ari) is None and ses.forks(ari) == []


def test_header_signed_out_and_in(client):
    assert 'href="/signin"' in client.get("/").text
    sign_in(client)
    html = client.get("/discover").text
    assert "AR" in html and "Sign out" in html and 'action="/signout"' in html
    assert 'href="/signin"' not in html


def test_signout(client):
    sign_in(client)
    r = client.post("/signout", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/"
    assert "Sign out" not in client.get("/").text


def test_plan_bar_avatar_follows_traveler(client):
    sign_in(client, "sam")
    html = client.get("/plan").text
    assert ">SK<" in html and ">AR<" not in html


def test_signin_is_no_longer_a_placeholder():
    from gitaway.pages import placeholders
    assert "/signin" not in placeholders.PLACEHOLDERS
