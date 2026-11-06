"""F-189: the installed app is a share target; a shared link opens the import filled in, signed in or out, and is never fetched on the way."""
from urllib.parse import quote

import pytest

from gitaway import safefetch
from gitaway.pages.sharetarget import shared_link
from tests.test_signin import sign_in

POST = "https://blog.example.com/santa-monica-with-kids"
YT = "https://youtu.be/abc123"


def test_manifest_declares_a_get_share_target(client):
    st = client.get("/manifest.webmanifest").json()["share_target"]
    assert st == {"action": "/share-to-gitaway", "method": "GET", "params": {"title": "title", "text": "text", "url": "url"}}


@pytest.mark.parametrize("args,want", [
    (dict(url=POST, text=YT, title="x"), POST),                           # url wins
    (dict(url="", text=f"Look at this {YT} so good!", title=POST), YT),   # then text
    (dict(title=f"Trip {POST}."), POST),                                  # then title; trailing full stop dropped
    (dict(url="javascript:alert(1)", text="ftp://x.example/a"), ""),      # only http(s)
    (dict(url="not a link", text="hello"), ""),
    (dict(url="javascript:alert(1)", text=POST), POST),                   # an unusable url falls through to the text
    (dict(url="https://" + "a" * 600), ""),                               # too long
])
def test_shared_link_picks_the_first_http_link(args, want):
    assert shared_link(**args) == want


def test_signed_in_the_share_opens_the_import_with_the_link_filled_in(client):
    sign_in(client)
    r = client.get("/share-to-gitaway", params={"text": f"Check this {POST}"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/creators/import?link=" + quote(POST, safe="")
    page = client.get(r.headers["location"]).text
    assert f'value="{POST}"' in page and 'id="ci-link"' in page


def test_the_share_never_fetches(client, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("fetched at share time")
    monkeypatch.setattr(safefetch, "TRANSPORT", boom)
    sign_in(client)
    assert client.get("/share-to-gitaway", params={"url": POST}, follow_redirects=True).status_code == 200


def test_nothing_usable_opens_the_empty_import(client):
    sign_in(client)
    r = client.get("/share-to-gitaway", params={"text": "just words"}, follow_redirects=False)
    assert r.headers["location"] == "/creators/import"


def test_signed_out_goes_to_sign_in_that_returns_to_the_filled_import(client):
    target = "/creators/import?link=" + quote(POST, safe="")
    r = client.get("/share-to-gitaway", params={"url": POST}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == f"/signin?next={quote(target, safe='')}&intent=publish"
    back = sign_in(client, next=target, intent="publish")
    assert back.headers["location"] == target


def test_a_bad_link_in_the_query_is_not_filled_in(client):
    sign_in(client)
    page = client.get("/creators/import", params={"link": "javascript:alert(1)"}).text
    assert "javascript:alert" not in page


def test_the_route_exists_in_production_mode_too(client, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    assert client.get("/share-to-gitaway", params={"url": POST}, follow_redirects=False).status_code == 303


def test_for_creators_says_what_iphone_cannot_do(client):
    assert "iPhone does not let web apps receive shares yet" in client.get("/for-creators").text
