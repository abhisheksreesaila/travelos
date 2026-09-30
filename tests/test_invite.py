"""Invite and simulated live friends (F-020): the session helpers and the HTTP seam."""

from urllib.parse import quote

import pytest

from gitaway import session as ses
from tests.test_calendar import add, book, tag
from tests.test_signin import session_data, sign_in


def invite(client, name="Mom", **extra):
    return client.post("/calendar/friends", data={"name": name, **extra}, follow_redirects=False)


def live(client, **extra):
    return client.post("/calendar/live", data=extra, follow_redirects=False)


def friend_names(client):
    return session_data(client).get("friends", {}).get("ari", [])


# ---- session helpers -----------------------------------------------------------------------------------------------

def test_add_friend_dedupes_and_is_per_traveler():
    s = {}
    ses.sign_in(s, "ari")
    mom = ses.add_friend(s, "Mom")
    assert (mom.name, mom.initials) == ("Mom", "MO")
    assert ses.add_friend(s, "  mom ").name == "Mom"
    ses.add_friend(s, "Sam")
    assert [f.name for f in ses.friends(s)] == ["Mom", "Sam"]
    ses.sign_in(s, "sam")
    assert ses.friends(s) == []
    ses.sign_out(s)
    assert ses.friends(s) == []


@pytest.mark.parametrize("bad", ["", "   ", "x" * 21, "You", "you"])
def test_bad_friend_names_are_refused(bad):
    s = {}
    ses.sign_in(s, "ari")
    with pytest.raises(ses.FriendError):
        ses.add_friend(s, bad)
    assert ses.friends(s) == []


def test_friends_are_capped():
    s = {}
    ses.sign_in(s, "ari")
    for i in range(ses.MAX_FRIENDS):
        ses.add_friend(s, f"Pal {i}")
    with pytest.raises(ses.FriendError):
        ses.add_friend(s, "One more")


# ---- invite over HTTP ----------------------------------------------------------------------------------------------

def test_invite_adds_a_friend_once(client):
    book(client)
    assert invite(client).status_code == 303
    assert invite(client, "mom").status_code == 303
    assert invite(client, "Sam").status_code == 303
    assert friend_names(client) == ["Mom", "Sam"]


def test_invite_needs_sign_in_and_a_booking(client):
    assert "/signin" in invite(client).headers["location"]
    sign_in(client)
    assert invite(client).headers["location"] == "/calendar"
    assert not session_data(client).get("friends")


def test_bad_invite_name_rerenders_the_dialog_with_the_reason(client):
    book(client)
    r = invite(client, "")
    assert r.status_code == 409 and 'role="alert"' in r.text and "cal-invite" in r.text


