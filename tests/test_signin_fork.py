from gitaway import session as ses
from tests.test_signin import session_data, sign_in, tid


def test_signed_in_fork_link_records_the_fork(client):
    sign_in(client)
    for slug in ["sun-tacos-and-tide-pools", "la-for-two-slow-mornings", "sun-tacos-and-tide-pools"]:
        r = client.get(f"/signin?next=/trips/{slug}&intent=fork", follow_redirects=False)
        assert r.headers["location"] == f"/trips/{slug}"
    assert ses.forks(session_data(client)) == ["sun-tacos-and-tide-pools", "la-for-two-slow-mornings"]


def test_signed_in_non_fork_intent_does_not_fork(client):
    sign_in(client)
    client.get("/signin?next=/trips/sun-tacos-and-tide-pools&intent=save", follow_redirects=False)
    assert "forks" not in session_data(client)

