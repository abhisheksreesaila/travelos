import base64
import json

import pytest

from gitaway import session as ses


def sign_in(client, traveler="ari", next="/", intent="save"):
    return client.post("/signin", data={"traveler": traveler, "next": next, "intent": intent}, follow_redirects=False)


def session_data(client):
    """Decode the signed session cookie (Starlette: base64(json).timestamp.signature)."""
    raw = client.cookies.get("session_").split(".")[0]
    return json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))


def test_dialog_title_depends_on_intent(client):
    for intent, words in [("pay", "book this trip"), ("fork", "fork this trip"),
                          ("invite", "invite your crew"), ("save", "save this trip")]:
        assert words in client.get(f"/signin?intent={intent}&next=/plan").text
    html = client.get("/signin?intent=pay").text
    assert "Ari Rivera" in html and "Sam Kim" in html and 'role="dialog"' in html
    assert "Cancel" in html and "Nothing here leaves your browser" in html


def test_unknown_intent_falls_back_to_save(client):
    html = client.get("/signin?intent=<script>").text
    assert "save this trip" in html and "<script>" not in html


def test_signin_stores_traveler_and_redirects_to_next(client):
    r = sign_in(client, "sam", next="/plan?f=1")
    assert r.status_code == 303 and r.headers["location"] == "/plan?f=1"
    assert session_data(client)["traveler"] == "sam"


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


def test_unknown_traveler_is_refused(client):
    assert sign_in(client, "nobody").status_code == 400
    assert "Sign out" not in client.get("/").text


def test_already_signed_in_goes_straight_to_next(client):
    sign_in(client)
    r = client.get("/signin?next=/plan&intent=pay", follow_redirects=False)
    assert r.status_code in (302, 303, 307) and r.headers["location"] == "/plan"


def test_fork_intent_adds_slug_once_over_http(client):
    sign_in(client, next="/trips/la-family-week", intent="fork")
    sign_in(client, next="/trips/la-family-week", intent="fork")
    sign_in(client, next="/trips/other", intent="save")
    assert session_data(client)["forks"] == {"ari": ["la-family-week"]}


def test_fork_helpers():
    s = {}
    ses.sign_in(s, "ari")
    assert ses.add_fork(s, "/plan") is False
    assert ses.add_fork(s, "/trips/x?y=1") is True
    assert ses.add_fork(s, "/trips/x") is False
    assert ses.forks(s) == ["x"]
    ses.sign_in(s, "sam")
    assert ses.forks(s) == []
    ses.add_fork(s, "/trips/b")
    ses.sign_in(s, "ari")
    assert ses.forks(s) == ["x"]
    assert ses.current_traveler(s).initials == "AR"
    ses.sign_out(s)
    assert ses.current_traveler(s) is None and ses.forks(s) == []


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