def test_signed_out_invite_goes_through_sign_in_with_intent_invite(client):
    r = client.get("/invite", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == f"/signin?next={quote('/calendar', safe='/')}&intent=invite"
    book(client)
    assert client.get("/invite", follow_redirects=False).headers["location"] == "/calendar?invite=1"


def test_invite_is_no_longer_a_placeholder():
    from gitaway.pages import placeholders
    assert "/invite" not in placeholders.PLACEHOLDERS


def test_the_invite_dialog_has_a_name_field_chips_and_a_copy_button(client):
    book(client)
    html = client.get("/calendar?invite=1").text
    assert 'role="dialog"' in html and 'name="name"' in html
    assert 'value="Mom"' in html and 'value="Sam"' in html
    assert "Copy invite link" in html and "data-copy" in html and "https://gitaway.example/join/GA-" in html
    assert "data-close" in html
    assert tag(html, "id", "cal-invite-btn")["href"] == "/calendar?invite=1"
    invite(client)
    chip = client.get("/calendar?invite=1").text
    assert "Mom is in" in chip


# ---- presence and avatars ------------------------------------------------------------------------------------------

def test_invited_friends_show_as_avatars_with_a_presence_line(client):
    book(client)
    assert "is planning with you" not in client.get("/calendar").text
    invite(client)
    invite(client, "Sam")
    html = client.get("/calendar").text
    bar = html[html.index("cal-avatars"):html.index("cal-actions-top")]
    assert ">AR<" in bar and ">MO<" in bar and ">SA<" in bar and bar.count("cal-presence-dot") == 2
    assert "Sam is planning with you" in bar and "Mom is planning" not in bar


def test_friend_names_are_escaped_everywhere(client):
    book(client)
    assert invite(client, "<script>x</script>"[:20]).status_code == 303
    html = client.get("/calendar?invite=1").text
    assert "<script>x" not in html and "&lt;script&gt;x" in html


# ---- scripted liveness ---------------------------------------------------------------------------------------------

def test_live_add_needs_mom_is_idempotent_and_authored_by_mom(client):
    book(client)
    assert "data-live" not in client.get("/calendar").text
    assert live(client).headers["location"] == "/calendar"
    invite(client, "Sam")
    assert live(client).headers["location"] == "/calendar"
    assert "data-live" not in client.get("/calendar").text
    invite(client)
    assert 'data-live="1"' in client.get("/calendar").text
    r = live(client)
    assert r.status_code == 303 and "new=a1" in r.headers["location"] and "live=1" in r.headers["location"]
    st = session_data(client)["cal"]["ari"]
    assert len(st["a"]) == 1 and st["a"][0]["t"] == "Travel Town steam trains" and st["a"][0]["b"] == "Mom"
    assert (st["a"][0]["d"], st["a"][0]["s"], st["a"][0]["e"]) == (2, 600, 750)
    assert len(st["n"]) == 1 and st["n"][0]["b"] == "Mom" and "The little one will love the trains" in st["n"][0]["t"]
    assert live(client).headers["location"] == "/calendar"
    st = session_data(client)["cal"]["ari"]
    assert len(st["a"]) == 1 and len(st["n"]) == 1
    assert "data-live" not in client.get("/calendar").text


def test_the_live_item_has_a_ring_and_pill_once_then_is_a_normal_item_by_mom(client):
    book(client)
    invite(client)
    first = client.get(live(client).headers["location"]).text
    assert "cal-livering" in first and "just now" in first and "cal-pop" in first
    assert "Travel Town steam trains" in first and "Added Travel Town on Sunday." in first
    later = client.get("/calendar").text
    assert "Travel Town steam trains" in later
    assert "cal-livering" not in later and "just now" not in later and "cal-pop" not in later
    assert 'cal-by">Mom<' in later
    feed = later[later.index('id="cal-feed"'):]
    assert "Mom · on Travel Town steam trains" in feed and ">MO<" in feed


def test_a_live_ring_needs_a_real_mom_item_so_a_forged_url_shows_nothing(client):
    book(client)
    add(client, id="a1", day="2", start="14:00", end="15:00", title="Mine")
    assert "cal-livering" not in client.get("/calendar?new=a1&live=1").text


def test_live_clash_falls_back_to_the_next_free_slot(client):
    book(client)
    add(client, id="a1", day="2", start="10:00", end="11:00", title="Mine")
    invite(client)
    live(client)
    st = session_data(client)["cal"]["ari"]
    mom = next(a for a in st["a"] if a.get("b") == "Mom")
    assert mom["d"] == 2 and mom["e"] - mom["s"] == 150
    assert mom["s"] == 660  # 11:00, the first free 2.5 hours after the clash


def test_live_skips_gracefully_when_the_whole_morning_is_taken(client):
    book(client)
    add(client, id="a1", day="2", start="07:00", end="13:00", title="Mine")
    add(client, id="a2", day="2", start="13:00", end="22:00", title="Mine too")
    invite(client)
    r = live(client)
    assert r.status_code == 303 and r.headers["location"] == "/calendar"
    st = session_data(client)["cal"]["ari"]
    assert [a["i"] for a in st["a"]] == ["a1", "a2"] and st["n"] == []
    assert "data-live" not in client.get("/calendar").text  # it will not try again


def test_the_live_add_is_per_trip_so_the_long_demo_gets_its_own(client):
    book(client)
    invite(client)
    live(client)
    assert 'data-live="1"' in client.get("/calendar?demo=long").text
    live(client, demo="long")
    assert "Travel Town steam trains" in client.get("/calendar?demo=long").text


def test_live_needs_sign_in_and_a_booking(client):
    assert live(client).status_code == 303 and "/signin" in live(client).headers["location"]
    sign_in(client)
    assert live(client).headers["location"] == "/calendar"


# ---- authors -------------------------------------------------------------------------------------------------------

def test_the_by_pill_is_you_for_your_own_items(client):
    book(client)
    add(client)
    html = client.get("/calendar").text
    assert 'cal-by">You<' in html


def test_the_invited_friends_avatar_writes_the_note_feed_entry(client):
    book(client)
    invite(client)
    live(client)
    client.post("/calendar/notes", data={"id": "n9", "text": "mine"})
    feed = client.get("/calendar").text
    feed = feed[feed.index('id="cal-feed"'):]
    assert feed.index("Mom · on Travel Town") < feed.index("You · whole trip", feed.index("Mom · on Travel Town"))
