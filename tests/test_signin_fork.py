from tests.test_signin import session_data, sign_in, tid


def test_signed_in_fork_link_records_the_fork(client):
    sign_in(client)
    for slug in ["sun-tacos-and-tide-pools", "la-for-two-slow-mornings", "sun-tacos-and-tide-pools"]:
        r = client.get(f"/signin?next=/trips/{slug}&intent=fork", follow_redirects=False)
        assert r.headers["location"] == f"/trips/{slug}"
    assert session_data(client)["forks"] == {tid("ari"): ["sun-tacos-and-tide-pools", "la-for-two-slow-mornings"]}


def test_signed_in_non_fork_intent_does_not_fork(client):
    sign_in(client)
    client.get("/signin?next=/trips/sun-tacos-and-tide-pools&intent=save", follow_redirects=False)
    assert "forks" not in session_data(client)


def test_post_fork_requires_a_traveler(client):
    r = client.post("/fork", data={"next": "/trips/sun-tacos-and-tide-pools"}, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/signin?next=/trips/sun-tacos-and-tide-pools&intent=fork"


def test_post_fork_adds_once_and_redirects_local_only(client):
    sign_in(client)
    for slug in ["sun-tacos-and-tide-pools", "la-for-two-slow-mornings", "sun-tacos-and-tide-pools"]:
        r = client.post("/fork", data={"next": f"/trips/{slug}"}, follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"] == f"/trips/{slug}"
    assert session_data(client)["forks"] == {tid("ari"): ["sun-tacos-and-tide-pools", "la-for-two-slow-mornings"]}
    assert client.post("/fork", data={"next": "//evil.example"}, follow_redirects=False).headers["location"] == "/"


def test_plan_bar_avatar_uses_traveler_colour(client):
    sign_in(client, "sam")
    assert "ws-avatar fill-grape" in client.get("/plan").text
    sign_in(client, "ari")
    assert "ws-avatar fill-sun" in client.get("/plan").text


def test_sign_in_links_return_to_the_current_page(client):
    assert 'href="/signin?next=%2Fdiscover"' in client.get("/discover").text
    assert 'href="/signin?next=%2Fplan%3Ff%3Df2"' in client.get("/plan?f=f2").text
    assert 'href="/signin"' in client.get("/").text
